from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

import pdf_html_polish.directory_publication as publication_module
from pdf_html_polish.directory_publication import CompleteDirectoryPublication


def _validate_flat_tree(path: Path) -> None:
    if not path.exists():
        return
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError(f"invalid tree: {path}")
    if any(not entry.is_file() or entry.is_symlink() for entry in path.iterdir()):
        raise RuntimeError(f"invalid tree entry: {path}")


def _committed_tree_matches(path: Path, transaction_id: str) -> bool:
    marker = path / "commit.txt"
    return (
        path.is_dir()
        and marker.is_file()
        and marker.read_text(encoding="utf-8") == transaction_id
    )


def _build_committed_tree(transaction: CompleteDirectoryPublication, body: str) -> None:
    (transaction.staging_dir / "article.html").write_text(body, encoding="utf-8")
    (transaction.staging_dir / "commit.txt").write_text(
        transaction.transaction_id,
        encoding="utf-8",
    )


def _transaction(target: Path, **kwargs: object) -> CompleteDirectoryPublication:
    return CompleteDirectoryPublication(
        target,
        validate_existing=_validate_flat_tree,
        validate_staging=_validate_flat_tree,
        committed_tree_matches=_committed_tree_matches,
        **kwargs,
    )


def _write_recovery_journal(
    target: Path,
    *,
    transaction_id: str,
    phase: str,
    baseline_path: Path | None,
) -> Path:
    baseline = (
        publication_module._tree_snapshot_seal(
            publication_module._snapshot_flat_tree(baseline_path)
        )
        if baseline_path is not None
        else None
    )
    journal = target.parent / f".{target.name}.publication.json"
    journal.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "target": str(target),
                "transaction_id": transaction_id,
                "phase": phase,
                "target_existed": baseline_path is not None,
                "baseline": baseline,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return journal


def _run_crashing_publication(
    target: Path, *, phase: str
) -> subprocess.CompletedProcess[str]:
    repository_root = Path(__file__).resolve().parents[1]
    script = f"""
import os
from pathlib import Path
import pdf_html_polish.directory_publication as publication

target = Path({str(target)!r})
phase = {phase!r}

def validate(path):
    if path.exists() and (not path.is_dir() or any(not entry.is_file() for entry in path.iterdir())):
        raise RuntimeError("invalid tree")

def committed(path, transaction_id):
    marker = path / "commit.txt"
    return marker.is_file() and marker.read_text(encoding="utf-8") == transaction_id

real_replace = publication._replace_path

def crash_replace(source, destination):
    real_replace(source, destination)
    if phase == "old_moved" and source == target and destination.name.endswith(".rollback"):
        os._exit(73)
    if phase == "new_published" and source.name.endswith(".staging") and destination == target:
        os._exit(74)

publication._replace_path = crash_replace
with publication.CompleteDirectoryPublication(
    target,
    validate_existing=validate,
    validate_staging=validate,
    committed_tree_matches=committed,
    lock_timeout_seconds=1,
) as transaction:
    (transaction.staging_dir / "article.html").write_text("new", encoding="utf-8")
    (transaction.staging_dir / "commit.txt").write_text(transaction.transaction_id, encoding="utf-8")
    transaction.commit()
"""
    environment = os.environ.copy()
    source_root = str(repository_root / "src")
    environment["PYTHONPATH"] = source_root + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=repository_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_complete_directory_publication_replaces_entire_tree(tmp_path: Path) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    (target / "stale.html").write_text("stale", encoding="utf-8")

    with _transaction(target) as transaction:
        _build_committed_tree(transaction, "new")
        transaction.commit()

    assert {entry.name for entry in target.iterdir()} == {"article.html", "commit.txt"}
    assert (target / "article.html").read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob(".final_html.publication.*.staging"))
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))
    assert not (tmp_path / ".final_html.publication.json").exists()


def test_complete_directory_publication_second_move_failure_restores_old_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    before = {entry.name: entry.read_bytes() for entry in target.iterdir()}
    real_replace = publication_module._replace_path

    def fail_new_tree_move(source: Path, destination: Path) -> None:
        if source.name.endswith(".staging") and destination == target:
            raise OSError("simulated second move failure")
        real_replace(source, destination)

    monkeypatch.setattr(publication_module, "_replace_path", fail_new_tree_move)

    with pytest.raises(OSError, match="simulated second move failure"):
        with _transaction(target) as transaction:
            _build_committed_tree(transaction, "new")
            transaction.commit()

    assert {entry.name: entry.read_bytes() for entry in target.iterdir()} == before
    assert not list(tmp_path.glob(".final_html.publication.*.staging"))
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))
    assert not (tmp_path / ".final_html.publication.json").exists()


