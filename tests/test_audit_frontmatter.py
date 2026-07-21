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


def test_frontmatter_defects_accepts_body_paragraph_with_many_project_citations() -> None:
    polish_blocks = parse_blocks(
        "<p>Neuroimaging data collection for the Human Connectome Project "
        '<a href="#ref-1">1</a>, UK Biobank <a href="#ref-2">2</a>, '
        'and Allen Brain Atlas <a href="#ref-3">3</a> supports research analyses '
        "across several international projects and clinical cohorts.</p>"
    )

    assert "P03" not in {defect.id for defect in frontmatter_defects([], polish_blocks)}


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


def test_frontmatter_defects_reports_publication_metadata_inside_sentence() -> None:
    polish_blocks = parse_blocks(
        "<p>Some institutions, such as the Prado Museum [11]</p>"
        "<p></p>"
        '<p class="z2m-front-matter">Citation: Quero, L. (2021). '
        "https://doi.org/10.3390/example</p>"
        '<p class="z2m-front-matter">Received: 12 November 2020; Accepted: 19 January 2021.</p>'
        "<p>Publisher's Note: The publisher remains neutral.</p>"
        '<p class="z2m-front-matter">Copyright: 2021 by the authors.</p>'
        "<p>and The Andy Warhol Museum [12], among others, pioneered this alternative.</p>"
    )

    defects = frontmatter_defects([], polish_blocks)

    assert [defect.id for defect in defects] == ["P100"]


def test_frontmatter_ocr_repaired_by_polish_sees_superscript_author_markers() -> None:
    polish_blocks = parse_blocks(
        '<p class="z2m-front-matter">Alice Smith<sup>1</sup> Bob Jones<sup>2</sup></p>'
    )

    assert frontmatter_ocr_repaired_by_polish("Alice Smith 1 2 Bob Jones 2 3", polish_blocks)


def test_frontmatter_metadata_and_toc_guards() -> None:
    assert looks_like_frontmatter_metadata_notice("Received: 4 May 2021")
    for notice in (
        "Academic Editors: Marco Leo and Anil Anthony Bharath",
        "\u2217 Equal advising",
        "These authors contributed equally",
        "See Comment page 334",
        "ASSETS '16, October 23 - 26, 2016, Reno, NV, USA",
        "TEI '24, February 11-14, 2024, Cork, Ireland",
        "Open Access Support provided by: University of Bath",
        "Conference Sponsors: SIGACCESS",
        "Citation in BibTeX format",
        "PDF Download 3623509.3633377.pdf",
        "eingereicht 17.4.2008 akzeptiert 16.6.2008",
        "Humboldt-Universit\u00e4t Fakult\u00e4t Institut Abteilung Berlin Tel.: 030 2093 4409 Fax: 030 2093 4222",
        "PD Dr. Rainer Schalnus Klinik fr Augenheilkunde, Klinikum der Johann-Wolfgang-Goethe-Universitt Theodor-Stern-Kai 7 60590 Frankfurt",
    ):
        assert looks_like_frontmatter_metadata_notice(notice)
    assert looks_like_table_of_contents_block(
        "1. Introduction 1 2. Methods 3 3. Results 5 4. Discussion 7 List of Figures"
    )


def test_frontmatter_defects_does_not_start_p100_from_metadata_notice() -> None:
    for notice in (
        "Academic Editors: Marco Leo and Anil Anthony Bharath",
        "\u2217 Equal advising",
        "See Comment page 334",
        "ASSETS '16, October 23 - 26, 2016, Reno, NV, USA",
    ):
        blocks = parse_blocks(
            f"<p>{notice}</p>"
            '<p class="z2m-front-matter">Received: 4 May 2021</p>'
            '<p class="z2m-front-matter">Copyright: 2021 by the authors.</p>'
            "<p>and this lowercase paragraph begins an independent body block.</p>"
        )

        assert "P100" not in {defect.id for defect in frontmatter_defects([], blocks)}


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
