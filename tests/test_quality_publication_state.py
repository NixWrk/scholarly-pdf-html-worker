from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from conftest import write_attested_audit_command

from pdf_html_polish.artifact_integrity import fingerprint_file
from pdf_html_polish.html_stages import (
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    write_raw_conversion_manifest,
)
from pdf_html_polish.quality_loop.cached_run_state import (
    CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
    cached_repolish_artifact_fingerprints,
)
from pdf_html_polish.quality_loop.enrichment_snapshot import (
    initialize_enrichment_snapshot,
    snapshot_enrichment_file,
)
from pdf_html_polish.quality_loop.commands import run_quality_history, write_gate_report
from pdf_html_polish.quality_loop.review_workflow import write_article_review_stage
from pdf_html_polish.quality_loop.publication_state import (
    QUALITY_PUBLICATION_MANIFEST_NAME,
    seal_quality_publication,
    validate_quality_publication,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _audit_record(article_id: str, raw_path: Path, polish_path: Path) -> dict:
    raw = fingerprint_file(raw_path, reject_symlink=True)
    polish = fingerprint_file(polish_path, reject_symlink=True)
    assert raw is not None
    assert polish is not None
    return {
        "article": article_id,
        "raw_stage_path": str(raw_path),
        "polish_stage_path": str(polish_path),
        "raw_stage_bytes": raw.size,
        "raw_stage_sha256": raw.sha256,
        "polish_stage_bytes": polish.size,
        "polish_stage_sha256": polish.sha256,
        "summary": {},
        "defects_found": [],
    }


def _quality_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    article_id = "article_a"
    converted = tmp_path / "converted"
    stage_dir = converted / article_id / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    production_raw = stage_dir / RAW_STAGE_NAME
    production_raw.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
    target_polish = stage_dir / POLISH_STAGE_NAME
    target_polish.write_text("<html><body><p>Old.</p></body></html>", encoding="utf-8")
    write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=production_raw,
    )

    quality_run = tmp_path / "quality"
    source_run = quality_run / "_converted_raw_source"
    source_cached_raw = source_run / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
    source_cached_raw.parent.mkdir(parents=True)
    shutil.copyfile(production_raw, source_cached_raw)
    profile_path = source_run / "profiles" / f"{article_id}.citation_profile.json"
    _write_json(profile_path, {"status": "ok", "style": "unknown", "confidence": "low"})
    _write_json(
        source_run / "manifest.json",
        {
            "source_snapshot_schema_version": CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
            "source_kind": "converted_raw_cache",
            "out_dir": str(source_run),
            "raw_count": 1,
            "article_count": 1,
            "raw_cache_dir": str(source_run / "raw_cache"),
            "profile_dir": str(source_run / "profiles"),
            "profile_status_counts": {"ok": 1},
            "profile_style_counts": {"unknown:low": 1},
            "articles": [
                {
                    "index": 1,
                    "article_id": article_id,
                    "article": article_id,
                    "raw_stage_path": str(production_raw),
                    "raw_cache_path": str(source_cached_raw),
                    "profile_path": str(profile_path),
                    "source_polish_path": str(target_polish),
                    "profile_status": "ok",
                    "citation_style": "unknown",
                    "citation_confidence": "low",
                    **cached_repolish_artifact_fingerprints(source_cached_raw, profile_path),
                }
            ],
        },
    )
    source_manifest_fingerprint = fingerprint_file(source_run / "manifest.json", reject_symlink=True)
    assert source_manifest_fingerprint is not None
    enrichment_snapshot = initialize_enrichment_snapshot(quality_run)

    quality_cached_raw = quality_run / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
    quality_cached_raw.parent.mkdir(parents=True)
    shutil.copyfile(production_raw, quality_cached_raw)
    audit_dir = quality_run / "audit_tree" / article_id
    audit_dir.mkdir(parents=True)
    audit_raw = audit_dir / RAW_STAGE_NAME
    audited_polish = audit_dir / POLISH_STAGE_NAME
    shutil.copyfile(production_raw, audit_raw)
    audited_polish.write_text(
        "<html><body><p>Audited.</p></body></html>",
        encoding="utf-8",
    )
    quality_polish = quality_run / "polish" / f"{article_id}.{POLISH_STAGE_NAME}"
    quality_polish.parent.mkdir(parents=True)
    shutil.copyfile(audited_polish, quality_polish)
    _write_json(
        quality_run / "manifest.json",
        {
            "source_kind": "cached_raw_repolish",
            "source_run_dir": str(source_run),
            "source_manifest_bytes": source_manifest_fingerprint.size,
            "source_manifest_sha256": source_manifest_fingerprint.sha256,
            "enrichment_snapshot_dir": str(enrichment_snapshot),
            "articles": [
                {
                    "article": article_id,
                    "raw_cache_path": str(quality_cached_raw),
                    "polish_path": str(quality_polish),
                }
            ],
        },
    )
    _write_json(
        quality_run / "audit_full_checks.json",
        {
            "audit_status": "complete",
            "articles": [_audit_record(article_id, audit_raw, audited_polish)],
        },
    )
    _write_gate_from_current_inputs(quality_run, tmp_path)
    return quality_run, production_raw, audited_polish



