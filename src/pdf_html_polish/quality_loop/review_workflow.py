"""Manual and article-review workflow helpers for quality-loop runs."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable, Iterable
import urllib.parse

from .p62_recovery_stage import has_terminal_source_visual_unavailable_evidence
from .run_utils import json_object, load_json, now, slug, write_json


ComparisonByArticle = Callable[[dict[str, Any]], dict[str, dict[str, Any]]]
ManifestArticleById = Callable[[dict[str, Any]], dict[str, dict[str, Any]]]
CopyReviewHtml = Callable[[Path, Path], dict[str, Any]]

TOP_LEVEL_DELTA_METRICS = ("score", "defects", "errors", "warnings")
DEFAULT_LOWER_IS_BETTER_METRICS = (
    "broken_internal_links",
    "external_page_query_links",
    "internal_page_anchor_links",
    "missing_local_images",
    "mixed_citation_style",
    "polish_missing_local_images",
    "polish_replacement_chars",
    "table_units_with_section_ids",
)


def defect_id_counts(defects: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for defect in defects:
        defect_id = str(defect.get("id") or "unknown")
        counts[defect_id] = counts.get(defect_id, 0) + 1
    return dict(sorted(counts.items()))


def severity_counts(defects: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for defect in defects:
        severity = str(defect.get("severity") or "info")
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def defect_quality_counted(defect: dict[str, Any]) -> bool:
    extra = json_object(defect.get("extra"))
    return extra.get("quality_counted") is not False


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _metric_value(record: dict[str, Any], metric: str) -> float:
    metrics = json_object(record.get("metrics"))
    if metric in metrics:
        return _as_float(metrics.get(metric))
    return _as_float(record.get(metric))


def _comparison_delta(comparison_item: dict[str, Any], metric: str) -> float:
    if metric in TOP_LEVEL_DELTA_METRICS:
        return _as_float(comparison_item.get(f"{metric}_delta"))
    metrics_delta = json_object(comparison_item.get("metrics_delta"))
    if metric in metrics_delta:
        return _as_float(metrics_delta.get(metric))
    return _as_float(comparison_item.get(f"{metric}_delta"))


def _positive_delta_evidence(
    comparison_item: dict[str, Any],
    gate_config: dict[str, Any],
) -> dict[str, float]:
    metrics = set(DEFAULT_LOWER_IS_BETTER_METRICS)
    metrics.update(str(metric) for metric in (gate_config.get("max_total_deltas") or {}).keys())
    deltas: dict[str, float] = {}
    for metric in tuple(TOP_LEVEL_DELTA_METRICS) + tuple(sorted(metrics)):
        delta = _comparison_delta(comparison_item, metric)
        if delta > 0:
            deltas[metric] = delta
    return deltas


def _selected_delta_evidence(
    comparison_item: dict[str, Any],
    gate_config: dict[str, Any],
) -> dict[str, float]:
    metrics = set(DEFAULT_LOWER_IS_BETTER_METRICS)
    metrics.update(str(metric) for metric in (gate_config.get("max_total_deltas") or {}).keys())
    result: dict[str, float] = {}
    for metric in tuple(TOP_LEVEL_DELTA_METRICS) + tuple(sorted(metrics)):
        delta = _comparison_delta(comparison_item, metric)
        if delta != 0:
            result[metric] = delta
    return result


def _polish_auto_repair_evidence_by_article(run_dir: Path) -> dict[str, dict[str, Any]]:
    report = load_json(run_dir / "polish_auto_repair_report.json", default={})
    evidence: dict[str, dict[str, Any]] = {}
    for item in report.get("articles") or []:
        if not isinstance(item, dict):
            continue
        article = str(item.get("article") or "")
        if not article:
            continue
        repair_ids = sorted(
            {
                str(repair.get("id") or "")
                for repair in item.get("repairs") or []
                if isinstance(repair, dict) and repair.get("id")
            }
        )
        evidence[article] = {
            "patched": bool(item.get("patched")),
            "repair_ids": repair_ids,
            "error_count": len(item.get("errors") or []),
        }
    return evidence


def _audit_source_visual_unavailable_labels_by_article(run_dir: Path) -> dict[str, set[str]]:
    audit = load_json(run_dir / "audit_full_checks.json", default={})
    labels_by_article: dict[str, set[str]] = {}
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        for defect in article.get("defects_found") or []:
            if not isinstance(defect, dict) or str(defect.get("id") or "") != "P62":
                continue
            extra = json_object(defect.get("extra"))
            if (
                str(extra.get("p62_subtype") or "") != "source_visual_unavailable"
                and str(extra.get("warning_origin") or "") != "source_visual_unavailable"
            ):
                continue
            label = str(extra.get("figure_label") or "").strip()
            if label:
                labels_by_article.setdefault(article_id, set()).add(label)
    return labels_by_article


def _p62_recovery_evidence_by_article(run_dir: Path) -> dict[str, dict[str, Any]]:
    report = load_json(run_dir / "p62_image_recovery_report.json", default={})
    audit_terminal_labels = _audit_source_visual_unavailable_labels_by_article(run_dir)
    seen_terminal_labels: dict[str, set[str]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for item in report.get("articles") or []:
        if not isinstance(item, dict):
            continue
        article = str(item.get("article") or "")
        if not article:
            continue
        article_evidence = evidence.setdefault(
            article,
            {
                "patched_count": 0,
                "source_visual_unavailable_count": 0,
                "source_pdf_unavailable_count": 0,
                "actionable_unresolved_count": 0,
                "recovery_sources": [],
            },
        )
        status = str(item.get("status") or "")
        plan_status = str(item.get("plan_status") or "")
        figure_label = str(item.get("figure_label") or item.get("resolved_figure_label") or "").strip()
        if "source_pdf_unavailable" in {status, plan_status}:
            article_evidence["source_pdf_unavailable_count"] += 1
            continue
        terminal_unavailable = (
            status == "source_visual_unavailable"
            or has_terminal_source_visual_unavailable_evidence(item)
            or (
                bool(figure_label)
                and figure_label in audit_terminal_labels.get(article, set())
            )
        )
        if terminal_unavailable:
            article_evidence["source_visual_unavailable_count"] += 1
            if figure_label:
                seen_terminal_labels.setdefault(article, set()).add(figure_label)
            continue
        if status in {"unresolved", "asset_ready_patch_missed"}:
            article_evidence["actionable_unresolved_count"] += 1
            continue
        if item.get("asset_status") == "ready" or status in {
            "patched",
            "already_patched",
            "patched_duplicate_visuals",
        }:
            article_evidence["patched_count"] += 1
        recovery_source = str(item.get("recovery_source") or "")
        if recovery_source and recovery_source not in article_evidence["recovery_sources"]:
            article_evidence["recovery_sources"].append(recovery_source)
    for article, labels in audit_terminal_labels.items():
        unseen = labels - seen_terminal_labels.get(article, set())
        if not unseen:
            continue
        article_evidence = evidence.setdefault(
            article,
            {
                "patched_count": 0,
                "source_visual_unavailable_count": 0,
                "source_pdf_unavailable_count": 0,
                "actionable_unresolved_count": 0,
                "recovery_sources": [],
            },
        )
        article_evidence["source_visual_unavailable_count"] += len(unseen)
    return evidence


def _review_change_sources(
    manifest_article: dict[str, Any],
    p62_evidence: dict[str, Any],
    repair_evidence: dict[str, Any],
) -> list[str]:
    sources: list[str] = []
    if int(manifest_article.get("restored_images") or 0) > 0:
        sources.append("image_cache_restore")
    if int(manifest_article.get("pdf_reference_recovered") or 0) > 0:
        sources.append("pdf_reference_recovery")
    if int(p62_evidence.get("patched_count") or 0) > 0:
        sources.append("p62_image_recovery")
    if int(p62_evidence.get("source_visual_unavailable_count") or 0) > 0:
        sources.append("p62_source_visual_unavailable")
    if int(p62_evidence.get("source_pdf_unavailable_count") or 0) > 0:
        sources.append("p62_source_pdf_unavailable")
    if repair_evidence.get("patched") and not int(repair_evidence.get("error_count") or 0):
        for repair_id in repair_evidence.get("repair_ids") or []:
            sources.append(f"polish_auto_repair:{repair_id}")
    return sorted(set(sources))


def classify_review_risk(
    *,
    changed: bool,
    defects: list[dict[str, Any]],
    non_ignored: list[dict[str, Any]],
    non_ignored_quality_counted: list[dict[str, Any]],
    comparison_item: dict[str, Any],
    record: dict[str, Any],
    assessment_article: dict[str, Any],
    manifest_article: dict[str, Any],
    gate_config: dict[str, Any],
    p62_evidence: dict[str, Any],
    repair_evidence: dict[str, Any],
) -> dict[str, Any]:
    positive_deltas = _positive_delta_evidence(comparison_item, gate_config)
    selected_deltas = _selected_delta_evidence(comparison_item, gate_config)
    broken_targets = assessment_article.get("broken_targets") or []
    broken_internal_links = len(broken_targets) or int(_metric_value(record, "broken_internal_links"))
    missing_local_images = int(
        _metric_value(record, "missing_local_images")
        or _metric_value(record, "polish_missing_local_images")
    )
    mixed_citation_style_present = bool(assessment_article.get("mixed_citation_style")) or bool(
        int(_metric_value(record, "mixed_citation_style"))
    )
    p62_actionable_unresolved = int(p62_evidence.get("actionable_unresolved_count") or 0)
    change_sources = _review_change_sources(manifest_article, p62_evidence, repair_evidence)

    reasons: list[str] = []
    if comparison_item.get("bucket") == "regressions":
        reasons.append("comparison_regression")
    if positive_deltas:
        reasons.append("lower_is_better_metric_increase")
    if non_ignored_quality_counted:
        reasons.append("non_ignored_quality_counted_audit_defects")
    if broken_internal_links:
        reasons.append("broken_internal_links")
    if missing_local_images:
        reasons.append("missing_local_images")
    if p62_actionable_unresolved:
        reasons.append("p62_unresolved_without_terminal_status")

    if reasons:
        risk_level = "high"
    elif changed and (non_ignored or defects or mixed_citation_style_present):
        risk_level = "medium"
        if non_ignored:
            reasons.append("observed_non_quality_or_telemetry_defects")
        elif defects:
            reasons.append("ignored_defects_only")
        if mixed_citation_style_present:
            reasons.append("mixed_citation_style_present")
    elif changed and comparison_item.get("bucket") == "unchanged" and change_sources:
        risk_level = "auto_verified"
        reasons.append("changed_without_quality_delta_explained")
    elif changed and comparison_item.get("bucket") in {"unchanged", "improvements"}:
        risk_level = "low"
        reasons.append("changed_without_quality_regression")
    else:
        risk_level = "low"
        reasons.append("unchanged_or_not_review_required")

    return {
        "review_risk_level": risk_level,
        "review_risk_reasons": sorted(set(reasons)),
        "auto_review_eligible": bool(changed and risk_level in {"auto_verified", "low"}),
        "auto_review_evidence": {
            "comparison_bucket": comparison_item.get("bucket", ""),
            "score_delta": _comparison_delta(comparison_item, "score"),
            "defects_delta": _comparison_delta(comparison_item, "defects"),
            "errors_delta": _comparison_delta(comparison_item, "errors"),
            "warnings_delta": _comparison_delta(comparison_item, "warnings"),
            "metric_deltas": selected_deltas,
            "positive_lower_is_better_metric_deltas": positive_deltas,
            "defect_count": len(defects),
            "non_ignored_defect_count": len(non_ignored),
            "non_ignored_quality_counted_defect_count": len(non_ignored_quality_counted),
            "observed_non_quality_defect_count": sum(
                1 for defect in defects if not defect_quality_counted(defect)
            ),
            "broken_internal_links": broken_internal_links,
            "missing_local_images": missing_local_images,
            "mixed_citation_style": mixed_citation_style_present,
            "p62": p62_evidence,
            "polish_auto_repair": repair_evidence,
            "change_sources": change_sources,
        },
    }


def existing_queue_items(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = load_json(path, default=[])
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    return []


def review_state_by_key(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for item in items:
        state = {
            key: value
            for key, value in item.items()
            if key.startswith("review_") and not key.startswith("review_risk_")
        }
        if not state:
            continue
        for key in ("article", "raw_stage_path", "polish_stage_path"):
            value = item.get(key)
            if value:
                states.setdefault(str(value), dict(state))
    return states


def write_manual_review_queue(
    run_dir: Path,
    *,
    gate_config: dict[str, Any],
    ignored_defect_ids: set[str] | None = None,
    comparison_by_article: ComparisonByArticle,
    manifest_article_by_id: ManifestArticleById,
) -> list[dict[str, Any]]:
    """Write all audited articles sorted by review priority."""

    ignored = set(gate_config.get("ignored_defect_ids_for_analysis") or [])
    if ignored_defect_ids:
        ignored.update(ignored_defect_ids)

    run_dir = run_dir.resolve(strict=False)
    audit = load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    entry = load_json(run_dir / "quality_history_entry.json", default={"articles": {}})
    assessment = load_json(run_dir / "assessment.json", default={"articles": []})
    manifest = load_json(run_dir / "manifest.json", default={})

    entry_articles = json_object(entry.get("articles"))
    assessment_by_article = {
        str(article.get("article")): article
        for article in assessment.get("articles", [])
        if isinstance(article, dict) and article.get("article")
    }
    manifest_by_article = manifest_article_by_id(manifest)
    comparison = load_json(run_dir / "quality_compare.json", default={"status": "no_previous_entry"})
    deltas = comparison_by_article(comparison)
    previous_state = review_state_by_key(existing_queue_items(run_dir / "manual_review_queue.json"))
    p62_evidence_by_article = _p62_recovery_evidence_by_article(run_dir)
    repair_evidence_by_article = _polish_auto_repair_evidence_by_article(run_dir)

    queue: list[dict[str, Any]] = []
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        defects = [defect for defect in article.get("defects_found", []) if isinstance(defect, dict)]
        non_ignored = [defect for defect in defects if str(defect.get("id") or "") not in ignored]
        quality_counted = [defect for defect in defects if defect_quality_counted(defect)]
        non_ignored_quality_counted = [
            defect for defect in non_ignored if defect_quality_counted(defect)
        ]
        record = entry_articles.get(article_id, {}) if isinstance(entry_articles, dict) else {}
        assessment_article = assessment_by_article.get(article_id, {})
        manifest_article = manifest_by_article.get(article_id, {})
        raw_stage_path = (
            article.get("raw_stage_path")
            or assessment_article.get("raw_stage_path")
            or manifest_article.get("raw_stage_path")
        )
        polish_stage_path = (
            article.get("polish_stage_path")
            or assessment_article.get("polish_stage_path")
            or manifest_article.get("polish_stage_path")
        )
        source_article = (
            article.get("source_article")
            or assessment_article.get("source_article")
            or manifest_article.get("article")
            or article_id
        )
        artifact_hint = (
            article.get("artifact_hint")
            or assessment_article.get("artifact_hint")
            or manifest_article.get("artifact_hint")
        )
        changed = bool(manifest_article.get("changed"))
        comparison_item = deltas.get(article_id, {})
        risk = classify_review_risk(
            changed=changed,
            defects=defects,
            non_ignored=non_ignored,
            non_ignored_quality_counted=non_ignored_quality_counted,
            comparison_item=comparison_item,
            record=record,
            assessment_article=assessment_article,
            manifest_article=manifest_article,
            gate_config=gate_config,
            p62_evidence=p62_evidence_by_article.get(article_id, {}),
            repair_evidence=repair_evidence_by_article.get(article_id, {}),
        )
        mandatory_review = bool(changed and risk["review_risk_level"] == "high")
        changed_without_quality_delta = changed and comparison_item.get("bucket") == "unchanged"
        review_state = {}
        for key in (article_id, str(raw_stage_path or ""), str(polish_stage_path or "")):
            if key and key in previous_state:
                review_state = dict(previous_state[key])
                break
        review_state.setdefault("review_status", "pending")
        review_state.setdefault("review_note", "")

        queue.append(
            {
                "article": article_id,
                "source_article": source_article,
                "artifact_hint": artifact_hint,
                "score": float(record.get("score", 0) or 0),
                "defect_count": len(defects),
                "non_ignored_defect_count": len(non_ignored),
                "quality_counted_defect_count": len(quality_counted),
                "non_ignored_quality_counted_defect_count": len(non_ignored_quality_counted),
                "defect_ids": defect_id_counts(defects),
                "non_ignored_defect_ids": defect_id_counts(non_ignored),
                "quality_counted_defect_ids": defect_id_counts(quality_counted),
                "non_ignored_quality_counted_defect_ids": defect_id_counts(
                    non_ignored_quality_counted
                ),
                "severity_counts": severity_counts(defects),
                "non_ignored_severity_counts": severity_counts(non_ignored),
                "changed": changed,
                "review_risk_level": risk["review_risk_level"],
                "review_risk_reasons": risk["review_risk_reasons"],
                "auto_review_eligible": risk["auto_review_eligible"],
                "auto_review_evidence": risk["auto_review_evidence"],
                "mandatory_review": mandatory_review,
                "mandatory_review_reason": (
                    "changed_without_quality_delta"
                    if mandatory_review and changed_without_quality_delta
                    else ("high_risk_changed_article" if mandatory_review else "")
                ),
                "comparison_bucket": comparison_item.get("bucket", ""),
                "raw_stage_path": raw_stage_path,
                "polish_stage_path": polish_stage_path,
                **review_state,
            }
        )

    queue.sort(
        key=lambda item: (
            0 if item.get("mandatory_review") else 1,
            {"high": 0, "medium": 1, "low": 2, "auto_verified": 3}.get(
                str(item.get("review_risk_level") or ""),
                4,
            ),
            -float(item.get("score") or 0),
            -int(item.get("non_ignored_defect_count") or 0),
            -int(item.get("defect_count") or 0),
            str(item.get("article") or ""),
        )
    )
    write_json(run_dir / "manual_review_queue.json", queue)
    return queue


def stage_path_for_review(run_dir: Path, value: Any, *, repo_root: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        run_candidate = (run_dir / path).resolve(strict=False)
        if run_candidate.exists():
            return run_candidate
        root_candidate = (repo_root / path).resolve(strict=False)
        if root_candidate.exists():
            return root_candidate
        return run_candidate
    return path.resolve(strict=False)


def relative_review_href(review_dir: Path, target_path: Path) -> str:
    try:
        rel = target_path.resolve(strict=False).relative_to(review_dir.resolve(strict=False))
    except ValueError:
        rel = target_path.resolve(strict=False)
    return urllib.parse.quote(str(rel).replace("\\", "/"), safe="/:#?&=%._-")


def write_article_review_stage(
    run_dir: Path,
    review_queue: list[dict[str, Any]] | None,
    *,
    max_articles: int | None = None,
    repo_root: Path,
    polish_stage: str,
    copy_review_html_with_inline_images: CopyReviewHtml,
) -> dict[str, Any]:
    """Build the mandatory changed-article review bundle for a loop run."""

    run_dir = run_dir.resolve(strict=False)
    review_queue = review_queue if review_queue is not None else existing_queue_items(run_dir / "manual_review_queue.json")
    review_dir = run_dir / "article_review"
    review_dir.mkdir(parents=True, exist_ok=True)

    mandatory_items = [item for item in review_queue if item.get("mandatory_review")]
    pending_mandatory = [
        item for item in mandatory_items if str(item.get("review_status") or "pending") == "pending"
    ]
    limit = len(mandatory_items) if max_articles is None or int(max_articles) <= 0 else int(max_articles)
    selected_items = mandatory_items[:limit]

    articles: list[dict[str, Any]] = []
    copy_errors: list[dict[str, Any]] = []
    for index, item in enumerate(selected_items, start=1):
        article = str(item.get("article") or f"article_{index}")
        source_path = stage_path_for_review(run_dir, item.get("polish_stage_path"), repo_root=repo_root)
        target_path = review_dir / f"{index:03d}_{slug(article, max_len=72)}" / polish_stage
        copy_info: dict[str, Any] = {}
        if source_path is not None and source_path.is_file():
            try:
                copy_info = copy_review_html_with_inline_images(source_path, target_path)
            except Exception as exc:  # pragma: no cover - defensive artifact generation
                copy_errors.append({"article": article, "polish_stage_path": str(source_path), "error": str(exc)})
        else:
            copy_errors.append(
                {
                    "article": article,
                    "polish_stage_path": str(source_path) if source_path is not None else "",
                    "error": "polish stage file is missing",
                }
            )

        articles.append(
            {
                "article": article,
                "source_article": item.get("source_article"),
                "artifact_hint": item.get("artifact_hint"),
                "reason": item.get("mandatory_review_reason") or item.get("reason") or "",
                "review_status": item.get("review_status") or "pending",
                "review_note": item.get("review_note") or "",
                "raw_stage_path": item.get("raw_stage_path"),
                "polish_stage_path": item.get("polish_stage_path"),
                "review_html": copy_info.get("review_html"),
                "review_href": (
                    relative_review_href(review_dir, Path(str(copy_info["review_html"])))
                    if copy_info.get("review_html")
                    else ""
                ),
                "inlined_image_count": int(copy_info.get("inlined_image_count") or 0),
                "missing_image_count": int(copy_info.get("missing_image_count") or 0),
                "missing_image_srcs": copy_info.get("missing_image_srcs") or [],
            }
        )

    index_lines = [
        "<!doctype html>",
        '<html><head><meta charset="utf-8">',
        "<title>Article Review Bundle</title>",
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.45}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:6px 8px;vertical-align:top}"
        "th{background:#f3f5f7;text-align:left}code{font-size:12px}</style>",
        "</head><body>",
        "<h1>Article Review Bundle</h1>",
        f"<p>Mandatory changed articles: {len(mandatory_items)}. Pending: {len(pending_mandatory)}. "
        f"Included here: {len(articles)}.</p>",
        "<table><thead><tr><th>#</th><th>Article</th><th>Status</th><th>Reason</th><th>Review HTML</th><th>Stage Path</th></tr></thead><tbody>",
    ]
    for index, item in enumerate(articles, start=1):
        review_link = (
            f'<a href="{escape(str(item.get("review_href") or ""), quote=True)}">open</a>'
            if item.get("review_href")
            else "missing"
        )
        index_lines.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{escape(str(item.get('article') or ''))}</code></td>"
            f"<td>{escape(str(item.get('review_status') or ''))}</td>"
            f"<td>{escape(str(item.get('reason') or ''))}</td>"
            f"<td>{review_link}</td>"
            f"<td><code>{escape(str(item.get('polish_stage_path') or ''))}</code></td>"
            "</tr>"
        )
    index_lines.extend(["</tbody></table>", "</body></html>"])
    index_path = review_dir / "index.html"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    status = "ready"
    if not mandatory_items:
        status = "not_required"
    elif copy_errors and len(copy_errors) == len(selected_items):
        status = "error"
    elif copy_errors:
        status = "partial"

    report = {
        "generated_at": now(),
        "status": status,
        "run_dir": str(run_dir),
        "review_dir": str(review_dir),
        "index_html": str(index_path),
        "queue_count": len(review_queue),
        "mandatory_count": len(mandatory_items),
        "pending_mandatory_count": len(pending_mandatory),
        "reviewed_mandatory_count": len(mandatory_items) - len(pending_mandatory),
        "selected_count": len(articles),
        "bundle_limit": limit,
        "copy_error_count": len(copy_errors),
        "copy_errors": copy_errors[:20],
        "articles": articles,
    }
    write_json(run_dir / "article_review_report.json", report)
    return report
