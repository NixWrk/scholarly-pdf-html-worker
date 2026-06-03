import base64
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import scripts.llm_quality_loop as llm_quality_loop
from scripts.llm_quality_loop import (
    assess_polish_html,
    build_analysis_pack,
    evaluate_quality_gate,
    manual_observation_signature,
    normalize_converted_audit_article_ids,
    prepare_converted_raw_cache,
    parse_args,
    prepare_converted_run,
    record_manual_observation,
    repolish_cached_run,
    render_llm_prompt,
    run_audit,
    run_test_command,
    write_pdf_problem_evidence_stage,
    write_p62_image_recovery_stage,
    write_p62_marker_recovery_plan,
    write_source_pdf_map_for_run,
    write_article_review_stage,
    write_manual_review_queue,
    write_manual_observation_summary,
    write_pattern_observations,
    write_resolver_decisions,
)


_VALID_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _valid_tiny_png_bytes() -> bytes:
    return base64.b64decode(_VALID_TINY_PNG_B64)


def _valid_tiny_png_data_url() -> str:
    return f"data:image/png;base64,{_VALID_TINY_PNG_B64}"


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


def test_quality_gate_uses_comparable_totals_when_corpus_changes() -> None:
    comparison = {
        "status": "ok",
        "totals_delta": {"score": 5, "defects": 2},
        "comparable_totals_delta": {"score": -1, "defects": 0},
        "new_article_count": 1,
        "regressions": [],
        "improvements": [{"article": "article_a", "score_delta": -1}],
    }
    gate_config = {
        "max_regressions": 0,
        "max_total_deltas": {"score": 0, "defects": 0},
    }

    report = evaluate_quality_gate(comparison, gate_config)

    assert report["status"] == "pass"
    assert report["new_article_count"] == 1
    assert report["comparable_totals_delta"] == {"score": -1, "defects": 0}


def test_quality_gate_requires_article_review_stage_when_configured() -> None:
    comparison = {
        "status": "ok",
        "totals_delta": {"score": 0, "defects": 0},
        "regressions": [],
        "improvements": [],
    }
    gate_config = {
        "max_regressions": 0,
        "max_total_deltas": {"score": 0, "defects": 0},
        "require_article_review_stage": True,
    }

    missing_report = evaluate_quality_gate(comparison, gate_config)

    assert missing_report["status"] == "fail"
    assert {failure["kind"] for failure in missing_report["failures"]} == {"article_review_stage_missing"}

    ready_report = evaluate_quality_gate(
        comparison,
        gate_config,
        article_review_report={
            "status": "ready",
            "review_dir": "article_review",
            "mandatory_count": 2,
            "pending_mandatory_count": 2,
            "selected_count": 2,
        },
    )

    assert ready_report["status"] == "pass"
    assert ready_report["article_review_stage"]["pending_mandatory_count"] == 2


def test_quality_gate_fails_when_mandatory_article_review_is_pending() -> None:
    comparison = {
        "status": "ok",
        "totals_delta": {"score": 0, "defects": 0},
        "regressions": [],
        "improvements": [],
    }
    gate_config = {
        "max_regressions": 0,
        "max_total_deltas": {"score": 0, "defects": 0},
        "require_article_review_stage": True,
        "max_pending_mandatory_reviews": 0,
    }

    report = evaluate_quality_gate(
        comparison,
        gate_config,
        article_review_report={
            "status": "ready",
            "review_dir": "article_review",
            "mandatory_count": 2,
            "pending_mandatory_count": 1,
            "selected_count": 2,
        },
    )

    assert report["status"] == "fail"
    assert {failure["kind"] for failure in report["failures"]} == {"mandatory_review_pending"}


def test_quality_gate_requires_pdf_text_and_problem_evidence_when_configured() -> None:
    comparison = {
        "status": "ok",
        "totals_delta": {"score": 0, "defects": 0},
        "regressions": [],
        "improvements": [],
    }
    gate_config = {
        "max_regressions": 0,
        "max_total_deltas": {"score": 0, "defects": 0},
        "require_pdf_text_layer_diagnostics": True,
        "require_pdf_problem_evidence_stage": True,
    }

    missing_report = evaluate_quality_gate(comparison, gate_config)

    assert missing_report["status"] == "fail"
    assert {
        "pdf_text_layer_diagnostics_missing",
        "pdf_problem_evidence_stage_missing",
    }.issubset({failure["kind"] for failure in missing_report["failures"]})

    ready_report = evaluate_quality_gate(
        comparison,
        gate_config,
        audit_report={
            "corpus_summary": {"totals": {"source_pdf_present": 2, "pdf_text_chars": 1200}}
        },
        audit_command_report={"pdf_diagnostics_enabled": True, "pdf_map_path": "source_pdf_map.json"},
        pdf_problem_evidence_report={
            "status": "ready",
            "report_path": "pdf_problem_evidence_report.json",
            "evidence_dir": "pdf_problem_evidence",
            "selected_count": 1,
            "ready_count": 1,
            "blocking_issue_count": 0,
            "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
        },
    )

    assert ready_report["status"] == "pass"
    assert ready_report["pdf_text_layer_diagnostics"]["pdf_text_chars"] == 1200
    assert ready_report["pdf_problem_evidence_stage"]["ready_count"] == 1


