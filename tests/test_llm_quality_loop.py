import base64
import json
import re
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
import zlib

import pytest

from pdf_html_polish.html_stages import (
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    write_raw_conversion_manifest,
)
from pdf_html_polish.quality_loop.cached_run_state import (
    CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
    CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR,
    CachedRunSourceError,
    cached_repolish_artifact_fingerprints,
    validate_cached_repolish_source,
)

import pdf_html_polish.quality_loop.converted_runs as converted_runs_module

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
    write_polish_auto_repair_stage,
    write_resolver_decisions,
)


_VALID_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _valid_tiny_png_bytes() -> bytes:
    return base64.b64decode(_VALID_TINY_PNG_B64)


def _valid_tiny_png_data_url() -> str:
    return f"data:image/png;base64,{_VALID_TINY_PNG_B64}"


def _commit_current_converted_raw(
    stage_dir: Path,
    *,
    source_pdf: Path | None = None,
) -> None:
    resolved_source = source_pdf or stage_dir.parent / f"{stage_dir.parent.name}.pdf"
    resolved_source.parent.mkdir(parents=True, exist_ok=True)
    if not resolved_source.exists():
        resolved_source.write_bytes(b"%PDF-1.4\n")
    write_raw_conversion_manifest(
        stage_dir,
        source_pdf=resolved_source,
        raw_stage_path=stage_dir / RAW_STAGE_NAME,
    )


def _write_current_converted_pair(
    stage_dir: Path,
    *,
    raw_html: str,
    polish_html: str,
    source_pdf: Path | None = None,
) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_path = stage_dir / RAW_STAGE_NAME
    raw_path.write_text(raw_html, encoding="utf-8")
    (stage_dir / POLISH_STAGE_NAME).write_text(polish_html, encoding="utf-8")
    _commit_current_converted_raw(stage_dir, source_pdf=source_pdf)


def _rgba_png_bytes(width: int, height: int, red: int, green: int, blue: int, alpha: int = 255) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw_scanline = b"\x00" + bytes([red, green, blue, alpha]) * width
    raw = raw_scanline * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _tiny_rgba_png_bytes(red: int, green: int, blue: int, alpha: int = 255) -> bytes:
    return _rgba_png_bytes(1, 1, red, green, blue, alpha)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _commit_cached_repolish_source(
    source: Path,
    *,
    article_metadata: dict[str, dict[str, object]] | None = None,
    source_run_dir: Path | None = None,
) -> dict[str, object]:
    source = source.resolve(strict=False)
    raw_dir = source / "raw_cache"
    profile_dir = source / "profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    metadata = article_metadata or {}
    articles: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    style_counts: dict[str, int] = {}
    for index, raw_path in enumerate(sorted(raw_dir.glob("*.01.en.raw.html")), start=1):
        article_id = raw_path.name.removesuffix(".01.en.raw.html")
        profile_path = profile_dir / f"{article_id}.citation_profile.json"
        if not profile_path.is_file():
            _write_json(
                profile_path,
                {"status": "ok", "style": "unknown", "confidence": "low"},
            )
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        assert isinstance(profile, dict)
        status = str(profile.get("status") or "unknown")
        style = str(profile.get("style") or "unknown")
        confidence = str(profile.get("confidence") or "low")
        status_counts[status] = status_counts.get(status, 0) + 1
        style_key = f"{style}:{confidence}"
        style_counts[style_key] = style_counts.get(style_key, 0) + 1
        articles.append(
            {
                "index": index,
                "article_id": article_id,
                "article": article_id,
                "raw_cache_path": str(raw_path.resolve()),
                "profile_path": str(profile_path.resolve()),
                "profile_status": status,
                "citation_style": style,
                "citation_confidence": confidence,
                **cached_repolish_artifact_fingerprints(raw_path, profile_path),
                **metadata.get(article_id, {}),
            }
        )
    manifest: dict[str, object] = {
        "source_snapshot_schema_version": CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
        "source_kind": "converted_raw_cache",
        "out_dir": str(source),
        "raw_count": len(articles),
        "article_count": len(articles),
        "raw_cache_dir": str(raw_dir.resolve()),
        "profile_dir": str(profile_dir.resolve()),
        "profile_status_counts": dict(sorted(status_counts.items())),
        "profile_style_counts": dict(sorted(style_counts.items())),
        "articles": articles,
    }
    if source_run_dir is not None:
        manifest["source_run_dir"] = str(source_run_dir.resolve(strict=False))
    _write_json(source / "manifest.json", manifest)
    return manifest


def test_quality_loop_script_keeps_review_helper_compatibility(tmp_path: Path) -> None:
    defects = [
        {"id": "P71", "severity": "warning"},
        {"id": "P71", "severity": "error"},
        {"id": "P04"},
    ]
    queue_path = tmp_path / "manual_review_queue.json"
    _write_json(
        queue_path,
        [
            {
                "article": "article_a",
                "polish_stage_path": "article_a/02.en.polish.html",
                "review_status": "reviewed",
                "review_note": "checked",
            }
        ],
    )

    assert llm_quality_loop._defect_id_counts(defects) == {"P04": 1, "P71": 2}
    assert llm_quality_loop._severity_counts(defects) == {"error": 1, "info": 1, "warning": 1}
    items = llm_quality_loop._existing_queue_items(queue_path)
    assert llm_quality_loop._review_state_by_key(items)["article_a"]["review_note"] == "checked"
    assert llm_quality_loop._relative_review_href(tmp_path, tmp_path / "article_a" / "02.en.polish.html") == (
        "article_a/02.en.polish.html"
    )


def test_quality_loop_script_keeps_source_pdf_helper_compatibility(tmp_path: Path) -> None:
    manifest = {"articles": [{"article_id": "article_a"}, {"article": "article_b"}]}
    nested_paths = {
        "source_pdf": "D:/papers/source.pdf",
        "nested": [{"overlay_source_pdf": "D:/papers/overlay.pdf?download=1"}],
    }
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    assert sorted(llm_quality_loop._manifest_article_by_id(manifest)) == ["article_a", "article_b"]
    assert llm_quality_loop._collect_pdf_path_strings(nested_paths) == [
        "D:/papers/source.pdf",
        "D:/papers/overlay.pdf?download=1",
    ]
    assert llm_quality_loop._attachment_keys_from_article(
        "Zotero_Elvis_D_KEY12345_571527_Article",
        {"zotero_attachment_key": "ABC12345"},
    ) == ["KEY12345", "ABC12345"]
    assert llm_quality_loop._existing_path_candidates(str(pdf_path)) == [
        pdf_path.resolve(strict=False)
    ]


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


def test_quality_gate_tolerates_null_or_malformed_optional_sections() -> None:
    report = evaluate_quality_gate(
        {
            "status": "ok",
            "totals_delta": None,
            "comparable_totals_delta": ["invalid"],
            "regressions": [None, "invalid"],
            "improvements": None,
        },
        {
            "max_regressions": 0,
            "max_total_deltas": None,
            "max_article_deltas": ["invalid"],
        },
    )

    assert report["status"] == "pass"
    assert report["regression_count"] == 0


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


def test_quality_gate_accepts_scanned_pdf_when_diagnostics_ran() -> None:
    report = evaluate_quality_gate(
        {
            "status": "ok",
            "totals_delta": {"score": 0, "defects": 0},
            "regressions": [],
            "improvements": [],
        },
        {
            "max_regressions": 0,
            "max_total_deltas": {"score": 0, "defects": 0},
            "require_pdf_text_layer_diagnostics": True,
        },
        audit_report={
            "corpus_summary": {"totals": {"source_pdf_present": 1, "pdf_text_chars": 0}}
        },
        audit_command_report={
            "pdf_diagnostics_enabled": True,
            "pdf_map_path": "source_pdf_map.json",
        },
    )

    assert report["status"] == "pass"
    assert report["pdf_text_layer_diagnostics"]["source_pdf_text_layer_empty"] is True


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


def test_analysis_pack_prioritizes_resolver_repair_candidates_over_accepted_telemetry(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    common_summary = {
        "source_pdf_present": True,
        "source_pdf_path": "paper.pdf",
        "pdf_text_status": "pymupdf",
    }
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {
                "defect_counts": {
                    "P04M": 1,
                    "P04N": 1,
                    "P35": 1,
                    "P45S": 1,
                    "P61": 1,
                    "P62": 1,
                }
            },
            "articles": [
                {
                    "article": "article_p61",
                    "raw_stage_path": "raw_p61.html",
                    "polish_stage_path": "polish_p61.html",
                    "summary": common_summary,
                    "defects_found": [
                        {
                            "id": "P61",
                            "severity": "warning",
                            "check": "missing semantic figure target",
                            "snippet": "Figure 3",
                            "extra": {"quality_counted": False, "figure_key": "3"},
                        }
                    ],
                },
                {
                    "article": "article_p04n",
                    "raw_stage_path": "raw_p04n.html",
                    "polish_stage_path": "polish_p04n.html",
                    "summary": common_summary,
                    "defects_found": [
                        {
                            "id": "P04N",
                            "severity": "warning",
                            "check": "citation-like range has no bibliography targets",
                            "snippet": "[1-3]",
                            "extra": {"quality_counted": False, "candidate_numbers": [1, 3]},
                        }
                    ],
                },
                {
                    "article": "article_telemetry",
                    "raw_stage_path": "raw_telemetry.html",
                    "polish_stage_path": "polish_telemetry.html",
                    "summary": common_summary,
                    "defects_found": [
                        {
                            "id": "P04M",
                            "severity": "warning",
                            "check": "math-like numeric range",
                            "extra": {"quality_counted": False},
                        },
                        {
                            "id": "P45S",
                            "severity": "warning",
                            "check": "roman suffix superscript marker",
                            "extra": {"quality_counted": False},
                        },
                        {
                            "id": "P35",
                            "severity": "warning",
                            "check": "source-layer replacement char",
                            "extra": {
                                "quality_counted": False,
                                "source_pdf_text_layer_evidence": True,
                            },
                        },
                    ],
                },
                {
                    "article": "article_p62",
                    "raw_stage_path": "raw_p62.html",
                    "polish_stage_path": "polish_p62.html",
                    "summary": common_summary,
                    "defects_found": [
                        {
                            "id": "P62",
                            "severity": "warning",
                            "check": "missing figure image",
                            "extra": {"quality_counted": False},
                        }
                    ],
                },
            ],
        },
    )
    _write_json(run_dir / "assessment.json", {"article_count": 4, "totals": {}, "articles": []})
    _write_json(
        run_dir / "quality_history_entry.json",
        {
            "run_id": "run_a",
            "totals": {},
            "articles": {
                "article_p04n": {"score": 1},
                "article_p61": {"score": 1},
                "article_p62": {"score": 1},
                "article_telemetry": {"score": 1},
            },
        },
    )
    _write_json(run_dir / "quality_compare.json", {"status": "ok", "regressions": [], "improvements": []})
    _write_json(run_dir / "manifest.json", {"article_count": 4, "source_kind": "test"})

    report = write_resolver_decisions(run_dir)
    assert report["repair_candidate_counts"] == {"P04N": 1, "P61": 1, "P62": 1}
    assert report["accepted_telemetry_counts"] == {"P04M": 1, "P35": 1, "P45S": 1}

    pack = build_analysis_pack(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": ["P61", "P62"]},
    )

    article_ids = [article["article"] for article in pack["articles"]]
    assert article_ids == ["article_p04n", "article_p61"]
    assert pack["articles"][0]["selection_reasons"] == [
        "non_telemetry_defects",
        "resolver_repair_candidate",
    ]
    assert pack["articles"][1]["defect_ids"] == {"P61": 1}
    assert pack["articles"][1]["resolver_repair_candidate_count"] == 1
    assert "article_telemetry" not in article_ids
    assert "article_p62" not in article_ids
    prompt = render_llm_prompt(pack)
    assert "selection_reasons" in prompt
    assert "article_p61" in prompt
    assert "article_telemetry" not in prompt


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


def test_p62_marker_recovery_plan_retries_full_pdf_when_label_missed_by_page_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "book.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    warning = "Figure 25 image was not extracted into this HTML."
    caption = "Figure 25. Complexity and customization versus learning rate."
    polish_path.write_text(
        '<div id="fig-25" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        f'<p class="z2m-missing-figure-warning z2m-figure-target" role="note">{warning}</p>'
        f'<p class="z2m-figure-caption">{caption}</p>'
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
                    "summary": {"source_pdf_present": True, "source_pdf_path": str(source_pdf)},
                    "defects_found": [
                        {
                            "id": "P62",
                            "snippet": warning,
                            "extra": {"warning_index": 1, "figure_label": "25"},
                        }
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})

    calls: list[int | None] = []

    def fake_pages(pdf_path: Path, *, max_pages: int | None = None):
        assert pdf_path == source_pdf
        calls.append(max_pages)
        if max_pages == 80:
            pages = ["ordinary production-process text"] * 80
            pages[71] = "customization and learning rate appear here, but not the figure label"
            return "fake_limited", pages, None
        pages = ["ordinary production-process text"] * 502
        pages[298] = caption
        return "fake_full", pages, None

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_pages)

    report = write_p62_marker_recovery_plan(
        run_dir,
        gate_config={
            "p62_marker_recovery_max_articles": 0,
            "p62_marker_recovery_max_pdf_pages": 80,
            "p62_marker_recovery_context_chars": 1200,
            "p62_marker_recovery_min_match_score": 0.05,
            "p62_marker_recovery_require_label_match": True,
            "p62_marker_recovery_retry_full_pdf_on_label_miss": True,
        },
    )

    article = report["articles"][0]
    assert calls == [80, None]
    assert article["status"] == "ready"
    assert article["source_pdf_page_number"] == 299
    assert article["marker_page_range"] == "298"
    assert article["text_layer_full_retry"] is True
    assert article["text_layer_truncated_to_limit"] is False


