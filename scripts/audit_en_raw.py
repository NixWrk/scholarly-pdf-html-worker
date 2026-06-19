#!/usr/bin/env python
"""Audit `01.en.raw.html` stage artifacts without running the pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.html_stages import RAW_STAGE_NAME  # noqa: E402
from pdf_html_polish.quality_loop.audit_raw_analysis import analyze_raw_file as _analyze_raw_file  # noqa: E402
from pdf_html_polish.quality_loop.audit_raw_report import (  # noqa: E402
    add_raw_corpus_hit_counts as _add_corpus_hit_counts,
    build_raw_report as _build_raw_report,
    find_raw_stage_files as find_stage_files,
    print_raw_report_summary as _print_summary,
)


STAGE_NAME = RAW_STAGE_NAME


def analyze_file(path: Path) -> dict[str, Any]:
    return _analyze_raw_file(path)


def build_report(roots: list[Path]) -> dict[str, Any]:
    return _build_raw_report(roots, stage_name=STAGE_NAME, analyze_file=analyze_file)


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
