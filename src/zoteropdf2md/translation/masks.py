from __future__ import annotations

import re

from ..abbreviations import LATIN_ABBREV_TO_RU, RU_ABBREV_TO_LATIN


ABBREV_PATTERN = re.compile(r"\b[A-Z]{2,5}\d*\b")
PROTECTED_SCIENCE_TERM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])("
    r"(?:i|micro|u|\u00b5)?ECoG|"
    r"TiN|PtIr|IrOx|RuOx|AIROF|EIROF|SIROF|"
    r"Parylene(?:[-\s]?C)?|PDMS|SU-8|ZIF|"
    r"Steeltrodes?|steeltrodes?"
    r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)
ABBREV_TOKEN_PATTERN = re.compile(r"@@Z2M\\?_A(\d+)(?:@@|@(?!@))", re.IGNORECASE)
TAG_TOKEN_PATTERN = re.compile(r"@@Z2M\\?_T(\d+)(?:@@|@(?!@))", re.IGNORECASE)
LATIN_ABBREV_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in LATIN_ABBREV_TO_RU.keys()]
RU_ABBREV_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in RU_ABBREV_TO_LATIN.keys()]

FORMULA_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"@@Z2M\\?_T\d+@@", re.IGNORECASE),
    re.compile(r"&lt;/?[A-Za-z][^&<>]{0,300}?&gt;", re.IGNORECASE),
    re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE),
    re.compile(r"\bdoi:\s*10\.\d{4,9}/[^\s<>()\"']+", re.IGNORECASE),
    re.compile(r"\\\(\s*\\mu\s*\\\)\s*m\b", re.IGNORECASE),
    re.compile(r"\\mu\s*m\b", re.IGNORECASE),
    re.compile(r"\u00b5\s*m\b", re.IGNORECASE),
    re.compile(
        r"\d+(?:\s*(?:\\\(\s*\\mu\s*\\\)|\\mu|\u00b5)\s*m)?"
        r"(?:\s*[x\u00d7]\s*\d+(?:\s*(?:\\\(\s*\\mu\s*\\\)|\\mu|\u00b5)\s*m)?){1,4}",
        re.IGNORECASE,
    ),
    re.compile(r"\$[^$\n]{1,600}\$"),
    re.compile(r"\\\([^\n]{1,600}?\\\)"),
    re.compile(r"\\\[[\s\S]{1,600}?\\\]"),
    re.compile(r"\\[A-Za-z]+(?:\s*\{[^{}]{0,160}\}){0,3}"),
    re.compile(
        r"[A-Za-z](?:\s*_\{[^{}]{1,80}\}|\s*_[A-Za-z0-9]{1,20}|\s*\^\{[^{}]{1,80}\}|\s*\^[A-Za-z0-9]{1,20})+"
    ),
    re.compile(r"(?<!\w)[A-Za-z]\s*(?=\\[A-Za-z])"),
    re.compile(
        r"(?<!\w)(?=[^,\n]{0,240}[=+\-*/])(?=[^,\n]{0,240}(?:\\|_|\^))"
        r"[A-Za-z0-9\\{}_^().]+(?:\s+[A-Za-z0-9\\{}_^().]+){0,40}(?!\w)"
    ),
    re.compile(r"(?<!\w)\d+(?:\s*\\times\s*\d+){1,4}(?:\s*[A-Za-z]{1,8})?(?!\w)", re.IGNORECASE),
)

FORMULA_TOKEN_PATTERN = re.compile(r"@@Z2M(?:\\?_)?F(\d+)(?:@@|@(?!@))", re.IGNORECASE)
UNRESOLVED_SENTINEL_PATTERN = re.compile(
    r"@{1,2}Z2M(?:\\?_)?[A-Z0-9_]+(?:@{0,2}|(?:\\?_)+)?",
    re.IGNORECASE,
)
HEADING_MERGE_SEPARATOR_LEAK_PATTERN = re.compile(
    r"@{1,2}Z2M(?:\\?_)?HSEP@{0,2}",
    re.IGNORECASE,
)
AUX_PROTOCOL_SENTINEL_LEAK_PATTERN = re.compile(
    r"(?:@{1,2}Z2M(?:\\?_)?[ATF]\d+(?:@{1,3}|(?:\\?_)+)?|"
    r"Z2M(?:\\?_)?[ATF]\d+(?:@{1,3}|(?:\\?_)+)?)",
    re.IGNORECASE,
)
STRAY_ABBREV_AT_PATTERN = re.compile(
    r"\b((?:i|micro|u|\u00b5)?ECoG|SNR|BMI|SEP|MEMS|COG|ERP|NHP|"
    r"VNA|ADC|LC|IEEE)@(?!@)(?=$|[^A-Za-z0-9])"
)


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
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


def formula_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in FORMULA_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if end > start:
                spans.append((start, end))
    return merge_spans(spans)