def test_complete_directory_publication_incomplete_rollback_keeps_recovery_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    real_replace = publication_module._replace_path

    def fail_publish_and_restore(source: Path, destination: Path) -> None:
        if destination == target and (
            source.name.endswith(".staging") or source.name.endswith(".rollback")
        ):
            raise OSError("simulated persistent rename failure")
        real_replace(source, destination)

    monkeypatch.setattr(
        publication_module,
        "_replace_path",
        fail_publish_and_restore,
    )

    with pytest.raises(
        RuntimeError, match="rollback was incomplete|cleanup was incomplete"
    ):
        with _transaction(target) as transaction:
            _build_committed_tree(transaction, "new")
            transaction.commit()

    journal = tmp_path / ".final_html.publication.json"
    rollback_paths = list(tmp_path.glob(".final_html.publication.*.rollback"))
    assert journal.is_file()
    assert len(rollback_paths) == 1
    assert (rollback_paths[0] / "old.html").read_text(encoding="utf-8") == "old"
    assert not target.exists()

    monkeypatch.undo()
    with _transaction(target):
        assert (target / "old.html").read_text(encoding="utf-8") == "old"

    assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert not journal.exists()
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))


def test_complete_directory_publication_base_exception_restores_old_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    real_replace = publication_module._replace_path

    def interrupt_new_tree_move(source: Path, destination: Path) -> None:
        if source.name.endswith(".staging") and destination == target:
            raise KeyboardInterrupt
        real_replace(source, destination)

    monkeypatch.setattr(publication_module, "_replace_path", interrupt_new_tree_move)

    with pytest.raises(KeyboardInterrupt):
        with _transaction(target) as transaction:
            _build_committed_tree(transaction, "new")
            transaction.commit()

    assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert not (target / "article.html").exists()


def test_snapshot_flat_tree_detects_entry_added_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    real_iterdir = Path.iterdir
    raced = False

    def racing_iterdir(path: Path):
        nonlocal raced
        entries = list(real_iterdir(path))
        yield from entries
        if path == target and not raced:
            raced = True
            (target / "late.html").write_text("late", encoding="utf-8")

    monkeypatch.setattr(Path, "iterdir", racing_iterdir)

    with pytest.raises(RuntimeError, match="changed while reading"):
        publication_module._snapshot_flat_tree(target)

    assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert (target / "late.html").read_text(encoding="utf-8") == "late"


def test_complete_directory_publication_detects_target_race_before_commit(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    old = target / "old.html"
    old.write_text("old", encoding="utf-8")

    with pytest.raises(RuntimeError, match="changed during publication"):
        with _transaction(target) as transaction:
            _build_committed_tree(transaction, "new")
            old.write_text("raced", encoding="utf-8")
            transaction.commit()

    assert old.read_text(encoding="utf-8") == "raced"
    assert not (target / "article.html").exists()


def test_complete_directory_publication_cancellation_preserves_old_tree(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")

    with pytest.raises(RuntimeError, match="cancelled before commit"):
        with _transaction(target, is_cancelled=lambda: True) as transaction:
            _build_committed_tree(transaction, "new")
            transaction.commit()

    assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert not (target / "article.html").exists()


def test_complete_directory_publication_before_mutation_failure_preserves_old_tree(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")

    def fail_authority_check() -> None:
        raise RuntimeError("authority changed")

    with pytest.raises(RuntimeError, match="authority changed"):
        with CompleteDirectoryPublication(
            target,
            validate_existing=_validate_flat_tree,
            validate_staging=_validate_flat_tree,
            committed_tree_matches=_committed_tree_matches,
            before_mutation=fail_authority_check,
        ) as transaction:
            _build_committed_tree(transaction, "new")
            transaction.commit()

    assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob(".final_html.publication.*.staging"))
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))
    assert not (tmp_path / ".final_html.publication.json").exists()


