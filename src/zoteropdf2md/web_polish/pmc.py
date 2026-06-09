"""PMC/NCBI article polish rules."""

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
        kind=WebHtmlKind.PMC_ARTICLE,
        token_selectors=(
            ("pmc-article", ".pmc-article"),
            ("pmc-article-section", ".pmc-article-section"),
            ("main-content", "#main-content"),
        ),
        min_text_length=800,
    )
    return extraction or extract_generic_web_article_fragment(html, kind=WebHtmlKind.PMC_ARTICLE)


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
            "pmc-actions-bar",
            "pmc-sidebar",
            "pmc-search",
            "pmc-page-banner",
            "pmc-menu",
            "article-page-sidebar",
            "usa-banner",
            "usa-overlay",
            "social-sharing",
            "figpopup",
            "ncbi-header",
            "ncbi-footer",
        ),
    ).strip()
