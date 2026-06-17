from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re

from pdf_html_polish.html_stages import POLISH_STAGE_NAME, RAW_STAGE_NAME
from pdf_html_polish.quality_loop.audit_blocks import (
    Block,
    Defect,
    plain_text,
    snippet,
    strip_tags,
    structure_html,
)
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect
from pdf_html_polish.quality_loop.audit_p35 import replacement_char_defects
from pdf_html_polish.quality_loop.audit_reference_identity import is_references_block


@dataclass(frozen=True)
class ManualBlindSpotDeps:
    page_link_re: re.Pattern[str]
    anchor_body_re: re.Pattern[str]
    double_close_anchor_re: re.Pattern[str]
    url_anchor_re: re.Pattern[str]
    malformed_url_anchor_body_re: re.Pattern[str]
    broken_url_text_re: re.Pattern[str]
    references_heading_re: re.Pattern[str]
    ref_anchor_body_re: re.Pattern[str]
    lowercase_ref_glue_re: re.Pattern[str]
    box_unit_re: re.Pattern[str]
    figure_unit_re: re.Pattern[str]
    immediate_external_figure_caption_re: re.Pattern[str]
    table_caption_re: re.Pattern[str]
    table_doi_append_re: re.Pattern[str]
    page_link_semantic_kind: Callable[[str, re.Match[str]], str | None]
    looks_like_figure_caption: Callable[[Block], bool]
    ends_like_sentence_fragment: Callable[[str], bool]
    looks_like_float_or_caption: Callable[[Block], bool]
    looks_like_float_note: Callable[[Block], bool]
    looks_like_equation_continuation: Callable[[Block], bool]
    starts_like_sentence_continuation: Callable[[str], bool]
    source_pdf_text_confirms_float_gap: Callable[[str, str, str], bool]


@dataclass(frozen=True)
class MeineRecentLinkDeps:
    ref_anchor_body_re: re.Pattern[str]
    author_year_text_re: re.Pattern[str]
    page_link_re: re.Pattern[str]
    mixedcase_var_footnote_re: re.Pattern[str]
    table_caption_id_re: re.Pattern[str]
    table_wrapper_id_re: re.Pattern[str]
    table_ref_partial_link_re: re.Pattern[str]
    flattened_sup_citation_re: re.Pattern[str]
    math_or_measurement_range_context_re: re.Pattern[str]
    doi_split_plain_re: re.Pattern[str]
    german_source_hint_re: re.Pattern[str]
    word_footnote_split_re: re.Pattern[str]
    suspicious_footnote_word_merges: set[str]
    figure_unit_re: re.Pattern[str]
    figure_caption_node_re: re.Pattern[str]
    figs_ref_false_ref_re: re.Pattern[str]
    comma_decimal_ref_re: re.Pattern[str]
    single_stat_ref_re: re.Pattern[str]
    references_heading_re: re.Pattern[str]
    reference_target_numbers: Callable[[str], set[int]]
    figure_target_keys: Callable[[str], set[str]]
    non_reference_body_blocks: Callable[[list[Block]], Iterable[Block]]
    ref_anchor_visible_number: Callable[[str], int | None]
    roman_word_split_defects: Callable[..., list[Defect]]
    is_references_block: Callable[[Block, bool], bool]
    looks_like_affiliation_label_roman_boundary: Callable[[str], bool]
    block_is_float_or_table_context: Callable[[Block], bool]
    flattened_sup_match_is_joined_figure_label: Callable[[re.Match[str]], bool]
    flattened_sup_match_is_doi_or_url_fragment: Callable[[str, re.Match[str]], bool]
    block_looks_like_math_or_measurement_range_context: Callable[[Block], bool]
    looks_like_table_flattened_citation_context: Callable[[str], bool]
    page_link_semantic_kind: Callable[[str, re.Match[str]], str | None]
    figure_caption_number_from_caption_node: Callable[[str], int | None]
    figure_unit_allows_shared_image_alias: Callable[[str, int, list[int]], bool]
    ref_match_inside_bracketed_numeric_citation: Callable[[str, int, int], bool]
    looks_like_comma_decimal_stat_ref: Callable[[str, re.Match[str]], bool]
    looks_like_sample_size_value_ref: Callable[[str, re.Match[str]], bool]
    visible_figure_target_defects: Callable[..., list[Defect]]
    looks_like_float_or_caption: Callable[[Block], bool]
    parse_overlapping_blocks: Callable[[str], list[Block]]
    missing_figure_warning_blocks: Callable[[str], list[Block]]
    classify_missing_figure_warning: Callable[[Block, list[Block]], dict[str, object]]


@dataclass(frozen=True)
class MeineRecentTextDeps:
    split_email_text_re: re.Pattern[str]
    runaway_repeated_text_re: re.Pattern[str]
    lost_ff_word_re: re.Pattern[str]
    known_joined_word_re: re.Pattern[str]
    float_sentence_interrupt_re: re.Pattern[str]
    corrupt_email_label_re: re.Pattern[str]
    reference_roman_split_re: re.Pattern[str]
    table_note_body_merge_re: re.Pattern[str]
    author_marker_glue_re: re.Pattern[str]
    latex_macro_runaway_re: re.Pattern[str]
    doi_body_prose_merge_re: re.Pattern[str]
    detached_accent_re: re.Pattern[str]
    table_section_absorb_re: re.Pattern[str]
    inline_intra_word_space_html_re: re.Pattern[str]
    intra_word_space_re: re.Pattern[str]
    table_footnote_word_letter_html_re: re.Pattern[str]
    affiliation_department_glue_re: re.Pattern[str]
    suspicious_email_domain_re: re.Pattern[str]
    body_page_header_re: re.Pattern[str]
    table_gibberish_flow_re: re.Pattern[str]
    float_or_metadata_interruption_re: re.Pattern[str]
    float_or_metadata_intrusion_marker_re: re.Pattern[str]
    escaped_sup_footnote_re: re.Pattern[str]
    references_backmatter_interleave_re: re.Pattern[str]
    old_scan_ocr_gibberish_re: re.Pattern[str]
    split_url_domain_re: re.Pattern[str]
    split_at_email_re: re.Pattern[str]
    bibliography_numbering_residue_re: re.Pattern[str]
    publisher_recommendation_block_re: re.Pattern[str]
    affiliation_marker_residue_re: re.Pattern[str]
    pdf_line_number_residue_re: re.Pattern[str]
    non_reference_body_blocks: Callable[[list[Block]], Iterable[Block]]
    joined_word_match_is_url_slug: Callable[[str, re.Match[str]], bool]
    known_ocr_token_defects: Callable[[str, str, str], list[Defect]]
    find_split_dot_email_match: Callable[[str], re.Match[str] | None]
    bibliography_numbering_residue_is_clean_reference_boundary: Callable[[str, str], bool]


