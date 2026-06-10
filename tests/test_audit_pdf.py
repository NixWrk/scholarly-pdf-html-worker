import re
from pathlib import Path
from typing import Any

from zoteropdf2md.quality_loop.audit_pdf import PdfDiagnosticsCache


def test_pdf_diagnostics_cache_caches_text_and_link_summaries(tmp_path: Path) -> None:
    raw_path = tmp_path / "article" / "02.en.raw.html"
    raw_path.parent.mkdir()
    raw_path.write_text("<html></html>", encoding="utf-8")
    pdf_path = raw_path.parent / "00.source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    calls = {"text": 0, "links": 0}

    def extract_text(path: Path) -> tuple[str, str, str | None]:
        calls["text"] += 1
        assert path == pdf_path
        return "fake", "PDF text", None

    def link_summary(path: Path, *, author_year_text_re: re.Pattern[str], sample_limit: int) -> dict[str, Any]:
        calls["links"] += 1
        assert path == pdf_path
        assert author_year_text_re.search("Smith 2020")
        assert sample_limit == 3
        return {"pdf_link_text_status": "fake", "pdf_link_count": 2}

    cache = PdfDiagnosticsCache(
        tmp_path / "cache",
        pdf_source_stage="00.source.pdf",
        author_year_text_re=re.compile(r"\b[A-Z][A-Za-z]+ \d{4}\b"),
        extract_pdf_text_func=extract_text,
        pdf_citation_link_summary_func=link_summary,
    )

    text, summary = cache.load_text(raw_path, None)
    assert text == "PDF text"
    assert summary["pdf_text_cache_status"] == "miss"
    assert calls["text"] == 1

    text, summary = cache.load_text(raw_path, None)
    assert text == "PDF text"
    assert summary["pdf_text_cache_status"] == "hit"
    assert calls["text"] == 1

    links = cache.link_summary(pdf_path, sample_limit=3)
    assert links["pdf_link_cache_status"] == "miss"
    assert calls["links"] == 1

    links = cache.link_summary(pdf_path, sample_limit=3)
    assert links["pdf_link_cache_status"] == "hit"
    assert calls["links"] == 1


def test_pdf_diagnostics_cache_marks_override_without_storing(tmp_path: Path) -> None:
    raw_path = tmp_path / "article" / "02.en.raw.html"
    raw_path.parent.mkdir()
    raw_path.write_text("<html></html>", encoding="utf-8")

    def fail_extract(_path: Path) -> tuple[str, str, str | None]:
        raise AssertionError("override should not call the extractor")

    cache = PdfDiagnosticsCache(
        tmp_path / "cache",
        pdf_source_stage="00.source.pdf",
        author_year_text_re=re.compile("."),
        extract_pdf_text_func=fail_extract,
    )

    text, summary = cache.load_text(raw_path, "override text")

    assert text == "override text"
    assert summary["pdf_text_status"] == "override"
    assert summary["pdf_text_cache_status"] == "override"
