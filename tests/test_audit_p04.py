from pdf_html_polish.quality_loop.audit_blocks import Block
from pdf_html_polish.quality_loop.audit_p04 import (
    has_unlinked_sup_numeric_range,
    reference_numbers_from_blocks,
    unlinked_citation_candidate_numbers,
    unlinked_citation_range_kind,
)


def _block(text: str, raw: str | None = None, *, tag: str = "p") -> Block:
    return Block(index=0, tag=tag, attrs={}, raw=raw or f"<{tag}>{text}</{tag}>", text=text, line=1)


def test_unlinked_citation_range_kind_classifies_body_range() -> None:
    block = _block("Prior studies [1, 2] support the method.")

    assert unlinked_citation_range_kind(
        block,
        looks_like_float_or_caption=lambda _block: False,
        block_looks_like_frontmatter_affiliation_table=lambda _block: False,
    ) == "body"
    assert unlinked_citation_candidate_numbers(block) == [1, 2]


def test_unlinked_citation_range_kind_splits_float_range() -> None:
    block = _block("Author affiliations <sup>1,2</sup>", raw="<table><td>Author <sup>1,2</sup></td></table>", tag="table")

    assert unlinked_citation_range_kind(
        block,
        looks_like_float_or_caption=lambda _block: True,
        block_looks_like_frontmatter_affiliation_table=lambda _block: False,
    ) == "float"


def test_unlinked_citation_range_kind_ignores_frontmatter_affiliation_table() -> None:
    block = _block("Author affiliations <sup>1,2</sup>", raw="<table><td>Author <sup>1,2</sup></td></table>", tag="table")

    assert unlinked_citation_range_kind(
        block,
        looks_like_float_or_caption=lambda _block: True,
        block_looks_like_frontmatter_affiliation_table=lambda _block: True,
    ) == ""


def test_unlinked_citation_range_kind_splits_math_sup_range() -> None:
    block = _block("The parameter values 28-31 matched the model.", raw="<p>The parameter values <sup>28-31</sup> matched.</p>")

    assert unlinked_citation_range_kind(
        block,
        looks_like_float_or_caption=lambda _block: False,
        block_looks_like_frontmatter_affiliation_table=lambda _block: False,
    ) == "math"
    assert unlinked_citation_candidate_numbers(block) == [28, 31]


def test_reference_numbers_from_blocks_reads_ids_and_raw_ref_targets() -> None:
    explicit_id = Block(index=0, tag="p", attrs={"id": "ref-7"}, raw="<p id='ref-7'>Seven.</p>", text="Seven.", line=1)
    nested_raw = _block("Nested.", raw='<div><span id="ref-11">Eleven.</span></div>', tag="div")

    assert reference_numbers_from_blocks([explicit_id, nested_raw]) == {7, 11}


def test_unlinked_sup_numeric_range_ignores_footnote_ref_range() -> None:
    block = _block(
        "Several investigators used refinements. 7-11 In 1967.",
        raw='<p>Several investigators used refinements.<sup class="z2m-footnote-ref">7-11</sup> In 1967.</p>',
    )

    assert has_unlinked_sup_numeric_range(block) is False
    assert unlinked_citation_range_kind(
        block,
        looks_like_float_or_caption=lambda _block: False,
        block_looks_like_frontmatter_affiliation_table=lambda _block: False,
    ) == ""


def test_unlinked_sup_numeric_range_ignores_measurement_unit_suffix() -> None:
    block = _block(
        "The value may be 4,11 min-1 below Fick.",
        raw="<p>The value may be <sup>4,11</sup>. min<sup>-1</sup> below Fick.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False


def test_unlinked_sup_numeric_range_ignores_project_identifier() -> None:
    block = _block(
        "This work used Project Number 24,5 .022.",
        raw="<p>This work used Project Number <sup>24,5</sup>.022.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False
    assert (
        unlinked_citation_range_kind(
            block,
            looks_like_float_or_caption=lambda _block: False,
            block_looks_like_frontmatter_affiliation_table=lambda _block: False,
        )
        == ""
    )


def test_unlinked_sup_numeric_range_ignores_dimension_unit_pair() -> None:
    block = _block(
        "The experiment room had 7.7 m 10,5 m of walkable space.",
        raw="<p>The experiment room had 7.7 m<sup>10,5</sup> m of walkable space.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False
    assert (
        unlinked_citation_range_kind(
            block,
            looks_like_float_or_caption=lambda _block: False,
            block_looks_like_frontmatter_affiliation_table=lambda _block: False,
        )
        == ""
    )


def test_unlinked_sup_numeric_range_ignores_software_version() -> None:
    block = _block(
        "The Python version 3, 10 was used.",
        raw="<p>The Python version <sup>3,10</sup> was used.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False


def test_unlinked_sup_numeric_range_ignores_unity_version() -> None:
    block = _block(
        "Unity 5,6 .1f1 was used to generate 3D cartoons.",
        raw="<p>Unity <sup>5,6</sup>.1f1 was used to generate 3D cartoons.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False
    assert (
        unlinked_citation_range_kind(
            block,
            looks_like_float_or_caption=lambda _block: False,
            block_looks_like_frontmatter_affiliation_table=lambda _block: False,
        )
        == ""
    )


def test_unlinked_sup_numeric_range_ignores_question_count_range() -> None:
    block = _block(
        "It contained 35-58 questions in total.",
        raw="<p>It contained <sup>35-58</sup> questions in total.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False


def test_unlinked_sup_numeric_range_ignores_target_option_count() -> None:
    block = _block(
        "The number of targets varied and it could be 3, 4 or 5 chairs.",
        raw="<p>The number of targets varied and it could be <sup>3, 4</sup> or 5 chairs.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False


def test_unlinked_sup_numeric_range_ignores_temporal_list_with_trailing_unit() -> None:
    block = _block(
        "Recordings were resumed for three monkeys at 2, 5 and 7 days after removing the prisms.",
        raw=(
            "<p>Recordings were resumed for three monkeys at "
            "<sup>2, 5</sup> and 7 days after removing the prisms.</p>"
        ),
    )

    assert has_unlinked_sup_numeric_range(block) is False
    assert unlinked_citation_range_kind(
        block,
        looks_like_float_or_caption=lambda _block: False,
        block_looks_like_frontmatter_affiliation_table=lambda _block: False,
    ) == ""
    assert unlinked_citation_candidate_numbers(block) == []


def test_unlinked_sup_numeric_range_still_flags_body_citation_list() -> None:
    block = _block(
        "Prior studies 2, 5 support the method.",
        raw="<p>Prior studies<sup>2, 5</sup> support the method.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is True
    assert unlinked_citation_range_kind(
        block,
        looks_like_float_or_caption=lambda _block: False,
        block_looks_like_frontmatter_affiliation_table=lambda _block: False,
    ) == "body"
    assert unlinked_citation_candidate_numbers(block) == [2, 5]
