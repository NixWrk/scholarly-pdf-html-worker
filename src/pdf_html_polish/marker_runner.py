from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

try:
    import psutil  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None


_PROGRESS_FILE_NAMES = {
    "marker_progress.jsonl",
    "marker_status.json",
    "marker_status.json.tmp",
}
_MAX_LOG_LINE_CHARS = 64 * 1024
_PROCESS_SCAN_INTERVAL_SECONDS = 1.0
_HEARTBEAT_INTERVAL_SECONDS = 10.0


@dataclass(frozen=True)
class RunResult:
    command: list[str]
    exit_code: int


@dataclass(frozen=True)
class ProgressContext:
    input_files: int
    pages_total: int | None
    output_dir: Path | None
    artifact_extension: str


@dataclass(frozen=True)
class _TrackedProcess:
    pid: int
    create_time: float | None


def build_marker_single_command(
    pdf_path: Path,
    output_dir: Path,
    output_format: str,
    *,
    marker_single_cmd: str = "marker_single",
    page_range: str | None = None,
    disable_multiprocessing: bool = False,
) -> list[str]:
    cmd = [
        marker_single_cmd,
        str(pdf_path),
        "--output_dir",
        str(output_dir),
        "--output_format",
        output_format,
        "--drop_repeated_text",
        "--drop_repeated_table_text",
        "--lowres_image_dpi",
        "300",
        "--highres_image_dpi",
        "300",
        "--PdfProvider_pdftext_workers",
        "1",
    ]
    if disable_multiprocessing:
        cmd.append("--disable_multiprocessing")
    if page_range:
        cmd.extend(["--page_range", str(page_range)])
    return cmd


