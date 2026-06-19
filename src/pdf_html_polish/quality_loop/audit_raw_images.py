from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote, urlsplit

from pdf_html_polish.quality_loop.audit_raw_blocks import Defect


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
IMG_SRC_RE = re.compile(
    r"<img\b[^>]*\bsrc\s*=\s*(?:(?P<quote>['\"])(?P<quoted>.*?)(?P=quote)|(?P<bare>[^\s>]+))",
    re.IGNORECASE | re.DOTALL,
)


def image_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in IMG_SRC_RE.finditer(text):
        refs.append(match.group("quoted") or match.group("bare") or "")
    return refs


def sidecar_images(article_dir: Path, stage_dir: Path) -> set[Path]:
    images: set[Path] = set()
    for base in {article_dir, stage_dir}:
        if not base.exists():
            continue
        for child in base.iterdir():
            if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                images.add(child.resolve(strict=False))
    return images


def resolve_image_ref(src: str, article_dir: Path, stage_dir: Path) -> tuple[str, Path | None]:
    parsed = urlsplit(src)
    if parsed.scheme in {"http", "https", "data"}:
        return parsed.scheme, None
    clean = unquote(parsed.path).replace("\\", "/")
    candidates = [stage_dir / clean, article_dir / clean]
    for candidate in candidates:
        if candidate.exists():
            return "local", candidate.resolve(strict=False)
    return "missing", (article_dir / clean).resolve(strict=False)


def image_summary(path: Path, text: str) -> tuple[dict[str, Any], Defect | None]:
    stage_dir = path.parent
    article_dir = stage_dir.parent
    refs = image_refs(text)
    local_resolved: set[Path] = set()
    remote_refs = 0
    data_refs = 0
    missing: list[str] = []

    for src in refs:
        kind, resolved = resolve_image_ref(src, article_dir, stage_dir)
        if kind == "local" and resolved is not None:
            local_resolved.add(resolved)
        elif kind == "data":
            data_refs += 1
        elif kind in {"http", "https"}:
            remote_refs += 1
        else:
            missing.append(src)

    sidecars = sidecar_images(article_dir, stage_dir)
    unused = sorted(str(path) for path in sidecars.difference(local_resolved))
    summary = {
        "img_tags": len(IMG_TAG_RE.findall(text)),
        "image_srcs": len(refs),
        "local_sidecar_files": len(sidecars),
        "local_refs_resolved": len(local_resolved),
        "remote_refs": remote_refs,
        "data_uri_refs": data_refs,
        "missing_refs": missing[:20],
        "unused_sidecars": unused[:20],
    }
    if missing:
        return summary, Defect(
            id="R03",
            check="Count <img> tags and sidecar image files",
            severity="error",
            snippet=missing[0],
            line=None,
            hypothesis="Marker referenced an image that is not present beside the article or stage artifact.",
            proposed_fix_layer="Marker image extraction or staging",
            regression_test="Audit image refs and sidecars for the full EN raw control corpus.",
            extra={"missing_refs": missing[:20], "missing_count": len(missing)},
        )
    return summary, None
