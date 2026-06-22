from __future__ import annotations

import html as html_lib
import re

from ..url_repair import BROKEN_PLAIN_URL_PROTOCOL_PATTERN, compact_visible_url_fragment


SPACED_PROTOCOL_HREF_ATTR_PATTERN = re.compile(
    r'(?P<prefix>\bhref\s*=\s*)(?P<quote>["\'])(?P<scheme>https?:)\s+//(?P<rest>[^"\']+)(?P=quote)',
    re.IGNORECASE,
)
SPACED_PROTOCOL_URL_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']https?:\s+//[^"\']+["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)


def _escape_html_text(value: str) -> str:
    return html_lib.escape(value, quote=False)


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


__all__ = [
    "SPACED_PROTOCOL_HREF_ATTR_PATTERN",
    "SPACED_PROTOCOL_URL_ANCHOR_PATTERN",
    "repair_spaced_protocol_url_anchors",
]
