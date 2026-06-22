from __future__ import annotations

from collections.abc import Callable
import re

from .html_fragments import add_class_attr, add_id_attr, append_class_to_attrs, visible_text

SUPERSCRIPT_DIGIT_TRANSLATION = str.maketrans(
    {
        "\u2070": "0",
        "\u00b9": "1",
        "\u00b2": "2",
        "\u00b3": "3",
        "\u2074": "4",
        "\u2075": "5",
        "\u2076": "6",
        "\u2077": "7",
        "\u2078": "8",
        "\u2079": "9",
    }
)
AUTHOR_MARKER_OCR_SYMBOL_PATTERN = re.compile(r"\s*[\u00c2\u0412]?\u00a9\s*")
AUTHOR_BYLINE_NAME_PATTERN = re.compile(
    r"\b"
    r"(?:[A-Z][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]*|[A-Z]\.)"
    r"(?:\s+(?:[A-Z][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]*|[A-Z]\.)){1,5}"
    r"\b",
    re.UNICODE,
)
AUTHOR_MARKER_NUMBER_RUN_PATTERN = re.compile(
    r"(?P<name>\b[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){1,6})\s*"
    r"(?P<nums>\d{1,2}(?:(?:\s+|[,.])\d{1,2}){0,5})"
    r"(?P<marker>[\*\u2020\u2021\u22a0\u2709]?)"
    r"(?=\s*(?:,|&amp;|&|</p>|$))"
)
AUTHOR_EXISTING_SUP_SPACE_PATTERN = re.compile(
    r"\s+(?=<sup\b[^>]*>\s*[\d,\s]+\s*</sup>)",
    re.IGNORECASE | re.DOTALL,
)
AFFILIATION_LABEL_OCR_PATTERN = re.compile(
    r"(?P<prefix>"
    r"^\s*(?:(?:<span\b[^>]*\bid\s*=\s*(?:['\"])page-[^'\"]+(?:['\"])[^>]*>\s*</span>|"
    r"<(?:i|b|em|strong)\b[^>]*>)\s*)*|"
    r"(?<=[.;:,])\s+|(?<=</a>)\s+|"
    r"\b(?:UK|USA|Italy|Poland|Germany|Svizzera|Italia)\s+"
    r")(?P<num>\d{1,2})\s*(?=[A-Z])",
    re.IGNORECASE,
)
FOOTNOTE_P_NODE_PATTERN = re.compile(
    r'^(?P<open><p\b[^>]*>)(?P<body>[\s\S]*)(?P<close></p>)$',
    re.IGNORECASE,
)
LEADING_PAGE_SPAN_PATTERN = re.compile(
    r'^\s*(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>\s*)+',
    re.IGNORECASE,
)
P_BLOCK_PATTERN = re.compile(
    r'(?P<open><p\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></p>)',
    re.IGNORECASE,
)
SUP_PATTERN = re.compile(r"<sup\b[^>]*>(.*?)</sup>", re.IGNORECASE | re.DOTALL)
PAGE_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
FOOTNOTE_CLASS_PATTERN = re.compile(
    r'\bclass\s*=\s*(["\'])(?=[^"\']*\bz2m-footnote\b)[^"\']*\1',
    re.IGNORECASE,
)
PAGE_ID_PATTERN = re.compile(r'\bid\s*=\s*(["\'])(page-[^"\']+)\1', re.IGNORECASE)


def unicode_capitalized_name_pair_count(text: str) -> int:
    token_re = re.compile(r"[^\W\d_][^\W\d_.'-]*", re.UNICODE)
    tokens = list(token_re.finditer(text))
    count = 0
    for left, right in zip(tokens, tokens[1:]):
        if not re.fullmatch(r"\s+", text[left.end() : right.start()]):
            continue
        if left.group(0)[0].isupper() and right.group(0)[0].isupper():
            count += 1
    return count


def unicode_glued_author_marker_count(text: str) -> int:
    if len(text) > 2000:
        text = text[:2000]
    text = text.translate(SUPERSCRIPT_DIGIT_TRANSLATION)
    token = r"[^\W\d_][^\W\d_.'-]*"
    marker_re = re.compile(
        rf"(?<!\w)(?P<name>{token}(?:\s+{token}){{0,3}})\s*,?\s*\d{{1,2}}(?:,\d{{1,2}})*",
        re.UNICODE,
    )
    count = 0
    for match in marker_re.finditer(text):
        name_tokens = re.findall(token, match.group("name"), re.UNICODE)
        if name_tokens and name_tokens[-1][0].isupper():
            count += 1
    return count


