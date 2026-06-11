from __future__ import annotations

import re

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
    "AUTHOR_EXISTING_SUP_SPACE_PATTERN",
    "AUTHOR_MARKER_NUMBER_RUN_PATTERN",
    "AUTHOR_MARKER_OCR_SYMBOL_PATTERN",
    "SUPERSCRIPT_DIGIT_TRANSLATION",
    "normalize_front_matter_marker_numbers",
    "repair_affiliation_label_ocr_body",
    "repair_author_marker_ocr_body",
]
