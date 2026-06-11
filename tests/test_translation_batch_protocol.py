from zoteropdf2md import gemma_html
from zoteropdf2md.translation.batch_protocol import (
    INTERNAL_MARKER_LEAK_PATTERN,
    build_batch_text,
    format_int_list,
    parse_batch_items,
    reconcile_batch_ids,
)


def test_build_batch_text_uses_id_addressed_markers() -> None:
    assert build_batch_text(["First", "Second"]) == "<z2m-i1/>First<z2m-i2/>Second"


def test_parse_batch_items_preserves_first_duplicate_and_reports_duplicate_id() -> None:
    parsed = parse_batch_items("<z2m-i1/>A<z2m-i2/>B<z2m-i1/>C")

    assert parsed.block_count == 3
    assert parsed.parsed_by_id == {1: "A", 2: "B"}
    assert parsed.duplicate_ids == [1]


def test_format_int_list_compacts_long_lists() -> None:
    assert format_int_list([]) == "[]"
    assert format_int_list([1, 2, 3]) == "[1,2,3]"
    assert format_int_list(list(range(1, 11)), max_items=4) == "[1,2,3,4,...+6]"


def test_internal_marker_leak_pattern_detects_batch_and_sentinel_protocol() -> None:
    assert INTERNAL_MARKER_LEAK_PATTERN.search("<z2m-i1/>")
    assert INTERNAL_MARKER_LEAK_PATTERN.search("@@Z2M_A0@@")


def test_reconcile_batch_ids_accepts_exact_id_set() -> None:
    result = reconcile_batch_ids({1: "A", 2: "B"}, ["source A", "source B"])

    assert result.ok
    assert result.parsed_by_id == {1: "A", 2: "B"}
    assert result.expected_ids == [1, 2]
    assert result.lenient_missing_id is None
    assert result.lenient_trailing_eos_k == 0


def test_reconcile_batch_ids_fills_single_lenient_missing_id() -> None:
    sources = [f"source {idx}" for idx in range(1, 12)]
    parsed = {idx: f"T{idx}" for idx in range(1, 12) if idx != 5}

    result = reconcile_batch_ids(parsed, sources)

    assert result.ok
    assert result.lenient_missing_id == 5
    assert result.parsed_by_id[5] == "source 5"


def test_reconcile_batch_ids_fills_trailing_eos_missing_ids() -> None:
    result = reconcile_batch_ids({1: "A", 2: "B"}, ["source A", "source B", "source C"])

    assert result.ok
    assert result.lenient_trailing_eos_k == 1
    assert result.parsed_by_id == {1: "A", 2: "B", 3: "source C"}


def test_reconcile_batch_ids_reports_hard_id_mismatch() -> None:
    result = reconcile_batch_ids({1: "A", 3: "C", 99: "extra"}, ["source A", "source B", "source C"])

    assert not result.ok
    assert result.error_reason == "id_mismatch missing=[2] extra=[99]"
    assert result.debug_message == "batch_fail reason=id_mismatch missing=[2] extra=[99]"


def test_gemma_html_keeps_legacy_private_batch_aliases() -> None:
    assert gemma_html._format_int_list is format_int_list
    assert gemma_html._build_batch_text is build_batch_text
