"""P62 missing-figure warning classification helpers."""

from __future__ import annotations

import re
from typing import Any, Callable

from pdf_html_polish.quality_loop.audit_blocks import Block
from pdf_html_polish.semantic_labels import (
    extended_data_figure_key_from_visible_number,
    supplementary_figure_key_from_visible_number,
)


SEMANTIC_FIGURE_WARNING_TEXT_RE = re.compile(
    r"\bFigure\s+(?P<label>(?:extended-data|supplementary)-[A-Za-z0-9][A-Za-z0-9.\-\u2010-\u2014]*)\b",
    re.IGNORECASE,
)
EXTENDED_DATA_FIGURE_LABEL_TEXT_RE = re.compile(
    r"\bExtended\s+Data\s+Fig(?:ure)?\.?\s+"
    r"(?P<label>\d+[A-Za-z]?|\d+(?:\s*[.\-\u2010-\u2014]\s*\d+(?!\s*[A-Za-z]))+)\b",
    re.IGNORECASE,
)
SUPPLEMENTARY_FIGURE_LABEL_TEXT_RE = re.compile(
    r"\bSupplement(?:ary|al)?\s+Fig(?:ure)?\.?\s+"
    r"(?P<label>\d+[A-Za-z]?|\d+(?:\s*[.\-\u2010-\u2014]\s*\d+(?!\s*[A-Za-z]))+)\b",
    re.IGNORECASE,
)
FIGURE_LABEL_TEXT_RE = re.compile(
    r"\b(?:Fig(?:ure)?\.?|Figure)\s+"
    r"(?P<label>\d+[A-Za-z]?|\d+(?:\s*[.\-\u2010-\u2014]\s*\d+(?!\s*[A-Za-z]))+)\b",
    re.IGNORECASE,
)


def has_nearby_image(blocks: list[Block], index: int, *, window: int = 6) -> bool:
    start = max(0, index - window)
    stop = min(len(blocks), index + window + 1)
    return any(block.has_figure_visual for block in blocks[start:stop])


def normalize_figure_label_key(label: str) -> str | None:
    label = re.sub(r"\s+", "", label)
    label = re.sub(r"[.\-\u2010-\u2014]+", "-", label)
    return label.strip("-").lower() or None


def figure_label_from_text(text: str) -> str | None:
    semantic_warning_match = SEMANTIC_FIGURE_WARNING_TEXT_RE.search(text)
    if semantic_warning_match is not None:
        return normalize_figure_label_key(semantic_warning_match.group("label"))
    extended_data_match = EXTENDED_DATA_FIGURE_LABEL_TEXT_RE.search(text)
    if extended_data_match is not None:
        return extended_data_figure_key_from_visible_number(extended_data_match.group("label"))
    supplementary_match = SUPPLEMENTARY_FIGURE_LABEL_TEXT_RE.search(text)
    if supplementary_match is not None:
        return supplementary_figure_key_from_visible_number(supplementary_match.group("label"))
    match = FIGURE_LABEL_TEXT_RE.search(text)
    if match is None:
        return None
    return normalize_figure_label_key(match.group("label"))


def figure_label_from_id(value: str) -> str | None:
    match = re.fullmatch(r"fig-(?P<label>[A-Za-z0-9][A-Za-z0-9.\-\u2010-\u2014]*)", value, re.IGNORECASE)
    if match is None:
        return None
    return normalize_figure_label_key(match.group("label"))


def figure_unit_label(block: Block) -> str | None:
    if block.tag != "div" or "z2m-figure-unit" not in block.classes:
        return None
    return figure_label_from_id(block.id)


def nearest_figure_label(
    blocks: list[Block],
    index: int,
    *,
    direction: int,
    window: int = 5,
) -> tuple[str | None, int | None]:
    if direction == 0:
        raise ValueError("direction must be non-zero")
    stop = min(len(blocks), index + window + 1) if direction > 0 else max(-1, index - window - 1)
    scan = range(index + direction, stop, direction)
    for candidate_index in scan:
        label = figure_label_from_text(blocks[candidate_index].text)
        if label is not None:
            return label, abs(candidate_index - index)
    return None, None


