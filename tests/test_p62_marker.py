import json
from pathlib import Path
import sys

from pdf_html_polish.quality_loop.p62_marker import execute_marker_command, validate_marker_output


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


def test_validate_marker_output_reports_not_run_for_missing_dir(tmp_path: Path) -> None:
    validation = validate_marker_output(tmp_path / "missing", "7")

    assert validation["status"] == "not_run"
    assert validation["html_count"] == 0
    assert validation["image_count"] == 0


def test_validate_marker_output_classifies_caption_and_images(tmp_path: Path) -> None:
    marker_dir = tmp_path / "marker"
    marker_dir.mkdir()
    (marker_dir / "index.html").write_text("<html><body><p>Figure 7. Caption.</p></body></html>", encoding="utf-8")

    validation = validate_marker_output(marker_dir, "7")
    assert validation["status"] == "caption_only"
    assert validation["label_present"] is True

    (marker_dir / "image.png").write_bytes(b"not a real png but marker output path exists")
    validation = validate_marker_output(marker_dir, "7")
    assert validation["status"] == "recovered_image"
    assert validation["image_count"] == 1


def test_validate_marker_output_reports_image_without_label(tmp_path: Path) -> None:
    marker_dir = tmp_path / "marker"
    marker_dir.mkdir()
    (marker_dir / "index.html").write_text("<html><body><p>No matching label.</p></body></html>", encoding="utf-8")
    (marker_dir / "image.jpg").write_bytes(b"fake")

    validation = validate_marker_output(marker_dir, "9")

    assert validation["status"] == "image_without_label"
    assert validation["label_present"] is False