class MarkerRunner:
    def __init__(
        self,
        marker_cmd: str = "marker",
        marker_single_cmd: str = "marker_single",
    ) -> None:
        self._marker_cmd = marker_cmd
        self._marker_single_cmd = marker_single_cmd
        self._current_process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._tracked_pids: dict[int, float | None] = {}

    @staticmethod
    def _pid_create_time(pid: int) -> float | None:
        if psutil is None or pid <= 0:
            return None
        try:
            return float(psutil.Process(pid).create_time())
        except Exception:
            return None

    def _track_pid(self, pid: int) -> None:
        if pid <= 0:
            return
        create_time = self._pid_create_time(pid)
        with self._lock:
            self._tracked_pids[pid] = create_time

    def _tracked_snapshot(self) -> list[_TrackedProcess]:
        with self._lock:
            return [
                _TrackedProcess(pid=pid, create_time=create_time)
                for pid, create_time in sorted(self._tracked_pids.items())
            ]

    def _register_child_pids(self, root_pid: int) -> None:
        if psutil is None or root_pid <= 0:
            return
        try:
            process = psutil.Process(root_pid)
            children = process.children(recursive=True)
        except Exception:
            return
        for child in children:
            self._track_pid(child.pid)

    @staticmethod
    def _kill_pid_tree(pid: int, expected_create_time: float | None = None) -> bool:
        if pid <= 0:
            return True

        if psutil is not None:
            try:
                root = psutil.Process(pid)
                if expected_create_time is not None:
                    actual_create_time = float(root.create_time())
                    if abs(actual_create_time - expected_create_time) > 0.001:
                        return True
                processes = [*root.children(recursive=True), root]
                for process in processes:
                    with suppress(Exception):
                        process.terminate()
                gone, alive = psutil.wait_procs(processes, timeout=2)
                for process in alive:
                    with suppress(Exception):
                        process.kill()
                psutil.wait_procs(alive, timeout=2)
                return True
            except psutil.NoSuchProcess:
                return True
            except Exception:
                if expected_create_time is not None:
                    return False

        if os.name != "nt":
            try:
                kill_process_group = getattr(os, "killpg", None)
                if callable(kill_process_group):
                    kill_process_group(pid, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
                return True
            except ProcessLookupError:
                return True
            except Exception:
                return False

        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return False

        if result.returncode == 0:
            return True

        output = (result.stdout or "").lower()
        return (
            "not found" in output
            or "no running instance" in output
            or "not running" in output
        )

    def cleanup_spawned_processes(self, log: Callable[[str], None] | None = None) -> None:
        tracked = self._tracked_snapshot()
        if not tracked:
            return

        killed = 0
        remaining: dict[int, float | None] = {}
        for process in tracked:
            if self._kill_pid_tree(process.pid, process.create_time):
                killed += 1
            else:
                remaining[process.pid] = process.create_time

        with self._lock:
            self._tracked_pids = remaining

        if log is not None:
            log(
                "Runner cleanup: "
                f"tracked={len(tracked)}, killed={killed}, remaining={len(remaining)}"
            )
            if remaining:
                log(f"Runner cleanup remaining PIDs: {', '.join(str(pid) for pid in remaining)}")

    def _stop_process_tree(
        self,
        process: subprocess.Popen[str],
        *,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self._track_pid(process.pid)
        self._register_child_pids(process.pid)
        with suppress(Exception):
            process.terminate()
        with suppress(Exception):
            process.wait(timeout=2)
        if process.poll() is None:
            self._kill_pid_tree(process.pid, self._pid_create_time(process.pid))
        self.cleanup_spawned_processes(log)

    def terminate_current(self) -> None:
        with self._lock:
            proc = self._current_process
        if proc is not None and proc.poll() is None:
            self._stop_process_tree(proc)
        else:
            self.cleanup_spawned_processes()

    def _run(
        self,
        command: list[str],
        env: dict[str, str],
        log: Callable[[str], None],
        progress: ProgressContext | None = None,
    ) -> RunResult:
        with self._run_lock:
            return self._run_serialized(command, env, log, progress)

    def _run_serialized(
        self,
        command: list[str],
        env: dict[str, str],
        log: Callable[[str], None],
        progress: ProgressContext | None = None,
    ) -> RunResult:
        run_started_at = perf_counter()
        log("$ " + " ".join(f'"{part}"' if " " in part else part for part in command))
        spawn_started_at = perf_counter()
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
            start_new_session=os.name != "nt",
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            ),
        )
        log(f"[timer] runner.spawn_process: {perf_counter() - spawn_started_at:.2f}s")
        log(f"Runner process started: pid={process.pid}")
        self._track_pid(process.pid)

        with self._lock:
            self._current_process = process

        first_output_at: float | None = None
        last_output_at: float | None = None
        last_filesystem_activity_at = run_started_at
        last_output_signature: tuple[object, ...] | None = None
        heartbeat_index = 0
        max_output_gap = 0.0
        line_count = 0
        last_marker_line = ""
        heartbeat_stop = threading.Event()
        stall_stop_sent = threading.Event()
        stall_timeout_seconds = _marker_stall_timeout_seconds(env)

        def log_progress(kind: str, exit_code: int | None = None) -> dict[str, object]:
            nonlocal heartbeat_index
            nonlocal last_filesystem_activity_at
            nonlocal last_output_signature

            heartbeat_index += 1
            elapsed = perf_counter() - run_started_at
            since_last_output = None if last_output_at is None else perf_counter() - last_output_at
            snapshot = _process_tree_snapshot(process.pid)
            output_snapshot = _output_dir_snapshot(progress)
            output_signature = _output_activity_signature(output_snapshot)
            if last_output_signature is None:
                last_output_signature = output_signature
            elif output_signature != last_output_signature:
                last_filesystem_activity_at = perf_counter()
                last_output_signature = output_signature

            output_idle_seconds = perf_counter() - last_filesystem_activity_at
            stdout_idle_seconds = elapsed if last_output_at is None else perf_counter() - last_output_at
            stall_idle_seconds = min(output_idle_seconds, stdout_idle_seconds)
            status = _marker_status(
                kind=kind,
                exit_code=exit_code,
                elapsed_seconds=elapsed,
                output_idle_seconds=output_idle_seconds,
                first_output_seen=first_output_at is not None,
            )
            payload = {
                "schema_version": 1,
                "kind": kind,
                "status": status,
                "updated_at": _utc_now_iso(),
                "heartbeat_index": heartbeat_index,
                "elapsed_seconds": round(elapsed, 2),
                "since_last_output_seconds": (
                    None if since_last_output is None else round(since_last_output, 2)
                ),
                "output_idle_seconds": round(output_idle_seconds, 2),
                "stall_idle_seconds": round(stall_idle_seconds, 2),
                "stall_timeout_seconds": (
                    None if stall_timeout_seconds <= 0 else round(stall_timeout_seconds, 2)
                ),
                "possibly_stalled": status == "running_idle",
                "exit_code": exit_code,
                "stdout_lines": line_count,
                "last_marker_line": last_marker_line,
                "input_files": progress.input_files if progress is not None else None,
                "pages_total": progress.pages_total if progress is not None else None,
                **output_snapshot,
                **snapshot,
            }
            log(_format_progress_payload(payload))
            _append_progress_jsonl(progress, payload)
            return payload

        def stop_if_stalled(payload: dict[str, object]) -> None:
            if stall_timeout_seconds <= 0 or stall_stop_sent.is_set():
                return
            if process.poll() is not None:
                return
            raw_idle_seconds = payload.get("stall_idle_seconds")
            if not isinstance(raw_idle_seconds, (int, float, str)):
                return
            try:
                idle_seconds = float(raw_idle_seconds)
            except ValueError:
                return
            if idle_seconds < stall_timeout_seconds:
                return
            stall_stop_sent.set()
            log(
                "Marker stall watchdog stopping process: "
                f"idle={idle_seconds:.1f}s timeout={stall_timeout_seconds:.1f}s"
            )
            self._stop_process_tree(process, log=log)

        def heartbeat() -> None:
            next_heartbeat_at = perf_counter() + _HEARTBEAT_INTERVAL_SECONDS
            while not heartbeat_stop.wait(_PROCESS_SCAN_INTERVAL_SECONDS):
                self._register_child_pids(process.pid)
                if perf_counter() < next_heartbeat_at:
                    continue
                next_heartbeat_at = perf_counter() + _HEARTBEAT_INTERVAL_SECONDS
                if first_output_at is None:
                    payload = log_progress("waiting_first_output")
                else:
                    payload = log_progress("process_alive")
                stop_if_stalled(payload)

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()
        log_progress("started")

        try:
            assert process.stdout is not None
            line_buffer: list[str] = []

            def emit_line(line: str, emitted_at: float) -> None:
                nonlocal first_output_at
                nonlocal last_output_at
                nonlocal max_output_gap
                nonlocal line_count
                nonlocal last_marker_line

                if first_output_at is None:
                    first_output_at = emitted_at
                    log(f"[timer] runner.first_output: {first_output_at - run_started_at:.2f}s")
                if last_output_at is not None:
                    max_output_gap = max(max_output_gap, emitted_at - last_output_at)
                last_output_at = emitted_at
                line_count += 1
                last_marker_line = line
                log(line)
                if _looks_like_marker_progress_line(line):
                    log_progress("marker_stdout_progress")

            while True:
                ch = process.stdout.read(1)
                if ch == "":
                    break

                now = perf_counter()
                if ch in ("\n", "\r"):
                    if line_buffer:
                        emit_line("".join(line_buffer), now)
                        line_buffer = []
                else:
                    line_buffer.append(ch)
                    if len(line_buffer) >= _MAX_LOG_LINE_CHARS:
                        emit_line("".join(line_buffer) + " [continued]", now)
                        line_buffer = []
            if line_buffer:
                emit_line("".join(line_buffer), perf_counter())

            wait_started_at = perf_counter()
            exit_code = process.wait()
            log(f"[timer] runner.wait_after_stdout_eof: {perf_counter() - wait_started_at:.2f}s")
            if first_output_at is None:
                log("[timer] runner.first_output: no output before process exit")
            if last_output_at is not None:
                log(f"[timer] runner.last_output: {last_output_at - run_started_at:.2f}s")
            log(f"[timer] runner.total: {perf_counter() - run_started_at:.2f}s")
            log(
                "Runner diagnostics: "
                f"exit_code={exit_code}, "
                f"stdout_lines={line_count}, "
                f"max_gap_between_lines={max_output_gap:.2f}s"
            )
            log_progress("complete", exit_code=exit_code)
            return RunResult(command=command, exit_code=exit_code)
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=0.2)
            self._register_child_pids(process.pid)
            with self._lock:
                if self._current_process is process:
                    self._current_process = None
                self._tracked_pids.pop(process.pid, None)
            self.cleanup_spawned_processes(log)

    def run_batch(
        self,
        input_dir: Path,
        output_dir: Path,
        skip_existing: bool,
        disable_multiprocessing: bool,
        output_format: str,
        env: dict[str, str],
        log: Callable[[str], None],
    ) -> RunResult:
        input_files = _count_input_pdfs(input_dir)
        disable_multiprocessing = disable_multiprocessing or input_files <= 1
        cmd = [
            self._marker_cmd,
            str(input_dir),
            "--output_dir",
            str(output_dir),
            "--output_format",
            output_format,
            "--drop_repeated_text",
            "--drop_repeated_table_text",
            "--lowres_image_dpi",
            "300",
            "--highres_image_dpi",
            "300",
        ]
        if skip_existing:
            cmd.append("--skip_existing")
        if disable_multiprocessing:
            cmd.append("--disable_multiprocessing")
        progress = ProgressContext(
            input_files=input_files,
            pages_total=_count_total_pdf_pages(input_dir.glob("*.pdf")),
            output_dir=output_dir,
            artifact_extension=_artifact_extension_for_output_format(output_format),
        )
        return self._run(cmd, env, log, progress=progress)

    def run_single(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_format: str,
        env: dict[str, str],
        log: Callable[[str], None],
        page_range: str | None = None,
        disable_multiprocessing: bool = False,
    ) -> RunResult:
        cmd = build_marker_single_command(
            pdf_path,
            output_dir,
            output_format,
            marker_single_cmd=self._marker_single_cmd,
            page_range=page_range,
            disable_multiprocessing=disable_multiprocessing,
        )
        progress = ProgressContext(
            input_files=1,
            pages_total=_count_page_range_pages(page_range) or _count_total_pdf_pages([pdf_path]),
            output_dir=output_dir,
            artifact_extension=_artifact_extension_for_output_format(output_format),
        )
        return self._run(cmd, env, log, progress=progress)

    def run_single_page(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_format: str,
        page_number: int,
        env: dict[str, str],
        log: Callable[[str], None],
    ) -> RunResult:
        """Run marker on one 1-based PDF page.

        Marker's CLI expects zero-based page ranges, so this helper keeps the
        public call aligned with PDF render/evidence page numbering.
        """

        if page_number < 1:
            raise ValueError("page_number must be 1-based and positive.")
        return self.run_single(
            pdf_path,
            output_dir,
            output_format,
            env,
            log,
            page_range=str(page_number - 1),
            disable_multiprocessing=True,
        )


