from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Pattern


@dataclass(frozen=True)
class PolishLanguagePolicy:
    code: str
    page_reference_label_pattern: Pattern[str] | None = None
    page_reference_left_context_pattern: Pattern[str] | None = None

    def looks_like_page_reference(self, label: str, *, left_text: str = "") -> bool:
        if self.page_reference_label_pattern is not None and self.page_reference_label_pattern.fullmatch(label):
            return True
        return (
            self.page_reference_left_context_pattern is not None
            and re.fullmatch(r"\s*\d{1,4}[\)\]\.,;:]*\s*", label) is not None
            and self.page_reference_left_context_pattern.search(left_text) is not None
        )


EN_POLISH_POLICY = PolishLanguagePolicy(code="en")

RU_POLISH_POLICY = PolishLanguagePolicy(
    code="ru",
    page_reference_label_pattern=re.compile(
        r"^\s*(?:см\.?\s*)?(?:с|стр)\.?\s*\d{1,4}(?:\s*[-\u2010-\u2015]\s*\d{1,4})?[\)\]\.,;:]*\s*$",
        re.IGNORECASE,
    ),
    page_reference_left_context_pattern=re.compile(r"(?:см\.?\s*)?(?:с|стр)\.?\s*$", re.IGNORECASE),
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
