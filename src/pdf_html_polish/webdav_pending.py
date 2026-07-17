from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .atomic_io import write_json_atomic
from .webdav_config import DEFAULT_CONFIG_PATH, WebDavConfig, WebDavServer


PENDING_WEBDAV_UPLOADS_FILE = "_webdav_pending_uploads.json"


@dataclass(frozen=True)
class PendingWebDavUpload:
    local_path: str
    remote_relative: str
    server_key: str
    server_name: str
    queued_at_utc: str
    attempts: int = 0
    last_error: str | None = None


@dataclass(frozen=True)
class WebDavUploadSummary:
    uploaded: int
    failed: int
    queued: int
    pending_total: int
    queue_path: Path


@dataclass(frozen=True)
class WebDavRetrySummary:
    attempted: int
    uploaded: int
    kept_pending: int
    dropped_missing_local: int
    server_missing: int
    failed: int
    queue_path: Path


def webdav_server_key(server: WebDavServer) -> str:
    """Stable-enough identity for pending uploads without storing secrets."""
    return "||".join(
        (
            server.url.strip().rstrip("/"),
            server.remote_root.strip().strip("/"),
            server.username.strip(),
        )
    )


def _norm_path(value: str | Path) -> str:
    return os.path.normcase(str(Path(value).expanduser().resolve(strict=False)))


def _queue_path(output_dir: Path) -> Path:
    return output_dir / PENDING_WEBDAV_UPLOADS_FILE


def _remote_relative_for(local_path: Path, output_dir: Path) -> str:
    local = Path(local_path).expanduser().resolve(strict=False)
    out_dir = Path(output_dir).expanduser().resolve(strict=False)
    try:
        return local.relative_to(out_dir).as_posix()
    except ValueError:
        return local.name


def load_pending_webdav_uploads(output_dir: str | Path) -> list[PendingWebDavUpload]:
    path = _queue_path(Path(output_dir).expanduser().resolve(strict=False))
    if not path.is_file():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(raw, list):
        return []

    out: list[PendingWebDavUpload] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        local_path = str(row.get("local_path", "")).strip()
        remote_relative = str(row.get("remote_relative", "")).strip()
        server_key = str(row.get("server_key", "")).strip()
        server_name = str(row.get("server_name", "")).strip()
        queued_at = str(row.get("queued_at_utc", "")).strip()
        if not local_path or not remote_relative or not server_key or not queued_at:
            continue
        try:
            attempts = int(row.get("attempts", 0))
        except Exception:
            attempts = 0
        last_error = row.get("last_error")
        out.append(
            PendingWebDavUpload(
                local_path=local_path,
                remote_relative=remote_relative,
                server_key=server_key,
                server_name=server_name,
                queued_at_utc=queued_at,
                attempts=max(0, attempts),
                last_error=None if last_error is None else str(last_error),
            )
        )
    return out


def save_pending_webdav_uploads(
    output_dir: str | Path,
    entries: list[PendingWebDavUpload],
) -> Path:
    out_dir = Path(output_dir).expanduser().resolve(strict=False)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _queue_path(out_dir)
    if not entries:
        if path.exists():
            path.unlink()
        return path

    payload = [
        {
            "local_path": e.local_path,
            "remote_relative": e.remote_relative,
            "server_key": e.server_key,
            "server_name": e.server_name,
            "queued_at_utc": e.queued_at_utc,
            "attempts": e.attempts,
            "last_error": e.last_error,
        }
        for e in entries
    ]
    write_json_atomic(path, payload)
    return path


def build_pending_webdav_upload(
    local_path: str | Path,
    output_dir: str | Path,
    server: WebDavServer,
    *,
    remote_relative: str | None = None,
    attempts: int = 0,
    last_error: str | None = None,
) -> PendingWebDavUpload:
    local = Path(local_path).expanduser().resolve(strict=False)
    relative = remote_relative or _remote_relative_for(local, Path(output_dir))
    return PendingWebDavUpload(
        local_path=str(local),
        remote_relative=relative.replace("\\", "/").lstrip("/"),
        server_key=webdav_server_key(server),
        server_name=server.name or server.url,
        queued_at_utc=datetime.now(timezone.utc).isoformat(),
        attempts=attempts,
        last_error=last_error,
    )


