import re

from pdf_html_polish.quality_loop.audit_blocks import Block, parse_blocks
from pdf_html_polish.quality_loop.audit_figure_caption_ux import (
    CAPTION_TEX_RESIDUE_RE,
    figure_caption_number_from_caption_node,
    figure_caption_numbers_from_caption_node,
    figure_caption_ux_defects,
    figure_unit_allows_shared_image_alias,
    looks_like_equation_continuation,
    looks_like_figure_caption,
    looks_like_float_note,
    looks_like_float_or_caption,
)


def _looks_like_figure_caption(block: Block) -> bool:
    return (
        block.id.startswith("fig-")
        or "z2m-figure-caption" in block.classes
        or re.match(r"^\s*(?:Figure|Fig\.?)\s+\d+", block.text, re.IGNORECASE) is not None
    )


def _block(text: str, *, id_: str = "", classes: str = "", block_type: str = "", raw: str | None = None) -> Block:
    attrs = {}
    if id_:
        attrs["id"] = id_
    if classes:
        attrs["class"] = classes
    if block_type:
        attrs["block-type"] = block_type
    return Block(index=0, tag="p", attrs=attrs, raw=raw or f"<p>{text}</p>", text=text, line=1)


def _defects(html: str, *, has_internal_links: bool = False) -> list[str]:
    defects = figure_caption_ux_defects(
        html,
        parse_blocks(html),
        has_internal_links=has_internal_links,
        looks_like_figure_caption=_looks_like_figure_caption,
        is_supplementary_figure_block=lambda block: False,
        is_handled_missing_figure_block=lambda block: False,
        has_nearby_image=lambda blocks, index: any(
            candidate.has_figure_visual
            for candidate in blocks[max(0, index - 2) : min(len(blocks), index + 3)]
        ),
        has_nearby_missing_figure_warning=lambda blocks, index: any(
            "z2m-missing-figure-warning" in candidate.classes
            for candidate in blocks[max(0, index - 2) : min(len(blocks), index + 3)]
        ),
        source_pdf_text_confirms_float_gap=lambda left, right, pdf_text: False,
    )
    return [defect.id for defect in defects]


def test_figure_caption_ux_reports_caption_tex_residue() -> None:
    ids = _defects('<p id="fig-1" class="z2m-figure-caption">Figure 1. Caption \\label{fig:a}</p>')

    assert "P12" in ids


def test_looks_like_figure_caption_rejects_prose_reference_text() -> None:
    caption = _block("Figure 1. A real caption sentence.")
    prose = _block("Figure 1 shows the measured response in the sample.")

    assert looks_like_figure_caption(caption)
    assert not looks_like_figure_caption(prose)


def test_figure_caption_number_from_caption_node_requires_caption_separator() -> None:
    assert figure_caption_number_from_caption_node("Figure 12. Response map.") == 12
    assert figure_caption_number_from_caption_node("Figure 12 shows a response map.") is None


def test_figure_caption_numbers_from_caption_node_ignores_cross_reference_context() -> None:
    assert figure_caption_numbers_from_caption_node("Figure 4. Main. See Figure 5. elsewhere.") == {4}


def test_figure_unit_allows_shared_image_alias_for_contiguous_caption_aliases() -> None:
    body = (
        '<p><img src="fig1.png"></p>'
        '<span class="z2m-float-alias" id="fig-2"></span>'
        '<p class="z2m-figure-caption">Figure 2. Alias caption.</p>'
    )

    assert figure_unit_allows_shared_image_alias(body, 1, [2])
    assert not figure_unit_allows_shared_image_alias(body, 1, [3])


def test_float_context_helpers_classify_float_notes_and_equations() -> None:
    assert looks_like_float_or_caption(_block("Figure 3. Caption.", classes="z2m-figure-caption"))
    assert looks_like_float_note(_block("Values: mean and SD."))
    assert looks_like_equation_continuation(_block("x = y + z"))
    assert looks_like_equation_continuation(_block("not rendered", block_type="Equation"))
    assert looks_like_equation_continuation(_block("display", raw='<p class="z2m-math-display">display</p>'))


def test_figure_caption_ux_reports_caption_without_image() -> None:
    ids = _defects('<p id="fig-2" class="z2m-figure-caption">Figure 2. Caption text.</p>')

    assert "P13" in ids


def test_figure_caption_ux_accepts_terminal_source_visual_unavailable_warning() -> None:
    ids = _defects(
        '<p>See <a href="#fig-3" class="z2m-fig-link">Figure 3</a>.</p>'
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note" '
        'data-z2m-recovery-status="source_visual_unavailable">'
        "Figure 3 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">Figure 3. Caption text.</p>'
        "</div>"
    )

    assert "P13" not in ids
    assert "P14" not in ids


def test_figure_caption_ux_reports_internal_target_style_gap() -> None:
    ids = _defects('<p>See <a href="#fig-1">Figure 1</a>.</p>', has_internal_links=True)

    assert "P15" in ids


def test_figure_caption_ux_reports_delayed_image_after_missing_warning() -> None:
    ids = _defects(
        '<p class="z2m-missing-figure-warning">Figure 3 image was not extracted.</p>'
        "<p>caption continuation.</p>"
        '<p><img src="fig3.png"/></p>'
    )

    assert "P16" in ids


def test_figure_caption_ux_reports_plural_multipanel_reference() -> None:
    ids = _defects("<p>The figures 4(A), (B) show the result.</p>")

    assert "P17" in ids


def test_figure_caption_ux_reports_float_interruption() -> None:
    ids = _defects(
        "<p>The signal was stable and</p>"
        '<figure><img src="fig1.png"/></figure>'
        "<p>continued after the image.</p>"
    )

    assert "P30" in ids


def test_figure_caption_ux_reports_page_furniture_and_caption_intrusion() -> None:
    ids = _defects(
        "<p>Copyright 2024 Publisher.</p><p>2024 a, b). Each shank was inserted.</p>"
        "<p>human input (required) image-modeling task was visible.</p>"
    )

    assert "P18" in ids
    assert "P19" in ids


def test_audit_script_keeps_legacy_figure_caption_ux_aliases() -> None:
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_en_polish.py"
    spec = importlib.util.spec_from_file_location("audit_en_polish_caption_ux_alias_check", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._figure_caption_ux_defects_base is figure_caption_ux_defects
    assert module.CAPTION_TEX_RESIDUE_RE is CAPTION_TEX_RESIDUE_RE
