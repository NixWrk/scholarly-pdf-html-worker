from pdf_html_polish.quality_loop.audit_p35 import replacement_char_defects


def test_replacement_char_defects_reports_visible_replacement_character() -> None:
    defects = replacement_char_defects("<p>value \ufffd remains</p>", "", stage="02.en.polish.html")

    assert [defect.id for defect in defects] == ["P35"]
    assert defects[0].extra == {"count": 1}


def test_replacement_char_defects_marks_pdf_source_noise_non_quality() -> None:
    defects = replacement_char_defects(
        "<p>SVRI dynes\ufffdsec\ufffdcm-5</p>",
        "SVRI dynes\x01sec\x01cm-5",
        stage="02.en.polish.html",
    )

    assert defects[0].extra == {
        "count": 2,
        "quality_counted": False,
        "source_pdf_text_layer_evidence": (
            "replacement characters align with source PDF text-layer symbol/OCR loss"
        ),
    }
