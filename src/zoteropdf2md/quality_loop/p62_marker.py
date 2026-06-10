"""Marker subprocess execution helpers for P62 recovery."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zoteropdf2md.quality_loop.converted_runs import visible_html_text
from zoteropdf2md.quality_loop.p62_matching import figure_label_present_in_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            process.kill()


def execute_marker_command(
    record: dict[str, Any],
    *,
    timeout_seconds: int,
    cwd: Path,
) -> dict[str, Any]:
    command = list(record.get("marker_command") or [])
    if not command:
        return {"status": "skipped", "reason": "marker_command_unavailable", "returncode": None}

    marker_output_dir = Path(str(record.get("marker_output_dir") or ""))
    if marker_output_dir:
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
            if marker_output_dir:
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

    if marker_output_dir:
        _write_json(marker_output_dir / "marker_execution_report.json", report)
    return report


def validate_marker_output(marker_output_dir: Path, figure_label: str) -> dict[str, Any]:
    if not marker_output_dir.exists():
        return {
            "status": "not_run",
            "html_count": 0,
            "image_count": 0,
            "label_present": False,
            "html_paths": [],
            "image_paths": [],
        }

    html_paths = sorted(path for path in marker_output_dir.rglob("*.html") if path.is_file())
    image_paths = sorted(
        path
        for path in marker_output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    label_present = False
    for html_path in html_paths:
        try:
            text = visible_html_text(html_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
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
        "image_paths": [str(path) for path in image_paths[:8]],
    }
