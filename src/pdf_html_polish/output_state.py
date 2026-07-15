from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

from .staging import FILENAME_MAP_NAME


def _normalize_path_str(value: str) -> str:
    return os.path.normcase(str(Path(value).expanduser().resolve(strict=False)))


def _normalize_path(path: Path) -> str:
    return os.path.normcase(str(path.expanduser().resolve(strict=False)))


def _source_hash_suffix(source_pdf_path: Path) -> str:
    digest = hashlib.sha1(source_pdf_path.stem.encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"_{digest}".lower()


def _build_output_artifact_index(output_dir: Path, artifact_extension: str) -> set[str]:
    names: set[str] = set()
    if not output_dir.is_dir():
        return names

    normalized_ext = artifact_extension if artifact_extension.startswith(".") else f".{artifact_extension}"
    normalized_ext = normalized_ext.lower()

    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        artifact_path = child / f"{child.name}{normalized_ext}"
        if artifact_path.is_file():
            names.add(child.name.lower())
    return names


def _load_existing_from_filename_map(
    output_dir: Path,
    output_artifact_dirs: set[str],
) -> tuple[set[str], dict[str, set[str]]]:
    map_path = output_dir / FILENAME_MAP_NAME
    if not map_path.is_file():
        return set(), {}

    existing: set[str] = set()
    alias_sources: dict[str, set[str]] = {}
    with map_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            source_path = (row.get("source_pdf_path") or "").strip()
            alias_pdf_path = (row.get("alias_pdf_path") or "").strip()
            if not source_path or not alias_pdf_path:
                continue

            alias_base = Path(alias_pdf_path).stem.lower()
            normalized_source = _normalize_path_str(source_path)
            alias_sources.setdefault(alias_base, set()).add(normalized_source)
            if alias_base in output_artifact_dirs:
                existing.add(normalized_source)

    return existing, alias_sources


def _alias_is_known_for_other_source(
    alias_base: str,
    normalized_source: str,
    alias_sources: dict[str, set[str]],
) -> bool:
    known_sources = alias_sources.get(alias_base.lower())
    return known_sources is not None and normalized_source not in known_sources


def _exact_legacy_output_alias(output_artifact_dirs: set[str], source_pdf_path: Path) -> str | None:
    alias_base = source_pdf_path.stem.lower()
    return alias_base if alias_base in output_artifact_dirs else None


def _hash_alias_output_aliases(output_artifact_dirs: set[str], source_pdf_path: Path) -> list[str]:
    suffix = _source_hash_suffix(source_pdf_path)
    return [dirname for dirname in output_artifact_dirs if dirname.endswith(suffix)]


def detect_existing_results(
    output_dir: Path,
    source_pdf_paths: list[Path],
    artifact_extension: str = ".md",
) -> set[str]:
    output_artifact_dirs = _build_output_artifact_index(output_dir, artifact_extension)

    existing, alias_sources = _load_existing_from_filename_map(output_dir, output_artifact_dirs)

    for source_pdf_path in source_pdf_paths:
        normalized = _normalize_path(source_pdf_path)
        if normalized in existing:
            continue

        exact_alias = _exact_legacy_output_alias(output_artifact_dirs, source_pdf_path)
        if exact_alias is not None and not _alias_is_known_for_other_source(
            exact_alias,
            normalized,
            alias_sources,
        ):
            existing.add(normalized)
            continue

        for hash_alias in _hash_alias_output_aliases(output_artifact_dirs, source_pdf_path):
            if _alias_is_known_for_other_source(hash_alias, normalized, alias_sources):
                continue
            existing.add(normalized)
            break

    return existing


def is_source_already_converted(
    output_dir: Path,
    source_pdf_path: Path,
    existing_set: set[str] | None = None,
    artifact_extension: str = ".md",
) -> bool:
    normalized = _normalize_path(source_pdf_path)
    if existing_set is None:
        existing_set = detect_existing_results(output_dir, [source_pdf_path], artifact_extension=artifact_extension)
    return normalized in existing_set


def normalize_source_path(source_pdf_path: Path) -> str:
    return _normalize_path(source_pdf_path)
