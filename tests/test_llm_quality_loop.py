import base64
import json
from pathlib import Path

from scripts.llm_quality_loop import (
    assess_polish_html,
    build_analysis_pack,
    evaluate_quality_gate,
    normalize_converted_audit_article_ids,
    prepare_converted_raw_cache,
    parse_args,
    prepare_converted_run,
    repolish_cached_run,
    render_llm_prompt,
    write_manual_review_queue,
    write_pattern_observations,
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
    assert "focused artifact regression" in prompt


def test_observe_runs_configured_tests_by_default() -> None:
    args = parse_args(
        [
            "observe",
            "--source-run-dir",
            "source_run",
            "--out-dir",
            "out_run",
        ]
    )

    assert args.run_tests is True

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
    assert "refine the P classification" in prompt


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
