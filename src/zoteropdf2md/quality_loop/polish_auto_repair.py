"""Local polish-stage auto-repair helpers."""

from __future__ import annotations

from typing import Any
import re

from .converted_runs import visible_html_text


REF_TARGET_BLOCK_RE = re.compile(
    r"<(?P<tag>li|p|div)\b(?P<attrs>[^>]*\bid\s*=\s*([\"'])ref-(?P<num>\d{1,4})\3[^>]*)>"
    r"(?P<body>[\s\S]*?)</(?P=tag)>",
    re.IGNORECASE,
)
VISIBLE_REF_PREFIX_RE = re.compile(r"^\s*(?:\[\s*(?P<bracket>\d{1,4})\s*\]|(?P<plain>\d{1,4})[.)])")
AUTHOR_YEAR_NUMERIC_REF_ANCHOR_RE = re.compile(
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*([\"'])#ref-(?P<num>\d{1,4})\2[^>]*)>"
    r"(?P<body>[\s\S]{0,120}?)</a>",
    re.IGNORECASE,
)
AUTHOR_YEAR_REF_ANCHOR_RE = re.compile(
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*([\"'])#ref-(?P<num>\d{1,4})\2[^>]*)>"
    r"(?P<body>[\s\S]{0,180}?)</a>",
    re.IGNORECASE,
)
AUTHOR_YEAR_TEXT_RE = re.compile(
    r"\b[A-Z][A-Za-z'\u2019.-]+(?:\s+et\s+al\.?)?(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
AUTHOR_YEAR_SURNAME_FRAGMENT_RE = re.compile(r"^[A-Z][A-Za-z'\u2019.-]{3,}$")
AUTHOR_YEAR_RIGHT_CONTEXT_RE = re.compile(
    r"^\s*(?:et\s+al\.?|(?:and|&)\s+[A-Z][A-Za-z'\u2019.-]+)?\s*,?\s*\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
REFERENCES_HEADING_RE = re.compile(r"<h[1-6]\b[^>]*>\s*(?:References|Bibliography|Works cited)\s*</h[1-6]>", re.IGNORECASE)


def audit_defect_ids(article: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("defects_found", "defects"):
        for defect in article.get(key) or []:
            if isinstance(defect, dict) and defect.get("id"):
                ids.add(str(defect.get("id")))
    return ids


def audit_articles_by_auto_repair_need(audit_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    articles: dict[str, dict[str, Any]] = {}
    for article in audit_report.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        defect_ids = audit_defect_ids(article)
        selected = defect_ids & {"P55", "P96", "P97", "P98"}
        if not selected:
            continue
        articles[article_id] = {"article": article, "defect_ids": sorted(selected)}
    return articles


def visible_ref_prefix_number(text: str) -> int | None:
    match = VISIBLE_REF_PREFIX_RE.match(text)
    if match is None:
        return None
    value = match.group("bracket") or match.group("plain")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def repair_visible_reference_numbers(html: str) -> tuple[str, int]:
    repairs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal repairs
        try:
            number = int(match.group("num"))
        except ValueError:
            return match.group(0)
        body = match.group("body")
        visible_number = visible_ref_prefix_number(visible_html_text(body))
        if visible_number == number:
            return match.group(0)
        if visible_number is not None:
            return match.group(0)
        repairs += 1
        prefix = f'<span class="z2m-ref-num">{number}.</span> '
        return f"<{match.group('tag')}{match.group('attrs')}>{prefix}{body}</{match.group('tag')}>"

    repaired = REF_TARGET_BLOCK_RE.sub(replace, html)
    return repaired, repairs


def split_before_references_for_repair(html: str) -> tuple[str, str]:
    positions: list[int] = []
    heading = REFERENCES_HEADING_RE.search(html)
    if heading is not None:
        positions.append(heading.start())
    first_ref = REF_TARGET_BLOCK_RE.search(html)
    if first_ref is not None:
        positions.append(first_ref.start())
    if not positions:
        return html, ""
    split_at = min(positions)
    return html[:split_at], html[split_at:]


def numeric_ref_anchor_label_numbers(label: str) -> list[int]:
    if re.fullmatch(r"[\s\(\)\[\],.;:\-\u2010-\u2014\d]+", label) is None:
        return []
    values = re.findall(r"\d{1,4}", label)
    if any(value.startswith("0") for value in re.findall(r"\d{2,4}", label)):
        return []
    numbers = [int(value) for value in values]
    return [number for number in numbers if not (1800 <= number <= 2099)]


def unwrap_author_year_numeric_ref_links(html: str) -> tuple[str, int]:
    before_references, references_and_after = split_before_references_for_repair(html)
    repairs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal repairs
        label = visible_html_text(match.group("body"))
        if not numeric_ref_anchor_label_numbers(label):
            return match.group(0)
        repairs += 1
        return match.group("body")

    repaired_before = AUTHOR_YEAR_NUMERIC_REF_ANCHOR_RE.sub(replace, before_references)
    return repaired_before + references_and_after, repairs


def looks_like_author_year_ref_anchor(label: str, right_text: str) -> bool:
    if AUTHOR_YEAR_TEXT_RE.search(label) is not None:
        return True
    cleaned = re.sub(r"\s+", " ", label).strip(" ([{,;")
    if AUTHOR_YEAR_SURNAME_FRAGMENT_RE.fullmatch(cleaned) is None:
        return False
    return AUTHOR_YEAR_RIGHT_CONTEXT_RE.match(right_text) is not None


def unwrap_author_year_ref_anchors(html: str) -> tuple[str, int]:
    before_references, references_and_after = split_before_references_for_repair(html)
    repairs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal repairs
        label = visible_html_text(match.group("body"))
        right_text = visible_html_text(before_references[match.end() : match.end() + 140])
        if not looks_like_author_year_ref_anchor(label, right_text):
            return match.group(0)
        repairs += 1
        return match.group("body")

    repaired_before = AUTHOR_YEAR_REF_ANCHOR_RE.sub(replace, before_references)
    return repaired_before + references_and_after, repairs
