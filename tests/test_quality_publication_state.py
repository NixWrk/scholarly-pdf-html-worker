from __future__ import annotations

import json
from pathlib import Path
import shutil

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
    _write_json(quality_run / "quality_gate_report.json", {"status": "pass"})
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

def test_quality_publication_seal_validates_exact_audited_snapshot(tmp_path: Path) -> None:
    quality_run, _production_raw, _audited_polish = _quality_run(tmp_path)

    seal = seal_quality_publication(quality_run)
    validation = validate_quality_publication(quality_run)

    assert seal["status"] == "completed"
    assert validation.valid
    assert set(validation.records_by_article) == {"article_a"}
    assert (quality_run / QUALITY_PUBLICATION_MANIFEST_NAME).is_file()


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
    assert validation.records_by_article == {}
    assert [record["article_id"] for record in seal["snapshot"]["skipped_articles"]] == [
        "article_a"
    ]


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
