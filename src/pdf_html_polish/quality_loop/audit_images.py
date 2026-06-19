"""Image-asset diagnostics shared by EN polish audit tooling."""

from __future__ import annotations

import hashlib
from html import unescape
from pathlib import Path
import re
from typing import Any
import urllib.parse

from pdf_html_polish.html_stages import is_html_stage_dir_name
from pdf_html_polish.quality_loop.audit_blocks import line_at_from_starts, line_starts


IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*(['\"])(?P<src>.*?)\1", re.IGNORECASE | re.DOTALL)


def is_inline_or_remote_src(src: str) -> bool:
    src = src.strip()
    if not src or src.startswith("#"):
        return True
    lower = src.lower()
    if lower.startswith(("data:", "http://", "https://", "blob:", "cid:")):
        return True
    parsed = urllib.parse.urlsplit(src)
    return bool(parsed.scheme and parsed.scheme.lower() not in {"file"})


def local_image_candidates(html_path: Path, src: str) -> list[Path]:
    clean = src.strip().split("?", 1)[0].split("#", 1)[0]
    if not clean:
        return []
    parsed = urllib.parse.urlsplit(clean)
    path_value = parsed.path if parsed.scheme.lower() == "file" else clean
    decoded = urllib.parse.unquote(path_value)
    if re.match(r"^/[A-Za-z]:/", decoded):
        decoded = decoded[1:]
    candidate = Path(decoded)
    if candidate.is_absolute():
        return [candidate]

    search_dirs = [html_path.parent]
    if is_html_stage_dir_name(html_path.parent.name):
        search_dirs.append(html_path.parent.parent)
    return [(base / decoded).resolve(strict=False) for base in search_dirs]


def missing_local_images(html_path: Path, html: str) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    seen: set[str] = set()
    starts = line_starts(html)
    for match in IMG_SRC_RE.finditer(html):
        src = unescape(match.group("src")).strip()
        if is_inline_or_remote_src(src):
            continue
        candidates = local_image_candidates(html_path, src)
        if any(candidate.is_file() for candidate in candidates):
            continue
        key = src
        if key in seen:
            continue
        seen.add(key)
        missing.append(
            {
                "src": src,
                "line": line_at_from_starts(starts, match.start()),
                "searched": [str(candidate) for candidate in candidates],
            }
        )
    return missing


def image_identity_key(html_path: Path, src: str) -> str | None:
    src = unescape(src).strip()
    if not src:
        return None
    if src.lower().startswith("data:image/"):
        return "data:" + hashlib.sha256(src.encode("utf-8", errors="replace")).hexdigest()
    if is_inline_or_remote_src(src):
        return None
    for candidate in local_image_candidates(html_path, src):
        if not candidate.is_file():
            continue
        try:
            return "file:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError:
            continue
    return f"src:{src}"
