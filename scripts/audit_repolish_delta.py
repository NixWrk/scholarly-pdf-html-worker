#!/usr/bin/env python
"""Dry-run current repolish code against quality-counted strict audit defects."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable
import sys
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.quality_loop.audit_diagnostics import diagnostic_spec


class _ImageHintParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hints: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        for name in ("src", "data-z2m-src"):
            value = values.get(name, "").strip()
            if value and not value.lower().startswith(("data:", "http://", "https://")):
                self.hints.append(value)


def _safe_image_relative_path(value: str) -> Path | None:
    clean = urllib.parse.unquote(value.split("?", 1)[0].split("#", 1)[0])
    path = Path(clean)
    if not clean or path.is_absolute() or ".." in path.parts:
        return None
    return path


def _attempt_sidecar_source(raw_path: Path, relative: Path) -> Path | None:
    if raw_path.parent.name not in {"_pdf_html_polish_stages", "_z2m_stages"}:
        return None
    article_root = raw_path.parent.parent
    attempts_roots = [
        root
        for root in (article_root / "_attempts", article_root.parent / "_attempts")
        if root.is_dir()
    ]
    if not attempts_roots:
        return None

    matches: list[Path] = []
    for attempts_root in attempts_roots:
        matches.extend(
            candidate
            for candidate in attempts_root.rglob(relative.name)
            if candidate.is_file()
            and candidate.relative_to(attempts_root).parts[-len(relative.parts) :]
            == relative.parts
        )
    if not matches:
        return None

    by_digest: dict[str, list[Path]] = {}
    for candidate in matches:
        digest = hashlib.sha256()
        with candidate.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        by_digest.setdefault(digest.hexdigest(), []).append(candidate)
    if len(by_digest) != 1:
        return None
    return sorted(matches)[0]


def stage_raw_with_sidecars(raw_path: Path, staging_root: Path) -> Path:
    staging_root.mkdir(parents=True, exist_ok=True)
    staged_raw = staging_root / raw_path.name
    shutil.copy2(raw_path, staged_raw)
    parser = _ImageHintParser()
    parser.feed(raw_path.read_text(encoding="utf-8", errors="replace"))
    source_roots = [raw_path.parent]
    if raw_path.parent.name in {"_pdf_html_polish_stages", "_z2m_stages"}:
        source_roots.append(raw_path.parent.parent)
    for hint in dict.fromkeys(parser.hints):
        relative = _safe_image_relative_path(hint)
        if relative is None:
            continue
        source = next(
            (root / relative for root in source_roots if (root / relative).is_file()),
            None,
        )
        if source is None:
            source = _attempt_sidecar_source(raw_path, relative)
        if source is None:
            continue
        target = staging_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
    return staged_raw


def inferred_citation_profile(raw_path: Path) -> dict[str, Any]:
    from pdf_html_polish.quality_loop.converted_runs import (
        _converted_raw_citation_profile,
    )

    raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
    return _converted_raw_citation_profile(raw_html, raw_path)


def load_json_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def article_matches_patterns(article: dict[str, Any], patterns: list[str]) -> bool:
    if not patterns:
        return True
    searchable = " ".join(
        str(article.get(field) or "")
        for field in ("article", "raw_stage_path", "polish_stage_path")
    ).casefold()
    return any(pattern in searchable for pattern in patterns)


def quality_defects(article: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for defect in article.get("defects_found") or []:
        extra = defect.get("extra") if isinstance(defect.get("extra"), dict) else {}
        explicit_quality = extra.get("quality_counted")
        spec = diagnostic_spec(str(defect.get("id") or ""))
        quality_counted = (
            bool(explicit_quality)
            if explicit_quality is not None
            else spec is None or spec.quality_counted_by_default
        )
        if (
            str(defect.get("severity")) in {"warning", "error"}
            and str(defect.get("status") or "open") == "open"
            and quality_counted
        ):
            result.append(defect)
    return result


def defect_counts(defects: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(defect.get("id") or "unknown") for defect in defects)


def console_safe(text: str, *, encoding: str | None = None) -> str:
    target_encoding = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(target_encoding, errors="backslashreplace").decode(
        target_encoding
    )


def classify_delta(
    before: Counter[str], after: Counter[str], *, error: str | None = None
) -> str:
    if error:
        return "repolish_failed"
    if not after:
        return "fixed"
    if after - before:
        return "regressed"
    if sum(after.values()) < sum(before.values()):
        return "improved"
    if after == before:
        return "unchanged"
    return "regressed"


def recommended_action(classification: str) -> str:
    if classification in {"fixed", "improved"}:
        return "repolish"
    if classification == "repolish_failed":
        return "artifact_repair_or_reconvert"
    return "code_fix_or_reconvert"


def evaluate_article(
    article: dict[str, Any],
    *,
    repolish: Callable[[Path], str],
    analyze_pair: Callable[[Path, Path], dict[str, Any]],
    temp_root: Path,
    keep_output_dir: Path | None = None,
) -> dict[str, Any]:
    raw_path = Path(str(article.get("raw_stage_path") or ""))
    polish_path = Path(str(article.get("polish_stage_path") or ""))
    before_defects: list[dict[str, Any]] = []
    before_counts: Counter[str] = Counter()
    error: str | None = None
    after_article: dict[str, Any] | None = None
    output_bytes = 0
    output_sha256: str | None = None
    candidate_output_path: Path | None = None

    try:
        if not raw_path.is_file():
            raise FileNotFoundError(f"raw stage missing: {raw_path}")
        if not polish_path.is_file():
            raise FileNotFoundError(f"polish stage missing: {polish_path}")
        before_article = analyze_pair(raw_path, polish_path)
        before_defects = quality_defects(before_article)
        before_counts = defect_counts(before_defects)
        with tempfile.TemporaryDirectory(
            prefix="z2m-repolish-delta-", dir=temp_root
        ) as directory:
            output_path = Path(directory) / "02.en.polish.html"
            output_html = repolish(raw_path)
            output_data = output_html.encode("utf-8")
            output_bytes = len(output_data)
            output_sha256 = hashlib.sha256(output_data).hexdigest()
            output_path.write_bytes(output_data)
            if keep_output_dir is not None:
                article_key = hashlib.sha256(
                    str(polish_path).encode("utf-8")
                ).hexdigest()[:16]
                candidate_output_path = (
                    keep_output_dir / article_key / "02.en.polish.html"
                )
                candidate_output_path.parent.mkdir(parents=True, exist_ok=True)
                candidate_output_path.write_bytes(output_data)
            after_article = analyze_pair(raw_path, output_path)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    after_defects = quality_defects(after_article or {})
    after_counts = defect_counts(after_defects)
    classification = classify_delta(before_counts, after_counts, error=error)
    return {
        "article": str(article.get("article") or polish_path.parent.parent.name),
        "raw_stage_path": str(raw_path),
        "polish_stage_path": str(polish_path),
        "before_defect_counts": dict(sorted(before_counts.items())),
        "before_defects": before_defects,
        "after_defect_counts": dict(sorted(after_counts.items())),
        "after_defects": after_defects,
        "fixed_defect_counts": dict(sorted((before_counts - after_counts).items())),
        "new_defect_counts": dict(sorted((after_counts - before_counts).items())),
        "classification": classification,
        "recommended_action": recommended_action(classification),
        "output_bytes": output_bytes,
        "output_sha256": output_sha256,
        "candidate_output_path": str(candidate_output_path)
        if candidate_output_path
        else None,
        "error": error,
    }


def load_strict_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "z2m_repolish_delta_strict_audit", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load strict audit module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def refresh_article_audit(
    article: dict[str, Any],
    *,
    analyze_pair: Callable[[Path, Path], dict[str, Any]],
) -> dict[str, Any]:
    raw_path = Path(str(article.get("raw_stage_path") or ""))
    polish_path = Path(str(article.get("polish_stage_path") or ""))
    current = analyze_pair(raw_path, polish_path)
    return {**article, **current}


def build_fresh_baseline(
    strict_module: Any,
    source_articles: list[dict[str, Any]],
    *,
    output: Path,
    jobs: int,
) -> list[dict[str, Any]]:
    roots: list[Path] = []
    for article in source_articles:
        raw_path = Path(str(article.get("raw_stage_path") or ""))
        polish_path = Path(str(article.get("polish_stage_path") or ""))
        if not raw_path.is_file() or not polish_path.is_file():
            raise FileNotFoundError(
                f"baseline stage pair missing: raw={raw_path} polish={polish_path}"
            )
        roots.append(polish_path)
    report = strict_module.build_report(
        roots,
        enable_pdf_diagnostics=False,
        progress_out=output,
        progress_write_every=25,
        jobs=max(1, jobs),
    )
    articles = list(report.get("articles") or [])
    if len(articles) != len(source_articles):
        raise RuntimeError(
            "Fresh baseline did not preserve the source corpus: "
            f"expected={len(source_articles)} actual={len(articles)}"
        )
    return articles


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def assemble_report(
    *,
    source_report: Path,
    candidates: list[dict[str, Any]],
    results: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    classifications = Counter(result["classification"] for result in results)
    before_counts = Counter()
    after_counts = Counter()
    fixed_counts = Counter()
    new_counts = Counter()
    for result in results:
        before_counts.update(result["before_defect_counts"])
        after_counts.update(result["after_defect_counts"])
        fixed_counts.update(result["fixed_defect_counts"])
        new_counts.update(result["new_defect_counts"])
    return {
        "mode": "pdf_html_repolish_delta",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "source_report": str(source_report),
        "summary": {
            "candidate_articles": len(candidates),
            "processed_articles": len(results),
            "classification_counts": dict(sorted(classifications.items())),
            "before_defect_counts": dict(sorted(before_counts.items())),
            "after_defect_counts": dict(sorted(after_counts.items())),
            "fixed_defect_counts": dict(sorted(fixed_counts.items())),
            "new_defect_counts": dict(sorted(new_counts.items())),
        },
        "results": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--baseline-output",
        type=Path,
        help="Fresh current-artifact baseline report (default: beside --output).",
    )
    parser.add_argument("--baseline-jobs", type=int, default=4)
    parser.add_argument("--temp-root", type=Path, default=ROOT / ".tmp_repolish_delta")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--defect-id", action="append", default=None)
    parser.add_argument(
        "--article-pattern",
        action="append",
        default=None,
        help="Case-insensitive substring filter over article name and stage paths; repeatable.",
    )
    parser.add_argument(
        "--keep-output-dir",
        type=Path,
        help="Optional diagnostics directory for candidate HTML. Production artifacts are never changed.",
    )
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    strict_report_path = args.strict_report.resolve()
    output = args.output.resolve()
    strict_report = load_json_report(strict_report_path)
    strict_module = load_strict_module(ROOT / "scripts" / "audit_en_polish.py")
    source_articles = list(strict_report.get("articles") or [])
    requested_article_patterns = [
        pattern.casefold() for pattern in args.article_pattern or []
    ]
    if requested_article_patterns:
        source_articles = [
            article
            for article in source_articles
            if article_matches_patterns(article, requested_article_patterns)
        ]
    baseline_output = (
        args.baseline_output.resolve()
        if args.baseline_output is not None
        else output.with_name(f"{output.stem}_baseline.json")
    )
    refreshed_articles = build_fresh_baseline(
        strict_module,
        source_articles,
        output=baseline_output,
        jobs=args.baseline_jobs,
    )
    requested_ids = set(args.defect_id or [])
    candidates = [
        article
        for article in refreshed_articles
        if quality_defects(article)
        and (
            not requested_ids
            or requested_ids.intersection(defect_counts(quality_defects(article)))
        )
    ]
    if args.limit > 0:
        candidates = candidates[: args.limit]

    previous_results: list[dict[str, Any]] = []
    if args.resume and output.is_file():
        previous = load_json_report(output)
        previous_results = list(previous.get("results") or [])
    completed_paths = {result["polish_stage_path"] for result in previous_results}
    results = previous_results

    args.temp_root.mkdir(parents=True, exist_ok=True)
    if args.keep_output_dir is not None:
        args.keep_output_dir.mkdir(parents=True, exist_ok=True)
    from pdf_html_polish.single_file_html import polish_and_inline_html_file

    def repolish(path: Path) -> str:
        with tempfile.TemporaryDirectory(
            prefix="z2m-repolish-input-", dir=args.temp_root
        ) as directory:
            staged_raw = stage_raw_with_sidecars(path, Path(directory))
            citation_profile = inferred_citation_profile(staged_raw)
            return polish_and_inline_html_file(
                staged_raw,
                citation_profile=citation_profile,
            ).html

    for index, article in enumerate(candidates, 1):
        if str(article.get("polish_stage_path") or "") in completed_paths:
            continue
        result = evaluate_article(
            article,
            repolish=repolish,
            analyze_pair=strict_module.analyze_pair,
            temp_root=args.temp_root,
            keep_output_dir=args.keep_output_dir,
        )
        results.append(result)
        report = assemble_report(
            source_report=strict_report_path,
            candidates=candidates,
            results=results,
            status="running",
        )
        write_report(output, report)
        progress_line = (
            f"Repolish delta: {index}/{len(candidates)} "
            f"article={result['article']} classification={result['classification']}"
        )
        print(console_safe(progress_line), flush=True)

    report = assemble_report(
        source_report=strict_report_path,
        candidates=candidates,
        results=results,
        status="complete",
    )
    write_report(output, report)
    final_summary = json.dumps(
        {"output": str(output), "summary": report["summary"]},
        ensure_ascii=False,
        indent=2,
    )
    print(console_safe(final_summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
