"""P62 image recovery stage orchestration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class P62ImageRecoveryStageConfig:
    max_items: int
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


def resolve_p62_image_recovery_stage_config(
    gate_config: dict[str, Any],
    *,
    execute_marker: bool | None = None,
    apply_patches: bool | None = None,
    max_items: int | None = None,
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
    probe_marker_for_unavailable = bool(
        gate_config.get("p62_image_recovery_probe_marker_for_unavailable", resolved_execute_marker)
    )
    return P62ImageRecoveryStageConfig(
        max_items=resolved_max_items,
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
