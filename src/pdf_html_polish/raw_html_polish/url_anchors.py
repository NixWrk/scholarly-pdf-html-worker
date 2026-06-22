from __future__ import annotations

import html as html_lib
import re

from ..url_repair import (
    BROKEN_PLAIN_URL_PROTOCOL_PATTERN,
    compact_visible_url_fragment,
    repair_broken_visible_url_text,
    split_url_and_trailing_punct,
    starts_like_visible_url_fragment,
    strip_wrapping_url_quotes,
    url_fragment_compare_key,
    url_fragment_keys_match_allowing_lost_hyphens,
)
from ..html_links import escape_html_attr_literal, replace_href_attr_literal
from .html_fragments import visible_text


SPACED_PROTOCOL_HREF_ATTR_PATTERN = re.compile(
    r'(?P<prefix>\bhref\s*=\s*)(?P<quote>["\'])(?P<scheme>https?:)\s+//(?P<rest>[^"\']+)(?P=quote)',
    re.IGNORECASE,
)
SPACED_PROTOCOL_URL_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']https?:\s+//[^"\']+["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
URL_ANCHOR_TEXT_PATTERN = re.compile(
    r'(?P<open><a\b[^>]*\bhref\s*=\s*(["\'])https?://[^"\']+\2[^>]*>)'
    r'(?P<body>[^<]{1,800})'
    r'(?P<close></a>)',
    re.IGNORECASE | re.DOTALL,
)
SPLIT_VISIBLE_URL_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[\s\S]{0,500}?)</a>(?P<tail>\s*[^<]{1,300})',
    re.IGNORECASE,
)
SPLIT_URL_ANCHOR_BLOCK_TAIL_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']*[-_])(?P=quote)[^>]*)>'
    r'(?P<body>https?://[\s\S]{0,500}?[-_])</a>'
    r'(?:\s*</p>\s*<p(?:\s+[^>]*)?>|\s+)\s*'
    r'(?P<tail>[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]{1,300})',
    re.IGNORECASE,
)
SPLIT_URL_ANCHOR_DOMAIN_TAIL_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[^<]{1,260})</a>'
    r'(?P<tail>\s*\.\s*[A-Za-z]{2,}'
    r'(?:/[A-Za-z0-9._~:#?\[\]@!$&\'()*+,;=%-]+)*'
    r'(?:/\s+[A-Za-z0-9][A-Za-z0-9._~:#?\[\]@!$&\'()*+,;=%-]+)?)'
    r'(?P<trailing>[.,;:)]?)',
    re.IGNORECASE | re.DOTALL,
)
PROSE_PREFIXED_URL_ANCHOR_TAIL_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[^<]{1,900}?https?://[^<\s]{4,260})\s*</a>'
    r'(?P<tail>\s+[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]{}@!$&\'()*+,;=%-]{1,320})'
    r'(?P<trailing>[.,;:)]?)',
    re.IGNORECASE | re.DOTALL,
)


def _escape_html_text(value: str) -> str:
    return html_lib.escape(value, quote=False)


def unescape_html_entities_repeated(value: str) -> str:
    current = value
    for _ in range(4):
        unescaped = html_lib.unescape(current)
        if unescaped == current:
            return current
        current = unescaped
    return current


def repair_spaced_protocol_url_anchors(html: str) -> str:
    """Join OCR spaces in URL anchor href protocols such as ``http: //``."""
    if "http" not in html.lower():
        return html

    def fix_href(attrs: str) -> tuple[str, str | None]:
        fixed_href: str | None = None

        def replace_attr(match: re.Match[str]) -> str:
            nonlocal fixed_href
            fixed_href = f"{match.group('scheme')}//{match.group('rest')}"
            return f"{match.group('prefix')}{match.group('quote')}{fixed_href}{match.group('quote')}"

        return SPACED_PROTOCOL_HREF_ATTR_PATTERN.sub(replace_attr, attrs, count=1), fixed_href

    def replace_anchor(match: re.Match[str]) -> str:
        attrs, fixed_href = fix_href(match.group("attrs"))
        body = match.group("body")
        if fixed_href and "<" not in body:
            fixed_body = BROKEN_PLAIN_URL_PROTOCOL_PATTERN.sub(r"\1", body)
            if compact_visible_url_fragment(fixed_body).lower() == compact_visible_url_fragment(fixed_href).lower():
                body = _escape_html_text(fixed_href)
        return f"<a{attrs}>{body}</a>"

    return SPACED_PROTOCOL_URL_ANCHOR_PATTERN.sub(replace_anchor, html)


