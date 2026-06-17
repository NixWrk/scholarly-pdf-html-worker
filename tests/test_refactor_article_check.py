import json
from pathlib import Path

from pdf_html_polish.quality_loop.article_check import build_refactor_article_check


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_minimal_run(run_dir: Path) -> None:
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "audit_status": "complete",
            "article_count": 2,
            "corpus_summary": {
                "defect_counts": {},
                "observed_defect_counts": {"P04N": 1},
            },
            "articles": [
                {
                    "article": "article_a",
                    "defects_found": [
                        {
                            "id": "P04N",
                            "severity": "warning",
                            "extra": {"quality_counted": False},
                        }
                    ],
                },
                {"article": "article_b", "defects_found": []},
            ],
        },
    )
    _write_json(
        run_dir / "quality_history_entry.json",
        {
            "totals": {
                "defects": 0,
                "errors": 0,
                "warnings": 0,
                "broken_internal_links": 0,
                "external_page_query_links": 0,
            }
        },
    )
    _write_json(run_dir / "assessment.json", {"totals": {}})
    _write_json(
        run_dir / "quality_gate_report.json",
        {
            "status": "fail",
            "failures": [
                {"kind": "article_review_stage"},
                {"kind": "mandatory_review_pending"},
            ],
        },
    )
    _write_json(run_dir / "llm_analysis_pack.json", {"articles": [{"article": "article_a"}]})


def test_refactor_article_check_allows_non_quality_observed_diagnostics(tmp_path: Path) -> None:
    _write_minimal_run(tmp_path)

    report = build_refactor_article_check(tmp_path, from_pack=True, defect_ids=["P04N"])

    assert report["status"] == "pass"
    assert report["selected_article_count"] == 1
    assert report["selected_summary"]["observed_defect_counts"] == {"P04N": 1}
    assert report["selected_summary"]["quality_defect_counts"] == {}


def test_refactor_article_check_fails_on_hard_link_metric_growth(tmp_path: Path) -> None:
    _write_minimal_run(tmp_path)
    entry = json.loads((tmp_path / "quality_history_entry.json").read_text(encoding="utf-8"))
    entry["totals"]["broken_internal_links"] = 1
    _write_json(tmp_path / "quality_history_entry.json", entry)

    report = build_refactor_article_check(tmp_path, from_pack=True)

    assert report["status"] == "fail"
    assert report["failures"] == [
        {"kind": "hard_link_metric", "metric": "broken_internal_links", "observed": 1}
    ]
