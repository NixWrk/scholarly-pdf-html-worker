from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .atomic_io import write_json_atomic, write_text_atomic


HTML_STAGE_DIR_NAME = "_pdf_html_polish_stages"
LEGACY_HTML_STAGE_DIR_NAME = "_z2m_stages"
HTML_STAGE_DIR_NAMES = frozenset({HTML_STAGE_DIR_NAME, LEGACY_HTML_STAGE_DIR_NAME})
HTML_STAGE_LOG_NAME = "stage.log"
RAW_STAGE_NAME = "01.en.raw.html"
POLISH_STAGE_NAME = "02.en.polish.html"
RAW_CONVERSION_MANIFEST_NAME = "raw_conversion_manifest.json"
RAW_CONVERSION_MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HtmlStageSaveResult:
    path: Path
    chars: int
    bytes: int
    log_path: Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_raw_conversion_manifest(
    stage_dir: Path,
    *,
    source_pdf: Path,
    raw_stage_path: Path,
) -> Path:
    """Atomically publish provenance for one confirmed raw Marker stage."""

    stage_root = stage_dir.resolve(strict=False)
    raw_path = raw_stage_path.resolve(strict=False)
    if raw_path.parent != stage_root or raw_path.name != RAW_STAGE_NAME:
        raise ValueError(f"Raw stage must be {stage_root / RAW_STAGE_NAME}: {raw_stage_path}")
    source_path = source_pdf.resolve(strict=True)
    raw_path = raw_stage_path.resolve(strict=True)
    source_stat = source_path.stat()
    raw_stat = raw_path.stat()
    payload = {
        "schema_version": RAW_CONVERSION_MANIFEST_SCHEMA_VERSION,
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_pdf_name": source_path.name,
        "source_pdf_bytes": int(source_stat.st_size),
        "source_pdf_sha256": _sha256_file(source_path),
        "raw_html_name": RAW_STAGE_NAME,
        "raw_html_bytes": int(raw_stat.st_size),
        "raw_html_sha256": _sha256_file(raw_path),
    }
    manifest_path = stage_root / RAW_CONVERSION_MANIFEST_NAME
    write_json_atomic(manifest_path, payload)
    return manifest_path


def html_stage_dir_for_html(html_path: Path) -> Path:
    """Return the per-paper debug directory for HTML stage snapshots."""

    return html_path.parent / HTML_STAGE_DIR_NAME


def html_stage_log_path(stage_dir: Path) -> Path:
    return stage_dir / HTML_STAGE_LOG_NAME


def is_html_stage_path(path: Path) -> bool:
    return path.parent.name in HTML_STAGE_DIR_NAMES


def is_html_stage_dir_name(name: str) -> bool:
    return name in HTML_STAGE_DIR_NAMES


def article_dir_from_html_stage(stage_path: Path) -> Path:
    return stage_path.parent.parent if is_html_stage_path(stage_path) else stage_path.parent


def article_name_from_html_stage(stage_path: Path) -> str:
    return article_dir_from_html_stage(stage_path).name


def append_html_stage_log(stage_dir: Path, message: str) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    log_path = html_stage_log_path(stage_dir)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")
    return log_path


def save_html_stage(
    stage_dir: Path,
    filename: str,
    html: str,
    stage: str,
    *,
    source_path: Path | None = None,
    details: list[str] | tuple[str, ...] = (),
) -> HtmlStageSaveResult:
    """Write one HTML stage snapshot and append stage metadata to logs."""

    stage_dir.mkdir(parents=True, exist_ok=True)
    path = stage_dir / filename
    write_text_atomic(path, html)

    encoded_len = len(html.encode("utf-8"))
    source_text = f" source={source_path.name}" if source_path is not None else ""
    detail_text = "".join(f" {item}" for item in details if item)
    line = (
        f"stage={stage} file={filename} chars={len(html)} "
        f"bytes={encoded_len}{source_text}{detail_text}"
    )
    log_path = append_html_stage_log(stage_dir, line)
    write_text_atomic(path.with_suffix(".log"), line + "\n")

    return HtmlStageSaveResult(
        path=path,
        chars=len(html),
        bytes=encoded_len,
        log_path=log_path,
    )
