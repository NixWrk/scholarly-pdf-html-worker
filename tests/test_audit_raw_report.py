from pdf_html_polish.quality_loop.audit_raw_report import (
    add_raw_corpus_hit_counts,
    build_raw_report,
    find_raw_stage_files,
    raw_report_summary_lines,
)


def _article(name: str, defects: list[str]) -> dict:
    return {
        "article": name,
        "en_raw_summary": {
            "bytes": 10,
            "images": {"img_tags": 1},
            "figure_labels": 2,
            "table_labels": 3,
            "page_headers": 4,
            "raw_sentinels": 5,
        },
        "defects_found": [{"id": defect_id} for defect_id in defects],
    }


def test_find_raw_stage_files_accepts_roots_and_direct_stage_files(tmp_path) -> None:
    root = tmp_path / "root"
    stage_dir = root / "Article" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    stage = stage_dir / "01.en.raw.html"
    stage.write_text("<html></html>", encoding="utf-8")

    assert find_raw_stage_files([root, stage]) == [stage.resolve(strict=False)]


def test_add_raw_corpus_hit_counts_mutates_defects_once_per_article() -> None:
    articles = [_article("one", ["R01", "R01"]), _article("two", ["R01", "R02"])]

    counts = add_raw_corpus_hit_counts(articles)

    assert counts == {"R01": 2, "R02": 1}
    assert [defect["same_pattern_hits_across_corpus"] for defect in articles[0]["defects_found"]] == [2, 2]


def test_build_raw_report_aggregates_totals_with_injected_analyzer(tmp_path) -> None:
    stage = tmp_path / "01.en.raw.html"
    stage.write_text("<html></html>", encoding="utf-8")

    report = build_raw_report([stage], analyze_file=lambda path: _article(path.name, ["R01"]))

    assert report["article_count"] == 1
    assert report["corpus_summary"]["defect_counts"] == {"R01": 1}
    assert report["corpus_summary"]["totals"] == {
        "bytes": 10,
        "img_tags": 1,
        "figure_labels": 2,
        "table_labels": 3,
        "page_headers": 4,
        "raw_sentinels": 5,
    }


def test_raw_report_summary_lines_formats_report() -> None:
    report = {
        "article_count": 1,
        "corpus_summary": {
            "defect_counts": {"R01": 1},
            "totals": {
                "bytes": 10,
                "img_tags": 1,
                "figure_labels": 2,
                "table_labels": 3,
                "page_headers": 4,
                "raw_sentinels": 5,
            },
        },
        "articles": [_article("one", ["R01"])],
    }

    assert raw_report_summary_lines(report) == [
        "EN raw audit: 1 artifact(s)",
        "Totals: bytes=10 img=1 figure_labels=2 table_labels=3 page_headers=4 raw_sentinels=5",
        "Defects by check: R01=1",
        "- one: bytes=10 img=1 fig=2 tables=3 headers=4 defects=1",
    ]
