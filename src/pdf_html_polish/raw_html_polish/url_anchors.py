from __future__ import annotations

import html as html_lib
import re

from ..url_repair import (
    BROKEN_PLAIN_URL_PROTOCOL_PATTERN,
    compact_visible_url_fragment,
    repair_broken_visible_url_text,
    split_url_and_trailing_punct,
    split_url_fragment_text_prose_tail,
    starts_like_visible_url_fragment,
    strip_url_fragment_edge_quotes,
    strip_wrapping_url_quotes,
    url_fragment_compare_key,
    url_fragment_keys_match_allowing_lost_hyphens,
)
from ..html_links import escape_html_attr_literal, href_attr_literal, replace_href_attr_literal
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
SPLIT_SCHEME_URL_ANCHOR_FRAGMENTS_PATTERN = re.compile(
    r'(?P<scheme>https?://)\s*'
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[^<]{1,260})</a>'
    r'(?P<mid>(?:\s*/\s*[A-Za-z0-9._~:/?#\[\]@!$&\'*+,;=%-]*){0,8}\s*)'
    r'(?:<a\b(?P<next_attrs>[^>]*\bhref\s*=\s*(?P<next_quote>["\'])(?P<next_href>https?://[^"\']+)'
    r'(?P=next_quote)[^>]*)>(?P<next_body>[^<]{1,260})</a>'
    r'(?P<after>(?:\s*/\s*[A-Za-z0-9._~:/?#\[\]@!$&\'*+,;=%-]*){0,8}\s*))?',
    re.IGNORECASE | re.DOTALL,
)
SPLIT_SCHEME_URL_ANCHOR_HEAD_PATTERN = re.compile(
    r'(?P<scheme>https?://)\s*'
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[^<]{1,260})</a>',
    re.IGNORECASE | re.DOTALL,
)
URL_FRAGMENT_TEXT_CHUNK_PATTERN = re.compile(
    r'\s*(?P<text>[/#?&=._~:;,%A-Za-z0-9!$\'()*+\[\]{}-]+(?:\s+[/#?&=._~:;,%A-Za-z0-9!$\'()*+\[\]{}-]+){0,4})',
    re.IGNORECASE,
)
URL_FRAGMENT_ANCHOR_CHUNK_PATTERN = re.compile(
    r'\s*<a\b(?P<attrs>[^>]*\bhref\s*=\s*(["\'])(?P<href>https?://[^"\']+)\2[^>]*)>'
    r'(?P<body>[^<]{1,260})</a>',
    re.IGNORECASE | re.DOTALL,
)
SPLIT_SAME_HREF_DOI_ANCHOR_TEXT_PATTERN = re.compile(
    r'<a\b(?P<attrs>(?=[^>]*\bhref\s*=\s*["\']"?https?://(?:dx\.)?doi\.org/)[^>]*)>'
    r'(?P<body>(?:(?!</a>)[\s\S]){0,260}?)</a>'
    r'(?P<mid>\s*[A-Za-z0-9][A-Za-z0-9._-]{0,24}\s*)'
    r'<a\b(?P<next_attrs>(?=[^>]*\bhref\s*=\s*["\']"?https?://(?:dx\.)?doi\.org/)[^>]*)>'
    r'(?P<next_body>(?:(?!</a>)[\s\S]){0,260}?)</a>',
    re.IGNORECASE,
)
SPLIT_DOI_HEAD_TAIL_ANCHOR_PATTERN = re.compile(
    r'(?P<prefix>\bdoi\s*:\s*)'
    r'(?P<head>10\.\d{4,9}/)\s*'
    r'<a\b(?P<attrs>(?=[^>]*\bhref\s*=\s*["\']https?://(?:dx\.)?doi\.org/)[^>]*)>'
    r'(?P<body>(?:(?!</a>)[\s\S]){0,260}?)</a>',
    re.IGNORECASE,
)
SPLIT_DOI_URL_ANCHOR_PATH_TAIL_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])'
    r'(?P<href>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]{3,})'
    r'(?P=quote)[^>]*)>'
    r'(?P<body>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]{3,})</a>'
    r'(?P<tail>\s+[A-Za-z][A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]{3,220})'
    r'(?P<trailing>[.,;:)]?)',
    re.IGNORECASE,
)
ADJACENT_SAME_HREF_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>(?=[^>]*\bhref\s*=\s*["\']"?https?://)[^>]*)>'
    r'(?P<body>[\s\S]{0,260}?)</a>\s+'
    r'<a\b(?P<next_attrs>(?=[^>]*\bhref\s*=\s*["\']"?https?://)[^>]*)>'
    r'(?P<next_body>[\s\S]{0,260}?)</a>',
    re.IGNORECASE,
)
ADJACENT_IDENTICAL_HREF_URL_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[\s\S]{0,260}?)</a>\s+'
    r'<a\b(?P<next_attrs>[^>]*\bhref\s*=\s*["\'](?P=href)["\'][^>]*)>'
    r'(?P<next_body>[\s\S]{0,260}?)</a>',
    re.IGNORECASE,
)
IDENTICAL_HREF_PROTOCOL_PREFIX_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'\s*(?P<body>https?:?)\s*</a>\s*//\s*'
    r'<a\b(?P<next_attrs>[^>]*\bhref\s*=\s*["\'](?P=href)["\'][^>]*)>'
    r'(?P<next_body>[\s\S]{0,500}?)</a>',
    re.IGNORECASE,
)
ADJACENT_SAME_MAILTO_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>(?=[^>]*\bhref\s*=\s*["\']mailto:)[^>]*)>'
    r'(?P<body>[\s\S]{0,160}?)</a>\s+'
    r'<a\b(?P<next_attrs>(?=[^>]*\bhref\s*=\s*["\']mailto:)[^>]*)>'
    r'(?P<next_body>[\s\S]{0,160}?)</a>',
    re.IGNORECASE,
)
SPLIT_WWW_DOMAIN_NOISY_HREF_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])http://www(?P=quote)[^>]*)>'
    r'(?P<body>http://www)</a>\s*\.\s*'
    r'<a\b(?P<next_attrs>[^>]*\bhref\s*=\s*(?P<next_quote>["\'])http://[^"\']+(?P=next_quote)[^>]*)>'
    r'(?P<next_body>[\s\S]{1,500}?)</a>',
    re.IGNORECASE,
)
POST_AUTOLINK_SPLIT_URL_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[^<]{1,260})</a>'
    r'(?P<join>\s*\.?\s*)'
    r'<a\b(?P<next_attrs>[^>]*\bhref\s*=\s*(?P<next_quote>["\'])(?P<next_href>https?://[^"\']+)'
    r'(?P=next_quote)[^>]*)>'
    r'(?P<next_body>[^<]{1,500})</a>'
    r'(?P<tail>\s*[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]{0,220})?',
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


