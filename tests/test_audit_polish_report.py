from pathlib import Path
from typing import Any

from pdf_html_polish.quality_loop.audit_polish_report import (
    PolishAuditReportDeps,
    build_polish_report,
    merge_targeted_polish_report,
    polish_report_summary_lines,
    print_polish_report_summary,
)


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


def test_merge_targeted_polish_report_replaces_articles_and_records_metadata(tmp_path: Path) -> None:
    root = tmp_path / "root"
    previous = _report(
        [root],
        [
            {"article": "Article one", "defects_found": []},
            {"article": "Article two", "defects_found": []},
        ],
        {},
        audit_status="complete",
        total_pair_count=2,
    )
    targeted = _report(
        [root / "Article two"],
        [{"article": "Article two", "defects_found": [{"id": "P04"}]}],
        {"P04": 1},
        audit_status="complete",
        total_pair_count=1,
    )

    merged = merge_targeted_polish_report(
        previous,
        targeted,
        deps=_deps([]),
        previous_report_path=tmp_path / "previous.json",
    )

    assert [article["article"] for article in merged["articles"]] == ["Article one", "Article two"]
    assert merged["corpus_summary"]["defect_counts"] == {"P04": 1}
    assert merged["total_pair_count"] == 2
    assert merged["targeted_audit"]["previous_report_path"] == str(tmp_path / "previous.json")
    assert merged["targeted_audit"]["reused_article_count"] == 1
    assert merged["targeted_audit"]["replaced_articles"] == ["Article two"]


def test_merge_targeted_polish_report_rejects_unexpected_new_articles(tmp_path: Path) -> None:
    previous = _report(
        [tmp_path],
        [{"article": "Article one", "defects_found": []}],
        {},
        audit_status="complete",
        total_pair_count=1,
    )
    targeted = _report(
        [tmp_path / "new"],
        [{"article": "Article new", "defects_found": []}],
        {},
        audit_status="complete",
        total_pair_count=1,
    )

    try:
        merge_targeted_polish_report(previous, targeted, deps=_deps([]))
    except ValueError as exc:
        assert "Article new" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected new targeted article to be rejected")


def test_merge_targeted_polish_report_allows_new_articles_when_requested(tmp_path: Path) -> None:
    previous = _report(
        [tmp_path],
        [{"article": "Article one", "defects_found": []}],
        {},
        audit_status="complete",
        total_pair_count=1,
    )
    targeted = _report(
        [tmp_path / "new"],
        [{"article": "Article new", "defects_found": [{"id": "P05"}]}],
        {"P05": 1},
        audit_status="complete",
        total_pair_count=1,
    )

    merged = merge_targeted_polish_report(
        previous,
        targeted,
        deps=_deps([]),
        allow_new_articles=True,
    )

    assert [article["article"] for article in merged["articles"]] == ["Article one", "Article new"]
    assert merged["targeted_audit"]["new_articles"] == ["Article new"]
    assert merged["targeted_audit"]["new_article_count"] == 1
    assert merged["corpus_summary"]["defect_counts"] == {"P05": 1}


def test_polish_report_summary_lines_include_totals_defects_and_articles(capsys) -> None:
    report = {
        "article_count": 1,
        "corpus_summary": {
            "totals": {
                "raw_img_tags": 1,
                "polish_img_tags": 2,
                "polish_ref_links": 3,
                "polish_fig_links": 4,
                "polish_table_links": 5,
                "polish_page_links": 6,
                "polish_replacement_chars": 7,
                "polish_missing_local_images": 8,
            },
            "defect_counts": {"P04": 2, "P05": 1},
        },
        "articles": [
            {
                "article": "Article one",
                "summary": {
                    "raw_blocks": 10,
                    "polish_blocks": 11,
                    "raw_img_tags": 1,
                    "polish_img_tags": 2,
                    "polish_missing_local_images": 3,
                    "polish_ref_links": 4,
                    "polish_fig_links": 5,
                    "polish_page_links": 6,
                    "polish_replacement_chars": 7,
                },
                "defects_found": [{"id": "P04"}],
            }
        ],
    }

    lines = polish_report_summary_lines(report)
    print_polish_report_summary(report)

    assert lines == [
        "EN raw/polish pair audit: 1 pair(s)",
        "Totals: raw_img=1 polish_img=2 ref_links=3 fig_links=4 table_links=5 page_links=6 bad_chars=7 missing_img=8",
        "Defects by check: P04=2, P05=1",
        "- Article one: blocks=10->11 img=1->2 missing_img=3 refs=4 fig_links=5 page_links=6 bad_chars=7 defects=1",
    ]
    assert capsys.readouterr().out.splitlines() == lines