def _artifact_extension_for_output_format(output_format: str) -> str:
    normalized = str(output_format or "").strip().lower().lstrip(".")
    if normalized == "html":
        return ".html"
    if normalized == "markdown":
        return ".md"
    return f".{normalized}" if normalized else ".html"


def _count_input_pdfs(input_dir: Path) -> int:
    try:
        return sum(1 for path in input_dir.glob("*.pdf") if path.is_file())
    except OSError:
        return 0


def _count_total_pdf_pages(paths: Iterable[Path]) -> int | None:
    total = 0
    seen = False
    for path in paths:
        page_count = _count_pdf_pages(Path(path))
        if page_count is None:
            continue
        seen = True
        total += page_count
    return total if seen else None


def _count_page_range_pages(page_range: str | None) -> int | None:
    if not page_range:
        return None
    total = 0
    for raw_part in str(page_range).split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = (item.strip() for item in part.split("-", 1))
            if not left.isdigit() or not right.isdigit():
                return None
            start = int(left)
            end = int(right)
            if end < start:
                return None
            total += end - start + 1
            continue
        if not part.isdigit():
            return None
        total += 1
    return total or None


def _count_pdf_pages(path: Path) -> int | None:
    try:
        import fitz  # type: ignore[import-untyped]

        with fitz.open(str(path)) as doc:
            return int(doc.page_count)
    except Exception:
        pass
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(path))
        return len(reader.pages)
    except Exception:
        return None


