import re

from pdf_html_polish.quality_loop.audit_blocks import Block, parse_blocks
from pdf_html_polish.quality_loop.audit_citation_style import (
    citation_style_consistency_defects,
    flattened_sup_match_is_doi_or_url_fragment,
    flattened_sup_match_is_joined_figure_label,
    linked_ref_near_non_citation_context,
    looks_like_comma_decimal_stat_ref,
    looks_like_sample_size_value_ref,
    numeric_ref_label_numbers,
    ref_anchor_visible_number,
    ref_match_inside_bracketed_numeric_citation,
)


def _all_blocks(blocks: list[Block]) -> list[Block]:
    return blocks


def _never_float_or_table_context(block: Block) -> bool:
    del block
    return False


def _single_block(html: str) -> Block:
    blocks = parse_blocks(html)
    assert len(blocks) == 1
    return blocks[0]


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


def test_ref_anchor_visible_number_accepts_single_visible_number() -> None:
    assert ref_anchor_visible_number("ref. 12") == 12
    assert ref_anchor_visible_number("1, 2") is None
    assert ref_anchor_visible_number("Smith") is None


def test_ref_match_inside_bracketed_numeric_citation_detects_linked_list() -> None:
    raw = 'Prior work [<a href="#ref-1">1</a>, 2] was cited.'
    anchor = re.search(r"<a\b[^>]*href=\"#ref-1\"[^>]*>1</a>", raw)
    plain_raw = 'Prior work <a href="#ref-1">1</a> was cited.'
    plain_anchor = re.search(r"<a\b[^>]*href=\"#ref-1\"[^>]*>1</a>", plain_raw)
    assert anchor is not None
    assert plain_anchor is not None

    assert ref_match_inside_bracketed_numeric_citation(
        raw, anchor.start(), anchor.end()
    )
    assert not ref_match_inside_bracketed_numeric_citation(
        plain_raw,
        plain_anchor.start(),
        plain_anchor.end(),
    )


def test_stat_ref_classifiers_accept_numeric_measurement_contexts() -> None:
    comma_raw = (
        'The Cohen d = <a href="#ref-1">1</a>, <a href="#ref-2">2</a> in the analysis.'
    )
    comma_match = re.search(
        r"<a\b[^>]*href=\"#ref-1\"[^>]*>1</a>\s*,\s*<a\b[^>]*href=\"#ref-2\"[^>]*>2</a>",
        comma_raw,
    )
    assert comma_match is not None
    assert looks_like_comma_decimal_stat_ref(comma_raw, comma_match)

    sample_raw = 'The final sample size was <a href="#ref-42">42</a> participants.'
    sample_match = re.search(r"sample size[\s\S]+?</a>", sample_raw)
    assert sample_match is not None
    assert looks_like_sample_size_value_ref(sample_raw, sample_match)


def test_flattened_sup_filters_detect_figure_labels_and_doi_fragments() -> None:
    figure_match = re.search(r"\bFig\.12\b", "See Fig.12 for details")
    doi_text = "The DOI is https://doi.org/10.1000/example2 for this article."
    doi_match = re.search(r"example2", doi_text)
    assert figure_match is not None
    assert doi_match is not None

    assert flattened_sup_match_is_joined_figure_label(figure_match)
    assert flattened_sup_match_is_doi_or_url_fragment(doi_text, doi_match)


def test_linked_ref_near_non_citation_context_flags_unit_like_context() -> None:
    block = _single_block(
        '<p>Urine pH <a href="#ref-7" class="z2m-ref-link">7</a> was recorded.</p>'
    )

    assert linked_ref_near_non_citation_context(block)


def test_linked_ref_near_non_citation_context_ignores_sentence_final_superscript() -> (
    None
):
    block = _single_block(
        "<p>OAB should be investigated."
        '<sup><a href="#ref-10" class="z2m-ref-link">10</a></sup> '
        "The most recent study shows a correlation between urine pH and symptoms."
        '<sup><a href="#ref-11" class="z2m-ref-link">11</a></sup></p>'
    )

    assert not linked_ref_near_non_citation_context(block)


def test_linked_ref_near_non_citation_context_ignores_truncated_phoneme_tail() -> None:
    block = _single_block(
        '<p>Movements often produce overlapping neural signatures <a href="#ref-12" '
        'class="z2m-ref-link"> 12; </a> these phonemes (especially vowels) are often '
        "interchangeable when a phoneme-based language model considers probable sentences.</p>"
    )

    assert not linked_ref_near_non_citation_context(block)


