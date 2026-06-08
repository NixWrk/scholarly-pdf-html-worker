from __future__ import annotations

from collections.abc import Callable
import re

from zoteropdf2md.quality_loop.audit_blocks import Block, Defect
from zoteropdf2md.quality_loop.audit_diagnostics import make_defect


ROMAN_WORD_SPLIT_RE = re.compile(r"\b(?P<prefix>[A-Z][A-Za-z]{3,})\s+(?P<suffix>v|i|x|vi|ix)\b")
ROMAN_WORD_SPLIT_FALSE_PREFIXES = {
    "appendix",
    "assuming",
    "cardio",
    "chapter",
    "coordinates",
    "dcon",
    "definingx",
    "figure",
    "haystackd",
    "mean",
    "mimics",
    "node",
    "numbered",
    "reference",
    "section",
    "table",
    "type",
    "where",
}


RomanSplitTelemetry = tuple[str, str, str, str, str, Block, re.Match[str]]


def roman_word_split_defects(
    polish_blocks: list[Block],
    *,
    references_heading_re: re.Pattern[str],
    is_references_block: Callable[[Block, bool], bool],
    looks_like_affiliation_label_roman_boundary: Callable[[Block, re.Match[str]], bool],
    stage: str,
) -> list[Defect]:
    defects: list[Defect] = []
    references_started = False
    roman_split_telemetry: RomanSplitTelemetry | None = None

    for block in polish_blocks:
        if references_heading_re.match(block.text):
            references_started = True
        if (
            is_references_block(block, references_started)
            or block.tag in {"table", "td", "th"}
            or re.search(r"<table\b|<t[dh]\b", block.raw, re.IGNORECASE) is not None
        ):
            continue
        split_match = ROMAN_WORD_SPLIT_RE.search(block.text)
        if split_match is None:
            continue
        prefix = split_match.group("prefix").lower()
        if prefix in ROMAN_WORD_SPLIT_FALSE_PREFIXES:
            continue
        suffix = split_match.group("suffix").lower()
        right_text = block.text[split_match.end() : split_match.end() + 12]
        if suffix == "x" and right_text.startswith("-"):
            continue
        if suffix == "v" and re.match(r"\.\s*\d", right_text):
            continue
        raw_prefix = re.escape(split_match.group("prefix"))
        raw_suffix = re.escape(split_match.group("suffix"))
        if re.search(
            rf"\b{raw_prefix}\s*<sub\b[^>]*>\s*{raw_suffix}\s*</sub>",
            block.raw,
            re.IGNORECASE,
        ):
            continue
        if re.search(
            rf"\b{raw_prefix}\s*<sup\b[^>]*>\s*{raw_suffix}\s*</sup>",
            block.raw,
            re.IGNORECASE,
        ):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45S",
                    "Roman-like suffix is already a superscript marker",
                    "A rendered superscript affiliation/footnote marker resembles a split word in visible text.",
                    "EN audit P45 superscript-marker classifier",
                    "Superscript affiliation markers such as Teixeira<sup>i</sup> must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        if re.search(
            rf"\b{raw_prefix}\s*<a\b[^>]*\bz2m-ref-link\b[^>]*>\s*{raw_suffix}\s*</a>",
            block.raw,
            re.IGNORECASE,
        ):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45L",
                    "Roman-like suffix is wrapped by a reference link",
                    "A reference-link boundary makes visible text resemble a split surname; repair belongs to citation/link cleanup.",
                    "EN audit P45 linked-suffix classifier",
                    "Author-year link fragments such as Pisan<a>i</a> must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        if re.search(
            rf"\b{raw_prefix}\s*<span\b[^>]*\bz2m-math\b[^>]*>",
            block.raw,
            re.IGNORECASE,
        ):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45M",
                    "Roman-like suffix is a rendered math variable",
                    "A rendered math variable resembles a split word in visible text.",
                    "EN audit P45 math-variable classifier",
                    "Math spans such as Function <span class='z2m-math'>v</span> must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        if looks_like_affiliation_label_roman_boundary(block, split_match):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45A",
                    "Roman-like suffix is an affiliation label boundary",
                    "Front-matter affiliation labels after countries can resemble a split surname in visible text.",
                    "EN audit P45 affiliation-label classifier",
                    "Affiliation lists such as 'Denmark i National Institute' must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        defects.append(
            make_defect(
                defect_id="P45",
                cc_class="CC-04/CC-13",
                check="Word or surname is split before a roman-like suffix",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=stage,
                hypothesis="Roman-suffix/table-footnote heuristics split ordinary words or surnames ending in i/v/x.",
                proposed_fix_layer="EN polish roman/table-footnote disambiguation",
                regression_test="Surnames such as Belyaev, Yakovlev, and Nedelev remain intact.",
                extra={"match": split_match.group(0)},
            )
        )
        break

    if roman_split_telemetry is not None and not any(defect.id == "P45" for defect in defects):
        defect_id, check, hypothesis, proposed_fix_layer, regression_test, block, split_match = roman_split_telemetry
        defects.append(
            make_defect(
                defect_id=defect_id,
                cc_class="CC-04/CC-13",
                check=check,
                severity="warning",
                block=block,
                snippet=block.text,
                stage=stage,
                hypothesis=hypothesis,
                proposed_fix_layer=proposed_fix_layer,
                regression_test=regression_test,
                extra={"match": split_match.group(0), "quality_counted": False},
            )
        )

    return defects