def nearby_image_offsets(
    blocks: list[Block],
    index: int,
    *,
    label: str | None = None,
    window: int = 8,
    looks_like_figure_caption: Callable[[Block], bool] | None = None,
) -> list[int]:
    def allows_missing_warning_image_scan(block: Block) -> bool:
        unit_label = figure_unit_label(block)
        if label is not None and unit_label is not None and unit_label != label:
            return False
        block_label = figure_label_from_text(block.text)
        if label is not None and block_label is not None and block_label != label:
            if (
                block.id.startswith("fig-")
                or block.classes & {"z2m-figure-caption", "z2m-figure-target"}
                or (looks_like_figure_caption is not None and looks_like_figure_caption(block))
            ):
                return False
        if block.has_figure_visual:
            return True
        if not block.text.strip():
            return True
        if block.tag in {"td", "th"}:
            return True
        if block.classes & {
            "z2m-missing-figure-warning",
            "z2m-missing-figure-unit",
            "z2m-figure-caption",
            "z2m-figure-target",
        }:
            return True
        if block.tag == "div" and block.classes & {"z2m-float-unit", "z2m-figure-unit"}:
            return True
        return block_label is not None

    offsets: list[int] = []
    for direction in (-1, 1):
        stop = min(len(blocks), index + window + 1) if direction > 0 else max(-1, index - window - 1)
        for candidate_index in range(index + direction, stop, direction):
            block = blocks[candidate_index]
            if block.has_figure_visual:
                if not allows_missing_warning_image_scan(block):
                    break
                offsets.append(candidate_index - index)
                continue
            if not allows_missing_warning_image_scan(block):
                break
    return sorted(offsets)


def find_warning_block_index(blocks: list[Block], warning: Block) -> int | None:
    for index, candidate in enumerate(blocks):
        if "z2m-missing-figure-warning" not in candidate.classes:
            continue
        if candidate.line == warning.line and candidate.text == warning.text:
            return index
    for index, candidate in enumerate(blocks):
        if "z2m-missing-figure-warning" in candidate.classes and candidate.text == warning.text:
            return index
    return None


def has_nearby_missing_figure_warning(blocks: list[Block], index: int, *, window: int = 2) -> bool:
    start = max(0, index - window)
    stop = min(len(blocks), index + window + 1)
    return any("z2m-missing-figure-warning" in block.classes for block in blocks[start:stop])


def is_handled_missing_figure_block(block: Block) -> bool:
    return (
        "z2m-missing-figure-unit" in block.classes
        and "z2m-missing-figure-warning" in block.raw
        and "z2m-figure-caption" in block.raw
    )


