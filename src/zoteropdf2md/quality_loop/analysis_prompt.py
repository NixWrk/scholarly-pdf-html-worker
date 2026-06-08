"""LLM prompt rendering for quality-loop analysis packs."""

from __future__ import annotations

from typing import Any
import json


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
