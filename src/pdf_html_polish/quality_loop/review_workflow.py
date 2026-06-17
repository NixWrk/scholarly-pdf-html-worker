"""Manual and article-review workflow helpers for quality-loop runs."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable, Iterable
import urllib.parse

from .run_utils import load_json, now, slug, write_json


ComparisonByArticle = Callable[[dict[str, Any]], dict[str, dict[str, Any]]]
ManifestArticleById = Callable[[dict[str, Any]], dict[str, dict[str, Any]]]
CopyReviewHtml = Callable[[Path, Path], dict[str, Any]]


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
        state = {key: value for key, value in item.items() if key.startswith("review_")}
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

    entry_articles = entry.get("articles") if isinstance(entry.get("articles"), dict) else {}
    assessment_by_article = {
        str(article.get("article")): article
        for article in assessment.get("articles", [])
        if isinstance(article, dict) and article.get("article")
    }
    manifest_by_article = manifest_article_by_id(manifest)
    comparison = load_json(run_dir / "quality_compare.json", default={"status": "no_previous_entry"})
    deltas = comparison_by_article(comparison)
    previous_state = review_state_by_key(existing_queue_items(run_dir / "manual_review_queue.json"))

    queue: list[dict[str, Any]] = []
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        defects = [defect for defect in article.get("defects_found", []) if isinstance(defect, dict)]
        non_ignored = [defect for defect in defects if str(defect.get("id") or "") not in ignored]
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
        mandatory_changed_review = changed and comparison_item.get("bucket") == "unchanged"
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
                "defect_ids": defect_id_counts(defects),
                "non_ignored_defect_ids": defect_id_counts(non_ignored),
                "severity_counts": severity_counts(defects),
                "non_ignored_severity_counts": severity_counts(non_ignored),
                "changed": changed,
                "mandatory_review": mandatory_changed_review,
                "mandatory_review_reason": (
                    "changed_without_quality_delta" if mandatory_changed_review else ""
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
