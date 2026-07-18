from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import pdf_html_polish.quality_loop.enrichment_snapshot as enrichment_snapshot_module
from pdf_html_polish.quality_loop.enrichment_snapshot import (
    ENRICHMENT_FILES_DIR_NAME,
    ENRICHMENT_MANIFEST_NAME,
    EnrichmentSnapshotError,
    initialize_enrichment_snapshot,
    snapshot_enrichment_file,
    validate_enrichment_snapshot,
)


def _manifest(run_dir: Path) -> dict:
    return json.loads(
        (run_dir / "_enrichment_snapshot" / ENRICHMENT_MANIFEST_NAME).read_text(
            encoding="utf-8"
        )
    )


def _source(tmp_path: Path, name: str = "source.pdf", data: bytes = b"pdf-bytes") -> Path:
    source = tmp_path / name
    source.write_bytes(data)
    return source


def test_initialize_and_validate_empty_snapshot(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"

    snapshot_dir = initialize_enrichment_snapshot(run_dir)
    validation = validate_enrichment_snapshot(run_dir)

    assert snapshot_dir == run_dir / "_enrichment_snapshot"
    assert validation.artifact_count == 0
    assert validation.usage_keys == frozenset()


def test_snapshot_records_content_addressed_file_and_dedupes_uses(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    source = _source(tmp_path)

    first = snapshot_enrichment_file(run_dir, "alpha", "p62_pdf", source)
    second = snapshot_enrichment_file(run_dir, "alpha", "p62_pdf", source)
    third = snapshot_enrichment_file(run_dir, "beta", "p62_pdf", source)
    validation = validate_enrichment_snapshot(run_dir)

    assert first == second == third
    assert first.read_bytes() == b"pdf-bytes"
    assert first.name == f"{hashlib.sha256(b'pdf-bytes').hexdigest()}.pdf"
    assert validation.artifact_count == 1
    assert validation.usage_keys == frozenset(
        {("alpha", "p62_pdf"), ("beta", "p62_pdf")}
    )
    uses = _manifest(run_dir)["artifacts"][0]["uses"]
    assert len(uses) == 2


def test_append_does_not_rehash_unrelated_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    first = snapshot_enrichment_file(
        run_dir,
        "alpha",
        "p62_pdf",
        _source(tmp_path, "first.pdf", b"first-pdf"),
    )
    real_fingerprint_file = enrichment_snapshot_module.fingerprint_file

    def reject_first_artifact_rehash(path: Path, **kwargs):
        if Path(path).resolve(strict=False) == first:
            raise AssertionError("append must not rehash unrelated snapshot blobs")
        return real_fingerprint_file(path, **kwargs)

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "fingerprint_file",
        reject_first_artifact_rehash,
    )

    snapshot_enrichment_file(
        run_dir,
        "beta",
        "p96_pdf",
        _source(tmp_path, "second.pdf", b"second-pdf"),
    )


def test_validate_rejects_tampered_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifact = snapshot_enrichment_file(
        run_dir,
        "alpha",
        "pdf_reference",
        _source(tmp_path),
    )
    artifact.write_bytes(b"tampered")

    with pytest.raises(EnrichmentSnapshotError, match="artifact_fingerprint_mismatch"):
        validate_enrichment_snapshot(run_dir)


def test_validate_rejects_untracked_extra_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    snapshot_dir = initialize_enrichment_snapshot(run_dir)
    (snapshot_dir / ENRICHMENT_FILES_DIR_NAME / "extra.bin").write_bytes(b"extra")

    with pytest.raises(EnrichmentSnapshotError, match="artifact_file_set_mismatch"):
        validate_enrichment_snapshot(run_dir)


@pytest.mark.parametrize(
    "alias_kind",
    ["snapshot_dir", "artifact_path", "usage_source_path"],
)
def test_validate_rejects_noncanonical_manifest_paths(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    run_dir = tmp_path / "run"
    artifact = snapshot_enrichment_file(
        run_dir,
        "alpha",
        "p62_pdf",
        _source(tmp_path),
    )
    manifest_path = run_dir / "_enrichment_snapshot" / ENRICHMENT_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if alias_kind == "snapshot_dir":
        snapshot_dir = run_dir / "_enrichment_snapshot"
        manifest["snapshot_dir"] = str(
            snapshot_dir.parent / "unused" / ".." / snapshot_dir.name
        )
        expected_error = "snapshot_dir_not_canonical"
    elif alias_kind == "artifact_path":
        manifest["artifacts"][0]["path"] = str(
            artifact.parent / "unused" / ".." / artifact.name
        )
        expected_error = "artifact_path_not_canonical"
    else:
        source_path = Path(manifest["artifacts"][0]["uses"][0]["source_path"])
        manifest["artifacts"][0]["uses"][0]["source_path"] = str(
            source_path.parent / "unused" / ".." / source_path.name
        )
        expected_error = "usage_source_path_not_canonical"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(EnrichmentSnapshotError, match=expected_error):
        validate_enrichment_snapshot(run_dir)


@pytest.mark.parametrize(
    "manifest_text",
    [
        '{"schema_version":1,"schema_version":1}\n',
        '{"schema_version":1,"probe":NaN}\n',
        "not-json\n",
    ],
)
def test_validate_rejects_non_strict_manifest(
    tmp_path: Path,
    manifest_text: str,
) -> None:
    run_dir = tmp_path / "run"
    snapshot_dir = initialize_enrichment_snapshot(run_dir)
    (snapshot_dir / ENRICHMENT_MANIFEST_NAME).write_text(
        manifest_text,
        encoding="utf-8",
    )

    with pytest.raises(EnrichmentSnapshotError, match="manifest_unreadable"):
        validate_enrichment_snapshot(run_dir)


def test_append_rejects_malformed_existing_usage_before_copy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    first = snapshot_enrichment_file(
        run_dir,
        "alpha",
        "p62_pdf",
        _source(tmp_path, "first.pdf", b"first"),
    )
    manifest_path = run_dir / "_enrichment_snapshot" / ENRICHMENT_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0]["uses"][0]["source_bytes"] = "invalid"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    malformed_manifest = manifest_path.read_bytes()

    with pytest.raises(EnrichmentSnapshotError, match="usage_source_bytes_invalid"):
        snapshot_enrichment_file(
            run_dir,
            "beta",
            "p96_pdf",
            _source(tmp_path, "second.pdf", b"second"),
        )

    assert list((run_dir / "_enrichment_snapshot" / ENRICHMENT_FILES_DIR_NAME).iterdir()) == [first]
    assert manifest_path.read_bytes() == malformed_manifest


def test_snapshot_rejects_addition_after_publication_seal(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    initialize_enrichment_snapshot(run_dir)
    (run_dir / "quality_publication_manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(EnrichmentSnapshotError, match="snapshot_sealed"):
        snapshot_enrichment_file(
            run_dir,
            "alpha",
            "pdf_reference",
            _source(tmp_path),
        )


def test_snapshot_rejects_link_like_publication_seal_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    initialize_enrichment_snapshot(run_dir)
    seal_path = run_dir / "quality_publication_manifest.json"
    real_path_is_link_like = enrichment_snapshot_module.path_is_link_like

    def seal_is_link_like(path: Path) -> bool:
        if Path(path) == seal_path:
            return True
        return real_path_is_link_like(path)

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "path_is_link_like",
        seal_is_link_like,
    )

    with pytest.raises(EnrichmentSnapshotError, match="snapshot_sealed"):
        snapshot_enrichment_file(
            run_dir,
            "alpha",
            "p62_pdf",
            _source(tmp_path),
        )


def test_snapshot_rejects_publication_seal_created_during_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    initialize_enrichment_snapshot(run_dir)
    seal_path = run_dir / "quality_publication_manifest.json"
    real_update_state = enrichment_snapshot_module._snapshot_update_state

    def update_state_then_seal(candidate_run_dir: Path):
        state = real_update_state(candidate_run_dir)
        seal_path.write_text("{}\n", encoding="utf-8")
        return state

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "_snapshot_update_state",
        update_state_then_seal,
    )

    with pytest.raises(EnrichmentSnapshotError, match="snapshot_sealed_during_update"):
        snapshot_enrichment_file(
            run_dir,
            "alpha",
            "p62_pdf",
            _source(tmp_path),
        )



def test_snapshot_discards_new_blob_when_manifest_changes_during_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    snapshot_dir = initialize_enrichment_snapshot(run_dir)
    manifest_path = snapshot_dir / ENRICHMENT_MANIFEST_NAME
    real_update_state = enrichment_snapshot_module._snapshot_update_state

    def update_state_then_rewrite_manifest(candidate_run_dir: Path):
        state = real_update_state(candidate_run_dir)
        manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
        return state

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "_snapshot_update_state",
        update_state_then_rewrite_manifest,
    )

    with pytest.raises(EnrichmentSnapshotError, match="manifest_changed_during_update"):
        snapshot_enrichment_file(
            run_dir,
            "alpha",
            "p62_pdf",
            _source(tmp_path),
        )

    assert list((snapshot_dir / ENRICHMENT_FILES_DIR_NAME).iterdir()) == []


