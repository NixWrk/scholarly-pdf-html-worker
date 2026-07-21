from pdf_html_polish.quality_loop.audit_blocks import Block
from pdf_html_polish.quality_loop.audit_diagnostics import (
    DIAGNOSTIC_SPECS,
    diagnostic_spec,
    make_defect,
)


def test_current_loop_diagnostics_have_audit_metadata() -> None:
    for defect_id in (
        "P04N",
        "P04M",
        "P04T",
        "P35",
        "P45M",
        "P45S",
        "P61",
        "P62",
        "P62A",
        "P62B",
        "P71",
    ):
        spec = diagnostic_spec(defect_id)

        assert spec is not None
        assert spec.id == defect_id
        assert spec.detector.startswith("_")
        assert spec.summary
        assert spec.audit_signal
        assert spec.repair_hint


def test_diagnostic_catalog_keeps_observed_telemetry_non_quality_by_default() -> None:
    for defect_id in (
        "P04N",
        "P04M",
        "P04T",
        "P45M",
        "P45S",
        "P61",
        "P62",
        "P62A",
        "P62B",
    ):
        assert DIAGNOSTIC_SPECS[defect_id].quality_counted_by_default is False
    for defect_id in ("P35", "P71"):
        assert DIAGNOSTIC_SPECS[defect_id].quality_counted_by_default is True


def test_make_defect_matches_audit_defect_contract() -> None:
    block = Block(index=0, tag="p", attrs={}, raw="<p>x</p>", text="x", line=42)
    defect = make_defect(
        defect_id="P62",
        cc_class="figure-integrity",
        check="Missing-figure warning has no nearby image",
        severity="warning",
        block=block,
        snippet="a" * 400,
        stage="02.en.polish.html",
        hypothesis="Visible warning remained in final HTML.",
        proposed_fix_layer="Marker image extraction diagnostics or review packaging",
        regression_test="Missing figure warnings are classified by nearby image context.",
        extra={"quality_counted": False},
    )

    assert defect.id == "P62"
    assert defect.line == 42
    assert len(defect.snippet) == 260
    assert defect.extra == {"quality_counted": False}


def test_make_defect_applies_catalog_quality_default_and_allows_override() -> None:
    kwargs = {
        "defect_id": "P62",
        "cc_class": "ocr",
        "check": "Known OCR token remains",
        "severity": "warning",
        "block": None,
        "snippet": "effekt iv",
        "stage": "02.en.polish.html",
        "hypothesis": "OCR residue",
        "proposed_fix_layer": "EN polish OCR residue scanner",
        "regression_test": "Telemetry stays non-quality unless explicitly promoted.",
    }

    assert make_defect(**kwargs).extra == {"quality_counted": False}
    assert make_defect(**kwargs, extra={"quality_counted": True}).extra == {
        "quality_counted": True
    }
