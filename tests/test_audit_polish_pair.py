import re
from pathlib import Path
from typing import Any

from pdf_html_polish.quality_loop.audit_polish_pair import PolishPairAnalysisDeps, analyze_polish_pair


def _pdf_summary(pdf_path: Path, text: str, status: str = "fake") -> dict[str, Any]:
    return {
        "pdf_diagnostics_enabled": True,
        "source_pdf_path": str(pdf_path),
        "source_pdf_present": pdf_path.is_file(),
        "source_pdf_origin": "map",
        "pdf_text_status": status,
        "pdf_text_chars": len(text),
        "pdf_text_error": None,
    }


def _link_summary() -> dict[str, Any]:
    return {
        "pdf_link_text_status": "fake",
        "pdf_link_count": 3,
        "pdf_citation_dest_links": 2,
        "pdf_author_year_link_labels": 1,
        "pdf_citation_link_samples": [{"page": 1, "dest": "cite.1", "text": "Smith 2020"}],
        "pdf_link_text_error": None,
    }


def _deps(observed: dict[str, Any], *, missing_images: list[dict[str, Any]] | None = None) -> PolishPairAnalysisDeps:
    def citation_defects(blocks, *, reference_blocks):
        observed["citation_block_count"] = len(blocks)
        observed["reference_block_count"] = len(reference_blocks)
        return []

    def figure_caption_ux_defects(html, blocks, *, pdf_text=""):
        observed["figure_pdf_text"] = pdf_text
        return []

    def citation_style_consistency_defects(html, blocks, *, pdf_text="", pdf_link_summary=None):
        observed["citation_style_pdf_text"] = pdf_text
        observed["pdf_link_summary"] = pdf_link_summary
        return []

    def pdf_text_layer_defects(pdf_text, html, blocks):
        observed["pdf_text_layer_text"] = pdf_text
        return []

    return PolishPairAnalysisDeps(
        source_pdf_path=lambda raw_path: raw_path.with_name("00.source.pdf"),
        load_pdf_diagnostic_text=lambda raw_path, override, pdf_path: (
            override or "PDF text",
            _pdf_summary(pdf_path or raw_path.with_name("00.source.pdf"), override or "PDF text", "override" if override else "fake"),
        ),
        pdf_citation_link_summary=lambda pdf_path: _link_summary(),
        article_name_from_stage=lambda stage_path: stage_path.parents[1].name,
        frontmatter_defects=lambda raw_blocks, polish_blocks: [],
        citation_defects=citation_defects,
        reference_identity_defects=lambda reference_blocks: [],
        unit_math_defects=lambda raw_html, polish_blocks: [],
        equation_table_defects=lambda polish_blocks: [],
        figure_caption_ux_defects=figure_caption_ux_defects,
        figure_visual_identity_defects=lambda polish_path, polish_html: [],
        image_asset_defects=lambda polish_path, polish_html: [],
        citation_style_consistency_defects=citation_style_consistency_defects,
        manual_blind_spot_defects=lambda polish_html, polish_blocks, *, pdf_text="": [],
        meine_recent_manual_defects=lambda polish_html, polish_blocks, *, pdf_text="": [],
        pdf_text_layer_defects=pdf_text_layer_defects,
        missing_local_images=lambda polish_path, polish_html: missing_images or [],
        ref_link_re=re.compile(r"<a\b[^>]*href=['\"]#ref-"),
        fig_link_re=re.compile(r"<a\b[^>]*href=['\"]#fig-"),
        table_link_re=re.compile(r"<a\b[^>]*href=['\"]#table-"),
        page_link_re=re.compile(r"<a\b[^>]*href=['\"]#page-"),
    )


def test_analyze_polish_pair_builds_summary_and_reference_handoff(tmp_path: Path) -> None:
    stage_dir = tmp_path / "Article sample" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw_path = stage_dir / "01.en.raw.html"
    polish_path = stage_dir / "02.en.polish.html"
    raw_path.write_text("<html><body><p>Raw <img src='raw.png'></p></body></html>", encoding="utf-8")
    polish_path.write_text(
        "<html><head><style>:target{scroll-margin-top:1rem}</style></head><body>"
        "<p><img src='missing.png'>"
        "<a href='#ref-1'>1</a><a href='#fig-1'>Fig. 1</a>"
        "<a href='#table-1'>Table 1</a><a href='#page-2'>2</a>\ufffd</p>"
        "<p id='fig-1'>Figure 1. Caption.</p>"
        "<p id='table-1'>Table 1. Caption.</p>"
        "<p id='ref-1'>Reference.</p>"
        "</body></html>",
        encoding="utf-8",
    )
    observed: dict[str, Any] = {}

    result = analyze_polish_pair(
        raw_path,
        polish_path,
        deps=_deps(observed, missing_images=[{"src": "missing.png"}]),
    )

    summary = result["summary"]
    assert result["article"] == "Article sample"
    assert observed["citation_block_count"] == summary["polish_blocks"]
    assert observed["reference_block_count"] == summary["polish_blocks"]
    assert summary["raw_img_tags"] == 1
    assert summary["polish_img_tags"] == 1
    assert summary["polish_ref_links"] == 1
    assert summary["polish_fig_links"] == 1
    assert summary["polish_table_links"] == 1
    assert summary["polish_page_links"] == 1
    assert summary["polish_fig_ids"] == 1
    assert summary["polish_table_ids"] == 1
    assert summary["polish_has_target_style"] is True
    assert summary["polish_has_scroll_margin"] is True
    assert summary["polish_replacement_chars"] == 1
    assert summary["polish_missing_local_images"] == 1
    assert summary["pdf_text_status"] == "disabled"


def test_analyze_polish_pair_propagates_pdf_diagnostics(tmp_path: Path) -> None:
    stage_dir = tmp_path / "Article sample" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw_path = stage_dir / "01.en.raw.html"
    polish_path = stage_dir / "02.en.polish.html"
    pdf_path = tmp_path / "external.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
    polish_path.write_text("<html><body><p>Polish.</p></body></html>", encoding="utf-8")
    observed: dict[str, Any] = {}

    result = analyze_polish_pair(
        raw_path,
        polish_path,
        deps=_deps(observed),
        enable_pdf_diagnostics=True,
        pdf_text_override="PDF text override",
        pdf_path_override=pdf_path,
    )

    summary = result["summary"]
    assert observed["figure_pdf_text"] == "PDF text override"
    assert observed["citation_style_pdf_text"] == "PDF text override"
    assert observed["pdf_text_layer_text"] == "PDF text override"
    assert observed["pdf_link_summary"]["pdf_link_text_status"] == "fake"
    assert summary["source_pdf_path"] == str(pdf_path)
    assert summary["source_pdf_origin"] == "map"
    assert summary["pdf_text_status"] == "override"
    assert summary["pdf_link_count"] == 3
    assert summary["pdf_link_cache_status"] == "disabled"
