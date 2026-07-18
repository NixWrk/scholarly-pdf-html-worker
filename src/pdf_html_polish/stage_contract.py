from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable
from .artifact_integrity import (
    artifact_is_structurally_valid,
    FileFingerprint,
    fingerprint_file,
)

from .atomic_io import copy_file_atomic as _copy_file_atomic
from .html_stages import (
    HTML_STAGE_DIR_NAMES,
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    RawConversionValidation,
    RawConversionValidator,
    require_validated_raw_conversion_ownership,
)
from .quality_loop.run_utils import git_dirty, git_short_head, load_json, now, write_json
from .quality_loop.publication_state import (
    validate_quality_publication,
)


RAW_STAGE = RAW_STAGE_NAME
POLISH_STAGE = POLISH_STAGE_NAME
PUBLISH_REPORT_NAME = "converted_stage_publish_report.json"
STAGE_CONTRACT_REPORT_NAME = "stage_contract_report.json"


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _iter_direct_children(path: Path) -> Iterable[Path]:
    try:
        yield from path.iterdir()
    except OSError:
        return


def _iter_html_files(root: Path) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda _error: None):
        base = Path(dirpath)
        for filename in filenames:
            if filename.lower().endswith(".html"):
                yield base / filename


def _stage_dir_has_html(stage_dir: Path) -> bool:
    return any(_iter_html_files(stage_dir))


def find_stage_dirs(roots: Iterable[Path]) -> list[Path]:
    """Return stage directories recognized under converted roots.

    Both the current ``_pdf_html_polish_stages`` and legacy ``_z2m_stages``
    names are supported because the live Zotero converted tree contains older
    runs.
    """

    found: set[Path] = set()
    for raw_root in roots:
        root = _resolve(raw_root)
        if root.is_file():
            if root.parent.name in HTML_STAGE_DIR_NAMES and _stage_dir_has_html(root.parent):
                found.add(root.parent)
            continue
        if not root.exists():
            continue
        if root.name in HTML_STAGE_DIR_NAMES and _stage_dir_has_html(root):
            found.add(root)
            continue
        for dirpath, dirnames, _filenames in os.walk(root, onerror=lambda _error: None):
            for dirname in list(dirnames):
                stage_dir = (Path(dirpath) / dirname).resolve(strict=False)
                if dirname in HTML_STAGE_DIR_NAMES and _stage_dir_has_html(stage_dir):
                    found.add(stage_dir)
    return sorted(found, key=str)


def _article_dir_record(
    article_dir: Path,
    stage_dirs: list[Path],
    raw_validator: RawConversionValidator,
) -> tuple[dict[str, Any], RawConversionValidation]:
    preferred = sorted(
        stage_dirs,
        key=lambda path: (0 if path.name == "_pdf_html_polish_stages" else 1, str(path)),
    )[0]
    allowed = {
        (preferred / RAW_STAGE).resolve(strict=False),
        (preferred / POLISH_STAGE).resolve(strict=False),
    }
    html_files = sorted(
        (path.resolve(strict=False) for path in _iter_html_files(article_dir)),
        key=str,
    )
    extras = [path for path in html_files if path not in allowed]
    missing = [path for path in sorted(allowed, key=str) if not path.is_file()]
    issues: list[dict[str, Any]] = []
    if len(stage_dirs) > 1:
        issues.append(
            {
                "kind": "multiple_stage_dirs",
                "stage_dirs": [str(path) for path in sorted(stage_dirs, key=str)],
            }
        )
    if missing:
        issues.append({"kind": "missing_canonical_html", "paths": [str(path) for path in missing]})
    if extras:
        issues.append({"kind": "extra_html", "paths": [str(path) for path in extras]})
    raw_validation = raw_validator.validate(preferred / RAW_STAGE)
    if not raw_validation.valid:
        issues.append(
            {
                "kind": "invalid_raw_conversion",
                "reason": raw_validation.reason,
                "manifest_path": str(raw_validation.manifest_path),
            }
        )

    record = {
        "article_dir": str(article_dir),
        "stage_dir": str(preferred),
        "html_count": len(html_files),
        "expected_html_count": 2,
        "raw_stage_path": str(preferred / RAW_STAGE),
        "polish_stage_path": str(preferred / POLISH_STAGE),
        "extra_html_count": len(extras),
        "extra_html_paths": [str(path) for path in extras],
        "missing_canonical_count": len(missing),
        "missing_canonical_paths": [str(path) for path in missing],
        "raw_conversion_valid": raw_validation.valid,
        "raw_conversion_reason": raw_validation.reason,
        "status": "pass" if not issues else "fail",
        "issues": issues,
    }
    return record, raw_validation