def repair_split_scheme_url_anchor_runs(html: str) -> str:
    """Join ``https://`` plus a run of same-href anchors/path fragments."""
    out_parts: list[str] = []
    cursor = 0
    search_pos = 0
    repairs = 0

    while True:
        match = SPLIT_SCHEME_URL_ANCHOR_HEAD_PATTERN.search(html, search_pos)
        if match is None:
            break

        href = html_lib.unescape(strip_wrapping_url_quotes(match.group("href")))
        href_key = url_fragment_compare_key(href)
        if not href_key:
            search_pos = match.end()
            continue

        pos = match.end()
        visible_parts = [f"{match.group('scheme')}{visible_text(match.group('body'))}"]
        best_end: int | None = None
        best_trailing = ""
        consumed_chunks = 0
        while consumed_chunks < 32 and pos < len(html):
            anchor = URL_FRAGMENT_ANCHOR_CHUNK_PATTERN.match(html, pos)
            if anchor is not None:
                anchor_href = unescape_html_entities_repeated(strip_wrapping_url_quotes(anchor.group("href")))
                if url_fragment_compare_key(anchor_href) != href_key:
                    break
                visible_parts.append(visible_text(anchor.group("body")))
                pos = anchor.end()
                consumed_chunks += 1
            else:
                chunk = URL_FRAGMENT_TEXT_CHUNK_PATTERN.match(html, pos)
                if chunk is None:
                    break
                text, consumed_text_len = split_url_fragment_text_prose_tail(chunk.group("text"))
                if not text:
                    break
                stripped = text.lstrip()
                previous_piece = visible_parts[-1].rstrip() if visible_parts else ""
                query_continuation = ("?" in "".join(visible_parts) or "&" in "".join(visible_parts)) and bool(
                    re.match(r"[A-Za-z0-9+%_.=&-]", stripped)
                )
                domain_tail_continuation = previous_piece.endswith(".") and bool(re.match(r"[A-Za-z0-9]", stripped))
                if not (
                    stripped.startswith(("/", "#", "?", "&"))
                    or query_continuation
                    or domain_tail_continuation
                ):
                    break
                visible_parts.append(text)
                pos = chunk.start("text") + consumed_text_len
                consumed_chunks += 1

            candidate = repair_broken_visible_url_text("".join(visible_parts))
            candidate_url, candidate_trailing = split_url_and_trailing_punct(candidate)
            candidate_key = url_fragment_compare_key(candidate_url)
            if url_fragment_keys_match_allowing_lost_hyphens(candidate_key, href_key) or (
                candidate_key.endswith("=") or href_key.endswith("=")
            ) and url_fragment_keys_match_allowing_lost_hyphens(candidate_key.rstrip("="), href_key.rstrip("=")):
                best_end = pos
                best_trailing = candidate_trailing
                break

        if best_end is None:
            search_pos = match.end()
            continue

        out_parts.append(html[cursor:match.start()])
        attrs = replace_href_attr_literal(match.group("attrs"), href)
        out_parts.append(f'<a{attrs}>{_escape_html_text(href)}</a>{best_trailing}')
        cursor = best_end
        search_pos = best_end
        repairs += 1

    if repairs == 0:
        return html
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def repair_split_scheme_url_anchor_fragments(html: str) -> str:
    """Join ``https://`` text with same-href URL anchors split across path fragments."""

    def replace(match: re.Match[str]) -> str:
        href = unescape_html_entities_repeated(strip_wrapping_url_quotes(match.group("href")))
        next_href = match.group("next_href")
        next_body = ""
        if next_href is not None:
            next_href = unescape_html_entities_repeated(strip_wrapping_url_quotes(next_href))
            if url_fragment_compare_key(next_href) != url_fragment_compare_key(href):
                return match.group(0)
            next_body = visible_text(match.group("next_body") or "")

        candidate = (
            f"{match.group('scheme')}{visible_text(match.group('body'))}"
            f"{match.group('mid') or ''}{next_body}{match.group('after') or ''}"
        )
        candidate = repair_broken_visible_url_text(candidate)
        if url_fragment_compare_key(candidate) != url_fragment_compare_key(href):
            return match.group(0)
        consumed_tail = match.group("after") if next_href is not None else match.group("mid")
        suffix = " " if (consumed_tail or "").endswith(" ") else ""
        attrs = replace_href_attr_literal(match.group("attrs"), href)
        return f'<a{attrs}>{_escape_html_text(href)}</a>{suffix}'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = repair_split_scheme_url_anchor_runs(current)
        current = SPLIT_SCHEME_URL_ANCHOR_FRAGMENTS_PATTERN.sub(replace, current)
    return current


