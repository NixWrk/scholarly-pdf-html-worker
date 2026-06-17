import base64
import hashlib

from zoteropdf2md.quality_loop.p62_html import (
    data_url_duplicates_existing_figure_unit,
    data_url_image_hash,
    extract_html_figure_units,
    html_has_missing_warning_for_figure_unit,
    html_has_recovery_for_label,
    html_has_stale_page_render_for_label,
    insert_recovered_figure_unit_for_visible_reference,
    move_p61_recovered_units_after_sentence_continuation,
    replace_figure_unit_target_with_missing_warning,
    replace_missing_warning_with_image,
    replace_recovery_with_missing_warning,
)


_DATA_URL = "data:image/png;base64," + base64.b64encode(b"fig").decode("ascii")


def test_replace_missing_warning_with_image_cleans_resolved_unit_class() -> None:
    html = (
        '<div id="fig-4" class="z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-missing-figure-warning">Figure 4 image was not extracted into this HTML.</p>'
        '<p class="z2m-figure-caption">Figure 4. Layout.</p>'
        "</div>"
    )

    patched, replacements = replace_missing_warning_with_image(
        html,
        figure_label="4",
        warning_index=1,
        data_url=_DATA_URL,
        source="marker_image",
        source_detail="marker/out.png",
    )

    assert replacements == 1
    assert "z2m-p62-recovered-target" in patched
    assert "z2m-missing-figure-unit" not in patched
    assert 'data-z2m-recovery-source="marker_image"' in patched


def test_recovery_with_missing_warning_matches_nearest_figure_unit_label() -> None:
    html = (
        '<div id="fig-3" class="z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        f'<img data-z2m-recovery-source="pdf_page_render" src="{_DATA_URL}"/></p>'
        '<p class="z2m-figure-caption">Figure 3. Old.</p>'
        "</div>"
        '<div id="fig-4" class="z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        f'<img data-z2m-recovery-source="pdf_page_render" src="{_DATA_URL}"/></p>'
        '<p class="z2m-figure-caption">Figure 4. New.</p>'
        "</div>"
    )

    patched, replacements = replace_recovery_with_missing_warning(
        html,
        figure_label="4",
        reason="false_match",
    )

    assert replacements == 1
    assert patched.count("z2m-p62-recovered-target") == 1
    assert html_has_missing_warning_for_figure_unit(patched, "4") is True
    assert html_has_missing_warning_for_figure_unit(patched, "3") is False


def test_recovery_source_filtering_and_hash_extraction() -> None:
    html = (
        '<div id="fig-8" class="z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        f'<img data-z2m-recovery-source="pdf_page_render" src="{_DATA_URL}"/></p>'
        '<p class="z2m-figure-caption">Figure 8. Caption text.</p>'
        "</div>"
    )

    units = extract_html_figure_units(html)

    assert html_has_recovery_for_label(html, "8") is True
    assert html_has_stale_page_render_for_label(html, "8") is True
    assert units[0]["label"] == "8"
    assert units[0]["caption"] == "Figure 8. Caption text."
    assert units[0]["image_hashes"] == [hashlib.sha256(b"fig").hexdigest()]
    assert data_url_image_hash(f'<img src="{_DATA_URL}"/>') == hashlib.sha256(b"fig").hexdigest()


def test_insert_recovered_figure_unit_for_p61_panel_reference_uses_base_target_key() -> None:
    html = (
        "<main>"
        "<p>The robot was trapped in the area indicated by Figure 11b.</p>"
        "<p>Discussion resumes.</p>"
        "</main>"
    )

    patched, replacements = insert_recovered_figure_unit_for_visible_reference(
        html,
        target_figure_key="11",
        visible_label="Figure 11b",
        snippet="The robot was trapped in the area indicated by Figure 11b.",
        data_url=_DATA_URL,
        source="pdf_figure_region_render",
        source_detail="fig11b.png",
    )

    assert replacements == 1
    assert 'id="fig-11"' in patched
    assert "Figure 11b" in patched
    assert 'data-z2m-origin="p61-source-pdf-recovery"' in patched
    assert patched.index('id="fig-11"') < patched.index("Discussion resumes")


def test_insert_recovered_figure_unit_for_p61_does_not_duplicate_existing_target() -> None:
    html = (
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig1.png"/></p>'
        "</div>"
        "<p>The result is shown in Figure 1.</p>"
    )

    patched, replacements = insert_recovered_figure_unit_for_visible_reference(
        html,
        target_figure_key="1",
        visible_label="Figure 1",
        snippet="The result is shown in Figure 1.",
        data_url=_DATA_URL,
        source="pdf_native_image",
        source_detail="fig1.png",
    )

    assert replacements == 0
    assert patched == html


def test_insert_recovered_figure_unit_for_p61_allows_ordinary_table_links_in_block() -> None:
    html = (
        "<main>"
        '<p>Based on <a href="#table-2" class="z2m-table-link">Table 2</a>, '
        "the visual field correlation is significant (Fig. 3).</p>"
        "</main>"
    )

    patched, replacements = insert_recovered_figure_unit_for_visible_reference(
        html,
        target_figure_key="3",
        visible_label="Fig. 3",
        snippet="visual field correlation is significant (Fig. 3)",
        data_url=_DATA_URL,
        source="pdf_native_image",
        source_detail="fig3.png",
    )

    assert replacements == 1
    assert 'id="fig-3"' in patched
    assert "z2m-table-link" in patched


def test_insert_recovered_figure_unit_for_p61_does_not_split_sentence_continuation() -> None:
    html = (
        "<main>"
        "<p>The proposed robot (<b>Figure 2</b>) contains a sensor tower for mounting all the sensors, "
        "including a depth camera and an</p>"
        "<p>mmWave module. The mounted sensors are used by the perception system.</p>"
        "<p>The next paragraph starts here.</p>"
        "</main>"
    )

    patched, replacements = insert_recovered_figure_unit_for_visible_reference(
        html,
        target_figure_key="2",
        visible_label="Figure 2",
        snippet="The robot contains all the sensors, including a depth camera and an mmWave module.",
        data_url=_DATA_URL,
        source="pdf_figure_region_render",
        source_detail="fig2.png",
    )

    assert replacements == 1
    assert patched.index("mmWave module") < patched.index('id="fig-2"')
    assert patched.index('id="fig-2"') < patched.index("The next paragraph starts here")


def test_move_p61_recovered_units_after_sentence_continuation_repairs_existing_split() -> None:
    html = (
        "<main>"
        "<p>The robot contains a sensor tower, including a camera and an</p>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit" '
        'data-z2m-origin="p61-source-pdf-recovery">'
        f'<p class="z2m-figure-target z2m-p62-recovered-target"><img src="{_DATA_URL}"/></p>'
        "</div>"
        "<p>mmWave module. The mounted sensors are used by the perception system.</p>"
        "</main>"
    )

    patched, replacements = move_p61_recovered_units_after_sentence_continuation(html)

    assert replacements == 1
    assert patched.index("mmWave module") < patched.index('id="fig-2"')


def test_data_url_duplicates_existing_figure_unit_ignores_same_target() -> None:
    html = (
        '<div id="fig-1" class="z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        f'<img src="{_DATA_URL}"/></p>'
        "</div>"
    )

    assert data_url_duplicates_existing_figure_unit(html, _DATA_URL, target_figure_key="2") is True
    assert data_url_duplicates_existing_figure_unit(html, _DATA_URL, target_figure_key="1") is False
