from __future__ import annotations

import concurrent.futures
import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .citation_profile import build_citation_profile_from_pdf
from .export_modes import ExportMode, get_export_mode_spec
from .history import append_history
from .html_stages import POLISH_STAGE_NAME, RAW_STAGE_NAME, html_stage_dir_for_html, save_html_stage
from .llm_bundle import LlmBundleResult, create_llm_bundle
from .marker_runner import MarkerRunner
from .models import PipelineSummary, StagedFile
from .ocr_quality import assess_ocr_quality_from_html, enqueue_reocr_candidate, load_reocr_queue
from .output_state import detect_existing_results, normalize_source_path
from .paths import resolve_zotero_data_dir
from .pipeline_discovery import discover_collection_pdfs, discover_source_pdfs
from .pipeline_options import PdfDiscoveryResult, PipelineOptions
from .pipeline_webdav import (
    resolve_webdav_config_path,
    retry_pending_webdav_exports,
    upload_webdav_mirror_if_configured,
)
from .pipeline_zotero import retry_pending_zotero_exports, zotero_write_lock_detected as detect_zotero_write_lock
from .runtime_temp import cleanup_runtime_temp_root, runtime_temp_root
from .single_file_html import (
    close_katex_v8_context,
    polish_and_inline_html_file,
)
from .staging import (
    FILENAME_MAP_NAME,
    cleanup_staging_dir,
    expected_output_artifact_path,
    stage_resolved_pdfs,
    write_filename_map,
)
from .text_cleanup import drop_repeated_phrases
from .webdav_pending import WebDavUploadSummary
from .zotero_html_attachment import attach_single_file_html
from .zotero_pending import (
    build_pending_entry,
    enqueue_pending_attachments,
    load_pending_attachments,
)


OVERLAY_SUFFIX_RE = re.compile(r"_([0-9a-f]{8})(?:\.pdf)?$", re.IGNORECASE)


@dataclass(frozen=True)
class _HtmlPolishWorkItem:
    staged_file: StagedFile
    html_path: Path
    stage_dir: Path
    raw_stage_path: Path
    citation_profile: Any


@dataclass(frozen=True)
class _HtmlPolishResult:
    html_path: Path
    stage_dir: Path
    raw_stage_path: Path
    polish_stage_path: Path | None
    inlined_images: int
    elapsed_s: float
    error: str | None = None


def _log_elapsed(log: Callable[[str], None] | None, stage: str, started_at: float) -> None:
    if log is None:
        return
    log(f"[timer] {stage}: {perf_counter() - started_at:.2f}s")


def _polish_html_work_item(item: _HtmlPolishWorkItem) -> _HtmlPolishResult:
    started_at = perf_counter()
    try:
        result = polish_and_inline_html_file(
            item.html_path,
            citation_profile=item.citation_profile,
        )
        item.html_path.write_text(result.html, encoding="utf-8")
        elapsed_s = perf_counter() - started_at
        polish_stage = save_html_stage(
            item.stage_dir,
            POLISH_STAGE_NAME,
            result.html,
            "en.polish.inline_images",
            source_path=item.html_path,
            details=(
                f"inlined_images={result.inlined_images}",
                f"elapsed_s={elapsed_s:.2f}",
            ),
        )
        return _HtmlPolishResult(
            html_path=item.html_path,
            stage_dir=item.stage_dir,
            raw_stage_path=item.raw_stage_path,
            polish_stage_path=polish_stage.path,
            inlined_images=result.inlined_images,
            elapsed_s=elapsed_s,
        )
    except Exception as exc:
        return _HtmlPolishResult(
            html_path=item.html_path,
            stage_dir=item.stage_dir,
            raw_stage_path=item.raw_stage_path,
            polish_stage_path=None,
            inlined_images=0,
            elapsed_s=perf_counter() - started_at,
            error=str(exc),
        )


def _polish_html_work_items(
    work_items: list[_HtmlPolishWorkItem],
    *,
    max_workers: int,
) -> list[_HtmlPolishResult]:
    if not work_items:
        return []
    worker_count = min(max(1, int(max_workers or 1)), len(work_items))
    if worker_count == 1:
        return [_polish_html_work_item(item) for item in work_items]
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(_polish_html_work_item, work_items))


def _webdav_upload_mirror_if_configured(
    file_path: Path,
    output_dir: Path,
    options: PipelineOptions,
    log: Callable[[str], None] | None,
) -> WebDavUploadSummary:
    return upload_webdav_mirror_if_configured(
        file_path=file_path,
        output_dir=output_dir,
        upload_enabled=options.webdav_upload_enabled,
        webdav_config_path=options.webdav_config_path,
        log=log,
    )


