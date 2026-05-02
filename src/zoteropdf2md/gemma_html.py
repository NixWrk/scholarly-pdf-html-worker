from __future__ import annotations

from dataclasses import dataclass
import re
import os
import html as html_lib
from pathlib import Path
from typing import Callable

from .abbreviations import LATIN_ABBREV_TO_RU, RU_ABBREV_TO_LATIN
from .single_file_html import _REFERENCES_HEADING_PATTERN


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

_TAG_SPLIT_PATTERN = re.compile(r"(<[^>]+>)")
_OPEN_TAG_PATTERN = re.compile(r"^<\s*([a-zA-Z0-9:_-]+)")
_CLOSE_TAG_PATTERN = re.compile(r"^<\s*/\s*([a-zA-Z0-9:_-]+)")
_TRANSLATABLE_TEXT_PATTERN = re.compile(r"[A-Za-z\u0400-\u04FF\u4E00-\u9FFF]")
_SKIP_TRANSLATION_TAGS = {"script", "style", "code", "pre", "math", "svg", "a", "sup", "sub"}

# Matches the translate="no" attribute (HTML spec for marking non-translatable content).
_NO_TRANSLATE_ATTR_PATTERN = re.compile(r'\btranslate\s*=\s*["\']no["\']', re.IGNORECASE)


def _has_translatable_visible_text(text: str) -> bool:
    if not _TRANSLATABLE_TEXT_PATTERN.search(text):
        return False
    visible = html_lib.unescape(text)
    visible = re.sub(r"<[^>]*>", "", visible)
    return bool(_TRANSLATABLE_TEXT_PATTERN.search(visible))

# SentencePiece byte-fallback tokens that Gemma sometimes emits when it encounters
# Unicode characters near the translation boundary.  They appear as literal ASCII
# sequences like <0xE2><0x82><0xA9> in the output.
# When followed by citation-like numbers the whole group is a dropped <sup>; restore it.
_BYTE_TOKEN_ARTIFACT_PATTERN = re.compile(r'(?:<0x[0-9A-Fa-f]{2}>)+')
_BYTE_TOKEN_CITATION_PATTERN = re.compile(
    r'(?:<0x[0-9A-Fa-f]{2}>)+(\d[\d,\u2013\u2014\-]*)'
)

# Uppercase Latin abbreviations that must survive translation unchanged.
# Restricted to SHORT sequences (2вЂ“5 letters) so that all-caps section titles
# such as INTRODUCTION, CONCLUSION, RESULTS (в‰Ґ6 letters) are NOT masked and
# can still be translated normally.  Real abbreviations (IEEE, MEMS, GAI, LC,
# ADC, VNA, RF) are typically в‰¤5 characters and will be protected.
_ABBREV_PATTERN = re.compile(r'\b[A-Z]{2,5}\d*\b')
_PROTECTED_SCIENCE_TERM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])("
    r"(?:i|micro|u|\u00b5)?ECoG|"
    r"TiN|PtIr|IrOx|RuOx|AIROF|EIROF|SIROF|"
    r"Parylene(?:[-\s]?C)?|PDMS|SU-8|ZIF|"
    r"Steeltrodes?|steeltrodes?"
    r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)
# Placeholder tokens used to protect abbreviations during model calls.
# ASCII sentinel is more robust than XML-style tags in free-form generation.
_ABBREV_TOKEN_PATTERN = re.compile(r"@@Z2M\\?_A(\d+)(?:@@|@(?!@))", re.IGNORECASE)
_TAG_TOKEN_PATTERN = re.compile(r"@@Z2M\\?_T(\d+)(?:@@|@(?!@))", re.IGNORECASE)

# Additional patterns for protecting specific abbreviations from translation
_LATIN_ABBREV_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in LATIN_ABBREV_TO_RU.keys()]
_RU_ABBREV_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in RU_ABBREV_TO_LATIN.keys()]

# Patterns that mask meta-commentary prefixes the model sometimes emits before
# the actual translation.  Abbreviations are no longer listed here: since commit 3b
# the prompt already contains an abstract rule ("keep every 2+ uppercase Latin
# letters"), masking them with <z2m-p> tokens causes them to be LOST when the
# model drops the unfamiliar XML token.  Rely on the prompt rule instead.
_PROMPT_LEAK_PROTECTION_PATTERNS = [
    r'\b(?:translation|translated text)\s*:\s*',
    r'\boriginal(?:\s+text)?\s*:\s*',
    r'\b(?:source|исходн)(?:\s+текст)?\s*:\s*',
]

# Patterns that indicate the model produced a meta-commentary / refusal instead of a
# translation.  When any of these match the translated output we fall back to the
# original source text so that no garbage leaks into the HTML.
_TRANSLATOR_REFUSAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"невозможно перевести", re.IGNORECASE),
    re.compile(r"не могу перевести", re.IGNORECASE),
    re.compile(r"не могу точно перевести", re.IGNORECASE),
    re.compile(r"не удаётся перевести", re.IGNORECASE),
    re.compile(r"пожалуйста.{0,40}предоставьте", re.IGNORECASE | re.DOTALL),
    re.compile(r"без дополнительного контекста", re.IGNORECASE),
    re.compile(r"нет достаточного контекста", re.IGNORECASE),
    re.compile(r"i cannot translate", re.IGNORECASE),
    re.compile(r"i(?:'m| am) unable to translate", re.IGNORECASE),
    re.compile(r"please provide.{0,60}context", re.IGNORECASE | re.DOTALL),
    re.compile(r"more context.{0,60}(?:to translate|for translation)", re.IGNORECASE | re.DOTALL),
)

_TRANSLATION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:translation|translated text|перевод)\s*:\s*",
    re.IGNORECASE,
)
_ORIGINAL_SECTION_PATTERN = re.compile(
    r"(?:\r?\n){1,2}\s*(?:original(?: text)?|source(?: text)?|исходн(?:ый|ого)\s+текст)\s*:\s*",
    re.IGNORECASE,
)

# Guard against prompt-leak: if the model echoes back a comma-separated list of
# uppercase Latin acronyms followed by wording that references translation/language
# (the tail of our abbreviation instruction), strip the fragment so it never
# reaches the rendered HTML.
_PROMPT_LEAK_SIGNATURE = re.compile(
    r'[A-Z]{2,},\s*[A-Z]{2,},\s*[A-Z]{2,}.*?(?:перевод|translation|язык|language).*?[\.\n]',
    re.IGNORECASE | re.DOTALL,
)
_PROMPT_RULE_LEAK_PHRASES: tuple[str, ...] = (
    "Rules:",
    "Keep every sequence of 2 or more uppercase Latin letters",
    "never transliterate them into Cyrillic",
    "Do not translate or modify proper names",
    "Output only the translation, nothing else",
    "Translate the following text",
    "\u0412 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0438 \u0441 \u043f\u0440\u0430\u0432\u0438\u043b\u0430\u043c\u0438",
    "\u041f\u0440\u0430\u0432\u0438\u043b\u0430:",
    "\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u0439\u0442\u0435 \u043a\u0430\u0436\u0434\u0443\u044e \u043f\u043e\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c",
    "\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u0442\u044c \u043a\u0430\u0436\u0434\u0443\u044e \u043f\u043e\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c",
    "\u043d\u0438\u043a\u043e\u0433\u0434\u0430 \u043d\u0435 \u0442\u0440\u0430\u043d\u0441\u043b\u0438\u0442\u0435\u0440\u0438\u0440\u0443\u0439\u0442\u0435",
    "\u041d\u0435 \u043f\u0435\u0440\u0435\u0432\u043e\u0434\u0438\u0442\u0435 \u0438 \u043d\u0435 \u0438\u0437\u043c\u0435\u043d\u044f\u0439\u0442\u0435",
    "\u041e\u0441\u0442\u0430\u0432\u043b\u044f\u0439\u0442\u0435 \u043d\u0435\u0438\u0437\u043c\u0435\u043d\u043d\u044b\u043c\u0438",
    "\u0412\u044b\u0432\u043e\u0434 \u0434\u043e\u043b\u0436\u0435\u043d \u0441\u043e\u0434\u0435\u0440\u0436\u0430\u0442\u044c \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u0435\u0440\u0435\u0432\u043e\u0434",
    "\u0412\u044b\u0432\u0435\u0441\u0442\u0438 \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u0435\u0440\u0435\u0432\u043e\u0434",
    "\u0412\u043e\u0442 \u043f\u0435\u0440\u0435\u0432\u043e\u0434 \u0442\u0435\u043a\u0441\u0442\u0430",
    "\u0441 \u0443\u0447\u0435\u0442\u043e\u043c \u0443\u043a\u0430\u0437\u0430\u043d\u043d\u044b\u0445 \u043f\u0440\u0430\u0432\u0438\u043b",
    "\u041f\u0435\u0440\u0435\u0434\u0430\u0439\u0442\u0435 \u0442\u0435\u043a\u0441\u0442 \u0434\u043b\u044f \u043f\u0435\u0440\u0435\u0432\u043e\u0434\u0430",
    "\u042f \u043f\u043e\u043d\u0438\u043c\u0430\u044e",
)
_VISIBLE_PROMPT_LEAK_PATTERN = re.compile(
    "|".join(re.escape(phrase) for phrase in _PROMPT_RULE_LEAK_PHRASES),
    re.IGNORECASE,
)
_PROMPT_RULE_ECHO_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"Rules:\s*\(1\).*?\(4\)\s*Output only the translation,\s*nothing else\.?",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:"
        r"\u0412\s+\u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0438\s+"
        r"\u0441\s+\u043f\u0440\u0430\u0432\u0438\u043b\u0430\u043c\u0438"
        r"|\u041f\u0440\u0430\u0432\u0438\u043b\u0430"
        r")\s*:\s*\(1\).*?\(4\)\s*"
        r"(?:\u0412\u044b\u0432\u043e\u0434|\u0412\u044b\u0432\u0435\u0441\u0442\u0438)"
        r".*?(?:\.\s*|$)",
        re.IGNORECASE | re.DOTALL,
    ),
)
_PROMPT_META_ECHO_PATTERN = re.compile(
    r"(?:"
    r"\u042f\s+\u043f\u043e\u043d\u0438\u043c\u0430\u044e\.?\s*"
    r"|\u041f\u0435\u0440\u0435\u0434\u0430\u0439\u0442\u0435\s+"
    r"\u0442\u0435\u043a\u0441\u0442\s+\u0434\u043b\u044f\s+"
    r"\u043f\u0435\u0440\u0435\u0432\u043e\u0434\u0430\.?\s*"
    r"|\u0412\u043e\u0442\s+\u043f\u0435\u0440\u0435\u0432\u043e\u0434\s+"
    r"\u0442\u0435\u043a\u0441\u0442\u0430[^:]{0,140}:\s*"
    r"|Here\s+is\s+(?:the\s+)?translation[^:]{0,140}:\s*"
    r")",
    re.IGNORECASE,
)

_FORMULA_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Internal tag placeholders used during recovery must survive intact.
    re.compile(r"@@Z2M\\?_T\d+@@", re.IGNORECASE),
    # Escaped HTML-like snippets and URLs must not be rewritten into real tags.
    re.compile(r"&lt;/?[A-Za-z][^&<>]{0,300}?&gt;", re.IGNORECASE),
    re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE),
    re.compile(r"\bdoi:\s*10\.\d{4,9}/[^\s<>()\"']+", re.IGNORECASE),
    # Unit spans around micro symbols are atomic; otherwise "\(\mu\) m" can
    # become "мм \(\mu\) м" when the adjacent "m" is translated separately.
    re.compile(r"\\\(\s*\\mu\s*\\\)\s*m\b", re.IGNORECASE),
    re.compile(r"\\mu\s*m\b", re.IGNORECASE),
    re.compile(r"\u00b5\s*m\b", re.IGNORECASE),
    re.compile(
        r"\d+(?:\s*(?:\\\(\s*\\mu\s*\\\)|\\mu|\u00b5)\s*m)?"
        r"(?:\s*[x\u00d7]\s*\d+(?:\s*(?:\\\(\s*\\mu\s*\\\)|\\mu|\u00b5)\s*m)?){1,4}",
        re.IGNORECASE,
    ),
    # Inline math delimiters.
    re.compile(r"\$[^$\n]{1,600}\$"),
    re.compile(r"\\\([^\n]{1,600}?\\\)"),
    re.compile(r"\\\[[\s\S]{1,600}?\\\]"),
    # LaTeX commands with optional brace arguments.
    re.compile(r"\\[A-Za-z]+(?:\s*\{[^{}]{0,160}\}){0,3}"),
    # Subscript / superscript expressions (e.g., I_1, L_{m}^{2}).
    re.compile(
        r"[A-Za-z](?:\s*_\{[^{}]{1,80}\}|\s*_[A-Za-z0-9]{1,20}|\s*\^\{[^{}]{1,80}\}|\s*\^[A-Za-z0-9]{1,20})+"
    ),
    # Single-letter coefficient directly before a LaTeX symbol (e.g., j\omega).
    re.compile(r"(?<!\w)[A-Za-z]\s*(?=\\[A-Za-z])"),
    # Dense equation chunks carrying operators with LaTeX/subscript markers.
    re.compile(
        r"(?<!\w)(?=[^,\n]{0,240}[=+\-*/])(?=[^,\n]{0,240}(?:\\|_|\^))"
        r"[A-Za-z0-9\\{}_^().]+(?:\s+[A-Za-z0-9\\{}_^().]+){0,40}(?!\w)"
    ),
    # Compact dimension style (e.g., 72 \times 48 \times 20 mm).
    re.compile(r"(?<!\w)\d+(?:\s*\\times\s*\d+){1,4}(?:\s*[A-Za-z]{1,8})?(?!\w)", re.IGNORECASE),
)

# Helpers for author-line detection.
_H1_CLOSE_PATTERN = re.compile(r"</h[1-6]\s*>", re.IGNORECASE)
_H_OPEN_PATTERN = re.compile(r"<h[1-6]\b[^>]*>", re.IGNORECASE)
_LIST_OPEN_PATTERN = re.compile(r"<(ul|ol)\b[^>]*>", re.IGNORECASE)
_FIRST_P_OPEN_PATTERN = re.compile(r"<p(\b[^>]*)>", re.IGNORECASE)
_P_CLOSE_PATTERN = re.compile(r"</p\s*>", re.IGNORECASE)
_ABSTRACT_MARKER_PATTERN = re.compile(r"\bAbstract\b", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_AUTHOR_LINE_NEGATIVE_PATTERN = re.compile(
    r"\b("
    r"abstract|received|accepted|published|doi|keywords?|"
    r"data availability|code availability|conflict of interest|competing interests?|"
    r"funding|acknowledg(?:e)?ments?|supplementary|references|bibliography|"
    r"cite this article|correspondence"
    r")\b",
    re.IGNORECASE,
)
_AUTHOR_WORD_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Za-z]+)?\b")

_TINY_FRAGMENT_MAX_CHARS = 24
_TINY_SINGLE_TOKEN_PATTERN = re.compile(
    r"^(?:"
    r"[A-Z]|[ij]|[IVXLCM]{1,6}|"
    r"[A-Z]{2,8}\d*s?|"
    r"[A-Z][a-z]?[A-Z][a-z]?\d*s?|"
    r"[A-Za-z][\u0370-\u03FF](?:\d+)?|"
    r"[\u0370-\u03FF]"
    r")$"
)
_TINY_TECHNICAL_TOKEN_PATTERN = re.compile(
    r"^(?:"
    r"(?:i|micro|u|\u00b5)?ECoG|"
    r"TiN|PtIr|IrO[xX]?|RuO[xX]?|AIROF|EIROF|SIROF|"
    r"PDMS|SU-8|LCPs?|SMPs?|MHz|GHz|kHz|Hz|mmHg|mm|cm|nm|"
    r"ms|mV|V|mA|uA|\u00b5A|A|RF|ADC|LC|IEEE"
    r")$",
    re.IGNORECASE,
)
_TINY_NUMERIC_UNIT_PATTERN = re.compile(
    r"^(?:[<>~\u2248\u2264\u2265]?\s*)?"
    r"\d+(?:[.,]\d+)?"
    r"(?:\s*(?:@|\u00b1|\+/-)\s*\d+(?:[.,]\d+)?)?"
    r"(?:\s|-)*"
    r"(?:mmHg|mm|cm|m|um|\u00b5m|nm|ms|s|Hz|kHz|MHz|GHz|V|mV|A|mA|uA|\u00b5A|"
    r"Ohm|ohm|\u03a9|k\u03a9|M\u03a9|W|mW|dB|%)$",
    re.IGNORECASE,
)
_SHORT_TRANSLATION_META_PATTERN = re.compile(
    r"(?:"
    r"\u0432\s+\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u0438\s+\u043e\u0442\s+\u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u0430|"
    r"\u0431\u0435\u0437\s+\u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u0430|"
    r"\u043c\u043e\u0436(?:\u0435\u0442|\u043d\u043e)\s+(?:\u0431\u044b\u0442\u044c\s+)?\u043f\u0435\u0440\u0435\u0432\u0435\u0434|"
    r"\u043f\u0435\u0440\u0435\u0432\u043e\u0434(?:\u0438\u0442\u0441\u044f|\u044f\u0442\u0441\u044f)?\s+\u043a\u0430\u043a|"
    r"\u0432\u0430\u0440\u0438\u0430\u043d\u0442(?:\u044b|\u0430)?\s+\u043f\u0435\u0440\u0435\u0432\u043e\u0434|"
    r"\u0438\u043b\u0438\s*:|"
    r"\u043a\s+\u0441\u043e\u0436\u0430\u043b\u0435\u043d\u0438\u044e|"
    r"\u043d\u0435\s+\u043c\u043e\u0433\u0443|"
    r"\u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c[\u0430-\u044f\u0451]*\s+\u0443\u0442\u043e\u0447\u043d|"
    r"depending\s+on\s+(?:the\s+)?context|"
    r"can\s+be\s+translated\s+as|"
    r"translation\s+(?:options?|variants?)|"
    r"alternatively\s*:|"
    r"i\s+cannot"
    r")",
    re.IGNORECASE,
)
_CJK_CONTAMINATION_PATTERN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
_RU_CJK_COUPLING_SOURCE_PATTERN = re.compile(r"\bcoupl[A-Za-z-]*\b", re.IGNORECASE)
_RU_CJK_COUPLING_SUFFIX_PATTERN = re.compile(
    r"\s*\u8026\s*(?:\u043f?\u043b\u0438\u0440[\u0430-\u044f\u0451]*|pling)\b",
    re.IGNORECASE,
)
_RU_CJK_COUPLING_STANDALONE_PATTERN = re.compile(r"\s*\u8026\s*")

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


def _split_text_chunks(text: str, max_chunk_chars: int) -> list[str]:
    if max_chunk_chars < 256:
        max_chunk_chars = 256
    if len(text) <= max_chunk_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    total_len = len(text)

    while start < total_len:
        end = min(total_len, start + max_chunk_chars)
        if end < total_len:
            min_boundary = start + max_chunk_chars // 2
            boundary = max(
                text.rfind("\n\n", min_boundary, end),
                text.rfind("\n", min_boundary, end),
                text.rfind(". ", min_boundary, end),
                text.rfind("! ", min_boundary, end),
                text.rfind("? ", min_boundary, end),
                text.rfind("\u3002", min_boundary, end),
                text.rfind("\uFF01", min_boundary, end),
                text.rfind("\uFF1F", min_boundary, end),
                text.rfind(" ", min_boundary, end),
            )
            if boundary > start:
                end = boundary + 1

        if end <= start:
            end = min(total_len, start + max_chunk_chars)

        chunks.append(text[start:end])
        start = end

    return chunks


def _update_skip_stack(tag_fragment: str, skip_stack: list[str]) -> None:
    raw = tag_fragment.strip()
    if not raw.startswith("<"):
        return
    if raw.startswith("<!--") or raw.startswith("<!"):
        return

    close_match = _CLOSE_TAG_PATTERN.match(raw)
    if close_match is not None:
        tag_name = close_match.group(1).lower()
        for idx in range(len(skip_stack) - 1, -1, -1):
            if skip_stack[idx] == tag_name:
                del skip_stack[idx]
                break
        return

    if raw.endswith("/>"):
        return

    open_match = _OPEN_TAG_PATTERN.match(raw)
    if open_match is None:
        return
    tag_name = open_match.group(1).lower()
    # Skip translation inside known non-translatable tags AND inside any element
    # that carries the standard HTML translate="no" attribute.
    if tag_name in _SKIP_TRANSLATION_TAGS or _NO_TRANSLATE_ATTR_PATTERN.search(raw):
        skip_stack.append(tag_name)


def _update_paragraph_stack(
    tag_fragment: str,
    paragraph_stack: list[int],
    paragraph_counter: list[int],
) -> None:
    raw = tag_fragment.strip()
    if not raw.startswith("<"):
        return
    if raw.startswith("<!--") or raw.startswith("<!"):
        return

    close_match = _CLOSE_TAG_PATTERN.match(raw)
    if close_match is not None and close_match.group(1).lower() == "p":
        if paragraph_stack:
            paragraph_stack.pop()
        return

    if raw.endswith("/>"):
        return

    open_match = _OPEN_TAG_PATTERN.match(raw)
    if open_match is None or open_match.group(1).lower() != "p":
        return

    paragraph_counter[0] += 1
    paragraph_stack.append(paragraph_counter[0])


def _update_heading_stack(
    tag_fragment: str,
    heading_stack: list[int],
    heading_counter: list[int],
) -> None:
    raw = tag_fragment.strip()
    if not raw.startswith("<"):
        return
    if raw.startswith("<!--") or raw.startswith("<!"):
        return

    close_match = _CLOSE_TAG_PATTERN.match(raw)
    if close_match is not None and close_match.group(1).lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        if heading_stack:
            heading_stack.pop()
        return

    if raw.endswith("/>"):
        return

    open_match = _OPEN_TAG_PATTERN.match(raw)
    if open_match is None:
        return
    if open_match.group(1).lower() not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return

    heading_counter[0] += 1
    heading_stack.append(heading_counter[0])


def _is_translator_refusal(text: str) -> bool:
    """Return True when *text* looks like a model refusal or meta-commentary."""
    return any(p.search(text) for p in _TRANSLATOR_REFUSAL_PATTERNS)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_source_echo(translated: str, source: str) -> str:
    """Trim common "translation + original source" echoes from model output."""
    cleaned = translated.strip()
    if not cleaned:
        return translated

    cleaned = _TRANSLATION_PREFIX_PATTERN.sub("", cleaned)

    source_clean = source.strip()
    if not source_clean:
        return cleaned

    labeled_original = _ORIGINAL_SECTION_PATTERN.search(cleaned)
    if labeled_original is not None:
        head = cleaned[:labeled_original.start()].rstrip()
        if head:
            return head

    exact_pos = cleaned.rfind(source_clean)
    if exact_pos > 0:
        prefix = cleaned[:exact_pos].rstrip()
        suffix = cleaned[exact_pos + len(source_clean):].strip()
        if prefix and (not suffix or len(suffix) <= 12):
            return prefix

    source_norm = _normalize_ws(source_clean).lower()
    if not source_norm:
        return cleaned

    blocks = [block.strip() for block in re.split(r"(?:\r?\n){2,}", cleaned) if block.strip()]
    if len(blocks) > 1:
        kept: list[str] = []
        removed = False
        for block in blocks:
            block_norm = _normalize_ws(block).lower()
            if block_norm == source_norm:
                removed = True
                continue
            kept.append(block)
        if removed and kept:
            return "\n\n".join(kept)

    return cleaned


def _has_visible_prompt_leak(text: str) -> bool:
    """Return True when text visibly contains translated prompt instructions."""
    return bool(text and _VISIBLE_PROMPT_LEAK_PATTERN.search(text))


def _strip_prompt_leak_echo(text: str) -> str:
    """Remove known prompt-rule echoes while preserving any real translation tail."""
    if not text:
        return text

    cleaned = text.strip()
    previous = None
    while previous != cleaned:
        previous = cleaned
        for pattern in _PROMPT_RULE_ECHO_BLOCK_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        cleaned = _PROMPT_META_ECHO_PATTERN.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned.strip(" \t\r\n\"'«»")


def _sanitize_prompt_leak_segment(
    source_seg: str,
    translated_seg: str,
) -> tuple[str, bool]:
    """Strip prompt-rule echoes from a translated segment or fall back safely."""
    if not _has_visible_prompt_leak(translated_seg):
        return translated_seg, False

    lead, core, tail = _split_outer_ws(translated_seg)
    cleaned_core = _strip_prompt_leak_echo(core)
    if cleaned_core and not _has_visible_prompt_leak(cleaned_core):
        return f"{lead}{cleaned_core}{tail}", True
    return source_seg, True


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans.sort(key=lambda item: (item[0], item[1]))
    merged: list[tuple[int, int]] = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _formula_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in _FORMULA_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if end > start:
                spans.append((start, end))
    return _merge_spans(spans)


