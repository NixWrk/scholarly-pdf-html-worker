"""HTML marking helpers used before text-node translation."""

from __future__ import annotations

import re

from ..html_references import REFERENCES_HEADING_PATTERN

_H1_CLOSE_PATTERN = re.compile(r"</h[1-6]\s*>", re.IGNORECASE)
_H_OPEN_PATTERN = re.compile(r"<h[1-6]\b[^>]*>", re.IGNORECASE)
_LIST_OPEN_PATTERN = re.compile(r"<(ul|ol)\b[^>]*>", re.IGNORECASE)
_FIRST_P_OPEN_PATTERN = re.compile(r"<p(\b[^>]*)>", re.IGNORECASE)
_P_CLOSE_PATTERN = re.compile(r"</p\s*>", re.IGNORECASE)
_ABSTRACT_MARKER_PATTERN = re.compile(r"\bAbstract\b", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_AUTHOR_LINE_NEGATIVE_PATTERN = re.compile(
    r"\b("
    r"abstract|received|accepted|published|doi|keywords?|"
    r"data availability|code availability|conflict of interest|competing interests?|"
    r"funding|acknowledg(?:e)?ments?|supplementary|references|bibliography|"
    r"cite this article|correspondence"
    r")\b",
    re.IGNORECASE,
)
_AUTHOR_WORD_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Za-z]+)?\b")


def _visible_text_fragment(html_fragment: str) -> str:
    text = _HTML_TAG_PATTERN.sub(" ", html_fragment)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&#160;", " ")
        .replace("\u00a0", " ")
    )
    return re.sub(r"\s+", " ", text).strip()


def _looks_author_line_paragraph(text: str) -> bool:
    if not text:
        return False
    normalized = " ".join(text.split())
    if len(normalized) < 8:
        return False
    if ":" in normalized:
        return False
    if _ABSTRACT_MARKER_PATTERN.search(normalized):
        return False
    if _AUTHOR_LINE_NEGATIVE_PATTERN.search(normalized):
        return False
    if len(re.findall(r"\d", normalized)) > 2:
        return False

    comma_count = normalized.count(",")
    name_like_count = len(_AUTHOR_WORD_PATTERN.findall(normalized))
    has_author_connector = bool(
        re.search(r"\b(?:and|&|et al\.?|member|fellow|professor)\b", normalized, re.IGNORECASE)
    )
    return (
        (comma_count >= 2 and name_like_count >= 2)
        or (has_author_connector and comma_count >= 1 and name_like_count >= 2)
    )


def mark_author_line_notranslate(html: str) -> str:
    """Mark only real author-line paragraphs as ``translate="no"``."""
    h1_end = _H1_CLOSE_PATTERN.search(html)
    if h1_end is None:
        return html

    search_pos = h1_end.end()
    first_h_after_h1 = _H_OPEN_PATTERN.search(html, search_pos)
    stop_pos = first_h_after_h1.start() if first_h_after_h1 else len(html)

    while True:
        p_match = _FIRST_P_OPEN_PATTERN.search(html, search_pos)
        if p_match is None or p_match.start() >= stop_pos:
            return html

        p_close = _P_CLOSE_PATTERN.search(html, p_match.end())
        if p_close is None:
            return html

        p_content = html[p_match.end():p_close.start()]
        visible = _visible_text_fragment(p_content)
        if _looks_author_line_paragraph(visible):
            attrs = p_match.group(1) or ""
            if "translate" in attrs.lower():
                return html
            new_tag = f"<p{attrs} translate=\"no\">"
            return html[: p_match.start()] + new_tag + html[p_match.end():]

        search_pos = p_close.end()


def _find_list_end(html: str, list_open: re.Match[str]) -> int | None:
    list_tag = (list_open.group(1) or "").lower()
    if list_tag not in {"ul", "ol"}:
        return None

    list_depth = 1
    list_token_pattern = re.compile(rf"</?{list_tag}\b[^>]*>", re.IGNORECASE)
    for token in list_token_pattern.finditer(html, list_open.end()):
        raw = token.group(0).strip().lower()
        if raw.startswith("</"):
            list_depth -= 1
            if list_depth == 0:
                return token.end()
        elif not raw.endswith("/>"):
            list_depth += 1
    return None


def _containing_p_end_for_list(
    html: str,
    *,
    search_start: int,
    list_start: int,
    minimum_end: int,
) -> int | None:
    p_end: int | None = None
    for p_match in _FIRST_P_OPEN_PATTERN.finditer(html, search_start, list_start):
        p_close = _P_CLOSE_PATTERN.search(html, p_match.end())
        if p_close is not None and p_close.start() > list_start and p_close.end() >= minimum_end:
            p_end = p_close.end()
    return p_end


def _reference_list_group_end(
    html: str,
    *,
    heading_end: int,
    first_list_open: re.Match[str],
) -> int | None:
    list_end = _find_list_end(html, first_list_open)
    if list_end is None:
        return None

    block_end = _containing_p_end_for_list(
        html,
        search_start=heading_end,
        list_start=first_list_open.start(),
        minimum_end=list_end,
    ) or list_end

    while True:
        whitespace = re.match(r"\s*", html[block_end:])
        next_pos = block_end + (whitespace.end() if whitespace else 0)

        p_match = _FIRST_P_OPEN_PATTERN.match(html, next_pos)
        if p_match is not None:
            p_close = _P_CLOSE_PATTERN.search(html, p_match.end())
            if p_close is None:
                return block_end
            p_content = html[p_match.end():p_close.start()]
            if _LIST_OPEN_PATTERN.search(p_content) is None:
                return block_end
            block_end = p_close.end()
            continue

        list_match = _LIST_OPEN_PATTERN.match(html, next_pos)
        if list_match is None:
            return block_end

        next_list_end = _find_list_end(html, list_match)
        if next_list_end is None:
            return block_end
        block_end = next_list_end


def mark_references_block_notranslate(html: str) -> str:
    """Mark bibliography block (references heading + list) as non-translatable."""
    heading_match = REFERENCES_HEADING_PATTERN.search(html)
    if heading_match is None:
        return html

    block_start = heading_match.start()
    next_heading = _H_OPEN_PATTERN.search(html, heading_match.end())
    block_end = next_heading.start() if next_heading else len(html)
    if next_heading is None:
        list_open = _LIST_OPEN_PATTERN.search(html, heading_match.end())
        if list_open is None:
            return html

        fallback_end = _reference_list_group_end(
            html,
            heading_end=heading_match.end(),
            first_list_open=list_open,
        )
        if fallback_end is None:
            return html
        block_end = fallback_end

    if block_end <= block_start:
        return html

    block = html[block_start:block_end]
    if re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bz2m-references-block\b',
        block,
        flags=re.IGNORECASE,
    ):
        return html
    wrapped = (
        '<div class="z2m-references-block" translate="no">'
        f"{block}"
        "</div>"
    )
    return html[:block_start] + wrapped + html[block_end:]
