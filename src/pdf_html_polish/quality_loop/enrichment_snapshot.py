"""Run-local immutable snapshots for files that enrich polished HTML."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, BinaryIO, NoReturn
from uuid import uuid4

from pdf_html_polish.artifact_integrity import FileFingerprint, fingerprint_file, read_bytes_with_fingerprint
from pdf_html_polish.atomic_io import write_json_atomic
from pdf_html_polish.quality_loop.cached_run_state import path_is_link_like


ENRICHMENT_SNAPSHOT_DIR_NAME = "_enrichment_snapshot"
ENRICHMENT_MANIFEST_NAME = "manifest.json"
ENRICHMENT_FILES_DIR_NAME = "files"
ENRICHMENT_SNAPSHOT_SCHEMA_VERSION = 1
QUALITY_PUBLICATION_MANIFEST_NAME = "quality_publication_manifest.json"
_MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_PURPOSE_RE = re.compile(r"[a-z][a-z0-9_]{1,63}")
_SUFFIX_RE = re.compile(r"\.[a-z0-9]{1,10}")
_LOCK = threading.RLock()


class EnrichmentSnapshotError(ValueError):
    """Raised when enrichment provenance is missing, mutable, or ambiguous."""


@dataclass(frozen=True)
class EnrichmentSnapshotValidation:
    run_dir: Path
    snapshot_dir: Path
    manifest_path: Path
    manifest: dict[str, Any]
    manifest_fingerprint: FileFingerprint
    artifact_count: int
    usage_keys: frozenset[tuple[str, str]]


def enrichment_snapshot_dir(run_dir: Path) -> Path:
    return Path(run_dir).expanduser().resolve(strict=False) / ENRICHMENT_SNAPSHOT_DIR_NAME


def _path_key(path: Path) -> str:
    return os.path.normcase(str(Path(path).expanduser().resolve(strict=False)))


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(str(Path(path).expanduser())))


def _has_link_like_component(path: Path) -> bool:
    lexical = _lexical_absolute(path)
    return any(path_is_link_like(component) for component in (lexical, *lexical.parents))


def _validated_run_dir(run_dir: Path) -> Path:
    lexical = _lexical_absolute(run_dir)
    if _has_link_like_component(lexical):
        _fail(f"run_dir_link_like:{lexical}")
    return lexical.resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve(strict=False).relative_to(Path(root).resolve(strict=False))
    except ValueError:
        return False
    return True


def _fail(reason: str) -> NoReturn:
    raise EnrichmentSnapshotError(reason)


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_json_key:{key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"nonfinite_json_constant:{value}")


def _read_manifest(snapshot_dir: Path) -> tuple[dict[str, Any], FileFingerprint]:
    manifest_path = snapshot_dir / ENRICHMENT_MANIFEST_NAME
    snapshot = read_bytes_with_fingerprint(manifest_path, reject_symlink=True)
    if snapshot is None:
        _fail(f"manifest_missing_empty_or_unstable:{manifest_path}")
    data, fingerprint = snapshot
    if fingerprint.size > _MAX_MANIFEST_BYTES:
        _fail("manifest_too_large")
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise EnrichmentSnapshotError("manifest_unreadable") from exc
    if not isinstance(payload, dict):
        _fail("manifest_not_object")
    return payload, fingerprint


def _initial_manifest(snapshot_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": ENRICHMENT_SNAPSHOT_SCHEMA_VERSION,
        "kind": "quality_enrichment_snapshot",
        "snapshot_dir": str(snapshot_dir.resolve(strict=False)),
        "artifacts": [],
    }


def initialize_enrichment_snapshot(run_dir: Path) -> Path:
    """Create an empty snapshot or validate the already-created one."""

    run_dir = _validated_run_dir(run_dir)
    snapshot_dir = enrichment_snapshot_dir(run_dir)
    with _LOCK:
        if snapshot_dir.exists() or path_is_link_like(snapshot_dir):
            validate_enrichment_snapshot(run_dir)
            return snapshot_dir
        if _has_link_like_component(run_dir):
            _fail(f"run_dir_link_like:{run_dir}")
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        files_dir = snapshot_dir / ENRICHMENT_FILES_DIR_NAME
        files_dir.mkdir(exist_ok=False)
        write_json_atomic(
            snapshot_dir / ENRICHMENT_MANIFEST_NAME,
            _initial_manifest(snapshot_dir),
        )
    return snapshot_dir


def _normalized_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if _SUFFIX_RE.fullmatch(suffix) else ".bin"


def _open_source_for_snapshot(path: Path) -> BinaryIO:
    return path.open("rb")


def _source_path_handle_identity(
    value: os.stat_result,
) -> tuple[int, int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(stat.S_IFMT(value.st_mode)),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def _source_version(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        *_source_path_handle_identity(value),
        int(value.st_ctime_ns),
    )


def _copy_source_snapshot(
    source_path: Path,
    files_dir: Path,
    tracked_artifact_paths: frozenset[str],
) -> tuple[Path, FileFingerprint, bool]:
    lexical_source = _lexical_absolute(source_path)
    if _has_link_like_component(lexical_source):
        _fail(f"source_link_like:{lexical_source}")
    try:
        before = lexical_source.stat()
    except OSError as exc:
        raise EnrichmentSnapshotError(f"source_unreadable:{lexical_source}") from exc
    if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
        _fail(f"source_not_regular_nonempty:{lexical_source}")

    temporary = files_dir / f".snapshot.{os.getpid()}.{uuid4().hex}.tmp"
    digest = hashlib.sha256()
    copied_bytes = 0
    destination: Path | None = None
    artifact_created = False
    try:
        with _open_source_for_snapshot(lexical_source) as source, temporary.open("xb") as target:
            opened_before = os.fstat(source.fileno())
            if _source_path_handle_identity(before) != _source_path_handle_identity(
                opened_before
            ):
                _fail(f"source_changed_during_snapshot:{lexical_source}")
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                copied_bytes += len(chunk)
                target.write(chunk)
            opened_after = os.fstat(source.fileno())
            target.flush()
            os.fsync(target.fileno())
        try:
            after = lexical_source.stat()
        except OSError as exc:
            raise EnrichmentSnapshotError(f"source_changed_during_snapshot:{lexical_source}") from exc
        if (
            _has_link_like_component(lexical_source)
            or _source_version(before) != _source_version(after)
            or _source_version(opened_before) != _source_version(opened_after)
            or _source_path_handle_identity(after)
            != _source_path_handle_identity(opened_after)
            or copied_bytes != int(before.st_size)
        ):
            _fail(f"source_changed_during_snapshot:{lexical_source}")
        sha256 = digest.hexdigest()
        destination = files_dir / f"{sha256}{_normalized_suffix(lexical_source)}"
        destination_key = _path_key(destination)
        destination_tracked = destination_key in tracked_artifact_paths
        destination_present = destination.exists() or path_is_link_like(destination)
        if destination_present and not destination_tracked:
            _fail(f"untracked_snapshot_artifact:{destination}")
        if destination_tracked and not destination_present:
            _fail(f"tracked_snapshot_artifact_missing:{destination}")
        if destination_tracked:
            existing = fingerprint_file(destination, reject_symlink=True)
            if (
                existing is None
                or existing.size != copied_bytes
                or existing.sha256 != sha256
            ):
                _fail(f"snapshot_content_collision:{destination}")
        else:
            try:
                os.link(temporary, destination)
                artifact_created = True
            except FileExistsError as exc:
                raise EnrichmentSnapshotError(
                    f"untracked_snapshot_artifact:{destination}"
                ) from exc
            except OSError as exc:
                raise EnrichmentSnapshotError(f"snapshot_publish_failed:{destination}") from exc
        fingerprint = fingerprint_file(destination, reject_symlink=True)
        if (
            fingerprint is None
            or fingerprint.size != copied_bytes
            or fingerprint.sha256 != sha256
        ):
            _fail(f"snapshot_copy_invalid:{destination}")
        result = (destination.resolve(strict=False), fingerprint, artifact_created)
        artifact_created = False
        return result
    finally:
        temporary.unlink(missing_ok=True)
        if artifact_created and destination is not None:
            destination.unlink(missing_ok=True)


def _usage(
    *,
    article: str,
    purpose: str,
    source_path: Path,
    fingerprint: FileFingerprint,
) -> dict[str, Any]:
    return {
        "article": article,
        "purpose": purpose,
        "source_path": str(_lexical_absolute(source_path)),
        "source_bytes": fingerprint.size,
        "source_sha256": fingerprint.sha256,
    }


def _usage_key(value: dict[str, Any]) -> tuple[str, str, str, int, str]:
    return (
        str(value.get("article") or ""),
        str(value.get("purpose") or ""),
        str(value.get("source_path") or ""),
        int(value.get("source_bytes") or 0),
        str(value.get("source_sha256") or ""),
    )


def _tracked_artifact_paths(
    artifacts: list[Any],
    files_dir: Path,
) -> frozenset[str]:
    tracked: set[str] = set()
    seen_usage_records: set[tuple[str, str, str, int, str]] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"path", "bytes", "sha256", "uses"}:
            _fail("artifact_record_invalid")
        path_value = artifact.get("path")
        if not isinstance(path_value, str) or not path_value:
            _fail("artifact_path_invalid")
        path = Path(path_value).expanduser()
        if not path.is_absolute() or not _is_within(path, files_dir):
            _fail(f"artifact_path_outside_snapshot:{path}")
        resolved = path.resolve(strict=False)
        canonical = files_dir.resolve(strict=False) / resolved.name
        if path_value != str(canonical):
            _fail(f"artifact_path_not_canonical:{path}")
        path_key = _path_key(resolved)
        if path_key in tracked:
            _fail(f"artifact_path_duplicate:{path}")
        size = _required_int(
            artifact.get("bytes"),
            reason=f"artifact_bytes_invalid:{resolved}",
            positive=True,
        )
        sha256 = artifact.get("sha256")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            _fail(f"artifact_sha256_invalid:{resolved}")
        if not resolved.name.startswith(sha256 + "."):
            _fail(f"artifact_name_mismatch:{resolved}")
        uses = artifact.get("uses")
        if not isinstance(uses, list) or not uses:
            _fail(f"artifact_uses_invalid:{resolved}")
        for usage in uses:
            if not isinstance(usage, dict) or set(usage) != {
                "article",
                "purpose",
                "source_path",
                "source_bytes",
                "source_sha256",
            }:
                _fail(f"artifact_usage_invalid:{resolved}")
            article = usage.get("article")
            purpose = usage.get("purpose")
            source_path = usage.get("source_path")
            source_bytes = _required_int(
                usage.get("source_bytes"),
                reason=f"usage_source_bytes_invalid:{resolved}",
                positive=True,
            )
            source_sha256 = usage.get("source_sha256")
            if not isinstance(article, str) or not article:
                _fail(f"usage_article_invalid:{resolved}")
            if not isinstance(purpose, str) or not _PURPOSE_RE.fullmatch(purpose):
                _fail(f"usage_purpose_invalid:{resolved}")
            if not isinstance(source_path, str) or not Path(source_path).is_absolute():
                _fail(f"usage_source_path_invalid:{resolved}")
            if source_path != str(_lexical_absolute(Path(source_path))):
                _fail(f"usage_source_path_not_canonical:{resolved}")
            if source_bytes != size or source_sha256 != sha256:
                _fail(f"usage_source_fingerprint_mismatch:{resolved}")
            usage_record = _usage_key(usage)
            if usage_record in seen_usage_records:
                _fail(f"usage_duplicate:{resolved}")
            seen_usage_records.add(usage_record)
        tracked.add(path_key)
    return frozenset(tracked)


def _snapshot_update_state(
    run_dir: Path,
) -> tuple[
    Path,
    Path,
    dict[str, Any],
    FileFingerprint,
    list[Any],
    frozenset[str],
]:
    snapshot_dir = enrichment_snapshot_dir(run_dir)
    if not snapshot_dir.exists() and not path_is_link_like(snapshot_dir):
        initialize_enrichment_snapshot(run_dir)
    files_dir = snapshot_dir / ENRICHMENT_FILES_DIR_NAME
    if _has_link_like_component(snapshot_dir):
        _fail(f"snapshot_dir_link_like:{snapshot_dir}")
    if _has_link_like_component(files_dir):
        _fail(f"files_dir_link_like:{files_dir}")
    if not snapshot_dir.is_dir() or not files_dir.is_dir():
        _fail(f"snapshot_missing:{snapshot_dir}")
    if {path.name for path in snapshot_dir.iterdir()} != {
        ENRICHMENT_MANIFEST_NAME,
        ENRICHMENT_FILES_DIR_NAME,
    }:
        _fail("snapshot_top_level_set_mismatch")

    manifest, manifest_fingerprint = _read_manifest(snapshot_dir)
    if set(manifest) != {"schema_version", "kind", "snapshot_dir", "artifacts"}:
        _fail("manifest_keys_invalid")
    if manifest.get("schema_version") != ENRICHMENT_SNAPSHOT_SCHEMA_VERSION:
        _fail("schema_version_invalid")
    if manifest.get("kind") != "quality_enrichment_snapshot":
        _fail("kind_invalid")
    if manifest.get("snapshot_dir") != str(snapshot_dir.resolve(strict=False)):
        _fail("snapshot_dir_not_canonical")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        _fail("artifacts_not_list")
    tracked_artifact_paths = _tracked_artifact_paths(artifacts, files_dir)
    actual_artifact_paths: set[str] = set()
    for path in files_dir.iterdir():
        if path_is_link_like(path) or not path.is_file():
            _fail(f"files_entry_invalid:{path}")
        actual_artifact_paths.add(_path_key(path))
    if actual_artifact_paths != set(tracked_artifact_paths):
        _fail("artifact_file_set_mismatch")
    return (
        snapshot_dir,
        files_dir,
        manifest,
        manifest_fingerprint,
        artifacts,
        tracked_artifact_paths,
    )


def _publication_seal_present(run_dir: Path) -> bool:
    seal_path = run_dir / QUALITY_PUBLICATION_MANIFEST_NAME
    return seal_path.exists() or path_is_link_like(seal_path)


def snapshot_enrichment_file(
    run_dir: Path,
    article: str,
    purpose: str,
    source_path: Path,
) -> Path:
    """Copy one actually used external input and atomically record its provenance."""

    run_dir = _validated_run_dir(run_dir)
    article = str(article or "").strip()
    purpose = str(purpose or "").strip()
    if not article:
        _fail("article_missing")
    if not _PURPOSE_RE.fullmatch(purpose):
        _fail(f"purpose_invalid:{purpose}")
    with _LOCK:
        if _publication_seal_present(run_dir):
            _fail("snapshot_sealed")
        (
            snapshot_dir,
            files_dir,
            manifest,
            manifest_fingerprint,
            artifacts,
            tracked_artifact_paths,
        ) = _snapshot_update_state(run_dir)

        if _publication_seal_present(run_dir):
            _fail("snapshot_sealed_during_update")
        source_candidate = _lexical_absolute(source_path)
        destination: Path
        fingerprint: FileFingerprint
        existing_artifact: dict[str, Any] | None = None
        artifact_created = False
        if _is_within(source_candidate, files_dir):
            source_resolved = source_candidate.resolve(strict=False)
            existing_artifact = next(
                (
                    item
                    for item in artifacts
                    if isinstance(item, dict)
                    and _path_key(Path(str(item.get("path") or ""))) == _path_key(source_resolved)
                ),
                None,
            )
            if existing_artifact is None:
                _fail(f"untracked_snapshot_artifact:{source_resolved}")
            fingerprint = fingerprint_file(source_resolved, reject_symlink=True)  # type: ignore[assignment]
            if fingerprint is None:
                _fail(f"managed_snapshot_invalid:{source_resolved}")
            destination = source_resolved
        else:
            destination, fingerprint, artifact_created = _copy_source_snapshot(
                source_candidate,
                files_dir,
                tracked_artifact_paths,
            )
            existing_artifact = next(
                (
                    item
                    for item in artifacts
                    if isinstance(item, dict)
                    and _path_key(Path(str(item.get("path") or ""))) == _path_key(destination)
                ),
                None,
            )

        try:
            if existing_artifact is None:
                existing_artifact = {
                    "path": str(destination),
                    "bytes": fingerprint.size,
                    "sha256": fingerprint.sha256,
                    "uses": [],
                }
                artifacts.append(existing_artifact)
            elif (
                existing_artifact.get("bytes") != fingerprint.size
                or existing_artifact.get("sha256") != fingerprint.sha256
            ):
                _fail(f"manifest_artifact_fingerprint_mismatch:{destination}")

            uses = existing_artifact.get("uses")
            if not isinstance(uses, list):
                _fail(f"artifact_uses_not_list:{destination}")
            usage = _usage(
                article=article,
                purpose=purpose,
                source_path=source_candidate,
                fingerprint=fingerprint,
            )
            if _usage_key(usage) not in {
                _usage_key(item) for item in uses if isinstance(item, dict)
            }:
                uses.append(usage)
                uses.sort(key=_usage_key)
            artifacts.sort(key=lambda item: str(item.get("path") if isinstance(item, dict) else ""))
            if _publication_seal_present(run_dir):
                _fail("snapshot_sealed_during_update")
            current_manifest_fingerprint = fingerprint_file(
                snapshot_dir / ENRICHMENT_MANIFEST_NAME,
                reject_symlink=True,
            )
            if (
                current_manifest_fingerprint is None
                or current_manifest_fingerprint.size != manifest_fingerprint.size
                or current_manifest_fingerprint.mtime_ns != manifest_fingerprint.mtime_ns
                or current_manifest_fingerprint.sha256 != manifest_fingerprint.sha256
            ):
                _fail("manifest_changed_during_update")
            write_json_atomic(snapshot_dir / ENRICHMENT_MANIFEST_NAME, manifest)
            artifact_created = False
            return destination
        finally:
            if artifact_created:
                destination.unlink(missing_ok=True)


def _required_int(value: Any, *, reason: str, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        _fail(reason)
    return value


def validate_enrichment_snapshot(run_dir: Path) -> EnrichmentSnapshotValidation:
    """Validate exact manifest coverage and every immutable enrichment artifact."""

    run_dir = _validated_run_dir(run_dir)
    snapshot_dir = enrichment_snapshot_dir(run_dir)
    files_dir = snapshot_dir / ENRICHMENT_FILES_DIR_NAME
    manifest_path = snapshot_dir / ENRICHMENT_MANIFEST_NAME
    if _has_link_like_component(snapshot_dir):
        _fail(f"snapshot_dir_link_like:{snapshot_dir}")
    if _has_link_like_component(files_dir):
        _fail(f"files_dir_link_like:{files_dir}")
    if not snapshot_dir.is_dir() or not files_dir.is_dir():
        _fail(f"snapshot_missing:{snapshot_dir}")
    top_entries = {path.name for path in snapshot_dir.iterdir()}
    if top_entries != {ENRICHMENT_MANIFEST_NAME, ENRICHMENT_FILES_DIR_NAME}:
        _fail("snapshot_top_level_set_mismatch")

    manifest, manifest_fingerprint = _read_manifest(snapshot_dir)
    if set(manifest) != {"schema_version", "kind", "snapshot_dir", "artifacts"}:
        _fail("manifest_keys_invalid")
    if manifest.get("schema_version") != ENRICHMENT_SNAPSHOT_SCHEMA_VERSION:
        _fail("schema_version_invalid")
    if manifest.get("kind") != "quality_enrichment_snapshot":
        _fail("kind_invalid")
    if manifest.get("snapshot_dir") != str(snapshot_dir.resolve(strict=False)):
        _fail("snapshot_dir_not_canonical")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        _fail("artifacts_not_list")

    expected_paths: set[str] = set()
    usage_keys: set[tuple[str, str]] = set()
    seen_usage_records: set[tuple[str, str, str, int, str]] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"path", "bytes", "sha256", "uses"}:
            _fail("artifact_record_invalid")
        path_value = artifact.get("path")
        if not isinstance(path_value, str) or not path_value:
            _fail("artifact_path_invalid")
        path = Path(path_value).expanduser()
        if not path.is_absolute() or not _is_within(path, files_dir):
            _fail(f"artifact_path_outside_snapshot:{path}")
        resolved = path.resolve(strict=False)
        path_key = _path_key(resolved)
        if path_key in expected_paths:
            _fail(f"artifact_path_duplicate:{resolved}")
        canonical = files_dir.resolve(strict=False) / resolved.name
        if path_value != str(canonical):
            _fail(f"artifact_path_not_canonical:{path}")
        expected_paths.add(path_key)
        size = _required_int(artifact.get("bytes"), reason=f"artifact_bytes_invalid:{resolved}", positive=True)
        sha256 = artifact.get("sha256")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            _fail(f"artifact_sha256_invalid:{resolved}")
        if not resolved.name.startswith(sha256 + "."):
            _fail(f"artifact_name_mismatch:{resolved}")
        fingerprint = fingerprint_file(resolved, reject_symlink=True)
        if fingerprint is None or (fingerprint.size, fingerprint.sha256) != (size, sha256):
            _fail(f"artifact_fingerprint_mismatch:{resolved}")
        uses = artifact.get("uses")
        if not isinstance(uses, list) or not uses:
            _fail(f"artifact_uses_invalid:{resolved}")
        for usage in uses:
            if not isinstance(usage, dict) or set(usage) != {
                "article",
                "purpose",
                "source_path",
                "source_bytes",
                "source_sha256",
            }:
                _fail(f"artifact_usage_invalid:{resolved}")
            article = usage.get("article")
            purpose = usage.get("purpose")
            source_path = usage.get("source_path")
            source_bytes = _required_int(
                usage.get("source_bytes"),
                reason=f"usage_source_bytes_invalid:{resolved}",
                positive=True,
            )
            source_sha256 = usage.get("source_sha256")
            if not isinstance(article, str) or not article:
                _fail(f"usage_article_invalid:{resolved}")
            if not isinstance(purpose, str) or not _PURPOSE_RE.fullmatch(purpose):
                _fail(f"usage_purpose_invalid:{resolved}")
            if not isinstance(source_path, str) or not Path(source_path).is_absolute():
                _fail(f"usage_source_path_invalid:{resolved}")
            if source_path != str(_lexical_absolute(Path(source_path))):
                _fail(f"usage_source_path_not_canonical:{resolved}")
            if source_bytes != size or source_sha256 != sha256:
                _fail(f"usage_source_fingerprint_mismatch:{resolved}")
            usage_record = _usage_key(usage)
            if usage_record in seen_usage_records:
                _fail(f"usage_duplicate:{resolved}")
            seen_usage_records.add(usage_record)
            usage_keys.add((article, purpose))

    actual_paths: set[str] = set()
    for path in files_dir.iterdir():
        if path_is_link_like(path) or not path.is_file():
            _fail(f"files_entry_invalid:{path}")
        actual_paths.add(_path_key(path))
    if actual_paths != expected_paths:
        _fail("artifact_file_set_mismatch")
    return EnrichmentSnapshotValidation(
        run_dir=run_dir,
        snapshot_dir=snapshot_dir,
        manifest_path=manifest_path,
        manifest=manifest,
        manifest_fingerprint=manifest_fingerprint,
        artifact_count=len(artifacts),
        usage_keys=frozenset(usage_keys),
    )
