from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence
from unicodedata import normalize

from .artifact_integrity import artifact_is_structurally_valid, fingerprint_file
from .atomic_io import copy_file_atomic as _copy_file_atomic
from .atomic_io import write_json_atomic as _write_json_atomic
from .directory_publication import CompleteDirectoryPublication
from .marker_runner import MarkerRunner, terminate_process_tree
from .models import PipelineSummary
from .pipeline import run_pipeline
from .pipeline_options import PipelineOptions
from .html_stages import (
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    article_dir_from_html_stage,
    require_current_raw_conversions,
)
from .language_detect import LanguageGateDecision, detect_language_from_html
from .quality_loop.cached_run_state import path_is_link_like
from .quality_loop.publication_state import validate_quality_publication
from .stage_contract import (
    publish_latest_polish_from_quality_run,
    stage_sealed_polish,
)


QUALITY_LOOP_SCRIPT = "scripts/llm_quality_loop.py"
FINAL_HTML_DIR_NAME = "final_html"
FINAL_HTML_MANIFEST_NAME = "final_html_manifest.json"
PIPELINE_MANIFEST_NAME = "pipeline_manifest.json"
_MAX_FINAL_HTML_MANIFEST_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class CleanPipelineOptions:
    conversion_options: PipelineOptions
    quality_output_dir: str | None = None
    run_id: str | None = None
    jobs: int | None = None
    repolish_jobs: int | None = None
    audit_jobs: int | None = None
    p62_marker_recovery_jobs: int | None = None
    p62_recovery_jobs: int | None = None
    polish_auto_repair_jobs: int | None = None
    previous_entry: str | None = None
    gate_config: str | None = None
    final_html_dir: str | None = None
    no_append_history: bool = True
    skip_quality_tests: bool = False
    fail_on_gate: bool = True
    publish_latest_to_converted: bool = True
    prune_extra_html: bool = True
    publish_report_path: str | None = None
    reuse_existing_conversion: bool = False


@dataclass(frozen=True)
class FinalHtmlArtifact:
    article: str
    source_path: Path
    final_path: Path


@dataclass(frozen=True)
class FinalHtmlCollection:
    final_html_dir: Path
    manifest_path: Path
    artifacts: tuple[FinalHtmlArtifact, ...]


@dataclass(frozen=True)
class CleanPipelineSummary:
    conversion_summary: PipelineSummary
    quality_output_dir: Path
    run_id: str
    observe_command: tuple[str, ...]
    observe_exit_code: int
    converted_stage_publish_report: dict[str, Any] | None
    final_html: FinalHtmlCollection


def source_language_payload(html: str) -> dict[str, Any]:
    detection = detect_language_from_html(html)
    detected = (detection.detected_language or "unknown").lower()
    skip = detected == "ru" and detection.confidence >= 0.75
    gate = LanguageGateDecision(skip, "already_russian" if skip else f"translate_{detected}_to_ru")
    return {
        "detection": detection.to_dict(),
        "gate": gate.to_dict(),
        "source_language_code": detected,
    }


def write_pipeline_manifest(converted_root: Path) -> Path:
    root = converted_root.expanduser().resolve(strict=False)
    articles: list[dict[str, Any]] = []
    for polish_path in sorted(root.rglob(POLISH_STAGE_NAME), key=str):
        if not polish_path.is_file():
            continue
        payload = source_language_payload(polish_path.read_text(encoding="utf-8", errors="replace"))
        article_dir = article_dir_from_html_stage(polish_path)
        sidecar = {
            "schema_version": 1,
            "kind": "pdf_html_article",
            "article": article_dir.name,
            "en_html_path": str(polish_path.resolve(strict=False)),
            **payload,
        }
        sidecar_path = polish_path.parent / PIPELINE_MANIFEST_NAME
        _write_json_atomic(sidecar_path, sidecar)
        articles.append(
            {
                "article": article_dir.name,
                "en_html_path": str(polish_path.resolve(strict=False)),
                "manifest_path": str(sidecar_path.resolve(strict=False)),
                **payload,
            }
        )

    manifest_path = root / PIPELINE_MANIFEST_NAME
    _write_json_atomic(
        manifest_path,
        {
            "schema_version": 1,
            "kind": "pdf_html_pipeline",
            "converted_root": str(root),
            "articles": articles,
        },
    )
    return manifest_path


