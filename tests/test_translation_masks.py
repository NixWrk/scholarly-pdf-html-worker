from zoteropdf2md import gemma_html
from zoteropdf2md.translation.masks import (
    apply_abbrev_mask,
    apply_formula_mask,
    apply_tag_mask,
    clean_final_text_fragment,
    restore_abbrev_mask,
    restore_formula_mask,
    restore_tag_mask,
)


def test_formula_mask_round_trips_math_and_urls() -> None:
    source = r"See \(x+y\) and https://example.org/path."

    masked, token_map = apply_formula_mask(source)

    assert "@@Z2MF" in masked
    assert restore_formula_mask(masked, token_map) == source


def test_abbrev_mask_protects_uppercase_and_science_terms() -> None:
    masked, token_map = apply_abbrev_mask("IEEE ECoG TiN signal")

    assert masked == "@@Z2M_A0@@ @@Z2M_A1@@ @@Z2M_A2@@ signal"
    assert restore_abbrev_mask(masked.replace("_A1@@", r"\_A1@@"), token_map) == "IEEE ECoG TiN signal"


def test_tag_mask_round_trips_escaped_sentinel_variants() -> None:
    masked, token_map = apply_tag_mask('<a href="#ref-1">1</a> text')

    assert masked == "@@Z2M_T0@@1@@Z2M_T1@@ text"
    assert restore_tag_mask(masked.replace("_T0@@", r"\_T0@@"), token_map) == '<a href="#ref-1">1</a> text'


def test_clean_final_text_fragment_strips_protocol_leaks() -> None:
    assert clean_final_text_fragment("IEEE@ @@Z2M_A0@@ text @@Z2M_HSEP@@ tail") == "IEEE text tail"


def test_gemma_html_reexports_translation_mask_helpers_for_compatibility() -> None:
    assert gemma_html._apply_formula_mask is apply_formula_mask
    assert gemma_html._restore_formula_mask is restore_formula_mask
    assert gemma_html._apply_abbrev_mask is apply_abbrev_mask
    assert gemma_html._restore_abbrev_mask is restore_abbrev_mask
    assert gemma_html._apply_tag_mask is apply_tag_mask
    assert gemma_html._restore_tag_mask is restore_tag_mask
