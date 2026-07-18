"""Fail-closed publication seal for audited quality-loop HTML."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, NoReturn

from pdf_html_polish.artifact_integrity import (
    artifact_is_structurally_valid,
    fingerprint_file,
    read_bytes_with_fingerprint,
)
from pdf_html_polish.atomic_io import write_json_atomic
from pdf_html_polish.html_stages import (
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    RawConversionValidation,
    RawConversionValidator,
    require_validated_raw_conversion_ownership,
)
from pdf_html_polish.quality_loop.cached_run_state import (
    CachedRunSourceError,
    path_is_link_like,
    validate_cached_repolish_source,
)


QUALITY_PUBLICATION_MANIFEST_NAME = "quality_publication_manifest.json"
QUALITY_PUBLICATION_MANIFEST_SCHEMA_VERSION = 2
AUDIT_REPORT_NAME = "audit_full_checks.json"
GATE_REPORT_NAME = "quality_gate_report.json"
_MAX_PUBLICATION_MANIFEST_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class QualityPublicationValidation:
    manifest_path: Path
    valid: bool
    reason: str
    records_by_article: dict[str, dict[str, Any]]


def _resolve(path: Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _path_key(path: Path) -> str:
    return os.path.normcase(str(_resolve(path)))


def _lexical_path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(Path(path).expanduser())))


def _path_has_link_like_component(path: Path) -> bool:
    candidate = Path(path).expanduser()
    return any(
        path_is_link_like(component)
        for component in (candidate, *candidate.parents)
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        _resolve(path).relative_to(_resolve(root))
    except ValueError:
        return False
    return True


def _file_record(path: Path, *, require_html: bool = False) -> tuple[dict[str, Any] | None, str]:
    candidate = Path(path).expanduser()
    if _path_has_link_like_component(candidate):
        return None, f"link_like_path:{candidate}"
    resolved = _resolve(candidate)
    snapshot = read_bytes_with_fingerprint(candidate, reject_symlink=True)
    if snapshot is None:
        return None, f"missing_empty_symlink_or_unstable:{resolved}"
    data, fingerprint = snapshot
    if require_html and not artifact_is_structurally_valid(resolved, fingerprint):
        return None, f"malformed_html:{resolved}"
    if require_html:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return None, f"invalid_utf8:{resolved}"
    return {
        "path": str(resolved),
        "bytes": fingerprint.size,
        "sha256": fingerprint.sha256,
    }, ""


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_json_key:{key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"nonfinite_json_constant:{value}")


def _json_document(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    resolved = _resolve(path)
    snapshot = read_bytes_with_fingerprint(resolved, reject_symlink=True)
    if snapshot is None:
        return {}, None, f"json_missing_empty_symlink_or_unstable:{resolved}"
    data, fingerprint = snapshot
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return {}, None, f"json_unreadable:{resolved}"
    if not isinstance(payload, dict):
        return {}, None, f"json_not_object:{resolved}"
    return payload, {
        "path": str(resolved),
        "bytes": fingerprint.size,
        "sha256": fingerprint.sha256,
    }, ""


def _article_map(
    payload: dict[str, Any],
    *,
    id_key: str,
    label: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in payload.get("articles") or []:
        if not isinstance(value, dict):
            errors.append(f"{label}_article_not_object")
            continue
        article_id = str(value.get(id_key) or "")
        if not article_id:
            errors.append(f"{label}_article_id_missing")
            continue
        if article_id in result:
            errors.append(f"{label}_article_id_duplicate:{article_id}")
            continue
        result[article_id] = value
    return result


def _manifest_path(item: dict[str, Any], key: str) -> Path | None:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    return _resolve(path) if path.is_absolute() else None


def _audit_fingerprint_matches(
    audit_article: dict[str, Any],
    *,
    prefix: str,
    record: dict[str, Any],
) -> bool:
    return bool(
        audit_article.get(f"{prefix}_stage_bytes") == record["bytes"]
        and audit_article.get(f"{prefix}_stage_sha256") == record["sha256"]
    )


def _raw_chain_record(
    *,
    article_id: str,
    quality_article: dict[str, Any],
    source_article: dict[str, Any],
    run_dir: Path,
    source_run_dir: Path | None,
    raw_validator: RawConversionValidator,
    raw_validations: list[RawConversionValidation],
    errors: list[str],
) -> dict[str, Any] | None:
    production_raw = _manifest_path(source_article, "raw_stage_path")
    source_cached_raw = _manifest_path(source_article, "raw_cache_path")
    quality_cached_raw = _manifest_path(quality_article, "raw_cache_path")
    target_polish_value = source_article.get("source_polish_path")
    declared_target_polish = (
        Path(target_polish_value).expanduser()
        if isinstance(target_polish_value, str) and target_polish_value.strip()
        else None
    )
    target_polish = (
        declared_target_polish
        if declared_target_polish is not None and declared_target_polish.is_absolute()
        else None
    )
    required_paths = {
        "production_raw": production_raw,
        "source_cached_raw": source_cached_raw,
        "quality_cached_raw": quality_cached_raw,
        "target_polish": target_polish,
    }
    missing_fields = [name for name, path in required_paths.items() if path is None]
    if missing_fields:
        errors.append(f"article_paths_missing:{article_id}:{','.join(missing_fields)}")
        return None
    assert production_raw is not None
    assert source_cached_raw is not None
    assert quality_cached_raw is not None
    assert target_polish is not None
    expected_target_polish = production_raw.parent / POLISH_STAGE_NAME
    if _lexical_path_key(target_polish) != _lexical_path_key(expected_target_polish):
        errors.append(f"target_polish_path_mismatch:{article_id}")
        return None
    if _path_has_link_like_component(target_polish):
        errors.append(f"target_polish_link_like:{article_id}")
        return None
    target_polish = expected_target_polish
    if source_run_dir is None or not _is_within(source_cached_raw, source_run_dir / "raw_cache"):
        errors.append(f"source_cached_raw_outside_run:{article_id}")
        return None
    if not _is_within(quality_cached_raw, run_dir / "raw_cache"):
        errors.append(f"quality_cached_raw_outside_run:{article_id}")
        return None

    raw_validation = raw_validator.validate(production_raw)
    if not raw_validation.valid:
        errors.append(f"production_raw_invalid:{article_id}:{raw_validation.reason}")
        return None
    file_specs = {
        "production_raw": production_raw,
        "source_cached_raw": source_cached_raw,
        "quality_cached_raw": quality_cached_raw,
    }
    file_records: dict[str, dict[str, Any]] = {}
    for name, path in file_specs.items():
        record, record_error = _file_record(path, require_html=True)
        if record is None:
            errors.append(f"{name}_invalid:{article_id}:{record_error}")
        else:
            file_records[name] = record
    if len(file_records) != len(file_specs):
        return None
    raw_signatures = {
        (record["bytes"], record["sha256"])
        for record in file_records.values()
    }
    if len(raw_signatures) != 1:
        errors.append(f"raw_snapshot_mismatch:{article_id}")
        return None
    raw_signature = next(iter(raw_signatures))
    if raw_signature != (raw_validation.raw_html_bytes, raw_validation.raw_html_sha256):
        errors.append(f"production_manifest_raw_mismatch:{article_id}")
        return None
    raw_validations.append(raw_validation)
    return {
        "article_id": article_id,
        **file_records,
        "target_polish_path": str(target_polish),
        "raw_conversion_manifest_path": str(raw_validation.manifest_path),
    }


def build_quality_publication_snapshot(
    quality_run_dir: Path,
) -> tuple[dict[str, Any], list[str]]:
    """Build deterministic evidence for the exact audited bytes to publish."""

    run_dir = _resolve(quality_run_dir)
    errors: list[str] = []
    quality_manifest, quality_manifest_record, error = _json_document(run_dir / "manifest.json")
    if error:
        errors.append(error)
    audit_report, audit_report_record, error = _json_document(run_dir / AUDIT_REPORT_NAME)
    if error:
        errors.append(error)
    gate_report, gate_report_record, error = _json_document(run_dir / GATE_REPORT_NAME)
    if error:
        errors.append(error)

    source_run_value = quality_manifest.get("source_run_dir")
    source_run_path = Path(source_run_value).expanduser() if isinstance(source_run_value, str) else None
    source_run_dir = (
        _resolve(source_run_path)
        if source_run_path is not None and source_run_path.is_absolute()
        else None
    )
    source_run_is_local = source_run_dir is not None and _is_within(source_run_dir, run_dir)
    if source_run_path is None:
        errors.append("quality_source_run_dir_missing")
    elif not source_run_path.is_absolute():
        errors.append("quality_source_run_dir_not_absolute")
    elif not source_run_is_local:
        errors.append("quality_source_run_dir_outside_quality_run")
    source_manifest: dict[str, Any] = {}
    source_manifest_record: dict[str, Any] | None = None
    if source_run_is_local and source_run_dir is not None:
        source_manifest, source_manifest_record, error = _json_document(source_run_dir / "manifest.json")
        if error:
            errors.append(error)
        try:
            source_validation = validate_cached_repolish_source(source_run_dir)
        except (CachedRunSourceError, OSError, ValueError) as exc:
            errors.append(f"source_snapshot_invalid:{exc}")
        else:
            source_manifest = source_validation.manifest
            validated_fingerprint = source_validation.manifest_fingerprint
            if source_manifest_record is None or (
                source_manifest_record.get("bytes"),
                source_manifest_record.get("sha256"),
            ) != (
                validated_fingerprint.size,
                validated_fingerprint.sha256,
            ):
                errors.append("source_manifest_changed_during_publication_preflight")
            if (
                quality_manifest.get("source_manifest_bytes"),
                quality_manifest.get("source_manifest_sha256"),
            ) != (
                validated_fingerprint.size,
                validated_fingerprint.sha256,
            ):
                errors.append("quality_source_manifest_fingerprint_mismatch")

    if quality_manifest.get("source_kind") != "cached_raw_repolish":
        errors.append("quality_source_kind_not_cached_raw_repolish")
    if source_manifest.get("source_kind") != "converted_raw_cache":
        errors.append("source_kind_not_converted_raw_cache")
    if audit_report.get("audit_status") != "complete":
        errors.append("audit_report_not_complete")
    gate_status = gate_report.get("status")
    if gate_status != "pass":
        gate_status_label = (
            gate_status if isinstance(gate_status, str) and gate_status else "missing_or_invalid"
        )
        errors.append(f"quality_gate_not_pass:{gate_status_label}")
    gate_failures = gate_report.get("failures")
    if not isinstance(gate_failures, list):
        errors.append("quality_gate_failures_invalid")
    elif gate_status == "pass" and gate_failures:
        errors.append("quality_gate_pass_has_failures")

    quality_articles = _article_map(
        quality_manifest,
        id_key="article",
        label="quality",
        errors=errors,
    )
    skipped_articles = _article_map(
        {"articles": quality_manifest.get("skipped_articles") or []},
        id_key="article",
        label="quality_skipped",
        errors=errors,
    )
    source_articles = _article_map(
        source_manifest,
        id_key="article_id",
        label="source",
        errors=errors,
    )
    audit_articles = _article_map(
        audit_report,
        id_key="article",
        label="audit",
        errors=errors,
    )
    missing_audit_articles = sorted(set(quality_articles) - set(audit_articles))
    extra_audit_articles = sorted(set(audit_articles) - set(quality_articles))
    if missing_audit_articles or extra_audit_articles:
        errors.append(
            "audit_article_set_mismatch:"
            f"missing={','.join(missing_audit_articles)}:"
            f"extra={','.join(extra_audit_articles)}"
        )
    processed_skipped_overlap = sorted(set(quality_articles) & set(skipped_articles))
    if processed_skipped_overlap:
        errors.append(
            "quality_processed_skipped_overlap:"
            + ",".join(processed_skipped_overlap)
        )
    covered_articles = set(quality_articles) | set(skipped_articles)
    missing_source_articles = sorted(covered_articles - set(source_articles))
    extra_source_articles = sorted(set(source_articles) - covered_articles)
    if missing_source_articles or extra_source_articles:
        errors.append(
            "source_article_set_mismatch:"
            f"missing={','.join(missing_source_articles)}:"
            f"extra={','.join(extra_source_articles)}"
        )
    if not covered_articles:
        errors.append("quality_coverage_empty")

    raw_validator = RawConversionValidator()
    raw_validations: list[RawConversionValidation] = []
    publication_records: list[dict[str, Any]] = []
    for article_id in sorted(quality_articles):
        quality_article = quality_articles[article_id]
        source_article = source_articles.get(article_id)
        audit_article = audit_articles.get(article_id)
        if source_article is None:
            errors.append(f"source_article_missing:{article_id}")
            continue
        if audit_article is None:
            errors.append(f"audit_article_missing:{article_id}")
            continue

        common_record = _raw_chain_record(
            article_id=article_id,
            quality_article=quality_article,
            source_article=source_article,
            run_dir=run_dir,
            source_run_dir=source_run_dir,
            raw_validator=raw_validator,
            raw_validations=raw_validations,
            errors=errors,
        )
        if common_record is None:
            continue
        expected_audit_dir = _resolve(run_dir / "audit_tree" / article_id)
        audit_raw = expected_audit_dir / RAW_STAGE_NAME
        audited_polish = expected_audit_dir / POLISH_STAGE_NAME
        if not _is_within(expected_audit_dir, run_dir / "audit_tree"):
            errors.append(f"audit_article_path_outside_run:{article_id}")
            continue
        file_specs = {
            "audit_raw": audit_raw,
            "audited_polish": audited_polish,
        }
        audit_file_records: dict[str, dict[str, Any]] = {}
        for name, path in file_specs.items():
            record, record_error = _file_record(path, require_html=True)
            if record is None:
                errors.append(f"{name}_invalid:{article_id}:{record_error}")
            else:
                audit_file_records[name] = record
        if len(audit_file_records) != len(file_specs):
            continue
        production_raw_record = common_record["production_raw"]
        audit_raw_record = audit_file_records["audit_raw"]
        if (
            audit_raw_record["bytes"],
            audit_raw_record["sha256"],
        ) != (
            production_raw_record["bytes"],
            production_raw_record["sha256"],
        ):
            errors.append(f"raw_snapshot_mismatch:{article_id}")
            continue

        audit_raw_path = _manifest_path(audit_article, "raw_stage_path")
        audit_polish_path = _manifest_path(audit_article, "polish_stage_path")
        if _path_key(audit_raw_path or Path()) != _path_key(audit_raw):
            errors.append(f"audit_raw_path_mismatch:{article_id}")
            continue
        if _path_key(audit_polish_path or Path()) != _path_key(audited_polish):
            errors.append(f"audit_polish_path_mismatch:{article_id}")
            continue
        if not _audit_fingerprint_matches(
            audit_article,
            prefix="raw",
            record=audit_file_records["audit_raw"],
        ):
            errors.append(f"audit_raw_fingerprint_mismatch:{article_id}")
            continue
        if not _audit_fingerprint_matches(
            audit_article,
            prefix="polish",
            record=audit_file_records["audited_polish"],
        ):
            errors.append(f"audit_polish_fingerprint_mismatch:{article_id}")
            continue

        publication_records.append(
            {
                **common_record,
                **audit_file_records,
                "publication_kind": "audited",
                "final_polish": audit_file_records["audited_polish"],
            }
        )

    skipped_records: list[dict[str, Any]] = []
    for article_id in sorted(skipped_articles):
        source_article = source_articles.get(article_id)
        if source_article is None:
            errors.append(f"source_article_missing:{article_id}")
            continue
        common_record = _raw_chain_record(
            article_id=article_id,
            quality_article=skipped_articles[article_id],
            source_article=source_article,
            run_dir=run_dir,
            source_run_dir=source_run_dir,
            raw_validator=raw_validator,
            raw_validations=raw_validations,
            errors=errors,
        )
        if common_record is None:
            continue
        fallback_polish = Path(common_record["target_polish_path"])
        fallback_record, fallback_error = _file_record(
            fallback_polish,
            require_html=True,
        )
        if fallback_record is None:
            errors.append(
                f"fallback_polish_invalid:{article_id}:{fallback_error}"
            )
            continue
        skipped_records.append(
            {
                **common_record,
                "publication_kind": "skipped_fallback",
                "fallback_polish": fallback_record,
                "final_polish": fallback_record,
            }
        )

    if raw_validations:
        try:
            require_validated_raw_conversion_ownership(raw_validations)
        except RuntimeError as exc:
            errors.append(f"raw_conversion_ownership_invalid:{exc}")

    snapshot = {
        "quality_run_dir": str(run_dir),
        "quality_manifest": quality_manifest_record,
        "source_manifest": source_manifest_record,
        "audit_report": audit_report_record,
        "gate_report": gate_report_record,
        "gate_status": gate_status,
        "articles": publication_records,
        "skipped_articles": skipped_records,
    }
    return snapshot, sorted(set(errors))


def quality_publication_manifest_path(quality_run_dir: Path) -> Path:
    return _resolve(quality_run_dir) / QUALITY_PUBLICATION_MANIFEST_NAME


def seal_quality_publication(quality_run_dir: Path) -> dict[str, Any]:
    """Atomically seal the final audited quality-run bytes for publication."""

    manifest_path = quality_publication_manifest_path(quality_run_dir)
    manifest_path.unlink(missing_ok=True)
    snapshot, errors = build_quality_publication_snapshot(quality_run_dir)
    payload = {
        "schema_version": QUALITY_PUBLICATION_MANIFEST_SCHEMA_VERSION,
        "status": "completed" if not errors else "invalid",
        "sealed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "errors": errors,
        "snapshot": snapshot,
    }
    write_json_atomic(manifest_path, payload)
    return payload


def validate_quality_publication(quality_run_dir: Path) -> QualityPublicationValidation:
    """Validate the seal and every file fingerprint before production mutation."""

    manifest_path = quality_publication_manifest_path(quality_run_dir)
    seal_snapshot = read_bytes_with_fingerprint(manifest_path, reject_symlink=True)
    if seal_snapshot is None:
        return QualityPublicationValidation(manifest_path, False, "manifest_missing_or_unstable", {})
    seal_bytes, seal_fingerprint = seal_snapshot
    if seal_fingerprint.size > _MAX_PUBLICATION_MANIFEST_BYTES:
        return QualityPublicationValidation(manifest_path, False, "manifest_too_large", {})
    try:
        payload = json.loads(
            seal_bytes.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return QualityPublicationValidation(manifest_path, False, "manifest_unreadable", {})
    if not isinstance(payload, dict):
        return QualityPublicationValidation(manifest_path, False, "manifest_not_object", {})
    if payload.get("schema_version") != QUALITY_PUBLICATION_MANIFEST_SCHEMA_VERSION:
        return QualityPublicationValidation(manifest_path, False, "schema_version_invalid", {})
    if payload.get("status") != "completed":
        return QualityPublicationValidation(manifest_path, False, "status_not_completed", {})
    expected_snapshot = payload.get("snapshot")
    if not isinstance(expected_snapshot, dict):
        return QualityPublicationValidation(manifest_path, False, "snapshot_missing", {})
    current_snapshot, errors = build_quality_publication_snapshot(quality_run_dir)
    if errors:
        return QualityPublicationValidation(
            manifest_path,
            False,
            "snapshot_invalid:" + ";".join(errors[:20]),
            {},
        )
    if current_snapshot != expected_snapshot:
        return QualityPublicationValidation(manifest_path, False, "snapshot_changed", {})
    current_seal_fingerprint = fingerprint_file(manifest_path, reject_symlink=True)
    if (
        current_seal_fingerprint is None
        or current_seal_fingerprint.size != seal_fingerprint.size
        or current_seal_fingerprint.mtime_ns != seal_fingerprint.mtime_ns
        or current_seal_fingerprint.sha256 != seal_fingerprint.sha256
    ):
        return QualityPublicationValidation(manifest_path, False, "manifest_changed_during_validation", {})
    records: list[Any] = []
    for key in ("articles", "skipped_articles"):
        values = current_snapshot.get(key)
        if not isinstance(values, list):
            return QualityPublicationValidation(
                manifest_path,
                False,
                f"{key}_records_invalid",
                {},
            )
        records.extend(values)
    by_article: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            return QualityPublicationValidation(manifest_path, False, "article_records_ambiguous", {})
        article_id = record.get("article_id")
        if not isinstance(article_id, str) or not article_id or article_id in by_article:
            return QualityPublicationValidation(manifest_path, False, "article_records_ambiguous", {})
        publication_kind = record.get("publication_kind")
        final_polish = record.get("final_polish")
        if publication_kind not in {"audited", "skipped_fallback"}:
            return QualityPublicationValidation(manifest_path, False, "publication_kind_invalid", {})
        if not isinstance(final_polish, dict):
            return QualityPublicationValidation(
                manifest_path,
                False,
                f"final_polish_record_invalid:{article_id}",
                {},
            )
        by_article[article_id] = record
    return QualityPublicationValidation(manifest_path, True, "", by_article)
