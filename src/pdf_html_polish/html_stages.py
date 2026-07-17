from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
from typing import Iterable

from .artifact_integrity import (
    FileFingerprint,
    artifact_is_structurally_valid,
    fingerprint_file,
    metadata_still_matches,
)
from .atomic_io import write_json_atomic, write_text_atomic


HTML_STAGE_DIR_NAME = "_pdf_html_polish_stages"
LEGACY_HTML_STAGE_DIR_NAME = "_z2m_stages"
HTML_STAGE_DIR_NAMES = frozenset({HTML_STAGE_DIR_NAME, LEGACY_HTML_STAGE_DIR_NAME})
HTML_STAGE_LOG_NAME = "stage.log"
RAW_STAGE_NAME = "01.en.raw.html"
POLISH_STAGE_NAME = "02.en.polish.html"
RAW_CONVERSION_MANIFEST_NAME = "raw_conversion_manifest.json"
RAW_CONVERSION_MANIFEST_SCHEMA_VERSION = 2
RAW_CONVERSION_MANIFEST_SUPPORTED_SCHEMAS = frozenset({1, 2})
_MAX_RAW_MANIFEST_BYTES = 64 * 1024


@dataclass(frozen=True)
class HtmlStageSaveResult:
    path: Path
    chars: int
    bytes: int
    log_path: Path


@dataclass(frozen=True)
class RawConversionValidation:
    raw_stage_path: Path
    manifest_path: Path
    valid: bool
    reason: str
    source_pdf_path: Path | None = None
    schema_version: int | None = None
    source_pdf_bytes: int | None = None
    source_pdf_sha256: str | None = None
    raw_html_bytes: int | None = None
    raw_html_sha256: str | None = None


def _path_key(path: Path) -> str:
    return os.path.normcase(str(Path(path).expanduser().resolve(strict=False)))


def raw_conversion_manifest_path(raw_stage_path: Path) -> Path:
    return Path(raw_stage_path).parent / RAW_CONVERSION_MANIFEST_NAME


def _validate_raw_stage_location(raw_stage_path: Path, *, require_file: bool) -> Path:
    raw_path = Path(raw_stage_path).expanduser()
    stage_dir = raw_path.parent
    article_dir = stage_dir.parent
    if raw_path.name != RAW_STAGE_NAME or stage_dir.name not in HTML_STAGE_DIR_NAMES:
        raise ValueError(f"Raw stage must be inside a recognized stage directory: {raw_path}")
    if article_dir.is_symlink() or stage_dir.is_symlink() or raw_path.is_symlink():
        raise ValueError(f"Raw conversion path must not contain a symlink: {raw_path}")
    if require_file and not raw_path.is_file():
        raise ValueError(f"Raw conversion stage is missing: {raw_path}")
    try:
        return raw_path.resolve(strict=require_file)
    except OSError as exc:
        raise ValueError(f"Raw conversion stage cannot be resolved: {raw_path}") from exc


def invalidate_raw_conversion_manifest(raw_stage_path: Path) -> None:
    raw_path = _validate_raw_stage_location(raw_stage_path, require_file=False)
    manifest_path = raw_conversion_manifest_path(raw_path)
    try:
        manifest_path.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Could not invalidate raw conversion: {manifest_path}") from exc


def write_raw_conversion_manifest(
    stage_dir: Path,
    *,
    source_pdf: Path,
    raw_stage_path: Path,
) -> Path:
    """Atomically publish provenance for one confirmed raw Marker stage."""

    raw_path = _validate_raw_stage_location(raw_stage_path, require_file=True)
    stage_root = Path(stage_dir).expanduser().resolve(strict=False)
    if _path_key(raw_path.parent) != _path_key(stage_root):
        raise ValueError(f"Raw stage must be {stage_root / RAW_STAGE_NAME}: {raw_stage_path}")
    invalidate_raw_conversion_manifest(raw_path)
    try:
        source_path = Path(source_pdf).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Source PDF cannot be resolved: {source_pdf}") from exc
    source_fingerprint = fingerprint_file(source_path, reject_symlink=False)
    raw_fingerprint = fingerprint_file(
        raw_path,
        reject_symlink=True,
        capture_edges=True,
    )
    if source_fingerprint is None:
        raise ValueError(f"Source PDF is missing, empty, or unstable: {source_path}")
    if raw_fingerprint is None or not artifact_is_structurally_valid(
        raw_path,
        raw_fingerprint,
    ):
        raise ValueError(f"Raw HTML stage is empty, malformed, or unstable: {raw_path}")
    payload = {
        "schema_version": RAW_CONVERSION_MANIFEST_SCHEMA_VERSION,
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "article_name": raw_path.parent.parent.name,
        "source_pdf_path": str(source_path),
        "source_pdf_name": source_path.name,
        "source_pdf_bytes": source_fingerprint.size,
        "source_pdf_sha256": source_fingerprint.sha256,
        "raw_html_name": RAW_STAGE_NAME,
        "raw_html_bytes": raw_fingerprint.size,
        "raw_html_sha256": raw_fingerprint.sha256,
    }
    manifest_path = raw_path.parent / RAW_CONVERSION_MANIFEST_NAME
    write_json_atomic(manifest_path, payload)
    if not metadata_still_matches(source_path, source_fingerprint) or not metadata_still_matches(
        raw_path,
        raw_fingerprint,
    ):
        invalidate_raw_conversion_manifest(raw_path)
        raise RuntimeError("Source PDF or raw HTML changed during manifest publication.")
    return manifest_path


