import json
import os
import sys
from pathlib import Path

import pytest

from conftest import write_attested_audit_command
from pdf_html_polish.quality_loop import commands as commands_module

from pdf_html_polish.quality_loop.commands import (
    run_quality_history,
    run_test_command,
    write_gate_report,
)
from pdf_html_polish.quality_loop.review_workflow import write_article_review_stage


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_run_test_command_defaults_to_repo_root_and_logs(tmp_path: Path) -> None:
    report = run_test_command(f"{json.dumps(sys.executable)} -c \"print('ok')\"", tmp_path)

    assert report["returncode"] == 0
    assert Path(report["stdout_path"]).is_file()
    assert "ok" in report["stdout_tail"]
    assert (tmp_path / "test_command_report.json").is_file()


@pytest.mark.parametrize("filename", ["test_stdout.log", "test_stderr.log"])
def test_run_test_command_unlinks_existing_hardlinked_logs_before_writing(
    tmp_path: Path,
    filename: str,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sentinel = tmp_path / f"outside_{filename}"
    sentinel.write_text("keep", encoding="utf-8")
    os.link(sentinel, run_dir / filename)

    report = run_test_command(
        f"{json.dumps(sys.executable)} -c \"print('ok')\"",
        run_dir,
    )

    assert report["returncode"] == 0
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert (run_dir / filename).is_file()


def test_run_test_command_rejects_link_like_run_directory_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run-link"
    monkeypatch.setattr(
        commands_module,
        "path_is_link_like",
        lambda path: Path(path) == run_dir,
    )

    with pytest.raises(ValueError, match="Test run directory is link-like"):
        run_test_command(
            f"{json.dumps(sys.executable)} -c \"print('should-not-run')\"",
            run_dir,
        )

    assert not (run_dir / "test_stdout.log").exists()
    assert not (run_dir / "test_stderr.log").exists()


def test_write_gate_report_loads_optional_stage_reports(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    gate_config_path = tmp_path / "gate.json"
    _write_json(run_dir / "audit_full_checks.json", {"corpus_summary": {"totals": {}}})
    write_attested_audit_command(run_dir)
    write_article_review_stage(
        run_dir,
        [],
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=lambda _source, _target: {},
    )
    run_quality_history(
        run_dir,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    _write_json(
        gate_config_path,
        {"allow_missing_previous": True, "max_regressions": 0, "max_total_deltas": {}},
    )

    report = write_gate_report(run_dir, gate_config_path)

    assert report["status"] == "pass"
    assert report["schema_version"] == 1
    assert [record["name"] for record in report["input_contract"]["inputs"]] == [
        "gate_config",
        "assessment",
        "quality_history_entry",
        "quality_previous_entry",
        "quality_compare",
        "article_review",
        "audit_report",
        "audit_command",
        "pdf_problem_evidence",
    ]
    assert (run_dir / "quality_gate_config_snapshot.json").is_file()
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
