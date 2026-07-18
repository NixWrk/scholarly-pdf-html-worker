"""PDF-backed bibliography target recovery helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import re

from .converted_runs import visible_html_text


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
REF_HREF_RE = re.compile(r"\bhref\s*=\s*[\"']#ref-\d+[\"']", re.IGNORECASE)

ArticleSourcePdfCandidates = Callable[[Path, str, dict[str, Any], dict[str, Any]], list[dict[str, Any]]]
ExtractReferenceEntries = Callable[[Path], list[Any]]
SnapshotPdf = Callable[[Path], Path]


def reference_id_numbers(html: str) -> list[int]:
    return sorted(
        {
            int(match.group(1))
            for match in re.finditer(r"\bid\s*=\s*['\"]ref-(\d+)['\"]", html, re.IGNORECASE)
        }
    )


def reference_id_gap_numbers(html: str) -> list[int]:
    ids = reference_id_numbers(html)
    if len(ids) < 2:
        return []
    gaps: list[int] = []
    for left, right in zip(ids, ids[1:]):
        if 0 < right - left <= 25:
            gaps.extend(range(left + 1, right))
    return gaps


def expand_reference_candidate_numbers(value: str) -> list[int]:
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


def plain_reference_candidate_is_safe(text: str, match: re.Match[str]) -> bool:
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


def reference_recovery_block_is_protected(attrs: str, body: str) -> bool:
    lower = f"{attrs} {body}".lower()
    if REFERENCE_RECOVERY_PROTECTED_CLASS_RE.search(lower):
        return True
    if re.search(r"</?(?:table|thead|tbody|tfoot|tr|td|th|math|script|style|code|pre|figure|figcaption)\b", lower):
        return True
    if REF_HREF_RE.search(body):
        return True
    visible = visible_html_text(body)
    if len(visible) < 12:
        return True
    if re.match(r"^(?:fig(?:ure)?|table|eq(?:uation)?|appendix|supplement|formula)\b", visible, re.IGNORECASE):
        return True
    return False


def unlinked_body_reference_candidate_numbers(html: str) -> list[int]:
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
        if reference_recovery_block_is_protected(attrs, body):
            continue
        text = visible_html_text(body)
        for match in BRACKETED_BODY_REFERENCE_CANDIDATE_RE.finditer(text):
            numbers.extend(expand_reference_candidate_numbers(match.group("body")))
        for match in PLAIN_BODY_REFERENCE_CANDIDATE_RE.finditer(text):
            if not plain_reference_candidate_is_safe(text, match):
                continue
            numbers.extend(expand_reference_candidate_numbers(match.group("body")))

    deduped: list[int] = []
    seen: set[int] = set()
    for number in numbers:
        if number not in seen:
            seen.add(number)
            deduped.append(number)
    return sorted(deduped)


def pdf_reference_recovery_numbers(polished_html: str) -> tuple[list[int], str]:
    ref_ids = reference_id_numbers(polished_html)
    gap_numbers = reference_id_gap_numbers(polished_html)
    if gap_numbers:
        return gap_numbers, "gap"
    body_numbers = unlinked_body_reference_candidate_numbers(polished_html)
    if ref_ids:
        ref_set = set(ref_ids)
        missing_body_targets = [number for number in body_numbers if number not in ref_set]
        if missing_body_targets and any(number in ref_set for number in body_numbers):
            return missing_body_targets, "body_citation_missing_target"
        return [], ""
    if body_numbers:
        return body_numbers, "body_citation"
    return [], ""


def profile_has_reference_entries(profile: dict[str, Any]) -> bool:
    return bool(profile.get("reference_entries"))


def reference_entry_record(entry: Any) -> dict[str, Any]:
    return {
        "page": int(getattr(entry, "page", 0) or 0),
        "number": int(getattr(entry, "number", 0) or 0),
        "text": str(getattr(entry, "text", "") or ""),
    }


def enrich_profile_with_pdf_reference_entries_if_needed(
    profile: dict[str, Any],
    polished_html: str,
    source_run_dir: Path,
    article: str,
    manifest_article: dict[str, Any],
    pdf_reference_cache: dict[str, list[dict[str, Any]]],
    *,
    article_source_pdf_candidates: ArticleSourcePdfCandidates,
    extract_reference_entries: ExtractReferenceEntries,
    snapshot_pdf: SnapshotPdf,
) -> tuple[dict[str, Any], int, str]:
    if profile_has_reference_entries(profile):
        return profile, 0, ""
    recovery_numbers, recovery_trigger = pdf_reference_recovery_numbers(polished_html)
    if not recovery_numbers:
        return profile, 0, ""
    recovery_set = set(recovery_numbers)
    candidates = article_source_pdf_candidates(source_run_dir, article, {}, manifest_article)
    for candidate in candidates:
        if not candidate.get("exists"):
            continue
        pdf_path = Path(str(candidate.get("path") or "")).expanduser()
        if not pdf_path.is_file():
            continue
        cache_key = str(snapshot_pdf(pdf_path).resolve(strict=False))
        if cache_key not in pdf_reference_cache:
            pdf_reference_cache[cache_key] = [
                reference_entry_record(entry)
                for entry in extract_reference_entries(Path(cache_key))
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