def verify_stage_contract(
    roots: Iterable[Path],
    *,
    out_report: Path | None = None,
) -> dict[str, Any]:
    """Verify that every discovered article stores exactly raw + latest polish HTML."""

    roots = [_resolve(root) for root in roots]
    stage_dirs = find_stage_dirs(roots)
    grouped: dict[Path, list[Path]] = {}
    for stage_dir in stage_dirs:
        grouped.setdefault(stage_dir.parent.resolve(strict=False), []).append(stage_dir)

    raw_validator = RawConversionValidator()
    article_results = [
        _article_dir_record(article_dir, sorted(article_stage_dirs, key=str), raw_validator)
        for article_dir, article_stage_dirs in sorted(grouped.items(), key=lambda item: str(item[0]))
    ]
    articles = [record for record, _validation in article_results]
    raw_validations = [validation for _record, validation in article_results]
    raw_validation_error = ""
    if raw_validations and all(validation.valid for validation in raw_validations):
        try:
            require_validated_raw_conversion_ownership(raw_validations)
        except RuntimeError as exc:
            raw_validation_error = str(exc)
    failing_articles = [article for article in articles if article["status"] != "pass"]
    report = {
        "generated_at": now(),
        "schema_version": 2,
        "source_roots": [str(root) for root in roots],
        "code_commit": git_short_head(),
        "working_tree_dirty": git_dirty(),
        "stage_dir_count": len(stage_dirs),
        "article_count": len(articles),
        "passing_article_count": len(articles) - len(failing_articles),
        "failing_article_count": len(failing_articles),
        "extra_html_count": sum(int(article["extra_html_count"]) for article in articles),
        "missing_canonical_count": sum(int(article["missing_canonical_count"]) for article in articles),
        "invalid_raw_conversion_count": sum(
            1 for article in articles if not article["raw_conversion_valid"]
        ),
        "raw_validation_error": raw_validation_error,
        "status": "pass" if not failing_articles and not raw_validation_error else "fail",
        "articles": articles,
    }
    if out_report is not None:
        write_json(_resolve(out_report), report)
    return report


