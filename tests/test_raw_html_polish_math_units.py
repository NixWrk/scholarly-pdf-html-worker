from zoteropdf2md import single_file_html
from zoteropdf2md.raw_html_polish.math_units import (
    convert_latex_sup_citations,
    convert_math_tags_to_tex,
    fix_latex_text_commands,
    fix_subscript_equation_spill,
    move_trailing_bracket_citations_out_of_inline_tex,
    repair_common_math_ocr_substitutions,
    repair_sqrt_subscript_brace_spill,
)


def test_fix_subscript_equation_spill_moves_large_continuation_outside_braces() -> None:
    source = r"\gamma_{ij=\frac{2a_ib_j}{a_i^2+b_j^2}}"

    assert fix_subscript_equation_spill(source) == r"\gamma_{ij}=\frac{2a_ib_j}{a_i^2+b_j^2}"


def test_fix_latex_text_commands_converts_basic_text_markup() -> None:
    source = r"\label{eq:test}\textbf{Bold} and \emph{italic} with \textrm{plain}"

    assert fix_latex_text_commands(source) == "<strong>Bold</strong> and <em>italic</em> with plain"


def test_move_trailing_bracket_citations_out_of_inline_tex() -> None:
    source = r"<p>\(x+y [12, 13]\)</p>"

    assert move_trailing_bracket_citations_out_of_inline_tex(source) == r"<p>\(x+y\) [12, 13]</p>"


def test_repair_common_math_ocr_substitutions_repairs_static_tex_bodies() -> None:
    source = r"<p>\(\frac{\omega}{2m}=1\)</p>"

    assert repair_common_math_ocr_substitutions(source) == r"<p>\(\frac{\omega}{\omega_0}=1\)</p>"


def test_convert_math_tags_to_tex_leaves_real_mathml_untouched() -> None:
    assert convert_math_tags_to_tex('<math display="block">x+y</math>') == r"\[x+y\]"
    mathml = "<math><mi>x</mi></math>"
    assert convert_math_tags_to_tex(mathml) == mathml


def test_convert_latex_sup_citations_promotes_inline_math_citations() -> None:
    assert convert_latex_sup_citations(r"Text \(^{153-156}\)") == "Text <sup>153-156</sup>"


def test_single_file_html_keeps_legacy_private_math_aliases() -> None:
    assert single_file_html._fix_subscript_equation_spill is fix_subscript_equation_spill
    assert single_file_html._repair_sqrt_subscript_brace_spill is repair_sqrt_subscript_brace_spill
