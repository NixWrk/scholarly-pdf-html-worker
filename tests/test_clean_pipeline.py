from __future__ import annotations

import json
import subprocess
import sys
import time
import shutil
import tomllib
from pathlib import Path

import pytest

from conftest import write_attested_audit_command

import pdf_html_polish.atomic_io as atomic_io_module
import pdf_html_polish.clean_pipeline as clean_pipeline_module
import pdf_html_polish.cli.clean_convert as clean_convert_module
import pdf_html_polish.pipeline as pipeline_module
from pdf_html_polish.artifact_integrity import fingerprint_file
from pdf_html_polish.cli.clean_convert import build_parser
from pdf_html_polish.clean_pipeline import (
    CleanPipelineOptions,
    build_observe_command,
    collect_final_html,
    default_quality_output_dir,
    run_clean_pipeline,
)
from pdf_html_polish.marker_runner import MarkerRunner, RunResult
from pdf_html_polish.models import PipelineSummary
from pdf_html_polish.html_stages import (
    HTML_STAGE_DIR_NAME,
    POLISH_STAGE_NAME,
    RAW_CONVERSION_MANIFEST_NAME,
    RAW_STAGE_NAME,
    write_raw_conversion_manifest,
)
from pdf_html_polish.quality_loop.cached_run_state import (
    CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
    cached_repolish_artifact_fingerprints,
)
from pdf_html_polish.quality_loop.enrichment_snapshot import (
    initialize_enrichment_snapshot,
)
from pdf_html_polish.quality_loop.commands import run_quality_history, write_gate_report
from pdf_html_polish.pipeline import run_pipeline, run_raw_html_pipeline
from pdf_html_polish.pipeline_options import PipelineOptions
from pdf_html_polish.quality_loop.publication_state import seal_quality_publication
from pdf_html_polish.result_state import (
    RESULT_MANIFEST_NAME,
    completed_result_is_current,
)


def _summary(
    output_dir: Path,
    *,
    failed_total: int = 0,
    converted_total: int | None = None,
    skipped_existing: int = 0,
) -> PipelineSummary:
    return PipelineSummary(
        collection_key="direct_pdf",
        collection_name="direct PDF files",
        attachments_total=1,
        pdfs_resolved=1,
        staged_total=1,
        converted_total=converted_total if converted_total is not None else (0 if failed_total else 1),
        skipped_existing=skipped_existing,
        failed_total=failed_total,
        output_dir=output_dir,
        filename_map_path=output_dir / "_source_filename_map.csv",
        export_mode="html",
    )


def _write_current_stage_pair(
    stage_dir: Path,
    source_pdf: Path,
    *,
    raw_html: str = "<html><body>raw</body></html>",
    polish_html: str = "<html><body>stale</body></html>",
) -> None:
    source_pdf.parent.mkdir(parents=True, exist_ok=True)
    if not source_pdf.exists():
        source_pdf.write_bytes(b"%PDF-1.4\n")
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_path = stage_dir / RAW_STAGE_NAME
    raw_path.write_text(raw_html, encoding="utf-8")
    (stage_dir / POLISH_STAGE_NAME).write_text(polish_html, encoding="utf-8")
    write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_valid_gate_report(quality_dir: Path) -> None:
    write_attested_audit_command(quality_dir)
    config_path = quality_dir.parent / f".{quality_dir.name}.gate_config.json"
    run_quality_history(
        quality_dir,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    _write_json(config_path, {"allow_missing_previous": True, "max_regressions": 0, "max_total_deltas": {}})
    write_gate_report(quality_dir, config_path)


def _seal_quality_output(
    quality_dir: Path,
    stage_dir: Path,
    article_id: str,
    *,
    audited_html: str = "<html><body>clean</body></html>",
) -> Path:
    production_raw = stage_dir / RAW_STAGE_NAME
    target_polish = stage_dir / POLISH_STAGE_NAME
    source_run = quality_dir / "_converted_raw_source"
    source_cached_raw = source_run / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
    source_cached_raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(production_raw, source_cached_raw)
    profile_path = source_run / "profiles" / f"{article_id}.citation_profile.json"
    _write_json(profile_path, {"status": "ok", "style": "unknown", "confidence": "low"})
    _write_json(
        source_run / "manifest.json",
        {
            "source_snapshot_schema_version": CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
            "source_kind": "converted_raw_cache",
            "out_dir": str(source_run),
            "raw_count": 1,
            "article_count": 1,
            "raw_cache_dir": str(source_run / "raw_cache"),
            "profile_dir": str(source_run / "profiles"),
            "profile_status_counts": {"ok": 1},
            "profile_style_counts": {"unknown:low": 1},
            "articles": [
                {
                    "index": 1,
                    "article_id": article_id,
                    "article": article_id,
                    "raw_stage_path": str(production_raw),
                    "raw_cache_path": str(source_cached_raw),
                    "profile_path": str(profile_path),
                    "source_polish_path": str(target_polish),
                    "profile_status": "ok",
                    "citation_style": "unknown",
                    "citation_confidence": "low",
                    **cached_repolish_artifact_fingerprints(source_cached_raw, profile_path),
                }
            ],
        },
    )
    source_manifest_fingerprint = fingerprint_file(source_run / "manifest.json", reject_symlink=True)
    assert source_manifest_fingerprint is not None
    enrichment_snapshot = initialize_enrichment_snapshot(quality_dir)

    quality_cached_raw = quality_dir / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
    quality_cached_raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(production_raw, quality_cached_raw)
    audited = quality_dir / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True, exist_ok=True)
    audit_raw = audited.parent / RAW_STAGE_NAME
    shutil.copyfile(production_raw, audit_raw)
    audited.write_text(audited_html, encoding="utf-8")
    _write_json(
        quality_dir / "manifest.json",
        {
            "source_kind": "cached_raw_repolish",
            "source_run_dir": str(source_run),
            "source_manifest_bytes": source_manifest_fingerprint.size,
            "source_manifest_sha256": source_manifest_fingerprint.sha256,
            "enrichment_snapshot_dir": str(enrichment_snapshot),
            "articles": [
                {"article": article_id, "raw_cache_path": str(quality_cached_raw)}
            ],
        },
    )
    raw_fingerprint = fingerprint_file(audit_raw, reject_symlink=True)
    polish_fingerprint = fingerprint_file(audited, reject_symlink=True)
    assert raw_fingerprint is not None
    assert polish_fingerprint is not None
    _write_json(
        quality_dir / "audit_full_checks.json",
        {
            "audit_status": "complete",
            "articles": [
                {
                    "article": article_id,
                    "raw_stage_path": str(audit_raw),
                    "polish_stage_path": str(audited),
                    "raw_stage_bytes": raw_fingerprint.size,
                    "raw_stage_sha256": raw_fingerprint.sha256,
                    "polish_stage_bytes": polish_fingerprint.size,
                    "polish_stage_sha256": polish_fingerprint.sha256,
                }
            ],
        },
    )
    _write_valid_gate_report(quality_dir)
    assert seal_quality_publication(quality_dir)["status"] == "completed"
    return audited