def test_snapshot_discards_new_blob_when_recording_usage_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    snapshot_dir = initialize_enrichment_snapshot(run_dir)

    def fail_usage(**kwargs):
        raise RuntimeError("usage failure")

    monkeypatch.setattr(enrichment_snapshot_module, "_usage", fail_usage)

    with pytest.raises(RuntimeError, match="usage failure"):
        snapshot_enrichment_file(
            run_dir,
            "alpha",
            "p62_pdf",
            _source(tmp_path),
        )

    assert list((snapshot_dir / ENRICHMENT_FILES_DIR_NAME).iterdir()) == []
    assert _manifest(run_dir)["artifacts"] == []


def test_snapshot_discards_linked_blob_when_copy_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    snapshot_dir = initialize_enrichment_snapshot(run_dir)
    source = _source(tmp_path)
    destination = (
        snapshot_dir
        / ENRICHMENT_FILES_DIR_NAME
        / f"{hashlib.sha256(source.read_bytes()).hexdigest()}.pdf"
    )
    real_fingerprint_file = enrichment_snapshot_module.fingerprint_file

    def reject_published_blob(path: Path, **kwargs):
        if Path(path) == destination:
            return None
        return real_fingerprint_file(path, **kwargs)

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "fingerprint_file",
        reject_published_blob,
    )

    with pytest.raises(EnrichmentSnapshotError, match="snapshot_copy_invalid"):
        snapshot_enrichment_file(
            run_dir,
            "alpha",
            "p62_pdf",
            source,
        )

    assert list((snapshot_dir / ENRICHMENT_FILES_DIR_NAME).iterdir()) == []
    assert _manifest(run_dir)["artifacts"] == []


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink support unavailable")
def test_initialize_rejects_symlinked_run_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "run-alias"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(EnrichmentSnapshotError, match="run_dir_link_like"):
        initialize_enrichment_snapshot(alias)


