from __future__ import annotations

import re


# Matches a phrase of 3-8 words repeated 3+ times back-to-back.
REPEATED_PHRASE_PATTERN = re.compile(
    r"\b((?:\w+\s+){2,7}\w+)(?:\s+\1){2,}",
    re.IGNORECASE,
)


def drop_repeated_phrases(text: str) -> str:
    """Collapse repeated phrase runs while leaving normal prose untouched."""
    prev = None
    result = text
    while result != prev:
        prev = result
        result = REPEATED_PHRASE_PATTERN.sub(r"\1", result)
    return result
