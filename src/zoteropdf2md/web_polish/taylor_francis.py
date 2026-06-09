"""Taylor & Francis article polish rules."""

from __future__ import annotations

import re

from ..web_html_polish import (
    WebArticleExtraction,
    WebHtmlKind,
    _attr_value,
    _extract_fragment_by_attr_tokens,
    _remove_elements_by_attr_tokens,
    _set_attr_value,
    extract_generic_web_article_fragment,
)


_A_OPEN_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
_BUTTON_RE = re.compile(
    r"<button\b(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</button>",
    re.IGNORECASE,
)


def extract_article_fragment(html: str) -> WebArticleExtraction:
    extraction = _extract_fragment_by_attr_tokens(
        html,
        kind=WebHtmlKind.TAYLOR_FRANCIS_ARTICLE,
        token_selectors=(
            ("nlm_article", "article .NLM_article"),
            ("hlfld-fulltext", ".hlFld-Fulltext"),
            ("article", "article"),
        ),
        min_text_length=800,
    )
    return extraction or extract_generic_web_article_fragment(html, kind=WebHtmlKind.TAYLOR_FRANCIS_ARTICLE)


def normalize_article_fragment(
    html: str,
    *,
    source_url: str | None = None,
    canonical_url: str | None = None,
) -> str:
    del source_url, canonical_url
    html = _remove_elements_by_attr_tokens(
        html,
        (
            "dropzone",
            "embedded-pdf-target",
            "article-tools",
            "social-share",
            "related-content",
            "recommend",
            "advert",
            "metrics",
        ),
    )
    html = _rewrite_data_behaviour_ref_links(html)
    html = _rewrite_data_rid_links(html)
    html = _rewrite_data_id_links(html)
    html = _rewrite_table_figure_buttons(html)
    return html.strip()


def _rewrite_data_rid_links(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        open_tag = match.group(0)
        attrs = match.group("attrs")
        href = (_attr_value(attrs, "href") or "").strip()
        data_rid = (_attr_value(attrs, "data-rid") or "").strip()
        if not data_rid or href not in {"", "#"}:
            return open_tag
        target = data_rid.split()[0]
        if not target:
            return open_tag
        return _set_attr_value(open_tag, "href", f"#{target}")

    return _A_OPEN_RE.sub(replace, html)


def _rewrite_data_behaviour_ref_links(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        open_tag = match.group(0)
        attrs = match.group("attrs")
        href = (_attr_value(attrs, "href") or "").strip()
        behaviour_ref = (_attr_value(attrs, "data-behaviour-ref") or "").strip()
        if not behaviour_ref or href not in {"", "#"}:
            return open_tag
        target = behaviour_ref if behaviour_ref.startswith("#") else f"#{behaviour_ref}"
        return _set_attr_value(open_tag, "href", target)

    return _A_OPEN_RE.sub(replace, html)


def _rewrite_data_id_links(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        open_tag = match.group(0)
        attrs = match.group("attrs")
        href = (_attr_value(attrs, "href") or "").strip()
        data_id = (_attr_value(attrs, "data-id") or "").strip()
        if not data_id or href not in {"", "#"}:
            return open_tag
        return _set_attr_value(open_tag, "href", f"#{data_id}")

    return _A_OPEN_RE.sub(replace, html)


def _rewrite_table_figure_buttons(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        body = match.group("body").strip()
        data_id = (_attr_value(attrs, "data-id") or "").strip()
        if not data_id:
            return match.group(0)
        class_value = (_attr_value(attrs, "class") or "").lower()
        if "show-table-fig-ref" not in class_value and "ref" not in class_value:
            return match.group(0)
        return f'<a class="z2m-web-ref-button" href="#{data_id}">{body}</a>'

    return _BUTTON_RE.sub(replace, html)
