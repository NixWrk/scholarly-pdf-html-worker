from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re

from zoteropdf2md.html_stages import POLISH_STAGE_NAME, RAW_STAGE_NAME
from zoteropdf2md.quality_loop.audit_blocks import (
    Block,
    Defect,
    plain_text,
    snippet,
    strip_tags,
    structure_html,
)
from zoteropdf2md.quality_loop.audit_diagnostics import make_defect
from zoteropdf2md.quality_loop.audit_p35 import replacement_char_defects
from zoteropdf2md.quality_loop.audit_reference_identity import is_references_block


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
