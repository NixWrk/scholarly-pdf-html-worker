"""WebDAV mirror adapter used by the conversion pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .webdav_config import DEFAULT_CONFIG_PATH
from .webdav_pending import WebDavUploadSummary, retry_pending_webdav_uploads, upload_webdav_with_pending


def resolve_webdav_config_path(webdav_config_path: str | None) -> Path:
    if webdav_config_path:
        return Path(webdav_config_path).expanduser().resolve(strict=False)
    return DEFAULT_CONFIG_PATH


def upload_webdav_mirror_if_configured(
    *,
    file_path: Path,
    output_dir: Path,
    upload_enabled: bool,
    webdav_config_path: str | None = None,
    log: Callable[[str], None] | None = None,
) -> WebDavUploadSummary:
    """Upload ``file_path`` to enabled WebDAV mirrors without breaking conversion."""

    queue_path = output_dir / "_webdav_pending_uploads.json"
    if not upload_enabled:
        return WebDavUploadSummary(
            uploaded=0,
            failed=0,
            queued=0,
            pending_total=0,
            queue_path=queue_path,
        )

    try:
        return upload_webdav_with_pending(
            file_path=file_path,
            output_dir=output_dir,
            config_path=resolve_webdav_config_path(webdav_config_path),
            log=log,
        )
    except Exception as exc:  # noqa: BLE001 - WebDAV mirror must not break conversion
        if log is not None:
            log(f"WebDAV upload error: {exc}")
        return WebDavUploadSummary(
            uploaded=0,
            failed=1,
            queued=0,
            pending_total=0,
            queue_path=queue_path,
        )


def retry_pending_webdav_exports(
    output_dir: str,
    webdav_config_path: str | None,
    log: Callable[[str], None],
) -> None:
    summary = retry_pending_webdav_uploads(
        output_dir=output_dir,
        config_path=resolve_webdav_config_path(webdav_config_path),
        log=log,
    )
    log(
        "Pending WebDAV retry summary: "
        f"attempted={summary.attempted}, "
        f"uploaded={summary.uploaded}, "
        f"kept_pending={summary.kept_pending}, "
        f"dropped_missing_local={summary.dropped_missing_local}, "
        f"server_missing={summary.server_missing}, "
        f"failed={summary.failed}"
    )
    log(f"Pending WebDAV queue file: {summary.queue_path}")
