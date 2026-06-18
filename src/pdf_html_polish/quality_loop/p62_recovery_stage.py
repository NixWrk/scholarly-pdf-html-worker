"""P62 image recovery stage orchestration helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class P62ImageRecoveryStageConfig:
    max_items: int
    jobs: int
    execute_marker: bool
    apply_patches: bool
    render_zoom: float
    marker_timeout: int
    probe_source_visual_unavailable: bool
    probe_marker_for_unavailable: bool
    probe_marker_timeout: int
    replace_page_render: bool
    remove_false_match_recovery: bool
    repair_duplicate_figure_images: bool


@dataclass(frozen=True)
class P62PatchTargetDependencies:
    existing_path_candidates: Callable[[Any], Iterable[Path]]
    path_is_inside: Callable[[Path, Path], bool]
    polish_stage: str


@dataclass(frozen=True)
class P62HtmlPatchResult:
    replacement_count: int
    patched_paths: tuple[str, ...]
    errors: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class P62RecoveredAsset:
    data_url: str
    recovery_source: str
    recovery_detail: str
    item_updates: dict[str, Any]


P62_REQUIRED_RECOVERY_CHECKS = (
    "marker_single_page_image",
    "source_visual_unavailable_probe",
    "pdf_detached_plate_region_render",
    "pdf_native_or_region_figure_asset",
    "false_match_recovery_cleanup",
    "pdf_page_render_upgrade",
    "pdf_page_render_fallback",
    "duplicate_figure_visual_repair",
    "html_missing_warning_patch",
)


def resolve_p62_image_recovery_stage_config(
    gate_config: dict[str, Any],
    *,
    execute_marker: bool | None = None,
    apply_patches: bool | None = None,
    max_items: int | None = None,
    jobs: int | None = None,
) -> P62ImageRecoveryStageConfig:
    resolved_max_items = (
        int(gate_config.get("p62_image_recovery_max_articles") or 0)
        if max_items is None
        else max_items
    )
    resolved_execute_marker = (
        bool(gate_config.get("p62_image_recovery_execute_marker", True))
        if execute_marker is None
        else execute_marker
    )
    resolved_apply_patches = (
        bool(gate_config.get("p62_image_recovery_apply_patches", True))
        if apply_patches is None
        else apply_patches
    )
    render_zoom = float(
        gate_config.get("p62_image_recovery_render_zoom")
        or gate_config.get("pdf_problem_evidence_render_zoom")
        or 1.5
    )
    marker_timeout = int(gate_config.get("p62_image_recovery_marker_timeout_seconds") or 300)
    resolved_jobs = (
        int(gate_config.get("p62_image_recovery_jobs") or gate_config.get("document_jobs") or 1)
        if jobs is None
        else jobs
    )
    probe_marker_for_unavailable = bool(
        gate_config.get("p62_image_recovery_probe_marker_for_unavailable", resolved_execute_marker)
    )
    return P62ImageRecoveryStageConfig(
        max_items=resolved_max_items,
        jobs=max(1, resolved_jobs),
        execute_marker=resolved_execute_marker,
        apply_patches=resolved_apply_patches,
        render_zoom=render_zoom,
        marker_timeout=marker_timeout,
        probe_source_visual_unavailable=bool(
            gate_config.get("p62_image_recovery_probe_source_visual_unavailable", True)
        ),
        probe_marker_for_unavailable=probe_marker_for_unavailable,
        probe_marker_timeout=int(
            gate_config.get("p62_image_recovery_source_visual_probe_marker_timeout_seconds")
            or marker_timeout
        ),
        replace_page_render=bool(gate_config.get("p62_image_recovery_replace_page_render", True)),
        remove_false_match_recovery=bool(
            gate_config.get("p62_image_recovery_remove_false_match_recovery", True)
        ),
        repair_duplicate_figure_images=bool(
            gate_config.get("p62_image_recovery_repair_duplicate_figure_images", True)
        ),
    )


def patch_targets_for_record(
    run_dir: Path,
    record: dict[str, Any],
    manifest_article: dict[str, Any],
    *,
    allow_external_paths: bool,
    dependencies: P62PatchTargetDependencies,
) -> list[Path]:
    article_id = str(record.get("article") or manifest_article.get("article_id") or "")
    values: list[Any] = [
        record.get("polish_stage_path"),
        manifest_article.get("polish_path"),
        manifest_article.get("polish_stage_path"),
        manifest_article.get("source_polish_path"),
    ]
    if article_id:
        values.extend(
            [
                run_dir / "polish" / f"{article_id}.{dependencies.polish_stage}",
                run_dir / "audit_tree" / article_id / dependencies.polish_stage,
            ]
        )

    candidates: list[Path] = []
    for value in values:
        for candidate in dependencies.existing_path_candidates(value):
            if not candidate.is_file():
                continue
            if not allow_external_paths and not dependencies.path_is_inside(candidate, run_dir):
                continue
            candidates.append(candidate)

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def apply_html_patch_to_targets(
    targets: Iterable[Path],
    patch_html: Callable[[str], tuple[str, int]],
    *,
    patched_paths: Iterable[str] = (),
    replacement_count: int = 0,
) -> P62HtmlPatchResult:
    patched_path_list = list(patched_paths)
    errors: list[dict[str, str]] = []
    total_replacements = replacement_count
    for target_path in targets:
        try:
            html = target_path.read_text(encoding="utf-8", errors="replace")
            patched, replacements = patch_html(html)
            if replacements:
                target_path.write_text(patched, encoding="utf-8")
                patched_path_list.append(str(target_path))
                total_replacements += replacements
        except OSError as exc:
            errors.append({"path": str(target_path), "error": str(exc)})
    return P62HtmlPatchResult(
        replacement_count=total_replacements,
        patched_paths=tuple(patched_path_list),
        errors=tuple(errors),
    )


def figure_asset_item_updates(figure_asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "figure_asset_status": figure_asset.get("status"),
        "figure_asset_path": figure_asset.get("path") or "",
        "figure_asset_source": figure_asset.get("source") or "",
        "figure_asset_error": figure_asset.get("error") or "",
        "figure_asset_page_number": figure_asset.get("page_number") or 0,
        "figure_asset_selected_rect": figure_asset.get("selected_rect"),
        "figure_asset_caption_found": figure_asset.get("caption_found"),
        "figure_asset_plate_index": figure_asset.get("plate_index"),
        "figure_asset_plate_count": figure_asset.get("plate_count"),
    }


def recover_pdf_figure_asset_for_stage(
    pdf_path: Path,
    source_page_number: int,
    figure_label: str,
    artifact_dir: Path,
    *,
    zoom: float,
    recover_detached_pdf_figure_plate_asset: Callable[..., dict[str, Any]],
    recover_pdf_figure_asset: Callable[..., dict[str, Any]],
    data_url_from_image_file: Callable[[Path], str | None],
) -> P62RecoveredAsset:
    figure_asset = recover_detached_pdf_figure_plate_asset(
        pdf_path,
        source_page_number,
        figure_label,
        artifact_dir,
        zoom=zoom,
    )
    if not (figure_asset.get("path") and figure_asset.get("source")):
        figure_asset = recover_pdf_figure_asset(
            pdf_path,
            source_page_number,
            figure_label,
            artifact_dir,
            zoom=zoom,
        )

    data_url = ""
    recovery_source = ""
    recovery_detail = ""
    if figure_asset.get("path") and figure_asset.get("source"):
        asset_path = Path(str(figure_asset.get("path")))
        data_url = data_url_from_image_file(asset_path) or ""
        if data_url:
            recovery_source = str(figure_asset.get("source") or "pdf_figure_region_render")
            recovery_detail = str(asset_path)

    return P62RecoveredAsset(
        data_url=data_url,
        recovery_source=recovery_source,
        recovery_detail=recovery_detail,
        item_updates=figure_asset_item_updates(figure_asset),
    )


def _source_visual_probe_status(item: dict[str, Any]) -> str:
    probe = item.get("source_visual_probe")
    if isinstance(probe, dict):
        return str(item.get("source_visual_probe_status") or probe.get("status") or "")
    return str(item.get("source_visual_probe_status") or "")


def has_terminal_source_visual_unavailable_evidence(item: dict[str, Any]) -> bool:
    """Return true only when source-unavailable P62 evidence is complete enough."""

    if item.get("asset_status") == "ready":
        return False

    plan_status = str(item.get("plan_status") or "")
    item_status = str(item.get("status") or "")
    if "source_visual_unavailable" not in {plan_status, item_status}:
        return False
    if not str(item.get("source_visual_unavailable_reason") or "").strip():
        return False
    if _source_visual_probe_status(item) != "not_found":
        return False

    probe = item.get("source_visual_probe")
    if not isinstance(probe, dict) or str(probe.get("status") or "") != "not_found":
        return False

    has_label_probe = bool(probe.get("label_pages") or probe.get("attempts"))
    visual_inventory = probe.get("visual_inventory")
    pypdf_image_inventory = probe.get("pypdf_image_inventory")
    has_visual_inventory = isinstance(visual_inventory, dict) and str(
        visual_inventory.get("status") or ""
    ) in {"ready", "empty"}
    has_pypdf_inventory = isinstance(pypdf_image_inventory, dict) and str(
        pypdf_image_inventory.get("status") or ""
    ) in {"ready", "empty"}
    return has_label_probe and has_visual_inventory and has_pypdf_inventory


def _normalize_p62_image_recovery_record(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    if has_terminal_source_visual_unavailable_evidence(normalized):
        normalized["status"] = "source_visual_unavailable"
        normalized.setdefault("terminal_status_reason", "source_visual_unavailable")
    return normalized


def _source_visual_unavailable_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in records:
        if str(item.get("status") or "") != "source_visual_unavailable":
            continue
        source_pdf_path = str(item.get("source_pdf_path") or "")
        figure_label = str(item.get("resolved_figure_label") or item.get("figure_label") or "")
        reason = str(item.get("source_visual_unavailable_reason") or "unknown")
        key = (source_pdf_path, figure_label, reason)
        group = groups.setdefault(
            key,
            {
                "source_pdf_path": source_pdf_path,
                "figure_label": figure_label,
                "source_visual_unavailable_reason": reason,
                "raw_record_count": 0,
                "_articles": set(),
            },
        )
        group["raw_record_count"] += 1
        article = str(item.get("article") or "")
        if article:
            group["_articles"].add(article)

    result: list[dict[str, Any]] = []
    for group in groups.values():
        articles = sorted(group.pop("_articles"))
        group["article_count"] = len(articles)
        group["affected_article_ids"] = articles
        result.append(group)
    result.sort(
        key=lambda item: (
            str(item.get("source_pdf_path") or ""),
            str(item.get("figure_label") or ""),
            str(item.get("source_visual_unavailable_reason") or ""),
        )
    )
    return result


def build_p62_image_recovery_report(
    *,
    generated_at: str,
    run_dir: Path,
    out_path: Path,
    plan_path: Path,
    recovery_root: Path,
    plan_candidate_count: int,
    selected_count: int,
    recovered_records: list[dict[str, Any]],
    patched_article_ids: Iterable[str],
    stage_config: P62ImageRecoveryStageConfig,
    allow_external_paths: bool,
) -> dict[str, Any]:
    report_records = [_normalize_p62_image_recovery_record(item) for item in recovered_records]
    status_counts = Counter(str(item.get("status") or "unknown") for item in report_records)
    source_counts = Counter(
        str(item.get("recovery_source") or item.get("status") or "unresolved")
        for item in report_records
    )
    source_visual_probe_status_counts = Counter(
        str(item.get("source_visual_probe_status") or "not_run") for item in report_records
    )
    asset_ready_count = sum(1 for item in report_records if item.get("asset_status") == "ready")
    source_visual_unavailable_count = int(status_counts.get("source_visual_unavailable", 0))
    source_visual_unavailable_groups = _source_visual_unavailable_groups(report_records)
    patched_warning_count = sum(int(item.get("patch_replacement_count") or 0) for item in report_records)
    page_render_upgrade_count = sum(1 for item in report_records if item.get("existing_page_render_upgrade"))
    page_render_recovery_removed_count = sum(
        1 for item in report_records if item.get("page_render_recovery_removed")
    )
    false_match_recovery_removed_count = sum(
        1 for item in report_records if item.get("false_match_recovery_removed")
    )
    duplicate_visual_repair_count = sum(
        int(item.get("duplicate_visual_repair_count") or 0) for item in report_records
    )
    patch_missed_count = int(status_counts.get("asset_ready_patch_missed", 0))
    unresolved_count = len(report_records) - asset_ready_count - source_visual_unavailable_count
    if selected_count == 0 and plan_candidate_count == 0:
        status = "not_required"
    elif unresolved_count == 0 and patch_missed_count == 0:
        status = "ready"
    elif asset_ready_count:
        status = "partial"
    else:
        status = "unresolved"

    return {
        "generated_at": generated_at,
        "run_dir": str(run_dir),
        "path": str(out_path),
        "plan_path": str(plan_path),
        "output_root": str(recovery_root),
        "status": status,
        "required_checks": list(P62_REQUIRED_RECOVERY_CHECKS),
        "candidate_count": int(plan_candidate_count or selected_count),
        "selected_count": selected_count,
        "asset_ready_count": asset_ready_count,
        "patched_warning_count": patched_warning_count,
        "patched_articles": sorted(patched_article_ids),
        "page_render_upgrade_count": page_render_upgrade_count,
        "page_render_recovery_removed_count": page_render_recovery_removed_count,
        "false_match_recovery_removed_count": false_match_recovery_removed_count,
        "duplicate_visual_repair_count": duplicate_visual_repair_count,
        "patch_missed_count": patch_missed_count,
        "source_visual_unavailable_count": source_visual_unavailable_count,
        "source_visual_unavailable_group_count": len(source_visual_unavailable_groups),
        "source_visual_unavailable_groups": source_visual_unavailable_groups,
        "unresolved_count": unresolved_count,
        "execute_marker": stage_config.execute_marker,
        "apply_patches": stage_config.apply_patches,
        "jobs": stage_config.jobs,
        "allow_external_paths": allow_external_paths,
        "replace_page_render": stage_config.replace_page_render,
        "remove_false_match_recovery": stage_config.remove_false_match_recovery,
        "repair_duplicate_figure_images": stage_config.repair_duplicate_figure_images,
        "render_zoom": stage_config.render_zoom,
        "marker_timeout_seconds": stage_config.marker_timeout,
        "probe_source_visual_unavailable": stage_config.probe_source_visual_unavailable,
        "probe_marker_for_unavailable": stage_config.probe_marker_for_unavailable,
        "source_visual_probe_marker_timeout_seconds": stage_config.probe_marker_timeout,
        "status_counts": dict(sorted(status_counts.items())),
        "recovery_source_counts": dict(sorted(source_counts.items())),
        "source_visual_probe_status_counts": dict(sorted(source_visual_probe_status_counts.items())),
        "articles": report_records,
    }
