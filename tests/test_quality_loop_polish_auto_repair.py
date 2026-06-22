from pdf_html_polish.quality_loop.polish_auto_repair import (
    assessment_articles_by_broken_internal_links,
    audit_articles_by_auto_repair_need,
    relink_external_numeric_citation_anchors,
    relink_spaced_multipanel_figure_refs,
    repair_visible_reference_numbers,
    unwrap_broken_internal_links,
    unwrap_author_year_numeric_ref_links,
    unwrap_author_year_ref_anchors,
)


def test_audit_articles_by_auto_repair_need_selects_supported_ids() -> None:
    report = {
        "articles": [
            {"article": "a", "defects_found": [{"id": "P55"}, {"id": "P04N"}]},
            {"article": "b", "defects": [{"id": "P96"}, {"id": "P98"}]},
            {"article": "c", "defects_found": [{"id": "P59"}]},
            {"article": "d", "defects_found": [{"id": "P17"}, {"id": "P62"}]},
        ]
    }

    selected = audit_articles_by_auto_repair_need(report)

    assert selected["a"]["defect_ids"] == ["P04N", "P55"]
    assert selected["b"]["defect_ids"] == ["P96", "P98"]
    assert selected["c"]["defect_ids"] == ["P59"]
    assert selected["d"]["defect_ids"] == ["P17"]


def test_assessment_articles_by_broken_internal_links_selects_link_regressions() -> None:
    assessment = {
        "articles": [
            {"article": "a", "href_counts": {"broken_internal_links": 2}},
            {"article": "b", "href_counts": {"broken_internal_links": 0}},
            {"article": "c", "href_counts": {}},
        ]
    }

    assert assessment_articles_by_broken_internal_links(assessment) == {"a": 2}


def test_unwrap_broken_internal_links_keeps_valid_targets() -> None:
    html = (
        '<p><a href="#fig-1" class="z2m-fig-link">Figure 1</a> '
        'and <a href="#fig-2" class="z2m-fig-link">Figure 2</a> '
        'plus <sup><a href="#ref-9" class="z2m-ref-link">9</a></sup>.</p>'
        '<div id="fig-1"></div>'
    )

    repaired, count = unwrap_broken_internal_links(html)

    assert count == 2
    assert '<a href="#fig-1" class="z2m-fig-link">Figure 1</a>' in repaired
    assert '<a href="#fig-2"' not in repaired
    assert '<a href="#ref-9"' not in repaired
    assert "Figure 2" in repaired
    assert "<sup>9</sup>" in repaired


def test_relink_spaced_multipanel_figure_refs_uses_existing_targets() -> None:
    html = (
        '<div id="fig-7" class="z2m-figure-unit">'
        '<p class="z2m-figure-caption">Figure 7. Panels.</p>'
        "</div>"
        "<p>The feature point is shown in Figure \n 7 (b)).</p>"
    )

    repaired, count = relink_spaced_multipanel_figure_refs(html)

    assert count == 1
    assert '<a href="#fig-7" class="z2m-fig-link">Figure\xa07</a> (b)' in repaired


def test_relink_external_numeric_citation_anchors_uses_existing_ref_targets() -> None:
    html = (
        '<p>Prior work <a href="https://app.readcube.com/library/item-1">[1]</a> '
        'and later studies <a href="https://app.readcube.com/library/item-2">[2,3]</a>.</p>'
        "<h4>References</h4>"
        '<p block-type="ListGroup"><ul>'
        '<li id="ref-1">First.</li><li id="ref-2">Second.</li><li id="ref-3">Third.</li>'
        "</ul></p>"
    )

    repaired, count = relink_external_numeric_citation_anchors(html)

    assert count == 2
    before_refs = repaired.split("<h4>References</h4>")[0]
    assert "readcube.com" not in before_refs
    assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in before_refs
    assert '[<a href="#ref-2" class="z2m-ref-link">2</a>,' in before_refs
    assert '<a href="#ref-3" class="z2m-ref-link">3</a>]' in before_refs