def _output_dir_snapshot(progress: ProgressContext | None) -> dict[str, object]:
    empty: dict[str, object] = {
        "output_artifacts": None,
        "output_total_files": None,
        "output_total_bytes": None,
        "output_newest_mtime_epoch": None,
    }
    if progress is None or progress.output_dir is None:
        return empty

    try:
        artifact_extension = progress.artifact_extension.lower()
        output_artifacts = 0
        output_total_files = 0
        output_total_bytes = 0
        newest_mtime: float | None = None
        for path in progress.output_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.name in _PROGRESS_FILE_NAMES:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            output_total_files += 1
            output_total_bytes += int(stat.st_size)
            newest_mtime = (
                stat.st_mtime
                if newest_mtime is None
                else max(newest_mtime, stat.st_mtime)
            )
            if path.name.lower().endswith(artifact_extension):
                output_artifacts += 1
        return {
            "output_artifacts": output_artifacts,
            "output_total_files": output_total_files,
            "output_total_bytes": output_total_bytes,
            "output_newest_mtime_epoch": newest_mtime,
        }
    except OSError:
        return empty


def _output_activity_signature(snapshot: dict[str, object]) -> tuple[object, ...]:
    return (
        snapshot.get("output_artifacts"),
        snapshot.get("output_total_files"),
        snapshot.get("output_total_bytes"),
        snapshot.get("output_newest_mtime_epoch"),
    )