def _build_env(options: PipelineOptions) -> dict[str, str]:
    env = os.environ.copy()
    if options.use_cuda:
        env["TORCH_DEVICE"] = "cuda"
        if options.cuda_device_index is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(options.cuda_device_index)

    if options.model_cache_dir:
        cache_dir = Path(options.model_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        env["MODEL_CACHE_DIR"] = str(cache_dir)

    return env


def _clean_md_repeated_phrases(md_path: Path, log: Callable[[str], None]) -> None:
    """Read an MD file, remove repeated-phrase hallucinations, write back if changed."""
    try:
        original = md_path.read_text(encoding="utf-8", errors="replace")
        cleaned = drop_repeated_phrases(original)
        if cleaned != original:
            md_path.write_text(cleaned, encoding="utf-8")
            log(f"Repetitions removed: {md_path.name} (-{len(original) - len(cleaned)} chars)")
    except Exception as exc:
        log(f"Warning: repetition cleanup failed for {md_path.name}: {exc}")


def _artifact_signature(path: Path) -> tuple[bool, int, int]:
    try:
        stat = path.stat()
    except OSError:
        return False, 0, 0
    return True, int(stat.st_size), int(stat.st_mtime_ns)


def _alias_suffix(value: str) -> str:
    match = OVERLAY_SUFFIX_RE.search(value)
    return match.group(1).lower() if match else ""


def _find_zotero_overlay_path(
    overlay_dir: Path | None,
    source_pdf_path: Path,
    alias_base_name: str | None,
) -> Path | None:
    if overlay_dir is None or not overlay_dir.is_dir():
        return None

    source_stem = source_pdf_path.stem
    alias_stem = alias_base_name or ""
    suffix = _alias_suffix(alias_stem) or _alias_suffix(source_stem)
    candidates = [
        overlay_dir / f"{source_stem}.overlays.json",
    ]
    if alias_stem:
        candidates.append(overlay_dir / f"{alias_stem}.overlays.json")
    if suffix:
        candidates.append(overlay_dir / f"{suffix}.overlays.json")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate

    if suffix:
        matches = sorted(overlay_dir.glob(f"*{glob.escape(suffix)}*.overlays.json"), key=str)
        if matches:
            return matches[0]

    source_prefix = source_stem[:48]
    if source_prefix:
        matches = sorted(
            overlay_dir.glob(f"*{glob.escape(source_prefix)}*.overlays.json"),
            key=str,
        )
        if matches:
            return matches[0]
    return None


def _empty_pipeline_summary(
    *,
    discovery: PdfDiscoveryResult,
    output_dir: Path,
    export_mode: str,
    skipped_existing: int = 0,
) -> PipelineSummary:
    return PipelineSummary(
        collection_key=discovery.collection_key,
        collection_name=discovery.collection_name,
        attachments_total=discovery.attachments_total,
        pdfs_resolved=len(discovery.candidates),
        staged_total=0,
        converted_total=0,
        skipped_existing=skipped_existing,
        failed_total=0,
        output_dir=output_dir,
        filename_map_path=output_dir / FILENAME_MAP_NAME,
        export_mode=export_mode,
    )


def run_raw_html_pipeline(
    options: PipelineOptions,
    runner: MarkerRunner,
    log: Callable[[str], None],
    is_cancelled: Callable[[], bool],
) -> PipelineSummary:
    """Convert direct PDFs to raw Marker HTML stages without polish or quality observe."""
    pipeline_started_at = perf_counter()
    output_dir = Path(options.output_dir).expanduser().resolve()
    runtime_tmp_root = runtime_temp_root(output_dir)
    stage = None

    if not options.source_pdf_paths:
        raise ValueError("Raw-only HTML conversion requires direct --pdf inputs.")

    try:
        started_at = perf_counter()
        output_dir.mkdir(parents=True, exist_ok=True)
        _log_elapsed(log, "raw_pipeline.prepare_output_dir", started_at)

        started_at = perf_counter()
        discovery = discover_source_pdfs(
            source_pdf_paths=options.source_pdf_paths or [],
            output_dir=options.output_dir,
            artifact_extension=".html",
            log=log,
        )
        _log_elapsed(log, "raw_pipeline.discover_source_pdfs", started_at)
        log(f"Selected PDF input: {discovery.collection_name}")
        log(f"PDF files in raw-only scope: {discovery.attachments_total}")

        resolved = [c.resolved_attachment for c in discovery.candidates]
        if not resolved:
            log("No local PDF files found. Nothing to process.")
            return _empty_pipeline_summary(
                discovery=discovery,
                output_dir=output_dir,
                export_mode=options.export_mode,
            )

        skipped_existing = 0
        started_at = perf_counter()
        existing_in_output = detect_existing_results(
            output_dir,
            [r.source_pdf_path for r in resolved],
            artifact_extension=".html",
        )
        _log_elapsed(log, "raw_pipeline.detect_existing_results", started_at)
        if options.skip_existing:
            before = len(resolved)
            resolved = [
                item for item in resolved
                if normalize_source_path(item.source_pdf_path) not in existing_in_output
            ]
            skipped_existing = before - len(resolved)
            if skipped_existing:
                log(f"Already present in output folder, skipped before raw-only run: {skipped_existing}")

        if not resolved:
            return _empty_pipeline_summary(
                discovery=discovery,
                output_dir=output_dir,
                export_mode=options.export_mode,
                skipped_existing=skipped_existing,
            )

        if is_cancelled():
            raise RuntimeError("Cancelled before raw-only staging.")

        started_at = perf_counter()
        stage = stage_resolved_pdfs(resolved, output_dir, options.max_base_len, temp_root=runtime_tmp_root)
        _log_elapsed(log, "raw_pipeline.stage_resolved_pdfs", started_at)

        started_at = perf_counter()
        filename_map_path = write_filename_map(output_dir, stage.staged_files)
        _log_elapsed(log, "raw_pipeline.write_filename_map", started_at)
        log(f"Filename map: {filename_map_path}")

        started_at = perf_counter()
        env = _build_env(options)
        _log_elapsed(log, "raw_pipeline.build_env", started_at)
        if env.get("MODEL_CACHE_DIR"):
            log(f"MODEL_CACHE_DIR={env['MODEL_CACHE_DIR']}")
        if env.get("TORCH_DEVICE"):
            log(f"TORCH_DEVICE={env['TORCH_DEVICE']}")
        if env.get("CUDA_VISIBLE_DEVICES"):
            log(f"CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']}")

        if is_cancelled():
            raise RuntimeError("Cancelled before raw-only conversion.")

        batch_skip_existing = options.skip_existing and options.skip_existing_source_pdf_paths is None
        artifact_before = {
            staged_file.alias_base_name: _artifact_signature(
                expected_output_artifact_path(output_dir, staged_file.alias_base_name, ".html")
            )
            for staged_file in stage.staged_files
        }

        started_at = perf_counter()
        batch_result = runner.run_batch(
            input_dir=stage.staging_dir,
            output_dir=output_dir,
            skip_existing=batch_skip_existing,
            disable_multiprocessing=options.disable_batch_multiprocessing,
            output_format="html",
            env=env,
            log=log,
        )
        _log_elapsed(log, "raw_pipeline.marker_batch", started_at)
        log(f"marker batch exit_code={batch_result.exit_code}")

        pending = []
        converted_total = 0
        for staged_file in stage.staged_files:
            artifact_path = expected_output_artifact_path(output_dir, staged_file.alias_base_name, ".html")
            exists_now, _, _ = _artifact_signature(artifact_path)
            if exists_now:
                before_sig = artifact_before.get(staged_file.alias_base_name, (False, 0, 0))
                if (
                    before_sig[0]
                    and not batch_skip_existing
                    and _artifact_signature(artifact_path) == before_sig
                ):
                    pending.append(staged_file)
                    continue
                converted_total += 1
                continue
            pending.append(staged_file)

        if pending:
            log(f"Raw-only fallback conversion for missing outputs: {len(pending)}")
        for staged_file in pending:
            if is_cancelled():
                raise RuntimeError("Cancelled during raw-only fallback conversion.")
            single_result = runner.run_single(
                pdf_path=staged_file.alias_pdf_path,
                output_dir=output_dir,
                output_format="html",
                env=env,
                log=log,
            )
            artifact_path = expected_output_artifact_path(output_dir, staged_file.alias_base_name, ".html")
            if single_result.exit_code == 0 and artifact_path.exists():
                converted_total += 1

        converted_source_paths: list[Path] = []
        for staged_file in stage.staged_files:
            html_path = expected_output_artifact_path(output_dir, staged_file.alias_base_name, ".html")
            if not html_path.is_file():
                continue
            converted_source_paths.append(staged_file.source_pdf_path)
            raw_html = html_path.read_text(encoding="utf-8", errors="replace")
            raw_stage = save_html_stage(
                html_stage_dir_for_html(html_path),
                RAW_STAGE_NAME,
                raw_html,
                "en.raw.marker",
                source_path=html_path,
                details=(
                    "raw_only=true",
                    f"source_pdf={staged_file.source_pdf_path.name}",
                ),
            )
            log(f"Raw HTML stage saved: {raw_stage.path}")

        marker_failed_total = len(stage.staged_files) - len(converted_source_paths)
        return PipelineSummary(
            collection_key=discovery.collection_key,
            collection_name=discovery.collection_name,
            attachments_total=discovery.attachments_total,
            pdfs_resolved=len(discovery.candidates),
            staged_total=len(stage.staged_files),
            converted_total=converted_total,
            skipped_existing=skipped_existing,
            failed_total=marker_failed_total,
            output_dir=output_dir,
            filename_map_path=filename_map_path,
            export_mode=options.export_mode,
        )
    finally:
        if stage is not None:
            cleanup_staging_dir(stage.staging_dir)
            log("Staging folder cleaned up.")
        close_katex_v8_context()
        cleanup_runtime_temp_root(runtime_tmp_root)
        log(f"Runtime temp cleaned: {runtime_tmp_root}")
        _log_elapsed(log, "raw_pipeline.total", pipeline_started_at)


def run_pipeline(
    options: PipelineOptions,
    runner: MarkerRunner,
    log: Callable[[str], None],
    is_cancelled: Callable[[], bool],
) -> PipelineSummary:
    pipeline_started_at = perf_counter()
    output_dir = Path(options.output_dir).expanduser().resolve()
    runtime_tmp_root = runtime_temp_root(output_dir)
    zotero_overlay_dir = (
        Path(options.zotero_overlay_dir).expanduser().resolve(strict=False)
        if options.zotero_overlay_dir
        else None
    )

    # Support comma-separated multi-mode (e.g. "classic,llm_bundle").
    # All modes in one pipeline call must share the same marker_output_format.
    export_modes_list = options.export_modes_list
    primary_spec = get_export_mode_spec(export_modes_list[0])
    artifact_extension = primary_spec.artifact_extension
    marker_output_format = primary_spec.marker_output_format
    direct_pdf_mode = bool(options.source_pdf_paths)
    if direct_pdf_mode and ExportMode.ZOTERO in export_modes_list:
        raise ValueError(
            "Direct PDF conversion cannot use Zotero export mode. "
            "Use export_mode=html and let the caller handle write-back."
        )
    if not direct_pdf_mode and (not options.zotero_data_dir or not options.collection_key):
        raise ValueError(
            "Either source_pdf_paths or both zotero_data_dir and collection_key must be provided."
        )

    zotero_dir_for_mode: Path | None = None
    zotero_write_lock_detected = False

    try:
        started_at = perf_counter()
        output_dir.mkdir(parents=True, exist_ok=True)
        _log_elapsed(log, "pipeline.prepare_output_dir", started_at)

        started_at = perf_counter()
        if direct_pdf_mode:
            discovery = discover_source_pdfs(
                source_pdf_paths=options.source_pdf_paths or [],
                output_dir=options.output_dir,
                artifact_extension=artifact_extension,
                log=log,
            )
            _log_elapsed(log, "pipeline.discover_source_pdfs", started_at)
            log(f"Selected PDF input: {discovery.collection_name}")
            log(f"PDF files in scope: {discovery.attachments_total}")
        else:
            discovery = discover_collection_pdfs(
                zotero_data_dir=options.zotero_data_dir,
                collection_key=options.collection_key,
                include_subcollections=options.include_subcollections,
                output_dir=options.output_dir,
                artifact_extension=artifact_extension,
                temp_root=runtime_tmp_root,
                log=log,
            )
            _log_elapsed(log, "pipeline.discover_collection_pdfs", started_at)
            log(f"Selected collection: {discovery.collection_name} ({discovery.collection_key})")
            log(f"Attachment records in scope: {discovery.attachments_total}")
        log(f"Resolved PDF attachments: {len(discovery.candidates)}")
        log(f"Export mode: {options.export_mode}")
        if discovery.unresolved_total:
            log(f"Skipped/unresolved attachments: {discovery.unresolved_total}")

        resolved = [c.resolved_attachment for c in discovery.candidates]
        if not resolved:
            log("No local PDF files found. Nothing to process.")
            return _empty_pipeline_summary(
                discovery=discovery,
                output_dir=output_dir,
                export_mode=options.export_mode,
            )

        if options.selected_source_pdf_paths and not direct_pdf_mode:
            started_at = perf_counter()
            selected_norm = {
                normalize_source_path(Path(path))
                for path in options.selected_source_pdf_paths
            }
            available_norm = {
                normalize_source_path(item.source_pdf_path)
                for item in resolved
            }
            skipped_without_pdf = selected_norm - available_norm
            if skipped_without_pdf:
                log(
                    "Selected entries without local PDF were skipped: "
                    f"{len(skipped_without_pdf)}"
                )
            before = len(resolved)
            selected_resolved = [
                item for item in resolved
                if normalize_source_path(item.source_pdf_path) in selected_norm
            ]
            if selected_resolved:
                resolved = selected_resolved
            else:
                log(
                    "Selection did not include local PDFs. "
                    "Processing all resolved PDFs from the collection."
                )
            _log_elapsed(log, "pipeline.apply_gui_selection_filter", started_at)
            log(f"Selected in GUI: {len(resolved)} of {before}")

        if not resolved:
            log("No PDFs selected for processing. Nothing to do.")
            return _empty_pipeline_summary(
                discovery=discovery,
                output_dir=output_dir,
                export_mode=options.export_mode,
            )

        skipped_existing = 0
        started_at = perf_counter()
        existing_in_output = detect_existing_results(
            output_dir,
            [r.source_pdf_path for r in resolved],
            artifact_extension=artifact_extension,
        )
        _log_elapsed(log, "pipeline.detect_existing_results", started_at)

        skip_existing_set: set[str] = set()
        if options.skip_existing_source_pdf_paths is not None:
            skip_existing_set = {
                normalize_source_path(Path(path))
                for path in options.skip_existing_source_pdf_paths
            }
            skip_existing_set &= existing_in_output
        elif options.skip_existing:
            skip_existing_set = set(existing_in_output)

        if skip_existing_set:
            started_at = perf_counter()
            before = len(resolved)
            resolved = [
                item for item in resolved
                if normalize_source_path(item.source_pdf_path) not in skip_existing_set
            ]
            skipped_existing = before - len(resolved)
            _log_elapsed(log, "pipeline.apply_skip_existing", started_at)
            if skipped_existing:
                log(f"Already present in output folder, skipped before run: {skipped_existing}")

        if not resolved:
            return _empty_pipeline_summary(
                discovery=discovery,
                output_dir=output_dir,
                export_mode=options.export_mode,
                skipped_existing=skipped_existing,
            )

        citation_profile_by_source: dict[str, object] = {}

        def citation_profile_for(source_pdf_path: Path, alias_base_name: str | None = None) -> object:
            source_norm = normalize_source_path(source_pdf_path)
            cached = citation_profile_by_source.get(source_norm)
            if cached is not None:
                return cached
            started_profile_at = perf_counter()
            zotero_overlay_path = _find_zotero_overlay_path(
                zotero_overlay_dir,
                source_pdf_path,
                alias_base_name,
            )
            if zotero_overlay_path is not None:
                log(
                    "Zotero overlay selected: "
                    f"{source_pdf_path.name}: {zotero_overlay_path}"
                )
            profile = build_citation_profile_from_pdf(
                source_pdf_path,
                zotero_overlay_path=zotero_overlay_path,
                require_zotero_overlay=options.require_zotero_overlay,
            )
            citation_profile_by_source[source_norm] = profile
            status = getattr(profile, "zotero_overlay_status", "")
            count = getattr(profile, "zotero_citation_count", 0)
            error = getattr(profile, "zotero_overlay_error", "")
            log(
                "Citation profile built: "
                f"{source_pdf_path.name} "
                f"(style={getattr(profile, 'style', 'unknown')}, "
                f"confidence={getattr(profile, 'confidence', 'low')}, "
                f"zotero_overlay={status or 'unknown'}, "
                f"zotero_citations={count})"
            )
            if error:
                log(f"Zotero overlay note: {source_pdf_path.name}: {error}")
            _log_elapsed(log, "pipeline.citation_profile", started_profile_at)
            return profile

        if ExportMode.ZOTERO in export_modes_list:
            started_at = perf_counter()
            zotero_dir_for_mode = resolve_zotero_data_dir(options.zotero_data_dir)
            if detect_zotero_write_lock(zotero_dir_for_mode):
                zotero_write_lock_detected = True
                log(
                    "Zotero write lock detected before conversion. "
                    "HTML results will be queued in output pending file for retry."
                )
            _log_elapsed(log, "pipeline.zotero_preflight_write_access", started_at)

        if is_cancelled():
            raise RuntimeError("Cancelled before staging.")

        started_at = perf_counter()
        stage = stage_resolved_pdfs(resolved, output_dir, options.max_base_len, temp_root=runtime_tmp_root)
        _log_elapsed(log, "pipeline.stage_resolved_pdfs", started_at)
        log(
            "Staging prepared: "
            f"requested_max={stage.requested_max_base_len}, "
            f"max_by_output_path={stage.max_base_len_by_output_path}, "
            f"effective_max={stage.effective_max_base_len}, "
            f"files={len(stage.staged_files)}"
        )

        started_at = perf_counter()
        filename_map_path = write_filename_map(output_dir, stage.staged_files)
        _log_elapsed(log, "pipeline.write_filename_map", started_at)
        log(f"Filename map: {filename_map_path}")

        started_at = perf_counter()
        env = _build_env(options)
        _log_elapsed(log, "pipeline.build_env", started_at)
        if env.get("MODEL_CACHE_DIR"):
            log(f"MODEL_CACHE_DIR={env['MODEL_CACHE_DIR']}")
        if env.get("TORCH_DEVICE"):
            log(f"TORCH_DEVICE={env['TORCH_DEVICE']}")
        if env.get("CUDA_VISIBLE_DEVICES"):
            log(f"CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']}")
        log(
            "Pipeline mode details: "
            f"modes={', '.join(m.value for m in export_modes_list)}, "
            f"marker_output_format={marker_output_format}, "
            f"artifact_extension={artifact_extension}"
        )
        if options.webdav_upload_enabled:
            log(f"WebDAV mirror: enabled (config={resolve_webdav_config_path(options.webdav_config_path)})")
            if marker_output_format != "html":
                log("WebDAV mirror: current output group is not HTML; upload skipped.")

        staged_source_bytes = 0
        for staged_file in stage.staged_files:
            try:
                staged_source_bytes += staged_file.source_pdf_path.stat().st_size
            except OSError:
                pass
        hardlinks = sum(1 for sf in stage.staged_files if sf.materialization == "hardlink")
        copies = sum(1 for sf in stage.staged_files if sf.materialization == "copy")
        shortened = sum(1 for sf in stage.staged_files if sf.was_shortened)
        log(
            "Staging details: "
            f"total_source_size_mb={staged_source_bytes / (1024 * 1024):.2f}, "
            f"hardlinks={hardlinks}, copies={copies}, shortened_aliases={shortened}"
        )

        converted_total = 0

        try:
            if is_cancelled():
                raise RuntimeError("Cancelled before conversion.")

            # If skip logic was already resolved per-file in GUI, don't pass --skip_existing
            # to marker, or it will skip files that user explicitly chose to reprocess.
            batch_skip_existing = options.skip_existing and options.skip_existing_source_pdf_paths is None
            log(
                "Marker run config: "
                f"files={len(stage.staged_files)}, "
                f"skip_existing_for_batch={batch_skip_existing}, "
                f"disable_batch_multiprocessing={options.disable_batch_multiprocessing}"
            )
            conversion_started_at = perf_counter()
            artifact_before = {
                staged_file.alias_base_name: _artifact_signature(
                    expected_output_artifact_path(
                        output_dir, staged_file.alias_base_name, artifact_extension
                    )
                )
                for staged_file in stage.staged_files
            }

            started_at = perf_counter()
            batch_result = runner.run_batch(
                input_dir=stage.staging_dir,
                output_dir=output_dir,
                skip_existing=batch_skip_existing,
                disable_multiprocessing=options.disable_batch_multiprocessing,
                output_format=marker_output_format,
                env=env,
                log=log,
            )
            _log_elapsed(log, "pipeline.marker_batch", started_at)
            log(f"marker batch exit_code={batch_result.exit_code}")

            started_at = perf_counter()
            pending = []
            unchanged_existing = 0
            for staged_file in stage.staged_files:
                artifact_path = expected_output_artifact_path(output_dir, staged_file.alias_base_name, artifact_extension)
                exists_now, _, _ = _artifact_signature(artifact_path)
                if exists_now:
                    before_sig = artifact_before.get(staged_file.alias_base_name, (False, 0, 0))
                    if (
                        before_sig[0]
                        and not batch_skip_existing
                        and _artifact_signature(artifact_path) == before_sig
                    ):
                        unchanged_existing += 1
                        pending.append(staged_file)
                        continue
                    converted_total += 1
                    continue
                pending.append(staged_file)
            _log_elapsed(log, "pipeline.detect_missing_after_batch", started_at)
            log(
                "Batch output check: "
                f"converted_after_batch={converted_total}, "
                f"missing_after_batch={len(pending)}, "
                f"unchanged_existing_after_batch={unchanged_existing}"
            )

            if pending:
                log(f"Fallback conversion for missing outputs: {len(pending)}")

            fallback_started_at = perf_counter()
            for staged_file in pending:
                if is_cancelled():
                    raise RuntimeError("Cancelled during fallback conversion.")

                single_started_at = perf_counter()
                single_result = runner.run_single(
                    pdf_path=staged_file.alias_pdf_path,
                    output_dir=output_dir,
                    output_format=marker_output_format,
                    env=env,
                    log=log,
                )
                _log_elapsed(log, f"pipeline.marker_single.{staged_file.alias_pdf_path.name}", single_started_at)
                artifact_path = expected_output_artifact_path(output_dir, staged_file.alias_base_name, artifact_extension)
                if single_result.exit_code == 0 and artifact_path.exists():
                    converted_total += 1
            if pending:
                _log_elapsed(log, "pipeline.fallback_total", fallback_started_at)
            _log_elapsed(log, "pipeline.conversion_total", conversion_started_at)

            started_at = perf_counter()
            converted_staged_files = []
            converted_source_paths: list[Path] = []
            for staged_file in stage.staged_files:
                artifact_path = expected_output_artifact_path(output_dir, staged_file.alias_base_name, artifact_extension)
                if not artifact_path.exists():
                    continue
                before_sig = artifact_before.get(staged_file.alias_base_name, (False, 0, 0))
                if (
                    before_sig[0]
                    and not batch_skip_existing
                    and _artifact_signature(artifact_path) == before_sig
                ):
                    log(
                        "Artifact unchanged after conversion attempts, treated as failed: "
                        f"{artifact_path.name}"
                    )
                    continue
                if artifact_path.exists():
                    converted_staged_files.append(staged_file)
                    converted_source_paths.append(staged_file.source_pdf_path)
            _log_elapsed(log, "pipeline.collect_converted_results", started_at)

            llm_bundle_result: LlmBundleResult | None = None
            zotero_html_attached_total = 0
            zotero_html_failed_total = 0
            zotero_html_queued_total = 0
            zotero_pending_total = 0
            webdav_uploaded_total = 0
            webdav_failed_total = 0
            webdav_queued_total = 0
            webdav_pending_total = 0
            ocr_quality_failed_total = 0
            reocr_queued_total = 0
            reocr_pending_total = len(load_reocr_queue(output_dir))
            history_paths = list(converted_source_paths)

            def mirror_webdav_html(html_path: Path) -> None:
                nonlocal webdav_uploaded_total, webdav_failed_total
                nonlocal webdav_queued_total, webdav_pending_total
                result = _webdav_upload_mirror_if_configured(
                    html_path,
                    output_dir,
                    options,
                    log,
                )
                webdav_uploaded_total += result.uploaded
                webdav_failed_total += result.failed
                webdav_queued_total += result.queued
                webdav_pending_total = result.pending_total

            # Level 3: clean repetition hallucinations from markdown outputs.
            if marker_output_format == "markdown" and converted_staged_files:
                started_at = perf_counter()
                for staged_file in converted_staged_files:
                    md_path = expected_output_artifact_path(
                        output_dir, staged_file.alias_base_name, ".md"
                    )
                    if md_path.is_file():
                        _clean_md_repeated_phrases(md_path, log)
                _log_elapsed(log, "pipeline.clean_md_repetitions", started_at)

            if converted_source_paths and ExportMode.LLM in export_modes_list:
                started_at = perf_counter()
                llm_bundle_result = create_llm_bundle(
                    output_dir=output_dir,
                    collection_name=discovery.collection_name,
                    staged_files=stage.staged_files,
                    converted_source_paths=converted_source_paths,
                )
                _log_elapsed(log, "pipeline.llm_bundle", started_at)
                log(
                    "LLM bundle created: "
                    f"{llm_bundle_result.bundle_dir} "
                    f"(md={llm_bundle_result.markdown_files}, images={llm_bundle_result.image_files})"
                )

            # Level 4: polish and inline images into EN HTML files.
            if converted_source_paths and marker_output_format == "html":
                started_at = perf_counter()
                inlined_files = 0
                total_inlined_images = 0
                polish_work_items: list[_HtmlPolishWorkItem] = []
                for staged_file in converted_staged_files:
                    html_path = expected_output_artifact_path(output_dir, staged_file.alias_base_name, ".html")
                    if not html_path.is_file():
                        continue
                    try:
                        stage_dir = html_stage_dir_for_html(html_path)
                        raw_html = html_path.read_text(encoding="utf-8", errors="replace")
                        raw_stage = save_html_stage(
                            stage_dir,
                            RAW_STAGE_NAME,
                            raw_html,
                            "en.raw.marker",
                            source_path=html_path,
                            details=(f"source_pdf={staged_file.source_pdf_path.name}",),
                        )
                        ocr_decision = assess_ocr_quality_from_html(raw_html)
                        if ocr_decision.needs_reocr:
                            queue_result = enqueue_reocr_candidate(
                                output_dir=output_dir,
                                source_pdf_path=staged_file.source_pdf_path,
                                alias_base_name=staged_file.alias_base_name,
                                artifact_path=html_path,
                                stage_raw_path=raw_stage.path,
                                decision=ocr_decision,
                            )
                            ocr_quality_failed_total += 1
                            if queue_result.added:
                                reocr_queued_total += 1
                            reocr_pending_total = queue_result.pending_total
                            log(
                                "OCR quality gate queued for re-OCR: "
                                f"{queue_result.reocr_alias_base_name} "
                                f"(score={ocr_decision.score:.3f}, "
                                f"reasons={','.join(ocr_decision.reasons) or 'score'}, "
                                f"pending_total={queue_result.pending_total})"
                            )
                        citation_profile = citation_profile_for(
                            staged_file.source_pdf_path,
                            staged_file.alias_base_name,
                        )
                        polish_work_items.append(
                            _HtmlPolishWorkItem(
                                staged_file=staged_file,
                                html_path=html_path,
                                stage_dir=stage_dir,
                                raw_stage_path=raw_stage.path,
                                citation_profile=citation_profile,
                            )
                        )
                    except Exception as exc:
                        log(f"Inline images failed for {html_path.name}: {exc}")
                postprocess_workers = min(
                    max(1, int(getattr(options, "postprocess_max_workers", 1) or 1)),
                    max(1, len(polish_work_items)),
                )
                if len(polish_work_items) > 1:
                    log(
                        "HTML postprocess polish workers: "
                        f"workers={postprocess_workers}, files={len(polish_work_items)}"
                    )
                for polish_result in _polish_html_work_items(
                    polish_work_items,
                    max_workers=postprocess_workers,
                ):
                    if polish_result.error:
                        log(f"Inline images failed for {polish_result.html_path.name}: {polish_result.error}")
                        continue
                    inlined_files += 1
                    total_inlined_images += polish_result.inlined_images
                    polish_stage_name = (
                        polish_result.polish_stage_path.name
                        if polish_result.polish_stage_path is not None
                        else ""
                    )
                    log(
                        "HTML debug stages saved: "
                        f"{polish_result.stage_dir} "
                        f"(raw={polish_result.raw_stage_path.name}, "
                        f"en_polish={polish_stage_name})"
                    )
                    mirror_webdav_html(polish_result.html_path)
                _log_elapsed(log, "pipeline.inline_en_images", started_at)
                log(f"Inlined images in EN HTML: files={inlined_files}, images={total_inlined_images}")

            if converted_source_paths and ExportMode.ZOTERO in export_modes_list:
                started_at = perf_counter()
                zotero_dir = zotero_dir_for_mode or resolve_zotero_data_dir(options.zotero_data_dir)
                source_to_resolved = {normalize_source_path(r.source_pdf_path): r for r in resolved}
                history_paths = []

                def html_artifact_for(item: StagedFile) -> Path:
                    return expected_output_artifact_path(output_dir, item.alias_base_name, ".html")

                def queue_entries_from(staged_items: list, error_message: str) -> None:
                    nonlocal zotero_html_queued_total, zotero_pending_total, zotero_html_failed_total
                    queue_batch = []
                    for item in staged_items:
                        source_norm = normalize_source_path(item.source_pdf_path)
                        resolved_item = source_to_resolved.get(source_norm)
                        if resolved_item is None:
                            zotero_html_failed_total += 1
                            log(f"Zotero queue skipped, source mapping missing: {item.source_pdf_path}")
                            continue
                        html_path = html_artifact_for(item)
                        if not html_path.is_file():
                            zotero_html_failed_total += 1
                            log(f"Zotero queue skipped, HTML not found: {html_path}")
                            continue
                        parent_item_id = resolved_item.attachment.parent_item_id or resolved_item.attachment.item_id
                        queue_batch.append(
                            build_pending_entry(
                                source_pdf_path=item.source_pdf_path,
                                html_path=html_path,
                                parent_item_id=parent_item_id,
                                last_error=error_message,
                            )
                        )
                    if queue_batch:
                        added, total = enqueue_pending_attachments(output_dir, queue_batch)
                        zotero_html_queued_total += len(queue_batch)
                        zotero_pending_total = total
                        log(
                            "Queued pending Zotero attachments: "
                            f"queued_now={len(queue_batch)}, "
                            f"new_unique={added}, pending_total={total}"
                        )

                if zotero_write_lock_detected:
                    queue_entries_from(
                        converted_staged_files,
                        "Zotero database locked for writing during run",
                    )
                else:
                    for idx, staged_file in enumerate(converted_staged_files):
                        source_norm = normalize_source_path(staged_file.source_pdf_path)
                        resolved_item = source_to_resolved.get(source_norm)
                        if resolved_item is None:
                            zotero_html_failed_total += 1
                            log(f"Zotero attach skipped, source mapping missing: {staged_file.source_pdf_path}")
                            continue

                        html_path = html_artifact_for(staged_file)
                        if not html_path.is_file():
                            zotero_html_failed_total += 1
                            log(f"Zotero attach skipped, HTML not found: {html_path}")
                            continue

                        try:
                            citation_profile = citation_profile_for(
                                staged_file.source_pdf_path,
                                staged_file.alias_base_name,
                            )
                            inline_result = polish_and_inline_html_file(
                                html_path,
                                citation_profile=citation_profile,
                            )
                            parent_item_id = resolved_item.attachment.parent_item_id or resolved_item.attachment.item_id
                            attach_result = attach_single_file_html(
                                zotero_data_dir=zotero_dir,
                                parent_item_id=parent_item_id,
                                source_pdf_path=staged_file.source_pdf_path,
                                html_content=inline_result.html,
                            )
                            zotero_html_attached_total += 1
                            history_paths.append(staged_file.source_pdf_path)
                            log(
                                "Zotero attachment created: "
                                f"parent={attach_result.parent_item_id}, "
                                f"itemID={attach_result.item_id}, "
                                f"key={attach_result.item_key}, "
                                f"inlined_images={inline_result.inlined_images}"
                            )
                        except RuntimeError as exc:
                            if "locked for writing" in str(exc).lower():
                                queue_entries_from(
                                    converted_staged_files[idx:],
                                    str(exc),
                                )
                                break
                            zotero_html_failed_total += 1
                            log(f"Zotero attachment failed for {staged_file.source_pdf_path}: {exc}")
                        except Exception as exc:
                            zotero_html_failed_total += 1
                            log(f"Zotero attachment failed for {staged_file.source_pdf_path}: {exc}")

                _log_elapsed(log, "pipeline.zotero_attach_html", started_at)
                zotero_pending_total = len(load_pending_attachments(output_dir))

            if history_paths:
                started_at = perf_counter()
                history_path = append_history(history_paths, output_dir)
                _log_elapsed(log, "pipeline.append_history", started_at)
                log(f"History updated: {history_path}")

            marker_failed_total = len(stage.staged_files) - len(converted_source_paths)
            failed_total = (
                marker_failed_total
                + zotero_html_failed_total
            )

            return PipelineSummary(
                collection_key=discovery.collection_key,
                collection_name=discovery.collection_name,
                attachments_total=discovery.attachments_total,
                pdfs_resolved=len(discovery.candidates),
                staged_total=len(stage.staged_files),
                converted_total=len(converted_source_paths),
                skipped_existing=skipped_existing,
                failed_total=failed_total,
                output_dir=output_dir,
                filename_map_path=filename_map_path,
                export_mode=options.export_mode,
                llm_bundle_dir=None if llm_bundle_result is None else llm_bundle_result.bundle_dir,
                llm_bundle_markdown_files=0 if llm_bundle_result is None else llm_bundle_result.markdown_files,
                llm_bundle_image_files=0 if llm_bundle_result is None else llm_bundle_result.image_files,
                zotero_html_attached_total=zotero_html_attached_total,
                zotero_html_failed_total=zotero_html_failed_total,
                zotero_html_queued_total=zotero_html_queued_total,
                zotero_pending_total=zotero_pending_total,
                webdav_uploaded_total=webdav_uploaded_total,
                webdav_failed_total=webdav_failed_total,
                webdav_queued_total=webdav_queued_total,
                webdav_pending_total=webdav_pending_total,
                ocr_quality_failed_total=ocr_quality_failed_total,
                reocr_queued_total=reocr_queued_total,
                reocr_pending_total=reocr_pending_total,
            )
        finally:
            cleanup_started_at = perf_counter()
            cleanup_staging_dir(stage.staging_dir)
            log("Staging folder cleaned up.")
            _log_elapsed(log, "pipeline.cleanup_staging", cleanup_started_at)
    finally:
        close_katex_v8_context()
        cleanup_runtime_temp_root(runtime_tmp_root)
        log(f"Runtime temp cleaned: {runtime_tmp_root}")
        _log_elapsed(log, "pipeline.total", pipeline_started_at)
