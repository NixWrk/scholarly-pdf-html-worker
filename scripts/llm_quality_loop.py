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
import os
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
SUP_BLOCK_RE = re.compile(r"<sup\b[^>]*>[\s\S]{0,500}?</sup>", re.IGNORECASE)
REF_HREF_RE = re.compile(r"\bhref\s*=\s*[\"']#ref-\d+[\"']", re.IGNORECASE)
REF_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*[\"']#ref-\d+[\"'][^>]*>(?P<body>[\s\S]{0,120}?)</a>",
    re.IGNORECASE,
)
MISSING_WARNING_CLASS_RE = re.compile(
    r"\bclass\s*=\s*([\"'])(?=[^\"']*\bz2m-missing)[^\"']*\1",
    re.IGNORECASE,
)


def _slug(value: str, *, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned or "article")[:max_len]


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


def _article_dir_from_stage(stage_path: Path) -> Path:
    return stage_path.parent.parent if stage_path.parent.name == "_z2m_stages" else stage_path.parent


def _article_name_from_stage(stage_path: Path) -> str:
    return _article_dir_from_stage(stage_path).name


def _artifact_hint(stage_path: Path, *, depth: int = 5) -> str:
    return str(Path(*stage_path.parts[-depth:])) if len(stage_path.parts) >= depth else str(stage_path)


def _norm_path(value: Any) -> str:
    return str(Path(str(value)).resolve(strict=False)) if value else ""


def _converted_article_id(raw_path: Path, index: int) -> str:
    article_dir = _article_dir_from_stage(raw_path)
    parent = article_dir.parent.name if article_dir.parent != article_dir else ""
    attachment = article_dir.parent.parent.name if article_dir.parent.parent != article_dir.parent else ""
    prefix = "_".join(part for part in (_slug(attachment, max_len=12), _slug(parent, max_len=24)) if part)
    suffix = _slug(article_dir.name, max_len=72)
    return f"{index:03d}_{prefix}_{suffix}" if prefix else f"{index:03d}_{suffix}"


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

    sup_ref_links = sum(1 for sup_match in SUP_BLOCK_RE.finditer(html) if REF_HREF_RE.search(sup_match.group(0)))
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


def find_converted_stage_pairs(roots: Iterable[Path]) -> list[tuple[Path, Path]]:
    """Find existing production ``01.en.raw.html`` -> ``02.en.polish.html`` pairs."""

    pairs: set[tuple[Path, Path]] = set()
    for root in roots:
        if root.is_file():
            if root.name == RAW_STAGE and (root.parent / POLISH_STAGE).is_file():
                pairs.add((root.resolve(strict=False), (root.parent / POLISH_STAGE).resolve(strict=False)))
            elif root.name == POLISH_STAGE and (root.parent / RAW_STAGE).is_file():
                pairs.add(((root.parent / RAW_STAGE).resolve(strict=False), root.resolve(strict=False)))
        elif root.exists():
            for polish_path in root.rglob(POLISH_STAGE):
                raw_path = polish_path.parent / RAW_STAGE
                if raw_path.is_file():
                    pairs.add((raw_path.resolve(strict=False), polish_path.resolve(strict=False)))
    return sorted(pairs, key=lambda pair: str(pair[1]))


def prepare_converted_run(roots: list[Path], out_dir: Path) -> dict[str, Any]:
    """Prepare a loop run from existing Zotero converted stage directories.

    The audit still reads the original stage paths so local sidecar images and
    source PDFs resolve naturally.  Article ids are made unique in the loop
    artifacts because production converted trees can contain duplicate document
    names under different attachment/mtime directories.
    """

    out_dir = out_dir.resolve(strict=False)
    out_dir.mkdir(parents=True, exist_ok=True)
    roots = [root.resolve(strict=False) for root in roots]
    pairs = find_converted_stage_pairs(roots)
    articles: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    profile = {"status": "not_applicable_converted_stage", "style": "unknown", "confidence": "low"}
    for index, (raw_path, polish_path) in enumerate(pairs, start=1):
        article = _article_name_from_stage(raw_path)
        article_id = _converted_article_id(raw_path, index)
        polish_html = polish_path.read_text(encoding="utf-8", errors="replace")
        articles.append(
            {
                "index": index,
                "article_id": article_id,
                "article": article,
                "article_dir": str(_article_dir_from_stage(raw_path)),
                "raw_stage_path": str(raw_path),
                "polish_stage_path": str(polish_path),
                "artifact_hint": _artifact_hint(raw_path),
            }
        )
        assessment = assess_polish_html(article_id, polish_html, profile)
        assessment["source_article"] = article
        assessment["raw_stage_path"] = str(raw_path)
        assessment["polish_stage_path"] = str(polish_path)
        assessment["artifact_hint"] = _artifact_hint(raw_path)
        assessments.append(assessment)

    totals, problematic = _assessment_totals(assessments)
    profile_status_counts = {profile["status"]: len(articles)} if articles else {}
    profile_style_counts = {f"{profile['style']}:{profile['confidence']}": len(articles)} if articles else {}
    manifest = {
        "generated_at": _now(),
        "source_kind": "converted_stage_roots",
        "source_roots": [str(root) for root in roots],
        "out_dir": str(out_dir),
        "code_commit": _git_short_head(),
        "working_tree_dirty": _git_dirty(),
        "article_count": len(articles),
        "profile_status_counts": profile_status_counts,
        "profile_style_counts": profile_style_counts,
        "articles": articles,
    }
    assessment = {
        "generated_at": _now(),
        "source_kind": "converted_stage_roots",
        "article_count": len(assessments),
        "run_dir": str(out_dir),
        "code_commit": _git_short_head(),
        "working_tree_dirty": _git_dirty(),
        "totals": totals,
        "profile_status_counts": profile_status_counts,
        "profile_style_counts": profile_style_counts,
        "problematic_articles": problematic,
        "articles": assessments,
    }
    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "assessment.json", assessment)
    return manifest


