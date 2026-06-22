from __future__ import annotations

import re

from .html_fragments import visible_text

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


def normalize_front_matter_marker_numbers(text: str) -> str:
    return ",".join(re.findall(r"\d{1,2}", text))


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
    "SUPERSCRIPT_DIGIT_TRANSLATION",
    "looks_author_byline_front_matter",
    "looks_author_marker_ocr_candidate",
    "normalize_front_matter_marker_numbers",
    "repair_affiliation_label_ocr_body",
    "repair_author_marker_ocr_body",
    "unicode_capitalized_name_pair_count",
    "unicode_glued_author_marker_count",
]
