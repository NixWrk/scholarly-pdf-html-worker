"""Committed source snapshots for cached quality-loop repolish runs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Any, NoReturn

from pdf_html_polish.artifact_integrity import (
    FileFingerprint,
    artifact_is_structurally_valid,
    fingerprint_file,
    read_bytes_with_fingerprint,
)
from pdf_html_polish.atomic_io import write_bytes_atomic, write_json_atomic
from pdf_html_polish.html_stages import RAW_STAGE_NAME


CACHED_REPOLISH_SOURCE_SCHEMA_VERSION = 1
CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR = "_repolish_source_snapshot"
_PROFILE_SUFFIX = "citation_profile.json"
_MAX_MANIFEST_BYTES = 64 * 1024 * 1024
_MAX_PROFILE_BYTES = 64 * 1024 * 1024


class CachedRunSourceError(RuntimeError):
    """The cached source tree cannot prove one complete immutable input set."""


@dataclass(frozen=True)
class CachedRunSourceArticle:
    article_id: str
    raw_path: Path
    profile_path: Path
    raw_fingerprint: FileFingerprint
    profile_fingerprint: FileFingerprint
    manifest_article: dict[str, Any]


@dataclass(frozen=True)
class CachedRunSourceValidation:
    run_dir: Path
    manifest: dict[str, Any]
    manifest_fingerprint: FileFingerprint
    articles: tuple[CachedRunSourceArticle, ...]


def _fail(reason: str) -> NoReturn:
    raise CachedRunSourceError(f"Invalid cached repolish source: {reason}")


def _resolve(path: Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _path_key(path: Path) -> str:
    return os.path.normcase(str(_resolve(path)))


def _qualified_reason(reason: str, suffix: str) -> str:
    head, separator, detail = reason.partition(":")
    return f"{head}_{suffix}{separator}{detail}"


def _manifest_path(
    payload: dict[str, Any],
    key: str,
    *,
    expected: Path,
    reason: str,
) -> Path:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(_qualified_reason(reason, "missing"))
    candidate = Path(value).expanduser()
    if not candidate.is_absolute() or _path_key(candidate) != _path_key(expected):
        _fail(_qualified_reason(reason, "mismatch"))
    return _resolve(candidate)


def _manifest_nonnegative_int(payload: dict[str, Any], key: str, *, reason: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value < 0:
        _fail(reason)
    return value


def _manifest_count_map(
    payload: dict[str, Any], key: str, *, reason: str
) -> dict[str, int]:
    value = payload.get(key)
    if not isinstance(value, dict) or any(
        not isinstance(name, str) or not name or type(count) is not int or count < 0
        for name, count in value.items()
    ):
        _fail(reason)
    return value


def _manifest_sha256(payload: dict[str, Any], key: str, *, reason: str) -> str:
    value = payload.get(key)
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(reason)
    return value


def path_is_link_like(path: Path) -> bool:
    """Return true for symlinks and Windows junctions without following them."""

    candidate = Path(path)
    try:
        if candidate.is_symlink():
            return True
        is_junction = getattr(candidate, "is_junction", None)
        return bool(is_junction is not None and is_junction())
    except OSError:
        return True


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_json_key:{key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"nonfinite_json_constant:{value}")


def _json_object_from_bytes(
    data: bytes,
    *,
    unreadable_reason: str,
    not_object_reason: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError):
        _fail(unreadable_reason)
    if not isinstance(payload, dict):
        _fail(not_object_reason)
    return payload


def _read_json_object(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> tuple[dict[str, Any], FileFingerprint]:
    snapshot = read_bytes_with_fingerprint(path, reject_symlink=True)
    if snapshot is None:
        _fail(f"{label}_missing_empty_symlink_or_unstable")
    data, file_fingerprint = snapshot
    if file_fingerprint.size > max_bytes:
        _fail(f"{label}_too_large")
    payload = _json_object_from_bytes(
        data,
        unreadable_reason=f"{label}_json_unreadable",
        not_object_reason=f"{label}_json_not_object",
    )
    return payload, file_fingerprint


def _directory_file_names(path: Path, *, label: str) -> set[str]:
    if path_is_link_like(path) or not path.is_dir():
        _fail(f"{label}_directory_missing_or_symlink")
    names: set[str] = set()
    try:
        entries = list(path.iterdir())
    except OSError:
        _fail(f"{label}_directory_unreadable")
    for entry in entries:
        if path_is_link_like(entry) or not entry.is_file():
            _fail(f"{label}_file_set_mismatch")
        names.add(entry.name)
    return names


def _source_top_level_entry_names(run_dir: Path) -> set[str]:
    try:
        entries = list(run_dir.iterdir())
    except OSError:
        _fail("source_top_level_unreadable")
    if any(path_is_link_like(entry) for entry in entries):
        _fail("source_top_level_set_mismatch")
    return {entry.name for entry in entries}


_EXPECTED_SOURCE_TOP_LEVEL_ENTRIES = {
    "manifest.json",
    "profiles",
    "raw_cache",
}


def _same_fingerprint(left: FileFingerprint, right: FileFingerprint) -> bool:
    return (
        left.size == right.size
        and left.mtime_ns == right.mtime_ns
        and left.sha256 == right.sha256
    )


def _same_content(left: FileFingerprint, right: FileFingerprint) -> bool:
    return left.size == right.size and left.sha256 == right.sha256


def _safe_article_id(value: object) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        _fail("article_id_invalid")
    if Path(value).name != value or "/" in value or "\\" in value:
        _fail(f"article_id_unsafe:{value}")
    return value


def _profile_string(profile: dict[str, Any], key: str, *, article_id: str) -> str:
    value = profile.get(key)
    if not isinstance(value, str) or not value:
        _fail(f"profile_{key}_invalid:{article_id}")
    return value


def cached_repolish_artifact_fingerprints(
    raw_path: Path,
    profile_path: Path,
) -> dict[str, Any]:
    """Return manifest fields for exact validated raw/profile bytes."""

    raw_snapshot = read_bytes_with_fingerprint(raw_path, reject_symlink=True)
    if raw_snapshot is None:
        _fail(f"raw_invalid:{_resolve(raw_path)}")
    raw_data, raw_fingerprint = raw_snapshot
    try:
        raw_data.decode("utf-8")
    except UnicodeDecodeError:
        _fail(f"raw_invalid_utf8:{_resolve(raw_path)}")
    if not artifact_is_structurally_valid(raw_path, raw_fingerprint):
        _fail(f"raw_html_malformed:{_resolve(raw_path)}")

    profile_payload, profile_fingerprint = _read_json_object(
        profile_path,
        label="profile",
        max_bytes=_MAX_PROFILE_BYTES,
    )
    if not profile_payload:
        _fail(f"profile_json_empty:{_resolve(profile_path)}")
    return {
        "raw_cache_bytes": raw_fingerprint.size,
        "raw_cache_sha256": raw_fingerprint.sha256,
        "profile_bytes": profile_fingerprint.size,
        "profile_sha256": profile_fingerprint.sha256,
    }


def validate_cached_repolish_source(source_run_dir: Path) -> CachedRunSourceValidation:
    """Validate one complete committed cached-repolish source tree."""

    source_candidate = Path(source_run_dir).expanduser()
    if path_is_link_like(source_candidate) or not source_candidate.is_dir():
        _fail("source_run_missing_or_symlink")
    run_dir = source_candidate.resolve(strict=True)
    manifest_path = run_dir / "manifest.json"
    manifest, manifest_fingerprint = _read_json_object(
        manifest_path,
        label="manifest",
        max_bytes=_MAX_MANIFEST_BYTES,
    )
    if _source_top_level_entry_names(run_dir) != _EXPECTED_SOURCE_TOP_LEVEL_ENTRIES:
        _fail("source_top_level_set_mismatch")
    if manifest.get("source_kind") != "converted_raw_cache":
        _fail("source_kind_not_converted_raw_cache")
    source_schema_version = manifest.get("source_snapshot_schema_version")
    if (
        type(source_schema_version) is not int
        or source_schema_version != CACHED_REPOLISH_SOURCE_SCHEMA_VERSION
    ):
        _fail("source_snapshot_schema_version_invalid")

    raw_dir = run_dir / "raw_cache"
    profile_dir = run_dir / "profiles"
    _manifest_path(manifest, "out_dir", expected=run_dir, reason="out_dir")
    _manifest_path(manifest, "raw_cache_dir", expected=raw_dir, reason="raw_cache_dir")
    _manifest_path(manifest, "profile_dir", expected=profile_dir, reason="profile_dir")

    article_values = manifest.get("articles")
    if not isinstance(article_values, list) or not article_values:
        _fail("articles_missing_or_empty")
    if _manifest_nonnegative_int(
        manifest, "raw_count", reason="raw_count_invalid"
    ) != len(article_values):
        _fail("raw_count_mismatch")
    if _manifest_nonnegative_int(
        manifest, "article_count", reason="article_count_invalid"
    ) != len(article_values):
        _fail("article_count_mismatch")

    expected_raw_names: set[str] = set()
    expected_profile_names: set[str] = set()
    seen_article_ids: set[str] = set()
    seen_artifact_paths: set[str] = set()
    parsed_articles: list[tuple[str, dict[str, Any], Path, Path]] = []
    for position, value in enumerate(article_values, start=1):
        if not isinstance(value, dict):
            _fail(f"article_record_invalid:{position}")
        article = dict(value)
        article_id = _safe_article_id(article.get("article_id"))
        if article_id in seen_article_ids:
            _fail(f"duplicate_article_id:{article_id}")
        seen_article_ids.add(article_id)
        article_index = article.get("index")
        if type(article_index) is not int:
            _fail(f"article_index_invalid:{article_id}")
        if article_index != position:
            _fail(f"article_index_mismatch:{article_id}")
        expected_raw = raw_dir / f"{article_id}.{RAW_STAGE_NAME}"
        expected_profile = profile_dir / f"{article_id}.{_PROFILE_SUFFIX}"
        raw_path = _manifest_path(
            article,
            "raw_cache_path",
            expected=expected_raw,
            reason=f"raw_cache_path:{article_id}",
        )
        profile_path = _manifest_path(
            article,
            "profile_path",
            expected=expected_profile,
            reason=f"profile_path:{article_id}",
        )
        artifact_path_keys = {_path_key(raw_path), _path_key(profile_path)}
        if artifact_path_keys & seen_artifact_paths:
            _fail(f"duplicate_artifact_path:{article_id}")
        seen_artifact_paths.update(artifact_path_keys)
        expected_raw_names.add(expected_raw.name)
        expected_profile_names.add(expected_profile.name)
        parsed_articles.append((article_id, article, raw_path, profile_path))

    if _directory_file_names(raw_dir, label="raw") != expected_raw_names:
        _fail("raw_file_set_mismatch")
    if _directory_file_names(profile_dir, label="profile") != expected_profile_names:
        _fail("profile_file_set_mismatch")

    profile_status_counts: Counter[str] = Counter()
    profile_style_counts: Counter[str] = Counter()
    validated_articles: list[CachedRunSourceArticle] = []
    for article_id, article, raw_path, profile_path in parsed_articles:
        raw_snapshot = read_bytes_with_fingerprint(raw_path, reject_symlink=True)
        if raw_snapshot is None:
            _fail(f"raw_invalid:{article_id}")
        raw_data, raw_fingerprint = raw_snapshot
        expected_raw_bytes = _manifest_nonnegative_int(
            article,
            "raw_cache_bytes",
            reason=f"raw_bytes_invalid:{article_id}",
        )
        expected_raw_sha256 = _manifest_sha256(
            article,
            "raw_cache_sha256",
            reason=f"raw_sha256_invalid:{article_id}",
        )
        if (raw_fingerprint.size, raw_fingerprint.sha256) != (
            expected_raw_bytes,
            expected_raw_sha256,
        ):
            _fail(f"raw_fingerprint_mismatch:{article_id}")
        try:
            raw_data.decode("utf-8")
        except UnicodeDecodeError:
            _fail(f"raw_invalid_utf8:{article_id}")
        if not artifact_is_structurally_valid(raw_path, raw_fingerprint):
            _fail(f"raw_html_malformed:{article_id}")

        profile_snapshot = read_bytes_with_fingerprint(
            profile_path, reject_symlink=True
        )
        if profile_snapshot is None:
            _fail(f"profile_invalid:{article_id}")
        profile_data, profile_fingerprint = profile_snapshot
        expected_profile_bytes = _manifest_nonnegative_int(
            article,
            "profile_bytes",
            reason=f"profile_bytes_invalid:{article_id}",
        )
        expected_profile_sha256 = _manifest_sha256(
            article,
            "profile_sha256",
            reason=f"profile_sha256_invalid:{article_id}",
        )
        if (profile_fingerprint.size, profile_fingerprint.sha256) != (
            expected_profile_bytes,
            expected_profile_sha256,
        ):
            _fail(f"profile_fingerprint_mismatch:{article_id}")
        if profile_fingerprint.size > _MAX_PROFILE_BYTES:
            _fail(f"profile_too_large:{article_id}")
        profile = _json_object_from_bytes(
            profile_data,
            unreadable_reason=f"profile_json_unreadable:{article_id}",
            not_object_reason=f"profile_json_not_object:{article_id}",
        )
        if not profile:
            _fail(f"profile_json_not_object:{article_id}")

        status = _profile_string(profile, "status", article_id=article_id)
        style = _profile_string(profile, "style", article_id=article_id)
        confidence = _profile_string(profile, "confidence", article_id=article_id)
        if article.get("profile_status") != status:
            _fail(f"profile_status_mismatch:{article_id}")
        if article.get("citation_style") != style:
            _fail(f"citation_style_mismatch:{article_id}")
        if article.get("citation_confidence") != confidence:
            _fail(f"citation_confidence_mismatch:{article_id}")
        profile_status_counts[status] += 1
        profile_style_counts[f"{style}:{confidence}"] += 1
        validated_articles.append(
            CachedRunSourceArticle(
                article_id=article_id,
                raw_path=raw_path,
                profile_path=profile_path,
                raw_fingerprint=raw_fingerprint,
                profile_fingerprint=profile_fingerprint,
                manifest_article=article,
            )
        )

    declared_status_counts = _manifest_count_map(
        manifest,
        "profile_status_counts",
        reason="profile_status_counts_invalid",
    )
    declared_style_counts = _manifest_count_map(
        manifest,
        "profile_style_counts",
        reason="profile_style_counts_invalid",
    )
    if declared_status_counts != dict(sorted(profile_status_counts.items())):
        _fail("profile_status_counts_mismatch")
    if declared_style_counts != dict(sorted(profile_style_counts.items())):
        _fail("profile_style_counts_mismatch")
    if _directory_file_names(raw_dir, label="raw") != expected_raw_names:
        _fail("raw_file_set_changed_during_validation")
    if _directory_file_names(profile_dir, label="profile") != expected_profile_names:
        _fail("profile_file_set_changed_during_validation")
    current_manifest_fingerprint = fingerprint_file(manifest_path, reject_symlink=True)
    if current_manifest_fingerprint is None or not _same_fingerprint(
        current_manifest_fingerprint,
        manifest_fingerprint,
    ):
        _fail("manifest_changed_during_validation")
    if _source_top_level_entry_names(run_dir) != _EXPECTED_SOURCE_TOP_LEVEL_ENTRIES:
        _fail("source_top_level_changed_during_validation")
    return CachedRunSourceValidation(
        run_dir=run_dir,
        manifest=manifest,
        manifest_fingerprint=manifest_fingerprint,
        articles=tuple(validated_articles),
    )


def revalidate_cached_repolish_source_unchanged(
    expected: CachedRunSourceValidation,
) -> CachedRunSourceValidation:
    """Require the committed source and all bound artifacts to remain unchanged."""

    current = validate_cached_repolish_source(expected.run_dir)
    if not _same_content(current.manifest_fingerprint, expected.manifest_fingerprint):
        _fail("manifest_changed_during_processing")
    return current


def read_cached_repolish_article_snapshot(
    article: CachedRunSourceArticle,
) -> tuple[str, dict[str, Any], bytes, bytes]:
    """Read the exact validated article bytes immediately before processing."""

    raw_snapshot = read_bytes_with_fingerprint(article.raw_path, reject_symlink=True)
    if raw_snapshot is None or not _same_content(
        raw_snapshot[1], article.raw_fingerprint
    ):
        _fail(f"raw_changed_after_validation:{article.article_id}")
    profile_snapshot = read_bytes_with_fingerprint(
        article.profile_path, reject_symlink=True
    )
    if profile_snapshot is None or not _same_content(
        profile_snapshot[1],
        article.profile_fingerprint,
    ):
        _fail(f"profile_changed_after_validation:{article.article_id}")
    try:
        raw_html = raw_snapshot[0].decode("utf-8")
    except UnicodeDecodeError:
        _fail(f"article_snapshot_unreadable:{article.article_id}")
    profile = _json_object_from_bytes(
        profile_snapshot[0],
        unreadable_reason=f"article_snapshot_unreadable:{article.article_id}",
        not_object_reason=f"article_profile_invalid:{article.article_id}",
    )
    if not profile:
        _fail(f"article_profile_invalid:{article.article_id}")
    return raw_html, profile, raw_snapshot[0], profile_snapshot[0]


def stage_cached_repolish_source_snapshot(
    source_run_dir: Path,
    staging_dir: Path,
    published_dir: Path,
) -> dict[str, Any]:
    """Stage exact committed source bytes for later publication inside a quality run."""

    validation = validate_cached_repolish_source(source_run_dir)
    staging_candidate = Path(staging_dir).expanduser()
    published_candidate = Path(published_dir).expanduser()
    if path_is_link_like(staging_candidate):
        _fail("snapshot_staging_already_exists")
    if path_is_link_like(published_candidate):
        _fail("snapshot_target_already_exists")
    staging = _resolve(staging_candidate)
    published = _resolve(published_candidate)
    if staging.exists() or path_is_link_like(staging):
        _fail("snapshot_staging_already_exists")
    if published.exists() or path_is_link_like(published):
        _fail("snapshot_target_already_exists")
    if _path_key(staging) == _path_key(published):
        _fail("snapshot_staging_equals_target")
    try:
        staging.relative_to(published)
        _fail("snapshot_paths_overlap")
    except ValueError:
        pass
    try:
        published.relative_to(staging)
        _fail("snapshot_paths_overlap")
    except ValueError:
        pass
    source_key = _path_key(validation.run_dir)
    source_prefix = source_key + os.sep
    snapshot_keys = {_path_key(staging), _path_key(published)}
    if any(key == source_key or key.startswith(source_prefix) for key in snapshot_keys):
        _fail("snapshot_path_inside_source")

    try:
        staged_raw_dir = staging / "raw_cache"
        staged_profile_dir = staging / "profiles"
        staged_raw_dir.mkdir(parents=True)
        staged_profile_dir.mkdir(parents=True)
        snapshot_articles: list[dict[str, Any]] = []
        for article in validation.articles:
            raw_snapshot = read_bytes_with_fingerprint(
                article.raw_path, reject_symlink=True
            )
            profile_snapshot = read_bytes_with_fingerprint(
                article.profile_path, reject_symlink=True
            )
            if raw_snapshot is None or not _same_content(
                raw_snapshot[1], article.raw_fingerprint
            ):
                _fail(f"raw_changed_during_snapshot:{article.article_id}")
            if profile_snapshot is None or not _same_content(
                profile_snapshot[1], article.profile_fingerprint
            ):
                _fail(f"profile_changed_during_snapshot:{article.article_id}")
            staged_raw = staged_raw_dir / article.raw_path.name
            staged_profile = staged_profile_dir / article.profile_path.name
            write_bytes_atomic(staged_raw, raw_snapshot[0])
            write_bytes_atomic(staged_profile, profile_snapshot[0])
            staged_raw_fingerprint = fingerprint_file(staged_raw, reject_symlink=True)
            staged_profile_fingerprint = fingerprint_file(
                staged_profile, reject_symlink=True
            )
            if staged_raw_fingerprint is None or not _same_content(
                staged_raw_fingerprint,
                article.raw_fingerprint,
            ):
                _fail(f"staged_raw_mismatch:{article.article_id}")
            if staged_profile_fingerprint is None or not _same_content(
                staged_profile_fingerprint,
                article.profile_fingerprint,
            ):
                _fail(f"staged_profile_mismatch:{article.article_id}")
            snapshot_article = dict(article.manifest_article)
            snapshot_article.update(
                {
                    "raw_cache_path": str(
                        published / "raw_cache" / article.raw_path.name
                    ),
                    "profile_path": str(
                        published / "profiles" / article.profile_path.name
                    ),
                    "source_raw_cache_path": str(article.raw_path),
                    "source_profile_path": str(article.profile_path),
                }
            )
            snapshot_articles.append(snapshot_article)

        current_manifest_fingerprint = fingerprint_file(
            validation.run_dir / "manifest.json",
            reject_symlink=True,
        )
        if current_manifest_fingerprint is None or not _same_fingerprint(
            current_manifest_fingerprint,
            validation.manifest_fingerprint,
        ):
            _fail("manifest_changed_during_snapshot")

        snapshot_manifest = dict(validation.manifest)
        previous_origin = snapshot_manifest.get("source_snapshot_origin")
        snapshot_manifest.update(
            {
                "out_dir": str(published),
                "raw_cache_dir": str(published / "raw_cache"),
                "profile_dir": str(published / "profiles"),
                "articles": snapshot_articles,
                "source_snapshot_origin": {
                    "run_dir": str(validation.run_dir),
                    "manifest_path": str(validation.run_dir / "manifest.json"),
                    "manifest_bytes": validation.manifest_fingerprint.size,
                    "manifest_sha256": validation.manifest_fingerprint.sha256,
                },
            }
        )
        if isinstance(previous_origin, dict):
            snapshot_manifest["source_snapshot_ancestor_origin"] = previous_origin
        write_json_atomic(staging / "manifest.json", snapshot_manifest)
        return snapshot_manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
