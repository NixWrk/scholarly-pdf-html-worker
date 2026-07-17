from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence
from unicodedata import normalize

from .atomic_io import copy_file_atomic as _copy_file_atomic
from .atomic_io import write_json_atomic as _write_json_atomic
from .marker_runner import MarkerRunner
from .models import PipelineSummary
from .pipeline import run_pipeline
from .pipeline_options import PipelineOptions
from .html_stages import (
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    article_dir_from_html_stage,
    article_name_from_html_stage,
    require_current_raw_conversions,
)
from .language_detect import LanguageGateDecision, detect_language_from_html
from .stage_contract import publish_latest_polish_from_quality_run


QUALITY_LOOP_SCRIPT = "scripts/llm_quality_loop.py"
FINAL_HTML_DIR_NAME = "final_html"
FINAL_HTML_MANIFEST_NAME = "final_html_manifest.json"
PIPELINE_MANIFEST_NAME = "pipeline_manifest.json"


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
    publish_latest_to_converted: bool = True
    prune_extra_html: bool = True
    publish_report_path: str | None = None
    reuse_existing_conversion: bool = False


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
    converted_stage_publish_report: dict[str, Any] | None
    final_html: FinalHtmlCollection


def source_language_payload(html: str) -> dict[str, Any]:
    detection = detect_language_from_html(html)
    detected = (detection.detected_language or "unknown").lower()
    skip = detected == "ru" and detection.confidence >= 0.75
    gate = LanguageGateDecision(skip, "already_russian" if skip else f"translate_{detected}_to_ru")
    return {
        "detection": detection.to_dict(),
        "gate": gate.to_dict(),
        "source_language_code": detected,
    }


def write_pipeline_manifest(converted_root: Path) -> Path:
    root = converted_root.expanduser().resolve(strict=False)
    articles: list[dict[str, Any]] = []
    for polish_path in sorted(root.rglob(POLISH_STAGE_NAME), key=str):
        if not polish_path.is_file():
            continue
        payload = source_language_payload(polish_path.read_text(encoding="utf-8", errors="replace"))
        article_dir = article_dir_from_html_stage(polish_path)
        sidecar = {
            "schema_version": 1,
            "kind": "pdf_html_article",
            "article": article_dir.name,
            "en_html_path": str(polish_path.resolve(strict=False)),
            **payload,
        }
        sidecar_path = polish_path.parent / PIPELINE_MANIFEST_NAME
        _write_json_atomic(sidecar_path, sidecar)
        articles.append(
            {
                "article": article_dir.name,
                "en_html_path": str(polish_path.resolve(strict=False)),
                "manifest_path": str(sidecar_path.resolve(strict=False)),
                **payload,
            }
        )

    manifest_path = root / PIPELINE_MANIFEST_NAME
    _write_json_atomic(
        manifest_path,
        {
            "schema_version": 1,
            "kind": "pdf_html_pipeline",
            "converted_root": str(root),
            "articles": articles,
        },
    )
    return manifest_path


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


