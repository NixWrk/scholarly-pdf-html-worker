from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .atomic_io import publish_directory_atomic, write_json_atomic, write_text_atomic
from .naming import make_unique_filename


_KEY_ALPHABET = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
_PENDING_MARKER_NAME = ".z2m-html-attachment-pending.json"
_PENDING_DIR_PREFIX = ".z2m-html-attachment-"
_PENDING_DIR_SUFFIX = ".pending"


@dataclass(frozen=True)
class AttachedHtmlResult:
    item_id: int
    item_key: str
    html_path: Path
    parent_item_id: int


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _next_id(conn: sqlite3.Connection, table: str, column: str) -> int:
    row = conn.execute(f"SELECT COALESCE(MAX({column}), 0) + 1 FROM {table}").fetchone()
    return int(row[0])


def _insert_row(conn: sqlite3.Connection, table: str, values: dict[str, object]) -> None:
    columns = _table_columns(conn, table)
    payload = {k: v for k, v in values.items() if k in columns}
    if not payload:
        raise RuntimeError(f"No compatible columns found for table {table}.")

    names = list(payload.keys())
    placeholders = ", ".join("?" for _ in names)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})",
        tuple(payload[name] for name in names),
    )


def _is_lock_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "database is locked" in msg
        or "database table is locked" in msg
        or "database is busy" in msg
    )


def _lookup_optional_int(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[object, ...],
) -> int | None:
    try:
        row = conn.execute(query, params).fetchone()
    except sqlite3.Error:
        return None
    if row is None or row[0] is None:
        return None
    return int(row[0])


def _attachment_item_type_id(conn: sqlite3.Connection) -> int:
    for query in (
        "SELECT itemTypeID FROM itemTypesCombined WHERE typeName = ?",
        "SELECT itemTypeID FROM itemTypes WHERE typeName = ?",
    ):
        value = _lookup_optional_int(conn, query, ("attachment",))
        if value is not None:
            return value
    return 14


def _imported_file_link_mode(conn: sqlite3.Connection) -> int:
    for query in (
        "SELECT linkModeID FROM itemAttachmentLinkModes WHERE linkMode = ?",
        "SELECT linkMode FROM itemAttachmentLinkModes WHERE linkModeName = ?",
    ):
        value = _lookup_optional_int(conn, query, ("imported_file",))
        if value is not None:
            return value
    return 1


def _library_id_for_parent(conn: sqlite3.Connection, parent_item_id: int) -> int | None:
    return _lookup_optional_int(conn, "SELECT libraryID FROM items WHERE itemID = ?", (parent_item_id,))


def _generate_unique_item_key(conn: sqlite3.Connection) -> str:
    while True:
        key = "".join(secrets.choice(_KEY_ALPHABET) for _ in range(8))
        exists = conn.execute("SELECT 1 FROM items WHERE key = ? LIMIT 1", (key,)).fetchone()
        if exists is None:
            return key


def _get_title_field_id(conn: sqlite3.Connection) -> int | None:
    for query in (
        "SELECT fieldID FROM fieldsCombined WHERE fieldName = ?",
        "SELECT fieldID FROM fields WHERE fieldName = ?",
    ):
        field_id = _lookup_optional_int(conn, query, ("title",))
        if field_id is not None:
            return field_id
    return None


def _upsert_item_data_value(conn: sqlite3.Connection, value: str) -> int:
    existing = _lookup_optional_int(conn, "SELECT valueID FROM itemDataValues WHERE value = ? LIMIT 1", (value,))
    if existing is not None:
        return existing
    value_id = _next_id(conn, "itemDataValues", "valueID")
    _insert_row(conn, "itemDataValues", {"valueID": value_id, "value": value})
    return value_id


def _try_set_attachment_title(conn: sqlite3.Connection, item_id: int, title: str) -> None:
    field_id = _get_title_field_id(conn)
    if field_id is None:
        return
    value_id = _upsert_item_data_value(conn, title)
    _insert_row(conn, "itemData", {"itemID": item_id, "fieldID": field_id, "valueID": value_id})


