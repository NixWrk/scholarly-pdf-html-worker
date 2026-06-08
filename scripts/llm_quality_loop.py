#!/usr/bin/env python
"""Orchestrate LLM-assisted EN polish quality loops.

The script is intentionally conservative: it prepares reproducible run
artifacts, evaluates quality gates, and builds compact LLM analysis packets.
Actual code edits still happen through a human/agent review step unless an
external LLM command is explicitly supplied.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html import escape
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.single_file_html import (  # noqa: E402
    close_katex_v8_context,
    polish_html_document,
)
from zoteropdf2md.citation_profile import extract_reference_entries_from_pdf  # noqa: E402
from zoteropdf2md.marker_runner import build_marker_single_command  # noqa: E402
from zoteropdf2md.polish_language import resolve_document_polish_language  # noqa: E402
from zoteropdf2md.quality_loop import commands as quality_commands  # noqa: E402
from zoteropdf2md.quality_loop.cached_images import (  # noqa: E402
    apply_data_image_cache as _apply_data_image_cache,
    cached_data_image_cache as _cached_data_image_cache,
    copy_review_html_with_inline_images as _copy_review_html_with_inline_images,
    manifest_article_for as _manifest_article_for,
)
from zoteropdf2md.quality_loop.converted_runs import (  # noqa: E402
    POLISH_STAGE,
    RAW_STAGE,
    assessment_totals as _assessment_totals,
    assess_polish_html,
    find_converted_stage_pairs,
    prepare_converted_raw_cache,
    prepare_converted_run,
    visible_html_text as _visible_html_text,
)
from zoteropdf2md.quality_loop import gates as quality_gates  # noqa: E402
from zoteropdf2md.quality_loop import pdf_utils as quality_pdf_utils  # noqa: E402
from zoteropdf2md.quality_loop import source_pdf as quality_source_pdf  # noqa: E402
from zoteropdf2md.quality_loop.observations import (  # noqa: E402
    compact_observation_text as _compact_observation_text,
    manual_observation_signature,
    record_manual_observation,
    write_manual_observation_summary as _write_manual_observation_summary,
)
from zoteropdf2md.quality_loop.pattern_observations import (  # noqa: E402
    write_pattern_observations as _write_pattern_observations,
)
from zoteropdf2md.quality_loop.resolver_decisions import (  # noqa: E402
    ARTICLE_SLOT_REPAIR_DECISION_NAMES,
    defect_extra as _defect_extra,
    write_resolver_decisions as _write_resolver_decisions,
)
from zoteropdf2md.quality_loop.run_utils import (  # noqa: E402
    article_dir_from_stage as _article_dir_from_stage,
    article_name_from_stage as _article_name_from_stage,
    artifact_hint as _artifact_hint,
    console_text as _console_text,
    converted_article_id as _converted_article_id,
    git_dirty as _git_dirty,
    git_short_head as _git_short_head,
    load_json as _load_json,
    norm_path as _norm_path,
    now as _now,
    profile_value as _profile_value,
    slug as _slug,
    write_json as _write_json,
)
from zoteropdf2md.quality_loop.p62_html import (  # noqa: E402
    clean_resolved_missing_unit_classes as _clean_resolved_p62_missing_unit_classes,
    data_url_image_hash as _p62_data_url_image_hash,
    extract_html_figure_units as _p62_extract_html_figure_units,
    figure_label_from_unit_id as _p62_figure_label_from_unit_id,
    html_has_missing_warning_for_figure_unit as _html_has_p62_missing_warning_for_figure_unit,
    html_has_recovery_for_label as _html_has_p62_recovery_for_label,
    html_has_stale_page_render_for_label as _html_has_p62_stale_page_render_for_label,
    id_matches_figure_label as _p62_id_matches_figure_label,
    missing_warning_target_html as _p62_missing_warning_target_html,
    recovered_target_matches_label as _p62_recovered_target_matches_label,
    recovered_target_source as _p62_recovered_target_source,
    recovery_target_html as _p62_recovery_target_html,
    replace_figure_unit_target_with_image as _replace_p62_figure_unit_target_with_image,
    replace_figure_unit_target_with_missing_warning as _replace_p62_figure_unit_target_with_missing_warning,
    replace_missing_warning_with_image as _replace_p62_missing_warning_with_image,
    replace_recovery_with_missing_warning as _replace_p62_recovery_with_missing_warning,
    replace_stale_recovery_with_image as _replace_p62_stale_recovery_with_image,
)
from zoteropdf2md.quality_loop.p62_marker import execute_marker_command as _execute_p62_marker_command_impl  # noqa: E402
from zoteropdf2md.quality_loop.p62_matching import (  # noqa: E402
    best_pdf_text_page as _best_pdf_text_page,
    caption_head_present_near_label as _p62_caption_head_present_near_label,
    caption_head_tokens as _p62_caption_head_tokens,
    evidence_snippet_tokens as _evidence_snippet_tokens,
    false_page_match_hint as _p62_false_page_match_hint,
    figure_label_present_in_text as _figure_label_present_in_text,
    figure_label_present_in_text_strict as _figure_label_present_in_text_strict,
    full_figure_label_from_context as _p62_full_figure_label_from_context,
    label_looks_caption_like as _p62_label_looks_caption_like,
    pdf_page_match_score as _pdf_page_match_score,
    pdf_page_visual_summaries as _p62_pdf_page_visual_summaries,
    tokenize_evidence_text as _tokenize_evidence_text,
)


DEFAULT_GATE_CONFIG = ROOT / "configs" / "llm_quality_gates.json"
DEFAULT_DEFECT_PATTERNS = ROOT / "configs" / "llm_defect_patterns.json"
DEFAULT_PATTERN_HISTORY_NAME = "pattern_observation_history.jsonl"
DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME = "manual_observation_ledger.jsonl"
DEFAULT_SOURCE_PDF_MAP_NAME = "source_pdf_map.json"
DEFAULT_PDF_PROBLEM_EVIDENCE_NAME = "pdf_problem_evidence_report.json"
DEFAULT_RESOLVER_DECISIONS_NAME = "resolver_decisions.json"
DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME = "p62_marker_recovery_plan.json"
DEFAULT_P62_IMAGE_RECOVERY_REPORT_NAME = "p62_image_recovery_report.json"
DEFAULT_POLISH_AUTO_REPAIR_REPORT_NAME = "polish_auto_repair_report.json"

REF_HREF_RE = re.compile(r"\bhref\s*=\s*[\"']#ref-\d+[\"']", re.IGNORECASE)
P_BLOCK_RE = re.compile(r"<p\b(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</p>", re.IGNORECASE)
BRACKETED_BODY_REFERENCE_CANDIDATE_RE = re.compile(
    r"\[\s*(?P<body>\d{1,3}(?:\s*(?:,|;|-|\u2013|\u2014)\s*\d{1,3}){1,12})\s*\]",
    re.IGNORECASE,
)
PLAIN_BODY_REFERENCE_CANDIDATE_RE = re.compile(
    r"(?<![\w.])(?P<body>\d{1,3}\s*(?:,|;|-|\u2013|\u2014)\s*\d{1,3}"
    r"(?:\s*(?:,|;|-|\u2013|\u2014)\s*\d{1,3}){0,12})(?!\s*(?:%|\u2030|cm|mm|m\b|kg|g\b|mg|"
    r"hz|khz|mhz|ghz|s\b|min\b|h\b|years?\b|months?\b|days?\b))",
    re.IGNORECASE,
)
REFERENCE_RECOVERY_PROTECTED_CLASS_RE = re.compile(
    r"\b(?:z2m-front-matter|z2m-missing|z2m-figure|z2m-table|z2m-equation|katex|math)\b",
    re.IGNORECASE,
)
P62_MISSING_WARNING_TEXT_RE = re.compile(
    r"\bFigure\s+(?P<label>[\w.-]+)\s+image\s+was\s+not\s+extracted\b",
    re.IGNORECASE,
)
P62_MISSING_WARNING_ELEMENT_RE = re.compile(
    r"<(?P<tag>p|div|span)\b(?P<attrs>[^>]*\bz2m-missing-figure-warning\b[^>]*)>"
    r"[\s\S]*?</(?P=tag)>",
    re.IGNORECASE,
)
P62_MISSING_FIGURE_UNIT_RE = re.compile(
    r"<div\b(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>",
    re.IGNORECASE,
)
P62_RECOVERED_TARGET_ELEMENT_RE = re.compile(
    r"<(?P<tag>p|div|span)\b(?P<attrs>[^>]*\bz2m-p62-recovered-target\b[^>]*)>"
    r"[\s\S]*?</(?P=tag)>",
    re.IGNORECASE,
)
P62_RECOVERY_SOURCE_RE = re.compile(
    r"\bdata-z2m-recovery-source\s*=\s*([\"'])(?P<source>.*?)\1",
    re.IGNORECASE | re.DOTALL,
)
P62_LOW_FIDELITY_RECOVERY_SOURCES = {"pdf_page_render"}
P62_DUPLICATE_REPAIRABLE_RECOVERY_SOURCES = {"marker_image"} | P62_LOW_FIDELITY_RECOVERY_SOURCES
P62_PDF_DERIVED_RECOVERY_SOURCES = {
    "pdf_page_render",
    "pdf_figure_region_render",
    "pdf_native_image",
    "pdf_detached_plate_region_render",
}
P62_UNRECOVERABLE_FALSE_MATCH_HINTS = {
    "toc_or_contents",
    "figure_caption_list",
    "manuscript_placeholder",
    "backmatter_or_reference_text",
    "prose_parenthetical_reference",
}
REF_TARGET_BLOCK_RE = re.compile(
    r"<(?P<tag>li|p|div)\b(?P<attrs>[^>]*\bid\s*=\s*([\"'])ref-(?P<num>\d{1,4})\3[^>]*)>"
    r"(?P<body>[\s\S]*?)</(?P=tag)>",
    re.IGNORECASE,
)
VISIBLE_REF_PREFIX_RE = re.compile(r"^\s*(?:\[\s*(?P<bracket>\d{1,4})\s*\]|(?P<plain>\d{1,4})[.)])")
AUTHOR_YEAR_NUMERIC_REF_ANCHOR_RE = re.compile(
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*([\"'])#ref-(?P<num>\d{1,4})\2[^>]*)>"
    r"(?P<body>[\s\S]{0,120}?)</a>",
    re.IGNORECASE,
)
AUTHOR_YEAR_REF_ANCHOR_RE = re.compile(
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*([\"'])#ref-(?P<num>\d{1,4})\2[^>]*)>"
    r"(?P<body>[\s\S]{0,180}?)</a>",
    re.IGNORECASE,
)
AUTHOR_YEAR_TEXT_RE = re.compile(
    r"\b[A-Z][A-Za-z'\u2019.-]+(?:\s+et\s+al\.?)?(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
AUTHOR_YEAR_SURNAME_FRAGMENT_RE = re.compile(r"^[A-Z][A-Za-z'\u2019.-]{3,}$")
AUTHOR_YEAR_RIGHT_CONTEXT_RE = re.compile(
    r"^\s*(?:et\s+al\.?|(?:and|&)\s+[A-Z][A-Za-z'\u2019.-]+)?\s*,?\s*\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
REFERENCES_HEADING_RE = re.compile(r"<h[1-6]\b[^>]*>\s*(?:References|Bibliography|Works cited)\s*</h[1-6]>", re.IGNORECASE)


def _manifest_article_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return quality_source_pdf.manifest_article_by_id(manifest)


def _configured_path_prefix_pairs() -> list[tuple[str, str]]:
    return quality_source_pdf.configured_path_prefix_pairs(ROOT)


def _host_path_candidates(value: str) -> list[Path]:
    return quality_source_pdf.host_path_candidates(value, repo_root=ROOT)


def _collect_pdf_path_strings(value: Any) -> list[str]:
    return quality_source_pdf.collect_pdf_path_strings(value)


def _source_export_dirs_from_stage_related_path(value: Any) -> list[Path]:
    return quality_source_pdf.source_export_dirs_from_stage_related_path(
        value,
        raw_stage=RAW_STAGE,
        polish_stage=POLISH_STAGE,
    )


def _pdf_candidates_from_source_export_dir(source_dir: Path) -> list[dict[str, Any]]:
    return quality_source_pdf.pdf_candidates_from_source_export_dir(source_dir, repo_root=ROOT)


def _zotero_root_paths() -> list[Path]:
    return quality_source_pdf.zotero_root_paths(repo_root=ROOT)


def _attachment_keys_from_article(article: str, manifest_article: dict[str, Any]) -> list[str]:
    return quality_source_pdf.attachment_keys_from_article(article, manifest_article)


def _pdf_candidates_from_zotero_storage(attachment_key: str) -> list[dict[str, Any]]:
    return quality_source_pdf.pdf_candidates_from_zotero_storage(attachment_key, repo_root=ROOT)


def _article_source_pdf_candidates(
    run_dir: Path,
    article: str,
    audit_summary: dict[str, Any],
    manifest_article: dict[str, Any],
) -> list[dict[str, Any]]:
    return quality_source_pdf.article_source_pdf_candidates(
        run_dir,
        article,
        audit_summary,
        manifest_article,
        repo_root=ROOT,
        raw_stage=RAW_STAGE,
        polish_stage=POLISH_STAGE,
    )


def write_source_pdf_map_for_run(
    run_dir: Path,
    manifest: dict[str, Any] | None = None,
    *,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Resolve source PDFs for audit text-layer diagnostics.

    The audit tree often does not contain ``00.source.pdf`` files, while the
    source run or Zotero storage still has the original PDF.  This map lets
    ``audit_en_polish.py --pdf-diagnostics`` use those external PDFs.
    """

    return quality_source_pdf.write_source_pdf_map_for_run(
        run_dir,
        manifest,
        out_path=out_path,
        repo_root=ROOT,
        raw_stage=RAW_STAGE,
        polish_stage=POLISH_STAGE,
        output_name=DEFAULT_SOURCE_PDF_MAP_NAME,
    )


def _pdf_text_pages(pdf_path: Path, *, max_pages: int | None = None) -> tuple[str, list[str], str | None]:
    return quality_pdf_utils.pdf_text_pages(pdf_path, max_pages=max_pages)


def _resolve_p62_pdf_page_for_figure(
    snippets: list[str],
    pages: list[str],
    figure_label: str,
    *,
    pdf_path: Path | None = None,
) -> dict[str, Any]:
    context = " ".join(snippets)
    resolved_label = _p62_full_figure_label_from_context(context, figure_label)
    candidate_labels = [label for label in dict.fromkeys([resolved_label, figure_label]) if label]
    snippet_tokens = _evidence_snippet_tokens(snippets)

    candidate_page_numbers: list[int] = []
    candidate_label_by_page: dict[int, str] = {}
    for label in candidate_labels:
        for page_number, page_text in enumerate(pages, start=1):
            if _figure_label_present_in_text_strict(page_text, label):
                if page_number not in candidate_label_by_page:
                    candidate_page_numbers.append(page_number)
                    candidate_label_by_page[page_number] = label
    if not candidate_page_numbers and figure_label:
        for page_number, page_text in enumerate(pages, start=1):
            if _figure_label_present_in_text(page_text, figure_label):
                candidate_page_numbers.append(page_number)
                candidate_label_by_page[page_number] = figure_label

    if not candidate_page_numbers:
        page_number, score = _best_pdf_text_page(snippets, pages)
        return {
            "page_number": page_number,
            "match_score": score,
            "label_pages": [],
            "resolved_figure_label": resolved_label,
            "candidates": [],
            "selected_false_match_hint": "",
            "source_visual_unavailable": False,
        }

    visual_summaries = (
        _p62_pdf_page_visual_summaries(pdf_path, candidate_page_numbers)
        if pdf_path is not None
        else {}
    )
    candidates: list[dict[str, Any]] = []
    for page_number in candidate_page_numbers:
        label = candidate_label_by_page.get(page_number) or resolved_label or figure_label
        page_text = pages[page_number - 1]
        text_score = _pdf_page_match_score(snippet_tokens, page_text)
        hint = _p62_false_page_match_hint(page_text, label)
        visual = visual_summaries.get(page_number, {})
        visual_count = int(visual.get("image_xrefs") or 0) + int(visual.get("image_blocks") or 0) + int(visual.get("drawings") or 0)
        caption_head_near_label = _p62_caption_head_present_near_label(page_text, label, snippets)
        caption_like = _p62_label_looks_caption_like(page_text, label) or caption_head_near_label
        effective_hint = "" if caption_like and hint == "prose_parenthetical_reference" else hint
        visual_score = min(0.45, 0.14 + float(visual_count) / 260.0) if visual_count else 0.0
        score = text_score
        if label == resolved_label and resolved_label != figure_label:
            score += 0.35
        if caption_like:
            score += 0.55
        score += visual_score
        if effective_hint in {"toc_or_contents", "figure_caption_list", "manuscript_placeholder"}:
            score -= 1.2
        elif effective_hint in {"prose_parenthetical_reference", "backmatter_or_reference_text"}:
            score -= 0.55
        if not visual_count:
            score -= 0.2
        candidates.append(
            {
                "page_number": page_number,
                "label": label,
                "match_score": round(float(text_score), 4),
                "rank_score": round(float(score), 4),
                "caption_like": caption_like,
                "caption_head_near_label": caption_head_near_label,
                "visual_score": round(float(visual_score), 4),
                "false_match_hint": effective_hint,
                "visual_summary": visual,
            }
        )
    candidates.sort(key=lambda item: (float(item.get("rank_score") or 0.0), -int(item.get("page_number") or 0)), reverse=True)
    visual_candidates = [
        item
        for item in candidates
        if not item.get("false_match_hint")
        and (
            int((item.get("visual_summary") or {}).get("image_xrefs") or 0)
            + int((item.get("visual_summary") or {}).get("image_blocks") or 0)
            + int((item.get("visual_summary") or {}).get("drawings") or 0)
        )
    ]
    selected = visual_candidates[0] if visual_candidates else candidates[0]
    visual_evidence_available = bool(visual_summaries)
    source_visual_unavailable = visual_evidence_available and bool(candidates) and not visual_candidates and all(
        item.get("false_match_hint") or not (
            int((item.get("visual_summary") or {}).get("image_xrefs") or 0)
            + int((item.get("visual_summary") or {}).get("image_blocks") or 0)
            + int((item.get("visual_summary") or {}).get("drawings") or 0)
        )
        for item in candidates
    )
    return {
        "page_number": int(selected.get("page_number") or 0),
        "match_score": float(selected.get("match_score") or 0.0),
        "label_pages": candidate_page_numbers[:20],
        "resolved_figure_label": selected.get("label") or resolved_label,
        "candidates": candidates[:12],
        "selected_false_match_hint": selected.get("false_match_hint") or "",
        "source_visual_unavailable": source_visual_unavailable,
    }


def _best_pdf_text_page_for_figure(
    snippets: list[str],
    pages: list[str],
    figure_label: str,
) -> tuple[int, float, list[int]]:
    label_pages = [
        index
        for index, page_text in enumerate(pages, start=1)
        if _figure_label_present_in_text(page_text, figure_label)
    ]
    if not label_pages:
        page_number, score = _best_pdf_text_page(snippets, pages)
        return page_number, score, []

    snippet_tokens = _evidence_snippet_tokens(snippets)
    best_page = label_pages[0]
    best_score = -1.0
    for page_number in label_pages:
        score = _pdf_page_match_score(snippet_tokens, pages[page_number - 1])
        if score > best_score:
            best_page = page_number
            best_score = score
    return best_page, max(0.0, best_score), label_pages


def _render_pdf_evidence_page(pdf_path: Path, page_number: int, out_path: Path, *, zoom: float) -> dict[str, Any]:
    return quality_pdf_utils.render_pdf_page(pdf_path, page_number, out_path, zoom=zoom)


def _problem_snippets_for_evidence(article: dict[str, Any]) -> list[str]:
    snippets: list[str] = []
    for defect in article.get("defects") or []:
        if isinstance(defect, dict) and defect.get("snippet"):
            snippets.append(_compact_observation_text(defect.get("snippet"), max_len=800))
    comparison = article.get("comparison") if isinstance(article.get("comparison"), dict) else {}
    if comparison.get("article") and comparison.get("score_delta"):
        snippets.append(f"comparison regression score_delta={comparison.get('score_delta')}")
    return [snippet for snippet in snippets if snippet]


def _attach_pdf_evidence_to_pack(pack: dict[str, Any], evidence_report: dict[str, Any]) -> dict[str, Any]:
    evidence_by_article = {
        str(item.get("article")): item
        for item in evidence_report.get("articles") or []
        if isinstance(item, dict) and item.get("article")
    }
    for article in pack.get("articles") or []:
        if isinstance(article, dict):
            article["pdf_problem_evidence"] = evidence_by_article.get(str(article.get("article")), {})
    pack["pdf_problem_evidence_stage"] = {
        "status": evidence_report.get("status"),
        "report_path": evidence_report.get("report_path"),
        "evidence_dir": evidence_report.get("evidence_dir"),
        "selected_count": evidence_report.get("selected_count", 0),
        "ready_count": evidence_report.get("ready_count", 0),
        "source_pdf_unavailable_count": evidence_report.get("source_pdf_unavailable_count", 0),
        "blocking_issue_count": evidence_report.get("blocking_issue_count", 0),
        "required_checks": evidence_report.get("required_checks", []),
    }
    return pack


