#!/usr/bin/env python
"""Audit `01.en.raw.html` stage artifacts without running the pipeline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.html_stages import RAW_STAGE_NAME  # noqa: E402
from pdf_html_polish.quality_loop.audit_raw_analysis import analyze_raw_file as _analyze_raw_file  # noqa: E402


STAGE_NAME = RAW_STAGE_NAME


def analyze_file(path: Path) -> dict[str, Any]:
    return _analyze_raw_file(path)


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
