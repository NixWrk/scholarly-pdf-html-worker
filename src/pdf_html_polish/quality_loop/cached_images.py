"""Image-cache restoration helpers for cached repolish and review bundles."""

from __future__ import annotations

from html import unescape
import os
from pathlib import Path
from typing import Any, Callable, Iterable
import re
import urllib.parse

from pdf_html_polish.artifact_integrity import read_bytes_with_fingerprint
from pdf_html_polish.atomic_io import write_text_atomic
from pdf_html_polish.html_images import (
    DEFAULT_INLINE_IMAGE_DOCUMENT_DOWNSCALE_BYTES,
    INLINE_IMAGE_DOCUMENT_DOWNSCALE_BYTES_ENV,
    data_image_src_looks_renderable,
    downscale_image_for_inline,
    inspect_inline_image_integrity,
    to_data_url,
    validate_data_url,
)
from pdf_html_polish.html_stages import is_html_stage_dir_name

from .converted_runs import POLISH_STAGE, RAW_STAGE
from .run_utils import article_dir_from_stage, load_json


SnapshotFile = Callable[[Path, str], Path]
IMG_SRC_RE = re.compile(r"(<img\b[^>]*?\s+src\s*=\s*)(['\"])(?P<src>.*?)(\2)", re.IGNORECASE | re.DOTALL)
DATA_Z2M_SRC_RE = re.compile(r"\bdata-z2m-src\s*=\s*(['\"])(?P<src>.*?)\1", re.IGNORECASE | re.DOTALL)
FIGURE_UNIT_RE = re.compile(
    r'<div\b(?=[^>]*\bid\s*=\s*(["\'])(?P<id>fig-\d{1,3})\1)'
    r'(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]*?</div>',
    re.IGNORECASE,
)


def is_inline_or_remote_src(src: str) -> bool:
    src = src.strip()
    if not src or src.startswith("#"):
        return True
    lower = src.lower()
    return lower.startswith(("data:", "http://", "https://", "blob:", "cid:"))


def img_srcs(html: str) -> list[str]:
    return [unescape(match.group("src")).strip() for match in IMG_SRC_RE.finditer(html)]