def _doi_core_from_href(href: str) -> str | None:
    href = strip_wrapping_url_quotes(href)
    match = re.match(r"https?://(?:dx\.)?doi\.org/(?P<doi>10\..+)$", href, re.IGNORECASE)
    return match.group("doi") if match is not None else None


def _doi_label_core(label: str) -> str:
    compact = strip_url_fragment_edge_quotes(compact_visible_url_fragment(label)).strip("()[]")
    compact = re.sub(r"^(?:doi:|digitalobjectidentifier)", "", compact, flags=re.IGNORECASE)
    compact = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", compact, flags=re.IGNORECASE)
    return compact.rstrip(".,;:")


def merge_split_same_href_doi_anchors(html: str) -> str:
    """Merge DOI labels split by a short plain-text fragment between same-href anchors."""

    def replace(match: re.Match[str]) -> str:
        href = href_attr_literal(match.group("attrs"))
        next_href = href_attr_literal(match.group("next_attrs"))
        if href is None or next_href is None:
            return match.group(0)
        href_core = _doi_core_from_href(href)
        next_href_core = _doi_core_from_href(next_href)
        if href_core is None or next_href_core is None:
            return match.group(0)
        if href_core.rstrip(".,;:").lower() != next_href_core.rstrip(".,;:").lower():
            return match.group(0)

        body_text = visible_text(match.group("body"))
        visible_label = f"{body_text}{visible_text(match.group('mid'))}{visible_text(match.group('next_body'))}"
        if _doi_label_core(visible_label).lower() != href_core.rstrip(".,;:").lower():
            return match.group(0)

        if re.match(r"\s*https?://(?:dx\.)?doi\.org/", visible_label, re.IGNORECASE):
            label = _escape_html_text(strip_wrapping_url_quotes(href).rstrip(".,;:"))
            return f'<a{match.group("attrs")}>{label}</a>'

        prefix_match = re.match(r"(?P<prefix>[\s\S]*?\bdoi\s*:)\s*", body_text, re.IGNORECASE)
        prefix = f"{prefix_match.group('prefix')} " if prefix_match is not None else ""
        label = _escape_html_text(href_core.rstrip(".,;:"))
        return f'{prefix}<a{match.group("attrs")}>{label}</a>'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = SPLIT_SAME_HREF_DOI_ANCHOR_TEXT_PATTERN.sub(replace, current)
    return current


