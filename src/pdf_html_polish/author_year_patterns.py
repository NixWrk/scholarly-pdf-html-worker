from __future__ import annotations

import re


AUTHOR_NAME_TOKEN = (
    r"[A-Z\u00c0-\u00de\u0410-\u042f\u0401]"
    r"[A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff\u0410-\u044f\u0401\u0451'\u2019.-]+"
)
AUTHOR_YEAR_SUFFIX_TOKEN = r"\d{4}[a-z\u0430-\u044f\u0451]?"
AUTHOR_YEAR_CITATION_PATTERN = re.compile(
    rf"(?<![\w-]){AUTHOR_NAME_TOKEN}"
    rf"(?:\s+(?:et\s+al\.?|\u0438\s+\u0434\u0440\.?|"
    rf"(?:and|\u0438)\s+{AUTHOR_NAME_TOKEN}|(?:&|&amp;)\s*{AUTHOR_NAME_TOKEN}))?"
    rf"(?:,\s*|\s+)\(?{AUTHOR_YEAR_SUFFIX_TOKEN}\)?",
    re.IGNORECASE,
)
