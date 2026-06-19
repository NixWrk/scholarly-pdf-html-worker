from pdf_html_polish.quality_loop.audit_float_gap import source_pdf_text_confirms_float_gap


def test_source_pdf_text_confirms_float_gap_when_float_label_sits_between_fragments() -> None:
    assert source_pdf_text_confirms_float_gap(
        "Alpha beta gamma delta",
        "Omega sigma theta lambda",
        "Alpha beta gamma delta Figure 2 shows the extracted plot Omega sigma theta lambda",
    )


def test_source_pdf_text_confirms_float_gap_rejects_plain_continuation() -> None:
    assert not source_pdf_text_confirms_float_gap(
        "Alpha beta gamma delta",
        "Omega sigma theta lambda",
        "Alpha beta gamma delta neutral connecting words Omega sigma theta lambda",
    )


def test_source_pdf_text_confirms_float_gap_requires_enough_context() -> None:
    assert not source_pdf_text_confirms_float_gap("Alpha beta", "Omega sigma", "Alpha beta Figure 2 Omega sigma")
    assert not source_pdf_text_confirms_float_gap("Alpha beta gamma", "Omega sigma theta", "")