def test_write_article_review_stage_builds_mandatory_bundle(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    stage_dir = run_dir / "article_a" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw_path = stage_dir / "01.en.raw.html"
    polish_path = stage_dir / "02.en.polish.html"
    raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
    polish_path.write_text("<html><body><p>Changed polish.</p></body></html>", encoding="utf-8")

    report = write_article_review_stage(
        run_dir,
        [
            {
                "article": "article_a",
                "source_article": "Article A",
                "mandatory_review": True,
                "mandatory_review_reason": "changed_without_quality_delta",
                "review_status": "pending",
                "raw_stage_path": str(raw_path),
                "polish_stage_path": str(polish_path),
            }
        ],
        max_articles=0,
    )

    assert report["status"] == "ready"
    assert report["mandatory_count"] == 1
    assert report["pending_mandatory_count"] == 1
    assert report["selected_count"] == 1
    assert Path(report["index_html"]).is_file()
    assert Path(report["articles"][0]["review_html"]).is_file()
    assert "Changed polish." in Path(report["articles"][0]["review_html"]).read_text(encoding="utf-8")


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
    assert "focused artifact regression" in prompt


def test_write_resolver_decisions_splits_observed_signals_and_pack_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {"defect_counts": {"P04T": 1, "P62": 1, "P04N": 1, "P71": 1, "P67": 1}},
            "articles": [
                {
                    "article": "article_a",
                    "raw_stage_path": "raw.html",
                    "polish_stage_path": "polish.html",
                    "summary": {
                        "source_pdf_present": True,
                        "source_pdf_path": "paper.pdf",
                        "pdf_text_status": "pymupdf",
                    },
                    "defects_found": [
                        {"id": "P04T", "severity": "warning", "check": "table numeric range", "extra": {"quality_counted": False}},
                        {
                            "id": "P62",
                            "severity": "warning",
                            "check": "missing figure warning",
                            "extra": {"quality_counted": False, "warning_origin": "caption-only-target"},
                        },
                        {"id": "P04N", "severity": "warning", "check": "citation-like range", "extra": {"quality_counted": False}},
                        {
                            "id": "P71",
                            "severity": "warning",
                            "check": "source OCR residue",
                            "extra": {"quality_counted": False, "source_pdf_text_layer_evidence": True},
                        },
                        {"id": "P67", "severity": "error", "check": "quality counted text defect"},
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})
    _write_json(run_dir / "quality_history_entry.json", {"run_id": "run_a", "totals": {}, "articles": {"article_a": {"score": 1}}})
    _write_json(run_dir / "quality_compare.json", {"status": "ok", "regressions": [], "improvements": []})
    _write_json(run_dir / "manifest.json", {"article_count": 1, "source_kind": "test"})

    report = write_resolver_decisions(run_dir)

    assert report["decision_counts"]["accepted_telemetry"] == 2
    assert report["decision_counts"]["needs_pdf_recovery"] == 1
    assert report["decision_counts"]["needs_pdf_reference_recovery"] == 1
    assert report["decision_counts"]["needs_repair"] == 1
    assert report["accepted_telemetry_counts"] == {"P04T": 1, "P71": 1}
    assert report["repair_candidate_counts"] == {"P04N": 1, "P62": 1}

    pack = build_analysis_pack(run_dir, gate_config={"ignored_defect_ids_for_analysis": []})
    assert pack["resolver_decisions"]["repair_candidate_counts"] == {"P04N": 1, "P62": 1}
    assert pack["articles"][0]["resolver_decisions"][0]["article"] == "article_a"
    assert "Observed Resolver Decisions" in render_llm_prompt(pack)


def test_analysis_pack_lists_changed_articles_without_quality_delta(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {"defect_counts": {}},
            "articles": [
                {
                    "article": "article_a",
                    "raw_stage_path": "raw_a.html",
                    "polish_stage_path": "polish_a.html",
                    "defects_found": [],
                },
                {
                    "article": "article_b",
                    "raw_stage_path": "raw_b.html",
                    "polish_stage_path": "polish_b.html",
                    "defects_found": [],
                },
            ],
        },
    )
    _write_json(run_dir / "assessment.json", {"article_count": 2, "totals": {}, "articles": []})
    _write_json(
        run_dir / "quality_history_entry.json",
        {
            "run_id": "run_changed",
            "totals": {"score": 5},
            "articles": {
                "article_a": {"score": 5, "defect_ids": {"P61": 1}},
                "article_b": {"score": 2, "defect_ids": {}},
            },
        },
    )
    _write_json(
        run_dir / "quality_compare.json",
        {
            "status": "ok",
            "regressions": [],
            "improvements": [{"article": "article_b", "score_delta": -1}],
            "unchanged": [{"article": "article_a", "score_delta": 0}],
        },
    )
    _write_json(
        run_dir / "manifest.json",
        {
            "article_count": 2,
            "articles": [
                {
                    "article_id": "article_a",
                    "article": "Doc A",
                    "changed": True,
                    "raw_stage_path": "raw_a.html",
                    "polish_stage_path": "polish_a.html",
                },
                {"article_id": "article_b", "article": "Doc B", "changed": True},
            ],
        },
    )

    pack = build_analysis_pack(run_dir, gate_config={"ignored_defect_ids_for_analysis": []})

    assert pack["mandatory_changed_review_count"] == 1
    assert pack["mandatory_changed_review_articles"][0]["article"] == "article_a"
    assert pack["mandatory_changed_review_articles"][0]["reason"] == "changed_without_quality_delta"
    prompt = render_llm_prompt(pack)
    assert "Mandatory Changed-Article Review" in prompt
    assert "article_a" in prompt


def test_analysis_pack_adds_zotero_source_pdf_candidates(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source_run = tmp_path / "source_run"
    html_root = tmp_path / "html"
    article_id = "Lib_KEY_123_Article"
    converted_raw = html_root / "converted" / "Lib" / "KEY" / "123" / "Article" / "_z2m_stages" / "01.en.raw.html"
    source_export = html_root / "source_exports" / "Lib" / "KEY" / "123"
    source_pdf = tmp_path / "zotero" / "storage" / "KEY" / "paper.pdf"
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"%PDF-1.4\n")

    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {"defect_counts": {"P59": 1}},
            "articles": [
                {
                    "article": article_id,
                    "summary": {
                        "source_pdf_path": str(run_dir / "missing.pdf"),
                        "source_pdf_present": False,
                        "source_pdf_origin": "stage",
                    },
                    "defects_found": [
                        {
                            "id": "P59",
                            "severity": "error",
                            "check": "false bibliography link",
                            "snippet": "figures 3 and 4",
                        }
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})
    _write_json(
        run_dir / "quality_history_entry.json",
        {"run_id": "run_a", "totals": {"score": 1}, "articles": {article_id: {"score": 1}}},
    )
    _write_json(run_dir / "quality_compare.json", {"status": "ok", "regressions": [], "improvements": []})
    _write_json(run_dir / "manifest.json", {"article_count": 1, "source_run_dir": str(source_run), "articles": []})
    _write_json(
        source_run / "manifest.json",
        {"articles": [{"article_id": article_id, "raw_stage_path": str(converted_raw)}]},
    )
    _write_json(source_export / "manifest.json", {"source_pdf": str(source_pdf)})

    pack = build_analysis_pack(run_dir, gate_config={"ignored_defect_ids_for_analysis": []})
    candidates = pack["articles"][0]["source_pdf_candidates"]

    assert candidates[0]["exists"] is True
    assert candidates[0]["path"] == str(source_pdf.resolve(strict=False))


def test_analysis_pack_falls_back_to_zotero_storage_by_attachment_key(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    zotero_root = tmp_path / "zotero"
    attachment_key = "KEY12345"
    article_id = f"Zotero_Elvis_D_{attachment_key}_571527_Article"
    source_pdf = zotero_root / "Zotero_Elvis_Data" / "storage" / attachment_key / "paper.pdf"
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("ZOTERO_PATH_PREFIX_MAP", f"/zotero_roots/pc_zotero={zotero_root}")

    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {"defect_counts": {"P33": 1}},
            "articles": [
                {
                    "article": article_id,
                    "summary": {"source_pdf_present": False},
                    "defects_found": [
                        {
                            "id": "P33",
                            "severity": "error",
                            "check": "semantic reference still points to page",
                            "snippet": "see [29]",
                        }
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})
    _write_json(
        run_dir / "quality_history_entry.json",
        {"run_id": "run_a", "totals": {"score": 1}, "articles": {article_id: {"score": 1}}},
    )
    _write_json(run_dir / "quality_compare.json", {"status": "ok", "regressions": [], "improvements": []})
    _write_json(run_dir / "manifest.json", {"article_count": 1, "articles": []})

    pack = build_analysis_pack(run_dir, gate_config={"ignored_defect_ids_for_analysis": []})
    candidates = pack["articles"][0]["source_pdf_candidates"]

    assert candidates[0]["exists"] is True
    assert candidates[0]["path"] == str(source_pdf.resolve(strict=False))
    assert candidates[0]["source"] == f"zotero_storage.{attachment_key}"


def test_source_pdf_map_resolves_existing_candidates_for_pdf_diagnostics(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    zotero_root = tmp_path / "zotero"
    attachment_key = "KEY12345"
    article_id = f"Zotero_Elvis_D_{attachment_key}_571527_Article"
    source_pdf = zotero_root / "Zotero_Elvis_Data" / "storage" / attachment_key / "paper.pdf"
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("ZOTERO_PATH_PREFIX_MAP", f"/zotero_roots/pc_zotero={zotero_root}")

    report = write_source_pdf_map_for_run(
        run_dir,
        {"articles": [{"article_id": article_id, "article": "Article"}]},
    )

    assert report["status"] == "ready"
    assert report["mapped_count"] == 1
    assert report["records"][0]["pdf_path"] == str(source_pdf.resolve(strict=False))
    assert (run_dir / "source_pdf_map.json").is_file()


def test_pdf_problem_evidence_stage_requires_render_and_text_layer(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    def fake_pages(pdf_path: Path, *, max_pages: int | None = None):
        assert pdf_path == source_pdf
        assert max_pages == 80
        return "fake", ["First page.", "The PDF text layer has the correct DOI boundary."], None

    def fake_render(pdf_path: Path, page_number: int, out_path: Path, *, zoom: float):
        assert page_number == 2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"png")
        return {"status": "rendered", "path": str(out_path), "error": ""}

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_pages)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fake_render)

    report = write_pdf_problem_evidence_stage(
        run_dir,
        {
            "articles": [
                {
                    "article": "article_a",
                    "source_pdf_candidates": [{"path": str(source_pdf), "exists": True, "source": "test"}],
                    "defects": [
                        {
                            "id": "P75",
                            "snippet": "correct DOI boundary",
                        }
                    ],
                }
            ]
        },
        gate_config={"pdf_problem_evidence_max_articles": 12, "pdf_problem_evidence_render_zoom": 1.0},
    )

    article = report["articles"][0]
    assert report["status"] == "ready"
    assert article["status"] == "ready"
    assert article["evidence_page"] == 2
    assert article["text_layer_status"] == "fake"
    assert Path(article["text_layer_excerpt_path"]).is_file()
    assert Path(article["page_render_path"]).is_file()


def test_p62_marker_recovery_plan_builds_single_page_marker_command(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    warning = (
        "Figure 6 image was not extracted into this HTML. "
        "Please check the original PDF for the missing visual content."
    )
    caption = (
        "Fig. 6. A heat map showing the relative time difference spent at each point "
        "in the T-maze, U-maze and Z-maze in sessions 13-14 compared to sessions 1-2."
    )
    polish_path.write_text(
        '<div id="fig-5" class="z2m-figure-unit">'
        '<p><img src="data:image/jpeg;base64,'
        + ("A" * 800)
        + '"/></p><p>Figure 5 | Properties of autonomous discovery.</p></div>'
        f'<div id="fig-6" class="z2m-missing-figure-unit">'
        f'<p class="z2m-missing-figure-warning">{warning}</p>'
        f'<p class="z2m-figure-caption">{caption}</p></div>',
        encoding="utf-8",
    )
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "article_a",
                    "polish_stage_path": str(polish_path),
                    "summary": {
                        "source_pdf_present": True,
                        "source_pdf_path": str(source_pdf),
                    },
                    "defects_found": [
                        {
                            "id": "P62",
                            "severity": "warning",
                            "check": "missing figure warning",
                            "snippet": warning,
                            "extra": {
                                "quality_counted": False,
                                "warning_index": 1,
                                "figure_label": "6",
                                "warning_origin": "caption-only-target",
                            },
                        }
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})
    _write_json(run_dir / "quality_history_entry.json", {"run_id": "run_a", "totals": {}, "articles": {}})
    _write_json(run_dir / "quality_compare.json", {"status": "ok", "regressions": [], "improvements": []})

    def fake_pages(pdf_path: Path, *, max_pages: int | None = None):
        assert pdf_path == source_pdf
        assert max_pages == 80
        return (
            "fake",
            [
                "Figure 5 | Properties of autonomous discovery with autonomous research agents.",
                "The study reports Fig. 6 as a heat map showing the relative time difference "
                "spent at each point in the T-maze U-maze and Z-maze.",
            ],
            None,
        )

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_pages)

    report = write_p62_marker_recovery_plan(
        run_dir,
        gate_config={
            "p62_marker_recovery_max_articles": 0,
            "p62_marker_recovery_max_pdf_pages": 80,
            "p62_marker_recovery_context_chars": 1200,
            "p62_marker_recovery_min_match_score": 0.05,
        },
    )

    article = report["articles"][0]
    assert report["status"] == "ready"
    assert report["candidate_count"] == 1
    assert article["status"] == "ready"
    assert article["source_pdf_page_number"] == 2
    assert article["marker_page_number_zero_based"] == 1
    assert article["marker_page_range"] == "1"
    assert article["marker_command"][article["marker_command"].index("--page_range") + 1] == "1"
    assert "--disable_multiprocessing" in article["marker_command"]
    assert article["existing_marker_output_validation"]["status"] == "not_run"
    assert report["marker_output_status_counts"] == {"not_run": 1}
    assert Path(article["polish_context_path"]).is_file()
    assert Path(article["source_pdf_page_excerpt_path"]).is_file()

    marker_output = Path(article["marker_output_dir"]) / "paper"
    marker_output.mkdir(parents=True)
    (marker_output / "paper.html").write_text("<p>Figure 6 | recovered caption only</p>", encoding="utf-8")
    caption_only_report = write_p62_marker_recovery_plan(
        run_dir,
        gate_config={
            "p62_marker_recovery_max_articles": 0,
            "p62_marker_recovery_max_pdf_pages": 80,
            "p62_marker_recovery_context_chars": 1200,
            "p62_marker_recovery_min_match_score": 0.05,
        },
    )
    assert caption_only_report["articles"][0]["existing_marker_output_validation"]["status"] == "caption_only"

    (marker_output / "_page_1_Figure_1.jpeg").write_bytes(b"jpg")
    recovered_report = write_p62_marker_recovery_plan(
        run_dir,
        gate_config={
            "p62_marker_recovery_max_articles": 0,
            "p62_marker_recovery_max_pdf_pages": 80,
            "p62_marker_recovery_context_chars": 1200,
            "p62_marker_recovery_min_match_score": 0.05,
        },
    )
    assert recovered_report["marker_output_status_counts"] == {"recovered_image": 1}

    pack = build_analysis_pack(run_dir, gate_config={"ignored_defect_ids_for_analysis": ["P62"]})
    assert pack["articles"] == []
    assert pack["p62_marker_recovery_plan"]["ready_count"] == 1
    prompt = render_llm_prompt(pack)
    assert "p62_marker_recovery_status" in prompt
    assert "P62 Marker Recovery Plan" in prompt


def test_p62_recovery_replaces_missing_warning_with_image() -> None:
    html = (
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 6 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">Figure 6. Caption survived.</p>'
        "</div>"
    )

    patched, replacements = llm_quality_loop._replace_p62_missing_warning_with_image(
        html,
        figure_label="6",
        warning_index=1,
        data_url=_valid_tiny_png_data_url(),
        source="pdf_page_render",
        source_detail="page_0006.png",
    )

    assert replacements == 1
    assert "z2m-missing-figure-warning" not in patched
    assert "z2m-missing-figure-unit" not in patched
    assert "z2m-p62-recovered-target" in patched
    assert 'data-z2m-recovery-source="pdf_page_render"' in patched
    assert "Figure 6. Caption survived." in patched


def test_p62_image_recovery_stage_renders_pdf_fallback_and_patches_html(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    warning = (
        "Figure 6 image was not extracted into this HTML. "
        "Please check the original PDF for the missing visual content."
    )
    polish_path.write_text(
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        f'<p class="z2m-missing-figure-warning z2m-figure-target" role="note">{warning}</p>'
        '<p class="z2m-figure-caption">Fig. 6. A heat map of the maze sessions.</p>'
        "</div>",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "article_a",
                    "polish_stage_path": str(polish_path),
                    "summary": {
                        "source_pdf_present": True,
                        "source_pdf_path": str(source_pdf),
                    },
                    "defects_found": [
                        {
                            "id": "P62",
                            "severity": "warning",
                            "check": "missing figure warning",
                            "snippet": warning,
                            "extra": {
                                "quality_counted": False,
                                "warning_index": 1,
                                "figure_label": "6",
                                "warning_origin": "caption-only-target",
                            },
                        }
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_pages(pdf_path: Path, *, max_pages: int | None = None):
        assert pdf_path == source_pdf
        return (
            "fake",
            [
                "Figure 5 | Previous figure.",
                "Fig. 6. A heat map of the maze sessions.",
            ],
            None,
        )

    def fake_render(pdf_path: Path, page_number: int, out_path: Path, *, zoom: float):
        assert pdf_path == source_pdf
        assert page_number == 2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(_valid_tiny_png_bytes())
        return {"status": "rendered", "path": str(out_path), "error": ""}

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_pages)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fake_render)
    monkeypatch.setattr(
        llm_quality_loop,
        "_p62_render_fallback_page_number",
        lambda pdf_path, source_page_number, figure_label: (source_page_number, "test_primary_page"),
    )

    write_p62_marker_recovery_plan(
        run_dir,
        gate_config={
            "p62_marker_recovery_max_articles": 0,
            "p62_marker_recovery_max_pdf_pages": 80,
            "p62_marker_recovery_context_chars": 1200,
            "p62_marker_recovery_min_match_score": 0.05,
        },
    )
    report = write_p62_image_recovery_stage(
        run_dir,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["asset_ready_count"] == 1
    assert report["patched_warning_count"] == 1
    assert report["recovery_source_counts"] == {"pdf_page_render": 1}
    patched_html = polish_path.read_text(encoding="utf-8")
    assert "z2m-missing-figure-warning" not in patched_html
    assert "z2m-p62-recovered-target" in patched_html
    assert (run_dir / "assessment.json").is_file()


def test_observe_runs_configured_tests_by_default() -> None:
    args = parse_args(
        [
            "observe",
            "--source-run-dir",
            "source_run",
            "--out-dir",
            "out_run",
            "--max-review-articles",
            "7",
        ]
    )

    assert args.run_tests is True
    assert args.max_review_articles == 7

    args = parse_args(
        [
            "observe",
            "--source-run-dir",
            "source_run",
            "--out-dir",
            "out_run",
            "--skip-tests",
        ]
    )

    assert args.run_tests is False


def test_observe_accepts_converted_raw_repolish_mode() -> None:
    args = parse_args(
        [
            "observe",
            "--converted-roots",
            "converted_root",
            "--repolish-converted-raw",
            "--out-dir",
            "out_run",
        ]
    )

    assert args.converted_roots == [Path("converted_root")]
    assert args.repolish_converted_raw is True
    assert args.skip_non_target_language is True
    assert args.polish_language == "auto"


def test_recover_p62_command_uses_configured_marker_mode_by_default() -> None:
    default_args = parse_args(["recover-p62", "--run-dir", "run"])
    run_marker_args = parse_args(["recover-p62", "--run-dir", "run", "--run-marker"])
    skip_marker_args = parse_args(["recover-p62", "--run-dir", "run", "--skip-marker"])

    assert default_args.execute_marker is None
    assert run_marker_args.execute_marker is True
    assert skip_marker_args.execute_marker is False


def test_render_llm_prompt_requires_artifact_regression_tests() -> None:
    prompt = render_llm_prompt(
        {
            "run_id": "run_a",
            "ignored_defect_ids": [],
            "articles": [],
        }
    )

    assert "Every production artifact fix must include a focused regression test" in prompt
    assert "guard/negative test" in prompt
    assert "full configured project test suite" in prompt
    assert "all cached raw files are scanned" in prompt
    assert "every accepted EN article is repolished" in prompt
    assert "Pattern observations must be accumulated globally across loop iterations" in prompt
    assert "manual observation ledger" in prompt
    assert "refine the P classification" in prompt
    assert "render the implicated source PDF page" in prompt
    assert "extract the PDF text layer" in prompt
    assert "PDF page render and text-layer evidence" in prompt
    assert "pdf_problem_evidence_status" in prompt
    assert "source_pdf_candidates" in prompt
    assert "search the Zotero/source_exports PDF candidates" in prompt
    assert "p62_marker_recovery_status" in prompt


def test_manual_observation_summary_accumulates_raw_manifestations(tmp_path: Path) -> None:
    ledger_path = tmp_path / "manual_observation_ledger.jsonl"
    first = record_manual_observation(
        ledger_path,
        {
            "created_at": "2026-05-25T00:00:00+00:00",
            "run_id": "run1",
            "article": "article_a",
            "stage_path": "article_a/02.en.polish.html",
            "snippet": "The article shows Objec tive split in a heading.",
            "suspected_pattern": "inline OCR word split in ordinary text",
        },
    )
    second = record_manual_observation(
        ledger_path,
        {
            "created_at": "2026-05-25T01:00:00+00:00",
            "run_id": "run2",
            "article": "article_b",
            "stage_path": "article_b/02.en.polish.html",
            "snippet": "The body contains meth ods after an inline span.",
            "suspected_pattern": "inline OCR word split in ordinary text",
        },
    )
    run_dir = tmp_path / "run2"
    _write_json(run_dir / "quality_history_entry.json", {"run_id": "run2"})

    summary = write_manual_observation_summary(run_dir, ledger_path=ledger_path)

    assert first["normalized_signature"] == second["normalized_signature"]
    assert ledger_path.read_text(encoding="utf-8").count("\n") == 2
    assert summary["observation_count"] == 2
    assert summary["group_count"] == 1
    candidate = summary["problem_candidates"][0]
    assert candidate["problem_state"] == "problem_candidate"
    assert candidate["article_count"] == 2
    assert candidate["run_count"] == 2
    assert candidate["statuses"] == {"untriaged": 2}
    assert [sample["article"] for sample in candidate["sample_observations"]] == ["article_a", "article_b"]


def test_manual_observation_summary_uses_latest_status_for_same_observation(tmp_path: Path) -> None:
    ledger_path = tmp_path / "manual_observation_ledger.jsonl"
    base_observation = {
        "observation_id": "manual-known-1",
        "run_id": "run1",
        "article": "article_a",
        "stage_path": "article_a/02.en.polish.html",
        "snippet": "Objec tive split remains.",
        "suspected_pattern": "inline OCR word split in ordinary text",
    }
    record_manual_observation(
        ledger_path,
        {
            **base_observation,
            "created_at": "2026-05-25T00:00:00+00:00",
            "status": "untriaged",
            "test_status": "none",
        },
    )
    record_manual_observation(
        ledger_path,
        {
            **base_observation,
            "created_at": "2026-05-25T01:00:00+00:00",
            "status": "covered_by_test",
            "test_status": "repair",
        },
    )

    summary = write_manual_observation_summary(tmp_path / "run", ledger_path=ledger_path)

    assert summary["ledger_entry_count"] == 2
    assert summary["observation_count"] == 1
    group = summary["groups"][0]
    assert group["statuses"] == {"covered_by_test": 1}
    assert group["test_statuses"] == {"repair": 1}
    assert summary["requires_triage"] == []


def test_manual_observation_signature_falls_back_to_normalized_text() -> None:
    signature = manual_observation_signature(
        {
            "article": "article_a",
            "snippet": "<span>Figure 12</span> has residue 34",
        }
    )

    assert signature == "text:figure_has_residue"


def test_analysis_pack_includes_manual_observation_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(run_dir / "audit_full_checks.json", {"corpus_summary": {"defect_counts": {}}, "articles": []})
    _write_json(run_dir / "assessment.json", {"article_count": 0, "totals": {}, "articles": []})
    _write_json(run_dir / "quality_history_entry.json", {"run_id": "run_a", "totals": {}, "articles": {}})
    _write_json(run_dir / "quality_compare.json", {"status": "ok", "regressions": [], "improvements": []})
    _write_json(run_dir / "manifest.json", {"article_count": 0})
    _write_json(
        run_dir / "manual_observation_summary.json",
        {
            "ledger_path": "manual.jsonl",
            "observation_count": 1,
            "group_count": 1,
            "problem_candidates": [
                {
                    "normalized_signature": "pattern:inline_ocr_word_split",
                    "problem_state": "problem_candidate",
                    "run_count": 1,
                    "article_count": 2,
                    "occurrence_count": 2,
                    "statuses": {"untriaged": 2},
                    "sample_observations": [{"article": "article_a", "snippet": "Objec tive"}],
                }
            ],
            "requires_triage": [
                {
                    "normalized_signature": "pattern:inline_ocr_word_split",
                    "article_count": 2,
                    "sample_observations": [{"article": "article_a", "snippet": "Objec tive"}],
                }
            ],
            "groups": [],
        },
    )

    pack = build_analysis_pack(run_dir)
    prompt = render_llm_prompt(pack)

    assert pack["manual_observations"]["observation_count"] == 1
    assert pack["manual_observations"]["problem_candidates"][0]["normalized_signature"] == (
        "pattern:inline_ocr_word_split"
    )
    assert "Manual Observation Ledger" in prompt
    assert "pattern:inline_ocr_word_split" in prompt


def test_record_observation_command_is_parsed() -> None:
    args = parse_args(
        [
            "record-observation",
            "--ledger",
            "manual.jsonl",
            "--article",
            "article_a",
            "--snippet",
            "bad split",
        ]
    )

    assert args.command == "record-observation"
    assert args.ledger == Path("manual.jsonl")
    assert args.observation_id is None
    assert args.status == "untriaged"
    assert args.test_status == "none"


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


def test_assessment_ignores_data_availability_reference_number_as_mixed_style() -> None:
    html = (
        "<html><body>"
        '<p>The indoor OD dataset<sup><a href="#ref-33" class="z2m-ref-link">33</a></sup> was used.</p>'
        "<h2>Data availability</h2>"
        "<p>The data that support the findings of this study are openly available in the Kaggle repository, "
        'reference number <a href="#ref-33" class="z2m-ref-link">[33]</a>.</p>'
        '<ol><li id="ref-33">Dataset reference.</li></ol>'
        "</body></html>"
    )

    assessment = assess_polish_html(
        "article_a",
        html,
        {"status": "ok", "style": "unknown", "confidence": "low"},
    )

    assert assessment["sup_ref_links"] == 1
    assert assessment["bracket_ref_links"] == 0
    assert assessment["href_counts"]["ref_links"] == 2
    assert assessment["mixed_citation_style"] is False


def test_assessment_counts_inline_bracket_link_as_mixed_style() -> None:
    html = (
        "<html><body>"
        '<p>The indoor OD dataset<sup><a href="#ref-33" class="z2m-ref-link">33</a></sup> was used, '
        'but a later paragraph cites <a href="#ref-12" class="z2m-ref-link">[12]</a>.</p>'
        '<ol><li id="ref-12">Reference.</li><li id="ref-33">Dataset reference.</li></ol>'
        "</body></html>"
    )

    assessment = assess_polish_html(
        "article_a",
        html,
        {"status": "ok", "style": "unknown", "confidence": "low"},
    )

    assert assessment["sup_ref_links"] == 1
    assert assessment["bracket_ref_links"] == 1
    assert assessment["mixed_citation_style"] is True


def test_prepare_converted_run_preserves_duplicate_articles_as_unique_ids(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    for mtime in ("111", "222"):
        stage_dir = root / "lib" / "KEY" / mtime / "Doc" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
        (stage_dir / "02.en.polish.html").write_text(
            '<html><body><p>Polish <a href="#ref-1">[1]</a></p><ol><li id="ref-1">Ref.</li></ol></body></html>',
            encoding="utf-8",
        )

    manifest = prepare_converted_run([root], tmp_path / "run")
    assessment = json.loads((tmp_path / "run" / "assessment.json").read_text(encoding="utf-8"))

    article_ids = [article["article_id"] for article in manifest["articles"]]
    assert manifest["source_kind"] == "converted_stage_roots"
    assert manifest["article_count"] == 2
    assert len(set(article_ids)) == 2
    assert {article["article"] for article in manifest["articles"]} == {"Doc"}
    assert assessment["article_count"] == 2
    assert [article["article"] for article in assessment["articles"]] == article_ids
    assert {article["source_article"] for article in assessment["articles"]} == {"Doc"}


def test_prepare_converted_raw_cache_preserves_source_paths_for_repolish(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    for mtime in ("111", "222"):
        stage_dir = root / "lib" / "KEY" / mtime / "Doc" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text(
            f"<html><body><p>Raw {mtime}</p><p><img src=\"fig1.png\"/></p></body></html>",
            encoding="utf-8",
        )
        (stage_dir / "02.en.polish.html").write_text(
            '<html><body><p><img data-z2m-src="fig1.png" src="data:image/png;base64,AAAA"/></p></body></html>',
            encoding="utf-8",
        )

    manifest = prepare_converted_raw_cache([root], tmp_path / "source")

    article_ids = [article["article_id"] for article in manifest["articles"]]
    assert manifest["source_kind"] == "converted_raw_cache"
    assert manifest["raw_count"] == 2
    assert len(set(article_ids)) == 2
    assert sorted(path.name for path in (tmp_path / "source" / "raw_cache").glob("*.01.en.raw.html")) == [
        f"{article_id}.01.en.raw.html" for article_id in article_ids
    ]
    assert all(Path(article["source_polish_path"]).name == "02.en.polish.html" for article in manifest["articles"])
    assert all(Path(article["raw_stage_path"]).name == "01.en.raw.html" for article in manifest["articles"])


def test_prepare_converted_raw_cache_infers_citation_style_from_raw_html(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "lib" / "KEY" / "111" / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text(
        "<html><body><p>Body cites [1], [2], [3], [4], [5], [6], and [7].</p></body></html>",
        encoding="utf-8",
    )
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")

    manifest = prepare_converted_raw_cache([root], tmp_path / "source")

    article = manifest["articles"][0]
    profile = json.loads(Path(article["profile_path"]).read_text(encoding="utf-8"))
    assert article["profile_status"] == "converted_raw_html_inferred"
    assert article["citation_style"] == "unknown"
    assert article["citation_confidence"] == "low"
    assert profile["source"] == "converted_raw_html"
    assert profile["source_policy"] == "use_inferred_style_only_when_high_confidence"
    assert profile["inferred_style"] == "bracket_numeric"
    assert profile["inferred_confidence"] == "medium"
    assert profile["bracket_numeric_count"] == 7
    assert manifest["profile_status_counts"] == {"converted_raw_html_inferred": 1}
    assert manifest["profile_style_counts"] == {"unknown:low": 1}


def test_prepare_converted_raw_cache_ids_do_not_shift_when_new_sources_appear(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "lib" / "KEY" / "222" / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")
    first = prepare_converted_raw_cache([root], tmp_path / "source1")
    original_id = first["articles"][0]["article_id"]

    earlier_stage_dir = root / "lib" / "AAA" / "111" / "Earlier" / "_z2m_stages"
    earlier_stage_dir.mkdir(parents=True)
    (earlier_stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    (earlier_stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")

    second = prepare_converted_raw_cache([root], tmp_path / "source2")
    ids_by_article = {article["article"]: article["article_id"] for article in second["articles"]}

    assert ids_by_article["Doc"] == original_id
    assert ids_by_article["Earlier"] != original_id


def test_normalize_converted_audit_article_ids_uses_manifest_paths(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    for mtime in ("111", "222"):
        stage_dir = root / "lib" / "KEY" / mtime / "Doc" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
        (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")

    run_dir = tmp_path / "run"
    manifest = prepare_converted_run([root], run_dir)
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "Doc",
                    "raw_stage_path": article["raw_stage_path"],
                    "polish_stage_path": article["polish_stage_path"],
                    "defects_found": [],
                }
                for article in manifest["articles"]
            ]
        },
    )

    audit = normalize_converted_audit_article_ids(run_dir)

    assert [article["article"] for article in audit["articles"]] == [
        article["article_id"] for article in manifest["articles"]
    ]
    assert {article["source_article"] for article in audit["articles"]} == {"Doc"}
    assert all(article["artifact_hint"] for article in audit["articles"])


def test_run_audit_writes_stream_logs_and_command_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    stage_dir = run_dir / "audit_tree" / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish.</p></body></html>", encoding="utf-8")

    run_audit(run_dir)

    report = json.loads((run_dir / "audit_command_report.json").read_text(encoding="utf-8"))
    audit = json.loads((run_dir / "audit_full_checks.json").read_text(encoding="utf-8"))
    assert report["returncode"] == 0
    assert Path(report["stdout_path"]).is_file()
    assert Path(report["stderr_path"]).is_file()
    assert audit["article_count"] == 1


def test_run_test_command_writes_stream_logs_and_command_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    report = run_test_command(f"{json.dumps(sys.executable)} -c \"print('ok')\"", run_dir)

    assert report["returncode"] == 0
    assert Path(report["stdout_path"]).is_file()
    assert Path(report["stderr_path"]).is_file()
    assert "ok" in report["stdout_tail"]
    assert (run_dir / "test_command_report.json").is_file()


def test_write_manual_review_queue_keeps_all_artifacts_and_filters_ignored(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "article_a",
                    "source_article": "Doc A",
                    "raw_stage_path": "raw_a.html",
                    "polish_stage_path": "polish_a.html",
                    "defects_found": [{"id": "P20", "severity": "error", "check": "Missing image"}],
                },
                {
                    "article": "article_b",
                    "source_article": "Doc B",
                    "raw_stage_path": "raw_b.html",
                    "polish_stage_path": "polish_b.html",
                    "defects_found": [{"id": "P67", "severity": "warning", "check": "Text residue"}],
                },
            ]
        },
    )
    _write_json(
        run_dir / "quality_history_entry.json",
        {
            "articles": {
                "article_a": {"score": 3},
                "article_b": {"score": 7},
            }
        },
    )
    _write_json(
        run_dir / "manual_review_queue.json",
        [{"article": "article_b", "review_status": "reviewed", "review_note": "looked real"}],
    )

    queue = write_manual_review_queue(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": ["P20"]},
    )

    assert [item["article"] for item in queue] == ["article_b", "article_a"]
    assert queue[0]["source_article"] == "Doc B"
    assert queue[0]["review_status"] == "reviewed"
    assert queue[0]["non_ignored_defect_ids"] == {"P67": 1}
    assert queue[1]["defect_ids"] == {"P20": 1}
    assert queue[1]["non_ignored_defect_ids"] == {}
    assert queue[1]["review_status"] == "pending"


def test_write_manual_review_queue_prioritizes_changed_articles_without_quality_delta(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "article_a",
                    "raw_stage_path": "raw_a.html",
                    "polish_stage_path": "polish_a.html",
                    "defects_found": [{"id": "P67", "severity": "warning", "check": "Text residue"}],
                },
                {
                    "article": "article_b",
                    "raw_stage_path": "raw_b.html",
                    "polish_stage_path": "polish_b.html",
                    "defects_found": [{"id": "P67", "severity": "warning", "check": "Text residue"}],
                },
            ]
        },
    )
    _write_json(
        run_dir / "quality_history_entry.json",
        {"articles": {"article_a": {"score": 1}, "article_b": {"score": 9}}},
    )
    _write_json(
        run_dir / "quality_compare.json",
        {
            "status": "ok",
            "regressions": [],
            "improvements": [{"article": "article_b", "score_delta": -1}],
            "unchanged": [{"article": "article_a", "score_delta": 0}],
        },
    )
    _write_json(
        run_dir / "manifest.json",
        {
            "articles": [
                {"article_id": "article_a", "changed": True},
                {"article_id": "article_b", "changed": True},
            ]
        },
    )

    queue = write_manual_review_queue(run_dir, gate_config={"ignored_defect_ids_for_analysis": []})

    assert [item["article"] for item in queue] == ["article_a", "article_b"]
    assert queue[0]["mandatory_review"] is True
    assert queue[0]["mandatory_review_reason"] == "changed_without_quality_delta"
    assert queue[0]["comparison_bucket"] == "unchanged"
    assert queue[1]["mandatory_review"] is False


def test_write_pattern_observations_accumulates_across_loop_iterations(tmp_path: Path) -> None:
    history_path = tmp_path / "pattern_history.jsonl"
    defect_patterns = {
        "P67": {
            "pattern": "text-cleanup",
            "criticality": "medium",
            "fix_layer": "EN polish text cleanup",
        }
    }

    first_run = tmp_path / "run1"
    _write_json(first_run / "manifest.json", {"source_kind": "cached_raw_repolish", "code_commit": "abc123"})
    _write_json(first_run / "quality_history_entry.json", {"run_id": "run1"})
    _write_json(
        first_run / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "article_a",
                    "raw_stage_path": "raw_a.html",
                    "polish_stage_path": "polish_a.html",
                    "defects_found": [
                        {
                            "id": "P67",
                            "severity": "warning",
                            "check": "Text residue",
                            "snippet": "bad spacing",
                        }
                    ],
                }
            ]
        },
    )

    first_summary = write_pattern_observations(
        first_run,
        defect_patterns=defect_patterns,
        history_path=history_path,
    )

    second_run = tmp_path / "run2"
    _write_json(second_run / "manifest.json", {"source_kind": "cached_raw_repolish", "code_commit": "def456"})
    _write_json(second_run / "quality_history_entry.json", {"run_id": "run2"})
    _write_json(
        second_run / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "article_b",
                    "raw_stage_path": "raw_b.html",
                    "polish_stage_path": "polish_b.html",
                    "defects_found": [
                        {
                            "id": "P67",
                            "severity": "warning",
                            "check": "Text residue",
                            "snippet": "bad join",
                        }
                    ],
                },
                {
                    "article": "article_c",
                    "raw_stage_path": "raw_c.html",
                    "polish_stage_path": "polish_c.html",
                    "defects_found": [],
                },
            ]
        },
    )

    second_summary = write_pattern_observations(
        second_run,
        defect_patterns=defect_patterns,
        history_path=history_path,
    )

    assert first_summary["all_articles_reviewed_for_patterns"] is True
    assert first_summary["article_count_reviewed"] == 1
    assert second_summary["article_count_reviewed"] == 2
    assert history_path.read_text(encoding="utf-8").count("\n") == 2
    candidate = second_summary["problem_candidates"][0]
    assert candidate["pattern_key"] == "text-cleanup"
    assert candidate["problem_state"] == "problem_candidate"
    assert candidate["run_count"] == 2
    assert candidate["article_observation_count"] == 2
    assert json.loads((second_run / "pattern_observations.json").read_text(encoding="utf-8"))["history_path"] == str(
        history_path.resolve(strict=False)
    )


