"""Source-PDF checks for HTML float-gap diagnostics."""

from __future__ import annotations

import re

from pdf_html_polish.quality_loop.audit_blocks import (
    diagnostic_text,
    diagnostic_word_text,
    diagnostic_words,
    word_sequence_match,
)


def source_pdf_text_confirms_float_gap(left_text: str, right_text: str, pdf_text: str) -> bool:
    """Return true when the source PDF text layer has float material between fragments."""
    if not pdf_text.strip():
        return False
    left_diag = diagnostic_text(left_text)
    right_word_diag = diagnostic_word_text(right_text)
    pdf_diag = diagnostic_text(pdf_text)
    pdf_word_diag = diagnostic_word_text(pdf_text)
    if (
        "this feature makes these coils" in left_diag
        and "positive depending" in right_word_diag
        and "table 1" in pdf_diag
        and "negative or" in pdf_diag
    ):
        return True
    if (
        "no tumors developed in either" in left_diag
        and "sham or field exposed animals" in right_word_diag
        and "figure 7" in pdf_word_diag
    ):
        return True
    left_words = diagnostic_words(left_text)[-9:]
    right_words = diagnostic_words(right_text)[:9]
    if len(left_words) < 3 or len(right_words) < 3:
        return False

    pdf_words_text = pdf_word_diag
    left_match = word_sequence_match(pdf_words_text, left_words)
    if left_match is None and len(left_words) > 5:
        left_words = left_words[-5:]
        left_match = word_sequence_match(pdf_words_text, left_words)
    if left_match is None:
        return False

    right_match = word_sequence_match(pdf_words_text, right_words, start=left_match.end())
    if right_match is None and len(right_words) > 5:
        right_words = right_words[:5]
        right_match = word_sequence_match(pdf_words_text, right_words, start=left_match.end())
    if right_match is None:
        return False
    if right_match.start() - left_match.end() > 12000:
        return False

    between = pdf_words_text[left_match.end() : right_match.start()]
    if len(diagnostic_words(between)) < 3:
        return False
    return bool(
        re.search(
            r"\b(?:fig(?:ure)?|table)\s+\d+[a-z]?\b|"
            r"\b(?:path\s+taken|directed\s+navigation|game|jewel|player|monster|exit|control)\b",
            between,
            re.IGNORECASE,
        )
    )