def test_p62_marker_recovery_plan_rejects_toc_and_selects_visual_label_page(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "standard.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    warning = "Figure 2 image was not extracted into this HTML."
    polish_path.write_text(
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        f'<p class="z2m-missing-figure-warning z2m-figure-target" role="note">{warning}</p>'
        '<p class="z2m-figure-caption">Figure 2. Na test cycle.</p>'
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
                    "summary": {"source_pdf_present": True, "source_pdf_path": str(source_pdf)},
                    "defects_found": [
                        {"id": "P62", "snippet": warning, "extra": {"warning_index": 1, "figure_label": "2"}}
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})

    def fake_pages(pdf_path: Path, *, max_pages: int | None = None):
        assert pdf_path == source_pdf
        pages = ["ordinary text"] * 20
        pages[3] = "CONTENTS ................................ Figure 2 Determination of test duration time ........ 18"
        pages[13] = "Figure 2. Na test cycle. The first cycle comprises cold and hot temperatures."
        return "fake", pages, None

    def fake_visuals(pdf_path: Path, page_numbers):
        assert pdf_path == source_pdf
        return {
            4: {"image_xrefs": 1, "image_blocks": 1, "drawings": 7, "text_blocks": 10},
            14: {"image_xrefs": 2, "image_blocks": 2, "drawings": 60, "text_blocks": 38},
        }

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_pages)
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_visual_summaries", fake_visuals)

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
    assert article["status"] == "ready"
    assert article["source_pdf_page_number"] == 14
    assert article["marker_page_range"] == "13"
    assert article["selected_false_match_hint"] == ""
    assert any(
        candidate["page_number"] == 4 and candidate["false_match_hint"] == "toc_or_contents"
        for candidate in article["page_resolver_candidates"]
    )


def test_p62_marker_recovery_plan_uses_full_hierarchical_figure_label(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "thesis.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    warning = "Figure 3 image was not extracted into this HTML."
    polish_path.write_text(
        '<div id="fig-3-1" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        f'<p class="z2m-missing-figure-warning z2m-figure-target" role="note">{warning}</p>'
        '<p class="z2m-figure-caption">Figure 3-1. Circuit diagram for the sinusoidal generator.</p>'
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
                    "summary": {"source_pdf_present": True, "source_pdf_path": str(source_pdf)},
                    "defects_found": [
                        {"id": "P62", "snippet": warning, "extra": {"warning_index": 1, "figure_label": "3"}}
                    ],
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})

    def fake_pages(pdf_path: Path, *, max_pages: int | None = None):
        assert pdf_path == source_pdf
        pages = ["ordinary text"] * 60
        pages[8] = "LIST OF FIGURES ........ FIGURE 3-3 CIRCUIT DIAGRAM ........ 53"
        pages[52] = "Figure 3-1. Circuit diagram for the sinusoidal generator with current converter."
        return "fake", pages, None

    def fake_visuals(pdf_path: Path, page_numbers):
        assert pdf_path == source_pdf
        return {
            9: {"image_xrefs": 0, "image_blocks": 0, "drawings": 0, "text_blocks": 28},
            53: {"image_xrefs": 11, "image_blocks": 11, "drawings": 24, "text_blocks": 33},
        }

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_pages)
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_visual_summaries", fake_visuals)

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
    assert article["status"] == "ready"
    assert article["figure_label"] == "3"
    assert article["resolved_figure_label"] == "3-1"
    assert article["source_pdf_page_number"] == 53
    assert article["marker_page_range"] == "52"


def test_p62_page_resolver_keeps_true_caption_despite_parenthetical_reference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    pages = ["ordinary text"] * 14
    pages[1] = (
        "The paradigm was introduced in prose (Fig. 1)11 before the full caption. "
        "Figure 1. Behavioral task. After engagement Start phase and an initial "
        "fixation period animals are presented a gaze-contingent display."
    )
    pages[11] = (
        "Then came the Choice phase where animals select between two alternatives "
        "presented in the clear (Fig. 1, Supplementary Movie 1). The task used "
        "engagement fixation animals cue letters matching distractor alternatives."
    )

    def fake_visuals(pdf_path: Path, page_numbers):
        assert pdf_path == source_pdf
        return {
            2: {"image_xrefs": 2, "image_blocks": 2, "drawings": 420, "text_blocks": 14},
            12: {"image_xrefs": 0, "image_blocks": 0, "drawings": 87, "text_blocks": 14},
        }

    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_visual_summaries", fake_visuals)

    resolver = llm_quality_loop._resolve_p62_pdf_page_for_figure(
        [
            "Figure 1. Behavioral task. After engagement (Start phase) and an initial "
            "fixation period, animals are presented a gaze-contingent display."
        ],
        pages,
        "1",
        pdf_path=source_pdf,
    )

    assert resolver["page_number"] == 2
    assert resolver["selected_false_match_hint"] == ""
    assert (resolver["candidates"] or [])[0]["caption_head_near_label"] is True


def test_p62_page_resolver_uses_visual_strength_to_break_caption_ties(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_pdf = tmp_path / "standard.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    pages = ["ordinary text"] * 16
    pages[4] = "Figure 2. Na test cycle. First cycle A time t1 second cycle t1."
    pages[13] = "Figure 2. Na test cycle. First cycle A time t1 second cycle t1."

    def fake_visuals(pdf_path: Path, page_numbers):
        assert pdf_path == source_pdf
        return {
            5: {"image_xrefs": 1, "image_blocks": 1, "drawings": 7, "text_blocks": 10},
            14: {"image_xrefs": 2, "image_blocks": 2, "drawings": 60, "text_blocks": 38},
        }

    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_visual_summaries", fake_visuals)

    resolver = llm_quality_loop._resolve_p62_pdf_page_for_figure(
        ["Figure 2. Na test cycle. First cycle A time t1 second cycle t1."],
        pages,
        "2",
        pdf_path=source_pdf,
    )

    assert resolver["page_number"] == 14
    assert (resolver["candidates"] or [])[0]["visual_score"] > (resolver["candidates"] or [])[1]["visual_score"]


def test_p61_nonduplicate_page_recovery_skips_duplicate_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")

    monkeypatch.setattr(
        llm_quality_loop,
        "_p62_render_fallback_page_number",
        lambda *_args, **_kwargs: (4, "caption_near_page_top_previous_page"),
    )

    def fake_render(_pdf_path: Path, page_number: int, out_path: Path, *, zoom: float) -> dict[str, str]:
        return {"status": "rendered", "path": str(out_path), "error": ""}

    def fake_data_url(path: Path) -> str:
        return f"data:image/png;base64,page-{path.stem[-4:]}"

    def fake_duplicates(_html: str, data_url: str, *, target_figure_key: str) -> bool:
        return data_url.endswith("0004")

    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fake_render)
    monkeypatch.setattr(llm_quality_loop, "_data_url_from_image_file", fake_data_url)
    monkeypatch.setattr(llm_quality_loop, "_p62_data_url_duplicates_existing_figure_unit", fake_duplicates)

    result = llm_quality_loop._render_p61_nonduplicate_page_recovery(
        pdf_path=pdf_path,
        source_page_number=5,
        figure_label="7",
        target_figure_key="7",
        artifact_dir=tmp_path / "artifacts",
        render_zoom=1.0,
        html="<html></html>",
    )

    assert result["status"] == "rendered"
    assert result["page_number"] == 5
    assert result["selection_reason"] == "source_pdf_page"
    assert [attempt["duplicates_existing_figure"] for attempt in result["attempts"]] == [True, False]


def test_p62_page_resolver_does_not_treat_accepted_article_header_as_backmatter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_pdf = tmp_path / "accepted.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    pages = ["ordinary text"] * 12
    pages[3] = (
        "Accepted Article This article is protected by copyright. "
        "FIG. 2. Schematic of the connected relationship between the left ventricle "
        "and the blood vessels in the thorax."
    )
    pages[11] = (
        "Accepted Article This article is protected by copyright. "
        "FIG. 2. Schematic of the connected relationship between the left ventricle "
        "and the blood vessels in the thorax. FIG. 3. Differential graph list."
    )

    def fake_visuals(pdf_path: Path, page_numbers):
        assert pdf_path == source_pdf
        return {
            4: {"image_xrefs": 0, "image_blocks": 0, "drawings": 5, "text_blocks": 50},
            12: {"image_xrefs": 0, "image_blocks": 0, "drawings": 0, "text_blocks": 44},
        }

    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_visual_summaries", fake_visuals)

    resolver = llm_quality_loop._resolve_p62_pdf_page_for_figure(
        [
            "FIG. 2. Schematic of the connected relationship between the left "
            "ventricle and the blood vessels in the thorax."
        ],
        pages,
        "2",
        pdf_path=source_pdf,
    )

    assert resolver["page_number"] == 4
    assert resolver["source_visual_unavailable"] is False
    assert all(candidate["false_match_hint"] != "backmatter_or_reference_text" for candidate in resolver["candidates"])