def test_repolish_cached_run_auto_policy_keeps_en_corpus_only(tmp_path: Path) -> None:
    source = tmp_path / "source"
    raw_cache = source / "raw_cache"
    raw_cache.mkdir(parents=True)
    en_text = (
        "This study evaluates the design of neural interfaces and describes the methods, "
        "results, and discussion for the experiments. "
    ) * 80
    ru_text = (
        "\u041a\u043b\u0438\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0435 "
        "\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u0438 "
        "\u043e\u043f\u0438\u0441\u044b\u0432\u0430\u044e\u0442 "
        "\u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0443 "
        "\u0438 \u043b\u0435\u0447\u0435\u043d\u0438\u0435. "
    ) * 80
    (raw_cache / "en_doc.01.en.raw.html").write_text(f"<html><body><p>{en_text}</p></body></html>", encoding="utf-8")
    (raw_cache / "ru_doc.01.en.raw.html").write_text(f"<html><body><p>{ru_text}</p></body></html>", encoding="utf-8")

    manifest = repolish_cached_run(
        source,
        tmp_path / "run",
        polish_language="auto",
        target_language="en",
        skip_non_target_language=True,
    )

    assert manifest["raw_count"] == 2
    assert manifest["article_count"] == 1
    assert manifest["skipped_count"] == 1
    assert manifest["polish_language_counts"] == {"en": 1}
    assert [article["article"] for article in manifest["articles"]] == ["en_doc"]
    assert [article["article"] for article in manifest["skipped_articles"]] == ["ru_doc"]
    assert manifest["skipped_articles"][0]["skip_reason"] == "detected_ru_not_en"
    assert (tmp_path / "run" / "audit_tree" / "en_doc" / "02.en.polish.html").is_file()
    assert not (tmp_path / "run" / "audit_tree" / "ru_doc").exists()


