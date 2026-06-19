from __future__ import annotations

import re

from .html_fragments import (
    MATH_TAG_SPLIT_PATTERN,
    TAG_SPLIT_PATTERN,
    update_skip_stack_for_tags,
)


SKIP_AUTOLINK_TAGS = {"script", "style", "code", "pre", "math", "svg", "a"}
TEXT_NODE_REPAIR_SKIP_TAGS = SKIP_AUTOLINK_TAGS - {"a"}

RU_BARE_FIG_LEXEME_PATTERN = re.compile(
    r"\b(?:Фиг(?:ура)?|Рис(?:унок|уног|унк|уно)?)\b(?=\s*(?:<a\b|[SsСс]?[IVXLCM\d]))",
    re.IGNORECASE,
)
HEADING_PROTOCOL_SENTINEL_LEAK_PATTERN = re.compile(
    r"@{1,2}Z2M(?:\\?_)?HSEP@{0,2}",
    re.IGNORECASE,
)
AUX_PROTOCOL_SENTINEL_LEAK_PATTERN = re.compile(
    r"@{1,2}Z2M(?:\\?_)?[ATF]\d+(?:@{1,2}|(?:\\?_)+)?",
    re.IGNORECASE,
)
SLASH_PIPE_ARTIFACT_PATTERN = re.compile(r"\s*\\+\s*\|\s*\\+\s*")
LEADING_SPACED_BACKSLASH_PATTERN = re.compile(r"(^|\s)\\+\s+")
TRAILING_SPACED_BACKSLASH_PATTERN = re.compile(r"\s+\\+(?=\s|$)")
BACKSLASH_BEFORE_QUOTE_PATTERN = re.compile(r'\\(["\'])')
INLINE_OR_DISPLAY_TEX_PATTERN = re.compile(r"(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))")

MOJIBAKE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("\u0432\u0402\u201d", "\u2014"),
    ("\u0432\u0402\u201c", "\u2013"),
    ("\u0432\u0402\u2122", "\u2019"),
    ("\u0432\u0402\u045a", "\u201c"),
    ("\u0432\u0402\u045c", "\u201d"),
    ("\u0412\u00a9", "\u00a9"),
    ("\u0420\u0406\u0420\u201a\u0432\u0402\u045c", "\u2014"),
    ("\u0420\u0406\u0420\u201a\u0432\u0402\u045a", "\u2013"),
    ("\u0420\u0406\u0420\u201a\u0432\u0404\u045e", "\u2019"),
    ("\u0420\u0406\u0420\u201a\u0421\u0459", "\u201c"),
    ("\u0420\u0406\u0420\u201a\u0421\u045a", "\u201d"),
    ("\u0420\u2019\u0412\u00a9", "\u00a9"),
    ("\u0420\u2019\u0412\u00b0", "\u00b0"),
    ("\u0420\u2019\u0412\u00b5", "\u00b5"),
    ("\u0420\u045b\u0421\u0098", "\u03bc"),
    ("\u0420\u045b\u0412\u00a9", "\u03a9"),
    ("\u0420\u201c\u0432\u0402\u201d", "\u00d7"),
    ("\u0432\u0402\u201d", "\u2014"),
    ("\u0432\u0402\u201c", "\u2013"),
    ("\u0432\u0402\u2122", "\u2019"),
    ("\u0432\u0402\u045a", "\u201c"),
    ("\u0432\u0402\u045c", "\u201d"),
    ("\u0432\u20ac\u2019", "\u2212"),
    ("\u0412\u00b0", "\u00b0"),
    ("\u0412\u00b5", "\u00b5"),
    ("\u041e\u0458", "\u03bc"),
    ("\u041e\u00a9", "\u03a9"),
    ("\u0413\u2014", "\u00d7"),
)


def update_skip_stack(tag_fragment: str, skip_stack: list[str]) -> None:
    update_skip_stack_for_tags(tag_fragment, skip_stack, SKIP_AUTOLINK_TAGS)


def fix_common_mojibake(html: str) -> str:
    fixed = html
    replacements = sorted(MOJIBAKE_REPLACEMENTS, key=lambda pair: len(pair[0]), reverse=True)
    previous = None
    while fixed != previous:
        previous = fixed
        for bad, good in replacements:
            fixed = fixed.replace(bad, good)
    return fixed


def cleanup_marker_escape_artifacts(html: str) -> str:
    parts = MATH_TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if MATH_TAG_SPLIT_PATTERN.fullmatch(part):
            update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue

        def clean_prose(text: str) -> str:
            text = SLASH_PIPE_ARTIFACT_PATTERN.sub(" | ", text)
            text = LEADING_SPACED_BACKSLASH_PATTERN.sub(r"\1", text)
            text = TRAILING_SPACED_BACKSLASH_PATTERN.sub(" ", text)
            return BACKSLASH_BEFORE_QUOTE_PATTERN.sub(r"\1", text)

        cleaned = "".join(
            frag
            if INLINE_OR_DISPLAY_TEX_PATTERN.fullmatch(frag)
            else clean_prose(frag)
            for frag in INLINE_OR_DISPLAY_TEX_PATTERN.split(part)
            if frag
        )
        out.append(cleaned)

    normalized_html = "".join(out)
    return RU_BARE_FIG_LEXEME_PATTERN.sub("Рисунок", normalized_html)


def strip_protocol_sentinel_leaks(html: str) -> str:
    """Remove leaked internal @@Z2M_* protocol sentinels from text nodes."""
    parts = TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(clean_protocol_sentinel_text(part))

    cleaned_html = "".join(out)
    return clean_protocol_sentinel_text(cleaned_html)


def clean_protocol_sentinel_text(text: str) -> str:
    cleaned = HEADING_PROTOCOL_SENTINEL_LEAK_PATTERN.sub(" ", text)
    cleaned = AUX_PROTOCOL_SENTINEL_LEAK_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\(\s*,\s*", "(", cleaned)
    cleaned = re.sub(r"\[\s*,\s*", "[", cleaned)
    cleaned = re.sub(r",\s*,", ", ", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    cleaned = re.sub(r"\s+\]", "]", cleaned)
    cleaned = re.sub(r"(?<=\s)-(?=[A-Z]{2,6}\b)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned
