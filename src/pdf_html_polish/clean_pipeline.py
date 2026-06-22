from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .marker_runner import MarkerRunner
from .models import PipelineSummary
from .pipeline import run_pipeline
from .pipeline_options import PipelineOptions


QUALITY_LOOP_SCRIPT = "scripts/llm_quality_loop.py"
FINAL_HTML_DIR_NAME = "final_html"
FINAL_HTML_MANIFEST_NAME = "final_html_manifest.json"


@dataclass(frozen=True)
class CleanPipelineOptions:
    conversion_options: PipelineOptions
    quality_output_dir: str | None = None
    run_id: str | None = None
    jobs: int | None = None
    repolish_jobs: int | None = None
    audit_jobs: int | None = None
    p62_marker_recovery_jobs: int | None = None
    p62_recovery_jobs: int | None = None
    polish_auto_repair_jobs: int | None = None
    previous_entry: str | None = None
    gate_config: str | None = None
    final_html_dir: str | None = None
    no_append_history: bool = True
    skip_quality_tests: bool = False
    fail_on_gate: bool = False


@dataclass(frozen=True)
class FinalHtmlArtifact:
    article: str
    source_path: Path
    final_path: Path


@dataclass(frozen=True)
class FinalHtmlCollection:
    final_html_dir: Path
    manifest_path: Path
    artifacts: tuple[FinalHtmlArtifact, ...]


@dataclass(frozen=True)
class CleanPipelineSummary:
    conversion_summary: PipelineSummary
    quality_output_dir: Path
    run_id: str
    observe_command: tuple[str, ...]
    observe_exit_code: int
    final_html: FinalHtmlCollection


def default_quality_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve(strict=False)
    return resolved.parent / f"{resolved.name}_quality"


def default_run_id(quality_output_dir: Path) -> str:
    return quality_output_dir.expanduser().resolve(strict=False).name


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def quality_loop_script_path() -> Path:
    return repository_root() / QUALITY_LOOP_SCRIPT


def build_observe_command(
    *,
    converted_root: Path,
    quality_output_dir: Path,
    run_id: str,
    jobs: int | None = None,
    repolish_jobs: int | None = None,
    audit_jobs: int | None = None,
    p62_marker_recovery_jobs: int | None = None,
    p62_recovery_jobs: int | None = None,
    polish_auto_repair_jobs: int | None = None,
    previous_entry: Path | None = None,
    gate_config: Path | None = None,
    no_append_history: bool = True,
    skip_quality_tests: bool = False,
    fail_on_gate: bool = False,
    script_path: Path | None = None,
) -> list[str]:
    script = script_path or quality_loop_script_path()
    command = [
        sys.executable,
        str(script),
        "observe",
        "--converted-roots",
        str(converted_root),
        "--out-dir",
        str(quality_output_dir),
        "--run-id",
        run_id,
    ]
    for flag, value in (
        ("--jobs", jobs),
        ("--repolish-jobs", repolish_jobs),
        ("--audit-jobs", audit_jobs),
        ("--p62-marker-recovery-jobs", p62_marker_recovery_jobs),
        ("--p62-recovery-jobs", p62_recovery_jobs),
        ("--polish-auto-repair-jobs", polish_auto_repair_jobs),
    ):
        if value is not None:
            command.extend([flag, str(int(value))])
    if previous_entry is not None:
        command.extend(["--previous-entry", str(previous_entry)])
    if gate_config is not None:
        command.extend(["--gate-config", str(gate_config)])
    if no_append_history:
        command.append("--no-append-history")
    if skip_quality_tests:
        command.append("--skip-tests")
    if fail_on_gate:
        command.append("--fail-on-gate")
    return command


def run_observe_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    log: Callable[[str], None] | None = None,
) -> int:
    if log is not None:
        log("$ " + " ".join(str(part) for part in command))
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd or repository_root()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        if log is not None:
            log(line.rstrip("\r\n"))
    return int(process.wait())


