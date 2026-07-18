from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import write_attested_audit_command

from pdf_html_polish.quality_loop.commands import run_quality_history, write_gate_report
from pdf_html_polish.quality_loop.gate_provenance import GateProvenanceError


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_gate_config(path: Path, **overrides: object) -> None:
    config: dict[str, object] = {
        "allow_missing_previous": True,
        "max_regressions": 0,
        "max_total_deltas": {},
    }
    config.update(overrides)
    _write_json(path, config)


def test_gate_rejects_quality_compare_not_derived_from_current_and_previous_entries(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    previous_path = tmp_path / "previous_entry.json"
    config_path = tmp_path / "gate.json"
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {"defect_counts": {"P99": 1}},
            "articles": [
                {
                    "article": "paper",
                    "summary": {},
                    "defects_found": [{"id": "P99", "severity": "error"}],
                }
            ],
        },
    )
    write_attested_audit_command(run_dir)
    _write_json(
        previous_path,
        {
            "run_id": "previous",
            "totals": {
                "score": 0.0,
                "defects": 0,
                "errors": 0,
                "warnings": 0,
                "infos": 0,
            },
            "articles": {
                "paper": {
                    "score": 0.0,
                    "defects": 0,
                    "errors": 0,
                    "warnings": 0,
                    "infos": 0,
                    "metrics": {},
                }
            },
        },
    )
    run_quality_history(
        run_dir,
        run_id="current",
        previous_entry=previous_path,
        no_append=True,
        repo_root=REPO_ROOT,
    )
    comparison = json.loads((run_dir / "quality_compare.json").read_text(encoding="utf-8"))
    assert comparison["regressions"]
    _write_json(
        run_dir / "quality_compare.json",
        {
            "generated_at": comparison["generated_at"],
            "previous_run_id": "previous",
            "current_run_id": "current",
            "status": "ok",
            "totals_delta": {},
            "comparable_totals_delta": {},
            "new_articles": [],
            "removed_articles": [],
            "new_article_count": 0,
            "removed_article_count": 0,
            "regressions": [],
            "improvements": [],
            "unchanged": [],
        },
    )
    _write_gate_config(config_path)

    with pytest.raises(GateProvenanceError):
        write_gate_report(run_dir, config_path)


def test_gate_rejects_article_review_report_that_hides_pending_mandatory_item(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "gate.json"
    _write_json(
        run_dir / "manual_review_queue.json",
        [
            {
                "article": "paper",
                "mandatory_review": True,
                "review_status": "pending",
                "polish_stage_path": str(run_dir / "audit_tree" / "paper" / "02.en.polish.html"),
            }
        ],
    )
    _write_json(
        run_dir / "article_review_report.json",
        {
            "status": "ready",
            "queue_count": 1,
            "mandatory_count": 1,
            "pending_mandatory_count": 0,
            "selected_count": 1,
        },
    )
    _write_gate_config(
        config_path,
        require_article_review_stage=True,
        max_pending_mandatory_reviews=0,
    )

    with pytest.raises(GateProvenanceError):
        write_gate_report(run_dir, config_path)


def test_gate_rejects_pdf_evidence_ready_without_source_or_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "gate.json"
    _write_json(
        run_dir / "pdf_problem_evidence_report.json",
        {
            "status": "ready",
            "selected_count": 1,
            "ready_count": 1,
            "source_pdf_unavailable_count": 0,
            "blocking_issue_count": 0,
            "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
            "articles": [
                {
                    "article": "paper",
                    "status": "ready",
                    "source_pdf_available": True,
                    "source_pdf_path": str(run_dir / "missing.pdf"),
                    "text_layer_chars": 100,
                    "text_layer_excerpt_path": str(run_dir / "missing.txt"),
                    "page_render_status": "rendered",
                    "page_render_path": str(run_dir / "missing.png"),
                }
            ],
        },
    )
    _write_gate_config(config_path, require_pdf_problem_evidence_stage=True)

    with pytest.raises(GateProvenanceError):
        write_gate_report(run_dir, config_path)


def test_gate_does_not_trust_audit_command_pdf_diagnostics_claim(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "gate.json"
    _write_json(
        run_dir / "audit_full_checks.json",
        {
            "corpus_summary": {"totals": {"source_pdf_present": 1, "pdf_text_chars": 100}},
            "articles": [
                {
                    "article": "paper",
                    "summary": {"pdf_diagnostics_enabled": False},
                }
            ],
        },
    )
    write_attested_audit_command(run_dir, enable_pdf_diagnostics=True)
    _write_gate_config(config_path, require_pdf_text_layer_diagnostics=True)

    with pytest.raises(
        GateProvenanceError,
        match="audit_report_pdf_diagnostics_flag_mismatch:paper",
    ):
        write_gate_report(run_dir, config_path)