def source_hinted_data_images(html: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for match in IMG_SRC_RE.finditer(html):
        src = unescape(match.group("src")).strip()
        if not src.lower().startswith("data:image/") or not data_image_src_looks_renderable(src):
            continue
        prefix = match.group(1)
        hint = DATA_Z2M_SRC_RE.search(prefix)
        if hint is not None:
            mapping[unescape(hint.group("src")).strip()] = src
    return mapping


def figure_unit_data_image_cache(raw_html: str, previous_polish_html: str) -> dict[str, str]:
    previous_by_figure: dict[str, list[str]] = {}
    for unit_match in FIGURE_UNIT_RE.finditer(previous_polish_html):
        data_srcs = [
            src
            for src in img_srcs(unit_match.group(0))
            if (
                src.lower().startswith("data:image/") and data_image_src_looks_renderable(src)
            )
        ]
        if data_srcs:
            previous_by_figure[unit_match.group("id").lower()] = data_srcs

    mapping: dict[str, str] = {}
    if not previous_by_figure:
        return mapping

    for unit_match in FIGURE_UNIT_RE.finditer(raw_html):
        raw_local_srcs = [
            src
            for src in img_srcs(unit_match.group(0))
            if not is_inline_or_remote_src(src)
        ]
        if not raw_local_srcs:
            continue
        data_srcs = previous_by_figure.get(unit_match.group("id").lower()) or []
        if len(data_srcs) != len(raw_local_srcs):
            continue
        mapping.update(zip(raw_local_srcs, data_srcs))
    return mapping


def ordered_data_image_cache(raw_html: str, previous_polish_html: str) -> dict[str, str]:
    """Map raw local image refs to data URLs from an older polish copy."""

    raw_local_srcs = [src for src in img_srcs(raw_html) if not is_inline_or_remote_src(src)]
    if not raw_local_srcs:
        return {}

    hinted = source_hinted_data_images(previous_polish_html)
    mapping = {src: hinted[src] for src in raw_local_srcs if src in hinted}
    figure_scoped = figure_unit_data_image_cache(raw_html, previous_polish_html)
    mapping.update({src: figure_scoped[src] for src in raw_local_srcs if src not in mapping and src in figure_scoped})
    missing_srcs = list(dict.fromkeys(src for src in raw_local_srcs if src not in mapping))
    if len(missing_srcs) == 1:
        claimed_data_urls = set(mapping.values())
        unclaimed_data_urls = list(
            dict.fromkeys(
                src
                for src in img_srcs(previous_polish_html)
                if src.lower().startswith("data:image/")
                and data_image_src_looks_renderable(src)
                and src not in claimed_data_urls
            )
        )
        if len(unclaimed_data_urls) == 1:
            mapping[missing_srcs[0]] = unclaimed_data_urls[0]
    return mapping


def escape_html_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def add_src_hint(prefix: str, source_src: str) -> str:
    if DATA_Z2M_SRC_RE.search(prefix):
        return prefix
    escaped = escape_html_attr(source_src)
    return re.sub(r"\bsrc\s*=\s*$", f'data-z2m-src="{escaped}" src=', prefix, flags=re.IGNORECASE)


def apply_data_image_cache(html: str, image_cache: dict[str, str]) -> tuple[str, int]:
    if not image_cache:
        return html, 0
    replacements = 0

    def replace_src(match: re.Match[str]) -> str:
        nonlocal replacements
        src = unescape(match.group("src")).strip()
        data_url = image_cache.get(src)
        if data_url is None:
            return match.group(0)
        if not data_url.lower().startswith("data:image/") or not data_image_src_looks_renderable(data_url):
            return match.group(0)
        replacements += 1
        prefix = add_src_hint(match.group(1), src)
        return f"{prefix}{match.group(2)}{data_url}{match.group(4)}"

    return IMG_SRC_RE.sub(replace_src, html), replacements


def manifest_article_for(manifest: dict[str, Any], article: str) -> dict[str, Any] | None:
    for item in manifest.get("articles") or []:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("article_id") or item.get("article") or "") == article
            or str(item.get("article") or "") == article
        ):
            return item
    return None