def _publish_final_html(
    *,
    quality_dir: Path,
    target_dir: Path,
    sources: Sequence[tuple[str, Path]],
    fallback_source: str | None = None,
) -> FinalHtmlCollection:
    target_dir = target_dir.resolve(strict=False)
    resolved_sources = [
        (article, source_path.resolve(strict=False))
        for article, source_path in sources
    ]
    overlapping = [
        source_path for _article, source_path in resolved_sources
        if source_path.is_relative_to(target_dir)
    ]
    if overlapping:
        raise ValueError(f"final_html_dir contains source HTML: {overlapping[0]}")
    seen_articles: dict[str, Path] = {}
    artifacts: list[FinalHtmlArtifact] = []
    for article, source_path in resolved_sources:
        article_key = normalize("NFC", article).casefold()
        previous = seen_articles.get(article_key)
        if previous is not None:
            raise RuntimeError(
                "Duplicate final HTML article name "
                f"{article!r}: {previous} and {source_path}."
            )
        seen_articles[article_key] = source_path
        artifacts.append(
            FinalHtmlArtifact(
                article=article,
                source_path=source_path.resolve(strict=False),
                final_path=(target_dir / f"{article}.html").resolve(strict=False),
            )
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        _copy_file_atomic(artifact.source_path, artifact.final_path)

    expected_paths = {artifact.final_path for artifact in artifacts}
    for stale_path in target_dir.glob("*.html"):
        if stale_path.resolve(strict=False) not in expected_paths:
            stale_path.unlink()

    manifest: dict[str, Any] = {
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
    if fallback_source is not None:
        manifest["fallback_source"] = fallback_source
    manifest_path = target_dir / FINAL_HTML_MANIFEST_NAME
    _write_json_atomic(manifest_path, manifest)
    return FinalHtmlCollection(
        final_html_dir=target_dir,
        manifest_path=manifest_path,
        artifacts=tuple(artifacts),
    )


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
    sources = [
        (source_path.parent.name, source_path)
        for source_path in sorted(audit_tree.rglob(POLISH_STAGE_NAME), key=str)
        if source_path.is_file()
    ]
    return _publish_final_html(
        quality_dir=quality_dir,
        target_dir=target_dir,
        sources=sources,
    )


def collect_converted_stage_final_html(
    converted_root: Path,
    quality_output_dir: Path,
    *,
    final_html_dir: Path | None = None,
) -> FinalHtmlCollection:
    converted_dir = converted_root.expanduser().resolve(strict=False)
    quality_dir = quality_output_dir.expanduser().resolve(strict=False)
    target_dir = (
        final_html_dir.expanduser().resolve(strict=False)
        if final_html_dir is not None
        else quality_dir / FINAL_HTML_DIR_NAME
    )
    sources = [
        (article_name_from_html_stage(source_path), source_path)
        for source_path in sorted(converted_dir.rglob(POLISH_STAGE_NAME), key=str)
        if source_path.is_file()
    ]
    return _publish_final_html(
        quality_dir=quality_dir,
        target_dir=target_dir,
        sources=sources,
        fallback_source="converted_stage",
    )


def empty_final_html_collection(
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
    return _publish_final_html(
        quality_dir=quality_dir,
        target_dir=target_dir,
        sources=(),
    )


def existing_conversion_summary(options: PipelineOptions) -> PipelineSummary:
    converted_root = Path(options.output_dir).expanduser().resolve(strict=False)
    raw_stages = sorted(
        (
            path for path in converted_root.rglob(RAW_STAGE_NAME)
            if path.is_file()
        ),
        key=str,
    )
    if not raw_stages:
        raise FileNotFoundError(
            "Repolish-only mode requires an existing 01.en.raw.html under "
            f"{converted_root}."
        )
    source_pdf_paths = [Path(path) for path in options.source_pdf_paths or []]
    validations = require_current_raw_conversions(
        raw_stages,
        source_pdf_paths=source_pdf_paths,
    )
    source_pdf_count = len(source_pdf_paths)
    article_count = len({article_dir_from_html_stage(path) for path in raw_stages})
    assert article_count == len(validations)
    return PipelineSummary(
        collection_key="direct_pdf",
        collection_name="existing PDF HTML conversions",
        attachments_total=max(source_pdf_count, article_count),
        pdfs_resolved=source_pdf_count,
        staged_total=0,
        converted_total=article_count,
        skipped_existing=0,
        failed_total=0,
        output_dir=converted_root,
        filename_map_path=converted_root / "_source_filename_map.csv",
        export_mode=options.export_mode,
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
    if options.reuse_existing_conversion:
        conversion_summary = existing_conversion_summary(options.conversion_options)
        log(
            "Reusing existing PDF HTML raw stages for repolish: "
            f"articles={conversion_summary.converted_total} output={conversion_summary.output_dir}"
        )
    else:
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
    if not options.reuse_existing_conversion and (
        conversion_summary.converted_total or conversion_summary.skipped_existing
    ):
        validated_summary = existing_conversion_summary(options.conversion_options)
        expected_current = conversion_summary.converted_total + conversion_summary.skipped_existing
        if validated_summary.converted_total != expected_current:
            raise RuntimeError(
                "Converted raw-stage count does not match the completed conversion summary "
                f"(validated={validated_summary.converted_total}, "
                f"expected_current={expected_current})."
            )

    converted_root = Path(options.conversion_options.output_dir).expanduser().resolve(strict=False)
    quality_output_dir = (
        Path(options.quality_output_dir).expanduser().resolve(strict=False)
        if options.quality_output_dir
        else default_quality_output_dir(converted_root)
    )
    if quality_output_dir == converted_root:
        raise ValueError("quality_output_dir must be different from the conversion output_dir.")

    if not conversion_summary.converted_total:
        final_html = empty_final_html_collection(
            quality_output_dir,
            final_html_dir=(
                Path(options.final_html_dir).expanduser().resolve(strict=False)
                if options.final_html_dir
                else None
            ),
        )
        return CleanPipelineSummary(
            conversion_summary=conversion_summary,
            quality_output_dir=quality_output_dir,
            run_id=options.run_id or default_run_id(quality_output_dir),
            observe_command=(),
            observe_exit_code=0,
            converted_stage_publish_report=None,
            final_html=final_html,
        )

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
        def active_observe_runner(
            command: Sequence[str],
            cwd: Path | None,
            log_func: Callable[[str], None] | None,
        ) -> int:
            return run_observe_command(
                command,
                cwd=cwd,
                log=log_func,
            )
    observe_exit_code = active_observe_runner(observe_command, repository_root(), log)
    if observe_exit_code != 0:
        raise RuntimeError(f"Quality observe failed with exit code {observe_exit_code}.")

    converted_stage_publish_report: dict[str, Any] | None = None
    if options.publish_latest_to_converted:
        converted_stage_publish_report = publish_latest_polish_from_quality_run(
            quality_output_dir,
            converted_roots=[converted_root],
            apply=True,
            prune_extra_html=options.prune_extra_html,
            out_report=(
                Path(options.publish_report_path).expanduser().resolve(strict=False)
                if options.publish_report_path
                else None
            ),
        )
        if converted_stage_publish_report.get("stage_contract_status") != "pass":
            raise RuntimeError(
                "Converted stage HTML contract failed after publishing latest polish "
                f"(failing={converted_stage_publish_report.get('stage_contract_failing_article_count')})."
            )

    final_html = collect_final_html(
        quality_output_dir,
        final_html_dir=(
            Path(options.final_html_dir).expanduser().resolve(strict=False)
            if options.final_html_dir
            else None
        ),
    )
    write_pipeline_manifest(converted_root)
    if not final_html.artifacts and conversion_summary.converted_total:
        log(
            "Quality observe produced no audited final HTML; "
            "using converted-stage polish fallback."
        )
        final_html = collect_converted_stage_final_html(
            converted_root,
            quality_output_dir,
            final_html_dir=(
                Path(options.final_html_dir).expanduser().resolve(strict=False)
                if options.final_html_dir
                else None
            ),
        )
        if not final_html.artifacts:
            raise RuntimeError(
                "Quality observe completed, but no final 02.en.polish.html files "
                f"were found under {quality_output_dir / 'audit_tree'} or {converted_root}."
            )

    return CleanPipelineSummary(
        conversion_summary=conversion_summary,
        quality_output_dir=quality_output_dir,
        run_id=run_id,
        observe_command=tuple(observe_command),
        observe_exit_code=observe_exit_code,
        converted_stage_publish_report=converted_stage_publish_report,
        final_html=final_html,
    )
