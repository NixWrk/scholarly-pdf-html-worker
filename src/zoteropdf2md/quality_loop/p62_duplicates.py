"""Duplicate figure-visual repair helpers for P62 recovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .p62_html import (
    P62_LOW_FIDELITY_RECOVERY_SOURCES,
    extract_html_figure_units,
    replace_figure_unit_target_with_image,
)


P62_DUPLICATE_REPAIRABLE_RECOVERY_SOURCES = {"marker_image"} | P62_LOW_FIDELITY_RECOVERY_SOURCES

PdfTextPages = Callable[..., tuple[str, list[str], str | None]]
ResolvePdfPage = Callable[..., dict[str, Any]]
RecoverFigureAsset = Callable[..., dict[str, Any]]
DataUrlFromImage = Callable[[Path], str | None]
Slug = Callable[..., str]


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
                target_path.write_text(patched, encoding="utf-8")
                report["patched_paths"].append(str(target_path))
                report["repair_count"] += sum(int(repair.get("replacement_count") or 0) for repair in patched_repairs)
            for repair in repairs:
                report["repairs"].append({"path": str(target_path), **repair})
        except OSError as exc:
            report["errors"].append({"path": str(target_path), "error": str(exc)})
    return report
