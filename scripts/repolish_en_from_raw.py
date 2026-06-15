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
from collections import Counter
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

from zoteropdf2md.html_images import to_data_url as _to_data_url  # noqa: E402
from zoteropdf2md.html_images import validate_data_url as _validate_data_url  # noqa: E402
from zoteropdf2md.html_stages import (  # noqa: E402
    HTML_STAGE_DIR_NAME,
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    article_dir_from_html_stage,
)
from zoteropdf2md.single_file_html import polish_html_document  # noqa: E402
from zoteropdf2md.polish_language import resolve_document_polish_language  # noqa: E402
from zoteropdf2md.quality_loop.cached_images import (  # noqa: E402
    apply_data_image_cache as _apply_data_image_cache,
    cached_data_image_cache as _cached_data_image_cache,
    ordered_data_image_cache as _ordered_data_image_cache,
)


RAW_STAGE = RAW_STAGE_NAME
POLISH_STAGE = POLISH_STAGE_NAME
IMG_SRC_RE = re.compile(r"(<img\b[^>]*?\s+src\s*=\s*)(['\"])(?P<src>.*?)(\2)", re.IGNORECASE | re.DOTALL)


@dataclass
class RepolishResult:
    article: str
    raw_stage: str
    polish_stage: str
    changed: bool
    requested_polish_language: str = "en"
    polish_language: str = "en"
    target_language: str = "en"
    detected_language: str = "unknown"
    language_confidence: float = 0.0
    language_reason: str = ""
    language_gate_reason: str = ""
    skipped: bool = False
    skip_reason: str = ""
    inlined_images: list[str] = field(default_factory=list)
    missing_images: list[dict[str, object]] = field(default_factory=list)
    restored_images: int = 0
    image_cache_source: str = ""


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
    if html_path.parent.name == HTML_STAGE_DIR_NAME:
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
    target_language: str = "en",
    skip_non_target_language: bool = False,
    skip_unknown_language: bool = False,
    inline_images: bool = True,
    image_cache_source_run: Path | None = None,
) -> RepolishResult:
    raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
    language_decision = resolve_document_polish_language(
        raw_html,
        table_caption_language=table_caption_language,
        polish_language=polish_language,
        target_language=target_language,
        skip_non_target_language=skip_non_target_language,
        skip_unknown_language=skip_unknown_language,
    )
    language_fields = language_decision.to_flat_report_fields()
    polish_path = raw_path.parent / POLISH_STAGE
    article_dir = article_dir_from_html_stage(raw_path)
    previous = polish_path.read_text(encoding="utf-8", errors="replace") if polish_path.is_file() else None
    if language_decision.should_skip:
        return RepolishResult(
            article=article_dir.name,
            raw_stage=str(raw_path),
            polish_stage=str(polish_path),
            changed=False,
            requested_polish_language=str(language_fields["requested_polish_language"]),
            polish_language=str(language_fields["polish_language"]),
            target_language=str(language_fields["target_language"]),
            detected_language=str(language_fields["detected_language"]),
            language_confidence=float(language_fields["language_confidence"]),
            language_reason=str(language_fields["language_reason"]),
            language_gate_reason=str(language_fields["language_gate_reason"]),
            skipped=True,
            skip_reason=str(language_fields["skip_reason"]),
        )

    data_image_cache: dict[str, str] = {}
    image_cache_sources: list[str] = []
    if inline_images and previous:
        previous_cache = _ordered_data_image_cache(raw_html, previous)
        if previous_cache:
            data_image_cache.update(previous_cache)
            image_cache_sources.append(str(polish_path))
    if inline_images and image_cache_source_run is not None:
        source_cache, source = _cached_data_image_cache(image_cache_source_run, article_dir.name, raw_html)
        if source_cache:
            before = len(data_image_cache)
            for src, data_url in source_cache.items():
                data_image_cache.setdefault(src, data_url)
            if len(data_image_cache) > before:
                image_cache_sources.append(source or str(image_cache_source_run))

    polished = polish_html_document(
        raw_html,
        table_caption_language=table_caption_language,
        enable_citation_linkify=True,
        polish_language=language_decision.selected_polish_language,
    )

    inlined_images: list[str] = []
    missing_images: list[dict[str, object]] = []
    restored_images = 0
    if inline_images:
        polished, restored_images = _apply_data_image_cache(polished, data_image_cache)
        polished, inlined_images, missing_images = _inline_local_images(polish_path, polished)

    changed = previous != polished
    polish_path.write_text(polished, encoding="utf-8")

    return RepolishResult(
        article=article_dir.name,
        raw_stage=str(raw_path),
        polish_stage=str(polish_path),
        changed=changed,
        requested_polish_language=str(language_fields["requested_polish_language"]),
        polish_language=str(language_fields["polish_language"]),
        target_language=str(language_fields["target_language"]),
        detected_language=str(language_fields["detected_language"]),
        language_confidence=float(language_fields["language_confidence"]),
        language_reason=str(language_fields["language_reason"]),
        language_gate_reason=str(language_fields["language_gate_reason"]),
        inlined_images=inlined_images,
        missing_images=missing_images,
        restored_images=restored_images,
        image_cache_source="; ".join(image_cache_sources),
    )


