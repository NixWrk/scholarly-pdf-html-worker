from __future__ import annotations

from zoteropdf2md.translation.quality_gates import (
    EnResidualQualityGateDependencies,
    apply_en_residual_quality_gate,
    apply_en_residual_segment_quality_gate,
    build_neighbor_context,
    safe_quality_gate_call,
)


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def _segment_core_text(text: str) -> str:
    return text.strip()


def _en_deps(**overrides: object) -> EnResidualQualityGateDependencies:
    def no_short_guard(_source: str, candidate: str) -> tuple[str, str | None]:
        return candidate, None

    values = {
        "apply_short_translation_guard": no_short_guard,
        "is_identity_residual": lambda source, translated: source == translated,
        "segment_core_text": _segment_core_text,
        "normalize_ws": _normalize_ws,
        "strip_unexpected_trailing_ellipsis": lambda _source, candidate: (candidate, False),
        "recover_parts_slice": lambda source_parts, start, end, _label, _seg: source_parts[start:end + 1],
        "recover_context": lambda source, _context, _label, _seg: source,
        "recover_forced": lambda source, _label, _seg: source,
        "recover_sentencewise": lambda source, _label, _seg: source,
        "debug": lambda _message: None,
    }
    values.update(overrides)
    return EnResidualQualityGateDependencies(**values)  # type: ignore[arg-type]


def test_build_neighbor_context_prefers_group_neighbors() -> None:
    context = build_neighbor_context(
        ["Intro", "Target", "Next paragraph", "Outside paragraph"],
        1,
        segment_groups=[1, 1, 1, 2],
        grouped_indices={1: [0, 1, 2], 2: [3]},
        segment_core_text=_segment_core_text,
        normalize_ws=_normalize_ws,
    )

    assert context == "Context (for consistency only): Intro Next paragraph"


def test_build_neighbor_context_falls_back_to_adjacent_segments() -> None:
    context = build_neighbor_context(
        ["Before", "Target", "After"],
        1,
        segment_core_text=_segment_core_text,
        normalize_ws=_normalize_ws,
        dedupe=False,
    )

    assert context == "Context (for consistency only): Before After"


def test_safe_quality_gate_call_records_errors_and_debug_message() -> None:
    counts: dict[str, int] = {}
    messages: list[str] = []

    def fail() -> object:
        raise RuntimeError("boom")

    result = safe_quality_gate_call(
        "context",
        2,
        fail,
        counts,
        debug_prefix="quality_gate",
        debug=messages.append,
    )

    assert result is None
    assert counts == {
        "quality_gate_recovery_error": 1,
        "quality_gate_context_error": 1,
    }
    assert messages == ["quality_gate reason=recovery_error seg=3 action=context error=RuntimeError"]


def test_apply_en_residual_quality_gate_recovers_paragraph_slice() -> None:
    messages: list[str] = []
    deps = _en_deps(
        recover_parts_slice=lambda _source_parts, _start, _end, _label, _seg: [
            "<p>",
            "Translated sentence.",
            "</p>",
        ],
        debug=messages.append,
    )

    result, counts = apply_en_residual_quality_gate(
        source_parts=["<p>", "English sentence.", "</p>"],
        translated_parts=["<p>", "English sentence.", "</p>"],
        translatable_indices=[1],
        source_segments=["English sentence."],
        paragraph_groups=[7],
        paragraph_part_ranges={7: (0, 2)},
        max_chunk_chars=1000,
        max_segments=3,
        dependencies=deps,
    )

    assert result == ["<p>", "Translated sentence.", "</p>"]
    assert counts == {
        "quality_gate_attempted": 1,
        "quality_gate_paragraph_recovery": 1,
    }
    assert messages == ["quality_gate reason=en_residual seg=1 action=paragraph_recovery"]


def test_apply_en_residual_segment_quality_gate_falls_back_to_forced() -> None:
    messages: list[str] = []
    deps = _en_deps(
        recover_context=lambda source, _context, _label, _seg: source,
        recover_forced=lambda _source, _label, _seg: "Translated sentence.",
        debug=messages.append,
    )

    result, counts = apply_en_residual_segment_quality_gate(
        source_segments=["Before.", "English sentence.", "After."],
        translated_segments=["Before translated.", "English sentence.", "After translated."],
        max_segments=3,
        dependencies=deps,
    )

    assert result == ["Before translated.", "Translated sentence.", "After translated."]
    assert counts == {
        "quality_gate_attempted": 1,
        "quality_gate_forced_recovery": 1,
    }
    assert messages == ["quality_gate_fallback reason=en_residual seg=2 action=forced_recovery"]


def test_apply_en_residual_segment_quality_gate_counts_short_guard_rejection() -> None:
    def short_guard(source: str, candidate: str) -> tuple[str, str | None]:
        if candidate == "x":
            return source, "too_short"
        return candidate, None

    deps = _en_deps(
        apply_short_translation_guard=short_guard,
        recover_forced=lambda _source, _label, _seg: "x",
        recover_sentencewise=lambda _source, _label, _seg: "Recovered sentence.",
    )

    result, counts = apply_en_residual_segment_quality_gate(
        source_segments=["English sentence."],
        translated_segments=["English sentence."],
        max_segments=3,
        dependencies=deps,
    )

    assert result == ["Recovered sentence."]
    assert counts == {
        "quality_gate_attempted": 1,
        "quality_gate_short_guard_rejected": 1,
        "quality_gate_short_guard_too_short": 1,
        "quality_gate_sentence_recovery": 1,
    }
