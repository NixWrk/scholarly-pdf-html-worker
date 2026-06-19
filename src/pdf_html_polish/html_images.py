"""Image inlining helpers for single-file HTML export."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import mimetypes
from pathlib import Path
import re
import urllib.parse
from typing import Callable, Mapping

from .html_links import escape_html_attr_literal


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
IMG_SRC_PATTERN = re.compile(r'(<img\b[^>]*?\ssrc\s*=\s*)(["\'])([^"\']+)(\2)', re.IGNORECASE)
IMAGE_CACHE_KEY_ATTR_PATTERN = re.compile(
    r'\bdata-z2m-image-key\s*=\s*(["\'])([^"\']+)\1',
    re.IGNORECASE,
)


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


def decode_data_image_payload(src_value: str) -> tuple[str, bytes] | None:
    src_value = src_value.strip()
    if src_value.lower().startswith("data:image/"):
        comma_idx = src_value.find(",")
        if comma_idx < 0:
            return None
        meta = src_value[:comma_idx].lower()
        if ";base64" not in meta:
            return None
        mime = meta.removeprefix("data:").split(";", 1)[0]
        payload = re.sub(r"\s+", "", src_value[comma_idx + 1 :])
    else:
        payload = re.sub(r"\s+", "", src_value)
        if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", payload):
            return None
        if payload.startswith("/9j/"):
            mime = "image/jpeg"
        elif payload.startswith("iVBOR"):
            mime = "image/png"
        elif payload.startswith(("R0lGODlh", "R0lGODdh")):
            mime = "image/gif"
        elif payload.startswith("UklGR"):
            mime = "image/webp"
        else:
            return None
    if len(payload) % 4 == 1:
        return mime, b""
    padded = payload + ("=" * ((4 - len(payload) % 4) % 4))
    try:
        return mime, base64.b64decode(padded)
    except Exception:
        return mime, b""


def data_image_src_looks_renderable(src_value: str) -> bool:
    decoded = decode_data_image_payload(src_value)
    if decoded is None:
        return True
    mime, blob = decoded
    if not blob:
        return False
    if mime == "image/jpeg":
        return blob.startswith(b"\xff\xd8") and blob.endswith(b"\xff\xd9")
    if mime == "image/png":
        return blob.startswith(b"\x89PNG\r\n\x1a\n") and blob.endswith(b"IEND\xaeB`\x82")
    if mime == "image/gif":
        return blob.startswith((b"GIF87a", b"GIF89a")) and blob.endswith(b";")
    if mime == "image/webp":
        return len(blob) >= 12 and blob.startswith(b"RIFF") and blob[8:12] == b"WEBP"
    return True


def html_node_image_srcs(raw: str) -> list[str]:
    return [match.group(3).strip() for match in IMG_SRC_PATTERN.finditer(raw)]


def html_node_has_renderable_image(raw: str) -> bool:
    return any(data_image_src_looks_renderable(src) for src in html_node_image_srcs(raw))


def html_node_has_broken_data_image(raw: str) -> bool:
    return any(
        decode_data_image_payload(src) is not None and not data_image_src_looks_renderable(src)
        for src in html_node_image_srcs(raw)
    )


def refresh_inlined_data_urls_by_hint(
    html: str,
    *,
    base_dir: Path,
) -> tuple[str, int]:
    """Refresh stale/corrupted data URLs using ``data-z2m-src`` sidecar hints."""
    refreshed = 0

    def resolve_hint_path(path_value: str) -> Path | None:
        if not path_value:
            return None
        clean_path = path_value.split("?", 1)[0].split("#", 1)[0]
        decoded = urllib.parse.unquote(clean_path)
        candidate = (base_dir / decoded).resolve(strict=False)
        if candidate.is_file():
            return candidate
        return None

    def replace(match: re.Match[str]) -> str:
        nonlocal refreshed
        prefix = match.group(1)
        quote = match.group(2)
        src_value = match.group(3).strip()
        suffix = match.group(4)

        if not src_value.lower().startswith("data:"):
            return match.group(0)

        hint_match = re.search(
            r'\bdata-z2m-src\s*=\s*(["\'])([^"\']+)\1',
            prefix,
            re.IGNORECASE,
        )
        if hint_match is None:
            return match.group(0)
        candidate = resolve_hint_path(hint_match.group(2).strip())
        if candidate is None:
            return match.group(0)
        if validate_data_url(src_value, candidate):
            return match.group(0)

        refreshed_data_url = to_data_url(candidate, detect_by_signature=True, log_func=None)
        if refreshed_data_url is None:
            return match.group(0)
        if not validate_data_url(refreshed_data_url, candidate):
            return match.group(0)

        refreshed += 1
        return f"{prefix}{quote}{refreshed_data_url}{suffix}"

    return IMG_SRC_PATTERN.sub(replace, html), refreshed


def refresh_inlined_data_urls_by_cache(
    html: str,
    *,
    image_cache: Mapping[str, str] | None,
) -> tuple[str, int]:
    """Restore broken inline image payloads from the pre-polish image cache."""
    if not image_cache:
        return html, 0

    refreshed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal refreshed
        prefix = match.group(1)
        quote = match.group(2)
        src_value = match.group(3).strip()
        suffix = match.group(4)

        key_match = IMAGE_CACHE_KEY_ATTR_PATTERN.search(prefix)
        if key_match is None:
            return match.group(0)
        cached_data_url = image_cache.get(key_match.group(2).strip())
        if not cached_data_url or not cached_data_url.lower().startswith("data:image/"):
            return match.group(0)
        if not data_image_src_looks_renderable(cached_data_url):
            return match.group(0)
        if src_value.lower().startswith("data:image/") and data_image_src_looks_renderable(src_value):
            return match.group(0)

        refreshed += 1
        return f"{prefix}{quote}{cached_data_url}{suffix}"

    return IMG_SRC_PATTERN.sub(replace, html), refreshed


def inline_images_from_html_text(text: str, base_dir: Path) -> tuple[InlineHtmlResult, dict[str, str]]:
    inlined_count = 0
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
    sidecar_images = sorted(
        (
            path
            for path in base_dir.iterdir()
            if path.is_file() and path.suffix.lower() in image_exts
        ),
        key=lambda path: path.name.lower(),
    )
    img_matches = list(IMG_SRC_PATTERN.finditer(text))
    data_img_count = sum(1 for match in img_matches if (match.group(3) or "").strip().lower().startswith("data:"))
    all_images_already_data = bool(img_matches) and data_img_count == len(img_matches)
    allow_sidecar_order_refresh = all_images_already_data and len(sidecar_images) == len(img_matches)
    sidecar_cursor = [0]
    image_match_cursor = [0]
    image_cache: dict[str, str] = {}

    def resolve_candidate(path_value: str) -> Path | None:
        if not path_value:
            return None
        clean_path = path_value.split("?", 1)[0].split("#", 1)[0]
        decoded = urllib.parse.unquote(clean_path)
        candidate = (base_dir / decoded).resolve(strict=False)
        if candidate.is_file():
            return candidate
        return None

    def add_src_hint(prefix: str, hint_path: str) -> str:
        if re.search(r'\bdata-z2m-src\s*=', prefix, re.IGNORECASE):
            return prefix
        escaped_hint = escape_html_attr_literal(hint_path)
        return re.sub(
            r"\bsrc\s*=\s*$",
            f'data-z2m-src="{escaped_hint}" src=',
            prefix,
            flags=re.IGNORECASE,
        )

    def add_image_key(prefix: str, image_key: str) -> str:
        if IMAGE_CACHE_KEY_ATTR_PATTERN.search(prefix):
            return prefix
        escaped_key = escape_html_attr_literal(image_key)
        return re.sub(
            r"\bsrc\s*=\s*$",
            f'data-z2m-image-key="{escaped_key}" src=',
            prefix,
            flags=re.IGNORECASE,
        )

    def remember_data_url(prefix: str, data_url: str, match_idx: int) -> str:
        if not data_url.lower().startswith("data:image/"):
            return prefix
        if not data_image_src_looks_renderable(data_url):
            return prefix
        decoded = decode_data_image_payload(data_url)
        if decoded is None:
            return prefix
        _, blob = decoded
        key_match = IMAGE_CACHE_KEY_ATTR_PATTERN.search(prefix)
        if key_match is None:
            digest = hashlib.sha256(blob).hexdigest()[:16]
            image_key = f"img-{match_idx}-{digest}"
            prefix = add_image_key(prefix, image_key)
        else:
            image_key = key_match.group(2).strip()
        image_cache[image_key] = data_url
        return prefix

    def replace(match: re.Match[str]) -> str:
        nonlocal inlined_count
        match_idx = image_match_cursor[0]
        image_match_cursor[0] += 1
        prefix = match.group(1)
        quote = match.group(2)
        src_value = match.group(3).strip()
        suffix = match.group(4)
        hint_match = re.search(
            r'\bdata-z2m-src\s*=\s*(["\'])([^"\']+)\1',
            prefix,
            re.IGNORECASE,
        )
        src_hint = hint_match.group(2).strip() if hint_match else ""

        if not src_value:
            return match.group(0)
        src_lower = src_value.lower()
        candidate: Path | None = None

        if src_lower.startswith("data:"):
            if src_hint:
                candidate = resolve_candidate(src_hint)
            if candidate is None and allow_sidecar_order_refresh and sidecar_cursor[0] < len(sidecar_images):
                candidate = sidecar_images[sidecar_cursor[0]]
                sidecar_cursor[0] += 1
                prefix = add_src_hint(prefix, candidate.name)
            if candidate is None:
                prefix = remember_data_url(prefix, src_value, match_idx)
                if prefix != match.group(1):
                    return f"{prefix}{quote}{src_value}{suffix}"
                return match.group(0)
        elif is_inline_or_remote(src_value):
            return match.group(0)
        else:
            candidate = resolve_candidate(src_value)
            if candidate is None:
                return match.group(0)
            prefix = add_src_hint(prefix, src_value)

        data_url = to_data_url(candidate, detect_by_signature=True, log_func=None)
        if data_url is None:
            return match.group(0)
        if not validate_data_url(data_url, candidate):
            return match.group(0)

        prefix = remember_data_url(prefix, data_url, match_idx)
        inlined_count += 1
        return f"{prefix}{quote}{data_url}{suffix}"

    inlined_html = IMG_SRC_PATTERN.sub(replace, text)
    return InlineHtmlResult(html=inlined_html, inlined_images=inlined_count), image_cache
