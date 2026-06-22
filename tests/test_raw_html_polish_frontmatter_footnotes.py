from pdf_html_polish.raw_html_polish.frontmatter_footnotes import (
    footnote_keywords,
    leading_footnote_number,
    looks_affiliation_label_body,
    looks_author_byline_front_matter,
    looks_author_marker_ocr_candidate,
    looks_footnote_block,
    looks_front_matter_block,
    mark_front_matter_paragraphs,
    mark_footnote_paragraphs_and_refs,
    normalize_front_matter_marker_numbers,
    repair_affiliation_label_ocr_body,
    repair_author_marker_ocr_body,
    repair_front_matter_marker_ocr,
    repair_front_matter_page_anchor_markers,
    repair_page_footnote_ref_links,
    split_url_footnote_prose_tails,
    unicode_capitalized_name_pair_count,
    unicode_glued_author_marker_count,
    valid_front_matter_marker_numbers,
)


def test_unicode_capitalized_name_pair_count_handles_non_ascii_names() -> None:
    assert unicode_capitalized_name_pair_count("Cem Yucel, Murat Ucar and Erhan Ates") == 3


def test_unicode_glued_author_marker_count_detects_marker_runs() -> None:
    assert unicode_glued_author_marker_count("Alice Smith1, Bob Jones2, Carol Roe3") == 3


def test_looks_author_byline_front_matter_accepts_superscript_author_line() -> None:
    raw = "<p>Alice Smith<sup>1</sup>, Bob Jones<sup>2</sup></p>"
    visible = "Alice Smith 1, Bob Jones 2"

    assert looks_author_byline_front_matter(raw, visible)


def test_looks_author_byline_front_matter_rejects_body_sentence() -> None:
    raw = "<p>Participants used figure 2 during the study.</p>"
    visible = "Participants used figure 2 during the study."

    assert not looks_author_byline_front_matter(raw, visible)


def test_looks_author_marker_ocr_candidate_detects_glued_front_matter_markers() -> None:
    raw = "<p>Alice Smith1, Bob Jones2, Carol Roe3</p>"

    assert looks_author_marker_ocr_candidate(raw)


def test_looks_author_marker_ocr_candidate_rejects_publication_dates() -> None:
    raw = "<p>Received 10.12.2024. Accepted after review.</p>"

    assert not looks_author_marker_ocr_candidate(raw)


def test_looks_affiliation_label_body_detects_institution_text() -> None:
    assert looks_affiliation_label_body("1Department of Biomedical Engineering")
    assert not looks_affiliation_label_body("1Participants completed the trial")


def test_leading_footnote_number_reads_sup_and_plain_prefixes() -> None:
    assert leading_footnote_number('<p><span id="page-1"></span><sup>2</sup> Note text.</p>') == 2
    assert leading_footnote_number("<p>3 https://example.org note.</p>") == 3
    assert leading_footnote_number("<div><sup>1</sup> Not a paragraph.</div>") is None


def test_footnote_keywords_uses_long_non_stop_words() -> None:
    assert footnote_keywords("1 Tensile strength material appears before testing") == {
        "tensile",
        "strength",
        "appears",
        "testing",
    }


def test_looks_footnote_block_accepts_notes_and_rejects_captions() -> None:
    raw = "<p><sup>1</sup> Tensile strength is determined by materials testing methods for polymers.</p>"

    assert looks_footnote_block(
        raw,
        figure_caption_num_from_visible=lambda _text: None,
        table_caption_key_from_visible=lambda _text: None,
    )
    assert not looks_footnote_block(
        raw,
        figure_caption_num_from_visible=lambda _text: 1,
        table_caption_key_from_visible=lambda _text: None,
    )


def test_looks_front_matter_block_uses_affiliation_callback() -> None:
    assert looks_front_matter_block(
        "<p>Plain institutional line.</p>",
        looks_affiliation_block=lambda _raw: True,
    )


