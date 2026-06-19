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
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.single_file_html import (  # noqa: E402
    close_katex_v8_context,
    polish_html_document,
)
from pdf_html_polish.citation_profile import extract_reference_entries_from_pdf  # noqa: E402
from pdf_html_polish.marker_runner import build_marker_single_command  # noqa: E402
from pdf_html_polish.polish_language import resolve_document_polish_language  # noqa: E402
from pdf_html_polish.quality_loop import commands as quality_commands  # noqa: E402
from pdf_html_polish.quality_loop.analysis_prompt import render_llm_prompt as _render_llm_prompt_impl  # noqa: E402
from pdf_html_polish.quality_loop.cached_images import (  # noqa: E402
    apply_data_image_cache as _apply_data_image_cache,
    cached_data_image_cache as _cached_data_image_cache,
    copy_review_html_with_inline_images as _copy_review_html_with_inline_images,
    manifest_article_for as _manifest_article_for,
)
from pdf_html_polish.quality_loop.converted_runs import (  # noqa: E402
    POLISH_STAGE,
    RAW_STAGE,
    assessment_totals as _assessment_totals,
    assess_polish_html,
    find_converted_stage_pairs,
    prepare_converted_raw_cache,
    prepare_converted_run,
    visible_html_text as _visible_html_text,
)
from pdf_html_polish.quality_loop import gates as quality_gates  # noqa: E402
from pdf_html_polish.quality_loop import pdf_utils as quality_pdf_utils  # noqa: E402
from pdf_html_polish.quality_loop import source_pdf as quality_source_pdf  # noqa: E402
from pdf_html_polish.quality_loop.observations import (  # noqa: E402
    compact_observation_text as _compact_observation_text,
    manual_observation_signature,
    record_manual_observation,
    write_manual_observation_summary as _write_manual_observation_summary,
)
from pdf_html_polish.quality_loop.pattern_observations import (  # noqa: E402
    write_pattern_observations as _write_pattern_observations,
)
from pdf_html_polish.quality_loop.pdf_evidence import (  # noqa: E402
    attach_pdf_evidence_to_pack as _attach_pdf_evidence_to_pack_impl,
    problem_snippets_for_evidence as _problem_snippets_for_evidence_impl,
    write_pdf_problem_evidence_stage as _write_pdf_problem_evidence_stage_impl,
)
from pdf_html_polish.quality_loop.pdf_reference_recovery import (  # noqa: E402
    enrich_profile_with_pdf_reference_entries_if_needed as _enrich_profile_with_pdf_reference_entries_if_needed_impl,
    expand_reference_candidate_numbers as _expand_reference_candidate_numbers_impl,
    pdf_reference_recovery_numbers as _pdf_reference_recovery_numbers_impl,
    plain_reference_candidate_is_safe as _plain_reference_candidate_is_safe_impl,
    profile_has_reference_entries as _profile_has_reference_entries_impl,
    reference_entry_record as _reference_entry_record_impl,
    reference_id_gap_numbers as _reference_id_gap_numbers_impl,
    reference_id_numbers as _reference_id_numbers_impl,
    reference_recovery_block_is_protected as _reference_recovery_block_is_protected_impl,
    unlinked_body_reference_candidate_numbers as _unlinked_body_reference_candidate_numbers_impl,
)
from pdf_html_polish.quality_loop.polish_auto_repair import (  # noqa: E402
    assessment_articles_by_broken_internal_links as _assessment_articles_by_broken_internal_links_impl,
    audit_articles_by_auto_repair_need as _audit_articles_by_auto_repair_need_impl,
    audit_defect_ids as _audit_defect_ids_impl,
    relink_external_numeric_citation_anchors as _relink_external_numeric_citation_anchors_impl,
    relink_spaced_multipanel_figure_refs as _relink_spaced_multipanel_figure_refs_impl,
    repair_second_echelon_ocr_residue as _repair_second_echelon_ocr_residue_impl,
    repair_visible_reference_numbers as _repair_visible_reference_numbers_impl,
    unwrap_broken_internal_links as _unwrap_broken_internal_links_impl,
    unwrap_author_year_numeric_ref_links as _unwrap_author_year_numeric_ref_links_impl,
    unwrap_author_year_ref_anchors as _unwrap_author_year_ref_anchors_impl,
    visible_ref_prefix_number as _visible_ref_prefix_number_impl,
)
from pdf_html_polish.quality_loop.resolver_decisions import (  # noqa: E402
    ARTICLE_SLOT_REPAIR_DECISION_NAMES,
    defect_extra as _defect_extra,
    write_resolver_decisions as _write_resolver_decisions,
)
from pdf_html_polish.quality_loop.review_workflow import (  # noqa: E402
    defect_id_counts as _defect_id_counts_impl,
    existing_queue_items as _existing_queue_items_impl,
    relative_review_href as _relative_review_href_impl,
    review_state_by_key as _review_state_by_key_impl,
    severity_counts as _severity_counts_impl,
    stage_path_for_review as _stage_path_for_review_impl,
    write_article_review_stage as _write_article_review_stage_impl,
    write_manual_review_queue as _write_manual_review_queue_impl,
)
from pdf_html_polish.quality_loop.run_utils import (  # noqa: E402
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
from pdf_html_polish.quality_loop.p62_duplicates import (  # noqa: E402
    apply_duplicate_figure_image_repairs as _apply_p62_duplicate_figure_image_repairs_impl,
    repair_duplicate_figure_images as _repair_p62_duplicate_figure_images_impl,
)
from pdf_html_polish.quality_loop.p62_html import (  # noqa: E402
    clean_resolved_missing_unit_classes as _clean_resolved_p62_missing_unit_classes,
    data_url_duplicates_existing_figure_unit as _p62_data_url_duplicates_existing_figure_unit,
    data_url_image_hash as _p62_data_url_image_hash,
    extract_html_figure_units as _p62_extract_html_figure_units,
    figure_label_from_unit_id as _p62_figure_label_from_unit_id,
    html_has_missing_warning_for_label as _html_has_p62_missing_warning_for_label,
    html_has_missing_warning_for_figure_unit as _html_has_p62_missing_warning_for_figure_unit,
    html_has_recovery_for_label as _html_has_p62_recovery_for_label,
    html_has_stale_page_render_for_label as _html_has_p62_stale_page_render_for_label,
    id_matches_figure_label as _p62_id_matches_figure_label,
    insert_recovered_figure_unit_for_visible_reference as _insert_p62_recovered_figure_unit_for_visible_reference,
    missing_warning_target_html as _p62_missing_warning_target_html,
    move_p61_recovered_units_after_sentence_continuation as _move_p61_recovered_units_after_sentence_continuation,
    recovered_target_matches_label as _p62_recovered_target_matches_label,
    recovered_target_source as _p62_recovered_target_source,
    recovery_target_html as _p62_recovery_target_html,
    replace_figure_unit_target_with_image as _replace_p62_figure_unit_target_with_image,
    replace_figure_unit_target_with_missing_warning as _replace_p62_figure_unit_target_with_missing_warning,
    replace_missing_warning_with_image as _replace_p62_missing_warning_with_image,
    replace_recovery_with_missing_warning as _replace_p62_recovery_with_missing_warning,
    replace_stale_recovery_with_image as _replace_p62_stale_recovery_with_image,
)
from pdf_html_polish.quality_loop.p62_marker import (  # noqa: E402
    execute_marker_command as _execute_p62_marker_command_impl,
    validate_marker_output as _validate_p62_marker_output_impl,
)
from pdf_html_polish.quality_loop.p62_plan import (  # noqa: E402
    P62MarkerRecoveryPlanDependencies,
    write_marker_recovery_plan as _write_p62_marker_recovery_plan_impl,
)
from pdf_html_polish.quality_loop.p62_recovery_stage import (  # noqa: E402
    apply_html_patch_to_targets as _apply_p62_html_patch_to_targets,
    build_p62_image_recovery_report as _build_p62_image_recovery_report,
    P62PatchTargetDependencies,
    patch_targets_for_record as _p62_patch_targets_for_record_impl,
    recover_pdf_figure_asset_for_stage as _recover_p62_pdf_figure_asset_for_stage,
    resolve_p62_image_recovery_stage_config as _resolve_p62_image_recovery_stage_config,
)
from pdf_html_polish.quality_loop.p62_pdf_assets import (  # noqa: E402
    external_pdf_tool_inventory as _p62_external_pdf_tool_inventory_impl,
    false_match_hint_blocks_asset_recovery as _p62_false_match_hint_blocks_asset_recovery_impl,
    page_caption_label_rects as _p62_page_caption_label_rects_impl,
    page_label_rects as _p62_page_label_rects_impl,
    pdf_page_caption_label_found as _p62_pdf_page_caption_label_found_impl,
    pdf_page_false_match_hint as _p62_pdf_page_false_match_hint_impl,
    pdf_visual_inventory as _p62_pdf_visual_inventory_impl,
    pypdf_image_inventory as _p62_pypdf_image_inventory_impl,
    recover_detached_pdf_figure_plate_asset as _recover_p62_detached_pdf_figure_plate_asset_impl,
    recover_pdf_figure_asset as _recover_p62_pdf_figure_asset_impl,
    render_fallback_page_number as _p62_render_fallback_page_number_impl,
)
from pdf_html_polish.quality_loop.p62_matching import (  # noqa: E402
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
from pdf_html_polish.quality_loop.p62_context import (  # noqa: E402
    P62_MISSING_WARNING_TEXT_RE,
    clean_context_fragment as _clean_p62_context_fragment_impl,
    context_fragment as _p62_context_fragment_impl,
    recovery_snippets as _p62_recovery_snippets_impl,
    warning_context_from_html as _p62_warning_context_from_html_impl,
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

P62_LOW_FIDELITY_RECOVERY_SOURCES = {"pdf_page_render"}
P62_PDF_DERIVED_RECOVERY_SOURCES = {
    "pdf_page_render",
    "pdf_figure_region_render",
    "pdf_native_image",
    "pdf_detached_plate_region_render",
}


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
    return _problem_snippets_for_evidence_impl(article)


def _attach_pdf_evidence_to_pack(pack: dict[str, Any], evidence_report: dict[str, Any]) -> dict[str, Any]:
    return _attach_pdf_evidence_to_pack_impl(pack, evidence_report)


def write_pdf_problem_evidence_stage(
    run_dir: Path,
    pack: dict[str, Any],
    *,
    gate_config: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    return _write_pdf_problem_evidence_stage_impl(
        run_dir,
        pack,
        gate_config=gate_config or load_gate_config(),
        out_path=out_path,
        output_name=DEFAULT_PDF_PROBLEM_EVIDENCE_NAME,
        pdf_text_pages=_pdf_text_pages,
        render_pdf_evidence_page=_render_pdf_evidence_page,
    )


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
    return _clean_p62_context_fragment_impl(fragment, max_len=max_len)


def _p62_context_fragment(html: str, position: int, *, radius: int) -> str:
    return _p62_context_fragment_impl(html, position, radius=radius)


def _p62_warning_context_from_html(
    html: str,
    defect: dict[str, Any],
    *,
    radius: int,
) -> tuple[str, str]:
    return _p62_warning_context_from_html_impl(html, defect, radius=radius)


def _p62_recovery_snippets(
    html: str,
    defect: dict[str, Any],
    *,
    context_chars: int,
) -> tuple[list[str], str, str]:
    return _p62_recovery_snippets_impl(html, defect, context_chars=context_chars)


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
    return _validate_p62_marker_output_impl(marker_output_dir, figure_label)


def write_p62_marker_recovery_plan(
    run_dir: Path,
    *,
    gate_config: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Build reproducible marker_single commands for source-backed P62 recovery."""
    dependencies = P62MarkerRecoveryPlanDependencies(
        index_polish_stage_files=_index_polish_stage_files,
        selected_pdf_candidate=_selected_pdf_candidate,
        find_polish_stage_path_for_article=_find_polish_stage_path_for_article,
        recovery_snippets=_p62_recovery_snippets,
        full_figure_label_from_context=_p62_full_figure_label_from_context,
        pdf_text_pages=_pdf_text_pages,
        resolve_pdf_page_for_figure=_resolve_p62_pdf_page_for_figure,
        validate_marker_output=_validate_p62_marker_output,
    )
    return _write_p62_marker_recovery_plan_impl(
        run_dir,
        gate_config=gate_config or load_gate_config(),
        dependencies=dependencies,
        out_path=out_path,
        plan_name=DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME,
    )


def _path_is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _repair_p62_duplicate_figure_images(
    html: str,
    *,
    pdf_path: Path,
    artifact_dir: Path,
    zoom: float,
    repair_plain_duplicates: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    return _repair_p62_duplicate_figure_images_impl(
        html,
        pdf_path=pdf_path,
        artifact_dir=artifact_dir,
        zoom=zoom,
        pdf_text_pages=_pdf_text_pages,
        resolve_pdf_page_for_figure=_resolve_p62_pdf_page_for_figure,
        recover_detached_pdf_figure_plate_asset=_recover_p62_detached_pdf_figure_plate_asset,
        recover_pdf_figure_asset=_recover_p62_pdf_figure_asset,
        data_url_from_image_file=_data_url_from_image_file,
        slug=_slug,
        repair_plain_duplicates=repair_plain_duplicates,
    )


def _apply_p62_duplicate_figure_image_repairs(
    targets: list[Path],
    *,
    pdf_path: Path,
    artifact_dir: Path,
    zoom: float,
    repair_plain_duplicates: bool = False,
) -> dict[str, Any]:
    return _apply_p62_duplicate_figure_image_repairs_impl(
        targets,
        pdf_path=pdf_path,
        artifact_dir=artifact_dir,
        zoom=zoom,
        pdf_text_pages=_pdf_text_pages,
        resolve_pdf_page_for_figure=_resolve_p62_pdf_page_for_figure,
        recover_detached_pdf_figure_plate_asset=_recover_p62_detached_pdf_figure_plate_asset,
        recover_pdf_figure_asset=_recover_p62_pdf_figure_asset,
        data_url_from_image_file=_data_url_from_image_file,
        slug=_slug,
        repair_plain_duplicates=repair_plain_duplicates,
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
    return _p62_render_fallback_page_number_impl(pdf_path, source_page_number, figure_label)


def _p62_record_allows_page_render_fallback(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or "")
    if status in {"source_visual_unavailable", "figure_label_page_unavailable"}:
        return False
    if status == "ready":
        return True
    label_pages = record.get("figure_label_pdf_page_candidates")
    return bool(label_pages)


def _render_p61_nonduplicate_page_recovery(
    *,
    pdf_path: Path,
    source_page_number: int,
    figure_label: str,
    target_figure_key: str,
    artifact_dir: Path,
    render_zoom: float,
    html: str,
) -> dict[str, Any]:
    fallback_page, fallback_reason = _p62_render_fallback_page_number(
        pdf_path,
        source_page_number,
        figure_label,
    )
    candidate_pages: list[tuple[int, str]] = []
    seen_pages: set[int] = set()
    for page_number, reason in (
        (fallback_page, fallback_reason),
        (source_page_number, "source_pdf_page"),
        (source_page_number - 1, "previous_source_pdf_page"),
        (source_page_number + 1, "next_source_pdf_page"),
    ):
        page_number = int(page_number or 0)
        if page_number <= 0 or page_number in seen_pages:
            continue
        seen_pages.add(page_number)
        candidate_pages.append((page_number, reason))

    attempts: list[dict[str, Any]] = []
    for page_number, reason in candidate_pages:
        render_path = (
            artifact_dir
            / f"fig_{_slug(figure_label or 'unknown', max_len=20)}_dedupe_{_slug(reason, max_len=32)}_"
            f"pdf_page_{page_number:04d}.png"
        )
        render = _render_pdf_evidence_page(pdf_path, page_number, render_path, zoom=render_zoom)
        rendered_path = Path(str(render.get("path") or "")) if render.get("path") else None
        rendered_data_url = _data_url_from_image_file(rendered_path) if rendered_path is not None else ""
        duplicates_existing = bool(
            rendered_data_url
            and _p62_data_url_duplicates_existing_figure_unit(
                html,
                rendered_data_url,
                target_figure_key=target_figure_key,
            )
        )
        attempt = {
            "page_number": page_number,
            "selection_reason": reason,
            "status": render.get("status") or "unknown",
            "path": render.get("path") or "",
            "error": render.get("error") or "",
            "duplicates_existing_figure": duplicates_existing,
        }
        attempts.append(attempt)
        if render.get("status") == "rendered" and rendered_path is not None and rendered_data_url and not duplicates_existing:
            return {
                "status": "rendered",
                "path": str(rendered_path),
                "page_number": page_number,
                "selection_reason": reason,
                "error": "",
                "data_url": rendered_data_url,
                "attempts": attempts,
            }

    return {
        "status": "all_render_candidates_duplicate_or_unavailable",
        "path": "",
        "page_number": 0,
        "selection_reason": "",
        "error": "",
        "data_url": "",
        "attempts": attempts,
    }


def _p62_false_match_hint_blocks_asset_recovery(
    hint: str,
    *,
    caption_found: bool = False,
) -> bool:
    return _p62_false_match_hint_blocks_asset_recovery_impl(hint, caption_found=caption_found)


def _p62_pdf_page_false_match_hint(pdf_path: Path, page_number: int, figure_label: str) -> str:
    return _p62_pdf_page_false_match_hint_impl(pdf_path, page_number, figure_label)


def _p62_pdf_page_caption_label_found(pdf_path: Path, page_number: int, figure_label: str) -> bool:
    return _p62_pdf_page_caption_label_found_impl(pdf_path, page_number, figure_label)


def _p62_page_caption_label_rects(page: Any, figure_label: str) -> list[Any]:
    return _p62_page_caption_label_rects_impl(page, figure_label)


def _p62_page_label_rects(page: Any, figure_label: str) -> list[Any]:
    return _p62_page_label_rects_impl(page, figure_label)


def _p62_pdf_visual_inventory(pdf_path: Path) -> dict[str, Any]:
    return _p62_pdf_visual_inventory_impl(pdf_path)


def _p62_pypdf_image_inventory(pdf_path: Path) -> dict[str, Any]:
    return _p62_pypdf_image_inventory_impl(pdf_path)


def _p62_external_pdf_tool_inventory() -> dict[str, Any]:
    return _p62_external_pdf_tool_inventory_impl()


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
    return _recover_p62_pdf_figure_asset_impl(
        pdf_path,
        page_number,
        figure_label,
        artifact_dir,
        zoom=zoom,
        data_url_from_image_file=_data_url_from_image_file,
        slug=_slug,
    )


def _recover_p62_detached_pdf_figure_plate_asset(
    pdf_path: Path,
    anchor_page_number: int,
    figure_label: str,
    artifact_dir: Path,
    *,
    zoom: float,
) -> dict[str, Any]:
    return _recover_p62_detached_pdf_figure_plate_asset_impl(
        pdf_path,
        anchor_page_number,
        figure_label,
        artifact_dir,
        zoom=zoom,
        data_url_from_image_file=_data_url_from_image_file,
        slug=_slug,
    )


def _p62_patch_targets_for_record(
    run_dir: Path,
    record: dict[str, Any],
    manifest_article: dict[str, Any],
    *,
    allow_external_paths: bool,
) -> list[Path]:
    dependencies = P62PatchTargetDependencies(
        existing_path_candidates=_existing_path_candidates,
        path_is_inside=_path_is_inside,
        polish_stage=POLISH_STAGE,
    )
    return _p62_patch_targets_for_record_impl(
        run_dir,
        record,
        manifest_article,
        allow_external_paths=allow_external_paths,
        dependencies=dependencies,
    )


def _merge_p62_html_patch_result(item: dict[str, Any], result: Any) -> None:
    item["patch_replacement_count"] = int(result.replacement_count)
    item["patched_paths"] = list(result.patched_paths)
    if result.errors:
        item.setdefault("patch_errors", []).extend(result.errors)


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
    return _audit_defect_ids_impl(article)


def _audit_articles_by_auto_repair_need(audit_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _audit_articles_by_auto_repair_need_impl(audit_report)


def _assessment_articles_by_broken_internal_links(assessment: dict[str, Any]) -> dict[str, int]:
    return _assessment_articles_by_broken_internal_links_impl(assessment)


def _visible_ref_prefix_number(text: str) -> int | None:
    return _visible_ref_prefix_number_impl(text)


def _repair_visible_reference_numbers(html: str) -> tuple[str, int]:
    return _repair_visible_reference_numbers_impl(html)


def _relink_spaced_multipanel_figure_refs(html: str) -> tuple[str, int]:
    return _relink_spaced_multipanel_figure_refs_impl(html)


def _repair_second_echelon_ocr_residue(html: str) -> tuple[str, int]:
    return _repair_second_echelon_ocr_residue_impl(html)


def _unwrap_broken_internal_links(html: str) -> tuple[str, int]:
    return _unwrap_broken_internal_links_impl(html)


def _relink_external_numeric_citation_anchors(html: str) -> tuple[str, int]:
    return _relink_external_numeric_citation_anchors_impl(html)


def _unwrap_author_year_numeric_ref_links(html: str) -> tuple[str, int]:
    return _unwrap_author_year_numeric_ref_links_impl(html)


def _unwrap_author_year_ref_anchors(html: str) -> tuple[str, int]:
    return _unwrap_author_year_ref_anchors_impl(html)


def write_polish_auto_repair_stage(
    run_dir: Path,
    *,
    gate_config: dict[str, Any] | None = None,
    out_path: Path | None = None,
    jobs: int | None = None,
    article_ids: Iterable[str] | None = None,
    refresh_assessment: bool = True,
) -> dict[str, Any]:
    """Apply source-backed local repairs promoted from post-audit defect checks."""

    gate_config = gate_config or load_gate_config()
    run_dir = run_dir.resolve(strict=False)
    out_path = out_path or (run_dir / DEFAULT_POLISH_AUTO_REPAIR_REPORT_NAME)
    repair_root = run_dir / "polish_auto_repair"
    audit_report = _load_json(run_dir / "audit_full_checks.json", default={})
    assessment = _load_json(run_dir / "assessment.json", default={})
    manifest = _load_json(run_dir / "manifest.json", default={})
    manifest_by_article = _manifest_article_by_id(manifest)
    repair_articles = _audit_articles_by_auto_repair_need(audit_report)
    for article_id, broken_count in _assessment_articles_by_broken_internal_links(assessment).items():
        repair_articles.setdefault(article_id, {"article": {}, "defect_ids": []})[
            "broken_internal_links"
        ] = broken_count
    article_filter = {str(article_id) for article_id in (article_ids or []) if str(article_id)}
    if article_filter:
        repair_articles = {
            article_id: item
            for article_id, item in repair_articles.items()
            if article_id in article_filter
        }
    zoom = float(
        gate_config.get("polish_auto_repair_render_zoom")
        or gate_config.get("p62_image_recovery_render_zoom")
        or 1.5
    )
    apply_patches = bool(gate_config.get("polish_auto_repair_apply_patches", True))
    worker_count = max(
        1,
        int(
            jobs
            if jobs is not None
            else (gate_config.get("polish_auto_repair_jobs") or gate_config.get("document_jobs") or 1)
        ),
    )

    report_articles: list[dict[str, Any]] = []
    patched_article_ids: set[str] = set()
    repair_counts: Counter[str] = Counter()
    target_patch_counts: Counter[str] = Counter()

    if worker_count > 1 and len(repair_articles) > 1 and not article_filter:
        parallel_root = repair_root / "_parallel_article_reports"
        parallel_root.mkdir(parents=True, exist_ok=True)
        repair_items = sorted(repair_articles.items())
        article_order = {article_id: index for index, (article_id, _item) in enumerate(repair_items, start=1)}
        print(
            "Polish auto repair parallel dispatch: "
            f"articles={len(repair_items)} jobs={worker_count} apply_patches={apply_patches}",
            flush=True,
        )

        def process_article_repair(group_index: int, article_id: str) -> dict[str, Any]:
            report_path = parallel_root / f"{group_index:03d}_{_slug(article_id, max_len=72)}.report.json"
            return write_polish_auto_repair_stage(
                run_dir,
                gate_config=gate_config,
                out_path=report_path,
                jobs=1,
                article_ids=[article_id],
                refresh_assessment=False,
            )

        completed_count = 0
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(process_article_repair, index, article_id): article_id
                for index, (article_id, _item) in enumerate(repair_items, start=1)
            }
            for future in as_completed(futures):
                article_id = futures[future]
                group_report = future.result()
                completed_count += 1
                patched_article_ids.update(str(article) for article in (group_report.get("patched_articles") or []))
                repair_counts.update(
                    {str(key): int(value) for key, value in (group_report.get("repair_counts") or {}).items()}
                )
                target_patch_counts.update(
                    {str(key): int(value) for key, value in (group_report.get("patched_targets") or {}).items()}
                )
                for article_report in group_report.get("articles") or []:
                    if not isinstance(article_report, dict):
                        continue
                    article_report = dict(article_report)
                    article_report["index"] = article_order.get(str(article_report.get("article") or article_id), 0)
                    report_articles.append(article_report)
                print(
                    "Polish auto repair article complete: "
                    f"{completed_count}/{len(repair_items)} article={_console_text(article_id)} "
                    f"patched_articles={group_report.get('patched_article_count', 0)}",
                    flush=True,
                )

        report_articles.sort(key=lambda item: int(item.get("index") or 0))
        if patched_article_ids and refresh_assessment:
            _refresh_assessment_for_articles(run_dir, patched_article_ids)
        report = {
            "generated_at": _now(),
            "run_dir": str(run_dir),
            "path": str(out_path),
            "status": "patched" if patched_article_ids else "no_changes",
            "candidate_count": len(repair_articles),
            "patched_article_count": len(patched_article_ids),
            "patched_articles": sorted(patched_article_ids),
            "repair_counts": dict(sorted(repair_counts.items())),
            "patched_targets": dict(sorted(target_patch_counts.items())),
            "apply_patches": apply_patches,
            "render_zoom": zoom,
            "jobs": worker_count,
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

    print(
        "Polish auto repair started: "
        f"articles={len(repair_articles)} apply_patches={apply_patches} jobs={worker_count}",
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
            "broken_internal_links": int(item.get("broken_internal_links") or 0),
            "targets": [str(path) for path in targets],
            "repairs": [],
            "patched": False,
            "errors": [],
        }

        if "P96" in defect_ids:
            audit_summary = audit_article.get("summary") or {}
            pdf_path = Path(str(audit_summary.get("source_pdf_path") or ""))
            selected_candidate: dict[str, Any] | None = None
            source_pdf_candidates: list[dict[str, Any]] = []
            if not pdf_path.is_file():
                selected_candidate, source_pdf_candidates = _selected_pdf_candidate(
                    run_dir,
                    article_id,
                    audit_summary,
                    manifest_article,
                )
                if selected_candidate and selected_candidate.get("path"):
                    pdf_path = Path(str(selected_candidate.get("path")))
            if pdf_path.is_file() and apply_patches:
                duplicate_report = _apply_p62_duplicate_figure_image_repairs(
                    targets,
                    pdf_path=pdf_path,
                    artifact_dir=repair_root / _slug(article_id, max_len=72) / "p96_duplicate_visual",
                    zoom=zoom,
                    repair_plain_duplicates=True,
                )
                patched_count = int(duplicate_report.get("repair_count") or 0)
                article_report["repairs"].append({"id": "P96", **duplicate_report})
                if patched_count:
                    repair_counts["P96"] += patched_count
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
                        "selected_pdf_candidate": selected_candidate or {},
                        "source_pdf_candidates": source_pdf_candidates[:8],
                    }
                )

        if "P17" in defect_ids and apply_patches:
            for target_path in targets:
                try:
                    html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                patched, p17_repairs = _relink_spaced_multipanel_figure_refs(html)
                if patched == html:
                    continue
                try:
                    target_path.write_text(patched, encoding="utf-8")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                repair_counts["P17"] += p17_repairs
                patched_article_ids.add(article_id)
                article_report["patched"] = True
                target_patch_counts[str(target_path)] += 1
                article_report["repairs"].append(
                    {
                        "id": "P17",
                        "path": str(target_path),
                        "spaced_multipanel_links": p17_repairs,
                    }
                )

        if "P71" in defect_ids and apply_patches:
            for target_path in targets:
                try:
                    html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                patched, p71_repairs = _repair_second_echelon_ocr_residue(html)
                if patched == html:
                    continue
                try:
                    target_path.write_text(patched, encoding="utf-8")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                repair_counts["P71"] += p71_repairs
                patched_article_ids.add(article_id)
                article_report["patched"] = True
                target_patch_counts[str(target_path)] += 1
                article_report["repairs"].append(
                    {
                        "id": "P71",
                        "path": str(target_path),
                        "ocr_residue_repairs": p71_repairs,
                    }
                )

        if {"P04", "P04N"} & defect_ids and apply_patches:
            for target_path in targets:
                try:
                    html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                patched, p04_repairs = _relink_external_numeric_citation_anchors(html)
                if patched == html:
                    continue
                try:
                    target_path.write_text(patched, encoding="utf-8")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                repair_counts["P04"] += p04_repairs
                patched_article_ids.add(article_id)
                article_report["patched"] = True
                target_patch_counts[str(target_path)] += 1
                article_report["repairs"].append(
                    {
                        "id": "P04/P04N",
                        "path": str(target_path),
                        "external_numeric_citation_anchor_relinks": p04_repairs,
                    }
                )

        if {"P55", "P59", "P97", "P98"} & defect_ids and apply_patches:
            for target_path in targets:
                try:
                    html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                patched = html
                p55_repairs = 0
                p59_repairs = 0
                p97_repairs = 0
                p98_repairs = 0
                if "P55" in defect_ids:
                    patched, p55_repairs = _unwrap_author_year_ref_anchors(patched)
                if "P97" in defect_ids:
                    patched, p97_repairs = _repair_visible_reference_numbers(patched)
                if {"P59", "P98"} & defect_ids:
                    patched, numeric_repairs = _unwrap_author_year_numeric_ref_links(patched)
                    if "P59" in defect_ids:
                        p59_repairs = numeric_repairs
                    if "P98" in defect_ids:
                        p98_repairs = numeric_repairs
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
                if p59_repairs:
                    repair_counts["P59"] += p59_repairs
                if p97_repairs:
                    repair_counts["P97"] += p97_repairs
                if p98_repairs:
                    repair_counts["P98"] += p98_repairs
                if p55_repairs or p59_repairs or p97_repairs or p98_repairs:
                    article_report["repairs"].append(
                        {
                            "id": "P55/P59/P97/P98",
                            "path": str(target_path),
                            "p55_author_year_link_unwraps": p55_repairs,
                            "p59_numeric_link_unwraps": p59_repairs,
                            "p97_visible_number_repairs": p97_repairs,
                            "p98_numeric_link_unwraps": p98_repairs,
                        }
                    )

        if item.get("broken_internal_links") and apply_patches:
            for target_path in targets:
                try:
                    html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                patched, broken_link_repairs = _unwrap_broken_internal_links(html)
                if patched == html:
                    continue
                try:
                    target_path.write_text(patched, encoding="utf-8")
                except OSError as exc:
                    article_report["errors"].append({"path": str(target_path), "error": str(exc)})
                    continue
                repair_counts["broken_internal_links"] += broken_link_repairs
                patched_article_ids.add(article_id)
                article_report["patched"] = True
                target_patch_counts[str(target_path)] += 1
                article_report["repairs"].append(
                    {
                        "id": "broken_internal_links",
                        "path": str(target_path),
                        "unwrapped_links": broken_link_repairs,
                    }
                )

        report_articles.append(article_report)

    if patched_article_ids and refresh_assessment:
        _refresh_assessment_for_articles(run_dir, patched_article_ids)

    report = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "path": str(out_path),
        "status": "patched" if patched_article_ids else "no_changes",
        "candidate_count": len(repair_articles),
        "patched_article_count": len(patched_article_ids),
        "patched_articles": sorted(patched_article_ids),
        "repair_counts": dict(sorted(repair_counts.items())),
        "patched_targets": dict(sorted(target_patch_counts.items())),
        "apply_patches": apply_patches,
        "render_zoom": zoom,
        "jobs": worker_count,
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
    jobs: int | None = None,
    refresh_assessment: bool = True,
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
    stage_config = _resolve_p62_image_recovery_stage_config(
        gate_config,
        execute_marker=execute_marker,
        apply_patches=apply_patches,
        max_items=max_items,
        jobs=jobs,
    )
    max_items = stage_config.max_items
    if max_items and max_items > 0:
        records = records[:max_items]
    indexed_records = [
        {**record, "recovery_index": int(record.get("recovery_index") or index)}
        for index, record in enumerate(records, start=1)
    ]
    records = indexed_records

    execute_marker = stage_config.execute_marker
    apply_patches = stage_config.apply_patches
    worker_count = max(1, int(stage_config.jobs or 1))
    render_zoom = stage_config.render_zoom
    marker_timeout = stage_config.marker_timeout
    probe_source_visual_unavailable = stage_config.probe_source_visual_unavailable
    probe_marker_for_unavailable = stage_config.probe_marker_for_unavailable
    probe_marker_timeout = stage_config.probe_marker_timeout
    replace_page_render = stage_config.replace_page_render
    remove_false_match_recovery = stage_config.remove_false_match_recovery
    repair_duplicate_figure_images = stage_config.repair_duplicate_figure_images

    manifest = _load_json(run_dir / "manifest.json", default={})
    manifest_by_article = _manifest_article_by_id(manifest)
    recovery_root = run_dir / "p62_image_recovery"
    recovered_records: list[dict[str, Any]] = []
    patched_article_ids: set[str] = set()
    if worker_count > 1 and len(records) > 1:
        article_groups: dict[str, list[dict[str, Any]]] = {}
        for index, record in enumerate(records, start=1):
            article_id = str(record.get("article") or f"article_{index}")
            article_groups.setdefault(article_id, []).append(record)
        if len(article_groups) > 1:
            parallel_root = recovery_root / "_parallel_article_plans"
            parallel_root.mkdir(parents=True, exist_ok=True)
            group_items = list(article_groups.items())
            print(
                "P62 image recovery parallel dispatch: "
                f"records={len(records)} articles={len(group_items)} jobs={worker_count}",
                flush=True,
            )

            def group_artifact_paths(group_index: int, article_id: str) -> tuple[Path, Path]:
                group_slug = f"{group_index:03d}_{_slug(article_id, max_len=72)}"
                return (
                    parallel_root / f"{group_slug}.plan.json",
                    parallel_root / f"{group_slug}.report.json",
                )

            def load_completed_group_report(
                group_index: int,
                article_id: str,
                group_records: list[dict[str, Any]],
            ) -> dict[str, Any] | None:
                _group_plan_path, group_report_path = group_artifact_paths(group_index, article_id)
                if not group_report_path.is_file():
                    return None
                group_report = _load_json(group_report_path, default={})
                if not isinstance(group_report, dict):
                    return None
                report_records = [
                    item for item in (group_report.get("articles") or []) if isinstance(item, dict)
                ]
                expected_indices = sorted(
                    int(record.get("recovery_index") or 0) for record in group_records
                )
                actual_indices = sorted(int(item.get("record_index") or 0) for item in report_records)
                if not expected_indices or actual_indices != expected_indices:
                    return None
                if any(str(item.get("article") or "") != article_id for item in report_records):
                    return None
                return group_report

            def process_article_group(
                group_index: int,
                article_id: str,
                group_records: list[dict[str, Any]],
            ) -> dict[str, Any]:
                group_plan_path, group_report_path = group_artifact_paths(group_index, article_id)
                group_plan = dict(plan)
                group_plan["articles"] = group_records
                group_plan["selected_count"] = len(group_records)
                _write_json(group_plan_path, group_plan)
                return write_p62_image_recovery_stage(
                    run_dir,
                    gate_config=gate_config,
                    plan_path=group_plan_path,
                    out_path=group_report_path,
                    execute_marker=execute_marker,
                    apply_patches=apply_patches,
                    allow_external_paths=allow_external_paths,
                    max_items=0,
                    jobs=1,
                    refresh_assessment=False,
                )

            reports_by_group: list[dict[str, Any] | None] = [None] * len(group_items)
            completed_records = 0
            completed_groups = 0
            pending_groups: list[tuple[int, str, list[dict[str, Any]]]] = []
            for group_index, (article_id, group_records) in enumerate(group_items, start=1):
                cached_report = load_completed_group_report(group_index, article_id, group_records)
                if cached_report is None:
                    pending_groups.append((group_index, article_id, group_records))
                    continue
                reports_by_group[group_index - 1] = cached_report
                completed_records += len(group_records)
                completed_groups += 1
                print(
                    "P62 image recovery article cached: "
                    f"articles={completed_groups}/{len(group_items)} "
                    f"records={completed_records}/{len(records)} "
                    f"article={_console_text(article_id)} "
                    f"asset_ready={cached_report.get('asset_ready_count', 0)} "
                    f"patched={cached_report.get('patched_warning_count', 0)}",
                    flush=True,
                )
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(process_article_group, group_index, article_id, group_records): (
                        group_index,
                        article_id,
                        len(group_records),
                    )
                    for group_index, article_id, group_records in pending_groups
                }
                for future in as_completed(futures):
                    group_index, article_id, group_record_count = futures[future]
                    group_report = future.result()
                    reports_by_group[group_index - 1] = group_report
                    completed_records += group_record_count
                    completed_groups += 1
                    print(
                        "P62 image recovery article complete: "
                        f"articles={completed_groups}/{len(group_items)} "
                        f"records={completed_records}/{len(records)} "
                        f"article={_console_text(article_id)} "
                        f"asset_ready={group_report.get('asset_ready_count', 0)} "
                        f"patched={group_report.get('patched_warning_count', 0)}",
                        flush=True,
                    )

            for group_report in reports_by_group:
                if not isinstance(group_report, dict):
                    continue
                recovered_records.extend(
                    item for item in (group_report.get("articles") or []) if isinstance(item, dict)
                )
                patched_article_ids.update(str(article) for article in (group_report.get("patched_articles") or []))
            recovered_records.sort(key=lambda item: int(item.get("record_index") or 0))

            if patched_article_ids and refresh_assessment:
                _refresh_assessment_for_articles(run_dir, patched_article_ids)

            report = _build_p62_image_recovery_report(
                generated_at=_now(),
                run_dir=run_dir,
                out_path=out_path,
                plan_path=plan_path,
                recovery_root=recovery_root,
                plan_candidate_count=int(plan.get("candidate_count") or 0),
                selected_count=len(records),
                recovered_records=recovered_records,
                patched_article_ids=patched_article_ids,
                stage_config=stage_config,
                allow_external_paths=allow_external_paths,
            )
            _write_json(out_path, report)
            return report

    print(
        "P62 image recovery started: "
        f"records={len(records)} execute_marker={execute_marker} apply_patches={apply_patches} jobs={worker_count}",
        flush=True,
    )

    for index, record in enumerate(records, start=1):
        article_id = str(record.get("article") or f"article_{index}")
        figure_label = str(record.get("figure_label") or "").strip()
        resolved_figure_label = str(record.get("resolved_figure_label") or figure_label).strip()
        record_index = int(record.get("recovery_index") or index)
        artifact_dir = recovery_root / f"{record_index:03d}_{_slug(article_id, max_len=72)}"
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
            "record_index": record_index,
            "source_article": record.get("source_article") or article_id,
            "defect_id": record.get("defect_id") or "",
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
                elif str(record.get("defect_id") or "") == "P61":
                    pass
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
                            + "_"
                            + _slug(article_id, max_len=24)
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
                    result = _apply_p62_html_patch_to_targets(
                        targets,
                        lambda html: _replace_p62_recovery_with_missing_warning(
                            html,
                            figure_label=figure_label or resolved_figure_label,
                            reason="source_visual_unavailable",
                        ),
                    )
                    _merge_p62_html_patch_result(item, result)
                    item["false_match_recovery_removed"] = bool(result.replacement_count)
                    if result.replacement_count:
                        patched_article_ids.add(article_id)
                if item.get("existing_page_render_recovery") and apply_patches:
                    result = _apply_p62_html_patch_to_targets(
                        targets,
                        lambda html: _replace_p62_recovery_with_missing_warning(
                            html,
                            figure_label=figure_label or resolved_figure_label,
                            reason="source_visual_unavailable",
                            replace_sources=P62_LOW_FIDELITY_RECOVERY_SOURCES,
                        ),
                        patched_paths=item.get("patched_paths") or [],
                        replacement_count=int(item.get("patch_replacement_count") or 0),
                    )
                    _merge_p62_html_patch_result(item, result)
                    item["page_render_recovery_removed"] = bool(result.replacement_count)
                    if result.replacement_count:
                        patched_article_ids.add(article_id)
                if source_page_is_false_match and apply_patches:
                    result = _apply_p62_html_patch_to_targets(
                        targets,
                        lambda html: _replace_p62_figure_unit_target_with_missing_warning(
                            html,
                            figure_label=figure_label or resolved_figure_label,
                            reason="source_visual_unavailable",
                        ),
                        patched_paths=item.get("patched_paths") or [],
                        replacement_count=int(item.get("patch_replacement_count") or 0),
                    )
                    _merge_p62_html_patch_result(item, result)
                    if result.replacement_count:
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
            recovered_asset = _recover_p62_pdf_figure_asset_for_stage(
                pdf_path,
                source_page_number,
                resolved_figure_label or figure_label,
                artifact_dir,
                zoom=render_zoom,
                recover_detached_pdf_figure_plate_asset=_recover_p62_detached_pdf_figure_plate_asset,
                recover_pdf_figure_asset=_recover_p62_pdf_figure_asset,
                data_url_from_image_file=_data_url_from_image_file,
            )
            item.update(recovered_asset.item_updates)
            data_url = recovered_asset.data_url
            recovery_source = recovered_asset.recovery_source
            recovery_detail = recovered_asset.recovery_detail

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
                            + "_"
                            + _slug(article_id, max_len=24)
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
                    result = _apply_p62_html_patch_to_targets(
                        targets,
                        lambda html: _replace_p62_recovery_with_missing_warning(
                            html,
                            figure_label=figure_label or resolved_figure_label,
                            reason="source_visual_unavailable",
                            replace_sources=P62_LOW_FIDELITY_RECOVERY_SOURCES,
                        ),
                        patched_paths=item.get("patched_paths") or [],
                        replacement_count=int(item.get("patch_replacement_count") or 0),
                    )
                    _merge_p62_html_patch_result(item, result)
                    item["page_render_recovery_removed"] = bool(result.replacement_count)
                    if result.replacement_count:
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
            def patch_recovered_image(html: str) -> tuple[str, int]:
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
                if not replacements and str(record.get("defect_id") or "") == "P61":
                    target_figure_key = str(record.get("target_figure_key") or figure_label or resolved_figure_label)
                    insert_data_url = data_url
                    insert_source = recovery_source
                    insert_detail = recovery_detail
                    if _p62_data_url_duplicates_existing_figure_unit(
                        html,
                        insert_data_url,
                        target_figure_key=target_figure_key,
                    ):
                        render = _render_p61_nonduplicate_page_recovery(
                            pdf_path=pdf_path,
                            source_page_number=source_page_number,
                            figure_label=resolved_figure_label or figure_label,
                            target_figure_key=target_figure_key,
                            artifact_dir=artifact_dir,
                            render_zoom=render_zoom,
                            html=html,
                        )
                        item.update(
                            {
                                "page_render_status": render.get("status"),
                                "page_render_path": render.get("path") or "",
                                "page_render_page_number": render.get("page_number") or 0,
                                "page_render_selection_reason": (
                                    f"p61_duplicate_asset:{render.get('selection_reason') or ''}"
                                ),
                                "page_render_error": render.get("error") or "",
                                "page_render_attempts": render.get("attempts") or [],
                            }
                        )
                        rendered_data_url = str(render.get("data_url") or "")
                        if rendered_data_url:
                            insert_data_url = rendered_data_url
                            insert_source = "pdf_page_render"
                            insert_detail = str(render.get("path") or "")
                        else:
                            item["unresolved_reason"] = "p61_duplicate_asset_no_nonduplicate_page_render"
                            return html, 0
                    if re.search(rf"\bid\s*=\s*([\"'])fig-{re.escape(target_figure_key)}\1", html, re.IGNORECASE):
                        patched, replacements = _replace_p62_figure_unit_target_with_image(
                            html,
                            figure_label=target_figure_key,
                            data_url=insert_data_url,
                            source=insert_source,
                            source_detail=insert_detail,
                        )
                    else:
                        patched, replacements = _insert_p62_recovered_figure_unit_for_visible_reference(
                            html,
                            target_figure_key=target_figure_key,
                            visible_label=str(record.get("visible_label") or f"Figure {figure_label or resolved_figure_label}"),
                            snippet=str(record.get("snippet") or " ".join(record.get("problem_snippets") or [])),
                            data_url=insert_data_url,
                            source=insert_source,
                            source_detail=insert_detail,
                        )
                if str(record.get("defect_id") or "") == "P61":
                    patched, moved_recovered_units = _move_p61_recovered_units_after_sentence_continuation(patched)
                    replacements += moved_recovered_units
                return patched, replacements

            result = _apply_p62_html_patch_to_targets(targets, patch_recovered_image)
            _merge_p62_html_patch_result(item, result)
            patched_paths = list(result.patched_paths)
            replacement_count = result.replacement_count
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

    if patched_article_ids and refresh_assessment:
        _refresh_assessment_for_articles(run_dir, patched_article_ids)

    report = _build_p62_image_recovery_report(
        generated_at=_now(),
        run_dir=run_dir,
        out_path=out_path,
        plan_path=plan_path,
        recovery_root=recovery_root,
        plan_candidate_count=int(plan.get("candidate_count") or 0),
        selected_count=len(records),
        recovered_records=recovered_records,
        patched_article_ids=patched_article_ids,
        stage_config=stage_config,
        allow_external_paths=allow_external_paths,
    )
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
    return _reference_id_numbers_impl(html)


def _reference_id_gap_numbers(html: str) -> list[int]:
    return _reference_id_gap_numbers_impl(html)


def _expand_reference_candidate_numbers(value: str) -> list[int]:
    return _expand_reference_candidate_numbers_impl(value)


def _plain_reference_candidate_is_safe(text: str, match: re.Match[str]) -> bool:
    return _plain_reference_candidate_is_safe_impl(text, match)


def _reference_recovery_block_is_protected(attrs: str, body: str) -> bool:
    return _reference_recovery_block_is_protected_impl(attrs, body)


def _unlinked_body_reference_candidate_numbers(html: str) -> list[int]:
    return _unlinked_body_reference_candidate_numbers_impl(html)


def _pdf_reference_recovery_numbers(polished_html: str) -> tuple[list[int], str]:
    return _pdf_reference_recovery_numbers_impl(polished_html)


def _profile_has_reference_entries(profile: dict[str, Any]) -> bool:
    return _profile_has_reference_entries_impl(profile)


def _reference_entry_record(entry: Any) -> dict[str, Any]:
    return _reference_entry_record_impl(entry)


def _enrich_profile_with_pdf_reference_entries_if_needed(
    profile: dict[str, Any],
    polished_html: str,
    source_run_dir: Path,
    article: str,
    manifest_article: dict[str, Any],
    pdf_reference_cache: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], int, str]:
    return _enrich_profile_with_pdf_reference_entries_if_needed_impl(
        profile,
        polished_html,
        source_run_dir,
        article,
        manifest_article,
        pdf_reference_cache,
        article_source_pdf_candidates=_article_source_pdf_candidates,
        extract_reference_entries=extract_reference_entries_from_pdf,
    )


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
    jobs: int = 1,
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
    pdf_reference_entries_cache_lock = threading.Lock()
    source_manifest = _load_json(source_run_dir / "manifest.json", default={})
    raw_files: list[Path] = []

    try:
        raw_files = sorted(raw_source_dir.glob(f"*.{RAW_STAGE}"))
        total_raw = len(raw_files)
        worker_count = max(1, int(jobs or 1))
        print(
            f"Repolish started: raw={total_raw} source={source_run_dir} jobs={worker_count}",
            flush=True,
        )
        last_report = time.monotonic()
        article_records_by_index: list[dict[str, Any] | None] = [None] * total_raw
        assessments_by_index: list[dict[str, Any] | None] = [None] * total_raw
        skipped_by_index: list[dict[str, Any] | None] = [None] * total_raw
        completed_count = 0
        processed_count = 0
        skipped_count = 0

        def report_progress(completed: int, *, force: bool = False) -> None:
            nonlocal last_report
            now = time.monotonic()
            if force or completed % 25 == 0 or now - last_report >= 15:
                print(
                    "Repolish progress: "
                    f"{completed}/{total_raw} articles={processed_count} "
                    f"skipped={skipped_count} changed={changed_count}",
                    flush=True,
                )
                last_report = now

        def process_raw_file(index: int, raw_path: Path) -> dict[str, Any]:
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
            if language_decision.should_skip:
                return {
                    "index": index,
                    "detected_language": language_decision.detection.detected_language,
                    "skip_reason": language_decision.skip_reason,
                    "skipped_record": {
                        "index": index,
                        "article": article,
                        "raw_cache_path": str(out_raw),
                        "profile_path": str(out_profile),
                        "profile_status": _profile_value(profile, "status"),
                        "citation_style": _profile_value(profile, "style"),
                        "citation_confidence": _profile_value(profile, "confidence"),
                        "language_detection": language_decision.detection.to_dict(),
                        **language_fields,
                    },
                }

            polished = polish_html_document(
                raw_html,
                table_caption_language="en",
                enable_citation_linkify=True,
                citation_profile=profile,
                polish_language=language_decision.selected_polish_language,
            )
            recovered_pdf_refs = 0
            pdf_reference_source = ""
            if not _profile_has_reference_entries(profile) and _pdf_reference_recovery_numbers(polished)[0]:
                with pdf_reference_entries_cache_lock:
                    profile, recovered_pdf_refs, pdf_reference_source = (
                        _enrich_profile_with_pdf_reference_entries_if_needed(
                            profile,
                            polished,
                            source_run_dir,
                            article,
                            manifest_article,
                            pdf_reference_entries_cache,
                        )
                    )
            if recovered_pdf_refs:
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
            previous_polish = source_run_dir / "polish" / out_polish.name
            previous_text = (
                previous_polish.read_text(encoding="utf-8", errors="replace")
                if previous_polish.is_file()
                else None
            )
            changed = previous_text != polished
            out_polish.write_text(polished, encoding="utf-8")

            pair_dir = audit_tree / article
            pair_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out_raw, pair_dir / RAW_STAGE)
            (pair_dir / POLISH_STAGE).write_text(polished, encoding="utf-8")

            status = _profile_value(profile, "status")
            style_key = f"{_profile_value(profile, 'style')}:{_profile_value(profile, 'confidence')}"
            article_record = {
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
            assessment = assess_polish_html(article, polished, profile)
            assessment.update(language_fields)
            return {
                "index": index,
                "detected_language": language_decision.detection.detected_language,
                "polish_language": language_decision.selected_polish_language,
                "changed": changed,
                "restored_images": restored_images,
                "restored_image_source": data_image_source,
                "pdf_reference_recovered": recovered_pdf_refs,
                "pdf_reference_source": pdf_reference_source,
                "profile_status": status,
                "profile_style_key": style_key,
                "article_record": article_record,
                "assessment": assessment,
            }

        def record_result(result: dict[str, Any]) -> None:
            nonlocal changed_count
            nonlocal restored_image_count
            nonlocal pdf_reference_recovery_count
            nonlocal processed_count
            nonlocal skipped_count
            index = int(result["index"])
            language_counts[str(result.get("detected_language") or "unknown")] += 1
            skipped_record = result.get("skipped_record")
            if isinstance(skipped_record, dict):
                skip_reason = str(result.get("skip_reason") or "")
                if skip_reason:
                    skip_reason_counts[skip_reason] += 1
                skipped_by_index[index - 1] = skipped_record
                skipped_count += 1
                return

            article_record = result.get("article_record")
            assessment = result.get("assessment")
            if not isinstance(article_record, dict) or not isinstance(assessment, dict):
                raise ValueError(f"Invalid repolish result for index {index}")
            article_records_by_index[index - 1] = article_record
            assessments_by_index[index - 1] = assessment
            processed_count += 1
            polish_language_counts[str(result.get("polish_language") or "unknown")] += 1
            if bool(result.get("changed")):
                changed_count += 1
            restored_images = int(result.get("restored_images") or 0)
            if restored_images:
                restored_image_count += restored_images
                restored_image_source_counts[str(result.get("restored_image_source") or "unknown")] += restored_images
            recovered_pdf_refs = int(result.get("pdf_reference_recovered") or 0)
            if recovered_pdf_refs:
                pdf_reference_recovery_count += recovered_pdf_refs
                pdf_reference_recovery_source_counts[str(result.get("pdf_reference_source") or "unknown")] += (
                    recovered_pdf_refs
                )
            status = str(result.get("profile_status") or "unknown")
            style_key = str(result.get("profile_style_key") or "unknown:low")
            profile_status_counts[status] = profile_status_counts.get(status, 0) + 1
            profile_style_counts[style_key] = profile_style_counts.get(style_key, 0) + 1

        if worker_count <= 1 or total_raw <= 1:
            for index, raw_path in enumerate(raw_files, start=1):
                record_result(process_raw_file(index, raw_path))
                completed_count += 1
                report_progress(completed_count)
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(process_raw_file, index, raw_path)
                    for index, raw_path in enumerate(raw_files, start=1)
                ]
                for future in as_completed(futures):
                    record_result(future.result())
                    completed_count += 1
                    report_progress(completed_count)

        articles = [article for article in article_records_by_index if article is not None]
        assessments = [assessment for assessment in assessments_by_index if assessment is not None]
        skipped_articles = [article for article in skipped_by_index if article is not None]
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
        "jobs": max(1, int(jobs or 1)),
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
        "jobs": manifest["jobs"],
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
    return _defect_id_counts_impl(defects)


def _severity_counts(defects: Iterable[dict[str, Any]]) -> dict[str, int]:
    return _severity_counts_impl(defects)


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
    return _existing_queue_items_impl(path)


def _review_state_by_key(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _review_state_by_key_impl(items)


def write_manual_review_queue(
    run_dir: Path,
    *,
    gate_config_path: Path = DEFAULT_GATE_CONFIG,
    gate_config: dict[str, Any] | None = None,
    ignored_defect_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    return _write_manual_review_queue_impl(
        run_dir,
        gate_config=gate_config or load_gate_config(gate_config_path),
        ignored_defect_ids=ignored_defect_ids,
        comparison_by_article=_comparison_by_article,
        manifest_article_by_id=_manifest_article_by_id,
    )


def _stage_path_for_review(run_dir: Path, value: Any) -> Path | None:
    return _stage_path_for_review_impl(run_dir, value, repo_root=ROOT)


def _relative_review_href(review_dir: Path, target_path: Path) -> str:
    return _relative_review_href_impl(review_dir, target_path)


def write_article_review_stage(
    run_dir: Path,
    review_queue: list[dict[str, Any]] | None = None,
    *,
    max_articles: int | None = None,
) -> dict[str, Any]:
    return _write_article_review_stage_impl(
        run_dir,
        review_queue,
        max_articles=max_articles,
        repo_root=ROOT,
        polish_stage=POLISH_STAGE,
        copy_review_html_with_inline_images=_copy_review_html_with_inline_images,
    )


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
            "source_visual_unavailable_count": p62_image_recovery_report.get(
                "source_visual_unavailable_count",
                0,
            ),
            "source_visual_unavailable_group_count": p62_image_recovery_report.get(
                "source_visual_unavailable_group_count",
                0,
            ),
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
            "jobs": p62_image_recovery_report.get("jobs"),
        },
        "polish_auto_repair_stage": {
            "path": polish_auto_repair_report.get("path")
            or str(run_dir / DEFAULT_POLISH_AUTO_REPAIR_REPORT_NAME),
            "status": polish_auto_repair_report.get("status"),
            "candidate_count": polish_auto_repair_report.get("candidate_count", 0),
            "patched_article_count": polish_auto_repair_report.get("patched_article_count", 0),
            "repair_counts": polish_auto_repair_report.get("repair_counts", {}),
            "apply_patches": polish_auto_repair_report.get("apply_patches"),
            "jobs": polish_auto_repair_report.get("jobs"),
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
    return _render_llm_prompt_impl(pack)

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
    pdf_diagnostics_cache_dir: Path | None = None,
    jobs: int = 1,
    merge_previous_report_path: Path | None = None,
) -> None:
    quality_commands.run_audit(
        run_dir,
        roots=roots,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_path=pdf_map_path,
        pdf_diagnostics_cache_dir=pdf_diagnostics_cache_dir,
        jobs=jobs,
        merge_previous_report_path=merge_previous_report_path,
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


def _patched_article_ids_from_repair_report(report: dict[str, Any]) -> set[str]:
    article_ids = {str(article) for article in report.get("patched_articles") or [] if str(article)}
    for item in report.get("articles") or []:
        if not isinstance(item, dict):
            continue
        patched = (
            bool(item.get("patched"))
            or bool(item.get("patched_paths"))
            or int(item.get("patch_replacement_count") or 0) > 0
            or int(item.get("duplicate_visual_repair_count") or 0) > 0
        )
        if patched and item.get("article"):
            article_ids.add(str(item.get("article")))
    return article_ids


def _repair_audit_roots_for_articles(run_dir: Path, article_ids: Iterable[str]) -> tuple[list[Path], list[str]]:
    roots: list[Path] = []
    missing: list[str] = []
    for article_id in sorted({str(article_id) for article_id in article_ids if str(article_id)}):
        root = run_dir / "audit_tree" / article_id
        if (root / RAW_STAGE).is_file() and (root / POLISH_STAGE).is_file():
            roots.append(root)
        else:
            missing.append(article_id)
    return roots, missing


def _configured_optional_path(value: Any) -> Path | None:
    if value is None or value == "":
        return None
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def _resolved_stage_jobs(
    *,
    args_value: int | None,
    gate_config: dict[str, Any],
    gate_key: str,
    default_jobs: int,
) -> int:
    value = args_value
    if value is None:
        value = gate_config.get(gate_key)
    if value is None:
        value = default_jobs
    return max(1, int(value or 1))


def observe(args: argparse.Namespace) -> int:
    run_dir = args.out_dir.resolve(strict=False)
    converted_roots = list(args.converted_roots or [])
    if args.source_run_dir and converted_roots:
        raise SystemExit("Use either --source-run-dir or --converted-roots, not both.")
    gate_config = load_gate_config(args.gate_config)
    default_jobs = max(1, int(args.jobs or gate_config.get("document_jobs") or 1))
    repolish_jobs = _resolved_stage_jobs(
        args_value=args.repolish_jobs,
        gate_config=gate_config,
        gate_key="repolish_jobs",
        default_jobs=default_jobs,
    )
    audit_jobs = _resolved_stage_jobs(
        args_value=args.audit_jobs,
        gate_config=gate_config,
        gate_key="audit_jobs",
        default_jobs=default_jobs,
    )
    if args.source_run_dir:
        manifest = repolish_cached_run(
            args.source_run_dir,
            run_dir,
            polish_language=args.polish_language,
            target_language=args.target_language,
            skip_non_target_language=args.skip_non_target_language,
            skip_unknown_language=args.skip_unknown_language,
            jobs=repolish_jobs,
        )
        print(
            "Repolished cached run: "
            f"raw={manifest['raw_count']} "
            f"articles={manifest['article_count']} "
            f"skipped={manifest['skipped_count']} "
            f"changed={manifest['changed_count']} "
            f"jobs={manifest.get('jobs')}"
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
                jobs=repolish_jobs,
            )
            print(
                "Repolished converted raw stages: "
                f"raw={source_manifest['raw_count']} "
                f"articles={manifest['article_count']} "
                f"skipped={manifest['skipped_count']} "
                f"changed={manifest['changed_count']} "
                f"jobs={manifest.get('jobs')}"
            )
        else:
            manifest = prepare_converted_run(converted_roots, run_dir)
            print(f"Prepared converted stage run: articles={manifest['article_count']}")
    pdf_diagnostics_cache_dir = _configured_optional_path(gate_config.get("pdf_diagnostics_cache_dir"))
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
            pdf_diagnostics_cache_dir=pdf_diagnostics_cache_dir,
            jobs=audit_jobs,
        )
        if audit_existing_converted:
            normalize_converted_audit_article_ids(run_dir)
        run_p62_recovery = (
            bool(gate_config.get("run_p62_image_recovery_stage", False))
            and not args.skip_p62_recovery
            and not audit_existing_converted
        )
        repair_audit_reasons: list[str] = []
        repair_audit_article_ids: set[str] = set()
        if run_p62_recovery:
            write_p62_marker_recovery_plan(run_dir, gate_config=gate_config)
            recovery_report = write_p62_image_recovery_stage(
                run_dir,
                gate_config=gate_config,
                execute_marker=bool(gate_config.get("p62_image_recovery_execute_marker", True)),
                apply_patches=bool(gate_config.get("p62_image_recovery_apply_patches", True)),
                max_items=args.p62_recovery_max_items,
                jobs=args.p62_recovery_jobs,
            )
            if int(recovery_report.get("patched_warning_count") or 0) > 0 and bool(
                gate_config.get("p62_image_recovery_rerun_audit", True)
            ):
                repair_audit_reasons.append("p62_image_recovery")
                repair_audit_article_ids.update(_patched_article_ids_from_repair_report(recovery_report))
        run_polish_auto_repair = (
            bool(gate_config.get("run_polish_auto_repair_stage", True))
            and not audit_existing_converted
        )
        if run_polish_auto_repair:
            auto_repair_report = write_polish_auto_repair_stage(
                run_dir,
                gate_config=gate_config,
                jobs=args.polish_auto_repair_jobs,
            )
            if int(auto_repair_report.get("patched_article_count") or 0) > 0 and bool(
                gate_config.get("polish_auto_repair_rerun_audit", True)
            ):
                repair_audit_reasons.append("polish_auto_repair")
                repair_audit_article_ids.update(_patched_article_ids_from_repair_report(auto_repair_report))
        if repair_audit_reasons:
            targeted_repair_audit = bool(gate_config.get("targeted_repair_audit_enabled", True))
            previous_audit_path = run_dir / "audit_full_checks.json"
            repair_audit_roots: list[Path] | None = None
            if targeted_repair_audit and previous_audit_path.is_file():
                target_roots, missing_articles = _repair_audit_roots_for_articles(run_dir, repair_audit_article_ids)
                if target_roots and not missing_articles and len(target_roots) == len(repair_audit_article_ids):
                    repair_audit_roots = target_roots
                else:
                    print(
                        "Targeted repair audit unavailable: "
                        f"targets={len(target_roots)} articles={len(repair_audit_article_ids)} "
                        f"missing={','.join(missing_articles[:8])}",
                        flush=True,
                    )
            print(
                "Deferred repair audit: "
                f"reasons={','.join(repair_audit_reasons)} "
                f"mode={'targeted' if repair_audit_roots is not None else 'full'} "
                f"articles={len(repair_audit_article_ids)}",
                flush=True,
            )
            run_audit(
                run_dir,
                roots=repair_audit_roots,
                enable_pdf_diagnostics=bool(gate_config.get("require_pdf_text_layer_diagnostics", False)),
                pdf_map_path=pdf_map_path,
                pdf_diagnostics_cache_dir=pdf_diagnostics_cache_dir,
                jobs=audit_jobs,
                merge_previous_report_path=previous_audit_path if repair_audit_roots is not None else None,
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
        help=(
            "Production converted roots or direct HTML stage files to audit without repolishing. "
            "Both _pdf_html_polish_stages and legacy _z2m_stages are recognized."
        ),
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
    observe_parser.add_argument(
        "--jobs",
        type=int,
        help=(
            "Default number of parallel article workers for document stages. "
            "Stage-specific --repolish-jobs/--audit-jobs override it."
        ),
    )
    observe_parser.add_argument(
        "--repolish-jobs",
        type=int,
        help="Parallel article workers for cached raw repolish.",
    )
    observe_parser.add_argument(
        "--audit-jobs",
        type=int,
        help="Parallel article workers for audit analysis.",
    )
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
    observe_parser.add_argument(
        "--p62-recovery-jobs",
        type=int,
        help="Article-level worker count for the P62 image recovery stage; defaults to gate config.",
    )
    observe_parser.add_argument(
        "--polish-auto-repair-jobs",
        type=int,
        help="Article-level worker count for the polish auto-repair stage; defaults to gate config.",
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
    recover_parser.add_argument(
        "--jobs",
        type=int,
        help="Article-level worker count for P62 image recovery; defaults to gate config.",
    )
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
            jobs=args.jobs,
        )
        if args.rerun_audit and int(report.get("patched_warning_count") or 0) > 0:
            pdf_map_path = args.run_dir / DEFAULT_SOURCE_PDF_MAP_NAME
            run_audit(
                args.run_dir,
                enable_pdf_diagnostics=bool(gate_config.get("require_pdf_text_layer_diagnostics", False)),
                pdf_map_path=pdf_map_path if pdf_map_path.is_file() else None,
                pdf_diagnostics_cache_dir=_configured_optional_path(gate_config.get("pdf_diagnostics_cache_dir")),
                jobs=int(gate_config.get("audit_jobs") or 1),
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
