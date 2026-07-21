"""Shared reference-section HTML patterns."""

from __future__ import annotations

import re


REFERENCES_HEADING_PATTERN = re.compile(
    r"<h([1-6])\b[^>]*>\s*(?:<[^>]+>\s*)*"
    r"(?:(?:[IVXLCM]+|\d+)\.?\s*)?(?:<[^>]+>\s*)*"
    r"(?:"
    r"References|Referencias|Références|"
    r"Bibliography|Bibliografie|Bibliografía|Literatur|Literaturverzeichnis|"
    r"\u041b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u0430|"
    r"\u0421\u043f\u0438\u0441\u043e\u043a \u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b|"
    r"\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438|"
    r"Referenzen|"
    r"\u53c2\u8003\u6587\u732e|"
    r"\u53c2\u8003\u8d44\u6599"
    r")"
    r"\s*(?:</[^>]+>\s*)*</h\1>",
    re.IGNORECASE | re.DOTALL,
)
NOTES_AND_REFERENCES_HEADING_PATTERN = re.compile(
    r"<h([1-6])\b[^>]*>\s*(?:<[^>]+>\s*)*"
    r"(?:(?:[IVXLCM]+|\d+)\.?\s*)?(?:<[^>]+>\s*)*"
    r"Notes\s+and\s+references"
    r"\s*(?:</[^>]+>\s*)*</h\1>",
    re.IGNORECASE | re.DOTALL,
)


# Backward-compatible aliases for older internal imports.
_REFERENCES_HEADING_PATTERN = REFERENCES_HEADING_PATTERN
_NOTES_AND_REFERENCES_HEADING_PATTERN = NOTES_AND_REFERENCES_HEADING_PATTERN