def _seal_skipped_quality_output(
    quality_dir: Path,
    stage_dir: Path,
    article_id: str,
) -> None:
    audited = _seal_quality_output(quality_dir, stage_dir, article_id)
    quality_manifest_path = quality_dir / "manifest.json"
    quality_manifest = json.loads(quality_manifest_path.read_text(encoding="utf-8"))
    skipped = quality_manifest["articles"].pop()
    skipped.update(
        {
            "language_skipped": True,
            "skip_reason": "detected_non_target_language",
        }
    )
    quality_manifest["skipped_articles"] = [skipped]
    _write_json(quality_manifest_path, quality_manifest)
    audit_report_path = quality_dir / "audit_full_checks.json"
    audit_report = json.loads(audit_report_path.read_text(encoding="utf-8"))
    audit_report["articles"] = []
    _write_json(audit_report_path, audit_report)
    (audited.parent / RAW_STAGE_NAME).unlink()
    audited.unlink()
    _write_valid_gate_report(quality_dir)
    assert seal_quality_publication(quality_dir)["status"] == "completed"


def _append_skipped_quality_output(
    quality_dir: Path,
    stage_dir: Path,
    article_id: str,
) -> None:
    production_raw = stage_dir / RAW_STAGE_NAME
    target_polish = stage_dir / POLISH_STAGE_NAME
    source_run = quality_dir / "_converted_raw_source"
    source_manifest_path = source_run / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    index = len(source_manifest["articles"]) + 1
    source_cached_raw = source_run / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
    shutil.copyfile(production_raw, source_cached_raw)
    profile_path = source_run / "profiles" / f"{article_id}.citation_profile.json"
    _write_json(profile_path, {"status": "ok", "style": "unknown", "confidence": "low"})
    source_manifest["articles"].append(
        {
            "index": index,
            "article_id": article_id,
            "article": article_id,
            "raw_stage_path": str(production_raw),
            "raw_cache_path": str(source_cached_raw),
            "profile_path": str(profile_path),
            "source_polish_path": str(target_polish),
            "profile_status": "ok",
            "citation_style": "unknown",
            "citation_confidence": "low",
            **cached_repolish_artifact_fingerprints(source_cached_raw, profile_path),
        }
    )
    source_manifest["raw_count"] = index
    source_manifest["article_count"] = index
    source_manifest["profile_status_counts"] = {"ok": index}
    source_manifest["profile_style_counts"] = {"unknown:low": index}
    _write_json(source_manifest_path, source_manifest)
    source_fingerprint = fingerprint_file(source_manifest_path, reject_symlink=True)
    assert source_fingerprint is not None

    quality_cached_raw = quality_dir / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
    shutil.copyfile(production_raw, quality_cached_raw)
    quality_manifest_path = quality_dir / "manifest.json"
    quality_manifest = json.loads(quality_manifest_path.read_text(encoding="utf-8"))
    quality_manifest["source_manifest_bytes"] = source_fingerprint.size
    quality_manifest["source_manifest_sha256"] = source_fingerprint.sha256
    quality_manifest.setdefault("skipped_articles", []).append(
        {
            "article": article_id,
            "raw_cache_path": str(quality_cached_raw),
            "language_skipped": True,
            "skip_reason": "detected_non_target_language",
        }
    )
    _write_json(quality_manifest_path, quality_manifest)
    assert seal_quality_publication(quality_dir)["status"] == "completed"


def test_default_quality_output_dir_sits_next_to_conversion_output(tmp_path: Path) -> None:
    assert default_quality_output_dir(tmp_path / "paper_run") == tmp_path / "paper_run_quality"


def test_public_console_scripts_only_expose_clean_pipeline() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["pdf-html-polish"] == "pdf_html_polish.cli.clean_convert:main"
    assert scripts["pdf-html-polish-clean"] == "pdf_html_polish.cli.clean_convert:main"
    assert scripts["pdf-html-polish-stage-contract"] == "pdf_html_polish.cli.stage_contract:main"
    assert "pdf-html-convert" not in scripts


def test_legacy_raw_repolish_writer_is_removed() -> None:
    legacy_writer = Path("scripts/repolish_en_from_raw.py")

    assert not legacy_writer.exists()


def test_clean_public_parser_does_not_offer_partial_export_mode() -> None:
    parser = build_parser()

    assert "--export-mode" not in parser.format_help()


def test_clean_public_parser_requires_zotero_overlay_by_default() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pdf", "paper.pdf", "--output-dir", "out"])
    relaxed = parser.parse_args(
        [
            "--pdf",
            "paper.pdf",
            "--output-dir",
            "out",
            "--allow-missing-zotero-overlay",
        ]
    )

    assert args.require_zotero_overlay is True
    assert relaxed.require_zotero_overlay is False


def test_clean_public_parser_accepts_raw_only_chunk_mode() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pdf", "paper.pdf", "--output-dir", "out", "--raw-only"])

    assert args.raw_only is True


def test_clean_public_parser_accepts_repolish_existing_mode() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pdf", "paper.pdf", "--output-dir", "out", "--repolish-existing"])

    assert args.repolish_existing is True


def test_clean_public_parser_accepts_quality_gate_diagnostic_mode() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["--pdf", "paper.pdf", "--output-dir", "out", "--diagnostic-allow-gate-failure"]
    )

    assert args.fail_on_gate is False


