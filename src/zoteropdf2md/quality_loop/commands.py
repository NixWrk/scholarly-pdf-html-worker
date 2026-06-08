"""Logged subprocess helpers for quality-loop stages."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from .gates import evaluate_quality_gate, load_gate_config
from .run_utils import DEFAULT_REPO_ROOT, load_json, now, write_json


def run_test_command(command: str, run_dir: Path, *, cwd: Path = DEFAULT_REPO_ROOT) -> dict[str, Any]:
    started = now()
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
            current = time.monotonic()
            if current >= next_report:
                print(f"Tests running: elapsed={int(current - started_monotonic)}s", flush=True)
                next_report = current + 15
            time.sleep(1)

    stdout_tail = stdout_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stdout_path.is_file() else ""
    stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stderr_path.is_file() else ""
    report = {
        "command": command,
        "started_at": started,
        "finished_at": now(),
        "returncode": returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    write_json(run_dir / "test_command_report.json", report)
    print(f"Tests finished: exit={returncode}", flush=True)
    if returncode != 0:
        raise SystemExit(f"Test command failed with exit code {returncode}: {command}")
    return report


def run_audit(
    run_dir: Path,
    roots: Iterable[Path] | None = None,
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_map_path: Path | None = None,
    jobs: int = 1,
    merge_previous_report_path: Path | None = None,
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> None:
    audit_roots = [root.resolve(strict=False) for root in roots] if roots else [run_dir / "audit_tree"]
    if not audit_roots:
        raise ValueError("No audit roots supplied.")
    missing_roots = [root for root in audit_roots if not root.exists()]
    if missing_roots:
        raise FileNotFoundError(f"Missing audit root(s): {', '.join(str(root) for root in missing_roots)}")

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    started = now()
    stdout_path = run_dir / "audit_stdout.log"
    stderr_path = run_dir / "audit_stderr.log"
    command = [
        sys.executable,
        str(repo_root / "scripts" / "audit_en_polish.py"),
        "--roots",
        *[str(root) for root in audit_roots],
        "--out",
        str(run_dir / "audit_full_checks.json"),
    ]
    if enable_pdf_diagnostics:
        command.append("--pdf-diagnostics")
    if pdf_map_path is not None:
        command.extend(["--pdf-map", str(pdf_map_path)])
    if int(jobs or 1) > 1:
        command.extend(["--jobs", str(int(jobs or 1))])
    if merge_previous_report_path is not None:
        command.extend(["--merge-previous-report", str(merge_previous_report_path)])

    print(f"Audit started: roots={len(audit_roots)} out={run_dir / 'audit_full_checks.json'}", flush=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
        )
        started_monotonic = time.monotonic()
        next_report = started_monotonic + 15
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            current = time.monotonic()
            if current >= next_report:
                print(f"Audit running: elapsed={int(current - started_monotonic)}s", flush=True)
                next_report = current + 15
            time.sleep(1)

    stdout_tail = stdout_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stdout_path.is_file() else ""
    stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stderr_path.is_file() else ""
    write_json(
        run_dir / "audit_command_report.json",
        {
            "command": command,
            "roots": [str(root) for root in audit_roots],
            "pdf_diagnostics_enabled": enable_pdf_diagnostics,
            "pdf_map_path": str(pdf_map_path) if pdf_map_path is not None else "",
            "jobs": int(jobs or 1),
            "merge_previous_report_path": (
                str(merge_previous_report_path) if merge_previous_report_path is not None else ""
            ),
            "targeted_merge_enabled": merge_previous_report_path is not None,
            "started_at": started,
            "finished_at": now(),
            "returncode": returncode,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        },
    )
    print(f"Audit finished: exit={returncode}", flush=True)
    if returncode != 0:
        raise SystemExit(f"Audit command failed with exit code {returncode}. See {run_dir / 'audit_command_report.json'}")


def run_quality_history(
    run_dir: Path,
    *,
    run_id: str | None,
    previous_entry: Path | None,
    no_append: bool,
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> None:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "record_en_polish_quality_history.py"),
        "--run-dir",
        str(run_dir),
    ]
    if run_id:
        command.extend(["--run-id", run_id])
    if previous_entry:
        command.extend(["--previous-entry", str(previous_entry)])
    if no_append:
        command.append("--no-append")
    subprocess.run(command, cwd=repo_root, check=True)


def write_gate_report(
    run_dir: Path,
    gate_config_path: Path,
    *,
    out_path: Path | None = None,
    pdf_problem_evidence_name: str = "pdf_problem_evidence_report.json",
) -> dict[str, Any]:
    comparison = load_json(run_dir / "quality_compare.json")
    gate_config = load_gate_config(gate_config_path)
    article_review_path = run_dir / "article_review_report.json"
    article_review_report = load_json(article_review_path) if article_review_path.is_file() else None
    audit_path = run_dir / "audit_full_checks.json"
    audit_report = load_json(audit_path) if audit_path.is_file() else None
    audit_command_path = run_dir / "audit_command_report.json"
    audit_command_report = load_json(audit_command_path) if audit_command_path.is_file() else None
    pdf_problem_evidence_path = run_dir / pdf_problem_evidence_name
    pdf_problem_evidence_report = (
        load_json(pdf_problem_evidence_path) if pdf_problem_evidence_path.is_file() else None
    )
    report = evaluate_quality_gate(
        comparison,
        gate_config,
        article_review_report=article_review_report,
        audit_report=audit_report,
        audit_command_report=audit_command_report,
        pdf_problem_evidence_report=pdf_problem_evidence_report,
    )
    write_json(out_path or (run_dir / "quality_gate_report.json"), report)
    return report