def repair_split_doi_head_tail_anchors(html: str) -> str:
    """Join ``doi:10.x/`` text with an immediately following DOI-tail anchor."""

    def replace(match: re.Match[str]) -> str:
        href = href_attr_literal(match.group("attrs"))
        if href is None:
            return match.group(0)
        href = strip_wrapping_url_quotes(href)
        doi_match = re.match(r"https?://(?:dx\.)?doi\.org/(?P<doi>10\..+)$", href, re.IGNORECASE)
        if doi_match is None:
            return match.group(0)
        href_doi = doi_match.group("doi").rstrip(".,;:")
        head = compact_visible_url_fragment(match.group("head"))
        body = strip_url_fragment_edge_quotes(compact_visible_url_fragment(visible_text(match.group("body"))))
        if f"{head}{body}".rstrip(".,;:").lower() != href_doi.lower():
            return match.group(0)
        label = _escape_html_text(href_doi)
        return f'{match.group("prefix")}<a{match.group("attrs")}>{label}</a>'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = SPLIT_DOI_HEAD_TAIL_ANCHOR_PATTERN.sub(replace, current)
    return current


def repair_split_doi_url_anchor_path_tails(html: str) -> str:
    """Join DOI URL anchors split inside the DOI path, e.g. ``annure v.bioeng``."""

    def replace(match: re.Match[str]) -> str:
        href = strip_wrapping_url_quotes(match.group("href"))
        body = strip_wrapping_url_quotes(visible_text(match.group("body")).strip())
        if href.rstrip(".,;:") != body.rstrip(".,;:"):
            return match.group(0)
        tail = visible_text(match.group("tail"))
        compact_tail = re.sub(r"\s+", "", tail)
        if not re.match(r"^[A-Za-z][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{3,}$", compact_tail):
            return match.group(0)
        if not re.search(r"(?:v[.-]|[A-Za-z]{2}\.|[A-Za-z]{2,}-)", tail, re.IGNORECASE):
            return match.group(0)
        candidate = f"{href}{compact_tail}"
        merged_url, trailing = split_url_and_trailing_punct(candidate + match.group("trailing"))
        if not re.match(r"https?://(?:dx\.)?doi\.org/10\.\d{4,9}/\S{8,}$", merged_url, re.IGNORECASE):
            return match.group(0)
        attrs = re.sub(
            r'(\bhref\s*=\s*)(["\'])(.*?)\2',
            lambda m: f'{m.group(1)}"{escape_html_attr_literal(merged_url)}"',
            match.group("attrs"),
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return f'<a{attrs}>{_escape_html_text(merged_url)}</a>{trailing}'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = SPLIT_DOI_URL_ANCHOR_PATH_TAIL_PATTERN.sub(replace, current)
    return current


def normalize_same_href_text_anchor_label(label: str) -> str:
    normalized = re.sub(r"\s+", " ", label).strip()
    return re.sub(r"\bsupple\s+mental\b", "supplemental", normalized, flags=re.IGNORECASE)


def looks_like_split_same_href_text_label(label: str) -> bool:
    if len(label) < 8 or len(label) > 180:
        return False
    if re.search(r"https?://|doi\.org/|\b10\.\d{4,9}/", label, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"\b(?:online|supplemental|supplementary|material|table|figure|appendix|data)\b",
            label,
            re.IGNORECASE,
        )
    )


