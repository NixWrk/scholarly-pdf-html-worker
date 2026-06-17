"""P62 missing-figure context extraction helpers."""

from __future__ import annotations

import re
from typing import Any

from zoteropdf2md.quality_loop.converted_runs import visible_html_text
from zoteropdf2md.quality_loop.observations import compact_observation_text
from zoteropdf2md.quality_loop.resolver_decisions import defect_extra


P62_MISSING_WARNING_TEXT_RE = re.compile(
    r"\bFigure\s+(?P<label>[\w.-]+)\s+image\s+was\s+not\s+extracted\b",
    re.IGNORECASE,
)


def clean_context_fragment(fragment: str, *, max_len: int = 1400) -> str:
    fragment = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", fragment)
    fragment = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", fragment)
    fragment = re.sub(r"(?is)<img\b[^>]*>", " [image] ", fragment)
    text = visible_html_text(fragment)
    text = re.sub(r"[A-Za-z0-9+/]{120,}={0,2}", " ", text)
    text = re.sub(
        r"\bFigure\s+[\w.-]+\s+image\s+was\s+not\s+extracted\s+into\s+this\s+HTML\.\s+"
        r"Please\s+check\s+the\s+original\s+PDF\s+for\s+the\s+missing\s+visual\s+content\.?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = P62_MISSING_WARNING_TEXT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return compact_observation_text(text, max_len=max_len)


def context_fragment(html: str, position: int, *, radius: int) -> str:
    div_start = html.rfind("<div", 0, position)
    div_end = html.find("</div>", position)
    if div_start >= 0 and div_end >= 0 and div_end - position <= max(radius * 2, 20000):
        candidate = html[div_start : div_end + len("</div>")]
        if "z2m-missing" in candidate[: min(len(candidate), position - div_start + 2000)].casefold():
            if clean_context_fragment(candidate):
                return candidate

    before = min(1400, max(600, radius // 2))
    return html[max(0, position - before) : min(len(html), position + radius)]


def warning_context_from_html(
    html: str,
    defect: dict[str, Any],
    *,
    radius: int,
) -> tuple[str, str]:
    if not html:
        return "", "html_unavailable"
    extra = defect_extra(defect)
    figure_label = str(extra.get("figure_label") or "").strip()
    warning_index = int(extra.get("warning_index") or 0)
    label_key = figure_label.casefold()

    regex_matches: list[tuple[int, str]] = []
    for match in P62_MISSING_WARNING_TEXT_RE.finditer(html):
        match_label = str(match.group("label") or "").casefold()
        if label_key and match_label != label_key:
            continue
        regex_matches.append((match.start(), "warning_text_regex"))
    if regex_matches:
        if warning_index > 0 and warning_index <= len(regex_matches):
            position, source = regex_matches[warning_index - 1]
        else:
            position, source = regex_matches[0]
        fragment = context_fragment(html, position, radius=radius)
        return clean_context_fragment(fragment), source

    snippet = str(defect.get("snippet") or "").strip()
    needles = [snippet]
    if figure_label:
        needles.append(f"Figure {figure_label} image was not extracted")
    html_lower = html.casefold()
    for needle in needles:
        if not needle:
            continue
        position = html.find(needle)
        if position < 0:
            position = html_lower.find(needle.casefold())
        if position >= 0:
            fragment = context_fragment(html, position, radius=radius)
            return clean_context_fragment(fragment), "snippet_match"

    missing_blocks = re.finditer(
        r"(?is)<(?P<tag>[a-z0-9]+)\b[^>]*\bz2m-missing[^>]*>.*?</(?P=tag)>",
        html,
    )
    for match in missing_blocks:
        visible = visible_html_text(match.group(0))
        if figure_label and f"figure {figure_label}" not in visible.casefold():
            continue
        position = match.start()
        fragment = context_fragment(html, position, radius=radius)
        return clean_context_fragment(fragment), "missing_block_match"

    return "", "warning_not_found"


def recovery_snippets(
    html: str,
    defect: dict[str, Any],
    *,
    context_chars: int,
) -> tuple[list[str], str, str]:
    context, context_source = warning_context_from_html(
        html,
        defect,
        radius=max(800, context_chars),
    )
    snippets: list[str] = []
    if context:
        snippets.append(context)
    snippet = compact_observation_text(defect.get("snippet"), max_len=400)
    if snippet and not context:
        snippets.append(snippet)
    extra = defect_extra(defect)
    figure_label = str(extra.get("figure_label") or "").strip()
    if figure_label and context:
        snippets.append(f"Fig. {figure_label}")
    return snippets, context, context_source
