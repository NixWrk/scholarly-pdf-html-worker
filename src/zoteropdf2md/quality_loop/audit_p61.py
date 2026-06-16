from __future__ import annotations

from collections.abc import Callable, Iterable
import re

from zoteropdf2md.quality_loop.audit_blocks import Block, Defect, attrs as parse_attrs, strip_tags
from zoteropdf2md.quality_loop.audit_diagnostics import make_defect
from zoteropdf2md.semantic_labels import (
    extended_data_figure_key_from_visible_number,
    figure_key_from_visible_number,
)


VISIBLE_FIGURE_REF_RE = re.compile(
    r"\b(?P<ext>Extended\s+Data\s+)?"
    r"\b(?P<supp>(?:Supplementary|Supplemental|Suppl\.?)\s+)?"
    r"(?:Fig\.?|Figure)\s+"
    r"(?P<num>(?:S\s*)?\d{1,3}"
    r"(?:\s*(?:[\-\u2010-\u2014]\s*\d{1,3}|\.\s*(?:\d{1,2}(?!\d)|\d{3}(?!\s+[A-Za-z]))))*)"
    r"(?P<letter>[A-Z])?\b",
    re.IGNORECASE,
)
AUTHOR_YEAR_FIGURE_PREFIX_RE = re.compile(
    r"(?:^|[\(\[\{~;]\s*)"
    r"(?:[A-Z][A-Za-z'`\-]+(?:\s+et\s+al\.)?|[A-Z][A-Za-z'`\-]+\s+(?:and|&)\s+[A-Z][A-Za-z'`\-]+)"
    r"\s*,?\s*(?:19|20)\d{2}[a-z]?\s*,?\s*$",
    re.IGNORECASE,
)
AUTHOR_YEAR_CITATION_RE = re.compile(
    r"\b[A-Z][A-Za-z'`\-]+(?:\s+et\s+al\.)?\s*,?\s*(?:19|20)\d{2}[a-z]?\b",
    re.IGNORECASE,
)
RIGHT_AUTHOR_YEAR_FIGURE_CONTEXT_RE = re.compile(
    r"^\s*(?:[,;:]\s*)?"
    r"(?:(?:subject|panel|image|plot|curve|data|model|table)\s+\d{1,3}\s+)?"
    r"(?:of\s+|from\s+|in\s+)?"
    r"[A-Z][A-Za-z'`\-]+(?:\s+et\s+al\.)?"
    r"(?:,?\s*\((?:19|20)\d{2}[a-z]?\)|,?\s+(?:19|20)\d{2}[a-z]?)",
    re.IGNORECASE,
)
EXTERNAL_COPYRIGHT_FIGURE_CONTEXT_RE = re.compile(
    r"\b(?:copyright\s+constraints?|copyright|cannot\s+replicate|not\s+replicated|"
    r"not\s+reproduced|permission|adapted\s+from|reprinted\s+from)\b",
    re.IGNORECASE,
)
HTML_CONTAINER_RE = re.compile(
    r"<(?P<tag>div|figure)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
CAPTION_BLOCK_RE = re.compile(
    r"<(?P<tag>p|figcaption|div|h[1-6])\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)


def figure_key_from_visible_match(match: re.Match[str]) -> str:
    key = figure_key_from_visible_number(match.group("num"))
    if match.group("ext"):
        return extended_data_figure_key_from_visible_number(match.group("num"))
    if match.group("supp"):
        return f"supplementary-{key}"
    return key


def is_external_supplementary_figure_ref(match: re.Match[str]) -> bool:
    key = figure_key_from_visible_number(match.group("num"))
    return bool(match.group("supp")) or key.startswith("s")


def is_compound_chapter_style_figure_ref(match: re.Match[str]) -> bool:
    number = match.group("num")
    return re.search(r"(?:[\-\u2010-\u2014]|\.\s*\d)", number) is not None


def figure_target_keys(html: str) -> set[str]:
    keys = {
        key.lower()
        for key in re.findall(r"\bid\s*=\s*['\"]fig-([A-Za-z0-9-]+)['\"]", html, re.IGNORECASE)
    }
    for unit_match in HTML_CONTAINER_RE.finditer(html):
        unit_attrs = parse_attrs(unit_match.group("attrs"))
        unit_id = unit_attrs.get("id", "")
        unit_classes = set(unit_attrs.get("class", "").split())
        if not unit_id.lower().startswith("fig-") or "z2m-figure-unit" not in unit_classes:
            continue
        for caption_match in CAPTION_BLOCK_RE.finditer(unit_match.group("body")):
            caption_attrs = parse_attrs(caption_match.group("attrs"))
            if "z2m-figure-caption" not in set(caption_attrs.get("class", "").split()):
                continue
            caption_text = strip_tags(caption_match.group("body"))
            visible_match = VISIBLE_FIGURE_REF_RE.search(caption_text)
            if visible_match is not None and visible_match.start() <= 40:
                keys.add(figure_key_from_visible_match(visible_match).lower())
                break
    return keys


def figure_target_numbers(html: str) -> set[int]:
    return {int(key) for key in figure_target_keys(html) if key.isdigit()}


def has_nearby_fig_link(block: Block, figure_key: str, text_pos: int) -> bool:
    raw_text = strip_tags(block.raw)
    if text_pos >= len(raw_text):
        raw_window = block.raw
    else:
        raw_window = block.raw[max(0, text_pos - 180) : text_pos + 220]
    return re.search(rf"href\s*=\s*['\"]#fig-{re.escape(figure_key)}['\"]", raw_window, re.IGNORECASE) is not None


def is_external_author_year_figure_ref(block: Block, match: re.Match[str]) -> bool:
    left = block.text[max(0, match.start() - 120) : match.start()]
    if AUTHOR_YEAR_FIGURE_PREFIX_RE.search(left):
        return True

    right = block.text[match.end() : min(len(block.text), match.end() + 220)]
    if RIGHT_AUTHOR_YEAR_FIGURE_CONTEXT_RE.search(right):
        return True
    if EXTERNAL_COPYRIGHT_FIGURE_CONTEXT_RE.search(right):
        return True

    opener = max(left.rfind("("), left.rfind("["), left.rfind("{"), left.rfind("~"))
    if opener < 0 or len(left) - opener > 120:
        return False
    right = block.text[match.end() : min(len(block.text), match.end() + 140)]
    closer_candidates = [pos for pos in (right.find(")"), right.find("]"), right.find("}"), right.find("!")) if pos >= 0]
    if not closer_candidates:
        return False
    citation_clause = left[opener:] + match.group(0) + right[: min(closer_candidates) + 1]
    if not AUTHOR_YEAR_CITATION_RE.search(citation_clause):
        return False
    return re.search(r"\b(?:Fig\.?|Figure)\s+\d", citation_clause, re.IGNORECASE) is not None


def visible_figure_target_defects(
    body_blocks: Iterable[Block],
    fig_targets: set[str],
    *,
    looks_like_float_or_caption: Callable[[Block], bool],
    stage: str,
) -> list[Defect]:
    for block in body_blocks:
        if looks_like_float_or_caption(block):
            continue
        for match in VISIBLE_FIGURE_REF_RE.finditer(block.text):
            figure_key = figure_key_from_visible_match(match)
            if is_external_supplementary_figure_ref(match):
                continue
            if is_external_author_year_figure_ref(block, match):
                continue
            if figure_key in fig_targets:
                continue
            if is_compound_chapter_style_figure_ref(match):
                continue
            if has_nearby_fig_link(block, figure_key, match.start()):
                continue
            return [
                make_defect(
                    defect_id="P61",
                    cc_class="CC-03/CC-08/CC-10",
                    check="Visible figure reference has no matching semantic figure target",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=stage,
                    hypothesis="Figure extraction/wrapping did not create targets for all visible figure references.",
                    proposed_fix_layer="EN polish figure target completeness audit",
                    regression_test=(
                        "References such as Figure 3D, Figure 4A, and Figure 4 report missing targets "
                        "when no fig-3/fig-4 wrapper exists."
                    ),
                    extra={
                        "figure": figure_key,
                        "figure_key": figure_key,
                        "visible_label": match.group(0),
                        "quality_counted": False,
                    },
                )
            ]
    return []
