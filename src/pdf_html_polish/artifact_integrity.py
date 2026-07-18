"""Stable fingerprints and structural checks for durable pipeline artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import stat


ARTIFACT_EDGE_BYTES = 4 * 1024 * 1024
_HTML_OPEN_RE = re.compile(rb"<html(?:\s|>)", re.IGNORECASE)
_BODY_OPEN_RE = re.compile(rb"<body(?:\s|>)", re.IGNORECASE)
_BODY_CLOSE_RE = re.compile(rb"</body\s*>", re.IGNORECASE)
_HTML_CLOSE_RE = re.compile(rb"</html\s*>", re.IGNORECASE)


@dataclass(frozen=True)
class FileFingerprint:
    size: int
    mtime_ns: int
    sha256: str
    head: bytes = b""
    tail: bytes = b""


def fingerprint_file(
    path: Path,
    *,
    reject_symlink: bool,
    capture_edges: bool = False,
) -> FileFingerprint | None:
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
                    if len(head) < ARTIFACT_EDGE_BYTES:
                        remaining = ARTIFACT_EDGE_BYTES - len(head)
                        head.extend(chunk[:remaining])
                    tail.extend(chunk)
                    if len(tail) > ARTIFACT_EDGE_BYTES:
                        del tail[: len(tail) - ARTIFACT_EDGE_BYTES]
        after = candidate.stat()
    except OSError:
        return None
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        return None
    return FileFingerprint(
        size=int(after.st_size),
        mtime_ns=int(after.st_mtime_ns),
        sha256=digest.hexdigest(),
        head=bytes(head),
        tail=bytes(tail),
    )


def read_bytes_with_fingerprint(
    path: Path,
    *,
    reject_symlink: bool,
) -> tuple[bytes, FileFingerprint] | None:
    """Read one stable file snapshot and fingerprint the exact returned bytes."""

    candidate = Path(path)
    try:
        if reject_symlink and candidate.is_symlink():
            return None
        before = candidate.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            return None
        digest = hashlib.sha256()
        content = bytearray()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                content.extend(chunk)
        after = candidate.stat()
    except OSError:
        return None
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        return None
    data = bytes(content)
    return data, FileFingerprint(
        size=int(after.st_size),
        mtime_ns=int(after.st_mtime_ns),
        sha256=digest.hexdigest(),
        head=data[:ARTIFACT_EDGE_BYTES],
        tail=data[-ARTIFACT_EDGE_BYTES:],
    )


def metadata_still_matches(path: Path, fingerprint: FileFingerprint) -> bool:
    try:
        current = Path(path).stat()
    except OSError:
        return False
    return (int(current.st_size), int(current.st_mtime_ns)) == (
        fingerprint.size,
        fingerprint.mtime_ns,
    )


def artifact_is_structurally_valid(path: Path, fingerprint: FileFingerprint) -> bool:
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
