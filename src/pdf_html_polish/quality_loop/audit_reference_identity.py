from __future__ import annotations

import re

from pdf_html_polish.html_stages import POLISH_STAGE_NAME
from pdf_html_polish.quality_loop.audit_blocks import (
    Block,
    Defect,
    normalize_ws,
    visible_ref_number_from_match,
)
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect


REFERENCES_HEADING_RE = re.compile(r"^\s*(?:references|bibliography|works cited)\s*$", re.IGNORECASE)
LOCAL_ABSTRACT_SECTION_HEADING_RE = re.compile(r"^\s*\d{1,3}\s*\|\s+\S")
REF_ID_RE = re.compile(r"^ref-(\d+)$", re.IGNORECASE)
VISIBLE_REF_NUM_RE = re.compile(r"^\s*(?:\[\s*(\d{1,4})\s*\]|(\d{1,4})[.)])")
EMBEDDED_REF_BOUNDARY_RE = re.compile(r"\s(?P<num>\d{1,4})\.\s+(?=[A-Z\u00c0-\u00de])")
REF_DUP_BRACKET_PREFIX_RE = re.compile(
    r'<span\b[^>]*\bz2m-ref-num\b[^>]*>\s*(?P<num>\d{1,4})\.\s*</span>\s*'
    r'(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\2[^>]*>\s*</span>\s*)*'
    r'\[(?P=num)\]',
    re.IGNORECASE,
)
NUMERIC_VALUE_ROW_RE = re.compile(
    r"^\s*(?:[-+]?\d+(?:\.\d+)?\s+){3,}[-+]?\d+(?:\.\d+)?\s*$"
)
REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE = re.compile(
    r"https?://|\bdoi\b|\b(?:pmid|arxiv|isbn)\b|"
    r"\b(?:19|20)\d{2}\b|"
    r"\b(?:journal|proceedings|conference|press|vol\.?|volume|pp\.?|pages?|"
    r"IEEE|ACM|Springer|Elsevier|Nature|Science|JAMA|Lancet|Urol|Ophthalmol|"
    r"Neurourol|Eur\s+J|Int\s+J)\b",
    re.IGNORECASE,
)
DOI_ONLY_METADATA_RE = re.compile(
    r"^\s*(?:doi:\s*)?(?:https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+\s*(?:DOI:)?\s*$",
    re.IGNORECASE,
)


def is_references_block(block: Block, references_started: bool) -> bool:
    return references_started or block.id.startswith("ref-") or REFERENCES_HEADING_RE.match(block.text) is not None


def _has_local_abstract_heading_nearby(
    blocks: list[Block],
    index: int,
    *,
    direction: int,
    window: int,
) -> bool:
    stop = min(len(blocks), index + window + 1) if direction > 0 else max(-1, index - window - 1)
    for scan_index in range(index + direction, stop, direction):
        candidate = blocks[scan_index]
        if LOCAL_ABSTRACT_SECTION_HEADING_RE.match(candidate.text):
            return True
        if candidate.tag.startswith("h") and REFERENCES_HEADING_RE.match(candidate.text):
            continue
    return False


def looks_like_local_abstract_reference_block(blocks: list[Block], index: int) -> bool:
    block = blocks[index]
    visible_match = VISIBLE_REF_NUM_RE.match(block.text)
    visible_number = visible_ref_number_from_match(visible_match)
    if visible_number is None or visible_number > 3:
        return False
    if not any(
        REFERENCES_HEADING_RE.match(blocks[scan_index].text)
        for scan_index in range(max(0, index - 3), index)
    ):
        return False
    if not (
        _has_local_abstract_heading_nearby(blocks, index, direction=-1, window=80)
        or _has_local_abstract_heading_nearby(blocks, index, direction=1, window=8)
    ):
        return False
    tail = VISIBLE_REF_NUM_RE.sub("", block.text, count=1).strip()
    author_head = r"[^\s,]{2,80}"
    initial_token = r"[^\W\d_](?:[^\W\d_]|\.){0,5}"
    return bool(
        re.match(
            rf"{author_head}(?:,\s+{initial_token}|(?:\s+{initial_token}){{1,4}}\s*,)",
            tail,
        )
        or re.search(r"\b(?:doi|pmid|pmcid)\s*:", tail, re.IGNORECASE)
    )