def test_run_raw_html_pipeline_saves_raw_stage_only(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "converted"
    logs: list[str] = []

    class FakeRunner:
        def run_batch(self, *, input_dir, output_dir, **_kwargs):
            for pdf_path in Path(input_dir).glob("*.pdf"):
                article_dir = Path(output_dir) / pdf_path.stem
                article_dir.mkdir(parents=True)
                (article_dir / f"{pdf_path.stem}.html").write_text(
                    "<html><body>raw marker</body></html>",
                    encoding="utf-8",
                )
            return RunResult(command=["marker"], exit_code=0)

        def run_single(self, **_kwargs):  # pragma: no cover - should not be needed
            raise AssertionError("raw-only batch should have produced the artifact")

    summary = run_raw_html_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode="html",
        ),
        FakeRunner(),  # type: ignore[arg-type]
        logs.append,
        lambda: False,
    )

    stage_dir = output_dir / "paper" / HTML_STAGE_DIR_NAME
    assert summary.converted_total == 1
    assert (stage_dir / "01.en.raw.html").read_text(encoding="utf-8") == (
        "<html><body>raw marker</body></html>"
    )
    manifest = json.loads(
        (stage_dir / RAW_CONVERSION_MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "completed"
    assert manifest["source_pdf_name"] == "paper.pdf"
    assert manifest["raw_html_name"] == "01.en.raw.html"
    assert len(manifest["source_pdf_sha256"]) == 64
    assert len(manifest["raw_html_sha256"]) == 64
    assert not (stage_dir / "02.en.polish.html").exists()
    result_path = output_dir / "paper" / "paper.html"
    assert (result_path.parent / RESULT_MANIFEST_NAME).is_file()
    assert completed_result_is_current(source_pdf, result_path)
    assert summary.result_commit_failed_total == 0
    assert any("Raw HTML stage saved" in entry for entry in logs)


def test_run_raw_html_pipeline_rejects_partial_failed_marker_output(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "converted"

    class FakeRunner:
        def run_batch(self, *, input_dir, output_dir, **_kwargs):
            for pdf_path in Path(input_dir).glob("*.pdf"):
                article_dir = Path(output_dir) / pdf_path.stem
                article_dir.mkdir(parents=True)
                (article_dir / f"{pdf_path.stem}.html").write_text(
                    "<html><body>partial</body></html>",
                    encoding="utf-8",
                )
            return RunResult(command=["marker"], exit_code=137)

        def run_single(self, **_kwargs):
            return RunResult(command=["marker_single"], exit_code=137)

    summary = run_raw_html_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode="html",
        ),
        FakeRunner(),  # type: ignore[arg-type]
        lambda _message: None,
        lambda: False,
    )

    stage_dir = output_dir / "paper" / HTML_STAGE_DIR_NAME
    assert summary.converted_total == 0
    assert summary.failed_total == 1
    assert not (stage_dir / "01.en.raw.html").exists()
    assert not (stage_dir / RAW_CONVERSION_MANIFEST_NAME).exists()
    result_path = output_dir / "paper" / "paper.html"
    assert not (result_path.parent / RESULT_MANIFEST_NAME).exists()

    batch_skip_values: list[bool] = []

    class RecoveryRunner:
        def run_batch(self, *, input_dir, output_dir, skip_existing, **_kwargs):
            batch_skip_values.append(bool(skip_existing))
            for pdf_path in Path(input_dir).glob("*.pdf"):
                article_dir = Path(output_dir) / pdf_path.stem
                article_dir.mkdir(parents=True, exist_ok=True)
                (article_dir / f"{pdf_path.stem}.html").write_text(
                    "<html><body>complete retry</body></html>",
                    encoding="utf-8",
                )
            return RunResult(command=["marker"], exit_code=0)

        def run_single(self, **_kwargs):  # pragma: no cover - batch must succeed
            raise AssertionError("recovery batch should have produced the artifact")

    recovered = run_raw_html_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode="html",
        ),
        RecoveryRunner(),  # type: ignore[arg-type]
        lambda _message: None,
        lambda: False,
    )

    assert batch_skip_values == [False]
    assert recovered.skipped_existing == 0
    assert recovered.converted_total == 1
    assert recovered.failed_total == 0
    assert completed_result_is_current(source_pdf, result_path)


def test_raw_only_resource_failure_requests_smaller_scope_without_same_pdf_retry(
    tmp_path: Path,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "converted"
    logs: list[str] = []

    class ResourceFailureRunner:
        def run_batch(self, **_kwargs):
            return RunResult(
                command=["marker"],
                exit_code=1,
                failure_reason="memory_exhausted",
            )

        def run_single(self, **_kwargs):
            raise AssertionError(
                "resource failure must return to the caller for a smaller PDF scope"
            )

    summary = run_raw_html_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode="html",
        ),
        ResourceFailureRunner(),  # type: ignore[arg-type]
        logs.append,
        lambda: False,
    )

    assert summary.converted_total == 0
    assert summary.failed_total == 1
    assert any(
        "marker_scope_reduction_required=memory_exhausted" in entry
        for entry in logs
    )


def test_full_pipeline_resource_failure_requests_smaller_scope_without_same_pdf_retry(
    tmp_path: Path,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "converted"
    logs: list[str] = []

    class ResourceFailureRunner:
        def run_batch(self, **_kwargs):
            return RunResult(
                command=["marker"],
                exit_code=1,
                failure_reason="stall_timeout",
            )

        def run_single(self, **_kwargs):
            raise AssertionError(
                "resource failure must return to the caller for a smaller PDF scope"
            )

    summary = run_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            skip_existing=False,
        ),
        ResourceFailureRunner(),  # type: ignore[arg-type]
        logs.append,
        lambda: False,
    )

    assert summary.converted_total == 0
    assert summary.failed_total == 1
    assert any(
        "marker_scope_reduction_required=stall_timeout" in entry
        for entry in logs
    )


@pytest.mark.parametrize(
    ("result", "staged_total", "pending_total", "expected"),
    [
        (
            RunResult(["marker"], 1, "memory_exhausted"),
            1,
            1,
            "memory_exhausted",
        ),
        (RunResult(["marker"], 137), 1, 1, "process_exit_137"),
        (RunResult(["marker"], 1), 1, 1, None),
        (RunResult(["marker"], 1, "memory_exhausted"), 2, 2, None),
        (RunResult(["marker"], 1, "memory_exhausted"), 2, 1, None),
        (RunResult(["marker"], 1, "memory_exhausted"), 1, 0, None),
    ],
)
def test_marker_scope_reduction_policy(
    result: RunResult,
    staged_total: int,
    pending_total: int,
    expected: str | None,
) -> None:
    assert pipeline_module._marker_scope_reduction_reason(
        result,
        staged_total=staged_total,
        pending_total=pending_total,
    ) == expected


def test_raw_force_retry_invalidates_previous_completion_before_marker(
    tmp_path: Path,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "converted"

    class SuccessRunner:
        def run_batch(self, *, input_dir, output_dir, **_kwargs):
            for pdf_path in Path(input_dir).glob("*.pdf"):
                article_dir = Path(output_dir) / pdf_path.stem
                article_dir.mkdir(parents=True, exist_ok=True)
                (article_dir / f"{pdf_path.stem}.html").write_text(
                    "<html><body>first complete result</body></html>",
                    encoding="utf-8",
                )
            return RunResult(command=["marker"], exit_code=0)

        def run_single(self, **_kwargs):  # pragma: no cover - batch must succeed
            raise AssertionError("successful batch should not need fallback")

    first = run_raw_html_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode="html",
        ),
        SuccessRunner(),  # type: ignore[arg-type]
        lambda _message: None,
        lambda: False,
    )
    result_path = output_dir / "paper" / "paper.html"
    manifest_path = result_path.parent / RESULT_MANIFEST_NAME
    raw_manifest_path = (
        result_path.parent / HTML_STAGE_DIR_NAME / RAW_CONVERSION_MANIFEST_NAME
    )
    assert first.failed_total == 0
    assert completed_result_is_current(source_pdf, result_path)
    assert raw_manifest_path.is_file()

    class FailedForceRunner:
        def run_batch(self, *, input_dir, output_dir, **_kwargs):
            for pdf_path in Path(input_dir).glob("*.pdf"):
                article_dir = Path(output_dir) / pdf_path.stem
                (article_dir / f"{pdf_path.stem}.html").write_text(
                    "<html><body>partial forced retry</body></html>",
                    encoding="utf-8",
                )
            return RunResult(command=["marker"], exit_code=137)

        def run_single(self, **_kwargs):
            return RunResult(command=["marker-single"], exit_code=137)

    failed_retry = run_raw_html_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode="html",
            skip_existing=False,
        ),
        FailedForceRunner(),  # type: ignore[arg-type]
        lambda _message: None,
        lambda: False,
    )

    assert failed_retry.converted_total == 0
    assert failed_retry.failed_total == 1
    assert not manifest_path.exists()
    assert not raw_manifest_path.exists()
    assert not completed_result_is_current(source_pdf, result_path)


