from pdf_html_polish import single_file_html
from pdf_html_polish.raw_html_polish.references_links import (
    AUTHOR_YEAR_CITATION_TEXT_PATTERN,
    PAGE_ANCHOR_PATTERN,
    REF_ANCHOR_PATTERN,
    REFERENCE_PAGE_ID_PATTERN,
    SEMANTIC_INTERNAL_ANCHOR_PATTERN,
    normalize_standalone_reference_paragraph_prefix,
    reference_visible_number,
    references_heading_match,
    references_heading_search,
    repair_ref_links_absorbed_decimal_or_unit_text,
    repair_ref_links_with_leading_closing_punctuation,
    retarget_mismatched_ref_link_labels,
    strip_duplicate_reference_number_artifacts,
    strip_embedded_reference_number_artifacts,
    strip_leading_reference_line_number_pair,
    strip_leading_reference_line_number_pairs_in_list_items,
    strip_reference_visible_number,
    unwrap_broken_internal_semantic_links,
    unwrap_broken_page_anchor_links,
    unwrap_duplicate_see_page_anchor_tails,
    unwrap_page_reference_page_links,
    unwrap_page_reference_ref_links,
    unwrap_plain_prose_page_links,
    unwrap_reference_list_page_links,
    unwrap_reference_list_page_number_links,
    unwrap_stale_numeric_page_links,
)


class _PageReferencePolicy:
    def looks_like_page_reference(self, label: str, *, left_text: str = "") -> bool:
        normalized = f"{left_text} {label}".strip()
        normalized_lower = normalized.lower()
        return normalized_lower.endswith("см. с. 34") or normalized_lower.endswith("page 34")


def test_references_heading_helpers_find_plain_and_notes_headings() -> None:
    assert references_heading_search("<p>Body</p><h2>References</h2>") is not None
    assert references_heading_match("<h2>References</h2>") is not None
    assert references_heading_search("<h2>Notes and references</h2>", allow_notes_heading=True) is not None
    for heading in (
        "Bibliografie",
        "Bibliografía",
        "Références",
        "Literaturverzeichnis",
    ):
        assert references_heading_search(f"<h2>{heading}</h2>") is not None


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


def test_unwrap_reference_list_page_number_links_keeps_normalized_ref_number() -> None:
    html = (
        '<ol><li id="ref-3">'
        '<a href="#page-12"><span class="z2m-ref-num">3.</span></a> Smith A.'
        "</li></ol>"
    )

    assert unwrap_reference_list_page_number_links(html) == (
        '<ol><li id="ref-3"><span class="z2m-ref-num">3.</span> Smith A.</li></ol>'
    )


def test_unwrap_reference_list_page_number_links_drops_duplicate_page_number() -> None:
    html = (
        '<ol><li id="ref-3">'
        '<span class="z2m-ref-num">3.</span> <a href="#page-12">3.</a> Smith A.'
        "</li></ol>"
    )

    assert unwrap_reference_list_page_number_links(html) == (
        '<ol><li id="ref-3"><span class="z2m-ref-num">3.</span> Smith A.</li></ol>'
    )


def test_unwrap_reference_list_page_links_only_changes_reference_nodes() -> None:
    html = (
        '<ol><li id="ref-2">Smith <a href="#page-10">101</a> Journal.</li>'
        '<li>Other <a href="#page-11">102</a></li></ol>'
        '<p id="ref-3">Doe <a href="#page-12">103</a> Book.</p>'
    )

    assert unwrap_reference_list_page_links(html) == (
        '<ol><li id="ref-2">Smith 101 Journal.</li>'
        '<li>Other <a href="#page-11">102</a></li></ol>'
        '<p id="ref-3">Doe 103 Book.</p>'
    )


def test_repair_ref_links_with_leading_closing_punctuation_moves_punctuation_out() -> None:
    html = '<p>(<a href="#ref-3" class="z2m-ref-link">)3,</a> 4)</p>'

    assert repair_ref_links_with_leading_closing_punctuation(html) == (
        '<p>()<a href="#ref-3" class="z2m-ref-link">3</a>, 4)</p>'
    )


def test_retarget_mismatched_ref_link_labels_relinks_or_unwraps_numeric_labels() -> None:
    html = (
        '<p><a href="#ref-1">2</a> and <a href="#ref-3">1, 2</a> '
        'but Smith <a href="#ref-9">2019)</a> and orphan <a href="#ref-9">325</a>.</p>'
        '<ol><li id="ref-1">One.</li><li id="ref-2">Two.</li></ol>'
    )

    assert retarget_mismatched_ref_link_labels(html) == (
        '<p><a href="#ref-2" class="z2m-ref-link">2</a> and '
        '<a href="#ref-1" class="z2m-ref-link">1</a>, '
        '<a href="#ref-2" class="z2m-ref-link">2</a> '
        'but Smith <a href="#ref-9">2019)</a> and orphan 325.</p>'
        '<ol><li id="ref-1">One.</li><li id="ref-2">Two.</li></ol>'
    )


def test_repair_ref_links_absorbed_decimal_or_unit_text_repairs_percent_and_unit() -> None:
    html = (
        '<p>Success was 7 <a href="#ref-12" class="z2m-ref-link">%12</a> '
        'and flow mL/ <a href="#ref-7">s7</a>.</p>'
        '<ol><li id="ref-7">Seven.</li><li id="ref-12">Twelve.</li></ol>'
    )

    assert repair_ref_links_absorbed_decimal_or_unit_text(html) == (
        '<p>Success was 7%<a href="#ref-12" class="z2m-ref-link">12</a> '
        'and flow mL/s<a href="#ref-7" class="z2m-ref-link">7</a>.</p>'
        '<ol><li id="ref-7">Seven.</li><li id="ref-12">Twelve.</li></ol>'
    )


