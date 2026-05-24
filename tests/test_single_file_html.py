import base64
import re
import shutil
from pathlib import Path
from uuid import uuid4

from zoteropdf2md.single_file_html import (
    _add_figure_anchors,
    _add_section_anchors,
    _fix_orphaned_sup_tags,
    _fix_subscript_equation_spill,
    _link_figure_refs,
    _link_section_refs,
    _repair_sentence_breaks_around_float_units,
    _to_data_url,
    _validate_data_url,
    close_katex_v8_context,
    inline_images_from_html_file,
    polish_html_document,
)


def _make_temp_dir() -> Path:
    path = Path(".tmp_local2") / f"test_single_file_html_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


_VALID_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _valid_tiny_png_bytes() -> bytes:
    return base64.b64decode(_VALID_TINY_PNG_B64)


def _valid_tiny_png_data_url() -> str:
    return f"data:image/png;base64,{_VALID_TINY_PNG_B64}"


def test_inline_images_from_html_file() -> None:
    tmp_path = _make_temp_dir()
    try:
        html_path = tmp_path / "doc.html"
        image_path = tmp_path / "img.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        html_path.write_text('<html><body><img src="img.png"></body></html>', encoding="utf-8")

        result = inline_images_from_html_file(html_path)

        assert result.inlined_images == 1
        assert "data:image/png;base64," in result.html
        assert re.search(r'\s+src=(["\'])img\.png\1', result.html) is None
        assert 'data-z2m-src="img.png"' in result.html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_inline_images_refreshes_existing_data_uri_from_sidecar_hint() -> None:
    tmp_path = _make_temp_dir()
    try:
        html_path = tmp_path / "doc.html"
        image_path = tmp_path / "img.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nfresh")
        html_path.write_text(
            '<html><body><img data-z2m-src="img.png" src="data:image/png;base64,AAAA"></body></html>',
            encoding="utf-8",
        )

        result = inline_images_from_html_file(html_path)

        assert result.inlined_images == 1
        assert "data:image/png;base64,AAAA" not in result.html
        assert "data:image/png;base64," in result.html
        assert 'data-z2m-src="img.png"' in result.html
        src_match = re.search(r"<img[^>]*\ssrc=(['\"])(.*?)\1", result.html, flags=re.IGNORECASE)
        assert src_match is not None
        src_value = src_match.group(2)
        assert src_value.startswith("data:image/png;base64,")
        payload = src_value.split(",", 1)[1]
        assert base64.b64decode(payload) == image_path.read_bytes()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_inline_images_repairs_broken_data_uri_from_sidecar_before_missing_warning() -> None:
    tmp_path = _make_temp_dir()
    try:
        valid_png = _valid_tiny_png_bytes()
        broken_png = base64.b64encode(b"\x89PNG\r\n\x1a\ntruncated").decode("ascii").rstrip("=")
        html_path = tmp_path / "doc.html"
        image_path = tmp_path / "fig5.png"
        image_path.write_bytes(valid_png)
        html_path.write_text(
            "<html><body>"
            f'<p id="fig-5"><img data-z2m-src="fig5.png" src="data:image/png;base64,{broken_png}"/></p>'
            "<p>Figure 5. Caption should keep the repaired sidecar image.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = inline_images_from_html_file(html_path)

        assert result.inlined_images == 1
        assert '<p class="z2m-missing-figure-warning"' not in result.html
        assert re.search(r"<[^>]+class=(['\"])[^'\"]*z2m-missing-figure-unit", result.html) is None
        assert broken_png not in result.html
        src_match = re.search(r"<img[^>]*\ssrc=(['\"])(.*?)\1", result.html, flags=re.IGNORECASE)
        assert src_match is not None
        src_value = src_match.group(2)
        assert src_value.startswith("data:image/png;base64,")
        payload = src_value.split(",", 1)[1]
        assert base64.b64decode(payload) == valid_png
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_polish_html_document_restores_broken_data_image_from_cache_before_missing_warning() -> None:
    broken_png = base64.b64encode(b"\x89PNG\r\n\x1a\ntruncated").decode("ascii").rstrip("=")
    valid_data_url = _valid_tiny_png_data_url()
    html = (
        "<html><body>"
        f'<p id="fig-5"><img data-z2m-image-key="fig-5-0" src="data:image/png;base64,{broken_png}"/></p>'
        "<p>Figure 5. Caption should keep the cached image.</p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        image_cache={"fig-5-0": valid_data_url},
    )

    assert '<p class="z2m-missing-figure-warning"' not in polished
    assert "z2m-missing-figure-unit" not in polished
    assert broken_png not in polished
    assert valid_data_url in polished
    assert '<p class="z2m-figure-caption">Figure 5. Caption should keep the cached image.</p>' in polished


def test_inline_images_polish_uses_en_mode_for_non_ru_html() -> None:
    tmp_path = _make_temp_dir()
    try:
        html_path = tmp_path / "doc.html"
        html_path.write_text(
            "<html><body><p>TABLE I PARAMETERS FOR TWO ANTENNAS</p></body></html>",
            encoding="utf-8",
        )

        result = inline_images_from_html_file(html_path)
        assert "TABLE I." in result.html
        assert "Таблица I." not in result.html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_inline_images_polish_detects_zotero_ru_html_filename() -> None:
    tmp_path = _make_temp_dir()
    try:
        html_path = tmp_path / "Paper [RU HTML].html"
        html_path.write_text(
            "<html><body><p>Figure 1 | caption text</p></body></html>",
            encoding="utf-8",
        )

        result = inline_images_from_html_file(html_path)

        assert "Рисунок 1" in result.html
        assert "Figure 1" not in result.html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_inline_images_adds_readability_and_repairs_common_text_artifacts() -> None:
    tmp_path = _make_temp_dir()
    try:
        html_path = tmp_path / "doc.html"
        html_path.write_text(
            "<html><head><meta charset='utf-8'/></head><body><p>A&lt;sup&gt;1&lt;/sup&gt; РІР‚вЂќ Р’В©</p></body></html>",
            encoding="utf-8",
        )

        result = inline_images_from_html_file(html_path)

        assert 'data-z2m-style="readable"' in result.html
        assert '<main id="marker-doc">' in result.html
        assert "A<sup>1</sup>" in result.html
        assert "—" in result.html
        assert "©" in result.html
        assert "&lt;sup&gt;" not in result.html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_polish_html_document_repairs_spaced_escaped_sup_artifacts() -> None:
    html = (
        "<html><body>"
        "<p><sup>&amp;</sup> lt;sup&gt;b&lt;/sup&gt;Tumor in situ.</p>"
        "<p>& lt;sup&gt;c&lt;/sup&gt;Triple-negative breast cancer.</p>"
        "<p>&amp; lt;sub&gt;x&lt;/sub&gt; axis label.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "<sup>b</sup>Tumor in situ." in polished
    assert "<sup>c</sup>Triple-negative breast cancer." in polished
    assert "<sub>x</sub> axis label." in polished
    assert "lt;sup" not in polished
    assert "<sup>&amp;</sup>" not in polished
    assert "& lt;" not in polished


def test_polish_html_document_refreshes_existing_readability_style() -> None:
    html = (
        "<html><head>"
        "<style data-z2m-style=\"readable\">"
        "p { margin: 0.5em 0; }"
        "</style>"
        "</head><body><p>Demo paragraph.</p></body></html>"
    )

    polished = polish_html_document(html)

    assert polished.count('data-z2m-style="readable"') == 1
    assert "text-indent: 1.25em;" in polished
    assert "font-weight: 500;" in polished


def test_polish_html_document_autolinks_plain_web_urls() -> None:
    html = (
        "<html><body>"
        "<p>See https://example.com/paper.pdf.</p>"
        "<p>Portal: www.nature.com/reprints</p>"
        "<p>Conference paper doi:10.1109/MEMSYS.2013.6474424.</p>"
        "<p>Journal paper doi: 10.3389/fncir.2017.00020</p>"
        "<p>Split DOI doi: 10.1002/ nau.22813</p>"
        "<p>Publisher DOI doi:10.4028/ www.scientific.net/AMM.510.163</p>"
        "<p>Repository record [10.4028/www.scientific.net/AMM.510.163]</p>"
        '<p>Proc. Natl. Acad. Sci. U.S.A <a href="https://doi.org/10.1073/pnas.1221113110">'
        ". 110, 18279-18284. doi: 10.1073/</a> pnas.1221113110</p>"
        "<p>Digital Object Identifier 10.1109/TBCAS.2017.2731370</p>"
        '<p>Apps include <a href="https://www.wysa.com/">https://www.wysa.com/</a>and '
        '<a href="https://woebothealth.com/">https://woebothealth.com/</a>.</p>'
        "<p><a href=\"#ref-1\">[1]</a></p>"
        "<pre>https://do-not-link.example</pre>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert 'href="https://example.com/paper.pdf"' in polished
    assert 'href="https://www.nature.com/reprints"' in polished
    assert 'href="https://doi.org/10.1109/MEMSYS.2013.6474424"' in polished
    assert ">10.1109/MEMSYS.2013.6474424</a>." in polished
    assert 'href="https://doi.org/10.3389/fncir.2017.00020"' in polished
    assert 'href="https://doi.org/10.1002/nau.22813"' in polished
    assert 'href="https://doi.org/10.4028/www.scientific.net/AMM.510.163"' in polished
    assert polished.count(">10.4028/www.scientific.net/AMM.510.163</a>") == 2
    assert "10.4028/ www.scientific.net" not in polished
    assert "AMM.510.163]</a>" not in polished
    assert ">10.4028/www.scientific.net/AMM.510.163</a>]" in polished
    assert 'doi: <a href="https://doi.org/10.1073/pnas.1221113110">10.1073/pnas.1221113110</a>' in polished
    assert "doi: 10.1073/</a> pnas" not in polished
    assert 'Digital Object Identifier <a href="https://doi.org/10.1109/TBCAS.2017.2731370"' in polished
    assert 'https://www.wysa.com/</a> and <a href="https://woebothealth.com/"' in polished
    assert '<a href="#ref-1">[1]</a>' in polished
    assert "<pre>https://do-not-link.example</pre>" in polished


def test_polish_html_document_splits_doi_metadata_from_following_prose() -> None:
    html = (
        "<html><body>"
        "<p>Figure data doi: 10.1371/journal.pone.0076783.g005 "
        "The bar plots in Figure 7 illustrate trial-by-trial completion times.</p>"
        "<p>Source https://doi.org/10.1371/journal.pone.0199389.g005 "
        "As before, time to complete each trial was normalized and compared.</p>"
        '<p id="ref-8">Reference DOI: https://doi.org/10.1000/example '
        "The journal title continues here.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert re.search(
        r'doi:\s*<a href="https://doi\.org/10\.1371/journal\.pone\.0076783\.g005"[^>]*>'
        r"10\.1371/journal\.pone\.0076783\.g005</a>\s*</p>\s*<p>The bar plots",
        polished,
    )
    assert re.search(
        r'<a href="https://doi\.org/10\.1371/journal\.pone\.0199389\.g005"[^>]*>'
        r"https://doi\.org/10\.1371/journal\.pone\.0199389\.g005</a>\s*</p>\s*"
        r"<p>As before",
        polished,
    )
    assert 'id="ref-8"' in polished
    assert "The journal title continues here.</p>" in compact
    assert "</p> <p>The journal title continues here." not in compact


def test_polish_html_document_unescapes_safe_anchor_snippets() -> None:
    html = (
        "<html><body>"
        "<p>Reference literal: &lt;a href=\"https://example.com/page\"&gt;https://example.com/page&lt;/a&gt;</p>"
        "<pre>&lt;a href=\"https://example.com/code\"&gt;https://example.com/code&lt;/a&gt;</pre>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert '<a href="https://example.com/page" target="_blank" rel="noopener noreferrer">https://example.com/page</a>' in polished
    assert '&lt;a href="https://example.com/code"&gt;' in polished


def test_polish_html_document_repairs_split_visible_url_anchor_text() -> None:
    html = (
        "<html><body>"
        '<p>The Supplementary Material for this article can be found '
        '<a href="http://journal.frontiersin.org/article/10.3389/fncir.2017.00020/full#supplementary-material">'
        "online at: http://journal.frontiersin.org/article/10.3389/fncir.</a> "
        "2017.00020/full#supplementary-material</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    expected_url = "http://journal.frontiersin.org/article/10.3389/fncir.2017.00020/full#supplementary-material"

    assert f'found online at: <a href="{expected_url}">{expected_url}</a></p>' in polished
    assert "fncir.</a> 2017.00020" not in polished


def test_polish_html_document_merges_same_href_text_anchor_fragments() -> None:
    url = "https://dx.doi.org/10.1136/bmjopen-2021-056234"
    html = (
        "<html><body>"
        f'<p>See <a href="{url}">online supple</a> '
        f'<a href="{url}">mental table 1A-C</a> for details.</p>'
        f'<p>Also see <a href="{url}">online</a> '
        f'<a href="{url}">supplemental table 2B</a>.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "online supplemental table 1A-C" in compact
    assert "online supplemental table 2B" in compact
    assert "supple</a>" not in compact
    assert polished.count(f'href="{url}"') == 2


def test_polish_html_document_repairs_split_url_anchor_across_paragraphs() -> None:
    html = (
        "<html><body>"
        '<p>Online at <a href="http://www.niepce-letters-and-">'
        "http://www.niepce-letters-and-</a></p>"
        "<p>documents.com/book/#/906/ (Date accessed, 18 March 2017)</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    expected_url = "http://www.niepce-letters-and-documents.com/book/#/906/"

    assert f'<a href="{expected_url}">{expected_url}</a> (Date accessed' in polished
    assert "letters-and-</a></p>" not in polished


def test_polish_html_document_merges_adjacent_same_doi_anchors() -> None:
    html = (
        "<html><body><p>Ref. "
        '<a href="https://doi.org/10.1101/cshperspect.a041660">https://doi.org/</a> '
        '<a href="https://doi.org/10.1101/cshperspect.a041660">10.1101/cshperspect.a041660</a>'
        "</p></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count('href="https://doi.org/10.1101/cshperspect.a041660"') == 1
    assert ">https://doi.org/10.1101/cshperspect.a041660</a>" in polished
    assert "https://doi.org/</a> <a" not in polished


def test_polish_html_document_merges_parenthesized_split_same_href_url_anchors() -> None:
    href = "https://creativecommons.org/licenses/by/4.0/"
    html = (
        "<html><body><p>License "
        f'<a href="{href}">(https://creativecommons.org/</a> '
        f'<a href="{href}">licenses/by/4.0/)</a>.</p></body></html>'
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count(f'href="{href}"') == 1
    assert f">{href}</a>" in polished
    assert "creativecommons.org/</a>" not in polished
    assert "licenses/by/4.0/)</a>" not in polished


def test_polish_html_document_restores_hyphens_when_merging_split_url_anchors() -> None:
    href = (
        "https://www.gensight-biologics.com/2018/10/26/"
        "gensight-biologics-enrolls-first-subject-in-first-in-man-pioneer-phase-i-ii-"
        "clinical-trial-of-gs030-combining-gene-therapy-and-optogenetics-for-the-treatment-"
        "of-retinitis-pigmentosa/"
    )
    html = (
        "<html><body><p>Ref. "
        f'<a href="{href}">https://www.gensight-biologics.com/2018/10/26/</a> '
        f'<a href="{href}">gensight-biologics-enrolls-first-subject-in-first-in-man-pioneer</a> '
        f'<a href="{href}">phase-i-ii-clinical-trial-of-gs030-combining-gene-therapy-and</a> '
        f'<a href="{href}">optogenetics-for-the-treatment-of-retinitis-pigmentosa/</a>'
        "</p></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count(f'href="{href}"') == 1
    assert f">{href}</a>" in polished
    assert "pioneerphase" not in polished
    assert "therapy-andoptogenetics" not in polished


def test_polish_html_document_repairs_post_autolink_split_url_domains() -> None:
    html = (
        "<html><body>"
        '<p>Available at: <a href="https://www">https://www</a>. '
        '<a href="https://www.mathworks.com/matlabcentral/fileexchange/33484-linear-deming-regression">'
        "mathworks.com/matlabcentral/fileexchange/334</a> 84-linear-deming-regression.</p>"
        '<p>Journal page <a href="http://www.dovepress">http://www.dovepress</a>. '
        "com/testimonials.php to read quotes.</p>"
        '<p>Software <a href="http://www.megasoftware.net/">http://www.megasoftwa</a> '
        '<a href="http://www.megasoftware.net/">re.net</a>.</p>'
        '<p>Safety pack <a href="http://www.osha.europa.eu/en/Campaigns/ew2005/pressroom">'
        "www. osh</a> "
        '<a href="http://www.osha.europa.eu/en/Campaigns/ew2005/pressroom">'
        "a.europa.eu/en/Campaigns/ew2005/pressroom</a>.</p>"
        '<p>Archive <a href="https://www.yumpu">www.yumpu</a>. '
        "com/en/document/read/9413826/ bladder-ultrasonographypdf-internationalcontinence-society</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert ">https://www.mathworks.com/matlabcentral/fileexchange/33484-linear-deming-regression</a>." in compact
    assert ">http://www.dovepress.com/testimonials.php</a> to read quotes." in compact
    assert ">http://www.megasoftware.net/</a>." in compact
    assert ">http://www.osha.europa.eu/en/Campaigns/ew2005/pressroom</a>." in compact
    assert ">https://www.yumpu.com/en/document/read/9413826/bladder-ultrasonographypdf-internationalcontinence-society</a>" in compact
    assert "https://www</a>. <a" not in compact
    assert "www.dovepress</a>. com" not in compact
    assert "www.megasoftwa</a>" not in compact
    assert "www. osh" not in compact
    assert "www.yumpu</a>. com" not in compact


def test_polish_html_document_does_not_merge_same_href_reference_prose_with_url() -> None:
    href = "https://www.zotero.org/google-docs/?L0JBPZ"
    html = (
        "<html><body><ol>"
        f'<li><a href="{href}">36Bird S, Loper E, Klein E. '
        "Natural Language Processing with Python. O'Reilly Media Inc., 2009 </a> "
        f'<a href="{href}">https://www.nltk.org/.</a></li>'
        "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert 'href="36Bird S' not in polished
    assert polished.count(f'href="{href}"') == 2
    assert "Natural Language Processing with Python" in compact
    assert "https://www.nltk.org/" in compact


def test_polish_html_document_keeps_sentence_period_after_normalized_url_anchor() -> None:
    href = "http://www.3dphotoworks.com"
    html = (
        "<html><body>"
        f'<p>DPhotoWorks website is at <a href="{href}"> http://www.3dphotoworks.com. </a></p>'
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit"><p>Figure 1. Caption.</p></div>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert re.search(rf'<a href="{re.escape(href)}">{re.escape(href)}</a>\.\s*</p>', compact)
    assert not re.search(rf'<a href="{re.escape(href)}">{re.escape(href)}</a>\s*</p>', compact)


def test_polish_html_document_repairs_nested_autolink_in_escaped_anchor_snippet() -> None:
    html = (
        "<html><body>"
        "<p>(created in BioRender. Chamanzar, M. (2025) "
        "&lt;a href=\"<a href=\"https://BioRender.com/qms5tta\" target=\"_blank\" rel=\"noopener noreferrer\">https://BioRender.com/qms5tta</a>\"&gt;"
        "<a href=\"https://BioRender.com/qms5tta&lt;/a&gt;\" target=\"_blank\" rel=\"noopener noreferrer\">https://BioRender.com/qms5tta&lt;/a&gt;</a>)</p>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert 'href="<a href="https://BioRender.com/qms5tta"' not in polished
    assert polished.count('href="https://BioRender.com/qms5tta"') == 1


def test_polish_html_document_merges_biorender_caption_url_fragments() -> None:
    html = (
        "<html><body>"
        '<p id="fig-8"><img src="fig8.jpeg"/></p>'
        '<p class="z2m-figure-caption">Figure 8. Dura piercing. b Histological evaluation '
        "around the insertion site (created BioRender. Chamanzar. (2025) </p>"
        '<h4 class="z2m-figure-caption"><a href="https://BioRender.com/8bfbsk2">'
        "https://BioRender.com/8bfbsk2</a>).</h4>"
        '<p block-type="Text" class="z2m-figure-caption">comparison shows normalized cell density.</p>'
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count('href="https://BioRender.com/8bfbsk2"') == 1
    assert "created in BioRender. Chamanzar, M. (2025)" in polished
    assert "c shows normalized cell density" in polished
    assert "<h4 class=\"z2m-figure-caption\">" not in polished


def test_polish_html_document_wraps_box_title_body_and_retargets_split_box_link() -> None:
    html = (
        "<html><body>"
        '<p>Direct clinical translation is not required (Box <a href="#page-2-0">1)</a>.</p>'
        '<h2><span id="page-2-0"></span>BOX 1</h2>'
        "<h1>Indirect translation: examples inspired by optogenetic circuit analysis</h1>"
        "<p>In one approach to indirect translation, laboratory models provide a testing ground.</p>"
        "<h2>Introduction</h2>"
        "<p>Body text.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<a href="#box-1" class="z2m-box-link">Box\xa01</a>)' in polished
    assert re.search(r'<div id="box-1" class="[^"]*\bz2m-box-unit\b', polished)
    box_html = polished.split('<div id="box-1" class="z2m-float-unit z2m-box-unit">', 1)[1].split("</div>", 1)[0]
    assert "z2m-box-heading" in box_html
    assert "Indirect translation: examples inspired by optogenetic circuit analysis" in box_html
    assert "laboratory models provide a testing ground" in box_html
    assert "Introduction" not in box_html


def test_polish_html_document_retargets_split_numeric_section_page_link() -> None:
    html = (
        "<html><body>"
        '<p>Embedded sensors are described in Section <a href="#page-4-0">2)</a>.</p>'
        '<p>Finally, our findings are presented in Section <a href="#page-24-0">6.</a></p>'
        '<h2><span id="page-4-0"></span>2. Related Work</h2>'
        '<h2><span id="page-24-0"></span>6. Conclusions</h2>'
        "<p>Closing text.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<h2 id="section-2">' in polished
    assert '<h2 id="section-6">' in polished
    assert '<a href="#section-2" class="z2m-section-link">Section\xa02</a>)' in polished
    assert '<a href="#section-6" class="z2m-section-link">Section\xa06</a>.' in polished
    assert 'href="#page-24-0"' not in polished
    assert 'href="#page-4-0"' not in polished


def test_polish_html_document_retargets_split_appendix_page_link() -> None:
    html = (
        "<html><body>"
        '<p>Primary paper details are presented in Appendix <a href="#page-25-0">A.</a></p>'
        '<h3><b>Appendix A</b></h3>'
        '<span id="page-25-0"></span><table><tr><td>Details</td></tr></table>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="section-appendix-a"' in polished
    assert '<a href="#section-appendix-a" class="z2m-section-link">Appendix\xa0A</a>.' in polished
    assert '<h3 id="section-appendix-a"><b><a href="#section-appendix-a"' not in polished
    assert 'href="#page-25-0"' not in polished


def test_polish_html_document_links_sup_citations_to_references() -> None:
    html = (
        "<html><body>"
        "<p>Finding<sup>1,2</sup> is robust.</p>"
        "<h4>References</h4>"
        "<ul><li>First ref.</li><li>Second ref.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert '<li id="ref-1">' in polished
    assert '<li id="ref-2">' in polished
    assert (
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-2" class="z2m-ref-link">2</a></sup>'
    ) in polished


def test_polish_html_document_leaves_ambiguous_plain_comma_refs_when_numbers_already_linked() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 42))
    html = (
        "<html><body>"
        "<p>Prior reports.<sup>38</sup> These established the baseline. "
        "Later work.<sup>39</sup> These confirmed it.</p>"
        "<p>The spectra resembled a metal quantum dots system, 38,39 no obvious peaks appeared.</p>"
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert '<a href="#ref-38" class="z2m-ref-link">38</a>' in polished
    assert '<a href="#ref-39" class="z2m-ref-link">39</a>' in polished
    assert "system, 38,39 no obvious peaks appeared" in polished
    assert "system,<sup>" not in polished


def test_polish_html_document_links_ambiguous_plain_comma_refs_when_numbers_are_missing_elsewhere() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 42))
    html = (
        "<html><body>"
        "<p>The spectra resembled a metal quantum dots system, 38,39 no obvious peaks appeared.</p>"
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert (
        'system,<sup><a href="#ref-38" class="z2m-ref-link">38</a>,'
        '<a href="#ref-39" class="z2m-ref-link">39</a></sup> no obvious peaks appeared'
    ) in polished


def test_polish_html_document_links_bare_latex_sup_citations_to_references() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 6))
    html = (
        "<html><body>"
        "<p>Examples involve memory \\(^4\\), decision-making \\(^5\\).</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "\\(^4\\)" not in polished
    assert '<a href="#ref-4" class="z2m-ref-link">4</a>' in polished
    assert '<a href="#ref-5" class="z2m-ref-link">5</a>' in polished


def test_polish_html_document_links_unicode_sup_citations_without_unit_exponents() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 4))
    html = (
        "<html><body>"
        "<p>Optogenetics\u00b9 enables light delivered\u00b2.\u00b3, while area mm\u00b2 remains a unit.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'Optogenetics<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>' in polished
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' in polished
    assert '<a href="#ref-3" class="z2m-ref-link">3</a>' in polished
    assert "area mm\u00b2 remains" in polished


def test_polish_html_document_merges_operator_started_parenthetical_continuation() -> None:
    html = (
        "<html><body>"
        "<p>These features enabled broad application (with</p>"
        "<p>&gt;10,000 papers already reporting discoveries).</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "application (with &gt;10,000 papers already reporting discoveries)." in polished
    assert "application (with</p>" not in polished


def test_polish_html_document_repairs_ocr_split_final_letter_citations() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 15))
    html = (
        "<html><body>"
        '<p>Optogenetic discoveries guide human brain functio '
        '<a href="#ref-13" class="z2m-ref-link">n13</a> '
        '<a href="#ref-14" class="z2m-ref-link">,14</a>.</p>'
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "brain function<sup>" in polished
    assert '<a href="#ref-13" class="z2m-ref-link">13</a>' in polished
    assert '<a href="#ref-14" class="z2m-ref-link">,14</a></sup>.' in polished
    assert "functio " not in polished
    assert ">n13</a>" not in polished


def test_polish_html_document_repairs_ocr_split_page_link_citation_after_references() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 21))
    html = (
        "<html><body>"
        "<p>Main text.</p>"
        f"<h4>References</h4><ol>{refs}"
        '<li id="ref-21"><span id="page-11-11"></span>'
        '<span class="z2m-ref-num">21.</span> Sahel et al.</li></ol>'
        "<h4>Competing interests</h4>"
        '<p>trial on optogenetics in retinal degeneratio <a href="#page-11-11">n21.</a> Other text.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "retinal degeneration<sup>" in polished
    assert '<a href="#ref-21" class="z2m-ref-link">21</a></sup>.' in polished
    assert "</sup>. Other text." in polished
    assert 'href="#page-11-11"' not in polished


def test_polish_html_document_repairs_acronym_plural_page_link_citation() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 42))
    html = (
        "<html><body>"
        f"<h4>References</h4><ol>{refs}"
        '<li id="ref-42"><span id="page-12-18"></span>'
        '<span class="z2m-ref-num">42.</span> Large animal reference.</li></ol>'
        '<p>Testing in NHP <a href="#page-12-18">s42</a> provides insight.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Testing in NHPs<sup>" in polished
    assert '<a href="#ref-42" class="z2m-ref-link">42</a></sup> provides insight.' in polished
    assert ">s42</a>" not in polished


def test_polish_html_document_repairs_split_page_linked_bracket_citation_run() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 12))
    html = (
        "<html><body>"
        '<p>Necessary in STEM <a href="#page-28-8">[9</a>'
        '<a href="#page-28-10">,11]</a>.</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<a href="#ref-9" class="z2m-ref-link">9</a>' in polished
    assert '<a href="#ref-11" class="z2m-ref-link">11</a>' in polished
    assert '<a href="#ref-9" class="z2m-ref-link">[<a' not in polished
    assert 'href="#page-28-8"' not in polished


def test_polish_html_document_repairs_partial_page_linked_bracket_citations() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 35))
    html = (
        "<html><body>"
        '<p>Improvement in PPI [<a href="#page-11-0">29</a>'
        '<a href="#page-12-0">\u201334]</a>. '
        'LUTS <a href="#page-11-0">[30</a>].</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '[<a href="#ref-29" class="z2m-ref-link">29</a>\u2013<a href="#ref-34" class="z2m-ref-link">34</a>]' in polished
    assert '[<a href="#ref-30" class="z2m-ref-link">30</a>]' in polished
    assert 'href="#page-11-0"' not in polished
    assert '<a href="#ref-15" class="z2m-ref-link">' not in polished


def test_polish_html_document_repairs_split_page_linked_bracket_list() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 8))
    html = (
        "<html><body>"
        '<p>Risk markers remain visible <a href="#page-9-0">[3</a>, '
        '<a href="#page-9-0">5]</a>, with later follow-up.</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '[<a href="#ref-3" class="z2m-ref-link">3</a>, <a href="#ref-5" class="z2m-ref-link">5</a>],' in polished
    assert 'href="#page-9-0"' not in polished


def test_polish_html_document_repairs_broken_plain_url_before_autolink() -> None:
    html = (
        "<html><body>"
        "<p>License (https:// creativecommons.org/licenses/by/ 4.0/)</p>"
        "<p>Article https:// doi.org/10.1038/s41598-019-45416-4</p>"
        "<p>Package https://github.com/albertorestifo/ node-dijkstra</p>"
        "<p>Latest updates: hps://dl.acm.org/doi/10.1145/3155286</p>"
        "<p>Journal page http://www . dovepress.com/testimonials.php</p>"
        "<p>Fact sheet https://www . who.int/news-room/fact-sheets/detail/blindness</p>"
        "<p>Safety pack www. osh a.europa.eu/en/Campaigns/ew2005/pressroom</p>"
        "<p>Supplemental site www.operativeneuro surgery-online.com.</p>"
        '<p>Linked updates: <a href="https://dl.acm.org/doi/10.1145/2982142.2982176">'
        "hps://dl.acm.org/doi/10.1145/2982142.2982176</a></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="https://creativecommons.org/licenses/by/4.0/"' in polished
    assert 'href="https://doi.org/10.1038/s41598-019-45416-4"' in polished
    assert 'href="https://github.com/albertorestifo/node-dijkstra"' in polished
    assert 'href="https://dl.acm.org/doi/10.1145/3155286"' in polished
    assert 'href="http://www.dovepress.com/testimonials.php"' in polished
    assert 'href="https://www.who.int/news-room/fact-sheets/detail/blindness"' in polished
    assert 'href="https://www.osha.europa.eu/en/Campaigns/ew2005/pressroom"' in polished
    assert 'href="https://www.operativeneurosurgery-online.com"' in polished
    assert ">https://dl.acm.org/doi/10.1145/2982142.2982176</a>" in polished
    assert ">https://creativecommons.org/licenses/by/4.0/</a>" in polished
    assert "https:// creativecommons.org" not in polished
    assert "https:// doi.org" not in polished
    assert "albertorestifo/ node-dijkstra" not in polished
    assert "hps://dl.acm.org" not in polished
    assert "by/ 4.0" not in polished
    assert "www . dovepress" not in polished
    assert "www . who" not in polished
    assert "www. osh a" not in polished
    assert "operativeneuro surgery" not in polished


def test_polish_html_document_repairs_spaced_protocol_url_anchors() -> None:
    html = (
        "<html><body>"
        '<p>Available online: <a href="http: //www.brailleauthority.org/tg/web-manual/index.html">'
        "http: //www.brailleauthority.org/tg/web-manual/index.html</a></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="http://www.brailleauthority.org/tg/web-manual/index.html"' in polished
    assert ">http://www.brailleauthority.org/tg/web-manual/index.html</a>" in polished
    assert "http: //" not in polished


def test_polish_html_document_repairs_url_spaces_inside_path_continuations() -> None:
    html = (
        "<html><body>"
        '<p>Available at: "https://commons.wikimedia.org/wiki/ '
        'File:Threshold_roc.stack_overflow_ answers.svg", accessed.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    expected = "https://commons.wikimedia.org/wiki/File:Threshold_roc.stack_overflow_answers.svg"

    assert f'href="{expected}"' in polished
    assert f">{expected}</a>" in polished
    assert "wiki/ File" not in polished
    assert "overflow_ answers" not in polished


def test_polish_html_document_merges_split_quoted_url_anchors() -> None:
    expected = "https://commons.wikimedia.org/wiki/File:Threshold_roc.stack_overflow_answers.svg"
    quoted_href = f'"{expected}"'
    html = (
        "<html><body>"
        "<p>Available at: "
        f'<a href=\'{quoted_href}\'>"https://commons.wikimedia.org/wiki/</a> '
        f'<a href=\'{quoted_href}\'>File:Threshold_roc.stack_overflow_</a> '
        f'<a href=\'{quoted_href}\'>answers.svg"</a>, accessed.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count(f'href="{expected}"') == 1
    assert f">{expected}</a>" in polished
    assert "wiki/</a>" not in polished
    assert "overflow_</a>" not in polished
    assert 'href=\'"https://' not in polished


def test_polish_html_document_merges_split_url_after_reference_anchor() -> None:
    url = "http://www.annualreviews.org"
    html = (
        "<html><body>"
        '<p>Figure adapted with permission from ref. <a href="#ref-277">277</a>, '
        f'<a href="{url}">http://</a> <a href="{url}">www.annualreviews.org</a>.</p>'
        "<ol><li id=\"ref-277\">Reference.</li></ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count(f'href="{url}"') == 1
    assert f">{url}</a>" in polished
    assert "http://</a>" not in polished


def test_polish_html_document_merges_split_mailto_anchors() -> None:
    html = (
        "<html><body>"
        '<p>e-mail: <a href="mailto:gyorgy.buzsaki@nyulangone.org">gyorgy.buzsaki@</a> '
        '<a href="mailto:gyorgy.buzsaki@nyulangone.org">nyulangone.org</a></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count('href="mailto:gyorgy.buzsaki@nyulangone.org"') == 1
    assert ">gyorgy.buzsaki@nyulangone.org</a>" in polished
    assert "gyorgy.buzsaki@</a>" not in polished


def test_polish_html_document_fixes_spaced_sup_and_backslash_artifacts() -> None:
    html = (
        "<html><body>"
        "<p>Fig. 2 \\ | \\ Pipeline. \\ The \\ key steps. "
        "<strong>Fig. 3</strong> \\\\ | \\\\ <strong>Pipeline.</strong> \\\\ The \\\\ key steps. "
        "< sup>3</ sup></p>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert " \\ | \\" not in polished
    assert "\\ The \\" not in polished
    assert "\\\\ | \\\\" not in polished
    assert "\\\\ The \\\\" not in polished
    assert "<sup>3</sup>" in polished


def test_polish_html_document_inserts_space_after_z2m_links() -> None:
    html = (
        "<html><body>"
        "<p>См. <a href=\"#ref-30\" class=\"z2m-ref-link\">[30]</a>Мы применили фильтр.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)
    assert '</a> Мы применили фильтр.' in polished


def test_polish_html_document_fixes_lc_sensor_heading_artifact() -> None:
    html = (
        "<html><body>"
        "<h1>Новая схема для пассивной беспроводной системы <i>LC</i> датчик</h1>"
        "</body></html>"
    )

    polished = polish_html_document(html)
    assert "<i>LC</i>-датчика" in polished


def test_polish_html_document_normalizes_table_caption_style() -> None:
    html = (
        "<html><body>"
        "<p>TABLE I PARAMETERS FOR TWO ANTENNAS</p>"
        "<p>TABLE II. PARAMETERS OF SENSOR</p>"
        "<p>Таблица III параметры антенны</p>"
        "<p>Таблица IV: COMPARISON OF STATE OF ARTS.</p>"
        '<p><span id="page-4-0"></span> TABLE V Анализ Бланда — Альтмана Qmax и PVR</p>'
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "Таблица I. Parameters for two antennas." in polished
    assert "Таблица II. Parameters of sensor." in polished
    assert "Таблица III. Параметры антенны." in polished
    assert "Таблица IV. Comparison of state of arts." in polished
    assert '<span id="page-4-0"></span> Таблица V. Анализ Бланда — Альтмана Qmax и PVR.' in polished
    assert 'id="table-i"' in polished
    assert 'id="table-ii"' in polished
    assert 'id="table-iii"' in polished
    assert 'id="table-iv"' in polished
    assert 'id="table-v"' in polished


def test_polish_html_document_normalizes_table_caption_style_en_mode() -> None:
    html = (
        "<html><body>"
        "<p>TABLE I PARAMETERS FOR TWO ANTENNAS</p>"
        "<p>Таблица II параметры сенсора</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "TABLE I. Parameters for two antennas." in polished
    assert "TABLE II. Параметры сенсора." in polished
    assert 'id="table-i"' in polished
    assert 'id="table-ii"' in polished


def test_polish_html_document_normalizes_table_cell_roman_suffixes() -> None:
    html = (
        "<html><body><table><tbody><tr>"
        "<td>PDMSi</td><td>Parylene Ci</td><td>Polyimidei</td>"
        "<td>LCPsii</td><td>SMPsiii</td><td>ascii</td>"
        "</tr></tbody></table></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<td>PDMS<sup class="z2m-table-fn">i</sup></td>' in polished
    assert '<td>Parylene C<sup class="z2m-table-fn">i</sup></td>' in polished
    assert '<td>Polyimide<sup class="z2m-table-fn">i</sup></td>' in polished
    assert '<td>LCPs<sup class="z2m-table-fn">ii</sup></td>' in polished
    assert '<td>SMPs<sup class="z2m-table-fn">iii</sup></td>' in polished
    assert "<td>ascii</td>" in polished


def test_polish_html_document_normalizes_ru_figure_caption_lexemes() -> None:
    html = (
        "<html><body>"
        "<p>рисуног 1 test caption</p>"
        "<p>рисунк 2 another caption</p>"
        "<p>РИСУНО 3 third caption</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru")
    assert "Рисунок 1. Test caption." in polished
    assert "Рисунок 2. Another caption." in polished
    assert "Рисунок 3. Third caption." in polished


def test_polish_html_document_normalizes_english_ru_figure_caption_label() -> None:
    html = "<html><body><p>Figure 5 | caption text</p></body></html>"
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "Figure 5" not in polished
    assert "Рисунок 5" in polished


def test_polish_html_document_normalizes_ru_figure_labels_with_linkify_enabled() -> None:
    html = (
        "<html><body>"
        "<p>Как показано на Figure 5.</p>"
        "<p>Figure 5 | подпись к рисунку</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru")

    assert "Figure 5" not in polished
    assert "Figure\xa05" not in polished
    assert "Рисунок 5" in polished


def test_polish_html_document_normalizes_ru_figure_caption_with_leading_inline_tag() -> None:
    html = (
        "<html><body>"
        "<p><span id=\"page-1-0\"></span> Фигура 2 | caption text</p>"
        "<p><span id=\"page-2-0\"></span> РИСУНО 5 | another caption</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "Фигура 2" not in polished
    assert "РИСУНО 5" not in polished
    assert "Рисунок 2. Caption text." in polished
    assert "Рисунок 5. Another caption." in polished


def test_polish_html_document_unwraps_page_links_inside_leading_caption_labels() -> None:
    html = (
        "<html><body>"
        '<p class="z2m-figure-caption"><a href="#page-3-0">Fig 2. S</a> chematic diagram</p>'
        '<p class="z2m-table-caption"><a href="#page-4-0">Table 1. T</a> he settings</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Figure 2. Schematic diagram." in polished
    assert "TABLE 1. The settings." in polished
    assert '<a href="#page-3-0">Fig 2. S</a>' not in polished
    assert '<a href="#page-4-0">Table 1. T</a>' not in polished


def test_polish_html_document_unwraps_page_links_on_reference_list_numbers() -> None:
    html = (
        "<html><body>"
        "<h4>References</h4><ul>"
        '<li id="ref-1"><a href="#page-0-0"><span class="z2m-ref-num">1.</span></a> '
        "Levy-Tzedek S. Color improves visual acuity.</li>"
        '<li id="ref-2"><a href="#page-0-0">2.</a> Auvray M. Learning to perceive.</li>'
        "</ul></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<a href="#page-0-0"><span class="z2m-ref-num">1.</span></a>' not in polished
    assert '<a href="#page-0-0">2.</a>' not in polished
    assert '<span class="z2m-ref-num">1.</span> Levy-Tzedek' in polished
    assert re.search(r"(?:>2\.</span>|>2\.) Auvray", polished)


def test_polish_html_document_normalizes_hallucinated_ru_figure_caption_label() -> None:
    html = (
        "<html><body>"
        "<p id=\"fig-1\"><span id=\"page-2-0\"></span> РАДИОГРАМ 1 | caption text</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "РАДИОГРАМ 1" not in polished
    assert "Рисунок 1. Caption text." in polished


def test_polish_html_document_normalizes_ru_figure_table_labels_inside_anchors() -> None:
    html = (
        "<html><body>"
        "<p><a href=\"#page-1-0\">Figure 1C</a> and <a href=\"#page-2-0\">Table 1</a> and Фигура 2.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "Figure 1C" not in polished
    assert "Table 1" not in polished
    assert "Фигура 2" not in polished
    assert "Рисунок 1C" in polished
    assert "Таблица 1" in polished
    assert "Рисунок 2" in polished


def test_polish_html_document_normalizes_ru_supplementary_and_split_figure_lexemes() -> None:
    html = (
        "<html><body>"
        "<p>Фигура S3a and РИСУНО 5 and Фигура <a href=\"#page-2-0\">1</a>.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "Фигура S3a" not in polished
    assert "РИСУНО 5" not in polished
    assert "Рисунок S3a" in polished
    assert "Рисунок 5" in polished
    assert "Рисунок <a href=\"#page-2-0\">1</a>" in polished


def test_polish_html_document_strips_protocol_sentinel_leaks() -> None:
    html = (
        "<html><body>"
        "<h2>@@Z2M_HSEPФинансирование</h2>"
        "<p>Статистически значимо (@@Z2M_A0\\_\\_, p &lt; 0,001), для @@Z2M_A1\\_\\_.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "@@Z2M_" not in polished
    assert "Финансирование" in polished
    assert "(p &lt; 0,001)" in polished


def test_polish_html_document_strips_english_prefix_from_ru_heading() -> None:
    html = (
        "<html><body>"
        "<h1><i>Shape memory polymers (SMPs) изменяют форму под воздействием стимулов</i></h1>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "Shape memory polymers" not in polished
    assert "изменяют форму под воздействием стимулов" in polished


def test_polish_html_document_normalizes_numeric_section_heading_levels() -> None:
    html = (
        "<html><body>"
        "<h4>2 СВЯЗАННАЯ РАБОТА</h4>"
        "<h1>2.1 Создание тактильных изображений</h1>"
        "<h2>3 Pic2Tac: FROM PICTURE TO TACTILE</h2>"
        "<h1>4 ПОЛЬЗОВАТЕЛЬСКИЕ ИССЛЕДОВАНИЯ</h1>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru")

    assert re.search(r"<h2[^>]*>2 СВЯЗАННАЯ РАБОТА</h2>", polished)
    assert re.search(r"<h3[^>]*>2\.1 Создание тактильных изображений</h3>", polished)
    assert re.search(r"<h2[^>]*>3 Pic2Tac: FROM PICTURE TO TACTILE</h2>", polished)
    assert re.search(r"<h2[^>]*>4 ПОЛЬЗОВАТЕЛЬСКИЕ ИССЛЕДОВАНИЯ</h2>", polished)


def test_polish_html_document_strips_long_english_run_in_ru_paragraph() -> None:
    html = (
        "<html><body>"
        "<p>Shape memory polymers change their shape in response to external stimuli, "
        "такие материалы изменяют форму под воздействием внешних стимулов.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "Shape memory polymers change their shape in response to external stimuli" not in polished
    assert "изменяют форму под воздействием внешних стимулов" in polished


def test_polish_html_document_keeps_long_english_run_inside_references_block() -> None:
    html = (
        "<html><body>"
        "<div class=\"z2m-references-block\" translate=\"no\">"
        "<p>Shape memory polymers change their shape in response to external stimuli, "
        "такие материалы изменяют форму.</p>"
        "</div>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru", enable_citation_linkify=False)
    assert "Shape memory polymers change their shape in response to external stimuli" in polished


def test_polish_html_document_ru_mode_can_disable_citation_linkify() -> None:
    html = (
        "<html><body>"
        "<p>See [1] and Fig. 2 for details.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(
        html,
        table_caption_language="ru",
        enable_citation_linkify=False,
    )
    assert 'class="z2m-ref-link"' not in polished
    assert 'class="z2m-fig-link"' not in polished


def test_polish_html_document_unwraps_nested_fig_links_even_when_linkify_disabled() -> None:
    html = (
        "<html><body>"
        "<p><a href=\"#fig-1\" class=\"z2m-fig-link\">"
        "<a href=\"#fig-1\" class=\"z2m-fig-link\">Figure 1a</a>"
        "</a></p>"
        "</body></html>"
    )
    polished = polish_html_document(
        html,
        table_caption_language="ru",
        enable_citation_linkify=False,
    )
    assert polished.count('class="z2m-fig-link"') == 1
    assert '<a href="#fig-1" class="z2m-fig-link"><a href="#fig-1"' not in polished


def test_polish_html_document_unwraps_nested_same_href_table_links() -> None:
    html = (
        "<html><body>"
        "<p>The values are listed in "
        "<a href=\"#table-8-2\" class=\"z2m-table-link\">"
        "<a href=\"#table-8-2\" class=\"z2m-table-link\">Tables 8.2</a>"
        "</a> and <a href=\"#table-8-4\" class=\"z2m-table-link\">8.4</a>.</p>"
        "<div id=\"table-8-2\"><p>TABLE 8.2. Data.</p></div>"
        "<div id=\"table-8-4\"><p>TABLE 8.4. Data.</p></div>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en", enable_citation_linkify=False)

    assert polished.count('href="#table-8-2"') == 1
    assert '<a href="#table-8-2" class="z2m-table-link">Tables 8.2</a>' in polished
    assert '<a href="#table-8-2" class="z2m-table-link"><a href="#table-8-2"' not in polished
    assert "</a></a>" not in polished


def test_polish_html_document_repairs_sentence_split_by_figure_block() -> None:
    html = (
        "<html><body>"
        "<p>The amplitude value is sent back to the microcontroller for signal processing</p>"
        "<figure><img src=\"f8.png\"/></figure>"
        "<p>at the same time, it is also sent to a NI DAQ.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert (
        "The amplitude value is sent back to the microcontroller for signal processing "
        "at the same time, it is also sent to a NI DAQ."
    ) in polished
    assert polished.count("at the same time, it is also sent to a NI DAQ.") == 1
    assert "<figure><img src=\"f8.png\"/></figure>" in polished


def test_polish_html_document_drops_ocr_figure_annotation_heading_before_caption() -> None:
    html = (
        "<html><body>"
        "<h4>Electrode Fabrication</h4>"
        "<h1>A 96ch flexible surface electrode array Fabricated electrode Thickness = 20um 20 mm "
        "Stimulating electrode Gold 1st Parylene-C layer Silicon substrate Aluminium mask "
        "2nd Parylene-C layer Oxygen plasma etching Remove mask and Liftoff from silicon substrate</h1>"
        "<p>FIGURE 1 | Electrode fabrication and experimental paradigm.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    assert "A 96ch flexible surface electrode array" not in polished
    assert "Figure 1." in polished


def test_polish_html_document_drops_page_footer_paragraphs() -> None:
    html = (
        "<html><body>"
        "<p>Li et al. Bioelectronic Medicine (2026) 12:6 Page 3 of 33</p>"
        "<p>Real article text continues here.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    assert "Page 3 of 33" not in polished
    assert "Real article text continues here." in polished


def test_polish_html_document_removes_page_furniture_inside_text_nodes() -> None:
    html = (
        "<html><body>"
        "<p>References ended. Published on 20 July 2015. Downloaded by California State "
        "University at Fresno on 25/07/2015 20:19:39 Entry for the Table of Contents.</p>"
        "<p>Published on 03 August 2015. Downloaded by Emory University on "
        "04/08/2015 04:19:33</p>"
        "<p>The acknowledgments stay readable.</p>"
        "<p>Map study context Manuscript received on April 17, 2021. Revised Manuscript "
        "received on April 15, 2021. Manuscript published on April 30, 2021. "
        "* Correspondence Author participants completed the task.</p>"
        "<p>Groups were compared for Alrabadi et al. 3 each position using a test.</p>"
        "<p>Groups were compared for <i> Alrabadi et al. </i> 3 each position again.</p>"
        "<p><i> Alrabadi et al. </i> 5</p>"
        "<p>ChemComm Accepted Manuscript This article can be cited before page numbers.</p>"
        "<h1>ChemComm </h1><p block-type=\"Text\">Accepted Manuscript </p>"
        "<p>This article can be cited before page numbers have been issued.</p>"
        "<p block-type=\"Text\">ChemComm Accepted Manuscrip </p>"
        "<p>photostability remains the real sentence.</p>"
        "<p>Microsoft Redmond Washington, FRANCO ET AL. | 1915 USA and XLSTAT.</p>"
        "<p>Data analysis was run on excel (Microsoft Redmond Washington, </p>"
        "<p block-type=\"Text\"> FRANCO ET AL. <sup> | </sup> <sup> 1915 </sup> </p>"
        "<p block-type=\"Text\"> USA) and XLSTAT.</p>"
        "<p><span id=\"page-10-0\"> </span> FRANCO ET AL. <sup> | </sup> "
        "<sup> 1923 </sup> persistence of the pattern can continue.</p>"
        "<p>Figure caption text 106 Y. Volpe et al. Tactile assessment continued.</p>"
        "<h4>106 <i>Y. Volpe et al.</i></h4><p>Tactile assessment starts cleanly.</p>"
        "<blockquote><p block-type=\"Text\"><i>Published By: Blue Eyes Intelligence Engineering "
        "&amp; Sciences Publication © Copyright: All rights reserved.</i></p></blockquote>"
        "<p block-type=\"Text\"><i>Retrieval Number:100.1/ijmh.E1208015521 "
        "doi:10.35940/ijmh.E1208.045821 Journal Website : www.ijmh.org</i></p>"
        '<code>ChemComm Accepted Manuscript FRANCO ET AL. | 1915</code>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Downloaded by California State University" not in polished
    assert "Downloaded by Emory University" not in polished
    assert "Entry for the Table of Contents" in polished
    assert "The acknowledgments stay readable" in polished
    assert "Manuscript received on April 17, 2021" not in polished
    assert "Map study context participants completed the task" in polished
    assert "for each position using a test" in polished
    assert "for each position again" in polished
    assert "Alrabadi et al. </i> 5" not in polished
    assert "ChemComm Accepted Manuscript This article" not in polished
    assert "<h1>ChemComm" not in polished
    assert "This article can be cited before page numbers" in polished
    assert "ChemComm Accepted Manuscrip </p>" not in polished
    assert "photostability remains the real sentence" in polished
    assert "Washington, USA and XLSTAT" in polished
    assert "Microsoft Redmond Washington, USA) and XLSTAT" in polished
    assert "persistence of the pattern can continue" in polished
    assert "Figure caption text Tactile assessment continued" in polished
    assert "Tactile assessment starts cleanly" in polished
    assert "Blue Eyes Intelligence Engineering" not in polished
    assert "Retrieval Number:100.1/ijmh.E1208015521" not in polished
    assert "Y. Volpe et al." not in polished
    assert "FRANCO ET AL. <sup>" not in polished
    assert "<code>ChemComm Accepted Manuscript FRANCO ET AL. | 1915</code>" in polished


def test_polish_html_document_drops_repeated_running_headers_and_repairs_text() -> None:
    html = (
        "<html><body>"
        "<p>Journal of Useful Imaging Accepted Manuscript</p>"
        "<p>During phantom evaluation, the device measured</p>"
        "<p>Journal of Useful Imaging Accepted Manuscript the signal continuously.</p>"
        "<p>Journal of Useful Imaging Accepted Manuscript</p>"
        "<p>Repeated observation remains a real body sentence.</p>"
        "<p>Repeated observation remains a real body sentence.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "Journal of Useful Imaging Accepted Manuscript" not in flat
    assert "the device measured the signal continuously." in flat
    assert flat.count("Repeated observation remains a real body sentence.") == 2


def test_polish_html_document_splits_glued_roman_suffixes() -> None:
    html = (
        "<html><body>"
        "<p>Foilii Laser ablationiv Plasma etchingv are listed.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    assert "Foil ii" in polished
    assert "ablation iv" in polished
    assert "etching v" in polished


def test_polish_html_document_rejoins_surname_split_after_given_name() -> None:
    html = (
        "<html><body>"
        "<p>Philip Shiu and Anton Arkhipov provided guidance throughout the process. "
        "While x-ray-based approaches remain useful.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Anton Arkhipov provided guidance" in polished
    assert "Anton Arkhipo v provided" not in polished
    assert "While x-ray-based approaches" in polished
    assert "Whilex-ray" not in polished


def test_polish_html_document_rejoins_ii_surname_split_after_initials() -> None:
    html = (
        "<html><body>"
        "<p>E. P. Vovk, Yu. P. Kurenev, and V. V. Petrangovskii</p>"
        "<p>Ukrainian Technology Center of Optical Instrumentation.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "V. V. Petrangovskii" in polished
    assert "Petrangovsk ii" not in polished
    assert "Yu. P. Kurenev," in polished


def test_polish_html_document_promotes_table_cell_roman_footnotes_and_soft_breaks() -> None:
    html = (
        "<html><body>"
        "<table><tr>"
        "<td>Evaporation, sputteringi</td>"
        "<td>Foilii</td>"
        "<td>Electrodepositionvii</td>"
        "<td>Electrodeposition (EIROF)viii</td>"
        "<td>RuOx</td>"
        "<td>Rough and porous morphology increases electro<br/>chemical surface area, "
        "deposition process compatible</td>"
        "</tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "sputtering<sup class=\"z2m-table-fn\">i</sup>" in polished
    assert "Foil<sup class=\"z2m-table-fn\">ii</sup>" in polished
    assert "Electrodeposition<sup class=\"z2m-table-fn\">vii</sup>" in polished
    assert "(EIROF)<sup class=\"z2m-table-fn\">viii</sup>" in polished
    assert "RuOx</td>" in polished
    assert "electrochemical surface area" in polished
    assert "<br" not in polished


def test_polish_html_document_keeps_names_and_variables_from_false_roman_splits() -> None:
    html = (
        "<html><body>"
        "<p class=\"z2m-front-matter\">Alice Belyae v, Yakovle v (1967), "
        "Gusta v le Gray, Gaura v Bartarya, Govern <a href=\"#page-1-0\">i1,</a></p>"
        "<table><tr><td>Qmax</td><td>Flowi</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Belyaev" in polished
    assert "Yakovlev (1967)" in polished
    assert "Gustav le Gray" in polished
    assert "Gaurav Bartarya" in polished
    assert "Governi<sup>1</sup>," in polished
    assert 'href="#page-1-0"' not in polished
    assert "Qmax" in polished
    assert "Qma<sup" not in polished
    assert "Flow<sup" not in polished


def test_polish_html_document_rejoins_surname_v_before_et_al_and_reference_sentence() -> None:
    html = (
        "<html><body>"
        "<p>Abdusalomo v et al. proposed a saliency method.</p>"
        "<p>Similarly, Laha v et al. studied navigation.</p>"
        "<p>Pairwise Kolmogoro v-Smirno v tests and a Marko v chain were reported.</p>"
        "<p>W i = Mean i * N n i and Dcon v refers to deformable convolution.</p>"
        "<h4>References</h4>"
        "<ul><li>J. A. Gardner and V. Bulato v. Scientific diagrams made easy.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Abdusalomov et al." in polished
    assert "Lahav et al." in polished
    assert "Kolmogorov-Smirnov tests" in polished
    assert "Markov chain" in polished
    assert "Mean i * N" in polished
    assert "Dcon v refers" in polished
    assert "V. Bulatov. Scientific diagrams" in polished
    assert "Abdusalomo v" not in polished
    assert "Laha v" not in polished
    assert "Kolmogoro v" not in polished
    assert "Smirno v" not in polished
    assert "Marko v" not in polished
    assert "Bulato v." not in polished


def test_polish_html_document_rejoins_vi_surname_before_reporting_verb() -> None:
    html = (
        "<html><body>"
        '<p>Hands-off historians, Hale vi suggests, sometimes speculate. '
        'Hale vi proposed a distinction. '
        'Table vi remains a separate appendix marker.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Halevi suggests" in polished
    assert "Halevi proposed" in polished
    assert "Hale vi suggests" not in polished
    assert "Hale vi proposed" not in polished
    assert "Table vi remains" in polished


def test_polish_html_document_rejoins_roman_split_email_local_part() -> None:
    html = (
        "<html><body>"
        "<p>Nizhni Novgorod State University e-mail: simono v@neuro.nnov.ru Received March 10, 2011</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "simonov@neuro.nnov.ru" in polished
    assert "simono v@" not in polished


def test_polish_html_document_repairs_sentence_split_by_image_paragraph() -> None:
    html = (
        "<html><body>"
        "<p>The sensor was positioned close to the antenna</p>"
        "<p><img src=\"fig9.png\"/></p>"
        "<p>At the same time, the signal was monitored continuously.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert (
        "The sensor was positioned close to the antenna "
        "At the same time, the signal was monitored continuously."
    ) in polished
    assert polished.count("At the same time, the signal was monitored continuously.") == 1
    assert "<p><img src=\"fig9.png\"/></p>" in polished


def test_polish_html_document_repairs_sentence_split_by_float_run_after_long_body_paragraph() -> None:
    html = (
        "<html><body>"
        "<p>The devised method was shared with the Italian Union of Blind and Visually Impaired People "
        "in Florence (Italy) and experts working in the Cultural Heritage field. According to their "
        "suggestions, authors realized bas-reliefs of artworks including The Annunciation permanently</p>"
        "<div id=\"fig-16\" class=\"z2m-float-unit z2m-figure-unit\"><p>Figure 16. GUI.</p></div>"
        "<span id=\"page-14-0\"> </span>"
        "<div id=\"fig-17\" class=\"z2m-float-unit z2m-figure-unit\"><p>Figure 17. Model.</p></div>"
        "<div id=\"fig-18\" class=\"z2m-float-unit z2m-figure-unit\"><p>Figure 18. Prototype.</p></div>"
        "<p>displayed at the Museo di San Marco.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert "The Annunciation permanently displayed at the Museo di San Marco." in polished
    assert polished.count("displayed at the Museo di San Marco.") == 1
    assert '<div id="fig-16" class="z2m-float-unit z2m-figure-unit' in polished


def test_polish_html_document_repairs_sentence_split_by_multiple_float_runs() -> None:
    html = (
        "<html><body>"
        "<p>The tactile output from the prototype</p>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit"><p>Figure 1. Prototype.</p></div>'
        "<p>was evaluated by participants</p>"
        '<div id="table-1" class="z2m-float-unit z2m-table-unit"><p>Table 1. Scores.</p></div>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit"><p>Figure 2. Setup.</p></div>'
        "<p>during the second study.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 2
    assert "The tactile output from the prototype was evaluated by participants during the second study." in polished
    assert polished.count("was evaluated by participants") == 1
    assert polished.count("during the second study.") == 1
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit">' in polished
    assert '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">' in polished


def test_polish_html_document_repairs_ru_sentence_split_by_multiple_tables() -> None:
    html = (
        "<html><body>"
        "<p>Также очевидно, что второе мочеиспускание у этих пациентов характеризуется большей вариабельностью</p>"
        '<div id="table-1" class="z2m-float-unit z2m-table-unit"><p>Таблица 1. Женщины.</p></div>'
        '<div id="table-2" class="z2m-float-unit z2m-table-unit"><p>Таблица 2. Мужчины.</p></div>'
        "<p>с более высокими показателями ошибок между потоками.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert (
        "Также очевидно, что второе мочеиспускание у этих пациентов характеризуется большей вариабельностью "
        "с более высокими показателями ошибок между потоками."
    ) in polished
    assert polished.count("с более высокими показателями ошибок между потоками.") == 1
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit">' in polished
    assert '<div id="table-2" class="z2m-float-unit z2m-table-unit">' in polished


def test_polish_html_document_repairs_en_sentence_split_by_multiple_tables_after_front_matter_mark() -> None:
    html = (
        "<html><body>"
        '<p class="z2m-front-matter">'
        "On the accuracy analysis tables, we see that volume affects Qmax the most, "
        "with the lowest error rates seen in ideal voiders with the IVFE and the greatest "
        "errors in the high volume high PVR voiders. It is also clear that the second void "
        "in these patients has greater variability</p>"
        '<div id="table-1" class="z2m-float-unit z2m-table-unit"><p>TABLE 1. Female statistics.</p></div>'
        '<div id="table-2" class="z2m-float-unit z2m-table-unit"><p>TABLE 2. Male statistics.</p></div>'
        "<p>with higher error rates between the flows.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert (
        "It is also clear that the second void in these patients has greater variability "
        "with higher error rates between the flows."
    ) in polished
    assert polished.count("with higher error rates between the flows.") == 1
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit">' in polished
    assert '<div id="table-2" class="z2m-float-unit z2m-table-unit">' in polished


def test_polish_html_document_repairs_split_after_pre_wrapped_table_run() -> None:
    html = (
        "<html><body>"
        '<p class="z2m-front-matter">'
        "It is also clear that the second void in these patients has greater variability</p>"
        '<div id="table-1" class="z2m-float-unit z2m-table-unit">'
        '<p class="z2m-table-caption">TABLE 1. Female statistics.</p>'
        "<table><tr><td>A</td></tr></table></div>"
        '<div id="table-2" class="z2m-float-unit z2m-table-unit">'
        '<p class="z2m-table-caption">TABLE 2. Male statistics.</p>'
        "<table><tr><td>B</td></tr></table></div>"
        "<p>with higher error rates between the flows.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "greater variability with higher error rates between the flows." in polished
    assert polished.count('id="table-1"') == 1
    assert polished.count('id="table-2"') == 1
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit"><div id="table-1"' not in polished


def test_polish_html_document_repairs_split_across_tables_with_punctuation_gap() -> None:
    html = (
        "<html><body>"
        "<p>Using accuracy measures, results are lower in normal bladder volumes and no PVR "
        "(Supplemental Table S3). We</p>"
        '<div id="table-3" class="z2m-float-unit z2m-table-unit"><p>TABLE 3. First table.</p></div>'
        '<p block-type="Text"> . </p>'
        '<div id="table-4" class="z2m-float-unit z2m-table-unit"><p>TABLE 4. Second table.</p></div>'
        '<p block-type="Text"> . </p>'
        '<div id="table-5" class="z2m-float-unit z2m-table-unit"><p>TABLE 5. Third table.</p></div>'
        '<span id="page-6-0"> </span>'
        "<p>can see that the derived values remain stable.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "(Supplemental Table S3). We can see that the derived values remain stable." in polished
    assert "We </p>" not in polished
    assert polished.count("can see that the derived values remain stable.") == 1
    assert '<p block-type="Text"> . </p>' in polished


def test_polish_html_document_repairs_short_multiword_fragment_before_float() -> None:
    html = (
        "<html><body>"
        "<p>We can clearly</p>"
        '<div id="table-1" class="z2m-float-unit z2m-table-unit"><p>TABLE 1. Results.</p></div>'
        "<p>see the pattern in both groups.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert "We can clearly see the pattern in both groups." in polished
    assert polished.count("see the pattern in both groups.") == 1
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit">' in polished


def test_polish_html_document_repairs_sentence_split_by_image_then_table_float() -> None:
    html = (
        "<html><body>"
        "<p>All authors independently screened all the</p>"
        "<p><img src=\"table-preview.png\"/></p>"
        "<div id=\"table-1\" class=\"z2m-float-unit z2m-table-unit\"><p>Table 1. Studies.</p></div>"
        "<p block-type=\"Text\" class=\"z2m-front-matter\">retrieved articles for inclusion and exclusion.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert "All authors independently screened all the retrieved articles for inclusion and exclusion." in polished
    assert polished.count("retrieved articles for inclusion and exclusion.") == 1
    assert "<p><img src=\"table-preview.png\"/></p>" in polished


def test_polish_html_document_repairs_sentence_split_by_caption_paragraph() -> None:
    html = (
        "<html><body>"
        "<p>The first network is trained by the second to generate synthetic images that cannot be distinguished from real ones, enabling the production of</p>"
        "<p>Fig. 1 | Overview of the GAI development pipeline.</p>"
        "<p>highly detailed, realistic images.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert (
        "The first network is trained by the second to generate synthetic images that cannot be distinguished from real ones, enabling the production of "
        "highly detailed, realistic images."
    ) in polished
    assert polished.count("highly detailed, realistic images.") == 1
    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">' in polished
    assert '<p class="z2m-figure-caption">Fig. 1 | Overview of the GAI development pipeline.</p>' in polished


def test_polish_html_document_repairs_sentence_split_by_box_then_figure() -> None:
    html = (
        "<html><body>"
        "<p>Since 2008, studies have used synthetic data to replace missing</p>"
        "<h4>BOX 1</h4>"
        "<h3>Glossary of key terms</h3>"
        "<p><b>Agentic model:</b> an AI model capable of autonomous decision-making.</p>"
        "<p><b>Transformer model:</b> a neural-network-based architecture.</p>"
        "<p>data, a common issue. The first network is trained by the second to generate synthetic images that cannot be distinguished from real ones, enabling the production of</p>"
        "<p><img src=\"fig1.png\"/></p>"
        "<p><b>Fig. 1</b> | Overview of the GAI development pipeline.</p>"
        "<p>highly detailed, realistic images.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert (
        "Since 2008, studies have used synthetic data to replace missing "
        "data, a common issue. The first network is trained by the second to generate synthetic images "
        "that cannot be distinguished from real ones, enabling the production of highly detailed, realistic images."
    ) in flat
    assert flat.count("highly detailed, realistic images.") == 1
    assert re.search(r'<div id="box-1" class="[^"]*\bz2m-box-unit\b', polished)
    assert '<h4 class="z2m-box-heading">BOX 1</h4>' in polished
    assert re.search(r'<div id="fig-1" class="[^"]*\bz2m-figure-unit\b', polished)


def test_polish_html_document_repairs_sentence_split_across_affiliation_block() -> None:
    html = (
        "<html><body>"
        "<p>Subsequently, multimodal foundation models (for example, GPT-5, Gemini 2.5 Pro,</p>"
        "<p>1Singapore National Eye Centre, Singapore Eye Research Institute, Singapore, Singapore. "
        "2AI Office, Singapore Health Services, Singapore, Singapore. "
        "3Nuffield Department of Clinical Neurosciences, University of Oxford, Oxford, UK. "
        "4Ophthalmology and Visual Sciences Academic Clinical Program, Duke-NUS Medical School, Singapore, Singapore. "
        "5Department of Ophthalmology, Byers Eye Institute, Stanford, CA, USA. "
        "15These authors contributed equally: Zhen Ling Teo, Arun James Thirunavukarasu. "
        "e-mail: daniel.ting@duke-nus.edu.sg</p>"
        "<p>Claude 4 and Grok 4), which can process images in addition to text, have increased utility.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert (
        "Subsequently, multimodal foundation models (for example, GPT-5, Gemini 2.5 Pro, "
        "Claude 4 and Grok 4), which can process images in addition to text, have increased utility."
    ) in flat
    assert "Singapore National Eye Centre" in polished
    assert "daniel.ting@duke-nus.edu.sg" in polished


def test_polish_html_document_repairs_sentence_split_across_affiliation_block_without_comma() -> None:
    html = (
        "<html><body>"
        "<p>Subsequently, multimodal foundation models (for example, GPT-5 and Gemini 2.5 Pro</p>"
        "<p>1Singapore National Eye Centre, Singapore Eye Research Institute, Singapore, Singapore. "
        "2AI Office, Singapore Health Services, Singapore, Singapore. "
        "3Nuffield Department of Clinical Neurosciences, University of Oxford, Oxford, UK. "
        "4Department of Ophthalmology and Optometry, Medical University of Vienna, Vienna, Austria. "
        "15These authors contributed equally: Zhen Ling Teo, Arun James Thirunavukarasu. "
        "e-mail: daniel.ting@duke-nus.edu.sg</p>"
        "<p>Claude 4 and Grok 4), which can process images in addition to text.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert (
        "Subsequently, multimodal foundation models (for example, GPT-5 and Gemini 2.5 Pro "
        "Claude 4 and Grok 4), which can process images in addition to text."
    ) in flat
    assert "Singapore National Eye Centre" in polished
    assert "daniel.ting@duke-nus.edu.sg" in polished


def test_polish_html_document_marks_affiliation_block_with_style_class() -> None:
    html = (
        "<html><body>"
        "<p>1Singapore National Eye Centre, Singapore Eye Research Institute, Singapore, Singapore. "
        "2AI Office, Singapore Health Services, Singapore, Singapore. "
        "3Nuffield Department of Clinical Neurosciences, University of Oxford, Oxford, UK. "
        "4Department of Ophthalmology and Optometry, Medical University of Vienna, Vienna, Austria. "
        "15These authors contributed equally: Zhen Ling Teo, Arun James Thirunavukarasu. "
        "e-mail: daniel.ting@duke-nus.edu.sg</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    assert "z2m-affiliations" in polished
    assert "border-top: 1px solid" in polished
    assert "border-bottom: 1px solid" in polished


def test_polish_html_document_keeps_panel_caption_continuation_inside_figure_unit() -> None:
    html = (
        "<html><body>"
        "<p><img src=\"fig2.jpg\"/></p>"
        "<p><span id=\"page-17-0\"></span>Figure 2. "
        "<b>Microfabrication of Steeltrode on commercially available stainless steel substrate.</b></p>"
        "<p block-type=\"Text\"><b>a</b> Effect of SU-8 and PDMS-Parylene C based planarization. "
        "<b>b</b> Process flow for fabrication of steeltrode with SU-8 insulation. "
        "<b>c</b> Process flow for fabrication of steeltrode with bi-layer metal traces. "
        "<b>d</b> Schematic cross section showing different layers of steeltrode.</p>"
        "<p>To ensure the flexibility of tether cable, the insulation material needs low flexural modulus.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    wrapper_start = polished.index('<div id="fig-2" class="z2m-float-unit z2m-figure-unit">')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert "Figure 2." in wrapper
    assert "Effect of SU-8" in wrapper
    assert "Process flow for fabrication" in wrapper
    assert 'class="z2m-figure-caption"' in wrapper
    assert "Effect of SU-8" not in after_wrapper
    assert "To ensure the flexibility" in after_wrapper


def test_polish_html_document_keeps_multi_image_single_caption_inside_figure_unit() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig4a.jpg"/></p>'
        '<p><img src="fig4b.jpg"/></p>'
        "<p>Figure 4. Experimental and computational models show the influence of flow rate.</p>"
        "<p>Text after the figure.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    wrapper_start = polished.index('<div id="fig-4" class="z2m-float-unit z2m-figure-unit">')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert 'src="fig4a.jpg"' in wrapper
    assert 'src="fig4b.jpg"' in wrapper
    assert "Figure 4. Experimental" in wrapper
    assert "Figure 4. Experimental" not in after_wrapper
    assert "Text after the figure." in after_wrapper


def test_polish_html_document_absorbs_external_matching_figure_caption() -> None:
    html = (
        "<html><body>"
        '<div id="fig-5-24" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig524.jpg"/></p></div>'
        '<p class="z2m-figure-caption"><a href="#fig-5-24" class="z2m-fig-link">Рис. 5.24</a> '
        "<b>Сферическая аберрация</b></p>"
        '<p><img src="fig525.jpg"/></p>'
        "<p>Хроматическая аберрация:</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en", polish_language="ru")
    wrapper_start = polished.index('<div id="fig-5-24" class="z2m-float-unit z2m-figure-unit">')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert 'src="fig524.jpg"' in wrapper
    assert "Рис. 5.24" in wrapper
    assert "Сферическая аберрация" in wrapper
    assert "Сферическая аберрация" not in after_wrapper
    assert 'src="fig525.jpg"' in after_wrapper


def test_polish_html_document_absorbs_delayed_caption_after_image_run() -> None:
    html = (
        "<html><body>"
        '<div id="fig-6-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="shutter-a.jpg"/></p></div>'
        '<p><img src="shutter-b.jpg"/></p>'
        '<div id="fig-6-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="shutter-c.jpg"/></p></div>'
        '<p class="z2m-figure-caption"><a href="#fig-6-3" class="z2m-fig-link">Рис. 6.3</a> '
        "<b>Центральный затвор</b></p>"
        "<p>Фокальный затвор начинается здесь.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en", polish_language="ru")
    wrapper_start = polished.index('<div id="fig-6-3" class="z2m-float-unit z2m-figure-unit">')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert 'src="shutter-a.jpg"' in wrapper
    assert 'src="shutter-b.jpg"' in wrapper
    assert 'src="shutter-c.jpg"' in wrapper
    assert "Рис. 6.3" in wrapper
    assert "Центральный затвор" not in after_wrapper
    assert "Фокальный затвор начинается здесь." in after_wrapper


def test_polish_html_document_absorbs_caption_after_missing_warning_unit_with_see_ref() -> None:
    html = (
        "<html><body>"
        '<div id="fig-9-6" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-figure-target">см. рис. 9.6 Figure 9-6 image was not extracted into this HTML.</p>'
        "</div>"
        '<p class="z2m-figure-caption"><a href="#fig-9-6" class="z2m-fig-link">Рис. 9.6</a> '
        "<b>Перемешивание листовой пленки в рамках</b></p>"
        "<p>Цикл следующий.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en", polish_language="ru")
    wrapper_start = polished.index('<div id="fig-9-6"')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert "Figure 9-6 image was not extracted" in wrapper
    assert "Рис. 9.6" in wrapper
    assert "Перемешивание листовой пленки" in wrapper
    assert "Перемешивание листовой пленки" not in after_wrapper
    assert "Цикл следующий." in after_wrapper


def test_polish_html_document_absorbs_spaced_decimal_figure_caption() -> None:
    html = (
        "<html><body>"
        '<div id="fig-3-9" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig39a.jpg"/></p></div>'
        '<p><img src="fig39b.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig. 3 .9. Calibration curves.</p>'
        "<p>After the figure.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    wrapper_start = polished.index('<div id="fig-3-9" class="z2m-float-unit z2m-figure-unit">')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert 'src="fig39a.jpg"' in wrapper
    assert 'src="fig39b.jpg"' in wrapper
    assert "Figure 3.9. Calibration curves." in wrapper
    assert "Calibration curves" not in after_wrapper
    assert "After the figure." in after_wrapper


def test_polish_html_document_links_caption_with_decimal_leading_text_to_base_figure() -> None:
    html = (
        "<html><body>"
        "<p>In Fig. 17 the virtual model is depicted. In Fig. 17 the model is split.</p>"
        '<p><img src="fig17.jpg"/></p>'
        "<p>Fig. 17. 2.5D virtual model obtained by applying the proposed methodology.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-17"' in polished
    assert 'id="fig-17-2-5"' not in polished
    assert polished.count('href="#fig-17"') == 2
    assert "Figure 17. 2.5D virtual model" in polished


def test_polish_html_document_repairs_sentence_split_by_image_and_caption_paragraphs() -> None:
    html = (
        "<html><body>"
        "<p>Also, this is an analog</p>"
        "<p><img src=\"fig1.jpg\"/></p>"
        "<p id=\"fig-1\">Fig. 1. The passive sensor model.</p>"
        "<p>circuit with limited frequency resolution.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "Also, this is an analog circuit with limited frequency resolution." in polished
    assert polished.count("circuit with limited frequency resolution.") == 1
    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">' in polished
    assert '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>' in polished
    assert '<p class="z2m-figure-caption">Fig. 1. The passive sensor model.</p>' in polished


def test_polish_html_document_repairs_sentence_split_by_wrapped_float_unit() -> None:
    html = (
        "<html><body>"
        '<p>All patients evaluated a questionnaire validated for</p>'
        '<p><span id="page-2-0"></span><img src="fig1.jpg"/></p>'
        '<p><b>Fig 1. Diagram of patient selection.</b></p>'
        '<p block-type="Text">the assessment of LUTS [10], before and after RARP.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 11))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "questionnaire validated for the assessment of LUTS" in flat
    assert flat.count("the assessment of LUTS") == 1
    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">' in polished


def test_polish_html_document_strips_running_header_inside_float_split() -> None:
    html = (
        "<html><body>"
        "<p>These factors and individual differences in lymphatic anatomy</p>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit"></div>'
        "<p>Combined Imaging in Breast Cancer were reduced by the self-controlled protocol.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert "lymphatic anatomy were reduced by the self-controlled protocol." in polished
    assert "Combined Imaging in Breast Cancer were reduced" not in polished
    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">' in polished


def test_polish_html_document_repairs_acronym_continuation_after_float() -> None:
    html = (
        "<html><body>"
        "<p>The results were obtained using the ICCD and EMCCD cameras, respectively, and the</p>"
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit"><p>Figure 4. Cameras.</p></div>'
        "<p>EMCCD camera gives a higher signal-to-noise ratio.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert "respectively, and the EMCCD camera gives a higher signal-to-noise ratio." in polished
    assert polished.count("EMCCD camera gives") == 1


def test_polish_html_document_strips_line_number_inside_float_split() -> None:
    html = (
        "<html><body>"
        "<p>The peak at about 284.9</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit"><p>Figure 2. XPS.</p></div>'
        "<p>35 eV suggests that carbon was present.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)

    assert repairs == 1
    assert "The peak at about 284.9 eV suggests that carbon was present." in polished
    assert "284.9 35 eV" not in polished


def test_polish_html_document_splits_trailing_table_note_before_float_continuation() -> None:
    html = (
        "<html><body>"
        "<p>Although this prior study qualified the device, in the absence of "
        "aSignificant, <i> p &lt; </i> 0.05.</p>"
        '<div id="table-iii" class="z2m-float-unit z2m-table-unit"><p>Table III. Standards.</p></div>'
        "<p>standards, it remains impractical for clinical use.</p>"
        "</body></html>"
    )

    polished, repairs = _repair_sentence_breaks_around_float_units(html)
    flat = " ".join(polished.split())

    assert repairs == 1
    assert "in the absence of standards, it remains impractical for clinical use." in flat
    assert '<p class="z2m-table-note">aSignificant, <i> p &lt; </i> 0.05.</p>' in polished
    assert "absence of aSignificant" not in flat


def test_polish_html_document_splits_embedded_table_caption_before_continuation() -> None:
    html = (
        "<html><body>"
        "<p>Although this prior study may have qualified the device, in the absence of "
        '<span id="page-9-0"> </span> TABLE III. A two-way analysis of variance.</p>'
        "<table><tbody><tr><td>SNR</td></tr></tbody></table>"
        "<p><span id=\"page-9-2\"> </span> aSignificant, <i> p &lt; </i> 0.05.</p>"
        "<p>standards, it remains impractical to qualify individual devices.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "in the absence of standards, it remains impractical to qualify individual devices." in flat
    assert "absence of <span id=\"page-9-0\"> </span> TABLE III" not in polished
    assert '<div id="table-iii" class="z2m-float-unit z2m-table-unit">' in polished
    assert '<p class="z2m-table-note"><span id="page-9-2"> </span> aSignificant' in polished


def test_polish_html_document_repairs_adjacent_running_header_split() -> None:
    html = (
        "<html><body>"
        "<p>Fresh lychee was purchased from a local market. After its skin</p>"
        '<p block-type="Text" class="z2m-front-matter">'
        "Journal of Materials Chemistry B Accepted Manuscrip was peeled, the lychee seed was taken out.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "After its skin was peeled, the lychee seed was taken out." in flat
    assert "Accepted Manuscrip was peeled" not in flat


def test_polish_html_document_strips_sup_line_number_in_adjacent_split() -> None:
    html = (
        "<html><body>"
        "<p>This work was supported by the National Natural Science</p>"
        "<p>Foundations of China and the Scientific</p>"
        "<p><sup>5</sup>Research Project of Guangxi Higher Learning.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "National Natural Science Foundations of China and the Scientific Research Project" in flat
    assert "<sup>5</sup>Research Project" not in polished


def test_polish_html_document_merges_body_tail_across_table_notes_and_figure() -> None:
    html = (
        "<html><body>"
        "<p>P values &lt;0.001 for all</p>"
        "<p><b>Table 1. Patient demographics.</b></p>"
        "<table><tbody><tr><td>A</td><td>B</td></tr></tbody></table>"
        "<p><sup>пїЅ</sup> : statistically significant</p>"
        "<p>Median value(IQR) or number of cases(%)</p>"
        "<p>Abbreviations RARP: robot-assisted radical prostatectomy</p>"
        "<p>CLSS: core lower urinary tract symptom score, QOL index: quality of life index</p>"
        '<p><a href="https://doi.org/10.1371/journal.pone.0275069.t001">'
        "https://doi.org/10.1371/journal.pone.0275069.t001</a></p>"
        '<p><img src="fig2.jpg"/></p>'
        "<p><b>Fig 2. Changes between pre- and post-RARP uroflowmetry parameters.</b></p>"
        "<p>three parameters). These tendencies were confirmed.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "P values &lt;0.001 for all three parameters). These tendencies were confirmed." in flat
    assert "QOL index: quality of life index three parameters" not in flat
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit' in polished
    assert '<div id="fig-2" class="z2m-float-unit z2m-figure-unit' in polished


def test_polish_html_document_marks_adjacent_float_units_as_one_visual_run() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig1.jpg"/></p>'
        '<p id="fig-1">Fig. 1. Architecture overview.</p>'
        '<p id="table-1">Table 1. Parameters.</p>'
        "<table><tbody><tr><td>A</td><td>B</td></tr></tbody></table>"
        "<p>Text after floats.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-float-run-start">' in polished
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit z2m-float-run-end">' in polished
    assert ".z2m-float-unit.z2m-float-run-start" in polished
    assert ".z2m-float-unit.z2m-float-run-end" in polished
    assert "Text after floats." in polished


def test_polish_html_document_keeps_wrapped_caption_out_of_body_merge() -> None:
    html = (
        "<html><body>"
        "<p>Peripheral nerves are complex cable-like</p>"
        "<p><img src=\"fig2.jpg\"/></p>"
        "<p><b> Fig. 2 </b> A cross-sectional diagram.</p>"
        "<p>vary in diameter, both of which affect conduction velocity.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "Peripheral nerves are complex cable-like vary in diameter" in flat
    assert "A cross-sectional diagram. vary in diameter" not in flat
    assert 'id="fig-2"' in polished


def test_polish_html_document_merges_et_al_year_split_across_figure_gap() -> None:
    html = (
        "<html><body>"
        "<p>The device was introduced by Choi et al.</p>"
        "<p><img src=\"fig12.jpg\"/></p>"
        "<p>Fig. 12. Examples of thin film intraneural interfaces. Copyright 2018.</p>"
        "<p>2024 a, b). Each shank was inserted at 45° with respect to the previous one.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "introduced by Choi et al. 2024 a, b). Each shank" in flat
    assert "Figure 12. Examples of thin film intraneural interfaces." in flat


def test_polish_html_document_does_not_merge_correspondence_with_body_after_figure_gap() -> None:
    html = (
        "<html><body>"
        "<p><sup>*</sup> Correspondence: Ellis Meng ellis.meng@usc.edu</p>"
        "<p><img src=\"fig1.jpg\"/></p>"
        "<p>Fig. 1. Graphical overview.</p>"
        "<p>al. 2022). Therefore, stimulation can cause off-target effects.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "ellis.meng@usc.edu al. 2022" not in flat
    assert "Correspondence: Ellis Meng ellis.meng@usc.edu" in flat


def test_polish_html_document_does_not_append_body_after_ocr_caption() -> None:
    html = (
        "<html><body>"
        "<h1>A 96ch flexible surface electrode array Fabricated electrode Thickness = 20um "
        "20 mm Stimulating electrode Gold Silicon substrate Aluminium mask</h1>"
        "<p>FIGURE 1 | Electrode fabrication and experimental paradigm.</p>"
        "<p>(0.12 mm2). Electrode fabrication began with parylene deposition.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "A 96ch flexible surface electrode array" not in flat
    assert "Figure 1. Electrode fabrication and experimental paradigm." in flat
    assert "experimental paradigm. (0.12 mm2)" not in flat
    assert "(0.12 mm2). Electrode fabrication began" in flat


def test_polish_html_document_repairs_cross_mixed_prose_and_figure_caption() -> None:
    html = (
        "<html><body>"
        "<p>Similar processes can be applied to develop multimodal foundation models. "
        "An early example is RETFound, which was trained in a 'fill in the blank' "
        "to evaluate for aspects such as accuracy, relevance and bias; and (4) deployment, "
        "which are crucial steps for clinical translation. CT, computed tomography; MRI, "
        "magnetic resonance imaging; CLIP, contrastive language-image pretraining; "
        "RAG, retrieval-augmented generation.</p>"
        "<p><img src=\"fig2.jpg\"/></p>"
        "<p><strong>Fig. 2</strong> | <strong>GAI development pipeline based on specific modalities.</strong> "
        "The key steps include: (1) pretraining; (2) fine-tuning; (3) reinforcement learning (required) "
        "\\\\ image-modeling task in which the model was exposed to fundus photographs with missing portions "
        "and tasked with reconstructing the missing pixels. Other foundation models were developed as well.</p>"
        "<p>Early anecdotal evidence and recent studies are described below.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert (
        "which was trained in a 'fill in the blank' image-modeling task in which the model was exposed"
    ) in flat
    assert "and (4) deployment, which are crucial steps for clinical translation." in flat
    assert "Fig. 2" in flat
    assert "(1) pretraining; (2) fine-tuning; (3) reinforcement learning (required)" in flat
    assert "\\\\ image-modeling task" not in polished
    assert "to evaluate for aspects such as accuracy, relevance and bias; and (4) deployment" in polished
    assert (
        "which was trained in a 'fill in the blank' to evaluate for aspects such as accuracy, relevance and bias"
        not in polished
    )
    assert flat.count("Early anecdotal evidence and recent studies are described below.") == 1


def test_polish_html_document_repairs_caption_suffix_left_and_body_tail_right() -> None:
    html = (
        "<html><body>"
        "<p>An early example is RETFound, which was trained in a 'fill in the blank' "
        "to evaluate for aspects such as accuracy, relevance and bias; and (4) deployment, "
        "which are crucial steps for clinical translation. CT, computed tomography; MRI, "
        "magnetic resonance imaging; CLIP, contrastive language-image pretraining; "
        "RAG, retrieval-augmented generation.</p>"
        "<p><img src=\"fig2.jpg\"/></p>"
        "<p><strong>Fig. 2</strong> | <strong>GAI development pipeline based on specific modalities.</strong> "
        "The key steps include: (1) pretraining; (2) fine-tuning; "
        "(3) reinforcement learning, which relies on human input (required)</p>"
        "<p>image-modeling task in which the model was exposed to fundus photographs.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "trained in a 'fill in the blank' image-modeling task" in flat
    assert "to evaluate for aspects such as accuracy, relevance and bias; and (4) deployment" in flat
    assert "Fig. 2" in flat
    assert "human input (required)" in flat
    assert "human input (required) image-modeling" not in flat


def test_polish_html_document_repairs_sentence_split_by_long_figure_chain() -> None:
    html = (
        "<html><body>"
        "<p>This</p>"
        "<p><img src=\"f4.jpg\"/></p>"
        "<p id=\"fig-4\">Fig. 4. Passive sensor model.</p>"
        "<p><img src=\"f5.jpg\"/></p>"
        "<p id=\"fig-5\">Fig. 5. Impedance and phase frequency response.</p>"
        "<p><img src=\"f6.jpg\"/></p>"
        "<p id=\"fig-6\">Fig. 6. Measurement principle.</p>"
        "<p>equivalent resistor changes the system's impedance.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "This equivalent resistor changes the system's impedance." in polished
    assert polished.count("equivalent resistor changes the system's impedance.") == 1
    assert '<p class="z2m-figure-caption">Fig. 6. Measurement principle.</p>' in polished


def test_polish_html_document_repairs_sentence_split_with_table_caption_gap() -> None:
    html = (
        "<html><body>"
        "<p>In our final prototype,</p>"
        "<p><img src=\"fig9.jpg\"/></p>"
        "<p id=\"fig-9\">Fig. 9. Final sensor mounted on the PCB.</p>"
        "<p>Table I. Parameters for two antennas.</p>"
        "<p>an integrated half-wave rectifier measures the output envelope.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert (
        "In our final prototype, an integrated half-wave rectifier measures the output envelope."
    ) in polished
    assert polished.count("an integrated half-wave rectifier measures the output envelope.") == 1
    assert '<div id="table-i" class="z2m-float-unit z2m-table-unit' in polished
    assert '<p class="z2m-table-caption">Таблица I. Parameters for two antennas.</p>' in polished


def test_polish_html_document_repairs_sentence_split_across_table_and_formula_note() -> None:
    html = (
        "<html><body>"
        "<p>Fig. 16 shows the k factor for two antenna with distance varying based on</p>"
        "<h4>TABLE III Antenna Parameters</h4>"
        "<table><tbody><tr><td>Parameter</td><td>Value</td></tr></tbody></table>"
        "<p>\\(f_{brain}\\) is the function which describes localized tissue properties.</p>"
        "<p>sizes. A small antenna features higher k factor at close distance.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert (
        "Fig. 16 shows the k factor for two antenna with distance varying based on "
        "sizes. A small antenna features higher k factor at close distance."
    ) in polished
    # Formula is now statically rendered (KaTeX); the original TeX is preserved
    # verbatim in data-z2m-tex for HTML→Markdown recovery, and the note prose
    # must still follow the rendered formula in the same paragraph.
    assert 'data-z2m-tex="\\(f_{brain}\\)"' in polished
    assert "</span> is the function which describes localized tissue properties." in polished
    assert '<div id="table-iii" class="z2m-float-unit z2m-table-unit">' in polished
    assert '<h4 class="z2m-table-caption">TABLE III Antenna Parameters</h4>' in polished
    assert "<table><tbody><tr><td>Parameter</td><td>Value</td></tr></tbody></table>" in polished


def test_polish_html_document_splits_table_note_from_body_continuation() -> None:
    html = (
        "<html><body>"
        "<p>Fig. 16 shows the k factor for two antenna with distance varying based on "
        "the antennas' and sensor's</p>"
        "<h4>TABLE III Antenna Parameters</h4>"
        "<table><tbody><tr><td>Parameter</td><td>Value</td></tr></tbody></table>"
        "<p>\\(f_{brain}\\) is the function which describes localized tissue permittivity "
        "and conductivity of the human head sizes. A small antenna features higher k factor "
        "at close distance.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert (
        "based on the antennas' and sensor's sizes. "
        "A small antenna features higher k factor at close distance."
    ) in flat
    assert "conductivity of the human head. sizes." not in flat
    assert '<div id="table-iii" class="z2m-float-unit z2m-table-unit">' in polished
    assert '<p class="z2m-table-note">' in polished
    table_unit = polished[
        polished.index('<div id="table-iii" class="z2m-float-unit z2m-table-unit">') :
        polished.index("</div>", polished.index('<div id="table-iii" class="z2m-float-unit z2m-table-unit">'))
    ]
    assert 'data-z2m-tex="\\(f_{brain}\\)"' in table_unit
    assert "</span> is the function" in table_unit


def test_polish_html_document_keeps_parenthetical_sample_size_table_note() -> None:
    html = (
        "<html><body>"
        "<p>With 33 scores, the COSMIN box for criterion validity was scored the most, "
        "followed by 8 scores for reliability, 6 for hypothesis testing and 4 scores "
        "for measurement</p>"
        "<table><tbody><tr><th>Table 2</th><th>Criteria</th></tr></tbody></table>"
        "<p>*In order to meet a level of evidence, all three criteria have to be met "
        "(consistency, methodological quality and sample size). Adapted from van "
        "Tulder et al, 20.</p>"
        "<p><img src=\"figure1.jpg\"/></p>"
        "<p id=\"fig-1\">Figure 1 PRISMA flow chart.</p>"
        "<p>error. In none of the studies internal consistency was scored.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "4 scores for measurement error. In none of the studies" in flat
    assert (
        "*In order to meet a level of evidence, all three criteria have to be met "
        "(consistency, methodological quality and sample size). Adapted from van "
        "Tulder et al, 20."
    ) in flat
    assert "measurement size). Adapted from" not in flat
    assert "sample</p>" not in flat


def test_polish_html_document_repairs_sentence_split_when_right_starts_with_comma() -> None:
    html = (
        "<html><body>"
        "<p>distance varying based on</p>"
        "<p><img src=\"fig16.jpg\"/></p>"
        "<p id=\"fig-16\">Fig. 16. Signal strength vs distance.</p>"
        "<p>, given the antennas' and sensor's sizes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "distance varying based on, given the antennas' and sensor's sizes." in polished
    assert "based on , given" not in polished


def test_polish_html_document_repairs_page_break_split_with_parenthesis() -> None:
    html = (
        "<html><body>"
        "<p>The reader can work over a wide frequency range</p>"
        "<p>(35 MHz to 2.7 GHz), which gives freedom to design different sensors.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert (
        "The reader can work over a wide frequency range "
        "(35 MHz to 2.7 GHz), which gives freedom to design different sensors."
    ) in polished


def test_polish_html_document_does_not_merge_page_break_reference_item() -> None:
    html = (
        "<html><body>"
        "<p>Discussion about prior art and comparison</p>"
        "<p>1. A. Author, \"Reference title\", Journal, 2020.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "<p>Discussion about prior art and comparison</p>" in polished
    assert "<p>1. A. Author, \"Reference title\", Journal, 2020.</p>" in polished


def test_polish_html_document_repairs_sentence_split_when_right_starts_uppercase() -> None:
    html = (
        "<html><body>"
        "<p>To facilitate observation, data is sampled by the Usb-6009 Data</p>"
        "<p><img src=\"fig10.jpg\"/></p>"
        "<p id=\"fig-10\">Fig. 10. Measurement setup.</p>"
        "<p>Acquisition Card (National Instruments).</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert (
        "To facilitate observation, data is sampled by the Usb-6009 Data "
        "Acquisition Card (National Instruments)."
    ) in polished
    assert polished.count("Acquisition Card (National Instruments).") == 1


def test_polish_html_document_repairs_sentence_split_with_dehyphenation() -> None:
    html = (
        "<html><body>"
        "<p>SPI bytes times 34 bytes per regis-</p>"
        "<p><img src=\"fig12.jpg\"/></p>"
        "<p id=\"fig-12\">Fig. 12. Resonant frequency shift.</p>"
        "<p>ter (32 bytes data per register) times 6 registers.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "SPI bytes times 34 bytes per register (32 bytes data per register) times 6 registers." in polished
    assert "regis-ter" not in polished


def test_polish_html_document_reorders_table_after_formula_context() -> None:
    html = (
        "<html><body>"
        "<p>A moving average, which works as a low pass filter removed the noise:</p>"
        "<p>TABLE IV Comparison of state of arts.</p>"
        "<table><tbody><tr><td>Range</td><td>Distance</td></tr></tbody></table>"
        "<p>\\[Ly_s(i) = \\frac{1}{2N+1}(y(i+N) + \\dots + y(i-N))\\]</p>"
        "<p>We chose N = 5.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)
    flat = " ".join(polished.split())

    assert flat.find("A moving average, which works as a low pass filter removed the noise:") < flat.find("\\[Ly_s(i)")
    assert flat.find("\\[Ly_s(i)") < flat.find("We chose N = 5.")
    assert flat.find("We chose N = 5.") < flat.find("Таблица IV. Comparison of state of arts.")


def test_polish_html_document_reorders_table_after_formula_with_equation_row_wrapper() -> None:
    html = (
        "<html><body>"
        "<p>A moving average, which works as a low pass filter removed the noise:</p>"
        "<p>TABLE IV Comparison of state of arts.</p>"
        "<table><tbody><tr><td>Range</td><td>Distance</td></tr></tbody></table>"
        "<div class=\"z2m-equation-row\"><span class=\"z2m-eq-lhs\"></span>"
        "<p>\\[Ly_s(i) = \\frac{1}{2N+1}(y(i+N) + \\dots + y(i-N))\\]</p>"
        "<span class=\"z2m-eq-num\">(9)</span></div>"
        "<p>We chose N = 5.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)
    flat = " ".join(polished.split())

    assert flat.find("\\[Ly_s(i)") < flat.find("We chose N = 5.")
    assert flat.find("We chose N = 5.") < flat.find("Таблица IV. Comparison of state of arts.")


def test_polish_html_document_repairs_sentence_split_across_box_block() -> None:
    html = (
        "<html><body>"
        "<p>Since 2008 there has been a growing prevalence of studies to replace missing</p>"
        "<h2>BOX 1</h2>"
        "<h3>Glossary of key terms</h3>"
        "<p>Agentic model: description.</p>"
        "<p>Transformer model: description.</p>"
        "<p>data—a common issue in clinical research.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)
    flat = " ".join(polished.split())

    assert (
        "Since 2008 there has been a growing prevalence of studies to replace missing "
        "data—a common issue in clinical research."
    ) in flat
    assert '<div id="box-1" class="z2m-float-unit z2m-box-unit">' in polished
    assert '<h2 class="z2m-box-heading">BOX 1</h2>' in polished
    assert '<h3 class="z2m-box-body">Glossary of key terms</h3>' in polished


def test_polish_html_document_does_not_reorder_table_without_formula_context() -> None:
    html = (
        "<html><body>"
        "<p>Comparison summary:</p>"
        "<p>TABLE IV Comparison of state of arts.</p>"
        "<table><tbody><tr><td>Range</td><td>Distance</td></tr></tbody></table>"
        "<p>Regular paragraph after table.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)
    flat = " ".join(polished.split())

    assert flat.find("Таблица IV. Comparison of state of arts.") < flat.find("Regular paragraph after table.")


def test_polish_html_document_does_not_merge_after_finished_sentence() -> None:
    html = (
        "<html><body>"
        "<p>The amplitude value is sent back to the microcontroller for signal processing.</p>"
        "<figure><img src=\"f8.png\"/></figure>"
        "<p>The system then records data in a text file.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "<p>The amplitude value is sent back to the microcontroller for signal processing.</p>" in polished
    assert "<p>The system then records data in a text file.</p>" in polished


def test_polish_html_document_does_not_merge_across_regular_middle_paragraph() -> None:
    html = (
        "<html><body>"
        "<p>The first network is trained by the second to generate synthetic images</p>"
        "<p>This is just a normal paragraph, not a figure caption.</p>"
        "<p>that cannot be distinguished from real ones.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html)

    assert "<p>The first network is trained by the second to generate synthetic images</p>" in polished
    assert "<p>that cannot be distinguished from real ones.</p>" in polished


def test_polish_html_document_repairs_split_url_before_autolink() -> None:
    html = (
        "<html><body>"
        "<p>Preprint at https://doi.org/10.48550/ arXiv.2408.06292</p>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert 'href="https://doi.org/10.48550/arXiv.2408.06292"' in polished


def test_polish_html_document_repairs_chained_page_boundary_continuations() -> None:
    html = (
        "<html><body>"
        "<p>According to the trajectory map, D3, D4, and D5 were separated by approximately</p>"
        "<p>one channel interval. Thus, there is much potential for improvement in terms of trajectory separation and</p>"
        "<p>prediction accuracy when using electrode arrays with a higher density.</p>"
        "<p>In this study, we were unable to clearly determine the efficacy of high-density electrodes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert (
        "According to the trajectory map, D3, D4, and D5 were separated by approximately "
        "one channel interval. Thus, there is much potential for improvement in terms of trajectory separation and "
        "prediction accuracy when using electrode arrays with a higher density."
    ) in polished
    assert polished.count("prediction accuracy when using electrode arrays") == 1
    assert "<p>In this study, we were unable" in polished


def test_polish_html_document_repairs_dangling_discourse_marker_continuation() -> None:
    html = (
        "<html><body>"
        "<p>Foresight 2 exhibits superior performance over a larger model. However,</p>"
        "<p>Foresight's development has been halted owing to concerns regarding unauthorized data use.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert (
        "Foresight 2 exhibits superior performance over a larger model. However, "
        "Foresight's development has been halted owing to concerns regarding unauthorized data use."
    ) in polished
    assert polished.count("Foresight's development has been halted") == 1


def test_polish_html_document_links_bracket_citations_to_references() -> None:
    """[N] bracket-style citations (common in IEEE papers) must become anchors."""
    html = (
        "<html><body>"
        "<p>Device performance [1], [3] and follow-up [2].</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>Ref one.</li>"
        "<li>Ref two.</li>"
        "<li>Ref three.</li>"
        "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in polished
    assert '<a href="#ref-2" class="z2m-ref-link">[2]</a>' in polished
    assert '<a href="#ref-3" class="z2m-ref-link">[3]</a>' in polished
    # References list items must carry IDs
    assert 'id="ref-1"' in polished
    assert 'id="ref-3"' in polished


def test_polish_html_document_keeps_single_citation_style_in_bracket_numeric_article() -> None:
    html = (
        "<html><body>"
        "<p>Prior museum accessibility work [1] and user studies [2] support the framework.</p>"
        "<p>A stray translated marker<sup>3</sup> should not become a second citation style.</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>Ref one.</li>"
        "<li>Ref two.</li>"
        "<li>Ref three.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in body
    assert '<a href="#ref-2" class="z2m-ref-link">[2]</a>' in body
    assert '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>' not in body
    assert "marker<sup>3</sup> should not become" in body


def test_polish_html_document_ids_standalone_reference_paragraphs() -> None:
    html = (
        "<html><body>"
        "<p>Prior museum accessibility work [1] and later network graphics [50] are relevant.</p>"
        "<h4>References</h4>"
        "<p>1. Luo Y. Tangible museum exhibits and accessibility. Journal of Access. 2019.</p>"
        "<ul>"
        "<li>2. Brule E. Assistive technologies for museums. 2020.</li>"
        "</ul>"
        "<p>50. Yang S. Network graphics for interactive cultural heritage. 2021.</p>"
        "<ul>"
        "<li>51. Engel C. Haptic interfaces in exhibitions. 2022.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )

    assert '<p id="ref-1">' in polished
    assert '<p id="ref-50">' in polished
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in polished
    assert '<a href="#ref-50" class="z2m-ref-link">[50]</a>' in polished


def test_polish_html_document_merges_unnumbered_reference_continuation() -> None:
    html = (
        "<html><body>"
        "<p>Way and Barner, 1997 and Cantoni et al., 2018 describe tactile access.</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>Canny J. A computational approach to edge detection. IEEE TPAMI. 1986.</li>"
        '<li>Cantoni V, Lombardi L. "Art Masterpieces Accessibility for Blind and Visually Impaired</li>'
        '<li>People," in International Conference on Image Analysis and Processing. 2018.</li>'
        "<li>Carion N. End-to-end object detection with transformers. 2020.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="ref-2"' in polished
    assert "Visually Impaired People" in polished
    assert re.search(r'id="ref-3"[\s\S]{0,120}Carion N\.', polished) is not None
    assert re.search(r'id="ref-\d+">People,"', polished) is None


def test_polish_html_document_wraps_superscript_profile_page_ref_links() -> None:
    html = (
        "<html><body>"
        '<p>Rapid postvoiding<a href="#page-9-0">.1</a> Follow-up data <a href="#page-9-1">2-4</a> support it.</p>'
        "<h4>References</h4>"
        "<ul>"
        '<li><span id="page-9-0"></span>First reference.</li>'
        '<li><span id="page-9-1"></span>Second reference.</li>'
        "<li>Third reference.</li>"
        "<li>Fourth reference.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert 'postvoiding.<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>' in polished
    assert (
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a>-'
        '<a href="#ref-4" class="z2m-ref-link">4</a></sup>'
    ) in polished


def test_polish_html_document_links_bracket_refs_after_numbered_references_heading() -> None:
    html = (
        "<html><body>"
        '<p>The improved questionnaire <a href="#page-19-0">[1]</a> and annealing [11] are discussed.</p>'
        "<h2>VIII. References</h2>"
        "<p block-type=\"ListGroup\"><ul>"
        '<li block-type="ListItem"><span id="page-19-0"></span> [1] First technical report.</li>'
        + "".join(f'<li block-type="ListItem">[{i}] Reference {i}.</li>' for i in range(2, 11))
        + '<li block-type="ListItem"><span id="page-20-8"></span> [11] Hedar and Fukushima.</li>'
        + "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("VIII. References")]

    assert 'id="ref-1"' in polished
    assert 'id="ref-11"' in polished
    assert '[<a href="#ref-1" class="z2m-ref-link">1</a>] and annealing' in body
    assert '<a href="#ref-11" class="z2m-ref-link">[11]</a>' in body
    assert 'href="#page-19-0"' not in body
    assert "[1] First technical report" not in polished


def test_polish_html_document_links_bracket_citation_ranges_and_lists() -> None:
    html = (
        "<html><body>"
        "<p>Different functions [1-4], arrays [11, 12], and atlas [34, 35, 40\u201343].</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 44)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    for ref_id in (1, 4, 11, 12, 34, 35, 40, 43):
        assert f'href="#ref-{ref_id}"' in polished


def test_polish_html_document_relinks_existing_anchor_inside_bracket_citation_list() -> None:
    html = (
        "<html><body>"
        '<p>SIROFs are used for stimulation of the visual cortex [ 10, 12 , '
        '<a href="#ref-16" class="z2m-ref-link">17</a>].</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 18)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<a href="#ref-10" class="z2m-ref-link">10</a>' in polished
    assert '<a href="#ref-12" class="z2m-ref-link">12</a>' in polished
    assert '<a href="#ref-17" class="z2m-ref-link">17</a>' in polished
    assert 'visual cortex [<a href="#ref-10" class="z2m-ref-link">10</a>, <a href="#ref-12" class="z2m-ref-link">12</a>, <a href="#ref-17" class="z2m-ref-link">17</a>].' in polished
    assert '<a href="#ref-16" class="z2m-ref-link">17</a>' not in polished


def test_polish_html_document_links_valid_bracket_citations_inside_tables() -> None:
    html = (
        "<html><body>"
        "<table><tbody><tr><td>Utah array [ 28 \u2013 33 ]</td></tr></tbody></table>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 34)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#ref-28"' in polished
    assert 'href="#ref-33"' in polished


def test_polish_html_document_links_table_citations_split_by_br_tags() -> None:
    html = (
        "<html><body>"
        "<table><tbody><tr><td>Microprobes FMA [38,<br/>39]</td>"
        "<td>Atlas [34,<br/>35, 40\u201343]</td></tr></tbody></table>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 44)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    for ref_id in (34, 35, 38, 39, 40, 43):
        assert f'href="#ref-{ref_id}"' in polished
    assert "<br/>" in polished


def test_polish_html_document_rewrites_page_linked_bracket_citations() -> None:
    html = (
        "<html><body>"
        "<p>Michigan-style probes <a href=\"#page-12-0\"></a> "
        "[ <a href=\"#page-12-0\">37,</a> <a href=\"#page-12-0\">38</a>] "
        "and isolation <a href=\"#page-13-29\"></a> [ <a href=\"#page-13-29\">45]</a> "
        "and sensors [ <a href=\"#page-13-30\">46, 47</a>] remain relevant.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 48)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#page-12-0"' not in polished
    for ref_id in (37, 38, 45, 46, 47):
        assert f'href="#ref-{ref_id}"' in polished


def test_polish_html_document_rewrites_single_page_linked_bracket_citation_with_period() -> None:
    html = (
        "<html><body>"
        '<p>Prior work remains relevant <a href="#page-9-0">[17,18].</a></p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 19)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#page-9-0"' not in polished
    assert 'href="#ref-17"' in polished
    assert 'href="#ref-18"' in polished
    assert "]." in polished


def test_polish_html_document_unlinks_supplementary_page_refs_without_targets() -> None:
    html = (
        "<html><body>"
        '<p>Baseline demographics were stratified by parameter <a href="#page-9-0">(S1-S3</a> Tables).</p>'
        "<h4>References</h4><ol><li>Ref one.</li></ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "(S1-S3 Tables)" in polished
    assert 'href="#page-9-0"' not in polished


def test_polish_html_document_retargets_split_page_table_refs() -> None:
    html = (
        "<html><body>"
        '<p>LUTS worsened <a href="#page-3-0">(Table</a> 1, P value &lt;0.01).</p>'
        '<p>Four patients were male <a href="#page-3-1">(Table 1</a>).</p>'
        "<p><b>Table 1. Patient demographics.</b></p>"
        "<table><tbody><tr><td>A</td><td>B</td></tr></tbody></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<a href="#table-1" class="z2m-table-link">(Table 1,</a> P value' in polished
    assert '<a href="#table-1" class="z2m-table-link">(Table 1</a>)' in polished
    assert 'href="#page-3-0"' not in polished
    assert 'href="#page-3-1"' not in polished


def test_polish_html_document_moves_page_split_citation_to_previous_sentence() -> None:
    html = (
        "<html><body>"
        "<p>A comparable coating lost rigidity after 15-18 d due to bulk degradation, "
        "rather than surface degradation</p>"
        "<p block-type=\"Text\">[60]. The combination of easy-to-handle probes "
        "makes the coating suitable.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 61)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'surface degradation <a href="#ref-60" class="z2m-ref-link">[60]</a>.' in polished
    assert '<p block-type="Text">The combination of easy-to-handle probes' in polished
    assert '<p block-type="Text"><a href="#ref-60"' not in polished


def test_polish_html_document_does_not_link_author_affiliation_superscripts() -> None:
    html = (
        "<html><body>"
        "<h1>Generative artificial intelligence in medicine</h1>"
        "<p>Zhen Ling Teo <sup>1,2,15</sup>, Arun James Thirunavukarasu "
        "<sup>3,15</sup>, Robert J. T. Morris <sup>11,12</sup></p>"
        "<p>Clinical studies support this claim<sup>1,2</sup>.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 16)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    author_start = polished.rfind("<p", 0, polished.index("Zhen Ling Teo"))
    author_end = polished.index("Clinical studies")
    author_block = polished[author_start:author_end]

    assert "z2m-front-matter" in author_block
    assert 'href="#ref-' not in author_block
    assert 'href="#ref-1"' in polished[author_end:]
    assert 'href="#ref-2"' in polished[author_end:]


def test_polish_html_document_does_not_link_unicode_author_affiliation_markers() -> None:
    html = (
        "<html><body>"
        "<h1>Comparison between uroflowmetry and sonouroflowmetry</h1>"
        "<p>Jan Krhut,1,2 Marcel Gärtner, <sup>3</sup> Radek Sýkora, "
        "<sup>1</sup> Petr Hurtík, <sup>4</sup> Michal Burda,4 "
        "Libor Luňáček, <sup>1</sup> Katarína Zvarová5 and Peter Zvara2,6</p>"
        "<p><sup>1</sup>Department of Urology, University Hospital, "
        "<sup>2</sup>Department of Surgical Studies, Ostrava University, "
        "<sup>3</sup>Department of Obstetrics and Gynecology, University Hospital, "
        "<sup>4</sup>Institute for Research and Applications of Fuzzy Modeling; "
        "<sup>5</sup>Department of Physiology; and 6 Department of Surgery.</p>"
        "<p>UF is a widely used non-invasive test for evaluation of bladder emptying.<sup>1</sup></p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 7)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    author_start = polished.rfind("<p", 0, polished.index("Jan Krhut"))
    author_end = polished.index("Department of Urology")
    author_block = polished[author_start:author_end]
    body_start = polished.index("UF is a widely")

    assert "z2m-front-matter" in author_block
    assert 'href="#ref-' not in author_block
    assert 'href="#ref-1"' in polished[body_start:]


def test_polish_html_document_does_not_link_author_heading_affiliation_superscripts() -> None:
    html = (
        "<html><body>"
        "<h1>The Shape of the Urine Stream</h1>"
        "<h1>Andrew P. S. Wheeler<sup>1*</sup>, Samir Morad<sup>2</sup>, "
        "Noor Buchholz<sup>3</sup>, Martin M. Knight<sup>2</sup></h1>"
        "<p>Clinical observations support this model<sup>1</sup>.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 4)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    author_start = polished.index("Andrew P. S. Wheeler")
    author_block_start = polished.rfind("<h1", 0, author_start)
    author_block_end = polished.index("</h1>", author_start)
    author_block = polished[author_block_start:author_block_end]

    assert "z2m-front-matter" in author_block
    assert 'href="#ref-' not in author_block
    assert 'href="#ref-1"' in polished[author_block_end:]


def test_polish_html_document_protects_short_author_byline_heading_refs() -> None:
    html = (
        "<html><body>"
        "<h2>Do Electrode Properties Create a Problem?</h2>"
        "<h2><b>Matthew J. Nelson<sup>1,2</sup> and Pierre Pouget <sup>1</sup></b></h2>"
        "<p>Local field potential recordings remain useful<sup>1</sup>.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    author_start = polished.index("Matthew J. Nelson")
    author_block_start = polished.rfind("<h2", 0, author_start)
    author_block_end = polished.index("</h2>", author_start)
    author_block = polished[author_block_start:author_block_end]
    body_start = polished.index("Local field potential")

    assert "z2m-front-matter" in author_block
    assert 'href="#ref-' not in author_block
    assert 'href="#ref-1"' in polished[body_start:]


def test_polish_html_document_protects_single_author_byline_refs() -> None:
    html = (
        "<html><body>"
        "<h1>Development of visual Neuroprostheses: trends and challenges</h1>"
        "<p>Eduardo Fernandez<sup>1,2</sup></p>"
        "<h4><b>Abstract</b></h4>"
        "<p>Visual prostheses are implantable medical devices<sup>1</sup>.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    author_start = polished.index("Eduardo Fernandez")
    author_block_start = polished.rfind("<p", 0, author_start)
    author_block_end = polished.index("</p>", author_start)
    author_block = polished[author_block_start:author_block_end]
    body_start = polished.index("Visual prostheses")

    assert "z2m-front-matter" in author_block
    assert 'href="#ref-' not in author_block
    assert 'href="#ref-1"' in polished[body_start:]


def test_polish_html_document_protects_contribution_note_refs() -> None:
    html = (
        "<html><body>"
        "<h1>Protocol for a systematic review</h1>"
        "<p><sup>1</sup> contributed equally.</p>"
        "<h2>1. Introduction</h2>"
        "<p>Prior work motivates the protocol<sup>1</sup>.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    note_start = polished.index("contributed equally")
    note_block_start = polished.rfind("<p", 0, note_start)
    note_block_end = polished.index("</p>", note_start)
    note_block = polished[note_block_start:note_block_end]
    body_start = polished.index("Prior work")

    assert "z2m-front-matter" in note_block
    assert 'href="#ref-' not in note_block
    assert 'href="#ref-1"' in polished[body_start:]


def test_polish_html_document_keeps_body_titlecase_sup_citations_linked() -> None:
    html = (
        "<html><body>"
        "<h1>Visual prosthesis review</h1>"
        "<p>Visual Prostheses<sup>1</sup> are implantable devices.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body_start = polished.index("Visual Prostheses")
    body_end = polished.index("</p>", body_start)
    body_block = polished[body_start:body_end]

    assert "z2m-front-matter" not in body_block
    assert 'href="#ref-1"' in body_block


def test_polish_html_document_repairs_front_matter_marker_ocr() -> None:
    html = (
        "<html><body>"
        "<h1>Generative artificial intelligence in medicine</h1>"
        "<p>Zhen Ling Teo \u0412\u00a9 1,2,15, Arun James Thirunavukarasu \u00a9 3,15, "
        "Kabilan Elangovan 1,2, Haoran Cheng<sup>1,4</sup>, "
        "Robert J. T. Morris \u00a9 <sup>11,12</sup>, Nigam H. Shah 10 13, "
        "Curtis P. Langlotz 10 14 &amp; Daniel Shu Wei Ting 1.2.5</p>"
        "<p><sup>1</sup>Singapore National Eye Centre, Singapore, Singapore. "
        "<sup>2</sup>AI Office, Singapore Health Services, Singapore. "
        "3 Nuffield Department of Clinical Neurosciences, University of Oxford, UK. "
        "5Department of Ophthalmology, Byers Eye Institute, Stanford, USA. "
        "10 Academic Ophthalmology, University of Nottingham, UK. "
        "13Department of Medicine, Stanford University, USA. "
        "14Department of Radiology, Stanford University, USA. "
        "<sup>15</sup>These authors contributed equally: Zhen Ling Teo, Arun James Thirunavukarasu. "
        "e-mail: daniel.ting@duke-nus.edu.sg</p>"
        "<p>Clinical studies support this claim<sup>1,2</sup>.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 16)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    frontmatter_end = polished.index("Clinical studies")
    frontmatter = polished[:frontmatter_end]

    assert "\u00a9" not in frontmatter
    assert "Nigam H. Shah 10 13" not in frontmatter
    assert "Daniel Shu Wei Ting 1.2.5" not in frontmatter
    assert "Zhen Ling Teo<sup>1,2,15</sup>" in frontmatter
    assert "Robert J. T. Morris<sup>11,12</sup>" in frontmatter
    assert "Nigam H. Shah<sup>10,13</sup>" in frontmatter
    assert "Daniel Shu Wei Ting<sup>1,2,5</sup>" in frontmatter
    assert "<sup>3</sup>Nuffield Department" in frontmatter
    assert "<sup>10</sup>Academic Ophthalmology" in frontmatter
    assert "<sup>13</sup>Department of Medicine" in frontmatter
    assert 'href="#ref-' not in frontmatter
    assert 'href="#ref-1"' in polished[frontmatter_end:]
    assert 'href="#ref-2"' in polished[frontmatter_end:]


def test_polish_html_document_does_not_mark_late_body_paragraph_as_front_matter() -> None:
    html = (
        "<html><body>"
        "<h1>Generative artificial intelligence in medicine</h1>"
        "<p>Zhen Ling Teo <sup>1,2,15</sup>, Arun James Thirunavukarasu <sup>3,15</sup></p>"
        + "".join(f"<p>Body paragraph {i} describes the study.</p>" for i in range(45))
        + "<p>Intrinsic metrics include BLEU, ROUGE, METEOR, CIDEr, and Levenshtein distance "
        "for evaluation<sup>134-139</sup>.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 140)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    metric_start = polished.index("Intrinsic metrics")
    metric_end = polished.index("</p>", metric_start)
    metric_block = polished[metric_start:metric_end]

    assert "z2m-front-matter" not in metric_block
    assert 'href="#ref-134"' in metric_block
    assert 'href="#ref-139"' in metric_block


def test_polish_html_document_protects_page_footnote_marker_from_ref_linking() -> None:
    html = (
        "<html><body>"
        "<p>The material has low tensile strength<sup>1</sup>. Therefore, smaller interfaces are difficult.</p>"
        "<p><sup>1</sup> Tensile strength of a material is determined by the maximum stress under stretching "
        "or pulling it can withstand before breaking.</p>"
        "<p>Separate numeric citations still work<sup>2</sup>.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'class="z2m-footnote"' in body
    assert '<sup class="z2m-footnote-ref">1</sup>' in body
    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' in body


def test_polish_html_document_repairs_url_footnotes_split_as_page_links() -> None:
    html = (
        "<html><body>"
        '<p>The app is available onlin <a href="#page-4-1">e4</a> on mobile browsers.</p>'
        '<p>Participants are totally blin <a href="#page-4-3">d6.</a> Most were blind since birth.</p>'
        '<p><span id="page-4-1"></span><a href="https://example.org/app"><sup>4</sup>'
        "https://example.org/app</a> After the exploration, participants described the artwork "
        "and collected answers for the tested modality in a second study session.</p>"
        '<p><span id="page-4-3"></span><a href="www.ada.gov/lodblind.htm">6www.ada.gov/lodblind.htm</a></p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 7)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'class="z2m-footnote"' in body
    assert 'online<sup class="z2m-footnote-ref">4</sup>' in body
    assert 'blind<sup class="z2m-footnote-ref">6</sup>.' in body
    assert '</a></p><p block-type="Text">After the exploration' in body
    assert 'href="#page-4-1"' not in body
    assert 'href="#page-4-3"' not in body
    assert 'href="#ref-4"' not in body
    assert 'href="#ref-6"' not in body


def test_polish_html_document_does_not_link_scientific_numeric_contexts() -> None:
    html = (
        "<html><body>"
        "<p>The buffer had a pH of 7,4, the stimulus was (D2,4 mA), "
        "monkey 1: 7.5 kg, and recordings ran from week 8 to week 52. "
        "A parameter space ranged from 10\u2212 <sup>10</sup> to 10 <sup>2</sup>, "
        "and C = 10\u2212 <sup>1</sup>. "
        "The overlap integral was around 1.39 \u00d7 10<sup>-17</sup> "
        "M<sup>-1</sup> cm<sup>-1</sup> nm<sup>4</sup>.</p>"
        "<p>These issues 17,18. Careful handling is required.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 60)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    science_block = polished[polished.index("The buffer"):polished.index("These issues")]

    assert 'href="#ref-' not in science_block
    assert '10<sup class="z2m-unit-exp">-10</sup> to 10<sup class="z2m-unit-exp">2</sup>' in science_block
    assert 'C = 10<sup class="z2m-unit-exp">-1</sup>' in science_block
    assert (
        '1.39 \u00d7 10<sup class="z2m-unit-exp">-17</sup> '
        'M<sup class="z2m-unit-exp">-1</sup> '
        'cm<sup class="z2m-unit-exp">-1</sup> '
        'nm<sup class="z2m-unit-exp">4</sup>'
    ) in science_block
    assert 'href="#ref-17"' in polished
    assert 'href="#ref-18"' in polished


def test_polish_html_document_does_not_link_capitalized_version_labels_as_citations() -> None:
    html = (
        "<html><body>"
        "<p>Examples include Claude 4, Grok 4, and Widget 5). Another sentence cites prior work 4.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 8)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "Claude 4, Grok 4, and Widget 5)" in body
    assert "Claude <sup>" not in body
    assert "Grok <sup>" not in body
    assert "Widget <sup>" not in body
    assert 'href="#ref-4"' in body


def test_polish_html_document_discloses_caption_without_image_and_adds_target_style() -> None:
    html = (
        "<html><body>"
        "<p>The experiment is summarized in Fig. 1.</p>"
        "<p>Fig. 1. Caption survived, but the image did not.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert "z2m-missing-figure-warning" in polished
    assert "Figure 1 image was not extracted" in polished
    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">' in polished
    assert '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">' in polished
    assert '<p class="z2m-figure-caption">Figure 1. Caption survived, but the image did not.</p>' in polished
    assert "scroll-margin-top" in polished
    assert ":target" in polished


def test_polish_html_document_does_not_warn_when_empty_spacer_separates_image_and_caption() -> None:
    html = (
        "<html><body>"
        "<p>The experiment is summarized in Fig. 1.</p>"
        f'<p><img src="{_valid_tiny_png_data_url()}"/></p>'
        "<p></p>"
        "<p>Fig. 1. Caption belongs to the image above.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert re.search(r'<p\b[^>]*\bz2m-missing-figure-warning\b', polished) is None
    assert "image was not extracted into this HTML" not in polished


def test_polish_html_document_does_not_warn_when_short_label_separates_float_unit_and_caption() -> None:
    html = (
        "<html><body>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        f'<p class="z2m-figure-target"><img src="{_valid_tiny_png_data_url()}"/></p>'
        "</div>"
        "<p>Translated Image CDE [20] - Translated Image</p>"
        "<p>Figure 2: Leveraging monocular depth estimation models.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Figure 2 image was not extracted" not in polished
    assert re.search(r'<p\b[^>]*\bz2m-missing-figure-warning\b', polished) is None


def test_polish_html_document_drops_stale_same_label_missing_figure_warning() -> None:
    html = (
        "<html><body>"
        f'<p><img src="{_valid_tiny_png_data_url()}"/></p>'
        '<p class="z2m-missing-figure-warning" role="note">'
        "Figure 2 image was not extracted into this HTML. Please check the original PDF for the missing visual content."
        "</p>"
        "<p>Figure 2. Caption belongs to the image above.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Figure 2 image was not extracted" not in polished
    assert re.search(r'<p\b[^>]*\bz2m-missing-figure-warning\b', polished) is None
    assert 'id="fig-2"' in polished
    assert "z2m-missing-figure-unit" not in polished


def test_polish_html_document_does_not_warn_for_in_text_subfigure_sentence() -> None:
    html = (
        "<html><body>"
        f'<p><img src="{_valid_tiny_png_data_url()}"/></p>'
        "<p>Figure 9 (a) STL file and (b) physical prototype.</p>"
        "<p>Figure 9(a). Such an STL model is finally printed using a rapid prototyping machine.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Figure 9 image was not extracted" not in polished
    assert re.search(r'<p\b[^>]*\bz2m-missing-figure-warning\b', polished) is None


def test_polish_html_document_discloses_missing_figure_in_ru() -> None:
    html = (
        "<html><body>"
        "<p>Описание см. на Figure 1.</p>"
        "<p>Figure 1. Подпись есть, картинки нет.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="ru")

    assert "z2m-missing-figure-warning" in polished
    assert "Рисунок 1 не был извлечен" in polished
    assert "Figure 1" not in polished


def test_polish_html_document_treats_truncated_data_image_as_missing_figure() -> None:
    broken_jpeg = base64.b64encode(b"\xff\xd8\xff\xe0truncated").decode("ascii").rstrip("=")
    html = (
        "<html><body>"
        f'<p id="fig-5"><img src="data:image/jpeg;base64,{broken_jpeg}"/></p>'
        "<p>Figure 5. Caption survived, but the image is truncated.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert "Figure 5 image was not extracted" in polished
    assert "data:image/jpeg;base64" not in polished
    assert '<div id="fig-5" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">' in polished
    assert '<p class="z2m-figure-caption">Figure 5. Caption survived, but the image is truncated.</p>' in polished


def test_polish_html_document_marks_existing_unit_with_broken_data_image_as_missing() -> None:
    broken_jpeg = base64.b64encode(b"\xff\xd8\xff\xe0truncated").decode("ascii").rstrip("=")
    html = (
        "<html><body>"
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
        f'<p class="z2m-figure-target"><img src="data:image/jpeg;base64,{broken_jpeg}"/></p>'
        '<p class="z2m-figure-caption">Figure 5. Caption survived, but the image is truncated.</p>'
        "</div>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert "Figure 5 image was not extracted" in polished
    assert "z2m-missing-figure-unit" in polished
    assert "data:image/jpeg;base64" not in polished


def test_polish_html_document_bracket_citations_not_linked_inside_references() -> None:
    """The [N] markers inside the references list itself must NOT become double-links."""
    html = (
        "<html><body>"
        "<p>See [1] for details.</p>"
        "<h4>References</h4>"
        "<ul><li>[1] Smith et al. 2020.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    # The in-text [1] BEFORE the heading should be linked.
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in polished
    # The [1] INSIDE the list item (after the heading) must NOT be wrapped again.
    # It will have a z2m-ref-num span prepended, but the [1] text itself stays plain.
    ref_section_start = polished.index("References")
    assert '<a href="#ref-1"' not in polished[ref_section_start:]


def test_polish_html_document_converts_block_math_to_tex_delimiters() -> None:
    r"""<math display="block"> with LaTeX content must become \[...\]."""
    html = (
        "<html><body>"
        r'<p><math display="block">Z_{1} = \frac{V_1}{I_1}</math></p>'
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert r"\[Z_{1} = \frac{V_1}{I_1}\]" in polished
    assert "<math" not in polished


def test_polish_html_document_converts_inline_math_to_tex_delimiters() -> None:
    r"""<math display="inline"> with LaTeX content must become \(...\)."""
    html = (
        "<html><body>"
        r'<p>The value <math display="inline">x^2</math> is positive.</p>'
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert r"\(x^2\)" in polished
    assert "<math" not in polished


def test_polish_html_document_positions_equation_number_right() -> None:
    """Equation numbers like (1) must be extracted into a flex-row wrapper div."""
    html = (
        '<html><body>'
        '<p block-type="Equation">\\[Z_1 = j\\omega L_1\\]\n   (1)</p>'
        '</body></html>'
    )
    polished = polish_html_document(html)

    assert 'class="z2m-equation-row"' in polished
    assert '<span class="z2m-eq-num">(1)</span>' in polished
    assert '<span class="z2m-eq-lhs">' in polished
    assert '\\[Z_1 = j\\omega L_1\\]' in polished


def test_polish_html_document_splits_equation_number_from_following_prose() -> None:
    html = (
        '<html><body>'
        '<p block-type="Equation">\\[Z_1 = j\\omega L_1\\] (1) To make (1) more clear, we define x.</p>'
        '</body></html>'
    )
    polished = polish_html_document(html)

    assert 'class="z2m-equation-row"' in polished
    assert '<span class="z2m-eq-num">(1)</span>' in polished
    assert '<p block-type="Text">To make (1) more clear, we define x.</p>' in polished
    assert '\\(Z_1 = j\\omega L_1\\)' not in polished


def test_polish_html_document_splits_converted_math_tag_equation_from_prose() -> None:
    html = (
        '<html><body>'
        '<p block-type="Equation"><math display="block">Z_1 = j\\omega L_1</math> (1) To make (1) more clear.</p>'
        '</body></html>'
    )
    polished = polish_html_document(html)

    assert 'class="z2m-equation-row"' in polished
    assert '<span class="z2m-eq-num">(1)</span>' in polished
    assert '<p block-type="Text">To make (1) more clear.</p>' in polished


def test_polish_html_document_repairs_common_omega_zero_ratio_ocr() -> None:
    html = (
        '<html><body>'
        '<p block-type="Equation"><math display="block">Z_1|_{\\frac{\\omega}{2m}=1}=j\\omega_0L_1</math> (3)</p>'
        '</body></html>'
    )
    polished = polish_html_document(html)

    assert r"\frac{\omega}{\omega_0}=1" in polished
    assert r"\frac{\omega}{2m}=1" not in polished


def test_polish_html_document_demotes_block_math_in_text_paragraph() -> None:
    """\\[...\\] inside a Marker Equation paragraph that has surrounding prose text
    must be converted to inline \\(...\\) so it does not force a line break."""
    html = (
        '<html><body>'
        '<p block-type="Equation">Fig. 4 shows \\[Z_1\\] is a function of x.</p>'
        '</body></html>'
    )
    polished = polish_html_document(html)

    assert '\\(Z_1\\)' in polished
    assert '\\[Z_1\\]' not in polished
    assert '<p block-type="Text">' in polished


def test_polish_html_document_wraps_existing_ref_number_in_span() -> None:
    """References already numbered 'N. Author' by Marker must get z2m-ref-num span."""
    html = (
        "<html><body>"
        "<p>See [1] for details.</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>1. Smith et al., Nature 2020.</li>"
        "<li>2. Jones et al., Science 2021.</li>"
        "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    ref_section = polished[polished.index("References"):]
    assert '<span class="z2m-ref-num">1.</span>' in ref_section
    assert '<span class="z2m-ref-num">2.</span>' in ref_section


def test_polish_html_document_strips_bracket_ref_prefix_from_references() -> None:
    """References that start with [N] must not produce '1. [1] Author' double-numbering."""
    html = (
        "<html><body>"
        "<p>See [1] for more.</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>[1] Smith et al., Nature 2020.</li>"
        "<li>[2] Jones et al., Science 2021.</li>"
        "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    # z2m-ref-num span must be present
    assert 'class="z2m-ref-num"' in polished
    # The literal "[1]" must NOT appear inside a list item after the heading
    # (it was stripped and replaced by the z2m-ref-num span).
    ref_section = polished[polished.index("References"):]
    # Check no "1. [1]" double numbering
    assert "1.</span> [1]" not in ref_section
    assert "1.</span> [2]" not in ref_section


def test_polish_html_document_strips_duplicate_dotted_bracket_ref_prefix() -> None:
    html = (
        "<html><body>"
        "<p>See [1] for more.</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>1. [1] Hubel D and Wiesel T 1.</li>"
        "<li>2. [2] Jones et al., Science 2021.</li>"
        "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    ref_section = polished[polished.index("References"):]

    assert '<span class="z2m-ref-num">1.</span> Hubel' in ref_section
    assert "1.</span> [1]" not in ref_section
    assert "2.</span> [2]" not in ref_section


def test_polish_html_document_strips_bare_duplicate_ref_prefix() -> None:
    html = (
        "<html><body>"
        "<p>See [1] for more.</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>1 Gravas S, Descazeaud A, Drake M et al.</li>"
        "<li>2 Kranse R, van Mastrigt R.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References"):]

    assert '<span class="z2m-ref-num">1.</span> Gravas' in ref_section
    assert '<span class="z2m-ref-num">2.</span> Kranse' in ref_section
    assert "1.</span> 1 Gravas" not in ref_section
    assert "2.</span> 2 Kranse" not in ref_section


def test_polish_html_document_handles_reference_number_glued_to_author_initial() -> None:
    html = (
        "<html><body>"
        '<p>NIRF imaging detects lymph nodes <a href="#page-10-1">1,</a> '
        '<a href="#page-10-2">2</a> and nonspecifi <a href="#page-10-3">c3</a>.</p>'
        "<h4>References</h4>"
        "<ul>"
        '<li><span id="page-10-1"></span>1E. M. Sevick-Muraca, Translation of imaging.</li>'
        '<li><span id="page-10-2"></span>2B. E. Schaafsma, Clinical use.</li>'
        '<li><span id="page-10-3"></span>3B. Madajewski, Surgical wounds.</li>'
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References"):]

    assert '<li id="ref-1"><span class="z2m-ref-num">1.</span> <span id="page-10-1"></span>E. M.' in ref_section
    assert '<li id="ref-2"><span class="z2m-ref-num">2.</span> <span id="page-10-2"></span>B. E.' in ref_section
    assert '<li id="ref-3"><span class="z2m-ref-num">3.</span> <span id="page-10-3"></span>B.' in ref_section
    assert 'href="#ref-1"' in polished
    assert 'href="#ref-2"' in polished
    assert 'href="#ref-3"' in polished
    assert 'href="#page-10-1"' not in polished[: polished.index("References")]
    assert 'href="#page-10-2"' not in polished[: polished.index("References")]
    assert 'href="#page-10-3"' not in polished[: polished.index("References")]


def test_polish_html_document_detects_unheaded_reference_list_after_acknowledgments() -> None:
    html = (
        "<html><body>"
        '<p>NIRF imaging detects lymph nodes <a href="#page-10-1">1,</a> '
        '<a href="#page-10-2">2</a> and nonspecifi <a href="#page-10-3">c3</a>.</p>'
        "<h2>ACKNOWLEDGMENTS</h2>"
        "<p>This work was supported by a grant.</p>"
        '<p block-type="ListGroup"><ul>'
        '<li block-type="ListItem"><span id="page-10-1"></span>1E. M. Sevick-Muraca, Translation of imaging.</li>'
        '<li block-type="ListItem"><span id="page-10-2"></span>2B. E. Schaafsma, Clinical use.</li>'
        '<li block-type="ListItem"><span id="page-10-3"></span>3B. Madajewski, Surgical wounds.</li>'
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="ref-1"' in polished
    assert 'id="ref-2"' in polished
    assert 'id="ref-3"' in polished
    assert 'href="#ref-1"' in polished
    assert 'href="#ref-2"' in polished
    assert 'href="#ref-3"' in polished
    body = polished[: polished.index("ACKNOWLEDGMENTS")]
    assert 'href="#page-10-1"' not in body
    assert 'href="#page-10-2"' not in body
    assert 'href="#page-10-3"' not in body


def test_polish_html_document_keeps_unnumbered_reference_entry_from_previous_ref() -> None:
    html = (
        "<html><body>"
        "<p>Surface processing is described in [58].</p>"
        "<h4>References</h4>"
        "<ul>"
        + "".join(f"<li>{i}. Reference {i}.</li>" for i in range(1, 58))
        + "<li>Best Stainless Steel Wafer Polishing Services. http://example.test.</li>"
        + "<li>59. Ong, X. C. Processing of platinum electrodes.</li>"
        + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References"):]

    assert '<li id="ref-58"><span class="z2m-ref-num">58.</span> Best Stainless' in ref_section
    assert '<li id="ref-59"><span class="z2m-ref-num">59.</span> Ong' in ref_section
    assert 'href="#ref-58"' in polished[: polished.index("References")]


def test_polish_html_document_merges_numbered_reference_continuation_before_ids() -> None:
    html = (
        "<html><body>"
        "<p>Biomedical stainless steel is discussed in [26].</p>"
        "<h4>References</h4>"
        "<ul>"
        + "".join(f"<li>{i}. Reference {i}.</li>" for i in range(1, 25))
        + "<li>25. Niinomi, M. Recent metallic materials for biomedical applications. Metall. Mater. Trans. A</li>"
        + "<li>26. (2007) doi:10.1007/s11661-002-0109-2.</li>"
        + "<li>26. Li, M. et al. Study of biocompatibility of stainless steel. Mater. Sci. Eng. C.</li>"
        + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References"):]

    assert 'href="#ref-26"' in polished[: polished.index("References")]
    assert ref_section.count('id="ref-26"') == 1
    assert 'id="ref-27"' not in ref_section
    assert "Niinomi" in ref_section
    assert 'href="https://doi.org/10.1007/s11661-002-0109-2"' in ref_section
    assert '<li id="ref-26"><span class="z2m-ref-num">26.</span> Li, M. et al.' in ref_section


def test_polish_html_document_merges_uppercase_reference_continuation_before_ids() -> None:
    html = (
        "<html><body>"
        "<p>Earlier clinical utility work is discussed (27).</p>"
        "<h4>References</h4>"
        '<p block-type="ListGroup"><ul>'
        + "".join(f"<li>{i}. Reference {i}.</li>" for i in range(1, 26))
        + (
            "<li>26. Sugie T, Kinoshita T, Masuda N, Sawada T, Yamauchi A, "
            "Kuroi K, et al. Evaluation of the Clinical Utility of the ICG "
            "Fluorescence Method Compared</li>"
        )
        + "</ul></p>"
        '<p block-type="Text"><span id="page-7-0"></span> Jin et al. Combined Imaging in Breast Cancer</p>'
        '<p block-type="ListGroup"><ul>'
        + (
            "<li>With the Radioisotope Method for Sentinel Lymph Node Biopsy in "
            "Breast Cancer. Ann Surg Oncol (2016) 1:44-50. doi: "
            '<a href="https://doi.org/10.1245/s10434-015-4809-4">'
            "10.1245/s10434-015-4809-4</a></li>"
        )
        + (
            "<li>27. He K, Chi C, Kou D, Huang W, Wu J, Wang Y, et al. "
            "Comparison Between the Indocyanine Green Fluorescence and Blue Dye "
            "Methods for Sentinel Lymph Node Biopsy.</li>"
        )
        + "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "paren_numeric", "confidence": "high"},
    )
    ref_section = polished[polished.index("References"):]

    assert 'href="#ref-27"' in polished[: polished.index("References")]
    assert 'id="ref-28"' not in ref_section
    assert ref_section.count('id="ref-26"') == 1
    assert ref_section.count('id="ref-27"') == 1
    assert (
        '<li id="ref-26"><span class="z2m-ref-num">26.</span> '
        "Sugie T, Kinoshita T, Masuda N"
    ) in ref_section
    assert "Compared With the Radioisotope Method" in ref_section
    assert '<li id="ref-27"><span class="z2m-ref-num">27.</span> He K, Chi C' in ref_section


def test_polish_html_document_recovers_rsc_line_numbered_reference_ids() -> None:
    html = (
        "<html><body>"
        "<p>Probe performance was compared<sup>21,27</sup>.</p>"
        "<h4>References</h4>"
        '<p block-type="ListGroup" class="has-continuation"><ul>'
        "<li>H. S. Choi, Nat Biotech, 2013, 31, 148.</li>"
        "<li>S. H. Kim, Sci. Rep., 2013, 3, 1198.</li>"
        "<li>3 M.-Y. Wu, Chem. Commun., 2014, 50, 183.</li>"
        "<li>4 G. S. Filonov, Nat Biotech, 2011, 29, 757.</li>"
        "<li>5 H. Hyun, Nat. Med., 2015, 21, 192.</li>"
        "<li>6 C. Zhao, Chem. Asian J., 2014, 9, 1777.</li>"
        "<li><sup>50</sup> 7 P. Greenspan and S. D. Fowler, J. Lipid Res., 1985, 26, 781.</li>"
        "<li>H. S. Muddana, Nano Lett., 2009, 9, 1559.</li>"
        "<li>9 R. D. Moriarty, A. Martin, K. Adamson, E. O'Reilly, P. Mollard, R. J.</li>"
        "</ul></p>"
        '<p block-type="ListGroup"><ul>'
        "<li>Forster and T. E. Keyes, J Microsc, 2014, 253, 204.</li>"
        "<li>55 10 X. He, X. Wu, K. Wang, B. Shi and L. Hai, Biomaterials, 2009, 30, 5601.</li>"
        "<li>11 X. Peng, J. Am. Chem. Soc., 2005, 127, 4170.</li>"
        "<li>J. Massin, W. Dayoub, C. Andraud, Chem. Mater., 2011, 23, 862.</li>"
        "<li>13 X. He, Wires. Nanomed. Nanobi., 2010, 2, 349.</li>"
        "<li>14 X. Du and Z. Y. Wang, Chem. Commun., 2011, 47, 4276.</li>"
        "<li>15 X. Zhang, J. Yu, Y. Rong, Chem. Sci., 2013, 4, 2143.</li>"
        "<li>16 X. He, Anal. Chem., 2012, 84, 9056.</li>"
        "<li>17 J. Geng, Nanoscale, 2014, 6, 939.</li>"
        "<li>70 18 J. Gravier, Mol Pharm, 2014, 11, 3133.</li>"
        "<li>19 Y. Jin, ACS Nano, 2011, <b>5</b>,</li>"
        "<li>1468.</li>"
        "<li>20 L. Wang and W. Tan, Nano Lett., 2006, 6, 84.</li>"
        "<li>75 21 X. Chen, Anal. Chem., 2009, <b>81</b>, 7009.</li>"
        "<li>22 A. Wagh, Bioconjugate Chem, 2012, 23, 981.</li>"
        "<li>23 H. Zhang and D. Zhou, Chem. Commun., 2012, 48, 5097.</li>"
        "<li>24 M. Hasegawa, Chem. Commun., 2013, 49, 228.</li>"
        "<li>25 Y. Wang, Chem. Commun., 2014, 50, 811.</li>"
        "<li>26 Q. Ma and X. Su. Analyst, 2010, 135, 1867.</li>"
        "<li>We. Liu, H. Choi, J. P. Zimmer and M. Bawendi. J. Am. Chem. Soc., 2007, 129, 14530.</li>"
        '<li class="list-indent-1">28 S. Mishra, P. Kumar. J. Adv. Eng. Res. 2014, 1, 36</li>'
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References"):]

    assert 'href="#ref-21"' in polished[: polished.index("References")]
    assert 'href="#ref-27"' in polished[: polished.index("References")]
    assert 'id="ref-29"' not in ref_section
    assert 'id="ref-1468"' not in ref_section
    assert '<li id="ref-9"><span class="z2m-ref-num">9.</span> R. D. Moriarty' in ref_section
    assert "R. J. Forster and T. E. Keyes" in ref_section
    assert '<li id="ref-10"><span class="z2m-ref-num">10.</span> X. He' in ref_section
    assert '<li id="ref-19"><span class="z2m-ref-num">19.</span> Y. Jin' in ref_section
    assert "ACS Nano, 2011, <b>5</b>, 1468." in ref_section
    assert '<li id="ref-21"><span class="z2m-ref-num">21.</span> X. Chen' in ref_section
    assert '<li id="ref-27"><span class="z2m-ref-num">27.</span> We. Liu' in ref_section
    assert '<li id="ref-28"><span class="z2m-ref-num">28.</span> S. Mishra' in ref_section
    assert "55 10 X. He" not in ref_section
    assert "75 21 X. Chen" not in ref_section


def test_polish_html_document_retargets_author_year_page_links_to_reference_ids() -> None:
    html = (
        "<html><body>"
        '<p>The material is difficult to scale (Lienemann et al. <a href="#page-29-11">2023</a>; '
        'Paggi et al. <a href="#page-30-1">2024</a>).</p>'
        "<h4>References</h4>"
        "<ul>"
        '<li><span id="page-29-11"></span>Lienemann et al. Soft materials for nerve interfaces. 2023.</li>'
        '<li><span id="page-30-1"></span>Paggi et al. Smaller nerve interfaces. 2024.</li>'
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#page-29-11"' not in body
    assert 'href="#page-30-1"' not in body
    assert '<a href="#ref-1" class="z2m-ref-link">2023</a>' in body
    assert '<a href="#ref-2" class="z2m-ref-link">2024</a>' in body


def test_polish_html_document_repairs_decimal_digit_absorbed_into_ref_link() -> None:
    html = (
        "<html><body>"
        '<p>Values were r=0.2 <a href="#ref-56" class="z2m-ref-link">255</a> '
        'and r=0.0 <a href="#ref-56" class="z2m-ref-link">555</a> '
        'or r=0.2 <a href="#ref-40" class="z2m-ref-link">139</a>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 60)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'r=0.2 <a href="#ref-56"' not in body
    assert 'r=0.22<a href="#ref-55" class="z2m-ref-link">55</a>' in body
    assert 'r=0.05<a href="#ref-55" class="z2m-ref-link">55</a>' in body
    assert 'r=0.21<a href="#ref-39" class="z2m-ref-link">39</a>' in body


def test_polish_html_document_repairs_sup_wrapped_decimal_absorbed_ref_links() -> None:
    html = (
        "<html><body>"
        '<p>Correlations were r=0.2 <sup><a href="#ref-56" class="z2m-ref-link">255</a></sup> '
        'and r=0.2 <sup><a href="#ref-32" class="z2m-ref-link">139</a></sup>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 60)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )
    body = polished[: polished.index("References")]

    assert 'r=0.22<sup><a href="#ref-55" class="z2m-ref-link">55</a></sup>' in body
    assert 'r=0.21<sup><a href="#ref-39" class="z2m-ref-link">39</a></sup>' in body
    assert 'href="#ref-56" class="z2m-ref-link">255</a>' not in body
    assert 'href="#ref-32" class="z2m-ref-link">139</a>' not in body


def test_polish_html_document_repairs_unit_letter_absorbed_into_ref_link() -> None:
    html = (
        "<html><body>"
        '<p>Sensitivity was 68%–90 <a href="#ref-28" class="z2m-ref-link">%28</a>) '
        'with rates &lt;19 mL/ <a href="#ref-28" class="z2m-ref-link">s28)</a>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 30)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '68%–90%<a href="#ref-28" class="z2m-ref-link">28</a>)' in body
    assert 'mL/s<a href="#ref-28" class="z2m-ref-link">28</a>)' in body
    assert "%28" not in body
    assert "s28" not in body


def test_polish_html_document_does_not_treat_datasheet_feature_lists_as_references() -> None:
    html = (
        "<html><body>"
        "<p><b>Tables 2,1:</b> Uroflow specific quantitative parameters of the curve.</p>"
        "<h2>REFERENCES</h2>"
        "<p>Abdelmagid, M. E. and Gajewski, J. B. 1998. Critical Review of the Uroflowmetry.</p>"
        "<p>Abrams, P. (2003). Urodynamics Second Edition. Springer Publishing.</p>"
        "<h4>TS912N Data Sheet</h4>"
        "<h4>Features</h4>"
        "<ul><li>Rail-to-rail input and output voltage ranges</li>"
        "<li>Single supply operation from 2.7 to 16 V</li></ul>"
        "<h4>PIC16F887 Data Sheet</h4>"
        "<h4>High-Performance RISC CPU:</h4>"
        "<ul><li>Only 35 instructions to learn:</li>"
        "<li>All single-cycle instructions except branches</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="ref-1"' not in polished
    assert 'id="ref-2"' not in polished
    assert 'href="#ref-' not in polished
    assert "<b>Tables 2,1:</b>" in polished


def test_polish_html_document_keeps_references_after_earlier_appendix_heading() -> None:
    html = (
        "<html><body>"
        "<h2>Appendix A</h2>"
        "<p>Supplementary setup details.</p>"
        "<p>The method was validated [1].</p>"
        "<h2>References</h2>"
        "<ul><li>Smith J. A useful validation study. Journal. 2020.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )

    assert 'id="ref-1"' in polished
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in polished


def test_polish_html_document_recovers_bare_citations_as_sup() -> None:
    """Marker sometimes drops <sup> and glues citation numbers to text."""
    html = (
        "<html><body>"
        "<p>can mitigate these issues17,68 and potential69,70.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 71)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert '<sup>' in polished
    assert 'href="#ref-17"' in polished
    assert 'href="#ref-68"' in polished
    assert 'href="#ref-69"' in polished
    assert 'href="#ref-70"' in polished


def test_polish_html_document_recovers_spaced_bare_citations() -> None:
    """Space-separated bare citations before punctuation must also become <sup>."""
    html = (
        "<html><body>"
        "<p>relatively understudied 80,152,166. Robust methods will be essential 81.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 171)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert 'href="#ref-80"' in polished
    assert 'href="#ref-152"' in polished
    assert 'href="#ref-166"' in polished


def test_polish_html_document_recovers_trailing_single_bare_citation() -> None:
    html = (
        "<html><body>"
        "<p>ongoing efforts aim to broaden access to large, multimodal clinical datasets 62.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 80)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert 'href="#ref-62"' in polished


def test_polish_html_document_recovers_known_ocr_citation_artifacts() -> None:
    html = (
        "<html><body>"
        "<p>Models are developed specifically to optimize performance in a highly specific medical task. Sec.</p>"
        "<p>A small model is fine-tuned on outputs generated by flagship models 6,000.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 70)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert "task. Sec." not in polished
    assert "flagship models 6,000" not in polished
    assert 'href="#ref-58"' in polished
    assert 'href="#ref-59"' in polished
    assert 'href="#ref-60"' in polished


def test_polish_html_document_converts_latex_sup_citations_after_math_conversion() -> None:
    html = (
        "<html><body>"
        "<p>Clinical use remains limited <math>^{71-73}</math> in practice.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 80)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert r"\(^{71-73}\)" not in polished
    assert 'href="#ref-71"' in polished
    assert 'href="#ref-73"' in polished


def test_polish_html_document_does_not_treat_decimal_number_as_citation() -> None:
    html = (
        "<html><body>"
        "<p>The spacing ranged from 1.5 – 2.5 mm across designs.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 90)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert "1.5 – 2.5 mm" in polished
    assert '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>.5' not in polished
    assert '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>.5' not in polished


def test_polish_html_document_does_not_link_unit_number_as_citation() -> None:
    html = (
        "<html><body>"
        "<p>The scanner was calibrated in (Unit 1) before the trial.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 50)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert "(Unit 1)" in polished
    assert 'href="#ref-1"' not in polished


def test_polish_html_document_normalizes_scientific_units_and_degree_symbol() -> None:
    html = (
        "<html><body>"
        "<p>Recording site area was 350 µm 2 and openings were 47.5 by 67.5 μm2were made.</p>"
        "<p>The dose was 10 mg kg h − 1 IV and capacitance was 750 μCcm−2.</p>"
        "<p>The voltage was 0.7Vand 1.0Vfor 30 μAand 250 μA, respectively.</p>"
        "<p>The coating was at least 130 <i>µ</i> m thick.</p>"
        "<p>The grating covered 1.5 ◦ × 1.5 ◦ and was baked at 200 ◦ C.</p>"
        "<p>The window covered 1.5 <i>◦ ×</i> 1.5 <i>◦</i> and was baked at 350 <i>◦</i> C.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert '350 µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert '67.5 µm<sup class="z2m-unit-exp">2</sup> were made' in polished
    assert 'mg kg<sup class="z2m-unit-exp">-1</sup> h<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'μC cm<sup class="z2m-unit-exp">-2</sup>' in polished
    assert "0.7 V and 1.0 V for 30 μA and 250 μA" in polished
    assert "130 µm thick" in polished
    assert "<i>µ</i> m" not in polished
    assert "1.5° × 1.5°" in polished
    assert "200°C" in polished
    assert "350°C" in polished
    assert "<i>◦" not in polished


def test_polish_html_document_keeps_prose_outside_inline_unit_formula_tail() -> None:
    html = (
        "<html><body>"
        r"<p>The approximate dosage of each drug was 4.25–8.5 "
        r"\(mg\cdot kg^{-1}\cdot h^{-1},\ 10.6\ \mu g\cdot kg^{-1}\cdot h^{-1},\ "
        r"and\ 0–2\%,\ respectively.\) Spontaneous breathing was maintained.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    # The swallowed prose tail must be split back OUT of the inline math: each
    # unit becomes its own rendered formula (TeX recoverable via data-z2m-tex)
    # and the trailing prose stays as plain text, not trapped in the formula.
    assert r'data-z2m-tex="\(mg\cdot kg^{-1}\cdot h^{-1}\)"' in polished
    assert r'data-z2m-tex="\(\mu g\cdot kg^{-1}\cdot h^{-1}\)"' in polished
    assert "and 0–2%, respectively." in polished
    assert r"and\ 0–2\%,\ respectively.\)" not in polished


def test_polish_html_document_renders_static_katex_without_mathjax() -> None:
    html = (
        "<html><head>"
        "<script>MathJax={tex:{}}</script>"
        '<script id="MathJax-script" '
        'src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>'
        "</head><body>"
        r"<p>Energy \(E=mc^2\) released.</p>"
        r"<p>\[\chi^2 = \sum_{i=1}^{n} \frac{(O_i-E_i)^2}{E_i}\]</p>"
        r"<p>System: \[\begin{aligned} a &= b+c \\ &= d \end{aligned}\]</p>"
        r"<pre>literal \(x^2\) must survive verbatim</pre>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    # MathJax is fully removed; no JS dependency remains.
    assert "MathJax-script" not in polished
    assert "cdn.jsdelivr.net/npm/mathjax" not in polished
    # KaTeX rendered the formulas statically (HTML+CSS, not an image).
    assert 'data-z2m-style="katex"' in polished
    assert polished.count('class="katex') >= 3
    assert "<img" not in polished
    # Original LaTeX is recoverable for the later HTML→Markdown / LLM step.
    assert r'data-z2m-tex="\(E=mc^2\)"' in polished
    assert r'class="z2m-math z2m-math-inline"' in polished
    assert r'class="z2m-math z2m-math-display"' in polished
    # aligned environment rendered (KaTeX, unlike the rejected hand-rolled path).
    assert "z2m-math-error" not in polished
    # Skip regions are left untouched.
    assert r"literal \(x^2\) must survive verbatim" in polished
    # Idempotent: re-polishing already-rendered output is a no-op for math.
    repolished = polish_html_document(polished, table_caption_language="en")
    assert repolished.count('data-z2m-style="katex"') == 1
    assert repolished.count('data-z2m-tex="\\(E=mc^2\\)"') == 1
    assert repolished.count('class="katex') == polished.count('class="katex')


def test_close_katex_v8_context_allows_recreate_after_static_render() -> None:
    html = "<html><body>" r"<p>Energy \(E=mc^2\).</p>" "</body></html>"

    try:
        first = polish_html_document(html, table_caption_language="en")
        assert 'data-z2m-style="katex"' in first

        close_katex_v8_context()

        second = polish_html_document(html, table_caption_language="en")
        assert 'data-z2m-style="katex"' in second
        assert r'data-z2m-tex="\(E=mc^2\)"' in second
    finally:
        close_katex_v8_context()


def test_polish_html_document_repairs_snr_sqrt_subscript_brace_spill_for_katex() -> None:
    html = (
        "<html><body>"
        '<p block-type="Equation"><math display="block">'
        r"SNR = \frac{\bar{S}^{t}(C) - \bar{S}^{b}(0)}"
        r"{\sqrt{\sum_{i=1}^{m} \sum_{j=1}^{n} "
        r"\left[S^{b}_{(i,j)}(0) - \bar{S}^{b}(0)\right]^{2}}}_{mn}},"
        "</math> (2)</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "katex-error" not in polished
    assert "z2m-math-error" not in polished
    assert r"}^{2}}}_{mn}}" not in polished
    assert r"\sqrt{\frac{\sum_{i=1}^{m}" in polished
    assert r"\right]^{2}}{mn}}" in polished
    assert '<span class="z2m-eq-num">(2)</span>' in polished


def test_polish_html_document_repairs_common_scientific_word_glue() -> None:
    html = (
        "<html><body>"
        "<p>The current was 20nCfor a pulse width and p = 0.04for the comparison.</p>"
        "<p>The level reached the -0.6 Vwater window limit and was safe forintracorticalstimulation.</p>"
        "<p>The most telling reminder in the resuscitation situation is that of a 6-</p>"
        "<p>year-old boy in a scanner room.</p>"
        "<p>The backup coil is optimised for a 7 year-old child.</p>"
        "<p>WVTR = D eff (C1 - C2) / l, where D eff is effective.</p>"
        "<p>The coefficient <i> D </i> eff stays compact.</p>"
        "<p>A specifc and identifed singleneuron model used artifcial clocks to refect fow in fxed space.</p>"
        "<p>The efects afected specifcity and coeficient diferences in eficient diferent trials diferentially.</p>"
        "<p>The work was timeconsuming and contentaware; an ofline metaanalysis reported sensorimotor defcits.</p>"
        "<p>Diferential and diferent vagal aferents used inhibitionbased phaselocked crossfrequency mechanisms.</p>"
        "<p>Online supple mental table 1 and Biobeha v. Rev. entries should be normalized.</p>"
        "<p>Refrence values were approximatley stable, not suiprising after comparision.</p>"
        "<p>The attaclied block mentioned an urtheral clincal issue beacause threfore remained.</p>"
        "<p>Uroflowrnetry, Uroflowmetery, urofowmetry, urflowmetry, and flowmetery were normalized.</p>"
        "<p>FERENCE VALUES reported intraand inter-subject variability.</p>"
        "<p>The non-invasivly aformentioned standarization subcomitee note stayed readable.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert "20 nC for" in polished
    assert "p = 0.04 for" in polished
    assert "V water window" in polished
    assert "for intracortical stimulation" in polished
    assert "6-year-old boy" in polished
    assert "7-year-old child" in polished
    assert "D<sub>eff</sub>" in polished
    assert "<i>D</i><sub>eff</sub>" in polished
    assert "specific and identified single-neuron model" in polished
    assert "artificial clocks to reflect flow in fixed space" in polished
    assert "effects affected specificity and coefficient differences in efficient different trials differentially" in polished
    assert "time-consuming and content-aware" in polished
    assert "offline meta-analysis reported sensorimotor deficits" in polished
    assert "differential and different vagal afferents" in polished
    assert "inhibition-based phase-locked cross-frequency mechanisms" in polished
    assert "Online supplemental table 1 and Biobehav. Rev. entries" in polished
    assert "Reference values were approximately stable, not surprising after comparison" in polished
    assert "attached block mentioned an urethral clinical issue because therefore remained" in polished
    assert "Uroflowmetry, Uroflowmetry, uroflowmetry, uroflowmetry, and flowmetry were normalized" in polished
    assert "REFERENCE VALUES reported intra- and inter-subject variability" in polished
    assert "non-invasively aforementioned standardization subcommittee note" in polished


def test_polish_html_document_normalizes_latex_micro_units_and_glued_charge_density() -> None:
    html = (
        "<html><body>"
        r"<p>The table reports 70\mum x 20 \mum (1 shaft) and an area of 4000\mum^2.</p>"
        r"<p>The charge injection capacity (CIC)of2.3mCm^-2 was measured.</p>"
        r"<p>This occurred at a current of 350 µA, corresponding to a charge injection capacity "
        r"\((CIC) of 2.3 mC cm^{-2}\)</p><p block-type='Text'>Additionally, CV was measured.</p>"
        r"<p>Two electrodes were stimulated with 300 \(\mu A\) \((CIC = 1.9  mC cm^{-2})\) "
        r"and 130 µA \((CIC = 0.7 \,mC cm^{-2})\) , respectively.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert r"\mum" not in polished
    assert "70 µm × 20 µm" in polished
    assert '4000 µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert '(CIC) of 2.3 mC cm<sup class="z2m-unit-exp">-2</sup>' in polished
    assert r"\((CIC)" not in polished
    assert "mC cm<sup class=\"z2m-unit-exp\">-2</sup>.</p><p block-type='Text'>Additionally" in polished
    assert "300 μA" in polished
    assert '(CIC = 1.9 mC cm<sup class="z2m-unit-exp">-2</sup>)' in polished
    assert '(CIC = 0.7 mC cm<sup class="z2m-unit-exp">-2</sup>),' in polished


def test_polish_html_document_normalizes_ohm_prefix_spacing_and_unit_punctuation() -> None:
    html = (
        "<html><body>"
        r"<p>The impedance was 4.8 k \(\Omega\) and 100.3 k Ω , while R was 1 M Ω .</p>"
        r"<p>The CIC was 2.3 mC cm <sup class='z2m-unit-exp'>-2</sup> , "
        r"and the area was 3200 µm <sup class='z2m-unit-exp'>2</sup> .</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "4.8 kΩ" in polished
    assert "100.3 kΩ," in polished
    assert "1 MΩ." in polished
    assert "mC cm<sup class='z2m-unit-exp'>-2</sup>," in polished
    assert "µm<sup class='z2m-unit-exp'>2</sup>." in polished
    assert "k Ω" not in polished
    assert "Ω ," not in polished
    assert "Ω ." not in polished


def test_polish_html_document_normalizes_latex_dimension_times_and_oxide_subscripts() -> None:
    html = (
        "<html><body>"
        r"<p>The array used 70 \mu\text{m} x 20 \mu\text{m} contacts and "
        r"67.5 \times 47.5\,\mum^2 windows.</p>"
        "<p>The material stack was AlOx 20 nm with HfOx and IrOx control layers.</p>"
        "<p>The isolation layer contained HfO <i>x</i>, AlO <i>x</i>, and IrO <i><sup>x</sup></i>.</p>"
        "<p>A stable phase of ZrAl <i> x </i> O <i> y </i> forms at the interface.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert r"\mu" not in polished
    assert "70 µm × 20 µm" in polished
    assert '47.5 µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert "AlO<sub>x</sub> 20 nm" in polished
    assert "HfO<sub>x</sub>" in polished
    assert "IrO<sub>x</sub>" in polished
    assert "ZrAl<sub>x</sub>O<sub>y</sub>" in polished
    assert "HfO <i> x </i>" not in polished


def test_polish_html_document_normalizes_plain_negative_unit_exponents() -> None:
    html = (
        "<html><body>"
        "<p>Values can be as low as ~10–13 cm–2 s -1 for ALD TiO2 and ~10−16 cm−2 s−1 for CVD SiO2.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '10<sup class="z2m-unit-exp">-13</sup> cm<sup class="z2m-unit-exp">-2</sup> s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert '10<sup class="z2m-unit-exp">-16</sup> cm<sup class="z2m-unit-exp">-2</sup> s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert "cm–2" not in polished
    assert "s -1" not in polished


def test_polish_html_document_normalizes_simple_latex_unit_only_fragments() -> None:
    html = (
        "<html><body>"
        r"<p>Corrosion appears at \(100 \,\muC \,cm^{-2}\), with thresholds from "
        r"\(190 \mu C cm^{-2}\) to 2.5 mC cm<sup>-2</sup>.</p>"
        r"<p>Electrode areas of \(3000 \mu m^2\), median thresholds of \(23 \mu A\), "
        r"and impedance of 4.8 k \(\Omega\) were reported.</p>"
        r"<p>Other electrodes used 3000 \(\mu m^2\) sites.</p>"
        r"<p>Four sizes were 30 μm \(\times\) 30 μm \((900 \ \mum^2; 58/92 \ ch), "
        r"50 \ \mum \times 40 \ \mum (2000 \ \mum^2;\) 12/92 ch), "
        r"and 100 \(\mu m\) shafts.</p>"
        r"<p>The text layer sometimes emits \(\mu\) C cm<sup>-2</sup> and "
        r"\(\mu\) m<sup>2</sup> fragments.</p>"
        r"<p><math>100 \,\mu\text{C} \,\text{cm}^{-2}</math></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert r"\muC" not in polished
    assert r"\(\mu\)" not in polished
    assert "<math" not in polished
    assert '100 μC cm<sup class="z2m-unit-exp">-2</sup>' in polished
    assert '190 μC cm<sup class="z2m-unit-exp">-2</sup>' in polished
    assert '3000 µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert r"3000 \(\mu m^2\)" not in polished
    assert r"\mum" not in polished
    assert r"\(\times\)" not in polished
    assert "30 μm × 30 μm" in polished
    assert '900 µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert "50 µm × 40 µm" in polished
    assert '2000 µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert "100 µm shafts" in polished
    assert "23 μA" in polished
    assert "4.8 kΩ" in polished
    assert 'μC cm<sup class="z2m-unit-exp">-2</sup>' in polished
    assert 'µm<sup class="z2m-unit-exp">2</sup>' in polished


def test_polish_html_document_unwraps_merken_dimension_prose_math() -> None:
    html = (
        "<html><body>"
        r"<p>Four different electrodes sizes were tested: 30 µm × 30 µm "
        r'\((900 µm<sup class="z2m-unit-exp">2</sup>; 58/92 \ ch), '
        r'50 µm × 40 µm (2000 µm<sup class="z2m-unit-exp">2</sup>;\) 12/92 ch), '
        r'\(100 µm × 40 µm\) (\(4000 µm<sup class="z2m-unit-exp">2</sup>\); '
        r'11/92 ch) and \(200 µm × 40 µm\) (8000 µm<sup class="z2m-unit-exp">2</sup>; '
        r"11/92 ch).</p>"
        r"<p>The range was \((30 × 30 µm  to  200 × 40 µm)\).</p>"
        r"<p>The model equation \(x_i = y_i + 1\) must stay math.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert r"\ ch" not in polished
    assert r";\)" not in polished
    assert r"\(100 µm" not in polished
    assert "( 4000" not in polished
    assert "</sup> ;" not in polished
    assert "58/92 ch" in polished
    assert "50 µm × 40 µm" in polished
    assert '4000 µm<sup class="z2m-unit-exp">2</sup>; 11/92 ch' in polished
    assert "(30 × 30 µm to 200 × 40 µm)" in polished
    assert r"\(x_i = y_i + 1\)" in polished


def test_polish_html_document_unwraps_dimension_tex_in_table_cells() -> None:
    html = (
        "<html><body>"
        "<table><tr>"
        r"<td>\(18.5  mm \times 23  mm\)</td>"
        r"<td>Up to \[18 \times 21 \text{ mm}\] (up to 256 shafts)</td>"
        r"<td>\((4 × 9  shafts)\)</td>"
        r"<td>\(\pm 1  mm \times 2  mm\)</td>"
        r"<td>\(\pm\) 5 × 5 mm</td>"
        r"<td>\(23 × 18.5 \mathrm{mm}\)</td>"
        "</tr></table>"
        r"<p>The model equation \(x_i = y_i + 1\) must stay math.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert r"\times" not in polished
    assert r"\text" not in polished
    assert r"\mathrm" not in polished
    assert r"Up to \[" not in polished
    assert r"\(\pm" not in polished
    assert "18.5 mm × 23 mm" in polished
    assert "Up to 18 × 21 mm (up to 256 shafts)" in polished
    assert "(4 × 9 shafts)" in polished
    assert "± 1 mm × 2 mm" in polished
    assert "± 5 × 5 mm" in polished
    assert "23 × 18.5 mm" in polished
    assert r"\(x_i = y_i + 1\)" in polished


def test_polish_html_document_unwraps_simple_statistical_inline_tex() -> None:
    html = (
        "<html><body>"
        r"<p>The values were \((4.37 \pm 2.47 vs. 5.22 \pm 2.38, p = 0.075;\) "
        r"\(0.23 \pm 0.57\) vs. \(0.47 \pm 1.10\) , p = 0.247) . However, values changed.</p>"
        r"<p>The median was (median \(0.51\pm0.09\) vs. \(0.53\pm0.09\) , respectively; P=0.58).</p>"
        r"<p>Near-infrared imaging provides \(\gamma\)-ray tissue penetration.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert (
        "(4.37 ± 2.47 vs. 5.22 ± 2.38, p = 0.075; "
        "0.23 ± 0.57 vs. 0.47 ± 1.10, p = 0.247). However"
    ) in polished
    assert "(median 0.51 ± 0.09 vs. 0.53 ± 0.09, respectively; P = 0.58)." in polished
    assert r"\pm" not in polished
    assert r"\(\gamma\)" in polished


def test_polish_html_document_restores_period_after_terminal_inline_formula() -> None:
    html = (
        "<html><body>"
        r"<p>This occurred at a current of 350 µA, corresponding to a charge injection capacity "
        r"\((CIC) of 2.3 mC cm^{-2}\)</p>"
        "<p>Additionally, cyclic voltammetry was measured.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert '(CIC) of 2.3 mC cm<sup class="z2m-unit-exp">-2</sup>.</p>' in polished
    assert r"\((CIC)" not in polished
    assert "<p>Additionally, cyclic voltammetry" in polished


def test_polish_html_document_repairs_equation_defined_index_prose() -> None:
    html = (
        "<html><body>"
        r"<p>\[\begin{split} COG(t)_x &= \frac{x_j iECoG(t)_j}{iECoG(t)_j}. \end{split}\] "
        "Here, an averaged ECoG voltage is shown as iECoG(t) j. "
        "A coordinate of position j is shown as (x j, yj).</p>"
        "<p>Here, an averaged ECoG voltage at position j is shown as iECoG(t) "
        "<sup> j </sup>. A coordinate of position j is shown as (x <sup> j </sup>, yj).</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert "iECoG(t)<sub>j</sub>" in polished
    assert "x<sub>j</sub>" in polished
    assert "y<sub>j</sub>" in polished
    assert "iECoG(t) <sup> j </sup>" not in polished
    assert "x <sup> j </sup>" not in polished


def test_polish_html_document_repairs_terminal_section_interleaving() -> None:
    html = (
        "<html><body>"
        "<h2>FUNDING</h2>"
        '<p block-type="Text">This work was partially supported by the Strategic Research Program for Brain Sciences by the Ministry of</p>'
        "<h1>REFERENCES</h1>"
        '<p block-type="ListGroup"><ul><li block-type="ListItem">1. Castagnola, E. Reference one.</li></ul></p>'
        '<p block-type="Text">Education, Culture, Sports, Science and Technology of Japan, JSPS KAKENHI Grant Number 15H03049 and National Institute of Dental and Craniofacial Research Grant.</p>'
        "<h1>SUPPLEMENTARY MATERIAL</h1>"
        '<p block-type="Text">The Supplementary Material for this article can be found online.</p>'
        '<p block-type="ListGroup"><ul><li block-type="ListItem">2. Chen, L. M. Reference two.</li></ul></p>'
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert polished.index("FUNDING") < polished.index("Education, Culture")
    assert polished.index("Education, Culture") < polished.index("SUPPLEMENTARY MATERIAL")
    assert polished.index("SUPPLEMENTARY MATERIAL") < polished.index("REFERENCES")
    assert polished.index("REFERENCES") < polished.index("Castagnola")
    assert polished.index("Castagnola") < polished.index("Chen")


def test_polish_html_document_marks_existing_unit_exponent_superscripts() -> None:
    html = (
        "<html><body>"
        "<p>Recording site area was 350 µm<sup>2</sup>.</p>"
        "<p>Dose was 10 mg kg h <i>−</i> <sup>1</sup> IV.</p>"
        "<p>Luminance was 74 cd m <i>−</i> <sup>2</sup>.</p>"
        "<p>Insertion velocity was 0.01 mm s <i>−</i> <sup>1</sup>.</p>"
        "<h4>References</h4><ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert 'mg kg<sup class="z2m-unit-exp">-1</sup> h<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'cd m<sup class="z2m-unit-exp">-2</sup>' in polished
    assert 'mm s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'href="#ref-1"' not in polished
    assert 'href="#ref-2"' not in polished


def test_polish_html_document_repairs_already_linked_unit_exponent() -> None:
    html = (
        "<html><body>"
        '<p>Insertion velocity was 0.01 mm s <i>−</i> '
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>Dissolution was ~20 nm d<sup>-<a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>Doping was 10<sup>20</sup> cm<sup>-<a href="#ref-3" class="z2m-ref-link">3</a></sup>.</p>'
        '<p>Bending stiffness was 3.3 × 10−12 N <a href="#ref-2" class="z2m-ref-link">m2</a>.</p>'
        '<p>Electrode sites had areas of 14 × 24 µm <a href="#ref-2" class="z2m-ref-link">2</a>.</p>'
        "<h4>References</h4><ul><li>Ref one.</li><li>Ref two.</li><li>Ref three.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'mm s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'nm d<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'cm<sup class="z2m-unit-exp">-3</sup>' in polished
    assert 'N m<sup class="z2m-unit-exp">2</sup>' in polished
    assert 'µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body


def test_polish_html_document_repairs_ml_per_second_ocr_unit_exponent() -> None:
    html = (
        "<html><body>"
        "<p>Flow rates of 5 to 50 mL:s{ <sup>1</sup> were tested.</p>"
        "<p>The flow rate increased to 20{25 mL:s{ <sup>1</sup>.</p>"
        '<p>Peak flow reached 20 mL:s{ <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>A more normal peak flow rate (w10mL:s{ <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>) was observed.</p>'
        "<p>The model was validated<sup>1</sup>.</p>"
        "<h4>References</h4><ul><li>Ref one.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert body.count('mL s<sup class="z2m-unit-exp">-1</sup>') == 4
    assert "mL:s{" not in body
    assert '20-25 mL s<sup class="z2m-unit-exp">-1</sup>' in body
    assert 'w10 mL s<sup class="z2m-unit-exp">-1</sup>' in body
    assert 'href="#ref-1"' not in body[: body.index("The model")]
    assert 'href="#ref-1"' in body[body.index("The model"):]


def test_polish_html_document_moves_trailing_bracket_citation_out_of_inline_tex() -> None:
    html = (
        "<html><body>"
        r"<p>The reaction is \(Ir(OH)_2 \leftrightarrow IrOH + H^+ + e^-[17]\).</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 18)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert r"e^+\e" not in polished
    assert r"e^-[17]\)" not in polished
    assert r"e^-\)" in polished
    assert 'href="#ref-17"' in polished


def test_polish_html_document_does_not_break_volume_issue_pair() -> None:
    html = (
        "<html><body>"
        "<p>Front. Neural Circuits 11:20. doi: 10.3389/fncir.2017.00020</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 40)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert "Neural Circuits 11:20." in polished
    assert "Neural Circuits :20." not in polished


def test_polish_html_document_repairs_existing_false_decimal_sup_citation() -> None:
    html = (
        "<html><body>"
        "<p>The spacing ranged from <sup><a href=\"#ref-1\" class=\"z2m-ref-link\">1</a></sup>.5 – 2.5 mm.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 10)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert "1.5 – 2.5 mm" in polished
    assert '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>.5' not in polished


def test_polish_html_document_recovers_citation_leaked_into_tex_unit_exponent() -> None:
    html = (
        "<html><body>"
        "<p>Stainless steel has fracture toughness of \\(112-278~\\mathrm{MPa}\\sqrt{\\mathrm{m}^{24}}\\).</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 30)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert r"\sqrt{\mathrm{m}^{24}}" not in polished
    assert r"\sqrt{\mathrm{m}}" in polished
    assert 'href="#ref-24"' in polished


def test_polish_html_document_normalizes_ocr_merged_citation_169_70_to_69_70() -> None:
    html = (
        "<html><body>"
        "<p>to help ensure that tools maximize their potential 169,70.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 180)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert 'href="#ref-69"' in polished
    assert 'href="#ref-70"' in polished
    assert 'href="#ref-169"' not in polished


def test_polish_html_document_normalizes_existing_sup_ocr_merged_citation_pair() -> None:
    html = (
        "<html><body>"
        "<p>to help ensure that tools maximize their potential <sup>169,70</sup>.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 180)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert 'href="#ref-69"' in polished
    assert 'href="#ref-70"' in polished
    assert 'href="#ref-169"' not in polished


def test_polish_html_document_normalizes_already_linked_ocr_merged_citation_pair() -> None:
    html = (
        "<html><body>"
        "<p>to help ensure that tools maximize their potential "
        '<sup><a href="#ref-169" class="z2m-ref-link">169</a>,'
        '<a href="#ref-70" class="z2m-ref-link">70</a></sup>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 180)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert 'href="#ref-69"' in polished
    assert 'href="#ref-70"' in polished
    assert 'href="#ref-169"' not in polished


def test_polish_html_document_recovers_dot_separated_citations() -> None:
    """Marker OCR artefact: dots instead of commas in citation lists."""
    html = (
        "<html><body>"
        "<p>mitigate these issues17.68. Specific education</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 71)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert 'href="#ref-17"' in polished
    assert 'href="#ref-68"' in polished


def test_polish_html_document_restores_sup_from_byte_tokens() -> None:
    """Gemma byte-token artifacts followed by citation numbers → <sup>."""
    html = (
        "<html><body>"
        "<p>кодирование<0xE2><0x82><0xA9>1,2 текст.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert "<0x" not in polished
    assert '<sup>' in polished
    assert 'href="#ref-1"' in polished
    assert 'href="#ref-2"' in polished


# ---------------------------------------------------------------------------
# Section anchors and links
# ---------------------------------------------------------------------------

def test_add_section_anchors_injects_id_into_roman_headings() -> None:
    html = (
        "<html><body>"
        "<h2>II. Method</h2>"
        "<h2>III. Results</h2>"
        "</body></html>"
    )
    result, found = _add_section_anchors(html)

    assert found == {"II", "III"}
    assert 'id="section-II"' in result
    assert 'id="section-III"' in result
    assert "<h2" in result


def test_add_section_anchors_skips_heading_with_existing_id() -> None:
    html = '<h3 id="my-id">IV. Discussion</h3>'
    result, found = _add_section_anchors(html)

    assert found == {"IV"}
    assert 'id="my-id"' in result
    # Must NOT add a second id
    assert result.count('id=') == 1


def test_link_section_refs_wraps_matching_roman_refs() -> None:
    html = "<p>See Section II for details and Section III for more.</p>"
    linked = _link_section_refs(html, {"II", "III"})

    assert 'href="#section-II"' in linked
    assert 'href="#section-III"' in linked
    assert "z2m-section-link" in linked


def test_link_section_refs_skips_unknown_sections() -> None:
    html = "<p>See Section V for details.</p>"
    linked = _link_section_refs(html, {"II"})

    assert 'href=' not in linked


def test_link_section_refs_skips_inside_existing_anchor() -> None:
    html = '<p>See <a href="#x">Section II info</a>.</p>'
    linked = _link_section_refs(html, {"II"})

    # Should not nest <a> inside <a>
    assert linked.count("<a") == 1


def test_polish_html_document_adds_section_anchor_links() -> None:
    html = (
        "<html><body>"
        "<h2>II. Method</h2>"
        "<p>As described in Section II above.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert 'id="section-II"' in polished
    assert 'href="#section-II"' in polished
    assert "z2m-section-link" in polished


# ---------------------------------------------------------------------------
# Figure anchors and links
# ---------------------------------------------------------------------------

def test_add_figure_anchors_injects_id_into_caption_paragraphs() -> None:
    html = (
        "<html><body>"
        "<p>Fig. 1. A diagram showing results.</p>"
        "<p>Fig. 2. Another illustration.</p>"
        "</body></html>"
    )
    result, found = _add_figure_anchors(html)

    assert found == {"1", "2"}
    assert 'id="fig-1"' in result
    assert 'id="fig-2"' in result


def test_add_figure_anchors_handles_russian_caption() -> None:
    html = "<p>Рис. 3. Схема устройства.</p>"
    result, found = _add_figure_anchors(html)

    assert "3" in found
    assert 'id="fig-3"' in result


def test_add_figure_anchors_handles_spaced_decimal_caption_number() -> None:
    html = "<p>Fig. 3 .9. Calibration curves of the flow rate measurement.</p>"
    result, found = _add_figure_anchors(html)

    assert "3-9" in found
    assert 'id="fig-3-9"' in result


def test_add_figure_anchors_keeps_caption_text_decimal_out_of_number() -> None:
    html = "<p>Fig. 17. 2.5D virtual model obtained by applying the proposed methodology.</p>"
    result, found = _add_figure_anchors(html)

    assert "17" in found
    assert "17-2-5" not in found
    assert 'id="fig-17"' in result
    assert 'id="fig-17-2-5"' not in result


def test_add_figure_anchors_skips_paragraph_with_existing_id() -> None:
    html = '<p id="already">Fig. 4. Caption text.</p>'
    result, found = _add_figure_anchors(html)

    assert "4" in found
    assert result.count('id=') == 1


def test_add_figure_anchors_handles_leading_inline_span_before_caption() -> None:
    html = '<p><span id="page-14-0"></span> Figure 1. Overview text.</p>'
    result, found = _add_figure_anchors(html)
    assert "1" in found
    assert 'id="fig-1"' in result


def test_add_figure_anchors_handles_wrapped_caption_label() -> None:
    html = '<p><b> Fig. 2 </b> A cross-sectional diagram.</p>'
    result, found = _add_figure_anchors(html)

    assert found == {"2"}
    assert 'id="fig-2"' in result


def test_add_figure_anchors_skips_subfigure_body_sentence() -> None:
    html = "<p>Figure 2(B) shows the full impedance plot for the electrodes.</p>"
    result, found = _add_figure_anchors(html)

    assert found == set()
    assert "id=" not in result


def test_add_figure_anchors_skips_legend_stub_and_body_auxiliary_sentence() -> None:
    html = (
        "<p>Fig. 9 (See legend on next page.)</p>"
        "<p>Fig. 14 was collected by varying the distance between sensor and antenna.</p>"
    )
    result, found = _add_figure_anchors(html)

    assert found == set()
    assert "id=" not in result


def test_link_figure_refs_wraps_matching_refs() -> None:
    html = "<p>As shown in Fig. 1 and Fig. 2 below.</p>"
    linked = _link_figure_refs(html, {"1", "2"})

    assert 'href="#fig-1"' in linked
    assert 'href="#fig-2"' in linked
    assert "z2m-fig-link" in linked


def test_link_figure_refs_wraps_figure_word_and_subfigure_suffixes() -> None:
    html = "<p>As shown in Figure 1c and 1d, the flexible cable reduces tethering.</p>"
    linked = _link_figure_refs(html, {"1"})
    assert 'href="#fig-1"' in linked
    assert "Figure\xa01c" in linked
    assert ">1d</a>" in linked


def test_link_figure_refs_wraps_decimal_and_chapter_style_numbers() -> None:
    html = "<p>See Figure 3.24 and Figure 57-5 for details.</p>"
    linked = _link_figure_refs(html, {"3-24", "57-5"})

    assert '<a href="#fig-3-24" class="z2m-fig-link">Figure\xa03.24</a>' in linked
    assert '<a href="#fig-57-5" class="z2m-fig-link">Figure\xa057-5</a>' in linked
    assert 'href="#fig-3"' not in linked
    assert 'href="#fig-57"' not in linked


def test_link_figure_refs_wraps_plural_multipanel_refs() -> None:
    html = "<p>The lack of distortion (figures 4(A), (B)) suggests stable shape.</p>"
    linked = _link_figure_refs(html, {"4"})
    assert 'href="#fig-4"' in linked
    assert "figures\xa04" in linked


def test_link_figure_refs_does_not_create_nested_fig_links() -> None:
    html = "<p>As shown in Figure 1a, the design remains stable.</p>"
    linked = _link_figure_refs(html, {"1"})
    assert linked.count('class="z2m-fig-link"') == 1
    assert '<a href="#fig-1" class="z2m-fig-link"><a href="#fig-1"' not in linked


def test_link_figure_refs_unwraps_preexisting_nested_fig_links() -> None:
    html = (
        '<p><a href="#fig-1" class="z2m-fig-link">'
        '<a href="#fig-1" class="z2m-fig-link">Figure\xa01a</a>'
        "</a> supports this claim.</p>"
    )
    linked = _link_figure_refs(html, {"1"})
    assert linked.count('class="z2m-fig-link"') == 1
    assert '<a href="#fig-1" class="z2m-fig-link"><a href="#fig-1"' not in linked


def test_link_figure_refs_skips_caption_dots() -> None:
    """'Fig. 3.' (with trailing dot) is a caption, not an in-text ref."""
    html = '<p id="fig-3">Fig. 3. Caption text.</p>'
    linked = _link_figure_refs(html, {"3"})

    # The caption itself must not be wrapped
    assert linked.count('<a') == 0


def test_link_figure_refs_skips_unknown_figures() -> None:
    html = "<p>See Fig. 9 for details.</p>"
    linked = _link_figure_refs(html, {"1", "2"})

    assert 'href=' not in linked


def test_link_figure_refs_skips_inside_existing_anchor() -> None:
    html = '<p>See <a href="#x">Fig. 1 data</a>.</p>'
    linked = _link_figure_refs(html, {"1"})

    assert linked.count("<a") == 1


def test_polish_html_document_adds_figure_anchor_links() -> None:
    html = (
        "<html><body>"
        "<p>The circuit is shown in Fig. 1.</p>"
        "<p>Fig. 1. Circuit schematic.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html)

    assert 'id="fig-1"' in polished
    assert 'href="#fig-1"' in polished
    assert "z2m-fig-link" in polished


def test_polish_html_document_adds_figure_anchor_links_for_figure_keyword() -> None:
    html = (
        "<html><body>"
        "<p>The architecture is shown in Figure 1c and 1d.</p>"
        "<p>Figure 1. Architecture overview.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert 'id="fig-1"' in polished
    assert 'href="#fig-1"' in polished
    assert "Figure\xa01c" in polished


def test_polish_html_document_links_panel_suffix_to_base_figure_only() -> None:
    html = (
        "<html><body>"
        "<p>Figure 2D shows the final tactile rendering.</p>"
        "<p>A 2D tactile image remains ordinary prose.</p>"
        "<p>Figure 2. Multichannel panel overview.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-2"' in polished
    assert '<a href="#fig-2" class="z2m-fig-link">Figure\xa02D</a>' in polished
    assert 'href="#fig-2-d"' not in polished
    assert "A 2D tactile image remains ordinary prose." in polished


def test_polish_html_document_puts_figure_anchor_on_nearby_image() -> None:
    html = (
        "<html><body>"
        "<p>The architecture is shown in Fig. 1.</p>"
        '<p><img src="_page_1_Figure_1.jpeg"/></p>'
        "<p>Fig. 1. Architecture overview.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">' in polished
    assert '<p class="z2m-figure-target"><img src="_page_1_Figure_1.jpeg"/></p>' in polished
    assert '<p class="z2m-figure-caption">Figure 1. Architecture overview.</p>' in polished
    assert 'href="#fig-1"' in polished


def test_polish_html_document_puts_figure_anchor_on_delayed_image() -> None:
    html = (
        "<html><body>"
        "<p>The dura piercing workflow is shown in Fig. 8.</p>"
        "<p>Figure 8. Dura piercing and neural recording.</p>"
        "<p>a Micrographs showing different stages.</p>"
        "<p>https://BioRender.com/example.</p>"
        "<p>comparison shows normalized cell density.</p>"
        '<p><img src="_page_36_Figure_5.jpeg"/></p>'
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert '<div id="fig-8" class="z2m-float-unit z2m-figure-unit">' in polished
    assert '<p class="z2m-figure-target"><img src="_page_36_Figure_5.jpeg"/></p>' in polished
    assert polished.index('<p class="z2m-figure-target"><img src="_page_36_Figure_5.jpeg"/></p>') < polished.index("Figure 8. Dura piercing")
    assert "Figure 8 image was not extracted" not in polished
    assert 'href="#fig-8"' in polished


def test_polish_html_document_recovers_unlabeled_panel_figure_target() -> None:
    html = (
        "<html><body>"
        '<p><img src="_page_0_Figure_7.jpeg"/></p>'
        "<p>lower limit of normal). (A) Before surgery. (B) After surgery. (C) After recovery.</p>"
        '<p><img src="_page_1_Figure_0.jpeg"/></p>'
        "<p>FIGURE 2. Slow and rapid cystometrograms.</p>"
        "<p>The flow was reduced before treatment (Fig. 1A).</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">' in polished
    assert '<p class="z2m-figure-target"><img src="_page_0_Figure_7.jpeg"/></p>' in polished
    assert (
        '<p class="z2m-figure-caption">lower limit of normal). (A) Before surgery. '
        "(B) After surgery. (C) After recovery.</p>"
    ) in polished
    assert 'href="#fig-1"' in polished


def test_polish_html_document_recovers_ordered_orphan_figure_targets() -> None:
    html = (
        "<html><body>"
        "<p>Results</p>"
        '<p><img src="_page_2_Figure_11.jpeg"/></p>'
        '<p><img src="_page_3_Figure_2.jpeg"/></p>'
        "<p>The literature search produced the flow diagram (Fig. 1).</p>"
        "<h2>Correlation of visual outcome in both eyes</h2>"
        "<p>The pooled results are shown in Fig. 2.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert re.search(r'<div id="fig-1" class="[^"]*\bz2m-figure-unit\b', polished)
    assert re.search(r'<div id="fig-2" class="[^"]*\bz2m-figure-unit\b', polished)
    assert '<p class="z2m-figure-target"><img src="_page_2_Figure_11.jpeg"/></p>' in polished
    assert '<p class="z2m-figure-target"><img src="_page_3_Figure_2.jpeg"/></p>' in polished
    assert 'href="#fig-1"' in polished
    assert 'href="#fig-2"' in polished


def test_polish_html_document_recovers_next_unassigned_orphan_figure_ref() -> None:
    html = (
        "<html><body>"
        '<p><img src="_page_2_Figure_11.jpeg"/></p>'
        "<p>The selection flow is summarized in Fig. 1.</p>"
        '<p><img src="_page_3_Figure_2.jpeg"/></p>'
        "<p>The selection flow (Fig. 1) supports the pooled estimate in Fig. 2.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert re.search(r'<div id="fig-1" class="[^"]*\bz2m-figure-unit\b', polished)
    assert re.search(r'<div id="fig-2" class="[^"]*\bz2m-figure-unit\b', polished)
    assert 'href="#fig-1"' in polished
    assert 'href="#fig-2"' in polished


def test_polish_html_document_recovers_orphan_figure_after_nearby_ref() -> None:
    html = (
        "<html><body>"
        "<p>Participants described the scene after touching it (see Figure 4A).</p>"
        "<p>As in Figure 4, icons supported a plausible narrative.</p>"
        '<p><img src="_page_7_Figure_16.jpeg"/></p>'
        "<p>Another example of scale appears in Figure 3D.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert re.search(r'<div id="fig-4" class="[^"]*\bz2m-figure-unit\b', polished)
    assert '<p class="z2m-figure-target"><img src="_page_7_Figure_16.jpeg"/></p>' in polished
    assert 'href="#fig-4"' in polished


def test_polish_html_document_does_not_recover_after_ambiguous_previous_refs() -> None:
    html = (
        "<html><body>"
        "<p>The workflow combines Fig. 1 and Fig. 2.</p>"
        '<p><img src="_page_7_Figure_16.jpeg"/></p>'
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert 'id="fig-2"' not in polished


def test_polish_html_document_does_not_recover_table_adjacent_image_as_figure() -> None:
    html = (
        "<html><body>"
        "<p>Table 1 Studies included in the review.</p>"
        '<p><img src="_page_1_Figure_14.jpeg"/></p>'
        "<p>The final flow is summarized in Fig. 1.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert 'href="#fig-1"' not in polished


def test_polish_html_document_does_not_shift_orphan_targets_when_refs_outnumber_images() -> None:
    html = (
        "<html><body>"
        '<p><img src="_page_1_Figure_14.jpeg"/></p>'
        "<p>Table 1 Studies included in the analysis.</p>"
        "<table><tr><td>Study</td></tr></table>"
        '<p><img src="_page_2_Figure_11.jpeg"/></p>'
        '<p><img src="_page_3_Figure_2.jpeg"/></p>'
        "<p>The flow diagram is shown in Fig. 1.</p>"
        "<p>The correlation plots are shown in Fig. 2 and Fig. 3.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert 'id="fig-2"' not in polished
    assert 'id="fig-3"' not in polished
    assert 'href="#fig-1"' not in polished
    assert 'href="#fig-2"' not in polished
    assert 'href="#fig-3"' not in polished


def test_polish_html_document_repairs_sentence_split_by_figure_with_page_anchor_gap() -> None:
    html = (
        "<html><body>"
        "<p>Fibers may be myelinated or unmyelinated and</p>"
        '<span id="page-2-0"></span>'
        '<p><img src="_page_2_Picture_1.jpeg"/></p>'
        "<p>Fig. 2. Peripheral nerve anatomy.</p>"
        "<p>vary in diameter and conduction velocity.</p>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert "Fibers may be myelinated or unmyelinated and vary in diameter" in polished
    assert '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">' in polished


def test_polish_html_document_repairs_author_year_split_across_frontmatter_and_figure_gap() -> None:
    html = (
        "<html><body>"
        "<p>The nerve returns signals to the brainstem (Neuhuber and Berthoud 2021; "
        "Paggi et al. 2024; Upadhye et</p>"
        "<p block-type=\"Text\">Alfred E. Mann Department of Biomedical Engineering, "
        "University of Southern California, Los Angeles, USA</p>"
        "<p><img src=\"fig1.jpeg\"/></p>"
        "<p><b>Fig. 1</b> A graphical overview of the autonomic system.</p>"
        "<p>al. 2022). Therefore, stimulation of the entirety of the vagus nerve "
        "can result in off-target effects.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Upadhye et al. 2022). Therefore" in polished
    assert "Upadhye et</p>" not in polished
    assert "A graphical overview of the autonomic system" in polished


def test_polish_html_document_repairs_sentence_split_across_footnote_blocks() -> None:
    html = (
        "<html><body>"
        "<p>Titanium nitride can be deposited via reactive sputtering with a titanium target and</p>"
        "<p><sup>2</sup> Electrochemical impedance is the total opposition to alternating current. "
        "A lower value is more desirable for stimulation studies.</p>"
        "<p>nitrogen gas, where stoichiometric properties can be tuned.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "titanium target and nitrogen gas" in polished
    assert "z2m-footnote" in polished
    assert "Electrochemical impedance" in polished


def test_polish_html_document_links_refs_to_wrapped_figure_caption() -> None:
    html = (
        "<html><body>"
        "<p>The architecture is shown in Fig. 2.</p>"
        "<p><strong>Fig. 2</strong> | <strong>GAI development pipeline.</strong></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-2"' in polished
    assert 'href="#fig-2"' in polished
    assert polished.count('class="z2m-fig-link"') == 1


def test_polish_html_document_retargets_existing_page_figure_link() -> None:
    html = (
        "<html><body>"
        "<p>The architecture is shown in Fig. <a href=\"#page-2-0\">2(</a>A).</p>"
        "<p>The incubator is shown <a href=\"#page-1-0\">(Fig. 2)</a>.</p>"
        "<p>Representative traces appear in Fig. <a href=\"#page-2-1\">2d,e)</a>.</p>"
        "<p>Other subpanels appear in Fig. <a href=\"#page-2-2\">2g–i</a>.</p>"
        "<p><b> Fig. 2 </b> A cross-sectional diagram.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-2"' in polished
    assert 'href="#fig-2"' in polished
    assert 'href="#page-2-0"' not in polished
    assert 'href="#page-1-0"' not in polished
    assert 'href="#page-2-1"' not in polished
    assert 'href="#page-2-2"' not in polished


def test_polish_html_document_retargets_page_figure_lists_ranges_and_subpanels() -> None:
    html = (
        "<html><body>"
        "<p>Chronic illnesses are reduced in Figures 7 and <a href=\"#page-17-0\">15)</a>.</p>"
        "<p>User interaction is summarized for <a href=\"#page-8-0\">Figs. 8\u201312</a>.</p>"
        "<p>Ambiguous regions are shown in Figs. 10, <a href=\"#page-9-0\">11(a) and 12</a>.</p>"
        "<p>Attribute segmentation is shown in Figure <a href=\"#page-3-1\">1(a):</a></p>"
        '<p>The photograph for image <a href="#page-7-0">5e</a> is ambiguous, '
        'while Paris image (in <a href="#page-9-1">8j</a>) is clear.</p>'
        "<p><b>Figure 1</b> Attribute segmentation map.</p>"
        "<p><b>Figure 5</b> Tactile photographs.</p>"
        "<p><b>Figure 7</b> First pathway.</p>"
        "<p><b>Figure 8</b> Initial segment.</p>"
        "<p><b>Figure 11</b> Ambiguous regions.</p>"
        "<p><b>Figure 15</b> Chronic illness summary.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#fig-1"' in polished
    assert 'href="#fig-5"' in polished
    assert 'href="#fig-8"' in polished
    assert 'href="#fig-11"' in polished
    assert 'href="#fig-15"' in polished
    assert 'href="#page-3-1"' not in polished
    assert 'href="#page-7-0"' not in polished
    assert 'href="#page-8-0"' not in polished
    assert 'href="#page-9-0"' not in polished
    assert 'href="#page-9-1"' not in polished
    assert 'href="#page-17-0"' not in polished


def test_polish_html_document_unwraps_unresolved_semantic_page_links() -> None:
    html = (
        "<html><body>"
        '<p>Missing visual is discussed in Fig. <a href="#page-2-0">9A)</a> '
        'and Table <a href="#page-3-0">7)</a>.</p>'
        "<p><b> Fig. 1 </b> Extracted figure.</p>"
        "<p>Table 1. Extracted table.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Fig. 9A)" in polished
    assert "Table 7)" in polished
    assert 'href="#page-2-0"' not in polished
    assert 'href="#page-3-0"' not in polished


def test_table_anchors_and_links_handle_wrapped_labels_and_page_links() -> None:
    html = (
        "<html><body>"
        "<p>See Table <a href=\"#page-2-1\">1)</a> for parameters.</p>"
        "<p><b> Table 1 </b> Summary of stimulation parameters.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="table-1"' in polished
    assert 'href="#table-1"' in polished
    assert "z2m-table-link" in polished
    assert 'href="#page-2-1"' not in polished


def test_polish_html_document_links_plural_table_pair_with_page_link_tail() -> None:
    html = (
        "<html><body>"
        "<p>The respective improvements are provided in (Tables 6 and "
        "<a href=\"#page-9-1\">7)</a>.</p>"
        "<p><b>Table 6</b> First comparison.</p><table><tr><td>A</td></tr></table>"
        "<p><b>Table 7</b> Second comparison.</p><table><tr><td>B</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#table-6"' in polished
    assert 'href="#table-7"' in polished
    assert 'href="#page-9-1"' not in polished
    assert 'Tables <a href="#table-6"' not in polished
    assert '<a href="#table-6" class="z2m-table-link">Tables\xa06</a>' in polished
    assert '<a href="#table-7" class="z2m-table-link">7</a>)' in polished


def test_polish_html_document_repairs_ru_table_pair_with_misclassified_ref() -> None:
    html = (
        "<html><body>"
        "<p>Описательная статистика приведена в таблицах 1 и <sup>2</sup>.</p>"
        "<p>Анализ представлен в Table 4 и <sup>5</sup>.</p>"
        "<p>TABLE 1. Female descriptive statistics.</p><table><tr><td>A</td></tr></table>"
        "<p>TABLE 2. Male descriptive statistics.</p><table><tr><td>B</td></tr></table>"
        "<p>TABLE 4. Bland-Altman analysis for Qmax and PVR.</p><table><tr><td>C</td></tr></table>"
        "<p>TABLE 5. Male Qmax comparison.</p><table><tr><td>D</td></tr></table>"
        "<h4>References</h4><ol>"
        "<li>Reference one.</li><li>Reference two.</li><li>Reference three.</li>"
        "<li>Reference four.</li><li>Reference five.</li>"
        "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="ru")

    assert 'href="#table-1"' in polished
    assert 'href="#table-2"' in polished
    assert 'href="#table-4"' in polished
    assert 'href="#table-5"' in polished
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' not in polished
    assert '<a href="#ref-5" class="z2m-ref-link">5</a>' not in polished
    assert '<sup><a href="#table-2"' not in polished
    assert '<sup><a href="#table-5"' not in polished
    assert "Таблица 4" in polished


def test_polish_html_document_repairs_existing_ru_table_ref_links_when_linkify_disabled() -> None:
    html = (
        "<html><body>"
        '<p>Описательная статистика приведена в таблицах 1 и '
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>.</p>'
        "<p>Дополнительный анализ приведен в Таблицы 1 и <sup>2</sup>.</p>"
        "<p>TABLE 1. Female descriptive statistics.</p><table><tr><td>A</td></tr></table>"
        "<p>TABLE 2. Male descriptive statistics.</p><table><tr><td>B</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="ru",
        enable_citation_linkify=False,
    )

    assert '<a href="#table-1" class="z2m-table-link">таблицах\xa01</a>' in polished
    assert '<a href="#table-2" class="z2m-table-link">2</a>' in polished
    assert '<a href="#table-1" class="z2m-table-link">Таблицы\xa01</a>' in polished
    assert 'href="#ref-2"' not in polished
    assert '<sup><a href="#table-2"' not in polished


def test_polish_html_document_localizes_ru_plural_table_link_label() -> None:
    html = (
        "<html><body>"
        "<p>Анализ представлен в Tables 4 and 5.</p>"
        "<p>TABLE 4. Bland-Altman analysis for Qmax and PVR.</p><table><tr><td>C</td></tr></table>"
        "<p>TABLE 5. Male Qmax comparison.</p><table><tr><td>D</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="ru")

    assert '<a href="#table-4" class="z2m-table-link">Таблицы 4</a>' in polished
    assert '<a href="#table-5" class="z2m-table-link">5</a>' in polished
    assert "Tables 4" not in polished


def test_polish_html_document_retargets_page_table_pair_and_appendix_label() -> None:
    html = (
        "<html><body>"
        "<p>Tables <a href=\"#page-17-2\">1</a> and <a href=\"#page-18-0\">2</a> summarize outcomes.</p>"
        "<p>Tables 5\u2010 <a href=\"#page-65-1\">6.</a> report strata.</p>"
        "<p>Table <a href=\"#page-16-0\">A1</a> summarizes interaction projects.</p>"
        "<p>Significant differences are listed in Tables <a href=\"#page-8-1\">I</a> "
        "<a href=\"#page-9-0\">\u2013III)</a>.</p>"
        "<p><b>Table 1</b> Baseline characteristics.</p><table><tr><td>A</td></tr></table>"
        "<p><b>Table 2</b> Follow-up characteristics.</p><table><tr><td>B</td></tr></table>"
        "<p><b>Table 6</b> Strata outcomes.</p><table><tr><td>D</td></tr></table>"
        "<p><b>Table A1</b> Interactive technologies.</p><table><tr><td>C</td></tr></table>"
        "<p><b>Table I</b> SNR outcomes.</p><table><tr><td>E</td></tr></table>"
        "<p><b>Table III</b> Contrast outcomes.</p><table><tr><td>F</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="table-a1"' in polished
    assert 'id="table-i"' in polished
    assert 'id="table-iii"' in polished
    assert 'href="#table-1"' in polished
    assert 'href="#table-2"' in polished
    assert 'href="#table-6"' in polished
    assert 'href="#table-a1"' in polished
    assert 'href="#table-i"' in polished
    assert 'href="#table-iii"' in polished
    assert 'href="#page-16-0"' not in polished
    assert 'href="#page-17-2"' not in polished
    assert 'href="#page-18-0"' not in polished
    assert 'href="#page-65-1"' not in polished
    assert 'href="#page-8-1"' not in polished
    assert 'href="#page-9-0"' not in polished


def test_polish_html_document_preserves_compound_figure_and_table_numbers() -> None:
    image = _valid_tiny_png_data_url()
    html = (
        "<html><body>"
        "<p>See Figure 3.24 and Table 3.1 for the extracted features.</p>"
        f'<p><img src="{image}"/></p>'
        "<p>Figure 3.24: MATLAB Uroflow algorithm.</p>"
        "<p><b>Table 3.1:</b> The features used by the classifier.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-3-24"' in polished
    assert 'href="#fig-3-24"' in polished
    assert 'id="fig-3"' not in polished
    assert 'id="table-3-1"' in polished
    assert 'href="#table-3-1"' in polished
    assert 'id="table-3"' not in polished


def test_polish_html_document_preserves_chapter_style_figure_and_table_numbers() -> None:
    html = (
        "<html><body>"
        "<p>See Figure 57-5 and Table 57-1 for the measurement setup.</p>"
        "<p>Figure 57-5. Multichannel urodynamic study.</p>"
        "<p>Table 57-1. Urodynamic parameters.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-57-5"' in polished
    assert 'href="#fig-57-5"' in polished
    assert 'id="fig-57"' not in polished
    assert 'id="table-57-1"' in polished
    assert 'href="#table-57-1"' in polished
    assert 'id="table-57"' not in polished


def test_polish_html_document_anchors_table_caption_inside_first_header_cell() -> None:
    html = (
        "<html><body>"
        "<p>The classification is described in Table 57-1.</p>"
        "<table><tbody>"
        '<tr><th colspan="2">Table 57-1<br/>Radiologic Type of Stress Incontinence</th></tr>'
        "<tr><th>Type</th><th>Description</th></tr>"
        "<tr><td>I</td><td>Incontinence is seen.</td></tr>"
        "</tbody></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<table id="table-57-1">' in polished
    assert 'href="#table-57-1"' in polished
    assert 'id="table-57"' not in polished


def test_polish_html_document_anchors_table_caption_inside_header_row() -> None:
    html = (
        "<html><body>"
        "<p>The included studies are summarized in Table 3.</p>"
        "<table><tbody>"
        "<tr>"
        "<th>Arif25<br/>Raja50<br/>Salinas50</th>"
        "<th>Table 3</th>"
        "<th>Included studies and clinical outcomes.</th>"
        "</tr>"
        "<tr><td>Study</td><td>Design</td><td>Outcome</td></tr>"
        "</tbody></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<table id="table-3">' in polished
    assert 'href="#table-3"' in polished


def test_polish_html_document_preserves_table_caption_above_source_table() -> None:
    html = (
        "<html><body>"
        "<p><b>Table 6</b> A comparison of materials.</p>"
        "<table><tr><td>Material</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    wrapper_start = polished.index('<div id="table-6" class="z2m-float-unit z2m-table-unit">')
    caption_index = polished.index("z2m-table-caption", wrapper_start)
    table_index = polished.index("<table>", wrapper_start)

    assert caption_index < table_index


def test_polish_html_document_wraps_loose_table_caption_targets() -> None:
    html = (
        "<html><body>"
        "<p><b>Table 4</b> A comparison of values.</p>"
        "<p><b>Table 5</b> Next comparison.</p><table><tr><td>B</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<p id="table-4"' not in polished
    assert '<div id="table-4" class="z2m-float-unit z2m-table-unit">' in polished
    assert '<div id="table-5" class="z2m-float-unit z2m-table-unit">' in polished


def test_polish_html_document_pairs_caption_with_following_table_after_consumed_table() -> None:
    html = (
        "<html><body>"
        "<p>Table 6. Database coverage.</p><table><tr><td>Scopus</td></tr></table>"
        "<p>Table 7. Geographic distribution per country.</p>"
        "<table><tr><th>Country</th></tr><tr><td>Italy</td></tr></table>"
        "<p>Table 8. Common number of participants for evaluation.</p>"
        "<table><tr><th>Participants</th></tr><tr><td>1-5</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    table7_start = polished.index('<div id="table-7"')
    table7 = polished[table7_start:polished.index("</div>", table7_start)]
    table8_start = polished.index('<div id="table-8"')
    table8 = polished[table8_start:polished.index("</div>", table8_start)]

    assert "Geographic distribution per country" in table7
    assert "Italy" in table7
    assert "Common number of participants" not in table7
    assert "Common number of participants" in table8
    assert "Participants" in table8
    assert "Italy" not in table8


def test_polish_html_document_closes_loose_table_unit_before_numbered_section() -> None:
    html = (
        "<html><body>"
        '<div id="table-3-1" class="z2m-float-unit z2m-table-unit">'
        '<p class="z2m-table-caption">TABLE 3.1. The features used by the classifier.</p>'
        "<p>The First curve peak is listed here.</p>"
        '<h3 id="section-3-8">3.8. Data Acquisition</h3>'
        "<p>The uroflowmetry device records the signal.</p>"
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    table_start = polished.index('<div id="table-3-1"')
    table_end = polished.index("</div>", table_start)

    assert 'id="section-3-8"' not in polished[table_start:table_end]
    assert polished.index('id="section-3-8"') > table_end


def test_table_anchors_and_links_handle_heading_captions() -> None:
    html = (
        "<html><body>"
        "<p>The parameters are listed in Table II.</p>"
        "<h4>TABLE II SENSOR PARAMETERS</h4>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="table-ii"' in polished
    assert 'href="#table-ii"' in polished
    assert polished.count('href="#table-ii"') == 1


def test_polish_html_document_repairs_existing_false_figure_label_sup_and_links_subfigures() -> None:
    html = (
        "<html><body>"
        "<p>The architecture is shown in Figure 1c and 1d.</p>"
        "<p>Figure <sup><a href=\"#ref-1\" class=\"z2m-ref-link\">1</a></sup>. Architecture overview.</p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 5)) + "</ul>"
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert "Figure <sup>" not in polished
    assert 'id="fig-1"' in polished
    assert "Figure\xa01c" in polished
    assert ">1d</a>" in polished


def test_link_figure_refs_handles_fig_transliteration() -> None:
    """'Фиг. 3' (translation of 'Fig. 3' by some models) must get a link."""
    html = "<p>Как показано на Фиг. 3 в данной работе.</p>"
    linked = _link_figure_refs(html, {"3"})
    assert 'href="#fig-3"' in linked
    assert "z2m-fig-link" in linked


def test_link_figure_refs_handles_figura_transliteration() -> None:
    """'Фигура 5' (extended form of 'Figure') must get a link."""
    html = "<p>Как показано на Фигура 5 в данной работе.</p>"
    linked = _link_figure_refs(html, {"5"})
    assert 'href="#fig-5"' in linked
    assert "z2m-fig-link" in linked


def test_add_figure_anchors_handles_fig_transliteration_in_caption() -> None:
    """A caption starting with 'Фиг. 3.' must get id='fig-3'."""
    html = "<p>Фиг. 3. Схема устройства.</p>"
    result, found = _add_figure_anchors(html)
    assert "3" in found
    assert 'id="fig-3"' in result


def test_polish_html_document_pairs_image_grid_with_caption_run() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig15.png"/></p>'
        '<p><img src="fig16.png"/></p>'
        "<p>Figure 15: Plot of the out of box mean squared error.</p>"
        "<p>Figure 16: A predictor importance plot.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-15"' in polished
    assert 'id="fig-16"' in polished
    fig15 = polished[polished.index('id="fig-15"') : polished.index('id="fig-16"')]
    fig16 = polished[polished.index('id="fig-16"') :]
    fig15_text = re.sub(r"<[^>]+>", " ", fig15).replace("\xa0", " ")
    fig16_text = re.sub(r"<[^>]+>", " ", fig16).replace("\xa0", " ")
    assert "fig15.png" in fig15
    assert "Figure 15" in fig15_text
    assert "Plot of the out of box mean squared error." in fig15_text
    assert "fig16.png" in fig16
    assert "Figure 16" in fig16_text
    assert "A predictor importance plot." in fig16_text


def test_polish_html_document_aliases_single_image_with_multiple_captions() -> None:
    html = (
        "<html><body>"
        "<p>The ridge model is shown in Fig. 14.</p>"
        '<p><img src="combined.png"/></p>'
        "<p>Figure 13: First ridge-regression diagnostic.</p>"
        "<p>Figure 14: Second ridge-regression diagnostic.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<div id="fig-13" class="z2m-float-unit z2m-figure-unit">' in polished
    assert '<span id="fig-14" class="z2m-float-alias"></span>' in polished
    assert 'href="#fig-14"' in polished
    assert polished.count('id="fig-14"') == 1


def test_polish_html_document_does_not_alias_caption_that_starts_next_image_run() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig4.jpg"/></p>'
        "<p>Figure 4. Three glossy collodion photographs mounted on solid matte board.</p>"
        "<p>Figure 5. Unmounted, untoned glossy collodion photograph.</p>"
        '<p><img src="fig6.jpg"/></p>'
        "<p>Figure 6. Mounted, gold-toned semi-glossy collodion photograph.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig4_start = polished.index('<div id="fig-4"')
    fig4 = polished[fig4_start : polished.index("</div>", fig4_start)]
    fig6_start = polished.index('<div id="fig-6"')
    fig6 = polished[fig6_start : polished.index("</div>", fig6_start)]

    assert "Figure 4." in fig4
    assert "Figure 5." not in fig4
    assert '<span id="fig-5" class="z2m-float-alias"></span>' not in fig4
    assert 'src="fig6.jpg"' in fig6
    assert "Figure 6." in fig6


def test_polish_html_document_pairs_caption_before_image_after_prior_figure_target() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig23.jpg"/></p>'
        "<p>Figure 23. Prior spectrum.</p>"
        "<p>Colorant examples are discussed below.</p>"
        "<p>Figure 24. Untinted and tinted versions of a matte-collodion photograph.</p>"
        '<p><img src="fig24.jpg"/></p>'
        "<p><b>Figure 25</b> Analytical spots highlighting colorants.</p>"
        '<p><img src="fig25.jpg"/></p>'
        "<p>Only the dots of thick white paint indicate zinc.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig24_start = polished.index('<div id="fig-24"')
    fig24 = polished[fig24_start : polished.index("</div>", fig24_start)]
    fig25_start = polished.index('<div id="fig-25"')
    fig25 = polished[fig25_start : polished.index("</div>", fig25_start)]

    assert 'src="fig24.jpg"' in fig24
    assert "Figure 24." in fig24
    assert "Figure 25" not in fig24
    assert 'src="fig25.jpg"' in fig25
    assert "Figure\xa025" in fig25


def test_polish_html_document_retargets_split_page_figure_link_word_and_number() -> None:
    html = (
        "<html><body>"
        '<p>The grids are shown in <a href="#page-20-0">(Fig</a> 15).</p>'
        "<p>Fig. 15. Classifier diagnostics.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#fig-15"' in polished
    assert 'href="#page-20-0"' not in polished


def test_polish_html_document_does_not_treat_figure_list_numbers_as_refs() -> None:
    html = (
        "<html><body>"
        "<p>The panels are shown in (Figs. 3 and <sup>5</sup>).</p>"
        "<p>Fig. 3. First panel.</p><p><img src=\"fig3.png\"/></p>"
        "<p>Fig. 5. Second panel.</p><p><img src=\"fig5.png\"/></p>"
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 6)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#fig-5" class="z2m-fig-link">5</a>' in polished
    assert 'href="#ref-5" class="z2m-ref-link">5</a>' not in polished[: polished.index("References")]


def test_link_section_refs_handles_russian_case_forms() -> None:
    """Genitive (Раздела) and locative (Разделе) case forms must create links."""
    html = "<p>Описано в Разделе II и результаты Раздела III представлены ниже.</p>"
    linked = _link_section_refs(html, {"II", "III"})
    assert 'href="#section-II"' in linked
    assert 'href="#section-III"' in linked


def test_polish_html_document_adds_appendix_anchor_with_page_span() -> None:
    html = (
        "<html><body>"
        '<h2><span id="page-20-0"></span>Appendix B More information about classifiers</h2>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="section-appendix-b"' in polished


def test_polish_html_document_links_equation_refs_to_equation_rows() -> None:
    html = (
        "<html><body>"
        "<p>The resulting relationship is shown in Equation 8.</p>"
        '<p block-type="Equation">\\[y = x + 1\\] (8)</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="eq-8"' in polished
    assert 'href="#eq-8"' in polished


def test_polish_html_document_unwraps_decimal_equation_page_links() -> None:
    html = (
        "<html><body>"
        '<p>The dynamics are shown in Eqn. <a href="#page-7-0">2.1)</a>.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Eqn. 2.1)" in polished
    assert 'href="#page-7-0"' not in polished


def test_polish_html_document_unwraps_broken_page_anchor_links() -> None:
    html = (
        "<html><body>"
        '<p><b><a href="#page-10-0">Chapter 2 cameras</a></b></p>'
        '<p>See <a href="#page-11-0">page 11</a> for more detail.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Chapter 2 cameras" in polished
    assert "page 11" in polished
    assert 'href="#page-10-0"' not in polished
    assert 'href="#page-11-0"' not in polished


def test_polish_html_document_keeps_working_page_anchor_links() -> None:
    html = (
        "<html><body>"
        '<span id="page-11-0"></span>'
        '<p>See <a href="#page-11-0">page 11</a> for more detail.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="page-11-0"' in polished
    assert 'href="#page-11-0"' in polished


def test_polish_html_document_unwraps_ru_page_reference_page_links() -> None:
    html = (
        "<html><body>"
        '<span id="page-33-0"></span><span id="page-63-0"></span>'
        '<p>Параллакс возникает <a href="#page-33-0">см. с. 34</a> '
        'и см. с. <a href="#page-63-0">64</a>, но обычная ссылка остается '
        '<a href="#page-11-0">page 11</a>.</p>'
        '<span id="page-11-0"></span>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="ru")
    compact = re.sub(r"\s+", " ", polished)

    assert "см. с. 34" in compact
    assert "см. с. 64" in compact
    assert 'href="#page-33-0"' not in polished
    assert 'href="#page-63-0"' not in polished
    assert 'href="#page-11-0"' in polished


def test_polish_html_document_keeps_ru_page_references_in_en_policy() -> None:
    html = (
        "<html><body>"
        '<span id="page-33-0"></span>'
        '<p>Параллакс возникает <a href="#page-33-0">см. с. 34</a>.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#page-33-0"' in polished


def test_polish_html_document_retargets_ru_see_figure_page_link() -> None:
    html = (
        "<html><body>"
        '<span id="page-35-0"></span>'
        '<p>Параллакс возникает <a href="#page-35-0">см. рис. 2.9</a>.</p>'
        "<p>Рис. 2.9. Видоискатель камеры.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en", polish_language="ru")

    assert 'href="#fig-2-9" class="z2m-fig-link">см. рис. 2.9</a>' in polished
    assert 'href="#page-35-0"' not in polished


def test_polish_html_document_keeps_ru_see_figure_page_link_in_en_policy() -> None:
    html = (
        "<html><body>"
        '<span id="page-35-0"></span>'
        '<p>Параллакс возникает <a href="#page-35-0">см. рис. 2.9</a>.</p>'
        "<p>Рис. 2.9. Видоискатель камеры.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="ru", polish_language="en")

    assert 'href="#page-35-0"' in polished
    assert 'href="#fig-2-9" class="z2m-fig-link">см. рис. 2.9</a>' not in polished


def test_polish_html_document_unwraps_unresolved_ru_see_figure_page_link() -> None:
    html = (
        "<html><body>"
        '<span id="page-35-0"></span>'
        '<p>Параллакс возникает <a href="#page-35-0">см. рис. 2.9</a>.</p>'
        "<p>Рис. 2.8. Видоискатель камеры.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en", polish_language="ru")
    compact = re.sub(r"\s+", " ", polished)

    assert "см. рис. 2.9" in compact
    assert 'href="#page-35-0"' not in polished


def test_polish_html_document_anchors_text_equation_and_retargets_page_link() -> None:
    html = (
        "<html><body>"
        '<p>The fairest comparison used Eq. <a href="#page-4-1">(3).</a></p>'
        '<span id="page-4-1"></span>'
        '<p block-type="Text">SNR = \\(20 \\log_{10} S\\). (3)</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="eq-3"' in polished
    assert 'href="#eq-3"' in polished
    assert 'href="#page-4-1"' not in polished


def test_polish_html_document_retargets_numeric_page_link_section_ref() -> None:
    html = (
        "<html><body>"
        '<p>As described in Section <a href="#page-3-1">3.2,</a> the model is stable.</p>'
        "<h2>3.2 Model details</h2>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#section-3-2" class="z2m-section-link">3.2,</a>' in polished
    assert 'href="#page-3-1"' not in polished


def test_polish_html_document_unwraps_unresolved_section_appendix_equation_page_refs() -> None:
    html = (
        "<html><body>"
        '<span id="page-6-0"></span><span id="page-7-0"></span>'
        '<span id="page-8-0"></span><span id="page-8-1"></span>'
        '<p>Values are defined in <a href="#page-6-0">Eq 1</a> and Appendix '
        '<a href="#page-7-0">A)</a>.</p>'
        '<p>Later we discuss Section <a href="#page-8-0">4.1,</a> but the heading is missing.</p>'
        '<p>Plural ranges stay as page navigation when no semantic target exists in Sections 3.4, 4 and '
        '<a href="#page-8-1">5.</a></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "Eq 1" in compact
    assert "Appendix A)" in compact
    assert "Section 4.1," in compact
    assert 'href="#page-6-0"' not in polished
    assert 'href="#page-7-0"' not in polished
    assert 'href="#page-8-0"' not in polished
    assert '<a href="#page-8-1">5.</a>' in polished


def test_polish_html_document_unwraps_split_unresolved_figure_table_page_labels() -> None:
    html = (
        "<html><body>"
        '<span id="page-2-0"></span><span id="page-3-0"></span><span id="page-4-0"></span>'
        '<p><a href="#page-2-0">Figure</a> 9 shows the hard task.</p>'
        '<p>Results are aggregated in <a href="#page-3-0">Table</a> 2.</p>'
        '<p>The phrase figure of merit keeps its page link '
        '<a href="#page-4-0">Figure</a> of merit.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "Figure 9 shows" in compact
    assert "Table 2." in compact
    assert 'href="#page-2-0"' not in polished
    assert 'href="#page-3-0"' not in polished
    assert 'href="#page-4-0"' in polished


def test_polish_html_document_retargets_plural_figure_section_page_ref_tails() -> None:
    html = (
        "<html><body>"
        '<span id="page-8-0"></span><span id="page-5-0"></span>'
        '<p>Error zones are shown in Figs '
        '<a href="#fig-2" class="z2m-fig-link">2A,</a> 3A and '
        '<a href="#page-8-0">4A)</a>.</p>'
        '<p>Flow limitations appear in Sections 2 and <a href="#page-5-0">3)</a>.</p>'
        '<p>Fig. 4. Example.</p>'
        '<h2>3. Results</h2>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert 'href="#fig-4" class="z2m-fig-link">4A)</a>' in polished
    assert "Sections 2 and 3)" in compact
    assert 'href="#page-8-0"' not in polished
    assert 'href="#page-5-0"' not in polished


def test_polish_html_document_links_box_refs_and_frames_box() -> None:
    html = (
        "<html><body>"
        "<p>See Box 1).</p>"
        "<p>Box 1. Optogenetics resources.</p>"
        "<p>Use the resources when choosing a light source.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<div id="box-1" class="z2m-float-unit z2m-box-unit">' in polished
    assert 'href="#box-1"' in polished
    assert "z2m-box-link" in polished


def test_polish_html_document_consumes_page_anchor_reference_label() -> None:
    html = (
        "<html><body>"
        "<p>Prior work supports this claim<sup>1</sup>.</p>"
        "<h4>References</h4>"
        '<ul><li><a href="#page-9-0">1</a>. First reference.</li></ul>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<span class="z2m-ref-num">1.</span> First reference.' in polished
    assert '<span class="z2m-ref-num">1.</span> <a href="#page-9-0">1</a>' not in polished


def test_polish_html_document_repairs_recent_meine_link_false_positives() -> None:
    html = (
        "<html><body>"
        '<p>Evidence <sup><a href="#ref-3" class="z2m-ref-link">9</a></sup> '
        'and Agarwal.3 remained visible. Smith et al3 agreed. The impedance 2 for recording, '
        '(CSC) 3 and (CIC)4 for capacity stayed linked.</p>'
        '<p><a href="#ref-1" class="z2m-ref-link">Bandettini, 1999</a> and '
        '<a href="#ref-2" class="z2m-ref-link">Lederman</a> et al. (1990) are author-year citations.</p>'
        '<p>Smith, 2020, Jones, 2019, Brown, 2018, and White, 2017 are plain author-year citations. '
        'Photographs are uploaded every day<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>. '
        'The Z values range from about <sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> to 4. '
        'The term is used<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>.</p>'
        '<p>Earlier work (Gaillard et al., 1999, <a href="#page-8-0">2000)</a> remains author-year text.</p>'
        '<p>A study (Dehaene-Lambertz et al., <a href="#page-8-1">2002)</a> also remains text.</p>'
        '<p>More work (Teng et al., <a href="#page-8-2">2012;</a> Kolarik et al., 2017) remains text.</p>'
        '<p>Optimization (Bonizzato et al <a href="#page-8-3">2023)</a> was cited.</p>'
        '<span id="page-8-4"></span>'
        '<p>The results are discussed in Sections 3.4, 4 and <a href="#page-8-4">5.</a></p>'
        '<p>Power analysis used effect size <a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-5" class="z2m-ref-link">5</a> and G*Power group '
        '<a href="#ref-2" class="z2m-ref-link">2</a>.</p>'
        '<p>The capacity (CSC) <sup class="z2m-footnote-ref">3</sup> and Merrill et al. '
        '<a href="#ref-8" class="z2m-ref-link">2005)</a> 5 . stayed linked.</p>'
        '<p>A fragment <a href="#page-4-0">that formulas that use the total</a> should be prose.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 10)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert '<a href="#ref-9" class="z2m-ref-link">9</a>' in polished
    assert 'Agarwal.<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>' in polished
    assert 'Smith et al<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>' in polished
    assert 'impedance <sup>2</sup> for recording' in polished
    assert '(CSC) <sup>3</sup> and (CIC)' in polished
    assert '(CIC)<sup>4</sup> for capacity' in polished
    assert '(CSC) <sup class="z2m-footnote-ref">3</sup> and Merrill' in polished
    assert '2005)</a><sup><a href="#ref-5" class="z2m-ref-link">5</a></sup>.' in polished
    assert 'href="#ref-1" class="z2m-ref-link">Bandettini' not in polished
    assert 'href="#ref-2" class="z2m-ref-link">Lederman' not in polished
    assert 'every day<sup>1</sup>' in polished
    assert 'range from about <sup>3</sup> to 4' in compact
    assert 'used<sup>3</sup>' in polished
    assert 'Gaillard et al., 1999, 2000)' in compact
    assert 'Dehaene-Lambertz et al., 2002)' in compact
    assert 'Teng et al., 2012; Kolarik et al., 2017' in compact
    assert 'Bonizzato et al 2023)' in compact
    assert 'href="#page-8-0"' not in polished
    assert 'href="#page-8-1"' not in polished
    assert 'href="#page-8-2"' not in polished
    assert 'href="#page-8-3"' not in polished
    assert '<a href="#page-8-4">5.</a>' in polished
    assert 'effect size <a href="#ref-1"' not in polished
    assert "effect size 1,5" in compact
    assert 'href="#page-4-0"' not in polished
    assert "that formulas that use the total" in polished


def test_polish_html_document_unwraps_ru_page_reference_false_ref_links() -> None:
    html = (
        "<html><body>"
        '<p>Одни представляют черный, <a href="#ref-108" class="z2m-ref-link">см. с. 239</a> '
        'и белый тон. См. с. <a href="#ref-34" class="z2m-ref-link">34</a> для примера. '
        'Нормальная ссылка остается <a href="#ref-3" class="z2m-ref-link">[3]</a>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 110)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="ru")
    compact = re.sub(r"\s+", " ", polished)

    assert "см. с. 239" in compact
    assert "См. с. 34" in compact
    assert 'href="#ref-108" class="z2m-ref-link">см. с. 239</a>' not in polished
    assert 'href="#ref-34" class="z2m-ref-link">34</a>' not in polished
    assert '<a href="#ref-3" class="z2m-ref-link">[3]</a>' in polished


def test_polish_html_document_keeps_ru_page_reference_ref_links_in_en_policy() -> None:
    html = (
        "<html><body>"
        '<p>Одни представляют черный, <a href="#ref-108" class="z2m-ref-link">см. с. 239</a>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 110)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#ref-108" class="z2m-ref-link">см. с. 239</a>' in polished


def test_polish_html_document_repairs_page_anchor_letter_glued_superscript_citations() -> None:
    html = (
        "<html><body>"
        '<p>from W <a href="#page-9-0">M11</a><a href="#page-10-0">,19</a>. '
        'More details can be found i <a href="#page-10-1">n20.</a></p>'
        '<p>We performed a demixed principal components analysis (dPCA '
        '<a href="#page-10-1">)20</a> to compress the data.</p>'
        "<h4>References</h4>"
        "<ul>"
        + "".join(f"<li>Ref {i}.</li>" for i in range(1, 21))
        + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert 'href="#page-9-0"' not in polished
    assert 'href="#page-10-0"' not in polished
    assert 'href="#page-10-1"' not in polished
    assert 'WM<sup><a href="#ref-11" class="z2m-ref-link">11</a>' in compact
    assert '<a href="#ref-19" class="z2m-ref-link">,19</a></sup>' in compact
    assert 'found in<sup><a href="#ref-20" class="z2m-ref-link">20</a></sup>.' in compact
    assert '(dPCA)<sup><a href="#ref-20" class="z2m-ref-link">20</a></sup>' in compact


def test_polish_html_document_repairs_split_open_bracket_page_citation_range() -> None:
    html = (
        "<html><body>"
        '<p>Patients should be evaluated accordingly <a href="#page-18-0">[26</a>-29].</p>'
        "<h4>References</h4>"
        "<ul>"
        + "".join(f"<li>Ref {i}.</li>" for i in range(1, 30))
        + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "</a></a>" not in polished
    assert 'href="#page-18-0"' not in polished
    assert '[<a href="#ref-26" class="z2m-ref-link">26</a>-<a href="#ref-29" class="z2m-ref-link">29</a>]' in compact


def test_polish_html_document_unwraps_decimal_figure_page_link_without_matching_target() -> None:
    html = (
        "<html><body>"
        '<p>One component is not necessarily associated with the others <a href="#page-1-0">(Fig. 6.1</a>).</p>'
        '<p>The tests are useful for diagnosis (<a href="#page-1-1">Tables 6.1</a> and '
        '<a href="#page-1-2">6.2)</a>.</p>'
        "<p>Figure 6. Extracted overview image.</p>"
        "<p><img src=\"fig6.png\"/></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert 'href="#page-1-0"' not in polished
    assert 'href="#page-1-1"' not in polished
    assert 'href="#page-1-2"' not in polished
    assert "(Fig. 6.1)." in compact
    assert "(Tables 6.1 and 6.2)." in compact


def test_polish_html_document_repairs_known_kuznietsov_surname_split() -> None:
    html = "<html><body><p>Kuznietso v et al. [24] introduced a semi-supervised approach.</p></body></html>"

    polished = polish_html_document(html, table_caption_language="en")

    assert "Kuznietsov et al." in polished
    assert "Kuznietso v" not in polished


def test_polish_html_document_repairs_empty_and_nested_reference_anchors() -> None:
    html = (
        "<html><body>"
        '<p>Flexible electrodes <a href="#ref-51" class="z2m-ref-link"></a>'
        '[<a href="#ref-51" class="z2m-ref-link">51</a>] and carriers '
        '<a href="#ref-13" class="z2m-ref-link">[<a href="#ref-13" class="z2m-ref-link">13</a>, '
        '<a href="#ref-52" class="z2m-ref-link">52</a>]</a>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 53)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-51" class="z2m-ref-link"></a>' not in body
    assert '<a href="#ref-13" class="z2m-ref-link">[<a' not in body
    assert '[<a href="#ref-13" class="z2m-ref-link">13</a>, <a href="#ref-52" class="z2m-ref-link">52</a>]' in body


def test_polish_html_document_repairs_nested_author_year_reference_links() -> None:
    html = (
        "<html><body>"
        '<p>Objects represented in 3D are costly (<a href="#ref-3" class="z2m-ref-link">'
        '<a href="#ref-3" class="z2m-ref-link">Biederman, 1987</a>)</a>.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 4)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-3" class="z2m-ref-link"><a' not in body
    assert 'href="#ref-3"' not in body
    assert "(Biederman, 1987)." in body


def test_polish_html_document_repairs_dangling_outer_reference_anchor() -> None:
    html = (
        "<html><body>"
        '<p>Restoring vision <a href="#ref-30" class="z2m-ref-link">'
        '[<a href="#ref-30" class="z2m-ref-link">30</a>, '
        '<a href="#ref-69" class="z2m-ref-link">69</a>, '
        '<a href="#ref-70" class="z2m-ref-link">70</a>], but cortex continues.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 71)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-30" class="z2m-ref-link">[<a' not in body
    assert 'Restoring vision [<a href="#ref-30" class="z2m-ref-link">30</a>' in body


def test_polish_html_document_repairs_table_word_splits_without_losing_roman_text() -> None:
    html = (
        "<html><body>"
        "<p>Reproduced from (Kori vi &amp; Ajmera, 2011).</p>"
        "<p>The cuff was introduced by Kori vi and Ajmera in 2011.</p>"
        "<p>Pakenaite K, Nedele v P, Kamperou E.</p>"
        "<table><tr>"
        '<td>Dorsal root gan glion</td>'
        '<td>Cylindrical mult<sup class="z2m-table-fn">i</sup>-electrode leads</td>'
        '<td>Comple<sup class="z2m-table-fn">x</sup> regional pain syn drome Types I and'
        '<sup class="z2m-table-fn">ii</sup></td>'
        '<td>NeuR<sup class="z2m-table-fn">x</sup> Diaphragm Pacing/Syn apse Biomedical</td>'
        '<td>Matr<sup class="z2m-table-fn">ix</sup> coils</td>'
        "<td>Percutaneous intramuscu lar diaphragm electrodes</td>"
        '<td>Rev<sup class="z2m-table-fn">i</sup> Tibial Neuromodulation System</td>'
        '<td>Freedom PNS System/Curon<sup class="z2m-table-fn">ix</sup></td>'
        "</tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Dorsal root ganglion" in polished
    assert "Cylindrical multi-electrode leads" in polished
    assert "Complex regional pain syndrome Types I and II" in polished
    assert "Korivi &amp; Ajmera" in polished
    assert "Korivi and Ajmera" in polished
    assert "Nedelev P" in polished
    assert "NeuRx Diaphragm Pacing/Synapse Biomedical" in polished
    assert "Matrix coils" in polished
    assert "Percutaneous intramuscular diaphragm electrodes" in polished
    assert "Revi Tibial Neuromodulation System" in polished
    assert "Freedom PNS System/Curonix" in polished
    assert "mult<sup" not in polished
    assert "Comple<sup" not in polished


def test_polish_html_document_does_not_link_chi_square_exponent() -> None:
    html = (
        "<html><body>"
        "<p>The comparison used (\u03c7<sup>2</sup>) statistics.</p>"
        "<h4>References</h4>"
        "<ul><li>First reference.</li><li>Second reference.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "\u03c7<sup>2</sup>" in polished
    assert 'href="#ref-2"' not in polished[: polished.index("References")]


def test_polish_html_document_preserves_all_caps_table_variables() -> None:
    html = (
        "<html><body>"
        "<table><tr><td>QMAX</td><td>Voltage</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "QMAX" in polished
    assert "QMA<sup" not in polished


def test_polish_html_document_marks_wide_table_layout() -> None:
    cells = "".join(f"<td>c{i}</td>" for i in range(15))
    html = f"<html><body><table><tr>{cells}</tr></table></body></html>"

    polished = polish_html_document(html, table_caption_language="en")

    assert "z2m-wide-table" in polished
    assert "z2m-has-wide-table" in polished


def test_polish_html_document_restores_p_value_significance_star() -> None:
    html = (
        "<html><body>"
        "<table><tr><td>&lt;0.01\ufffd</td></tr></table>"
        "<p>*: statistically significant.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "&lt;0.01*" in polished
    assert "\ufffd" not in polished


def test_polish_html_document_restores_mojibake_significance_and_threshold_markers() -> None:
    html = (
        "<html><body>"
        "<table><tr>"
        "<th>Delta VV (&lt;-150mL vs. пїЅ -150mL)</th>"
        "<th>Delta MFR (&gt;+10mL/s vs. пїЅ +10mL/s)</th>"
        "<td>0.014пїЅ</td>"
        "</tr></table>"
        "<p><sup>пїЅ</sup> : statistically significant</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "0.014*" in polished
    assert "&ge; -150mL" in polished
    assert "&le; +10mL/s" in polished
    assert "пїЅ" not in polished


def test_polish_html_document_drops_journal_page_furniture_and_preserves_sentence() -> None:
    html = (
        "<html><body>"
        "<p>This role may be</p>"
        "<p>Processes 2021, 9, 1726 5 of 31</p>"
        "<p>performed by friends, parents, or teachers.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Processes 2021" not in polished
    assert "This role may be performed by friends" in polished


def test_polish_html_document_strips_dense_pdf_line_numbers_without_units_or_citations() -> None:
    html = (
        "<html><body>"
        "<p>A green 5 approach was developed as a 10 fluorescence probe. "
        "It was then applied 15 for imaging with 20 the sizes below 10 nm. "
        "Methods have been 25 reported and equipment 30 required for green 35 chemistry. "
        "A new carbon 40 source had 45 high coloring effects, cancer, 50 skin irritation, "
        "leuco-methylene 55 blue during MB 60 treatment and simple 65 operation.</p>"
        "<p>Real values remain below 10 nm and at 10 μM. Fig. 5 shows controls. "
        "Electron transfer process. 40 In addition, MB stayed stable. "
        "Hydrothermal cutting strategies 19,20 Nevertheless continued.</p>"
        "<p>Spectroscopy 70 (XPS) of the sample and carbonized at the 75 After point.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "green approach" in polished
    assert "as a fluorescence probe" in polished
    assert "applied for imaging" in polished
    assert "with the sizes below 10 nm" in polished
    assert "been reported" in polished
    assert "equipment required" in polished
    assert "green chemistry" in polished
    assert "carbon source" in polished
    assert "high coloring effects" in polished
    assert "cancer, skin irritation" in polished
    assert "leuco-methylene blue" in polished
    assert "MB treatment" in polished
    assert "simple operation" in polished
    assert "Spectroscopy (XPS) of the sample" in polished
    assert "carbonized at the After point" in polished
    assert "below 10 nm" in polished
    assert "10 μM" in polished
    assert "Fig. 5 shows" in polished
    assert "process. 40 In addition" in polished
    assert "strategies 19,20 Nevertheless" in polished


def test_polish_html_document_does_not_strip_sparse_multiples_as_line_numbers() -> None:
    html = (
        "<html><body>"
        "<p>The culture incubated for 10 min before Figure 5 shows the control. "
        "The detection limit was 50 mM, and Section 20 describes the model.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "10 min" in polished
    assert "Figure 5 shows" in polished
    assert "50 mM" in polished
    assert "Section 20 describes" in polished


def test_polish_html_document_does_not_link_front_matter_glued_author_markers() -> None:
    html = (
        "<html><body>"
        "<p>Andrew P. S. Wheeler1*, Jane Q. Public2, Sam T. Author3</p>"
        "<p>Clinical studies support this claim<sup>1</sup>.</p>"
        "<h4>References</h4>"
        "<ul><li>First reference.</li><li>Second reference.</li><li>Third reference.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    main_start = polished.index('<main id="marker-doc">')
    author_block = polished[main_start : polished.index("Clinical studies")]

    assert "z2m-front-matter" in author_block
    assert 'href="#ref-' not in author_block
    assert "Wheeler<sup>1</sup>*" in author_block
    assert 'href="#ref-1"' in polished[polished.index("Clinical studies") :]


# ---------------------------------------------------------------------------
# Subscript / superscript equation-spill fix
# ---------------------------------------------------------------------------

def test_fix_subscript_equation_spill_moves_frac_outside_subscript() -> None:
    r"""\\gamma_{ij=\\frac{a}{b}} → \\gamma_{ij}=\\frac{a}{b}"""
    latex = r"\gamma_{ij=\frac{2a_ib_j}{a_i^2+b_j^2}}"
    result = _fix_subscript_equation_spill(latex)
    assert result == r"\gamma_{ij}=\frac{2a_ib_j}{a_i^2+b_j^2}"


def test_fix_subscript_equation_spill_handles_nested_braces() -> None:
    r"""Nested fraction braces inside the spill must be preserved."""
    latex = r"\alpha_{n=\frac{x+1}{y-1}}"
    result = _fix_subscript_equation_spill(latex)
    assert result == r"\alpha_{n}=\frac{x+1}{y-1}"


def test_fix_subscript_equation_spill_leaves_normal_subscripts_untouched() -> None:
    r"""\\sum_{i=1}^{n} must not be modified (= is a summation limit, not a spill)."""
    latex = r"\sum_{i=1}^{n} x_i"
    result = _fix_subscript_equation_spill(latex)
    assert result == latex


def test_fix_subscript_equation_spill_handles_superscript() -> None:
    r"""Same fix applies to ^{…=\\frac{…}}."""
    latex = r"\phi^{k=\frac{a}{b}}"
    result = _fix_subscript_equation_spill(latex)
    assert result == r"\phi^{k}=\frac{a}{b}"


def test_fix_subscript_equation_spill_leaves_html_unchanged_when_no_match() -> None:
    html = "<p>Normal text with no LaTeX.</p>"
    assert _fix_subscript_equation_spill(html) == html


def test_polish_html_document_fixes_subscript_equation_spill() -> None:
    r"""End-to-end: spill inside an equation paragraph is repaired."""
    html = (
        "<html><body>"
        r'<p block-type="Equation">\[\gamma_{ij=\frac{2a_ib_j}{a_i^2+b_j^2}}\]</p>'
        "</body></html>"
    )
    polished = polish_html_document(html)
    assert r"\gamma_{ij}=\frac" in polished
    assert r"\gamma_{ij=\frac" not in polished


# ---------------------------------------------------------------------------
# _fix_orphaned_sup_tags
# ---------------------------------------------------------------------------

def test_fix_orphaned_sup_simple() -> None:
    """<sup>. text</sup> with long content is unwrapped."""
    html = "<p>understudied <sup>. However, researchers are applying foundation models to tasks that could improve healthcare quality.</sup> More.</p>"
    result = _fix_orphaned_sup_tags(html)
    assert "<sup>." not in result
    assert "However, researchers" in result
    # The wrapping sup is removed
    assert result.count("<sup>") == 0


def test_fix_orphaned_sup_preserves_inner_citation() -> None:
    """Inner <sup><a>N</a></sup> citation survives unwrapping of broken outer sup."""
    html = (
        '<p>studied <sup>. Researchers apply models '
        '<sup><a href="#ref-5" class="z2m-ref-link">5</a></sup>'
        ' to many tasks.</sup> Next sentence.</p>'
    )
    result = _fix_orphaned_sup_tags(html)
    assert "<sup>." not in result
    # Inner citation sup is preserved
    assert 'href="#ref-5"' in result
    assert "<sup>" in result  # inner citation sup still present
    assert "Researchers apply models" in result


def test_fix_orphaned_sup_leaves_valid_citation_unchanged() -> None:
    """Short <sup> with digit content (real citation) is not touched."""
    html = '<p>pressure<sup><a href="#ref-3">3</a></sup>. Next.</p>'
    result = _fix_orphaned_sup_tags(html)
    assert result == html


def test_fix_orphaned_sup_leaves_short_period_sup_unchanged() -> None:
    """<sup>. X</sup> shorter than 30 chars without nested sup is left alone."""
    html = "<p>text<sup>. ok</sup> more</p>"
    result = _fix_orphaned_sup_tags(html)
    assert result == html


def test_fix_orphaned_sup_multiple_in_document() -> None:
    """Multiple broken sups in one document are all repaired."""
    broken = (
        '<sup>. First broken sentence with enough chars to trigger fix.</sup>'
        '<sup>. Second broken sentence with enough chars to trigger fix.</sup>'
    )
    result = _fix_orphaned_sup_tags(broken)
    assert "<sup>." not in result
    assert "First broken" in result
    assert "Second broken" in result


def test_polish_html_document_unlinks_author_year_footnote_markers() -> None:
    html = (
        "<html><body>"
        "<p>Electrode sites should have low electrochemical impedance"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> for recording, '
        "high charge storage capacity (CSC)"
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> and high CIC'
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a></sup> for stimulation '
        "(Cogan 2008; Larson and Meng 2019; Merrill et al. 2005)"
        '<sup><a href="#ref-5" class="z2m-ref-link">5</a></sup>.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 6))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#ref-2"' not in polished
    assert 'href="#ref-3"' not in polished
    assert 'href="#ref-4"' not in polished
    assert 'href="#ref-5"' not in polished
    assert "impedance<sup>2</sup>" in polished
    assert "(Cogan 2008; Larson and Meng 2019; Merrill et al. 2005)<sup>5</sup>" in polished


def test_polish_html_document_keeps_numeric_citations_in_mixed_author_year_docs() -> None:
    html = (
        "<html><body>"
        "<p>Voiding dysfunction is highly prevalent. UF is a widely used test for bladder emptying."
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> It is carried out on an outpatient basis.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "make this look like an author-year document.</p>"
        "<p>Electrode sites should have low impedance"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> for recording.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 3))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'bladder emptying.<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>' in polished
    assert 'impedance<sup>2</sup> for recording' in polished


def test_polish_html_document_unwraps_author_year_ref_links_with_multiple_authors() -> None:
    html = (
        "<html><body>"
        '<p>Earlier numeric work<sup>2</sup> and later reviews were combined.</p>'
        '<p>These results follow prior studies (<a href="#ref-49" class="z2m-ref-link">'
        'Way and Barner, 1997)</a> and (<a href="#ref-6" class="z2m-ref-link">'
        'B\u00fcchel et al., 1998)</a>.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 51))
        + "</ol></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )
    body = polished[: polished.index("References")]

    assert 'href="#ref-49"' not in body
    assert 'href="#ref-6"' not in body
    assert "(Way and Barner, 1997)" in body
    assert "(B\u00fcchel et al., 1998)" in body
    assert '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> and' in body


def test_polish_html_document_repairs_linked_unit_exponent_false_ref() -> None:
    html = (
        "<html><body>"
        '<p>Charge density reached 100 \u03bcC cm -<a href="#ref-2" class="z2m-ref-link">2</a> '
        'and remained below the limit [<a href="#ref-13" class="z2m-ref-link">13</a>].</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 14))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#ref-2"' not in polished
    assert '\u03bcC cm<sup class="z2m-unit-exp">-2</sup>' in polished
    assert 'href="#ref-13"' in polished


def test_polish_html_document_links_superscript_citations_before_lowercase_continuations() -> None:
    html = (
        "<html><body>"
        "<p>Data generated from a previous study<sup>7,8</sup> was reanalyzed. "
        "Griffiths et al<sup>6</sup> in the form. "
        "Area was 20 cm<sup>2</sup> and remained stable. "
        "Current was 10 A<sup>2</sup> and remained stable.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 9))
        + "</ol></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )
    body = polished[: polished.index("References")]

    assert 'href="#ref-7"' in body
    assert 'href="#ref-8"' in body
    assert 'href="#ref-6"' in body
    assert 'previous study<sup><a href="#ref-7" class="z2m-ref-link">7</a>,<a href="#ref-8"' in body
    assert 'Griffiths et al<sup><a href="#ref-6" class="z2m-ref-link">6</a></sup> in' in body
    assert 'href="#ref-2"' not in body
    assert 'cm<sup class="z2m-unit-exp">2</sup> and' in body
    assert 'A<sup><a href="#ref-2"' not in body


def test_polish_html_document_unlinks_numeric_dimension_and_degree_refs() -> None:
    html = (
        "<html><body>"
        '<p>The <sup><a href="#ref-20" class="z2m-ref-link">20</a></sup> by '
        '100 \u03bcm<sup class="z2m-unit-exp">2</sup> shafts were coated.</p>'
        '<p>The wedges ranged between <sup><a href="#ref-20" class="z2m-ref-link">20</a></sup> '
        "and 45 degrees.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 21))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#ref-20"' not in polished
    assert "The 20 by 100 \u03bcm<sup class=\"z2m-unit-exp\">2</sup> shafts" in polished
    assert "between 20 and 45 degrees" in polished


def test_polish_html_document_normalizes_safe_control_article_artifacts() -> None:
    html = (
        "<html><body>"
        "<p>The current state-ofthe-art method uses Alessentially medical foundation models. "
        "Moreover, Al techniques can improve artiicial intelligence. "
        "The sensor has qualify factor Q, and the worklow stayed stable.</p>"
        "<p>Clinical documentation had ofclinical and essenetial residues.</p>"
        "<p>Fudan Univerisity reported a pathologica example that deceases as the distance grows.</p>"
        "<p>Extra ligature loss had modifcations, fowmeter hardware, "
        "flling pressure, diffi culty voiding, and Specifi cally, the testing identifi es causes.</p>"
        "<p>More lost ligatures had fows, fowrate, flter, cutof, fuid, signifcant, "
        "fowmetry, ndings, fi rst, defi ciency, defi ned, Diffi cult, diffi cult, "
        "outfl ow, urofl owmetry, urofl ow, fl uid, and fl ow.</p>"
        "<p>Split fi/fl words included diffi culties, signifi cantly, signifi cant, "
        "infl uence, Profi le, profi les, profi le, confi dence, Griffi ths, "
        "defi ne, Defi nition, defi nition, fl uoroscopy, fl uoroscopic, "
        "fl uorescent, refl ux, fl oor, Offi ce, offi ce, benefi cial, "
        "and urofl owmeter.</p>"
        "<p>References mentioned eicient tools, eiciency, eectiveness, deining protocols, "
        "uniied inputs, simpliication, ine-grained evaluation, and ailiations.</p>"
        "<p>More ligature losses included signifcantly fewer errors, eficacy trials, "
        "fltering pipelines, scafolds, fbers, fexible flms, fbroin, biofuid, "
        "difusion, feld-efect sensors, fll and flled forms, fowing fluid, "
        "fuoroscopy, fuoroscopic guidance, and fashes of light, "
        "suficiently powered tradeofs, and an oficer in the ofice.</p>"
        "<p>Lost ligatures included frst fne fgurative defned profcient beneft "
        "difculties staf eforts confrmed clarifed infuenced fnger fndings feld. "
        "The patient stimulated \u00aerst and the device saw \u0412\u00aerst order markers.</p>"
        "<p>Joined words included medicineresistant customdesigned hardwareupdate easy-tolearn "
        "Attributebased thistask higherthan disabilitiessometimesface artworksis "
        "hierarchicalsegmentation webbased needsto includesinformation participantssuggested "
        "overallwork guidelinesfor issimilarto easierto spatialcognitive wassupported "
        "blindaccessible timedependent threedimensional twodimensional lowdimensional topdown "
        "contextdependent finergrained featurebased basreliefs "
        "semisupervised locationspecific asprepared asmeasured lung-tohead mattecollodion "
        "explorationSeamless da Vinci1Si allin-one farred Perceptionof "
        "Key-wordaware openaccess BEHAVIORALAND MBVurgency CTABassistant Qmaxnormal "
        "touchinteraction intraand interobserver nearinfrared Shapefrom-shading "
        "patients,were staffmembers theCreative frontto-back ecofriendly nervesparing "
        "upprojection KeunWhangbo first-inhumans Descriptionsfor realworld "
        "Refreshabletactile OFTACTILE residualnormal processingbased handassembled "
        "staffmember selfcontrolled Qmaxurgency d)2.5D prostatectomy\u0394VV "
        "groundtruth backilluminated displaycan EVERYDAYACTIVITIES voicecommands singlefinger "
        "Computeraided MRsafe MRcompatible inIndian Nineteenthcentury airpolluted watersoluble "
        "nonneoadjuvant lightbeam SUFestimated SUFdetermined UFrecorded ofdepression "
        "numbergestures 99Tcmcolloids.</p>"
        "<p>OCR phrases included Hands of!, best suites, all the they identified, "
        "and voiding positing.</p>"
        "<p>More OCR included significate differences, an involunatary contraction, "
        "a uroflometer, upto three tests, pngpng, parametres, simpification, Amercian, "
        "liverposl nomograms, an Examing Committee, urinary track, "
        "inital shape, Bolognia, systometry, bulbocarnosus, Ncology, "
        "and euromodulation devices, Append ix A, MDP i, B rain-computer interfaces, Ita ly, "
        "APPEND ix B, Hindaw i, fMR i, I mplantable systems, will to help reveal, "
        "Sem i -structured interviews, Tree-dimensional Analysis Sofware, Beha v. Neurosci., "
        "Mata-Analysis, documents that that intensity, Retinal Nerve Fiber Laver, "
        "Bel humeur, Leporin i, t o the best of our knowledge, ob je ct s w ould, "
        "safe ty c oncerns, enj oy, basrelief, populationbased cohorts, "
        "signalto-noise ratios, and advanta- \u00a8 geous settings.</p>"
        "<p>Spatial printing OCR included incl ude, b e interpreted, A dd itional "
        "expressi ve ness, T his fact, specifi c behavior, CNC-millin g m achines, supp ort structures, "
        "a dditive production, alternati ves, pr inting services, technical ly, "
        "high ) w ere, thr ee different, straightfo rw ard, Gener al digital, "
        "Barc elona, coefcient values, and supple mental notes.</p>"
        "<p>The 1.5 T magnetic eld and urine ow rate remained stable.</p>"
        "<p>The laser components include The Cartesian linear stage provides 2 DOF motion.</p>"
        "<code>frst medicineresistant</code>"
        "<p>Reprints andpermissions information governs archiving ofthe accepted manuscript.</p>"
        "<p>P. A. Heppner, \u00b4 and D. M. Budgett reported the device. "
        "L. Syd \u00a8 anheimo described a wireless \u00a8 intraocular pressure sensor.</p>"
        "<p>Contact e-mail: iskandar@ neurosurgery.wisc.edu.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "state-of-the-art" in polished
    assert "AI essentially medical foundation models" in polished
    assert "AI techniques" in polished
    assert "artificial intelligence" in polished
    assert "quality factor Q" in polished
    assert "workflow stayed stable" in polished
    assert "of clinical" in polished
    assert "essential residues" in polished
    assert "Fudan University" in polished
    assert "pathological example" in polished
    assert "decreases as the distance" in polished
    assert "Extra ligature loss had modifications, flowmeter hardware" in polished
    assert "filling pressure, difficulty voiding" in polished
    assert "Specifically, the testing identifies causes" in polished
    assert "More lost ligatures had flows, flow rate, filter, cutoff, fluid, significant" in polished
    assert "flowmetry, findings, first, deficiency, defined, Difficult, difficult" in polished
    assert "outflow, uroflowmetry, uroflow, fluid, and flow" in polished
    assert "included difficulties, significantly, significant, influence, Profile" in polished
    assert "profiles, profile, confidence, Griffiths, define, Definition, definition" in polished
    assert "fluoroscopy, fluoroscopic, fluorescent, reflux, floor, Office, office, beneficial" in polished
    assert "and uroflowmeter" in polished
    assert "efficient tools" in polished
    assert "efficiency" in polished
    assert "effectiveness" in polished
    assert "defining protocols" in polished
    assert "unified inputs" in polished
    assert "simplification" in polished
    assert "fine-grained evaluation" in polished
    assert "affiliations" in polished
    assert "significantly fewer errors, efficacy trials, filtering pipelines" in polished
    assert "scaffolds, fibers, flexible films, fibroin, biofluid" in polished
    assert "diffusion, field-effect sensors, fill and filled forms, flowing fluid" in polished
    assert "fluoroscopy, fluoroscopic guidance, and flashes of light" in polished
    assert "sufficiently powered tradeoffs" in polished
    assert "an officer in the office" in polished
    assert "first fine figurative defined proficient benefit" in polished
    assert "influenced finger findings field" in polished
    assert "difficulties staff efforts confirmed clarified influenced finger findings field" in polished
    assert "stimulated first and the device saw first order markers" in polished
    assert "medicine-resistant custom-designed hardware update easy-to-learn" in polished
    assert "Attribute-based this task higher than disabilities sometimes face artworks is" in polished
    assert "hierarchical segmentation web-based needs to includes information participants suggested" in polished
    assert "overall work guidelines for is similar to easier to spatial-cognitive was supported" in polished
    assert "blind-accessible time-dependent three-dimensional two-dimensional low-dimensional top-down" in polished
    assert "context-dependent finer-grained feature-based" in polished
    assert "bas-reliefs semi-supervised location-specific as-prepared as measured" in polished
    assert "lung-to-head matte-collodion exploration. Seamless da Vinci Si all-in-one far-red" in polished
    assert "Perception of Keyword-aware open-access BEHAVIORAL AND MBV-urgency CTAB-assisted" in polished
    assert "Qmax-normal touch interaction intra- and interobserver near-infrared Shape-from-shading" in polished
    assert "patients were staff members the Creative front-to-back eco-friendly nerve-sparing" in polished
    assert "up-projection Keun Whangbo first-in-humans Descriptions for real-world" in polished
    assert "Refreshable tactile OF TACTILE residual-normal processing-based hand-assembled" in polished
    assert "staff member self-controlled Qmax-urgency d) 2.5D" in polished
    assert "prostatectomy \u0394VV ground-truth back-illuminated display can EVERYDAY ACTIVITIES" in polished
    assert "voice commands single-finger Computer-aided MR-safe MR-compatible in Indian" in polished
    assert "Nineteenth-century air-polluted water-soluble non-neoadjuvant light-beam" in polished
    assert "SUF-estimated SUF-determined UF-recorded" in polished
    assert "of depression number gestures 99Tcm colloids" in polished
    assert "Hands off!, best suits, all that they identified, and voiding position" in polished
    assert "significant differences, an involuntary contraction, a uroflowmeter" in polished
    assert "up to three tests, png, parameters, simplification, American" in polished
    assert "Liverpool nomograms, an Examining Committee, urinary tract, initial shape" in polished
    assert "Bologna, cystometry, bulbocavernosus, Oncology, and neuromodulation devices" in polished
    assert "Appendix A, MDPI, Brain-computer interfaces, Italy" in polished
    assert "APPENDIX B, Hindawi, fMRI, Implantable systems, will help reveal" in polished
    assert "Semi-structured interviews, Three-dimensional Analysis Software, Behav. Neurosci." in polished
    assert "Meta-Analysis, documents that the intensity, Retinal Nerve Fiber Layer" in polished
    assert "Belhumeur, Leporini, to the best of our knowledge, objects would" in polished
    assert "safety concerns, enjoy, bas-relief, population-based cohorts, signal-to-noise ratios" in polished
    assert "and advantageous settings" in polished
    assert "included include, be interpreted, Additional expressiveness, This fact, specific behavior" in polished
    assert "CNC-milling machines, support structures, additive production, alternatives" in polished
    assert "printing services, technically, high) were, three different, straightforward" in polished
    assert "General digital, Barcelona, coefficient values, and supplemental notes" in polished
    assert "The 1.5 T magnetic field and urine flow rate remained stable" in polished
    assert "The Cartesian linear stage provides 2 DOF motion" in polished
    assert "The laser components include The Cartesian" not in polished
    assert "<code>frst medicineresistant</code>" in polished
    assert "Reprints and permissions information" in polished
    assert "of the accepted manuscript" in polished
    assert "Heppner, and D. M. Budgett" in polished
    assert "Syd\u00e4nheimo" in polished
    assert "wireless intraocular" in polished
    assert "iskandar@neurosurgery.wisc.edu" in polished


def test_polish_html_document_repairs_english_ocr_artifacts_across_inline_markup() -> None:
    html = (
        "<html><body>"
        '<p>The surface <a href="#ref-1" class="z2m-ref-link">[Bel</a> humeur et al. 1999] '
        "stayed visible.</p>"
        '<p>While touching the original ob <a href="#page-7-0">je</a> '
        '<a href="#page-7-1">ct</a> <a href="#ref-1" class="z2m-ref-link">s w</a>ould '
        'be best, safe <a href="#ref-1" class="z2m-ref-link">ty c</a>oncerns remain.</p>'
        '<p>People enj <a href="#page-9-0">oy a</a> painting.</p>'
        "<p><b>B</b> rain-computer interfaces were reported in Roma, Ita <b>ly</b>.</p>"
        '<p>We specifically incl <a href="#page-7-4">ude</a>, which has to '
        '<a href="#page-7-5">b</a> e interpreted. A <a href="#page-7-6">dd</a> itional '
        'expressi <a href="#page-7-5">ve</a> ness follows. T <a href="#ref-1">his</a> '
        'fact uses CNC-millin <a href="#ref-1">g m</a> achines, supp '
        '<a href="www.agisoft.ru">ort structures in a</a> dditive production, alternati '
        '<a href="#page-7-9">ves</a>, <a href="#page-3-0">pr</a> inting services, '
        'technical <a href="#page-7-5">ly</a>, high <a href="#page-5-0">)</a> '
        '<a href="#page-5-0">w</a> ere, thr <a href="#page-2-0">ee</a> different, '
        'straightfo <a href="#page-5-0">rw</a> ard, Gener <a href="#page-7-13">al</a> '
        'digital, and <a href="http://www.tactileview.com/">Barc</a> elona.</p>'
        '<table><tr><td>Leporin<sup class="z2m-table-fn">i</sup> et al.; '
        'Ghian<sup class="z2m-table-fn">i</sup>, Leporini &amp; Paterno.</td></tr></table>'
        '<code>ob <a href="#page-7-0">je</a> ct s w ould</code>'
        '<a href="https://example.test/B%20rain-computer">B rain-computer</a>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<a href="#ref-1" class="z2m-ref-link">[Belhumeur</a> et al. 1999]' in polished
    assert "original objects would be best, safety concerns remain" in polished
    assert "People enjoy a painting" in polished
    assert "Brain-computer interfaces were reported in Roma, Italy" in polished
    assert "specifically include, which has to be interpreted" in polished
    assert "Additional expressiveness follows. This fact uses CNC-milling machines" in polished
    assert "support structures in additive production, alternatives, printing services" in polished
    assert "technically, high) were, three different, straightforward" in polished
    assert "General digital, and Barcelona" in polished
    assert "Leporini et al.; Ghiani, Leporini &amp; Paterno" in polished
    assert "<code>ob je ct s w ould</code>" in polished
    assert '<a href="https://example.test/B%20rain-computer">B rain-computer</a>' in polished


def test_polish_html_document_repairs_joined_word_residuals_from_audit() -> None:
    html = (
        "<html><body>"
        "<p>videobased and textbased content used leftright and pushpull cues. "
        "The feed-andsleep technique measured symptomscore changes in urineflow traces.</p>"
        "<p>FromFebruary the darkbrown sample had BPHassociated markers, "
        "domaininvariant features, vitamin-Ddeficient status, and Qcould improve.</p>"
        "<p>OpticalTouch, vanderVorst, Al Omari1, and texture.Tactile remain visible.</p>"
        "<p>readyreckoners appeared withlower urinary tract symptoms, while Positionrelated "
        "effects used twoobject, shiftinvariant, IPPgrades, and Qto verify operation.</p>"
        "<p>The port extrusionsurgically treated group was recorded.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "video-based and text-based content used left-right and push-pull cues" in polished
    assert "feed-and-sleep technique measured symptom score changes in urine flow traces" in polished
    assert "From February the dark brown sample had BPH-associated markers" in polished
    assert "domain-invariant features, vitamin-D-deficient status, and Q could improve" in polished
    assert "Optical Touch, van der Vorst, Al Omari 1, and texture. Tactile" in polished
    assert "ready reckoners appeared with lower urinary tract symptoms" in polished
    assert "Position-related effects used two-object, shift-invariant, IPP grades, and Q to verify" in polished
    assert "port extrusion surgically treated group" in polished


def test_polish_html_document_repairs_known_ocr_suffixes_across_inline_markup() -> None:
    html = (
        "<html><body>"
        '<p>See Append<sup class="z2m-table-fn">ix</sup> 1 and '
        'APPEND<sup class="z2m-table-fn">ix</sup> B.</p>'
        '<p>Sources include MDP<sup class="z2m-table-fn">i</sup>, '
        'Hindaw<a href="#page-3-0">i</a>, and fMR<span>i</span> scans.</p>'
        '<p>Sem<sup class="z2m-table-fn">i</sup>-structured interviews used '
        "Three-dimensioanl images.</p>"
        '<p>Keep stimul<sup class="z2m-table-fn">i</sup> untouched.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Appendix 1 and APPENDIX B" in polished
    assert "Sources include MDPI, Hindawi, and fMRI scans" in polished
    assert "Semi-structured interviews used Three-dimensional images" in polished
    assert 'stimul<sup class="z2m-table-fn">i</sup> untouched' in polished


def test_polish_html_document_repairs_ocr_tokens_from_global_p71_audit() -> None:
    html = (
        "<html><body>"
        "<p>Thirtyeight subjects used bootloding software for watershed Segmentaion.</p>"
        "<p>The sys- tem used a crania l implant appro ximately twice per trial.</p>"
        "<p>F igures showed TQma x and PdetQma x with a passive senor.</p>"
        "<p>The Deptartment reported PRAVALENCE in a discription in J Neurocsi.</p>"
        "<p>Schfer et al. discussed aesthesia protocols.</p>"
        "<p>The result was to be The topological sort and simulates the The validation.</p>"
        "<p>Leave IRIT-ELIPSE unchanged.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Thirty-eight subjects used bootloading software for watershed Segmentation" in polished
    assert "The system used a cranial implant approximately twice per trial" in polished
    assert "Figures showed TQmax and PdetQmax with a passive sensor" in polished
    assert "The Department reported PREVALENCE in a description in J Neurosci" in polished
    assert "Sch\u00e4fer et al. discussed anesthesia protocols" in polished
    assert "to be the topological sort and simulates the validation" in polished
    assert "IRIT-ELIPSE" in polished


def test_polish_html_document_repairs_mojibake_detached_latin_accents_in_text_nodes() -> None:
    html = (
        "<html><body>"
        "<p>The relief climbs the fac\u0412\u0451ade. "
        "O\u0412\u0491Donnell wrote a consumer\u0412\u0491s guide. "
        "Pogoreli\u0412\u0491c, Huski\u0412\u0491c, Cohad\u0415\u0455i\u0412\u0491c, "
        "Juki\u0412\u0491c, Ma\u0412\u0491ckowski, Neum\u0412\u0401uller, "
        "Sch\u0412\u0401afer, Bezi\u0412\u0491er, Niccol\u0412\u0491o, "
        "Karolina Pakenait \u041b\u2122 e\u041b\u2122, BRICENO\u041b\u045a, "
        "Sabine Susstrunk \u0412\u0401 School, fa\u0412\u0451cades, Bros- \u0412\u0491 tow, "
        "Wabi \u0412\u0491nski, Mo\u0412\u0491scicka, moir\u0412\u0491e-like, "
        "HOLLERER \u0412\u0401 , would \u0412\u0491 be, many \u0412\u0401 insightful, "
        "Microsoft \u0412\u0491 coco, Peter M \u041b\u2122 Hall, and "
        "S. OA\u041b\u2020 \u041b\u2021SModhrain were present. "
        "SEQUIN \u0412\u0491 , C., Konrad \u0412\u0491 Schindler, and "
        "Adarsh \u0412\u0401 Kowdle, Radim \u041b\u2021 S\u041b\u2021 ara, "
        "templates \u0412\u0491 for objects, and C. BAijhler, \u041b\u045a and P. Penaz were cited. "
        "Kristja\u00b4nsson A\u00b4, Jo\u00b4hannesson O\u00b4 I, Sa\u00b4nchez, "
        "Ka\u00b4rma\u00b4n, Ismae\u00a8l, Muhovi\u02c7c, and University \u00a8 of Kent appeared. "
        "Cuevas-Rodr\u0412\u0491\u0414\u00b1guez, Garc\u0414\u00b1\u0412\u0491a-Betances, "
        "Uberla\u041b\u2020ndia, and na\u0412\u0401\u0414\u00b1ve readers were listed. "
        "The text had qualitative colour \u0412\u0491 palettes and present \u0412\u0401 <i> active </i> modes.</p>"
        '<p><a href="https://orcid.org/0000-0001-8665-1362">Karolina Pakenait</a> '
        "\u041b\u2122 e\u041b\u2122 University of Bath.</p>"
        '<p data-name="fac\u0412\u0451ade">The visible name is Neum\u0412\u0401uller.</p>'
        "<code>fac\u0412\u0451ade O\u0412\u0491Donnell</code>"
        "<pre>Sch\u0412\u0401afer</pre>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "fa\u00e7ade" in polished
    assert "O'Donnell" in polished
    assert "consumer's guide" in polished
    assert "Pogoreli\u0107, Huski\u0107, Cohad\u017ei\u0107, Juki\u0107" in polished
    assert "Ma\u0107kowski" in polished
    assert "Neum\u00fcller" in polished
    assert "Sch\u00e4fer" in polished
    assert "B\u00e9zier" in polished
    assert "Niccol\u00f3" in polished
    assert "Pakenait\u0117" in polished
    assert "BRICE\u00d1O" in polished
    assert "S\u00fcsstrunk School" in polished
    assert "fa\u00e7ades" in polished
    assert "Brostow" in polished
    assert "Wabi\u0144ski" in polished
    assert "Mo\u015bcicka" in polished
    assert "moir\u00e9-like" in polished
    assert "HOLLERER, would be, many insightful" in polished
    assert "Microsoft COCO" in polished
    assert "Peter M. Hall" in polished
    assert "S. O'Modhrain" in polished
    assert "SEQUIN, C." in polished
    assert "Konrad Schindler" in polished
    assert "Adarsh Kowdle" in polished
    assert "Radim \u0160\u00e1ra" in polished
    assert "templates for objects" in polished
    assert "C. B\u00fchler, and P. Penaz" in polished
    assert "Kristj\u00e1nsson \u00c1, J\u00f3hannesson \u00d3 I, S\u00e1nchez" in polished
    assert "K\u00e1rm\u00e1n, Isma\u00ebl, Muhovi\u010d, and University of Kent" in polished
    assert "Cuevas-Rodr\u00edguez, Garc\u00eda-Betances, Uberl\u00e2ndia, and na\u00efve readers" in polished
    assert "qualitative colour palettes and present <i> active </i> modes" in polished
    assert 'href="https://orcid.org/0000-0001-8665-1362">Karolina Pakenait\u0117</a>' in polished
    assert 'data-name="fac\u0412\u0451ade"' in polished
    assert "<code>fac\u0412\u0451ade O\u0412\u0491Donnell</code>" in polished
    assert "<pre>Sch\u0412\u0401afer</pre>" in polished


def test_polish_html_document_keeps_english_ocr_repairs_en_only() -> None:
    html = (
        "<html><body>"
        "<p>Lost ligatures included frst and fne. "
        "Joined words included medicineresistant, Attributebased, realworld, "
        "groundtruth, and displaycan. Typos included systometry and Ncology.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="ru", polish_language="ru")

    assert "frst and fne" in polished
    assert "medicineresistant, Attributebased, realworld, groundtruth, and displaycan" in polished
    assert "systometry and Ncology" in polished


def test_polish_html_document_repairs_publication_metadata_author_marker_block() -> None:
    html = (
        "<html><body>"
        "<h1>Generative artificial intelligence in medicine</h1>"
        "<p>Received: 2 April 2025 Accepted: 27 August 2025 Published online: 06 October 2025 "
        "Check for updates Zhen Ling Teo \u0412\u00a9 1,2,15, "
        "Arun James Thirunavukarasu \u0412\u00a9 3,15, Kabilan Elangovan 1 , 2 , "
        "Haoran Cheng 1 , 4 , Prasanth Mooya 1 , 2 &amp; Daniel Shu Wei Ting 1.2.5</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Check for updates" not in polished
    assert "z2m-front-matter" in polished
    assert "Zhen Ling Teo<sup>1,2,15</sup>" in polished
    assert "Arun James Thirunavukarasu<sup>3,15</sup>" in polished
    assert "Daniel Shu Wei Ting<sup>1,2,5</sup>" in polished
    assert "Zhen Ling Teo \u0412\u00a9 1" not in polished


def test_to_data_url_detects_jpeg_by_signature() -> None:
    """JPEG files should be detected by signature, not just extension."""
    import tempfile

    # Create a JPEG-like file with wrong extension
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        # Write JPEG magic bytes: FF D8 FF
        f.write(b"\xff\xd8\xff" + b"\x00" * 100)
        temp_path = Path(f.name)

    try:
        result = _to_data_url(temp_path, detect_by_signature=True)
        assert result is not None
        assert "data:image/jpeg;base64," in result
    finally:
        temp_path.unlink()


def test_validate_data_url() -> None:
    """Data URLs should be validated against original files."""
    import tempfile

    # Create a test file with known content
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"test content for validation")
        temp_path = Path(f.name)

    try:
        data_url = _to_data_url(temp_path)
        assert data_url is not None
        assert _validate_data_url(data_url, temp_path) is True

        # Corrupt the URL by changing base64 data
        bad_url = data_url.replace("dGVzdCBjb250ZW50", "Y29ycnVwdGVk")
        assert _validate_data_url(bad_url, temp_path) is False
    finally:
        temp_path.unlink()
