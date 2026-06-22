"""Reference-heading and bibliography-number cleanup helpers."""

from __future__ import annotations

import re
from typing import Any

from ..html_references import NOTES_AND_REFERENCES_HEADING_PATTERN, REFERENCES_HEADING_PATTERN
from .html_fragments import visible_text


LI_ID_PATTERN = re.compile(r'\bid\s*=\s*(["\'])ref-(\d+)["\']', re.IGNORECASE)
LI_BLOCK_PATTERN = re.compile(r"<li\b([^>]*)>(.*?)</li>", re.IGNORECASE | re.DOTALL)
REFERENCE_PAGE_ID_PATTERN = re.compile(r'\bid\s*=\s*(["\'])(page-[^"\']+)\1', re.IGNORECASE)
PAGE_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
SEMANTIC_INTERNAL_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])#'
    r'(?P<target>(?:table|page)-[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
REF_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#ref-(?P<num>\d+)["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
P_BLOCK_PATTERN = re.compile(
    r'(?P<open><p\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></p>)',
    re.IGNORECASE,
)
REFERENCE_LEADING_PAGE_NUM_ANCHOR_PATTERN = re.compile(
    r'(?P<open><li\b[^>]*\bid\s*=\s*(["\'])ref-(?P<num>\d+)\2[^>]*>\s*'
    r'(?:(?:<(?:b|strong|i|em)\b[^>]*>\s*)*)?)'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\4[^>]*>'
    r'(?P<body>\s*(?:<span\b[^>]*\bz2m-ref-num\b[^>]*>\s*)?\d{1,4}\.?\s*(?:</span>)?\s*)'
    r'</a>',
    re.IGNORECASE,
)
REFERENCE_DUPLICATE_PAGE_NUM_ANCHOR_PATTERN = re.compile(
    r'(?P<open><li\b[^>]*\bid\s*=\s*(["\'])ref-(?P<num>\d+)\2[^>]*>\s*'
    r'<span\b[^>]*\bz2m-ref-num\b[^>]*>\s*\d{1,4}\.?\s*</span>\s*)'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\4[^>]*>'
    r'(?P<body>\s*\d{1,4}\.?\s*)'
    r'</a>\s*',
    re.IGNORECASE,
)
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
    r'^\s*(?:(?!</?sup\b)<[^>]+>\s*)*'
    r'(?:'
    r'<sup\b[^>]*>\s*(?P<sup>\d{1,4})\s*</sup>'
    r'|\[(?P<bracket>\d{1,4})\]'
    r'|(?P<dot>\d{1,4})\.'
    r'|(?P<glued>\d{1,4})(?=[A-Z]\.)'
    r'|(?P<gluedword>\d{1,4})(?=[A-Z][A-Za-z])'
    r'|(?P<spaced>\d{1,4})(?=\s+(?:<[^>]+>\s*)*[A-Z]\.)'
    r'|(?P<spacedword>\d{1,4})(?=\s+(?:<[^>]+>\s*)*[A-Z][A-Za-z])'
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
        match.group("sup")
        or match.group("bracket")
        or match.group("dot")
        or match.group("glued")
        or match.group("gluedword")
        or match.group("spaced")
        or match.group("spacedword")
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


def unwrap_reference_list_page_number_links(html: str) -> str:
    """Remove Marker page links from leading bibliography item numbers."""
    if "#page-" not in html or "z2m-ref-num" not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        label = re.sub(r"\s+", " ", visible_text(match.group("body"))).strip()
        if label != f"{match.group('num')}." and label != match.group("num"):
            return match.group(0)
        return f"{match.group('open')}{match.group('body')}"

    repaired = REFERENCE_LEADING_PAGE_NUM_ANCHOR_PATTERN.sub(replace, html)

    def drop_duplicate(match: re.Match[str]) -> str:
        label = re.sub(r"\s+", " ", visible_text(match.group("body"))).strip()
        if label != f"{match.group('num')}." and label != match.group("num"):
            return match.group(0)
        return match.group("open")

    return REFERENCE_DUPLICATE_PAGE_NUM_ANCHOR_PATTERN.sub(drop_duplicate, repaired)


