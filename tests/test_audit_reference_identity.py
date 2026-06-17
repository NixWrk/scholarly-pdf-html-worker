from pdf_html_polish.quality_loop.audit_blocks import parse_blocks
from pdf_html_polish.quality_loop.audit_reference_identity import (
    is_references_block,
    looks_like_local_abstract_reference_block,
    numbered_reference_block_is_likely_non_bibliographic,
    reference_identity_defects,
)


def _ids(html: str) -> list[str]:
    return [defect.id for defect in reference_identity_defects(parse_blocks(html))]


def test_reference_identity_reports_ref_id_visible_number_mismatch() -> None:
    defects = _ids(
        '<h2>References</h2>'
        '<p id="ref-2">1. Smith A. Example Journal 2020.</p>'
    )

    assert "P21" in defects


def test_reference_identity_reports_duplicate_visible_numbers() -> None:
    defects = _ids(
        '<h2>References</h2>'
        '<p id="ref-1">1. Smith A. Example Journal 2020.</p>'
        '<p id="ref-1">1. Jones B. Example Journal 2021.</p>'
    )

    assert "P22" in defects


def test_reference_identity_reports_duplicate_bracket_prefix() -> None:
    defects = _ids(
        '<h2>References</h2>'
        '<p id="ref-1"><span class="z2m-ref-num">1.</span>[1] Smith A. Example Journal 2020.</p>'
    )

    assert "P27" in defects


def test_reference_identity_reports_embedded_numbered_reference() -> None:
    defects = _ids(
        '<h2>References</h2>'
        '<p id="ref-1">1. Smith A. Example Journal 2020. '
        '2. Jones, B. Example Journal 2021.</p>'
    )

    assert "P26" in defects


def test_reference_identity_reports_missing_visible_number() -> None:
    defects = _ids(
        '<h2>References</h2>'
        '<p id="ref-1">1. Smith A. Example Journal 2020.</p>'
        '<p id="ref-2">Jones B. Example Journal 2021.</p>'
    )

    assert "P97" in defects


def test_reference_identity_reference_block_helpers() -> None:
    blocks = parse_blocks(
        '<p>12 | Local abstract heading</p>'
        '<h2>References</h2>'
        '<p>1. Smith, A. doi: 10.1000/example</p>'
    )

    assert is_references_block(blocks[1], references_started=False)
    assert looks_like_local_abstract_reference_block(blocks, 2)
    assert numbered_reference_block_is_likely_non_bibliographic(parse_blocks("<p>1. Optional input.</p>")[0])


def test_audit_script_keeps_legacy_reference_identity_aliases() -> None:
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_en_polish.py"
    spec = importlib.util.spec_from_file_location("audit_en_polish_reference_identity_alias_check", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._reference_identity_defects is reference_identity_defects
    assert module._is_references_block is is_references_block
    assert module._looks_like_local_abstract_reference_block is looks_like_local_abstract_reference_block
    assert module._numbered_reference_block_is_likely_non_bibliographic is numbered_reference_block_is_likely_non_bibliographic
