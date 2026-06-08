"""Image inlining helpers for single-file HTML export."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import mimetypes
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class InlineHtmlResult:
    html: str
    inlined_images: int


IMAGE_SIGNATURES: dict[bytes, str] = {
    # Generic JPEG SOI+marker prefix (fallback for uncommon APP markers).
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff\xe0": "image/jpeg",
    b"\xff\xd8\xff\xe1": "image/jpeg",
    b"\xff\xd8\xff\xed": "image/jpeg",
    b"\xff\xd8\xff\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",
    b"%PDF": "application/pdf",
    b"\x49\x49\x2a\x00": "image/tiff",
    b"\x4d\x4d\x00\x2a": "image/tiff",
    b"\x42\x4d": "image/bmp",
}


def is_inline_or_remote(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("data:")
        or lowered.startswith("mailto:")
        or lowered.startswith("#")
        or lowered.startswith("javascript:")
    )


def detect_image_signature(file_path: Path) -> str | None:
    """Detect MIME type by reading magic bytes from file."""
    try:
        with open(file_path, "rb") as handle:
            header = handle.read(12)
    except OSError:
        return None

    if not header:
        return None

    for signature, mime in IMAGE_SIGNATURES.items():
        if header.startswith(signature):
            return mime
    return None


def detect_jpeg_colorspace(header: bytes) -> str | None:
    """Detect JPEG colorspace by parsing APP13 marker."""
    if len(header) < 4:
        return None

    offset = 3
    while offset + 4 <= len(header):
        if header[offset] != 0xFF:
            break
        marker = header[offset + 1]
        if marker == 0xED:
            if offset + 4 > len(header):
                return None
            length = (header[offset + 2] << 8) | header[offset + 3]
            if offset + 2 + length > len(header):
                return None
            start = offset + 4
            end = start + 12
            if end <= len(header) and header[start:end] == b"Photoshop ":
                color_data_offset = start + 8
                if color_data_offset + 2 <= len(header):
                    color_type = header[color_data_offset]
                    return "cmyk" if color_type == 1 else "rgb"
        elif marker in (0xE0, 0xE1, 0xEE):
            if offset + 4 > len(header):
                break
            length = (header[offset + 2] << 8) | header[offset + 3]
            if length < 2:
                break
            offset += 2 + length
            continue
        else:
            if offset + 4 > len(header):
                break
            length = (header[offset + 2] << 8) | header[offset + 3]
            if length < 2:
                break
            offset += 2 + length
            continue

    return None


def to_data_url(
    file_path: Path,
    *,
    detect_by_signature: bool = True,
    log_func: Callable[[str], None] | None = None,
) -> str | None:
    """Convert image file to a data URL with signature-based MIME detection."""
    mime_by_sig = detect_image_signature(file_path) if detect_by_signature else None
    mime_by_ext, _ = mimetypes.guess_type(file_path.name)
    detected_mime = mime_by_sig or mime_by_ext

    if not detected_mime or not detected_mime.startswith("image/"):
        if log_func:
            log_func(
                f"[DIAG] MIME detect fail: path={file_path.name} "
                f"sig={mime_by_sig} ext={mime_by_ext}"
            )
        return None

    blob = file_path.read_bytes()
    file_hash = hashlib.sha256(blob).hexdigest()[:16]

    cmyk_warning = ""
    if detected_mime == "image/jpeg" and len(blob) >= 4:
        colorspace = detect_jpeg_colorspace(blob)
        if colorspace == "cmyk":
            cmyk_warning = " [WARNING: CMYK JPEG - may not display correctly in browsers]"

    try:
        encoded = base64.b64encode(blob).decode("ascii")
        data_url = f"data:{detected_mime};base64,{encoded}"

        if log_func:
            log_func(
                f"[DIAG] MIME detected: path={file_path.name} "
                f"sig={mime_by_sig} ext={mime_by_ext} hash={file_hash}{cmyk_warning}"
            )
        return data_url
    except Exception as exc:
        if log_func:
            log_func(f"[DIAG] Base64 encode fail: {file_path.name}: {exc}")
        return None


def validate_data_url(data_url: str, original_file: Path) -> bool:
    """Validate that a data URL decodes back to the original file."""
    try:
        if not data_url.startswith("data:image/"):
            return False

        comma_idx = data_url.find(",")
        if comma_idx == -1:
            return False

        b64_content = data_url[comma_idx + 1 :]
        decoded = base64.b64decode(b64_content)
        original = original_file.read_bytes()

        return decoded == original
    except Exception:
        return False
