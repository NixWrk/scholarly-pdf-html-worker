"""Float-unit caption and table-note detection helpers."""

from __future__ import annotations

import re

from ..semantic_labels import (
    figure_key_from_visible_number,
    normalize_table_key,
    supplementary_figure_key_from_visible_number,
)
from .html_fragments import visible_text


FIG_KEY_TOKEN = r"\d+(?:[.\-\u2010\u2011\u2012\u2013\u2014]\d+)*"
FIG_COMPOUND_KEY_TOKEN = r"\d+(?:[.\-\u2010\u2011\u2012\u2013\u2014]\d+)+"
FIG_RELAXED_KEY_TOKEN = (
    r"\d+(?:\s*[.\-\u2010\u2011\u2012\u2013\u2014]\s*\d+"
    r"(?!\s*[A-Za-z])"
    r"(?!\s*[.\-\u2010\u2011\u2012\u2013\u2014]\s*\d+[A-Za-z]))*"
    r"(?!\d)"
)
FIG_PANEL_SUFFIX_TOKEN = r"[a-z]"
FIG_CAPTION_PANEL_SUFFIX_TOKEN = rf"(?:{FIG_PANEL_SUFFIX_TOKEN}|\s+[A-Za-z](?=\s|[).:|,\-\u2010-\u2014]))"
FIG_REF_LABEL_TOKEN = (
    r"(?:Figs?|Figures?|FIGS?|FIGURES?"
    r"|\u0420\u0438\u0441(?:\u0443\u043d\u043e\u043a)?|\u0440\u0438\u0441(?:\u0443\u043d\u043e\u043a)?"
    r"|\u0424\u0438\u0433(?:\u0443\u0440\u0430)?|\u0444\u0438\u0433(?:\u0443\u0440\u0430)?)"
)
SUPPLEMENTARY_FIG_PREFIX_TOKEN = r"(?:Supplementary|Supplemental|Suppl\.?)"
SUPPLEMENTARY_FIG_KEY_TOKEN = rf"(?:S\s*)?{FIG_KEY_TOKEN}"
SUPPLEMENTARY_FIG_RELAXED_KEY_TOKEN = rf"(?:S\s*)?{FIG_RELAXED_KEY_TOKEN}"
TABLE_KEY_TOKEN = r"(?:[A-Z]\d+|[IVXLCM]+|\d+(?:[.\-\u2010\u2011\u2012\u2013\u2014]\d+)*)"
TABLE_REF_WORD_TOKEN = (
    r"(?:TABLES?|Tables?|"
    r"\u0422\u0430\u0431\u043b\u0438\u0446(?:\u0430|\u044b|\u0435|\u0430\u0445|\u0443)?)"
)


