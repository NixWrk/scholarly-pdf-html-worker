from pdf_html_polish.raw_html_polish.frontmatter_footnotes import (
    normalize_front_matter_marker_numbers,
    repair_affiliation_label_ocr_body,
    repair_author_marker_ocr_body,
)


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