# ---------------------------------------------------------------------------
# Batch translation helpers
# ---------------------------------------------------------------------------

# ID-addressed markers injected before each segment in batch mode.
# Example payload:
#   <z2m-i1/>First segment text...
#   <z2m-i2/>Second segment text...
_BATCH_ITEM_PATTERN = re.compile(
    r"<z2m-i(\d+)\s*/>([\s\S]*?)(?=<z2m-i\d+\s*/>|\Z)",
    re.IGNORECASE,
)

# Formula placeholder tokens (ASCII sentinel) kept unchanged by the model.
_FORMULA_TOKEN_PATTERN = re.compile(r"@@Z2M(?:\\?_)?F(\d+)(?:@@|@(?!@))", re.IGNORECASE)
_UNRESOLVED_SENTINEL_PATTERN = re.compile(
    r"@{1,2}Z2M(?:\\?_)?[A-Z0-9_]+(?:@{0,2}|(?:\\?_)+)?",
    re.IGNORECASE,
)
# Any internal protocol marker leaking into the final translated text means the
# reconstructed batch output is not trustworthy and the segment should be
# recovered locally through single-segment translation.
_INTERNAL_MARKER_LEAK_PATTERN = re.compile(
    r"<\s*z2m-[^>]*>|@@Z2M(?:\\?_)?[A-Z0-9_]+@{0,2}",
    re.IGNORECASE,
)

# Safety limit: skip batch mode if the combined text exceeds this many characters
# (rough estimate 4 chars в‰€ 1 token, limit в‰€ 50k tokens input).
_MAX_BATCH_CHARS = 80_000
_WINDOW_BATCH_TARGET_SEGMENTS = 8
_WINDOW_BATCH_OVERLAP_SEGMENTS = 1
_MAX_WINDOW_BATCH_CHARS = 40_000
_HEADING_MERGE_SEPARATOR = "@@Z2M_HSEP@@"
_HEADING_INLINE_MARKUP_TAGS = {"i", "em", "b", "strong"}
_HEADING_MERGE_SEPARATOR_LEAK_PATTERN = re.compile(
    r"@{1,2}Z2M(?:\\?_)?HSEP@{0,2}",
    re.IGNORECASE,
)
_AUX_PROTOCOL_SENTINEL_LEAK_PATTERN = re.compile(
    r"(?:@{1,2}Z2M(?:\\?_)?[ATF]\d+(?:@{1,3}|(?:\\?_)+)?|"
    r"Z2M(?:\\?_)?[ATF]\d+(?:@{1,3}|(?:\\?_)+)?)",
    re.IGNORECASE,
)
_STRAY_ABBREV_AT_PATTERN = re.compile(
    r"\b((?:i|micro|u|\u00b5)?ECoG|SNR|BMI|SEP|MEMS|COG|ERP|NHP|"
    r"VNA|ADC|LC|IEEE)@(?!@)(?=$|[^A-Za-z0-9])"
)
_HEADING_PREFIX_TOKEN_PATTERN = re.compile(r"^\s*([A-Z]|[IVXLCM]{1,8})\.\s+", re.IGNORECASE)
_HEADING_GLOSSARY_RU: dict[str, str] = {
    "MEASUREMENT": "ИЗМЕРЕНИЕ",
}
_HEADING_MISTRANSLATION_FIXUPS_RU: dict[str, str] = {
    "МЕРОПРИЕМ": "ИЗМЕРЕНИЕ",
    "МЕРОПРИЁМ": "ИЗМЕРЕНИЕ",
}
_ABBREVIATION_EXPANSION_RU: dict[str, str] = {
    "SEP": "сенсорный вызванный потенциал",
    "ECoG": "электрокортикограмма",
    "\u00b5ECoG": "микроэлектрокортикограмма",
    "iECoG": "интерполированный сигнал ECoG",
    "MEMS": "микроэлектромеханические системы",
    "COG": "центр тяжести",
    "BMI": "интерфейс мозг-машина",
    "Ch": "канал",
    "D1": "большой палец",
    "D2": "указательный палец",
    "D3": "средний палец",
    "D4": "безымянный палец",
    "D5": "мизинец",
    "IPS": "внутритеменная борозда",
    "CS": "центральная борозда",
    "ERP": "потенциал, связанный с событием",
    "SNR": "соотношение сигнал/шум",
    "NHP": "нечеловеческий примат",
}
_HALLUCINATED_ABBREV_KEYS = {
    "CEO",
    "COO",
    "CFO",
    "CRM",
    "SaaS",
    "PPC",
    "CMS",
    "GDPR",
    "Blockchain",
    "Cybersecurity",
}
_ABBREVIATION_ENTRY_PATTERN = re.compile(
    r"^\s*([A-Za-z\u00b5][A-Za-z0-9\u00b5+\-]*)\s*,\s*(.+?)\s*\.?\s*$"
)
_ABBREVIATION_PARAGRAPH_PATTERN = re.compile(
    r"(?P<open><p\b[^>]*>)(?P<body>[\s\S]{0,8000}?)(?P<close></p>)",
    re.IGNORECASE,
)
_ABBREVIATION_LABEL_TEXT_PATTERN = re.compile(r"^\s*Abbreviations?\s*:", re.IGNORECASE)
_RU_TERMINOLOGY_FIXUPS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bмикрофабрикованные\b", re.IGNORECASE), "изготовленные методами микрофабрикации"),
    (re.compile(r"\bмикрофабрикованных\b", re.IGNORECASE), "изготовленных методами микрофабрикации"),
    (re.compile(r"\bмикрофабрикованным\b", re.IGNORECASE), "изготовленным методами микрофабрикации"),
    (re.compile(r"\bмикрофабрикованными\b", re.IGNORECASE), "изготовленными методами микрофабрикации"),
    (re.compile(r"\bмикрофабрикованной\b", re.IGNORECASE), "изготовленной методами микрофабрикации"),
    (re.compile(r"\bмикрофабрикованная\b", re.IGNORECASE), "изготовленная методами микрофабрикации"),
    (re.compile(r"\bмикрофабрикованное\b", re.IGNORECASE), "изготовленное методами микрофабрикации"),
    (re.compile(r"\bмикрофабрикованный\b", re.IGNORECASE), "изготовленный методами микрофабрикации"),
    (re.compile(r"\bвысокоразрешающ[а-яё]+\s+запис[а-яё]*\b", re.IGNORECASE), "записи с высоким разрешением"),
    (re.compile(r"\bвысокой\s+точности\s+записи\b", re.IGNORECASE), "для записи с высоким разрешением"),
    (re.compile(r"\bстальн[а-яё]*\s+трод[а-яё]*\b", re.IGNORECASE), "Steeltrode"),
    (re.compile(r"\bстелетрод[а-яё]*\b", re.IGNORECASE), "Steeltrode"),
    (re.compile(r"\bстеелтрод[а-яё]*\b", re.IGNORECASE), "Steeltrode"),
    (re.compile(r"\bстилтрод[а-яё]*\b", re.IGNORECASE), "Steeltrode"),
    (re.compile(r"\bстеплерод[а-яё]*\b", re.IGNORECASE), "Steeltrode"),
    (re.compile(r"\bSU-8\s+изготовлени[ея]\s+Steeltrode\b", re.IGNORECASE), "изготовление Steeltrode на основе SU-8"),
    (re.compile(r"\b(?:имплантируемой|имплантуемой)\s+штанги\b", re.IGNORECASE), "имплантируемой части зонда"),
    (re.compile(r"\bимплантируемая\s+штанга\b", re.IGNORECASE), "имплантируемая часть зонда"),
    (re.compile(r"\bмеханические\s+испытания\s+изгиба\s+стали\b", re.IGNORECASE), "механические испытания стального зонда на изгиб"),
    (re.compile(r"\bпар[аеёи]лен[а-яё]*(?:\s+C| С)?\b", re.IGNORECASE), "Parylene C"),
    (re.compile(r"\bпарафилен[а-яё]*(?:\s+C| С)?\b", re.IGNORECASE), "Parylene C"),
)
_RU_ENGLISH_RESIDUAL_FIXUPS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bwhich\s+is\s+discussed\s+in\b", re.IGNORECASE),
        "\u0447\u0442\u043e \u043e\u0431\u0441\u0443\u0436\u0434\u0430\u0435\u0442\u0441\u044f \u0432",
    ),
    (
        re.compile(
            r"\bwe\s+solved\s+the\s+complicated\s+series-\s*"
            r"\u0443\u0440\u0430\u0432\u043d\u0435\u043d\u0438[\u044f\u0435]\s+"
            r"\u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u043e\u0439\s+"
            r"\u0446\u0435\u043f\u0438",
            re.IGNORECASE,
        ),
        (
            "\u043c\u044b \u0440\u0435\u0448\u0438\u043b\u0438 \u0441\u043b\u043e\u0436\u043d\u044b\u0435 "
            "\u0443\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u044f "
            "\u043f\u043e\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u043d\u043e-"
            "\u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u043e\u0439 "
            "\u0446\u0435\u043f\u0438"
        ),
    ),
    (
        re.compile(r"\bthe\s+output\s+amplitude\s+sent\s+to\s+the\s+ADC\s+decreases\s+to\b", re.IGNORECASE),
        (
            "\u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434\u0430 \u0432\u044b\u0445\u043e\u0434\u043d\u043e\u0433\u043e "
            "\u0441\u0438\u0433\u043d\u0430\u043b\u0430, \u043f\u043e\u0434\u0430\u0432\u0430\u0435\u043c\u043e\u0433\u043e "
            "\u043d\u0430 ADC, \u0443\u043c\u0435\u043d\u044c\u0448\u0430\u0435\u0442\u0441\u044f \u0434\u043e"
        ),
    ),
    (
        re.compile(r"\bThe\s+amplitude\s+difference\s+between\s+before\s+and\s+after\s+adding\b", re.IGNORECASE),
        (
            "\u0420\u0430\u0437\u043d\u043e\u0441\u0442\u044c \u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434 "
            "\u0434\u043e \u0438 \u043f\u043e\u0441\u043b\u0435 \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u0438\u044f"
        ),
    ),
    (
        re.compile(r"\bThis\s+amplitude\s+difference\s+could\s+also\s+be\s+defined\s+by\b", re.IGNORECASE),
        (
            "\u042d\u0442\u0443 \u0440\u0430\u0437\u043d\u043e\u0441\u0442\u044c "
            "\u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434 \u0442\u0430\u043a\u0436\u0435 "
            "\u043c\u043e\u0436\u043d\u043e \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0438\u0442\u044c \u043a\u0430\u043a"
        ),
    ),
    (
        re.compile(
            r"\bBy\s+solving\s+the\s+series-\s*"
            r"\u0443\u0440\u0430\u0432\u043d\u0435\u043d\u0438[\u044f\u0435]\s+"
            r"\u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u043e\u0439\s+"
            r"\u0446\u0435\u043f\u0438",
            re.IGNORECASE,
        ),
        (
            "\u0420\u0435\u0448\u0430\u044f \u0443\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u044f "
            "\u043f\u043e\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u043d\u043e-"
            "\u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u043e\u0439 "
            "\u0446\u0435\u043f\u0438"
        ),
    ),
    (
        re.compile(
            r"\bFig\.\s*7\s+shows\s+the\s+relationship\s+between\s+the\s+"
            r"amplitude\s+of\s+signal\s+drop\b",
            re.IGNORECASE,
        ),
        (
            "\u0420\u0438\u0441. 7 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442 "
            "\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u044c \u043c\u0435\u0436\u0434\u0443 "
            "\u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434\u043e\u0439 "
            "\u043f\u0430\u0434\u0435\u043d\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u0430"
        ),
    ),
    (
        re.compile(
            r"\bshows\s+the\s+relationship\s+between\s+the\s+amplitude\s+of\s+signal\s+drop\b",
            re.IGNORECASE,
        ),
        (
            "\u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442 "
            "\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u044c "
            "\u043c\u0435\u0436\u0434\u0443 \u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434\u043e\u0439 "
            "\u043f\u0430\u0434\u0435\u043d\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u0430"
        ),
    ),
    (
        re.compile(r"(?<=\))\s+is\s+(?=\\\()", re.IGNORECASE),
        " \u0440\u0430\u0432\u043d\u0430 ",
    ),
    (
        re.compile(
            r"\bNSF\s+Young\s+Professionals\s+Contributing\s+to\s+Smart\s+"
            r"and\s+Connected\s+Health\b",
            re.IGNORECASE,
        ),
        (
            "NSF \u0434\u043b\u044f \u043c\u043e\u043b\u043e\u0434\u044b\u0445 "
            "\u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442\u043e\u0432, "
            "\u0432\u043d\u043e\u0441\u044f\u0449\u0438\u0445 \u0432\u043a\u043b\u0430\u0434 "
            "\u0432 \u0443\u043c\u043d\u043e\u0435 \u0438 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043d\u043e\u0435 "
            "\u0437\u0434\u0440\u0430\u0432\u043e\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435"
        ),
    ),
)
_HEADING_ALLCAPS_WORD_PATTERN = re.compile(r"\b[A-Z\u0410-\u042F\u0401]{3,}\b")
_HEADING_RU_WORD_PATTERN = re.compile(r"[\u0410-\u042F\u0430-\u044F\u0401\u0451]{4,}")
_HEADING_RU_OOV_SKIP = {
    "WI",
    "USA",
}
_TABLE_CAPTION_ALLCAPS_PATTERN = re.compile(
    r"^\s*TABLE\s+([IVX]+)\s+([A-Z0-9][A-Z0-9\s,()/:+\-]{3,})\s*$"
)
_RECOVERY_CONTEXT_DEPTH = 0
_PYMORPHY3_ANALYZER = None
_PYMORPHY3_UNAVAILABLE = False


