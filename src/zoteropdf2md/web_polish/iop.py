"""IOPscience article polish rules."""

from __future__ import annotations

from html import escape as html_escape
from html import unescape
import re

from .core import (
    WebArticleExtraction,
    WebHtmlKind,
    _attr_value,
    _balanced_element_from_match,
    _extract_fragment_by_attr_tokens,
    _remove_elements_by_attr_tokens,
    _set_attr_value,
    _visible_text_length,
    extract_generic_web_article_fragment,
)


_IMG_OPEN_RE = re.compile(r"<img\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
_FA_ICON_SVG_RE = re.compile(
    r"<svg\b(?=[^>]*\bclass\s*=\s*(['\"])[^'\"]*\bfa-icon\b)[\s\S]*?</svg>",
    re.IGNORECASE,
)
_EXPORT_CITATION_RE = re.compile(
    r"<p\b[^>]*>\s*<small>\s*Export\s+citation\s+and\s+abstract\s*</small>\s*</p>",
    re.IGNORECASE,
)
_REFERENCES_CONTAINER_RE = re.compile(
    r"<(?P<tag>div|section)\b(?P<attrs>[^<>]*\breferences\b[^<>]*)>",
    re.IGNORECASE,
)


def extract_article_fragment(html: str) -> WebArticleExtraction:
    extraction = _extract_fragment_by_attr_tokens(
        html,
        kind=WebHtmlKind.IOP_ARTICLE,
        token_selectors=(
            ("article-content", ".article-content"),
        ),
        min_text_length=800,
    )
    if extraction is not None:
        return extraction

    extraction = _extract_fragment_by_attr_tokens(
        html,
        kind=WebHtmlKind.IOP_ARTICLE,
        token_selectors=(
            ("wd-jnl-art-full-text", ".wd-jnl-art-full-text"),
            ("itemprop=\"articleBody\"", '[itemprop="articleBody"]'),
            ("itemprop='articleBody'", '[itemprop="articleBody"]'),
        ),
        min_text_length=800,
    )
    return extraction or extract_generic_web_article_fragment(html, kind=WebHtmlKind.IOP_ARTICLE)


def normalize_article_fragment(
    html: str,
    *,
    source_url: str | None = None,
    canonical_url: str | None = None,
) -> str:
    del source_url, canonical_url
    html = _promote_lazy_image_sources(html)
    html = _remove_elements_by_attr_tokens(
        html,
        (
            "leaderboard-ad",
            "ad-iframe",
            "ad-iframe-wrap",
            "advert",
            "middle-ad",
            "sidebar-ad",
            "article-metrics",
            "wd-jnl-art-license",
            "jnl-art-license",
            "content-tools",
            "article-tools",
            "content-nav",
            "linked-articles",
            "related-content",
            "related-article",
            "wd-related-articles",
            "side-and-below",
            "recommend",
            "download-options",
            "fig-dwnld",
            "btn-multi-block",
            "zoom-tools",
            "reveal-trigger",
            "loading-icon",
            "print-hide",
            "share",
            "cookie",
            "toolbar",
        ),
        tags=("aside", "button", "div", "footer", "header", "nav", "p", "section", "span"),
    )
    html = _EXPORT_CITATION_RE.sub(" ", html)
    html = _FA_ICON_SVG_RE.sub(" ", html)
    html = _remove_empty_references_shells(html)
    return html.strip()


def _promote_lazy_image_sources(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        open_tag = match.group(0)
        attrs = match.group("attrs")
        data_src = (_attr_value(attrs, "data-src") or "").strip()
        if not _is_remote_url(data_src):
            return open_tag

        src = (_attr_value(attrs, "src") or "").strip()
        if src and not _is_placeholder_src(src):
            return open_tag

        next_tag = _set_attr_value(open_tag, "src", data_src)
        if "data-z2m-src-placeholder" in next_tag.lower() or not src:
            return next_tag
        escaped_src = html_escape(src, quote=True)
        return re.sub(r">\s*$", f' data-z2m-src-placeholder="{escaped_src}">', next_tag, count=1)

    return _IMG_OPEN_RE.sub(replace, html)


def _is_remote_url(value: str) -> bool:
    lowered = unescape(value).strip().lower()
    return lowered.startswith("https://") or lowered.startswith("http://")


def _is_placeholder_src(value: str) -> bool:
    lowered = unescape(value).strip().lower()
    return lowered.startswith("data:image/")


def _remove_empty_references_shells(html: str) -> str:
    cleaned = html
    previous = None
    while previous != cleaned:
        previous = cleaned
        for match in list(_REFERENCES_CONTAINER_RE.finditer(cleaned)):
            fragment = _balanced_element_from_match(cleaned, match)
            if fragment is None:
                continue
            visible_length = _visible_text_length(fragment)
            if visible_length >= 20:
                continue
            cleaned = cleaned[: match.start()] + " " + cleaned[match.start() + len(fragment) :]
            break
    return cleaned
