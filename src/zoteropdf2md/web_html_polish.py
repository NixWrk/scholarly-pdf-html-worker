"""Web-native HTML normalization helpers.

This module is intentionally separate from ``single_file_html``.  The latter
repairs Marker/PDF HTML, while web-native sources such as arXiv LaTeXML mostly
need source-aware normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from html import escape as html_escape
from html import unescape
from pathlib import Path
import re
import urllib.parse

from .html_images import (
    InlineHtmlResult,
    is_inline_or_remote,
    to_data_url,
    validate_data_url,
)
from .html_links import (
    SameDocumentLinkCanonicalization,
    _ATTR_HREF_RE,
    _arxiv_abs_parts,
    _arxiv_html_parts,
    _html_fragment_targets,
    _is_root_relative_url,
    _urlsplit_or_none,
    canonicalize_same_document_links,
    count_same_document_absolute_fragment_links,
    declared_document_urls as _declared_document_urls,
)


class WebHtmlKind(str, Enum):
    """Known web HTML source kinds."""

    ARXIV_ABS_PAGE = "arxiv_abs_page"
    ARXIV_LATEXML = "arxiv_latexml"
    PMC_ARTICLE = "pmc_article"
    TAYLOR_FRANCIS_ARTICLE = "taylor_francis_article"
    SPRINGER_NATURE_ARTICLE = "springer_nature_article"
    RESEARCHGATE_PAGE = "researchgate_page"
    SCIENDO_ABSTRACT_PAGE = "sciendo_abstract_page"
    OJS_ABSTRACT_PAGE = "ojs_abstract_page"
    GENERIC_ARTICLE = "generic_article"
    UNKNOWN = "unknown"


class WebHtmlPolishError(ValueError):
    """Raised when a web HTML attachment cannot be polished as an article."""


@dataclass(frozen=True)
class WebHtmlPolishResult:
    html: str
    kind: WebHtmlKind
    article_extracted: bool
    article_selector: str | None
    same_document_links_rewritten: int
    unresolved_same_document_links: int


@dataclass(frozen=True)
class WebHtmlFilePolishResult:
    html: str
    kind: WebHtmlKind
    article_extracted: bool
    article_selector: str | None
    same_document_links_rewritten: int
    unresolved_same_document_links: int
    inlined_images: int


@dataclass(frozen=True)
class WebArticleExtraction:
    html: str
    extracted: bool
    selector: str | None
    text_length: int


@dataclass(frozen=True)
class _ArticleCandidate:
    html: str
    tag: str
    attrs: str
    score: int
    selector: str
    text_length: int


_IMG_SRC_RE = re.compile(
    r"(?P<prefix><img\b[^>]*?\ssrc\s*=\s*)(?P<quote>['\"])(?P<src>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_SRCSET_RE = re.compile(
    r"(?P<prefix><(?:img|source)\b[^>]*?\ssrcset\s*=\s*)(?P<quote>['\"])(?P<srcset>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_ROOT_RELATIVE_URL_ATTR_RE = re.compile(
    r"(?P<prefix>(?<![\w:-])(?P<name>href|src|action|poster)\s*=\s*)"
    r"(?P<quote>['\"])(?P<url>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_TITLE_RE = re.compile(r"<title\b[^>]*>(?P<title>[\s\S]*?)</title>", re.IGNORECASE)
_BODY_RE = re.compile(r"<body\b[^>]*>(?P<body>[\s\S]*?)</body>", re.IGNORECASE)
_ARTICLE_START_RE = re.compile(
    r"<(?P<tag>article|main|section|div)\b(?P<attrs>[^<>]*)>",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"</?(?P<tag>[A-Za-z][A-Za-z0-9:-]*)(?P<attrs>[^<>]*)?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_NON_ARTICLE_BLOCK_RE = re.compile(
    r"<(?:script|style|noscript|template)\b[\s\S]*?</(?:script|style|noscript|template)>",
    re.IGNORECASE,
)
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_WEB_READABILITY_STYLE = """<style data-z2m-style="web-html-polish">
:root { color-scheme: light; }
body {
  margin: 0;
  background: #f7f8fa;
  color: #171717;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.6;
}
#web-doc {
  box-sizing: border-box;
  max-width: 980px;
  margin: 0 auto;
  padding: 32px 24px 56px;
  background: #fff;
}
img, svg, video, canvas { max-width: 100%; height: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #d8dde6; padding: 6px 8px; vertical-align: top; }
pre, code { white-space: pre-wrap; overflow-wrap: anywhere; }
a { color: #0645ad; overflow-wrap: anywhere; }
figure,
.fig,
.fig-inline,
.tbl,
.table-wrap,
.tableView,
.NLM_table-wrap,
.NLM_table,
.c-article-section__figure,
.c-article-section__table,
.c-article-table,
figure.ltx_table {
  margin: 28px 0;
  padding: 14px 0;
  border-top: 1px solid #cbd5e1;
  border-bottom: 1px solid #cbd5e1;
  background: #fff;
  clear: both;
}
.c-article-section__figure figure,
.c-article-section__table figure,
.c-article-table figure,
figure figure {
  margin: 0;
  padding: 0;
  border: 0;
}
figcaption,
caption,
.fig-caption,
.table-caption,
.caption,
.captionText,
.tableCaption,
.NLM_caption,
.c-article-table__caption,
.ltx_caption {
  display: block;
  margin: 0 0 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
  color: #374151;
  font-size: 0.95em;
  line-height: 1.5;
}
.captionLabel,
.fig-label,
.table-label,
.ltx_tag_caption,
.c-article-section__figure-caption,
.c-article-section__table-caption,
.c-article-table__caption b {
  color: #111827;
  font-weight: 650;
}
.c-article-references,
ul.ref-list,
ul.references.numeric-ordered-list,
.ref-list > ul,
.references > ul {
  list-style: none;
  counter-reset: z2m-ref;
  padding-left: 0;
}
.c-article-references > li,
ul.ref-list > li,
ul.references.numeric-ordered-list > li,
.ref-list > ul > li,
.references > ul > li {
  counter-increment: z2m-ref;
  position: relative;
  padding-left: 2.8em;
  margin: 0.6em 0;
}
.c-article-references > li::before,
ul.ref-list > li::before,
ul.references.numeric-ordered-list > li::before,
.ref-list > ul > li::before,
.references > ul > li::before {
  content: counter(z2m-ref) ".";
  position: absolute;
  left: 0;
  width: 2.2em;
  text-align: right;
  color: #4b5563;
  font-weight: 600;
}
.off-screen, .sr-only, .visually-hidden, .u-visually-hidden, .usa-sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}
figure.ltx_table { overflow-x: auto; }
figure.ltx_table .ltx_transformed_outer {
  width: 100% !important;
  max-width: 100% !important;
  height: auto !important;
  vertical-align: baseline !important;
  overflow-x: auto;
}
figure.ltx_table .ltx_transformed_inner {
  display: block;
  transform: none !important;
}
figure.ltx_table table {
  width: auto;
  max-width: 100%;
  margin: 0 auto;
}
.ltx_align_center { text-align: center; }
.ltx_align_left { text-align: left; }
.ltx_align_right { text-align: right; }
#web-doc :target {
  outline: 3px solid #f59e0b;
  outline-offset: 4px;
  background: #fff7d6;
  border-radius: 4px;
  scroll-margin-top: 24px;
}
</style>"""


def detect_web_html_kind(html: str, *, source_url: str | None = None) -> WebHtmlKind:
    """Classify known web HTML attachments."""

    parsed_source = _urlsplit_or_none(source_url)
    if parsed_source is not None and _arxiv_abs_parts(parsed_source) is not None:
        return WebHtmlKind.ARXIV_ABS_PAGE

    sample = html[:500_000].lower()
    if _looks_like_arxiv_abs_page(sample):
        return WebHtmlKind.ARXIV_ABS_PAGE
    if _looks_like_sciendo_abstract_page(sample, parsed_source):
        return WebHtmlKind.SCIENDO_ABSTRACT_PAGE
    if _looks_like_ojs_abstract_page(sample, parsed_source):
        return WebHtmlKind.OJS_ABSTRACT_PAGE
    if _looks_like_arxiv_latexml(sample, parsed_source):
        return WebHtmlKind.ARXIV_LATEXML
    if _looks_like_pmc_article(sample, parsed_source):
        return WebHtmlKind.PMC_ARTICLE
    if _looks_like_taylor_francis_article(sample, parsed_source):
        return WebHtmlKind.TAYLOR_FRANCIS_ARTICLE
    if _looks_like_springer_nature_article(sample, parsed_source):
        return WebHtmlKind.SPRINGER_NATURE_ARTICLE
    if _looks_like_researchgate_page(sample, parsed_source):
        return WebHtmlKind.RESEARCHGATE_PAGE
    full_sample = html.lower()
    if full_sample != sample:
        if _looks_like_arxiv_abs_page(full_sample):
            return WebHtmlKind.ARXIV_ABS_PAGE
        if _looks_like_sciendo_abstract_page(full_sample, parsed_source):
            return WebHtmlKind.SCIENDO_ABSTRACT_PAGE
        if _looks_like_ojs_abstract_page(full_sample, parsed_source):
            return WebHtmlKind.OJS_ABSTRACT_PAGE
        if _looks_like_arxiv_latexml(full_sample, parsed_source):
            return WebHtmlKind.ARXIV_LATEXML
        if _looks_like_pmc_article(full_sample, parsed_source):
            return WebHtmlKind.PMC_ARTICLE
        if _looks_like_taylor_francis_article(full_sample, parsed_source):
            return WebHtmlKind.TAYLOR_FRANCIS_ARTICLE
        if _looks_like_springer_nature_article(full_sample, parsed_source):
            return WebHtmlKind.SPRINGER_NATURE_ARTICLE
        if _looks_like_researchgate_page(full_sample, parsed_source):
            return WebHtmlKind.RESEARCHGATE_PAGE
    if "<article" in sample:
        return WebHtmlKind.GENERIC_ARTICLE
    return WebHtmlKind.UNKNOWN


def require_web_article_html(html: str, *, source_url: str | None = None) -> WebHtmlKind:
    """Return the source kind, rejecting known landing pages."""

    kind = detect_web_html_kind(html, source_url=source_url)
    if kind == WebHtmlKind.ARXIV_ABS_PAGE:
        raise WebHtmlPolishError(
            "arXiv abstract pages are landing pages, not article HTML; use the /html/ attachment instead."
        )
    if kind == WebHtmlKind.RESEARCHGATE_PAGE:
        raise WebHtmlPolishError(
            "ResearchGate pages are landing/PDF pages, not stable article HTML; use the PDF attachment when available."
        )
    if kind == WebHtmlKind.SCIENDO_ABSTRACT_PAGE:
        raise WebHtmlPolishError(
            "Sciendo/Reference Global abstract-tab pages are not full article HTML; fetch the ?tab=article URL first."
        )
    if kind == WebHtmlKind.OJS_ABSTRACT_PAGE:
        raise WebHtmlPolishError(
            "OJS article pages with only abstract/galley links are not full article HTML; use the PDF galley when available."
        )
    return kind


def polish_web_html_document(
    html: str,
    *,
    source_url: str | None = None,
    canonical_url: str | None = None,
) -> WebHtmlPolishResult:
    """Normalize a web-native article HTML document.

    This keeps web-native sources separate from the Marker/PDF repair path:
    strip executable payloads, extract the article-like fragment, canonicalize
    same-document links, and wrap the result in a stable readable shell.
    """

    kind = require_web_article_html(html, source_url=source_url)
    title = _document_title(html)
    extraction = extract_web_article_fragment(html, kind=kind)
    normalized_html = normalize_web_article_fragment(
        extraction.html,
        kind=kind,
        source_url=source_url,
        canonical_url=canonical_url,
    )
    declared_urls = _declared_document_urls(html)
    inferred_canonical_url = canonical_url or (declared_urls[0] if declared_urls else None)
    canonicalized = canonicalize_same_document_links(
        normalized_html,
        source_url=source_url,
        canonical_url=inferred_canonical_url,
    )
    article_html = absolutize_root_relative_urls(
        canonicalized.html,
        base_url=_root_relative_url_base(
            kind=kind,
            canonical_url=inferred_canonical_url,
            source_url=source_url,
        ),
    )
    wrapped = _wrap_web_article_html(
        article_html,
        kind=kind,
        title=title,
        article_selector=extraction.selector,
    )
    return WebHtmlPolishResult(
        html=wrapped,
        kind=kind,
        article_extracted=extraction.extracted,
        article_selector=extraction.selector,
        same_document_links_rewritten=canonicalized.rewritten_count,
        unresolved_same_document_links=canonicalized.unresolved_count,
    )


def polish_web_html_file(
    html_path: Path,
    *,
    source_url: str | None = None,
    canonical_url: str | None = None,
) -> WebHtmlFilePolishResult:
    """Polish a web-native HTML file and inline local sidecar images."""

    html = html_path.read_text(encoding="utf-8", errors="replace")
    document = polish_web_html_document(
        html,
        source_url=source_url,
        canonical_url=canonical_url,
    )
    inlined = inline_local_images_from_web_html_document(document.html, base_dir=html_path.parent)
    return WebHtmlFilePolishResult(
        html=inlined.html,
        kind=document.kind,
        article_extracted=document.article_extracted,
        article_selector=document.article_selector,
        same_document_links_rewritten=document.same_document_links_rewritten,
        unresolved_same_document_links=document.unresolved_same_document_links,
        inlined_images=inlined.inlined_images,
    )


def inline_local_images_from_web_html_document(html: str, *, base_dir: Path) -> InlineHtmlResult:
    """Inline local ``<img src>`` and ``srcset`` references without Marker polish."""

    base_dir = base_dir.resolve(strict=False)
    inlined_count = 0

    def inline_src_value(src_value: str) -> str | None:
        nonlocal inlined_count
        if not src_value or _is_nonlocal_image_src(src_value):
            return None

        candidate = _resolve_local_asset(src_value, base_dir=base_dir)
        if candidate is None:
            return None

        data_url = to_data_url(candidate, detect_by_signature=True, log_func=None)
        if data_url is None or not validate_data_url(data_url, candidate):
            return None

        inlined_count += 1
        return data_url

    def replace_src(match: re.Match[str]) -> str:
        nonlocal inlined_count
        prefix = match.group("prefix")
        quote = match.group("quote")
        src_value = unescape(match.group("src")).strip()
        data_url = inline_src_value(src_value)
        if data_url is None:
            return match.group(0)

        prefix = _add_src_hint(prefix, src_value)
        return f"{prefix}{quote}{data_url}{quote}"

    def replace_srcset(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        quote = match.group("quote")
        srcset = unescape(match.group("srcset")).strip()
        next_entries: list[str] = []
        changed = False
        for raw_entry in srcset.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            parts = entry.split()
            src_value = parts[0]
            descriptor = " ".join(parts[1:])
            data_url = inline_src_value(src_value)
            if data_url is None:
                next_entries.append(entry)
                continue
            changed = True
            next_entries.append(f"{data_url} {descriptor}".strip())
        if not changed:
            return match.group(0)
        escaped_srcset = html_escape(", ".join(next_entries), quote=True)
        return f"{prefix}{quote}{escaped_srcset}{quote}"

    html = _IMG_SRC_RE.sub(replace_src, html)
    html = _SRCSET_RE.sub(replace_srcset, html)
    return InlineHtmlResult(html=html, inlined_images=inlined_count)


def absolutize_root_relative_urls(html: str, *, base_url: str | None) -> str:
    """Rewrite ``/...`` publisher links so local ``file://`` viewing does not hijack them."""

    parsed_base = _urlsplit_or_none(base_url)
    if parsed_base is None or not parsed_base.scheme or not parsed_base.netloc:
        return html

    origin = urllib.parse.urlunsplit((parsed_base.scheme, parsed_base.netloc, "/", "", ""))

    def absolute_url(raw_url: str) -> str | None:
        value = unescape(raw_url).strip()
        if not _is_root_relative_url(value):
            return None
        return urllib.parse.urljoin(origin, value)

    def replace_attr(match: re.Match[str]) -> str:
        rewritten = absolute_url(match.group("url"))
        if rewritten is None:
            return match.group(0)
        quote = match.group("quote")
        return f"{match.group('prefix')}{quote}{html_escape(rewritten, quote=True)}{quote}"

    def replace_srcset(match: re.Match[str]) -> str:
        changed = False
        entries: list[str] = []
        for raw_entry in match.group("srcset").split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            parts = entry.split()
            rewritten = absolute_url(parts[0])
            if rewritten is None:
                entries.append(entry)
                continue
            changed = True
            descriptor = " ".join(parts[1:])
            entries.append(f"{rewritten} {descriptor}".strip())
        if not changed:
            return match.group(0)
        quote = match.group("quote")
        return f"{match.group('prefix')}{quote}{html_escape(', '.join(entries), quote=True)}{quote}"

    html = _ROOT_RELATIVE_URL_ATTR_RE.sub(replace_attr, html)
    html = _SRCSET_RE.sub(replace_srcset, html)
    return html


