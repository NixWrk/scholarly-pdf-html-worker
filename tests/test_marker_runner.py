from pathlib import Path
import json
import os
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pdf_html_polish.marker_runner as marker_runner_module

from pdf_html_polish.marker_runner import (
    MarkerRunner,
    ProgressContext,
    RunResult,
    _append_progress_jsonl,
    _count_page_range_pages,
    _marker_stall_timeout_seconds,
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
        for flag in (
            "--layout_batch_size",
            "--detection_batch_size",
            "--ocr_error_batch_size",
            "--recognition_batch_size",
            "--equation_batch_size",
        ):
            assert command[command.index(flag) + 1] == "1"


def test_marker_runner_uses_configured_conservative_batch_sizes() -> None:
    runner = _CapturingMarkerRunner()
    env = {
        "MARKER_LAYOUT_BATCH_SIZE": "2",
        "MARKER_DETECTION_BATCH_SIZE": "3",
        "MARKER_EQUATION_BATCH_SIZE": "0",
    }

    runner.run_single(
        pdf_path=Path("in") / "paper.pdf",
        output_dir=Path("out"),
        output_format="html",
        env=env,
        log=lambda _line: None,
    )

    command = runner.commands[0]
    assert command[command.index("--layout_batch_size") + 1] == "2"
    assert command[command.index("--detection_batch_size") + 1] == "3"
    assert command[command.index("--recognition_batch_size") + 1] == "1"
    assert "--equation_batch_size" not in command


def test_marker_batch_disables_multiprocessing_for_single_pdf(tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "paper.pdf").write_bytes(b"%PDF")
    runner = _CapturingMarkerRunner()

    runner.run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        skip_existing=False,
        disable_multiprocessing=False,
        output_format="html",
        env={},
        log=lambda _line: None,
    )

    assert "--disable_multiprocessing" in runner.commands[0]


def test_marker_batch_keeps_multiprocessing_for_multiple_pdfs(tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "a.pdf").write_bytes(b"%PDF")
    (input_dir / "b.pdf").write_bytes(b"%PDF")
    runner = _CapturingMarkerRunner()

    runner.run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        skip_existing=False,
        disable_multiprocessing=False,
        output_format="html",
        env={},
        log=lambda _line: None,
    )

    assert "--disable_multiprocessing" not in runner.commands[0]


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


def test_marker_stall_timeout_env_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("MARKER_STALL_TIMEOUT_SECONDS", raising=False)

    assert _marker_stall_timeout_seconds({}) == 0
    assert _marker_stall_timeout_seconds({"MARKER_STALL_TIMEOUT_SECONDS": "300"}) == 300
    assert _marker_stall_timeout_seconds({"MARKER_STALL_TIMEOUT_SECONDS": "bad"}) == 0


def test_marker_cleanup_kills_tracked_child_process() -> None:
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    runner = MarkerRunner()
    logs: list[str] = []
    try:
        runner._track_pid(process.pid)
        runner.cleanup_spawned_processes(logs.append)
        deadline = time.monotonic() + 5
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)

        assert process.poll() is not None
        assert any("Runner cleanup:" in line for line in logs)
    finally:
        if process.poll() is None:
            process.kill()


def test_marker_cleanup_does_not_kill_reused_pid(monkeypatch) -> None:
    terminated: list[int] = []

    class FakeProcess:
        pid = 73

        def create_time(self) -> float:
            return 200.0

        def children(self, recursive: bool = False) -> list[object]:
            return []

        def terminate(self) -> None:
            terminated.append(self.pid)

    fake_psutil = SimpleNamespace(
        Process=lambda _pid: FakeProcess(),
        NoSuchProcess=ProcessLookupError,
        wait_procs=lambda processes, timeout: (processes, []),
    )
    monkeypatch.setattr(marker_runner_module, "psutil", fake_psutil)

    assert MarkerRunner._kill_pid_tree(73, expected_create_time=100.0)
    assert terminated == []


