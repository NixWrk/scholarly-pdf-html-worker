"""Image inlining helpers for single-file HTML export."""

from __future__ import annotations

import base64
from collections import deque
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import mimetypes
import os
from pathlib import Path
import re
import urllib.parse
from typing import Callable, Mapping

from .html_links import escape_html_attr_literal


@dataclass(frozen=True)
class InlineHtmlResult:
    html: str
    inlined_images: int


@dataclass(frozen=True)
class InlineImageIntegrity:
    image_count: int
    missing_src_count: int
    unsupported_src_count: int
    broken_data_url_count: int
    inline_skip_count: int

    @property
    def publishable(self) -> bool:
        return not (
            self.missing_src_count
            or self.unsupported_src_count
            or self.broken_data_url_count
            or self.inline_skip_count
        )


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
INLINE_SKIP_ATTR_PATTERN = re.compile(
    r'\bdata-z2m-inline-skip\s*=',
    re.IGNORECASE,
)
INLINE_SKIP_METADATA_PATTERN = re.compile(
    r'''\s+data-z2m-inline-(?:skip|size|limit)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''',
    re.IGNORECASE,
)
# Standalone Zotero/WebDAV HTML attachments do not carry sidecar image files.
# By default, inline every local image; explicit env/call limits remain available
# as an operator escape hatch for pathological inputs.
DEFAULT_INLINE_IMAGE_MAX_BYTES = 0
DEFAULT_INLINE_IMAGE_TOTAL_MAX_BYTES = 0
DEFAULT_INLINE_IMAGE_DOWNSCALE_BYTES = 8 * 1024 * 1024
DEFAULT_INLINE_IMAGE_HARD_MAX_BYTES = 64 * 1024 * 1024
INLINE_IMAGE_MAX_BYTES_ENV = "PDF_HTML_INLINE_IMAGE_MAX_BYTES"
INLINE_IMAGE_TOTAL_MAX_BYTES_ENV = "PDF_HTML_INLINE_IMAGE_TOTAL_MAX_BYTES"
INLINE_IMAGE_DOWNSCALE_BYTES_ENV = "PDF_HTML_INLINE_IMAGE_DOWNSCALE_BYTES"
INLINE_IMAGE_HARD_MAX_BYTES_ENV = "PDF_HTML_INLINE_IMAGE_HARD_MAX_BYTES"
DOWNSCALE_MAX_EDGE = 2000
DOWNSCALE_JPEG_QUALITY = 85
DOWNSCALE_SOURCE_MAX_PIXELS = 50_000_000


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


def _blob_to_data_url(
    blob: bytes,
    detected_mime: str,
    *,
    file_name: str,
    mime_by_sig: str | None = None,
    mime_by_ext: str | None = None,
    log_func: Callable[[str], None] | None = None,
) -> str | None:
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
                f"[DIAG] MIME detected: path={file_name} "
                f"sig={mime_by_sig} ext={mime_by_ext} hash={file_hash}{cmyk_warning}"
            )
        return data_url
    except Exception as exc:
        if log_func:
            log_func(f"[DIAG] Base64 encode fail: {file_name}: {exc}")
        return None


