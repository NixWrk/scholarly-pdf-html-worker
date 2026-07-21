from __future__ import annotations

import html as html_lib
import re

from ..html_links import escape_html_attr_literal, href_attr_literal
from ..url_repair import split_url_and_trailing_punct
from .html_fragments import node_has_class, visible_text


DOI_METADATA_BODY_BOUNDARY_PATTERN = re.compile(
    r"(?P<doi>(?:\b(?:DOI|doi)\s*:\s*)?(?:"
    r"<a\b(?=[^>]*\bhref\s*=\s*['\"]https?://(?:dx\.)?doi\.org/10\.)[^>]*>[\s\S]{0,400}?</a>"
    r"|https?://(?:dx\.)?doi\.org/10\.[^\s<]+"
    r"|10\.\d{4,9}/[^\s<]+"
    r"))"
    r"(?P<space>\s+)"
    r"(?P<tail>(?:</?(?:span|em|i|b|strong)\b[^>]*>\s*)*"
    r"(?:the|this|we|in|as|or|depicted|generated|lines)\b[\s\S]{20,})",
    re.IGNORECASE,
)
PLOS_TABLE_DOI_BODY_BOUNDARY_PATTERN = re.compile(
    r"(?P<doi>(?:\b(?:DOI|doi)\s*:\s*)?(?:"
    r"<a\b(?=[^>]*\bhref\s*=\s*['\"]https?://(?:dx\.)?doi\.org/10\.1371/journal\.pone\.[^'\"]+\.t\d+)"
    r"[^>]*>[\s\S]{0,400}?</a>"
    r"|https?://(?:dx\.)?doi\.org/10\.1371/journal\.pone\.[^\s<]+\.t\d+\b"
    r"|10\.1371/journal\.pone\.[^\s<]+\.t\d+\b"
    r"))"
    r"(?P<space>\s+)"
    r"(?P<tail>[\s\S]{35,})",
    re.IGNORECASE,
)
REFERENCE_PARAGRAPH_ATTR_PATTERN = re.compile(
    r"\b(?:id\s*=\s*['\"]ref-\d+|"
    r"class\s*=\s*['\"][^'\"]*(?:z2m-reference|z2m-bibliography|references|bibliography))",
    re.IGNORECASE,
)
DOI_MISWRAPPED_ANCHOR_LABEL_PATTERN = re.compile(
    r"<a\b(?P<attrs>[^>]*)>"
    r"(?P<body>(?:(?!</a>).)*?\bdoi:\s*10\.\d{4,9}/\s*)</a>"
    r"\s*(?P<tail>[^\s<]+)",
    re.IGNORECASE | re.DOTALL,
)
DOI_SWALLOWED_BROKEN_BLOCK_TAIL_PATTERN = re.compile(
    r"(?P<open><p\b[^>]*>\s*(?:DOI\s*:\s*)?)"
    r"<a\b[^>]*\bhref\s*=\s*(?P<quote>['\"])"
    r"(?P<url>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
    r"\s*</p>\s*<p>\s*(?P<head>[A-Za-z][A-Za-z-]*)\s*(?P=quote)[^>]*>"
    r"(?P<label>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
    r"\s+(?P=head)\s*</a>\s*(?P<rest>[\s\S]*?</p>)",
    re.IGNORECASE,
)
DOI_SWALLOWED_HREF_TAIL_PATTERN = re.compile(
    r"(?P<open><p\b[^>]*>\s*(?:DOI\s*:\s*)?)"
    r"<a\b[^>]*\bhref\s*=\s*(?P<quote>['\"])"
    r"(?P<url>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
    r"(?P<tail>\s+[A-Za-z][A-Za-z-]{1,80})(?P=quote)[^>]*>"
    r"(?P<label>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
    r"(?P=tail)</a>\s*(?P<rest>[\s\S]*?)</p>",
    re.IGNORECASE,
)
PARAGRAPH_BLOCK_PATTERN = re.compile(
    r"(?P<open><p\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></p>)",
    re.IGNORECASE,
)


def _escape_html_text(value: str) -> str:
    return html_lib.escape(value, quote=False)


