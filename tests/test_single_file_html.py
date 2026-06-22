import base64
import re
import shutil
from pathlib import Path
from uuid import uuid4

from pdf_html_polish import html_images, html_links, text_cleanup
from pdf_html_polish.raw_html_polish import html_fragments, pre_cleanup
from pdf_html_polish.raw_html_polish import frontmatter_footnotes
from pdf_html_polish.single_file_html import (
    _AUX_PROTOCOL_SENTINEL_LEAK_PATTERN,
    _AUTHOR_BYLINE_NAME_RE,
    _BACKSLASH_BEFORE_QUOTE_PATTERN,
    _ESCAPED_INLINE_TAG_PATTERN,
    _HEADING_PROTOCOL_SENTINEL_LEAK_PATTERN,
    _IMAGE_CACHE_KEY_ATTR_PATTERN,
    _IMG_SRC_PATTERN,
    _INLINE_OR_DISPLAY_TEX_PATTERN,
    _LEADING_SPACED_BACKSLASH_PATTERN,
    _NESTED_FIG_LINK_PATTERN,
    _NESTED_SAME_HREF_INTERNAL_LINK_PATTERN,
    _PAGE_HEADER_FOOTER_LINE_PATTERN,
    _REPEATED_PHRASE_PATTERN,
    _RU_BARE_FIG_LEXEME_PATTERN,
    _SKIP_AUTOLINK_TAGS,
    _SLASH_PIPE_ARTIFACT_PATTERN,
    _SPACED_ESCAPED_INLINE_TAG_PATTERN,
    _SPACED_INLINE_TAG_PATTERN,
    _SPLIT_ESCAPED_INLINE_OPEN_TAG_PATTERN,
    _TEXT_NODE_REPAIR_SKIP_TAGS,
    _TRAILING_SPACED_BACKSLASH_PATTERN,
    _add_figure_anchors,
    _add_section_anchors,
    _cleanup_marker_escape_artifacts,
    _figure_caption_num_from_visible,
    _fix_common_mojibake,
    _fix_orphaned_sup_tags,
    _fix_false_sup_citations_in_decimals_and_figure_labels,
    _fix_subscript_equation_spill,
    _footnote_keywords,
    _leading_footnote_number,
    _looks_affiliation_block,
    _looks_affiliation_label_body,
    _looks_author_byline_front_matter,
    _looks_author_marker_ocr_candidate,
    _looks_footnote_block,
    _looks_front_matter_block,
    _mark_affiliation_paragraphs,
    _mark_front_matter_paragraphs,
    _mark_footnote_paragraphs_and_refs,
    _inline_images_from_html_text,
    _link_figure_refs,
    _link_unlinked_numeric_superscripts_to_existing_refs,
    _link_section_refs,
    _late_recover_orphan_figure_anchors_and_links,
    _normalize_spaced_inline_sup_sub_tags,
    _refresh_inlined_data_urls_by_cache,
    _refresh_inlined_data_urls_by_hint,
    _repair_figure_ref_links_misclassified_as_refs,
    _repair_confirmed_front_matter_artifacts,
    _repair_confirmed_front_matter_email_artifacts_body,
    _repair_front_matter_marker_ocr,
    _repair_front_matter_page_anchor_markers,
    _repair_known_word_glue,
    _repair_latin_detached_accent_artifacts_in_visible_text,
    _repair_page_footnote_ref_links,
    _repair_sevick_muraca_author_marker,
    _repair_sentence_breaks_around_float_units,
    _repair_sup_figure_chain_continuations,
    _repair_turkish_urology_byline,
    _repair_xue_byline_abstract_split,
    _recover_unique_bare_source_named_figure_units,
    _restore_shielded_data_image_srcs,
    _shield_renderable_data_image_srcs,
    _split_zhu_affiliation_tail,
    _split_url_footnote_prose_tails,
    _split_table_units_before_section_headings,
    _to_data_url,
    _unescape_inline_sup_sub,
    _unwrap_nested_fig_links,
    _unwrap_nested_same_href_internal_links,
    _strip_protocol_sentinel_leaks,
    _unicode_capitalized_name_pair_count,
    _unicode_glued_author_marker_count,
    _update_skip_stack,
    _validate_data_url,
    close_katex_v8_context,
    drop_repeated_phrases,
    inline_images_only_from_html_file,
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


def test_single_file_html_preserves_extracted_helper_aliases() -> None:
    assert _IMG_SRC_PATTERN is html_images.IMG_SRC_PATTERN
    assert _IMAGE_CACHE_KEY_ATTR_PATTERN is html_images.IMAGE_CACHE_KEY_ATTR_PATTERN
    assert _inline_images_from_html_text is html_images.inline_images_from_html_text
    assert _refresh_inlined_data_urls_by_hint is html_images.refresh_inlined_data_urls_by_hint
    assert _refresh_inlined_data_urls_by_cache is html_images.refresh_inlined_data_urls_by_cache
    assert _NESTED_FIG_LINK_PATTERN is html_links.NESTED_FIG_LINK_PATTERN
    assert _NESTED_SAME_HREF_INTERNAL_LINK_PATTERN is html_links.NESTED_SAME_HREF_INTERNAL_LINK_PATTERN
    assert _unwrap_nested_fig_links is html_links.unwrap_nested_fig_links
    assert _unwrap_nested_same_href_internal_links is html_links.unwrap_nested_same_href_internal_links
    assert _REPEATED_PHRASE_PATTERN is text_cleanup.REPEATED_PHRASE_PATTERN
    assert drop_repeated_phrases is text_cleanup.drop_repeated_phrases
    assert _ESCAPED_INLINE_TAG_PATTERN is html_fragments.ESCAPED_INLINE_TAG_PATTERN
    assert _SPACED_ESCAPED_INLINE_TAG_PATTERN is html_fragments.SPACED_ESCAPED_INLINE_TAG_PATTERN
    assert _SPLIT_ESCAPED_INLINE_OPEN_TAG_PATTERN is html_fragments.SPLIT_ESCAPED_INLINE_OPEN_TAG_PATTERN
    assert _SPACED_INLINE_TAG_PATTERN is html_fragments.SPACED_INLINE_TAG_PATTERN
    assert _unescape_inline_sup_sub is html_fragments.unescape_inline_sup_sub
    assert _normalize_spaced_inline_sup_sub_tags is html_fragments.normalize_spaced_inline_sup_sub_tags
    assert _SKIP_AUTOLINK_TAGS is pre_cleanup.SKIP_AUTOLINK_TAGS
    assert _TEXT_NODE_REPAIR_SKIP_TAGS is pre_cleanup.TEXT_NODE_REPAIR_SKIP_TAGS
    assert _SLASH_PIPE_ARTIFACT_PATTERN is pre_cleanup.SLASH_PIPE_ARTIFACT_PATTERN
    assert _LEADING_SPACED_BACKSLASH_PATTERN is pre_cleanup.LEADING_SPACED_BACKSLASH_PATTERN
    assert _TRAILING_SPACED_BACKSLASH_PATTERN is pre_cleanup.TRAILING_SPACED_BACKSLASH_PATTERN
    assert _BACKSLASH_BEFORE_QUOTE_PATTERN is pre_cleanup.BACKSLASH_BEFORE_QUOTE_PATTERN
    assert _INLINE_OR_DISPLAY_TEX_PATTERN is pre_cleanup.INLINE_OR_DISPLAY_TEX_PATTERN
    assert _RU_BARE_FIG_LEXEME_PATTERN is pre_cleanup.RU_BARE_FIG_LEXEME_PATTERN
    assert _HEADING_PROTOCOL_SENTINEL_LEAK_PATTERN is pre_cleanup.HEADING_PROTOCOL_SENTINEL_LEAK_PATTERN
    assert _AUX_PROTOCOL_SENTINEL_LEAK_PATTERN is pre_cleanup.AUX_PROTOCOL_SENTINEL_LEAK_PATTERN
    assert _fix_common_mojibake is pre_cleanup.fix_common_mojibake
    assert _cleanup_marker_escape_artifacts is pre_cleanup.cleanup_marker_escape_artifacts
    assert _strip_protocol_sentinel_leaks is pre_cleanup.strip_protocol_sentinel_leaks
    assert _update_skip_stack is pre_cleanup.update_skip_stack
    assert _AUTHOR_BYLINE_NAME_RE is frontmatter_footnotes.AUTHOR_BYLINE_NAME_PATTERN
    assert _PAGE_HEADER_FOOTER_LINE_PATTERN is frontmatter_footnotes.PAGE_HEADER_FOOTER_LINE_PATTERN
    assert _unicode_capitalized_name_pair_count is frontmatter_footnotes.unicode_capitalized_name_pair_count
    assert _unicode_glued_author_marker_count is frontmatter_footnotes.unicode_glued_author_marker_count
    assert _looks_affiliation_block is frontmatter_footnotes.looks_affiliation_block
    assert _looks_affiliation_label_body is frontmatter_footnotes.looks_affiliation_label_body
    assert _looks_author_byline_front_matter is frontmatter_footnotes.looks_author_byline_front_matter
    assert _looks_author_marker_ocr_candidate is frontmatter_footnotes.looks_author_marker_ocr_candidate
    assert _leading_footnote_number is frontmatter_footnotes.leading_footnote_number
    assert _footnote_keywords is frontmatter_footnotes.footnote_keywords
    assert _repair_confirmed_front_matter_artifacts is frontmatter_footnotes.repair_confirmed_front_matter_artifacts
    assert _repair_confirmed_front_matter_email_artifacts_body is frontmatter_footnotes.repair_confirmed_front_matter_email_artifacts_body
    assert _repair_turkish_urology_byline is frontmatter_footnotes.repair_turkish_urology_byline
    assert _repair_xue_byline_abstract_split is frontmatter_footnotes.repair_xue_byline_abstract_split
    assert _repair_sevick_muraca_author_marker is frontmatter_footnotes.repair_sevick_muraca_author_marker
    assert _split_zhu_affiliation_tail is frontmatter_footnotes.split_zhu_affiliation_tail
    assert _mark_affiliation_paragraphs is frontmatter_footnotes.mark_affiliation_paragraphs
    assert _repair_page_footnote_ref_links is frontmatter_footnotes.repair_page_footnote_ref_links
    assert _split_url_footnote_prose_tails is frontmatter_footnotes.split_url_footnote_prose_tails


def test_single_file_front_matter_marker_ocr_wrapper() -> None:
    html = '<p class="z2m-front-matter">Alice Smith1, Bob Jones2, Carol Roe3</p>'

    repaired = _repair_front_matter_marker_ocr(html)

    assert "Alice Smith<sup>1</sup>, Bob Jones<sup>2</sup>, Carol Roe<sup>3</sup>" in repaired


def test_single_file_mark_front_matter_paragraphs_wrapper() -> None:
    html = "<p>Keywords: mobility</p><p>Introduction starts here.</p>"

    marked = _mark_front_matter_paragraphs(html)

    assert '<p class="z2m-front-matter">Keywords: mobility</p>' in marked
    assert "<p>Introduction starts here.</p>" in marked


def test_single_file_looks_front_matter_block_wrapper() -> None:
    assert _looks_front_matter_block("<p>Keywords: mobility</p>")
    assert not _looks_front_matter_block("<p>Introduction starts here.</p>")


def test_single_file_footnote_block_wrapper_uses_float_caption_guards() -> None:
    raw = "<p><sup>1</sup> Tensile strength is determined by materials testing methods for polymers.</p>"

    assert _looks_footnote_block(raw)


def test_single_file_mark_footnote_wrapper_marks_matching_ref() -> None:
    html = (
        "<p>Low tensile strength<sup>1</sup> remains important.</p>"
        "<p><sup>1</sup> Tensile strength is determined by materials testing methods.</p>"
    )

    marked = _mark_footnote_paragraphs_and_refs(html)

    assert 'id="footnote-1"' in marked
    assert 'strength<sup class="z2m-footnote-ref">1</sup>' in marked


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


def test_single_file_front_matter_page_anchor_marker_wrapper() -> None:
    body = 'Alic<a href="#page-1">e1,2</a>, <a href="#page-1">3</a>'

    assert _repair_front_matter_page_anchor_markers(body) == (
        "Alice<sup>1,2</sup>, <sup>3</sup>"
    )


def test_confirmed_front_matter_email_artifacts_body_helper() -> None:
    body = (
        "Department of Industrial Engineering, University of Florence, Italy. "
        "Contacts: lapo.governi@unfi.it. "
        "For correspondence Me-mail: michael.deistler@uni-tuebingen.de"
    )

    repaired = _repair_confirmed_front_matter_email_artifacts_body(body)

    assert "Me-mail:" not in repaired
    assert "e-mail: michael.deistler@uni-tuebingen.de" in repaired
    assert "lapo.governi@unifi.it" in repaired


def test_repair_turkish_urology_byline_helper_handles_marker_run() -> None:
    body = (
        "Mehmet Zeynel Keskin, Erkin Karaca, Murat U\u00e7ar, "
        "Erhan Ate\u015f, Cem Y\u00fccel, and Yusuf \u00d6zlem \u0130lbey "
        "1 1 2 3 1 1"
    )

    repaired = _repair_turkish_urology_byline(body)

    assert "Mehmet Zeynel Keskin<sup>1</sup>" in repaired
    assert "Murat U\u00e7ar<sup>2</sup>" in repaired
    assert "Yusuf \u00d6zlem \u0130lbey<sup>1</sup>" in repaired


def test_confirmed_front_matter_split_helpers_render_blocks() -> None:
    xue = _repair_xue_byline_abstract_split(
        "<p>",
        "</p>",
        "Mingyue Xue, ab Mengbing Zou, Jingjin Zhao, Zhihua Zhan Ab and "
        "Shulin Zhao Zhao A green approach was developed for detection.",
    )

    assert xue is not None
    assert '<p class="z2m-front-matter">Mingyue Xue<sup>ab</sup>' in xue
    assert "<p>A green approach was developed for detection.</p>" in xue

    body = _repair_sevick_muraca_author_marker(
        "Banghe Zhu, John C. Rasmussen, and Eva M. Sevick-Murac aa) "
        "Center for Molecular Imaging, The Brown Foundation Institute."
    )
    zhu = _split_zhu_affiliation_tail("<p>", "</p>", body)

    assert zhu is not None
    assert "Eva M. Sevick-Muraca<sup>a)</sup>" in zhu
    assert 'class="z2m-front-matter z2m-affiliations"' in zhu


def test_inline_images_only_from_html_file_does_not_apply_marker_polish() -> None:
    tmp_path = _make_temp_dir()
    try:
        html_path = tmp_path / "doc.html"
        image_path = tmp_path / "img.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        html_path.write_text('<html><body><img src="img.png"></body></html>', encoding="utf-8")

        result = inline_images_only_from_html_file(html_path)

        assert result.inlined_images == 1
        assert "data:image/png;base64," in result.html
        assert 'data-z2m-style="readable"' not in result.html
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


def test_data_image_src_shield_round_trips_large_renderable_payload() -> None:
    large_gif = base64.b64encode(b"GIF89a" + (b"A" * 250_000) + b";").decode("ascii")
    data_url = f"data:image/gif;base64,{large_gif}"
    html = f'<html><body><p><img src="{data_url}"/></p><p>Text with 2 m^-1.</p></body></html>'

    shielded, image_srcs = _shield_renderable_data_image_srcs(html)

    assert data_url not in shielded
    assert "data-z2m-data-image-src-shield" in shielded
    assert _VALID_TINY_PNG_B64 in shielded
    assert _restore_shielded_data_image_srcs(shielded, image_srcs) == html


def test_data_image_src_shield_keeps_broken_payload_visible_to_polish() -> None:
    broken = base64.b64encode(b"\x89PNG\r\n\x1a\ntruncated").decode("ascii").rstrip("=")
    html = f'<html><body><img src="data:image/png;base64,{broken}"/></body></html>'

    shielded, image_srcs = _shield_renderable_data_image_srcs(html)

    assert shielded == html
    assert image_srcs == {}


def test_polish_html_document_restores_large_data_image_after_shielded_polish() -> None:
    large_gif = base64.b64encode(b"GIF89a" + (b"A" * 250_000) + b";").decode("ascii")
    data_url = f"data:image/gif;base64,{large_gif}"
    html = f'<html><body><p><img src="{data_url}"/></p><p>Figure 7. Example caption.</p></body></html>'

    polished = polish_html_document(html, table_caption_language="en")

    assert data_url in polished
    assert "data-z2m-data-image-src-shield" not in polished
    assert _VALID_TINY_PNG_B64 not in polished


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
        "<p>Split DOI suffix doi: 10.1111/ de sc.12374</p>"
        "<p>Short split DOI suffix doi: 10.1186/ g m155</p>"
        "<p>Publisher word DOI doi:10.1126/ science.153.3732.197</p>"
        "<p>Publisher DOI doi:10.4028/ www.scientific.net/AMM.510.163</p>"
        "<p>PDF DOI URL https://onlinelibrary.wiley.com/doi/pdf/10 .1111/ j.1444-0938.2007.00120.x</p>"
        "<p>PNAS supplement www.pnas.org/lookup/suppl/doi:10.1073/pnas.1006199107/-/DCSupplemental.</p>"
        "<p>Repository record [10.4028/www.scientific.net/AMM.510.163]</p>"
        '<p>Proc. Natl. Acad. Sci. U.S.A <a href="https://doi.org/10.1073/pnas.1221113110">'
        ". 110, 18279-18284. doi: 10.1073/</a> pnas.1221113110</p>"
        '<p>Split DOI anchor <a href="https://doi.org/10.1111/desc.12374">doi: 10.1111/</a> '
        'de <a href="https://doi.org/10.1111/desc.12374">sc.12374</a></p>'
        '<p>Split DOI start <a href="https://doi.org/10.1111/j.1551-6709.2009.01040.x">doi:</a> '
        '10 <a href="https://doi.org/10.1111/j.1551-6709.2009.01040.x">.1111/j.1551-6709.2009.01040.x</a></p>'
        '<p>Split HTTP DOI anchor <a href="http://doi.org/10.1167/iovs.15-18991">'
        ". 2016;57(11):4948-4961, doi:10.1167/</a> iovs.15-18991.</p>"
        '<p>Split DOI head anchor doi:10.1590/ '
        '<a href="https://doi.org/10.1590/S1984-46702010000500002">S1984-46702010000500002</a></p>'
        '<p>Split DOI URL path <a href="https://doi.org/10.1146/annure">'
        "https://doi.org/10.1146/annure</a> v.bioeng.10.061807.160529</p>"
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
    assert 'href="https://doi.org/10.1111/desc.12374"' in polished
    assert 'href="https://doi.org/10.1186/gm155"' in polished
    assert 'href="https://doi.org/10.1126/science.153.3732.197"' in polished
    assert 'href="https://doi.org/10.4028/www.scientific.net/AMM.510.163"' in polished
    assert 'href="https://onlinelibrary.wiley.com/doi/pdf/10.1111/j.1444-0938.2007.00120.x"' in polished
    assert 'href="https://www.pnas.org/lookup/suppl/doi:10.1073/pnas.1006199107/-/DCSupplemental"' in polished
    assert 'lookup/suppl/doi:<a href=' not in polished
    assert polished.count(">10.4028/www.scientific.net/AMM.510.163</a>") == 2
    assert "10.4028/ www.scientific.net" not in polished
    assert "10.1111/ de sc" not in polished
    assert "10 .1111/ j" not in polished
    assert "AMM.510.163]</a>" not in polished
    assert ">10.4028/www.scientific.net/AMM.510.163</a>]" in polished
    assert 'doi: <a href="https://doi.org/10.1073/pnas.1221113110">10.1073/pnas.1221113110</a>' in polished
    assert "doi: 10.1073/</a> pnas" not in polished
    assert 'doi: <a href="https://doi.org/10.1111/desc.12374">10.1111/desc.12374</a>' in polished
    assert 'doi: <a href="https://doi.org/10.1111/j.1551-6709.2009.01040.x">10.1111/j.1551-6709.2009.01040.x</a>' in polished
    assert ">10.1167/iovs.15-18991</a>" in polished
    assert "doi:10.1167/</a> iovs" not in polished
    assert 'doi:<a href="https://doi.org/10.1590/S1984-46702010000500002">10.1590/S1984-46702010000500002</a>' in polished
    assert 'href="https://doi.org/10.1146/annurev.bioeng.10.061807.160529"' in polished
    assert "annure</a> v.bioeng" not in polished
    assert "10.1111/</a> de <a" not in polished
    assert ">doi:</a> 10 <a" not in polished
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
        '<p><a href="https://doi.org/10.1371/journal.pone.0223755.t001">'
        "https://doi.org/10.1371/journal.pone.0223755.t001</a> one used a guide dog "
        "and two used no aid. Of those using visual aids, only one subject tested the LEO Belt.</p>"
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
    assert (
        '<a href="https://doi.org/10.1371/journal.pone.0223755.t001">'
        "https://doi.org/10.1371/journal.pone.0223755.t001</a></p>"
    ) in polished
    assert "<p>one used a guide dog and two used no aid." in polished


def test_polish_html_document_moves_table_doi_body_tail_out_of_table_unit() -> None:
    html = (
        "<html><body>"
        '<div id="table-1" class="z2m-float-unit z2m-table-unit">'
        '<p class="z2m-table-caption">Table 1. Participant information.</p>'
        "<table><tr><td>1</td><td>24</td></tr></table>"
        '<p block-type="Text" class="z2m-table-note">'
        '<a href="https://doi.org/10.1371/journal.pone.0249996.t001">'
        "https://doi.org/10.1371/journal.pone.0249996.t001</a> "
        "switch, the first stimulation started at 40% intensity output. "
        "If no phosphenes were present, TMS intensity output was increased.</p>"
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert (
        '<p block-type="Text" class="z2m-table-note">'
        '<a href="https://doi.org/10.1371/journal.pone.0249996.t001">'
        "https://doi.org/10.1371/journal.pone.0249996.t001</a></p>"
    ) in polished
    assert "</p></div> <p>switch, the first stimulation started" in compact


def test_polish_html_document_marks_electronic_supplementary_material_as_front_matter() -> None:
    html = (
        "<html><body>"
        "<p>Electronic supplementary material is available at "
        '<a href="http://dx.doi.org/10.1098/rspb.2013.3011">'
        "http://dx.doi.org/10.1098/rspb.2013.3011</a> "
        "or via http://rspb.royalsocietypublishing.org .</p>"
        "<h1>Visual navigation in starfish</h1>"
        "<p>Abstract starts here.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert re.search(
        r'<p class="z2m-front-matter">Electronic supplementary material is available at .*'
        r"or via .*rspb\.royalsocietypublishing\.org.*\.</p>",
        compact,
    )
    assert "2013.3011</a></p> <p>or via" not in compact


def test_polish_html_document_moves_plos_figure_doi_out_of_body_sentence() -> None:
    html = (
        "<html><body>"
        '<p block-type="Text">'
        "Before starting, participants were educated on phosphene characteristics to ensure "
        "accurate reporting. During the preassessment, participants were instructed to state "
        '"yes" if they perceived a phosphene after stimulation. If unsure, they were required '
        'to reply "maybe," and a subsequent pulse was administered. If they remained quiet '
        "after a stimulation was given, "
        '<a href="https://doi.org/10.1371/journal.pone.0249996.g001">'
        "https://doi.org/10.1371/journal.pone.0249996.g001</a> "
        'this indicated "no," and the coil was repositioned onto the next stimulation site.</p>'
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig 1. Experiment set-up.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert 'given, this indicated "no,"' in compact
    assert "0249996.g001</a> this indicated" not in compact
    assert '<p class="z2m-front-matter">DOI: <a href="https://doi.org/10.1371/journal.pone.0249996.g001"' in polished


def test_polish_html_document_splits_long_plos_table_doi_note_from_body_tail() -> None:
    note = (
        "Numeric details of the experimental parameter of phosphene count. Electrode spacing "
        "refers to the distance between electrode tips implanted in LGN tissue in a 3D regular "
        "grid pattern that will produce a center-weighted phosphene pattern in visual space. "
        "Total electrode count includes electrodes that will generate phosphenes anywhere in "
        "the entire visual field, most of which would not be active in the Primary experiment, "
        "whereas the count within 10 degrees is for those electrodes generating phosphenes that "
        "lie within the central part of visual space corresponding to the approximate location "
        "of the letterform stimuli in this report. "
    )
    html = (
        "<html><body>"
        f'<p block-type="Text">{note}doi:'
        '<a href="https://doi.org/10.1371/journal.pone.0073592.t002">'
        "10.1371/journal.pone.0073592.t002</a> "
        "The nine letters used from the Snellen set are shown paired with their three distractors.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "0073592.t002</a> The nine letters" not in compact
    assert "</a></p> <p>The nine letters used from the Snellen set" in compact


def test_polish_html_document_repairs_doi_anchor_that_swallowed_prose_tail() -> None:
    html = (
        "<html><body>"
        '<p block-type="Text">Figure supplement 2. Additional experimental functions.</p>'
        '<p block-type="Text">DOI: <a href="https://doi.org/10.7554/eLife.37841.009</p>'
        '<p>the">https://doi.org/10.7554/eLife.37841.009 the</a> path, the guide stops.</p>'
        '<p block-type="Text">DOI: '
        '<a href="https://doi.org/10.7554/eLife.37841.012 building">'
        "https://doi.org/10.7554/eLife.37841.012 building</a> "
        "that had been pre-scanned by the HoloLens.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert '<a href="https://doi.org/10.7554/eLife.37841.009">https://doi.org/10.7554/eLife.37841.009</a>' in compact
    assert "<p>the path, the guide stops.</p>" in compact
    assert '<a href="https://doi.org/10.7554/eLife.37841.012">https://doi.org/10.7554/eLife.37841.012</a>' in compact
    assert "<p>building that had been pre-scanned by the HoloLens.</p>" in compact


def test_polish_html_document_drops_confirmed_page_furniture_blocks() -> None:
    html = (
        "<html><body>"
        "<p>Keywords: assistive technology; urban mobility</p>"
        "<h1>check for</h1><p>updates</p>"
        "<p>Citation: Tachiquin, R.; Wearable Urban Mobility Assistive Device. Sensors 2021, 21, 5274. "
        "https://doi.org/10.3390/s21165274</p>"
        "<p>Academic Editor: Thurmon Lockhart</p>"
        '<p class="z2m-front-matter">Received: 4 May 2021 Accepted: 31 July 2021 Published: 4 August 2021</p>'
        "<p>Publisher's Note: MDPI stays neutral with regard to jurisdictional claims.</p>"
        "<p class=\"z2m-front-matter\">Copyright: 2021 by the authors. Licensee MDPI, Basel, Switzerland.</p>"
        "<h2>1. Introduction</h2><p>Body starts.</p>"
        "<p>15206777, 2021, S3, Downloaded from https://onlinelibrary.wiley.com/doi/10.1002/nau.24751 "
        "by Egyptian National Sti. Network (Enstinet), Wiley Online Library on [06/11/2022]. "
        "See the Terms and Conditions (https://onlinelibrary.wiley.com/terms-and-conditions) "
        "on Wiley Online Library for rules of use; OA articles are governed by the applicable Creative Commons License</p>"
        "<p>After footer body continues.</p>"
        "<h4><b>REFERENCES</b></h4><p block-type=\"ListGroup\"><ul>"
        '<li block-type="ListItem" id="ref-1">1. Reference.</li></ul></p>'
        "<h1><b>Resonance-Compatible Incubator With a Built-in Coil Ultrafast Magnetic Resonance Imaging "
        "of the Neonate in a Magnetic</b></h1>"
        "<p><i>Pediatrics</i> 2004;113;e150 Daniel J.A. Connolly.</p>"
        "<p>Updated Information & including high resolution figures, can be found at:</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "check for" not in polished
    assert "Citation: Tachiquin" not in polished
    assert "Wiley Online Library" not in polished
    assert "Resonance-Compatible Incubator With a Built-in Coil Ultrafast" not in polished
    assert "Body starts." in polished
    assert "After footer body continues." in polished


def test_polish_html_document_unwraps_section_title_page_anchor_in_prose() -> None:
    html = (
        "<html><body>"
        '<p block-type="Text">Using concept 1 as a reference, the following changes are made '
        'as described in <a href="#page-23-2">3.3.2 Evaluation criteria for concepts.</a></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="#page-23-2"' not in polished
    assert "3.3.2 Evaluation criteria for concepts." in polished


def test_polish_html_document_repairs_confirmed_float_body_residue_from_pdf_review() -> None:
    html = (
        "<html><body>"
        '<p block-type="Text">All analyses showed the Response Rate was expected since '
        'the "Marked" Response (of which the ADAS-Cog score is the '
        '<span id="page-5-2"> </span> Bolded rows show the distribution across all sites. </p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit"><p><img src="fig2.jpg"/></p></div>'
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit"><p><img src="fig4.jpg"/></p></div>'
        '<p block-type="Text" class="has-continuation"> main determinant) was more frequent '
        "than the other types of responses.</p>"
        '<p block-type="Text">While moving through the environment, contextual auditory and '
        "spatial information is acquired sequentially and is continuously updated, allowing "
        "the Control player exit </p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit"><p><img src="fig2b.jpg"/></p></div>'
        "<p>jewel</p><p>player</p><p>Game</p>"
        '<p class="z2m-figure-caption">FIGURE 2 | Virtual rendering of an existing building.</p>'
        "<p>jewel</p><p>exit</p><p>monster</p>"
        "<p> user to build a corresponding mental representation of the building's spatial layout. "
        "Spatial cues are updated after each step.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "ADAS-Cog score is the main determinant) was more frequent" in compact
    assert '<p class="z2m-table-note"><span id="page-5-2"> </span> Bolded rows show' in polished
    assert "score is the <span id=\"page-5-2\"> </span> Bolded rows" not in polished
    assert "allowing the user to build a corresponding mental representation" in compact
    assert "Control player exit" not in compact
    assert not re.search(r"<p>\s*(?:jewel|player|Game|exit|monster)\s*</p>", polished)


def test_polish_html_document_merges_split_summary_table_note_continuation() -> None:
    html = (
        "<html><body>"
        '<p class="z2m-table-note"><sup>*</sup> The basis for the <b>assumed risk</b> (e.g.</p>'
        '<p>the median control group risk across studies) is provided in footnotes. '
        'The <b>corresponding risk</b> is based on the assumed risk in the comparison group. '
        '<b>CI:</b> Confidence interval; </p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert '(e.g. the median control group risk across studies)' in compact
    assert 'class="z2m-table-note"' in polished
    assert "<p>the median control group risk" not in polished


def test_polish_html_document_splits_distinct_nested_figure_units() -> None:
    html = (
        "<html><body>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 1. First result.</p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig2.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Second result.</p>'
        "</div></div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    assert 'id="fig-2"' not in fig1_match.group(0)
    assert polished.index('<div id="fig-1"') < polished.index('<div id="fig-2"')
    assert polished.index("Figure 1. First result.</p></div>") < polished.index('<div id="fig-2"')


def test_polish_html_document_splits_leading_image_from_duplicate_caption_successor() -> None:
    html = (
        "<html><body>"
        "<p>The limits of agreement are presented in Fig. 2.</p>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="bland-altman-pooled.jpg"/></p>'
        '<p class="z2m-figure-target"><img src="bland-altman-change.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig. 3: Bland-Altman plot for change values. '
        "Fig. 3: Bland-Altman plot for change values.</p>"
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig2_match is not None
    assert fig3_match is not None
    assert "bland-altman-pooled.jpg" in fig2_match.group(0)
    assert "bland-altman-change.jpg" not in fig2_match.group(0)
    assert "bland-altman-pooled.jpg" not in fig3_match.group(0)
    assert "bland-altman-change.jpg" in fig3_match.group(0)


def test_polish_html_document_wraps_bare_image_in_sequence_gap() -> None:
    html = (
        "<html><body>"
        "<p>Learning trends are summarized in Figure 3.</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="mean-ratio.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Mean feedback ratio.</p>'
        "</div>"
        '<p><img src="learning-trends.jpg"/></p>'
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="volitional-control.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4. Volitional control results.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig3_match is not None
    assert "learning-trends.jpg" in fig3_match.group(0)
    assert "z2m-figure-target" in fig3_match.group(0)


def test_polish_html_document_wraps_leading_bare_image_before_first_figure_unit() -> None:
    html = (
        "<html><body>"
        "<p>The route guidance task is shown in Figure 1.</p>"
        '<p><img src="route-guidance-task.jpg"/></p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="training-performance.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Training performance.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    assert "route-guidance-task.jpg" in fig1_match.group(0)
    assert "z2m-figure-target" in fig1_match.group(0)


def test_polish_html_document_does_not_wrap_leading_gap_with_image_count_mismatch() -> None:
    html = (
        "<html><body>"
        "<p>The participant flow is shown in Figure 1.</p>"
        '<p><img src="flow-diagram.jpg"/></p>'
        '<p><img src="publisher-logo.jpg"/></p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="outcomes.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Outcomes.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert "flow-diagram.jpg" in polished
    assert "publisher-logo.jpg" in polished
    assert "Figure 1 image was not extracted" not in polished


def test_polish_html_document_marks_leading_gap_without_image_as_missing_figure_unit() -> None:
    html = (
        "<html><body>"
        "<p>The scanning sequence is summarized in Figure 1.</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="task.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Spatial task.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    assert 'data-z2m-origin="sequence-gap-missing-target"' in fig1_match.group(0)
    assert "Figure 1 image was not extracted" in fig1_match.group(0)
    assert polished.index('id="fig-1"') < polished.index('id="fig-2"')


def test_polish_html_document_does_not_mark_leading_gap_when_mention_precedes_visuals() -> None:
    html = (
        "<html><body>"
        "<p>The participant flow is shown in Figure 1.</p>"
        '<p><img src="flow-diagram.jpg"/></p>'
        '<p><img src="publisher-logo.jpg"/></p>'
        "<p>The later task is shown below.</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="outcomes.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Outcomes.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert "Figure 1 image was not extracted" not in polished


def test_polish_html_document_does_not_wrap_partial_leading_image_gap() -> None:
    html = (
        "<html><body>"
        "<p>The baseline endoscopy is shown in Figure 1.</p>"
        "<p>The preoperative scan is shown in Figure 2.</p>"
        "<p>The postoperative scan is shown in Figure 3.</p>"
        '<p><img src="baseline-endoscopy.jpg"/></p>'
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="follow-up.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4. Follow-up findings.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert 'id="fig-2"' not in polished
    assert 'id="fig-3"' not in polished
    assert "baseline-endoscopy.jpg" in polished


def test_polish_html_document_does_not_wrap_distant_frontmatter_image_as_partial_leading_gap() -> None:
    html = (
        "<html><body>"
        '<p><img src="journal-cover.jpg"/></p>'
        f"<p>{'Front matter text. ' * 260}</p>"
        "<p>The baseline endoscopy is shown in Figure 1.</p>"
        "<p>The preoperative scan is shown in Figure 2.</p>"
        "<p>The postoperative scan is shown in Figure 3.</p>"
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="follow-up.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4. Follow-up findings.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert 'id="fig-2"' not in polished
    assert 'id="fig-3"' not in polished
    assert "journal-cover.jpg" in polished


def test_polish_html_document_splits_leading_image_run_from_first_sequence_unit() -> None:
    html = (
        "<html><body>"
        "<p>Figure 1 shows the baseline exam. Figure 2 shows the CT scan. "
        "Figure 3 shows navigation setup.</p>"
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="baseline.jpg"/></p>'
        '<p class="z2m-figure-target"><img src="ct-scan.jpg"/></p>'
        '<p class="z2m-figure-target"><img src="navigation.jpg"/></p>'
        '<p class="z2m-figure-target"><img src="eye-position.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4. Eye position before surgery.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    for fig_num, image in [
        ("1", "baseline.jpg"),
        ("2", "ct-scan.jpg"),
        ("3", "navigation.jpg"),
        ("4", "eye-position.jpg"),
    ]:
        fig_match = re.search(
            rf'<div\b(?=[^>]*\bid="fig-{fig_num}")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
            polished,
        )
        assert fig_match is not None
        assert image in fig_match.group(0)

    fig4_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-4")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig4_match is not None
    assert "baseline.jpg" not in fig4_match.group(0)
    assert "Figure 4. Eye position before surgery." in fig4_match.group(0)


def test_polish_html_document_does_not_split_two_image_first_unit_as_missing_predecessor() -> None:
    html = (
        "<html><body>"
        "<p>Figure 1 describes the MRI acquisition protocol.</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="maze-visible-platform.jpg"/></p>'
        '<p class="z2m-figure-target"><img src="maze-hidden-platform.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Screenshots of the virtual maze task.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig2_match is not None
    assert "maze-visible-platform.jpg" in fig2_match.group(0)
    assert "maze-hidden-platform.jpg" in fig2_match.group(0)


def test_polish_html_document_marks_leading_gap_when_first_unit_images_are_source_named() -> None:
    html = (
        "<html><body>"
        "<p>The scan workflow is summarized in Figure 1.</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img data-z2m-src="_page_3_Figure_2.jpeg" src="fig2a.jpg"/></p>'
        '<p class="z2m-figure-target"><img data-z2m-src="_page_3_Figure_3.jpeg" src="fig2b.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Screenshots of the navigation task.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    assert "Figure 1 image was not extracted" in fig1_match.group(0)


def test_polish_html_document_wraps_unique_bare_source_named_figure() -> None:
    html = (
        "<html><body>"
        "<p>The stimulation setup is summarized in Figure 1.</p>"
        '<p><img src="_page_3_Figure_1.jpeg"/></p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="_page_4_Figure_2.jpeg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Outcome comparison.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    assert "_page_3_Figure_1.jpeg" in fig1_match.group(0)
    assert "z2m-figure-target" in fig1_match.group(0)


def test_polish_html_document_wraps_minimal_source_named_figure_without_existing_units() -> None:
    html = (
        "<html><body>"
        "<p>The trial flowchart is shown in Fig. 1.</p>"
        '<p><img src="_page_3_Figure_1.jpeg"/></p>'
        "<p>The navigation setup is shown in Fig. 2.</p>"
        '<p><img src="_page_4_Picture_11.jpeg"/></p>'
        "</body></html>"
    )

    polished = _recover_unique_bare_source_named_figure_units(html)

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    assert "_page_3_Figure_1.jpeg" in fig1_match.group(0)
    assert 'id="fig-2"' not in polished


def test_polish_html_document_does_not_wrap_ambiguous_bare_source_named_figures() -> None:
    html = (
        "<html><body>"
        "<p>The stimulation setup is summarized in Figure 1.</p>"
        '<p><img src="_page_3_Figure_1.jpeg"/></p>'
        "<p>Additional page artwork was extracted separately.</p>"
        '<p><img src="_page_4_Figure_1.jpeg"/></p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="_page_4_Figure_2.jpeg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Outcome comparison.</p>'
        "</div>"
        "</body></html>"
    )

    polished = _recover_unique_bare_source_named_figure_units(html)

    assert 'id="fig-1"' not in polished
    assert "_page_3_Figure_1.jpeg" in polished
    assert "_page_4_Figure_1.jpeg" in polished


def test_polish_html_document_wraps_multiple_bare_images_in_sequence_gap() -> None:
    html = (
        "<html><body>"
        "<p>Bipolar stimulation is summarized in Figure 9.</p>"
        "<p>The dynamic operation image is shown in Figure 10.</p>"
        '<div id="fig-8" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="sequential-map.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 8. Sequential stimulation map.</p>'
        "</div>"
        '<p><img src="bipolar-stimulation.jpg"/></p>'
        "<p>Dynamic operation test</p>"
        '<p><img src="dynamic-operation.jpg"/></p>'
        '<div id="fig-11" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="real-time-test.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 11. Real time dynamic operation.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig9_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-9")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig10_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-10")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig9_match is not None
    assert fig10_match is not None
    assert "bipolar-stimulation.jpg" in fig9_match.group(0)
    assert "dynamic-operation.jpg" in fig10_match.group(0)
    assert "z2m-figure-target" in fig9_match.group(0)
    assert "z2m-figure-target" in fig10_match.group(0)


def test_polish_html_document_does_not_wrap_multi_sequence_gap_with_image_count_mismatch() -> None:
    html = (
        "<html><body>"
        "<p>Bipolar stimulation is summarized in Figure 9.</p>"
        "<p>The dynamic operation image is shown in Figure 10.</p>"
        '<div id="fig-8" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="sequential-map.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 8. Sequential stimulation map.</p>'
        "</div>"
        '<p><img src="ambiguous-gap-image.jpg"/></p>'
        '<div id="fig-11" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="real-time-test.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 11. Real time dynamic operation.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-9"' not in polished
    assert 'id="fig-10"' not in polished
    assert "ambiguous-gap-image.jpg" in polished


def test_polish_html_document_marks_sequence_gap_without_image_as_missing_figure_unit() -> None:
    html = (
        "<html><body>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="controller.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Guidance system architecture.</p>'
        "</div>"
        "<p>The directional control pattern is shown in Figure 3.</p>"
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="direction-signal.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4. Continuous direction signal.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert 'data-z2m-origin="sequence-gap-missing-target"' in fig3
    assert "Figure 3 image was not extracted" in fig3
    assert "z2m-figure-target" in fig3


def test_polish_html_document_does_not_mark_unmentioned_sequence_gap_as_missing() -> None:
    html = (
        "<html><body>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="controller.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Guidance system architecture.</p>'
        "</div>"
        "<p>The next section describes the direction signal.</p>"
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="direction-signal.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4. Continuous direction signal.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-3"' not in polished
    assert "Figure 3 image was not extracted" not in polished


def test_polish_html_document_wraps_trailing_bare_image_after_last_figure_unit() -> None:
    html = (
        "<html><body>"
        "<p>A detailed map (Fig. 2) of the relative position of each phosphene was prepared.</p>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="electrode-array.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig. 1 Array of electrodes.</p>'
        "</div>"
        "<p>Consequently, as indicated in Fig. 2, six phosphenes were selected.</p>"
        '<p><img src="phosphene-map.jpg"/></p>'
        "<p>by the intrinsic phosphene flicker.</p>"
        '<p class="z2m-front-matter">We thank the patient and his family.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig2_match is not None
    assert "phosphene-map.jpg" in fig2_match.group(0)
    assert "z2m-figure-target" in fig2_match.group(0)


def test_polish_html_document_does_not_wrap_trailing_bare_image_after_backmatter() -> None:
    html = (
        "<html><body>"
        "<p>A detailed map (Fig. 2) of the relative position of each phosphene was prepared.</p>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="electrode-array.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig. 1 Array of electrodes.</p>'
        "</div>"
        '<p class="z2m-front-matter">We thank the patient and his family.</p>'
        '<p><img src="publisher-mark.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-2"' not in polished
    assert "publisher-mark.jpg" in polished


def test_polish_html_document_marks_trailing_gap_without_image_as_missing_figure_unit() -> None:
    html = (
        "<html><body>"
        "<p>The final phosphene map is summarized in Fig. 2.</p>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="electrode-array.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig. 1 Array of electrodes.</p>'
        "</div>"
        "<p>Consequently, Fig. 2 identified the selected phosphenes.</p>"
        "<h2>References</h2>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig2_match is not None
    assert "Figure 2 image was not extracted" in fig2_match.group(0)


def test_polish_html_document_marks_final_next_gap_mentioned_before_last_unit_as_missing() -> None:
    html = (
        "<html><body>"
        "<p>The camera rig is shown in Figure 2. Two array layouts are shown in Figure 3.</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="camera-rig.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Camera rig used for the experiment.</p>'
        "</div>"
        "<h2>Methods</h2>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig3_match is not None
    assert "Figure 3 image was not extracted" in fig3_match.group(0)
    assert polished.index('id="fig-2"') < polished.index('id="fig-3"')


def test_polish_html_document_does_not_mark_nonconsecutive_trailing_gap_as_missing() -> None:
    html = (
        "<html><body>"
        "<p>The final result appears in Figure 9.</p>"
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="figure-6.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 6. Last extracted result.</p>'
        "</div>"
        "<p>Figure 9 compares the held-out condition.</p>"
        "<h2>References</h2>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-7"' not in polished
    assert 'id="fig-8"' not in polished
    assert 'id="fig-9"' not in polished
    assert "image was not extracted into this HTML" not in polished


def test_polish_html_document_does_not_wrap_sequence_gap_without_visible_reference() -> None:
    html = (
        "<html><body>"
        "<p>The stimulation maps are discussed below.</p>"
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="previous-map.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 5. Previous stimulation map.</p>'
        "</div>"
        '<p><img src="unrelated-between-units.jpg"/></p>'
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="later-map.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 7. Later stimulation map.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert (
        re.search(
            r'<div\b(?=[^>]*\bid="fig-6")(?=[^>]*\bz2m-figure-unit\b)',
            polished,
        )
        is None
    )
    assert '<p><img src="unrelated-between-units.jpg"/></p>' in polished


def test_polish_html_document_splits_figure_unit_before_swallowed_body_tail() -> None:
    html = (
        "<html><body>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption"><b>Fig 1. First result.</b> Apparatus overview.</p>'
        '<p block-type="Text">The following paragraph belongs to the article body.</p>'
        '<span id="page-3-0"> </span>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig2.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig 2. Second result.</p>'
        "</div></div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)
    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig1_match is not None
    assert "The following paragraph belongs" not in fig1_match.group(0)
    assert 'id="fig-2"' not in fig1_match.group(0)
    assert '</div><p block-type="Text">The following paragraph belongs' in compact


def test_polish_html_document_splits_caption_doi_body_tail_and_repairs_sentence() -> None:
    html = (
        "<html><body>"
        "<p>The aerodynamic drag forces could be neglected as being less than the</p>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 1. Sketch of the boundary conditions. doi:'
        '<a href="https://doi.org/10.1371/journal.pone.0047111.g001" '
        'target="_blank" rel="noopener noreferrer">'
        "10.1371/journal.pone.0047111.g001</a> surface tension forces. "
        "Given these assumptions the steady-state equations apply.</p>"
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)
    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig1_match is not None
    assert "surface tension forces" not in fig1_match.group(0)
    assert 'href="https://doi.org/10.1371/journal.pone.0047111.g001"</p>' not in polished
    assert "less than the surface tension forces. Given these assumptions" in compact


def test_polish_html_document_splits_caption_body_tail_after_repaired_doi_path() -> None:
    html = (
        "<html><body>"
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig7.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 7. Canonical layout of the model. '
        '<a href="https://doi.org/10.1371/journal." target="_blank" rel="noopener noreferrer">'
        "https://doi.org/10.1371/journal.</a> pcbi.1000651.g007 "
        "the intrinsic features and predictions of this model are described below.</p>"
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)
    fig7_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-7")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig7_match is not None
    assert "the intrinsic features" not in fig7_match.group(0)
    assert "journal.pcbi.1000651.g007</a>" in fig7_match.group(0)
    assert "</div> <p>the intrinsic features and predictions of this model" in compact


def test_polish_html_document_keeps_uppercase_body_tail_outside_terminal_caption_doi() -> None:
    html = (
        "<html><body>"
        '<p block-type="Text">The actuators alert users about obstacles in VR.</p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig2.jpg"/></p>'
        '<p class="z2m-figure-caption"><b>Fig 2. (A) Picture of the ETA tested in this study '
        "and (B) subject wearing the ETA together with the VR device.</b> "
        '<a href="https://doi.org/10.1371/journal.pdig.0000275.g002">'
        "https://doi.org/10.1371/journal.pdig.0000275.g002</a> "
        "In its original configuration, the ETA was connected to a camera and a processing unit "
        "that were combined to form a computer vision system able to detect obstacles.</p>"
        "</div>"
        '<p block-type="Text">When the ETA was interfaced with the VR platform, the function changed.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)
    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig2_match is not None
    assert "In its original configuration" not in fig2_match.group(0)
    assert "journal.pdig.0000275.g002</a> In its original" not in compact
    assert "</div> <p>In its original configuration" in compact


def test_polish_html_document_does_not_reabsorb_lowercase_body_tail_after_caption_doi() -> None:
    html = (
        "<html><body>"
        '<p block-type="Text">Most of the complexity of these equations is described below.</p>'
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig7.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 7. Canonical layout of the foveal confluence. '
        "Plus and minus signs signify representations of the upper and lower visual field. "
        "doi:10.1371/journal.pcbi.1000651.g007 "
        "the intrinsic features and predictions of this model with realistic parameters "
        "suggest that this model is inadequate to describe the architecture.</p>"
        "</div>"
        '<p block-type="Text">This is because the shift is most easily conceptualized in Cartesian space.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)
    fig7_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-7")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig7_match is not None
    assert "the intrinsic features" not in fig7_match.group(0)
    assert "journal.pcbi.1000651.g007</a> the intrinsic" not in compact
    assert "</div> <p>the intrinsic features and predictions of this model" in compact


def test_polish_html_document_splits_caption_after_terminal_ref_citation_tail() -> None:
    html = (
        "<html><body>"
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig6.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 6. Improved data visualization. '
        'Data in Figures 2(A-C) were published previously.<sup>'
        '<a href="#ref-24" class="z2m-ref-link">24</a></sup> '
        "temperature below 45-C at low pH and below 70-C at pH 6-8.</p>"
        "</div>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 25))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    fig6_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-6")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig6_match is not None
    assert "temperature below" not in fig6_match.group(0)
    assert "<p>temperature below 45-C at low pH" in polished


def test_polish_html_document_splits_unclosed_figure_unit_before_body_tail() -> None:
    html = (
        "<html><body>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig 1. First result.</p>'
        '<p block-type="Text">This paragraph was swallowed by the figure wrapper.</p>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig2.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig 2. Second result.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig1_match is not None
    assert "This paragraph was swallowed" not in fig1_match.group(0)
    assert 'id="fig-2"' not in fig1_match.group(0)


def test_polish_html_document_splits_unclosed_figure_unit_before_next_image_block() -> None:
    html = (
        "<html><body>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig3a.jpg"/></p>'
        '<p class="z2m-figure-target"><img src="fig3b.jpg"/></p>'
        '<p class="z2m-figure-caption"><b>Fig 3.</b> Spectral frequency displays.</p>'
        '<p><img src="fig4.jpg"/></p>'
        '<p id="fig-4" class="z2m-figure-caption"><b>Fig 4.</b> Navigation performance.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert "Spectral frequency displays" in fig3
    assert "fig4.jpg" not in fig3
    assert "Fig 4." not in fig3


def test_polish_html_document_splits_late_figure_unit_before_body_heading_and_next_figure() -> None:
    html = (
        "<html><body>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig3a.jpg"/></p>'
        '<p class="z2m-figure-target"><img src="fig3b.jpg"/></p>'
        '<p class="z2m-figure-caption"><b>Fig 3.</b> Spectral frequency displays.</p>'
        "<p>2.5 Experimental protocol Testing was carried out in a large laboratory.</p>"
        '<p><img src="fig4.jpg"/></p>'
        '<p id="fig-4" class="z2m-figure-caption"><b>Fig 4.</b> Navigation performance.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)
    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert "Experimental protocol" not in fig3
    assert "fig4.jpg" not in fig3
    assert "Fig 4." not in fig3
    assert "</div><p>2.5 Experimental protocol Testing was carried out" in compact


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


def test_polish_html_document_repairs_scheme_split_same_href_url_fragments() -> None:
    url = "https://www.who.int/news-room/fact-sheets/detail/blindness-and-visual-impairment"
    tango_url = (
        "https://www.businessinsider.com/google-tango-2017-5?r=US&IR=T"
        "#in-this-demo-tango-is-used-in-a-classroom-to-show-a-bunch-of-students-a-virtual-globe-"
        "floating-in-the-middle-of-the-room-2"
    )
    html = (
        "<html><body>"
        '<p>Available online: https://'
        f'<a href="{url}">www.who.int</a> / news-room/fact-sheets/detail/ '
        f'<a href="{url}">blindness-and-visual-impairment</a> '
        "(accessed on 10 September 2020).</p>"
        '<p>Project site: https://<a href="https://soundofvision.net/">soundofvision.net</a> / '
        "(accessed on 10 September 2020).</p>"
        '<p>Factsheet: http://'
        '<a href="http://www.who.int/mediacentre/factsheets/fs282/en/">www.who.int</a> / '
        '<a href="http://www.who.int/mediacentre/factsheets/fs282/en/">mediacentre</a> '
        "/factsheets/fs282/en/ (accessed).</p>"
        '<p><a href="www.ada.gov/lodblind.htm">6www.ada.gov/lodblind.htm</a></p>'
        '<p>Waiver ( <a href="http://creativecom mons.org/publicdomain/zero/1.0/) applies">'
        "http://creativecom mons.org/publicdomain/zero/1.0/) applies</a> to data.</p>"
        '<p>Shop <a href="https://shop.aph.org/">https://shop.aph.org/https://shop.aph.org/</a>.</p>'
        '<p>Google Tango (https://'
        f'<a href="{tango_url}">www.businessinsider.com</a> /google-tango-2017-5?r=US&amp;IR=T#in-this '
        f'<a href="{tango_url}">demo-tango-is-used-in-a-classroom-to-show-a-bunch-of-students-a-virtual-globe-floating-in-the</a> '
        f'<a href="{tango_url}">middle-of-the-room-2)</a> device.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert f'Available online: <a href="{url}">{url}</a> (accessed' in polished
    assert '<a href="https://soundofvision.net/">https://soundofvision.net/</a> (accessed' in polished
    assert (
        '<a href="http://www.who.int/mediacentre/factsheets/fs282/en/">'
        "http://www.who.int/mediacentre/factsheets/fs282/en/</a> (accessed)"
    ) in polished
    assert '<a href="www.ada.gov/lodblind.htm">6 www.ada.gov/lodblind.htm</a>' in polished
    assert (
        'Waiver ( <a href="http://creativecommons.org/publicdomain/zero/1.0/">'
        "http://creativecommons.org/publicdomain/zero/1.0/</a>) applies to data."
    ) in polished
    assert 'Shop <a href="https://shop.aph.org/">https://shop.aph.org/</a>.' in polished
    tango_html_url = tango_url.replace("&", "&amp;")
    assert f'Google Tango (<a href="{tango_html_url}">{tango_html_url}</a>) device.' in polished
    assert "https://<a" not in polished
    assert "6www." not in polished
    assert " / news-room" not in polished


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


def test_polish_html_document_links_bracket_ranges_in_math_like_prose() -> None:
    html = (
        "<html><body>"
        "<p>Public datasets such as ADE20K [1, 2] and SceneNN [3] do not cover door handles.</p>"
        "<h4>References</h4><ol>"
        "<li>Dataset one.</li><li>Dataset two.</li><li>Dataset three.</li>"
        "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-1" class="z2m-ref-link">1</a>' in body
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' in body
    assert '<a href="#ref-3" class="z2m-ref-link">[3]</a>' in body


def test_polish_html_document_retargets_external_cross_tag_bracket_citations() -> None:
    long_query = "x" * 500
    html = (
        "<html><body>"
        f'<p>The correlations were reported as p <a href="https://example.test/a?{long_query}">[2,</a> '
        f'<a href="https://example.test/b?{long_query}">8]</a>.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 9))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "https://example.test" not in body
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' in body
    assert '<a href="#ref-8" class="z2m-ref-link">8</a>' in body


def test_polish_html_document_links_sentence_terminal_sup_range_after_unit_phrase() -> None:
    html = (
        "<html><body>"
        "<p>The force was sufficient for operating through a skull that was 1 mm thick.<sup>28-31</sup></p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 32))
        + "</ol></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )
    body = polished[: polished.index("References")]

    assert '<a href="#ref-28" class="z2m-ref-link">28</a>' in body
    assert '<a href="#ref-31" class="z2m-ref-link">31</a>' in body


def test_polish_html_document_links_numeric_citation_ranges_inside_tables() -> None:
    html = (
        "<html><body>"
        "<table><tr><td>Designs the questionnaire and analyzes the collected data</td>"
        "<td>[6, 66, 153]</td></tr>"
        "<tr><td>Contrast response</td><td>contrast <sup>51-53</sup> studies agreed.</td></tr></table>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 154))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    for ref_id in (6, 51, 53, 66, 153):
        assert f'href="#ref-{ref_id}"' in body


def test_polish_html_document_does_not_link_low_number_table_decimal_artifacts() -> None:
    html = (
        "<html><body>"
        "<table><tr><td>Head vertical transl. <sup>1,2</sup> 8.8</td>"
        "<td>Distance to the VI User <sup>1,2</sup> Sound Pattern</td></tr></table>"
        "<h4>References</h4><ol><li>Reference one.</li><li>Reference two.</li></ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body


def test_polish_html_document_cleans_reference_numbering_artifacts() -> None:
    html = (
        "<html><body>"
        "<p>Prior work<sup>32</sup> is cited.</p>"
        "<h4>References</h4><ul>"
        "<li>31. Prior, A. (2020). Baseline reference.</li>"
        "<li>33. 32 De Nunzio, C. (2021). The diagnosis of benign obstruction.</li>"
        "<li>25 33. Bishr, M. (2016). Medical management 3. of benign prostatic hyperplasia.</li>"
        "<li>34. Khorsheed, M. (2012). Challenges and Opportunities, Jeddah "
        "35. Al-Fawzan, M. (2014). Fostering university collaboration.</li>"
        "<li>36. 36Novadaq, Operator's Manual.</li>"
        "</ul></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert '<li id="ref-32"><span class="z2m-ref-num">32.</span> De Nunzio' in compact
    assert '<li id="ref-33"><span class="z2m-ref-num">33.</span> Bishr' in compact
    assert "Medical management of benign prostatic hyperplasia" in compact
    assert '<li id="ref-35"><span class="z2m-ref-num">35.</span> Al-Fawzan' in compact
    assert '<li id="ref-36"><span class="z2m-ref-num">36.</span> Novadaq' in compact
    assert "33. 32 De Nunzio" not in compact
    assert "25 33. Bishr" not in compact
    assert "36Novadaq" not in compact


def test_polish_html_document_moves_interleaved_backmatter_before_references() -> None:
    html = """
    <html><body>
    <p>The conclusion cites prior work 1.</p>
    <h3>DATA AVAILABILITY STATEMENT</h3>
    <p>The raw data will be made available by the authors.</p>
    <h3>ETHICS STATEMENT</h3>
    <p>The studies involving human participants were reviewed and approved by Simon Jones, Department of Computer Science,</p>
    <h2>REFERENCES</h2>
    <p block-type="ListGroup"><ul>
      <li>1. Alpha, A. (2020). First article.</li>
      <li>2. Beta, B. (2021). Second article.</li>
    </ul></p>
    <p block-type="Text">University of Bath, United Kingdom. Participation in the study was entirely voluntary and written informed consent was provided to participate in this study.</p>
    <h2>AUTHOR CONTRIBUTIONS</h2>
    <p>PH created the original idea for this project.</p>
    <h2>FUNDING</h2>
    <p>Research was supported by a university grant.</p>
    <p block-type="ListGroup"><ul>
      <li>3. Gamma, G. (2022). Third article.</li>
    </ul></p>
    </body></html>
    """

    polished = polish_html_document(html)

    references_pos = polished.index("REFERENCES")
    assert polished.index("University of Bath") < references_pos
    assert polished.index("AUTHOR CONTRIBUTIONS") < references_pos
    assert polished.index("FUNDING") < references_pos
    assert polished.index("Alpha, A.") > references_pos
    assert polished.index("Gamma, G.") > references_pos


def test_polish_html_document_strips_line_numbers_before_unnumbered_reference_items() -> None:
    html = (
        "<html><body>"
        "<h4>References</h4><ul>"
        "<li>25 5 H. Li, X. He, Z. Kang. Carbon dots.</li>"
        "<li>105 41 Y. Yan, M. Zhang, K. Gong. Chem. Mater.</li>"
        "</ul></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "25 5 H. Li" not in compact
    assert "105 41 Y. Yan" not in compact
    assert '<li id="ref-5"><span class="z2m-ref-num">5.</span> H. Li' in compact
    assert '<li id="ref-41"><span class="z2m-ref-num">41.</span> Y. Yan' in compact


def test_polish_html_document_strips_four_digit_reference_line_numbers_and_links_late_sup_range() -> None:
    html = (
        "<html><body>"
        "<p>Lower frequency bands contained most power<sup>106\u2013108</sup>.</p>"
        "<h4>References</h4><ul>"
        "<li>1161 106. Smith, M. A. Spatial and Temporal Scales of Neuronal Correlation. "
        "<i>Journal of Neuroscience</i> <b>28</b>, 12591-12603 (2008).</li>"
        "<li>1162 Primary Visual Cortex continuation.</li>"
        "<li>1163 107. Vinje, W. E. and Gallant, J. L. Sparse coding and decorrelation. "
        "<i>Science</i> <b>287</b>, 1273-1276 (2000).</li>"
        "<li>1164 during natural vision continuation.</li>"
        "<li>1165 108. Morales-Gregorio, A. et al. Neural manifolds in V1 change. "
        "<i>Cell Reports</i> <b>43</b>, (2024).</li>"
        "</ul></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    ref_section = polished[polished.index("References") :]

    assert '<li id="ref-106"><span class="z2m-ref-num">106.</span> Smith' in ref_section
    assert '<li id="ref-107"><span class="z2m-ref-num">107.</span> Vinje' in ref_section
    assert '<li id="ref-108"><span class="z2m-ref-num">108.</span> Morales-Gregorio' in ref_section
    assert "Primary Visual Cortex continuation." in ref_section
    assert "during natural vision continuation." in ref_section
    assert 'id="ref-109"' not in ref_section
    assert "1161 106." not in ref_section
    assert "1162 Primary" not in ref_section
    assert '<a href="#ref-106" class="z2m-ref-link">106</a>' in body
    assert '<a href="#ref-108" class="z2m-ref-link">108</a>' in body


def test_polish_html_document_recovers_missing_reference_entry_from_pdf_profile() -> None:
    html = (
        "<html><body>"
        "<p>Hernia repair outcomes were compared [158].</p>"
        "<h4>References</h4><ul>"
        '<li>[157] C. Schug-Pass, D. A. Jacob, and F. Kockerling, "Biomechanical properties," '
        "Hernia, vol. 17, pp. 773-777, 2013.</li>"
        '<li>[159] M. Cambal, P. Zonca, and B. Hrbaty, "Comparison of self-gripping mesh," '
        "Bratislavske Lekarske Listy, vol. 113, pp. 103-107, 2012.</li>"
        "</ul></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "reference_entries": [
                {
                    "page": 24,
                    "number": 158,
                    "text": (
                        'R. H. Fortelny, A. H. Petter-Puchner, C. May et al., "The impact '
                        "of atraumatic fibrin sealant vs. staple mesh fixation in TAPP hernia repair "
                        'on chronic pain and quality of life," Surgical Endoscopy and Other '
                        "Interventional Techniques, vol. 26, no. 1, pp. 249-254, 2012."
                    ),
                }
            ],
        },
    )
    ref_section = polished[polished.index("References") :]

    assert 'id="ref-158"' in ref_section
    assert "Fortelny" in ref_section
    assert "atraumatic fibrin sealant" in ref_section
    assert '<span class="z2m-ref-num">158.</span>' in ref_section
    assert 'href="#ref-158"' in polished[: polished.index("References")]


def test_polish_html_document_recovers_tail_reference_entry_from_pdf_profile() -> None:
    html = (
        "<html><body>"
        "<p>Balance problems increase fall risk [28-30].</p>"
        "<h4>References</h4><ul>"
        '<li id="ref-28">Willis JR. Existing reference.</li>'
        '<li id="ref-29">Wada T. Existing reference.</li>'
        "</ul></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "reference_entries": [
                {"page": 20, "number": 30, "text": "Lee HK, Scudds RJ. Balance comparison. Age and ageing. 2003."}
            ],
        },
    )
    ref_section = polished[polished.index("References") :]
    body = polished[: polished.index("References")]

    assert 'id="ref-30"' in ref_section
    assert "Lee HK, Scudds RJ" in ref_section
    assert '<a href="#ref-30" class="z2m-ref-link">30</a>' in body


def test_polish_html_document_appends_pdf_recovered_reference_section_without_existing_references() -> None:
    html = "<html><body><p>Prior work 1,2.</p></body></html>"

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "reference_entries_recovery_numbers": [1, 2],
            "reference_entries": [
                {"page": 3, "number": 1, "text": "Alpha A. First source. Journal, 2020."},
                {"page": 3, "number": 2, "text": "Beta B. Second source. Journal, 2021."},
            ],
        },
    )
    ref_section = polished[polished.index("References") :]
    body = polished[: polished.index("References")]

    assert 'data-z2m-pdf-recovered-references="1"' in ref_section
    assert 'id="ref-1"' in ref_section
    assert 'id="ref-2"' in ref_section
    assert "Alpha A. First source." in ref_section
    assert '<span class="z2m-ref-num">1.</span>' in ref_section
    assert '<a href="#ref-1" class="z2m-ref-link">1</a>' in body
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' in body


def test_polish_html_document_appends_existing_profile_references_for_plain_body_citations() -> None:
    html = (
        "<html><body>"
        "<p>The particles were below 10 nm. 1,2 Owing to fluorescence, signals were stable.</p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "reference_entries": [
                {"page": 10, "number": 1, "text": "Zhu D. Physiology. People Health Publishing Company, 2009."},
                {"page": 10, "number": 2, "text": "Yao T. Physiology. People Health Publishing Company, 2004."},
            ],
        },
    )
    ref_section = polished[polished.index("References") :]
    body = polished[: polished.index("References")]

    assert 'data-z2m-pdf-recovered-references="1"' in ref_section
    assert 'id="ref-1"' in ref_section
    assert '<a href="#ref-1" class="z2m-ref-link">1</a>' in body
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' in body
    assert "nm.<sup>" in body


def test_polish_html_document_does_not_append_affiliation_profile_entries_as_references() -> None:
    html = "<html><body><p>Communication after stroke was difficult 1,2.</p></body></html>"

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "reference_entries": [
                {
                    "page": 1,
                    "number": 1,
                    "text": "Wallace H. Coulter Department of Biomedical Engineering, Emory University, Atlanta, GA, USA",
                },
                {
                    "page": 1,
                    "number": 2,
                    "text": "Department of Neurosurgery, Emory University, Atlanta, GA, USA",
                },
            ],
        },
    )

    assert 'data-z2m-pdf-recovered-references="1"' not in polished
    assert 'id="ref-1"' not in polished
    assert 'href="#ref-1"' not in polished


def test_polish_html_document_links_superscript_citations_after_profile_reference_recovery() -> None:
    html = (
        "<html><body>"
        "<p>The particles were below 10 nm.<sup>1,2</sup>Owing to fluorescence, signals were stable.</p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "reference_entries": [
                {"page": 7, "number": 1, "text": "Fang Y. Carbon dots. ACS Nano, 2012."},
                {"page": 7, "number": 2, "text": "Baker SN. Carbon nanomaterials. Angew. Chem. Int. Ed., 2010."},
            ],
        },
    )
    body = polished[: polished.index("References")]

    assert '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,' in body
    assert '<a href="#ref-2" class="z2m-ref-link">2</a></sup>' in body
    assert "<sup>1,2</sup>" not in body


def test_polish_html_document_appends_pdf_recovered_prefix_for_later_body_citation_range() -> None:
    html = "<html><body><p>Settings were described in [6, 7].</p></body></html>"

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "reference_entries_recovery_numbers": [6, 7],
            "reference_entries": [
                {"page": 3, "number": number, "text": f"Reference {number}. Journal, 2020."}
                for number in range(1, 8)
            ],
        },
    )
    ref_section = polished[polished.index("References") :]
    body = polished[: polished.index("References")]

    assert 'id="ref-1"' in ref_section
    assert 'id="ref-7"' in ref_section
    assert '<a href="#ref-6" class="z2m-ref-link">6</a>' in body
    assert '<a href="#ref-7" class="z2m-ref-link">7</a>' in body


def test_polish_html_document_links_remaining_plain_superscript_ranges_in_superscript_docs() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 20))
    html = (
        "<html><body>"
        '<p>Prior work<sup><a href="#ref-7" class="z2m-ref-link">7</a></sup> '
        "and patient studies<sup>18,19</sup> reported sensitivity.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert '<a href="#ref-18" class="z2m-ref-link">18</a>' in polished
    assert '<a href="#ref-19" class="z2m-ref-link">19</a>' in polished
    assert "<sup>18,19</sup>" not in polished


def test_polish_html_document_links_flattened_et_al_citations_without_profile() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 18))
    html = (
        "<html><body>"
        "<p>Prior systems Ding et al. 15 / Palmom et al. 16 / "
        "Albellard et al. 17 reported feedback modes.</p>"
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'Ding et al.<sup><a href="#ref-15" class="z2m-ref-link">15</a></sup>' in polished
    assert 'Palmom et al.<sup><a href="#ref-16" class="z2m-ref-link">16</a></sup>' in polished
    assert 'Albellard et al.<sup><a href="#ref-17" class="z2m-ref-link">17</a></sup>' in polished


def test_late_unlinked_superscript_relink_only_handles_et_al_context() -> None:
    refs = "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 69))
    html = (
        "<html><body>"
        "<p>The circuit follows Tehovnik et al.<sup>68</sup> during calibration, "
        "but hardware notes<sup>2</sup> remain footnote-like.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    fixed = _link_unlinked_numeric_superscripts_to_existing_refs(html)
    body = fixed[: fixed.index("References")]

    assert 'Tehovnik et al.<sup><a href="#ref-68" class="z2m-ref-link">68</a></sup>' in body
    assert "notes<sup>2</sup>" in body
    assert 'href="#ref-2"' not in body


def test_late_unlinked_superscript_relink_links_existing_numeric_ranges_before_references() -> None:
    refs = "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 110))
    html = (
        "<html><body>"
        '<p>Most power was concentrated in lower bands (<a href="#fig-2" '
        'class="z2m-fig-link">Figure 2E</a>,F)<sup>106\u2013108</sup>.</p>'
        "<h4>References</h4><ol>"
        '<li id="ref-106">Reference note<sup>106\u2013108</sup>.</li>'
        f"{refs}</ol>"
        "</body></html>"
    )

    fixed = _link_unlinked_numeric_superscripts_to_existing_refs(html)
    body = fixed[: fixed.index("References")]
    references = fixed[fixed.index("References") :]

    assert '<a href="#ref-106" class="z2m-ref-link">106</a>' in body
    assert '<a href="#ref-108" class="z2m-ref-link">108</a>' in body
    assert "<sup>106\u2013108</sup>" not in body
    assert "Reference note<sup>106\u2013108</sup>" in references


def test_polish_html_document_links_spaced_et_al_after_existing_superscripts() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 26))
    html = (
        "<html><body>"
        '<p block-type="Text">Variations in flow rate were reported.'
        '<sup><a href="#ref-22" class="z2m-ref-link">22</a></sup> '
        "Fantl et al 10 calls it multiple peak, and specifies 20% of <i>Q</i> max. "
        "Pauwels et al 11 names this shape undulating.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'Fantl et al<sup><a href="#ref-10" class="z2m-ref-link">10</a></sup>' in polished
    assert 'Pauwels et al<sup><a href="#ref-11" class="z2m-ref-link">11</a></sup>' in polished
    assert "Fantl et al 10" not in polished


def test_polish_html_document_links_spaced_et_al_in_bracket_numeric_docs() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 26))
    html = (
        "<html><body>"
        '<p block-type="Text">A bracket citation remains primary '
        '<a href="#ref-22" class="z2m-ref-link">[22]</a>. '
        "Fantl et al 10 calls it multiple peak, and specifies 20% of <i>Q</i> max.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )

    assert 'href="#ref-22"' in polished
    assert 'Fantl et al<sup><a href="#ref-10" class="z2m-ref-link">10</a></sup>' in polished
    assert "Fantl et al 10" not in polished


def test_polish_html_document_links_split_et_al_two_digit_citation() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 22))
    html = (
        "<html><body>"
        '<p block-type="Text">Chou et al16 and Jorgensen et al1\n'
        '7 call this shape "tall and peaked".</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'Chou et al<sup><a href="#ref-16" class="z2m-ref-link">16</a></sup>' in polished
    assert 'Jorgensen et al<sup><a href="#ref-17" class="z2m-ref-link">17</a></sup>' in polished
    assert "Jorgensen et al1" not in polished
    assert 'href="#ref-1"' not in polished[: polished.index("References")]


def test_polish_html_document_repairs_split_et_al_two_digit_link() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 22))
    html = (
        "<html><body>"
        '<p block-type="Text">and Jorgensen et al<sup>'
        '<a href="#ref-1" class="z2m-ref-link">1</sup> </a> 7 '
        'call this shape "high flow".</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'Jorgensen et al<sup><a href="#ref-17" class="z2m-ref-link">17</a></sup>' in body
    assert 'href="#ref-1" class' not in body
    assert "> 7" not in body


def test_polish_html_document_links_split_et_al_two_digit_before_page_linked_verb() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 22))
    html = (
        "<html><body>"
        '<p block-type="Text">Ghobish refined the definition, and Jensen et al2\n'
        '0 <a href="#page-6-0">define</a> intermittent flow as lasting 15 s.</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'Jensen et al<sup><a href="#ref-20" class="z2m-ref-link">20</a></sup>' in polished
    assert "Jensen et al2" not in polished


def test_polish_html_document_links_flattened_dot_and_range_superscripts() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 28))
    html = (
        "<html><body>"
        "<p>Nearby landmarks.18-22 This approach was used. "
        "The maps combine landmark recognition.12,13,26,27 However, maintenance is hard.</p>"
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'landmarks.<sup><a href="#ref-18" class="z2m-ref-link">18</a>-' in polished
    assert '<a href="#ref-22" class="z2m-ref-link">22</a></sup>' in polished
    assert 'recognition.<sup><a href="#ref-12" class="z2m-ref-link">12</a>,' in polished
    assert "landmarks.18-22" not in polished
    assert "recognition.12,13,26,27" not in polished


def test_polish_html_document_links_flattened_dot_ranges_in_bracket_profile() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 29))
    html = (
        "<html><body>"
        '<p>A normal bracket citation remains <a href="#ref-3" class="z2m-ref-link">[3]</a>. '
        "Nearby landmarks.18-22 These apps are GPS-based.23-25 "
        "Landmark recognition.12,13,26,27 may help. A final solution.28 follows.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )
    body = polished[: polished.index("References")]

    assert 'href="#ref-3"' in body
    assert 'landmarks.<sup><a href="#ref-18" class="z2m-ref-link">18</a>-' in body
    assert 'apps are GPS-based.<sup><a href="#ref-23" class="z2m-ref-link">23</a>-' in body
    assert 'recognition.<sup><a href="#ref-12" class="z2m-ref-link">12</a>,' in body
    assert 'solution.<sup><a href="#ref-28" class="z2m-ref-link">28</a></sup>' in body
    assert "landmarks.18-22" not in body
    assert "recognition.12,13,26,27" not in body


def test_polish_html_document_links_repeated_flattened_single_superscripts() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 67))
    html = (
        "<html><body>"
        "<p>Training supports independence. 66 It also compensates for reduced visual information 66 "
        "and supports people across the life span. 66 A later study agreed.</p>"
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'independence. <sup><a href="#ref-66" class="z2m-ref-link">66</a></sup> It' in polished
    assert 'span. <sup><a href="#ref-66" class="z2m-ref-link">66</a></sup> A later' in polished
    assert "independence. 66 It" not in polished


def test_polish_html_document_repairs_nested_reference_anchor_wrappers() -> None:
    refs = "".join(f"<li>{idx}. Ref {idx}.</li>" for idx in range(1, 104))
    html = (
        "<html><body>"
        "<p>Prior work [52, 74, 75] was cited.</p>"
        "<p>Mapping [91], [103] is useful.</p>"
        "<p>Complications <a href=\"javascript:void(0)\">["
        '<a href="#ref-6" class="z2m-ref-link">6</a>,</a> '
        '<a href="#ref-7" class="z2m-ref-link">7</a>].</p>'
        '<p>Legacy PMID: <a href="http://example.test">23844067</a></a> Smith.</p>'
        '<p>Available: <a href="https://play.google.com/store/apps/details?id=com.app">'
        "https://play.google.com/store/apps/details?id=com.app</a></a> (2015).</p>"
        '<p>The inaccessible routes have been mentione <a href="#ref-6" class="z2m-ref-link">'
        'd [<a href="#ref-6" class="z2m-ref-link">6</a>, '
        '<a href="#ref-7" class="z2m-ref-link">7</a>].</a></p>'
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="javascript:void(0)"' not in polished
    assert "</a></a>" not in polished
    assert "mentioned [" in polished
    assert "mentione " not in polished
    assert re.search(r'<a href="#ref-52"[^>]*>52</a>,\s*<a href="#ref-74"', polished)
    assert re.search(r'\[<a href="#ref-6"[^>]*>6</a>,\s*<a href="#ref-7"', polished)
    assert re.search(
        r'<a href="#ref-91"[^>]*>\[91\]</a>,\s*<a href="#ref-103"[^>]*>\[103\]</a>',
        polished,
    )


def test_polish_html_document_removes_malformed_outer_author_year_ref_anchor() -> None:
    html = (
        "<html><body>"
        "<p>The finding was in contrast to Teng and Whitney ("
        '<a href="#ref-12" class="z2m-ref-link">2011) and Thaler et al. (2014a).</p>'
        "<h3>Results</h3>"
        '<p id="fig-2"><img src="fig2.jpg"/></p>'
        '<p>Fig. <a href="#fig-2" class="z2m-fig-link">2)</a> summarizes performance.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 13))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-12"' not in body
    assert "Teng and Whitney (2011) and Thaler et al. (2014a)." in re.sub(r"\s+", " ", body)
    assert re.search(r'<a\b[^>]*href="#ref-12"[\s\S]*<a\b', body) is None


def test_polish_html_document_removes_malformed_outer_italic_ref_anchor() -> None:
    html = (
        "<html><body>"
        '<p><i><a href="#ref-35" class="z2m-ref-link">Nada et al. (2015)</i> '
        "placed sensors near landmarks. Later work ("
        '<i><a href="#ref-48" class="z2m-ref-link">Vera</a></i> Zenteno 2018) agreed.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 49))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    flat = re.sub(r"\s+", " ", body)

    assert 'href="#ref-35"' not in body
    assert "Nada et al. (2015)" in flat
    assert re.search(r'<a\b[^>]*href="#ref-35"[\s\S]*<a\b', body) is None


def test_polish_html_document_keeps_plain_sup_footnotes_in_bracket_numeric_docs() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 30))
    html = (
        "<html><body>"
        '<p>A bracket citation remains primary <a href="#ref-21" class="z2m-ref-link">[21]</a>.</p>'
        "<p>The sensor belt holds components,<sup>2</sup> a controller,<sup>3</sup> "
        "and battery. <sup>6</sup> All components are listed.</p>"
        "<p>The haptic rendering stacked outlines into a 2 1<sup>2</sup>D structure.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )

    body = polished[: polished.index("References")]
    assert 'href="#ref-21"' in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-6"' not in body
    assert "2 1<sup>2</sup>D" in body


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


def test_polish_html_document_repairs_ref_anchor_ocr_split_word_fragments() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 61))
    html = (
        "<html><body>"
        "<p>Silverstein' "
        '<a href="#ref-13" class="z2m-ref-link">s13</a> described the task.</p>'
        '<p>The main subcortical input to the AD <a href="#ref-38" class="z2m-ref-link">n56.</a></p>'
        '<p>Methods adopted in the 1990 <a href="#ref-29" class="z2m-ref-link">s60</a>.</p>'
        '<p>Pressure P <a href="#ref-36" class="z2m-ref-link">a36.</a> remained stable.</p>'
        '<p>The stimulus se <a href="#ref-11" class="z2m-ref-link">t11.</a> continued.</p>'
        '<p>The questionnaire was referenced as se <a href="#ref-18" class="z2m-ref-link">e18</a>.</p>'
        '<p>The next step tw <a href="#ref-32" class="z2m-ref-link">o32</a> succeeded.</p>'
        '<p>The visual ag <a href="#ref-20" class="z2m-ref-link">e20</a> range was broad.</p>'
        '<p>A small-scale ma <a href="#ref-13" class="z2m-ref-link">p13.</a> was studied.</p>'
        '<p>The assessment was more object iv <a href="#ref-3" class="z2m-ref-link">e3</a>.</p>'
        '<p>Visual cortex V <a href="#ref-34" class="z2m-ref-link">153.</a> was studied.</p>'
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'Silverstein\'s<sup><a href="#ref-13" class="z2m-ref-link">13</a></sup>' in body
    assert 'ADn<sup><a href="#ref-56" class="z2m-ref-link">56</a></sup>.' in body
    assert '1990s<sup><a href="#ref-60" class="z2m-ref-link">60</a></sup>.' in body
    assert 'Pa<sup><a href="#ref-36" class="z2m-ref-link">36</a></sup>.' in body
    assert 'set<sup><a href="#ref-11" class="z2m-ref-link">11</a></sup>.' in body
    assert 'see<sup><a href="#ref-18" class="z2m-ref-link">18</a></sup>.' in body
    assert 'two<sup><a href="#ref-32" class="z2m-ref-link">32</a></sup> succeeded' in body
    assert 'age<sup><a href="#ref-20" class="z2m-ref-link">20</a></sup> range' in body
    assert 'map<sup><a href="#ref-13" class="z2m-ref-link">13</a></sup>.' in body
    assert 'objective<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>.' in body
    assert 'V1<sup><a href="#ref-53" class="z2m-ref-link">53</a></sup>.' in body
    assert 'href="#ref-38"' not in body
    assert 'href="#ref-29"' not in body
    assert 'href="#ref-34"' not in body


def test_polish_html_document_retargets_or_unwraps_mismatched_ref_labels() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 61))
    html = (
        "<html><body>"
        '<p>The estimates are current<sup><a href="#ref-33" class="z2m-ref-link">55</a>'
        '<a href="#ref-56" class="z2m-ref-link">,56,</a></sup> across trials.</p>'
        '<p>Later work <a href="#ref-27" class="z2m-ref-link">57</a> confirmed this.</p>'
        '<p>Copyright Elsevier 201 <a href="#ref-64" class="z2m-ref-link">986</a>.</p>'
        '<p>Performance <a href="#ref-15" class="z2m-ref-link">'
        "could be achieved with as few as 325 (Srivastava, Troyk,</a> "
        "and Dagnelie, 2009) phosphenes.</p>"
        f"<h4>References</h4><ul>{refs}</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-55" class="z2m-ref-link">55</a>' in body
    assert '<a href="#ref-56" class="z2m-ref-link">,56,</a>' in body
    assert '<a href="#ref-57" class="z2m-ref-link">57</a>' in body
    assert 'href="#ref-33"' not in body
    assert 'href="#ref-27"' not in body
    assert 'href="#ref-64"' not in body
    assert 'href="#ref-15"' not in body
    assert "could be achieved with as few as 325" in body


def test_polish_html_document_keeps_bracket_citations_near_group_word() -> None:
    html = (
        "<html><body>"
        "<p>Over 35 million of this group are classified as blind [1, 2]. "
        "A large proportion of sight loss remains without a cure [3].</p>"
        "<h4>References</h4><ol>"
        "<li>Reference one.</li><li>Reference two.</li><li>Reference three.</li>"
        "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '[<a href="#ref-1" class="z2m-ref-link">1</a>, <a href="#ref-2" class="z2m-ref-link">2</a>]' in body
    assert '<a href="#ref-3" class="z2m-ref-link">[3]</a>' in body


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
        "<p>PMD news https: // https://www.pmdtec.com/news_media/press_release/leica-pmd.php</p>"
        "<p>WHO trends https:// www.who. int/ blindness /causes/trends/en/</p>"
        "<p>Curve notes http:// pages.mtu.edu /~{}shene/COURSES/cs3621/NOTES/curves/ continuity.html</p>"
        "<p>Medical shop https:// www.devinemedical. com/ 541035-good-vibrations-vibrating-clock-p /lss-541035.htm</p>"
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
    assert 'href="https://www.pmdtec.com/news_media/press_release/leica-pmd.php"' in polished
    assert 'href="https://www.who.int/blindness/causes/trends/en/"' in polished
    assert 'href="http://pages.mtu.edu/~{}shene/COURSES/cs3621/NOTES/curves/continuity.html"' in polished
    assert 'href="https://www.devinemedical.com/541035-good-vibrations-vibrating-clock-p/lss-541035.htm"' in polished
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
    assert "https: //" not in polished
    assert "who. int" not in polished
    assert "pages.mtu.edu /" not in polished
    assert "curves/ continuity" not in polished
    assert "devinemedical. com" not in polished
    assert "-p /lss" not in polished


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


def test_polish_html_document_merges_split_external_url_anchor_runs() -> None:
    pmd = "https://www.pmdtec.com/news_media/press_release/leica-pmd.php"
    wcc = "https://wccftech.com/infineons-tof-camera-sensor-is-capable-of-150k-pixel-output/"
    query = "https://example.com/search?q=foo+bar%2C+baz&btnG="
    who = "https://www.who.int/blindness/causes/trends/en/"
    devine = "https://www.devinemedical.com/541035-Sunu-Band-Mobility-Guide-and-Smart-Watch-p/lss-541035.htm"
    navcog = "http://www.cs.cmu.edu/~{}NavCog/navcog.html"
    query_html = query.replace("&", "&amp;")
    html = (
        "<html><body>"
        f'<p>PMD <a href="{pmd}">https:</a> // <a href="{pmd}">{pmd}</a>.</p>'
        f'<p>News https://<a href="{wcc}">wccftech.</a> com/ '
        f'<a href="{wcc}">infineons-tof-camera-sensor-is-capable-of-150k-pixel-output</a> /.</p>'
        f'<p>Search https://<a href="{query_html}">example.com</a> /search?q=foo+ '
        f'<a href="{query_html}">bar%2C</a> +baz&amp;btnG=.</p>'
        f'<p>WHO https://<a href="{who}">www.who.</a> int/ <a href="{who}">blindness</a> '
        "/causes/trends/en/ (accessed on 12 June 2020).</p>"
        f'<p>Shop https://<a href="{devine}">www.devinemedical.</a> com/ '
        f'<a href="{devine}">541035-Sunu-Band-Mobility-Guide-and-Smart-Watch-p</a> '
        "/lss-541035.htm (accessed on 5 July 2019).</p>"
        f'<p>NavCog http://<a href="{navcog}">www.cs.cmu.edu</a> '
        "/~{}NavCog/navcog.html (accessed on 29 July 2019).</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count(f'href="{pmd}"') == 1
    assert f">{pmd}</a>" in polished
    assert polished.count(f'href="{wcc}"') == 1
    assert f">{wcc}</a>" in polished
    assert polished.count(f'href="{query_html}"') == 1
    assert f">{query_html}</a>" in polished
    assert polished.count(f'href="{who}"') == 1
    assert f">{who}</a> (accessed on 12 June 2020)" in polished
    assert polished.count(f'href="{devine}"') == 1
    assert f">{devine}</a> (accessed on 5 July 2019)" in polished
    assert polished.count(f'href="{navcog}"') == 1
    assert f">{navcog}</a> (accessed on 29 July 2019)" in polished
    assert "https:</a> //" not in polished
    assert "wccftech.</a> com" not in polished
    assert "bar%2C</a> +baz" not in polished
    assert "www.who.</a> int" not in polished
    assert "www.devinemedical.</a> com" not in polished
    assert "www.cs.cmu.edu</a>" not in polished


def test_polish_html_document_repairs_noisy_url_anchor_tails() -> None:
    construction = "https://www.construction-physics.com/p/why-did-agriculture-mechanize-and"
    nuclear = "https://www.construction-physics.com/p/why-are-nuclear-power-construction-c3c"
    cc_by = "https://creativecommons.org/licenses/by/4.0/"
    html = (
        "<html><body>"
        '<p>Tiptoi (<a href="http://www" target="_blank" rel="noopener noreferrer">http://www</a>. '
        '<a href="http://www.penalty -@M tiptoi.com">tiptoi.com). While the last continues</a> '
        "for arbitrary content.</p>"
        f'<p>Ref. <a href="{construction}">Construction Physics, June 16, 2021, '
        "https://www.construction</a> physics.com/p/why-did-agriculture-mechanize-and.</p>"
        f'<p>Potter, Brian. "Why Are Nuclear Power Construction Costs So High? Part III: The Nuclear '
        f'<a href="{nuclear}">Navy." Construction Physics, July 1, 2022. https://www.construction-</a> '
        f'<a href="{nuclear}">physics.com/p/why-are-nuclear-power-construction-c3c.</a></p>'
        '<p>Licence <a href="https://creativecom-mons.org/licenses/by/ 4.0/">'
        "https://creativecom-mons.org/licenses/by/ 4.0/</a>.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'href="http://www.tiptoi.com"' in polished
    assert ">http://www.tiptoi.com</a>). While the last continues for arbitrary content." in re.sub(r"\s+", " ", polished)
    assert f'href="{construction}"' in polished
    assert f"Construction Physics, June 16, 2021, <a href=\"{construction}\">{construction}</a>." in re.sub(
        r"\s+",
        " ",
        polished,
    )
    assert f'Navy." Construction Physics, July 1, 2022. <a href="{nuclear}">{nuclear}</a>.' in re.sub(
        r"\s+",
        " ",
        polished,
    )
    assert polished.count(f'href="{cc_by}"') == 1
    assert f">{cc_by}</a>." in polished
    assert "http://www</a>. <a" not in polished
    assert "construction</a> physics.com" not in polished
    assert "construction-</a> <a" not in polished
    assert "creativecom-mons" not in polished
    assert "by/ 4.0" not in polished


def test_polish_html_document_merges_split_mailto_anchors() -> None:
    html = (
        "<html><body>"
        '<p>e-mail: <a href="mailto:gyorgy.buzsaki@nyulangone.org">gyorgy.buzsaki@</a> '
        '<a href="mailto:gyorgy.buzsaki@nyulangone.org">nyulangone.org</a></p>'
        '<p>(email: <a href="mailto:valeriaanna.sovrano@unitn.it">valeriaanna.</a> '
        '<a href="mailto:valeriaanna.sovrano@unitn.it">sovrano@unitn.it)</a></p>'
        '<p>e-mail: <a href="mailto:lotfi\\protect _merabet@meei.harvard.edu">lotfi_merabet@</a> '
        '<a href="mailto:lotfi\\protect _merabet@meei.harvard.edu">meei.harvard.edu</a></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count('href="mailto:gyorgy.buzsaki@nyulangone.org"') == 1
    assert ">gyorgy.buzsaki@nyulangone.org</a>" in polished
    assert polished.count('href="mailto:valeriaanna.sovrano@unitn.it"') == 1
    assert ">valeriaanna.sovrano@unitn.it</a>)" in polished
    assert polished.count('href="mailto:lotfi_merabet@meei.harvard.edu"') == 1
    assert ">lotfi_merabet@meei.harvard.edu</a>" in polished
    assert "gyorgy.buzsaki@</a>" not in polished
    assert "valeriaanna.</a>" not in polished
    assert "lotfi_merabet@</a>" not in polished


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
        '<li id="ref-3"><b><a href="#page-0-0"><span class="z2m-ref-num">3.</span></a></b> '
        "Marron JA. Orientation-mobility performance.</li>"
        '<li id="ref-4"><span class="z2m-ref-num">4.</span> Minich JA. Lateral. '
        '<a href="#page-17-0">2016</a>;5(1).</li>'
        '<li id="ref-5"><span class="z2m-ref-num">5.</span> W<a href="#page-8-11">3</a>C '
        "Accessibility Initiative. 2022.</li>"
        "</ul></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References"):]

    assert '<a href="#page-0-0"><span class="z2m-ref-num">1.</span></a>' not in polished
    assert '<a href="#page-0-0">2.</a>' not in polished
    assert '<a href="#page-0-0"><span class="z2m-ref-num">3.</span></a>' not in polished
    assert 'href="#page-17-0"' not in ref_section
    assert 'href="#page-8-11"' not in ref_section
    assert '<span class="z2m-ref-num">1.</span> Levy-Tzedek' in polished
    assert re.search(r"(?:>2\.</span>|>2\.) Auvray", polished)
    assert '<b><span class="z2m-ref-num">3.</span></b> Marron' in polished
    assert "Lateral. 2016;5(1)." in polished
    assert "W3C Accessibility Initiative" in polished


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
        "<p>The Kolmogoro v\u2013Smirno v test, Marko v decision process, and "
        "Lyapuno v stability analysis were listed.</p>"
        "<p>A Chebyche v filter, Tikhono v regularization, Lyapuno v exponents, "
        "Marko v fields, and a Gauss-Marko v hypothesis were listed.</p>"
        "<p>Zhangaskano v's approach, Georgie v's study, Azou vi et al., "
        "Moossa vi et al., and Ghaza vi et al. were cited.</p>"
        "<p>Agents used the Arxi v interface and Arxi v tool; Mostafa vi et al. used the nomogram. "
        "Mostafa vi et al13 called it staccato.</p>"
        "<p>Neura vi/Cerenovus, Inqo vi), A. Khosra vi are with Deakin, "
        "Krunosla v Stingl1,2, Ivano v IV, V. Popko v), Z. Moussa vi), Valery Putlaye v), "
        "Ak. Korole v str, University of the Nege v., and Laha v [4] were listed.</p>"
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
    assert "Kolmogorov\u2013Smirnov test, Markov decision process" in polished
    assert "Lyapunov stability analysis" in polished
    assert "Chebychev filter" in polished
    assert "Tikhonov regularization" in polished
    assert "Lyapunov exponents" in polished
    assert "Markov fields" in polished
    assert "Gauss-Markov hypothesis" in polished
    assert "Zhangaskanov's approach" in polished
    assert "Georgiev's study" in polished
    assert "Azouvi et al." in polished
    assert "Moossavi et al." in polished
    assert "Ghazavi et al." in polished
    assert "Arxiv interface and Arxiv tool; Mostafavi et al." in polished
    assert "Mostafavi et al13 called it staccato" in polished
    assert "Neuravi/Cerenovus" in polished
    assert "Inqovi)" in polished
    assert "A. Khosravi are with Deakin" in polished
    assert "Krunoslav Stingl" in polished
    assert "Ivanov IV" in polished
    assert "V. Popkov)" in polished
    assert "Z. Moussavi)" in polished
    assert "Valery Putlayev)" in polished
    assert "Ak. Korolev str" in polished
    assert "University of the Negev." in polished
    assert "Lahav [4]" in polished
    assert "Mean i * N" in polished
    assert "Dcon v refers" in polished
    assert "V. Bulatov. Scientific diagrams" in polished
    assert "Abdusalomo v" not in polished
    assert "Laha v" not in polished
    assert "Kolmogoro v" not in polished
    assert "Smirno v" not in polished
    assert "Marko v" not in polished
    assert "Lyapuno v" not in polished
    assert "Arxi v" not in polished
    assert "Mostafa vi" not in polished
    assert "Bulato v." not in polished


def test_polish_html_document_repairs_ref_linked_roman_suffix_author_year_split() -> None:
    html = (
        "<html><body>"
        "<p>Prior work by Korol and Pisan "
        '<a href="#ref-67" class="z2m-ref-link">i</a> '
        '<a href="#ref-67" class="z2m-ref-link">2015)</a> was cited.</p>'
        "<h4>References</h4>"
        '<ul><li id="ref-67"><span class="z2m-ref-num">67.</span> Pisani reference.</li></ul>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Korol and Pisani " in polished
    assert '<a href="#ref-67" class="z2m-ref-link">i</a>' not in polished
    assert '<a href="#ref-67" class="z2m-ref-link">2015)</a>' in polished


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


def test_polish_html_document_repairs_split_visible_emails_in_long_text_nodes() -> None:
    filler = " ".join(["background"] * 650)
    html = (
        "<html><body><p>"
        f"{filler} Email: jan. krhut@fno.cz. Contact: valeriaanna. sovrano@unitn.it. "
        "e-mail: lotfi_merabet@ meei.harvard.edu. Reach margaret.tarampi@psych .utah.edu. "
        "The request was addressed. jamesbarresemd@gmail.com."
        "</p></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Email: jan.krhut@fno.cz" in polished
    assert "Contact: valeriaanna.sovrano@unitn.it" in polished
    assert "lotfi_merabet@meei.harvard.edu" in polished
    assert "margaret.tarampi@psych.utah.edu" in polished
    assert "addressed. jamesbarresemd@gmail.com" in polished
    assert "jan. krhut@" not in polished
    assert "valeriaanna. sovrano@" not in polished
    assert "@ meei" not in polished
    assert "psych .utah" not in polished


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


def test_polish_html_document_repairs_sentence_split_across_sidebar_metadata() -> None:
    html = (
        "<html><body>"
        "<p>Conclusion The diagnostic accuracy is insufficient and reliability remains insufficiently</p>"
        "<h4>Strengths and limitations of this study</h4>"
        '<p block-type="ListGroup"><ul><li>Broad systematic search.</li></ul></p>'
        "<p>researched. Better study designs are needed.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "reliability remains insufficiently researched. Better study designs are needed." in flat
    assert "Strengths and limitations of this study" in flat
    assert polished.count("researched. Better study designs are needed.") == 1


def test_polish_html_document_repairs_body_paragraph_misclassified_as_front_matter() -> None:
    html = (
        "<html><body>"
        '<p class="z2m-front-matter">Patients with a history of lower urinary system surgery were ex-</p>'
        "<h4>Main Points:</h4>"
        '<p block-type="ListGroup"><ul><li>Uroflowmetry is an essential test.</li></ul></p>'
        "<p>cluded, and a total of 83 patients were included in the study.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "surgery were excluded, and a total of 83 patients" in flat
    assert "Main Points:" in flat


def test_polish_html_document_repairs_sentence_split_across_metadata_tail() -> None:
    html = (
        "<html><body>"
        "<p>Many visual computing algorithms turn</p>"
        "<p>This work was performed in cooperation with a museum.</p>"
        '<p>DOI <a href="https://doi.org/10.1145/2037820.2037822">10.1145/2037820.2037822</a> '
        '<a href="http://doi.acm.org/10.1145/2037820.2037822">http://doi.acm.org/10.1145/2037820.2037822</a> '
        "out to be equally well suited for tactile media.</p>"
        "<h2>Related Work</h2>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "Many visual computing algorithms turn out to be equally well suited for tactile media." in flat
    assert "10.1145/2037820.2037822" in flat
    assert "DOI" in flat


def test_polish_html_document_repairs_acm_permission_body_intrusion() -> None:
    html = (
        "<html><body>"
        "<p>Interestingly, many visual computing algorithms turn "
        "by others than ACM must be honored. Abstracting with credit is permitted. "
        "Permissions may be requested from Publications Dept., ACM, Inc., "
        "or permissions@acm.org.</p>"
        "<p>This work was performed in cooperation with a museum.</p>"
        '<p>DOI <a href="https://doi.org/10.1145/2037820.2037822">'
        "10.1145/2037820.2037822</a> "
        '<a href="http://doi.acm.org/10.1145/2037820.2037822">'
        "http://doi.acm.org/10.1145/2037820.2037822</a> "
        "out to be equally well suited for tactile media.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "many visual computing algorithms turn out to be equally well suited" in flat
    assert "by others than ACM must be honored" in flat
    assert "z2m-front-matter" in polished
    assert "DOI" in flat


def test_polish_html_document_repairs_acm_turn_out_across_metadata_blocks() -> None:
    html = (
        "<html><body>"
        "<p>Interestingly, many visual computing algorithms turn</p>"
        "<p>This work was performed in cooperation with a museum.</p>"
        "<p>All paintings copyright by the museum.</p>"
        "<p>Permission to make digital copies is granted. Copyrights for components "
        "of this work owned by others than ACM must be honored. Permissions may be "
        "requested at permissions@acm.org.</p>"
        "<p>© 2011 ACM 1556-4673/2011/11-ART5 $10.00</p>"
        '<p>DOI <a href="https://doi.org/10.1145/2037820.2037822">'
        "10.1145/2037820.2037822</a> "
        '<a href="http://doi.acm.org/10.1145/2037820.2037822">'
        "http://doi.acm.org/10.1145/2037820.2037822</a> "
        "out to be equally well suited for tactile media.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "many visual computing algorithms turn out to be equally well suited" in flat
    assert "by others than ACM must be honored" in flat
    assert not re.search(r"algorithms turn\s*</p>", polished)


def test_polish_html_document_moves_inline_clearvision_footnote_intrusion() -> None:
    html = (
        "<html><body>"
        "<p>These printers are readily available in communal locations such as libraries or schools. "
        "2 ClearVision project: www.clearvisionproject.org "
        "In summary, our work makes the following contributions: A novel system.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "schools. In summary, our work makes" in flat
    assert "2 ClearVision project:" in flat
    assert "www.clearvisionproject.org" in flat
    assert "z2m-footnote" in polished


def test_polish_html_document_splits_clearvision_footnote_body_tail() -> None:
    html = (
        "<html><body>"
        "<p>These printers are readily available in communal locations such as libraries or schools.</p>"
        '<p><sup>2</sup> <a href="http://www.clearvisionproject.org/">ClearVision project:</a> '
        '<a href="www.clearvisionproject.org">www.clearvisionproject.org</a></p>'
        "<p>In summary, our work makes the following contributions:</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "schools.</p><p>In summary, our work makes" in flat
    assert re.search(r"<p>In summary, our work makes", polished) is not None
    footnote = re.search(r'<p[^>]*class="z2m-footnote"[\s\S]*?</p>', polished)
    assert footnote is not None
    assert "In summary" not in footnote.group(0)


def test_polish_html_document_inserts_summary_boundary_after_small_animals_imaging() -> None:
    html = (
        "<html><body>"
        "<p>The fluorescence contrast is very promising for small animals imaging "
        "In summary, the nanomicelles could be employed for NIR in vivo imaging.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "small animals imaging. In summary, the nanomicelles" in flat


def test_polish_html_document_moves_box_body_tail_out_of_body_paragraph() -> None:
    html = (
        "<html><body>"
        "<p>Oscillatory cycles have a dual role. They organize sequential neuronal events as well as "
        "The temporal characteristics of brain oscillations are remarkably preserved across mammals. "
        "Brain-body oscillations span several orders of magnitude. Heartbeat rhythms bias the amplitude "
        "of various brain oscillations<sup>155</sup>.</p>"
        '<div id="box-1" class="z2m-float-unit z2m-box-unit">'
        '<h3 class="z2m-box-heading">Box 1 | Brain-body rhythms</h3>'
        '<p class="z2m-box-body">Periodic events coordinate neuronal activity.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())
    box = re.search(r'<div id="box-1"[\s\S]*?</div>', polished)

    assert "events as well as The temporal characteristics" not in flat
    assert "They organize sequential neuronal events.</p>" in flat
    assert box is not None
    assert "The temporal characteristics of brain oscillations" in box.group(0)


def test_polish_html_document_moves_glossary_out_of_body_paragraph_split() -> None:
    html = (
        "<html><body>"
        "<p>CNV could also be related to the haemodynamic response in the cortex, "
        "and thus indirectly to heartbeat variation, when human subjects judge duration 274. "
        "Studies</p>"
        "<h3><b>Glossary</b></h3>"
        "<h4>Cross-frequency phase-amplitude coupling</h4>"
        "<p>The most prominent law underlying the hierarchy of brain oscillators.</p>"
        "<h4>Working memory</h4>"
        "<p>A mechanism that allows information to be briefly held.</p>"
        "<p>relating timing and subjective experience of timing to infraslow and ultraslow "
        "oscillations are rare.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "judge duration 274. Studies relating timing and subjective experience" in flat
    assert "Studies Glossary Cross-frequency" not in flat
    assert flat.index("Studies relating timing") < flat.index("Glossary")


def test_polish_html_document_repairs_figure_caption_tail_taken_as_body_text() -> None:
    html = (
        "<html><body>"
        "<p>We found that all these forms of WM control used the cortical sheet. "
        "The idea is that during the initial encoding of the sequence, different spatiovectors "
        "extracted from 2 s (back) delay trials. Then data from 1 s (blue), 1.41 s (green), "
        "2.83 s (red) and 4 s (cyan) are plotted using the same weight vectors. "
        "c The 4-array spatial distribution is shown. Source data are provided as Source Data file. "
        "Panel a was created with clip art images from DESIGNALIKIE, Limited.</p>"
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="data:image/png;base64,AA=="/></p>'
        '<p class="z2m-figure-caption">Figure 5. Spatial patterns of control-related activity. '
        "They are projected using the eight-session average dPCA weight.</p></div>"
        '<p block-type="Text" class="has-continuation">temporal patterns of gamma are activated '
        "for the first vs second item.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "different spatio-temporal patterns of gamma are activated" in flat
    assert "dPCA weight vectors extracted from 2 s (back) delay trials" in flat
    assert "different spatiovectors extracted" not in flat


def test_polish_html_document_repairs_3d_space_split_by_float_run() -> None:
    html = (
        "<html><body>"
        "<p>The expert described subjects and mutual position in the (hypothetic)</p>"
        '<div id="fig-19" class="z2m-float-unit z2m-figure-unit"><p>Figure 19. Prototype.</p></div>'
        '<div id="fig-20" class="z2m-float-unit z2m-figure-unit"><p>Figure 20. Prototype.</p></div>'
        "<p>3D space. After this explanation, the panel tried again.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "mutual position in the (hypothetic) 3D space. After this explanation" in flat
    assert polished.count("3D space. After this explanation") == 1


def test_polish_html_document_repairs_blockquote_sentence_split_by_float() -> None:
    html = (
        "<html><body>"
        "<blockquote><p>Only longer</p></blockquote>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit"><p>Figure 2. Map.</p></div>'
        "<p>term studies will determine whether the implant is active.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "Only longer term studies will determine whether the implant is active." in flat
    assert polished.count("term studies will determine") == 1


def test_polish_html_document_moves_inline_author_email_intrusion() -> None:
    html = (
        "<html><body>"
        "<p>Lesions were excluded. A John G. Webster john.webster@wisc.edu major and essential "
        "step in the medical evaluation is physical examination.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "A major and essential step in the medical evaluation is physical examination." in flat
    assert "John G. Webster john.webster@wisc.edu" in flat


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


def test_polish_html_document_pairs_caption_after_image_run_across_empty_bridge() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig11a.jpg"/></p>'
        '<p><img src="fig11b.jpg"/></p>'
        '<p block-type="Text"></p>'
        "<p>Fig. 11. Empirical analysis on hyperparameters.</p>"
        "<p>Text after the figure.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    wrapper_start = polished.index('<div id="fig-11" class="z2m-float-unit z2m-figure-unit">')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert 'src="fig11a.jpg"' in wrapper
    assert 'src="fig11b.jpg"' in wrapper
    assert "Figure 11. Empirical analysis" in wrapper
    assert "z2m-missing-figure-warning" not in wrapper
    assert "Figure 11. Empirical analysis" not in after_wrapper
    assert "Text after the figure." in after_wrapper


def test_polish_html_document_pairs_caption_after_image_run_across_caption_note() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig2a.jpg"/></p>'
        '<p><img src="fig2b.jpg"/></p>'
        '<p block-type="Text">* User-defined criteria for the question "What electronic travel aids do you use": '
        "22C#1-Aipoly Vision, 22C#2-Envision AI. ** User-defined criteria for the question "
        '"If you would create a novel aid, what functions would be important": '
        "26C#1-interactive tactile map, 26C#2-nearby objects recognition.</p>"
        '<p><b>Figure 2.</b> The importance of chosen criteria as defined by the respondents.</p>'
        "<p>Text after the figure.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    wrapper_start = polished.index('<div id="fig-2" class="z2m-float-unit z2m-figure-unit">')
    wrapper_end = polished.index("</div>", wrapper_start)
    wrapper = polished[wrapper_start:wrapper_end]
    after_wrapper = polished[wrapper_end:]

    assert 'src="fig2a.jpg"' in wrapper
    assert 'src="fig2b.jpg"' in wrapper
    assert "User-defined criteria" in wrapper
    assert 'href="#fig-2"' in wrapper
    assert "The importance of chosen criteria" in wrapper
    assert "z2m-missing-figure-warning" not in wrapper
    assert "The importance of chosen criteria" not in after_wrapper
    assert "Text after the figure." in after_wrapper


def test_polish_html_document_does_not_pair_caption_forward_across_body_prose() -> None:
    html = (
        "<html><body>"
        "<p>Fig. 6. Route in the virtual environment.</p>"
        "<h3>Article running header</h3>"
        '<p><img src="fig7.jpg"/></p>'
        "<p>Fig. 7. Simulation in progress, with patient on bed.</p>"
        "<h1>Experiments</h1>"
        "<p block-type=\"Text\">The wheelchair condition is shown in Figure 8.</p>"
        '<p><img src="fig8.jpg"/></p>'
        "<p>Fig. 8. Patient preparing for starting a trial session.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig7_match = re.search(r'<div id="fig-7"[\s\S]*?</div>', polished)
    fig8_match = re.search(r'<div id="fig-8"[\s\S]*?</div>', polished)
    assert fig7_match is not None
    assert fig8_match is not None
    fig7 = fig7_match.group(0)
    fig8 = fig8_match.group(0)
    assert 'src="fig7.jpg"' in fig7
    assert 'src="fig8.jpg"' not in fig7
    assert "Simulation in progress" in fig7
    assert 'src="fig8.jpg"' in fig8
    assert "Patient preparing" in fig8
    assert "z2m-missing-figure-warning" not in fig8


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
    wrapper_match = re.search(r'<div[^>]*id="fig-5-24"[^>]*class="[^"]*z2m-figure-unit[^"]*"[^>]*>', polished)
    assert wrapper_match is not None
    wrapper_start = wrapper_match.start()
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
    assert re.search(r'<div id="fig-1" class="[^"]*\bz2m-float-unit\b[^"]*\bz2m-figure-unit\b', polished)


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
    assert re.search(r'<div id="fig-1" class="[^"]*\bz2m-float-unit\b[^"]*\bz2m-figure-unit\b', polished)


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
        "<p>* : statistically significant</p>"
        "<p>Median value(IQR) or number of cases(%)</p>"
        "<p>Positive value = increased symptoms, negative value = decreased symptoms</p>"
        "<p>Abbreviations RARP: robot-assisted radical prostatectomy</p>"
        "<p>CLSS: core lower urinary tract symptom score, QOL index: quality of life index</p>"
        "<p>Delta PVR, post-RARP residual urine volume - pre-RARP residual urine volume.</p>"
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
    assert "decreased symptoms three parameters" not in flat
    assert '<div id="table-1" class="z2m-float-unit z2m-table-unit' in polished
    assert '<div id="fig-2" class="z2m-float-unit z2m-figure-unit' in polished
    assert (
        'class="z2m-table-note">Positive value = increased symptoms, negative value = decreased symptoms</p>'
        in polished
    )


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
    assert '(0.12 mm<sup class="z2m-unit-exp">2</sup>). Electrode fabrication began' in flat


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


def test_polish_html_document_keeps_in_text_figure_reference_out_of_float_gap() -> None:
    html = (
        "<html><body>"
        "<p>The field of view was measured empirically by moving tags through the reader.</p>"
        '<p><a href="#fig-4" class="z2m-fig-link">Figure 4</a> shows the operating range '
        "of the tag reader as a function of the angle between</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig2.jpg"/></p>'
        '<p class="z2m-figure-caption"><b>Figure 2.</b> Segmentation of a digital tag.</p>'
        "</div>"
        "<p>the tag reader and the normal to the tag. The reader can identify coded numbers.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = " ".join(polished.split())

    assert "angle between the tag reader and the normal to the tag" in flat
    assert "Figure 2. Segmentation of a digital tag. the tag reader" not in flat


def test_polish_html_document_repairs_float_sentence_after_late_page_anchor_gap() -> None:
    html = (
        "<html><body>"
        '<p><a href="#fig-4" class="z2m-fig-link">Figure 4</a> shows the reading range '
        "as a function of the angle between</p>"
        '<span id="page-3-0"></span>'
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig2.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Test apparatus.</p>'
        "</div>"
        "<p>the tag reader and the normal to the tag. The reader is reliable.</p>"
        '<p id="fig-4"><img src="fig4.jpg"/></p>'
        "<p>Figure 4. Reading range.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    flat = re.sub(r"\s+", " ", polished)

    assert "angle between the tag reader and the normal to the tag." in flat
    assert "</div> <p>the tag reader and the normal" not in flat


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


def test_polish_html_document_moves_for_these_reasons_tail_out_of_box() -> None:
    html = (
        "<html><body>"
        "<p>The population size matters when evaluating whether an approach will be "
        "practically viable and sustainable. For these</p>"
        "<h2>BOX 1</h2>"
        "<h3>Indirect translation: examples inspired by optogenetic circuit analysis</h3>"
        "<p>In one approach to indirect translation, laboratory models provide a testing ground.</p>"
        "<p>These examples illustrate how optogenetics can guide treatment design.</p>"
        "<p>reasons, a transdiagnostic approach aimed at alleviating a specific symptom may make the most sense.</p>"
        "<h2>Preclinical disease models</h2>"
        "</body></html>"
    )

    polished = polish_html_document(html, polish_language="en")
    flat = " ".join(polished.split())

    assert "For these In one approach" not in flat
    assert "For these reasons, a transdiagnostic approach" in flat
    box_match = re.search(r'<div id="box-1"[\s\S]*?</div>', polished)
    assert box_match is not None
    assert "reasons, a transdiagnostic" not in box_match.group(0)
    assert polished.index("For these reasons") > polished.index("</div>")
    assert polished.index("For these reasons") < polished.index("Preclinical disease models")


def test_polish_html_document_keeps_split_figure_caption_continuations_out_of_body() -> None:
    html = (
        "<html><body>"
        "<p block-type=\"Text\">Viral vectors and gene therapy payloads could, "
        "in principle, also trigger global</p>"
        "<p><img src=\"fig4.png\"/></p>"
        "<p><b>Fig. 4 | Direct delivery methods.</b> Gene vector delivery may be "
        "targeted to the cell bodies or to</p>"
        "<p block-type=\"Text\">projection targets for additional specificity.</p>"
        "<p block-type=\"Text\">innate or adaptive immune responses that are toxic.</p>"
        "<p block-type=\"Text\">Delivery cannot completely prevent vector entry into "
        "the systemic circulation</p>"
        "<p><img src=\"fig5.png\"/></p>"
        "<p><b>Fig. 5 | Human immune responses.</b> Clinical experience has not "
        "revealed destruction of</p>"
        "<p block-type=\"Text\">transduced target cells behind the BBB. b, Human "
        "immune responses to AAV vectors.</p>"
        "<p block-type=\"Text\">(with some serotypes more likely to leak than others). "
        "AAV DNA could also be detected.</p>"
        "<p block-type=\"Text\">The light delivery devices themselves, if needed, also</p>"
        "<p><img src=\"fig7.png\"/></p>"
        "<p><b>Fig. 7 | Regulatory pathways.</b> The agency considers a notified "
        "body (medical device)</p>"
        "<p block-type=\"Text\">and the Committee for Advanced Therapies (gene therapy).</p>"
        "<p block-type=\"Text\">require evaluation for robustness and safety.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, polish_language="en")
    flat = " ".join(polished.split())

    assert "also trigger global innate or adaptive immune responses" in flat
    assert "also trigger global projection targets" not in flat
    assert "cell bodies or to projection targets for additional specificity" in flat
    assert "systemic circulation (with some serotypes more likely to leak than others)" in flat
    assert "revealed destruction of transduced target cells behind the BBB" in flat
    assert "The light delivery devices themselves, if needed, also require evaluation" in flat
    assert "body (medical device) and the Committee for Advanced Therapies" in flat


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


def test_polish_html_document_strips_page_linked_bracket_prefix_from_standalone_reference_paragraphs() -> None:
    html = (
        "<html><body>"
        "<p>Prior work [1, 2] is relevant.</p>"
        "<h4>References</h4>"
        '<p><span id="page-20-0"></span><a href="#page-0-0">[1] (</a>'
        "2022). World Report on Vision. [Online]. Available: https://example.org/report</p>"
        '<p><a href="#page-1-0">[2]</a> Miyagawa SH. Journey to excellence. Lakeville, MN: Press; 1999.</p>'
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )
    ref_section = polished[polished.index("References"):]

    assert '<p id="ref-1"><span class="z2m-ref-num">1.</span> (2022). World Report' in ref_section
    assert '<p id="ref-2"><span class="z2m-ref-num">2.</span> Miyagawa SH.' in ref_section
    assert 'href="#page-0-0"' not in ref_section
    assert 'href="#page-1-0"' not in ref_section
    assert '<a href="#ref-1" class="z2m-ref-link">1</a>' in polished[: polished.index("References")]
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' in polished[: polished.index("References")]


def test_polish_html_document_does_not_id_duplicate_number_doi_footer_as_reference() -> None:
    html = (
        "<html><body>"
        "<p>Screening outcomes followed the prior study [96].</p>"
        "<h4>References</h4>"
        "<p>95. Richardson J. Clinical vision screening. Ophthalmology. 2023.</p>"
        '<p>978 <a href="https://doi.org/10.2147/OPTH.S442430">'
        "https://doi.org/10.2147/OPTH.S442430</a> DovePress Clinical Ophthalmology 2024:18</p>"
        "<p>96. Papadopoulos A. Accessibility outcome measures. Clin Ophthalmol. 2024.</p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )
    ref_section = polished[polished.index("References") :]

    assert 'id="ref-978"' not in ref_section
    assert '<p id="ref-96">96. Papadopoulos A.' in ref_section
    assert '<a href="#ref-96" class="z2m-ref-link">[96]</a>' in polished[: polished.index("References")]


def test_polish_html_document_keeps_post_reference_lists_out_of_ref_ids() -> None:
    html = (
        "<html><body>"
        '<p>Stimuli were counterbalanced to minimize order effects <a href="#page-16-0">50.</a> '
        "Follow-up text.</p>"
        "<h4>References</h4>"
        "<p block-type=\"ListGroup\"><ul>"
        + "".join(f"<li>{idx}. Reference {idx}. Journal. 2020.</li>" for idx in range(1, 50))
        + "</ul></p>"
        '<p><span id="page-16-0"></span>50. Greenspon CM. Intracortical stimulation. '
        "Brain Stimul. 2024.</p>"
        "<h4><b>Acknowledgements</b></h4>"
        "<p>Thanks to all participants.</p>"
        "<h3>Data</h3>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>50. Accession codes, unique identifiers, or web links for publicly available datasets</li>"
        "<li>51. Restrictions on data availability.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    acknowledgements_and_after = polished[polished.index("Acknowledgements") :]

    assert '<a href="#ref-50" class="z2m-ref-link">50.</a>' in body
    assert '<p id="ref-50"><span id="page-16-0"></span>50. Greenspon CM.' in polished
    assert '<li id="ref-50"><span class="z2m-ref-num">50.</span> Accession codes' not in polished
    assert 'id="ref-51"' not in acknowledgements_and_after
    assert 'href="#page-16-0"' not in body


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


def test_polish_html_document_merges_lowercase_unnumbered_reference_continuation() -> None:
    html = (
        "<html><body>"
        "<h4>References</h4>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>Bishr, M., Boehm, K., Trudeau, V., Tian, Z., Dell'Oglio, P., "
        "Schiffmann, J., & Saad, F. (2016). Medical management</li>"
        "<li>of benign prostatic hyperplasia: Results from a population-based study. "
        "Canadian Urological Association Journal, 10(1-2), 55.</li>"
        "<li>Choudhury, S. (2010). Which voiding position is associated with lowest flow rates?</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "Medical management of benign prostatic hyperplasia" in compact
    assert re.search(r'id="ref-2"[\s\S]{0,120}Choudhury, S\.', polished) is not None
    assert re.search(r'id="ref-\d+"[\s\S]{0,80}of benign prostatic hyperplasia', polished) is None


def test_polish_html_document_merges_journal_title_reference_continuation() -> None:
    html = (
        "<html><body>"
        "<h4>References</h4>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>DECARLO, D., FINKELSTEIN, A., RUSINKIEWICZ, S., AND SANTELLA, A. "
        "2003. Suggestive contours for conveying shape.</li>"
        "<li>ACM Transactions on Graphics (SIGGRAPH '03) 22, 3 (July), 848-855.</li>"
        "<li>DICARLO, J., AND WANDELL, B. 2000. Rendering high dynamic range images.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "Suggestive contours for conveying shape. ACM Transactions on Graphics" in compact
    assert re.search(r'id="ref-2"[\s\S]{0,120}DICARLO, J\.', polished) is not None
    assert re.search(r'id="ref-\d+"[\s\S]{0,80}ACM Transactions', polished) is None


def test_polish_html_document_preserves_numbered_lowercase_author_reference() -> None:
    html = (
        "<html><body>"
        "<h4>References</h4>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>247. Safaie, M. et al. Turning the body into a clock.</li>"
        "<li>248. van Rijn, H. Towards ecologically valid interval timing.</li>"
        "<li>249. Hodos, W. Complex response patterns.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert re.search(r'id="ref-248"[\s\S]{0,80}van Rijn, H\.', polished) is not None
    assert "clock. van Rijn" not in re.sub(r"\s+", " ", polished)


def test_polish_html_document_merges_numbered_lowercase_reference_line_continuation() -> None:
    html = (
        "<html><body>"
        "<h4>References</h4>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>31. Demir A, Karadag MA. Abdominal or transrectal ultrasonographic prostate volume and cystoscopic prostatic</li>"
        "<li>32. urethral length measurements to determine the surgical technique. J Urol Surg 2016;3:119-22.</li>"
        "<li>33. 32 De Nunzio C, Lombardo R. The diagnosis of benign prostatic obstruction.</li>"
        "<li>34. 33 Guzelsoy M. Role of transition zone index.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "prostatic urethral length measurements" in compact
    assert '<li id="ref-32"><span class="z2m-ref-num">32.</span> De Nunzio' in compact
    assert '<li id="ref-33"><span class="z2m-ref-num">33.</span> Guzelsoy' in compact
    assert "33. 32 De Nunzio" not in compact


def test_polish_html_document_separates_reference_study_group_author_glue() -> None:
    html = (
        "<html><body>"
        "<h4>References</h4>"
        "<ul>"
        "<li>RNS System in Epilepsy Study GroupMorrell MJ. Responsive cortical stimulation.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Study Group. Morrell MJ" in polished
    assert "Study GroupMorrell" not in polished


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


def test_polish_html_document_accepts_line_numbered_bibliography_heading() -> None:
    html = (
        "<html><body>"
        "<p>Prior work [1] supports the approach.</p>"
        "<h4>898 <b>Bibliography</b></h4>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>899 1. First bibliography item.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="ref-1"' in polished
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in polished


def test_polish_html_document_accepts_compact_roman_references_heading() -> None:
    html = (
        "<html><body>"
        "<p>Prior work [1] supports the approach.</p>"
        "<h4>V.REFERENCES</h4>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>First bibliography item.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="ref-1"' in polished
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in polished


def test_polish_html_document_links_page_bracket_refs_with_swallowed_parenthesis() -> None:
    html = (
        "<html><body>"
        '<p>This approach limits the area of the ring (see <a href="#page-10-0">[29])</a> '
        'and remains tolerated (see <a href="#page-10-0">[28,31])</a>.</p>'
        "<h4>References</h4>"
        "<ul>"
        + "".join(
            (
                f'<li><span id="page-10-0"></span>[{i}] Reference {i}.</li>'
                if i == 28
                else f"<li>[{i}] Reference {i}.</li>"
            )
            for i in range(1, 32)
        )
        + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'see [<a href="#ref-29" class="z2m-ref-link">29</a>])' in body
    assert (
        'see [<a href="#ref-28" class="z2m-ref-link">28</a>, '
        '<a href="#ref-31" class="z2m-ref-link">31</a>]).'
    ) in body
    assert 'href="#page-10-0"' not in body


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


def test_polish_html_document_links_void_anchor_bracket_citations() -> None:
    html = (
        "<html><body>"
        '<p>Prior work <a href="javascript:void(0)"> [1] </a> and '
        '<a href="javascript:void(0)"> [2-4]. </a> supports this.</p>'
        "<h4>References</h4>"
        "<ul>" + "".join(f"<li>Ref {i}.</li>" for i in range(1, 5)) + "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "javascript:void(0)" not in body
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in body
    assert (
        '[<a href="#ref-2" class="z2m-ref-link">2</a>-'
        '<a href="#ref-4" class="z2m-ref-link">4</a>].'
    ) in body


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


def test_polish_html_document_protects_unicode_superscript_author_byline_refs() -> None:
    html = (
        "<html><body>"
        "<h1>A bioelectric router for adaptive isochronous neurostimulation</h1>"
        "<p>Eashan Sahai¹, Jordan Hickman¹,² &amp; Daniel J. Denman¹⊠</p>"
        "<p>Clinical observations support this model<sup>1</sup>.</p>"
        "<h4>References</h4>"
        "<ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    author_start = polished.index("Eashan Sahai")
    author_block_start = polished.rfind("<p", 0, author_start)
    author_block_end = polished.index("</p>", author_start)
    author_block = polished[author_block_start:author_block_end]
    body_start = polished.index("Clinical observations")

    assert "z2m-front-matter" in author_block
    assert 'href="#ref-' not in author_block
    assert "Eashan Sahai<sup>1</sup>" in author_block
    assert "Jordan Hickman<sup>1,2</sup>" in author_block
    assert "Daniel J. Denman<sup>1</sup>⊠" in author_block
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
        'Gari D. Cliffor <a href="#page-0-0">d1,5</a>, '
        'Amit J. Sha <a href="#page-0-2">h4,6,7</a>, '
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
    assert "Gari D. Clifford<sup>1,5</sup>" in frontmatter
    assert "Amit J. Shah<sup>4,6,7</sup>" in frontmatter
    assert "Daniel Shu Wei Ting<sup>1,2,5</sup>" in frontmatter
    assert "<sup>3</sup>Nuffield Department" in frontmatter
    assert "<sup>10</sup>Academic Ophthalmology" in frontmatter
    assert "<sup>13</sup>Department of Medicine" in frontmatter
    assert 'href="#ref-' not in frontmatter
    assert 'href="#page-' not in frontmatter
    assert 'href="#ref-1"' in polished[frontmatter_end:]
    assert 'href="#ref-2"' in polished[frontmatter_end:]


def test_polish_html_document_repairs_confirmed_front_matter_email_artifacts() -> None:
    html = (
        "<html><body>"
        "<h1>Confirmed front matter repairs</h1>"
        "<p>Department of Industrial Engineering, University of Florence, Italy. "
        "Contacts: lapo.governi@unfi.it, monica.carfagni@unfi.it. "
        "For correspondence Me-mail: michael.deistler@uni-tuebingen.de</p>"
        "<p>The body text begins here.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    frontmatter = polished[: polished.index("The body text begins")]

    assert "Me-mail:" not in frontmatter
    assert "e-mail: michael.deistler@uni-tuebingen.de" in frontmatter
    assert "@unfi.it" not in frontmatter
    assert "lapo.governi@unifi.it" in frontmatter
    assert "monica.carfagni@unifi.it" in frontmatter


def test_polish_html_document_repairs_confirmed_author_marker_runs() -> None:
    html = (
        "<html><body>"
        "<h1>Author marker repairs</h1>"
        '<p>Mehmet <a href="https://pubmed.ncbi.nlm.nih.gov/?term=Keskin">Zeynel Keskin,</a> '
        'Erkin <a href="https://pubmed.ncbi.nlm.nih.gov/?term=Karaca">Karaca</a> , '
        'Murat U\u00e7ar, <a href="https://pubmed.ncbi.nlm.nih.gov/?term=Ate\u015f">Erhan Ate\u015f,</a> '
        'Cem <a href="https://pubmed.ncbi.nlm.nih.gov/?term=Y\u00fccel">Y\u00fccel</a> , and '
        'Yusuf <a href="https://pubmed.ncbi.nlm.nih.gov/?term=\u00d6zlem">\u00d6zlem</a> '
        "\u0130lbey 1 1 2 3 1 1</p>"
        "<h2>Abstract</h2>"
        "<p>The first body sentence follows.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Mehmet Zeynel Keskin<sup>1</sup>" in polished
    assert "Murat U\u00e7ar<sup>2</sup>" in polished
    assert "Erhan Ate\u015f<sup>3</sup>" in polished
    assert "Yusuf \u00d6zlem \u0130lbey<sup>1</sup>" in polished


def test_polish_html_document_repairs_xue_author_markers_without_losing_abstract_tail() -> None:
    html = (
        "<html><body>"
        "<h1>A green approach for ultrasensitive fluorescence detection</h1>"
        "<p>Mingyue Xue, ab Mengbing Zou, Jingjin Zhao, Zhihua Zhan Ab and Shulin Zhao "
        "Zhao A green approach was developed for detection.</p>"
        "<p>The next body sentence follows.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Mingyue Xue<sup>ab</sup>, Mengbing Zou<sup>a</sup>" in polished
    assert "Jingjin Zhao<sup>*a</sup>" in polished
    assert "Zhao Zhao A green approach" not in polished
    assert "A green approach was developed for detection." in polished


def test_polish_html_document_repairs_medical_physics_author_marker_split() -> None:
    html = (
        "<html><body>"
        "<h1>Effects of multispectral fluorescence imaging</h1>"
        "<p>Banghe Zhu, John C. Rasmussen, and Eva M. Sevick-Murac aa) "
        "Center for Molecular Imaging, The Brown Foundation Institute of Molecular Medicine.</p>"
        "<h2>Abstract</h2>"
        "<p>The article body begins.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Eva M. Sevick-Muraca<sup>a)</sup>" in polished
    assert "Eva M. Sevick-Murac aa)" not in polished
    assert "z2m-affiliations" in polished
    assert "<p>The article body begins.</p>" in polished


def test_polish_html_document_repairs_medical_physics_author_marker_line_break() -> None:
    html = (
        "<html><body>"
        "<h1>Intraoperative fluorescence molecular imaging</h1>"
        "<p>Banghe Zhu, John C. Rasmussen, and Eva M. Sevick-Murac \n"
        "    aa)\n"
        "(Received 17 October 2013; revised 5 December 2013.)</p>"
        "<p><b>Purpose:</b> The body starts here.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Eva M. Sevick-Muraca<sup>a)</sup>" in polished
    assert "Sevick-Murac" not in re.sub(r"Sevick-Muraca<sup>a\)</sup>", "", polished)
    assert "(Received 17 October 2013; revised 5 December 2013.)" in polished


def test_polish_html_document_repairs_front_matter_department_affiliation_glue() -> None:
    html = (
        "<html><body>"
        "<h1>A prototype power assist wheelchair</h1>"
        "<p>Richard Simpson*1,2,3, Edmund LoPresti4, Steve Hayashi2</p>"
        "<p><span id=\"page-0-0\"></span>Address: 1Department of Rehabilitation Science and Technology; "
        "University of Pittsburgh, USA 2Human Engineering Research Labs; "
        "VA Pittsburgh Healthcare System, USA, 3Department of Bioengineering; "
        "University of Pittsburgh, USA and 4AT Sciences; Pittsburgh, PA, USA</p>"
        '<p block-type="ListGroup" class="z2m-front-matter"><ul>'
        '<li block-type="ListItem"><i>1Department of Physiology, LLRM Medical College</i></li>'
        '<li block-type="ListItem"><span id="page-1-0"></span>2Department of Bioengineering</li>'
        "</ul></p>"
        "<p>IRCCS San Raffaele Scientific, InstituteDepartment of Obstetrics and Gynecology, Milano</p>"
        "<h2>Abstract</h2>"
        "<p>The wheelchair avoided obstacles during testing.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    frontmatter_end = polished.index("Abstract")
    frontmatter = polished[:frontmatter_end]

    assert "1Department" not in frontmatter
    assert "2Human" not in frontmatter
    assert "3Department" not in frontmatter
    assert "<sup>1</sup>Department of Rehabilitation" in frontmatter
    assert "<sup>2</sup>Human Engineering" in frontmatter
    assert "<sup>3</sup>Department of Bioengineering" in frontmatter
    assert "<sup>1</sup>Department of Physiology" in frontmatter
    assert "<sup>2</sup>Department of Bioengineering" in frontmatter
    assert "Institute Department of Obstetrics" in frontmatter


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


def test_polish_html_document_marks_footnote_range_refs() -> None:
    html = (
        "<html><body>"
        "<p>Several investigators have used the same principle with various refinements.<sup>7-11</sup> "
        "In 1967 a new technique was described.</p>"
        '<p><sup>7</sup> Backman, K. A. and Von Garrelts, B.: Apparatus for recording micturition.</p>'
        '<p><sup>8</sup> Von Garrelts, B.: Analysis of micturition.</p>'
        '<p><sup>9</sup> Kaufman, J. J.: A new recording uroflowmeter.</p>'
        '<p><sup>10</sup> Kaufman, J. J.: Uroflowmetry in urological diagnosis.</p>'
        '<p><sup>11</sup> Klein, G. and Collins, W. E.: A uroflowmeter for clinical use.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="footnote-7"' in polished
    assert 'id="footnote-11"' in polished
    assert '<sup class="z2m-footnote-ref">7-11</sup>' in polished


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
    assert re.search(
        r'<p\b(?=[^>]*\bz2m-missing-figure-warning\b)(?=[^>]*\bz2m-figure-target\b)(?=[^>]*\brole="note")',
        polished,
    )
    assert 'data-z2m-origin="caption-only-target"' in polished
    assert '<p class="z2m-figure-caption">Figure 1. Caption survived, but the image did not.</p>' in polished
    assert "scroll-margin-top" in polished
    assert ":target" in polished


def test_polish_html_document_wraps_accepted_manuscript_figure_placeholder_as_missing_target() -> None:
    html = (
        "<html><body>"
        "<p>The spectral echo analysis is summarized in Figure 1.</p>"
        "<h2>/ FIGURE 1 NEAR HERE /</h2>"
        "<table><tr><th>Figure and table captions</th></tr>"
        "<tr><td>Figure 1. Spectral cues used in the object detection task.</td></tr></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig1_match is not None
    fig1 = fig1_match.group(0)
    assert 'data-z2m-origin="accepted-manuscript-placeholder"' in fig1
    assert "Figure 1 image was not extracted" in fig1
    assert "NEAR HERE" in fig1
    assert 'class="z2m-missing-figure-warning z2m-figure-target"' in fig1
    assert 'href="#fig-1"' in polished


def test_polish_html_document_wraps_slash_only_accepted_manuscript_figure_placeholder() -> None:
    html = (
        "<html><body>"
        "<p>The room impulse response results are shown in Figure 12.</p>"
        "<p>/ FIGURE 12 /</p>"
        "<p>Figure 12</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<div id="fig-12" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">' in polished
    assert 'data-z2m-origin="accepted-manuscript-placeholder"' in polished
    assert 'href="#fig-12"' in polished
    assert polished.count('id="fig-12"') == 1


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


def test_polish_html_document_merges_caption_only_missing_unit_with_previous_image_unit() -> None:
    html = (
        "<html><body>"
        '<p>See <a href="#fig-2" class="z2m-fig-link">Figure 2</a>.</p>'
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-float-run-start">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 1. Overall system description.</p>'
        "</div>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-float-run-mid">'
        '<p><img src="fig2.jpg"/></p>'
        "</div>"
        '<p id="fig-2"><b>Figure 2.</b> Architecture of the system.</p>'
        "<p>Body text resumes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert 'src="fig2.jpg"' in fig2
    assert "Architecture of the system" in fig2
    assert "Figure 2 image was not extracted" not in polished
    assert "z2m-missing-figure-unit" not in fig2
    assert polished.count('id="fig-1"') == 1


def test_polish_html_document_merges_existing_missing_unit_with_previous_duplicate_image_unit() -> None:
    html = (
        "<html><body>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-float-run-start">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption"><b>Figure 1.</b> Overall description.</p>'
        "</div>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-float-run-mid">'
        '<p><img src="fig2.jpg"/></p>'
        "</div>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit z2m-float-run-end">'
        '<p data-z2m-origin="caption-only-target" class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 2 image was not extracted into this HTML. Please check the original PDF for the missing visual content."
        "</p>"
        '<p class="z2m-figure-caption"><b>Figure 2.</b> Architecture of the system.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert 'src="fig2.jpg"' in fig2
    assert "Architecture of the system" in fig2
    assert "Figure 2 image was not extracted" not in polished
    assert "z2m-missing-figure-unit" not in fig2
    assert polished.count('id="fig-1"') == 1


def test_polish_html_document_merges_caption_only_missing_unit_with_previous_table_surrogate() -> None:
    html = (
        "<html><body>"
        '<p><a href="#fig-7" class="z2m-fig-link">Figure 7</a> shows the recommended routes.</p>'
        "<table><tbody>"
        "<tr><th>Recommended:0 times</th><th>many</th></tr>"
        "<tr><td>Recommended:16 times</td><td>few</td></tr>"
        "</tbody></table>"
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p data-z2m-origin="caption-only-target" class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 7 image was not extracted into this HTML. Please check the original PDF for the missing visual content."
        "</p>"
        '<p class="z2m-figure-caption"><b>Figure 7.</b> Identification results by area.</p>'
        "</div>"
        "<p>Body text resumes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig7_match = re.search(r'<div\b(?=[^>]*\bid="fig-7")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig7_match is not None
    fig7 = fig7_match.group(0)
    assert "<table" in fig7
    assert "Recommended:16 times" in fig7
    assert "Identification results by area" in fig7
    assert "z2m-figure-target" in fig7
    assert "Figure 7 image was not extracted" not in polished
    assert "z2m-missing-figure-unit" not in fig7


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


def test_polish_html_document_splits_html_math_tag_equation_from_where_prose() -> None:
    html = (
        '<html><body>'
        '<p block-type="Equation"><math display="block">'
        r"W(n) = 0.5 \left[1 - \cos\left(\frac{2\pi n}{m}\right)\right], "
        r"\ n = 0, 1, \dots, m<sup class=\"z2m-unit-exp\">-1</sup>"
        '</math> (3) where m is the shifting length of the window function. '
        "Figure 2 shows the waveform.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'class="z2m-equation-row"' in polished
    assert '<span class="z2m-eq-num">(3)</span>' in polished
    assert '<p block-type="Text">where m is the shifting length of the window function. Figure 2 shows' in polished
    assert 'block-type="Equation"><math display="block"' in polished
    assert "(3) where m is" not in polished


def test_polish_html_document_does_not_merge_equation_paragraph_with_where_text() -> None:
    html = (
        '<html><body>'
        '<p block-type="Equation"><math display="block">'
        r"W(n) = 0.5 \left[1 - \cos\left(\frac{2\pi n}{m}\right)\right]"
        "</math> (3)</p>"
        '<p block-type="Text">where m is the shifting length of the window function. '
        "Figure 2 shows the waveform.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'class="z2m-equation-row"' in polished
    assert '<span class="z2m-eq-num">(3)</span>' in polished
    assert '<p block-type="Text">where m is the shifting length of the window function. Figure 2 shows' in polished
    assert "(3) where m is" not in polished


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
        '<li><span id="page-4-0"></span>[ <a href="#page-1-10">3]</a> Kruk et al., 2020.</li>'
        '<li><span id="page-4-1"></span><a href="#page-1-11">[4]</a> Popescu et al., 2014.</li>'
        '<li><span id="page-4-2"></span><a href="#page-1-12">[5</a>] Precision Microdrives, 2020.</li>'
        '<li><span id="page-4-3"></span><a href="#page-1-13">[6] S</a> . J. LaGrow, 2011.</li>'
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
    assert "3.</span> Kruk" in ref_section
    assert "4.</span> Popescu" in ref_section
    assert "5.</span> Precision Microdrives" in ref_section
    assert "6.</span> S. J. LaGrow" in ref_section
    assert "6.</span> [6]" not in ref_section
    assert "6.</span> . J. LaGrow" not in ref_section
    assert 'href="#page-1-10"' not in ref_section
    assert 'href="#page-1-11"' not in ref_section
    assert 'href="#page-1-12"' not in ref_section
    assert 'href="#page-1-13"' not in ref_section


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


def test_polish_html_document_splits_collapsed_dot_bulleted_reference_item() -> None:
    html = (
        "<html><body>"
        "<p>Existing RNAs include guide-dogs [2, 3] and GPS-based aids [7, 8].</p>"
        "<h4>References</h4>"
        '<p block-type="ListGroup"><ul>'
        '<li block-type="ListItem">1. . Galindo C, et al., "Control Architecture," IEEE, 2006. '
        '. Ulrich I and Borenstein J, "The GuideCane," IEEE, 2001. '
        '. Kulyukin V, et al., "Robot-Assisted Wayfinding," Autonomous Robots, 2006. '
        '. Bissit D and Heyes A, "Biofeedback in Rehabilitation," Ergonomics, 1980. '
        '. Benjamin JM, Ali NA, and Schepis AF, "A Laser Cane for the Blind," 1973. '
        '. Yuan D and Manduchi R, "A Tool for Range Sensing," CVPR Workshops, 2004. '
        '. Balachandran W, Cecelja F, and Ptasinski P, "A GPS Based Navigation Aid," 2003. '
        '. Wilson J, et al., "SWAN," Wearable Comput., 2007.</li>'
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    ref_section = polished[polished.index("References"):]

    assert '<li block-type="ListItem" id="ref-8">' in ref_section
    assert '<span class="z2m-ref-num">8.</span> Wilson J' in ref_section
    assert '[<a href="#ref-2" class="z2m-ref-link">2</a>, <a href="#ref-3" class="z2m-ref-link">3</a>]' in body
    assert '[<a href="#ref-7" class="z2m-ref-link">7</a>, <a href="#ref-8" class="z2m-ref-link">8</a>]' in body


def test_polish_html_document_splits_implicit_reference_before_number_gap() -> None:
    html = (
        "<html><body>"
        "<p>Electronic canes are compared in prior work [23, 24].</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>22. Buchs, G.; Simon, N.; Maidenbaum, S.; Amedi, A. Waist-up Protection for Blind Individuals. "
        "<i>Restor. Neurol. Neurosci.</i> <b>2017</b>, <i>35</i>, 225-235. "
        '<a href="http://dx.doi.org/10.3233/RNN-160686">[CrossRef]</a> '
        "dos Santos, A.D.P.; Medola, F.O.; Cinelli, M.J.; Garcia Ramirez, A.R.; Sandnes, F.E. "
        "Are Electronic White Canes Better than Traditional Canes? <i>Univ. Access Inf. Soc.</i> "
        "<b>2021</b>, <i>20</i>, 93-103. "
        '<a href="http://dx.doi.org/10.1007/s10209-020-00712-z">[CrossRef]</a></li>'
        "<li>24. Dakopoulos, D.; Bourbakis, N.G. Wearable Obstacle Avoidance Electronic Travel Aids. "
        "<i>IEEE Trans. Syst.</i> <b>2010</b>, <i>40</i>, 25-35.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    ref22 = re.search(r'<li id="ref-22"[\s\S]*?</li>', polished)

    assert ref22 is not None
    assert "dos Santos" not in ref22.group(0)
    assert re.search(r'<li id="ref-23"[\s\S]{0,180}dos Santos', polished) is not None
    assert re.search(r'<li id="ref-24"[\s\S]{0,180}Dakopoulos', polished) is not None
    assert '<a href="#ref-23" class="z2m-ref-link">23</a>' in body
    assert '<a href="#ref-24" class="z2m-ref-link">24</a>' in body


def test_polish_html_document_splits_implicit_reference_after_medline_link() -> None:
    html = (
        "<html><body>"
        "<p>Biomechanical analysis is used in rehabilitation [23, 24].</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>22. Kober SE, Wood G, Hofer D, Kreuzig W, Kiefer M, Neuper C. "
        "Virtual reality in neurologic rehabilitation of spatial disorientation. "
        "J Neuroeng Rehabil 2013 Feb 08;10:17. "
        '<a href="http://www.ncbi.nlm.nih.gov/pubmed/23394289">[Medline: 23394289]</a> '
        "van den Bogert AJ, Geijtenbeek T, Even-Zohar O, Steenbrink F, Hardin EC. "
        "A real-time system for biomechanical analysis of human movement and muscle function. "
        "Med Biol Eng Comput 2013 Oct;51(10):1069-1077. "
        '<a href="http://www.ncbi.nlm.nih.gov/pubmed/23884905">[Medline: 23884905]</a></li>'
        "<li>24. de Rooij IJM, van de Port IGL, Visser-Meily JMA, Meijer JG. "
        "Virtual reality gait training versus non-virtual reality gait training. Trials 2019;20:89.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    ref22 = re.search(r'<li id="ref-22"[\s\S]*?</li>', polished)

    assert ref22 is not None
    assert "van den Bogert" not in ref22.group(0)
    assert re.search(r'<li id="ref-23"[\s\S]{0,180}van den Bogert', polished) is not None
    assert re.search(r'<li id="ref-24"[\s\S]{0,180}de Rooij', polished) is not None
    assert '<a href="#ref-23" class="z2m-ref-link">23</a>' in body
    assert '<a href="#ref-24" class="z2m-ref-link">24</a>' in body


def test_polish_html_document_splits_numbered_institutional_reference_tail() -> None:
    html = (
        "<html><body>"
        "<p>Museum accessibility programs are summarized in prior work [12, 13].</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>11. Museo del Prado. Touching the Prado. Available online: "
        '<a href="https://www.museodelprado.es/en/touching-the-prado">https://example.test/prado</a> '
        "(accessed on 9 November 2020). 12. The Andy Warhol Museum. Available online: "
        '<a href="https://www.warhol.org/accessibility-accommodations/">https://example.test/warhol</a> '
        "(accessed on 9 November 2020).</li>"
        "<li>13. Candlin, F. The dubious inheritance of touch. <i>J. Vis. Culture</i> <b>2006</b>.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert re.search(r'<li id="ref-12"[\s\S]{0,180}Andy Warhol Museum', polished) is not None
    assert re.search(r'<li id="ref-13"[\s\S]{0,180}Candlin', polished) is not None
    assert '<a href="#ref-12" class="z2m-ref-link">12</a>' in body
    assert '<a href="#ref-13" class="z2m-ref-link">13</a>' in body


def test_polish_html_document_keeps_short_dot_separator_reference_item_unsplit() -> None:
    html = (
        "<html><body>"
        "<p>See [1] for details.</p>"
        "<h4>References</h4>"
        "<ul>"
        '<li>1. Smith J, "One reference with preserved OCR dots" . Available online. '
        ". Retrieved 2024.</li>"
        "</ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References"):]

    assert ref_section.count("<li") == 1
    assert 'id="ref-2"' not in ref_section


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


def test_polish_html_document_splits_zotero_reference_tail_from_backmatter_paragraph() -> None:
    html = (
        "<html><body>"
        "<p>Brainstem stroke communication was difficult 1,2.</p>"
        "<h2>Declaration of interests</h2>"
        '<p block-type="Text">The center has a research agreement; cha '
        '<a href="https://www.zotero.org/google-docs/?abc">1</a> '
        '<a href="https://www.zotero.org/google-docs/?abc">Searls DE, Pazdera L, Korbel E, Vysata O, Caplan LR.</a> '
        '<a href="https://www.zotero.org/google-docs/?abc">Symptoms and Signs of Posterior Circulation Ischemia.</a> '
        "<i>Arch Neurol</i> 2012; <b>69</b>: 346-51.</p>"
        '<p block-type="ListGroup" class="has-continuation"><ul>'
        '<li block-type="ListItem"><a href="https://www.zotero.org/google-docs/?abc">2</a> '
        '<a href="https://www.zotero.org/google-docs/?abc">Teasell R, Foley N, Doherty T, Finestone H.</a> '
        "<i>Arch Phys Med Rehabil</i> 2002; <b>83</b>: 1013-6.</li>"
        '<li block-type="ListItem"><a href="https://www.zotero.org/google-docs/?abc">3</a> '
        '<a href="https://www.zotero.org/google-docs/?abc">Stavisky SD. Restoring Speech Using Brain-Computer Interfaces.</a> '
        "<i>Annu Rev Biomed Eng</i> 2025; <b>27</b>: 29-54.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    ref_section = polished[polished.index("References") :]
    body = polished[: polished.index("References")]

    assert 'id="ref-1"' in ref_section
    assert 'id="ref-2"' in ref_section
    assert 'id="ref-3"' in ref_section
    assert "zotero.org/google-docs" not in ref_section
    assert '<a href="#ref-1" class="z2m-ref-link">1</a>' in body
    assert '<a href="#ref-2" class="z2m-ref-link">2</a>' in body


def test_polish_html_document_splits_embedded_reference_list_after_conclusion_items() -> None:
    html = (
        "<html><body>"
        "<p>The widely held opinion 1-3 that Galilean systems are unsuitable is incorrect.</p>"
        "<h4>CONCLUSION</h4>"
        "<p>1. When working in twilight, mark brightness must be adjusted.</p>"
        '<p block-type="ListGroup"><ul>'
        "<li>2. When minimizing weight and size outweighs other requirements, "
        "preference can be given to a Galilean viewfinder.</li>"
        "<li>1A. I. Tudorovski, <i>Theory of Optical Devices</i>, part 2 (Akad. Nauk SSSR, Moscow, 1952).</li>"
        "<li>2G. G. Slyusarev, <i>Calculations for Optical Systems</i> (Mashinostroenie, Leningrad, 1975).</li>"
        "<li>3V. N. Churilovski, <i>Theory of Optical Devices</i> (Mashinostroenie, Moscow, 1966).</li>"
        "<li><sup>4</sup> I. A. Turygin, <i>Applied Optics</i> (Mashinostroenie, Moscow, 1965).</li>"
        "<li>5B. N. Begunov and N. P. Zakaznov, <i>The Theory of Optical Systems</i> (Moscow, 1973).</li>"
        "<li>6M. I. Apenko and A. S. Dubovik, <i>Applied Optics</i> (Nauka, Moscow, 1971). "
        "7M. M. Rusinov, <i>The Makeup of Optical Systems</i> (Leningrad, 1989).</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    conclusion = polished[polished.index("CONCLUSION") : polished.index("References")]
    ref_section = polished[polished.index("References") :]
    body = polished[: polished.index("CONCLUSION")]

    assert "preference can be given to a Galilean viewfinder" in conclusion
    assert 'id="ref-2"' not in conclusion
    for ref_id in range(1, 8):
        assert f'id="ref-{ref_id}"' in ref_section
    assert "Rusinov" in re.search(r'<li id="ref-7"[\s\S]*?</li>', ref_section).group(0)
    assert 'href="#ref-1"' in body
    assert 'href="#ref-3"' in body


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


def test_polish_html_document_trims_adjacent_article_after_references() -> None:
    html = (
        "<html><body>"
        "<h2>'Braille' reading by a blind volunteer by visual cortex stimulation</h2>"
        "<p>Received October 20; accepted November 4, 1975.</p>"
        '<p block-type="ListGroup" class="z2m-front-matter"><ul>'
        "<li>Brindley, G. S., and Lewin, W., J. Physiol., Lond., 196, 479-493 (1968). "
        "Brindley, G. S., Handbook of Sensory Physiology, 7, 583-594 "
        "(Springer-Verlag, New York, 1973). Dobelle, W. H., Science, 183, 440-444 (1974). "
        "Mladejovsky, M. G., Dobelle, W. H., and Brackmann, D. E., "
        "Trans. Am. Soc. Artif. Int. Organs, 21, 1-6 (1975).</li>"
        "</ul></p>"
        "<h2><b>Ethylene-induced volatile</b> inhibitors causing soil fungistasis</h2>"
        "<p>THE phenomenon of soil fungistasis<sup>1-3</sup> was described elsewhere.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Mladejovsky" in polished
    assert "Ethylene-induced" not in polished
    assert "fungistasis" not in polished
    assert polished.rstrip().endswith("</body></html>")


def test_polish_html_document_keeps_reference_list_continuation_after_heading() -> None:
    filler = " ".join(["Body prose before references."] * 80)
    html = (
        "<html><body>"
        f"<p>{filler}</p>"
        "<h2>References</h2>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>1. Arago, F. Journal of Applied Photography, 1839, 9, 824.</li>"
        "<li>2. Barger, M. S. and White, W. B. University Press, 2000.</li>"
        "</ul></p>"
        "<h2>Robinson and Vicenzi Southworth and Hawes Daguerreotypes</h2>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>3. Robinson, M. Journal of Photographic History, 2008, 12, 55.</li>"
        "<li>4. Romer, G. Science and Photography Press, 2014.</li>"
        "</ul></p>"
        "<h1>Bibliography</h1>"
        "<p block-type=\"ListGroup\"><ul>"
        "<li>5. Wood, J. The Daguerreotype. University of Iowa Press, 1989.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Southworth and Hawes Daguerreotypes" in polished
    assert "Journal of Photographic History" in polished
    assert "The Daguerreotype" in polished
    assert 'id="ref-3"' in polished
    assert 'id="ref-5"' in polished


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


def test_polish_html_document_moves_leading_paren_out_of_ref_link_label() -> None:
    html = (
        "<html><body>"
        '<p>We saw the same pattern in Extended Data Fig. 6 '
        '<a href="#ref-2" class="z2m-ref-link">)2</a>.</p>'
        "<h4>References</h4>"
        "<ul><li>One.</li><li>Two.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert ')<a href="#ref-2" class="z2m-ref-link">2</a>.' in body
    assert ')2</a>' not in body


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
        "<p>The floor covered 60m2, the field covered 1.73 m2, and the maze covered 8 × 4 m 2.</p>"
        "<p>The M2 occlusion and 350M 2 model label are not square-meter units.</p>"
        "<p>The grating covered 1.5 ◦ × 1.5 ◦ and was baked at 200 ◦ C.</p>"
        "<p>The window covered 1.5 <i>◦ ×</i> 1.5 <i>◦</i> and was baked at 350 <i>◦</i> C.</p>"
        '<p>Conductivity <a href="#ref-215">12.6 mS cm </a> − 1 at −40 C.</p>'
        "<p>The map devoted cortex to representation of 1 <b>◦</b> of visual space.</p>"
        "<p>Luminance was 30.3 c d m − 2 and 16.8 cd m − 2.</p>"
        "<p>The tactile map covered 1,200 <i> m </i> <sup> 2 </sup> and 400 <i>m</i><sup>2</sup>.</p>"
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
    assert '60 m<sup class="z2m-unit-exp">2</sup>' in polished
    assert '1.73 m<sup class="z2m-unit-exp">2</sup>' in polished
    assert '8 × 4 m<sup class="z2m-unit-exp">2</sup>' in polished
    assert "M2 occlusion" in polished
    assert "350M 2 model label" in polished
    assert "1.5° × 1.5°" in polished
    assert "200°C" in polished
    assert "350°C" in polished
    assert "<i>◦" not in polished
    assert '12.6 mS cm<sup class="z2m-unit-exp">-1</sup></a> at −40 C' in polished
    assert "1° of visual space" in polished
    assert '30.3 cd m<sup class="z2m-unit-exp">-2</sup>' in polished
    assert '16.8 cd m<sup class="z2m-unit-exp">-2</sup>' in polished
    assert '1,200 m<sup class="z2m-unit-exp">2</sup>' in polished
    assert '400 m<sup class="z2m-unit-exp">2</sup>' in polished
    assert "c d m" not in polished
    assert "<b>◦" not in polished


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


def test_polish_html_document_repairs_known_table_ocr_artifacts() -> None:
    html = (
        "<html><body>"
        "<p class=\"z2m-table-caption\">TABLE 1. Female descriptive statistics of different methods.</p>"
        "<table><tbody>"
        "<tr><th></th><th> nales <br/> an ±sD </th><th> Calcula <br/> Flow </th>"
        "<th> Qn <br/> Flow i </th><th> nax <br/> ndexes </th></tr>"
        "<tr><th>age</th><th>Actual Qavg</th><th>actual Qmax</th><th>VV</th><th>PVR</th></tr>"
        "</tbody></table>"
        "<table><tbody><tr><th><b>Collodion Prints</b></th><th> S </th></tr>"
        "<tr><th>Process</th><th>Surface Coating</th></tr><tr><td>Wothlytype</td><td>X</td></tr></tbody></table>"
        "<table><tbody><tr><th>MENDATION <br/> QUESTIONNAIRE - <br/> M <br/> RECO</th>"
        "<th>QUESTIONNAIRE <br/> TYPE OF</th><th>REFERENCES</th><th>W TO GET IT <br/> HO</th></tr></tbody></table>"
        "<table><tbody><tr><th>MS <br/> MPTO <br/> SY</th>"
        "<th>MENDATION <br/> QUESTIONNAIRE - <br/> M <br/> RECO</th>"
        "<th>QUESTIONNAIRE <br/> TYPE OF</th><th>REFERENCES</th><th>W TO GET IT <br/> HO</th></tr></tbody></table>"
        "<p>T a bl e 2 1 con t' �nue d)</p>"
        "<p>HE�LTHY SUBJECT 11 ME�SUREMENT 32 SER I �L NBR . 1802</p>"
        "<table><tbody><tr><td>Gartenfreund: Exploring the botanical garden with an enclusive app</td></tr></tbody></table>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "nales" not in polished
    assert "Qn <br/> Flow i" not in polished
    assert "Actual Qavg" in polished
    assert "Collodion Prints" in polished
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", polished))
    assert "Collodion Prints S Process" not in visible
    assert "SYMPTOMS QUESTIONNAIRE - RECOMMENDATION" in polished
    assert "<th>SYMPTOMS</th>" in polished
    assert "TYPE OF QUESTIONNAIRE" in polished
    assert "HOW TO GET IT" in polished
    assert "MENDATION <br" not in polished
    assert "MS <br/> MPTO" not in polished
    assert "M <br/> RECO" not in polished
    assert "Table 2.1 (continued)" in polished
    assert "T a bl e" not in polished
    assert "HEALTHY SUBJECT 11 MEASUREMENT 32 SERIAL-NBR. 1802" in polished
    assert "HE�LTHY" not in polished
    assert "inclusive app" in polished
    assert "enclusive app" not in polished


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
        "<p>where k is found to be 0.5 mL s-1 mm-1.</p>"
        "<p>Scan velocity was 1 cm s <sup> − </sup> <sup> 1 </sup> and 130000 M <sup> − </sup> <sup> 1 </sup>.</p>"
        "<h4>References</h4><ul><li>Ref one.</li><li>Ref two.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")

    assert 'µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert 'mg kg<sup class="z2m-unit-exp">-1</sup> h<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'cd m<sup class="z2m-unit-exp">-2</sup>' in polished
    assert 'mm s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert '0.5 mL s<sup class="z2m-unit-exp">-1</sup> mm<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'cm s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'M<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'href="#ref-1"' not in polished
    assert 'href="#ref-2"' not in polished


def test_polish_html_document_repairs_already_linked_unit_exponent() -> None:
    html = (
        "<html><body>"
        '<p>Insertion velocity was 0.01 mm s <i>−</i> '
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>Dissolution was ~20 nm d<sup>-<a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>Doping was 10<sup>20</sup> cm<sup>-<a href="#ref-3" class="z2m-ref-link">3</a></sup>.</p>'
        '<p>Dose was 4.25 mg·kg<sup>-<a href="#ref-1" class="z2m-ref-link">1</a></sup>·'
        'h<sup>-<a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>Resistance was dyne sec cm<sup>-<a href="#ref-5" class="z2m-ref-link">5</a></sup>.</p>'
        '<p>Cycling rate was maintained at 60 revolutionsmin <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>Cardiac output was reported in L min <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        '<p>Bending stiffness was 3.3 × 10−12 N <a href="#ref-2" class="z2m-ref-link">m2</a>.</p>'
        '<p>Electrode sites had areas of 14 × 24 µm <a href="#ref-2" class="z2m-ref-link">2</a>.</p>'
        "<h4>References</h4><ul><li>Ref one.</li><li>Ref two.</li><li>Ref three.</li><li>Ref four.</li><li>Ref five.</li></ul>"
        "</body></html>"
    )
    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'mm s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'nm d<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'cm<sup class="z2m-unit-exp">-3</sup>' in polished
    assert 'kg<sup class="z2m-unit-exp">-1</sup>·h<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'dyne sec cm<sup class="z2m-unit-exp">-5</sup>' in polished
    assert 'revolutions min<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'L min<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'N m<sup class="z2m-unit-exp">2</sup>' in polished
    assert 'µm<sup class="z2m-unit-exp">2</sup>' in polished
    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-5"' not in body


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


def test_add_figure_anchors_handles_roman_one_ocr_caption() -> None:
    html = '<p><img src="trial-design.jpg"/></p><p>Figure I Design of the trial.</p>'
    result, found = _add_figure_anchors(html)

    assert found == {"1"}
    assert 'id="fig-1"' in result
    assert 'class="z2m-figure-target"' in result


def test_add_figure_anchors_ignores_roman_one_body_sentence() -> None:
    html = "<p>Figure I shows the design of the trial.</p>"
    result, found = _add_figure_anchors(html)

    assert found == set()
    assert 'id="fig-1"' not in result


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


def test_add_figure_anchors_handles_supplementary_caption_label() -> None:
    html = '<p><b>Supplementary Figure 11</b> . Effect of the sensing condition.</p>'
    result, found = _add_figure_anchors(html)

    assert found == {"supplementary-11"}
    assert 'id="fig-supplementary-11"' in result


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


def test_link_figure_refs_links_chapter_local_panel_ref_from_section_context() -> None:
    html = (
        '<h3 id="section-2-4-3">2.4.3. Discussion</h3>'
        "<p>The CED output in the plain environment (Figure 4B) matched the target.</p>"
    )

    linked = _link_figure_refs(html, {"2-4", "3-4", "4-1"})

    assert '<a href="#fig-2-4" class="z2m-fig-link">Figure\xa04B</a>' in linked
    assert 'href="#fig-4"' not in linked


def test_link_figure_refs_does_not_link_chapter_local_panel_without_section_context() -> None:
    html = "<p>The CED output in the plain environment (Figure 4B) matched the target.</p>"

    linked = _link_figure_refs(html, {"2-4", "3-4", "4-1"})

    assert "z2m-fig-link" not in linked
    assert "Figure 4B" in linked


def test_link_figure_refs_links_supplementary_refs_to_supplementary_targets() -> None:
    html = "<p>See Supplementary Figure 11 and Figure 11 for the paired controls.</p>"
    linked = _link_figure_refs(html, {"supplementary-11", "11"})

    assert '<a href="#fig-supplementary-11" class="z2m-fig-link">Supplementary Figure\xa011</a>' in linked
    assert '<a href="#fig-11" class="z2m-fig-link">Figure\xa011</a>' in linked


def test_link_figure_refs_wraps_plural_multipanel_refs() -> None:
    html = "<p>The lack of distortion (figures 4(A), (B)) suggests stable shape.</p>"
    linked = _link_figure_refs(html, {"4"})
    assert 'href="#fig-4"' in linked
    assert "figures\xa04" in linked


def test_link_figure_refs_wraps_spaced_singular_multipanel_refs() -> None:
    html = "<p>The previous task (figure 7 (a), (c) and table 4) was reused.</p>"
    linked = _link_figure_refs(html, {"7"})
    assert '<a href="#fig-7" class="z2m-fig-link">figure\xa07</a> (a), (c)' in linked


def test_polish_html_document_relinks_spaced_multipanel_refs_after_float_targets() -> None:
    html = (
        "<html><body>"
        "<p>Ref (figure \n    7 (a), (c)\n    and table 4).</p>"
        "<p><img src=x.jpeg/></p>"
        "<p><span id=page-7-0></span><b>FIGURE 7.</b> Caption.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-7"' in polished
    assert '<a href="#fig-7" class="z2m-fig-link">figure\xa07</a> (a), (c)' in polished


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


def test_repair_figure_ref_links_misclassified_as_refs_retargets_plural_figure_list() -> None:
    html = (
        '<p>The limit is evident from figures '
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> and '
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a></sup>. '
        'Prior work<sup><a href="#ref-9" class="z2m-ref-link">9</a></sup> remains a citation.</p>'
    )

    repaired = _repair_figure_ref_links_misclassified_as_refs(html, {"3", "4"})

    assert 'figures <a href="#fig-3" class="z2m-fig-link">3</a> and ' in repaired
    assert '<a href="#fig-4" class="z2m-fig-link">4</a>' in repaired
    assert '<sup><a href="#fig-3"' not in repaired
    assert '<sup><a href="#fig-4"' not in repaired
    assert 'href="#ref-9" class="z2m-ref-link"' in repaired


def test_polish_html_document_repairs_plural_figure_list_false_ref_links() -> None:
    html = (
        "<html><body>"
        '<p>There is a hardware limit (evident from figures '
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> and '
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a></sup>).</p>'
        "<p>Figure 3. Full target coverage.</p>"
        "<p>Figure 4. Inner target coverage.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 5))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'figures <a href="#fig-3" class="z2m-fig-link">3</a> and ' in body
    assert '<a href="#fig-4" class="z2m-fig-link">4</a>' in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-4"' not in body


def test_polish_html_document_unlinks_electrode_pair_false_ref_links() -> None:
    html = (
        "<html><body>"
        "<p>The impedance between electrodes "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> and '
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> '
        "then produces a voltage. Prior work"
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a></sup> remains cited.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 5))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "between electrodes 2 and 3 then produces" in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-4" class="z2m-ref-link"' in body


def test_polish_html_document_unlinks_electrode_pair_with_plain_second_label() -> None:
    html = (
        "<html><body>"
        "<p>Z0 = basic impedance (Ohm) between the two inner electrodes "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> and 3</p>'
        "<p>Prior work"
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a></sup> remains cited.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 5))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "between the two inner electrodes 2 and 3" in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-4" class="z2m-ref-link"' in body


def test_repair_sup_figure_chain_continuations_links_decimal_comma_sup() -> None:
    html = (
        '<p>shown in <a href="#fig-3-15" class="z2m-fig-link">Figure 3.15</a> '
        'and <sup>3,16</sup>, were calculated.</p>'
    )

    repaired = _repair_sup_figure_chain_continuations(html, {"3-15", "3-16"})

    assert '<a href="#fig-3-16" class="z2m-fig-link">3.16</a>' in repaired
    assert "<sup>3,16</sup>" not in repaired


def test_polish_html_document_links_decimal_comma_sup_figure_chain() -> None:
    html = (
        "<html><body>"
        "<p>The correlation shown in Figure 3.15 and <sup>3,16</sup>, was calculated.</p>"
        "<p>Figure 3.15. Velocity plot.</p>"
        "<p>Figure 3.16. Impedance plot.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<a href="#fig-3-15" class="z2m-fig-link">Figure\xa03.15</a>' in polished
    assert '<a href="#fig-3-16" class="z2m-fig-link">3.16</a>' in polished
    assert "<sup>3,16</sup>" not in polished


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

    assert re.search(r'<div id="fig-1" class="[^"]*\bz2m-float-unit\b[^"]*\bz2m-figure-unit\b', polished)
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


def test_polish_html_document_recovers_picture_orphan_with_consecutive_alias_refs() -> None:
    html = (
        "<html><body>"
        '<p><img src="_page_4_Picture_2.jpeg"/></p>'
        "<h2>Results</h2>"
        "<p>Participants completed the two obstacle courses shown in Figure 6 and Figure 7.</p>"
        '<p><img src="_page_5_Figure_2.jpeg"/></p>'
        "<p>Figure 8. Collisions for able-bodied participants.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig6_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-6")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig6_match is not None
    fig6 = fig6_match.group(0)
    assert '_page_4_Picture_2.jpeg' in fig6
    assert 'id="fig-7"' not in fig6
    alias = '<span id="fig-7" class="z2m-float-alias" data-z2m-origin="orphan-image-ref"></span>'
    assert alias in polished
    assert polished.index(alias) < polished.index('id="fig-6"')
    assert not re.search(r'<div\b(?=[^>]*\bid="fig-7")(?=[^>]*\bz2m-figure-unit\b)', polished)
    assert 'href="#fig-6"' in polished
    assert 'href="#fig-7"' in polished


def test_polish_html_document_does_not_assign_page_zero_picture_from_later_refs() -> None:
    html = (
        "<html><body>"
        '<p><img src="_page_0_Picture_17.jpeg"/></p>'
        "<p>Visual field testing was abnormal (Figure 1). "
        "The fundal examination was normal (Figure 2), and OCT showed edema (Figure 3).</p>"
        '<p><img src="_page_2_Figure_1.jpeg"/></p>'
        "<p>Figure 4. Eye position photography before surgery.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    logo_unit = re.search(
        r'<div\b(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?_page_0_Picture_17\.jpeg[\s\S]*?</div>',
        polished,
    )
    assert logo_unit is None
    assert 'href="#fig-1"' not in polished
    assert 'href="#fig-2"' not in polished
    assert 'href="#fig-3"' not in polished
    assert re.search(r'<div\b(?=[^>]*\bid="fig-4")(?=[^>]*\bz2m-figure-unit\b)', polished)


def test_polish_html_document_recovers_page_id_picture_orphan_after_known_figure() -> None:
    html = (
        "<html><body>"
        "<p>The results shown in Figure 10 show robust hand detection. Figure 11 also demonstrates pointing.</p>"
        '<p><img src="_page_11_Figure_1.jpeg"/></p>'
        "<p>Figure 11. Results of finger pointing estimation with dynamic backgrounds.</p>"
        '<p id="page-11-1"><img src="_page_11_Picture_4.jpeg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig10_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-10")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig10_match is not None
    assert '_page_11_Picture_4.jpeg' in fig10_match.group(0)
    assert '<span id="page-11-1"></span>' in polished
    assert 'href="#fig-10"' in polished
    assert 'href="#fig-11"' in polished


def test_polish_html_document_recovers_multipart_picture_orphan_from_preceding_ref() -> None:
    html = (
        "<html><body>"
        "<p>Figure 16 shows a snapshot of one user using the proposed system during the field test. "
        "As seen in Figure 16b, the system required entering the destination through speech.</p>"
        "<p>Some ethical issues regarding this study should be mentioned.</p>"
        '<p id="page-24-0"><img src="_page_24_Picture_2.jpeg"/></p>'
        '<p><img src="_page_24_Picture_3.jpeg"/></p>'
        "<p>proposed system; (b) Screen of the proposed wayfinding system. "
        "Figure 16. A user performing the initial tasks: (a) A user is moving according to guidance; "
        "(b) Screen of the proposed wayfinding system.</p>"
        "<p>Figure 17 shows the test maps constructed for the field tests.</p>"
        '<p><img src="_page_25_Figure_1.jpeg"/></p>'
        "<p>Figure 17. Test maps constructed for real environments.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig16_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-16")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig16_match is not None
    fig16 = fig16_match.group(0)
    assert '_page_24_Picture_2.jpeg' in fig16
    assert '_page_24_Picture_3.jpeg' in fig16
    assert 'href="#fig-16"' in polished
    assert 'href="#fig-17"' in polished


def test_polish_html_document_recovers_orphan_figure_from_terminal_ref_after_heading() -> None:
    html = (
        "<html><body>"
        '<p><img src="_page_14_Figure_8.jpeg"/></p>'
        "<p>Spatial and temporal codes can stimulate specific retinal cells.</p>"
        "<p>Current printing technology can produce conical electrodes.</p>"
        '<h4>5.2 "Eye in Eye" based on reflection</h4>'
        "<p>The device projects colored light into the fovea, as shown in Figure 9. "
        "Its micro-display supports flexible adjustment.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig9_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-9")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig9_match is not None
    assert '_page_14_Figure_8.jpeg' in fig9_match.group(0)
    assert "Figure 9 image was not extracted" not in polished


def test_polish_html_document_does_not_split_chapter_style_terminal_ref_as_integer() -> None:
    html = (
        "<html><body>"
        '<p><img src="_page_183_Figure_0.jpeg"/></p>'
        "<p>The relationship between multiphasicity and V is summarized in Figure 8.14.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig814_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-8-14")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig814_match is not None
    assert '_page_183_Figure_0.jpeg' in fig814_match.group(0)
    assert 'id="fig-8"' not in polished


def test_late_recover_orphan_figure_links_after_float_cleanup() -> None:
    html = (
        "<html><body>"
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="_page_5_Figure_2.jpeg"/></p>'
        '<p class="z2m-figure-caption"><b>Figure 6.</b> Prior estimate.</p>'
        "</div>"
        '<p block-type="Text">Figure 7 shows a case example with the complete evolution of '
        "relative accelerations.</p>"
        '<p><img src="_page_5_Figure_5.jpeg"/></p>'
        '<p><img src="_page_5_Figure_6.jpeg"/></p>'
        '<p block-type="Text">Table 1 shows positions defined in Figure 7.</p>'
        '<div id="table-1" class="z2m-float-unit z2m-table-unit">'
        '<p class="z2m-table-caption">Table 1. Detail of positions.</p>'
        "<table><tr><td>A</td></tr></table>"
        "</div>"
        "</body></html>"
    )

    recovered = _late_recover_orphan_figure_anchors_and_links(html)

    fig7_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-7")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        recovered,
    )
    assert fig7_match is not None
    fig7 = fig7_match.group(0)
    assert 'src="_page_5_Figure_5.jpeg"' in fig7
    assert 'src="_page_5_Figure_6.jpeg"' in fig7
    assert '<a href="#fig-7" class="z2m-fig-link">Figure\xa07</a> shows' in recovered
    assert 'defined in <a href="#fig-7" class="z2m-fig-link">Figure\xa07</a>' in recovered


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


def test_polish_html_document_repairs_sentence_split_by_table_with_abbreviation_note() -> None:
    html = (
        "<html><body>"
        "<p>The postoperative angle was different in each group, but there was no significant</p>"
        '<span id="page-5-0"> </span>'
        "<table><tbody><tr><th>Group</th><th>Value</th></tr><tr><td>A</td><td>1</td></tr></tbody></table>"
        "<p>Abbreviation: HKAA, hip-knee-ankle angle.</p>"
        "<table><tbody><tr><th>Group</th><th>mMPTA</th></tr><tr><td>B</td><td>2</td></tr></tbody></table>"
        "<p>difference between the two groups before and after surgery.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "there was no significant difference between the two groups" in compact
    assert "there was no significant</p>" not in polished


def test_repair_sentence_breaks_around_float_units_allows_math_heavy_paragraphs() -> None:
    katex_bloat = '<span class="katex-html">' + ("<span></span>" * 900) + "</span>"
    html = (
        "<html><body>"
        f"<p>For each image P_i, eccentricity r_i = x_i + 2x_i^2 with{katex_bloat}</p>"
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig6.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 6. Prior experiment.</p>'
        "</div>"
        "<p>x_i ~ U(0, 1) and size sigma_i = 2r_i + 1.</p>"
        "</body></html>"
    )

    repaired, count = _repair_sentence_breaks_around_float_units(html)
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", repaired))

    assert count == 1
    assert "with x_i ~ U(0, 1)" in visible
    assert "with</p>" not in repaired


def test_polish_html_document_repairs_math_split_after_katex_render() -> None:
    html = (
        "<html><body>"
        "<p>For each image \\(P_i\\), eccentricity \\(r_i = x_i + 2x_i^2\\) with</p>"
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig6.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 6. Prior experiment.</p>'
        "</div>"
        "<p>\\(x_i \\sim U(0, 1)\\) and size \\(\\sigma_i = 2r_i + 1\\).</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    with_idx = polished.index("with")

    assert polished.find('data-z2m-tex="\\(x_i', with_idx, with_idx + 9000) != -1
    assert re.search(r"with\s*</p>\s*<div\b[^>]*\bid=\"fig-6\"", polished) is None


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


def test_polish_html_document_unwraps_late_split_see_page_anchor_tail() -> None:
    html = (
        "<html><body>"
        '<span id="page-13-0"></span>'
        '<p class="z2m-front-matter">Competing interest: '
        '<a href="#page-13-0">See</a><a href="#page-13-0">page 14</a> '
        'of the <a href="http://creativecommons.org/licenses/by/4.0/">Creative Commons</a> '
        "Attribution License.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count('href="#page-13-0"') == 1
    assert "page 14 of the" in re.sub(r"\s+", " ", polished)


def test_polish_html_document_does_not_move_license_tail_into_competing_interest() -> None:
    html = (
        "<html><body>"
        '<span id="page-13-0"></span>'
        '<span id="page-14-0"></span>'
        "<p>None of the technologies available</p>"
        '<p class="z2m-front-matter">*For correspondence: meister@caltech.edu</p>'
        '<p>Competing interest: <a href="#page-13-0">See</a> '
        '<a href="#page-13-0">page 14</a></p>'
        '<p>Funding: <a href="#page-14-0">See page 15</a> today deliver the high data rate.</p>'
        '<p class="z2m-front-matter">Received: 24 April 2018 Accepted: 27 October 2018</p>'
        '<p class="z2m-front-matter">Reviewing editor: Fred Rieke, University of Washington</p>'
        '<p class="z2m-front-matter">Copyright Liu et al. '
        "This article is distributed under the terms of the "
        '<a href="http://creativecommons.org/licenses/by/4.0/">Creative Commons</a> '
        '<a href="http://creativecommons.org/licenses/by/4.0/">Attribution License,</a> '
        "which permits unrestricted use and redistribution.</p>"
        "<p><img data-z2m-src=\"_page_1_Picture_1.jpeg\" /></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert polished.count('href="#page-13-0"') == 1
    assert "Competing interest:" in compact
    competing_paragraph = re.search(r"<p[^>]*>[^<]*Competing interest:[\s\S]*?</p>", polished)
    assert competing_paragraph is not None
    assert "Creative Commons" not in competing_paragraph.group(0)
    assert "This article is distributed under the terms of the" in compact


def test_polish_html_document_retargets_supplementary_page_figure_link() -> None:
    html = (
        "<html><body>"
        '<p>The assay is shown in Supplementary <a href="#page-8-0">Figure 11</a> '
        'and in <a href="#page-9-0">Figure 11</a>.</p>'
        "<p><b>Supplementary Figure 11</b> . Effect of the sensing condition.</p>"
        "<p><b>Figure 11</b> Main text control.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-supplementary-11"' in polished
    assert 'id="fig-11"' in polished
    assert 'href="#fig-supplementary-11"' in polished
    assert 'href="#fig-11"' in polished
    assert 'Supplementary <a href="#fig-supplementary-11" class="z2m-fig-link">Figure 11</a>' in polished
    assert 'href="#page-8-0"' not in polished
    assert 'href="#page-9-0"' not in polished


def test_polish_html_document_retargets_extended_data_figure_link() -> None:
    html = (
        "<html><body>"
        '<p>The rig is shown in Extended Data <a href="#page-8-0">Fig. 8</a>, '
        'while the main result appears in <a href="#page-9-0">Figure 8</a>.</p>'
        '<p><img src="extended8.jpg"/></p>'
        '<p><b>Extended Data Fig. 8</b> | Hardware setup used for the trials.</p>'
        '<p><img src="main8.jpg"/></p>'
        '<p><b>Figure 8</b> Main behavioural result.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-extended-data-8"' in polished
    assert 'id="fig-8"' in polished
    assert 'href="#fig-extended-data-8"' in polished
    assert 'href="#fig-8"' in polished
    assert 'Extended Data <a href="#fig-extended-data-8" class="z2m-fig-link">Fig. 8</a>' in polished
    assert '<a href="#fig-8" class="z2m-fig-link">Figure 8</a>' in polished
    assert 'href="#page-8-0"' not in polished
    assert 'href="#page-9-0"' not in polished


def test_polish_html_document_pairs_extended_data_heading_caption_with_previous_image() -> None:
    html = (
        "<html><body>"
        "<p>Dynamics are shown in Extended Data Fig. 8.</p>"
        '<p block-type="Text" class="has-continuation">'
        "<b>Extended Data Fig. 3 | Network of simplified neurons.</b> "
        "The networks consist of simplified branches.</p>"
        "<p block-type=\"Text\">(activity on the right) and the gradient with respect to all conductances.</p>"
        '<p><img src="ed4.jpg"/></p>'
        "<p><b>Extended Data Fig. 4 | Fitting single-cell models.</b> "
        "Number of simulations and runtime required to achieve the target loss.</p>"
        "<p block-type=\"Text\">loss across ten gradient descent runs and ten genetic algorithms.</p>"
        '<p><img src="ed5.jpg"/></p>'
        "<p><b>Extended Data Fig. 5 | Recordings from the Allen Cell Types Database.</b> "
        "Gradient descent and the genetic algorithm were run for fifty iterations.</p>"
        "<p block-type=\"Text\">simulations per step in parallel on GPU. Scale bars: 200 ms and 30 mV.</p>"
        '<p><img src="ed6.jpg"/></p>'
        "<p><b>Extended Data Fig. 6 | Bayesian inference of membrane conductances.</b> "
        "Blue lines show confidence intervals.</p>"
        '<p><img src="ed7.jpg"/></p>'
        "<p><b>Extended Data Fig. 7 | Generalization of the evidence integration task.</b> "
        'We used the same network parameters as in Fig. <a href="#page-5-0">4.</a></p>'
        '<p><img src="ed8.jpg"/></p>'
        "<h3><b>Extended Data Fig. 8 | Long-term dynamics reveal transient coding.</b> "
        'Long-term dynamics of the network from Fig. <a href="#page-5-0">4</a>.</h3>'
        "<p block-type=\"Text\">space, after briefly presenting either stimulus.</p>"
        '<p><img src="ed9.jpg"/></p>'
        "<p><b>Extended Data Fig. 9 | Hidden layer tuning.</b> Left: Before training.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    for key, image in (
        ("extended-data-4", "ed4.jpg"),
        ("extended-data-5", "ed5.jpg"),
        ("extended-data-6", "ed6.jpg"),
        ("extended-data-7", "ed7.jpg"),
        ("extended-data-8", "ed8.jpg"),
        ("extended-data-9", "ed9.jpg"),
    ):
        unit_match = re.search(
            rf'<div\b(?=[^>]*\bid="fig-{key}")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
            polished,
        )
        assert unit_match is not None
        unit = unit_match.group(0)
        assert f'src="{image}"' in unit
        assert "z2m-missing-figure-warning" not in unit


def test_polish_html_document_does_not_insert_missing_warning_for_supplementary_caption() -> None:
    html = (
        "<html><body>"
        "<p>See Supplementary Figure 3 for the auxiliary calibration.</p>"
        "<p><b>Supplementary Figure 3</b> . Auxiliary calibration.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-supplementary-3"' in polished
    assert 'href="#fig-supplementary-3"' in polished
    assert "Figure supplementary-3 image was not extracted" not in polished


def test_polish_html_document_repairs_figure_ref_split_by_line_number_block() -> None:
    html = (
        "<html><body>"
        "<p>The IEDC was stable in Figure 564 </p>"
        "<p>8C). Similarly, the average IEDC stayed stable.</p>"
        "<p>Figure 8. Electrode map summary.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Figure 564" not in polished
    assert '<a href="#fig-8" class="z2m-fig-link">Figure\xa08C</a>' in polished


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


def test_polish_html_document_keeps_bracket_citations_from_figure_chain_linking() -> None:
    html = (
        "<html><body>"
        "<p>Figure 1. Electrode placement.</p>"
        "<p>Figure 7. Acquisition settings.</p>"
        "<p>The electrodes were positioned as shown in Fig. 1 and the settings presented in [6, 7].</p>"
        "<h4>References</h4>"
        "<ol>" + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 8)) + "</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#fig-1"' in body
    assert '[<a href="#ref-6" class="z2m-ref-link">6</a>, <a href="#ref-7" class="z2m-ref-link">7</a>]' in body
    assert re.search(r"\[[^\]]*#fig-7", body) is None


def test_polish_html_document_unwraps_unresolved_semantic_page_links() -> None:
    html = (
        "<html><body>"
        '<p>Missing visual is discussed in Fig. <a href="#page-2-0">9A)</a> '
        'and Table <a href="#page-3-0">7)</a>.</p>'
        '<p>The screen is shown in <a href="#page-2-1">Figure 1a &amp; 1b.</a> '
        'and in Supplementary <a href="#page-2-2">Figure S2</a>.</p>'
        '<p>See S1 <a href="#page-4-0">Table</a>, Section <a href="#page-4-1">V-C)</a>, '
        'and Appendix <a href="#page-4-2">A.3.</a> for details.</p>'
        '<p>Data reported in the <a href="#page-5-0">Results</a> section are available.</p>'
        "<p><b> Fig. 1 </b> Extracted figure.</p>"
        "<p>Table 1. Extracted table.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "Fig. 9A)" in polished
    assert "Table 7)" in polished
    assert "Figure 1a &amp; 1b." in polished
    assert "Supplementary Figure S2" in polished
    assert "S1 Table" in polished
    assert "Section V-C)" in polished
    assert "Appendix A.3." in polished
    assert "Results section" in polished
    assert 'href="#page-2-0"' not in polished
    assert 'href="#page-3-0"' not in polished
    assert 'href="#page-2-1"' not in polished
    assert 'href="#page-2-2"' not in polished
    assert 'href="#page-4-0"' not in polished
    assert 'href="#page-4-1"' not in polished
    assert 'href="#page-4-2"' not in polished
    assert 'href="#page-5-0"' not in polished


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


def test_figure_caption_detection_ignores_body_reference_verbs() -> None:
    assert _figure_caption_num_from_visible("Figure 2 plots the change in gaze angle.") is None
    assert _figure_caption_num_from_visible("Figure 1 showcases the generated samples.") is None
    assert _figure_caption_num_from_visible("Figure 2 visualizes the generated samples.") is None
    assert _figure_caption_num_from_visible("Figure 12. F1 confidence curve.") == "12"


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


def test_polish_html_document_aliases_embedded_caption_labels_in_one_figure_unit() -> None:
    html = (
        "<html><body>"
        "<p>The matured ISM design is shown in Figure 7.</p>"
        '<p><img src="ism-models.jpg"/></p>'
        "<p>Figure 6 - Fully assembled ISM device Figure 7 - Differing ISM models "
        "showing leaded vs non-leaded designs.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig6_match = re.search(r'<div\b(?=[^>]*\bid="fig-6")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig6_match is not None
    fig6 = fig6_match.group(0)
    fig6_text = re.sub(r"<[^>]+>", " ", fig6).replace("\xa0", " ")
    assert 'src="ism-models.jpg"' in fig6
    assert "Figure 6" in fig6_text
    assert "Figure 7" in fig6_text
    assert '<span id="fig-7" class="z2m-float-alias"></span>' in fig6
    assert polished.count('id="fig-7"') == 1


def test_polish_html_document_aliases_embedded_list_caption_labels() -> None:
    html = (
        "<html><body>"
        "<p>The spherical coordinate system is shown in Fig. 7.</p>"
        '<p><img src="flattened.jpg"/></p>'
        "<p><b>FIG. 5.</b> Three flattened left hemispheres.</p>"
        '<p block-type="ListGroup"><ul>'
        "<li><b>FIG. 6.</b> Lateral view after spherical transformation.</li>"
        "<li><b>FIG. 7.</b> Spherical coordinate system painted onto surfaces.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig5_match = re.search(r'<div\b(?=[^>]*\bid="fig-5")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig5_match is not None
    fig5 = fig5_match.group(0)
    assert '<span id="fig-6" class="z2m-float-alias"></span>' in fig5
    assert '<span id="fig-7" class="z2m-float-alias"></span>' in fig5
    assert polished.count('id="fig-6"') == 1
    assert polished.count('id="fig-7"') == 1


def test_polish_html_document_does_not_alias_decimal_caption_label_prefix() -> None:
    html = (
        "<html><body>"
        "<p>The room task is discussed in Fig. 4.</p>"
        '<p><img src="letter-task.jpg"/></p>'
        "<p>Figure 4.1 : Letter recognition task in the virtual room.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-4" class="z2m-float-alias"' not in polished
    assert '<span id="fig-4" class="z2m-float-alias"></span>' not in polished
    assert 'id="fig-4-1"' in polished


def test_polish_html_document_does_not_alias_in_caption_body_reference() -> None:
    html = (
        "<html><body>"
        "<p>Current steering is compared with Figure 2A.</p>"
        '<p><img src="steering.jpg"/></p>'
        "<p>Figure 3. Effectiveness of Dynamic Current Steering in a blind participant "
        "(same participant as Figure 2). Five subdural electrodes were stimulated.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<span id="fig-2" class="z2m-float-alias"></span>' not in polished
    assert 'id="fig-3"' in polished


def test_polish_html_document_does_not_alias_extended_data_caption_reference() -> None:
    html = (
        "<html><body>"
        "<p>The recurrent network is summarized in Fig. 4.</p>"
        '<p><img src="network.jpg"/></p>'
        "<p>Fig. 4. Recurrent network dynamics. Extended Data Fig. 8 | "
        "Long-term dynamics reveal transient coding.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert '<span id="fig-8" class="z2m-float-alias"></span>' not in polished
    assert 'id="fig-4"' in polished


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


def test_polish_html_document_does_not_reuse_previous_image_across_body_prose() -> None:
    html = (
        "<html><body>"
        "<p>Figure 9. Example of LIDAR scan obtained in floor mode.</p>"
        '<p><img src="fig9.jpg"/></p>'
        "<p block-type=\"Text\">Figure 9 shows an example of raw LIDAR data. "
        "The line is estimated using [Figure 10(a)].</p>"
        "<p>Figure 10. Procedure used to estimate the frontal line.</p>"
        '<p><img src="fig10.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig9_match = re.search(r'<div id="fig-9"[\s\S]*?</div>', polished)
    fig10_match = re.search(r'<div id="fig-10"[\s\S]*?</div>', polished)
    assert fig9_match is not None
    assert fig10_match is not None
    fig9 = fig9_match.group(0)
    fig10 = fig10_match.group(0)

    assert 'src="fig9.jpg"' in fig9
    assert "Figure 9." in fig9
    assert "shows an example of raw LIDAR" not in fig9
    assert 'src="fig10.jpg"' in fig10
    assert "Figure 10." in fig10
    assert 'src="fig9.jpg"' not in fig10
    assert "shows an example of raw LIDAR" not in fig10
    body_match = re.search(r'<p\b[^>]*>\s*<a href="#fig-9"[\s\S]*?shows an example of raw LIDAR[\s\S]*?</p>', polished)
    assert body_match is not None
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_treats_figure_plots_as_body_reference() -> None:
    html = (
        "<html><body>"
        "<h3>Results</h3>"
        "<p block-type=\"Text\">Figure 2 plots the change in gaze angle for all subjects.</p>"
        '<p><img src="fig2.jpg"/></p>'
        "<p>Figure 2. Comparison of saccade amplitudes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(r'<div id="fig-2"[\s\S]*?</div>', polished)
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert 'src="fig2.jpg"' in fig2
    assert "Figure 2." in fig2
    assert "plots the change in gaze angle" not in fig2
    assert re.search(r'<p\b[^>]*\bz2m-missing-figure-warning\b', polished) is None
    body_match = re.search(r'<p\b[^>]*>\s*<a href="#fig-2"[\s\S]*?plots the change in gaze angle[\s\S]*?</p>', polished)
    assert body_match is not None
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_treats_spaced_panel_figure_shows_as_body_reference() -> None:
    html = (
        "<html><body>"
        "<p block-type=\"Text\">Figure 4 D shows model and simulated predictions for patient data.</p>"
        '<p><img src="fig4.jpg"/></p>'
        "<p>Figure 4. Phosphene size as function of current amplitude.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig4_match = re.search(r'<div id="fig-4"[\s\S]*?</div>', polished)
    assert fig4_match is not None
    assert 'src="fig4.jpg"' in fig4_match.group(0)
    assert "Phosphene size as function" in fig4_match.group(0)
    body_match = re.search(
        r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-4")[^>]*>[\s\S]*?model and simulated predictions[\s\S]*?</p>',
        polished,
    )
    assert body_match is not None
    assert 'href="#fig-4"' in body_match.group(0)
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_treats_panel_chain_figure_examines_as_body_reference() -> None:
    html = (
        "<html><body>"
        "<p block-type=\"Text\">Figure 7 B and C examines the predicted effect of electrode size.</p>"
        '<p><img src="fig7.jpg"/></p>'
        "<p>Figure 7. Using virtual patients to predict perceptual outcomes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig7_match = re.search(r'<div id="fig-7"[\s\S]*?</div>', polished)
    assert fig7_match is not None
    assert 'src="fig7.jpg"' in fig7_match.group(0)
    assert "Using virtual patients" in fig7_match.group(0)
    body_match = re.search(
        r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-7")[^>]*>[\s\S]*?predicted effect of electrode size[\s\S]*?</p>',
        polished,
    )
    assert body_match is not None
    assert 'href="#fig-7"' in body_match.group(0)
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_treats_parenthetical_panel_phrase_shows_as_body_reference() -> None:
    html = (
        "<html><body>"
        "<p block-type=\"Text\">Figure 4 (left panels) shows the variable error in the navigation tasks.</p>"
        '<p><img src="fig4.jpg"/></p>'
        "<p>Figure 4. Variable-error maps for allocentric and egocentric tasks.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig4_match = re.search(r'<div id="fig-4"[\s\S]*?</div>', polished)
    assert fig4_match is not None
    fig4 = fig4_match.group(0)
    assert 'src="fig4.jpg"' in fig4
    assert "Variable-error maps" in fig4
    assert "left panels" not in fig4
    body_match = re.search(
        r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-4")[^>]*>[\s\S]*?variable error[\s\S]*?</p>',
        polished,
    )
    assert body_match is not None
    assert 'href="#fig-4"' in body_match.group(0)
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_treats_panel_range_shows_as_body_reference() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig3.jpg"/></p>'
        "<p>Fig. 3 The software acquires the video and displays flow versus time.</p>"
        "<p block-type=\"Text\">Figure 5a-c show the mean differences between predetermined volumes.</p>"
        '<p><img src="fig5.jpg"/></p>'
        "<p>Fig. 5 a\u2013c Bland-Altman plots for total voided volume.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(r'<div id="fig-3"[\s\S]*?</div>', polished)
    fig5_match = re.search(r'<div id="fig-5"[\s\S]*?</div>', polished)
    assert fig3_match is not None
    assert fig5_match is not None
    fig3 = fig3_match.group(0)
    fig5 = fig5_match.group(0)
    assert 'src="fig3.jpg"' in fig3
    assert 'src="fig5.jpg"' not in fig3
    assert 'id="fig-5" class="z2m-float-alias"' not in fig3
    assert 'src="fig5.jpg"' in fig5
    body_match = re.search(
        r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-5")[^>]*>[\s\S]*?mean differences[\s\S]*?</p>',
        polished,
    )
    assert body_match is not None
    assert 'href="#fig-5"' in body_match.group(0)
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_treats_repeated_number_panel_range_as_body_reference() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig4.jpg"/></p>'
        "<p>Fig. 4. Maze navigational behaviours and results.</p>"
        "<p block-type=\"Text\">Fig 4I\u20134K show the learning curves over six trials.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig4_match = re.search(r'<div id="fig-4"[\s\S]*?</div>', polished)
    assert fig4_match is not None
    fig4 = fig4_match.group(0)
    assert 'src="fig4.jpg"' in fig4
    assert "Maze navigational behaviours" in fig4
    assert "learning curves" not in fig4
    body_match = re.search(r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-4")[^>]*>[\s\S]*?learning curves[\s\S]*?</p>', polished)
    assert body_match is not None
    assert 'href="#fig-4"' in body_match.group(0)
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_treats_validates_and_details_as_body_figure_verbs() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig8.jpg"/></p>'
        "<p>Figure 8. Confusion matrix for the detector.</p>"
        "<p block-type=\"Text\">Figure 8 validates the confusion matrix produced through the approach.</p>"
        '<p><img src="fig13.jpg"/></p>'
        "<p>Figure 13. Collision counts for each mode.</p>"
        "<p block-type=\"Text\">Figure 13 details the number of collisions for each mode.</p>"
        '<p><img src="fig4.jpg"/></p>'
        "<p>Figure 4. Corticospinal axon topography.</p>"
        "<p block-type=\"Text\">Figure 4 exemplifies the topography of corticospinal axons.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    for fig_id, image, caption, body in [
        ("fig-8", "fig8.jpg", "Confusion matrix", "validates the confusion matrix"),
        ("fig-13", "fig13.jpg", "Collision counts", "details the number of collisions"),
        ("fig-4", "fig4.jpg", "Corticospinal axon topography", "exemplifies the topography"),
    ]:
        fig_match = re.search(rf'<div id="{fig_id}"[\s\S]*?</div>', polished)
        assert fig_match is not None
        fig = fig_match.group(0)
        assert f'src="{image}"' in fig
        assert caption in fig
        assert body not in fig
    assert len(re.findall(r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-)[^>]*>[\s\S]*?</p>', polished)) >= 2


def test_polish_html_document_drops_duplicate_id_from_body_figure_reference() -> None:
    html = (
        "<html><body>"
        '<div id="fig-9" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig9.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 9. Scaling of unsupervised pretraining.</p>'
        "</div>"
        '<p block-type="Text" id="fig-9">Fig. <a href="#fig-9" class="z2m-fig-link">9B</a> '
        "contrasts decoding curves in the two pretraining settings.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count('id="fig-9"') == 1
    body_match = re.search(r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-9")[^>]*>[\s\S]*?contrasts decoding[\s\S]*?</p>', polished)
    assert body_match is not None
    assert 'href="#fig-9"' in body_match.group(0)
    assert "z2m-figure-caption" not in body_match.group(0)


def test_figure_caption_num_ignores_decimal_or_hyphen_body_references() -> None:
    assert _figure_caption_num_from_visible("Figure 4-39 shows the cross-sectional view.") is None
    assert _figure_caption_num_from_visible("Figure 3.11 provides further demonstration.") is None
    assert _figure_caption_num_from_visible("Figure 2. 8 shows the traces of electrical activity.") is None
    assert _figure_caption_num_from_visible("Figure 3.10. Calibration curves of the flow rate measurement.") == "3-10"
    assert _figure_caption_num_from_visible("Figure 2. 6 The topography of the electrodes.") == "2-6"


def test_polish_html_document_does_not_anchor_decimal_figure_body_reference() -> None:
    html = (
        "<html><body>"
        "<p>Figure 2. 8 shows the traces of electrical and mechanical activity of the heart.</p>"
        '<p>See <a href="#fig-3-10" class="z2m-fig-link">Figure 3.10</a>.</p>'
        '<p id="fig-3-10">Figure 3.10. Calibration curves of the flow rate measurement.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-2"' not in polished
    assert "Figure 2. 8 shows the traces" in polished
    assert 'id="fig-3-10"' in polished


def test_polish_html_document_retargets_spaced_decimal_caption_before_image() -> None:
    html = (
        "<html><body>"
        '<p>See <a href="#fig-2-6" class="z2m-fig-link">Figure 2.6</a>.</p>'
        '<p id="fig-2-6">Figure 2. 6 The topography of the electrodes.</p>'
        '<p><img src="fig26.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig_match = re.search(r'<div id="fig-2-6"[\s\S]*?</div>', polished)
    assert fig_match is not None
    assert 'src="fig26.jpg"' in fig_match.group(0)
    caption_match = re.search(
        r'<p\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-2-6")[^>]*>[\s\S]*?topography[\s\S]*?</p>',
        polished,
    )
    assert caption_match is not None
    assert 'href="#fig-2-6"' in polished


def test_polish_html_document_drops_duplicate_id_from_figure_chain_body_reference() -> None:
    html = (
        "<html><body>"
        '<div id="fig-4-62" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig462.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4-62. First result.</p>'
        "</div>"
        '<div id="fig-4-63" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig463.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4-63. Second result.</p>'
        "</div>"
        '<p block-type="Text" id="fig-4-62">Figure 4-62 and Figure 4-63 shows the shapes of the deformation.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert polished.count('id="fig-4-62"') == 1
    body_match = re.search(
        r'<p\b(?=[^>]*block-type="Text")(?![^>]*\bid="fig-4-62")[^>]*>[\s\S]*?Figure 4[.-]\s*62 and Figure 4-63[\s\S]*?</p>',
        polished,
    )
    assert body_match is not None
    assert "z2m-figure-caption" not in body_match.group(0)


def test_polish_html_document_retargets_caption_only_id_to_following_image() -> None:
    html = (
        "<html><body>"
        '<p>See <a href="#fig-1" class="z2m-fig-link">Figure 1</a>.</p>'
        '<p id="fig-1">Figure 1. Mean percentage error rate for interventions.</p>'
        "<h2>Percentage of instructor interventions to total locations</h2>"
        '<p><img src="fig1.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig_match = re.search(r'<div id="fig-1"[\s\S]*?</div>', polished)
    assert fig_match is not None
    assert 'src="fig1.jpg"' in fig_match.group(0)
    caption_match = re.search(r'<p\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-1")[^>]*>[\s\S]*?Mean percentage error rate[\s\S]*?</p>', polished)
    assert caption_match is not None
    assert 'href="#fig-1"' in polished


def test_polish_html_document_retargets_caption_id_to_image_with_page_anchor() -> None:
    html = (
        "<html><body>"
        '<p>See <a href="#fig-1" class="z2m-fig-link">Figure 1</a>.</p>'
        '<p><span id="page-1-0"></span><img src="fig1.jpg"/></p>'
        "<p>Parallel in-silico discovery of bacterial gene transfer mechanism relevant to AMR</p>"
        '<p id="fig-1">Figure 1. The system design and experimental validation summary.</p>'
        "<p>Body text resumes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    target_match = re.search(r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?fig1\.jpg[\s\S]*?</div>', polished)
    assert target_match is not None
    caption_match = re.search(
        r'<p\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-1")[^>]*>[\s\S]*?system design[\s\S]*?</p>',
        polished,
    )
    assert caption_match is not None
    assert 'href="#fig-1"' in polished


def test_polish_html_document_anchors_heading_figure_caption_to_previous_image() -> None:
    html = (
        "<html><body>"
        "<p>Optical coherence tomography revealed optic disc edema (Figure 2).</p>"
        '<p><img src="oct.jpg"/></p>'
        "<h2><b>FIGURE 2: Retinal photographs and thickness evaluation</b></h2>"
        "<p>Retinal nerve fiber layer defects were observed in both eyes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert 'src="oct.jpg"' in fig2
    assert re.search(
        r'<h2\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-2")[^>]*>[\s\S]*?Retinal photographs',
        fig2,
    )
    assert 'href="#fig-2"' in polished


def test_polish_html_document_retargets_void_number_link_for_heading_figure_ref() -> None:
    html = (
        "<html><body>"
        "<p>Optical coherence tomography revealed optic disc edema "
        '(Figure <i><a href="javascript:void(0)"> 2 </a></i>).</p>'
        '<p><img src="oct.jpg"/></p>'
        "<h2><b>FIGURE 2: Retinal photographs and thickness evaluation</b></h2>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index('id="fig-2"')]

    assert "javascript:void(0)" not in body
    assert re.search(
        r'Figure\s*<i>\s*<a href="#fig-2" class="z2m-fig-link">\s*2\s*</a>\s*</i>',
        body,
    )
    assert 'src="oct.jpg"' in polished


def test_polish_html_document_anchors_heading_figure_caption_to_following_image() -> None:
    html = (
        "<html><body>"
        "<p>A diagram of participant flow is shown in figure 2.</p>"
        "<h2>Figure 2 Participant recruitment flow diagram.</h2>"
        '<p><img src="flow.jpg"/></p>'
        "<p>One hundred and seventy-two patients were approached.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert 'src="flow.jpg"' in fig2
    assert re.search(
        r'<h2\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-2")[^>]*>[\s\S]*?Participant recruitment',
        fig2,
    )
    assert 'href="#fig-2"' in polished


def test_polish_html_document_anchors_standalone_heading_label_after_image() -> None:
    html = (
        "<html><body>"
        "<p>The retina projects information to the LGN for further processing (Figure 3).</p>"
        '<p><img src="_page_3_Picture_8.jpeg"/></p>'
        '<h4><span id="page-3-1"></span>FIGURE 3</h4>'
        "<p>The structure of the retina. Created with BioRender.com.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert '_page_3_Picture_8.jpeg' in fig3
    assert re.search(
        r'<h4\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-3")[^>]*>[\s\S]*?FIGURE',
        fig3,
    )
    assert 'href="#fig-3"' in polished


def test_polish_html_document_anchors_stat_map_caption_to_previous_image() -> None:
    html = (
        "<html><body>"
        "<p>The localization contrast is shown in Fig. 3 (P &lt;0.001 uncorrected).</p>"
        '<p><img src="_page_7_Picture_8.jpeg"/></p>'
        "<p><b>Fig. 3</b> <i>t</i> maps for contrasts testing the main effect.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert '_page_7_Picture_8.jpeg' in fig3
    assert re.search(
        r'<p\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-3")[^>]*>[\s\S]*?maps for contrasts',
        fig3,
    )
    assert 'href="#fig-3"' in polished


def test_add_figure_anchors_keeps_stat_map_caption_plain_without_adjacent_image() -> None:
    html = "<p><b>Fig. 3</b> <i>t</i> maps for contrasts testing the main effect.</p>"

    result, found = _add_figure_anchors(html)

    assert "3" not in found
    assert 'id="fig-3"' not in result


def test_polish_html_document_wraps_heading_caption_without_image_as_missing() -> None:
    html = (
        "<html><body>"
        "<p>Compare the missing schematic in Figure 8.</p>"
        "<h2>Figure 8. Missing heading caption.</h2>"
        "<p>Body text resumes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig8_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-8")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig8_match is not None
    fig8 = fig8_match.group(0)
    assert "Figure 8 image was not extracted" in fig8
    assert 'data-z2m-origin="caption-only-target"' in fig8
    assert re.search(
        r'<h2\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-8")[^>]*>[\s\S]*?Missing heading caption',
        fig8,
    )
    assert 'href="#fig-8"' in polished


def test_polish_html_document_recovers_orphan_figure_from_page_linked_ref_across_table() -> None:
    html = (
        "<html><body>"
        '<p>Detailed information can be found in <a href="#table-4">Table 4</a> '
        'and <a href="#page-13-0">Figure 3</a>.</p>'
        '<div id="table-4" class="z2m-float-unit z2m-table-unit">'
        '<p class="z2m-table-caption">TABLE 4. Spatial navigation clusters.</p>'
        "<table><tr><td>Cluster</td></tr></table></div>"
        '<p><img data-z2m-src="_page_13_Figure_1.jpeg" src="fig3.jpg"/></p>'
        "<p><span id=\"page-13-0\"></span> Brain areas activated by spatial navigation "
        "in EB and SC and results of conjunction analysis. (Left) 3D renders of the brain "
        "and activation clusters. (Right) Axial cuts of the brain with identified clusters.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert 'src="fig3.jpg"' in fig3
    assert "Brain areas activated by spatial navigation" in fig3
    assert 'class="z2m-figure-target"' in fig3
    assert 'class="z2m-figure-caption"' in fig3
    assert 'href="#fig-3"' in polished
    assert 'href="#page-13-0">Figure 3</a>' not in polished


def test_polish_html_document_recovers_embedded_figure_label_caption_after_image() -> None:
    html = (
        "<html><body>"
        '<p><img src="front.jpg"/></p>'
        "<p>The Smart Power Assistance Module for Manual Wheelchairs (front view) "
        "<b>Figure 1</b> The Smart Power Assistance Module for Manual Wheelchairs (front view).</p>"
        '<p><img src="back.jpg"/></p>'
        "<p>The Smart Power Assistance Module for Manual Wheelchairs (back view) "
        "<b>Figure 2</b> The Smart Power Assistance Module for Manual Wheelchairs (back view).</p>"
        "<p>The SPAM shown in Figure 1 and Figure 2 senses propulsion forces.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig1_match is not None
    fig1 = fig1_match.group(0)
    assert 'src="front.jpg"' in fig1
    assert "Manual Wheelchairs (front view)" in fig1
    assert 'class="z2m-figure-target"' in fig1
    assert 'class="z2m-figure-caption"' in fig1

    fig2_match = re.search(r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert 'src="back.jpg"' in fig2
    assert "Manual Wheelchairs (back view)" in fig2
    assert 'href="#fig-1"' in polished
    assert 'href="#fig-2"' in polished


def test_polish_html_document_ignores_embedded_figure_ref_in_body_text_after_image() -> None:
    html = (
        "<html><body>"
        '<p><img src="diagram.jpg"/></p>'
        '<p block-type="Text">The system shown in Figure 1 describes the wheel force sensor.</p>'
        "<p>No figure caption follows in this accepted-manuscript text.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert 'z2m-figure-unit' not in polished


def test_polish_html_document_retargets_caption_id_across_short_ocr_prose_gap() -> None:
    html = (
        "<html><body>"
        '<p>See <a href="#fig-4" class="z2m-fig-link">Figure 4</a>.</p>'
        '<p><img src="fig4a.jpg"/></p>'
        '<p><img src="fig4b.jpg"/></p>'
        "<p>curvatures. c, Nano-bio interfaces can assess intracellular structures and modulate the cytoskeleton.</p>"
        '<p id="fig-4">Fig. 4 | Nanotopographical interfaces for probing cellular processes.</p>'
        "<p>Body text resumes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig4_match = re.search(r'<div\b(?=[^>]*\bid="fig-4")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig4_match is not None
    fig4 = fig4_match.group(0)
    assert 'src="fig4a.jpg"' in fig4
    assert 'src="fig4b.jpg"' in fig4
    caption_match = re.search(
        r'<p\b(?=[^>]*\bz2m-figure-caption\b)(?![^>]*\bid="fig-4")[^>]*>[\s\S]*?Nanotopographical[\s\S]*?</p>',
        polished,
    )
    assert caption_match is not None
    assert 'href="#fig-4"' in polished


def test_polish_html_document_does_not_retarget_caption_id_across_table_unit() -> None:
    html = (
        "<html><body>"
        '<p>See <a href="#fig-8" class="z2m-fig-link">Figure 8</a>.</p>'
        '<p><img src="candidate.jpg"/></p>'
        '<div id="table-4" class="z2m-float-unit z2m-table-unit"><p>Table 4. Intervening table.</p><table><tr><td>x</td></tr></table></div>'
        '<p id="fig-8">Figure 8. Caption after a table.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert not re.search(r'<div\b(?=[^>]*\bid="fig-8")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?candidate\.jpg', polished)
    assert "Caption after a table" in polished
    fig8_match = re.search(r'<div\b(?=[^>]*\bid="fig-8")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig8_match is not None
    assert "z2m-missing-figure-warning" in fig8_match.group(0)


def test_polish_html_document_wraps_unretargeted_caption_only_target_as_missing() -> None:
    html = (
        "<html><body>"
        '<p>Compare <a href="#fig-5" class="z2m-fig-link">Figure 5</a>.</p>'
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig4.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 4. Previous image.</p>'
        "</div>"
        '<p id="fig-5">Figure 5. Missing image caption.</p>'
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig6.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 6. Following image.</p>'
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig5_match = re.search(r'<div\b(?=[^>]*\bid="fig-5")(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig5_match is not None
    fig5 = fig5_match.group(0)
    assert "Figure 5 image was not extracted" in fig5
    assert 'data-z2m-origin="caption-only-target"' in fig5
    assert "Missing image caption" in fig5
    assert 'src="fig4.jpg"' not in fig5
    assert 'src="fig6.jpg"' not in fig5
    assert not re.search(r'<p\b(?=[^>]*\bid="fig-5")[^>]*>[\s\S]*?Missing image caption', polished)


def test_polish_html_document_keeps_details_of_caption_as_figure_caption() -> None:
    html = (
        "<html><body>"
        '<p>See <a href="#fig-2" class="z2m-fig-link">Figure 2</a>.</p>'
        '<p><b><a href="#fig-2" class="z2m-fig-link">Figure 2</a></b> '
        "Details of the Palazzo Ducale Gothic lodges.</p>"
        '<p><img src="fig2.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig_match = re.search(r'<div id="fig-2"[\s\S]*?</div>', polished)
    assert fig_match is not None
    fig2 = fig_match.group(0)
    assert 'src="fig2.jpg"' in fig2
    assert "Details of the Palazzo Ducale" in fig2
    assert 'href="#fig-2"' in polished


def test_polish_html_document_keeps_3d_title_out_of_figure_number() -> None:
    html = (
        "<html><body>"
        '<p><img src="fig2.jpg"/></p>'
        '<p><span id="page-2-0"> </span> Figure 2. 3D high-density multiple electrode sheets.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(r'<div id="fig-2"[\s\S]*?</div>', polished)
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert 'src="fig2.jpg"' in fig2
    assert "3D high-density multiple electrode sheets" in fig2
    assert 'id="fig-2-3"' not in polished


def test_polish_html_document_absorbs_external_caption_after_existing_figure_unit() -> None:
    html = (
        "<html><body>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig3.jpg"/></p>'
        "</div>"
        '<p class="z2m-figure-caption"><b>Figure 3.</b> Brain activity associated with navigation.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(r'<div id="fig-3"[\s\S]*?</div>', polished)
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert 'src="fig3.jpg"' in fig3
    assert "Brain activity associated with navigation" in fig3
    assert not re.search(r'</div>\s*<p\b[^>]*\bz2m-figure-caption\b[^>]*>\s*<b>\s*Figure 3\.', polished)


def test_polish_html_document_does_not_absorb_plain_image_with_different_figure_id() -> None:
    html = (
        "<html><body>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig3a.jpg"/></p>'
        "</div>"
        '<p id="fig-2"><img src="fig2.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 3. Seed connectivity map.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(r'<div id="fig-3"[\s\S]*?</div>', polished)
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert 'src="fig3a.jpg"' in fig3
    assert 'src="fig2.jpg"' not in fig3
    assert 'id="fig-2" class="z2m-float-alias"' not in fig3


def test_polish_html_document_expands_continuation_only_figure_unit() -> None:
    html = (
        "<html><body>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig3a.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 3. Cont.</p>'
        "</div>"
        '<p id="fig-3" class="z2m-figure-target"><img src="fig3b.jpg"/></p>'
        '<p class="z2m-figure-caption"><b>Figure 3.</b> Gait velocity measurements.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(r'<div id="fig-3"[\s\S]*?</div>', polished)
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    assert 'src="fig3a.jpg"' in fig3
    assert 'src="fig3b.jpg"' in fig3
    assert "Figure 3. Cont." in fig3
    assert "Gait velocity measurements" in fig3
    assert not re.search(r'</div>\s*<p\b[^>]*\bid="fig-3"\b', polished)


def test_polish_html_document_expands_existing_caption_unit_with_next_same_label_image() -> None:
    html = (
        "<html><body>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig3a.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig. 3: Bland Altman plot for baseline data.</p>'
        "</div>"
        '<p id="fig-3"><img src="fig3b.jpg"/></p>'
        '<p class="z2m-figure-caption">Fig. 3: Bland Altman plot for exercise data.</p>'
        "<p>Discussion starts here.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig3_match = re.search(r'<div id="fig-3"[\s\S]*?</div>', polished)
    assert fig3_match is not None
    fig3 = fig3_match.group(0)
    after = polished[fig3_match.end() :]
    assert 'src="fig3a.jpg"' in fig3
    assert 'src="fig3b.jpg"' in fig3
    assert "baseline data" in fig3
    assert "exercise data" in fig3
    assert not re.search(r'<p\b[^>]*\bid="fig-3"\b', after)
    assert "Discussion starts here." in after


def test_polish_html_document_wraps_caption_id_after_image_run_and_page_furniture() -> None:
    html = (
        "<html><body>"
        '<p><img src="femur-model.jpg"/></p>'
        '<p block-type="Text" class="z2m-front-matter">Downloaded from Wiley Online Library. '
        "See the Terms and Conditions; OA articles are governed by the applicable Creative Commons License.</p>"
        '<p id="fig-2">Figure 2 Measurement of the femoral valgus angle in the three-dimensional model.</p>'
        "<p>Body text resumes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(r'<div id="fig-2"[\s\S]*?</div>', polished)
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    after = polished[fig2_match.end() :]
    assert 'src="femur-model.jpg"' in fig2
    assert "Figure 2 Measurement of the femoral" in fig2
    assert "Wiley Online Library" not in fig2
    assert "Wiley Online Library" not in polished
    assert not re.search(r'<p\b[^>]*\bid="fig-2"\b', after)
    assert "Body text resumes." in after


def test_polish_html_document_does_not_suppress_missing_warning_across_previous_figure_unit() -> None:
    html = (
        "<html><body>"
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 1. Existing image.</p>'
        "</div>"
        '<p id="fig-2"><b>Figure 2.</b> Missing system architecture.</p>'
        '<p>See Figure 2 for the architecture.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(r'<div id="fig-2"[\s\S]*?</div>', polished)
    assert fig2_match is not None
    fig2 = fig2_match.group(0)
    assert "z2m-missing-figure-unit" in fig2
    assert "z2m-missing-figure-warning" in fig2
    assert "Missing system architecture" in fig2
    assert 'src="fig1.jpg"' not in fig2


def test_polish_html_document_retargets_duplicate_figure_label_with_nearby_next_ref() -> None:
    html = (
        "<html><body>"
        '<p><img src="cells.jpg"/></p>'
        "<p>Figure 5. Time-course imaging of cell internalization.</p>"
        '<p block-type="Text">As illustrated in Figure 6A, three different nanomicelles '
        "were dipped on the buttock of the nude mice.</p>"
        '<p><img src="mouse-nir.jpg"/></p>'
        '<p><img src="mouse-brightfield.jpg"/></p>'
        "<p><b>Figure 5. </b>In vivo imaging of nude mice after subcutaneous injections. "
        "(A) NIR image. (B) Bright field image.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig5_match = re.search(r'<div\b(?=[^>]*\bid="fig-5")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    fig6_match = re.search(r'<div\b(?=[^>]*\bid="fig-6")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>', polished)
    assert fig5_match is not None
    assert fig6_match is not None
    fig5 = fig5_match.group(0)
    fig6 = fig6_match.group(0)
    assert 'src="cells.jpg"' in fig5
    assert 'src="mouse-nir.jpg"' in fig6
    assert 'src="mouse-brightfield.jpg"' in fig6
    assert "Figure 6." in fig6
    assert "In vivo imaging" in fig6
    assert 'href="#fig-6"' in polished
    assert "z2m-missing-figure-warning" not in fig6
    assert polished.count('id="fig-6"') == 1


def test_polish_html_document_keeps_duplicate_figure_label_without_next_ref() -> None:
    html = (
        "<html><body>"
        '<p><img src="cells.jpg"/></p>'
        "<p>Figure 5. Time-course imaging of cell internalization.</p>"
        '<p block-type="Text">The in vivo experiment used the same nanomicelles for comparison.</p>'
        '<p><img src="mouse-nir.jpg"/></p>'
        '<p><img src="mouse-brightfield.jpg"/></p>'
        "<p><b>Figure 5. </b>In vivo imaging of nude mice after subcutaneous injections. "
        "(A) NIR image. (B) Bright field image.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-6"' not in polished
    assert "Figure 6." not in polished
    assert 'href="#fig-6"' not in polished


def test_split_table_unit_before_heading_preserves_following_figure_close() -> None:
    html = (
        '<div id="table-4" class="z2m-float-unit z2m-table-unit">'
        '<p class="z2m-table-caption">TABLE 4. Results.</p>'
        '<h3 id="section-6-5">6.5 Comparison of Results</h3>'
        '<p>Figure 1 shows the training loss.</p>'
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 1: Training loss.</p>'
        "</div>"
    )

    repaired = _split_table_units_before_section_headings(html)

    assert '<div id="table-4" class="z2m-float-unit z2m-table-unit">' in repaired
    assert '<p class="z2m-table-caption">TABLE 4. Results.</p></div><h3' in repaired
    fig_start = repaired.index('<div id="fig-1"')
    fig_end = repaired.index("</div>", fig_start)
    fig = repaired[fig_start:fig_end]
    assert 'src="fig1.jpg"' in fig
    assert "Figure 1: Training loss." in fig
    assert repaired[fig_end : fig_end + 6] == "</div>"


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


def test_polish_html_document_wraps_standalone_figure_label_before_image_as_real_target() -> None:
    html = (
        "<html><body>"
        "<p>The vertical line guide position is shown in Figure 1.</p>"
        "<p>Figure 1</p>"
        '<p><img src="line-guide.jpg"/></p>'
        "<p>Body text resumes.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    fig1 = fig1_match.group(0)
    assert 'src="line-guide.jpg"' in fig1
    assert "z2m-missing-figure-warning" not in fig1
    assert 'class="z2m-figure-target"' in fig1
    assert re.search(r'<p\b(?=[^>]*\bz2m-figure-caption\b)[^>]*>[\s\S]*?Figure', fig1)
    assert 'href="#fig-1"' in polished
    assert "Body text resumes." in polished[fig1_match.end() :]


def test_polish_html_document_keeps_panel_details_with_standalone_figure_labels() -> None:
    html = (
        "<html><body>"
        "<p>The final stent position is shown in Fig. 3A.</p>"
        "<h3>Figures</h3>"
        '<p><img src="venous-phase.jpg"/></p>'
        "<h4>Figure 1</h4>"
        "<p>(A) Venous phase angiogram demonstrating stenosis.</p>"
        '<p><img src="pressure-map.jpg"/></p>'
        "<p>Figure 2</p>"
        "<p>(A) Showing an 8mm vascular stent across the stenosis.</p>"
        '<p><img src="microwire.jpg"/></p>'
        "<p>Figure 3</p>"
        "<p>(A) Using a standard microwire to cross the narrowed segment.</p>"
        "<p>Body text resumes after the figure list.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig3_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-3")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig1_match is not None
    assert fig2_match is not None
    assert fig3_match is not None
    fig1 = fig1_match.group(0)
    fig2 = fig2_match.group(0)
    fig3 = fig3_match.group(0)
    assert 'src="venous-phase.jpg"' in fig1
    assert "(A) Venous phase angiogram" in fig1
    assert 'src="pressure-map.jpg"' not in fig1
    assert 'src="pressure-map.jpg"' in fig2
    assert "(A) Showing an 8mm vascular stent" in fig2
    assert 'src="microwire.jpg"' not in fig2
    assert 'src="microwire.jpg"' in fig3
    assert "(A) Using a standard microwire" in fig3
    assert 'href="#fig-3"' in polished
    assert "Body text resumes after the figure list." in polished[fig3_match.end() :]


def test_polish_html_document_wraps_caption_before_panel_image_run() -> None:
    html = (
        "<html><body>"
        "<p>The receptive-field results are summarized in Figure 9 and Figure 9b.</p>"
        "<h4>Figure 9</h4>"
        "<p>Location and size of phosphenes produced by stimulation of the primary visual cortex. "
        "(a) A posterior-medial view of the occipital portion of one brain. "
        "(b) Method for mapping receptive fields. "
        "(c) Method for mapping phosphenes. "
        "Modified with permission from the Society for Neuroscience.</p>"
        "<h4>a Predicted cortical activation: human V1</h4>"
        '<p><img src="fig9-a.jpg"/></p>'
        '<p><img src="fig9-b.jpg"/></p>'
        "<h4><b>C</b> Predicted cortical activation: macaque V1</h4>"
        '<p><img src="fig9-c.jpg"/></p>'
        '<p><img src="fig9-d.jpg"/></p>'
        "<p>Body text resumes between the figure panels and the next caption.</p>"
        "<p>Figure 10</p>"
        "<p>Relationship between predicted cortical activity and behavior.</p>"
        '<p><img src="fig10.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig9_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-9")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig10_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-10")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig9_match is not None
    assert fig10_match is not None
    fig9 = fig9_match.group(0)
    fig10 = fig10_match.group(0)
    assert 'src="fig9-a.jpg"' in fig9
    assert 'src="fig9-b.jpg"' in fig9
    assert 'src="fig9-c.jpg"' in fig9
    assert 'src="fig9-d.jpg"' in fig9
    assert "Predicted cortical activation: macaque V1" in fig9
    assert 'src="fig10.jpg"' not in fig9
    assert 'src="fig10.jpg"' in fig10
    assert 'href="#fig-9"' in polished
    assert "Figure 9b" not in polished
    assert 'href="#fig-10"' not in fig9


def test_polish_html_document_keeps_previous_caption_image_when_next_panel_run_follows() -> None:
    html = (
        "<html><body>"
        "<p>Electrical stimulation of visual cortex provides an opportunity to test this tenet (Figure 9).</p>"
        '<p><img src="fig9-location-size.jpg"/></p>'
        "<p>Bosking Beauchamp Yoshor</p>"
        "<p>area, this can be due to the centering of the electrode over a color domain.</p>"
        "<h1><b>ECoG:</b> electrocorticography</h1>"
        "<h4>Figure 9</h4>"
        "<p>Location and size of phosphenes produced by stimulation of the primary visual cortex. "
        "(a) A posterior-medial view of the occipital portion of one brain. "
        "(b) Method for mapping receptive fields. "
        "(c) Method for mapping phosphenes. "
        "(d) Receptive field eccentricity versus phosphene eccentricity. "
        "(e) Receptive field polar angle versus phosphene polar angle. "
        "(f) Phosphene size tested for six currents. "
        "(g) Phosphene size versus eccentricity.</p>"
        "<h4>a Predicted cortical activation: human V1</h4>"
        '<p><img src="fig10-a.jpg"/></p>'
        '<p><img src="fig10-b.jpg"/></p>'
        "<h4><b>C</b> Predicted cortical activation: macaque V1</h4>"
        '<p><img src="fig10-c.jpg"/></p>'
        '<p><img src="fig10-d.jpg"/></p>'
        "<p>Figure 10</p>"
        "<p>Relationship between predicted cortical activity and behavior. "
        "(a) Schematic showing the map of visual space. "
        "(b) The phosphene location and size predicted for electrical stimulation. "
        "(c) Predicted cortical activation during primate saccades. "
        "(d) The size of saccade delay fields.</p>"
        '<p><img src="fig11-face-place.jpg"/></p>'
        "<p>Figure 11</p>"
        "<p>Stimulation of face- and place-selective regions of ventral temporal cortex.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig9 = re.search(
        r'<div\b(?=[^>]*\bid="fig-9")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig10 = re.search(
        r'<div\b(?=[^>]*\bid="fig-10")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig11 = re.search(
        r'<div\b(?=[^>]*\bid="fig-11")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )

    assert fig9 is not None
    assert fig10 is not None
    assert fig11 is not None
    fig9_html = fig9.group(0)
    fig10_html = fig10.group(0)
    fig11_html = fig11.group(0)
    assert 'src="fig9-location-size.jpg"' in fig9_html
    assert 'src="fig10-a.jpg"' not in fig9_html
    assert 'src="fig10-a.jpg"' in fig10_html
    assert 'src="fig10-b.jpg"' in fig10_html
    assert 'src="fig10-c.jpg"' in fig10_html
    assert 'src="fig10-d.jpg"' in fig10_html
    assert 'src="fig11-face-place.jpg"' not in fig10_html
    assert 'src="fig11-face-place.jpg"' in fig11_html
    assert 'href="#fig-9"' in polished


def test_polish_html_document_links_digit_ref_to_roman_one_ocr_caption_target() -> None:
    html = (
        "<html><body>"
        "<p>Figure 1 shows the design of the trial.</p>"
        '<p><img src="_page_3_Figure_2.jpeg"/></p>'
        "<p>Figure I Design of the trial.</p>"
        "<p>Randomisation details continue.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    fig1 = fig1_match.group(0)
    assert 'src="_page_3_Figure_2.jpeg"' in fig1
    assert "Figure I Design of the trial." in fig1
    assert "z2m-missing-figure-warning" not in fig1
    assert 'href="#fig-1"' in polished
    assert "Randomisation details continue." in polished[fig1_match.end() :]


def test_polish_html_document_does_not_steal_following_caption_image_for_roman_one_caption() -> None:
    html = (
        "<html><body>"
        "<p>For a graphical illustration, see Figure 1.</p>"
        "<table><tr><td>0</td><td>10</td><td>20</td><td>30</td></tr>"
        "<tr><td>Cannot do at all</td><td></td><td>Moderately can do</td><td>Highly certain can do</td></tr>"
        "<tr><td colspan=\"4\">Self-efficacy item</td></tr></table>"
        "<p>Figure I This figure displays the self-efficacy scale.</p>"
        "<p>Notes: Used with permission.</p>"
        '<p><img src="_page_22_Figure_1.jpeg"/></p>'
        "<p><b>Figure 2</b> This figure illustrates the care system.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    fig2_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-2")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    fig1_match = re.search(
        r'<div\b(?=[^>]*\bid="fig-1")(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
        polished,
    )
    assert fig1_match is not None
    assert fig2_match is not None
    fig1 = fig1_match.group(0)
    fig2 = fig2_match.group(0)
    assert "<table" in fig1
    assert "Self-efficacy item" in fig1
    assert "Figure I This figure displays the self-efficacy scale." in fig1
    assert "Notes: Used with permission." in fig1
    assert 'src="_page_22_Figure_1.jpeg"' not in fig1
    assert 'src="_page_22_Figure_1.jpeg"' in fig2
    assert "Figure\xa02" in fig2
    assert "z2m-missing-figure-warning" not in fig2
    assert 'href="#fig-1"' in polished


def test_polish_html_document_does_not_anchor_in_text_figure_sentence_before_image() -> None:
    html = (
        "<html><body>"
        "<p>Figure 1 shows the line guide attached to the magnifier.</p>"
        '<p><img src="line-guide.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-1"' not in polished
    assert "z2m-figure-unit" not in polished


def test_polish_html_document_does_not_anchor_standalone_panel_label_before_image() -> None:
    html = (
        "<html><body>"
        "<p>FIG. 2D depicts a top view of the base element.</p>"
        "<p>FIG. 2D</p>"
        '<p><img src="patent-panel.jpg"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="fig-2"' not in polished
    assert "z2m-figure-unit" not in polished


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


def test_polish_html_document_unwraps_broken_internal_semantic_links_after_late_repairs() -> None:
    html = (
        "<html><body>"
        '<p>Comments are shown in Table <a href="#table-5" class="z2m-table-link">5.</a></p>'
        '<p>Some improvement with an adult knee coil. <a href="#page-8-0">Adam et</a> al. (2001).</p>'
        '<p><a href="#custom-missing">custom</a> anchor remains custom.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert 'href="#table-5"' not in polished
    assert 'href="#page-8-0"' not in polished
    assert "Table 5." in compact
    assert "Adam et al. (2001)" in compact
    assert 'href="#custom-missing"' in polished


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


def test_polish_html_document_unwraps_working_author_year_page_fragment_links() -> None:
    html = (
        "<html><body>"
        '<span id="page-14-0"></span>'
        '<p>Retinotopic studies <a href="#page-14-0">(Bandettini,</a> 2009) '
        'and (<a href="#page-14-0">Allman</a> &amp; Kaas, 1971) are cited.</p>'
        '<p>Diffusion work (<a href="#page-14-0">(Basser &amp;</a> Jones, 2002) '
        'and <a href="#page-14-0">Adam et</a> al. (2001) remained author-year text.</p>'
        '<p>Encoding followed (<a href="#page-14-0">Ama</a>no et al. (2009).</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)
    visible = compact.replace("&amp;", "&")

    assert 'id="page-14-0"' in polished
    assert 'href="#page-14-0"' not in polished
    assert "(Bandettini, 2009)" in visible
    assert "(Allman & Kaas, 1971)" in visible
    assert "(Basser & Jones, 2002)" in visible
    assert "Adam et al. (2001)" in visible
    assert "Amano et al. (2009)" in visible


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
        '<p>Plural ranges also unwrap when no semantic target exists in Sections 3.4, 4 and '
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
    assert 'href="#page-8-1"' not in polished


def test_polish_html_document_unwraps_stale_numeric_page_links_for_p33_patterns() -> None:
    html = (
        "<html><body>"
        + "".join(f'<span id="page-{idx}-0"></span>' for idx in range(1, 11))
        + '<p>Participants are summarized in Tab. <a href="#page-1-0">1)</a>.</p>'
        '<p>The prototype is described in Sect. <a href="#page-2-0">2)</a>.</p>'
        '<p>Details appear in Additional File <a href="#page-3-0">5)</a>.</p>'
        '<p>Videos are available in Multimedia Appendices 1 and <a href="#page-4-0">2.</a></p>'
        '<p>The device must satisfy Req. <a href="#page-5-0">2)</a>.</p>'
        '<p>The control signal is read in Listing 4, line <a href="#page-6-0">49)</a>.</p>'
        '<p>The loss function is described with formula <a href="#page-7-0">16.</a></p>'
        '<p>Training remained difficult (Kolarik et al. <a href="#page-8-0">2014;</a> '
        'Worchel et al. 1950).</p>'
        '<p>Several reports support this claim <a href="#page-9-0">37.</a></p>'
        '<p>Video captioning is abbreviated as <a href="#page-10-0">VC</a> in this section.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    compact = re.sub(r"\s+", " ", polished)

    assert "Tab. 1)" in compact
    assert "Sect. 2)" in compact
    assert "Additional File 5)" in compact
    assert "Multimedia Appendices 1 and 2." in compact
    assert "Req. 2)" in compact
    assert "Listing 4, line 49)" in compact
    assert "formula 16." in compact
    assert "Kolarik et al. 2014;" in compact
    assert "claim 37." in compact
    assert "as VC in this section" in compact
    assert 'href="#page-' not in polished


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
    assert 'href="#page-8-4"' not in polished
    assert "Sections 3.4, 4 and 5." in compact
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
        '<p>The first publications concerning this techniqu <a href="#page-4-0">e16,17</a> '
        "demonstrate correct implant position.</p>"
        '<p>Responses were stable in the absence of visual cue <a href="#page-12-0">s14,26</a> '
        '\u2013 <a href="#page-12-0">28.</a></p>'
        '<p>The main subcortical input to the AD <a href="#page-12-0">n12.</a> Future studies continue.</p>'
        '<p>Frequency differences were about 3-60 H <a href="#page-15-0">z12,</a> respectively.</p>'
        '<p>We performed a demixed principal components analysis (dPCA '
        '<a href="#page-10-1">)20</a> to compress the data.</p>'
        "<h4>References</h4>"
        "<ul>"
        + "".join(f"<li>Ref {i}.</li>" for i in range(1, 29))
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
    assert 'technique<sup><a href="#ref-16" class="z2m-ref-link">16</a>,' in compact
    assert '<a href="#ref-17" class="z2m-ref-link">17</a></sup> demonstrate' in compact
    assert 'visual cues<sup><a href="#ref-14" class="z2m-ref-link">14</a>,' in compact
    assert '<a href="#ref-28" class="z2m-ref-link">28.</a></sup>' in compact
    assert 'input to the ADn<sup><a href="#ref-12" class="z2m-ref-link">12</a></sup>.' in compact
    assert '60 Hz<sup><a href="#ref-12" class="z2m-ref-link">12</a></sup>,' in compact
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


def test_polish_html_document_unlinks_author_year_filter_level_number() -> None:
    html = (
        "<html><body>"
        "<p>Prior studies describe the method (Smith, 2010; Jones, 2011; Brown, 2012; "
        "Lee, 2013; Patel, 2014).</p>"
        '<p>The control curves were smoothed with an Olympic filter level <sup>'
        '<a href="#ref-2" class="z2m-ref-link">2</a></sup>). For this experiment, '
        "the sampled signal was retained.</p>"
        "<h4>References</h4>"
        "<ol>"
        "<li id=\"ref-1\">Smith A. Method paper. 2010.</li>"
        "<li id=\"ref-2\">Jones B. Filter paper. 2011.</li>"
        "<li id=\"ref-3\">Brown C. Method paper. 2012.</li>"
        "<li id=\"ref-4\">Lee D. Method paper. 2013.</li>"
        "<li id=\"ref-5\">Patel E. Method paper. 2014.</li>"
        "</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    flat = " ".join(body.split())

    assert 'href="#ref-2"' not in body
    assert "Olympic filter level 2). For this experiment" in flat


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


def test_polish_html_document_repairs_known_replacement_char_symbols() -> None:
    html = (
        "<html><body>"
        '<a href="http://CRAN.R-project.org/package\ufffd=\ufffdnlme">nlme</a>'
        '<a href="https://doi.org/10.1007/s10143-004-\ufffd0337-6">doi</a>'
        "<h4>\ufffd <b>IMPLICATIONS FOR REHABILITATION</b></h4>"
        "<ul><li>\ufffd Higher educational institutions need training.</li></ul>"
        "<table><tr><td>EB1*\ufffd</td><td>Obesity\ufffd</td></tr></table>"
        '<p class="z2m-table-note">\ufffd <b>LB</b>: Late blind \ufffd\ufffd <b>EB</b>: Early blind</p>'
        "<p>Signs with text height &gt; 20 pixels, 11-20 pixels, and \ufffd 10 pixels were red.</p>"
        '<p>obesity as \ufffd27.5 kg/m<sup class="z2m-unit-exp">2</sup> and SVRI '
        '(dynes\ufffdsec\ufffdcm-5\ufffdm<sup class="z2m-unit-exp">2</sup>).</p>'
        "<p><b>systolic blood pressure</b> \ufffd <b>140 mmHg</b> or "
        "<b>diastolic blood pressure</b> \ufffd <b>90 mmHg</b>.</p>"
        "<table><tr><th>Adjusted Model 1\ufffd</th></tr></table><p><sup>\ufffd</sup> Model 1 was adjusted.</p>"
        "<p>Correlations used \ufffd = p <i> &lt; </i> .05; \ufffd\ufffd = p <i> &lt; </i> .01.</p>"
        "<p>The stream line was ca. 80 <i> \\\\m. </i></p>"
        "<p>Retief M, Let\ufffdsosa R. SilkeK\ufffdrcher.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "\ufffd" not in polished
    assert "package=nlme" in polished
    assert "10.1007/s10143-004-0337-6" in polished
    assert "<li>Higher educational institutions need training.</li>" in polished
    assert "EB1**" in polished
    assert "* <b>LB</b>: Late blind ** <b>EB</b>: Early blind" in polished
    assert "and &le; 10 pixels" in polished
    assert "obesity as &ge;27.5 kg/m" in polished
    assert "<b>systolic blood pressure</b> &ge; <b>140 mmHg</b>" in polished
    assert "<b>diastolic blood pressure</b> &ge; <b>90 mmHg</b>" in polished
    assert "Adjusted Model 1*" in polished
    assert "<sup>*</sup> Model 1 was adjusted" in polished
    assert "dynes&middot;sec&middot;cm-5&middot;m" in polished
    assert "* = p <i> &lt; </i> .05; ** = p <i> &lt; </i> .01" in polished
    assert "80 µm." in polished
    assert "Letšosa" in polished
    assert "SilkeKärcher" in polished


def test_polish_html_document_repairs_rollema_scan_replacement_chars() -> None:
    html = (
        "<html><body>"
        "<p>The urinary f lo\ufffd rate and volume of u\ufffdine were measured. "
        "The \"A\ufffdroplethysmograph\" was refined by KAUF\ufffdmN. "
        "For volumes \ufffd 100 ml, output was 10 V/\ufffd 0.02 V and differed by less than \ufffd 3%. "
        "Target markers used (\ufffd) the edge of the grid. Targ\ufffdt points followed.</p>"
        "<p>After a warming-up period of \ufffd h, an error of up to \ufffd 2% was introduced. "
        "The measurement does not exceed \ufffd 2 ml/ s and will rarely exceed \ufffd 2.0 ml/s. "
        "The error : \ufffd 1.0 s, and Qmax was 5.9 \ufffd 3.3 ml/ s.</p>"
        "<p>duration of s;t\ufffdtoms and subjective s\ufffdtoms; duration of s\ufffd111 2toms "
        "and subjective s\ufffdEtoms; rectal 12al\ufffdtion; vesical trabeculat\ufffdon.</p>"
        "<table><tbody><tr><th> patient number </th><th> I </th><th> 2 </th><th> J </th>"
        "<th> \ufffd </th><th> 5 </th></tr><tr> <td> \ufffd </td> <td> 66 </td>"
        "<td> 78 </td></tr><tr><td> duration </td><td> I\ufffd </td></tr>"
        "<tr><td> TURP ( n=13) </td><td> \ufffd\xb7 </td></tr><tr><td> \ufffd </td></tr>"
        "</tbody></table>"
        "<p>blood creatinine (\ufffdmol/1); 98 \ufffdol/1; MAR \ufffdIN; bladder \ufffdicture; "
        "\ufffd (maximum f low rate); co\ufffdtraction; urinary f\ufffdow rate signa\ufffd.</p>"
        "<p>0 \ufffd R<sup>2</sup> :5 l and mean value + 2 SD (x \ufffd 2 SD). "
        "The useful range is 200 ml \ufffd V \ufffd 150 ml. "
        "The relevant percentile discrimination l imi t \ufffd measurements continue.</p>"
        "<ul><li>no further interest in the context of this study \ufffd </li>"
        "<li>measurements are only useful if 200 \ufffd V \ufffd 350 ml ;</li>"
        "<li>the sensitivity is \ufffd x 100% 62% \ufffd</li>"
        "<li>the specificity is * x 100% 75% \ufffd</li>"
        "<li>the percentage of misclassifications is 3 + 2 × 100% = 3 1 % . 8 + 8</li></ul>"
        "<p>Differences ( a \ufffd 0.05). relative!\ufffd low prevalence. "
        "urge prior \ufffdo micturition. (n=SB ; \ufffd m=870). "
        "SD derived o.\ufffd .v. and fitted o.\ufffd.v. to data from ( n\ufffdSB). "
        "T100 ; \ufffd 2 3 .2 s and TQmax ; \ufffd 7 . 6 s. "
        "Limits are given ( y SO\ufffd). The method is mean \ufffd 1 SD.</p>"
        "<p>McNEMAR\ufffds test; 100 ml \ufffd V \ufffd 450 ml; presence was \ufffdresence; "
        "F\ufffdE each \ufffdalected variable; m\ufffdsclassifications; ran\ufffde of V; "
        "4. \ufffd \ufffde variable; 100 \ufffd1 \ufffd V \ufffd 450 ml; "
        "methods used (\ufffd 2.5 % false pos itives).</p>"
        "<p>psychologische re\ufffd\ufffding; 1 0 0 ml \ufffd V \ufffd 450 ml; "
        "binnen \ufffden persoon; (V \ufffd res idu na mictie).</p>"
        "<p>FRIMODT-M\u00a2LLE\ufffd; Bl\ufffdstomningens; North k\ufffderica; MENNINGER, \ufffd. A.; "
        "SAN\ufffdE; \ufffdatho logie; EDW\ufffd\ufffdS; f\ufffdgures and f\ufffdgure; "
        "(d\ufffd/dtlmax; percent\ufffd le.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "\ufffd" not in polished
    assert "flow rate" in polished
    assert "A&euml;roplethysmograph" in polished
    assert "KAUFMAN" in polished
    assert "for volumes &le; 100 ml" in polished
    assert "10 V/&plusmn; 0.02 V" in polished
    assert "less than &plusmn; 3%" in polished
    assert "period of &frac12; h" in polished
    assert "exceed &plusmn; 2 ml/ s" in polished
    assert "age </td> <td> 66" in polished
    assert re.search(r"<th>\s*4\s*</th>", polished)
    assert "<td> 1&frac12; </td>" in polished
    assert "blood creatinine (&micro;mol/l)" in polished
    assert "Qmax (maximum flow rate)" in polished
    assert "0 &le; R<sup>2</sup> &le; 1" in polished
    assert "the sensitivity is 5/8 × 100% = 62%;" in polished
    assert "the specificity is 6/8 × 100% = 75%;" in polished
    assert "(&alpha; = 0.05)" in polished
    assert "(n=58; &Sigma; m=870)" in polished
    assert "o.i.v." in polished
    assert "(&gamma; = 80%)" in polished
    assert "McNEMAR's test" in polished
    assert "100 ml &le; V &le; 450 ml" in polished
    assert "For each selected variable" in polished
    assert "psychologische remming" in polished
    assert "binnen &eacute;&eacute;n persoon" in polished
    assert "FRIMODT-M&Oslash;LLER" in polished
    assert "SAND&Oslash;E" in polished
    assert "EDWARDS" in polished
    assert "(dL/dt)max" in polished
    assert "percentile" in polished


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


def test_polish_html_document_drops_repository_and_publisher_chrome_pages() -> None:
    html = (
        "<html><body>"
        '<p><img src="flore-cover.png"/></p>'
        "<h1>FLORE Repository istituzionale dell'Università degli Studi di Firenze</h1>"
        "<h1><b>Different Strategies for Rapid Prototyping of Digital Bas-Reliefs</b></h1>"
        "<h3>Original Citation:</h3><p>/ M. Carfagni; L. Puggelli.</p>"
        "<p>La data sopra indicata si riferisce al Repository FloRe (Article begins on next page)</p>"
        "<p>Applied Mechanics and Materials Vol. 510 real article starts.</p>"
        "<h1><b>Articles you may be interested in</b></h1>"
        "<p>A handheld fluorescence molecular tomography system for intraoperative optical imaging.</p>"
        "<p>Magnetic resonance-guided near-infrared tomography of the breast.</p>"
        '<p><img src="aip-real-page.png"/></p>'
        '<p><img src="rug-cover.png"/></p>'
        '<h1 class="z2m-front-matter">University of Groningen</h1>'
        "<p>IMPORTANT NOTE: You are advised to consult the publisher's version.</p>"
        "<p>Downloaded from the University of Groningen/UMCG research database.</p>"
        "<p>Download date: 31-10-2022</p>"
        '<p><img src="rug-real-page.png"/></p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "FLORE Repository" not in polished
    assert "Article begins on next page" not in polished
    assert "Articles you may be interested in" not in polished
    assert "University of Groningen" not in polished
    assert "IMPORTANT NOTE" not in polished
    assert "flore-cover.png" not in polished
    assert "rug-cover.png" not in polished
    assert "Applied Mechanics and Materials Vol. 510 real article starts." in polished
    assert "aip-real-page.png" in polished
    assert "rug-real-page.png" in polished


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


def test_polish_html_document_unlinks_author_year_pdf_footnote_definition_refs() -> None:
    html = (
        "<html><body>"
        "<p>Parallelized laboratories used identical configurations and research objectives"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>. '
        "Each laboratory published outputs to the shared archive.</p>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        '<p><span id="page-9-0"></span><math display="inline"><sup>^'
        '<a href="#ref-2" class="z2m-ref-link">2</a></sup></math> '
        "There is no limit to the number of connected systems.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 4))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-2"' not in body
    assert "research objectives<sup>2</sup>" in body
    assert "There is no limit to the number of connected systems" in body


def test_polish_html_document_unlinks_author_year_fraction_and_plain_footnote_defs() -> None:
    html = (
        "<html><body>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<p>The stimulation function was f(I)"
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>/'
        '<a href="#ref-2" class="z2m-ref-link">2</a></sup>, '
        "where I is current and K is a fitting parameter.</p>"
        '<p><span id="page-11-0"></span><sup>'
        '<a href="#ref-1" class="z2m-ref-link">1</a></sup> '
        "A photocoagulation laser was used for the lesion.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 4))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body
    assert "f(I)<sup>1/2</sup>, where I is current" in body
    assert "<sup>1</sup> A photocoagulation laser" in body


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


def test_polish_html_document_unlinks_author_year_numbered_sequences() -> None:
    html = (
        "<html><body>"
        "<p>To guide the model, in experiments "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> and 3, '
        "we compared graphics "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> to 8. '
        "The sessions were scheduled between "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> and 14 days. '
        "The disease was stage "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>. '
        "The error term was (0.2)"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>. '
        "The vibration used tactors "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> and 7 at the same time. '
        "They attended two sessions (sessions "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> and '
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>) of training. '
        "Responses had z score "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>. '
        "The work presents "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>) a review and 2) methods. '
        "Small areas lower than beta / 4"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>) were merged. '
        "The computer requires (6-2)"
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> the entering of data. '
        "The model was used to investigate "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>) validity and 2) value. '
        "The contrast was (luminance 1 - luminance "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>)/(luminance 1 + luminance '
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>). '
        "The caption listed targ "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> and targ '
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>. '
        "The tool should be administered between ages "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> and 3.5 years old.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 4))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body
    assert "experiments 2 and 3" in body
    assert "graphics 1 to 8" in body
    assert "between 2 and 14 days" in body
    assert "stage 2." in body
    assert "(0.2)<sup>2</sup>" in body
    assert "tactors 3 and 7" in body
    assert "sessions 2 and 3) of training" in body
    assert "z score 2." in body
    assert "presents 1) a review and 2) methods" in body
    assert "beta / 4<sup>2</sup>)" in body
    assert "(6-2)<sup>1</sup> the entering of data" in body
    assert "investigate 1) validity and 2) value" in body
    assert "luminance 1 - luminance 2)/(luminance 1 + luminance 2)" in body
    assert "caption listed targ 1 and targ 2" in body
    assert "between ages 1 and 3.5 years old" in body


def test_polish_html_document_unlinks_author_year_decimal_comma_runs() -> None:
    html = (
        "<html><body>"
        "<p>The software Mimics (3-matic v"
        '<sup><a href="#ref-5" class="z2m-ref-link">5</a>,'
        '<a href="#ref-1" class="z2m-ref-link">1</a></sup>) was used. '
        "Targets were at egocentric distances of "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-5" class="z2m-ref-link">5</a></sup>, 3.1, or 6 m. '
        "The audio-extended variant of Qwen"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a>,'
        '<a href="#ref-5" class="z2m-ref-link">5</a></sup> 1.5B was tested. '
        "The diameters of the five comparison discs were "
        '<sup><a href="#ref-5" class="z2m-ref-link">5</a>,'
        '<a href="#ref-1" class="z2m-ref-link">1</a></sup>, 9, and 13.5 cm. '
        "A linear regression resulted in a slope of "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a>,'
        '<a href="#ref-7" class="z2m-ref-link">7</a></sup>.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 8))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-5"' not in body
    assert 'href="#ref-7"' not in body
    assert "3-matic v5.1" in body
    assert "distances of 1.5, 3.1, or 6 m" in body
    assert "Qwen2.5 1.5B" in body
    assert "diameters of the five comparison discs were 5.1, 9" in body
    assert "slope of 2.7" in body


def test_polish_html_document_unlinks_decimal_comma_value_ref_links() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 552))
    html = (
        "<html><body>"
        "<p>The 10-min averages showed dispersion ratio "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a>,'
        '<a href="#ref-1" class="z2m-ref-link">1</a></sup>, '
        "a decline over the course of "
        '<sup><a href="#ref-9" class="z2m-ref-link">9</a>,4</sup>, 10.4, and 31.7 months, '
        "and molecular weight is "
        '<sup><a href="#ref-551" class="z2m-ref-link">551</a>,5</sup>).</p>'
        "<h4>References</h4><ol>"
        + refs
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "dispersion ratio 3.1" in body
    assert "course of 9.4, 10.4, and 31.7 months" in body
    assert "molecular weight is 551.5)" in body
    assert 'href="#ref-1"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-9"' not in body
    assert 'href="#ref-551"' not in body


def test_polish_html_document_unlinks_numeric_value_sup_ref_runs_in_bracket_docs() -> None:
    html = (
        "<html><body>"
        "<p>Prior navigation work used standard methods [1].</p>"
        "<p>The closest obstacle (left at "
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a>,'
        '<a href="#ref-18" class="z2m-ref-link">18</a></sup>8 mm) was highlighted.</p>'
        "<p>The retrieval interval can last "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a>, '
        '<a href="#ref-6" class="z2m-ref-link">6</a></sup> or 9 seconds.</p>'
        "<p>Observers (ages "
        '<sup><a href="#ref-18" class="z2m-ref-link">18</a>\u2013'
        '<a href="#ref-28" class="z2m-ref-link">28</a></sup>) participated.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 29))
        + "</ol></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )
    body = polished[: polished.index("References")]

    assert "left at 4,188 mm" in body
    assert "can last 3, 6 or 9 seconds" in body
    assert "ages 18\u201328" in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-4"' not in body
    assert 'href="#ref-6"' not in body
    assert 'href="#ref-18"' not in body
    assert 'href="#ref-28"' not in body
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in body


def test_polish_html_document_unlinks_approximate_duration_range_ref_link() -> None:
    html = (
        "<html><body>"
        "<p>The drug has an average tmax of approximately "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> to 6 hours '
        "and a half-life of 14 hours.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 4))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "approximately 3 to 6 hours" in body
    assert 'href="#ref-3"' not in body


def test_polish_html_document_unlinks_count_of_total_ref_link() -> None:
    html = (
        "<html><body>"
        "<p>Clinical neurosurgeons have performed or supervised "
        '<sup><a href="#ref-35" class="z2m-ref-link">35</a></sup> of the 78 implants '
        "in our series since 1999. However "
        '<sup><a href="#ref-25" class="z2m-ref-link">25</a></sup> of the arrays '
        "had less than 96 wire-bonded electrodes. One array was failing by day "
        '<sup><a href="#ref-21" class="z2m-ref-link">21</a></sup>.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 36))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "supervised 35 of the 78 implants" in body
    assert "However 25 of the arrays" in body
    assert "failing by day 21." in body
    assert 'href="#ref-21"' not in body
    assert 'href="#ref-25"' not in body
    assert 'href="#ref-35"' not in body


def test_polish_html_document_unlinks_author_year_software_version_refs() -> None:
    html = (
        "<html><body>"
        "<p>The model was implemented in PyTorch version "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-3" class="z2m-ref-link">3</a>,'
        '<a href="#ref-1" class="z2m-ref-link">1</a></sup>, using CUDA driver version '
        '<sup><a href="#ref-10" class="z2m-ref-link">10</a>,'
        '<a href="#ref-2" class="z2m-ref-link">2</a></sup>.</p>'
        "<p>UF is a widely used test for bladder emptying."
        '<sup><a href="#ref-6" class="z2m-ref-link">6</a></sup></p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 11))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "PyTorch version 1.3.1" in body
    assert "CUDA driver version 10.2" in body
    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-10"' not in body
    assert '<sup><a href="#ref-6" class="z2m-ref-link">6</a></sup>' in body


def test_polish_html_document_unlinks_author_year_r_version_refs() -> None:
    html = (
        "<html><body>"
        "<p>All analyses were conducted in R (v "
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a>,'
        '<a href="#ref-3" class="z2m-ref-link">3</a>,'
        '<a href="#ref-2" class="z2m-ref-link">2</a></sup>).</p>'
        "<p>UF is a widely used test for bladder emptying."
        '<sup><a href="#ref-6" class="z2m-ref-link">6</a></sup></p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 7))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "R (v 4.3.2)" in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-4"' not in body
    assert '<sup><a href="#ref-6" class="z2m-ref-link">6</a></sup>' in body


def test_polish_html_document_unlinks_author_year_numbered_study_refs() -> None:
    html = (
        "<html><body>"
        "<p>Performance in Studies 2 and "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> was similar in both groups.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 4))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-3"' not in body
    assert "Studies 2 and 3 was similar" in body


def test_polish_html_document_unlinks_author_year_numbered_experiment_refs() -> None:
    html = (
        "<html><body>"
        "<p>To briefly review the major results of Experiments 1 and "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>: performance changed.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 3))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-2"' not in body
    assert "Experiments 1 and 2: performance changed" in body


def test_polish_html_document_unlinks_author_year_numeric_false_refs_for_counts() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 27))
    html = (
        "<html><body>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        '<p>Subjects counted <sup><a href="#ref-4" class="z2m-ref-link">4</a></sup> '
        "to 12 white squares.</p>"
        "<p>In this study, 16, 14, and "
        '<sup><a href="#ref-20" class="z2m-ref-link">20</a></sup> of congenital blind, '
        "late blind, and sighted individuals were recruited.</p>"
        "<p>Forty patients, 14 with sleep apnoea syndrome and "
        '<sup><a href="#ref-26" class="z2m-ref-link">26</a></sup> with chronic obstructive '
        "pulmonary disease, took part.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-4"' not in body
    assert 'href="#ref-20"' not in body
    assert 'href="#ref-26"' not in body
    assert "counted <sup>4</sup> to 12 white squares" in body
    assert "16, 14, and <sup>20</sup> of congenital blind" in body
    assert "14 with sleep apnoea syndrome and <sup>26</sup> with chronic" in body


def test_polish_html_document_unlinks_author_year_numeric_range_and_equation_labels() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 8))
    html = (
        "<html><body>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        '<p>Earlier prototypes solved tactile output (3 - <a href="#ref-7" '
        'class="z2m-ref-link">7)</a>.</p>'
        '<p><span class="z2m-math z2m-math-inline" role="math">delta V = rho L</span> '
        '<a href="#ref-1" class="z2m-ref-link">[1]</a></p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-7"' not in body
    assert 'href="#ref-1"' not in body
    assert "(3 - 7)" in body
    assert "[1]" in body


def test_polish_html_document_unlinks_author_year_standard_part_and_unit_decimal_refs() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 61))
    html = (
        "<html><body>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<p>Evaluation followed draft annex D of ISO 10993 Part "
        '<sup><a href="#ref-60" class="z2m-ref-link">60</a></sup>) and included pathology.</p>'
        "<p>This means that impedance cardiography may be "
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a>,11</sup>. min<sup>-1</sup> below Fick.</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-60"' not in body
    assert 'href="#ref-4"' not in body
    assert "ISO 10993 Part <sup>60</sup>)" in body
    assert re.search(r"may be <sup>4,11</sup>\. min<sup[^>]*>-1</sup> below Fick", body)


def test_polish_html_document_unlinks_author_year_front_matter_affiliation_marker() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 5))
    html = (
        "<html><body>"
        "<h1>Ambulatory Impedance Cardiography</h1>"
        '<p>Monica J. E. Parry <sup><a href="#ref-4" class="z2m-ref-link">4</a></sup> '
        "Judith McFetridge-Durdle b Background: Standard noninvasive impedance cardiography "
        "has been used in clinical studies.</p>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-4"' not in body
    assert "Parry <sup>4</sup> Judith" in body


def test_polish_html_document_unwraps_single_surname_et_al_author_year_ref_link() -> None:
    refs = "".join(
        (
            '<li id="ref-10">10. Schira, M. M., Tyler, C. W., Breakspear, M., '
            "&amp; Spehar, B. (2009).</li>"
        )
        if idx == 10
        else f'<li id="ref-{idx}">{idx}. Reference.</li>'
        for idx in range(1, 11)
    )
    html = (
        "<html><body>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        '<p>Using high resolution methods, <a href="#ref-10" class="z2m-ref-link">Schira</a> '
        "et al. (2009) traced the angle maps.</p>"
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-10"' not in body
    assert "Schira et al. (2009)" in body


def test_polish_html_document_keeps_numeric_parenthetical_citations_despite_frontmatter_author_year_text() -> None:
    refs = "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 22))
    numeric_citations = "".join(
        f'<p>Numeric citation evidence <a href="#ref-{idx}" class="z2m-ref-link">({idx})</a>.</p>'
        for idx in range(1, 6)
    )
    html = (
        "<html><body>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, Black 2016, "
        "and Green 2015 appear in front matter only.</p>"
        f"{numeric_citations}"
        "<p>Users explore elements through speech descriptions "
        '<a href="#ref-8" class="z2m-ref-link">(8,</a> 9) or vibration feedback '
        '<a href="#ref-10" class="z2m-ref-link">(10)</a>.</p>'
        f"<h4>References</h4><ol>{refs}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-8"' in body
    assert 'href="#ref-10"' in body
    assert "(8," in body


def test_polish_html_document_unlinks_color_label_ref_false_positives() -> None:
    html = (
        "<html><body>"
        "<p>The colors used in Experiment 4 are different from the colors used in Experiment 3. "
        "However, the green used in Experiment 4 is very similar to green"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> in Experiment 3.</p>'
        "<p>The preferred color was predominately a red hue, followed by green hues "
        "(green<sup>1</sup> or green"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a>,'
        '<a href="#ref-15" class="z2m-ref-link">15</a></sup>.6%) and blue hues '
        "(blue1 and blue"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a>,'
        '<a href="#ref-1" class="z2m-ref-link">1</a></sup>.6%).</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 16))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "green<sup>2</sup> in Experiment 3" in body
    assert "green<sup>2</sup>,15.6%" in body
    assert "blue<sup>2</sup>,1.6%" in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-15"' not in body
    assert 'href="#ref-1"' not in body


def test_polish_html_document_keeps_color_word_citation_without_label_context() -> None:
    html = (
        "<html><body>"
        "<p>The sample remained green"
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> after processing.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol><li>Reference one.</li><li>Reference two.</li></ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>' in body


def test_polish_html_document_unlinks_numbered_sequence_ref_in_numeric_article() -> None:
    html = (
        "<html><body>"
        "<p>We designed eight graphics representing train station floor plans, graphics "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> to 8.</p>'
        '<p>Earlier tactile studies <sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> '
        "reported similar tasks.</p>"
        "<h4>References</h4><ol><li>Reference one.</li><li>Reference two.</li></ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "graphics 1 to 8" in body
    assert 'href="#ref-1"' not in body
    assert '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>' in body


def test_polish_html_document_unlinks_numeric_range_endpoint_ref_false_positive() -> None:
    html = (
        "<html><body>"
        "<p>The NBG amplitude values were scaled by the maximum value across all "
        "orientations to range between 0 and "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> for each electrode.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol><li>Reference one.</li></ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "range between 0 and 1 for each electrode" in body
    assert 'href="#ref-1"' not in body


def test_polish_html_document_keeps_numeric_citation_after_range_sentence() -> None:
    html = (
        "<html><body>"
        "<p>The values ranged from 0 to 1."
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup></p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol><li>Reference one.</li></ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-1"' in body


def test_polish_html_document_keeps_author_year_group_citation_lists() -> None:
    html = (
        "<html><body>"
        "<p>Published single-institution case series from our group "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a>,'
        '<a href="#ref-6" class="z2m-ref-link">6</a></sup> and others '
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-10" class="z2m-ref-link">10</a></sup> demonstrated the utility.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 11))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-3" class="z2m-ref-link">3</a>' in body
    assert '<a href="#ref-6" class="z2m-ref-link">6</a>' in body
    assert '<a href="#ref-1" class="z2m-ref-link">1</a>' in body
    assert '<a href="#ref-10" class="z2m-ref-link">10</a>' in body


def test_polish_html_document_unlinks_statistical_superscript_decimal_runs() -> None:
    html = (
        "<html><body>"
        "<p>The effect size in this study was "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-5" class="z2m-ref-link">5</a></sup>, '
        "and the visual acuity was logMAR "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-43" class="z2m-ref-link">43</a></sup>.</p>'
        "<p>The measurements correspond to logMAR 2.00 and "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,'
        '<a href="#ref-43" class="z2m-ref-link">43</a></sup>, respectively.</p>'
        "<p>The recalled content was active M=9.25 (SD "
        '<sup><a href="#ref-5" class="z2m-ref-link">5</a>,'
        '<a href="#ref-71" class="z2m-ref-link">71</a></sup>) '
        "vs. sham M=8.09 (SD "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a>,'
        '<a href="#ref-78" class="z2m-ref-link">78</a></sup>).</p>'
        '<p>The value was inputted into G*Power '
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a>,'
        '<a href="#ref-1" class="z2m-ref-link">1</a></sup>.</p>'
        "<p>Published case series from our group "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a>,'
        '<a href="#ref-6" class="z2m-ref-link">6</a></sup> remained citations.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 44))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "effect size in this study was 1.5" in body
    assert "logMAR 1.43" in body
    assert "logMAR 2.00 and 1.43" in body
    assert "SD 5.71" in body
    assert "SD 3.78" in body
    assert "G*Power 3.1" in body
    assert '<a href="#ref-5" class="z2m-ref-link">5</a>' not in body
    assert '<a href="#ref-43" class="z2m-ref-link">43</a>' not in body
    assert '<a href="#ref-3" class="z2m-ref-link">3</a>,' in body
    assert '<a href="#ref-6" class="z2m-ref-link">6</a>' in body


def test_polish_html_document_unlinks_sample_size_value_refs_but_keeps_citations() -> None:
    html = (
        "<html><body>"
        "<p>The final sample size of the early-blind group was "
        '<sup><a href="#ref-11" class="z2m-ref-link">11</a></sup>.</p>'
        "<p>Sample size was "
        '<sup><a href="#ref-32" class="z2m-ref-link">32</a></sup> to 63.</p>'
        "<p>Effect sizes and attrition rates were similar to those observed in the pilot study."
        '<sup><a href="#ref-21" class="z2m-ref-link">21</a></sup></p>'
        "<p>Our sample size is comparable to previous studies testing the same tasks "
        '<a href="#ref-31" class="z2m-ref-link">31</a>,'
        '<a href="#ref-32" class="z2m-ref-link">32</a>.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 34))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]
    compact = re.sub(r"\s+", " ", body)

    assert 'href="#ref-11"' not in body
    assert "early-blind group was <sup>11</sup>" in compact
    assert "Sample size was <sup>32</sup> to 63" in compact
    assert '<a href="#ref-21" class="z2m-ref-link">21</a>' in body
    assert '<a href="#ref-31" class="z2m-ref-link">31</a>' in body
    assert '<a href="#ref-32" class="z2m-ref-link">32</a>' in body


def test_polish_html_document_unlinks_author_year_enumerated_item_refs() -> None:
    html = (
        "<html><body>"
        "<p>Delay discounting rates are associated with two neural circuits: "
        "1) the executive function network, and "
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>) '
        "the impulsive network.</p>"
        "<p>We carried out two navigation methods using "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>) '
        "DRL and UWB localization, and 2) SLAM and DRL.</p>"
        "<p>Participants completed a questionnaire to understand their "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>) '
        "perceived difficulty of the route, 2) confidence level, and "
        "3) willingness to use the mobility aid.</p>"
        "<p>We evaluated three benchmarks: "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>. GPQA Diamond, '
        "2. MMLU-Pro, and "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>. MedQA.</p>'
        "<p>Alexander et al., 1986; Bickel et al., 2014; Hanlon et al., 2015; "
        "MacKillop and Kahler, 2009 make this an author-year article.</p>"
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 4))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "1) the executive function network, and 2) the impulsive network" in body
    assert "using 1) DRL and UWB localization, and 2) SLAM and DRL" in body
    assert "their 1) perceived difficulty of the route, 2) confidence level" in body
    assert "three benchmarks: 1. GPQA Diamond, 2. MMLU-Pro, and 3. MedQA" in body
    assert 'href="#ref-1"' not in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body


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


def test_polish_html_document_unwraps_year_only_author_year_ref_links() -> None:
    html = (
        "<html><body>"
        '<p>Earlier work (Kellogg <a href="#ref-12" class="z2m-ref-link">1962;</a> '
        'Milne et al. <a href="#ref-12" class="z2m-ref-link">2014a;</a> '
        'Rice and Feinstein <a href="#ref-12" class="z2m-ref-link">1965;</a> '
        'Teng and Whitney <a href="#ref-12" class="z2m-ref-link">2011</a>; '
        'Thaler et al. <a href="#ref-12" class="z2m-ref-link">2014)</a> was cited.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 13))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-12"' not in body
    assert "Kellogg 1962; Milne et al. 2014a; Rice and Feinstein 1965; Teng and Whitney 2011; Thaler et al. 2014)" in body


def test_polish_html_document_unwraps_mismatched_author_year_surname_ref_links() -> None:
    refs = []
    for idx in range(1, 133):
        if idx == 2:
            refs.append('<li id="ref-2">2. Numeric citation target.</li>')
        elif idx == 15:
            refs.append(
                '<li id="ref-15">15. Alireza Ghafarollahi and Markus J Buehler. '
                "Protagents: protein discovery. Digital Discovery, 2025.</li>"
            )
        elif idx == 43:
            refs.append("<li id=\"ref-43\">43. Di Jin et al. Medical exams. Applied Sciences, 2021.</li>")
        elif idx == 117:
            refs.append("<li id=\"ref-117\">117. Tao Tu et al. Towards conversational diagnostic ai. 2024.</li>")
        elif idx == 132:
            refs.append("<li id=\"ref-132\">132. Shunyu Yao et al. React: Synergizing reasoning and acting. 2023b.</li>")
        else:
            refs.append(f'<li id="ref-{idx}">{idx}. Placeholder reference.</li>')
    html = (
        "<html><body>"
        '<p>Transformers (<a href="#ref-117" class="z2m-ref-link">Vaswani</a> (2017)) '
        'and recurrent baselines (<a href="#ref-43" class="z2m-ref-link">Jordan</a> (1997)) '
        'differ from agents <a href="#ref-132" class="z2m-ref-link">Yao et al.</a> (2023b). '
        'Prior audits (<a href="#ref-15" class="z2m-ref-link">Gupta</a> '
        '<a href="#ref-15" class="z2m-ref-link">&amp; Pruthi</a> (2025)) '
        'and review links (<a href="#ref-15" class="z2m-ref-link">(Gupta &amp; Pruthi</a> (2025)) '
        'must not point to unrelated references. '
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup></p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(refs)
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-117"' not in body
    assert 'href="#ref-43"' not in body
    assert 'href="#ref-15"' not in body
    assert "Transformers (Vaswani (2017))" in body
    assert "recurrent baselines (Jordan (1997))" in body
    assert "Prior audits (Gupta &amp; Pruthi (2025))" in body
    assert "review links ((Gupta &amp; Pruthi (2025))" in body
    assert '<a href="#ref-132" class="z2m-ref-link">Yao et al.</a> (2023b)' in body
    assert '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>' in body


def test_polish_html_document_retargets_author_year_fragments_to_matching_references() -> None:
    refs = []
    for idx in range(1, 135):
        if idx == 15:
            refs.append(
                '<li id="ref-15">15. Alireza Ghafarollahi and Markus J Buehler. '
                'Protagents. Digital Discovery, 2024a.</li>'
            )
        elif idx == 23:
            refs.append(
                '<li id="ref-23">23. Tarun Gupta and Danish Pruthi. '
                'All that glitters is not novel. arXiv preprint, 2025.</li>'
            )
        elif idx == 54:
            refs.append(
                '<li id="ref-54">54. Joel Lehman and Kenneth O Stanley. '
                'Novelty search and the problem with objectives. 2011.</li>'
            )
        elif idx == 59:
            refs.append('<li id="ref-59">59. Sihang Li et al. Scilitllm. 2024c.</li>')
        elif idx == 69:
            refs.append(
                '<li id="ref-69">69. Brady D. Lund and K. T. Naheem. '
                'Can chatgpt be an author? Learned Publishing, 2023.</li>'
            )
        elif idx == 132:
            refs.append(
                '<li id="ref-132">132. Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, '
                'Izhak Shafran, Karthik Narasimhan, and Yuan Cao. React: '
                'Synergizing reasoning and acting in language models. 2023b.</li>'
            )
        elif idx == 134:
            refs.append(
                '<li id="ref-134">134. N. Yeo-The and B. L. Tang. '
                'Nlp systems such as chatgpt cannot be listed as an author. 2023.</li>'
            )
        else:
            refs.append(f'<li id="ref-{idx}">{idx}. Placeholder reference.</li>')
    html = (
        "<html><body>"
        '<p>Related work cites <a href="#ref-15" class="z2m-ref-link">(Gupta &amp; Pruthi</a> '
        '(2025), <a href="#ref-59" class="z2m-ref-link">(Lund &amp; Naheem</a> (2023), '
        'and <a href="#ref-132" class="z2m-ref-link">Yeo-The &amp; Tang</a> (2023). '
        'Exploration follows <a href="#ref-43" class="z2m-ref-link">(Lehman &amp; Stanley</a> '
        '(2011), while <a href="#ref-132" class="z2m-ref-link">Yao et al.</a> '
        '(2023b) remains correctly linked.</p>'
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "show that this article uses author-year citations.</p>"
        "<h4>References</h4><ol>"
        + "".join(refs)
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert '<a href="#ref-23" class="z2m-ref-link">(Gupta &amp; Pruthi</a>' in body
    assert '<a href="#ref-69" class="z2m-ref-link">(Lund &amp; Naheem</a>' in body
    assert '<a href="#ref-134" class="z2m-ref-link">Yeo-The &amp; Tang</a>' in body
    assert '<a href="#ref-54" class="z2m-ref-link">(Lehman &amp; Stanley</a>' in body
    assert '<a href="#ref-132" class="z2m-ref-link">Yao et al.</a>' in body
    assert 'href="#ref-15" class="z2m-ref-link">(Gupta' not in body
    assert 'href="#ref-59" class="z2m-ref-link">(Lund' not in body
    assert 'href="#ref-43" class="z2m-ref-link">(Lehman' not in body


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


def test_polish_html_document_unwraps_ph_range_false_links() -> None:
    html = (
        "<html><body>"
        '<p>No major change was observed at pH 4 and <sup><a href="#ref-5" class="z2m-ref-link">5</a></sup> '
        'or at pH 6-<a href="#fig-8" class="z2m-fig-link">8</a>. '
        'The array was implanted in Monkeys 3 and <a href="#fig-4" class="z2m-fig-link">4</a>. '
        'Infusion ran over <sup><a href="#ref-4" class="z2m-ref-link">4</a></sup> to 6 minutes. '
        'Patients had WHO functional classes <sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> '
        'and <sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>, while one cohort had functional class '
        '<sup><a href="#ref-4" class="z2m-ref-link">4</a></sup>. '
        'Signals reached area <sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> first and area '
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> subsequently. '
        'The previous result was reported in 200 <a href="#ref-9" class="z2m-ref-link">9)</a>. '
        'Prior work remains cited<sup><a href="#ref-10" class="z2m-ref-link">10</a></sup>.</p>'
        "<h4>References</h4><ol>"
        + "".join(f"<li>Reference {idx}.</li>" for idx in range(1, 11))
        + "</ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert "pH 4 and 5" in body
    assert "pH 6-8" in body
    assert "Monkeys 3 and 4" in body
    assert "over 4 to 6 minutes" in body
    assert "WHO functional classes 2 and 3" in body
    assert "functional class 4" in body
    assert "area 3 first and area 1 subsequently" in body
    assert "2009)" in body
    assert 'href="#ref-4"' not in body
    assert 'href="#ref-5"' not in body
    assert 'href="#fig-8"' not in body
    assert 'href="#fig-4"' not in body
    assert 'href="#ref-9"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-1"' not in body
    assert 'href="#ref-10"' in body


def test_polish_html_document_repairs_italic_linked_unit_exponent_false_ref() -> None:
    html = (
        "<html><body>"
        '<p>Cone density was 15,000/<i> mm </i> '
        '<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> at the fovea, '
        'fields reached 400 T<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>/m, '
        'and Q=41,253 deg <sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> in a circle.</p>'
        "<h4>References</h4><ol><li>Reference one.</li><li>Reference two.</li></ol></body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")
    body = polished[: polished.index("References")]

    assert 'href="#ref-2"' not in body
    assert '<i> mm </i><sup class="z2m-unit-exp">2</sup>' in body
    assert '400 T<sup class="z2m-unit-exp">2</sup>/m' in body
    assert '41,253 deg<sup class="z2m-unit-exp">2</sup> in a circle' in body


def test_polish_html_document_links_superscript_citations_before_lowercase_continuations() -> None:
    html = (
        "<html><body>"
        "<p>Data generated from a previous study<sup>7,8</sup> was reanalyzed. "
        "Griffiths et al<sup>6</sup> in the form. "
        "Health service use<sup>3,5</sup> than usual care was lower. "
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
    assert 'href="#ref-3"' in body
    assert 'href="#ref-5"' in body
    assert 'previous study<sup><a href="#ref-7" class="z2m-ref-link">7</a>,<a href="#ref-8"' in body
    assert 'Griffiths et al<sup><a href="#ref-6" class="z2m-ref-link">6</a></sup> in' in body
    assert 'use<sup><a href="#ref-3" class="z2m-ref-link">3</a>,<a href="#ref-5"' in body
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
        "<p>The cell toxity was negligible, TlOO minus the baseline was stable, "
        "Qrnax, TQrnax, and Q2sea were measured, London1843 was cited, co verage improved, "
        "and Dokumenty po istor ii fotograf ii was cited.</p>"
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
        "groundtruth backilluminated displaycan EVERYDAYACTIVITIES VoiceCommands singlefinger "
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
    assert "cell toxicity was negligible" in polished
    assert "T100 minus the baseline was stable" in polished
    assert "Qmax, TQmax, and Q2sec were measured" in polished
    assert "London 1843 was cited" in polished
    assert "coverage improved" in polished
    assert "Dokumenty po istorii fotografii" in polished
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
    assert "VoiceCommands single-finger Computer-aided MR-safe MR-compatible in Indian" in polished
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
        "<p>The method proceeded <i>chronologicall</i> y through the experiments.</p>"
        '<p>We specifically incl <a href="#page-7-4">ude</a>, which has to '
        '<a href="#page-7-5">b</a> e interpreted. A <a href="#page-7-6">dd</a> itional '
        'expressi <a href="#page-7-5">ve</a> ness follows. T <a href="#ref-1">his</a> '
        'fact uses CNC-millin <a href="#ref-1">g m</a> achines, supp '
        '<a href="www.agisoft.ru">ort structures in a</a> dditive production, alternati '
        '<a href="#page-7-9">ves</a>, <a href="#page-3-0">pr</a> inting services, '
        'organic diet intervention signifi <a href="#refhub-13">cantly reduces</a> exposure, '
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
    assert "proceeded <i>chronologically</i> through the experiments" in polished
    assert "specifically include, which has to be interpreted" in polished
    assert "Additional expressiveness follows. This fact uses CNC-milling machines" in polished
    assert "support structures in additive production, alternatives, printing services" in polished
    assert 'organic diet intervention significantly <a href="#refhub-13"> reduces</a> exposure' in polished
    assert "technically, high) were, three different, straightforward" in polished
    assert "General digital, and Barcelona" in polished
    assert "Leporini et al.; Ghiani, Leporini &amp; Paterno" in polished
    assert "<code>ob je ct s w ould</code>" in polished
    assert '<a href="https://example.test/B%20rain-computer">B rain-computer</a>' in polished


def test_polish_html_document_repairs_pdf_verified_remaining_intra_word_spaces() -> None:
    html = (
        "<html><body>"
        "<p>References mentioned a virtual environ ment, Behav. Neuro sci., "
        "and Parkin sonism Relat Disord.</p>"
        "<p>The protocol required disconti nuation of the infusion before transport.</p>"
        "<p>RUTHERFO RD, M. cited the Inter national Standard IEC 601-2-19.</p>"
        '<p><a href="https://refhub.example/sref16">Parkin</a>'
        '<a href="https://refhub.example/sref16">sonism Relat. Disorders</a></p>'
        '<p><a href="https://refhub.example/sref17">Effects of age on virtual environ</a>'
        '<a href="https://refhub.example/sref17">ment place navigation and Behav. Neuro</a> sci.</p>'
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "virtual environment" in polished
    assert "Behav. Neurosci." in polished
    assert "Parkinsonism Relat Disord" in polished
    assert "discontinuation of the infusion" in polished
    assert "RUTHERFORD, M. cited the International Standard" in polished
    assert ">Parkinsonism</a>" in polished
    assert ">Effects of age on virtual environment</a>" in polished
    assert "Behav. Neurosci.</a>" in polished


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
        "<p>Critical Rewiev appeared in J Magr Reson Imaging while Urdynamic tests "
        "used electromyograhic tracing.</p>"
        "<p>Apple-like voice controls appeared as Appel's Sir i; masks used the "
        "compliment of the text-area mask.</p>"
        "<p>Hip-pocampus, fascade models, Stocks shift, Object Eden260V, "
        "B Nusssenblatt, and OPRATING PRICIPLE were printed as ARTI CLE TYPE.</p>"
        "<p>Low-Cost Indo Cyanine Green Florescence Technique was cited.</p>"
        '<p>Table terms included TQma<sup class="z2m-table-fn">x</sup>, '
        'PdetQma<a href="#page-3-0">x</a>, and a crania <a href="#page-3-0">l</a> implant.</p>'
        '<p>The sys- <a href="#page-2-0">tem</a> was appro<a href="#page-2-0">x</a>imately ready; '
        'F<a href="#page-2-0">igures</a> showed the result.</p>'
        '<p>Download <a href="https://upload.wikimedia.org/a/SVM_margins.png">'
        "https://upload.wikimedia.org/a/SVM_margins.pngpng</a>.</p>"
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
    assert "Critical review appeared in J Magn Reson Imaging while urodynamic tests" in polished
    assert "used electromyographic tracing" in polished
    assert "Apple-like voice controls appeared as Apple's Siri" in polished
    assert "complement of the text-area mask" in polished
    assert "Hippocampus, facade models, Stokes shift, Objet Eden260V" in polished
    assert "B Nussenblatt, and OPERATING PRINCIPLE were printed as ARTICLE TYPE" in polished
    assert "Low-Cost Indo Cyanine Green Fluorescence Technique" in polished
    assert "Table terms included TQmax, PdetQmax, and a cranial implant" in polished
    assert "The system was approximately ready; Figures showed the result" in polished
    assert (
        '<a href="https://upload.wikimedia.org/a/SVM_margins.png">'
        "https://upload.wikimedia.org/a/SVM_margins.png</a>"
    ) in polished
    assert "IRIT-ELIPSE" in polished


def test_polish_html_document_repairs_second_wave_ocr_residues() -> None:
    html = (
        "<html><body>"
        "<p>For large amplitude oscillations with aspect ratios Dmax=Dminw1:5, "
        "Wherev 2 denotes v T v, 0.999 0995 stayed nearby, and r=0.9 840.</p>"
        "<p>Theexperiment had injuryassociated findings and lower urinary tractfunction symptoms.</p>"
        "<p>The experiment tookplaceinasquare area, delimited bywooden panels. "
        "Thisarearepresented afictitious roomthat hadtobeencoded byparticipants. "
        "Theflooroftheareawasmarked byacolored gridtomonitor movement.</p>"
        "<p>References include benignprostatic hypertrophy, Trends andChallenges in Robot "
        "Manipulation, NeururolUrodyn2021 Mar, and Theeffect in healthyyoung men.</p>"
        "<p>The SoftBankbacked startup used itemspecific spiking, a match-tosample task, "
        "controlrelated activity, intraobject depth values, imageto-image translation, "
        "and realdomain images.</p>"
        "<p>The bladder over distentionon voiding function and suggestiveof abnormal "
        "uroflow references stayed readable.</p>"
        "<p>The AcceptableBladder Capacity reference stayed readable.</p>"
        "<p>The cuetrials result used a trialaverage measure and a textdetection module "
        "for speechballoon areas.</p>"
        "<p>The patient had inflammationat the moment and the sequence held inWM during the task.</p>"
        "<p>The DCM imagedepth pairs used a customdesigned model and a cognitive iter.</p>"
        "<p>sys- tem, telsa, TQma x, PdetQma x, Appel's Sir i, F igures, "
        "appro ximately, PRAVALENCE, Mulitmodal, international continent society, "
        "grade 1\u00bc0-4.9 mm, grade 2\u00bc5-10 mm, grade 3\u00bcmore than 10 mm, "
        "eBDetheque, milivolt, nanomicells, DirectX- R, BOO i, symphisis, "
        "14 C-beled, and Computer Based Method ?.</p>"
        "<p>Wherev <sup>2</sup> stayed split, TQma<sup>x</sup>, PdetQma<sup>x</sup>, "
        'sys-<span id="page-8-0"> </span> tem, and DirectX- <sup>R</sup> remained.</p>'
        "<p>pv0:05, 63 DPhotoWorks, and thev have stayed. The data are coma separated "
        "with a plent of samples at 31.6 8 C. IPelvic organ prolapse, agumentation, "
        "DWT values -2 mm, \u0399mproving access, form eBDtheque, enzymelinked assays, "
        "p, pj]of triangles, Ote this: DO: 10.1039/example, and If inal remained.</p>"
        "<p>Residual P71 tokens included pv0:001, linearly seperable data, "
        "E clarity of their design, b5223 magnification, Routeledge, Build-in sensors, "
        "Shepadex columns, sequence4 acquisition, room temperation, purposed work, "
        "425 cmH2O, 460 bpm, and Archelological exploration.</p>"
        "<p>More residual P71 tokens included validtation accuracy, 0:5mLs{ 1 mm{ 1, "
        "a 9 m m dot, IPP Grade iii, Gen-A i tools, trimetylsilyl ether, FA 330, "
        "around287.8 eV, millitres, 368C, rst few days, and Museum of Moden Art.</p>"
        "<p>HTML-shaped P71 residues included 0:5mLs{ <sup>1</sup> mm{ <sup>1</sup>, "
        "a 9 <sup>m</sup> m dot, IPP Grade<sup class=\"z2m-table-fn\">iii</sup>, "
        "and Gen-A<sup class=\"z2m-table-fn\">i</sup>.</p>"
        "<p>We attempeted to detecte MB in a Time verses Flow Rate ghraph after "
        "recovering the dihydroxyated active form.</p>"
        "<p>More recurring OCR tokens: a health male volunteer, Dl5660620 nm, Cvalli, "
        "Authers, afrer 5 min, and a defensen protein.</p>"
        "<p>Other recurring OCR tokens: (Rgiht), tranformed analytes, and et nl. references.</p>"
        "<p>Reference OCR tokens: Verebrate Endocrinology, Naturwissenschaftem, "
        "Foundayion, and millenium.</p>"
        "<p>Assay OCR tokens: coditions imlied oberved occurance with realtive speices "
        "that responsed in a treaditional way. Furhtermore, Electronic(Cambridge appeared.</p>"
        "<p>Split italic residue kept BOO <i>i</i> in a table-like row.</p>"
        '<p>Reference split reached r=0.9 <a href="#ref-9">526 30 31 33 52)</a>. '
        "Solid .999 fine silver sheet (left)999 fine silver clad copper (right). "
        "The symptom hispareunia stayed in the abstract.</p>"
        "<table><tr><td>A 40-grain bath contains appro </td><td> ximately 8.25% "
        "by weight.</td></tr></table>"
        '<table><tr><th></th><th>Avo<sup class="z2m-table-fn">i</sup></th>'
        "<th>irdupois</th><th>Metric</th></tr></table>"
        "<p><i>Actual temperatures were 31.6 </i> 8 <i> C and 35.9 </i> 8 <i> C.</i></p>"
        "<p>Algorithm uses VoiceCommands and AIType.</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "aspect ratios Dmax/Dmin > 1.5, Where v^2 denotes v T v" in polished
    assert "0.999 0.995 stayed nearby, and r=0.9840" in polished
    assert "The experiment had injury-associated findings and lower urinary tract function symptoms" in polished
    assert "took place in a square area, delimited by wooden panels" in polished
    assert "This area represented a fictitious room that had to be encoded by participants" in polished
    assert "The floor of the area was marked by a colored grid to monitor movement" in polished
    assert "benign prostatic hypertrophy, Trends and Challenges in Robot Manipulation" in polished
    assert "Neurourol Urodyn 2021 Mar, and The effect in healthy young men" in polished
    assert "SoftBank-backed startup used item-specific spiking, a match-to-sample task" in polished
    assert "control-related activity, intra-object depth values, image-to-image translation" in polished
    assert "and real domain images" in polished
    assert "bladder over distention on voiding function" in polished
    assert "suggestive of abnormal uroflow" in polished
    assert "Acceptable Bladder Capacity reference" in polished
    assert "cue trials result used a trial average measure" in polished
    assert "text-detection module for speech-balloon areas" in polished
    assert "inflammation at the moment and the sequence held in WM" in polished
    assert "image-depth pairs used a custom-designed model and a cognitive filter" in polished
    assert "system, tesla, TQmax, PdetQmax, Apple's Siri, Figures" in polished
    assert "approximately, PREVALENCE, Multimodal, International Continence Society" in polished
    assert "grade 1 = 0-4.9 mm, grade 2 = 5-10 mm, grade 3 = more than 10 mm" in polished
    assert "eBDtheque, millivolt, nanomicelles, DirectX-R, BOOI, symphysis" in polished
    assert "14C-labeled, and Computer Based Method?" in polished
    assert "Where v<sup>2</sup> stayed split, TQmax, PdetQmax" in polished
    assert "system, and DirectX-R remained" in polished
    assert "p<0.05, 3DPhotoWorks, and they have stayed" in polished
    assert "comma-separated with plenty of samples at 31.6 °C" in polished
    assert "Pelvic organ prolapse, augmentation, DWT values >2 mm" in polished
    assert "Improving access, from eBDtheque, enzyme-linked assays" in polished
    assert "p, pj] of triangles, Cite this: doi:" in polished
    assert "10.1039/example" in polished
    assert "and I_final remained" in polished
    assert "p<0.001, linearly separable data" in polished
    assert "The clarity of their design, b=223 magnification, Routledge, Built-in sensors" in polished
    assert "Sephadex columns, sequence 4 acquisition, room temperature, proposed work" in polished
    assert ">25 cmH2O, >60 bpm, and Archaeological exploration" in polished
    assert 'validation accuracy, 0.5 mL s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert 'mm<sup class="z2m-unit-exp">-1</sup>' in polished
    assert "a 9 mm dot, IPP Grade III, Gen-AI tools, trimethylsilyl ether, FA 33°" in polished
    assert 'HTML-shaped P71 residues included 0.5 mL s<sup class="z2m-unit-exp">-1</sup>' in polished
    assert "a 9 mm dot, IPP Grade III, and Gen-AI" in polished
    assert "We attempted to detect MB in a Time versus Flow Rate graph" in polished
    assert "recovering the dihydroxylated active form" in polished
    assert "a healthy male volunteer, Delta lambda=660 +/- 20 nm, Cavalli" in polished
    assert "Authors, after 5 min, and a defensin protein" in polished
    assert "Other recurring OCR tokens: (Right), transformed analytes, and et al. references" in polished
    assert "Vertebrate Endocrinology, Naturwissenschaften, Foundation, and millennium" in polished
    assert "Assay OCR tokens: conditions implied observed occurrence with relative species" in polished
    assert "that responded in a traditional way. Furthermore, Electronics (Cambridge appeared" in polished
    assert "around 287.8 eV, millilitres, 36.8 °C, first few days" in polished
    assert "Museum of Modern Art" in polished
    assert "kept BOOI in a table-like row" in polished
    assert "r=0.9526 30 31 33 52)" in polished
    assert "sheet (left). .999 fine silver clad copper" in polished
    assert "symptom dyspareunia stayed in the abstract" in polished
    assert "contains approximately</td><td> 8.25% by weight" in polished
    assert '<th colspan="2">Avoirdupois</th>' in polished
    assert "Actual temperatures were 31.6 °C and 35.9 °C" in polished
    assert "Algorithm uses VoiceCommands and AIType" in polished
    assert "Dmax=Dminw1:5" not in polished
    assert "theexperiment" not in polished.lower()
    assert "voice commands" not in polished.lower()


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
        "Rodr\u0412\u00b4\u0414\u00b1guez, Bedan\u041b\u045ao, na\u0412\u00a8\u0414\u00b1ve, "
        "Gru\u0412\u00a8nbaum, Lu\u0412\u00a8tzner, Sao\u041b\u045a Lu\u0412\u00b4\u0414\u00b1s, "
        "Negra\u041b\u045ao, Svens\u041b\u2021ek, Cl\u0414\u00b1\u0412\u00b4nico, "
        "interpre- \u0412\u00b4 tation, and Schmitz- \u0412\u00a8 Rode appeared. "
        "Fern\u00b4andez, Smorawin\u00b4ski, Lubin\u00b4ska, Rodr\u00b4\u0131guez, "
        "Mart\u0131\u00b4nez, Sa\u0131\u00a8d, Lema\u02c6\u0131tre, Carri\u00b8co, "
        "Sertba\u00b8s, Ag- \u00b4 gregating, au- \u00b4 toencoders, "
        "Green- \u00a8 berg, Bar- \u00b4 ranco, Abbreviations \u00b4 Symbol, "
        "and or \u00b4 both were also present. Re \u00b4 flective notes cited "
        '<a href="#ref-1" data-name="Fern\u0412\u0491andez">Fern\u0412\u0491andez et al.</a>, '
        '<a href="#ref-2">Gru\u0412\u00a8nbaum, Fa\u0412\u0451canha, '
        "Ideggyo\u0412\u0491gya\u0412\u0491szati, and Mohand-Sa\u0414\u00b1\u0412\u00a8d</a>. "
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
    assert "Rodr\u00edguez, Beda\u00f1o, na\u00efve" in polished
    assert "Gr\u00fcnbaum, L\u00fctzner, S\u00e3o Lu\u00eds" in polished
    assert "Negr\u00e3o, Sven\u0161ek, Cl\u00ednico" in polished
    assert "interpretation, and Schmitz-Rode appeared" in polished
    assert "Fern\u00e1ndez, Smorawi\u0144ski, Lubi\u0144ska, Rodr\u00edguez" in polished
    assert "Mart\u00ednez, Sa\u00efd, Lema\u00eetre, Carri\u00e7o, Sertba\u015f" in polished
    assert "Aggregating, autoencoders, Greenberg, Barranco" in polished
    assert "Abbreviations Symbol, and or both were also present" in polished
    assert "Reflective notes cited" in polished
    assert 'data-name="Fern\u0412\u0491andez"' in polished
    assert '>Fern\u00e1ndez et al.</a>' in polished
    assert ">Gr\u00fcnbaum, Fa\u00e7anha, Ideggy\u00f3gy\u00e1szati, and Mohand-Sa\u00efd</a>" in polished
    assert "qualitative colour palettes and present <i> active </i> modes" in polished
    assert 'href="https://orcid.org/0000-0001-8665-1362">Karolina Pakenait\u0117</a>' in polished
    assert 'data-name="fac\u0412\u0451ade"' in polished
    assert "<code>fac\u0412\u0451ade O\u0412\u0491Donnell</code>" in polished
    assert "<pre>Sch\u0412\u0401afer</pre>" in polished


def test_latin_detached_accent_repair_handles_plain_dot_above() -> None:
    html = (
        "<html><body>"
        "<p>ACM Reference Format: Karolina Pakenait \u02d9 e, "
        "Adwait Sharma, \u02d9 and Peter Hall.</p>"
        "<p>Pakenait \u02d9 e\u02d9 et al. detected salient objects.</p>"
        '<li id="ref-42">Karolina Pakenait \u02d9 e and Peter M \u02d9 Hall.</li>'
        "</body></html>"
    )

    repaired = _repair_latin_detached_accent_artifacts_in_visible_text(html)

    assert "Pakenait\u0117" in repaired
    assert "Pakenait \u02d9 e" not in repaired
    assert "Peter M. Hall" in repaired
    assert "\u02d9 and Peter Hall" not in repaired


def test_latin_detached_accent_repair_converts_arcminute_symbol() -> None:
    html = (
        "<html><body>"
        "<h4><b>Abbreviations</b></h4>"
        "<p>\u0412\u0491 Symbol for minutes of arc DBS Deep brain stimulation</p>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert "\u2032 Symbol for minutes of arc DBS" in polished
    assert "\u00b4 Symbol for minutes of arc" not in polished


def test_large_html_known_word_glue_repairs_safe_ligature_phrases() -> None:
    html = (
        "<html><body>"
        "<p>The old scan reported slow urine ow rates and a white ght stimulus. "
        "It signifi cantly used a fuorescent tube in Urofowmetery studies with a urofowmeter. "
        "The suf cient battery powered fowmeters had bene ts. "
        "Insuf cient fluid fowed above low fowrates with clinical signifcance.</p>"
        "<code>urine ow should stay in code</code>"
        + (" " * 500001)
        + "</body></html>"
    )

    repaired = _repair_known_word_glue(html)

    assert "urine flow rates" in repaired
    assert "white light stimulus" in repaired
    assert "significantly used a fluorescent tube in Uroflowmetry studies with a uroflowmeter" in repaired
    assert "sufficient battery powered flowmeters" in repaired
    assert "had benefits" in repaired
    assert "Insufficient fluid flowed above low flow rates with clinical significance" in repaired
    assert "<code>urine ow should stay in code</code>" in repaired


def test_large_html_known_word_glue_repairs_old_scan_ocr_residues() -> None:
    html = (
        "<html><body>"
        "<p>EARLY DETECTION CAUSED BY PROTRUDED LUMBAH I - i. "
        "The (!I G :. nosis result t L ' n normal electromyogram of the perineal muschnr:. "
        "Before TURP: v&amp;me 328 ml; After TVRP: pleak flow 5.8 ml. "
        "Figure 3 noted U-W vertebrae and questioned 4y6-8. "
        "Vesicaf dysfunction, J Ural, lumbar snine, Surg Gvnecol Obstet @e3), "
        "disc orolanse, I Bone Point Sure, Bvadley.</p>"
        "<p>Tilting the sections of the coil to foriTi 110 rather than 180 increases "
        "the magnitude of the stimulus.d/T./Sz. Unit: kcounl/mg prolan, "
        "Lndferase activity was determitied from the iiiiegfiited lummesceoce yield. "
        "The elTicacy was noted while linearmotor S~pole aller the N-pole repels.</p>"
        "<p>It isl part of the brochure, not aJways demonstrale the enor· mous range. "
        "Use riSing fronts to property center the image. A charaCleriza· lion covers "
        "Llnhof Master Te&lt;:hnlka and Unhol Kafdan Mastel TL. From inli nily to "
        "out of locus, the smallest I-SlOP follows the ScheimplJug rule. "
        "Three companson ShOIS describe a particularimagedislance. "
        "IndMdual OUlldlngs gelloreground and background around a subjecl; "
        "this pocIure from slreellevel can eleminate errors with sufiicient "
        "millimelers for aillinhof-supplied specificions.</p>"
        "<p>Mu&amp;es de la Ville de Paris, Mu&amp;e Zadkine, Valentin Haiiy, The Cruc$xion, "
        "and enough P to bc familiar.</p>"
        "<p>Methods of measzu'ing the volume/weight as a fww-cion of time. "
        "Ai1• displacement pl'inuipZe. A contin,Ious curve and Gra1Jimetry. "
        "OVerfLow method, Timing prinaip Ze, uroflowrneter, Uroflowrnetry, "
        "RotCDTleter, PsyahoZogiaaZ, bZood chemistry, ResiduaZ urine, "
        "MuZtiphasicity, estabZishment of reference vaZues, variabZes and abiZities. "
        "A!Jstract, vuiation, measwe, Druck/Fiow.</p>"
        "<code>foriTi and It isl should stay in code</code>"
        + (" " * 500001)
        + "</body></html>"
    )

    repaired = _repair_known_word_glue(html)

    assert "PROTRUDED LUMBAR DISC" in repaired
    assert "diagnosis resulted in normal electromyogram of the perineal musculature." in repaired
    assert "volume 328 ml; After TURP: peak flow" in repaired
    assert "L4-L5 vertebrae and questioned 4,6-8" in repaired
    assert "Vesical dysfunction, J Urol, lumbar spine, Surg Gynecol Obstet (1963)" in repaired
    assert "disc prolapse, J Bone Joint Surg, Bradley" in repaired
    assert "form 110 rather than 180 increases the magnitude of the stimulus dEz/dz" in repaired
    assert "kcount/mg protein, Luciferase activity was determined from the integrated luminescence yield" in repaired
    assert "The efficacy was noted while linearmotor S-pole after the N-pole repels" in repaired
    assert "It is part of the brochure, not always demonstrate the enormous range" in repaired
    assert "rising fronts to properly center the image" in repaired
    assert "characterization covers Linhof Master Technika and Linhof Kardan Master TL" in repaired
    assert "From infinity to out of focus, the smallest f-stop follows the Scheimpflug rule" in repaired
    assert "Three comparison shots describe a particular image distance" in repaired
    assert "Individual buildings get foreground and background around a subject" in repaired
    assert "this picture from street level can eliminate errors with sufficient millimeters" in repaired
    assert "all Linhof-supplied specifications" in repaired
    assert "Musées de la Ville de Paris, Musée Zadkine, Valentin Haüy, The Crucifixion" in repaired
    assert "enough to be familiar" in repaired
    assert "Methods of measuring the volume/weight as a function of time" in repaired
    assert "Air displacement principle" in repaired
    assert "A continuous curve and Gravimetry" in repaired
    assert "Overflow method, Timing principle, uroflowmeter, Uroflowmetry" in repaired
    assert "Rotameter, Psychological, blood chemistry, Residual urine" in repaired
    assert "Multiphasicity, establishment of reference values, variables and abilities" in repaired
    assert "Abstract, variation, measure, Druck/Flow" in repaired
    assert "<code>foriTi and It isl should stay in code</code>" in repaired


def test_large_html_known_word_glue_repairs_residual_p71_tokens() -> None:
    html = (
        "<html><body>"
        "<p>The dissertation proceeds chronologicall y. "
        "The method proceeds <i>chronologicall</i> y through the archive. "
        "Centre Canadien d'Archtecture and A Woodsawer's Nooning were cited. "
        "The subject is classifified as positive after an inital test. "
        "Variables Qrnax, TQrnax, Q2sea, and TlOO were measured. "
        "London1843 and co verage appeared in references.</p>"
        "<code>chronologicall y and classifified should stay in code</code>"
        + (" " * 500001)
        + "</body></html>"
    )

    repaired = _repair_known_word_glue(html)

    assert "proceeds chronologically" in repaired
    assert "proceeds <i>chronologically</i> through the archive" in repaired
    assert "Centre Canadien d'Architecture" in repaired
    assert "A Woodsawyer's Nooning" in repaired
    assert "classified as positive after an initial test" in repaired
    assert "Variables Qmax, TQmax, Q2sec, and T100 were measured" in repaired
    assert "London 1843 and coverage appeared" in repaired
    assert "<code>chronologicall y and classifified should stay in code</code>" in repaired


def test_large_html_false_sup_repair_unlinks_statistical_r_squared() -> None:
    html = (
        "<html><body>"
        '<p>The higher the value of R <sup> <a href="#ref-2" class="z2m-ref-link">2</a> '
        "</sup>, the better the regression line fits.</p>"
        + (" " * 500001)
        + "</body></html>"
    )

    repaired = _fix_false_sup_citations_in_decimals_and_figure_labels(html)

    assert 'href="#ref-2"' not in repaired
    assert "R <sup>2</sup>" in repaired


def test_large_html_false_sup_repair_unlinks_cortical_layer_number() -> None:
    html = (
        "<html><body>"
        "<p>FIG. 13. The molecular layer (cortical layer "
        '<sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>) remained intact.</p>'
        + (" " * 500001)
        + "</body></html>"
    )

    repaired = _fix_false_sup_citations_in_decimals_and_figure_labels(html)

    assert 'href="#ref-1"' not in repaired
    assert "cortical layer 1) remained intact" in repaired


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
