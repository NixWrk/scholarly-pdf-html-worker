from zoteropdf2md import single_file_html
from zoteropdf2md.raw_html_polish.float_units import (
    caption_tail_opens_caption,
    embedded_table_caption_key_from_visible,
    figure_caption_num_from_visible,
    is_caption_node,
    is_figure_caption_node,
    is_table_caption_node,
    is_table_note_node,
    looks_table_note_text,
    raw_has_class,
    table_caption_key_from_visible,
)


def test_caption_tail_opens_caption_distinguishes_caption_from_prose_reference() -> None:
    assert caption_tail_opens_caption(". Cortical response after stimulation")
    assert not caption_tail_opens_caption(" shows cortical response")


def test_figure_caption_num_from_visible_handles_regular_compound_and_supplementary() -> None:
    assert figure_caption_num_from_visible("Fig. 3. Cortical response") == "3"
    assert figure_caption_num_from_visible("Figure 3.2. Compound caption") == "3-2"
    assert figure_caption_num_from_visible("Supplementary Fig. S2. Extra data") == "supplementary-s2"
    assert figure_caption_num_from_visible("Fig. 3 shows cortical response") is None


def test_table_caption_key_extractors() -> None:
    assert table_caption_key_from_visible("Table 1. Baseline characteristics") == "1"
    assert table_caption_key_from_visible("TABLE II: Outcomes") == "ii"
    assert embedded_table_caption_key_from_visible("Results are summarized in Table A1: details") == "a1"


def test_table_note_detection_helpers() -> None:
    assert raw_has_class('<p class="foo z2m-table-note">Note</p>', "z2m-table-note")
    assert looks_table_note_text("Abbreviations: BMI, body mass index")
    assert is_table_note_node('<p><sup>a</sup>Values represent mean SD.</p>')
    assert is_table_note_node('<p class="z2m-table-note">Any short note</p>')


def test_caption_node_predicates() -> None:
    assert is_figure_caption_node("<p>Fig. 2. Extracted image</p>")
    assert is_table_caption_node("<h3>Table 2. Data</h3>")
    assert is_caption_node("<p>Table 2. Data</p>")
    assert not is_caption_node("<p>Fig. 2 shows extracted image.</p>")


def test_single_file_html_keeps_legacy_private_float_aliases() -> None:
    assert single_file_html._figure_caption_num_from_visible is figure_caption_num_from_visible
    assert single_file_html._table_caption_key_from_visible is table_caption_key_from_visible
    assert single_file_html._is_caption_node is is_caption_node