def test_marker_runner_serializes_runs_per_instance() -> None:
    class BlockingRunner(MarkerRunner):
        def __init__(self) -> None:
            super().__init__()
            self.guard = threading.Lock()
            self.active = 0
            self.max_active = 0

        def _run_serialized(self, command, env, log, progress=None):  # type: ignore[override]
            with self.guard:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.05)
            with self.guard:
                self.active -= 1
            return RunResult(command=command, exit_code=0)

    runner = BlockingRunner()
    barrier = threading.Barrier(3)

    def run_one(label: str) -> None:
        barrier.wait()
        runner._run([label], {}, lambda _line: None)

    threads = [threading.Thread(target=run_one, args=(label,)) for label in ("a", "b")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert runner.max_active == 1


def test_marker_runner_cleans_tracking_after_normal_exit() -> None:
    class RecordingRunner(MarkerRunner):
        def __init__(self) -> None:
            super().__init__()
            self.cleanup_calls = 0

        def cleanup_spawned_processes(self, log=None):  # type: ignore[override]
            self.cleanup_calls += 1
            return super().cleanup_spawned_processes(log)

    runner = RecordingRunner()
    result = runner._run(
        [sys.executable, "-c", "print('done')"],
        dict(os.environ),
        lambda _line: None,
    )

    assert result.exit_code == 0
    assert runner.cleanup_calls == 1
    assert runner._tracked_snapshot() == []


def test_marker_runner_bounds_unterminated_stdout_lines() -> None:
    runner = MarkerRunner()
    logs: list[str] = []
    size = marker_runner_module._MAX_LOG_LINE_CHARS + 17

    result = runner._run(
        [sys.executable, "-c", f"print('x' * {size}, end='')"],
        dict(os.environ),
        logs.append,
    )

    output_chunks = [line for line in logs if line.startswith("x")]
    assert result.exit_code == 0
    assert len(output_chunks) == 2
    assert len(output_chunks[0]) <= marker_runner_module._MAX_LOG_LINE_CHARS + len(" [continued]")



def test_marker_runner_wraps_batch_in_gpu_container(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "paper.pdf").write_bytes(b"%PDF")
    output_dir = tmp_path / "output"
    cache_dir = tmp_path / "cache"
    runner = _CapturingMarkerRunner()
    env = {
        "MARKER_DOCKER_IMAGE": "zotero-pdf-html-worker:local",
        "MARKER_DOCKER_GPUS": "all",
        "MODEL_CACHE_DIR": str(cache_dir),
        "CUDA_VISIBLE_DEVICES": "1",
        "TORCH_DEVICE": "cuda",
        "HF_TOKEN": "super-secret",
    }

    runner.run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        skip_existing=False,
        disable_multiprocessing=False,
        output_format="html",
        env=env,
        log=lambda _line: None,
    )

    command = runner.commands[0]
    image_index = command.index("zotero-pdf-html-worker:local")
    assert command[:4] == ["docker", "run", "--rm", "--init"]
    assert command[command.index("--gpus") + 1] == "all"
    assert "CUDA_VISIBLE_DEVICES" in command
    assert "TORCH_DEVICE" in command
    assert "HF_TOKEN" in command
    assert all("super-secret" not in part for part in command)
    assert "MODEL_CACHE_DIR=/root/.cache/datalab/models" in command
    assert f"{input_dir.resolve()}:/marker-input:ro" in command
    assert f"{output_dir.resolve()}:/marker-output" in command
    assert f"{cache_dir.resolve()}:/root/.cache/datalab/models" in command
    assert command[image_index + 1 : image_index + 3] == ["marker", "/marker-input"]
    assert command[command.index("--output_dir") + 1] == "/marker-output"


def test_marker_runner_wraps_single_pdf_in_gpu_container(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    pdf = input_dir / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "output"
    runner = _CapturingMarkerRunner()

    runner.run_single(
        pdf_path=pdf,
        output_dir=output_dir,
        output_format="html",
        env={
            "MARKER_DOCKER_IMAGE": "zotero-pdf-html-worker:local",
            "MARKER_DOCKER_GPUS": "all",
            "MODEL_CACHE_DIR": str(tmp_path / "cache"),
            "CUDA_VISIBLE_DEVICES": "1",
        },
        log=lambda _line: None,
        page_range="2-4",
    )

    command = runner.commands[0]
    image_index = command.index("zotero-pdf-html-worker:local")
    assert command[image_index + 1 : image_index + 3] == [
        "marker_single",
        "/marker-input/paper.pdf",
    ]
    assert command[command.index("--page_range") + 1] == "2-4"


def test_marker_runner_cleanup_removes_active_container(monkeypatch) -> None:
    removed: list[str] = []
    runner = MarkerRunner()
    runner._track_container("zotero-marker-test")
    monkeypatch.setattr(
        runner,
        "_remove_docker_container",
        lambda name: removed.append(name) is None,
    )

    runner.cleanup_spawned_processes()

    assert removed == ["zotero-marker-test"]
    assert runner._active_containers_snapshot() == []
