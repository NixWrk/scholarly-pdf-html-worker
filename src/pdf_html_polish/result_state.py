"""Fail-closed completion records for canonical conversion artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat

from .atomic_io import write_json_atomic


RESULT_MANIFEST_NAME = "_conversion_result_manifest.json"
RESULT_MANIFEST_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 64 * 1024
_ARTIFACT_EDGE_BYTES = 4 * 1024 * 1024
_HTML_OPEN_RE = re.compile(rb"<html(?:\s|>)", re.IGNORECASE)
_BODY_OPEN_RE = re.compile(rb"<body(?:\s|>)", re.IGNORECASE)
_BODY_CLOSE_RE = re.compile(rb"</body\s*>", re.IGNORECASE)
_HTML_CLOSE_RE = re.compile(rb"</html\s*>", re.IGNORECASE)


@dataclass(frozen=True)
class _Fingerprint:
    size: int
    mtime_ns: int
    sha256: str
    head: bytes = b""
    tail: bytes = b""


def result_manifest_path(artifact_path: Path) -> Path:
    return Path(artifact_path).parent / RESULT_MANIFEST_NAME


def _fingerprint(
    path: Path,
    *,
    reject_symlink: bool,
    capture_edges: bool = False,
) -> _Fingerprint | None:
    candidate = Path(path)
    try:
        if reject_symlink and candidate.is_symlink():
            return None
        before = candidate.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            return None
        digest = hashlib.sha256()
        head = bytearray()
        tail = bytearray()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                if capture_edges:
                    if len(head) < _ARTIFACT_EDGE_BYTES:
                        remaining = _ARTIFACT_EDGE_BYTES - len(head)
                        head.extend(chunk[:remaining])
                    tail.extend(chunk)
                    if len(tail) > _ARTIFACT_EDGE_BYTES:
                        del tail[: len(tail) - _ARTIFACT_EDGE_BYTES]
        after = candidate.stat()
    except OSError:
        return None
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        return None
    return _Fingerprint(
        size=int(after.st_size),
        mtime_ns=int(after.st_mtime_ns),
        sha256=digest.hexdigest(),
        head=bytes(head),
        tail=bytes(tail),
    )


def _metadata_still_matches(path: Path, fingerprint: _Fingerprint) -> bool:
    try:
        current = Path(path).stat()
    except OSError:
        return False
    return (int(current.st_size), int(current.st_mtime_ns)) == (
        fingerprint.size,
        fingerprint.mtime_ns,
    )


def _artifact_is_structurally_valid(path: Path, fingerprint: _Fingerprint) -> bool:
    if Path(path).suffix.lower() != ".html":
        return fingerprint.size > 0
    sample = fingerprint.head
    if fingerprint.size > len(fingerprint.head):
        sample += b"\n" + fingerprint.tail
    html_open = _HTML_OPEN_RE.search(sample)
    body_open = _BODY_OPEN_RE.search(sample)
    body_close = _BODY_CLOSE_RE.search(sample)
    html_close = _HTML_CLOSE_RE.search(sample)
    if None in (html_open, body_open, body_close, html_close):
        return False
    assert html_open is not None
    assert body_open is not None
    assert body_close is not None
    assert html_close is not None
    return html_open.start() < body_open.start() < body_close.start() < html_close.start()


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
    source_fingerprint = _fingerprint(source_pdf, reject_symlink=False)
    artifact_fingerprint = _fingerprint(
        artifact,
        reject_symlink=True,
        capture_edges=True,
    )
    if source_fingerprint is None:
        raise ValueError(f"Source PDF is not a stable non-empty file: {source_pdf}")
    if artifact_fingerprint is None or not _artifact_is_structurally_valid(
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
    if not _metadata_still_matches(source_pdf, source_fingerprint) or not _metadata_still_matches(
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

    source_fingerprint = _fingerprint(source_pdf, reject_symlink=False)
    artifact_fingerprint = _fingerprint(
        artifact,
        reject_symlink=True,
        capture_edges=True,
    )
    if source_fingerprint is None or artifact_fingerprint is None:
        return False
    if not _artifact_is_structurally_valid(artifact, artifact_fingerprint):
        return False
    fingerprints_match = (
        _manifest_int(payload, "source_pdf_bytes") == source_fingerprint.size
        and payload.get("source_pdf_sha256") == source_fingerprint.sha256
        and _manifest_int(payload, "artifact_bytes") == artifact_fingerprint.size
        and payload.get("artifact_sha256") == artifact_fingerprint.sha256
    )
    return (
        fingerprints_match
        and _metadata_still_matches(source_pdf, source_fingerprint)
        and _metadata_still_matches(artifact, artifact_fingerprint)
    )
