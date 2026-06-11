"""Deterministic abbreviation repairs for translation input and output."""

from __future__ import annotations

import html as html_lib
import re

ABBREVIATION_EXPANSION_RU: dict[str, str] = {
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
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_outer_ws(text: str) -> tuple[str, str, str]:
    leading_len = len(text) - len(text.lstrip())
    trailing_len = len(text) - len(text.rstrip())
    core_end = len(text) - trailing_len if trailing_len else len(text)
    return text[:leading_len], text[leading_len:core_end], text[core_end:]


def _segment_core_text(text: str) -> str:
    _, core, _ = _split_outer_ws(text)
    return core


def lookup_abbreviation_expansion_ru(key: str, fallback: str) -> str:
    """Return a stable RU expansion for known scientific abbreviations."""
    direct = ABBREVIATION_EXPANSION_RU.get(key)
    if direct is not None:
        return direct
    lowered = key.lower()
    for known_key, expansion in ABBREVIATION_EXPANSION_RU.items():
        if known_key.lower() == lowered:
            return expansion
    return fallback.strip().rstrip(".")


def source_abbreviation_entries(source_seg: str) -> list[tuple[str, str]]:
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
        expansion = lookup_abbreviation_expansion_ru(key, match.group(2))
        entries.append((key, expansion))

    present = {key.lower() for key, _expansion in entries}
    for known_key in ABBREVIATION_EXPANSION_RU:
        if known_key.lower() in present:
            continue
        if re.search(
            rf"(?<![A-Za-z0-9\u00b5]){re.escape(known_key)}(?![A-Za-z0-9\u00b5])",
            payload,
            flags=re.IGNORECASE,
        ):
            entries.append((known_key, ABBREVIATION_EXPANSION_RU[known_key]))
    return entries


def format_abbreviation_entries_ru(entries: list[tuple[str, str]]) -> str:
    rebuilt = "; ".join(f"{key}, {expansion}" for key, expansion in entries)
    return f"Сокращения: {rebuilt}."


def _visible_text_from_html_fragment(fragment: str) -> str:
    text = _HTML_TAG_PATTERN.sub(" ", fragment)
    return _normalize_ws(html_lib.unescape(text))


def replace_abbreviation_paragraphs_ru(source_html: str) -> str:
    """Deterministically translate scientific abbreviation paragraphs."""

    def _replace(match: re.Match[str]) -> str:
        body = match.group("body")
        visible = _visible_text_from_html_fragment(body)
        if not _ABBREVIATION_LABEL_TEXT_PATTERN.match(visible):
            return match.group(0)

        entries = source_abbreviation_entries(visible)
        if len(entries) < 2:
            return match.group(0)

        translated = html_lib.escape(format_abbreviation_entries_ru(entries), quote=False)
        return f'{match.group("open")}<span translate="no">{translated}</span>{match.group("close")}'

    return _ABBREVIATION_PARAGRAPH_PATTERN.sub(_replace, source_html)


def repair_abbreviation_definition_segment(source_seg: str, translated_seg: str) -> str:
    """Rebuild known abbreviation definition lines when the model hallucinates."""
    entries = source_abbreviation_entries(source_seg)
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

    return f"{lead}{format_abbreviation_entries_ru(entries)}{tail}"