def default_quality_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve(strict=False)
    return resolved.parent / f"{resolved.name}_quality"


def default_run_id(quality_output_dir: Path) -> str:
    return quality_output_dir.expanduser().resolve(strict=False).name


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def quality_loop_script_path() -> Path:
    return repository_root() / QUALITY_LOOP_SCRIPT


def build_observe_command(
    *,
    converted_root: Path,
    quality_output_dir: Path,
    run_id: str,
    jobs: int | None = None,
    repolish_jobs: int | None = None,
    audit_jobs: int | None = None,
    p62_marker_recovery_jobs: int | None = None,
    p62_recovery_jobs: int | None = None,
    polish_auto_repair_jobs: int | None = None,
    previous_entry: Path | None = None,
    gate_config: Path | None = None,
    no_append_history: bool = True,
    skip_quality_tests: bool = False,
    fail_on_gate: bool = True,
    script_path: Path | None = None,
) -> list[str]:
    script = script_path or quality_loop_script_path()
    command = [
        sys.executable,
        str(script),
        "observe",
        "--converted-roots",
        str(converted_root),
        "--out-dir",
        str(quality_output_dir),
        "--run-id",
        run_id,
        "--polish-language",
        "auto",
        "--include-non-target-language",
    ]
    for flag, value in (
        ("--jobs", jobs),
        ("--repolish-jobs", repolish_jobs),
        ("--audit-jobs", audit_jobs),
        ("--p62-marker-recovery-jobs", p62_marker_recovery_jobs),
        ("--p62-recovery-jobs", p62_recovery_jobs),
        ("--polish-auto-repair-jobs", polish_auto_repair_jobs),
    ):
        if value is not None:
            command.extend([flag, str(int(value))])
    if previous_entry is not None:
        command.extend(["--previous-entry", str(previous_entry)])
    if gate_config is not None:
        command.extend(["--gate-config", str(gate_config)])
    if no_append_history:
        command.append("--no-append-history")
    if skip_quality_tests:
        command.append("--skip-tests")
    if fail_on_gate:
        command.append("--fail-on-gate")
    else:
        command.append("--diagnostic-allow-gate-failure")
    return command


def run_observe_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    log: Callable[[str], None] | None = None,
) -> int:
    if log is not None:
        log("$ " + " ".join(str(part) for part in command))
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd or repository_root()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        start_new_session=os.name != "nt",
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        ),
    )
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if log is not None:
                log(line.rstrip("\r\n"))
        return int(process.wait())
    finally:
        if process.poll() is None:
            terminated = terminate_process_tree(process.pid)
            if not terminated:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


_WINDOWS_DEVICE_SUFFIXES = tuple(str(index) for index in range(1, 10)) + (
    "\u00b9",
    "\u00b2",
    "\u00b3",
)
_WINDOWS_RESERVED_NAMES = {"aux", "con", "nul", "prn"} | {
    f"{prefix}{suffix}"
    for prefix in ("com", "lpt")
    for suffix in _WINDOWS_DEVICE_SUFFIXES
}
_WINDOWS_FORBIDDEN_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*')


def _canonical_final_html_dir(path: Path) -> Path:
    lexical = Path(path).expanduser()
    if not lexical.is_absolute():
        raise ValueError(f"final_html_dir must be absolute and canonical: {lexical}")
    if any(part in {".", ".."} for part in lexical.parts):
        raise ValueError(f"final_html_dir must be canonical: {lexical}")
    if any(path_is_link_like(component) for component in (lexical, *lexical.parents)):
        raise ValueError(f"final_html_dir contains a link-like component: {lexical}")
    canonical = lexical.resolve(strict=False)
    if os.path.normcase(str(lexical)) != os.path.normcase(str(canonical)):
        raise ValueError(f"final_html_dir must be canonical: {lexical}")
    return canonical


