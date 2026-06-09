"""Presentation-shell helpers for raw/Marker polished HTML."""

from __future__ import annotations

import re

from ..abbreviations import RU_ABBREV_TO_LATIN


_HEAD_OPEN_PATTERN = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
_HEAD_CLOSE_PATTERN = re.compile(r"</head>", re.IGNORECASE)
_META_CHARSET_PATTERN = re.compile(r"<meta\s+charset\s*=\s*['\"]?utf-8['\"]?\s*/?>", re.IGNORECASE)
_HTML_OPEN_PATTERN = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
_READABILITY_STYLE_BLOCK_PATTERN = re.compile(
    r"<style\b[^>]*\bdata-z2m-style\s*=\s*['\"]readable['\"][^>]*>[\s\S]*?</style>",
    re.IGNORECASE,
)
_BODY_PATTERN = re.compile(r"(<body\b[^>]*>)(.*?)(</body>)", re.IGNORECASE | re.DOTALL)
_TAG_SPLIT_PATTERN = re.compile(r"(<[^>]+>)")
_EMPTY_PARAGRAPH_PATTERN = re.compile(r"<p>\s*(?:&nbsp;|\u00a0)?\s*</p>", re.IGNORECASE)
_EXCESSIVE_BREAKS_PATTERN = re.compile(r"(?:<br\s*/?>\s*){4,}", re.IGNORECASE)
_CYRILLIC_CHAR_PATTERN = re.compile(r"[\u0400-\u04FF]")
_HEADING_TAG_PATTERN = re.compile(
    r"(<h[1-6]\b[^>]*>)(.*?)(</h[1-6]>)",
    re.IGNORECASE | re.DOTALL,
)
_HEADING_PERIOD_BEFORE_ABBREV_PATTERN = re.compile(
    r"\.\s+(<(?:i|em|b|strong)\b[^>]*>\s*[A-Z]{2,})",
    re.IGNORECASE,
)
_HEADING_ACRONYM_SENSOR_PATTERN = re.compile(
    r"(<(i|em|b|strong)\b[^>]*>\s*[A-Z0-9]{2,8}\s*</\2>)\s+датчик\b",
    re.IGNORECASE,
)
_CYRILLIC_CAPITAL_AFTER_INLINE_PATTERN = re.compile(
    r"(</(i|em|b|strong)>)\s+([\u0410-\u042F\u0401])",
    re.IGNORECASE,
)


def inject_default_styles(html: str, *, readability_style: str) -> str:
    if _READABILITY_STYLE_BLOCK_PATTERN.search(html):
        return _READABILITY_STYLE_BLOCK_PATTERN.sub(readability_style, html, count=1)

    if _HEAD_CLOSE_PATTERN.search(html):
        return _HEAD_CLOSE_PATTERN.sub(f"{readability_style}\n</head>", html, count=1)

    if _HTML_OPEN_PATTERN.search(html):
        return _HTML_OPEN_PATTERN.sub(
            lambda m: f"{m.group(0)}\n<head>\n{readability_style}\n</head>",
            html,
            count=1,
        )

    return f"<head>\n{readability_style}\n</head>\n{html}"


def inject_utf8_charset(html: str) -> str:
    if _META_CHARSET_PATTERN.search(html):
        return html

    if _HEAD_OPEN_PATTERN.search(html):
        return _HEAD_OPEN_PATTERN.sub(
            lambda m: f'{m.group(0)}\n<meta charset="utf-8">',
            html,
            count=1,
        )

    if _HTML_OPEN_PATTERN.search(html):
        return _HTML_OPEN_PATTERN.sub(
            lambda m: f'{m.group(0)}\n<head>\n<meta charset="utf-8">\n</head>',
            html,
            count=1,
        )

    return f'<head>\n<meta charset="utf-8">\n</head>\n{html}'


def wrap_body_in_container(html: str) -> str:
    if 'id="marker-doc"' in html:
        return html

    def replace(match: re.Match[str]) -> str:
        body_open, body_inner, body_close = match.groups()
        return f'{body_open}\n  <main id="marker-doc">\n{body_inner}\n  </main>\n{body_close}'

    return _BODY_PATTERN.sub(replace, html, count=1)


def cleanup_empty_html_blocks(html: str) -> str:
    cleaned = _EMPTY_PARAGRAPH_PATTERN.sub("", html)
    cleaned = _EXCESSIVE_BREAKS_PATTERN.sub("<br><br>", cleaned)
    return cleaned


def fix_heading_translation_breaks(html: str) -> str:
    """Remove false sentence-break periods inserted before inline abbreviations in headings."""

    def fix_heading(match: re.Match[str]) -> str:
        open_tag, content, close_tag = match.group(1), match.group(2), match.group(3)
        fixed = _HEADING_PERIOD_BEFORE_ABBREV_PATTERN.sub(r" \1", content)
        fixed = _CYRILLIC_CAPITAL_AFTER_INLINE_PATTERN.sub(
            lambda m: m.group(1) + " " + m.group(3).lower(),
            fixed,
        )
        fixed = _HEADING_ACRONYM_SENSOR_PATTERN.sub(
            lambda m: f"{m.group(1)}-датчика",
            fixed,
        )
        return f"{open_tag}{fixed}{close_tag}"

    return _HEADING_TAG_PATTERN.sub(fix_heading, html)


def restore_abbreviations(html: str) -> str:
    """Restore Latin abbreviations in text nodes without touching HTML tags."""

    if _CYRILLIC_CHAR_PATTERN.search(html) is None:
        return html
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            out.append(part)
            continue

        restored_part = part
        for pattern, replacement in RU_ABBREV_TO_LATIN.items():
            restored_part = re.sub(
                pattern,
                lambda _: replacement,
                restored_part,
                flags=re.IGNORECASE,
            )
        out.append(restored_part)

    return "".join(out)
