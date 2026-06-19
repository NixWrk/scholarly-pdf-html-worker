#!/usr/bin/env python
"""Audit `01.en.raw.html` stage artifacts without running the pipeline."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.html_stages import RAW_STAGE_NAME, article_name_from_html_stage  # noqa: E402
from pdf_html_polish.quality_loop.audit_raw_blocks import (  # noqa: E402
    Block,
    BlockParser,
    Defect,
    first_match_defect as _first_match_defect,
    normalize_ws as _normalize_ws,
    parse_blocks as _parse_blocks,
    read_utf8 as _read_utf8,
    strip_tags as _strip_tags,
)
from pdf_html_polish.quality_loop.audit_raw_checks import (  # noqa: E402
    FIGURE_CAPTION_RE,
    all_caps_heading_defects as _all_caps_heading_defects,
    anchor_summary as _anchor_summary,
    caption_without_image_defects as _caption_without_image_defects,
    heading_ocr_defects as _heading_ocr_defects,
    major_tag_defects as _major_tag_defects,
    mojibake_micro_count as _mojibake_micro_count,
    references_summary as _references_summary,
)
from pdf_html_polish.quality_loop.audit_raw_images import (  # noqa: E402
    image_refs as _image_refs,
    image_summary as _image_summary,
    resolve_image_ref as _resolve_image_ref,
    sidecar_images as _sidecar_images,
)


STAGE_NAME = RAW_STAGE_NAME

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


def analyze_file(path: Path) -> dict[str, Any]:
    data, text, read_defect = _read_utf8(path)
    blocks = _parse_blocks(text) if text else []
    plain_text = _strip_tags(text) if text else ""
    image_summary, image_defect = _image_summary(path, text) if text else ({}, None)

    defects: list[Defect] = []
    if read_defect is not None:
        defects.append(read_defect)
    defects.extend(_major_tag_defects(text))
    if image_defect is not None:
        defects.append(image_defect)

    defects.extend(_caption_without_image_defects(blocks))
    defects.extend(_heading_ocr_defects(blocks))

    for defect in [
        _first_match_defect(
            defect_id="R07",
            check="Detect page headers/footers like Page X of Y",
            severity="info",
            pattern=PAGE_HEADER_RE,
            text=plain_text,
            hypothesis="EN raw contains page headers that should be removed in EN polish.",
            proposed_fix_layer="EN polish",
            regression_test="Unit-test page header removal and re-run EN raw audit to keep the baseline visible.",
        ),
        _first_match_defect(
            defect_id="R08",
            check="Detect glued roman/table footnote suffixes",
            severity="info",
            pattern=GLUED_ROMAN_SUFFIX_RE,
            text=plain_text,
            hypothesis="OCR or table extraction glued a roman footnote suffix to a word.",
            proposed_fix_layer="EN polish, only after checking same-pattern corpus hits",
            regression_test="Add focused normalization cases for the systemic suffix pattern.",
        ),
        _first_match_defect(
            defect_id="R09",
            check="Detect DOI corruption and duplicated DOI fragments",
            severity="info",
            pattern=DUPLICATED_DOI_FRAGMENT_RE,
            text=plain_text,
            hypothesis="Raw extraction duplicated a DOI token.",
            proposed_fix_layer="Marker/source classification if raw-only; EN polish if introduced later",
            regression_test="Compare DOI counts before and after polish for affected articles.",
        ),
        _first_match_defect(
            defect_id="R11",
            check="Detect broken hyphenated line joins in prose/table cells",
            severity="info",
            pattern=BROKEN_HYPHEN_RE,
            text=plain_text,
            hypothesis="Layout extraction preserved a hyphenated line break or table split.",
            proposed_fix_layer="EN polish after corpus review",
            regression_test="Add text-normalization test for the shared hyphenation shape.",
        ),
        _first_match_defect(
            defect_id="R12",
            check="Detect formula/unit splits around micro units",
            severity="info",
            pattern=FORMULA_UNIT_FRAGMENT_RE,
            text=plain_text,
            hypothesis="Formula or OCR extraction split micro-unit text before translation.",
            proposed_fix_layer="EN polish or formula protection",
            regression_test="Add formula/unit protection test and re-run audit over all EN raw files.",
        ),
        _first_match_defect(
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

    defects.extend(_all_caps_heading_defects(blocks))

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
        "anchors": _anchor_summary(text),
        "references": _references_summary(plain_text),
        "doi_tokens": len(doi_tokens),
        "duplicated_doi_fragments": len(DUPLICATED_DOI_FRAGMENT_RE.findall(plain_text)),
        "glued_roman_suffixes": len(GLUED_ROMAN_SUFFIX_RE.findall(plain_text)),
        "broken_hyphen_joins": len(BROKEN_HYPHEN_RE.findall(plain_text)),
        "formula_unit_fragments": len(FORMULA_UNIT_FRAGMENT_RE.findall(plain_text)),
        "micro_tokens": len(MICRO_TOKEN_RE.findall(plain_text)),
        "mojibake_micro_tokens": _mojibake_micro_count(plain_text),
    }

    return {
        "article": article_name_from_html_stage(path),
        "stage_path": str(path),
        "run_log": str(path.with_suffix(".log")) if path.with_suffix(".log").exists() else None,
        "en_raw_summary": summary,
        "defects_found": [asdict(defect) for defect in defects],
    }


def find_stage_files(roots: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if root.is_file() and root.name == STAGE_NAME:
            found.append(root)
        elif root.exists():
            found.extend(root.rglob(STAGE_NAME))
    return sorted({path.resolve(strict=False) for path in found})


def _add_corpus_hit_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        seen = {defect["id"] for defect in article["defects_found"]}
        for defect_id in seen:
            counts[defect_id] = counts.get(defect_id, 0) + 1
    for article in articles:
        for defect in article["defects_found"]:
            defect["same_pattern_hits_across_corpus"] = counts.get(defect["id"], 0)
    return counts


def build_report(roots: list[Path]) -> dict[str, Any]:
    files = find_stage_files(roots)
    articles = [analyze_file(path) for path in files]
    defect_counts = _add_corpus_hit_counts(articles)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": STAGE_NAME,
        "roots": [str(root) for root in roots],
        "article_count": len(articles),
        "corpus_summary": {
            "defect_counts": defect_counts,
            "totals": {
                "bytes": sum(article["en_raw_summary"]["bytes"] for article in articles),
                "img_tags": sum(article["en_raw_summary"]["images"].get("img_tags", 0) for article in articles),
                "figure_labels": sum(article["en_raw_summary"]["figure_labels"] for article in articles),
                "table_labels": sum(article["en_raw_summary"]["table_labels"] for article in articles),
                "page_headers": sum(article["en_raw_summary"]["page_headers"] for article in articles),
                "raw_sentinels": sum(article["en_raw_summary"]["raw_sentinels"] for article in articles),
            },
        },
        "articles": articles,
    }


def _print_summary(report: dict[str, Any]) -> None:
    print(f"EN raw audit: {report['article_count']} artifact(s)")
    totals = report["corpus_summary"]["totals"]
    print(
        "Totals: "
        f"bytes={totals['bytes']} "
        f"img={totals['img_tags']} "
        f"figure_labels={totals['figure_labels']} "
        f"table_labels={totals['table_labels']} "
        f"page_headers={totals['page_headers']} "
        f"raw_sentinels={totals['raw_sentinels']}"
    )
    defect_counts = report["corpus_summary"]["defect_counts"]
    if defect_counts:
        print("Defects by check: " + ", ".join(f"{key}={value}" for key, value in sorted(defect_counts.items())))
    else:
        print("Defects by check: none")
    for article in report["articles"]:
        summary = article["en_raw_summary"]
        print(
            f"- {article['article']}: "
            f"bytes={summary['bytes']} "
            f"img={summary['images'].get('img_tags', 0)} "
            f"fig={summary['figure_labels']} "
            f"tables={summary['table_labels']} "
            f"headers={summary['page_headers']} "
            f"defects={len(article['defects_found'])}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="Root directories or direct 01.en.raw.html files to audit.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with status 1 when an error-severity defect is found.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.roots)
    _print_summary(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    if args.fail_on_error:
        for article in report["articles"]:
            if any(defect["severity"] == "error" for defect in article["defects_found"]):
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
