"""Converted-stage and cached-run preparation helpers for the quality loop."""

from __future__ import annotations

from collections import Counter
from html import unescape
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any, Iterable

from zoteropdf2md.citation_profile import infer_citation_style_from_text
from zoteropdf2md.html_links import count_same_document_absolute_fragment_links
from zoteropdf2md.html_stages import POLISH_STAGE_NAME, RAW_STAGE_NAME

from .run_utils import (
    article_dir_from_stage,
    article_name_from_stage,
    artifact_hint,
    converted_article_id,
    git_dirty,
    git_short_head,
    now,
    profile_value,
    write_json,
)


RAW_STAGE = RAW_STAGE_NAME
POLISH_STAGE = POLISH_STAGE_NAME

HREF_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*([\"'])(?P<href>.*?)\1", re.IGNORECASE | re.DOTALL)
ID_RE = re.compile(r"\bid\s*=\s*([\"'])(?P<id>.*?)\1", re.IGNORECASE | re.DOTALL)
SUP_BLOCK_RE = re.compile(r"<sup\b[^>]*>[\s\S]{0,500}?</sup>", re.IGNORECASE)
REF_HREF_RE = re.compile(r"\bhref\s*=\s*[\"']#ref-\d+[\"']", re.IGNORECASE)
REF_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*[\"']#ref-\d+[\"'][^>]*>(?P<body>[\s\S]{0,120}?)</a>",
    re.IGNORECASE,
)
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


def _html_plain_text_for_profile(html: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6]|table|section|article)>", "\n", text)
    text = TAG_RE.sub(" ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def visible_html_text(fragment: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", " ", fragment)
    text = TAG_RE.sub(" ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _is_data_availability_reference_number(ref_match: re.Match[str], html: str) -> bool:
    body_text = visible_html_text(ref_match.group("body"))
    if not BRACKET_NUMERIC_REF_TEXT_RE.fullmatch(body_text):
        return False
    prefix = visible_html_text(html[max(0, ref_match.start() - 700) : ref_match.start()])
    suffix = visible_html_text(html[ref_match.end() : min(len(html), ref_match.end() + 160)])
    near_text = f"{prefix[-500:]} {body_text} {suffix[:160]}"
    return bool(REFERENCE_NUMBER_BRACKET_RE.search(near_text) and DATA_AVAILABILITY_CONTEXT_RE.search(near_text))


def _is_bracket_ref_link_for_style(ref_match: re.Match[str], html: str) -> bool:
    body_text = visible_html_text(ref_match.group("body"))
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


def _href_has_local_page_query(href: str) -> bool:
    if "page=" not in href.lower():
        return False
    parsed = urllib.parse.urlsplit(href)
    if parsed.scheme or parsed.netloc:
        return False
    return re.search(r"(?:^|&)page=", parsed.query, re.IGNORECASE) is not None


def assess_polish_html(article: str, html: str, profile: dict[str, Any]) -> dict[str, Any]:
    ids = {match.group("id") for match in ID_RE.finditer(html)}
    href_counts: dict[str, int] = {}
    broken_targets: list[str] = []
    same_document_absolute_links = count_same_document_absolute_fragment_links(html)
    if same_document_absolute_links:
        href_counts["same_document_absolute_links_remaining"] = same_document_absolute_links
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
        if _href_has_local_page_query(href):
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
        "profile_style": profile_value(profile, "style"),
        "profile_confidence": profile_value(profile, "confidence"),
        "profile_status": profile_value(profile, "status"),
        "href_counts": dict(sorted(href_counts.items())),
        "broken_targets": sorted(set(broken_targets)),
        "table_units_with_section_ids": 0,
        "sup_ref_links": sup_ref_links,
        "bracket_ref_links": bracket_ref_links,
        "mixed_citation_style": bool(sup_ref_links and bracket_ref_links),
        "missing_warning_count": len(MISSING_WARNING_CLASS_RE.findall(html)),
    }


