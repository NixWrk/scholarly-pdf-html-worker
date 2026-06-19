import importlib.util
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4

from pdf_html_polish.html_stages import RAW_STAGE_NAME
from pdf_html_polish.quality_loop.audit_raw_analysis import analyze_raw_file
from pdf_html_polish.quality_loop.audit_raw_report import (
    add_raw_corpus_hit_counts,
    build_raw_report,
    find_raw_stage_files,
    print_raw_report_summary,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "audit_en_raw.py"


def _make_temp_dir() -> Path:
    path = Path(".tmp_local2") / f"test_audit_en_raw_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_en_raw", AUDIT_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_raw_cli_preserves_legacy_aliases() -> None:
    audit = _load_audit_module()

    assert audit.STAGE_NAME == RAW_STAGE_NAME
    assert audit._analyze_raw_file is analyze_raw_file
    assert audit._add_corpus_hit_counts is add_raw_corpus_hit_counts
    assert audit._build_raw_report is build_raw_report
    assert audit.find_stage_files is find_raw_stage_files
    assert audit._print_summary is print_raw_report_summary


def test_analyze_file_reports_en_raw_defect_shapes() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        article_dir = tmp_path / "Kaiju sample"
        stage_dir = article_dir / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        html_path = stage_dir / "01.en.raw.html"
        html_path.write_text(
            "\n".join(
                [
                    "<!DOCTYPE html>",
                    "<html><body>",
                    "<h1>A 96ch flexible surface electrode array Thickness = 20\u0412\u00b5m "
                    "Gold 1st Parylene-C layer Silicon substrate Aluminium mask "
                    "Oxygen plasma etching Remove mask and Liftoff from silicon substrate</h1>",
                    "<p>FIGURE 1 | Electrode fabrication and experimental paradigm.</p>",
                    "<p>Page 2 of 10</p>",
                    "<p>Foilii etchingv 20 \u0412\u00b5 m.</p>",
                    "<p>@@Z2M_A_1</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_file(html_path)

        summary = result["en_raw_summary"]
        assert summary["bytes"] > 0
        assert summary["figure_labels"] == 1
        assert summary["page_headers"] == 1
        assert summary["raw_sentinels"] == 1
        assert summary["formula_unit_fragments"] >= 1

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert {"R05", "R06", "R07", "R08", "R12", "R14"}.issubset(defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_cli_writes_report_and_resolves_sidecar_images() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        root = tmp_path / "root"
        article_dir = root / "Ahmed sample"
        stage_dir = article_dir / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (article_dir / "_page_0_Picture_1.jpeg").write_bytes(b"fake-image")
        (stage_dir / "01.en.raw.html").write_text(
            (
                "<!DOCTYPE html><html><body>"
                "<p><img src=\"_page_0_Picture_1.jpeg\"/></p>"
                "<p>Figure 1. Caption near image.</p>"
                "</body></html>"
            ),
            encoding="utf-8",
        )
        out_path = tmp_path / "audit.json"

        exit_code = audit.main(["--roots", str(root), "--out", str(out_path), "--fail-on-error"])

        assert exit_code == 0
        report = json.loads(out_path.read_text(encoding="utf-8"))
        assert report["article_count"] == 1
        article = report["articles"][0]
        assert article["en_raw_summary"]["images"]["img_tags"] == 1
        assert article["en_raw_summary"]["images"]["missing_refs"] == []
        assert article["defects_found"] == []
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
