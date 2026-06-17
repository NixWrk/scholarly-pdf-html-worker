from zoteropdf2md import single_file_html
from zoteropdf2md.raw_html_polish.references_links import (
    normalize_standalone_reference_paragraph_prefix,
    reference_visible_number,
    references_heading_match,
    references_heading_search,
    strip_duplicate_reference_number_artifacts,
    strip_embedded_reference_number_artifacts,
    strip_leading_reference_line_number_pair,
    strip_leading_reference_line_number_pairs_in_list_items,
    strip_reference_visible_number,
)


def test_references_heading_helpers_find_plain_and_notes_headings() -> None:
    assert references_heading_search("<p>Body</p><h2>References</h2>") is not None
    assert references_heading_match("<h2>References</h2>") is not None
    assert references_heading_search("<h2>Notes and references</h2>", allow_notes_heading=True) is not None


def test_reference_visible_number_handles_line_number_prefixes() -> None:
    body = "899 1. Bourne A."

    assert reference_visible_number(body) == 1
    assert strip_reference_visible_number(body) == "Bourne A."


def test_reference_visible_number_handles_spaced_author_and_sup_prefixes() -> None:
    assert reference_visible_number("2 Teasell R, Foley N. Journal 2002.") == 2
    assert strip_reference_visible_number("2 Teasell R, Foley N. Journal 2002.") == "Teasell R, Foley N. Journal 2002."

    sup_body = "<sup>4</sup> I. A. Turygin, Applied Optics."
    assert reference_visible_number(sup_body) == 4
    assert strip_reference_visible_number(sup_body) == "I. A. Turygin, Applied Optics."


def test_strip_leading_reference_line_number_pair() -> None:
    assert strip_leading_reference_line_number_pair("899 1. Bourne A.") == "1. Bourne A."


def test_strip_leading_reference_line_number_pairs_in_list_items() -> None:
    source = '<ol><li class="ref">899 1. Bourne A.</li></ol>'

    assert strip_leading_reference_line_number_pairs_in_list_items(source) == (
        '<ol><li class="ref">1. Bourne A.</li></ol>'
    )


def test_normalize_standalone_reference_paragraph_prefix_preserves_author_initial() -> None:
    body = '<a href="#page-1">[3] A</a>. Smith'

    assert normalize_standalone_reference_paragraph_prefix(body, "3") == (
        '<span class="z2m-ref-num">3.</span> A. Smith'
    )


def test_reference_number_artifact_stripping() -> None:
    assert strip_duplicate_reference_number_artifacts("1. 1Smith", "1") == "1. Smith"
    assert strip_embedded_reference_number_artifacts("Journal 12. of tests") == "Journal of tests"


def test_single_file_html_keeps_legacy_private_reference_aliases() -> None:
    assert single_file_html._reference_visible_number is reference_visible_number
    assert single_file_html._references_heading_search is references_heading_search
