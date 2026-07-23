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
SPLIT_EMAIL_LOCAL_DOT_PATTERN = re.compile(
    r"\b(?P<left>[A-Za-z][A-Za-z0-9._%+-]{1,})\.\s+"
    r"(?P<right>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)
SPLIT_EMAIL_SENTENCE_BOUNDARY_WORDS = {
    "addressed",
    "author",
    "authors",
    "contact",
    "correspondence",
    "email",
}


def repair_split_visible_emails(text: str) -> str:
    repaired = SPLIT_EMAIL_LABELED_LOCAL_DOT_PATTERN.sub(
        r"\g<label>\g<left>.\g<right>",
        text,
    )

    def repair_named_local_dot(match: re.Match[str]) -> str:
        left = match.group("left")
        if left.casefold() in SPLIT_EMAIL_SENTENCE_BOUNDARY_WORDS:
            return match.group(0)
        right = match.group("right")
        right_local = right.split("@", 1)[0]
        prefix = match.string[max(0, match.start() - 240) : match.start()]
        labeled = re.search(
            r"(?:e-?mail|email\s+address|correspondence(?:\s+to)?|contact)\s*:\s*$",
            prefix,
            re.IGNORECASE,
        )
        named = re.search(
            rf"\b{re.escape(left)}\s+{re.escape(right_local)}\b",
            prefix,
            re.IGNORECASE,
        )
        if labeled is None and named is None:
            return match.group(0)
        return f"{left}.{right}"

    repaired = SPLIT_EMAIL_LOCAL_DOT_PATTERN.sub(repair_named_local_dot, repaired)
    repaired = SPLIT_EMAIL_AFTER_AT_PATTERN.sub(r"\g<local>@\g<domain>", repaired)
    return SPLIT_EMAIL_DOMAIN_DOT_PATTERN.sub(r"\g<local>.\g<tld>", repaired)