def merge_adjacent_same_href_url_anchors(html: str) -> str:
    """Merge adjacent URL/DOI anchors that point to the same href."""

    def replace_protocol_prefix(match: re.Match[str]) -> str:
        href = strip_wrapping_url_quotes(match.group("href"))
        visible = repair_broken_visible_url_text(f"{match.group('body')}//{visible_text(match.group('next_body'))}")
        visible_url, trailing = split_url_and_trailing_punct(visible)
        if not url_fragment_keys_match_allowing_lost_hyphens(
            url_fragment_compare_key(visible_url),
            url_fragment_compare_key(href),
        ):
            return match.group(0)
        attrs = replace_href_attr_literal(match.group("attrs"), href)
        return f'<a{attrs}>{_escape_html_text(href)}</a>{trailing}'

    def replace(match: re.Match[str]) -> str:
        href = href_attr_literal(match.group("attrs"))
        next_href = href_attr_literal(match.group("next_attrs"))
        if href is None or next_href is None:
            return match.group(0)

        href = strip_wrapping_url_quotes(href)
        next_href = strip_wrapping_url_quotes(next_href)
        compact_href = strip_url_fragment_edge_quotes(compact_visible_url_fragment(href))
        compact_next_href = strip_url_fragment_edge_quotes(compact_visible_url_fragment(next_href))
        if compact_href != compact_next_href:
            return match.group(0)
        if not compact_href.lower().startswith(("http://", "https://")):
            return match.group(0)

        body = visible_text(match.group("body"))
        next_body = visible_text(match.group("next_body"))
        text_label = normalize_same_href_text_anchor_label(f"{body} {next_body}")
        if looks_like_split_same_href_text_label(text_label):
            return f'<a{match.group("attrs")}>{_escape_html_text(text_label)}</a>'

        prose_url_match = re.search(r"(?P<prefix>[\s\S]*?)(?P<head>https?://\S+)\s*$", body, re.IGNORECASE)
        if prose_url_match is not None:
            candidate = repair_broken_visible_url_text(f"{prose_url_match.group('head')}{next_body}")
            candidate_url, candidate_trailing = split_url_and_trailing_punct(candidate)
            if url_fragment_keys_match_allowing_lost_hyphens(
                url_fragment_compare_key(candidate_url),
                url_fragment_compare_key(html_lib.unescape(href)),
            ):
                attrs = replace_href_attr_literal(match.group("attrs"), html_lib.unescape(href))
                prefix = _escape_html_text(prose_url_match.group("prefix"))
                return f'{prefix}<a{attrs}>{_escape_html_text(html_lib.unescape(href))}</a>{candidate_trailing}'

        compact_body = strip_url_fragment_edge_quotes(compact_visible_url_fragment(body + next_body)).strip("()[]")
        doi_href_match = re.match(r"https?://(?:dx\.)?doi\.org/(?P<doi>10\..+)$", compact_href, re.IGNORECASE)
        if doi_href_match is not None:
            doi_label = re.sub(r"^(?:doi:|digitalobjectidentifier)", "", compact_body, flags=re.IGNORECASE)
            doi_label = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi_label, flags=re.IGNORECASE)
            if doi_label.rstrip(".,;:").lower() == doi_href_match.group("doi").rstrip(".,;:").lower():
                if compact_body.lower().startswith(("http://", "https://")):
                    return f'<a{match.group("attrs")}>{_escape_html_text(compact_href.rstrip(".,;:"))}</a>'
                prefix = "doi: " if re.match(r"doi:", compact_body, re.IGNORECASE) else ""
                return f'{prefix}<a{match.group("attrs")}>{_escape_html_text(doi_href_match.group("doi").rstrip(".,;:"))}</a>'
        if not compact_body:
            return match.group(0)
        if not (
            compact_href.startswith(compact_body)
            or compact_body.startswith("http://")
            or compact_body.startswith("https://")
            or compact_body.startswith("doi.org/")
            or compact_body.startswith("10.")
        ):
            return match.group(0)
        label = compact_body
        if compact_href.replace("-", "") == label.replace("-", ""):
            label = compact_href
        elif compact_href.startswith(label) and len(compact_href) >= len(label):
            label = compact_href if len(label) >= max(12, len(compact_href) - 4) else label
        escaped_href = escape_html_attr_literal(compact_href)
        escaped_label = _escape_html_text(label)
        return f'<a href="{escaped_href}" target="_blank" rel="noopener noreferrer">{escaped_label}</a>'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = IDENTICAL_HREF_PROTOCOL_PREFIX_ANCHOR_PATTERN.sub(replace_protocol_prefix, current)
        current = ADJACENT_IDENTICAL_HREF_URL_ANCHOR_PATTERN.sub(replace, current)
        current = ADJACENT_SAME_HREF_ANCHOR_PATTERN.sub(replace, current)
    return current


