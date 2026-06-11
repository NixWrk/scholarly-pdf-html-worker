"""Post-reassembly recovery guards for translated segment lists."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PostReassemblyGuardDependencies:
    post_guard_reason: Callable[..., str | None]
    find_contiguous_identity_runs: Callable[..., list[tuple[int, int]]]
    build_neighbor_context: Callable[[int, dict[int, list[int]]], str]
    recover_context: Callable[[str, str, str, int], str]
    recover_single: Callable[[str, str, int], str]
    recover_forced: Callable[[str, str, int], str]
    recover_sentencewise: Callable[[str, str, int], str]
    try_batch_translate: Callable[..., tuple[list[str] | None, str]]
    is_identity_residual: Callable[[str, str], bool]
    sanitize_prompt_leak: Callable[[str, str], tuple[str, Any]]
    strip_unexpected_trailing_ellipsis: Callable[[str, str], tuple[str, bool]]
    format_int_list: Callable[[list[int]], str]
    debug: Callable[[str], Any]


def _increment(counts: dict[str, int], key: str, amount: int = 1) -> None:
    counts[key] = counts.get(key, 0) + amount


def apply_post_reassembly_guards(
    *,
    source_segments: list[str],
    translated_segments: list[str],
    max_chunk_chars: int,
    context_label: str,
    dependencies: PostReassemblyGuardDependencies,
    segment_groups: list[int | None] | None = None,
    enable_paragraph_identity_guard: bool = True,
    enable_identity_residual_guard: bool = True,
    enable_identity_context_recovery: bool = True,
    max_batch_chars_floor: int = 80_000,
) -> tuple[list[str], dict[str, int]]:
    if len(source_segments) != len(translated_segments):
        return translated_segments, {}

    snapshot = list(translated_segments)
    result = list(translated_segments)
    recovery_counts: dict[str, int] = {}
    paragraph_identity_runs: dict[int, list[tuple[int, int]]] = {}
    paragraph_identity_indices: set[int] = set()
    grouped_indices: dict[int, list[int]] = {}
    context_recovered_segments: set[int] = set()

    if segment_groups is not None and len(segment_groups) == len(source_segments):
        for seg_idx, group_id in enumerate(segment_groups):
            if group_id is None:
                continue
            grouped_indices.setdefault(group_id, []).append(seg_idx)
        if enable_identity_residual_guard and enable_paragraph_identity_guard:
            for group_id, indices in grouped_indices.items():
                if len(indices) < 2:
                    continue
                runs = dependencies.find_contiguous_identity_runs(
                    indices,
                    source_segments=source_segments,
                    translated_segments=snapshot,
                    min_total_chars=80,
                )
                if not runs:
                    continue
                paragraph_identity_runs[group_id] = runs
                for run_start, run_end in runs:
                    paragraph_identity_indices.update(range(run_start, run_end + 1))

    def _try_context_recovery_for_index(seg_idx: int) -> bool:
        if not enable_identity_context_recovery:
            return False
        if seg_idx in context_recovered_segments:
            return False

        context_text = dependencies.build_neighbor_context(seg_idx, grouped_indices)
        if not context_text:
            return False

        recovered = dependencies.recover_context(
            source_segments[seg_idx],
            context_text,
            f"{context_label}_context",
            seg_idx + 1,
        )
        context_recovered_segments.add(seg_idx)
        if dependencies.is_identity_residual(source_segments[seg_idx], recovered):
            dependencies.debug(
                f"{context_label}_lenient reason=identity_context_failed "
                f"seg={seg_idx + 1} detail=still_identity"
            )
            return False

        result[seg_idx] = recovered
        _increment(recovery_counts, "identity_context_recovery")
        dependencies.debug(
            f"{context_label}_lenient reason=identity_context_recovery seg={seg_idx + 1}"
        )
        return True

    for idx, (source_seg, translated_seg) in enumerate(
        zip(source_segments, snapshot),
        start=1,
    ):
        prev_seg = snapshot[idx - 2] if idx > 1 else None
        next_seg = snapshot[idx] if idx < len(snapshot) else None
        reason = dependencies.post_guard_reason(
            source_segments=source_segments,
            source_index=idx - 1,
            source_seg=source_seg,
            translated_seg=translated_seg,
            prev_translated=prev_seg,
            next_translated=next_seg,
        )
        if reason is None:
            continue
        if reason == "identity_residual" and not enable_identity_residual_guard:
            continue
        if reason == "identity_residual" and (idx - 1) in paragraph_identity_indices:
            continue

        result[idx - 1] = dependencies.recover_single(source_seg, context_label, idx)
        if reason == "prompt_leak":
            result[idx - 1], _ = dependencies.sanitize_prompt_leak(source_seg, result[idx - 1])
        if reason == "trailing_ellipsis_artifact":
            stripped_seg, stripped = dependencies.strip_unexpected_trailing_ellipsis(
                source_seg,
                result[idx - 1],
            )
            if stripped:
                result[idx - 1] = stripped_seg
                _increment(recovery_counts, "trailing_ellipsis_stripped")
                dependencies.debug(
                    f"{context_label}_lenient reason=trailing_ellipsis_stripped "
                    f"seg={idx} action=post_hoc_strip"
                )
        _increment(recovery_counts, reason)
        dependencies.debug(
            f"{context_label}_lenient reason={reason} seg={idx} action=local_segment_recovery"
        )
        if reason == "identity_residual":
            _finish_identity_recovery(
                source_segments=source_segments,
                result=result,
                seg_idx=idx - 1,
                context_label=context_label,
                recovery_counts=recovery_counts,
                dependencies=dependencies,
                try_context_recovery=_try_context_recovery_for_index,
            )

    if paragraph_identity_runs:
        _recover_paragraph_identity_runs(
            source_segments=source_segments,
            result=result,
            paragraph_identity_runs=paragraph_identity_runs,
            grouped_indices=grouped_indices,
            max_chunk_chars=max_chunk_chars,
            max_batch_chars_floor=max_batch_chars_floor,
            context_label=context_label,
            recovery_counts=recovery_counts,
            dependencies=dependencies,
            try_context_recovery=_try_context_recovery_for_index,
        )

    return result, recovery_counts


def _finish_identity_recovery(
    *,
    source_segments: list[str],
    result: list[str],
    seg_idx: int,
    context_label: str,
    recovery_counts: dict[str, int],
    dependencies: PostReassemblyGuardDependencies,
    try_context_recovery: Callable[[int], bool],
) -> None:
    source_seg = source_segments[seg_idx]
    if dependencies.is_identity_residual(source_seg, result[seg_idx]):
        try_context_recovery(seg_idx)
    if dependencies.is_identity_residual(source_seg, result[seg_idx]):
        forced = dependencies.recover_forced(source_seg, f"{context_label}_forced", seg_idx + 1)
        result[seg_idx] = forced
        if not dependencies.is_identity_residual(source_seg, result[seg_idx]):
            _increment(recovery_counts, "identity_forced_recovery")
            dependencies.debug(
                f"{context_label}_lenient reason=identity_forced_recovery seg={seg_idx + 1}"
            )
    if dependencies.is_identity_residual(source_seg, result[seg_idx]):
        sent_recovered = dependencies.recover_sentencewise(source_seg, f"{context_label}_sent", seg_idx + 1)
        result[seg_idx] = sent_recovered
        if not dependencies.is_identity_residual(source_seg, result[seg_idx]):
            _increment(recovery_counts, "identity_sentence_recovery")
            dependencies.debug(
                f"{context_label}_lenient reason=identity_sentence_recovery seg={seg_idx + 1}"
            )
    if dependencies.is_identity_residual(source_seg, result[seg_idx]):
        _increment(recovery_counts, "identity_terminal")
        dependencies.debug(
            f"{context_label}_lenient reason=identity_terminal seg={seg_idx + 1} "
            "action=keep_recovered"
        )


def _recover_paragraph_identity_runs(
    *,
    source_segments: list[str],
    result: list[str],
    paragraph_identity_runs: dict[int, list[tuple[int, int]]],
    grouped_indices: dict[int, list[int]],
    max_chunk_chars: int,
    max_batch_chars_floor: int,
    context_label: str,
    recovery_counts: dict[str, int],
    dependencies: PostReassemblyGuardDependencies,
    try_context_recovery: Callable[[int], bool],
) -> None:
    for group_id, runs in sorted(paragraph_identity_runs.items()):
        group_indices = grouped_indices.get(group_id, [])
        for run_start, run_end in runs:
            run_indices = list(range(run_start, run_end + 1))
            context_indices = _expanded_context_indices(run_indices, group_indices)
            context_sources = [source_segments[i] for i in context_indices]
            context_result, run_reason = dependencies.try_batch_translate(
                context_sources,
                max_batch_chars=max(max_batch_chars_floor, max_chunk_chars * 8),
                segment_groups=[1] * len(context_sources),
                enable_paragraph_identity_guard=False,
                enable_identity_context_recovery=False,
            )
            if context_result is None:
                run_result = [
                    dependencies.recover_single(source_segments[i], context_label, i + 1)
                    for i in run_indices
                ]
                dependencies.debug(
                    f"{context_label}_lenient reason=identity_residual_paragraph "
                    f"group={group_id} segs={dependencies.format_int_list([i + 1 for i in run_indices])} "
                    f"action=local_segment_recovery reason_detail={run_reason}"
                )
            else:
                run_result = _map_context_result_to_run(
                    run_indices=run_indices,
                    context_indices=context_indices,
                    context_result=context_result,
                    source_segments=source_segments,
                )
                dependencies.debug(
                    f"{context_label}_lenient reason=identity_residual_paragraph "
                    f"group={group_id} segs={dependencies.format_int_list([i + 1 for i in run_indices])} "
                    "action=paragraph_recovery"
                )

            for local_idx, seg_idx in enumerate(run_indices):
                result[seg_idx] = run_result[local_idx]
                _finish_identity_recovery(
                    source_segments=source_segments,
                    result=result,
                    seg_idx=seg_idx,
                    context_label=context_label,
                    recovery_counts=recovery_counts,
                    dependencies=dependencies,
                    try_context_recovery=try_context_recovery,
                )
            _increment(recovery_counts, "identity_residual_paragraph")


def _expanded_context_indices(run_indices: list[int], group_indices: list[int]) -> list[int]:
    context_indices = list(run_indices)
    if len(run_indices) == 1 and len(group_indices) > 1:
        try:
            local_pos = group_indices.index(run_indices[0])
        except ValueError:
            local_pos = -1
        if local_pos >= 0:
            c_start = max(0, local_pos - 1)
            c_end = min(len(group_indices), local_pos + 2)
            expanded = group_indices[c_start:c_end]
            if len(expanded) > 1:
                context_indices = expanded
    return context_indices


def _map_context_result_to_run(
    *,
    run_indices: Sequence[int],
    context_indices: Sequence[int],
    context_result: Sequence[str],
    source_segments: Sequence[str],
) -> list[str]:
    run_result: list[str] = []
    for seg_idx in run_indices:
        try:
            mapped_pos = context_indices.index(seg_idx)
        except ValueError:
            mapped_pos = -1
        if mapped_pos < 0:
            run_result.append(source_segments[seg_idx])
        else:
            run_result.append(context_result[mapped_pos])
    return run_result
