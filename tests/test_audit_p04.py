from zoteropdf2md.quality_loop.audit_blocks import Block
from zoteropdf2md.quality_loop.audit_p04 import (
    has_unlinked_sup_numeric_range,
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


def test_unlinked_sup_numeric_range_ignores_software_version() -> None:
    block = _block(
        "The Python version 3, 10 was used.",
        raw="<p>The Python version <sup>3,10</sup> was used.</p>",
    )

    assert has_unlinked_sup_numeric_range(block) is False
