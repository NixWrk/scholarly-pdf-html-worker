from __future__ import annotations

from pathlib import Path

import pytest

from pdf_html_polish.export_modes import ExportMode
from pdf_html_polish.marker_runner import RunResult
from pdf_html_polish.models import AttachmentRecord, ResolvedAttachment
import pdf_html_polish.pipeline as pipeline_module
from pdf_html_polish.pipeline import run_pipeline
from pdf_html_polish.pipeline_options import PdfCandidate, PdfDiscoveryResult, PipelineOptions
from pdf_html_polish.result_state import (
    RESULT_MANIFEST_NAME,
    completed_result_is_current,
)


class _MarkdownRunner:
    def run_batch(self, *, input_dir, output_dir, output_format, **_kwargs):
        assert output_format == "markdown"
        for pdf_path in Path(input_dir).glob("*.pdf"):
            article_dir = Path(output_dir) / pdf_path.stem
            article_dir.mkdir(parents=True, exist_ok=True)
            (article_dir / f"{pdf_path.stem}.md").write_text(
                "# Complete article\n\nStable Markdown body.\n",
                encoding="utf-8",
            )
        return RunResult(command=["fake-marker"], exit_code=0)

    def run_single(self, **_kwargs):  # pragma: no cover - batch must succeed
        raise AssertionError("markdown batch should have produced the artifact")


class _HtmlRunner:
    def run_batch(self, *, input_dir, output_dir, output_format, **_kwargs):
        assert output_format == "html"
        for pdf_path in Path(input_dir).glob("*.pdf"):
            article_dir = Path(output_dir) / pdf_path.stem
            article_dir.mkdir(parents=True, exist_ok=True)
            (article_dir / f"{pdf_path.stem}.html").write_text(
                "<html><body><p>Complete article output.</p></body></html>",
                encoding="utf-8",
            )
        return RunResult(command=["fake-marker"], exit_code=0)

    def run_single(self, **_kwargs):  # pragma: no cover - batch must succeed
        raise AssertionError("HTML batch should have produced the artifact")


def test_markdown_completion_manifest_is_the_only_skip_authority(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    output_dir = tmp_path / "out"

    first = run_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode=ExportMode.CLASSIC.value,
            skip_existing=False,
        ),
        _MarkdownRunner(),  # type: ignore[arg-type]
        lambda _message: None,
        lambda: False,
    )
    artifact_path = output_dir / "paper" / "paper.md"

    assert first.converted_total == 1
    assert first.failed_total == 0
    assert first.result_commit_failed_total == 0
    assert completed_result_is_current(source_pdf, artifact_path)

    class MustNotRun:
        def run_batch(self, **_kwargs):
            raise AssertionError("committed Markdown should be skipped before Marker")

        def run_single(self, **_kwargs):
            raise AssertionError("committed Markdown should be skipped before Marker")

    second = run_pipeline(
        PipelineOptions(
            source_pdf_paths=[str(source_pdf)],
            output_dir=str(output_dir),
            export_mode=ExportMode.CLASSIC.value,
        ),
        MustNotRun(),  # type: ignore[arg-type]
        lambda _message: None,
        lambda: False,
    )

    assert second.converted_total == 0
    assert second.skipped_existing == 1
    assert second.failed_total == 0


def test_llm_bundle_failure_leaves_markdown_result_uncommitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    output_dir = tmp_path / "out"

    def fail_bundle(**_kwargs):
        raise RuntimeError("simulated LLM bundle failure")

    monkeypatch.setattr(pipeline_module, "create_llm_bundle", fail_bundle)

    with pytest.raises(RuntimeError, match="simulated LLM bundle failure"):
        run_pipeline(
            PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(output_dir),
                export_mode=ExportMode.LLM.value,
                skip_existing=False,
            ),
            _MarkdownRunner(),  # type: ignore[arg-type]
            lambda _message: None,
            lambda: False,
        )

    article_dir = output_dir / "paper"
    assert (article_dir / "paper.md").is_file()
    assert not (article_dir / RESULT_MANIFEST_NAME).exists()


def test_html_result_commit_failure_blocks_zotero_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    output_dir = tmp_path / "out"
    zotero_dir = tmp_path / "zotero"
    zotero_dir.mkdir()
    resolved = ResolvedAttachment(
        attachment=AttachmentRecord(
            item_id=7,
            attachment_key="PDFKEY01",
            parent_item_id=42,
            link_mode=0,
            path=str(source_pdf),
            content_type="application/pdf",
        ),
        source_pdf_path=source_pdf,
    )
    discovery = PdfDiscoveryResult(
        collection_name="Test collection",
        collection_key="TESTCOLL",
        attachments_total=1,
        unresolved_total=0,
        candidates=[PdfCandidate(resolved_attachment=resolved, already_in_output=False)],
    )
    attach_calls: list[dict[str, object]] = []
    logs: list[str] = []

    monkeypatch.setattr(
        pipeline_module,
        "discover_collection_pdfs",
        lambda **_kwargs: discovery,
    )
    monkeypatch.setattr(
        pipeline_module,
        "resolve_zotero_data_dir",
        lambda _path: zotero_dir,
    )
    monkeypatch.setattr(
        pipeline_module,
        "detect_zotero_write_lock",
        lambda _path: False,
    )

    def fail_result_commit(**_kwargs):
        raise OSError("simulated manifest publication failure")

    def record_attach(**kwargs):
        attach_calls.append(dict(kwargs))
        raise AssertionError("uncommitted HTML must not reach Zotero")

    monkeypatch.setattr(pipeline_module, "publish_completed_result", fail_result_commit)
    monkeypatch.setattr(pipeline_module, "attach_single_file_html", record_attach)

    summary = run_pipeline(
        PipelineOptions(
            zotero_data_dir=str(zotero_dir),
            collection_key="TESTCOLL",
            output_dir=str(output_dir),
            export_mode=ExportMode.ZOTERO.value,
            skip_existing=False,
        ),
        _HtmlRunner(),  # type: ignore[arg-type]
        logs.append,
        lambda: False,
    )

    article_dir = output_dir / "paper"
    assert summary.converted_total == 1
    assert summary.failed_total == 1
    assert summary.result_commit_failed_total == 1
    assert summary.zotero_html_attached_total == 0
    assert summary.zotero_html_failed_total == 0
    assert attach_calls == []
    assert not (article_dir / RESULT_MANIFEST_NAME).exists()
    assert any("Zotero attach skipped after HTML output failure" in line for line in logs)