def looks_author_byline_front_matter(raw: str, visible: str) -> bool:
    if len(visible) < 6 or len(visible) > 450:
        return False
    lower = visible.lower()
    marker_visible = visible.translate(SUPERSCRIPT_DIGIT_TRANSLATION)
    if re.match(r"^\s*(?:abstract|introduction|references|bibliography)\b", lower):
        return False
    if len(re.findall(r"[.!?](?:\s|$)", visible)) >= 2:
        return False
    if re.search(
        r"\b(?:are|is|was|were|has|have|had|using|used|support|supports|"
        r"show|shows|shown|study|studies|method|methods|results?|participants?|"
        r"patients?|models?|devices?|figure|table)\b",
        lower,
    ):
        return False
    if re.search(r"\b(?:box|fig(?:ure)?s?|table|section|appendix|equations?|eqs?\.?)\s+\d", lower):
        return False

    sup_marker_hits = len(
        re.findall(
            r"<sup\b[^>]*>\s*(?:<a\b[^>]*>\s*)?\d{1,2}(?:\s*[,.\-]\s*\d{1,2}){0,6}",
            raw,
            re.IGNORECASE | re.DOTALL,
        )
    )
    glued_marker_hits = max(
        len(
            re.findall(
                r"\b[A-Z][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff.'-]+"
                r"(?:\s+[A-Z][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff.'-]+){1,5}"
                r"\s*\d{1,2}(?:\s*[,.\-]\s*\d{1,2}){0,6}",
                marker_visible,
            )
        ),
        unicode_glued_author_marker_count(visible),
    )
    if sup_marker_hits == 0 and glued_marker_hits == 0:
        return False

    name_hits = len(AUTHOR_BYLINE_NAME_PATTERN.findall(visible))
    if name_hits < 1:
        return False
    if name_hits >= 2 and (sup_marker_hits >= 1 or glued_marker_hits >= 1):
        return True

    # Single-author bylines are often just "Name <sup>1,2</sup>" before Abstract.
    residue = AUTHOR_BYLINE_NAME_PATTERN.sub(" ", visible)
    residue = re.sub(r"\b(?:and|or|et\s+al)\b", " ", residue, flags=re.IGNORECASE)
    residue = re.sub(r"[\d\s,.;:*()\[\]\-\u2013\u2014\u2020\u2021&]+", " ", residue)
    return len(residue.strip()) <= 12


def looks_author_marker_ocr_candidate(raw: str) -> bool:
    text = visible_text(raw)
    if not text or len(text) > 4000:
        return False
    lower = text.lower()
    marker_visible = text.translate(SUPERSCRIPT_DIGIT_TRANSLATION)
    if re.match(r"^\s*(?:abstract|introduction)\b", lower):
        return False
    name_like = len(re.findall(r"\b[A-Z][A-Za-z.'-]+\s+[A-Z][A-Za-z.'-]+\b", text))
    glued_author_markers = len(
        re.findall(
            r"\b[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){1,6}\d{1,2}[\*\u2020\u2021\u22a0\u2709]?",
            marker_visible,
        )
    )
    if glued_author_markers >= 2 and (text.count(",") >= 1 or "&" in text):
        return True
    if name_like < 3:
        return False
    marker_like = (
        re.search(r"[\u00c2\u0412]?\u00a9\s*\d", marker_visible) is not None
        or re.search(r"\b\d{1,2}\.\d{1,2}\.\d{1,2}\b", marker_visible) is not None
        or re.search(r"(?:\b[A-Z][A-Za-z.'-]+\s+){1,5}\d{1,2}\s+\d{1,2}\b", marker_visible) is not None
        or re.search(r"\b[A-Z][A-Za-z.'-]+\d{1,2}[\*\u2020\u2021\u22a0\u2709]?(?:,|&|$)", marker_visible) is not None
    )
    if re.match(r"^\s*(?:received|accepted|published)\b", lower) and not marker_like:
        return False
    return marker_like and (text.count(",") >= 2 or "&" in text)


def looks_affiliation_label_body(body: str) -> bool:
    return bool(
        re.search(
            r"(?:Department|University|Institute|Laborator(?:y|ies)|Hospital|College|Centre|Center)",
            visible_text(body),
            re.IGNORECASE,
        )
    )


