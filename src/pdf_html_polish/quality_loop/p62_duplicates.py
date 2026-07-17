"""Duplicate figure-visual repair helpers for P62 recovery."""

from __future__ import annotations

from pathlib import Path
import struct
from typing import Any, Callable

from pdf_html_polish.atomic_io import write_text_atomic

from .p62_html import (
    P62_LOW_FIDELITY_RECOVERY_SOURCES,
    data_url_image_hash,
    extract_html_figure_units,
    replace_figure_unit_target_with_missing_warning,
    replace_figure_unit_target_with_image,
)


P62_REGION_REPAIR_SOURCES = {"pdf_figure_region_render", "pdf_detached_plate_region_render"}
P62_DUPLICATE_REPAIRABLE_RECOVERY_SOURCES = (
    {"marker_image"} | P62_LOW_FIDELITY_RECOVERY_SOURCES | P62_REGION_REPAIR_SOURCES
)
P62_UNSAFE_DUPLICATE_WARNING_SOURCES = P62_LOW_FIDELITY_RECOVERY_SOURCES | P62_REGION_REPAIR_SOURCES

PdfTextPages = Callable[..., tuple[str, list[str], str | None]]
ResolvePdfPage = Callable[..., dict[str, Any]]
RecoverFigureAsset = Callable[..., dict[str, Any]]
DataUrlFromImage = Callable[[Path], str | None]
Slug = Callable[..., str]


def _image_pixel_size(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)
    if len(data) >= 12 and data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            while marker == 0xFF and index < len(data):
                marker = data[index]
                index += 1
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(data):
                break
            segment_length = struct.unpack(">H", data[index : index + 2])[0]
            if segment_length < 2 or index + segment_length > len(data):
                break
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                if segment_length >= 7:
                    height, width = struct.unpack(">HH", data[index + 3 : index + 7])
                    return int(width), int(height)
                break
            index += segment_length
    return None


def _pdf_region_asset_looks_like_page_strip(asset: dict[str, Any], asset_path: Path) -> dict[str, Any] | None:
    if str(asset.get("source") or "") not in P62_REGION_REPAIR_SOURCES:
        return None
    size = _image_pixel_size(asset_path)
    if size is None:
        return None
    width, height = size
    if width <= 0 or height <= 0:
        return None
    aspect_ratio = float(width) / float(height)
    if width >= 500 and height <= 96 and aspect_ratio >= 8.0:
        return {
            "width": width,
            "height": height,
            "aspect_ratio": round(aspect_ratio, 4),
        }
    return None