def collect_final_html(
    quality_output_dir: Path,
    *,
    final_html_dir: Path | None = None,
) -> FinalHtmlCollection:
    quality_dir = quality_output_dir.expanduser().resolve(strict=False)
    target_dir = (
        final_html_dir.expanduser().resolve(strict=False)
        if final_html_dir is not None
        else quality_dir / FINAL_HTML_DIR_NAME
    )
    audit_tree = quality_dir / "audit_tree"
    target_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[FinalHtmlArtifact] = []
    for source_path in sorted(audit_tree.rglob("02.en.polish.html"), key=str):
        if not source_path.is_file():
            continue
        article = source_path.parent.name
        final_path = target_dir / f"{article}.html"
        shutil.copy2(source_path, final_path)
        artifacts.append(
            FinalHtmlArtifact(
                article=article,
                source_path=source_path.resolve(strict=False),
                final_path=final_path.resolve(strict=False),
            )
        )

    manifest_path = target_dir / FINAL_HTML_MANIFEST_NAME
    manifest = {
        "schema_version": 1,
        "quality_output_dir": str(quality_dir),
        "final_html_dir": str(target_dir),
        "article_count": len(artifacts),
        "html_files": [
            {
                "article": artifact.article,
                "source_path": str(artifact.source_path),
                "final_path": str(artifact.final_path),
            }
            for artifact in artifacts
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return FinalHtmlCollection(
        final_html_dir=target_dir,
        manifest_path=manifest_path,
        artifacts=tuple(artifacts),
    )


def run_clean_pipeline(
    options: CleanPipelineOptions,
    runner: MarkerRunner,
    log: Callable[[str], None],
    is_cancelled: Callable[[], bool],
    *,
    pipeline_runner: Callable[
        [PipelineOptions, MarkerRunner, Callable[[str], None], Callable[[], bool]],
        PipelineSummary,
    ] = run_pipeline,
    observe_runner: Callable[[Sequence[str], Path | None, Callable[[str], None] | None], int]
    | None = None,
) -> CleanPipelineSummary:
    conversion_summary = pipeline_runner(
        options.conversion_options,
        runner,
        log,
        is_cancelled,
    )
    if conversion_summary.failed_total:
        raise RuntimeError(
            "PDF conversion failed; quality observe was skipped "
            f"(failed={conversion_summary.failed_total})."
        )

    converted_root = Path(options.conversion_options.output_dir).expanduser().resolve(strict=False)
    quality_output_dir = (
        Path(options.quality_output_dir).expanduser().resolve(strict=False)
        if options.quality_output_dir
        else default_quality_output_dir(converted_root)
    )
    if quality_output_dir == converted_root:
        raise ValueError("quality_output_dir must be different from the conversion output_dir.")

    run_id = options.run_id or default_run_id(quality_output_dir)
    observe_command = build_observe_command(
        converted_root=converted_root,
        quality_output_dir=quality_output_dir,
        run_id=run_id,
        jobs=options.jobs,
        repolish_jobs=options.repolish_jobs,
        audit_jobs=options.audit_jobs,
        p62_marker_recovery_jobs=options.p62_marker_recovery_jobs,
        p62_recovery_jobs=options.p62_recovery_jobs,
        polish_auto_repair_jobs=options.polish_auto_repair_jobs,
        previous_entry=(
            Path(options.previous_entry).expanduser().resolve(strict=False)
            if options.previous_entry
            else None
        ),
        gate_config=(
            Path(options.gate_config).expanduser().resolve(strict=False)
            if options.gate_config
            else None
        ),
        no_append_history=options.no_append_history,
        skip_quality_tests=options.skip_quality_tests,
        fail_on_gate=options.fail_on_gate,
    )

    active_observe_runner = observe_runner
    if active_observe_runner is None:
        active_observe_runner = (
            lambda command, cwd, log_func: run_observe_command(
                command,
                cwd=cwd,
                log=log_func,
            )
        )
    observe_exit_code = active_observe_runner(observe_command, repository_root(), log)
    if observe_exit_code != 0:
        raise RuntimeError(f"Quality observe failed with exit code {observe_exit_code}.")

    final_html = collect_final_html(
        quality_output_dir,
        final_html_dir=(
            Path(options.final_html_dir).expanduser().resolve(strict=False)
            if options.final_html_dir
            else None
        ),
    )
    if not final_html.artifacts and conversion_summary.converted_total:
        raise RuntimeError(
            "Quality observe completed, but no final 02.en.polish.html files "
            f"were found under {quality_output_dir / 'audit_tree'}."
        )

    return CleanPipelineSummary(
        conversion_summary=conversion_summary,
        quality_output_dir=quality_output_dir,
        run_id=run_id,
        observe_command=tuple(observe_command),
        observe_exit_code=observe_exit_code,
        final_html=final_html,
    )
