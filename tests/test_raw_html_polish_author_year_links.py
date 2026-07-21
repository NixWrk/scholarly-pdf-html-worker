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
        "remained relevant.</p>"
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

    assert (
        unwrap_author_year_ref_links(
            html,
            pdf_annotation_reference_label_keys=lambda _profile: {"smith 2020)"},
            normalize_pdf_annotation_label=lambda value: value.strip().casefold(),
        )
        == html
    )


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


def test_link_plain_author_year_citations_matches_bibliography_by_name_and_year() -> (
    None
):
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
    assert (
        '<a href="#ref-20" class="z2m-ref-link">Metcalfe and Gresty, 1992</a>' in linked
    )
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

    assert (
        '<a href="#ref-12" class="z2m-ref-link">Glasauer et al., 2002</a>' in polished
    )
    assert (
        '<a href="#ref-20" class="z2m-ref-link">Metcalfe and Gresty, 1992)</a>'
        in polished
    )


def test_polish_html_document_targets_unnumbered_author_year_bibliography_only() -> (
    None
):
    html = (
        "<html><body>"
        "<p>Prior work by Smith, 2020 and Jones, 2021 established the method.</p>"
        "<h4>References</h4>"
        "<p>Smith, J. (2020). A reliable method. Journal of Testing, 4, 1-9.</p>"
        "<p>Jones, A. (2021). A second method. https://doi.org/10.1000/example.</p>"
        "<table><tr><td>Post-reference table</td></tr></table>"
        "<h4>Design Methodology Recommendations</h4>"
        '<p block-type="ListGroup"><ul><li>1. Validate with users.</li></ul></p>'
        "</body></html>"
    )

    polished = single_file_html.polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "author_year", "confidence": "medium"},
    )

    assert (
        '<p id="ref-1" class="z2m-author-year-reference">Smith, J. (2020)' in polished
    )
    assert (
        '<p id="ref-2" class="z2m-author-year-reference">Jones, A. (2021)' in polished
    )
    assert polished.count("z2m-author-year-reference") == 2
    assert '<a href="#ref-1" class="z2m-ref-link">Smith, 2020</a>' in polished
    assert '<a href="#ref-2" class="z2m-ref-link">Jones, 2021</a>' in polished
    recommendations = polished.split("Design Methodology Recommendations", maxsplit=1)[
        1
    ]
    assert 'id="ref-' not in recommendations
    assert "z2m-ref-num" not in recommendations


def test_polish_html_document_prefers_reference_paragraphs_before_unheaded_list() -> (
    None
):
    html = (
        "<html><body>"
        "<p>Prior work by Smith, 2020 and Jones, 2021 established the method.</p>"
        "<h4>References</h4>"
        "<p>Smith, J. (2020). A reliable method. Jones, A. (2021). A second method.</p>"
        "<p><b>Design Methodology Recommendations</b></p>"
        '<p block-type="ListGroup"><ul><li>1. Validate with users.</li></ul></p>'
        "</body></html>"
    )

    polished = single_file_html.polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "author_year", "confidence": "medium"},
    )

    assert (
        '<p id="ref-1" class="z2m-author-year-reference">Smith, J. (2020)' in polished
    )
    assert '<a href="#ref-1" class="z2m-ref-link">Smith, 2020</a>' in polished
    assert '<a href="#ref-1" class="z2m-ref-link">Jones, 2021</a>' in polished
    recommendations = polished.split("Design Methodology Recommendations", maxsplit=1)[
        1
    ]
    assert 'id="ref-' not in recommendations
    assert "z2m-ref-num" not in recommendations


def test_single_file_html_keeps_author_year_link_compatibility_surface() -> None:
    assert (
        single_file_html._link_plain_author_year_citations
        is author_year_links.link_plain_author_year_citations
    )
    assert (
        single_file_html._repair_roman_suffix_author_year_ref_link_splits
        is author_year_links.repair_roman_suffix_author_year_ref_link_splits
    )
    assert (
        single_file_html._unwrap_author_year_page_links
        is author_year_links.unwrap_author_year_page_links
    )
    assert (
        single_file_html._recover_trailing_citation_after_author_year_ref
        is author_year_links.recover_trailing_citation_after_author_year_ref
    )
    assert (
        single_file_html._unwrap_author_year_ref_links_impl
        is author_year_links.unwrap_author_year_ref_links
    )


def test_link_plain_author_year_citations_supports_cyrillic_names_and_suffixes() -> (
    None
):
    html = (
        "<p>\u041c\u0435\u0442\u043e\u0434 \u043e\u043f\u0438\u0441\u0430\u043d "
        "\u0418\u0432\u0430\u043d\u043e\u0432 \u0438 \u041f\u0435\u0442\u0440\u043e\u0432, 2020; "
        "\u0430 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 "
        "\u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d "
        "\u0421\u0438\u0434\u043e\u0440\u043e\u0432 \u0438 \u0434\u0440., 2021\u0430.</p>"
        "<h4>\u0421\u043f\u0438\u0441\u043e\u043a \u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b</h4><ol>"
        '<li id="ref-1">\u0418\u0432\u0430\u043d\u043e\u0432 \u0418. \u0438 '
        "\u041f\u0435\u0442\u0440\u043e\u0432 \u041f. \u041c\u0435\u0442\u043e\u0434. 2020.</li>"
        '<li id="ref-2">\u0421\u0438\u0434\u043e\u0440\u043e\u0432 \u0421. '
        "\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442. 2021\u0430.</li>"
        "</ol>"
    )

    linked = link_plain_author_year_citations(html)

    assert (
        '<a href="#ref-1" class="z2m-ref-link">'
        "\u0418\u0432\u0430\u043d\u043e\u0432 \u0438 \u041f\u0435\u0442\u0440\u043e\u0432, 2020</a>"
    ) in linked
    assert (
        '<a href="#ref-2" class="z2m-ref-link">'
        "\u0421\u0438\u0434\u043e\u0440\u043e\u0432 \u0438 \u0434\u0440., 2021\u0430</a>"
    ) in linked