def manual_blind_spot_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    deps: ManualBlindSpotDeps,
    pdf_text: str = "",
    polish_stage: str = POLISH_STAGE_NAME,
) -> list[Defect]:
    defects: list[Defect] = []
    slim_html = structure_html(polish_html)

    for match in deps.page_link_re.finditer(slim_html):
        kind = deps.page_link_semantic_kind(slim_html, match)
        if kind is None:
            continue
        defects.append(
            make_defect(
                defect_id="P33",
                cc_class="CC-02/CC-03/CC-10",
                check="Semantic reference still points to PDF page anchor",
                severity="warning" if kind.startswith("semantic") else "error",
                block=None,
                snippet=snippet(slim_html, match.start(), match.end()),
                stage=polish_stage,
                hypothesis="A citation, table/figure/box/section reference, or OCR-glued citation was left as a #page-* link.",
                proposed_fix_layer="EN polish semantic cross-reference retargeting",
                regression_test="Box/Table/Section/Appendix and bibliography refs must target #box/#table/#section/#ref rather than #page.",
                extra={"page_target": match.group("target"), "label": strip_tags(match.group("body")), "kind": kind},
            )
        )
        break

    nested_anchor_match = next(
        (match for match in deps.anchor_body_re.finditer(slim_html) if "<a" in match.group("body").lower()),
        None,
    )
    double_close_match = deps.double_close_anchor_re.search(slim_html)
    malformed_anchor_match = nested_anchor_match or double_close_match
    if malformed_anchor_match is not None:
        defects.append(
            make_defect(
                defect_id="P34",
                cc_class="CC-02/CC-03",
                check="Malformed nested or double-closed anchor",
                severity="error",
                block=None,
                snippet=snippet(slim_html, malformed_anchor_match.start(), malformed_anchor_match.end()),
                stage=polish_stage,
                hypothesis="Citation/link reconstruction wrapped an already-linked fragment or left an extra closing anchor.",
                proposed_fix_layer="EN polish anchor normalization after citation retargeting",
                regression_test="Citation lists such as [24, 25] and [30] never contain nested <a> tags or stray </a>.",
            )
        )

    defects.extend(replacement_char_defects(polish_html, pdf_text, stage=polish_stage))

    url_check_plain = plain_text(deps.url_anchor_re.sub(" URL ", slim_html))
    broken_url_match = deps.broken_url_text_re.search(url_check_plain)
    malformed_url_anchor_match = deps.malformed_url_anchor_body_re.search(slim_html)
    if broken_url_match is not None or malformed_url_anchor_match is not None:
        if broken_url_match is not None:
            defect_snippet = snippet(url_check_plain, broken_url_match.start(), broken_url_match.end())
        else:
            assert malformed_url_anchor_match is not None
            defect_snippet = strip_tags(
                snippet(slim_html, malformed_url_anchor_match.start(), malformed_url_anchor_match.end())
            )
        defects.append(
            make_defect(
                defect_id="P36",
                cc_class="CC-03/CC-13",
                check="Visible URL or DOI is split or malformed",
                severity="warning",
                block=None,
                snippet=defect_snippet,
                stage=polish_stage,
                hypothesis="Line/page splitting, OCR, or autolinking left a visibly broken URL/DOI label.",
                proposed_fix_layer="EN polish URL/DOI label normalization",
                regression_test="URLs like 'https:// creativecommons.org', 'hps://dl.acm.org', and 'doi.org/ 10...' are joined or reported.",
            )
        )

    references_started = False
    for block in polish_blocks:
        if deps.references_heading_re.match(block.text):
            references_started = True
        if is_references_block(block, references_started) or block.classes & {
            "z2m-front-matter",
            "z2m-affiliations",
            "z2m-footnote",
        }:
            continue
        for match in deps.ref_anchor_body_re.finditer(block.raw):
            label = strip_tags(match.group("body"))
            if not deps.lowercase_ref_glue_re.fullmatch(label):
                continue
            defects.append(
                make_defect(
                    defect_id="P37",
                    cc_class="CC-02/CC-13",
                    check="Citation link absorbed the final letter of a word",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Superscript OCR split the last letter from the preceding word and citation linking preserved that split.",
                    proposed_fix_layer="EN polish citation OCR glue repair",
                    regression_test="Patterns like 'functio n13,14' and 'consideration s20,23' rejoin the letter to the word.",
                    extra={"label": label, "ref_target": match.group("num")},
                )
            )
            break
        if defects and defects[-1].id == "P37":
            break

    for match in deps.box_unit_re.finditer(slim_html):
        box_text = strip_tags(match.group("body"))
        tail = slim_html[match.end() : match.end() + 600]
        if len(box_text) <= 40 and re.fullmatch(r"(?:BOX|Box)\s+\d+[A-Za-z]?", box_text) and re.match(
            r"\s*<h[1-6]\b", tail, re.IGNORECASE
        ):
            defects.append(
                make_defect(
                    defect_id="P38",
                    cc_class="CC-09/CC-12",
                    check="Box wrapper contains only the box label",
                    severity="warning",
                    block=None,
                    snippet=snippet(slim_html, match.start(), min(len(slim_html), match.end() + 220)),
                    stage=polish_stage,
                    hypothesis="Box framing stopped at the label and left the box title/content outside the wrapper.",
                    proposed_fix_layer="EN polish box-unit assembly",
                    regression_test="Box 1 label, title, and body paragraphs are wrapped as one z2m-box-unit with top/bottom rules.",
                )
            )
            break

    for match in deps.figure_unit_re.finditer(slim_html):
        figure_id = match.group("id")
        tail = slim_html[match.end() : match.end() + 5000]
        caption_match = deps.immediate_external_figure_caption_re.search(tail)
        if caption_match is None:
            continue
        caption_raw = caption_match.group(0)
        caption_text = strip_tags(caption_raw)
        figure_num_match = re.search(r"\d+", figure_id)
        figure_num = figure_num_match.group(0) if figure_num_match else ""
        points_to_same_figure = (
            re.search(rf"href\s*=\s*['\"]#{re.escape(figure_id)}['\"]", caption_raw, re.IGNORECASE) is not None
            or bool(figure_num and re.match(rf"\s*(?:Fig\.?|Figure)\s*{re.escape(figure_num)}\b", caption_text, re.IGNORECASE))
        )
        if not points_to_same_figure:
            continue
        defects.append(
            make_defect(
                defect_id="P39",
                cc_class="CC-08/CC-12",
                check="Figure wrapper closes before its remaining image or caption",
                severity="warning",
                block=None,
                snippet=snippet(slim_html, match.start(), min(len(slim_html), match.end() + caption_match.end())),
                stage=polish_stage,
                hypothesis="Multi-image or caption assembly left part of the same figure outside the z2m-figure-unit.",
                proposed_fix_layer="EN polish figure-unit expansion after target assignment",
                regression_test="Multi-panel figures keep all adjacent images and the matching caption inside the same figure wrapper.",
                extra={"figure_id": figure_id},
            )
        )
        break

    saw_float_split = False
    for index, block in enumerate(polish_blocks[:-2]):
        if block.tag != "p" or block.classes & {"z2m-front-matter", "z2m-affiliations"}:
            continue
        if deps.looks_like_figure_caption(block) or deps.table_caption_re.match(block.text):
            continue
        if not deps.ends_like_sentence_fragment(block.text):
            continue
        saw_float = False
        for candidate in polish_blocks[index + 1 : min(len(polish_blocks), index + 14)]:
            if deps.looks_like_float_or_caption(candidate):
                saw_float = True
                continue
            if not saw_float:
                break
            if deps.looks_like_float_note(candidate):
                continue
            if deps.looks_like_equation_continuation(candidate):
                break
            if candidate.tag == "p" and deps.starts_like_sentence_continuation(candidate.text):
                if deps.source_pdf_text_confirms_float_gap(block.text, candidate.text, pdf_text):
                    break
                defects.append(
                    make_defect(
                        defect_id="P40",
                        cc_class="CC-07/CC-13",
                        check="Float likely interrupts a sentence continuation",
                        severity="warning",
                        block=block,
                        snippet=f"{block.text[-140:]} ... {candidate.text[:140]}",
                        stage=polish_stage,
                        hypothesis="A figure/table was left between two fragments of the same sentence.",
                        proposed_fix_layer="EN polish float-aware reading-order repair",
                        regression_test="Paragraph fragments around a float rejoin when the before-text has no sentence terminator and after-text starts as a continuation.",
                    )
                )
                saw_float_split = True
                break
            break
        if saw_float_split:
            break

    for block in polish_blocks:
        if deps.table_doi_append_re.search(block.text):
            defects.append(
                make_defect(
                    defect_id="P41",
                    cc_class="CC-07/CC-13",
                    check="Body prose is appended to a table DOI/note paragraph",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="A table note/DOI block swallowed the continuation of body prose after a misplaced table.",
                    proposed_fix_layer="EN polish table-note boundary and reading-order repair",
                    regression_test="Text following a table DOI, such as 'three parameters). These tendencies...', is restored to the surrounding body paragraph.",
                )
            )
            break

    return defects