MISSING_WARNING_CLASS_RE = re.compile(
    r"\bclass\s*=\s*([\"'])(?=[^\"']*\bz2m-missing)[^\"']*\1",
    re.IGNORECASE,
)


def assessment_totals(articles: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, list[str]]]:
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
        article = article_name_from_stage(raw_path)
        article_id = converted_article_id(raw_path, index)
        polish_html = polish_path.read_text(encoding="utf-8", errors="replace")
        articles.append(
            {
                "index": index,
                "article_id": article_id,
                "article": article,
                "article_dir": str(article_dir_from_stage(raw_path)),
                "raw_stage_path": str(raw_path),
                "polish_stage_path": str(polish_path),
                "artifact_hint": artifact_hint(raw_path),
            }
        )
        assessment = assess_polish_html(article_id, polish_html, profile)
        assessment["source_article"] = article
        assessment["raw_stage_path"] = str(raw_path)
        assessment["polish_stage_path"] = str(polish_path)
        assessment["artifact_hint"] = artifact_hint(raw_path)
        assessments.append(assessment)

    totals, problematic = assessment_totals(assessments)
    profile_status_counts = {profile["status"]: len(articles)} if articles else {}
    profile_style_counts = {f"{profile['style']}:{profile['confidence']}": len(articles)} if articles else {}
    manifest = {
        "generated_at": now(),
        "source_kind": "converted_stage_roots",
        "source_roots": [str(root) for root in roots],
        "out_dir": str(out_dir),
        "code_commit": git_short_head(),
        "working_tree_dirty": git_dirty(),
        "article_count": len(articles),
        "profile_status_counts": profile_status_counts,
        "profile_style_counts": profile_style_counts,
        "articles": articles,
    }
    assessment = {
        "generated_at": now(),
        "source_kind": "converted_stage_roots",
        "article_count": len(assessments),
        "run_dir": str(out_dir),
        "code_commit": git_short_head(),
        "working_tree_dirty": git_dirty(),
        "totals": totals,
        "profile_status_counts": profile_status_counts,
        "profile_style_counts": profile_style_counts,
        "problematic_articles": problematic,
        "articles": assessments,
    }
    write_json(out_dir / "manifest.json", manifest)
    write_json(out_dir / "assessment.json", assessment)
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
        article = article_name_from_stage(raw_path)
        article_id = converted_article_id(raw_path, index)
        out_raw = raw_cache / f"{article_id}.{RAW_STAGE}"
        out_profile = profiles / f"{article_id}.citation_profile.json"
        shutil.copy2(raw_path, out_raw)
        raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
        profile = _converted_raw_citation_profile(raw_html, raw_path)
        write_json(out_profile, profile)
        profile_status_counts[profile["status"]] += 1
        profile_style_counts[f"{profile['style']}:{profile['confidence']}"] += 1
        articles.append(
            {
                "index": index,
                "article_id": article_id,
                "article": article,
                "article_dir": str(article_dir_from_stage(raw_path)),
                "raw_stage_path": str(raw_path),
                "source_polish_path": str(polish_path),
                "polish_stage_path": str(polish_path),
                "raw_cache_path": str(out_raw),
                "profile_path": str(out_profile),
                "artifact_hint": artifact_hint(raw_path),
                "profile_status": profile["status"],
                "citation_style": profile["style"],
                "citation_confidence": profile["confidence"],
            }
        )

    manifest = {
        "generated_at": now(),
        "source_kind": "converted_raw_cache",
        "source_roots": [str(root) for root in roots],
        "out_dir": str(out_dir),
        "code_commit": git_short_head(),
        "working_tree_dirty": git_dirty(),
        "raw_count": len(articles),
        "article_count": len(articles),
        "raw_cache_dir": str(raw_cache),
        "profile_dir": str(profiles),
        "profile_status_counts": dict(sorted(profile_status_counts.items())),
        "profile_style_counts": dict(sorted(profile_style_counts.items())),
        "articles": articles,
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest
