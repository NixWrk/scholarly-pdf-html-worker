from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from pdf_html_polish.artifact_integrity import fingerprint_file
from pdf_html_polish.quality_loop.audit_command_provenance import (
    build_audit_code_manifest,
    build_audit_command_report,
)
from pdf_html_polish.quality_loop.commands import run_quality_history, write_gate_report
import pdf_html_polish.quality_loop.gate_provenance as gate_provenance
from pdf_html_polish.quality_loop.gate_provenance import (
    GATE_CONFIG_SNAPSHOT_NAME,
    GateProvenanceError,
    build_provenanced_gate_report,
    prepare_gate_config_snapshot,
    validate_gate_report_provenance,
)
from pdf_html_polish.quality_loop.pdf_evidence import (
    write_pdf_problem_evidence_stage,
)
from pdf_html_polish.quality_loop.review_workflow import write_article_review_stage


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_attested_audit(
    run_dir: Path,
    *,
    enable_pdf_diagnostics: bool = False,
    include_article: bool = False,
) -> dict:
    audit_root = (run_dir / "audit_tree").resolve(strict=False)
    audit_root.mkdir(parents=True, exist_ok=True)
    articles: list[dict] = []
    if include_article:
        stage_dir = audit_root / "paper" / "_z2m_stages"
        stage_dir.mkdir(parents=True, exist_ok=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text("<html><body><p>Polish.</p></body></html>", encoding="utf-8")
        raw_fingerprint = fingerprint_file(raw_path, reject_symlink=True)
        polish_fingerprint = fingerprint_file(polish_path, reject_symlink=True)
        assert raw_fingerprint is not None and polish_fingerprint is not None
        articles.append(
            {
                "article": "paper",
                "raw_stage_path": str(raw_path.resolve(strict=False)),
                "polish_stage_path": str(polish_path.resolve(strict=False)),
                "raw_stage_bytes": raw_fingerprint.size,
                "raw_stage_sha256": raw_fingerprint.sha256,
                "polish_stage_bytes": polish_fingerprint.size,
                "polish_stage_sha256": polish_fingerprint.sha256,
                "summary": {
                    "pdf_diagnostics_enabled": enable_pdf_diagnostics,
                    "source_pdf_path": str(
                        (stage_dir / "00.source.pdf").resolve(strict=False)
                    ),
                    "source_pdf_present": False,
                    "source_pdf_bytes": 0,
                    "source_pdf_sha256": "",
                    "source_pdf_origin": "stage",
                    "pdf_text_status": "missing" if enable_pdf_diagnostics else "disabled",
                    "pdf_text_chars": 0,
                },
                "defects_found": [],
            }
        )
    audit = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "stage": "01.en.raw.html -> 02.en.polish.html",
        "roots": [str(audit_root)],
        "audit_status": "complete",
        "processed_pair_count": len(articles),
        "total_pair_count": len(articles),
        "article_count": len(articles),
        "corpus_summary": {
            "defect_counts": {},
            "observed_defect_counts": {},
            "non_quality_defect_counts": {},
            "totals": {
                "source_pdf_present": 0,
                "pdf_text_chars": 0,
            },
        },
        "articles": articles,
    }
    _write_json(run_dir / "audit_full_checks.json", audit)
    (run_dir / "audit_stdout.log").write_text("", encoding="utf-8")
    (run_dir / "audit_stderr.log").write_text("", encoding="utf-8")
    command_report = build_audit_command_report(
        run_dir,
        repo_root=_REPO_ROOT,
        roots=[audit_root],
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_input=None,
        pdf_diagnostics_cache_dir=None,
        jobs=1,
        merge_previous_report_input=None,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        returncode=0,
        code_manifest=build_audit_code_manifest(_REPO_ROOT),
    )
    _write_json(run_dir / "audit_command_report.json", command_report)
    return audit


