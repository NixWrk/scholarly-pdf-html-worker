"""Converted-stage and cached-run preparation helpers for the quality loop."""

from __future__ import annotations

from collections import Counter
from html import unescape
import re
import urllib.parse
from pathlib import Path
from typing import Any, Iterable
from pdf_html_polish.artifact_integrity import fingerprint_file

from pdf_html_polish.atomic_io import copy_file_atomic
from pdf_html_polish.quality_loop.cached_run_state import (
    CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
    cached_repolish_artifact_fingerprints,
    validate_cached_repolish_source,
    path_is_link_like,
)
from pdf_html_polish.citation_profile import infer_citation_style_from_text
from pdf_html_polish.html_links import count_same_document_absolute_fragment_links
from pdf_html_polish.html_stages import (
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    RawConversionValidation,
    require_current_raw_conversions,
)
from pdf_html_polish.raw_html_polish.references_links import references_heading_search
from pdf_html_polish.raw_html_polish.references_links import (
    LI_BLOCK_PATTERN,
    P_BLOCK_PATTERN,
    reference_visible_number,
)

from .run_utils import (
    article_dir_from_stage,
    article_name_from_stage,
    artifact_hint,
    converted_article_id,
    git_dirty,
    git_short_head,
    json_object,
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
NUMERIC_SUPERSCRIPT_LABEL_RE = re.compile(
    r"^\s*[\[(]?\d{1,3}(?:\s*(?:[,;]|-|\u2013|\u2014)\s*\d{1,3}){0,12}[\])]?\s*[.,;]?\s*$"
)
PAGE_ANCHOR_RE = re.compile(
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\1[^>]*>(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
EMBEDDED_NUMBERED_REFERENCE_RE = re.compile(
    r"(?<!\d)(?P<number>[1-9]\d{0,2})[.)]\s+(?=[A-Z\u00c0-\u00de])"
)
UNHEADED_REFERENCE_LIST_BLOCK_RE = re.compile(
    r"(?:<p\b[^>]*>\s*)?<[ou]l\b[\s\S]*?</[ou]l>(?:\s*</p>)?",
    re.IGNORECASE,
)
FLATTENED_NUMERIC_CITATION_HINT_RE = re.compile(
    r"\b(?:et\s+al\.?\s*|[A-Za-z]{5,}\.)(?P<number>\d{1,3})(?!\s*\d)(?=[\s,.;)])",
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


def _numeric_superscript_hint_count(html: str) -> int:
    normalized_html = unescape(html)
    return sum(
        NUMERIC_SUPERSCRIPT_LABEL_RE.fullmatch(visible_html_text(match.group(0))) is not None
        for match in SUP_BLOCK_RE.finditer(normalized_html)
    )


def _flattened_numeric_citation_hint_count(html: str, max_reference: int) -> int:
    if max_reference <= 0:
        return 0
    text = _html_plain_text_for_profile(html)
    return sum(
        1
        for match in FLATTENED_NUMERIC_CITATION_HINT_RE.finditer(text)
        if 1 <= int(match.group("number")) <= max_reference
    )


def _numeric_page_anchor_hint_count(html: str) -> int:
    return sum(
        NUMERIC_SUPERSCRIPT_LABEL_RE.fullmatch(visible_html_text(match.group("body"))) is not None
        for match in PAGE_ANCHOR_RE.finditer(html)
    )


def _numbered_reference_hint_count(bibliography_html: str) -> int:
    numbers: set[int] = set()
    for match in LI_BLOCK_PATTERN.finditer(bibliography_html):
        number = reference_visible_number(match.group(2) or "")
        if number is not None:
            numbers.add(number)
    for match in P_BLOCK_PATTERN.finditer(bibliography_html):
        number = reference_visible_number(match.group("body") or "")
        if number is not None:
            numbers.add(number)

    bibliography_text = _html_plain_text_for_profile(bibliography_html)
    embedded_numbers = {
        int(match.group("number"))
        for match in EMBEDDED_NUMBERED_REFERENCE_RE.finditer(bibliography_text)
    }
    return max(len(numbers), len(embedded_numbers))


def _unheaded_numbered_reference_start(raw_html: str) -> int | None:
    for match in UNHEADED_REFERENCE_LIST_BLOCK_RE.finditer(raw_html):
        block = match.group(0)
        numbers: list[int] = []
        for li_match in LI_BLOCK_PATTERN.finditer(block):
            number = reference_visible_number(li_match.group(2) or "")
            if number is None:
                break
            numbers.append(number)
            if len(numbers) >= 4:
                break
        if len(numbers) < 3 or numbers[:3] != [1, 2, 3]:
            continue
        left_text = visible_html_text(
            raw_html[max(0, match.start() - 1800) : match.start()]
        ).casefold()
        if "acknowledg" in left_text or match.start() > int(len(raw_html) * 0.55):
            return match.start()
    return None


def _is_data_availability_reference_number(ref_match: re.Match[str], html: str) -> bool:
    body_text = visible_html_text(ref_match.group("body"))
    if not BRACKET_NUMERIC_REF_TEXT_RE.fullmatch(body_text):
        return False
    prefix = visible_html_text(html[max(0, ref_match.start() - 700) : ref_match.start()])
    suffix = visible_html_text(html[ref_match.end() : min(len(html), ref_match.end() + 160)])
    near_text = f"{prefix[-500:]} {body_text} {suffix[:160]}"
    return bool(REFERENCE_NUMBER_BRACKET_RE.search(near_text) and DATA_AVAILABILITY_CONTEXT_RE.search(near_text))


def _is_table_reference_column_link(ref_match: re.Match[str], html: str) -> bool:
    body_text = visible_html_text(ref_match.group("body"))
    if not BRACKET_NUMERIC_REF_TEXT_RE.fullmatch(body_text):
        return False
    cell_start = max(
        html.rfind("<td", 0, ref_match.start()),
        html.rfind("<th", 0, ref_match.start()),
    )
    if cell_start < 0:
        return False
    previous_cell_close = max(
        html.rfind("</td>", 0, ref_match.start()),
        html.rfind("</th>", 0, ref_match.start()),
    )
    if previous_cell_close > cell_start:
        return False
    cell_end_candidates = [
        index
        for index in (
            html.find("</td>", ref_match.end()),
            html.find("</th>", ref_match.end()),
        )
        if index >= 0
    ]
    if not cell_end_candidates:
        return False
    cell_end = min(cell_end_candidates)
    if visible_html_text(html[cell_start: cell_end + 5]) != body_text:
        return False
    table_start = html.rfind("<table", 0, ref_match.start())
    if table_start < 0 or html.rfind("</table>", 0, ref_match.start()) > table_start:
        return False
    header_end = html.find("</tr>", table_start)
    if header_end < 0 or header_end > ref_match.start():
        return False
    header_text = visible_html_text(html[table_start: header_end])
    return bool(re.search(r"\breferences?\b", header_text, re.IGNORECASE))


def _is_bracket_ref_link_for_style(ref_match: re.Match[str], html: str) -> bool:
    body_text = visible_html_text(ref_match.group("body"))
    if "[" not in body_text or "]" not in body_text:
        return False
    return not (
        _is_data_availability_reference_number(ref_match, html)
        or _is_table_reference_column_link(ref_match, html)
    )


def _converted_raw_citation_profile(raw_html: str, raw_path: Path) -> dict[str, Any]:
    references_heading = references_heading_search(raw_html, allow_notes_heading=True)
    if references_heading is not None:
        profile_html = raw_html[: references_heading.start()]
        bibliography_html = raw_html[references_heading.end() :]
    else:
        unheaded_start = _unheaded_numbered_reference_start(raw_html)
        if unheaded_start is None:
            profile_html = raw_html
            bibliography_html = raw_html[len(raw_html) // 2 :]
        else:
            profile_html = raw_html[:unheaded_start]
            bibliography_html = raw_html[unheaded_start:]
    text = _html_plain_text_for_profile(profile_html)
    numbered_reference_hints = _numbered_reference_hint_count(bibliography_html)
    tagged_superscript_hints = _numeric_superscript_hint_count(profile_html)
    flattened_superscript_hints = _flattened_numeric_citation_hint_count(
        profile_html, numbered_reference_hints
    )
    superscript_hints = (
        tagged_superscript_hints + flattened_superscript_hints
        if numbered_reference_hints >= 5 else 0
    )
    numeric_page_anchor_hints = _numeric_page_anchor_hint_count(profile_html)
    numeric_structure_hints = max(numbered_reference_hints, numeric_page_anchor_hints)
    inferred_style, inferred_confidence, paren_count, bracket_count = infer_citation_style_from_text(
        text,
        superscript_hint_count=superscript_hints,
        numeric_structure_hint_count=numeric_structure_hints,
        numbered_reference_hint_count=numbered_reference_hints,
    )
    body_only_style, body_only_confidence, _, _ = infer_citation_style_from_text(
        text,
        superscript_hint_count=superscript_hints,
        numeric_structure_hint_count=numeric_page_anchor_hints,
        numbered_reference_hint_count=0,
    )
    initial_numeric_style_is_usable = (
        inferred_confidence == "high"
        or (
            inferred_confidence == "medium"
            and inferred_style in {"bracket_numeric", "superscript_numeric"}
            and numbered_reference_hints >= 5
        )
    )
    if (
        not initial_numeric_style_is_usable
        and inferred_style != "author_year"
        and body_only_style == "author_year"
    ):
        inferred_style, inferred_confidence = body_only_style, body_only_confidence
    evidence_backed_medium_numeric = (
        inferred_confidence == "medium"
        and inferred_style in {"bracket_numeric", "superscript_numeric"}
        and numbered_reference_hints >= 5
    )
    usable_inferred_style = (
        inferred_confidence == "high"
        or (inferred_style == "author_year" and inferred_confidence == "medium")
        or evidence_backed_medium_numeric
    )
    style = inferred_style if usable_inferred_style else "unknown"
    confidence = inferred_confidence if usable_inferred_style else "low"
    return {
        "status": "converted_raw_html_inferred",
        "style": style,
        "confidence": confidence,
        "source": "converted_raw_html",
        "source_policy": "use_high_confidence_or_evidence_backed_medium_inferred_style",
        "inferred_style": inferred_style,
        "inferred_confidence": inferred_confidence,
        "body_only_inferred_style": body_only_style,
        "body_only_inferred_confidence": body_only_confidence,
        "source_raw_stage_path": str(raw_path),
        "paren_numeric_count": paren_count,
        "bracket_numeric_count": bracket_count,
        "numeric_superscript_hint_count": tagged_superscript_hints,
        "flattened_numeric_citation_hint_count": flattened_superscript_hints,
        "numeric_page_anchor_hint_count": numeric_page_anchor_hints,
        "numbered_reference_hint_count": numbered_reference_hints,
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
        href_counts = json_object(article.get("href_counts"))
        for key, value in href_counts.items():
            totals[key] = totals.get(key, 0) + int(value)
            if value:
                problematic.setdefault(key, []).append(article_id)
        for key in ("table_units_with_section_ids", "sup_ref_links", "bracket_ref_links", "missing_warning_count"):
            totals[key] = totals.get(key, 0) + int(article.get(key) or 0)
        if article.get("mixed_citation_style"):
            problematic.setdefault("mixed_citation_style", []).append(article_id)
    return dict(sorted(totals.items())), {key: sorted(value) for key, value in sorted(problematic.items())}


def find_converted_raw_stages(roots: Iterable[Path]) -> list[Path]:
    """Find production raw stages without requiring a previous polish artifact."""

    raw_stages: set[Path] = set()
    for root in roots:
        if root.is_file():
            if root.name == RAW_STAGE:
                raw_stages.add(root.resolve(strict=False))
            elif root.name == POLISH_STAGE and (root.parent / RAW_STAGE).is_file():
                raw_stages.add((root.parent / RAW_STAGE).resolve(strict=False))
        elif root.exists():
            raw_stages.update(
                raw_path.resolve(strict=False)
                for raw_path in root.rglob(RAW_STAGE)
                if raw_path.is_file()
            )
    return sorted(raw_stages, key=str)


def find_converted_stage_pairs(roots: Iterable[Path]) -> list[tuple[Path, Path]]:
    """Find existing production ``01.en.raw.html`` -> ``02.en.polish.html`` pairs."""

    return [
        (raw_path, (raw_path.parent / POLISH_STAGE).resolve(strict=False))
        for raw_path in find_converted_raw_stages(roots)
        if (raw_path.parent / POLISH_STAGE).is_file()
    ]


def _validated_raw_sources(
    raw_stage_paths: Iterable[Path],
) -> dict[Path, RawConversionValidation]:
    validations = require_current_raw_conversions(raw_stage_paths)
    return {
        validation.raw_stage_path.resolve(strict=False): validation
        for validation in validations
    }


def _validated_source_record(validation: RawConversionValidation) -> dict[str, Any]:
    assert validation.source_pdf_path is not None
    return {
        "source_pdf_path": str(validation.source_pdf_path),
        "source_pdf_origin": "raw_conversion_manifest",
        "raw_conversion_manifest_path": str(validation.manifest_path),
        "raw_conversion_manifest_schema_version": validation.schema_version,
    }


def _reject_existing_raw_cache_artifacts(out_dir: Path) -> None:
    if not out_dir.exists():
        return
    entries = sorted(out_dir.iterdir(), key=lambda path: path.name.casefold())
    if not entries:
        return
    owned_names = {"raw_cache", "profiles", "manifest.json"}
    kind = "owned artifacts" if any(path.name in owned_names for path in entries) else "artifacts"
    raise FileExistsError(
        f"Converted raw cache already contains {kind}: "
        + ", ".join(str(path) for path in entries)
    )


def _copy_validated_raw(
    validation: RawConversionValidation,
    destination: Path,
) -> None:
    copy_file_atomic(validation.raw_stage_path, destination)
    copied = fingerprint_file(destination, reject_symlink=True)
    if (
        copied is not None
        and copied.size == validation.raw_html_bytes
        and copied.sha256 == validation.raw_html_sha256
    ):
        return
    try:
        destination.unlink(missing_ok=True)
    except OSError:
        pass
    raise RuntimeError(
        "Copied raw stage does not match its validated conversion manifest: "
        f"{validation.raw_stage_path}"
    )


def prepare_converted_run(roots: list[Path], out_dir: Path) -> dict[str, Any]:
    """Prepare a loop run from existing Zotero converted stage directories.

    The audit still reads the original stage paths so local sidecar images and
    source PDFs resolve naturally.  Article ids are made unique in the loop
    artifacts because production converted trees can contain duplicate document
    names under different attachment/mtime directories.
    """

    out_dir = out_dir.resolve(strict=False)
    roots = [root.resolve(strict=False) for root in roots]
    raw_stages = find_converted_raw_stages(roots)
    validations_by_raw = _validated_raw_sources(raw_stages)
    missing_polish = [
        raw_path.parent / POLISH_STAGE
        for raw_path in raw_stages
        if not (raw_path.parent / POLISH_STAGE).is_file()
    ]
    if missing_polish:
        details = "; ".join(str(path) for path in missing_polish[:20])
        raise RuntimeError(f"Converted raw stages are missing polish artifacts: {details}")
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = [(raw_path, raw_path.parent / POLISH_STAGE) for raw_path in raw_stages]
    articles: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    profile = {"status": "not_applicable_converted_stage", "style": "unknown", "confidence": "low"}
    for index, (raw_path, polish_path) in enumerate(pairs, start=1):
        article = article_name_from_stage(raw_path)
        article_id = converted_article_id(raw_path, index)
        polish_html = polish_path.read_text(encoding="utf-8", errors="replace")
        article_record = {
            "index": index,
            "article_id": article_id,
            "article": article,
            "article_dir": str(article_dir_from_stage(raw_path)),
            "raw_stage_path": str(raw_path),
            "polish_stage_path": str(polish_path),
            "artifact_hint": artifact_hint(raw_path),
        }
        article_record.update(_validated_source_record(validations_by_raw[raw_path]))
        articles.append(article_record)
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

    out_candidate = Path(out_dir).expanduser()
    if path_is_link_like(out_candidate):
        raise ValueError(f"Converted raw cache path must not be link-like: {out_candidate}")
    out_dir = out_candidate.resolve(strict=False)
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"Converted raw cache path must be a directory: {out_dir}")
    _reject_existing_raw_cache_artifacts(out_dir)

    roots = [root.resolve(strict=False) for root in roots]
    raw_stages = find_converted_raw_stages(roots)
    if not raw_stages:
        raise ValueError("No committed converted raw stages were found for cached repolish.")
    validations_by_raw = _validated_raw_sources(raw_stages)
    _reject_existing_raw_cache_artifacts(out_dir)
    raw_cache = out_dir / "raw_cache"
    profiles = out_dir / "profiles"
    for path in (raw_cache, profiles):
        path.mkdir(parents=True, exist_ok=False)
    articles: list[dict[str, Any]] = []
    profile_status_counts: Counter[str] = Counter()
    profile_style_counts: Counter[str] = Counter()
    for index, raw_path in enumerate(raw_stages, start=1):
        polish_path = raw_path.parent / POLISH_STAGE
        article = article_name_from_stage(raw_path)
        article_id = converted_article_id(raw_path, index)
        out_raw = raw_cache / f"{article_id}.{RAW_STAGE}"
        out_profile = profiles / f"{article_id}.citation_profile.json"
        _copy_validated_raw(validations_by_raw[raw_path], out_raw)
        raw_html = out_raw.read_text(encoding="utf-8")
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
                "source_polish_present": polish_path.is_file(),
                "source_polish_path": str(polish_path),
                "polish_stage_path": str(polish_path),
                "raw_cache_path": str(out_raw),
                "profile_path": str(out_profile),
                "artifact_hint": artifact_hint(raw_path),
                "profile_status": profile["status"],
                "citation_style": profile["style"],
                "citation_confidence": profile["confidence"],
                **cached_repolish_artifact_fingerprints(out_raw, out_profile),
                **_validated_source_record(validations_by_raw[raw_path]),
            }
        )

    manifest = {
        "generated_at": now(),
        "source_snapshot_schema_version": CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
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
    validate_cached_repolish_source(out_dir)
    return manifest