def test_complete_directory_publication_lock_times_out_without_mutation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")

    with _transaction(target):
        with pytest.raises(TimeoutError, match="publication lock"):
            with _transaction(target, lock_timeout_seconds=0):
                raise AssertionError("second publisher must not acquire the lock")

    assert (target / "old.html").read_text(encoding="utf-8") == "old"


def test_complete_directory_publication_cross_process_lock_times_out_and_recovers(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    ready = tmp_path / "child.ready"
    repository_root = Path(__file__).resolve().parents[1]
    script = f"""
import time
from pathlib import Path
from pdf_html_polish.directory_publication import CompleteDirectoryPublication

target = Path({str(target)!r})
ready = Path({str(ready)!r})

def validate(path):
    if path.exists() and (not path.is_dir() or any(not entry.is_file() for entry in path.iterdir())):
        raise RuntimeError("invalid tree")

def committed(path, transaction_id):
    return False

with CompleteDirectoryPublication(
    target,
    validate_existing=validate,
    validate_staging=validate,
    committed_tree_matches=committed,
    lock_timeout_seconds=1,
):
    ready.write_text("ready", encoding="utf-8")
    time.sleep(30)
"""
    environment = os.environ.copy()
    source_root = str(repository_root / "src")
    environment["PYTHONPATH"] = source_root + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=repository_root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(100):
            if ready.is_file() or process.poll() is not None:
                break
            time.sleep(0.05)
        assert ready.is_file(), (
            process.stderr.read() if process.stderr is not None else ""
        )
        with pytest.raises(TimeoutError, match="publication lock"):
            with _transaction(target, lock_timeout_seconds=0.1):
                raise AssertionError("parent must not acquire a child-held lock")
        assert (target / "old.html").read_text(encoding="utf-8") == "old"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)

    with _transaction(target):
        assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert not (tmp_path / ".final_html.publication.json").exists()
    assert not list(tmp_path.glob(".final_html.publication.*.staging"))


def test_complete_directory_publication_recovers_zero_byte_lock_creation_crash(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    lock_path = tmp_path / ".final_html.publication.lock"
    lock_path.touch()

    with _transaction(target) as transaction:
        _build_committed_tree(transaction, "new")
        transaction.commit()

    assert lock_path.stat().st_size == 0
    assert (target / "article.html").read_text(encoding="utf-8") == "new"


def test_complete_directory_publication_rejects_hardlinked_lock_without_writing(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    sentinel = tmp_path / "sentinel.bin"
    sentinel.write_bytes(b"sentinel")
    lock_path = tmp_path / ".final_html.publication.lock"
    lock_path.hardlink_to(sentinel)

    with pytest.raises(RuntimeError, match="lock file is unsafe"):
        with _transaction(target):
            raise AssertionError("unsafe lock must fail before recovery")

    assert sentinel.read_bytes() == b"sentinel"
    assert lock_path.read_bytes() == b"sentinel"
    assert (target / "old.html").read_text(encoding="utf-8") == "old"


def test_complete_directory_publication_rejects_untracked_crash_residue(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    orphan = tmp_path / f".final_html.publication.{'c' * 32}.staging"
    orphan.mkdir()
    (orphan / "partial.html").write_text("partial", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Untracked directory publication residue"):
        with _transaction(target):
            raise AssertionError("untracked residue must fail closed")

    assert orphan.is_dir()
    assert (target / "old.html").read_text(encoding="utf-8") == "old"


def test_complete_directory_publication_cleans_atomic_journal_crash_temp(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    journal_temp = tmp_path / f"..final_html.publication.json.1234.{'e' * 32}.tmp"
    journal_temp.write_text("partial journal", encoding="utf-8")

    with _transaction(target):
        assert not journal_temp.exists()

    assert not journal_temp.exists()
    assert (target / "old.html").read_text(encoding="utf-8") == "old"


def test_complete_directory_publication_rejects_tampered_target_with_rollback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "tampered.html").write_text("tampered", encoding="utf-8")
    transaction_id = "d" * 32
    rollback = tmp_path / f".final_html.publication.{transaction_id}.rollback"
    rollback.mkdir()
    (rollback / "old.html").write_text("old", encoding="utf-8")
    journal = _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="old_moved",
        baseline_path=rollback,
    )

    with pytest.raises(RuntimeError, match="recovery is ambiguous"):
        with _transaction(target):
            raise AssertionError("tampered committed target must fail closed")

    assert (target / "tampered.html").read_text(encoding="utf-8") == "tampered"
    assert (rollback / "old.html").read_text(encoding="utf-8") == "old"
    assert journal.exists()


def test_complete_directory_publication_rejects_unexpected_target_when_none_existed(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "foreign.html").write_text("foreign", encoding="utf-8")
    transaction_id = "f" * 32
    journal = _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="staging",
        baseline_path=None,
    )

    with pytest.raises(RuntimeError, match="unexpected target"):
        with _transaction(target):
            raise AssertionError("an unowned target must fail closed")

    assert (target / "foreign.html").read_text(encoding="utf-8") == "foreign"
    assert journal.exists()


def test_complete_directory_publication_rejects_tampered_restored_target_without_rollback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    old = target / "old.html"
    old.write_text("old", encoding="utf-8")
    transaction_id = "9" * 32
    journal = _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="old_moved",
        baseline_path=target,
    )
    old.write_text("tampered", encoding="utf-8")

    with pytest.raises(RuntimeError, match="recorded baseline"):
        with _transaction(target):
            raise AssertionError("a tampered restored target must fail closed")

    assert old.read_text(encoding="utf-8") == "tampered"
    assert journal.exists()


def test_complete_directory_publication_retries_committed_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    real_remove = publication_module._safe_remove_flat_tree

    def fail_rollback_cleanup_once(path: Path) -> None:
        if path.name.endswith(".rollback"):
            raise OSError("simulated cleanup failure")
        real_remove(path)

    monkeypatch.setattr(
        publication_module,
        "_safe_remove_flat_tree",
        fail_rollback_cleanup_once,
    )
    with _transaction(target) as transaction:
        _build_committed_tree(transaction, "new")
        transaction.commit()

    assert (target / "article.html").read_text(encoding="utf-8") == "new"
    assert (tmp_path / ".final_html.publication.json").is_file()
    assert list(tmp_path.glob(".final_html.publication.*.rollback"))

    monkeypatch.undo()
    with _transaction(target):
        pass

    assert (target / "article.html").read_text(encoding="utf-8") == "new"
    assert not (tmp_path / ".final_html.publication.json").exists()
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))


