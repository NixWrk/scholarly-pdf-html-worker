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
AUTHOR_YEAR_CITATION_TEXT_PATTERN = re.compile(
    r"\b"
    r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
    r"(?:\s+(?:et\s+al\.?|and\s+[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+|&\s*[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+))?"
    r"(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
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


def replace_href_and_link_class(attrs: str, href: str, class_name: str) -> str:
    attrs = re.sub(
        r'\bhref\s*=\s*(["\'])#[^"\']+\1',
        f'href="{href}"',
        attrs,
        count=1,
        flags=re.IGNORECASE,
    )
    class_match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', attrs, re.IGNORECASE | re.DOTALL)
    if class_match is None:
        return f'{attrs} class="{class_name}"'
    classes = [
        cls
        for cls in class_match.group(2).split()
        if cls not in {"z2m-ref-link", "z2m-fig-link", "z2m-table-link", "z2m-eq-link"}
    ]
    if class_name not in classes:
        classes.append(class_name)
    return attrs[: class_match.start(2)] + " ".join(classes) + attrs[class_match.end(2) :]


def retarget_mismatched_ref_link_labels(html: str) -> str:
    """Keep visible numeric citation labels aligned with their #ref target."""
    if "#ref-" not in html:
        return html
    ref_numbers = {int(match.group(2)) for match in LI_ID_PATTERN.finditer(html)}
    if not ref_numbers:
        return html

    def is_valid_visible_ref(number: int) -> bool:
        return number in ref_numbers and not (1800 <= number <= 2099)

    def render_numeric_label(label: str) -> str | None:
        if re.search(r"[A-Za-z]", label):
            return None
        if re.fullmatch(
            r"[\s\(\[\]\),.;:\-\u2010\u2011\u2012\u2013\u2014\d]+",
            label,
        ) is None:
            return None
        numbers = [int(value) for value in re.findall(r"\d{1,4}", label)]
        if not numbers or any(not is_valid_visible_ref(number) for number in numbers):
            return None
        if any(value.startswith("0") for value in re.findall(r"\d{2,4}", label)):
            return None

        def link_number(num_match: re.Match[str]) -> str:
            number_text = num_match.group(0)
            number = int(number_text)
            return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'

        return re.sub(r"\d{1,4}", link_number, label)

    def looks_like_page_reference_label(label: str) -> bool:
        normalized = re.sub(r"\s+", " ", label).strip()
        return re.search(
            r"(?:"
            r"\b(?:see|cf)\.?\s+(?:p|pp|page|pages)\.?\s*\d|"
            r"\b(?:p|pp|page|pages)\.?\s*\d|"
            r"\u0441\u043c\.?\s*\u0441\.?\s*\d"
            r")",
            normalized,
            re.IGNORECASE,
        ) is not None

    def looks_like_author_year_context(label: str, left_text: str) -> bool:
        label_for_pattern = re.sub(r"(\d{4}[a-z]?)[\),.;:]+$", r"\1", label.strip(), flags=re.IGNORECASE)
        if AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label_for_pattern):
            return True
        if not re.fullmatch(r"\(?\d{4}[a-z]?\)?[\),.;:]*", label.strip(), re.IGNORECASE):
            return False
        if AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(f"{left_text[-180:]} {label_for_pattern}"):
            return True
        author_tail = re.compile(
            r"(?:\(|;|,|\bby\s+)?\s*"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
            r"(?:\s+[a-z])?"
            r"(?:\s+(?:et\s+al\.?|and|&)\s+"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
            r"(?:\s+[a-z])?|\s+et\s+al\.?)?"
            r"(?:,|\.)?\s*$"
        )
        return author_tail.search(left_text[-120:]) is not None

    def should_preserve_invalid_single_label(match: re.Match[str], label: str, visible_number: int) -> bool:
        left_text = visible_text(html[max(0, match.start() - 180): match.start()])
        if 1800 <= visible_number <= 2099 and looks_like_author_year_context(label, left_text):
            return True
        if looks_like_page_reference_label(label):
            return True
        if re.fullmatch(r"\s*\d{3,4}[\)\]\.,;:]*\s*", label) and re.search(
            r"[-\u2212]?\d+\.\d+\s*$",
            left_text,
        ):
            return True
        return False

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        numbers = [int(num) for num in re.findall(r"\d{1,4}", label)]
        if len(numbers) > 1:
            rendered = render_numeric_label(label)
            if rendered is not None and int(match.group("num")) not in numbers:
                return rendered
            return match.group(0)
        if len(numbers) != 1:
            return match.group(0)
        visible_number = numbers[0]
        if visible_number == int(match.group("num")):
            return match.group(0)
        if not is_valid_visible_ref(visible_number):
            if should_preserve_invalid_single_label(match, label, visible_number):
                return match.group(0)
            return match.group("body")
        attrs = replace_href_and_link_class(match.group("attrs"), f"#ref-{visible_number}", "z2m-ref-link")
        return f'<a{attrs}>{match.group("body")}</a>'

    return REF_ANCHOR_PATTERN.sub(replace, html)


