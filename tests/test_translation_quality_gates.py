from __future__ import annotations

from zoteropdf2md.translation.quality_gates import build_neighbor_context, safe_quality_gate_call


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def _segment_core_text(text: str) -> str:
    return text.strip()


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
