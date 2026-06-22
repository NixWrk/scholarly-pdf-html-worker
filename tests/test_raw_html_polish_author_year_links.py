from pdf_html_polish import single_file_html
from pdf_html_polish.raw_html_polish import author_year_links
from pdf_html_polish.raw_html_polish.author_year_links import (
    link_plain_author_year_citations,
    recover_trailing_citation_after_author_year_ref,
    repair_roman_suffix_author_year_ref_link_splits,
    unwrap_author_year_page_links,
    unwrap_author_year_ref_links,
)


def test_unwrap_author_year_ref_links_unwraps_full_author_year_label() -> None:
    html = (
        '<p>Earlier work <a href="#ref-1" class="z2m-ref-link">Smith 2020)</a> '
        'remained relevant.</p>'
        '<ol><li id="ref-1">Smith J. Vision study. 2020.</li></ol>'
    )

    assert unwrap_author_year_ref_links(html) == (
        "<p>Earlier work Smith 2020) remained relevant.</p>"
        '<ol><li id="ref-1">Smith J. Vision study. 2020.</li></ol>'
    )


def test_unwrap_author_year_ref_links_preserves_pdf_annotation_labels() -> None:
    html = (
        '<p>Earlier work <a href="#ref-1" class="z2m-ref-link">Smith 2020)</a>.</p>'
        '<ol><li id="ref-1">Smith J. Vision study. 2020.</li></ol>'
    )

    assert unwrap_author_year_ref_links(
        html,
        pdf_annotation_reference_label_keys=lambda _profile: {"smith 2020)"},
        normalize_pdf_annotation_label=lambda value: value.strip().casefold(),
    ) == html


def test_repair_roman_suffix_author_year_ref_link_splits() -> None:
    html = (
        '<p>Trev <a href="#ref-3" class="z2m-ref-link">i</a>'
        '<a href="#ref-3" class="z2m-ref-link">2012</a> described the method.</p>'
    )

    assert repair_roman_suffix_author_year_ref_link_splits(html) == (
        '<p>Trevi<a href="#ref-3" class="z2m-ref-link">2012</a> described the method.</p>'
    )


def test_unwrap_author_year_page_links_removes_stale_page_anchor_fragments() -> None:
    html = '<p>Retinotopic studies <a href="#page-14">(Bandettini,</a> 2009) are cited.</p>'

    assert unwrap_author_year_page_links(html) == (
        "<p>Retinotopic studies (Bandettini, 2009) are cited.</p>"
    )


def test_recover_trailing_citation_after_author_year_ref() -> None:
    html = (
        '<p><a href="#ref-2" class="z2m-ref-link">Smith 2020)</a> 3.</p>'
        '<ol><li id="ref-2">Smith J. 2020.</li><li id="ref-3">Numeric citation.</li></ol>'
    )

    assert recover_trailing_citation_after_author_year_ref(html) == (
        '<p><a href="#ref-2" class="z2m-ref-link">Smith 2020)</a>'
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup>.</p>'
        '<ol><li id="ref-2">Smith J. 2020.</li><li id="ref-3">Numeric citation.</li></ol>'
    )


def test_link_plain_author_year_citations_matches_bibliography_by_name_and_year() -> None:
    html = (
        "<p>Navigation relies on vestibular cues (Glasauer et al., 2002; "
        "Metcalfe and Gresty, 1992; Unknown et al., 2002).</p>"
        "<h4>References</h4><ol>"
        '<li id="ref-12">Glasauer, S., Amorim, M.A. and Berthoz, A. (2002) Example.</li>'
        '<li id="ref-20">Metcalfe, T. and Gresty, M. (1992) Example.</li>'
        "</ol>"
    )

    linked = link_plain_author_year_citations(html)

    assert '<a href="#ref-12" class="z2m-ref-link">Glasauer et al., 2002</a>' in linked
    assert '<a href="#ref-20" class="z2m-ref-link">Metcalfe and Gresty, 1992</a>' in linked
    assert "Unknown et al., 2002" in linked
    assert 'href="#ref-1"' not in linked


def test_polish_html_document_links_plain_author_year_citations_after_cleanup() -> None:
    html = (
        "<html><body>"
        "<p>Navigation relies on vestibular cues (Glasauer et al., 2002; "
        "Metcalfe and Gresty, 1992).</p>"
        "<h4>References</h4><p><ul>"
        '<li id="ref-12">Glasauer, S., Amorim, M.A. and Berthoz, A. (2002) Example.</li>'
        '<li id="ref-20">Metcalfe, T. and Gresty, M. (1992) Example.</li>'
        "</ul></p></body></html>"
    )

    polished = single_file_html.polish_html_document(
        html,
        citation_profile={"style": "author_year", "confidence": "medium"},
    )

    assert '<a href="#ref-12" class="z2m-ref-link">Glasauer et al., 2002</a>' in polished
    assert '<a href="#ref-20" class="z2m-ref-link">Metcalfe and Gresty, 1992)</a>' in polished


def test_single_file_html_keeps_author_year_link_compatibility_surface() -> None:
    assert single_file_html._link_plain_author_year_citations is author_year_links.link_plain_author_year_citations
    assert (
        single_file_html._repair_roman_suffix_author_year_ref_link_splits
        is author_year_links.repair_roman_suffix_author_year_ref_link_splits
    )
    assert single_file_html._unwrap_author_year_page_links is author_year_links.unwrap_author_year_page_links
    assert (
        single_file_html._recover_trailing_citation_after_author_year_ref
        is author_year_links.recover_trailing_citation_after_author_year_ref
    )
    assert single_file_html._unwrap_author_year_ref_links_impl is author_year_links.unwrap_author_year_ref_links