def unwrap_reference_list_page_links(html: str) -> str:
    """Remove residual PDF page links inside normalized bibliography entries."""
    if "#page-" not in html or "ref-" not in html:
        return html

    def unwrap_anchors(fragment: str) -> str:
        return PAGE_ANCHOR_PATTERN.sub(lambda match: match.group("body"), fragment)

    def replace_li(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        body = match.group(2) or ""
        if LI_ID_PATTERN.search(attrs) is None:
            return match.group(0)
        return f"<li{attrs}>{unwrap_anchors(body)}</li>"

    repaired = LI_BLOCK_PATTERN.sub(replace_li, html)

    def replace_p(match: re.Match[str]) -> str:
        open_tag = match.group("open")
        if LI_ID_PATTERN.search(open_tag) is None:
            return match.group(0)
        return f'{open_tag}{unwrap_anchors(match.group("body"))}{match.group("close")}'

    return P_BLOCK_PATTERN.sub(replace_p, repaired)


def repair_ref_links_with_leading_closing_punctuation(html: str) -> str:
    """Move a leading closing parenthesis/bracket back outside a citation link."""
    if "#ref-" not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        label_match = re.fullmatch(r"(?P<lead>[\)\]])\s*(?P<num>\d{1,3})(?P<trail>[,.;:]*)", label)
        if label_match is None or label_match.group("num") != match.group("num"):
            return match.group(0)
        return (
            f'{label_match.group("lead")}'
            f'<a{match.group("attrs")}>{label_match.group("num")}</a>'
            f'{label_match.group("trail")}'
        )

    return REF_ANCHOR_PATTERN.sub(replace, html)


def unwrap_page_reference_ref_links(html: str, language_policy: Any) -> str:
    """Remove bibliography links from explicit page references."""
    if "#ref-" not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        left_text = visible_text(html[max(0, match.start() - 48): match.start()])
        if language_policy.looks_like_page_reference(label, left_text=left_text):
            return match.group("body")
        return match.group(0)

    return REF_ANCHOR_PATTERN.sub(replace, html)


def unwrap_stale_numeric_page_links(html: str, language_policy: Any) -> str:
    """Remove leftover page anchors that wrap citation-like numeric labels."""
    if "#page-" not in html:
        return html

    numeric_label = re.compile(
        r"^\s*[\[\(]?\s*\d{1,4}"
        r"(?:\s*(?:[,;]|&|and|[-\u2010\u2011\u2012\u2013\u2014])\s*\d{1,4})*"
        r"[\]\)\.,;:]*\s*$",
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        left_text = visible_text(html[max(0, match.start() - 80): match.start()])
        if language_policy.looks_like_page_reference(label, left_text=left_text):
            return match.group(0)
        if re.search(r"\b(?:pages?|pp?\.?|sheet|slide)\s*$", left_text, re.IGNORECASE):
            return match.group(0)
        if numeric_label.fullmatch(label) is None:
            return match.group(0)
        return match.group("body")

    return PAGE_ANCHOR_PATTERN.sub(replace, html)


def unwrap_page_reference_page_links(html: str, language_policy: Any) -> str:
    """Remove page-anchor links from explicit page-reference labels."""
    if "#page-" not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        left_text = visible_text(html[max(0, match.start() - 48): match.start()])
        if language_policy.looks_like_page_reference(label, left_text=left_text):
            return match.group("body")
        return match.group(0)

    return PAGE_ANCHOR_PATTERN.sub(replace, html)


def unwrap_broken_page_anchor_links(html: str) -> str:
    """Drop #page-* links that no longer have a matching page anchor id."""
    if "#page-" not in html:
        return html
    page_ids = {match.group(2) for match in REFERENCE_PAGE_ID_PATTERN.finditer(html)}
    if not page_ids:
        return PAGE_ANCHOR_PATTERN.sub(lambda match: match.group("body"), html)

    def replace(match: re.Match[str]) -> str:
        href_match = re.search(
            r'\bhref\s*=\s*(["\'])#(?P<target>page-[^"\']+)\1',
            match.group("attrs"),
            re.IGNORECASE,
        )
        if href_match is None or href_match.group("target") in page_ids:
            return match.group(0)
        return match.group("body")

    return PAGE_ANCHOR_PATTERN.sub(replace, html)


def unwrap_broken_internal_semantic_links(html: str) -> str:
    """Drop late broken table/page links without stripping preserved citation markup."""
    if 'href="#' not in html and "href='#" not in html:
        return html
    ids = {
        match.group("id")
        for match in re.finditer(
            r'\bid\s*=\s*(["\'])(?P<id>[^"\']+)\1',
            html,
            re.IGNORECASE | re.DOTALL,
        )
    }

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        if target in ids:
            return match.group(0)
        if target.startswith("page-"):
            label = visible_text(match.group("body")).strip()
            left_text = visible_text(html[max(0, match.start() - 100) : match.start()])
            if re.fullmatch(
                r"[\[\(]?\s*(?:pages?|pp?\.?|p\.?)?\s*\d{1,4}[\)\]\.,;:]?",
                label,
                re.IGNORECASE,
            ):
                return match.group(0)
            if re.search(
                r"\b(?:fig(?:ure)?|figs?|figures?|table|СЂРёСЃСѓРЅРѕРє|С„РёРіСѓСЂР°|С‚Р°Р±Р»РёС†Р°)\s*$",
                left_text,
                re.IGNORECASE,
            ):
                if re.fullmatch(r"\d{1,4}[A-Za-zРђ-РЇР°-СЏ]?", label):
                    return match.group(0)
        return match.group("body")

    return SEMANTIC_INTERNAL_ANCHOR_PATTERN.sub(replace, html)
