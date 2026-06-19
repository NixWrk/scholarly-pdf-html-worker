import re

from pdf_html_polish.quality_loop.audit_raw_blocks import (
    Defect,
    first_match_defect,
    parse_blocks,
    read_utf8,
    snippet_at,
    strip_tags,
)


def test_parse_blocks_keeps_image_presence_and_lines() -> None:
    blocks = parse_blocks("<p>Lead</p>\n<figure><img src='fig.png'> Caption</figure>")

    assert [(block.index, block.tag, block.text, block.has_img, block.line) for block in blocks] == [
        (0, "p", "Lead", False, 1),
        (1, "figure", "[IMG] Caption", True, 2),
    ]


def test_snippet_and_strip_tags_normalize_html_text() -> None:
    html = "<p>Alpha&nbsp;<b>Beta</b> Gamma</p>"

    assert strip_tags(html) == "Alpha Beta Gamma"
    assert snippet_at(html, html.index("Beta"), width=20) == "Alpha Beta Gamma"


def test_first_match_defect_records_count_examples_and_line() -> None:
    defect = first_match_defect(
        defect_id="RXX",
        check="Find repeated token",
        severity="info",
        pattern=re.compile(r"Page\s+\d+"),
        text="Intro\nPage 1\nBody Page 2",
        hypothesis="test",
        proposed_fix_layer="test layer",
        regression_test="test regression",
    )

    assert isinstance(defect, Defect)
    assert defect.line == 2
    assert defect.extra["count"] == 2
    assert defect.extra["examples"] == ["Page 1", "Body Page 2"]


def test_read_utf8_reports_empty_and_invalid_files(tmp_path) -> None:
    empty = tmp_path / "empty.html"
    empty.write_bytes(b"")
    data, text, defect = read_utf8(empty)
    assert data == b""
    assert text == ""
    assert defect is not None
    assert defect.id == "R01"

    invalid = tmp_path / "invalid.html"
    invalid.write_bytes(b"\xff")
    _, decoded, invalid_defect = read_utf8(invalid)
    assert "\ufffd" in decoded
    assert invalid_defect is not None
    assert invalid_defect.id == "R01"