def leading_footnote_number(raw: str) -> int | None:
    match = FOOTNOTE_P_NODE_PATTERN.match(raw)
    if match is None:
        return None
    body = match.group("body")
    leading = LEADING_PAGE_SPAN_PATTERN.sub("", body)
    leading = re.sub(r"^\s*<a\b[^>]*>\s*", "", leading, count=1, flags=re.IGNORECASE)
    sup_match = re.match(
        r"\s*<sup\b[^>]*>\s*(?:<a\b[^>]*>\s*)?(\d{1,2})(?:\s*</a>)?\s*</sup>(?=\s|\S)",
        leading,
        re.IGNORECASE | re.DOTALL,
    )
    if sup_match is not None:
        return int(sup_match.group(1))
    text_match = re.match(r"^\s*(\d{1,2})(?=\s+[A-Z]|(?:https?://|www\.))", visible_text(leading), re.IGNORECASE)
    if text_match is not None:
        return int(text_match.group(1))
    return None


def footnote_keywords(text: str) -> set[str]:
    text = re.sub(r"^\s*\d{1,2}\s+", "", text)
    stop = {
        "before",
        "after",
        "which",
        "where",
        "these",
        "those",
        "their",
        "there",
        "material",
    }
    words = [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z-]{5,}", text)]
    return {word for word in words[:12] if word not in stop}


def looks_footnote_block(
    raw: str,
    *,
    figure_caption_num_from_visible: Callable[[str], object | None],
    table_caption_key_from_visible: Callable[[str], object | None],
) -> bool:
    number = leading_footnote_number(raw)
    if number is None or number <= 0 or number > 20:
        return False
    text = visible_text(raw)
    if re.search(r"(?:https?://|www\.)", text, re.IGNORECASE):
        return len(text) <= 700
    if len(text) < 35 or len(text) > 700:
        return False
    if figure_caption_num_from_visible(text) is not None or table_caption_key_from_visible(text) is not None:
        return False
    lower = text.lower()
    if lower.startswith(("abstract", "introduction", "references", "bibliography")):
        return False
    return len(re.findall(r"[A-Za-z]{3,}", text)) >= 6


def mark_footnote_paragraphs_and_refs(
    html: str,
    *,
    figure_caption_num_from_visible: Callable[[str], object | None],
    table_caption_key_from_visible: Callable[[str], object | None],
    citation_tag_is_protected: Callable[[str], bool],
    numeric_superscript_context_allows_citation: Callable[[str, int, int], bool],
) -> str:
    footnote_keyword_map: dict[int, set[str]] = {}

    def mark_footnote(match: re.Match[str]) -> str:
        raw = match.group(0)
        if not looks_footnote_block(
            raw,
            figure_caption_num_from_visible=figure_caption_num_from_visible,
            table_caption_key_from_visible=table_caption_key_from_visible,
        ):
            return raw
        number = leading_footnote_number(raw)
        if number is None:
            return raw
        footnote_keyword_map[number] = footnote_keywords(visible_text(raw))
        attrs = match.group("open")[2:-1]
        marked_attrs = append_class_to_attrs(attrs, "z2m-footnote")
        marked_open = add_id_attr(f"<p{marked_attrs}>", f"footnote-{number}")
        return f"{marked_open}{match.group('body')}{match.group('close')}"

    marked = P_BLOCK_PATTERN.sub(mark_footnote, html)
    if not footnote_keyword_map:
        return marked

    def mark_ref(match: re.Match[str]) -> str:
        raw = match.group(0)
        open_tag = match.group("open")
        if citation_tag_is_protected(open_tag):
            return raw
        body = match.group("body")

        def replace_sup(sup_match: re.Match[str]) -> str:
            sup_raw = sup_match.group(0)
            if "z2m-footnote-ref" in sup_raw or "<a " in sup_raw.lower():
                return sup_raw
            inner = visible_text(sup_match.group(1))
            if not re.fullmatch(r"\d{1,2}", inner):
                range_numbers = [int(value) for value in re.findall(r"\d{1,2}", inner)]
                if (
                    len(range_numbers) < 2
                    or not re.fullmatch(r"\s*\d{1,2}(?:\s*(?:[,;\-\u2013\u2014])\s*\d{1,2}){1,12}\s*", inner)
                    or any(number not in footnote_keyword_map for number in range_numbers)
                    or not numeric_superscript_context_allows_citation(body, sup_match.start(), sup_match.end())
                ):
                    return sup_raw
                open_end = sup_raw.find(">")
                if open_end < 0:
                    return sup_raw
                sup_open = add_class_attr(sup_raw[: open_end + 1], "z2m-footnote-ref")
                return f"{sup_open}{sup_match.group(1)}</sup>"
            number = int(inner)
            keywords = footnote_keyword_map.get(number)
            if not keywords:
                return sup_raw
            left_text = visible_text(body[: sup_match.start()]).lower()
            if not any(keyword in left_text for keyword in keywords):
                return sup_raw
            open_end = sup_raw.find(">")
            if open_end < 0:
                return sup_raw
            sup_open = add_class_attr(sup_raw[: open_end + 1], "z2m-footnote-ref")
            return f"{sup_open}{sup_match.group(1)}</sup>"

        new_body = SUP_PATTERN.sub(replace_sup, body)
        return f"{open_tag}{new_body}{match.group('close')}"

    return P_BLOCK_PATTERN.sub(mark_ref, marked)


