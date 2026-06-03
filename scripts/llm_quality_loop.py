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
from html import escape, unescape
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.single_file_html import (  # noqa: E402
    _to_data_url,
    _validate_data_url,
    close_katex_v8_context,
    polish_html_document,
)
from zoteropdf2md.citation_profile import (  # noqa: E402
    extract_reference_entries_from_pdf,
    infer_citation_style_from_text,
)
from zoteropdf2md.marker_runner import build_marker_single_command  # noqa: E402
from zoteropdf2md.polish_language import resolve_document_polish_language  # noqa: E402


RAW_STAGE = "01.en.raw.html"
POLISH_STAGE = "02.en.polish.html"
DEFAULT_GATE_CONFIG = ROOT / "configs" / "llm_quality_gates.json"
DEFAULT_DEFECT_PATTERNS = ROOT / "configs" / "llm_defect_patterns.json"
DEFAULT_PATTERN_HISTORY_NAME = "pattern_observation_history.jsonl"
DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME = "manual_observation_ledger.jsonl"
DEFAULT_SOURCE_PDF_MAP_NAME = "source_pdf_map.json"
DEFAULT_PDF_PROBLEM_EVIDENCE_NAME = "pdf_problem_evidence_report.json"
DEFAULT_RESOLVER_DECISIONS_NAME = "resolver_decisions.json"
DEFAULT_P62_MARKER_RECOVERY_PLAN_NAME = "p62_marker_recovery_plan.json"
DEFAULT_P62_IMAGE_RECOVERY_REPORT_NAME = "p62_image_recovery_report.json"

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
IMG_SRC_RE = re.compile(r"(<img\b[^>]*?\bsrc\s*=\s*)(['\"])(?P<src>.*?)(\2)", re.IGNORECASE | re.DOTALL)
DATA_Z2M_SRC_RE = re.compile(r"\bdata-z2m-src\s*=\s*(['\"])(?P<src>.*?)\1", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BRACKET_NUMERIC_REF_TEXT_RE = re.compile(r"^\[\s*\d+(?:\s*(?:,|;|-|\u2013)\s*\d+)*\s*\]$")
REFERENCE_NUMBER_BRACKET_RE = re.compile(
    r"\breference\s+number\s*\[\s*\d+(?:\s*(?:,|;|-|\u2013)\s*\d+)*\s*\]",
    re.IGNORECASE,
)
DATA_AVAILABILITY_CONTEXT_RE = re.compile(
    r"\b(?:data\s+availability|openly\s+available|available\s+in\s+the|repository|datasets?)\b",
    re.IGNORECASE,
)
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


def _converted_article_id(raw_path: Path, index: int | None = None) -> str:
    article_dir = _article_dir_from_stage(raw_path)
    version = article_dir.parent.name if article_dir.parent != article_dir else ""
    attachment = article_dir.parent.parent.name if article_dir.parent.parent != article_dir.parent else ""
    library = (
        article_dir.parent.parent.parent.name
        if article_dir.parent.parent.parent != article_dir.parent.parent
        else ""
    )
    prefix = "_".join(
        part
        for part in (
            _slug(library, max_len=14),
            _slug(attachment, max_len=10),
            _slug(version, max_len=22),
        )
        if part
    )
    suffix = _slug(article_dir.name, max_len=72)
    return f"{prefix}_{suffix}" if prefix else suffix


def _html_plain_text_for_profile(html: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6]|table|section|article)>", "\n", text)
    text = TAG_RE.sub(" ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _visible_html_text(fragment: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", " ", fragment)
    text = TAG_RE.sub(" ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _is_data_availability_reference_number(ref_match: re.Match[str], html: str) -> bool:
    body_text = _visible_html_text(ref_match.group("body"))
    if not BRACKET_NUMERIC_REF_TEXT_RE.fullmatch(body_text):
        return False
    prefix = _visible_html_text(html[max(0, ref_match.start() - 700) : ref_match.start()])
    suffix = _visible_html_text(html[ref_match.end() : min(len(html), ref_match.end() + 160)])
    near_text = f"{prefix[-500:]} {body_text} {suffix[:160]}"
    return bool(REFERENCE_NUMBER_BRACKET_RE.search(near_text) and DATA_AVAILABILITY_CONTEXT_RE.search(near_text))


def _is_bracket_ref_link_for_style(ref_match: re.Match[str], html: str) -> bool:
    body_text = _visible_html_text(ref_match.group("body"))
    if "[" not in body_text or "]" not in body_text:
        return False
    return not _is_data_availability_reference_number(ref_match, html)


def _converted_raw_citation_profile(raw_html: str, raw_path: Path) -> dict[str, Any]:
    text = _html_plain_text_for_profile(raw_html)
    inferred_style, inferred_confidence, paren_count, bracket_count = infer_citation_style_from_text(text)
    style = inferred_style if inferred_confidence == "high" else "unknown"
    confidence = inferred_confidence if inferred_confidence == "high" else "low"
    return {
        "status": "converted_raw_html_inferred",
        "style": style,
        "confidence": confidence,
        "source": "converted_raw_html",
        "source_policy": "use_inferred_style_only_when_high_confidence",
        "inferred_style": inferred_style,
        "inferred_confidence": inferred_confidence,
        "source_raw_stage_path": str(raw_path),
        "paren_numeric_count": paren_count,
        "bracket_numeric_count": bracket_count,
    }


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
        if _is_bracket_ref_link_for_style(ref_match, html)
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


def prepare_converted_raw_cache(roots: list[Path], out_dir: Path) -> dict[str, Any]:
    """Build a cached-run source directory from production converted stages.

    The generated directory is intentionally shaped like a normal cached run:
    ``raw_cache/<article>.01.en.raw.html`` plus
    ``profiles/<article>.citation_profile.json``.  It lets the loop repolish
    production raw artifacts without writing back into the Zotero converted
    tree.  The manifest keeps the original stage paths so image restoration can
    reuse already inlined production polish or local sidecar files.
    """

    out_dir = out_dir.resolve(strict=False)
    raw_cache = out_dir / "raw_cache"
    profiles = out_dir / "profiles"
    for path in (raw_cache, profiles):
        path.mkdir(parents=True, exist_ok=True)

    roots = [root.resolve(strict=False) for root in roots]
    pairs = find_converted_stage_pairs(roots)
    articles: list[dict[str, Any]] = []
    profile_status_counts: Counter[str] = Counter()
    profile_style_counts: Counter[str] = Counter()
    for index, (raw_path, polish_path) in enumerate(pairs, start=1):
        article = _article_name_from_stage(raw_path)
        article_id = _converted_article_id(raw_path, index)
        out_raw = raw_cache / f"{article_id}.{RAW_STAGE}"
        out_profile = profiles / f"{article_id}.citation_profile.json"
        shutil.copy2(raw_path, out_raw)
        raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
        profile = _converted_raw_citation_profile(raw_html, raw_path)
        _write_json(out_profile, profile)
        profile_status_counts[profile["status"]] += 1
        profile_style_counts[f"{profile['style']}:{profile['confidence']}"] += 1
        articles.append(
            {
                "index": index,
                "article_id": article_id,
                "article": article,
                "article_dir": str(_article_dir_from_stage(raw_path)),
                "raw_stage_path": str(raw_path),
                "source_polish_path": str(polish_path),
                "polish_stage_path": str(polish_path),
                "raw_cache_path": str(out_raw),
                "profile_path": str(out_profile),
                "artifact_hint": _artifact_hint(raw_path),
                "profile_status": profile["status"],
                "citation_style": profile["style"],
                "citation_confidence": profile["confidence"],
            }
        )

    manifest = {
        "generated_at": _now(),
        "source_kind": "converted_raw_cache",
        "source_roots": [str(root) for root in roots],
        "out_dir": str(out_dir),
        "code_commit": _git_short_head(),
        "working_tree_dirty": _git_dirty(),
        "raw_count": len(articles),
        "article_count": len(articles),
        "raw_cache_dir": str(raw_cache),
        "profile_dir": str(profiles),
        "profile_status_counts": dict(sorted(profile_status_counts.items())),
        "profile_style_counts": dict(sorted(profile_style_counts.items())),
        "articles": articles,
    }
    _write_json(out_dir / "manifest.json", manifest)
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


def _configured_path_prefix_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = [
        ("/pdf_html_translator_repo", str(ROOT)),
        ("/data/html", r"D:\Elvis_projects\Zotero_automatization\data\html"),
        ("/zotero_roots/pc_zotero", r"C:\PC\Zotero"),
        ("/zotero_roots/user_zotero", r"C:\Users\ELVIS_NIX\Zotero"),
    ]
    for env_name in ("HTML_DOCKER_MOUNT_PREFIX_MAP", "ZOTERO_PATH_PREFIX_MAP"):
        for item in os.environ.get(env_name, "").split(";"):
            if "=" not in item:
                continue
            left, right = (part.strip() for part in item.split("=", 1))
            if left and right:
                pairs.append((left, right))
                pairs.append((right, left))
    return pairs


def _host_path_candidates(value: str) -> list[Path]:
    raw = value.strip()
    if not raw:
        return []
    candidates = [Path(raw).resolve(strict=False)]
    normalized = raw.replace("\\", "/")
    for source_prefix, target_prefix in _configured_path_prefix_pairs():
        source_norm = source_prefix.replace("\\", "/").rstrip("/")
        if normalized == source_norm or normalized.startswith(source_norm + "/"):
            suffix = normalized[len(source_norm) :].lstrip("/")
            candidates.append((Path(target_prefix) / Path(*suffix.split("/"))).resolve(strict=False))
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def _collect_pdf_path_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_lower = str(key).lower()
            if isinstance(nested, str) and (
                key_lower in {"source_pdf", "source_pdf_path", "pdf_path", "overlay_source_pdf", "source_path", "path"}
                or "pdf" in key_lower
            ):
                if nested.lower().split("?", 1)[0].endswith(".pdf"):
                    found.append(nested)
            found.extend(_collect_pdf_path_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_collect_pdf_path_strings(nested))
    elif isinstance(value, str) and value.lower().split("?", 1)[0].endswith(".pdf"):
        found.append(value)
    return found


def _source_export_dirs_from_stage_related_path(value: Any) -> list[Path]:
    if not value:
        return []
    path = Path(str(value)).resolve(strict=False)
    if path.name in {RAW_STAGE, POLISH_STAGE} or path.parent.name == "_z2m_stages":
        article_dir = _article_dir_from_stage(path)
    else:
        article_dir = path
    parts = list(article_dir.parts)
    dirs: list[Path] = []
    for marker in ("source_exports", "converted", "final_exports", "translated"):
        if marker not in parts:
            continue
        idx = parts.index(marker)
        after = parts[idx + 1 :]
        if len(after) < 3:
            continue
        dirs.append(Path(*parts[:idx], "source_exports", *after[:3]).resolve(strict=False))
    return dirs


def _pdf_candidates_from_source_export_dir(source_dir: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not source_dir.is_dir():
        return candidates
    for json_path in sorted([source_dir / "manifest.json", *source_dir.glob("*_meta.json")], key=str):
        if not json_path.is_file():
            continue
        data = _load_json(json_path, default={})
        for pdf_value in _collect_pdf_path_strings(data):
            for host_path in _host_path_candidates(pdf_value):
                candidates.append(
                    {
                        "path": str(host_path),
                        "exists": host_path.is_file(),
                        "source": str(json_path),
                        "original_path": pdf_value,
                    }
                )
    return candidates


def _zotero_root_paths() -> list[Path]:
    roots: list[Path] = []
    for source_prefix, target_prefix in _configured_path_prefix_pairs():
        if "zotero" not in source_prefix.lower() and "zotero" not in target_prefix.lower():
            continue
        root = Path(target_prefix).resolve(strict=False)
        if root not in roots:
            roots.append(root)
    return roots


def _attachment_keys_from_article(article: str, manifest_article: dict[str, Any]) -> list[str]:
    keys: list[str] = []

    def add(value: str) -> None:
        if value and value not in keys:
            keys.append(value)

    for token in re.split(r"[_\\/]+", article):
        if re.fullmatch(r"[A-Z0-9]{6,10}", token) and any(ch.isdigit() for ch in token):
            add(token)
    for key in ("attachment_key", "zotero_attachment_key", "zotero_key"):
        value = manifest_article.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Z0-9]{6,10}", value):
            add(value)
    for path_key in ("raw_stage_path", "polish_stage_path", "restored_image_source"):
        value = manifest_article.get(path_key)
        if not value:
            continue
        for part in Path(str(value)).parts:
            if re.fullmatch(r"[A-Z0-9]{6,10}", part):
                add(part)
    return keys


def _pdf_candidates_from_zotero_storage(attachment_key: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not attachment_key:
        return candidates
    for root in _zotero_root_paths():
        storage_dirs = [root / "storage" / attachment_key]
        if root.is_dir():
            storage_dirs.extend(root.glob(f"*/storage/{attachment_key}"))
        for storage_dir in storage_dirs:
            if not storage_dir.is_dir():
                continue
            for pdf_path in sorted(storage_dir.glob("*.pdf"), key=str):
                candidates.append(
                    {
                        "path": str(pdf_path.resolve(strict=False)),
                        "exists": pdf_path.is_file(),
                        "source": f"zotero_storage.{attachment_key}",
                        "original_path": str(storage_dir.resolve(strict=False)),
                    }
                )
    return candidates


def _article_source_pdf_candidates(
    run_dir: Path,
    article: str,
    audit_summary: dict[str, Any],
    manifest_article: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    visited_runs: set[Path] = set()

    def add_pdf_value(value: Any, source: str) -> None:
        if not value:
            return
        for host_path in _host_path_candidates(str(value)):
            candidates.append(
                {
                    "path": str(host_path),
                    "exists": host_path.is_file(),
                    "source": source,
                    "original_path": str(value),
                }
            )

    def add_source_dirs_from_item(item: dict[str, Any]) -> None:
        for key in (
            "article_dir",
            "raw_stage_path",
            "source_polish_path",
            "polish_stage_path",
            "polish_path",
            "restored_image_source",
        ):
            for source_dir in _source_export_dirs_from_stage_related_path(item.get(key)):
                candidates.extend(_pdf_candidates_from_source_export_dir(source_dir))

    add_pdf_value(audit_summary.get("source_pdf_path"), "audit_summary.source_pdf_path")
    add_source_dirs_from_item(manifest_article)
    for key in ("source_pdf", "source_pdf_path", "pdf_path", "overlay_source_pdf"):
        add_pdf_value(manifest_article.get(key), f"manifest.{key}")
    for attachment_key in _attachment_keys_from_article(article, manifest_article):
        candidates.extend(_pdf_candidates_from_zotero_storage(attachment_key))

    def visit(source_run: Path) -> None:
        source_run = source_run.resolve(strict=False)
        if source_run in visited_runs:
            return
        visited_runs.add(source_run)
        manifest = _load_json(source_run / "manifest.json", default={})
        item = _manifest_article_for(manifest, article) or {}
        if item:
            add_source_dirs_from_item(item)
            for key in ("source_pdf", "source_pdf_path", "pdf_path", "overlay_source_pdf"):
                add_pdf_value(item.get(key), f"{source_run.name}.manifest.{key}")
            for attachment_key in _attachment_keys_from_article(article, item):
                candidates.extend(_pdf_candidates_from_zotero_storage(attachment_key))
        nested = manifest.get("source_run_dir")
        if nested:
            visit(Path(str(nested)))

    visit(run_dir)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = f"{candidate.get('path')}|{candidate.get('original_path')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    deduped.sort(key=lambda item: (not bool(item.get("exists")), str(item.get("path"))))
    return deduped[:12]


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

    run_dir = run_dir.resolve(strict=False)
    manifest = manifest or _load_json(run_dir / "manifest.json", default={})
    out_path = out_path or (run_dir / DEFAULT_SOURCE_PDF_MAP_NAME)
    records: list[dict[str, Any]] = []
    mapped: dict[str, dict[str, Any]] = {}
    for item in manifest.get("articles") or []:
        if not isinstance(item, dict):
            continue
        article = str(item.get("article_id") or item.get("article") or "")
        if not article:
            continue
        candidates = _article_source_pdf_candidates(run_dir, article, {}, item)
        selected = next((candidate for candidate in candidates if candidate.get("exists")), None)
        record = {
            "article": article,
            "source_article": item.get("article"),
            "pdf_path": selected.get("path") if selected else "",
            "source": selected.get("source") if selected else "",
            "exists": bool(selected),
            "candidate_count": len(candidates),
            "candidates": candidates,
        }
        records.append(record)
        if selected:
            mapped[article] = record

    report = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "status": "ready" if mapped else "empty",
        "article_count": len(records),
        "mapped_count": len(mapped),
        "unmapped_count": len(records) - len(mapped),
        "records": records,
    }
    _write_json(out_path, report)
    return report


def _pdf_text_pages(pdf_path: Path, *, max_pages: int | None = None) -> tuple[str, list[str], str | None]:
    if not pdf_path.is_file():
        return "missing", [], None

    errors: list[str] = []
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            limit = len(doc) if not max_pages or max_pages <= 0 else min(len(doc), max_pages)
            return "pymupdf", [doc.load_page(index).get_text("text") or "" for index in range(limit)], None
        finally:
            doc.close()
    except ImportError as exc:
        errors.append(f"pymupdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - PDF/parser specific
        errors.append(f"pymupdf failed: {exc}")

    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        pages = list(reader.pages)
        limit = len(pages) if not max_pages or max_pages <= 0 else min(len(pages), max_pages)
        return "pypdf", [pages[index].extract_text() or "" for index in range(limit)], None
    except ImportError as exc:
        errors.append(f"pypdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - PDF/parser specific
        errors.append(f"pypdf failed: {exc}")

    return "unavailable", [], "; ".join(errors)


def _tokenize_evidence_text(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", unescape(str(value)).casefold())
        if not token.isdigit()
    ]


def _best_pdf_text_page(snippets: list[str], pages: list[str]) -> tuple[int, float]:
    if not pages:
        return 0, 0.0
    snippet_tokens = _evidence_snippet_tokens(snippets)
    if not snippet_tokens:
        return 1, 0.0

    best_page = 1
    best_score = -1.0
    for index, page_text in enumerate(pages, start=1):
        page_tokens = set(_tokenize_evidence_text(page_text))
        if not page_tokens:
            score = 0.0
        else:
            score = len(snippet_tokens & page_tokens) / max(1, len(snippet_tokens))
        if score > best_score:
            best_page = index
            best_score = score
    return best_page, max(0.0, best_score)


def _evidence_snippet_tokens(snippets: list[str]) -> set[str]:
    snippet_tokens: set[str] = set()
    for snippet in snippets:
        snippet_tokens.update(_tokenize_evidence_text(snippet)[:80])
    return snippet_tokens


def _pdf_page_match_score(snippet_tokens: set[str], page_text: str) -> float:
    if not snippet_tokens:
        return 0.0
    page_tokens = set(_tokenize_evidence_text(page_text))
    if not page_tokens:
        return 0.0
    return len(snippet_tokens & page_tokens) / max(1, len(snippet_tokens))


def _figure_label_present_in_text(text: str, figure_label: str) -> bool:
    label = str(figure_label or "").strip()
    if not label:
        return False
    return bool(
        re.search(
            rf"\b(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?=\b|[^\w])",
            str(text or ""),
            re.IGNORECASE,
        )
    )


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
    if not pdf_path.is_file():
        return {"status": "missing_pdf", "path": "", "error": ""}
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number < 1 or page_number > len(doc):
                return {
                    "status": "page_out_of_range",
                    "path": "",
                    "error": f"page {page_number} outside 1..{len(doc)}",
                }
            page = doc.load_page(page_number - 1)
            matrix = fitz.Matrix(float(zoom), float(zoom))
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pixmap.save(str(out_path))
            return {"status": "rendered", "path": str(out_path), "error": ""}
        finally:
            doc.close()
    except ImportError as exc:
        return {"status": "renderer_unavailable", "path": "", "error": str(exc)}
    except Exception as exc:  # pragma: no cover - PDF/render specific
        return {"status": "render_error", "path": "", "error": str(exc)}


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
        page_number, match_score, label_pages = _best_pdf_text_page_for_figure(snippets, pages, figure_label)
        text_layer_full_retry = False
        if (
            retry_full_pdf_on_label_miss
            and require_label_match
            and figure_label
            and not label_pages
            and max_pdf_pages > 0
            and len(pages) >= max_pdf_pages
        ):
            full_cache_key = f"{pdf_path}|full"
            if full_cache_key not in pdf_text_cache:
                pdf_text_cache[full_cache_key] = _pdf_text_pages(pdf_path, max_pages=None)
            full_text_status, full_pages, full_text_error = pdf_text_cache[full_cache_key]
            full_page_number, full_match_score, full_label_pages = _best_pdf_text_page_for_figure(
                snippets,
                full_pages,
                figure_label,
            )
            if full_label_pages:
                text_status = full_text_status
                pages = full_pages
                text_error = full_text_error
                page_number = full_page_number
                match_score = full_match_score
                label_pages = full_label_pages
                text_layer_full_retry = True
        text_chars = sum(len(page_text) for page_text in pages)
        record.update(
            {
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
                    figure_label,
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


def _clean_resolved_p62_missing_unit_classes(html: str) -> str:
    def replace_unit(match: re.Match[str]) -> str:
        raw = match.group(0)
        if "z2m-missing-figure-warning" in raw:
            return raw
        open_end = raw.find(">")
        if open_end < 0:
            return raw
        open_tag = _remove_class_from_open_tag(raw[: open_end + 1], "z2m-missing-figure-unit")
        return open_tag + raw[open_end + 1 :]

    return P62_MISSING_FIGURE_UNIT_RE.sub(replace_unit, html)


def _p62_recovery_target_html(
    data_url: str,
    *,
    figure_label: str,
    source: str,
    source_detail: str,
) -> str:
    label = str(figure_label or "").strip()
    alt = f"Recovered Figure {label} visual from source PDF" if label else "Recovered figure visual from source PDF"
    return (
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img '
        f'data-z2m-src="{_escape_html_attr(source_detail)}" '
        f'data-z2m-recovery-source="{_escape_html_attr(source)}" '
        f'alt="{_escape_html_attr(alt)}" '
        f'src="{_escape_html_attr(data_url)}"/>'
        "</p>"
    )


def _replace_p62_missing_warning_with_image(
    html: str,
    *,
    figure_label: str,
    warning_index: int | None,
    data_url: str,
    source: str,
    source_detail: str,
) -> tuple[str, int]:
    matches = list(P62_MISSING_WARNING_ELEMENT_RE.finditer(html))
    if not matches:
        return html, 0

    label_matches = [
        match
        for match in matches
        if not figure_label or _figure_label_present_in_text(_visible_html_text(match.group(0)), figure_label)
    ]
    usable_matches = label_matches or matches
    if warning_index and warning_index > 0 and warning_index <= len(usable_matches):
        target = usable_matches[warning_index - 1]
    else:
        target = usable_matches[0]

    replacement = _p62_recovery_target_html(
        data_url,
        figure_label=figure_label,
        source=source,
        source_detail=source_detail,
    )
    patched = html[: target.start()] + replacement + html[target.end() :]
    return _clean_resolved_p62_missing_unit_classes(patched), 1


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
    if not path.is_file():
        return None
    data_url = _to_data_url(path, detect_by_signature=True, log_func=None)
    if data_url is None or not _validate_data_url(data_url, path):
        return None
    return data_url


def _first_valid_image_path(validation: dict[str, Any]) -> Path | None:
    for raw_path in validation.get("image_paths") or []:
        path = Path(str(raw_path))
        if _data_url_from_image_file(path) is not None:
            return path
    return None


def _execute_p62_marker_command(
    record: dict[str, Any],
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = list(record.get("marker_command") or [])
    if not command:
        return {"status": "skipped", "reason": "marker_command_unavailable", "returncode": None}

    marker_output_dir = Path(str(record.get("marker_output_dir") or ""))
    if marker_output_dir:
        marker_output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    started = _now()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout_seconds if timeout_seconds > 0 else None,
            check=False,
        )
        stdout = result.stdout or ""
        report = {
            "status": "completed" if result.returncode == 0 else "failed",
            "command": command,
            "started_at": started,
            "finished_at": _now(),
            "returncode": result.returncode,
            "stdout_tail": stdout[-4000:],
        }
    except FileNotFoundError as exc:
        report = {
            "status": "failed",
            "command": command,
            "started_at": started,
            "finished_at": _now(),
            "returncode": None,
            "error": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        report = {
            "status": "timeout",
            "command": command,
            "started_at": started,
            "finished_at": _now(),
            "returncode": None,
            "timeout_seconds": timeout_seconds,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
        }

    if marker_output_dir:
        _write_json(marker_output_dir / "marker_execution_report.json", report)
    return report


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
    if str(record.get("status") or "") == "ready":
        return True
    label_pages = record.get("figure_label_pdf_page_candidates")
    return bool(label_pages)


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
            "warning_index": record.get("warning_index"),
            "plan_status": record.get("status"),
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
            "page_render_status": "not_run",
            "page_render_path": "",
            "page_render_page_number": 0,
            "page_render_selection_reason": "",
            "patch_replacement_count": 0,
            "patched_paths": [],
            "status": "unresolved",
            "unresolved_reason": "",
        }

        if apply_patches and targets:
            warning_still_present = False
            for target_path in targets:
                try:
                    target_html = target_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    item.setdefault("patch_errors", []).append({"path": str(target_path), "error": str(exc)})
                    continue
                if _html_has_p62_missing_warning_for_label(target_html, figure_label):
                    warning_still_present = True
                    break
            if not warning_still_present:
                item["asset_status"] = "ready"
                item["recovery_source"] = "existing_patched_html"
                item["recovery_detail"] = "; ".join(str(path) for path in targets)
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
        if execute_marker and marker_validation.get("status") != "recovered_image":
            item["marker_execution"] = _execute_p62_marker_command(record, timeout_seconds=marker_timeout)
            marker_output_dir = Path(str(record.get("marker_output_dir") or ""))
            marker_validation = _validate_p62_marker_output(marker_output_dir, figure_label)
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

        if not data_url:
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
                figure_label,
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
                        figure_label=figure_label,
                        warning_index=warning_index,
                        data_url=data_url,
                        source=recovery_source,
                        source_detail=recovery_detail,
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
            "pdf_page_render_fallback",
            "html_missing_warning_patch",
        ],
        "candidate_count": int(plan.get("candidate_count") or len(records)),
        "selected_count": len(records),
        "asset_ready_count": asset_ready_count,
        "patched_warning_count": patched_warning_count,
        "patch_missed_count": patch_missed_count,
        "unresolved_count": unresolved_count,
        "execute_marker": execute_marker,
        "apply_patches": apply_patches,
        "allow_external_paths": allow_external_paths,
        "render_zoom": render_zoom,
        "marker_timeout_seconds": marker_timeout,
        "status_counts": dict(sorted(status_counts.items())),
        "recovery_source_counts": dict(sorted(source_counts.items())),
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


def _is_inline_or_remote_src(src: str) -> bool:
    src = src.strip()
    if not src or src.startswith("#"):
        return True
    lower = src.lower()
    return lower.startswith(("data:", "http://", "https://", "blob:", "cid:"))


def _img_srcs(html: str) -> list[str]:
    return [unescape(match.group("src")).strip() for match in IMG_SRC_RE.finditer(html)]


def _source_hinted_data_images(html: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for match in IMG_SRC_RE.finditer(html):
        src = unescape(match.group("src")).strip()
        if not src.lower().startswith("data:image/"):
            continue
        prefix = match.group(1)
        hint = DATA_Z2M_SRC_RE.search(prefix)
        if hint is not None:
            mapping[unescape(hint.group("src")).strip()] = src
    return mapping


def _ordered_data_image_cache(raw_html: str, previous_polish_html: str) -> dict[str, str]:
    """Map raw local image refs to data URLs from an older polish copy.

    Cached loop runs intentionally store only raw/profile HTML.  If the older
    production polish had already inlined local images, preserve those payloads
    so the loop audits polish behavior instead of reporting packaging artifacts.
    """

    raw_local_srcs = [src for src in _img_srcs(raw_html) if not _is_inline_or_remote_src(src)]
    if not raw_local_srcs:
        return {}

    hinted = _source_hinted_data_images(previous_polish_html)
    mapping = {src: hinted[src] for src in raw_local_srcs if src in hinted}
    missing_srcs = [src for src in raw_local_srcs if src not in mapping]
    if not missing_srcs:
        return mapping

    data_srcs = [src for src in _img_srcs(previous_polish_html) if src.lower().startswith("data:image/")]
    if len(data_srcs) == len(raw_local_srcs):
        mapping.update({src: data_src for src, data_src in zip(raw_local_srcs, data_srcs) if src in missing_srcs})
    return mapping


def _escape_html_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _add_src_hint(prefix: str, source_src: str) -> str:
    if DATA_Z2M_SRC_RE.search(prefix):
        return prefix
    escaped = _escape_html_attr(source_src)
    return re.sub(r"\bsrc\s*=\s*$", f'data-z2m-src="{escaped}" src=', prefix, flags=re.IGNORECASE)


def _apply_data_image_cache(html: str, image_cache: dict[str, str]) -> tuple[str, int]:
    if not image_cache:
        return html, 0
    replacements = 0

    def replace_src(match: re.Match[str]) -> str:
        nonlocal replacements
        src = unescape(match.group("src")).strip()
        data_url = image_cache.get(src)
        if data_url is None:
            return match.group(0)
        replacements += 1
        prefix = _add_src_hint(match.group(1), src)
        return f"{prefix}{match.group(2)}{data_url}{match.group(4)}"

    return IMG_SRC_RE.sub(replace_src, html), replacements


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


def _manifest_article_for(manifest: dict[str, Any], article: str) -> dict[str, Any] | None:
    for item in manifest.get("articles") or []:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("article_id") or item.get("article") or "") == article
            or str(item.get("article") or "") == article
        ):
            return item
    return None


def _previous_polish_candidates(source_run_dir: Path, article: str) -> list[Path]:
    candidates: list[Path] = []
    visited: set[Path] = set()

    def visit(run_dir: Path) -> None:
        run_dir = run_dir.resolve(strict=False)
        if run_dir in visited:
            return
        visited.add(run_dir)
        manifest = _load_json(run_dir / "manifest.json", default={})
        item = _manifest_article_for(manifest, article)
        if item:
            for key in ("source_polish_path", "polish_stage_path", "polish_path"):
                value = item.get(key)
                if value:
                    candidates.append(Path(str(value)).resolve(strict=False))
        direct_polish = run_dir / "polish" / f"{article}.{POLISH_STAGE}"
        candidates.append(direct_polish.resolve(strict=False))
        nested = manifest.get("source_run_dir")
        if nested:
            visit(Path(str(nested)))

    visit(source_run_dir)
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def _article_source_image_dirs(source_run_dir: Path, article: str) -> list[Path]:
    dirs: list[Path] = []
    visited: set[Path] = set()

    def add_stage_related_dirs(value: Any) -> None:
        if not value:
            return
        stage_path = Path(str(value)).resolve(strict=False)
        if stage_path.name in {RAW_STAGE, POLISH_STAGE} or stage_path.parent.name == "_z2m_stages":
            article_dir = _article_dir_from_stage(stage_path)
        else:
            article_dir = stage_path.parent
        dirs.append(article_dir)

        parts = list(article_dir.parts)
        if "source_exports" not in parts:
            return
        idx = parts.index("source_exports")
        converted_article_dir = Path(*parts[:idx], "converted", *parts[idx + 1 :])
        dirs.append(converted_article_dir)
        if converted_article_dir.is_dir():
            for child in converted_article_dir.iterdir():
                if child.is_dir() and not child.name.startswith("_"):
                    dirs.append(child)

    def visit(run_dir: Path) -> None:
        run_dir = run_dir.resolve(strict=False)
        if run_dir in visited:
            return
        visited.add(run_dir)
        manifest = _load_json(run_dir / "manifest.json", default={})
        item = _manifest_article_for(manifest, article)
        if item:
            for key in ("raw_stage_path", "source_polish_path", "polish_stage_path", "polish_path"):
                add_stage_related_dirs(item.get(key))
        nested = manifest.get("source_run_dir")
        if nested:
            visit(Path(str(nested)))

    visit(source_run_dir)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in dirs:
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def _local_image_candidates_from_dirs(src: str, search_dirs: Iterable[Path]) -> list[Path]:
    clean = src.strip().split("?", 1)[0].split("#", 1)[0]
    if not clean:
        return []
    parsed = urllib.parse.urlsplit(clean)
    path_value = parsed.path if parsed.scheme.lower() == "file" else clean
    decoded = urllib.parse.unquote(path_value)
    if re.match(r"^/[A-Za-z]:/", decoded):
        decoded = decoded[1:]
    candidate = Path(decoded)
    if candidate.is_absolute():
        return [candidate]
    return [(base / decoded).resolve(strict=False) for base in search_dirs]


def _cached_sidecar_image_cache(
    source_run_dir: Path,
    article: str,
    raw_html: str,
    existing: dict[str, str],
) -> tuple[dict[str, str], str | None]:
    search_dirs = _article_source_image_dirs(source_run_dir, article)
    if not search_dirs:
        return {}, None
    image_cache: dict[str, str] = {}
    source_dirs: set[str] = set()
    raw_local_srcs = [src for src in _img_srcs(raw_html) if not _is_inline_or_remote_src(src)]
    for src in raw_local_srcs:
        if src in existing:
            continue
        for candidate in _local_image_candidates_from_dirs(src, search_dirs):
            if not candidate.is_file():
                continue
            data_url = _to_data_url(candidate, detect_by_signature=True, log_func=None)
            if data_url is None or not _validate_data_url(data_url, candidate):
                continue
            image_cache[src] = data_url
            source_dirs.add(str(candidate.parent))
            break
    if not image_cache:
        return {}, None
    return image_cache, "; ".join(sorted(source_dirs))


def _cached_data_image_cache(source_run_dir: Path, article: str, raw_html: str) -> tuple[dict[str, str], str | None]:
    raw_local_srcs = [src for src in _img_srcs(raw_html) if not _is_inline_or_remote_src(src)]
    expected_count = len(set(raw_local_srcs))
    collected: dict[str, str] = {}
    sources: list[str] = []
    for candidate in _previous_polish_candidates(source_run_dir, article):
        if not candidate.is_file():
            continue
        previous_html = candidate.read_text(encoding="utf-8", errors="replace")
        image_cache = _ordered_data_image_cache(raw_html, previous_html)
        if image_cache:
            collected.update(image_cache)
            sources.append(str(candidate))
            if len(collected) >= expected_count:
                return collected, "; ".join(sources)
    sidecar_cache, sidecar_source = _cached_sidecar_image_cache(source_run_dir, article, raw_html, collected)
    if sidecar_cache:
        collected.update(sidecar_cache)
        if sidecar_source:
            sources.append(sidecar_source)
    return collected, "; ".join(sources) if sources else None


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
    return _load_json(path)


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
    comparable_totals_delta = (
        comparison.get("comparable_totals_delta")
        if isinstance(comparison.get("comparable_totals_delta"), dict)
        else {}
    )
    gate_totals_delta = comparable_totals_delta or totals_delta
    for metric, limit in dict(gate_config.get("max_total_deltas") or {}).items():
        observed = float(gate_totals_delta.get(metric, 0) or 0)
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
        if isinstance(audit_report, dict):
            audit_totals = dict((audit_report.get("corpus_summary") or {}).get("totals") or {})
        audit_pdf_summary = {
            "pdf_text_chars": int(audit_totals.get("pdf_text_chars") or 0),
            "source_pdf_present": int(audit_totals.get("source_pdf_present") or 0),
            "command_used_pdf_diagnostics": bool(
                isinstance(audit_command_report, dict)
                and audit_command_report.get("pdf_diagnostics_enabled")
            ),
            "pdf_map_path": (
                audit_command_report.get("pdf_map_path")
                if isinstance(audit_command_report, dict)
                else None
            ),
        }
        if not isinstance(audit_report, dict):
            failures.append(
                {
                    "kind": "pdf_text_layer_diagnostics_missing",
                    "message": "audit_full_checks.json was not available for PDF text-layer diagnostics validation.",
                }
            )
        elif not audit_pdf_summary["command_used_pdf_diagnostics"]:
            failures.append(
                {
                    "kind": "pdf_text_layer_diagnostics_disabled",
                    "message": "Audit did not run with --pdf-diagnostics.",
                }
            )
        elif audit_pdf_summary["source_pdf_present"] > 0 and audit_pdf_summary["pdf_text_chars"] <= 0:
            failures.append(
                {
                    "kind": "pdf_text_layer_empty",
                    "source_pdf_present": audit_pdf_summary["source_pdf_present"],
                    "pdf_text_chars": audit_pdf_summary["pdf_text_chars"],
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _pattern_key_for_defect(defect: dict[str, Any], defect_patterns: dict[str, Any]) -> str:
    defect_id = str(defect.get("id") or "unknown")
    pattern = defect_patterns.get(defect_id) if isinstance(defect_patterns.get(defect_id), dict) else {}
    known_pattern = str(pattern.get("pattern") or "").strip()
    if known_pattern:
        return known_pattern
    check = str(defect.get("check") or "unclassified").strip()
    return f"{defect_id}:{_slug(check, max_len=48)}"


def _empty_pattern_record(pattern_key: str, defect_patterns: dict[str, Any]) -> dict[str, Any]:
    matching = [
        pattern
        for pattern in defect_patterns.values()
        if isinstance(pattern, dict) and pattern.get("pattern") == pattern_key
    ]
    known = matching[0] if matching else {}
    return {
        "pattern_key": pattern_key,
        "criticality": known.get("criticality"),
        "fix_layer": known.get("fix_layer"),
        "occurrence_count": 0,
        "article_count": 0,
        "articles": [],
        "defect_ids": {},
        "checks": {},
        "severity_counts": {},
        "sample_observations": [],
    }


def _add_count(target: dict[str, int], key: str, amount: int = 1) -> None:
    target[key] = int(target.get(key, 0) or 0) + amount


def _problem_state(run_count: int, article_observation_count: int, occurrence_count: int) -> str:
    if run_count >= 2 or article_observation_count >= 2 or occurrence_count >= 3:
        return "problem_candidate"
    return "pattern_observation"


def _aggregate_pattern_history(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for record in records:
        run_id = str(record.get("run_id") or "")
        generated_at = str(record.get("generated_at") or "")
        for pattern in record.get("patterns") or []:
            if not isinstance(pattern, dict):
                continue
            pattern_key = str(pattern.get("pattern_key") or "")
            if not pattern_key:
                continue
            target = aggregated.setdefault(
                pattern_key,
                {
                    "pattern_key": pattern_key,
                    "criticality": pattern.get("criticality"),
                    "fix_layer": pattern.get("fix_layer"),
                    "run_ids": [],
                    "run_count": 0,
                    "occurrence_count": 0,
                    "article_observation_count": 0,
                    "defect_ids": {},
                    "checks": {},
                    "severity_counts": {},
                    "sample_observations": [],
                    "first_seen_at": generated_at,
                    "last_seen_at": generated_at,
                },
            )
            if run_id and run_id not in target["run_ids"]:
                target["run_ids"].append(run_id)
            target["run_count"] = len(target["run_ids"])
            target["occurrence_count"] += int(pattern.get("occurrence_count") or 0)
            target["article_observation_count"] += int(pattern.get("article_count") or 0)
            for key, value in dict(pattern.get("defect_ids") or {}).items():
                _add_count(target["defect_ids"], str(key), int(value or 0))
            for key, value in dict(pattern.get("checks") or {}).items():
                _add_count(target["checks"], str(key), int(value or 0))
            for key, value in dict(pattern.get("severity_counts") or {}).items():
                _add_count(target["severity_counts"], str(key), int(value or 0))
            for sample in pattern.get("sample_observations") or []:
                if len(target["sample_observations"]) >= 8:
                    break
                if isinstance(sample, dict):
                    target["sample_observations"].append(sample)
            if generated_at:
                if not target.get("first_seen_at") or generated_at < target["first_seen_at"]:
                    target["first_seen_at"] = generated_at
                if not target.get("last_seen_at") or generated_at > target["last_seen_at"]:
                    target["last_seen_at"] = generated_at

    for pattern in aggregated.values():
        pattern["defect_ids"] = dict(sorted(pattern["defect_ids"].items()))
        pattern["checks"] = dict(sorted(pattern["checks"].items()))
        pattern["severity_counts"] = dict(sorted(pattern["severity_counts"].items()))
        pattern["run_ids"] = sorted(pattern["run_ids"])
        pattern["problem_state"] = _problem_state(
            int(pattern.get("run_count") or 0),
            int(pattern.get("article_observation_count") or 0),
            int(pattern.get("occurrence_count") or 0),
        )

    return sorted(
        aggregated.values(),
        key=lambda item: (
            item.get("problem_state") != "problem_candidate",
            -int(item.get("article_observation_count") or 0),
            -int(item.get("occurrence_count") or 0),
            str(item.get("pattern_key") or ""),
        ),
    )


def _manual_observation_ledger_path(run_dir: Path, ledger_path: Path | None = None) -> Path:
    return (ledger_path or (run_dir.parent / DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME)).resolve(strict=False)


def _normalize_observation_text(value: Any, *, max_len: int = 180) -> str:
    text = TAG_RE.sub(" ", str(value or ""))
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\d+", "#", text)
    return text[:max_len]


def _compact_observation_text(value: Any, *, max_len: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def manual_observation_signature(observation: dict[str, Any]) -> str:
    suspected_pattern = _normalize_observation_text(observation.get("suspected_pattern"), max_len=96)
    if suspected_pattern:
        return f"pattern:{_slug(suspected_pattern, max_len=96)}"
    for key in ("visible_text", "snippet", "html_fragment", "notes"):
        normalized = _normalize_observation_text(observation.get(key))
        if normalized:
            return f"text:{_slug(normalized, max_len=120)}"
    return "text:unknown"


def record_manual_observation(ledger_path: Path, observation: dict[str, Any]) -> dict[str, Any]:
    """Append one manually spotted manifestation to the cumulative ledger."""

    article = str(observation.get("article") or "").strip()
    snippet = str(observation.get("snippet") or "").strip()
    if not article:
        raise ValueError("Manual observation requires an article.")
    if not snippet:
        raise ValueError("Manual observation requires a snippet.")

    created_at = str(observation.get("created_at") or _now())
    stage_path = observation.get("stage_path")
    defect_id = observation.get("defect_id_if_any") or observation.get("defect_id")
    record = {
        "created_at": created_at,
        "run_id": str(observation.get("run_id") or "").strip(),
        "article": article,
        "stage_path": str(stage_path) if stage_path else "",
        "defect_id_if_any": str(defect_id or "").strip(),
        "snippet": snippet,
        "html_fragment": str(observation.get("html_fragment") or "").strip(),
        "visible_text": str(observation.get("visible_text") or "").strip(),
        "suspected_pattern": str(observation.get("suspected_pattern") or "").strip(),
        "status": str(observation.get("status") or "untriaged").strip() or "untriaged",
        "test_status": str(observation.get("test_status") or "none").strip() or "none",
        "notes": str(observation.get("notes") or "").strip(),
        "source": str(observation.get("source") or "manual_review").strip() or "manual_review",
    }
    record["normalized_signature"] = str(
        observation.get("normalized_signature") or manual_observation_signature(record)
    )
    digest_source = json.dumps(
        {
            "created_at": record["created_at"],
            "article": record["article"],
            "snippet": record["snippet"],
            "stage_path": record["stage_path"],
            "suspected_pattern": record["suspected_pattern"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    record["observation_id"] = str(
        observation.get("observation_id")
        or f"manual-{_slug(created_at, max_len=20)}-{hashlib.sha1(digest_source.encode('utf-8')).hexdigest()[:10]}"
    )
    _append_jsonl(ledger_path.resolve(strict=False), record)
    return record


def write_manual_observation_summary(
    run_dir: Path,
    *,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Group raw manual observations before promoting them into problems."""

    run_dir = run_dir.resolve(strict=False)
    ledger_path = _manual_observation_ledger_path(run_dir, ledger_path)
    raw_records = _read_jsonl(ledger_path)
    records_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_record in enumerate(raw_records):
        record = dict(raw_record)
        observation_id = str(record.get("observation_id") or f"legacy-{index}")
        record["observation_id"] = observation_id
        created_at = str(record.get("created_at") or "")
        previous = records_by_id.get(observation_id)
        if previous is None:
            record["_first_seen_at"] = created_at
            records_by_id[observation_id] = record
            continue
        first_seen = str(previous.get("_first_seen_at") or previous.get("created_at") or "")
        previous_created = str(previous.get("created_at") or "")
        if created_at >= previous_created:
            record["_first_seen_at"] = first_seen
            records_by_id[observation_id] = record
    records = sorted(
        records_by_id.values(),
        key=lambda record: (str(record.get("_first_seen_at") or ""), str(record.get("observation_id") or "")),
    )
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        signature = str(record.get("normalized_signature") or manual_observation_signature(record))
        first_seen_at = str(record.get("_first_seen_at") or record.get("created_at") or "")
        group = grouped.setdefault(
            signature,
            {
                "normalized_signature": signature,
                "occurrence_count": 0,
                "article_count": 0,
                "run_count": 0,
                "articles": [],
                "run_ids": [],
                "defect_ids": {},
                "statuses": {},
                "test_statuses": {},
                "suspected_patterns": {},
                "sources": {},
                "sample_observations": [],
                "first_seen_at": first_seen_at,
                "last_seen_at": str(record.get("created_at") or ""),
                "_articles": set(),
                "_run_ids": set(),
            },
        )
        group["occurrence_count"] += 1
        article = str(record.get("article") or "")
        run_id = str(record.get("run_id") or "")
        if article:
            group["_articles"].add(article)
        if run_id:
            group["_run_ids"].add(run_id)
        _add_count(group["defect_ids"], str(record.get("defect_id_if_any") or "none"))
        _add_count(group["statuses"], str(record.get("status") or "untriaged"))
        _add_count(group["test_statuses"], str(record.get("test_status") or "none"))
        _add_count(group["suspected_patterns"], str(record.get("suspected_pattern") or "unspecified"))
        _add_count(group["sources"], str(record.get("source") or "manual_review"))

        created_at = str(record.get("created_at") or "")
        if first_seen_at:
            if not group.get("first_seen_at") or first_seen_at < group["first_seen_at"]:
                group["first_seen_at"] = first_seen_at
        if created_at:
            if not group.get("last_seen_at") or created_at > group["last_seen_at"]:
                group["last_seen_at"] = created_at
        if len(group["sample_observations"]) < 8:
            group["sample_observations"].append(
                {
                    "observation_id": record.get("observation_id"),
                    "article": article,
                    "run_id": run_id,
                    "stage_path": record.get("stage_path"),
                    "defect_id_if_any": record.get("defect_id_if_any"),
                    "snippet": _compact_observation_text(record.get("snippet")),
                    "status": record.get("status") or "untriaged",
                    "test_status": record.get("test_status") or "none",
                    "notes": _compact_observation_text(record.get("notes"), max_len=240),
                }
            )

    groups: list[dict[str, Any]] = []
    for group in grouped.values():
        articles = sorted(group.pop("_articles"))
        run_ids = sorted(group.pop("_run_ids"))
        group["articles"] = articles
        group["run_ids"] = run_ids
        group["article_count"] = len(articles)
        group["run_count"] = len(run_ids)
        for key in ("defect_ids", "statuses", "test_statuses", "suspected_patterns", "sources"):
            group[key] = dict(sorted(group[key].items()))
        group["problem_state"] = _problem_state(
            int(group.get("run_count") or 0),
            int(group.get("article_count") or 0),
            int(group.get("occurrence_count") or 0),
        )
        groups.append(group)

    groups.sort(
        key=lambda item: (
            item.get("problem_state") != "problem_candidate",
            -int(item.get("article_count") or 0),
            -int(item.get("occurrence_count") or 0),
            str(item.get("normalized_signature") or ""),
        )
    )
    problem_candidates = [group for group in groups if group.get("problem_state") == "problem_candidate"]
    requires_triage = [group for group in groups if int(dict(group.get("statuses") or {}).get("untriaged", 0) or 0)]
    summary = {
        "generated_at": _now(),
        "run_id": _load_json(run_dir / "quality_history_entry.json", default={}).get("run_id") or run_dir.name,
        "run_dir": str(run_dir),
        "ledger_path": str(ledger_path),
        "ledger_entry_count": len(raw_records),
        "observation_count": len(records),
        "group_count": len(groups),
        "groups": groups,
        "problem_candidates": problem_candidates,
        "requires_triage": requires_triage,
    }
    _write_json(run_dir / "manual_observation_summary.json", summary)
    return summary


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


def _review_html_image_search_dirs(stage_path: Path) -> list[Path]:
    article_dir = _article_dir_from_stage(stage_path)
    candidates = [
        stage_path.parent,
        article_dir,
        article_dir / "images",
        article_dir / "figures",
        article_dir / "assets",
    ]
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    return deduped


def _copy_review_html_with_inline_images(source_path: Path, target_path: Path) -> dict[str, Any]:
    html = source_path.read_text(encoding="utf-8", errors="replace")
    search_dirs = _review_html_image_search_dirs(source_path)
    inlined = 0
    missing: list[str] = []

    def replace_src(match: re.Match[str]) -> str:
        nonlocal inlined
        src = unescape(match.group("src")).strip()
        if _is_inline_or_remote_src(src):
            return match.group(0)
        for candidate in _local_image_candidates_from_dirs(src, search_dirs):
            if not candidate.is_file():
                continue
            data_url = _to_data_url(candidate, detect_by_signature=True, log_func=None)
            if data_url is None or not _validate_data_url(data_url, candidate):
                continue
            inlined += 1
            prefix = _add_src_hint(match.group(1), src)
            return f"{prefix}{match.group(2)}{data_url}{match.group(4)}"
        missing.append(src)
        return match.group(0)

    copied = IMG_SRC_RE.sub(replace_src, html)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(copied, encoding="utf-8")
    return {
        "review_html": str(target_path),
        "source_html": str(source_path),
        "inlined_image_count": inlined,
        "missing_image_count": len(missing),
        "missing_image_srcs": sorted(set(missing))[:20],
    }


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
    """Summarize current corpus manifestations and append them to pattern history."""

    run_dir = run_dir.resolve(strict=False)
    history_path = (history_path or (run_dir.parent / DEFAULT_PATTERN_HISTORY_NAME)).resolve(strict=False)
    defect_patterns = defect_patterns or _load_json(defect_patterns_path, default={})
    audit = _load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    manifest = _load_json(run_dir / "manifest.json", default={})
    entry = _load_json(run_dir / "quality_history_entry.json", default={})
    run_id = str(entry.get("run_id") or run_dir.name)

    current_by_pattern: dict[str, dict[str, Any]] = {}
    audit_articles = [article for article in audit.get("articles") or [] if isinstance(article, dict)]
    for article in audit_articles:
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        source_article = str(article.get("source_article") or article_id)
        artifact_hint = article.get("artifact_hint")
        raw_stage_path = article.get("raw_stage_path")
        polish_stage_path = article.get("polish_stage_path")
        for defect in article.get("defects_found") or []:
            if not isinstance(defect, dict):
                continue
            pattern_key = _pattern_key_for_defect(defect, defect_patterns)
            record = current_by_pattern.setdefault(
                pattern_key,
                {
                    **_empty_pattern_record(pattern_key, defect_patterns),
                    "_article_set": set(),
                },
            )
            record["occurrence_count"] += 1
            record["_article_set"].add(article_id)
            _add_count(record["defect_ids"], str(defect.get("id") or "unknown"))
            _add_count(record["checks"], str(defect.get("check") or "unknown"))
            _add_count(record["severity_counts"], str(defect.get("severity") or "info"))
            if len(record["sample_observations"]) < 8:
                record["sample_observations"].append(
                    {
                        "article": article_id,
                        "source_article": source_article,
                        "artifact_hint": artifact_hint,
                        "defect_id": defect.get("id"),
                        "severity": defect.get("severity"),
                        "check": defect.get("check"),
                        "snippet": defect.get("snippet"),
                        "raw_stage_path": raw_stage_path,
                        "polish_stage_path": polish_stage_path,
                    }
                )

    patterns: list[dict[str, Any]] = []
    for record in current_by_pattern.values():
        articles = sorted(record.pop("_article_set"))
        record["articles"] = articles
        record["article_count"] = len(articles)
        record["defect_ids"] = dict(sorted(record["defect_ids"].items()))
        record["checks"] = dict(sorted(record["checks"].items()))
        record["severity_counts"] = dict(sorted(record["severity_counts"].items()))
        record["problem_state"] = _problem_state(1, len(articles), int(record["occurrence_count"] or 0))
        patterns.append(record)

    patterns.sort(
        key=lambda item: (
            item.get("problem_state") != "problem_candidate",
            -int(item.get("article_count") or 0),
            -int(item.get("occurrence_count") or 0),
            str(item.get("pattern_key") or ""),
        )
    )

    history_record = {
        "generated_at": _now(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "source_kind": manifest.get("source_kind"),
        "code_commit": manifest.get("code_commit"),
        "working_tree_dirty": manifest.get("working_tree_dirty"),
        "article_count_reviewed": len(audit_articles),
        "pattern_count": len(patterns),
        "patterns": patterns,
    }
    previous_history = _read_jsonl(history_path)
    _append_jsonl(history_path, history_record)
    cumulative_patterns = _aggregate_pattern_history([*previous_history, history_record])
    problem_candidates = [
        pattern for pattern in cumulative_patterns if pattern.get("problem_state") == "problem_candidate"
    ]
    summary = {
        **history_record,
        "history_path": str(history_path),
        "all_articles_reviewed_for_patterns": True,
        "cumulative_patterns": cumulative_patterns,
        "problem_candidates": problem_candidates,
    }
    _write_json(run_dir / "pattern_observations.json", summary)
    return summary


BENIGN_TELEMETRY_DEFECT_IDS = {"P04T", "P04M", "P45S", "P45M"}
PDF_REFERENCE_RECOVERY_DEFECT_IDS = {"P04N"}
PDF_FIGURE_RECOVERY_DEFECT_IDS = {"P62"}
SEMANTIC_FIGURE_TARGET_DEFECT_IDS = {"P61"}
SOURCE_LAYER_TELEMETRY_DEFECT_IDS = {"P35", "P71"}


def _defect_extra(defect: dict[str, Any]) -> dict[str, Any]:
    extra = defect.get("extra")
    return extra if isinstance(extra, dict) else {}


def _defect_quality_counted(defect: dict[str, Any]) -> bool:
    extra = _defect_extra(defect)
    return bool(extra.get("quality_counted", True))


def _has_source_pdf_text_layer_evidence(defect: dict[str, Any], article_summary: dict[str, Any]) -> bool:
    extra = _defect_extra(defect)
    if any("source_pdf_text_layer" in str(key) and value for key, value in extra.items()):
        return True
    return (
        str(article_summary.get("pdf_text_status") or "").lower() not in {"", "missing", "unavailable", "error"}
        and bool(article_summary.get("source_pdf_present"))
    )


def _resolver_decision_for_defect(
    defect: dict[str, Any],
    article_summary: dict[str, Any],
) -> tuple[str, str, str, list[str]]:
    defect_id = str(defect.get("id") or "unknown")
    extra = _defect_extra(defect)
    if _defect_quality_counted(defect):
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
    if defect_id in SOURCE_LAYER_TELEMETRY_DEFECT_IDS and _has_source_pdf_text_layer_evidence(defect, article_summary):
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


def _resolver_sample_decision(defect: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    article_id = str(article.get("article") or "")
    article_summary = article.get("summary") if isinstance(article.get("summary"), dict) else {}
    decision, reason, fix_layer, evidence_required = _resolver_decision_for_defect(defect, article_summary)
    extra = _defect_extra(defect)
    return {
        "article": article_id,
        "source_article": article.get("source_article") or article_id,
        "defect_id": str(defect.get("id") or "unknown"),
        "check": defect.get("check"),
        "severity": defect.get("severity"),
        "quality_counted": _defect_quality_counted(defect),
        "decision": decision,
        "reason": reason,
        "fix_layer": fix_layer,
        "evidence_required": evidence_required,
        "snippet": _compact_observation_text(defect.get("snippet"), max_len=260),
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


def _group_resolver_decisions(decisions: Iterable[dict[str, Any]], decision_names: set[str]) -> list[dict[str, Any]]:
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


def write_resolver_decisions(run_dir: Path) -> dict[str, Any]:
    """Classify observed audit signals into telemetry, repair, and triage buckets."""

    run_dir = run_dir.resolve(strict=False)
    audit = _load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    manifest = _load_json(run_dir / "manifest.json", default={})
    entry = _load_json(run_dir / "quality_history_entry.json", default={})
    run_id = str(entry.get("run_id") or run_dir.name)
    decisions: list[dict[str, Any]] = []
    for article in audit.get("articles") or []:
        if not isinstance(article, dict):
            continue
        for defect in article.get("defects_found") or []:
            if isinstance(defect, dict):
                decisions.append(_resolver_sample_decision(defect, article))

    decision_counts = Counter(str(item.get("decision") or "unknown") for item in decisions)
    defect_id_counts = Counter(str(item.get("defect_id") or "unknown") for item in decisions)
    accepted_telemetry_counts = Counter(
        str(item.get("defect_id") or "unknown")
        for item in decisions
        if item.get("decision") == "accepted_telemetry"
    )
    repair_decision_names = {"needs_pdf_recovery", "needs_semantic_recovery", "needs_pdf_reference_recovery"}
    repair_candidate_counts = Counter(
        str(item.get("defect_id") or "unknown")
        for item in decisions
        if item.get("decision") in repair_decision_names
    )
    manual_or_llm_count = int(decision_counts.get("needs_manual_or_llm", 0))
    report = {
        "generated_at": _now(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "path": str(run_dir / DEFAULT_RESOLVER_DECISIONS_NAME),
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
        "repair_candidate_groups": _group_resolver_decisions(decisions, repair_decision_names),
        "accepted_telemetry_groups": _group_resolver_decisions(decisions, {"accepted_telemetry"}),
        "manual_or_llm_groups": _group_resolver_decisions(decisions, {"needs_manual_or_llm"}),
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
    _write_json(run_dir / DEFAULT_RESOLVER_DECISIONS_NAME, report)
    return report


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
            "patch_missed_count": p62_image_recovery_report.get("patch_missed_count", 0),
            "unresolved_count": p62_image_recovery_report.get("unresolved_count", 0),
            "status_counts": p62_image_recovery_report.get("status_counts", {}),
            "recovery_source_counts": p62_image_recovery_report.get("recovery_source_counts", {}),
            "execute_marker": p62_image_recovery_report.get("execute_marker"),
            "apply_patches": p62_image_recovery_report.get("apply_patches"),
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
        f"- p62_image_recovery_unresolved_count: `{(pack.get('p62_image_recovery_stage') or {}).get('unresolved_count')}`",
        f"- p62_image_recovery_source_counts: `{json.dumps((pack.get('p62_image_recovery_stage') or {}).get('recovery_source_counts', {}), ensure_ascii=False, sort_keys=True)}`",
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
                f"- patch_missed_count: `{p62_recovery.get('patch_missed_count')}`",
                f"- unresolved_count: `{p62_recovery.get('unresolved_count')}`",
                f"- recovery_source_counts: `{json.dumps(p62_recovery.get('recovery_source_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
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
    audit_roots = [root.resolve(strict=False) for root in roots] if roots else [run_dir / "audit_tree"]
    if not audit_roots:
        raise ValueError("No audit roots supplied.")
    missing_roots = [root for root in audit_roots if not root.exists()]
    if missing_roots:
        raise FileNotFoundError(f"Missing audit root(s): {', '.join(str(root) for root in missing_roots)}")
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    started = _now()
    stdout_path = run_dir / "audit_stdout.log"
    stderr_path = run_dir / "audit_stderr.log"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "audit_en_polish.py"),
        "--roots",
        *[str(root) for root in audit_roots],
        "--out",
        str(run_dir / "audit_full_checks.json"),
    ]
    if enable_pdf_diagnostics:
        command.append("--pdf-diagnostics")
    if pdf_map_path is not None:
        command.extend(["--pdf-map", str(pdf_map_path)])
    print(f"Audit started: roots={len(audit_roots)} out={run_dir / 'audit_full_checks.json'}", flush=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
        )
        started_monotonic = time.monotonic()
        next_report = started_monotonic + 15
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            now = time.monotonic()
            if now >= next_report:
                print(f"Audit running: elapsed={int(now - started_monotonic)}s", flush=True)
                next_report = now + 15
            time.sleep(1)

    stdout_tail = stdout_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stdout_path.is_file() else ""
    stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stderr_path.is_file() else ""
    _write_json(
        run_dir / "audit_command_report.json",
        {
            "command": command,
            "roots": [str(root) for root in audit_roots],
            "pdf_diagnostics_enabled": enable_pdf_diagnostics,
            "pdf_map_path": str(pdf_map_path) if pdf_map_path is not None else "",
            "started_at": started,
            "finished_at": _now(),
            "returncode": returncode,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        },
    )
    print(f"Audit finished: exit={returncode}", flush=True)
    if returncode != 0:
        raise SystemExit(f"Audit command failed with exit code {returncode}. See {run_dir / 'audit_command_report.json'}")


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
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "test_stdout.log"
    stderr_path = run_dir / "test_stderr.log"
    print(f"Tests started: {command}", flush=True)
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            shell=True,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
        )
        started_monotonic = time.monotonic()
        next_report = started_monotonic + 15
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            now = time.monotonic()
            if now >= next_report:
                print(f"Tests running: elapsed={int(now - started_monotonic)}s", flush=True)
                next_report = now + 15
            time.sleep(1)

    stdout_tail = stdout_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stdout_path.is_file() else ""
    stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stderr_path.is_file() else ""
    report = {
        "command": command,
        "started_at": started,
        "finished_at": _now(),
        "returncode": returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    _write_json(run_dir / "test_command_report.json", report)
    print(f"Tests finished: exit={returncode}", flush=True)
    if returncode != 0:
        raise SystemExit(f"Test command failed with exit code {returncode}: {command}")
    return report


def _write_gate_report(run_dir: Path, gate_config_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    comparison = _load_json(run_dir / "quality_compare.json")
    gate_config = load_gate_config(gate_config_path)
    article_review_path = run_dir / "article_review_report.json"
    article_review_report = _load_json(article_review_path) if article_review_path.is_file() else None
    audit_path = run_dir / "audit_full_checks.json"
    audit_report = _load_json(audit_path) if audit_path.is_file() else None
    audit_command_path = run_dir / "audit_command_report.json"
    audit_command_report = _load_json(audit_command_path) if audit_command_path.is_file() else None
    pdf_problem_evidence_path = run_dir / DEFAULT_PDF_PROBLEM_EVIDENCE_NAME
    pdf_problem_evidence_report = (
        _load_json(pdf_problem_evidence_path) if pdf_problem_evidence_path.is_file() else None
    )
    report = evaluate_quality_gate(
        comparison,
        gate_config,
        article_review_report=article_review_report,
        audit_report=audit_report,
        audit_command_report=audit_command_report,
        pdf_problem_evidence_report=pdf_problem_evidence_report,
    )
    _write_json(out_path or (run_dir / "quality_gate_report.json"), report)
    return report


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
