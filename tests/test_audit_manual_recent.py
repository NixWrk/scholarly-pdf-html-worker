import importlib.util
from pathlib import Path
import sys

from zoteropdf2md.quality_loop.audit_blocks import parse_blocks
from zoteropdf2md.quality_loop.audit_manual_recent import (
    ManualBlindSpotDeps,
    manual_blind_spot_defects,
    meine_recent_text_ocr_defects,
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


def test_audit_script_keeps_legacy_manual_blind_spot_aliases() -> None:
    audit = _load_audit_module()

    assert audit._manual_blind_spot_defects_base is manual_blind_spot_defects
    assert audit._meine_recent_text_ocr_defects_base is meine_recent_text_ocr_defects
    assert isinstance(audit._manual_blind_spot_deps(), ManualBlindSpotDeps)
    assert isinstance(audit._meine_recent_link_structure_deps(), audit.MeineRecentLinkDeps)
    assert isinstance(audit._meine_recent_text_ocr_deps(), audit.MeineRecentTextDeps)
