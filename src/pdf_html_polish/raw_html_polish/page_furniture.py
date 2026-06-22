from __future__ import annotations

import re

from .frontmatter_footnotes import PAGE_HEADER_FOOTER_LINE_PATTERN
from .html_fragments import node_has_class, visible_text


SENTENCE_NODE_PATTERN = re.compile(
    r"<p\b[^>]*>[\s\S]*?</p>|<figure\b[\s\S]*?</figure>|<h[1-6]\b[^>]*>[\s\S]*?</h[1-6]>|<table\b[\s\S]*?</table>",
    re.IGNORECASE,
)
SENTENCE_P_NODE_PATTERN = re.compile(
    r'^(?P<open><p\b[^>]*>)(?P<body>[\s\S]*)(?P<close></p>)$',
    re.IGNORECASE,
)
PARAGRAPH_PATTERN = re.compile(r"(<p\b[^>]*>)([\s\S]*?)(</p>)", re.IGNORECASE)
WILEY_DOWNLOAD_PAGE_FURNITURE_PATTERN = re.compile(
    r"^\s*\d{6,9},\s+\d{4},\s+[A-Za-z0-9]+,\s+Downloaded\s+from\s+"
    r"https://onlinelibrary\.wiley\.com/doi/\S+\s+by\s+[\s\S]{0,900}?"
    r"Wiley\s+Online\s+Library\b[\s\S]{0,900}?"
    r"(?:Terms\s+and\s+Conditions|Creative\s+Commons\s+License)\b",
    re.IGNORECASE,
)
JOURNAL_PAGE_FURNITURE_PATTERN = re.compile(
    r"^[A-Z][A-Za-z& .:-]{2,80}\s+\d{4}\s*,\s*\d+\s*,\s*\d+"
    r"(?:\s*\.\s*https?://doi\.org/\S+)?"
    r"(?:\s+\d+\s+of\s+\d+)?\s*$",
    re.IGNORECASE,
)
LEADING_PAGE_ANCHOR_HTML_PATTERN = (
    r'(?:\s|<span\b[^>]*\bid\s*=\s*["\']page-[^"\']+["\'][^>]*>\s*</span>)*'
)
PDF_RUNNING_HEADER_PREFIX_PATTERNS = (
    re.compile(
        rf"^(?P<lead>{LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>(?:[A-Z][A-Za-z'\-]+\s+et\s+al\.\s+)?Combined\s+Imaging\s+in\s+Breast\s+Cancer)\b"
        r"(?P<tail>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^(?P<lead>{LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>Journal\s+of\s+Materials\s+Chemistry\s+B\s+Accepted\s+Manuscrip(?:t)?)\b"
        r"(?P<tail>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^(?P<lead>{LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>ChemComm\s+Accepted\s+Manuscript)\b"
        r"(?P<tail>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^(?P<lead>{LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>Published\s+on\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\.?\s+Downloaded\s+by\s+[\s\S]*?)"
        r"(?P<tail>\s*)$",
        re.IGNORECASE,
    ),
)
PDF_LINE_NUMBER_CONTINUATION_BODY_PATTERN = re.compile(
    rf"^(?P<lead>{LEADING_PAGE_ANCHOR_HTML_PATTERN})"
    r"(?:(?P<num>[1-9]\d{0,2})|<sup\b[^>]*>\s*(?P<sup_num>[1-9]\d{0,2})\s*</sup>)\s*"
    r"(?P<tail>[\s\S]*)$",
    re.IGNORECASE,
)
PUBLISHER_CHROME_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<[^>]+>\s*)*check\s+for\s*(?:</[^>]+>\s*)*</h[1-6]>\s*"
        r"<p\b[^>]*>\s*updates\s*</p>\s*"
        r"(?:<p\b[^>]*>\s*Citation\s*:[\s\S]{0,6000}?</p>\s*)?"
        r"(?:<p\b[^>]*>\s*Academic\s+Editor\s*:[\s\S]{0,1200}?</p>\s*)?"
        r"(?:<p\b(?=[^>]*\bz2m-front-matter\b)[^>]*>\s*"
        r"Received\s*:[\s\S]{0,1200}?Published\s*:[\s\S]{0,1200}?</p>\s*)?"
        r"(?:<p\b[^>]*>\s*Publisher['\u2019]s\s+Note\s*:[\s\S]{0,1600}?</p>\s*)?"
        r"(?:<p\b[^>]*>\s*Copyright\s*:[\s\S]{0,2600}?</p>\s*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h1\b[^>]*>\s*(?:<b\b[^>]*>\s*)?"
        r"Resonance-Compatible\s+Incubator\s+With\s+a\s+Built-in\s+Coil\s+"
        r"Ultrafast\s+Magnetic\s+Resonance\s+Imaging\s+of\s+the\s+Neonate\s+"
        r"in\s+a\s+Magnetic[\s\S]*?(?=</body>|</main>|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<[^>]+>\s*)*FLORE\s+Repository\s+istituzionale"
        r"[\s\S]{0,800}?</h[1-6]>"
        r"[\s\S]{0,200000}?\bArticle\s+begins\s+on\s+next\s+page\b[\s\S]{0,500}?</p>\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<b>\s*)?Articles\s+you\s+may\s+be\s+interested\s+in"
        r"(?:\s*</b>)?\s*</h[1-6]>"
        r"[\s\S]{0,120000}?(?=<p\b[^>]*>\s*<img\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<[^>]+>\s*)*University\s+of\s+Groningen"
        r"[\s\S]{0,800}?</h[1-6]>"
        r"[\s\S]{0,160000}?<p\b[^>]*>\s*Download\s+date\s*:[\s\S]{0,500}?</p>\s*",
        re.IGNORECASE,
    ),
)