def test_looks_front_matter_block_accepts_keywords_and_rejects_intro() -> None:
    assert looks_front_matter_block(
        "<p>Keywords: navigation, mobility</p>",
        looks_affiliation_block=lambda _raw: False,
    )
    assert not looks_front_matter_block(
        "<p>Introduction This starts the paper.</p>",
        looks_affiliation_block=lambda _raw: False,
    )


def test_looks_front_matter_block_accepts_author_byline() -> None:
    raw = "<p>Alice Smith<sup>1</sup>, Bob Jones<sup>2</sup></p>"

    assert looks_front_matter_block(raw, looks_affiliation_block=lambda _raw: False)


def test_mark_footnote_paragraphs_and_refs_marks_definition_and_matching_ref() -> None:
    html = (
        "<p>Low tensile strength<sup>1</sup> remains important.</p>"
        "<p><sup>1</sup> Tensile strength is determined by materials testing methods.</p>"
    )

    marked = mark_footnote_paragraphs_and_refs(
        html,
        figure_caption_num_from_visible=lambda _text: None,
        table_caption_key_from_visible=lambda _text: None,
        citation_tag_is_protected=lambda _open_tag: False,
        numeric_superscript_context_allows_citation=lambda _body, _start, _end: True,
    )

    assert 'class="z2m-footnote"' in marked
    assert 'id="footnote-1"' in marked
    assert 'strength<sup class="z2m-footnote-ref">1</sup>' in marked


def test_mark_footnote_paragraphs_and_refs_skips_protected_ref_blocks() -> None:
    html = (
        "<p class=\"z2m-front-matter\">Low tensile strength<sup>1</sup>.</p>"
        "<p><sup>1</sup> Tensile strength is determined by materials testing methods.</p>"
    )

    marked = mark_footnote_paragraphs_and_refs(
        html,
        figure_caption_num_from_visible=lambda _text: None,
        table_caption_key_from_visible=lambda _text: None,
        citation_tag_is_protected=lambda open_tag: "z2m-front-matter" in open_tag,
        numeric_superscript_context_allows_citation=lambda _body, _start, _end: True,
    )

    assert 'class="z2m-front-matter">Low tensile strength<sup>1</sup>' in marked


def test_repair_page_footnote_ref_links_restores_page_linked_marker() -> None:
    html = (
        '<p>Low tensile strength <a href="#page-7">x1</a> remains important.</p>'
        '<p class="z2m-footnote"><span id="page-7"></span><sup>1</sup> '
        "Tensile strength is determined by materials testing methods.</p>"
    )

    repaired = repair_page_footnote_ref_links(html)

    assert 'strengthx<sup class="z2m-footnote-ref">1</sup> remains' in repaired


def test_repair_page_footnote_ref_links_leaves_unmatched_page_links() -> None:
    html = (
        '<p>Low tensile strength <a href="#page-8">1</a> remains important.</p>'
        '<p class="z2m-footnote"><span id="page-7"></span><sup>1</sup> '
        "Tensile strength is determined by materials testing methods.</p>"
    )

    assert repair_page_footnote_ref_links(html) == html


def test_split_url_footnote_prose_tails_detaches_long_body_tail() -> None:
    tail = (
        "This paragraph continues with enough ordinary prose words to make the "
        "tail look like article body content rather than a footnote fragment."
    )
    html = (
        '<p class="z2m-footnote"><span id="page-2"></span>'
        '<a href="https://example.org">1 https://example.org</a> '
        f"{tail}</p>"
    )

    split = split_url_footnote_prose_tails(html)

    assert '<p class="z2m-footnote"><span id="page-2"></span><a href="https://example.org">1 https://example.org</a></p>' in split
    assert f'<p block-type="Text">{tail}</p>' in split


def test_split_url_footnote_prose_tails_keeps_short_tails() -> None:
    html = (
        '<p class="z2m-footnote"><a href="https://example.org">'
        "1 https://example.org</a> Short note.</p>"
    )

    assert split_url_footnote_prose_tails(html) == html


