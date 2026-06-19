from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
from typing import Any

from pdf_html_polish.html_stages import article_name_from_html_stage
from pdf_html_polish.quality_loop.audit_raw_blocks import (
    Defect,
    first_match_defect,
    parse_blocks,
    read_utf8,
    strip_tags,
)
from pdf_html_polish.quality_loop.audit_raw_checks import (
    FIGURE_CAPTION_RE,
    all_caps_heading_defects,
    anchor_summary,
    caption_without_image_defects,
    heading_ocr_defects,
    major_tag_defects,
    mojibake_micro_count,
    references_summary,
)
from pdf_html_polish.quality_loop.audit_raw_images import image_summary as raw_image_summary


FIGURE_LABEL_RE = re.compile(r"\b(?:FIGURE|Figure|Fig\.)\s+\d+[A-Za-z]?\b")
TABLE_LABEL_RE = re.compile(r"\b(?:TABLE|Table)\s+(?:[IVXLCDM]+|\d+)\b")
PAGE_HEADER_RE = re.compile(r"\bPage\s+\d+\s+of\s+\d+\b", re.IGNORECASE)
RAW_SENTINEL_RE = re.compile(r"@@Z2M|<z2m\b|Z2M(?:_[ATF])?", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s<>'\"]+", re.IGNORECASE)
DUPLICATED_DOI_FRAGMENT_RE = re.compile(
    r"\b(10\.\d{4,9}/[^\s<>'\"]+)\s+\1\b",
    re.IGNORECASE,
)
BROKEN_HYPHEN_RE = re.compile(r"\b[A-Za-z]{2,}-\s+[a-z]{2,}\b")
GLUED_ROMAN_SUFFIX_RE = re.compile(
    r"\b[A-Za-z]{4,}(?:ii|iii|iv|vi|vii|viii|xii|xiii|xiv|xv|ingv)\b",
    re.IGNORECASE,
)

MICRO_CHARS = "\u00b5\u03bc"
MOJIBAKE_MICRO = "\u0412\u00b5"
MICRO_TOKEN_RE = re.compile(rf"(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})")
FORMULA_UNIT_FRAGMENT_RE = re.compile(
    rf"(?:\d+\s*(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})\s*m\b|"
    rf"(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})\s+m\b|"
    rf"\bm\s+(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})\b)",
    re.IGNORECASE,
)


def analyze_raw_file(path: Path) -> dict[str, Any]:
    data, text, read_defect = read_utf8(path)
    blocks = parse_blocks(text) if text else []
    plain_text = strip_tags(text) if text else ""
    image_summary, image_defect = raw_image_summary(path, text) if text else ({}, None)

    defects: list[Defect] = []
    if read_defect is not None:
        defects.append(read_defect)
    defects.extend(major_tag_defects(text))
    if image_defect is not None:
        defects.append(image_defect)

    defects.extend(caption_without_image_defects(blocks))
    defects.extend(heading_ocr_defects(blocks))

    for defect in [
        first_match_defect(
            defect_id="R07",
            check="Detect page headers/footers like Page X of Y",
            severity="info",
            pattern=PAGE_HEADER_RE,
            text=plain_text,
            hypothesis="EN raw contains page headers that should be removed in EN polish.",
            proposed_fix_layer="EN polish",
            regression_test="Unit-test page header removal and re-run EN raw audit to keep the baseline visible.",
        ),
        first_match_defect(
            defect_id="R08",
            check="Detect glued roman/table footnote suffixes",
            severity="info",
            pattern=GLUED_ROMAN_SUFFIX_RE,
            text=plain_text,
            hypothesis="OCR or table extraction glued a roman footnote suffix to a word.",
            proposed_fix_layer="EN polish, only after checking same-pattern corpus hits",
            regression_test="Add focused normalization cases for the systemic suffix pattern.",
        ),
        first_match_defect(
            defect_id="R09",
            check="Detect DOI corruption and duplicated DOI fragments",
            severity="info",
            pattern=DUPLICATED_DOI_FRAGMENT_RE,
            text=plain_text,
            hypothesis="Raw extraction duplicated a DOI token.",
            proposed_fix_layer="Marker/source classification if raw-only; EN polish if introduced later",
            regression_test="Compare DOI counts before and after polish for affected articles.",
        ),
        first_match_defect(
            defect_id="R11",
            check="Detect broken hyphenated line joins in prose/table cells",
            severity="info",
            pattern=BROKEN_HYPHEN_RE,
            text=plain_text,
            hypothesis="Layout extraction preserved a hyphenated line break or table split.",
            proposed_fix_layer="EN polish after corpus review",
            regression_test="Add text-normalization test for the shared hyphenation shape.",
        ),
        first_match_defect(
            defect_id="R12",
            check="Detect formula/unit splits around micro units",
            severity="info",
            pattern=FORMULA_UNIT_FRAGMENT_RE,
            text=plain_text,
            hypothesis="Formula or OCR extraction split micro-unit text before translation.",
            proposed_fix_layer="EN polish or formula protection",
            regression_test="Add formula/unit protection test and re-run audit over all EN raw files.",
        ),
        first_match_defect(
            defect_id="R14",
            check="Detect raw pipeline sentinels",
            severity="error",
            pattern=RAW_SENTINEL_RE,
            text=text,
            hypothesis="Pipeline sentinels leaked into EN raw, which should never happen.",
            proposed_fix_layer="pipeline staging or sanitizer",
            regression_test="Run EN raw audit and fail on R14.",
        ),
    ]:
        if defect is not None:
            defects.append(defect)

    defects.extend(all_caps_heading_defects(blocks))

    figure_mentions = list(FIGURE_LABEL_RE.finditer(plain_text))
    figure_captions = [block for block in blocks if FIGURE_CAPTION_RE.search(block.text)]
    table_labels = list(TABLE_LABEL_RE.finditer(plain_text))
    doi_tokens = list(DOI_RE.finditer(plain_text))

    summary = {
        "bytes": len(data),
        "blocks": len(blocks),
        "images": image_summary,
        "figure_labels": len(figure_mentions),
        "figure_caption_blocks": len(figure_captions),
        "table_labels": len(table_labels),
        "page_headers": len(PAGE_HEADER_RE.findall(plain_text)),
        "raw_sentinels": len(RAW_SENTINEL_RE.findall(text)),
        "anchors": anchor_summary(text),
        "references": references_summary(plain_text),
        "doi_tokens": len(doi_tokens),
        "duplicated_doi_fragments": len(DUPLICATED_DOI_FRAGMENT_RE.findall(plain_text)),
        "glued_roman_suffixes": len(GLUED_ROMAN_SUFFIX_RE.findall(plain_text)),
        "broken_hyphen_joins": len(BROKEN_HYPHEN_RE.findall(plain_text)),
        "formula_unit_fragments": len(FORMULA_UNIT_FRAGMENT_RE.findall(plain_text)),
        "micro_tokens": len(MICRO_TOKEN_RE.findall(plain_text)),
        "mojibake_micro_tokens": mojibake_micro_count(plain_text),
    }

    return {
        "article": article_name_from_html_stage(path),
        "stage_path": str(path),
        "run_log": str(path.with_suffix(".log")) if path.with_suffix(".log").exists() else None,
        "en_raw_summary": summary,
        "defects_found": [asdict(defect) for defect in defects],
    }
