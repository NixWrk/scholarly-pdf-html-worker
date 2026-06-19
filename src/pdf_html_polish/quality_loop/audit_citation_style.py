"""Citation-style consistency diagnostics for EN polish audits."""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from pdf_html_polish.quality_loop.audit_blocks import Block, Defect, strip_tags
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect


REF_ANCHOR_BODY_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<num>\d+)['\"][^>]*>"
    r"(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
AUTHOR_YEAR_STYLE_TEXT_RE = re.compile(
    r"\b"
    r"[A-Z][A-Za-z'\u2019.-]+"
    r"(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'\u2019.-]+|&\s*[A-Z][A-Za-z'\u2019.-]+))?"
    r"(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)


def numeric_ref_label_numbers(label: str) -> list[int]:
    if re.fullmatch(r"[\s\(\)\[\],.;:\-\u2010-\u2014\d]+", label) is None:
        return []
    numbers = [int(value) for value in re.findall(r"\d{1,4}", label)]
    if any(value.startswith("0") for value in re.findall(r"\d{2,4}", label)):
        return []
    return [number for number in numbers if not (1800 <= number <= 2099)]


def paren_numeric_ref_link_count(
    body_blocks: Iterable[Block],
    *,
    ref_anchor_body_re: re.Pattern[str] = REF_ANCHOR_BODY_RE,
) -> int:
    count = 0
    for block in body_blocks:
        for match in ref_anchor_body_re.finditer(block.raw):
            if "<sup" in block.raw[max(0, match.start() - 40) : match.start()].lower():
                continue
            label = strip_tags(match.group("body")).strip()
            if not numeric_ref_label_numbers(label):
                continue
            left_text = strip_tags(block.raw[max(0, match.start() - 40) : match.start()])
            right_text = strip_tags(block.raw[match.end() : match.end() + 80])
            if (
                re.search(r"\(\s*$", left_text) is not None
                or label.startswith("(")
                or re.match(r"^\s*(?:[,;\-\u2010-\u2014]\s*\d|\))", right_text) is not None
            ):
                count += 1
    return count


def ref_anchor_is_bracketed_numeric_citation(block_raw: str, match: re.Match[str]) -> bool:
    label = strip_tags(match.group("body")).strip()
    if not numeric_ref_label_numbers(label):
        return False
    if label.lstrip().startswith("[") or label.rstrip().endswith("]"):
        return True
    left_text = strip_tags(block_raw[max(0, match.start() - 24) : match.start()])
    right_text = strip_tags(block_raw[match.end() : match.end() + 36])
    return (
        re.search(r"\[\s*$", left_text) is not None
        and re.match(r"^\s*(?:[,;]\s*\d|\])", right_text) is not None
    )


def citation_style_consistency_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
    pdf_link_summary: dict[str, Any] | None = None,
    stage: str,
    non_reference_body_blocks: Callable[[list[Block]], Iterable[Block]],
    block_is_float_or_table_context: Callable[[Block], bool],
    ref_anchor_body_re: re.Pattern[str] = REF_ANCHOR_BODY_RE,
    author_year_style_text_re: re.Pattern[str] = AUTHOR_YEAR_STYLE_TEXT_RE,
) -> list[Defect]:
    del polish_html

    body_blocks = list(non_reference_body_blocks(polish_blocks))
    body_text = " ".join(block.text for block in body_blocks)
    html_author_year_count = len(author_year_style_text_re.findall(body_text))
    pdf_author_year_count = len(author_year_style_text_re.findall(pdf_text)) if pdf_text else 0
    pdf_link_summary = pdf_link_summary or {}
    pdf_citation_dest_links = int(pdf_link_summary.get("pdf_citation_dest_links") or 0)
    pdf_author_year_link_labels = int(pdf_link_summary.get("pdf_author_year_link_labels") or 0)
    pdf_author_year_evidence = pdf_citation_dest_links >= 5 and pdf_author_year_link_labels >= 2
    html_author_year_evidence = html_author_year_count >= 6
    if not (pdf_author_year_evidence or html_author_year_evidence):
        return []

    bracket_citation_count = len(re.findall(r"\[\s*\d", body_text))
    numeric_ref_link_count = sum(
        1
        for block in body_blocks
        for match in ref_anchor_body_re.finditer(block.raw)
        if numeric_ref_label_numbers(strip_tags(match.group("body")))
    )
    numeric_sup_ref_link_count = sum(
        1
        for block in body_blocks
        for match in ref_anchor_body_re.finditer(block.raw)
        if numeric_ref_label_numbers(strip_tags(match.group("body")))
        and "<sup" in block.raw[max(0, match.start() - 40) : match.start()].lower()
    )
    numeric_citation_dominant = (
        numeric_ref_link_count >= 5 and numeric_sup_ref_link_count >= 5
    ) or (
        numeric_ref_link_count >= 10 and numeric_sup_ref_link_count >= 3
    )
    paren_numeric_count = paren_numeric_ref_link_count(body_blocks, ref_anchor_body_re=ref_anchor_body_re)
    if (numeric_citation_dominant or paren_numeric_count >= 5) and not pdf_author_year_evidence:
        return []
    if bracket_citation_count >= 4 and not pdf_author_year_evidence:
        return []

    for block in body_blocks:
        if block_is_float_or_table_context(block):
            continue
        for match in ref_anchor_body_re.finditer(block.raw):
            label = strip_tags(match.group("body"))
            numbers = numeric_ref_label_numbers(label)
            if not numbers:
                continue
            if ref_anchor_is_bracketed_numeric_citation(block.raw, match):
                continue
            text_window = strip_tags(block.raw[max(0, match.start() - 180) : match.end() + 180])
            if re.search(r"\b(?:Fig\.?|Figs\.?|Figure|Table|Eqn?\.?|Equation)\b", text_window, re.IGNORECASE):
                continue
            return [
                make_defect(
                    defect_id="P98",
                    cc_class="CC-02/CC-13/CC-14",
                    check="Numeric-only bibliography link appears in author-year article",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=stage,
                    hypothesis="Article-level citation style evidence was author-year, but numeric citation fallback still created a bibliography link.",
                    proposed_fix_layer="PDF citation-profile driven article-level citation-style lock",
                    regression_test="When PDF link labels or HTML body evidence prove author-year style, numeric-only body #ref links are unwrapped.",
                    extra={
                        "label": label,
                        "ref_target": match.group("num"),
                        "html_author_year_count": html_author_year_count,
                        "pdf_author_year_count": pdf_author_year_count,
                        "pdf_citation_dest_links": pdf_citation_dest_links,
                        "pdf_author_year_link_labels": pdf_author_year_link_labels,
                    },
                )
            ]
    return []
