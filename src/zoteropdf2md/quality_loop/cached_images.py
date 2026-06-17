"""Image-cache restoration helpers for cached repolish and review bundles."""

from __future__ import annotations

from html import unescape
from pathlib import Path
from typing import Any, Iterable
import re
import urllib.parse

from zoteropdf2md.html_images import to_data_url, validate_data_url
from zoteropdf2md.html_stages import HTML_STAGE_DIR_NAME

from .converted_runs import POLISH_STAGE, RAW_STAGE
from .run_utils import article_dir_from_stage, load_json


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
        if not src.lower().startswith("data:image/"):
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
            if src.lower().startswith("data:image/")
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
    missing_srcs = [src for src in raw_local_srcs if src not in mapping]
    if not missing_srcs:
        return mapping

    data_srcs = [src for src in img_srcs(previous_polish_html) if src.lower().startswith("data:image/")]
    if len(data_srcs) == len(raw_local_srcs):
        mapping.update({src: data_src for src, data_src in zip(raw_local_srcs, data_srcs) if src in missing_srcs})
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
        if stage_path.name in {RAW_STAGE, POLISH_STAGE} or stage_path.parent.name == HTML_STAGE_DIR_NAME:
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
    candidate = Path(decoded)
    if candidate.is_absolute():
        return [candidate]
    return [(base / decoded).resolve(strict=False) for base in search_dirs]


def cached_sidecar_image_cache(
    source_run_dir: Path,
    article: str,
    raw_html: str,
    existing: dict[str, str],
) -> tuple[dict[str, str], str | None]:
    search_dirs = article_source_image_dirs(source_run_dir, article)
    if not search_dirs:
        return {}, None
    image_cache: dict[str, str] = {}
    source_dirs: set[str] = set()
    raw_local_srcs = [src for src in img_srcs(raw_html) if not is_inline_or_remote_src(src)]
    for src in raw_local_srcs:
        if src in existing:
            continue
        for candidate in local_image_candidates_from_dirs(src, search_dirs):
            if not candidate.is_file():
                continue
            data_url = to_data_url(candidate, detect_by_signature=True, log_func=None)
            if data_url is None or not validate_data_url(data_url, candidate):
                continue
            image_cache[src] = data_url
            source_dirs.add(str(candidate.parent))
            break
    if not image_cache:
        return {}, None
    return image_cache, "; ".join(sorted(source_dirs))


def cached_data_image_cache(source_run_dir: Path, article: str, raw_html: str) -> tuple[dict[str, str], str | None]:
    raw_local_srcs = [src for src in img_srcs(raw_html) if not is_inline_or_remote_src(src)]
    expected_count = len(set(raw_local_srcs))
    collected: dict[str, str] = {}
    sources: list[str] = []
    for candidate in previous_polish_candidates(source_run_dir, article):
        if not candidate.is_file():
            continue
        previous_html = candidate.read_text(encoding="utf-8", errors="replace")
        image_cache = ordered_data_image_cache(raw_html, previous_html)
        if image_cache:
            collected.update(image_cache)
            sources.append(str(candidate))
            if len(collected) >= expected_count:
                return collected, "; ".join(sources)
    sidecar_cache, sidecar_source = cached_sidecar_image_cache(source_run_dir, article, raw_html, collected)
    if sidecar_cache:
        collected.update(sidecar_cache)
        if sidecar_source:
            sources.append(sidecar_source)
    return collected, "; ".join(sources) if sources else None


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
            if data_url is None or not validate_data_url(data_url, candidate):
                continue
            inlined += 1
            prefix = add_src_hint(match.group(1), src)
            return f"{prefix}{match.group(2)}{data_url}{match.group(4)}"
        missing.append(src)
        return match.group(0)

    copied = IMG_SRC_RE.sub(replace_src, html)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(copied, encoding="utf-8")
    return {
        "review_html": str(target_path),
        "source_html": str(source_path),
        "inlined_image_count": inlined,
        "missing_image_count": len(missing),
        "missing_image_srcs": sorted(set(missing))[:20],
    }