def _configured_run(tmp_path: Path) -> tuple[Path, Path, dict]:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "gate.json"
    write_article_review_stage(
        run_dir,
        [],
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=lambda _source, _target: {},
    )
    _write_attested_audit(run_dir, enable_pdf_diagnostics=True, include_article=True)
    write_pdf_problem_evidence_stage(
        run_dir,
        {"articles": []},
        gate_config={},
        pdf_text_pages=lambda *_args, **_kwargs: ("not_called", [], None),
        render_pdf_evidence_page=lambda *_args, **_kwargs: {"status": "not_called"},
    )
    run_quality_history(
        run_dir,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    _write_json(
        config_path,
        {
            "allow_missing_previous": True,
            "max_regressions": 0,
            "max_total_deltas": {},
            "require_article_review_stage": True,
            "max_pending_mandatory_reviews": 0,
            "require_pdf_text_layer_diagnostics": True,
            "require_pdf_problem_evidence_stage": True,
        },
    )
    report = write_gate_report(run_dir, config_path)
    assert report["status"] == "pass"
    return run_dir, config_path, report


@pytest.mark.parametrize(
    "generated_at",
    [
        "2026-01-01",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00Z",
        "2026-01-01 00:00:00+00:00",
        "2026-01-01T03:00:00+03:00",
    ],
)
def test_gate_report_rejects_noncanonical_utc_generated_at(
    tmp_path: Path,
    generated_at: str,
) -> None:
    run_dir, _config_path, report = _configured_run(tmp_path)
    report["generated_at"] = generated_at

    with pytest.raises(GateProvenanceError, match="gate_report_generated_at_invalid"):
        validate_gate_report_provenance(run_dir, report)


@pytest.mark.parametrize(
    ("filename", "input_name", "reason"),
    [
        (
            "article_review_report.json",
            "article_review",
            "article_review_generated_at_invalid",
        ),
        (
            "quality_history_entry.json",
            "quality_history_entry",
            "quality_history_generated_at_invalid",
        ),
        (
            "quality_compare.json",
            "quality_compare",
            "quality_compare_generated_at_invalid",
        ),
        (
            "pdf_problem_evidence_report.json",
            "pdf_problem_evidence",
            "pdf_evidence_generated_at_invalid",
        ),
    ],
)
def test_gate_rejects_noncanonical_upstream_generated_at_with_fresh_fingerprint(
    tmp_path: Path,
    filename: str,
    input_name: str,
    reason: str,
) -> None:
    run_dir, _config_path, report = _configured_run(tmp_path)
    path = run_dir / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["generated_at"] = "2026-01-01T00:00:00Z"
    _write_json(path, payload)
    fingerprint = fingerprint_file(path, reject_symlink=True)
    assert fingerprint is not None
    input_record = next(
        record
        for record in report["input_contract"]["inputs"]
        if record["name"] == input_name
    )
    input_record["bytes"] = fingerprint.size
    input_record["sha256"] = fingerprint.sha256

    with pytest.raises(GateProvenanceError, match=reason):
        validate_gate_report_provenance(run_dir, report)


def test_quality_history_producer_and_replay_force_same_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[dict[str, str] | None] = []
    real_run = subprocess.run

    def capturing_run(*args, **kwargs):
        environment = kwargs.get("env")
        observed.append(dict(environment) if isinstance(environment, dict) else None)
        return real_run(*args, **kwargs)

    monkeypatch.setenv("PYTHONHASHSEED", "random")
    monkeypatch.setenv("PYTHONIOENCODING", "cp1251")
    monkeypatch.setattr(subprocess, "run", capturing_run)

    _configured_run(tmp_path)

    expected = {
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
    }
    assert len(observed) >= 3
    assert all(environment is not None for environment in observed)
    assert all(
        {name: environment[name] for name in expected} == expected
        for environment in observed
        if environment is not None
    )


def test_gate_rejects_coherently_forged_minimal_audit_command_report(
    tmp_path: Path,
) -> None:
    run_dir, _config_path, _report = _configured_run(tmp_path)
    _write_json(
        run_dir / "audit_command_report.json",
        {
            "returncode": 0,
            "pdf_diagnostics_enabled": True,
            "pdf_map_path": "source_pdf_map.json",
            "command": ["forged-audit"],
        },
    )

    with pytest.raises(GateProvenanceError, match="audit_command_report_schema_invalid"):
        build_provenanced_gate_report(run_dir)


def test_gate_config_snapshot_preserves_start_of_run_authority(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source = tmp_path / "gate.json"
    _write_json(source, {"allow_missing_previous": True, "max_regressions": 0})
    snapshot = prepare_gate_config_snapshot(run_dir, source)
    _write_json(source, {"allow_missing_previous": False, "max_regressions": 99})

    report = write_gate_report(run_dir, snapshot.path)

    assert report["status"] == "pass"
    assert snapshot.config == {"allow_missing_previous": True, "max_regressions": 0}


def test_gate_config_snapshot_rejects_different_source_on_same_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source = tmp_path / "gate.json"
    _write_json(source, {"allow_missing_previous": True})
    prepare_gate_config_snapshot(run_dir, source)
    _write_json(source, {"allow_missing_previous": False})

    with pytest.raises(GateProvenanceError, match="gate_config_snapshot_conflict"):
        prepare_gate_config_snapshot(run_dir, source)


def test_gate_config_snapshot_does_not_overwrite_unknown_existing_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source = tmp_path / "gate.json"
    target = run_dir / GATE_CONFIG_SNAPSHOT_NAME
    _write_json(source, {"allow_missing_previous": True})
    _write_json(target, {"untrusted": True})

    with pytest.raises(GateProvenanceError, match="gate_config_snapshot_fields_invalid"):
        prepare_gate_config_snapshot(run_dir, source)

    assert json.loads(target.read_text(encoding="utf-8")) == {"untrusted": True}


@pytest.mark.parametrize(
    "text",
    [
        '{"max_regressions":0,"max_regressions":1}\n',
        '{"max_regressions":NaN}\n',
        '[]\n',
    ],
    ids=["duplicate-key", "nonfinite-number", "not-object"],
)
def test_gate_config_snapshot_rejects_ambiguous_source_json(tmp_path: Path, text: str) -> None:
    source = tmp_path / "gate.json"
    source.write_text(text, encoding="utf-8")

    with pytest.raises(GateProvenanceError):
        prepare_gate_config_snapshot(tmp_path / "run", source)


def test_gate_config_snapshot_rejects_symlink_source(tmp_path: Path) -> None:
    source = tmp_path / "gate.json"
    link = tmp_path / "gate-link.json"
    _write_json(source, {"allow_missing_previous": True})
    try:
        link.symlink_to(source)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(GateProvenanceError, match="gate_config_source_link_like_path"):
        prepare_gate_config_snapshot(tmp_path / "run", link)


def test_gate_input_reader_rejects_different_open_handle_with_same_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "gate.json"
    impostor = tmp_path / "impostor.json"
    source.write_text('{"a":1}\n', encoding="utf-8")
    impostor.write_text('{"b":2}\n', encoding="utf-8")
    source_stat = source.stat()
    os.utime(impostor, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
    real_open = gate_provenance._open_gate_input

    def open_impostor(path: Path):
        return impostor.open("rb") if path == source.resolve(strict=False) else real_open(path)

    monkeypatch.setattr(gate_provenance, "_open_gate_input", open_impostor)

    with pytest.raises(GateProvenanceError, match="gate_config_source_changed_during_read"):
        prepare_gate_config_snapshot(tmp_path / "run", source)


def test_gate_report_records_absent_input_and_rejects_late_appearance(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    config = tmp_path / "gate.json"
    _write_json(config, {"allow_missing_previous": True})
    report = write_gate_report(run_dir, config)
    comparison_record = next(
        record for record in report["input_contract"]["inputs"] if record["name"] == "quality_compare"
    )
    assert comparison_record["present"] is False
    _write_json(run_dir / "quality_compare.json", {"status": "ok"})

    with pytest.raises(GateProvenanceError, match="gate_input_fingerprint_mismatch:quality_compare"):
        validate_gate_report_provenance(run_dir, report)


@pytest.mark.parametrize(
    "filename",
    ["quality_history_entry.json", "quality_previous_entry_snapshot.json"],
)
def test_gate_rejects_partial_history_inputs_without_comparison(
    tmp_path: Path,
    filename: str,
) -> None:
    run_dir = tmp_path / "run"
    config = tmp_path / "gate.json"
    _write_json(config, {"allow_missing_previous": True})
    _write_json(run_dir / filename, {"stale": True})

    with pytest.raises(GateProvenanceError, match="quality_history_partial_inputs"):
        write_gate_report(run_dir, config)


def test_gate_report_rejects_present_input_removed_after_evaluation(tmp_path: Path) -> None:
    run_dir, _config_path, report = _configured_run(tmp_path)
    (run_dir / "article_review_report.json").unlink()

    with pytest.raises(GateProvenanceError, match="gate_input_fingerprint_mismatch:article_review"):
        validate_gate_report_provenance(run_dir, report)


def test_gate_report_recomputes_instead_of_trusting_forged_pass(tmp_path: Path) -> None:
    run_dir, _config_path, report = _configured_run(tmp_path)
    comparison_path = run_dir / "quality_compare.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["regressions"] = [{"article": "forged"}]
    _write_json(comparison_path, comparison)
    comparison_fingerprint = fingerprint_file(comparison_path, reject_symlink=True)
    assert comparison_fingerprint is not None
    forged = deepcopy(report)
    comparison_record = next(
        record for record in forged["input_contract"]["inputs"] if record["name"] == "quality_compare"
    )
    comparison_record["bytes"] = comparison_fingerprint.size
    comparison_record["sha256"] = comparison_fingerprint.sha256

    with pytest.raises(GateProvenanceError, match="quality_compare_recompute_mismatch"):
        validate_gate_report_provenance(run_dir, forged)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "path-alias", "extra-field"])
def test_gate_report_requires_exact_input_contract(tmp_path: Path, mutation: str) -> None:
    run_dir, _config_path, report = _configured_run(tmp_path)
    malformed = deepcopy(report)
    records = malformed["input_contract"]["inputs"]
    if mutation == "missing":
        records.pop()
    elif mutation == "duplicate":
        records[-1] = deepcopy(records[0])
    elif mutation == "path-alias":
        comparison = next(record for record in records if record["name"] == "quality_compare")
        comparison["path"] = str(run_dir / "unused" / ".." / "quality_compare.json")
    else:
        records[0]["unexpected"] = True

    with pytest.raises(GateProvenanceError):
        validate_gate_report_provenance(run_dir, malformed)


def test_gate_config_snapshot_records_exact_source_fingerprint(tmp_path: Path) -> None:
    source = tmp_path / "gate.json"
    source_bytes = b'{"max_regressions": 0}\n'
    source.write_bytes(source_bytes)

    snapshot = prepare_gate_config_snapshot(tmp_path / "run", source)

    assert snapshot.source_record == {
        "path": str(source.resolve(strict=False)),
        "bytes": len(source_bytes),
        "sha256": hashlib.sha256(source_bytes).hexdigest(),
    }
    assert build_provenanced_gate_report(tmp_path / "run")["input_contract"]["inputs"][0][
        "sha256"
    ] == snapshot.fingerprint.sha256


def test_article_review_copy_error_is_a_provenanced_gate_failure(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source = tmp_path / "paper.html"
    source.write_text("<html><body>paper</body></html>", encoding="utf-8")
    write_article_review_stage(
        run_dir,
        [
            {
                "article": "paper",
                "mandatory_review": True,
                "review_status": "pending",
                "polish_stage_path": str(source),
            }
        ],
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=lambda _source, _target: (_ for _ in ()).throw(
            RuntimeError("copy failed")
        ),
    )
    _write_attested_audit(run_dir)
    run_quality_history(
        run_dir,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    config_path = tmp_path / "gate.json"
    _write_json(
        config_path,
        {
            "allow_missing_previous": True,
            "require_article_review_stage": True,
            "max_pending_mandatory_reviews": 0,
        },
    )

    report = write_gate_report(run_dir, config_path)

    assert report["status"] == "fail"
    assert {failure["kind"] for failure in report["failures"]} == {
        "article_review_stage",
        "mandatory_review_pending",
    }


def test_article_review_missing_source_path_is_a_provenanced_gate_failure(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    stage_report = write_article_review_stage(
        run_dir,
        [
            {
                "article": "paper",
                "mandatory_review": True,
                "review_status": "pending",
            }
        ],
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=lambda _source, _target: {},
    )
    assert stage_report["status"] == "error"
    assert stage_report["copy_errors"] == [
        {
            "article": "paper",
            "polish_stage_path": "",
            "error": "polish stage file is missing",
        }
    ]
    _write_attested_audit(run_dir)
    run_quality_history(
        run_dir,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    config_path = tmp_path / "gate.json"
    _write_json(
        config_path,
        {
            "allow_missing_previous": True,
            "require_article_review_stage": True,
            "max_pending_mandatory_reviews": 0,
        },
    )

    report = write_gate_report(run_dir, config_path)

    assert report["status"] == "fail"
    assert {failure["kind"] for failure in report["failures"]} == {
        "article_review_stage",
        "mandatory_review_pending",
    }


def _artifact_configured_run(
    tmp_path: Path,
    *,
    pdf_pages: list[str] | None = None,
    source_pdf_exists: bool = True,
    expected_gate_status: str = "pass",
) -> tuple[Path, dict, dict[str, Path]]:
    run_dir = tmp_path / "run"
    review_source = tmp_path / "paper.html"
    review_source.write_text("<html><body>paper</body></html>", encoding="utf-8")

    def copy_review(source: Path, target: Path) -> dict:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return {
            "review_html": str(target),
            "inlined_image_count": 0,
            "missing_image_count": 0,
            "missing_image_srcs": [],
        }

    write_article_review_stage(
        run_dir,
        [
            {
                "article": "paper",
                "mandatory_review": True,
                "review_status": "reviewed",
                "polish_stage_path": str(review_source),
            }
        ],
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=copy_review,
    )
    _write_attested_audit(run_dir)
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    def render(_pdf: Path, _page: int, target: Path, *, zoom: float) -> dict:
        assert zoom == 1.5
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png")
        return {"status": "rendered", "path": str(target), "error": ""}

    pdf_report = write_pdf_problem_evidence_stage(
        run_dir,
        {
            "articles": [
                {
                    "article": "paper",
                    "source_pdf_candidates": [
                        {
                            "exists": source_pdf_exists,
                            "path": str(source_pdf),
                            "source": "test",
                        }
                    ],
                    "defects": [{"snippet": "target text"}],
                }
            ]
        },
        gate_config={},
        pdf_text_pages=lambda *_args, **_kwargs: ("ok", pdf_pages or ["target text"], None),
        render_pdf_evidence_page=render,
    )
    run_quality_history(
        run_dir,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    config_path = tmp_path / "gate.json"
    _write_json(
        config_path,
        {
            "allow_missing_previous": True,
            "require_article_review_stage": True,
            "max_pending_mandatory_reviews": 0,
            "require_pdf_problem_evidence_stage": True,
        },
    )
    gate_report = write_gate_report(run_dir, config_path)
    assert gate_report["status"] == expected_gate_status
    review_report = json.loads(
        (run_dir / "article_review_report.json").read_text(encoding="utf-8")
    )
    paths = {
        "queue": run_dir / "manual_review_queue.json",
        "review_source": review_source,
        "review_html": Path(review_report["articles"][0]["review_html"]),
        "review_index": Path(review_report["index_html"]),
        "review_dir": Path(review_report["review_dir"]),
        "pdf_origin": source_pdf,
        "pdf_selection": run_dir / "pdf_problem_evidence_inputs.json",
        "pdf_snapshot": Path(
            pdf_report["articles"][0]["source_pdf_path"] or run_dir / "missing.pdf"
        ),
        "pdf_excerpt": Path(
            pdf_report["articles"][0]["text_layer_excerpt_path"] or run_dir / "missing.txt"
        ),
        "pdf_render": Path(
            pdf_report["articles"][0]["page_render_path"] or run_dir / "missing.png"
        ),
        "pdf_dir": Path(pdf_report["evidence_dir"]),
        "gate_config": run_dir / GATE_CONFIG_SNAPSHOT_NAME,
    }
    return run_dir, gate_report, paths


@pytest.mark.parametrize(
    "artifact",
    ["queue", "review_source", "review_html", "review_index", "review_extra"],
)
def test_gate_rejects_mutated_or_extra_article_review_artifacts(
    tmp_path: Path,
    artifact: str,
) -> None:
    run_dir, gate_report, paths = _artifact_configured_run(tmp_path)
    if artifact == "review_extra":
        (paths["review_dir"] / "stale.txt").write_text("stale", encoding="utf-8")
    else:
        paths[artifact].write_bytes(paths[artifact].read_bytes() + b"tampered")

    with pytest.raises(GateProvenanceError):
        validate_gate_report_provenance(run_dir, gate_report)


@pytest.mark.parametrize(
    "artifact",
    ["pdf_selection", "pdf_snapshot", "pdf_excerpt", "pdf_render", "pdf_extra"],
)
def test_gate_rejects_mutated_or_extra_pdf_evidence_artifacts(
    tmp_path: Path,
    artifact: str,
) -> None:
    run_dir, gate_report, paths = _artifact_configured_run(tmp_path)
    if artifact == "pdf_extra":
        (paths["pdf_dir"] / "stale.txt").write_text("stale", encoding="utf-8")
    else:
        paths[artifact].write_bytes(paths[artifact].read_bytes() + b"tampered")

    with pytest.raises(GateProvenanceError):
        validate_gate_report_provenance(run_dir, gate_report)


def test_pdf_origin_mutation_after_snapshot_does_not_change_gate_authority(
    tmp_path: Path,
) -> None:
    run_dir, gate_report, paths = _artifact_configured_run(tmp_path)
    snapshot_before = paths["pdf_snapshot"].read_bytes()
    paths["pdf_origin"].write_bytes(b"changed outside the run")

    validation = validate_gate_report_provenance(run_dir, gate_report)

    assert validation.input_records
    assert paths["pdf_snapshot"].read_bytes() == snapshot_before


def test_empty_pdf_text_layer_is_a_provenanced_incomplete_gate_failure(
    tmp_path: Path,
) -> None:
    run_dir, gate_report, _paths = _artifact_configured_run(
        tmp_path,
        pdf_pages=[""],
        expected_gate_status="fail",
    )

    assert {failure["kind"] for failure in gate_report["failures"]} == {
        "pdf_problem_evidence_stage"
    }
    evidence = json.loads(
        (run_dir / "pdf_problem_evidence_report.json").read_text(encoding="utf-8")
    )
    assert evidence["status"] == "incomplete"
    assert evidence["articles"][0]["text_layer_chars"] == 0


def test_gate_rejects_contradictory_unavailable_pdf_evidence(tmp_path: Path) -> None:
    run_dir, _gate_report, paths = _artifact_configured_run(
        tmp_path,
        source_pdf_exists=False,
    )
    report_path = run_dir / "pdf_problem_evidence_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["articles"][0]["source_pdf_source"] = "forged"
    report["articles"][0]["text_layer_chars"] = 999
    _write_json(report_path, report)

    with pytest.raises(
        GateProvenanceError,
        match="pdf_evidence_unavailable_state_mismatch:paper",
    ):
        write_gate_report(run_dir, paths["gate_config"])


def test_gate_rejects_pdf_not_required_status_with_selected_evidence(tmp_path: Path) -> None:
    run_dir, _gate_report, paths = _artifact_configured_run(tmp_path)
    report_path = run_dir / "pdf_problem_evidence_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["status"] = "not_required"
    _write_json(report_path, report)

    with pytest.raises(GateProvenanceError, match="pdf_evidence_status_mismatch"):
        write_gate_report(run_dir, paths["gate_config"])


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("report-extra", "article_review_report_fields_invalid"),
        ("article-extra", "article_review_article_fields_invalid:paper"),
        ("bundle-limit", "article_review_bundle_limit_mismatch"),
        ("success-metadata", "article_review_success_article_mismatch:paper"),
        ("selected-count-bool", "article_review_selected_count_mismatch"),
    ],
)
def test_gate_rejects_nonexact_article_review_report(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    run_dir, _gate_report, paths = _artifact_configured_run(tmp_path)
    report_path = run_dir / "article_review_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if mutation == "report-extra":
        report["unexpected"] = True
    elif mutation == "article-extra":
        report["articles"][0]["unexpected"] = True
    elif mutation == "bundle-limit":
        report["bundle_limit"] = 2
    elif mutation == "success-metadata":
        report["articles"][0]["review_href"] = "https://example.invalid/forged"
        report["articles"][0]["inlined_image_count"] = -1
    else:
        report["selected_count"] = True
    _write_json(report_path, report)

    with pytest.raises(GateProvenanceError, match=reason):
        write_gate_report(run_dir, paths["gate_config"])


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("report-extra", "pdf_evidence_report_fields_invalid"),
        ("article-extra", "pdf_evidence_article_fields_invalid:paper"),
        ("selection-candidate-extra", "pdf_evidence_candidate_fields_invalid:paper:0"),
        ("selection-candidate-alias", "pdf_evidence_candidate_invalid:paper:0"),
        ("selected-semantics", "pdf_evidence_text_state_invalid:paper"),
    ],
)
def test_gate_rejects_nonexact_pdf_evidence_report(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    run_dir, _gate_report, paths = _artifact_configured_run(tmp_path)
    report_path = run_dir / "pdf_problem_evidence_report.json"
    if mutation.startswith("selection-candidate-"):
        inputs = json.loads(paths["pdf_selection"].read_text(encoding="utf-8"))
        candidate = inputs["articles"][0]["source_pdf_candidates"][0]
        if mutation == "selection-candidate-extra":
            candidate["unexpected"] = True
        else:
            source_path = Path(candidate["path"])
            candidate["path"] = str(
                source_path.parent / "unused" / ".." / source_path.name
            )
            inputs["articles"][0]["selected_source_pdf"] = dict(candidate)
        _write_json(paths["pdf_selection"], inputs)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if mutation == "selection-candidate-alias":
            report["articles"][0]["source_pdf_origin_path"] = candidate["path"]
        fingerprint = fingerprint_file(paths["pdf_selection"], reject_symlink=True)
        assert fingerprint is not None
        report["provenance"]["inputs"]["bytes"] = fingerprint.size
        report["provenance"]["inputs"]["sha256"] = fingerprint.sha256
    else:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if mutation == "report-extra":
            report["unexpected"] = True
        elif mutation == "article-extra":
            report["articles"][0]["unexpected"] = True
        else:
            report["articles"][0]["text_layer_page_count"] = 999
            report["articles"][0]["evidence_page"] = 999
    _write_json(report_path, report)

    with pytest.raises(GateProvenanceError, match=reason):
        write_gate_report(run_dir, paths["gate_config"])


def test_gate_rejects_unknown_article_review_status(tmp_path: Path) -> None:
    run_dir, _gate_report, paths = _artifact_configured_run(tmp_path)
    queue = json.loads(paths["queue"].read_text(encoding="utf-8"))
    queue[0]["review_status"] = "invented_status"
    _write_json(paths["queue"], queue)
    write_article_review_stage(
        run_dir,
        queue,
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=lambda source, target: {
            "review_html": str(target),
        },
    )

    with pytest.raises(GateProvenanceError, match="article_review_queue_status_invalid"):
        write_gate_report(run_dir, paths["gate_config"])


def test_mandatory_review_needs_fix_remains_blocking(tmp_path: Path) -> None:
    run_dir, _gate_report, paths = _artifact_configured_run(tmp_path)
    queue = json.loads(paths["queue"].read_text(encoding="utf-8"))
    queue[0]["review_status"] = "needs_fix"
    _write_json(paths["queue"], queue)

    def copy_review(source: Path, target: Path) -> dict:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return {
            "review_html": str(target),
            "inlined_image_count": 0,
            "missing_image_count": 0,
            "missing_image_srcs": [],
        }

    write_article_review_stage(
        run_dir,
        queue,
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=copy_review,
    )

    report = write_gate_report(run_dir, paths["gate_config"])

    assert report["status"] == "fail"
    assert {failure["kind"] for failure in report["failures"]} == {
        "mandatory_review_pending"
    }


def test_article_review_rerun_removes_stale_run_owned_artifacts(tmp_path: Path) -> None:
    run_dir, _gate_report, paths = _artifact_configured_run(tmp_path)
    stale = paths["review_dir"] / "stale.txt"
    stale.write_text("old", encoding="utf-8")
    queue = json.loads(paths["queue"].read_text(encoding="utf-8"))

    def copy_review(source: Path, target: Path) -> dict:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return {"review_html": str(target)}

    report = write_article_review_stage(
        run_dir,
        queue,
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=copy_review,
    )

    assert report["status"] == "ready"
    assert not stale.exists()
    assert Path(report["articles"][0]["review_html"]).is_file()


def _previous_configured_run(tmp_path: Path) -> tuple[Path, Path, dict]:
    run_dir = tmp_path / "run"
    previous = tmp_path / "previous.json"
    _write_json(
        previous,
        {
            "run_id": "previous",
            "totals": {
                "score": 0,
                "defects": 0,
                "errors": 0,
                "warnings": 0,
                "infos": 0,
            },
            "articles": {},
        },
    )
    _write_attested_audit(run_dir)
    run_quality_history(
        run_dir,
        run_id="current",
        previous_entry=previous,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    config = tmp_path / "gate.json"
    _write_json(config, {"max_regressions": 0, "max_total_deltas": {}})
    report = write_gate_report(run_dir, config)
    assert report["status"] == "pass"
    return run_dir, previous, report


@pytest.mark.parametrize(
    "input_name",
    ["quality_history_entry", "quality_previous_entry"],
)
def test_gate_rejects_history_input_mutated_after_gate(
    tmp_path: Path,
    input_name: str,
) -> None:
    run_dir, _previous, report = _previous_configured_run(tmp_path)
    record = next(
        item for item in report["input_contract"]["inputs"] if item["name"] == input_name
    )
    path = Path(record["path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tampered"] = True
    _write_json(path, payload)

    with pytest.raises(GateProvenanceError, match=f"gate_input_fingerprint_mismatch:{input_name}"):
        validate_gate_report_provenance(run_dir, report)


def test_gate_replays_forged_history_entry_even_with_updated_fingerprint(
    tmp_path: Path,
) -> None:
    run_dir, _previous, report = _previous_configured_run(tmp_path)
    entry_path = run_dir / "quality_history_entry.json"
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    entry["article_count"] = 999
    _write_json(entry_path, entry)
    fingerprint = fingerprint_file(entry_path, reject_symlink=True)
    assert fingerprint is not None
    forged = deepcopy(report)
    record = next(
        item
        for item in forged["input_contract"]["inputs"]
        if item["name"] == "quality_history_entry"
    )
    record["bytes"] = fingerprint.size
    record["sha256"] = fingerprint.sha256

    with pytest.raises(GateProvenanceError, match="quality_history_entry_recompute_mismatch"):
        validate_gate_report_provenance(run_dir, forged)


def test_external_previous_mutation_after_snapshot_does_not_change_gate_authority(
    tmp_path: Path,
) -> None:
    run_dir, previous, report = _previous_configured_run(tmp_path)
    snapshot_before = (run_dir / "quality_previous_entry_snapshot.json").read_bytes()
    _write_json(previous, {"run_id": "replaced", "totals": {}, "articles": {}})

    validation = validate_gate_report_provenance(run_dir, report)

    assert validation.input_records
    assert (run_dir / "quality_previous_entry_snapshot.json").read_bytes() == snapshot_before


def test_quality_history_rerun_rejects_conflicting_previous_authority(tmp_path: Path) -> None:
    run_dir, previous, _report = _previous_configured_run(tmp_path)
    _write_json(previous, {"run_id": "different", "totals": {}, "articles": {}})

    with pytest.raises(subprocess.CalledProcessError):
        run_quality_history(
            run_dir,
            run_id="current",
            previous_entry=previous,
            no_append=True,
            repo_root=Path(__file__).resolve().parents[1],
        )


@pytest.mark.parametrize(
    "text",
    ['{"run_id":"one","run_id":"two"}\n', '{"run_id":NaN}\n'],
)
def test_quality_history_rejects_ambiguous_previous_json(tmp_path: Path, text: str) -> None:
    run_dir = tmp_path / "run"
    _write_json(run_dir / "audit_full_checks.json", {"articles": []})
    previous = tmp_path / "previous.json"
    previous.write_text(text, encoding="utf-8")

    with pytest.raises(subprocess.CalledProcessError):
        run_quality_history(
            run_dir,
            run_id="current",
            previous_entry=previous,
            no_append=True,
            repo_root=Path(__file__).resolve().parents[1],
        )
