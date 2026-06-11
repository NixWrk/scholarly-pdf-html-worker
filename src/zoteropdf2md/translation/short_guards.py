"""Guards for tiny or suspicious single-fragment translations."""

from __future__ import annotations

import html as html_lib
import re

from .prompt_guards import is_translator_refusal

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
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


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def visible_text_from_html_fragment(fragment: str) -> str:
    text = _HTML_TAG_PATTERN.sub(" ", fragment)
    return _normalize_ws(html_lib.unescape(text))


def tiny_fragment_visible_text(fragment: str) -> str:
    visible = visible_text_from_html_fragment(fragment)
    visible = visible.replace("\u00a0", " ")
    return _normalize_ws(visible)


def strip_tiny_wrapper_punctuation(text: str) -> str:
    return text.strip(" \t\r\n()[]{}.,;:<>")


def should_preserve_tiny_fragment(fragment: str) -> bool:
    """Return True for atomic technical fragments that should not hit the model."""
    visible = tiny_fragment_visible_text(fragment)
    if not visible:
        return False

    core = strip_tiny_wrapper_punctuation(visible)
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


def short_translation_guard_reason(source_seg: str, translated_seg: str) -> str | None:
    """Detect bad short-fragment outputs such as variant lists or meta comments."""
    source_visible = tiny_fragment_visible_text(source_seg)
    translated_visible = tiny_fragment_visible_text(translated_seg)
    if not source_visible or not translated_visible:
        return None

    source_core = strip_tiny_wrapper_punctuation(source_visible)
    translated_core = strip_tiny_wrapper_punctuation(translated_visible)
    if not source_core or not translated_core:
        return None

    if should_preserve_tiny_fragment(source_seg) and translated_core != source_core:
        return "protected_tiny_fragment_changed"

    source_len = len(source_core)
    if source_len > 32:
        return None

    if is_translator_refusal(translated_core):
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


def apply_short_translation_guard(source_seg: str, translated_seg: str) -> tuple[str, str | None]:
    reason = short_translation_guard_reason(source_seg, translated_seg)
    if reason is None:
        return translated_seg, None
    return source_seg, reason
