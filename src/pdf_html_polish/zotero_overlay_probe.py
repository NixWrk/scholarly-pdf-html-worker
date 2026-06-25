from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from subprocess import TimeoutExpired, run


DEFAULT_OVERLAY_TIMEOUT_SECONDS = 180
OVERLAY_PROBE_ENV = "PDF_HTML_POLISH_ZOTERO_OVERLAY_PROBE"
PDFJS_DIR_ENV = "PDF_HTML_POLISH_ZOTERO_PDFJS_DIR"


@dataclass(frozen=True)
class ZoteroOverlayProbeResult:
    output_path: Path
    attempted: bool
    generated: bool
    command: list[str]
    error: str = ""
    stdout: str = ""
    stderr: str = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_zotero_overlay_probe_script() -> Path | None:
    env_probe = os.environ.get(OVERLAY_PROBE_ENV)
    if env_probe:
        candidate = Path(env_probe).expanduser().resolve(strict=False)
        if candidate.is_file():
            return candidate

    repo_root = _repo_root()
    candidates = [
        repo_root / "tools" / "zotero_overlay_probe.mjs",
        repo_root / ".tmp_local2" / "vendor" / "zotero-pdfjs" / "zotero_overlay_probe.mjs",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def find_zotero_pdfjs_dir() -> Path | None:
    env_pdfjs = os.environ.get(PDFJS_DIR_ENV)
    if env_pdfjs:
        candidate = Path(env_pdfjs).expanduser().resolve(strict=False)
        if candidate.is_dir():
            return candidate

    for candidate in (
        _repo_root() / ".tmp_local2" / "vendor" / "zotero-pdfjs",
        Path("/opt/zotero-pdfjs"),
    ):
        if candidate.is_dir():
            return candidate
    return None


def generate_zotero_overlay_json(
    pdf_path: str | Path,
    output_path: str | Path,
    *,
    timeout_seconds: int = DEFAULT_OVERLAY_TIMEOUT_SECONDS,
) -> ZoteroOverlayProbeResult:
    """Run the Zotero/pdf.js overlay probe and write a temporary JSON file."""
    pdf = Path(pdf_path).expanduser().resolve(strict=False)
    output = Path(output_path).expanduser().resolve(strict=False)
    probe_script = find_zotero_overlay_probe_script()
    if probe_script is None:
        return ZoteroOverlayProbeResult(
            output_path=output,
            attempted=False,
            generated=False,
            command=[],
            error=(
                "Zotero overlay probe script not found. Set "
                f"{OVERLAY_PROBE_ENV} or keep tools/zotero_overlay_probe.mjs available."
            ),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "node",
        str(probe_script),
        str(pdf),
        "--out",
        str(output),
        "--no-futyma-check",
    ]
    pdfjs_dir = find_zotero_pdfjs_dir()
    if pdfjs_dir is not None:
        command.extend(["--pdfjs-dir", str(pdfjs_dir)])

    try:
        completed = run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return ZoteroOverlayProbeResult(
            output_path=output,
            attempted=True,
            generated=False,
            command=command,
            error=f"Node.js executable not found: {exc}",
        )
    except TimeoutExpired as exc:
        return ZoteroOverlayProbeResult(
            output_path=output,
            attempted=True,
            generated=False,
            command=command,
            error=f"Zotero overlay probe timed out after {timeout_seconds}s",
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
        )

    generated = completed.returncode == 0 and output.is_file()
    error = "" if generated else f"Zotero overlay probe exited with code {completed.returncode}"
    return ZoteroOverlayProbeResult(
        output_path=output,
        attempted=True,
        generated=generated,
        command=command,
        error=error,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
