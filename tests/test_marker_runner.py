from pathlib import Path
import json

from pdf_html_polish.marker_runner import (
    MarkerRunner,
    ProgressContext,
    RunResult,
    _append_progress_jsonl,
    _count_page_range_pages,
    _marker_status,
    _output_dir_snapshot,
    build_marker_single_command,
)


class _CapturingMarkerRunner(MarkerRunner):
    def __init__(self) -> None:
        super().__init__(marker_cmd="marker", marker_single_cmd="marker_single")
        self.commands: list[list[str]] = []

    def _run(self, command, env, log, progress=None):  # type: ignore[override]
        self.commands.append(command)
        assert progress is None or isinstance(progress, ProgressContext)
        return RunResult(command=command, exit_code=0)


def test_marker_runner_uses_300dpi_for_batch_and_single() -> None:
    runner = _CapturingMarkerRunner()

    runner.run_batch(
        input_dir=Path("in"),
        output_dir=Path("out"),
        skip_existing=False,
        disable_multiprocessing=False,
        output_format="html",
        env={},
        log=lambda _line: None,
    )
    runner.run_single(
        pdf_path=Path("in") / "paper.pdf",
        output_dir=Path("out"),
        output_format="html",
        env={},
        log=lambda _line: None,
    )

    for command in runner.commands:
        assert command[command.index("--lowres_image_dpi") + 1] == "300"
        assert command[command.index("--highres_image_dpi") + 1] == "300"


def test_marker_runner_supports_single_page_range() -> None:
    runner = _CapturingMarkerRunner()

    result = runner.run_single_page(
        pdf_path=Path("in") / "paper.pdf",
        output_dir=Path("out"),
        output_format="html",
        page_number=7,
        env={},
        log=lambda _line: None,
    )

    assert result.command[result.command.index("--page_range") + 1] == "6"
    assert runner.commands[0][runner.commands[0].index("--PdfProvider_pdftext_workers") + 1] == "1"
    assert "--disable_multiprocessing" in result.command
    assert _count_page_range_pages("0,5-10,20") == 8


def test_build_marker_single_command_matches_runner_defaults() -> None:
    command = build_marker_single_command(
        Path("paper.pdf"),
        Path("out"),
        "html",
        page_range="2",
    )

    assert command[:2] == ["marker_single", "paper.pdf"]
    assert command[command.index("--page_range") + 1] == "2"
    assert command[command.index("--lowres_image_dpi") + 1] == "300"


def test_marker_progress_writes_jsonl_and_current_status(tmp_path: Path) -> None:
    progress = ProgressContext(
        input_files=1,
        pages_total=12,
        output_dir=tmp_path,
        artifact_extension=".html",
    )
    payload = {
        "schema_version": 1,
        "kind": "process_alive",
        "status": "running",
        "heartbeat_index": 3,
    }

    _append_progress_jsonl(progress, payload)

    jsonl_lines = (tmp_path / "marker_progress.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(jsonl_lines) == 1
    assert json.loads(jsonl_lines[0])["heartbeat_index"] == 3
    assert json.loads((tmp_path / "marker_status.json").read_text(encoding="utf-8")) == payload


def test_output_dir_snapshot_tracks_artifacts_and_bytes(tmp_path: Path) -> None:
    (tmp_path / "paper.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"12345")
    (tmp_path / "marker_progress.jsonl").write_text("ignored", encoding="utf-8")
    (tmp_path / "marker_status.json").write_text("ignored", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "extra.html").write_text("x", encoding="utf-8")

    snapshot = _output_dir_snapshot(
        ProgressContext(
            input_files=1,
            pages_total=1,
            output_dir=tmp_path,
            artifact_extension=".html",
        )
    )

    assert snapshot["output_artifacts"] == 2
    assert snapshot["output_total_files"] == 3
    assert snapshot["output_total_bytes"] >= 18
    assert isinstance(snapshot["output_newest_mtime_epoch"], float)


def test_marker_status_marks_long_idle_process() -> None:
    assert (
        _marker_status(
            kind="process_alive",
            exit_code=None,
            elapsed_seconds=900,
            output_idle_seconds=900,
            first_output_seen=True,
        )
        == "running_idle"
    )
    assert (
        _marker_status(
            kind="complete",
            exit_code=0,
            elapsed_seconds=3,
            output_idle_seconds=1,
            first_output_seen=True,
        )
        == "completed"
    )
