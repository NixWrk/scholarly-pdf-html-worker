from __future__ import annotations

import html as html_lib
import re

from ..html_links import escape_html_attr_literal, replace_href_attr_literal
from ..url_repair import (
    compact_visible_url_fragment,
    repair_broken_visible_url_text,
    split_url_and_trailing_punct,
    strip_wrapping_url_quotes,
    url_fragment_compare_key,
)
from .html_fragments import TAG_SPLIT_PATTERN
from .pre_cleanup import update_skip_stack


BROKEN_URL_ANCHOR_LABEL_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>(?:https?://|www\.)[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[^<]{0,500})</a>',
    re.IGNORECASE | re.DOTALL,
)
TRAILING_PROSE_URL_PATTERN = re.compile(
    r"(?P<url>https?://\S+?)(?P<trail>\)\s+(?:applies|is|are|to|for)\b[\s\S]*)$",
    re.IGNORECASE,
)


def _escape_html_text(value: str) -> str:
    return html_lib.escape(value, quote=False)


def split_trailing_prose_url(value: str) -> tuple[str, str] | None:
    match = TRAILING_PROSE_URL_PATTERN.match(value.strip())
    if match is None:
        return None
    url = match.group("url")
    if not re.search(r"\.[A-Za-z]{2,}(?:[/:?#]|$)", url, re.IGNORECASE):
        return None
    return url, match.group("trail")


def repair_broken_plain_url_text(html: str) -> str:
    """Join OCR spaces inside visible plain URLs before autolinking."""
    parts = TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(repair_broken_visible_url_text(part))

    return "".join(out)


def repair_broken_url_anchor_labels(html: str) -> str:
    """Normalize visible URL labels when the href already carries the intact URL."""
    lower_html = html.lower()
    if "http" not in lower_html and "www." not in lower_html:
        return html

    def replace(match: re.Match[str]) -> str:
        href = strip_wrapping_url_quotes(match.group("href"))
        body = match.group("body")
        repaired = repair_broken_visible_url_text(body)
        href_repaired = repair_broken_visible_url_text(href)
        href_split = split_trailing_prose_url(href_repaired)
        body_split = split_trailing_prose_url(repaired)
        if href_split is not None or body_split is not None:
            split_url, split_tail = body_split or href_split  # type: ignore[misc]
            if url_fragment_compare_key(split_url) == url_fragment_compare_key((href_split or body_split)[0]):  # type: ignore[index]
                attrs = re.sub(
                    r'(\bhref\s*=\s*)(["\'])(.*?)\2',
                    lambda m: f'{m.group(1)}"{escape_html_attr_literal(split_url)}"',
                    match.group("attrs"),
                    count=1,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                return f'<a{attrs}>{_escape_html_text(split_url)}</a>{_escape_html_text(split_tail)}'
        repaired_key = url_fragment_compare_key(repaired)
        href_key = url_fragment_compare_key(href)
        compact_repaired = compact_visible_url_fragment(html_lib.unescape(repaired)).rstrip("/")
        compact_href = compact_visible_url_fragment(html_lib.unescape(href)).rstrip("/")
        if compact_href and compact_repaired.lower() in {
            f"{compact_href}{compact_href}".lower(),
            f"{compact_href}/{compact_href}".lower(),
        }:
            attrs = replace_href_attr_literal(match.group("attrs"), html_lib.unescape(href))
            return f'<a{attrs}>{_escape_html_text(html_lib.unescape(href))}</a>'
        if repaired_key != href_key:
            href_repaired_url, href_repaired_trailing = split_url_and_trailing_punct(href_repaired.strip())
            if (
                href_repaired != href
                and not href_repaired_trailing
                and url_fragment_compare_key(href_repaired_url) == repaired_key
            ):
                attrs = replace_href_attr_literal(match.group("attrs"), href_repaired_url)
                return f'<a{attrs}>{_escape_html_text(href_repaired_url)}</a>'
            if repaired == body or not re.search(r"(?:https?://|www\.)", body, re.IGNORECASE):
                return match.group(0)
            return f'<a{match.group("attrs")}>{_escape_html_text(repaired)}</a>'
        visible_url, trailing = split_url_and_trailing_punct(repaired.strip())
        if trailing and url_fragment_compare_key(visible_url) == href_key:
            return f'<a{match.group("attrs")}>{_escape_html_text(href)}</a>{_escape_html_text(trailing)}'
        if repaired == body and not re.match(r"\s*https?://", body, re.IGNORECASE):
            return match.group(0)
        return f'<a{match.group("attrs")}>{_escape_html_text(href)}</a>'

    return BROKEN_URL_ANCHOR_LABEL_PATTERN.sub(replace, html)


__all__ = [
    "BROKEN_URL_ANCHOR_LABEL_PATTERN",
    "TRAILING_PROSE_URL_PATTERN",
    "repair_broken_plain_url_text",
    "repair_broken_url_anchor_labels",
    "split_trailing_prose_url",
]
