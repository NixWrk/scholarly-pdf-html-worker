"""Citation defect diagnostics for EN polish audits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

from pdf_html_polish.html_stages import POLISH_STAGE_NAME
from pdf_html_polish.quality_loop.audit_blocks import Block, Defect
from pdf_html_polish.quality_loop.audit_citation_style import linked_ref_near_non_citation_context
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect
from pdf_html_polish.quality_loop.audit_p04 import (
    reference_numbers_from_blocks,
    unlinked_citation_candidate_numbers,
    unlinked_sup_numeric_range_matches_footnote_targets,
)
from pdf_html_polish.quality_loop.audit_reference_identity import REFERENCES_HEADING_RE, is_references_block


LATEX_SUP_CITATION_RE = re.compile(r"\\\(\^\{[\d,\s\-\u2013\u2014]+}\\\)")
OCR_CITATION_WORD_RE = re.compile(
    r"\btask\.\s+Sec\.|\bflagship models\s+6,000\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CitationDefectDeps:
    unlinked_citation_range_kind: Callable[[Block], str]
    is_references_block: Callable[[Block, bool], bool] = is_references_block
    linked_ref_near_non_citation_context: Callable[[Block], bool] = linked_ref_near_non_citation_context
    unlinked_citation_candidate_numbers: Callable[[Block], list[int]] = unlinked_citation_candidate_numbers
    reference_numbers_from_blocks: Callable[[list[Block]], set[int]] = reference_numbers_from_blocks
    unlinked_sup_numeric_range_matches_footnote_targets: Callable[
        [Block, set[int]], bool
    ] = unlinked_sup_numeric_range_matches_footnote_targets


def citation_defects(
    polish_blocks: list[Block],
    *,
    deps: CitationDefectDeps,
    reference_blocks: list[Block] | None = None,
    polish_stage: str = POLISH_STAGE_NAME,
    references_heading_re: re.Pattern[str] = REFERENCES_HEADING_RE,
    latex_sup_citation_re: re.Pattern[str] = LATEX_SUP_CITATION_RE,
    ocr_citation_word_re: re.Pattern[str] = OCR_CITATION_WORD_RE,
) -> list[Defect]:
    defects: list[Defect] = []
    references_started = False
    unlinked_range_candidates: dict[str, Block] = {}
    ref_numbers = deps.reference_numbers_from_blocks(reference_blocks or polish_blocks)
    footnote_numbers = {
        int(match.group(1))
        for block in polish_blocks
        for match in (re.match(r"^footnote-(\d+)$", block.id, re.IGNORECASE),)
        if match is not None
    }
    saw_false_positive = False
    saw_ocr_citation = False
    saw_latex_sup = False
    for block in polish_blocks:
        if references_heading_re.match(block.text):
            references_started = True
        if deps.is_references_block(block, references_started):
            continue
        if block.classes & {"z2m-front-matter", "z2m-affiliations", "z2m-footnote"}:
            continue
        if not saw_ocr_citation and ocr_citation_word_re.search(block.text):
            defects.append(
                make_defect(
                    defect_id="P32",
                    cc_class="CC-02/CC-14",
                    check="Likely OCR-corrupted superscript citation remains",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Marker recognized superscript citation numbers as words or ordinary numeric text.",
                    proposed_fix_layer="EN polish citation OCR recovery with reference-count/PDF evidence guards",
                    regression_test="Patterns such as 'task. Sec.' and 'flagship models 6,000' recover to citation links when references 58-60 exist.",
                )
            )
            saw_ocr_citation = True
        range_kind = deps.unlinked_citation_range_kind(block)
        if range_kind and range_kind not in unlinked_range_candidates:
            unlinked_range_candidates[range_kind] = block
        if not saw_latex_sup and latex_sup_citation_re.search(block.raw):
            defects.append(
                make_defect(
                    defect_id="P28",
                    cc_class="CC-02/CC-05",
                    check="Citation-like LaTeX superscript remains in polish",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Citation-like math superscripts were generated after the citation conversion pass or skipped as math.",
                    proposed_fix_layer="EN polish post-math citation recovery",
                    regression_test="Inline math forms like \\(^{71-73}\\) become linked citation superscripts.",
                )
            )
            saw_latex_sup = True
        if not saw_false_positive and deps.linked_ref_near_non_citation_context(block):
            defects.append(
                make_defect(
                    defect_id="P05",
                    cc_class="CC-02/CC-04",
                    check="Reference links appear in likely non-citation numeric context",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Broad numeric linkification may have linked units, labels, or scientific values.",
                    proposed_fix_layer="EN polish citation false-positive guards",
                    regression_test="pH, units, week/month labels, animal labels, and stimulus labels must remain unlinked.",
                )
            )
            saw_false_positive = True
    if "body" in unlinked_range_candidates:
        block = unlinked_range_candidates["body"]
        candidate_numbers = deps.unlinked_citation_candidate_numbers(block)
        missing_targets = [number for number in candidate_numbers if number not in ref_numbers]
        if not ref_numbers:
            defects.append(
                make_defect(
                    defect_id="P04N",
                    cc_class="CC-02/CC-13",
                    check="Citation-like range/list has no bibliography targets to link",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Reference heading/list recognition failed, so citation parser cannot create valid #ref links.",
                    proposed_fix_layer="EN polish bibliography heading and reference-list detection",
                    regression_test="Citation ranges in articles with no recognized ref targets are classified separately from parser misses.",
                    extra={"quality_counted": False, "candidate_numbers": candidate_numbers},
                )
            )
        elif candidate_numbers and missing_targets:
            defects.append(
                make_defect(
                    defect_id="P04R",
                    cc_class="CC-02/CC-13",
                    check="Citation-like range/list refers to missing bibliography targets",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Bibliography normalization skipped or merged some target numbers, so citation parser cannot link safely.",
                    proposed_fix_layer="EN polish bibliography continuation split and reference ID gap repair",
                    regression_test="Ranges such as [6, 7] remain separate from P04 when ref-6/ref-7 are absent.",
                    extra={
                        "quality_counted": False,
                        "candidate_numbers": candidate_numbers,
                        "missing_targets": missing_targets,
                    },
                )
            )
        else:
            defects.append(
                make_defect(
                    defect_id="P04",
                    cc_class="CC-02",
                    check="Unlinked body citation range/list remains in polish",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Citation grammar misses body ranges, en-dash/hyphen spans, or comma-separated lists.",
                    proposed_fix_layer="EN polish citation parser",
                    regression_test="Link [1-4], [8-10], [11, 12], and mixed body citation list/range forms.",
                )
            )
    elif "float" in unlinked_range_candidates:
        block = unlinked_range_candidates["float"]
        candidate_numbers = deps.unlinked_citation_candidate_numbers(block)
        if candidate_numbers and ref_numbers and not any(number in ref_numbers for number in candidate_numbers):
            return defects
        defects.append(
            make_defect(
                defect_id="P04T",
                cc_class="CC-02/CC-06",
                check="Citation-like numeric range/list remains in table or float context",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=polish_stage,
                hypothesis="Table, caption, or float content contains numeric ranges/lists that should be reviewed separately from body citation linking.",
                proposed_fix_layer="EN audit P04 table/float classifier or table-specific citation policy",
                regression_test="Author-affiliation and table numeric ranges must not inflate body P04 counts.",
                extra={"quality_counted": False},
            )
        )
    elif "math" in unlinked_range_candidates:
        block = unlinked_range_candidates["math"]
        candidate_numbers = deps.unlinked_citation_candidate_numbers(block)
        if candidate_numbers and ref_numbers and not any(number in ref_numbers for number in candidate_numbers):
            return defects
        if not deps.unlinked_sup_numeric_range_matches_footnote_targets(block, footnote_numbers):
            defects.append(
                make_defect(
                    defect_id="P04M",
                    cc_class="CC-02/CC-05",
                    check="Citation-like numeric range/list remains in math or measurement context",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Math, statistical, vector, or measurement notation resembles citation ranges and needs separate classification.",
                    proposed_fix_layer="EN audit P04 math/measurement classifier",
                    regression_test="Numeric vectors, parameter intervals, and measurement ranges must not inflate body P04 counts.",
                    extra={"quality_counted": False},
                )
            )
    return defects
