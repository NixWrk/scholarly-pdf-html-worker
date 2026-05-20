#!/usr/bin/env python
"""Record compact EN polish quality history for a completed run directory."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


SEVERITY_WEIGHT = {
    "error": 10.0,
    "warning": 3.0,
    "info": 0.5,
}

LINK_METRIC_WEIGHT = {
    "broken_internal_links": 4.0,
    "internal_page_anchor_links": 1.0,
    "external_page_query_links": 1.0,
    "table_units_with_section_ids": 5.0,
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_path(run_dir: Path, name: str) -> Path:
    return run_dir / name


def _severity_counts(defects: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for defect in defects:
        severity = str(defect.get("severity") or "info")
        if severity not in counts:
            counts[severity] = 0
        counts[severity] += 1
    return counts


def _assessment_articles(assessment: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not assessment:
        return {}
    return {
        str(article.get("article") or ""): article
        for article in assessment.get("articles", [])
        if article.get("article")
    }


def _audit_articles(audit: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not audit:
        return {}
    return {
        str(article.get("article") or ""): article
        for article in audit.get("articles", [])
        if article.get("article")
    }


def _link_metrics(article: dict[str, Any], audit_article: dict[str, Any] | None) -> dict[str, int]:
    href_counts = article.get("href_counts") if isinstance(article.get("href_counts"), dict) else {}
    summary = audit_article.get("summary") if audit_article and isinstance(audit_article.get("summary"), dict) else {}
    return {
        "broken_internal_links": int(href_counts.get("broken_internal_links") or 0),
        "internal_page_anchor_links": int(href_counts.get("internal_page_anchor_links") or 0),
        "external_page_query_links": int(href_counts.get("external_page_query_links") or 0),
        "page_links": int(href_counts.get("page_links") or summary.get("polish_page_links") or 0),
        "ref_links": int(href_counts.get("ref_links") or summary.get("polish_ref_links") or 0),
        "fig_links": int(href_counts.get("fig_links") or summary.get("polish_fig_links") or 0),
        "table_links": int(href_counts.get("table_links") or summary.get("polish_table_links") or 0),
        "table_units_with_section_ids": int(article.get("table_units_with_section_ids") or 0),
        "missing_warning_count": int(article.get("missing_warning_count") or 0),
        "missing_local_images": int(summary.get("polish_missing_local_images") or 0),
    }


def _article_score(defects: list[dict[str, Any]], metrics: dict[str, int]) -> float:
    severity_counts = _severity_counts(defects)
    score = sum(SEVERITY_WEIGHT.get(severity, 0.5) * count for severity, count in severity_counts.items())
    score += len({str(defect.get("id") or "") for defect in defects if defect.get("id")}) * 0.25
    for metric, weight in LINK_METRIC_WEIGHT.items():
        score += metrics.get(metric, 0) * weight
    return round(score, 2)


def build_entry(
    *,
    run_dir: Path,
    run_id: str,
    assessment: dict[str, Any] | None,
    audit: dict[str, Any] | None,
) -> dict[str, Any]:
    assessment_by_article = _assessment_articles(assessment)
    audit_by_article = _audit_articles(audit)
    article_names = sorted(set(assessment_by_article) | set(audit_by_article))
    articles: dict[str, dict[str, Any]] = {}
    totals = {
        "score": 0.0,
        "defects": 0,
        "errors": 0,
        "warnings": 0,
        "infos": 0,
        "broken_internal_links": 0,
        "internal_page_anchor_links": 0,
        "external_page_query_links": 0,
        "table_units_with_section_ids": 0,
        "missing_warning_count": 0,
    }

    for article_name in article_names:
        assessment_article = assessment_by_article.get(article_name, {})
        audit_article = audit_by_article.get(article_name, {})
        defects = list(audit_article.get("defects_found") or [])
        severities = _severity_counts(defects)
        metrics = _link_metrics(assessment_article, audit_article)
        defect_ids: dict[str, int] = {}
        for defect in defects:
            defect_id = str(defect.get("id") or "unknown")
            defect_ids[defect_id] = defect_ids.get(defect_id, 0) + 1
        score = _article_score(defects, metrics)
        record = {
            "article": article_name,
            "score": score,
            "defects": len(defects),
            "errors": severities.get("error", 0),
            "warnings": severities.get("warning", 0),
            "infos": severities.get("info", 0),
            "unique_defect_ids": len(defect_ids),
            "defect_ids": dict(sorted(defect_ids.items())),
            **metrics,
        }
        articles[article_name] = record
        totals["score"] = round(totals["score"] + score, 2)
        totals["defects"] += record["defects"]
        totals["errors"] += record["errors"]
        totals["warnings"] += record["warnings"]
        totals["infos"] += record["infos"]
        for metric in (
            "broken_internal_links",
            "internal_page_anchor_links",
            "external_page_query_links",
            "table_units_with_section_ids",
            "missing_warning_count",
        ):
            totals[metric] += record[metric]

    ranking = sorted(articles.values(), key=lambda item: (-item["score"], item["article"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "article_count": len(articles),
        "totals": totals,
        "audit_defect_counts": (audit or {}).get("corpus_summary", {}).get("defect_counts", {}),
        "articles": articles,
        "ranking": ranking,
    }


def _read_last_history_entry(history_path: Path) -> dict[str, Any] | None:
    if not history_path.is_file():
        return None
    last_line = ""
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last_line = line
    return json.loads(last_line) if last_line else None


def compare_entries(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if previous is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "previous_run_id": None,
            "current_run_id": current["run_id"],
            "status": "no_previous_entry",
        }
    previous_articles = previous.get("articles", {})
    current_articles = current.get("articles", {})
    all_articles = sorted(set(previous_articles) | set(current_articles))
    article_deltas: list[dict[str, Any]] = []
    for article in all_articles:
        old = previous_articles.get(article, {})
        new = current_articles.get(article, {})
        delta = {
            "article": article,
            "score_delta": round(float(new.get("score", 0)) - float(old.get("score", 0)), 2),
            "defects_delta": int(new.get("defects", 0)) - int(old.get("defects", 0)),
            "errors_delta": int(new.get("errors", 0)) - int(old.get("errors", 0)),
            "warnings_delta": int(new.get("warnings", 0)) - int(old.get("warnings", 0)),
            "broken_internal_links_delta": int(new.get("broken_internal_links", 0))
            - int(old.get("broken_internal_links", 0)),
            "internal_page_anchor_links_delta": int(new.get("internal_page_anchor_links", 0))
            - int(old.get("internal_page_anchor_links", 0)),
            "external_page_query_links_delta": int(new.get("external_page_query_links", 0))
            - int(old.get("external_page_query_links", 0)),
            "old_score": old.get("score", 0),
            "new_score": new.get("score", 0),
        }
        article_deltas.append(delta)

    totals_delta = {
        key: round(float(current.get("totals", {}).get(key, 0)) - float(previous.get("totals", {}).get(key, 0)), 2)
        for key in sorted(set(previous.get("totals", {})) | set(current.get("totals", {})))
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "previous_run_id": previous.get("run_id"),
        "current_run_id": current["run_id"],
        "status": "ok",
        "totals_delta": totals_delta,
        "regressions": [item for item in article_deltas if item["score_delta"] > 0],
        "improvements": [item for item in article_deltas if item["score_delta"] < 0],
        "unchanged": [item for item in article_deltas if item["score_delta"] == 0],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-id", help="Stable label for this quality run.")
    parser.add_argument("--assessment", type=Path)
    parser.add_argument("--audit-report", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--previous-entry", type=Path)
    parser.add_argument("--out-entry", type=Path)
    parser.add_argument("--out-compare", type=Path)
    parser.add_argument("--out-ranking", type=Path)
    parser.add_argument("--no-append", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve(strict=False)
    assessment_path = args.assessment or _default_path(run_dir, "assessment.json")
    audit_path = args.audit_report or _default_path(run_dir, "audit_full_checks.json")
    history_path = args.history or _default_path(run_dir, "quality_history.jsonl")
    out_entry = args.out_entry or _default_path(run_dir, "quality_history_entry.json")
    out_compare = args.out_compare or _default_path(run_dir, "quality_compare.json")
    out_ranking = args.out_ranking or _default_path(run_dir, "brokenness_ranking.json")

    assessment = _load_json(assessment_path) if assessment_path.is_file() else None
    audit = _load_json(audit_path) if audit_path.is_file() else None
    if assessment is None and audit is None:
        raise SystemExit("No assessment or audit report found.")

    previous = _load_json(args.previous_entry) if args.previous_entry else _read_last_history_entry(history_path)
    entry = build_entry(
        run_dir=run_dir,
        run_id=args.run_id or run_dir.name,
        assessment=assessment,
        audit=audit,
    )
    comparison = compare_entries(previous, entry)

    out_entry.parent.mkdir(parents=True, exist_ok=True)
    out_entry.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_compare.parent.mkdir(parents=True, exist_ok=True)
    out_compare.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_ranking.parent.mkdir(parents=True, exist_ok=True)
    out_ranking.write_text(json.dumps(entry["ranking"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.no_append:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    totals = entry["totals"]
    print(
        "Quality history: "
        f"run={entry['run_id']} articles={entry['article_count']} "
        f"score={totals['score']} defects={totals['defects']} "
        f"errors={totals['errors']} warnings={totals['warnings']}"
    )
    if comparison["status"] == "ok":
        delta = comparison["totals_delta"]
        print(
            "Compared with previous: "
            f"score_delta={delta.get('score', 0)} "
            f"defects_delta={delta.get('defects', 0)} "
            f"regressions={len(comparison['regressions'])} "
            f"improvements={len(comparison['improvements'])}"
        )
    else:
        print("Compared with previous: no previous entry")
    print(f"Wrote {out_entry}")
    print(f"Wrote {out_compare}")
    print(f"Wrote {out_ranking}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