def test_raw_only_cli_returns_nonzero_when_any_document_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")

    class FakeRunner:
        def cleanup_spawned_processes(self, _log) -> None:
            return None

    monkeypatch.setattr(clean_convert_module, "MarkerRunner", lambda **_kwargs: FakeRunner())
    monkeypatch.setattr(
        clean_convert_module,
        "run_raw_html_pipeline",
        lambda *_args, **_kwargs: _summary(tmp_path / "converted", failed_total=1),
    )

    exit_code = clean_convert_module.main(
        ["--pdf", str(source_pdf), "--output-dir", str(tmp_path / "converted"), "--raw-only"]
    )

    assert exit_code == 1


def test_build_observe_command_uses_repair_enabled_converted_root_defaults(tmp_path: Path) -> None:
    command = build_observe_command(
        converted_root=tmp_path / "converted",
        quality_output_dir=tmp_path / "quality",
        run_id="paper_quality",
        jobs=4,
        previous_entry=tmp_path / "previous" / "quality_history_entry.json",
        script_path=tmp_path / "scripts" / "llm_quality_loop.py",
    )

    assert command[1:] == [
        str(tmp_path / "scripts" / "llm_quality_loop.py"),
        "observe",
        "--converted-roots",
        str(tmp_path / "converted"),
        "--out-dir",
        str(tmp_path / "quality"),
        "--run-id",
        "paper_quality",
        "--polish-language",
        "auto",
        "--include-non-target-language",
        "--jobs",
        "4",
        "--previous-entry",
        str(tmp_path / "previous" / "quality_history_entry.json"),
        "--no-append-history",
        "--fail-on-gate",
    ]
    assert "--audit-converted-existing" not in command
    assert "--skip-tests" not in command


