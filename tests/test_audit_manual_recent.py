import importlib.util
from pathlib import Path
import re
import sys

from pdf_html_polish.quality_loop.audit_blocks import parse_blocks
from pdf_html_polish.quality_loop.audit_manual_recent import (
    ManualBlindSpotDeps,
    MeineRecentLinkDeps,
    MeineRecentTextDeps,
    block_is_float_or_table_context,
    build_meine_recent_link_deps,
    build_meine_recent_text_deps,
    manual_blind_spot_defects,
    meine_recent_text_ocr_defects,
    non_reference_body_blocks,
    ref_match_inside_bracketed_reference_list,
    reference_target_numbers,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "audit_en_polish.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_en_polish_manual_recent_test", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manual_ids(html: str) -> list[str]:
    audit = _load_audit_module()
    return [defect.id for defect in audit._manual_blind_spot_defects(html, parse_blocks(html))]


def _recent_ids(html: str) -> list[str]:
    audit = _load_audit_module()
    return [defect.id for defect in audit._meine_recent_manual_defects(html, parse_blocks(html))]


def test_manual_blind_spot_reports_malformed_anchor() -> None:
    ids = _manual_ids('<p><a href="#ref-1">1</a></a></p>')

    assert "P34" in ids


def test_manual_blind_spot_reports_broken_visible_url() -> None:
    ids = _manual_ids("<p>Available at https:// creativecommons.org/licenses/by/4.0/ today.</p>")

    assert "P36" in ids


def test_manual_blind_spot_reports_lowercase_ref_glue() -> None:
    ids = _manual_ids('<p>functio <a href="#ref-13">n13</a> was measured.</p>')

    assert "P37" in ids


def test_manual_blind_spot_reports_float_sentence_split() -> None:
    ids = _manual_ids(
        "<p>The response was measured with</p>"
        '<figure><img src="fig1.png"/></figure>'
        "<p>continued observations after the image.</p>"
    )

    assert "P40" in ids


def test_meine_recent_link_structure_reports_shifted_visible_ref_label() -> None:
    ids = _recent_ids('<p>See <a href="#ref-2">1</a> for details.</p>')

    assert "P42" in ids


def test_meine_recent_link_structure_reports_decimal_equation_page_link() -> None:
    ids = _recent_ids('<p>Eqn. <a href="#page-4">2.1</a> describes the model.</p>')

    assert "P43" in ids


def test_meine_recent_link_structure_reports_bracket_citation_page_link() -> None:
    ids = _recent_ids('<p>Prior work <a href="#page-10">[1]</a> was cited.</p>')

    assert "P63" in ids


def test_meine_recent_text_ocr_reports_split_email_local_part() -> None:
    ids = _recent_ids("<p>simono v@example.com</p>")

    assert "P64" in ids


def test_meine_recent_text_ocr_reports_runaway_repeated_text() -> None:
    ids = _recent_ids("<p>slow, slow, slow, slow, slow, slow, slow.</p>")

    assert "P65" in ids


def test_reference_target_numbers_reads_ref_ids() -> None:
    html = '<ol><li id="ref-2">Two.</li><li id="ref-17">Seventeen.</li></ol>'

    assert reference_target_numbers(html) == {2, 17}


def test_block_is_float_or_table_context_detects_ids_and_classes() -> None:
    figure_block = parse_blocks('<p id="fig-1">Figure 1. Caption.</p>')[0]
    table_block = parse_blocks('<p class="z2m-table-unit">Table body.</p>')[0]
    body_block = parse_blocks("<p>Ordinary body text.</p>")[0]

    assert block_is_float_or_table_context(figure_block)
    assert block_is_float_or_table_context(table_block)
    assert not block_is_float_or_table_context(body_block)


def test_non_reference_body_blocks_skips_references_and_frontmatter() -> None:
    blocks = parse_blocks(
        '<p class="z2m-front-matter">Author 1</p>'
        "<p>Main body.</p>"
        "<h4>References</h4>"
        '<p id="ref-1">Smith reference.</p>'
    )

    assert [block.text for block in non_reference_body_blocks(blocks)] == ["Main body."]


def test_ref_match_inside_bracketed_reference_list_detects_linked_lists() -> None:
    raw = 'Prior work [<a href="#ref-1" class="z2m-ref-link">1</a>, 2] is cited.'
    anchor = re.search(r"<a\b[^>]*href=\"#ref-1\"[^>]*>1</a>", raw)
    assert anchor is not None

    assert ref_match_inside_bracketed_reference_list(raw, anchor.start(), anchor.end())
    assert not ref_match_inside_bracketed_reference_list(
        'Prior work <a href="#ref-1" class="z2m-ref-link">1</a> is cited.',
        anchor.start(),
        anchor.end(),
    )


def test_build_meine_recent_link_deps_wires_default_callbacks() -> None:
    deps = build_meine_recent_link_deps(
        author_year_text_re=re.compile(r"\bSmith\s+2020\b"),
        page_link_re=re.compile(r"<a href=\"#page-(?P<target>\d+)\">(?P<body>.*?)</a>"),
        figure_unit_re=re.compile(r"<div id=\"(?P<id>fig-\d+)\" class=\"z2m-figure-unit\">(?P<body>.*?)</div>"),
    )

    assert isinstance(deps, MeineRecentLinkDeps)
    assert deps.reference_target_numbers('<ol><li id="ref-7">Reference.</li></ol>') == {7}
    assert deps.ref_anchor_visible_number("7") == 7
    assert deps.figure_target_keys(
        '<div id="fig-2" class="z2m-figure-unit">'
        '<p class="z2m-figure-caption">Figure 2. Caption.</p>'
        "</div>"
    ) == {"2"}


def test_build_meine_recent_text_deps_wires_default_patterns_and_callbacks() -> None:
    deps = build_meine_recent_text_deps()

    assert isinstance(deps, MeineRecentTextDeps)
    assert deps.split_email_text_re.search("simono v@example.com") is not None
    assert deps.known_joined_word_re.search("Theexperiment") is not None
    assert deps.known_ocr_token_defects("inital", "", stage="07.en.polish.html")


def test_audit_script_keeps_legacy_manual_blind_spot_aliases() -> None:
    audit = _load_audit_module()

    assert audit._manual_blind_spot_defects_base is manual_blind_spot_defects
    assert audit._meine_recent_text_ocr_defects_base is meine_recent_text_ocr_defects
    assert isinstance(audit._manual_blind_spot_deps(), ManualBlindSpotDeps)
    assert isinstance(audit._meine_recent_link_structure_deps(), audit.MeineRecentLinkDeps)
    assert isinstance(audit._meine_recent_text_ocr_deps(), audit.MeineRecentTextDeps)