def test_complete_directory_publication_recovers_old_tree_after_crash_before_second_move(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    transaction_id = "a" * 32
    staging = tmp_path / f".final_html.publication.{transaction_id}.staging"
    rollback = tmp_path / f".final_html.publication.{transaction_id}.rollback"
    staging.mkdir()
    (staging / "article.html").write_text("partial new", encoding="utf-8")
    target.replace(rollback)
    _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="prepared",
        baseline_path=rollback,
    )

    with _transaction(target):
        assert (target / "old.html").read_text(encoding="utf-8") == "old"
        assert not staging.exists()
        assert not rollback.exists()

    assert (target / "old.html").read_text(encoding="utf-8") == "old"


def test_complete_directory_publication_recovers_after_real_process_exit_old_moved(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")

    result = _run_crashing_publication(target, phase="old_moved")

    assert result.returncode == 73, result.stderr
    assert not target.exists()
    with _transaction(target):
        assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert not (tmp_path / ".final_html.publication.json").exists()
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))
    assert not list(tmp_path.glob(".final_html.publication.*.staging"))


def test_complete_directory_publication_recovers_after_real_process_exit_new_published(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")

    result = _run_crashing_publication(target, phase="new_published")

    assert result.returncode == 74, result.stderr
    assert (target / "article.html").read_text(encoding="utf-8") == "new"
    with _transaction(target):
        assert (target / "article.html").read_text(encoding="utf-8") == "new"
    assert not (tmp_path / ".final_html.publication.json").exists()
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))
    assert not list(tmp_path.glob(".final_html.publication.*.staging"))


def test_complete_directory_publication_finishes_committed_tree_after_crash(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    transaction_id = "b" * 32
    rollback = tmp_path / f".final_html.publication.{transaction_id}.rollback"
    rollback.mkdir()
    (rollback / "old.html").write_text("old", encoding="utf-8")
    target.mkdir()
    (target / "article.html").write_text("new", encoding="utf-8")
    (target / "commit.txt").write_text(transaction_id, encoding="utf-8")
    _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="old_moved",
        baseline_path=rollback,
    )

    with _transaction(target):
        assert (target / "article.html").read_text(encoding="utf-8") == "new"
        assert not rollback.exists()

    assert (target / "article.html").read_text(encoding="utf-8") == "new"


