from pathlib import Path

import pytest

from pdf_html_polish import pipeline as pipeline_module
from pdf_html_polish import pipeline_zotero
from pdf_html_polish.pipeline_discovery import discover_source_pdfs
from pdf_html_polish.pipeline_options import PipelineOptions
from pdf_html_polish.pipeline_webdav import upload_webdav_mirror_if_configured


def test_pipeline_module_keeps_compatibility_reexports() -> None:
    assert pipeline_module.PipelineOptions is PipelineOptions
    assert pipeline_module.discover_source_pdfs is discover_source_pdfs


def test_discover_source_pdfs_is_file_adapter(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    logs: list[str] = []

    discovery = discover_source_pdfs(
        [str(pdf_path), str(pdf_path), str(tmp_path / "missing.txt")],
        output_dir=str(tmp_path / "out"),
        log=logs.append,
    )

    assert discovery.collection_name == "direct PDF files"
    assert discovery.attachments_total == 2
    assert discovery.unresolved_total == 1
    assert len(discovery.candidates) == 1
    assert discovery.candidates[0].resolved_attachment.source_pdf_path == pdf_path
    assert any("Skipped non-PDF or missing source" in message for message in logs)


def test_webdav_adapter_disabled_is_noop(tmp_path: Path) -> None:
    summary = upload_webdav_mirror_if_configured(
        file_path=tmp_path / "article.html",
        output_dir=tmp_path,
        upload_enabled=False,
    )

    assert summary.uploaded == 0
    assert summary.failed == 0
    assert summary.queued == 0
    assert summary.pending_total == 0
    assert summary.queue_path == tmp_path / "_webdav_pending_uploads.json"


def test_zotero_write_lock_adapter_detects_only_lock_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def locked(_: Path) -> None:
        raise RuntimeError("Zotero database is locked for writing")

    monkeypatch.setattr(pipeline_zotero, "check_zotero_write_access", locked)
    assert pipeline_zotero.zotero_write_lock_detected(tmp_path) is True

    def other_error(_: Path) -> None:
        raise RuntimeError("unexpected sqlite failure")

    monkeypatch.setattr(pipeline_zotero, "check_zotero_write_access", other_error)
    with pytest.raises(RuntimeError, match="unexpected sqlite failure"):
        pipeline_zotero.zotero_write_lock_detected(tmp_path)
