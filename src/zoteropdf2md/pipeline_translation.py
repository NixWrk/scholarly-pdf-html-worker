"""Legacy translation notices for the conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .gemma_html import language_name_for_code, normalize_language_code
from .pipeline_options import PipelineOptions


@dataclass(frozen=True)
class LegacyTranslationStatus:
    language_code: str
    language_name: str


def log_legacy_translation_config(options: PipelineOptions, log: Callable[[str], None]) -> None:
    if not options.translate_html_with_gemma:
        return
    log(
        "Gemma config: "
        f"backend={options.translation_backend}, "
        f"target_language={options.translation_target_language_code}, "
        f"source_language={options.translation_source_language}, "
        f"model_ref={options.translation_model_ref}, "
        f"max_input_tokens={options.translation_max_input_tokens}, "
        f"context_window_segments={options.translation_context_window_segments}, "
        f"context_overlap_segments={options.translation_context_overlap_segments}, "
        f"context_max_window_chars={options.translation_context_max_window_chars}, "
        f"quality_gate={options.translation_enable_en_residual_quality_gate}, "
        f"quality_gate_max_segments={options.translation_en_residual_quality_gate_max_segments}"
    )


def log_externalized_translation_notice(
    options: PipelineOptions,
    log: Callable[[str], None],
) -> LegacyTranslationStatus:
    language_code = normalize_language_code(options.translation_target_language_code)
    language_name = language_name_for_code(language_code)
    log(
        "Gemma HTML translation is handled by the package translation runner, "
        "not by the PDF conversion pipeline. Use pdf-html-translate "
        "for 03.ru.translate.html output."
    )
    return LegacyTranslationStatus(language_code=language_code, language_name=language_name)


def log_non_html_translation_skip(log: Callable[[str], None]) -> None:
    log(
        "Gemma translation enabled, but current group output format is not HTML. "
        "Translation skipped for this group."
    )
