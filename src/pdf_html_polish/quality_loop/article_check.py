"""Targeted article checks for refactoring loops."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ALLOWED_GATE_FAILURES = {"article_review_stage", "mandatory_review_pending"}


def _load_json(path: Path, default: Any | None = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _article_id(article: dict[str, Any]) -> str:
    return str(article.get("article") or article.get("article_id") or article.get("source_article") or "")


def _defect_id(defect: dict[str, Any]) -> str:
    return str(defect.get("id") or defect.get("defect_id") or "unknown")


def _defect_quality_counted(defect: dict[str, Any]) -> bool:
    extra = defect.get("extra") if isinstance(defect.get("extra"), dict) else {}
    value = defect.get("quality_counted", extra.get("quality_counted"))
    return value is not False


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def audit_articles_by_id(audit_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for article in audit_report.get("articles") or []:
        if isinstance(article, dict):
            article_id = _article_id(article)
            if article_id:
                result[article_id] = article
    return result


def select_article_ids(
    *,
    run_dir: Path,
    audit_report: dict[str, Any],
    explicit_articles: Iterable[str] = (),
    defect_ids: Iterable[str] = (),
    from_pack: bool = False,
    limit: int | None = None,
) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()

    def add(article_id: str) -> None:
        article_id = str(article_id or "").strip()
        if article_id and article_id not in seen:
            seen.add(article_id)
            selected.append(article_id)

    for article_id in explicit_articles:
        add(article_id)

    if from_pack:
        pack = _load_json(run_dir / "llm_analysis_pack.json", default={})
        for item in pack.get("articles") or []:
            if isinstance(item, dict):
                add(str(item.get("article") or item.get("source_article") or ""))

    wanted_defects = {str(item) for item in defect_ids if str(item)}
    if wanted_defects:
        for article in audit_report.get("articles") or []:
            if not isinstance(article, dict):
                continue
            article_id = _article_id(article)
            if not article_id:
                continue
            for defect in article.get("defects_found") or []:
                if isinstance(defect, dict) and _defect_id(defect) in wanted_defects:
                    add(article_id)
                    break

    if limit is not None and limit > 0:
        return selected[:limit]
    return selected


def summarize_audit_articles(
    articles: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    observed_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    affected_articles: dict[str, set[str]] = {}
    quality_affected_articles: dict[str, set[str]] = {}

    for article in articles:
        article_id = _article_id(article)
        for defect in article.get("defects_found") or []:
            if not isinstance(defect, dict):
                continue
            defect_id = _defect_id(defect)
            observed_counts[defect_id] += 1
            severity_counts[str(defect.get("severity") or "unknown")] += 1
            affected_articles.setdefault(defect_id, set()).add(article_id)
            if _defect_quality_counted(defect):
                quality_counts[defect_id] += 1
                quality_affected_articles.setdefault(defect_id, set()).add(article_id)

    return {
        "observed_defect_counts": _counter_dict(observed_counts),
        "quality_defect_counts": _counter_dict(quality_counts),
        "severity_counts": _counter_dict(severity_counts),
        "observed_article_counts": {
            defect_id: len(articles_for_defect)
            for defect_id, articles_for_defect in sorted(affected_articles.items())
        },
        "quality_article_counts": {
            defect_id: len(articles_for_defect)
            for defect_id, articles_for_defect in sorted(quality_affected_articles.items())
        },
    }


def build_refactor_article_check(
    run_dir: Path,
    *,
    explicit_articles: Iterable[str] = (),
    defect_ids: Iterable[str] = (),
    from_pack: bool = False,
    limit: int | None = None,
    require_quality_zero: bool = True,
    require_hard_links_zero: bool = True,
    allowed_gate_failures: set[str] | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve(strict=False)
    audit_report = _load_json(run_dir / "audit_full_checks.json")
    history_entry = _load_json(run_dir / "quality_history_entry.json", default={})
    assessment = _load_json(run_dir / "assessment.json", default={})
    gate_report = _load_json(run_dir / "quality_gate_report.json", default={})

    articles_by_id = audit_articles_by_id(audit_report)
    selected_ids = select_article_ids(
        run_dir=run_dir,
        audit_report=audit_report,
        explicit_articles=explicit_articles,
        defect_ids=defect_ids,
        from_pack=from_pack,
        limit=limit,
    )
    if not selected_ids:
        selected_ids = sorted(articles_by_id)

    selected_articles = [articles_by_id[article_id] for article_id in selected_ids if article_id in articles_by_id]
    missing_selected = [article_id for article_id in selected_ids if article_id not in articles_by_id]

    corpus_summary = audit_report.get("corpus_summary") if isinstance(audit_report.get("corpus_summary"), dict) else {}
    quality_totals = history_entry.get("totals") if isinstance(history_entry.get("totals"), dict) else {}
    assessment_totals = assessment.get("totals") if isinstance(assessment.get("totals"), dict) else {}
    selected_summary = summarize_audit_articles(selected_articles)

    failures: list[dict[str, Any]] = []
    if missing_selected:
        failures.append({"kind": "missing_selected_articles", "articles": missing_selected})

    corpus_quality_counts = dict(corpus_summary.get("defect_counts") or {})
    if require_quality_zero:
        if int(quality_totals.get("defects") or 0) != 0:
            failures.append({"kind": "quality_total_defects", "observed": quality_totals.get("defects")})
        if int(quality_totals.get("errors") or 0) != 0:
            failures.append({"kind": "quality_total_errors", "observed": quality_totals.get("errors")})
        if int(quality_totals.get("warnings") or 0) != 0:
            failures.append({"kind": "quality_total_warnings", "observed": quality_totals.get("warnings")})
        if corpus_quality_counts:
            failures.append({"kind": "corpus_quality_defect_counts", "counts": corpus_quality_counts})
        if selected_summary["quality_defect_counts"]:
            failures.append(
                {
                    "kind": "selected_quality_defect_counts",
                    "counts": selected_summary["quality_defect_counts"],
                }
            )

    if require_hard_links_zero:
        hard_link_totals = {
            "broken_internal_links": quality_totals.get(
                "broken_internal_links", assessment_totals.get("broken_internal_links", 0)
            ),
            "external_page_query_links": quality_totals.get(
                "external_page_query_links", assessment_totals.get("external_page_query_links", 0)
            ),
        }
        for metric, value in hard_link_totals.items():
            if float(value or 0) != 0:
                failures.append({"kind": "hard_link_metric", "metric": metric, "observed": value})

    if gate_report:
        gate_status = gate_report.get("status")
        gate_failures = [
            str(item.get("kind") or "unknown")
            for item in gate_report.get("failures") or []
            if isinstance(item, dict)
        ]
        allowed = DEFAULT_ALLOWED_GATE_FAILURES if allowed_gate_failures is None else allowed_gate_failures
        unexpected = [] if "*" in allowed else [kind for kind in gate_failures if kind not in allowed]
        if gate_status == "fail" and unexpected:
            failures.append({"kind": "unexpected_gate_failures", "failures": unexpected})

    return {
        "status": "fail" if failures else "pass",
        "run_dir": str(run_dir),
        "audit_status": audit_report.get("audit_status"),
        "article_count": audit_report.get("article_count"),
        "selected_article_count": len(selected_articles),
        "missing_selected_articles": missing_selected,
        "selected_articles": selected_ids,
        "selected_summary": selected_summary,
        "corpus_quality_defect_counts": corpus_quality_counts,
        "corpus_observed_defect_counts": dict(corpus_summary.get("observed_defect_counts") or {}),
        "quality_totals": {
            key: quality_totals.get(key, 0)
            for key in ("defects", "errors", "warnings", "broken_internal_links", "external_page_query_links")
        },
        "gate_status": gate_report.get("status"),
        "gate_failure_kinds": [
            str(item.get("kind") or "unknown")
            for item in gate_report.get("failures") or []
            if isinstance(item, dict)
        ],
        "failures": failures,
    }