def enqueue_pending_webdav_uploads(
    output_dir: str | Path,
    entries: list[PendingWebDavUpload],
) -> tuple[int, int]:
    existing = load_pending_webdav_uploads(output_dir)
    merged: dict[str, PendingWebDavUpload] = {}

    for row in existing:
        key = f"{row.server_key}||{_norm_path(row.local_path)}||{row.remote_relative}"
        merged[key] = row

    added = 0
    for row in entries:
        key = f"{row.server_key}||{_norm_path(row.local_path)}||{row.remote_relative}"
        if key not in merged:
            merged[key] = row
            added += 1
            continue

        prev = merged[key]
        earliest = prev.queued_at_utc if prev.queued_at_utc <= row.queued_at_utc else row.queued_at_utc
        merged[key] = PendingWebDavUpload(
            local_path=prev.local_path,
            remote_relative=prev.remote_relative,
            server_key=prev.server_key,
            server_name=prev.server_name,
            queued_at_utc=earliest,
            attempts=max(prev.attempts, row.attempts),
            last_error=row.last_error or prev.last_error,
        )

    ordered = sorted(
        merged.values(),
        key=lambda e: (e.queued_at_utc, e.server_name.lower(), _norm_path(e.local_path)),
    )
    save_pending_webdav_uploads(output_dir, ordered)
    return added, len(ordered)


def upload_webdav_with_pending(
    file_path: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    log: Callable[[str], None] | None = None,
    uploader: object | None = None,
) -> WebDavUploadSummary:
    out_dir = Path(output_dir).expanduser().resolve(strict=False)
    queue_path = _queue_path(out_dir)
    config = WebDavConfig.load(Path(config_path))
    servers = config.get_enabled_servers()
    if not servers:
        return WebDavUploadSummary(
            uploaded=0,
            failed=0,
            queued=0,
            pending_total=len(load_pending_webdav_uploads(out_dir)),
            queue_path=queue_path,
        )

    def emit(message: str) -> None:
        if log is not None:
            log(message)

    if uploader is None:
        try:
            from .webdav_uploader import WebDavUploader

            uploader = WebDavUploader()
        except Exception as exc:
            entries = [
                build_pending_webdav_upload(
                    file_path,
                    out_dir,
                    server,
                    last_error=f"WebDAV uploader unavailable: {exc}",
                )
                for server in servers
            ]
            _, total = enqueue_pending_webdav_uploads(out_dir, entries)
            emit(f"WebDAV upload unavailable; queued={len(entries)}, pending_total={total}")
            return WebDavUploadSummary(
                uploaded=0,
                failed=len(entries),
                queued=len(entries),
                pending_total=total,
                queue_path=queue_path,
            )

    local = Path(file_path).expanduser().resolve(strict=False)
    relative = _remote_relative_for(local, out_dir)
    uploaded = 0
    failed = 0
    pending_entries: list[PendingWebDavUpload] = []

    for server in servers:
        try:
            ok, msg = uploader.upload_file(server, local, relative)  # type: ignore[attr-defined]
        except Exception as exc:
            ok = False
            msg = str(exc)

        if ok:
            uploaded += 1
            emit(f"WebDAV upload: {server.name or server.url} <- {local.name}")
            continue

        failed += 1
        emit(f"WebDAV upload failed: {server.name or server.url}: {msg}")
        pending_entries.append(
            build_pending_webdav_upload(
                local,
                out_dir,
                server,
                remote_relative=relative,
                last_error=msg,
            )
        )

    pending_total = len(load_pending_webdav_uploads(out_dir))
    if pending_entries:
        _, pending_total = enqueue_pending_webdav_uploads(out_dir, pending_entries)
        emit(
            "Queued pending WebDAV uploads: "
            f"queued_now={len(pending_entries)}, pending_total={pending_total}"
        )

    return WebDavUploadSummary(
        uploaded=uploaded,
        failed=failed,
        queued=len(pending_entries),
        pending_total=pending_total,
        queue_path=queue_path,
    )


