"""Reference-heading and bibliography-number cleanup helpers."""

from __future__ import annotations

import re

from ..html_references import NOTES_AND_REFERENCES_HEADING_PATTERN, REFERENCES_HEADING_PATTERN


PAGE_ANCHOR_BRACKET_REF_NUM_STRIP_PATTERN = re.compile(
    r'^\s*(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>\s*)*'
    r'(?:'
    r'\[\s*<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\2[^>]*>\s*\d{1,4}\s*\]?\s*</a>'
    r'|'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\3[^>]*>\s*\[\s*\d{1,4}\s*\]?\s*</a>\s*\]?'
    r')\s*',
    re.IGNORECASE,
)
PAGE_ANCHOR_BRACKET_REF_INITIAL_PATTERN = re.compile(
    r'^\s*(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>\s*)*'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\2[^>]*>'
    r'\s*\[\s*\d{1,4}\s*\]\s*(?P<initial>[A-Z])\s*</a>\s*(?P<dot>\.)\s*',
    re.IGNORECASE,
)
PAGE_ANCHOR_BRACKET_REF_TRAILING_PUNCT_PATTERN = re.compile(
    r'^\s*(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>\s*)*'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\2[^>]*>'
    r'\s*\[\s*\d{1,4}\s*\]\s*(?P<trailing>[(])\s*</a>\s*',
    re.IGNORECASE,
)
VISIBLE_REF_NUM_PATTERN = re.compile(
    r'^\s*(?:<[^>]+>\s*)*'
    r'(?:'
    r'\[(?P<bracket>\d{1,4})\]'
    r'|(?P<dot>\d{1,4})\.'
    r'|(?P<glued>\d{1,4})(?=[A-Z]\.)'
    r'|(?P<gluedword>\d{1,4})(?=[A-Z][A-Za-z])'
    r'|(?P<spaced>\d{1,4})(?=\s+(?:<[^>]+>\s*)*[A-Z]\.)'
    r')\s*',
    re.IGNORECASE,
)
LINE_PREFIXED_VISIBLE_REF_NUM_PATTERN = re.compile(
    r'^\s*(?:<[^>]+>\s*)*'
    r'(?P<line>\d{1,4})\.?(?:\s*</sup>)?\s+'
    r'(?P<number>\d{1,4})\.?\s+'
    r'(?=(?:<[^>]+>\s*)*[A-Z\u00c0-\u00de])',
    re.IGNORECASE,
)
REFERENCE_LINE_PREFIX_ONLY_PATTERN = re.compile(
    r'^(?P<prefix>\s*(?:<[^>]+>\s*)*)'
    r'(?P<line>\d{3,4})\.?\s+'
    r'(?=(?:<[^>]+>\s*)*\S)',
    re.IGNORECASE,
)
LI_BLOCK_PATTERN = re.compile(r"<li\b([^>]*)>(.*?)</li>", re.IGNORECASE | re.DOTALL)


def references_heading_search(html: str, *, allow_notes_heading: bool = False) -> re.Match[str] | None:
    matches = [match for match in (REFERENCES_HEADING_PATTERN.search(html),) if match is not None]
    if allow_notes_heading:
        notes_match = NOTES_AND_REFERENCES_HEADING_PATTERN.search(html)
        if notes_match is not None:
            matches.append(notes_match)
    return min(matches, key=lambda match: match.start()) if matches else None


def references_heading_match(html: str, *, allow_notes_heading: bool = False) -> re.Match[str] | None:
    return REFERENCES_HEADING_PATTERN.match(html) or (
        NOTES_AND_REFERENCES_HEADING_PATTERN.match(html) if allow_notes_heading else None
    )


def looks_like_reference_line_number(value: int) -> bool:
    if 5 <= value <= 300 and value % 5 == 0:
        return True
    # Some OCR/Marker outputs preserve PDF line numbers before bibliography numbers.
    return 500 <= value <= 3000


def line_prefixed_reference_number_match(body: str) -> re.Match[str] | None:
    match = LINE_PREFIXED_VISIBLE_REF_NUM_PATTERN.match(body)
    if match is None:
        return None
    try:
        line_number = int(match.group("line"))
        ref_number = int(match.group("number"))
    except ValueError:
        return None
    if line_number == ref_number or not looks_like_reference_line_number(line_number):
        return None
    if ref_number <= 0 or ref_number > 999:
        return None
    return match


def reference_visible_number(body: str) -> int | None:
    line_prefixed_match = line_prefixed_reference_number_match(body)
    if line_prefixed_match is not None:
        return int(line_prefixed_match.group("number"))

    match = VISIBLE_REF_NUM_PATTERN.match(body)
    if match is None:
        return None
    value = (
        match.group("bracket")
        or match.group("dot")
        or match.group("glued")
        or match.group("gluedword")
        or match.group("spaced")
    )
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def strip_reference_visible_number(body: str) -> str:
    line_prefixed_match = line_prefixed_reference_number_match(body)
    if line_prefixed_match is not None:
        return body[: line_prefixed_match.start()] + body[line_prefixed_match.end() :]
    return VISIBLE_REF_NUM_PATTERN.sub("", body, count=1)


