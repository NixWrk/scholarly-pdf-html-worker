from __future__ import annotations

from zoteropdf2md.translation.short_guards import (
    apply_short_translation_guard,
    short_translation_guard_reason,
    should_preserve_tiny_fragment,
)


def test_should_preserve_tiny_fragment_keeps_units_and_technical_tokens() -> None:
    assert should_preserve_tiny_fragment("<span>5 mm</span>") is True
    assert should_preserve_tiny_fragment("<i>ECoG</i>") is True
    assert should_preserve_tiny_fragment("a") is False


def test_short_translation_guard_rejects_changed_protected_fragment() -> None:
    assert short_translation_guard_reason("<i>ECoG</i>", "электрокортикограмма") == (
        "protected_tiny_fragment_changed"
    )


def test_short_translation_guard_rejects_meta_and_overgenerated_outputs() -> None:
    assert short_translation_guard_reason("procedure", "depending on the context") == (
        "short_meta_translation"
    )
    assert short_translation_guard_reason("protocol", "1. вариант; 2. другой вариант; 3. третий") == (
        "short_variant_list"
    )


def test_apply_short_translation_guard_returns_source_when_rejected() -> None:
    guarded, reason = apply_short_translation_guard("TiN", "нитрид титана")

    assert guarded == "TiN"
    assert reason == "protected_tiny_fragment_changed"


def test_apply_short_translation_guard_allows_normal_short_translation() -> None:
    guarded, reason = apply_short_translation_guard("opening", "открытие")

    assert guarded == "открытие"
    assert reason is None