def to_data_url(
    file_path: Path,
    *,
    detect_by_signature: bool = True,
    max_bytes: int | None = None,
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

    try:
        file_size = file_path.stat().st_size
    except OSError:
        return None
    if max_bytes is not None and file_size > max_bytes:
        if log_func:
            log_func(
                f"[DIAG] Image inline skipped: path={file_path.name} "
                f"size={file_size} max={max_bytes}"
            )
        return None

    blob = file_path.read_bytes()
    return _blob_to_data_url(
        blob,
        detected_mime,
        file_name=file_path.name,
        mime_by_sig=mime_by_sig,
        mime_by_ext=mime_by_ext,
        log_func=log_func,
    )


def downscale_image_for_inline(
    file_path: Path,
    *,
    max_bytes: int | None,
    detect_by_signature: bool = True,
    log_func: Callable[[str], None] | None = None,
) -> tuple[str, int] | None:
    """Downscale an oversized image and return ``(data_url, byte_count)`` if it fits."""
    if max_bytes is None or max_bytes <= 0:
        return None

    mime_by_sig = detect_image_signature(file_path) if detect_by_signature else None
    mime_by_ext, _ = mimetypes.guess_type(file_path.name)
    detected_mime = mime_by_sig or mime_by_ext
    if not detected_mime or not detected_mime.startswith("image/"):
        return None

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        if log_func:
            log_func(f"[DIAG] Pillow unavailable; cannot downscale {file_path.name}")
        return None

    try:
        with Image.open(file_path) as image:
            width, height = image.size
            if width <= 0 or height <= 0:
                return None
            if width * height > DOWNSCALE_SOURCE_MAX_PIXELS:
                if log_func:
                    log_func(
                        f"[DIAG] Image downscale source too large: path={file_path.name} "
                        f"pixels={width * height} max={DOWNSCALE_SOURCE_MAX_PIXELS}"
                    )
                return None
            image.load()
            longest_edge = max(width, height)
            if longest_edge > DOWNSCALE_MAX_EDGE:
                scale = DOWNSCALE_MAX_EDGE / longest_edge
                resized_to = (
                    max(1, int(width * scale)),
                    max(1, int(height * scale)),
                )
                image = image.resize(resized_to, Image.Resampling.LANCZOS)

            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            output = BytesIO()
            if detected_mime == "image/png" and has_alpha:
                if image.mode not in {"RGBA", "LA"}:
                    image = image.convert("RGBA")
                output_mime = "image/png"
                image.save(output, format="PNG", optimize=True)
            else:
                output_mime = "image/jpeg"
                if image.mode != "RGB":
                    image = image.convert("RGB")
                image.save(
                    output,
                    format="JPEG",
                    quality=DOWNSCALE_JPEG_QUALITY,
                    optimize=True,
                )
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        if log_func:
            log_func(f"[DIAG] Image downscale fail: {file_path.name}: {exc}")
        return None

    blob = output.getvalue()
    if len(blob) > max_bytes:
        if log_func:
            log_func(
                f"[DIAG] Downscaled image still too large: path={file_path.name} "
                f"size={len(blob)} max={max_bytes}"
            )
        return None
    data_url = _blob_to_data_url(blob, output_mime, file_name=file_path.name, log_func=log_func)
    if data_url is None or not data_image_src_looks_renderable(data_url):
        return None
    return data_url, len(blob)


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


_BASE64_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
_BASE64_EDGE_CHARS = 40


def _base64_image_region(src_value: str) -> tuple[str, str, int] | None:
    value = src_value.strip()
    lowered = value.lower()
    if lowered.startswith("data:image/"):
        comma_idx = value.find(",")
        if comma_idx < 0:
            return None
        meta = lowered[:comma_idx]
        if ";base64" not in meta:
            return None
        mime = meta.removeprefix("data:").split(";", 1)[0]
        return value, mime, comma_idx + 1

    raw_prefix = "".join(char for char in value[:24] if not char.isspace())
    if raw_prefix.startswith("/9j/"):
        mime = "image/jpeg"
    elif raw_prefix.startswith("iVBOR"):
        mime = "image/png"
    elif raw_prefix.startswith(("R0lGODlh", "R0lGODdh")):
        mime = "image/gif"
    elif raw_prefix.startswith("UklGR"):
        mime = "image/webp"
    else:
        return None
    return value, mime, 0


def _decode_base64_edge(chars: list[str]) -> bytes | None:
    raw = "".join(chars)
    padded = raw + ("=" * ((4 - len(raw) % 4) % 4))
    try:
        return base64.b64decode(padded, validate=True)
    except (ValueError, TypeError):
        return None


def _scan_base64_image_edges(value: str, start: int) -> tuple[bytes, bytes, int] | None:
    prefix_chars: list[str] = []
    suffix_chars: deque[str] = deque(maxlen=_BASE64_EDGE_CHARS)
    total_chars = 0
    padding_chars = 0
    padding_started = False

    for index in range(start, len(value)):
        char = value[index]
        if char.isspace():
            continue
        if char == "=":
            padding_started = True
            padding_chars += 1
            if padding_chars > 2:
                return None
        elif char in _BASE64_ALPHABET:
            if padding_started:
                return None
        else:
            return None
        if len(prefix_chars) < _BASE64_EDGE_CHARS:
            prefix_chars.append(char)
        suffix_chars.append(char)
        total_chars += 1

    if total_chars == 0 or total_chars % 4 == 1:
        return None
    if padding_chars and total_chars % 4 != 0:
        return None

    suffix_list = list(suffix_chars)
    suffix_global_start = total_chars - len(suffix_list)
    suffix_alignment_drop = (-suffix_global_start) % 4
    if suffix_alignment_drop:
        suffix_list = suffix_list[suffix_alignment_drop:]
    prefix_blob = _decode_base64_edge(prefix_chars)
    suffix_blob = _decode_base64_edge(suffix_list)
    if not prefix_blob or not suffix_blob:
        return None
    decoded_size = ((total_chars - padding_chars) * 6) // 8
    return prefix_blob, suffix_blob, decoded_size


def _non_base64_svg_looks_renderable(src_value: str) -> bool:
    value = src_value.strip()
    lowered = value.lower()
    comma_idx = value.find(",")
    if comma_idx < 0:
        return False
    meta = lowered[:comma_idx]
    mime = meta.removeprefix("data:").split(";", 1)[0]
    if mime != "image/svg+xml":
        return False
    payload_prefix = lowered[comma_idx + 1 : comma_idx + 257].lstrip()
    return payload_prefix.startswith(("<svg", "<?xml", "%3csvg", "%3c?xml"))


def data_image_src_looks_renderable(src_value: str) -> bool:
    region = _base64_image_region(src_value)
    if region is None:
        if src_value.strip().lower().startswith("data:image/"):
            return _non_base64_svg_looks_renderable(src_value)
        return True
    value, mime, start = region
    scanned = _scan_base64_image_edges(value, start)
    if scanned is None:
        return False
    prefix, suffix, decoded_size = scanned
    if mime == "image/jpeg":
        return prefix.startswith(b"\xff\xd8") and suffix.endswith(b"\xff\xd9")
    if mime == "image/png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n") and suffix.endswith(b"IEND\xaeB`\x82")
    if mime == "image/gif":
        return prefix.startswith((b"GIF87a", b"GIF89a")) and suffix.endswith(b";")
    if mime == "image/webp":
        return decoded_size >= 12 and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"
    if mime == "image/svg+xml":
        stripped_prefix = prefix.lstrip(b"\xef\xbb\xbf \t\r\n")
        return stripped_prefix.startswith((b"<svg", b"<?xml"))
    return decoded_size > 0


