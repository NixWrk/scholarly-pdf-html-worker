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


@dataclass(frozen=True)
class BatchIdReconciliation:
    parsed_by_id: dict[int, str]
    expected_ids: list[int]
    lenient_missing_id: int | None
    lenient_trailing_eos_k: int
    error_reason: str
    debug_message: str

    @property
    def ok(self) -> bool:
        return not self.error_reason


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


def reconcile_batch_ids(
    parsed_by_id: dict[int, str],
    source_segments: Sequence[str],
) -> BatchIdReconciliation:
    segment_count = len(source_segments)
    parsed_by_id = dict(parsed_by_id)
    expected_ids = list(range(1, segment_count + 1))
    expected_ids_set = set(expected_ids)
    found_ids_set = set(parsed_by_id.keys())
    missing_ids = sorted(expected_ids_set - found_ids_set)
    extra_ids = sorted(found_ids_set - expected_ids_set)
    lenient_missing_id: int | None = None
    lenient_trailing_eos_k = 0

    if not missing_ids and not extra_ids:
        return BatchIdReconciliation(
            parsed_by_id=parsed_by_id,
            expected_ids=expected_ids,
            lenient_missing_id=None,
            lenient_trailing_eos_k=0,
            error_reason="",
            debug_message="",
        )

    lenient_missing_limit = segment_count // 10
    if (
        lenient_missing_limit >= 1
        and not extra_ids
        and len(missing_ids) == 1
        and len(parsed_by_id) == segment_count - 1
    ):
        lenient_missing_id = missing_ids[0]
        parsed_by_id[lenient_missing_id] = source_segments[lenient_missing_id - 1]
        return BatchIdReconciliation(
            parsed_by_id=parsed_by_id,
            expected_ids=expected_ids,
            lenient_missing_id=lenient_missing_id,
            lenient_trailing_eos_k=0,
            error_reason="",
            debug_message="",
        )

    if not extra_ids:
        trailing_limit = max(1, segment_count // 3)
        trailing_suffix = list(range(segment_count - len(missing_ids) + 1, segment_count + 1))
        if (
            missing_ids == trailing_suffix
            and len(missing_ids) <= trailing_limit
            and len(parsed_by_id) == segment_count - len(missing_ids)
        ):
            lenient_trailing_eos_k = len(missing_ids)
            for missing_id in missing_ids:
                parsed_by_id[missing_id] = source_segments[missing_id - 1]
            return BatchIdReconciliation(
                parsed_by_id=parsed_by_id,
                expected_ids=expected_ids,
                lenient_missing_id=None,
                lenient_trailing_eos_k=lenient_trailing_eos_k,
                error_reason="",
                debug_message="",
            )

    debug_message = (
        "batch_fail reason=id_mismatch "
        f"missing={format_int_list(missing_ids)} "
        f"extra={format_int_list(extra_ids)}"
    )
    error_reason = (
        "id_mismatch "
        f"missing={format_int_list(missing_ids)} "
        f"extra={format_int_list(extra_ids)}"
    )
    return BatchIdReconciliation(
        parsed_by_id=parsed_by_id,
        expected_ids=expected_ids,
        lenient_missing_id=None,
        lenient_trailing_eos_k=0,
        error_reason=error_reason,
        debug_message=debug_message,
    )