def caption_tail_opens_caption(tail: str) -> bool:
    tail = tail.lstrip()
    if not tail:
        return False
    if re.match(
        r"^[\-\u2010\u2011\u2012\u2013\u2014]\s*(?:\d+\s*)?[A-Za-z]\s+"
        r"(?:show|shows|showed|showcase|showcases|depict|depicts|illustrate|illustrates|"
        r"present|presents|represent|represents|plot|plots|display|displays|examine|examines|"
        r"suggest|suggests|indicate|indicates|validate|validates|detail|details|exemplify|exemplifies)\b",
        tail,
        re.IGNORECASE,
    ):
        return False
    if re.match(
        r"^[.:]\s*\d+\s+"
        r"(?:show|shows|showed|showcase|showcases|depict|depicts|illustrate|illustrates|"
        r"present|presents|represent|represents|plot|plots|display|displays|examine|examines|"
        r"suggest|suggests|indicate|indicates|validate|validates|detail|details|exemplify|exemplifies|"
        r"provide|provides|demonstrate|demonstrates|compare|compares|reveal|reveals)\b",
        tail,
        re.IGNORECASE,
    ):
        return False
    if tail[:1] in ".|:-\u2010\u2011\u2012\u2013\u2014":
        return True
    if tail[:1] in "([{":
        if re.match(
            r"^\(\s*(?:left|right|top|bottom|upper|lower|central|center|middle|"
            r"same|both|all|main|inset|side|front|back|first|second|third)"
            r"(?:\s+(?:and|or|/)?\s*(?:left|right|top|bottom|upper|lower|central|center|middle|"
            r"same|both|all|main|inset|side|front|back|first|second|third|panels?|panel|plots?|plot|images?|image))*"
            r"\s*\)\s*"
            r"(?:show|shows|showed|showcase|showcases|depict|depicts|illustrate|illustrates|"
            r"present|presents|represent|represents|plot|plots|display|displays|examine|examines|"
            r"suggest|suggests|indicate|indicates)\b",
            tail,
            re.IGNORECASE,
        ):
            return False
        subfigure_ref = re.match(r"^\([A-Za-z]\)\s*([^\W\d_]+)", tail, re.IGNORECASE)
        if subfigure_ref is not None and subfigure_ref.group(1).lower() in {
            "show",
            "shows",
            "showed",
            "shown",
            "showcase",
            "showcases",
            "showcased",
            "demonstrate",
            "demonstrates",
            "demonstrated",
            "depict",
            "depicts",
            "depicted",
            "illustrate",
            "illustrates",
            "illustrated",
            "present",
            "presents",
            "presented",
            "represent",
            "represents",
            "represented",
            "plot",
            "plots",
            "plotted",
            "visualize",
            "visualizes",
            "visualized",
            "visualise",
            "visualises",
            "visualised",
            "display",
            "displays",
            "displayed",
            "map",
            "maps",
            "mapped",
            "describe",
            "describes",
            "described",
            "is",
            "are",
            "was",
            "were",
            "can",
            "will",
        }:
            return False
        return True
    if re.match(
        r"^(?:and|or|,|&)\s+[A-Za-z]\s+"
        r"(?:show|shows|showed|showcase|showcases|depict|depicts|illustrate|illustrates|"
        r"present|presents|represent|represents|plot|plots|display|displays|examine|examines|"
        r"suggest|suggests|indicate|indicates)\b",
        tail,
        re.IGNORECASE,
    ):
        return False
    if re.match(
        rf"^(?:and|or)\s+(?:Fig(?:ure)?\.?|Figure)\s*{FIG_KEY_TOKEN}(?:\s*\([A-Za-z]\)|[A-Za-z]|\s+[A-Za-z](?=\s))?\s+"
        r"(?:show|shows|showed|showcase|showcases|depict|depicts|illustrate|illustrates|"
        r"present|presents|represent|represents|plot|plots|display|displays|examine|examines|"
        r"suggest|suggests|indicate|indicates|validate|validates|detail|details|exemplify|exemplifies)\b",
        tail,
        re.IGNORECASE,
    ):
        return False
    if tail[:1].isdigit():
        return True
    if tail[:1].isupper():
        return True

    word_match = re.match(r"([^\W\d_]+)", tail, re.IGNORECASE)
    if word_match is None:
        return False
    word = word_match.group(1).lower()
    if len(word) <= 1:
        return False
    prose_verbs = {
        "show",
        "shows",
        "shown",
        "showed",
        "showcase",
        "showcases",
        "showcased",
        "demonstrate",
        "demonstrates",
        "demonstrated",
        "depict",
        "depicts",
        "depicted",
        "illustrate",
        "illustrates",
        "illustrated",
        "present",
        "presents",
        "presented",
        "represent",
        "represents",
        "represented",
        "plot",
        "plots",
        "plotted",
        "visualize",
        "visualizes",
        "visualized",
        "visualise",
        "visualises",
        "visualised",
        "display",
        "displays",
        "displayed",
        "map",
        "maps",
        "mapped",
        "describe",
        "describes",
        "described",
        "examine",
        "examines",
        "examined",
        "suggest",
        "suggests",
        "suggested",
        "summarize",
        "summarizes",
        "summarized",
        "summarise",
        "summarises",
        "summarised",
        "list",
        "lists",
        "listed",
        "compare",
        "compares",
        "compared",
        "report",
        "reports",
        "reported",
        "indicate",
        "indicates",
        "indicated",
        "validate",
        "validates",
        "validated",
        "detail",
        "details",
        "detailed",
        "exemplify",
        "exemplifies",
        "exemplified",
        "provide",
        "provides",
        "provided",
        "contain",
        "contains",
        "contained",
        "reveal",
        "reveals",
        "revealed",
        "highlight",
        "highlights",
        "highlighted",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "has",
        "have",
        "had",
        "can",
        "could",
        "will",
        "would",
        "may",
        "might",
        "should",
        "\u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442",
        "\u0434\u0435\u043c\u043e\u043d\u0441\u0442\u0440\u0438\u0440\u0443\u0435\u0442",
        "\u0438\u043b\u043b\u044e\u0441\u0442\u0440\u0438\u0440\u0443\u0435\u0442",
        "\u043f\u0440\u0435\u0434\u0441\u0442\u0430\u0432\u043b\u044f\u0435\u0442",
        "\u0441\u043e\u0434\u0435\u0440\u0436\u0438\u0442",
        "\u0441\u0440\u0430\u0432\u043d\u0438\u0432\u0430\u0435\u0442",
    }
    return word not in prose_verbs