def test_linked_ref_near_non_citation_context_ignores_month_word_citation() -> None:
    block = _single_block(
        '<p>Symptoms improved at month <a href="#ref-13" class="z2m-ref-link">13</a>.</p>'
    )

    assert not linked_ref_near_non_citation_context(block)


def test_citation_style_consistency_defects_reports_numeric_ref_in_author_year_article() -> (
    None
):
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


def test_citation_style_consistency_defects_reports_missing_author_year_ref_links() -> (
    None
):
    html = (
        "<p>Smith et al. (2020), Jones and Brown (2021), Gupta &amp; Pruthi (2025), "
        "Lund and Naheem (2023), Yeo-The &amp; Tang (2023), and Lehman and Stanley (2011) "
        "define the author-year style.</p>"
        '<p id="ref-1">Smith J. Example.</p>'
        '<p id="ref-2">Jones J. Example.</p>'
        '<p id="ref-3">Gupta A. Example.</p>'
    )

    defects = _citation_style_defects(html)

    assert [defect.id for defect in defects] == ["P99"]
    assert defects[0].extra["ref_id_count"] == 3
    assert defects[0].extra["ref_link_count"] == 0


def test_citation_style_consistency_defects_ignores_unlinked_parenthetical_numeric_article() -> (
    None
):
    html = (
        "<p>Between 1997 and 2007, Smith (1958), Jones (1965), Brown (1971), "
        "White (1978), Green (1982), and Black (1991) described earlier work.</p>"
        "<p>Current evidence follows the numbered sources (1), (2), (3), (4), (5), and (6).</p>"
        + "".join(f'<p id="ref-{idx}">Reference {idx}.</p>' for idx in range(1, 7))
    )

    assert _citation_style_defects(html) == []


def test_citation_style_consistency_defects_ignores_unlinked_bracket_numeric_article() -> (
    None
):
    html = (
        "<p>Smith (2020), Jones (2021), Brown (2022), White (2023), Green (2024), "
        "and Black (2025) describe prior work.</p>"
        "<p>Current evidence uses numbered sources [1], [2], [3], and [4].</p>"
        + "".join(f'<p id="ref-{idx}">Reference {idx}.</p>' for idx in range(1, 5))
    )

    assert _citation_style_defects(html) == []


def test_citation_style_consistency_defects_ignores_sparse_superscript_numeric_article() -> (
    None
):
    html = (
        "<p>Smith et al. (2020), Jones and Brown (2021), Gupta &amp; Pruthi (2025), "
        "Lund and Naheem (2023), Yeo-The &amp; Tang (2023), and Lehman and Stanley (2011) "
        "make the front matter look author-year.</p>"
        "<p>Dedicated scanners existed in our institution5 and others.<sup>"
        '<a href="#ref-6" class="z2m-ref-link">6</a></sup> In general, they worked.</p>'
        "<h4>References</h4><ul>"
        + "".join(
            f'<li id="ref-{idx}"><span class="z2m-ref-num">{idx}.</span> Reference {idx}.</li>'
            for idx in range(1, 7)
        )
        + "</ul>"
    )

    assert _citation_style_defects(html) == []


def test_citation_style_consistency_defects_ignores_unlinked_flattened_numeric_article() -> (
    None
):
    html = (
        "<p>Smith et al. (2020), Jones and Brown (2021), Gupta &amp; Pruthi (2025), "
        "Lund and Naheem (2023), Yeo-The &amp; Tang (2023), and Lehman and Stanley (2011) "
        "make the front matter look author-year.</p>"
        "<p>Dedicated scanners existed in our institution5 and others. 6 In general, they worked.</p>"
        "<h4>References</h4><ul>"
        + "".join(
            f'<li id="ref-{idx}"><span class="z2m-ref-num">{idx}.</span> Reference {idx}.</li>'
            for idx in range(1, 7)
        )
        + "</ul>"
    )

    assert _citation_style_defects(html) == []


def test_citation_style_consistency_defects_ignores_parenthetical_numeric_dominant_article() -> (
    None
):
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


def test_linked_ref_near_non_citation_context_ignores_author_year_anchor() -> None:
    block = _single_block(
        '<p>The pH shifts described by (<a href="#ref-7" class="z2m-ref-link">'
        "Cogan, 2008</a>) were reproduced.</p>"
    )

    assert not linked_ref_near_non_citation_context(block)
