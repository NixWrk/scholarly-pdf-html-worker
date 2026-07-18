"""Pair-level EN polish audit orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any
from pdf_html_polish.artifact_integrity import read_bytes_with_fingerprint

from pdf_html_polish.quality_loop.audit_blocks import (
    Block,
    Defect,
    parse_blocks,
    reference_identity_blocks,
)


@dataclass(frozen=True)
class PolishPairAnalysisDeps:
    source_pdf_path: Callable[[Path], Path]
    load_pdf_diagnostic_text: Callable[[Path, str | None, Path | None], tuple[str, dict[str, Any]]]
    pdf_citation_link_summary: Callable[[Path], dict[str, Any]]
    article_name_from_stage: Callable[[Path], str]
    frontmatter_defects: Callable[[list[Block], list[Block]], list[Defect]]
    citation_defects: Callable[..., list[Defect]]
    reference_identity_defects: Callable[[list[Block]], list[Defect]]
    unit_math_defects: Callable[[str, list[Block]], list[Defect]]
    equation_table_defects: Callable[[list[Block]], list[Defect]]
    figure_caption_ux_defects: Callable[..., list[Defect]]
    figure_visual_identity_defects: Callable[[Path, str], list[Defect]]
    image_asset_defects: Callable[[Path, str], list[Defect]]
    citation_style_consistency_defects: Callable[..., list[Defect]]
    manual_blind_spot_defects: Callable[..., list[Defect]]
    meine_recent_manual_defects: Callable[..., list[Defect]]
    pdf_text_layer_defects: Callable[[str, str, list[Block]], list[Defect]]
    missing_local_images: Callable[[Path, str], list[dict[str, Any]]]
    ref_link_re: re.Pattern[str]
    fig_link_re: re.Pattern[str]
    table_link_re: re.Pattern[str]
    page_link_re: re.Pattern[str]


def disabled_pdf_link_summary() -> dict[str, Any]:
    return {
        "pdf_link_text_status": "disabled",
        "pdf_link_count": 0,
        "pdf_citation_dest_links": 0,
        "pdf_author_year_link_labels": 0,
        "pdf_citation_link_samples": [],
        "pdf_link_text_error": None,
        "pdf_link_cache_status": "disabled",
    }


def disabled_pdf_text_summary(
    raw_path: Path,
    *,
    deps: PolishPairAnalysisDeps,
    enable_pdf_diagnostics: bool,
    pdf_path_override: Path | None,
) -> dict[str, Any]:
    pdf_path = pdf_path_override or deps.source_pdf_path(raw_path)
    return {
        "pdf_diagnostics_enabled": enable_pdf_diagnostics,
        "source_pdf_path": str(pdf_path),
        "source_pdf_present": pdf_path.is_file(),
        "source_pdf_origin": "map" if pdf_path_override is not None else "stage",
        "pdf_text_status": "disabled",
        "pdf_text_chars": 0,
        "pdf_text_error": None,
        "pdf_text_cache_status": "disabled",
    }


def analyze_polish_pair(
    raw_path: Path,
    polish_path: Path,
    *,
    deps: PolishPairAnalysisDeps,
    enable_pdf_diagnostics: bool = False,
    pdf_text_override: str | None = None,
    pdf_path_override: Path | None = None,
    pdf_diagnostics_cache: Any | None = None,
) -> dict[str, Any]:
    raw_snapshot = read_bytes_with_fingerprint(raw_path, reject_symlink=True)
    polish_snapshot = read_bytes_with_fingerprint(polish_path, reject_symlink=True)
    if raw_snapshot is None or polish_snapshot is None:
        raise RuntimeError(
            f"Raw or polish stage changed during audit: {raw_path}, {polish_path}"
        )
    raw_bytes, raw_fingerprint = raw_snapshot
    polish_bytes, polish_fingerprint = polish_snapshot
    raw_html = raw_bytes.decode("utf-8", errors="replace")
    polish_html = polish_bytes.decode("utf-8", errors="replace")
    raw_blocks = parse_blocks(raw_html)
    polish_blocks = parse_blocks(polish_html)
    polish_reference_blocks = reference_identity_blocks(polish_html)

    pdf_text = ""
    pdf_summary = disabled_pdf_text_summary(
        raw_path,
        deps=deps,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_path_override=pdf_path_override,
    )
    if enable_pdf_diagnostics or pdf_text_override is not None:
        if pdf_diagnostics_cache is not None:
            pdf_text, pdf_summary = pdf_diagnostics_cache.load_text(raw_path, pdf_text_override, pdf_path_override)
        else:
            pdf_text, pdf_summary = deps.load_pdf_diagnostic_text(raw_path, pdf_text_override, pdf_path_override)
            pdf_summary["pdf_text_cache_status"] = "disabled"

    pdf_link_summary = disabled_pdf_link_summary()
    if enable_pdf_diagnostics:
        if pdf_diagnostics_cache is not None:
            pdf_link_summary = pdf_diagnostics_cache.link_summary(Path(pdf_summary["source_pdf_path"]))
        else:
            pdf_link_summary = deps.pdf_citation_link_summary(Path(pdf_summary["source_pdf_path"]))
            pdf_link_summary["pdf_link_cache_status"] = "disabled"

    defects: list[Defect] = []
    defects.extend(deps.frontmatter_defects(raw_blocks, polish_blocks))
    defects.extend(deps.citation_defects(polish_blocks, reference_blocks=polish_reference_blocks))
    defects.extend(deps.reference_identity_defects(polish_reference_blocks))
    defects.extend(deps.unit_math_defects(raw_html, polish_blocks))
    defects.extend(deps.equation_table_defects(polish_blocks))
    defects.extend(deps.figure_caption_ux_defects(polish_html, polish_blocks, pdf_text=pdf_text))
    defects.extend(deps.figure_visual_identity_defects(polish_path, polish_html))
    defects.extend(deps.image_asset_defects(polish_path, polish_html))
    defects.extend(
        deps.citation_style_consistency_defects(
            polish_html,
            polish_blocks,
            pdf_text=pdf_text,
            pdf_link_summary=pdf_link_summary,
        )
    )
    defects.extend(deps.manual_blind_spot_defects(polish_html, polish_blocks, pdf_text=pdf_text))
    defects.extend(deps.meine_recent_manual_defects(polish_html, polish_blocks, pdf_text=pdf_text))
    if enable_pdf_diagnostics or pdf_text_override is not None:
        defects.extend(deps.pdf_text_layer_defects(pdf_text, polish_html, polish_blocks))

    missing_images = deps.missing_local_images(polish_path, polish_html)
    summary = {
        "raw_blocks": len(raw_blocks),
        "polish_blocks": len(polish_blocks),
        "raw_img_tags": len(re.findall(r"<img\b", raw_html, re.IGNORECASE)),
        "polish_img_tags": len(re.findall(r"<img\b", polish_html, re.IGNORECASE)),
        "polish_ref_links": len(deps.ref_link_re.findall(polish_html)),
        "polish_fig_links": len(deps.fig_link_re.findall(polish_html)),
        "polish_table_links": len(deps.table_link_re.findall(polish_html)),
        "polish_page_links": len(deps.page_link_re.findall(polish_html)),
        "polish_fig_ids": len(re.findall(r"\bid\s*=\s*['\"]fig-", polish_html, re.IGNORECASE)),
        "polish_table_ids": len(re.findall(r"\bid\s*=\s*['\"]table-", polish_html, re.IGNORECASE)),
        "polish_has_target_style": ":target" in polish_html,
        "polish_has_scroll_margin": "scroll-margin" in polish_html,
        "polish_replacement_chars": polish_html.count("\ufffd"),
        "polish_missing_local_images": len(missing_images),
        **pdf_summary,
        **pdf_link_summary,
    }
    return {
        "article": deps.article_name_from_stage(polish_path),
        "raw_stage_path": str(raw_path),
        "polish_stage_path": str(polish_path),
        "raw_stage_bytes": raw_fingerprint.size,
        "raw_stage_sha256": raw_fingerprint.sha256,
        "polish_stage_bytes": polish_fingerprint.size,
        "polish_stage_sha256": polish_fingerprint.sha256,
        "summary": summary,
        "defects_found": [asdict(defect) for defect in defects],
    }