def figure_caption_num_from_visible(visible: str) -> str | None:
    supplementary_match = re.match(
        rf"^\s*{SUPPLEMENTARY_FIG_PREFIX_TOKEN}\s+"
        r"(?:FIG(?:URE)?|Fig(?:ure)?"
        r"|\u0420\u0438\u0441(?:\u0443\u043d\u043e\u043a)?|\u0440\u0438\u0441(?:\u0443\u043d\u043e\u043a)?"
        r"|\u0424\u0438\u0433(?:\u0443\u0440\u0430)?|\u0444\u0438\u0433(?:\u0443\u0440\u0430)?)"
        rf"\.?\s*({SUPPLEMENTARY_FIG_RELAXED_KEY_TOKEN})({FIG_CAPTION_PANEL_SUFFIX_TOKEN})?([\s\S]*)$",
        visible,
        re.IGNORECASE,
    )
    if supplementary_match is not None:
        tail = supplementary_match.group(3)
        if re.match(r"^\s*\(\s*(?:see\s+legend|continued)\b[\s\S]*\)\s*$", tail, re.IGNORECASE):
            return None
        if not caption_tail_opens_caption(tail):
            return None
        return supplementary_figure_key_from_visible_number(supplementary_match.group(1))

    compound_match = re.match(
        r"^\s*(?:FIG(?:URE)?|Fig(?:ure)?"
        r"|\u0420\u0438\u0441(?:\u0443\u043d\u043e\u043a)?|\u0440\u0438\u0441(?:\u0443\u043d\u043e\u043a)?"
        r"|\u0424\u0438\u0433(?:\u0443\u0440\u0430)?|\u0444\u0438\u0433(?:\u0443\u0440\u0430)?)"
        rf"\.?\s*({FIG_COMPOUND_KEY_TOKEN})({FIG_CAPTION_PANEL_SUFFIX_TOKEN})?([\s\S]*)$",
        visible,
        re.IGNORECASE,
    )
    if compound_match is not None:
        tail = compound_match.group(3)
        if re.match(r"^\s*\(\s*(?:see\s+legend|continued)\b[\s\S]*\)\s*$", tail, re.IGNORECASE):
            return None
        if not caption_tail_opens_caption(tail):
            return None
        return figure_key_from_visible_number(compound_match.group(1))

    spaced_decimal_match = re.match(
        r"^\s*(?:FIG(?:URE)?|Fig(?:ure)?"
        r"|\u0420\u0438\u0441(?:\u0443\u043d\u043e\u043a)?|\u0440\u0438\u0441(?:\u0443\u043d\u043e\u043a)?"
        r"|\u0424\u0438\u0433(?:\u0443\u0440\u0430)?|\u0444\u0438\u0433(?:\u0443\u0440\u0430)?)"
        r"\.?\s*(\d+)\s*\.\s*(\d+)([\s\S]*)$",
        visible,
        re.IGNORECASE,
    )
    if spaced_decimal_match is not None:
        tail = spaced_decimal_match.group(3)
        if re.match(r"^\s*\.\s*\d", tail):
            full_tail = f". {spaced_decimal_match.group(2)}{tail}"
            if caption_tail_opens_caption(full_tail):
                return figure_key_from_visible_number(spaced_decimal_match.group(1))
            return None
        if tail and not tail[:1].isspace() and tail[:1] not in ".|:-\u2010\u2011\u2012\u2013\u2014([{":
            full_tail = f". {spaced_decimal_match.group(2)}{tail}"
            if caption_tail_opens_caption(full_tail):
                return figure_key_from_visible_number(spaced_decimal_match.group(1))
            return None
        if re.match(r"^\s*\(\s*(?:see\s+legend|continued)\b[\s\S]*\)\s*$", tail, re.IGNORECASE):
            return None
        if not caption_tail_opens_caption(tail):
            return None
        return figure_key_from_visible_number(
            f"{spaced_decimal_match.group(1)}-{spaced_decimal_match.group(2)}"
        )

    match = re.match(
        r"^\s*(?:FIG(?:URE)?|Fig(?:ure)?"
        r"|\u0420\u0438\u0441(?:\u0443\u043d\u043e\u043a)?|\u0440\u0438\u0441(?:\u0443\u043d\u043e\u043a)?"
        r"|\u0424\u0438\u0433(?:\u0443\u0440\u0430)?|\u0444\u0438\u0433(?:\u0443\u0440\u0430)?)"
        rf"\.?\s*({FIG_RELAXED_KEY_TOKEN})({FIG_CAPTION_PANEL_SUFFIX_TOKEN})?([\s\S]*)$",
        visible,
        re.IGNORECASE,
    )
    if match is None:
        return None
    tail = match.group(3)
    if re.match(r"^\s*\(\s*(?:see\s+legend|continued)\b[\s\S]*\)\s*$", tail, re.IGNORECASE):
        return None
    if not caption_tail_opens_caption(tail):
        return None
    return figure_key_from_visible_number(match.group(1))


