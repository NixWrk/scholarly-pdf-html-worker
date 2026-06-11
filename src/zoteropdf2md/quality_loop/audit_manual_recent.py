from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

from zoteropdf2md.html_stages import POLISH_STAGE_NAME
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
