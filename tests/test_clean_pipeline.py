from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from pdf_html_polish.cli.clean_convert import build_parser
from pdf_html_polish.clean_pipeline import (
    CleanPipelineOptions,
    build_observe_command,
    collect_final_html,
    default_quality_output_dir,
    run_clean_pipeline,
)
from pdf_html_polish.marker_runner import MarkerRunner
from pdf_html_polish.models import PipelineSummary
from pdf_html_polish.pipeline_options import PipelineOptions


def _summary(output_dir: Path, *, failed_total: int = 0) -> PipelineSummary:
    return PipelineSummary(
        collection_key="direct_pdf",
        collection_name="direct PDF files",
        attachments_total=1,
        pdfs_resolved=1,
        staged_total=1,
        converted_total=0 if failed_total else 1,
        skipped_existing=0,
        failed_total=failed_total,
        output_dir=output_dir,
        filename_map_path=output_dir / "_source_filename_map.csv",
        export_mode="html",
    )


def test_default_quality_output_dir_sits_next_to_conversion_output(tmp_path: Path) -> None:
    assert default_quality_output_dir(tmp_path / "paper_run") == tmp_path / "paper_run_quality"


def test_public_console_scripts_only_expose_clean_pipeline() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["pdf-html-polish"] == "pdf_html_polish.cli.clean_convert:main"
    assert scripts["pdf-html-polish-clean"] == "pdf_html_polish.cli.clean_convert:main"


def test_clean_public_parser_does_not_offer_partial_export_mode() -> None:
    parser = build_parser()

    assert "--export-mode" not in parser.format_help()


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
        "--jobs",
        "4",
        "--previous-entry",
        str(tmp_path / "previous" / "quality_history_entry.json"),
        "--no-append-history",
    ]
    assert "--audit-converted-existing" not in command
    assert "--skip-tests" not in command


def test_collect_final_html_copies_audited_polish_outputs(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    article_dir = quality_dir / "audit_tree" / "article_a"
    article_dir.mkdir(parents=True)
    source = article_dir / "02.en.polish.html"
    source.write_text("<html><body>clean</body></html>", encoding="utf-8")

    collection = collect_final_html(quality_dir)

    assert len(collection.artifacts) == 1
    final_path = quality_dir / "final_html" / "article_a.html"
    assert collection.artifacts[0].final_path == final_path.resolve(strict=False)
    assert final_path.read_text(encoding="utf-8") == "<html><body>clean</body></html>"
    manifest = json.loads(collection.manifest_path.read_text(encoding="utf-8"))
    assert manifest["article_count"] == 1
    assert manifest["html_files"][0]["article"] == "article_a"


def test_run_clean_pipeline_runs_conversion_observe_and_collects_final_html(tmp_path: Path) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    logs: list[str] = []
    observe_calls: list[tuple[list[str], Path | None]] = []

    def fake_pipeline_runner(*_args):
        conversion_dir.mkdir(parents=True)
        return _summary(conversion_dir)

    def fake_observe_runner(command, cwd, log):
        observe_calls.append((list(command), cwd))
        final_stage = quality_dir / "audit_tree" / "article_a" / "02.en.polish.html"
        final_stage.parent.mkdir(parents=True)
        final_stage.write_text("<html><body>audited</body></html>", encoding="utf-8")
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
    assert "observe ok" in logs


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
