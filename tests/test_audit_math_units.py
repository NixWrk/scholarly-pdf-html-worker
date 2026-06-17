from pdf_html_polish.quality_loop.audit_blocks import parse_blocks
from pdf_html_polish.quality_loop.audit_math_units import (
    equation_table_defects,
    inline_tex_contains_citation_bracket,
    unit_math_defects,
)


def test_unit_math_defects_reports_flattened_unit_exponents() -> None:
    blocks = parse_blocks("<p>The electrode area was 30 um2 and stable.</p>")

    defects = unit_math_defects("", blocks)

    assert [defect.id for defect in defects] == ["P06"]


def test_unit_math_defects_reports_citation_inside_inline_tex() -> None:
    blocks = parse_blocks(r"<p>The value was \(x + y [17]\).</p>")

    defects = unit_math_defects("", blocks)

    assert [defect.id for defect in defects] == ["P07"]


def test_unit_math_defects_reports_raw_display_math_ocr_when_polish_keeps_it() -> None:
    raw_html = r"<p>\[\frac{\omega}{2m}=1\]</p>"
    blocks = parse_blocks(raw_html)

    defects = unit_math_defects(raw_html, blocks)

    assert [defect.id for defect in defects] == ["P08"]


def test_equation_table_defects_reports_absorbed_prose() -> None:
    blocks = parse_blocks('<p block-type="Equation">x = y (1) To make this usable, text follows.</p>')

    defects = equation_table_defects(blocks)

    assert [defect.id for defect in defects] == ["P09"]


def test_inline_tex_citation_bracket_ignores_latex_optional_args() -> None:
    assert not inline_tex_contains_citation_bracket(r"\sqrt[2]{x}")
    assert inline_tex_contains_citation_bracket(r"x + y [12]")


def test_audit_script_keeps_legacy_math_unit_aliases() -> None:
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_en_polish.py"
    spec = importlib.util.spec_from_file_location("audit_en_polish_alias_check", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._unit_math_defects is unit_math_defects
    assert module._equation_table_defects is equation_table_defects
