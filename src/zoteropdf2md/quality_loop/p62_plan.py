from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from zoteropdf2md.marker_runner import build_marker_single_command
from zoteropdf2md.quality_loop.observations import compact_observation_text
from zoteropdf2md.quality_loop.resolver_decisions import defect_extra
from zoteropdf2md.quality_loop.run_utils import load_json, now, slug, write_json
from zoteropdf2md.quality_loop.source_pdf import manifest_article_by_id


DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME = "p62_marker_recovery_plan.json"
DEFAULT_MARKER_RECOVERY_DEFECT_IDS = {"P62", "P62A"}


@dataclass(frozen=True)
class P62MarkerRecoveryPlanDependencies:
    index_polish_stage_files: Callable[[Path], list[Path]]
    selected_pdf_candidate: Callable[
        [Path, str, dict[str, Any], dict[str, Any]],
        tuple[dict[str, Any] | None, list[dict[str, Any]]],
    ]
    find_polish_stage_path_for_article: Callable[
        [Path, str, dict[str, Any], dict[str, Any], list[Path]],
        tuple[Path | None, str],
    ]
    recovery_snippets: Callable[..., tuple[list[str], str, str]]
    full_figure_label_from_context: Callable[[str, str], str]
    pdf_text_pages: Callable[..., tuple[str, list[str], str | None]]
    resolve_pdf_page_for_figure: Callable[..., dict[str, Any]]
    validate_marker_output: Callable[[Path, str], dict[str, Any]]


def _visible_label_from_p61_defect(defect: dict[str, Any]) -> str:
    extra = defect_extra(defect)
    visible_label = str(extra.get("visible_label") or "").strip()
    if visible_label:
        match = re.search(
            r"\b(?:Fig(?:ure)?\.?|FIG(?:URE)?\.?)\s*(?P<label>\d{1,3}[A-Za-z]?)\b",
            visible_label,
            re.IGNORECASE,
        )
        if match is not None:
            return match.group("label")
    return str(extra.get("figure_key") or extra.get("figure") or "").strip()


def figure_label_for_recovery_defect(defect: dict[str, Any]) -> str:
    extra = defect_extra(defect)
    figure_label = str(extra.get("figure_label") or "").strip()
    if figure_label:
        return figure_label
    if str(defect.get("id") or "") == "P61":
        return _visible_label_from_p61_defect(defect)
    return ""


def figure_target_key_for_recovery_defect(defect: dict[str, Any], figure_label: str) -> str:
    extra = defect_extra(defect)
    if str(defect.get("id") or "") == "P61":
        target_key = str(extra.get("figure_key") or extra.get("figure") or "").strip()
        if target_key:
            return target_key
    label = str(figure_label or "").strip()
    label_match = re.fullmatch(r"(?P<num>\d{1,3})(?P<panel>[A-Za-z])?", label)
    if label_match is not None:
        return label_match.group("num")
    return label


def marker_recovery_defect_ids(gate_config: dict[str, Any]) -> set[str]:
    defect_ids = set(DEFAULT_MARKER_RECOVERY_DEFECT_IDS)
    if gate_config.get("p62_marker_recovery_include_p61"):
        defect_ids.add("P61")
    return defect_ids


