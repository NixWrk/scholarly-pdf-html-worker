from pdf_html_polish.quality_loop.audit_blocks import parse_blocks
from pdf_html_polish.quality_loop.audit_frontmatter import (
    block_looks_like_frontmatter_affiliation_table,
    frontmatter_defects,
    frontmatter_ocr_repaired_by_polish,
    looks_like_frontmatter_metadata_notice,
    looks_like_table_of_contents_block,
)


def test_frontmatter_defects_reports_raw_marker_ocr() -> None:
    raw_blocks = parse_blocks("<p>Alice Smith 1 2 corresponding marker damage.</p>")

    defects = frontmatter_defects(raw_blocks, [])

    assert [defect.id for defect in defects] == ["P01"]


def test_frontmatter_defects_reports_affiliation_ref_links_and_author_line_links() -> None:
    polish_blocks = parse_blocks(
        '<p class="z2m-affiliations"><a href="#ref-1">1</a> Department.</p>'
        '<p>Alice Smith <a href="#ref-1">1</a> Bob Jones <a href="#ref-2">2</a></p>'
    )

    defects = frontmatter_defects([], polish_blocks)

    assert [defect.id for defect in defects] == ["P02", "P03"]


def test_frontmatter_defects_reports_late_body_frontmatter() -> None:
    prefix = "".join("<p>Filler.</p>" for _ in range(41))
    late = (
        '<p class="z2m-front-matter">'
        "Clinical validation metrics for models and patients show performance evaluation in studies."
        "</p>"
    )
    polish_blocks = parse_blocks(prefix + late)

    defects = frontmatter_defects([], polish_blocks)

    assert [defect.id for defect in defects] == ["P25"]


def test_frontmatter_ocr_repaired_by_polish_sees_superscript_author_markers() -> None:
    polish_blocks = parse_blocks(
        '<p class="z2m-front-matter">Alice Smith<sup>1</sup> Bob Jones<sup>2</sup></p>'
    )

    assert frontmatter_ocr_repaired_by_polish("Alice Smith 1 2 Bob Jones 2 3", polish_blocks)


def test_frontmatter_metadata_and_toc_guards() -> None:
    assert looks_like_frontmatter_metadata_notice("Received: 4 May 2021")
    assert looks_like_table_of_contents_block(
        "1. Introduction 1 2. Methods 3 3. Results 5 4. Discussion 7 List of Figures"
    )


def test_block_looks_like_frontmatter_affiliation_table() -> None:
    blocks = parse_blocks(
        "<table><tr><td>"
        "Alice Smith 1 Department of Medicine 1 University of Example 2 "
        "Bob Jones 2 Institute of Science 3 Denmark 4 Correspondence 5"
        "</td></tr></table>"
    )

    assert any(block_looks_like_frontmatter_affiliation_table(block) for block in blocks)


def test_audit_script_keeps_legacy_frontmatter_aliases() -> None:
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_en_polish.py"
    spec = importlib.util.spec_from_file_location("audit_en_polish_frontmatter_alias_check", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._frontmatter_defects is frontmatter_defects
    assert module._block_looks_like_frontmatter_affiliation_table is block_looks_like_frontmatter_affiliation_table
