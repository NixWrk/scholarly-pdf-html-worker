from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from pdf_html_polish import atomic_io
from pdf_html_polish import zotero_html_attachment as attachment_module


def _create_zotero_data(tmp_path: Path) -> Path:
    zotero_data_dir = tmp_path / "zotero"
    (zotero_data_dir / "storage").mkdir(parents=True)
    conn = sqlite3.connect(zotero_data_dir / "zotero.sqlite")
    try:
        conn.executescript(
            """
            CREATE TABLE items (
                itemID INTEGER PRIMARY KEY,
                itemTypeID INTEGER,
                dateAdded TEXT,
                dateModified TEXT,
                libraryID INTEGER,
                key TEXT UNIQUE,
                version INTEGER,
                synced INTEGER
            );
            CREATE TABLE itemAttachments (
                itemID INTEGER PRIMARY KEY,
                parentItemID INTEGER,
                linkMode INTEGER,
                contentType TEXT,
                path TEXT,
                syncState INTEGER,
                storageModTime INTEGER,
                lastProcessedModificationTime INTEGER
            );
            CREATE TABLE itemTypesCombined (itemTypeID INTEGER, typeName TEXT);
            CREATE TABLE itemAttachmentLinkModes (linkModeID INTEGER, linkMode TEXT);
            """
        )
        conn.execute(
            "INSERT INTO items "
            "(itemID, itemTypeID, dateAdded, dateModified, libraryID, key, version, synced) "
            "VALUES (1, 2, '', '', 7, 'PARENT22', 1, 1)"
        )
        conn.execute("INSERT INTO itemTypesCombined VALUES (14, 'attachment')")
        conn.execute("INSERT INTO itemAttachmentLinkModes VALUES (1, 'imported_file')")
        conn.commit()
    finally:
        conn.close()
    return zotero_data_dir


def _database_counts(zotero_data_dir: Path) -> tuple[int, int]:
    conn = sqlite3.connect(zotero_data_dir / "zotero.sqlite")
    try:
        return (
            int(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM itemAttachments").fetchone()[0]),
        )
    finally:
        conn.close()


def _write_pending_marker(storage_dir: Path, html_filename: str) -> Path:
    marker_path = storage_dir / attachment_module._PENDING_MARKER_NAME
    marker_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "item_key": storage_dir.name,
                "html_filename": html_filename,
            }
        ),
        encoding="utf-8",
    )
    return marker_path


def test_attach_single_file_html_commits_complete_storage_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = _create_zotero_data(tmp_path)
    monkeypatch.setattr(attachment_module, "_generate_unique_item_key", lambda _conn: "ATTACH22")

    result = attachment_module.attach_single_file_html(
        zotero_data_dir,
        parent_item_id=1,
        source_pdf_path=tmp_path / "paper.pdf",
        html_content="<html><body>complete</body></html>",
    )

    assert result.item_key == "ATTACH22"
    assert result.html_path.read_text(encoding="utf-8") == "<html><body>complete</body></html>"
    assert not (result.html_path.parent / attachment_module._PENDING_MARKER_NAME).exists()
    assert _database_counts(zotero_data_dir) == (2, 1)
    conn = sqlite3.connect(zotero_data_dir / "zotero.sqlite")
    try:
        row = conn.execute("SELECT parentItemID, path FROM itemAttachments").fetchone()
    finally:
        conn.close()
    assert row == (1, f"storage:{result.html_path.name}")


def test_attach_single_file_html_rolls_back_when_atomic_html_publication_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = _create_zotero_data(tmp_path)
    monkeypatch.setattr(attachment_module, "_generate_unique_item_key", lambda _conn: "FAILHTML")
    real_replace = atomic_io.os.replace

    def fail_html_replace(temporary: Path, target: Path) -> None:
        if Path(target).suffix == ".html":
            raise OSError("simulated HTML publication failure")
        real_replace(temporary, target)

    monkeypatch.setattr(atomic_io.os, "replace", fail_html_replace)

    with pytest.raises(OSError, match="simulated HTML publication failure"):
        attachment_module.attach_single_file_html(
            zotero_data_dir,
            parent_item_id=1,
            source_pdf_path=tmp_path / "paper.pdf",
            html_content="<html>new</html>",
        )

    assert _database_counts(zotero_data_dir) == (1, 0)
    assert not (zotero_data_dir / "storage" / "FAILHTML").exists()