def test_repolish_cached_run_recovers_reference_gap_from_source_pdf(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    raw_cache = source / "raw_cache"
    profiles = source / "profiles"
    raw_cache.mkdir(parents=True)
    profiles.mkdir(parents=True)
    pdf_path = tmp_path / "zotero" / "storage" / "NFX7BLRP" / "spotnitz.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    raw_html = (
        "<html><body>"
        "<p>This study discusses hernia repair outcomes and cites a randomized trial [158].</p>"
        "<h4>References</h4><ul>"
        '<li>[157] C. Schug-Pass, D. A. Jacob, and F. Kockerling, "Biomechanical properties," '
        "Hernia, vol. 17, pp. 773-777, 2013.</li>"
        '<li>[159] M. Cambal, P. Zonca, and B. Hrbaty, "Comparison of self-gripping mesh," '
        "Bratislavske Lekarske Listy, vol. 113, pp. 103-107, 2012.</li>"
        "</ul></body></html>"
    )
    (raw_cache / "spotnitz.01.en.raw.html").write_text(raw_html, encoding="utf-8")
    _write_json(profiles / "spotnitz.citation_profile.json", {"status": "ok", "style": "unknown", "confidence": "low"})
    _write_json(
        source / "manifest.json",
        {
            "articles": [
                {
                    "article": "spotnitz",
                    "article_id": "spotnitz",
                    "source_pdf_path": str(pdf_path),
                }
            ]
        },
    )

    monkeypatch.setattr(
        llm_quality_loop,
        "extract_reference_entries_from_pdf",
        lambda _path: [
            SimpleNamespace(
                page=24,
                number=158,
                text=(
                    'R. H. Fortelny, A. H. Petter-Puchner, C. May et al., "The impact '
                    "of atraumatic fibrin sealant vs. staple mesh fixation in TAPP hernia repair "
                    'on chronic pain and quality of life," Surgical Endoscopy, 2012.'
                ),
            )
        ],
    )

    manifest = repolish_cached_run(source, tmp_path / "run", polish_language="en")
    polished = (tmp_path / "run" / "polish" / "spotnitz.02.en.polish.html").read_text(encoding="utf-8")
    profile = json.loads(
        (tmp_path / "run" / "profiles" / "spotnitz.citation_profile.json").read_text(encoding="utf-8")
    )

    assert manifest["pdf_reference_recovery_count"] == 1
    assert manifest["articles"][0]["pdf_reference_recovered"] == 1
    assert 'id="ref-158"' in polished
    assert "Fortelny" in polished
    assert profile["reference_entries_status"] == "loaded_from_source_pdf_gap_recovery"


