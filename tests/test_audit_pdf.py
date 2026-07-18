import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import pytest

from pdf_html_polish.quality_loop.audit_pdf import PdfDiagnosticsCache, load_pdf_map
from pdf_html_polish.quality_loop.audit_blocks import parse_blocks
from pdf_html_polish.quality_loop.audit_pdf import pdf_text_layer_defects
def _cache_value_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()




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
        return {
            "pdf_link_text_status": "fake",
            "pdf_link_count": 2,
            "pdf_citation_dest_links": 0,
            "pdf_author_year_link_labels": 0,
            "pdf_citation_link_samples": [],
            "pdf_link_text_error": None,
        }

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


def test_pdf_diagnostics_cache_does_not_follow_preplaced_temporary_hardlink(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "article" / "02.en.raw.html"
    raw_path.parent.mkdir()
    raw_path.write_text("<html></html>", encoding="utf-8")
    pdf_path = raw_path.parent / "00.source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    cache = PdfDiagnosticsCache(
        tmp_path / "cache",
        pdf_source_stage="00.source.pdf",
        author_year_text_re=re.compile("."),
        extract_pdf_text_func=lambda _path: ("fake", "PDF text", None),
    )
    key = cache._key(
        pdf_path,
        kind="text",
        extra={
            "extractor": "extract_pdf_text:v1",
            "source_pdf_origin": "stage",
        },
    )
    assert key is not None
    target = cache._path_for_key(key)
    predictable_temporary = target.with_name(
        f"{target.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    outside = tmp_path / "outside.txt"
    outside.write_text("keep-outside", encoding="utf-8")
    os.link(outside, predictable_temporary)

    text, summary = cache.load_text(raw_path, None)

    assert text == "PDF text"
    assert summary["pdf_text_cache_status"] == "miss"
    assert outside.read_text(encoding="utf-8") == "keep-outside"
    assert target.is_file()
    assert target.stat().st_ino != outside.stat().st_ino


def test_pdf_diagnostics_cache_rejects_same_metadata_different_content(tmp_path: Path) -> None:
    raw_path = tmp_path / "article" / "02.en.raw.html"
    raw_path.parent.mkdir()
    raw_path.write_text("<html></html>", encoding="utf-8")
    pdf_path = raw_path.parent / "00.source.pdf"
    original_bytes = b"%PDF-1.4 AAAAA"
    replacement_bytes = b"%PDF-1.4 BBBBB"
    assert len(original_bytes) == len(replacement_bytes)
    pdf_path.write_bytes(original_bytes)
    original_stat = pdf_path.stat()
    calls = {"text": 0, "links": 0}

    def extract_text(path: Path) -> tuple[str, str, str | None]:
        calls["text"] += 1
        return "fake", path.read_bytes().decode("ascii"), None

    def link_summary(
        path: Path,
        *,
        author_year_text_re: re.Pattern[str],
        sample_limit: int,
    ) -> dict[str, Any]:
        calls["links"] += 1
        assert author_year_text_re.search("Smith 2020")
        assert sample_limit == 3
        return {
            "pdf_link_text_status": "fake",
            "pdf_link_count": 1,
            "pdf_citation_dest_links": 1,
            "pdf_author_year_link_labels": 0,
            "pdf_citation_link_samples": [
                {"page": 1, "dest": "cite.1", "text": path.read_bytes().decode("ascii")}
            ],
            "pdf_link_text_error": None,
        }

    cache = PdfDiagnosticsCache(
        tmp_path / "cache",
        pdf_source_stage="00.source.pdf",
        author_year_text_re=re.compile(r"\b[A-Z][A-Za-z]+ \d{4}\b"),
        extract_pdf_text_func=extract_text,
        pdf_citation_link_summary_func=link_summary,
    )

    first_text, first_summary = cache.load_text(raw_path, None)
    first_links = cache.link_summary(pdf_path, sample_limit=3)
    assert first_text == original_bytes.decode("ascii")
    assert first_summary["pdf_text_cache_status"] == "miss"
    assert first_links["pdf_link_cache_status"] == "miss"

    pdf_path.write_bytes(replacement_bytes)
    os.utime(
        pdf_path,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )
    replacement_stat = pdf_path.stat()
    assert replacement_stat.st_size == original_stat.st_size
    assert replacement_stat.st_mtime_ns == original_stat.st_mtime_ns

    second_text, second_summary = cache.load_text(raw_path, None)
    second_links = cache.link_summary(pdf_path, sample_limit=3)

    replacement_sha = hashlib.sha256(replacement_bytes).hexdigest()
    assert second_text == replacement_bytes.decode("ascii")
    assert (
        second_links["pdf_citation_link_samples"][0]["text"]
        == replacement_bytes.decode("ascii")
    )
    assert second_summary["pdf_text_cache_status"] == "miss"
    assert second_links["pdf_link_cache_status"] == "miss"
    assert second_summary["source_pdf_bytes"] == len(replacement_bytes)
    assert second_summary["source_pdf_sha256"] == replacement_sha
    assert second_links["source_pdf_bytes"] == len(replacement_bytes)
    assert second_links["source_pdf_sha256"] == replacement_sha
    assert calls == {"text": 2, "links": 2}


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


def test_pdf_diagnostics_cache_ignores_malformed_cache_record(tmp_path: Path) -> None:
    raw_path = tmp_path / "article" / "02.en.raw.html"
    raw_path.parent.mkdir()
    raw_path.write_text("<html></html>", encoding="utf-8")
    pdf_path = raw_path.parent / "00.source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    calls = 0

    def extract_text(_path: Path) -> tuple[str, str, str | None]:
        nonlocal calls
        calls += 1
        return "fake", f"PDF text {calls}", None

    cache_dir = tmp_path / "cache"
    cache = PdfDiagnosticsCache(
        cache_dir,
        pdf_source_stage="00.source.pdf",
        author_year_text_re=re.compile("."),
        extract_pdf_text_func=extract_text,
    )
    first_text, first_summary = cache.load_text(raw_path, None)
    assert first_text == "PDF text 1"
    assert first_summary["pdf_text_cache_status"] == "miss"
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    cache_files[0].write_text("[]\n", encoding="utf-8")

    second_text, second_summary = cache.load_text(raw_path, None)

    assert second_text == "PDF text 2"
    assert second_summary["pdf_text_cache_status"] == "miss"
    assert calls == 2

    cache_record = json.loads(cache_files[0].read_text(encoding="utf-8"))
    cache_record["value"]["text"] = "forged without matching digest"
    cache_files[0].write_text(json.dumps(cache_record), encoding="utf-8")
    third_text, third_summary = cache.load_text(raw_path, None)

    assert third_text == "PDF text 3"
    assert third_summary["pdf_text_cache_status"] == "miss"
    assert calls == 3

    cache_record = json.loads(cache_files[0].read_text(encoding="utf-8"))
    cache_record["value"]["summary"]["pdf_text_chars"] = 999
    cache_record["value_sha256"] = _cache_value_sha256(cache_record["value"])
    cache_files[0].write_text(json.dumps(cache_record), encoding="utf-8")
    fourth_text, fourth_summary = cache.load_text(raw_path, None)

    assert fourth_text == "PDF text 4"
    assert fourth_summary["pdf_text_cache_status"] == "miss"
    assert calls == 4


def test_pdf_diagnostics_cache_rejects_semantically_invalid_link_record(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "article" / "00.source.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    calls = 0

    def link_summary(
        _path: Path,
        *,
        author_year_text_re: re.Pattern[str],
        sample_limit: int,
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        assert author_year_text_re.search("Smith 2020")
        assert sample_limit == 3
        return {
            "pdf_link_text_status": "fake",
            "pdf_link_count": 1,
            "pdf_citation_dest_links": 1,
            "pdf_author_year_link_labels": 1,
            "pdf_citation_link_samples": [
                {"page": 1, "dest": "cite.1", "text": "Smith 2020"}
            ],
            "pdf_link_text_error": None,
        }

    cache_dir = tmp_path / "cache"
    cache = PdfDiagnosticsCache(
        cache_dir,
        pdf_source_stage="00.source.pdf",
        author_year_text_re=re.compile(r"\b[A-Z][A-Za-z]+ \d{4}\b"),
        pdf_citation_link_summary_func=link_summary,
    )
    first_summary = cache.link_summary(pdf_path, sample_limit=3)
    assert first_summary["pdf_link_cache_status"] == "miss"
    assert calls == 1

    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    cache_record = json.loads(cache_files[0].read_text(encoding="utf-8"))
    cache_record["value"]["pdf_citation_dest_links"] = 2
    cache_record["value_sha256"] = _cache_value_sha256(cache_record["value"])
    cache_files[0].write_text(json.dumps(cache_record), encoding="utf-8")

    second_summary = cache.link_summary(pdf_path, sample_limit=3)

    assert second_summary["pdf_link_cache_status"] == "miss"
    assert calls == 2

def test_pdf_diagnostics_cache_separates_stage_and_map_origin(tmp_path: Path) -> None:
    raw_path = tmp_path / "article" / "02.en.raw.html"
    raw_path.parent.mkdir()
    raw_path.write_text("<html></html>", encoding="utf-8")
    pdf_path = raw_path.parent / "00.source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    calls = 0

    def extract_text(_path: Path) -> tuple[str, str, str | None]:
        nonlocal calls
        calls += 1
        return "fake", "PDF text", None

    cache = PdfDiagnosticsCache(
        tmp_path / "cache",
        pdf_source_stage="00.source.pdf",
        author_year_text_re=re.compile("."),
        extract_pdf_text_func=extract_text,
    )
    _, stage_summary = cache.load_text(raw_path, None)
    _, map_summary = cache.load_text(
        raw_path,
        None,
        pdf_path_override=pdf_path,
    )

    assert stage_summary["source_pdf_origin"] == "stage"
    assert stage_summary["pdf_text_cache_status"] == "miss"
    assert map_summary["source_pdf_origin"] == "map"
    assert map_summary["pdf_text_cache_status"] == "miss"
    assert calls == 2



@pytest.mark.parametrize(
    "payload",
    [
        '{"Doc":"first.pdf","Doc":"second.pdf"}',
        (
            '[{"article":"Doc","pdf_path":"first.pdf"},'
            '{"article":"Doc","pdf_path":"second.pdf"}]'
        ),
    ],
)
def test_load_pdf_map_rejects_duplicate_article_identity(
    tmp_path: Path,
    payload: str,
) -> None:
    map_path = tmp_path / "pdf-map.json"
    map_path.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate_pdf_map_article"):
        load_pdf_map(map_path)


def test_pdf_text_layer_defects_reports_interleaved_terminal_sections() -> None:
    pdf_text = "Funding\nSupplementary material\nReferences"
    polish_html = "<h2>Funding</h2><h2>References</h2><h2>Supplementary material</h2>"
    polish_blocks = parse_blocks(polish_html)

    defects = pdf_text_layer_defects(
        pdf_text,
        polish_html,
        polish_blocks,
        references_heading_re=re.compile(r"^references$", re.IGNORECASE),
        stage="02.en.polish.html",
    )

    assert [defect.id for defect in defects] == ["P24"]
    assert defects[0].first_broken_stage == "02.en.polish.html"
    assert defects[0].extra["pdf_positions"]["funding"] < defects[0].extra["pdf_positions"]["references"]
