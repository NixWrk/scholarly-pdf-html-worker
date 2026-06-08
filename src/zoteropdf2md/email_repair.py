from __future__ import annotations

import re


SPLIT_EMAIL_AFTER_AT_PATTERN = re.compile(
    r"(?P<local>\b[A-Za-z0-9._%+-]{2,})@\s+(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
SPLIT_EMAIL_DOMAIN_DOT_PATTERN = re.compile(
    r"(?P<local>\b[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9-]+)(?:\s*\.\s+|\s+\.\s*)"
    r"(?P<tld>(?:[A-Za-z0-9-]+\.)*[A-Za-z]{2,})\b"
)
SPLIT_EMAIL_LABELED_LOCAL_DOT_PATTERN = re.compile(
    r"(?P<label>\b(?:e-?mail|email\s+address|correspondence(?:\s+to)?|contact)\s*:\s*)"
    r"(?P<left>[A-Za-z0-9_%+-][A-Za-z0-9._%+-]{1,})\.\s+"
    r"(?P<right>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)


def repair_split_visible_emails(text: str) -> str:
    repaired = SPLIT_EMAIL_LABELED_LOCAL_DOT_PATTERN.sub(
        r"\g<label>\g<left>.\g<right>",
        text,
    )
    repaired = SPLIT_EMAIL_AFTER_AT_PATTERN.sub(r"\g<local>@\g<domain>", repaired)
    return SPLIT_EMAIL_DOMAIN_DOT_PATTERN.sub(r"\g<local>.\g<tld>", repaired)
