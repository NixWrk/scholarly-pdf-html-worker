from __future__ import annotations

from typing import Any

from zoteropdf2md.translation.post_reassembly import (
    PostReassemblyGuardDependencies,
    apply_post_reassembly_guards,
)


def _deps(**overrides: Any) -> PostReassemblyGuardDependencies:
    values = {
        "post_guard_reason": lambda **kwargs: None,
        "find_contiguous_identity_runs": lambda *args, **kwargs: [],
        "build_neighbor_context": lambda seg_idx, grouped_indices: "",
        "recover_context": lambda source, context, label, seg_index: source,
        "recover_single": lambda source, label, seg_index: f"RECOVERED {source}",
        "recover_forced": lambda source, label, seg_index: source,
        "recover_sentencewise": lambda source, label, seg_index: source,
        "try_batch_translate": lambda source_segments, **kwargs: (None, "failed"),
        "is_identity_residual": lambda source, translated: source == translated,
        "sanitize_prompt_leak": lambda source, translated: (translated, False),
        "strip_unexpected_trailing_ellipsis": lambda source, translated: (translated, False),
        "format_int_list": lambda values: "[" + ",".join(str(value) for value in values) + "]",
        "debug": lambda message: None,
    }
    values.update(overrides)
    return PostReassemblyGuardDependencies(**values)


def test_apply_post_reassembly_guards_recovers_prompt_leak() -> None:
    messages: list[str] = []

    result, counts = apply_post_reassembly_guards(
        source_segments=["Source text"],
        translated_segments=["Rules: leaked prompt"],
        max_chunk_chars=1800,
        context_label="batch",
        dependencies=_deps(
            post_guard_reason=lambda **kwargs: "prompt_leak",
            sanitize_prompt_leak=lambda source, translated: ("SANITIZED", True),
            debug=messages.append,
        ),
    )

    assert result == ["SANITIZED"]
    assert counts == {"prompt_leak": 1}
    assert messages == ["batch_lenient reason=prompt_leak seg=1 action=local_segment_recovery"]


def test_apply_post_reassembly_guards_uses_context_recovery_for_identity() -> None:
    result, counts = apply_post_reassembly_guards(
        source_segments=["Previous", "Source text", "Next"],
        translated_segments=["Previous", "Source text", "Next"],
        max_chunk_chars=1800,
        context_label="batch",
        dependencies=_deps(
            post_guard_reason=lambda **kwargs: "identity_residual"
            if kwargs["source_index"] == 1
            else None,
            build_neighbor_context=lambda seg_idx, grouped_indices: "Context text",
            recover_single=lambda source, label, seg_index: source,
            recover_context=lambda source, context, label, seg_index: "Recovered text",
        ),
    )

    assert result == ["Previous", "Recovered text", "Next"]
    assert counts == {"identity_residual": 1, "identity_context_recovery": 1}


def test_apply_post_reassembly_guards_recovers_paragraph_identity_run() -> None:
    result, counts = apply_post_reassembly_guards(
        source_segments=["First source text", "Second source text"],
        translated_segments=["First source text", "Second source text"],
        max_chunk_chars=1800,
        context_label="batch",
        segment_groups=[1, 1],
        dependencies=_deps(
            post_guard_reason=lambda **kwargs: "identity_residual",
            find_contiguous_identity_runs=lambda *args, **kwargs: [(0, 1)],
            try_batch_translate=lambda source_segments, **kwargs: (["Первый", "Второй"], "ok"),
        ),
    )

    assert result == ["Первый", "Второй"]
    assert counts == {"identity_residual_paragraph": 1}
