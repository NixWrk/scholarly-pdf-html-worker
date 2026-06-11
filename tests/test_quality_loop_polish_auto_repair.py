from zoteropdf2md.quality_loop.polish_auto_repair import (
    audit_articles_by_auto_repair_need,
    repair_visible_reference_numbers,
    unwrap_author_year_numeric_ref_links,
    unwrap_author_year_ref_anchors,
)


def test_audit_articles_by_auto_repair_need_selects_supported_ids() -> None:
    report = {
        "articles": [
            {"article": "a", "defects_found": [{"id": "P55"}, {"id": "P04N"}]},
            {"article": "b", "defects": [{"id": "P96"}, {"id": "P98"}]},
            {"article": "c", "defects_found": [{"id": "P59"}]},
            {"article": "d", "defects_found": [{"id": "P62"}]},
        ]
    }

    selected = audit_articles_by_auto_repair_need(report)

    assert selected["a"]["defect_ids"] == ["P55"]
    assert selected["b"]["defect_ids"] == ["P96", "P98"]
    assert selected["c"]["defect_ids"] == ["P59"]
    assert "d" not in selected


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
