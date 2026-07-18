from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, BinaryIO, NoReturn

from pdf_html_polish.artifact_integrity import FileFingerprint
from pdf_html_polish.quality_loop.audit_command_provenance import (
    AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES,
    AuditCommandProvenanceError,
    validate_audit_command_report,
)
from pdf_html_polish.quality_loop.cached_run_state import path_is_link_like
from pdf_html_polish.quality_loop.gates import evaluate_quality_gate
from pdf_html_polish.quality_loop.pdf_evidence import (
    PDF_PROBLEM_EVIDENCE_ARTICLE_FIELDS,
    PDF_PROBLEM_EVIDENCE_CANDIDATE_ALLOWED_FIELDS,
    PDF_PROBLEM_EVIDENCE_CANDIDATE_REQUIRED_FIELDS,
    PDF_PROBLEM_EVIDENCE_INPUTS_NAME,
    PDF_PROBLEM_EVIDENCE_INPUTS_SCHEMA_VERSION,
    PDF_PROBLEM_EVIDENCE_PROVENANCE_SCHEMA_VERSION,
    PDF_PROBLEM_EVIDENCE_REPORT_FIELDS,
    PDF_PROBLEM_EVIDENCE_REPORT_SCHEMA_VERSION,
    PDF_PROBLEM_EVIDENCE_UNAVAILABLE_ARTICLE_FIELDS,
)
from pdf_html_polish.quality_loop.review_workflow import (
    ARTICLE_REVIEW_ARTICLE_FIELDS,
    ARTICLE_REVIEW_PROVENANCE_SCHEMA_VERSION,
    ARTICLE_REVIEW_REPORT_FIELDS,
    ARTICLE_REVIEW_REPORT_SCHEMA_VERSION,
    UNRESOLVED_MANDATORY_REVIEW_STATUSES,
    relative_review_href,
)
from pdf_html_polish.quality_loop.run_utils import parse_canonical_utc_timestamp


GATE_REPORT_SCHEMA_VERSION = 1
GATE_INPUT_CONTRACT_SCHEMA_VERSION = 1
GATE_CONFIG_SNAPSHOT_SCHEMA_VERSION = 1
GATE_CONFIG_SNAPSHOT_NAME = "quality_gate_config_snapshot.json"
ASSESSMENT_NAME = "assessment.json"
QUALITY_HISTORY_ENTRY_NAME = "quality_history_entry.json"
QUALITY_PREVIOUS_ENTRY_SNAPSHOT_NAME = "quality_previous_entry_snapshot.json"
QUALITY_PREVIOUS_ENTRY_SNAPSHOT_SCHEMA_VERSION = 1
QUALITY_COMPARE_NAME = "quality_compare.json"
ARTICLE_REVIEW_REPORT_NAME = "article_review_report.json"
AUDIT_REPORT_NAME = "audit_full_checks.json"
AUDIT_COMMAND_REPORT_NAME = "audit_command_report.json"
PDF_PROBLEM_EVIDENCE_REPORT_NAME = "pdf_problem_evidence_report.json"

_MAX_CONFIG_BYTES = 2 * 1024 * 1024
_MAX_INPUT_BYTES = 256 * 1024 * 1024
_SHA256_HEX = frozenset("0123456789abcdef")
_INPUT_SPECS = (
    ("gate_config", GATE_CONFIG_SNAPSHOT_NAME, False),
    ("assessment", ASSESSMENT_NAME, True),
    ("quality_history_entry", QUALITY_HISTORY_ENTRY_NAME, True),
    ("quality_previous_entry", QUALITY_PREVIOUS_ENTRY_SNAPSHOT_NAME, True),
    ("quality_compare", QUALITY_COMPARE_NAME, True),
    ("article_review", ARTICLE_REVIEW_REPORT_NAME, True),
    ("audit_report", AUDIT_REPORT_NAME, True),
    ("audit_command", AUDIT_COMMAND_REPORT_NAME, True),
    ("pdf_problem_evidence", PDF_PROBLEM_EVIDENCE_REPORT_NAME, True),
)


class GateProvenanceError(ValueError):
    pass


@dataclass(frozen=True)
class GateConfigSnapshot:
    path: Path
    config: dict[str, Any]
    source_record: dict[str, Any]
    fingerprint: FileFingerprint


@dataclass(frozen=True)
class GateReportProvenanceValidation:
    input_records: tuple[dict[str, Any], ...]


def _fail(reason: str) -> NoReturn:
    raise GateProvenanceError(reason)


def _require_canonical_utc_timestamp(value: Any, *, reason: str) -> str:
    if not isinstance(value, str):
        _fail(reason)
    try:
        parse_canonical_utc_timestamp(value)
    except ValueError:
        _fail(reason)
    return value


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_json_key:{key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"nonfinite_json_constant:{value}")


def _json_value_from_bytes(data: bytes, *, label: str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError):
        _fail(f"{label}_json_unreadable")


def _json_object_from_bytes(data: bytes, *, label: str) -> dict[str, Any]:
    payload = _json_value_from_bytes(data, label=label)
    if not isinstance(payload, dict):
        _fail(f"{label}_json_not_object")
    return payload


def _canonical(path: Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _lexical_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(Path(path).expanduser())))


def _same_path(left: Path, right: Path) -> bool:
    return _lexical_key(left) == _lexical_key(right)


def _path_has_link_like_component(path: Path) -> bool:
    candidate = Path(path).expanduser()
    return any(path_is_link_like(component) for component in (candidate, *candidate.parents))


def _path_is_absent(path: Path, *, label: str) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return True
    except OSError:
        _fail(f"{label}_path_unreadable")
    return False


def _open_gate_input(path: Path) -> BinaryIO:
    return path.open("rb")


