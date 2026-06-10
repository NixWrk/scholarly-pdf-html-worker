from __future__ import annotations

import re


# Patterns that mask meta-commentary prefixes the model sometimes emits before
# the actual translation. Abbreviations are intentionally not listed here: the
# translation prompt already asks the model to preserve uppercase Latin tokens,
# while XML-like prompt-leak masks are easy for free-form generation to drop.
PROMPT_LEAK_PROTECTION_PATTERNS = [
    r'\b(?:translation|translated text)\s*:\s*',
    r'\boriginal(?:\s+text)?\s*:\s*',
    r'\b(?:source|исходн)(?:\s+текст)?\s*:\s*',
]

TRANSLATOR_REFUSAL_PATTERNS: tuple[re.Pattern[str], ...] = (
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

TRANSLATION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:translation|translated text|перевод)\s*:\s*",
    re.IGNORECASE,
)
ORIGINAL_SECTION_PATTERN = re.compile(
    r"(?:\r?\n){1,2}\s*(?:original(?: text)?|source(?: text)?|исходн(?:ый|ого)\s+текст)\s*:\s*",
    re.IGNORECASE,
)

PROMPT_LEAK_SIGNATURE = re.compile(
    r'[A-Z]{2,},\s*[A-Z]{2,},\s*[A-Z]{2,}.*?(?:перевод|translation|язык|language).*?[\.\n]',
    re.IGNORECASE | re.DOTALL,
)
PROMPT_RULE_LEAK_PHRASES: tuple[str, ...] = (
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
VISIBLE_PROMPT_LEAK_PATTERN = re.compile(
    "|".join(re.escape(phrase) for phrase in PROMPT_RULE_LEAK_PHRASES),
    re.IGNORECASE,
)
PROMPT_RULE_ECHO_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
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
PROMPT_META_ECHO_PATTERN = re.compile(
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


def is_translator_refusal(text: str) -> bool:
    """Return True when *text* looks like a model refusal or meta-commentary."""
    return any(pattern.search(text) for pattern in TRANSLATOR_REFUSAL_PATTERNS)


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_source_echo(translated: str, source: str) -> str:
    """Trim common "translation + original source" echoes from model output."""
    cleaned = translated.strip()
    if not cleaned:
        return translated

    cleaned = TRANSLATION_PREFIX_PATTERN.sub("", cleaned)

    source_clean = source.strip()
    if not source_clean:
        return cleaned

    labeled_original = ORIGINAL_SECTION_PATTERN.search(cleaned)
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

    source_norm = normalize_ws(source_clean).lower()
    if not source_norm:
        return cleaned

    blocks = [block.strip() for block in re.split(r"(?:\r?\n){2,}", cleaned) if block.strip()]
    if len(blocks) > 1:
        kept: list[str] = []
        removed = False
        for block in blocks:
            block_norm = normalize_ws(block).lower()
            if block_norm == source_norm:
                removed = True
                continue
            kept.append(block)
        if removed and kept:
            return "\n\n".join(kept)

    return cleaned


def has_visible_prompt_leak(text: str) -> bool:
    """Return True when text visibly contains translated prompt instructions."""
    return bool(text and VISIBLE_PROMPT_LEAK_PATTERN.search(text))


def strip_prompt_leak_echo(text: str) -> str:
    """Remove known prompt-rule echoes while preserving any real translation tail."""
    if not text:
        return text

    cleaned = text.strip()
    previous = None
    while previous != cleaned:
        previous = cleaned
        for pattern in PROMPT_RULE_ECHO_BLOCK_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        cleaned = PROMPT_META_ECHO_PATTERN.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned.strip(" \t\r\n\"'«»")


def split_outer_ws(text: str) -> tuple[str, str, str]:
    leading_len = len(text) - len(text.lstrip())
    trailing_len = len(text) - len(text.rstrip())
    core_end = len(text) - trailing_len if trailing_len else len(text)
    return text[:leading_len], text[leading_len:core_end], text[core_end:]


def sanitize_prompt_leak_segment(
    source_seg: str,
    translated_seg: str,
) -> tuple[str, bool]:
    """Strip prompt-rule echoes from a translated segment or fall back safely."""
    if not has_visible_prompt_leak(translated_seg):
        return translated_seg, False

    lead, core, tail = split_outer_ws(translated_seg)
    cleaned_core = strip_prompt_leak_echo(core)
    if cleaned_core and not has_visible_prompt_leak(cleaned_core):
        return f"{lead}{cleaned_core}{tail}", True
    return source_seg, True


def apply_prompt_leak_mask(text: str) -> tuple[str, dict[str, str]]:
    """Protect against prompt leakage by masking specific model prefix patterns."""
    amap: dict[str, str] = {}
    masked = text

    for pattern in PROMPT_LEAK_PROTECTION_PATTERNS:
        compiled_pattern = re.compile(pattern, re.IGNORECASE)

        def replace_match(match: re.Match[str]) -> str:
            original = match.group(0)
            token = f'<z2m-p id="{len(amap)}"/>'
            amap[token] = original
            return token

        masked = compiled_pattern.sub(replace_match, masked)

    return masked, amap
