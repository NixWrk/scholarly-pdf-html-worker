"""Batch translation marker protocol helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Sequence


BATCH_ITEM_PATTERN = re.compile(
    r"<z2m-i(\d+)\s*/>([\s\S]*?)(?=<z2m-i\d+\s*/>|\Z)",
    re.IGNORECASE,
)

INTERNAL_MARKER_LEAK_PATTERN = re.compile(
    r"<\s*z2m-[^>]*>|@@Z2M(?:\\?_)?[A-Z0-9_]+@{0,2}",
    re.IGNORECASE,
)

MAX_BATCH_CHARS = 80_000
WINDOW_BATCH_TARGET_SEGMENTS = 8
WINDOW_BATCH_OVERLAP_SEGMENTS = 1
MAX_WINDOW_BATCH_CHARS = 40_000


@dataclass(frozen=True)
class ParsedBatchItems:
    parsed_by_id: dict[int, str]
    duplicate_ids: list[int]
    block_count: int


def build_batch_text(masked_segments: Sequence[str]) -> str:
    return "".join(f"<z2m-i{i}/>{segment}" for i, segment in enumerate(masked_segments, start=1))


def format_int_list(values: list[int], *, max_items: int = 8) -> str:
    if not values:
        return "[]"
    if len(values) <= max_items:
        return "[" + ",".join(str(v) for v in values) + "]"
    head = ",".join(str(v) for v in values[:max_items])
    return f"[{head},...+{len(values) - max_items}]"


def parse_batch_items(translated_batch: str) -> ParsedBatchItems:
    matches = list(BATCH_ITEM_PATTERN.finditer(translated_batch))
    parsed_by_id: dict[int, str] = {}
    duplicate_ids: set[int] = set()
    for match in matches:
        item_id = int(match.group(1))
        item_text = match.group(2)
        if item_id in parsed_by_id:
            duplicate_ids.add(item_id)
            continue
        parsed_by_id[item_id] = item_text
    return ParsedBatchItems(
        parsed_by_id=parsed_by_id,
        duplicate_ids=sorted(duplicate_ids),
        block_count=len(matches),
    )