def meine_recent_link_structure_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    deps: MeineRecentLinkDeps,
    pdf_text: str = "",
    polish_stage: str = POLISH_STAGE_NAME,
    raw_stage: str = RAW_STAGE_NAME,
) -> list[Defect]:
    del pdf_text
    defects: list[Defect] = []
    slim_html = structure_html(polish_html)
    plain = plain_text(slim_html)
    ref_targets = deps.reference_target_numbers(slim_html)
    fig_targets = deps.figure_target_keys(slim_html)
    body_blocks = list(deps.non_reference_body_blocks(polish_blocks))

    for block in body_blocks:
        for match in deps.ref_anchor_body_re.finditer(block.raw):
            label = strip_tags(match.group("body"))
            if deps.author_year_text_re.search(label) is not None:
                continue
            visible_number = deps.ref_anchor_visible_number(label)
            target_number = int(match.group("num"))
            if visible_number is None or visible_number == target_number:
                continue
            if 1800 <= visible_number <= 2099:
                continue
            defects.append(
                make_defect(
                    defect_id="P42",
                    cc_class="CC-02/CC-13",
                    check="Visible citation label points to a different bibliography target",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Bibliography continuation drift or ordinal reassignment changed #ref targets without preserving visible citation identity.",
                    proposed_fix_layer="EN polish bibliography identity audit before citation linkification",
                    regression_test="Visible citation labels such as ',9' must link to #ref-9, not shifted continuation targets.",
                    extra={"visible_number": visible_number, "ref_target": target_number, "label": label},
                )
            )
            break
        if defects and defects[-1].id == "P42":
            break

    for match in deps.page_link_re.finditer(slim_html):
        label = strip_tags(match.group("body"))
        left = strip_tags(slim_html[max(0, match.start() - 100) : match.start()])
        if not (
            re.fullmatch(r"\d+\.\d+\)?\.?", label)
            and re.search(r"\b(?:Eqn?\.?|Equation)\s*$", left, re.IGNORECASE)
        ):
            continue
        defects.append(
            make_defect(
                defect_id="P43",
                cc_class="CC-03/CC-06/CC-10",
                check="Decimal equation reference remains a PDF page link",
                severity="warning",
                block=None,
                snippet=snippet(slim_html, match.start(), match.end()),
                stage=polish_stage,
                hypothesis="Equation-reference retargeting handles simple integers but misses decimal equation labels such as Eqn. 2.1.",
                proposed_fix_layer="EN polish equation-reference parser",
                regression_test="Eqn. 2.1 and Eqn. 2.4 page anchors retarget to equation IDs or unwrap if no reliable target exists.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    for block in polish_blocks[:25]:
        for match in deps.page_link_re.finditer(block.raw):
            label = strip_tags(match.group("body"))
            if re.fullmatch(r"i\s*\d+\s*,?", label, re.IGNORECASE) is None:
                continue
            defects.append(
                make_defect(
                    defect_id="P44",
                    cc_class="CC-01/CC-03",
                    check="Front-matter affiliation marker remains as page-anchor glue",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Superscript affiliation labels in the front matter were OCR-glued into page-anchor links.",
                    proposed_fix_layer="EN polish front-matter marker repair before page-link preservation",
                    regression_test="Author/affiliation fragments like 'i1,' and 'i3,' do not remain linked to #page anchors.",
                    extra={"page_target": match.group("target"), "label": label},
                )
            )
            break
        if defects and defects[-1].id == "P44":
            break

    defects.extend(
        deps.roman_word_split_defects(
            polish_blocks,
            references_heading_re=deps.references_heading_re,
            is_references_block=deps.is_references_block,
            looks_like_affiliation_label_roman_boundary=deps.looks_like_affiliation_label_roman_boundary,
            stage=polish_stage,
        )
    )

    mixed_var_match = deps.mixedcase_var_footnote_re.search(slim_html)
    if mixed_var_match is not None:
        defects.append(
            make_defect(
                defect_id="P46",
                cc_class="CC-04/CC-11",
                check="Mixed-case scientific variable was split as a table footnote",
                severity="error",
                block=None,
                snippet=snippet(slim_html, mixed_var_match.start(), mixed_var_match.end()),
                stage=polish_stage,
                hypothesis="Table footnote detection treats terminal x/i/v as a footnote marker even when it is part of a variable such as Qmax.",
                proposed_fix_layer="EN polish table-footnote parser with variable/name guards",
                regression_test="Qmax/Qave/Qmn-style variables stay plain text in table cells and captions.",
            )
        )

    for caption_match in deps.table_caption_id_re.finditer(slim_html):
        tail = slim_html[caption_match.end() : caption_match.end() + 4000]
        wrapper_match = deps.table_wrapper_id_re.search(tail)
        if wrapper_match is None:
            continue
        caption_num = caption_match.group("num")
        wrapper_num = wrapper_match.group("num")
        if caption_num == wrapper_num:
            continue
        defects.append(
            make_defect(
                defect_id="P47",
                cc_class="CC-07/CC-11/CC-13",
                check="Table caption target drifts to a different table wrapper",
                severity="error",
                block=None,
                snippet=snippet(slim_html, caption_match.start(), caption_match.end() + wrapper_match.end()),
                stage=polish_stage,
                hypothesis="Caption/table assembly assigned a caption ID by visible label but wrapped the following table under a different ordinal.",
                proposed_fix_layer="EN polish table-unit assembly and caption-table adjacency validation",
                regression_test="A caption with id=table-4 is followed by or wrapped with table-4, never table-5.",
                extra={"caption_table": caption_num, "wrapper_table": wrapper_num},
            )
        )
        break

    for caption_match in deps.table_caption_id_re.finditer(slim_html):
        tail = slim_html[caption_match.end() : caption_match.end() + 1600]
        first_table = re.search(r"<table\b", tail, re.IGNORECASE)
        first_wrapper = deps.table_wrapper_id_re.search(tail)
        if first_table is None or (first_wrapper is not None and first_wrapper.start() < first_table.start()):
            continue
        defects.append(
            make_defect(
                defect_id="P48",
                cc_class="CC-07/CC-11",
                check="Table caption is followed by an unwrapped table",
                severity="warning",
                block=None,
                snippet=snippet(slim_html, caption_match.start(), caption_match.end() + first_table.end()),
                stage=polish_stage,
                hypothesis="A visible table caption was given a target ID, but the adjacent table body was not included in the semantic wrapper.",
                proposed_fix_layer="EN polish table-unit wrapping",
                regression_test="Captions above tables wrap the following table body into the same z2m-table-unit.",
                extra={"caption_table": caption_match.group("num")},
            )
        )
        break

    for block in body_blocks:
        partial_table_match = deps.table_ref_partial_link_re.search(block.raw)
        if partial_table_match is None:
            continue
        defects.append(
            make_defect(
                defect_id="P49",
                cc_class="CC-03/CC-10",
                check="Only the digit of a table reference is linked",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=polish_stage,
                hypothesis="Cross-reference linkification wrapped only the number and left the semantic label outside the anchor.",
                proposed_fix_layer="EN polish table-reference parser",
                regression_test="'Table 4', 'Tables 4 and 5', and similar labels are linked as whole semantic references.",
                extra=partial_table_match.groupdict(),
            )
        )
        break

    for block in body_blocks:
        if deps.block_is_float_or_table_context(block):
            continue
        linkless_raw = re.sub(r"<a\b[^>]*>.*?</a>", " ", block.raw, flags=re.IGNORECASE | re.DOTALL)
        linkless_text = strip_tags(linkless_raw)
        flattened_match = deps.flattened_sup_citation_re.search(linkless_text)
        if flattened_match is None:
            continue
        if deps.flattened_sup_match_is_joined_figure_label(flattened_match):
            continue
        if deps.flattened_sup_match_is_doi_or_url_fragment(linkless_text, flattened_match):
            continue
        if (
            re.search(r"https?://(?:dx\.)?doi\.org/10\.\d{4,9}/", block.raw, re.IGNORECASE)
            and re.search(r"[A-Za-z]{3,}\.\d", flattened_match.group(0))
        ):
            continue
        number = int(flattened_match.group("num"))
        if number not in ref_targets:
            continue
        window = linkless_text[max(0, flattened_match.start() - 120) : flattened_match.end() + 160]
        if not re.search(r"\bet\s+al\.?\s*\d", flattened_match.group(0), re.IGNORECASE):
            if (
                deps.math_or_measurement_range_context_re.search(window)
                or deps.block_looks_like_math_or_measurement_range_context(block)
            ):
                continue
        if deps.looks_like_table_flattened_citation_context(linkless_text):
            continue
        defects.append(
            make_defect(
                defect_id="P50",
                cc_class="CC-02/CC-13",
                check="Flattened superscript citation remains unlinked",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=polish_stage,
                hypothesis="Superscript citation OCR was flattened into prose, so the citation parser did not see a bracket/sup marker.",
                proposed_fix_layer="EN polish citation OCR recovery",
                regression_test="Patterns like 'Agarwal et al3' and 'voiders.3' recover to reference links when ref-3 exists.",
                extra={"visible_number": number, "match": flattened_match.group(0)},
            )
        )
        break

    for match in deps.page_link_re.finditer(slim_html):
        if deps.page_link_semantic_kind(slim_html, match) is not None:
            continue
        label = strip_tags(match.group("body"))
        if len(re.findall(r"[A-Za-z]{2,}", label)) < 3:
            continue
        if deps.author_year_text_re.search(label) is not None:
            continue
        if re.search(r"\b(?:copyright|creative commons|doi|https?)\b", label, re.IGNORECASE):
            continue
        defects.append(
            make_defect(
                defect_id="P51",
                cc_class="CC-03/CC-07/CC-13",
                check="Prose fragment remains wrapped as a PDF page link",
                severity="warning",
                block=None,
                snippet=snippet(slim_html, match.start(), match.end()),
                stage=polish_stage,
                hypothesis="Page-anchor preservation kept an OCR/page-break prose fragment linked instead of unwrapping it into body text.",
                proposed_fix_layer="EN polish page-link cleanup",
                regression_test="Plain prose fragments such as 'that formulas that use the total' are unwrapped from #page anchors.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    doi_split_match = deps.doi_split_plain_re.search(plain)
    if doi_split_match is not None:
        defects.append(
            make_defect(
                defect_id="P52",
                cc_class="CC-03/CC-13",
                check="Plain DOI label is split after slash",
                severity="warning",
                block=None,
                snippet=snippet(plain, doi_split_match.start(), doi_split_match.end()),
                stage=polish_stage,
                hypothesis="Line wrapping split a DOI suffix and the URL/DOI repair pass did not join the visible label.",
                proposed_fix_layer="EN polish DOI normalization",
                regression_test="Labels like 'doi: 10.1002/ nau.22813' become one clickable DOI without changing the DOI text.",
            )
        )

    german_probe = plain[:20000]
    german_hits = deps.german_source_hint_re.findall(german_probe)
    german_keys = {hit.upper() for hit in german_hits}
    german_anchor_hints = {
        "DEUTSCHE",
        "DRESDEN",
        "KLINIK",
        "KOLLODIUM",
        "KOLLODIUMVERFAHREN",
        "LEITTHEMA",
        "LEITLINIEN",
        "PHOTOGRAPHIE",
        "PROSTATASYNDROMS",
        "UROLOGE",
        "ZUSAMMENFASSUNG",
    }
    if len(german_hits) >= 8 and german_keys & german_anchor_hints:
        defects.append(
            make_defect(
                defect_id="P53",
                cc_class="CC-00/CC-14",
                check="Likely non-English source reached the English polish audit",
                severity="error",
                block=None,
                snippet=snippet(plain, 0, min(len(plain), 600)),
                stage=raw_stage,
                hypothesis="Source-language gating did not exclude a German document before the English marker/polish profile.",
                proposed_fix_layer="Pre-marker source-language detection and run routing",
                regression_test="German sources are tagged as source_language=de before marker and are not sent through the EN polish profile.",
                extra={"german_hint_count": len(german_hits), "german_hints": sorted(german_keys)[:12]},
            )
        )

    for word_match in deps.word_footnote_split_re.finditer(slim_html):
        prefix = word_match.group("prefix")
        combined = f"{prefix}{word_match.group('suffix')}".lower()
        if combined not in deps.suspicious_footnote_word_merges:
            continue
        if prefix.lower() in {"qma", "qa", "qav", "qmn"}:
            continue
        if prefix.isupper() and len(prefix) >= 2:
            continue
        if prefix.lower() in {"pdms", "polyimide", "parylene"}:
            continue
        defects.append(
            make_defect(
                defect_id="P54",
                cc_class="CC-04/CC-11/CC-13",
                check="Ordinary word was split as a table footnote",
                severity="warning",
                block=None,
                snippet=snippet(slim_html, word_match.start(), word_match.end()),
                stage=polish_stage,
                hypothesis="Table-footnote roman suffix repair is too broad and can split ordinary words, especially in non-English sources.",
                proposed_fix_layer="EN polish table-footnote parser with lexical and language-aware guards",
                regression_test="Words such as Mastix/Borax/Kupfervitriol and author surnames are not split into z2m-table-fn spans.",
                extra={"prefix": prefix, "suffix": word_match.group("suffix")},
            )
        )
        break

    for block in body_blocks:
        for match in deps.ref_anchor_body_re.finditer(block.raw):
            label = strip_tags(match.group("body"))
            right_text = strip_tags(block.raw[match.end() : match.end() + 100])
            surname_author_year_fragment = (
                re.fullmatch(r"[A-Z][A-Za-z'’.-]{3,}", label) is not None
                and re.match(r"^\s*et\s+al\.?\s*\(?\d{4}[a-z]?\)?", right_text, re.IGNORECASE) is not None
            )
            if deps.author_year_text_re.search(label) is None and not surname_author_year_fragment:
                continue
            defects.append(
                make_defect(
                    defect_id="P55",
                    cc_class="CC-02/CC-13",
                    check="Author-year citation is linked to a numeric bibliography target",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Article-level citation strategy confused author-year citations with numeric reference targets.",
                    proposed_fix_layer="EN polish article-level citation-style detection",
                    regression_test="Author-year citations match bibliography by surname/year or remain plain when confidence is low; they never map to arbitrary #ref-N.",
                    extra={"ref_target": match.group("num"), "label": label},
                )
            )
            break
        if defects and defects[-1].id == "P55":
            break

    for match in deps.page_link_re.finditer(slim_html):
        label = strip_tags(match.group("body"))
        if deps.author_year_text_re.search(label) is None:
            continue
        defects.append(
            make_defect(
                defect_id="P56",
                cc_class="CC-02/CC-03/CC-13",
                check="Author-year citation remains a PDF page link",
                severity="warning",
                block=None,
                snippet=snippet(slim_html, match.start(), match.end()),
                stage=polish_stage,
                hypothesis="Author-year citation retargeting is missing or low-confidence, leaving stale #page anchors in body prose.",
                proposed_fix_layer="EN polish author-year citation parser",
                regression_test="Author-year page anchors either link by surname/year or unwrap to plain text without #page targets.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    for match in deps.figure_unit_re.finditer(slim_html):
        wrapper_num_match = re.search(r"\d+", match.group("id"))
        if wrapper_num_match is None:
            continue
        wrapper_num = int(wrapper_num_match.group(0))
        body = match.group("body")
        alias_nums = {
            int(number)
            for number in re.findall(r"\bid\s*=\s*['\"]fig-(\d+)['\"]", body, re.IGNORECASE)
        }
        caption_nums = {
            number
            for caption_match in deps.figure_caption_node_re.finditer(body)
            for number in [deps.figure_caption_number_from_caption_node(caption_match.group("body"))]
            if number is not None
        }
        unrelated = sorted((alias_nums | caption_nums) - {wrapper_num})
        if not unrelated:
            continue
        if deps.figure_unit_allows_shared_image_alias(body, wrapper_num, unrelated):
            continue
        defects.append(
            make_defect(
                defect_id="P57",
                cc_class="CC-08/CC-10/CC-13",
                check="Figure wrapper contains an unrelated figure alias or caption number",
                severity="error",
                block=None,
                snippet=snippet(slim_html, match.start(), match.end()),
                stage=polish_stage,
                hypothesis="Figure assembly merged captions/aliases for distinct figures into one wrapper.",
                proposed_fix_layer="EN polish figure-unit assembly and alias validation",
                regression_test="fig-1 wrappers do not contain fig-4 aliases or visible Fig. 4 captions unless the PDF proves a shared compound figure.",
                extra={"wrapper_figure": wrapper_num, "unrelated_figures": unrelated[:10]},
            )
        )
        break

    for block in body_blocks:
        for match in deps.ref_anchor_body_re.finditer(block.raw):
            label_number = deps.ref_anchor_visible_number(strip_tags(match.group("body")))
            if label_number is None:
                continue
            left_tail = strip_tags(block.raw[max(0, match.start() - 100) : match.start()])
            if deps.figs_ref_false_ref_re.search(left_tail) is None:
                continue
            defects.append(
                make_defect(
                    defect_id="P58",
                    cc_class="CC-02/CC-03/CC-10",
                    check="Figure list/range number links to bibliography reference",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Figure-reference grammar failed, and the remaining number was picked up by bibliography citation linkification.",
                    proposed_fix_layer="EN polish figure-reference parser before citation linkification",
                    regression_test="Patterns like '(Figs. 3 and 5)' link to figure targets, not #ref-5.",
                    extra={"visible_number": label_number, "ref_target": match.group("num")},
                )
            )
            break
        if defects and defects[-1].id == "P58":
            break

    body_text = " ".join(block.text for block in body_blocks)
    bracket_citation_count = len(re.findall(r"\[\s*\d", body_text))
    author_year_count = len(deps.author_year_text_re.findall(body_text))
    numeric_ref_link_count = sum(
        1
        for block in body_blocks
        for match in deps.ref_anchor_body_re.finditer(block.raw)
        if deps.ref_anchor_visible_number(strip_tags(match.group("body"))) is not None
    )
    numeric_sup_ref_link_count = sum(
        1
        for block in body_blocks
        for match in deps.ref_anchor_body_re.finditer(block.raw)
        if deps.ref_anchor_visible_number(strip_tags(match.group("body"))) is not None
        and "<sup" in block.raw[max(0, match.start() - 40) : match.start()].lower()
    )
    numeric_citation_dominant = (
        numeric_ref_link_count >= 5
        and numeric_sup_ref_link_count >= 5
    ) or (
        numeric_ref_link_count >= 10
        and numeric_sup_ref_link_count >= 3
    )
    if author_year_count >= 4 and bracket_citation_count < 4 and not numeric_citation_dominant:
        for block in body_blocks:
            for match in deps.ref_anchor_body_re.finditer(block.raw):
                label = strip_tags(match.group("body"))
                if re.fullmatch(r"\d{1,3}", label) is None or int(label) > 3:
                    continue
                raw_window = block.raw[max(0, match.start() - 80) : match.end() + 80].lower()
                text_window = strip_tags(block.raw[max(0, match.start() - 160) : match.end() + 160])
                if re.search(r"\b(?:Fig\.?|Figs\.?|Figure|Table|Eqn?\.?|Equation)\b", text_window, re.IGNORECASE):
                    continue
                if "<sup" not in raw_window and re.search(r"\b(?:source|web|github|facebook|living|data)\b", text_window, re.IGNORECASE) is None:
                    continue
                defects.append(
                    make_defect(
                        defect_id="P59",
                        cc_class="CC-02/CC-13",
                        check="Numeric footnote marker links to bibliography in author-year article",
                        severity="error",
                        block=block,
                        snippet=block.text,
                        stage=polish_stage,
                        hypothesis="Mixed footnote/bibliography strategy treated source/web footnotes as numbered bibliography citations.",
                        proposed_fix_layer="EN polish citation-style and footnote-style separation",
                        regression_test="Frontiers-style source footnotes 1/2/3 link to footnotes or remain footnotes, not #ref-1/#ref-2/#ref-3.",
                        extra={"ref_target": match.group("num"), "label": label},
                    )
                )
                break
            if defects and defects[-1].id == "P59":
                break

    for block in body_blocks:
        comma_match = deps.comma_decimal_ref_re.search(block.raw)
        single_stat_match = deps.single_stat_ref_re.search(block.raw)
        if comma_match is not None and deps.ref_match_inside_bracketed_numeric_citation(
            block.raw,
            comma_match.start(),
            comma_match.end(),
        ):
            comma_match = None
        if single_stat_match is not None and deps.ref_match_inside_bracketed_numeric_citation(
            block.raw,
            single_stat_match.start(),
            single_stat_match.end(),
        ):
            single_stat_match = None
        if comma_match is not None:
            if not deps.looks_like_comma_decimal_stat_ref(block.raw, comma_match):
                comma_match = None
        if single_stat_match is not None and not deps.looks_like_sample_size_value_ref(block.raw, single_stat_match):
            single_stat_match = None
        if comma_match is None and single_stat_match is None:
            continue
        defects.append(
            make_defect(
                defect_id="P60",
                cc_class="CC-02/CC-04/CC-13",
                check="Statistical or comma-decimal value was linked as bibliography references",
                severity="error",
                block=block,
                snippet=block.text,
                stage=polish_stage,
                hypothesis="Comma-decimal/statistical notation was mistaken for a reference list.",
                proposed_fix_layer="EN polish citation false-positive guards for statistical contexts",
                regression_test="Values like effect size 1,5, allocation ratio 3,1, and sample-size values remain numeric text.",
                extra=(comma_match or single_stat_match).groupdict(),
            )
        )
        break

    defects.extend(
        deps.visible_figure_target_defects(
            body_blocks,
            fig_targets,
            looks_like_float_or_caption=deps.looks_like_float_or_caption,
            stage=polish_stage,
        )
    )

    warning_context_blocks = deps.parse_overlapping_blocks(polish_html)
    for warning_index, block in enumerate(deps.missing_figure_warning_blocks(polish_html)):
        classification = deps.classify_missing_figure_warning(block, warning_context_blocks)
        extra = {"warning_index": warning_index + 1, **classification["extra"]}
        defects.append(
            make_defect(
                defect_id=str(classification["defect_id"]),
                cc_class="CC-08/CC-13",
                check=str(classification["check"]),
                severity="warning",
                block=block,
                snippet=block.text,
                stage=raw_stage,
                hypothesis=str(classification["hypothesis"]),
                proposed_fix_layer=str(classification["proposed_fix_layer"]),
                regression_test=(
                    "Visible z2m-missing-figure-warning blocks are counted and split into "
                    "same-label, ambiguous-nearby-image, and no-nearby-image subtypes."
                ),
                extra=extra,
            )
        )

    for match in deps.page_link_re.finditer(slim_html):
        label = strip_tags(match.group("body"))
        if re.match(r"^\[\s*\d", label) is None:
            continue
        defects.append(
            make_defect(
                defect_id="P63",
                cc_class="CC-02/CC-03/CC-10",
                check="Bracket citation remains a PDF page link",
                severity="error",
                block=None,
                snippet=snippet(slim_html, match.start(), match.end()),
                stage=polish_stage,
                hypothesis="Bracket citation grammar missed page-anchor citation forms, including no-space lists and ranges.",
                proposed_fix_layer="EN polish bracket citation retargeting",
                regression_test="Citations like [1], [17,18], [20-23], [30], and [33] link to #ref targets instead of #page anchors.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    return defects

def meine_recent_text_ocr_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    deps: MeineRecentTextDeps,
    pdf_text: str = "",
    polish_stage: str = POLISH_STAGE_NAME,
) -> list[Defect]:
    defects: list[Defect] = []
    slim_html = structure_html(polish_html)
    plain = plain_text(slim_html)
    body_blocks = list(deps.non_reference_body_blocks(polish_blocks))

    _defect = make_defect
    _snippet = snippet
    _strip_tags = strip_tags
    _joined_word_match_is_url_slug = deps.joined_word_match_is_url_slug
    _known_ocr_token_defects = deps.known_ocr_token_defects
    _find_split_dot_email_match = deps.find_split_dot_email_match
    _bibliography_numbering_residue_is_clean_reference_boundary = deps.bibliography_numbering_residue_is_clean_reference_boundary
    POLISH_STAGE = polish_stage

    SPLIT_EMAIL_TEXT_RE = deps.split_email_text_re
    RUNAWAY_REPEATED_TEXT_RE = deps.runaway_repeated_text_re
    LOST_FF_WORD_RE = deps.lost_ff_word_re
    KNOWN_JOINED_WORD_RE = deps.known_joined_word_re
    FLOAT_SENTENCE_INTERRUPT_RE = deps.float_sentence_interrupt_re
    CORRUPT_EMAIL_LABEL_RE = deps.corrupt_email_label_re
    REFERENCE_ROMAN_SPLIT_RE = deps.reference_roman_split_re
    TABLE_NOTE_BODY_MERGE_RE = deps.table_note_body_merge_re
    AUTHOR_MARKER_GLUE_RE = deps.author_marker_glue_re
    LATEX_MACRO_RUNAWAY_RE = deps.latex_macro_runaway_re
    DOI_BODY_PROSE_MERGE_RE = deps.doi_body_prose_merge_re
    DETACHED_ACCENT_RE = deps.detached_accent_re
    TABLE_SECTION_ABSORB_RE = deps.table_section_absorb_re
    INLINE_INTRA_WORD_SPACE_HTML_RE = deps.inline_intra_word_space_html_re
    INTRA_WORD_SPACE_RE = deps.intra_word_space_re
    TABLE_FOOTNOTE_WORD_LETTER_HTML_RE = deps.table_footnote_word_letter_html_re
    AFFILIATION_DEPARTMENT_GLUE_RE = deps.affiliation_department_glue_re
    SUSPICIOUS_EMAIL_DOMAIN_RE = deps.suspicious_email_domain_re
    BODY_PAGE_HEADER_RE = deps.body_page_header_re
    TABLE_GIBBERISH_FLOW_RE = deps.table_gibberish_flow_re
    FLOAT_OR_METADATA_INTERRUPTION_RE = deps.float_or_metadata_interruption_re
    FLOAT_OR_METADATA_INTRUSION_MARKER_RE = deps.float_or_metadata_intrusion_marker_re
    ESCAPED_SUP_FOOTNOTE_RE = deps.escaped_sup_footnote_re
    REFERENCES_BACKMATTER_INTERLEAVE_RE = deps.references_backmatter_interleave_re
    OLD_SCAN_OCR_GIBBERISH_RE = deps.old_scan_ocr_gibberish_re
    SPLIT_URL_DOMAIN_RE = deps.split_url_domain_re
    SPLIT_AT_EMAIL_RE = deps.split_at_email_re
    BIBLIOGRAPHY_NUMBERING_RESIDUE_RE = deps.bibliography_numbering_residue_re
    PUBLISHER_RECOMMENDATION_BLOCK_RE = deps.publisher_recommendation_block_re
    AFFILIATION_MARKER_RESIDUE_RE = deps.affiliation_marker_residue_re
    PDF_LINE_NUMBER_RESIDUE_RE = deps.pdf_line_number_residue_re

    split_email_match = SPLIT_EMAIL_TEXT_RE.search(plain)
    if split_email_match is not None:
        defects.append(
            _defect(
                defect_id="P64",
                cc_class="CC-04/CC-13",
                check="Email local-part is split before a roman-like suffix",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_email_match.start(), split_email_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Roman-suffix repair split an email local-part such as simonov into 'simono v@...'.",
                proposed_fix_layer="EN polish roman-suffix email guard",
                regression_test="Email addresses like simonov@neuro.nnov.ru remain contiguous after roman-suffix cleanup.",
            )
        )

    runaway_match = RUNAWAY_REPEATED_TEXT_RE.search(plain)
    if runaway_match is not None:
        defects.append(
            _defect(
                defect_id="P65",
                cc_class="CC-04/CC-13",
                check="Runaway repeated word or phrase remains in polish text",
                severity="error",
                block=None,
                snippet=_snippet(plain, runaway_match.start(), runaway_match.end()),
                stage=POLISH_STAGE,
                hypothesis="OCR or sentence-repair cleanup repeated the same token/fragment enough times to corrupt a body paragraph.",
                proposed_fix_layer="EN polish repeated-fragment collapse audit",
                regression_test="Runs such as 'slow, slow, slow...' and repeated optogenetic kinetics fragments are reported.",
            )
        )

    lost_ff_match = LOST_FF_WORD_RE.search(plain)
    if lost_ff_match is not None:
        defects.append(
            _defect(
                defect_id="P66",
                cc_class="CC-04/CC-13",
                check="Common lost ligature word remains in polish text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, lost_ff_match.start(), lost_ff_match.end()),
                stage=POLISH_STAGE,
                hypothesis="OCR or ligature normalization dropped an 'ff', 'fi', or 'fl' pair in common scientific prose.",
                proposed_fix_layer="EN polish OCR spelling/ligature cleanup",
                regression_test="Words such as effect, efficacy, officer, coefficient, flexible, fibers, and diffusion are not left as lost-ligature variants.",
                extra={"match": lost_ff_match.group(0)},
            )
        )

    joined_word_match = next(
        (
            match
            for match in KNOWN_JOINED_WORD_RE.finditer(plain)
            if not _joined_word_match_is_url_slug(plain, match)
        ),
        None,
    )
    if joined_word_match is not None:
        defects.append(
            _defect(
                defect_id="P67",
                cc_class="CC-04/CC-13",
                check="Known joined word or missing separator remains in polish text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, joined_word_match.start(), joined_word_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Line-break, marker, or footnote cleanup failed to restore an ordinary word boundary or separator.",
                proposed_fix_layer="EN polish joined-word and separator cleanup",
                regression_test="Patterns such as 'considerationsincluding', 'timeconsuming', 'theCreative', 'd)2.5D', and 'prostatectomyDeltaVV' are reported.",
                extra={"match": joined_word_match.group(0)},
            )
        )

    float_interrupt_match = FLOAT_SENTENCE_INTERRUPT_RE.search(plain)
    if float_interrupt_match is not None:
        defects.append(
            _defect(
                defect_id="P68",
                cc_class="CC-07/CC-08/CC-13",
                check="Float material interrupts a body sentence",
                severity="error",
                block=None,
                snippet=_snippet(plain, float_interrupt_match.start(), float_interrupt_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A box or figure was inserted between two halves of the same body sentence, preserving a bad PDF reading order.",
                proposed_fix_layer="EN polish float/body reading-order repair",
                regression_test="Sentences split by Box/Figure blocks, such as 'For these ... reasons' or 'also ... require evaluation', are reported.",
            )
        )

    corrupt_email_label_match = CORRUPT_EMAIL_LABEL_RE.search(plain)
    if corrupt_email_label_match is not None:
        defects.append(
            _defect(
                defect_id="P69",
                cc_class="CC-04/CC-13",
                check="E-mail label is corrupted by marker glyphs",
                severity="warning",
                block=None,
                snippet=_snippet(plain, corrupt_email_label_match.start(), corrupt_email_label_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Front-matter symbol cleanup attached an affiliation/correspondence marker to the e-mail label.",
                proposed_fix_layer="EN polish front-matter e-mail label cleanup",
                regression_test="Labels such as 'Me-mail:' and boxed-glyph 'Se-mail:' do not survive in final polish HTML.",
                extra={"match": corrupt_email_label_match.group(0)},
            )
        )

    reference_roman_split_match = REFERENCE_ROMAN_SPLIT_RE.search(plain)
    if reference_roman_split_match is not None:
        defects.append(
            _defect(
                defect_id="P70",
                cc_class="CC-04/CC-13",
                check="Reference journal abbreviation is split before roman-like v",
                severity="warning",
                block=None,
                snippet=_snippet(plain, reference_roman_split_match.start(), reference_roman_split_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Roman-suffix repair or reference cleanup split a journal abbreviation inside the bibliography.",
                proposed_fix_layer="EN polish reference roman-suffix guard",
                regression_test="'Neurosci. Biobehav. Rev.' does not become 'Neurosci. Biobeha v. Rev.' in references.",
            )
        )

    defects.extend(_known_ocr_token_defects(plain, pdf_text, stage=POLISH_STAGE))

    table_note_body_merge_match = TABLE_NOTE_BODY_MERGE_RE.search(plain)
    if table_note_body_merge_match is not None:
        defects.append(
            _defect(
                defect_id="P72",
                cc_class="CC-07/CC-11/CC-13",
                check="Table note is merged into following body prose",
                severity="error",
                block=None,
                snippet=_snippet(plain, table_note_body_merge_match.start(), table_note_body_merge_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A table footnote/legend lost its boundary and swallowed the next body paragraph.",
                proposed_fix_layer="EN polish table-note/body boundary repair",
                regression_test="Table notes ending with symptom direction do not merge into 'studies to evaluate...' body prose.",
            )
        )

    author_marker_glue_match = AUTHOR_MARKER_GLUE_RE.search(plain)
    if author_marker_glue_match is not None:
        author_marker_context = plain[
            max(0, author_marker_glue_match.start() - 220) : author_marker_glue_match.end() + 220
        ]
        if re.match(r"Between\s+100\s+and\b", author_marker_glue_match.group(0), re.IGNORECASE) and re.search(
            r"\bBetween\s+0\s+and\s+100\b[\s\S]{0,240}\bBetween\s+100\s+and\s+200\b[\s\S]{0,240}"
            r"\bBetween\s+200\s+and\s+255\b[\s\S]{0,240}\bperceptual\s+threshold\b",
            author_marker_context,
            re.IGNORECASE,
        ):
            author_marker_glue_match = None

    if author_marker_glue_match is not None:
        defects.append(
            _defect(
                defect_id="P73",
                cc_class="CC-01/CC-04/CC-13",
                check="Author affiliation marker is glued into author line as 100",
                severity="warning",
                block=None,
                snippet=_snippet(plain, author_marker_glue_match.start(), author_marker_glue_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Front-matter superscript or ORCID marker was converted into a plain numeric token in the author list.",
                proposed_fix_layer="EN polish front-matter author-marker cleanup",
                regression_test="Author lines such as 'Mukhiddinov 100 and Soon-Young Kim' are reported as marker glue.",
                extra={"match": author_marker_glue_match.group(0)},
            )
        )

    latex_macro_runaway_match = LATEX_MACRO_RUNAWAY_RE.search(plain)
    if latex_macro_runaway_match is not None:
        defects.append(
            _defect(
                defect_id="P74",
                cc_class="CC-04/CC-13",
                check="Runaway LaTeX macro expansion remains in polish text",
                severity="error",
                block=None,
                snippet=_snippet(plain, latex_macro_runaway_match.start(), latex_macro_runaway_match.end()),
                stage=POLISH_STAGE,
                hypothesis="PDF/HTML import exposed a repeated TeX macro expansion instead of rendered article text.",
                proposed_fix_layer="EN polish TeX macro residue and web-import cleanup",
                regression_test="Repeated ACM-style '\\@ifnextchar' macro runs are reported as corrupt body text.",
            )
        )

    doi_body_merge = next(
        (
            (block, match)
            for block in body_blocks
            for match in [DOI_BODY_PROSE_MERGE_RE.search(block.text)]
            if match is not None
        ),
        None,
    )
    if doi_body_merge is not None:
        doi_body_merge_block, doi_body_merge_match = doi_body_merge
        defects.append(
            _defect(
                defect_id="P75",
                cc_class="CC-07/CC-13",
                check="DOI metadata is merged into following body prose",
                severity="warning",
                block=doi_body_merge_block,
                snippet=_snippet(
                    doi_body_merge_block.text,
                    doi_body_merge_match.start(),
                    doi_body_merge_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="A DOI/front-matter metadata line lost its boundary and swallowed the next paragraph.",
                proposed_fix_layer="EN polish DOI/front-matter boundary repair",
                regression_test="A DOI line followed by body prose such as 'the plasticity...' is reported.",
            )
        )

    detached_accent_match = DETACHED_ACCENT_RE.search(plain)
    if detached_accent_match is not None:
        defects.append(
            _defect(
                defect_id="P76",
                cc_class="CC-04/CC-13",
                check="Detached accent mark remains inside a word or name",
                severity="warning",
                block=None,
                snippet=_snippet(plain, detached_accent_match.start(), detached_accent_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Unicode accent composition was not normalized, leaving names such as Neumuller/Bezier with standalone accent glyphs.",
                proposed_fix_layer="EN polish Unicode accent normalization",
                regression_test="Names like 'Neumuller' and 'Bezier' do not retain detached diaeresis/acute marks.",
                extra={"match": detached_accent_match.group(0)},
            )
        )

    table_section_absorb_block: Block | None = None
    table_section_absorb_match: re.Match[str] | None = None
    for block in polish_blocks:
        table_section_absorb_match = TABLE_SECTION_ABSORB_RE.search(block.text)
        if table_section_absorb_match is not None:
            table_section_absorb_block = block
            break
    if table_section_absorb_block is not None and table_section_absorb_match is not None:
        defects.append(
            _defect(
                defect_id="P77",
                cc_class="CC-07/CC-11/CC-13",
                check="Table block absorbs following sections or figure captions",
                severity="error",
                block=table_section_absorb_block,
                snippet=_snippet(
                    table_section_absorb_block.text,
                    table_section_absorb_match.start(),
                    table_section_absorb_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="A table/list extraction block kept reading through subsequent section headings and body paragraphs.",
                proposed_fix_layer="EN polish table/list boundary and reading-order repair",
                regression_test="Table 3.1 blocks do not swallow '3.8 Data Acquisition' and '3.9 Criteria for Use of Data'.",
            )
        )

    specific_intra_word_matches: set[str] = set()

    inline_intra_word_space_match = INLINE_INTRA_WORD_SPACE_HTML_RE.search(slim_html)
    if inline_intra_word_space_match is not None:
        plain_match = INTRA_WORD_SPACE_RE.search(_strip_tags(inline_intra_word_space_match.group(0)))
        if plain_match is not None:
            specific_intra_word_matches.add(plain_match.group(0))
        defects.append(
            _defect(
                defect_id="P94",
                cc_class="CC-04/CC-13",
                check="Known intra-word spacing residue crosses inline markup",
                severity="warning",
                block=None,
                snippet=_strip_tags(
                    slim_html[
                        max(0, inline_intra_word_space_match.start() - 180) : inline_intra_word_space_match.end()
                        + 180
                    ]
                ),
                stage=POLISH_STAGE,
                hypothesis="OCR kept a word split across anchors or inline formatting, so text-only cleanup could not see the full word.",
                proposed_fix_layer="EN polish inline-aware OCR spacing cleanup",
                regression_test="Inline splits such as '<b>B</b> rain-computer' and anchor-split 'ob je ct s w ould' are classified separately from plain P78 text.",
                extra={"match": plain_match.group(0) if plain_match is not None else _strip_tags(inline_intra_word_space_match.group(0))},
            )
        )

    table_footnote_word_letter_match = TABLE_FOOTNOTE_WORD_LETTER_HTML_RE.search(slim_html)
    if table_footnote_word_letter_match is not None:
        plain_match = INTRA_WORD_SPACE_RE.search(_strip_tags(table_footnote_word_letter_match.group(0)))
        if plain_match is not None:
            specific_intra_word_matches.add(plain_match.group(0))
        defects.append(
            _defect(
                defect_id="P95",
                cc_class="CC-04/CC-13",
                check="Known word letter is misclassified as a table footnote marker",
                severity="warning",
                block=None,
                snippet=_strip_tags(
                    slim_html[
                        max(0, table_footnote_word_letter_match.start() - 180) : table_footnote_word_letter_match.end()
                        + 180
                    ]
                ),
                stage=POLISH_STAGE,
                hypothesis="A terminal letter of a known word or author name was preserved as z2m-table-fn instead of normal inline text.",
                proposed_fix_layer="EN polish table footnote/word-boundary cleanup",
                regression_test="Known names such as Leporini in tables are reported as table-footnote letter splits, not generic P78 spacing.",
                extra={"match": plain_match.group(0) if plain_match is not None else _strip_tags(table_footnote_word_letter_match.group(0))},
            )
        )

    intra_word_space_match = next(
        (
            match
            for match in INTRA_WORD_SPACE_RE.finditer(plain)
            if match.group(0) not in specific_intra_word_matches
        ),
        None,
    )
    if (
        intra_word_space_match is not None
        and intra_word_space_match.group(0) not in specific_intra_word_matches
    ):
        defects.append(
            _defect(
                defect_id="P78",
                cc_class="CC-04/CC-13",
                check="Known intra-word spacing residue remains in polish text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, intra_word_space_match.start(), intra_word_space_match.end()),
                stage=POLISH_STAGE,
                hypothesis="OCR kept spurious character gaps inside ordinary words after final polish cleanup.",
                proposed_fix_layer="EN polish intra-word spacing cleanup",
                regression_test="Fragments such as 'ob je ct s w ould' and 'safe ty c oncerns' are reported.",
                extra={"match": intra_word_space_match.group(0)},
            )
        )

    affiliation_department_glue_match = AFFILIATION_DEPARTMENT_GLUE_RE.search(plain)
    if affiliation_department_glue_match is not None:
        defects.append(
            _defect(
                defect_id="P79",
                cc_class="CC-01/CC-04/CC-13",
                check="Front-matter affiliation number is glued to Department",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    affiliation_department_glue_match.start(),
                    affiliation_department_glue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Superscript affiliation markers were flattened and attached to the following affiliation label.",
                proposed_fix_layer="EN polish front-matter affiliation spacing cleanup",
                regression_test="Affiliation labels such as '1Department' and '5Department' are reported.",
                extra={"match": affiliation_department_glue_match.group(0)},
            )
        )

    suspicious_email_domain_match = SUSPICIOUS_EMAIL_DOMAIN_RE.search(plain)
    if suspicious_email_domain_match is not None:
        defects.append(
            _defect(
                defect_id="P80",
                cc_class="CC-04/CC-13",
                check="Institutional email domain looks OCR-truncated",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    suspicious_email_domain_match.start(),
                    suspicious_email_domain_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Manual review found an institution-specific e-mail typo alongside otherwise consistent domain spellings.",
                proposed_fix_layer="EN polish front-matter e-mail/domain OCR cleanup",
                regression_test="Suspicious Florence-domain typo '@unfi.it' is reported.",
                extra={"match": suspicious_email_domain_match.group(0)},
            )
        )

    body_page_header_match = BODY_PAGE_HEADER_RE.search(plain)
    if body_page_header_match is not None:
        defects.append(
            _defect(
                defect_id="P81",
                cc_class="CC-07/CC-13",
                check="Page header or footer remains in body prose",
                severity="warning",
                block=None,
                snippet=_snippet(plain, body_page_header_match.start(), body_page_header_match.end()),
                stage=POLISH_STAGE,
                hypothesis="PDF page furniture was preserved as ordinary paragraph text after polish cleanup.",
                proposed_fix_layer="EN polish page furniture cleanup",
                regression_test="Headers such as 'FRANCO ET AL. | 1915' are reported.",
                extra={"match": body_page_header_match.group(0)},
            )
        )

    table_gibberish_flow_match = TABLE_GIBBERISH_FLOW_RE.search(plain)
    if table_gibberish_flow_match is not None:
        defects.append(
            _defect(
                defect_id="P82",
                cc_class="CC-04/CC-07/CC-11/CC-13",
                check="Table data has OCR-scrambled column headers",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    table_gibberish_flow_match.start(),
                    table_gibberish_flow_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="A table extraction block lost column structure and preserved heavily scrambled OCR tokens.",
                proposed_fix_layer="EN polish table OCR/column structure audit",
                regression_test="Uroflow table fragments such as 'nales 5 ted Q a rates' and malformed P-value runs are reported.",
            )
        )

    float_or_metadata_interruption_match = next(
        (
            match
            for match in FLOAT_OR_METADATA_INTERRUPTION_RE.finditer(plain)
            if FLOAT_OR_METADATA_INTRUSION_MARKER_RE.search(match.group(0)) is not None
        ),
        None,
    )
    if float_or_metadata_interruption_match is not None:
        defects.append(
            _defect(
                defect_id="P83",
                cc_class="CC-07/CC-08/CC-13",
                check="Body phrase is interrupted by float or metadata material",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    float_or_metadata_interruption_match.start(),
                    float_or_metadata_interruption_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="PDF reading order inserted figure, footnote, or journal metadata between two halves of one body phrase.",
                proposed_fix_layer="EN polish float/body reading-order repair",
                regression_test="Known splits such as 'printed on swell paper to ... form a tactile rendering' and 'mul- ... timodal sensing' are reported.",
            )
        )

    escaped_sup_footnote_match = ESCAPED_SUP_FOOTNOTE_RE.search(plain)
    if escaped_sup_footnote_match is not None:
        defects.append(
            _defect(
                defect_id="P84",
                cc_class="CC-01/CC-04/CC-13",
                check="Escaped footnote superscript markup remains as visible text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, escaped_sup_footnote_match.start(), escaped_sup_footnote_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A raw escaped footnote marker was not decoded or converted into a proper footnote marker.",
                proposed_fix_layer="EN polish escaped-footnote/front-matter cleanup",
                regression_test="Visible residues such as '& lt;sup>2' and '& lt;sup>3' are reported.",
                extra={"match": escaped_sup_footnote_match.group(0)},
            )
        )

    references_backmatter_interleave_match = REFERENCES_BACKMATTER_INTERLEAVE_RE.search(plain)
    if references_backmatter_interleave_match is not None:
        defects.append(
            _defect(
                defect_id="P85",
                cc_class="CC-07/CC-13",
                check="References are interleaved with back-matter sections",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    references_backmatter_interleave_match.start(),
                    references_backmatter_interleave_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Back-matter continuation text was placed after an early References heading, mixing article metadata with bibliography entries.",
                proposed_fix_layer="EN polish back-matter/reference ordering repair",
                regression_test="Frontiers-style back matter split as 'ETHICS STATEMENT ... REFERENCES ... University of Bath ... AUTHOR CONTRIBUTIONS' is reported.",
            )
        )

    split_dot_email_match = _find_split_dot_email_match(plain)
    if split_dot_email_match is not None:
        defects.append(
            _defect(
                defect_id="P86",
                cc_class="CC-01/CC-04/CC-13",
                check="Email address is split after a dot",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_dot_email_match.start(), split_dot_email_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Line wrapping or sentence cleanup inserted whitespace inside an e-mail local-part.",
                proposed_fix_layer="EN polish e-mail normalization",
                regression_test="Visible e-mails such as 'jan. krhut@fno.cz' are reported as split local-parts.",
                extra={"match": split_dot_email_match.group(0)},
            )
        )

    old_scan_ocr_gibberish_match = OLD_SCAN_OCR_GIBBERISH_RE.search(plain)
    if old_scan_ocr_gibberish_match is not None:
        defects.append(
            _defect(
                defect_id="P87",
                cc_class="CC-04/CC-13",
                check="Old-scan OCR gibberish remains in polish text",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    old_scan_ocr_gibberish_match.start(),
                    old_scan_ocr_gibberish_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Manual full-text review found old scanned PDFs with residual OCR tokens and table/caption gibberish that normal article cleanup cannot safely repair.",
                proposed_fix_layer="EN polish OCR-quality gate / old-scan routing",
                regression_test="Old-scan residues such as 'LUMBAH I - i', 'The (!I G :. nosis', 'v&me', 'foriTi', and 'kcounl/mg prolan' are reported.",
                extra={"match": old_scan_ocr_gibberish_match.group(0)},
            )
        )

    split_url_domain_match = SPLIT_URL_DOMAIN_RE.search(plain)
    if split_url_domain_match is not None:
        defects.append(
            _defect(
                defect_id="P88",
                cc_class="CC-04/CC-13",
                check="URL domain is split by OCR whitespace",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_url_domain_match.start(), split_url_domain_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Reference URL normalization missed whitespace inserted inside a domain name.",
                proposed_fix_layer="EN polish URL/domain whitespace cleanup",
                regression_test="Split domains such as 'www. osh a.europa.eu' are reported.",
                extra={"match": split_url_domain_match.group(0)},
            )
        )

    split_at_email_match = SPLIT_AT_EMAIL_RE.search(plain)
    if split_at_email_match is not None:
        defects.append(
            _defect(
                defect_id="P89",
                cc_class="CC-01/CC-04/CC-13",
                check="Email address is split after at-sign",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_at_email_match.start(), split_at_email_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Line wrapping or front-matter cleanup inserted whitespace between the at-sign and the email domain.",
                proposed_fix_layer="EN polish e-mail normalization",
                regression_test="Visible e-mails such as 'iskandar@ neurosurgery.wisc.edu' are reported as split domains.",
                extra={"match": split_at_email_match.group(0)},
            )
        )

    bibliography_numbering_residue_match = BIBLIOGRAPHY_NUMBERING_RESIDUE_RE.search(plain)
    if (
        bibliography_numbering_residue_match is not None
        and not _bibliography_numbering_residue_is_clean_reference_boundary(
            polish_html,
            bibliography_numbering_residue_match.group(0),
        )
    ):
        defects.append(
            _defect(
                defect_id="P90",
                cc_class="CC-02/CC-04/CC-13",
                check="Bibliography numbering is duplicated or shifted",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    bibliography_numbering_residue_match.start(),
                    bibliography_numbering_residue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Reference-list line wrapping preserved a previous bibliography number as visible text before the next entry.",
                proposed_fix_layer="EN polish reference numbering cleanup",
                regression_test="Reference runs such as '20. 20 van Tulder' and '33. 32 De Nunzio' are reported.",
                extra={"match": bibliography_numbering_residue_match.group(0)},
            )
        )

    publisher_recommendation_match = PUBLISHER_RECOMMENDATION_BLOCK_RE.search(plain)
    if publisher_recommendation_match is not None:
        defects.append(
            _defect(
                defect_id="P91",
                cc_class="CC-07/CC-13",
                check="Publisher recommendation sidebar remains in article body",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    publisher_recommendation_match.start(),
                    publisher_recommendation_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Publisher landing-page recommendations were preserved before the real article body.",
                proposed_fix_layer="EN polish publisher chrome/sidebar cleanup",
                regression_test="IOP front matter such as 'You may also like ... ChArUco-based 3D scanner' is reported.",
                extra={"match": publisher_recommendation_match.group(0)},
            )
        )

    affiliation_marker_residue_match = AFFILIATION_MARKER_RESIDUE_RE.search(plain)
    if affiliation_marker_residue_match is not None:
        defects.append(
            _defect(
                defect_id="P92",
                cc_class="CC-01/CC-04/CC-13",
                check="Author affiliation markers are glued or left as a numeric run",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    affiliation_marker_residue_match.start(),
                    affiliation_marker_residue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Front-matter cleanup did not separate author names from affiliation markers or compact a leftover affiliation-number run.",
                proposed_fix_layer="EN polish author/affiliation normalization",
                regression_test="Author residues such as 'Yary Volpe1' and 'İlbey 1 1 2 3 1 1' are reported.",
                extra={"match": affiliation_marker_residue_match.group(0)},
            )
        )

    pdf_line_number_residue_match = PDF_LINE_NUMBER_RESIDUE_RE.search(plain)
    if pdf_line_number_residue_match is not None:
        defects.append(
            _defect(
                defect_id="P93",
                cc_class="CC-04/CC-07/CC-13",
                check="Publisher line numbers remain in body prose",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    pdf_line_number_residue_match.start(),
                    pdf_line_number_residue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="PDF line numbers from an accepted manuscript were preserved as ordinary article text.",
                proposed_fix_layer="EN polish page/line-number cleanup",
                regression_test="RSC accepted-manuscript line numbers such as 'with 20 the sizes' and '_{75} incubated' are reported.",
                extra={"match": pdf_line_number_residue_match.group(0)},
            )
        )

    return defects
