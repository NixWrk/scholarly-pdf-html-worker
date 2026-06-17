from __future__ import annotations

import re


def normalize_semantic_key(value: str) -> str:
    normalized = value.strip().strip(".")
    normalized = re.sub(r"\s*[.\-\u2010\u2011\u2012\u2013\u2014]\s*", "-", normalized)
    return normalized.strip("-").lower()


def figure_key_from_visible_number(value: str) -> str:
    return normalize_semantic_key(re.sub(r"(?i)^s\s+(?=\d)", "s", value.strip()))


def supplementary_figure_key_from_visible_number(value: str) -> str:
    return f"supplementary-{figure_key_from_visible_number(value)}"


def extended_data_figure_key_from_visible_number(value: str) -> str:
    return f"extended-data-{figure_key_from_visible_number(value)}"


def normalize_table_key(label: str) -> str:
    return normalize_semantic_key(label)