def repair_page_footnote_ref_links(html: str) -> str:
    """Convert page-linked OCR footnote markers back to superscript notes."""
    if "#page-" not in html or "z2m-footnote" not in html:
        return html

    footnote_page_ids: set[str] = set()
    footnote_numbers: set[int] = set()
    for block in P_BLOCK_PATTERN.finditer(html):
        raw = block.group(0)
        if FOOTNOTE_CLASS_PATTERN.search(raw) is None:
            continue
        footnote_numbers.update(int(num) for num in re.findall(r"<sup\b[^>]*>\s*(\d{1,2})\s*</sup>", raw, re.IGNORECASE))
        footnote_numbers.update(
            int(num)
            for num in re.findall(r"(?<!\d)(\d{1,2})(?=(?:\s+https?://|\s+www\.|https?://|www\.))", visible_text(raw), re.IGNORECASE)
        )
        leading_number = leading_footnote_number(raw)
        if leading_number is not None:
            footnote_numbers.add(leading_number)
        for page_match in PAGE_ID_PATTERN.finditer(raw):
            footnote_page_ids.add(page_match.group(2))

    if not footnote_page_ids or not footnote_numbers:
        return html

    def repair_block(match: re.Match[str]) -> str:
        raw = match.group(0)
        if FOOTNOTE_CLASS_PATTERN.search(raw) is not None:
            return raw

        def replace_anchor(anchor_match: re.Match[str]) -> str:
            attrs = anchor_match.group("attrs")
            target_match = re.search(r'\bhref\s*=\s*(["\'])#(?P<target>page-[^"\']+)\1', attrs, re.IGNORECASE)
            if target_match is None or target_match.group("target") not in footnote_page_ids:
                return anchor_match.group(0)
            label = visible_text(anchor_match.group("body")).strip()
            label_match = re.fullmatch(r"(?P<prefix>[A-Za-z]?)(?P<num>\d{1,2})(?P<trail>[\)\]\.,;:]*)", label)
            if label_match is None:
                return anchor_match.group(0)
            number = int(label_match.group("num"))
            if number not in footnote_numbers:
                return anchor_match.group(0)
            return (
                f'{label_match.group("prefix")}'
                f'<sup class="z2m-footnote-ref">{number}</sup>'
                f'{label_match.group("trail")}'
            )

        body = PAGE_ANCHOR_PATTERN.sub(replace_anchor, match.group("body"))
        body = re.sub(
            r'(\b[A-Za-z]{3,})\s+([A-Za-z])(<sup class="z2m-footnote-ref">\d{1,2}</sup>)',
            r"\1\2\3",
            body,
        )
        return f"{match.group('open')}{body}{match.group('close')}"

    return P_BLOCK_PATTERN.sub(repair_block, html)


def normalize_front_matter_marker_numbers(text: str) -> str:
    return ",".join(re.findall(r"\d{1,2}", text))


def valid_front_matter_marker_numbers(value: str) -> str | None:
    numbers = normalize_front_matter_marker_numbers(value)
    if not numbers:
        return None
    parsed = [int(item) for item in numbers.split(",")]
    if any(number <= 0 or number > 30 for number in parsed):
        return None
    return numbers