def test_repair_front_matter_marker_ocr_repairs_author_and_affiliation_blocks() -> None:
    html = (
        '<p class="z2m-front-matter">Alice Smith1, Bob Jones2, Carol Roe3</p>'
        '<p class="z2m-affiliations">1Department of A. 2University of B</p>'
    )

    repaired = repair_front_matter_marker_ocr(
        html,
        looks_like_ocr_split_word_join=lambda _word, _letter: False,
    )

    assert "Alice Smith<sup>1</sup>, Bob Jones<sup>2</sup>, Carol Roe<sup>3</sup>" in repaired
    assert "<sup>1</sup>Department of A. <sup>2</sup>University of B" in repaired


def test_repair_front_matter_marker_ocr_repairs_affiliation_list_items() -> None:
    html = "<ul><li>1Department of A. 2University of B</li></ul>"

    repaired = repair_front_matter_marker_ocr(
        html,
        looks_like_ocr_split_word_join=lambda _word, _letter: False,
    )

    assert "<li><sup>1</sup>Department of A. <sup>2</sup>University of B</li>" in repaired


def test_mark_front_matter_paragraphs_uses_callback() -> None:
    html = "<p>Keywords: mobility</p><p>Body paragraph.</p>"

    marked = mark_front_matter_paragraphs(
        html,
        looks_front_matter_block=lambda raw: "Keywords:" in raw,
    )

    assert '<p class="z2m-front-matter">Keywords: mobility</p>' in marked
    assert "<p>Body paragraph.</p>" in marked


def test_mark_front_matter_paragraphs_respects_block_limit() -> None:
    html = "".join(f"<p>Front {idx}</p>" for idx in range(42))

    marked = mark_front_matter_paragraphs(
        html,
        looks_front_matter_block=lambda _raw: True,
        max_front_matter_blocks=1,
    )

    assert marked.count("z2m-front-matter") == 1


def test_normalize_front_matter_marker_numbers_compacts_separator_noise() -> None:
    assert normalize_front_matter_marker_numbers("1, 02; x9") == "1,02,9"


def test_valid_front_matter_marker_numbers_rejects_out_of_range_values() -> None:
    assert valid_front_matter_marker_numbers("1, 30") == "1,30"
    assert valid_front_matter_marker_numbers("0, 2") is None
    assert valid_front_matter_marker_numbers("31") is None


def test_repair_front_matter_page_anchor_markers_uses_word_join_callback() -> None:
    body = 'Alic<a href="#page-1">e1,2</a>, <a href="#page-1">3</a>'

    repaired = repair_front_matter_page_anchor_markers(
        body,
        looks_like_ocr_split_word_join=lambda word, letter: word == "Alic" and letter == "e",
    )

    assert repaired == "Alice<sup>1,2</sup>, <sup>3</sup>"


def test_repair_front_matter_page_anchor_markers_preserves_untrusted_glue() -> None:
    body = 'Topic<a href="#page-1">x31</a>'

    repaired = repair_front_matter_page_anchor_markers(
        body,
        looks_like_ocr_split_word_join=lambda _word, _letter: False,
    )

    assert repaired == body


def test_repair_author_marker_ocr_body_converts_glued_author_numbers() -> None:
    body = "Alice Smith \u00a91, Bob Jones 2 3*"

    assert repair_author_marker_ocr_body(body) == (
        "Alice Smith<sup>1</sup>, Bob Jones<sup>2,3</sup>*"
    )


def test_repair_author_marker_ocr_body_preserves_existing_sup_spacing() -> None:
    body = "Alice Smith <sup>1</sup>, Bob Jones 2"

    assert repair_author_marker_ocr_body(body) == (
        "Alice Smith<sup>1</sup>, Bob Jones<sup>2</sup>"
    )


def test_repair_affiliation_label_ocr_body_wraps_inline_labels() -> None:
    body = "1Department of A. 2University of B"

    assert repair_affiliation_label_ocr_body(body) == (
        "<sup>1</sup>Department of A. <sup>2</sup>University of B"
    )


def test_repair_affiliation_label_ocr_body_leaves_out_of_range_labels() -> None:
    assert repair_affiliation_label_ocr_body("31Department of A") == "31Department of A"