def repair_ref_links_absorbed_decimal_or_unit_text(html: str) -> str:
    """Move OCR-swallowed decimal/unit text back out of citation anchors."""
    if "#ref-" not in html:
        return html
    ref_numbers = {int(match.group(2)) for match in LI_ID_PATTERN.finditer(html)}
    if not ref_numbers:
        return html

    def valid_cite(
        cite_text: str,
        target_text: str,
        *,
        allow_near_target: bool = False,
        allow_wrong_target: bool = False,
    ) -> int | None:
        if not cite_text or cite_text.startswith("0"):
            return None
        try:
            cite = int(cite_text)
            target = int(target_text)
        except ValueError:
            return None
        if cite not in ref_numbers or 1800 <= cite <= 2099:
            return None
        if target == cite or (allow_near_target and abs(target - cite) <= 1) or allow_wrong_target:
            return cite
        return None

    decimal_pattern = re.compile(
        r"(?P<prefix>(?<![\w.])[-\u2212]?\d+\.\d+)\s+"
        r"(?P<sup_open><sup\b[^>]*>\s*)?"
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"\s*(?P<lead>\d)(?P<cite>\d{2,3})(?P<trail>[\)\]\.,;:]*)\s*</a>"
        r"(?P<sup_close>\s*</sup>)?",
        re.IGNORECASE | re.DOTALL,
    )
    percent_pattern = re.compile(
        r"(?P<prefix>\d)\s+"
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"\s*%(?P<cite>\d{1,3})(?P<trail>[\)\]\.,;:]*)\s*</a>",
        re.IGNORECASE | re.DOTALL,
    )
    slash_unit_pattern = re.compile(
        r"(?P<prefix>\b(?:mL|ml|L|mm|cm|m|um|nm|Вµm)\s*/)\s*"
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"\s*s(?P<cite>\d{1,3})(?P<trail>[\)\]\.,;:]*)\s*</a>",
        re.IGNORECASE | re.DOTALL,
    )

    def anchor(attrs: str, cite: int, label: str) -> str:
        fixed_attrs = replace_href_and_link_class(attrs, f"#ref-{cite}", "z2m-ref-link")
        return f"<a{fixed_attrs}>{label}</a>"

    def replace_decimal(match: re.Match[str]) -> str:
        full_text = f"{match.group('lead')}{match.group('cite')}"
        try:
            full_number = int(full_text)
            target_number = int(match.group("target"))
        except ValueError:
            full_number = -1
            target_number = -1
        if full_number in ref_numbers and abs(target_number - full_number) <= 1:
            return match.group(0)
        cite = valid_cite(match.group("cite"), match.group("target"), allow_near_target=True)
        if cite is None:
            cite = valid_cite(
                match.group("cite"),
                match.group("target"),
                allow_wrong_target=full_number not in ref_numbers,
            )
        if cite is None:
            return match.group(0)
        cite_anchor = anchor(match.group("attrs"), cite, str(cite))
        if match.group("sup_open") and match.group("sup_close"):
            cite_anchor = f"{match.group('sup_open')}{cite_anchor}{match.group('sup_close')}"
        return (
            f"{match.group('prefix')}{match.group('lead')}"
            f"{cite_anchor}{match.group('trail')}"
        )

    def replace_percent(match: re.Match[str]) -> str:
        cite = valid_cite(match.group("cite"), match.group("target"))
        if cite is None:
            return match.group(0)
        return f"{match.group('prefix')}%{anchor(match.group('attrs'), cite, str(cite))}{match.group('trail')}"

    def replace_slash_unit(match: re.Match[str]) -> str:
        cite = valid_cite(match.group("cite"), match.group("target"))
        if cite is None:
            return match.group(0)
        return f"{match.group('prefix')}s{anchor(match.group('attrs'), cite, str(cite))}{match.group('trail')}"

    repaired = decimal_pattern.sub(replace_decimal, html)
    repaired = percent_pattern.sub(replace_percent, repaired)
    return slash_unit_pattern.sub(replace_slash_unit, repaired)


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


def unwrap_plain_prose_page_links(html: str) -> str:
    """Drop page anchors that wrap ordinary prose fragments."""
    if "#page-" not in html:
        return html

    semantic_label = re.compile(
        r"^\s*(?:"
        r"(?:Fig(?:s|ure)?|Figures?|Table|Tables|Box|Section|Appendix|Eq(?:n|uation)?\.?|Equation)"
        r"\.?\s+[A-Za-z0-9IVXLCM.\-вЂ“]+|"
        r"\[\s*\d|"
        r"\(?S?\d+(?:[-вЂ“]\s*S?\d+)?\s*(?:Tables?|Figures?|Files?|Data)?\)?"
        r")",
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        if re.fullmatch(r"[A-Z]{2,6}", label.strip()) is not None:
            left_text = visible_text(html[max(0, match.start() - 48): match.start()])
            if re.search(r"\b(?:page|pp?\.?|section|chapter)\s*$", left_text, re.IGNORECASE) is None:
                return match.group("body")
        if len(re.findall(r"[A-Za-z]{2,}", label)) < 3:
            return match.group(0)
        if AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label) is not None:
            return match.group("body")
        if semantic_label.match(label):
            if re.match(r"^\s*\d+(?:\.\d+){1,}\.?\s+[A-Z]", label) and len(
                re.findall(r"[A-Za-z]{2,}", label)
            ) >= 3:
                return match.group("body")
            return match.group(0)
        if re.search(r"\b(?:copyright|creative commons|doi|https?|www\.)\b", label, re.IGNORECASE):
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


def unwrap_duplicate_see_page_anchor_tails(html: str) -> str:
    """Unwrap page-number tails when Marker split one "See page N" page anchor."""
    if "#page-" not in html:
        return html

    pattern = re.compile(
        r'(?P<first><a\b(?P<attrs1>[^>]*\bhref\s*=\s*(?P<q1>["\'])#(?P<target>page-[^"\']+)(?P=q1)[^>]*)>'
        r"\s*See\s*</a>)"
        r"\s*"
        r'<a\b[^>]*\bhref\s*=\s*(?P<q2>["\'])#(?P=target)(?P=q2)[^>]*>'
        r"(?P<body>\s*(?:pages?|pp?\.?)?\s*\d{1,4}[\)\]\.,;:]*\s*)</a>",
        re.IGNORECASE,
    )
    return pattern.sub(lambda match: f"{match.group('first')} {match.group('body').strip()}", html)


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
