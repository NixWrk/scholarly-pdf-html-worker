"""P04 citation-range classification helpers."""

from __future__ import annotations

import re
from typing import Callable

from pdf_html_polish.quality_loop.audit_blocks import Block, strip_tags


CITATION_RANGE_LIST_RE = re.compile(
    r"\[\s*\d+\s*(?:[-\u2013]\s*\d+|,\s*\d+)"
    r"(?:\s*,\s*\d+(?:\s*[-\u2013]\s*\d+)?)*\s*\]"
)
TAGGED_CITATION_RANGE_LIST_RE = re.compile(
    r"\[\s*(?P<body>(?=[\s\S]*?<)[\s\S]{1,260}?)\s*\]",
    re.IGNORECASE,
)
SUP_NUMERIC_RANGE_RE = re.compile(
    r"<sup\b(?![^>]*\bz2m-unit-exp\b)[^>]*>"
    r"(?P<body>\s*\d{1,3}\s*(?:[-\u2013\u2014]\s*\d{1,3}|,\s*\d{1,3})"
    r"(?:\s*,\s*\d{1,3}(?:\s*[-\u2013\u2014]\s*\d{1,3})?)*\s*)"
    r"</sup>",
    re.IGNORECASE,
)
SUP_MEASUREMENT_UNIT_RIGHT_RE = re.compile(
    r"^\s*(?:[.)]\s*)?"
    r"(?:"
    r"(?:l|L|ml|mL|min|s|sec|kg|g|mg|m|cm|mm|um|A|V|Hz|bpm|mmHg)"
    r"(?:\b|[\s.\u00b7*/^-])|"
    r"(?:[munp\u00b5\u03bc]?m|[munp\u00b5\u03bc]?A|[munp\u00b5\u03bc]?V)\b"
    r")",
    re.IGNORECASE,
)
SUP_MEASUREMENT_CONTEXT_RE = re.compile(
    r"\b(?:above|below|difference|differences|exercise|fick|mean|measured|measurement|"
    r"rest|sd|value|values?)\b",
    re.IGNORECASE,
)
SUP_PROJECT_OR_GRANT_CONTEXT_RE = re.compile(
    r"\b(?:agreement|award|contract|funding|grant|project|programme|program|research)\s+"
    r"(?:no\.?|number|id)?\s*$",
    re.IGNORECASE,
)
SUP_DIMENSION_UNIT_LEFT_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*|[×x]\s*)"
    r"(?:m|cm|mm|km|ft|in)\s*$",
    re.IGNORECASE,
)
SUP_COUNT_OR_OPTION_CONTEXT_RE = re.compile(
    r"\b(?:chair|chairs|choice|choices|item|items|option|options|question|questions|"
    r"response|responses|target|targets)\b",
    re.IGNORECASE,
)
STAT_NUMERIC_CONTEXT_RE = re.compile(
    r"\b(?:sample\s+size|G\*Power|allocation\s+ratio|effect\s+size|"
    r"statistical\s+power|power\s+analysis)\b",
    re.IGNORECASE,
)
MATH_OR_MEASUREMENT_RANGE_CONTEXT_RE = re.compile(
    r"(?:\\\[|\\\(|"
    r"\b(?:anova|array|arrays|class|classes|coordinate|coordinates|equation|eq\.?|"
    r"formula|glm|heatmap|interval|intervals|likelihood|matrix|median|parameter|"
    r"parameters|probability|range|scale|score|scores|threshold|vector|"
    r"values?)\b|"
    r"[=<>]|[\u00b0\u03bc\u03c0\u03c3\u03c4\u03a6\u2208\u2211\u2212\u2217"
    r"\u2219\u2223\u223c\u2248\u25e6])",
    re.IGNORECASE,
)
NON_CITATION_BRACKET_RANGE_CONTEXT_RE = re.compile(
    r"\b(?:amplitude|array|arrays|bounds?|class\s+scores?|coordinate|coordinates|"
    r"current|dimension|dimensions|electrode\s+values?|feature|heatmap|input|"
    r"interval|intervals|layer|layers|likelihood|map\s+size|matrix|median|"
    r"normalization|normalized|output|parameters?|pixel|points?|probability|range|"
    r"random\s+number|scale|score|scores|sigmoid|starting|STAI|threshold|values?|"
    r"vector|vectors|VAS)\b|"
    r"[\u00b0\u03bc\u03c0\u03c3\u03c4\u03a6\u2208\u2211\u2212\u2217\u2219\u2223\u223c\u2248\u25e6]",
    re.IGNORECASE,
)