def numbered_reference_block_is_likely_non_bibliographic(block: Block) -> bool:
    if block.id.startswith("ref-"):
        return False
    text = normalize_ws(block.text)
    if re.match(r"^\s*\d+\.\d+(?:\.\d+)*\b", text):
        return True
    if REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE.search(text):
        return False
    if re.match(r"^\s*\d+\.\s*\[?(?:optional|required)\]?\s", text, re.IGNORECASE):
        return True
    return True


def _looks_like_embedded_numbered_reference_tail(tail: str) -> bool:
    text = tail.strip()
    if len(text) < 18:
        return False
    if re.match(
        r"^(?:The\s+)?[A-Z][A-Za-z0-9&'\u2019().,\- ]{3,90}\.\s+Available\s+online\b",
        text,
    ):
        return True
    return bool(
        re.match(
            r"^[A-Z][A-Za-z\u00c0-\u00ff'\u2019.-]+,\s+(?:[A-Z]|et\s+al\.?\b)",
            text,
        )
        or re.match(
            r"^[A-Z][A-Za-z\u00c0-\u00ff'\u2019.-]+\s+"
            r"[A-Z][A-Za-z\u00c0-\u00ff'\u2019.-]+,\s+(?:[A-Z]|et\s+al\.?\b)",
            text,
        )
    )


def _can_have_embedded_numbered_reference(
    block: Block, visible_number: int | None, id_number: int | None
) -> bool:
    if visible_number is not None or id_number is not None:
        return True
    return block.attrs.get("data-z2m-audit-nested-ref-item") == "1"


