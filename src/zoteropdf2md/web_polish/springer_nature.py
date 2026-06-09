"""Springer/Nature Link article polish rules."""

from __future__ import annotations

from ..web_html_polish import (
    WebArticleExtraction,
    WebHtmlKind,
    _extract_fragment_by_attr_tokens,
    _remove_elements_by_attr_tokens,
    extract_generic_web_article_fragment,
)


def extract_article_fragment(html: str) -> WebArticleExtraction:
    extraction = _extract_fragment_by_attr_tokens(
        html,
        kind=WebHtmlKind.SPRINGER_NATURE_ARTICLE,
        token_selectors=(
            ("c-article-main", ".c-article-main"),
            ("c-article-body", ".c-article-body"),
            ("article__body", ".article__body"),
            ("article-body", ".article-body"),
            ("main-content", "#main-content"),
        ),
        min_text_length=800,
    )
    return extraction or extract_generic_web_article_fragment(html, kind=WebHtmlKind.SPRINGER_NATURE_ARTICLE)


def normalize_article_fragment(
    html: str,
    *,
    source_url: str | None = None,
    canonical_url: str | None = None,
) -> str:
    del source_url, canonical_url
    return _remove_elements_by_attr_tokens(
        html,
        (
            "c-article-extras",
            "c-article-metrics",
            "c-article-recommendations",
            "c-article-sidebar",
            "c-article-related",
            "c-pdf-download",
            "app-article-metrics",
            "js-article__aside",
            "js-article-sidebar",
            "article-sidebar",
            "share",
            "advert",
        ),
    ).strip()