def html_node_image_srcs(raw: str) -> list[str]:
    return [match.group(3).strip() for match in IMG_SRC_PATTERN.finditer(raw)]


def html_node_has_renderable_image(raw: str) -> bool:
    return any(data_image_src_looks_renderable(src) for src in html_node_image_srcs(raw))


def html_node_has_broken_data_image(raw: str) -> bool:
    return any(
        _base64_image_region(src) is not None and not data_image_src_looks_renderable(src)
        for src in html_node_image_srcs(raw)
    )


def resolve_local_image_candidate(base_dir: Path, path_value: str) -> Path | None:
    """Resolve an image sidecar while keeping traversal and symlinks inside ``base_dir``."""
    if not path_value:
        return None
    base_root = base_dir.resolve(strict=False)
    clean_path = path_value.split("?", 1)[0].split("#", 1)[0]
    decoded = urllib.parse.unquote(clean_path)
    candidate = (base_root / decoded).resolve(strict=False)
    try:
        candidate.relative_to(base_root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def clear_inline_skip_metadata(prefix: str) -> str:
    return INLINE_SKIP_METADATA_PATTERN.sub("", prefix)


class _InlineImageIntegrityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.image_count = 0
        self.missing_src_count = 0
        self.unsupported_src_count = 0
        self.broken_data_url_count = 0
        self.inline_skip_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "img":
            self._inspect_image(attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "img":
            self._inspect_image(attrs)

    def _inspect_image(self, attrs: list[tuple[str, str | None]]) -> None:
        self.image_count += 1
        attributes = {name.lower(): value for name, value in attrs}
        has_inline_skip = "data-z2m-inline-skip" in attributes
        src = (attributes.get("src") or "").strip()
        if not src:
            self.missing_src_count += 1
            if has_inline_skip:
                self.inline_skip_count += 1
            return
        lowered = src.lower()
        if lowered.startswith("data:image/"):
            if not data_image_src_looks_renderable(src):
                self.broken_data_url_count += 1
                if has_inline_skip:
                    self.inline_skip_count += 1
            return
        if lowered.startswith(("http://", "https://")):
            return
        self.unsupported_src_count += 1
        if has_inline_skip:
            self.inline_skip_count += 1


def inspect_inline_image_integrity(html: str) -> InlineImageIntegrity:
    """Return publication integrity counts for live ``img`` elements."""
    parser = _InlineImageIntegrityParser()
    parser.feed(html)
    parser.close()
    return InlineImageIntegrity(
        image_count=parser.image_count,
        missing_src_count=parser.missing_src_count,
        unsupported_src_count=parser.unsupported_src_count,
        broken_data_url_count=parser.broken_data_url_count,
        inline_skip_count=parser.inline_skip_count,
    )


def refresh_inlined_data_urls_by_hint(
    html: str,
    *,
    base_dir: Path,
) -> tuple[str, int]:
    """Refresh stale/corrupted data URLs using ``data-z2m-src`` sidecar hints."""
    refreshed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal refreshed
        prefix = match.group(1)
        quote = match.group(2)
        src_value = match.group(3).strip()
        suffix = match.group(4)

        if not src_value.lower().startswith("data:"):
            return match.group(0)

        if (
            IMAGE_CACHE_KEY_ATTR_PATTERN.search(prefix) is not None
            and data_image_src_looks_renderable(src_value)
        ):
            clean_prefix = clear_inline_skip_metadata(prefix)
            if clean_prefix != prefix:
                return f"{clean_prefix}{quote}{src_value}{suffix}"
            return match.group(0)

        hint_match = re.search(
            r'\bdata-z2m-src\s*=\s*(["\'])([^"\']+)\1',
            prefix,
            re.IGNORECASE,
        )
        if hint_match is None:
            return match.group(0)
        candidate = resolve_local_image_candidate(base_dir, hint_match.group(2).strip())
        if candidate is None:
            return match.group(0)
        if validate_data_url(src_value, candidate):
            clean_prefix = clear_inline_skip_metadata(prefix)
            if clean_prefix != prefix:
                return f"{clean_prefix}{quote}{src_value}{suffix}"
            return match.group(0)

        refreshed_data_url = to_data_url(candidate, detect_by_signature=True, log_func=None)
        if refreshed_data_url is None:
            return match.group(0)
        if not data_image_src_looks_renderable(refreshed_data_url):
            return match.group(0)
        if not validate_data_url(refreshed_data_url, candidate):
            return match.group(0)

        refreshed += 1
        clean_prefix = clear_inline_skip_metadata(prefix)
        return f"{clean_prefix}{quote}{refreshed_data_url}{suffix}"

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
        if (
            src_value == cached_data_url
            and data_image_src_looks_renderable(src_value)
        ):
            clean_prefix = clear_inline_skip_metadata(prefix)
            if clean_prefix != prefix:
                return f"{clean_prefix}{quote}{src_value}{suffix}"
            return match.group(0)

        refreshed += 1
        clean_prefix = clear_inline_skip_metadata(prefix)
        return f"{clean_prefix}{quote}{cached_data_url}{suffix}"

    return IMG_SRC_PATTERN.sub(replace, html), refreshed


def inline_images_from_html_text(
    text: str,
    base_dir: Path,
    *,
    max_image_bytes: int | None = None,
    max_total_bytes: int | None = None,
    downscale_bytes: int | None = None,
    hard_max_image_bytes: int | None = None,
) -> tuple[InlineHtmlResult, dict[str, str]]:
    inlined_count = 0
    inlined_bytes = 0
    max_image_bytes = _effective_inline_limit(
        max_image_bytes,
        env_name=INLINE_IMAGE_MAX_BYTES_ENV,
        default=DEFAULT_INLINE_IMAGE_MAX_BYTES,
    )
    max_total_bytes = _effective_inline_limit(
        max_total_bytes,
        env_name=INLINE_IMAGE_TOTAL_MAX_BYTES_ENV,
        default=DEFAULT_INLINE_IMAGE_TOTAL_MAX_BYTES,
    )
    downscale_bytes = _effective_inline_limit(
        downscale_bytes,
        env_name=INLINE_IMAGE_DOWNSCALE_BYTES_ENV,
        default=DEFAULT_INLINE_IMAGE_DOWNSCALE_BYTES,
    )
    hard_max_image_bytes = _effective_inline_limit(
        hard_max_image_bytes,
        env_name=INLINE_IMAGE_HARD_MAX_BYTES_ENV,
        default=DEFAULT_INLINE_IMAGE_HARD_MAX_BYTES,
    )
    image_match_cursor = [0]
    image_cache: dict[str, str] = {}

    def resolve_candidate(path_value: str) -> Path | None:
        return resolve_local_image_candidate(base_dir, path_value)

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
        if max_image_bytes is not None and len(blob) > max_image_bytes:
            return prefix
        key_match = IMAGE_CACHE_KEY_ATTR_PATTERN.search(prefix)
        if key_match is None:
            digest = hashlib.sha256(blob).hexdigest()[:16]
            image_key = f"img-{match_idx}-{digest}"
            prefix = add_image_key(prefix, image_key)
        else:
            image_key = key_match.group(2).strip()
        image_cache[image_key] = data_url
        return prefix

    def skip_inline(prefix: str, reason: str, *, size: int | None = None, limit: int | None = None) -> str:
        if INLINE_SKIP_ATTR_PATTERN.search(prefix):
            return prefix
        attrs = f'data-z2m-inline-skip="{escape_html_attr_literal(reason)}"'
        if size is not None:
            attrs += f' data-z2m-inline-size="{size}"'
        if limit is not None:
            attrs += f' data-z2m-inline-limit="{limit}"'
        return re.sub(
            r"\bsrc\s*=\s*$",
            f"{attrs} src=",
            prefix,
            flags=re.IGNORECASE,
        )

    def candidate_size(candidate: Path) -> int | None:
        try:
            return candidate.stat().st_size
        except OSError:
            return None

    def inline_budget_skip(size: int) -> tuple[str, int, int] | None:
        if max_image_bytes is not None and size > max_image_bytes:
            return "image_too_large", size, max_image_bytes
        if max_total_bytes is not None and inlined_bytes + size > max_total_bytes:
            return "document_inline_budget_exceeded", size, max_total_bytes
        if hard_max_image_bytes is not None and size > hard_max_image_bytes:
            return "image_hard_limit_exceeded", size, hard_max_image_bytes
        return None

    def remaining_inline_limit() -> int | None:
        limits: list[int] = []
        if max_image_bytes is not None:
            limits.append(max_image_bytes)
        if max_total_bytes is not None:
            limits.append(max_total_bytes - inlined_bytes)
        if hard_max_image_bytes is not None:
            limits.append(hard_max_image_bytes)
        if not limits:
            return None
        return min(limits)

    def replace(match: re.Match[str]) -> str:
        nonlocal inlined_count, inlined_bytes
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
            if candidate is None:
                prefix = clear_inline_skip_metadata(prefix)
                prefix = remember_data_url(prefix, src_value, match_idx)
                if prefix != match.group(1):
                    return f"{prefix}{quote}{src_value}{suffix}"
                return match.group(0)
        elif is_inline_or_remote(src_value):
            if src_lower.startswith(("http://", "https://")):
                prefix = clear_inline_skip_metadata(prefix)
                return f"{prefix}{quote}{src_value}{suffix}"
            return match.group(0)
        else:
            candidate = resolve_candidate(src_value)
            if candidate is None:
                return match.group(0)
            prefix = add_src_hint(prefix, src_value)

        candidate_bytes = candidate_size(candidate)
        if candidate_bytes is None:
            prefix = skip_inline(prefix, "unreadable")
            return f"{prefix}{quote}{src_value}{suffix}"
        budget_skip = inline_budget_skip(candidate_bytes)
        should_downscale = budget_skip is not None or (
            downscale_bytes is not None and candidate_bytes > downscale_bytes
        )
        if should_downscale:
            downscaled = downscale_image_for_inline(
                candidate,
                max_bytes=remaining_inline_limit(),
                detect_by_signature=True,
                log_func=None,
            )
            if downscaled is not None:
                data_url, byte_count = downscaled
                prefix = clear_inline_skip_metadata(prefix)
                prefix = remember_data_url(prefix, data_url, match_idx)
                inlined_count += 1
                inlined_bytes += byte_count
                return f"{prefix}{quote}{data_url}{suffix}"
            if budget_skip is not None:
                reason, size, limit = budget_skip
                prefix = skip_inline(prefix, reason, size=size, limit=limit)
                return f"{prefix}{quote}{src_value}{suffix}"

        original_data_url = to_data_url(
            candidate,
            detect_by_signature=True,
            max_bytes=remaining_inline_limit(),
            log_func=None,
        )
        if original_data_url is None:
            return match.group(0)
        if not data_image_src_looks_renderable(original_data_url):
            return match.group(0)
        if not validate_data_url(original_data_url, candidate):
            return match.group(0)

        prefix = clear_inline_skip_metadata(prefix)
        prefix = remember_data_url(prefix, original_data_url, match_idx)
        inlined_count += 1
        inlined_bytes += candidate_bytes
        return f"{prefix}{quote}{original_data_url}{suffix}"

    inlined_html = IMG_SRC_PATTERN.sub(replace, text)
    return InlineHtmlResult(html=inlined_html, inlined_images=inlined_count), image_cache


def _effective_inline_limit(value: int | None, *, env_name: str, default: int) -> int | None:
    raw: int | str | None = value
    if raw is None:
        raw = os.environ.get(env_name)
    if raw is None:
        raw = default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = default
    return parsed if parsed > 0 else None