def _mark_article_skipped(quality_run: Path) -> None:
    manifest_path = quality_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    skipped = manifest["articles"].pop()
    skipped["language_skipped"] = True
    skipped["skip_reason"] = "detected_non_target_language"
    manifest["skipped_articles"] = [skipped]
    _write_json(manifest_path, manifest)
    audit_path = quality_run / "audit_full_checks.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["articles"] = []
    _write_json(audit_path, audit)
    audit_dir = quality_run / "audit_tree" / "article_a"
    (audit_dir / RAW_STAGE_NAME).unlink()
    (audit_dir / POLISH_STAGE_NAME).unlink()
    _write_gate_from_current_inputs(quality_run, quality_run.parent)

def _write_gate_from_current_inputs(
    quality_run: Path,
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    write_attested_audit_command(quality_run)
    comparison_path = quality_run / "quality_compare.json"
    article_review_path = quality_run / "article_review_report.json"
    gate_config_path = tmp_path / "gate_config.json"
    write_article_review_stage(
        quality_run,
        [],
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=lambda _source, _target: {},
    )
    run_quality_history(
        quality_run,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    _write_json(
        gate_config_path,
        {
            "max_regressions": 0,
            "max_total_deltas": {},
            "require_article_review_stage": True,
            "allow_missing_previous": True,
            "max_pending_mandatory_reviews": 0,
        },
    )
    write_gate_report(quality_run, gate_config_path)
    return comparison_path, article_review_path, gate_config_path


def test_quality_publication_rejects_comparison_changed_after_gate_report(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    comparison_path, _article_review_path, _gate_config_path = _write_gate_from_current_inputs(
        quality_run,
        tmp_path,
    )
    _write_json(
        comparison_path,
        {"status": "ok", "regressions": [{"article": "late_regression"}]},
    )

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("gate_provenance" in error for error in seal["errors"])


def test_quality_publication_rejects_article_review_changed_after_gate_report(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    _comparison_path, article_review_path, _gate_config_path = _write_gate_from_current_inputs(
        quality_run,
        tmp_path,
    )
    _write_json(
        article_review_path,
        {"status": "ready", "pending_mandatory_count": 1},
    )

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("gate_provenance" in error for error in seal["errors"])


def test_quality_publication_seal_validates_exact_audited_snapshot(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)

    seal = seal_quality_publication(quality_run)
    validation = validate_quality_publication(quality_run)

    assert seal["status"] == "completed"
    assert validation.valid
    assert set(validation.records_by_article) == {"article_a"}
    assert [record["name"] for record in seal["snapshot"]["gate_inputs"]] == [
        "gate_config",
        "assessment",
        "quality_history_entry",
        "quality_previous_entry",
        "quality_compare",
        "article_review",
        "audit_report",
        "audit_command",
        "pdf_problem_evidence",
    ]
    assert (quality_run / QUALITY_PUBLICATION_MANIFEST_NAME).is_file()


@pytest.mark.parametrize(
    ("input_name", "replacement"),
    [
        ("quality_compare.json", {"status": "ok", "regressions": [{"article": "late"}]}),
        ("article_review_report.json", {"status": "ready", "pending_mandatory_count": 1}),
        ("audit_command_report.json", {"pdf_diagnostics_enabled": True}),
        ("pdf_problem_evidence_report.json", {"status": "ready"}),
    ],
)
def test_quality_publication_rejects_gate_input_changed_after_seal(
    tmp_path: Path,
    input_name: str,
    replacement: dict,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    assert seal_quality_publication(quality_run)["status"] == "completed"
    _write_json(quality_run / input_name, replacement)

    validation = validate_quality_publication(quality_run)

    assert not validation.valid
    assert "gate_provenance" in validation.reason


def test_quality_publication_rejects_gate_config_snapshot_changed_after_seal(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    assert seal_quality_publication(quality_run)["status"] == "completed"
    snapshot_path = quality_run / "quality_gate_config_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["config"]["max_regressions"] = 99
    _write_json(snapshot_path, snapshot)

    validation = validate_quality_publication(quality_run)

    assert not validation.valid
    assert "gate_provenance" in validation.reason


def test_quality_publication_requires_enrichment_snapshot(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    shutil.rmtree(quality_run / "_enrichment_snapshot")

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any(
        error.startswith("enrichment_snapshot_invalid:")
        for error in seal["errors"]
    )


def test_quality_publication_rejects_enrichment_snapshot_path_alias(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    manifest_path = quality_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_dir = quality_run / "_enrichment_snapshot"
    manifest["enrichment_snapshot_dir"] = str(
        snapshot_dir.parent / "unused" / ".." / snapshot_dir.name
    )
    _write_json(manifest_path, manifest)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert "quality_enrichment_snapshot_dir_mismatch" in seal["errors"]


def test_quality_publication_rejects_enrichment_artifact_tampered_before_seal(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    source = tmp_path / "repair.pdf"
    source.write_bytes(b"repair-pdf")
    artifact = snapshot_enrichment_file(
        quality_run,
        "article_a",
        "p96_pdf",
        source,
    )
    artifact.write_bytes(b"tampered")

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any(
        error.startswith("enrichment_snapshot_invalid:artifact_fingerprint_mismatch")
        for error in seal["errors"]
    )


def test_quality_publication_rejects_enrichment_artifact_tampered_after_seal(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    source = tmp_path / "repair.pdf"
    source.write_bytes(b"repair-pdf")
    artifact = snapshot_enrichment_file(
        quality_run,
        "article_a",
        "p96_pdf",
        source,
    )
    assert seal_quality_publication(quality_run)["status"] == "completed"
    artifact.write_bytes(b"tampered")

    validation = validate_quality_publication(quality_run)

    assert not validation.valid
    assert "enrichment_snapshot_invalid:artifact_fingerprint_mismatch" in validation.reason


@pytest.mark.parametrize(
    "count_key",
    ["restored_images", "pdf_reference_recovered"],
)
def test_quality_publication_requires_declared_enrichment_usage(
    tmp_path: Path,
    count_key: str,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    manifest_path = quality_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"][0][count_key] = 1
    _write_json(manifest_path, manifest)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert (
        f"quality_enrichment_provenance_missing:article_a:{count_key}"
        in seal["errors"]
    )


def test_quality_publication_accepts_declared_enrichment_usage(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    source = tmp_path / "sidecar.png"
    source.write_bytes(b"image-bytes")
    snapshot_enrichment_file(
        quality_run,
        "article_a",
        "image_sidecar",
        source,
    )
    manifest_path = quality_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"][0]["restored_images"] = 1
    _write_json(manifest_path, manifest)

    assert seal_quality_publication(quality_run)["status"] == "completed"
    assert validate_quality_publication(quality_run).valid


def test_quality_publication_rejects_consistent_enrichment_rewrite_after_seal(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    source = tmp_path / "repair.pdf"
    source.write_bytes(b"repair-pdf")
    artifact = snapshot_enrichment_file(
        quality_run,
        "article_a",
        "p96_pdf",
        source,
    )
    assert seal_quality_publication(quality_run)["status"] == "completed"

    replacement = b"consistent-rewrite"
    replacement_sha256 = hashlib.sha256(replacement).hexdigest()
    replacement_path = artifact.with_name(f"{replacement_sha256}.pdf")
    replacement_path.write_bytes(replacement)
    artifact.unlink()
    enrichment_manifest_path = quality_run / "_enrichment_snapshot" / "manifest.json"
    enrichment_manifest = json.loads(enrichment_manifest_path.read_text(encoding="utf-8"))
    record = enrichment_manifest["artifacts"][0]
    record["path"] = str(replacement_path)
    record["bytes"] = len(replacement)
    record["sha256"] = replacement_sha256
    for usage in record["uses"]:
        usage["source_bytes"] = len(replacement)
        usage["source_sha256"] = replacement_sha256
    _write_json(enrichment_manifest_path, enrichment_manifest)

    validation = validate_quality_publication(quality_run)

    assert not validation.valid
    assert validation.reason == "snapshot_changed"


def test_quality_publication_rejects_source_profile_changed_before_seal(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    quality_manifest = json.loads((quality_run / "manifest.json").read_text(encoding="utf-8"))
    source_run = Path(quality_manifest["source_run_dir"])
    profile_path = source_run / "profiles" / "article_a.citation_profile.json"
    _write_json(profile_path, {"status": "tampered", "style": "unknown", "confidence": "low"})

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("source_snapshot_invalid" in error for error in seal["errors"])


def test_quality_publication_rejects_source_profile_changed_after_seal(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    assert seal_quality_publication(quality_run)["status"] == "completed"
    quality_manifest = json.loads((quality_run / "manifest.json").read_text(encoding="utf-8"))
    source_run = Path(quality_manifest["source_run_dir"])
    profile_path = source_run / "profiles" / "article_a.citation_profile.json"
    _write_json(profile_path, {"status": "tampered", "style": "unknown", "confidence": "low"})

    validation = validate_quality_publication(quality_run)



    assert not validation.valid
    assert "source_snapshot_invalid" in validation.reason


def test_quality_publication_rejects_polish_changed_after_seal(tmp_path: Path) -> None:
    quality_run, _production_raw, audited_polish = _quality_run(tmp_path)
    assert seal_quality_publication(quality_run)["status"] == "completed"

    audited_polish.write_text(
        "<html><body><p>Tampered after audit.</p></body></html>",
        encoding="utf-8",
    )

    validation = validate_quality_publication(quality_run)
    assert not validation.valid
    assert "audit_polish_fingerprint_mismatch" in validation.reason


def test_quality_publication_rejects_gate_changed_after_seal(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    assert seal_quality_publication(quality_run)["status"] == "completed"
    _write_json(
        quality_run / "quality_gate_report.json",
        {"status": "fail", "failures": [{"kind": "late_regression"}]},
    )

    validation = validate_quality_publication(quality_run)

    assert not validation.valid
    assert "quality_gate_not_pass:fail" in validation.reason


@pytest.mark.parametrize(
    "seal_json",
    [
        '{"schema_version":3,"schema_version":3}\n',
        '{"schema_version":3,"status":"completed","snapshot":{},"probe":NaN}\n',
    ],
    ids=["duplicate-key", "nonfinite-number"],
)
def test_quality_publication_rejects_ambiguous_seal_json(
    tmp_path: Path,
    seal_json: str,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    assert seal_quality_publication(quality_run)["status"] == "completed"
    (quality_run / QUALITY_PUBLICATION_MANIFEST_NAME).write_text(
        seal_json,
        encoding="utf-8",
    )

    validation = validate_quality_publication(quality_run)

    assert not validation.valid
    assert validation.reason == "manifest_unreadable"


def test_quality_publication_rejects_production_raw_changed_after_seal(tmp_path: Path) -> None:
    quality_run, production_raw, _audited_polish = _quality_run(tmp_path)
    assert seal_quality_publication(quality_run)["status"] == "completed"

    production_raw.write_text(
        "<html><body><p>New conversion.</p></body></html>",
        encoding="utf-8",
    )

    validation = validate_quality_publication(quality_run)
    assert not validation.valid
    assert "production_raw_invalid" in validation.reason


def test_quality_publication_does_not_seal_malformed_polish(tmp_path: Path) -> None:
    quality_run, _production_raw, audited_polish = _quality_run(tmp_path)
    audited_polish.write_text("<html><body>truncated", encoding="utf-8")
    audit_report = json.loads((quality_run / "audit_full_checks.json").read_text(encoding="utf-8"))
    audit_report["articles"] = [_audit_record("article_a", audited_polish.parent / RAW_STAGE_NAME, audited_polish)]
    _write_json(quality_run / "audit_full_checks.json", audit_report)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("audited_polish_invalid" in error for error in seal["errors"])
    assert not validate_quality_publication(quality_run).valid


def test_quality_publication_requires_complete_audit_report(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    audit_report = json.loads((quality_run / "audit_full_checks.json").read_text(encoding="utf-8"))
    audit_report["audit_status"] = "running"
    _write_json(quality_run / "audit_full_checks.json", audit_report)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert "audit_report_not_complete" in seal["errors"]


def test_quality_publication_rejects_extra_audit_article(tmp_path: Path) -> None:
    quality_run, _production_raw, audited_polish = _quality_run(tmp_path)
    audit_path = quality_run / "audit_full_checks.json"
    audit_report = json.loads(audit_path.read_text(encoding="utf-8"))
    extra = _audit_record(
        "stale_extra",
        audited_polish.parent / RAW_STAGE_NAME,
        audited_polish,
    )
    audit_report["articles"].append(extra)
    _write_json(audit_path, audit_report)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("audit_article_set_mismatch" in error for error in seal["errors"])


def test_quality_publication_accepts_exact_all_skipped_coverage(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    _mark_article_skipped(quality_run)

    seal = seal_quality_publication(quality_run)
    validation = validate_quality_publication(quality_run)

    assert seal["status"] == "completed"
    assert validation.valid
    record = validation.records_by_article["article_a"]
    assert record["publication_kind"] == "skipped_fallback"
    assert record["final_polish"] == record["fallback_polish"]
    assert record["fallback_polish"]["path"] == str(
        (_production_raw.parent / POLISH_STAGE_NAME).resolve(strict=False)
    )
    assert [record["article_id"] for record in seal["snapshot"]["skipped_articles"]] == [
        "article_a"
    ]


@pytest.mark.parametrize("fallback_state", ["missing", "malformed"])
def test_quality_publication_rejects_invalid_skipped_fallback_before_seal(
    tmp_path: Path,
    fallback_state: str,
) -> None:
    quality_run, production_raw, _audited_polish = _quality_run(tmp_path)
    _mark_article_skipped(quality_run)
    fallback = production_raw.parent / POLISH_STAGE_NAME
    if fallback_state == "missing":
        fallback.unlink()
    else:
        fallback.write_text("<html><body>truncated", encoding="utf-8")

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("fallback_polish_invalid:article_a" in error for error in seal["errors"])


def test_quality_publication_rejects_redirected_skipped_fallback_path(
    tmp_path: Path,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    _mark_article_skipped(quality_run)
    rogue = tmp_path / "rogue.html"
    rogue.write_text("<html><body><p>Unrelated HTML.</p></body></html>", encoding="utf-8")
    quality_manifest_path = quality_run / "manifest.json"
    quality_manifest = json.loads(quality_manifest_path.read_text(encoding="utf-8"))
    source_run = Path(quality_manifest["source_run_dir"])
    source_manifest_path = source_run / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_manifest["articles"][0]["source_polish_path"] = str(rogue)
    _write_json(source_manifest_path, source_manifest)
    source_fingerprint = fingerprint_file(source_manifest_path, reject_symlink=True)
    assert source_fingerprint is not None
    quality_manifest["source_manifest_bytes"] = source_fingerprint.size
    quality_manifest["source_manifest_sha256"] = source_fingerprint.sha256
    _write_json(quality_manifest_path, quality_manifest)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert "target_polish_path_mismatch:article_a" in seal["errors"]


def test_quality_publication_rejects_linked_skipped_fallback(
    tmp_path: Path,
) -> None:
    quality_run, production_raw, _audited_polish = _quality_run(tmp_path)
    _mark_article_skipped(quality_run)
    fallback = production_raw.parent / POLISH_STAGE_NAME
    outside = tmp_path / "outside.html"
    outside.write_bytes(fallback.read_bytes())
    fallback.unlink()
    try:
        fallback.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any(
        error.startswith("target_polish_link_like:article_a")
        for error in seal["errors"]
    )


def test_quality_publication_rejects_skipped_fallback_changed_after_seal(
    tmp_path: Path,
) -> None:
    quality_run, production_raw, _audited_polish = _quality_run(tmp_path)
    _mark_article_skipped(quality_run)
    assert seal_quality_publication(quality_run)["status"] == "completed"
    fallback = production_raw.parent / POLISH_STAGE_NAME
    fallback.write_text("<html><body><p>Changed fallback.</p></body></html>", encoding="utf-8")

    validation = validate_quality_publication(quality_run)

    assert not validation.valid
    assert "snapshot_changed" in validation.reason


def test_quality_publication_rechecks_skipped_production_raw(tmp_path: Path) -> None:
    quality_run, production_raw, _audited_polish = _quality_run(tmp_path)
    _mark_article_skipped(quality_run)
    assert seal_quality_publication(quality_run)["status"] == "completed"

    production_raw.write_text(
        "<html><body><p>Changed after skip.</p></body></html>",
        encoding="utf-8",
    )

    validation = validate_quality_publication(quality_run)
    assert not validation.valid
    assert "production_raw_invalid" in validation.reason


def test_quality_publication_rejects_unclassified_source_article(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    source_manifest_path = quality_run / "_converted_raw_source" / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    extra = dict(source_manifest["articles"][0])
    extra["article_id"] = "unclassified_extra"
    source_manifest["articles"].append(extra)
    _write_json(source_manifest_path, source_manifest)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("source_article_set_mismatch" in error for error in seal["errors"])


def test_quality_publication_rejects_processed_skipped_overlap(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    manifest_path = quality_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["skipped_articles"] = [dict(manifest["articles"][0])]
    _write_json(manifest_path, manifest)

    seal = seal_quality_publication(quality_run)
    assert seal["status"] == "invalid"
    assert any("quality_processed_skipped_overlap" in error for error in seal["errors"])



def test_quality_publication_rejects_invalid_utf8_html(tmp_path: Path) -> None:
    quality_run, _production_raw, audited_polish = _quality_run(tmp_path)
    audited_polish.write_bytes(b"<html><body>\xff</body></html>")
    audit_path = quality_run / "audit_full_checks.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["articles"] = [
        _audit_record("article_a", audited_polish.parent / RAW_STAGE_NAME, audited_polish)
    ]
    _write_json(audit_path, audit)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("invalid_utf8" in error for error in seal["errors"])


def test_quality_publication_rejects_relative_source_run_path(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    manifest_path = quality_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_run_dir"] = "_converted_raw_source"
    _write_json(manifest_path, manifest)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert "quality_source_run_dir_not_absolute" in seal["errors"]


@pytest.mark.parametrize(
    "gate_payload",
    [
        {"status": "fail", "failures": [{"kind": "regression"}]},
        {"status": "unknown", "failures": []},
        {},
    ],
    ids=["failed", "unknown", "missing-status"],
)
def test_quality_publication_rejects_gate_that_did_not_pass(
    tmp_path: Path,
    gate_payload: dict,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    _write_json(quality_run / "quality_gate_report.json", gate_payload)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any(error.startswith("quality_gate_not_pass:") for error in seal["errors"])
    assert not validate_quality_publication(quality_run).valid


@pytest.mark.parametrize(
    "gate_json",
    [
        '{"status":"pass","status":"pass"}\n',
        '{"status":"pass","score":NaN}\n',
    ],
    ids=["duplicate-key", "nonfinite-number"],
)
def test_quality_publication_rejects_ambiguous_gate_json(
    tmp_path: Path,
    gate_json: str,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    (quality_run / "quality_gate_report.json").write_text(gate_json, encoding="utf-8")

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any("quality_gate_report" in error or "json_unreadable" in error for error in seal["errors"])
    assert not validate_quality_publication(quality_run).valid


@pytest.mark.parametrize(
    "gate_payload",
    [
        {"status": "pass"},
        {"status": "pass", "failures": {}},
        {"status": "pass", "failures": [{"kind": "hidden_failure"}]},
    ],
    ids=["missing-failures", "invalid-failures", "inconsistent-pass"],
)
def test_quality_publication_requires_consistent_pass_gate_contract(
    tmp_path: Path,
    gate_payload: dict,
) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)
    _write_json(quality_run / "quality_gate_report.json", gate_payload)

    seal = seal_quality_publication(quality_run)

    assert seal["status"] == "invalid"
    assert any(
        error in {"quality_gate_failures_invalid", "quality_gate_pass_has_failures"}
        for error in seal["errors"]
    )
