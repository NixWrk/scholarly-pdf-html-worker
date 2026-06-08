import json
from pathlib import Path
import sys

from zoteropdf2md.quality_loop.p62_marker import execute_marker_command


def test_execute_marker_command_skips_missing_command() -> None:
    report = execute_marker_command({}, timeout_seconds=1, cwd=Path.cwd())

    assert report == {"status": "skipped", "reason": "marker_command_unavailable", "returncode": None}


def test_execute_marker_command_writes_report_for_completed_command(tmp_path: Path) -> None:
    output_dir = tmp_path / "marker"

    report = execute_marker_command(
        {
            "marker_command": [sys.executable, "-c", "print('marker ok')"],
            "marker_output_dir": str(output_dir),
        },
        timeout_seconds=10,
        cwd=tmp_path,
    )

    saved = json.loads((output_dir / "marker_execution_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert report["returncode"] == 0
    assert "marker ok" in report["stdout_tail"]
    assert saved["status"] == "completed"
