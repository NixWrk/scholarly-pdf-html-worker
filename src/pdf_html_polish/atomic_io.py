"""Durable same-directory publication for pipeline artifacts."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4


def _temporary_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")


def _sync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path.parent, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _replace(temporary: Path, target: Path) -> None:
    os.replace(temporary, target)
    _sync_parent(target)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target)
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if target.is_file():
            shutil.copymode(target, temporary)
        _replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def write_text_atomic(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    errors: str | None = None,
) -> None:
    write_bytes_atomic(path, text.encode(encoding, errors=errors or "strict"))


def write_json_atomic(path: Path, data: Any) -> None:
    write_text_atomic(
        path,
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    )


def copy_file_atomic(source: Path, target: Path) -> None:
    source_path = Path(source)
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target_path)
    try:
        shutil.copyfile(source_path, temporary)
        with temporary.open("rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copystat(source_path, temporary)
        _replace(temporary, target_path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_directory_atomic(source: Path, target: Path) -> None:
    source_path = Path(source)
    target_path = Path(target)
    if source_path.parent.resolve(strict=False) != target_path.parent.resolve(strict=False):
        raise ValueError("Atomic directory publication requires a shared parent directory.")
    if source_path.is_symlink() or not source_path.is_dir():
        raise ValueError(f"Atomic directory source must be a regular directory: {source_path}")
    if target_path.exists() or target_path.is_symlink():
        raise FileExistsError(f"Atomic directory target already exists: {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source_path, target_path)
    _sync_parent(target_path)
