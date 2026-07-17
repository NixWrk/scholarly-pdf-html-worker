"""Corpus report assembly helpers for audit scripts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pdf_html_polish.atomic_io import write_json_atomic
from .run_utils import json_object


def find_stage_pairs(
    roots: Iterable[Path],
    *,
    raw_stage: str,
    polish_stage: str,
) -> list[tuple[Path, Path]]:
    pairs: set[tuple[Path, Path]] = set()
    for root in roots:
        candidates: list[Path] = []
        if root.is_file():
            if root.name == polish_stage:
                candidates.append(root)
            elif root.name == raw_stage and (root.parent / polish_stage).is_file():
                candidates.append(root.parent / polish_stage)
        elif root.exists():
            candidates.extend(root.rglob(polish_stage))
        for polish_path in candidates:
            raw_path = polish_path.parent / raw_stage
            if raw_path.is_file():
                pairs.add((raw_path.resolve(strict=False), polish_path.resolve(strict=False)))
    return sorted(pairs, key=lambda pair: str(pair[1]))


def defect_quality_counted(defect: dict[str, Any]) -> bool:
    extra = json_object(defect.get("extra"))
    return extra.get("quality_counted") is not False


def observed_corpus_hit_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        seen = {defect["id"] for defect in article["defects_found"]}
        for defect_id in seen:
            counts[defect_id] = counts.get(defect_id, 0) + 1
    return counts


def add_corpus_hit_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        seen = {
            defect["id"]
            for defect in article["defects_found"]
            if defect_quality_counted(defect)
        }
        for defect_id in seen:
            counts[defect_id] = counts.get(defect_id, 0) + 1
    observed_counts = observed_corpus_hit_counts(articles)
    for article in articles:
        for defect in article["defects_found"]:
            defect_id = defect["id"]
            defect["same_pattern_hits_across_corpus"] = counts.get(defect_id, 0)
            defect["same_pattern_observed_hits_across_corpus"] = observed_counts.get(defect_id, 0)
    return counts


def non_quality_corpus_hit_counts(
    observed_counts: dict[str, int],
    quality_counts: dict[str, int],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for defect_id, observed_count in observed_counts.items():
        non_quality_count = observed_count - quality_counts.get(defect_id, 0)
        if non_quality_count > 0:
            counts[defect_id] = non_quality_count
    return counts


def corpus_totals(articles: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "raw_img_tags": sum(article["summary"]["raw_img_tags"] for article in articles),
        "polish_img_tags": sum(article["summary"]["polish_img_tags"] for article in articles),
        "polish_ref_links": sum(article["summary"]["polish_ref_links"] for article in articles),
        "polish_fig_links": sum(article["summary"]["polish_fig_links"] for article in articles),
        "polish_table_links": sum(article["summary"]["polish_table_links"] for article in articles),
        "polish_page_links": sum(article["summary"]["polish_page_links"] for article in articles),
        "polish_replacement_chars": sum(article["summary"]["polish_replacement_chars"] for article in articles),
        "polish_missing_local_images": sum(article["summary"]["polish_missing_local_images"] for article in articles),
        "source_pdf_present": sum(1 for article in articles if article["summary"]["source_pdf_present"]),
        "pdf_text_chars": sum(article["summary"]["pdf_text_chars"] for article in articles),
    }


def assemble_report(
    roots: list[Path],
    articles: list[dict[str, Any]],
    defect_counts: dict[str, int],
    *,
    raw_stage: str,
    polish_stage: str,
    audit_status: str,
    total_pair_count: int,
) -> dict[str, Any]:
    observed_counts = observed_corpus_hit_counts(articles)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": f"{raw_stage} -> {polish_stage}",
        "roots": [str(root) for root in roots],
        "audit_status": audit_status,
        "processed_pair_count": len(articles),
        "total_pair_count": total_pair_count,
        "article_count": len(articles),
        "corpus_summary": {
            "defect_counts": defect_counts,
            "observed_defect_counts": observed_counts,
            "non_quality_defect_counts": non_quality_corpus_hit_counts(
                observed_counts,
                defect_counts,
            ),
            "totals": corpus_totals(articles),
        },
        "articles": articles,
    }


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    write_json_atomic(path, report)