def _final_html_filename(article: str) -> str:
    if not article or article != normalize("NFC", article):
        raise ValueError(f"Invalid final HTML article name: {article!r}")
    if (
        article in {".", ".."}
        or article.endswith((" ", "."))
        or any(ord(character) < 32 for character in article)
        or any(
            character in _WINDOWS_FORBIDDEN_FILENAME_CHARACTERS for character in article
        )
    ):
        raise ValueError(f"Invalid final HTML article name: {article!r}")
    if (
        article.split(".", maxsplit=1)[0].rstrip(" .").casefold()
        in _WINDOWS_RESERVED_NAMES
    ):
        raise ValueError(f"Invalid final HTML article name: {article!r}")
    filename = f"{article}.html"
    if len(filename.encode("utf-8")) > 240:
        raise ValueError(f"Invalid final HTML article name: {article!r}")
    return filename


def _require_owned_final_html_tree(
    path: Path,
    *,
    expected_target_dir: Path | None = None,
    allow_unsealed_legacy: bool = False,
) -> None:
    if not path.exists() and not path_is_link_like(path):
        return
    if path_is_link_like(path) or not path.is_dir():
        raise RuntimeError(
            f"Final HTML target is not an owned regular directory: {path}"
        )
    entries = list(path.iterdir())
    for entry in entries:
        if (
            path_is_link_like(entry)
            or not entry.is_file()
            or (
                entry.name != FINAL_HTML_MANIFEST_NAME
                and entry.suffix.casefold() != ".html"
            )
        ):
            raise RuntimeError(f"Final HTML target contains a foreign entry: {entry}")
    if not entries or allow_unsealed_legacy:
        return

    payload = _load_final_html_manifest(path / FINAL_HTML_MANIFEST_NAME)
    publication_id = payload.get("publication_id") if payload is not None else None
    expected_target = expected_target_dir or path
    if (
        not isinstance(publication_id, str)
        or len(publication_id) != 32
        or any(character not in "0123456789abcdef" for character in publication_id)
        or not _final_html_tree_matches_publication(
            path, publication_id, expected_target_dir=expected_target
        )
    ):
        raise RuntimeError(
            "Final HTML target is nonempty but lacks a valid ownership manifest: "
            f"{path}"
        )


def _require_exact_staging_tree(path: Path, expected_names: set[str]) -> None:
    if path_is_link_like(path) or not path.is_dir():
        raise RuntimeError(f"Final HTML staging tree is invalid: {path}")
    actual_names: set[str] = set()
    for entry in path.iterdir():
        entry_stat = entry.stat(follow_symlinks=False)
        if (
            path_is_link_like(entry)
            or not entry.is_file()
            or int(entry_stat.st_nlink) != 1
        ):
            raise RuntimeError(
                f"Final HTML staging tree contains an unsafe entry: {entry}"
            )
        actual_names.add(entry.name)
    if actual_names != expected_names:
        raise RuntimeError(
            "Final HTML staging tree does not match the complete expected tree: "
            f"expected={sorted(expected_names)!r} actual={sorted(actual_names)!r}"
        )


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_json_key:{key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"nonfinite_json_constant:{value}")


