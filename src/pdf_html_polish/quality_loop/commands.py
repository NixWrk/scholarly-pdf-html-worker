"""Logged subprocess helpers for quality-loop stages."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from pdf_html_polish.html_stages import (
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    article_name_from_html_stage,
)
from .audit_command_provenance import (
    AUDIT_COMMAND_REPORT_NAME,
    AUDIT_COMMAND_REPORT_SCHEMA_VERSION,
    AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES,
    AUDIT_OUTPUT_NAME,
    AuditCommandProvenanceError,
    absent_audit_input,
    build_audit_code_manifest,
    build_audit_command,
    build_audit_command_report,
    build_merge_previous_input_record,
    build_pdf_map_input_record,
    canonical_existing_root,
    load_audit_json_object,
    validate_audit_command_report,
)
from .audit_pdf import load_pdf_map
from .audit_report import find_stage_pairs
from .cached_run_state import path_is_link_like
from .enrichment_snapshot import snapshot_enrichment_file
from .gate_provenance import (
    GATE_CONFIG_SNAPSHOT_NAME,
    PDF_PROBLEM_EVIDENCE_REPORT_NAME,
    build_provenanced_gate_report,
    prepare_gate_config_snapshot,
    validate_gate_report_provenance,
)
from .run_utils import DEFAULT_REPO_ROOT, now, write_json


def canonical_run_directory(path: Path, *, label: str) -> Path:
    candidate = Path(path).expanduser()
    lexical = candidate if candidate.is_absolute() else Path.cwd() / candidate
    if any(
        path_is_link_like(component)
        for component in (lexical, *lexical.parents)
    ):
        raise ValueError(f"{label} is link-like: {lexical}")
    canonical = lexical.resolve(strict=False)
    if str(lexical) != str(canonical):
        raise ValueError(f"{label} must be canonical: {lexical}")
    if canonical.exists() and not canonical.is_dir():
        raise ValueError(f"{label} is not a directory: {canonical}")
    canonical.mkdir(parents=True, exist_ok=True)
    if any(
        path_is_link_like(component)
        for component in (canonical, *canonical.parents)
    ):
        raise ValueError(f"{label} became link-like: {canonical}")
    if not canonical.is_dir():
        raise ValueError(f"{label} is not a directory: {canonical}")
    return canonical.resolve(strict=True)


def _remove_existing_run_owned_file(path: Path, *, label: str) -> None:
    if not (path.exists() or path_is_link_like(path)):
        return
    if path_is_link_like(path):
        raise ValueError(f"Existing {label} is link-like: {path}")
    if not path.is_file():
        raise ValueError(f"Existing {label} is not a regular file: {path}")
    path.unlink()


def run_test_command(command: str, run_dir: Path, *, cwd: Path = DEFAULT_REPO_ROOT) -> dict[str, Any]:
    run_dir = canonical_run_directory(run_dir, label="Test run directory")
    started = now()
    stdout_path = run_dir / "test_stdout.log"
    stderr_path = run_dir / "test_stderr.log"
    for log_path, label in (
        (stdout_path, "test stdout"),
        (stderr_path, "test stderr"),
    ):
        _remove_existing_run_owned_file(log_path, label=label)
    print(f"Tests started: {command}", flush=True)
    with stdout_path.open("x", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "x",
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


def _audit_article_ids(audit_roots: Iterable[Path]) -> set[str]:
    pairs = find_stage_pairs(
        audit_roots,
        raw_stage=RAW_STAGE_NAME,
        polish_stage=POLISH_STAGE_NAME,
    )
    article_ids = [article_name_from_html_stage(polish_path) for _raw_path, polish_path in pairs]
    if len(set(article_ids)) != len(article_ids):
        raise ValueError("Audit roots contain duplicate article identities.")
    return set(article_ids)


def _canonical_pdf_map_path(path: Path, *, label: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"Audit PDF map path must be absolute: {label}: {candidate}")
    if any(
        path_is_link_like(component)
        for component in (candidate, *candidate.parents)
    ):
        raise ValueError(f"Audit PDF map path is link-like: {label}: {candidate}")
    canonical = candidate.resolve(strict=False)
    if str(candidate) != str(canonical):
        raise ValueError(f"Audit PDF map path must be canonical: {label}: {candidate}")
    return canonical


def _canonical_pdf_diagnostics_cache_dir(path: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError(
            f"Audit diagnostics cache path must be absolute: {candidate}"
        )
    if any(
        path_is_link_like(component)
        for component in (candidate, *candidate.parents)
    ):
        raise ValueError(
            f"Audit diagnostics cache path is link-like: {candidate}"
        )
    canonical = candidate.resolve(strict=False)
    if str(candidate) != str(canonical):
        raise ValueError(
            f"Audit diagnostics cache path must be canonical: {candidate}"
        )
    return canonical


def _materialize_pdf_map_input(
    run_dir: Path,
    article_ids: set[str],
    pdf_map_source: Path,
) -> dict[str, Any]:
    source_snapshot = snapshot_enrichment_file(
        run_dir,
        "__audit__",
        "audit_pdf_map_source",
        pdf_map_source,
    )
    try:
        supplied_map = load_pdf_map(source_snapshot)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Audit PDF map is invalid: {pdf_map_source}") from exc

    materialized_map: dict[str, str] = {}
    pdf_sources: list[tuple[str, Path, Path]] = []
    for article in sorted(article_ids & set(supplied_map)):
        source_path = _canonical_pdf_map_path(
            supplied_map[article],
            label=article,
        )
        snapshot = snapshot_enrichment_file(
            run_dir,
            article,
            "audit_source_pdf",
            source_path,
        )
        materialized_map[article] = str(snapshot)
        pdf_sources.append((article, source_path, snapshot))

    temporary_map = run_dir / f".audit_pdf_map_materialized.{uuid4().hex}.json"
    try:
        write_json(temporary_map, materialized_map)
        materialized_snapshot = snapshot_enrichment_file(
            run_dir,
            "__audit__",
            "audit_pdf_map_materialized",
            temporary_map,
        )
    finally:
        temporary_map.unlink(missing_ok=True)
    return build_pdf_map_input_record(
        pdf_map_source,
        source_snapshot,
        materialized_snapshot,
        pdf_sources,
    )


def run_audit(
    run_dir: Path,
    roots: Iterable[Path] | None = None,
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_map_path: Path | None = None,
    pdf_diagnostics_cache_dir: Path | None = None,
    jobs: int = 1,
    merge_previous_report_path: Path | None = None,
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> None:
    run_dir = canonical_run_directory(run_dir, label="Audit run directory")
    repo_root = Path(repo_root).expanduser().resolve(strict=False)
    supplied_roots = list(roots) if roots is not None else [run_dir / "audit_tree"]
    if not supplied_roots:
        raise ValueError("No audit roots supplied.")
    audit_roots = [canonical_existing_root(root) for root in supplied_roots]
    if len({os.path.normcase(str(root)) for root in audit_roots}) != len(audit_roots):
        raise ValueError("Duplicate audit roots supplied.")
    if type(jobs) is not int or jobs < 1:
        raise ValueError("Audit jobs must be a positive integer.")
    target_article_ids = _audit_article_ids(audit_roots)

    merge_previous_input = absent_audit_input()
    if merge_previous_report_path is not None:
        if not target_article_ids:
            raise ValueError("Targeted audit requires at least one article.")
        previous_candidate = Path(merge_previous_report_path).expanduser()
        if not previous_candidate.is_absolute():
            raise ValueError("Targeted audit baseline path must be absolute.")
        previous_source = previous_candidate.resolve(strict=False)
        if str(previous_candidate) != str(previous_source):
            raise ValueError("Targeted audit baseline path must be canonical.")
        expected_previous = run_dir / AUDIT_OUTPUT_NAME
        if previous_source != expected_previous:
            raise ValueError(
                f"Targeted audit baseline must be the current run output: {expected_previous}"
            )
        previous_command_source = run_dir / AUDIT_COMMAND_REPORT_NAME
        try:
            baseline_report = load_audit_json_object(
                previous_source,
                label="audit_baseline_report",
            )
            baseline_command = load_audit_json_object(
                previous_command_source,
                label="audit_baseline_command",
            )
        except AuditCommandProvenanceError as exc:
            raise ValueError(f"Targeted audit baseline JSON is invalid: {exc}") from exc
        if baseline_command.get("targeted_merge_enabled") is not False:
            raise ValueError("Targeted audit baseline must be a full audit.")
        if baseline_command.get("pdf_diagnostics_enabled") is not enable_pdf_diagnostics:
            raise ValueError("Targeted audit baseline PDF diagnostics mode does not match.")
        try:
            validate_audit_command_report(
                run_dir,
                baseline_report,
                baseline_command,
                repo_root=repo_root,
                allowed_changed_article_ids=target_article_ids,
            )
        except AuditCommandProvenanceError as exc:
            raise ValueError(f"Targeted audit baseline provenance is invalid: {exc}") from exc
        previous_snapshot = snapshot_enrichment_file(
            run_dir,
            "__audit__",
            "audit_merge_baseline",
            previous_source,
        )
        previous_command_snapshot = snapshot_enrichment_file(
            run_dir,
            "__audit__",
            "audit_merge_baseline_command",
            previous_command_source,
        )
        merge_previous_input = build_merge_previous_input_record(
            previous_source,
            previous_snapshot,
            previous_command_source,
            previous_command_snapshot,
            allowed_changed_articles=target_article_ids,
        )

    pdf_map_input = absent_audit_input()
    if pdf_map_path is not None:
        if not enable_pdf_diagnostics:
            raise ValueError("Audit PDF map requires PDF diagnostics to be enabled.")
        pdf_map_source = _canonical_pdf_map_path(
            pdf_map_path,
            label="source map",
        )
        pdf_map_input = _materialize_pdf_map_input(
            run_dir,
            target_article_ids,
            pdf_map_source,
        )

    cache_dir = (
        _canonical_pdf_diagnostics_cache_dir(pdf_diagnostics_cache_dir)
        if pdf_diagnostics_cache_dir is not None
        else None
    )

    output_path = run_dir / AUDIT_OUTPUT_NAME
    command_report_path = run_dir / AUDIT_COMMAND_REPORT_NAME
    stdout_path = run_dir / "audit_stdout.log"
    stderr_path = run_dir / "audit_stderr.log"
    for stale_path, label in (
        (output_path, "audit output"),
        (command_report_path, "audit command report"),
        (stdout_path, "audit stdout"),
        (stderr_path, "audit stderr"),
    ):
        _remove_existing_run_owned_file(stale_path, label=label)

    env = os.environ.copy()
    environment_overrides = dict(
        AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES
    )
    env.update(environment_overrides)
    started = now()
    command = build_audit_command(
        repo_root=repo_root,
        roots=audit_roots,
        output_path=output_path,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_input=pdf_map_input,
        pdf_diagnostics_cache_dir=cache_dir,
        jobs=jobs,
        merge_previous_report_input=merge_previous_input,
    )
    code_manifest_before = build_audit_code_manifest(repo_root)

    print(f"Audit started: roots={len(audit_roots)} out={output_path}", flush=True)
    with stdout_path.open("x", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "x",
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
    finished = now()
    code_manifest_after = build_audit_code_manifest(repo_root)
    print(f"Audit finished: exit={returncode}", flush=True)
    if returncode != 0 or code_manifest_after != code_manifest_before:
        write_json(
            command_report_path,
            {
                "schema_version": AUDIT_COMMAND_REPORT_SCHEMA_VERSION,
                "kind": "quality_audit_command_failure",
                "command": command,
                "started_at": started,
                "finished_at": finished,
                "environment_overrides": environment_overrides,
                "returncode": returncode,
                "code_stable": code_manifest_after == code_manifest_before,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            },
        )
        if returncode != 0:
            raise SystemExit(
                f"Audit command failed with exit code {returncode}. See {command_report_path}"
            )
        raise RuntimeError(f"Audit code changed while the command was running. See {command_report_path}")

    report = build_audit_command_report(
        run_dir,
        repo_root=repo_root,
        roots=audit_roots,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_input=pdf_map_input,
        pdf_diagnostics_cache_dir=cache_dir,
        jobs=jobs,
        merge_previous_report_input=merge_previous_input,
        started_at=started,
        finished_at=finished,
        returncode=returncode,
        environment_overrides=environment_overrides,
        code_manifest=code_manifest_before,
    )
    write_json(command_report_path, report)


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
    environment = os.environ.copy()
    environment.update(AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES)
    subprocess.run(command, cwd=repo_root, env=environment, check=True)


def write_gate_report(
    run_dir: Path,
    gate_config_path: Path,
    *,
    out_path: Path | None = None,
    pdf_problem_evidence_name: str = PDF_PROBLEM_EVIDENCE_REPORT_NAME,
) -> dict[str, Any]:
    if pdf_problem_evidence_name != PDF_PROBLEM_EVIDENCE_REPORT_NAME:
        raise ValueError("Gate provenance requires the canonical PDF evidence report name.")
    snapshot = prepare_gate_config_snapshot(run_dir, gate_config_path)
    report = build_provenanced_gate_report(run_dir)
    write_json(out_path or (run_dir / "quality_gate_report.json"), report)
    validate_gate_report_provenance(run_dir, report)
    if snapshot.path != Path(run_dir).resolve(strict=False) / GATE_CONFIG_SNAPSHOT_NAME:
        raise RuntimeError("Gate config snapshot path changed unexpectedly.")
    return report