def looks_like_numeric_vector(text: str, match: re.Match[str]) -> bool:
    body = match.group(0).strip()[1:-1]
    numbers = [int(item) for item in re.findall(r"\d+", body)]
    if not numbers:
        return False
    if any(number == 0 for number in numbers):
        return True
    left_raw = text[max(0, match.start() - 100) : match.start()]
    right = text[match.end() : match.end() + 40]
    if re.search(r"[A-Za-z]\s*$", left_raw) and re.match(r"^[\s\u200b]*=", right):
        return True
    if len(numbers) == 2 and numbers[0] > numbers[1] and re.match(r"^[\s\u200b]*=", right):
        return True
    left = left_raw.lower()
    return bool(
        re.search(
            r"\b(?:vector|vectors|array|arrays|assignment|assignments|interval|intervals|"
            r"likelihood|likelihoods|score|scores|class|classes|elements|normalized|dividing)\b",
            left,
        )
    )


def looks_like_math_or_measurement_range(text: str, match: re.Match[str]) -> bool:
    body = match.group(0)
    if re.search(r"\[\s*(?:0|[-\u2212])", body):
        return True
    window = text[max(0, match.start() - 180) : min(len(text), match.end() + 180)]
    left = text[max(0, match.start() - 120) : match.start()]
    if re.search(r"\b(?:within|in|the)\s+(?:the\s+)?range\s*$", left, re.IGNORECASE):
        return True
    return MATH_OR_MEASUREMENT_RANGE_CONTEXT_RE.search(window) is not None


def plain_bracket_range_is_likely_non_citation_math_or_measurement(text: str, match: re.Match[str]) -> bool:
    body = match.group(0)
    numbers = [int(value) for value in re.findall(r"\d+", body)]
    if not numbers:
        return False
    left = text[max(0, match.start() - 80) : match.start()]
    if re.search(
        r"\b(?:prior|previous|related|reported|study|studies|work|works|literature|"
        r"references?|refs?)\s*$",
        left,
        re.IGNORECASE,
    ):
        return False
    right = text[match.end() : match.end() + 80]
    window = text[max(0, match.start() - 180) : min(len(text), match.end() + 180)]
    if any(number == 0 for number in numbers):
        return True
    if re.match(r"\s*(?:%|[munpВµОј]?A|[munpВµОј]?m|V|Hz|s|ms|kg|N)\b", right):
        return True
    if re.search(r"\b(?:map\s+size|starting|ending|points?)\b", window, re.IGNORECASE):
        return True
    if len(numbers) >= 3 and NON_CITATION_BRACKET_RANGE_CONTEXT_RE.search(window):
        return True
    return (
        NON_CITATION_BRACKET_RANGE_CONTEXT_RE.search(window) is not None
        and looks_like_math_or_measurement_range(text, match)
    )


def plain_bracket_range_is_likely_non_citation_table_text(text: str, match: re.Match[str]) -> bool:
    body = match.group(0)
    if re.fullmatch(r"\[\s*(?:19|20)\d{2}\s*[-\u2013\u2014]\s*(?:19|20)\d{2}\s*\]", body):
        return True
    window = text[max(0, match.start() - 220) : min(len(text), match.end() + 220)]
    return bool(
        re.search(r"\b(?:search\s+statement|set\s+number|concept|ti,\s*ab|exp\s+OR)\b", window, re.IGNORECASE)
        and re.search(r"\[\s*(?:19|20)\d{2}\s*[-\u2013\u2014]\s*(?:19|20)\d{2}\s*\]", body)
    )


def block_looks_like_math_or_measurement_range_context(block: Block) -> bool:
    text = block.text
    if STAT_NUMERIC_CONTEXT_RE.search(text):
        return True
    if re.search(r"\[\s*(?:0|[-\u2212])", text):
        return True
    return MATH_OR_MEASUREMENT_RANGE_CONTEXT_RE.search(text) is not None


def looks_like_table_flattened_citation_context(text: str) -> bool:
    if len(re.findall(r"\bet\s+al\.?\s*\d{1,3}\b", text, re.IGNORECASE)) < 2:
        return False
    return re.search(
        r"\b(?:algorithm|category|curve|descriptors|efficiency|flow\s+rate|"
        r"indicator|normal|compressive|constrictive|precision|recall|"
        r"roc|score|smooth|tower-shaped)\b",
        text,
        re.IGNORECASE,
    ) is not None


def looks_like_software_version_context(text: str, start: int) -> bool:
    left = text[max(0, start - 160) : start]
    return (
        re.search(
            r"\b(?:python|pytorch|cuda|tensorflow|torch|matlab|unity|opencv|numpy|scipy|"
            r"excel|photoshop)\s*$|"
            r"\b(?:python|pytorch|cuda|tensorflow|torch|matlab|unity|opencv|numpy|scipy|"
            r"excel|photoshop|driver)\s+(?:driver\s+)?version\s*$|"
            r"\bversion\s*$",
            left,
            re.IGNORECASE,
        )
        is not None
    )