def test_unwrap_page_reference_ref_links_uses_language_policy() -> None:
    html = '<p>См. с. <a href="#ref-34" class="z2m-ref-link">34</a>; cite <a href="#ref-3">3</a>.</p>'

    assert unwrap_page_reference_ref_links(html, _PageReferencePolicy()) == (
        '<p>См. с. 34; cite <a href="#ref-3">3</a>.</p>'
    )


def test_unwrap_page_reference_page_links_uses_language_policy() -> None:
    html = '<p>См. с. <a href="#page-34">34</a>; see <a href="#page-5">Figure 5</a>.</p>'

    assert unwrap_page_reference_page_links(html, _PageReferencePolicy()) == (
        '<p>См. с. 34; see <a href="#page-5">Figure 5</a>.</p>'
    )


def test_unwrap_stale_numeric_page_links_preserves_explicit_page_references() -> None:
    html = '<p>Prior work <a href="#page-7">[12, 13]</a> but see page <a href="#page-8">34</a>.</p>'

    assert unwrap_stale_numeric_page_links(html, _PageReferencePolicy()) == (
        '<p>Prior work [12, 13] but see page <a href="#page-8">34</a>.</p>'
    )


def test_unwrap_plain_prose_page_links_preserves_semantic_short_labels() -> None:
    html = (
        '<p><a href="#page-1">ordinary prose fragments from article body</a> '
        '<a href="#page-2">Figure 2</a> '
        '<a href="#page-3">Smith et al. 2020</a></p>'
    )

    assert unwrap_plain_prose_page_links(html) == (
        '<p>ordinary prose fragments from article body '
        '<a href="#page-2">Figure 2</a> '
        'Smith et al. 2020</p>'
    )


def test_unwrap_duplicate_see_page_anchor_tails_keeps_first_anchor() -> None:
    html = '<p><a href="#page-8">See</a><a href="#page-8">page 12</a> for details.</p>'

    assert unwrap_duplicate_see_page_anchor_tails(html) == (
        '<p><a href="#page-8">See</a> page 12 for details.</p>'
    )


def test_unwrap_broken_page_anchor_links_preserves_working_page_ids() -> None:
    html = '<span id="page-2"></span><p><a href="#page-2">page 2</a> <a href="#page-9">orphaned prose</a></p>'

    assert unwrap_broken_page_anchor_links(html) == (
        '<span id="page-2"></span><p><a href="#page-2">page 2</a> orphaned prose</p>'
    )


def test_unwrap_broken_internal_semantic_links_preserves_page_number_labels() -> None:
    html = (
        '<p>Table <a href="#table-9" class="z2m-table-link">9</a> '
        'and prose <a href="#page-9">Adam et</a> al. '
        'but page <a href="#page-10">10</a>.</p>'
    )

    assert unwrap_broken_internal_semantic_links(html) == (
        '<p>Table 9 and prose Adam et al. but page <a href="#page-10">10</a>.</p>'
    )


def test_single_file_html_keeps_legacy_private_reference_aliases() -> None:
    assert single_file_html._AUTHOR_YEAR_CITATION_TEXT_PATTERN is AUTHOR_YEAR_CITATION_TEXT_PATTERN
    assert single_file_html._PAGE_ANCHOR_PATTERN is PAGE_ANCHOR_PATTERN
    assert single_file_html._REFERENCE_PAGE_ID_PATTERN is REFERENCE_PAGE_ID_PATTERN
    assert single_file_html._REF_ANCHOR_PATTERN is REF_ANCHOR_PATTERN
    assert single_file_html._SEMANTIC_INTERNAL_ANCHOR_PATTERN is SEMANTIC_INTERNAL_ANCHOR_PATTERN
    assert single_file_html._reference_visible_number is reference_visible_number
    assert single_file_html._references_heading_search is references_heading_search
    assert (
        single_file_html._repair_ref_links_absorbed_decimal_or_unit_text
        is repair_ref_links_absorbed_decimal_or_unit_text
    )
    assert (
        single_file_html._repair_ref_links_with_leading_closing_punctuation
        is repair_ref_links_with_leading_closing_punctuation
    )
    assert single_file_html._retarget_mismatched_ref_link_labels is retarget_mismatched_ref_link_labels
    assert single_file_html._unwrap_broken_internal_semantic_links is unwrap_broken_internal_semantic_links
    assert single_file_html._unwrap_broken_page_anchor_links is unwrap_broken_page_anchor_links
    assert single_file_html._unwrap_duplicate_see_page_anchor_tails is unwrap_duplicate_see_page_anchor_tails
    assert single_file_html._unwrap_page_reference_page_links is unwrap_page_reference_page_links
    assert single_file_html._unwrap_page_reference_ref_links is unwrap_page_reference_ref_links
    assert single_file_html._unwrap_plain_prose_page_links is unwrap_plain_prose_page_links
    assert single_file_html._unwrap_reference_list_page_links is unwrap_reference_list_page_links
    assert single_file_html._unwrap_reference_list_page_number_links is unwrap_reference_list_page_number_links
    assert single_file_html._unwrap_stale_numeric_page_links is unwrap_stale_numeric_page_links
