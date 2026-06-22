"""Citation-style consistency diagnostics for EN polish audits."""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from pdf_html_polish.quality_loop.audit_blocks import Block, Defect, normalize_ws, strip_tags
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect


REF_ANCHOR_BODY_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<num>\d+)['\"][^>]*>"
    r"(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
REF_LINK_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(\d+)['\"][^>]*>", re.IGNORECASE)
REF_ID_RE = re.compile(r"\bid\s*=\s*['\"]ref-\d+['\"]", re.IGNORECASE)
AUTHOR_YEAR_STYLE_TEXT_RE = re.compile(
    r"\b"
    r"[A-Z][A-Za-z'\u2019.-]+"
    r"(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'\u2019.-]+|&\s*[A-Z][A-Za-z'\u2019.-]+))?"
    r"(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
NONCITATION_CONTEXT_RE = re.compile(
    r"\b(?:pH|D\d|Vand|Aand|mAand|uAand|µAand|μAand)\b|"
    r"\b(?:week|month)\s+\d+\b|"
    r"\b(?:monkey|animal|female|male)\s+\d+\b|"
    r"\b(?:mm\s*s|cm\s*s|m\s*s|cm|mC|kg|mA|uA|µA|μA|MHz|GHz|kHz)\s*[-\u2212]\s*\d+\b|"
    r"\b(?:u|µ|μ)m\s*(?:1|2)\b",
    re.IGNORECASE,
)
ML_PER_SECOND_CONTEXT_RE = re.compile(r"\bmL\s*[:/]\s*s\s*\{?\s*[-\u2212]?\s*\d+\b", re.IGNORECASE)


def has_noncitation_context(text: str) -> bool:
    for match in NONCITATION_CONTEXT_RE.finditer(text):
        if match.group(0) == "pH" or match.group(0).lower() != "ph":
            return True
    return False


def numeric_ref_label_numbers(label: str) -> list[int]:
    if re.fullmatch(r"[\s\(\)\[\],.;:\-\u2010-\u2014\d]+", label) is None:
        return []
    numbers = [int(value) for value in re.findall(r"\d{1,4}", label)]
    if any(value.startswith("0") for value in re.findall(r"\d{2,4}", label)):
        return []
    return [number for number in numbers if not (1800 <= number <= 2099)]


def ref_anchor_visible_number(label: str) -> int | None:
    numbers = re.findall(r"\d+", label)
    if len(numbers) != 1:
        return None
    return int(numbers[0])


def ref_match_inside_bracketed_numeric_citation(raw: str, start: int, end: int) -> bool:
    ref_anchor = re.search(r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+", raw[start:end], re.IGNORECASE)
    anchor_start = start + ref_anchor.start() if ref_anchor is not None else start
    anchor_end = raw.find("</a>", end, min(len(raw), end + 160))
    if anchor_end >= 0:
        anchor_visible = normalize_ws(strip_tags(raw[start : anchor_end + len("</a>")]))
        if re.fullmatch(r"\[\s*\d{1,4}\s*\]\s*\.?", anchor_visible, re.IGNORECASE):
            return True
    left = raw.rfind("[", max(0, anchor_start - 240), anchor_start)
    if left < 0:
        return False
    right = raw.find("]", end, min(len(raw), end + 160))
    if right < 0:
        return False
    visible = normalize_ws(strip_tags(raw[left : right + 1]))
    return (
        re.fullmatch(
            r"\[\s*\d{1,4}(?:\s*(?:[,;]|[-\u2013\u2014]|\band\b)\s*\d{1,4})*\s*\]\s*\.?",
            visible,
            re.IGNORECASE,
        )
        is not None
    )


def ref_match_inside_sentence_final_superscript(raw: str, start: int, end: int) -> bool:
    sup_open = raw.rfind("<sup", 0, start)
    if sup_open < 0:
        return False
    prior_sup_close = raw.rfind("</sup", 0, start)
    if prior_sup_close > sup_open:
        return False
    sup_close = raw.find("</sup>", end)
    if sup_close < 0:
        return False
    before_text = strip_tags(raw[max(0, sup_open - 96) : sup_open]).rstrip()
    if not before_text or before_text[-1] not in ".!?)]":
        return False
    sup_body = raw[sup_open : sup_close + len("</sup>")]
    if not re.search(r'\bhref\s*=\s*["\']#ref-\d+["\']', sup_body, re.IGNORECASE):
        return False
    after_text = strip_tags(raw[sup_close + len("</sup>") : sup_close + len("</sup>") + 96]).lstrip()
    return not after_text or bool(re.match(r"(?:[A-Z]|\(|\[|,|;|:)", after_text))


def ref_match_inside_clean_superscript_citation(raw: str, start: int, end: int) -> bool:
    sup_open = raw.rfind("<sup", 0, start)
    if sup_open < 0:
        return False
    prior_sup_close = raw.rfind("</sup", 0, start)
    if prior_sup_close > sup_open:
        return False
    sup_close = raw.find("</sup>", end)
    if sup_close < 0:
        return False
    sup_body = raw[sup_open : sup_close + len("</sup>")]
    if not re.search(r'\bhref\s*=\s*["\']#ref-\d+["\']', sup_body, re.IGNORECASE):
        return False
    visible = normalize_ws(strip_tags(sup_body))
    return re.fullmatch(r"[\d,\s;.\-\u2010-\u2014]+", visible) is not None


def ref_match_inside_author_et_al_citation(raw: str, start: int, end: int) -> bool:
    left_text = strip_tags(raw[max(0, start - 96) : start]).rstrip()
    return re.search(r"\bet\s+al\.?\s*$", left_text, re.IGNORECASE) is not None


def ref_match_is_parenthetical_tail_citation(raw: str, start: int, end: int) -> bool:
    anchor_end = raw.find("</a>", end, min(len(raw), end + 160))
    if anchor_end < 0:
        return False
    anchor_visible = normalize_ws(strip_tags(raw[start : anchor_end + len("</a>")]))
    if re.fullmatch(r"\)\s*\d{1,4}\s*\.?", anchor_visible) is None:
        return False
    right_text = strip_tags(raw[anchor_end + len("</a>") : anchor_end + len("</a>") + 32]).lstrip()
    return not right_text or right_text[0] in ".,;)]"


def block_looks_like_author_affiliation_byline(block: Block) -> bool:
    text = normalize_ws(block.text)
    if len(text) > 1200:
        return False
    degree_hits = len(re.findall(r"\b(?:M\.D|Ph\.?D|F\.R\.C\.S|B\.Sc|M\.Sc)\.?", text, re.IGNORECASE))
    short_ref_hits = len(re.findall(r"(?:^|[\s,])\d{1,2}(?=\s|,|$)", text))
    return degree_hits >= 4 and short_ref_hits >= 4


def ref_visible_number_from_anchor(raw: str, start: int, end: int) -> tuple[int | None, int]:
    anchor_end = raw.find("</a>", end, min(len(raw), end + 200))
    if anchor_end < 0:
        return None, end
    label = normalize_ws(strip_tags(raw[start : anchor_end + len("</a>")]))
    number = ref_anchor_visible_number(label)
    return number, anchor_end + len("</a>")


def ref_match_is_month_word_citation(raw: str, start: int, end: int) -> bool:
    number, anchor_end = ref_visible_number_from_anchor(raw, start, end)
    if number is None or number <= 12:
        return False
    left_text = strip_tags(raw[max(0, start - 64) : start]).rstrip()
    right_text = strip_tags(raw[anchor_end : anchor_end + 32]).lstrip()
    return re.search(r"\bmonth\s*$", left_text, re.IGNORECASE) is not None and (
        not right_text or right_text[0] in ".,;:)]"
    )


def ref_match_is_measurement_parenthetical_citation(raw: str, start: int, end: int) -> bool:
    number, anchor_end = ref_visible_number_from_anchor(raw, start, end)
    if number is None:
        return False
    left_text = strip_tags(raw[max(0, start - 140) : start])
    right_text = strip_tags(raw[anchor_end : anchor_end + 48]).lstrip()
    if not right_text.startswith(")"):
        return False
    left_paren = left_text.rfind("(")
    right_paren = left_text.rfind(")")
    if left_paren < 0 or right_paren > left_paren:
        return False
    parenthetical = left_text[left_paren:]
    return bool(re.search(r"(?:%|mL\s*/\s*s|mL\s+s|mmHg|cmH2O|L\s*/\s*s)", parenthetical, re.IGNORECASE))


def ref_match_follows_figure_or_unit_parenthetical_citation(raw: str, start: int, end: int) -> bool:
    number, anchor_end = ref_visible_number_from_anchor(raw, start, end)
    if number is None:
        return False
    left_text = strip_tags(raw[max(0, start - 260) : start]).rstrip()
    right_text = strip_tags(raw[anchor_end : anchor_end + 48]).lstrip()
    if not left_text.endswith(")"):
        return False
    if right_text and right_text[0] not in ".,;:)]":
        return False
    right_paren = left_text.rfind(")")
    left_paren = left_text.rfind("(", 0, right_paren)
    if left_paren < 0:
        return False
    parenthetical = left_text[left_paren : right_paren + 1]
    return bool(
        re.search(r"\b(?:Fig|Figure)\.?\s*\d", parenthetical, re.IGNORECASE)
        or re.search(
            r"(?:%|mL\s*/\s*s|mL\s+s|mmHg|cmH2O|L\s*/\s*s|N\s*m\s*2|"
            r"(?:u|Вµ|Ој|μ)m\s*2|mm\s*2|cm\s*2)",
            parenthetical,
            re.IGNORECASE,
        )
    )


def ref_match_inside_animal_human_study_citation(raw: str, start: int, end: int) -> bool:
    window = normalize_ws(strip_tags(raw[max(0, start - 320) : min(len(raw), end + 320)]))
    return bool(
        re.search(
            r"\banimal\s*\d{1,3}\s+and\s+human\s+studies\s+of\s+retinal\s*\d{1,3}"
            r"(?:\s*,\s*\d{1,3})?\s+and\s+cortical\s*\d{1,3}\s+stimulat\w*",
            window,
            re.IGNORECASE,
        )
        or re.search(r"\breport\s+\d{1,3}\s+by\s+that\s+group\b", window, re.IGNORECASE)
    )


def linked_ref_near_non_citation_context(block: Block) -> bool:
    if block_looks_like_author_affiliation_byline(block):
        return False
    for match in REF_LINK_RE.finditer(block.raw):
        if ref_match_inside_bracketed_numeric_citation(block.raw, match.start(), match.end()):
            continue
        if ref_match_inside_clean_superscript_citation(block.raw, match.start(), match.end()):
            continue
        if ref_match_inside_sentence_final_superscript(block.raw, match.start(), match.end()):
            continue
        if ref_match_inside_author_et_al_citation(block.raw, match.start(), match.end()):
            continue
        if ref_match_is_parenthetical_tail_citation(block.raw, match.start(), match.end()):
            continue
        if ref_match_is_month_word_citation(block.raw, match.start(), match.end()):
            continue
        if ref_match_is_measurement_parenthetical_citation(block.raw, match.start(), match.end()):
            continue
        if ref_match_follows_figure_or_unit_parenthetical_citation(block.raw, match.start(), match.end()):
            continue
        if ref_match_inside_animal_human_study_citation(block.raw, match.start(), match.end()):
            continue
        window_raw = block.raw[max(0, match.start() - 48) : match.end() + 80]
        window_text = strip_tags(window_raw)
        context_text = re.sub(r"\bD\d-type\b", "D-type", window_text, flags=re.IGNORECASE)
        if re.search(r"\b[A-Za-z0-9]+-D\d+\s+\d{1,3}\b", context_text):
            continue
        if has_noncitation_context(context_text) or ML_PER_SECOND_CONTEXT_RE.search(context_text):
            return True
    return False


def anchor_span_inside_match(
    raw: str,
    match: re.Match[str],
    *,
    ref_anchor_body_re: re.Pattern[str] = REF_ANCHOR_BODY_RE,
) -> tuple[int, int]:
    anchor = ref_anchor_body_re.search(raw[match.start() : match.end()])
    if anchor is None:
        return match.start(), match.end()
    start = match.start() + anchor.start()
    return start, match.start() + anchor.end()


def looks_like_sample_size_value_ref(
    raw: str,
    match: re.Match[str],
    *,
    ref_anchor_body_re: re.Pattern[str] = REF_ANCHOR_BODY_RE,
) -> bool:
    anchor_start, anchor_end = anchor_span_inside_match(raw, match, ref_anchor_body_re=ref_anchor_body_re)
    left_text = strip_tags(raw[max(0, anchor_start - 240) : anchor_start])
    right_text = strip_tags(raw[anchor_end : anchor_end + 100]).lstrip()
    if re.search(
        r"\bsample\s+size\b[^.;:]{0,160}\b(?:was|were|is|=|:)\s*$",
        left_text,
        re.IGNORECASE,
    ) is None:
        return False
    return (
        not right_text
        or re.match(
            r"^(?:[\.,;:)]|to\b|[-\u2010-\u2014]|\d|participants?\b|patients?\b|subjects?\b|controls?\b)",
            right_text,
            re.IGNORECASE,
        )
        is not None
    )


def looks_like_comma_decimal_stat_ref(raw: str, match: re.Match[str]) -> bool:
    left_text = strip_tags(raw[max(0, match.start() - 240) : match.start()])
    return re.search(
        r"(?:"
        r"\beffect\s+size\b[^.;:]{0,140}\b(?:was|were|is|of|=|:)\s*|"
        r"\ballocation\s+ratio\b[^.;:]{0,180}\b(?:was|were|is|of|=|:|G\*Power)\s*|"
        r"\bG\*Power\s*|"
        r"\bCohen(?:'s)?\s*d\s*=?\s*|"
        r"\blogMAR\s*|"
        r"\b(?:SD|SEM)\s*=?\s*"
        r")$",
        left_text,
        re.IGNORECASE,
    ) is not None


def flattened_sup_match_is_joined_figure_label(match: re.Match[str]) -> bool:
    return re.match(r"\b[A-Za-z]*(?:fig|figure)\.\d{1,3}\b", match.group(0), re.IGNORECASE) is not None


def flattened_sup_match_is_doi_or_url_fragment(text: str, match: re.Match[str]) -> bool:
    window = text[max(0, match.start() - 180) : min(len(text), match.end() + 120)]
    return bool(
        re.search(r"https?://(?:dx\.)?doi\.org/10\.\d{4,9}/", window, re.IGNORECASE)
        or re.search(r"\bdoi\s*:?\s*10\.\d{4,9}/", window, re.IGNORECASE)
    )


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

    ref_id_count = len(REF_ID_RE.findall(polish_html))
    ref_link_count = len(REF_LINK_RE.findall(polish_html))
    if ref_id_count >= 3 and ref_link_count == 0:
        first_body_block = body_blocks[0] if body_blocks else polish_blocks[0] if polish_blocks else None
        return [
            make_defect(
                defect_id="P99",
                cc_class="CC-02/CC-13/CC-14",
                check="Author-year article has bibliography targets but no body reference links",
                severity="error",
                block=first_body_block,
                snippet=first_body_block.text if first_body_block is not None else body_text[:240],
                stage=stage,
                hypothesis="Article-level citation style evidence was author-year, but bibliography link recovery produced no #ref links.",
                proposed_fix_layer="Converted raw citation-profile fallback and author-year bibliography link recovery",
                regression_test="When converted raw HTML has medium author-year evidence, the cached profile keeps author_year so citations link to #ref targets.",
                extra={
                    "ref_id_count": ref_id_count,
                    "ref_link_count": ref_link_count,
                    "html_author_year_count": html_author_year_count,
                    "pdf_author_year_count": pdf_author_year_count,
                    "pdf_citation_dest_links": pdf_citation_dest_links,
                    "pdf_author_year_link_labels": pdf_author_year_link_labels,
                },
            )
        ]

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
