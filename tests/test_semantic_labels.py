from pdf_html_polish.semantic_labels import (
    extended_data_figure_key_from_visible_number,
    figure_key_from_visible_number,
    normalize_semantic_key,
    normalize_table_key,
    supplementary_figure_key_from_visible_number,
)


def test_normalize_semantic_key_collapses_separators() -> None:
    assert normalize_semantic_key(" 4 . 5. ") == "4-5"
    assert normalize_semantic_key("A \u2013 B") == "a-b"


def test_figure_key_from_visible_number_normalizes_supplement_prefix() -> None:
    assert figure_key_from_visible_number("S 1") == "s1"
    assert supplementary_figure_key_from_visible_number("S 1") == "supplementary-s1"
    assert extended_data_figure_key_from_visible_number("8A") == "extended-data-8a"


def test_normalize_table_key_uses_semantic_key_rules() -> None:
    assert normalize_table_key("II . A") == "ii-a"
