"""Logged subprocess helpers for quality-loop stages."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_test_command(command: str, run_dir: Path, *, cwd: Path) -> dict[str, Any]:
    started = _now()
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "test_stdout.log"
    stderr_path = run_dir / "test_stderr.log"
    print(f"Tests started: {command}", flush=True)
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
        )
        started_monotonic = time.monotonic()
        next_report = started_monotonic + 15
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            now = time.monotonic()
            if now >= next_report:
                print(f"Tests running: elapsed={int(now - started_monotonic)}s", flush=True)
                next_report = now + 15
            time.sleep(1)

    stdout_tail = stdout_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stdout_path.is_file() else ""
    stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stderr_path.is_file() else ""
    report = {
        "command": command,
        "started_at": started,
        "finished_at": _now(),
        "returncode": returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    _write_json(run_dir / "test_command_report.json", report)
    print(f"Tests finished: exit={returncode}", flush=True)
    if returncode != 0:
        raise SystemExit(f"Test command failed with exit code {returncode}: {command}")
    return report
