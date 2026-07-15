"""Resolver decisions for observed quality-loop audit signals."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .observations import compact_observation_text
from .run_utils import json_object, load_json, now, write_json


BENIGN_TELEMETRY_DEFECT_IDS = {"P04T", "P04M", "P45S", "P45M"}
PDF_REFERENCE_RECOVERY_DEFECT_IDS = {"P04N"}
PDF_FIGURE_RECOVERY_DEFECT_IDS = {"P62"}
SEMANTIC_FIGURE_TARGET_DEFECT_IDS = {"P61"}
SOURCE_LAYER_TELEMETRY_DEFECT_IDS = {"P35", "P71"}
REPAIR_RESOLVER_DECISION_NAMES = {
    "needs_pdf_recovery",
    "needs_semantic_recovery",
    "needs_pdf_reference_recovery",
}
ARTICLE_SLOT_REPAIR_DECISION_NAMES = {
    "needs_semantic_recovery",
    "needs_pdf_reference_recovery",
    "needs_manual_or_llm",
}


def defect_extra(defect: dict[str, Any]) -> dict[str, Any]:
    extra = defect.get("extra")
    return extra if isinstance(extra, dict) else {}


def defect_quality_counted(defect: dict[str, Any]) -> bool:
    extra = defect_extra(defect)
    return bool(extra.get("quality_counted", True))


def has_source_pdf_text_layer_evidence(defect: dict[str, Any], article_summary: dict[str, Any]) -> bool:
    extra = defect_extra(defect)
    if any("source_pdf_text_layer" in str(key) and value for key, value in extra.items()):
        return True
    return (
        str(article_summary.get("pdf_text_status") or "").lower() not in {"", "missing", "unavailable", "error"}
        and bool(article_summary.get("source_pdf_present"))
    )


def resolver_decision_for_defect(
    defect: dict[str, Any],
    article_summary: dict[str, Any],
) -> tuple[str, str, str, list[str]]:
    defect_id = str(defect.get("id") or "unknown")
    extra = defect_extra(defect)
    if defect_quality_counted(defect):
        return (
            "needs_repair",
            "quality_counted_defect",
            str(defect.get("proposed_fix_layer") or "audit_or_polish_repair"),
            ["quality_counted=true", "focused regression test", "fresh full observe comparison"],
        )
    if defect_id in BENIGN_TELEMETRY_DEFECT_IDS:
        return (
            "accepted_telemetry",
            "benign_classifier_telemetry",
            "audit_telemetry_split",
            ["quality_counted=false", "audit extra subtype", "negative guard test"],
        )
    if defect_id in SOURCE_LAYER_TELEMETRY_DEFECT_IDS and has_source_pdf_text_layer_evidence(defect, article_summary):
        return (
            "accepted_telemetry",
            "source_pdf_text_layer_evidence",
            "source_layer_ocr_telemetry",
            ["quality_counted=false", "source PDF text-layer evidence", "stage snippet"],
        )
    if defect_id in PDF_FIGURE_RECOVERY_DEFECT_IDS:
        origin = str(extra.get("warning_origin") or extra.get("p62_subtype") or "missing_figure_warning")
        return (
            "needs_pdf_recovery",
            origin,
            "pdf_backed_figure_image_recovery",
            ["source PDF page render", "nearby caption/label evidence", "image extraction fallback test"],
        )
    if defect_id in SEMANTIC_FIGURE_TARGET_DEFECT_IDS:
        return (
            "needs_semantic_recovery",
            "figure_reference_without_semantic_target",
            "semantic_figure_target_inventory_after_pdf_recovery",
            ["visible label", "figure/table target inventory", "source PDF page render"],
        )
    if defect_id in PDF_REFERENCE_RECOVERY_DEFECT_IDS:
        return (
            "needs_pdf_reference_recovery",
            "citation_like_body_numbers_without_bibliography_targets",
            "pdf_backed_bibliography_target_recovery",
            ["citation-like number group", "source PDF reference entries", "reference-link regression test"],
        )
    return (
        "needs_manual_or_llm",
        "unclassified_observed_signal",
        "manual_or_evidence_bound_llm_triage",
        ["stage snippet", "source PDF render/text evidence", "manual observation ledger entry if new"],
    )


def resolver_sample_decision(defect: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    article_id = str(article.get("article") or "")
    article_summary = json_object(article.get("summary"))
    decision, reason, fix_layer, evidence_required = resolver_decision_for_defect(defect, article_summary)
    extra = defect_extra(defect)
    return {
        "article": article_id,
        "source_article": article.get("source_article") or article_id,
        "defect_id": str(defect.get("id") or "unknown"),
        "check": defect.get("check"),
        "severity": defect.get("severity"),
        "quality_counted": defect_quality_counted(defect),
        "decision": decision,
        "reason": reason,
        "fix_layer": fix_layer,
        "evidence_required": evidence_required,
        "snippet": compact_observation_text(defect.get("snippet"), max_len=260),
        "raw_stage_path": article.get("raw_stage_path"),
        "polish_stage_path": article.get("polish_stage_path"),
        "source_pdf_present": article_summary.get("source_pdf_present"),
        "source_pdf_path": article_summary.get("source_pdf_path"),
        "source_pdf_origin": article_summary.get("source_pdf_origin"),
        "pdf_text_status": article_summary.get("pdf_text_status"),
        "extra": {
            key: value
            for key, value in extra.items()
            if key
            in {
                "quality_counted",
                "warning_origin",
                "p62_subtype",
                "figure_label",
                "figure_key",
                "visible_label",
                "source_pdf_text_layer_evidence",
            }
        },
    }


def group_resolver_decisions(decisions: Iterable[dict[str, Any]], decision_names: set[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in decisions:
        if item.get("decision") not in decision_names:
            continue
        key = (
            str(item.get("defect_id") or "unknown"),
            str(item.get("decision") or "unknown"),
            str(item.get("fix_layer") or "unknown"),
        )
        group = groups.setdefault(
            key,
            {
                "defect_id": key[0],
                "decision": key[1],
                "fix_layer": key[2],
                "count": 0,
                "article_count": 0,
                "_articles": set(),
                "sample_decisions": [],
            },
        )
        group["count"] += 1
        group["_articles"].add(item.get("article"))
        if len(group["sample_decisions"]) < 5:
            group["sample_decisions"].append(item)
    result: list[dict[str, Any]] = []
    for group in groups.values():
        articles = sorted(str(article) for article in group.pop("_articles") if article)
        group["articles"] = articles[:50]
        group["article_count"] = len(articles)
        result.append(group)
    result.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("defect_id") or "")))
    return result


def write_resolver_decisions(
    run_dir: Path,
    *,
    output_name: str = "resolver_decisions.json",
) -> dict[str, Any]:
    """Classify observed audit signals into telemetry, repair, and triage buckets."""

    run_dir = run_dir.resolve(strict=False)
    audit = load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    manifest = load_json(run_dir / "manifest.json", default={})
    entry = load_json(run_dir / "quality_history_entry.json", default={})
    run_id = str(entry.get("run_id") or run_dir.name)
    decisions: list[dict[str, Any]] = []
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        for defect in article.get("defects_found") or []:
            if isinstance(defect, dict):
                decisions.append(resolver_sample_decision(defect, article))

    decision_counts = Counter(str(item.get("decision") or "unknown") for item in decisions)
    defect_id_counts = Counter(str(item.get("defect_id") or "unknown") for item in decisions)
    accepted_telemetry_counts = Counter(
        str(item.get("defect_id") or "unknown")
        for item in decisions
        if item.get("decision") == "accepted_telemetry"
    )
    repair_candidate_counts = Counter(
        str(item.get("defect_id") or "unknown")
        for item in decisions
        if item.get("decision") in REPAIR_RESOLVER_DECISION_NAMES
    )
    manual_or_llm_count = int(decision_counts.get("needs_manual_or_llm", 0))
    report = {
        "generated_at": now(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "path": str(run_dir / output_name),
        "source_kind": manifest.get("source_kind"),
        "code_commit": manifest.get("code_commit"),
        "working_tree_dirty": manifest.get("working_tree_dirty"),
        "decision_count": len(decisions),
        "article_count": len({item.get("article") for item in decisions if item.get("article")}),
        "observed_non_quality_count": sum(1 for item in decisions if not item.get("quality_counted")),
        "quality_counted_count": sum(1 for item in decisions if item.get("quality_counted")),
        "decision_counts": dict(sorted(decision_counts.items())),
        "defect_id_counts": dict(sorted(defect_id_counts.items())),
        "accepted_telemetry_counts": dict(sorted(accepted_telemetry_counts.items())),
        "repair_candidate_counts": dict(sorted(repair_candidate_counts.items())),
        "manual_or_llm_count": manual_or_llm_count,
        "repair_candidate_groups": group_resolver_decisions(decisions, REPAIR_RESOLVER_DECISION_NAMES),
        "accepted_telemetry_groups": group_resolver_decisions(decisions, {"accepted_telemetry"}),
        "manual_or_llm_groups": group_resolver_decisions(decisions, {"needs_manual_or_llm"}),
        "automation_plan": [
            {
                "order": 1,
                "scope": "P04T/P04M/P45S/P45M",
                "action": "Keep benign table/math/superscript classifiers as accepted telemetry with negative guard tests.",
                "status": "implemented_in_resolver",
            },
            {
                "order": 2,
                "scope": "P62",
                "action": "Use PDF-render evidence for missing figure/image recovery before semantic target repair.",
                "status": "repair_candidate",
            },
            {
                "order": 3,
                "scope": "P61",
                "action": "Rebuild semantic figure target inventory after PDF-backed figure recovery.",
                "status": "repair_candidate",
            },
            {
                "order": 4,
                "scope": "P04N",
                "action": "Recover source-backed bibliography targets from citation-like body ranges/lists and PDF reference entries.",
                "status": "active_repair_layer",
            },
            {
                "order": 5,
                "scope": "P71/P35",
                "action": "Accept source-layer OCR/mojibake residues only when source PDF text-layer evidence is present.",
                "status": "implemented_in_resolver",
            },
        ],
        "decisions": decisions,
    }
    write_json(run_dir / output_name, report)
    return report
