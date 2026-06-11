"""Shared helpers for translation quality-gate recovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_neighbor_context(
    source_segments: list[str],
    seg_idx: int,
    *,
    segment_core_text: Callable[[str], str],
    normalize_ws: Callable[[str], str],
    segment_groups: list[int | None] | None = None,
    grouped_indices: dict[int, list[int]] | None = None,
    max_chars: int = 220,
    max_snippets: int = 2,
    dedupe: bool = True,
) -> str:
    candidates: list[int] = []
    if segment_groups is not None and grouped_indices is not None and 0 <= seg_idx < len(segment_groups):
        group_id = segment_groups[seg_idx]
        if group_id is not None:
            indices = grouped_indices.get(group_id, [])
            if seg_idx in indices:
                pos = indices.index(seg_idx)
                candidates.extend(indices[max(0, pos - 1):pos])
                candidates.extend(indices[pos + 1:pos + 2])

    if not candidates:
        candidates.extend([seg_idx - 1, seg_idx + 1])

    snippets: list[str] = []
    for idx in candidates:
        if idx < 0 or idx >= len(source_segments) or idx == seg_idx:
            continue
        core = normalize_ws(segment_core_text(source_segments[idx]))
        if not core:
            continue
        if len(core) > max_chars:
            core = core[:max_chars].rstrip() + "..."
        if dedupe and core in snippets:
            continue
        snippets.append(core)

    if not snippets:
        return ""
    return "Context (for consistency only): " + " ".join(snippets[:max_snippets])


def safe_quality_gate_call(
    action: str,
    seg_idx: int,
    call: Callable[[], object],
    counts: dict[str, int],
    *,
    debug_prefix: str,
    debug: Callable[[str], Any],
) -> object | None:
    try:
        return call()
    except Exception as exc:
        counts["quality_gate_recovery_error"] = counts.get("quality_gate_recovery_error", 0) + 1
        counts[f"quality_gate_{action}_error"] = counts.get(f"quality_gate_{action}_error", 0) + 1
        debug(
            f"{debug_prefix} reason=recovery_error "
            f"seg={seg_idx + 1} action={action} error={type(exc).__name__}"
        )
        return None