def classify_missing_figure_warning(
    warning: Block,
    polish_blocks: list[Block],
    *,
    looks_like_figure_caption: Callable[[Block], bool] | None = None,
) -> dict[str, Any]:
    label = figure_label_from_text(warning.text)
    index = find_warning_block_index(polish_blocks, warning)
    extra: dict[str, Any] = {
        "figure_label": label,
        "p62_subtype": "unclassified",
    }
    if warning.attrs.get("data-z2m-origin") == "caption-only-target":
        extra["quality_counted"] = False
        extra["warning_origin"] = "caption-only-target"
    if index is not None:
        context_start = max(0, index - 4)
        context_stop = min(len(polish_blocks), index + 5)
        for context_block in polish_blocks[context_start:context_stop]:
            if not is_handled_missing_figure_block(context_block):
                continue
            unit_label = figure_unit_label(context_block) or figure_label_from_text(context_block.text)
            if label is not None and unit_label is not None and unit_label != label:
                continue
            extra["quality_counted"] = False
            extra.setdefault("warning_origin", "missing-figure-unit")
            break
    if index is None:
        if not any(block.has_figure_visual for block in polish_blocks):
            extra["p62_subtype"] = "no_nearby_image"
            return {
                "defect_id": "P62",
                "check": "Missing-figure warning has no nearby image",
                "hypothesis": "The final HTML is explicit about a missing source image, and no image was found in the block context.",
                "proposed_fix_layer": "Marker image extraction diagnostics or review packaging",
                "extra": extra,
            }
        return {
            "defect_id": "P62B",
            "check": "Missing-figure warning could not be placed in block context",
            "hypothesis": "The final HTML warns about a missing figure, but audit could not classify the surrounding image context.",
            "proposed_fix_layer": "EN polish missing-figure warning classifier",
            "extra": extra,
        }

    image_offsets = nearby_image_offsets(
        polish_blocks,
        index,
        label=label,
        looks_like_figure_caption=looks_like_figure_caption,
    )
    previous_image_offsets = [offset for offset in image_offsets if offset < 0]
    next_image_offsets = [offset for offset in image_offsets if offset > 0]
    previous_label, previous_label_distance = nearest_figure_label(
        polish_blocks,
        index,
        direction=-1,
    )
    next_label, next_label_distance = nearest_figure_label(
        polish_blocks,
        index,
        direction=1,
    )
    extra.update(
        {
            "block_index": index,
            "previous_image_offsets": previous_image_offsets[:4],
            "next_image_offsets": next_image_offsets[:4],
            "previous_figure_label": previous_label,
            "previous_figure_label_distance": previous_label_distance,
            "next_figure_label": next_label,
            "next_figure_label_distance": next_label_distance,
        }
    )

    nearest_previous_image = min((abs(offset) for offset in previous_image_offsets), default=None)
    nearest_next_image = min(next_image_offsets, default=None)
    same_next_caption = label is not None and next_label == label
    same_previous_caption = label is not None and previous_label == label
    previous_label_does_not_intercept_image = (
        previous_label is None
        or previous_label == label
        or nearest_previous_image is None
        or previous_label_distance is None
        or previous_label_distance > nearest_previous_image
    )
    if (
        same_next_caption
        and previous_label_does_not_intercept_image
        and (
            nearest_previous_image is not None
            and nearest_previous_image <= 4
            or nearest_next_image is not None
            and nearest_next_image <= 4
        )
    ) or (same_previous_caption and nearest_previous_image is not None and nearest_previous_image <= 4):
        extra["p62_subtype"] = "same_label_image_near_warning"
        return {
            "defect_id": "P62A",
            "check": "Missing-figure warning is adjacent to a same-label image/caption",
            "hypothesis": "The figure image appears to be present, but EN polish inserted a stale missing-image warning next to it.",
            "proposed_fix_layer": "EN polish figure image/caption association",
            "extra": extra,
        }

    if not image_offsets and (
        same_next_caption
        and next_label_distance is not None
        and next_label_distance <= 2
        or same_previous_caption
        and previous_label_distance is not None
        and previous_label_distance <= 2
    ):
        extra["quality_counted"] = False
        extra.setdefault("warning_origin", "caption-only-caption")

    if image_offsets:
        extra["p62_subtype"] = "nearby_image_ambiguous_label"
        return {
            "defect_id": "P62B",
            "check": "Missing-figure warning has nearby image content but ambiguous label match",
            "hypothesis": "The article contains nearby image content, but the warning could not be confidently matched to the same figure label.",
            "proposed_fix_layer": "EN polish figure image/caption association and manual review packaging",
            "extra": extra,
        }

    extra["p62_subtype"] = "no_nearby_image"
    return {
        "defect_id": "P62",
        "check": "Missing-figure warning has no nearby image",
        "hypothesis": "The final HTML is explicit about a missing source image, and no nearby image was found in the block context.",
        "proposed_fix_layer": "Marker image extraction diagnostics or review packaging",
        "extra": extra,
    }