def test_validate_rejects_link_like_files_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    snapshot_dir = initialize_enrichment_snapshot(run_dir)
    files_dir = snapshot_dir / ENRICHMENT_FILES_DIR_NAME
    real_path_is_link_like = enrichment_snapshot_module.path_is_link_like

    def files_directory_is_link_like(path: Path) -> bool:
        if Path(path) == files_dir:
            return True
        return real_path_is_link_like(path)

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "path_is_link_like",
        files_directory_is_link_like,
    )

    with pytest.raises(EnrichmentSnapshotError, match="files_dir_link_like"):
        validate_enrichment_snapshot(run_dir)


def test_snapshot_rejects_source_replaced_between_stat_and_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    source = _source(tmp_path, data=b"original")
    replacement = _source(tmp_path, "replacement.pdf", b"replaced")
    original_stat = source.stat()
    os.utime(
        replacement,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )
    real_open = enrichment_snapshot_module._open_source_for_snapshot
    swapped = False

    def swap_before_open(path: Path):
        nonlocal swapped
        if Path(path) == source and not swapped:
            swapped = True
            os.replace(replacement, source)
        return real_open(path)

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "_open_source_for_snapshot",
        swap_before_open,
    )

    with pytest.raises(EnrichmentSnapshotError, match="source_changed_during_snapshot"):
        snapshot_enrichment_file(run_dir, "alpha", "p62_pdf", source)


def test_snapshot_rejects_untracked_destination_created_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    source = _source(tmp_path)
    initialize_enrichment_snapshot(run_dir)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = (
        run_dir
        / "_enrichment_snapshot"
        / ENRICHMENT_FILES_DIR_NAME
        / f"{digest}.pdf"
    )
    real_update_state = enrichment_snapshot_module._snapshot_update_state

    def update_state_then_inject(candidate_run_dir: Path):
        state = real_update_state(candidate_run_dir)
        destination.write_bytes(source.read_bytes())
        return state

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "_snapshot_update_state",
        update_state_then_inject,
    )

    with pytest.raises(EnrichmentSnapshotError, match="untracked_snapshot_artifact"):
        snapshot_enrichment_file(run_dir, "alpha", "p62_pdf", source)

    assert _manifest(run_dir)["artifacts"] == []


def test_snapshot_rejects_tracked_destination_removed_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    source = _source(tmp_path)
    artifact = snapshot_enrichment_file(run_dir, "alpha", "p62_pdf", source)
    real_update_state = enrichment_snapshot_module._snapshot_update_state

    def update_state_then_remove(candidate_run_dir: Path):
        state = real_update_state(candidate_run_dir)
        artifact.unlink()
        return state

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "_snapshot_update_state",
        update_state_then_remove,
    )

    with pytest.raises(EnrichmentSnapshotError, match="tracked_snapshot_artifact_missing"):
        snapshot_enrichment_file(run_dir, "beta", "p62_pdf", source)


def test_snapshot_rejects_link_like_source_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    source = _source(tmp_path)
    real_path_is_link_like = enrichment_snapshot_module.path_is_link_like

    def source_is_link_like(path: Path) -> bool:
        if Path(path) == source:
            return True
        return real_path_is_link_like(path)

    monkeypatch.setattr(
        enrichment_snapshot_module,
        "path_is_link_like",
        source_is_link_like,
    )

    with pytest.raises(EnrichmentSnapshotError, match="source_link_like"):
        snapshot_enrichment_file(run_dir, "alpha", "p62_pdf", source)
