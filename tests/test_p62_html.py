import base64
import hashlib

from zoteropdf2md.quality_loop.p62_html import (
    data_url_image_hash,
    extract_html_figure_units,
    html_has_missing_warning_for_figure_unit,
    html_has_recovery_for_label,
    html_has_stale_page_render_for_label,
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
