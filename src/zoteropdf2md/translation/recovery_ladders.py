"""Recovery ladder algorithms for HTML translation segments."""

from __future__ import annotations

from collections.abc import Callable
import re


TARGET_MARKER_START = "zz2mtargetstartzz"
TARGET_MARKER_END = "zz2mtargetendzz"
FORCED_MARKER_START = "zz2mforcestartzz"
FORCED_MARKER_END = "zz2mforceendzz"


def marker_payload(text: str, marker_start: str, marker_end: str) -> str:
    match = re.search(
        rf"{re.escape(marker_start)}(.*?){re.escape(marker_end)}",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match is None:
        return ""
    return match.group(1).strip()


def recover_segment_with_context_markers(
    source_seg: str,
    *,
    context_text: str,
    recover_single_segment: Callable[[str], str],
) -> str:
    if not context_text:
        return recover_single_segment(source_seg)

    wrapped = f"{TARGET_MARKER_START}{source_seg}{TARGET_MARKER_END}\n{context_text}"
    recovered = recover_single_segment(wrapped)
    candidate = marker_payload(recovered, TARGET_MARKER_START, TARGET_MARKER_END)
    if candidate:
        return candidate
    return recover_single_segment(source_seg)


def recover_segment_with_forced_markers(
    source_seg: str,
    *,
    forced_instruction: str,
    recover_single_segment: Callable[[str], str],
) -> str:
    wrapped = f"{forced_instruction}{FORCED_MARKER_START}{source_seg}{FORCED_MARKER_END}"
    recovered = recover_single_segment(wrapped)
    candidate = marker_payload(recovered, FORCED_MARKER_START, FORCED_MARKER_END)
    if candidate:
        return candidate
    return recover_single_segment(source_seg)


def recover_segment_sentencewise(
    source_seg: str,
    *,
    split_outer_ws: Callable[[str], tuple[str, str, str]],
    normalize_ws: Callable[[str], str],
    segment_core_text: Callable[[str], str],
    is_identity_residual: Callable[[str, str], bool],
    recover_single_segment: Callable[[str], str],
    recover_forced_segment: Callable[[str], str],
) -> str:
    lead, core, tail = split_outer_ws(source_seg)
    core_text = core.strip()
    if not core_text:
        return source_seg
    sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", core_text) if chunk.strip()]
    if len(sentences) < 2:
        return source_seg

    translated_sentences: list[str] = []
    for sent in sentences:
        try:
            translated = recover_single_segment(sent)
        except Exception:
            translated = sent
        if is_identity_residual(sent, translated):
            try:
                translated = recover_forced_segment(sent)
            except Exception:
                pass
        translated_sentences.append(normalize_ws(segment_core_text(translated)))

    joined = " ".join(chunk for chunk in translated_sentences if chunk).strip()
    if not joined:
        return source_seg
    return f"{lead}{joined}{tail}"