def strip_page_anchor_bracket_ref_num_prefix(body: str) -> str:
    def keep_author_initial(match: re.Match[str]) -> str:
        return f"{match.group('initial')}{match.group('dot')} "

    body = PAGE_ANCHOR_BRACKET_REF_INITIAL_PATTERN.sub(keep_author_initial, body, count=1)
    body = PAGE_ANCHOR_BRACKET_REF_TRAILING_PUNCT_PATTERN.sub(
        lambda match: match.group("trailing"),
        body,
        count=1,
    )
    return PAGE_ANCHOR_BRACKET_REF_NUM_STRIP_PATTERN.sub("", body, count=1)


def normalize_standalone_reference_paragraph_prefix(body: str, number: str) -> str:
    stripped_body = strip_page_anchor_bracket_ref_num_prefix(body)
    if stripped_body == body or 'class="z2m-ref-num"' in stripped_body:
        return stripped_body
    return f'<span class="z2m-ref-num">{number}.</span> {stripped_body.lstrip()}'


def strip_leading_reference_line_number_only(body: str) -> str:
    """Strip a standalone PDF line number at the start of a reference continuation."""

    def strip_start(match: re.Match[str]) -> str:
        try:
            line_number = int(match.group("line"))
        except ValueError:
            return match.group(0)
        if not looks_like_reference_line_number(line_number):
            return match.group(0)
        return match.group("prefix")

    return REFERENCE_LINE_PREFIX_ONLY_PATTERN.sub(strip_start, body, count=1)


def strip_leading_reference_line_number_before_expected_number(
    body: str,
    expected_number: int | None,
) -> str:
    if expected_number is None or expected_number <= 0:
        return body

    expected = str(expected_number)

    def strip_start(match: re.Match[str]) -> str:
        try:
            line_number = int(match.group("line"))
            ref_number = int(match.group("number"))
        except ValueError:
            return match.group(0)
        if ref_number != expected_number or line_number == ref_number:
            return match.group(0)
        if not (
            looks_like_reference_line_number(line_number)
            or abs(line_number - ref_number) <= 3
        ):
            return match.group(0)
        return f"{match.group('prefix')}{expected}. "

    fixed = re.sub(
        rf'^(?P<prefix>\s*(?:(?!</?sup\b)<[^>]+>\s*)*)<sup\b[^>]*>\s*'
        rf'(?P<line>\d{{1,4}})\.?\s*</sup>\s+(?P<number>{re.escape(expected)})\.?\s+'
        r'(?=(?:<[^>]+>\s*)*[A-Z])',
        strip_start,
        body,
        count=1,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        rf'^(?P<prefix>\s*(?:<[^>]+>\s*)*)(?P<line>\d{{1,4}})\.?\s+'
        rf'(?P<number>{re.escape(expected)})\.?\s+'
        r'(?=(?:<[^>]+>\s*)*[A-Z])',
        strip_start,
        fixed,
        count=1,
        flags=re.IGNORECASE,
    )
    return fixed


def strip_leading_reference_line_number_pair(body: str) -> str:
    """Strip visible PDF line/page numbers before a bibliography item number."""

    def strip_start(match: re.Match[str]) -> str:
        try:
            line_number = int(match.group("line"))
            ref_number = int(match.group("number"))
        except ValueError:
            return match.group(0)
        if line_number == ref_number:
            return match.group(0)
        if not (
            looks_like_reference_line_number(line_number)
            or abs(line_number - ref_number) <= 3
        ):
            return match.group(0)
        return f"{match.group('prefix')}{ref_number}. "

    return re.sub(
        r'^(?P<prefix>\s*(?:(?!</?(?:li|ul|ol)\b)<[^>]+>\s*)*)'
        r'(?P<line>\d{1,4})\.?\s+'
        r'(?P<number>\d{1,3})\.?\s+'
        r'(?=(?:<[^>]+>\s*)*[A-Z\u00c0-\u00de])',
        strip_start,
        body,
        count=1,
        flags=re.IGNORECASE,
    )


def strip_leading_reference_line_number_pairs_in_list_items(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        body = match.group(2) or ""
        fixed_body = strip_leading_reference_line_number_pair(body)
        if fixed_body == body:
            return match.group(0)
        return f"<li{attrs}>{fixed_body}</li>"

    return LI_BLOCK_PATTERN.sub(replace, html)


def strip_duplicate_reference_number_artifacts(body: str, number: str) -> str:
    fixed = re.sub(
        rf'^(?P<prefix>\s*(?:<[^>]+>\s*)*){re.escape(number)}\.\s+'
        rf'{re.escape(number)}(?=(?:<[^>]+>\s*)*[A-Z][A-Za-z])',
        rf"\g<prefix>{number}. ",
        body,
        count=1,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        rf'(?P<prefix><span\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bz2m-ref-num\b)'
        rf'[^>]*>\s*{re.escape(number)}\.\s*</span>\s*)'
        rf'{re.escape(number)}(?=(?:<[^>]+>\s*)*[A-Z][A-Za-z])',
        r"\g<prefix>",
        fixed,
        count=1,
        flags=re.IGNORECASE,
    )
    return re.sub(
        rf'^(?P<prefix>\s*(?:<[^>]+>\s*)*){re.escape(number)}'
        r'(?=(?:<[^>]+>\s*)*[A-Z][A-Za-z])',
        r"\g<prefix>",
        fixed,
        count=1,
        flags=re.IGNORECASE,
    )


def strip_embedded_reference_number_artifacts(body: str) -> str:
    return re.sub(
        r'(?<=[A-Za-z])\s+\d{1,3}\.\s+'
        r'(?=(?:of|for|in|on|with|and|the|a|an|to)\b)',
        " ",
        body,
        count=1,
        flags=re.IGNORECASE,
    )