def test_repolish_cached_run_recovers_pdf_references_from_body_citation_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    raw_cache = source / "raw_cache"
    profiles = source / "profiles"
    raw_cache.mkdir(parents=True)
    profiles.mkdir(parents=True)
    pdf_path = tmp_path / "zotero" / "storage" / "BODYCITE" / "paper.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    raw_html = "<html><body><p>Prior work 1,2.</p></body></html>"
    (raw_cache / "bodycite.01.en.raw.html").write_text(raw_html, encoding="utf-8")
    _write_json(profiles / "bodycite.citation_profile.json", {"status": "ok", "style": "unknown", "confidence": "low"})
    _write_json(
        source / "manifest.json",
        {
            "articles": [
                {
                    "article": "bodycite",
                    "article_id": "bodycite",
                    "source_pdf_path": str(pdf_path),
                }
            ]
        },
    )

    monkeypatch.setattr(
        llm_quality_loop,
        "extract_reference_entries_from_pdf",
        lambda _path: [
            SimpleNamespace(page=10, number=1, text="Alpha A. First source. Journal, 2020."),
            SimpleNamespace(page=10, number=2, text="Beta B. Second source. Journal, 2021."),
        ],
    )

    manifest = repolish_cached_run(source, tmp_path / "run", polish_language="en")
    polished = (tmp_path / "run" / "polish" / "bodycite.02.en.polish.html").read_text(encoding="utf-8")
    profile = json.loads(
        (tmp_path / "run" / "profiles" / "bodycite.citation_profile.json").read_text(encoding="utf-8")
    )

    assert manifest["pdf_reference_recovery_count"] == 2
    assert manifest["articles"][0]["pdf_reference_recovered"] == 2
    assert profile["reference_entries_status"] == "loaded_from_source_pdf_citation_recovery"
    assert profile["reference_entries_recovery_trigger"] == "body_citation"
    assert profile["reference_entries_recovery_numbers"] == [1, 2]
    assert 'data-z2m-pdf-recovered-references="1"' in polished
    assert 'id="ref-1"' in polished
    assert 'id="ref-2"' in polished
    assert 'href="#ref-1"' in polished
    assert 'href="#ref-2"' in polished