def sup_numeric_range_is_software_version(block: Block, match: re.Match[str]) -> bool:
    numbers = re.findall(r"\d{1,3}", match.group("body"))
    if len(numbers) < 2:
        return False
    visible_pattern = r"\s*,\s*".join(re.escape(number) for number in numbers)
    for text_match in re.finditer(visible_pattern, block.text):
        if looks_like_software_version_context(block.text, text_match.start()):
            return True
    return False


def sup_numeric_range_is_measurement_value(block: Block, match: re.Match[str]) -> bool:
    """Detect OCR-raised decimal/list values that are followed by physical units."""

    right_text = strip_tags(block.raw[match.end() : match.end() + 260])
    if SUP_MEASUREMENT_UNIT_RIGHT_RE.match(right_text) is None:
        return False
    left_text = strip_tags(block.raw[max(0, match.start() - 220) : match.start()])
    if SUP_DIMENSION_UNIT_LEFT_RE.search(left_text):
        return True
    return SUP_MEASUREMENT_CONTEXT_RE.search(f"{left_text} {right_text}") is not None


DECIMAL_COMMA_VALUE_CONTEXT_RE = re.compile(
    r"\b(?:coefficient|coordinate|decline|depth|dispersion\s+ratio|equal\s+to|"
    r"height|length|mean|median|molecular\s+weight|ratio|slope|transl\.?|"
    r"translation|value|values?|width)\b|"
    r"\b(?:chi|χ)\s*2\b|p\s*[<=>]",
    re.IGNORECASE,
)


def sup_numeric_range_is_decimal_comma_value(block: Block, match: re.Match[str]) -> bool:
    body = match.group("body")
    if re.search(r"[-\u2013\u2014;]", body):
        return False
    parts = [int(value) for value in re.findall(r"\d{1,3}", body)]
    if len(parts) != 2:
        return False
    if parts[1] > 99:
        return False
    left_text = strip_tags(block.raw[max(0, match.start() - 220) : match.start()])
    right_text = strip_tags(block.raw[match.end() : match.end() + 220])
    if DECIMAL_COMMA_VALUE_CONTEXT_RE.search(f"{left_text} {right_text}"):
        return True
    if re.match(r"^\s*(?:[,;)]|\d+(?:\.\d+)?)", right_text):
        return True
    return False


def sup_numeric_range_is_count_or_option_value(block: Block, match: re.Match[str]) -> bool:
    left_text = strip_tags(block.raw[max(0, match.start() - 220) : match.start()])
    right_text = strip_tags(block.raw[match.end() : match.end() + 120])
    near_text = f"{left_text} {right_text}"
    if SUP_COUNT_OR_OPTION_CONTEXT_RE.search(near_text) is None:
        return False
    if re.match(
        r"^\s*(?:or\s+\d+\s+)?(?:chair|chairs|choice|choices|item|items|option|options|"
        r"question|questions|response|responses|target|targets)\b",
        right_text,
        re.IGNORECASE,
    ):
        return True
    return bool(
        re.search(
            r"\b(?:number\s+of|contained?|total|varied|conditional)\b",
            near_text,
            re.IGNORECASE,
        )
    )


def sup_numeric_range_is_low_number_table_layout_marker(block: Block, match: re.Match[str]) -> bool:
    if block.tag != "table" and not re.search(r"<t[dh]\b", block.raw, re.IGNORECASE):
        return False
    body = match.group("body")
    if re.search(r"[-\u2013\u2014;]", body):
        return False
    numbers = [int(value) for value in re.findall(r"\d{1,3}", body)]
    if len(numbers) != 2 or max(numbers) > 5:
        return False
    left_text = strip_tags(block.raw[max(0, match.start() - 140) : match.start()])
    right_text = strip_tags(block.raw[match.end() : match.end() + 140])
    return bool(
        re.search(r"\b(?:distance|head|height|sound|pattern|transl\.?|user)\b", f"{left_text} {right_text}", re.IGNORECASE)
    )


def sup_numeric_range_is_project_or_grant_number(block: Block, match: re.Match[str]) -> bool:
    left_text = strip_tags(block.raw[max(0, match.start() - 180) : match.start()])
    return SUP_PROJECT_OR_GRANT_CONTEXT_RE.search(left_text) is not None


def unlinked_sup_numeric_range_matches_footnote_targets(block: Block, footnote_numbers: set[int]) -> bool:
    if not footnote_numbers:
        return False
    for match in SUP_NUMERIC_RANGE_RE.finditer(block.raw):
        raw = match.group(0)
        if "z2m-ref-link" in raw:
            continue
        numbers = [int(value) for value in re.findall(r"\d{1,3}", match.group("body"))]
        if numbers and all(number in footnote_numbers for number in numbers):
            return True
    return False