def test_relink_external_numeric_citation_anchors_skips_missing_targets() -> None:
    html = (
        '<p>Prior work <a href="https://app.readcube.com/library/item-1">[2,4]</a>.</p>'
        "<h4>References</h4>"
        '<ol><li id="ref-2">Second.</li><li id="ref-3">Third.</li></ol>'
    )

    repaired, count = relink_external_numeric_citation_anchors(html)

    assert count == 0
    assert repaired == html


def test_reference_number_repair_preserves_existing_visible_numbers() -> None:
    html = (
        '<ol><li id="ref-1">[1] Existing.</li>'
        '<li id="ref-2">Missing visible number.</li>'
        '<li id="ref-3">4. Mismatched visible number.</li></ol>'
    )

    repaired, count = repair_visible_reference_numbers(html)

    assert count == 1
    assert '<span class="z2m-ref-num">2.</span> Missing visible number.' in repaired
    assert "[1] Existing." in repaired
    assert "4. Mismatched visible number." in repaired


def test_author_year_reference_repairs_stop_before_references() -> None:
    html = (
        '<p><a href="#ref-3">Flores</a> et al. (2015) and '
        '<a href="#ref-4">Schira</a>, Tyler, Breakspear, & Spehar, 2009, '
        'plus <a href="#ref-5">Yao et al.</a> (2023b) and '
        '<a href="#ref-2">2</a> are body prose.</p>'
        "<h4>References</h4>"
        '<p id="ref-2"><a href="#ref-2">2</a> Reference text.</p>'
        '<p id="ref-3">Flores citation.</p>'
        '<p id="ref-4">Schira citation.</p>'
        '<p id="ref-5">Yao citation.</p>'
    )

    unwrapped_names, p55_count = unwrap_author_year_ref_anchors(html)
    unwrapped_numbers, p98_count = unwrap_author_year_numeric_ref_links(unwrapped_names)

    assert p55_count == 3
    assert p98_count == 1
    assert '<a href="#ref-3">Flores</a>' not in unwrapped_numbers.split("<h4>References</h4>")[0]
    assert '<a href="#ref-4">Schira</a>' not in unwrapped_numbers.split("<h4>References</h4>")[0]
    assert '<a href="#ref-5">Yao et al.</a>' not in unwrapped_numbers.split("<h4>References</h4>")[0]
    assert '<a href="#ref-2">2</a>' not in unwrapped_numbers.split("<h4>References</h4>")[0]
    assert '<p id="ref-2"><a href="#ref-2">2</a> Reference text.</p>' in unwrapped_numbers


def test_author_year_reference_repair_preserves_matching_bibliography_links() -> None:
    html = (
        '<p>Navigation relied on <a href="#ref-20" class="z2m-ref-link">'
        'Metcalfe and Gresty, 1992</a> and '
        '<a href="#ref-25" class="z2m-ref-link">Seemungal et al., 2007)</a>.</p>'
        "<h4>References</h4><ol>"
        '<li id="ref-20">Metcalfe, T. and Gresty, M. (1992) Example.</li>'
        '<li id="ref-25">Seemungal, B.M., Glasauer, S. and Bronstein, A.M. (2007) Example.</li>'
        "</ol>"
    )

    repaired, count = unwrap_author_year_ref_anchors(html)

    assert count == 0
    assert repaired == html


def test_author_year_numeric_repair_handles_p59_map_labels() -> None:
    html = (
        '<p>map <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>: doll, cat; '
        'map <sup><a href="#ref-2" class="z2m-ref-link">2</a></sup>: knife, chair.</p>'
        "<h4>References</h4>"
        '<p id="ref-1"><a href="#ref-1">1</a> First reference.</p>'
        '<p id="ref-2"><a href="#ref-2">2</a> Second reference.</p>'
    )

    repaired, count = unwrap_author_year_numeric_ref_links(html)
    before_refs = repaired.split("<h4>References</h4>")[0]

    assert count == 2
    assert 'href="#ref-1"' not in before_refs
    assert 'href="#ref-2"' not in before_refs
    assert 'map <sup>1</sup>: doll, cat' in before_refs
    assert '<p id="ref-1"><a href="#ref-1">1</a> First reference.</p>' in repaired