def apply_formula_mask(text: str) -> tuple[str, dict[str, str]]:
    """Replace formula spans with ``@@Z2MF{N}@@`` tokens."""
    spans = formula_spans(text)
    if not spans:
        return text, {}
    fmap: dict[str, str] = {}
    masked = text
    for j, (start, end) in enumerate(reversed(spans)):
        real_j = len(spans) - 1 - j
        token = f"@@Z2MF{real_j}@@"
        fmap[token] = text[start:end]
        masked = masked[:start] + token + masked[end:]
    return masked, fmap


def normalize_sentinel_escapes(text: str) -> str:
    """Normalize markdown-escaped protocol sentinels returned by LLMs."""
    if "@@Z2M" not in text and "@@z2m" not in text:
        return text
    return re.sub(r"@@([zZ]2[mM])\\+(?=[A-Za-z_])", r"@@\1", text)


def sentinel_token_variants(token: str) -> set[str]:
    variants = {token}
    if "_" in token:
        variants.add(token.replace("_", r"\_"))
    if token.endswith("@@"):
        short = token[:-1]
        variants.add(short)
        if "_" in short:
            variants.add(short.replace("_", r"\_"))
    return {variant for variant in variants if variant}


def strip_protocol_sentinels(text: str) -> str:
    """Remove leaked internal protocol sentinels from final text fragments."""
    if "z2m" not in text.lower():
        return text
    cleaned = normalize_sentinel_escapes(text)
    cleaned = HEADING_MERGE_SEPARATOR_LEAK_PATTERN.sub(" ", cleaned)
    cleaned = AUX_PROTOCOL_SENTINEL_LEAK_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def strip_stray_abbrev_at_signs(text: str) -> str:
    """Remove a leaked sentinel tail after protected abbreviations."""
    if "@" not in text:
        return text
    return STRAY_ABBREV_AT_PATTERN.sub(r"\1", text)


def clean_final_text_fragment(text: str) -> str:
    return strip_stray_abbrev_at_signs(strip_protocol_sentinels(text))


def clean_final_part_fragment(part: str) -> str:
    if part.startswith("<"):
        return strip_protocol_sentinels(part)
    return clean_final_text_fragment(part)


def restore_formula_mask(text: str, fmap: dict[str, str]) -> str:
    """Substitute formula placeholder tokens back with their original strings."""
    if not fmap:
        return text
    text = normalize_sentinel_escapes(text)

    def replace(match: re.Match[str]) -> str:
        token = f"@@Z2MF{int(match.group(1))}@@"
        return fmap.get(token, match.group(0))

    restored = FORMULA_TOKEN_PATTERN.sub(replace, text)
    for token, formula in fmap.items():
        for variant in sentinel_token_variants(token):
            restored = restored.replace(variant, formula)
    return restored


def apply_custom_abbrev_mask(text: str) -> tuple[str, dict[str, str]]:
    """Apply custom masking for specific Latin abbreviations using our dictionary."""
    amap: dict[str, str] = {}
    masked = text

    for pattern in LATIN_ABBREV_PATTERNS:

        def replace_match(match: re.Match[str]) -> str:
            original = match.group(0)
            for key_pattern, _replacement in LATIN_ABBREV_TO_RU.items():
                if re.match(key_pattern, original, re.IGNORECASE):
                    token = f"@@Z2M_A{len(amap)}@@"
                    amap[token] = original
                    return token
            return original

        masked = pattern.sub(replace_match, masked)

    return masked, amap


def apply_abbrev_mask(text: str) -> tuple[str, dict[str, str]]:
    """Replace abbreviations and unstable scientific terms with sentinel tokens."""
    preferred_spans = [
        (match.start(), match.end())
        for match in PROTECTED_SCIENCE_TERM_PATTERN.finditer(text)
    ]
    spans = list(preferred_spans)
    for match in ABBREV_PATTERN.finditer(text):
        start, end = match.span()
        if any(not (end <= pref_start or start >= pref_end) for pref_start, pref_end in preferred_spans):
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


def restore_abbrev_mask(text: str, amap: dict[str, str]) -> str:
    """Substitute abbreviation placeholder tokens back with their original strings."""
    if not amap:
        return text
    text = normalize_sentinel_escapes(text)

    def replace(match: re.Match[str]) -> str:
        token = f"@@Z2M_A{int(match.group(1))}@@"
        return amap.get(token, match.group(0))

    restored = ABBREV_TOKEN_PATTERN.sub(replace, text)
    for token, original in amap.items():
        for variant in sentinel_token_variants(token):
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


def apply_tag_mask(text: str) -> tuple[str, dict[str, str]]:
    """Mask inline HTML tags inside a text segment to keep recovery stable."""
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


def restore_tag_mask(text: str, tmap: dict[str, str]) -> str:
    """Restore inline tag tokens after recovery translation."""
    if not tmap:
        return text
    text = normalize_sentinel_escapes(text)

    def replace(match: re.Match[str]) -> str:
        token = f"@@Z2M_T{int(match.group(1))}@@"
        return tmap.get(token, match.group(0))

    restored = TAG_TOKEN_PATTERN.sub(replace, text)
    for token, original in tmap.items():
        for variant in sentinel_token_variants(token):
            restored = restored.replace(variant, original)
    return restored
