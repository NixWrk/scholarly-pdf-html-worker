from pathlib import Path

import pytest

from zoteropdf2md import gemma_html
from zoteropdf2md.translation.languages import (
    DEFAULT_GEMMA_TARGET_LANGUAGE,
    language_name_for_code,
    normalize_language_code,
    translated_html_output_path,
)


def test_normalize_language_code_accepts_codes_names_and_defaults() -> None:
    assert normalize_language_code(None) == DEFAULT_GEMMA_TARGET_LANGUAGE
    assert normalize_language_code("") == DEFAULT_GEMMA_TARGET_LANGUAGE
    assert normalize_language_code("RU") == "ru"
    assert normalize_language_code("Russian") == "ru"
    assert normalize_language_code("Chinese") == "zh"


def test_normalize_language_code_rejects_unknown_language() -> None:
    with pytest.raises(ValueError, match="Unsupported translation language"):
        normalize_language_code("Klingon")


def test_language_name_and_output_path_helpers() -> None:
    assert language_name_for_code("de") == "German"
    assert translated_html_output_path(Path("article.html"), "Russian") == Path("article.ru.html")


def test_gemma_html_reexports_translation_language_helpers() -> None:
    assert gemma_html.normalize_language_code is normalize_language_code
    assert gemma_html.translated_html_output_path is translated_html_output_path