def _root_relative_url_base(
    *,
    kind: WebHtmlKind,
    canonical_url: str | None,
    source_url: str | None,
) -> str | None:
    for raw_url in (canonical_url, source_url):
        parsed = _urlsplit_or_none(raw_url)
        if parsed is not None and parsed.scheme and parsed.netloc and not _is_doi_host(parsed.netloc):
            return raw_url
    return _publisher_default_origin(kind)


def _publisher_default_origin(kind: WebHtmlKind) -> str | None:
    if kind == WebHtmlKind.ARXIV_LATEXML:
        return "https://arxiv.org/"
    if kind == WebHtmlKind.PMC_ARTICLE:
        return "https://pmc.ncbi.nlm.nih.gov/"
    if kind == WebHtmlKind.TAYLOR_FRANCIS_ARTICLE:
        return "https://www.tandfonline.com/"
    if kind == WebHtmlKind.SPRINGER_NATURE_ARTICLE:
        return "https://link.springer.com/"
    return None


def _is_doi_host(host: str) -> bool:
    normalized = host.lower().split(":", 1)[0]
    return normalized in {"doi.org", "dx.doi.org", "www.doi.org"}


def extract_web_article_fragment(html: str, *, kind: WebHtmlKind | None = None) -> WebArticleExtraction:
    """Extract the central article-like fragment from third-party web HTML."""

    source_specific = _extract_source_specific_article_fragment(html, kind=kind)
    if source_specific is not None:
        return source_specific
    return extract_generic_web_article_fragment(html, kind=kind)


