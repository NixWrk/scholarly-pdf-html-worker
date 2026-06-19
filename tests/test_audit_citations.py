from pdf_html_polish.quality_loop.audit_blocks import Block
from pdf_html_polish.quality_loop.audit_citations import CitationDefectDeps, citation_defects


def _block(text: str, raw: str | None = None, *, id_: str = "", classes: str = "") -> Block:
    attrs = {}
    if id_:
        attrs["id"] = id_
    if classes:
        attrs["class"] = classes
    return Block(index=0, tag="p", attrs=attrs, raw=raw or f"<p>{text}</p>", text=text, line=1)


def _deps(kind: str = "", *, linked_ref: bool = False) -> CitationDefectDeps:
    return CitationDefectDeps(
        unlinked_citation_range_kind=lambda block: kind if "[1, 2]" in block.text else "",
        linked_ref_near_non_citation_context=lambda block: linked_ref and "linked" in block.text,
    )


def test_citation_defects_reports_body_range_with_matching_targets() -> None:
    block = _block("Prior studies [1, 2] support the method.")
    references = [_block("One.", id_="ref-1"), _block("Two.", id_="ref-2")]

    defects = citation_defects([block], reference_blocks=references, deps=_deps("body"))

    assert [defect.id for defect in defects] == ["P04"]


def test_citation_defects_splits_missing_and_absent_reference_targets() -> None:
    block = _block("Prior studies [1, 2] support the method.")
    partial_references = [_block("One.", id_="ref-1")]

    missing_target_defects = citation_defects([block], reference_blocks=partial_references, deps=_deps("body"))
    absent_target_defects = citation_defects([block], deps=_deps("body"))

    assert [defect.id for defect in missing_target_defects] == ["P04R"]
    assert missing_target_defects[0].extra["missing_targets"] == [2]
    assert [defect.id for defect in absent_target_defects] == ["P04N"]
    assert absent_target_defects[0].extra["candidate_numbers"] == [1, 2]


def test_citation_defects_reports_latex_ocr_and_linked_ref_contexts_once() -> None:
    blocks = [
        _block("The marker produced task. Sec. citation text."),
        _block("Inline math \\(^{71-73}\\) remained.", raw="<p>Inline math \\(^{71-73}\\) remained.</p>"),
        _block("linked pH context"),
        _block("linked second pH context"),
    ]

    defects = citation_defects(blocks, deps=_deps(linked_ref=True))

    assert [defect.id for defect in defects] == ["P32", "P28", "P05"]
