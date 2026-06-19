from pathlib import Path
from typing import Any

from pdf_html_polish.quality_loop.audit_polish_report import PolishAuditReportDeps, build_polish_report


def _report(
    roots: list[Path],
    articles: list[dict[str, Any]],
    defect_counts: dict[str, int],
    *,
    audit_status: str,
    total_pair_count: int,
) -> dict[str, Any]:
    return {
        "roots": [str(root) for root in roots],
        "articles": articles,
        "corpus_summary": {"defect_counts": defect_counts},
        "audit_status": audit_status,
        "processed_pair_count": len(articles),
        "total_pair_count": total_pair_count,
    }


def _defect_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        for defect in article.get("defects_found") or []:
            defect_id = str(defect.get("id") or "")
            counts[defect_id] = counts.get(defect_id, 0) + 1
    return counts


def _deps(
    pairs: list[tuple[Path, Path]],
    *,
    writes: list[dict[str, Any]] | None = None,
) -> PolishAuditReportDeps:
    def analyze_pair(raw_path: Path, polish_path: Path, **kwargs) -> dict[str, Any]:
        return {
            "article": raw_path.parent.parent.name,
            "raw_stage_path": str(raw_path),
            "polish_stage_path": str(polish_path),
            "summary": {
                "pdf_path_override": str(kwargs.get("pdf_path_override") or ""),
                "has_cache": kwargs.get("pdf_diagnostics_cache") is not None,
            },
            "defects_found": [{"id": "P04"}] if "two" in raw_path.parent.parent.name else [],
        }

    def write_json_report(path: Path, report: dict[str, Any]) -> None:
        if writes is not None:
            writes.append(report)
        path.write_text("written", encoding="utf-8")

    return PolishAuditReportDeps(
        find_pairs=lambda roots: pairs,
        analyze_pair=analyze_pair,
        add_corpus_hit_counts=_defect_counts,
        assemble_report=_report,
        write_json_report=write_json_report,
        article_name_from_stage=lambda stage_path: stage_path.parent.parent.name,
        pdf_diagnostics_cache_factory=lambda cache_dir: {"cache_dir": str(cache_dir)},
    )


def _stage_pair(root: Path, article: str) -> tuple[Path, Path]:
    stage_dir = root / article / "_z2m_stages"
    return stage_dir / "01.en.raw.html", stage_dir / "02.en.polish.html"


def test_build_polish_report_writes_progress_and_final_report(tmp_path: Path) -> None:
    root = tmp_path / "root"
    pairs = [_stage_pair(root, "Article one"), _stage_pair(root, "Article two")]
    writes: list[dict[str, Any]] = []
    progress_path = tmp_path / "progress.json"

    report = build_polish_report(
        [root],
        deps=_deps(pairs, writes=writes),
        progress_out=progress_path,
        progress_write_every=1,
    )

    assert progress_path.read_text(encoding="utf-8") == "written"
    assert [(item["audit_status"], item["processed_pair_count"]) for item in writes] == [
        ("running", 1),
        ("complete", 2),
        ("complete", 2),
    ]
    assert report["corpus_summary"]["defect_counts"] == {"P04": 1}


def test_build_polish_report_preserves_parallel_article_order_and_pdf_deps(tmp_path: Path) -> None:
    root = tmp_path / "root"
    pairs = [
        _stage_pair(root, "Article one"),
        _stage_pair(root, "Article two"),
        _stage_pair(root, "Article three"),
    ]
    pdf_path = tmp_path / "mapped.pdf"

    report = build_polish_report(
        [root],
        deps=_deps(pairs),
        enable_pdf_diagnostics=True,
        pdf_map={"Article two": pdf_path},
        jobs=2,
        pdf_diagnostics_cache_dir=tmp_path / "cache",
    )

    assert [article["article"] for article in report["articles"]] == [
        "Article one",
        "Article two",
        "Article three",
    ]
    assert report["articles"][1]["summary"]["pdf_path_override"] == str(pdf_path)
    assert {article["summary"]["has_cache"] for article in report["articles"]} == {True}