def html_stage_dir_for_html(html_path: Path) -> Path:
    """Return the per-paper debug directory for HTML stage snapshots."""

    return html_path.parent / HTML_STAGE_DIR_NAME


def html_stage_log_path(stage_dir: Path) -> Path:
    return stage_dir / HTML_STAGE_LOG_NAME


def is_html_stage_path(path: Path) -> bool:
    return path.parent.name in HTML_STAGE_DIR_NAMES


def is_html_stage_dir_name(name: str) -> bool:
    return name in HTML_STAGE_DIR_NAMES


def article_dir_from_html_stage(stage_path: Path) -> Path:
    return stage_path.parent.parent if is_html_stage_path(stage_path) else stage_path.parent


def article_name_from_html_stage(stage_path: Path) -> str:
    return article_dir_from_html_stage(stage_path).name


def _manifest_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    return value if type(value) is int and value >= 0 else None


def _manifest_sha256(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str) or len(value) != 64:
        return None
    normalized = value.lower()
    return normalized if all(character in "0123456789abcdef" for character in normalized) else None


def _load_raw_conversion_manifest(path: Path) -> tuple[dict[str, object] | None, str]:
    try:
        if path.is_symlink():
            return None, "manifest_symlink"
        manifest_stat = path.stat()
        if not stat.S_ISREG(manifest_stat.st_mode):
            return None, "manifest_not_regular_file"
        if manifest_stat.st_size > _MAX_RAW_MANIFEST_BYTES:
            return None, "manifest_too_large"
        payload = json.loads(path.read_text(encoding="utf-8"))
        after_stat = path.stat()
    except FileNotFoundError:
        return None, "manifest_missing"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "manifest_unreadable"
    if (manifest_stat.st_size, manifest_stat.st_mtime_ns) != (after_stat.st_size, after_stat.st_mtime_ns):
        return None, "manifest_changed_during_read"
    if not isinstance(payload, dict):
        return None, "manifest_not_object"
    return payload, ""


