from zoteropdf2md.quality_loop.audit_blocks import Block
from zoteropdf2md.quality_loop.audit_p61 import (
    figure_key_from_visible_number,
    figure_target_keys,
    visible_figure_target_defects,
)


def _block(text: str, raw: str | None = None, *, index: int = 0) -> Block:
    return Block(index=index, tag="p", attrs={}, raw=raw or f"<p>{text}</p>", text=text, line=index + 1)


def _defects(block: Block, targets: set[str] | None = None):
    return visible_figure_target_defects(
        [block],
        targets or set(),
        looks_like_float_or_caption=lambda _block: False,
        stage="02.en.polish.html",
    )


def test_figure_key_from_visible_number_normalizes_ranges_and_panels() -> None:
    assert figure_key_from_visible_number("3D") == "3d"
    assert figure_key_from_visible_number("4 - 5") == "4-5"
    assert figure_key_from_visible_number("S 1") == "s1"


def test_figure_target_keys_collects_semantic_fig_ids() -> None:
    html = '<div id="fig-3"></div><figure id="fig-Supplementary-4"></figure>'

    assert figure_target_keys(html) == {"3", "supplementary-4"}


def test_figure_target_keys_keeps_extended_data_separate_from_main_figure() -> None:
    html = (
        '<div id="fig-extended-data-8" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="extended8.jpg"/></p>'
        '<p class="z2m-figure-caption">Extended Data Fig. 8 | Hardware setup.</p>'
        "</div>"
    )
    targets = figure_target_keys(html)

    assert "extended-data-8" in targets
    assert "8" not in targets
    assert _defects(_block("Extended Data Fig. 8 shows the rig."), targets) == []
    assert [defect.id for defect in _defects(_block("Figure 8 shows the rig."), targets)] == ["P61"]


def test_figure_target_keys_infers_caption_number_from_slugged_figure_unit() -> None:
    html = (
        '<div id="fig-18-1840" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig18.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 18. 1840 Robert Cornelius daguerreotype.</p>'
        "</div>"
    )
    targets = figure_target_keys(html)

    assert {"18", "18-1840"}.issubset(targets)
    assert _defects(_block("Figure 18 illustrates the burnishing marks."), targets) == []


def test_figure_target_keys_keeps_compound_caption_key_specific() -> None:
    html = (
        '<div id="fig-3-5" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="fig35.jpg"/></p>'
        '<p class="z2m-figure-caption">Figure 3.5. Flow-rate signal.</p>'
        "</div>"
    )
    targets = figure_target_keys(html)

    assert "3-5" in targets
    assert "3" not in targets


def test_visible_figure_target_defects_reports_missing_target() -> None:
    defects = _defects(_block("The result is summarized in Figure 3D."))

    assert [defect.id for defect in defects] == ["P61"]
    assert defects[0].extra == {
        "figure": "3",
        "figure_key": "3",
        "visible_label": "Figure 3D",
        "quality_counted": False,
    }


def test_visible_figure_target_defects_accepts_existing_target() -> None:
    assert _defects(_block("The result is summarized in Figure 3."), {"3"}) == []


def test_visible_figure_target_defects_ignores_supplementary_references() -> None:
    assert _defects(_block("The details are shown in Supplementary Figure S1.")) == []
    assert _defects(_block("The details are shown in Figure S1.")) == []


def test_visible_figure_target_defects_ignores_chapter_style_compound_numbers() -> None:
    assert _defects(_block("The next section explains the retinotopic map (Fig. 7.5).")) == []
    assert _defects(_block("The approach follows the workflow in Figure 5-1.")) == []
    assert [defect.id for defect in _defects(_block("The local result is summarized in Figure 5."))] == ["P61"]


def test_visible_figure_target_defects_accepts_nearby_existing_link() -> None:
    block = _block(
        "The result is summarized in Figure 3.",
        raw='<p>The result is summarized in <a href="#fig-3">Figure 3</a>.</p>',
    )

    assert _defects(block) == []


def test_visible_figure_target_defects_ignores_external_author_year_figure_citation() -> None:
    block = _block(
        "Perusal of published distributions (Fiorani et al., 1992, Fig. 5; "
        "Zhou et al., 2000, Fig. 19) supports the range."
    )

    assert _defects(block) == []


def test_visible_figure_target_defects_keeps_local_figure_after_author_year_sentence() -> None:
    block = _block("Fiorani et al. described similar effects in 1992. Figure 5 shows the local result.")

    assert [defect.id for defect in _defects(block)] == ["P61"]