def test_p62_detached_plate_asset_maps_numeric_label_to_plate_order(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "accepted_plates.pdf"
    doc = fitz.open()
    anchor = doc.new_page(width=612, height=792)
    anchor.insert_text(
        (96, 96),
        "Accepted Article\nFIG. 2 is the model schematic described in the manuscript.",
    )
    page_2 = doc.new_page(width=612, height=792)
    page_2.insert_text((96, 740), "This article is protected by copyright.")
    page_2.insert_image(fitz.Rect(96, 96, 300, 260), stream=_valid_tiny_png_bytes())
    page_3 = doc.new_page(width=612, height=792)
    page_3.insert_text((96, 740), "This article is protected by copyright.")
    page_3.insert_image(fitz.Rect(96, 72, 360, 220), stream=_valid_tiny_png_bytes())
    page_3.insert_image(fitz.Rect(96, 300, 420, 520), stream=_valid_tiny_png_bytes())
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_detached_pdf_figure_plate_asset(
        pdf_path,
        1,
        "2",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] == "detached_plate_rendered"
    assert asset["source"] == "pdf_detached_plate_region_render"
    assert asset["page_number"] == 3
    assert asset["plate_index"] == 2
    assert Path(asset["path"]).is_file()


def test_p62_caption_rect_prefers_caption_line_over_prose_reference(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "caption_rect.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((96, 160), "The participants walked farther in compass mode (Figure 8).")
    page.insert_text((96, 520), "Figure 8. The mean walking distance on the first experiment day.")
    doc.save(str(pdf_path))
    doc.close()

    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(0)
        caption_rects = llm_quality_loop._p62_page_caption_label_rects(page, "8")
        all_rects = llm_quality_loop._p62_page_label_rects(page, "8")
    finally:
        doc.close()

    assert caption_rects
    assert all_rects
    assert min(rect.y0 for rect in caption_rects) > 500
    assert min(rect.y0 for rect in all_rects) < 200


def test_p62_pdf_figure_asset_renders_text_only_figure_region(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "text_figure.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_textbox(
        fitz.Rect(72, 80, 540, 250),
        (
            "Briefly name activities and their locations during which you experience difficulties.\n"
            "Which activity do you consider difficult?        Where?\n"
            "1. To walk to the post office                  In the city centre\n"
            "2. To visit my sister using public transport   In town\n"
            "3. To play cards with friends                  In the community centre"
        ),
        fontsize=11,
    )
    page.insert_text((72, 280), "Figure 1. Worksheet for prioritizing client's needs.")
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_pdf_figure_asset(
        pdf_path,
        1,
        "1",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] == "text_region_rendered"
    assert asset["source"] == "pdf_figure_region_render"
    assert Path(asset["path"]).is_file()


def test_p62_pdf_figure_asset_rejects_manuscript_placeholder_page(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "placeholder.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 120), "Insert Figure 5 about here.")
    page.insert_text((72, 180), "The experiment is described in the surrounding prose.")
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_pdf_figure_asset(
        pdf_path,
        1,
        "5",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] == "false_label_match_manuscript_placeholder"
    assert asset["source"] == ""
    assert asset["path"] == ""


def test_p62_pdf_figure_asset_allows_prose_reference_when_caption_exists(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "caption_and_reference.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 80), "Another example is presented in Figure 10.")
    page.insert_image(fitz.Rect(120, 180, 360, 300), stream=_valid_tiny_png_bytes())
    page.insert_text((72, 330), "Figure 10. Example visual with a real caption.")
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_pdf_figure_asset(
        pdf_path,
        1,
        "10",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] in {"native_image_extracted", "region_rendered"}
    assert asset["source"] in {"pdf_native_image", "pdf_figure_region_render"}
    assert Path(asset["path"]).is_file()


def test_p62_pdf_figure_asset_ignores_page_header_rule_for_caption_region(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "header_rule_and_figure.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 48), "Detecting signage and doors for blind navigation")
    page.draw_line((72, 60), (540, 60))
    page.insert_text((72, 86), "Fig. 2 Query-based signage and door detection by a wearable camera.")
    page.insert_image(fitz.Rect(250, 80, 430, 230), stream=_valid_tiny_png_bytes())
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_pdf_figure_asset(
        pdf_path,
        1,
        "2",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] == "native_image_extracted"
    assert asset["source"] == "pdf_native_image"
    assert Path(asset["path"]).is_file()


def test_p62_pdf_figure_asset_ignores_vertical_page_rule_for_caption_region(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "vertical_rule_and_figure.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.draw_line((580, 0), (580, 792))
    page.insert_image(fitz.Rect(72, 490, 380, 700), stream=_valid_tiny_png_bytes())
    page.insert_text((72, 724), "Fig. 1 Overview of virtual brainy chair.")
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_pdf_figure_asset(
        pdf_path,
        1,
        "1",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] == "native_image_extracted"
    assert asset["source"] == "pdf_native_image"
    assert Path(asset["path"]).is_file()


def test_p62_pdf_figure_asset_does_not_absorb_adjacent_body_column(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "figure_near_body_column.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(50, 500, 380, 690), stream=_valid_tiny_png_bytes())
    page.draw_rect(fitz.Rect(40, 490, 390, 700))
    page.insert_textbox(
        fitz.Rect(406, 490, 560, 720),
        "This prose column describes the surrounding method and should not be "
        "absorbed into the recovered figure crop. " * 4,
        fontsize=9,
    )
    page.insert_text((50, 724), "Fig. 1 Overview of virtual brainy chair.")
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_pdf_figure_asset(
        pdf_path,
        1,
        "1",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] == "region_rendered"
    assert asset["source"] == "pdf_figure_region_render"
    assert asset["selected_rect"][2] < 405
    assert Path(asset["path"]).is_file()


def test_p62_pdf_figure_asset_prefers_side_aligned_graphics_over_lower_image(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "side_aligned_flowchart.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 48), "Detecting signage and doors for blind navigation")
    page.draw_line((72, 60), (540, 60))
    page.insert_text((72, 90), "Fig. 5 Flow chart of our proposed door detection method.")
    page.draw_rect(fitz.Rect(250, 82, 330, 122))
    page.draw_rect(fitz.Rect(370, 82, 450, 122))
    page.draw_line((330, 102), (370, 102))
    page.insert_image(fitz.Rect(90, 240, 390, 420), stream=_valid_tiny_png_bytes())
    doc.save(str(pdf_path))
    doc.close()

    asset = llm_quality_loop._recover_p62_pdf_figure_asset(
        pdf_path,
        1,
        "5",
        tmp_path / "asset",
        zoom=1.0,
    )

    assert asset["status"] == "region_rendered"
    assert asset["source"] == "pdf_figure_region_render"
    selected_rect = asset["selected_rect"]
    assert selected_rect[1] < 130
    assert selected_rect[3] < 170
    assert Path(asset["path"]).is_file()


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


def test_p62_recovery_cleanup_matches_nearest_figure_unit_label() -> None:
    html = (
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="one.png" data-z2m-recovery-source="pdf_page_render" '
        f'alt="Recovered Figure 1 visual from source PDF" src="{_valid_tiny_png_data_url()}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 1. One.</p>'
        "</div>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="two.png" data-z2m-recovery-source="pdf_page_render" '
        f'alt="Recovered Figure 2 visual from source PDF" src="{_valid_tiny_png_data_url()}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 2. Two.</p>'
        "</div>"
    )

    patched, replacements = llm_quality_loop._replace_p62_recovery_with_missing_warning(
        html,
        figure_label="2",
        reason="source_visual_unavailable",
        replace_sources={"pdf_page_render"},
    )

    assert replacements == 1
    assert "Figure 1 image was not extracted" not in patched
    assert "one.png" in patched
    assert "Figure 2 image was not extracted" in patched
    assert "two.png" not in patched


def test_p62_missing_warning_detection_uses_figure_unit_id_for_mismatched_text() -> None:
    html = (
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 2 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">Figure 4. The complex environment.</p>'
        "</div>"
    )

    assert llm_quality_loop._html_has_p62_missing_warning_for_figure_unit(html, "4") is True
    patched, replacements = llm_quality_loop._replace_p62_figure_unit_target_with_missing_warning(
        html,
        figure_label="4",
        reason="source_visual_unavailable",
    )

    assert replacements == 1
    assert "Figure 4 image was not extracted" in patched
    assert "Figure 2 image was not extracted" not in patched


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


def test_p62_image_recovery_stage_runs_marker_first_with_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 7 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">Figure 7. Marker-recovered visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    marker_output_dir = run_dir / "p62_marker_recovery" / "article_a" / "fig_7"
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "7",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 8,
                    "figure_label_pdf_page_candidates": [8],
                    "polish_stage_path": str(polish_path),
                    "marker_page_range": "7",
                    "marker_command": ["marker_single", str(source_pdf), "--page_range", "7"],
                    "marker_output_dir": str(marker_output_dir),
                    "existing_marker_output_validation": {"status": "not_run"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    calls: list[int] = []

    def fake_execute(record: dict[str, object], *, timeout_seconds: int) -> dict[str, object]:
        calls.append(timeout_seconds)
        output = Path(str(record["marker_output_dir"])) / "paper"
        output.mkdir(parents=True)
        (output / "paper.html").write_text("<p>Figure 7. Marker-recovered visual.</p>", encoding="utf-8")
        (output / "_page_7_Figure_0.png").write_bytes(_valid_tiny_png_bytes())
        return {"status": "completed", "elapsed_seconds": 1.25, "timeout_seconds": timeout_seconds}

    def fail_render(*args, **kwargs):
        raise AssertionError("marker-recovered P62 records must not render PDF fallback")

    monkeypatch.setattr(llm_quality_loop, "_execute_p62_marker_command", fake_execute)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fail_render)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={
            "p62_image_recovery_execute_marker": True,
            "p62_image_recovery_marker_timeout_seconds": 600,
            "p62_image_recovery_render_zoom": 1.0,
        },
    )

    assert calls == [600]
    assert report["status"] == "ready"
    assert report["marker_timeout_seconds"] == 600
    assert report["recovery_source_counts"] == {"marker_image": 1}
    patched_html = polish_path.read_text(encoding="utf-8")
    assert 'data-z2m-recovery-source="marker_image"' in patched_html
    assert "z2m-missing-figure-warning" not in patched_html


def test_p62_image_recovery_stage_uses_pdf_figure_asset_before_page_render(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 5 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">Figure 5. Screenshot visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    asset_path = run_dir / "asset.png"
    asset_path.write_bytes(_valid_tiny_png_bytes())
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "5",
                    "resolved_figure_label": "5",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 8,
                    "figure_label_pdf_page_candidates": [8],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "caption_only"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_asset(pdf_path: Path, page_number: int, figure_label: str, artifact_dir: Path, *, zoom: float):
        assert pdf_path == source_pdf
        assert page_number == 8
        assert figure_label == "5"
        return {
            "status": "region_rendered",
            "path": str(asset_path),
            "source": "pdf_figure_region_render",
            "error": "",
            "selected_rect": (10.0, 20.0, 200.0, 160.0),
            "caption_found": True,
        }

    def fail_page_render(*args, **kwargs):
        raise AssertionError("PDF figure asset should be used before full-page render fallback")

    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fake_asset)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fail_page_render)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["recovery_source_counts"] == {"pdf_figure_region_render": 1}
    article = report["articles"][0]
    assert article["figure_asset_status"] == "region_rendered"
    assert article["page_render_status"] == "not_run"
    patched_html = polish_path.read_text(encoding="utf-8")
    assert 'data-z2m-recovery-source="pdf_figure_region_render"' in patched_html
    assert "z2m-missing-figure-warning" not in patched_html


def test_p62_image_recovery_stage_upgrades_existing_page_render_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="old_page.png" data-z2m-recovery-source="pdf_page_render" '
        f'alt="Recovered Figure 5 visual from source PDF" src="{_valid_tiny_png_data_url()}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 5. Screenshot visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    asset_path = run_dir / "asset.png"
    asset_path.write_bytes(_valid_tiny_png_bytes())
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "5",
                    "resolved_figure_label": "5",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 8,
                    "figure_label_pdf_page_candidates": [8],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "caption_only"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_asset(pdf_path: Path, page_number: int, figure_label: str, artifact_dir: Path, *, zoom: float):
        assert pdf_path == source_pdf
        assert page_number == 8
        assert figure_label == "5"
        return {
            "status": "region_rendered",
            "path": str(asset_path),
            "source": "pdf_figure_region_render",
            "error": "",
            "selected_rect": (10.0, 20.0, 200.0, 160.0),
            "caption_found": True,
        }

    def fail_page_render(*args, **kwargs):
        raise AssertionError("existing page-render recovery should be upgraded before full-page render fallback")

    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fake_asset)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fail_page_render)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["asset_ready_count"] == 1
    assert report["page_render_upgrade_count"] == 1
    assert report["recovery_source_counts"] == {"pdf_figure_region_render": 1}
    article = report["articles"][0]
    assert article["existing_page_render_recovery"] is True
    assert article["existing_page_render_upgrade"] is True
    patched_html = polish_path.read_text(encoding="utf-8")
    assert 'data-z2m-recovery-source="pdf_figure_region_render"' in patched_html
    assert 'data-z2m-recovery-source="pdf_page_render"' not in patched_html
    assert "z2m-missing-figure-warning" not in patched_html


def test_p62_image_recovery_stage_does_not_upgrade_page_render_with_page_render(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-8" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="old_page.png" data-z2m-recovery-source="pdf_page_render" '
        f'alt="Recovered Figure 8 visual from source PDF" src="{_valid_tiny_png_data_url()}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 8. Placeholder-only caption.</p>'
        "</div>",
        encoding="utf-8",
    )
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "8",
                    "resolved_figure_label": "8",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 12,
                    "figure_label_pdf_page_candidates": [12],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "caption_only"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def no_asset(pdf_path: Path, page_number: int, figure_label: str, artifact_dir: Path, *, zoom: float):
        return {
            "status": "no_figure_region",
            "path": "",
            "source": "",
            "error": "No graphic/image region could be associated with the target caption.",
        }

    def fail_page_render(*args, **kwargs):
        raise AssertionError("stale page-render recovery must not be replaced by another page render")

    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", no_asset)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fail_page_render)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "unresolved"
    assert report["asset_ready_count"] == 0
    assert report["page_render_upgrade_count"] == 0
    assert report["page_render_recovery_removed_count"] == 1
    article = report["articles"][0]
    assert article["existing_page_render_recovery"] is True
    assert article["existing_page_render_upgrade"] is False
    assert article["unresolved_reason"] == "existing_pdf_page_render_no_higher_fidelity_asset"
    patched_html = polish_path.read_text(encoding="utf-8")
    assert "z2m-missing-figure-warning" in patched_html
    assert 'data-z2m-recovery-source="pdf_page_render"' not in patched_html
    assert 'data-z2m-recovery-source="pdf_figure_region_render"' not in patched_html


def test_p62_image_recovery_stage_removes_false_match_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fitz = pytest.importorskip("fitz")
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 120), "Insert Figure 9 about here.")
    doc.save(str(source_pdf))
    doc.close()
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-9" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="bad_region.png" data-z2m-recovery-source="pdf_figure_region_render" '
        f'alt="Recovered Figure 9 visual from source PDF" src="{_valid_tiny_png_data_url()}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 9. Placeholder-only caption.</p>'
        "</div>",
        encoding="utf-8",
    )
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "9",
                    "resolved_figure_label": "9",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 1,
                    "figure_label_pdf_page_candidates": [1],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "caption_only"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fail_asset(*args, **kwargs):
        raise AssertionError("false-match recovery should be removed before PDF asset extraction")

    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fail_asset)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "unresolved"
    assert report["asset_ready_count"] == 0
    assert report["false_match_recovery_removed_count"] == 1
    article = report["articles"][0]
    assert article["existing_false_match_recovery"] is True
    assert article["false_match_recovery_removed"] is True
    assert article["source_page_false_match_hint"] == "manuscript_placeholder"
    patched_html = polish_path.read_text(encoding="utf-8")
    assert "z2m-missing-figure-warning" in patched_html
    assert 'data-z2m-recovery-source="pdf_figure_region_render"' not in patched_html


def test_p62_image_recovery_stage_replaces_false_match_recovery_with_probe_asset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fitz = pytest.importorskip("fitz")
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 120), "Insert Figure 10 about here.")
    doc.save(str(source_pdf))
    doc.close()
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-10" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="bad_region.png" data-z2m-recovery-source="pdf_figure_region_render" '
        f'alt="Recovered Figure 10 visual from source PDF" src="{_valid_tiny_png_data_url()}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 10. Recovered elsewhere.</p>'
        "</div>",
        encoding="utf-8",
    )
    asset_path = run_dir / "probe.png"
    asset_path.write_bytes(_valid_tiny_png_bytes())
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "10",
                    "resolved_figure_label": "10",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 1,
                    "figure_label_pdf_page_candidates": [1],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "caption_only"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_probe(*args, **kwargs):
        return {
            "status": "found_asset",
            "asset": {
                "status": "native_image_extracted",
                "path": str(asset_path),
                "source": "pdf_native_image",
                "error": "",
                "page_number": 5,
            },
            "attempts": [{"method": "pdf_label_page_asset", "status": "native_image_extracted"}],
        }

    monkeypatch.setattr(llm_quality_loop, "_probe_p62_source_visual_unavailable", fake_probe)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["asset_ready_count"] == 1
    assert report["source_visual_probe_status_counts"] == {"found_asset": 1}
    assert report["recovery_source_counts"] == {"pdf_native_image": 1}
    article = report["articles"][0]
    assert article["existing_false_match_recovery"] is True
    assert article["false_match_recovery_removed"] is False
    patched_html = polish_path.read_text(encoding="utf-8")
    assert 'data-z2m-recovery-source="pdf_native_image"' in patched_html
    assert 'data-z2m-recovery-source="pdf_figure_region_render"' not in patched_html
    assert "z2m-missing-figure-warning" not in patched_html


def test_p62_image_recovery_stage_repairs_duplicate_existing_figure_after_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    duplicated_payload = base64.b64encode(b"figure-six-image-was-attached-twice").decode("ascii")
    duplicated_data_url = f"data:image/png;base64,{duplicated_payload}"
    polish_path.write_text(
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target">'
        f'<img data-z2m-src="_page_6_Figure_1.jpeg" alt="Figure 5" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Fig. 5. The proportion of mazes successfully navigated.</p>'
        "</div>"
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="marker/_page_6_Figure_1.jpeg" data-z2m-recovery-source="marker_image" '
        f'alt="Recovered Figure 6" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Fig. 6. A heat map showing the relative time difference.</p>'
        "</div>",
        encoding="utf-8",
    )
    asset_path = run_dir / "fig5.png"
    asset_path.write_bytes(_valid_tiny_png_bytes())
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "6",
                    "resolved_figure_label": "6",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 7,
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "recovered_image"},
                }
            ],
        },
    )

    def fake_text_pages(pdf_path: Path, *, max_pages=None):
        assert pdf_path == source_pdf
        return (
            "fixture",
            [
                "",
                "",
                "",
                "",
                "Fig. 5. The proportion of mazes successfully navigated.",
                "Fig. 6. A heat map showing the relative time difference.",
            ],
            None,
        )

    def fake_recover(pdf_path: Path, page_number: int, figure_label: str, output_dir: Path, *, zoom: float):
        assert pdf_path == source_pdf
        assert page_number == 5
        assert figure_label == "5"
        return {
            "status": "native_image_extracted",
            "path": str(asset_path),
            "source": "pdf_native_image",
            "error": "",
            "page_number": page_number,
        }

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_text_pages)
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_false_match_hint", lambda *args, **kwargs: "")
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_caption_label_found", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        llm_quality_loop,
        "_recover_p62_detached_pdf_figure_plate_asset",
        lambda *args, **kwargs: {"status": "not_found"},
    )
    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fake_recover)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["duplicate_visual_repair_count"] == 1
    assert report["articles"][0]["status"] == "patched_duplicate_visuals"
    patched_html = polish_path.read_text(encoding="utf-8")
    assert patched_html.count(duplicated_data_url) == 1
    assert 'data-z2m-recovery-source="pdf_native_image"' in patched_html
    assert 'data-z2m-recovery-source="marker_image"' in patched_html
    assert "Recovered Figure 5 visual from source PDF" in patched_html
    assert "_page_6_Figure_1.jpeg" in patched_html


