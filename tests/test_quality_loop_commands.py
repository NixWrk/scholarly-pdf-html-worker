import json
import sys
from pathlib import Path

from pdf_html_polish.quality_loop.commands import run_test_command, write_gate_report


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_run_test_command_defaults_to_repo_root_and_logs(tmp_path: Path) -> None:
    report = run_test_command(f"{json.dumps(sys.executable)} -c \"print('ok')\"", tmp_path)

    assert report["returncode"] == 0
    assert Path(report["stdout_path"]).is_file()
    assert "ok" in report["stdout_tail"]
    assert (tmp_path / "test_command_report.json").is_file()


def test_write_gate_report_loads_optional_stage_reports(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    gate_config_path = tmp_path / "gate.json"
    _write_json(run_dir / "quality_compare.json", {"status": "ok", "regressions": [], "improvements": []})
    _write_json(run_dir / "article_review_report.json", {"status": "not_required", "pending_mandatory_count": 0})
    _write_json(run_dir / "audit_full_checks.json", {"corpus_summary": {"totals": {}}})
    _write_json(run_dir / "audit_command_report.json", {"pdf_diagnostics_enabled": False})
    _write_json(gate_config_path, {"max_regressions": 0, "max_total_deltas": {}})

    report = write_gate_report(run_dir, gate_config_path)

    assert report["status"] == "pass"
    assert (run_dir / "quality_gate_report.json").is_file()


def test_write_gate_report_allows_missing_quality_compare_for_skip_history(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    gate_config_path = tmp_path / "gate.json"
    _write_json(
        gate_config_path,
        {"allow_missing_previous": True, "max_regressions": 0, "max_total_deltas": {}},
    )

    report = write_gate_report(run_dir, gate_config_path)

    assert report["status"] == "pass"
    assert report["regression_count"] == 0
    assert (run_dir / "quality_gate_report.json").is_file()
