import pytest

from zoteropdf2md.web_html_polish import (
    WebHtmlKind,
    WebHtmlPolishError,
    canonicalize_same_document_links,
    count_same_document_absolute_fragment_links,
    detect_web_html_kind,
    polish_web_html_file,
    polish_web_html_document,
)


KOSMOS_LIKE_HTML = """
<!doctype html>
<html>
<head>
  <!-- Generated on arXiv by LaTeXML -->
  <title>1 Introduction</title>
</head>
<body>
  <div class="ltx_page_main">
    <section id="S1">
      <h2 class="ltx_title ltx_title_section">Introduction</h2>
      <p class="ltx_p">
        See <a class="ltx_ref" href="https://arxiv.org/html/2511.02824v2#S1">Section 1</a>
        and cite
        <cite class="ltx_cite">[<a class="ltx_ref" href="https://arxiv.org/html/2511.02824v2#bib.bib56">56</a>]</cite>.
        Code is at <a class="ltx_ref ltx_href" href="https://github.com/EdisonScientific/kosmos-figures">GitHub</a>.
        Reports are at <a class="ltx_ref" href="https://platform.edisonscientific.com/trajectories/example">Edison</a>.
      </p>
    </section>
    <section class="ltx_bibliography" id="bib">
      <ol><li id="bib.bib56">MendelianRandomization R package.</li></ol>
    </section>
  </div>
</body>
</html>
"""