def write_pdf_problem_evidence_stage(
    run_dir: Path,
    pack: dict[str, Any],
    *,
    gate_config: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Create PDF render/text-layer evidence requirements for selected problem articles."""

    gate_config = gate_config or load_gate_config()
    run_dir = run_dir.resolve(strict=False)
    out_path = out_path or (run_dir / DEFAULT_PDF_PROBLEM_EVIDENCE_NAME)
    evidence_dir = run_dir / "pdf_problem_evidence"
    max_articles = int(gate_config.get("pdf_problem_evidence_max_articles") or 0)
    selected_articles = list(pack.get("articles") or [])
    if max_articles > 0:
        selected_articles = selected_articles[:max_articles]
    zoom = float(gate_config.get("pdf_problem_evidence_render_zoom") or 1.5)
    max_pdf_pages = int(gate_config.get("pdf_problem_evidence_max_pdf_pages") or 80)
    allow_missing_source_pdf = bool(gate_config.get("pdf_problem_evidence_allow_missing_source_pdf", True))

    evidence_articles: list[dict[str, Any]] = []
    ready_count = 0
    unavailable_count = 0
    blocking_issue_count = 0

    for index, article in enumerate(selected_articles, start=1):
        article_id = str(article.get("article") or f"article_{index}")
        candidates = list(article.get("source_pdf_candidates") or [])
        selected_pdf = next((candidate for candidate in candidates if candidate.get("exists")), None)
        snippets = _problem_snippets_for_evidence(article)
        article_dir = evidence_dir / f"{index:03d}_{_slug(article_id, max_len=72)}"
        record: dict[str, Any] = {
            "article": article_id,
            "source_article": article.get("source_article"),
            "status": "source_pdf_unavailable",
            "source_pdf_available": bool(selected_pdf),
            "source_pdf_path": selected_pdf.get("path") if selected_pdf else "",
            "source_pdf_source": selected_pdf.get("source") if selected_pdf else "",
            "source_pdf_candidate_count": len(candidates),
            "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
            "problem_snippet_count": len(snippets),
            "problem_snippets": snippets[:8],
            "evidence_page": 0,
            "text_layer_status": "not_run",
            "text_layer_chars": 0,
            "text_layer_page_count": 0,
            "text_layer_page_limit": max_pdf_pages,
            "text_layer_truncated_to_limit": False,
            "text_layer_error": "",
            "text_layer_excerpt_path": "",
            "page_render_status": "not_run",
            "page_render_path": "",
            "page_render_error": "",
            "match_score": 0.0,
        }
        if not selected_pdf:
            unavailable_count += 1
            record["unavailable_reason"] = "No existing source PDF candidate was found."
            if not allow_missing_source_pdf:
                blocking_issue_count += 1
            evidence_articles.append(record)
            continue

        pdf_path = Path(str(selected_pdf.get("path") or "")).expanduser()
        text_status, pages, text_error = _pdf_text_pages(pdf_path, max_pages=max_pdf_pages)
        page_number, match_score = _best_pdf_text_page(snippets, pages)
        if page_number <= 0 and pages:
            page_number = 1
        text_excerpt_path = ""
        if page_number > 0 and pages:
            text_excerpt_path = str(article_dir / f"page_{page_number:04d}.txt")
            Path(text_excerpt_path).parent.mkdir(parents=True, exist_ok=True)
            Path(text_excerpt_path).write_text(pages[page_number - 1], encoding="utf-8", errors="replace")
        render = (
            _render_pdf_evidence_page(
                pdf_path,
                page_number or 1,
                article_dir / f"page_{(page_number or 1):04d}.png",
                zoom=zoom,
            )
            if page_number > 0 or pages
            else {"status": "no_page_to_render", "path": "", "error": "No page text was extracted."}
        )

        text_chars = sum(len(page_text) for page_text in pages)
        record.update(
            {
                "status": "ready",
                "evidence_page": page_number,
                "text_layer_status": text_status,
                "text_layer_chars": text_chars,
                "text_layer_page_count": len(pages),
                "text_layer_page_limit": max_pdf_pages,
                "text_layer_truncated_to_limit": len(pages) >= max_pdf_pages,
                "text_layer_error": text_error or "",
                "text_layer_excerpt_path": text_excerpt_path,
                "page_render_status": render.get("status"),
                "page_render_path": render.get("path"),
                "page_render_error": render.get("error") or "",
                "match_score": round(float(match_score), 4),
            }
        )
        if text_chars <= 0 or render.get("status") != "rendered":
            record["status"] = "incomplete"
            blocking_issue_count += 1
        else:
            ready_count += 1
        evidence_articles.append(record)

    if not selected_articles:
        status = "not_required"
    elif blocking_issue_count:
        status = "incomplete"
    else:
        status = "ready"
    report = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "report_path": str(out_path),
        "evidence_dir": str(evidence_dir),
        "status": status,
        "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
        "allow_missing_source_pdf": allow_missing_source_pdf,
        "selected_count": len(selected_articles),
        "ready_count": ready_count,
        "source_pdf_unavailable_count": unavailable_count,
        "blocking_issue_count": blocking_issue_count,
        "articles": evidence_articles,
    }
    _write_json(out_path, report)
    return report


def _path_text_variants(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    variants = [raw]
    try:
        repaired = raw.encode("cp1251").decode("utf-8")
    except UnicodeError:
        repaired = ""
    if repaired and repaired not in variants:
        variants.append(repaired)
    return variants


def _existing_path_candidates(value: Any) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    for variant in _path_text_variants(value):
        for candidate in _host_path_candidates(variant):
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.is_file():
                candidates.append(candidate)
    return candidates


def _index_polish_stage_files(run_dir: Path) -> list[Path]:
    roots = [run_dir / "polish", run_dir / "audit_tree"]
    files: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in (POLISH_STAGE, f"*.{POLISH_STAGE}"):
            try:
                matches = root.rglob(pattern)
                for path in matches:
                    if not path.is_file():
                        continue
                    key = str(path.resolve(strict=False))
                    if key in seen:
                        continue
                    seen.add(key)
                    files.append(path.resolve(strict=False))
            except OSError:
                continue
    return files


def _find_polish_stage_path_for_article(
    run_dir: Path,
    article_id: str,
    article: dict[str, Any],
    manifest_article: dict[str, Any],
    polish_index: list[Path],
) -> tuple[Path | None, str]:
    for item in (article, manifest_article):
        for key in ("polish_stage_path", "polish_path", "source_polish_path"):
            for candidate in _existing_path_candidates(item.get(key)):
                return candidate, f"{key}.declared"

    tokens = _attachment_keys_from_article(article_id, manifest_article)
    source_article = str(article.get("source_article") or manifest_article.get("article") or "")
    tokens.extend(_attachment_keys_from_article(source_article, manifest_article))
    tokens = [token for token in dict.fromkeys(tokens) if token]
    for token in tokens:
        for path in polish_index:
            path_text = str(path)
            if token in path.name or token in path_text:
                return path, f"indexed_attachment_key.{token}"

    return None, "missing"


def _clean_p62_context_fragment(fragment: str, *, max_len: int = 1400) -> str:
    fragment = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", fragment)
    fragment = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", fragment)
    fragment = re.sub(r"(?is)<img\b[^>]*>", " [image] ", fragment)
    text = _visible_html_text(fragment)
    text = re.sub(r"[A-Za-z0-9+/]{120,}={0,2}", " ", text)
    text = re.sub(
        r"\bFigure\s+[\w.-]+\s+image\s+was\s+not\s+extracted\s+into\s+this\s+HTML\.\s+"
        r"Please\s+check\s+the\s+original\s+PDF\s+for\s+the\s+missing\s+visual\s+content\.?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = P62_MISSING_WARNING_TEXT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _compact_observation_text(text, max_len=max_len)


def _p62_context_fragment(html: str, position: int, *, radius: int) -> str:
    div_start = html.rfind("<div", 0, position)
    div_end = html.find("</div>", position)
    if div_start >= 0 and div_end >= 0 and div_end - position <= max(radius * 2, 20000):
        candidate = html[div_start : div_end + len("</div>")]
        if "z2m-missing" in candidate[: min(len(candidate), position - div_start + 2000)].casefold():
            return candidate

    before = min(600, max(200, radius // 5))
    return html[max(0, position - before) : min(len(html), position + radius)]


def _p62_warning_context_from_html(
    html: str,
    defect: dict[str, Any],
    *,
    radius: int,
) -> tuple[str, str]:
    if not html:
        return "", "html_unavailable"
    extra = _defect_extra(defect)
    figure_label = str(extra.get("figure_label") or "").strip()
    warning_index = int(extra.get("warning_index") or 0)
    label_key = figure_label.casefold()

    regex_matches: list[tuple[int, str]] = []
    for match in P62_MISSING_WARNING_TEXT_RE.finditer(html):
        match_label = str(match.group("label") or "").casefold()
        if label_key and match_label != label_key:
            continue
        regex_matches.append((match.start(), "warning_text_regex"))
    if regex_matches:
        if warning_index > 0 and warning_index <= len(regex_matches):
            position, source = regex_matches[warning_index - 1]
        else:
            position, source = regex_matches[0]
        fragment = _p62_context_fragment(html, position, radius=radius)
        return _clean_p62_context_fragment(fragment), source

    snippet = str(defect.get("snippet") or "").strip()
    needles = [snippet]
    if figure_label:
        needles.append(f"Figure {figure_label} image was not extracted")
    html_lower = html.casefold()
    for needle in needles:
        if not needle:
            continue
        position = html.find(needle)
        if position < 0:
            position = html_lower.find(needle.casefold())
        if position >= 0:
            fragment = _p62_context_fragment(html, position, radius=radius)
            return _clean_p62_context_fragment(fragment), "snippet_match"

    missing_blocks = re.finditer(
        r"(?is)<(?P<tag>[a-z0-9]+)\b[^>]*\bz2m-missing[^>]*>.*?</(?P=tag)>",
        html,
    )
    for match in missing_blocks:
        visible = _visible_html_text(match.group(0))
        if figure_label and f"figure {figure_label}" not in visible.casefold():
            continue
        position = match.start()
        fragment = _p62_context_fragment(html, position, radius=radius)
        return _clean_p62_context_fragment(fragment), "missing_block_match"

    return "", "warning_not_found"


def _p62_recovery_snippets(
    html: str,
    defect: dict[str, Any],
    *,
    context_chars: int,
) -> tuple[list[str], str, str]:
    context, context_source = _p62_warning_context_from_html(
        html,
        defect,
        radius=max(800, context_chars),
    )
    snippets: list[str] = []
    if context:
        snippets.append(context)
    snippet = _compact_observation_text(defect.get("snippet"), max_len=400)
    if snippet and not context:
        snippets.append(snippet)
    extra = _defect_extra(defect)
    figure_label = str(extra.get("figure_label") or "").strip()
    if figure_label and context:
        snippets.append(f"Fig. {figure_label}")
    return snippets, context, context_source


def _selected_pdf_candidate(
    run_dir: Path,
    article_id: str,
    article: dict[str, Any],
    manifest_article: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    summary = article.get("summary") if isinstance(article.get("summary"), dict) else {}
    candidates = _article_source_pdf_candidates(run_dir, article_id, summary, manifest_article)
    selected = next((candidate for candidate in candidates if candidate.get("exists")), None)
    return selected, candidates


def _validate_p62_marker_output(marker_output_dir: Path, figure_label: str) -> dict[str, Any]:
    if not marker_output_dir.exists():
        return {
            "status": "not_run",
            "html_count": 0,
            "image_count": 0,
            "label_present": False,
            "html_paths": [],
            "image_paths": [],
        }

    html_paths = sorted(path for path in marker_output_dir.rglob("*.html") if path.is_file())
    image_paths = sorted(
        path
        for path in marker_output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    label_present = False
    for html_path in html_paths:
        try:
            text = _visible_html_text(html_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if _figure_label_present_in_text(text, figure_label):
            label_present = True
            break

    if label_present and image_paths:
        status = "recovered_image"
    elif label_present:
        status = "caption_only"
    elif image_paths:
        status = "image_without_label"
    else:
        status = "empty_or_unmatched"
    return {
        "status": status,
        "html_count": len(html_paths),
        "image_count": len(image_paths),
        "label_present": label_present,
        "html_paths": [str(path) for path in html_paths[:8]],
        "image_paths": [str(path) for path in image_paths[:8]],
    }


def write_p62_marker_recovery_plan(
    run_dir: Path,
    *,
    gate_config: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Build reproducible marker_single commands for source-backed P62 recovery."""

    gate_config = gate_config or load_gate_config()
    run_dir = run_dir.resolve(strict=False)
    out_path = out_path or (run_dir / DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME)
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

    audit = _load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    manifest = _load_json(run_dir / "manifest.json", default={})
    manifest_by_article = _manifest_article_by_id(manifest)
    polish_index = _index_polish_stage_files(run_dir)

    p62_items: list[tuple[dict[str, Any], dict[str, Any], int]] = []
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        for defect_index, defect in enumerate(article.get("defects_found") or [], start=1):
            if isinstance(defect, dict) and str(defect.get("id") or "") == "P62":
                p62_items.append((article, defect, defect_index))

    selected_items = p62_items[:max_items] if max_items > 0 else p62_items
    pdf_text_cache: dict[str, tuple[str, list[str], str | None]] = {}
    records: list[dict[str, Any]] = []

    for index, (article, defect, defect_index) in enumerate(selected_items, start=1):
        article_id = str(article.get("article") or f"article_{index}")
        manifest_article = manifest_by_article.get(article_id, {})
        extra = _defect_extra(defect)
        figure_label = str(extra.get("figure_label") or "").strip()
        article_dir = output_root / f"{index:03d}_{_slug(article_id, max_len=72)}"
        if figure_label:
            article_dir = article_dir / f"fig_{_slug(figure_label, max_len=20)}"

        selected_pdf, source_pdf_candidates = _selected_pdf_candidate(
            run_dir,
            article_id,
            article,
            manifest_article,
        )
        polish_path, polish_path_source = _find_polish_stage_path_for_article(
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

        snippets, polish_context, polish_context_source = _p62_recovery_snippets(
            polish_html,
            defect,
            context_chars=context_chars,
        )
        resolved_figure_label = _p62_full_figure_label_from_context(polish_context, figure_label)
        context_path = ""
        if polish_context:
            context_path = str(article_dir / "polish_context.txt")
            Path(context_path).parent.mkdir(parents=True, exist_ok=True)
            Path(context_path).write_text(polish_context + "\n", encoding="utf-8")

        record: dict[str, Any] = {
            "article": article_id,
            "source_article": article.get("source_article") or article_id,
            "defect_index": defect_index,
            "figure_label": figure_label,
            "resolved_figure_label": resolved_figure_label,
            "warning_index": extra.get("warning_index"),
            "warning_origin": extra.get("warning_origin") or extra.get("p62_subtype"),
            "status": "source_pdf_unavailable",
            "snippet": _compact_observation_text(defect.get("snippet"), max_len=300),
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
            pdf_text_cache[cache_key] = _pdf_text_pages(pdf_path, max_pages=max_pdf_pages)
        text_status, pages, text_error = pdf_text_cache[cache_key]
        resolver = _resolve_p62_pdf_page_for_figure(
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
                pdf_text_cache[full_cache_key] = _pdf_text_pages(pdf_path, max_pages=None)
            full_text_status, full_pages, full_text_error = pdf_text_cache[full_cache_key]
            full_resolver = _resolve_p62_pdf_page_for_figure(
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
                "existing_marker_output_validation": _validate_p62_marker_output(
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
        "generated_at": _now(),
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
    _write_json(out_path, report)
    return report


def _path_is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _remove_class_from_open_tag(open_tag: str, class_name: str) -> str:
    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        classes = [
            item
            for item in re.split(r"\s+", match.group(2).strip())
            if item and item != class_name
        ]
        if not classes:
            return ""
        return f"class={quote}{' '.join(classes)}{quote}"

    return re.sub(
        r"\bclass\s*=\s*(['\"])(.*?)\1",
        replace,
        open_tag,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _repair_p62_duplicate_figure_images(
    html: str,
    *,
    pdf_path: Path,
    artifact_dir: Path,
    zoom: float,
    repair_plain_duplicates: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    if not pdf_path.is_file():
        return html, []
    units = _p62_extract_html_figure_units(html)
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        for image_hash in unit.get("image_hashes") or []:
            by_hash.setdefault(str(image_hash), []).append(unit)

    duplicate_groups = [
        group
        for group in by_hash.values()
        if len({str(unit.get("label") or "") for unit in group}) > 1
    ]
    if not duplicate_groups:
        return html, []

    text_status, pages, text_error = _pdf_text_pages(pdf_path, max_pages=None)
    if text_status == "missing" or not pages:
        return html, []

    patched = html
    repairs: list[dict[str, Any]] = []
    repaired_labels: set[str] = set()
    for group in duplicate_groups:
        labels = [str(unit.get("label") or "") for unit in group if unit.get("label")]
        if not any(unit.get("recovery_sources") for unit in group) and not repair_plain_duplicates:
            continue
        plain_candidates = [unit for unit in group if not unit.get("recovery_sources")]
        repair_mode = "plain_duplicate_target"
        if not any(unit.get("recovery_sources") for unit in group):
            repair_mode = "plain_duplicate_group"
            candidates = list(group)
        elif plain_candidates:
            candidates = plain_candidates
        else:
            repair_mode = "recovered_duplicate_target"
            candidates = [
                unit
                for unit in group
                if set(str(source) for source in (unit.get("recovery_sources") or []))
                & P62_DUPLICATE_REPAIRABLE_RECOVERY_SOURCES
            ]
        for unit in candidates:
            label = str(unit.get("label") or "")
            if not label or label in repaired_labels:
                continue
            candidate_recovery_sources = [
                str(source) for source in (unit.get("recovery_sources") or []) if str(source)
            ]
            caption = str(unit.get("caption") or "")
            snippets = [caption] if caption else [f"Figure {label}"]
            resolver = _resolve_p62_pdf_page_for_figure(snippets, pages, label, pdf_path=pdf_path)
            page_number = int(resolver.get("page_number") or 0)
            duplicate_hash = str((unit.get("image_hashes") or [""])[0])
            if page_number <= 0 or bool(resolver.get("source_visual_unavailable")):
                repairs.append(
                    {
                        "figure_label": label,
                        "status": "unresolved",
                        "reason": "pdf_page_unavailable_or_source_visual_unavailable",
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "text_layer_status": text_status,
                        "text_layer_error": text_error or "",
                    }
                )
                continue
            repair_dir = artifact_dir / "duplicate_visual_repair" / f"fig_{_slug(label, max_len=20)}"
            asset = _recover_p62_detached_pdf_figure_plate_asset(
                pdf_path,
                page_number,
                label,
                repair_dir,
                zoom=zoom,
            )
            if not (asset.get("path") and asset.get("source")):
                asset = _recover_p62_pdf_figure_asset(
                    pdf_path,
                    page_number,
                    label,
                    repair_dir,
                    zoom=zoom,
                )
            asset_path = Path(str(asset.get("path") or ""))
            data_url = _data_url_from_image_file(asset_path) if asset_path else None
            if not data_url or not asset.get("source"):
                repairs.append(
                    {
                        "figure_label": label,
                        "status": asset.get("status") or "unresolved",
                        "reason": asset.get("error") or "no_recoverable_duplicate_asset",
                        "source_pdf_page_number": page_number,
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "resolver": resolver,
                    }
                )
                continue
            next_html, replacements = _replace_p62_figure_unit_target_with_image(
                patched,
                figure_label=label,
                data_url=data_url,
                source=str(asset.get("source") or ""),
                source_detail=str(asset_path),
            )
            if not replacements:
                repairs.append(
                    {
                        "figure_label": label,
                        "status": "patch_missed",
                        "reason": "figure_unit_target_not_found",
                        "source_pdf_page_number": page_number,
                        "duplicate_labels": labels,
                        "duplicate_hash": duplicate_hash,
                        "repair_mode": repair_mode,
                        "candidate_recovery_sources": candidate_recovery_sources,
                        "asset_path": str(asset_path),
                        "asset_source": asset.get("source") or "",
                    }
                )
                continue
            patched = next_html
            repaired_labels.add(label)
            repairs.append(
                {
                    "figure_label": label,
                    "status": "patched",
                    "source_pdf_page_number": page_number,
                    "duplicate_labels": labels,
                    "duplicate_hash": duplicate_hash,
                    "repair_mode": repair_mode,
                    "candidate_recovery_sources": candidate_recovery_sources,
                    "asset_path": str(asset_path),
                    "asset_source": asset.get("source") or "",
                    "asset_status": asset.get("status") or "",
                    "resolver": resolver,
                    "replacement_count": replacements,
                }
            )
    return patched, repairs


def _apply_p62_duplicate_figure_image_repairs(
    targets: list[Path],
    *,
    pdf_path: Path,
    artifact_dir: Path,
    zoom: float,
    repair_plain_duplicates: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "repair_count": 0,
        "patched_paths": [],
        "repairs": [],
        "errors": [],
    }
    if not targets or not pdf_path.is_file():
        return report
    for target_path in targets:
        try:
            html = target_path.read_text(encoding="utf-8", errors="replace")
            patched, repairs = _repair_p62_duplicate_figure_images(
                html,
                pdf_path=pdf_path,
                artifact_dir=artifact_dir / _slug(target_path.stem, max_len=48),
                zoom=zoom,
                repair_plain_duplicates=repair_plain_duplicates,
            )
            patched_repairs = [repair for repair in repairs if repair.get("status") == "patched"]
            if patched_repairs and patched != html:
                target_path.write_text(patched, encoding="utf-8")
                report["patched_paths"].append(str(target_path))
                report["repair_count"] += sum(int(repair.get("replacement_count") or 0) for repair in patched_repairs)
            for repair in repairs:
                report["repairs"].append({"path": str(target_path), **repair})
        except OSError as exc:
            report["errors"].append({"path": str(target_path), "error": str(exc)})
    return report


def _html_has_p62_missing_warning_for_label(html: str, figure_label: str) -> bool:
    matches = list(P62_MISSING_WARNING_ELEMENT_RE.finditer(html))
    if not matches:
        return False
    if not figure_label:
        return True
    return any(
        _figure_label_present_in_text(_visible_html_text(match.group(0)), figure_label)
        for match in matches
    )


def _data_url_from_image_file(path: Path) -> str | None:
    return quality_pdf_utils.data_url_from_image_file(path)


def _first_valid_image_path(validation: dict[str, Any]) -> Path | None:
    return quality_pdf_utils.first_valid_image_path(validation)


def _execute_p62_marker_command(
    record: dict[str, Any],
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    return _execute_p62_marker_command_impl(record, timeout_seconds=timeout_seconds, cwd=ROOT)


def _p62_render_fallback_page_number(
    pdf_path: Path,
    source_page_number: int,
    figure_label: str,
) -> tuple[int, str]:
    page_number = max(1, int(source_page_number or 1))
    label = str(figure_label or "").strip()
    if not label or page_number <= 1:
        return page_number, "primary_matched_page"

    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number > len(doc):
                return page_number, "primary_page_out_of_text_limit"
            page = doc.load_page(page_number - 1)
            rects = []
            for needle in (f"Figure {label}", f"Fig. {label}", f"Fig {label}"):
                rects.extend(page.search_for(needle))
            if not rects:
                return page_number, "primary_matched_page"
            top_ratio = min(float(rect.y0) for rect in rects) / max(1.0, float(page.rect.height))
            if top_ratio <= 0.22:
                return page_number - 1, "caption_near_page_top_previous_page"
            return page_number, "caption_on_primary_page"
        finally:
            doc.close()
    except Exception:
        return page_number, "primary_matched_page"


def _p62_record_allows_page_render_fallback(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or "")
    if status in {"source_visual_unavailable", "figure_label_page_unavailable"}:
        return False
    if status == "ready":
        return True
    label_pages = record.get("figure_label_pdf_page_candidates")
    return bool(label_pages)


def _p62_false_match_hint_blocks_asset_recovery(
    hint: str,
    *,
    caption_found: bool = False,
) -> bool:
    value = str(hint or "")
    if value == "prose_parenthetical_reference" and caption_found:
        return False
    return value in P62_UNRECOVERABLE_FALSE_MATCH_HINTS


def _p62_pdf_page_false_match_hint(pdf_path: Path, page_number: int, figure_label: str) -> str:
    label = str(figure_label or "").strip()
    if not label or not pdf_path.is_file() or page_number <= 0:
        return ""
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number > len(doc):
                return ""
            page_text = str(doc.load_page(page_number - 1).get_text("text") or "")
        finally:
            doc.close()
    except Exception:
        return ""
    return _p62_false_page_match_hint(page_text, label)


def _p62_pdf_page_caption_label_found(pdf_path: Path, page_number: int, figure_label: str) -> bool:
    label = str(figure_label or "").strip()
    if not label or not pdf_path.is_file() or page_number <= 0:
        return False
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number > len(doc):
                return False
            page = doc.load_page(page_number - 1)
            return bool(_p62_page_caption_label_rects(page, label))
        finally:
            doc.close()
    except Exception:
        return False


def _p62_pdf_visual_inventory(pdf_path: Path) -> dict[str, Any]:
    if not pdf_path.is_file():
        return {
            "status": "missing_pdf",
            "page_count": 0,
            "native_image_count": 0,
            "large_image_count": 0,
            "pages_with_native_images": [],
            "pages_with_large_images": [],
            "error": "",
        }
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            native_pages: list[dict[str, Any]] = []
            large_pages: list[dict[str, Any]] = []
            native_count = 0
            large_count = 0
            for page_index in range(len(doc)):
                page = doc.load_page(page_index)
                images = page.get_images(full=True)
                large_images = _p62_large_image_rects(page)
                native_count += len(images)
                large_count += len(large_images)
                if images:
                    native_pages.append({"page_number": page_index + 1, "count": len(images)})
                if large_images:
                    large_pages.append({"page_number": page_index + 1, "count": len(large_images)})
            return {
                "status": "ready",
                "page_count": len(doc),
                "native_image_count": native_count,
                "large_image_count": large_count,
                "pages_with_native_images": native_pages[:40],
                "pages_with_large_images": large_pages[:40],
                "error": "",
            }
        finally:
            doc.close()
    except ImportError as exc:
        return {
            "status": "renderer_unavailable",
            "page_count": 0,
            "native_image_count": 0,
            "large_image_count": 0,
            "pages_with_native_images": [],
            "pages_with_large_images": [],
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - PDF-specific
        return {
            "status": "inventory_error",
            "page_count": 0,
            "native_image_count": 0,
            "large_image_count": 0,
            "pages_with_native_images": [],
            "pages_with_large_images": [],
            "error": str(exc),
        }


def _p62_pypdf_image_inventory(pdf_path: Path) -> dict[str, Any]:
    if not pdf_path.is_file():
        return {
            "status": "missing_pdf",
            "page_count": 0,
            "image_count": 0,
            "pages_with_images": [],
            "errors": [],
        }
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        pages_with_images: list[dict[str, Any]] = []
        errors: list[str] = []
        image_count = 0
        for index, page in enumerate(reader.pages, start=1):
            try:
                images = list(getattr(page, "images", []) or [])
            except Exception as exc:  # pragma: no cover - PDF-specific
                errors.append(f"page {index}: {exc}")
                images = []
            image_count += len(images)
            if images:
                pages_with_images.append({"page_number": index, "count": len(images)})
        return {
            "status": "ready" if not errors else "partial",
            "page_count": len(reader.pages),
            "image_count": image_count,
            "pages_with_images": pages_with_images[:40],
            "errors": errors[:8],
        }
    except ImportError as exc:
        return {
            "status": "parser_unavailable",
            "page_count": 0,
            "image_count": 0,
            "pages_with_images": [],
            "errors": [str(exc)],
        }
    except Exception as exc:  # pragma: no cover - PDF-specific
        return {
            "status": "inventory_error",
            "page_count": 0,
            "image_count": 0,
            "pages_with_images": [],
            "errors": [str(exc)],
        }


def _p62_external_pdf_tool_inventory() -> dict[str, Any]:
    tools = {}
    for tool_name in ("pdfimages", "mutool", "pdfinfo", "pdftoppm"):
        tools[tool_name] = {"available": bool(shutil.which(tool_name))}
    return {"status": "ready", "tools": tools}


def _probe_p62_source_visual_unavailable(
    pdf_path: Path,
    figure_label: str,
    artifact_dir: Path,
    *,
    snippets: list[str] | None = None,
    zoom: float,
    run_marker: bool = False,
    marker_timeout_seconds: int = 300,
    marker_output_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify whether a source visual can still be recovered for an unavailable P62 record."""

    label = str(figure_label or "").strip()
    report: dict[str, Any] = {
        "status": "not_found",
        "figure_label": label,
        "source_pdf_path": str(pdf_path) if pdf_path else "",
        "text_layer_status": "not_run",
        "text_layer_error": "",
        "text_layer_page_count": 0,
        "label_pages": [],
        "attempts": [],
        "visual_inventory": {"status": "not_run"},
        "pypdf_image_inventory": {"status": "not_run"},
        "external_tool_inventory": {"status": "not_run"},
        "marker_execution": {"status": "not_run"},
        "marker_output_validation": {"status": "not_run"},
        "asset": {},
    }
    if not label:
        report["status"] = "missing_figure_label"
        return report
    if not pdf_path.is_file():
        report["status"] = "missing_pdf"
        return report

    artifact_dir.mkdir(parents=True, exist_ok=True)
    text_status, pages, text_error = _pdf_text_pages(pdf_path, max_pages=None)
    report.update(
        {
            "text_layer_status": text_status,
            "text_layer_error": text_error or "",
            "text_layer_page_count": len(pages),
        }
    )
    strict_pages = [
        page_number
        for page_number, page_text in enumerate(pages, start=1)
        if _figure_label_present_in_text_strict(page_text, label)
    ]
    loose_pages = [
        page_number
        for page_number, page_text in enumerate(pages, start=1)
        if page_number not in strict_pages and _figure_label_present_in_text(page_text, label)
    ]
    label_pages = strict_pages + loose_pages
    report["label_pages"] = label_pages[:40]

    if label_pages:
        visual_summaries = _p62_pdf_page_visual_summaries(pdf_path, label_pages)
        for page_number in label_pages:
            page_text = pages[page_number - 1] if page_number <= len(pages) else ""
            hint = _p62_false_page_match_hint(page_text, label)
            caption_found = _p62_pdf_page_caption_label_found(pdf_path, page_number, label)
            visual_summary = visual_summaries.get(page_number, {})
            attempt: dict[str, Any] = {
                "method": "pdf_label_page_asset",
                "page_number": page_number,
                "false_match_hint": hint,
                "caption_found": caption_found,
                "visual_summary": visual_summary,
                "status": "not_run",
            }
            if _p62_false_match_hint_blocks_asset_recovery(hint, caption_found=caption_found):
                attempt["status"] = "skipped_false_label_match"
                report["attempts"].append(attempt)
                continue

            page_artifact_dir = artifact_dir / f"page_{page_number:04d}"
            asset = _recover_p62_detached_pdf_figure_plate_asset(
                pdf_path,
                page_number,
                label,
                page_artifact_dir,
                zoom=zoom,
            )
            if not (asset.get("path") and asset.get("source")):
                asset = _recover_p62_pdf_figure_asset(
                    pdf_path,
                    page_number,
                    label,
                    page_artifact_dir,
                    zoom=zoom,
                )
            attempt.update(
                {
                    "status": asset.get("status") or "not_found",
                    "asset_path": asset.get("path") or "",
                    "asset_source": asset.get("source") or "",
                    "error": asset.get("error") or "",
                }
            )
            report["attempts"].append(attempt)
            if asset.get("path") and asset.get("source") and _data_url_from_image_file(Path(str(asset.get("path")))):
                report["status"] = "found_asset"
                report["asset"] = asset
                return report
    else:
        report["attempts"].append(
            {
                "method": "pdf_label_page_asset",
                "status": "skipped_no_label_pages",
                "page_number": 0,
                "false_match_hint": "",
            }
        )

    report["visual_inventory"] = _p62_pdf_visual_inventory(pdf_path)
    report["pypdf_image_inventory"] = _p62_pypdf_image_inventory(pdf_path)
    report["external_tool_inventory"] = _p62_external_pdf_tool_inventory()

    if run_marker:
        marker_output_dir = marker_output_dir or (artifact_dir / "marker_full_pdf")
        marker_record = {
            "marker_output_dir": str(marker_output_dir),
            "marker_command": build_marker_single_command(
                pdf_path,
                marker_output_dir,
                "html",
                page_range=None,
                disable_multiprocessing=True,
            ),
        }
        existing_execution_path = marker_output_dir / "marker_execution_report.json"
        if existing_execution_path.is_file():
            existing_execution = _load_json(existing_execution_path, default={})
            report["marker_execution"] = {
                **existing_execution,
                "status": f"reused_{existing_execution.get('status') or 'unknown'}",
            }
        else:
            report["marker_execution"] = _execute_p62_marker_command(
                marker_record,
                timeout_seconds=marker_timeout_seconds,
            )
        marker_validation = _validate_p62_marker_output(marker_output_dir, label)
        report["marker_output_validation"] = marker_validation
        marker_image = (
            _first_valid_image_path(marker_validation)
            if marker_validation.get("status") == "recovered_image"
            else None
        )
        if marker_image is not None:
            report["status"] = "found_asset"
            report["asset"] = {
                "status": "marker_image_recovered",
                "path": str(marker_image),
                "source": "marker_image",
                "error": "",
            }
            return report

    return report


def _recover_p62_pdf_figure_asset(
    pdf_path: Path,
    page_number: int,
    figure_label: str,
    artifact_dir: Path,
    *,
    zoom: float,
) -> dict[str, Any]:
    if not pdf_path.is_file():
        return {"status": "missing_pdf", "path": "", "source": "", "error": ""}
    label = str(figure_label or "").strip()
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number < 1 or page_number > len(doc):
                return {
                    "status": "page_out_of_range",
                    "path": "",
                    "source": "",
                    "error": f"page {page_number} outside 1..{len(doc)}",
                }
            page = doc.load_page(page_number - 1)
            page_area = max(1.0, float(page.rect.width) * float(page.rect.height))
            caption_label_rects = _p62_page_caption_label_rects(page, label)
            caption_rects = caption_label_rects or _p62_page_label_rects(page, label)
            false_match_hint = _p62_false_page_match_hint(str(page.get_text("text") or ""), label)
            if _p62_false_match_hint_blocks_asset_recovery(
                false_match_hint,
                caption_found=bool(caption_label_rects),
            ):
                return {
                    "status": f"false_label_match_{false_match_hint}",
                    "path": "",
                    "source": "",
                    "error": "Matched PDF page is a false figure-label location, not a recoverable visual.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rects),
                    "false_match_hint": false_match_hint,
                }
            caption_rect = _fitz_union_rect(caption_rects) if caption_rects else None
            graphics = _p62_page_graphic_rects(page)
            selected = _p62_select_graphic_rects_for_caption(page.rect, graphics, caption_rect)
            if not selected:
                text_region = _p62_text_figure_region_for_caption(page, caption_rect)
                if text_region is not None:
                    text_region = _p62_expand_rect(
                        text_region,
                        page.rect,
                        margin=max(4.0, min(page.rect.width, page.rect.height) * 0.01),
                    )
                    if _fitz_rect_area(text_region) > page_area * 0.001:
                        out_path = artifact_dir / f"fig_{_slug(label or 'unknown', max_len=20)}_pdf_text_region_page_{page_number:04d}.png"
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(float(zoom), float(zoom)), clip=text_region, alpha=False)
                        pixmap.save(str(out_path))
                        if _data_url_from_image_file(out_path) is not None:
                            return {
                                "status": "text_region_rendered",
                                "path": str(out_path),
                                "source": "pdf_figure_region_render",
                                "error": "",
                                "page_number": page_number,
                                "caption_found": bool(caption_rect),
                                "selected_rect": _fitz_rect_tuple(text_region),
                                "graphic_count": len(graphics),
                                "selected_graphic_count": 0,
                            }
                return {
                    "status": "no_figure_region",
                    "path": "",
                    "source": "",
                    "error": "No graphic/image region could be associated with the target caption.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rect),
                    "graphic_count": len(graphics),
                }

            image_candidates = [item for item in selected if item.get("kind") == "image" and item.get("xref")]
            selected_area = sum(_fitz_rect_area(item["rect"]) for item in selected)
            drawing_count = sum(1 for item in selected if item.get("kind") == "drawing")
            if (
                len(image_candidates) == 1
                and drawing_count == 0
                and selected_area >= page_area * 0.01
            ):
                extracted = doc.extract_image(int(image_candidates[0]["xref"]))
                data = extracted.get("image")
                ext = str(extracted.get("ext") or "png").lower().lstrip(".")
                if data:
                    out_path = artifact_dir / f"fig_{_slug(label or 'unknown', max_len=20)}_pdf_native_page_{page_number:04d}.{ext}"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(data)
                    if _data_url_from_image_file(out_path) is not None:
                        return {
                            "status": "native_image_extracted",
                            "path": str(out_path),
                            "source": "pdf_native_image",
                            "error": "",
                            "page_number": page_number,
                            "caption_found": bool(caption_rect),
                            "selected_rect": _fitz_rect_tuple(image_candidates[0]["rect"]),
                            "graphic_count": len(graphics),
                        }

            region = _fitz_union_rect([item["rect"] for item in selected])
            region = _p62_expand_rect(region, page.rect, margin=max(4.0, min(page.rect.width, page.rect.height) * 0.01))
            region = _p62_include_nearby_text_blocks(page, region, caption_rect)
            region = _p62_expand_rect(region, page.rect, margin=max(3.0, min(page.rect.width, page.rect.height) * 0.006))
            if _fitz_rect_area(region) <= page_area * 0.001:
                return {
                    "status": "figure_region_too_small",
                    "path": "",
                    "source": "",
                    "error": "Associated figure region is too small.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rect),
                    "selected_rect": _fitz_rect_tuple(region),
                }
            out_path = artifact_dir / f"fig_{_slug(label or 'unknown', max_len=20)}_pdf_region_page_{page_number:04d}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(float(zoom), float(zoom)), clip=region, alpha=False)
            pixmap.save(str(out_path))
            if _data_url_from_image_file(out_path) is None:
                return {
                    "status": "region_render_invalid",
                    "path": str(out_path),
                    "source": "",
                    "error": "Rendered region did not produce a valid image.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rect),
                    "selected_rect": _fitz_rect_tuple(region),
                }
            return {
                "status": "region_rendered",
                "path": str(out_path),
                "source": "pdf_figure_region_render",
                "error": "",
                "page_number": page_number,
                "caption_found": bool(caption_rect),
                "selected_rect": _fitz_rect_tuple(region),
                "graphic_count": len(graphics),
                "selected_graphic_count": len(selected),
            }
        finally:
            doc.close()
    except ImportError as exc:
        return {"status": "renderer_unavailable", "path": "", "source": "", "error": str(exc)}
    except Exception as exc:  # pragma: no cover - PDF/render specific
        return {"status": "figure_asset_error", "path": "", "source": "", "error": str(exc)}


def _recover_p62_detached_pdf_figure_plate_asset(
    pdf_path: Path,
    anchor_page_number: int,
    figure_label: str,
    artifact_dir: Path,
    *,
    zoom: float,
) -> dict[str, Any]:
    label_index = _p62_simple_numeric_figure_index(figure_label)
    if label_index <= 0:
        return {"status": "not_numeric_figure_label", "path": "", "source": "", "error": ""}
    if not pdf_path.is_file():
        return {"status": "missing_pdf", "path": "", "source": "", "error": ""}
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if anchor_page_number < 1 or anchor_page_number > len(doc):
                return {
                    "status": "page_out_of_range",
                    "path": "",
                    "source": "",
                    "error": f"page {anchor_page_number} outside 1..{len(doc)}",
                }
            anchor_page = doc.load_page(anchor_page_number - 1)
            anchor_text = str(anchor_page.get_text("text") or "").casefold()
            if "accepted article" not in anchor_text:
                return {"status": "not_detached_plate_pattern", "path": "", "source": "", "error": ""}
            if _p62_large_image_rects(anchor_page):
                return {"status": "anchor_page_has_large_image", "path": "", "source": "", "error": ""}

            plates: list[dict[str, Any]] = []
            for page_index in range(anchor_page_number - 1, len(doc)):
                page = doc.load_page(page_index)
                text = str(page.get_text("text") or "").strip()
                text_blocks = sum(
                    1
                    for block in (page.get_text("dict") or {}).get("blocks") or []
                    if block.get("type") == 0
                )
                if text_blocks > 8 and len(text) > 1600:
                    continue
                for image in _p62_large_image_rects(page):
                    plates.append(
                        {
                            "page_number": page_index + 1,
                            "rect": image["rect"],
                            "xref": image.get("xref") or 0,
                            "area_ratio": image.get("area_ratio") or 0.0,
                        }
                    )
            plates.sort(
                key=lambda item: (
                    int(item.get("page_number") or 0),
                    float(item["rect"].y0),
                    float(item["rect"].x0),
                )
            )
            if len(plates) < label_index:
                return {
                    "status": "detached_plate_not_found",
                    "path": "",
                    "source": "",
                    "error": f"found {len(plates)} plate images, need figure index {label_index}",
                    "plate_count": len(plates),
                }
            chosen = plates[label_index - 1]
            page_number = int(chosen["page_number"])
            page = doc.load_page(page_number - 1)
            rect = _p62_expand_rect(chosen["rect"], page.rect, margin=3.0)
            out_path = artifact_dir / f"fig_{_slug(figure_label or 'unknown', max_len=20)}_pdf_plate_page_{page_number:04d}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(float(zoom), float(zoom)), clip=rect, alpha=False)
            pixmap.save(str(out_path))
            if _data_url_from_image_file(out_path) is None:
                return {
                    "status": "detached_plate_render_invalid",
                    "path": str(out_path),
                    "source": "",
                    "error": "Rendered detached plate did not produce a valid image.",
                    "page_number": page_number,
                    "selected_rect": _fitz_rect_tuple(rect),
                }
            return {
                "status": "detached_plate_rendered",
                "path": str(out_path),
                "source": "pdf_detached_plate_region_render",
                "error": "",
                "page_number": page_number,
                "anchor_page_number": anchor_page_number,
                "selected_rect": _fitz_rect_tuple(rect),
                "plate_count": len(plates),
                "plate_index": label_index,
            }
        finally:
            doc.close()
    except ImportError as exc:
        return {"status": "renderer_unavailable", "path": "", "source": "", "error": str(exc)}
    except Exception as exc:  # pragma: no cover - PDF/render specific
        return {"status": "detached_plate_error", "path": "", "source": "", "error": str(exc)}


def _p62_simple_numeric_figure_index(figure_label: str) -> int:
    label = str(figure_label or "").strip()
    if not re.fullmatch(r"\d{1,3}", label):
        return 0
    value = int(label)
    return value if value > 0 else 0


def _p62_large_image_rects(page: Any) -> list[dict[str, Any]]:
    page_area = max(1.0, float(page.rect.width) * float(page.rect.height))
    images: list[dict[str, Any]] = []
    seen: set[tuple[int, tuple[float, float, float, float]]] = set()
    try:
        for image_info in page.get_images(full=True):
            xref = int(image_info[0])
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            for rect in rects:
                area_ratio = _fitz_rect_area(rect) / page_area
                key = (xref, _fitz_rect_tuple(rect))
                if area_ratio < 0.04 or key in seen:
                    continue
                seen.add(key)
                images.append({"xref": xref, "rect": rect, "area_ratio": area_ratio})
    except Exception:
        return images
    return images


def _p62_page_caption_label_rects(page: Any, figure_label: str) -> list[Any]:
    label = str(figure_label or "").strip()
    if not label:
        return []
    caption_pattern = re.compile(
        rf"^\s*(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?![\w-]|\.[A-Za-z0-9])(?:\s*[.:|]\s*|\s+)",
        re.IGNORECASE,
    )
    rects: list[Any] = []
    try:
        import fitz  # type: ignore[import-not-found]

        blocks = (page.get_text("dict") or {}).get("blocks") or []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines") or []:
                text = "".join(span.get("text", "") for span in line.get("spans") or [])
                if not caption_pattern.search(text):
                    continue
                bbox = line.get("bbox") or block.get("bbox")
                if bbox:
                    rects.append(fitz.Rect(bbox))
    except Exception:
        return rects
    return rects


def _p62_page_label_rects(page: Any, figure_label: str) -> list[Any]:
    label = str(figure_label or "").strip()
    if not label:
        return []
    rects: list[Any] = []
    for needle in (f"Figure {label}", f"FIGURE {label}", f"Fig. {label}", f"Fig {label}"):
        try:
            rects.extend(page.search_for(needle))
        except Exception:
            continue
    return rects


def _p62_page_graphic_rects(page: Any) -> list[dict[str, Any]]:
    graphics: list[dict[str, Any]] = []
    seen: set[tuple[str, int, tuple[float, float, float, float]]] = set()
    try:
        for image_info in page.get_images(full=True):
            xref = int(image_info[0])
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            for rect in rects:
                key = ("image", xref, _fitz_rect_tuple(rect))
                if key not in seen and _fitz_rect_area(rect) > 1.0:
                    seen.add(key)
                    graphics.append({"kind": "image", "xref": xref, "rect": rect})
    except Exception:
        pass
    try:
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect is None or _fitz_rect_area(rect) <= 4.0:
                continue
            key = ("drawing", 0, _fitz_rect_tuple(rect))
            if key in seen:
                continue
            seen.add(key)
            graphics.append({"kind": "drawing", "xref": 0, "rect": rect})
    except Exception:
        pass
    return graphics


def _p62_select_graphic_rects_for_caption(
    page_rect: Any,
    graphics: list[dict[str, Any]],
    caption_rect: Any | None,
) -> list[dict[str, Any]]:
    if not graphics:
        return []
    page_height = max(1.0, float(page_rect.height))
    page_width = max(1.0, float(page_rect.width))
    page_area = page_width * page_height
    if caption_rect is None:
        return sorted(graphics, key=lambda item: _fitz_rect_area(item["rect"]), reverse=True)[:8]

    above: list[tuple[float, dict[str, Any]]] = []
    below: list[tuple[float, dict[str, Any]]] = []
    overlapping: list[tuple[float, dict[str, Any]]] = []
    for item in graphics:
        rect = item["rect"]
        area = _fitz_rect_area(rect)
        if area < max(4.0, page_area * 0.00005):
            continue
        x_overlap = _fitz_x_overlap_ratio(rect, caption_rect)
        if x_overlap <= 0 and area < page_area * 0.03:
            continue
        if rect.y1 <= caption_rect.y0 + 3:
            distance = max(0.0, float(caption_rect.y0 - rect.y1))
            if distance <= page_height * 0.62:
                above.append((distance - min(0.3, x_overlap) * 40.0, item))
        elif rect.y0 >= caption_rect.y1 - 3:
            distance = max(0.0, float(rect.y0 - caption_rect.y1))
            if distance <= page_height * 0.62:
                below.append((distance - min(0.3, x_overlap) * 40.0, item))
        else:
            overlapping.append((0.0, item))

    chosen_pool = above if above else below if below else overlapping
    if not chosen_pool:
        return sorted(graphics, key=lambda item: _fitz_rect_area(item["rect"]), reverse=True)[:8]
    chosen_pool.sort(key=lambda item: item[0])
    nearest_distance = chosen_pool[0][0]
    selected = [
        item
        for distance, item in chosen_pool
        if distance <= nearest_distance + page_height * 0.28
    ]
    if not selected:
        selected = [chosen_pool[0][1]]
    return selected


def _p62_text_figure_region_for_caption(page: Any, caption_rect: Any | None) -> Any | None:
    if caption_rect is None:
        return None
    try:
        import fitz  # type: ignore[import-not-found]

        blocks = (page.get_text("dict") or {}).get("blocks") or []
    except Exception:
        return None
    page_height = max(1.0, float(page.rect.height))
    page_width = max(1.0, float(page.rect.width))
    min_y = max(0.0, float(caption_rect.y0) - page_height * 0.48)
    candidates: list[Any] = []
    for block in blocks:
        if block.get("type") != 0 or not block.get("bbox"):
            continue
        try:
            rect = fitz.Rect(block.get("bbox"))
        except Exception:
            continue
        if _fitz_rects_intersect(rect, caption_rect):
            continue
        if rect.y1 > caption_rect.y0 + 3:
            continue
        if rect.y1 < min_y:
            continue
        if rect.width < page_width * 0.18 or rect.height < 5:
            continue
        if _fitz_x_overlap_ratio(rect, caption_rect) <= 0 and rect.width < page_width * 0.55:
            continue
        candidates.append(rect)
    if not candidates:
        return None
    region = _fitz_union_rect(candidates)
    if _fitz_rect_area(region) < page_width * page_height * 0.01:
        return None
    return region


def _p62_include_nearby_text_blocks(page: Any, region: Any, caption_rect: Any | None) -> Any:
    try:
        blocks = (page.get_text("dict") or {}).get("blocks") or []
    except Exception:
        return region
    expanded = _p62_expand_rect(region, page.rect, margin=12.0)
    rects = [region]
    for block in blocks:
        if block.get("type") != 0 or not block.get("bbox"):
            continue
        try:
            import fitz  # type: ignore[import-not-found]

            rect = fitz.Rect(block.get("bbox"))
        except Exception:
            continue
        if caption_rect is not None and _fitz_rects_intersect(rect, caption_rect):
            continue
        if _fitz_rects_intersect(rect, expanded):
            rects.append(rect)
    return _fitz_union_rect(rects)


def _fitz_rect_area(rect: Any) -> float:
    return max(0.0, float(rect.width)) * max(0.0, float(rect.height))


def _fitz_x_overlap_ratio(a: Any, b: Any) -> float:
    overlap = max(0.0, min(float(a.x1), float(b.x1)) - max(float(a.x0), float(b.x0)))
    return overlap / max(1.0, min(float(a.width), float(b.width)))


def _fitz_rects_intersect(a: Any, b: Any) -> bool:
    return min(float(a.x1), float(b.x1)) > max(float(a.x0), float(b.x0)) and min(float(a.y1), float(b.y1)) > max(float(a.y0), float(b.y0))


def _fitz_union_rect(rects: list[Any]) -> Any:
    if not rects:
        raise ValueError("Cannot union empty rect list")
    rect = rects[0]
    for other in rects[1:]:
        rect = rect | other
    return rect


def _p62_expand_rect(rect: Any, page_rect: Any, *, margin: float) -> Any:
    try:
        import fitz  # type: ignore[import-not-found]

        return fitz.Rect(
            max(float(page_rect.x0), float(rect.x0) - margin),
            max(float(page_rect.y0), float(rect.y0) - margin),
            min(float(page_rect.x1), float(rect.x1) + margin),
            min(float(page_rect.y1), float(rect.y1) + margin),
        )
    except Exception:
        return rect


def _fitz_rect_tuple(rect: Any) -> tuple[float, float, float, float]:
    return (
        round(float(rect.x0), 2),
        round(float(rect.y0), 2),
        round(float(rect.x1), 2),
        round(float(rect.y1), 2),
    )


def _p62_patch_targets_for_record(
    run_dir: Path,
    record: dict[str, Any],
    manifest_article: dict[str, Any],
    *,
    allow_external_paths: bool,
) -> list[Path]:
    article_id = str(record.get("article") or manifest_article.get("article_id") or "")
    values: list[Any] = [
        record.get("polish_stage_path"),
        manifest_article.get("polish_path"),
        manifest_article.get("polish_stage_path"),
        manifest_article.get("source_polish_path"),
    ]
    if article_id:
        values.extend(
            [
                run_dir / "polish" / f"{article_id}.{POLISH_STAGE}",
                run_dir / "audit_tree" / article_id / POLISH_STAGE,
            ]
        )

    candidates: list[Path] = []
    for value in values:
        for candidate in _existing_path_candidates(value):
            if not candidate.is_file():
                continue
            if not allow_external_paths and not _path_is_inside(candidate, run_dir):
                continue
            candidates.append(candidate)

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _profile_for_assessment(manifest_article: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    for candidate in _existing_path_candidates(manifest_article.get("profile_path")):
        if candidate.is_file():
            try:
                return _load_json(candidate)
            except Exception:
                break
    return {
        "status": existing.get("profile_status") or manifest_article.get("profile_status") or "unknown",
        "style": existing.get("profile_style") or manifest_article.get("citation_style") or "unknown",
        "confidence": existing.get("profile_confidence")
        or manifest_article.get("citation_confidence")
        or "low",
    }


def _refresh_assessment_for_articles(run_dir: Path, article_ids: Iterable[str]) -> dict[str, Any]:
    requested = {str(article_id) for article_id in article_ids if article_id}
    if not requested:
        return _load_json(run_dir / "assessment.json", default={})

    assessment = _load_json(run_dir / "assessment.json", default={"articles": []})
    manifest = _load_json(run_dir / "manifest.json", default={})
    manifest_by_article = _manifest_article_by_id(manifest)
    existing_articles = [
        article for article in assessment.get("articles") or [] if isinstance(article, dict)
    ]

    updated_articles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for existing in existing_articles:
        article_id = str(existing.get("article") or "")
        if article_id not in requested:
            updated_articles.append(existing)
            seen.add(article_id)
            continue
        manifest_article = manifest_by_article.get(article_id, {})
        targets = _p62_patch_targets_for_record(
            run_dir,
            {"article": article_id, "polish_stage_path": existing.get("polish_stage_path")},
            manifest_article,
            allow_external_paths=False,
        )
        html_path = targets[0] if targets else None
        if html_path is None:
            updated_articles.append(existing)
            seen.add(article_id)
            continue
        html = html_path.read_text(encoding="utf-8", errors="replace")
        refreshed = assess_polish_html(
            article_id,
            html,
            _profile_for_assessment(manifest_article, existing),
        )
        for key in (
            "source_article",
            "raw_stage_path",
            "polish_stage_path",
            "artifact_hint",
            "language_detection",
            "polish_language",
            "target_language",
            "skip_non_target_language",
            "skip_unknown_language",
        ):
            if existing.get(key) is not None:
                refreshed[key] = existing.get(key)
            elif manifest_article.get(key) is not None:
                refreshed[key] = manifest_article.get(key)
        updated_articles.append(refreshed)
        seen.add(article_id)

    for article_id in sorted(requested - seen):
        manifest_article = manifest_by_article.get(article_id, {})
        targets = _p62_patch_targets_for_record(
            run_dir,
            {"article": article_id, "polish_stage_path": ""},
            manifest_article,
            allow_external_paths=False,
        )
        if not targets:
            continue
        html = targets[0].read_text(encoding="utf-8", errors="replace")
        refreshed = assess_polish_html(article_id, html, _profile_for_assessment(manifest_article, {}))
        for key in ("source_article", "raw_stage_path", "polish_stage_path", "artifact_hint"):
            if manifest_article.get(key) is not None:
                refreshed[key] = manifest_article.get(key)
        updated_articles.append(refreshed)

    totals, problematic = _assessment_totals(updated_articles)
    refreshed_assessment = {
        **assessment,
        "generated_at": _now(),
        "article_count": len(updated_articles),
        "totals": totals,
        "problematic_articles": problematic,
        "articles": updated_articles,
    }
    _write_json(run_dir / "assessment.json", refreshed_assessment)
    return refreshed_assessment


def _audit_defect_ids(article: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("defects_found", "defects"):
        for defect in article.get(key) or []:
            if isinstance(defect, dict) and defect.get("id"):
                ids.add(str(defect.get("id")))
    return ids


def _audit_articles_by_auto_repair_need(audit_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    articles: dict[str, dict[str, Any]] = {}
    for article in audit_report.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        defect_ids = _audit_defect_ids(article)
        selected = defect_ids & {"P55", "P96", "P97", "P98"}
        if not selected:
            continue
        articles[article_id] = {"article": article, "defect_ids": sorted(selected)}
    return articles


def _visible_ref_prefix_number(text: str) -> int | None:
    match = VISIBLE_REF_PREFIX_RE.match(text)
    if match is None:
        return None
    value = match.group("bracket") or match.group("plain")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _repair_visible_reference_numbers(html: str) -> tuple[str, int]:
    repairs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal repairs
        try:
            number = int(match.group("num"))
        except ValueError:
            return match.group(0)
        body = match.group("body")
        visible_number = _visible_ref_prefix_number(_visible_html_text(body))
        if visible_number == number:
            return match.group(0)
        if visible_number is not None:
            return match.group(0)
        repairs += 1
        prefix = f'<span class="z2m-ref-num">{number}.</span> '
        return f"<{match.group('tag')}{match.group('attrs')}>{prefix}{body}</{match.group('tag')}>"

    repaired = REF_TARGET_BLOCK_RE.sub(replace, html)
    return repaired, repairs


def _split_before_references_for_repair(html: str) -> tuple[str, str]:
    positions: list[int] = []
    heading = REFERENCES_HEADING_RE.search(html)
    if heading is not None:
        positions.append(heading.start())
    first_ref = REF_TARGET_BLOCK_RE.search(html)
    if first_ref is not None:
        positions.append(first_ref.start())
    if not positions:
        return html, ""
    split_at = min(positions)
    return html[:split_at], html[split_at:]


def _numeric_ref_anchor_label_numbers(label: str) -> list[int]:
    if re.fullmatch(r"[\s\(\)\[\],.;:\-\u2010-\u2014\d]+", label) is None:
        return []
    values = re.findall(r"\d{1,4}", label)
    if any(value.startswith("0") for value in re.findall(r"\d{2,4}", label)):
        return []
    numbers = [int(value) for value in values]
    return [number for number in numbers if not (1800 <= number <= 2099)]


def _unwrap_author_year_numeric_ref_links(html: str) -> tuple[str, int]:
    before_references, references_and_after = _split_before_references_for_repair(html)
    repairs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal repairs
        label = _visible_html_text(match.group("body"))
        if not _numeric_ref_anchor_label_numbers(label):
            return match.group(0)
        repairs += 1
        return match.group("body")

    repaired_before = AUTHOR_YEAR_NUMERIC_REF_ANCHOR_RE.sub(replace, before_references)
    return repaired_before + references_and_after, repairs


def _looks_like_author_year_ref_anchor(label: str, right_text: str) -> bool:
    if AUTHOR_YEAR_TEXT_RE.search(label) is not None:
        return True
    cleaned = re.sub(r"\s+", " ", label).strip(" ([{,;")
    if AUTHOR_YEAR_SURNAME_FRAGMENT_RE.fullmatch(cleaned) is None:
        return False
    return AUTHOR_YEAR_RIGHT_CONTEXT_RE.match(right_text) is not None


def _unwrap_author_year_ref_anchors(html: str) -> tuple[str, int]:
    before_references, references_and_after = _split_before_references_for_repair(html)
    repairs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal repairs
        label = _visible_html_text(match.group("body"))
        right_text = _visible_html_text(before_references[match.end() : match.end() + 140])
        if not _looks_like_author_year_ref_anchor(label, right_text):
            return match.group(0)
        repairs += 1
        return match.group("body")

    repaired_before = AUTHOR_YEAR_REF_ANCHOR_RE.sub(replace, before_references)
    return repaired_before + references_and_after, repairs


def write_polish_auto_repair_stage(
    run_dir: Path,
    *,
    gate_config: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Apply source-backed local repairs promoted from post-audit defect checks."""

    gate_config = gate_config or load_gate_config()
    run_dir = run_dir.resolve(strict=False)
    out_path = out_path or (run_dir / DEFAULT_POLISH_AUTO_REPAIR_REPORT_NAME)
    repair_root = run_dir / "polish_auto_repair"
    audit_report = _load_json(run_dir / "audit_full_checks.json", default={})
    manifest = _load_json(run_dir / "manifest.json", default={})
    manifest_by_article = _manifest_article_by_id(manifest)
    repair_articles = _audit_articles_by_auto_repair_need(audit_report)
    zoom = float(gate_config.get("polish_auto_repair_render_zoom") or gate_config.get("p62_image_recovery_render_zoom") or 1.5)
    apply_patches = bool(gate_config.get("polish_auto_repair_apply_patches", True))

    report_articles: list[dict[str, Any]] = []
    patched_article_ids: set[str] = set()
    repair_counts: Counter[str] = Counter()
    target_patch_counts: Counter[str] = Counter()

    print(
        "Polish auto repair started: "
        f"articles={len(repair_articles)} apply_patches={apply_patches}",
        flush=True,
    )
    for index, (article_id, item) in enumerate(sorted(repair_articles.items()), start=1):
        audit_article = item["article"]
        defect_ids = set(item["defect_ids"])
        manifest_article = manifest_by_article.get(article_id, {})
        targets = _p62_patch_targets_for_record(
            run_dir,
            {"article": article_id, "polish_stage_path": ""},
            manifest_article,
            allow_external_paths=False,
        )
        article_report: dict[str, Any] = {
            "index": index,
            "article": article_id,
            "defect_ids": sorted(defect_ids),
            "targets": [str(path) for path in targets],
            "repairs": [],
            "patched": False,
            "errors": [],
        }

        if "P96" in defect_ids:
            pdf_path = Path(str((audit_article.get("summary") or {}).get("source_pdf_path") or ""))
            if pdf_path.is_file() and apply_patches:
                duplicate_report = _apply_p62_duplicate_figure_image_repairs(
                    targets,
                    pdf_path=pdf_path,
                    artifact_dir=repair_root / _slug(article_id, max_len=72) / "p96_duplicate_visual",
                    zoom=zoom,
                    repair_plain_duplicates=True,
                )
                patched_count = int(duplicate_report.get("repair_count") or 0)
                repair_counts["P96"] += patched_count
                article_report["repairs"].append({"id": "P96", **duplicate_report})
                if patched_count:
                    patched_article_ids.add(article_id)
                    article_report["patched"] = True
                    for path in duplicate_report.get("patched_paths") or []:
                        target_patch_counts[str(path)] += 1
            else:
                article_report["repairs"].append(
                    {
                        "id": "P96",
                        "repair_count": 0,
                        "status": "skipped_missing_pdf" if not pdf_path.is_file() else "dry_run",
                        "source_pdf_path": str(pdf_path),
                    }
                )

        if {"P55", "P97", "P98"} & defect_ids and apply_patches:
            for target_path in targets:
                try:
                    html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                patched = html
                p55_repairs = 0
                p97_repairs = 0
                p98_repairs = 0
                if "P55" in defect_ids:
                    patched, p55_repairs = _unwrap_author_year_ref_anchors(patched)
                if "P97" in defect_ids:
                    patched, p97_repairs = _repair_visible_reference_numbers(patched)
                if "P98" in defect_ids:
                    patched, p98_repairs = _unwrap_author_year_numeric_ref_links(patched)
                if patched != html:
                    try:
                        target_path.write_text(patched, encoding="utf-8")
                    except OSError as exc:
                        article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                        continue
                    patched_article_ids.add(article_id)
                    article_report["patched"] = True
                    target_patch_counts[str(target_path)] += 1
                if p55_repairs:
                    repair_counts["P55"] += p55_repairs
                if p97_repairs:
                    repair_counts["P97"] += p97_repairs
                if p98_repairs:
                    repair_counts["P98"] += p98_repairs
                if p55_repairs or p97_repairs or p98_repairs:
                    article_report["repairs"].append(
                        {
                            "id": "P55/P97/P98",
                            "path": str(target_path),
                            "p55_author_year_link_unwraps": p55_repairs,
                            "p97_visible_number_repairs": p97_repairs,
                            "p98_numeric_link_unwraps": p98_repairs,
                        }
                    )

        report_articles.append(article_report)

    if patched_article_ids:
        _refresh_assessment_for_articles(run_dir, patched_article_ids)

    report = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "path": str(out_path),
        "status": "patched" if patched_article_ids else "no_changes",
        "candidate_count": len(repair_articles),
        "patched_article_count": len(patched_article_ids),
        "repair_counts": dict(sorted(repair_counts.items())),
        "patched_targets": dict(sorted(target_patch_counts.items())),
        "apply_patches": apply_patches,
        "render_zoom": zoom,
        "articles": report_articles,
    }
    _write_json(out_path, report)
    print(
        "Polish auto repair complete: "
        f"status={report['status']} patched_articles={len(patched_article_ids)} "
        f"repairs={dict(sorted(repair_counts.items()))}",
        flush=True,
    )
    return report


def write_p62_image_recovery_stage(
    run_dir: Path,
    *,
    gate_config: dict[str, Any] | None = None,
    plan_path: Path | None = None,
    out_path: Path | None = None,
    execute_marker: bool | None = None,
    apply_patches: bool | None = None,
    allow_external_paths: bool = False,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Recover P62 missing-figure visuals through marker, then PDF page render fallback."""

    gate_config = gate_config or load_gate_config()
    run_dir = run_dir.resolve(strict=False)
    plan_path = plan_path or (run_dir / DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME)
    out_path = out_path or (run_dir / DEFAULT_P62_IMAGE_RECOVERY_REPORT_NAME)
    if not plan_path.is_file():
        write_p62_marker_recovery_plan(run_dir, gate_config=gate_config, out_path=plan_path)
    plan = _load_json(plan_path, default={"articles": []})
    records = [item for item in plan.get("articles") or [] if isinstance(item, dict)]
    if max_items is None:
        max_items = int(gate_config.get("p62_image_recovery_max_articles") or 0)
    if max_items and max_items > 0:
        records = records[:max_items]

    if execute_marker is None:
        execute_marker = bool(gate_config.get("p62_image_recovery_execute_marker", True))
    if apply_patches is None:
        apply_patches = bool(gate_config.get("p62_image_recovery_apply_patches", True))
    render_zoom = float(
        gate_config.get("p62_image_recovery_render_zoom")
        or gate_config.get("pdf_problem_evidence_render_zoom")
        or 1.5
    )
    marker_timeout = int(gate_config.get("p62_image_recovery_marker_timeout_seconds") or 300)
    probe_source_visual_unavailable = bool(
        gate_config.get("p62_image_recovery_probe_source_visual_unavailable", True)
    )
    probe_marker_for_unavailable = bool(
        gate_config.get("p62_image_recovery_probe_marker_for_unavailable", execute_marker)
    )
    probe_marker_timeout = int(
        gate_config.get("p62_image_recovery_source_visual_probe_marker_timeout_seconds")
        or marker_timeout
    )
    replace_page_render = bool(gate_config.get("p62_image_recovery_replace_page_render", True))
    remove_false_match_recovery = bool(
        gate_config.get("p62_image_recovery_remove_false_match_recovery", True)
    )
    repair_duplicate_figure_images = bool(
        gate_config.get("p62_image_recovery_repair_duplicate_figure_images", True)
    )

    manifest = _load_json(run_dir / "manifest.json", default={})
    manifest_by_article = _manifest_article_by_id(manifest)
    recovery_root = run_dir / "p62_image_recovery"
    recovered_records: list[dict[str, Any]] = []
    patched_article_ids: set[str] = set()
    print(
        "P62 image recovery started: "
        f"records={len(records)} execute_marker={execute_marker} apply_patches={apply_patches}",
        flush=True,
    )

    for index, record in enumerate(records, start=1):
        article_id = str(record.get("article") or f"article_{index}")
        figure_label = str(record.get("figure_label") or "").strip()
        resolved_figure_label = str(record.get("resolved_figure_label") or figure_label).strip()
        artifact_dir = recovery_root / f"{index:03d}_{_slug(article_id, max_len=72)}"
        if figure_label:
            artifact_dir = artifact_dir / f"fig_{_slug(figure_label, max_len=20)}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = Path(str(record.get("source_pdf_path") or "")).expanduser()
        source_page_number = int(record.get("source_pdf_page_number") or 0)
        manifest_article = manifest_by_article.get(article_id, {})
        targets = _p62_patch_targets_for_record(
            run_dir,
            record,
            manifest_article,
            allow_external_paths=allow_external_paths,
        )
        item: dict[str, Any] = {
            "article": article_id,
            "source_article": record.get("source_article") or article_id,
            "figure_label": figure_label,
            "resolved_figure_label": resolved_figure_label,
            "warning_index": record.get("warning_index"),
            "plan_status": record.get("status"),
            "selected_false_match_hint": record.get("selected_false_match_hint") or "",
            "source_visual_unavailable_reason": record.get("source_visual_unavailable_reason") or "",
            "source_pdf_path": str(pdf_path) if record.get("source_pdf_path") else "",
            "source_pdf_page_number": source_page_number,
            "patch_target_paths": [str(path) for path in targets],
            "execute_marker": execute_marker,
            "apply_patches": apply_patches,
            "asset_status": "not_ready",
            "recovery_source": "",
            "recovery_detail": "",
            "marker_execution": {"status": "not_run"},
            "marker_output_validation": record.get("existing_marker_output_validation") or {"status": "not_run"},
            "source_visual_probe_status": "not_run",
            "source_visual_probe": {"status": "not_run"},
            "figure_asset_status": "not_run",
            "figure_asset_path": "",
            "figure_asset_source": "",
            "figure_asset_error": "",
            "page_render_status": "not_run",
            "page_render_path": "",
            "page_render_page_number": 0,
            "page_render_selection_reason": "",
            "existing_page_render_recovery": False,
            "existing_page_render_upgrade": False,
            "page_render_recovery_removed": False,
            "existing_false_match_recovery": False,
            "false_match_recovery_removed": False,
            "source_page_false_match_hint": "",
            "source_page_caption_found": False,
            "duplicate_visual_repair_count": 0,
            "duplicate_visual_repairs": [],
            "patch_replacement_count": 0,
            "patched_paths": [],
            "status": "unresolved",
            "unresolved_reason": "",
        }
        source_page_false_match_hint = _p62_pdf_page_false_match_hint(
            pdf_path,
            source_page_number,
            resolved_figure_label or figure_label,
        )
        item["source_page_false_match_hint"] = source_page_false_match_hint
        source_page_caption_found = _p62_pdf_page_caption_label_found(
            pdf_path,
            source_page_number,
            resolved_figure_label or figure_label,
        )
        item["source_page_caption_found"] = source_page_caption_found

        if apply_patches and targets:
            warning_still_present = False
            stale_page_render_present = False
            false_match_recovery_present = False
            for target_path in targets:
                try:
                    target_html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    item.setdefault("patch_errors", []).append({"path": str(target_path), "error": str(exc)})
                    continue
                if _html_has_p62_missing_warning_for_label(
                    target_html,
                    figure_label,
                ) or _html_has_p62_missing_warning_for_figure_unit(
                    target_html,
                    figure_label or resolved_figure_label,
                ):
                    warning_still_present = True
                    break
                if replace_page_render and _html_has_p62_stale_page_render_for_label(
                    target_html,
                    figure_label or resolved_figure_label,
                ):
                    stale_page_render_present = True
                if (
                    remove_false_match_recovery
                    and _p62_false_match_hint_blocks_asset_recovery(
                        source_page_false_match_hint,
                        caption_found=source_page_caption_found,
                    )
                    and _html_has_p62_recovery_for_label(
                        target_html,
                        figure_label or resolved_figure_label,
                        sources=P62_PDF_DERIVED_RECOVERY_SOURCES,
                    )
                ):
                    false_match_recovery_present = True
            item["existing_page_render_recovery"] = stale_page_render_present
            item["existing_false_match_recovery"] = false_match_recovery_present
            if not warning_still_present:
                if false_match_recovery_present:
                    print(
                        "P62 false-match recovery probe: "
                        f"{index}/{len(records)} article={_console_text(article_id)} "
                        f"fig={figure_label or '?'} hint={source_page_false_match_hint or '?'}",
                        flush=True,
                    )
                elif stale_page_render_present:
                    print(
                        "P62 page-render upgrade attempt: "
                        f"{index}/{len(records)} article={_console_text(article_id)} fig={figure_label or '?'}",
                        flush=True,
                    )
                else:
                    duplicate_repair = (
                        _apply_p62_duplicate_figure_image_repairs(
                            targets,
                            pdf_path=pdf_path,
                            artifact_dir=artifact_dir,
                            zoom=render_zoom,
                        )
                        if repair_duplicate_figure_images
                        else {"repair_count": 0, "patched_paths": [], "repairs": [], "errors": []}
                    )
                    item["duplicate_visual_repair_count"] = int(duplicate_repair.get("repair_count") or 0)
                    item["duplicate_visual_repairs"] = duplicate_repair.get("repairs") or []
                    if duplicate_repair.get("errors"):
                        item.setdefault("patch_errors", []).extend(duplicate_repair.get("errors") or [])
                    item["asset_status"] = "ready"
                    item["recovery_source"] = "existing_patched_html"
                    item["recovery_detail"] = "; ".join(str(path) for path in targets)
                    if item["duplicate_visual_repair_count"]:
                        item["patch_replacement_count"] = item["duplicate_visual_repair_count"]
                        item["patched_paths"] = list(duplicate_repair.get("patched_paths") or [])
                        item["status"] = "patched_duplicate_visuals"
                        patched_article_ids.add(article_id)
                    else:
                        item["status"] = "already_patched"
                    recovered_records.append(item)
                    if index % 10 == 0 or index == len(records):
                        ready_so_far = sum(1 for current in recovered_records if current.get("asset_status") == "ready")
                        patched_so_far = sum(int(current.get("patch_replacement_count") or 0) for current in recovered_records)
                        print(
                            "P62 image recovery progress: "
                            f"{index}/{len(records)} asset_ready={ready_so_far} patched={patched_so_far}",
                            flush=True,
                        )
                    continue

        if not pdf_path.is_file():
            item["unresolved_reason"] = "source_pdf_unavailable"
            recovered_records.append(item)
            continue
        if source_page_number <= 0:
            item["unresolved_reason"] = "source_pdf_page_unavailable"
            recovered_records.append(item)
            continue

        marker_validation = dict(record.get("existing_marker_output_validation") or {})
        marker_command_available = bool(record.get("marker_command"))
        marker_output_dir_raw = str(record.get("marker_output_dir") or "").strip()
        if (
            execute_marker
            and marker_validation.get("status") != "recovered_image"
            and marker_command_available
            and marker_output_dir_raw
        ):
            print(
                "P62 marker attempt: "
                f"{index}/{len(records)} article={_console_text(article_id)} fig={figure_label or '?'} "
                f"page_range={record.get('marker_page_range') or '?'} timeout={marker_timeout}s",
                flush=True,
            )
            item["marker_execution"] = _execute_p62_marker_command(record, timeout_seconds=marker_timeout)
            marker_output_dir = Path(marker_output_dir_raw)
            marker_validation = _validate_p62_marker_output(marker_output_dir, resolved_figure_label or figure_label)
            print(
                "P62 marker result: "
                f"{index}/{len(records)} status={item['marker_execution'].get('status')} "
                f"validation={marker_validation.get('status')} "
                f"elapsed={item['marker_execution'].get('elapsed_seconds')}s",
                flush=True,
            )
        elif execute_marker and marker_validation.get("status") != "recovered_image":
            item["marker_execution"] = {
                "status": "skipped",
                "reason": "marker_command_or_output_dir_unavailable",
                "returncode": None,
            }
        item["marker_output_validation"] = marker_validation

        data_url = ""
        recovery_source = ""
        recovery_detail = ""
        marker_image = (
            _first_valid_image_path(marker_validation)
            if marker_validation.get("status") == "recovered_image"
            else None
        )
        if marker_image is not None:
            data_url = _data_url_from_image_file(marker_image) or ""
            recovery_source = "marker_image"
            recovery_detail = str(marker_image)

        source_page_is_false_match = _p62_false_match_hint_blocks_asset_recovery(
            source_page_false_match_hint,
            caption_found=source_page_caption_found,
        )
        needs_source_visual_probe = (
            str(record.get("status") or "") == "source_visual_unavailable"
            or bool(item.get("existing_false_match_recovery"))
            or source_page_is_false_match
        )
        if not data_url and needs_source_visual_probe:
            if probe_source_visual_unavailable:
                print(
                    "P62 source-visual probe: "
                    f"{index}/{len(records)} article={_console_text(article_id)} fig={figure_label or '?'} "
                    f"marker={probe_marker_for_unavailable} timeout={probe_marker_timeout}s",
                    flush=True,
                )
                source_visual_probe = _probe_p62_source_visual_unavailable(
                    pdf_path,
                    resolved_figure_label or figure_label,
                    artifact_dir / "source_visual_probe",
                    snippets=[
                        str(snippet)
                        for snippet in (record.get("problem_snippets") or [])
                        if str(snippet).strip()
                    ],
                    zoom=render_zoom,
                    run_marker=probe_marker_for_unavailable,
                    marker_timeout_seconds=probe_marker_timeout,
                    marker_output_dir=(
                        recovery_root
                        / "_source_visual_probe_marker"
                        / (
                            hashlib.sha1(str(pdf_path.resolve(strict=False)).encode("utf-8")).hexdigest()[:12]
                            + "_"
                            + _slug(pdf_path.stem, max_len=48)
                        )
                    )
                    if probe_marker_for_unavailable
                    else None,
                )
                item["source_visual_probe"] = source_visual_probe
                item["source_visual_probe_status"] = source_visual_probe.get("status") or "unknown"
                probe_asset = source_visual_probe.get("asset") if isinstance(source_visual_probe.get("asset"), dict) else {}
                if probe_asset.get("path") and probe_asset.get("source"):
                    asset_path = Path(str(probe_asset.get("path")))
                    data_url = _data_url_from_image_file(asset_path) or ""
                    if data_url:
                        recovery_source = str(probe_asset.get("source") or "source_visual_probe")
                        recovery_detail = str(asset_path)
                        item.update(
                            {
                                "figure_asset_status": probe_asset.get("status") or "source_visual_probe_asset",
                                "figure_asset_path": str(asset_path),
                                "figure_asset_source": recovery_source,
                                "figure_asset_error": probe_asset.get("error") or "",
                                "figure_asset_page_number": probe_asset.get("page_number") or 0,
                                "figure_asset_selected_rect": probe_asset.get("selected_rect"),
                                "figure_asset_caption_found": probe_asset.get("caption_found"),
                                "figure_asset_plate_index": probe_asset.get("plate_index"),
                                "figure_asset_plate_count": probe_asset.get("plate_count"),
                            }
                        )
                print(
                    "P62 source-visual probe result: "
                    f"{index}/{len(records)} status={item['source_visual_probe_status']} "
                    f"source={recovery_source or 'unresolved'}",
                    flush=True,
                )
            if not data_url:
                if item.get("existing_false_match_recovery") and apply_patches:
                    patched_paths: list[str] = []
                    replacement_count = 0
                    for target_path in targets:
                        try:
                            html = target_path.read_text(encoding="utf-8", errors="replace")
                            patched, replacements = _replace_p62_recovery_with_missing_warning(
                                html,
                                figure_label=figure_label or resolved_figure_label,
                                reason="source_visual_unavailable",
                            )
                            if replacements:
                                target_path.write_text(patched, encoding="utf-8")
                                patched_paths.append(str(target_path))
                                replacement_count += replacements
                        except OSError as exc:
                            item.setdefault("patch_errors", []).append({"path": str(target_path), "error": str(exc)})
                    item["patch_replacement_count"] = replacement_count
                    item["patched_paths"] = patched_paths
                    item["false_match_recovery_removed"] = bool(replacement_count)
                    if replacement_count:
                        patched_article_ids.add(article_id)
                if item.get("existing_page_render_recovery") and apply_patches:
                    patched_paths = list(item.get("patched_paths") or [])
                    replacement_count = int(item.get("patch_replacement_count") or 0)
                    for target_path in targets:
                        try:
                            html = target_path.read_text(encoding="utf-8", errors="replace")
                            patched, replacements = _replace_p62_recovery_with_missing_warning(
                                html,
                                figure_label=figure_label or resolved_figure_label,
                                reason="source_visual_unavailable",
                                replace_sources=P62_LOW_FIDELITY_RECOVERY_SOURCES,
                            )
                            if replacements:
                                target_path.write_text(patched, encoding="utf-8")
                                patched_paths.append(str(target_path))
                                replacement_count += replacements
                        except OSError as exc:
                            item.setdefault("patch_errors", []).append({"path": str(target_path), "error": str(exc)})
                    item["patch_replacement_count"] = replacement_count
                    item["patched_paths"] = patched_paths
                    item["page_render_recovery_removed"] = bool(replacement_count)
                    if replacement_count:
                        patched_article_ids.add(article_id)
                if source_page_is_false_match and apply_patches:
                    patched_paths = list(item.get("patched_paths") or [])
                    replacement_count = int(item.get("patch_replacement_count") or 0)
                    for target_path in targets:
                        try:
                            html = target_path.read_text(encoding="utf-8", errors="replace")
                            patched, replacements = _replace_p62_figure_unit_target_with_missing_warning(
                                html,
                                figure_label=figure_label or resolved_figure_label,
                                reason="source_visual_unavailable",
                            )
                            if replacements:
                                target_path.write_text(patched, encoding="utf-8")
                                patched_paths.append(str(target_path))
                                replacement_count += replacements
                        except OSError as exc:
                            item.setdefault("patch_errors", []).append({"path": str(target_path), "error": str(exc)})
                    item["patch_replacement_count"] = replacement_count
                    item["patched_paths"] = patched_paths
                    if replacement_count:
                        patched_article_ids.add(article_id)
                if item.get("existing_false_match_recovery"):
                    item["unresolved_reason"] = (
                        "existing_recovery_matches_false_pdf_page:"
                        f"{source_page_false_match_hint or 'unknown'}"
                    )
                elif item.get("existing_page_render_recovery"):
                    item["unresolved_reason"] = "existing_pdf_page_render_no_higher_fidelity_asset"
                elif source_page_is_false_match:
                    item["unresolved_reason"] = (
                        "source_pdf_page_false_match:"
                        f"{source_page_false_match_hint or 'unknown'}"
                    )
                else:
                    item["unresolved_reason"] = "source_visual_unavailable"
                recovered_records.append(item)
                continue

        if not data_url:
            figure_asset = _recover_p62_detached_pdf_figure_plate_asset(
                pdf_path,
                source_page_number,
                resolved_figure_label or figure_label,
                artifact_dir,
                zoom=render_zoom,
            )
            if not (figure_asset.get("path") and figure_asset.get("source")):
                figure_asset = _recover_p62_pdf_figure_asset(
                    pdf_path,
                    source_page_number,
                    resolved_figure_label or figure_label,
                    artifact_dir,
                    zoom=render_zoom,
                )
            item.update(
                {
                    "figure_asset_status": figure_asset.get("status"),
                    "figure_asset_path": figure_asset.get("path") or "",
                    "figure_asset_source": figure_asset.get("source") or "",
                    "figure_asset_error": figure_asset.get("error") or "",
                    "figure_asset_page_number": figure_asset.get("page_number") or 0,
                    "figure_asset_selected_rect": figure_asset.get("selected_rect"),
                    "figure_asset_caption_found": figure_asset.get("caption_found"),
                    "figure_asset_plate_index": figure_asset.get("plate_index"),
                    "figure_asset_plate_count": figure_asset.get("plate_count"),
                }
            )
            if figure_asset.get("path") and figure_asset.get("source"):
                asset_path = Path(str(figure_asset.get("path")))
                data_url = _data_url_from_image_file(asset_path) or ""
                if data_url:
                    recovery_source = str(figure_asset.get("source") or "pdf_figure_region_render")
                    recovery_detail = str(asset_path)

        if not data_url:
            if item.get("existing_page_render_recovery") and probe_source_visual_unavailable:
                print(
                    "P62 page-render source-visual probe: "
                    f"{index}/{len(records)} article={_console_text(article_id)} fig={figure_label or '?'} "
                    f"marker={probe_marker_for_unavailable} timeout={probe_marker_timeout}s",
                    flush=True,
                )
                source_visual_probe = _probe_p62_source_visual_unavailable(
                    pdf_path,
                    resolved_figure_label or figure_label,
                    artifact_dir / "source_visual_probe",
                    snippets=[
                        str(snippet)
                        for snippet in (record.get("problem_snippets") or [])
                        if str(snippet).strip()
                    ],
                    zoom=render_zoom,
                    run_marker=probe_marker_for_unavailable,
                    marker_timeout_seconds=probe_marker_timeout,
                    marker_output_dir=(
                        recovery_root
                        / "_source_visual_probe_marker"
                        / (
                            hashlib.sha1(str(pdf_path.resolve(strict=False)).encode("utf-8")).hexdigest()[:12]
                            + "_"
                            + _slug(pdf_path.stem, max_len=48)
                        )
                    )
                    if probe_marker_for_unavailable
                    else None,
                )
                item["source_visual_probe"] = source_visual_probe
                item["source_visual_probe_status"] = source_visual_probe.get("status") or "unknown"
                probe_asset = source_visual_probe.get("asset") if isinstance(source_visual_probe.get("asset"), dict) else {}
                if probe_asset.get("path") and probe_asset.get("source"):
                    asset_path = Path(str(probe_asset.get("path")))
                    data_url = _data_url_from_image_file(asset_path) or ""
                    if data_url:
                        recovery_source = str(probe_asset.get("source") or "source_visual_probe")
                        recovery_detail = str(asset_path)
                        item.update(
                            {
                                "figure_asset_status": probe_asset.get("status") or "source_visual_probe_asset",
                                "figure_asset_path": str(asset_path),
                                "figure_asset_source": recovery_source,
                                "figure_asset_error": probe_asset.get("error") or "",
                                "figure_asset_page_number": probe_asset.get("page_number") or 0,
                                "figure_asset_selected_rect": probe_asset.get("selected_rect"),
                                "figure_asset_caption_found": probe_asset.get("caption_found"),
                                "figure_asset_plate_index": probe_asset.get("plate_index"),
                                "figure_asset_plate_count": probe_asset.get("plate_count"),
                            }
                        )
                print(
                    "P62 page-render source-visual probe result: "
                    f"{index}/{len(records)} status={item['source_visual_probe_status']} "
                    f"source={recovery_source or 'unresolved'}",
                    flush=True,
                )

        if not data_url:
            figure_asset_status = str(item.get("figure_asset_status") or "")
            if source_page_is_false_match or figure_asset_status.startswith("false_label_match_"):
                item["unresolved_reason"] = (
                    "source_pdf_page_false_match:"
                    f"{source_page_false_match_hint or figure_asset_status.removeprefix('false_label_match_') or 'unknown'}"
                )
                recovered_records.append(item)
                if index % 10 == 0 or index == len(records):
                    ready_so_far = sum(1 for current in recovered_records if current.get("asset_status") == "ready")
                    patched_so_far = sum(int(current.get("patch_replacement_count") or 0) for current in recovered_records)
                    print(
                        "P62 image recovery progress: "
                        f"{index}/{len(records)} asset_ready={ready_so_far} patched={patched_so_far}",
                        flush=True,
                    )
                continue
            if item.get("existing_page_render_recovery"):
                if apply_patches:
                    patched_paths = list(item.get("patched_paths") or [])
                    replacement_count = int(item.get("patch_replacement_count") or 0)
                    for target_path in targets:
                        try:
                            html = target_path.read_text(encoding="utf-8", errors="replace")
                            patched, replacements = _replace_p62_recovery_with_missing_warning(
                                html,
                                figure_label=figure_label or resolved_figure_label,
                                reason="source_visual_unavailable",
                                replace_sources=P62_LOW_FIDELITY_RECOVERY_SOURCES,
                            )
                            if replacements:
                                target_path.write_text(patched, encoding="utf-8")
                                patched_paths.append(str(target_path))
                                replacement_count += replacements
                        except OSError as exc:
                            item.setdefault("patch_errors", []).append({"path": str(target_path), "error": str(exc)})
                    item["patch_replacement_count"] = replacement_count
                    item["patched_paths"] = patched_paths
                    item["page_render_recovery_removed"] = bool(replacement_count)
                    if replacement_count:
                        patched_article_ids.add(article_id)
                item["unresolved_reason"] = "existing_pdf_page_render_no_higher_fidelity_asset"
                recovered_records.append(item)
                if index % 10 == 0 or index == len(records):
                    ready_so_far = sum(1 for current in recovered_records if current.get("asset_status") == "ready")
                    patched_so_far = sum(int(current.get("patch_replacement_count") or 0) for current in recovered_records)
                    print(
                        "P62 image recovery progress: "
                        f"{index}/{len(records)} asset_ready={ready_so_far} patched={patched_so_far}",
                        flush=True,
                    )
                continue
            if not _p62_record_allows_page_render_fallback(record):
                item["unresolved_reason"] = "page_render_fallback_requires_figure_label_page"
                recovered_records.append(item)
                if index % 10 == 0 or index == len(records):
                    ready_so_far = sum(1 for current in recovered_records if current.get("asset_status") == "ready")
                    patched_so_far = sum(int(current.get("patch_replacement_count") or 0) for current in recovered_records)
                    print(
                        "P62 image recovery progress: "
                        f"{index}/{len(records)} asset_ready={ready_so_far} patched={patched_so_far}",
                        flush=True,
                    )
                continue
            render_page, selection_reason = _p62_render_fallback_page_number(
                pdf_path,
                source_page_number,
                resolved_figure_label or figure_label,
            )
            render_path = artifact_dir / f"fig_{_slug(figure_label or 'unknown', max_len=20)}_pdf_page_{render_page:04d}.png"
            render = _render_pdf_evidence_page(pdf_path, render_page, render_path, zoom=render_zoom)
            item.update(
                {
                    "page_render_status": render.get("status"),
                    "page_render_path": render.get("path") or "",
                    "page_render_page_number": render_page,
                    "page_render_selection_reason": selection_reason,
                    "page_render_error": render.get("error") or "",
                }
            )
            if render.get("status") == "rendered" and render.get("path"):
                rendered_path = Path(str(render.get("path")))
                data_url = _data_url_from_image_file(rendered_path) or ""
                recovery_source = "pdf_page_render"
                recovery_detail = str(rendered_path)

        if not data_url:
            item["unresolved_reason"] = item.get("page_render_error") or "no_recoverable_image_asset"
            recovered_records.append(item)
            continue

        item["asset_status"] = "ready"
        item["recovery_source"] = recovery_source
        item["recovery_detail"] = recovery_detail
        if apply_patches:
            warning_index = int(record.get("warning_index") or 0) or None
            patched_paths: list[str] = []
            replacement_count = 0
            for target_path in targets:
                try:
                    html = target_path.read_text(encoding="utf-8", errors="replace")
                    patched, replacements = _replace_p62_missing_warning_with_image(
                        html,
                        figure_label=figure_label or resolved_figure_label,
                        warning_index=warning_index,
                        data_url=data_url,
                        source=recovery_source,
                        source_detail=recovery_detail,
                    )
                    if not replacements and replace_page_render:
                        patched, replacements = _replace_p62_stale_recovery_with_image(
                            html,
                            figure_label=figure_label or resolved_figure_label,
                            data_url=data_url,
                            source=recovery_source,
                            source_detail=recovery_detail,
                        )
                        if replacements:
                            item["existing_page_render_upgrade"] = True
                    if not replacements and item.get("existing_false_match_recovery"):
                        patched, replacements = _replace_p62_stale_recovery_with_image(
                            html,
                            figure_label=figure_label or resolved_figure_label,
                            data_url=data_url,
                            source=recovery_source,
                            source_detail=recovery_detail,
                            replace_sources=P62_PDF_DERIVED_RECOVERY_SOURCES,
                        )
                        if replacements:
                            item["existing_page_render_upgrade"] = recovery_source not in P62_LOW_FIDELITY_RECOVERY_SOURCES
                    if replacements:
                        target_path.write_text(patched, encoding="utf-8")
                        patched_paths.append(str(target_path))
                        replacement_count += replacements
                except OSError as exc:
                    item.setdefault("patch_errors", []).append({"path": str(target_path), "error": str(exc)})
            item["patch_replacement_count"] = replacement_count
            item["patched_paths"] = patched_paths
            if repair_duplicate_figure_images:
                duplicate_repair = _apply_p62_duplicate_figure_image_repairs(
                    targets,
                    pdf_path=pdf_path,
                    artifact_dir=artifact_dir,
                    zoom=render_zoom,
                )
                item["duplicate_visual_repair_count"] = int(duplicate_repair.get("repair_count") or 0)
                item["duplicate_visual_repairs"] = duplicate_repair.get("repairs") or []
                if duplicate_repair.get("errors"):
                    item.setdefault("patch_errors", []).extend(duplicate_repair.get("errors") or [])
                if item["duplicate_visual_repair_count"]:
                    item["patch_replacement_count"] += item["duplicate_visual_repair_count"]
                    patched_paths.extend(
                        path
                        for path in (duplicate_repair.get("patched_paths") or [])
                        if path not in patched_paths
                    )
                    item["patched_paths"] = patched_paths
                    patched_article_ids.add(article_id)
            if replacement_count:
                item["status"] = "patched"
                patched_article_ids.add(article_id)
            else:
                item["status"] = "asset_ready_patch_missed"
                item["unresolved_reason"] = "missing_warning_element_not_found_in_patch_targets"
        else:
            item["status"] = "asset_ready"
        recovered_records.append(item)
        if index % 10 == 0 or index == len(records):
            ready_so_far = sum(1 for current in recovered_records if current.get("asset_status") == "ready")
            patched_so_far = sum(int(current.get("patch_replacement_count") or 0) for current in recovered_records)
            print(
                "P62 image recovery progress: "
                f"{index}/{len(records)} asset_ready={ready_so_far} patched={patched_so_far}",
                flush=True,
            )

    if patched_article_ids:
        _refresh_assessment_for_articles(run_dir, patched_article_ids)

    status_counts = Counter(str(item.get("status") or "unknown") for item in recovered_records)
    source_counts = Counter(str(item.get("recovery_source") or "unresolved") for item in recovered_records)
    asset_ready_count = sum(1 for item in recovered_records if item.get("asset_status") == "ready")
    patched_warning_count = sum(int(item.get("patch_replacement_count") or 0) for item in recovered_records)
    page_render_upgrade_count = sum(1 for item in recovered_records if item.get("existing_page_render_upgrade"))
    page_render_recovery_removed_count = sum(
        1 for item in recovered_records if item.get("page_render_recovery_removed")
    )
    false_match_recovery_removed_count = sum(
        1 for item in recovered_records if item.get("false_match_recovery_removed")
    )
    duplicate_visual_repair_count = sum(
        int(item.get("duplicate_visual_repair_count") or 0) for item in recovered_records
    )
    patch_missed_count = int(status_counts.get("asset_ready_patch_missed", 0))
    unresolved_count = len(recovered_records) - asset_ready_count
    if not records and int(plan.get("candidate_count") or 0) == 0:
        status = "not_required"
    elif unresolved_count == 0 and patch_missed_count == 0:
        status = "ready"
    elif asset_ready_count:
        status = "partial"
    else:
        status = "unresolved"
    report = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "path": str(out_path),
        "plan_path": str(plan_path),
        "output_root": str(recovery_root),
        "status": status,
        "required_checks": [
            "marker_single_page_image",
            "source_visual_unavailable_probe",
            "pdf_detached_plate_region_render",
            "pdf_native_or_region_figure_asset",
            "false_match_recovery_cleanup",
            "pdf_page_render_upgrade",
            "pdf_page_render_fallback",
            "duplicate_figure_visual_repair",
            "html_missing_warning_patch",
        ],
        "candidate_count": int(plan.get("candidate_count") or len(records)),
        "selected_count": len(records),
        "asset_ready_count": asset_ready_count,
        "patched_warning_count": patched_warning_count,
        "page_render_upgrade_count": page_render_upgrade_count,
        "page_render_recovery_removed_count": page_render_recovery_removed_count,
        "false_match_recovery_removed_count": false_match_recovery_removed_count,
        "duplicate_visual_repair_count": duplicate_visual_repair_count,
        "patch_missed_count": patch_missed_count,
        "unresolved_count": unresolved_count,
        "execute_marker": execute_marker,
        "apply_patches": apply_patches,
        "allow_external_paths": allow_external_paths,
        "replace_page_render": replace_page_render,
        "remove_false_match_recovery": remove_false_match_recovery,
        "repair_duplicate_figure_images": repair_duplicate_figure_images,
        "render_zoom": render_zoom,
        "marker_timeout_seconds": marker_timeout,
        "probe_source_visual_unavailable": probe_source_visual_unavailable,
        "probe_marker_for_unavailable": probe_marker_for_unavailable,
        "source_visual_probe_marker_timeout_seconds": probe_marker_timeout,
        "status_counts": dict(sorted(status_counts.items())),
        "recovery_source_counts": dict(sorted(source_counts.items())),
        "source_visual_probe_status_counts": dict(
            sorted(Counter(str(item.get("source_visual_probe_status") or "not_run") for item in recovered_records).items())
        ),
        "articles": recovered_records,
    }
    _write_json(out_path, report)
    return report


def _converted_manifest_by_pair(manifest: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    articles: dict[tuple[str, str], dict[str, Any]] = {}
    for article in manifest.get("articles") or []:
        if not isinstance(article, dict):
            continue
        raw_path = _norm_path(article.get("raw_stage_path"))
        polish_path = _norm_path(article.get("polish_stage_path"))
        if raw_path and polish_path:
            articles[(raw_path, polish_path)] = article
    return articles


def _reference_id_numbers(html: str) -> list[int]:
    return sorted(
        {
            int(match.group(1))
            for match in re.finditer(r"\bid\s*=\s*['\"]ref-(\d+)['\"]", html, re.IGNORECASE)
        }
    )


def _reference_id_gap_numbers(html: str) -> list[int]:
    ids = _reference_id_numbers(html)
    if len(ids) < 2:
        return []
    gaps: list[int] = []
    for left, right in zip(ids, ids[1:]):
        if 0 < right - left <= 25:
            gaps.extend(range(left + 1, right))
    return gaps


def _expand_reference_candidate_numbers(value: str) -> list[int]:
    tokens = re.findall(r"\d{1,3}|[,;]|\u2013|\u2014|-", value)
    numbers: list[int] = []
    pending_range_from: int | None = None
    previous_number: int | None = None
    for token in tokens:
        if token.isdigit():
            number = int(token)
            if not 1 <= number <= 250:
                pending_range_from = None
                previous_number = None
                continue
            if pending_range_from is not None:
                if pending_range_from < number and number - pending_range_from <= 25:
                    numbers.extend(range(pending_range_from + 1, number + 1))
                else:
                    numbers.append(number)
                pending_range_from = None
            else:
                numbers.append(number)
            previous_number = number
        elif token in {"-", "\u2013", "\u2014"} and previous_number is not None:
            pending_range_from = previous_number
        else:
            pending_range_from = None
    deduped: list[int] = []
    seen: set[int] = set()
    for number in numbers:
        if number not in seen:
            seen.add(number)
            deduped.append(number)
    return deduped


def _plain_reference_candidate_is_safe(text: str, match: re.Match[str]) -> bool:
    start, end = match.span("body")
    prefix = text[max(0, start - 80) : start].lower()
    suffix = text[end : min(len(text), end + 18)].lower()
    if re.match(r"\s*(?:%|\u2030|percent|cm|mm|m\b|kg|g\b|mg|hz|khz|mhz|ghz|s\b|min\b|h\b)", suffix):
        return False
    if re.search(
        r"(?:fig(?:ure)?|table|section|sec|eq(?:uation)?|page|pages|pp|volume|vol|issue|"
        r"range|distance|frequency|values?|sample|n\s*=|aged?|years?|months?|days?|"
        r"cm|mm|kg|mg|hz|mhz|mpa|\u00b0|\u00b1|\u00d7|x)\s*$",
        prefix,
    ):
        return False
    if not re.search(r"[a-z][a-z),.;:'\"\s-]{0,60}$", prefix, re.IGNORECASE):
        return False
    return True


def _reference_recovery_block_is_protected(attrs: str, body: str) -> bool:
    lower = f"{attrs} {body}".lower()
    if REFERENCE_RECOVERY_PROTECTED_CLASS_RE.search(lower):
        return True
    if re.search(r"</?(?:table|thead|tbody|tfoot|tr|td|th|math|script|style|code|pre|figure|figcaption)\b", lower):
        return True
    if REF_HREF_RE.search(body):
        return True
    visible = _visible_html_text(body)
    if len(visible) < 12:
        return True
    if re.match(r"^(?:fig(?:ure)?|table|eq(?:uation)?|appendix|supplement|formula)\b", visible, re.IGNORECASE):
        return True
    return False


def _unlinked_body_reference_candidate_numbers(html: str) -> list[int]:
    numbers: list[int] = []
    blocks = list(P_BLOCK_RE.finditer(html))
    if not blocks:
        fallback_match = re.match(r"(?P<attrs>)(?P<body>[\s\S]*)", html)
        blocks = [fallback_match] if fallback_match is not None else []
    for block in blocks:
        if block is None:
            continue
        attrs = block.group("attrs") or ""
        body = block.group("body") or ""
        if _reference_recovery_block_is_protected(attrs, body):
            continue
        text = _visible_html_text(body)
        for match in BRACKETED_BODY_REFERENCE_CANDIDATE_RE.finditer(text):
            numbers.extend(_expand_reference_candidate_numbers(match.group("body")))
        for match in PLAIN_BODY_REFERENCE_CANDIDATE_RE.finditer(text):
            if not _plain_reference_candidate_is_safe(text, match):
                continue
            numbers.extend(_expand_reference_candidate_numbers(match.group("body")))

    deduped: list[int] = []
    seen: set[int] = set()
    for number in numbers:
        if number not in seen:
            seen.add(number)
            deduped.append(number)
    return sorted(deduped)


def _pdf_reference_recovery_numbers(polished_html: str) -> tuple[list[int], str]:
    ref_ids = _reference_id_numbers(polished_html)
    gap_numbers = _reference_id_gap_numbers(polished_html)
    if gap_numbers:
        return gap_numbers, "gap"
    if ref_ids:
        return [], ""
    body_numbers = _unlinked_body_reference_candidate_numbers(polished_html)
    if body_numbers:
        return body_numbers, "body_citation"
    return [], ""


def _profile_has_reference_entries(profile: dict[str, Any]) -> bool:
    return bool(profile.get("reference_entries"))


def _reference_entry_record(entry: Any) -> dict[str, Any]:
    return {
        "page": int(getattr(entry, "page", 0) or 0),
        "number": int(getattr(entry, "number", 0) or 0),
        "text": str(getattr(entry, "text", "") or ""),
    }


def _enrich_profile_with_pdf_reference_entries_if_needed(
    profile: dict[str, Any],
    polished_html: str,
    source_run_dir: Path,
    article: str,
    manifest_article: dict[str, Any],
    pdf_reference_cache: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], int, str]:
    if _profile_has_reference_entries(profile):
        return profile, 0, ""
    recovery_numbers, recovery_trigger = _pdf_reference_recovery_numbers(polished_html)
    if not recovery_numbers:
        return profile, 0, ""
    recovery_set = set(recovery_numbers)
    candidates = _article_source_pdf_candidates(source_run_dir, article, {}, manifest_article)
    for candidate in candidates:
        if not candidate.get("exists"):
            continue
        pdf_path = Path(str(candidate.get("path") or "")).expanduser()
        if not pdf_path.is_file():
            continue
        cache_key = str(pdf_path.resolve(strict=False))
        if cache_key not in pdf_reference_cache:
            pdf_reference_cache[cache_key] = [
                _reference_entry_record(entry)
                for entry in extract_reference_entries_from_pdf(pdf_path)
                if getattr(entry, "number", 0) and getattr(entry, "text", "")
            ]
        entries = pdf_reference_cache[cache_key]
        matched = [entry for entry in entries if int(entry.get("number", 0) or 0) in recovery_set]
        if not matched:
            continue
        updated = dict(profile)
        updated["reference_entries"] = entries
        updated["reference_entries_status"] = (
            "loaded_from_source_pdf_gap_recovery"
            if recovery_trigger == "gap"
            else "loaded_from_source_pdf_citation_recovery"
        )
        updated["reference_entries_count"] = len(entries)
        updated["reference_entries_source_pdf"] = cache_key
        updated["reference_entries_missing_ids"] = sorted(recovery_set)
        updated["reference_entries_recovery_numbers"] = sorted(recovery_set)
        updated["reference_entries_recovery_matched_numbers"] = sorted(
            {int(entry.get("number", 0) or 0) for entry in matched}
        )
        updated["reference_entries_recovery_trigger"] = recovery_trigger
        return updated, len(matched), cache_key
    return profile, 0, ""


def normalize_converted_audit_article_ids(run_dir: Path) -> dict[str, Any]:
    """Rewrite audit article names to unique converted-run artifact ids."""

    manifest = _load_json(run_dir / "manifest.json", default={})
    audit = _load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    if manifest.get("source_kind") != "converted_stage_roots":
        return audit

    by_pair = _converted_manifest_by_pair(manifest)
    unmatched: list[dict[str, Any]] = []
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        raw_path = _norm_path(article.get("raw_stage_path"))
        polish_path = _norm_path(article.get("polish_stage_path"))
        manifest_article = by_pair.get((raw_path, polish_path))
        if not manifest_article:
            unmatched.append({"raw_stage_path": raw_path, "polish_stage_path": polish_path})
            continue
        article["source_article"] = article.get("source_article") or article.get("article")
        article["article"] = manifest_article["article_id"]
        article["artifact_hint"] = manifest_article.get("artifact_hint")

    audit["article_count"] = len(audit.get("articles") or [])
    if unmatched:
        audit["converted_id_normalization_unmatched"] = unmatched
    _write_json(run_dir / "audit_full_checks.json", audit)
    return audit


def repolish_cached_run(
    source_run_dir: Path,
    out_dir: Path,
    *,
    polish_language: str | None = None,
    target_language: str = "en",
    skip_non_target_language: bool = False,
    skip_unknown_language: bool = False,
) -> dict[str, Any]:
    """Regenerate polish HTML from a run directory containing raw_cache/profiles."""
    source_run_dir = source_run_dir.resolve(strict=False)
    out_dir = out_dir.resolve(strict=False)
    raw_source_dir = source_run_dir / "raw_cache"
    profile_source_dir = source_run_dir / "profiles"
    if not raw_source_dir.is_dir():
        raise FileNotFoundError(f"Missing raw_cache directory: {raw_source_dir}")

    raw_out = out_dir / "raw_cache"
    profile_out = out_dir / "profiles"
    polish_out = out_dir / "polish"
    audit_tree = out_dir / "audit_tree"
    for path in (raw_out, profile_out, polish_out, audit_tree):
        path.mkdir(parents=True, exist_ok=True)

    articles: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    skipped_articles: list[dict[str, Any]] = []
    profile_status_counts: dict[str, int] = {}
    profile_style_counts: dict[str, int] = {}
    language_counts: Counter[str] = Counter()
    polish_language_counts: Counter[str] = Counter()
    skip_reason_counts: Counter[str] = Counter()
    changed_count = 0
    restored_image_count = 0
    restored_image_source_counts: Counter[str] = Counter()
    pdf_reference_recovery_count = 0
    pdf_reference_recovery_source_counts: Counter[str] = Counter()
    pdf_reference_entries_cache: dict[str, list[dict[str, Any]]] = {}
    source_manifest = _load_json(source_run_dir / "manifest.json", default={})

    try:
        raw_files = sorted(raw_source_dir.glob(f"*.{RAW_STAGE}"))
        total_raw = len(raw_files)
        print(f"Repolish started: raw={total_raw} source={source_run_dir}", flush=True)
        last_report = time.monotonic()

        def report_progress(index: int, *, force: bool = False) -> None:
            nonlocal last_report
            now = time.monotonic()
            if force or index % 25 == 0 or now - last_report >= 15:
                print(
                    "Repolish progress: "
                    f"{index}/{total_raw} articles={len(articles)} "
                    f"skipped={len(skipped_articles)} changed={changed_count}",
                    flush=True,
                )
                last_report = now

        for index, raw_path in enumerate(raw_files, start=1):
            article = raw_path.name.removesuffix(f".{RAW_STAGE}")
            manifest_article = _manifest_article_for(source_manifest, article) or {}
            profile_path = profile_source_dir / f"{article}.citation_profile.json"
            profile = (
                _load_json(profile_path)
                if profile_path.is_file()
                else {"status": "missing_profile", "style": "unknown", "confidence": "low"}
            )
            raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
            out_raw = raw_out / raw_path.name
            out_profile = profile_out / f"{article}.citation_profile.json"
            out_polish = polish_out / f"{article}.{POLISH_STAGE}"
            shutil.copy2(raw_path, out_raw)
            if profile_path.is_file():
                shutil.copy2(profile_path, out_profile)
            else:
                _write_json(out_profile, profile)

            language_decision = resolve_document_polish_language(
                raw_html,
                table_caption_language="en",
                polish_language=polish_language,
                target_language=target_language,
                skip_non_target_language=skip_non_target_language,
                skip_unknown_language=skip_unknown_language,
            )
            language_fields = language_decision.to_flat_report_fields()
            language_counts[language_decision.detection.detected_language] += 1
            if language_decision.should_skip:
                skip_reason_counts[language_decision.skip_reason] += 1
                skipped_articles.append(
                    {
                        "index": index,
                        "article": article,
                        "raw_cache_path": str(out_raw),
                        "profile_path": str(out_profile),
                        "profile_status": _profile_value(profile, "status"),
                        "citation_style": _profile_value(profile, "style"),
                        "citation_confidence": _profile_value(profile, "confidence"),
                        "language_detection": language_decision.detection.to_dict(),
                        **language_fields,
                    }
                )
                report_progress(index)
                continue

            polish_language_counts[language_decision.selected_polish_language] += 1
            polished = polish_html_document(
                raw_html,
                table_caption_language="en",
                enable_citation_linkify=True,
                citation_profile=profile,
                polish_language=language_decision.selected_polish_language,
            )
            profile, recovered_pdf_refs, pdf_reference_source = _enrich_profile_with_pdf_reference_entries_if_needed(
                profile,
                polished,
                source_run_dir,
                article,
                manifest_article,
                pdf_reference_entries_cache,
            )
            if recovered_pdf_refs:
                pdf_reference_recovery_count += recovered_pdf_refs
                pdf_reference_recovery_source_counts[pdf_reference_source] += recovered_pdf_refs
                _write_json(out_profile, profile)
                polished = polish_html_document(
                    raw_html,
                    table_caption_language="en",
                    enable_citation_linkify=True,
                    citation_profile=profile,
                    polish_language=language_decision.selected_polish_language,
                )
            data_image_cache, data_image_source = _cached_data_image_cache(source_run_dir, article, raw_html)
            polished, restored_images = _apply_data_image_cache(polished, data_image_cache)
            if restored_images:
                restored_image_count += restored_images
                restored_image_source_counts[data_image_source or "unknown"] += restored_images
            previous_polish = source_run_dir / "polish" / out_polish.name
            previous_text = (
                previous_polish.read_text(encoding="utf-8", errors="replace")
                if previous_polish.is_file()
                else None
            )
            changed = previous_text != polished
            if changed:
                changed_count += 1
            out_polish.write_text(polished, encoding="utf-8")

            pair_dir = audit_tree / article
            pair_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out_raw, pair_dir / RAW_STAGE)
            (pair_dir / POLISH_STAGE).write_text(polished, encoding="utf-8")

            status = _profile_value(profile, "status")
            style_key = f"{_profile_value(profile, 'style')}:{_profile_value(profile, 'confidence')}"
            profile_status_counts[status] = profile_status_counts.get(status, 0) + 1
            profile_style_counts[style_key] = profile_style_counts.get(style_key, 0) + 1
            articles.append(
                {
                    "index": index,
                    "article": article,
                    "raw_cache_path": str(out_raw),
                    "profile_path": str(out_profile),
                    "polish_path": str(out_polish),
                    "profile_status": status,
                    "citation_style": _profile_value(profile, "style"),
                    "citation_confidence": _profile_value(profile, "confidence"),
                    "changed": changed,
                    "restored_images": restored_images,
                    "restored_image_source": data_image_source,
                    "pdf_reference_recovered": recovered_pdf_refs,
                    "pdf_reference_source": pdf_reference_source,
                    "language_detection": language_decision.detection.to_dict(),
                    **language_fields,
                }
            )
            assessment = assess_polish_html(article, polished, profile)
            assessment.update(language_fields)
            assessments.append(assessment)
            report_progress(index)
        report_progress(total_raw, force=True)
    finally:
        close_katex_v8_context()

    totals, problematic = _assessment_totals(assessments)
    manifest = {
        "generated_at": _now(),
        "source_kind": "cached_raw_repolish",
        "mandatory_corpus_repolish": True,
        "source_run_dir": str(source_run_dir),
        "out_dir": str(out_dir),
        "code_commit": _git_short_head(),
        "working_tree_dirty": _git_dirty(),
        "polish_language": polish_language or "en",
        "target_language": target_language,
        "skip_non_target_language": skip_non_target_language,
        "skip_unknown_language": skip_unknown_language,
        "raw_count": len(raw_files),
        "article_count": len(articles),
        "skipped_count": len(skipped_articles),
        "changed_count": changed_count,
        "raw_cache_dir": str(raw_out),
        "profile_dir": str(profile_out),
        "polish_dir": str(polish_out),
        "audit_tree_dir": str(audit_tree),
        "language_counts": dict(sorted(language_counts.items())),
        "polish_language_counts": dict(sorted(polish_language_counts.items())),
        "skip_reason_counts": dict(sorted(skip_reason_counts.items())),
        "restored_image_count": restored_image_count,
        "restored_image_source_counts": dict(sorted(restored_image_source_counts.items())),
        "pdf_reference_recovery_count": pdf_reference_recovery_count,
        "pdf_reference_recovery_source_counts": dict(sorted(pdf_reference_recovery_source_counts.items())),
        "profile_status_counts": dict(sorted(profile_status_counts.items())),
        "profile_style_counts": dict(sorted(profile_style_counts.items())),
        "articles": articles,
        "skipped_articles": skipped_articles,
    }
    assessment = {
        "generated_at": _now(),
        "source_kind": "cached_raw_repolish",
        "raw_count": len(raw_files),
        "article_count": len(assessments),
        "skipped_count": len(skipped_articles),
        "run_dir": str(out_dir),
        "code_commit": _git_short_head(),
        "working_tree_dirty": _git_dirty(),
        "target_language": target_language,
        "skip_non_target_language": skip_non_target_language,
        "skip_unknown_language": skip_unknown_language,
        "language_counts": manifest["language_counts"],
        "polish_language_counts": manifest["polish_language_counts"],
        "skip_reason_counts": manifest["skip_reason_counts"],
        "totals": totals,
        "profile_status_counts": manifest["profile_status_counts"],
        "profile_style_counts": manifest["profile_style_counts"],
        "problematic_articles": problematic,
        "articles": assessments,
    }
    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "assessment.json", assessment)
    return manifest


def load_gate_config(path: Path = DEFAULT_GATE_CONFIG) -> dict[str, Any]:
    return quality_gates.load_gate_config(path)


def evaluate_quality_gate(
    comparison: dict[str, Any],
    gate_config: dict[str, Any],
    *,
    article_review_report: dict[str, Any] | None = None,
    audit_report: dict[str, Any] | None = None,
    audit_command_report: dict[str, Any] | None = None,
    pdf_problem_evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return quality_gates.evaluate_quality_gate(
        comparison,
        gate_config,
        article_review_report=article_review_report,
        audit_report=audit_report,
        audit_command_report=audit_command_report,
        pdf_problem_evidence_report=pdf_problem_evidence_report,
    )


def _defect_summary(defect: dict[str, Any], defect_patterns: dict[str, Any]) -> dict[str, Any]:
    defect_id = str(defect.get("id") or "unknown")
    pattern = defect_patterns.get(defect_id) if isinstance(defect_patterns.get(defect_id), dict) else {}
    return {
        "id": defect_id,
        "severity": defect.get("severity"),
        "check": defect.get("check"),
        "snippet": _compact_observation_text(defect.get("snippet")),
        "hypothesis": _compact_observation_text(defect.get("hypothesis"), max_len=300),
        "proposed_fix_layer": _compact_observation_text(defect.get("proposed_fix_layer"), max_len=180),
        "regression_test": _compact_observation_text(defect.get("regression_test"), max_len=240),
        "same_pattern_hits_across_corpus": defect.get("same_pattern_hits_across_corpus"),
        "known_pattern": pattern.get("pattern"),
        "known_criticality": pattern.get("criticality"),
        "known_fix_layer": pattern.get("fix_layer"),
    }


def _comparison_by_article(comparison: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for bucket in ("regressions", "improvements", "unchanged"):
        for item in comparison.get(bucket) or []:
            if item.get("article"):
                result[str(item["article"])] = {"bucket": bucket, **item}
    return result


def _changed_without_quality_delta_reviews(
    manifest: dict[str, Any],
    comparison: dict[str, Any],
    *,
    entry_articles: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Articles changed by repolish but not explained by quality deltas.

    These are mandatory sanity-review items: the patch touched the artifact, but
    the run's targeted audit improvement/regression buckets did not explain the
    change. They are the highest-risk blind spots for silent link/text drift.
    """

    deltas = _comparison_by_article(comparison)
    entry_articles = entry_articles or {}
    reviews: list[dict[str, Any]] = []
    for item in manifest.get("articles") or []:
        if not isinstance(item, dict) or not item.get("changed"):
            continue
        article_id = item.get("article_id") or item.get("article")
        if not article_id:
            continue
        article_id = str(article_id)
        comparison_item = deltas.get(article_id, {})
        if comparison_item.get("bucket") != "unchanged":
            continue
        record = entry_articles.get(article_id, {}) if isinstance(entry_articles, dict) else {}
        reviews.append(
            {
                "article": article_id,
                "source_article": item.get("article") or article_id,
                "reason": "changed_without_quality_delta",
                "review_requirement": (
                    "Mandatory sanity review: polish output changed, but the article was not in "
                    "the improvement/regression set for the run."
                ),
                "score": record.get("score", 0),
                "defect_ids": record.get("defect_ids", {}),
                "comparison": comparison_item,
                "raw_stage_path": item.get("raw_stage_path") or item.get("raw_cache_path"),
                "polish_stage_path": item.get("polish_stage_path") or item.get("polish_path"),
                "profile_path": item.get("profile_path"),
            }
        )
    reviews.sort(key=lambda item: (-float(item.get("score") or 0), str(item.get("article") or "")))
    return reviews


def _defect_id_counts(defects: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for defect in defects:
        defect_id = str(defect.get("id") or "unknown")
        counts[defect_id] = counts.get(defect_id, 0) + 1
    return dict(sorted(counts.items()))


def _severity_counts(defects: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for defect in defects:
        severity = str(defect.get("severity") or "info")
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def write_manual_observation_summary(
    run_dir: Path,
    *,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    return _write_manual_observation_summary(
        run_dir,
        ledger_path=ledger_path,
        default_ledger_name=DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME,
    )


def _existing_queue_items(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = _load_json(path, default=[])
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    return []


def _review_state_by_key(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
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
    gate_config_path: Path = DEFAULT_GATE_CONFIG,
    gate_config: dict[str, Any] | None = None,
    ignored_defect_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Write all audited articles sorted by review priority.

    Unlike the LLM pack, this queue keeps every article, including articles
    whose only current defects are ignored for analysis.  It is the hand-review
    ledger for continuing the loop article by article.
    """

    gate_config = gate_config or load_gate_config(gate_config_path)
    ignored = set(gate_config.get("ignored_defect_ids_for_analysis") or [])
    if ignored_defect_ids:
        ignored.update(ignored_defect_ids)

    run_dir = run_dir.resolve(strict=False)
    audit = _load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    entry = _load_json(run_dir / "quality_history_entry.json", default={"articles": {}})
    assessment = _load_json(run_dir / "assessment.json", default={"articles": []})
    manifest = _load_json(run_dir / "manifest.json", default={})

    entry_articles = entry.get("articles") if isinstance(entry.get("articles"), dict) else {}
    assessment_by_article = {
        str(article.get("article")): article
        for article in assessment.get("articles", [])
        if isinstance(article, dict) and article.get("article")
    }
    manifest_by_article = _manifest_article_by_id(manifest)
    comparison = _load_json(run_dir / "quality_compare.json", default={"status": "no_previous_entry"})
    deltas = _comparison_by_article(comparison)
    previous_state = _review_state_by_key(_existing_queue_items(run_dir / "manual_review_queue.json"))

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
                "defect_ids": _defect_id_counts(defects),
                "non_ignored_defect_ids": _defect_id_counts(non_ignored),
                "severity_counts": _severity_counts(defects),
                "non_ignored_severity_counts": _severity_counts(non_ignored),
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
    _write_json(run_dir / "manual_review_queue.json", queue)
    return queue


def _stage_path_for_review(run_dir: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        run_candidate = (run_dir / path).resolve(strict=False)
        if run_candidate.exists():
            return run_candidate
        root_candidate = (ROOT / path).resolve(strict=False)
        if root_candidate.exists():
            return root_candidate
        return run_candidate
    return path.resolve(strict=False)


def _relative_review_href(review_dir: Path, target_path: Path) -> str:
    try:
        rel = target_path.resolve(strict=False).relative_to(review_dir.resolve(strict=False))
    except ValueError:
        rel = target_path.resolve(strict=False)
    return urllib.parse.quote(str(rel).replace("\\", "/"), safe="/:#?&=%._-")


def write_article_review_stage(
    run_dir: Path,
    review_queue: list[dict[str, Any]] | None = None,
    *,
    max_articles: int | None = None,
) -> dict[str, Any]:
    """Build the mandatory changed-article review bundle for a loop run."""

    run_dir = run_dir.resolve(strict=False)
    review_queue = review_queue if review_queue is not None else _existing_queue_items(run_dir / "manual_review_queue.json")
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
        source_path = _stage_path_for_review(run_dir, item.get("polish_stage_path"))
        target_path = review_dir / f"{index:03d}_{_slug(article, max_len=72)}" / POLISH_STAGE
        copy_info: dict[str, Any] = {}
        if source_path is not None and source_path.is_file():
            try:
                copy_info = _copy_review_html_with_inline_images(source_path, target_path)
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
                    _relative_review_href(review_dir, Path(str(copy_info["review_html"])))
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
        "generated_at": _now(),
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
    _write_json(run_dir / "article_review_report.json", report)
    return report


def write_pattern_observations(
    run_dir: Path,
    *,
    defect_patterns_path: Path = DEFAULT_DEFECT_PATTERNS,
    defect_patterns: dict[str, Any] | None = None,
    history_path: Path | None = None,
) -> dict[str, Any]:
    return _write_pattern_observations(
        run_dir,
        defect_patterns_path=defect_patterns_path,
        defect_patterns=defect_patterns,
        history_path=history_path,
        default_history_name=DEFAULT_PATTERN_HISTORY_NAME,
    )


def write_resolver_decisions(run_dir: Path) -> dict[str, Any]:
    return _write_resolver_decisions(run_dir, output_name=DEFAULT_RESOLVER_DECISIONS_NAME)


def build_analysis_pack(
    run_dir: Path,
    *,
    max_articles: int = 12,
    gate_config: dict[str, Any] | None = None,
    defect_patterns: dict[str, Any] | None = None,
    ignored_defect_ids: set[str] | None = None,
) -> dict[str, Any]:
    gate_config = gate_config or load_gate_config()
    defect_patterns = defect_patterns or _load_json(DEFAULT_DEFECT_PATTERNS, default={})
    ignored = set(gate_config.get("ignored_defect_ids_for_analysis") or [])
    if ignored_defect_ids:
        ignored.update(ignored_defect_ids)

    run_dir = run_dir.resolve(strict=False)
    audit = _load_json(run_dir / "audit_full_checks.json", default={"articles": [], "corpus_summary": {}})
    assessment = _load_json(run_dir / "assessment.json", default={"articles": [], "totals": {}})
    entry = _load_json(run_dir / "quality_history_entry.json", default={"articles": {}, "ranking": [], "totals": {}})
    comparison = _load_json(run_dir / "quality_compare.json", default={"status": "no_previous_entry"})
    manifest = _load_json(run_dir / "manifest.json", default={})
    pattern_observations = _load_json(run_dir / "pattern_observations.json", default={})
    manual_observations = _load_json(run_dir / "manual_observation_summary.json", default={})
    article_review_report = _load_json(run_dir / "article_review_report.json", default={})
    pdf_problem_evidence_report = _load_json(run_dir / DEFAULT_PDF_PROBLEM_EVIDENCE_NAME, default={})
    resolver_decisions_report = _load_json(run_dir / DEFAULT_RESOLVER_DECISIONS_NAME, default={})
    p62_marker_recovery_report = _load_json(run_dir / DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME, default={})
    p62_image_recovery_report = _load_json(run_dir / DEFAULT_P62_IMAGE_RECOVERY_REPORT_NAME, default={})
    polish_auto_repair_report = _load_json(run_dir / DEFAULT_POLISH_AUTO_REPAIR_REPORT_NAME, default={})
    deltas = _comparison_by_article(comparison)
    manifest_by_article = _manifest_article_by_id(manifest)
    resolver_by_article: dict[str, list[dict[str, Any]]] = {}
    for decision in resolver_decisions_report.get("decisions") or []:
        if not isinstance(decision, dict) or not decision.get("article"):
            continue
        resolver_by_article.setdefault(str(decision["article"]), []).append(decision)
    assessment_by_article = {
        str(article.get("article")): article
        for article in assessment.get("articles", [])
        if article.get("article")
    }
    entry_articles = entry.get("articles") if isinstance(entry.get("articles"), dict) else {}
    mandatory_changed_reviews = _changed_without_quality_delta_reviews(
        manifest,
        comparison,
        entry_articles=entry_articles,
    )

    candidates: list[dict[str, Any]] = []
    for article in audit.get("articles", []):
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        article_resolver_decisions = resolver_by_article.get(article_id) or []
        accepted_telemetry_ids = {
            str(decision.get("defect_id") or "")
            for decision in article_resolver_decisions
            if decision.get("decision") == "accepted_telemetry"
        }
        article_slot_repair_ids = {
            str(decision.get("defect_id") or "")
            for decision in article_resolver_decisions
            if decision.get("decision") in ARTICLE_SLOT_REPAIR_DECISION_NAMES
        }
        defects = [
            defect
            for defect in article.get("defects_found", [])
            if str(defect.get("id") or "") not in accepted_telemetry_ids
            and (
                str(defect.get("id") or "") not in ignored
                or str(defect.get("id") or "") in article_slot_repair_ids
            )
        ]
        record = entry_articles.get(article_id, {}) if isinstance(entry_articles, dict) else {}
        assessment_article = assessment_by_article.get(article_id, {})
        manifest_article = manifest_by_article.get(article_id, {})
        score = float(record.get("score", 0) or 0)
        article_slot_repair_count = sum(
            1
            for decision in article_resolver_decisions
            if decision.get("decision") in ARTICLE_SLOT_REPAIR_DECISION_NAMES
        )
        accepted_telemetry_count = sum(
            1 for decision in article_resolver_decisions if decision.get("decision") == "accepted_telemetry"
        )
        selection_reasons: list[str] = []
        if defects:
            selection_reasons.append("non_telemetry_defects")
        if article_slot_repair_count:
            selection_reasons.append("resolver_repair_candidate")
        if article_id in deltas:
            selection_reasons.append("history_delta")
        if not selection_reasons:
            continue
        candidates.append(
            {
                "article": article_id,
                "source_article": (
                    article.get("source_article")
                    or assessment_article.get("source_article")
                    or manifest_article.get("article")
                    or article_id
                ),
                "artifact_hint": (
                    article.get("artifact_hint")
                    or assessment_article.get("artifact_hint")
                    or manifest_article.get("artifact_hint")
                ),
                "score": score,
                "non_ignored_defect_count": len(defects),
                "resolver_repair_candidate_count": article_slot_repair_count,
                "accepted_telemetry_count": accepted_telemetry_count,
                "selection_reasons": selection_reasons,
                "defects": defects,
                "audit_summary": article.get("summary", {}),
                "source_pdf_candidates": _article_source_pdf_candidates(
                    run_dir,
                    article_id,
                    article.get("summary", {}),
                    manifest_article,
                ),
                "assessment": assessment_article,
                "history_record": record,
                "comparison": deltas.get(article_id, {}),
                "raw_stage_path": (
                    article.get("raw_stage_path")
                    or assessment_article.get("raw_stage_path")
                    or manifest_article.get("raw_stage_path")
                ),
                "polish_stage_path": (
                    article.get("polish_stage_path")
                    or assessment_article.get("polish_stage_path")
                    or manifest_article.get("polish_stage_path")
                ),
            }
        )

    candidates.sort(
        key=lambda item: (
            -int(item["resolver_repair_candidate_count"]),
            -float(item["comparison"].get("score_delta", 0) or 0),
            -int(item["non_ignored_defect_count"]),
            -float(item["score"]),
            str(item["article"]),
        )
    )

    articles: list[dict[str, Any]] = []
    for item in candidates[:max_articles]:
        defect_ids: dict[str, int] = {}
        for defect in item["defects"]:
            defect_id = str(defect.get("id") or "unknown")
            defect_ids[defect_id] = defect_ids.get(defect_id, 0) + 1
        articles.append(
            {
                "article": item["article"],
                "source_article": item["source_article"],
                "artifact_hint": item["artifact_hint"],
                "score": item["score"],
                "non_ignored_defect_count": item["non_ignored_defect_count"],
                "resolver_repair_candidate_count": item["resolver_repair_candidate_count"],
                "accepted_telemetry_count": item["accepted_telemetry_count"],
                "selection_reasons": item["selection_reasons"],
                "defect_ids": dict(sorted(defect_ids.items())),
                "comparison": item["comparison"],
                "labels": item["history_record"].get("labels", {}),
                "metrics": item["history_record"].get("metrics", {}),
                "assessment": item["assessment"],
                "audit_summary": item["audit_summary"],
                "source_pdf_candidates": item["source_pdf_candidates"],
                "raw_stage_path": item["raw_stage_path"],
                "polish_stage_path": item["polish_stage_path"],
                "defects": [_defect_summary(defect, defect_patterns) for defect in item["defects"][:12]],
                "resolver_decisions": (resolver_by_article.get(str(item["article"])) or [])[:12],
            }
        )

    pack = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "run_id": entry.get("run_id") or run_dir.name,
        "code_commit": manifest.get("code_commit"),
        "raw_count": manifest.get("raw_count"),
        "skipped_count": manifest.get("skipped_count"),
        "ignored_defect_ids": sorted(ignored),
        "article_count": manifest.get("article_count") or assessment.get("article_count"),
        "language_counts": manifest.get("language_counts") or assessment.get("language_counts") or {},
        "polish_language_counts": manifest.get("polish_language_counts")
        or assessment.get("polish_language_counts")
        or {},
        "skip_reason_counts": manifest.get("skip_reason_counts") or assessment.get("skip_reason_counts") or {},
        "quality_totals": entry.get("totals", {}),
        "assessment_totals": assessment.get("totals", {}),
        "comparison_status": comparison.get("status"),
        "comparison_totals_delta": comparison.get("totals_delta", {}),
        "comparison_comparable_totals_delta": comparison.get("comparable_totals_delta", {}),
        "new_article_count": comparison.get("new_article_count", 0),
        "removed_article_count": comparison.get("removed_article_count", 0),
        "regression_count": len(comparison.get("regressions") or []),
        "improvement_count": len(comparison.get("improvements") or []),
        "mandatory_changed_review_count": len(mandatory_changed_reviews),
        "mandatory_changed_review_articles": mandatory_changed_reviews[:50],
        "article_review_stage": {
            "status": article_review_report.get("status"),
            "review_dir": article_review_report.get("review_dir"),
            "index_html": article_review_report.get("index_html"),
            "mandatory_count": article_review_report.get("mandatory_count", 0),
            "pending_mandatory_count": article_review_report.get("pending_mandatory_count", 0),
            "selected_count": article_review_report.get("selected_count", 0),
        },
        "audit_defect_counts": audit.get("corpus_summary", {}).get("defect_counts", {}),
        "resolver_decisions": {
            "path": resolver_decisions_report.get("path")
            or str(run_dir / DEFAULT_RESOLVER_DECISIONS_NAME),
            "decision_count": resolver_decisions_report.get("decision_count", 0),
            "article_count": resolver_decisions_report.get("article_count", 0),
            "observed_non_quality_count": resolver_decisions_report.get("observed_non_quality_count", 0),
            "quality_counted_count": resolver_decisions_report.get("quality_counted_count", 0),
            "decision_counts": resolver_decisions_report.get("decision_counts", {}),
            "defect_id_counts": resolver_decisions_report.get("defect_id_counts", {}),
            "accepted_telemetry_counts": resolver_decisions_report.get("accepted_telemetry_counts", {}),
            "repair_candidate_counts": resolver_decisions_report.get("repair_candidate_counts", {}),
            "manual_or_llm_count": resolver_decisions_report.get("manual_or_llm_count", 0),
            "repair_candidate_groups": (resolver_decisions_report.get("repair_candidate_groups") or [])[:12],
            "accepted_telemetry_groups": (resolver_decisions_report.get("accepted_telemetry_groups") or [])[:12],
            "manual_or_llm_groups": (resolver_decisions_report.get("manual_or_llm_groups") or [])[:12],
            "automation_plan": resolver_decisions_report.get("automation_plan") or [],
        },
        "p62_marker_recovery_plan": {
            "path": p62_marker_recovery_report.get("path")
            or str(run_dir / DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME),
            "status": p62_marker_recovery_report.get("status"),
            "output_root": p62_marker_recovery_report.get("output_root"),
            "candidate_count": p62_marker_recovery_report.get("candidate_count", 0),
            "selected_count": p62_marker_recovery_report.get("selected_count", 0),
            "ready_count": p62_marker_recovery_report.get("ready_count", 0),
            "unresolved_count": p62_marker_recovery_report.get("unresolved_count", 0),
            "status_counts": p62_marker_recovery_report.get("status_counts", {}),
            "marker_output_status_counts": p62_marker_recovery_report.get("marker_output_status_counts", {}),
            "marker_page_range_indexing": p62_marker_recovery_report.get("marker_page_range_indexing"),
            "require_label_match": p62_marker_recovery_report.get("require_label_match"),
            "ready_samples": (p62_marker_recovery_report.get("ready_samples") or [])[:8],
        },
        "p62_image_recovery_stage": {
            "path": p62_image_recovery_report.get("path")
            or str(run_dir / DEFAULT_P62_IMAGE_RECOVERY_REPORT_NAME),
            "status": p62_image_recovery_report.get("status"),
            "output_root": p62_image_recovery_report.get("output_root"),
            "candidate_count": p62_image_recovery_report.get("candidate_count", 0),
            "selected_count": p62_image_recovery_report.get("selected_count", 0),
            "asset_ready_count": p62_image_recovery_report.get("asset_ready_count", 0),
            "patched_warning_count": p62_image_recovery_report.get("patched_warning_count", 0),
            "duplicate_visual_repair_count": p62_image_recovery_report.get("duplicate_visual_repair_count", 0),
            "patch_missed_count": p62_image_recovery_report.get("patch_missed_count", 0),
            "unresolved_count": p62_image_recovery_report.get("unresolved_count", 0),
            "status_counts": p62_image_recovery_report.get("status_counts", {}),
            "recovery_source_counts": p62_image_recovery_report.get("recovery_source_counts", {}),
            "source_visual_probe_status_counts": p62_image_recovery_report.get(
                "source_visual_probe_status_counts",
                {},
            ),
            "probe_marker_for_unavailable": p62_image_recovery_report.get("probe_marker_for_unavailable"),
            "execute_marker": p62_image_recovery_report.get("execute_marker"),
            "apply_patches": p62_image_recovery_report.get("apply_patches"),
        },
        "polish_auto_repair_stage": {
            "path": polish_auto_repair_report.get("path")
            or str(run_dir / DEFAULT_POLISH_AUTO_REPAIR_REPORT_NAME),
            "status": polish_auto_repair_report.get("status"),
            "candidate_count": polish_auto_repair_report.get("candidate_count", 0),
            "patched_article_count": polish_auto_repair_report.get("patched_article_count", 0),
            "repair_counts": polish_auto_repair_report.get("repair_counts", {}),
            "apply_patches": polish_auto_repair_report.get("apply_patches"),
        },
        "pattern_observations": {
            "history_path": pattern_observations.get("history_path"),
            "article_count_reviewed": pattern_observations.get("article_count_reviewed"),
            "pattern_count": pattern_observations.get("pattern_count"),
            "all_articles_reviewed_for_patterns": pattern_observations.get("all_articles_reviewed_for_patterns"),
            "problem_candidates": (pattern_observations.get("problem_candidates") or [])[:12],
            "current_patterns": (pattern_observations.get("patterns") or [])[:12],
            "cumulative_patterns": (pattern_observations.get("cumulative_patterns") or [])[:12],
        },
        "manual_observations": {
            "ledger_path": manual_observations.get("ledger_path"),
            "ledger_entry_count": manual_observations.get("ledger_entry_count", 0),
            "observation_count": manual_observations.get("observation_count", 0),
            "group_count": manual_observations.get("group_count", 0),
            "problem_candidates": (manual_observations.get("problem_candidates") or [])[:12],
            "requires_triage": (manual_observations.get("requires_triage") or [])[:12],
            "groups": (manual_observations.get("groups") or [])[:12],
        },
        "articles": articles,
    }
    if isinstance(pdf_problem_evidence_report, dict) and pdf_problem_evidence_report:
        _attach_pdf_evidence_to_pack(pack, pdf_problem_evidence_report)
    return pack


def render_llm_prompt(pack: dict[str, Any]) -> str:
    lines = [
        "# EN Polish LLM Quality Review",
        "",
        "You are reviewing a pdf-html-translator EN polish experiment.",
        "Ignore defect ids listed in `ignored_defect_ids` unless they interact with a text/link problem.",
        "Classify universal root causes, propose the smallest code layer to fix them, and name regression tests.",
        "Do not propose broad rewrites when a local repair or guard is enough.",
        "Every production artifact fix must include a focused regression test that reproduces the observed symptom.",
        "Also add at least one guard/negative test when the repair could touch links, tags, math, code, language policy, or nearby article classes.",
        "Pattern observations must be accumulated globally across loop iterations before local manifestations are promoted into shared problem statements.",
        "Review the all-article current pattern summary and the cumulative pattern history before proposing a fix.",
        "During problem analysis, render the implicated source PDF page(s), extract the PDF text layer for those page(s), and compare both against raw/polish HTML before classifying the root cause; when stage-local source_pdf_present=false, search the Zotero/source_exports PDF candidates listed in source_pdf_candidates before declaring the PDF unavailable.",
        "A problem classification is incomplete unless it cites source PDF page-render evidence and PDF text-layer evidence, or records that the source PDF/evidence was unavailable.",
        "Any newly noticed manual manifestation that is not already captured by the audit must be recorded in the manual observation ledger before analysis or repair.",
        "Manual observations stay raw until their cumulative groups justify a shared problem statement, except for clearly severe regressions.",
        "For every confirmed manual observation, add or update audit/repair/false-positive test coverage and mark the observation status/test_status.",
        "When one P-code groups different root causes or artifact mechanisms, refine the P classification before or alongside the repair.",
        "The loop is incomplete until the full configured project test suite and a full cached raw EN repolish comparison have both passed.",
        "The full cached raw EN repolish comparison means all cached raw files are scanned and every accepted EN article is repolished.",
        "",
        "Return this structure:",
        "1. Critical findings by article.",
        "2. Cross-article patterns.",
        "3. PDF page render and text-layer evidence used, or why either was unavailable.",
        "4. Patch plan with production file/function targets.",
        "5. Tests to add or update, including the focused artifact regression.",
        "6. Risks and gate checks to rerun.",
        "",
        "## Run Summary",
        f"- run_id: `{pack.get('run_id')}`",
        f"- run_dir: `{pack.get('run_dir')}`",
        f"- code_commit: `{pack.get('code_commit')}`",
        f"- raw_count: `{pack.get('raw_count')}`",
        f"- article_count: `{pack.get('article_count')}`",
        f"- skipped_count: `{pack.get('skipped_count')}`",
        f"- language_counts: `{json.dumps(pack.get('language_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- polish_language_counts: `{json.dumps(pack.get('polish_language_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- ignored_defect_ids: `{', '.join(pack.get('ignored_defect_ids') or [])}`",
        f"- comparison_status: `{pack.get('comparison_status')}`",
        f"- regression_count: `{pack.get('regression_count')}`",
        f"- improvement_count: `{pack.get('improvement_count')}`",
        f"- mandatory_changed_review_count: `{pack.get('mandatory_changed_review_count')}`",
        f"- article_review_status: `{(pack.get('article_review_stage') or {}).get('status')}`",
        f"- article_review_index: `{(pack.get('article_review_stage') or {}).get('index_html')}`",
        f"- article_review_pending_mandatory_count: `{(pack.get('article_review_stage') or {}).get('pending_mandatory_count')}`",
        f"- pdf_problem_evidence_status: `{(pack.get('pdf_problem_evidence_stage') or {}).get('status')}`",
        f"- pdf_problem_evidence_dir: `{(pack.get('pdf_problem_evidence_stage') or {}).get('evidence_dir')}`",
        f"- pdf_problem_evidence_blocking_issues: `{(pack.get('pdf_problem_evidence_stage') or {}).get('blocking_issue_count')}`",
        f"- resolver_decisions_path: `{(pack.get('resolver_decisions') or {}).get('path')}`",
        f"- resolver_decision_counts: `{json.dumps((pack.get('resolver_decisions') or {}).get('decision_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- resolver_repair_candidate_counts: `{json.dumps((pack.get('resolver_decisions') or {}).get('repair_candidate_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- resolver_accepted_telemetry_counts: `{json.dumps((pack.get('resolver_decisions') or {}).get('accepted_telemetry_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- p62_marker_recovery_status: `{(pack.get('p62_marker_recovery_plan') or {}).get('status')}`",
        f"- p62_marker_recovery_ready_count: `{(pack.get('p62_marker_recovery_plan') or {}).get('ready_count')}`",
        f"- p62_marker_recovery_unresolved_count: `{(pack.get('p62_marker_recovery_plan') or {}).get('unresolved_count')}`",
        f"- p62_marker_recovery_status_counts: `{json.dumps((pack.get('p62_marker_recovery_plan') or {}).get('status_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- p62_marker_output_status_counts: `{json.dumps((pack.get('p62_marker_recovery_plan') or {}).get('marker_output_status_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- p62_image_recovery_status: `{(pack.get('p62_image_recovery_stage') or {}).get('status')}`",
        f"- p62_image_recovery_asset_ready_count: `{(pack.get('p62_image_recovery_stage') or {}).get('asset_ready_count')}`",
        f"- p62_image_recovery_patched_warning_count: `{(pack.get('p62_image_recovery_stage') or {}).get('patched_warning_count')}`",
        f"- p62_duplicate_visual_repair_count: `{(pack.get('p62_image_recovery_stage') or {}).get('duplicate_visual_repair_count')}`",
        f"- p62_image_recovery_unresolved_count: `{(pack.get('p62_image_recovery_stage') or {}).get('unresolved_count')}`",
        f"- p62_image_recovery_source_counts: `{json.dumps((pack.get('p62_image_recovery_stage') or {}).get('recovery_source_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- p62_source_visual_probe_status_counts: `{json.dumps((pack.get('p62_image_recovery_stage') or {}).get('source_visual_probe_status_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- comparison_totals_delta: `{json.dumps(pack.get('comparison_totals_delta', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- comparison_comparable_totals_delta: `{json.dumps(pack.get('comparison_comparable_totals_delta', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- new_article_count: `{pack.get('new_article_count')}`",
        f"- removed_article_count: `{pack.get('removed_article_count')}`",
        f"- pattern_history_path: `{(pack.get('pattern_observations') or {}).get('history_path')}`",
        f"- pattern_articles_reviewed: `{(pack.get('pattern_observations') or {}).get('article_count_reviewed')}`",
        f"- manual_observation_ledger_path: `{(pack.get('manual_observations') or {}).get('ledger_path')}`",
        f"- manual_observation_ledger_entries: `{(pack.get('manual_observations') or {}).get('ledger_entry_count')}`",
        f"- manual_observation_count: `{(pack.get('manual_observations') or {}).get('observation_count')}`",
        f"- manual_observation_group_count: `{(pack.get('manual_observations') or {}).get('group_count')}`",
    ]
    mandatory_changed_reviews = pack.get("mandatory_changed_review_articles") or []
    if mandatory_changed_reviews:
        lines.extend(
            [
                "",
                "## Mandatory Changed-Article Review",
                "",
                "Articles changed by repolish but absent from improvement/regression buckets must be manually checked before accepting the run.",
            ]
        )
        for item in mandatory_changed_reviews[:12]:
            lines.append(
                f"- {item.get('article')}: score={item.get('score')} | "
                f"defects={json.dumps(item.get('defect_ids', {}), ensure_ascii=False, sort_keys=True)} | "
                f"raw={item.get('raw_stage_path')} | polish={item.get('polish_stage_path')}"
            )
    lines.extend(
        [
            "",
            "## Accumulated Pattern Observations",
            "",
            "Use these grouped observations before judging any article-local symptom.",
        ]
    )
    pattern_observations = pack.get("pattern_observations") or {}
    problem_candidates = pattern_observations.get("problem_candidates") or []
    if problem_candidates:
        lines.append("")
        lines.append("### Problem Candidates")
        for pattern in problem_candidates[:8]:
            lines.append(
                f"- {pattern.get('pattern_key')}: state={pattern.get('problem_state')} | "
                f"runs={pattern.get('run_count')} | article_observations={pattern.get('article_observation_count')} | "
                f"occurrences={pattern.get('occurrence_count')} | defects={json.dumps(pattern.get('defect_ids', {}), ensure_ascii=False, sort_keys=True)}"
            )
    current_patterns = pattern_observations.get("current_patterns") or []
    if current_patterns:
        lines.append("")
        lines.append("### Current Run Pattern Groups")
        for pattern in current_patterns[:8]:
            lines.append(
                f"- {pattern.get('pattern_key')}: articles={pattern.get('article_count')} | "
                f"occurrences={pattern.get('occurrence_count')} | defects={json.dumps(pattern.get('defect_ids', {}), ensure_ascii=False, sort_keys=True)}"
            )
    resolver_decisions = pack.get("resolver_decisions") or {}
    repair_groups = resolver_decisions.get("repair_candidate_groups") or []
    telemetry_groups = resolver_decisions.get("accepted_telemetry_groups") or []
    manual_groups = resolver_decisions.get("manual_or_llm_groups") or []
    if repair_groups or telemetry_groups or manual_groups:
        lines.extend(
            [
                "",
                "## Observed Resolver Decisions",
                "",
                "Use these decisions before proposing repairs: accepted telemetry needs guard coverage, repair candidates need source-backed automation, and manual/LLM items need evidence packs.",
            ]
        )
        if repair_groups:
            lines.append("")
            lines.append("### Repair Candidates")
            for group in repair_groups[:8]:
                lines.append(
                    f"- {group.get('defect_id')} {group.get('decision')}: count={group.get('count')} | "
                    f"articles={group.get('article_count')} | fix_layer={group.get('fix_layer')}"
                )
        if telemetry_groups:
            lines.append("")
            lines.append("### Accepted Telemetry")
            for group in telemetry_groups[:8]:
                lines.append(
                    f"- {group.get('defect_id')}: count={group.get('count')} | "
                    f"articles={group.get('article_count')} | fix_layer={group.get('fix_layer')}"
                )
        if manual_groups:
            lines.append("")
            lines.append("### Manual Or Evidence-Bound LLM")
            for group in manual_groups[:8]:
                lines.append(
                    f"- {group.get('defect_id')}: count={group.get('count')} | "
                    f"articles={group.get('article_count')} | fix_layer={group.get('fix_layer')}"
                )
    p62_plan = pack.get("p62_marker_recovery_plan") or {}
    p62_samples = p62_plan.get("ready_samples") or []
    if p62_plan.get("candidate_count") or p62_samples:
        lines.extend(
            [
                "",
                "## P62 Marker Recovery Plan",
                "",
                "These are dry-run marker_single commands for page-scoped figure recovery. Marker page_range values are zero-based; source_pdf_page_number is one-based.",
                f"- status: `{p62_plan.get('status')}`",
                f"- path: `{p62_plan.get('path')}`",
                f"- output_root: `{p62_plan.get('output_root')}`",
                f"- candidate_count: `{p62_plan.get('candidate_count')}`",
                f"- ready_count: `{p62_plan.get('ready_count')}`",
                f"- unresolved_count: `{p62_plan.get('unresolved_count')}`",
                f"- marker_output_status_counts: `{json.dumps(p62_plan.get('marker_output_status_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
            ]
        )
        for sample in p62_samples[:5]:
            lines.append(
                f"- {sample.get('article')} fig={sample.get('figure_label')} "
                f"pdf_page={sample.get('source_pdf_page_number')} "
                f"marker_page_range={sample.get('marker_page_range')} "
                f"score={sample.get('match_score')} | command={json.dumps(sample.get('marker_command') or [], ensure_ascii=False)}"
            )
    p62_recovery = pack.get("p62_image_recovery_stage") or {}
    if p62_recovery.get("candidate_count") or p62_recovery.get("asset_ready_count"):
        lines.extend(
            [
                "",
                "## P62 Image Recovery Stage",
                "",
                "This stage executes marker when configured, then falls back to a source-PDF page render so P62 visuals remain automatically recoverable.",
                f"- status: `{p62_recovery.get('status')}`",
                f"- path: `{p62_recovery.get('path')}`",
                f"- output_root: `{p62_recovery.get('output_root')}`",
                f"- candidate_count: `{p62_recovery.get('candidate_count')}`",
                f"- asset_ready_count: `{p62_recovery.get('asset_ready_count')}`",
                f"- patched_warning_count: `{p62_recovery.get('patched_warning_count')}`",
                f"- duplicate_visual_repair_count: `{p62_recovery.get('duplicate_visual_repair_count')}`",
                f"- patch_missed_count: `{p62_recovery.get('patch_missed_count')}`",
                f"- unresolved_count: `{p62_recovery.get('unresolved_count')}`",
                f"- recovery_source_counts: `{json.dumps(p62_recovery.get('recovery_source_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- source_visual_probe_status_counts: `{json.dumps(p62_recovery.get('source_visual_probe_status_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- probe_marker_for_unavailable: `{p62_recovery.get('probe_marker_for_unavailable')}`",
            ]
        )
    manual_observations = pack.get("manual_observations") or {}
    lines.extend(
        [
            "",
            "## Manual Observation Ledger",
            "",
            "Use this append-only ledger for newly spotted manifestations before promoting them into audit patterns or repairs.",
        ]
    )
    manual_problem_candidates = manual_observations.get("problem_candidates") or []
    if manual_problem_candidates:
        lines.append("")
        lines.append("### Manual Problem Candidates")
        for group in manual_problem_candidates[:8]:
            lines.append(
                f"- {group.get('normalized_signature')}: state={group.get('problem_state')} | "
                f"runs={group.get('run_count')} | articles={group.get('article_count')} | "
                f"occurrences={group.get('occurrence_count')} | statuses={json.dumps(group.get('statuses', {}), ensure_ascii=False, sort_keys=True)}"
            )
    requires_triage = manual_observations.get("requires_triage") or []
    if requires_triage:
        lines.append("")
        lines.append("### Manual Observations Requiring Triage")
        for group in requires_triage[:8]:
            sample = (group.get("sample_observations") or [{}])[0]
            lines.append(
                f"- {group.get('normalized_signature')}: articles={group.get('article_count')} | "
                f"sample_article={sample.get('article')} | snippet={sample.get('snippet')}"
            )
    lines.extend(["", "## Articles"])
    for article in pack.get("articles", []):
        title = str(article.get("article") or "")
        source_article = article.get("source_article")
        if source_article and source_article != title:
            title = f"{title} ({source_article})"
        lines.extend(
            [
                "",
                f"### {title}",
                f"- score: `{article.get('score')}`",
                f"- non_ignored_defect_count: `{article.get('non_ignored_defect_count')}`",
                f"- resolver_repair_candidate_count: `{article.get('resolver_repair_candidate_count')}`",
                f"- accepted_telemetry_count: `{article.get('accepted_telemetry_count')}`",
                f"- selection_reasons: `{', '.join(article.get('selection_reasons') or [])}`",
                f"- defect_ids: `{json.dumps(article.get('defect_ids', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- comparison: `{json.dumps(article.get('comparison', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- metrics: `{json.dumps(article.get('metrics', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- artifact_hint: `{article.get('artifact_hint')}`",
                f"- raw_stage_path: `{article.get('raw_stage_path')}`",
                f"- polish_stage_path: `{article.get('polish_stage_path')}`",
                f"- source_pdf_path: `{(article.get('audit_summary') or {}).get('source_pdf_path')}`",
                f"- source_pdf_present: `{(article.get('audit_summary') or {}).get('source_pdf_present')}`",
                f"- source_pdf_origin: `{(article.get('audit_summary') or {}).get('source_pdf_origin')}`",
                f"- source_pdf_candidates: `{json.dumps(article.get('source_pdf_candidates') or [], ensure_ascii=False)}`",
                f"- pdf_problem_evidence: `{json.dumps(article.get('pdf_problem_evidence') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- resolver_decisions: `{json.dumps(article.get('resolver_decisions') or [], ensure_ascii=False, sort_keys=True)}`",
                "- defect snippets:",
            ]
        )
        for defect in article.get("defects", [])[:8]:
            snippet = str(defect.get("snippet") or "").replace("\n", " ")
            lines.append(
                f"  - {defect.get('id')} {defect.get('severity')}: {defect.get('check')} | "
                f"pattern={defect.get('known_pattern')} | snippet={snippet}"
            )
    lines.append("")
    return "\n".join(lines)


def write_analysis_pack(
    run_dir: Path,
    *,
    out_json: Path | None = None,
    out_prompt: Path | None = None,
    max_articles: int = 12,
    gate_config_path: Path = DEFAULT_GATE_CONFIG,
    defect_patterns_path: Path = DEFAULT_DEFECT_PATTERNS,
    ignored_defect_ids: set[str] | None = None,
    manual_observation_ledger: Path | None = None,
) -> dict[str, Any]:
    gate_config = load_gate_config(gate_config_path)
    defect_patterns = _load_json(defect_patterns_path, default={})
    write_manual_observation_summary(run_dir, ledger_path=manual_observation_ledger)
    write_resolver_decisions(run_dir)
    if gate_config.get("require_p62_marker_recovery_plan", True):
        write_p62_marker_recovery_plan(run_dir, gate_config=gate_config)
    pack = build_analysis_pack(
        run_dir,
        max_articles=max_articles,
        gate_config=gate_config,
        defect_patterns=defect_patterns,
        ignored_defect_ids=ignored_defect_ids,
    )
    if gate_config.get("require_pdf_problem_evidence_stage", False):
        evidence_report = write_pdf_problem_evidence_stage(run_dir, pack, gate_config=gate_config)
        _attach_pdf_evidence_to_pack(pack, evidence_report)
    out_json = out_json or (run_dir / "llm_analysis_pack.json")
    out_prompt = out_prompt or (run_dir / "llm_analysis_prompt.md")
    _write_json(out_json, pack)
    out_prompt.parent.mkdir(parents=True, exist_ok=True)
    out_prompt.write_text(render_llm_prompt(pack), encoding="utf-8")
    return pack


def run_audit(
    run_dir: Path,
    roots: Iterable[Path] | None = None,
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_map_path: Path | None = None,
) -> None:
    quality_commands.run_audit(
        run_dir,
        roots=roots,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_path=pdf_map_path,
        repo_root=ROOT,
    )


def run_quality_history(run_dir: Path, *, run_id: str | None, previous_entry: Path | None, no_append: bool) -> None:
    quality_commands.run_quality_history(
        run_dir,
        run_id=run_id,
        previous_entry=previous_entry,
        no_append=no_append,
        repo_root=ROOT,
    )


def run_test_command(command: str, run_dir: Path) -> dict[str, Any]:
    return quality_commands.run_test_command(command, run_dir, cwd=ROOT)


def _write_gate_report(run_dir: Path, gate_config_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    return quality_commands.write_gate_report(
        run_dir,
        gate_config_path,
        out_path=out_path,
        pdf_problem_evidence_name=DEFAULT_PDF_PROBLEM_EVIDENCE_NAME,
    )


def observe(args: argparse.Namespace) -> int:
    run_dir = args.out_dir.resolve(strict=False)
    converted_roots = list(args.converted_roots or [])
    if args.source_run_dir and converted_roots:
        raise SystemExit("Use either --source-run-dir or --converted-roots, not both.")
    if args.source_run_dir:
        manifest = repolish_cached_run(
            args.source_run_dir,
            run_dir,
            polish_language=args.polish_language,
            target_language=args.target_language,
            skip_non_target_language=args.skip_non_target_language,
            skip_unknown_language=args.skip_unknown_language,
        )
        print(
            "Repolished cached run: "
            f"raw={manifest['raw_count']} "
            f"articles={manifest['article_count']} "
            f"skipped={manifest['skipped_count']} "
            f"changed={manifest['changed_count']}"
        )
    elif converted_roots:
        if args.repolish_converted_raw:
            source_cache_dir = run_dir / "_converted_raw_source"
            source_manifest = prepare_converted_raw_cache(converted_roots, source_cache_dir)
            manifest = repolish_cached_run(
                source_cache_dir,
                run_dir,
                polish_language=args.polish_language,
                target_language=args.target_language,
                skip_non_target_language=args.skip_non_target_language,
                skip_unknown_language=args.skip_unknown_language,
            )
            print(
                "Repolished converted raw stages: "
                f"raw={source_manifest['raw_count']} "
                f"articles={manifest['article_count']} "
                f"skipped={manifest['skipped_count']} "
                f"changed={manifest['changed_count']}"
            )
        else:
            manifest = prepare_converted_run(converted_roots, run_dir)
            print(f"Prepared converted stage run: articles={manifest['article_count']}")
    gate_config = load_gate_config(args.gate_config)
    if args.run_tests:
        run_test_command(args.test_command or gate_config.get("required_test_command") or "python -m pytest -q", run_dir)
    if not args.skip_audit:
        audit_existing_converted = bool(converted_roots and not args.repolish_converted_raw)
        pdf_map_path: Path | None = None
        if gate_config.get("require_pdf_text_layer_diagnostics", False):
            pdf_map_report = write_source_pdf_map_for_run(run_dir, manifest)
            if int(pdf_map_report.get("mapped_count") or 0) > 0:
                pdf_map_path = run_dir / DEFAULT_SOURCE_PDF_MAP_NAME
        run_audit(
            run_dir,
            roots=converted_roots if audit_existing_converted else None,
            enable_pdf_diagnostics=bool(gate_config.get("require_pdf_text_layer_diagnostics", False)),
            pdf_map_path=pdf_map_path,
        )
        if audit_existing_converted:
            normalize_converted_audit_article_ids(run_dir)
        run_p62_recovery = (
            bool(gate_config.get("run_p62_image_recovery_stage", False))
            and not args.skip_p62_recovery
            and not audit_existing_converted
        )
        if run_p62_recovery:
            write_p62_marker_recovery_plan(run_dir, gate_config=gate_config)
            recovery_report = write_p62_image_recovery_stage(
                run_dir,
                gate_config=gate_config,
                execute_marker=bool(gate_config.get("p62_image_recovery_execute_marker", True)),
                apply_patches=bool(gate_config.get("p62_image_recovery_apply_patches", True)),
                max_items=args.p62_recovery_max_items,
            )
            if int(recovery_report.get("patched_warning_count") or 0) > 0 and bool(
                gate_config.get("p62_image_recovery_rerun_audit", True)
            ):
                run_audit(
                    run_dir,
                    enable_pdf_diagnostics=bool(gate_config.get("require_pdf_text_layer_diagnostics", False)),
                    pdf_map_path=pdf_map_path,
                )
        run_polish_auto_repair = (
            bool(gate_config.get("run_polish_auto_repair_stage", True))
            and not audit_existing_converted
        )
        if run_polish_auto_repair:
            auto_repair_report = write_polish_auto_repair_stage(run_dir, gate_config=gate_config)
            if int(auto_repair_report.get("patched_article_count") or 0) > 0 and bool(
                gate_config.get("polish_auto_repair_rerun_audit", True)
            ):
                run_audit(
                    run_dir,
                    enable_pdf_diagnostics=bool(gate_config.get("require_pdf_text_layer_diagnostics", False)),
                    pdf_map_path=pdf_map_path,
                )
    if not args.skip_history:
        run_quality_history(
            run_dir,
            run_id=args.run_id,
            previous_entry=args.previous_entry,
            no_append=args.no_append_history,
        )
    review_queue = write_manual_review_queue(
        run_dir,
        gate_config_path=args.gate_config,
        ignored_defect_ids=set(args.ignore_defect_id or []),
    )
    review_bundle_limit = (
        args.max_review_articles
        if args.max_review_articles is not None
        else gate_config.get("article_review_bundle_max_articles")
    )
    article_review_report = write_article_review_stage(
        run_dir,
        review_queue,
        max_articles=review_bundle_limit,
    )
    pattern_observations = write_pattern_observations(
        run_dir,
        defect_patterns_path=args.defect_patterns,
        history_path=args.pattern_history,
    )
    manual_observations = write_manual_observation_summary(
        run_dir,
        ledger_path=args.manual_observation_ledger,
    )
    pack = write_analysis_pack(
        run_dir,
        max_articles=args.max_articles,
        gate_config_path=args.gate_config,
        defect_patterns_path=args.defect_patterns,
        ignored_defect_ids=set(args.ignore_defect_id or []),
        manual_observation_ledger=args.manual_observation_ledger,
    )
    gate_report = _write_gate_report(run_dir, args.gate_config)
    print(
        "LLM quality loop: "
        f"gate={gate_report['status']} review_queue={len(review_queue)} "
        f"article_review={article_review_report['status']} "
        f"mandatory_pending={article_review_report['pending_mandatory_count']} "
        f"patterns={pattern_observations['pattern_count']} "
        f"problem_candidates={len(pattern_observations['problem_candidates'])} "
        f"manual_observations={manual_observations['observation_count']} "
        f"manual_problem_candidates={len(manual_observations['problem_candidates'])} "
        f"resolver_repairs={sum((pack.get('resolver_decisions') or {}).get('repair_candidate_counts', {}).values())} "
        f"articles_in_pack={len(pack['articles'])} run_dir={run_dir}"
    )
    return 1 if gate_report["status"] == "fail" and args.fail_on_gate else 0


def run_llm_command(prompt_path: Path, out_path: Path, command: list[str]) -> int:
    if not command:
        raise SystemExit("Pass the LLM command after --, for example: run-llm --prompt prompt.md --out out.md -- codex ...")
    prompt = prompt_path.read_text(encoding="utf-8")
    result = subprocess.run(command, input=prompt, text=True, capture_output=True, cwd=ROOT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.stdout, encoding="utf-8")
    if result.stderr:
        (out_path.with_suffix(out_path.suffix + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
    return result.returncode


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    observe_parser = subparsers.add_parser("observe", help="Run repolish/audit/history/gate and build an LLM pack.")
    observe_parser.add_argument("--source-run-dir", type=Path, help="Run dir with raw_cache and profiles to repolish.")
    observe_parser.add_argument(
        "--polish-language",
        choices=("en", "ru", "auto"),
        default="auto",
        help="Language policy for language-specific polish repairs when repolishing a cached run.",
    )
    observe_parser.add_argument(
        "--target-language",
        default="en",
        help="Corpus language to keep for cached-run repolish; defaults to EN for this loop.",
    )
    language_filter_group = observe_parser.add_mutually_exclusive_group()
    language_filter_group.add_argument(
        "--skip-non-target-language",
        dest="skip_non_target_language",
        action="store_true",
        help="Skip confidently detected non-target documents from cached-run audit/statistics.",
    )
    language_filter_group.add_argument(
        "--include-non-target-language",
        dest="skip_non_target_language",
        action="store_false",
        help="Keep non-target documents in cached-run audit/statistics.",
    )
    observe_parser.set_defaults(skip_non_target_language=True)
    observe_parser.add_argument(
        "--skip-unknown-language",
        action="store_true",
        help="Skip documents whose language cannot be detected confidently.",
    )
    observe_parser.add_argument(
        "--converted-roots",
        nargs="+",
        type=Path,
        help="Production converted roots or direct _z2m_stages files to audit without repolishing.",
    )
    observe_parser.add_argument(
        "--repolish-converted-raw",
        action="store_true",
        help=(
            "With --converted-roots, copy production 01.en.raw.html stages into an internal "
            "raw_cache and run the normal EN repolish loop without writing back to converted roots."
        ),
    )
    observe_parser.add_argument("--out-dir", type=Path, required=True)
    observe_parser.add_argument("--run-id")
    observe_parser.add_argument("--previous-entry", type=Path)
    observe_parser.add_argument("--gate-config", type=Path, default=DEFAULT_GATE_CONFIG)
    observe_parser.add_argument("--defect-patterns", type=Path, default=DEFAULT_DEFECT_PATTERNS)
    observe_parser.add_argument(
        "--pattern-history",
        type=Path,
        help=f"Append-only JSONL history for accumulated pattern observations. Defaults to out-dir parent/{DEFAULT_PATTERN_HISTORY_NAME}.",
    )
    observe_parser.add_argument(
        "--manual-observation-ledger",
        type=Path,
        help=(
            "Append-only JSONL ledger for manually spotted manifestations. "
            f"Defaults to out-dir parent/{DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME}."
        ),
    )
    observe_parser.add_argument("--ignore-defect-id", action="append")
    observe_parser.add_argument("--max-articles", type=int, default=12)
    observe_parser.add_argument(
        "--max-review-articles",
        type=int,
        help=(
            "Maximum mandatory changed articles to copy into article_review/index.html. "
            "Zero or omission means all mandatory changed articles unless gate config sets a positive limit."
        ),
    )
    test_group = observe_parser.add_mutually_exclusive_group()
    test_group.add_argument(
        "--run-tests",
        dest="run_tests",
        action="store_true",
        help="Run the configured test command before audit/history/gates. This is the default for the loop.",
    )
    test_group.add_argument(
        "--skip-tests",
        dest="run_tests",
        action="store_false",
        help="Skip the configured test command; use only for exploratory audit runs, not for code patches.",
    )
    observe_parser.set_defaults(run_tests=True)
    observe_parser.add_argument("--test-command")
    observe_parser.add_argument("--skip-audit", action="store_true")
    observe_parser.add_argument(
        "--skip-p62-recovery",
        action="store_true",
        help="Skip the configured P62 marker/render recovery stage after audit.",
    )
    observe_parser.add_argument(
        "--p62-recovery-max-items",
        type=int,
        help="Limit P62 image recovery records for this observe run; omitted or zero means all.",
    )
    observe_parser.add_argument("--skip-history", action="store_true")
    observe_parser.add_argument("--no-append-history", action="store_true")
    observe_parser.add_argument("--fail-on-gate", action="store_true")

    gate_parser = subparsers.add_parser("gate", help="Evaluate quality_compare.json against configured gates.")
    gate_parser.add_argument("--run-dir", type=Path, required=True)
    gate_parser.add_argument("--gate-config", type=Path, default=DEFAULT_GATE_CONFIG)
    gate_parser.add_argument("--out", type=Path)
    gate_parser.add_argument("--fail-on-gate", action="store_true")

    pack_parser = subparsers.add_parser("pack", help="Build llm_analysis_pack.json and llm_analysis_prompt.md.")
    pack_parser.add_argument("--run-dir", type=Path, required=True)
    pack_parser.add_argument("--out-json", type=Path)
    pack_parser.add_argument("--out-prompt", type=Path)
    pack_parser.add_argument("--gate-config", type=Path, default=DEFAULT_GATE_CONFIG)
    pack_parser.add_argument("--defect-patterns", type=Path, default=DEFAULT_DEFECT_PATTERNS)
    pack_parser.add_argument("--manual-observation-ledger", type=Path)
    pack_parser.add_argument("--ignore-defect-id", action="append")
    pack_parser.add_argument("--max-articles", type=int, default=12)

    recover_parser = subparsers.add_parser(
        "recover-p62",
        help="Execute marker/render recovery for P62 missing-figure warnings in an existing run dir.",
    )
    recover_parser.add_argument("--run-dir", type=Path, required=True)
    recover_parser.add_argument("--gate-config", type=Path, default=DEFAULT_GATE_CONFIG)
    recover_parser.add_argument("--plan", type=Path)
    recover_parser.add_argument("--out", type=Path)
    recover_parser.add_argument("--max-items", type=int)
    marker_mode = recover_parser.add_mutually_exclusive_group()
    marker_mode.add_argument(
        "--run-marker",
        dest="execute_marker",
        action="store_true",
        help="Execute marker before source-PDF page render fallback.",
    )
    marker_mode.add_argument(
        "--skip-marker",
        dest="execute_marker",
        action="store_false",
        help="Do not execute marker; go straight to source-PDF page render fallback.",
    )
    recover_parser.set_defaults(execute_marker=None)
    recover_parser.add_argument(
        "--no-apply",
        dest="apply_patches",
        action="store_false",
        help="Create recovery assets and report without patching HTML.",
    )
    recover_parser.set_defaults(apply_patches=True)
    recover_parser.add_argument(
        "--rerun-audit",
        action="store_true",
        help="Rerun audit after HTML patches so audit_full_checks reflects the recovery.",
    )

    record_parser = subparsers.add_parser(
        "record-observation",
        help="Append one manually spotted manifestation to the manual observation ledger.",
    )
    record_parser.add_argument("--ledger", type=Path, required=True)
    record_parser.add_argument("--run-dir", type=Path)
    record_parser.add_argument("--run-id")
    record_parser.add_argument("--observation-id")
    record_parser.add_argument("--article", required=True)
    record_parser.add_argument("--stage-path", type=Path)
    record_parser.add_argument("--defect-id")
    record_parser.add_argument("--snippet", required=True)
    record_parser.add_argument("--html-fragment")
    record_parser.add_argument("--visible-text")
    record_parser.add_argument("--suspected-pattern")
    record_parser.add_argument(
        "--status",
        choices=(
            "untriaged",
            "confirmed",
            "false_positive",
            "promoted_to_audit",
            "promoted_to_repair",
            "covered_by_test",
            "ignored",
        ),
        default="untriaged",
    )
    record_parser.add_argument(
        "--test-status",
        choices=("none", "audit", "repair", "false_positive", "guard"),
        default="none",
    )
    record_parser.add_argument("--notes", default="")
    record_parser.add_argument("--source", default="manual_review")

    llm_parser = subparsers.add_parser("run-llm", help="Send a generated prompt to an explicit external LLM command.")
    llm_parser.add_argument("--prompt", type=Path, required=True)
    llm_parser.add_argument("--out", type=Path, required=True)
    llm_parser.add_argument("llm_command", nargs=argparse.REMAINDER)

    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "observe":
        return observe(args)
    if args.command == "gate":
        report = _write_gate_report(args.run_dir, args.gate_config, args.out)
        print(f"Quality gate: {report['status']} failures={len(report['failures'])}")
        return 1 if report["status"] == "fail" and args.fail_on_gate else 0
    if args.command == "pack":
        pack = write_analysis_pack(
            args.run_dir,
            out_json=args.out_json,
            out_prompt=args.out_prompt,
            max_articles=args.max_articles,
            gate_config_path=args.gate_config,
            defect_patterns_path=args.defect_patterns,
            ignored_defect_ids=set(args.ignore_defect_id or []),
            manual_observation_ledger=args.manual_observation_ledger,
        )
        print(f"LLM analysis pack: articles={len(pack['articles'])} run_dir={args.run_dir}")
        return 0
    if args.command == "recover-p62":
        gate_config = load_gate_config(args.gate_config)
        if args.plan is None or not args.plan.is_file():
            write_p62_marker_recovery_plan(args.run_dir, gate_config=gate_config, out_path=args.plan)
        report = write_p62_image_recovery_stage(
            args.run_dir,
            gate_config=gate_config,
            plan_path=args.plan,
            out_path=args.out,
            execute_marker=args.execute_marker,
            apply_patches=args.apply_patches,
            max_items=args.max_items,
        )
        if args.rerun_audit and int(report.get("patched_warning_count") or 0) > 0:
            pdf_map_path = args.run_dir / DEFAULT_SOURCE_PDF_MAP_NAME
            run_audit(
                args.run_dir,
                enable_pdf_diagnostics=bool(gate_config.get("require_pdf_text_layer_diagnostics", False)),
                pdf_map_path=pdf_map_path if pdf_map_path.is_file() else None,
            )
        print(
            "P62 image recovery: "
            f"status={report['status']} "
            f"asset_ready={report['asset_ready_count']} "
            f"patched={report['patched_warning_count']} "
            f"unresolved={report['unresolved_count']} "
            f"run_dir={args.run_dir}"
        )
        return 0
    if args.command == "record-observation":
        run_id = args.run_id
        if not run_id and args.run_dir:
            entry = _load_json(args.run_dir / "quality_history_entry.json", default={})
            run_id = str(entry.get("run_id") or args.run_dir.name)
        record = record_manual_observation(
            args.ledger,
            {
                "run_id": run_id or "",
                "observation_id": args.observation_id,
                "article": args.article,
                "stage_path": args.stage_path,
                "defect_id": args.defect_id,
                "snippet": args.snippet,
                "html_fragment": args.html_fragment,
                "visible_text": args.visible_text,
                "suspected_pattern": args.suspected_pattern,
                "status": args.status,
                "test_status": args.test_status,
                "notes": args.notes,
                "source": args.source,
            },
        )
        message = f"Manual observation recorded: {record['observation_id']} ledger={args.ledger}"
        if args.run_dir:
            summary = write_manual_observation_summary(args.run_dir, ledger_path=args.ledger)
            message += f" groups={summary['group_count']} problem_candidates={len(summary['problem_candidates'])}"
        print(message)
        return 0
    if args.command == "run-llm":
        command = list(args.llm_command)
        if command and command[0] == "--":
            command = command[1:]
        return run_llm_command(args.prompt, args.out, command)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
