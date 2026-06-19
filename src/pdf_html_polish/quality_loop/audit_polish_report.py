"""Report-level EN polish audit orchestration."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PolishAuditReportDeps:
    find_pairs: Callable[[list[Path]], list[tuple[Path, Path]]]
    analyze_pair: Callable[..., dict[str, Any]]
    add_corpus_hit_counts: Callable[[list[dict[str, Any]]], dict[str, int]]
    assemble_report: Callable[..., dict[str, Any]]
    write_json_report: Callable[[Path, dict[str, Any]], None]
    article_name_from_stage: Callable[[Path], str]
    pdf_diagnostics_cache_factory: Callable[[Path], Any]


def _analyze_pair_task(task: tuple[int, Path, Path, bool, str, Any | None, PolishAuditReportDeps]) -> tuple[int, dict[str, Any]]:
    index, raw_path, polish_path, enable_pdf_diagnostics, pdf_path, pdf_diagnostics_cache, deps = task
    return (
        index,
        deps.analyze_pair(
            raw_path,
            polish_path,
            enable_pdf_diagnostics=enable_pdf_diagnostics,
            pdf_path_override=Path(pdf_path) if pdf_path else None,
            pdf_diagnostics_cache=pdf_diagnostics_cache,
        ),
    )


def build_polish_report(
    roots: list[Path],
    *,
    deps: PolishAuditReportDeps,
    enable_pdf_diagnostics: bool = False,
    pdf_map: dict[str, Path] | None = None,
    progress_out: Path | None = None,
    progress_write_every: int = 10,
    jobs: int = 1,
    pdf_diagnostics_cache_dir: Path | None = None,
) -> dict[str, Any]:
    pairs = deps.find_pairs(roots)
    progress_every = max(1, progress_write_every)
    worker_count = max(1, int(jobs or 1))
    articles_by_index: list[dict[str, Any] | None] = [None] * len(pairs)
    pdf_diagnostics_cache = (
        deps.pdf_diagnostics_cache_factory(pdf_diagnostics_cache_dir)
        if enable_pdf_diagnostics and pdf_diagnostics_cache_dir is not None
        else None
    )

    def completed_articles() -> list[dict[str, Any]]:
        return [article for article in articles_by_index if article is not None]

    def write_progress(completed: int) -> None:
        if progress_out is None or not (completed % progress_every == 0 or completed == len(pairs)):
            return
        articles = completed_articles()
        defect_counts = deps.add_corpus_hit_counts(articles)
        partial_report = deps.assemble_report(
            roots,
            articles,
            defect_counts,
            audit_status=("complete" if completed == len(pairs) else "running"),
            total_pair_count=len(pairs),
        )
        deps.write_json_report(progress_out, partial_report)
        print(
            f"Audit progress: {completed}/{len(pairs)} articles={len(articles)} "
            f"defects={sum(len(article['defects_found']) for article in articles)}",
            flush=True,
        )

    pdf_map = pdf_map or {}
    if worker_count <= 1 or len(pairs) <= 1:
        for index, (raw_path, polish_path) in enumerate(pairs, 1):
            articles_by_index[index - 1] = deps.analyze_pair(
                raw_path,
                polish_path,
                enable_pdf_diagnostics=enable_pdf_diagnostics,
                pdf_path_override=pdf_map.get(deps.article_name_from_stage(raw_path)),
                pdf_diagnostics_cache=pdf_diagnostics_cache,
            )
            write_progress(index)
    else:
        tasks = [
            (
                index,
                raw_path,
                polish_path,
                enable_pdf_diagnostics,
                str(pdf_map.get(deps.article_name_from_stage(raw_path)) or ""),
                pdf_diagnostics_cache,
                deps,
            )
            for index, (raw_path, polish_path) in enumerate(pairs, 1)
        ]
        completed = 0
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(_analyze_pair_task, task) for task in tasks]
            for future in as_completed(futures):
                index, article = future.result()
                articles_by_index[index - 1] = article
                completed += 1
                write_progress(completed)

    articles = completed_articles()
    defect_counts = deps.add_corpus_hit_counts(articles)
    report = deps.assemble_report(
        roots,
        articles,
        defect_counts,
        audit_status="complete",
        total_pair_count=len(pairs),
    )
    if progress_out is not None:
        deps.write_json_report(progress_out, report)
    return report


def merge_targeted_polish_report(
    previous_report: dict[str, Any],
    targeted_report: dict[str, Any],
    *,
    deps: PolishAuditReportDeps,
    previous_report_path: Path | None = None,
    allow_new_articles: bool = False,
) -> dict[str, Any]:
    previous_articles = previous_report.get("articles") or []
    targeted_articles = targeted_report.get("articles") or []
    by_article: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for article in previous_articles:
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        by_article[article_id] = article
        order.append(article_id)

    replaced: list[str] = []
    new_articles: list[str] = []
    for article in targeted_articles:
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        if article_id not in by_article:
            if not allow_new_articles:
                raise ValueError(f"Targeted audit article is not present in previous report: {article_id}")
            order.append(article_id)
            new_articles.append(article_id)
        else:
            replaced.append(article_id)
        by_article[article_id] = article

    merged_articles = [by_article[article_id] for article_id in order if article_id in by_article]
    defect_counts = deps.add_corpus_hit_counts(merged_articles)
    merged = deps.assemble_report(
        [Path(root) for root in previous_report.get("roots") or targeted_report.get("roots") or []],
        merged_articles,
        defect_counts,
        audit_status="complete",
        total_pair_count=int(previous_report.get("total_pair_count") or len(merged_articles)),
    )
    merged["targeted_audit"] = {
        "enabled": True,
        "previous_report_path": str(previous_report_path) if previous_report_path is not None else "",
        "target_roots": targeted_report.get("roots") or [],
        "target_article_count": len(targeted_articles),
        "reused_article_count": max(0, len(previous_articles) - len(replaced)),
        "replaced_article_count": len(replaced),
        "new_article_count": len(new_articles),
        "replaced_articles": sorted(replaced),
        "new_articles": sorted(new_articles),
    }
    return merged
