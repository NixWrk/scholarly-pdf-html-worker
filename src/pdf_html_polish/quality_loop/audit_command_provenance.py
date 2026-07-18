"""Exact provenance for the quality audit subprocess and its final report."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import threading
from typing import Any, Iterable, NoReturn

from pdf_html_polish.quality_loop.cached_run_state import path_is_link_like
from pdf_html_polish.quality_loop.audit_postprocessors import (
    AuditPostprocessorError,
    normalize_converted_audit_article_ids_payload,
)
from pdf_html_polish.quality_loop.audit_pdf import load_pdf_map
from pdf_html_polish.quality_loop.enrichment_snapshot import (
    ENRICHMENT_FILES_DIR_NAME,
    ENRICHMENT_SNAPSHOT_DIR_NAME,
)
from pdf_html_polish.quality_loop.run_utils import (
    DEFAULT_REPO_ROOT,
    parse_canonical_utc_timestamp,
    write_json,
)


AUDIT_COMMAND_REPORT_SCHEMA_VERSION = 3
AUDIT_CODE_MANIFEST_SCHEMA_VERSION = 1
AUDIT_COMMAND_REPORT_KIND = "quality_audit_command"
AUDIT_OUTPUT_NAME = "audit_full_checks.json"
AUDIT_STDOUT_NAME = "audit_stdout.log"
AUDIT_STDERR_NAME = "audit_stderr.log"
AUDIT_COMMAND_REPORT_NAME = "audit_command_report.json"
AUDIT_SCRIPT_RELATIVE_PATH = Path("scripts") / "audit_en_polish.py"
AUDIT_PACKAGE_RELATIVE_PATH = Path("src") / "pdf_html_polish"
NORMALIZE_CONVERTED_IDS_POSTPROCESSOR = "normalize_converted_audit_article_ids"
_MAX_AUDIT_JSON_BYTES = 256 * 1024 * 1024
AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES = {
    "PYTHONHASHSEED": "0",
    "PYTHONIOENCODING": "utf-8",
}

_SHA256_HEX = frozenset("0123456789abcdef")
_REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "command",
        "repo_root",
        "python_executable",
        "python_version",
        "environment_overrides",
        "code_manifest",
        "roots",
        "output_path",
        "command_output",
        "audit_output",
        "pdf_diagnostics_enabled",
        "pdf_map_input",
        "pdf_map_path",
        "pdf_diagnostics_cache_dir",
        "jobs",
        "merge_previous_report_input",
        "merge_previous_report_path",
        "targeted_merge_enabled",
        "postprocessors",
        "started_at",
        "finished_at",
        "returncode",
        "stdout",
        "stderr",
        "stdout_path",
        "stderr_path",
        "stdout_tail",
        "stderr_tail",
    }
)
_CODE_RECORD_CACHE: dict[tuple[str, tuple[int, int, int, int, int, int]], dict[str, Any]] = {}
_CODE_RECORD_CACHE_LOCK = threading.Lock()


class AuditCommandProvenanceError(ValueError):
    pass


def _fail(reason: str) -> NoReturn:
    raise AuditCommandProvenanceError(reason)


def _validated_environment_overrides(value: Any) -> dict[str, str]:
    if (
        type(value) is not dict
        or value != AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES
    ):
        _fail("audit_command_environment_overrides_invalid")
    return dict(value)


def _validated_command_interval(
    started_at: Any,
    finished_at: Any,
) -> tuple[Any, Any]:
    try:
        started = parse_canonical_utc_timestamp(started_at)
    except ValueError:
        _fail("audit_command_started_at_invalid")
    try:
        finished = parse_canonical_utc_timestamp(finished_at)
    except ValueError:
        _fail("audit_command_finished_at_invalid")
    if finished < started:
        _fail("audit_command_timestamp_order_invalid")
    return started, finished


def _validate_audit_generated_at(
    audit_report: dict[str, Any],
    *,
    started: Any,
    finished: Any,
) -> None:
    try:
        generated = parse_canonical_utc_timestamp(audit_report.get("generated_at"))
    except ValueError:
        _fail("audit_report_generated_at_invalid")
    if generated < started or generated > finished:
        _fail("audit_report_generated_at_outside_command")


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _SHA256_HEX for character in value)
    )


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(str(Path(path).expanduser())))


def _canonical(path: Path) -> Path:
    return _lexical_absolute(path).resolve(strict=False)


def _path_key(path: Path) -> str:
    return os.path.normcase(str(_canonical(path)))


def _same_path(left: Path, right: Path) -> bool:
    return _path_key(left) == _path_key(right)


def _is_within(path: Path, root: Path) -> bool:
    try:
        _canonical(path).relative_to(_canonical(root))
        return True
    except ValueError:
        return False


def _has_link_like_component(path: Path) -> bool:
    candidate = _lexical_absolute(path)
    return any(path_is_link_like(component) for component in (candidate, *candidate.parents))


def canonical_existing_root(path: Path) -> Path:
    candidate = _lexical_absolute(path)
    if _has_link_like_component(candidate):
        _fail(f"audit_root_link_like:{candidate}")
    resolved = candidate.resolve(strict=False)
    if not resolved.exists():
        _fail(f"audit_root_missing:{resolved}")
    if not (resolved.is_dir() or resolved.is_file()):
        _fail(f"audit_root_invalid:{resolved}")
    return resolved


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(stat.S_IFMT(value.st_mode)),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def _file_version(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (*_stat_identity(value), int(value.st_ctime_ns))


def file_record(path: Path, *, allow_empty: bool = False, label: str = "audit_artifact") -> dict[str, Any]:
    lexical = _lexical_absolute(path)
    if _has_link_like_component(lexical):
        _fail(f"{label}_link_like")
    candidate = lexical.resolve(strict=False)
    try:
        before = candidate.stat()
        if not stat.S_ISREG(before.st_mode) or (before.st_size <= 0 and not allow_empty):
            _fail(f"{label}_empty_or_nonregular")
        digest = hashlib.sha256()
        with candidate.open("rb") as handle:
            opened_before = os.fstat(handle.fileno())
            if _stat_identity(before) != _stat_identity(opened_before):
                _fail(f"{label}_changed_during_read")
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            opened_after = os.fstat(handle.fileno())
        after = candidate.stat()
    except AuditCommandProvenanceError:
        raise
    except OSError as exc:
        raise AuditCommandProvenanceError(f"{label}_unreadable") from exc
    if (
        _file_version(before) != _file_version(after)
        or _file_version(opened_before) != _file_version(opened_after)
        or _stat_identity(after) != _stat_identity(opened_after)
    ):
        _fail(f"{label}_changed_during_read")
    return {
        "path": str(candidate),
        "bytes": int(after.st_size),
        "sha256": digest.hexdigest(),
    }


def _record_shape(
    value: Any,
    *,
    label: str,
    expected_path: Path | None = None,
    allow_empty: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"path", "bytes", "sha256"}:
        _fail(f"{label}_record_invalid")
    raw_path = value.get("path")
    size = value.get("bytes")
    sha256 = value.get("sha256")
    if not isinstance(raw_path, str) or not Path(raw_path).is_absolute():
        _fail(f"{label}_path_invalid")
    if _has_link_like_component(Path(raw_path)):
        _fail(f"{label}_path_link_like")
    if raw_path != str(_canonical(Path(raw_path))):
        _fail(f"{label}_path_not_canonical")
    if expected_path is not None and not _same_path(Path(raw_path), expected_path):
        _fail(f"{label}_path_mismatch")
    if type(size) is not int or size < (0 if allow_empty else 1):
        _fail(f"{label}_bytes_invalid")
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or any(character not in _SHA256_HEX for character in sha256)
    ):
        _fail(f"{label}_sha256_invalid")
    return value


def _record_matches_current(
    value: Any,
    *,
    label: str,
    expected_path: Path,
    allow_empty: bool = False,
) -> dict[str, Any]:
    record = _record_shape(
        value,
        label=label,
        expected_path=expected_path,
        allow_empty=allow_empty,
    )
    current = file_record(expected_path, allow_empty=allow_empty, label=label)
    if record != current:
        _fail(f"{label}_fingerprint_mismatch")
    return record


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_json_key:{key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"nonfinite_json_constant:{value}")


def load_audit_json_object(
    path: Path,
    *,
    label: str,
    expected_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lexical = _lexical_absolute(path)
    if _has_link_like_component(lexical):
        _fail(f"{label}_link_like")
    candidate = lexical.resolve(strict=False)
    try:
        before = candidate.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            _fail(f"{label}_empty_or_nonregular")
        if before.st_size > _MAX_AUDIT_JSON_BYTES:
            _fail(f"{label}_too_large")
        with candidate.open("rb") as handle:
            opened_before = os.fstat(handle.fileno())
            if _stat_identity(before) != _stat_identity(opened_before):
                _fail(f"{label}_changed_during_read")
            data = handle.read(_MAX_AUDIT_JSON_BYTES + 1)
            opened_after = os.fstat(handle.fileno())
        after = candidate.stat()
    except AuditCommandProvenanceError:
        raise
    except OSError as exc:
        raise AuditCommandProvenanceError(f"{label}_unreadable") from exc
    if len(data) > _MAX_AUDIT_JSON_BYTES:
        _fail(f"{label}_too_large")
    if (
        _file_version(before) != _file_version(after)
        or _file_version(opened_before) != _file_version(opened_after)
        or _stat_identity(after) != _stat_identity(opened_after)
        or len(data) != int(after.st_size)
        or _has_link_like_component(lexical)
    ):
        _fail(f"{label}_changed_during_read")
    current_record = {
        "path": str(candidate),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if expected_record is not None:
        expected = _record_shape(
            expected_record,
            label=label,
            expected_path=candidate,
        )
        if current_record != expected:
            _fail(f"{label}_fingerprint_mismatch")
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise AuditCommandProvenanceError(f"{label}_json_unreadable") from exc
    if not isinstance(payload, dict):
        _fail(f"{label}_json_not_object")
    return payload


def _tail_text(path: Path) -> str:
    candidate = _canonical(path)
    try:
        size = candidate.stat().st_size
        with candidate.open("rb") as handle:
            handle.seek(max(0, size - 65536))
            data = handle.read()
    except OSError as exc:
        raise AuditCommandProvenanceError(f"audit_log_tail_unreadable:{candidate}") from exc
    return data.decode("utf-8", errors="replace")[-4000:]


def _code_file_record(path: Path) -> dict[str, Any]:
    candidate = _canonical(path)
    if _has_link_like_component(path):
        _fail("audit_code_file_link_like")
    try:
        version = _file_version(candidate.stat())
    except OSError as exc:
        raise AuditCommandProvenanceError("audit_code_file_unreadable") from exc
    cache_key = (str(candidate), version)
    with _CODE_RECORD_CACHE_LOCK:
        cached = _CODE_RECORD_CACHE.get(cache_key)
    if cached is not None:
        try:
            if _file_version(candidate.stat()) == version:
                return dict(cached)
        except OSError:
            pass
    record = file_record(candidate, label="audit_code_file")
    try:
        if _file_version(candidate.stat()) != version:
            _fail("audit_code_file_changed_during_read")
    except OSError as exc:
        raise AuditCommandProvenanceError("audit_code_file_unreadable") from exc
    with _CODE_RECORD_CACHE_LOCK:
        _CODE_RECORD_CACHE[cache_key] = dict(record)
    return record


def build_audit_code_manifest(repo_root: Path = DEFAULT_REPO_ROOT) -> dict[str, Any]:
    root = _canonical(repo_root)
    script = root / AUDIT_SCRIPT_RELATIVE_PATH
    package_root = root / AUDIT_PACKAGE_RELATIVE_PATH
    if not package_root.is_dir() or _has_link_like_component(package_root):
        _fail("audit_code_package_invalid")
    paths = [script, *sorted(package_root.rglob("*.py"), key=lambda path: str(path).casefold())]
    if not paths or len({_path_key(path) for path in paths}) != len(paths):
        _fail("audit_code_file_set_invalid")
    records = [_code_file_record(path) for path in paths]
    digest_payload = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": AUDIT_CODE_MANIFEST_SCHEMA_VERSION,
        "files": records,
        "sha256": hashlib.sha256(digest_payload.encode("utf-8")).hexdigest(),
    }


def absent_audit_input() -> dict[str, Any]:
    return {"present": False}


def build_merge_previous_input_record(
    source_path: Path,
    snapshot_path: Path,
    command_source_path: Path,
    command_snapshot_path: Path,
    *,
    allowed_changed_articles: Iterable[str],
) -> dict[str, Any]:
    articles = list(allowed_changed_articles)
    if (
        any(not isinstance(article, str) or not article for article in articles)
        or len(set(articles)) != len(articles)
    ):
        _fail("audit_merge_allowed_changed_articles_invalid")
    articles.sort()
    return {
        "present": True,
        "source_path": str(_canonical(source_path)),
        "snapshot": file_record(snapshot_path, label="audit_input_snapshot"),
        "command_source_path": str(_canonical(command_source_path)),
        "command_snapshot": file_record(
            command_snapshot_path,
            label="audit_merge_previous_command_snapshot",
        ),
        "allowed_changed_articles": articles,
    }


@dataclass(frozen=True)
class MergeBaselineAttestation:
    report_path: Path
    report: dict[str, Any]
    command: dict[str, Any]
    mapped_pdf_sources: dict[str, dict[str, Any]]
    original_pdf_map: dict[str, Path]
    allowed_changed_articles: frozenset[str]


def build_pdf_map_input_record(
    source_path: Path,
    source_snapshot_path: Path,
    materialized_snapshot_path: Path,
    pdf_sources: Iterable[tuple[str, Path, Path]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    seen_articles: set[str] = set()
    for article, pdf_source_path, pdf_snapshot_path in sorted(
        pdf_sources,
        key=lambda item: item[0],
    ):
        if not isinstance(article, str) or not article or article in seen_articles:
            _fail("audit_pdf_source_article_invalid")
        seen_articles.add(article)
        snapshot = file_record(pdf_snapshot_path, label="audit_pdf_source_snapshot")
        records.append(
            {
                "article": article,
                "source": {
                    "path": str(_canonical(pdf_source_path)),
                    "bytes": snapshot["bytes"],
                    "sha256": snapshot["sha256"],
                },
                "snapshot": snapshot,
            }
        )
    return {
        "present": True,
        "source_path": str(_canonical(source_path)),
        "source_snapshot": file_record(
            source_snapshot_path,
            label="audit_pdf_map_source_snapshot",
        ),
        "materialized_snapshot": file_record(
            materialized_snapshot_path,
            label="audit_pdf_map_materialized_snapshot",
        ),
        "pdf_sources": records,
    }


def _input_snapshot_path(value: dict[str, Any]) -> Path | None:
    if value.get("present") is False:
        return None
    snapshot = value.get("snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("path"), str):
        _fail("audit_input_snapshot_invalid")
    return Path(snapshot["path"])


def _pdf_map_snapshot_path(value: dict[str, Any]) -> Path | None:
    if value.get("present") is False:
        return None
    snapshot = value.get("materialized_snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("path"), str):
        _fail("audit_pdf_map_materialized_snapshot_invalid")
    return Path(snapshot["path"])


def build_audit_command(
    *,
    repo_root: Path,
    roots: Iterable[Path],
    output_path: Path,
    enable_pdf_diagnostics: bool,
    pdf_map_input: dict[str, Any],
    pdf_diagnostics_cache_dir: Path | None,
    jobs: int,
    merge_previous_report_input: dict[str, Any],
) -> list[str]:
    root = _canonical(repo_root)
    audit_roots = [_canonical(path) for path in roots]
    command = [
        str(_canonical(Path(sys.executable))),
        str(root / AUDIT_SCRIPT_RELATIVE_PATH),
        "--roots",
        *[str(path) for path in audit_roots],
        "--out",
        str(_canonical(output_path)),
    ]
    if enable_pdf_diagnostics:
        command.append("--pdf-diagnostics")
    pdf_map_path = _pdf_map_snapshot_path(pdf_map_input)
    if pdf_map_path is not None:
        command.extend(["--pdf-map", str(_canonical(pdf_map_path))])
    if pdf_diagnostics_cache_dir is not None:
        command.extend(["--pdf-diagnostics-cache-dir", str(_canonical(pdf_diagnostics_cache_dir))])
    if jobs > 1:
        command.extend(["--jobs", str(jobs)])
    previous_path = _input_snapshot_path(merge_previous_report_input)
    if previous_path is not None:
        command.extend(["--merge-previous-report", str(_canonical(previous_path))])
    return command


def build_audit_command_report(
    run_dir: Path,
    *,
    repo_root: Path,
    roots: Iterable[Path],
    enable_pdf_diagnostics: bool,
    pdf_map_input: dict[str, Any] | None,
    pdf_diagnostics_cache_dir: Path | None,
    jobs: int,
    merge_previous_report_input: dict[str, Any] | None,
    started_at: str,
    finished_at: str,
    returncode: int,
    environment_overrides: dict[str, str] | None = None,
    code_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_root = _canonical(run_dir)
    repo = _canonical(repo_root)
    audit_roots = [_canonical(path) for path in roots]
    map_input = pdf_map_input or absent_audit_input()
    previous_input = merge_previous_report_input or absent_audit_input()
    output_path = run_root / AUDIT_OUTPUT_NAME
    stdout_path = run_root / AUDIT_STDOUT_NAME
    stderr_path = run_root / AUDIT_STDERR_NAME
    output_record = file_record(output_path, label="audit_output")
    started, finished = _validated_command_interval(started_at, finished_at)
    output_payload = load_audit_json_object(
        output_path,
        label="audit_output",
        expected_record=output_record,
    )
    _validate_audit_generated_at(
        output_payload,
        started=started,
        finished=finished,
    )
    effective_environment_overrides = _validated_environment_overrides(
        AUDIT_SUBPROCESS_ENVIRONMENT_OVERRIDES
        if environment_overrides is None
        else environment_overrides
    )
    pdf_map_snapshot = _pdf_map_snapshot_path(map_input)
    previous_snapshot = _input_snapshot_path(previous_input)
    return {
        "schema_version": AUDIT_COMMAND_REPORT_SCHEMA_VERSION,
        "kind": AUDIT_COMMAND_REPORT_KIND,
        "command": build_audit_command(
            repo_root=repo,
            roots=audit_roots,
            output_path=output_path,
            enable_pdf_diagnostics=enable_pdf_diagnostics,
            pdf_map_input=map_input,
            pdf_diagnostics_cache_dir=pdf_diagnostics_cache_dir,
            jobs=jobs,
            merge_previous_report_input=previous_input,
        ),
        "repo_root": str(repo),
        "python_executable": str(_canonical(Path(sys.executable))),
        "python_version": sys.version,
        "environment_overrides": effective_environment_overrides,
        "code_manifest": code_manifest or build_audit_code_manifest(repo),
        "roots": [str(path) for path in audit_roots],
        "output_path": str(output_path),
        "command_output": output_record,
        "audit_output": output_record,
        "pdf_diagnostics_enabled": enable_pdf_diagnostics,
        "pdf_map_input": map_input,
        "pdf_map_path": str(pdf_map_snapshot) if pdf_map_snapshot is not None else "",
        "pdf_diagnostics_cache_dir": (
            str(_canonical(pdf_diagnostics_cache_dir)) if pdf_diagnostics_cache_dir is not None else ""
        ),
        "jobs": jobs,
        "merge_previous_report_input": previous_input,
        "merge_previous_report_path": str(previous_snapshot) if previous_snapshot is not None else "",
        "targeted_merge_enabled": previous_snapshot is not None,
        "postprocessors": [],
        "started_at": started_at,
        "finished_at": finished_at,
        "returncode": returncode,
        "stdout": file_record(stdout_path, allow_empty=True, label="audit_stdout"),
        "stderr": file_record(stderr_path, allow_empty=True, label="audit_stderr"),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_tail": _tail_text(stdout_path),
        "stderr_tail": _tail_text(stderr_path),
    }


def record_audit_postprocessor(
    run_dir: Path,
    *,
    name: str,
    input_record: dict[str, Any],
    input_snapshot_path: Path,
    command_input_record: dict[str, Any],
    command_snapshot_path: Path,
    inputs: Iterable[tuple[str, dict[str, Any], Path]],
) -> dict[str, Any]:
    if name != NORMALIZE_CONVERTED_IDS_POSTPROCESSOR:
        _fail(f"audit_postprocessor_unknown:{name}")
    run_root = _canonical(run_dir)
    report_path = run_root / AUDIT_COMMAND_REPORT_NAME
    report = load_audit_json_object(
        report_path,
        label="audit_command_report_for_postprocessor",
    )
    if (
        set(report) != _REPORT_FIELDS
        or report.get("schema_version") != AUDIT_COMMAND_REPORT_SCHEMA_VERSION
        or report.get("kind") != AUDIT_COMMAND_REPORT_KIND
    ):
        _fail("audit_command_report_unavailable_for_postprocessor")
    input_source = _record_shape(
        input_record,
        label="audit_postprocessor_input",
        expected_path=run_root / AUDIT_OUTPUT_NAME,
    )
    if report.get("audit_output") != input_source:
        _fail("audit_postprocessor_input_mismatch")
    input_snapshot = _snapshot_record_in_run(
        file_record(
            input_snapshot_path,
            label="audit_postprocessor_input_snapshot",
        ),
        label="audit_postprocessor_input_snapshot",
        run_dir=run_root,
    )
    if not _same_fingerprint(input_source, input_snapshot):
        _fail("audit_postprocessor_input_snapshot_mismatch")
    postprocessor_input = load_audit_json_object(
        Path(input_snapshot["path"]),
        label="audit_postprocessor_input_snapshot",
        expected_record=input_snapshot,
    )

    command_source = _record_matches_current(
        command_input_record,
        label="audit_postprocessor_command_input",
        expected_path=report_path,
    )
    command_snapshot = _snapshot_record_in_run(
        file_record(
            command_snapshot_path,
            label="audit_postprocessor_command_snapshot",
        ),
        label="audit_postprocessor_command_snapshot",
        run_dir=run_root,
    )
    if not _same_fingerprint(command_source, command_snapshot):
        _fail("audit_postprocessor_command_snapshot_mismatch")
    snapshotted_command = load_audit_json_object(
        command_snapshot_path,
        label="audit_postprocessor_command_snapshot",
        expected_record=command_snapshot,
    )
    if snapshotted_command != report:
        _fail("audit_postprocessor_command_snapshot_content_mismatch")

    input_records: list[dict[str, Any]] = []
    manifest_payload: dict[str, Any] | None = None
    for input_name, source_value, snapshot_path in inputs:
        if input_name != "manifest" or input_records:
            _fail("audit_postprocessor_inputs_invalid")
        source = _record_shape(
            source_value,
            label="audit_postprocessor_manifest_source",
            expected_path=run_root / "manifest.json",
        )
        snapshot = _snapshot_record_in_run(
            file_record(
                snapshot_path,
                label="audit_postprocessor_manifest_snapshot",
            ),
            label="audit_postprocessor_manifest_snapshot",
            run_dir=run_root,
        )
        if not _same_fingerprint(source, snapshot):
            _fail("audit_postprocessor_manifest_snapshot_mismatch")
        manifest_payload = load_audit_json_object(
            Path(snapshot["path"]),
            label="audit_postprocessor_manifest_snapshot",
            expected_record=snapshot,
        )
        input_records.append(
            {
                "name": input_name,
                "source": source,
                "snapshot": snapshot,
            }
        )
    if len(input_records) != 1:
        _fail("audit_postprocessor_inputs_invalid")
    assert manifest_payload is not None
    output_record = file_record(run_root / AUDIT_OUTPUT_NAME, label="audit_output")
    output_payload = load_audit_json_object(
        run_root / AUDIT_OUTPUT_NAME,
        label="audit_postprocessor_output",
        expected_record=output_record,
    )
    try:
        expected_output = normalize_converted_audit_article_ids_payload(
            postprocessor_input,
            manifest_payload,
        )
    except AuditPostprocessorError as exc:
        raise AuditCommandProvenanceError(
            f"audit_postprocessor_replay_invalid:{exc}"
        ) from exc
    if output_payload != expected_output:
        _fail("audit_postprocessor_output_replay_mismatch")
    postprocessors = report.get("postprocessors")
    if not isinstance(postprocessors, list) or any(
        isinstance(item, dict) and item.get("name") == name
        for item in postprocessors
    ):
        _fail("audit_postprocessor_chain_invalid")
    postprocessors.append(
        {
            "name": name,
            "command_input": command_source,
            "command_snapshot": command_snapshot,
            "input": input_source,
            "input_snapshot": input_snapshot,
            "inputs": input_records,
            "output": output_record,
        }
    )
    report["audit_output"] = output_record
    write_json(report_path, report)
    return report


def _validate_code_manifest(value: Any, *, repo_root: Path) -> None:
    if not isinstance(value, dict) or set(value) != {"schema_version", "files", "sha256"}:
        _fail("audit_code_manifest_invalid")
    if value.get("schema_version") != AUDIT_CODE_MANIFEST_SCHEMA_VERSION:
        _fail("audit_code_manifest_schema_invalid")
    current = build_audit_code_manifest(repo_root)
    if value != current:
        _fail("audit_code_manifest_mismatch")


def _validate_merge_previous_input(
    value: Any,
    *,
    run_dir: Path,
    current_command: dict[str, Any],
    enable_pdf_diagnostics: bool,
) -> MergeBaselineAttestation | None:
    label = "audit_merge_previous_input"
    if not isinstance(value, dict):
        _fail(f"{label}_invalid")
    if value.get("present") is False:
        if set(value) != {"present"}:
            _fail(f"{label}_absent_fields_invalid")
        return None
    if value.get("present") is not True or set(value) != {
        "present",
        "source_path",
        "snapshot",
        "command_source_path",
        "command_snapshot",
        "allowed_changed_articles",
    }:
        _fail(f"{label}_fields_invalid")
    source_path = value.get("source_path")
    command_source_path = value.get("command_source_path")
    if (
        not isinstance(source_path, str)
        or source_path != str(_canonical(run_dir) / AUDIT_OUTPUT_NAME)
    ):
        _fail(f"{label}_source_path_invalid")
    if (
        not isinstance(command_source_path, str)
        or command_source_path
        != str(_canonical(run_dir) / AUDIT_COMMAND_REPORT_NAME)
    ):
        _fail(f"{label}_command_source_path_invalid")
    report_snapshot = _snapshot_record_in_run(
        value.get("snapshot"),
        label=f"{label}_snapshot",
        run_dir=run_dir,
    )
    command_snapshot = _snapshot_record_in_run(
        value.get("command_snapshot"),
        label="audit_merge_previous_command_snapshot",
        run_dir=run_dir,
    )
    changed_value = value.get("allowed_changed_articles")
    if (
        not isinstance(changed_value, list)
        or not changed_value
        or not all(isinstance(article, str) and article for article in changed_value)
        or changed_value != sorted(set(changed_value))
    ):
        _fail("audit_merge_allowed_changed_articles_invalid")
    allowed_changed_articles = frozenset(changed_value)

    report = load_audit_json_object(
        Path(report_snapshot["path"]),
        label="audit_merge_baseline_report",
        expected_record=report_snapshot,
    )
    command = load_audit_json_object(
        Path(command_snapshot["path"]),
        label="audit_merge_baseline_command",
        expected_record=command_snapshot,
    )
    if (
        set(command) != _REPORT_FIELDS
        or command.get("schema_version") != AUDIT_COMMAND_REPORT_SCHEMA_VERSION
        or command.get("kind") != AUDIT_COMMAND_REPORT_KIND
    ):
        _fail("audit_merge_baseline_command_schema_invalid")
    baseline_started, baseline_finished = _validated_command_interval(
        command.get("started_at"),
        command.get("finished_at"),
    )
    _validate_audit_generated_at(
        report,
        started=baseline_started,
        finished=baseline_finished,
    )
    for field in (
        "repo_root",
        "python_executable",
        "python_version",
        "environment_overrides",
        "code_manifest",
    ):
        if command.get(field) != current_command.get(field):
            _fail(f"audit_merge_baseline_command_{field}_mismatch")
    if (
        command.get("targeted_merge_enabled") is not False
        or command.get("merge_previous_report_input") != {"present": False}
        or command.get("merge_previous_report_path") != ""
    ):
        _fail("audit_merge_baseline_not_full")
    if command.get("pdf_diagnostics_enabled") is not enable_pdf_diagnostics:
        _fail("audit_merge_baseline_pdf_diagnostics_mismatch")
    if command.get("returncode") != 0 or command.get("output_path") != source_path:
        _fail("audit_merge_baseline_command_result_invalid")
    baseline_output = _record_shape(
        command.get("audit_output"),
        label="audit_merge_baseline_output",
        expected_path=Path(source_path),
    )
    if (
        baseline_output["bytes"] != report_snapshot["bytes"]
        or baseline_output["sha256"] != report_snapshot["sha256"]
    ):
        _fail("audit_merge_baseline_output_fingerprint_mismatch")
    if "targeted_audit" in report:
        _fail("audit_merge_baseline_report_not_full")

    pdf_map_path, mapped_pdf_sources, original_pdf_map = _validate_pdf_map_input(
        command.get("pdf_map_input"),
        run_dir=run_dir,
    )
    expected_pdf_map_path = str(pdf_map_path) if pdf_map_path is not None else ""
    if command.get("pdf_map_path") != expected_pdf_map_path:
        _fail("audit_merge_baseline_pdf_map_path_mismatch")
    if pdf_map_path is not None and not enable_pdf_diagnostics:
        _fail("audit_merge_baseline_pdf_map_without_diagnostics")
    return MergeBaselineAttestation(
        report_path=Path(report_snapshot["path"]),
        report=report,
        command=command,
        mapped_pdf_sources=mapped_pdf_sources,
        original_pdf_map=original_pdf_map,
        allowed_changed_articles=allowed_changed_articles,
    )


def _snapshot_record_in_run(
    value: Any,
    *,
    label: str,
    run_dir: Path,
) -> dict[str, Any]:
    record = _record_shape(value, label=label)
    snapshot_path = Path(record["path"])
    files_root = _canonical(run_dir) / ENRICHMENT_SNAPSHOT_DIR_NAME / ENRICHMENT_FILES_DIR_NAME
    if not _is_within(snapshot_path, files_root):
        _fail(f"{label}_outside_run")
    return _record_matches_current(
        record,
        label=label,
        expected_path=snapshot_path,
    )


def _canonical_pdf_map_entries(
    entries: dict[str, Path],
    *,
    label: str,
) -> dict[str, Path]:
    canonical: dict[str, Path] = {}
    for article, path in entries.items():
        if (
            not path.is_absolute()
            or str(path) != str(_canonical(path))
        ):
            _fail(f"{label}_path_not_canonical:{article}")
        if _has_link_like_component(path):
            _fail(f"{label}_path_link_like:{article}")
        canonical[article] = _canonical(path)
    return canonical


def _validate_pdf_map_input(
    value: Any,
    *,
    run_dir: Path,
) -> tuple[Path | None, dict[str, dict[str, Any]], dict[str, Path]]:
    if not isinstance(value, dict):
        _fail("audit_pdf_map_input_invalid")
    if value.get("present") is False:
        if set(value) != {"present"}:
            _fail("audit_pdf_map_input_absent_fields_invalid")
        return None, {}, {}
    if value.get("present") is not True or set(value) != {
        "present",
        "source_path",
        "source_snapshot",
        "materialized_snapshot",
        "pdf_sources",
    }:
        _fail("audit_pdf_map_input_fields_invalid")
    source_path = value.get("source_path")
    if (
        not isinstance(source_path, str)
        or not Path(source_path).is_absolute()
        or source_path != str(_canonical(Path(source_path)))
    ):
        _fail("audit_pdf_map_input_source_path_invalid")
    source_snapshot = _snapshot_record_in_run(
        value.get("source_snapshot"),
        label="audit_pdf_map_source_snapshot",
        run_dir=run_dir,
    )
    materialized_snapshot = _snapshot_record_in_run(
        value.get("materialized_snapshot"),
        label="audit_pdf_map_materialized_snapshot",
        run_dir=run_dir,
    )
    pdf_sources = value.get("pdf_sources")
    if not isinstance(pdf_sources, list):
        _fail("audit_pdf_sources_invalid")

    source_records: dict[str, dict[str, Any]] = {}
    listed_articles: list[str] = []
    for item in pdf_sources:
        if not isinstance(item, dict) or set(item) != {"article", "source", "snapshot"}:
            _fail("audit_pdf_source_record_invalid")
        article = item.get("article")
        if not isinstance(article, str) or not article or article in source_records:
            _fail("audit_pdf_source_article_invalid")
        source = _record_shape(item.get("source"), label="audit_pdf_source")
        snapshot = _snapshot_record_in_run(
            item.get("snapshot"),
            label="audit_pdf_source_snapshot",
            run_dir=run_dir,
        )
        if (
            source["bytes"] != snapshot["bytes"]
            or source["sha256"] != snapshot["sha256"]
        ):
            _fail(f"audit_pdf_source_fingerprint_mismatch:{article}")
        source_records[article] = {"source": source, "snapshot": snapshot}
        listed_articles.append(article)
    if listed_articles != sorted(listed_articles):
        _fail("audit_pdf_sources_not_sorted")

    try:
        original_map = load_pdf_map(Path(source_snapshot["path"]))
        materialized_map = load_pdf_map(Path(materialized_snapshot["path"]))
    except (OSError, UnicodeError, ValueError) as exc:
        raise AuditCommandProvenanceError("audit_pdf_map_snapshot_invalid") from exc
    original_map = _canonical_pdf_map_entries(
        original_map,
        label="audit_pdf_map_source",
    )
    materialized_map = _canonical_pdf_map_entries(
        materialized_map,
        label="audit_pdf_map_materialized",
    )
    expected_materialized = {
        article: Path(record["snapshot"]["path"])
        for article, record in source_records.items()
    }
    if materialized_map != expected_materialized:
        _fail("audit_pdf_map_materialization_mismatch")
    for article, record in source_records.items():
        original_path = original_map.get(article)
        if original_path is None or str(original_path) != record["source"]["path"]:
            _fail(f"audit_pdf_map_source_mismatch:{article}")
    return (
        Path(materialized_snapshot["path"]),
        source_records,
        original_map,
    )


def _validate_audit_report_sources(
    audit_report: dict[str, Any],
    *,
    enable_pdf_diagnostics: bool,
    mapped_pdf_sources: dict[str, dict[str, Any]],
    original_pdf_map: dict[str, Path],
    allowed_changed_articles: frozenset[str] = frozenset(),
) -> None:
    if audit_report.get("audit_status") != "complete":
        _fail("audit_report_not_complete")
    articles = audit_report.get("articles")
    if not isinstance(articles, list):
        _fail("audit_report_articles_invalid")
    count = len(articles)
    for field in ("article_count", "processed_pair_count", "total_pair_count"):
        if type(audit_report.get(field)) is not int or audit_report.get(field) != count:
            _fail(f"audit_report_{field}_mismatch")
    seen_articles: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for article in articles:
        if not isinstance(article, dict):
            _fail("audit_report_article_invalid")
        article_id = article.get("article")
        if not isinstance(article_id, str) or not article_id or article_id in seen_articles:
            _fail("audit_report_article_identity_invalid")
        seen_articles.add(article_id)
        raw_path = article.get("raw_stage_path")
        polish_path = article.get("polish_stage_path")
        if not isinstance(raw_path, str) or not isinstance(polish_path, str):
            _fail(f"audit_report_stage_path_invalid:{article_id}")
        pair = (str(_canonical(Path(raw_path))), str(_canonical(Path(polish_path))))
        if pair != (raw_path, polish_path) or pair in seen_pairs:
            _fail(f"audit_report_stage_pair_invalid:{article_id}")
        seen_pairs.add(pair)
        raw_bytes = article.get("raw_stage_bytes")
        raw_sha256 = article.get("raw_stage_sha256")
        polish_bytes = article.get("polish_stage_bytes")
        polish_sha256 = article.get("polish_stage_sha256")
        if (
            type(raw_bytes) is not int
            or raw_bytes < 1
            or not _is_sha256(raw_sha256)
            or type(polish_bytes) is not int
            or polish_bytes < 1
            or not _is_sha256(polish_sha256)
        ):
            _fail(f"audit_report_stage_fingerprint_invalid:{article_id}")
        if article_id not in allowed_changed_articles:
            raw_record = file_record(Path(raw_path), label="audit_raw_stage")
            polish_record = file_record(Path(polish_path), label="audit_polish_stage")
            if raw_bytes != raw_record["bytes"] or raw_sha256 != raw_record["sha256"]:
                _fail(f"audit_report_raw_fingerprint_mismatch:{article_id}")
            if (
                polish_bytes != polish_record["bytes"]
                or polish_sha256 != polish_record["sha256"]
            ):
                _fail(f"audit_report_polish_fingerprint_mismatch:{article_id}")

        summary = article.get("summary")
        if not isinstance(summary, dict):
            _fail(f"audit_report_summary_invalid:{article_id}")
        if summary.get("pdf_diagnostics_enabled") is not enable_pdf_diagnostics:
            _fail(f"audit_report_pdf_diagnostics_flag_mismatch:{article_id}")
        if not enable_pdf_diagnostics:
            continue

        source_path_value = summary.get("source_pdf_path")
        source_present = summary.get("source_pdf_present")
        source_bytes = summary.get("source_pdf_bytes")
        source_sha256 = summary.get("source_pdf_sha256")
        source_origin = summary.get("source_pdf_origin")
        if (
            not isinstance(source_path_value, str)
            or not Path(source_path_value).is_absolute()
            or source_path_value != str(_canonical(Path(source_path_value)))
            or type(source_present) is not bool
            or type(source_bytes) is not int
            or source_bytes < 0
            or not isinstance(source_sha256, str)
            or source_origin not in {"map", "stage"}
            or (
                source_present
                and (source_bytes < 1 or not _is_sha256(source_sha256))
            )
            or (not source_present and (source_bytes != 0 or source_sha256 != ""))
        ):
            _fail(f"audit_report_pdf_source_invalid:{article_id}")
        source_path = Path(source_path_value)
        mapped_source = mapped_pdf_sources.get(article_id)
        if mapped_source is not None:
            expected = mapped_source["snapshot"]
            if (
                source_origin != "map"
                or source_present is not True
                or source_path_value != expected["path"]
                or source_bytes != expected["bytes"]
                or source_sha256 != expected["sha256"]
            ):
                _fail(f"audit_report_pdf_source_mismatch:{article_id}")
            continue

        expected_stage_path = _canonical(Path(raw_path).parent / "00.source.pdf")
        if source_origin != "stage" or source_path_value != str(expected_stage_path):
            _fail(f"audit_report_pdf_stage_source_mismatch:{article_id}")
        if article_id in allowed_changed_articles:
            continue
        if source_present:
            current_source = file_record(
                source_path,
                label="audit_report_pdf_stage_source",
            )
            if (
                source_bytes != current_source["bytes"]
                or source_sha256 != current_source["sha256"]
            ):
                _fail(f"audit_report_pdf_stage_fingerprint_mismatch:{article_id}")
        elif (
            source_bytes != 0
            or source_sha256
            or source_path.exists()
            or _has_link_like_component(source_path)
        ):
            _fail(f"audit_report_pdf_stage_absence_mismatch:{article_id}")

    if not allowed_changed_articles <= seen_articles:
        _fail("audit_report_allowed_changed_articles_missing")
    expected_mapped_articles = seen_articles & set(original_pdf_map)
    if set(mapped_pdf_sources) != expected_mapped_articles:
        _fail(
            "audit_pdf_source_article_set_mismatch:"
            f"expected={','.join(sorted(expected_mapped_articles))}:"
            f"actual={','.join(sorted(mapped_pdf_sources))}"
        )


_CORPUS_RECOMPUTED_FIELDS = frozenset(
    {
        "same_pattern_hits_across_corpus",
        "same_pattern_observed_hits_across_corpus",
    }
)
_TARGETED_AUDIT_FIELDS = frozenset(
    {
        "enabled",
        "previous_report_path",
        "target_roots",
        "target_article_count",
        "reused_article_count",
        "replaced_article_count",
        "new_article_count",
        "replaced_articles",
        "new_articles",
    }
)


def _same_fingerprint(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("bytes") == right.get("bytes")
        and left.get("sha256") == right.get("sha256")
    )


def _without_recomputed_corpus_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_recomputed_corpus_fields(item)
            for key, item in value.items()
            if key not in _CORPUS_RECOMPUTED_FIELDS
        }
    if isinstance(value, list):
        return [_without_recomputed_corpus_fields(item) for item in value]
    return value


def _article_records_by_id(
    report: dict[str, Any],
    *,
    label: str,
) -> dict[str, dict[str, Any]]:
    articles = report.get("articles")
    if not isinstance(articles, list):
        _fail(f"{label}_articles_invalid")
    records: dict[str, dict[str, Any]] = {}
    for article in articles:
        if not isinstance(article, dict):
            _fail(f"{label}_article_invalid")
        article_id = article.get("article")
        if not isinstance(article_id, str) or not article_id or article_id in records:
            _fail(f"{label}_article_identity_invalid")
        records[article_id] = article
    return records


def _target_article_ids_for_roots(
    report: dict[str, Any],
    roots: Iterable[Path],
) -> frozenset[str]:
    selected: set[str] = set()
    root_list = list(roots)
    for article_id, article in _article_records_by_id(
        report,
        label="audit_target",
    ).items():
        raw_value = article.get("raw_stage_path")
        polish_value = article.get("polish_stage_path")
        if not isinstance(raw_value, str) or not isinstance(polish_value, str):
            _fail(f"audit_target_stage_path_invalid:{article_id}")
        raw_path = Path(raw_value)
        polish_path = Path(polish_value)
        if any(
            (
                _is_within(raw_path, root)
                and _is_within(polish_path, root)
            )
            or _same_path(raw_path, root)
            or _same_path(polish_path, root)
            for root in root_list
        ):
            selected.add(article_id)
    return frozenset(selected)


def _validate_targeted_merge_authority(
    audit_report: dict[str, Any],
    *,
    roots: list[Path],
    enable_pdf_diagnostics: bool,
    current_mapped_pdf_sources: dict[str, dict[str, Any]],
    current_original_pdf_map: dict[str, Path],
    baseline: MergeBaselineAttestation,
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    _validate_audit_report_sources(
        baseline.report,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        mapped_pdf_sources=baseline.mapped_pdf_sources,
        original_pdf_map=baseline.original_pdf_map,
        allowed_changed_articles=baseline.allowed_changed_articles,
    )
    baseline_roots = baseline.report.get("roots")
    if (
        not isinstance(baseline_roots, list)
        or baseline_roots != baseline.command.get("roots")
        or "targeted_audit" in baseline.report
    ):
        _fail("audit_merge_baseline_roots_invalid")

    current_articles = _article_records_by_id(audit_report, label="audit_merged")
    baseline_articles = _article_records_by_id(
        baseline.report,
        label="audit_merge_baseline",
    )
    if set(current_articles) != set(baseline_articles):
        _fail("audit_merge_article_set_mismatch")
    target_articles = _target_article_ids_for_roots(audit_report, roots)
    if target_articles != baseline.allowed_changed_articles:
        _fail("audit_merge_target_article_set_mismatch")
    for article_id in sorted(set(current_articles) - set(target_articles)):
        if _without_recomputed_corpus_fields(
            current_articles[article_id]
        ) != _without_recomputed_corpus_fields(baseline_articles[article_id]):
            _fail(f"audit_merge_carried_article_mismatch:{article_id}")

    targeted = audit_report.get("targeted_audit")
    expected_targeted = {
        "enabled": True,
        "previous_report_path": str(baseline.report_path),
        "target_roots": [str(root) for root in roots],
        "target_article_count": len(target_articles),
        "reused_article_count": len(current_articles) - len(target_articles),
        "replaced_article_count": len(target_articles),
        "new_article_count": 0,
        "replaced_articles": sorted(target_articles),
        "new_articles": [],
    }
    if (
        not isinstance(targeted, dict)
        or set(targeted) != _TARGETED_AUDIT_FIELDS
        or targeted != expected_targeted
    ):
        _fail("audit_report_targeted_metadata_invalid")

    if not set(current_mapped_pdf_sources) <= set(target_articles):
        _fail("audit_merge_current_pdf_sources_outside_target")
    carried_articles = set(current_articles) - set(target_articles)
    effective_mapped = dict(current_mapped_pdf_sources)
    effective_mapped.update(
        {
            article: record
            for article, record in baseline.mapped_pdf_sources.items()
            if article in carried_articles
        }
    )
    effective_original = {
        article: path
        for article, path in current_original_pdf_map.items()
        if article in target_articles
    }
    effective_original.update(
        {
            article: path
            for article, path in baseline.original_pdf_map.items()
            if article in carried_articles
        }
    )
    return effective_mapped, effective_original


def _validate_postprocessors(
    value: Any,
    *,
    command_report: dict[str, Any],
    audit_report: dict[str, Any],
    command_output: dict[str, Any],
    audit_output: dict[str, Any],
    run_dir: Path,
) -> None:
    if not isinstance(value, list):
        _fail("audit_postprocessors_invalid")
    previous = command_output
    seen: set[str] = set()
    replayed_output: dict[str, Any] | None = None
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {
            "name",
            "command_input",
            "command_snapshot",
            "input",
            "input_snapshot",
            "inputs",
            "output",
        }:
            _fail("audit_postprocessor_record_invalid")
        name = item.get("name")
        if name != NORMALIZE_CONVERTED_IDS_POSTPROCESSOR or name in seen:
            _fail(f"audit_postprocessor_invalid:{name}")
        seen.add(name)
        input_record = _record_shape(
            item.get("input"),
            label="audit_postprocessor_input",
            expected_path=_canonical(run_dir) / AUDIT_OUTPUT_NAME,
        )
        output_record = _record_shape(
            item.get("output"),
            label="audit_postprocessor_output",
            expected_path=_canonical(run_dir) / AUDIT_OUTPUT_NAME,
        )
        if input_record != previous:
            _fail("audit_postprocessor_chain_input_mismatch")
        input_snapshot = _snapshot_record_in_run(
            item.get("input_snapshot"),
            label="audit_postprocessor_input_snapshot",
            run_dir=run_dir,
        )
        if not _same_fingerprint(input_record, input_snapshot):
            _fail("audit_postprocessor_input_snapshot_mismatch")
        postprocessor_input = load_audit_json_object(
            Path(input_snapshot["path"]),
            label="audit_postprocessor_input_snapshot",
            expected_record=input_snapshot,
        )

        command_input = _record_shape(
            item.get("command_input"),
            label="audit_postprocessor_command_input",
            expected_path=_canonical(run_dir) / AUDIT_COMMAND_REPORT_NAME,
        )
        command_snapshot = _snapshot_record_in_run(
            item.get("command_snapshot"),
            label="audit_postprocessor_command_snapshot",
            run_dir=run_dir,
        )
        if not _same_fingerprint(command_input, command_snapshot):
            _fail("audit_postprocessor_command_snapshot_mismatch")
        snapshotted_command = load_audit_json_object(
            Path(command_snapshot["path"]),
            label="audit_postprocessor_command_snapshot",
            expected_record=command_snapshot,
        )
        expected_command = dict(command_report)
        expected_command["audit_output"] = input_record
        expected_command["postprocessors"] = value[:index]
        if snapshotted_command != expected_command:
            _fail("audit_postprocessor_command_snapshot_content_mismatch")
        inputs = item.get("inputs")
        if not isinstance(inputs, list) or len(inputs) != 1:
            _fail("audit_postprocessor_inputs_invalid")
        manifest_input = inputs[0]
        if not isinstance(manifest_input, dict) or set(manifest_input) != {
            "name",
            "source",
            "snapshot",
        }:
            _fail("audit_postprocessor_manifest_invalid")
        if manifest_input.get("name") != "manifest":
            _fail("audit_postprocessor_manifest_name_invalid")
        manifest_source = _record_shape(
            manifest_input.get("source"),
            label="audit_postprocessor_manifest_source",
            expected_path=_canonical(run_dir) / "manifest.json",
        )
        manifest_snapshot = _snapshot_record_in_run(
            manifest_input.get("snapshot"),
            label="audit_postprocessor_manifest_snapshot",
            run_dir=run_dir,
        )
        if not _same_fingerprint(manifest_source, manifest_snapshot):
            _fail("audit_postprocessor_manifest_snapshot_mismatch")
        manifest_payload = load_audit_json_object(
            Path(manifest_snapshot["path"]),
            label="audit_postprocessor_manifest_snapshot",
            expected_record=manifest_snapshot,
        )
        try:
            replayed_output = normalize_converted_audit_article_ids_payload(
                postprocessor_input,
                manifest_payload,
            )
        except AuditPostprocessorError as exc:
            raise AuditCommandProvenanceError(
                f"audit_postprocessor_replay_invalid:{exc}"
            ) from exc
        previous = output_record
    if previous != audit_output:
        _fail("audit_postprocessor_chain_output_mismatch")
    if value and replayed_output != audit_report:
        _fail("audit_postprocessor_output_replay_mismatch")


def validate_audit_command_report(
    run_dir: Path,
    audit_report: dict[str, Any],
    command_report: dict[str, Any],
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
    allowed_changed_article_ids: Iterable[str] = (),
) -> None:
    run_root = _canonical(run_dir)
    repo = _canonical(repo_root)
    changed_articles = list(allowed_changed_article_ids)
    if (
        any(not isinstance(article, str) or not article for article in changed_articles)
        or len(set(changed_articles)) != len(changed_articles)
    ):
        _fail("audit_command_allowed_changed_articles_invalid")
    allowed_changed_articles = frozenset(changed_articles)
    if set(command_report) != _REPORT_FIELDS:
        _fail("audit_command_report_schema_invalid")
    if command_report.get("schema_version") != AUDIT_COMMAND_REPORT_SCHEMA_VERSION:
        _fail("audit_command_report_schema_invalid")
    if command_report.get("kind") != AUDIT_COMMAND_REPORT_KIND:
        _fail("audit_command_report_kind_invalid")
    if command_report.get("repo_root") != str(repo):
        _fail("audit_command_repo_root_invalid")
    if command_report.get("python_executable") != str(_canonical(Path(sys.executable))):
        _fail("audit_command_python_invalid")
    if command_report.get("python_version") != sys.version:
        _fail("audit_command_python_version_invalid")
    _validated_environment_overrides(
        command_report.get("environment_overrides")
    )
    _validate_code_manifest(command_report.get("code_manifest"), repo_root=repo)

    roots_value = command_report.get("roots")
    if not isinstance(roots_value, list) or not roots_value:
        _fail("audit_command_roots_invalid")
    roots: list[Path] = []
    for raw_root in roots_value:
        if not isinstance(raw_root, str) or not Path(raw_root).is_absolute():
            _fail("audit_command_root_invalid")
        root = canonical_existing_root(Path(raw_root))
        if raw_root != str(root):
            _fail("audit_command_root_not_canonical")
        roots.append(root)
    if len({_path_key(root) for root in roots}) != len(roots):
        _fail("audit_command_roots_duplicate")

    output_path = run_root / AUDIT_OUTPUT_NAME
    if command_report.get("output_path") != str(output_path):
        _fail("audit_command_output_path_invalid")
    command_output = _record_shape(
        command_report.get("command_output"),
        label="audit_command_output",
        expected_path=output_path,
    )
    audit_output = _record_matches_current(
        command_report.get("audit_output"),
        label="audit_output",
        expected_path=output_path,
    )

    enable_pdf_diagnostics = command_report.get("pdf_diagnostics_enabled")
    if type(enable_pdf_diagnostics) is not bool:
        _fail("audit_command_pdf_diagnostics_invalid")
    pdf_map_path, mapped_pdf_sources, original_pdf_map = _validate_pdf_map_input(
        command_report.get("pdf_map_input"),
        run_dir=run_root,
    )
    if pdf_map_path is not None and not enable_pdf_diagnostics:
        _fail("audit_command_pdf_map_without_diagnostics")
    expected_pdf_map_path = str(pdf_map_path) if pdf_map_path is not None else ""
    if command_report.get("pdf_map_path") != expected_pdf_map_path:
        _fail("audit_command_pdf_map_path_mismatch")

    cache_value = command_report.get("pdf_diagnostics_cache_dir")
    if not isinstance(cache_value, str):
        _fail("audit_command_cache_dir_invalid")
    cache_dir: Path | None = None
    if cache_value:
        cache_dir = _canonical(Path(cache_value))
        if cache_value != str(cache_dir) or _has_link_like_component(cache_dir):
            _fail("audit_command_cache_dir_invalid")

    jobs = command_report.get("jobs")
    if type(jobs) is not int or jobs < 1:
        _fail("audit_command_jobs_invalid")
    merge_baseline = _validate_merge_previous_input(
        command_report.get("merge_previous_report_input"),
        run_dir=run_root,
        current_command=command_report,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
    )
    previous_path = merge_baseline.report_path if merge_baseline is not None else None
    expected_previous_path = str(previous_path) if previous_path is not None else ""
    if command_report.get("merge_previous_report_path") != expected_previous_path:
        _fail("audit_command_merge_previous_path_mismatch")
    if command_report.get("targeted_merge_enabled") is not (previous_path is not None):
        _fail("audit_command_targeted_merge_flag_mismatch")

    expected_command = build_audit_command(
        repo_root=repo,
        roots=roots,
        output_path=output_path,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_input=command_report["pdf_map_input"],
        pdf_diagnostics_cache_dir=cache_dir,
        jobs=jobs,
        merge_previous_report_input=command_report["merge_previous_report_input"],
    )
    if command_report.get("command") != expected_command:
        _fail("audit_command_argv_mismatch")
    if type(command_report.get("returncode")) is not int or command_report.get("returncode") != 0:
        _fail("audit_command_returncode_invalid")
    started, finished = _validated_command_interval(
        command_report.get("started_at"),
        command_report.get("finished_at"),
    )
    _validate_audit_generated_at(
        audit_report,
        started=started,
        finished=finished,
    )

    stdout_path = run_root / AUDIT_STDOUT_NAME
    stderr_path = run_root / AUDIT_STDERR_NAME
    if command_report.get("stdout_path") != str(stdout_path):
        _fail("audit_stdout_path_mismatch")
    if command_report.get("stderr_path") != str(stderr_path):
        _fail("audit_stderr_path_mismatch")
    _record_matches_current(
        command_report.get("stdout"),
        label="audit_stdout",
        expected_path=stdout_path,
        allow_empty=True,
    )
    _record_matches_current(
        command_report.get("stderr"),
        label="audit_stderr",
        expected_path=stderr_path,
        allow_empty=True,
    )
    if command_report.get("stdout_tail") != _tail_text(stdout_path):
        _fail("audit_stdout_tail_mismatch")
    if command_report.get("stderr_tail") != _tail_text(stderr_path):
        _fail("audit_stderr_tail_mismatch")

    _validate_postprocessors(
        command_report.get("postprocessors"),
        command_report=command_report,
        audit_report=audit_report,
        command_output=command_output,
        audit_output=audit_output,
        run_dir=run_root,
    )
    effective_mapped_pdf_sources = mapped_pdf_sources
    effective_original_pdf_map = original_pdf_map
    if merge_baseline is not None:
        if allowed_changed_articles:
            _fail("audit_command_nested_allowed_changed_articles")
        (
            effective_mapped_pdf_sources,
            effective_original_pdf_map,
        ) = _validate_targeted_merge_authority(
            audit_report,
            roots=roots,
            enable_pdf_diagnostics=enable_pdf_diagnostics,
            current_mapped_pdf_sources=mapped_pdf_sources,
            current_original_pdf_map=original_pdf_map,
            baseline=merge_baseline,
        )
    _validate_audit_report_sources(
        audit_report,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        mapped_pdf_sources=effective_mapped_pdf_sources,
        original_pdf_map=effective_original_pdf_map,
        allowed_changed_articles=allowed_changed_articles,
    )

    report_roots = audit_report.get("roots")
    if not isinstance(report_roots, list) or not all(isinstance(root, str) for root in report_roots):
        _fail("audit_report_roots_invalid")
    if previous_path is None:
        if report_roots != [str(root) for root in roots] or "targeted_audit" in audit_report:
            _fail("audit_report_roots_mismatch")
    else:
        targeted = audit_report.get("targeted_audit")
        if not isinstance(targeted, dict):
            _fail("audit_report_targeted_metadata_missing")
        if targeted.get("enabled") is not True:
            _fail("audit_report_targeted_flag_invalid")
        if targeted.get("target_roots") != [str(root) for root in roots]:
            _fail("audit_report_target_roots_mismatch")
        if targeted.get("previous_report_path") != str(previous_path):
            _fail("audit_report_previous_path_mismatch")
