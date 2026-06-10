"""Translation language configuration shared across pipeline entry points."""

from __future__ import annotations

from pathlib import Path


DEFAULT_GEMMA_MODEL = "p6_google_gemma-4-26b-a4b@q6_k"
DEFAULT_GEMMA_TARGET_LANGUAGE = "ru"
GEMMA_LANGUAGE_CHOICES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("ru", "Russian"),
    ("de", "German"),
    ("zh", "Chinese"),
)

_LANGUAGE_NAME_BY_CODE = dict(GEMMA_LANGUAGE_CHOICES)
_LANGUAGE_CODE_BY_NAME = {name.lower(): code for code, name in GEMMA_LANGUAGE_CHOICES}


def normalize_language_code(value: str | None) -> str:
    if value is None:
        return DEFAULT_GEMMA_TARGET_LANGUAGE

    raw = value.strip()
    if not raw:
        return DEFAULT_GEMMA_TARGET_LANGUAGE

    lowered = raw.lower()
    if lowered in _LANGUAGE_NAME_BY_CODE:
        return lowered

    by_name = _LANGUAGE_CODE_BY_NAME.get(lowered)
    if by_name is not None:
        return by_name

    supported = ", ".join(code for code, _ in GEMMA_LANGUAGE_CHOICES)
    raise ValueError(f"Unsupported translation language '{value}'. Supported codes: {supported}")


def language_name_for_code(language_code: str) -> str:
    normalized = normalize_language_code(language_code)
    return _LANGUAGE_NAME_BY_CODE.get(normalized, normalized)


def translated_html_output_path(source_html_path: Path, language_code: str) -> Path:
    normalized = normalize_language_code(language_code)
    return source_html_path.with_name(f"{source_html_path.stem}.{normalized}.html")
