#!/usr/bin/env python
"""Orchestrate LLM-assisted EN polish quality loops.

The script is intentionally conservative: it prepares reproducible run
artifacts, evaluates quality gates, and builds compact LLM analysis packets.
Actual code edits still happen through a human/agent review step unless an
external LLM command is explicitly supplied.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.single_file_html import close_katex_v8_context, polish_html_document  # noqa: E402


RAW_STAGE = "01.en.raw.html"
POLISH_STAGE = "02.en.polish.html"
DEFAULT_GATE_CONFIG = ROOT / "configs" / "llm_quality_gates.json"
DEFAULT_DEFECT_PATTERNS = ROOT / "configs" / "llm_defect_patterns.json"

HREF_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*([\"'])(?P<href>.*?)\1", re.IGNORECASE | re.DOTALL)
ID_RE = re.compile(r"\bid\s*=\s*([\"'])(?P<id>.*?)\1", re.IGNORECASE | re.DOTALL)
SUP_REF_RE = re.compile(
    r"<sup\b[^>]*>[\s\S]{0,500}?href\s*=\s*[\"']#ref-\d+[\"'][\s\S]{0,500}?</sup>",
    re.IGNORECASE,
)
REF_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*[\"']#ref-\d+[\"'][^>]*>(?P<body>[\s\S]{0,120}?)</a>",
    re.IGNORECASE,
)
MISSING_WARNING_CLASS_RE = re.compile(
    r"\bclass\s*=\s*([\"'])(?=[^\"']*\bz2m-missing)[^\"']*\1",
    re.IGNORECASE,
)


def _load_json(path: Path, default: Any | None = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_short_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def _git_dirty() -> bool:
    try:
        return bool(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).strip())
    except Exception:
        return True


def _profile_value(profile: dict[str, Any], key: str, default: str = "") -> str:
    return str(profile.get(key) or default)


def assess_polish_html(article: str, html: str, profile: dict[str, Any]) -> dict[str, Any]:
    ids = {match.group("id") for match in ID_RE.finditer(html)}
    href_counts: dict[str, int] = {}
    broken_targets: list[str] = []
    for match in HREF_RE.finditer(html):
        href = match.group("href")
        if href.startswith("#ref-"):
            href_counts["ref_links"] = href_counts.get("ref_links", 0) + 1
        if href.startswith("#fig-"):
            href_counts["fig_links"] = href_counts.get("fig_links", 0) + 1
        if href.startswith("#table-"):
            href_counts["table_links"] = href_counts.get("table_links", 0) + 1
        if href.startswith("#page-"):
            href_counts["page_links"] = href_counts.get("page_links", 0) + 1
            href_counts["internal_page_anchor_links"] = href_counts.get("internal_page_anchor_links", 0) + 1
        if "?page=" in href:
            href_counts["external_page_query_links"] = href_counts.get("external_page_query_links", 0) + 1
        if href.startswith("#") and href[1:] not in ids:
            href_counts["broken_internal_links"] = href_counts.get("broken_internal_links", 0) + 1
            broken_targets.append(href[1:])

    sup_ref_links = len(SUP_REF_RE.findall(html))
    bracket_ref_links = sum(
        1
        for ref_match in REF_ANCHOR_RE.finditer(html)
        if "[" in ref_match.group("body") and "]" in ref_match.group("body")
    )
    return {
        "article": article,
        "profile_style": _profile_value(profile, "style"),
        "profile_confidence": _profile_value(profile, "confidence"),
        "profile_status": _profile_value(profile, "status"),
        "href_counts": dict(sorted(href_counts.items())),
        "broken_targets": sorted(set(broken_targets)),
        "table_units_with_section_ids": 0,
        "sup_ref_links": sup_ref_links,
        "bracket_ref_links": bracket_ref_links,
        "mixed_citation_style": bool(sup_ref_links and bracket_ref_links),
        "missing_warning_count": len(MISSING_WARNING_CLASS_RE.findall(html)),
    }


def _assessment_totals(articles: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, list[str]]]:
    totals: dict[str, int] = {}
    problematic: dict[str, list[str]] = {}
    for article in articles:
        article_id = str(article["article"])
        href_counts = article.get("href_counts") if isinstance(article.get("href_counts"), dict) else {}
        for key, value in href_counts.items():
            totals[key] = totals.get(key, 0) + int(value)
            if value:
                problematic.setdefault(key, []).append(article_id)
        for key in ("table_units_with_section_ids", "sup_ref_links", "bracket_ref_links", "missing_warning_count"):
            totals[key] = totals.get(key, 0) + int(article.get(key) or 0)
        if article.get("mixed_citation_style"):
            problematic.setdefault("mixed_citation_style", []).append(article_id)
    return dict(sorted(totals.items())), {key: sorted(value) for key, value in sorted(problematic.items())}


def repolish_cached_run(source_run_dir: Path, out_dir: Path) -> dict[str, Any]:
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
    profile_status_counts: dict[str, int] = {}
    profile_style_counts: dict[str, int] = {}
    changed_count = 0

    try:
        raw_files = sorted(raw_source_dir.glob(f"*.{RAW_STAGE}"))
        for index, raw_path in enumerate(raw_files, start=1):
            article = raw_path.name.removesuffix(f".{RAW_STAGE}")
            profile_path = profile_source_dir / f"{article}.citation_profile.json"
            profile = (
                _load_json(profile_path)
                if profile_path.is_file()
                else {"status": "missing_profile", "style": "unknown", "confidence": "low"}
            )
            raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
            polished = polish_html_document(
                raw_html,
                table_caption_language="en",
                enable_citation_linkify=True,
                citation_profile=profile,
            )

            out_raw = raw_out / raw_path.name
            out_profile = profile_out / f"{article}.citation_profile.json"
            out_polish = polish_out / f"{article}.{POLISH_STAGE}"
            shutil.copy2(raw_path, out_raw)
            if profile_path.is_file():
                shutil.copy2(profile_path, out_profile)
            else:
                _write_json(out_profile, profile)
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
                }
            )
            assessments.append(assess_polish_html(article, polished, profile))
    finally:
        close_katex_v8_context()

    totals, problematic = _assessment_totals(assessments)
    manifest = {
        "generated_at": _now(),
        "source_run_dir": str(source_run_dir),
        "out_dir": str(out_dir),
        "code_commit": _git_short_head(),
        "working_tree_dirty": _git_dirty(),
        "article_count": len(articles),
        "changed_count": changed_count,
        "raw_cache_dir": str(raw_out),
        "profile_dir": str(profile_out),
        "polish_dir": str(polish_out),
        "audit_tree_dir": str(audit_tree),
        "profile_status_counts": dict(sorted(profile_status_counts.items())),
        "profile_style_counts": dict(sorted(profile_style_counts.items())),
        "articles": articles,
    }
    assessment = {
        "generated_at": _now(),
        "article_count": len(assessments),
        "run_dir": str(out_dir),
        "code_commit": _git_short_head(),
        "working_tree_dirty": _git_dirty(),
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
    return _load_json(path)


def evaluate_quality_gate(comparison: dict[str, Any], gate_config: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    status = str(comparison.get("status") or "")
    if status == "no_previous_entry":
        if not gate_config.get("allow_missing_previous", False):
            failures.append({"kind": "missing_previous", "message": "No previous quality entry was available."})
    elif status != "ok":
        failures.append({"kind": "comparison_status", "status": status})

    regressions = list(comparison.get("regressions") or [])
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

    totals_delta = comparison.get("totals_delta") if isinstance(comparison.get("totals_delta"), dict) else {}
    for metric, limit in dict(gate_config.get("max_total_deltas") or {}).items():
        observed = float(totals_delta.get(metric, 0) or 0)
        if observed > float(limit):
            failures.append({"kind": "total_delta", "metric": metric, "observed": observed, "limit": limit})

    article_limits = dict(gate_config.get("max_article_deltas") or {})
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

    return {
        "generated_at": _now(),
        "status": "fail" if failures else "pass",
        "failures": failures,
        "regression_count": len(regressions),
        "improvement_count": len(comparison.get("improvements") or []),
        "totals_delta": totals_delta,
    }


def _defect_summary(defect: dict[str, Any], defect_patterns: dict[str, Any]) -> dict[str, Any]:
    defect_id = str(defect.get("id") or "unknown")
    pattern = defect_patterns.get(defect_id) if isinstance(defect_patterns.get(defect_id), dict) else {}
    return {
        "id": defect_id,
        "severity": defect.get("severity"),
        "check": defect.get("check"),
        "snippet": defect.get("snippet"),
        "hypothesis": defect.get("hypothesis"),
        "proposed_fix_layer": defect.get("proposed_fix_layer"),
        "regression_test": defect.get("regression_test"),
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
    deltas = _comparison_by_article(comparison)
    assessment_by_article = {
        str(article.get("article")): article
        for article in assessment.get("articles", [])
        if article.get("article")
    }
    entry_articles = entry.get("articles") if isinstance(entry.get("articles"), dict) else {}

    candidates: list[dict[str, Any]] = []
    for article in audit.get("articles", []):
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        defects = [
            defect
            for defect in article.get("defects_found", [])
            if str(defect.get("id") or "") not in ignored
        ]
        record = entry_articles.get(article_id, {}) if isinstance(entry_articles, dict) else {}
        score = float(record.get("score", 0) or 0)
        if not defects and article_id not in deltas:
            continue
        candidates.append(
            {
                "article": article_id,
                "score": score,
                "non_ignored_defect_count": len(defects),
                "defects": defects,
                "audit_summary": article.get("summary", {}),
                "assessment": assessment_by_article.get(article_id, {}),
                "history_record": record,
                "comparison": deltas.get(article_id, {}),
                "raw_stage_path": article.get("raw_stage_path"),
                "polish_stage_path": article.get("polish_stage_path"),
            }
        )

    candidates.sort(
        key=lambda item: (
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
                "score": item["score"],
                "non_ignored_defect_count": item["non_ignored_defect_count"],
                "defect_ids": dict(sorted(defect_ids.items())),
                "comparison": item["comparison"],
                "labels": item["history_record"].get("labels", {}),
                "metrics": item["history_record"].get("metrics", {}),
                "assessment": item["assessment"],
                "audit_summary": item["audit_summary"],
                "raw_stage_path": item["raw_stage_path"],
                "polish_stage_path": item["polish_stage_path"],
                "defects": [_defect_summary(defect, defect_patterns) for defect in item["defects"][:12]],
            }
        )

    return {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "run_id": entry.get("run_id") or run_dir.name,
        "code_commit": manifest.get("code_commit"),
        "ignored_defect_ids": sorted(ignored),
        "article_count": manifest.get("article_count") or assessment.get("article_count"),
        "quality_totals": entry.get("totals", {}),
        "assessment_totals": assessment.get("totals", {}),
        "comparison_status": comparison.get("status"),
        "comparison_totals_delta": comparison.get("totals_delta", {}),
        "regression_count": len(comparison.get("regressions") or []),
        "improvement_count": len(comparison.get("improvements") or []),
        "audit_defect_counts": audit.get("corpus_summary", {}).get("defect_counts", {}),
        "articles": articles,
    }


def render_llm_prompt(pack: dict[str, Any]) -> str:
    lines = [
        "# EN Polish LLM Quality Review",
        "",
        "You are reviewing a pdf-html-translator EN polish experiment.",
        "Ignore defect ids listed in `ignored_defect_ids` unless they interact with a text/link problem.",
        "Classify universal root causes, propose the smallest code layer to fix them, and name regression tests.",
        "Do not propose broad rewrites when a local repair or guard is enough.",
        "",
        "Return this structure:",
        "1. Critical findings by article.",
        "2. Cross-article patterns.",
        "3. Patch plan with production file/function targets.",
        "4. Tests to add or update.",
        "5. Risks and gate checks to rerun.",
        "",
        "## Run Summary",
        f"- run_id: `{pack.get('run_id')}`",
        f"- run_dir: `{pack.get('run_dir')}`",
        f"- code_commit: `{pack.get('code_commit')}`",
        f"- ignored_defect_ids: `{', '.join(pack.get('ignored_defect_ids') or [])}`",
        f"- comparison_status: `{pack.get('comparison_status')}`",
        f"- regression_count: `{pack.get('regression_count')}`",
        f"- improvement_count: `{pack.get('improvement_count')}`",
        f"- comparison_totals_delta: `{json.dumps(pack.get('comparison_totals_delta', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Articles",
    ]
    for article in pack.get("articles", []):
        lines.extend(
            [
                "",
                f"### {article.get('article')}",
                f"- score: `{article.get('score')}`",
                f"- non_ignored_defect_count: `{article.get('non_ignored_defect_count')}`",
                f"- defect_ids: `{json.dumps(article.get('defect_ids', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- comparison: `{json.dumps(article.get('comparison', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- metrics: `{json.dumps(article.get('metrics', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- raw_stage_path: `{article.get('raw_stage_path')}`",
                f"- polish_stage_path: `{article.get('polish_stage_path')}`",
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
) -> dict[str, Any]:
    gate_config = load_gate_config(gate_config_path)
    defect_patterns = _load_json(defect_patterns_path, default={})
    pack = build_analysis_pack(
        run_dir,
        max_articles=max_articles,
        gate_config=gate_config,
        defect_patterns=defect_patterns,
        ignored_defect_ids=ignored_defect_ids,
    )
    out_json = out_json or (run_dir / "llm_analysis_pack.json")
    out_prompt = out_prompt or (run_dir / "llm_analysis_prompt.md")
    _write_json(out_json, pack)
    out_prompt.parent.mkdir(parents=True, exist_ok=True)
    out_prompt.write_text(render_llm_prompt(pack), encoding="utf-8")
    return pack


def run_audit(run_dir: Path) -> None:
    audit_tree = run_dir / "audit_tree"
    if not audit_tree.is_dir():
        raise FileNotFoundError(f"Missing audit_tree directory: {audit_tree}")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_en_polish.py"),
            "--roots",
            str(audit_tree),
            "--out",
            str(run_dir / "audit_full_checks.json"),
        ],
        cwd=ROOT,
        check=True,
    )


def run_quality_history(run_dir: Path, *, run_id: str | None, previous_entry: Path | None, no_append: bool) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "record_en_polish_quality_history.py"),
        "--run-dir",
        str(run_dir),
    ]
    if run_id:
        command.extend(["--run-id", run_id])
    if previous_entry:
        command.extend(["--previous-entry", str(previous_entry)])
    if no_append:
        command.append("--no-append")
    subprocess.run(command, cwd=ROOT, check=True)


def run_test_command(command: str, run_dir: Path) -> dict[str, Any]:
    started = _now()
    result = subprocess.run(command, cwd=ROOT, shell=True, text=True, capture_output=True)
    report = {
        "command": command,
        "started_at": started,
        "finished_at": _now(),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }
    _write_json(run_dir / "test_command_report.json", report)
    if result.returncode != 0:
        raise SystemExit(f"Test command failed with exit code {result.returncode}: {command}")
    return report


def _write_gate_report(run_dir: Path, gate_config_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    comparison = _load_json(run_dir / "quality_compare.json")
    gate_config = load_gate_config(gate_config_path)
    report = evaluate_quality_gate(comparison, gate_config)
    _write_json(out_path or (run_dir / "quality_gate_report.json"), report)
    return report


def observe(args: argparse.Namespace) -> int:
    run_dir = args.out_dir.resolve(strict=False)
    if args.source_run_dir:
        manifest = repolish_cached_run(args.source_run_dir, run_dir)
        print(f"Repolished cached run: articles={manifest['article_count']} changed={manifest['changed_count']}")
    if args.run_tests:
        gate_config = load_gate_config(args.gate_config)
        run_test_command(args.test_command or gate_config.get("required_test_command") or "python -m pytest -q", run_dir)
    if not args.skip_audit:
        run_audit(run_dir)
    if not args.skip_history:
        run_quality_history(
            run_dir,
            run_id=args.run_id,
            previous_entry=args.previous_entry,
            no_append=args.no_append_history,
        )
    gate_report = _write_gate_report(run_dir, args.gate_config)
    pack = write_analysis_pack(
        run_dir,
        max_articles=args.max_articles,
        gate_config_path=args.gate_config,
        defect_patterns_path=args.defect_patterns,
        ignored_defect_ids=set(args.ignore_defect_id or []),
    )
    print(
        "LLM quality loop: "
        f"gate={gate_report['status']} articles_in_pack={len(pack['articles'])} run_dir={run_dir}"
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
    observe_parser.add_argument("--out-dir", type=Path, required=True)
    observe_parser.add_argument("--run-id")
    observe_parser.add_argument("--previous-entry", type=Path)
    observe_parser.add_argument("--gate-config", type=Path, default=DEFAULT_GATE_CONFIG)
    observe_parser.add_argument("--defect-patterns", type=Path, default=DEFAULT_DEFECT_PATTERNS)
    observe_parser.add_argument("--ignore-defect-id", action="append")
    observe_parser.add_argument("--max-articles", type=int, default=12)
    observe_parser.add_argument("--run-tests", action="store_true")
    observe_parser.add_argument("--test-command")
    observe_parser.add_argument("--skip-audit", action="store_true")
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
    pack_parser.add_argument("--ignore-defect-id", action="append")
    pack_parser.add_argument("--max-articles", type=int, default=12)

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
        )
        print(f"LLM analysis pack: articles={len(pack['articles'])} run_dir={args.run_dir}")
        return 0
    if args.command == "run-llm":
        command = list(args.llm_command)
        if command and command[0] == "--":
            command = command[1:]
        return run_llm_command(args.prompt, args.out, command)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