def test_pdf_reference_body_recovery_is_skipped_when_reference_ids_exist() -> None:
    html = (
        "<html><body>"
        "<p>Prior work 1,2.</p>"
        "<h2>References</h2><ul>"
        '<li id="ref-1">Alpha A. First source.</li>'
        '<li id="ref-2">Beta B. Second source.</li>'
        "</ul></body></html>"
    )

    assert llm_quality_loop._pdf_reference_recovery_numbers(html) == ([], "")


def test_repolish_cached_run_restores_ancestor_inlined_images(tmp_path: Path) -> None:
    source = tmp_path / "source"
    raw_cache = source / "raw_cache"
    profiles = source / "profiles"
    raw_cache.mkdir(parents=True)
    profiles.mkdir(parents=True)
    raw_html = (
        "<html><body>"
        "<p>This study describes the methods and results for a figure.</p>"
        '<p><img src="fig1.png"/></p>'
        '<p><img src="fig2.png"/></p>'
        "</body></html>"
    )
    (raw_cache / "doc.01.en.raw.html").write_text(raw_html, encoding="utf-8")
    _write_json(profiles / "doc.citation_profile.json", {"status": "ok", "style": "unknown", "confidence": "low"})

    ancestor_polish = tmp_path / "ancestor" / "doc.02.en.polish.html"
    ancestor_polish.parent.mkdir(parents=True)
    ancestor_polish.write_text(
        "<html><body>"
        '<p><img src="data:image/png;base64,AAAA"/></p>'
        '<p><img src="data:image/png;base64,BBBB"/></p>'
        "</body></html>",
        encoding="utf-8",
    )
    chain = tmp_path / "chain"
    _write_json(
        chain / "manifest.json",
        {
            "articles": [
                {
                    "article": "doc",
                    "source_polish_path": str(ancestor_polish),
                }
            ]
        },
    )
    _write_json(source / "manifest.json", {"source_run_dir": str(chain), "articles": [{"article": "doc"}]})

    manifest = repolish_cached_run(source, tmp_path / "run")
    polished = (tmp_path / "run" / "polish" / "doc.02.en.polish.html").read_text(encoding="utf-8")
    audit_polished = (tmp_path / "run" / "audit_tree" / "doc" / "02.en.polish.html").read_text(encoding="utf-8")

    assert manifest["restored_image_count"] == 2
    assert 'data-z2m-src="fig1.png" src="data:image/png;base64,AAAA"' in polished
    assert 'data-z2m-src="fig2.png" src="data:image/png;base64,BBBB"' in polished
    assert '<img src="fig1.png"' not in polished
    assert audit_polished == polished


