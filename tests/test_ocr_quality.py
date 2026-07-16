import base64
import json
from pathlib import Path
import shutil
from uuid import uuid4

from pdf_html_polish.export_modes import ExportMode
from pdf_html_polish.marker_runner import RunResult
from pdf_html_polish.ocr_quality import (
    REOCR_QUEUE_NAME,
    REOCR_SUFFIX,
    assess_ocr_quality_from_html,
    enqueue_reocr_candidate,
    load_reocr_queue,
)
import pdf_html_polish.pipeline as pipeline_module
from pdf_html_polish.pipeline import PipelineOptions, _find_zotero_overlay_path, run_pipeline


_VALID_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
    "x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _make_temp_dir() -> Path:
    path = Path(".tmp_local2") / f"test_ocr_quality_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_ocr_quality_allows_normal_text() -> None:
    html = (
        "<html><body>"
        "<p>This article describes accessible tactile diagrams and reports "
        "a controlled evaluation with participants, figures, references, "
        "and reproducible methods. The extracted text is coherent and has "
        "ordinary sentence structure across several paragraphs.</p>"
        "<p>The results indicate that the proposed method improves navigation "
        "without introducing obvious OCR damage.</p>"
        "</body></html>"
    )

    decision = assess_ocr_quality_from_html(html)

    assert decision.needs_reocr is False
    assert decision.score > 0.8
    assert decision.reasons == []


def test_ocr_quality_flags_image_only_or_garbage_text() -> None:
    html = (
        "<html><body>"
        '<p><img src="page1.png"></p><p><img src="page2.png"></p>'
        "<p>Abstrac t Chapte r Uroflowrnetry Gra1Jimetry "
        "The second second C TANGET STATE Service Surveyor.</p>"
        "</body></html>"
    )

    decision = assess_ocr_quality_from_html(html)

    assert decision.needs_reocr is True
    assert "too_little_extractable_text_with_images" in decision.reasons
    assert decision.known_ocr_hits >= 4


def test_reocr_queue_deduplicates_and_marks_suffix() -> None:
    tmp_path = _make_temp_dir()
    try:
        source_pdf = tmp_path / "paper.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n")
        decision = assess_ocr_quality_from_html(
            '<html><body><p><img src="1.png"></p><p><img src="2.png"></p></body></html>'
        )

        first = enqueue_reocr_candidate(
            output_dir=tmp_path,
            source_pdf_path=source_pdf,
            alias_base_name="paper",
            artifact_path=tmp_path / "paper" / "paper.html",
            stage_raw_path=tmp_path / "paper" / "_z2m_stages" / "01.en.raw.html",
            decision=decision,
        )
        second = enqueue_reocr_candidate(
            output_dir=tmp_path,
            source_pdf_path=source_pdf,
            alias_base_name="paper",
            artifact_path=tmp_path / "paper" / "paper.html",
            stage_raw_path=tmp_path / "paper" / "_z2m_stages" / "01.en.raw.html",
            decision=decision,
        )

        entries = load_reocr_queue(tmp_path)
        assert first.added is True
        assert second.added is False
        assert len(entries) == 1
        assert entries[0]["reocr_alias_base_name"] == f"paper{REOCR_SUFFIX}"
        assert (tmp_path / "_reocr_pending" / f"paper{REOCR_SUFFIX}.json").is_file()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


class _FakeHtmlRunner:
    def run_batch(self, *, input_dir, output_dir, output_format, **_kwargs):
        assert output_format == "html"
        for pdf_path in sorted(Path(input_dir).glob("*.pdf")):
            article_dir = Path(output_dir) / pdf_path.stem
            article_dir.mkdir(parents=True, exist_ok=True)
            (article_dir / "page1.png").write_bytes(_VALID_TINY_PNG)
            (article_dir / "page2.png").write_bytes(_VALID_TINY_PNG)
            (article_dir / f"{pdf_path.stem}.html").write_text(
                "<html><body>"
                '<p><img src="page1.png"></p><p><img src="page2.png"></p>'
                "<p>Abstrac t Chapte r Uroflowrnetry Gra1Jimetry "
                "The second second C TANGET STATE Service Surveyor.</p>"
                "</body></html>",
                encoding="utf-8",
            )
        return RunResult(command=["fake-marker"], exit_code=0)

    def run_single(self, **_kwargs):
        return RunResult(command=["fake-marker-single"], exit_code=1)


class _FakeMathHtmlRunner:
    def run_batch(self, *, input_dir, output_dir, output_format, **_kwargs):
        assert output_format == "html"
        for pdf_path in sorted(Path(input_dir).glob("*.pdf")):
            article_dir = Path(output_dir) / pdf_path.stem
            article_dir.mkdir(parents=True, exist_ok=True)
            (article_dir / f"{pdf_path.stem}.html").write_text(
                "<html><body>"
                r"<p>Energy \(E=mc^2\) released.</p>"
                '<h2>References</h2><ol><li id="ref-1">Example reference.</li></ol>'
                "</body></html>",
                encoding="utf-8",
            )
        return RunResult(command=["fake-marker"], exit_code=0)

    def run_single(self, **_kwargs):
        return RunResult(command=["fake-marker-single"], exit_code=1)