def write_marker_recovery_plan(
    run_dir: Path,
    *,
    gate_config: dict[str, Any] | None,
    dependencies: P62MarkerRecoveryPlanDependencies,
    out_path: Path | None = None,
    plan_name: str = DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME,
) -> dict[str, Any]:
    """Build reproducible marker_single commands for source-backed P62 recovery."""

    gate_config = gate_config or {}
    run_dir = run_dir.resolve(strict=False)
    out_path = out_path or (run_dir / plan_name)
    output_root = run_dir / "p62_marker_recovery"
    max_items = int(gate_config.get("p62_marker_recovery_max_articles") or 0)
    max_pdf_pages = int(
        gate_config.get("p62_marker_recovery_max_pdf_pages")
        or gate_config.get("pdf_problem_evidence_max_pdf_pages")
        or 80
    )
    context_chars = int(gate_config.get("p62_marker_recovery_context_chars") or 5000)
    min_match_score = float(gate_config.get("p62_marker_recovery_min_match_score") or 0.05)
    require_label_match = bool(gate_config.get("p62_marker_recovery_require_label_match", True))
    retry_full_pdf_on_label_miss = bool(
        gate_config.get("p62_marker_recovery_retry_full_pdf_on_label_miss", True)
    )
    recovery_defect_ids = marker_recovery_defect_ids(gate_config)

    audit = load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    manifest = load_json(run_dir / "manifest.json", default={})
    manifest_by_article = manifest_article_by_id(manifest)
    polish_index = dependencies.index_polish_stage_files(run_dir)

    p62_items: list[tuple[dict[str, Any], dict[str, Any], int]] = []
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        for defect_index, defect in enumerate(article.get("defects_found") or [], start=1):
            if isinstance(defect, dict) and str(defect.get("id") or "") in recovery_defect_ids:
                p62_items.append((article, defect, defect_index))

    selected_items = p62_items[:max_items] if max_items > 0 else p62_items
    pdf_text_cache: dict[str, tuple[str, list[str], str | None]] = {}
    records: list[dict[str, Any]] = []

    for index, (article, defect, defect_index) in enumerate(selected_items, start=1):
        article_id = str(article.get("article") or f"article_{index}")
        manifest_article = manifest_by_article.get(article_id, {})
        extra = defect_extra(defect)
        figure_label = figure_label_for_recovery_defect(defect)
        target_figure_key = figure_target_key_for_recovery_defect(defect, figure_label)
        article_dir = output_root / f"{index:03d}_{slug(article_id, max_len=72)}"
        if figure_label:
            article_dir = article_dir / f"fig_{slug(figure_label, max_len=20)}"

        selected_pdf, source_pdf_candidates = dependencies.selected_pdf_candidate(
            run_dir,
            article_id,
            article,
            manifest_article,
        )
        polish_path, polish_path_source = dependencies.find_polish_stage_path_for_article(
            run_dir,
            article_id,
            article,
            manifest_article,
            polish_index,
        )
        polish_html = ""
        polish_read_error = ""
        if polish_path is not None:
            try:
                polish_html = polish_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                polish_read_error = str(exc)

        snippets, polish_context, polish_context_source = dependencies.recovery_snippets(
            polish_html,
            defect,
            context_chars=context_chars,
        )
        resolved_figure_label = dependencies.full_figure_label_from_context(polish_context, figure_label)
        context_path = ""
        if polish_context:
            context_path = str(article_dir / "polish_context.txt")
            Path(context_path).parent.mkdir(parents=True, exist_ok=True)
            Path(context_path).write_text(polish_context + "\n", encoding="utf-8")

        record: dict[str, Any] = {
            "article": article_id,
            "source_article": article.get("source_article") or article_id,
            "defect_index": defect_index,
            "defect_id": defect.get("id"),
            "figure_label": figure_label,
            "target_figure_key": target_figure_key,
            "visible_label": extra.get("visible_label") or "",
            "resolved_figure_label": resolved_figure_label,
            "warning_index": extra.get("warning_index"),
            "warning_origin": extra.get("warning_origin") or extra.get("p62_subtype"),
            "status": "source_pdf_unavailable",
            "snippet": compact_observation_text(defect.get("snippet"), max_len=300),
            "source_pdf_available": bool(selected_pdf),
            "source_pdf_path": selected_pdf.get("path") if selected_pdf else "",
            "source_pdf_source": selected_pdf.get("source") if selected_pdf else "",
            "source_pdf_candidate_count": len(source_pdf_candidates),
            "source_pdf_candidates": source_pdf_candidates[:8],
            "polish_stage_path": str(polish_path) if polish_path is not None else "",
            "polish_stage_path_source": polish_path_source,
            "polish_read_error": polish_read_error,
            "polish_context_source": polish_context_source,
            "polish_context_path": context_path,
            "polish_context_excerpt": polish_context,
            "problem_snippet_count": len(snippets),
            "problem_snippets": snippets[:4],
            "text_layer_status": "not_run",
            "text_layer_error": "",
            "text_layer_page_count": 0,
            "text_layer_page_limit": max_pdf_pages,
            "text_layer_truncated_to_limit": False,
            "text_layer_full_retry": False,
            "source_pdf_page_number": 0,
            "figure_label_pdf_page_candidates": [],
            "page_resolver_candidates": [],
            "selected_false_match_hint": "",
            "source_visual_unavailable_reason": "",
            "require_label_match": require_label_match,
            "marker_page_number_zero_based": None,
            "marker_page_range": "",
            "match_score": 0.0,
            "min_match_score": min_match_score,
            "source_pdf_page_excerpt_path": "",
            "marker_output_dir": "",
            "marker_command": [],
            "existing_marker_output_validation": {"status": "not_run"},
        }
        if not selected_pdf:
            records.append(record)
            continue
        if not snippets:
            record["status"] = "warning_context_unavailable"
            records.append(record)
            continue

        pdf_path = Path(str(selected_pdf.get("path") or "")).expanduser()
        cache_key = f"{pdf_path}|{max_pdf_pages}"
        if cache_key not in pdf_text_cache:
            pdf_text_cache[cache_key] = dependencies.pdf_text_pages(pdf_path, max_pages=max_pdf_pages)
        text_status, pages, text_error = pdf_text_cache[cache_key]
        resolver = dependencies.resolve_pdf_page_for_figure(
            snippets,
            pages,
            resolved_figure_label or figure_label,
            pdf_path=pdf_path,
        )
        page_number = int(resolver.get("page_number") or 0)
        match_score = float(resolver.get("match_score") or 0.0)
        label_pages = list(resolver.get("label_pages") or [])
        text_layer_full_retry = False
        if (
            retry_full_pdf_on_label_miss
            and require_label_match
            and (resolved_figure_label or figure_label)
            and (
                not label_pages
                or resolver.get("source_visual_unavailable")
                or resolver.get("selected_false_match_hint")
            )
            and max_pdf_pages > 0
            and len(pages) >= max_pdf_pages
        ):
            full_cache_key = f"{pdf_path}|full"
            if full_cache_key not in pdf_text_cache:
                pdf_text_cache[full_cache_key] = dependencies.pdf_text_pages(pdf_path, max_pages=None)
            full_text_status, full_pages, full_text_error = pdf_text_cache[full_cache_key]
            full_resolver = dependencies.resolve_pdf_page_for_figure(
                snippets,
                full_pages,
                resolved_figure_label or figure_label,
                pdf_path=pdf_path,
            )
            full_page_number = int(full_resolver.get("page_number") or 0)
            full_match_score = float(full_resolver.get("match_score") or 0.0)
            full_label_pages = list(full_resolver.get("label_pages") or [])
            if full_label_pages:
                text_status = full_text_status
                pages = full_pages
                text_error = full_text_error
                resolver = full_resolver
                page_number = full_page_number
                match_score = full_match_score
                label_pages = full_label_pages
                text_layer_full_retry = True
        resolved_figure_label = str(resolver.get("resolved_figure_label") or resolved_figure_label or figure_label)
        text_chars = sum(len(page_text) for page_text in pages)
        record.update(
            {
                "resolved_figure_label": resolved_figure_label,
                "text_layer_status": text_status,
                "text_layer_error": text_error or "",
                "text_layer_page_count": len(pages),
                "text_layer_chars": text_chars,
                "text_layer_truncated_to_limit": bool(
                    max_pdf_pages > 0 and len(pages) >= max_pdf_pages and not text_layer_full_retry
                ),
                "text_layer_full_retry": text_layer_full_retry,
                "source_pdf_page_number": page_number,
                "figure_label_pdf_page_candidates": label_pages[:20],
                "page_resolver_candidates": resolver.get("candidates") or [],
                "selected_false_match_hint": resolver.get("selected_false_match_hint") or "",
                "match_score": round(float(match_score), 4),
            }
        )
        if not pages or text_chars <= 0:
            record["status"] = "text_layer_unavailable"
            records.append(record)
            continue
        if page_number <= 0 or match_score <= 0:
            record["status"] = "page_match_unavailable"
            records.append(record)
            continue
        if require_label_match and figure_label and not label_pages:
            record["status"] = "figure_label_page_unavailable"
            records.append(record)
            continue
        if resolver.get("source_visual_unavailable"):
            record["status"] = "source_visual_unavailable"
            record["source_visual_unavailable_reason"] = "all_label_matches_are_false_or_without_visual_objects"
            records.append(record)
            continue

        excerpt_path = article_dir / f"source_pdf_page_{page_number:04d}.txt"
        excerpt_path.parent.mkdir(parents=True, exist_ok=True)
        excerpt_path.write_text(pages[page_number - 1], encoding="utf-8", errors="replace")
        marker_page_index = page_number - 1
        marker_output_dir = article_dir / f"marker_page_{page_number:04d}"
        marker_page_range = str(marker_page_index)
        record.update(
            {
                "source_pdf_page_excerpt_path": str(excerpt_path),
                "marker_page_number_zero_based": marker_page_index,
                "marker_page_range": marker_page_range,
                "marker_output_dir": str(marker_output_dir),
                "marker_command": build_marker_single_command(
                    pdf_path,
                    marker_output_dir,
                    "html",
                    page_range=marker_page_range,
                    disable_multiprocessing=True,
                ),
                "existing_marker_output_validation": dependencies.validate_marker_output(
                    marker_output_dir,
                    resolved_figure_label or figure_label,
                ),
            }
        )
        record["status"] = "ready" if match_score >= min_match_score else "page_match_low_confidence"
        records.append(record)

    status_counts = Counter(str(item.get("status") or "unknown") for item in records)
    marker_output_status_counts = Counter(
        str((item.get("existing_marker_output_validation") or {}).get("status") or "not_run")
        for item in records
    )
    ready_count = int(status_counts.get("ready", 0))
    unresolved_count = len(records) - ready_count
    if not p62_items:
        status = "not_required"
    elif unresolved_count:
        status = "partial"
    else:
        status = "ready"
    ready_samples = [
        {
            "article": item.get("article"),
            "figure_label": item.get("figure_label"),
            "source_pdf_page_number": item.get("source_pdf_page_number"),
            "marker_page_range": item.get("marker_page_range"),
            "match_score": item.get("match_score"),
            "marker_command": item.get("marker_command"),
        }
        for item in records
        if item.get("status") == "ready"
    ][:8]
    report = {
        "generated_at": now(),
        "run_dir": str(run_dir),
        "path": str(out_path),
        "output_root": str(output_root),
        "status": status,
        "required_checks": [
            "polish_missing_warning_context",
            "source_pdf_text_page_match",
            "marker_single_page_command",
        ],
        "candidate_count": len(p62_items),
        "selected_count": len(records),
        "truncated_by_max_articles": bool(max_items > 0 and len(p62_items) > max_items),
        "max_articles": max_items,
        "ready_count": ready_count,
        "unresolved_count": unresolved_count,
        "status_counts": dict(sorted(status_counts.items())),
        "marker_output_status_counts": dict(sorted(marker_output_status_counts.items())),
        "min_match_score": min_match_score,
        "require_label_match": require_label_match,
        "marker_page_range_indexing": "zero_based_marker_cli",
        "ready_samples": ready_samples,
        "articles": records,
    }
    write_json(out_path, report)
    return report
