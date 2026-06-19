from __future__ import annotations

import re
from typing import Any

from pdf_html_polish.quality_loop.audit_raw_blocks import Block, Defect, line_at, snippet_at


HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
HTML_TAG_RE = re.compile(r"<html(?:\s|>)", re.IGNORECASE)
BODY_TAG_RE = re.compile(r"<body(?:\s|>)", re.IGNORECASE)
FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:FIGURE\s+\d+\s*\||Figure\s+\d+\s*[.:]|Fig\.\s+\d+\s*\.)",
    re.IGNORECASE,
)
ESCAPED_ANCHOR_RE = re.compile(r"&lt;\s*/?\s*a(?:\s|&gt;|>)", re.IGNORECASE)
REFERENCES_RE = re.compile(
    r"\b(?:references|bibliography|works cited|literature cited)\b",
    re.IGNORECASE,
)
MOJIBAKE_MICRO = "\u0412\u00b5"


def major_tag_defects(text: str) -> list[Defect]:
    defects: list[Defect] = []
    checks = [
        ("html", HTML_TAG_RE, re.compile(r"</html\s*>", re.IGNORECASE)),
        ("body", BODY_TAG_RE, re.compile(r"</body\s*>", re.IGNORECASE)),
    ]
    for tag, open_re, close_re in checks:
        opens = len(open_re.findall(text))
        closes = len(close_re.findall(text))
        if opens == 0 or closes == 0 or opens != closes:
            defects.append(
                Defect(
                    id="R02",
                    check="HTML has <html>, <body>, balanced major closing tags",
                    severity="error",
                    snippet=f"{tag}: open={opens}, close={closes}",
                    hypothesis="Marker emitted malformed HTML or the stage artifact was truncated.",
                    proposed_fix_layer="Marker output capture or raw-stage validation",
                    regression_test="Audit R02 over all canonical EN raw artifacts.",
                    extra={"tag": tag, "open": opens, "close": closes},
                )
            )
    return defects


def caption_without_image_defects(blocks: list[Block], *, window: int = 3) -> list[Defect]:
    defects: list[Defect] = []
    for block in blocks:
        if not FIGURE_CAPTION_RE.search(block.text):
            continue
        start = max(0, block.index - window)
        stop = min(len(blocks), block.index + window + 1)
        if any(neighbor.has_img for neighbor in blocks[start:stop]):
            continue
        defects.append(
            Defect(
                id="R05",
                check="Figure label has nearby image before/after within a small block window",
                severity="warning",
                snippet=block.text[:260],
                line=block.line,
                hypothesis="A figure caption exists, but Marker did not keep a nearby figure image in the raw HTML.",
                proposed_fix_layer="classify as Marker/PDF extraction defect unless a documented fallback is added",
                regression_test="Audit caption-to-image proximity for all canonical EN raw artifacts.",
                extra={"block_index": block.index, "window": window},
            )
        )
    return defects


def heading_ocr_defects(blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    for index, block in enumerate(blocks):
        if block.tag not in HEADING_TAGS:
            continue
        next_block = blocks[index + 1] if index + 1 < len(blocks) else None
        if next_block is None or not FIGURE_CAPTION_RE.search(next_block.text):
            continue
        letters = re.findall(r"[A-Za-z]", block.text)
        uppercase = [char for char in letters if char.isupper()]
        uppercase_ratio = (len(uppercase) / len(letters)) if letters else 0.0
        has_panel_terms = bool(
            re.search(
                r"\b(?:electrode|array|substrate|mask|etching|thickness|stimulating|recording)\b",
                block.text,
                re.IGNORECASE,
            )
        )
        suspicious = (len(block.text) > 120 and has_panel_terms) or (
            len(block.text) > 80 and uppercase_ratio > 0.45 and has_panel_terms
        )
        if suspicious:
            defects.append(
                Defect(
                    id="R06",
                    check="Detect OCR-only figure panels in headings",
                    severity="warning",
                    snippet=block.text[:260],
                    line=block.line,
                    hypothesis="Marker converted figure panel text into a document heading.",
                    proposed_fix_layer="classify as Marker/PDF extraction defect; optionally add downstream fallback policy",
                    regression_test="Audit suspicious heading OCR leakage across the canonical EN raw corpus.",
                    extra={
                        "tag": block.tag,
                        "block_index": block.index,
                        "uppercase_ratio": round(uppercase_ratio, 3),
                    },
                )
            )
    return defects


def all_caps_heading_defects(blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    for block in blocks:
        if block.tag not in HEADING_TAGS or len(block.text) < 40:
            continue
        letters = re.findall(r"[A-Za-z]", block.text)
        if not letters:
            continue
        uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
        if uppercase_ratio < 0.75:
            continue
        if not re.search(r"\b(?:Figure|FIGURE|Table|TABLE|[A-Z]{4,})\b", block.text):
            continue
        defects.append(
            Defect(
                id="R13",
                check="Detect suspicious all-caps figure/table text inside headings",
                severity="warning",
                snippet=block.text[:260],
                line=block.line,
                hypothesis="A figure or table panel was promoted to a heading in EN raw.",
                proposed_fix_layer="Marker/PDF extraction classification or EN polish fallback after corpus review",
                regression_test="Audit all-caps heading leakage across all canonical EN raw artifacts.",
                extra={
                    "tag": block.tag,
                    "block_index": block.index,
                    "uppercase_ratio": round(uppercase_ratio, 3),
                },
            )
        )
    return defects


def references_summary(text: str) -> dict[str, Any]:
    matches = list(REFERENCES_RE.finditer(text))
    if not matches:
        return {"found": False, "line": None, "snippet": None, "post_reference_bytes": 0}
    first = matches[0]
    return {
        "found": True,
        "line": line_at(text, first.start()),
        "snippet": snippet_at(text, first.start(), first.end()),
        "post_reference_bytes": len(text) - first.start(),
    }


def anchor_summary(text: str) -> dict[str, Any]:
    return {
        "anchors": len(re.findall(r"<a\b", text, re.IGNORECASE)),
        "escaped_anchors": len(ESCAPED_ANCHOR_RE.findall(text)),
        "ids": len(re.findall(r"\bid\s*=", text, re.IGNORECASE)),
        "hrefs": len(re.findall(r"\bhref\s*=", text, re.IGNORECASE)),
    }


def mojibake_micro_count(text: str) -> int:
    return len(re.findall(re.escape(MOJIBAKE_MICRO), text))