def extract_generic_web_article_fragment(html: str, *, kind: WebHtmlKind | None = None) -> WebArticleExtraction:
    """Extract an article-like fragment without publisher-specific rules."""

    cleaned = _strip_non_article_payloads(html)
    candidates: list[_ArticleCandidate] = []
    for match in _ARTICLE_START_RE.finditer(cleaned):
        tag = match.group("tag")
        attrs = match.group("attrs")
        if not _promising_article_start(tag, attrs, kind=kind):
            continue
        fragment = _balanced_element_from_match(cleaned, match)
        if fragment is None:
            continue
        candidate = _score_article_candidate(fragment, tag, attrs, kind=kind)
        if candidate is not None:
            candidates.append(candidate)

    if candidates:
        best = max(candidates, key=lambda candidate: (candidate.score, candidate.text_length))
        if best.score >= 1_500 and best.text_length >= 1_000:
            return WebArticleExtraction(
                html=best.html.strip(),
                extracted=True,
                selector=best.selector,
                text_length=best.text_length,
            )

    body = _body_inner(cleaned) or cleaned
    text_length = _visible_text_length(body)
    return WebArticleExtraction(
        html=body.strip(),
        extracted=False,
        selector="body" if body != cleaned else None,
        text_length=text_length,
    )


def normalize_web_article_fragment(
    html: str,
    *,
    kind: WebHtmlKind,
    source_url: str | None = None,
    canonical_url: str | None = None,
) -> str:
    """Apply publisher-specific static normalizations after extraction."""

    if kind == WebHtmlKind.ARXIV_LATEXML:
        from .web_polish import arxiv  # pylint: disable=import-outside-toplevel

        return arxiv.normalize_article_fragment(html, source_url=source_url, canonical_url=canonical_url)
    if kind == WebHtmlKind.PMC_ARTICLE:
        from .web_polish import pmc  # pylint: disable=import-outside-toplevel

        return pmc.normalize_article_fragment(html, source_url=source_url, canonical_url=canonical_url)
    if kind == WebHtmlKind.TAYLOR_FRANCIS_ARTICLE:
        from .web_polish import taylor_francis  # pylint: disable=import-outside-toplevel

        return taylor_francis.normalize_article_fragment(html, source_url=source_url, canonical_url=canonical_url)
    if kind == WebHtmlKind.SPRINGER_NATURE_ARTICLE:
        from .web_polish import springer_nature  # pylint: disable=import-outside-toplevel

        return springer_nature.normalize_article_fragment(html, source_url=source_url, canonical_url=canonical_url)
    return html