def table_caption_key_from_visible(visible: str) -> str | None:
    match = re.match(
        r"^\s*(?:TABLE|Table|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)"
        rf"\.?\s+({TABLE_KEY_TOKEN})([\s\S]*)$",
        visible,
        re.IGNORECASE,
    )
    if match is None:
        return None
    if not caption_tail_opens_caption(match.group(2)):
        return None
    return normalize_table_key(match.group(1))


def embedded_table_caption_key_from_visible(visible: str) -> str | None:
    match = re.search(
        rf"\b(?:TABLE|Table|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s+({TABLE_KEY_TOKEN})"
        r"(?=\s|[.\-:;]|$)",
        visible[:4000],
        re.IGNORECASE,
    )
    if match is None:
        return None
    return normalize_table_key(match.group(1))


def raw_has_class(raw: str, class_name: str) -> bool:
    class_match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', raw, re.IGNORECASE | re.DOTALL)
    if class_match is None:
        return False
    return class_name in class_match.group(2).split()


def looks_table_note_text(visible: str) -> bool:
    text = visible.strip()
    if not text:
        return False
    lower = text.lower()
    if re.match(r"^(?:notes?|table\s+notes?)\b", lower):
        return True
    if lower.startswith(("\ufffd", "пїЅ")):
        return True
    if lower.startswith(("*", "\u2020", "\u2021")):
        return True
    if re.match(r"^\?\s*:\s*statistically\s+significant\b", lower):
        return True
    if re.match(r"^(?:(?:median\s+value|values?\s+represent)\b|positive\s+value\s*=)", lower):
        return True
    if re.match("^(?:delta|\u03b4)\\s*pvr\\b", lower):
        return True
    if re.match(r"^abbreviations?\b", lower):
        return True
    if re.match(r"^[A-Z][A-Za-z0-9 /\-]{0,35}:\s+", text) and re.search(
        r"\b(?:score|index|rate|volume|stage|specific|residual|quality|robot|uroflow|prostate|symptom)\b",
        lower,
    ):
        return True
    if ":" in text and re.search(r"\b(?:odds ratio|confidence interval|perioperative change)\b", lower):
        return True
    if re.match(r"^https?://doi\.org/10\.\d{4,9}/\S+\.t\d+\b", lower):
        return True
    if lower.startswith("this list includes") or "not exhaustive" in lower:
        return True
    if re.match(r"^\\[\(\[]", text) and re.search(
        r"\b(?:is|are)\s+(?:the\s+)?(?:function|value|parameter|term)\b|\bdescribes?\b",
        lower,
    ):
        return True
    if re.match(
        r"^[a-z]\s*(?:body\s+mass\s+index|tumor\s+in\s+situ|triple-negative\s+breast\s+cancer|"
        r"sentinel\s+lymph\s+node\s+biopsy|axillary\s+lymph\s+node\s+dissection|"
        r"indocyanine\s+green|methylene\s+blue|radioisotope|positivity\s+was\s+defined|"
        r"significant,\s*p\s*(?:<|&lt;|\u2264|<=)\s*0\.05)\b",
        lower,
    ):
        return True
    return False


def is_table_note_node(raw: str) -> bool:
    if not raw.lstrip().lower().startswith("<p"):
        return False
    if raw_has_class(raw, "z2m-table-note"):
        return True
    visible = visible_text(raw)
    if len(visible) > 800:
        return False
    if re.match(
        r"^\s*<p\b[^>]*>\s*(?:<span\b[^>]*\bid\s*=\s*[\"']page-[^\"']+[\"'][^>]*>\s*</span>\s*)*"
        r"<sup\b[^>]*>\s*[a-z]\s*</sup>\s*[A-Z]",
        raw,
        re.IGNORECASE,
    ):
        return True
    return looks_table_note_text(visible)


def is_figure_caption_node(raw: str) -> bool:
    low = raw.lstrip().lower()
    if not (low.startswith("<p") or re.match(r"<h[1-6]\b", low)):
        return False
    return figure_caption_num_from_visible(visible_text(raw)) is not None


def is_table_caption_node(raw: str) -> bool:
    low = raw.lstrip().lower()
    if not (low.startswith("<p") or re.match(r"<h[1-6]\b", low)):
        return False
    return table_caption_key_from_visible(visible_text(raw)) is not None


def is_caption_node(raw: str) -> bool:
    return is_figure_caption_node(raw) or is_table_caption_node(raw)
