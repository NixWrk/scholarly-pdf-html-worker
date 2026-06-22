from pdf_html_polish.raw_html_polish.frontmatter_footnotes import (
    looks_author_byline_front_matter,
    looks_author_marker_ocr_candidate,
    normalize_front_matter_marker_numbers,
    repair_affiliation_label_ocr_body,
    repair_author_marker_ocr_body,
    unicode_capitalized_name_pair_count,
    unicode_glued_author_marker_count,
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


def test_normalize_front_matter_marker_numbers_compacts_separator_noise() -> None:
    assert normalize_front_matter_marker_numbers("1, 02; x9") == "1,02,9"


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
