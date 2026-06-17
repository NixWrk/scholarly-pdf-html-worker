from pathlib import Path

from pdf_html_polish.quality_loop.converted_runs import (
    POLISH_STAGE,
    RAW_STAGE,
    assess_polish_html,
    find_converted_stage_pairs,
)


def test_find_converted_stage_pairs_accepts_roots_and_stage_files(tmp_path: Path) -> None:
    stage_dir = tmp_path / "lib" / "ATTACH" / "v1" / "article" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw_path = stage_dir / RAW_STAGE
    polish_path = stage_dir / POLISH_STAGE
    raw_path.write_text("<html>raw</html>", encoding="utf-8")
    polish_path.write_text("<html>polish</html>", encoding="utf-8")

    assert find_converted_stage_pairs([tmp_path]) == [
        (raw_path.resolve(strict=False), polish_path.resolve(strict=False))
    ]
    assert find_converted_stage_pairs([polish_path]) == [
        (raw_path.resolve(strict=False), polish_path.resolve(strict=False))
    ]


def test_assess_polish_html_counts_navigation_and_citation_style_signals() -> None:
    html = """
    <html><body>
      <p id="ref-1">[1] First reference</p>
      <p><sup><a href="#ref-1">1</a></sup> mixed with <a href="#ref-2">[2]</a>.</p>
      <p><a href="?page=4">bad page query</a><a href="#fig-1">missing figure</a></p>
      <p class="z2m-missing-figure-warning">Figure image was not extracted.</p>
    </body></html>
    """

    assessment = assess_polish_html(
        "article",
        html,
        {"status": "ok", "style": "unknown", "confidence": "low"},
    )

    assert assessment["href_counts"]["ref_links"] == 2
    assert assessment["href_counts"]["broken_internal_links"] == 2
    assert assessment["href_counts"]["external_page_query_links"] == 1
    assert assessment["sup_ref_links"] == 1
    assert assessment["bracket_ref_links"] == 1
    assert assessment["mixed_citation_style"] is True
    assert assessment["missing_warning_count"] == 1


def test_assess_polish_html_counts_remaining_same_document_absolute_links() -> None:
    html = """
    <html><body>
      <section id="S1"></section>
      <section id="bib.bib56"></section>
      <p>
        <a href="https://arxiv.org/html/2511.02824v2#S1">Section 1</a>
        <a href="https://arxiv.org/html/2511.02824v2#bib.bib56">[56]</a>
        <a href="https://example.org/html/2511.02824#S1">external fragment</a>
      </p>
    </body></html>
    """

    assessment = assess_polish_html(
        "article",
        html,
        {"status": "ok", "style": "unknown", "confidence": "low"},
    )

    assert assessment["href_counts"]["same_document_absolute_links_remaining"] == 2