def test_p62_image_recovery_stage_repairs_duplicate_marker_recovered_figures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    duplicated_payload = base64.b64encode(b"marker-page-image-reused-for-two-labels").decode("ascii")
    duplicated_data_url = f"data:image/png;base64,{duplicated_payload}"
    polish_path.write_text(
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="marker/_page_4_Figure_0.png" data-z2m-recovery-source="marker_image" '
        f'alt="Recovered Figure 1" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 1. First recovered marker visual.</p>'
        "</div>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img data-z2m-src="marker/_page_4_Figure_0.png" data-z2m-recovery-source="marker_image" '
        f'alt="Recovered Figure 2" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 2. Second recovered marker visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    fig1_asset = run_dir / "fig1.png"
    fig2_asset = run_dir / "fig2.png"
    fig1_asset.write_bytes(_tiny_rgba_png_bytes(255, 0, 0))
    fig2_asset.write_bytes(_tiny_rgba_png_bytes(0, 255, 0))
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 2,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "1",
                    "resolved_figure_label": "1",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 5,
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "recovered_image"},
                },
                {
                    "article": "article_a",
                    "figure_label": "2",
                    "resolved_figure_label": "2",
                    "warning_index": 2,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 5,
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "recovered_image"},
                },
            ],
        },
    )

    def fake_text_pages(pdf_path: Path, *, max_pages=None):
        assert pdf_path == source_pdf
        return (
            "fixture",
            [
                "",
                "",
                "",
                "",
                "Figure 1. First recovered marker visual. Figure 2. Second recovered marker visual.",
            ],
            None,
        )

    def fake_recover(pdf_path: Path, page_number: int, figure_label: str, output_dir: Path, *, zoom: float):
        assert pdf_path == source_pdf
        assert page_number == 5
        asset_path = fig1_asset if figure_label == "1" else fig2_asset
        return {
            "status": "region_rendered",
            "path": str(asset_path),
            "source": "pdf_figure_region_render",
            "error": "",
            "page_number": page_number,
        }

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_text_pages)
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_false_match_hint", lambda *args, **kwargs: "")
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_caption_label_found", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        llm_quality_loop,
        "_recover_p62_detached_pdf_figure_plate_asset",
        lambda *args, **kwargs: {"status": "not_found"},
    )
    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fake_recover)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["duplicate_visual_repair_count"] == 2
    assert report["status_counts"] == {"already_patched": 1, "patched_duplicate_visuals": 1}
    repairs = report["articles"][0]["duplicate_visual_repairs"]
    assert [repair["figure_label"] for repair in repairs if repair["status"] == "patched"] == ["1", "2"]
    assert {repair["repair_mode"] for repair in repairs if repair["status"] == "patched"} == {
        "recovered_duplicate_target"
    }
    patched_html = polish_path.read_text(encoding="utf-8")
    assert duplicated_data_url not in patched_html
    assert patched_html.count('data-z2m-recovery-source="pdf_figure_region_render"') == 2
    hashes = {
        llm_quality_loop._p62_data_url_image_hash(match.group(0))
        for match in re.finditer(r"<img\b[^>]*>", patched_html, re.IGNORECASE | re.DOTALL)
    }
    assert len(hashes) == 2


def test_p62_image_recovery_stage_parallelizes_by_article_and_preserves_record_order(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    for article in ("article_a", "article_b"):
        for path in (
            run_dir / "polish" / f"{article}.02.en.polish.html",
            run_dir / "audit_tree" / article / "02.en.polish.html",
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f'<html><body><div id="fig-1">Figure 1. Already present for {article}.</div></body></html>',
                encoding="utf-8",
            )
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 3,
            "articles": [
                {"article": "article_a", "figure_label": "1", "status": "ready"},
                {"article": "article_b", "figure_label": "1", "status": "ready"},
                {"article": "article_a", "figure_label": "2", "status": "ready"},
            ],
        },
    )
    _write_json(
        run_dir / "manifest.json",
        {"articles": [{"article_id": "article_a"}, {"article_id": "article_b"}]},
    )
    _write_json(run_dir / "assessment.json", {"article_count": 2, "totals": {}, "articles": []})

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={
            "p62_image_recovery_jobs": 2,
            "p62_image_recovery_repair_duplicate_figure_images": False,
        },
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["jobs"] == 2
    assert report["selected_count"] == 3
    assert [article["record_index"] for article in report["articles"]] == [1, 2, 3]
    assert [article["article"] for article in report["articles"]] == ["article_a", "article_b", "article_a"]
    assert report["status_counts"] == {"already_patched": 3}


def test_p62_image_recovery_stage_parallel_resume_skips_completed_article_reports(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    article_b_polish = run_dir / "polish" / "article_b.02.en.polish.html"
    article_b_audit = run_dir / "audit_tree" / "article_b" / "02.en.polish.html"
    for path in (article_b_polish, article_b_audit):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '<html><body><div id="fig-1">Figure 1. Already present.</div></body></html>',
            encoding="utf-8",
        )
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 2,
            "articles": [
                {"article": "article_a", "figure_label": "1", "status": "ready"},
                {"article": "article_b", "figure_label": "1", "status": "ready"},
            ],
        },
    )
    _write_json(
        run_dir / "manifest.json",
        {"articles": [{"article_id": "article_a"}, {"article_id": "article_b"}]},
    )
    _write_json(run_dir / "assessment.json", {"article_count": 2, "totals": {}, "articles": []})
    parallel_root = run_dir / "p62_image_recovery" / "_parallel_article_plans"
    parallel_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        parallel_root / "001_article_a.report.json",
        {
            "articles": [
                {
                    "article": "article_a",
                    "record_index": 1,
                    "figure_label": "1",
                    "status": "already_patched",
                    "asset_status": "ready",
                }
            ],
            "patched_articles": [],
            "asset_ready_count": 0,
            "patched_warning_count": 0,
        },
    )

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={
            "p62_image_recovery_jobs": 2,
            "p62_image_recovery_repair_duplicate_figure_images": False,
        },
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert [article["record_index"] for article in report["articles"]] == [1, 2]
    assert [article["article"] for article in report["articles"]] == ["article_a", "article_b"]
    assert report["status_counts"] == {"already_patched": 2}