def retry_pending_webdav_uploads(
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    log: Callable[[str], None] | None = None,
    uploader: object | None = None,
) -> WebDavRetrySummary:
    out_dir = Path(output_dir).expanduser().resolve(strict=False)
    queue_path = _queue_path(out_dir)
    pending = load_pending_webdav_uploads(out_dir)
    if not pending:
        return WebDavRetrySummary(
            attempted=0,
            uploaded=0,
            kept_pending=0,
            dropped_missing_local=0,
            server_missing=0,
            failed=0,
            queue_path=queue_path,
        )

    def emit(message: str) -> None:
        if log is not None:
            log(message)

    config = WebDavConfig.load(Path(config_path))
    servers = {webdav_server_key(server): server for server in config.get_enabled_servers()}

    if uploader is None:
        try:
            from .webdav_uploader import WebDavUploader

            uploader = WebDavUploader()
        except Exception as exc:
            unavailable_remaining = [
                PendingWebDavUpload(
                    local_path=row.local_path,
                    remote_relative=row.remote_relative,
                    server_key=row.server_key,
                    server_name=row.server_name,
                    queued_at_utc=row.queued_at_utc,
                    attempts=row.attempts,
                    last_error=f"WebDAV uploader unavailable: {exc}",
                )
                for row in pending
            ]
            save_pending_webdav_uploads(out_dir, unavailable_remaining)
            emit(f"Pending WebDAV retry unavailable: {exc}")
            return WebDavRetrySummary(
                attempted=0,
                uploaded=0,
                kept_pending=len(unavailable_remaining),
                dropped_missing_local=0,
                server_missing=0,
                failed=len(unavailable_remaining),
                queue_path=queue_path,
            )

    remaining: list[PendingWebDavUpload] = []
    attempted = 0
    uploaded = 0
    dropped_missing_local = 0
    server_missing = 0
    failed = 0

    for row in pending:
        local = Path(row.local_path).expanduser().resolve(strict=False)
        if not local.is_file():
            dropped_missing_local += 1
            emit(f"Pending WebDAV dropped (local file missing): {local}")
            continue

        server = servers.get(row.server_key)
        if server is None:
            server_missing += 1
            remaining.append(
                PendingWebDavUpload(
                    local_path=row.local_path,
                    remote_relative=row.remote_relative,
                    server_key=row.server_key,
                    server_name=row.server_name,
                    queued_at_utc=row.queued_at_utc,
                    attempts=row.attempts,
                    last_error="Server is disabled or missing from WebDAV config.",
                )
            )
            emit(f"Pending WebDAV kept (server missing): {row.server_name}")
            continue

        attempted += 1
        try:
            ok, msg = uploader.upload_file(server, local, row.remote_relative)  # type: ignore[attr-defined]
        except Exception as exc:
            ok = False
            msg = str(exc)

        if ok:
            uploaded += 1
            emit(f"Pending WebDAV uploaded: {server.name or server.url} <- {local.name}")
            continue

        failed += 1
        remaining.append(
            PendingWebDavUpload(
                local_path=row.local_path,
                remote_relative=row.remote_relative,
                server_key=row.server_key,
                server_name=row.server_name,
                queued_at_utc=row.queued_at_utc,
                attempts=row.attempts + 1,
                last_error=msg,
            )
        )
        emit(f"Pending WebDAV upload failed: {server.name or server.url}: {msg}")

    save_pending_webdav_uploads(out_dir, remaining)
    return WebDavRetrySummary(
        attempted=attempted,
        uploaded=uploaded,
        kept_pending=len(remaining),
        dropped_missing_local=dropped_missing_local,
        server_missing=server_missing,
        failed=failed,
        queue_path=queue_path,
    )
