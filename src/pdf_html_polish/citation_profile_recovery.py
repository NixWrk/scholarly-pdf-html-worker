"""Helpers for consuming citation profiles during HTML polishing."""

from __future__ import annotations

import html as html_lib
from typing import Any


MAX_PROFILE_REFERENCE_GAP_RECOVERY = 24
MAX_PROFILE_REFERENCE_SECTION_RECOVERY = 80


def citation_profile_style(citation_profile: Any | None) -> str:
    if citation_profile is None:
        return ""
    if isinstance(citation_profile, dict):
        return str(citation_profile.get("style") or "")
    return str(getattr(citation_profile, "style", "") or "")


def citation_profile_confidence(citation_profile: Any | None) -> str:
    if citation_profile is None:
        return ""
    if isinstance(citation_profile, dict):
        return str(citation_profile.get("confidence") or "")
    return str(getattr(citation_profile, "confidence", "") or "")


def citation_profile_is_high_confidence_paren_numeric(citation_profile: Any | None) -> bool:
    return (
        citation_profile_style(citation_profile) == "paren_numeric"
        and citation_profile_confidence(citation_profile) == "high"
    )


def citation_profile_is_high_confidence_superscript_numeric(citation_profile: Any | None) -> bool:
    return (
        citation_profile_style(citation_profile) == "superscript_numeric"
        and citation_profile_confidence(citation_profile) == "high"
    )


def citation_profile_is_bracket_numeric(citation_profile: Any | None) -> bool:
    return (
        citation_profile_style(citation_profile) == "bracket_numeric"
        and citation_profile_confidence(citation_profile) in {"medium", "high"}
    )


def citation_profile_is_author_year(citation_profile: Any | None) -> bool:
    return (
        citation_profile_style(citation_profile) == "author_year"
        and citation_profile_confidence(citation_profile) in {"medium", "high"}
    )


def citation_profile_items(citation_profile: Any | None, key: str) -> list[Any]:
    if citation_profile is None:
        return []
    if isinstance(citation_profile, dict):
        value = citation_profile.get(key)
    else:
        value = getattr(citation_profile, key, None)
    return value if isinstance(value, list) else []


def citation_profile_ref_prefix(citation_profile: Any | None) -> str:
    if citation_profile is None:
        return ""
    if isinstance(citation_profile, dict):
        return str(citation_profile.get("ref_dest_prefix") or "")
    return str(getattr(citation_profile, "ref_dest_prefix", "") or "")


def profile_item_value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def citation_profile_has_zotero_reference_evidence(citation_profile: Any | None) -> bool:
    if citation_profile is None:
        return False
    try:
        count = int(profile_item_value(citation_profile, "zotero_citation_count", 0) or 0)
    except (TypeError, ValueError):
        count = 0
    return count > 0 or bool(citation_profile_items(citation_profile, "zotero_citations"))


def citation_profile_reference_entries_by_number(citation_profile: Any | None) -> dict[int, str]:
    entries: dict[int, str] = {}
    for item in citation_profile_items(citation_profile, "reference_entries"):
        try:
            number = int(profile_item_value(item, "number", 0) or 0)
        except (TypeError, ValueError):
            continue
        text = str(profile_item_value(item, "text", "") or "").strip()
        if number <= 0 or not text:
            continue
        entries.setdefault(number, text)
    return entries


def citation_profile_reference_recovery_numbers(citation_profile: Any | None) -> list[int]:
    raw_values = profile_item_value(citation_profile, "reference_entries_recovery_numbers", [])
    if not isinstance(raw_values, list):
        return []
    numbers: list[int] = []
    for value in raw_values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in numbers:
            numbers.append(number)
    return sorted(numbers)


def contiguous_profile_reference_recovery_numbers(
    citation_profile: Any | None,
    entries_by_number: dict[int, str],
) -> list[int]:
    requested = citation_profile_reference_recovery_numbers(citation_profile)
    if not requested:
        return []
    max_number = max(requested)
    if max_number > MAX_PROFILE_REFERENCE_SECTION_RECOVERY:
        return []
    numbers = list(range(1, max_number + 1))
    if any(number not in entries_by_number for number in numbers):
        return []
    return numbers


def pdf_recovered_reference_section_from_profile(citation_profile: Any | None) -> tuple[str, int]:
    entries_by_number = citation_profile_reference_entries_by_number(citation_profile)
    if not entries_by_number:
        return "", 0
    numbers = contiguous_profile_reference_recovery_numbers(citation_profile, entries_by_number)
    if not numbers:
        return "", 0
    items = []
    for number in numbers:
        escaped = html_lib.escape(entries_by_number[number], quote=False)
        items.append(
            f'<li block-type="ListItem" id="ref-{number}" data-z2m-pdf-recovered-ref="1">{escaped}</li>'
        )
    section = (
        '<h2 data-z2m-pdf-recovered-references="1">References</h2>'
        '<ul class="z2m-pdf-recovered-references" data-z2m-pdf-recovered-references="1">'
        + " ".join(items)
        + "</ul>"
    )
    return section, numbers[-1]
