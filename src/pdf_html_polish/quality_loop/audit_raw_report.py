from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from pdf_html_polish.html_stages import RAW_STAGE_NAME
from pdf_html_polish.quality_loop.audit_raw_analysis import analyze_raw_file


def find_raw_stage_files(roots: Iterable[Path], *, stage_name: str = RAW_STAGE_NAME) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if root.is_file() and root.name == stage_name:
            found.append(root)
        elif root.exists():
            found.extend(root.rglob(stage_name))
    return sorted({path.resolve(strict=False) for path in found})


def add_raw_corpus_hit_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        seen = {defect["id"] for defect in article["defects_found"]}
        for defect_id in seen:
            counts[defect_id] = counts.get(defect_id, 0) + 1
    for article in articles:
        for defect in article["defects_found"]:
            defect["same_pattern_hits_across_corpus"] = counts.get(defect["id"], 0)
    return counts


def build_raw_report(
    roots: list[Path],
    *,
    stage_name: str = RAW_STAGE_NAME,
    analyze_file: Callable[[Path], dict[str, Any]] = analyze_raw_file,
) -> dict[str, Any]:
    files = find_raw_stage_files(roots, stage_name=stage_name)
    articles = [analyze_file(path) for path in files]
    defect_counts = add_raw_corpus_hit_counts(articles)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage_name,
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


def raw_report_summary_lines(report: dict[str, Any]) -> list[str]:
    lines = [f"EN raw audit: {report['article_count']} artifact(s)"]
    totals = report["corpus_summary"]["totals"]
    lines.append(
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
        lines.append("Defects by check: " + ", ".join(f"{key}={value}" for key, value in sorted(defect_counts.items())))
    else:
        lines.append("Defects by check: none")
    for article in report["articles"]:
        summary = article["en_raw_summary"]
        lines.append(
            f"- {article['article']}: "
            f"bytes={summary['bytes']} "
            f"img={summary['images'].get('img_tags', 0)} "
            f"fig={summary['figure_labels']} "
            f"tables={summary['table_labels']} "
            f"headers={summary['page_headers']} "
            f"defects={len(article['defects_found'])}"
        )
    return lines


def print_raw_report_summary(report: dict[str, Any]) -> None:
    for line in raw_report_summary_lines(report):
        print(line)