def reference_identity_defects(
    polish_blocks: list[Block],
    *,
    polish_stage: str = POLISH_STAGE_NAME,
) -> list[Defect]:
    defects: list[Defect] = []
    references_started = False
    seen_visible: dict[int, Block] = {}
    seen_ids: dict[int, Block] = {}
    nested_seen_ids: dict[int, Block] = {}
    saw_mismatch = False
    saw_duplicate = False
    saw_gap = False
    saw_duplicate_prefix = False
    saw_embedded_numbered_reference = False
    missing_visible_number: list[tuple[int, Block]] = []

    for index, block in enumerate(polish_blocks):
        if REFERENCES_HEADING_RE.match(block.text):
            references_started = True
            continue
        if not is_references_block(block, references_started):
            continue
        if not block.id and DOI_ONLY_METADATA_RE.match(block.text):
            continue
        if block.id.startswith("section-"):
            continue

        visible_match = VISIBLE_REF_NUM_RE.match(block.text)
        visible_number = visible_ref_number_from_match(visible_match)
        id_match = REF_ID_RE.match(block.id)
        id_number = int(id_match.group(1)) if id_match is not None else None
        if (
            visible_number is not None
            and looks_like_local_abstract_reference_block(polish_blocks, index)
        ):
            continue
        if id_number is None and NUMERIC_VALUE_ROW_RE.match(block.text):
            continue
        if (
            visible_number is not None
            and id_number is None
            and numbered_reference_block_is_likely_non_bibliographic(block)
        ):
            continue
        is_nested_audit_ref = block.attrs.get("data-z2m-audit-nested-ref-item") == "1"
        if id_number is not None:
            if is_nested_audit_ref:
                nested_seen_ids[id_number] = block
            else:
                seen_ids[id_number] = block
                if visible_number is None and not DOI_ONLY_METADATA_RE.match(block.text):
                    missing_visible_number.append((id_number, block))
        if is_nested_audit_ref:
            if visible_number is not None and visible_number not in seen_visible:
                seen_visible[visible_number] = block
            continue

        if not saw_duplicate_prefix and REF_DUP_BRACKET_PREFIX_RE.search(block.raw):
            defects.append(
                make_defect(
                    defect_id="P27",
                    cc_class="CC-02/CC-13",
                    check="Bibliography entry keeps duplicate bracketed reference prefix",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Reference normalization added z2m numbering without stripping the source bracket number.",
                    proposed_fix_layer="EN polish bibliography prefix deduplication",
                    regression_test="References like '1. [1] Author...' normalize to one visible number.",
                )
            )
            saw_duplicate_prefix = True

        if not saw_embedded_numbered_reference and _can_have_embedded_numbered_reference(
            block, visible_number, id_number
        ):
            text_without_prefix = VISIBLE_REF_NUM_RE.sub("", block.text, count=1)
            for embedded_match in EMBEDDED_REF_BOUNDARY_RE.finditer(text_without_prefix):
                embedded_number = int(embedded_match.group("num"))
                if embedded_number > 500 or embedded_number in {visible_number, id_number}:
                    continue
                if not _looks_like_embedded_numbered_reference_tail(
                    text_without_prefix[embedded_match.end() :]
                ):
                    continue
                defects.append(
                    make_defect(
                        defect_id="P26",
                        cc_class="CC-02/CC-13",
                        check="Bibliography item contains embedded numbered references",
                        severity="warning",
                        block=block,
                        snippet=block.text,
                        stage=polish_stage,
                        hypothesis="Reference continuation merging swallowed one or more later bibliography entries into an earlier item.",
                        proposed_fix_layer="EN polish bibliography continuation merge and line-number stripping",
                        regression_test="Line-number-prefixed bibliography items such as '1161 106. Smith...' remain independent ref-106 entries.",
                        extra={
                            "embedded_number": embedded_number,
                            "id_number": id_number,
                            "visible_number": visible_number,
                        },
                    )
                )
                saw_embedded_numbered_reference = True
                break

        if not saw_mismatch and id_number is not None and visible_number is not None and id_number != visible_number:
            defects.append(
                make_defect(
                    defect_id="P21",
                    cc_class="CC-02/CC-13",
                    check="Reference target ID does not match visible bibliography number",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Reference IDs were assigned by raw list ordinal after Marker split or duplicated bibliography items.",
                    proposed_fix_layer="EN polish bibliography normalization before citation linkification",
                    regression_test="id=ref-N must contain visible reference number N when the bibliography prints numbers.",
                    extra={"id_number": id_number, "visible_number": visible_number},
                )
            )
            saw_mismatch = True

        if visible_number is None:
            continue
        if visible_number in seen_visible and not saw_duplicate:
            defects.append(
                make_defect(
                    defect_id="P22",
                    cc_class="CC-02/CC-13",
                    check="Duplicate visible bibliography number",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="A continuation fragment or duplicate raw list item may still be treated as a separate reference.",
                    proposed_fix_layer="EN polish bibliography continuation merge and reference audit",
                    regression_test="Duplicate visible reference numbers are merged or explicitly reported before manual review.",
                    extra={"visible_number": visible_number, "first_line": seen_visible[visible_number].line},
                )
            )
            saw_duplicate = True
        else:
            seen_visible[visible_number] = block

    if not saw_gap and len(seen_ids) >= 2:
        sorted_ids = sorted(seen_ids)
        for left, right in zip(sorted_ids, sorted_ids[1:]):
            if right - left > 1:
                missing = list(range(left + 1, right))
                missing = [ref_id for ref_id in missing if ref_id not in nested_seen_ids]
                if not missing:
                    continue
                defects.append(
                    make_defect(
                        defect_id="P26",
                        cc_class="CC-02/CC-13",
                        check="Bibliography target IDs contain a gap",
                        severity="warning",
                        block=seen_ids[right],
                        snippet=seen_ids[right].text,
                        stage=polish_stage,
                        hypothesis="An unnumbered item or continuation may have been swallowed, skipped, or assigned the wrong identity.",
                        proposed_fix_layer="EN polish bibliography identity/gap audit",
                        regression_test="A missing visible number such as 58 is warned or assigned to the unnumbered bibliography item.",
                        extra={"missing_ids": missing[:10], "left_id": left, "right_id": right},
                    )
                )
                saw_gap = True
                break

    if missing_visible_number and (seen_visible or len(seen_ids) >= 2):
        ref_id, block = missing_visible_number[0]
        defects.append(
            make_defect(
                defect_id="P97",
                cc_class="CC-02/CC-13",
                check="Bibliography target is missing its visible reference number",
                severity="error",
                block=block,
                snippet=block.text,
                stage=polish_stage,
                hypothesis="Reference IDs were created, but one or more bibliography entries were left unnumbered for the reader.",
                proposed_fix_layer="EN polish bibliography numbering and reference identity audit",
                regression_test="Every id=ref-N bibliography entry gets visible number N or is explicitly reported.",
                extra={
                    "ref_id": ref_id,
                    "missing_visible_ref_ids": [number for number, _block in missing_visible_number[:12]],
                },
            )
        )

    return defects
