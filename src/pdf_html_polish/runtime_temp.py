from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import psutil

from .atomic_io import write_json_atomic


RUNTIME_TEMP_DIRNAME = "_z2m_runtime_tmp"
RUNTIME_RUN_PREFIX = "run_"
RUNTIME_OWNER_SUFFIX = ".owner.json"
RUNTIME_OWNER_SCHEMA_VERSION = 1
_PROCESS_CREATE_TIME_TOLERANCE_SECONDS = 0.01


def _runtime_container(output_dir: Path) -> Path:
    output_root = Path(output_dir).expanduser().resolve(strict=False)
    container = output_root / RUNTIME_TEMP_DIRNAME
    if container.is_symlink():
        raise ValueError(f"Runtime temp container must not be a symlink: {container}")
    if container.exists() and not container.is_dir():
        raise ValueError(f"Runtime temp container must be a directory: {container}")
    container.mkdir(parents=True, exist_ok=True)
    escaped = (
        container.is_symlink()
        or container.resolve(strict=True).parent != output_root.resolve(strict=True)
    )
    if escaped:
        raise ValueError(f"Runtime temp container escaped the output directory: {container}")
    return container


def _owner_path(run_dir: Path) -> Path:
    return run_dir.parent / f"{run_dir.name}{RUNTIME_OWNER_SUFFIX}"


def _current_process_create_time() -> float:
    return float(psutil.Process(os.getpid()).create_time())


def _read_owner(owner_path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(owner_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _owner_is_live(owner_path: Path) -> bool:
    payload = _read_owner(owner_path)
    if payload is None or payload.get("schema_version") != RUNTIME_OWNER_SCHEMA_VERSION:
        return False
    raw_pid = payload.get("pid")
    raw_create_time = payload.get("process_create_time")
    if isinstance(raw_pid, bool) or not isinstance(raw_pid, (int, str)):
        return False
    if isinstance(raw_create_time, bool) or not isinstance(
        raw_create_time, (int, float, str)
    ):
        return False
    try:
        pid = int(raw_pid)
        expected_create_time = float(raw_create_time)
    except ValueError:
        return False
    if pid <= 0:
        return False
    try:
        actual_create_time = float(psutil.Process(pid).create_time())
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
    delta = abs(actual_create_time - expected_create_time)
    return delta <= _PROCESS_CREATE_TIME_TOLERANCE_SECONDS


def _remove_run_dir(run_dir: Path) -> None:
    if run_dir.is_symlink():
        run_dir.unlink()
    elif run_dir.exists():
        shutil.rmtree(run_dir)


def _prune_orphaned_runs(container: Path) -> None:
    for run_dir in list(container.iterdir()):
        if not run_dir.name.startswith(RUNTIME_RUN_PREFIX):
            continue
        if run_dir.name.endswith(RUNTIME_OWNER_SUFFIX):
            continue
        if not (run_dir.is_dir() or run_dir.is_symlink()):
            continue
        owner_path = _owner_path(run_dir)
        if _owner_is_live(owner_path):
            continue
        try:
            _remove_run_dir(run_dir)
            owner_path.unlink(missing_ok=True)
        except OSError:
            continue

    for owner_path in container.glob(f"{RUNTIME_RUN_PREFIX}*{RUNTIME_OWNER_SUFFIX}"):
        run_name = owner_path.name[: -len(RUNTIME_OWNER_SUFFIX)]
        run_dir = container / run_name
        if run_dir.exists() or run_dir.is_symlink() or _owner_is_live(owner_path):
            continue
        try:
            owner_path.unlink(missing_ok=True)
        except OSError:
            continue


def runtime_temp_root(output_dir: Path) -> Path:
    """Create one owned runtime directory and reap dead run-scoped siblings."""

    container = _runtime_container(output_dir)
    _prune_orphaned_runs(container)
    run_dir = container / f"{RUNTIME_RUN_PREFIX}{uuid4().hex}"
    owner_path = _owner_path(run_dir)
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_json_atomic(
        owner_path,
        {
            "schema_version": RUNTIME_OWNER_SCHEMA_VERSION,
            "pid": os.getpid(),
            "process_create_time": _current_process_create_time(),
            "created_at": created_at,
        },
    )
    try:
        run_dir.mkdir()
    except BaseException:
        owner_path.unlink(missing_ok=True)
        raise
    return run_dir


def make_temp_dir(root: Path, prefix: str) -> Path:
    if root.is_symlink():
        raise ValueError(f"Temporary root must not be a symlink: {root}")
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError(f"Temporary root must be a directory: {root}")
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(root)))


def cleanup_runtime_temp_root(root: Path) -> bool:
    """Remove only the caller's owned run directory, never a shared container."""

    run_dir = Path(root)
    managed = (
        run_dir.parent.name == RUNTIME_TEMP_DIRNAME
        and run_dir.name.startswith(RUNTIME_RUN_PREFIX)
    )
    if not managed:
        raise ValueError(f"Refusing to clean an unmanaged runtime path: {run_dir}")
    container = run_dir.parent
    if container.is_symlink():
        return False
    owner_path = _owner_path(run_dir)
    try:
        _remove_run_dir(run_dir)
        if run_dir.exists() or run_dir.is_symlink():
            return False
        owner_path.unlink(missing_ok=True)
        try:
            container.rmdir()
        except OSError:
            pass
        return not owner_path.exists()
    except OSError:
        return False