class _FakeMissingImageRunner:
    def run_batch(self, *, input_dir, output_dir, output_format, **_kwargs):
        assert output_format == "html"
        for pdf_path in sorted(Path(input_dir).glob("*.pdf")):
            article_dir = Path(output_dir) / pdf_path.stem
            article_dir.mkdir(parents=True, exist_ok=True)
            (article_dir / f"{pdf_path.stem}.html").write_text(
                "<html><body>"
                '<img src="figures/missing.png">'
                "<p>This coherent article contains enough ordinary text to pass "
                "the OCR quality heuristic while exercising the independent image "
                "publication gate. The methods and results remain readable.</p>"
                "<p>Additional discussion keeps the document structurally normal "
                "and prevents an unrelated re-OCR decision.</p>"
                "</body></html>",
                encoding="utf-8",
            )
        return RunResult(command=["fake-marker"], exit_code=0)

    def run_single(self, **_kwargs):
        return RunResult(command=["fake-marker-single"], exit_code=1)


def test_pipeline_queues_bad_ocr_html_for_reocr(monkeypatch) -> None:
    tmp_path = _make_temp_dir()
    try:
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
        source_pdf = tmp_path / "bad_scan.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n")
        output_dir = tmp_path / "out"
        logs: list[str] = []

        summary = run_pipeline(
            PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(output_dir),
                export_mode=ExportMode.HTML.value,
                skip_existing=False,
                cleanup_staging=True,
            ),
            _FakeHtmlRunner(),
            logs.append,
            lambda: False,
        )

        queue_path = output_dir / REOCR_QUEUE_NAME
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        entry = queue["entries"][0]

        assert summary.failed_total == 0
        assert summary.html_polish_failed_total == 0
        assert summary.ocr_quality_failed_total == 1
        assert summary.reocr_queued_total == 1
        assert summary.reocr_pending_total == 1
        assert entry["alias_base_name"] == "bad_scan"
        assert entry["reocr_alias_base_name"] == f"bad_scan{REOCR_SUFFIX}"
        assert (output_dir / "_reocr_pending" / f"bad_scan{REOCR_SUFFIX}.json").is_file()
        assert any("OCR quality gate queued for re-OCR" in line for line in logs)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_pipeline_counts_image_integrity_failure_and_skips_polish_stage(monkeypatch) -> None:
    tmp_path = _make_temp_dir()
    try:
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
        source_pdf = tmp_path / "missing_image.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n")
        output_dir = tmp_path / "out"
        logs: list[str] = []

        summary = run_pipeline(
            PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(output_dir),
                export_mode=ExportMode.HTML.value,
                skip_existing=False,
                cleanup_staging=True,
            ),
            _FakeMissingImageRunner(),
            logs.append,
            lambda: False,
        )

        article_dir = output_dir / "missing_image"
        raw_html = article_dir / "missing_image.html"
        polish_stage = article_dir / "_z2m_stages" / "02.en.polish.html"

        assert summary.converted_total == 1
        assert summary.failed_total == 1
        assert summary.html_polish_failed_total == 1
        assert raw_html.is_file()
        assert not polish_stage.exists()
        assert any(
            "HTML image integrity check failed" in line
            for line in logs
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_pipeline_finds_zotero_overlay_by_alias_suffix() -> None:
    tmp_path = _make_temp_dir()
    try:
        overlay_dir = tmp_path / "overlays"
        overlay_dir.mkdir()
        overlay_path = overlay_dir / "cached_82a4cf51.overlays.json"
        overlay_path.write_text('{"summary":{"citations":[]}}\n', encoding="utf-8")

        match = _find_zotero_overlay_path(
            overlay_dir,
            tmp_path / "Very long source title.pdf",
            "Very long source title_82a4cf51",
        )

        assert match == overlay_path
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_pipeline_html_polish_uses_static_katex_and_closes_context(monkeypatch) -> None:
    tmp_path = _make_temp_dir()
    try:
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
        source_pdf = tmp_path / "math_article.pdf"
        source_pdf.write_bytes(b"%PDF-1.4\n")
        overlay_dir = tmp_path / "overlays"
        overlay_dir.mkdir()
        overlay_path = overlay_dir / "math_article.overlays.json"
        overlay_path.write_text('{"summary":{"citations":[]}}\n', encoding="utf-8")
        output_dir = tmp_path / "out"
        logs: list[str] = []
        close_calls: list[bool] = []
        profile_overlay_paths: list[Path | None] = []
        original_close = pipeline_module.close_katex_v8_context

        def close_context() -> None:
            close_calls.append(True)
            original_close()

        def build_profile(_path, **kwargs):
            profile_overlay_paths.append(kwargs.get("zotero_overlay_path"))
            return {"status": "test", "style": "numeric", "confidence": "high"}

        monkeypatch.setattr(pipeline_module, "close_katex_v8_context", close_context)
        monkeypatch.setattr(pipeline_module, "build_citation_profile_from_pdf", build_profile)

        summary = run_pipeline(
            PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(output_dir),
                export_mode=ExportMode.HTML.value,
                skip_existing=False,
                cleanup_staging=True,
                zotero_overlay_dir=str(overlay_dir),
            ),
            _FakeMathHtmlRunner(),
            logs.append,
            lambda: False,
        )

        html_path = output_dir / "math_article" / "math_article.html"
        html = html_path.read_text(encoding="utf-8")

        assert summary.failed_total == 0
        assert summary.converted_total == 1
        assert 'data-z2m-style="katex"' in html
        assert r'data-z2m-tex="\(E=mc^2\)"' in html
        assert profile_overlay_paths == [overlay_path.resolve(strict=False)]
        assert close_calls == [True]
    finally:
        pipeline_module.close_katex_v8_context()
        shutil.rmtree(tmp_path, ignore_errors=True)