def repair_miswrapped_doi_anchor_labels(html: str) -> str:
    """Move prose out of DOI anchors when OCR split the DOI after a slash."""

    def replace(match: re.Match[str]) -> str:
        href = href_attr_literal(match.group("attrs")) or ""
        href_match = re.match(
            r"https?://(?:dx\.)?doi\.org/(?P<doi>10\..+)$", href, re.IGNORECASE
        )
        if href_match is None:
            return match.group(0)
        href_doi = href_match.group("doi")
        body = match.group("body")
        doi_match = re.search(
            r"(?P<prefix>[\s\S]*?\bdoi:\s*)(?P<head>10\.\d{4,9}/)\s*$",
            body,
            re.IGNORECASE,
        )
        if doi_match is None:
            return match.group(0)
        full_doi = doi_match.group("head") + match.group("tail")
        if full_doi.rstrip(".,;:") != href_doi.rstrip(".,;:"):
            return match.group(0)
        full_doi, trailing = split_url_and_trailing_punct(full_doi)
        attrs = match.group("attrs")
        label = _escape_html_text(full_doi)
        return f"{doi_match.group('prefix')}<a{attrs}>{label}</a>{trailing}"

    return DOI_MISWRAPPED_ANCHOR_LABEL_PATTERN.sub(replace, html)


def repair_doi_anchor_swallowed_prose_tails(html: str) -> str:
    """Move prose tails out of DOI anchors whose href swallowed paragraph text."""
    if "doi.org/10." not in html.lower():
        return html

    def doi_paragraph(open_tag: str, url: str) -> str:
        escaped_url = escape_html_attr_literal(url)
        return f'{open_tag}<a href="{escaped_url}">{_escape_html_text(url)}</a></p>'

    def replace_broken_block(match: re.Match[str]) -> str:
        url = match.group("url")
        if match.group("label").rstrip(".,;:") != url.rstrip(".,;:"):
            return match.group(0)
        tail = f"{match.group('head')} {match.group('rest').lstrip()}"
        return f"{doi_paragraph(match.group('open'), url)}\n<p>{tail}"

    def replace_href_tail(match: re.Match[str]) -> str:
        url = match.group("url")
        if match.group("label").rstrip(".,;:") != url.rstrip(".,;:"):
            return match.group(0)
        tail = f"{match.group('tail').strip()} {match.group('rest').lstrip()}".rstrip()
        tail_text = visible_text(tail)
        if len(tail_text) < 25 or len(tail_text.split()) < 4:
            return match.group(0)
        return f"{doi_paragraph(match.group('open'), url)}\n<p>{tail}</p>"

    previous = None
    current = html
    while previous != current:
        previous = current
        current = DOI_SWALLOWED_BROKEN_BLOCK_TAIL_PATTERN.sub(
            replace_broken_block, current
        )
        current = DOI_SWALLOWED_HREF_TAIL_PATTERN.sub(replace_href_tail, current)
    return current


def split_doi_metadata_body_paragraphs(html: str) -> str:
    """Split DOI/front-matter metadata from body prose when both share one paragraph."""
    lowered = html.lower()
    if "doi" not in lowered and "10." not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        open_tag = match.group("open")
        if REFERENCE_PARAGRAPH_ATTR_PATTERN.search(open_tag):
            return match.group(0)

        body = match.group("body")
        boundary = PLOS_TABLE_DOI_BODY_BOUNDARY_PATTERN.search(body)
        is_plos_table_doi = boundary is not None
        if boundary is None:
            boundary = DOI_METADATA_BODY_BOUNDARY_PATTERN.search(body)
        if boundary is None:
            return match.group(0)
        if node_has_class(open_tag, "z2m-front-matter") and not is_plos_table_doi:
            return match.group(0)

        left_body = body[: boundary.end("doi")].rstrip()
        right_body = body[boundary.start("tail") :].lstrip()
        right_text = visible_text(right_body)
        if len(right_text) < 35 or len(right_text.split()) < 5:
            return match.group(0)

        prefix_text = visible_text(body[: boundary.start("doi")])
        if (
            len(prefix_text) > 500
            and not is_plos_table_doi
            and not re.search(
                r"\b(?:fig(?:ure)?|table|doi|copyright|license|received|published|available|plos)\b",
                prefix_text,
                re.IGNORECASE,
            )
        ):
            return match.group(0)

        return f"{open_tag}{left_body}{match.group('close')}\n<p>{right_body}</p>"

    return PARAGRAPH_BLOCK_PATTERN.sub(replace, html)


__all__ = [
    "DOI_METADATA_BODY_BOUNDARY_PATTERN",
    "DOI_MISWRAPPED_ANCHOR_LABEL_PATTERN",
    "DOI_SWALLOWED_BROKEN_BLOCK_TAIL_PATTERN",
    "DOI_SWALLOWED_HREF_TAIL_PATTERN",
    "PARAGRAPH_BLOCK_PATTERN",
    "PLOS_TABLE_DOI_BODY_BOUNDARY_PATTERN",
    "REFERENCE_PARAGRAPH_ATTR_PATTERN",
    "repair_doi_anchor_swallowed_prose_tails",
    "repair_miswrapped_doi_anchor_labels",
    "split_doi_metadata_body_paragraphs",
]
