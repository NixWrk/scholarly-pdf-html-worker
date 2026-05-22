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
from html import unescape
import json
import os
import re
import shutil
import subprocess
import sys
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
from zoteropdf2md.citation_profile import infer_citation_style_from_text  # noqa: E402
from zoteropdf2md.polish_language import resolve_document_polish_language  # noqa: E402


RAW_STAGE = "01.en.raw.html"
POLISH_STAGE = "02.en.polish.html"
DEFAULT_GATE_CONFIG = ROOT / "configs" / "llm_quality_gates.json"
DEFAULT_DEFECT_PATTERNS = ROOT / "configs" / "llm_defect_patterns.json"
DEFAULT_PATTERN_HISTORY_NAME = "pattern_observation_history.jsonl"

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
                continue

            polish_language_counts[language_decision.selected_polish_language] += 1
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
                    "language_detection": language_decision.detection.to_dict(),
                    **language_fields,
                }
            )
            assessment = assess_polish_html(article, polished, profile)
            assessment.update(language_fields)
            assessments.append(assessment)
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
        "audit_defect_counts": audit.get("corpus_summary", {}).get("defect_counts", {}),
        "pattern_observations": {
            "history_path": pattern_observations.get("history_path"),
            "article_count_reviewed": pattern_observations.get("article_count_reviewed"),
            "pattern_count": pattern_observations.get("pattern_count"),
            "all_articles_reviewed_for_patterns": pattern_observations.get("all_articles_reviewed_for_patterns"),
            "problem_candidates": (pattern_observations.get("problem_candidates") or [])[:12],
            "current_patterns": (pattern_observations.get("patterns") or [])[:12],
            "cumulative_patterns": (pattern_observations.get("cumulative_patterns") or [])[:12],
        },
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
        "Every production artifact fix must include a focused regression test that reproduces the observed symptom.",
        "Also add at least one guard/negative test when the repair could touch links, tags, math, code, language policy, or nearby article classes.",
        "Pattern observations must be accumulated globally across loop iterations before local manifestations are promoted into shared problem statements.",
        "Review the all-article current pattern summary and the cumulative pattern history before proposing a fix.",
        "When one P-code groups different root causes or artifact mechanisms, refine the P classification before or alongside the repair.",
        "The loop is incomplete until the full configured project test suite and a full cached raw EN repolish comparison have both passed.",
        "The full cached raw EN repolish comparison means all cached raw files are scanned and every accepted EN article is repolished.",
        "",
        "Return this structure:",
        "1. Critical findings by article.",
        "2. Cross-article patterns.",
        "3. Patch plan with production file/function targets.",
        "4. Tests to add or update, including the focused artifact regression.",
        "5. Risks and gate checks to rerun.",
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
        f"- comparison_totals_delta: `{json.dumps(pack.get('comparison_totals_delta', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- comparison_comparable_totals_delta: `{json.dumps(pack.get('comparison_comparable_totals_delta', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- new_article_count: `{pack.get('new_article_count')}`",
        f"- removed_article_count: `{pack.get('removed_article_count')}`",
        f"- pattern_history_path: `{(pack.get('pattern_observations') or {}).get('history_path')}`",
        f"- pattern_articles_reviewed: `{(pack.get('pattern_observations') or {}).get('article_count_reviewed')}`",
        "",
        "## Accumulated Pattern Observations",
        "",
        "Use these grouped observations before judging any article-local symptom.",
    ]
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
    if args.run_tests:
        gate_config = load_gate_config(args.gate_config)
        run_test_command(args.test_command or gate_config.get("required_test_command") or "python -m pytest -q", run_dir)
    if not args.skip_audit:
        audit_existing_converted = bool(converted_roots and not args.repolish_converted_raw)
        run_audit(run_dir, roots=converted_roots if audit_existing_converted else None)
        if audit_existing_converted:
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
    pattern_observations = write_pattern_observations(
        run_dir,
        defect_patterns_path=args.defect_patterns,
        history_path=args.pattern_history,
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
        f"patterns={pattern_observations['pattern_count']} "
        f"problem_candidates={len(pattern_observations['problem_candidates'])} "
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
    observe_parser.add_argument("--ignore-defect-id", action="append")
    observe_parser.add_argument("--max-articles", type=int, default=12)
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