def test_polish_auto_repair_stage_parallelizes_by_article_and_merges_reports(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    audit_articles = []
    for article, ref_number in (("article_a", 1), ("article_b", 2)):
        for path in (
            run_dir / "polish" / f"{article}.02.en.polish.html",
            run_dir / "audit_tree" / article / "02.en.polish.html",
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "<html><body>"
                f'<p>External citation <a href="https://app.readcube.com/item-{ref_number}">[{ref_number}]</a>.</p>'
                "<h4>References</h4>"
                f'<ol><li id="ref-{ref_number}">Reference {ref_number}.</li></ol>'
                "</body></html>",
                encoding="utf-8",
            )
        audit_articles.append(
            {
                "article": article,
                "summary": {},
                "defects_found": [{"id": "P04N", "extra": {"candidate_numbers": [ref_number]}}],
            }
        )
    _write_json(run_dir / "audit_full_checks.json", {"articles": audit_articles})
    _write_json(
        run_dir / "manifest.json",
        {"articles": [{"article_id": "article_a"}, {"article_id": "article_b"}]},
    )
    _write_json(run_dir / "assessment.json", {"article_count": 2, "totals": {}, "articles": []})

    report = write_polish_auto_repair_stage(run_dir, gate_config={"polish_auto_repair_jobs": 2})

    assert report["status"] == "patched"
    assert report["jobs"] == 2
    assert report["patched_article_count"] == 2
    assert report["patched_articles"] == ["article_a", "article_b"]
    assert [article["index"] for article in report["articles"]] == [1, 2]
    assert set(report["repair_counts"]) == {"P04"}
    for article, ref_number in (("article_a", 1), ("article_b", 2)):
        html = (run_dir / "polish" / f"{article}.02.en.polish.html").read_text(encoding="utf-8")
        assert f'href="#ref-{ref_number}"' in html


def test_polish_auto_repair_stage_repairs_p71_ocr_residues(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    article = "article_p71"
    polish_path = run_dir / "polish" / f"{article}.02.en.polish.html"
    audit_tree_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    for path in (polish_path, audit_tree_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<html><body>"
            "<p>The cross validtation accuracy used 0:5mLs{ 1 mm{ 1 and FA 330.</p>"
            "<p>The table kept 0:5mLs{ <sup>1</sup> mm{ <sup>1</sup>, "
            "9 <sup>m</sup> m, IPP Grade<sup class=\"z2m-table-fn\">iii</sup>, "
            "Gen-A<sup class=\"z2m-table-fn\">i</sup>, and a ghraph.</p>"
            "<p>The article mentioned a health male volunteer, Dl5660620 nm, Cvalli, "
            "Authers, afrer 5 min, and a defensen protein.</p>"
            "<p>Other residues had (Rgiht) labels, tranformed analytes, and et nl. references.</p>"
            "<p>References had Verebrate Endocrinology, Naturwissenschaftem, Foundayion, and millenium.</p>"
            "<p>The assay coditions imlied oberved occurance with realtive speices that responsed "
            "in a treaditional way. Furhtermore, Electronic(Cambridge appeared.</p>"
            "<p>Museum of Moden Art reported around287.8 eV.</p>"
            "</body></html>",
            encoding="utf-8",
        )
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {},
                    "defects_found": [{"id": "P71"}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    report = write_polish_auto_repair_stage(run_dir, gate_config={})

    assert report["status"] == "patched"
    assert report["repair_counts"] == {"P71": 2}
    assert report["patched_articles"] == [article]
    for path in (polish_path, audit_tree_path):
        html = path.read_text(encoding="utf-8")
        assert (
            'cross validation accuracy used 0.5 mL s<sup class="z2m-unit-exp">-1</sup> '
            'mm<sup class="z2m-unit-exp">-1</sup> and FA 33°'
        ) in html
        assert (
            'table kept 0.5 mL s<sup class="z2m-unit-exp">-1</sup> '
            'mm<sup class="z2m-unit-exp">-1</sup>, 9 mm, IPP Grade III, Gen-AI, and a graph'
        ) in html
        assert "healthy male volunteer, Delta lambda=660 +/- 20 nm, Cavalli" in html
        assert "Authors, after 5 min, and a defensin protein" in html
        assert "Other residues had (Right) labels, transformed analytes, and et al. references" in html
        assert "Vertebrate Endocrinology, Naturwissenschaften, Foundation, and millennium" in html
        assert "assay conditions implied observed occurrence with relative species that responded" in html
        assert "in a traditional way. Furthermore, Electronics (Cambridge appeared" in html
        assert "Museum of Modern Art reported around 287.8 eV" in html


def test_polish_auto_repair_stage_repairs_p06_flat_unit_exponents(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    article = "article_p06"
    polish_path = run_dir / "polish" / f"{article}.02.en.polish.html"
    audit_tree_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    for path in (polish_path, audit_tree_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<html><body><p>where k is found to be 0.5 mL s-1 mm-1.</p></body></html>",
            encoding="utf-8",
        )
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {},
                    "defects_found": [{"id": "P06"}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    report = write_polish_auto_repair_stage(run_dir, gate_config={})

    assert report["status"] == "patched"
    assert report["repair_counts"] == {"P06": 2}
    assert report["patched_articles"] == [article]
    for path in (polish_path, audit_tree_path):
        html = path.read_text(encoding="utf-8")
        assert (
            '0.5 mL s<sup class="z2m-unit-exp">-1</sup> '
            'mm<sup class="z2m-unit-exp">-1</sup>'
        ) in html


def test_polish_auto_repair_stage_repairs_reference_numbers_and_author_year_numeric_links(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    article = "article_a"
    polish_path = run_dir / "polish" / f"{article}.02.en.polish.html"
    audit_tree_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    for path in (polish_path, audit_tree_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<html><body>"
            '<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 '
            'mark author-year style, while <sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> '
            'is not a bibliography citation. <a href="#ref-3" class="z2m-ref-link">Flores</a> '
            "et al. (2015) is author-year prose.</p>"
            "<h4>References</h4><ol>"
            '<li id="ref-1">[1] Already visibly numbered.</li>'
            '<li id="ref-2">Missing visible number.</li>'
            '<li id="ref-3">[3] Flores, A. Example citation.</li>'
            "</ol></body></html>",
            encoding="utf-8",
        )
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {},
                    "defects_found": [
                        {"id": "P55", "extra": {"ref_target": "3", "label": "Flores"}},
                        {"id": "P97", "extra": {"missing_visible_ref_ids": [2]}},
                        {"id": "P98", "extra": {"ref_target": "2"}},
                    ],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    report = write_polish_auto_repair_stage(run_dir, gate_config={})

    assert report["status"] == "patched"
    assert report["patched_article_count"] == 1
    assert report["repair_counts"] == {"P55": 2, "P97": 2, "P98": 2}
    for path in (polish_path, audit_tree_path):
        html = path.read_text(encoding="utf-8")
        before_refs = html[: html.index("References")]
        assert 'href="#ref-2"' not in html[: html.index("References")]
        assert 'href="#ref-3"' not in before_refs
        assert "Flores</a>" not in before_refs
        assert "Flores et al. (2015)" in before_refs
        assert '<span class="z2m-ref-num">2.</span> Missing visible number.' in html
        assert "[1] Already visibly numbered." in html
        assert '<li id="ref-3">[3] Flores, A. Example citation.</li>' in html


def test_polish_auto_repair_stage_repairs_external_numeric_citation_anchors(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    article = "article_a"
    polish_path = run_dir / "polish" / f"{article}.02.en.polish.html"
    audit_tree_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    for path in (polish_path, audit_tree_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<html><body>"
            '<p>Blindness prevention <a href="https://app.readcube.com/library/item-1">[1]</a> '
            'and restorative treatments <a href="https://app.readcube.com/library/item-2">[2,3]</a> '
            "remain active areas.</p>"
            "<h4>References</h4>"
            '<p block-type="ListGroup"><ul>'
            '<li id="ref-1">First reference.</li>'
            '<li id="ref-2">Second reference.</li>'
            '<li id="ref-3">Third reference.</li>'
            "</ul></p>"
            "</body></html>",
            encoding="utf-8",
        )
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {},
                    "defects_found": [{"id": "P04N", "extra": {"candidate_numbers": [2, 3]}}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    report = write_polish_auto_repair_stage(run_dir, gate_config={})

    assert report["status"] == "patched"
    assert report["patched_article_count"] == 1
    assert report["repair_counts"] == {"P04": 4}
    for path in (polish_path, audit_tree_path):
        html = path.read_text(encoding="utf-8")
        before_refs = html[: html.index("References")]
        assert "readcube.com" not in before_refs
        assert '<a href="#ref-1" class="z2m-ref-link">[1]</a>' in before_refs
        assert '[<a href="#ref-2" class="z2m-ref-link">2</a>,' in before_refs
        assert '<a href="#ref-3" class="z2m-ref-link">3</a>]' in before_refs


def test_polish_auto_repair_stage_unwraps_broken_internal_links_from_assessment(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    article = "article_a"
    polish_path = run_dir / "polish" / f"{article}.02.en.polish.html"
    audit_tree_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    for path in (polish_path, audit_tree_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<html><body>"
            '<p><a href="#fig-1" class="z2m-fig-link">Figure 1</a> remains valid, '
            'but <a href="#fig-2" class="z2m-fig-link">Figure 2</a> is stale and '
            '<a href="#ref-9" class="z2m-ref-link">9</a> is also stale.</p>'
            '<div id="fig-1" class="z2m-figure-unit">Figure 1.</div>'
            "</body></html>",
            encoding="utf-8",
        )
    _write_json(run_dir / "audit_full_checks.json", {"articles": []})
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(
        run_dir / "assessment.json",
        {
            "article_count": 1,
            "totals": {"broken_internal_links": 2},
            "articles": [
                {
                    "article": article,
                    "href_counts": {"broken_internal_links": 2},
                    "broken_targets": ["fig-2", "ref-9"],
                }
            ],
        },
    )

    report = write_polish_auto_repair_stage(run_dir, gate_config={})

    assert report["status"] == "patched"
    assert report["candidate_count"] == 1
    assert report["repair_counts"] == {"broken_internal_links": 4}
    for path in (polish_path, audit_tree_path):
        html = path.read_text(encoding="utf-8")
        assert '<a href="#fig-1" class="z2m-fig-link">Figure 1</a>' in html
        assert 'href="#fig-2"' not in html
        assert 'href="#ref-9"' not in html
        assert "Figure 2" in html


def test_polish_auto_repair_stage_repairs_p59_numeric_labels(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    article = "article_a"
    polish_path = run_dir / "polish" / f"{article}.02.en.polish.html"
    audit_tree_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    for path in (polish_path, audit_tree_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<html><body>"
            '<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 '
            'mark author-year style. map <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup>: '
            "doll, cat, knife.</p>"
            "<h4>References</h4><ol>"
            '<li id="ref-1">[1] Real bibliography entry.</li>'
            "</ol></body></html>",
            encoding="utf-8",
        )
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {},
                    "defects_found": [{"id": "P59", "extra": {"ref_target": "1"}}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    report = write_polish_auto_repair_stage(run_dir, gate_config={})

    assert report["status"] == "patched"
    assert report["patched_article_count"] == 1
    assert report["repair_counts"] == {"P59": 2}
    for path in (polish_path, audit_tree_path):
        html = path.read_text(encoding="utf-8")
        before_refs = html[: html.index("References")]
        assert 'href="#ref-1"' not in before_refs
        assert "map <sup>1</sup>: doll, cat, knife" in before_refs
        assert '<li id="ref-1">[1] Real bibliography entry.</li>' in html


def test_polish_auto_repair_stage_repairs_p17_spaced_multipanel_refs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    article = "article_a"
    polish_path = run_dir / "polish" / f"{article}.02.en.polish.html"
    audit_tree_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    html = (
        "<html><body>"
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-caption">Figure 7. Panels.</p>'
        "</div>"
        "<p>The origin is located at the top left corner (see Figure \n 7 (b)).</p>"
        "</body></html>"
    )
    for path in (polish_path, audit_tree_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {},
                    "defects_found": [{"id": "P17"}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    report = write_polish_auto_repair_stage(run_dir, gate_config={})

    assert report["status"] == "patched"
    assert report["patched_article_count"] == 1
    assert report["repair_counts"] == {"P17": 2}
    for path in (polish_path, audit_tree_path):
        repaired = path.read_text(encoding="utf-8")
        assert '<a href="#fig-7" class="z2m-fig-link">Figure\xa07</a> (b)' in repaired


def test_polish_auto_repair_stage_repairs_plain_duplicate_figure_visuals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    article = "article_a"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    duplicated_payload = base64.b64encode(b"plain-duplicate-visual").decode("ascii")
    duplicated_data_url = f"data:image/png;base64,{duplicated_payload}"
    polish_path.write_text(
        '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target">'
        f'<img alt="Figure 1" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 1. First source visual.</p>'
        "</div>"
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target">'
        f'<img alt="Figure 2" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 2. Second source visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    fig1_asset = run_dir / "fig1.png"
    fig2_asset = run_dir / "fig2.png"
    fig1_asset.write_bytes(_tiny_rgba_png_bytes(255, 0, 0))
    fig2_asset.write_bytes(_tiny_rgba_png_bytes(0, 255, 0))
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {"source_pdf_path": str(source_pdf)},
                    "defects_found": [{"id": "P96", "extra": {"figure_ids": ["fig-1", "fig-2"]}}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_text_pages(pdf_path: Path, *, max_pages=None):
        assert pdf_path == source_pdf
        return ("fixture", ["Figure 1. First source visual.", "Figure 2. Second source visual."], None)

    def fake_recover(pdf_path: Path, page_number: int, figure_label: str, output_dir: Path, *, zoom: float):
        assert pdf_path == source_pdf
        asset_path = fig1_asset if figure_label == "1" else fig2_asset
        return {
            "status": "region_rendered",
            "path": str(asset_path),
            "source": "pdf_figure_region_render",
            "error": "",
            "page_number": page_number,
        }

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_text_pages)
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_false_match_hint", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        llm_quality_loop,
        "_recover_p62_detached_pdf_figure_plate_asset",
        lambda *args, **kwargs: {"status": "not_found"},
    )
    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fake_recover)

    report = write_polish_auto_repair_stage(run_dir, gate_config={"polish_auto_repair_render_zoom": 1.0})

    assert report["status"] == "patched"
    assert report["repair_counts"] == {"P96": 2}
    patched_html = polish_path.read_text(encoding="utf-8")
    assert duplicated_data_url not in patched_html
    assert patched_html.count('data-z2m-recovery-source="pdf_figure_region_render"') == 2
    repairs = report["articles"][0]["repairs"][0]["repairs"]
    assert {repair["repair_mode"] for repair in repairs if repair["status"] == "patched"} == {
        "plain_duplicate_group"
    }


def test_polish_auto_repair_stage_rejects_strip_like_duplicate_region_assets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    article = "article_a"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    duplicated_payload = base64.b64encode(b"plain-duplicate-visual").decode("ascii")
    duplicated_data_url = f"data:image/png;base64,{duplicated_payload}"
    polish_path.write_text(
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target">'
        f'<img alt="Figure 2" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 2. Query-based signage and door detection.</p>'
        "</div>"
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target">'
        f'<img alt="Figure 5" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 5. Experimental evaluation examples.</p>'
        "</div>",
        encoding="utf-8",
    )
    strip_asset = run_dir / "header_strip.png"
    strip_asset.write_bytes(_rgba_png_bytes(769, 40, 255, 255, 255))
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {"source_pdf_path": str(source_pdf)},
                    "defects_found": [{"id": "P96", "extra": {"figure_ids": ["fig-2", "fig-5"]}}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_text_pages(pdf_path: Path, *, max_pages=None):
        assert pdf_path == source_pdf
        return ("fixture", ["Figure 2. Query-based signage.", "Figure 5. Experimental evaluation."], None)

    def fake_recover(pdf_path: Path, page_number: int, figure_label: str, output_dir: Path, *, zoom: float):
        assert pdf_path == source_pdf
        return {
            "status": "region_rendered",
            "path": str(strip_asset),
            "source": "pdf_figure_region_render",
            "error": "",
            "page_number": page_number,
        }

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_text_pages)
    monkeypatch.setattr(llm_quality_loop, "_p62_pdf_page_false_match_hint", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        llm_quality_loop,
        "_recover_p62_detached_pdf_figure_plate_asset",
        lambda *args, **kwargs: {"status": "not_found"},
    )
    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fake_recover)

    report = write_polish_auto_repair_stage(run_dir, gate_config={"polish_auto_repair_render_zoom": 1.0})

    assert report["status"] == "no_changes"
    assert report["repair_counts"] == {}
    patched_html = polish_path.read_text(encoding="utf-8")
    assert patched_html.count(duplicated_data_url) == 2
    assert 'data-z2m-recovery-source="pdf_figure_region_render"' not in patched_html
    repairs = report["articles"][0]["repairs"][0]["repairs"]
    assert {repair["reason"] for repair in repairs} == {"pdf_region_asset_looks_like_page_strip"}
    assert {repair["asset_dimensions"]["height"] for repair in repairs} == {40}


def test_polish_auto_repair_stage_uses_zotero_title_pdf_fallback_for_p96(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    article = (
        "Zotero_Elvis_D_C37DAWJT_2754214_17806620590000_"
        "Custom_Zotero_Fallback_Mobility_Paper_With_Unique_Nebula_Marker"
    )
    polish_path = run_dir / "audit_tree" / article / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="data:image/png;base64,dup"/></p>'
        '<p class="z2m-figure-caption">Figure 5. A virtual environment.</p>'
        "</div>"
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="data:image/png;base64,dup"/></p>'
        '<p class="z2m-figure-caption">Figure 6. Questionnaire.</p>'
        "</div>",
        encoding="utf-8",
    )
    zotero_root = tmp_path / "Zotero_Elvis_Data"
    storage_dir = zotero_root / "storage" / "LQQBDBNU"
    storage_dir.mkdir(parents=True)
    source_pdf = (
        storage_dir
        / "Example - 2024 - Custom Zotero Fallback Mobility Paper With Unique Nebula Marker.pdf"
    )
    source_pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("ZOTERO_PATH_PREFIX_MAP", f"/zotero_roots/test_zotero={zotero_root}")
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "summary": {"source_pdf_path": str(polish_path.parent / "00.source.pdf")},
                    "defects_found": [{"id": "P96", "extra": {"figure_ids": ["fig-5", "fig-6"]}}],
                }
            ]
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": article}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})
    captured: dict[str, Path] = {}

    def fake_duplicate_repair(targets, *, pdf_path: Path, artifact_dir: Path, zoom: float, repair_plain_duplicates: bool):
        captured["pdf_path"] = pdf_path
        return {"repair_count": 1, "patched_paths": [str(polish_path)], "repairs": [], "errors": []}

    monkeypatch.setattr(llm_quality_loop, "_apply_p62_duplicate_figure_image_repairs", fake_duplicate_repair)

    report = write_polish_auto_repair_stage(run_dir, gate_config={"polish_auto_repair_render_zoom": 1.0})

    assert captured["pdf_path"] == source_pdf.resolve(strict=False)
    assert report["status"] == "patched"
    assert report["repair_counts"] == {"P96": 1}


def test_p62_image_recovery_stage_uses_detached_plate_before_region_crop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "accepted.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-2" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 2 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">FIG. 2. Detached plate visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    asset_path = run_dir / "plate.png"
    asset_path.write_bytes(_valid_tiny_png_bytes())
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "2",
                    "resolved_figure_label": "2",
                    "warning_index": 1,
                    "status": "ready",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 4,
                    "figure_label_pdf_page_candidates": [4, 12],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "caption_only"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_detached(pdf_path: Path, page_number: int, figure_label: str, artifact_dir: Path, *, zoom: float):
        assert pdf_path == source_pdf
        assert page_number == 4
        assert figure_label == "2"
        return {
            "status": "detached_plate_rendered",
            "path": str(asset_path),
            "source": "pdf_detached_plate_region_render",
            "error": "",
            "page_number": 16,
            "selected_rect": (96.0, 72.0, 360.0, 220.0),
            "plate_index": 2,
            "plate_count": 3,
        }

    def fail_region_crop(*args, **kwargs):
        raise AssertionError("Detached plate should be used before ordinary region crop")

    def fail_page_render(*args, **kwargs):
        raise AssertionError("Detached plate should be used before full-page render fallback")

    monkeypatch.setattr(llm_quality_loop, "_recover_p62_detached_pdf_figure_plate_asset", fake_detached)
    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fail_region_crop)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fail_page_render)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["recovery_source_counts"] == {"pdf_detached_plate_region_render": 1}
    article = report["articles"][0]
    assert article["figure_asset_status"] == "detached_plate_rendered"
    assert article["figure_asset_page_number"] == 16
    assert article["figure_asset_plate_index"] == 2
    patched_html = polish_path.read_text(encoding="utf-8")
    assert 'data-z2m-recovery-source="pdf_detached_plate_region_render"' in patched_html
    assert "z2m-missing-figure-warning" not in patched_html


def test_p62_image_recovery_stage_does_not_render_unmatched_page_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    warning = "Figure 25 image was not extracted into this HTML."
    polish_path.write_text(
        '<div id="fig-25" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        f'<p class="z2m-missing-figure-warning z2m-figure-target" role="note">{warning}</p>'
        '<p class="z2m-figure-caption">Figure 25. Complexity and customization versus learning rate.</p>'
        "</div>",
        encoding="utf-8",
    )
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "25",
                    "warning_index": 1,
                    "status": "figure_label_page_unavailable",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 72,
                    "figure_label_pdf_page_candidates": [],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "not_run"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fail_render(*args, **kwargs):
        raise AssertionError("unmatched P62 records must not render arbitrary PDF pages")

    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fail_render)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=False,
    )

    assert report["status"] == "unresolved"
    assert report["asset_ready_count"] == 0
    assert report["unresolved_count"] == 1
    assert report["articles"][0]["unresolved_reason"] == "page_render_fallback_requires_figure_label_page"
    patched_html = polish_path.read_text(encoding="utf-8")
    assert "z2m-missing-figure-warning" in patched_html
    assert "z2m-p62-recovered-target" not in patched_html


def test_p62_image_recovery_stage_probes_source_visual_unavailable_before_skipping(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 3 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">Figure 3. A recovered source visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    asset_path = run_dir / "probe.png"
    asset_path.write_bytes(_valid_tiny_png_bytes())
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "3",
                    "resolved_figure_label": "3",
                    "warning_index": 1,
                    "status": "source_visual_unavailable",
                    "source_visual_unavailable_reason": "all_label_matches_are_false_or_without_visual_objects",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 10,
                    "figure_label_pdf_page_candidates": [10],
                    "problem_snippets": ["Figure 3. A recovered source visual."],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "caption_only"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    def fake_probe(
        pdf_path: Path,
        figure_label: str,
        artifact_dir: Path,
        *,
        snippets: list[str] | None,
        zoom: float,
        run_marker: bool,
        marker_timeout_seconds: int,
        marker_output_dir: Path | None,
    ):
        assert pdf_path == source_pdf
        assert figure_label == "3"
        assert snippets == ["Figure 3. A recovered source visual."]
        assert zoom == 1.0
        assert run_marker is True
        assert marker_timeout_seconds == 77
        assert artifact_dir.name == "source_visual_probe"
        assert marker_output_dir is not None
        assert marker_output_dir.parent.name == "_source_visual_probe_marker"
        return {
            "status": "found_asset",
            "asset": {
                "status": "region_rendered",
                "path": str(asset_path),
                "source": "pdf_figure_region_render",
                "error": "",
                "page_number": 12,
                "selected_rect": (10.0, 20.0, 200.0, 120.0),
                "caption_found": True,
            },
            "attempts": [{"method": "pdf_label_page_asset", "status": "region_rendered"}],
        }

    def fail_page_render(*args, **kwargs):
        raise AssertionError("probe-recovered records must not render a full PDF page")

    monkeypatch.setattr(llm_quality_loop, "_probe_p62_source_visual_unavailable", fake_probe)
    monkeypatch.setattr(llm_quality_loop, "_render_pdf_evidence_page", fail_page_render)

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={
            "p62_image_recovery_render_zoom": 1.0,
            "p62_image_recovery_probe_marker_for_unavailable": True,
            "p62_image_recovery_source_visual_probe_marker_timeout_seconds": 77,
        },
        execute_marker=False,
    )

    assert report["status"] == "ready"
    assert report["asset_ready_count"] == 1
    assert report["source_visual_probe_status_counts"] == {"found_asset": 1}
    assert report["recovery_source_counts"] == {"pdf_figure_region_render": 1}
    article = report["articles"][0]
    assert article["source_visual_probe_status"] == "found_asset"
    assert article["figure_asset_page_number"] == 12
    patched_html = polish_path.read_text(encoding="utf-8")
    assert 'data-z2m-recovery-source="pdf_figure_region_render"' in patched_html
    assert "z2m-missing-figure-warning" not in patched_html


def test_p62_image_recovery_stage_records_unavailable_probe_when_not_found(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    polish_path = run_dir / "audit_tree" / "article_a" / "02.en.polish.html"
    polish_path.parent.mkdir(parents=True)
    polish_path.write_text(
        '<div id="fig-4" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 4 image was not extracted into this HTML.</p>"
        '<p class="z2m-figure-caption">Figure 4. Missing source visual.</p>'
        "</div>",
        encoding="utf-8",
    )
    plan_path = run_dir / "p62_marker_recovery_plan.json"
    _write_json(
        plan_path,
        {
            "candidate_count": 1,
            "articles": [
                {
                    "article": "article_a",
                    "figure_label": "4",
                    "resolved_figure_label": "4",
                    "warning_index": 1,
                    "status": "source_visual_unavailable",
                    "source_pdf_path": str(source_pdf),
                    "source_pdf_page_number": 14,
                    "figure_label_pdf_page_candidates": [14],
                    "polish_stage_path": str(polish_path),
                    "existing_marker_output_validation": {"status": "empty_or_unmatched"},
                }
            ],
        },
    )
    _write_json(run_dir / "manifest.json", {"articles": [{"article_id": "article_a"}]})
    _write_json(run_dir / "assessment.json", {"article_count": 1, "totals": {}, "articles": []})

    monkeypatch.setattr(
        llm_quality_loop,
        "_probe_p62_source_visual_unavailable",
        lambda *args, **kwargs: {
            "status": "not_found",
            "label_pages": [14],
            "attempts": [{"status": "skipped_false_label_match"}],
            "visual_inventory": {"status": "ready", "native_image_count": 0},
            "asset": {},
        },
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "_validate_p62_marker_output",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("empty marker_output_dir must not be scanned")
        ),
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "_render_pdf_evidence_page",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("source_visual_unavailable must not fall through to full-page render")
        ),
    )

    report = write_p62_image_recovery_stage(
        run_dir,
        plan_path=plan_path,
        gate_config={"p62_image_recovery_render_zoom": 1.0},
        execute_marker=True,
    )

    assert report["status"] == "unresolved"
    assert report["source_visual_probe_status_counts"] == {"not_found": 1}
    article = report["articles"][0]
    assert article["unresolved_reason"] == "source_visual_unavailable"
    assert article["source_visual_probe_status"] == "not_found"
    assert article["source_visual_probe"]["label_pages"] == [14]
    assert "z2m-missing-figure-warning" in polish_path.read_text(encoding="utf-8")


def test_p62_source_visual_probe_skips_false_label_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    def fake_pages(pdf_path: Path, *, max_pages: int | None = None):
        assert pdf_path == source_pdf
        assert max_pages is None
        return (
            "fake",
            [
                "Contents\nFigure 5 Virtual walking trial results ........ 22",
                "Participants used look-around mode (Figure 5) during the experiment.",
                "Insert Figure 5 about here",
            ],
            None,
        )

    monkeypatch.setattr(llm_quality_loop, "_pdf_text_pages", fake_pages)
    monkeypatch.setattr(
        llm_quality_loop,
        "_p62_pdf_page_visual_summaries",
        lambda pdf_path, pages: {page: {"image_xrefs": 0, "image_blocks": 0, "drawings": 0} for page in pages},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "_p62_pdf_visual_inventory",
        lambda pdf_path: {
            "status": "ready",
            "page_count": 3,
            "native_image_count": 0,
            "large_image_count": 0,
            "pages_with_native_images": [],
            "pages_with_large_images": [],
            "error": "",
        },
    )

    def fail_recover(*args, **kwargs):
        raise AssertionError("false label matches should not be cropped as figures")

    monkeypatch.setattr(llm_quality_loop, "_recover_p62_detached_pdf_figure_plate_asset", fail_recover)
    monkeypatch.setattr(llm_quality_loop, "_recover_p62_pdf_figure_asset", fail_recover)

    probe = llm_quality_loop._probe_p62_source_visual_unavailable(
        source_pdf,
        "5",
        tmp_path / "probe",
        snippets=["Figure 5. Virtual walking trial results."],
        zoom=1.0,
        run_marker=False,
    )

    assert probe["status"] == "not_found"
    assert probe["label_pages"] == [1, 2, 3]
    assert {attempt["status"] for attempt in probe["attempts"]} == {"skipped_false_label_match"}
    assert probe["visual_inventory"]["native_image_count"] == 0


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


def test_observe_accepts_parallel_document_job_overrides() -> None:
    args = parse_args(
        [
            "observe",
            "--source-run-dir",
            "source_run",
            "--out-dir",
            "out_run",
            "--jobs",
            "64",
            "--repolish-jobs",
            "32",
            "--audit-jobs",
            "48",
            "--p62-marker-recovery-jobs",
            "7",
            "--p62-recovery-jobs",
            "8",
            "--polish-auto-repair-jobs",
            "9",
        ]
    )

    assert args.jobs == 64
    assert args.repolish_jobs == 32
    assert args.audit_jobs == 48
    assert args.p62_marker_recovery_jobs == 7
    assert args.p62_recovery_jobs == 8
    assert args.polish_auto_repair_jobs == 9


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


def test_observe_defaults_converted_roots_to_repolish_mode() -> None:
    default_args = parse_args(["observe", "--converted-roots", "converted_root", "--out-dir", "out_run"])
    audit_only_args = parse_args(
        [
            "observe",
            "--converted-roots",
            "converted_root",
            "--audit-converted-existing",
            "--out-dir",
            "out_run",
        ]
    )

    assert default_args.repolish_converted_raw is True
    assert audit_only_args.repolish_converted_raw is False


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


def test_assessment_does_not_count_http_page_query_links_as_local_page_queries() -> None:
    html = (
        "<html><body>"
        '<p><a href="https://example.org/items?page=4">external page query</a> '
        '<a href="viewer.html?page=4">local viewer</a> '
        '<a href="?page=5">local query</a></p>'
        "</body></html>"
    )

    assessment = assess_polish_html("article_a", html, {"status": "ok", "style": "unknown", "confidence": "low"})

    assert assessment["href_counts"]["external_page_query_links"] == 2


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


def test_prepare_converted_run_rejects_uncommitted_raw_stage(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / RAW_STAGE_NAME).write_text(
        "<html><body><p>Raw</p></body></html>",
        encoding="utf-8",
    )
    (stage_dir / POLISH_STAGE_NAME).write_text(
        "<html><body><p>Polish</p></body></html>",
        encoding="utf-8",
    )

    run_dir = tmp_path / "run"
    with pytest.raises(RuntimeError, match="manifest_missing"):
        prepare_converted_run([root], run_dir)
    assert not run_dir.exists()
    cache_dir = tmp_path / "cache"
    with pytest.raises(RuntimeError, match="manifest_missing"):
        prepare_converted_raw_cache([root], cache_dir)
    assert not cache_dir.exists()


def test_prepare_converted_raw_cache_preserves_existing_owned_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "Doc" / "_z2m_stages"
    _write_current_converted_pair(
        stage_dir,
        raw_html="<html><body><p>Validated raw.</p></body></html>",
        polish_html="<html><body><p>Polish.</p></body></html>",
    )
    out_dir = tmp_path / "source"
    sentinel = out_dir / "raw_cache" / "sentinel.bin"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"keep-existing-cache")
    manifest_path = out_dir / "manifest.json"
    original_manifest = '{"sentinel": true}\n'
    manifest_path.write_text(original_manifest, encoding="utf-8")

    with pytest.raises(FileExistsError, match="already contains owned artifacts"):
        prepare_converted_raw_cache([root], out_dir)

    assert sentinel.read_bytes() == b"keep-existing-cache"
    assert manifest_path.read_text(encoding="utf-8") == original_manifest
    assert not (out_dir / "profiles").exists()


def test_prepare_converted_raw_cache_rejects_unrelated_existing_artifact_before_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "Doc" / "_z2m_stages"
    _write_current_converted_pair(
        stage_dir,
        raw_html="<html><body><p>Validated raw.</p></body></html>",
        polish_html="<html><body><p>Polish.</p></body></html>",
    )
    out_dir = tmp_path / "source"
    stale = out_dir / "audit_full_checks.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"stale": true}\n', encoding="utf-8")

    with pytest.raises(FileExistsError, match="already contains artifacts"):
        prepare_converted_raw_cache([root], out_dir)

    assert stale.read_text(encoding="utf-8") == '{"stale": true}\n'
    assert not (out_dir / "raw_cache").exists()
    assert not (out_dir / "profiles").exists()
    assert not (out_dir / "manifest.json").exists()


def test_prepare_converted_raw_cache_rechecks_output_after_source_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "Doc" / "_z2m_stages"
    _write_current_converted_pair(
        stage_dir,
        raw_html="<html><body><p>Validated raw.</p></body></html>",
        polish_html="<html><body><p>Polish.</p></body></html>",
    )
    out_dir = tmp_path / "source"
    stale = out_dir / "audit_full_checks.json"
    real_validate = converted_runs_module._validated_raw_sources

    def validate_then_add_artifact(
        paths: list[Path],
    ) -> dict[Path, object]:
        result = real_validate(paths)
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text('{"raced": true}\n', encoding="utf-8")
        return result

    monkeypatch.setattr(
        converted_runs_module,
        "_validated_raw_sources",
        validate_then_add_artifact,
    )
    with pytest.raises(FileExistsError, match="already contains artifacts"):
        prepare_converted_raw_cache([root], out_dir)

    assert stale.read_text(encoding="utf-8") == '{"raced": true}\n'
    assert not (out_dir / "raw_cache").exists()
    assert not (out_dir / "profiles").exists()
    assert not (out_dir / "manifest.json").exists()


def test_prepare_converted_raw_cache_rejects_empty_input_before_creating_output(
    tmp_path: Path,
) -> None:
    root = tmp_path / "converted"
    root.mkdir()
    out_dir = tmp_path / "source"

    with pytest.raises(ValueError, match="No committed converted raw stages"):
        prepare_converted_raw_cache([root], out_dir)

    assert not out_dir.exists()

def test_converted_raw_cache_regenerates_missing_polish_but_audit_only_rejects_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw_path = stage_dir / RAW_STAGE_NAME
    raw_path.write_text(
        "<html><body><p>Raw without previous polish.</p></body></html>",
        encoding="utf-8",
    )
    _commit_current_converted_raw(stage_dir)

    manifest = prepare_converted_raw_cache([root], tmp_path / "source")

    assert manifest["raw_count"] == 1
    assert manifest["articles"][0]["source_polish_present"] is False
    assert Path(manifest["articles"][0]["raw_cache_path"]).is_file()
    with pytest.raises(RuntimeError, match="missing polish artifacts"):
        prepare_converted_run([root], tmp_path / "audit_only")


def test_prepare_converted_raw_cache_rejects_copy_that_changed_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "Doc" / "_z2m_stages"
    _write_current_converted_pair(
        stage_dir,
        raw_html="<html><body><p>Validated raw.</p></body></html>",
        polish_html="<html><body><p>Polish.</p></body></html>",
    )
    out_dir = tmp_path / "source"

    def copy_changed(_source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "<html><body><p>Different raw bytes.</p></body></html>",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "pdf_html_polish.quality_loop.converted_runs.copy_file_atomic",
        copy_changed,
    )
    with pytest.raises(RuntimeError, match="does not match its validated conversion manifest"):
        prepare_converted_raw_cache([root], out_dir)

    assert not any((out_dir / "raw_cache").glob("*.html"))
    assert not (out_dir / "manifest.json").exists()


def test_prepare_converted_raw_cache_profiles_the_validated_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "Doc" / "_z2m_stages"
    original_raw = (
        "<html><body><p>"
        "Glasauer et al. (2002), Metcalfe and Gresty (1992), "
        "Seemungal et al. (2007), Loomis et al. (2001), "
        "Klem et al. (1999), Hilgetag et al. (2001), "
        "Oliveri et al. (2000), Bestmann et al. (2002), "
        "and Brandt et al. (2002).</p></body></html>"
    )
    _write_current_converted_pair(
        stage_dir,
        raw_html=original_raw,
        polish_html="<html><body><p>Polish.</p></body></html>",
    )
    raw_path = stage_dir / RAW_STAGE_NAME
    out_dir = tmp_path / "source_snapshot"

    def copy_then_mutate(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        source.write_text("<html><body><p>No citations.</p></body></html>", encoding="utf-8")

    monkeypatch.setattr(
        "pdf_html_polish.quality_loop.converted_runs.copy_file_atomic",
        copy_then_mutate,
    )
    manifest = prepare_converted_raw_cache([root], out_dir)

    article = manifest["articles"][0]
    assert article["citation_style"] == "author_year"
    assert Path(article["raw_cache_path"]).read_text(encoding="utf-8") == original_raw
    assert raw_path.read_text(encoding="utf-8") != original_raw


def test_prepare_converted_run_preserves_duplicate_articles_as_unique_ids(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    for mtime in ("111", "222"):
        stage_dir = root / "lib" / "KEY" / mtime / "Doc" / "_z2m_stages"
        _write_current_converted_pair(
            stage_dir,
            raw_html="<html><body><p>Raw</p></body></html>",
            polish_html=(
                '<html><body><p>Polish <a href="#ref-1">[1]</a></p>'
                '<ol><li id="ref-1">Ref.</li></ol></body></html>'
            ),
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
        _write_current_converted_pair(
            stage_dir,
            raw_html=(
                f"<html><body><p>Raw {mtime}</p>"
                '<p><img src="fig1.png"/></p></body></html>'
            ),
            polish_html=(
                f'<html><body><p><img data-z2m-src="fig1.png" '
                f'src="{_valid_tiny_png_data_url()}"/></p></body></html>'
            ),
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


def test_prepare_converted_raw_cache_uses_manifest_source_over_filename_map(tmp_path: Path) -> None:
    root = tmp_path / "converted_run"
    article_dir = root / "AliasDoc"
    stage_dir = article_dir / "_pdf_html_polish_stages"
    source_pdf = tmp_path / "zotero" / "paper.pdf"
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"%PDF-1.4\n")
    alias_pdf = root / "_z2m_runtime_tmp" / "zotero_pdf_stage_abc" / "AliasDoc.pdf"
    alias_pdf.parent.mkdir(parents=True)
    alias_pdf.write_bytes(b"%PDF-1.4\n")
    _write_current_converted_pair(
        stage_dir,
        raw_html="<html><body><p>Raw</p></body></html>",
        polish_html="<html><body><p>Polish</p></body></html>",
        source_pdf=source_pdf,
    )
    (root / "_source_filename_map.csv").write_text(
        "source_pdf_path,alias_pdf_path,source_base_len,alias_base_len,was_shortened,materialization\n"
        f"{source_pdf},{alias_pdf},9,8,no,copy\n",
        encoding="utf-8",
    )

    manifest = prepare_converted_raw_cache([root], tmp_path / "source")

    article = manifest["articles"][0]
    assert article["source_pdf_path"] == str(source_pdf)
    assert article["source_pdf_origin"] == "raw_conversion_manifest"
    assert article["raw_conversion_manifest_schema_version"] == 2
    report = write_source_pdf_map_for_run(tmp_path / "source", manifest)
    assert report["mapped_count"] == 1
    assert report["records"][0]["pdf_path"] == str(source_pdf)


def test_prepare_converted_raw_cache_infers_citation_style_from_raw_html(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "lib" / "KEY" / "111" / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text(
        "<html><body><p>Body cites [1], [2], [3], [4], [5], [6], and [7].</p></body></html>",
        encoding="utf-8",
    )
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")
    _commit_current_converted_raw(stage_dir)

    manifest = prepare_converted_raw_cache([root], tmp_path / "source")

    article = manifest["articles"][0]
    profile = json.loads(Path(article["profile_path"]).read_text(encoding="utf-8"))
    assert article["profile_status"] == "converted_raw_html_inferred"
    assert article["citation_style"] == "unknown"
    assert article["citation_confidence"] == "low"
    assert profile["source"] == "converted_raw_html"
    assert profile["source_policy"] == "use_high_confidence_or_medium_author_year_inferred_style"
    assert profile["inferred_style"] == "bracket_numeric"
    assert profile["inferred_confidence"] == "medium"
    assert profile["bracket_numeric_count"] == 7
    assert manifest["profile_status_counts"] == {"converted_raw_html_inferred": 1}
    assert manifest["profile_style_counts"] == {"unknown:low": 1}


def test_prepare_converted_raw_cache_uses_medium_author_year_inference(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "lib" / "KEY" / "111" / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text(
        "<html><body><p>"
        "Glasauer et al. (2002), Metcalfe and Gresty (1992), Seemungal et al. (2007), "
        "Loomis et al. (2001), Klem et al. (1999), Hilgetag et al. (2001), "
        "Oliveri et al. (2000), Bestmann et al. (2002), and Brandt et al. (2002) "
        "define an author-year converted PDF."
        "</p></body></html>",
        encoding="utf-8",
    )
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")
    _commit_current_converted_raw(stage_dir)

    manifest = prepare_converted_raw_cache([root], tmp_path / "source")

    article = manifest["articles"][0]
    profile = json.loads(Path(article["profile_path"]).read_text(encoding="utf-8"))
    assert article["citation_style"] == "author_year"
    assert article["citation_confidence"] == "medium"
    assert profile["inferred_style"] == "author_year"
    assert profile["inferred_confidence"] == "medium"
    assert manifest["profile_style_counts"] == {"author_year:medium": 1}


def test_prepare_converted_raw_cache_ignores_bibliography_for_author_year_inference(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "lib" / "KEY" / "111" / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text(
        "<html><body>"
        "<p>Locomotion not only in humans is based on spinal pattern generators.1 "
        "Recent imaging studies showed the supraspinal network.2,3</p>"
        "<h2>References</h2><ol>"
        '<li id="ref-1">Jahn, K., A. Deutschlander, T. Stephan, et al. 2008. Example.</li>'
        '<li id="ref-2">Jahn, K., A. Deutschlander, T. Stephan, et al. 2004. Example.</li>'
        '<li id="ref-3">Wagner, J., T. Stephan, R. Kalla, et al. 2008. Example.</li>'
        '<li id="ref-4">O&apos;Keefe, J. 1976. Example.</li>'
        '<li id="ref-5">Taube, J.S. 2007. Example.</li>'
        '<li id="ref-6">Hafting, T., M. Fyhn, S. Molden, et al. 2005. Example.</li>'
        '<li id="ref-7">McNaughton, B.L., F.P. Battaglia, O. Jensen, et al. 2006. Example.</li>'
        '<li id="ref-8">Ekstrom, A.D., M.J. Kahana, J.B. Caplan, et al. 2003. Example.</li>'
        "</ol></body></html>",
        encoding="utf-8",
    )
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")
    _commit_current_converted_raw(stage_dir)

    manifest = prepare_converted_raw_cache([root], tmp_path / "source")

    article = manifest["articles"][0]
    profile = json.loads(Path(article["profile_path"]).read_text(encoding="utf-8"))
    assert article["citation_style"] == "unknown"
    assert article["citation_confidence"] == "low"
    assert profile["inferred_style"] == "unknown"
    assert profile["inferred_confidence"] == "low"


def test_prepare_converted_raw_cache_ids_do_not_shift_when_new_sources_appear(tmp_path: Path) -> None:
    root = tmp_path / "converted"
    stage_dir = root / "lib" / "KEY" / "222" / "Doc" / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")
    _commit_current_converted_raw(stage_dir)
    first = prepare_converted_raw_cache([root], tmp_path / "source1")
    original_id = first["articles"][0]["article_id"]

    earlier_stage_dir = root / "lib" / "AAA" / "111" / "Earlier" / "_z2m_stages"
    earlier_stage_dir.mkdir(parents=True)
    (earlier_stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    (earlier_stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish</p></body></html>", encoding="utf-8")
    _commit_current_converted_raw(earlier_stage_dir)

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
        _commit_current_converted_raw(stage_dir)

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


def test_observe_defers_repair_rerun_audit_until_all_repair_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / "run"
    source_dir = tmp_path / "source"
    stage_dir = run_dir / "audit_tree" / "article_a"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish.</p></body></html>", encoding="utf-8")
    audit_calls: list[dict[str, object]] = []
    repolish_calls: list[dict[str, object]] = []
    repair_calls: list[tuple[str, dict[str, object]]] = []
    finalization_calls: list[str] = []

    gate_config = {
        "repolish_jobs": 3,
        "audit_jobs": 2,
        "require_pdf_text_layer_diagnostics": False,
        "targeted_repair_audit_enabled": True,
        "run_p62_image_recovery_stage": True,
        "p62_image_recovery_execute_marker": True,
        "p62_image_recovery_apply_patches": True,
        "p62_image_recovery_rerun_audit": True,
        "run_polish_auto_repair_stage": True,
        "polish_auto_repair_rerun_audit": True,
        "article_review_bundle_max_articles": 0,
    }

    def fake_repolish(*args: object, **kwargs: object) -> dict[str, object]:
        repolish_calls.append({"args": args, "kwargs": kwargs})
        return {"raw_count": 1, "article_count": 1, "skipped_count": 0, "changed_count": 1}

    def fake_run_audit(*args: object, **kwargs: object) -> None:
        if not audit_calls:
            _write_json(run_dir / "audit_full_checks.json", {"roots": [str(run_dir / "audit_tree")], "articles": []})
        audit_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(llm_quality_loop, "load_gate_config", lambda *args, **kwargs: gate_config)
    monkeypatch.setattr(llm_quality_loop, "repolish_cached_run", fake_repolish)
    monkeypatch.setattr(llm_quality_loop, "run_audit", fake_run_audit)
    monkeypatch.setattr(llm_quality_loop, "run_quality_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        llm_quality_loop,
        "write_p62_marker_recovery_plan",
        lambda *args, **kwargs: repair_calls.append(("p62_plan", dict(kwargs))) or {},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_p62_image_recovery_stage",
        lambda *args, **kwargs: repair_calls.append(("p62_recovery", dict(kwargs)))
        or {"patched_warning_count": 3, "patched_articles": ["article_a"]},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_polish_auto_repair_stage",
        lambda *args, **kwargs: repair_calls.append(("polish_auto_repair", dict(kwargs)))
        or {"patched_article_count": 2, "patched_articles": ["article_a"]},
    )
    monkeypatch.setattr(llm_quality_loop, "write_manual_review_queue", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        llm_quality_loop,
        "write_article_review_stage",
        lambda *args, **kwargs: {"status": "not_required", "pending_mandatory_count": 0},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_pattern_observations",
        lambda *args, **kwargs: {"pattern_count": 0, "problem_candidates": []},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_manual_observation_summary",
        lambda *args, **kwargs: {"observation_count": 0, "problem_candidates": []},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_analysis_pack",
        lambda *args, **kwargs: {"resolver_decisions": {"repair_candidate_counts": {}}, "articles": []},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "_write_gate_report",
        lambda *args, **kwargs: finalization_calls.append("gate") or {"status": "pass"},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "seal_quality_publication",
        lambda *args, **kwargs: finalization_calls.append("seal")
        or {"status": "completed", "errors": []},
    )

    args = parse_args(
        [
            "observe",
            "--source-run-dir",
            str(source_dir),
            "--out-dir",
            str(run_dir),
            "--jobs",
            "5",
            "--skip-tests",
            "--skip-history",
        ]
    )

    assert llm_quality_loop.observe(args) == 0
    assert [name for name, _kwargs in repair_calls] == ["p62_plan", "p62_recovery", "polish_auto_repair"]
    assert [kwargs["jobs"] for _name, kwargs in repair_calls] == [5, 5, 5]
    assert repolish_calls[0]["kwargs"]["jobs"] == 3
    assert len(audit_calls) == 2
    assert audit_calls[0]["kwargs"]["jobs"] == 2
    assert audit_calls[1]["kwargs"]["jobs"] == 2
    assert audit_calls[0]["kwargs"].get("merge_previous_report_path") is None
    assert audit_calls[1]["kwargs"]["roots"] == [stage_dir]
    assert audit_calls[1]["kwargs"]["merge_previous_report_path"] == run_dir / "audit_full_checks.json"
    assert finalization_calls == ["gate", "seal"]


def test_observe_converted_roots_default_runs_repolish_and_repair_stages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    converted_root = tmp_path / "converted"
    stage_dir = run_dir / "audit_tree" / "article_a"
    stage_dir.mkdir(parents=True)
    (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
    (stage_dir / "02.en.polish.html").write_text("<html><body><p>Polish.</p></body></html>", encoding="utf-8")
    converted_cache_calls: list[dict[str, object]] = []
    repolish_calls: list[dict[str, object]] = []
    audit_calls: list[dict[str, object]] = []
    repair_calls: list[tuple[str, dict[str, object]]] = []

    gate_config = {
        "repolish_jobs": 3,
        "audit_jobs": 2,
        "require_pdf_text_layer_diagnostics": False,
        "targeted_repair_audit_enabled": True,
        "run_p62_image_recovery_stage": True,
        "p62_image_recovery_execute_marker": True,
        "p62_image_recovery_apply_patches": True,
        "p62_image_recovery_rerun_audit": True,
        "run_polish_auto_repair_stage": True,
        "polish_auto_repair_rerun_audit": True,
        "article_review_bundle_max_articles": 0,
    }

    def fake_prepare_converted_raw_cache(*args: object, **kwargs: object) -> dict[str, object]:
        converted_cache_calls.append({"args": args, "kwargs": kwargs})
        return {"raw_count": 1, "article_count": 1}

    def fake_repolish(*args: object, **kwargs: object) -> dict[str, object]:
        repolish_calls.append({"args": args, "kwargs": kwargs})
        return {"raw_count": 1, "article_count": 1, "skipped_count": 0, "changed_count": 1}

    def fake_run_audit(*args: object, **kwargs: object) -> None:
        if not audit_calls:
            _write_json(run_dir / "audit_full_checks.json", {"roots": [str(run_dir / "audit_tree")], "articles": []})
        audit_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(llm_quality_loop, "load_gate_config", lambda *args, **kwargs: gate_config)
    monkeypatch.setattr(llm_quality_loop, "prepare_converted_raw_cache", fake_prepare_converted_raw_cache)
    monkeypatch.setattr(llm_quality_loop, "repolish_cached_run", fake_repolish)
    monkeypatch.setattr(llm_quality_loop, "run_audit", fake_run_audit)
    monkeypatch.setattr(llm_quality_loop, "run_quality_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        llm_quality_loop,
        "write_p62_marker_recovery_plan",
        lambda *args, **kwargs: repair_calls.append(("p62_plan", dict(kwargs))) or {},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_p62_image_recovery_stage",
        lambda *args, **kwargs: repair_calls.append(("p62_recovery", dict(kwargs)))
        or {"patched_warning_count": 1, "patched_articles": ["article_a"]},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_polish_auto_repair_stage",
        lambda *args, **kwargs: repair_calls.append(("polish_auto_repair", dict(kwargs)))
        or {"patched_article_count": 1, "patched_articles": ["article_a"]},
    )
    monkeypatch.setattr(llm_quality_loop, "write_manual_review_queue", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        llm_quality_loop,
        "write_article_review_stage",
        lambda *args, **kwargs: {"status": "not_required", "pending_mandatory_count": 0},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_pattern_observations",
        lambda *args, **kwargs: {"pattern_count": 0, "problem_candidates": []},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_manual_observation_summary",
        lambda *args, **kwargs: {"observation_count": 0, "problem_candidates": []},
    )
    monkeypatch.setattr(
        llm_quality_loop,
        "write_analysis_pack",
        lambda *args, **kwargs: {"resolver_decisions": {"repair_candidate_counts": {}}, "articles": []},
    )
    monkeypatch.setattr(llm_quality_loop, "_write_gate_report", lambda *args, **kwargs: {"status": "pass"})
    monkeypatch.setattr(
        llm_quality_loop,
        "seal_quality_publication",
        lambda *args, **kwargs: {"status": "completed", "errors": []},
    )

    args = parse_args(
        [
            "observe",
            "--converted-roots",
            str(converted_root),
            "--out-dir",
            str(run_dir),
            "--skip-tests",
            "--skip-history",
        ]
    )

    assert llm_quality_loop.observe(args) == 0
    assert converted_cache_calls[0]["args"] == ([converted_root], run_dir / "_converted_raw_source")
    assert repolish_calls[0]["args"][0] == run_dir / "_converted_raw_source"
    assert repolish_calls[0]["kwargs"]["jobs"] == 3
    assert [name for name, _kwargs in repair_calls] == ["p62_plan", "p62_recovery", "polish_auto_repair"]
    assert len(audit_calls) == 2
    assert audit_calls[0]["kwargs"].get("roots") is None
    assert audit_calls[1]["kwargs"]["roots"] == [stage_dir]


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
                    "defects_found": [],
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
    _commit_cached_repolish_source(source)

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


def test_repolish_cached_run_parallel_jobs_keep_manifest_order(tmp_path: Path) -> None:
    source = tmp_path / "source"
    raw_cache = source / "raw_cache"
    profiles = source / "profiles"
    raw_cache.mkdir(parents=True)
    profiles.mkdir(parents=True)
    for article in ("alpha", "beta", "gamma"):
        (raw_cache / f"{article}.01.en.raw.html").write_text(
            "<html><body><p>This article describes methods, results, and discussion.</p></body></html>",
            encoding="utf-8",
        )
        _write_json(
            profiles / f"{article}.citation_profile.json",
            {"status": "ok", "style": "unknown", "confidence": "low"},
        )
    _commit_cached_repolish_source(source)

    manifest = repolish_cached_run(source, tmp_path / "run", jobs=3)
    assessment = json.loads((tmp_path / "run" / "assessment.json").read_text(encoding="utf-8"))

    assert manifest["jobs"] == 3
    assert manifest["article_count"] == 3
    assert [article["article"] for article in manifest["articles"]] == ["alpha", "beta", "gamma"]
    assert [article["article"] for article in assessment["articles"]] == ["alpha", "beta", "gamma"]


def test_repolish_cached_run_rejects_uncommitted_source_before_output_mutation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    (raw_dir / "doc.01.en.raw.html").write_text(
        "<html><body><p>Uncommitted source.</p></body></html>",
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"

    with pytest.raises(CachedRunSourceError, match="manifest_missing_empty_symlink_or_unstable"):
        repolish_cached_run(source, out_dir)

    assert not out_dir.exists()


def test_repolish_cached_run_publishes_and_uses_internal_source_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    source_raw = raw_dir / "doc.01.en.raw.html"
    source_raw.write_text(
        "<html><body><p>Committed source snapshot.</p></body></html>",
        encoding="utf-8",
    )
    _commit_cached_repolish_source(source)
    out_dir = tmp_path / "run"

    manifest = repolish_cached_run(source, out_dir)

    snapshot_dir = Path(manifest["source_run_dir"])
    assert snapshot_dir == (out_dir / CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR).resolve()
    assert manifest["source_origin_run_dir"] == str(source.resolve())
    source_validation = validate_cached_repolish_source(snapshot_dir)
    assert manifest["source_manifest_sha256"] == source_validation.manifest_fingerprint.sha256
    assert source_validation.manifest["source_snapshot_origin"]["run_dir"] == str(source.resolve())
    assert (out_dir / "raw_cache" / source_raw.name).read_bytes() == source_raw.read_bytes()


def test_repolish_cached_run_uses_staged_bytes_when_origin_changes_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    source_raw = raw_dir / "doc.01.en.raw.html"
    original_html = "<html><body><p>Original committed bytes.</p></body></html>"
    source_raw.write_text(original_html, encoding="utf-8")
    _commit_cached_repolish_source(source)
    real_stage = llm_quality_loop.stage_cached_repolish_source_snapshot

    def stage_then_mutate(
        source_run_dir: Path,
        staging_dir: Path,
        published_dir: Path,
    ) -> dict[str, object]:
        result = real_stage(source_run_dir, staging_dir, published_dir)
        source_raw.write_text(
            "<html><body><p>Origin changed after staging.</p></body></html>",
            encoding="utf-8",
        )
        return result

    monkeypatch.setattr(
        llm_quality_loop,
        "stage_cached_repolish_source_snapshot",
        stage_then_mutate,
    )
    out_dir = tmp_path / "run"

    repolish_cached_run(source, out_dir)

    assert (out_dir / "raw_cache" / source_raw.name).read_text(encoding="utf-8") == original_html
    assert "Original committed bytes" in (out_dir / "polish" / "doc.02.en.polish.html").read_text(
        encoding="utf-8"
    )


def test_repolish_cached_run_rejects_tampered_persistent_snapshot_before_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    (raw_dir / "doc.01.en.raw.html").write_text(
        "<html><body><p>Committed bytes.</p></body></html>",
        encoding="utf-8",
    )
    _commit_cached_repolish_source(source)
    real_validate = llm_quality_loop.validate_cached_repolish_source

    def tamper_then_validate(snapshot_dir: Path):
        snapshot_raw = next((snapshot_dir / "raw_cache").glob("*.html"))
        snapshot_raw.write_text(
            "<html><body><p>Tampered snapshot.</p></body></html>",
            encoding="utf-8",
        )
        return real_validate(snapshot_dir)

    monkeypatch.setattr(llm_quality_loop, "validate_cached_repolish_source", tamper_then_validate)
    out_dir = tmp_path / "run"

    with pytest.raises(CachedRunSourceError, match="raw_fingerprint_mismatch:doc"):
        repolish_cached_run(source, out_dir)

    assert not (out_dir / CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR).exists()
    assert not (out_dir / "raw_cache").exists()
    assert not (out_dir / "manifest.json").exists()


def test_repolish_cached_run_rejects_snapshot_mutation_during_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    (raw_dir / "doc.01.en.raw.html").write_text(
        "<html><body><p>Committed bytes.</p></body></html>",
        encoding="utf-8",
    )
    _commit_cached_repolish_source(source)
    out_dir = tmp_path / "run"
    real_polish = llm_quality_loop.polish_html_document
    mutated = False

    def polish_then_mutate(*args: object, **kwargs: object) -> str:
        nonlocal mutated
        polished = real_polish(*args, **kwargs)
        if not mutated:
            snapshot_raw = out_dir / CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR / "raw_cache" / "doc.01.en.raw.html"
            snapshot_raw.write_text(
                "<html><body><p>Changed after worker read.</p></body></html>",
                encoding="utf-8",
            )
            mutated = True
        return polished

    monkeypatch.setattr(llm_quality_loop, "polish_html_document", polish_then_mutate)

    with pytest.raises(CachedRunSourceError, match="raw_fingerprint_mismatch:doc"):
        repolish_cached_run(source, out_dir)

    assert not (out_dir / "manifest.json").exists()
    assert not (out_dir / "assessment.json").exists()


def test_repolish_cached_run_refuses_existing_owned_output_without_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    (raw_dir / "doc.01.en.raw.html").write_text(
        "<html><body><p>Committed bytes.</p></body></html>",
        encoding="utf-8",
    )
    _commit_cached_repolish_source(source)
    out_dir = tmp_path / "run"
    sentinel = out_dir / "raw_cache" / "keep.txt"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already contains owned artifacts"):
        repolish_cached_run(source, out_dir)

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (out_dir / CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR).exists()


def test_repolish_cached_run_refuses_unrelated_existing_output_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    (raw_dir / "doc.01.en.raw.html").write_text(
        "<html><body><p>Committed bytes.</p></body></html>",
        encoding="utf-8",
    )
    _commit_cached_repolish_source(source)
    out_dir = tmp_path / "run"
    stale_audit = out_dir / "audit_full_checks.json"
    stale_audit.parent.mkdir(parents=True)
    stale_audit.write_text('{"stale": true}\n', encoding="utf-8")

    with pytest.raises(FileExistsError, match="unrelated artifacts"):
        repolish_cached_run(source, out_dir)

    assert stale_audit.read_text(encoding="utf-8") == '{"stale": true}\n'
    assert not (out_dir / CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR).exists()
    assert not (out_dir / "raw_cache").exists()


def test_repolish_cached_run_allows_only_internal_committed_source_entry(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "run"
    source = out_dir / "_converted_raw_source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    (raw_dir / "doc.01.en.raw.html").write_text(
        "<html><body><p>Committed internal source.</p></body></html>",
        encoding="utf-8",
    )
    _commit_cached_repolish_source(source)

    manifest = repolish_cached_run(source, out_dir)

    assert manifest["article_count"] == 1
    assert source.is_dir()
    assert (out_dir / CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR / "manifest.json").is_file()


def test_repolish_cached_run_rechecks_unrelated_output_after_source_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    raw_dir = source / "raw_cache"
    raw_dir.mkdir(parents=True)
    (raw_dir / "doc.01.en.raw.html").write_text(
        "<html><body><p>Committed bytes.</p></body></html>",
        encoding="utf-8",
    )
    _commit_cached_repolish_source(source)
    out_dir = tmp_path / "run"
    real_stage = llm_quality_loop.stage_cached_repolish_source_snapshot

    def stage_then_add_unrelated(
        source_run_dir: Path,
        staging_dir: Path,
        published_dir: Path,
    ) -> dict[str, object]:
        result = real_stage(source_run_dir, staging_dir, published_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "stale-gate.json").write_text('{"stale": true}\n', encoding="utf-8")
        return result

    monkeypatch.setattr(
        llm_quality_loop,
        "stage_cached_repolish_source_snapshot",
        stage_then_add_unrelated,
    )

    with pytest.raises(FileExistsError, match="gained unrelated artifacts"):
        repolish_cached_run(source, out_dir)

    assert (out_dir / "stale-gate.json").is_file()
    assert not (out_dir / CACHED_REPOLISH_SOURCE_SNAPSHOT_DIR).exists()


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
    _commit_cached_repolish_source(
        source,
        article_metadata={"spotnitz": {"source_pdf_path": str(pdf_path)}},
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
    _commit_cached_repolish_source(
        source,
        article_metadata={"bodycite": {"source_pdf_path": str(pdf_path)}},
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
    valid_image = _valid_tiny_png_data_url()
    ancestor_polish.write_text(
        "<html><body>"
        f'<p><img data-z2m-src="fig1.png" src="{valid_image}"/></p>'
        f'<p><img data-z2m-src="fig2.png" src="{valid_image}"/></p>'
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
    _commit_cached_repolish_source(source, source_run_dir=chain)

    manifest = repolish_cached_run(source, tmp_path / "run")
    polished = (tmp_path / "run" / "polish" / "doc.02.en.polish.html").read_text(encoding="utf-8")
    audit_polished = (tmp_path / "run" / "audit_tree" / "doc" / "02.en.polish.html").read_text(encoding="utf-8")

    assert manifest["restored_image_count"] == 2
    assert f'data-z2m-src="fig1.png" src="{valid_image}"' in polished
    assert f'data-z2m-src="fig2.png" src="{valid_image}"' in polished
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
    _commit_cached_repolish_source(source, source_run_dir=chain)

    manifest = repolish_cached_run(source, tmp_path / "run")
    polished = (tmp_path / "run" / "polish" / "doc.02.en.polish.html").read_text(encoding="utf-8")

    assert manifest["restored_image_count"] == 1
    assert 'data-z2m-src="fig1.png" src="data:image/png;base64,' in polished
    assert '<img src="fig1.png"' not in polished
