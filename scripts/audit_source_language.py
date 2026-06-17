#!/usr/bin/env python
"""Audit source language for raw HTML stages."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.html_stages import RAW_STAGE_NAME, article_name_from_html_stage
from pdf_html_polish.language_detect import detect_language_from_html, language_gate_decision


RAW_STAGE = RAW_STAGE_NAME
RUN_DATE = datetime.now().strftime("%Y-%m-%d")


def _jsonable_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def find_raw_stages(roots: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.is_file() and root.name == RAW_STAGE:
            found.add(root.resolve(strict=False))
        elif root.exists():
            found.update(path.resolve(strict=False) for path in root.rglob(RAW_STAGE))
    return sorted(found, key=lambda path: str(path))


def _candidate_output_roots(roots: Iterable[Path]) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        if root.is_file():
            parents = list(root.parents)
            if len(parents) >= 3:
                candidates.append(parents[2])
        else:
            candidates.append(root)
    return candidates


def _load_alias_maps(roots: Iterable[Path]) -> dict[str, dict[str, Any]]:
    aliases: dict[str, dict[str, Any]] = {}
    for root in _candidate_output_roots(roots):
        quality_dir = root / "_quality_audit"
        if not quality_dir.is_dir():
            continue
        for path in sorted(quality_dir.glob("source_alias_map_*.json")):
            try:
                items = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and item.get("alias_base_name"):
                    aliases[str(item["alias_base_name"])] = item
    return aliases


def _article_alias(raw_path: Path) -> str:
    return article_name_from_html_stage(raw_path)


def analyze_raw_stage(
    raw_path: Path,
    *,
    alias_map: dict[str, dict[str, Any]],
    target_language: str,
    min_confidence: float,
    skip_unknown: bool,
) -> dict[str, Any]:
    html = raw_path.read_text(encoding="utf-8", errors="replace")
    detection = detect_language_from_html(html)
    decision = language_gate_decision(
        detection,
        target_language=target_language,
        min_confidence=min_confidence,
        skip_unknown=skip_unknown,
    )
    alias = _article_alias(raw_path)
    source = alias_map.get(alias, {})
    return {
        "article": alias,
        "raw_stage_path": _jsonable_path(raw_path),
        "source_pdf_path": source.get("source_pdf_path", ""),
        "source_pdf_name": source.get("source_pdf_name", ""),
        "language": detection.to_dict(),
        "gate": decision.to_dict(),
    }


def _default_out_path(roots: list[Path]) -> Path | None:
    if len(roots) != 1 or roots[0].is_file():
        return None
    return roots[0] / "_quality_audit" / f"source_language_audit_{RUN_DATE}.json"


def _csv_path_for_json(out_path: Path | None) -> Path | None:
    if out_path is None:
        return None
    return out_path.with_suffix(".csv")


def build_report(
    roots: list[Path],
    *,
    target_language: str,
    min_confidence: float,
    skip_unknown: bool,
) -> dict[str, Any]:
    alias_map = _load_alias_maps(roots)
    articles = [
        analyze_raw_stage(
            raw_path,
            alias_map=alias_map,
            target_language=target_language,
            min_confidence=min_confidence,
            skip_unknown=skip_unknown,
        )
        for raw_path in find_raw_stages(roots)
    ]
    language_counts = Counter(article["language"]["detected_language"] for article in articles)
    skipped = [article for article in articles if article["gate"]["should_skip"]]
    unknown = [article for article in articles if article["language"]["detected_language"] == "unknown"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": RAW_STAGE,
        "roots": [str(root) for root in roots],
        "target_language": target_language,
        "min_confidence": min_confidence,
        "skip_unknown": skip_unknown,
        "article_count": len(articles),
        "corpus_summary": {
            "language_counts": dict(sorted(language_counts.items())),
            "language_skipped_total": len(skipped),
            "unknown_total": len(unknown),
        },
        "language_skipped": skipped,
        "unknown_language": unknown,
        "articles": articles,
    }


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "article",
                "detected_language",
                "confidence",
                "reason",
                "should_skip",
                "gate_reason",
                "sampled_windows",
                "latin_ratio",
                "cyrillic_ratio",
                "english_stopword_hits",
                "russian_stopword_hits",
                "source_pdf_path",
                "raw_stage_path",
            ],
        )
        writer.writeheader()
        for article in report["articles"]:
            language = article["language"]
            gate = article["gate"]
            writer.writerow(
                {
                    "article": article["article"],
                    "detected_language": language["detected_language"],
                    "confidence": f"{float(language['confidence']):.4f}",
                    "reason": language["reason"],
                    "should_skip": "yes" if gate["should_skip"] else "no",
                    "gate_reason": gate["reason"],
                    "sampled_windows": language["sampled_windows"],
                    "latin_ratio": f"{float(language['latin_ratio']):.4f}",
                    "cyrillic_ratio": f"{float(language['cyrillic_ratio']):.4f}",
                    "english_stopword_hits": language["english_stopword_hits"],
                    "russian_stopword_hits": language["russian_stopword_hits"],
                    "source_pdf_path": article["source_pdf_path"],
                    "raw_stage_path": article["raw_stage_path"],
                }
            )


def _print_summary(report: dict[str, Any]) -> None:
    summary = report["corpus_summary"]
    print(f"Source language audit: {report['article_count']} raw stage(s)")
    print(
        "Language counts: "
        + ", ".join(
            f"{lang}={count}" for lang, count in summary["language_counts"].items()
        )
    )
    print(
        "Gate: "
        f"target={report['target_language']} "
        f"min_confidence={report['min_confidence']} "
        f"skipped={summary['language_skipped_total']} "
        f"unknown={summary['unknown_total']}"
    )
    for article in report["language_skipped"][:30]:
        language = article["language"]
        print(
            f"- skip {article['article']}: "
            f"lang={language['detected_language']} "
            f"confidence={float(language['confidence']):.2f} "
            f"reason={language['reason']}"
        )
    if len(report["language_skipped"]) > 30:
        print(f"... {len(report['language_skipped']) - 30} more skipped raw stages")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="Root directories or direct 01.en.raw.html files to audit.",
    )
    parser.add_argument("--target-language", default="en", help="Expected source language code.")
    parser.add_argument("--min-confidence", type=float, default=0.75, help="Mismatch skip threshold.")
    parser.add_argument(
        "--skip-unknown-language",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Treat unknown as a skip. Use --no-skip-unknown-language to allow it.",
    )
    parser.add_argument("--out", type=Path, help="Optional JSON report path.")
    parser.add_argument("--csv-out", type=Path, help="Optional CSV report path.")
    parser.add_argument(
        "--fail-on-non-target",
        action="store_true",
        help="Exit with status 1 when any raw stage is gated as non-target language.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.roots,
        target_language=args.target_language,
        min_confidence=args.min_confidence,
        skip_unknown=args.skip_unknown_language,
    )
    _print_summary(report)

    out_path = args.out or _default_out_path(args.roots)
    csv_path = args.csv_out or _csv_path_for_json(out_path)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out_path}")
    if csv_path is not None:
        write_csv(csv_path, report)
        print(f"Wrote {csv_path}")
    if args.fail_on_non_target and report["language_skipped"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
