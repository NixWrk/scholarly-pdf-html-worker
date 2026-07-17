from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3
from typing import Any

import pytest

from pdf_html_polish.zotero import ZoteroRepository


def _create_database(zotero_data_dir: Path) -> Path:
    zotero_data_dir.mkdir(parents=True)
    db_path = zotero_data_dir / "zotero.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE records (value TEXT)")
        conn.execute("INSERT INTO records VALUES ('base')")
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_snapshot_online_backup_includes_committed_wal_and_excludes_uncommitted_row(tmp_path: Path) -> None:
    zotero_data_dir = tmp_path / "zotero"
    db_path = _create_database(zotero_data_dir)
    writer = sqlite3.connect(db_path)
    snapshot_conn: sqlite3.Connection | None = None
    snapshot_dir: Path | None = None
    try:
        journal_mode = str(writer.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
        if journal_mode != "wal":
            pytest.skip("SQLite WAL mode is unavailable on this filesystem")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("INSERT INTO records VALUES ('wal-committed')")
        writer.commit()
        assert Path(f"{db_path}-wal").is_file()
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("INSERT INTO records VALUES ('uncommitted')")

        repository = ZoteroRepository(zotero_data_dir, snapshot_temp_root=tmp_path / "snapshots")
        snapshot_conn, snapshot_dir = repository._connect_snapshot()
        values = [str(row[0]) for row in snapshot_conn.execute("SELECT value FROM records ORDER BY rowid")]

        assert values == ["base", "wal-committed"]
        assert snapshot_conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        if snapshot_conn is not None:
            snapshot_conn.close()
        if snapshot_dir is not None:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        if writer.in_transaction:
            writer.rollback()
        writer.close()


def test_snapshot_failure_closes_source_and_removes_private_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = tmp_path / "zotero"
    _create_database(zotero_data_dir)
    snapshot_root = tmp_path / "snapshots"
    repository = ZoteroRepository(zotero_data_dir, snapshot_temp_root=snapshot_root)

    class FailingSource:
        closed = False

        def backup(self, _destination: sqlite3.Connection, **_kwargs: Any) -> None:
            raise sqlite3.OperationalError("simulated backup failure")

        def close(self) -> None:
            self.closed = True

    source = FailingSource()
    monkeypatch.setattr(repository, "_connect_primary", lambda: source)

    with pytest.raises(sqlite3.OperationalError, match="simulated backup failure"):
        repository._connect_snapshot()

    assert source.closed is True
    assert snapshot_root.is_dir()
    assert list(snapshot_root.iterdir()) == []


def test_fetchall_closes_successful_primary_connection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = tmp_path / "zotero"
    _create_database(zotero_data_dir)
    repository = ZoteroRepository(zotero_data_dir)

    class Result:
        @staticmethod
        def fetchall() -> list[str]:
            return ["row"]

    class Primary:
        closed = False

        @staticmethod
        def execute(_query: str, _params: tuple[Any, ...]) -> Result:
            return Result()

        def close(self) -> None:
            self.closed = True

    primary = Primary()
    monkeypatch.setattr(repository, "_connect_primary", lambda: primary)

    assert repository._fetchall("SELECT 1") == ["row"]
    assert primary.closed is True


def test_fetchall_closes_locked_primary_and_snapshot_and_removes_snapshot_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    zotero_data_dir = tmp_path / "zotero"
    _create_database(zotero_data_dir)
    repository = ZoteroRepository(zotero_data_dir)
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "zotero.sqlite").write_bytes(b"private")

    class LockedPrimary:
        closed = False

        @staticmethod
        def execute(_query: str, _params: tuple[Any, ...]) -> None:
            raise sqlite3.OperationalError("database is locked")

        def close(self) -> None:
            self.closed = True

    class Snapshot:
        closed = False

        @staticmethod
        def execute(_query: str, _params: tuple[Any, ...]) -> Any:
            class Result:
                @staticmethod
                def fetchall() -> list[str]:
                    return ["snapshot-row"]

            return Result()

        def close(self) -> None:
            self.closed = True

    primary = LockedPrimary()
    snapshot = Snapshot()
    monkeypatch.setattr(repository, "_connect_primary", lambda: primary)
    monkeypatch.setattr(repository, "_connect_snapshot", lambda: (snapshot, snapshot_dir))

    assert repository._fetchall("SELECT 1") == ["snapshot-row"]
    assert primary.closed is True
    assert snapshot.closed is True
    assert not snapshot_dir.exists()


def test_primary_read_only_uri_handles_spaces_and_hash_in_path(tmp_path: Path) -> None:
    zotero_data_dir = tmp_path / "zotero # data"
    _create_database(zotero_data_dir)
    repository = ZoteroRepository(zotero_data_dir)

    conn = repository._connect_primary()
    try:
        assert conn.execute("SELECT value FROM records").fetchone()[0] == "base"
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO records VALUES ('forbidden')")
    finally:
        conn.close()