def test_attach_single_file_html_removes_storage_after_database_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = _create_zotero_data(tmp_path)
    monkeypatch.setattr(attachment_module, "_generate_unique_item_key", lambda _conn: "FAILDB22")
    real_insert_row = attachment_module._insert_row

    def fail_attachment_row(conn: sqlite3.Connection, table: str, values: dict[str, object]) -> None:
        if table == "itemAttachments":
            raise sqlite3.IntegrityError("simulated attachment row failure")
        real_insert_row(conn, table, values)

    monkeypatch.setattr(attachment_module, "_insert_row", fail_attachment_row)

    with pytest.raises(sqlite3.IntegrityError, match="simulated attachment row failure"):
        attachment_module.attach_single_file_html(
            zotero_data_dir,
            parent_item_id=1,
            source_pdf_path=tmp_path / "paper.pdf",
            html_content="<html>new</html>",
        )

    assert _database_counts(zotero_data_dir) == (1, 0)
    assert not (zotero_data_dir / "storage" / "FAILDB22").exists()


def test_attach_single_file_html_recovers_interrupted_markers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = _create_zotero_data(tmp_path)
    private_pending_dir = (
        zotero_data_dir / "storage" / ".z2m-html-attachment-STAGED22-0123456789abcdef0123456789abcdef.pending"
    )
    private_pending_dir.mkdir()
    (private_pending_dir / ".partial.tmp").write_text("partial", encoding="utf-8")

    orphan_dir = zotero_data_dir / "storage" / "RPHAN222"
    orphan_dir.mkdir()
    (orphan_dir / "orphan.html").write_text("orphan", encoding="utf-8")
    _write_pending_marker(orphan_dir, "orphan.html")

    committed_dir = zotero_data_dir / "storage" / "CMMIT222"
    committed_dir.mkdir()
    committed_html = committed_dir / "committed.html"
    committed_html.write_text("committed", encoding="utf-8")
    committed_marker = _write_pending_marker(committed_dir, committed_html.name)
    conn = sqlite3.connect(zotero_data_dir / "zotero.sqlite")
    try:
        conn.execute(
            "INSERT INTO items "
            "(itemID, itemTypeID, dateAdded, dateModified, libraryID, key, version, synced) "
            "VALUES (2, 14, '', '', 7, 'CMMIT222', 0, 0)"
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(attachment_module, "_generate_unique_item_key", lambda _conn: "NEWITEM2")
    attachment_module.attach_single_file_html(
        zotero_data_dir,
        parent_item_id=1,
        source_pdf_path=tmp_path / "paper.pdf",
        html_content="<html>new</html>",
    )

    assert not private_pending_dir.exists()
    assert not orphan_dir.exists()
    assert committed_html.read_text(encoding="utf-8") == "committed"
    assert not committed_marker.exists()


def test_attach_single_file_html_skips_key_with_existing_storage_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = _create_zotero_data(tmp_path)
    collision_dir = zotero_data_dir / "storage" / "CLLIDE22"
    collision_dir.mkdir()
    sentinel = collision_dir / "existing.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    keys = iter(("CLLIDE22", "UNUSED22"))
    monkeypatch.setattr(attachment_module, "_generate_unique_item_key", lambda _conn: next(keys))

    result = attachment_module.attach_single_file_html(
        zotero_data_dir,
        parent_item_id=1,
        source_pdf_path=tmp_path / "paper.pdf",
        html_content="<html>new</html>",
    )

    assert result.item_key == "UNUSED22"
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_attach_single_file_html_fails_closed_for_committed_marker_without_html(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = _create_zotero_data(tmp_path)
    broken_dir = zotero_data_dir / "storage" / "BRKEN222"
    broken_dir.mkdir()
    marker_path = _write_pending_marker(broken_dir, "missing.html")
    conn = sqlite3.connect(zotero_data_dir / "zotero.sqlite")
    try:
        conn.execute(
            "INSERT INTO items "
            "(itemID, itemTypeID, dateAdded, dateModified, libraryID, key, version, synced) "
            "VALUES (2, 14, '', '', 7, 'BRKEN222', 0, 0)"
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(attachment_module, "_generate_unique_item_key", lambda _conn: "UNUSED22")

    with pytest.raises(RuntimeError, match="missing its regular storage file"):
        attachment_module.attach_single_file_html(
            zotero_data_dir,
            parent_item_id=1,
            source_pdf_path=tmp_path / "paper.pdf",
            html_content="<html>new</html>",
        )

    assert marker_path.is_file()
    assert _database_counts(zotero_data_dir) == (2, 0)
