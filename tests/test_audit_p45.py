import re

from pdf_html_polish.quality_loop.audit_blocks import Block
from pdf_html_polish.quality_loop.audit_manual_patterns import (
    looks_like_affiliation_label_roman_boundary,
)
from pdf_html_polish.quality_loop.audit_p45 import ROMAN_WORD_SPLIT_RE, roman_word_split_defects


REFERENCES_HEADING_RE = re.compile(r"^\s*references\s*$", re.IGNORECASE)


def _block(text: str, raw: str | None = None, *, index: int = 0, tag: str = "p") -> Block:
    return Block(index=index, tag=tag, attrs={}, raw=raw or f"<{tag}>{text}</{tag}>", text=text, line=index + 1)


def _defects(
    block: Block,
    *,
    is_reference: bool = False,
    is_affiliation_label: bool = False,
):
    return roman_word_split_defects(
        [block],
        references_heading_re=REFERENCES_HEADING_RE,
        is_references_block=lambda _block, _references_started: is_reference,
        looks_like_affiliation_label_roman_boundary=lambda _block, _match: is_affiliation_label,
        stage="02.en.polish.html",
    )


def test_country_affiliation_boundary_does_not_require_article_info_context() -> None:
    block = _block(
        "University Hospital, Magdeburg, Germany i Institute for Clinical Research"
    )
    split_match = ROMAN_WORD_SPLIT_RE.search(block.text)

    assert split_match is not None
    assert looks_like_affiliation_label_roman_boundary(block, split_match) is True


def test_roman_word_split_defects_reports_plain_split_word() -> None:
    defects = _defects(_block("The surname Belyae v remains split."))

    assert [defect.id for defect in defects] == ["P45"]
    assert defects[0].extra == {"match": "Belyae v"}


def test_roman_word_split_defects_classifies_superscript_marker_telemetry() -> None:
    block = _block("The author Teixeira i remains visible.", raw="<p>The author Teixeira<sup>i</sup> remains visible.</p>")
    defects = _defects(block)

    assert [defect.id for defect in defects] == ["P45S"]
    assert defects[0].extra == {"match": "Teixeira i", "quality_counted": False}


def test_roman_word_split_defects_classifies_math_span_telemetry() -> None:
    block = _block("Function v is defined.", raw='<p>Function <span class="z2m-math">v</span> is defined.</p>')
    defects = _defects(block)

    assert [defect.id for defect in defects] == ["P45M"]
    assert defects[0].extra == {"match": "Function v", "quality_counted": False}


def test_roman_word_split_defects_classifies_affiliation_label_telemetry() -> None:
    defects = _defects(_block("Denmark i National Institute"), is_affiliation_label=True)

    assert [defect.id for defect in defects] == ["P45A"]
    assert defects[0].extra == {"match": "Denmark i", "quality_counted": False}


def test_roman_word_split_defects_skips_reference_blocks_and_false_prefixes() -> None:
    assert _defects(_block("The surname Belyae v remains split."), is_reference=True) == []
    assert _defects(_block("Figure v shows the result.")) == []
    assert _defects(_block("Panel i shows the result.")) == []
    assert _defects(_block("Whenever v changes, the result is updated.")) == []
