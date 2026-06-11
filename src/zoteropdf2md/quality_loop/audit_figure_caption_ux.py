from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import re

from zoteropdf2md.html_stages import POLISH_STAGE_NAME
from zoteropdf2md.quality_loop.audit_blocks import Block, Defect, plain_text, snippet
from zoteropdf2md.quality_loop.audit_diagnostics import make_defect
from zoteropdf2md.quality_loop.audit_reference_identity import REFERENCES_HEADING_RE


TABLE_CAPTION_RE = re.compile(r"^\s*(?:TABLE|Table)\s+(?:[IVXLCM]+|\d+)\b", re.IGNORECASE)
MULTIPANEL_FIG_REF_RE = re.compile(
    r"\bfigures?\s+\d+\s*\([A-Za-z]\)\s*,\s*\([A-Za-z]\)",
    re.IGNORECASE,
)
PAGE_FURNITURE_CONTINUATION_RE = re.compile(
    r"(?:Copyright\s+\d{4}[\s\S]{0,120}?</p>\s*<p\b[^>]*>\s*(?:<a\b[^>]*>\s*)?\d{4}\s+[a-z]\s*,\s*[a-z]\)|"
    r"Correspondence:[\s\S]{0,120}?@\S+\s+[a-z]{1,4}\.\s+\d{4}\))",
    re.IGNORECASE,
)
CAPTION_INTRUSION_RE = re.compile(
    r"human input\s*\(required\)\s+image-modeling task",
    re.IGNORECASE,
)
CAPTION_TEX_RESIDUE_RE = re.compile(
    r"(?:\\\\|\\label\b|\\textbf\b|&lt;\s*/?\s*a\b|href=&quot;|href=\"<a\s+href=)",
    re.IGNORECASE,
)
TABLE_CAPTION_NODE_RE = re.compile(
    r"<(?P<tag>p|h[1-6]|figcaption)\b(?=[^>]*\bz2m-table-caption\b)[^>]*>"
    r"[\s\S]*?</(?P=tag)>",
    re.IGNORECASE,
)
BIORENDER_CAPTION_URL_RE = re.compile(r"BioRender\.com/", re.IGNORECASE)
BIORENDER_CAPTION_SPLIT_RE = re.compile(
    r"created\s+(?:in\s+)?BioRender[\s\S]{0,600}?</p>\s*"
    r"<h[1-6]\b[^>]*\bz2m-figure-caption\b[^>]*>[\s\S]{0,300}?BioRender\.com/"
    r"[\s\S]{0,300}?</h[1-6]>\s*"
    r"<p\b[^>]*\bz2m-figure-caption\b[^>]*>\s*comparison\s+shows\b",
    re.IGNORECASE,
)


def caption_raw_for_tex_residue(block: Block) -> str:
    if block.tag == "table":
        return ""
    if "z2m-table-unit" in block.classes:
        caption_match = TABLE_CAPTION_NODE_RE.search(block.raw)
        if caption_match is not None:
            return caption_match.group(0)
        return re.split(r"<table\b", block.raw, maxsplit=1, flags=re.IGNORECASE)[0]
    return block.raw