def normalize_mailto_address(address: str) -> str:
    normalized = html_lib.unescape(address).strip()
    normalized = normalized.replace("\\protect _", "_").replace("\\_", "_")
    return re.sub(r"\s+", "", normalized)


def merge_adjacent_same_href_mailto_anchors(html: str) -> str:
    """Merge OCR-split mailto anchors that point to the same address."""

    def replace(match: re.Match[str]) -> str:
        href = href_attr_literal(match.group("attrs"))
        next_href = href_attr_literal(match.group("next_attrs"))
        if href is None or next_href is None:
            return match.group(0)
        if href.lower() != next_href.lower() or not href.lower().startswith("mailto:"):
            return match.group(0)

        visible_label = re.sub(r"\s+", "", visible_text(match.group("body")) + visible_text(match.group("next_body")))
        label_match = re.match(
            r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?P<trailing>[\]).,;:]*)$",
            visible_label,
        )
        if label_match is None:
            return match.group(0)

        label = label_match.group("email")
        address = normalize_mailto_address(href[len("mailto:") :])
        if label.lower() != address.lower():
            return match.group(0)
        escaped_href = escape_html_attr_literal(f"mailto:{address}")
        escaped_label = _escape_html_text(label)
        return f'<a href="{escaped_href}">{escaped_label}</a>{_escape_html_text(label_match.group("trailing"))}'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = ADJACENT_SAME_MAILTO_ANCHOR_PATTERN.sub(replace, current)
    return current


def repair_split_www_domain_anchor_with_noisy_href(html: str) -> str:
    """Recover ``http://www.example`` when the continuation anchor href is OCR-noisy."""

    def replace(match: re.Match[str]) -> str:
        visible = visible_text(match.group("next_body"))
        domain_match = re.match(
            r"\s*(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?P<trailing>[\s\S]*)",
            visible,
        )
        if domain_match is None:
            return match.group(0)
        domain = domain_match.group("domain").rstrip(".,;:)")
        if "." not in domain:
            return match.group(0)
        merged_url = f"http://www.{domain}"
        attrs = replace_href_attr_literal(match.group("attrs"), merged_url)
        return f'<a{attrs}>{_escape_html_text(merged_url)}</a>{_escape_html_text(domain_match.group("trailing"))}'

    return SPLIT_WWW_DOMAIN_NOISY_HREF_PATTERN.sub(replace, html)


