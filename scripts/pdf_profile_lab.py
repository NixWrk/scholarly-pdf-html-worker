#!/usr/bin/env python
"""Flat repolish lab for PDF-derived citation-profile experiments.

The lab keeps one cached raw HTML per article and writes polish outputs into a
single flat folder.  It intentionally does not copy image sidecars.

For production-equivalent citation/internal-link checks, put
``_source_filename_map.csv`` in ``--source-root`` with ``alias_pdf_path`` and
``source_pdf_path`` columns.  The alias suffix must match the raw article
directory suffix so the lab can rebuild the same PDF-derived citation profile
that production passes to ``polish_html_document``.  Pass ``--zotero-overlay-dir``
to merge prebuilt Zotero/pdf.js overlay JSON when that data is part of the run.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.citation_profile import (  # noqa: E402
    CitationProfile,
    build_citation_profile_from_pdf,
    merge_citation_profile_with_zotero_overlays,
)
from zoteropdf2md.html_stages import RAW_STAGE_NAME, article_dir_from_html_stage  # noqa: E402
from zoteropdf2md.single_file_html import (  # noqa: E402
    close_katex_v8_context,
    polish_html_document,
)


RAW_STAGE = RAW_STAGE_NAME
SOURCE_MAP = "_source_filename_map.csv"
SUFFIX_RE = re.compile(r"_([0-9a-f]{8})(?:\.pdf)?$", re.IGNORECASE)


@dataclass
class LabArticle:
    suffix: str
    article: str
    source_pdf_path: str
    raw_cache_path: str
    profile_path: str
    polish_path: str
    profile_status: str
    citation_style: str
    citation_confidence: str
    changed: bool


def _article_suffix(value: str) -> str:
    match = SUFFIX_RE.search(value)
    if match is None:
        return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")[:32] or "article"
    return match.group(1).lower()


def _load_pdf_map(source_root: Path) -> dict[str, str]:
    map_path = source_root / SOURCE_MAP
    if not map_path.is_file():
        return {}
    pdf_by_suffix: dict[str, str] = {}
    with map_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            alias = row.get("alias_pdf_path") or ""
            source = row.get("source_pdf_path") or ""
            suffix = _article_suffix(Path(alias).name)
            if suffix and source:
                pdf_by_suffix[suffix] = source
    return pdf_by_suffix


def find_raw_files(source_root: Path) -> list[Path]:
    return sorted(source_root.rglob(RAW_STAGE), key=str)


def _load_or_build_profile(
    pdf_path: str,
    profile_path: Path,
    *,
    refresh: bool,
    zotero_overlay_path: Path | None = None,
) -> CitationProfile | dict[str, object]:
    if profile_path.is_file() and not refresh:
        profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
        if zotero_overlay_path is not None and not profile_data.get("zotero_citations"):
            profile_data = merge_citation_profile_with_zotero_overlays(profile_data, zotero_overlay_path)
            profile_path.write_text(json.dumps(profile_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif not profile_data.get("zotero_overlay_status"):
            profile = build_citation_profile_from_pdf(pdf_path)
            profile_data = profile.to_json_dict() if isinstance(profile, CitationProfile) else profile
            profile_path.write_text(json.dumps(profile_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return profile_data
    profile = build_citation_profile_from_pdf(pdf_path, zotero_overlay_path=zotero_overlay_path)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profile.to_json_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return profile


def _profile_attr(profile: CitationProfile | dict[str, object], key: str, default: str = "") -> str:
    if isinstance(profile, dict):
        return str(profile.get(key) or default)
    return str(getattr(profile, key, default) or default)


def _find_zotero_overlay_path(
    zotero_overlay_dir: Path | None,
    pdf_path: str,
    suffix: str,
) -> Path | None:
    if zotero_overlay_dir is None:
        return None
    overlay_dir = zotero_overlay_dir.expanduser().resolve(strict=False)
    if not overlay_dir.is_dir():
        return None

    pdf_name = Path(pdf_path).name
    candidates = [
        overlay_dir / f"{Path(pdf_name).stem}.overlays.json",
        overlay_dir / f"{suffix}.overlays.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    matches = sorted(overlay_dir.glob(f"*{suffix}*.overlays.json"), key=str)
    if matches:
        return matches[0]
    matches = sorted(overlay_dir.glob(f"*{Path(pdf_name).stem[:48]}*.overlays.json"), key=str)
    return matches[0] if matches else None


def run_lab(
    source_root: Path,
    out_dir: Path,
    *,
    refresh_raw_cache: bool = False,
    refresh_profiles: bool = False,
    zotero_overlay_dir: Path | None = None,
    suffixes: set[str] | None = None,
) -> dict[str, object]:
    source_root = source_root.expanduser().resolve(strict=False)
    out_dir = out_dir.expanduser().resolve(strict=False)
    raw_cache_dir = out_dir / "raw_cache"
    profile_dir = out_dir / "profiles"
    polish_dir = out_dir / "polish"
    raw_cache_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    polish_dir.mkdir(parents=True, exist_ok=True)

    pdf_by_suffix = _load_pdf_map(source_root)
    articles: list[LabArticle] = []
    for raw_stage in find_raw_files(source_root):
        article_dir = article_dir_from_html_stage(raw_stage)
        suffix = _article_suffix(article_dir.name)
        if suffixes is not None and suffix not in suffixes:
            continue

        raw_cache_path = raw_cache_dir / f"{suffix}.{RAW_STAGE}"
        if refresh_raw_cache or not raw_cache_path.is_file():
            shutil.copy2(raw_stage, raw_cache_path)

        source_pdf_path = pdf_by_suffix.get(suffix, "")
        profile_path = profile_dir / f"{suffix}.citation_profile.json"
        profile: CitationProfile | dict[str, object]
        if source_pdf_path:
            zotero_overlay_path = _find_zotero_overlay_path(zotero_overlay_dir, source_pdf_path, suffix)
            profile = _load_or_build_profile(
                source_pdf_path,
                profile_path,
                refresh=refresh_profiles,
                zotero_overlay_path=zotero_overlay_path,
            )
        else:
            profile = {
                "source_pdf_path": "",
                "status": "missing_source_map",
                "style": "unknown",
                "confidence": "low",
            }
            profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        raw_html = raw_cache_path.read_text(encoding="utf-8", errors="replace")
        polish_html = polish_html_document(
            raw_html,
            table_caption_language="en",
            enable_citation_linkify=True,
            citation_profile=profile,
        )
        polish_path = polish_dir / f"{suffix}.02.en.polish.html"
        previous = polish_path.read_text(encoding="utf-8", errors="replace") if polish_path.is_file() else None
        changed = previous != polish_html
        polish_path.write_text(polish_html, encoding="utf-8")

        articles.append(
            LabArticle(
                suffix=suffix,
                article=article_dir.name,
                source_pdf_path=source_pdf_path,
                raw_cache_path=str(raw_cache_path),
                profile_path=str(profile_path),
                polish_path=str(polish_path),
                profile_status=_profile_attr(profile, "status"),
                citation_style=_profile_attr(profile, "style"),
                citation_confidence=_profile_attr(profile, "confidence"),
                changed=changed,
            )
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source_root),
        "out_dir": str(out_dir),
        "raw_cache_dir": str(raw_cache_dir),
        "polish_dir": str(polish_dir),
        "article_count": len(articles),
        "changed_count": sum(1 for article in articles if article.changed),
        "articles": [asdict(article) for article in articles],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--refresh-raw-cache", action="store_true")
    parser.add_argument("--refresh-profiles", action="store_true")
    parser.add_argument(
        "--zotero-overlay-dir",
        type=Path,
        help="Optional directory with Zotero/pdf.js *.overlays.json files.",
    )
    parser.add_argument(
        "--suffix",
        action="append",
        help="Optional 8-char article suffix to process. Repeat for multiple articles.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    suffixes = {value.lower() for value in args.suffix} if args.suffix else None
    try:
        report = run_lab(
            args.source_root,
            args.out_dir,
            refresh_raw_cache=args.refresh_raw_cache,
            refresh_profiles=args.refresh_profiles,
            zotero_overlay_dir=args.zotero_overlay_dir,
            suffixes=suffixes,
        )
    finally:
        close_katex_v8_context()
    print(
        "PDF profile lab: "
        f"articles={report['article_count']} "
        f"changed={report['changed_count']} "
        f"out={report['out_dir']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