def test_repolish_cached_run_restores_converted_sidecar_images(tmp_path: Path) -> None:
    source = tmp_path / "source"
    raw_cache = source / "raw_cache"
    profiles = source / "profiles"
    raw_cache.mkdir(parents=True)
    profiles.mkdir(parents=True)
    (raw_cache / "doc.01.en.raw.html").write_text(
        '<html><body><p>Figure below.</p><p><img src="fig1.png"/></p></body></html>',
        encoding="utf-8",
    )
    _write_json(profiles / "doc.citation_profile.json", {"status": "ok", "style": "unknown", "confidence": "low"})

    source_exports_raw = tmp_path / "html" / "source_exports" / "lib" / "att" / "doc" / "01.en.raw.html"
    source_exports_raw.parent.mkdir(parents=True)
    source_exports_raw.write_text("", encoding="utf-8")
    converted_doc = tmp_path / "html" / "converted" / "lib" / "att" / "doc" / "Document"
    converted_doc.mkdir(parents=True)
    converted_doc.joinpath("fig1.png").write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
    )

    chain = tmp_path / "chain"
    _write_json(
        chain / "manifest.json",
        {
            "articles": [
                {
                    "article": "doc",
                    "raw_stage_path": str(source_exports_raw),
                }
            ]
        },
    )
    _write_json(source / "manifest.json", {"source_run_dir": str(chain), "articles": [{"article": "doc"}]})

    manifest = repolish_cached_run(source, tmp_path / "run")
    polished = (tmp_path / "run" / "polish" / "doc.02.en.polish.html").read_text(encoding="utf-8")

    assert manifest["restored_image_count"] == 1
    assert 'data-z2m-src="fig1.png" src="data:image/png;base64,' in polished
    assert '<img src="fig1.png"' not in polished