def _quality_source_manifest(quality_run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    quality_manifest = load_json(quality_run_dir / "manifest.json")
    source_run_dir_value = quality_manifest.get("source_run_dir")
    if not source_run_dir_value:
        raise ValueError(
            "Quality manifest has no source_run_dir. Run observe in converted-raw repolish mode first."
        )
    source_run_dir = _resolve(Path(str(source_run_dir_value)))
    source_manifest = load_json(source_run_dir / "manifest.json")
    return quality_manifest, source_manifest


def _source_article_by_id(source_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for article in source_manifest.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article_id") or article.get("article") or "")
        if article_id:
            if article_id in by_id:
                raise ValueError(
                    f"Source manifest contains duplicate article id: {article_id!r}."
                )
            by_id[article_id] = article
    return by_id


def _quality_article_ids(quality_manifest: dict[str, Any]) -> list[str]:
    article_ids: list[str] = []
    for article in quality_manifest.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or article.get("article_id") or "")
        if article_id:
            if article_id in article_ids:
                raise ValueError(
                    f"Quality manifest contains duplicate article id: {article_id!r}."
                )
            article_ids.append(article_id)
    return article_ids


def _backup_path_for(backup_dir: Path, path: Path) -> Path:
    drive = path.drive.replace(":", "")
    parts = [part for part in path.parts if part not in (path.anchor, path.drive, "\\")]
    return backup_dir / drive / Path(*parts)


def _backup_file(path: Path, backup_dir: Path) -> Path | None:
    if not path.is_file():
        return None
    target = _backup_path_for(backup_dir, path)
    _copy_file_atomic(path, target)
    return target


def _manifest_path_value(article: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = article.get(key)
        if value:
            return str(value)
    return ""


def _stage_extra_html_paths(stage_dir: Path) -> list[Path]:
    article_dir = stage_dir.parent
    allowed = {
        (stage_dir / RAW_STAGE).absolute(),
        (stage_dir / POLISH_STAGE).absolute(),
    }
    return sorted(
        (
            path.absolute()
            for path in _iter_html_files(article_dir)
            if path.absolute() not in allowed
        ),
        key=str,
    )




def _sealed_record_path(record: dict[str, Any], key: str) -> Path | None:
    value = record.get(key)
    if not isinstance(value, dict):
        return None
    path_value = value.get("path")
    if not isinstance(path_value, str) or not path_value:
        return None
    return _resolve(Path(path_value))


def stage_audited_polish(
    source: Path,
    destination: Path,
    sealed_record: dict[str, Any],
) -> None:
    expected = sealed_record.get("audited_polish")
    if not isinstance(expected, dict):
        raise RuntimeError("Quality publication seal has no audited polish fingerprint.")
    _copy_file_atomic(source, destination)
    fingerprint = fingerprint_file(destination, reject_symlink=True, capture_edges=True)
    if (
        fingerprint is not None
        and artifact_is_structurally_valid(destination, fingerprint)
        and fingerprint.size == expected.get("bytes")
        and fingerprint.sha256 == expected.get("sha256")
    ):
        return
    destination.unlink(missing_ok=True)
    raise RuntimeError(f"Staged audited polish does not match quality publication seal: {source}")


@dataclass(frozen=True)
class _MutationSnapshot:
    path: Path
    rollback_path: Path | None
    fingerprint: FileFingerprint | None


def _same_content(first: FileFingerprint, second: FileFingerprint) -> bool:
    return (first.size, first.sha256) == (second.size, second.sha256)


def _same_file_state(first: FileFingerprint, second: FileFingerprint) -> bool:
    return _same_content(first, second) and first.mtime_ns == second.mtime_ns


def _snapshot_mutation_paths(
    paths: Iterable[Path],
    rollback_dir: Path,
) -> list[_MutationSnapshot]:
    snapshots: list[_MutationSnapshot] = []
    seen: dict[str, Path] = {}
    for index, raw_path in enumerate(paths, start=1):
        path = _resolve(raw_path)
        key = os.path.normcase(str(path))
        previous = seen.get(key)
        if previous is not None:
            raise RuntimeError(f"Publication mutation path is ambiguous: {previous} and {path}")
        seen[key] = path
        if path.is_symlink():
            raise RuntimeError(f"Publication mutation path is a symlink: {path}")
        if not path.exists():
            snapshots.append(_MutationSnapshot(path, None, None))
            continue
        fingerprint = fingerprint_file(path, reject_symlink=True)
        if fingerprint is None:
            raise RuntimeError(f"Publication mutation path is not a stable regular file: {path}")
        rollback_path = rollback_dir / f"{index:06d}.rollback"
        _copy_file_atomic(path, rollback_path)
        rollback_fingerprint = fingerprint_file(rollback_path, reject_symlink=True)
        current_fingerprint = fingerprint_file(path, reject_symlink=True)
        if (
            rollback_fingerprint is None
            or current_fingerprint is None
            or not _same_content(rollback_fingerprint, fingerprint)
            or not _same_file_state(current_fingerprint, fingerprint)
        ):
            raise RuntimeError(f"Publication mutation path changed during snapshot: {path}")
        snapshots.append(_MutationSnapshot(path, rollback_path, fingerprint))
    return snapshots


def _require_mutation_snapshots_current(
    snapshots: Iterable[_MutationSnapshot],
) -> None:
    for snapshot in snapshots:
        if snapshot.fingerprint is None:
            if snapshot.path.exists() or snapshot.path.is_symlink():
                raise RuntimeError(
                    f"Publication mutation path appeared after preflight: {snapshot.path}"
                )
            continue
        current = fingerprint_file(snapshot.path, reject_symlink=True)
        if current is None or not _same_file_state(current, snapshot.fingerprint):
            raise RuntimeError(
                f"Publication mutation path changed after preflight: {snapshot.path}"
            )


def _rollback_mutations(snapshots: Iterable[_MutationSnapshot]) -> list[str]:
    errors: list[str] = []
    for snapshot in reversed(list(snapshots)):
        try:
            if snapshot.rollback_path is None:
                if snapshot.path.is_dir():
                    raise RuntimeError("unexpected directory occupies previously absent path")
                snapshot.path.unlink(missing_ok=True)
                continue
            _copy_file_atomic(snapshot.rollback_path, snapshot.path)
            restored = fingerprint_file(snapshot.path, reject_symlink=True)
            if (
                restored is None
                or snapshot.fingerprint is None
                or not _same_content(restored, snapshot.fingerprint)
            ):
                raise RuntimeError("restored bytes do not match rollback snapshot")
        except BaseException as exc:
            errors.append(f"{snapshot.path}: {type(exc).__name__}: {exc}")
    return errors

def publish_latest_polish_from_quality_run(
    quality_run_dir: Path,
    *,
    converted_roots: Iterable[Path] = (),
    apply: bool = False,
    prune_extra_html: bool = True,
    backup_dir: Path | None = None,
    out_report: Path | None = None,
) -> dict[str, Any]:
    """Publish final audited polish HTML back into the source converted stages.

    The source ``01.en.raw.html`` is never modified.  The final
    ``audit_tree/<article>/02.en.polish.html`` produced by the quality loop is
    copied over the matching source ``02.en.polish.html``.  Extra HTML files
    under the same article directory are reported and, with ``apply=True`` and
    ``prune_extra_html=True``, removed.
    """

    quality_run_dir = _resolve(quality_run_dir)
    quality_audit_root = _resolve(quality_run_dir / "audit_tree")
    converted_roots = [_resolve(root) for root in converted_roots]
    resolved_backup_dir = _resolve(backup_dir) if backup_dir is not None else None
    quality_manifest, source_manifest = _quality_source_manifest(quality_run_dir)
    source_by_id = _source_article_by_id(source_manifest)

    article_ids = _quality_article_ids(quality_manifest)
    records: list[dict[str, Any]] = []
    copied = 0
    quality_publication = validate_quality_publication(quality_run_dir)
    quality_publication_error = "" if quality_publication.valid else quality_publication.reason
    sealed_by_article = quality_publication.records_by_article

    skipped = 0
    removed = 0
    missing = 0
    out_of_scope = 0
    invalid_raw = 0
    invalid_quality_publication = 0
    pending: list[tuple[dict[str, Any], Path, Path, list[Path], dict[str, Any]]] = []
    raw_validator = RawConversionValidator()
    valid_raw_conversions: list[RawConversionValidation] = []

    for article_id in article_ids:
        source_article = source_by_id.get(article_id)
        audited_polish = _resolve(quality_audit_root / article_id / POLISH_STAGE)
        if source_article is None:
            missing += 1
            records.append(
                {
                    "article": article_id,
                    "status": "missing_source_manifest_article",
                    "audited_polish_path": str(audited_polish),
                }
            )
            continue

        raw_path_value = _manifest_path_value(source_article, "raw_stage_path")
        target_polish_value = _manifest_path_value(source_article, "source_polish_path", "polish_stage_path")
        if not raw_path_value or not target_polish_value:
            missing += 1
            records.append(
                {
                    "article": article_id,
                    "status": "missing_source_stage_paths",
                    "raw_stage_path": raw_path_value,
                    "target_polish_path": target_polish_value,
                    "audited_polish_path": str(audited_polish),
                }
            )
            continue

        raw_path = _resolve(Path(raw_path_value))
        target_polish = _resolve(Path(target_polish_value))
        stage_dir = raw_path.parent
        if converted_roots and not any(_is_relative_to(raw_path, root) for root in converted_roots):
            out_of_scope += 1
            records.append(
                {
                    "article": article_id,
                    "status": "outside_converted_roots",
                    "raw_stage_path": str(raw_path),
                    "target_polish_path": str(target_polish),
                }
            )
            continue

        extra_html = _stage_extra_html_paths(stage_dir) if stage_dir.exists() else []
        record: dict[str, Any] = {
            "article": article_id,
            "raw_stage_path": str(raw_path),
            "target_polish_path": str(target_polish),
            "audited_polish_path": str(audited_polish),
            "extra_html_count": len(extra_html),
            "extra_html_paths": [str(path) for path in extra_html],
            "copied": False,
            "removed_extra_html_count": 0,
            "backup_paths": [],
        }

        if not _is_relative_to(audited_polish, quality_audit_root):
            out_of_scope += 1
            record["status"] = "outside_quality_audit_tree"
            records.append(record)
            continue
        if not raw_path.is_file():
            missing += 1
            record["status"] = "missing_raw_stage"
            records.append(record)
            continue
        raw_validation = raw_validator.validate(raw_path)
        record["raw_conversion_valid"] = raw_validation.valid
        record["raw_conversion_reason"] = raw_validation.reason
        if not raw_validation.valid:
            invalid_raw += 1
            record["status"] = "invalid_raw_conversion"
            records.append(record)
            continue
        valid_raw_conversions.append(raw_validation)
        article_root = stage_dir.parent.resolve(strict=False)
        unsafe_extra_html = [
            path
            for path in extra_html
            if path.is_symlink()
            or not _is_relative_to(path.resolve(strict=False), article_root)
        ]
        if unsafe_extra_html:
            out_of_scope += 1
            record["status"] = "unsafe_extra_html_path"
            record["unsafe_extra_html_paths"] = [str(path) for path in unsafe_extra_html]
            records.append(record)
            continue
        if not audited_polish.is_file():
            missing += 1
            record["status"] = "missing_audited_polish"
            records.append(record)
            continue
        if target_polish.parent != stage_dir:
            missing += 1
            record["status"] = "target_not_beside_raw"
            records.append(record)
            continue
        sealed_record = sealed_by_article.get(article_id)
        if not quality_publication.valid or sealed_record is None:
            invalid_quality_publication += 1
            record["status"] = "invalid_quality_publication"
            record["quality_publication_reason"] = quality_publication_error or "article_not_sealed"
            records.append(record)
            continue
        sealed_paths = {
            "production_raw": _sealed_record_path(sealed_record, "production_raw"),
            "audited_polish": _sealed_record_path(sealed_record, "audited_polish"),
        }
        if (
            sealed_paths["production_raw"] != raw_path
            or sealed_paths["audited_polish"] != audited_polish
            or _resolve(Path(str(sealed_record.get("target_polish_path") or ""))) != target_polish
        ):
            invalid_quality_publication += 1
            record["status"] = "quality_publication_path_mismatch"
            records.append(record)
            continue
        if (
            raw_validation.raw_html_bytes != sealed_record["production_raw"].get("bytes")
            or raw_validation.raw_html_sha256 != sealed_record["production_raw"].get("sha256")
        ):
            invalid_quality_publication += 1
            record["status"] = "quality_publication_raw_mismatch"
            records.append(record)
            continue

        pending.append((record, audited_polish, target_polish, extra_html, sealed_record))
        records.append(record)

    raw_validation_error = ""
    if valid_raw_conversions and invalid_raw == 0:
        try:
            require_validated_raw_conversion_ownership(valid_raw_conversions)
        except RuntimeError as exc:
            raw_validation_error = str(exc)
    preflight_complete = (
        missing == 0
        and out_of_scope == 0
        and invalid_raw == 0
        and invalid_quality_publication == 0
        and not raw_validation_error
        and not quality_publication_error
    )
    if apply and preflight_complete:
        rechecked_publication = validate_quality_publication(quality_run_dir)
        if (
            not rechecked_publication.valid
            or rechecked_publication.records_by_article != sealed_by_article
        ):
            raise RuntimeError(
                "Quality publication changed between preflight and staging: "
                f"{rechecked_publication.reason or 'article_records_changed'}"
            )
        with TemporaryDirectory(prefix=".quality_publish_", dir=quality_run_dir) as staging_value:
            staging_dir = Path(staging_value)
            staged_pending: list[
                tuple[dict[str, Any], Path, Path, list[Path], dict[str, Any]]
            ] = []
            for index, (record, audited_polish, target_polish, extra_html, sealed_record) in enumerate(
                pending,
                start=1,
            ):
                staged_polish = staging_dir / f"{index:06d}.{POLISH_STAGE}"
                stage_audited_polish(audited_polish, staged_polish, sealed_record)
                staged_pending.append(
                    (record, staged_polish, target_polish, extra_html, sealed_record)
                )
            post_staging_publication = validate_quality_publication(quality_run_dir)
            if (
                not post_staging_publication.valid
                or post_staging_publication.records_by_article != sealed_by_article
            ):
                raise RuntimeError(
                    "Quality publication changed during staging: "
                    f"{post_staging_publication.reason or 'article_records_changed'}"
                )
            mutation_paths = [
                path
                for _record, _staged, target, extra_html, _sealed in staged_pending
                for path in ([target] + (extra_html if prune_extra_html else []))
            ]
            rollback_dir = staging_dir / "rollback"
            rollback_dir.mkdir()
            mutation_snapshots = _snapshot_mutation_paths(mutation_paths, rollback_dir)
            snapshots_by_path = {
                os.path.normcase(str(snapshot.path)): snapshot
                for snapshot in mutation_snapshots
            }
            post_snapshot_publication = validate_quality_publication(quality_run_dir)
            if (
                not post_snapshot_publication.valid
                or post_snapshot_publication.records_by_article != sealed_by_article
            ):
                raise RuntimeError(
                    "Quality publication changed during rollback snapshot: "
                    f"{post_snapshot_publication.reason or 'article_records_changed'}"
                )
            for record, _staged_polish, target_polish, extra_html, _sealed_record in staged_pending:
                if resolved_backup_dir is not None:
                    backup_path = _backup_file(target_polish, resolved_backup_dir)
                    if backup_path is not None:
                        record["backup_paths"].append(str(backup_path))
                    if prune_extra_html:
                        for extra_path in extra_html:
                            backup_path = _backup_file(extra_path, resolved_backup_dir)
                            if backup_path is not None:
                                record["backup_paths"].append(str(backup_path))
            try:
                _require_mutation_snapshots_current(mutation_snapshots)
                for (
                    _record,
                    staged_polish,
                    target_polish,
                    _extra_html,
                    sealed_record,
                ) in staged_pending:
                    target_snapshot = snapshots_by_path[os.path.normcase(str(target_polish))]
                    _require_mutation_snapshots_current([target_snapshot])
                    stage_audited_polish(staged_polish, target_polish, sealed_record)
                after_copy_publication = validate_quality_publication(quality_run_dir)
                if (
                    not after_copy_publication.valid
                    or after_copy_publication.records_by_article != sealed_by_article
                ):
                    raise RuntimeError(
                        "Quality publication changed while committing targets: "
                        f"{after_copy_publication.reason or 'article_records_changed'}"
                    )
                if prune_extra_html:
                    for _record, _staged, _target, extra_html, _sealed in staged_pending:
                        for extra_path in extra_html:
                            extra_snapshot = snapshots_by_path[os.path.normcase(str(extra_path))]
                            _require_mutation_snapshots_current([extra_snapshot])
                            extra_path.unlink()
                committed_publication = validate_quality_publication(quality_run_dir)
                if (
                    not committed_publication.valid
                    or committed_publication.records_by_article != sealed_by_article
                ):
                    raise RuntimeError(
                        "Quality publication changed during commit: "
                        f"{committed_publication.reason or 'article_records_changed'}"
                    )
            except BaseException as exc:
                rollback_errors = _rollback_mutations(mutation_snapshots)
                if rollback_errors:
                    raise RuntimeError(
                        "Quality publication failed and rollback was incomplete: "
                        + "; ".join(rollback_errors)
                    ) from exc
                raise
            for record, staged_polish, target_polish, extra_html, _sealed_record in staged_pending:
                copied += 1
                record["copied"] = True
                if prune_extra_html:
                    removed += len(extra_html)
                    record["removed_extra_html_count"] = len(extra_html)
                record["status"] = "published"
    elif apply or not preflight_complete:
        for record, _audited_polish, _target_polish, _extra_html, _sealed_record in pending:
            record["status"] = "blocked_by_preflight"
    else:
        skipped = len(pending)
        for record, _audited_polish, _target_polish, _extra_html, _sealed_record in pending:
            record["status"] = "dry_run"

    affected_roots = [
        Path(record["raw_stage_path"]).parent.parent
        for record in records
        if record.get("raw_stage_path") and record.get("status") != "outside_converted_roots"
    ]
    contract_report = verify_stage_contract(affected_roots) if affected_roots else {
        "status": "pass",
        "article_count": 0,
        "failing_article_count": 0,
    }
    contract_verification_status = contract_report.get("status")
    stage_contract_status = "pass" if preflight_complete and contract_verification_status == "pass" else "fail"
    report = {
        "generated_at": now(),
        "schema_version": 3,
        "mode": "apply" if apply else "dry_run",
        "quality_run_dir": str(quality_run_dir),
        "quality_code_commit": quality_manifest.get("code_commit"),
        "quality_working_tree_dirty": quality_manifest.get("working_tree_dirty"),
        "current_code_commit": git_short_head(),
        "current_working_tree_dirty": git_dirty(),
        "converted_roots": [str(root) for root in converted_roots],
        "prune_extra_html": prune_extra_html,
        "backup_dir": str(resolved_backup_dir) if resolved_backup_dir is not None else "",
        "article_count": len(article_ids),
        "published_count": copied,
        "dry_run_count": skipped,
        "missing_count": missing,
        "outside_scope_count": out_of_scope,
        "invalid_raw_conversion_count": invalid_raw,
        "raw_validation_error": raw_validation_error,
        "extra_html_count": sum(int(record.get("extra_html_count") or 0) for record in records),
        "removed_extra_html_count": removed,
        "stage_contract_status": stage_contract_status,
        "stage_contract_verification_status": contract_verification_status,
        "stage_contract_failing_article_count": contract_report.get("failing_article_count"),
        "invalid_quality_publication_count": invalid_quality_publication,
        "quality_publication_valid": quality_publication.valid,
        "quality_publication_reason": quality_publication_error,
        "quality_publication_manifest_path": str(quality_publication.manifest_path),
        "records": records,
    }
    if out_report is not None:
        write_json(_resolve(out_report), report)
    else:
        write_json(quality_run_dir / PUBLISH_REPORT_NAME, report)
    return report


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
