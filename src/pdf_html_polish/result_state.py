"""Fail-closed completion records for canonical conversion artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import stat

from .artifact_integrity import (
    artifact_is_structurally_valid,
    fingerprint_file,
    metadata_still_matches,
)
from .atomic_io import write_json_atomic


RESULT_MANIFEST_NAME = "_conversion_result_manifest.json"
RESULT_MANIFEST_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 64 * 1024
def result_manifest_path(artifact_path: Path) -> Path:
    return Path(artifact_path).parent / RESULT_MANIFEST_NAME


def _validate_artifact_location(artifact_path: Path) -> None:
    artifact = Path(artifact_path)
    article_dir = artifact.parent
    if article_dir.is_symlink() or artifact.is_symlink():
        raise ValueError(f"Canonical result path must not contain a symlink: {artifact}")
    if not article_dir.is_dir():
        raise ValueError(f"Canonical result article directory is missing: {article_dir}")
    expected_name = f"{article_dir.name}{artifact.suffix.lower()}"
    if artifact.name.casefold() != expected_name.casefold():
        raise ValueError(
            "Canonical result name must match its article directory: "
            f"expected={expected_name} actual={artifact.name}"
        )


def invalidate_completed_result(artifact_path: Path) -> None:
    artifact = Path(artifact_path)
    article_dir = artifact.parent
    if article_dir.is_symlink():
        raise ValueError(f"Refusing to invalidate a result through a symlink: {article_dir}")
    manifest_path = result_manifest_path(artifact)
    try:
        manifest_path.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Could not invalidate completed result: {manifest_path}") from exc


def publish_completed_result(
    *,
    source_pdf_path: Path,
    artifact_path: Path,
    result_kind: str,
) -> Path:
    source_pdf = Path(source_pdf_path)
    artifact = Path(artifact_path)
    invalidate_completed_result(artifact)
    _validate_artifact_location(artifact)
    source_fingerprint = fingerprint_file(source_pdf, reject_symlink=False)
    artifact_fingerprint = fingerprint_file(
        artifact,
        reject_symlink=True,
        capture_edges=True,
    )
    if source_fingerprint is None:
        raise ValueError(f"Source PDF is not a stable non-empty file: {source_pdf}")
    if artifact_fingerprint is None or not artifact_is_structurally_valid(
        artifact,
        artifact_fingerprint,
    ):
        raise ValueError(f"Canonical result is empty, malformed, or unstable: {artifact}")
    normalized_kind = str(result_kind or "").strip()
    if not normalized_kind:
        raise ValueError("Completed result kind must be non-empty.")

    payload = {
        "schema_version": RESULT_MANIFEST_SCHEMA_VERSION,
        "status": "completed",
        "result_kind": normalized_kind,
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_pdf_path": str(source_pdf.expanduser().resolve(strict=True)),
        "source_pdf_name": source_pdf.name,
        "source_pdf_bytes": source_fingerprint.size,
        "source_pdf_sha256": source_fingerprint.sha256,
        "artifact_name": artifact.name,
        "artifact_extension": artifact.suffix.lower(),
        "artifact_bytes": artifact_fingerprint.size,
        "artifact_sha256": artifact_fingerprint.sha256,
    }
    manifest_path = result_manifest_path(artifact)
    write_json_atomic(manifest_path, payload)
    if not metadata_still_matches(source_pdf, source_fingerprint) or not metadata_still_matches(
        artifact,
        artifact_fingerprint,
    ):
        invalidate_completed_result(artifact)
        raise RuntimeError("Source PDF or canonical result changed during completion publication.")
    return manifest_path


def _manifest_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    return value if type(value) is int and value >= 0 else None


def _load_manifest(path: Path) -> dict[str, object] | None:
    try:
        if path.is_symlink():
            return None
        manifest_stat = path.stat()
        if not stat.S_ISREG(manifest_stat.st_mode) or manifest_stat.st_size > _MAX_MANIFEST_BYTES:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def completed_result_is_current(source_pdf_path: Path, artifact_path: Path) -> bool:
    source_pdf = Path(source_pdf_path)
    artifact = Path(artifact_path)
    try:
        _validate_artifact_location(artifact)
    except ValueError:
        return False
    payload = _load_manifest(result_manifest_path(artifact))
    if payload is None:
        return False
    if payload.get("schema_version") != RESULT_MANIFEST_SCHEMA_VERSION:
        return False
    if payload.get("status") != "completed":
        return False
    if not isinstance(payload.get("result_kind"), str) or not payload["result_kind"]:
        return False
    if payload.get("source_pdf_name") != source_pdf.name:
        return False
    if payload.get("artifact_name") != artifact.name:
        return False
    if payload.get("artifact_extension") != artifact.suffix.lower():
        return False

    source_fingerprint = fingerprint_file(source_pdf, reject_symlink=False)
    artifact_fingerprint = fingerprint_file(
        artifact,
        reject_symlink=True,
        capture_edges=True,
    )
    if source_fingerprint is None or artifact_fingerprint is None:
        return False
    if not artifact_is_structurally_valid(artifact, artifact_fingerprint):
        return False
    fingerprints_match = (
        _manifest_int(payload, "source_pdf_bytes") == source_fingerprint.size
        and payload.get("source_pdf_sha256") == source_fingerprint.sha256
        and _manifest_int(payload, "artifact_bytes") == artifact_fingerprint.size
        and payload.get("artifact_sha256") == artifact_fingerprint.sha256
    )
    return (
        fingerprints_match
        and metadata_still_matches(source_pdf, source_fingerprint)
        and metadata_still_matches(artifact, artifact_fingerprint)
    )
