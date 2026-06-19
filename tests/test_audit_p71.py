from pdf_html_polish.quality_loop.audit_p71 import (
    known_ocr_token_defects,
    known_ocr_token_is_present_in_pdf_text_layer,
)


def test_known_ocr_token_defects_reports_curated_token() -> None:
    defects = known_ocr_token_defects("The test mentions urflowmetry in prose.", "", stage="02.en.polish.html")

    assert [defect.id for defect in defects] == ["P71"]
    assert defects[0].extra == {"match": "urflowmetry"}


def test_known_ocr_token_defects_accepts_curated_false_positive_context() -> None:
    assert known_ocr_token_defects("The IRIT-ELIPSE project is named here.", "", stage="02.en.polish.html") == []
    assert known_ocr_token_defects("Downloaded from OceanofPDF.com", "", stage="02.en.polish.html") == []
    assert (
        known_ocr_token_defects(
            "TOOTEKO: A case study of augmented reality for an accessible cultural heritage.",
            "",
            stage="02.en.polish.html",
        )
        == []
    )


def test_known_ocr_token_defects_marks_pdf_layer_evidence_non_quality() -> None:
    defects = known_ocr_token_defects(
        "The source spelling says Uroflowmetery here.",
        "The PDF text layer also says Uroflowmetery here.",
        stage="02.en.polish.html",
    )

    assert defects[0].extra == {
        "match": "Uroflowmetery",
        "quality_counted": False,
        "source_pdf_text_layer_evidence": "known OCR token is already present in the source PDF text layer",
    }


def test_known_ocr_token_pdf_layer_evidence_matches_normalized_word_sequence() -> None:
    assert known_ocr_token_is_present_in_pdf_text_layer("Qavg and Omax", "Qavg\nand\tOmax")
