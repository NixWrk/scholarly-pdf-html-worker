from __future__ import annotations

from html import unescape
import re

from zoteropdf2md.html_stages import POLISH_STAGE_NAME, RAW_STAGE_NAME
from zoteropdf2md.quality_loop.audit_blocks import Block, Defect, snippet, unit_diagnostic_texts
from zoteropdf2md.quality_loop.audit_diagnostics import make_defect


UNIT_FLATTEN_RE = re.compile(
    r"\b(?:mC\s*cm|cd\s*m|kg\s*h|mg\s*kg\s*h)\s*[-\u2212]\s*\d+\b|"
    r"\b(?-i:(?:u|\u00b5|\u03bc)m)\s*[23]\b|"
    r"\bmCcm[-\u2212]\d+\b|"
    r"\b\d+(?:\.\d+)?\s*(?-i:(?:u|\u00b5|\u03bc)?m)\s*[23]\b|"
    r"\b\d+(?:\.\d+)?Vand\b|"
    r"\b\d+(?:\.\d+)?\s*(?:u|µ|μ)Aand\b",
    re.IGNORECASE,
)
DEGREE_DEFECT_RE = re.compile(r"\b\d+(?:\.\d+)?\s+\u25e6(?=\W|$)")
LINKED_UNIT_EXP_DEFECT_RE = re.compile(
    r"\b(?:mm\s*s|cm\s*s|m\s*s|cd\s*m|mC\s*cm|(?:u|µ|μ)C\s*cm|cm|mm|m)\s*"
    r"(?:[-\u2212]|\s+\u2212)\s*1\b",
    re.IGNORECASE,
)
RESIDUAL_UNIT_TEX_RE = re.compile(
    r"\\\(\s*\\mu\s*\\\)\s*(?:C|A|m)\b|"
    r"\\muC\b|"
    r"\\mu\s*m\s*\^\{?2\}?|"
    r"\\mu\\text\{m\}|"
    r"mC\s*cm\s*<sup>\s*-?\s*<a\b",
    re.IGNORECASE,
)
JOINED_PROSE_TOKEN_RE = re.compile(
    r"\b(?:Vwater|0\.04for|forintracorticalstimulation|20nCfor|"
    r"chosenasthiswasregardedasthenominal|chosenasthiswasregardedasthe|"
    r"\d+(?:\.\d+)?(?:V|nC|(?:u|Вµ|Ој)A)(?:and|for|was))\b",
    re.IGNORECASE,
)
INLINE_TEX_RE = re.compile(r"\\\(([\s\S]{0,800}?)\\\)")
MATH_TAG_WITH_CITATION_RE = re.compile(r"<math\b[\s\S]{0,800}?\[\d+\][\s\S]{0,800}?</math>", re.IGNORECASE)
EQUATION_ABSORB_RE = re.compile(
    r"\(\d{1,3}\)\s+(?:To make|As shown|where\b|Fig\.|Figure|Equation)",
    re.IGNORECASE,
)
DISPLAY_MATH_OCR_RE = re.compile(r"(?:\\omega\s*}\s*\{\s*2m|omega\s*/\s*2m|\\frac\{\\omega\}\{2m\})")


def inline_tex_contains_citation_bracket(tex: str) -> bool:
    for match in re.finditer(r"\[\s*\d{1,4}\s*\]", tex):
        prefix = tex[: match.start()]
        if re.search(r"\\[A-Za-z]+\*?\s*$", prefix):
            continue
        return True
    return False


def unit_match_is_repaired_in_raw(match_text: str, raw: str) -> bool:
    raw_unescaped = unescape(raw)
    if re.search(r"(?-i:(?:u|\u00b5|\u03bc)m)\s*[23]\b", match_text, re.IGNORECASE):
        return bool(
            re.search(
                r"(?-i:(?:u|\u00b5|\u03bc)m)\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[23]\s*</sup>",
                raw_unescaped,
                re.IGNORECASE,
            )
            or (
                "data-z2m-tex" in raw_unescaped
                and re.search(r"(?-i:(?:u|\u00b5|\u03bc)m)\s*\^\{?\s*[23]\s*\}?", raw_unescaped)
            )
        )
    if re.search(r"\b\d+(?:\.\d+)?\s*(?-i:(?:u|\u00b5|\u03bc)?m)\s*[23]\b", match_text, re.IGNORECASE):
        return bool(
            re.search(
                r"(?-i:(?:u|\u00b5|\u03bc)?m)\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[23]\s*</sup>",
                raw_unescaped,
                re.IGNORECASE,
            )
            or (
                "data-z2m-tex" in raw_unescaped
                and re.search(r"(?-i:(?:u|\u00b5|\u03bc)?m)\s*\^\{?\s*[23]\s*\}?", raw_unescaped)
            )
        )
    if re.search(r"\b(?:mC\s*cm|cd\s*m|kg\s*h|mg\s*kg\s*h)\s*[-\u2212]\s*\d+\b", match_text, re.IGNORECASE):
        return bool(re.search(r"<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*-\d+\s*</sup>", raw_unescaped, re.IGNORECASE))
    return False


