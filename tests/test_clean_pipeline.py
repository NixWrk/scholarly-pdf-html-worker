from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import pdf_html_polish.clean_pipeline as clean_pipeline_module
import pdf_html_polish.cli.clean_convert as clean_convert_module
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
from pdf_html_polish.marker_runner import RunResult
from pdf_html_polish.html_stages import (
    HTML_STAGE_DIR_NAME,
    RAW_CONVERSION_MANIFEST_NAME,
)
from pdf_html_polish.pipeline import run_raw_html_pipeline
from pdf_html_polish.pipeline_options import PipelineOptions


def _summary(output_dir: Path, *, failed_total: int = 0, converted_total: int | None = None) -> PipelineSummary:
    return PipelineSummary(
        collection_key="direct_pdf",
        collection_name="direct PDF files",
        attachments_total=1,
        pdfs_resolved=1,
        staged_total=1,
        converted_total=converted_total if converted_total is not None else (0 if failed_total else 1),
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
    assert scripts["pdf-html-polish-stage-contract"] == "pdf_html_polish.cli.stage_contract:main"
    assert "pdf-html-convert" not in scripts


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
    final_dir = quality_dir / "final_html"
    final_dir.mkdir()
    stale_path = final_dir / "removed_article.html"
    stale_path.write_text("<html><body>stale</body></html>", encoding="utf-8")
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
    assert not stale_path.exists()


def test_collect_final_html_rejects_duplicate_article_names_before_writing(
    tmp_path: Path,
) -> None:
    quality_dir = tmp_path / "quality"
    for branch, body in (("first", "one"), ("second", "two")):
        source = quality_dir / "audit_tree" / branch / "duplicate" / "02.en.polish.html"
        source.parent.mkdir(parents=True)
        source.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Duplicate final HTML article name 'duplicate'"):
        collect_final_html(quality_dir)

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
    source = quality_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>new</body></html>", encoding="utf-8")
    final_dir = quality_dir / "final_html"
    final_dir.mkdir()
    final_path = final_dir / "article_a.html"
    final_path.write_text("<html><body>previous</body></html>", encoding="utf-8")

    def fail_copy(_source: Path, temporary: Path) -> None:
        Path(temporary).write_text("partial", encoding="utf-8")
        raise OSError("simulated interrupted copy")

    monkeypatch.setattr(clean_pipeline_module.shutil, "copy2", fail_copy)

    with pytest.raises(OSError, match="simulated interrupted copy"):
        collect_final_html(quality_dir)

    assert final_path.read_text(encoding="utf-8") == "<html><body>previous</body></html>"
    assert list(final_dir.glob("*.tmp")) == []


def test_collect_final_html_rejects_target_containing_source(tmp_path: Path) -> None:
    quality_dir = tmp_path / "quality"
    article_dir = quality_dir / "audit_tree" / "article_a"
    article_dir.mkdir(parents=True)
    source = article_dir / "02.en.polish.html"
    source.write_text("<html><body>source</body></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="final_html_dir contains source HTML"):
        collect_final_html(quality_dir, final_html_dir=article_dir)

    assert source.read_text(encoding="utf-8") == "<html><body>source</body></html>"
    assert not (article_dir / "article_a.html").exists()
    assert not (article_dir / "final_html_manifest.json").exists()


def test_run_clean_pipeline_runs_conversion_observe_and_collects_final_html(tmp_path: Path) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    article_id = "converted_article_a"
    logs: list[str] = []
    observe_calls: list[tuple[list[str], Path | None]] = []

    def fake_pipeline_runner(*_args):
        stage_dir = conversion_dir / "article_a" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text("<html><body>raw</body></html>", encoding="utf-8")
        (stage_dir / "02.en.polish.html").write_text("<html><body>stale</body></html>", encoding="utf-8")
        (conversion_dir / "article_a" / "article_a.html").write_text(
            "<html><body>extra</body></html>",
            encoding="utf-8",
        )
        return _summary(conversion_dir)

    def fake_observe_runner(command, cwd, log):
        observe_calls.append((list(command), cwd))
        source_run = quality_dir / "_converted_raw_source"
        source_run.mkdir(parents=True)
        (source_run / "manifest.json").write_text(
            json.dumps(
                {
                    "articles": [
                        {
                            "article_id": article_id,
                            "raw_stage_path": str(conversion_dir / "article_a" / "_z2m_stages" / "01.en.raw.html"),
                            "source_polish_path": str(
                                conversion_dir / "article_a" / "_z2m_stages" / "02.en.polish.html"
                            ),
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (quality_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "source_run_dir": str(source_run),
                    "code_commit": "abc123",
                    "working_tree_dirty": False,
                    "articles": [{"article": article_id}],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        final_stage = quality_dir / "audit_tree" / article_id / "02.en.polish.html"
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


def test_run_clean_pipeline_repolishes_existing_raw_without_conversion(tmp_path: Path) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    stage_dir = conversion_dir / "article_a" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text("<html><body>raw</body></html>", encoding="utf-8")
    (stage_dir / "02.en.polish.html").write_text("<html><body>stale</body></html>", encoding="utf-8")
    logs: list[str] = []
    observe_calls: list[list[str]] = []

    def fail_pipeline_runner(*_args):
        raise AssertionError("repolish-only mode must not invoke PDF conversion")

    def fake_observe_runner(command, cwd, log):
        observe_calls.append(list(command))
        final_stage = quality_dir / "audit_tree" / "article_a" / "02.en.polish.html"
        final_stage.parent.mkdir(parents=True)
        final_stage.write_text("<html><body>repolished</body></html>", encoding="utf-8")
        if log is not None:
            log("repolish observe ok")
        return 0

    summary = run_clean_pipeline(
        CleanPipelineOptions(
            conversion_options=PipelineOptions(
                source_pdf_paths=[str(tmp_path / "paper.pdf")],
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


def test_run_clean_pipeline_uses_converted_stage_fallback_when_observe_skips_all(
    tmp_path: Path,
) -> None:
    conversion_dir = tmp_path / "converted"
    quality_dir = tmp_path / "quality"
    logs: list[str] = []

    def fake_pipeline_runner(*_args):
        stage_dir = conversion_dir / "article_es" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text("<html><body>bruto</body></html>", encoding="utf-8")
        (stage_dir / "02.en.polish.html").write_text("<html><body>limpio</body></html>", encoding="utf-8")
        return _summary(conversion_dir)

    def fake_observe_runner(command, cwd, log):
        (quality_dir / "audit_tree").mkdir(parents=True)
        (quality_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "articles": [],
                    "skipped_articles": [
                        {
                            "article": "article_es",
                            "language_skipped": True,
                            "skip_reason": "detected_es_not_en",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
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
            publish_latest_to_converted=False,
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
    assert (quality_dir / "final_html" / "article_es.html").read_text(encoding="utf-8") == (
        "<html><body>limpio</body></html>"
    )
    manifest = json.loads(summary.final_html.manifest_path.read_text(encoding="utf-8"))
    assert manifest["fallback_source"] == "converted_stage"
    assert any("converted-stage polish fallback" in entry for entry in logs)


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