LONG_PARAGRAPH = (
    "This article paragraph contains enough scientific prose to exercise the "
    "article extractor without falling back to the whole body. "
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nz2m-test-image"


def test_detect_web_html_kind_distinguishes_arxiv_latexml_from_abs_page() -> None:
    abs_html = """
    <html><head><meta name="citation_arxiv_id" content="2511.02824"></head>
    <body><div class="extra-services"><a class="abs-button" id="latexml-download-link"
    href="https://arxiv.org/html/2511.02824v2">HTML (experimental)</a></div></body></html>
    """

    assert detect_web_html_kind(KOSMOS_LIKE_HTML) == WebHtmlKind.ARXIV_LATEXML
    assert detect_web_html_kind(abs_html) == WebHtmlKind.ARXIV_ABS_PAGE
    assert (
        detect_web_html_kind("<html></html>", source_url="https://arxiv.org/abs/2511.02824")
        == WebHtmlKind.ARXIV_ABS_PAGE
    )


def test_polish_web_html_document_rejects_arxiv_abs_page() -> None:
    abs_html = """
    <html><head><meta name="citation_arxiv_id" content="2511.02824"></head>
    <body><a class="abs-button" href="https://arxiv.org/html/2511.02824v2">HTML (experimental)</a></body></html>
    """

    with pytest.raises(WebHtmlPolishError):
        polish_web_html_document(abs_html, source_url="https://arxiv.org/abs/2511.02824")


def test_canonicalize_same_document_links_rewrites_only_self_fragments() -> None:
    result = canonicalize_same_document_links(
        KOSMOS_LIKE_HTML,
        source_url="https://arxiv.org/html/2511.02824v2",
    )

    assert result.rewritten_count == 2
    assert result.unresolved_count == 0
    assert 'href="#S1"' in result.html
    assert 'href="#bib.bib56"' in result.html
    assert 'href="https://github.com/EdisonScientific/kosmos-figures"' in result.html
    assert 'href="https://platform.edisonscientific.com/trajectories/example"' in result.html
    assert count_same_document_absolute_fragment_links(
        result.html,
        source_url="https://arxiv.org/html/2511.02824v2",
    ) == 0


def test_canonicalize_same_document_links_allows_versionless_arxiv_source_url() -> None:
    result = canonicalize_same_document_links(
        KOSMOS_LIKE_HTML,
        source_url="https://arxiv.org/html/2511.02824",
    )

    assert result.rewritten_count == 2
    assert 'href="#S1"' in result.html
    assert 'href="#bib.bib56"' in result.html


def test_canonicalize_same_document_links_preserves_unresolved_self_fragments() -> None:
    html = (
        '<html><body><section id="S1"></section>'
        '<a href="https://arxiv.org/html/2511.02824v2#missing">missing</a>'
        "</body></html>"
    )

    result = canonicalize_same_document_links(
        html,
        source_url="https://arxiv.org/html/2511.02824v2",
    )

    assert result.rewritten_count == 0
    assert result.unresolved_count == 1
    assert 'href="https://arxiv.org/html/2511.02824v2#missing"' in result.html


def test_polish_web_html_document_extracts_arxiv_latexml_article() -> None:
    html = f"""
    <html>
      <head><title>Kosmos</title></head>
      <body>
        <header>site chrome should disappear</header>
        <script>self.__next_f.push(["not article"])</script>
        <div class="ltx_page_main">
          <section id="S1">
            <h1 class="ltx_title_document">Kosmos</h1>
            <p>{" ".join([LONG_PARAGRAPH] * 18)}</p>
            <a href="https://arxiv.org/html/2511.02824v2#S1">Section</a>
          </section>
          <section class="ltx_bibliography" id="bib">
            <ol><li id="bib.bib1">Reference</li></ol>
          </section>
        </div>
        <footer>publisher footer should disappear</footer>
      </body>
    </html>
    """

    result = polish_web_html_document(html, source_url="https://arxiv.org/html/2511.02824v2")

    assert result.kind == WebHtmlKind.ARXIV_LATEXML
    assert result.article_extracted is True
    assert result.article_selector == ".ltx_page_main"
    assert 'data-z2m-source-kind="arxiv_latexml"' in result.html
    assert "site chrome should disappear" not in result.html
    assert "publisher footer should disappear" not in result.html
    assert "self.__next_f.push" not in result.html
    assert 'href="#S1"' in result.html


def test_polish_web_html_document_extracts_pmc_article() -> None:
    html = f"""
    <html>
      <head><title>PMC Article</title></head>
      <body>
        <nav>PMC navigation</nav>
        <main id="main-content">
          <article class="pmc-article" id="article">
            <h1>Comparison of methods</h1>
            <section id="sec1"><p>{" ".join([LONG_PARAGRAPH] * 20)}</p></section>
            <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC8911527/#sec1">same document</a>
            <a href="https://example.org/outside">outside</a>
          </article>
        </main>
      </body>
    </html>
    """

    result = polish_web_html_document(html, source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC8911527/")

    assert result.kind == WebHtmlKind.PMC_ARTICLE
    assert result.article_extracted is True
    assert result.article_selector in {"article .pmc-article", ".pmc-article"}
    assert "PMC navigation" not in result.html
    assert 'href="#sec1"' in result.html
    assert 'href="https://example.org/outside"' in result.html


def test_polish_web_html_document_extracts_taylor_francis_nlm_fulltext() -> None:
    html = f"""
    <html>
      <head><title>Taylor Article</title></head>
      <body>
        <div class="topbar">Taylor navigation</div>
        <article class="NLM_article">
          <div id="abstractId1" class="hlFld-Abstract"><p>{" ".join([LONG_PARAGRAPH] * 8)}</p></div>
          <div class="hlFld-Fulltext">
            <div class="NLM_sec" id="S0001"><h2>Methods</h2><p>{" ".join([LONG_PARAGRAPH] * 20)}</p></div>
            <a href="https://www.tandfonline.com/doi/full/10.1080/example#S0001">back</a>
          </div>
        </article>
      </body>
    </html>
    """

    result = polish_web_html_document(
        html,
        source_url="https://www.tandfonline.com/doi/full/10.1080/example",
    )

    assert result.kind == WebHtmlKind.TAYLOR_FRANCIS_ARTICLE
    assert result.article_extracted is True
    assert result.article_selector == "article .NLM_article"
    assert "Taylor navigation" not in result.html
    assert 'href="#S0001"' in result.html


def test_polish_web_html_document_extracts_springer_nature_body() -> None:
    html = f"""
    <html>
      <head><title>Springer Article</title></head>
      <body>
        <aside>related articles</aside>
        <article>
          <div class="c-article-body" id="body">
            <h2 id="Sec1">Introduction</h2>
            <p>{" ".join([LONG_PARAGRAPH] * 22)}</p>
          </div>
        </article>
      </body>
    </html>
    """

    result = polish_web_html_document(html, source_url="https://link.springer.com/article/10.1007/example")

    assert result.kind == WebHtmlKind.SPRINGER_NATURE_ARTICLE
    assert result.article_extracted is True
    assert result.article_selector in {"article .c-article-body", ".c-article-body"}
    assert "related articles" not in result.html


def test_polish_web_html_file_inlines_local_images_without_marker_polish(tmp_path) -> None:
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(PNG_BYTES)
    html_path = tmp_path / "article.html"
    html_path.write_text(
        f"""
        <html><body>
          <article>
            <h1>Article</h1>
            <p>{" ".join([LONG_PARAGRAPH] * 20)}</p>
            <img src="figure.png?download=1" alt="Figure">
          </article>
        </body></html>
        """,
        encoding="utf-8",
    )

    result = polish_web_html_file(html_path)

    assert result.inlined_images == 1
    assert 'data-z2m-src="figure.png?download=1"' in result.html
    assert 'src="data:image/png;base64,' in result.html


def test_generic_canonicalizer_infers_repeated_non_arxiv_self_links() -> None:
    html = """
    <html><body>
      <article>
        <section id="sec1"></section>
        <section id="sec2"></section>
        <a href="https://example.org/article#sec1">one</a>
        <a href="https://example.org/article#sec2">two</a>
      </article>
    </body></html>
    """

    result = canonicalize_same_document_links(html)

    assert result.rewritten_count == 2
    assert 'href="#sec1"' in result.html
    assert 'href="#sec2"' in result.html
