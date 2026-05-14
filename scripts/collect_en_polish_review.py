#!/usr/bin/env python
"""Collect self-contained EN polish HTML copies for manual review."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
import json
import sys
from pathlib import Path
import re
import urllib.parse
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.single_file_html import _to_data_url, _validate_data_url  # noqa: E402


POLISH_STAGE = "02.en.polish.html"
IMG_SRC_RE = re.compile(r"(<img\b[^>]*?\bsrc\s*=\s*)(['\"])(?P<src>.*?)(\2)", re.IGNORECASE | re.DOTALL)


@dataclass
class ReviewCopy:
    article: str
    source_html: str
    review_html: str
    inlined_images: list[str] = field(default_factory=list)
    missing_images: list[dict[str, object]] = field(default_factory=list)


def _slug(value: str, *, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned or "article")[:max_len]


def _is_inline_or_remote_src(src: str) -> bool:
    src = src.strip()
    if not src or src.startswith("#"):
        return True
    lower = src.lower()
    if lower.startswith(("data:", "http://", "https://", "blob:", "cid:")):
        return True
    parsed = urllib.parse.urlsplit(src)
    return bool(parsed.scheme and parsed.scheme.lower() not in {"file"})


def _local_image_candidates(html_path: Path, src: str) -> list[Path]:
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
    if html_path.parent.name == "_z2m_stages":
        search_dirs.append(html_path.parent.parent)
    return [(base / decoded).resolve(strict=False) for base in search_dirs]


def _resolve_local_image(html_path: Path, src: str) -> Path | None:
    for candidate in _local_image_candidates(html_path, src):
        if candidate.is_file():
            return candidate
    return None


def _escape_html_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _add_src_hint(prefix: str, hint_path: str) -> str:
    if re.search(r'\bdata-z2m-src\s*=', prefix, re.IGNORECASE):
        return prefix
    escaped_hint = _escape_html_attr(hint_path)
    return re.sub(
        r"\bsrc\s*=\s*$",
        f'data-z2m-src="{escaped_hint}" src=',
        prefix,
        flags=re.IGNORECASE,
    )


def _inline_image_assets(polish_path: Path, target_dir: Path) -> ReviewCopy:
    article_dir = polish_path.parent.parent if polish_path.parent.name == "_z2m_stages" else polish_path.parent
    article = article_dir.name
    html = polish_path.read_text(encoding="utf-8", errors="replace")
    inlined_images: list[str] = []
    missing_images: list[dict[str, object]] = []

    def replace_src(match: re.Match[str]) -> str:
        prefix = match.group(1)
        quote = match.group(2)
        src = unescape(match.group("src")).strip()
        suffix = match.group(4)
        if _is_inline_or_remote_src(src):
            return match.group(0)

        source = _resolve_local_image(polish_path, src)
        if source is None:
            missing_images.append(
                {
                    "src": src,
                    "searched": [str(candidate) for candidate in _local_image_candidates(polish_path, src)],
                }
            )
            return match.group(0)

        data_url = _to_data_url(source, detect_by_signature=True, log_func=None)
        if data_url is None or not _validate_data_url(data_url, source):
            missing_images.append(
                {
                    "src": src,
                    "source": str(source),
                    "error": "could not encode image as data URL",
                }
            )
            return match.group(0)

        inlined_images.append(source.name)
        hinted_prefix = _add_src_hint(prefix, src)
        return f"{hinted_prefix}{quote}{data_url}{suffix}"

    target_dir.mkdir(parents=True, exist_ok=True)
    rewritten_html = IMG_SRC_RE.sub(replace_src, html)
    review_html_path = target_dir / POLISH_STAGE
    review_html_path.write_text(rewritten_html, encoding="utf-8")
    return ReviewCopy(
        article=article,
        source_html=str(polish_path),
        review_html=str(review_html_path),
        inlined_images=sorted(set(inlined_images)),
        missing_images=missing_images,
    )


def find_polish_files(roots: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.is_file() and root.name == POLISH_STAGE:
            found.add(root.resolve(strict=False))
        elif root.exists():
            found.update(path.resolve(strict=False) for path in root.rglob(POLISH_STAGE))
    return sorted(found, key=str)


def collect_review_set(roots: list[Path], out_dir: Path) -> dict[str, object]:
    polish_files = find_polish_files(roots)
    out_dir.mkdir(parents=True, exist_ok=True)
    copies: list[ReviewCopy] = []
    for index, polish_path in enumerate(polish_files, start=1):
        article_dir = polish_path.parent.parent if polish_path.parent.name == "_z2m_stages" else polish_path.parent
        target_dir = out_dir / f"{index:02d}_{_slug(article_dir.name)}"
        copies.append(_inline_image_assets(polish_path, target_dir))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [str(root) for root in roots],
        "out_dir": str(out_dir),
        "article_count": len(copies),
        "inlined_image_count": sum(len(copy.inlined_images) for copy in copies),
        "missing_image_count": sum(len(copy.missing_images) for copy in copies),
        "articles": [asdict(copy) for copy in copies],
    }
    (out_dir / "index.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="Root directories or 02.en.polish.html files to collect.",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output review directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect_review_set(args.roots, args.out)
    print(
        "Collected "
        f"{report['article_count']} EN polish file(s), "
        f"inlined {report['inlined_image_count']} image(s), "
        f"missing {report['missing_image_count']} image(s)."
    )
    print(f"Wrote {args.out / 'index.json'}")
    return 1 if report["missing_image_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
