from zoteropdf2md import gemma_html
from zoteropdf2md.translation.prompt_guards import (
    apply_prompt_leak_mask,
    has_visible_prompt_leak,
    is_translator_refusal,
    sanitize_prompt_leak_segment,
    strip_prompt_leak_echo,
    strip_source_echo,
)


def test_translator_refusal_detector_matches_common_meta_outputs() -> None:
    assert is_translator_refusal("I cannot translate this without more context.")
    assert is_translator_refusal("Не могу перевести без дополнительного контекста.")
    assert not is_translator_refusal("The electrode array was implanted successfully.")


def test_strip_source_echo_removes_labeled_original_tail() -> None:
    translated = "Translation: Готовый перевод.\n\nOriginal text: Source paragraph."

    assert strip_source_echo(translated, "Source paragraph.") == "Готовый перевод."


def test_strip_source_echo_removes_repeated_source_block() -> None:
    translated = "Готовый перевод.\n\nSource paragraph with spacing."

    assert strip_source_echo(translated, "Source paragraph with   spacing.") == "Готовый перевод."


def test_prompt_leak_echo_cleanup_preserves_translation_tail() -> None:
    leaked = "Here is the translation according to the rules: Готовый перевод."

    assert strip_prompt_leak_echo(leaked) == "Готовый перевод."


def test_visible_prompt_leak_segment_falls_back_when_cleanup_still_leaks() -> None:
    translated, changed = sanitize_prompt_leak_segment(
        "Original segment.",
        "  Rules: Output only the translation, nothing else.  ",
    )

    assert changed
    assert translated == "Original segment."


def test_apply_prompt_leak_mask_masks_translation_prefixes() -> None:
    masked, token_map = apply_prompt_leak_mask("Translation: Body. Source: Tail.")

    assert masked == '<z2m-p id="0"/>Body. <z2m-p id="1"/>Tail.'
    assert token_map == {
        '<z2m-p id="0"/>': "Translation: ",
        '<z2m-p id="1"/>': "Source: ",
    }


def test_gemma_html_reexports_prompt_guard_helpers_for_compatibility() -> None:
    assert gemma_html._strip_source_echo is strip_source_echo
    assert gemma_html._strip_prompt_leak_echo is strip_prompt_leak_echo
    assert gemma_html._has_visible_prompt_leak is has_visible_prompt_leak
    assert gemma_html._is_translator_refusal is is_translator_refusal
