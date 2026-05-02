from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


HTML_STAGE_DIR_NAME = "_z2m_stages"
HTML_STAGE_LOG_NAME = "stage.log"


@dataclass(frozen=True)
class HtmlStageSaveResult:
    path: Path
    chars: int
    bytes: int
    log_path: Path


def html_stage_dir_for_html(html_path: Path) -> Path:
    """Return the per-paper debug directory for HTML stage snapshots."""

    return html_path.parent / HTML_STAGE_DIR_NAME


def html_stage_log_path(stage_dir: Path) -> Path:
    return stage_dir / HTML_STAGE_LOG_NAME


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
    path.write_text(html, encoding="utf-8")

    encoded_len = len(html.encode("utf-8"))
    source_text = f" source={source_path.name}" if source_path is not None else ""
    detail_text = "".join(f" {item}" for item in details if item)
    line = (
        f"stage={stage} file={filename} chars={len(html)} "
        f"bytes={encoded_len}{source_text}{detail_text}"
    )
    log_path = append_html_stage_log(stage_dir, line)
    path.with_suffix(".log").write_text(line + "\n", encoding="utf-8")

    return HtmlStageSaveResult(
        path=path,
        chars=len(html),
        bytes=encoded_len,
        log_path=log_path,
    )
