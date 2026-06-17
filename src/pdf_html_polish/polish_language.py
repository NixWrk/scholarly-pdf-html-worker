from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Pattern

from .language_detect import (
    LanguageDetection,
    LanguageGateDecision,
    detect_language_from_html,
    language_gate_decision,
    normalize_language_code,
)


@dataclass(frozen=True)
class PolishLanguagePolicy:
    code: str
    page_reference_label_pattern: Pattern[str] | None = None
    page_reference_left_context_pattern: Pattern[str] | None = None
    semantic_reference_lead_in_pattern: Pattern[str] | None = None

    def looks_like_page_reference(self, label: str, *, left_text: str = "") -> bool:
        if self.page_reference_label_pattern is not None and self.page_reference_label_pattern.fullmatch(label):
            return True
        return (
            self.page_reference_left_context_pattern is not None
            and re.fullmatch(r"\s*\d{1,4}[\)\]\.,;:]*\s*", label) is not None
            and self.page_reference_left_context_pattern.search(left_text) is not None
        )

    def strip_semantic_reference_lead_in(self, label: str) -> str:
        if self.semantic_reference_lead_in_pattern is None:
            return label
        return self.semantic_reference_lead_in_pattern.sub(r"\1", label, count=1)


@dataclass(frozen=True)
class DocumentPolishLanguageDecision:
    requested_polish_language: str
    selected_polish_language: str
    target_language: str
    detection: LanguageDetection
    gate_decision: LanguageGateDecision
    should_skip: bool = False
    skip_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_polish_language": self.requested_polish_language,
            "selected_polish_language": self.selected_polish_language,
            "target_language": self.target_language,
            "language_gate_reason": self.gate_decision.reason,
            "language_skipped": self.should_skip,
            "skip_reason": self.skip_reason,
            "language_detection": self.detection.to_dict(),
        }

    def to_flat_report_fields(self) -> dict[str, object]:
        detection = self.detection
        return {
            "requested_polish_language": self.requested_polish_language,
            "polish_language": self.selected_polish_language,
            "target_language": self.target_language,
            "detected_language": detection.detected_language,
            "language_confidence": detection.confidence,
            "language_reason": detection.reason,
            "language_gate_reason": self.gate_decision.reason,
            "language_skipped": self.should_skip,
            "skip_reason": self.skip_reason,
        }


EN_POLISH_POLICY = PolishLanguagePolicy(code="en")

RU_POLISH_POLICY = PolishLanguagePolicy(
    code="ru",
    page_reference_label_pattern=re.compile(
        r"^\s*(?:см\.?\s*)?(?:с|стр)\.?\s*\d{1,4}(?:\s*[-\u2010-\u2015]\s*\d{1,4})?[\)\]\.,;:]*\s*$",
        re.IGNORECASE,
    ),
    page_reference_left_context_pattern=re.compile(r"(?:см\.?\s*)?(?:с|стр)\.?\s*$", re.IGNORECASE),
    semantic_reference_lead_in_pattern=re.compile(r"^(\s*[\(\[]?\s*)(?:см\.?\s*)+", re.IGNORECASE),
)


def resolve_polish_language_policy(
    polish_language: str | None = None,
    *,
    table_caption_language: str | None = None,
) -> PolishLanguagePolicy:
    language = (polish_language or table_caption_language or "en").strip().casefold()
    if language.startswith("ru"):
        return RU_POLISH_POLICY
    return EN_POLISH_POLICY


def _normalize_requested_polish_language(
    polish_language: str | None = None,
    *,
    table_caption_language: str | None = None,
) -> str:
    language = (polish_language or table_caption_language or "en").strip().casefold()
    if language == "auto":
        return "auto"
    if normalize_language_code(language).startswith("ru"):
        return "ru"
    return "en"


def _select_polish_language_for_detection(
    detection: LanguageDetection,
    requested_polish_language: str,
    *,
    min_confidence: float = 0.75,
) -> str:
    if requested_polish_language != "auto":
        return requested_polish_language
    detected = normalize_language_code(detection.detected_language)
    if detected == "ru" and detection.confidence >= min_confidence:
        return "ru"
    return "en"


def resolve_document_polish_language(
    html: str,
    *,
    polish_language: str | None = None,
    table_caption_language: str | None = None,
    target_language: str = "en",
    skip_non_target_language: bool = False,
    skip_unknown_language: bool = False,
    min_confidence: float = 0.75,
) -> DocumentPolishLanguageDecision:
    """Choose the language-specific polish policy for one raw HTML document."""

    detection = detect_language_from_html(html)
    requested = _normalize_requested_polish_language(
        polish_language,
        table_caption_language=table_caption_language,
    )
    selected = _select_polish_language_for_detection(
        detection,
        requested,
        min_confidence=min_confidence,
    )
    gate = language_gate_decision(
        detection,
        target_language=target_language,
        min_confidence=min_confidence,
        skip_unknown=skip_unknown_language,
    )

    detected = normalize_language_code(detection.detected_language)
    should_skip = False
    if skip_non_target_language:
        should_skip = gate.should_skip
    elif skip_unknown_language and detected == "unknown":
        should_skip = gate.should_skip

    return DocumentPolishLanguageDecision(
        requested_polish_language=requested,
        selected_polish_language=selected,
        target_language=normalize_language_code(target_language) or "en",
        detection=detection,
        gate_decision=gate,
        should_skip=should_skip,
        skip_reason=gate.reason if should_skip else "",
    )