def test_complete_directory_publication_recovers_restored_recorded_baseline(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    transaction_id = "7" * 32
    journal = _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="old_moved",
        baseline_path=target,
    )

    with _transaction(target):
        assert (target / "old.html").read_text(encoding="utf-8") == "old"
        active_journal = json.loads(journal.read_text(encoding="utf-8"))
        assert active_journal["transaction_id"] != transaction_id
        assert active_journal["phase"] == "staging"

    assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert not journal.exists()


def test_complete_directory_publication_rejects_tampered_rollback_before_cleanup(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    transaction_id = "6" * 32
    rollback = tmp_path / f".final_html.publication.{transaction_id}.rollback"
    rollback.mkdir()
    old = rollback / "old.html"
    old.write_text("old", encoding="utf-8")
    journal = _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="old_moved",
        baseline_path=rollback,
    )
    target.mkdir()
    (target / "article.html").write_text("new", encoding="utf-8")
    (target / "commit.txt").write_text(transaction_id, encoding="utf-8")
    old.write_text("tampered", encoding="utf-8")

    with pytest.raises(RuntimeError, match="recorded baseline"):
        with _transaction(target):
            raise AssertionError("a tampered rollback must fail closed")

    assert (target / "article.html").read_text(encoding="utf-8") == "new"
    assert old.read_text(encoding="utf-8") == "tampered"
    assert journal.exists()


def test_complete_directory_publication_rejects_committed_target_in_staging_phase(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    transaction_id = "5" * 32
    target.mkdir()
    (target / "article.html").write_text("new", encoding="utf-8")
    (target / "commit.txt").write_text(transaction_id, encoding="utf-8")
    journal = _write_recovery_journal(
        target,
        transaction_id=transaction_id,
        phase="staging",
        baseline_path=None,
    )

    with pytest.raises(RuntimeError, match="during journal phase staging"):
        with _transaction(target):
            raise AssertionError("an impossible committed phase must fail closed")

    assert (target / "article.html").read_text(encoding="utf-8") == "new"
    assert journal.exists()


@pytest.mark.parametrize("fail_call", range(1, 6))
@pytest.mark.parametrize("fail_after_write", [False, True])
def test_complete_directory_publication_recovers_each_journal_write_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_call: int,
    fail_after_write: bool,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    old = target / "old.html"
    old.write_text("old", encoding="utf-8")
    real_write = publication_module.write_json_atomic
    call_count = 0

    def fail_selected_write(path: Path, payload: object) -> None:
        nonlocal call_count
        call_count += 1
        should_fail = call_count == fail_call
        if should_fail and not fail_after_write:
            raise OSError("simulated journal write failure")
        real_write(path, payload)
        if should_fail:
            raise OSError("simulated journal write failure")

    monkeypatch.setattr(publication_module, "write_json_atomic", fail_selected_write)

    with pytest.raises(OSError, match="simulated journal write failure"):
        with _transaction(target) as transaction:
            _build_committed_tree(transaction, "new")
            transaction.commit()

    assert call_count == fail_call
    assert old.read_text(encoding="utf-8") == "old"
    assert not (target / "article.html").exists()

    monkeypatch.setattr(publication_module, "write_json_atomic", real_write)
    with _transaction(target):
        assert old.read_text(encoding="utf-8") == "old"

    assert old.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / ".final_html.publication.json").exists()
    assert not list(tmp_path.glob(".final_html.publication.*.staging"))
    assert not list(tmp_path.glob(".final_html.publication.*.rollback"))


def test_complete_directory_publication_rejects_malformed_journal_without_mutation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "final_html"
    target.mkdir()
    (target / "old.html").write_text("old", encoding="utf-8")
    journal = tmp_path / ".final_html.publication.json"
    journal.write_text('{"schema_version":1,"schema_version":2}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="journal"):
        with _transaction(target):
            raise AssertionError("malformed journal must fail before staging")

    assert (target / "old.html").read_text(encoding="utf-8") == "old"
    assert journal.exists()
