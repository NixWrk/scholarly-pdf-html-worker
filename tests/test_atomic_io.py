from pathlib import Path

import pytest

import pdf_html_polish.atomic_io as atomic_io
from pdf_html_polish.atomic_io import (
    copy_file_atomic,
    publish_directory_atomic,
    write_json_atomic,
    write_text_atomic,
)


def test_atomic_writers_round_trip_without_temporary_files(tmp_path: Path) -> None:
    text_path = tmp_path / "nested" / "stage.html"
    json_path = tmp_path / "manifest.json"
    source = tmp_path / "source.bin"
    copied = tmp_path / "copied.bin"
    source.write_bytes(b"source-data")

    write_text_atomic(text_path, "<html>ok</html>")
    write_json_atomic(json_path, {"status": "ok", "count": 2})
    copy_file_atomic(source, copied)

    assert text_path.read_text(encoding="utf-8") == "<html>ok</html>"
    assert json_path.read_text(encoding="utf-8").endswith("\n")
    assert copied.read_bytes() == b"source-data"
    assert list(tmp_path.rglob("*.tmp")) == []


def test_atomic_write_failure_preserves_previous_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "manifest.json"
    target.write_text('{"status":"previous"}\n', encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(atomic_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_json_atomic(target, {"status": "new"})

    assert target.read_text(encoding="utf-8") == '{"status":"previous"}\n'
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_copy_failure_preserves_previous_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.html"
    target = tmp_path / "target.html"
    source.write_text("new", encoding="utf-8")
    target.write_text("previous", encoding="utf-8")

    def fail_copy(_source: Path, temporary: Path) -> None:
        Path(temporary).write_text("partial", encoding="utf-8")
        raise OSError("simulated copy failure")

    monkeypatch.setattr(atomic_io.shutil, "copyfile", fail_copy)

    with pytest.raises(OSError, match="simulated copy failure"):
        copy_file_atomic(source, target)

    assert target.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.glob("*.tmp")) == []


def test_publish_directory_atomic_moves_complete_directory_and_rejects_collision(tmp_path: Path) -> None:
    source = tmp_path / ".pending"
    source.mkdir()
    (source / "article.html").write_text("complete", encoding="utf-8")
    target = tmp_path / "ATTACH22"

    publish_directory_atomic(source, target)

    assert not source.exists()
    assert (target / "article.html").read_text(encoding="utf-8") == "complete"

    collision_source = tmp_path / ".collision"
    collision_source.mkdir()
    (collision_source / "article.html").write_text("new", encoding="utf-8")

    with pytest.raises(FileExistsError, match="target already exists"):
        publish_directory_atomic(collision_source, target)

    assert (collision_source / "article.html").read_text(encoding="utf-8") == "new"
    assert (target / "article.html").read_text(encoding="utf-8") == "complete"