def _load_final_html_manifest(path: Path) -> dict[str, Any] | None:
    try:
        if path_is_link_like(path):
            return None
        before = path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or int(before.st_nlink) != 1
            or int(before.st_size) <= 0
            or int(before.st_size) > _MAX_FINAL_HTML_MANIFEST_BYTES
        ):
            return None
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            data = handle.read(_MAX_FINAL_HTML_MANIFEST_BYTES + 1)
            finished = os.fstat(handle.fileno())
        after = path.stat(follow_symlinks=False)

        def identity(value: os.stat_result) -> tuple[int, int, int, int]:
            return (
                int(value.st_dev),
                int(value.st_ino),
                int(value.st_size),
                int(value.st_mtime_ns),
            )

        if (
            len(data) > _MAX_FINAL_HTML_MANIFEST_BYTES
            or identity(before) != identity(opened)
            or identity(opened) != identity(finished)
            or identity(finished) != identity(after)
        ):
            return None
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _final_html_tree_matches_publication(
    path: Path,
    publication_id: str,
    *,
    expected_target_dir: Path | None = None,
) -> bool:
    try:
        payload = _load_final_html_manifest(path / FINAL_HTML_MANIFEST_NAME)
        if payload is None:
            return False
        target_dir = expected_target_dir or path
        expected_keys = {
            "schema_version",
            "publication_id",
            "quality_output_dir",
            "final_html_dir",
            "article_count",
            "html_files",
        }
        if set(payload) != expected_keys:
            return False
        records = payload.get("html_files")
        article_count = payload.get("article_count")
        if (
            type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 2
            or payload.get("publication_id") != publication_id
            or not isinstance(payload.get("quality_output_dir"), str)
            or payload.get("final_html_dir") != str(target_dir)
            or type(article_count) is not int
            or article_count < 0
            or not isinstance(records, list)
            or len(records) != article_count
        ):
            return False
        expected_names = {FINAL_HTML_MANIFEST_NAME}
        seen_article_keys: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or set(record) != {
                "article",
                "source_path",
                "final_path",
                "bytes",
                "sha256",
            }:
                return False
            article = record.get("article")
            source_path = record.get("source_path")
            source_candidate = (
                Path(source_path) if isinstance(source_path, str) else Path()
            )
            final_path = record.get("final_path")
            byte_count = record.get("bytes")
            sha256 = record.get("sha256")
            article_key = (
                normalize("NFC", article).casefold() if isinstance(article, str) else ""
            )
            if (
                not isinstance(article, str)
                or article_key in seen_article_keys
                or not isinstance(source_path, str)
                or not source_path
                or not source_candidate.is_absolute()
                or source_candidate.is_relative_to(target_dir)
                or not isinstance(final_path, str)
                or type(byte_count) is not int
                or byte_count <= 0
                or not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                return False
            expected_path = path / _final_html_filename(article)
            expected_final_path = target_dir / _final_html_filename(article)
            if Path(final_path) != expected_final_path:
                return False
            fingerprint = fingerprint_file(
                expected_path, reject_symlink=True, capture_edges=True
            )
            if (
                fingerprint is None
                or int(expected_path.stat(follow_symlinks=False).st_nlink) != 1
                or not artifact_is_structurally_valid(expected_path, fingerprint)
                or fingerprint.size != byte_count
                or fingerprint.sha256 != sha256
            ):
                return False
            seen_article_keys.add(article_key)
            expected_names.add(expected_path.name)
        _require_exact_staging_tree(path, expected_names)
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def _publish_final_html(
    *,
    quality_dir: Path,
    target_dir: Path,
    sources: Sequence[tuple[str, Path]],
    sealed_records_by_article: dict[str, dict[str, Any]] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    before_mutation: Callable[[], None] | None = None,
) -> FinalHtmlCollection:
    target_dir = _canonical_final_html_dir(target_dir)
    quality_dir = quality_dir.expanduser().resolve(strict=False)
    if quality_dir == target_dir or quality_dir.is_relative_to(target_dir):
        raise ValueError(
            f"final_html_dir must not equal or contain quality_output_dir: {target_dir}"
        )
    resolved_sources = [
        (
            article,
            source_path.resolve(strict=False),
            _final_html_filename(article),
        )
        for article, source_path in sources
    ]
    overlapping = [
        source_path
        for _article, source_path, _filename in resolved_sources
        if source_path.is_relative_to(target_dir)
    ]
    if overlapping:
        raise ValueError(f"final_html_dir contains source HTML: {overlapping[0]}")
    seen_articles: dict[str, Path] = {}
    artifacts: list[FinalHtmlArtifact] = []
    for article, source_path, filename in resolved_sources:
        article_key = normalize("NFC", article).casefold()
        previous = seen_articles.get(article_key)
        if previous is not None:
            raise RuntimeError(
                "Duplicate final HTML article name "
                f"{article!r}: {previous} and {source_path}."
            )
        seen_articles[article_key] = source_path
        artifacts.append(
            FinalHtmlArtifact(
                article=article,
                source_path=source_path.resolve(strict=False),
                final_path=target_dir / filename,
            )
        )
    if sealed_records_by_article is not None and set(sealed_records_by_article) != {
        artifact.article for artifact in artifacts
    }:
        raise RuntimeError(
            "Final HTML sealed record coverage does not match the article set"
        )

    allow_unsealed_legacy = target_dir == quality_dir / FINAL_HTML_DIR_NAME

    def validate_existing(path: Path) -> None:
        _require_owned_final_html_tree(
            path,
            expected_target_dir=target_dir,
            allow_unsealed_legacy=allow_unsealed_legacy,
        )

    validate_existing(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if _canonical_final_html_dir(target_dir) != target_dir:
        raise RuntimeError(
            f"Final HTML target changed while preparing publication: {target_dir}"
        )

    validate_existing(target_dir)
    expected_names = {artifact.final_path.name for artifact in artifacts} | {
        FINAL_HTML_MANIFEST_NAME
    }
    with CompleteDirectoryPublication(
        target_dir,
        validate_existing=validate_existing,
        validate_staging=lambda path: _require_exact_staging_tree(path, expected_names),
        committed_tree_matches=_final_html_tree_matches_publication,
        is_cancelled=is_cancelled,
        before_mutation=before_mutation,
    ) as transaction:
        manifest_records: list[dict[str, Any]] = []
        for artifact in artifacts:
            transaction.check_cancelled()
            staged_path = transaction.staging_dir / artifact.final_path.name
            if sealed_records_by_article is None:
                _copy_file_atomic(artifact.source_path, staged_path)
            else:
                stage_sealed_polish(
                    artifact.source_path,
                    staged_path,
                    sealed_records_by_article[artifact.article],
                    fingerprint_key="final_polish",
                )
            fingerprint = fingerprint_file(
                staged_path,
                reject_symlink=True,
                capture_edges=True,
            )
            if fingerprint is None or not artifact_is_structurally_valid(
                staged_path,
                fingerprint,
            ):
                raise RuntimeError(
                    f"Final HTML staging artifact is invalid: {staged_path}"
                )
            manifest_records.append(
                {
                    "article": artifact.article,
                    "source_path": str(artifact.source_path),
                    "final_path": str(artifact.final_path),
                    "bytes": fingerprint.size,
                    "sha256": fingerprint.sha256,
                }
            )
        transaction.check_cancelled()
        manifest: dict[str, Any] = {
            "schema_version": 2,
            "publication_id": transaction.transaction_id,
            "quality_output_dir": str(quality_dir),
            "final_html_dir": str(target_dir),
            "article_count": len(artifacts),
            "html_files": manifest_records,
        }
        manifest_path = transaction.staging_dir / FINAL_HTML_MANIFEST_NAME
        _write_json_atomic(manifest_path, manifest)
        if _canonical_final_html_dir(target_dir) != target_dir:
            raise RuntimeError(
                f"Final HTML target changed before publication: {target_dir}"
            )
        transaction.commit()

    return FinalHtmlCollection(
        final_html_dir=target_dir,
        manifest_path=target_dir / FINAL_HTML_MANIFEST_NAME,
        artifacts=tuple(artifacts),
    )


def collect_final_html(
    quality_output_dir: Path,
    *,
    final_html_dir: Path | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> FinalHtmlCollection:
    quality_dir = quality_output_dir.expanduser().resolve(strict=False)
    target_dir = (
        final_html_dir.expanduser()
        if final_html_dir is not None
        else quality_dir / FINAL_HTML_DIR_NAME
    )
    publication = validate_quality_publication(quality_dir)
    if not publication.valid:
        raise RuntimeError(
            "Final HTML collection requires a valid quality publication seal: "
            f"{publication.reason}"
        )
    sources: list[tuple[str, Path]] = []
    for article, record in sorted(publication.records_by_article.items()):
        if is_cancelled is not None and is_cancelled():
            raise RuntimeError("Final HTML collection cancelled before staging")
        final_record = record.get("final_polish")
        if not isinstance(final_record, dict):
            raise RuntimeError(f"Sealed article has no final polish record: {article}")
        source_value = final_record.get("path")
        if not isinstance(source_value, str) or not source_value:
            raise RuntimeError(f"Sealed article has no final polish path: {article}")
        sources.append((article, Path(source_value).resolve(strict=False)))

    def require_current_quality_publication() -> None:
        rechecked = validate_quality_publication(quality_dir)
        if (
            not rechecked.valid
            or rechecked.records_by_article != publication.records_by_article
        ):
            raise RuntimeError(
                "Quality publication changed during final HTML collection: "
                f"{rechecked.reason or 'article_records_changed'}"
            )

    return _publish_final_html(
        quality_dir=quality_dir,
        target_dir=target_dir,
        sources=sources,
        sealed_records_by_article=publication.records_by_article,
        is_cancelled=is_cancelled,
        before_mutation=require_current_quality_publication,
    )


def empty_final_html_collection(
    quality_output_dir: Path,
    *,
    final_html_dir: Path | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> FinalHtmlCollection:
    quality_dir = quality_output_dir.expanduser().resolve(strict=False)
    target_dir = (
        final_html_dir.expanduser()
        if final_html_dir is not None
        else quality_dir / FINAL_HTML_DIR_NAME
    )
    return _publish_final_html(
        quality_dir=quality_dir,
        target_dir=target_dir,
        sources=(),
        is_cancelled=is_cancelled,
    )


def existing_conversion_summary(options: PipelineOptions) -> PipelineSummary:
    converted_root = Path(options.output_dir).expanduser().resolve(strict=False)
    raw_stages = sorted(
        (
            path for path in converted_root.rglob(RAW_STAGE_NAME)
            if path.is_file()
        ),
        key=str,
    )
    if not raw_stages:
        raise FileNotFoundError(
            "Repolish-only mode requires an existing 01.en.raw.html under "
            f"{converted_root}."
        )
    source_pdf_paths = [Path(path) for path in options.source_pdf_paths or []]
    validations = require_current_raw_conversions(
        raw_stages,
        source_pdf_paths=source_pdf_paths,
    )
    source_pdf_count = len(source_pdf_paths)
    article_count = len({article_dir_from_html_stage(path) for path in raw_stages})
    assert article_count == len(validations)
    return PipelineSummary(
        collection_key="direct_pdf",
        collection_name="existing PDF HTML conversions",
        attachments_total=max(source_pdf_count, article_count),
        pdfs_resolved=source_pdf_count,
        staged_total=0,
        converted_total=article_count,
        skipped_existing=0,
        failed_total=0,
        output_dir=converted_root,
        filename_map_path=converted_root / "_source_filename_map.csv",
        export_mode=options.export_mode,
    )


def run_clean_pipeline(
    options: CleanPipelineOptions,
    runner: MarkerRunner,
    log: Callable[[str], None],
    is_cancelled: Callable[[], bool],
    *,
    pipeline_runner: Callable[
        [PipelineOptions, MarkerRunner, Callable[[str], None], Callable[[], bool]],
        PipelineSummary,
    ] = run_pipeline,
    observe_runner: Callable[[Sequence[str], Path | None, Callable[[str], None] | None], int]
    | None = None,
) -> CleanPipelineSummary:
    if options.reuse_existing_conversion:
        conversion_summary = existing_conversion_summary(options.conversion_options)
        log(
            "Reusing existing PDF HTML raw stages for repolish: "
            f"articles={conversion_summary.converted_total} output={conversion_summary.output_dir}"
        )
    else:
        conversion_summary = pipeline_runner(
            options.conversion_options,
            runner,
            log,
            is_cancelled,
        )
    if conversion_summary.failed_total:
        raise RuntimeError(
            "PDF conversion failed; quality observe was skipped "
            f"(failed={conversion_summary.failed_total})."
        )
    if not options.reuse_existing_conversion and (
        conversion_summary.converted_total or conversion_summary.skipped_existing
    ):
        validated_summary = existing_conversion_summary(options.conversion_options)
        expected_current = conversion_summary.converted_total + conversion_summary.skipped_existing
        if validated_summary.converted_total != expected_current:
            raise RuntimeError(
                "Converted raw-stage count does not match the completed conversion summary "
                f"(validated={validated_summary.converted_total}, "
                f"expected_current={expected_current})."
            )

    converted_root = Path(options.conversion_options.output_dir).expanduser().resolve(strict=False)
    quality_output_dir = (
        Path(options.quality_output_dir).expanduser().resolve(strict=False)
        if options.quality_output_dir
        else default_quality_output_dir(converted_root)
    )
    if quality_output_dir == converted_root:
        raise ValueError("quality_output_dir must be different from the conversion output_dir.")

    if (
        not conversion_summary.converted_total
        and not conversion_summary.skipped_existing
    ):
        final_html = empty_final_html_collection(
            quality_output_dir,
            final_html_dir=(
                Path(options.final_html_dir).expanduser()
                if options.final_html_dir
                else None
            ),
            is_cancelled=is_cancelled,
        )
        return CleanPipelineSummary(
            conversion_summary=conversion_summary,
            quality_output_dir=quality_output_dir,
            run_id=options.run_id or default_run_id(quality_output_dir),
            observe_command=(),
            observe_exit_code=0,
            converted_stage_publish_report=None,
            final_html=final_html,
        )

    run_id = options.run_id or default_run_id(quality_output_dir)
    observe_command = build_observe_command(
        converted_root=converted_root,
        quality_output_dir=quality_output_dir,
        run_id=run_id,
        jobs=options.jobs,
        repolish_jobs=options.repolish_jobs,
        audit_jobs=options.audit_jobs,
        p62_marker_recovery_jobs=options.p62_marker_recovery_jobs,
        p62_recovery_jobs=options.p62_recovery_jobs,
        polish_auto_repair_jobs=options.polish_auto_repair_jobs,
        previous_entry=(
            Path(options.previous_entry).expanduser().resolve(strict=False)
            if options.previous_entry
            else None
        ),
        gate_config=(
            Path(options.gate_config).expanduser().resolve(strict=False)
            if options.gate_config
            else None
        ),
        no_append_history=options.no_append_history,
        skip_quality_tests=options.skip_quality_tests,
        fail_on_gate=options.fail_on_gate,
    )

    active_observe_runner = observe_runner
    if active_observe_runner is None:
        def active_observe_runner(
            command: Sequence[str],
            cwd: Path | None,
            log_func: Callable[[str], None] | None,
        ) -> int:
            return run_observe_command(
                command,
                cwd=cwd,
                log=log_func,
            )

    observe_exit_code = active_observe_runner(observe_command, repository_root(), log)
    if observe_exit_code != 0:
        raise RuntimeError(f"Quality observe failed with exit code {observe_exit_code}.")

    converted_stage_publish_report: dict[str, Any] | None = None
    if options.publish_latest_to_converted:
        converted_stage_publish_report = publish_latest_polish_from_quality_run(
            quality_output_dir,
            converted_roots=[converted_root],
            apply=True,
            prune_extra_html=options.prune_extra_html,
            out_report=(
                Path(options.publish_report_path).expanduser().resolve(strict=False)
                if options.publish_report_path
                else None
            ),
        )
        if converted_stage_publish_report.get("stage_contract_status") != "pass":
            raise RuntimeError(
                "Converted stage HTML contract failed after publishing latest polish "
                f"(failing={converted_stage_publish_report.get('stage_contract_failing_article_count')})."
            )

    final_html = collect_final_html(
        quality_output_dir,
        final_html_dir=(
            Path(options.final_html_dir).expanduser()
            if options.final_html_dir
            else None
        ),
        is_cancelled=is_cancelled,
    )
    write_pipeline_manifest(converted_root)

    return CleanPipelineSummary(
        conversion_summary=conversion_summary,
        quality_output_dir=quality_output_dir,
        run_id=run_id,
        observe_command=tuple(observe_command),
        observe_exit_code=observe_exit_code,
        converted_stage_publish_report=converted_stage_publish_report,
        final_html=final_html,
    )