def previous_polish_candidates(source_run_dir: Path, article: str) -> list[Path]:
    candidates: list[Path] = []
    visited: set[Path] = set()

    def visit(run_dir: Path) -> None:
        run_dir = run_dir.resolve(strict=False)
        if run_dir in visited:
            return
        visited.add(run_dir)
        manifest = load_json(run_dir / "manifest.json", default={})
        item = manifest_article_for(manifest, article)
        if item:
            for key in ("source_polish_path", "polish_stage_path", "polish_path"):
                value = item.get(key)
                if value:
                    candidates.append(Path(str(value)).resolve(strict=False))
        direct_polish = run_dir / "polish" / f"{article}.{POLISH_STAGE}"
        candidates.append(direct_polish.resolve(strict=False))
        review_polish = run_dir / "audit_tree" / article / POLISH_STAGE
        candidates.append(review_polish.resolve(strict=False))
        nested = manifest.get("source_run_dir")
        if nested:
            visit(Path(str(nested)))

    visit(source_run_dir)
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def article_source_image_dirs(source_run_dir: Path, article: str) -> list[Path]:
    dirs: list[Path] = []
    visited: set[Path] = set()

    def add_stage_related_dirs(value: Any) -> None:
        if not value:
            return
        stage_path = Path(str(value)).resolve(strict=False)
        if stage_path.name in {RAW_STAGE, POLISH_STAGE} or is_html_stage_dir_name(stage_path.parent.name):
            article_dir = article_dir_from_stage(stage_path)
        else:
            article_dir = stage_path.parent
        dirs.append(article_dir)

        parts = list(article_dir.parts)
        if "source_exports" not in parts:
            return
        idx = parts.index("source_exports")
        converted_article_dir = Path(*parts[:idx], "converted", *parts[idx + 1 :])
        dirs.append(converted_article_dir)
        if converted_article_dir.is_dir():
            for child in converted_article_dir.iterdir():
                if child.is_dir() and not child.name.startswith("_"):
                    dirs.append(child)

    def visit(run_dir: Path) -> None:
        run_dir = run_dir.resolve(strict=False)
        if run_dir in visited:
            return
        visited.add(run_dir)
        manifest = load_json(run_dir / "manifest.json", default={})
        item = manifest_article_for(manifest, article)
        if item:
            for key in ("raw_stage_path", "source_polish_path", "polish_stage_path", "polish_path"):
                add_stage_related_dirs(item.get(key))
        nested = manifest.get("source_run_dir")
        if nested:
            visit(Path(str(nested)))

    visit(source_run_dir)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in dirs:
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def local_image_candidates_from_dirs(src: str, search_dirs: Iterable[Path]) -> list[Path]:
    clean = src.strip().split("?", 1)[0].split("#", 1)[0]
    if not clean:
        return []
    parsed = urllib.parse.urlsplit(clean)
    path_value = parsed.path if parsed.scheme.lower() == "file" else clean
    decoded = urllib.parse.unquote(path_value)
    if re.match(r"^/[A-Za-z]:/", decoded):
        decoded = decoded[1:]
    candidates: list[Path] = []
    for base in search_dirs:
        base_root = base.resolve(strict=False)
        candidate = (base_root / decoded).resolve(strict=False)
        try:
            candidate.relative_to(base_root)
        except ValueError:
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def cached_sidecar_image_cache(
    source_run_dir: Path,
    article: str,
    raw_html: str,
    existing: dict[str, str],
    *,
    snapshot_file: SnapshotFile,
    document_downscale_bytes: int | None = None,
) -> tuple[dict[str, str], str | None, str | None]:
    search_dirs = article_source_image_dirs(source_run_dir, article)
    if not search_dirs:
        return {}, None, None
    image_cache: dict[str, str] = {}
    source_files: set[str] = set()
    source_dirs: set[str] = set()
    raw_local_srcs = [src for src in img_srcs(raw_html) if not is_inline_or_remote_src(src)]
    selected: list[tuple[str, Path, Path]] = []
    selected_srcs: set[str] = set()
    for src in raw_local_srcs:
        if src in existing or src in selected_srcs:
            continue
        for candidate in local_image_candidates_from_dirs(src, search_dirs):
            if not candidate.is_file():
                continue
            snapshotted = snapshot_file(candidate, "image_sidecar")
            selected.append((src, snapshotted, candidate))
            selected_srcs.add(src)
            break

    soft_budget = _effective_document_downscale_bytes(document_downscale_bytes)
    total_bytes = sum(path.stat().st_size for _src, path, _origin in selected)
    per_image_target = (
        max(64 * 1024, soft_budget // len(selected))
        if soft_budget is not None and selected and total_bytes > soft_budget
        else None
    )
    for src, snapshotted, candidate in selected:
        downscaled = (
            downscale_image_for_inline(
                snapshotted,
                max_bytes=per_image_target,
                detect_by_signature=True,
                log_func=None,
            )
            if per_image_target is not None
            and snapshotted.stat().st_size > per_image_target
            else None
        )
        data_url = (
            downscaled[0]
            if downscaled is not None
            else to_data_url(snapshotted, detect_by_signature=True, log_func=None)
        )
        if data_url is None or not data_image_src_looks_renderable(data_url):
            continue
        if downscaled is None and not validate_data_url(data_url, snapshotted):
            continue
        image_cache[src] = data_url
        source_files.add(str(snapshotted))
        source_dirs.add(str(candidate.parent.resolve(strict=False)))
    if not image_cache:
        return {}, None, None
    return image_cache, "; ".join(sorted(source_files)), "; ".join(sorted(source_dirs))


def _effective_document_downscale_bytes(value: int | None) -> int | None:
    raw: int | str | None = value
    if raw is None:
        raw = os.environ.get(INLINE_IMAGE_DOCUMENT_DOWNSCALE_BYTES_ENV)
    if raw is None:
        raw = DEFAULT_INLINE_IMAGE_DOCUMENT_DOWNSCALE_BYTES
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = DEFAULT_INLINE_IMAGE_DOCUMENT_DOWNSCALE_BYTES
    return parsed if parsed > 0 else None


def cached_data_image_cache(
    source_run_dir: Path,
    article: str,
    raw_html: str,
    *,
    snapshot_file: SnapshotFile,
    document_downscale_bytes: int | None = None,
) -> tuple[dict[str, str], str | None, str | None]:
    raw_local_srcs = [src for src in img_srcs(raw_html) if not is_inline_or_remote_src(src)]
    expected_count = len(set(raw_local_srcs))
    collected, sidecar_source, sidecar_origin_source = cached_sidecar_image_cache(
        source_run_dir,
        article,
        raw_html,
        {},
        snapshot_file=snapshot_file,
        document_downscale_bytes=document_downscale_bytes,
    )
    sources: list[str] = []
    origin_sources: list[str] = []
    if sidecar_source:
        sources.append(sidecar_source)
    if sidecar_origin_source:
        origin_sources.append(sidecar_origin_source)
    if len(collected) >= expected_count:
        return collected, "; ".join(sources), "; ".join(origin_sources)
    for candidate in previous_polish_candidates(source_run_dir, article):
        if not candidate.is_file():
            continue
        snapshotted = snapshot_file(candidate, "image_previous_polish")
        stable = read_bytes_with_fingerprint(snapshotted, reject_symlink=True)
        if stable is None:
            raise ValueError(f"Snapshotted previous polish is unreadable: {snapshotted}")
        try:
            previous_html = stable[0].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Snapshotted previous polish is not UTF-8: {snapshotted}") from exc
        image_cache = ordered_data_image_cache(raw_html, previous_html)
        if image_cache:
            collected.update(
                (src, data_url)
                for src, data_url in image_cache.items()
                if src not in collected
            )
            sources.append(str(snapshotted))
            origin_sources.append(str(candidate.resolve(strict=False)))
            if len(collected) >= expected_count:
                return collected, "; ".join(sources), "; ".join(origin_sources)
    return (
        collected,
        "; ".join(sources) if sources else None,
        "; ".join(origin_sources) if origin_sources else None,
    )


def review_html_image_search_dirs(stage_path: Path) -> list[Path]:
    article_dir = article_dir_from_stage(stage_path)
    candidates = [
        stage_path.parent,
        article_dir,
        article_dir / "images",
        article_dir / "figures",
        article_dir / "assets",
    ]
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    return deduped


def copy_review_html_with_inline_images(source_path: Path, target_path: Path) -> dict[str, Any]:
    html = source_path.read_text(encoding="utf-8", errors="replace")
    search_dirs = review_html_image_search_dirs(source_path)
    inlined = 0
    missing: list[str] = []

    def replace_src(match: re.Match[str]) -> str:
        nonlocal inlined
        src = unescape(match.group("src")).strip()
        if is_inline_or_remote_src(src):
            return match.group(0)
        for candidate in local_image_candidates_from_dirs(src, search_dirs):
            if not candidate.is_file():
                continue
            data_url = to_data_url(candidate, detect_by_signature=True, log_func=None)
            if (
                data_url is None
                or not data_image_src_looks_renderable(data_url)
                or not validate_data_url(data_url, candidate)
            ):
                continue
            inlined += 1
            prefix = add_src_hint(match.group(1), src)
            return f"{prefix}{match.group(2)}{data_url}{match.group(4)}"
        missing.append(src)
        return match.group(0)

    copied = IMG_SRC_RE.sub(replace_src, html)
    integrity = inspect_inline_image_integrity(copied)
    if not integrity.publishable:
        raise ValueError(
            "Review HTML image integrity check failed: "
            f"source={source_path} missing={integrity.missing_src_count} "
            f"unsupported={integrity.unsupported_src_count} "
            f"broken={integrity.broken_data_url_count} skips={integrity.inline_skip_count}"
        )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(target_path, copied)
    return {
        "review_html": str(target_path),
        "source_html": str(source_path),
        "inlined_image_count": inlined,
        "missing_image_count": len(missing),
        "missing_image_srcs": sorted(set(missing))[:20],
    }