def has_unlinked_tagged_citation_range(block: Block) -> bool:
    for match in TAGGED_CITATION_RANGE_LIST_RE.finditer(block.raw):
        body = match.group("body")
        if "<" not in body or "z2m-ref-link" in body:
            continue
        visible = strip_tags(body)
        if CITATION_RANGE_LIST_RE.fullmatch(f"[{visible}]") is not None:
            return True
    return False


def has_unlinked_sup_numeric_range(block: Block) -> bool:
    for match in SUP_NUMERIC_RANGE_RE.finditer(block.raw):
        raw = match.group(0)
        if "z2m-ref-link" not in raw:
            if "z2m-footnote-ref" in raw:
                continue
            if sup_numeric_range_is_project_or_grant_number(block, match):
                continue
            if sup_numeric_range_is_software_version(block, match):
                continue
            if sup_numeric_range_is_measurement_value(block, match):
                continue
            if sup_numeric_range_is_decimal_comma_value(block, match):
                continue
            if sup_numeric_range_is_count_or_option_value(block, match):
                continue
            if sup_numeric_range_is_low_number_table_layout_marker(block, match):
                continue
            return True
    return False


def unlinked_citation_range_kind(
    block: Block,
    *,
    looks_like_float_or_caption: Callable[[Block], bool],
    block_looks_like_frontmatter_affiliation_table: Callable[[Block], bool],
) -> str:
    match = CITATION_RANGE_LIST_RE.search(block.text)
    has_unlinked_plain_match = match is not None and "z2m-ref-link" not in block.raw
    has_vector_range = has_unlinked_plain_match and looks_like_numeric_vector(block.text, match)
    has_plain_range = has_unlinked_plain_match and not has_vector_range
    has_tagged_range = has_unlinked_tagged_citation_range(block)
    has_sup_range = has_unlinked_sup_numeric_range(block)
    if not has_plain_range and not has_vector_range and not has_tagged_range and not has_sup_range:
        return ""
    if (
        (block.block_type.lower() == "equation" or "z2m-equation-row" in block.classes)
        and has_unlinked_plain_match
        and not has_sup_range
    ):
        return ""
    if (
        has_unlinked_plain_match
        and match is not None
        and ("z2m-equation-row" in block.classes or block.block_type.lower() == "equation")
        and looks_like_numeric_vector(block.text, match)
        and not has_sup_range
    ):
        return ""
    if (
        has_unlinked_plain_match
        and not has_sup_range
        and match is not None
        and plain_bracket_range_is_likely_non_citation_math_or_measurement(block.text, match)
    ):
        return ""
    if looks_like_float_or_caption(block):
        if block_looks_like_frontmatter_affiliation_table(block):
            return ""
        if (
            has_unlinked_plain_match
            and not has_sup_range
            and match is not None
            and plain_bracket_range_is_likely_non_citation_table_text(block.text, match)
        ):
            return ""
        return "float"
    if (
        has_vector_range
        or (match is not None and looks_like_math_or_measurement_range(block.text, match))
        or block_looks_like_math_or_measurement_range_context(block)
    ):
        return "math"
    return "body"


def unlinked_citation_candidate_numbers(block: Block) -> list[int]:
    match = CITATION_RANGE_LIST_RE.search(block.text)
    if match is not None:
        return [int(value) for value in re.findall(r"\d+", match.group(0))]
    for sup_match in SUP_NUMERIC_RANGE_RE.finditer(block.raw):
        raw = sup_match.group(0)
        if "z2m-ref-link" not in raw and "z2m-footnote-ref" not in raw:
            if sup_numeric_range_is_project_or_grant_number(block, sup_match):
                continue
            if sup_numeric_range_is_measurement_value(block, sup_match):
                continue
            if sup_numeric_range_is_decimal_comma_value(block, sup_match):
                continue
            if sup_numeric_range_is_count_or_option_value(block, sup_match):
                continue
            if sup_numeric_range_is_low_number_table_layout_marker(block, sup_match):
                continue
            return [int(value) for value in re.findall(r"\d+", sup_match.group("body"))]
    for tagged_match in TAGGED_CITATION_RANGE_LIST_RE.finditer(block.raw):
        body = tagged_match.group("body")
        if "<" not in body or "z2m-ref-link" in body:
            continue
        visible = strip_tags(body)
        if CITATION_RANGE_LIST_RE.fullmatch(f"[{visible}]") is not None:
            return [int(value) for value in re.findall(r"\d+", visible)]
    return []