class RawConversionValidator:
    def __init__(self, source_pdf_paths: Iterable[Path] | None = None) -> None:
        self._allowed_sources: dict[str, Path] | None
        self._allowed_by_name: dict[str, list[Path]] = {}
        if source_pdf_paths is None:
            self._allowed_sources = None
        else:
            self._allowed_sources = {}
            for source_pdf_path in source_pdf_paths:
                source_path = Path(source_pdf_path).expanduser().resolve(strict=False)
                key = _path_key(source_path)
                self._allowed_sources.setdefault(key, source_path)
            for source_path in self._allowed_sources.values():
                resolved_name = source_path.expanduser().resolve(strict=False).name.casefold()
                self._allowed_by_name.setdefault(resolved_name, []).append(source_path)
        self._source_fingerprints: dict[str, FileFingerprint | None] = {}

    def _source_fingerprint(self, source_path: Path) -> FileFingerprint | None:
        key = _path_key(source_path)
        cached = self._source_fingerprints.get(key)
        if cached is not None and metadata_still_matches(source_path, cached):
            return cached
        current = fingerprint_file(source_path, reject_symlink=False)
        self._source_fingerprints[key] = current
        return current

    def _source_for_manifest(
        self,
        payload: dict[str, object],
        schema_version: int,
        expected_size: int,
        expected_sha256: str,
    ) -> tuple[Path | None, FileFingerprint | None, str]:
        if schema_version >= 2:
            source_value = payload.get("source_pdf_path")
            if not isinstance(source_value, str) or not source_value.strip():
                return None, None, "source_path_missing"
            manifest_source = Path(source_value).expanduser()
            if not manifest_source.is_absolute():
                return None, None, "source_path_not_absolute"
            source_key = _path_key(manifest_source)
            if self._allowed_sources is not None:
                source_path = self._allowed_sources.get(source_key)
                if source_path is None:
                    return None, None, "source_not_requested"
            else:
                source_path = manifest_source
            source_fingerprint = self._source_fingerprint(source_path)
            if source_fingerprint is None:
                return source_path, None, "source_missing_empty_or_unstable"
            return source_path, source_fingerprint, ""

        if self._allowed_sources is None:
            return None, None, "legacy_manifest_requires_source_scope"
        source_name = payload.get("source_pdf_name")
        if not isinstance(source_name, str) or not source_name:
            return None, None, "source_name_missing"
        matches: list[tuple[Path, FileFingerprint]] = []
        for candidate in self._allowed_by_name.get(source_name.casefold(), []):
            candidate_fingerprint = self._source_fingerprint(candidate)
            if (
                candidate_fingerprint is not None
                and candidate_fingerprint.size == expected_size
                and candidate_fingerprint.sha256 == expected_sha256
            ):
                matches.append((candidate, candidate_fingerprint))
        if not matches:
            return None, None, "legacy_source_not_matched"
        if len(matches) != 1:
            return None, None, "legacy_source_ambiguous"
        return matches[0][0], matches[0][1], ""

    def validate(self, raw_stage_path: Path) -> RawConversionValidation:
        raw_path = Path(raw_stage_path)
        manifest_path = raw_conversion_manifest_path(raw_path)

        def invalid(reason: str, schema_version: int | None = None) -> RawConversionValidation:
            return RawConversionValidation(
                raw_stage_path=raw_path,
                manifest_path=manifest_path,
                valid=False,
                reason=reason,
                schema_version=schema_version,
            )

        try:
            raw_path = _validate_raw_stage_location(raw_path, require_file=True)
        except ValueError:
            return invalid("raw_stage_location_invalid")
        payload, load_reason = _load_raw_conversion_manifest(manifest_path)
        if payload is None:
            return invalid(load_reason)
        schema_value = payload.get("schema_version")
        if type(schema_value) is not int:
            return invalid("schema_version_invalid")
        schema_version = schema_value
        if schema_version not in RAW_CONVERSION_MANIFEST_SUPPORTED_SCHEMAS:
            return invalid("schema_version_unsupported", schema_version)
        if payload.get("status") != "completed":
            return invalid("status_not_completed", schema_version)
        if payload.get("raw_html_name") != RAW_STAGE_NAME:
            return invalid("raw_name_mismatch", schema_version)
        if schema_version >= 2 and payload.get("article_name") != raw_path.parent.parent.name:
            return invalid("article_name_mismatch", schema_version)

        source_size = _manifest_int(payload, "source_pdf_bytes")
        source_sha256 = _manifest_sha256(payload, "source_pdf_sha256")
        raw_size = _manifest_int(payload, "raw_html_bytes")
        raw_sha256 = _manifest_sha256(payload, "raw_html_sha256")
        if None in (source_size, source_sha256, raw_size, raw_sha256):
            return invalid("fingerprint_fields_invalid", schema_version)
        assert source_size is not None
        assert source_sha256 is not None
        assert raw_size is not None
        assert raw_sha256 is not None

        raw_fingerprint = fingerprint_file(
            raw_path,
            reject_symlink=True,
            capture_edges=True,
        )
        if raw_fingerprint is None:
            return invalid("raw_missing_empty_or_unstable", schema_version)
        if not artifact_is_structurally_valid(raw_path, raw_fingerprint):
            return invalid("raw_html_malformed", schema_version)
        if raw_fingerprint.size != raw_size or raw_fingerprint.sha256 != raw_sha256:
            return invalid("raw_fingerprint_mismatch", schema_version)

        source_path, source_fingerprint, source_reason = self._source_for_manifest(
            payload,
            schema_version,
            source_size,
            source_sha256,
        )
        if source_path is None or source_fingerprint is None:
            return invalid(source_reason, schema_version)
        if payload.get("source_pdf_name") != source_path.expanduser().resolve(strict=False).name:
            return invalid("source_name_mismatch", schema_version)
        if source_fingerprint.size != source_size or source_fingerprint.sha256 != source_sha256:
            return invalid("source_fingerprint_mismatch", schema_version)
        if not metadata_still_matches(source_path, source_fingerprint):
            return invalid("source_changed_during_validation", schema_version)
        if not metadata_still_matches(raw_path, raw_fingerprint):
            return invalid("raw_changed_during_validation", schema_version)
        return RawConversionValidation(
            raw_stage_path=raw_path,
            manifest_path=manifest_path,
            valid=True,
            reason="",
            source_pdf_path=source_path,
            schema_version=schema_version,
            source_pdf_bytes=source_fingerprint.size,
            source_pdf_sha256=source_fingerprint.sha256,
            raw_html_bytes=raw_fingerprint.size,
            raw_html_sha256=raw_fingerprint.sha256,
        )


