#!/usr/bin/env python
"""Regenerate ``02.en.polish.html`` from existing ``01.en.raw.html`` stages.

This helper intentionally uses only raw HTML stages.  It does not rebuild or
pass the PDF-derived citation profile used by the production pipeline, and it
does not consume Zotero/pdf.js overlay JSON.  Use it for raw-HTML-only polish
checks such as text cleanup, float recovery, and math/layout behavior.

For citation/internal-link quality checks, use ``scripts/pdf_profile_lab.py``
with ``_source_filename_map.csv`` so each raw stage is paired with its source
PDF and rebuilt citation profile.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
import json
from pathlib import Path
import re
import sys
import urllib.parse
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.single_file_html import (  # noqa: E402
    _to_data_url,
    _validate_data_url,
    polish_html_document,
)


RAW_STAGE = "01.en.raw.html"
POLISH_STAGE = "02.en.polish.html"
IMG_SRC_RE = re.compile(r"(<img\b[^>]*?\bsrc\s*=\s*)(['\"])(?P<src>.*?)(\2)", re.IGNORECASE | re.DOTALL)


@dataclass
class RepolishResult:
    article: str
    raw_stage: str
    polish_stage: str
    changed: bool
    inlined_images: list[str] = field(default_factory=list)
    missing_images: list[dict[str, object]] = field(default_factory=list)


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
    if re.search(r"\bdata-z2m-src\s*=", prefix, re.IGNORECASE):
        return prefix
    escaped_hint = _escape_html_attr(hint_path)
    return re.sub(
        r"\bsrc\s*=\s*$",
        f'data-z2m-src="{escaped_hint}" src=',
        prefix,
        flags=re.IGNORECASE,
    )


def _inline_local_images(html_path: Path, html: str) -> tuple[str, list[str], list[dict[str, object]]]:
    inlined_images: list[str] = []
    missing_images: list[dict[str, object]] = []

    def replace_src(match: re.Match[str]) -> str:
        prefix = match.group(1)
        quote = match.group(2)
        src = unescape(match.group("src")).strip()
        suffix = match.group(4)
        if _is_inline_or_remote_src(src):
            return match.group(0)

        source = _resolve_local_image(html_path, src)
        if source is None:
            missing_images.append(
                {
                    "src": src,
                    "searched": [str(candidate) for candidate in _local_image_candidates(html_path, src)],
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

    rewritten = IMG_SRC_RE.sub(replace_src, html)
    return rewritten, sorted(set(inlined_images)), missing_images


def find_raw_files(roots: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.is_file() and root.name == RAW_STAGE:
            found.add(root.resolve(strict=False))
        elif root.exists():
            found.update(path.resolve(strict=False) for path in root.rglob(RAW_STAGE))
    return sorted(found, key=str)


def repolish_file(
    raw_path: Path,
    *,
    table_caption_language: str = "en",
    polish_language: str | None = None,
    inline_images: bool = True,
) -> RepolishResult:
    raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
    polished = polish_html_document(
        raw_html,
        table_caption_language=table_caption_language,
        enable_citation_linkify=True,
        polish_language=polish_language,
    )

    polish_path = raw_path.parent / POLISH_STAGE
    inlined_images: list[str] = []
    missing_images: list[dict[str, object]] = []
    if inline_images:
        polished, inlined_images, missing_images = _inline_local_images(polish_path, polished)

    previous = polish_path.read_text(encoding="utf-8", errors="replace") if polish_path.is_file() else None
    changed = previous != polished
    polish_path.write_text(polished, encoding="utf-8")

    article_dir = raw_path.parent.parent if raw_path.parent.name == "_z2m_stages" else raw_path.parent
    return RepolishResult(
        article=article_dir.name,
        raw_stage=str(raw_path),
        polish_stage=str(polish_path),
        changed=changed,
        inlined_images=inlined_images,
        missing_images=missing_images,
    )


def repolish_roots(
    roots: list[Path],
    *,
    table_caption_language: str = "en",
    polish_language: str | None = None,
    inline_images: bool = True,
) -> dict[str, object]:
    results = [
        repolish_file(
            raw_path,
            table_caption_language=table_caption_language,
            polish_language=polish_language,
            inline_images=inline_images,
        )
        for raw_path in find_raw_files(roots)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": f"{RAW_STAGE} -> {POLISH_STAGE}",
        "roots": [str(root) for root in roots],
        "table_caption_language": table_caption_language,
        "polish_language": polish_language or table_caption_language,
        "article_count": len(results),
        "changed_count": sum(1 for result in results if result.changed),
        "inlined_image_count": sum(len(result.inlined_images) for result in results),
        "missing_image_count": sum(len(result.missing_images) for result in results),
        "articles": [asdict(result) for result in results],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="Root directories or direct 01.en.raw.html files to repolish.",
    )
    parser.add_argument("--out-report", type=Path, help="Optional JSON report path.")
    parser.add_argument(
        "--table-caption-language",
        choices=("en", "ru"),
        default="en",
        help="Caption language mode for polish_html_document.",
    )
    parser.add_argument(
        "--polish-language",
        choices=("en", "ru"),
        help="Language policy for language-specific polish repairs; defaults to --table-caption-language.",
    )
    parser.add_argument(
        "--no-inline-images",
        action="store_true",
        help="Do not inline local image files into regenerated polish HTML.",
    )
    parser.add_argument(
        "--fail-on-missing-images",
        action="store_true",
        help="Exit with status 1 when any local image reference cannot be inlined.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = repolish_roots(
        args.roots,
        table_caption_language=args.table_caption_language,
        polish_language=args.polish_language,
        inline_images=not args.no_inline_images,
    )
    print(
        "Repolished EN stages: "
        f"articles={report['article_count']} "
        f"changed={report['changed_count']} "
        f"inlined_images={report['inlined_image_count']} "
        f"missing_images={report['missing_image_count']}"
    )
    if args.out_report is not None:
        args.out_report.parent.mkdir(parents=True, exist_ok=True)
        args.out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.out_report}")
    if args.fail_on_missing_images and report["missing_image_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