def normalize_double_escaped_url_anchor_text(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        if "&amp;amp;" not in body:
            return match.group(0)
        visible = html_lib.unescape(body)
        if not starts_like_visible_url_fragment(visible):
            return match.group(0)
        return f'{match.group("open")}{body.replace("&amp;amp;", "&amp;")}{match.group("close")}'

    return URL_ANCHOR_TEXT_PATTERN.sub(replace, html)


def consume_compact_prefix(text: str, compact_prefix: str) -> tuple[str, str] | None:
    if not compact_prefix:
        return "", text

    index = 0
    for pos, char in enumerate(text):
        if char.isspace():
            continue
        if index >= len(compact_prefix) or char != compact_prefix[index]:
            return None
        index += 1
        if index == len(compact_prefix):
            return text[: pos + 1], text[pos + 1 :]
    return None


def repair_split_visible_url_anchors(html: str) -> str:
    """Keep a URL anchor's visible text intact when OCR split the URL after the link."""

    def replace(match: re.Match[str]) -> str:
        href = match.group("href")
        body_text = visible_text(match.group("body"))
        if not body_text:
            return match.group(0)

        lead = ""
        url_text = body_text
        lead_match = re.match(r"(?P<lead>(?:online|available|found)\s+at:\s*)(?P<url>https?://[\s\S]+)$", body_text, re.IGNORECASE)
        if lead_match is not None:
            lead = lead_match.group("lead")
            url_text = lead_match.group("url")

        href_compact = compact_visible_url_fragment(href)
        body_compact = compact_visible_url_fragment(url_text)
        href_key = url_fragment_compare_key(href)
        body_key = url_fragment_compare_key(url_text)
        if not (href_compact.startswith(body_compact) or href_key.startswith(body_key)):
            return match.group(0)

        needed_tail = (
            href_compact[len(body_compact) :]
            if href_compact.startswith(body_compact)
            else href_key[len(body_key) :]
        )
        if not needed_tail:
            return match.group(0)
        consumed = consume_compact_prefix(match.group("tail"), needed_tail)
        if consumed is None:
            return match.group(0)

        _, tail_rest = consumed
        attrs = match.group("attrs")
        return f'{lead}<a{attrs}>{href}</a>{tail_rest}'

    return SPLIT_VISIBLE_URL_ANCHOR_PATTERN.sub(replace, html)


def repair_split_url_anchor_block_tail(html: str) -> str:
    """Join a URL anchor split at a paragraph boundary."""

    def replace(match: re.Match[str]) -> str:
        href = strip_wrapping_url_quotes(match.group("href"))
        body = visible_text(match.group("body"))
        if compact_visible_url_fragment(href) != compact_visible_url_fragment(body):
            return match.group(0)

        merged_url, trailing = split_url_and_trailing_punct(f"{href}{match.group('tail')}")
        if not re.search(r"\.[A-Za-z]{2,}(?:[/:?#]|$)", merged_url, re.IGNORECASE):
            return match.group(0)

        attrs = re.sub(
            r'(\bhref\s*=\s*)(["\'])(.*?)\2',
            lambda m: f'{m.group(1)}"{escape_html_attr_literal(merged_url)}"',
            match.group("attrs"),
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return f'<a{attrs}>{_escape_html_text(merged_url)}</a>{trailing}'

    return SPLIT_URL_ANCHOR_BLOCK_TAIL_PATTERN.sub(replace, html)


def repair_split_url_anchor_domain_tail(html: str) -> str:
    """Join a partial URL anchor with its visible ``.com/...`` tail."""

    def replace(match: re.Match[str]) -> str:
        href = unescape_html_entities_repeated(strip_wrapping_url_quotes(match.group("href")))
        body = visible_text(match.group("body")).strip()
        href_key = url_fragment_compare_key(href)
        body_key = url_fragment_compare_key(body)
        if not body_key or not (href_key == body_key or href_key.startswith(body_key)):
            return match.group(0)
        if not re.search(r"\b(?:https?://|www\.)", body, re.IGNORECASE):
            return match.group(0)

        candidate = repair_broken_visible_url_text(f"{body}{match.group('tail')}")
        candidate = re.sub(r"\s+", "", candidate)
        if not candidate.lower().startswith(("http://", "https://")):
            scheme_match = re.match(r"(?P<scheme>https?://)", href, re.IGNORECASE)
            if scheme_match is None:
                return match.group(0)
            candidate = f"{scheme_match.group('scheme')}{candidate}"
        merged_url, trailing = split_url_and_trailing_punct(candidate + match.group("trailing"))
        if not re.search(r"\.[A-Za-z]{2,}(?:[/:?#]|$)", merged_url, re.IGNORECASE):
            return match.group(0)

        attrs = re.sub(
            r'(\bhref\s*=\s*)(["\'])(.*?)\2',
            lambda m: f'{m.group(1)}"{escape_html_attr_literal(merged_url)}"',
            match.group("attrs"),
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return f'<a{attrs}>{_escape_html_text(merged_url)}</a>{trailing}'

    return SPLIT_URL_ANCHOR_DOMAIN_TAIL_PATTERN.sub(replace, html)


def repair_prose_prefixed_url_anchor_tail(html: str) -> str:
    """Move prose out of URL anchors when only the URL tail continues after them."""

    def replace(match: re.Match[str]) -> str:
        href = unescape_html_entities_repeated(strip_wrapping_url_quotes(match.group("href")))
        href_key = url_fragment_compare_key(href)
        if not href_key:
            return match.group(0)

        body_text = visible_text(match.group("body"))
        url_match = re.search(r"(?P<prefix>[\s\S]*?)(?P<head>https?://\S+)\s*$", body_text, re.IGNORECASE)
        if url_match is None:
            return match.group(0)

        candidate = repair_broken_visible_url_text(f"{url_match.group('head')}{match.group('tail')}")
        candidate_url, candidate_trailing = split_url_and_trailing_punct(candidate + (match.group("trailing") or ""))
        candidate_key = url_fragment_compare_key(candidate_url)
        if not (
            url_fragment_keys_match_allowing_lost_hyphens(candidate_key, href_key)
            or href_key.startswith(candidate_key)
            or candidate_key.startswith(href_key)
        ):
            return match.group(0)

        label = href if url_fragment_keys_match_allowing_lost_hyphens(candidate_key, href_key) else candidate_url
        attrs = replace_href_attr_literal(match.group("attrs"), label)
        prefix = _escape_html_text(url_match.group("prefix"))
        return f'{prefix}<a{attrs}>{_escape_html_text(label)}</a>{candidate_trailing}'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = PROSE_PREFIXED_URL_ANCHOR_TAIL_PATTERN.sub(replace, current)
    return current


__all__ = [
    "PROSE_PREFIXED_URL_ANCHOR_TAIL_PATTERN",
    "SPLIT_VISIBLE_URL_ANCHOR_PATTERN",
    "SPLIT_URL_ANCHOR_BLOCK_TAIL_PATTERN",
    "SPLIT_URL_ANCHOR_DOMAIN_TAIL_PATTERN",
    "SPACED_PROTOCOL_HREF_ATTR_PATTERN",
    "SPACED_PROTOCOL_URL_ANCHOR_PATTERN",
    "URL_ANCHOR_TEXT_PATTERN",
    "consume_compact_prefix",
    "normalize_double_escaped_url_anchor_text",
    "repair_prose_prefixed_url_anchor_tail",
    "repair_split_visible_url_anchors",
    "repair_split_url_anchor_block_tail",
    "repair_split_url_anchor_domain_tail",
    "repair_spaced_protocol_url_anchors",
    "unescape_html_entities_repeated",
]
