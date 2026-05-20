import json
from pathlib import Path

from scripts.llm_quality_loop import (
    assess_polish_html,
    build_analysis_pack,
    evaluate_quality_gate,
    render_llm_prompt,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_quality_gate_fails_on_regressions_and_critical_metric_growth() -> None:
    comparison = {
        "status": "ok",
        "totals_delta": {
            "score": 4,
            "defects": 1,
            "broken_internal_links": 1,
        },
        "regressions": [
            {
                "article": "article_a",
                "score_delta": 4,
                "defects_delta": 1,
                "errors_delta": 0,
            }
        ],
        "improvements": [],
    }
    gate_config = {
        "max_regressions": 0,
        "max_total_deltas": {
            "score": 0,
            "defects": 0,
            "broken_internal_links": 0,
        },
        "max_article_deltas": {"score_delta": 0},
    }

    report = evaluate_quality_gate(comparison, gate_config)

    assert report["status"] == "fail"
    assert {failure["kind"] for failure in report["failures"]} == {
        "regressions",
        "total_delta",
        "article_delta",
    }


def test_quality_gate_passes_when_lower_is_better_metrics_do_not_increase() -> None:
    comparison = {
        "status": "ok",
        "totals_delta": {
            "score": -10,
            "defects": -1,
            "broken_internal_links": 0,
        },
        "regressions": [],
        "improvements": [{"article": "article_a", "score_delta": -10}],
    }
    gate_config = {
        "max_regressions": 0,
        "max_total_deltas": {"score": 0, "defects": 0, "broken_internal_links": 0},
    }

    report = evaluate_quality_gate(comparison, gate_config)

    assert report["status"] == "pass"
    assert report["improvement_count"] == 1


def test_analysis_pack_filters_ignored_defects_and_adds_pattern_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {"defect_counts": {"P20": 1, "P67": 1}},
            "articles": [
                {
                    "article": "article_a",
                    "raw_stage_path": "raw.html",
                    "polish_stage_path": "polish.html",
                    "summary": {"polish_ref_links": 2},
                    "defects_found": [
                        {
                            "id": "P20",
                            "severity": "error",
                            "check": "Missing image",
                            "snippet": "missing image",
                        },
                        {
                            "id": "P67",
                            "severity": "warning",
                            "check": "Text residue",
                            "snippet": "bad text",
                            "hypothesis": "cleanup missed it",
                        },
                    ],
                }
            ],
        },
    )
    _write_json(
        run_dir / "assessment.json",
        {
            "article_count": 1,
            "totals": {"ref_links": 2},
            "articles": [{"article": "article_a", "href_counts": {"ref_links": 2}}],
        },
    )
    _write_json(
        run_dir / "quality_history_entry.json",
        {
            "run_id": "run_a",
            "totals": {"score": 3},
            "articles": {
                "article_a": {
                    "score": 3,
                    "labels": {"profile_style": "bracket_numeric"},
                    "metrics": {"ref_links": 2},
                }
            },
        },
    )
    _write_json(
        run_dir / "quality_compare.json",
        {
            "status": "ok",
            "totals_delta": {"score": -1},
            "regressions": [],
            "improvements": [{"article": "article_a", "score_delta": -1}],
            "unchanged": [],
        },
    )
    _write_json(run_dir / "manifest.json", {"article_count": 1, "code_commit": "abc123"})

    pack = build_analysis_pack(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": ["P20"]},
        defect_patterns={"P67": {"pattern": "text-cleanup", "criticality": "medium", "fix_layer": "polish"}},
    )

    article = pack["articles"][0]
    assert article["article"] == "article_a"
    assert article["defect_ids"] == {"P67": 1}
    assert article["defects"][0]["known_pattern"] == "text-cleanup"
    assert "P20" not in article["defect_ids"]
    prompt = render_llm_prompt(pack)
    assert "article_a" in prompt
    assert "text-cleanup" in prompt


def test_assessment_warning_count_ignores_css_selector_without_body_warning() -> None:
    html = (
        "<html><head><style>p.z2m-missing-figure-warning { color: red; }</style></head>"
        "<body><p>No warning block here.</p></body></html>"
    )

    assessment = assess_polish_html("article_a", html, {"status": "ok", "style": "unknown", "confidence": "low"})

    assert assessment["missing_warning_count"] == 0


def test_assessment_does_not_count_bracket_link_after_unit_sup_as_mixed_style() -> None:
    html = (
        "<html><body>"
        '<p>Volume was 20 cm <sup>3</sup> [<a href="#ref-6" class="z2m-ref-link">6</a>].</p>'
        '<ol><li id="ref-6">Reference.</li></ol>'
        "</body></html>"
    )

    assessment = assess_polish_html(
        "article_a",
        html,
        {"status": "ok", "style": "bracket_numeric", "confidence": "medium"},
    )

    assert assessment["sup_ref_links"] == 0
    assert assessment["href_counts"]["ref_links"] == 1
    assert assessment["mixed_citation_style"] is False
