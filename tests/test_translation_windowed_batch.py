from __future__ import annotations

from typing import Any

from zoteropdf2md.translation.windowed_batch import (
    WindowedBatchDependencies,
    try_windowed_batch_translate_with_reason,
)


def _deps(**overrides: object) -> WindowedBatchDependencies:
    values = {
        "try_batch_translate": lambda segments, **_kwargs: ([f"T:{segment}" for segment in segments], "ok"),
        "recover_single": lambda segment, _max_chars, _label, _seg_index: f"R:{segment}",
        "apply_post_reassembly_guards": lambda _source, translated, _max_chars, _label, _groups: (translated, {}),
        "debug": lambda _message: None,
    }
    values.update(overrides)
    return WindowedBatchDependencies(**values)  # type: ignore[arg-type]


def test_windowed_batch_stores_only_core_segments_from_overlapped_windows() -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def try_batch(segments: list[str], **kwargs: Any) -> tuple[list[str], str]:
        calls.append((list(segments), dict(kwargs)))
        return [f"T:{segment}" for segment in segments], "ok"

    result, reason = try_windowed_batch_translate_with_reason(
        ["s0", "s1", "s2", "s3", "s4"],
        window_segments=2,
        overlap_segments=1,
        max_window_chars=5000,
        segment_groups=[0, 0, 1, 1, 2],
        mask_abbrev_flags=[True, False, True, False, True],
        dependencies=_deps(try_batch_translate=try_batch),
    )

    assert result == ["T:s0", "T:s1", "T:s2", "T:s3", "T:s4"]
    assert reason == "ok"
    assert [call[0] for call in calls] == [
        ["s0", "s1", "s2"],
        ["s1", "s2", "s3", "s4"],
        ["s3", "s4"],
    ]
    assert calls[1][1]["segment_groups"] == [0, 1, 1, 2]
    assert calls[1][1]["mask_abbrev_flags"] == [False, True, False, True]
    assert calls[1][1]["enable_identity_residual_guard"] is False
    assert calls[1][1]["enable_identity_context_recovery"] is False


def test_windowed_batch_bisects_failed_windows_to_leaf_recovery() -> None:
    messages: list[str] = []
    recovered: list[tuple[str, int, str, int]] = []

    def recover_single(segment: str, max_chunk_chars: int, context_label: str, seg_index: int) -> str:
        recovered.append((segment, max_chunk_chars, context_label, seg_index))
        return f"R:{segment}"

    result, reason = try_windowed_batch_translate_with_reason(
        ["s0", "s1", "s2", "s3"],
        window_segments=4,
        overlap_segments=0,
        max_window_chars=1000,
        dependencies=_deps(
            try_batch_translate=lambda _segments, **_kwargs: (None, "bad_window"),
            recover_single=recover_single,
            debug=messages.append,
        ),
    )

    assert result == ["R:s0", "R:s1", "R:s2", "R:s3"]
    assert reason == "ok"
    assert recovered == [
        ("s0", 1000, "window", 1),
        ("s1", 1000, "window", 2),
        ("s2", 1000, "window", 3),
        ("s3", 1000, "window", 4),
    ]
    assert messages == [
        "window_fail core=[0:4) extended=[0:4) reason=bad_window",
        "window_fail core=[0:2) extended=[0:2) reason=bad_window",
        "leaf_per_segment core=[0:2) extended=[0:2) reason=bad_window",
        "window_fail core=[2:4) extended=[2:4) reason=bad_window",
        "leaf_per_segment core=[2:4) extended=[2:4) reason=bad_window",
    ]


def test_windowed_batch_reports_post_reassembly_recovery_counts() -> None:
    post_calls: list[tuple[list[str], list[str], int, str, list[int | None] | None]] = []

    def apply_post(
        source_segments: list[str],
        translated_segments: list[str],
        max_chunk_chars: int,
        context_label: str,
        segment_groups: list[int | None] | None,
    ) -> tuple[list[str], dict[str, int]]:
        post_calls.append((source_segments, translated_segments, max_chunk_chars, context_label, segment_groups))
        return [f"{segment}!" for segment in translated_segments], {
            "identity_terminal": 1,
            "prompt_leak": 2,
        }

    result, reason = try_windowed_batch_translate_with_reason(
        ["s0", "s1"],
        window_segments=2,
        overlap_segments=0,
        max_window_chars=100,
        segment_groups=[3, 3],
        dependencies=_deps(apply_post_reassembly_guards=apply_post),
    )

    assert result == ["T:s0!", "T:s1!"]
    assert reason == "ok_window_leak_recovery count=3 details=identity_terminal=1,prompt_leak=2"
    assert post_calls == [(
        ["s0", "s1"],
        ["T:s0", "T:s1"],
        256,
        "window",
        [3, 3],
    )]
