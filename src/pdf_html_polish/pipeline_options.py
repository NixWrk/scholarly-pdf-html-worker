"""Option and discovery result models for the conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .export_modes import ExportMode, parse_export_mode
from .models import ResolvedAttachment
from .staging import DEFAULT_MAX_BASE_LEN


@dataclass(frozen=True)
class PipelineOptions:
    zotero_data_dir: str = ""
    collection_key: str = ""
    include_subcollections: bool = False
    output_dir: str = ""
    skip_existing: bool = True
    use_cuda: bool = True
    cuda_device_index: int | None = 0
    model_cache_dir: str | None = None
    max_base_len: int = DEFAULT_MAX_BASE_LEN
    disable_batch_multiprocessing: bool = False
    cleanup_staging: bool = True
    source_pdf_paths: list[str] | None = None
    selected_source_pdf_paths: list[str] | None = None
    skip_existing_source_pdf_paths: list[str] | None = None
    # Comma-separated export modes, e.g. "classic" or "classic,llm_bundle".
    # Multiple modes sharing the same marker_output_format run with one Marker call.
    export_mode: str = ExportMode.CLASSIC.value
    zotero_overlay_dir: str | None = None
    webdav_upload_enabled: bool = False
    webdav_config_path: str | None = None

    @property
    def export_modes_list(self) -> list[ExportMode]:
        return [parse_export_mode(m.strip()) for m in self.export_mode.split(",") if m.strip()]


@dataclass(frozen=True)
class PdfCandidate:
    resolved_attachment: ResolvedAttachment
    already_in_output: bool


@dataclass(frozen=True)
class PdfDiscoveryResult:
    collection_name: str
    collection_key: str
    attachments_total: int
    unresolved_total: int
    candidates: list[PdfCandidate]