def _marker_status(
    *,
    kind: str,
    exit_code: int | None,
    elapsed_seconds: float,
    output_idle_seconds: float,
    first_output_seen: bool,
) -> str:
    if kind == "complete":
        return "completed" if exit_code == 0 else "failed"
    if not first_output_seen and elapsed_seconds < 60:
        return "starting"
    if output_idle_seconds >= 600:
        return "running_idle"
    return "running"


def _marker_stall_timeout_seconds(env: dict[str, str]) -> float:
    raw_value = env.get("MARKER_STALL_TIMEOUT_SECONDS") or os.environ.get(
        "MARKER_STALL_TIMEOUT_SECONDS",
        "",
    )
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, value)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _process_tree_snapshot(root_pid: int) -> dict[str, object]:
    if psutil is None or root_pid <= 0:
        return {
            "process_count": None,
            "cpu_percent": None,
            "rss_mb": None,
            "child_pids": [],
        }
    try:
        root = psutil.Process(root_pid)
        processes = [root, *root.children(recursive=True)]
    except Exception:
        return {
            "process_count": None,
            "cpu_percent": None,
            "rss_mb": None,
            "child_pids": [],
        }

    cpu_percent = 0.0
    rss_bytes = 0
    child_pids: list[int] = []
    for process in processes:
        try:
            cpu_percent += float(process.cpu_percent(interval=None))
            rss_bytes += int(process.memory_info().rss)
            if process.pid != root_pid:
                child_pids.append(int(process.pid))
        except Exception:
            continue
    return {
        "process_count": len(processes),
        "cpu_percent": round(cpu_percent, 1),
        "rss_mb": round(rss_bytes / (1024 * 1024), 1),
        "child_pids": sorted(child_pids),
    }


def _looks_like_marker_progress_line(line: str) -> bool:
    lowered = line.lower()
    return (
        "processing pdfs:" in lowered
        or "inferenced " in lowered
        or "converting " in lowered and " pdfs" in lowered
    )


def _format_progress_payload(payload: dict[str, object]) -> str:
    parts = [
        f"kind={payload['kind']}",
        f"elapsed={payload['elapsed_seconds']}s",
    ]
    since_last = payload.get("since_last_output_seconds")
    if since_last is not None:
        parts.append(f"since_last_output={since_last}s")
    if payload.get("input_files") is not None:
        parts.append(f"files={payload['input_files']}")
    if payload.get("pages_total") is not None:
        parts.append(f"pages_total={payload['pages_total']}")
    if payload.get("output_artifacts") is not None:
        parts.append(f"output_artifacts={payload['output_artifacts']}")
    if payload.get("process_count") is not None:
        parts.append(f"processes={payload['process_count']}")
    if payload.get("cpu_percent") is not None:
        parts.append(f"cpu={payload['cpu_percent']}%")
    if payload.get("rss_mb") is not None:
        parts.append(f"rss={payload['rss_mb']}MB")
    line = str(payload.get("last_marker_line") or "").strip()
    if line:
        parts.append(f"last={line[-160:]}")
    return "Marker progress: " + ", ".join(parts)


def _append_progress_jsonl(progress: ProgressContext | None, payload: dict[str, object]) -> None:
    if progress is None or progress.output_dir is None:
        return
    try:
        progress.output_dir.mkdir(parents=True, exist_ok=True)
        path = progress.output_dir / "marker_progress.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        status_path = progress.output_dir / "marker_status.json"
        temp_path = progress.output_dir / "marker_status.json.tmp"
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(status_path)
    except OSError:
        return