def drop_page_header_footer_paragraphs(html: str) -> str:
    """Remove OCR page header/footer paragraphs such as ``Page X of Y``."""

    def replace(match: re.Match[str]) -> str:
        body = match.group(2) or ""
        visible = visible_text(body)
        if not visible:
            return match.group(0)
        if WILEY_DOWNLOAD_PAGE_FURNITURE_PATTERN.match(visible):
            return ""
        if len(visible) <= 180 and JOURNAL_PAGE_FURNITURE_PATTERN.match(visible):
            return ""
        if not PAGE_HEADER_FOOTER_LINE_PATTERN.search(visible):
            return match.group(0)
        low = visible.lower()
        if (
            "et al." in low
            or "nature " in low
            or "journal" in low
            or len(visible) <= 220
        ):
            return ""
        return match.group(0)

    return PARAGRAPH_PATTERN.sub(replace, html)


def looks_running_header_line(visible: str) -> bool:
    text = re.sub(r"\s+", " ", visible).strip()
    if not text:
        return False
    if PAGE_HEADER_FOOTER_LINE_PATTERN.search(text):
        return True
    if len(text) > 220:
        return False
    for pattern in PDF_RUNNING_HEADER_PREFIX_PATTERNS:
        match = pattern.match(text)
        if match is not None and not match.group("tail").strip():
            return True
    return False


def normalize_page_furniture_key(visible: str) -> str:
    text = re.sub(r"\s+", " ", visible).strip()
    return text.lower()


def looks_repeated_page_furniture_text(visible: str) -> bool:
    text = re.sub(r"\s+", " ", visible).strip()
    if not text or len(text) > 220:
        return False
    if looks_running_header_line(text):
        return True
    lower = text.lower()
    if re.search(r"\b(?:published on|downloaded by|accepted manuscript|page\s+\d+\s+of\s+\d+)\b", lower):
        return True
    if re.search(r"\b(?:journal|chemistry|chemcomm|medicine|imaging|manuscript)\b", lower):
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
        return 3 <= len(words) <= 14
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if not (3 <= len(words) <= 12):
        return False
    if text.rstrip().endswith((".", "!", "?", ":", ";")):
        return False
    titleish = sum(1 for word in words if word[:1].isupper() or word.isupper())
    return titleish / max(len(words), 1) >= 0.55


def is_protected_page_furniture_node(raw: str) -> bool:
    protected_classes = (
        "z2m-table-note",
        "z2m-footnote",
        "z2m-figure-caption",
        "z2m-table-caption",
        "z2m-ref-link",
        "z2m-references-block",
    )
    if any(node_has_class(raw, class_name) for class_name in protected_classes):
        return True
    if re.search(r'\bblock-type\s*=\s*(["\'])List(?:Group|Item)\1', raw, re.IGNORECASE):
        return True
    if re.match(r"^\s*<h[1-6]\b", raw, re.IGNORECASE):
        visible = visible_text(raw)
        if re.match(r"^(?:abstract|introduction|results?|discussion|conclusions?|references?)\b", visible, re.IGNORECASE):
            return True
    return False


def repeated_page_furniture_keys(html: str) -> set[str]:
    counts: dict[str, int] = {}
    for node in SENTENCE_NODE_PATTERN.finditer(html):
        raw = node.group(0)
        if not (raw.lstrip().lower().startswith("<p") or re.match(r"^\s*<h[1-6]\b", raw, re.IGNORECASE)):
            continue
        if is_protected_page_furniture_node(raw):
            continue
        visible = visible_text(raw)
        if not looks_repeated_page_furniture_text(visible):
            continue
        key = normalize_page_furniture_key(visible)
        counts[key] = counts.get(key, 0) + 1
    return {key for key, count in counts.items() if count >= 2}


def strip_plain_visible_prefix_from_body(body: str, visible_prefix: str) -> str | None:
    prefix_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'&.-]*", visible_prefix)
    if len(prefix_words) < 3:
        return None
    prefix_pattern = r"\s+".join(re.escape(word) for word in prefix_words)
    pattern = re.compile(
        rf"^(?P<lead>{LEADING_PAGE_ANCHOR_HTML_PATTERN})(?P<prefix>{prefix_pattern})\b(?P<tail>[\s\S]+)$",
        re.IGNORECASE,
    )
    match = pattern.match(body)
    if match is None:
        return None
    tail = match.group("tail").lstrip()
    tail_text = visible_text(tail)
    if len(tail_text) < 6:
        return None
    return match.group("lead") + tail


