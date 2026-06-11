"""Shared helpers for translation quality-gate recovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EnResidualQualityGateDependencies:
    apply_short_translation_guard: Callable[[str, str], tuple[str, str | None]]
    is_identity_residual: Callable[[str, str], bool]
    segment_core_text: Callable[[str], str]
    normalize_ws: Callable[[str], str]
    strip_unexpected_trailing_ellipsis: Callable[[str, str], tuple[str, bool]]
    recover_parts_slice: Callable[[list[str], int, int, str, int], list[str] | None]
    recover_context: Callable[[str, str, str, int], str]
    recover_forced: Callable[[str, str, int], str]
    recover_sentencewise: Callable[[str, str, int], str]
    debug: Callable[[str], Any]


@dataclass(frozen=True)
class CjkQualityGateDependencies:
    normalize_language_code: Callable[[str | None], str]
    has_unexpected_cjk: Callable[..., bool]
    repair_known_cjk_contamination: Callable[..., str]
    segment_core_text: Callable[[str], str]
    normalize_ws: Callable[[str], str]
    strip_unexpected_trailing_ellipsis: Callable[[str, str], tuple[str, bool]]
    recover_parts_slice: Callable[[list[str], int, int, str, int], list[str] | None]
    recover_context: Callable[[str, str, str, int], str]
    recover_forced: Callable[[str, str, int], str]
    debug: Callable[[str], Any]


def _increment(counts: dict[str, int], key: str, amount: int = 1) -> None:
    counts[key] = counts.get(key, 0) + amount


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


def apply_en_residual_quality_gate(
    *,
    source_parts: list[str],
    translated_parts: list[str],
    translatable_indices: list[int],
    source_segments: list[str],
    paragraph_groups: list[int | None],
    paragraph_part_ranges: dict[int, tuple[int, int]],
    max_chunk_chars: int,
    max_segments: int,
    dependencies: EnResidualQualityGateDependencies,
) -> tuple[list[str], dict[str, int]]:
    if (
        len(translatable_indices) != len(source_segments)
        or len(source_segments) != len(paragraph_groups)
    ):
        return translated_parts, {}

    residual_indices = [
        seg_idx
        for seg_idx, (part_idx, source_seg) in enumerate(zip(translatable_indices, source_segments))
        if dependencies.is_identity_residual(source_seg, translated_parts[part_idx])
    ]
    if not residual_indices:
        return translated_parts, {}

    counts: dict[str, int] = {}
    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(residual_indices)
        return translated_parts, counts

    grouped_indices = _group_indices(paragraph_groups)
    result_parts = list(translated_parts)
    processed = 0

    for seg_idx in residual_indices:
        part_idx = translatable_indices[seg_idx]
        source_seg = source_segments[seg_idx]
        if not dependencies.is_identity_residual(source_seg, result_parts[part_idx]):
            continue
        if processed >= max_segments:
            _increment(counts, "quality_gate_skipped_limit")
            continue

        processed += 1
        _increment(counts, "quality_gate_attempted")

        recovered = False
        group_id = paragraph_groups[seg_idx]
        part_range = paragraph_part_ranges.get(group_id) if group_id is not None else None
        if part_range is not None:
            recovered, result_parts = _try_en_paragraph_recovery(
                source_parts=source_parts,
                result_parts=result_parts,
                source_seg=source_seg,
                seg_idx=seg_idx,
                part_idx=part_idx,
                part_range=part_range,
                max_chunk_chars=max_chunk_chars,
                counts=counts,
                dependencies=dependencies,
            )

        if not recovered:
            context_text = build_neighbor_context(
                source_segments,
                seg_idx,
                segment_groups=paragraph_groups,
                grouped_indices=grouped_indices,
                segment_core_text=dependencies.segment_core_text,
                normalize_ws=dependencies.normalize_ws,
            )
            if context_text:
                candidate = safe_quality_gate_call(
                    "context",
                    seg_idx,
                    lambda: dependencies.recover_context(
                        source_seg,
                        context_text,
                        "quality_gate_context",
                        seg_idx + 1,
                    ),
                    counts,
                    debug_prefix="quality_gate",
                    debug=dependencies.debug,
                )
                if isinstance(candidate, str):
                    candidate, candidate_ok = _prepare_en_candidate(source_seg, candidate, counts, dependencies)
                    if candidate_ok and not dependencies.is_identity_residual(source_seg, candidate):
                        result_parts[part_idx] = candidate
                        recovered = True
                        _increment(counts, "quality_gate_context_recovery")
                        dependencies.debug(
                            "quality_gate reason=en_residual "
                            f"seg={seg_idx + 1} action=context_recovery"
                        )

        if not recovered:
            recovered = _try_en_single_segment_recovery(
                action="forced",
                success_count="quality_gate_forced_recovery",
                context_label="quality_gate_forced",
                debug_prefix="quality_gate",
                source_seg=source_seg,
                seg_idx=seg_idx,
                counts=counts,
                dependencies=dependencies,
                recover=dependencies.recover_forced,
                assign=lambda candidate: result_parts.__setitem__(part_idx, candidate),
            )

        if not recovered:
            recovered = _try_en_single_segment_recovery(
                action="sentence",
                success_count="quality_gate_sentence_recovery",
                context_label="quality_gate_sent",
                debug_prefix="quality_gate",
                source_seg=source_seg,
                seg_idx=seg_idx,
                counts=counts,
                dependencies=dependencies,
                recover=dependencies.recover_sentencewise,
                assign=lambda candidate: result_parts.__setitem__(part_idx, candidate),
            )

        if not recovered:
            _increment(counts, "quality_gate_unresolved")
            dependencies.debug(
                "quality_gate reason=en_residual "
                f"seg={seg_idx + 1} action=keep_unresolved"
            )

    return result_parts, counts


def apply_en_residual_segment_quality_gate(
    *,
    source_segments: list[str],
    translated_segments: list[str],
    max_segments: int,
    dependencies: EnResidualQualityGateDependencies,
) -> tuple[list[str], dict[str, int]]:
    if len(source_segments) != len(translated_segments):
        return translated_segments, {}

    residual_indices = [
        idx
        for idx, (source_seg, translated_seg) in enumerate(zip(source_segments, translated_segments))
        if dependencies.is_identity_residual(source_seg, translated_seg)
    ]
    if not residual_indices:
        return translated_segments, {}

    counts: dict[str, int] = {}
    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(residual_indices)
        return translated_segments, counts

    result = list(translated_segments)
    processed = 0
    for seg_idx in residual_indices:
        source_seg = source_segments[seg_idx]
        if not dependencies.is_identity_residual(source_seg, result[seg_idx]):
            continue
        if processed >= max_segments:
            _increment(counts, "quality_gate_skipped_limit")
            continue

        processed += 1
        _increment(counts, "quality_gate_attempted")

        recovered = False
        context_text = build_neighbor_context(
            source_segments,
            seg_idx,
            segment_core_text=dependencies.segment_core_text,
            normalize_ws=dependencies.normalize_ws,
            dedupe=False,
        )
        if context_text:
            candidate = safe_quality_gate_call(
                "context",
                seg_idx,
                lambda: dependencies.recover_context(
                    source_seg,
                    context_text,
                    "quality_gate_fallback_context",
                    seg_idx + 1,
                ),
                counts,
                debug_prefix="quality_gate_fallback",
                debug=dependencies.debug,
            )
            if isinstance(candidate, str):
                candidate, candidate_ok = _prepare_en_candidate(source_seg, candidate, counts, dependencies)
                if candidate_ok and not dependencies.is_identity_residual(source_seg, candidate):
                    result[seg_idx] = candidate
                    recovered = True
                    _increment(counts, "quality_gate_context_recovery")
                    dependencies.debug(
                        "quality_gate_fallback reason=en_residual "
                        f"seg={seg_idx + 1} action=context_recovery"
                    )

        if not recovered:
            recovered = _try_en_single_segment_recovery(
                action="forced",
                success_count="quality_gate_forced_recovery",
                context_label="quality_gate_fallback_forced",
                debug_prefix="quality_gate_fallback",
                source_seg=source_seg,
                seg_idx=seg_idx,
                counts=counts,
                dependencies=dependencies,
                recover=dependencies.recover_forced,
                assign=lambda candidate: result.__setitem__(seg_idx, candidate),
            )

        if not recovered:
            recovered = _try_en_single_segment_recovery(
                action="sentence",
                success_count="quality_gate_sentence_recovery",
                context_label="quality_gate_fallback_sent",
                debug_prefix="quality_gate_fallback",
                source_seg=source_seg,
                seg_idx=seg_idx,
                counts=counts,
                dependencies=dependencies,
                recover=dependencies.recover_sentencewise,
                assign=lambda candidate: result.__setitem__(seg_idx, candidate),
            )

        if not recovered:
            _increment(counts, "quality_gate_unresolved")
            dependencies.debug(
                "quality_gate_fallback reason=en_residual "
                f"seg={seg_idx + 1} action=keep_unresolved"
            )

    return result, counts


def apply_cjk_quality_gate(
    *,
    source_parts: list[str],
    translated_parts: list[str],
    translatable_indices: list[int],
    source_segments: list[str],
    paragraph_groups: list[int | None],
    paragraph_part_ranges: dict[int, tuple[int, int]],
    max_chunk_chars: int,
    max_segments: int,
    target_language_code: str,
    dependencies: CjkQualityGateDependencies,
) -> tuple[list[str], dict[str, int]]:
    if dependencies.normalize_language_code(target_language_code) == "zh":
        return translated_parts, {}
    if (
        len(translatable_indices) != len(source_segments)
        or len(source_segments) != len(paragraph_groups)
    ):
        return translated_parts, {}

    cjk_indices = [
        seg_idx
        for seg_idx, part_idx in enumerate(translatable_indices)
        if dependencies.has_unexpected_cjk(translated_parts[part_idx], target_language_code=target_language_code)
    ]
    if not cjk_indices:
        return translated_parts, {}

    counts: dict[str, int] = {}
    result_parts = list(translated_parts)
    cjk_indices, known_attempted = _apply_known_cjk_repairs(
        cjk_indices=cjk_indices,
        get_source=lambda seg_idx: source_segments[seg_idx],
        get_translated=lambda seg_idx: result_parts[translatable_indices[seg_idx]],
        set_translated=lambda seg_idx, value: result_parts.__setitem__(translatable_indices[seg_idx], value),
        target_language_code=target_language_code,
        debug_prefix="cjk_gate",
        counts=counts,
        dependencies=dependencies,
    )
    if not cjk_indices:
        return result_parts, counts

    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(cjk_indices)
        return result_parts, counts

    grouped_indices = _group_indices(paragraph_groups)
    processed = 0

    for seg_idx in cjk_indices:
        part_idx = translatable_indices[seg_idx]
        if not dependencies.has_unexpected_cjk(result_parts[part_idx], target_language_code=target_language_code):
            continue
        if processed >= max_segments:
            _increment(counts, "quality_gate_skipped_limit")
            continue

        processed += 1
        if seg_idx not in known_attempted:
            _increment(counts, "quality_gate_attempted")

        recovered = False
        group_id = paragraph_groups[seg_idx]
        part_range = paragraph_part_ranges.get(group_id) if group_id is not None else None
        if part_range is not None:
            recovered, result_parts = _try_cjk_paragraph_recovery(
                source_parts=source_parts,
                result_parts=result_parts,
                part_idx=part_idx,
                part_range=part_range,
                seg_idx=seg_idx,
                max_chunk_chars=max_chunk_chars,
                target_language_code=target_language_code,
                counts=counts,
                dependencies=dependencies,
            )

        if not recovered:
            context_text = build_neighbor_context(
                source_segments,
                seg_idx,
                segment_groups=paragraph_groups,
                grouped_indices=grouped_indices,
                segment_core_text=dependencies.segment_core_text,
                normalize_ws=dependencies.normalize_ws,
            )
            if context_text:
                recovered = _try_cjk_context_recovery(
                    source_seg=source_segments[seg_idx],
                    context_text=context_text,
                    result_parts=result_parts,
                    part_idx=part_idx,
                    seg_idx=seg_idx,
                    target_language_code=target_language_code,
                    counts=counts,
                    dependencies=dependencies,
                )

        if not recovered:
            recovered = _try_cjk_forced_recovery(
                source_seg=source_segments[seg_idx],
                seg_idx=seg_idx,
                target_language_code=target_language_code,
                counts=counts,
                dependencies=dependencies,
                context_label="cjk_gate_forced",
                debug_prefix="cjk_gate",
                assign=lambda candidate: result_parts.__setitem__(part_idx, candidate),
                strip_ellipsis=True,
            )

        if not recovered:
            _increment(counts, "quality_gate_unresolved")
            dependencies.debug(
                "cjk_gate reason=cjk_contamination "
                f"seg={seg_idx + 1} action=keep_unresolved"
            )

    return result_parts, counts


def apply_cjk_segment_quality_gate(
    *,
    source_segments: list[str],
    translated_segments: list[str],
    max_segments: int,
    target_language_code: str,
    dependencies: CjkQualityGateDependencies,
) -> tuple[list[str], dict[str, int]]:
    if dependencies.normalize_language_code(target_language_code) == "zh":
        return translated_segments, {}
    if len(source_segments) != len(translated_segments):
        return translated_segments, {}

    cjk_indices = [
        idx
        for idx, translated_seg in enumerate(translated_segments)
        if dependencies.has_unexpected_cjk(translated_seg, target_language_code=target_language_code)
    ]
    if not cjk_indices:
        return translated_segments, {}

    counts: dict[str, int] = {}
    result = list(translated_segments)
    cjk_indices, known_attempted = _apply_known_cjk_repairs(
        cjk_indices=cjk_indices,
        get_source=lambda seg_idx: source_segments[seg_idx],
        get_translated=lambda seg_idx: result[seg_idx],
        set_translated=lambda seg_idx, value: result.__setitem__(seg_idx, value),
        target_language_code=target_language_code,
        debug_prefix="cjk_gate_fallback",
        counts=counts,
        dependencies=dependencies,
    )
    if not cjk_indices:
        return result, counts

    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(cjk_indices)
        return result, counts

    processed = 0
    for seg_idx in cjk_indices:
        if not dependencies.has_unexpected_cjk(result[seg_idx], target_language_code=target_language_code):
            continue
        if processed >= max_segments:
            _increment(counts, "quality_gate_skipped_limit")
            continue

        processed += 1
        if seg_idx not in known_attempted:
            _increment(counts, "quality_gate_attempted")
        recovered = _try_cjk_forced_recovery(
            source_seg=source_segments[seg_idx],
            seg_idx=seg_idx,
            target_language_code=target_language_code,
            counts=counts,
            dependencies=dependencies,
            context_label="cjk_gate_fallback_forced",
            debug_prefix="cjk_gate_fallback",
            assign=lambda candidate: result.__setitem__(seg_idx, candidate),
            strip_ellipsis=False,
        )
        if recovered:
            continue

        _increment(counts, "quality_gate_unresolved")
        dependencies.debug(
            "cjk_gate_fallback reason=cjk_contamination "
            f"seg={seg_idx + 1} action=keep_unresolved"
        )

    return result, counts


def _group_indices(segment_groups: list[int | None]) -> dict[int, list[int]]:
    grouped_indices: dict[int, list[int]] = {}
    for seg_idx, group_id in enumerate(segment_groups):
        if group_id is None:
            continue
        grouped_indices.setdefault(group_id, []).append(seg_idx)
    return grouped_indices


def _guard_en_quality_candidate(
    source_seg: str,
    candidate: str,
    counts: dict[str, int],
    dependencies: EnResidualQualityGateDependencies,
) -> tuple[str, bool]:
    guarded, guard_reason = dependencies.apply_short_translation_guard(source_seg, candidate)
    if guard_reason is None:
        return candidate, True
    _increment(counts, "quality_gate_short_guard_rejected")
    _increment(counts, f"quality_gate_short_guard_{guard_reason}")
    return guarded, False


def _prepare_en_candidate(
    source_seg: str,
    candidate: str,
    counts: dict[str, int],
    dependencies: EnResidualQualityGateDependencies,
) -> tuple[str, bool]:
    stripped_candidate, stripped = dependencies.strip_unexpected_trailing_ellipsis(source_seg, candidate)
    if stripped:
        candidate = stripped_candidate
    return _guard_en_quality_candidate(source_seg, candidate, counts, dependencies)


def _try_en_paragraph_recovery(
    *,
    source_parts: list[str],
    result_parts: list[str],
    source_seg: str,
    seg_idx: int,
    part_idx: int,
    part_range: tuple[int, int],
    max_chunk_chars: int,
    counts: dict[str, int],
    dependencies: EnResidualQualityGateDependencies,
) -> tuple[bool, list[str]]:
    slice_chars = sum(len(source_parts[idx]) for idx in range(part_range[0], part_range[1] + 1))
    if slice_chars > max(2_500, max_chunk_chars * 2):
        _increment(counts, "quality_gate_paragraph_skipped_large")
        return False, result_parts

    recovered_slice = safe_quality_gate_call(
        "paragraph",
        seg_idx,
        lambda: dependencies.recover_parts_slice(
            source_parts,
            part_range[0],
            part_range[1],
            "quality_gate_wide",
            seg_idx + 1,
        ),
        counts,
        debug_prefix="quality_gate",
        debug=dependencies.debug,
    )
    if recovered_slice is None:
        return False, result_parts

    candidate_parts = list(result_parts)
    candidate_parts[part_range[0]:part_range[1] + 1] = recovered_slice
    candidate = candidate_parts[part_idx]
    candidate, candidate_ok = _guard_en_quality_candidate(source_seg, candidate, counts, dependencies)
    candidate_parts[part_idx] = candidate
    if candidate_ok and not dependencies.is_identity_residual(source_seg, candidate):
        _increment(counts, "quality_gate_paragraph_recovery")
        dependencies.debug(
            "quality_gate reason=en_residual "
            f"seg={seg_idx + 1} action=paragraph_recovery"
        )
        return True, candidate_parts
    return False, result_parts


def _try_en_single_segment_recovery(
    *,
    action: str,
    success_count: str,
    context_label: str,
    debug_prefix: str,
    source_seg: str,
    seg_idx: int,
    counts: dict[str, int],
    dependencies: EnResidualQualityGateDependencies,
    recover: Callable[[str, str, int], str],
    assign: Callable[[str], Any],
) -> bool:
    candidate = safe_quality_gate_call(
        action,
        seg_idx,
        lambda: recover(source_seg, context_label, seg_idx + 1),
        counts,
        debug_prefix=debug_prefix,
        debug=dependencies.debug,
    )
    if not isinstance(candidate, str):
        return False
    candidate, candidate_ok = _prepare_en_candidate(source_seg, candidate, counts, dependencies)
    if not candidate_ok or dependencies.is_identity_residual(source_seg, candidate):
        return False

    assign(candidate)
    _increment(counts, success_count)
    dependencies.debug(
        f"{debug_prefix} reason=en_residual "
        f"seg={seg_idx + 1} action={action}_recovery"
    )
    return True


def _apply_known_cjk_repairs(
    *,
    cjk_indices: list[int],
    get_source: Callable[[int], str],
    get_translated: Callable[[int], str],
    set_translated: Callable[[int, str], Any],
    target_language_code: str,
    debug_prefix: str,
    counts: dict[str, int],
    dependencies: CjkQualityGateDependencies,
) -> tuple[list[int], set[int]]:
    known_attempted: set[int] = set()
    remaining_cjk_indices: list[int] = []
    for seg_idx in cjk_indices:
        translated = get_translated(seg_idx)
        repaired = dependencies.repair_known_cjk_contamination(
            get_source(seg_idx),
            translated,
            target_language_code=target_language_code,
        )
        if repaired != translated:
            set_translated(seg_idx, repaired)
            known_attempted.add(seg_idx)
            _increment(counts, "quality_gate_attempted")
            if not dependencies.has_unexpected_cjk(repaired, target_language_code=target_language_code):
                _increment(counts, "quality_gate_known_recovery")
                dependencies.debug(
                    f"{debug_prefix} reason=cjk_contamination "
                    f"seg={seg_idx + 1} action=known_repair"
                )
                continue
        remaining_cjk_indices.append(seg_idx)
    return remaining_cjk_indices, known_attempted


def _try_cjk_paragraph_recovery(
    *,
    source_parts: list[str],
    result_parts: list[str],
    part_idx: int,
    part_range: tuple[int, int],
    seg_idx: int,
    max_chunk_chars: int,
    target_language_code: str,
    counts: dict[str, int],
    dependencies: CjkQualityGateDependencies,
) -> tuple[bool, list[str]]:
    slice_chars = sum(len(source_parts[idx]) for idx in range(part_range[0], part_range[1] + 1))
    if slice_chars > max(2_500, max_chunk_chars * 2):
        _increment(counts, "quality_gate_paragraph_skipped_large")
        return False, result_parts

    recovered_slice = safe_quality_gate_call(
        "paragraph",
        seg_idx,
        lambda: dependencies.recover_parts_slice(
            source_parts,
            part_range[0],
            part_range[1],
            "cjk_gate_wide",
            seg_idx + 1,
        ),
        counts,
        debug_prefix="cjk_gate",
        debug=dependencies.debug,
    )
    if recovered_slice is None:
        return False, result_parts

    candidate_parts = list(result_parts)
    candidate_parts[part_range[0]:part_range[1] + 1] = recovered_slice
    if not dependencies.has_unexpected_cjk(candidate_parts[part_idx], target_language_code=target_language_code):
        _increment(counts, "quality_gate_paragraph_recovery")
        dependencies.debug(
            "cjk_gate reason=cjk_contamination "
            f"seg={seg_idx + 1} action=paragraph_recovery"
        )
        return True, candidate_parts
    return False, result_parts


def _try_cjk_context_recovery(
    *,
    source_seg: str,
    context_text: str,
    result_parts: list[str],
    part_idx: int,
    seg_idx: int,
    target_language_code: str,
    counts: dict[str, int],
    dependencies: CjkQualityGateDependencies,
) -> bool:
    candidate = safe_quality_gate_call(
        "context",
        seg_idx,
        lambda: dependencies.recover_context(
            source_seg,
            context_text,
            "cjk_gate_context",
            seg_idx + 1,
        ),
        counts,
        debug_prefix="cjk_gate",
        debug=dependencies.debug,
    )
    if not isinstance(candidate, str):
        return False

    stripped_candidate, stripped = dependencies.strip_unexpected_trailing_ellipsis(source_seg, candidate)
    if stripped:
        candidate = stripped_candidate
    if dependencies.has_unexpected_cjk(candidate, target_language_code=target_language_code):
        return False

    result_parts[part_idx] = candidate
    _increment(counts, "quality_gate_context_recovery")
    dependencies.debug(
        "cjk_gate reason=cjk_contamination "
        f"seg={seg_idx + 1} action=context_recovery"
    )
    return True


def _try_cjk_forced_recovery(
    *,
    source_seg: str,
    seg_idx: int,
    target_language_code: str,
    counts: dict[str, int],
    dependencies: CjkQualityGateDependencies,
    context_label: str,
    debug_prefix: str,
    assign: Callable[[str], Any],
    strip_ellipsis: bool,
) -> bool:
    candidate = safe_quality_gate_call(
        "forced",
        seg_idx,
        lambda: dependencies.recover_forced(source_seg, context_label, seg_idx + 1),
        counts,
        debug_prefix=debug_prefix,
        debug=dependencies.debug,
    )
    if not isinstance(candidate, str):
        return False
    if strip_ellipsis:
        stripped_candidate, stripped = dependencies.strip_unexpected_trailing_ellipsis(source_seg, candidate)
        if stripped:
            candidate = stripped_candidate
    if dependencies.has_unexpected_cjk(candidate, target_language_code=target_language_code):
        return False

    assign(candidate)
    _increment(counts, "quality_gate_forced_recovery")
    dependencies.debug(
        f"{debug_prefix} reason=cjk_contamination "
        f"seg={seg_idx + 1} action=forced_recovery"
    )
    return True