def _pending_attachment_paths(marker_path: Path) -> tuple[Path, Path] | None:
    storage_dir = marker_path.parent
    if storage_dir.is_symlink() or marker_path.is_symlink() or not marker_path.is_file():
        return None
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    schema_version = payload.get("schema_version")
    item_key = str(payload.get("item_key") or "")
    html_filename = str(payload.get("html_filename") or "")
    if (
        schema_version != 1
        or item_key != storage_dir.name
        or len(item_key) != 8
        or any(character not in _KEY_ALPHABET for character in item_key)
        or not html_filename
        or Path(html_filename).name != html_filename
    ):
        return None
    return storage_dir, storage_dir / html_filename


def _cleanup_pending_attachment(marker_path: Path, html_path: Path) -> None:
    storage_dir = marker_path.parent
    for path in (html_path, marker_path):
        if path.is_dir() and not path.is_symlink():
            raise RuntimeError(f"Refusing to remove unexpected pending attachment directory: {path}")
        path.unlink(missing_ok=True)
    try:
        storage_dir.rmdir()
    except OSError:
        # Preserve unknown files if anything else appeared in this Zotero directory.
        pass


def _private_pending_dir_owned(path: Path) -> bool:
    name = path.name
    if not name.startswith(_PENDING_DIR_PREFIX) or not name.endswith(_PENDING_DIR_SUFFIX):
        return False
    identity = name[len(_PENDING_DIR_PREFIX) : -len(_PENDING_DIR_SUFFIX)]
    item_key, separator, nonce = identity.partition("-")
    return (
        bool(separator)
        and len(item_key) == 8
        and all(character in _KEY_ALPHABET for character in item_key)
        and len(nonce) == 32
        and all(character in "0123456789abcdef" for character in nonce)
    )