def repolish_roots(
    roots: list[Path],
    *,
    table_caption_language: str = "en",
    polish_language: str | None = None,
    target_language: str = "en",
    skip_non_target_language: bool = False,
    skip_unknown_language: bool = False,
    inline_images: bool = True,
    image_cache_source_run: Path | None = None,
) -> dict[str, object]:
    results = [
        repolish_file(
            raw_path,
            table_caption_language=table_caption_language,
            polish_language=polish_language,
            target_language=target_language,
            skip_non_target_language=skip_non_target_language,
            skip_unknown_language=skip_unknown_language,
            inline_images=inline_images,
            image_cache_source_run=image_cache_source_run,
        )
        for raw_path in find_raw_files(roots)
    ]
    processed_results = [result for result in results if not result.skipped]
    skipped_results = [result for result in results if result.skipped]
    language_counts = Counter(result.detected_language for result in results)
    polish_language_counts = Counter(result.polish_language for result in processed_results)
    restored_image_source_counts: Counter[str] = Counter()
    for result in processed_results:
        if result.restored_images:
            restored_image_source_counts[result.image_cache_source or "unknown"] += result.restored_images
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": f"{RAW_STAGE} -> {POLISH_STAGE}",
        "roots": [str(root) for root in roots],
        "image_cache_source_run": str(image_cache_source_run) if image_cache_source_run is not None else "",
        "table_caption_language": table_caption_language,
        "polish_language": polish_language or table_caption_language,
        "target_language": target_language,
        "skip_non_target_language": skip_non_target_language,
        "skip_unknown_language": skip_unknown_language,
        "raw_count": len(results),
        "article_count": len(processed_results),
        "skipped_count": len(skipped_results),
        "changed_count": sum(1 for result in processed_results if result.changed),
        "restored_image_count": sum(result.restored_images for result in processed_results),
        "inlined_image_count": sum(len(result.inlined_images) for result in processed_results),
        "missing_image_count": sum(len(result.missing_images) for result in processed_results),
        "restored_image_source_counts": dict(sorted(restored_image_source_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "polish_language_counts": dict(sorted(polish_language_counts.items())),
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
        choices=("en", "ru", "auto"),
        help="Language policy for language-specific polish repairs; defaults to --table-caption-language.",
    )
    parser.add_argument(
        "--target-language",
        default="en",
        help="Document language to keep when --skip-non-target-language is enabled.",
    )
    parser.add_argument(
        "--skip-non-target-language",
        action="store_true",
        help="Skip confidently detected non-target documents instead of regenerating their polish stage.",
    )
    parser.add_argument(
        "--skip-unknown-language",
        action="store_true",
        help="Skip documents whose language cannot be detected confidently.",
    )
    parser.add_argument(
        "--no-inline-images",
        action="store_true",
        help="Do not inline local image files into regenerated polish HTML.",
    )
    parser.add_argument(
        "--image-cache-source-run",
        type=Path,
        help=(
            "Optional previous/source run directory used to restore data:image URLs "
            "for local raw image references before sidecar inlining."
        ),
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
        target_language=args.target_language,
        skip_non_target_language=args.skip_non_target_language,
        skip_unknown_language=args.skip_unknown_language,
        inline_images=not args.no_inline_images,
        image_cache_source_run=args.image_cache_source_run,
    )
    print(
        "Repolished EN stages: "
        f"raw={report['raw_count']} "
        f"articles={report['article_count']} "
        f"skipped={report['skipped_count']} "
        f"changed={report['changed_count']} "
        f"restored_images={report['restored_image_count']} "
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
