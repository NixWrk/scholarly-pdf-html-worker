from pathlib import Path
from types import SimpleNamespace

from zoteropdf2md.quality_loop.pdf_reference_recovery import (
    enrich_profile_with_pdf_reference_entries_if_needed,
    pdf_reference_recovery_numbers,
)


def test_pdf_reference_recovery_numbers_prefers_reference_gaps() -> None:
    html = (
        "<html><body><h4>References</h4><ol>"
        '<li id="ref-1">One.</li>'
        '<li id="ref-4">Four.</li>'
        "</ol></body></html>"
    )

    assert pdf_reference_recovery_numbers(html) == ([2, 3], "gap")


def test_pdf_reference_recovery_numbers_skip_body_candidates_when_refs_exist() -> None:
    html = (
        "<html><body>"
        "<p>Prior work 1,2.</p>"
        "<h2>References</h2><ul>"
        '<li id="ref-1">Alpha A. First source.</li>'
        '<li id="ref-2">Beta B. Second source.</li>'
        "</ul></body></html>"
    )

    assert pdf_reference_recovery_numbers(html) == ([], "")


def test_enrich_profile_loads_matching_pdf_reference_entries(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    cache: dict[str, list[dict[str, object]]] = {}

    updated, count, source = enrich_profile_with_pdf_reference_entries_if_needed(
        {"status": "ok"},
        "<p>Prior work 1,2.</p>",
        tmp_path / "source",
        "article_a",
        {},
        cache,
        article_source_pdf_candidates=lambda *_args: [
            {"path": str(pdf_path), "exists": True, "source": "test"}
        ],
        extract_reference_entries=lambda _path: [
            SimpleNamespace(page=10, number=1, text="Alpha A. First source."),
            SimpleNamespace(page=11, number=2, text="Beta B. Second source."),
        ],
    )

    assert count == 2
    assert source == str(pdf_path.resolve(strict=False))
    assert updated["reference_entries_status"] == "loaded_from_source_pdf_citation_recovery"
    assert updated["reference_entries_recovery_matched_numbers"] == [1, 2]
    assert cache[source][0]["number"] == 1