def test_collect_final_html_copies_audited_polish_outputs(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    stage_dir = tmp_path / "converted" / "article_a" / "_z2m_stages"
    _write_current_stage_pair(stage_dir, tmp_path / "paper.pdf")
    source = _seal_quality_output(quality_dir, stage_dir, "article_a")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir()
    stale_path = final_dir / "removed_article.html"
    stale_path.write_text("<html><body>stale</body></html>", encoding="utf-8")

    collection = collect_final_html(quality_dir)

    assert len(collection.artifacts) == 1
    final_path = quality_dir / "final_html" / "article_a.html"
    assert collection.artifacts[0].final_path == final_path.resolve(strict=False)
    assert final_path.read_text(encoding="utf-8") == "<html><body>clean</body></html>"
    manifest = json.loads(collection.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert len(manifest["publication_id"]) == 32
    assert manifest["article_count"] == 1
    assert manifest["html_files"][0]["article"] == "article_a"
    assert manifest["html_files"][0]["bytes"] == final_path.stat().st_size
    assert len(manifest["html_files"][0]["sha256"]) == 64
    assert Path(manifest["html_files"][0]["source_path"]) == source.resolve(strict=False)
    assert not stale_path.exists()


def test_publish_final_html_rejects_duplicate_article_names_before_writing(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    sources: list[tuple[str, Path]] = []
    for branch, body in (("first", "one"), ("second", "two")):
        source = quality_dir / "audit_tree" / branch / "duplicate" / "02.en.polish.html"
        source.parent.mkdir(parents=True)
        source.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
        sources.append(("duplicate", source))

    with pytest.raises(RuntimeError, match="Duplicate final HTML article name 'duplicate'"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=quality_dir / "final_html",
            sources=sources,
        )

    assert not (quality_dir / "final_html" / "duplicate.html").exists()
    assert not (quality_dir / "final_html" / "final_html_manifest.json").exists()


def test_collect_final_html_rejects_portable_case_collisions(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    first_source = tmp_path / "first.html"
    second_source = tmp_path / "second.html"
    first_source.write_text("<html><body>first</body></html>", encoding="utf-8")
    second_source.write_text("<html><body>second</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"

    with pytest.raises(RuntimeError, match="Duplicate final HTML article name"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=(("Article", first_source), ("article", second_source)),
        )

    assert not (final_dir / "Article.html").exists()
    assert not (final_dir / "article.html").exists()
    assert not (final_dir / "final_html_manifest.json").exists()


def test_collect_final_html_failed_copy_preserves_previous_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_dir = tmp_path / "quality"
    stage_dir = tmp_path / "converted" / "article_a" / "_z2m_stages"
    _write_current_stage_pair(stage_dir, tmp_path / "paper.pdf")
    _seal_quality_output(quality_dir, stage_dir, "article_a", audited_html="<html><body>new</body></html>")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir()
    final_path = final_dir / "article_a.html"
    final_path.write_text("<html><body>previous</body></html>", encoding="utf-8")

    def fail_copy(_source: Path, temporary: Path) -> None:
        Path(temporary).write_text("partial", encoding="utf-8")
        raise OSError("simulated interrupted copy")

    monkeypatch.setattr(atomic_io_module.shutil, "copyfile", fail_copy)

    with pytest.raises(OSError, match="simulated interrupted copy"):
        collect_final_html(quality_dir)

    assert final_path.read_text(encoding="utf-8") == "<html><body>previous</body></html>"
    assert list(final_dir.glob("*.tmp")) == []


def test_publish_final_html_failed_second_copy_preserves_entire_previous_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_dir = tmp_path / "quality"
    sources: list[tuple[str, Path]] = []
    for article in ("article_a", "article_b"):
        source = quality_dir / "sources" / f"{article}.html"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"<html><body>new {article}</body></html>", encoding="utf-8")
        sources.append((article, source))

    final_dir = quality_dir / "final_html"
    final_dir.mkdir(parents=True)
    (final_dir / "article_a.html").write_text("old a", encoding="utf-8")
    (final_dir / "article_b.html").write_text("old b", encoding="utf-8")
    (final_dir / "stale.html").write_text("old stale", encoding="utf-8")
    (final_dir / "final_html_manifest.json").write_text(
        "old manifest", encoding="utf-8"
    )
    before = {
        path.relative_to(final_dir).as_posix(): path.read_bytes()
        for path in final_dir.rglob("*")
        if path.is_file()
    }

    original_copy = clean_pipeline_module._copy_file_atomic
    copy_count = 0

    def fail_second_copy(source: Path, target: Path) -> None:
        nonlocal copy_count
        copy_count += 1
        if copy_count == 2:
            raise OSError("simulated second copy failure")
        original_copy(source, target)

    monkeypatch.setattr(clean_pipeline_module, "_copy_file_atomic", fail_second_copy)

    with pytest.raises(OSError, match="simulated second copy failure"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=sources,
        )

    after = {
        path.relative_to(final_dir).as_posix(): path.read_bytes()
        for path in final_dir.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_publish_final_html_manifest_failure_preserves_entire_previous_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "sources" / "article_a.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>new</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir(parents=True)
    (final_dir / "article_a.html").write_text("old", encoding="utf-8")
    (final_dir / "stale.html").write_text("stale", encoding="utf-8")
    (final_dir / "final_html_manifest.json").write_text(
        "old manifest", encoding="utf-8"
    )
    before = {
        path.relative_to(final_dir).as_posix(): path.read_bytes()
        for path in final_dir.rglob("*")
        if path.is_file()
    }

    def fail_manifest(_path: Path, _payload: object) -> None:
        raise OSError("simulated manifest failure")

    monkeypatch.setattr(clean_pipeline_module, "_write_json_atomic", fail_manifest)

    with pytest.raises(OSError, match="simulated manifest failure"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=(("article_a", source),),
        )

    after = {
        path.relative_to(final_dir).as_posix(): path.read_bytes()
        for path in final_dir.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_publish_final_html_rejects_article_path_traversal_before_writing(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>source</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"

    with pytest.raises(ValueError, match="article name"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=(("../escaped", source),),
        )

    assert not (quality_dir / "escaped.html").exists()
    assert not final_dir.exists()


def test_publish_final_html_rejects_quality_directory_as_empty_target(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    quality_dir.mkdir()
    sentinel = quality_dir / "existing.html"
    sentinel.write_text("<html><body>keep</body></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="quality_output_dir"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=quality_dir,
            sources=(),
        )

    assert sentinel.read_text(encoding="utf-8") == "<html><body>keep</body></html>"
    assert not (quality_dir / "final_html_manifest.json").exists()


def test_publish_final_html_rejects_noncanonical_target_before_writing(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>source</body></html>", encoding="utf-8")
    target_dir = quality_dir / "alias" / ".." / "final_html"

    with pytest.raises(ValueError, match="canonical"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=target_dir,
            sources=(("article_a", source),),
        )

    assert not (quality_dir / "final_html").exists()


@pytest.mark.parametrize(
    "article",
    [
        "..",
        "CON",
        "CON .report",
        "COM\u00b9.report",
        "LPT\u00b2.scan",
        "bad\\name",
        "bad:name",
        "bad.",
        "e\u0301",
    ],
)
def test_publish_final_html_rejects_nonportable_article_names_before_writing(
    tmp_path: Path,
    article: str,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>source</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"

    with pytest.raises(ValueError, match="article name"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=((article, source),),
        )

    assert not final_dir.exists()


def test_publish_final_html_rejects_link_like_target_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>source</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"
    monkeypatch.setattr(
        clean_pipeline_module,
        "path_is_link_like",
        lambda path: Path(path) == final_dir,
    )

    with pytest.raises(ValueError, match="link-like"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=(("article_a", source),),
        )


def test_collect_final_html_rejects_noncanonical_public_target_before_writing(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    stage_dir = tmp_path / "converted" / "article_a" / "_z2m_stages"
    _write_current_stage_pair(stage_dir, tmp_path / "paper.pdf")
    _seal_quality_output(quality_dir, stage_dir, "article_a")
    target_dir = tmp_path / "public" / "alias" / ".." / "final_html"

    with pytest.raises(ValueError, match="canonical"):
        collect_final_html(quality_dir, final_html_dir=target_dir)

    assert not (tmp_path / "public" / "final_html").exists()


def test_publish_final_html_cancellation_during_staging_preserves_previous_tree(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    sources: list[tuple[str, Path]] = []
    for article in ("article_a", "article_b"):
        source = quality_dir / "sources" / f"{article}.html"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"<html><body>{article}</body></html>", encoding="utf-8")
        sources.append((article, source))
    final_dir = quality_dir / "final_html"
    final_dir.mkdir(parents=True)
    previous = final_dir / "previous.html"
    previous.write_text("<html><body>previous</body></html>", encoding="utf-8")
    cancellation_checks = 0

    def cancel_after_first_copy() -> bool:
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks >= 2

    with pytest.raises(RuntimeError, match="cancelled before commit"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=sources,
            is_cancelled=cancel_after_first_copy,
        )

    assert previous.read_text(encoding="utf-8") == "<html><body>previous</body></html>"
    assert {entry.name for entry in final_dir.iterdir()} == {"previous.html"}


def test_publish_final_html_detects_byte_identical_target_directory_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)

    source.write_text("<html><body>new</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir(parents=True)
    (final_dir / "article_a.html").write_text(
        "<html><body>old</body></html>",
        encoding="utf-8",
    )
    (final_dir / "final_html_manifest.json").write_text(
        "old manifest", encoding="utf-8"
    )
    detached = quality_dir / "detached_original"
    original_write = clean_pipeline_module._write_json_atomic

    def write_then_replace_target(path: Path, payload: object) -> None:
        original_write(path, payload)
        final_dir.replace(detached)
        shutil.copytree(detached, final_dir, copy_function=shutil.copy2)

    monkeypatch.setattr(
        clean_pipeline_module,
        "_write_json_atomic",
        write_then_replace_target,
    )

    with pytest.raises(RuntimeError, match="changed during publication"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=(("article_a", source),),
        )

    assert (final_dir / "article_a.html").read_text(encoding="utf-8") == (
        "<html><body>old</body></html>"
    )
    assert (detached / "article_a.html").read_text(encoding="utf-8") == (
        "<html><body>old</body></html>"
    )


def test_publish_final_html_replaces_hardlinked_old_entry_without_touching_peer(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>new</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir(parents=True)
    sentinel = quality_dir / "external_sentinel.html"
    sentinel.write_text("<html><body>external old</body></html>", encoding="utf-8")
    (final_dir / "article_a.html").hardlink_to(sentinel)

    clean_pipeline_module._publish_final_html(
        quality_dir=quality_dir,
        target_dir=final_dir,
        sources=(("article_a", source),),
    )

    assert (
        sentinel.read_text(encoding="utf-8") == "<html><body>external old</body></html>"
    )
    assert (final_dir / "article_a.html").read_text(encoding="utf-8") == (
        "<html><body>new</body></html>"
    )


def test_final_html_manifest_detects_published_html_tampering(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>new</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"

    collection = clean_pipeline_module._publish_final_html(
        quality_dir=quality_dir,
        target_dir=final_dir,
        sources=(("article_a", source),),
    )
    manifest = json.loads(collection.manifest_path.read_text(encoding="utf-8"))
    publication_id = manifest["publication_id"]

    assert clean_pipeline_module._final_html_tree_matches_publication(
        final_dir,
        publication_id,
    )
    (final_dir / "article_a.html").write_text(
        "<html><body>tampered</body></html>",
        encoding="utf-8",
    )
    assert not clean_pipeline_module._final_html_tree_matches_publication(
        final_dir,
        publication_id,
    )


def test_publish_final_html_rejects_foreign_target_entry_before_writing(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>new</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir(parents=True)
    foreign = final_dir / "owner-notes.txt"
    foreign.write_text("do not delete", encoding="utf-8")

    with pytest.raises(RuntimeError, match="foreign entry"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=final_dir,
            sources=(("article_a", source),),
        )

    assert foreign.read_text(encoding="utf-8") == "do not delete"
    assert not (final_dir / "article_a.html").exists()

def test_publish_final_html_rejects_unowned_nonempty_external_target(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>new</body></html>", encoding="utf-8")
    external_dir = tmp_path / "operator-selected-html"
    external_dir.mkdir()
    foreign = external_dir / "important.html"
    foreign.write_text("<html><body>keep</body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="valid ownership manifest"):
        clean_pipeline_module._publish_final_html(
            quality_dir=quality_dir,
            target_dir=external_dir,
            sources=(("article_a", source),),
        )

    assert foreign.read_text(encoding="utf-8") == "<html><body>keep</body></html>"
    assert not (external_dir / "article_a.html").exists()


def test_publish_final_html_republishes_owned_external_target(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>first</body></html>", encoding="utf-8")
    external_dir = tmp_path / "published-html"

    clean_pipeline_module._publish_final_html(
        quality_dir=quality_dir,
        target_dir=external_dir,
        sources=(("article_a", source),),
    )
    source.write_text("<html><body>second</body></html>", encoding="utf-8")
    clean_pipeline_module._publish_final_html(
        quality_dir=quality_dir,
        target_dir=external_dir,
        sources=(("article_a", source),),
    )

    assert (external_dir / "article_a.html").read_text(encoding="utf-8") == (
        "<html><body>second</body></html>"
    )



def test_collect_final_html_rejects_target_containing_source(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    stage_dir = tmp_path / "converted" / "article_a" / "_z2m_stages"
    _write_current_stage_pair(stage_dir, tmp_path / "paper.pdf")
    source = _seal_quality_output(
        quality_dir, stage_dir, "article_a", audited_html="<html><body>source</body></html>"
    )
    article_dir = source.parent

    with pytest.raises(ValueError, match="final_html_dir contains source HTML"):
        collect_final_html(quality_dir, final_html_dir=article_dir)

    assert source.read_text(encoding="utf-8") == "<html><body>source</body></html>"
    assert not (article_dir / "article_a.html").exists()
    assert not (article_dir / "final_html_manifest.json").exists()



def test_collect_final_html_rejects_missing_publication_seal(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    source = quality_dir / "audit_tree" / "article_a" / POLISH_STAGE_NAME
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>unsealed</body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="requires a valid quality publication seal"):
        collect_final_html(quality_dir)

    assert not (quality_dir / "final_html" / "article_a.html").exists()


def test_collect_final_html_rejects_audited_polish_tampered_after_seal(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    stage_dir = tmp_path / "converted" / "article_a" / "_z2m_stages"
    _write_current_stage_pair(stage_dir, tmp_path / "paper.pdf")
    source = _seal_quality_output(quality_dir, stage_dir, "article_a")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir()
    final_path = final_dir / "article_a.html"
    final_path.write_text("<html><body>previous</body></html>", encoding="utf-8")
    source.write_text("<html><body>tampered but valid</body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="requires a valid quality publication seal"):
        collect_final_html(quality_dir)

    assert final_path.read_text(encoding="utf-8") == "<html><body>previous</body></html>"


def test_collect_final_html_rejects_skipped_fallback_tampered_after_seal(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    stage_dir = tmp_path / "converted" / "article_es" / "_z2m_stages"
    _write_current_stage_pair(
        stage_dir,
        tmp_path / "paper.pdf",
        polish_html="<html><body>sealed fallback</body></html>",
    )
    _seal_skipped_quality_output(quality_dir, stage_dir, "article_es")
    fallback = stage_dir / POLISH_STAGE_NAME
    fallback.write_text("<html><body>changed fallback</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir()
    previous = final_dir / "article_es.html"
    previous.write_text("<html><body>previous</body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="requires a valid quality publication seal"):
        collect_final_html(quality_dir)

    assert previous.read_text(encoding="utf-8") == "<html><body>previous</body></html>"


def test_collect_final_html_rechecks_skipped_fallback_after_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_dir = tmp_path / "quality"
    stage_dir = tmp_path / "converted" / "article_es" / "_z2m_stages"
    _write_current_stage_pair(
        stage_dir,
        tmp_path / "paper.pdf",
        polish_html="<html><body>sealed fallback</body></html>",
    )
    _seal_skipped_quality_output(quality_dir, stage_dir, "article_es")
    fallback = stage_dir / POLISH_STAGE_NAME
    final_dir = quality_dir / "final_html"
    final_dir.mkdir()
    previous = final_dir / "article_es.html"
    previous.write_text("<html><body>previous</body></html>", encoding="utf-8")
    original_stage = clean_pipeline_module.stage_sealed_polish

    def stage_then_change_fallback(
        source: Path,
        destination: Path,
        sealed_record: dict,
        *,
        fingerprint_key: str,
    ) -> None:
        original_stage(
            source,
            destination,
            sealed_record,
            fingerprint_key=fingerprint_key,
        )
        fallback.write_text("<html><body>raced fallback</body></html>", encoding="utf-8")

    monkeypatch.setattr(clean_pipeline_module, "stage_sealed_polish", stage_then_change_fallback)

    with pytest.raises(RuntimeError, match="changed during final HTML collection"):
        collect_final_html(quality_dir)

    assert previous.read_text(encoding="utf-8") == "<html><body>previous</body></html>"


def test_run_clean_pipeline_runs_conversion_observe_and_collects_final_html(tmp_path: Path) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    article_id = "converted_article_a"
    logs: list[str] = []
    observe_calls: list[tuple[list[str], Path | None]] = []

    def fake_pipeline_runner(*_args):
        stage_dir = conversion_dir / "article_a" / "_z2m_stages"
        _write_current_stage_pair(
            stage_dir,
            tmp_path / "paper.pdf",
        )
        (conversion_dir / "article_a" / "article_a.html").write_text(
            "<html><body>extra</body></html>",
            encoding="utf-8",
        )
        return _summary(conversion_dir)

    def fake_observe_runner(command, cwd, log):
        observe_calls.append((list(command), cwd))
        _seal_quality_output(
            quality_dir,
            conversion_dir / "article_a" / "_z2m_stages",
            article_id,
            audited_html="<html><body>audited</body></html>",
        )
        if log is not None:
            log("observe ok")
        return 0

    summary = run_clean_pipeline(
        CleanPipelineOptions(
            conversion_options=PipelineOptions(
                source_pdf_paths=[str(tmp_path / "paper.pdf")],
                output_dir=str(conversion_dir),
                export_mode="html",
            ),
            quality_output_dir=str(quality_dir),
            run_id="quality_run",
            jobs=2,
        ),
        MarkerRunner(),
        logs.append,
        lambda: False,
        pipeline_runner=fake_pipeline_runner,
        observe_runner=fake_observe_runner,
    )

    assert summary.conversion_summary.converted_total == 1
    assert summary.quality_output_dir == quality_dir.resolve(strict=False)
    assert summary.run_id == "quality_run"
    assert observe_calls
    assert "--converted-roots" in observe_calls[0][0]
    assert "--jobs" in observe_calls[0][0]
    assert summary.final_html.artifacts[0].final_path.read_text(encoding="utf-8") == (
        "<html><body>audited</body></html>"
    )
    assert summary.converted_stage_publish_report is not None
    assert summary.converted_stage_publish_report["stage_contract_status"] == "pass"
    assert (conversion_dir / "article_a" / "_z2m_stages" / "02.en.polish.html").read_text(encoding="utf-8") == (
        "<html><body>audited</body></html>"
    )
    root_manifest = json.loads((conversion_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))
    stage_manifest = json.loads(
        (conversion_dir / "article_a" / "_z2m_stages" / "pipeline_manifest.json").read_text(encoding="utf-8")
    )
    assert root_manifest["articles"][0]["en_html_path"].endswith("02.en.polish.html")
    assert stage_manifest["en_html_path"].endswith("02.en.polish.html")
    assert "detection" in stage_manifest
    assert "gate" in stage_manifest
    assert not (conversion_dir / "article_a" / "article_a.html").exists()
    assert "observe ok" in logs


def test_run_clean_pipeline_validates_new_and_skipped_raw_stages_together(
    tmp_path: Path,
) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    first_source = tmp_path / "first.pdf"
    second_source = tmp_path / "second.pdf"

    def fake_pipeline_runner(*_args):
        _write_current_stage_pair(
            conversion_dir / "first" / "_z2m_stages",
            first_source,
        )
        _write_current_stage_pair(
            conversion_dir / "second" / "_z2m_stages",
            second_source,
        )
        return _summary(
            conversion_dir,
            converted_total=1,
            skipped_existing=1,
        )

    def fake_observe_runner(_command, _cwd, _log):
        _seal_quality_output(
            quality_dir,
            conversion_dir / "first" / "_z2m_stages",
            "first",
            audited_html="<html><body>audited</body></html>",
        )
        _append_skipped_quality_output(
            quality_dir,
            conversion_dir / "second" / "_z2m_stages",
            "second",
        )
        return 0

    summary = run_clean_pipeline(
        CleanPipelineOptions(
            conversion_options=PipelineOptions(
                source_pdf_paths=[str(first_source), str(second_source)],
                output_dir=str(conversion_dir),
                export_mode="html",
            ),
            quality_output_dir=str(quality_dir),
        ),
        MarkerRunner(),
        lambda _message: None,
        lambda: False,
        pipeline_runner=fake_pipeline_runner,
        observe_runner=fake_observe_runner,
    )

    assert summary.conversion_summary.converted_total == 1
    assert summary.conversion_summary.skipped_existing == 1
    artifacts = {artifact.article: artifact for artifact in summary.final_html.artifacts}
    assert set(artifacts) == {"first", "second"}
    assert summary.converted_stage_publish_report is not None
    assert summary.converted_stage_publish_report["published_count"] == 1
    assert summary.converted_stage_publish_report["stage_contract_status"] == "pass"
    assert (conversion_dir / "first" / "_z2m_stages" / POLISH_STAGE_NAME).read_text(
        encoding="utf-8"
    ) == "<html><body>audited</body></html>"
    assert (conversion_dir / "second" / "_z2m_stages" / POLISH_STAGE_NAME).read_text(
        encoding="utf-8"
    ) == "<html><body>stale</body></html>"
    assert artifacts["first"].final_path.read_text(encoding="utf-8") == (
        "<html><body>audited</body></html>"
    )
    assert artifacts["second"].final_path.read_text(encoding="utf-8") == (
        "<html><body>stale</body></html>"
    )


def test_run_clean_pipeline_repolishes_when_every_conversion_is_already_current(
    tmp_path: Path,
) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    source_pdf = tmp_path / "paper.pdf"
    observe_calls: list[list[str]] = []

    def fake_pipeline_runner(*_args):
        _write_current_stage_pair(
            conversion_dir / "article_a" / "_z2m_stages",
            source_pdf,
        )
        return _summary(
            conversion_dir,
            converted_total=0,
            skipped_existing=1,
        )

    def fake_observe_runner(command, _cwd, _log):
        observe_calls.append(list(command))
        _seal_quality_output(
            quality_dir,
            conversion_dir / "article_a" / "_z2m_stages",
            "article_a",
            audited_html="<html><body>repolished current</body></html>",
        )
        return 0

    summary = run_clean_pipeline(
        CleanPipelineOptions(
            conversion_options=PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(conversion_dir),
                export_mode="html",
            ),
            quality_output_dir=str(quality_dir),
            publish_latest_to_converted=False,
        ),
        MarkerRunner(),
        lambda _message: None,
        lambda: False,
        pipeline_runner=fake_pipeline_runner,
        observe_runner=fake_observe_runner,
    )

    assert summary.conversion_summary.converted_total == 0
    assert summary.conversion_summary.skipped_existing == 1
    assert observe_calls
    assert summary.final_html.artifacts[0].final_path.read_text(encoding="utf-8") == (
        "<html><body>repolished current</body></html>"
    )



def test_run_clean_pipeline_repolishes_existing_raw_without_conversion(tmp_path: Path) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    stage_dir = conversion_dir / "article_a" / "_z2m_stages"
    source_pdf = tmp_path / "paper.pdf"
    _write_current_stage_pair(
        stage_dir,
        source_pdf,
    )
    logs: list[str] = []
    observe_calls: list[list[str]] = []

    def fail_pipeline_runner(*_args):
        raise AssertionError("repolish-only mode must not invoke PDF conversion")

    def fake_observe_runner(command, cwd, log):
        observe_calls.append(list(command))
        _seal_quality_output(
            quality_dir,
            stage_dir,
            "article_a",
            audited_html="<html><body>repolished</body></html>",
        )
        if log is not None:
            log("repolish observe ok")
        return 0

    summary = run_clean_pipeline(
        CleanPipelineOptions(
            conversion_options=PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(conversion_dir),
                export_mode="html",
            ),
            quality_output_dir=str(quality_dir),
            publish_latest_to_converted=False,
            skip_quality_tests=True,
            reuse_existing_conversion=True,
        ),
        MarkerRunner(),
        logs.append,
        lambda: False,
        pipeline_runner=fail_pipeline_runner,
        observe_runner=fake_observe_runner,
    )

    assert summary.conversion_summary.converted_total == 1
    assert observe_calls
    assert "--skip-tests" in observe_calls[0]
    assert summary.final_html.artifacts[0].final_path.read_text(encoding="utf-8") == (
        "<html><body>repolished</body></html>"
    )
    assert any("Reusing existing PDF HTML raw stages" in entry for entry in logs)


def test_run_clean_pipeline_repolish_rejects_tampered_raw_before_observe(
    tmp_path: Path,
) -> None:
    conversion_dir = tmp_path / "converted"
    source_pdf = tmp_path / "paper.pdf"
    stage_dir = conversion_dir / "article_a" / "_z2m_stages"
    _write_current_stage_pair(stage_dir, source_pdf)
    (stage_dir / RAW_STAGE_NAME).write_text(
        "<html><body>tampered raw</body></html>",
        encoding="utf-8",
    )

    def fail_pipeline_runner(*_args):
        raise AssertionError("repolish-only mode must not invoke conversion")

    def fail_observe_runner(*_args):
        raise AssertionError("invalid raw stage must not reach observe")

    with pytest.raises(RuntimeError, match="raw_fingerprint_mismatch"):
        run_clean_pipeline(
            CleanPipelineOptions(
                conversion_options=PipelineOptions(
                    source_pdf_paths=[str(source_pdf)],
                    output_dir=str(conversion_dir),
                    export_mode="html",
                ),
                quality_output_dir=str(tmp_path / "quality"),
                publish_latest_to_converted=False,
                reuse_existing_conversion=True,
            ),
            MarkerRunner(),
            lambda _message: None,
            lambda: False,
            pipeline_runner=fail_pipeline_runner,
            observe_runner=fail_observe_runner,
        )


def test_run_clean_pipeline_repolish_existing_requires_raw_stage(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="01.en.raw.html"):
        run_clean_pipeline(
            CleanPipelineOptions(
                conversion_options=PipelineOptions(output_dir=str(tmp_path / "converted")),
                reuse_existing_conversion=True,
            ),
            MarkerRunner(),
            lambda _message: None,
            lambda: False,
        )


def test_run_clean_pipeline_collects_sealed_fallback_when_observe_skips_all(
    tmp_path: Path,
) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    logs: list[str] = []

    def fake_pipeline_runner(*_args):
        stage_dir = conversion_dir / "article_es" / "_z2m_stages"
        _write_current_stage_pair(
            stage_dir,
            tmp_path / "paper.pdf",
            raw_html="<html><body>bruto</body></html>",
            polish_html="<html><body>limpio</body></html>",
        )
        return _summary(conversion_dir)

    def fake_observe_runner(command, cwd, log):
        _seal_skipped_quality_output(
            quality_dir,
            conversion_dir / "article_es" / "_z2m_stages",
            "article_es",
        )
        if log is not None:
            log("observe skipped non-en article")
        return 0

    summary = run_clean_pipeline(
        CleanPipelineOptions(
            conversion_options=PipelineOptions(
                source_pdf_paths=[str(tmp_path / "paper.pdf")],
                output_dir=str(conversion_dir),
                export_mode="html",
            ),
            quality_output_dir=str(quality_dir),
        ),
        MarkerRunner(),
        logs.append,
        lambda: False,
        pipeline_runner=fake_pipeline_runner,
        observe_runner=fake_observe_runner,
    )

    assert len(summary.final_html.artifacts) == 1
    assert summary.final_html.artifacts[0].source_path == (
        conversion_dir / "article_es" / "_z2m_stages" / "02.en.polish.html"
    ).resolve(strict=False)
    assert summary.converted_stage_publish_report is not None
    assert summary.converted_stage_publish_report["published_count"] == 0
    assert summary.converted_stage_publish_report["stage_contract_status"] == "pass"
    assert (quality_dir / "final_html" / "article_es.html").read_text(encoding="utf-8") == (
        "<html><body>limpio</body></html>"
    )
    manifest = json.loads(summary.final_html.manifest_path.read_text(encoding="utf-8"))
    assert "fallback_source" not in manifest
    assert not any("converted-stage polish fallback" in entry for entry in logs)


def test_run_clean_pipeline_skips_observe_when_conversion_failed(tmp_path: Path) -> None:
    def fake_pipeline_runner(*_args):
        return _summary(tmp_path / "converted", failed_total=1)

    def fail_observe_runner(*_args):
        raise AssertionError("observe should not run after conversion failure")

    with pytest.raises(RuntimeError, match="PDF conversion failed"):
        run_clean_pipeline(
            CleanPipelineOptions(
                conversion_options=PipelineOptions(
                    source_pdf_paths=[str(tmp_path / "paper.pdf")],
                    output_dir=str(tmp_path / "converted"),
                    export_mode="html",
                )
            ),
            MarkerRunner(),
            lambda _message: None,
            lambda: False,
            pipeline_runner=fake_pipeline_runner,
            observe_runner=fail_observe_runner,
        )


def test_run_clean_pipeline_skips_observe_when_nothing_converted(tmp_path: Path) -> None:
    def fake_pipeline_runner(*_args):
        return _summary(tmp_path / "converted", converted_total=0)

    def fail_observe_runner(*_args):
        raise AssertionError("observe should not run when conversion did no work")

    final_dir = tmp_path / "converted_quality" / "final_html"
    final_dir.mkdir(parents=True)
    stale_path = final_dir / "stale.html"
    stale_path.write_text("<html><body>stale</body></html>", encoding="utf-8")
    summary = run_clean_pipeline(
        CleanPipelineOptions(
            conversion_options=PipelineOptions(
                source_pdf_paths=[str(tmp_path / "paper.pdf")],
                output_dir=str(tmp_path / "converted"),
                export_mode="html",
            )
        ),
        MarkerRunner(),
        lambda _message: None,
        lambda: False,
        pipeline_runner=fake_pipeline_runner,
        observe_runner=fail_observe_runner,
    )

    assert summary.observe_command == ()
    assert summary.observe_exit_code == 0
    assert summary.final_html.artifacts == ()
    assert not stale_path.exists()


def test_clean_pipeline_gate_policy_is_fail_closed_by_default(tmp_path: Path) -> None:
    assert CleanPipelineOptions.__dataclass_fields__["fail_on_gate"].default is True

    command = build_observe_command(
        converted_root=tmp_path / "converted",
        quality_output_dir=tmp_path / "quality",
        run_id="quality",
        script_path=tmp_path / "scripts" / "llm_quality_loop.py",
    )
    diagnostic_command = build_observe_command(
        converted_root=tmp_path / "converted",
        quality_output_dir=tmp_path / "quality-diagnostic",
        run_id="quality-diagnostic",
        fail_on_gate=False,
        script_path=tmp_path / "scripts" / "llm_quality_loop.py",
    )

    assert "--fail-on-gate" in command
    assert "--diagnostic-allow-gate-failure" not in command
    assert "--diagnostic-allow-gate-failure" in diagnostic_command
    assert "--fail-on-gate" not in diagnostic_command


def test_clean_public_parser_fails_on_gate_by_default() -> None:
    parser = build_parser()

    default_args = parser.parse_args(["--pdf", "paper.pdf", "--output-dir", "out"])
    diagnostic_args = parser.parse_args(
        ["--pdf", "paper.pdf", "--output-dir", "out", "--diagnostic-allow-gate-failure"]
    )

    assert default_args.fail_on_gate is True
    assert diagnostic_args.fail_on_gate is False


def test_run_observe_command_stops_process_when_log_callback_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spawned: list[subprocess.Popen[str]] = []
    real_popen = subprocess.Popen

    def tracking_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        spawned.append(process)
        return process

    def failing_log(line: str) -> None:
        if line == "trigger-cleanup":
            raise OSError("injected observe log failure")

    monkeypatch.setattr(
        clean_pipeline_module.subprocess,
        "Popen",
        tracking_popen,
    )

    with pytest.raises(OSError, match="injected observe log failure"):
        clean_pipeline_module.run_observe_command(
            [
                sys.executable,
                "-c",
                "import time; print('trigger-cleanup', flush=True); time.sleep(30)",
            ],
            cwd=tmp_path,
            log=failing_log,
        )

    assert len(spawned) == 1
    deadline = time.monotonic() + 5
    while spawned[0].poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert spawned[0].poll() is not None