def merge_post_autolink_split_url_anchors(html: str) -> str:
    """Merge URL anchors that were split by OCR and then autolinked separately."""

    def replace(match: re.Match[str]) -> str:
        href = strip_wrapping_url_quotes(match.group("href"))
        next_href = strip_wrapping_url_quotes(match.group("next_href"))
        body = visible_text(match.group("body"))
        next_body = visible_text(match.group("next_body"))
        tail = match.group("tail") or ""

        combined = f"{body}{match.group('join')}{next_body}{tail}"
        repaired = repair_broken_visible_url_text(combined)
        if not starts_like_visible_url_fragment(repaired):
            return match.group(0)
        repaired_key = url_fragment_compare_key(repaired)
        next_href_key = url_fragment_compare_key(next_href)
        href_key = url_fragment_compare_key(href)
        if not repaired_key:
            return match.group(0)
        if not (
            next_href_key.startswith(repaired_key)
            or repaired_key.startswith(next_href_key)
            or (href_key and href_key != next_href_key and next_href_key.startswith(href_key))
        ):
            return match.group(0)

        repaired_url, repaired_trailing = split_url_and_trailing_punct(repaired)
        repaired_key = url_fragment_compare_key(repaired_url)
        label = next_href if next_href_key.startswith(repaired_key) and len(repaired_key) >= len(next_href_key) - 4 else repaired_url
        merged_url, trailing = split_url_and_trailing_punct(label)
        if not trailing:
            trailing = repaired_trailing
        if not re.search(r"\.[A-Za-z]{2,}(?:[/:?#]|$)", merged_url, re.IGNORECASE):
            return match.group(0)
        attrs = re.sub(
            r'(\bhref\s*=\s*)(["\'])(.*?)\2',
            lambda m: f'{m.group(1)}"{escape_html_attr_literal(merged_url)}"',
            match.group("next_attrs"),
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return f'<a{attrs}>{_escape_html_text(merged_url)}</a>{trailing}'

    previous = None
    current = html
    while previous != current:
        previous = current
        current = POST_AUTOLINK_SPLIT_URL_ANCHOR_PATTERN.sub(replace, current)
    return current


__all__ = [
    "ADJACENT_IDENTICAL_HREF_URL_ANCHOR_PATTERN",
    "ADJACENT_SAME_HREF_ANCHOR_PATTERN",
    "ADJACENT_SAME_MAILTO_ANCHOR_PATTERN",
    "IDENTICAL_HREF_PROTOCOL_PREFIX_ANCHOR_PATTERN",
    "POST_AUTOLINK_SPLIT_URL_ANCHOR_PATTERN",
    "PROSE_PREFIXED_URL_ANCHOR_TAIL_PATTERN",
    "SPLIT_SCHEME_URL_ANCHOR_FRAGMENTS_PATTERN",
    "SPLIT_SCHEME_URL_ANCHOR_HEAD_PATTERN",
    "SPLIT_DOI_HEAD_TAIL_ANCHOR_PATTERN",
    "SPLIT_DOI_URL_ANCHOR_PATH_TAIL_PATTERN",
    "SPLIT_SAME_HREF_DOI_ANCHOR_TEXT_PATTERN",
    "SPLIT_WWW_DOMAIN_NOISY_HREF_PATTERN",
    "SPLIT_VISIBLE_URL_ANCHOR_PATTERN",
    "SPLIT_URL_ANCHOR_BLOCK_TAIL_PATTERN",
    "SPLIT_URL_ANCHOR_DOMAIN_TAIL_PATTERN",
    "SPACED_PROTOCOL_HREF_ATTR_PATTERN",
    "SPACED_PROTOCOL_URL_ANCHOR_PATTERN",
    "URL_ANCHOR_TEXT_PATTERN",
    "URL_FRAGMENT_ANCHOR_CHUNK_PATTERN",
    "URL_FRAGMENT_TEXT_CHUNK_PATTERN",
    "consume_compact_prefix",
    "looks_like_split_same_href_text_label",
    "merge_post_autolink_split_url_anchors",
    "merge_adjacent_same_href_mailto_anchors",
    "merge_adjacent_same_href_url_anchors",
    "merge_split_same_href_doi_anchors",
    "normalize_double_escaped_url_anchor_text",
    "normalize_mailto_address",
    "normalize_same_href_text_anchor_label",
    "repair_prose_prefixed_url_anchor_tail",
    "repair_split_doi_head_tail_anchors",
    "repair_split_doi_url_anchor_path_tails",
    "repair_split_scheme_url_anchor_fragments",
    "repair_split_scheme_url_anchor_runs",
    "repair_split_visible_url_anchors",
    "repair_split_url_anchor_block_tail",
    "repair_split_url_anchor_domain_tail",
    "repair_split_www_domain_anchor_with_noisy_href",
    "repair_spaced_protocol_url_anchors",
    "unescape_html_entities_repeated",
]
