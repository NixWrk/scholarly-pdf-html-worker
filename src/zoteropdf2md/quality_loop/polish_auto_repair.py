"""Local polish-stage auto-repair helpers."""

from __future__ import annotations

from typing import Any
import re

from zoteropdf2md.single_file_html import (
    _current_figure_target_keys,
    _link_spaced_multipanel_figure_refs,
)

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
AUTHOR_YEAR_NAME_LABEL_RE = re.compile(
    r"^[A-Z][A-Za-z'\u2019.-]{2,}"
    r"(?:\s+(?:et\s+al\.?|[A-Z][A-Za-z'\u2019.-]{2,}|(?:and|&)\s+[A-Z][A-Za-z'\u2019.-]{2,}))*\.?$",
    re.IGNORECASE,
)
AUTHOR_YEAR_RIGHT_CONTEXT_RE = re.compile(
    r"^\s*(?:et\s+al\.?|(?:and|&)\s+[A-Z][A-Za-z'\u2019.-]+)?\s*,?\s*\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
AUTHOR_YEAR_AUTHOR_LIST_RIGHT_CONTEXT_RE = re.compile(
    r"^\s*,?\s*(?:[A-Z][A-Za-z'\u2019.-]+|(?:and|&)\s+[A-Z][A-Za-z'\u2019.-]+)"
    r"(?:\s*,\s*(?:[A-Z][A-Za-z'\u2019.-]+|(?:and|&)\s+[A-Z][A-Za-z'\u2019.-]+))*"
    r"\s*,?\s*\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
REFERENCES_HEADING_RE = re.compile(r"<h[1-6]\b[^>]*>\s*(?:References|Bibliography|Works cited)\s*</h[1-6]>", re.IGNORECASE)
SUPPORTED_AUTO_REPAIR_DEFECT_IDS = {"P04", "P04N", "P17", "P55", "P59", "P96", "P97", "P98"}
AUTHOR_YEAR_LABEL_STOPWORDS = {
    "appendix",
    "chapter",
    "eq",
    "equation",
    "fig",
    "figure",
    "image",
    "map",
    "panel",
    "section",
    "table",
}
REF_ID_RE = re.compile(r"\bid\s*=\s*['\"]ref-(?P<num>\d{1,4})['\"]", re.IGNORECASE)
EXTERNAL_NUMERIC_CITATION_ANCHOR_RE = re.compile(
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>['\"])(?P<href>[^'\"]+)(?P=quote)[^>]*)>"
    r"(?P<body>[\s\S]{0,260}?)</a>",
    re.IGNORECASE,
)
BRACKET_NUMERIC_CITATION_LABEL_RE = re.compile(
    r"^\s*(?P<bracket>\[\s*(?P<body>\d{1,4}(?:\s*(?:[,;]|\-|\u2013|\u2014)\s*\d{1,4}){0,24})\s*\])"
    r"(?P<trail>[.,;:]?)\s*$"
)


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
        selected = defect_ids & SUPPORTED_AUTO_REPAIR_DEFECT_IDS
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


def reference_target_numbers(html: str) -> set[int]:
    return {int(match.group("num")) for match in REF_ID_RE.finditer(html)}


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
    if not cleaned[:1].isupper():
        return False
    first_token = re.split(r"\s+", cleaned, maxsplit=1)[0].strip(".").casefold()
    if first_token in AUTHOR_YEAR_LABEL_STOPWORDS:
        return False
    if (
        AUTHOR_YEAR_SURNAME_FRAGMENT_RE.fullmatch(cleaned) is None
        and AUTHOR_YEAR_NAME_LABEL_RE.fullmatch(cleaned) is None
    ):
        return False
    return (
        AUTHOR_YEAR_RIGHT_CONTEXT_RE.match(right_text) is not None
        or AUTHOR_YEAR_AUTHOR_LIST_RIGHT_CONTEXT_RE.match(right_text) is not None
    )


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


def relink_spaced_multipanel_figure_refs(html: str) -> tuple[str, int]:
    figure_targets = _current_figure_target_keys(html)
    if not figure_targets:
        return html, 0
    before_count = html.count("z2m-fig-link")
    repaired = _link_spaced_multipanel_figure_refs(html, figure_targets)
    if repaired == html:
        return html, 0
    return repaired, max(1, repaired.count("z2m-fig-link") - before_count)


def _render_numeric_bracket_citation_label(label: str, ref_numbers: set[int]) -> str | None:
    match = BRACKET_NUMERIC_CITATION_LABEL_RE.fullmatch(label)
    if match is None:
        return None
    body = match.group("body")
    tokens = re.findall(r"\d{1,4}", body)
    if not tokens or any(len(token) > 1 and token.startswith("0") for token in tokens):
        return None
    numbers = [int(token) for token in tokens]
    if any(number not in ref_numbers or 1800 <= number <= 2099 for number in numbers):
        return None

    def link_number(number_match: re.Match[str]) -> str:
        number_text = number_match.group(0)
        number = int(number_text)
        return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'

    if len(numbers) == 1 and body.strip().isdigit():
        number = numbers[0]
        return f'<a href="#ref-{number}" class="z2m-ref-link">[{number}]</a>{match.group("trail")}'
    linked_body = re.sub(r"\d{1,4}", link_number, body)
    return f'[{linked_body}]{match.group("trail")}'


def relink_external_numeric_citation_anchors(html: str) -> tuple[str, int]:
    ref_numbers = reference_target_numbers(html)
    if not ref_numbers or "<a" not in html:
        return html, 0
    before_references, references_and_after = split_before_references_for_repair(html)
    repairs = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal repairs
        href = (match.group("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            return match.group(0)
        body = match.group("body")
        if "#ref-" in body or "z2m-ref-link" in body:
            return match.group(0)
        rendered = _render_numeric_bracket_citation_label(visible_html_text(body), ref_numbers)
        if rendered is None:
            return match.group(0)
        repairs += 1
        return rendered

    repaired_before = EXTERNAL_NUMERIC_CITATION_ANCHOR_RE.sub(replace, before_references)
    return repaired_before + references_and_after, repairs