def repair_duplicate_figure_images(
    html: str,
    *,
    pdf_path: Path,
    artifact_dir: Path,
    zoom: float,
    pdf_text_pages: PdfTextPages,
    resolve_pdf_page_for_figure: ResolvePdfPage,
    recover_detached_pdf_figure_plate_asset: RecoverFigureAsset,
    recover_pdf_figure_asset: RecoverFigureAsset,
    data_url_from_image_file: DataUrlFromImage,
    slug: Slug,
    repair_plain_duplicates: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    if not pdf_path.is_file():
        return html, []
    units = extract_html_figure_units(html)
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        for image_hash in unit.get("image_hashes") or []:
            by_hash.setdefault(str(image_hash), []).append(unit)

    duplicate_groups = [
        group
        for group in by_hash.values()
        if len({str(unit.get("label") or "") for unit in group}) > 1
    ]
    if not duplicate_groups:
        return html, []

    text_status, pages, text_error = pdf_text_pages(pdf_path, max_pages=None)
    if text_status == "missing" or not pages:
        return html, []

    patched = html
    repairs: list[dict[str, Any]] = []
    repaired_labels: set[str] = set()
    for group in duplicate_groups:
        labels = [str(unit.get("label") or "") for unit in group if unit.get("label")]
        if not any(unit.get("recovery_sources") for unit in group) and not repair_plain_duplicates:
            continue
        plain_candidates = [unit for unit in group if not unit.get("recovery_sources")]
        repair_mode = "plain_duplicate_target"
        if not any(unit.get("recovery_sources") for unit in group):
            repair_mode = "plain_duplicate_group"
            candidates = list(group)
        elif plain_candidates:
            candidates = plain_candidates
        else:
            repair_mode = "recovered_duplicate_target"
            candidates = [
                unit
                for unit in group
                if set(str(source) for source in (unit.get("recovery_sources") or []))
                & P62_DUPLICATE_REPAIRABLE_RECOVERY_SOURCES
            ]
        for unit in candidates:
            label = str(unit.get("label") or "")
            if not label or label in repaired_labels:
                continue
            candidate_recovery_sources = [
                str(source) for source in (unit.get("recovery_sources") or []) if str(source)
            ]
            caption = str(unit.get("caption") or "")
            snippets = [caption] if caption else [f"Figure {label}"]
            resolver = resolve_pdf_page_for_figure(snippets, pages, label, pdf_path=pdf_path)
            page_number = int(resolver.get("page_number") or 0)
            duplicate_hash = str((unit.get("image_hashes") or [""])[0])
            if page_number <= 0 or bool(resolver.get("source_visual_unavailable")):
                repairs.append(
                    {
                        "figure_label": label,
                        "status": "unresolved",
                        "reason": "pdf_page_unavailable_or_source_visual_unavailable",
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "text_layer_status": text_status,
                        "text_layer_error": text_error or "",
                    }
                )
                continue
            repair_dir = artifact_dir / "duplicate_visual_repair" / f"fig_{slug(label, max_len=20)}"
            asset = recover_detached_pdf_figure_plate_asset(
                pdf_path,
                page_number,
                label,
                repair_dir,
                zoom=zoom,
            )
            if not (asset.get("path") and asset.get("source")):
                asset = recover_pdf_figure_asset(
                    pdf_path,
                    page_number,
                    label,
                    repair_dir,
                    zoom=zoom,
                )
            asset_path = Path(str(asset.get("path") or ""))
            strip_like = _pdf_region_asset_looks_like_page_strip(asset, asset_path) if asset_path else None
            if strip_like is not None:
                cleanup_allowed = bool(
                    set(candidate_recovery_sources) & P62_UNSAFE_DUPLICATE_WARNING_SOURCES
                )
                next_html = patched
                replacements = 0
                if cleanup_allowed:
                    next_html, replacements = replace_figure_unit_target_with_missing_warning(
                        patched,
                        figure_label=label,
                        reason="source_visual_unavailable",
                    )
                if replacements:
                    patched = next_html
                    repaired_labels.add(label)
                    repairs.append(
                        {
                            "figure_label": label,
                            "status": "patched",
                            "reason": "pdf_region_asset_looks_like_page_strip",
                            "action": "replaced_duplicate_recovery_with_missing_warning",
                            "source_pdf_page_number": page_number,
                            "duplicate_labels": labels,
                            "duplicate_hash": duplicate_hash,
                            "repair_mode": repair_mode,
                            "candidate_recovery_sources": candidate_recovery_sources,
                            "resolver": resolver,
                            "asset_path": str(asset_path),
                            "asset_source": asset.get("source") or "",
                            "asset_status": asset.get("status") or "",
                            "asset_dimensions": strip_like,
                            "replacement_count": replacements,
                        }
                    )
                    continue
                repairs.append(
                    {
                        "figure_label": label,
                        "status": "unresolved",
                        "reason": "pdf_region_asset_looks_like_page_strip",
                        "source_pdf_page_number": page_number,
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "resolver": resolver,
                        "asset_path": str(asset_path),
                        "asset_source": asset.get("source") or "",
                        "asset_status": asset.get("status") or "",
                        "asset_dimensions": strip_like,
                    }
                )
                continue
            data_url = data_url_from_image_file(asset_path) if asset_path else None
            if not data_url or not asset.get("source"):
                repairs.append(
                    {
                        "figure_label": label,
                        "status": asset.get("status") or "unresolved",
                        "reason": asset.get("error") or "no_recoverable_duplicate_asset",
                        "source_pdf_page_number": page_number,
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "resolver": resolver,
                    }
                )
                continue
            recovered_hash = data_url_image_hash(f'<img src="{data_url}"/>')
            if duplicate_hash and recovered_hash == duplicate_hash:
                repairs.append(
                    {
                        "figure_label": label,
                        "status": "unresolved",
                        "reason": "recovered_asset_matches_duplicate_hash",
                        "source_pdf_page_number": page_number,
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "asset_path": str(asset_path),
                        "asset_source": asset.get("source") or "",
                        "asset_status": asset.get("status") or "",
                        "resolver": resolver,
                    }
                )
                continue
            next_html, replacements = replace_figure_unit_target_with_image(
                patched,
                figure_label=label,
                data_url=data_url,
                source=str(asset.get("source") or ""),
                source_detail=str(asset_path),
            )
            if not replacements:
                repairs.append(
                    {
                        "figure_label": label,
                        "status": "patch_missed",
                        "reason": "figure_unit_target_not_found",
                        "source_pdf_page_number": page_number,
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "asset_path": str(asset_path),
                        "asset_source": asset.get("source") or "",
                    }
                )
                continue
            patched = next_html
            repaired_labels.add(label)
            repairs.append(
                {
                    "figure_label": label,
                    "status": "patched",
                    "source_pdf_page_number": page_number,
                    "duplicate_labels": labels,
                    "duplicate_hash": duplicate_hash,
                    "repair_mode": repair_mode,
                    "candidate_recovery_sources": candidate_recovery_sources,
                    "asset_path": str(asset_path),
                    "asset_source": asset.get("source") or "",
                    "asset_status": asset.get("status") or "",
                    "resolver": resolver,
                    "replacement_count": replacements,
                }
            )
    return patched, repairs


def apply_duplicate_figure_image_repairs(
    targets: list[Path],
    *,
    pdf_path: Path,
    artifact_dir: Path,
    zoom: float,
    pdf_text_pages: PdfTextPages,
    resolve_pdf_page_for_figure: ResolvePdfPage,
    recover_detached_pdf_figure_plate_asset: RecoverFigureAsset,
    recover_pdf_figure_asset: RecoverFigureAsset,
    data_url_from_image_file: DataUrlFromImage,
    slug: Slug,
    repair_plain_duplicates: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "repair_count": 0,
        "patched_paths": [],
        "repairs": [],
        "errors": [],
    }
    if not targets or not pdf_path.is_file():
        return report
    for target_path in targets:
        try:
            html = target_path.read_text(encoding="utf-8", errors="replace")
            patched, repairs = repair_duplicate_figure_images(
                html,
                pdf_path=pdf_path,
                artifact_dir=artifact_dir / slug(target_path.stem, max_len=48),
                zoom=zoom,
                pdf_text_pages=pdf_text_pages,
                resolve_pdf_page_for_figure=resolve_pdf_page_for_figure,
                recover_detached_pdf_figure_plate_asset=recover_detached_pdf_figure_plate_asset,
                recover_pdf_figure_asset=recover_pdf_figure_asset,
                data_url_from_image_file=data_url_from_image_file,
                slug=slug,
                repair_plain_duplicates=repair_plain_duplicates,
            )
            patched_repairs = [repair for repair in repairs if repair.get("status") == "patched"]
            if patched_repairs and patched != html:
                write_text_atomic(target_path, patched)
                report["patched_paths"].append(str(target_path))
                report["repair_count"] += sum(int(repair.get("replacement_count") or 0) for repair in patched_repairs)
            for repair in repairs:
                report["repairs"].append({"path": str(target_path), **repair})
        except OSError as exc:
            report["errors"].append({"path": str(target_path), "error": str(exc)})
    return report
