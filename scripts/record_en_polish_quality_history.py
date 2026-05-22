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
    "polish_replacement_chars": 1.0,
}

DERIVED_METRIC_PAIRS = {
    "block_delta": ("raw_blocks", "polish_blocks"),
    "image_delta": ("raw_img_tags", "polish_img_tags"),
    "ref_link_delta": ("raw_ref_links", "ref_links"),
    "fig_link_delta": ("raw_fig_links", "fig_links"),
    "table_link_delta": ("raw_table_links", "table_links"),
    "page_link_delta": ("raw_page_links", "page_links"),
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


def _numeric_value(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    return None


def _copy_numeric_values(source: dict[str, Any]) -> dict[str, int | float]:
    metrics: dict[str, int | float] = {}
    for key, value in source.items():
        numeric = _numeric_value(value)
        if numeric is not None:
            metrics[key] = numeric
    return metrics


def _article_labels(article: dict[str, Any], audit_article: dict[str, Any] | None) -> dict[str, str]:
    summary = audit_article.get("summary") if audit_article and isinstance(audit_article.get("summary"), dict) else {}
    return {
        "profile_style": str(article.get("profile_style") or ""),
        "profile_confidence": str(article.get("profile_confidence") or ""),
        "profile_status": str(article.get("profile_status") or ""),
        "pdf_text_status": str(summary.get("pdf_text_status") or ""),
        "source_pdf_origin": str(summary.get("source_pdf_origin") or ""),
    }


def _article_metrics(article: dict[str, Any], audit_article: dict[str, Any] | None) -> dict[str, int | float]:
    href_counts = article.get("href_counts") if isinstance(article.get("href_counts"), dict) else {}
    summary = audit_article.get("summary") if audit_article and isinstance(audit_article.get("summary"), dict) else {}
    metrics = _copy_numeric_values(summary)
    metrics.update(
        {
            "broken_internal_links": int(href_counts.get("broken_internal_links") or 0),
            "internal_page_anchor_links": int(href_counts.get("internal_page_anchor_links") or 0),
            "external_page_query_links": int(href_counts.get("external_page_query_links") or 0),
            "page_links": int(href_counts.get("page_links") or summary.get("polish_page_links") or 0),
            "ref_links": int(href_counts.get("ref_links") or summary.get("polish_ref_links") or 0),
            "fig_links": int(href_counts.get("fig_links") or summary.get("polish_fig_links") or 0),
            "table_links": int(href_counts.get("table_links") or summary.get("polish_table_links") or 0),
            "table_units_with_section_ids": int(article.get("table_units_with_section_ids") or 0),
            "sup_ref_links": int(article.get("sup_ref_links") or 0),
            "bracket_ref_links": int(article.get("bracket_ref_links") or 0),
            "mixed_citation_style": int(bool(article.get("mixed_citation_style"))),
            "missing_warning_count": int(article.get("missing_warning_count") or 0),
            "missing_local_images": int(summary.get("polish_missing_local_images") or 0),
        }
    )
    aliases = {
        "raw_ref_links": "raw_ref_links",
        "polish_ref_links": "ref_links",
        "raw_fig_links": "raw_fig_links",
        "polish_fig_links": "fig_links",
        "raw_table_links": "raw_table_links",
        "polish_table_links": "table_links",
        "raw_page_links": "raw_page_links",
        "polish_page_links": "page_links",
    }
    for summary_key, metric_key in aliases.items():
        if summary_key in summary and metric_key not in metrics:
            numeric = _numeric_value(summary.get(summary_key))
            if numeric is not None:
                metrics[metric_key] = numeric
    for derived_key, (before_key, after_key) in DERIVED_METRIC_PAIRS.items():
        if before_key in metrics or after_key in metrics:
            metrics[derived_key] = metrics.get(after_key, 0) - metrics.get(before_key, 0)
    return dict(sorted(metrics.items()))


def _article_score(defects: list[dict[str, Any]], metrics: dict[str, int | float]) -> float:
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
    totals: dict[str, int | float] = {
        "score": 0.0,
        "defects": 0,
        "errors": 0,
        "warnings": 0,
        "infos": 0,
    }

    for article_name in article_names:
        assessment_article = assessment_by_article.get(article_name, {})
        audit_article = audit_by_article.get(article_name, {})
        defects = list(audit_article.get("defects_found") or [])
        severities = _severity_counts(defects)
        metrics = _article_metrics(assessment_article, audit_article)
        labels = _article_labels(assessment_article, audit_article)
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
            "labels": labels,
            "metrics": metrics,
            **metrics,
        }
        articles[article_name] = record
        totals["score"] = round(totals["score"] + score, 2)
        totals["defects"] += record["defects"]
        totals["errors"] += record["errors"]
        totals["warnings"] += record["warnings"]
        totals["infos"] += record["infos"]
        for metric, value in metrics.items():
            totals[metric] = round(float(totals.get(metric, 0)) + float(value), 2)

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


def _record_metrics(record: dict[str, Any]) -> dict[str, int | float]:
    metrics = record.get("metrics")
    if isinstance(metrics, dict):
        return {
            str(key): value
            for key, value in metrics.items()
            if _numeric_value(value) is not None
        }
    excluded = {
        "article",
        "score",
        "defects",
        "errors",
        "warnings",
        "infos",
        "unique_defect_ids",
        "defect_ids",
        "labels",
    }
    return {
        key: value
        for key, value in record.items()
        if key not in excluded and _numeric_value(value) is not None
    }


def _record_total_metrics(record: dict[str, Any]) -> dict[str, int | float]:
    metrics = {
        key: value
        for key in ("score", "defects", "errors", "warnings", "infos")
        if (value := _numeric_value(record.get(key))) is not None
    }
    metrics.update(_record_metrics(record))
    return metrics


def _sum_record_totals(records: list[dict[str, Any]]) -> dict[str, int | float]:
    totals: dict[str, int | float] = {}
    for record in records:
        for key, value in _record_total_metrics(record).items():
            totals[key] = round(float(totals.get(key, 0)) + float(value), 2)
    return dict(sorted(totals.items()))


def _subtract_totals(
    current: dict[str, int | float],
    previous: dict[str, int | float],
) -> dict[str, int | float]:
    return {
        key: round(float(current.get(key, 0)) - float(previous.get(key, 0)), 2)
        for key in sorted(set(previous) | set(current))
    }


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
    comparable_article_deltas: list[dict[str, Any]] = []
    new_article_deltas: list[dict[str, Any]] = []
    removed_article_deltas: list[dict[str, Any]] = []
    for article in all_articles:
        has_old = article in previous_articles
        has_new = article in current_articles
        old = previous_articles.get(article, {})
        new = current_articles.get(article, {})
        old_metrics = _record_metrics(old)
        new_metrics = _record_metrics(new)
        metric_deltas = {
            key: round(float(new_metrics.get(key, 0)) - float(old_metrics.get(key, 0)), 2)
            for key in sorted(set(old_metrics) | set(new_metrics))
        }
        delta = {
            "article": article,
            "score_delta": round(float(new.get("score", 0)) - float(old.get("score", 0)), 2),
            "defects_delta": int(new.get("defects", 0)) - int(old.get("defects", 0)),
            "errors_delta": int(new.get("errors", 0)) - int(old.get("errors", 0)),
            "warnings_delta": int(new.get("warnings", 0)) - int(old.get("warnings", 0)),
            "metrics_delta": metric_deltas,
            "old_score": old.get("score", 0),
            "new_score": new.get("score", 0),
            "comparison_state": "comparable" if has_old and has_new else "new" if has_new else "removed",
        }
        for key, value in metric_deltas.items():
            delta[f"{key}_delta"] = value
        article_deltas.append(delta)
        if has_old and has_new:
            comparable_article_deltas.append(delta)
        elif has_new:
            new_article_deltas.append(delta)
        else:
            removed_article_deltas.append(delta)

    totals_delta = {
        key: round(float(current.get("totals", {}).get(key, 0)) - float(previous.get("totals", {}).get(key, 0)), 2)
        for key in sorted(set(previous.get("totals", {})) | set(current.get("totals", {})))
    }
    comparable_names = sorted(set(previous_articles) & set(current_articles))
    comparable_previous_totals = _sum_record_totals([previous_articles[name] for name in comparable_names])
    comparable_current_totals = _sum_record_totals([current_articles[name] for name in comparable_names])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "previous_run_id": previous.get("run_id"),
        "current_run_id": current["run_id"],
        "status": "ok",
        "totals_delta": totals_delta,
        "comparable_totals_delta": _subtract_totals(comparable_current_totals, comparable_previous_totals),
        "new_articles": new_article_deltas,
        "removed_articles": removed_article_deltas,
        "new_article_count": len(new_article_deltas),
        "removed_article_count": len(removed_article_deltas),
        "regressions": [item for item in comparable_article_deltas if item["score_delta"] > 0],
        "improvements": [item for item in comparable_article_deltas if item["score_delta"] < 0],
        "unchanged": [item for item in comparable_article_deltas if item["score_delta"] == 0],
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
