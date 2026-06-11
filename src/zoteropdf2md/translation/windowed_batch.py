"""Windowed batch orchestration for translation segments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WindowedBatchDependencies:
    try_batch_translate: Callable[..., tuple[list[str] | None, str]]
    recover_single: Callable[[str, int, str, int], str]
    apply_post_reassembly_guards: Callable[
        [list[str], list[str], int, str, list[int | None] | None],
        tuple[list[str], dict[str, int]],
    ]
    debug: Callable[[str], Any]


def try_windowed_batch_translate_with_reason(
    segments: list[str],
    *,
    window_segments: int,
    overlap_segments: int,
    max_window_chars: int,
    max_window_tokens: int = 0,
    count_text_tokens: Callable[[str], int] | None = None,
    segment_groups: list[int | None] | None = None,
    mask_abbrev_flags: list[bool] | None = None,
    dependencies: WindowedBatchDependencies,
) -> tuple[list[str] | None, str]:
    if len(segments) < 2:
        return None, f"single_segment count={len(segments)}"
    if mask_abbrev_flags is not None and len(mask_abbrev_flags) != len(segments):
        return None, "mask_abbrev_flags_length_mismatch"

    window_segments = max(2, int(window_segments))
    overlap_segments = max(0, int(overlap_segments))
    n = len(segments)
    translated: list[str | None] = [None] * n
    leaf_max_chunk_chars = max(256, min(max_window_chars, 1800))

    def _store_core_from_window(
        *,
        core_start: int,
        core_end: int,
        ext_start: int,
        window_result: list[str],
    ) -> None:
        local_start = core_start - ext_start
        for idx in range(core_start, core_end):
            translated[idx] = window_result[local_start + (idx - core_start)]

    def _translate_core_range(core_start: int, core_end: int) -> tuple[bool, str]:
        ext_start = max(0, core_start - overlap_segments)
        ext_end = min(n, core_end + overlap_segments)
        window_result, reason = dependencies.try_batch_translate(
            segments[ext_start:ext_end],
            max_batch_chars=max_window_chars,
            max_batch_tokens=max_window_tokens,
            count_text_tokens=count_text_tokens,
            segment_groups=(
                segment_groups[ext_start:ext_end]
                if segment_groups is not None
                else None
            ),
            mask_abbrev_flags=(
                mask_abbrev_flags[ext_start:ext_end]
                if mask_abbrev_flags is not None
                else None
            ),
            enable_identity_residual_guard=False,
            enable_identity_context_recovery=False,
        )
        if window_result is not None:
            _store_core_from_window(
                core_start=core_start,
                core_end=core_end,
                ext_start=ext_start,
                window_result=window_result,
            )
            return True, "ok"

        dependencies.debug(
            "window_fail "
            f"core=[{core_start}:{core_end}) "
            f"extended=[{ext_start}:{ext_end}) "
            f"reason={reason}"
        )

        core_len = core_end - core_start
        if core_len <= 2:
            dependencies.debug(
                "leaf_per_segment "
                f"core=[{core_start}:{core_end}) "
                f"extended=[{ext_start}:{ext_end}) "
                f"reason={reason}"
            )
            for idx in range(core_start, core_end):
                translated[idx] = dependencies.recover_single(
                    segments[idx],
                    leaf_max_chunk_chars,
                    "window",
                    idx + 1,
                )
            return True, (
                "ok_leaf_per_segment "
                f"core=[{core_start}:{core_end}) "
                f"extended=[{ext_start}:{ext_end}) "
                f"reason={reason}"
            )

        mid = core_start + core_len // 2
        left_ok, left_reason = _translate_core_range(core_start, mid)
        if not left_ok:
            return False, left_reason
        right_ok, right_reason = _translate_core_range(mid, core_end)
        if not right_ok:
            return False, right_reason
        return True, "ok"

    core_start = 0
    while core_start < n:
        core_end = min(n, core_start + window_segments)
        ok, reason = _translate_core_range(core_start, core_end)
        if not ok:
            return None, reason
        core_start = core_end

    if any(item is None for item in translated):
        return None, "window_postcheck_none_entries"
    translated_full = [item for item in translated if item is not None]
    translated_full, guard_recovery_counts = dependencies.apply_post_reassembly_guards(
        segments,
        translated_full,
        leaf_max_chunk_chars,
        "window",
        segment_groups,
    )
    guard_recovered = sum(guard_recovery_counts.values())
    if guard_recovered > 0:
        details = ",".join(
            f"{name}={count}"
            for name, count in sorted(guard_recovery_counts.items())
            if count > 0
        )
        return translated_full, (
            "ok_window_leak_recovery "
            f"count={guard_recovered} details={details}"
        )
    return translated_full, "ok"