def _manifest_article_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    articles: dict[str, dict[str, Any]] = {}
    for article in manifest.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = article.get("article_id") or article.get("article")
        if article_id:
            articles[str(article_id)] = article
    return articles


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


def repolish_cached_run(source_run_dir: Path, out_dir: Path, *, polish_language: str | None = None) -> dict[str, Any]:
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
                polish_language=polish_language,
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
        "polish_language": polish_language or "en",
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
                "raw_stage_path": raw_stage_path,
                "polish_stage_path": polish_stage_path,
                **review_state,
            }
        )

    queue.sort(
        key=lambda item: (
            -float(item.get("score") or 0),
            -int(item.get("non_ignored_defect_count") or 0),
            -int(item.get("defect_count") or 0),
            str(item.get("article") or ""),
        )
    )
    _write_json(run_dir / "manual_review_queue.json", queue)
    return queue


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
    manifest_by_article = _manifest_article_by_id(manifest)
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
        assessment_article = assessment_by_article.get(article_id, {})
        manifest_article = manifest_by_article.get(article_id, {})
        score = float(record.get("score", 0) or 0)
        if not defects and article_id not in deltas:
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
                "defects": defects,
                "audit_summary": article.get("summary", {}),
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
                f"- defect_ids: `{json.dumps(article.get('defect_ids', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- comparison: `{json.dumps(article.get('comparison', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- metrics: `{json.dumps(article.get('metrics', {}), ensure_ascii=False, sort_keys=True)}`",
                f"- artifact_hint: `{article.get('artifact_hint')}`",
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


def run_audit(run_dir: Path, roots: Iterable[Path] | None = None) -> None:
    audit_roots = [root.resolve(strict=False) for root in roots] if roots else [run_dir / "audit_tree"]
    if not audit_roots:
        raise ValueError("No audit roots supplied.")
    missing_roots = [root for root in audit_roots if not root.exists()]
    if missing_roots:
        raise FileNotFoundError(f"Missing audit root(s): {', '.join(str(root) for root in missing_roots)}")
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    started = _now()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_en_polish.py"),
            "--roots",
            *[str(root) for root in audit_roots],
            "--out",
            str(run_dir / "audit_full_checks.json"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )
    _write_json(
        run_dir / "audit_command_report.json",
        {
            "roots": [str(root) for root in audit_roots],
            "started_at": started,
            "finished_at": _now(),
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
        },
    )
    if result.returncode != 0:
        raise SystemExit(f"Audit command failed with exit code {result.returncode}. See {run_dir / 'audit_command_report.json'}")


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
    converted_roots = list(args.converted_roots or [])
    if args.source_run_dir and converted_roots:
        raise SystemExit("Use either --source-run-dir or --converted-roots, not both.")
    if args.source_run_dir:
        manifest = repolish_cached_run(args.source_run_dir, run_dir, polish_language=args.polish_language)
        print(f"Repolished cached run: articles={manifest['article_count']} changed={manifest['changed_count']}")
    elif converted_roots:
        manifest = prepare_converted_run(converted_roots, run_dir)
        print(f"Prepared converted stage run: articles={manifest['article_count']}")
    if args.run_tests:
        gate_config = load_gate_config(args.gate_config)
        run_test_command(args.test_command or gate_config.get("required_test_command") or "python -m pytest -q", run_dir)
    if not args.skip_audit:
        run_audit(run_dir, roots=converted_roots if converted_roots else None)
        if converted_roots:
            normalize_converted_audit_article_ids(run_dir)
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
        f"gate={gate_report['status']} review_queue={len(review_queue)} "
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
        choices=("en", "ru"),
        help="Language policy for language-specific polish repairs when repolishing a cached run.",
    )
    observe_parser.add_argument(
        "--converted-roots",
        nargs="+",
        type=Path,
        help="Production converted roots or direct _z2m_stages files to audit without repolishing.",
    )
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
