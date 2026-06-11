from __future__ import annotations

from zoteropdf2md.translation.recovery_ladders import (
    FORCED_MARKER_END,
    FORCED_MARKER_START,
    TARGET_MARKER_END,
    TARGET_MARKER_START,
    recover_segment_sentencewise,
    recover_segment_with_context_markers,
    recover_segment_with_forced_markers,
)


def _split_outer_ws(text: str) -> tuple[str, str, str]:
    lead_len = len(text) - len(text.lstrip())
    tail_len = len(text) - len(text.rstrip())
    lead = text[:lead_len]
    tail = text[len(text) - tail_len:] if tail_len else ""
    core = text[lead_len:len(text) - tail_len if tail_len else len(text)]
    return lead, core, tail


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def test_recover_segment_with_context_markers_extracts_marked_payload() -> None:
    calls: list[str] = []

    def recover(segment: str) -> str:
        calls.append(segment)
        return f"{TARGET_MARKER_START}перевод{TARGET_MARKER_END}\ncontext"

    result = recover_segment_with_context_markers(
        "source",
        context_text="neighbor context",
        recover_single_segment=recover,
    )

    assert result == "перевод"
    assert calls == [f"{TARGET_MARKER_START}source{TARGET_MARKER_END}\nneighbor context"]


def test_recover_segment_with_context_markers_falls_back_when_marker_is_missing() -> None:
    calls: list[str] = []

    def recover(segment: str) -> str:
        calls.append(segment)
        return "fallback translation" if segment == "source" else "no marker"

    result = recover_segment_with_context_markers(
        "source",
        context_text="neighbor context",
        recover_single_segment=recover,
    )

    assert result == "fallback translation"
    assert calls == [f"{TARGET_MARKER_START}source{TARGET_MARKER_END}\nneighbor context", "source"]


def test_recover_segment_with_forced_markers_uses_instruction_and_extracts_payload() -> None:
    calls: list[str] = []

    def recover(segment: str) -> str:
        calls.append(segment)
        return f"{FORCED_MARKER_START}forced translation{FORCED_MARKER_END}"

    result = recover_segment_with_forced_markers(
        "source",
        forced_instruction="Translate only:\n",
        recover_single_segment=recover,
    )

    assert result == "forced translation"
    assert calls == [f"Translate only:\n{FORCED_MARKER_START}source{FORCED_MARKER_END}"]


def test_recover_segment_sentencewise_forces_identity_residual_sentence() -> None:
    def recover_single(segment: str) -> str:
        return segment if segment == "Second sentence." else f"RU {segment}"

    def recover_forced(segment: str) -> str:
        return f"FORCED {segment}"

    result = recover_segment_sentencewise(
        "  First sentence. Second sentence.  ",
        split_outer_ws=_split_outer_ws,
        normalize_ws=_normalize_ws,
        segment_core_text=lambda text: text,
        is_identity_residual=lambda source, translated: source == translated,
        recover_single_segment=recover_single,
        recover_forced_segment=recover_forced,
    )

    assert result == "  RU First sentence. FORCED Second sentence.  "
