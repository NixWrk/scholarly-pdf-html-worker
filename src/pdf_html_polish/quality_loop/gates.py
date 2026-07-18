"""Quality gate evaluation for LLM-assisted polish runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .run_utils import json_object


def load_gate_config(path: Path) -> dict[str, Any]:
    return json_object(json.loads(path.read_text(encoding="utf-8")))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_quality_gate(
    comparison: dict[str, Any],
    gate_config: dict[str, Any],
    *,
    article_review_report: dict[str, Any] | None = None,
    audit_report: dict[str, Any] | None = None,
    audit_command_report: dict[str, Any] | None = None,
    pdf_problem_evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    status = str(comparison.get("status") or "")
    if status == "no_previous_entry":
        if not gate_config.get("allow_missing_previous", False):
            failures.append({"kind": "missing_previous", "message": "No previous quality entry was available."})
    elif status != "ok":
        failures.append({"kind": "comparison_status", "status": status})

    regressions = [
        item for item in comparison.get("regressions") or [] if isinstance(item, dict)
    ]
    max_regressions = int(gate_config.get("max_regressions", 0))
    if len(regressions) > max_regressions:
        failures.append(
            {
                "kind": "regressions",
                "observed": len(regressions),
                "limit": max_regressions,
                "articles": [item.get("article") for item in regressions],
            }
        )

    totals_delta = json_object(comparison.get("totals_delta"))
    comparable_totals_delta = json_object(comparison.get("comparable_totals_delta"))
    gate_totals_delta = comparable_totals_delta or totals_delta
    for metric, limit in json_object(gate_config.get("max_total_deltas")).items():
        observed = float(gate_totals_delta.get(metric, 0) or 0)
        if observed > float(limit):
            failures.append({"kind": "total_delta", "metric": metric, "observed": observed, "limit": limit})

    article_limits = json_object(gate_config.get("max_article_deltas"))
    for item in regressions:
        for metric, limit in article_limits.items():
            observed = float(item.get(metric, 0) or 0)
            if observed > float(limit):
                failures.append(
                    {
                        "kind": "article_delta",
                        "article": item.get("article"),
                        "metric": metric,
                        "observed": observed,
                        "limit": limit,
                    }
                )

    article_review_summary: dict[str, Any] | None = None
    if gate_config.get("require_article_review_stage", False):
        if not isinstance(article_review_report, dict):
            failures.append(
                {
                    "kind": "article_review_stage_missing",
                    "message": "article_review_report.json was not generated for this run.",
                }
            )
        else:
            article_review_summary = {
                "status": article_review_report.get("status"),
                "review_dir": article_review_report.get("review_dir"),
                "queue_count": article_review_report.get("queue_count"),
                "mandatory_count": article_review_report.get("mandatory_count"),
                "pending_mandatory_count": article_review_report.get("pending_mandatory_count"),
                "selected_count": article_review_report.get("selected_count"),
            }
            if article_review_report.get("status") not in {"ready", "not_required"}:
                failures.append(
                    {
                        "kind": "article_review_stage",
                        "status": article_review_report.get("status"),
                        "message": "Article review stage did not finish cleanly.",
                    }
                )
            if gate_config.get("max_pending_mandatory_reviews") is not None:
                pending_limit = int(gate_config.get("max_pending_mandatory_reviews") or 0)
                pending = int(article_review_report.get("pending_mandatory_count") or 0)
                if pending > pending_limit:
                    failures.append(
                        {
                            "kind": "mandatory_review_pending",
                            "observed": pending,
                            "limit": pending_limit,
                        }
                    )

    audit_pdf_summary: dict[str, Any] | None = None
    if gate_config.get("require_pdf_text_layer_diagnostics", False):
        audit_totals = {}
        audit_articles: list[dict[str, Any]] = []
        if isinstance(audit_report, dict):
            audit_totals = json_object(
                json_object(audit_report.get("corpus_summary")).get("totals")
            )
            raw_audit_articles = audit_report.get("articles")
            if isinstance(raw_audit_articles, list):
                audit_articles = [
                    article
                    for article in raw_audit_articles
                    if isinstance(article, dict)
                ]
        audit_diagnostics_flags = [
            json_object(article.get("summary")).get("pdf_diagnostics_enabled") is True
            for article in audit_articles
        ]
        audit_report_used_pdf_diagnostics = bool(audit_diagnostics_flags) and all(
            audit_diagnostics_flags
        )
        command_returncode = (
            audit_command_report.get("returncode")
            if isinstance(audit_command_report, dict)
            else None
        )
        audit_pdf_summary = {
            "pdf_text_chars": int(audit_totals.get("pdf_text_chars") or 0),
            "source_pdf_present": int(audit_totals.get("source_pdf_present") or 0),
            "command_returncode": command_returncode,
            "command_used_pdf_diagnostics": bool(
                isinstance(audit_command_report, dict)
                and audit_command_report.get("pdf_diagnostics_enabled")
            ),
            "audit_report_used_pdf_diagnostics": audit_report_used_pdf_diagnostics,
            "audit_article_count": len(audit_articles),
            "pdf_map_path": (
                audit_command_report.get("pdf_map_path")
                if isinstance(audit_command_report, dict)
                else None
            ),
            "source_pdf_text_layer_empty": (
                int(audit_totals.get("source_pdf_present") or 0) > 0
                and int(audit_totals.get("pdf_text_chars") or 0) <= 0
            ),
        }
        if not isinstance(audit_report, dict):
            failures.append(
                {
                    "kind": "pdf_text_layer_diagnostics_missing",
                    "message": "audit_full_checks.json was not available for PDF text-layer diagnostics validation.",
                }
            )
        elif type(command_returncode) is not int or command_returncode != 0:
            failures.append(
                {
                    "kind": "pdf_text_layer_diagnostics_command_failed",
                    "returncode": command_returncode,
                    "message": "The PDF diagnostics audit command did not prove a successful exit.",
                }
            )
        elif not audit_pdf_summary["command_used_pdf_diagnostics"]:
            failures.append(
                {
                    "kind": "pdf_text_layer_diagnostics_disabled",
                    "message": "Audit did not run with --pdf-diagnostics.",
                }
            )
        elif not audit_report_used_pdf_diagnostics:
            failures.append(
                {
                    "kind": "pdf_text_layer_diagnostics_inconsistent",
                    "message": (
                        "Audit command claimed PDF diagnostics, but the article results "
                        "do not consistently confirm that diagnostics were enabled."
                    ),
                }
            )

    pdf_problem_evidence_summary: dict[str, Any] | None = None
    if gate_config.get("require_pdf_problem_evidence_stage", False):
        if not isinstance(pdf_problem_evidence_report, dict):
            failures.append(
                {
                    "kind": "pdf_problem_evidence_stage_missing",
                    "message": "pdf_problem_evidence_report.json was not generated for this run.",
                }
            )
        else:
            pdf_problem_evidence_summary = {
                "status": pdf_problem_evidence_report.get("status"),
                "report_path": pdf_problem_evidence_report.get("report_path"),
                "evidence_dir": pdf_problem_evidence_report.get("evidence_dir"),
                "selected_count": pdf_problem_evidence_report.get("selected_count", 0),
                "ready_count": pdf_problem_evidence_report.get("ready_count", 0),
                "source_pdf_unavailable_count": pdf_problem_evidence_report.get(
                    "source_pdf_unavailable_count", 0
                ),
                "blocking_issue_count": pdf_problem_evidence_report.get("blocking_issue_count", 0),
                "required_checks": pdf_problem_evidence_report.get("required_checks", []),
            }
            if pdf_problem_evidence_report.get("status") not in {"ready", "not_required"}:
                failures.append(
                    {
                        "kind": "pdf_problem_evidence_stage",
                        "status": pdf_problem_evidence_report.get("status"),
                        "blocking_issue_count": pdf_problem_evidence_report.get("blocking_issue_count", 0),
                    }
                )

    return {
        "generated_at": _now(),
        "status": "fail" if failures else "pass",
        "failures": failures,
        "regression_count": len(regressions),
        "improvement_count": len(comparison.get("improvements") or []),
        "totals_delta": totals_delta,
        "comparable_totals_delta": comparable_totals_delta,
        "new_article_count": int(comparison.get("new_article_count") or 0),
        "removed_article_count": int(comparison.get("removed_article_count") or 0),
        "article_review_stage": article_review_summary,
        "pdf_text_layer_diagnostics": audit_pdf_summary,
        "pdf_problem_evidence_stage": pdf_problem_evidence_summary,
    }