def _extract_source_specific_article_fragment(
    html: str,
    *,
    kind: WebHtmlKind | None,
) -> WebArticleExtraction | None:
    if kind == WebHtmlKind.ARXIV_LATEXML:
        from .web_polish import arxiv  # pylint: disable=import-outside-toplevel

        return arxiv.extract_article_fragment(html)
    if kind == WebHtmlKind.PMC_ARTICLE:
        from .web_polish import pmc  # pylint: disable=import-outside-toplevel

        return pmc.extract_article_fragment(html)
    if kind == WebHtmlKind.TAYLOR_FRANCIS_ARTICLE:
        from .web_polish import taylor_francis  # pylint: disable=import-outside-toplevel

        return taylor_francis.extract_article_fragment(html)
    if kind == WebHtmlKind.SPRINGER_NATURE_ARTICLE:
        from .web_polish import springer_nature  # pylint: disable=import-outside-toplevel

        return springer_nature.extract_article_fragment(html)
    return None


def _extract_fragment_by_attr_tokens(
    html: str,
    *,
    kind: WebHtmlKind,
    token_selectors: tuple[tuple[str, str], ...],
    min_text_length: int = 500,
) -> WebArticleExtraction | None:
    """Extract the best balanced element whose opening attrs match known tokens."""

    cleaned = _strip_non_article_payloads(html)
    candidates: list[_ArticleCandidate] = []
    for token, selector in token_selectors:
        token_lower = token.lower()
        for match in _ARTICLE_START_RE.finditer(cleaned):
            tag = match.group("tag")
            attrs = match.group("attrs")
            attrs_lower = unescape(attrs).lower()
            if token_lower not in attrs_lower:
                continue
            fragment = _balanced_element_from_match(cleaned, match)
            if fragment is None:
                continue
            candidate = _score_article_candidate(fragment, tag, attrs, kind=kind)
            if candidate is None:
                continue
            candidates.append(
                _ArticleCandidate(
                    html=candidate.html,
                    tag=candidate.tag,
                    attrs=candidate.attrs,
                    score=candidate.score + 50_000 - len(candidates),
                    selector=selector,
                    text_length=candidate.text_length,
                )
            )

    if not candidates:
        return None
    best = max(candidates, key=lambda candidate: (candidate.score, candidate.text_length))
    if best.text_length < min_text_length:
        return None
    return WebArticleExtraction(
        html=best.html.strip(),
        extracted=True,
        selector=best.selector,
        text_length=best.text_length,
    )


