from __future__ import annotations

import re


BROKEN_PLAIN_URL_PROTOCOL_PATTERN = re.compile(r"\b(https?://)\s+", re.IGNORECASE)
BROKEN_PLAIN_URL_SPACED_PROTOCOL_PATTERN = re.compile(r"\b(https?):\s+//\s*", re.IGNORECASE)
BROKEN_PLAIN_URL_DUPLICATE_PROTOCOL_PATTERN = re.compile(
    r"\bhttps?://\s*(?=https?://)",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_KNOWN_LINEBREAK_DOMAIN_PATTERN = re.compile(
    r"\bcreativecom-\s*mons\.org\b",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_SCHEME_PATTERN = re.compile(r"\b(?:hps|htps|ttps)://", re.IGNORECASE)
BROKEN_PLAIN_URL_PATH_SPACE_PATTERN = re.compile(
    r"(?P<prefix>\bhttps?://[A-Za-z0-9._~:/?#\[\]{}@!$&'()*+,;=%-]*/)\s+"
    r"(?=[A-Za-z0-9._~:/?#\[\]{}@!$&'*+,;=%-])",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_CONTINUATION_SPACE_PATTERN = re.compile(
    r"(?P<prefix>\bhttps?://[A-Za-z0-9._~:/?#\[\]{}@!$&'()*+,;=%-]*[/_-])\s+"
    r"(?=[A-Za-z0-9._~:/?#\[\]{}@!$&'*+,;=%-])",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_SPACE_BEFORE_SLASH_PATTERN = re.compile(
    r"(?P<prefix>\bhttps?://[A-Za-z0-9._~:/?#\[\]{}@!$&'()*+,;=%-]+)\s+"
    r"(?=/[A-Za-z0-9._~:/?#\[\]{}@!$&'*+,;=%-])",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_DOT_BEFORE_SPACE_PATTERN = re.compile(
    r"(?P<prefix>\b(?:(?:https?://)?www|https?://[A-Za-z0-9-]+)(?:\.[A-Za-z0-9-]+)*)"
    r"\s+\.\s+(?=[A-Za-z0-9-]+(?:[./]|$))",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_DOT_AFTER_SPACE_PATTERN = re.compile(
    r"(?P<prefix>\b(?:(?:https?://)?www|https?://[A-Za-z0-9-]+)(?:\.[A-Za-z0-9-]+)*\.)"
    r"\s+(?=[A-Za-z0-9-]+(?:\s+[A-Za-z0-9-]+)?\.)",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_DOMAIN_LABEL_SPACE_PATTERN = re.compile(
    r"(?P<prefix>\b(?:(?:https?://)?www\.|https?://[A-Za-z0-9-]+\.)(?:[A-Za-z0-9-]+\.)*[A-Za-z0-9-]+)"
    r"\s+(?P<tail>[A-Za-z0-9-]{1,40})(?=\.)",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_DOMAIN_WORD_SPACE_PATTERN = re.compile(
    r"(?P<prefix>\bhttps?://[A-Za-z0-9-]{3,})\s+"
    r"(?P<tail>[A-Za-z0-9-]+\.[A-Za-z]{2,})(?=[/:?#)]|/|$)",
    re.IGNORECASE,
)
BROKEN_PLAIN_URL_TLD_SPACE_PATTERN = re.compile(
    r"(?P<prefix>\bhttps?://(?:[A-Za-z0-9-]+\.)+[A-Za-z0-9-]+\.)\s+"
    r"(?P<tail>[A-Za-z]{2,63})(?=[/:?#)\s]|$)",
    re.IGNORECASE,
)


def split_url_and_trailing_punct(url: str) -> tuple[str, str]:
    core = url
    trailing = ""

    while core and core[-1] in ".,;:!?":
        trailing = core[-1] + trailing
        core = core[:-1]

    while core.endswith(")") and core.count("(") < core.count(")"):
        trailing = ")" + trailing
        core = core[:-1]

    while core.endswith("]") and core.count("[") < core.count("]"):
        trailing = "]" + trailing
        core = core[:-1]

    return core, trailing


def repair_broken_visible_url_text(text: str) -> str:
    fixed = BROKEN_PLAIN_URL_SCHEME_PATTERN.sub("https://", text)
    fixed = BROKEN_PLAIN_URL_SPACED_PROTOCOL_PATTERN.sub(r"\1://", fixed)
    fixed = BROKEN_PLAIN_URL_DUPLICATE_PROTOCOL_PATTERN.sub("", fixed)
    fixed = BROKEN_PLAIN_URL_PROTOCOL_PATTERN.sub(r"\1", fixed)
    fixed = BROKEN_PLAIN_URL_KNOWN_LINEBREAK_DOMAIN_PATTERN.sub("creativecommons.org", fixed)
    fixed = re.sub(r"\b(?P<label>\d{1,3})(?=www\.)", r"\g<label> ", fixed)
    fixed = re.sub(r"\b10\s+\.\s*(?=\d{4,9}/)", "10.", fixed)
    fixed = re.sub(r"\b10\.\s+(?=\d{4,9}/)", "10.", fixed)
    fixed = re.sub(
        r"(?P<head>\b(?:(?:doi|DOI)\s*:\s*|(?:Digital\s+Object\s+Identifier|DOI)\s+)?"
        r"10\.\d{4,9}/)\s+(?=[A-Za-z0-9])",
        r"\g<head>",
        fixed,
        flags=re.IGNORECASE,
    )
    previous = None
    while previous != fixed:
        previous = fixed
        fixed = re.sub(
            r"(?P<head>\b10\.\d{4,9}/[A-Za-z]{1,3})\s+"
            r"(?P<tail>[A-Za-z][A-Za-z0-9._-]*\d[A-Za-z0-9._-]*)",
            r"\g<head>\g<tail>",
            fixed,
        )
        fixed = BROKEN_PLAIN_URL_DOT_BEFORE_SPACE_PATTERN.sub(r"\g<prefix>.", fixed)
        fixed = BROKEN_PLAIN_URL_DOT_AFTER_SPACE_PATTERN.sub(r"\g<prefix>", fixed)
        fixed = BROKEN_PLAIN_URL_DOMAIN_WORD_SPACE_PATTERN.sub(r"\g<prefix>\g<tail>", fixed)
        fixed = BROKEN_PLAIN_URL_DOMAIN_LABEL_SPACE_PATTERN.sub(r"\g<prefix>\g<tail>", fixed)
        fixed = BROKEN_PLAIN_URL_TLD_SPACE_PATTERN.sub(r"\g<prefix>\g<tail>", fixed)
        fixed = BROKEN_PLAIN_URL_SPACE_BEFORE_SLASH_PATTERN.sub(r"\g<prefix>", fixed)
        fixed = BROKEN_PLAIN_URL_PATH_SPACE_PATTERN.sub(r"\g<prefix>", fixed)
        fixed = BROKEN_PLAIN_URL_CONTINUATION_SPACE_PATTERN.sub(r"\g<prefix>", fixed)
    fixed = re.sub(
        r"\b(?P<ext>png|jpe?g|gif|svg|webp|pdf)(?P=ext)\b",
        r"\g<ext>",
        fixed,
        flags=re.IGNORECASE,
    )
    return fixed
