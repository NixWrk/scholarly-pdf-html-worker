"""Marker subprocess execution helpers for P62 recovery."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pdf_html_polish.atomic_io import write_json_atomic
from pdf_html_polish.quality_loop.cached_run_state import path_is_link_like
from pdf_html_polish.quality_loop.converted_runs import visible_html_text
from pdf_html_polish.quality_loop.p62_matching import figure_label_present_in_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Any) -> None:
    write_json_atomic(path, data)


def _terminate_process_tree(process: subprocess.Popen[Any], *, cwd: Path) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        with suppress(Exception):
            process.wait(timeout=5)
        if process.poll() is None:
            with suppress(Exception):
                process.kill()
            with suppress(Exception):
                process.wait(timeout=5)
        return

    kill_process_group = getattr(os, "killpg", None)
    try:
        if callable(kill_process_group):
            kill_process_group(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)
    except Exception:
        if callable(kill_process_group):
            with suppress(Exception):
                kill_process_group(process.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        if process.poll() is None:
            with suppress(Exception):
                process.kill()
        with suppress(Exception):
            process.wait(timeout=5)


def execute_marker_command(
    record: dict[str, Any],
    *,
    timeout_seconds: int,
    cwd: Path,
) -> dict[str, Any]:
    raw_command = record.get("marker_command")
    if not raw_command:
        return {"status": "skipped", "reason": "marker_command_unavailable", "returncode": None}
    if (
        not isinstance(raw_command, list)
        or not raw_command
        or any(not isinstance(argument, str) or not argument for argument in raw_command)
    ):
        return {"status": "skipped", "reason": "marker_command_invalid", "returncode": None}
    command = list(raw_command)

    marker_output_value = str(record.get("marker_output_dir") or "").strip()
    if not marker_output_value:
        return {
            "status": "skipped",
            "reason": "marker_output_dir_unavailable",
            "returncode": None,
        }
    marker_output_dir = Path(marker_output_value).expanduser()
    if any(
        path_is_link_like(component)
        for component in (marker_output_dir, *marker_output_dir.parents)
    ):
        return {"status": "skipped", "reason": "marker_output_dir_link_like", "returncode": None}
    marker_output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    started = _now()
    started_monotonic = time.monotonic()
    stdout = ""
    try:
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        try:
            stdout, _ = process.communicate(timeout=timeout_seconds if timeout_seconds > 0 else None)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process, cwd=cwd)
            try:
                more_stdout, _ = process.communicate(timeout=5)
                stdout = (stdout or "") + (more_stdout or "")
            except Exception:
                pass
            report = {
                "status": "timeout",
                "command": command,
                "started_at": started,
                "finished_at": _now(),
                "elapsed_seconds": round(time.monotonic() - started_monotonic, 2),
                "returncode": None,
                "timeout_seconds": timeout_seconds,
                "stdout_tail": (stdout or "")[-4000:],
            }
            _write_json(marker_output_dir / "marker_execution_report.json", report)
            return report

        stdout = stdout or ""
        report = {
            "status": "completed" if process.returncode == 0 else "failed",
            "command": command,
            "started_at": started,
            "finished_at": _now(),
            "elapsed_seconds": round(time.monotonic() - started_monotonic, 2),
            "returncode": process.returncode,
            "timeout_seconds": timeout_seconds,
            "stdout_tail": stdout[-4000:],
        }
    except FileNotFoundError as exc:
        report = {
            "status": "failed",
            "command": command,
            "started_at": started,
            "finished_at": _now(),
            "elapsed_seconds": round(time.monotonic() - started_monotonic, 2),
            "returncode": None,
            "timeout_seconds": timeout_seconds,
            "error": str(exc),
        }

    _write_json(marker_output_dir / "marker_execution_report.json", report)
    return report


def _invalid_marker_output(reason: str) -> dict[str, Any]:
    return {
        "status": "invalid_output",
        "reason": reason,
        "html_count": 0,
        "image_count": 0,
        "label_present": False,
        "html_paths": [],
        "image_paths": [],
    }


def validate_marker_output(
    marker_output_dir: Path,
    figure_label: str,
    *,
    snapshot_html: Callable[[Path], Path] | None = None,
) -> dict[str, Any]:
    if path_is_link_like(marker_output_dir):
        return _invalid_marker_output(f"invalid_output_dir:{marker_output_dir}")
    if not marker_output_dir.exists():
        return {
            "status": "not_run",
            "html_count": 0,
            "image_count": 0,
            "label_present": False,
            "html_paths": [],
            "image_paths": [],
        }
    if not marker_output_dir.is_dir():
        return _invalid_marker_output(f"invalid_output_dir:{marker_output_dir}")

    html_paths: list[Path] = []
    image_paths: list[Path] = []
    root = marker_output_dir.resolve(strict=True)

    def raise_walk_error(error: OSError) -> None:
        raise error

    try:
        for current_root, directory_names, file_names in os.walk(
            root,
            topdown=True,
            onerror=raise_walk_error,
            followlinks=False,
        ):
            directory_names.sort()
            file_names.sort()
            current = Path(current_root)
            for name in (*directory_names, *file_names):
                entry = current / name
                if path_is_link_like(entry):
                    return _invalid_marker_output(f"link_like_entry:{entry}")
                try:
                    entry.resolve(strict=True).relative_to(root)
                except (OSError, ValueError):
                    return _invalid_marker_output(f"entry_outside_output_dir:{entry}")
            for name in file_names:
                path = current / name
                if not path.is_file():
                    return _invalid_marker_output(f"irregular_output_entry:{path}")
                if path.suffix.lower() == ".html":
                    html_paths.append(path)
                elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                    image_paths.append(path)
    except OSError as exc:
        return _invalid_marker_output(f"output_tree_unreadable:{exc}")

    label_present = False
    html_snapshot_paths: list[str] = []
    for html_path in html_paths:
        try:
            read_path = snapshot_html(html_path) if snapshot_html is not None else html_path
            if snapshot_html is not None:
                html_snapshot_paths.append(str(read_path))
            text = visible_html_text(read_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            return _invalid_marker_output(f"invalid_utf8_html:{html_path}")
        except OSError as exc:
            return _invalid_marker_output(f"html_unreadable:{html_path}:{exc}")
        if figure_label_present_in_text(text, figure_label):
            label_present = True
            break

    if label_present and image_paths:
        status = "recovered_image"
    elif label_present:
        status = "caption_only"
    elif image_paths:
        status = "image_without_label"
    else:
        status = "empty_or_unmatched"
    return {
        "status": status,
        "html_count": len(html_paths),
        "image_count": len(image_paths),
        "label_present": label_present,
        "html_paths": [str(path) for path in html_paths[:8]],
        "html_snapshot_paths": html_snapshot_paths[:8],
        "image_paths": [str(path) for path in image_paths[:8]],
    }