def _path_handle_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(stat.S_IFMT(value.st_mode)),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def _file_version(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (*_path_handle_identity(value), int(value.st_ctime_ns))


def _read_stable_bytes(path: Path, *, label: str, max_bytes: int) -> tuple[bytes, FileFingerprint]:
    try:
        before = path.stat()
    except OSError as exc:
        raise GateProvenanceError(f"{label}_path_unreadable") from exc
    if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
        _fail(f"{label}_empty_or_nonregular")
    if before.st_size > max_bytes:
        _fail(f"{label}_too_large")

    digest = hashlib.sha256()
    content = bytearray()
    try:
        with _open_gate_input(path) as handle:
            opened_before = os.fstat(handle.fileno())
            if _path_handle_identity(before) != _path_handle_identity(opened_before):
                _fail(f"{label}_changed_during_read")
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                if len(content) + len(chunk) > max_bytes:
                    _fail(f"{label}_too_large")
                content.extend(chunk)
            opened_after = os.fstat(handle.fileno())
        after = path.stat()
    except OSError as exc:
        raise GateProvenanceError(f"{label}_changed_during_read") from exc
    if (
        _path_has_link_like_component(path)
        or _file_version(before) != _file_version(after)
        or _file_version(opened_before) != _file_version(opened_after)
        or _path_handle_identity(after) != _path_handle_identity(opened_after)
        or len(content) != int(before.st_size)
    ):
        _fail(f"{label}_changed_during_read")
    data = bytes(content)
    return data, FileFingerprint(
        size=len(data),
        mtime_ns=int(after.st_mtime_ns),
        sha256=digest.hexdigest(),
    )


def _read_json_object(
    path: Path,
    *,
    label: str,
    max_bytes: int,
    allow_missing: bool,
) -> tuple[dict[str, Any] | None, FileFingerprint | None]:
    candidate = Path(path)
    if _path_has_link_like_component(candidate):
        _fail(f"{label}_link_like_path")
    if _path_is_absent(candidate, label=label):
        if allow_missing:
            return None, None
        _fail(f"{label}_missing")
    data, fingerprint = _read_stable_bytes(candidate, label=label, max_bytes=max_bytes)
    return _json_object_from_bytes(data, label=label), fingerprint


def _read_json_array(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> tuple[list[Any], FileFingerprint]:
    candidate = Path(path)
    if _path_has_link_like_component(candidate):
        _fail(f"{label}_link_like_path")
    if _path_is_absent(candidate, label=label):
        _fail(f"{label}_missing")
    data, fingerprint = _read_stable_bytes(
        candidate,
        label=label,
        max_bytes=max_bytes,
    )
    payload = _json_value_from_bytes(data, label=label)
    if not isinstance(payload, list):
        _fail(f"{label}_json_not_array")
    return payload, fingerprint


def _fingerprint_record(path: Path, fingerprint: FileFingerprint) -> dict[str, Any]:
    return {
        "path": str(_canonical(path)),
        "bytes": fingerprint.size,
        "sha256": fingerprint.sha256,
    }


def _sha256(value: Any, *, reason: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        _fail(reason)
    return value


def _positive_int(value: Any, *, reason: str) -> int:
    if type(value) is not int or value <= 0:
        _fail(reason)
    return value


def _validate_config_snapshot_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if set(payload) != {"schema_version", "source", "config"}:
        _fail("gate_config_snapshot_fields_invalid")
    if payload.get("schema_version") != GATE_CONFIG_SNAPSHOT_SCHEMA_VERSION:
        _fail("gate_config_snapshot_schema_invalid")
    source = payload.get("source")
    if not isinstance(source, dict) or set(source) != {"path", "bytes", "sha256"}:
        _fail("gate_config_snapshot_source_invalid")
    source_path_value = source.get("path")
    if not isinstance(source_path_value, str) or not source_path_value:
        _fail("gate_config_snapshot_source_path_invalid")
    source_path = Path(source_path_value)
    if not source_path.is_absolute() or str(_canonical(source_path)) != source_path_value:
        _fail("gate_config_snapshot_source_path_noncanonical")
    _positive_int(source.get("bytes"), reason="gate_config_snapshot_source_bytes_invalid")
    _sha256(source.get("sha256"), reason="gate_config_snapshot_source_sha256_invalid")
    config = payload.get("config")
    if not isinstance(config, dict):
        _fail("gate_config_snapshot_config_invalid")
    return config, source


def _publish_bytes_exclusive(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if _path_has_link_like_component(target.parent):
        _fail("gate_config_snapshot_parent_link_like")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def prepare_gate_config_snapshot(run_dir: Path, source_path: Path) -> GateConfigSnapshot:
    run_candidate = Path(run_dir).expanduser()
    if _path_has_link_like_component(run_candidate):
        _fail("gate_run_dir_link_like_path")
    run = _canonical(run_candidate)
    run.mkdir(parents=True, exist_ok=True)
    target = run / GATE_CONFIG_SNAPSHOT_NAME
    source_candidate = Path(source_path).expanduser()
    if _path_has_link_like_component(source_candidate):
        _fail("gate_config_source_link_like_path")
    if not source_candidate.is_absolute():
        source_candidate = _canonical(source_candidate)
    if _same_path(source_candidate, target):
        payload, fingerprint = _read_json_object(
            target,
            label="gate_config_snapshot",
            max_bytes=_MAX_CONFIG_BYTES,
            allow_missing=False,
        )
        assert payload is not None and fingerprint is not None
        config, source_record = _validate_config_snapshot_payload(payload)
        return GateConfigSnapshot(target, config, source_record, fingerprint)

    source = _canonical(source_candidate)
    source_payload, source_fingerprint = _read_json_object(
        source,
        label="gate_config_source",
        max_bytes=_MAX_CONFIG_BYTES,
        allow_missing=False,
    )
    assert source_payload is not None and source_fingerprint is not None
    source_record = {
        "path": str(source),
        "bytes": source_fingerprint.size,
        "sha256": source_fingerprint.sha256,
    }
    expected = {
        "schema_version": GATE_CONFIG_SNAPSHOT_SCHEMA_VERSION,
        "source": source_record,
        "config": source_payload,
    }
    serialized = (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if _path_is_absent(target, label="gate_config_snapshot"):
        _publish_bytes_exclusive(target, serialized)
    payload, fingerprint = _read_json_object(
        target,
        label="gate_config_snapshot",
        max_bytes=_MAX_CONFIG_BYTES,
        allow_missing=False,
    )
    assert payload is not None and fingerprint is not None
    config, recorded_source = _validate_config_snapshot_payload(payload)
    if payload != expected:
        _fail("gate_config_snapshot_conflict")
    return GateConfigSnapshot(target, config, recorded_source, fingerprint)


def _input_path(run_dir: Path, filename: str) -> Path:
    return _canonical(run_dir) / filename


def _read_gate_inputs(
    run_dir: Path,
) -> tuple[dict[str, dict[str, Any] | None], list[dict[str, Any]]]:
    payloads: dict[str, dict[str, Any] | None] = {}
    records: list[dict[str, Any]] = []
    for name, filename, allow_missing in _INPUT_SPECS:
        path = _input_path(run_dir, filename)
        payload, fingerprint = _read_json_object(
            path,
            label=f"gate_input_{name}",
            max_bytes=_MAX_INPUT_BYTES,
            allow_missing=allow_missing,
        )
        payloads[name] = payload
        record: dict[str, Any] = {
            "name": name,
            "path": str(path),
            "present": fingerprint is not None,
        }
        if fingerprint is not None:
            record.update({"bytes": fingerprint.size, "sha256": fingerprint.sha256})
        records.append(record)
    return payloads, records



def _validate_review_artifact_record(
    record: Any,
    *,
    run_dir: Path,
    expected_kind: str,
    expected_article: str,
    expected_path: Path | None = None,
) -> Path:
    label = f"article_review_artifact:{expected_kind}:{expected_article or 'index'}"
    if not isinstance(record, dict) or set(record) != {
        "kind",
        "article",
        "path",
        "bytes",
        "sha256",
    }:
        _fail(f"{label}_record_invalid")
    if record.get("kind") != expected_kind or record.get("article") != expected_article:
        _fail(f"{label}_identity_invalid")
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        _fail(f"{label}_path_invalid")
    path = Path(raw_path)
    if not path.is_absolute() or str(_canonical(path)) != raw_path:
        _fail(f"{label}_path_noncanonical")
    if expected_path is not None and not _same_path(path, expected_path):
        _fail(f"{label}_path_mismatch")
    declared_bytes = _positive_int(record.get("bytes"), reason=f"{label}_bytes_invalid")
    declared_sha256 = _sha256(record.get("sha256"), reason=f"{label}_sha256_invalid")
    _data, current = _read_stable_bytes(
        path,
        label=label,
        max_bytes=_MAX_INPUT_BYTES,
    )
    if (declared_bytes, declared_sha256) != (current.size, current.sha256):
        _fail(f"{label}_fingerprint_mismatch")
    resolved = _canonical(path)
    review_dir = _canonical(run_dir) / "article_review"
    if expected_kind in {"index_html", "review_html"}:
        try:
            resolved.relative_to(review_dir)
        except ValueError:
            _fail(f"{label}_outside_review_dir")
    return resolved


def _validate_article_review_provenance(
    run_dir: Path,
    report: dict[str, Any],
    gate_config: dict[str, Any],
) -> None:
    if set(report) != ARTICLE_REVIEW_REPORT_FIELDS:
        _fail("article_review_report_fields_invalid")
    if report.get("schema_version") != ARTICLE_REVIEW_REPORT_SCHEMA_VERSION:
        _fail("article_review_report_schema_invalid")
    _require_canonical_utc_timestamp(
        report.get("generated_at"),
        reason="article_review_generated_at_invalid",
    )
    expected_run = _canonical(run_dir)
    if report.get("run_dir") != str(expected_run):
        _fail("article_review_run_dir_mismatch")
    provenance = report.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != {
        "schema_version",
        "queue",
        "artifacts",
    }:
        _fail("article_review_provenance_invalid")
    if provenance.get("schema_version") != ARTICLE_REVIEW_PROVENANCE_SCHEMA_VERSION:
        _fail("article_review_provenance_schema_invalid")

    queue_path = _canonical(run_dir) / "manual_review_queue.json"
    queue_payload, queue_fingerprint = _read_json_array(
        queue_path,
        label="article_review_queue",
        max_bytes=_MAX_INPUT_BYTES,
    )
    expected_queue_record = {
        "kind": "manual_review_queue",
        "article": "",
        **_fingerprint_record(queue_path, queue_fingerprint),
    }
    if provenance.get("queue") != expected_queue_record:
        _fail("article_review_queue_fingerprint_mismatch")

    queue: list[dict[str, Any]] = []
    seen_queue_articles: set[str] = set()
    allowed_statuses = {
        "pending",
        "reviewed",
        "accepted_auto",
        "needs_fix",
        "false_positive",
    }
    for index, item in enumerate(queue_payload):
        if not isinstance(item, dict):
            _fail(f"article_review_queue_item_invalid:{index}")
        article = item.get("article")
        if not isinstance(article, str) or not article or article in seen_queue_articles:
            _fail(f"article_review_queue_article_invalid:{index}")
        seen_queue_articles.add(article)
        if type(item.get("mandatory_review")) is not bool:
            _fail(f"article_review_queue_mandatory_invalid:{article}")
        review_status = item.get("review_status") or "pending"
        if not isinstance(review_status, str) or review_status not in allowed_statuses:
            _fail(f"article_review_queue_status_invalid:{article}")
        queue.append(item)

    mandatory_items = [item for item in queue if item["mandatory_review"]]
    pending_mandatory = [
        item
        for item in mandatory_items
        if (item.get("review_status") or "pending") in UNRESOLVED_MANDATORY_REVIEW_STATUSES
    ]
    count_expectations = {
        "queue_count": len(queue),
        "mandatory_count": len(mandatory_items),
        "pending_mandatory_count": len(pending_mandatory),
        "reviewed_mandatory_count": len(mandatory_items) - len(pending_mandatory),
    }
    for field, expected in count_expectations.items():
        if type(report.get(field)) is not int or report.get(field) != expected:
            _fail(f"article_review_{field}_mismatch")

    bundle_limit = report.get("bundle_limit")
    configured_bundle_limit = gate_config.get("article_review_bundle_max_articles", 0)
    if type(configured_bundle_limit) is not int or configured_bundle_limit < 0:
        _fail("article_review_config_bundle_limit_invalid")
    expected_bundle_limit = (
        configured_bundle_limit
        if configured_bundle_limit > 0
        else len(mandatory_items)
    )
    if type(bundle_limit) is not int or bundle_limit < 0:
        _fail("article_review_bundle_limit_invalid")
    if bundle_limit != expected_bundle_limit:
        _fail("article_review_bundle_limit_mismatch")
    expected_selected = mandatory_items[:bundle_limit]
    report_articles = report.get("articles")
    if not isinstance(report_articles, list) or any(
        not isinstance(article, dict) for article in report_articles
    ):
        _fail("article_review_articles_invalid")
    if (
        type(report.get("selected_count")) is not int
        or report.get("selected_count") != len(expected_selected)
        or len(report_articles) != len(expected_selected)
    ):
        _fail("article_review_selected_count_mismatch")

    copy_error_count = report.get("copy_error_count")
    copy_errors = report.get("copy_errors")
    if (
        type(copy_error_count) is not int
        or copy_error_count < 0
        or not isinstance(copy_errors, list)
        or copy_error_count != len(copy_errors)
        or copy_error_count > len(expected_selected)
    ):
        _fail("article_review_copy_errors_invalid")
    selected_articles = {str(item["article"]) for item in expected_selected}
    copy_error_by_article: dict[str, dict[str, Any]] = {}
    for index, error in enumerate(copy_errors):
        if not isinstance(error, dict) or set(error) != {
            "article",
            "polish_stage_path",
            "error",
        }:
            _fail(f"article_review_copy_error_invalid:{index}")
        article = error.get("article")
        source_path = error.get("polish_stage_path")
        message = error.get("error")
        if (
            not isinstance(article, str)
            or article not in selected_articles
            or article in copy_error_by_article
            or not isinstance(source_path, str)
            or (
                source_path
                and (
                    not Path(source_path).is_absolute()
                    or str(_canonical(Path(source_path))) != source_path
                )
            )
            or not isinstance(message, str)
            or not message
        ):
            _fail(f"article_review_copy_error_invalid:{index}")
        copy_error_by_article[article] = error

    expected_status = "not_required" if not mandatory_items else "ready"
    if copy_error_count:
        expected_status = "error" if copy_error_count == len(expected_selected) else "partial"
    if report.get("status") != expected_status:
        _fail("article_review_status_mismatch")

    expected_review_dir = expected_run / "article_review"
    expected_index = expected_review_dir / "index.html"
    if report.get("review_dir") != str(expected_review_dir):
        _fail("article_review_dir_mismatch")
    if report.get("index_html") != str(expected_index):
        _fail("article_review_index_path_mismatch")

    artifact_payload = provenance.get("artifacts")
    if not isinstance(artifact_payload, list):
        _fail("article_review_artifacts_invalid")
    artifact_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    artifact_paths: set[Path] = set()
    for record in artifact_payload:
        if not isinstance(record, dict):
            _fail("article_review_artifact_record_invalid")
        identity = (
            str(record.get("kind") or ""),
            str(record.get("article") or ""),
        )
        if identity in artifact_by_identity:
            _fail("article_review_artifact_duplicate")
        artifact_by_identity[identity] = record

    index_record = artifact_by_identity.pop(("index_html", ""), None)
    artifact_paths.add(
        _validate_review_artifact_record(
            index_record,
            run_dir=run_dir,
            expected_kind="index_html",
            expected_article="",
            expected_path=expected_index,
        )
    )

    for queue_item, article_report in zip(
        expected_selected,
        report_articles,
        strict=True,
    ):
        article = str(queue_item["article"])
        if set(article_report) != ARTICLE_REVIEW_ARTICLE_FIELDS:
            _fail(f"article_review_article_fields_invalid:{article}")
        for field in (
            "article",
            "source_article",
            "artifact_hint",
            "raw_stage_path",
            "polish_stage_path",
        ):
            expected_value = article if field == "article" else queue_item.get(field)
            if article_report.get(field) != expected_value:
                _fail(f"article_review_article_field_mismatch:{article}:{field}")
        expected_reason = (
            queue_item.get("mandatory_review_reason")
            or queue_item.get("reason")
            or ""
        )
        if article_report.get("reason") != expected_reason:
            _fail(f"article_review_article_reason_mismatch:{article}")
        if article_report.get("review_note") != (queue_item.get("review_note") or ""):
            _fail(f"article_review_article_note_mismatch:{article}")
        expected_status = queue_item.get("review_status") or "pending"
        if article_report.get("review_status") != expected_status:
            _fail(f"article_review_article_status_mismatch:{article}")
        copy_error = copy_error_by_article.get(article)
        source_value = queue_item.get("polish_stage_path")
        resolved_source_path: Path | None = None
        if source_value not in {None, ""}:
            if not isinstance(source_value, str):
                _fail(f"article_review_source_path_invalid:{article}")
            resolved_source_path = Path(source_value)
            if not resolved_source_path.is_absolute():
                resolved_source_path = _canonical(run_dir / resolved_source_path)
        elif copy_error is None:
            _fail(f"article_review_source_path_invalid:{article}")
        source_record = artifact_by_identity.pop(("source_html", article), None)
        review_record = artifact_by_identity.pop(("review_html", article), None)
        if copy_error is not None:
            error_source_path = str(copy_error["polish_stage_path"])
            if resolved_source_path is None and error_source_path:
                _fail(f"article_review_copy_error_source_mismatch:{article}")
            if (
                resolved_source_path is not None
                and error_source_path != str(resolved_source_path)
            ):
                _fail(f"article_review_copy_error_source_mismatch:{article}")
            if source_record is not None or review_record is not None:
                _fail(f"article_review_failed_artifact_unexpected:{article}")
            if (
                article_report.get("review_html") not in {None, ""}
                or article_report.get("review_href") != ""
                or article_report.get("inlined_image_count") != 0
                or article_report.get("missing_image_count") != 0
                or article_report.get("missing_image_srcs") != []
            ):
                _fail(f"article_review_failed_article_mismatch:{article}")
            continue
        if resolved_source_path is None:  # Defensive fail-closed narrowing.
            _fail(f"article_review_source_path_invalid:{article}")
        artifact_paths.add(
            _validate_review_artifact_record(
                source_record,
                run_dir=run_dir,
                expected_kind="source_html",
                expected_article=article,
                expected_path=resolved_source_path,
            )
        )
        review_value = article_report.get("review_html")
        if not isinstance(review_value, str) or not review_value:
            _fail(f"article_review_html_path_invalid:{article}")
        artifact_paths.add(
            _validate_review_artifact_record(
                review_record,
                run_dir=run_dir,
                expected_kind="review_html",
                expected_article=article,
                expected_path=Path(review_value),
            )
        )
        expected_href = relative_review_href(expected_review_dir, Path(review_value))
        inlined_count = article_report.get("inlined_image_count")
        missing_count = article_report.get("missing_image_count")
        missing_srcs = article_report.get("missing_image_srcs")
        if (
            article_report.get("review_href") != expected_href
            or type(inlined_count) is not int
            or inlined_count < 0
            or type(missing_count) is not int
            or missing_count < 0
            or not isinstance(missing_srcs, list)
            or any(not isinstance(src, str) or not src for src in missing_srcs)
            or len(missing_srcs) > 20
        ):
            _fail(f"article_review_success_article_mismatch:{article}")

    if artifact_by_identity:
        _fail("article_review_artifact_set_extra")
    try:
        actual_review_files = {
            _canonical(path)
            for path in expected_review_dir.rglob("*")
            if path.is_file()
        }
    except OSError as exc:
        raise GateProvenanceError(
            "article_review_artifact_inventory_unreadable"
        ) from exc
    declared_review_files = {
        path
        for path in artifact_paths
        if path == expected_index or expected_review_dir in path.parents
    }
    if actual_review_files != declared_review_files:
        _fail("article_review_artifact_set_mismatch")




def _validate_previous_entry_snapshot(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if set(payload) != {"schema_version", "present", "source", "entry"}:
        _fail("quality_previous_entry_snapshot_fields_invalid")
    if payload.get("schema_version") != QUALITY_PREVIOUS_ENTRY_SNAPSHOT_SCHEMA_VERSION:
        _fail("quality_previous_entry_snapshot_schema_invalid")
    present = payload.get("present")
    if type(present) is not bool:
        _fail("quality_previous_entry_snapshot_presence_invalid")
    source = payload.get("source")
    if not isinstance(source, dict):
        _fail("quality_previous_entry_snapshot_source_invalid")
    kind = source.get("kind")
    if kind == "none":
        if set(source) != {"kind"} or present or payload.get("entry") is not None:
            _fail("quality_previous_entry_snapshot_none_invalid")
        return None
    if kind not in {"explicit_json", "history_jsonl"} or set(source) != {
        "kind",
        "path",
        "bytes",
        "sha256",
    }:
        _fail("quality_previous_entry_snapshot_source_invalid")
    source_path = source.get("path")
    if (
        not isinstance(source_path, str)
        or not source_path
        or not Path(source_path).is_absolute()
        or str(_canonical(Path(source_path))) != source_path
    ):
        _fail("quality_previous_entry_snapshot_source_path_invalid")
    _positive_int(
        source.get("bytes"),
        reason="quality_previous_entry_snapshot_source_bytes_invalid",
    )
    _sha256(
        source.get("sha256"),
        reason="quality_previous_entry_snapshot_source_sha256_invalid",
    )
    entry = payload.get("entry")
    if not present or not isinstance(entry, dict):
        _fail("quality_previous_entry_snapshot_entry_invalid")
    return entry


def _write_replay_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _replay_quality_history(
    run_dir: Path,
    *,
    run_id: str,
    assessment: dict[str, Any] | None,
    audit_report: dict[str, Any] | None,
    previous_entry: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "record_en_polish_quality_history.py"
    if not script_path.is_file() or _path_has_link_like_component(script_path):
        _fail("quality_history_replay_script_unavailable")
    try:
        with tempfile.TemporaryDirectory(prefix="z2m-quality-history-replay-") as temporary:
            root = Path(temporary)
            assessment_path = root / "assessment.json"
            audit_path = root / "audit_full_checks.json"
            previous_path = root / "previous_entry.json"
            history_path = root / "missing_history.jsonl"
            out_entry = root / "quality_history_entry.json"
            out_compare = root / "quality_compare.json"
            out_ranking = root / "brokenness_ranking.json"
            out_previous_snapshot = root / QUALITY_PREVIOUS_ENTRY_SNAPSHOT_NAME
            if assessment is not None:
                _write_replay_json(assessment_path, assessment)
            if audit_report is not None:
                _write_replay_json(audit_path, audit_report)
            if previous_entry is not None:
                _write_replay_json(previous_path, previous_entry)
            command = [
                sys.executable,
                str(script_path),
                "--run-dir",
                str(_canonical(run_dir)),
                "--run-id",
                run_id,
                "--assessment",
                str(assessment_path),
                "--audit-report",
                str(audit_path),
                "--history",
                str(history_path),
                "--out-entry",
                str(out_entry),
                "--out-compare",
                str(out_compare),
                "--out-ranking",
                str(out_ranking),
                "--out-previous-snapshot",
                str(out_previous_snapshot),
                "--no-append",
            ]
            if previous_entry is not None:
                command.extend(["--previous-entry", str(previous_path)])
            environment = os.environ.copy()
            environment.update(AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES)
            completed = subprocess.run(
                command,
                cwd=repo_root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr.strip() or completed.stdout.strip())[-2000:]
                raise GateProvenanceError(
                    "quality_history_replay_failed:"
                    f"returncode={completed.returncode}:{detail}"
                )
            replayed_entry, _entry_fingerprint = _read_json_object(
                out_entry,
                label="quality_history_replay_entry",
                max_bytes=_MAX_INPUT_BYTES,
                allow_missing=False,
            )
            replayed_compare, _compare_fingerprint = _read_json_object(
                out_compare,
                label="quality_history_replay_compare",
                max_bytes=_MAX_INPUT_BYTES,
                allow_missing=False,
            )
            assert replayed_entry is not None and replayed_compare is not None
            return replayed_entry, replayed_compare
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateProvenanceError("quality_history_replay_failed") from exc


def _validate_quality_history_provenance(
    run_dir: Path,
    payloads: dict[str, dict[str, Any] | None],
) -> None:
    comparison = payloads.get("quality_compare")
    current_entry = payloads.get("quality_history_entry")
    previous_snapshot = payloads.get("quality_previous_entry")
    if comparison is None:
        if current_entry is not None or previous_snapshot is not None:
            _fail("quality_history_partial_inputs")
        return
    if not isinstance(current_entry, dict):
        _fail("quality_history_entry_missing")
    if not isinstance(previous_snapshot, dict):
        _fail("quality_previous_entry_snapshot_missing")
    previous_entry = _validate_previous_entry_snapshot(previous_snapshot)
    assessment = payloads.get("assessment")
    audit_report = payloads.get("audit_report")
    if assessment is None and audit_report is None:
        _fail("quality_history_sources_missing")
    run_id = current_entry.get("run_id")
    entry_generated_at = current_entry.get("generated_at")
    comparison_generated_at = comparison.get("generated_at")
    if not isinstance(run_id, str) or not run_id:
        _fail("quality_history_run_id_invalid")
    entry_generated_at = _require_canonical_utc_timestamp(
        entry_generated_at,
        reason="quality_history_generated_at_invalid",
    )
    comparison_generated_at = _require_canonical_utc_timestamp(
        comparison_generated_at,
        reason="quality_compare_generated_at_invalid",
    )

    replayed_entry, replayed_compare = _replay_quality_history(
        run_dir,
        run_id=run_id,
        assessment=assessment,
        audit_report=audit_report,
        previous_entry=previous_entry,
    )
    replayed_entry["generated_at"] = entry_generated_at
    replayed_compare["generated_at"] = comparison_generated_at
    if replayed_entry != current_entry:
        _fail("quality_history_entry_recompute_mismatch")
    if replayed_compare != comparison:
        _fail("quality_compare_recompute_mismatch")

def _validate_pdf_evidence_artifact_record(
    record: Any,
    *,
    run_dir: Path,
    expected_kind: str,
    expected_article: str,
    expected_path: Path,
) -> Path:
    label = f"pdf_evidence_artifact:{expected_kind}:{expected_article}"
    if not isinstance(record, dict) or set(record) != {
        "kind",
        "article",
        "path",
        "bytes",
        "sha256",
    }:
        _fail(f"{label}_record_invalid")
    if record.get("kind") != expected_kind or record.get("article") != expected_article:
        _fail(f"{label}_identity_invalid")
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        _fail(f"{label}_path_invalid")
    path = Path(raw_path)
    if (
        not path.is_absolute()
        or str(_canonical(path)) != raw_path
        or not _same_path(path, expected_path)
    ):
        _fail(f"{label}_path_mismatch")
    declared_bytes = _positive_int(record.get("bytes"), reason=f"{label}_bytes_invalid")
    declared_sha256 = _sha256(record.get("sha256"), reason=f"{label}_sha256_invalid")
    _data, current = _read_stable_bytes(
        path,
        label=label,
        max_bytes=_MAX_INPUT_BYTES,
    )
    if (declared_bytes, declared_sha256) != (current.size, current.sha256):
        _fail(f"{label}_fingerprint_mismatch")
    resolved = _canonical(path)
    allowed_root = (
        _canonical(run_dir) / "_enrichment_snapshot" / "files"
        if expected_kind == "source_pdf"
        else _canonical(run_dir) / "pdf_problem_evidence"
    )
    try:
        resolved.relative_to(allowed_root)
    except ValueError:
        _fail(f"{label}_outside_run_owned_root")
    return resolved


def _validate_pdf_problem_evidence_provenance(
    run_dir: Path,
    report: dict[str, Any],
    gate_config: dict[str, Any],
) -> None:
    if set(report) != PDF_PROBLEM_EVIDENCE_REPORT_FIELDS:
        _fail("pdf_evidence_report_fields_invalid")
    if report.get("schema_version") != PDF_PROBLEM_EVIDENCE_REPORT_SCHEMA_VERSION:
        _fail("pdf_evidence_report_schema_invalid")
    _require_canonical_utc_timestamp(
        report.get("generated_at"),
        reason="pdf_evidence_generated_at_invalid",
    )
    provenance = report.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != {
        "schema_version",
        "inputs",
        "artifacts",
    }:
        _fail("pdf_evidence_provenance_invalid")
    if provenance.get("schema_version") != PDF_PROBLEM_EVIDENCE_PROVENANCE_SCHEMA_VERSION:
        _fail("pdf_evidence_provenance_schema_invalid")

    inputs_path = _canonical(run_dir) / PDF_PROBLEM_EVIDENCE_INPUTS_NAME
    inputs, inputs_fingerprint = _read_json_object(
        inputs_path,
        label="pdf_evidence_inputs",
        max_bytes=_MAX_INPUT_BYTES,
        allow_missing=False,
    )
    assert inputs is not None and inputs_fingerprint is not None
    expected_input_record = {
        "kind": "evidence_inputs",
        "article": "",
        **_fingerprint_record(inputs_path, inputs_fingerprint),
    }
    if provenance.get("inputs") != expected_input_record:
        _fail("pdf_evidence_inputs_fingerprint_mismatch")
    if set(inputs) != {
        "schema_version",
        "max_articles",
        "render_zoom",
        "max_pdf_pages",
        "allow_missing_source_pdf",
        "articles",
    }:
        _fail("pdf_evidence_inputs_fields_invalid")
    if inputs.get("schema_version") != PDF_PROBLEM_EVIDENCE_INPUTS_SCHEMA_VERSION:
        _fail("pdf_evidence_inputs_schema_invalid")
    config_expectations = {
        "max_articles": int(gate_config.get("pdf_problem_evidence_max_articles") or 0),
        "render_zoom": float(gate_config.get("pdf_problem_evidence_render_zoom") or 1.5),
        "max_pdf_pages": int(gate_config.get("pdf_problem_evidence_max_pdf_pages") or 80),
        "allow_missing_source_pdf": bool(
            gate_config.get("pdf_problem_evidence_allow_missing_source_pdf", True)
        ),
    }
    for field, expected in config_expectations.items():
        actual = inputs.get(field)
        if field == "render_zoom":
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                _fail("pdf_evidence_render_zoom_invalid")
            actual = float(actual)
        if actual != expected:
            _fail(f"pdf_evidence_config_mismatch:{field}")

    selection_articles = inputs.get("articles")
    if not isinstance(selection_articles, list):
        _fail("pdf_evidence_selection_invalid")
    report_articles = report.get("articles")
    if not isinstance(report_articles, list) or len(report_articles) != len(
        selection_articles
    ):
        _fail("pdf_evidence_article_set_mismatch")
    if (
        type(report.get("selected_count")) is not int
        or report.get("selected_count") != len(selection_articles)
    ):
        _fail("pdf_evidence_selected_count_mismatch")
    expected_run = _canonical(run_dir)
    expected_report = expected_run / PDF_PROBLEM_EVIDENCE_REPORT_NAME
    expected_evidence_dir = expected_run / "pdf_problem_evidence"
    if report.get("run_dir") != str(expected_run):
        _fail("pdf_evidence_run_dir_mismatch")
    if report.get("report_path") != str(expected_report):
        _fail("pdf_evidence_report_path_mismatch")
    if report.get("evidence_dir") != str(expected_evidence_dir):
        _fail("pdf_evidence_dir_mismatch")
    required_checks = ["source_pdf_page_render", "source_pdf_text_layer"]
    if report.get("required_checks") != required_checks:
        _fail("pdf_evidence_required_checks_mismatch")
    allow_missing = config_expectations["allow_missing_source_pdf"]
    if report.get("allow_missing_source_pdf") is not allow_missing:
        _fail("pdf_evidence_allow_missing_mismatch")

    artifact_payload = provenance.get("artifacts")
    if not isinstance(artifact_payload, list):
        _fail("pdf_evidence_artifacts_invalid")
    artifact_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    evidence_paths: set[Path] = set()
    for artifact in artifact_payload:
        if not isinstance(artifact, dict):
            _fail("pdf_evidence_artifact_record_invalid")
        identity = (
            str(artifact.get("kind") or ""),
            str(artifact.get("article") or ""),
        )
        if identity in artifact_by_identity:
            _fail("pdf_evidence_artifact_duplicate")
        artifact_by_identity[identity] = artifact

    seen_articles: set[str] = set()
    ready_count = 0
    unavailable_count = 0
    blocking_issue_count = 0
    for selection, article_report in zip(
        selection_articles,
        report_articles,
        strict=True,
    ):
        if not isinstance(selection, dict) or not isinstance(article_report, dict):
            _fail("pdf_evidence_article_invalid")
        if set(selection) != {
            "article",
            "source_article",
            "source_pdf_candidates",
            "selected_source_pdf",
            "problem_snippets",
        }:
            _fail("pdf_evidence_selection_article_fields_invalid")
        article = selection.get("article")
        if not isinstance(article, str) or not article or article in seen_articles:
            _fail("pdf_evidence_article_identity_invalid")
        seen_articles.add(article)
        candidates = selection.get("source_pdf_candidates")
        if not isinstance(candidates, list):
            _fail(f"pdf_evidence_candidates_invalid:{article}")
        for candidate_index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                _fail(f"pdf_evidence_candidates_invalid:{article}")
            fields = set(candidate)
            if (
                not PDF_PROBLEM_EVIDENCE_CANDIDATE_REQUIRED_FIELDS <= fields
                or not fields <= PDF_PROBLEM_EVIDENCE_CANDIDATE_ALLOWED_FIELDS
            ):
                _fail(
                    f"pdf_evidence_candidate_fields_invalid:{article}:{candidate_index}"
                )
            if (
                not isinstance(candidate.get("path"), str)
                or not candidate.get("path")
                or not Path(candidate["path"]).is_absolute()
                or str(_canonical(Path(candidate["path"]))) != candidate["path"]
                or type(candidate.get("exists")) is not bool
                or not isinstance(candidate.get("source"), str)
                or not candidate.get("source")
                or (
                    "original_path" in candidate
                    and not isinstance(candidate["original_path"], str)
                )
            ):
                _fail(f"pdf_evidence_candidate_invalid:{article}:{candidate_index}")
        snippets = selection.get("problem_snippets")
        selected_pdf = selection.get("selected_source_pdf")
        if not isinstance(snippets, list) or any(
            not isinstance(snippet, str) for snippet in snippets
        ):
            _fail(f"pdf_evidence_snippets_invalid:{article}")
        expected_selected_pdf = next(
            (candidate for candidate in candidates if candidate["exists"]),
            None,
        )
        if selected_pdf != expected_selected_pdf:
            _fail(f"pdf_evidence_selected_source_mismatch:{article}")
        expected_article_fields = (
            PDF_PROBLEM_EVIDENCE_UNAVAILABLE_ARTICLE_FIELDS
            if selected_pdf is None
            else PDF_PROBLEM_EVIDENCE_ARTICLE_FIELDS
        )
        if set(article_report) != expected_article_fields:
            _fail(f"pdf_evidence_article_fields_invalid:{article}")
        if article_report.get("article") != article:
            _fail(f"pdf_evidence_article_order_mismatch:{article}")
        if article_report.get("source_article") != selection.get("source_article"):
            _fail(f"pdf_evidence_source_article_mismatch:{article}")
        if article_report.get("source_pdf_candidate_count") != len(candidates):
            _fail(f"pdf_evidence_candidate_count_mismatch:{article}")
        if (
            article_report.get("problem_snippet_count") != len(snippets)
            or article_report.get("problem_snippets") != snippets[:8]
        ):
            _fail(f"pdf_evidence_snippet_mismatch:{article}")
        if article_report.get("required_checks") != required_checks:
            _fail(f"pdf_evidence_article_checks_mismatch:{article}")

        if selected_pdf is None:
            unavailable_count += 1
            if not allow_missing:
                blocking_issue_count += 1
            unavailable_expectations = {
                "status": "source_pdf_unavailable",
                "source_pdf_available": False,
                "source_pdf_path": "",
                "source_pdf_origin_path": "",
                "source_pdf_source": "",
                "evidence_page": 0,
                "text_layer_status": "not_run",
                "text_layer_chars": 0,
                "text_layer_page_count": 0,
                "text_layer_page_limit": config_expectations["max_pdf_pages"],
                "text_layer_truncated_to_limit": False,
                "text_layer_error": "",
                "text_layer_excerpt_path": "",
                "page_render_status": "not_run",
                "page_render_path": "",
                "page_render_error": "",
                "match_score": 0.0,
                "unavailable_reason": "No existing source PDF candidate was found.",
            }
            if any(
                article_report.get(field) != expected
                for field, expected in unavailable_expectations.items()
            ) or type(article_report.get("match_score")) is not float:
                _fail(f"pdf_evidence_unavailable_state_mismatch:{article}")
            continue
        if not isinstance(selected_pdf, dict):
            _fail(f"pdf_evidence_selected_source_invalid:{article}")
        selected_path = selected_pdf.get("path")
        if not isinstance(selected_path, str) or not selected_path:
            _fail(f"pdf_evidence_selected_source_path_invalid:{article}")
        if (
            article_report.get("source_pdf_available") is not True
            or article_report.get("source_pdf_origin_path") != selected_path
            or article_report.get("source_pdf_source") != selected_pdf.get("source")
        ):
            _fail(f"pdf_evidence_source_state_mismatch:{article}")

        evidence_page = article_report.get("evidence_page")
        text_status = article_report.get("text_layer_status")
        text_chars = article_report.get("text_layer_chars")
        text_page_count = article_report.get("text_layer_page_count")
        text_page_limit = article_report.get("text_layer_page_limit")
        text_truncated = article_report.get("text_layer_truncated_to_limit")
        text_error = article_report.get("text_layer_error")
        excerpt_value = article_report.get("text_layer_excerpt_path")
        render_status = article_report.get("page_render_status")
        render_value = article_report.get("page_render_path")
        render_error = article_report.get("page_render_error")
        match_score = article_report.get("match_score")
        max_pdf_pages = int(config_expectations["max_pdf_pages"])
        text_page_count_value = (
            int(text_page_count) if type(text_page_count) is int else -1
        )
        evidence_page_value = int(evidence_page) if type(evidence_page) is int else -1
        page_state_valid = (
            type(text_page_count) is int
            and 0 <= text_page_count_value <= max_pdf_pages
            and type(evidence_page) is int
            and (
                (text_page_count_value == 0 and evidence_page_value == 0)
                or (
                    text_page_count_value > 0
                    and 1 <= evidence_page_value <= text_page_count_value
                )
            )
        )
        if (
            not isinstance(text_status, str)
            or not text_status
            or type(text_chars) is not int
            or text_chars < 0
            or not page_state_valid
            or text_page_limit != max_pdf_pages
            or type(text_truncated) is not bool
            or text_truncated is not (text_page_count_value >= max_pdf_pages)
            or not isinstance(text_error, str)
            or not isinstance(excerpt_value, str)
            or bool(excerpt_value) is not (text_chars > 0)
            or not isinstance(render_status, str)
            or not render_status
            or not isinstance(render_value, str)
            or not isinstance(render_error, str)
            or isinstance(match_score, bool)
            or not isinstance(match_score, (int, float))
            or not math.isfinite(float(match_score))
            or not 0.0 <= float(match_score) <= 1.0
        ):
            _fail(f"pdf_evidence_text_state_invalid:{article}")

        source_value = article_report.get("source_pdf_path")
        if not isinstance(source_value, str) or not source_value:
            _fail(f"pdf_evidence_snapshot_path_invalid:{article}")
        source_record = artifact_by_identity.pop(("source_pdf", article), None)
        _validate_pdf_evidence_artifact_record(
            source_record,
            run_dir=run_dir,
            expected_kind="source_pdf",
            expected_article=article,
            expected_path=Path(source_value),
        )

        if excerpt_value:
            if not isinstance(excerpt_value, str):
                _fail(f"pdf_evidence_excerpt_path_invalid:{article}")
            excerpt_record = artifact_by_identity.pop(("text_excerpt", article), None)
            evidence_paths.add(
                _validate_pdf_evidence_artifact_record(
                    excerpt_record,
                    run_dir=run_dir,
                    expected_kind="text_excerpt",
                    expected_article=article,
                    expected_path=Path(excerpt_value),
                )
            )
        if render_status == "rendered":
            if not isinstance(render_value, str) or not render_value:
                _fail(f"pdf_evidence_render_path_invalid:{article}")
            render_record = artifact_by_identity.pop(("page_render", article), None)
            evidence_paths.add(
                _validate_pdf_evidence_artifact_record(
                    render_record,
                    run_dir=run_dir,
                    expected_kind="page_render",
                    expected_article=article,
                    expected_path=Path(render_value),
                )
            )
        article_ready = (
            type(text_chars) is int
            and text_chars > 0
            and bool(excerpt_value)
            and render_status == "rendered"
        )
        expected_article_status = "ready" if article_ready else "incomplete"
        if article_report.get("status") != expected_article_status:
            _fail(f"pdf_evidence_article_status_mismatch:{article}")
        if article_ready:
            ready_count += 1
        else:
            blocking_issue_count += 1

    if artifact_by_identity:
        _fail("pdf_evidence_artifact_set_extra")
    actual_evidence_paths: set[Path] = set()
    if expected_evidence_dir.exists():
        try:
            for path in expected_evidence_dir.rglob("*"):
                if path_is_link_like(path):
                    _fail("pdf_evidence_artifact_link_like")
                if path.is_file():
                    actual_evidence_paths.add(_canonical(path))
        except OSError as exc:
            raise GateProvenanceError(
                "pdf_evidence_artifact_inventory_unreadable"
            ) from exc
    if actual_evidence_paths != evidence_paths:
        _fail("pdf_evidence_artifact_set_mismatch")

    count_expectations = {
        "ready_count": ready_count,
        "source_pdf_unavailable_count": unavailable_count,
        "blocking_issue_count": blocking_issue_count,
    }
    for field, expected in count_expectations.items():
        if type(report.get(field)) is not int or report.get(field) != expected:
            _fail(f"pdf_evidence_{field}_mismatch")
    expected_status = (
        "not_required"
        if not selection_articles
        else "incomplete"
        if blocking_issue_count
        else "ready"
    )
    if report.get("status") != expected_status:
        _fail("pdf_evidence_status_mismatch")

def _evaluate_from_inputs(
    run_dir: Path,
    payloads: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    config_snapshot = payloads.get("gate_config")
    if not isinstance(config_snapshot, dict):
        _fail("gate_config_snapshot_missing")
    gate_config, _source = _validate_config_snapshot_payload(config_snapshot)
    audit_report = payloads.get("audit_report")
    audit_command_report = payloads.get("audit_command")
    if (audit_report is None) is not (audit_command_report is None):
        _fail("audit_command_report_pair_incomplete")
    if audit_report is not None and audit_command_report is not None:
        try:
            validate_audit_command_report(
                run_dir,
                audit_report,
                audit_command_report,
            )
        except AuditCommandProvenanceError as exc:
            _fail(str(exc))
    _validate_quality_history_provenance(run_dir, payloads)
    comparison = payloads.get("quality_compare") or {"status": "no_previous_entry"}
    article_review_report = payloads.get("article_review")
    if article_review_report is not None:
        _validate_article_review_provenance(
            run_dir, article_review_report, gate_config
        )
    pdf_problem_evidence_report = payloads.get("pdf_problem_evidence")
    if pdf_problem_evidence_report is not None:
        _validate_pdf_problem_evidence_provenance(
            run_dir,
            pdf_problem_evidence_report,
            gate_config,
        )
    return evaluate_quality_gate(
        comparison,
        gate_config,
        article_review_report=article_review_report,
        audit_report=audit_report,
        audit_command_report=audit_command_report,
        pdf_problem_evidence_report=pdf_problem_evidence_report,
    )


def build_provenanced_gate_report(run_dir: Path) -> dict[str, Any]:
    payloads, records = _read_gate_inputs(run_dir)
    report = {
        "schema_version": GATE_REPORT_SCHEMA_VERSION,
        **_evaluate_from_inputs(run_dir, payloads),
        "input_contract": {
            "schema_version": GATE_INPUT_CONTRACT_SCHEMA_VERSION,
            "inputs": records,
        },
    }
    validate_gate_report_provenance(run_dir, report)
    return report


def _validate_declared_input_record(
    record: Any,
    *,
    name: str,
    expected_path: Path,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        _fail(f"gate_input_record_invalid:{name}")
    present = record.get("present")
    expected_fields = {"name", "path", "present", "bytes", "sha256"} if present is True else {
        "name",
        "path",
        "present",
    }
    if set(record) != expected_fields:
        _fail(f"gate_input_record_fields_invalid:{name}")
    if record.get("name") != name or record.get("path") != str(expected_path):
        _fail(f"gate_input_record_identity_invalid:{name}")
    if type(present) is not bool:
        _fail(f"gate_input_record_presence_invalid:{name}")
    if present:
        _positive_int(record.get("bytes"), reason=f"gate_input_record_bytes_invalid:{name}")
        _sha256(record.get("sha256"), reason=f"gate_input_record_sha256_invalid:{name}")
    return record


def validate_gate_report_provenance(
    run_dir: Path,
    report: dict[str, Any],
) -> GateReportProvenanceValidation:
    if report.get("schema_version") != GATE_REPORT_SCHEMA_VERSION:
        _fail("gate_report_schema_invalid")
    generated_at = _require_canonical_utc_timestamp(
        report.get("generated_at"),
        reason="gate_report_generated_at_invalid",
    )
    contract = report.get("input_contract")
    if not isinstance(contract, dict) or set(contract) != {"schema_version", "inputs"}:
        _fail("gate_input_contract_invalid")
    if contract.get("schema_version") != GATE_INPUT_CONTRACT_SCHEMA_VERSION:
        _fail("gate_input_contract_schema_invalid")
    declared_inputs = contract.get("inputs")
    if not isinstance(declared_inputs, list) or len(declared_inputs) != len(_INPUT_SPECS):
        _fail("gate_input_contract_set_invalid")

    declared_records: list[dict[str, Any]] = []
    for declared, (name, filename, _allow_missing) in zip(declared_inputs, _INPUT_SPECS, strict=True):
        declared_records.append(
            _validate_declared_input_record(
                declared,
                name=name,
                expected_path=_input_path(run_dir, filename),
            )
        )

    payloads, current_records = _read_gate_inputs(run_dir)
    for declared, current in zip(declared_records, current_records, strict=True):
        if declared != current:
            _fail(f"gate_input_fingerprint_mismatch:{declared['name']}")

    recomputed = _evaluate_from_inputs(run_dir, payloads)
    recomputed["generated_at"] = generated_at
    expected_report = {
        "schema_version": GATE_REPORT_SCHEMA_VERSION,
        **recomputed,
        "input_contract": contract,
    }
    if report != expected_report:
        _fail("gate_result_recompute_mismatch")
    return GateReportProvenanceValidation(tuple(current_records))
