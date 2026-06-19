from pdf_html_polish.quality_loop.audit_raw_blocks import parse_blocks
from pdf_html_polish.quality_loop.audit_raw_checks import (
    all_caps_heading_defects,
    anchor_summary,
    caption_without_image_defects,
    heading_ocr_defects,
    major_tag_defects,
    mojibake_micro_count,
    references_summary,
)


def test_major_tag_defects_reports_missing_body_close() -> None:
    defects = major_tag_defects("<html><body><p>Open")

    assert [defect.id for defect in defects] == ["R02", "R02"]
    assert [defect.extra for defect in defects] == [
        {"tag": "html", "open": 1, "close": 0},
        {"tag": "body", "open": 1, "close": 0},
    ]


def test_caption_without_image_defects_uses_block_window() -> None:
    blocks = parse_blocks("<p>Figure 1. Caption without image.</p>")

    defects = caption_without_image_defects(blocks)

    assert [defect.id for defect in defects] == ["R05"]
    assert defects[0].extra["block_index"] == 0


def test_heading_ocr_defects_detects_panel_heading_before_caption() -> None:
    blocks = parse_blocks(
        "<h1>"
        "A 96ch flexible surface electrode array Thickness Gold Silicon substrate "
        "Aluminium mask Oxygen plasma etching Remove mask and Liftoff recording array"
        "</h1>"
        "<p>FIGURE 1 | Caption.</p>"
    )

    assert [defect.id for defect in heading_ocr_defects(blocks)] == ["R06"]


def test_all_caps_heading_defects_detects_figure_or_table_heading() -> None:
    blocks = parse_blocks("<h2>TABLE 1 CHARACTERISTICS OF INCLUDED SUBJECTS AND RECORDINGS</h2>")

    assert [defect.id for defect in all_caps_heading_defects(blocks)] == ["R13"]


def test_references_and_anchor_summaries() -> None:
    text = '<p id="x"><a href="#ref-1">1</a> &lt;a href="#bad"&gt; References tail</p>'

    assert references_summary(text)["found"] is True
    assert anchor_summary(text) == {"anchors": 1, "escaped_anchors": 1, "ids": 1, "hrefs": 2}


def test_mojibake_micro_count() -> None:
    assert mojibake_micro_count("20 \u0412\u00b5m and 30 um") == 1