def _cleanup_private_pending_dir(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or not _private_pending_dir_owned(path):
        raise RuntimeError(f"Refusing to remove untrusted pending attachment directory: {path}")
    children = list(path.iterdir())
    unexpected = [child for child in children if child.is_symlink() or not child.is_file()]
    if unexpected:
        raise RuntimeError(f"Refusing to remove pending attachment directory with unexpected entries: {unexpected}")
    for child in children:
        child.unlink()
    path.rmdir()


def _recover_pending_html_attachments(conn: sqlite3.Connection, zotero_data_dir: Path) -> None:
    storage_root = zotero_data_dir / "storage"
    if storage_root.is_symlink():
        raise RuntimeError(f"Refusing symlinked Zotero storage root: {storage_root}")
    if not storage_root.is_dir():
        return
    for pending_dir in storage_root.glob(f"{_PENDING_DIR_PREFIX}*{_PENDING_DIR_SUFFIX}"):
        if _private_pending_dir_owned(pending_dir):
            _cleanup_private_pending_dir(pending_dir)
    for marker_path in storage_root.glob(f"*/{_PENDING_MARKER_NAME}"):
        pending = _pending_attachment_paths(marker_path)
        if pending is None:
            continue
        storage_dir, html_path = pending
        if storage_dir.parent != storage_root:
            continue
        item_key = storage_dir.name
        committed = conn.execute("SELECT 1 FROM items WHERE key = ? LIMIT 1", (item_key,)).fetchone()
        if committed is not None:
            if html_path.is_symlink() or not html_path.is_file():
                raise RuntimeError(
                    "Committed Zotero HTML attachment is missing its regular storage file: "
                    f"key={item_key} path={html_path}"
                )
            marker_path.unlink(missing_ok=True)
            continue
        _cleanup_pending_attachment(marker_path, html_path)


def _write_pending_marker(marker_path: Path, item_key: str, html_filename: str) -> None:
    write_json_atomic(
        marker_path,
        {
            "schema_version": 1,
            "item_key": item_key,
            "html_filename": html_filename,
        },
    )


def attach_single_file_html(
    zotero_data_dir: Path,
    parent_item_id: int,
    source_pdf_path: Path,
    html_content: str,
) -> AttachedHtmlResult:
    db_path = zotero_data_dir / "zotero.sqlite"
    if not db_path.is_file():
        raise FileNotFoundError(f"zotero.sqlite not found: {db_path}")

    conn = sqlite3.connect(db_path, timeout=2.0)
    conn.row_factory = sqlite3.Row
    pending_marker_path: Path | None = None
    pending_html_path: Path | None = None
    private_pending_dir: Path | None = None
    transaction_committed = False

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        _recover_pending_html_attachments(conn, zotero_data_dir)

        parent_exists = conn.execute("SELECT 1 FROM items WHERE itemID = ? LIMIT 1", (parent_item_id,)).fetchone()
        if parent_exists is None:
            raise RuntimeError(f"Parent item not found in Zotero DB: itemID={parent_item_id}")

        item_id = _next_id(conn, "items", "itemID")
        storage_root = zotero_data_dir / "storage"
        if storage_root.is_symlink():
            raise RuntimeError(f"Refusing symlinked Zotero storage root: {storage_root}")
        storage_root.mkdir(parents=True, exist_ok=True)
        for _attempt in range(128):
            item_key = _generate_unique_item_key(conn)
            storage_dir = storage_root / item_key
            if not storage_dir.exists() and not storage_dir.is_symlink():
                break
        else:
            raise RuntimeError("Unable to allocate a Zotero attachment key unused by DB and storage.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        library_id = _library_id_for_parent(conn, parent_item_id)
        _insert_row(
            conn,
            "items",
            {
                "itemID": item_id,
                "itemTypeID": _attachment_item_type_id(conn),
                "dateAdded": now,
                "dateModified": now,
                "libraryID": library_id,
                "key": item_key,
                "version": 0,
                "synced": 0,
            },
        )

        private_pending_dir = storage_root / (
            f"{_PENDING_DIR_PREFIX}{item_key}-{uuid4().hex}{_PENDING_DIR_SUFFIX}"
        )
        private_pending_dir.mkdir(exist_ok=False)
        html_filename = make_unique_filename(f"{source_pdf_path.stem}_marker", ".html", set(), max_stem_len=120)
        pending_marker_path = private_pending_dir / _PENDING_MARKER_NAME
        pending_html_path = private_pending_dir / html_filename
        _write_pending_marker(pending_marker_path, item_key, html_filename)
        write_text_atomic(pending_html_path, html_content)
        publish_directory_atomic(private_pending_dir, storage_dir)
        private_pending_dir = None
        pending_marker_path = storage_dir / _PENDING_MARKER_NAME
        pending_html_path = storage_dir / html_filename
        html_path = pending_html_path
        mod_time_ms = int(html_path.stat().st_mtime * 1000)

        _insert_row(
            conn,
            "itemAttachments",
            {
                "itemID": item_id,
                "parentItemID": parent_item_id,
                "linkMode": _imported_file_link_mode(conn),
                "contentType": "text/html",
                "path": f"storage:{html_filename}",
                "syncState": 0,
                "storageModTime": mod_time_ms,
                "lastProcessedModificationTime": mod_time_ms,
            },
        )

        try:
            _try_set_attachment_title(conn, item_id, f"{source_pdf_path.stem} (Marker HTML)")
        except sqlite3.Error:
            # Title is optional. Attachment remains valid without explicit itemData row.
            pass

        conn.commit()
        transaction_committed = True
        try:
            pending_marker_path.unlink(missing_ok=True)
        except OSError:
            # A later attachment call reconciles a marker left after a committed DB row.
            pass
        return AttachedHtmlResult(
            item_id=item_id,
            item_key=item_key,
            html_path=html_path,
            parent_item_id=parent_item_id,
        )
    except sqlite3.OperationalError as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        if _is_lock_error(exc):
            raise RuntimeError(
                "Zotero database is locked for writing. Close Zotero and retry Zotero export mode."
            ) from exc
        raise
    except Exception:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise
    finally:
        if not transaction_committed and private_pending_dir is not None and private_pending_dir.exists():
            _cleanup_private_pending_dir(private_pending_dir)
        elif not transaction_committed and pending_marker_path is not None and pending_html_path is not None:
            _cleanup_pending_attachment(pending_marker_path, pending_html_path)
        conn.close()


def check_zotero_write_access(zotero_data_dir: Path) -> None:
    db_path = zotero_data_dir / "zotero.sqlite"
    if not db_path.is_file():
        raise FileNotFoundError(f"zotero.sqlite not found: {db_path}")

    conn = sqlite3.connect(db_path, timeout=2.0)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()
    except sqlite3.OperationalError as exc:
        if _is_lock_error(exc):
            raise RuntimeError(
                "Zotero database is locked for writing. Close Zotero and retry Zotero export mode."
            ) from exc
        raise
    finally:
        conn.close()
