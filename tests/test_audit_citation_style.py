from pdf_html_polish.quality_loop.audit_blocks import Block, parse_blocks
from pdf_html_polish.quality_loop.audit_citation_style import (
    citation_style_consistency_defects,
    numeric_ref_label_numbers,
)


def _all_blocks(blocks: list[Block]) -> list[Block]:
    return blocks


def _never_float_or_table_context(block: Block) -> bool:
    del block
    return False


def _citation_style_defects(html: str):
    return citation_style_consistency_defects(
        html,
        parse_blocks(html),
        stage="02.en.polish.html",
        non_reference_body_blocks=_all_blocks,
        block_is_float_or_table_context=_never_float_or_table_context,
    )


def test_numeric_ref_label_numbers_filters_years_and_leading_zeroes() -> None:
    assert numeric_ref_label_numbers("(8, 10-12)") == [8, 10, 12]
    assert numeric_ref_label_numbers("Smith 2020") == []
    assert numeric_ref_label_numbers("[03]") == []
    assert numeric_ref_label_numbers("[1999]") == []


def test_citation_style_consistency_defects_reports_numeric_ref_in_author_year_article() -> None:
    html = (
        "<p>Smith et al. (2020), Jones and Brown (2021), Gupta &amp; Pruthi (2025), "
        "Lund and Naheem (2023), Yeo-The &amp; Tang (2023), and Lehman and Stanley (2011) "
        'define the author-year style, but this marker <sup><a href="#ref-12" '
        'class="z2m-ref-link">12</a></sup> should not be a bibliography link.</p>'
    )

    defects = _citation_style_defects(html)

    assert [defect.id for defect in defects] == ["P98"]
    assert defects[0].extra["ref_target"] == "12"
    assert defects[0].first_broken_stage == "02.en.polish.html"


def test_citation_style_consistency_defects_ignores_parenthetical_numeric_dominant_article() -> None:
    numeric_citations = [
        f'<p>Numeric citation evidence <a href="#ref-{idx}" class="z2m-ref-link">({idx})</a>.</p>'
        for idx in range(1, 6)
    ]
    html = "\n".join(
        [
            "<p>Smith et al. (2020), Jones and Brown (2021), Gupta &amp; Pruthi (2025), "
            "Lund and Naheem (2023), Yeo-The &amp; Tang (2023), and Lehman and Stanley (2011) "
            "make front matter look author-year.</p>",
            *numeric_citations,
            '<p>Users explore through speech descriptions <a href="#ref-8" class="z2m-ref-link">(8,</a> '
            '9) or vibration feedback <a href="#ref-10" class="z2m-ref-link">(10)</a>.</p>',
        ]
    )

    defects = _citation_style_defects(html)

    assert defects == []


def test_citation_style_consistency_defects_ignores_bracket_numeric_citations() -> None:
    html = (
        "<p>Smith et al. (2020), Jones and Brown (2021), Gupta &amp; Pruthi (2025), "
        "Lund and Naheem (2023), Yeo-The &amp; Tang (2023), and Lehman and Stanley (2011) "
        "make this sparse article look author-year.</p>"
        '<p>Public datasets include ADE20K [<a href="#ref-1" class="z2m-ref-link">1</a>, 2] '
        'and SceneNN [<a href="#ref-3" class="z2m-ref-link">3</a>].</p>'
    )

    defects = _citation_style_defects(html)

    assert defects == []