def figure_caption_ux_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    looks_like_figure_caption: Callable[[Block], bool],
    is_supplementary_figure_block: Callable[[Block], bool],
    is_handled_missing_figure_block: Callable[[Block], bool],
    has_nearby_image: Callable[[list[Block], int], bool],
    has_nearby_missing_figure_warning: Callable[[list[Block], int], bool],
    source_pdf_text_confirms_float_gap: Callable[[str, str, str], bool],
    pdf_text: str = "",
    has_internal_links: bool = False,
    table_caption_re: re.Pattern[str] = TABLE_CAPTION_RE,
    references_heading_re: re.Pattern[str] = REFERENCES_HEADING_RE,
    polish_stage: str = POLISH_STAGE_NAME,
) -> list[Defect]:
    defects: list[Defect] = []
    split_match = BIORENDER_CAPTION_SPLIT_RE.search(polish_html)
    if split_match is not None:
        defects.append(
            make_defect(
                defect_id="P31",
                cc_class="CC-12/CC-13",
                check="BioRender caption URL split into standalone heading",
                severity="warning",
                block=None,
                snippet=snippet(plain_text(polish_html), split_match.start(), split_match.end()),
                stage=polish_stage,
                hypothesis="Marker split a figure caption credit/URL into a heading-like fragment.",
                proposed_fix_layer="EN polish caption-fragment merger",
                regression_test="BioRender URL heading between caption fragments is merged back into one figure caption paragraph.",
            )
        )

    for block in polish_blocks:
        is_caption = bool(looks_like_figure_caption(block) or table_caption_re.match(block.text))
        caption_raw = caption_raw_for_tex_residue(block) if is_caption else ""
        if caption_raw and CAPTION_TEX_RESIDUE_RE.search(caption_raw):
            defects.append(
                make_defect(
                    defect_id="P12",
                    cc_class="CC-12",
                    check="Caption contains TeX/escaped-link residue",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Caption cleanup left TeX linebreaks, labels, formatting commands, or escaped anchor text visible.",
                    proposed_fix_layer="EN polish caption cleanup",
                    regression_test="Captions with BioRender links, \\label, \\textbf, and \\\\ linebreaks render as readable caption text.",
                )
            )
            break

    for index, block in enumerate(polish_blocks[:-1]):
        if "z2m-figure-caption" not in block.classes or "biorender" not in block.text.lower():
            continue
        next_block = polish_blocks[index + 1]
        if (
            "z2m-figure-caption" in next_block.classes
            and next_block.tag.startswith("h")
            and BIORENDER_CAPTION_URL_RE.search(next_block.text)
        ):
            defects.append(
                make_defect(
                    defect_id="P31",
                    cc_class="CC-12/CC-13",
                    check="BioRender caption URL split into standalone heading",
                    severity="warning",
                    block=next_block,
                    snippet=f"{block.text[-160:]} {next_block.text}",
                    stage=polish_stage,
                    hypothesis="Marker split a figure caption credit/URL into a heading-like fragment.",
                    proposed_fix_layer="EN polish caption-fragment merger",
                    regression_test="BioRender URL heading between caption fragments is merged back into one figure caption paragraph.",
                )
            )
            break

    figure_id_counts = Counter(
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[^"\']+)\1', polish_html, re.IGNORECASE)
    )

    for block in polish_blocks:
        if block.tag == "table":
            continue
        is_figure_caption = looks_like_figure_caption(block)
        if (
            is_figure_caption
            and not is_supplementary_figure_block(block)
            and not is_handled_missing_figure_block(block)
            and figure_id_counts.get(block.id, 0) <= 1
            and not has_nearby_image(polish_blocks, block.index)
            and not has_nearby_missing_figure_warning(polish_blocks, block.index)
        ):
            defects.append(
                make_defect(
                    defect_id="P13",
                    cc_class="CC-08/CC-13",
                    check="Figure caption has no nearby image",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="The final HTML may silently present a caption-only figure.",
                    proposed_fix_layer="raw audit surfacing and EN polish missing-figure warning block",
                    regression_test="Caption-without-image produces a visible user-facing warning.",
                )
            )
            break

    for index, block in enumerate(polish_blocks):
        if "z2m-missing-figure-warning" not in block.classes:
            continue
        window = polish_blocks[index + 1 : min(len(polish_blocks), index + 8)]
        if any(candidate.has_figure_visual for candidate in window):
            defects.append(
                make_defect(
                    defect_id="P16",
                    cc_class="CC-08/CC-13",
                    check="Missing-figure warning appears before a delayed nearby image",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Figure/caption assembly used too narrow a search window and warned even though the image was present later.",
                    proposed_fix_layer="EN polish figure target assignment and missing-warning scan",
                    regression_test="Delayed image within a caption continuation run is targeted instead of warning.",
                )
            )
            break

    for block in polish_blocks:
        if not block.id.startswith("fig-") or block.has_figure_visual:
            continue
        if figure_id_counts.get(block.id, 0) > 1:
            continue
        if is_supplementary_figure_block(block):
            continue
        if is_handled_missing_figure_block(block):
            continue
        if has_nearby_missing_figure_warning(polish_blocks, block.index):
            continue
        if re.search(rf"href\s*=\s*['\"]#{re.escape(block.id)}['\"]", polish_html, re.IGNORECASE):
            defects.append(
                make_defect(
                    defect_id="P14",
                    cc_class="CC-10",
                    check="Figure link target is caption paragraph, not whole figure block",
                    severity="info",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Figure navigation targets the caption ID, so the image may be above the viewport.",
                    proposed_fix_layer="EN polish HTML/CSS target wrapper and scroll behavior",
                    regression_test="Clicking #fig-* reveals the image and caption together.",
                )
            )
            break

    if has_internal_links and (":target" not in polish_html or "scroll-margin" not in polish_html):
        defects.append(
            make_defect(
                defect_id="P15",
                cc_class="CC-03/CC-10",
                check="Internal-link target UX styling is missing or incomplete",
                severity="info",
                block=None,
                snippet="internal links found, but no shared :target/scroll-margin behavior",
                stage=polish_stage,
                hypothesis="Internal links may scroll/focus/highlight inconsistently across articles.",
                proposed_fix_layer="EN polish readability CSS/optional JS",
                regression_test="Reference, figure, table, equation, and section targets share scroll offset and target highlight.",
            )
        )

    for block in polish_blocks:
        if MULTIPANEL_FIG_REF_RE.search(block.text) and "z2m-fig-link" not in block.raw:
            defects.append(
                make_defect(
                    defect_id="P17",
                    cc_class="CC-10",
                    check="Plural multipanel figure reference is not linked",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Figure-reference grammar misses plural forms like 'figures 4(A), (B)'.",
                    proposed_fix_layer="EN polish figure-reference parser",
                    regression_test="Link plural multipanel references to the base figure target.",
                )
            )
            break

    for index, block in enumerate(polish_blocks[:-2]):
        if block.tag != "p" or looks_like_figure_caption(block) or references_heading_re.match(block.text):
            continue
        left = block.text.strip()
        if not re.search(r"\b(?:and|or|but|with|of|the|sensor's)\s*$", left, re.IGNORECASE):
            continue
        saw_float = False
        for candidate in polish_blocks[index + 1 : min(len(polish_blocks), index + 12)]:
            if (
                candidate.has_figure_visual
                or "z2m-float-unit" in candidate.classes
                or candidate.tag in {"table", "figure"}
                or looks_like_figure_caption(candidate)
                or table_caption_re.match(candidate.text)
            ):
                saw_float = True
                continue
            if not saw_float:
                break
            if candidate.tag == "p" and candidate.text and candidate.text[0].islower():
                if source_pdf_text_confirms_float_gap(left, candidate.text, pdf_text):
                    break
                defects.append(
                    make_defect(
                        defect_id="P30",
                        cc_class="CC-07/CC-13",
                        check="Likely float interruption inside body sentence",
                        severity="warning",
                        block=block,
                        snippet=f"{left} ... {candidate.text[:160]}",
                        stage=polish_stage,
                        hypothesis="A figure/table unit may still split a sentence continuation.",
                        proposed_fix_layer="EN polish float-aware reading-order repair",
                        regression_test="A paragraph ending in a conjunction before a float rejoins a lowercase continuation after the float.",
                    )
                )
                return defects
            break

    page_match = PAGE_FURNITURE_CONTINUATION_RE.search(polish_html)
    if page_match is not None:
        defects.append(
            make_defect(
                defect_id="P18",
                cc_class="CC-01/CC-13",
                check="Page furniture interrupts a sentence continuation",
                severity="warning",
                block=None,
                snippet=snippet(polish_html, page_match.start(), page_match.end()),
                stage=polish_stage,
                hypothesis="A page footer/front-matter block was treated as prose or blocked joining across a page/float gap.",
                proposed_fix_layer="EN polish page-furniture cleanup and continuation repair",
                regression_test="Copyright/correspondence/footer blocks stay separate and sentence tails rejoin surrounding prose.",
            )
        )

    caption_intrusion = CAPTION_INTRUSION_RE.search(plain_text(polish_html))
    if caption_intrusion is not None:
        defects.append(
            make_defect(
                defect_id="P19",
                cc_class="CC-12/CC-13",
                check="Figure-caption prose intrusion remains after backslash cleanup",
                severity="warning",
                block=None,
                snippet=snippet(plain_text(polish_html), caption_intrusion.start(), caption_intrusion.end()),
                stage=polish_stage,
                hypothesis="A caption/body split was cleaned syntactically but not reassembled semantically.",
                proposed_fix_layer="EN polish caption-intrusion recovery",
                regression_test="Caption ending at '(required)' must not swallow body prose or drop the intended continuation.",
            )
        )
    return defects
