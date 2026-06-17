"""Zotero write and pending-queue adapters for the conversion pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .zotero_html_attachment import check_zotero_write_access
from .zotero_pending import retry_pending_attachments


def zotero_write_lock_detected(zotero_dir: Path) -> bool:
    """Return True only for the expected Zotero SQLite write-lock failure."""

    try:
        check_zotero_write_access(zotero_dir)
    except RuntimeError as exc:
        if "locked for writing" in str(exc).lower():
            return True
        raise
    return False


def retry_pending_zotero_exports(
    zotero_data_dir: str,
    output_dir: str,
    log: Callable[[str], None],
) -> None:
    summary = retry_pending_attachments(
        zotero_data_dir=zotero_data_dir,
        output_dir=output_dir,
        log=log,
    )
    log(
        "Pending retry summary: "
        f"attempted={summary.attempted}, "
        f"attached={summary.attached}, "
        f"kept_pending={summary.kept_pending}, "
        f"dropped_missing_html={summary.dropped_missing_html}, "
        f"failed_non_lock={summary.failed_non_lock}, "
        f"lock_blocked={summary.lock_blocked}"
    )
    log(f"Pending queue file: {summary.queue_path}")