def repair_front_matter_page_anchor_markers(
    body: str,
    *,
    looks_like_ocr_split_word_join: Callable[[str, str], bool],
) -> str:
    """Convert OCR-glued author markers like ``...i<a>1</a>`` out of page links."""
    glued_pattern = re.compile(
        r"(?P<stem>\b[A-Za-z]{3,})\s*"
        r"<a\b[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*>"
        r"\s*(?P<letter>[A-Za-z])(?P<nums>\d{1,2}(?:\s*,\s*\d{1,2})*)(?P<trail>,?)\s*</a>",
        re.IGNORECASE,
    )
    bare_pattern = re.compile(
        r"<a\b[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*>"
        r"\s*(?:[A-Za-z])?(?P<nums>\d{1,2}(?:\s*,\s*\d{1,2})*)(?P<trail>,?)\s*</a>",
        re.IGNORECASE,
    )

    def replace_glued(match: re.Match[str]) -> str:
        stem = match.group("stem")
        letter = match.group("letter")
        if not looks_like_ocr_split_word_join(stem, letter):
            return match.group(0)
        numbers = valid_front_matter_marker_numbers(match.group("nums"))
        if numbers is None:
            return match.group(0)
        if letter.lower() == "i" and stem.lower().endswith(("i", "v", "x")):
            suffix = ""
        else:
            suffix = "" if stem.lower().endswith(letter.lower()) else letter
        return f"{stem}{suffix}<sup>{numbers}</sup>{match.group('trail')}"

    def replace_bare(match: re.Match[str]) -> str:
        numbers = valid_front_matter_marker_numbers(match.group("nums"))
        if numbers is None:
            return match.group(0)
        return f"<sup>{numbers}</sup>{match.group('trail')}"

    body = glued_pattern.sub(replace_glued, body)
    return bare_pattern.sub(replace_bare, body)


def repair_author_marker_ocr_body(body: str) -> str:
    body = AUTHOR_MARKER_OCR_SYMBOL_PATTERN.sub(" ", body)
    body = body.translate(SUPERSCRIPT_DIGIT_TRANSLATION)
    body = AUTHOR_EXISTING_SUP_SPACE_PATTERN.sub("", body)
    body = re.sub(r"(?<=\d)\s*([,.])\s*(?=\d{1,2}\b)", r"\1", body)

    def replace_marker(match: re.Match[str]) -> str:
        numbers = normalize_front_matter_marker_numbers(match.group("nums"))
        if not numbers:
            return match.group(0)
        marker = match.group("marker") or ""
        return f"{match.group('name')}<sup>{numbers}</sup>{marker}"

    body = AUTHOR_MARKER_NUMBER_RUN_PATTERN.sub(replace_marker, body)
    body = re.sub(r"\s+([,;])", r"\1", body)
    body = re.sub(r"\s{2,}", " ", body)
    return body.strip()


def repair_affiliation_label_ocr_body(body: str) -> str:
    def replace_label(match: re.Match[str]) -> str:
        number = int(match.group("num"))
        if number <= 0 or number > 30:
            return match.group(0)
        return f"{match.group('prefix')}<sup>{number}</sup>"

    return AFFILIATION_LABEL_OCR_PATTERN.sub(replace_label, body)


__all__ = [
    "AFFILIATION_LABEL_OCR_PATTERN",
    "AUTHOR_BYLINE_NAME_PATTERN",
    "AUTHOR_EXISTING_SUP_SPACE_PATTERN",
    "AUTHOR_MARKER_NUMBER_RUN_PATTERN",
    "AUTHOR_MARKER_OCR_SYMBOL_PATTERN",
    "FOOTNOTE_P_NODE_PATTERN",
    "LEADING_PAGE_SPAN_PATTERN",
    "P_BLOCK_PATTERN",
    "FOOTNOTE_CLASS_PATTERN",
    "PAGE_ANCHOR_PATTERN",
    "PAGE_ID_PATTERN",
    "SUPERSCRIPT_DIGIT_TRANSLATION",
    "SUP_PATTERN",
    "footnote_keywords",
    "leading_footnote_number",
    "looks_affiliation_label_body",
    "looks_author_byline_front_matter",
    "looks_author_marker_ocr_candidate",
    "looks_footnote_block",
    "mark_footnote_paragraphs_and_refs",
    "normalize_front_matter_marker_numbers",
    "repair_affiliation_label_ocr_body",
    "repair_author_marker_ocr_body",
    "repair_front_matter_page_anchor_markers",
    "repair_page_footnote_ref_links",
    "unicode_capitalized_name_pair_count",
    "unicode_glued_author_marker_count",
    "valid_front_matter_marker_numbers",
]
