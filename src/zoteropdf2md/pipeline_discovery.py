"""PDF source discovery adapters for the conversion pipeline."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Callable

from .attachments import resolve_pdf_attachments
from .models import AttachmentRecord, ResolvedAttachment
from .output_state import detect_existing_results, normalize_source_path
from .paths import resolve_zotero_data_dir
from .pipeline_options import PdfCandidate, PdfDiscoveryResult
from .zotero import ZoteroRepository


def _log_elapsed(log: Callable[[str], None] | None, stage: str, started_at: float) -> None:
    if log is None:
        return
    log(f"[timer] {stage}: {perf_counter() - started_at:.2f}s")


def discover_collection_pdfs(
    zotero_data_dir: str,
    collection_key: str,
    include_subcollections: bool,
    output_dir: str,
    artifact_extension: str = ".md",
    temp_root: Path | None = None,
    log: Callable[[str], None] | None = None,
) -> PdfDiscoveryResult:
    discover_started_at = perf_counter()

    started_at = perf_counter()
    zotero_dir = resolve_zotero_data_dir(zotero_data_dir)
    out_dir = Path(output_dir).expanduser().resolve()
    _log_elapsed(log, "discover.resolve_paths", started_at)

    started_at = perf_counter()
    repo = ZoteroRepository(zotero_dir, snapshot_temp_root=temp_root)
    _log_elapsed(log, "discover.open_repository", started_at)

    started_at = perf_counter()
    collection = repo.get_collection_by_key(collection_key)
    _log_elapsed(log, "discover.get_collection", started_at)

    started_at = perf_counter()
    collection_ids = repo.get_descendant_collection_ids(collection.collection_id, include_subcollections)
    _log_elapsed(log, "discover.get_descendant_collection_ids", started_at)

    started_at = perf_counter()
    attachment_records = repo.get_attachment_records(collection_ids)
    _log_elapsed(log, "discover.get_attachment_records", started_at)

    started_at = perf_counter()
    resolved, unresolved = resolve_pdf_attachments(zotero_dir, attachment_records)
    _log_elapsed(log, "discover.resolve_pdf_attachments", started_at)

    started_at = perf_counter()
    existing_in_output = detect_existing_results(
        out_dir,
        [r.source_pdf_path for r in resolved],
        artifact_extension=artifact_extension,
    )
    _log_elapsed(log, "discover.detect_existing_results", started_at)

    candidates = [
        PdfCandidate(
            resolved_attachment=r,
            already_in_output=(normalize_source_path(r.source_pdf_path) in existing_in_output),
        )
        for r in resolved
    ]
    _log_elapsed(log, "discover.total", discover_started_at)

    return PdfDiscoveryResult(
        collection_name=collection.full_name,
        collection_key=collection.key,
        attachments_total=len(attachment_records),
        unresolved_total=len(unresolved),
        candidates=candidates,
    )


def discover_source_pdfs(
    source_pdf_paths: list[str],
    output_dir: str,
    artifact_extension: str = ".md",
    log: Callable[[str], None] | None = None,
) -> PdfDiscoveryResult:
    discover_started_at = perf_counter()

    started_at = perf_counter()
    out_dir = Path(output_dir).expanduser().resolve()
    _log_elapsed(log, "discover_file.resolve_paths", started_at)

    resolved: list[ResolvedAttachment] = []
    unresolved_total = 0
    seen: set[str] = set()
    for index, raw_path in enumerate(source_pdf_paths, start=1):
        pdf_path = Path(raw_path).expanduser().resolve(strict=False)
        normalized = normalize_source_path(pdf_path)
        if normalized in seen:
            continue
        seen.add(normalized)
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            unresolved_total += 1
            if log is not None:
                log(f"Skipped non-PDF or missing source: {pdf_path}")
            continue
        record = AttachmentRecord(
            item_id=index,
            attachment_key=f"direct_pdf_{index:04d}",
            parent_item_id=None,
            link_mode=None,
            path=str(pdf_path),
            content_type="application/pdf",
        )
        resolved.append(ResolvedAttachment(attachment=record, source_pdf_path=pdf_path))

    started_at = perf_counter()
    existing_in_output = detect_existing_results(
        out_dir,
        [r.source_pdf_path for r in resolved],
        artifact_extension=artifact_extension,
    )
    _log_elapsed(log, "discover_file.detect_existing_results", started_at)

    candidates = [
        PdfCandidate(
            resolved_attachment=r,
            already_in_output=(normalize_source_path(r.source_pdf_path) in existing_in_output),
        )
        for r in resolved
    ]
    _log_elapsed(log, "discover_file.total", discover_started_at)

    return PdfDiscoveryResult(
        collection_name="direct PDF files",
        collection_key="direct_pdf",
        attachments_total=len(seen),
        unresolved_total=unresolved_total,
        candidates=candidates,
    )
