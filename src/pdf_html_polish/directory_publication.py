"""Crash-recoverable complete-directory publication."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import errno
import importlib
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import time
from types import TracebackType
from typing import Any, Literal, NoReturn, cast
from uuid import uuid4

from .atomic_io import write_json_atomic
from .quality_loop.cached_run_state import path_is_link_like


DirectoryValidator = Callable[[Path], None]
CommittedTreeMatcher = Callable[[Path, str], bool]
CancellationCheck = Callable[[], bool]
BeforeMutationCheck = Callable[[], None]

_JOURNAL_SCHEMA_VERSION = 2
_JOURNAL_PHASES = frozenset(
    {"initializing", "staging", "prepared", "old_moved", "new_published"}
)
_TRANSACTION_ID_LENGTH = 32
_LOCK_POLL_SECONDS = 0.05
_PROCESS_LOCK_GUARD = threading.Lock()
_PROCESS_LOCKS: set[str] = set()


def _fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def _same_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (int(first.st_dev), int(first.st_ino)) == (
        int(second.st_dev),
        int(second.st_ino),
    )


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


def _replace_path(source: Path, destination: Path) -> None:
    os.replace(source, destination)
    _sync_parent(destination)


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_json_key:{key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"nonfinite_json_constant:{value}")


@dataclass(frozen=True)
class _TreeEntry:
    name: str
    device: int
    inode: int
    mode: int
    link_count: int
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


@dataclass(frozen=True)
class _TreeSnapshot:
    device: int
    inode: int
    entries: tuple[_TreeEntry, ...]


TreeSnapshot = _TreeSnapshot | None


def _tree_snapshot_seal(snapshot: TreeSnapshot) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    entries = [
        [
            entry.name,
            entry.device,
            entry.inode,
            entry.mode,
            entry.link_count,
            entry.size,
            entry.mtime_ns,
            entry.ctime_ns,
            entry.sha256,
        ]
        for entry in snapshot.entries
    ]
    encoded = json.dumps(
        [snapshot.device, snapshot.inode, entries],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "device": snapshot.device,
        "inode": snapshot.inode,
        "entry_count": len(snapshot.entries),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _tree_seal_is_valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "device",
        "inode",
        "entry_count",
        "sha256",
    }:
        return False
    digest = value.get("sha256")
    return (
        type(value.get("device")) is int
        and value["device"] >= 0
        and type(value.get("inode")) is int
        and value["inode"] >= 0
        and type(value.get("entry_count")) is int
        and value["entry_count"] >= 0
        and isinstance(digest, str)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


def _snapshot_flat_tree(path: Path) -> TreeSnapshot:
    if not path.exists() and not path_is_link_like(path):
        return None
    if path_is_link_like(path) or not path.is_dir():
        _fail(f"Directory publication target is not a regular directory: {path}")
    try:
        root_before = path.stat()
    except OSError as exc:
        raise RuntimeError(
            f"Directory publication target is unreadable: {path}"
        ) from exc

    inventory = sorted(path.iterdir(), key=lambda candidate: candidate.name)
    result: list[_TreeEntry] = []
    for entry in inventory:
        if path_is_link_like(entry):
            _fail(f"Directory publication tree contains a link-like entry: {entry}")
        try:
            before = entry.stat()
        except OSError as exc:
            raise RuntimeError(
                f"Directory publication entry is unreadable: {entry}"
            ) from exc
        if not stat.S_ISREG(before.st_mode):
            _fail(f"Directory publication tree contains a non-file entry: {entry}")
        digest = hashlib.sha256()
        try:
            with entry.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = entry.stat()
        except OSError as exc:
            raise RuntimeError(
                f"Directory publication entry changed while reading: {entry}"
            ) from exc
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            _fail(f"Directory publication entry changed while reading: {entry}")
        result.append(
            _TreeEntry(
                name=entry.name,
                device=int(after.st_dev),
                inode=int(after.st_ino),
                mode=int(after.st_mode),
                link_count=int(after.st_nlink),
                size=int(after.st_size),
                mtime_ns=int(after.st_mtime_ns),
                ctime_ns=int(after.st_ctime_ns),
                sha256=digest.hexdigest(),
            )
        )
    try:
        root_after = path.stat()
    except OSError as exc:
        raise RuntimeError(
            f"Directory publication target changed while reading: {path}"
        ) from exc
    root_state_before = (
        root_before.st_dev,
        root_before.st_ino,
        root_before.st_mode,
        root_before.st_size,
        root_before.st_mtime_ns,
        root_before.st_ctime_ns,
    )
    root_state_after = (
        root_after.st_dev,
        root_after.st_ino,
        root_after.st_mode,
        root_after.st_size,
        root_after.st_mtime_ns,
        root_after.st_ctime_ns,
    )
    inventory_after = sorted(candidate.name for candidate in path.iterdir())
    if root_state_before != root_state_after or inventory_after != [
        entry.name for entry in result
    ]:
        _fail(f"Directory publication target changed while reading: {path}")
    return _TreeSnapshot(
        device=int(root_after.st_dev),
        inode=int(root_after.st_ino),
        entries=tuple(result),
    )


def _safe_remove_flat_tree(path: Path) -> None:
    if not path.exists() and not path_is_link_like(path):
        return
    if path_is_link_like(path) or not path.is_dir():
        _fail(f"Refusing to remove unsafe directory publication residue: {path}")
    entries = list(path.iterdir())
    if any(path_is_link_like(entry) or not entry.is_file() for entry in entries):
        _fail(f"Refusing to remove non-flat directory publication residue: {path}")
    for entry in entries:
        entry.unlink()
    path.rmdir()
    _sync_parent(path)


class _PublicationFileLock:
    def __init__(self, path: Path, timeout_seconds: float) -> None:
        if timeout_seconds < 0:
            raise ValueError("lock_timeout_seconds must be non-negative")
        self.path = path
        self.timeout_seconds = timeout_seconds
        self._descriptor: int | None = None
        self._identity: os.stat_result | None = None
        self._process_key = _path_key(path)
        self._process_reserved = False

    def _reserve_process_lock(self, deadline: float) -> None:
        while True:
            with _PROCESS_LOCK_GUARD:
                if self._process_key not in _PROCESS_LOCKS:
                    _PROCESS_LOCKS.add(self._process_key)
                    self._process_reserved = True
                    return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for directory publication lock: {self.path}"
                )
            time.sleep(_LOCK_POLL_SECONDS)

    def _open_lock_file(self) -> int:
        if path_is_link_like(self.path):
            _fail(f"Directory publication lock path is link-like: {self.path}")
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(self.path, flags | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            descriptor = os.open(self.path, flags)
        descriptor_stat = os.fstat(descriptor)
        try:
            path_stat = self.path.stat(follow_symlinks=False)
        except OSError:
            os.close(descriptor)
            raise
        if (
            path_is_link_like(self.path)
            or not stat.S_ISREG(descriptor_stat.st_mode)
            or int(descriptor_stat.st_nlink) != 1
            or not _same_identity(descriptor_stat, path_stat)
        ):
            os.close(descriptor)
            _fail(f"Directory publication lock file is unsafe: {self.path}")
        self._identity = descriptor_stat
        return descriptor

    @staticmethod
    def _try_os_lock(descriptor: int) -> bool:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or getattr(
                    exc,
                    "winerror",
                    None,
                ) in {33, 36}:
                    return False
                raise
            return True
        fcntl_module = importlib.import_module("fcntl")
        flock = cast(Callable[[int, int], object], getattr(fcntl_module, "flock"))
        operation = cast(int, getattr(fcntl_module, "LOCK_EX")) | cast(
            int, getattr(fcntl_module, "LOCK_NB")
        )

        try:
            flock(descriptor, operation)
        except BlockingIOError:
            return False
        return True

    @staticmethod
    def _unlock_os(descriptor: int) -> None:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            return

        fcntl_module = importlib.import_module("fcntl")
        flock = cast(Callable[[int, int], object], getattr(fcntl_module, "flock"))
        operation = cast(int, getattr(fcntl_module, "LOCK_UN"))
        flock(descriptor, operation)

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout_seconds
        self._reserve_process_lock(deadline)
        try:
            descriptor = self._open_lock_file()
            while not self._try_os_lock(descriptor):
                if time.monotonic() >= deadline:
                    os.close(descriptor)
                    raise TimeoutError(
                        f"Timed out waiting for directory publication lock: {self.path}"
                    )
                time.sleep(_LOCK_POLL_SECONDS)
            self._descriptor = descriptor
        except BaseException:
            self._release_process_reservation()
            raise

    def require_current(self) -> None:
        descriptor = self._descriptor
        identity = self._identity
        if descriptor is None or identity is None:
            _fail("Directory publication lock is not held")
        try:
            descriptor_stat = os.fstat(descriptor)
            path_stat = self.path.stat(follow_symlinks=False)
        except OSError as exc:
            raise RuntimeError("Directory publication lock changed while held") from exc
        if (
            path_is_link_like(self.path)
            or int(path_stat.st_nlink) != 1
            or not _same_identity(identity, descriptor_stat)
            or not _same_identity(descriptor_stat, path_stat)
        ):
            _fail("Directory publication lock changed while held")

    def _release_process_reservation(self) -> None:
        if not self._process_reserved:
            return
        with _PROCESS_LOCK_GUARD:
            _PROCESS_LOCKS.discard(self._process_key)
        self._process_reserved = False

    def release(self) -> None:
        descriptor = self._descriptor
        self._descriptor = None
        try:
            if descriptor is not None:
                try:
                    self._unlock_os(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            self._release_process_reservation()


class CompleteDirectoryPublication:
    """Build and publish one exact flat directory tree as a recoverable transaction."""

    def __init__(
        self,
        target_dir: Path,
        *,
        validate_existing: DirectoryValidator,
        validate_staging: DirectoryValidator,
        committed_tree_matches: CommittedTreeMatcher,
        is_cancelled: CancellationCheck | None = None,
        before_mutation: BeforeMutationCheck | None = None,
        lock_timeout_seconds: float = 30.0,
    ) -> None:
        self.target_dir = Path(target_dir)
        self._validate_existing = validate_existing
        self._validate_staging = validate_staging
        self._committed_tree_matches = committed_tree_matches
        self._is_cancelled = is_cancelled or (lambda: False)
        self._before_mutation = before_mutation or (lambda: None)
        self._lock = _PublicationFileLock(
            self.target_dir.parent / f".{self.target_dir.name}.publication.lock",
            lock_timeout_seconds,
        )
        self._journal_path = (
            self.target_dir.parent / f".{self.target_dir.name}.publication.json"
        )
        self._transaction_id = ""
        self._staging_dir: Path | None = None
        self._rollback_dir: Path | None = None
        self._baseline: TreeSnapshot = None
        self._entered = False
        self._committed = False
        self._mutation_started = False

    @property
    def transaction_id(self) -> str:
        if not self._transaction_id:
            raise RuntimeError("Directory publication transaction has not started")
        return self._transaction_id

    @property
    def staging_dir(self) -> Path:
        if self._staging_dir is None:
            raise RuntimeError("Directory publication transaction has not started")
        return self._staging_dir

    def _paths_for(self, transaction_id: str) -> tuple[Path, Path]:
        prefix = f".{self.target_dir.name}.publication.{transaction_id}"
        return (
            self.target_dir.parent / f"{prefix}.staging",
            self.target_dir.parent / f"{prefix}.rollback",
        )

    def _read_journal(self) -> dict[str, Any] | None:
        if not self._journal_path.exists() and not path_is_link_like(
            self._journal_path
        ):
            return None
        if path_is_link_like(self._journal_path) or not self._journal_path.is_file():
            _fail(f"Directory publication journal path is unsafe: {self._journal_path}")
        journal_stat = self._journal_path.stat()
        if int(journal_stat.st_nlink) != 1 or int(journal_stat.st_size) > 64 * 1024:
            _fail(f"Directory publication journal is unsafe: {self._journal_path}")
        try:
            payload = json.loads(
                self._journal_path.read_text(encoding="utf-8"),
                object_pairs_hook=_json_object_without_duplicates,
                parse_constant=_reject_json_constant,
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(
                f"Directory publication journal is malformed: {self._journal_path}"
            ) from exc
        expected_keys = {
            "schema_version",
            "target",
            "transaction_id",
            "phase",
            "target_existed",
            "baseline",
        }
        if not isinstance(payload, dict) or set(payload) != expected_keys:
            _fail(
                f"Directory publication journal schema is invalid: {self._journal_path}"
            )
        transaction_id = payload.get("transaction_id")
        target_existed = payload.get("target_existed")
        baseline = payload.get("baseline")
        if (
            type(payload.get("schema_version")) is not int
            or payload["schema_version"] != _JOURNAL_SCHEMA_VERSION
            or payload.get("target") != str(self.target_dir)
            or not isinstance(transaction_id, str)
            or len(transaction_id) != _TRANSACTION_ID_LENGTH
            or any(character not in "0123456789abcdef" for character in transaction_id)
            or payload.get("phase") not in _JOURNAL_PHASES
            or type(target_existed) is not bool
            or (target_existed is True and not _tree_seal_is_valid(baseline))
            or (target_existed is False and baseline is not None)
            or (payload.get("phase") == "old_moved" and target_existed is not True)
        ):
            _fail(
                f"Directory publication journal values are invalid: {self._journal_path}"
            )
        return payload

    def _write_journal(self, phase: str, *, target_existed: bool) -> None:
        if phase not in _JOURNAL_PHASES:
            raise ValueError(f"Invalid directory publication phase: {phase}")
        self._lock.require_current()
        if target_existed != (self._baseline is not None):
            raise RuntimeError("Directory publication baseline state changed")
        write_json_atomic(
            self._journal_path,
            {
                "schema_version": _JOURNAL_SCHEMA_VERSION,
                "target": str(self.target_dir),
                "transaction_id": self.transaction_id,
                "phase": phase,
                "target_existed": target_existed,
                "baseline": _tree_snapshot_seal(self._baseline),
            },
        )
        payload = self._read_journal()
        if payload is None or payload.get("phase") != phase:
            _fail("Directory publication journal verification failed")

    def _remove_journal(self) -> None:
        if not self._journal_path.exists() and not path_is_link_like(
            self._journal_path
        ):
            return
        payload = self._read_journal()
        if payload is None:
            return
        self._journal_path.unlink()
        _sync_parent(self._journal_path)

    def _committed_matches(self, path: Path, transaction_id: str) -> bool:
        try:
            return bool(self._committed_tree_matches(path, transaction_id))
        except (OSError, UnicodeError, ValueError, RuntimeError):
            return False

    def _cleanup_journal_temporaries(self) -> None:
        prefix = f".{self._journal_path.name}."
        for path in self.target_dir.parent.glob(f"{prefix}*.tmp"):
            remainder = path.name[len(prefix) : -len(".tmp")]
            parts = remainder.split(".")
            if (
                len(parts) != 2
                or not parts[0].isdigit()
                or len(parts[1]) != _TRANSACTION_ID_LENGTH
                or any(character not in "0123456789abcdef" for character in parts[1])
            ):
                continue
            if path_is_link_like(path) or not path.is_file():
                _fail(f"Directory publication journal temporary is unsafe: {path}")
            temporary_stat = path.stat()
            if int(temporary_stat.st_nlink) != 1:
                _fail(f"Directory publication journal temporary is unsafe: {path}")
            path.unlink()
        _sync_parent(self._journal_path)

    def _recover_previous_transaction(self) -> None:
        payload = self._read_journal()
        if payload is None:
            orphan_pattern = f".{self.target_dir.name}.publication.*"
            orphans = [
                path
                for path in self.target_dir.parent.glob(orphan_pattern)
                if path.name.endswith((".staging", ".rollback"))
            ]
            if orphans:
                _fail(f"Untracked directory publication residue: {orphans[0]}")
            return
        transaction_id = str(payload["transaction_id"])
        target_existed = payload["target_existed"] is True
        baseline_seal = payload["baseline"]
        phase = str(payload["phase"])
        staging_dir, rollback_dir = self._paths_for(transaction_id)
        target_exists = self.target_dir.exists() or path_is_link_like(self.target_dir)
        target_committed = target_exists and self._committed_matches(
            self.target_dir,
            transaction_id,
        )
        rollback_exists = rollback_dir.exists() or path_is_link_like(rollback_dir)
        if rollback_exists:
            if not target_existed:
                _fail(
                    "Directory publication recovery found a rollback tree for a target "
                    "that did not previously exist"
                )
            self._validate_existing(rollback_dir)
            if _tree_snapshot_seal(_snapshot_flat_tree(rollback_dir)) != baseline_seal:
                _fail(
                    "Directory publication recovery rollback does not match "
                    "the recorded baseline"
                )
        if target_committed:
            if phase in {"initializing", "staging"}:
                _fail(
                    "Directory publication recovery found a committed target "
                    f"during journal phase {phase}"
                )
            _safe_remove_flat_tree(staging_dir)
            _safe_remove_flat_tree(rollback_dir)
            self._remove_journal()
            return
        if rollback_exists:
            if target_exists:
                _fail(
                    "Directory publication recovery is ambiguous: "
                    "target and rollback both exist"
                )
            _replace_path(rollback_dir, self.target_dir)
            _safe_remove_flat_tree(staging_dir)
            self._remove_journal()
            return
        if target_existed:
            if not target_exists:
                _fail(
                    "Directory publication recovery cannot find the previous target tree"
                )
            self._validate_existing(self.target_dir)
            if (
                _tree_snapshot_seal(_snapshot_flat_tree(self.target_dir))
                != baseline_seal
            ):
                _fail(
                    "Directory publication recovery target does not match "
                    "the recorded baseline"
                )
        elif target_exists:
            _fail("Directory publication recovery found an unexpected target")
        _safe_remove_flat_tree(staging_dir)
        self._remove_journal()

    def __enter__(self) -> CompleteDirectoryPublication:
        if self._entered:
            raise RuntimeError("Directory publication transaction cannot be re-entered")
        if (
            path_is_link_like(self.target_dir.parent)
            or not self.target_dir.parent.is_dir()
        ):
            raise ValueError(
                f"Directory publication parent must be an existing regular directory: {self.target_dir.parent}"
            )
        self._lock.acquire()
        try:
            self._cleanup_journal_temporaries()
            self._recover_previous_transaction()
            self._validate_existing(self.target_dir)
            self._baseline = _snapshot_flat_tree(self.target_dir)
            self._transaction_id = uuid4().hex
            self._staging_dir, self._rollback_dir = self._paths_for(
                self._transaction_id
            )
            self._write_journal(
                "initializing",
                target_existed=self._baseline is not None,
            )
            self._staging_dir.mkdir(mode=0o700)
            self._write_journal("staging", target_existed=self._baseline is not None)
            self._entered = True
            return self
        except BaseException:
            self._lock.release()
            raise

    def check_cancelled(self) -> None:
        if self._is_cancelled():
            raise RuntimeError("Directory publication cancelled before commit")

    def _rollback_failed_commit(self) -> list[str]:
        errors: list[str] = []
        staging_dir = self._staging_dir
        rollback_dir = self._rollback_dir
        if staging_dir is None or rollback_dir is None:
            return ["transaction paths unavailable"]
        try:
            if not self._mutation_started:
                _safe_remove_flat_tree(staging_dir)
                _safe_remove_flat_tree(rollback_dir)
                self._remove_journal()
                return errors

            target_committed = self._committed_matches(
                self.target_dir,
                self.transaction_id,
            )
            rollback_exists = rollback_dir.exists() or path_is_link_like(rollback_dir)
            if self._baseline is not None and rollback_exists:
                if self.target_dir.exists() or path_is_link_like(self.target_dir):
                    if not target_committed:
                        raise RuntimeError(
                            "unexpected target occupies rollback destination"
                        )
                    _safe_remove_flat_tree(staging_dir)
                    _replace_path(self.target_dir, staging_dir)
                _replace_path(rollback_dir, self.target_dir)
            elif self._baseline is None and target_committed:
                _safe_remove_flat_tree(staging_dir)
                _replace_path(self.target_dir, staging_dir)
            elif self._baseline is not None:
                self._validate_existing(self.target_dir)
                if _snapshot_flat_tree(self.target_dir) != self._baseline:
                    raise RuntimeError(
                        "previous target changed and no rollback tree exists"
                    )
            elif self.target_dir.exists() or path_is_link_like(self.target_dir):
                raise RuntimeError("unexpected target appeared during rollback")
            _safe_remove_flat_tree(staging_dir)
            _safe_remove_flat_tree(rollback_dir)
        except BaseException as exc:
            errors.append(f"tree:{type(exc).__name__}:{exc}")
        if not errors:
            try:
                self._remove_journal()
            except BaseException as exc:
                errors.append(f"journal:{type(exc).__name__}:{exc}")
        return errors

    def commit(self) -> None:
        if not self._entered or self._committed:
            raise RuntimeError("Directory publication transaction is not pending")
        staging_dir = self.staging_dir
        rollback_dir = self._rollback_dir
        assert rollback_dir is not None
        self.check_cancelled()
        self._validate_staging(staging_dir)
        self._validate_existing(self.target_dir)
        if _snapshot_flat_tree(self.target_dir) != self._baseline:
            raise RuntimeError(
                "Directory publication target changed during publication"
            )
        self._lock.require_current()
        target_existed = self._baseline is not None
        self._write_journal("prepared", target_existed=target_existed)
        self._before_mutation()
        self.check_cancelled()
        self._validate_existing(self.target_dir)
        if _snapshot_flat_tree(self.target_dir) != self._baseline:
            raise RuntimeError("Directory publication target changed before mutation")
        self._lock.require_current()
        try:
            self._mutation_started = True
            if target_existed:
                _replace_path(self.target_dir, rollback_dir)
                self._write_journal("old_moved", target_existed=True)
                self._validate_existing(rollback_dir)
                if _snapshot_flat_tree(rollback_dir) != self._baseline:
                    raise RuntimeError(
                        "Directory publication rollback snapshot changed"
                    )
            _replace_path(staging_dir, self.target_dir)
            self._write_journal("new_published", target_existed=target_existed)
            self._validate_staging(self.target_dir)
            if not self._committed_matches(self.target_dir, self.transaction_id):
                raise RuntimeError(
                    "Directory publication committed tree validation failed"
                )
        except BaseException as exc:
            rollback_errors = self._rollback_failed_commit()
            if rollback_errors:
                raise RuntimeError(
                    "Directory publication failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from exc
            raise
        self._committed = True
        try:
            _safe_remove_flat_tree(rollback_dir)
            self._remove_journal()
        except (OSError, RuntimeError):
            # The new tree is fully committed. The journal lets the next run
            # finish residue cleanup without rolling back valid output.
            pass

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        cleanup_error: RuntimeError | None = None
        try:
            if not self._committed:
                errors = self._rollback_failed_commit()
                if errors:
                    cleanup_error = RuntimeError(
                        "Directory publication cleanup was incomplete: "
                        + "; ".join(errors)
                    )
        finally:
            self._lock.release()
            self._entered = False
        if cleanup_error is not None:
            raise cleanup_error from exc_value
        return False