def _remove_elements_by_attr_tokens(
    html: str,
    tokens: tuple[str, ...],
    *,
    tags: tuple[str, ...] = ("aside", "div", "footer", "header", "nav", "section"),
) -> str:
    """Remove balanced elements whose opening tag attributes contain any token."""

    lowered_tokens = tuple(token.lower() for token in tokens)
    allowed_tags = {tag.lower() for tag in tags}
    previous = None
    cleaned = html
    while previous != cleaned:
        previous = cleaned
        for match in list(_HTML_TAG_RE.finditer(cleaned)):
            tag = match.group("tag").lower()
            if tag not in allowed_tags or match.group(0).startswith("</"):
                continue
            attrs = unescape(match.group("attrs") or "").lower()
            if not any(token in attrs for token in lowered_tokens):
                continue
            fragment = _balanced_element_from_match(cleaned, match)
            if fragment is None:
                continue
            cleaned = cleaned[: match.start()] + " " + cleaned[match.start() + len(fragment) :]
            break
    return cleaned


def _attr_value(attrs: str, name: str) -> str | None:
    match = re.search(
        rf"(?<![\w:-]){re.escape(name)}\s*=\s*(['\"])(?P<value>.*?)\1",
        attrs,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    return unescape(match.group("value")).strip()


def _set_attr_value(open_tag: str, name: str, value: str) -> str:
    escaped_value = html_escape(value, quote=True)
    attr_re = re.compile(
        rf"(?P<prefix>(?<![\w:-]){re.escape(name)}\s*=\s*)(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
        re.IGNORECASE | re.DOTALL,
    )
    if attr_re.search(open_tag):
        return attr_re.sub(
            lambda match: f"{match.group('prefix')}{match.group('quote')}{escaped_value}{match.group('quote')}",
            open_tag,
            count=1,
        )
    return re.sub(r">\s*$", f' {name}="{escaped_value}">', open_tag, count=1)


def _looks_like_arxiv_abs_page(sample: str) -> bool:
    return (
        'name="citation_arxiv_id"' in sample
        and ("html (experimental)" in sample or "latexml-download-link" in sample)
        and ("abs-button" in sample or "extra-services" in sample)
    )


def _looks_like_arxiv_latexml(
    sample: str,
    parsed_source: urllib.parse.SplitResult | None,
) -> bool:
    if "ltx_page_main" not in sample:
        return False
    if "generated" in sample and "latexml" in sample:
        return True
    if "ltx_bibliography" in sample or "ltx_title_document" in sample:
        return True
    return parsed_source is not None and _arxiv_html_parts(parsed_source) is not None


def _looks_like_pmc_article(sample: str, parsed_source: urllib.parse.SplitResult | None) -> bool:
    host = (parsed_source.netloc.lower() if parsed_source is not None else "")
    if host in {"pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov"}:
        return True
    return "pmc-article" in sample or 'id="main-content"' in sample and "pmc" in sample


def _looks_like_taylor_francis_article(sample: str, parsed_source: urllib.parse.SplitResult | None) -> bool:
    host = (parsed_source.netloc.lower() if parsed_source is not None else "")
    if host.endswith("tandfonline.com"):
        return True
    return "hlfld-fulltext" in sample or "nlm_article" in sample


def _looks_like_springer_nature_article(sample: str, parsed_source: urllib.parse.SplitResult | None) -> bool:
    host = (parsed_source.netloc.lower() if parsed_source is not None else "")
    if host in {"link.springer.com", "www.nature.com"}:
        return True
    return "c-article-body" in sample or "article__body" in sample


def _looks_like_researchgate_page(sample: str, parsed_source: urllib.parse.SplitResult | None) -> bool:
    host = (parsed_source.netloc.lower() if parsed_source is not None else "")
    if host.endswith("researchgate.net"):
        return True
    return (
        "www.researchgate.net" in sample
        or "lite.publicationdetails" in sample
        or "research-detail-header-section" in sample
        or ("download full-text pdf" in sample and "researchgate" in sample)
    )


def _looks_like_sciendo_abstract_page(
    sample: str,
    parsed_source: urllib.parse.SplitResult | None,
) -> bool:
    host = (parsed_source.netloc.lower() if parsed_source is not None else "")
    if host not in {"content.sciendo.com", "reference-global.com", "www.reference-global.com"} and not (
        "content.sciendo.com" in sample or "reference-global.com" in sample
    ):
        return False
    return (
        "content-tabs" in sample
        and "tab-button-article" in sample
        and ("abstract-content" in sample or "self.__next_f.push" in sample)
    )


def _looks_like_ojs_abstract_page(
    sample: str,
    parsed_source: urllib.parse.SplitResult | None,
) -> bool:
    host = (parsed_source.netloc.lower() if parsed_source is not None else "")
    if not (
        host.endswith("almclinmed.ru")
        or "almclinmed.ru" in sample
        or "open journal systems" in sample
        or "pkp" in sample
    ):
        return False
    if 'id="articlefulltext"' not in sample or 'id="articleabstract"' not in sample:
        return False
    return "citation_pdf_url" in sample or "/article/download/" in sample or "class=\"file\"" in sample


def _strip_non_article_payloads(html: str) -> str:
    cleaned = _COMMENT_RE.sub(" ", html)
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = _NON_ARTICLE_BLOCK_RE.sub(" ", cleaned)
    return cleaned


def _document_title(html: str) -> str:
    match = _TITLE_RE.search(html)
    if match is None:
        return "Web Article"
    title = _visible_text(match.group("title"))
    return title or "Web Article"


def _body_inner(html: str) -> str | None:
    match = _BODY_RE.search(html)
    if match is None:
        return None
    return match.group("body")


def _balanced_element_from_match(html: str, start_match: re.Match[str]) -> str | None:
    tag = start_match.group("tag").lower()
    depth = 0
    for match in _HTML_TAG_RE.finditer(html, start_match.start()):
        token_tag = match.group("tag").lower()
        if token_tag != tag:
            continue
        raw = match.group(0)
        if raw.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[start_match.start() : match.end()]
            continue
        if raw.endswith("/>") or token_tag in _VOID_TAGS:
            continue
        depth += 1
    return None


def _score_article_candidate(
    fragment: str,
    tag: str,
    attrs: str,
    *,
    kind: WebHtmlKind | None,
) -> _ArticleCandidate | None:
    text_length = _visible_text_length(fragment)
    if text_length < 500:
        return None

    tag = tag.lower()
    attrs_lower = unescape(attrs).lower()
    fragment_probe = fragment[:300_000].lower()
    score = min(text_length // 75, 3_000)
    selector = tag

    if "ltx_page_main" in attrs_lower:
        score += 8_000
        selector = ".ltx_page_main"
    if "pmc-article" in attrs_lower:
        score += 7_000
        selector = ".pmc-article"
    if "nlm_article" in attrs_lower:
        score += 6_500
        selector = ".NLM_article"
    if "c-article-body" in attrs_lower:
        score += 5_800
        selector = ".c-article-body"
    elif "article__body" in attrs_lower or "article-body" in attrs_lower:
        score += 5_500
        selector = ".article-body"
    if "article-content" in attrs_lower or "article__content" in attrs_lower:
        score += 5_000
        selector = ".article-content"
    if "hlfld-fulltext" in attrs_lower:
        score += 3_200
        selector = ".hlFld-Fulltext"
    if 'id="main-content"' in attrs_lower or "'main-content'" in attrs_lower:
        score += 3_000
        selector = "#main-content"

    if tag == "article":
        score += 3_000
        selector = "article" if selector == tag else selector
    elif tag == "main":
        score += 1_800
        selector = "main" if selector == tag else selector

    if tag == "article" and "pmc-article" in fragment_probe:
        score += 3_000
        selector = "article .pmc-article"
    if tag == "article" and "c-article-body" in fragment_probe:
        score += 2_500
        selector = "article .c-article-body"
    if tag == "article" and "nlm_article" in fragment_probe:
        score += 2_500
        selector = "article .NLM_article"
    if "ltx_bibliography" in fragment_probe or "references" in fragment_probe or "bibliography" in fragment_probe:
        score += 600

    if "abstract" in attrs_lower and "fulltext" not in attrs_lower and text_length < 8_000:
        score -= 2_500
    if any(word in attrs_lower for word in ("navbar", "navigation", "footer", "header", "sidebar", "cookie")):
        score -= 3_000

    if kind == WebHtmlKind.ARXIV_LATEXML and "ltx_page_main" not in attrs_lower:
        score -= 1_000
    if kind == WebHtmlKind.RESEARCHGATE_PAGE and text_length < 12_000:
        score -= 1_500

    return _ArticleCandidate(
        html=fragment,
        tag=tag,
        attrs=attrs,
        score=score,
        selector=selector,
        text_length=text_length,
    )


def _promising_article_start(tag: str, attrs: str, *, kind: WebHtmlKind | None) -> bool:
    tag = tag.lower()
    if tag in {"article", "main"}:
        return True

    attrs_lower = unescape(attrs).lower()
    if not attrs_lower:
        return False

    strong_tokens = (
        "ltx_page_main",
        "pmc-article",
        "nlm_article",
        "c-article-body",
        "article__body",
        "article-body",
        "article__content",
        "article-content",
        "hlfld-fulltext",
        "main-content",
        "fulltext-view",
        "article-section",
    )
    if any(token in attrs_lower for token in strong_tokens):
        return True

    if kind == WebHtmlKind.ARXIV_LATEXML and "ltx_" in attrs_lower:
        return True
    if tag == "section" and "jats" in attrs_lower and "article" in attrs_lower:
        return True
    return False


def _visible_text_length(html: str) -> int:
    return len(_visible_text(html))


def _visible_text(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    return " ".join(unescape(text).split())


def _wrap_web_article_html(
    article_html: str,
    *,
    kind: WebHtmlKind,
    title: str,
    article_selector: str | None,
) -> str:
    escaped_title = html_escape(title, quote=False)
    escaped_kind = html_escape(kind.value, quote=True)
    selector_attr = ""
    if article_selector:
        selector_attr = f' data-z2m-article-selector="{html_escape(article_selector, quote=True)}"'
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{escaped_title}</title>\n"
        f"{_WEB_READABILITY_STYLE}\n"
        "</head>\n"
        "<body>\n"
        f'<main id="web-doc" data-z2m-source-kind="{escaped_kind}"{selector_attr}>\n'
        f"{article_html}\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def _is_nonlocal_image_src(src_value: str) -> bool:
    lowered = src_value.lower()
    return lowered.startswith("file:") or is_inline_or_remote(src_value)


def _resolve_local_asset(src_value: str, *, base_dir: Path) -> Path | None:
    clean_src = src_value.split("?", 1)[0].split("#", 1)[0]
    decoded = urllib.parse.unquote(clean_src)
    if not decoded:
        return None
    raw_path = Path(decoded)
    if raw_path.is_absolute():
        return None
    candidate = (base_dir / raw_path).resolve(strict=False)
    try:
        candidate.relative_to(base_dir)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _add_src_hint(prefix: str, hint_path: str) -> str:
    if re.search(r"\bdata-z2m-src\s*=", prefix, re.IGNORECASE):
        return prefix
    escaped_hint = html_escape(hint_path, quote=True)
    return re.sub(
        r"\bsrc\s*=\s*$",
        f'data-z2m-src="{escaped_hint}" src=',
        prefix,
        flags=re.IGNORECASE,
    )