def require_validated_raw_conversion_ownership(
    validations: Iterable[RawConversionValidation],
) -> list[RawConversionValidation]:
    validated = list(validations)
    invalid = [validation for validation in validated if not validation.valid]
    if invalid:
        details = "; ".join(
            f"{validation.raw_stage_path}: {validation.reason}"
            for validation in invalid[:20]
        )
        raise RuntimeError(
            "Raw conversion validation failed "
            f"(invalid={len(invalid)} total={len(validated)}): {details}"
        )

    article_owners: dict[str, Path] = {}
    source_owners: dict[str, Path] = {}
    conflicts: list[str] = []
    for validation in validated:
        article_key = _path_key(article_dir_from_html_stage(validation.raw_stage_path))
        previous_article = article_owners.setdefault(article_key, validation.raw_stage_path)
        if previous_article != validation.raw_stage_path:
            conflicts.append(
                f"article has multiple raw stages: {previous_article}, {validation.raw_stage_path}"
            )
        assert validation.source_pdf_path is not None
        source_key = _path_key(validation.source_pdf_path)
        previous_source = source_owners.setdefault(source_key, validation.raw_stage_path)
        if previous_source != validation.raw_stage_path:
            conflicts.append(
                f"source has multiple raw stages: {previous_source}, {validation.raw_stage_path}"
            )
    if conflicts:
        raise RuntimeError("Raw conversion ownership is ambiguous: " + "; ".join(conflicts[:20]))
    return validated


def require_current_raw_conversions(
    raw_stage_paths: Iterable[Path],
    *,
    source_pdf_paths: Iterable[Path] | None = None,
) -> list[RawConversionValidation]:
    source_scope = None if source_pdf_paths is None else tuple(Path(path) for path in source_pdf_paths)
    unique_paths = {
        _path_key(Path(raw_stage_path)): Path(raw_stage_path)
        for raw_stage_path in raw_stage_paths
    }
    validator = RawConversionValidator(source_scope)
    validations = [
        validator.validate(raw_path)
        for raw_path in sorted(unique_paths.values(), key=str)
    ]
    require_validated_raw_conversion_ownership(validations)
    if source_scope is not None:
        expected_sources = {_path_key(source_path): source_path for source_path in source_scope}
        actual_sources = {
            _path_key(validation.source_pdf_path)
            for validation in validations
            if validation.source_pdf_path is not None
        }
        missing_sources = [expected_sources[key] for key in expected_sources.keys() - actual_sources]
        if missing_sources:
            details = "; ".join(str(path) for path in sorted(missing_sources, key=str)[:20])
            raise RuntimeError(f"Requested source PDFs have no current raw conversion: {details}")
    return validations


def append_html_stage_log(stage_dir: Path, message: str) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    log_path = html_stage_log_path(stage_dir)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")
    return log_path


def save_html_stage(
    stage_dir: Path,
    filename: str,
    html: str,
    stage: str,
    *,
    source_path: Path | None = None,
    details: list[str] | tuple[str, ...] = (),
) -> HtmlStageSaveResult:
    """Write one HTML stage snapshot and append stage metadata to logs."""

    stage_dir.mkdir(parents=True, exist_ok=True)
    path = stage_dir / filename
    write_text_atomic(path, html)

    encoded_len = len(html.encode("utf-8"))
    source_text = f" source={source_path.name}" if source_path is not None else ""
    detail_text = "".join(f" {item}" for item in details if item)
    line = (
        f"stage={stage} file={filename} chars={len(html)} "
        f"bytes={encoded_len}{source_text}{detail_text}"
    )
    log_path = append_html_stage_log(stage_dir, line)
    write_text_atomic(path.with_suffix(".log"), line + "\n")

    return HtmlStageSaveResult(
        path=path,
        chars=len(html),
        bytes=encoded_len,
        log_path=log_path,
    )