def drop_repeated_page_furniture(html: str) -> str:
    repeated_keys = repeated_page_furniture_keys(html)
    if not repeated_keys:
        return html

    key_to_text: dict[str, str] = {}
    for node in SENTENCE_NODE_PATTERN.finditer(html):
        visible = visible_text(node.group(0))
        key = normalize_page_furniture_key(visible)
        if key in repeated_keys and key not in key_to_text:
            key_to_text[key] = re.sub(r"\s+", " ", visible).strip()

    nodes = list(SENTENCE_NODE_PATTERN.finditer(html))
    dropped: set[int] = set()
    replacements: dict[int, str] = {}

    for idx, node in enumerate(nodes):
        raw = node.group(0)
        if not raw.lstrip().lower().startswith("<p"):
            continue
        if is_protected_page_furniture_node(raw):
            continue
        match = SENTENCE_P_NODE_PATTERN.match(raw)
        if match is None:
            continue
        visible = visible_text(match.group("body"))
        key = normalize_page_furniture_key(visible)
        if key in repeated_keys:
            dropped.add(idx)
            continue
        for repeated_text in key_to_text.values():
            stripped_body = strip_plain_visible_prefix_from_body(match.group("body"), repeated_text)
            if stripped_body is None:
                continue
            replacements[idx] = f"{match.group('open')}{stripped_body}{match.group('close')}"
            break

    if not dropped and not replacements:
        return html

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def expand_span_start_to_leading_image_paragraph(html: str, start: int) -> int:
    prefix = html[:start]
    search_start = max(0, len(prefix) - 2_000_000)
    paragraph_start = prefix.lower().rfind("<p", search_start)
    if paragraph_start < 0:
        return start
    candidate = html[paragraph_start:start]
    if re.fullmatch(r"<p\b[^>]*>\s*<img\b[\s\S]*?</p>\s*", candidate, flags=re.IGNORECASE):
        return paragraph_start
    return start


def drop_publisher_chrome_pages(html: str) -> str:
    spans: list[tuple[int, int]] = []
    for pattern in PUBLISHER_CHROME_BLOCK_PATTERNS:
        for match in pattern.finditer(html):
            spans.append((expand_span_start_to_leading_image_paragraph(html, match.start()), match.end()))
    if not spans:
        return html

    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    out: list[str] = []
    cursor = 0
    for start, end in merged:
        out.append(html[cursor:start])
        cursor = end
    out.append(html[cursor:])
    return "".join(out)


def strip_pdf_running_header_prefix_from_body(body: str) -> tuple[str, bool]:
    current = body
    changed = False
    while True:
        for pattern in PDF_RUNNING_HEADER_PREFIX_PATTERNS:
            match = pattern.match(current)
            if match is None:
                continue
            tail = match.group("tail")
            if not tail or not visible_text(tail):
                current = match.group("lead")
            else:
                current = match.group("lead") + tail.lstrip()
            changed = True
            break
        else:
            return current, changed


def strip_leading_pdf_line_number_from_body(body: str) -> tuple[str, bool]:
    match = PDF_LINE_NUMBER_CONTINUATION_BODY_PATTERN.match(body)
    if match is None:
        return body, False
    try:
        number = int(match.group("num") or match.group("sup_num"))
    except ValueError:
        return body, False
    if number % 5 != 0:
        return body, False

    tail = match.group("tail")
    tail_text = visible_text(tail)
    if not re.match(
        r"^(?:eV|nm|mM|uM|mL|cm|mm|kg|Research\s+Project)\b",
        tail_text,
        re.IGNORECASE,
    ):
        return body, False
    return match.group("lead") + tail.lstrip(), True


__all__ = [
    "JOURNAL_PAGE_FURNITURE_PATTERN",
    "LEADING_PAGE_ANCHOR_HTML_PATTERN",
    "PAGE_HEADER_FOOTER_LINE_PATTERN",
    "PDF_LINE_NUMBER_CONTINUATION_BODY_PATTERN",
    "PDF_RUNNING_HEADER_PREFIX_PATTERNS",
    "PUBLISHER_CHROME_BLOCK_PATTERNS",
    "SENTENCE_NODE_PATTERN",
    "SENTENCE_P_NODE_PATTERN",
    "WILEY_DOWNLOAD_PAGE_FURNITURE_PATTERN",
    "drop_page_header_footer_paragraphs",
    "drop_publisher_chrome_pages",
    "drop_repeated_page_furniture",
    "expand_span_start_to_leading_image_paragraph",
    "is_protected_page_furniture_node",
    "looks_repeated_page_furniture_text",
    "looks_running_header_line",
    "normalize_page_furniture_key",
    "repeated_page_furniture_keys",
    "strip_leading_pdf_line_number_from_body",
    "strip_pdf_running_header_prefix_from_body",
    "strip_plain_visible_prefix_from_body",
]