def unit_math_defects(
    raw_html: str,
    polish_blocks: list[Block],
    *,
    raw_stage: str = RAW_STAGE_NAME,
    polish_stage: str = POLISH_STAGE_NAME,
) -> list[Defect]:
    defects: list[Defect] = []
    for block in polish_blocks:
        for diagnostic_text in unit_diagnostic_texts(block):
            unit_match = UNIT_FLATTEN_RE.search(diagnostic_text)
            if unit_match is not None and unit_match_is_repaired_in_raw(unit_match.group(0), block.raw):
                unit_match = None
            linked_unit_match = LINKED_UNIT_EXP_DEFECT_RE.search(diagnostic_text)
            if linked_unit_match is not None and "z2m-unit-exp" in block.raw:
                linked_unit_match = None
            joined_match = JOINED_PROSE_TOKEN_RE.search(diagnostic_text)
            match = unit_match or DEGREE_DEFECT_RE.search(diagnostic_text) or linked_unit_match or joined_match
            if match:
                defects.append(
                    make_defect(
                        defect_id="P06",
                        cc_class="CC-04",
                        check="Flattened or malformed unit/exponent/spacing pattern",
                        severity="warning",
                        block=block,
                        snippet=diagnostic_text or block.text,
                        stage=polish_stage,
                        hypothesis="Unit/math normalization did not preserve exponent, micro/degree symbol, or spacing.",
                        proposed_fix_layer="EN polish unit normalization before citation linkification",
                        regression_test="Normalize micro units, cm^-2, um^2, degree symbols, and value-unit-word spacing.",
                    )
                )
                break
        if defects and defects[-1].id == "P06":
            break

    for block in polish_blocks:
        if RESIDUAL_UNIT_TEX_RE.search(block.raw):
            defects.append(
                make_defect(
                    defect_id="P23",
                    cc_class="CC-04/CC-05",
                    check="Residual unit-only TeX fragment remains in polish",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="A simple scientific unit was left as inline TeX or kept a linked unit exponent.",
                    proposed_fix_layer="EN polish unit normalization after MathML/TeX conversion",
                    regression_test="Unit-only TeX fragments like \\(\\mu\\) C, \\muC cm^-2, and \\mu m^2 normalize to readable unit text.",
                )
            )
            break

    for block in polish_blocks:
        if MATH_TAG_WITH_CITATION_RE.search(block.raw) or any(
            inline_tex_contains_citation_bracket(match.group(1))
            for match in INLINE_TEX_RE.finditer(block.raw)
        ):
            defects.append(
                make_defect(
                    defect_id="P07",
                    cc_class="CC-05",
                    check="Citation appears inside math span",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Math conversion swallowed an adjacent citation into the formula.",
                    proposed_fix_layer="Marker raw math extraction or EN polish math/citation boundary cleanup",
                    regression_test="Citations like [17] after equations must stay outside math spans and link normally.",
                )
            )
            break

    raw_match = DISPLAY_MATH_OCR_RE.search(raw_html)
    polish_math_text = "\n".join(block.raw for block in polish_blocks)
    if raw_match and DISPLAY_MATH_OCR_RE.search(polish_math_text):
        defects.append(
            make_defect(
                defect_id="P08",
                cc_class="CC-05/CC-13",
                check="Suspicious raw display-math OCR substitution",
                severity="warning",
                block=None,
                snippet=snippet(raw_html, raw_match.start(), raw_match.end()),
                stage=raw_stage,
                hypothesis="A displayed equation likely contains an OCR/math-recognition substitution.",
                proposed_fix_layer="raw audit surfacing or math-quality audit",
                regression_test="Catch omega_0 becoming 2m and similar impossible denominator tokens.",
            )
        )
    return defects


def equation_table_defects(
    polish_blocks: list[Block],
    *,
    polish_stage: str = POLISH_STAGE_NAME,
) -> list[Defect]:
    defects: list[Defect] = []
    for block in polish_blocks:
        if block.block_type.lower() == "equation" and EQUATION_ABSORB_RE.search(block.text):
            defects.append(
                make_defect(
                    defect_id="P09",
                    cc_class="CC-06",
                    check="Equation block absorbed following prose",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Equation/prose merge logic crossed a numbered display equation boundary.",
                    proposed_fix_layer="EN polish equation block assembly",
                    regression_test="Equation (1) and following explanatory paragraph must remain separate blocks.",
                )
            )
            break

    for block in polish_blocks:
        if block.block_type.lower() == "equation" and re.match(r"^\s*(?:Fig\.?|Figure)\s+\d+\s+shows\b", block.text, re.IGNORECASE):
            defects.append(
                make_defect(
                    defect_id="P10",
                    cc_class="CC-06",
                    check="Mixed prose/math paragraph classified as equation",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="A prose paragraph containing math was treated as a pure equation block.",
                    proposed_fix_layer="Marker raw block typing or EN polish mixed block handling",
                    regression_test="Paragraphs like 'Fig. 4 shows ... f(...) = ...' stay text-with-math.",
                )
            )
            break

    for index, block in enumerate(polish_blocks):
        if not re.fullmatch(r"\(\d{1,3}\)", block.text):
            continue
        previous = polish_blocks[max(0, index - 4) : index]
        if any(prev.tag == "table" or prev.id.startswith("table-") for prev in previous):
            defects.append(
                make_defect(
                    defect_id="P11",
                    cc_class="CC-06/CC-07",
                    check="Orphan equation number appears after table/float",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="A table or float was inserted between an equation body and its number.",
                    proposed_fix_layer="EN polish equation-number atomicity and float-safe relocation",
                    regression_test="No table/title/paragraph may appear between equation body and equation number.",
                )
            )
            break
    return defects