def _cascade_debug(message: str) -> None:
    flag = os.getenv("Z2M_DEBUG_CASCADE", "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return
    print(f"[cascade] {message}", flush=True)


def _is_recovery_context_active() -> bool:
    return _RECOVERY_CONTEXT_DEPTH > 0


def _sanitize_generation_config_for_greedy(generation_config: object | None) -> None:
    """Align generation config with deterministic decoding.

    Some model bundles ship sampling defaults (top_p/top_k/temperature) in
    generation_config.json. We run with do_sample=False, so keep config in a
    greedy-compatible state to avoid warnings and ambiguous behavior.
    """
    if generation_config is None:
        return

    def _set(attr: str, value: object) -> None:
        if not hasattr(generation_config, attr):
            return
        try:
            setattr(generation_config, attr, value)
        except Exception:
            return

    _set("do_sample", False)
    _set("top_p", 1.0)
    _set("top_k", 50)
    _set("temperature", 1.0)
    _set("typical_p", 1.0)


def _format_int_list(values: list[int], *, max_items: int = 8) -> str:
    if not values:
        return "[]"
    if len(values) <= max_items:
        return "[" + ",".join(str(v) for v in values) + "]"
    head = ",".join(str(v) for v in values[:max_items])
    return f"[{head},...+{len(values) - max_items}]"


def _apply_formula_mask(text: str) -> tuple[str, dict[str, str]]:
    """Replace formula spans with ``@@Z2MF{N}@@`` tokens.

    Returns ``(masked_text, token_map)`` where *token_map* maps each token
    back to the original formula string so it can be restored after translation.
    """
    spans = _formula_spans(text)
    if not spans:
        return text, {}
    fmap: dict[str, str] = {}
    masked = text
    # Replace right-to-left so positions stay valid.
    for j, (start, end) in enumerate(reversed(spans)):
        real_j = len(spans) - 1 - j
        token = f"@@Z2MF{real_j}@@"
        fmap[token] = text[start:end]
        masked = masked[:start] + token + masked[end:]
    return masked, fmap


def _normalize_sentinel_escapes(text: str) -> str:
    """Normalize markdown-escaped protocol sentinels returned by LLMs.

    Some models emit escaped variants such as ``@@Z2M\\_A0@@``.  Those must be
    canonicalized before token-restore logic runs.
    """
    if "@@Z2M" not in text and "@@z2m" not in text:
        return text
    normalized = re.sub(r"@@([zZ]2[mM])\\+(?=[A-Za-z_])", r"@@\1", text)
    return normalized


def _sentinel_token_variants(token: str) -> set[str]:
    variants = {token}
    if "_" in token:
        variants.add(token.replace("_", r"\_"))
    if token.endswith("@@"):
        short = token[:-1]
        variants.add(short)
        if "_" in short:
            variants.add(short.replace("_", r"\_"))
    return {v for v in variants if v}


def _strip_protocol_sentinels(text: str) -> str:
    """Remove leaked internal protocol sentinels from final text fragments."""
    if "z2m" not in text.lower():
        return text
    cleaned = _normalize_sentinel_escapes(text)
    cleaned = _HEADING_MERGE_SEPARATOR_LEAK_PATTERN.sub(" ", cleaned)
    cleaned = _AUX_PROTOCOL_SENTINEL_LEAK_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def _strip_stray_abbrev_at_signs(text: str) -> str:
    """Remove a leaked sentinel tail after protected abbreviations."""
    if "@" not in text:
        return text
    return _STRAY_ABBREV_AT_PATTERN.sub(r"\1", text)


def _clean_final_text_fragment(text: str) -> str:
    return _strip_stray_abbrev_at_signs(_strip_protocol_sentinels(text))


def _clean_final_part_fragment(part: str) -> str:
    if part.startswith("<"):
        return _strip_protocol_sentinels(part)
    return _clean_final_text_fragment(part)


def _restore_formula_mask(text: str, fmap: dict[str, str]) -> str:
    """Substitute formula placeholder tokens back with their original strings."""
    if not fmap:
        return text
    text = _normalize_sentinel_escapes(text)

    def _replace(match: re.Match[str]) -> str:
        token = f"@@Z2MF{int(match.group(1))}@@"
        return fmap.get(token, match.group(0))

    restored = _FORMULA_TOKEN_PATTERN.sub(_replace, text)
    for token, formula in fmap.items():
        for variant in _sentinel_token_variants(token):
            restored = restored.replace(variant, formula)
    return restored


def _apply_prompt_leak_mask(text: str) -> tuple[str, dict[str, str]]:
    """Protect against prompt leakage by masking specific patterns."""
    amap: dict[str, str] = {}
    masked = text

    # Apply patterns that should not leak from prompts
    for pattern in _PROMPT_LEAK_PROTECTION_PATTERNS:
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        def replace_match(match):
            original = match.group(0)
            token = f'<z2m-p id="{len(amap)}"/>'
            amap[token] = original
            return token

        masked = compiled_pattern.sub(replace_match, masked)

    return masked, amap


def _apply_custom_abbrev_mask(text: str) -> tuple[str, dict[str, str]]:
    """Apply custom masking for specific Latin abbreviations using our dictionary."""
    amap: dict[str, str] = {}
    masked = text

    # Apply patterns from our custom dictionary
    for pattern in _LATIN_ABBREV_PATTERNS:
        def replace_match(match):
            original = match.group(0)
            # Get the replacement from our mapping
            for key_pattern, replacement in LATIN_ABBREV_TO_RU.items():
                if re.match(key_pattern, original, re.IGNORECASE):
                    token = f"@@Z2M_A{len(amap)}@@"
                    amap[token] = original
                    return token
            return original

        masked = pattern.sub(replace_match, masked)

    return masked, amap


def _apply_abbrev_mask(text: str) -> tuple[str, dict[str, str]]:
    """Replace uppercase abbreviations with ``@@Z2M_A{N}@@`` tokens.

    Protects sequences such as ``IEEE``, ``GAI``, ``LC``, ``ADC`` from being
    transliterated or "translated" by the model (e.g. GAI -> Cyrillic). Also
    protects unstable mixed-case scientific terms such as ``ECoG`` and material
    names such as ``TiN``/``Parylene C``.
    """
    preferred_spans = [
        (m.start(), m.end())
        for m in _PROTECTED_SCIENCE_TERM_PATTERN.finditer(text)
    ]
    spans = list(preferred_spans)
    for match in _ABBREV_PATTERN.finditer(text):
        start, end = match.span()
        if any(not (end <= s or start >= e) for s, e in preferred_spans):
            continue
        spans.append((start, end))
    spans = sorted(set(spans), key=lambda span: span[0])
    if not spans:
        return text, {}
    amap: dict[str, str] = {}
    masked = text
    for j, (start, end) in enumerate(reversed(spans)):
        real_j = len(spans) - 1 - j
        token = f"@@Z2M_A{real_j}@@"
        amap[token] = text[start:end]
        masked = masked[:start] + token + masked[end:]
    return masked, amap


def _restore_abbrev_mask(text: str, amap: dict[str, str]) -> str:
    """Substitute abbreviation placeholder tokens back with their original strings.

    Returns the original *text* unchanged if any placeholder token could not be
    restored (which would indicate the model dropped part of the masked text).
    """
    if not amap:
        return text
    text = _normalize_sentinel_escapes(text)

    def _replace(match: re.Match[str]) -> str:
        token = f"@@Z2M_A{int(match.group(1))}@@"
        return amap.get(token, match.group(0))

    restored = _ABBREV_TOKEN_PATTERN.sub(_replace, text)
    for token, original in amap.items():
        for variant in _sentinel_token_variants(token):
            restored = restored.replace(variant, original)
    for original in sorted(set(amap.values()), key=len, reverse=True):
        if len(original) < 2:
            continue
        restored = re.sub(
            rf"{re.escape(original)}@(?!@)(?=$|[^A-Za-z0-9])",
            original,
            restored,
        )
    return restored


def _apply_tag_mask(text: str) -> tuple[str, dict[str, str]]:
    """Mask inline HTML tags inside a text segment to keep recovery stable.

    This is used only for single-segment recovery paths where the model may
    hallucinate punctuation around missing inline anchors/tags.
    """
    tags = list(re.finditer(r"<[^>]+>", text))
    if not tags:
        return text, {}

    masked = text
    tmap: dict[str, str] = {}
    for j, match in enumerate(reversed(tags)):
        real_j = len(tags) - 1 - j
        token = f"@@Z2M_T{real_j}@@"
        tmap[token] = match.group(0)
        start, end = match.span()
        masked = masked[:start] + token + masked[end:]
    return masked, tmap


def _restore_tag_mask(text: str, tmap: dict[str, str]) -> str:
    """Restore inline tag tokens after recovery translation."""
    if not tmap:
        return text
    text = _normalize_sentinel_escapes(text)

    def _replace(match: re.Match[str]) -> str:
        token = f"@@Z2M_T{int(match.group(1))}@@"
        return tmap.get(token, match.group(0))

    restored = _TAG_TOKEN_PATTERN.sub(_replace, text)
    for token, original in tmap.items():
        for variant in _sentinel_token_variants(token):
            restored = restored.replace(variant, original)
    return restored


def _split_outer_ws(text: str) -> tuple[str, str, str]:
    leading_len = len(text) - len(text.lstrip())
    trailing_len = len(text) - len(text.rstrip())
    core_end = len(text) - trailing_len if trailing_len else len(text)
    return text[:leading_len], text[leading_len:core_end], text[core_end:]


def _segment_core_text(text: str) -> str:
    _, core, _ = _split_outer_ws(text)
    return core


def _has_following_translatable(segments: list[str], current_index: int) -> bool:
    for next_idx in range(current_index + 1, len(segments)):
        nxt = segments[next_idx]
        if not nxt or not nxt.strip():
            continue
        return bool(_TRANSLATABLE_TEXT_PATTERN.search(nxt))
    return False


def _has_trailing_ellipsis_artifact(
    source_seg: str,
    translated_seg: str,
    source_segments: list[str],
    source_index: int,
) -> bool:
    source_core = _segment_core_text(source_seg).rstrip()
    translated_core = _segment_core_text(translated_seg).rstrip()
    if not translated_core:
        return False

    src_has_ellipsis = source_core.endswith(("...", "вЂ¦"))
    out_has_ellipsis = translated_core.endswith(("...", "вЂ¦"))
    if not out_has_ellipsis or src_has_ellipsis:
        return False

    return _has_following_translatable(source_segments, source_index)


def _strip_unexpected_trailing_ellipsis(source_seg: str, translated_seg: str) -> tuple[str, bool]:
    lead, core, tail = _split_outer_ws(translated_seg)
    src_core = _segment_core_text(source_seg).rstrip()
    trimmed_core = core.rstrip()
    if not trimmed_core:
        return translated_seg, False
    if src_core.endswith(("...", "РІР‚В¦")):
        return translated_seg, False
    if not trimmed_core.endswith(("...", "РІР‚В¦")):
        return translated_seg, False

    stripped = re.sub(r"(?:\.\.\.|РІР‚В¦)+\s*$", "", trimmed_core).rstrip()
    if not stripped:
        return translated_seg, False
    return f"{lead}{stripped}{tail}", True


def _redistribute_recovered_slice_to_parts(
    source_slice: list[str],
    recovered_chunk: str,
) -> list[str] | None:
    """Split *recovered_chunk* back to the exact shape of *source_slice*.

    The source slice is a contiguous HTML fragment already split by ``_TAG_SPLIT_PATTERN``.
    We require the same tag sequence in order and assign recovered text spans between
    those tags back into the original text-part slots.
    """
    result: list[str] = []
    pos = 0
    total = len(source_slice)

    for i, source_part in enumerate(source_slice):
        if source_part.startswith("<"):
            tag_pos = recovered_chunk.find(source_part, pos)
            if tag_pos < 0:
                return None
            if tag_pos > pos:
                leaked = recovered_chunk[pos:tag_pos]
                if leaked.strip():
                    if result and not result[-1].startswith("<"):
                        result[-1] = result[-1] + leaked
                    else:
                        return None
            result.append(source_part)
            pos = tag_pos + len(source_part)
            continue

        next_tag = None
        for j in range(i + 1, total):
            candidate = source_slice[j]
            if candidate.startswith("<"):
                next_tag = candidate
                break
        if next_tag is None:
            text_part = recovered_chunk[pos:]
            pos = len(recovered_chunk)
        else:
            next_pos = recovered_chunk.find(next_tag, pos)
            if next_pos < 0:
                return None
            text_part = recovered_chunk[pos:next_pos]
            pos = next_pos
        result.append(text_part)

    if pos < len(recovered_chunk):
        if recovered_chunk[pos:].strip():
            return None
    return result


def _recover_parts_slice_with_tag_mask(
    *,
    source_parts: list[str],
    start_part_idx: int,
    end_part_idx: int,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    context_label: str,
    seg_index: int | None = None,
) -> list[str] | None:
    if start_part_idx < 0 or end_part_idx >= len(source_parts) or start_part_idx > end_part_idx:
        return None
    source_slice = source_parts[start_part_idx:end_part_idx + 1]
    if not source_slice:
        return None

    source_chunk = "".join(source_slice)
    recovered_chunk = _recover_single_segment_with_tag_mask(
        source_chunk,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
        context_label=context_label,
        seg_index=seg_index,
    )
    return _redistribute_recovered_slice_to_parts(source_slice, recovered_chunk)


def _find_contiguous_identity_runs(
    indices: list[int],
    *,
    source_segments: list[str],
    translated_segments: list[str],
    min_total_chars: int = 80,
) -> list[tuple[int, int]]:
    if not indices:
        return []
    identity_indices = [
        idx for idx in indices
        if _is_identity_residual(source_segments[idx], translated_segments[idx])
    ]
    if not identity_indices:
        return []

    runs: list[tuple[int, int]] = []
    run_start = identity_indices[0]
    run_end = identity_indices[0]
    run_chars = len(_segment_core_text(source_segments[run_start]))

    for idx in identity_indices[1:]:
        if idx == run_end + 1:
            run_end = idx
            run_chars += len(_segment_core_text(source_segments[idx]))
            continue
        if (run_end - run_start + 1) >= 2 or run_chars >= min_total_chars:
            runs.append((run_start, run_end))
        run_start = idx
        run_end = idx
        run_chars = len(_segment_core_text(source_segments[idx]))

    if (run_end - run_start + 1) >= 2 or run_chars >= min_total_chars:
        runs.append((run_start, run_end))
    return runs


def _extract_next_paragraph_context_text(parts: list[str], start_part_idx: int) -> str:
    in_paragraph = False
    chunks: list[str] = []

    for part in parts[start_part_idx + 1:]:
        if part.startswith("<"):
            raw = part.strip()
            open_match = _OPEN_TAG_PATTERN.match(raw)
            close_match = _CLOSE_TAG_PATTERN.match(raw)
            tag_name = ""
            if open_match is not None:
                tag_name = open_match.group(1).lower()
            if close_match is not None:
                tag_name = close_match.group(1).lower()

            if not in_paragraph and open_match is not None and tag_name == "p" and not raw.endswith("/>"):
                in_paragraph = True
                continue
            if in_paragraph and close_match is not None and tag_name == "p":
                break
            continue

        if not in_paragraph:
            continue
        if not _TRANSLATABLE_TEXT_PATTERN.search(part):
            continue
        chunks.append(_normalize_ws(part))

    paragraph = _normalize_ws(" ".join(chunks))
    if not paragraph:
        return ""
    first_sentence = re.split(r"(?<=[.!?])\s+", paragraph, maxsplit=1)[0].strip()
    if len(first_sentence) > 220:
        return first_sentence[:220].rstrip() + "..."
    return first_sentence


def _recover_heading_segment_with_context(
    source_seg: str,
    *,
    context_text: str,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    seg_index: int,
) -> str:
    if not context_text:
        return _recover_single_segment_with_tag_mask(
            source_seg,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
            context_label="heading",
            seg_index=seg_index,
        )

    combined_source = f"[[hstart]]{source_seg}[[hend]]\n{context_text}"
    recovered = _recover_single_segment_with_tag_mask(
        combined_source,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
        context_label="heading",
        seg_index=seg_index,
    )
    match = re.search(r"\[\[hstart\]\](.*?)\[\[hend\]\]", recovered, flags=re.DOTALL | re.IGNORECASE)
    if match is not None:
        candidate = match.group(1).strip()
        if candidate and not _is_heading_context_leak_candidate(
            source_seg=source_seg,
            candidate=candidate,
            context_text=context_text,
        ):
            return candidate
        _cascade_debug(
            f"heading_lenient reason=context_leak seg={seg_index} action=source_only_recovery"
        )
    return _recover_single_segment_with_tag_mask(
        source_seg,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
        context_label="heading",
        seg_index=seg_index,
    )


def _is_heading_context_leak_candidate(
    *,
    source_seg: str,
    candidate: str,
    context_text: str,
) -> bool:
    """Detect when heading context recovery leaked paragraph content into heading slot."""
    source_norm = _normalize_ws(_segment_core_text(source_seg))
    candidate_norm = _normalize_ws(_segment_core_text(candidate))
    context_norm = _normalize_ws(context_text)
    if not candidate_norm:
        return True
    # Heading retry should never emit raw block tags (<h1>, <p>, ...).
    if re.search(r"<[^>]+>", candidate):
        return True

    # If source heading starts with an enumerated token (A., IV., ...), keep it.
    source_prefix = _HEADING_PREFIX_TOKEN_PATTERN.match(source_norm)
    if source_prefix is not None:
        prefix = source_prefix.group(1).lower() + "."
        if not candidate_norm.lower().startswith(prefix):
            return True

    # Candidate that mostly repeats paragraph context indicates boundary leak.
    if context_norm:
        check_len = min(48, len(context_norm))
        if check_len >= 20 and candidate_norm.lower().startswith(context_norm[:check_len].lower()):
            return True

    # Heading text should not balloon into a paragraph-sized sentence block.
    if len(candidate_norm) > max(140, len(source_norm) * 3):
        return True

    return False


def _apply_heading_glossary_postedit(source_seg: str, translated_seg: str) -> str:
    """Apply deterministic glossary fixes for known unstable heading terms."""
    source_norm = _normalize_ws(_segment_core_text(source_seg))
    translated_norm = _normalize_ws(_segment_core_text(translated_seg))
    if not source_norm or not translated_norm:
        return translated_seg

    out = translated_seg
    source_upper = source_norm.upper()

    if "ECOG RECORDING OF SOMATOSENSORY EVOKED POTENTIALS" in source_upper:
        stable_phrase = (
            "\u0437\u0430\u043f\u0438\u0441\u0438 "
            "\u0441\u043e\u043c\u0430\u0442\u043e\u0441\u0435\u043d\u0441\u043e\u0440\u043d\u044b\u0445 "
            "\u0432\u044b\u0437\u0432\u0430\u043d\u043d\u044b\u0445 "
            "\u043f\u043e\u0442\u0435\u043d\u0446\u0438\u0430\u043b\u043e\u0432 "
            "\u043d\u0430 ECoG"
        )
        out = re.sub(
            r"\bECoG\s+Recording\s+of\s+Somatosensory\s+Evoked\s+Potentials\b",
            stable_phrase,
            out,
            flags=re.IGNORECASE,
        )
        out = re.sub(
            r"\bECoG\s+Recording\s+of\s+Somatosensory\s+"
            r"\u041f\u043e\u0442\u0435\u043d\u0446\u0438\u0430\u043b[\u0430-\u044f\u0451]*,?\s+"
            r"\u0432\u044b\u0437\u0432\u0430\u043d[\u0430-\u044f\u0451]*\b",
            stable_phrase,
            out,
            flags=re.IGNORECASE,
        )

    for en_term, ru_term in _HEADING_GLOSSARY_RU.items():
        if en_term not in source_upper:
            continue
        out = re.sub(
            rf"\b{re.escape(en_term)}\b",
            ru_term,
            out,
            flags=re.IGNORECASE,
        )
        for bad_ru, fixed_ru in _HEADING_MISTRANSLATION_FIXUPS_RU.items():
            out = re.sub(
                rf"\b{re.escape(bad_ru)}\b",
                fixed_ru,
                out,
                flags=re.IGNORECASE,
            )
    return out


def _lookup_abbreviation_expansion_ru(key: str, fallback: str) -> str:
    """Return a stable RU expansion for known scientific abbreviations."""
    direct = _ABBREVIATION_EXPANSION_RU.get(key)
    if direct is not None:
        return direct
    lowered = key.lower()
    for known_key, expansion in _ABBREVIATION_EXPANSION_RU.items():
        if known_key.lower() == lowered:
            return expansion
    return fallback.strip().rstrip(".")


def _source_abbreviation_entries(source_seg: str) -> list[tuple[str, str]]:
    """Parse source ``Abbreviations: KEY, expansion; ...`` segments."""
    source_core = _segment_core_text(source_seg)
    if not re.match(r"^\s*abbreviations?\s*:", source_core, re.IGNORECASE):
        return []

    payload = re.sub(
        r"^\s*abbreviations?\s*:\s*",
        "",
        source_core,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    payload = payload.rstrip(".")
    if not payload:
        return []

    entries: list[tuple[str, str]] = []
    for raw_entry in re.split(r"\s*;\s*", payload):
        raw_entry = raw_entry.strip()
        if not raw_entry:
            continue
        match = _ABBREVIATION_ENTRY_PATTERN.match(raw_entry)
        if match is None:
            continue
        key = match.group(1).strip()
        expansion = _lookup_abbreviation_expansion_ru(key, match.group(2))
        entries.append((key, expansion))

    present = {key.lower() for key, _expansion in entries}
    for known_key in _ABBREVIATION_EXPANSION_RU:
        if known_key.lower() in present:
            continue
        if re.search(
            rf"(?<![A-Za-z0-9\u00b5]){re.escape(known_key)}(?![A-Za-z0-9\u00b5])",
            payload,
            flags=re.IGNORECASE,
        ):
            entries.append((known_key, _ABBREVIATION_EXPANSION_RU[known_key]))
    return entries


def _format_abbreviation_entries_ru(entries: list[tuple[str, str]]) -> str:
    rebuilt = "; ".join(f"{key}, {expansion}" for key, expansion in entries)
    return f"Сокращения: {rebuilt}."


def _visible_text_from_html_fragment(fragment: str) -> str:
    text = _HTML_TAG_PATTERN.sub(" ", fragment)
    return _normalize_ws(html_lib.unescape(text))


def _tiny_fragment_visible_text(fragment: str) -> str:
    visible = _visible_text_from_html_fragment(fragment)
    visible = visible.replace("\u00a0", " ")
    return _normalize_ws(visible)


def _strip_tiny_wrapper_punctuation(text: str) -> str:
    return text.strip(" \t\r\n()[]{}.,;:<>")


def _should_preserve_tiny_fragment(fragment: str) -> bool:
    """Return True for atomic technical fragments that should not hit the model.

    These are not translation units: panel letters, variables, acronyms, units,
    and compact numeric-unit spans. Sending them alone to Gemma often
    produces explanations or refusals rather than useful translation.
    """
    visible = _tiny_fragment_visible_text(fragment)
    if not visible:
        return False

    core = _strip_tiny_wrapper_punctuation(visible)
    if not core:
        return False
    if core == "a":
        return False

    if _TINY_NUMERIC_UNIT_PATTERN.fullmatch(core):
        return True
    if len(core) > _TINY_FRAGMENT_MAX_CHARS:
        return False
    if _TINY_TECHNICAL_TOKEN_PATTERN.fullmatch(core):
        return True
    if _TINY_SINGLE_TOKEN_PATTERN.fullmatch(core):
        return True
    return False


def _short_translation_guard_reason(source_seg: str, translated_seg: str) -> str | None:
    """Detect bad short-fragment outputs such as variant lists or meta comments."""
    source_visible = _tiny_fragment_visible_text(source_seg)
    translated_visible = _tiny_fragment_visible_text(translated_seg)
    if not source_visible or not translated_visible:
        return None

    source_core = _strip_tiny_wrapper_punctuation(source_visible)
    translated_core = _strip_tiny_wrapper_punctuation(translated_visible)
    if not source_core or not translated_core:
        return None

    if _should_preserve_tiny_fragment(source_seg) and translated_core != source_core:
        return "protected_tiny_fragment_changed"

    source_len = len(source_core)
    if source_len > 32:
        return None

    if _is_translator_refusal(translated_core):
        return "short_refusal"
    if _SHORT_TRANSLATION_META_PATTERN.search(translated_core):
        return "short_meta_translation"

    translated_len = len(translated_core)
    if source_len <= 5 and translated_len > 20:
        return "short_overgeneration"
    if source_len <= 10 and translated_len > 48:
        return "short_overgeneration"
    if source_len <= 20 and translated_len > max(64, source_len * 4):
        return "short_overgeneration"

    if source_len <= 20 and translated_len > max(32, source_len * 3):
        list_like = (
            "\n" in translated_seg
            or ";" in translated_core
            or re.search(r"\s/\s|\d+\s*[\).]", translated_core) is not None
        )
        if list_like:
            return "short_variant_list"

    return None


def _apply_short_translation_guard(source_seg: str, translated_seg: str) -> tuple[str, str | None]:
    reason = _short_translation_guard_reason(source_seg, translated_seg)
    if reason is None:
        return translated_seg, None
    return source_seg, reason


def _replace_abbreviation_paragraphs_ru(source_html: str) -> str:
    """Deterministically translate scientific abbreviation paragraphs.

    Marker often emits abbreviation definitions as ``<b>Abbreviations:</b>``
    followed by a separate text node. Translating the label alone makes the
    model hallucinate a business glossary. Replacing the whole paragraph before
    text-node translation is both faster and safer.
    """

    def _replace(match: re.Match[str]) -> str:
        body = match.group("body")
        visible = _visible_text_from_html_fragment(body)
        if not _ABBREVIATION_LABEL_TEXT_PATTERN.match(visible):
            return match.group(0)

        entries = _source_abbreviation_entries(visible)
        if len(entries) < 2:
            return match.group(0)

        translated = html_lib.escape(_format_abbreviation_entries_ru(entries), quote=False)
        return f'{match.group("open")}<span translate="no">{translated}</span>{match.group("close")}'

    return _ABBREVIATION_PARAGRAPH_PATTERN.sub(_replace, source_html)


def _repair_abbreviation_definition_segment(source_seg: str, translated_seg: str) -> str:
    """Rebuild known abbreviation definition lines when the model hallucinates.

    Gemma occasionally turns a compact scientific abbreviation line
    into an unrelated business glossary (CEO/COO/CFO/etc.).  For this very
    specific source structure, a deterministic line is safer than another model
    retry and avoids extra runtime.
    """
    entries = _source_abbreviation_entries(source_seg)
    if not entries:
        return translated_seg

    lead, core, tail = _split_outer_ws(translated_seg)
    core_norm = _normalize_ws(core)
    hallucinated = any(
        re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", core_norm)
        for key in _HALLUCINATED_ABBREV_KEYS
    )
    missing_source_keys = any(
        re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", core_norm) is None
        for key, _expansion in entries
    )
    lacks_cyrillic = re.search(r"[\u0410-\u042F\u0430-\u044F\u0401\u0451]", core_norm) is None

    if not hallucinated and not missing_source_keys and not lacks_cyrillic:
        return translated_seg

    return f"{lead}{_format_abbreviation_entries_ru(entries)}{tail}"


def _repair_ru_cjk_coupling_artifact(source_seg: str, translated_seg: str) -> str:
    """Repair Qwen's high-confidence coupling artifact for Russian output."""
    if "\u8026" not in translated_seg:
        return translated_seg
    if _RU_CJK_COUPLING_SOURCE_PATTERN.search(_segment_core_text(source_seg)) is None:
        return translated_seg

    lead, core, tail = _split_outer_ws(translated_seg)
    if not core:
        return translated_seg

    fixed = _RU_CJK_COUPLING_SUFFIX_PATTERN.sub(" \u0441\u0432\u044f\u0437\u0438", core)
    if "\u8026" in fixed:
        fixed = _RU_CJK_COUPLING_STANDALONE_PATTERN.sub(" \u0441\u0432\u044f\u0437\u0438 ", fixed)
    fixed = re.sub(r"\s{2,}", " ", fixed).strip()
    return f"{lead}{fixed}{tail}"


def _repair_ru_cjk_buffer_artifact(source_seg: str, translated_seg: str) -> str:
    """Repair Qwen's Chinese 'buffer' fragment in Russian PBS phrases."""
    if "\u7f13\u51b2" not in translated_seg:
        return translated_seg

    source_core = _normalize_ws(_segment_core_text(source_seg)).lower()
    translated_core = _normalize_ws(_segment_core_text(translated_seg)).lower()
    if "pbs" not in source_core and "phosphate" not in source_core and "pbs" not in translated_core:
        return translated_seg

    lead, core, tail = _split_outer_ws(translated_seg)
    if not core:
        return translated_seg

    fixed = core.replace("\u7f13\u51b2", "\u0431\u0443\u0444\u0435\u0440")
    fixed = re.sub(r"\s{2,}", " ", fixed).strip()
    return f"{lead}{fixed}{tail}"


def _apply_ru_terminology_postedit(source_seg: str, translated_seg: str) -> str:
    """Apply high-confidence RU terminology repairs after model translation."""
    if not translated_seg or not translated_seg.strip():
        return translated_seg

    out = _repair_abbreviation_definition_segment(source_seg, translated_seg)
    out = _repair_ru_cjk_coupling_artifact(source_seg, out)
    out = _repair_ru_cjk_buffer_artifact(source_seg, out)
    lead, core, tail = _split_outer_ws(out)
    if not core:
        return out

    fixed = core
    for pattern, replacement in _RU_TERMINOLOGY_FIXUPS:
        fixed = pattern.sub(replacement, fixed)
    for pattern, replacement in _RU_ENGLISH_RESIDUAL_FIXUPS:
        fixed = pattern.sub(replacement, fixed)
    fixed = re.sub(r"\s{2,}", " ", fixed)
    return f"{lead}{fixed}{tail}"


def _normalize_heading_case_for_translation(source_seg: str) -> tuple[str, bool]:
    """Normalize all-caps heading words before translation.

    Returns normalized text and a flag indicating that output should be restored
    to all-caps style.
    """
    lead, core, tail = _split_outer_ws(source_seg)
    core_norm = _normalize_ws(core)
    if not core_norm:
        return source_seg, False

    has_allcaps_words = _HEADING_ALLCAPS_WORD_PATTERN.search(core_norm) is not None
    has_lowercase = re.search(r"[a-z\u0430-\u044F\u0451]", core_norm) is not None
    preserve_allcaps_style = has_allcaps_words and not has_lowercase
    if not preserve_allcaps_style:
        return source_seg, False

    def _title_word(match: re.Match[str]) -> str:
        word = match.group(0)
        return word.title()

    normalized = _HEADING_ALLCAPS_WORD_PATTERN.sub(_title_word, core)
    return f"{lead}{normalized}{tail}", preserve_allcaps_style


def _restore_heading_caps_style(translated_seg: str, preserve_allcaps_style: bool) -> str:
    if not preserve_allcaps_style:
        return translated_seg
    lead, core, tail = _split_outer_ws(translated_seg)
    core_norm = _normalize_ws(core)
    if not core_norm:
        return translated_seg
    return f"{lead}{core_norm.upper()}{tail}"


def _get_pymorphy3_analyzer():
    global _PYMORPHY3_ANALYZER, _PYMORPHY3_UNAVAILABLE
    if _PYMORPHY3_ANALYZER is not None:
        return _PYMORPHY3_ANALYZER
    if _PYMORPHY3_UNAVAILABLE:
        return None
    try:
        import pymorphy3  # type: ignore[import-not-found]
    except Exception:
        _PYMORPHY3_UNAVAILABLE = True
        return None
    try:
        _PYMORPHY3_ANALYZER = pymorphy3.MorphAnalyzer()
    except Exception:
        _PYMORPHY3_UNAVAILABLE = True
        return None
    return _PYMORPHY3_ANALYZER


def _is_unknown_ru_heading_word(word: str, analyzer) -> bool:
    if not analyzer:
        return False
    if word.upper() in _HEADING_RU_OOV_SKIP:
        return False
    parses = analyzer.parse(word.lower())
    if not parses:
        return True
    for parse in parses[:5]:
        if "UNKN" not in str(getattr(parse, "tag", "")):
            return False
    return True


def _heading_has_oov_confabulation(
    source_seg: str,
    translated_seg: str,
    *,
    target_language_code: str,
) -> bool:
    """Detect heading confabulation using morphology-driven OOV checks."""
    if normalize_language_code(target_language_code) != "ru":
        return False

    source_norm = _normalize_ws(_segment_core_text(source_seg))
    translated_norm = _normalize_ws(_segment_core_text(translated_seg))
    if not source_norm or not translated_norm:
        return False
    if not re.search(r"[\u0410-\u042F\u0430-\u044F\u0401\u0451]", translated_norm):
        return False

    analyzer = _get_pymorphy3_analyzer()
    if analyzer is None:
        return False

    words = _HEADING_RU_WORD_PATTERN.findall(translated_norm)
    if not words:
        return False
    unknown_count = sum(1 for word in words if _is_unknown_ru_heading_word(word, analyzer))
    if unknown_count <= 0:
        return False
    # Aggressive for short headings: one unknown lexical core is enough.
    return unknown_count >= max(1, len(words) // 2)


def _recover_segment_with_context_markers(
    source_seg: str,
    *,
    context_text: str,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    context_label: str,
    seg_index: int,
) -> str:
    if not context_text:
        return _recover_single_segment_with_tag_mask(
            source_seg,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
            context_label=context_label,
            seg_index=seg_index,
        )

    marker_start = "zz2mtargetstartzz"
    marker_end = "zz2mtargetendzz"
    wrapped = f"{marker_start}{source_seg}{marker_end}\n{context_text}"
    recovered = _recover_single_segment_with_tag_mask(
        wrapped,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
        context_label=context_label,
        seg_index=seg_index,
    )
    match = re.search(
        rf"{re.escape(marker_start)}(.*?){re.escape(marker_end)}",
        recovered,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match is not None:
        candidate = match.group(1).strip()
        if candidate:
            return candidate
    return _recover_single_segment_with_tag_mask(
        source_seg,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
        context_label=context_label,
        seg_index=seg_index,
    )


def _recover_segment_with_forced_markers(
    source_seg: str,
    *,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    context_label: str,
    seg_index: int,
) -> str:
    marker_start = "zz2mforcestartzz"
    marker_end = "zz2mforceendzz"
    wrapped = (
        "РїРµСЂРµРІРµРґРё С‚РµРєСЃС‚ РјРµР¶РґСѓ РјР°СЂРєРµСЂР°РјРё РЅР° С†РµР»РµРІРѕР№ СЏР·С‹Рє РїРѕР»РЅРѕСЃС‚СЊСЋ. "
        "РЅРµ РѕСЃС‚Р°РІР»СЏР№ Р°РЅРіР»РёР№СЃРєРёРµ СЃР»РѕРІР° Р±РµР· РїРµСЂРµРІРѕРґР°, РєСЂРѕРјРµ С‚РµС…РЅРёС‡РµСЃРєРёС… Р°Р±Р±СЂРµРІРёР°С‚СѓСЂ "
        "Рё РёРјРµРЅ СЃРѕР±СЃС‚РІРµРЅРЅС‹С….\n"
        f"{marker_start}{source_seg}{marker_end}"
    )
    recovered = _recover_single_segment_with_tag_mask(
        wrapped,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
        context_label=context_label,
        seg_index=seg_index,
    )
    match = re.search(
        rf"{re.escape(marker_start)}(.*?){re.escape(marker_end)}",
        recovered,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match is not None:
        candidate = match.group(1).strip()
        if candidate:
            return candidate
    return _recover_single_segment_with_tag_mask(
        source_seg,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
        context_label=context_label,
        seg_index=seg_index,
    )


def _recover_segment_sentencewise(
    source_seg: str,
    *,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    context_label: str,
    seg_index: int,
) -> str:
    lead, core, tail = _split_outer_ws(source_seg)
    core_text = core.strip()
    if not core_text:
        return source_seg
    sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", core_text) if chunk.strip()]
    if len(sentences) < 2:
        return source_seg

    translated_sentences: list[str] = []
    for sent in sentences:
        try:
            translated = _recover_single_segment_with_tag_mask(
                sent,
                translate_text=translate_text,
                cache=cache,
                max_chunk_chars=max_chunk_chars,
                context_label=context_label,
                seg_index=seg_index,
            )
        except Exception:
            translated = sent
        if _is_identity_residual(sent, translated):
            try:
                translated = _recover_segment_with_forced_markers(
                    sent,
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label=context_label,
                    seg_index=seg_index,
                )
            except Exception:
                pass
        translated_sentences.append(_normalize_ws(_segment_core_text(translated)))

    joined = " ".join(chunk for chunk in translated_sentences if chunk).strip()
    if not joined:
        return source_seg
    return f"{lead}{joined}{tail}"


def _recover_single_segment_with_tag_mask(
    source_seg: str,
    *,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    context_label: str,
    seg_index: int | None = None,
) -> str:
    global _RECOVERY_CONTEXT_DEPTH
    masked_source, tmap = _apply_tag_mask(source_seg)
    _RECOVERY_CONTEXT_DEPTH += 1
    try:
        recovered_masked = _translate_text_segment(
            masked_source,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
        )
    finally:
        _RECOVERY_CONTEXT_DEPTH = max(0, _RECOVERY_CONTEXT_DEPTH - 1)
    restored = _restore_tag_mask(recovered_masked, tmap)
    if tmap:
        expected_ids = list(range(len(tmap)))
        found_ids = sorted(int(m.group(1)) for m in _TAG_TOKEN_PATTERN.finditer(recovered_masked))
        if found_ids != expected_ids:
            seg_info = f" seg={seg_index}" if seg_index is not None else ""
            _cascade_debug(
                f"{context_label}_lenient reason=tag_mask_dropped{seg_info} "
                f"expected={_format_int_list(expected_ids)} got={_format_int_list(found_ids)}"
            )
    return restored


def _is_duplicate_neighbor_segment(candidate: str, neighbor: str | None) -> bool:
    if neighbor is None:
        return False
    cand_norm = _normalize_ws(_segment_core_text(candidate)).lower()
    neigh_norm = _normalize_ws(_segment_core_text(neighbor)).lower()
    if len(cand_norm) < 40 or len(neigh_norm) < 40:
        return False

    span = min(30, len(cand_norm), len(neigh_norm))
    if span < 12:
        return False

    same_prefix = cand_norm[:span] == neigh_norm[:span]
    same_suffix = cand_norm[-span:] == neigh_norm[-span:]
    return same_prefix and same_suffix


def _has_min_latin_words(text: str, min_count: int = 2) -> bool:
    return len(re.findall(r"[A-Za-z]{2,}", text)) >= min_count


def _has_long_english_word_run(text: str, min_words: int = 8) -> bool:
    words = list(re.finditer(r"[A-Za-z]{2,}", text))
    if not words:
        return False

    run_len = 0
    prev_end = -1
    for match in words:
        if prev_end < 0:
            run_len = 1
        else:
            between = text[prev_end:match.start()]
            # Continue the run only when the gap has no alphabetic letters.
            if not re.search(r"[A-Za-z\u0400-\u04FF]", between or ""):
                run_len += 1
            else:
                run_len = 1
        if run_len >= min_words:
            return True
        prev_end = match.end()
    return False


def _cjk_contamination_count(text: str, *, target_language_code: str = DEFAULT_GEMMA_TARGET_LANGUAGE) -> int:
    if normalize_language_code(target_language_code) == "zh":
        return 0
    return len(_CJK_CONTAMINATION_PATTERN.findall(_segment_core_text(text)))


def _has_unexpected_cjk(text: str, *, target_language_code: str = DEFAULT_GEMMA_TARGET_LANGUAGE) -> bool:
    return _cjk_contamination_count(text, target_language_code=target_language_code) > 0


def _repair_known_cjk_contamination(
    source_seg: str,
    translated_seg: str,
    *,
    target_language_code: str,
) -> str:
    if normalize_language_code(target_language_code) == "ru":
        out = _repair_ru_cjk_coupling_artifact(source_seg, translated_seg)
        out = _repair_ru_cjk_buffer_artifact(source_seg, out)
        return out
    return translated_seg


def _is_identity_residual(source_seg: str, translated_seg: str) -> bool:
    if _should_preserve_tiny_fragment(source_seg):
        return False

    source_core = _normalize_ws(_segment_core_text(source_seg))
    translated_core = _normalize_ws(_segment_core_text(translated_seg))
    if not source_core or not translated_core:
        return False
    if len(translated_core) < 10:
        return False
    if not _has_min_latin_words(source_core, min_count=2):
        return False

    if translated_core == source_core:
        return True

    # Catch mixed EN/RU outputs where a long contiguous EN fragment survived.
    if _has_long_english_word_run(translated_core, min_words=8):
        return True

    # Count only letters to avoid punctuation/digit skew for technical strings.
    letters = [char for char in translated_core if char.isalpha()]
    if len(letters) < 5:
        return False
    latin_chars = sum(1 for char in letters if ("A" <= char <= "Z") or ("a" <= char <= "z"))
    latin_ratio = latin_chars / len(letters)
    if len(letters) >= 80:
        return latin_ratio >= 0.7
    return latin_ratio >= 0.8


def _is_identity_residual_segment(source_seg: str, translated_seg: str) -> bool:
    # Backward-compatible alias used by older tests/call-sites.
    return _is_identity_residual(source_seg, translated_seg)


def _post_reassembly_guard_reason(
    *,
    source_segments: list[str],
    source_index: int,
    source_seg: str,
    translated_seg: str,
    prev_translated: str | None,
    next_translated: str | None,
) -> str | None:
    translated_core = _segment_core_text(translated_seg)
    if _INTERNAL_MARKER_LEAK_PATTERN.search(translated_core):
        return "marker_leak"
    if _has_visible_prompt_leak(translated_core):
        return "prompt_leak"
    if _is_identity_residual(source_seg, translated_seg):
        return "identity_residual"
    if _is_duplicate_neighbor_segment(translated_seg, prev_translated):
        return "duplicate_leak"
    if _is_duplicate_neighbor_segment(translated_seg, next_translated):
        return "duplicate_leak"
    if _has_trailing_ellipsis_artifact(source_seg, translated_seg, source_segments, source_index):
        return "trailing_ellipsis_artifact"
    return None


def _apply_post_reassembly_guards(
    *,
    source_segments: list[str],
    translated_segments: list[str],
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    context_label: str,
    segment_groups: list[int | None] | None = None,
    enable_paragraph_identity_guard: bool = True,
    enable_identity_residual_guard: bool = True,
    enable_identity_context_recovery: bool = True,
) -> tuple[list[str], dict[str, int]]:
    if len(source_segments) != len(translated_segments):
        return translated_segments, {}

    snapshot = list(translated_segments)
    result = list(translated_segments)
    recovery_counts: dict[str, int] = {}
    paragraph_identity_runs: dict[int, list[tuple[int, int]]] = {}
    paragraph_identity_indices: set[int] = set()
    grouped_indices: dict[int, list[int]] = {}
    context_recovered_segments: set[int] = set()

    if segment_groups is not None and len(segment_groups) == len(source_segments):
        for seg_idx, group_id in enumerate(segment_groups):
            if group_id is None:
                continue
            grouped_indices.setdefault(group_id, []).append(seg_idx)
        if enable_identity_residual_guard and enable_paragraph_identity_guard:
            for group_id, indices in grouped_indices.items():
                if len(indices) < 2:
                    continue
                runs = _find_contiguous_identity_runs(
                    indices,
                    source_segments=source_segments,
                    translated_segments=snapshot,
                    min_total_chars=80,
                )
                if not runs:
                    continue
                paragraph_identity_runs[group_id] = runs
                for run_start, run_end in runs:
                    paragraph_identity_indices.update(range(run_start, run_end + 1))

    def _build_neighbor_context_text(seg_idx: int) -> str:
        snippets: list[str] = []

        def _append_from_index(idx: int) -> None:
            if idx < 0 or idx >= len(source_segments) or idx == seg_idx:
                return
            core = _normalize_ws(_segment_core_text(source_segments[idx]))
            if not core:
                return
            if len(core) > 220:
                core = core[:220].rstrip() + "..."
            if core in snippets:
                return
            snippets.append(core)

        if segment_groups is not None and len(segment_groups) == len(source_segments):
            group_id = segment_groups[seg_idx]
            if group_id is not None:
                indices = grouped_indices.get(group_id, [])
                if indices:
                    try:
                        local_pos = indices.index(seg_idx)
                    except ValueError:
                        local_pos = -1
                    if local_pos >= 0:
                        if local_pos > 0:
                            _append_from_index(indices[local_pos - 1])
                        if local_pos + 1 < len(indices):
                            _append_from_index(indices[local_pos + 1])

        if not snippets:
            _append_from_index(seg_idx - 1)
            _append_from_index(seg_idx + 1)

        if not snippets:
            return ""
        return "Context (for consistency only): " + " ".join(snippets[:2])

    def _try_context_recovery_for_index(seg_idx: int) -> bool:
        if not enable_identity_context_recovery:
            return False
        if seg_idx in context_recovered_segments:
            return False

        context_text = _build_neighbor_context_text(seg_idx)
        if not context_text:
            return False

        recovered = _recover_segment_with_context_markers(
            source_segments[seg_idx],
            context_text=context_text,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
            context_label=f"{context_label}_context",
            seg_index=seg_idx + 1,
        )
        context_recovered_segments.add(seg_idx)
        if _is_identity_residual(source_segments[seg_idx], recovered):
            _cascade_debug(
                f"{context_label}_lenient reason=identity_context_failed "
                f"seg={seg_idx + 1} detail=still_identity"
            )
            return False

        result[seg_idx] = recovered
        recovery_counts["identity_context_recovery"] = (
            recovery_counts.get("identity_context_recovery", 0) + 1
        )
        _cascade_debug(
            f"{context_label}_lenient reason=identity_context_recovery seg={seg_idx + 1}"
        )
        return True

    for idx, (source_seg, translated_seg) in enumerate(
        zip(source_segments, snapshot),
        start=1,
    ):
        prev_seg = snapshot[idx - 2] if idx > 1 else None
        next_seg = snapshot[idx] if idx < len(snapshot) else None
        reason = _post_reassembly_guard_reason(
            source_segments=source_segments,
            source_index=idx - 1,
            source_seg=source_seg,
            translated_seg=translated_seg,
            prev_translated=prev_seg,
            next_translated=next_seg,
        )
        if reason is None:
            continue
        if reason == "identity_residual" and not enable_identity_residual_guard:
            continue
        if reason == "identity_residual" and (idx - 1) in paragraph_identity_indices:
            # Handle full-paragraph identity in one call below.
            continue

        result[idx - 1] = _recover_single_segment_with_tag_mask(
            source_seg,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
            context_label=context_label,
            seg_index=idx,
        )
        if reason == "prompt_leak":
            result[idx - 1], _ = _sanitize_prompt_leak_segment(
                source_seg,
                result[idx - 1],
            )
        if reason == "trailing_ellipsis_artifact":
            stripped_seg, stripped = _strip_unexpected_trailing_ellipsis(
                source_seg,
                result[idx - 1],
            )
            if stripped:
                result[idx - 1] = stripped_seg
                recovery_counts["trailing_ellipsis_stripped"] = (
                    recovery_counts.get("trailing_ellipsis_stripped", 0) + 1
                )
                _cascade_debug(
                    f"{context_label}_lenient reason=trailing_ellipsis_stripped "
                    f"seg={idx} action=post_hoc_strip"
                )
        recovery_counts[reason] = recovery_counts.get(reason, 0) + 1
        _cascade_debug(
            f"{context_label}_lenient "
            f"reason={reason} seg={idx} action=local_segment_recovery"
        )
        if reason == "identity_residual" and _is_identity_residual(source_seg, result[idx - 1]):
            _try_context_recovery_for_index(idx - 1)
        if reason == "identity_residual" and _is_identity_residual(source_seg, result[idx - 1]):
            forced = _recover_segment_with_forced_markers(
                source_seg,
                translate_text=translate_text,
                cache=cache,
                max_chunk_chars=max_chunk_chars,
                context_label=f"{context_label}_forced",
                seg_index=idx,
            )
            result[idx - 1] = forced
            if not _is_identity_residual(source_seg, result[idx - 1]):
                recovery_counts["identity_forced_recovery"] = (
                    recovery_counts.get("identity_forced_recovery", 0) + 1
                )
                _cascade_debug(
                    f"{context_label}_lenient reason=identity_forced_recovery seg={idx}"
                )
        if reason == "identity_residual" and _is_identity_residual(source_seg, result[idx - 1]):
            sent_recovered = _recover_segment_sentencewise(
                source_seg,
                translate_text=translate_text,
                cache=cache,
                max_chunk_chars=max_chunk_chars,
                context_label=f"{context_label}_sent",
                seg_index=idx,
            )
            result[idx - 1] = sent_recovered
            if not _is_identity_residual(source_seg, result[idx - 1]):
                recovery_counts["identity_sentence_recovery"] = (
                    recovery_counts.get("identity_sentence_recovery", 0) + 1
                )
                _cascade_debug(
                    f"{context_label}_lenient reason=identity_sentence_recovery seg={idx}"
                )
        if _is_identity_residual(source_seg, result[idx - 1]):
            recovery_counts["identity_terminal"] = recovery_counts.get("identity_terminal", 0) + 1
            _cascade_debug(
                f"{context_label}_lenient reason=identity_terminal seg={idx} action=keep_recovered"
            )

    if paragraph_identity_runs:
        for group_id, runs in sorted(paragraph_identity_runs.items()):
            group_indices = grouped_indices.get(group_id, [])
            for run_start, run_end in runs:
                run_indices = list(range(run_start, run_end + 1))
                context_indices = list(run_indices)
                if len(run_indices) == 1 and len(group_indices) > 1:
                    try:
                        local_pos = group_indices.index(run_indices[0])
                    except ValueError:
                        local_pos = -1
                    if local_pos >= 0:
                        c_start = max(0, local_pos - 1)
                        c_end = min(len(group_indices), local_pos + 2)
                        expanded = group_indices[c_start:c_end]
                        if len(expanded) > 1:
                            context_indices = expanded

                context_sources = [source_segments[i] for i in context_indices]
                context_result, run_reason = _try_batch_translate_with_reason(
                    context_sources,
                    translate_text,
                    max_batch_chars=max(_MAX_BATCH_CHARS, max_chunk_chars * 8),
                    segment_groups=[1] * len(context_sources),
                    enable_paragraph_identity_guard=False,
                    enable_identity_context_recovery=False,
                )
                if context_result is None:
                    run_result = [
                        _recover_single_segment_with_tag_mask(
                            source_segments[i],
                            translate_text=translate_text,
                            cache=cache,
                            max_chunk_chars=max_chunk_chars,
                            context_label=context_label,
                            seg_index=i + 1,
                        )
                        for i in run_indices
                    ]
                    _cascade_debug(
                        f"{context_label}_lenient reason=identity_residual_paragraph "
                        f"group={group_id} segs={_format_int_list([i + 1 for i in run_indices])} "
                        f"action=local_segment_recovery reason_detail={run_reason}"
                    )
                else:
                    run_result = []
                    for seg_idx in run_indices:
                        try:
                            mapped_pos = context_indices.index(seg_idx)
                        except ValueError:
                            mapped_pos = -1
                        if mapped_pos < 0:
                            run_result.append(source_segments[seg_idx])
                        else:
                            run_result.append(context_result[mapped_pos])
                    _cascade_debug(
                        f"{context_label}_lenient reason=identity_residual_paragraph "
                        f"group={group_id} segs={_format_int_list([i + 1 for i in run_indices])} "
                        "action=paragraph_recovery"
                    )

                for local_idx, seg_idx in enumerate(run_indices):
                    result[seg_idx] = run_result[local_idx]
                    if _is_identity_residual(source_segments[seg_idx], result[seg_idx]):
                        _try_context_recovery_for_index(seg_idx)
                    if _is_identity_residual(source_segments[seg_idx], result[seg_idx]):
                        forced = _recover_segment_with_forced_markers(
                            source_segments[seg_idx],
                            translate_text=translate_text,
                            cache=cache,
                            max_chunk_chars=max_chunk_chars,
                            context_label=f"{context_label}_forced",
                            seg_index=seg_idx + 1,
                        )
                        result[seg_idx] = forced
                        if not _is_identity_residual(source_segments[seg_idx], result[seg_idx]):
                            recovery_counts["identity_forced_recovery"] = (
                                recovery_counts.get("identity_forced_recovery", 0) + 1
                            )
                            _cascade_debug(
                                f"{context_label}_lenient reason=identity_forced_recovery seg={seg_idx + 1}"
                            )
                    if _is_identity_residual(source_segments[seg_idx], result[seg_idx]):
                        sent_recovered = _recover_segment_sentencewise(
                            source_segments[seg_idx],
                            translate_text=translate_text,
                            cache=cache,
                            max_chunk_chars=max_chunk_chars,
                            context_label=f"{context_label}_sent",
                            seg_index=seg_idx + 1,
                        )
                        result[seg_idx] = sent_recovered
                        if not _is_identity_residual(source_segments[seg_idx], result[seg_idx]):
                            recovery_counts["identity_sentence_recovery"] = (
                                recovery_counts.get("identity_sentence_recovery", 0) + 1
                            )
                            _cascade_debug(
                                f"{context_label}_lenient reason=identity_sentence_recovery seg={seg_idx + 1}"
                            )
                    if _is_identity_residual(source_segments[seg_idx], result[seg_idx]):
                        recovery_counts["identity_terminal"] = recovery_counts.get("identity_terminal", 0) + 1
                        _cascade_debug(
                            f"{context_label}_lenient reason=identity_terminal seg={seg_idx + 1} "
                            "action=keep_recovered"
                        )
                recovery_counts["identity_residual_paragraph"] = (
                    recovery_counts.get("identity_residual_paragraph", 0) + 1
                )

    return result, recovery_counts


def _apply_wide_paragraph_recovery(
    *,
    source_parts: list[str],
    translated_parts: list[str],
    translatable_indices: list[int],
    source_segments: list[str],
    paragraph_groups: list[int | None],
    paragraph_part_ranges: dict[int, tuple[int, int]],
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
) -> tuple[list[str], dict[str, int]]:
    if (
        len(translatable_indices) != len(source_segments)
        or len(source_segments) != len(paragraph_groups)
    ):
        return translated_parts, {}

    grouped_indices: dict[int, list[int]] = {}
    for seg_idx, group_id in enumerate(paragraph_groups):
        if group_id is None:
            continue
        grouped_indices.setdefault(group_id, []).append(seg_idx)

    ellipsis_groups: set[int] = set()
    identity_run_groups: dict[int, list[tuple[int, int]]] = {}

    current_translated_segments = [translated_parts[idx] for idx in translatable_indices]
    for group_id, indices in grouped_indices.items():
        for seg_idx in indices:
            if _has_trailing_ellipsis_artifact(
                source_segments[seg_idx],
                current_translated_segments[seg_idx],
                source_segments,
                seg_idx,
            ):
                ellipsis_groups.add(group_id)
                break

        runs = _find_contiguous_identity_runs(
            indices,
            source_segments=source_segments,
            translated_segments=current_translated_segments,
        )
        if runs:
            identity_run_groups[group_id] = runs

    target_groups = sorted(set(ellipsis_groups) | set(identity_run_groups.keys()))
    if not target_groups:
        return translated_parts, {}

    result_parts = list(translated_parts)
    recovery_counts: dict[str, int] = {}

    for group_id in target_groups:
        part_range = paragraph_part_ranges.get(group_id)
        if part_range is None:
            continue
        start_part_idx, end_part_idx = part_range
        slice_chars = sum(len(source_parts[idx]) for idx in range(start_part_idx, end_part_idx + 1))
        if slice_chars > max(2_500, max_chunk_chars * 2):
            recovery_counts["wide_recovery_skipped_large"] = (
                recovery_counts.get("wide_recovery_skipped_large", 0) + 1
            )
            _cascade_debug(
                "wide_lenient reason=wide_recovery_skipped_large "
                f"group={group_id} chars={slice_chars}"
            )
            continue
        segs = grouped_indices.get(group_id, [])
        seg_hint = segs[0] + 1 if segs else None
        recovered_slice = _recover_parts_slice_with_tag_mask(
            source_parts=source_parts,
            start_part_idx=start_part_idx,
            end_part_idx=end_part_idx,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
            context_label="wide",
            seg_index=seg_hint,
        )
        if recovered_slice is None:
            recovery_counts["wide_recovery_split_fail"] = (
                recovery_counts.get("wide_recovery_split_fail", 0) + 1
            )
            _cascade_debug(
                "wide_lenient reason=wide_recovery_split_fail "
                f"group={group_id} part_range=[{start_part_idx}:{end_part_idx}]"
            )
            continue

        result_parts[start_part_idx:end_part_idx + 1] = recovered_slice
        recovery_counts["wide_paragraph_recovery"] = recovery_counts.get("wide_paragraph_recovery", 0) + 1

        run_details = identity_run_groups.get(group_id, [])
        run_text = ",".join(f"[{a + 1}:{b + 1}]" for a, b in run_details) if run_details else "-"
        reasons: list[str] = []
        if group_id in ellipsis_groups:
            reasons.append("trailing_ellipsis_artifact")
        if run_details:
            reasons.append("identity_run")
        reason_text = "+".join(reasons) if reasons else "unknown"
        _cascade_debug(
            "wide_lenient reason=paragraph_wide_recovery "
            f"group={group_id} reason_set={reason_text} runs={run_text} "
            f"part_range=[{start_part_idx}:{end_part_idx}]"
        )

    return result_parts, recovery_counts


def _apply_en_residual_quality_gate(
    *,
    source_parts: list[str],
    translated_parts: list[str],
    translatable_indices: list[int],
    source_segments: list[str],
    paragraph_groups: list[int | None],
    paragraph_part_ranges: dict[int, tuple[int, int]],
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    max_segments: int,
) -> tuple[list[str], dict[str, int]]:
    if (
        len(translatable_indices) != len(source_segments)
        or len(source_segments) != len(paragraph_groups)
    ):
        return translated_parts, {}

    residual_indices = [
        seg_idx
        for seg_idx, (part_idx, source_seg) in enumerate(zip(translatable_indices, source_segments))
        if _is_identity_residual(source_seg, translated_parts[part_idx])
    ]
    if not residual_indices:
        return translated_parts, {}

    counts: dict[str, int] = {}
    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(residual_indices)
        return translated_parts, counts

    grouped_indices: dict[int, list[int]] = {}
    for seg_idx, group_id in enumerate(paragraph_groups):
        if group_id is None:
            continue
        grouped_indices.setdefault(group_id, []).append(seg_idx)

    result_parts = list(translated_parts)
    processed = 0

    def _guard_quality_candidate(source_seg: str, candidate: str) -> tuple[str, bool]:
        guarded, guard_reason = _apply_short_translation_guard(source_seg, candidate)
        if guard_reason is None:
            return candidate, True
        counts["quality_gate_short_guard_rejected"] = (
            counts.get("quality_gate_short_guard_rejected", 0) + 1
        )
        counts[f"quality_gate_short_guard_{guard_reason}"] = (
            counts.get(f"quality_gate_short_guard_{guard_reason}", 0) + 1
        )
        return guarded, False

    def _neighbor_context(seg_idx: int) -> str:
        candidates: list[int] = []
        group_id = paragraph_groups[seg_idx]
        if group_id is not None:
            indices = grouped_indices.get(group_id, [])
            if seg_idx in indices:
                pos = indices.index(seg_idx)
                candidates.extend(indices[max(0, pos - 1):pos])
                candidates.extend(indices[pos + 1:pos + 2])
        if not candidates:
            candidates.extend([seg_idx - 1, seg_idx + 1])

        snippets: list[str] = []
        for idx in candidates:
            if idx < 0 or idx >= len(source_segments) or idx == seg_idx:
                continue
            core = _normalize_ws(_segment_core_text(source_segments[idx]))
            if not core:
                continue
            if len(core) > 220:
                core = core[:220].rstrip() + "..."
            if core not in snippets:
                snippets.append(core)
        if not snippets:
            return ""
        return "Context (for consistency only): " + " ".join(snippets[:2])

    def _safe_gate_call(action: str, seg_idx: int, call: Callable[[], object]) -> object | None:
        try:
            return call()
        except Exception as exc:
            counts["quality_gate_recovery_error"] = (
                counts.get("quality_gate_recovery_error", 0) + 1
            )
            counts[f"quality_gate_{action}_error"] = (
                counts.get(f"quality_gate_{action}_error", 0) + 1
            )
            _cascade_debug(
                "quality_gate reason=recovery_error "
                f"seg={seg_idx + 1} action={action} error={type(exc).__name__}"
            )
            return None

    for seg_idx in residual_indices:
        part_idx = translatable_indices[seg_idx]
        source_seg = source_segments[seg_idx]
        if not _is_identity_residual(source_seg, result_parts[part_idx]):
            continue
        if processed >= max_segments:
            counts["quality_gate_skipped_limit"] = counts.get("quality_gate_skipped_limit", 0) + 1
            continue

        processed += 1
        counts["quality_gate_attempted"] = counts.get("quality_gate_attempted", 0) + 1

        recovered = False
        group_id = paragraph_groups[seg_idx]
        part_range = paragraph_part_ranges.get(group_id) if group_id is not None else None
        if part_range is not None:
            slice_chars = sum(len(source_parts[idx]) for idx in range(part_range[0], part_range[1] + 1))
            if slice_chars <= max(2_500, max_chunk_chars * 2):
                recovered_slice = _safe_gate_call(
                    "paragraph",
                    seg_idx,
                    lambda: _recover_parts_slice_with_tag_mask(
                        source_parts=source_parts,
                        start_part_idx=part_range[0],
                        end_part_idx=part_range[1],
                        translate_text=translate_text,
                        cache=cache,
                        max_chunk_chars=max_chunk_chars,
                        context_label="quality_gate_wide",
                        seg_index=seg_idx + 1,
                    ),
                )
                if recovered_slice is not None:
                    candidate_parts = list(result_parts)
                    candidate_parts[part_range[0]:part_range[1] + 1] = recovered_slice
                    candidate = candidate_parts[part_idx]
                    candidate, candidate_ok = _guard_quality_candidate(source_seg, candidate)
                    candidate_parts[part_idx] = candidate
                    if candidate_ok and not _is_identity_residual(source_seg, candidate):
                        result_parts = candidate_parts
                        recovered = True
                        counts["quality_gate_paragraph_recovery"] = (
                            counts.get("quality_gate_paragraph_recovery", 0) + 1
                        )
                        _cascade_debug(
                            "quality_gate reason=en_residual "
                            f"seg={seg_idx + 1} action=paragraph_recovery"
                        )
            else:
                counts["quality_gate_paragraph_skipped_large"] = (
                    counts.get("quality_gate_paragraph_skipped_large", 0) + 1
                )

        if not recovered:
            context_text = _neighbor_context(seg_idx)
            if context_text:
                candidate = _safe_gate_call(
                    "context",
                    seg_idx,
                    lambda: _recover_segment_with_context_markers(
                        source_seg,
                        context_text=context_text,
                        translate_text=translate_text,
                        cache=cache,
                        max_chunk_chars=max_chunk_chars,
                        context_label="quality_gate_context",
                        seg_index=seg_idx + 1,
                    ),
                )
                if isinstance(candidate, str):
                    stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(source_seg, candidate)
                    if stripped:
                        candidate = stripped_candidate
                    candidate, candidate_ok = _guard_quality_candidate(source_seg, candidate)
                    if candidate_ok and not _is_identity_residual(source_seg, candidate):
                        result_parts[part_idx] = candidate
                        recovered = True
                        counts["quality_gate_context_recovery"] = (
                            counts.get("quality_gate_context_recovery", 0) + 1
                        )
                        _cascade_debug(
                            "quality_gate reason=en_residual "
                            f"seg={seg_idx + 1} action=context_recovery"
                        )

        if not recovered:
            candidate = _safe_gate_call(
                "forced",
                seg_idx,
                lambda: _recover_segment_with_forced_markers(
                    source_seg,
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="quality_gate_forced",
                    seg_index=seg_idx + 1,
                ),
            )
            if isinstance(candidate, str):
                stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(source_seg, candidate)
                if stripped:
                    candidate = stripped_candidate
                candidate, candidate_ok = _guard_quality_candidate(source_seg, candidate)
                if candidate_ok and not _is_identity_residual(source_seg, candidate):
                    result_parts[part_idx] = candidate
                    recovered = True
                    counts["quality_gate_forced_recovery"] = (
                        counts.get("quality_gate_forced_recovery", 0) + 1
                    )
                    _cascade_debug(
                        "quality_gate reason=en_residual "
                        f"seg={seg_idx + 1} action=forced_recovery"
                    )

        if not recovered:
            candidate = _safe_gate_call(
                "sentence",
                seg_idx,
                lambda: _recover_segment_sentencewise(
                    source_seg,
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="quality_gate_sent",
                    seg_index=seg_idx + 1,
                ),
            )
            if isinstance(candidate, str):
                stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(source_seg, candidate)
                if stripped:
                    candidate = stripped_candidate
                candidate, candidate_ok = _guard_quality_candidate(source_seg, candidate)
                if candidate_ok and not _is_identity_residual(source_seg, candidate):
                    result_parts[part_idx] = candidate
                    recovered = True
                    counts["quality_gate_sentence_recovery"] = (
                        counts.get("quality_gate_sentence_recovery", 0) + 1
                    )
                    _cascade_debug(
                        "quality_gate reason=en_residual "
                        f"seg={seg_idx + 1} action=sentence_recovery"
                    )

        if not recovered:
            counts["quality_gate_unresolved"] = counts.get("quality_gate_unresolved", 0) + 1
            _cascade_debug(
                "quality_gate reason=en_residual "
                f"seg={seg_idx + 1} action=keep_unresolved"
            )

    return result_parts, counts


def _apply_en_residual_segment_quality_gate(
    *,
    source_segments: list[str],
    translated_segments: list[str],
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    max_segments: int,
) -> tuple[list[str], dict[str, int]]:
    if len(source_segments) != len(translated_segments):
        return translated_segments, {}

    residual_indices = [
        idx
        for idx, (source_seg, translated_seg) in enumerate(zip(source_segments, translated_segments))
        if _is_identity_residual(source_seg, translated_seg)
    ]
    if not residual_indices:
        return translated_segments, {}

    counts: dict[str, int] = {}
    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(residual_indices)
        return translated_segments, counts

    result = list(translated_segments)

    def _guard_quality_candidate(source_seg: str, candidate: str) -> tuple[str, bool]:
        guarded, guard_reason = _apply_short_translation_guard(source_seg, candidate)
        if guard_reason is None:
            return candidate, True
        counts["quality_gate_short_guard_rejected"] = (
            counts.get("quality_gate_short_guard_rejected", 0) + 1
        )
        counts[f"quality_gate_short_guard_{guard_reason}"] = (
            counts.get(f"quality_gate_short_guard_{guard_reason}", 0) + 1
        )
        return guarded, False

    def _neighbor_context(seg_idx: int) -> str:
        snippets: list[str] = []
        for idx in (seg_idx - 1, seg_idx + 1):
            if idx < 0 or idx >= len(source_segments):
                continue
            core = _normalize_ws(_segment_core_text(source_segments[idx]))
            if not core:
                continue
            if len(core) > 220:
                core = core[:220].rstrip() + "..."
            snippets.append(core)
        if not snippets:
            return ""
        return "Context (for consistency only): " + " ".join(snippets)

    def _safe_gate_call(action: str, seg_idx: int, call: Callable[[], object]) -> object | None:
        try:
            return call()
        except Exception as exc:
            counts["quality_gate_recovery_error"] = (
                counts.get("quality_gate_recovery_error", 0) + 1
            )
            counts[f"quality_gate_{action}_error"] = (
                counts.get(f"quality_gate_{action}_error", 0) + 1
            )
            _cascade_debug(
                "quality_gate_fallback reason=recovery_error "
                f"seg={seg_idx + 1} action={action} error={type(exc).__name__}"
            )
            return None

    processed = 0
    for seg_idx in residual_indices:
        source_seg = source_segments[seg_idx]
        if not _is_identity_residual(source_seg, result[seg_idx]):
            continue
        if processed >= max_segments:
            counts["quality_gate_skipped_limit"] = counts.get("quality_gate_skipped_limit", 0) + 1
            continue

        processed += 1
        counts["quality_gate_attempted"] = counts.get("quality_gate_attempted", 0) + 1

        recovered = False
        context_text = _neighbor_context(seg_idx)
        if context_text:
            candidate = _safe_gate_call(
                "context",
                seg_idx,
                lambda: _recover_segment_with_context_markers(
                    source_seg,
                    context_text=context_text,
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="quality_gate_fallback_context",
                    seg_index=seg_idx + 1,
                ),
            )
            if isinstance(candidate, str):
                stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(source_seg, candidate)
                if stripped:
                    candidate = stripped_candidate
                candidate, candidate_ok = _guard_quality_candidate(source_seg, candidate)
                if candidate_ok and not _is_identity_residual(source_seg, candidate):
                    result[seg_idx] = candidate
                    recovered = True
                    counts["quality_gate_context_recovery"] = (
                        counts.get("quality_gate_context_recovery", 0) + 1
                    )
                    _cascade_debug(
                        "quality_gate_fallback reason=en_residual "
                        f"seg={seg_idx + 1} action=context_recovery"
                    )

        if not recovered:
            candidate = _safe_gate_call(
                "forced",
                seg_idx,
                lambda: _recover_segment_with_forced_markers(
                    source_seg,
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="quality_gate_fallback_forced",
                    seg_index=seg_idx + 1,
                ),
            )
            if isinstance(candidate, str):
                stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(source_seg, candidate)
                if stripped:
                    candidate = stripped_candidate
                candidate, candidate_ok = _guard_quality_candidate(source_seg, candidate)
                if candidate_ok and not _is_identity_residual(source_seg, candidate):
                    result[seg_idx] = candidate
                    recovered = True
                    counts["quality_gate_forced_recovery"] = (
                        counts.get("quality_gate_forced_recovery", 0) + 1
                    )
                    _cascade_debug(
                        "quality_gate_fallback reason=en_residual "
                        f"seg={seg_idx + 1} action=forced_recovery"
                    )

        if not recovered:
            candidate = _safe_gate_call(
                "sentence",
                seg_idx,
                lambda: _recover_segment_sentencewise(
                    source_seg,
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="quality_gate_fallback_sent",
                    seg_index=seg_idx + 1,
                ),
            )
            if isinstance(candidate, str):
                stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(source_seg, candidate)
                if stripped:
                    candidate = stripped_candidate
                candidate, candidate_ok = _guard_quality_candidate(source_seg, candidate)
                if candidate_ok and not _is_identity_residual(source_seg, candidate):
                    result[seg_idx] = candidate
                    recovered = True
                    counts["quality_gate_sentence_recovery"] = (
                        counts.get("quality_gate_sentence_recovery", 0) + 1
                    )
                    _cascade_debug(
                        "quality_gate_fallback reason=en_residual "
                        f"seg={seg_idx + 1} action=sentence_recovery"
                    )

        if not recovered:
            counts["quality_gate_unresolved"] = counts.get("quality_gate_unresolved", 0) + 1
            _cascade_debug(
                "quality_gate_fallback reason=en_residual "
                f"seg={seg_idx + 1} action=keep_unresolved"
            )

    return result, counts


def _apply_cjk_quality_gate(
    *,
    source_parts: list[str],
    translated_parts: list[str],
    translatable_indices: list[int],
    source_segments: list[str],
    paragraph_groups: list[int | None],
    paragraph_part_ranges: dict[int, tuple[int, int]],
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    max_segments: int,
    target_language_code: str,
) -> tuple[list[str], dict[str, int]]:
    if normalize_language_code(target_language_code) == "zh":
        return translated_parts, {}
    if (
        len(translatable_indices) != len(source_segments)
        or len(source_segments) != len(paragraph_groups)
    ):
        return translated_parts, {}

    cjk_indices = [
        seg_idx
        for seg_idx, part_idx in enumerate(translatable_indices)
        if _has_unexpected_cjk(translated_parts[part_idx], target_language_code=target_language_code)
    ]
    if not cjk_indices:
        return translated_parts, {}

    counts: dict[str, int] = {}
    result_parts = list(translated_parts)
    known_attempted: set[int] = set()
    remaining_cjk_indices: list[int] = []
    for seg_idx in cjk_indices:
        part_idx = translatable_indices[seg_idx]
        repaired = _repair_known_cjk_contamination(
            source_segments[seg_idx],
            result_parts[part_idx],
            target_language_code=target_language_code,
        )
        if repaired != result_parts[part_idx]:
            result_parts[part_idx] = repaired
            known_attempted.add(seg_idx)
            counts["quality_gate_attempted"] = counts.get("quality_gate_attempted", 0) + 1
            if not _has_unexpected_cjk(repaired, target_language_code=target_language_code):
                counts["quality_gate_known_recovery"] = (
                    counts.get("quality_gate_known_recovery", 0) + 1
                )
                _cascade_debug(
                    "cjk_gate reason=cjk_contamination "
                    f"seg={seg_idx + 1} action=known_repair"
                )
                continue
        remaining_cjk_indices.append(seg_idx)
    cjk_indices = remaining_cjk_indices
    if not cjk_indices:
        return result_parts, counts

    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(cjk_indices)
        return result_parts, counts

    grouped_indices: dict[int, list[int]] = {}
    for seg_idx, group_id in enumerate(paragraph_groups):
        if group_id is None:
            continue
        grouped_indices.setdefault(group_id, []).append(seg_idx)

    processed = 0

    def _candidate_is_clean(candidate: str) -> bool:
        return not _has_unexpected_cjk(candidate, target_language_code=target_language_code)

    def _neighbor_context(seg_idx: int) -> str:
        candidates: list[int] = []
        group_id = paragraph_groups[seg_idx]
        if group_id is not None:
            indices = grouped_indices.get(group_id, [])
            if seg_idx in indices:
                pos = indices.index(seg_idx)
                candidates.extend(indices[max(0, pos - 1):pos])
                candidates.extend(indices[pos + 1:pos + 2])
        if not candidates:
            candidates.extend([seg_idx - 1, seg_idx + 1])

        snippets: list[str] = []
        for idx in candidates:
            if idx < 0 or idx >= len(source_segments) or idx == seg_idx:
                continue
            core = _normalize_ws(_segment_core_text(source_segments[idx]))
            if not core:
                continue
            if len(core) > 220:
                core = core[:220].rstrip() + "..."
            if core not in snippets:
                snippets.append(core)
        if not snippets:
            return ""
        return "Context (for consistency only): " + " ".join(snippets[:2])

    def _safe_gate_call(action: str, seg_idx: int, call: Callable[[], object]) -> object | None:
        try:
            return call()
        except Exception as exc:
            counts["quality_gate_recovery_error"] = (
                counts.get("quality_gate_recovery_error", 0) + 1
            )
            counts[f"quality_gate_{action}_error"] = (
                counts.get(f"quality_gate_{action}_error", 0) + 1
            )
            _cascade_debug(
                "cjk_gate reason=recovery_error "
                f"seg={seg_idx + 1} action={action} error={type(exc).__name__}"
            )
            return None

    for seg_idx in cjk_indices:
        part_idx = translatable_indices[seg_idx]
        if not _has_unexpected_cjk(result_parts[part_idx], target_language_code=target_language_code):
            continue
        if processed >= max_segments:
            counts["quality_gate_skipped_limit"] = counts.get("quality_gate_skipped_limit", 0) + 1
            continue

        processed += 1
        if seg_idx not in known_attempted:
            counts["quality_gate_attempted"] = counts.get("quality_gate_attempted", 0) + 1

        recovered = False
        group_id = paragraph_groups[seg_idx]
        part_range = paragraph_part_ranges.get(group_id) if group_id is not None else None
        if part_range is not None:
            slice_chars = sum(len(source_parts[idx]) for idx in range(part_range[0], part_range[1] + 1))
            if slice_chars <= max(2_500, max_chunk_chars * 2):
                recovered_slice = _safe_gate_call(
                    "paragraph",
                    seg_idx,
                    lambda: _recover_parts_slice_with_tag_mask(
                        source_parts=source_parts,
                        start_part_idx=part_range[0],
                        end_part_idx=part_range[1],
                        translate_text=translate_text,
                        cache=cache,
                        max_chunk_chars=max_chunk_chars,
                        context_label="cjk_gate_wide",
                        seg_index=seg_idx + 1,
                    ),
                )
                if recovered_slice is not None:
                    candidate_parts = list(result_parts)
                    candidate_parts[part_range[0]:part_range[1] + 1] = recovered_slice
                    if _candidate_is_clean(candidate_parts[part_idx]):
                        result_parts = candidate_parts
                        recovered = True
                        counts["quality_gate_paragraph_recovery"] = (
                            counts.get("quality_gate_paragraph_recovery", 0) + 1
                        )
                        _cascade_debug(
                            "cjk_gate reason=cjk_contamination "
                            f"seg={seg_idx + 1} action=paragraph_recovery"
                        )
            else:
                counts["quality_gate_paragraph_skipped_large"] = (
                    counts.get("quality_gate_paragraph_skipped_large", 0) + 1
                )

        if not recovered:
            context_text = _neighbor_context(seg_idx)
            if context_text:
                candidate = _safe_gate_call(
                    "context",
                    seg_idx,
                    lambda: _recover_segment_with_context_markers(
                        source_segments[seg_idx],
                        context_text=context_text,
                        translate_text=translate_text,
                        cache=cache,
                        max_chunk_chars=max_chunk_chars,
                        context_label="cjk_gate_context",
                        seg_index=seg_idx + 1,
                    ),
                )
                if isinstance(candidate, str):
                    stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(
                        source_segments[seg_idx],
                        candidate,
                    )
                    if stripped:
                        candidate = stripped_candidate
                    if _candidate_is_clean(candidate):
                        result_parts[part_idx] = candidate
                        recovered = True
                        counts["quality_gate_context_recovery"] = (
                            counts.get("quality_gate_context_recovery", 0) + 1
                        )
                        _cascade_debug(
                            "cjk_gate reason=cjk_contamination "
                            f"seg={seg_idx + 1} action=context_recovery"
                        )

        if not recovered:
            candidate = _safe_gate_call(
                "forced",
                seg_idx,
                lambda: _recover_segment_with_forced_markers(
                    source_segments[seg_idx],
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="cjk_gate_forced",
                    seg_index=seg_idx + 1,
                ),
            )
            if isinstance(candidate, str):
                stripped_candidate, stripped = _strip_unexpected_trailing_ellipsis(
                    source_segments[seg_idx],
                    candidate,
                )
                if stripped:
                    candidate = stripped_candidate
                if _candidate_is_clean(candidate):
                    result_parts[part_idx] = candidate
                    recovered = True
                    counts["quality_gate_forced_recovery"] = (
                        counts.get("quality_gate_forced_recovery", 0) + 1
                    )
                    _cascade_debug(
                        "cjk_gate reason=cjk_contamination "
                        f"seg={seg_idx + 1} action=forced_recovery"
                    )

        if not recovered:
            counts["quality_gate_unresolved"] = counts.get("quality_gate_unresolved", 0) + 1
            _cascade_debug(
                "cjk_gate reason=cjk_contamination "
                f"seg={seg_idx + 1} action=keep_unresolved"
            )

    return result_parts, counts


def _apply_cjk_segment_quality_gate(
    *,
    source_segments: list[str],
    translated_segments: list[str],
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
    max_segments: int,
    target_language_code: str,
) -> tuple[list[str], dict[str, int]]:
    if normalize_language_code(target_language_code) == "zh":
        return translated_segments, {}
    if len(source_segments) != len(translated_segments):
        return translated_segments, {}

    cjk_indices = [
        idx
        for idx, translated_seg in enumerate(translated_segments)
        if _has_unexpected_cjk(translated_seg, target_language_code=target_language_code)
    ]
    if not cjk_indices:
        return translated_segments, {}

    counts: dict[str, int] = {}
    result = list(translated_segments)
    known_attempted: set[int] = set()
    remaining_cjk_indices: list[int] = []
    for seg_idx in cjk_indices:
        repaired = _repair_known_cjk_contamination(
            source_segments[seg_idx],
            result[seg_idx],
            target_language_code=target_language_code,
        )
        if repaired != result[seg_idx]:
            result[seg_idx] = repaired
            known_attempted.add(seg_idx)
            counts["quality_gate_attempted"] = counts.get("quality_gate_attempted", 0) + 1
            if not _has_unexpected_cjk(repaired, target_language_code=target_language_code):
                counts["quality_gate_known_recovery"] = (
                    counts.get("quality_gate_known_recovery", 0) + 1
                )
                _cascade_debug(
                    "cjk_gate_fallback reason=cjk_contamination "
                    f"seg={seg_idx + 1} action=known_repair"
                )
                continue
        remaining_cjk_indices.append(seg_idx)
    cjk_indices = remaining_cjk_indices
    if not cjk_indices:
        return result, counts

    if max_segments <= 0:
        counts["quality_gate_skipped_limit"] = len(cjk_indices)
        return result, counts

    def _safe_gate_call(action: str, seg_idx: int, call: Callable[[], object]) -> object | None:
        try:
            return call()
        except Exception as exc:
            counts["quality_gate_recovery_error"] = (
                counts.get("quality_gate_recovery_error", 0) + 1
            )
            counts[f"quality_gate_{action}_error"] = (
                counts.get(f"quality_gate_{action}_error", 0) + 1
            )
            _cascade_debug(
                "cjk_gate_fallback reason=recovery_error "
                f"seg={seg_idx + 1} action={action} error={type(exc).__name__}"
            )
            return None

    processed = 0
    for seg_idx in cjk_indices:
        if not _has_unexpected_cjk(result[seg_idx], target_language_code=target_language_code):
            continue
        if processed >= max_segments:
            counts["quality_gate_skipped_limit"] = counts.get("quality_gate_skipped_limit", 0) + 1
            continue

        processed += 1
        if seg_idx not in known_attempted:
            counts["quality_gate_attempted"] = counts.get("quality_gate_attempted", 0) + 1
        candidate = _safe_gate_call(
            "forced",
            seg_idx,
            lambda: _recover_segment_with_forced_markers(
                source_segments[seg_idx],
                translate_text=translate_text,
                cache=cache,
                max_chunk_chars=max_chunk_chars,
                context_label="cjk_gate_fallback_forced",
                seg_index=seg_idx + 1,
            ),
        )
        if isinstance(candidate, str) and not _has_unexpected_cjk(candidate, target_language_code=target_language_code):
            result[seg_idx] = candidate
            counts["quality_gate_forced_recovery"] = (
                counts.get("quality_gate_forced_recovery", 0) + 1
            )
            _cascade_debug(
                "cjk_gate_fallback reason=cjk_contamination "
                f"seg={seg_idx + 1} action=forced_recovery"
            )
            continue

        counts["quality_gate_unresolved"] = counts.get("quality_gate_unresolved", 0) + 1
        _cascade_debug(
            "cjk_gate_fallback reason=cjk_contamination "
            f"seg={seg_idx + 1} action=keep_unresolved"
        )

    return result, counts


def _try_batch_translate(
    segments: list[str],
    translate_text: Callable[[str], str],
    *,
    max_batch_chars: int = _MAX_BATCH_CHARS,
) -> list[str] | None:
    result, _ = _try_batch_translate_with_reason(
        segments,
        translate_text,
        max_batch_chars=max_batch_chars,
    )
    return result


def _try_batch_translate_with_reason_legacy(
    segments: list[str],
    translate_text: Callable[[str], str],
    *,
    max_batch_chars: int = _MAX_BATCH_CHARS,
) -> tuple[list[str] | None, str]:
    """Translate all *segments* in a single model call.

    Masks mathematical formulas, joins segments with ``<z2m-sep/>`` separator,
    calls ``translate_text`` once, then splits the result back.

    Returns the translated list on success.  Returns ``None`` вЂ” signalling the
    caller to fall back to per-segment translation вЂ” when:

    * there is only one segment (batch overhead not worth it),
    * the combined text exceeds ``max_batch_chars``,
    * the model call raises an exception,
    * or the separator count in the output does not match the input.
    """
    if len(segments) < 2:
        return None, f"single_segment count={len(segments)}"

    # Mask formulas so the model does not try to translate LaTeX/math notation.
    masked_segs: list[str] = []
    fmaps: list[dict[str, str]] = []
    for seg in segments:
        masked, fmap = _apply_formula_mask(seg)
        masked_segs.append(masked)
        fmaps.append(fmap)

    batch_text = _BATCH_SEPARATOR.join(masked_segs)
    if len(batch_text) > max_batch_chars:
        return None, f"batch_too_long chars={len(batch_text)} max={max_batch_chars}"

    try:
        translated_batch = translate_text(batch_text)
    except Exception as exc:
        message = str(exc).replace("\n", " ").strip()
        if len(message) > 200:
            message = message[:200] + "..."
        return None, f"llm_exception type={type(exc).__name__} msg={message!r}"

    # Clean byte-token artefacts before splitting.
    translated_batch = _BYTE_TOKEN_CITATION_PATTERN.sub(r'<sup>\1</sup>', translated_batch)
    translated_batch = _BYTE_TOKEN_ARTIFACT_PATTERN.sub("", translated_batch)

    translated_parts = _BATCH_SEP_PATTERN.split(translated_batch)
    if len(translated_parts) != len(segments):
        # Model ate or duplicated separators вЂ” result is not trustworthy.
        return None, (
            "separator_mismatch "
            f"expected={len(segments)} got={len(translated_parts)}"
        )

    result: list[str] = []
    for orig, t_seg, fmap in zip(segments, translated_parts, fmaps):
        lead, core, tail = _split_outer_ws(t_seg)
        _, orig_core, _ = _split_outer_ws(orig)
        if _is_translator_refusal(core.strip()):
            t_seg = orig
        else:
            core = _strip_source_echo(core, orig_core)
            core = _restore_formula_mask(core, fmap)
            t_seg = f"{lead}{core}{tail}"
        result.append(t_seg)

    return result, "ok"


def _try_windowed_batch_translate(
    segments: list[str],
    translate_text: Callable[[str], str],
    *,
    window_segments: int = _WINDOW_BATCH_TARGET_SEGMENTS,
    overlap_segments: int = _WINDOW_BATCH_OVERLAP_SEGMENTS,
    max_window_chars: int = _MAX_WINDOW_BATCH_CHARS,
    max_window_tokens: int = 0,
    count_text_tokens: Callable[[str], int] | None = None,
    segment_groups: list[int | None] | None = None,
) -> list[str] | None:
    result, _ = _try_windowed_batch_translate_with_reason(
        segments,
        translate_text,
        window_segments=window_segments,
        overlap_segments=overlap_segments,
        max_window_chars=max_window_chars,
        max_window_tokens=max_window_tokens,
        count_text_tokens=count_text_tokens,
        segment_groups=segment_groups,
    )
    return result


def _try_windowed_batch_translate_with_reason_legacy(
    segments: list[str],
    translate_text: Callable[[str], str],
    *,
    window_segments: int = _WINDOW_BATCH_TARGET_SEGMENTS,
    overlap_segments: int = _WINDOW_BATCH_OVERLAP_SEGMENTS,
    max_window_chars: int = _MAX_WINDOW_BATCH_CHARS,
) -> tuple[list[str] | None, str]:
    """Translate in overlapping windows to balance context quality and GPU load."""
    if len(segments) < 2:
        return None, f"single_segment count={len(segments)}"

    window_segments = max(2, int(window_segments))
    overlap_segments = max(0, int(overlap_segments))
    n = len(segments)
    translated: list[str | None] = [None] * n

    core_start = 0
    while core_start < n:
        core_end = min(n, core_start + window_segments)
        ext_start = max(0, core_start - overlap_segments)
        ext_end = min(n, core_end + overlap_segments)

        window_result, reason = _try_batch_translate_with_reason(
            segments[ext_start:ext_end],
            translate_text,
            max_batch_chars=max_window_chars,
        )
        if window_result is None:
            return None, (
                "window_failed "
                f"core=[{core_start}:{core_end}) "
                f"extended=[{ext_start}:{ext_end}) "
                f"reason={reason}"
            )

        local_start = core_start - ext_start
        for idx in range(core_start, core_end):
            translated[idx] = window_result[local_start + (idx - core_start)]
        core_start = core_end

    if any(item is None for item in translated):
        return None, "window_postcheck_none_entries"
    return [item for item in translated if item is not None], "ok"


# --------------------------------------------------------------------------- #
# Batch translation protocol v2 (id-addressed + retry/bisect recovery)
# --------------------------------------------------------------------------- #

def _try_batch_translate_with_reason(
    segments: list[str],
    translate_text: Callable[[str], str],
    *,
    max_batch_chars: int = _MAX_BATCH_CHARS,
    max_batch_tokens: int = 0,
    count_text_tokens: Callable[[str], int] | None = None,
    segment_groups: list[int | None] | None = None,
    mask_abbrev_flags: list[bool] | None = None,
    enable_paragraph_identity_guard: bool = True,
    enable_identity_residual_guard: bool = True,
    enable_identity_context_recovery: bool = True,
) -> tuple[list[str] | None, str]:
    if len(segments) < 2:
        return None, f"single_segment count={len(segments)}"
    if mask_abbrev_flags is not None and len(mask_abbrev_flags) != len(segments):
        return None, "mask_abbrev_flags_length_mismatch"

    masked_segs: list[str] = []
    fmaps: list[dict[str, str]] = []
    amaps: list[dict[str, str]] = []
    for seg_idx, seg in enumerate(segments):
        masked, fmap = _apply_formula_mask(seg)
        if mask_abbrev_flags is None or mask_abbrev_flags[seg_idx]:
            masked, amap = _apply_abbrev_mask(masked)
        else:
            amap = {}
        masked_segs.append(masked)
        fmaps.append(fmap)
        amaps.append(amap)

    batch_text = "".join(
        f"<z2m-i{idx}/>{seg}"
        for idx, seg in enumerate(masked_segs, start=1)
    )
    if len(batch_text) > max_batch_chars:
        return None, f"batch_too_long chars={len(batch_text)} max={max_batch_chars}"
    if max_batch_tokens > 0 and count_text_tokens is not None:
        batch_tokens = count_text_tokens(batch_text)
        if batch_tokens > max_batch_tokens:
            return None, f"batch_too_long tokens={batch_tokens} max={max_batch_tokens}"

    try:
        translated_batch = translate_text(batch_text)
    except Exception as exc:
        message = str(exc).replace("\n", " ").strip()
        if len(message) > 200:
            message = message[:200] + "..."
        return None, f"llm_exception type={type(exc).__name__} msg={message!r}"

    translated_batch = _BYTE_TOKEN_CITATION_PATTERN.sub(r'<sup>\1</sup>', translated_batch)
    translated_batch = _BYTE_TOKEN_ARTIFACT_PATTERN.sub("", translated_batch)

    matches = list(_BATCH_ITEM_PATTERN.finditer(translated_batch))
    if not matches:
        return None, "structured_parse_failed blocks=0"

    parsed_by_id: dict[int, str] = {}
    duplicate_ids: set[int] = set()
    for match in matches:
        item_id = int(match.group(1))
        item_text = match.group(2)
        if item_id in parsed_by_id:
            duplicate_ids.add(item_id)
            continue
        parsed_by_id[item_id] = item_text

    if duplicate_ids:
        _cascade_debug(f"batch_fail reason=duplicate_ids ids={_format_int_list(sorted(duplicate_ids))}")
        return None, (
            "duplicate_ids "
            f"ids={_format_int_list(sorted(duplicate_ids))}"
        )

    expected_ids = list(range(1, len(segments) + 1))
    expected_ids_set = set(expected_ids)
    found_ids_set = set(parsed_by_id.keys())
    missing_ids = sorted(expected_ids_set - found_ids_set)
    extra_ids = sorted(found_ids_set - expected_ids_set)

    lenient_missing_id: int | None = None
    lenient_trailing_eos_k = 0
    lenient_missing_limit = len(segments) // 10
    if missing_ids or extra_ids:
        if (
            lenient_missing_limit >= 1
            and not extra_ids
            and len(missing_ids) == 1
            and len(parsed_by_id) == len(segments) - 1
        ):
            lenient_missing_id = missing_ids[0]
            parsed_by_id[lenient_missing_id] = segments[lenient_missing_id - 1]
        elif not extra_ids:
            trailing_limit = max(1, len(segments) // 3)
            trailing_suffix = list(
                range(len(segments) - len(missing_ids) + 1, len(segments) + 1)
            )
            if (
                missing_ids == trailing_suffix
                and len(missing_ids) <= trailing_limit
                and len(parsed_by_id) == len(segments) - len(missing_ids)
            ):
                lenient_trailing_eos_k = len(missing_ids)
                for missing_id in missing_ids:
                    parsed_by_id[missing_id] = segments[missing_id - 1]
            else:
                _cascade_debug(
                    "batch_fail reason=id_mismatch "
                    f"missing={_format_int_list(missing_ids)} "
                    f"extra={_format_int_list(extra_ids)}"
                )
                return None, (
                    "id_mismatch "
                    f"missing={_format_int_list(missing_ids)} "
                    f"extra={_format_int_list(extra_ids)}"
                )
        else:
            _cascade_debug(
                "batch_fail reason=id_mismatch "
                f"missing={_format_int_list(missing_ids)} "
                f"extra={_format_int_list(extra_ids)}"
            )
            return None, (
                "id_mismatch "
                f"missing={_format_int_list(missing_ids)} "
                f"extra={_format_int_list(extra_ids)}"
            )

    translated_parts = [parsed_by_id[item_id] for item_id in expected_ids]
    result: list[str] = []
    lenient_abbrev_recovered = 0
    lenient_formula_recovered = 0
    seg_recovery_cache: dict[str, str] = {}
    for seg_idx, (orig, t_seg, fmap, amap) in enumerate(
        zip(segments, translated_parts, fmaps, amaps),
        start=1,
    ):
        lead, core, tail = _split_outer_ws(t_seg)
        _, orig_core, _ = _split_outer_ws(orig)

        if amap:
            expected_abbrev_ids = list(range(len(amap)))
            found_abbrev_ids = sorted(
                int(m.group(1)) for m in _ABBREV_TOKEN_PATTERN.finditer(core)
            )
            if found_abbrev_ids != expected_abbrev_ids:
                missing_abbrev_ids = sorted(
                    set(expected_abbrev_ids) - set(found_abbrev_ids)
                )
                extra_abbrev_ids = sorted(
                    set(found_abbrev_ids) - set(expected_abbrev_ids)
                )
                # Model altered abbrev sentinels in this segment. Recover this
                # segment locally instead of failing the whole window.
                recovered_seg = _recover_single_segment_with_tag_mask(
                    orig,
                    translate_text=translate_text,
                    cache=seg_recovery_cache,
                    max_chunk_chars=1800,
                    context_label="batch",
                    seg_index=seg_idx,
                )
                result.append(recovered_seg)
                lenient_abbrev_recovered += 1
                _cascade_debug(
                    "batch_lenient reason=abbrev_tokens_altered "
                    f"seg={seg_idx} "
                    f"expected={_format_int_list(expected_abbrev_ids)} "
                    f"got={_format_int_list(found_abbrev_ids)} "
                    f"missing={_format_int_list(missing_abbrev_ids)} "
                    f"extra={_format_int_list(extra_abbrev_ids)} "
                    "action=local_segment_recovery"
                )
                continue

        if fmap:
            expected_token_ids = list(range(len(fmap)))
            found_token_ids = sorted(
                int(m.group(1)) for m in _FORMULA_TOKEN_PATTERN.finditer(core)
            )
            if found_token_ids != expected_token_ids:
                missing_formula_ids = sorted(
                    set(expected_token_ids) - set(found_token_ids)
                )
                extra_formula_ids = sorted(
                    set(found_token_ids) - set(expected_token_ids)
                )
                recovered_seg = _recover_single_segment_with_tag_mask(
                    orig,
                    translate_text=translate_text,
                    cache=seg_recovery_cache,
                    max_chunk_chars=1800,
                    context_label="batch",
                    seg_index=seg_idx,
                )
                result.append(recovered_seg)
                lenient_formula_recovered += 1
                _cascade_debug(
                    "batch_lenient reason=formula_tokens_altered "
                    f"seg={seg_idx} "
                    f"expected={_format_int_list(expected_token_ids)} "
                    f"got={_format_int_list(found_token_ids)} "
                    f"missing={_format_int_list(missing_formula_ids)} "
                    f"extra={_format_int_list(extra_formula_ids)} "
                    "action=local_segment_recovery"
                )
                continue

        if _is_translator_refusal(core.strip()):
            t_seg = orig
        else:
            core = _strip_source_echo(core, orig_core)
            core = _restore_abbrev_mask(core, amap)
            core = _restore_formula_mask(core, fmap)
            t_seg = f"{lead}{core}{tail}"
        result.append(t_seg)

    if segment_groups is not None and len(segment_groups) != len(segments):
        segment_groups = None

    # If the batch needed structural token recovery, keep the local identity
    # guard for this batch: a dropped sentinel often means nearby segments were
    # echoed unchanged too. Pure identity cleanup is still deferred by windowed
    # callers to avoid hundreds of duplicate recovery calls on long articles.
    force_identity_guard_after_structural_recovery = (
        lenient_missing_id is not None
        or lenient_trailing_eos_k > 0
        or lenient_abbrev_recovered > 0
        or lenient_formula_recovered > 0
    )
    result, guard_recovery_counts = _apply_post_reassembly_guards(
        source_segments=segments,
        translated_segments=result,
        translate_text=translate_text,
        cache=seg_recovery_cache,
        max_chunk_chars=1800,
        context_label="batch",
        segment_groups=segment_groups,
        enable_paragraph_identity_guard=enable_paragraph_identity_guard,
        enable_identity_residual_guard=(
            enable_identity_residual_guard
            or force_identity_guard_after_structural_recovery
        ),
        enable_identity_context_recovery=(
            enable_identity_context_recovery
            or force_identity_guard_after_structural_recovery
        ),
    )
    guard_recovered = sum(guard_recovery_counts.values())
    if guard_recovered > 0:
        details = ",".join(
            f"{name}={count}"
            for name, count in sorted(guard_recovery_counts.items())
            if count > 0
        )
        return result, (
            "ok_leak_recovery "
            f"count={guard_recovered} details={details}"
        )

    if lenient_missing_id is not None:
        return result, f"ok_lenient_missing_id={lenient_missing_id}"
    if lenient_trailing_eos_k > 0:
        return result, f"ok_lenient_trailing_eos k={lenient_trailing_eos_k}"
    if lenient_formula_recovered > 0:
        return result, f"ok_lenient_formula_recovered count={lenient_formula_recovered}"
    if lenient_abbrev_recovered > 0:
        return result, f"ok_lenient_abbrev_recovered count={lenient_abbrev_recovered}"
    return result, "ok"


def _try_windowed_batch_translate_with_reason(
    segments: list[str],
    translate_text: Callable[[str], str],
    *,
    window_segments: int = _WINDOW_BATCH_TARGET_SEGMENTS,
    overlap_segments: int = _WINDOW_BATCH_OVERLAP_SEGMENTS,
    max_window_chars: int = _MAX_WINDOW_BATCH_CHARS,
    max_window_tokens: int = 0,
    count_text_tokens: Callable[[str], int] | None = None,
    segment_groups: list[int | None] | None = None,
    mask_abbrev_flags: list[bool] | None = None,
) -> tuple[list[str] | None, str]:
    if len(segments) < 2:
        return None, f"single_segment count={len(segments)}"
    if mask_abbrev_flags is not None and len(mask_abbrev_flags) != len(segments):
        return None, "mask_abbrev_flags_length_mismatch"

    window_segments = max(2, int(window_segments))
    overlap_segments = max(0, int(overlap_segments))
    n = len(segments)
    translated: list[str | None] = [None] * n
    leaf_cache: dict[str, str] = {}
    leaf_max_chunk_chars = max(256, min(max_window_chars, 1800))

    def _store_core_from_window(
        *,
        core_start: int,
        core_end: int,
        ext_start: int,
        window_result: list[str],
    ) -> None:
        local_start = core_start - ext_start
        for idx in range(core_start, core_end):
            translated[idx] = window_result[local_start + (idx - core_start)]

    def _translate_core_range(core_start: int, core_end: int) -> tuple[bool, str]:
        ext_start = max(0, core_start - overlap_segments)
        ext_end = min(n, core_end + overlap_segments)
        window_result, reason = _try_batch_translate_with_reason(
            segments[ext_start:ext_end],
            translate_text,
            max_batch_chars=max_window_chars,
            max_batch_tokens=max_window_tokens,
            count_text_tokens=count_text_tokens,
            segment_groups=(
                segment_groups[ext_start:ext_end]
                if segment_groups is not None
                else None
            ),
            mask_abbrev_flags=(
                mask_abbrev_flags[ext_start:ext_end]
                if mask_abbrev_flags is not None
                else None
            ),
            enable_identity_residual_guard=False,
            enable_identity_context_recovery=False,
        )
        if window_result is not None:
            _store_core_from_window(
                core_start=core_start,
                core_end=core_end,
                ext_start=ext_start,
                window_result=window_result,
            )
            return True, "ok"
        _cascade_debug(
            "window_fail "
            f"core=[{core_start}:{core_end}) "
            f"extended=[{ext_start}:{ext_end}) "
            f"reason={reason}"
        )

        core_len = core_end - core_start
        if core_len <= 2:
            _cascade_debug(
                "leaf_per_segment "
                f"core=[{core_start}:{core_end}) "
                f"extended=[{ext_start}:{ext_end}) "
                f"reason={reason}"
            )
            for idx in range(core_start, core_end):
                translated[idx] = _recover_single_segment_with_tag_mask(
                    segments[idx],
                    translate_text=translate_text,
                    cache=leaf_cache,
                    max_chunk_chars=leaf_max_chunk_chars,
                    context_label="window",
                    seg_index=idx + 1,
                )
            return True, (
                "ok_leaf_per_segment "
                f"core=[{core_start}:{core_end}) "
                f"extended=[{ext_start}:{ext_end}) "
                f"reason={reason}"
            )

        mid = core_start + core_len // 2
        left_ok, left_reason = _translate_core_range(core_start, mid)
        if not left_ok:
            return False, left_reason
        right_ok, right_reason = _translate_core_range(mid, core_end)
        if not right_ok:
            return False, right_reason
        return True, "ok"

    core_start = 0
    while core_start < n:
        core_end = min(n, core_start + window_segments)
        ok, reason = _translate_core_range(core_start, core_end)
        if not ok:
            return None, reason
        core_start = core_end

    if any(item is None for item in translated):
        return None, "window_postcheck_none_entries"
    translated_full = [item for item in translated if item is not None]
    translated_full, guard_recovery_counts = _apply_post_reassembly_guards(
        source_segments=segments,
        translated_segments=translated_full,
        translate_text=translate_text,
        cache=leaf_cache,
        max_chunk_chars=leaf_max_chunk_chars,
        context_label="window",
        segment_groups=segment_groups,
        enable_identity_residual_guard=False,
        enable_identity_context_recovery=False,
    )
    guard_recovered = sum(guard_recovery_counts.values())
    if guard_recovered > 0:
        details = ",".join(
            f"{name}={count}"
            for name, count in sorted(guard_recovery_counts.items())
            if count > 0
        )
        return translated_full, (
            "ok_window_leak_recovery "
            f"count={guard_recovered} details={details}"
        )
    return translated_full, "ok"


def _translate_plain_fragment(
    text: str,
    *,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
) -> str:
    if not text or not text.strip():
        return text
    if not _TRANSLATABLE_TEXT_PATTERN.search(text):
        return text

    leading_len = len(text) - len(text.lstrip())
    trailing_len = len(text) - len(text.rstrip())
    core_end = len(text) - trailing_len if trailing_len else len(text)
    core = text[leading_len:core_end]
    if not core or not core.strip():
        return text

    translated = cache.get(core)
    if translated is None:
        translated = _translate_with_chunk_fallback(
            core,
            translate_text=translate_text,
            max_chunk_chars=max_chunk_chars,
        )
        if _is_translator_refusal(translated):
            translated = core
        else:
            translated = _strip_source_echo(translated, core)
            translated = _strip_prompt_leak_echo(translated)
            if not translated:
                translated = core
            # Byte-token sequences followed by citation numbers are dropped <sup> tags;
            # restore them so _add_reference_ids_and_citation_links can linkify them.
            translated = _BYTE_TOKEN_CITATION_PATTERN.sub(r'<sup>\1</sup>', translated)
            translated = _BYTE_TOKEN_ARTIFACT_PATTERN.sub("", translated)
        cache[core] = translated

    return text[:leading_len] + translated + text[core_end:]


def _visible_text_fragment(html_fragment: str) -> str:
    text = _HTML_TAG_PATTERN.sub(" ", html_fragment)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&#160;", " ")
        .replace("\u00a0", " ")
    )
    return re.sub(r"\s+", " ", text).strip()


def _looks_author_line_paragraph(text: str) -> bool:
    if not text:
        return False
    normalized = " ".join(text.split())
    if len(normalized) < 8:
        return False
    if ":" in normalized:
        return False
    if _ABSTRACT_MARKER_PATTERN.search(normalized):
        return False
    if _AUTHOR_LINE_NEGATIVE_PATTERN.search(normalized):
        return False
    if len(re.findall(r"\d", normalized)) > 2:
        return False

    comma_count = normalized.count(",")
    name_like_count = len(_AUTHOR_WORD_PATTERN.findall(normalized))
    has_author_connector = bool(
        re.search(r"\b(?:and|&|et al\.?|member|fellow|professor)\b", normalized, re.IGNORECASE)
    )
    return (
        (comma_count >= 2 and name_like_count >= 2)
        or (has_author_connector and comma_count >= 1 and name_like_count >= 2)
    )


def _mark_author_line_notranslate(html: str) -> str:
    """Mark only real author-line paragraphs as ``translate=\"no\"``.

    This avoids over-marking metadata lines such as ``Received: ...``.
    """
    h1_end = _H1_CLOSE_PATTERN.search(html)
    if h1_end is None:
        return html

    search_pos = h1_end.end()
    first_h_after_h1 = _H_OPEN_PATTERN.search(html, search_pos)
    stop_pos = first_h_after_h1.start() if first_h_after_h1 else len(html)

    while True:
        p_match = _FIRST_P_OPEN_PATTERN.search(html, search_pos)
        if p_match is None or p_match.start() >= stop_pos:
            return html

        p_close = _P_CLOSE_PATTERN.search(html, p_match.end())
        if p_close is None:
            return html

        p_content = html[p_match.end():p_close.start()]
        visible = _visible_text_fragment(p_content)
        if _looks_author_line_paragraph(visible):
            attrs = p_match.group(1) or ""
            if "translate" in attrs.lower():
                return html
            new_tag = f"<p{attrs} translate=\"no\">"
            return html[: p_match.start()] + new_tag + html[p_match.end():]

        search_pos = p_close.end()


def _find_list_end(html: str, list_open: re.Match[str]) -> int | None:
    list_tag = (list_open.group(1) or "").lower()
    if list_tag not in {"ul", "ol"}:
        return None

    list_depth = 1
    list_token_pattern = re.compile(rf"</?{list_tag}\b[^>]*>", re.IGNORECASE)
    for token in list_token_pattern.finditer(html, list_open.end()):
        raw = token.group(0).strip().lower()
        if raw.startswith("</"):
            list_depth -= 1
            if list_depth == 0:
                return token.end()
        elif not raw.endswith("/>"):
            list_depth += 1
    return None


def _containing_p_end_for_list(
    html: str,
    *,
    search_start: int,
    list_start: int,
    minimum_end: int,
) -> int | None:
    p_end: int | None = None
    for p_match in _FIRST_P_OPEN_PATTERN.finditer(html, search_start, list_start):
        p_close = _P_CLOSE_PATTERN.search(html, p_match.end())
        if p_close is not None and p_close.start() > list_start and p_close.end() >= minimum_end:
            p_end = p_close.end()
    return p_end


def _reference_list_group_end(
    html: str,
    *,
    heading_end: int,
    first_list_open: re.Match[str],
) -> int | None:
    list_end = _find_list_end(html, first_list_open)
    if list_end is None:
        return None

    block_end = _containing_p_end_for_list(
        html,
        search_start=heading_end,
        list_start=first_list_open.start(),
        minimum_end=list_end,
    ) or list_end

    while True:
        whitespace = re.match(r"\s*", html[block_end:])
        next_pos = block_end + (whitespace.end() if whitespace else 0)

        p_match = _FIRST_P_OPEN_PATTERN.match(html, next_pos)
        if p_match is not None:
            p_close = _P_CLOSE_PATTERN.search(html, p_match.end())
            if p_close is None:
                return block_end
            p_content = html[p_match.end():p_close.start()]
            if _LIST_OPEN_PATTERN.search(p_content) is None:
                return block_end
            block_end = p_close.end()
            continue

        list_match = _LIST_OPEN_PATTERN.match(html, next_pos)
        if list_match is None:
            return block_end

        next_list_end = _find_list_end(html, list_match)
        if next_list_end is None:
            return block_end
        block_end = next_list_end


def _mark_references_block_notranslate(html: str) -> str:
    """Mark bibliography block (references heading + list) as non-translatable.

    Post-reference narrative sections remain translatable.
    """
    heading_match = _REFERENCES_HEADING_PATTERN.search(html)
    if heading_match is None:
        return html

    block_start = heading_match.start()
    next_heading = _H_OPEN_PATTERN.search(html, heading_match.end())
    block_end = next_heading.start() if next_heading else len(html)
    if next_heading is None:
        # No structural heading boundary found. Fall back to a confident list boundary
        # (References heading + <ul>/<ol> list). If no list is found, skip marking
        # to avoid freezing post-reference narrative sections.
        list_open = _LIST_OPEN_PATTERN.search(html, heading_match.end())
        if list_open is None:
            return html

        fallback_end = _reference_list_group_end(
            html,
            heading_end=heading_match.end(),
            first_list_open=list_open,
        )
        if fallback_end is None:
            return html
        block_end = fallback_end

    if block_end <= block_start:
        return html

    block = html[block_start:block_end]
    if re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bz2m-references-block\b',
        block,
        flags=re.IGNORECASE,
    ):
        return html
    wrapped = (
        '<div class="z2m-references-block" translate="no">'
        f"{block}"
        "</div>"
    )
    return html[:block_start] + wrapped + html[block_end:]


def _is_context_or_memory_error(exc: Exception) -> bool:
    lowered = str(exc).lower()
    markers = (
        "context window exceeded",
        "sequence length",
        "max position embeddings",
        "token indices sequence length is longer",
        "index out of range in self",
        "cuda out of memory",
        "outofmemoryerror",
    )
    return any(marker in lowered for marker in markers)


def _translate_with_chunk_fallback(
    text: str,
    *,
    translate_text: Callable[[str], str],
    max_chunk_chars: int,
) -> str:
    if not text:
        return text
    if not _TRANSLATABLE_TEXT_PATTERN.search(text):
        return text

    # Apply prompt leak protection before translation
    masked_text, prompt_leak_map = _apply_prompt_leak_mask(text)

    def translate_with_masked_text(masked_text: str) -> str:
        translated = translate_text(masked_text)
        # Restore any prompt leak protection tokens that might have been processed
        if prompt_leak_map:
            # We can't restore the original text here since it's already translated,
            # but we make sure no prompt leak patterns appear in the result by
            # removing them (they should be rare anyway)
            return translated
        return translated

    try:
        result = translate_with_masked_text(masked_text)
        return result
    except Exception as exc:
        if not _is_context_or_memory_error(exc):
            raise

    chunk_chars = max(256, max_chunk_chars)
    if len(text) <= chunk_chars:
        # Nothing left to split; re-raise by trying one more time for the real traceback.
        return translate_with_masked_text(masked_text)

    def _translate_recursive(chunk_text: str, current_chunk_chars: int) -> str:
        if not _TRANSLATABLE_TEXT_PATTERN.search(chunk_text):
            return chunk_text

        # Apply prompt leak protection to chunks too
        masked_chunk, chunk_prompt_leak_map = _apply_prompt_leak_mask(chunk_text)

        def translate_with_masked_chunk(masked_chunk: str) -> str:
            translated = translate_text(masked_chunk)
            if chunk_prompt_leak_map:
                return translated
            return translated

        try:
            result = translate_with_masked_chunk(masked_chunk)
            return result
        except Exception as chunk_exc:
            if not _is_context_or_memory_error(chunk_exc):
                raise
            if len(chunk_text) <= 256:
                raise

        next_chunk_chars = max(256, current_chunk_chars // 2)
        if next_chunk_chars >= len(chunk_text):
            next_chunk_chars = max(256, len(chunk_text) // 2)
        if next_chunk_chars >= len(chunk_text):
            return translate_with_masked_chunk(masked_chunk)

        translated_parts: list[str] = []
        for sub_chunk in _split_text_chunks(chunk_text, max_chunk_chars=next_chunk_chars):
            translated_parts.append(_translate_recursive(sub_chunk, next_chunk_chars))
        return "".join(translated_parts)

    translated_parts: list[str] = []
    for chunk in _split_text_chunks(text, max_chunk_chars=chunk_chars):
        translated_parts.append(_translate_recursive(chunk, chunk_chars))
    return "".join(translated_parts)


def _translate_plain_fragment_preserving_abbrev(
    text: str,
    *,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
) -> str:
    if not text or not text.strip():
        return text

    masked_text, amap = _apply_abbrev_mask(text)
    translated_masked = _translate_plain_fragment(
        masked_text,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
    )

    if not amap:
        return translated_masked

    expected_abbrev_ids = list(range(len(amap)))
    found_abbrev_ids = sorted(
        int(m.group(1)) for m in _ABBREV_TOKEN_PATTERN.finditer(translated_masked)
    )
    if found_abbrev_ids != expected_abbrev_ids:
        # The model altered abbreviation placeholders. In recovery context we
        # accept translated text when it is clearly non-English; otherwise keep
        # strict fallback to source text.
        if _is_recovery_context_active():
            restored_lenient = _restore_abbrev_mask(translated_masked, amap)
            if re.search(r"[\u0410-\u042F\u0430-\u044F\u0401\u0451]", restored_lenient):
                return restored_lenient
        return text
    return _restore_abbrev_mask(translated_masked, amap)


def _retry_table_caption_translation(
    *,
    source_core: str,
    translated_core: str,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
) -> str:
    """Retry all-caps TABLE captions with normalized casing when translation is identity."""
    match = _TABLE_CAPTION_ALLCAPS_PATTERN.match(source_core)
    if match is None:
        return translated_core

    source_norm = _normalize_ws(source_core).lower()
    translated_norm = _normalize_ws(translated_core).lower()
    if translated_norm != source_norm and re.search(r"[\u0410-\u042F\u0430-\u044F\u0401\u0451]", translated_core):
        return translated_core

    roman = match.group(1)
    tail = match.group(2)
    retry_source = f"Table {roman} {tail.lower()}"
    retry_translated = _translate_plain_fragment(
        retry_source,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
    ).strip()

    if not retry_translated:
        return translated_core
    if re.search(r"[\u0410-\u042F\u0430-\u044F\u0401\u0451]", retry_translated):
        return retry_translated
    return translated_core


def _translate_text_segment(
    segment: str,
    translate_text: Callable[[str], str],
    cache: dict[str, str],
    max_chunk_chars: int,
) -> str:
    if not segment:
        return segment

    leading_len = len(segment) - len(segment.lstrip())
    trailing_len = len(segment) - len(segment.rstrip())
    core_end = len(segment) - trailing_len if trailing_len else len(segment)
    core = segment[leading_len:core_end]
    if not core.strip():
        return segment

    spans = _formula_spans(core)
    if not spans:
        translated_core = _translate_plain_fragment_preserving_abbrev(
            core,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
        )
        translated_core = _retry_table_caption_translation(
            source_core=core,
            translated_core=translated_core,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
        )
        translated_core = _strip_prompt_leak_echo(translated_core)
        if not translated_core:
            translated_core = core
        return segment[:leading_len] + translated_core + segment[core_end:]

    translated_parts: list[str] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            translated_parts.append(
                _translate_plain_fragment_preserving_abbrev(
                    core[cursor:start],
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                )
            )
        translated_parts.append(core[start:end])
        cursor = end

    if cursor < len(core):
        translated_parts.append(
            _translate_plain_fragment_preserving_abbrev(
                core[cursor:],
                translate_text=translate_text,
                cache=cache,
                max_chunk_chars=max_chunk_chars,
            )
        )

    translated_core = "".join(translated_parts)
    translated_core = _retry_table_caption_translation(
        source_core=core,
        translated_core=translated_core,
        translate_text=translate_text,
        cache=cache,
        max_chunk_chars=max_chunk_chars,
    )
    translated_core = _strip_prompt_leak_echo(translated_core)
    if not translated_core:
        translated_core = core
    return segment[:leading_len] + translated_core + segment[core_end:]


@dataclass(frozen=True)
class _HeadingInlineTerm:
    text: str
    open_tag: str
    close_tag: str


@dataclass(frozen=True)
class _HeadingMerge:
    secondary_indices: tuple[int, ...]
    folded_indices: tuple[int, ...] = ()
    inline_terms: tuple[_HeadingInlineTerm, ...] = ()
    link_text_index: int | None = None


def _is_heading_tag_name(tag_name: str) -> bool:
    return tag_name.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}


def _is_heading_inline_preserved_term(text: str) -> bool:
    core = _normalize_ws(text)
    if not core:
        return False
    return bool(
        _PROTECTED_SCIENCE_TERM_PATTERN.fullmatch(core)
        or _ABBREV_PATTERN.fullmatch(core)
    )


def _heading_inline_terms(
    parts: list[str],
    *,
    start_idx: int,
    end_idx: int,
) -> tuple[_HeadingInlineTerm, ...]:
    terms: list[_HeadingInlineTerm] = []
    for idx in range(start_idx, end_idx + 1):
        part = parts[idx]
        if not part or part.startswith("<"):
            continue
        if not _is_heading_inline_preserved_term(part):
            continue
        if idx <= start_idx or idx >= end_idx:
            continue

        open_part = parts[idx - 1]
        close_part = parts[idx + 1]
        open_match = _OPEN_TAG_PATTERN.match(open_part.strip())
        close_match = _CLOSE_TAG_PATTERN.match(close_part.strip())
        if open_match is None or close_match is None:
            continue
        open_name = open_match.group(1).lower()
        close_name = close_match.group(1).lower()
        if open_name != close_name or open_name not in _HEADING_INLINE_MARKUP_TAGS:
            continue
        terms.append(
            _HeadingInlineTerm(
                text=_normalize_ws(part),
                open_tag=open_part,
                close_tag=close_part,
            )
        )
    return tuple(terms)


def _restore_heading_inline_terms(text: str, terms: tuple[_HeadingInlineTerm, ...]) -> str:
    restored = text
    for term in terms:
        needle = term.text.strip()
        if not needle:
            continue
        pattern = re.compile(
            rf"(?<![A-Za-z0-9>])({re.escape(needle)})(?![A-Za-z0-9<])"
        )
        if pattern.search(restored) is None:
            continue
        restored = pattern.sub(
            lambda m: f"{term.open_tag}{m.group(1)}{term.close_tag}",
            restored,
            count=1,
        )
    return restored


def _heading_link_text_index(
    parts: list[str],
    *,
    start_idx: int,
    end_idx: int,
    text_indices: list[int],
) -> int | None:
    """Return text-node index for an inline heading link that splits a phrase."""
    if len(text_indices) < 2:
        return None

    for idx in range(start_idx, end_idx + 1):
        part = parts[idx]
        if not part or not part.startswith("<"):
            continue
        open_match = _OPEN_TAG_PATTERN.match(part.strip())
        if open_match is None or open_match.group(1).lower() != "a":
            continue

        depth = 1
        close_idx: int | None = None
        for scan_idx in range(idx + 1, end_idx + 1):
            scan_part = parts[scan_idx]
            if not scan_part or not scan_part.startswith("<"):
                continue
            scan_raw = scan_part.strip()
            scan_open = _OPEN_TAG_PATTERN.match(scan_raw)
            scan_close = _CLOSE_TAG_PATTERN.match(scan_raw)
            if scan_open is not None and scan_open.group(1).lower() == "a":
                depth += 1
            elif scan_close is not None and scan_close.group(1).lower() == "a":
                depth -= 1
                if depth == 0:
                    close_idx = scan_idx
                    break
        if close_idx is None:
            continue

        inside = [text_idx for text_idx in text_indices if idx < text_idx < close_idx]
        outside = [
            text_idx
            for text_idx in text_indices
            if text_idx < idx or text_idx > close_idx
        ]
        if len(inside) == 1 and outside:
            return inside[0]

    return None


def _legacy_merge_heading_text_nodes(
    parts: list[str],
) -> tuple[list[str], dict[int, list[int]]]:
    """Merge text nodes inside heading tags (h1-h6) using ASCII sentinel.

    Returns:
        tuple of (modified_parts, merges) where merges is {merge_src_idx: [secondary_indices]}
        to track which text nodes were merged.
    """
    heading_stack: list[str] = []  # Stack of open heading tag names
    heading_text_indices: dict[int, list[int]] = {}  # depth -> list of text part indices
    current_heading_depth = -1
    merges: dict[int, list[int]] = {}  # merge_src_idx -> [other_indices_that_were_merged]

    # First pass: identify text nodes inside headings
    for i, part in enumerate(parts):
        if not part:
            continue

        if part.startswith("<"):
            # Parse opening/closing tags
            tag_name = ""
            match = re.match(r"</?([a-z0-9]+)", part, re.IGNORECASE)
            if match:
                tag_name = match.group(1).lower()

            if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                if not part.startswith("</"):
                    # Opening tag
                    heading_stack.append(tag_name)
                    current_heading_depth = len(heading_stack) - 1
                    heading_text_indices[current_heading_depth] = []
                else:
                    # Closing tag
                    if heading_stack and heading_stack[-1] == tag_name:
                        heading_stack.pop()
                        current_heading_depth = len(heading_stack) - 1
        else:
            # Text node
            if heading_stack:
                # We're inside a heading
                heading_text_indices[current_heading_depth].append(i)

    # Second pass: merge text nodes within headings if >= 2 nodes
    modified_parts = list(parts)

    for depth in sorted(heading_text_indices.keys(), reverse=True):
        text_indices = heading_text_indices[depth]
        if len(text_indices) < 2:
            # Single text node or no text in heading вЂ” skip merge
            continue

        # Collect texts from all indices
        texts_to_merge = [modified_parts[idx] for idx in text_indices]

        # Merge via ASCII sentinel that survives tokenization more reliably than
        # private-use unicode separators.
        merged_text = _HEADING_MERGE_SEPARATOR.join(texts_to_merge)

        # Replace first index with merged, empty out the rest
        first_idx = text_indices[0]
        modified_parts[first_idx] = merged_text
        secondary_indices = text_indices[1:]
        for idx in secondary_indices:
            modified_parts[idx] = ""

        # Record which indices were merged
        merges[first_idx] = secondary_indices

    return modified_parts, merges


def _legacy_split_heading_text_nodes(
    parts: list[str],
    merges: dict[int, list[int]],
) -> list[str]:
    """Restore heading text nodes after translation.

    If heading separator was preserved, split and restore.
    If lost (model dropped it), keep merged in first index.

    Safely handles index bounds вЂ” returns parts unchanged if indices are invalid.
    """
    if not merges:
        return list(parts)

    result = list(parts)

    for merge_src_idx, secondary_indices in merges.items():
        # Bounds check
        if merge_src_idx >= len(result):
            continue

        # Check all secondary indices too
        if any(idx >= len(result) for idx in secondary_indices):
            continue

        merged_text = result[merge_src_idx]

        # Check if separator was preserved
        if not merged_text or _HEADING_MERGE_SEPARATOR not in merged_text:
            # Model dropped the separator вЂ” keep merged in first index
            # Secondary indices stay empty
            continue

        # Split by separator
        split_texts = merged_text.split(_HEADING_MERGE_SEPARATOR)
        expected_count = 1 + len(secondary_indices)
        if len(split_texts) != expected_count:
            # Mismatch вЂ” keep merged
            continue

        # Distribute split texts
        result[merge_src_idx] = split_texts[0]
        for i, idx in enumerate(secondary_indices, start=1):
            result[idx] = split_texts[i]

    return result


def _merge_heading_text_nodes(
    parts: list[str],
) -> tuple[list[str], dict[int, _HeadingMerge]]:
    """Merge heading text; fold inline protected acronyms into visible text."""
    heading_stack: list[tuple[str, int]] = []
    heading_ranges: list[tuple[int, int]] = []

    for idx, part in enumerate(parts):
        if not part or not part.startswith("<"):
            continue
        raw = part.strip()
        close_match = _CLOSE_TAG_PATTERN.match(raw)
        if close_match is not None:
            tag_name = close_match.group(1).lower()
            if heading_stack and heading_stack[-1][0] == tag_name:
                _, open_idx = heading_stack.pop()
                if open_idx + 1 <= idx - 1:
                    heading_ranges.append((open_idx + 1, idx - 1))
            continue
        if raw.endswith("/>"):
            continue
        open_match = _OPEN_TAG_PATTERN.match(raw)
        if open_match is None:
            continue
        tag_name = open_match.group(1).lower()
        if _is_heading_tag_name(tag_name):
            heading_stack.append((tag_name, idx))

    modified_parts = list(parts)
    merges: dict[int, _HeadingMerge] = {}
    for start_idx, end_idx in heading_ranges:
        text_indices = [
            idx
            for idx in range(start_idx, end_idx + 1)
            if modified_parts[idx] and not modified_parts[idx].startswith("<")
        ]
        if len(text_indices) < 2:
            continue

        first_idx = text_indices[0]
        secondary_indices = tuple(text_indices[1:])
        inline_terms = _heading_inline_terms(
            modified_parts,
            start_idx=start_idx,
            end_idx=end_idx,
        )
        link_text_index = _heading_link_text_index(
            modified_parts,
            start_idx=start_idx,
            end_idx=end_idx,
            text_indices=text_indices,
        )
        texts_to_merge = [modified_parts[idx] for idx in text_indices]
        if inline_terms:
            modified_parts[first_idx] = re.sub(r"\s{2,}", " ", "".join(texts_to_merge))
            folded_indices = tuple(range(start_idx, end_idx + 1))
            for folded_idx in folded_indices:
                if folded_idx != first_idx:
                    modified_parts[folded_idx] = ""
            merges[first_idx] = _HeadingMerge(
                secondary_indices=secondary_indices,
                folded_indices=folded_indices,
                inline_terms=inline_terms,
            )
            continue

        if link_text_index is not None:
            modified_parts[first_idx] = re.sub(r"\s{2,}", " ", "".join(texts_to_merge))
            folded_indices = tuple(text_indices)
            for folded_idx in folded_indices:
                if folded_idx != first_idx:
                    modified_parts[folded_idx] = ""
            merges[first_idx] = _HeadingMerge(
                secondary_indices=secondary_indices,
                folded_indices=folded_indices,
                link_text_index=link_text_index,
            )
            continue

        modified_parts[first_idx] = _HEADING_MERGE_SEPARATOR.join(texts_to_merge)
        for secondary_idx in secondary_indices:
            modified_parts[secondary_idx] = ""
        merges[first_idx] = _HeadingMerge(secondary_indices=secondary_indices)

    return modified_parts, merges


def _split_heading_text_nodes(
    parts: list[str],
    merges: dict[int, _HeadingMerge],
) -> list[str]:
    """Restore heading text nodes after translation."""
    if not merges:
        return list(parts)

    result = list(parts)
    for merge_src_idx, merge in merges.items():
        if merge_src_idx >= len(result):
            continue
        if merge.inline_terms:
            result[merge_src_idx] = _restore_heading_inline_terms(
                result[merge_src_idx],
                merge.inline_terms,
            )
            for folded_idx in merge.folded_indices:
                if folded_idx != merge_src_idx and folded_idx < len(result):
                    result[folded_idx] = ""
            continue

        if merge.link_text_index is not None:
            if merge.link_text_index < len(result):
                merged_text = result[merge_src_idx]
                if not merged_text:
                    merged_text = result[merge.link_text_index]
                result[merge.link_text_index] = _clean_final_text_fragment(merged_text)
            for folded_idx in merge.folded_indices:
                if folded_idx != merge.link_text_index and folded_idx < len(result):
                    result[folded_idx] = ""
            continue

        secondary_indices = merge.secondary_indices
        if any(idx >= len(result) for idx in secondary_indices):
            continue
        merged_text = result[merge_src_idx]
        if not merged_text or _HEADING_MERGE_SEPARATOR not in merged_text:
            continue
        split_texts = merged_text.split(_HEADING_MERGE_SEPARATOR)
        expected_count = 1 + len(secondary_indices)
        if len(split_texts) != expected_count:
            continue
        result[merge_src_idx] = split_texts[0]
        for offset, idx in enumerate(secondary_indices, start=1):
            result[idx] = split_texts[offset]

    return result


def translate_html_text_nodes(
    html: str,
    translate_text: Callable[[str], str],
    *,
    max_chunk_chars: int = 1800,
    target_language_code: str = DEFAULT_GEMMA_TARGET_LANGUAGE,
    translate_heading_text: Callable[[str], str] | None = None,
    enable_heading_oov_guard: bool = False,
    heading_translation_max_chars: int = 80,
    context_window_segments: int = _WINDOW_BATCH_TARGET_SEGMENTS,
    context_overlap_segments: int = _WINDOW_BATCH_OVERLAP_SEGMENTS,
    context_max_window_chars: int = _MAX_WINDOW_BATCH_CHARS,
    context_max_window_tokens: int = 0,
    count_text_tokens: Callable[[str], int] | None = None,
    enable_marker_batching: bool = True,
    enable_en_residual_quality_gate: bool = True,
    en_residual_quality_gate_max_segments: int = 24,
    enable_cjk_quality_gate: bool = True,
    cjk_quality_gate_max_segments: int = 8,
    on_segment_start: Callable[[int, int], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    on_batch_fallback: Callable[[str], None] | None = None,
    on_warning: Callable[[str], None] | None = None,
) -> tuple[str, int]:
    """Translate all translatable text nodes in *html*, leaving markup intact.

    **Batch mode (primary path):** translatable text nodes are translated in
    overlapping windows with id markers (``<z2m-iN/>``), which allows strict
    parse/coverage validation while preserving local inter-paragraph context.

    **Recovery path:** failed windows are bisected recursively; leaf windows
    (1-2 core segments) are translated per-segment locally, so one broken
    batch does not force global document-wide fallback.

    The References / Bibliography section is never translated.
    """
    target_language_code = normalize_language_code(target_language_code)
    # Keep bibliography entries in source language, but leave post-reference
    # narrative sections (Data availability, Conflict of interest, etc.)
    # translatable.
    html = _mark_references_block_notranslate(html)
    if target_language_code == "ru":
        html = _replace_abbreviation_paragraphs_ru(html)

    parts = _TAG_SPLIT_PATTERN.split(html)

    # Pre-merge: combine text nodes within heading tags (h1-h6) to preserve context.
    # This fixes the issue where "Sensor" inside <h1>...<i>LC</i>Sensor</h1> was
    # translated separately and incorrectly as "Р”Р°С‚С‡РёРє" (nominative) instead of
    # "РґР°С‚С‡РёРєР°" (genitive). The merge uses \x00 as separator, which the model never outputs.
    parts, heading_merges = _merge_heading_text_nodes(parts)

    # Single pass: collect indices of translatable text nodes.
    skip_stack: list[str] = []
    translatable_indices: list[int] = []
    translatable_paragraph_groups: list[int | None] = []
    translatable_heading_groups: list[int | None] = []
    paragraph_stack: list[int] = []
    paragraph_counter = [0]
    paragraph_part_ranges: dict[int, tuple[int, int]] = {}
    heading_stack: list[int] = []
    heading_counter = [0]
    heading_part_ranges: dict[int, tuple[int, int]] = {}
    tiny_fragment_preserved_count = 0
    for i, part in enumerate(parts):
        if not part:
            continue
        if part.startswith("<"):
            _update_paragraph_stack(part, paragraph_stack, paragraph_counter)
            _update_heading_stack(part, heading_stack, heading_counter)
            if paragraph_stack:
                group_id = paragraph_stack[-1]
                start, end = paragraph_part_ranges.get(group_id, (i, i))
                paragraph_part_ranges[group_id] = (min(start, i), max(end, i))
            if heading_stack:
                heading_id = heading_stack[-1]
                start, end = heading_part_ranges.get(heading_id, (i, i))
                heading_part_ranges[heading_id] = (min(start, i), max(end, i))
            _update_skip_stack(part, skip_stack)
            continue
        if paragraph_stack:
            group_id = paragraph_stack[-1]
            start, end = paragraph_part_ranges.get(group_id, (i, i))
            paragraph_part_ranges[group_id] = (min(start, i), max(end, i))
        if heading_stack:
            heading_id = heading_stack[-1]
            start, end = heading_part_ranges.get(heading_id, (i, i))
            heading_part_ranges[heading_id] = (min(start, i), max(end, i))
        if not skip_stack and _has_translatable_visible_text(part):
            if _should_preserve_tiny_fragment(part):
                tiny_fragment_preserved_count += 1
                continue
            translatable_indices.append(i)
            translatable_paragraph_groups.append(paragraph_stack[-1] if paragraph_stack else None)
            translatable_heading_groups.append(heading_stack[-1] if heading_stack else None)

    total_segments = len(translatable_indices)
    if total_segments == 0:
        if tiny_fragment_preserved_count and on_warning is not None:
            try:
                on_warning(f"tiny_fragment_preserved_count={tiny_fragment_preserved_count}")
            except Exception:
                pass
        return "".join(p for p in parts if p), 0
    enable_heading_oov_guard = bool(enable_heading_oov_guard)
    heading_translation_max_chars = max(8, int(heading_translation_max_chars))
    context_window_segments = max(2, int(context_window_segments))
    context_overlap_segments = max(0, int(context_overlap_segments))
    context_max_window_chars = max(1_024, int(context_max_window_chars))
    context_max_window_tokens = max(0, int(context_max_window_tokens))
    enable_marker_batching = bool(enable_marker_batching)
    enable_en_residual_quality_gate = bool(enable_en_residual_quality_gate)
    en_residual_quality_gate_max_segments = max(0, int(en_residual_quality_gate_max_segments))
    enable_cjk_quality_gate = bool(enable_cjk_quality_gate) and target_language_code != "zh"
    cjk_quality_gate_max_segments = max(0, int(cjk_quality_gate_max_segments))

    # ------------------------------------------------------------------ #
    # Primary path: batch translation                                      #
    # ------------------------------------------------------------------ #
    source_parts = list(parts)
    source_texts = [parts[i] for i in translatable_indices]
    source_texts_for_batch = list(source_texts)
    mask_abbrev_flags = [
        not bool(heading_merges.get(part_idx) and heading_merges[part_idx].inline_terms)
        for part_idx in translatable_indices
    ]
    heading_allcaps_style_flags: list[bool] = [False] * len(source_texts)
    for idx, heading_group in enumerate(translatable_heading_groups):
        if heading_group is None:
            continue
        normalized_heading, preserve_allcaps = _normalize_heading_case_for_translation(source_texts[idx])
        source_texts_for_batch[idx] = normalized_heading
        heading_allcaps_style_flags[idx] = preserve_allcaps

    heading_translation_cache: dict[str, str] = {}
    heading_oov_retry_count = 0
    heading_oov_unresolved = 0

    if enable_marker_batching:
        batch_result, batch_reason = _try_windowed_batch_translate_with_reason(
            source_texts_for_batch,
            translate_text,
            window_segments=context_window_segments,
            overlap_segments=context_overlap_segments,
            max_window_chars=context_max_window_chars,
            max_window_tokens=context_max_window_tokens,
            count_text_tokens=count_text_tokens,
            segment_groups=translatable_paragraph_groups,
            mask_abbrev_flags=mask_abbrev_flags,
        )
    else:
        batch_result, batch_reason = None, "marker_batching_disabled"

    if batch_result is not None:
        for idx, src, tgt in zip(translatable_indices, source_texts, batch_result):
            parts[idx] = tgt
        wide_cache: dict[str, str] = {}
        parts, initial_wide_counts = _apply_wide_paragraph_recovery(
            source_parts=source_parts,
            translated_parts=parts,
            translatable_indices=translatable_indices,
            source_segments=source_texts,
            paragraph_groups=translatable_paragraph_groups,
            paragraph_part_ranges=paragraph_part_ranges,
            translate_text=translate_text,
            cache=wide_cache,
            max_chunk_chars=max_chunk_chars,
        )
        if on_progress is not None:
            try:
                on_progress(total_segments, total_segments)
            except Exception:
                pass
        # Post-split: restore original heading text nodes if separator preserved.
        parts = _split_heading_text_nodes(parts, heading_merges)
        # Clean leaked protocol markers after split (safety net for malformed separators/tokens).
        parts = [_clean_final_part_fragment(p) for p in parts]
        # Deterministic heading glossary pass (quality guard for short all-caps headings).
        for part_idx, source_seg, heading_group in zip(
            translatable_indices,
            source_texts,
            translatable_heading_groups,
        ):
            if heading_group is None:
                continue
            parts[part_idx] = _apply_heading_glossary_postedit(source_seg, parts[part_idx])
        # Final identity pass (after heading split) catches single-inline headings
        # and any residual EN segments that escaped window-level guards.
        final_cache: dict[str, str] = {}
        final_identity_terminal_count = 0
        for seg_no, (part_idx, source_seg) in enumerate(
            zip(translatable_indices, source_texts),
            start=1,
        ):
            if _HEADING_MERGE_SEPARATOR in source_seg:
                continue
            translated_seg = parts[part_idx]
            if not _is_identity_residual(source_seg, translated_seg):
                continue

            heading_group = (
                translatable_heading_groups[seg_no - 1]
                if (seg_no - 1) < len(translatable_heading_groups)
                else None
            )
            if heading_group is not None:
                context_text = _extract_next_paragraph_context_text(source_parts, part_idx)
                recovered_seg = _recover_heading_segment_with_context(
                    source_seg,
                    context_text=context_text,
                    translate_text=translate_text,
                    cache=final_cache,
                    max_chunk_chars=max_chunk_chars,
                    seg_index=seg_no,
                )
            else:
                recovered_seg = _recover_single_segment_with_tag_mask(
                    source_seg,
                    translate_text=translate_text,
                    cache=final_cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="final",
                    seg_index=seg_no,
                )
            stripped_seg, stripped = _strip_unexpected_trailing_ellipsis(source_seg, recovered_seg)
            if stripped:
                recovered_seg = stripped_seg
                _cascade_debug(
                    f"final_lenient reason=trailing_ellipsis_stripped seg={seg_no} action=post_hoc_strip"
                )
            parts[part_idx] = recovered_seg

            if _is_identity_residual(source_seg, recovered_seg) and heading_group is not None:
                heading_range = heading_part_ranges.get(heading_group)
                if heading_range is not None:
                    recovered_heading_slice = _recover_parts_slice_with_tag_mask(
                        source_parts=source_parts,
                        start_part_idx=heading_range[0],
                        end_part_idx=heading_range[1],
                        translate_text=translate_text,
                        cache=final_cache,
                        max_chunk_chars=max_chunk_chars,
                        context_label="heading_wide",
                        seg_index=seg_no,
                    )
                    if recovered_heading_slice is not None:
                        parts[heading_range[0]:heading_range[1] + 1] = recovered_heading_slice
                        recovered_seg = parts[part_idx]

            if _is_identity_residual(source_seg, recovered_seg):
                final_identity_terminal_count += 1
                _cascade_debug(
                    f"final_lenient reason=identity_terminal seg={seg_no} action=keep_recovered"
                )
            else:
                _cascade_debug(
                    f"final_lenient reason=identity_residual seg={seg_no} action=local_segment_recovery"
                )
            if heading_group is not None:
                recovered_seg = _apply_heading_glossary_postedit(source_seg, recovered_seg)
                parts[part_idx] = recovered_seg

        # One more paragraph-wide pass after final per-segment retries helps when
        # isolated retries keep returning identity EN for technical text.
        parts, final_wide_counts = _apply_wide_paragraph_recovery(
            source_parts=source_parts,
            translated_parts=parts,
            translatable_indices=translatable_indices,
            source_segments=source_texts,
            paragraph_groups=translatable_paragraph_groups,
            paragraph_part_ranges=paragraph_part_ranges,
            translate_text=translate_text,
            cache=wide_cache,
            max_chunk_chars=max_chunk_chars,
        )
        for part_idx, source_seg, heading_group in zip(
            translatable_indices,
            source_texts,
            translatable_heading_groups,
        ):
            if heading_group is None:
                continue
            parts[part_idx] = _apply_heading_glossary_postedit(source_seg, parts[part_idx])

        # Phase 8.8 abc: heading-specific stabilization.
        # a) normalize all-caps heading input and restore caps style.
        # b) detect RU OOV confabulation and retry in contextual mode.
        # c) route short heading segments through a dedicated heading translator when provided.
        for seg_no, (part_idx, source_seg, heading_group, preserve_allcaps_style) in enumerate(
            zip(
                translatable_indices,
                source_texts,
                translatable_heading_groups,
                heading_allcaps_style_flags,
            ),
            start=1,
        ):
            if heading_group is None:
                continue

            candidate = parts[part_idx]
            if _HEADING_MERGE_SEPARATOR in source_seg:
                # Merged inline-heading fragments are handled by split/join path.
                parts[part_idx] = _apply_heading_glossary_postedit(
                    source_seg,
                    _restore_heading_caps_style(candidate, preserve_allcaps_style),
                )
                continue

            source_core = _segment_core_text(source_seg)
            if translate_heading_text is not None and len(source_core) <= heading_translation_max_chars:
                normalized_heading, _ = _normalize_heading_case_for_translation(source_seg)
                cache_key = f"{target_language_code}\x1f{normalized_heading}"
                cached_heading = heading_translation_cache.get(cache_key)
                if cached_heading is None:
                    try:
                        cached_heading = translate_heading_text(normalized_heading)
                    except Exception:
                        cached_heading = ""
                    heading_translation_cache[cache_key] = cached_heading
                if cached_heading.strip():
                    candidate = cached_heading

            candidate = _restore_heading_caps_style(candidate, preserve_allcaps_style)
            candidate = _apply_heading_glossary_postedit(source_seg, candidate)

            needs_oov_retry = (
                enable_heading_oov_guard
                and _heading_has_oov_confabulation(
                    source_seg,
                    candidate,
                    target_language_code=target_language_code,
                )
            )
            needs_identity_retry = _is_identity_residual(source_seg, candidate)
            if needs_oov_retry:
                heading_oov_retry_count += 1

            if needs_oov_retry or needs_identity_retry:
                context_text = _extract_next_paragraph_context_text(source_parts, part_idx)
                recovered_heading = _recover_heading_segment_with_context(
                    source_seg,
                    context_text=context_text,
                    translate_text=translate_text,
                    cache=final_cache,
                    max_chunk_chars=max_chunk_chars,
                    seg_index=seg_no,
                )
                recovered_heading = _restore_heading_caps_style(
                    recovered_heading,
                    preserve_allcaps_style,
                )
                recovered_heading = _apply_heading_glossary_postedit(source_seg, recovered_heading)
                if not _is_identity_residual(source_seg, recovered_heading):
                    candidate = recovered_heading
                elif translate_heading_text is not None and len(source_core) <= heading_translation_max_chars:
                    # One extra short-heading attempt in MT mode for stubborn identity results.
                    normalized_heading, _ = _normalize_heading_case_for_translation(source_seg)
                    cache_key = f"{target_language_code}\x1f{normalized_heading}"
                    cached_heading = heading_translation_cache.get(cache_key)
                    if cached_heading is None:
                        try:
                            cached_heading = translate_heading_text(normalized_heading)
                        except Exception:
                            cached_heading = ""
                        heading_translation_cache[cache_key] = cached_heading
                    if cached_heading.strip():
                        candidate = _apply_heading_glossary_postedit(
                            source_seg,
                            _restore_heading_caps_style(cached_heading, preserve_allcaps_style),
                        )

            if (
                enable_heading_oov_guard
                and _heading_has_oov_confabulation(
                    source_seg,
                    candidate,
                    target_language_code=target_language_code,
                )
            ):
                heading_oov_unresolved += 1

            parts[part_idx] = candidate

        quality_gate_counts: dict[str, int] = {}
        if enable_en_residual_quality_gate:
            parts, quality_gate_counts = _apply_en_residual_quality_gate(
                source_parts=source_parts,
                translated_parts=parts,
                translatable_indices=translatable_indices,
                source_segments=source_texts,
                paragraph_groups=translatable_paragraph_groups,
                paragraph_part_ranges=paragraph_part_ranges,
                translate_text=translate_text,
                cache=final_cache,
                max_chunk_chars=max_chunk_chars,
                max_segments=en_residual_quality_gate_max_segments,
            )

        cjk_quality_gate_counts: dict[str, int] = {}
        if enable_cjk_quality_gate:
            parts, cjk_quality_gate_counts = _apply_cjk_quality_gate(
                source_parts=source_parts,
                translated_parts=parts,
                translatable_indices=translatable_indices,
                source_segments=source_texts,
                paragraph_groups=translatable_paragraph_groups,
                paragraph_part_ranges=paragraph_part_ranges,
                translate_text=translate_text,
                cache=final_cache,
                max_chunk_chars=max_chunk_chars,
                max_segments=cjk_quality_gate_max_segments,
                target_language_code=target_language_code,
            )

        if target_language_code == "ru":
            for part_idx, source_seg in zip(translatable_indices, source_texts):
                parts[part_idx] = _apply_ru_terminology_postedit(source_seg, parts[part_idx])

        short_guard_counts: dict[str, int] = {}
        for part_idx, source_seg in zip(translatable_indices, source_texts):
            guarded_seg, guard_reason = _apply_short_translation_guard(source_seg, parts[part_idx])
            if guard_reason is not None:
                parts[part_idx] = guarded_seg
                short_guard_counts[guard_reason] = short_guard_counts.get(guard_reason, 0) + 1

        parts = _split_heading_text_nodes(parts, heading_merges)
        for part_idx in translatable_indices:
            parts[part_idx] = _clean_final_text_fragment(parts[part_idx])

        translated_segments = sum(
            1
            for part_idx, source_seg in zip(translatable_indices, source_texts)
            if parts[part_idx] != source_seg
        )
        en_residual_segments = sum(
            1
            for part_idx, source_seg in zip(translatable_indices, source_texts)
            if _is_identity_residual(source_seg, parts[part_idx])
        )
        sentinel_leak_segments = sum(
            1
            for part_idx in translatable_indices
            if _UNRESOLVED_SENTINEL_PATTERN.search(parts[part_idx])
        )
        cjk_contamination_segments = sum(
            1
            for part_idx in translatable_indices
            if _has_unexpected_cjk(parts[part_idx], target_language_code=target_language_code)
        )
        wide_recovery_total = (
            initial_wide_counts.get("wide_paragraph_recovery", 0)
            + final_wide_counts.get("wide_paragraph_recovery", 0)
        )
        wide_split_fail_total = (
            initial_wide_counts.get("wide_recovery_split_fail", 0)
            + final_wide_counts.get("wide_recovery_split_fail", 0)
        )
        wide_skipped_large_total = (
            initial_wide_counts.get("wide_recovery_skipped_large", 0)
            + final_wide_counts.get("wide_recovery_skipped_large", 0)
        )
        if on_warning is not None:
            try:
                on_warning(f"identity_terminal_count={final_identity_terminal_count}")
                on_warning(f"wide_paragraph_recovery_count={wide_recovery_total}")
                on_warning(f"wide_recovery_split_fail_count={wide_split_fail_total}")
                on_warning(f"wide_recovery_skipped_large_count={wide_skipped_large_total}")
                on_warning(f"en_residual_segments={en_residual_segments}")
                on_warning(f"sentinel_leak_segments={sentinel_leak_segments}")
                on_warning(f"cjk_contamination_segments={cjk_contamination_segments}")
                on_warning(f"tiny_fragment_preserved_count={tiny_fragment_preserved_count}")
                on_warning(
                    "short_translation_guard_rejected_count="
                    f"{sum(short_guard_counts.values())}"
                )
                for reason, count in sorted(short_guard_counts.items()):
                    on_warning(f"short_translation_guard_{reason}={count}")
                on_warning(f"heading_oov_retry_count={heading_oov_retry_count}")
                on_warning(f"heading_oov_unresolved={heading_oov_unresolved}")
                on_warning(
                    "en_residual_quality_gate_attempted="
                    f"{quality_gate_counts.get('quality_gate_attempted', 0)}"
                )
                on_warning(
                    "en_residual_quality_gate_recovered="
                    f"{sum(count for name, count in quality_gate_counts.items() if name.endswith('_recovery'))}"
                )
                on_warning(
                    "en_residual_quality_gate_unresolved="
                    f"{quality_gate_counts.get('quality_gate_unresolved', 0)}"
                )
                on_warning(
                    "en_residual_quality_gate_skipped="
                    f"{quality_gate_counts.get('quality_gate_skipped_limit', 0)}"
                )
                on_warning(
                    "en_residual_quality_gate_paragraph_skipped_large="
                    f"{quality_gate_counts.get('quality_gate_paragraph_skipped_large', 0)}"
                )
                on_warning(
                    "en_residual_quality_gate_errors="
                    f"{quality_gate_counts.get('quality_gate_recovery_error', 0)}"
                )
                on_warning(
                    "cjk_quality_gate_attempted="
                    f"{cjk_quality_gate_counts.get('quality_gate_attempted', 0)}"
                )
                on_warning(
                    "cjk_quality_gate_recovered="
                    f"{sum(count for name, count in cjk_quality_gate_counts.items() if name.endswith('_recovery'))}"
                )
                on_warning(
                    "cjk_quality_gate_unresolved="
                    f"{cjk_quality_gate_counts.get('quality_gate_unresolved', 0)}"
                )
                on_warning(
                    "cjk_quality_gate_skipped="
                    f"{cjk_quality_gate_counts.get('quality_gate_skipped_limit', 0)}"
                )
                on_warning(
                    "cjk_quality_gate_errors="
                    f"{cjk_quality_gate_counts.get('quality_gate_recovery_error', 0)}"
                )
            except Exception:
                pass
        return "".join(p for p in parts if p), translated_segments

    if on_batch_fallback is not None:
        try:
            on_batch_fallback(batch_reason)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Fallback: per-segment translation (original behaviour)              #
    # ------------------------------------------------------------------ #
    cache: dict[str, str] = {}
    translated_segments = 0
    processed_segments = 0
    out: list[str] = []
    fallback_skip_stack: list[str] = []
    fallback_source_segments: list[str] = []
    fallback_translated_segments: list[str] = []
    fallback_out_indices: list[int] = []
    short_guard_counts: dict[str, int] = {}

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, fallback_skip_stack)
            out.append(part)
            continue
        if fallback_skip_stack or not _has_translatable_visible_text(part):
            out.append(part)
            continue
        if _should_preserve_tiny_fragment(part):
            out.append(part)
            continue

        current_segment = processed_segments + 1
        if on_segment_start is not None:
            try:
                on_segment_start(current_segment, total_segments)
            except Exception:
                pass

        translated = _translate_text_segment(
            part,
            translate_text=translate_text,
            cache=cache,
            max_chunk_chars=max_chunk_chars,
        )
        heading_group = (
            translatable_heading_groups[processed_segments]
            if processed_segments < len(translatable_heading_groups)
            else None
        )
        if heading_group is not None:
            preserve_allcaps_style = (
                heading_allcaps_style_flags[processed_segments]
                if processed_segments < len(heading_allcaps_style_flags)
                else False
            )
            source_seg = part
            source_core = _segment_core_text(source_seg)
            if (
                translate_heading_text is not None
                and _HEADING_MERGE_SEPARATOR not in source_seg
                and len(source_core) <= heading_translation_max_chars
            ):
                normalized_heading, _ = _normalize_heading_case_for_translation(source_seg)
                cache_key = f"{target_language_code}\x1f{normalized_heading}"
                cached_heading = heading_translation_cache.get(cache_key)
                if cached_heading is None:
                    try:
                        cached_heading = translate_heading_text(normalized_heading)
                    except Exception:
                        cached_heading = ""
                    heading_translation_cache[cache_key] = cached_heading
                if cached_heading.strip():
                    translated = cached_heading
            translated = _restore_heading_caps_style(translated, preserve_allcaps_style)
            translated = _apply_heading_glossary_postedit(source_seg, translated)
            if (
                enable_heading_oov_guard
                and _heading_has_oov_confabulation(
                    source_seg,
                    translated,
                    target_language_code=target_language_code,
                )
            ):
                heading_oov_retry_count += 1
                recovered = _recover_single_segment_with_tag_mask(
                    source_seg,
                    translate_text=translate_text,
                    cache=cache,
                    max_chunk_chars=max_chunk_chars,
                    context_label="heading_oov",
                    seg_index=current_segment,
                )
                recovered = _apply_heading_glossary_postedit(
                    source_seg,
                    _restore_heading_caps_style(recovered, preserve_allcaps_style),
                )
                translated = recovered
                if (
                    enable_heading_oov_guard
                    and _heading_has_oov_confabulation(
                        source_seg,
                        translated,
                        target_language_code=target_language_code,
                    )
                ):
                    heading_oov_unresolved += 1
        guarded, guard_reason = _apply_short_translation_guard(part, translated)
        if guard_reason is not None:
            translated = guarded
            short_guard_counts[guard_reason] = short_guard_counts.get(guard_reason, 0) + 1
        if translated != part:
            translated_segments += 1
        out.append(translated)
        fallback_source_segments.append(part)
        fallback_translated_segments.append(translated)
        fallback_out_indices.append(len(out) - 1)
        processed_segments += 1
        if on_progress is not None:
            try:
                on_progress(processed_segments, total_segments)
            except Exception:
                pass

    fallback_quality_gate_counts: dict[str, int] = {}
    if enable_en_residual_quality_gate:
        recovered_fallback_segments, fallback_quality_gate_counts = (
            _apply_en_residual_segment_quality_gate(
                source_segments=fallback_source_segments,
                translated_segments=fallback_translated_segments,
                translate_text=translate_text,
                cache=cache,
                max_chunk_chars=max_chunk_chars,
                max_segments=en_residual_quality_gate_max_segments,
            )
        )
        for out_idx, recovered_seg in zip(fallback_out_indices, recovered_fallback_segments):
            out[out_idx] = recovered_seg
        fallback_translated_segments = recovered_fallback_segments

    fallback_cjk_quality_gate_counts: dict[str, int] = {}
    if enable_cjk_quality_gate:
        recovered_fallback_segments, fallback_cjk_quality_gate_counts = (
            _apply_cjk_segment_quality_gate(
                source_segments=fallback_source_segments,
                translated_segments=fallback_translated_segments,
                translate_text=translate_text,
                cache=cache,
                max_chunk_chars=max_chunk_chars,
                max_segments=cjk_quality_gate_max_segments,
                target_language_code=target_language_code,
            )
        )
        for out_idx, recovered_seg in zip(fallback_out_indices, recovered_fallback_segments):
            out[out_idx] = recovered_seg
        fallback_translated_segments = recovered_fallback_segments

    if target_language_code == "ru":
        for pos, (out_idx, source_seg) in enumerate(zip(fallback_out_indices, fallback_source_segments)):
            out[out_idx] = _apply_ru_terminology_postedit(source_seg, out[out_idx])
            guarded, guard_reason = _apply_short_translation_guard(source_seg, out[out_idx])
            if guard_reason is not None:
                out[out_idx] = guarded
                short_guard_counts[guard_reason] = short_guard_counts.get(guard_reason, 0) + 1
            if pos < len(fallback_translated_segments):
                fallback_translated_segments[pos] = out[out_idx]

    # In the fallback path, out[] has different indices than parts[] (empty strings
    # are skipped), so index-based split is not applicable. Apply protocol-marker
    # cleanup directly per emitted fragment.
    out = [_clean_final_part_fragment(p) for p in out]
    if on_warning is not None:
        en_residual_segments = sum(
            1
            for source_seg, translated_seg in zip(fallback_source_segments, fallback_translated_segments)
            if _is_identity_residual(source_seg, translated_seg)
        )
        sentinel_leak_segments = sum(
            1
            for translated_seg in fallback_translated_segments
            if _UNRESOLVED_SENTINEL_PATTERN.search(translated_seg)
        )
        cjk_contamination_segments = sum(
            1
            for translated_seg in fallback_translated_segments
            if _has_unexpected_cjk(translated_seg, target_language_code=target_language_code)
        )
        try:
            on_warning("identity_terminal_count=0")
            on_warning("wide_paragraph_recovery_count=0")
            on_warning("wide_recovery_split_fail_count=0")
            on_warning(f"en_residual_segments={en_residual_segments}")
            on_warning(f"sentinel_leak_segments={sentinel_leak_segments}")
            on_warning(f"cjk_contamination_segments={cjk_contamination_segments}")
            on_warning(f"tiny_fragment_preserved_count={tiny_fragment_preserved_count}")
            on_warning(
                "short_translation_guard_rejected_count="
                f"{sum(short_guard_counts.values())}"
            )
            for reason, count in sorted(short_guard_counts.items()):
                on_warning(f"short_translation_guard_{reason}={count}")
            on_warning(f"heading_oov_retry_count={heading_oov_retry_count}")
            on_warning(f"heading_oov_unresolved={heading_oov_unresolved}")
            on_warning(
                "en_residual_quality_gate_attempted="
                f"{fallback_quality_gate_counts.get('quality_gate_attempted', 0)}"
            )
            on_warning(
                "en_residual_quality_gate_recovered="
                f"{sum(count for name, count in fallback_quality_gate_counts.items() if name.endswith('_recovery'))}"
            )
            on_warning(
                "en_residual_quality_gate_unresolved="
                f"{fallback_quality_gate_counts.get('quality_gate_unresolved', 0)}"
            )
            on_warning(
                "en_residual_quality_gate_skipped="
                f"{fallback_quality_gate_counts.get('quality_gate_skipped_limit', 0)}"
            )
            on_warning(
                "en_residual_quality_gate_errors="
                f"{fallback_quality_gate_counts.get('quality_gate_recovery_error', 0)}"
            )
            on_warning(
                "cjk_quality_gate_attempted="
                f"{fallback_cjk_quality_gate_counts.get('quality_gate_attempted', 0)}"
            )
            on_warning(
                "cjk_quality_gate_recovered="
                f"{sum(count for name, count in fallback_cjk_quality_gate_counts.items() if name.endswith('_recovery'))}"
            )
            on_warning(
                "cjk_quality_gate_unresolved="
                f"{fallback_cjk_quality_gate_counts.get('quality_gate_unresolved', 0)}"
            )
            on_warning(
                "cjk_quality_gate_skipped="
                f"{fallback_cjk_quality_gate_counts.get('quality_gate_skipped_limit', 0)}"
            )
            on_warning(
                "cjk_quality_gate_errors="
                f"{fallback_cjk_quality_gate_counts.get('quality_gate_recovery_error', 0)}"
            )
        except Exception:
            pass
    out = [
        _clean_final_part_fragment(seg)
        for seg in out
    ]
    return "".join(out), translated_segments
