#!/usr/bin/env python
"""Audit EN raw -> EN polish stage pairs without running Marker."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.html_stages import HTML_STAGE_DIR_NAME, POLISH_STAGE_NAME, RAW_STAGE_NAME
from pdf_html_polish.quality_loop.audit_blocks import (
    Block,
    Defect,
    attrs as _attrs,
    line_at as _line_at,
    line_at_from_starts as _line_at_from_starts,
    line_starts as _line_starts,
    parse_blocks as _parse_blocks,
    parse_overlapping_blocks as _parse_overlapping_blocks,
    snippet as _snippet,
    strip_tags as _strip_tags,
)
from pdf_html_polish.quality_loop.audit_citation_style import (
    REF_ANCHOR_BODY_RE,
    REF_LINK_RE,
    citation_style_consistency_defects as _citation_style_consistency_defects_base,
)
from pdf_html_polish.quality_loop.audit_citations import (
    CitationDefectDeps,
    citation_defects as _citation_defects_base,
)
from pdf_html_polish.quality_loop.audit_images import (
    figure_visual_identity_defects as _figure_visual_identity_defects_base,
    image_asset_defects as _image_asset_defects_base,
    missing_local_images as _missing_local_images,
)
from pdf_html_polish.quality_loop.audit_frontmatter import (
    FRONTMATTER_OCR_RE,
    block_looks_like_frontmatter_affiliation_table as _block_looks_like_frontmatter_affiliation_table,
    frontmatter_defects as _frontmatter_defects,
)
from pdf_html_polish.quality_loop.audit_figure_caption_ux import (
    BIORENDER_CAPTION_SPLIT_RE,
    BIORENDER_CAPTION_URL_RE,
    CAPTION_INTRUSION_RE,
    CAPTION_TEX_RESIDUE_RE,
    FIGURE_CAPTION_NODE_RE,
    MULTIPANEL_FIG_REF_RE,
    PAGE_FURNITURE_CONTINUATION_RE,
    TABLE_CAPTION_RE,
    TABLE_CAPTION_NODE_RE,
    figure_caption_number_from_caption_node as _figure_caption_number_from_caption_node,
    figure_caption_ux_defects as _figure_caption_ux_defects_base,
    looks_like_equation_continuation as _looks_like_equation_continuation,
    looks_like_figure_caption as _looks_like_figure_caption,
    looks_like_float_note as _looks_like_float_note,
    looks_like_float_or_caption as _looks_like_float_or_caption,
    is_supplementary_figure_block as _is_supplementary_figure_block,
)
from pdf_html_polish.quality_loop.audit_float_gap import (
    source_pdf_text_confirms_float_gap as _source_pdf_text_confirms_float_gap,
)
from pdf_html_polish.quality_loop.audit_reference_identity import (
    DOI_ONLY_METADATA_RE,
    EMBEDDED_REF_BOUNDARY_RE,
    LOCAL_ABSTRACT_SECTION_HEADING_RE,
    NUMERIC_VALUE_ROW_RE,
    REFERENCES_HEADING_RE,
    REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE,
    REF_DUP_BRACKET_PREFIX_RE,
    REF_ID_RE,
    VISIBLE_REF_NUM_RE,
    is_references_block as _is_references_block,
    looks_like_local_abstract_reference_block as _looks_like_local_abstract_reference_block,
    numbered_reference_block_is_likely_non_bibliographic as _numbered_reference_block_is_likely_non_bibliographic,
    reference_identity_defects as _reference_identity_defects,
)
from pdf_html_polish.quality_loop.audit_manual_patterns import (
    ends_like_sentence_fragment as _ends_like_sentence_fragment,
    page_link_semantic_kind as _page_link_semantic_kind,
    starts_like_sentence_continuation as _starts_like_sentence_continuation,
)
from pdf_html_polish.quality_loop.audit_manual_recent import (
    ManualBlindSpotDeps,
    MeineRecentLinkDeps,
    MeineRecentTextDeps,
    block_is_float_or_table_context as _block_is_float_or_table_context,
    build_meine_recent_link_deps as _build_meine_recent_link_deps,
    build_meine_recent_text_deps as _build_meine_recent_text_deps,
    classify_missing_figure_warning as _classify_missing_figure_warning,
    manual_blind_spot_defects as _manual_blind_spot_defects_base,
    meine_recent_link_structure_defects as _meine_recent_link_structure_defects_base,
    meine_recent_text_ocr_defects as _meine_recent_text_ocr_defects_base,
    nearby_image_offsets as _nearby_image_offsets,
    non_reference_body_blocks as _non_reference_body_blocks,
)
from pdf_html_polish.quality_loop.audit_math_units import (
    DEGREE_DEFECT_RE,
    DISPLAY_MATH_OCR_RE,
    EQUATION_ABSORB_RE,
    INLINE_TEX_RE,
    JOINED_PROSE_TOKEN_RE,
    LINKED_UNIT_EXP_DEFECT_RE,
    MATH_TAG_WITH_CITATION_RE,
    RESIDUAL_UNIT_TEX_RE,
    UNIT_FLATTEN_RE,
    equation_table_defects as _equation_table_defects,
    inline_tex_contains_citation_bracket as _inline_tex_contains_citation_bracket,
    unit_math_defects as _unit_math_defects,
    unit_match_is_repaired_in_raw as _unit_match_is_repaired_in_raw,
)
from pdf_html_polish.quality_loop.audit_report import (
    add_corpus_hit_counts as _add_corpus_hit_counts,
    assemble_report,
    corpus_totals as _corpus_totals,
    defect_quality_counted as _defect_quality_counted,
    find_stage_pairs,
    non_quality_corpus_hit_counts as _non_quality_corpus_hit_counts,
    observed_corpus_hit_counts as _observed_corpus_hit_counts,
    write_json_report as _write_json_report,
)
from pdf_html_polish.quality_loop.audit_pdf import (
    article_name_from_stage as _article_name_from_stage,
    extract_pdf_text as _extract_pdf_text,
    first_path_value as _first_path_value,
    load_pdf_diagnostic_text,
    load_pdf_map as _load_pdf_map,
    PdfDiagnosticsCache as _PackagePdfDiagnosticsCache,
    pdf_citation_link_summary,
    pdf_text_layer_defects as _pdf_text_layer_defects_impl,
    pdf_path_from_map_record as _pdf_path_from_map_record,
    section_order_pdf_defects as _section_order_pdf_defects_impl,
    source_pdf_path,
)
from pdf_html_polish.quality_loop.audit_polish_pair import (
    PolishPairAnalysisDeps,
    analyze_polish_pair as _analyze_polish_pair_base,
)
from pdf_html_polish.quality_loop.audit_polish_report import (
    PolishAuditReportDeps,
    build_polish_report as _build_polish_report_base,
    merge_targeted_polish_report as _merge_targeted_report_base,
    print_polish_report_summary as _print_summary,
)
from pdf_html_polish.quality_loop.audit_p04 import unlinked_citation_range_kind as _unlinked_citation_range_kind_base
from pdf_html_polish.quality_loop.audit_p35 import replacement_char_defects as _replacement_char_defects
from pdf_html_polish.quality_loop.audit_p62 import (
    has_nearby_image as _has_nearby_image,
    has_nearby_missing_figure_warning as _has_nearby_missing_figure_warning,
    is_handled_missing_figure_block as _is_handled_missing_figure_block,
)


RAW_STAGE = RAW_STAGE_NAME
POLISH_STAGE = POLISH_STAGE_NAME
PDF_SOURCE_STAGE = "00.source.pdf"

FIG_LINK_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*['\"]#fig-([^'\"]+)['\"][^>]*>", re.IGNORECASE)
TABLE_LINK_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*['\"]#table-([^'\"]+)['\"][^>]*>", re.IGNORECASE)
PAGE_LINK_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#page-(?P<target>[^'\"]+)['\"][^>]*>"
    r"(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
ANCHOR_BODY_RE = re.compile(r"<a\b[^>]*>(?P<body>.*?)</a>", re.IGNORECASE | re.DOTALL)
DOUBLE_CLOSE_ANCHOR_RE = re.compile(r"</a>\s*</a>", re.IGNORECASE)
URL_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"](?:https?://|www\.)[^'\"]+['\"][^>]*>.*?</a>",
    re.IGNORECASE | re.DOTALL,
)
MALFORMED_URL_ANCHOR_BODY_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"](?:https?://|www\.)[^'\"]+['\"][^>]*>"
    r"\s*(?:(?:hps|htps|ttps)://|https?://\s+|\d+www\.|"
    r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+/\s+"
    r"[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)[\s\S]{0,300}?</a>|"
    r"<a\b[^>]*\bhref\s*=\s*(?P<split_quote>['\"])(?P<split_href>https?://[^'\"]+)(?P=split_quote)[^>]*>"
    r"\s*\(?https?://[^<]{1,120}/\s*</a>\s*"
    r"<a\b[^>]*\bhref\s*=\s*(?P=split_quote)(?P=split_href)(?P=split_quote)[^>]*>"
    r"\s*[A-Za-z0-9][^<]{0,120}</a>",
    re.IGNORECASE | re.DOTALL,
)
BROKEN_URL_TEXT_RE = re.compile(
    r"\b(?:hps|htps|ttps)://\S+|"
    r"\bhttps?://\s+|"
    r"\bhttps?://\S+\s+\d+www\.|"
    r"\b\d+www\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|"
    r"\bhttps?://(?:dx\.)?doi\.org/\d+\.\d+/\s+[A-Za-z0-9]|"
    r"\bhttps?://doi\.org/10\s+\.\s+\d+|"
    r"\bhttps?://\S+/(?:wp|news-room/north|contents/part1/ports-and|ports-and-container)\s+[A-Za-z0-9]|"
    r"\bhttps?://\S+/cgi/pt\?\s+[A-Za-z0-9]|"
    r"\bhttps?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+/\s+"
    r"(?!https?://|www\.)"
    r"(?=[A-Za-z0-9._~:/?#\[\]@!$&'*+,;=%-]*[A-Za-z._~:/?#\[\]@!$&'*+,;=%-])"
    r"[A-Za-z0-9._~:/?#\[\]@!$&'*+,;=%-]+|"
    r"\bhttps?://\S+\.(?:h\s+tml|xht\s+ml)\b|"
    r"\btouching-\s+the-prado\b|"
    r"\bdoi\.org/\s+10\.",
    re.IGNORECASE,
)
LOWERCASE_REF_GLUE_RE = re.compile(r"^[a-z][\s\u00a0]*\d{1,4}(?:[\s,\-\u2013\u2014\d.);]*)?$")
BOX_UNIT_RE = re.compile(
    r"<div\b(?=[^>]*\bz2m-box-unit\b)[^>]*>(?P<body>.*?)</div>",
    re.IGNORECASE | re.DOTALL,
)
FIGURE_UNIT_RE = re.compile(
    r"<div\b(?=[^>]*\bz2m-figure-unit\b)(?=[^>]*\bid\s*=\s*['\"](?P<id>fig-[^'\"]+)['\"])[^>]*>"
    r"(?P<body>.*?)</div>",
    re.IGNORECASE | re.DOTALL,
)
IMMEDIATE_EXTERNAL_FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:<p\b[^>]*>(?:(?!</p>)[\s\S])*<img\b(?:(?!</p>)[\s\S])*</p>\s*)?"
    r"<p\b[^>]*\bz2m-figure-caption\b[^>]*>(?P<body>.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)
TABLE_DOI_APPEND_RE = re.compile(
    r"https?://doi\.org/10\.[^\s<]+\.t\d+\s+"
    r"(?P<tail>(?:[a-z]|\(?[a-z])[\s\S]{20,220})",
    re.IGNORECASE,
)
AUTHOR_YEAR_TEXT_RE = re.compile(
    r"\b[A-Z][A-Za-z'вЂ™.-]+(?:\s+et\s+al\.)?(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
def _source_pdf_path(raw_path: Path) -> Path:
    return source_pdf_path(raw_path, pdf_source_stage=PDF_SOURCE_STAGE)


def _pdf_citation_link_summary(pdf_path: Path, *, sample_limit: int = 12) -> dict[str, Any]:
    return pdf_citation_link_summary(
        pdf_path,
        author_year_text_re=AUTHOR_YEAR_TEXT_RE,
        sample_limit=sample_limit,
    )


def _load_pdf_diagnostic_text(
    raw_path: Path,
    pdf_text_override: str | None,
    pdf_path_override: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    return load_pdf_diagnostic_text(
        raw_path,
        pdf_text_override,
        pdf_source_stage=PDF_SOURCE_STAGE,
        pdf_path_override=pdf_path_override,
        extract_pdf_text_func=_extract_pdf_text,
    )


class PdfDiagnosticsCache(_PackagePdfDiagnosticsCache):
    def __init__(self, cache_dir: Path) -> None:
        def link_summary_adapter(
            pdf_path: Path,
            *,
            author_year_text_re: re.Pattern[str],
            sample_limit: int,
        ) -> dict[str, Any]:
            del author_year_text_re
            return _pdf_citation_link_summary(pdf_path, sample_limit=sample_limit)

        super().__init__(
            cache_dir,
            pdf_source_stage=PDF_SOURCE_STAGE,
            extract_pdf_text_func=_extract_pdf_text,
            pdf_citation_link_summary_func=link_summary_adapter,
            author_year_text_re=AUTHOR_YEAR_TEXT_RE,
            author_year_cache_key="AUTHOR_YEAR_TEXT_RE:v1",
        )


def _unlinked_citation_range_kind(block: Block) -> str:
    return _unlinked_citation_range_kind_base(
        block,
        looks_like_float_or_caption=_looks_like_float_or_caption,
        block_looks_like_frontmatter_affiliation_table=_block_looks_like_frontmatter_affiliation_table,
    )


def _citation_defects(polish_blocks: list[Block], *, reference_blocks: list[Block] | None = None) -> list[Defect]:
    return _citation_defects_base(
        polish_blocks,
        reference_blocks=reference_blocks,
        deps=CitationDefectDeps(unlinked_citation_range_kind=_unlinked_citation_range_kind),
        polish_stage=POLISH_STAGE,
    )


def _figure_caption_ux_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    has_internal_links = bool(REF_LINK_RE.search(polish_html) or FIG_LINK_RE.search(polish_html) or TABLE_LINK_RE.search(polish_html))
    return _figure_caption_ux_defects_base(
        polish_html,
        polish_blocks,
        pdf_text=pdf_text,
        has_internal_links=has_internal_links,
        looks_like_figure_caption=_looks_like_figure_caption,
        is_supplementary_figure_block=_is_supplementary_figure_block,
        is_handled_missing_figure_block=_is_handled_missing_figure_block,
        has_nearby_image=_has_nearby_image,
        has_nearby_missing_figure_warning=_has_nearby_missing_figure_warning,
        source_pdf_text_confirms_float_gap=_source_pdf_text_confirms_float_gap,
        table_caption_re=TABLE_CAPTION_RE,
        references_heading_re=REFERENCES_HEADING_RE,
        polish_stage=POLISH_STAGE,
    )


def _image_asset_defects(polish_path: Path, polish_html: str) -> list[Defect]:
    return _image_asset_defects_base(polish_path, polish_html, stage=POLISH_STAGE)


def _figure_visual_identity_defects(polish_path: Path, polish_html: str) -> list[Defect]:
    return _figure_visual_identity_defects_base(
        polish_path,
        polish_html,
        stage=POLISH_STAGE,
        figure_unit_re=FIGURE_UNIT_RE,
        figure_caption_node_re=FIGURE_CAPTION_NODE_RE,
        figure_caption_number_from_caption_node=_figure_caption_number_from_caption_node,
    )


def _citation_style_consistency_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
    pdf_link_summary: dict[str, Any] | None = None,
) -> list[Defect]:
    return _citation_style_consistency_defects_base(
        polish_html,
        polish_blocks,
        pdf_text=pdf_text,
        pdf_link_summary=pdf_link_summary,
        stage=POLISH_STAGE,
        non_reference_body_blocks=_non_reference_body_blocks,
        block_is_float_or_table_context=_block_is_float_or_table_context,
        ref_anchor_body_re=REF_ANCHOR_BODY_RE,
    )


def _manual_blind_spot_deps() -> ManualBlindSpotDeps:
    return ManualBlindSpotDeps(
        page_link_re=PAGE_LINK_RE,
        anchor_body_re=ANCHOR_BODY_RE,
        double_close_anchor_re=DOUBLE_CLOSE_ANCHOR_RE,
        url_anchor_re=URL_ANCHOR_RE,
        malformed_url_anchor_body_re=MALFORMED_URL_ANCHOR_BODY_RE,
        broken_url_text_re=BROKEN_URL_TEXT_RE,
        references_heading_re=REFERENCES_HEADING_RE,
        ref_anchor_body_re=REF_ANCHOR_BODY_RE,
        lowercase_ref_glue_re=LOWERCASE_REF_GLUE_RE,
        box_unit_re=BOX_UNIT_RE,
        figure_unit_re=FIGURE_UNIT_RE,
        immediate_external_figure_caption_re=IMMEDIATE_EXTERNAL_FIGURE_CAPTION_RE,
        table_caption_re=TABLE_CAPTION_RE,
        table_doi_append_re=TABLE_DOI_APPEND_RE,
        page_link_semantic_kind=_page_link_semantic_kind,
        looks_like_figure_caption=_looks_like_figure_caption,
        ends_like_sentence_fragment=_ends_like_sentence_fragment,
        looks_like_float_or_caption=_looks_like_float_or_caption,
        looks_like_float_note=_looks_like_float_note,
        looks_like_equation_continuation=_looks_like_equation_continuation,
        starts_like_sentence_continuation=_starts_like_sentence_continuation,
        source_pdf_text_confirms_float_gap=_source_pdf_text_confirms_float_gap,
    )


def _manual_blind_spot_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    return _manual_blind_spot_defects_base(
        polish_html,
        polish_blocks,
        deps=_manual_blind_spot_deps(),
        pdf_text=pdf_text,
        polish_stage=POLISH_STAGE,
    )


def _meine_recent_link_structure_deps() -> MeineRecentLinkDeps:
    return _build_meine_recent_link_deps(
        author_year_text_re=AUTHOR_YEAR_TEXT_RE,
        page_link_re=PAGE_LINK_RE,
        figure_unit_re=FIGURE_UNIT_RE,
    )


def _meine_recent_text_ocr_deps() -> MeineRecentTextDeps:
    return _build_meine_recent_text_deps()


def _meine_recent_manual_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    defects: list[Defect] = []
    defects.extend(
        _meine_recent_link_structure_defects_base(
            polish_html,
            polish_blocks,
            deps=_meine_recent_link_structure_deps(),
            pdf_text=pdf_text,
            polish_stage=POLISH_STAGE,
            raw_stage=RAW_STAGE,
        )
    )
    defects.extend(
        _meine_recent_text_ocr_defects_base(
            polish_html,
            polish_blocks,
            deps=_meine_recent_text_ocr_deps(),
            pdf_text=pdf_text,
            polish_stage=POLISH_STAGE,
        )
    )
    return defects


def _section_order_pdf_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
) -> list[Defect]:
    return _section_order_pdf_defects_impl(
        pdf_text,
        polish_html,
        polish_blocks,
        references_heading_re=REFERENCES_HEADING_RE,
        stage=POLISH_STAGE,
    )


def _pdf_text_layer_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
) -> list[Defect]:
    return _pdf_text_layer_defects_impl(
        pdf_text,
        polish_html,
        polish_blocks,
        references_heading_re=REFERENCES_HEADING_RE,
        stage=POLISH_STAGE,
    )


def _polish_pair_analysis_deps() -> PolishPairAnalysisDeps:
    return PolishPairAnalysisDeps(
        source_pdf_path=_source_pdf_path,
        load_pdf_diagnostic_text=_load_pdf_diagnostic_text,
        pdf_citation_link_summary=_pdf_citation_link_summary,
        article_name_from_stage=_article_name_from_stage,
        frontmatter_defects=_frontmatter_defects,
        citation_defects=_citation_defects,
        reference_identity_defects=_reference_identity_defects,
        unit_math_defects=_unit_math_defects,
        equation_table_defects=_equation_table_defects,
        figure_caption_ux_defects=_figure_caption_ux_defects,
        figure_visual_identity_defects=_figure_visual_identity_defects,
        image_asset_defects=_image_asset_defects,
        citation_style_consistency_defects=_citation_style_consistency_defects,
        manual_blind_spot_defects=_manual_blind_spot_defects,
        meine_recent_manual_defects=_meine_recent_manual_defects,
        pdf_text_layer_defects=_pdf_text_layer_defects,
        missing_local_images=_missing_local_images,
        ref_link_re=REF_LINK_RE,
        fig_link_re=FIG_LINK_RE,
        table_link_re=TABLE_LINK_RE,
        page_link_re=PAGE_LINK_RE,
    )


def analyze_pair(
    raw_path: Path,
    polish_path: Path,
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_text_override: str | None = None,
    pdf_path_override: Path | None = None,
    pdf_diagnostics_cache: PdfDiagnosticsCache | None = None,
) -> dict[str, Any]:
    return _analyze_polish_pair_base(
        raw_path,
        polish_path,
        deps=_polish_pair_analysis_deps(),
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_text_override=pdf_text_override,
        pdf_path_override=pdf_path_override,
        pdf_diagnostics_cache=pdf_diagnostics_cache,
    )


def find_pairs(roots: Iterable[Path]) -> list[tuple[Path, Path]]:
    return find_stage_pairs(roots, raw_stage=RAW_STAGE, polish_stage=POLISH_STAGE)


def _assemble_report(
    roots: list[Path],
    articles: list[dict[str, Any]],
    defect_counts: dict[str, int],
    *,
    audit_status: str,
    total_pair_count: int,
) -> dict[str, Any]:
    return assemble_report(
        roots,
        articles,
        defect_counts,
        raw_stage=RAW_STAGE,
        polish_stage=POLISH_STAGE,
        audit_status=audit_status,
        total_pair_count=total_pair_count,
    )


def _polish_audit_report_deps() -> PolishAuditReportDeps:
    return PolishAuditReportDeps(
        find_pairs=find_pairs,
        analyze_pair=analyze_pair,
        add_corpus_hit_counts=_add_corpus_hit_counts,
        assemble_report=_assemble_report,
        write_json_report=_write_json_report,
        article_name_from_stage=_article_name_from_stage,
        pdf_diagnostics_cache_factory=PdfDiagnosticsCache,
    )


def build_report(
    roots: list[Path],
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_map: dict[str, Path] | None = None,
    progress_out: Path | None = None,
    progress_write_every: int = 10,
    jobs: int = 1,
    pdf_diagnostics_cache_dir: Path | None = None,
) -> dict[str, Any]:
    return _build_polish_report_base(
        roots,
        deps=_polish_audit_report_deps(),
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map=pdf_map,
        progress_out=progress_out,
        progress_write_every=progress_write_every,
        jobs=jobs,
        pdf_diagnostics_cache_dir=pdf_diagnostics_cache_dir,
    )


def merge_targeted_report(
    previous_report: dict[str, Any],
    targeted_report: dict[str, Any],
    *,
    previous_report_path: Path | None = None,
    allow_new_articles: bool = False,
) -> dict[str, Any]:
    return _merge_targeted_report_base(
        previous_report,
        targeted_report,
        deps=_polish_audit_report_deps(),
        previous_report_path=previous_report_path,
        allow_new_articles=allow_new_articles,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="Root directories, 01.en.raw.html files, or 02.en.polish.html files to audit.",
    )
    parser.add_argument("--out", type=Path, help="Optional JSON report path.")
    parser.add_argument(
        "--progress-write-every",
        type=int,
        default=10,
        help="When --out is set, atomically refresh the JSON report after this many audited pairs.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with status 1 when an error-severity defect is found.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with status 1 when any warning/error defect is found.",
    )
    parser.add_argument(
        "--pdf-diagnostics",
        action="store_true",
        help=(
            f"Use {PDF_SOURCE_STAGE} beside raw stages, when available, as an optional text-layer signal "
            "for low-confidence ordering diagnostics."
        ),
    )
    parser.add_argument(
        "--pdf-map",
        type=Path,
        help=(
            "Optional JSON map from article id to external PDF path. Accepts a plain object, "
            "a list of {article,pdf_path} records, or Zotero candidate records with exact/fuzzy matches."
        ),
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel article workers for audit analysis. Defaults to 1.",
    )
    parser.add_argument(
        "--merge-previous-report",
        type=Path,
        help=(
            "Merge this targeted audit into an existing full audit report. The roots are treated as "
            "the changed subset, unchanged articles are reused, and corpus summaries are recomputed."
        ),
    )
    parser.add_argument(
        "--pdf-diagnostics-cache-dir",
        type=Path,
        help="Optional directory cache for PDF text/link diagnostics keyed by path, size, and mtime.",
    )
    parser.add_argument(
        "--allow-new-target-articles",
        action="store_true",
        help="Allow targeted merge to add articles that were not present in the previous report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pdf_map = _load_pdf_map(args.pdf_map) if args.pdf_map is not None else None
    previous_report: dict[str, Any] | None = None
    if args.merge_previous_report is not None:
        previous_report = json.loads(args.merge_previous_report.read_text(encoding="utf-8"))
    report = build_report(
        args.roots,
        enable_pdf_diagnostics=args.pdf_diagnostics,
        pdf_map=pdf_map,
        progress_out=None if previous_report is not None else args.out,
        progress_write_every=args.progress_write_every,
        jobs=args.jobs,
        pdf_diagnostics_cache_dir=args.pdf_diagnostics_cache_dir,
    )
    if previous_report is not None:
        report = merge_targeted_report(
            previous_report,
            report,
            previous_report_path=args.merge_previous_report,
            allow_new_articles=args.allow_new_target_articles,
        )
        if args.out is not None:
            _write_json_report(args.out, report)
    _print_summary(report)
    if args.out is not None:
        print(f"Wrote {args.out}")
    if args.fail_on_error or args.fail_on_warning:
        severities = {"error"}
        if args.fail_on_warning:
            severities.add("warning")
        for article in report["articles"]:
            if any(defect["severity"] in severities for defect in article["defects_found"]):
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
