from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from conftest import write_attested_audit_command

import pdf_html_polish.atomic_io as atomic_io_module
import pdf_html_polish.stage_contract as stage_contract_module
from pdf_html_polish.artifact_integrity import fingerprint_file
from pdf_html_polish.html_stages import (
    POLISH_STAGE_NAME,
    RAW_CONVERSION_MANIFEST_NAME,
    RAW_STAGE_NAME,
    write_raw_conversion_manifest,
)
from pdf_html_polish.quality_loop.cached_run_state import (
    CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
    cached_repolish_artifact_fingerprints,
)
from pdf_html_polish.quality_loop.enrichment_snapshot import (
    initialize_enrichment_snapshot,
)
from pdf_html_polish.quality_loop.commands import run_quality_history, write_gate_report
from pdf_html_polish.quality_loop.publication_state import (
    seal_quality_publication,
)
from pdf_html_polish.stage_contract import (
    publish_latest_polish_from_quality_run,
    verify_stage_contract,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_valid_gate_report(quality_run: Path) -> None:
    write_attested_audit_command(quality_run)
    config_path = quality_run.parent / f".{quality_run.name}.gate_config.json"
    run_quality_history(
        quality_run,
        run_id="current",
        previous_entry=None,
        no_append=True,
        repo_root=Path(__file__).resolve().parents[1],
    )
    _write_json(config_path, {"allow_missing_previous": True, "max_regressions": 0, "max_total_deltas": {}})
    write_gate_report(quality_run, config_path)


def _stage_pair(article_dir: Path, *, source_pdf: Path | None = None) -> Path:
    stage_dir = article_dir / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw_path = stage_dir / RAW_STAGE_NAME
    raw_path.write_text("<html><body>raw</body></html>", encoding="utf-8")
    (stage_dir / POLISH_STAGE_NAME).write_text("<html><body>old polish</body></html>", encoding="utf-8")
    resolved_source = source_pdf or article_dir.parent / f"{article_dir.name}.pdf"
    resolved_source.parent.mkdir(parents=True, exist_ok=True)
    if not resolved_source.exists():
        resolved_source.write_bytes(b"%PDF-1.4\n")
    write_raw_conversion_manifest(
        stage_dir,
        source_pdf=resolved_source,
        raw_stage_path=raw_path,
    )
    return stage_dir



def _seal_quality_run(quality_run: Path) -> dict:
    quality_manifest_path = quality_run / "manifest.json"
    quality_manifest = json.loads(quality_manifest_path.read_text(encoding="utf-8"))
    source_run = Path(quality_manifest["source_run_dir"])
    source_manifest_path = source_run / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    quality_manifest["source_kind"] = "cached_raw_repolish"
    source_manifest["source_snapshot_schema_version"] = CACHED_REPOLISH_SOURCE_SCHEMA_VERSION
    source_manifest["source_kind"] = "converted_raw_cache"
    source_manifest["out_dir"] = str(source_run)

    source_articles = [
        article
        for article in source_manifest.get("articles") or []
        if isinstance(article, dict) and article.get("article_id")
    ]
    source_by_id = {str(article["article_id"]): article for article in source_articles}
    for index, source_article in enumerate(source_articles, start=1):
        article_id = str(source_article["article_id"])
        production_raw = Path(str(source_article.get("raw_stage_path") or ""))
        if not production_raw.is_file():
            continue
        source_cached_raw = source_run / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
        source_cached_raw.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(production_raw, source_cached_raw)
        profile_path = source_run / "profiles" / f"{article_id}.citation_profile.json"
        _write_json(profile_path, {"status": "ok", "style": "unknown", "confidence": "low"})
        source_article.update(
            {
                "index": index,
                "article": source_article.get("article") or article_id,
                "raw_cache_path": str(source_cached_raw),
                "profile_path": str(profile_path),
                "profile_status": "ok",
                "citation_style": "unknown",
                "citation_confidence": "low",
                **cached_repolish_artifact_fingerprints(source_cached_raw, profile_path),
            }
        )

    source_manifest["raw_count"] = len(source_articles)
    source_manifest["article_count"] = len(source_articles)
    source_manifest["raw_cache_dir"] = str(source_run / "raw_cache")
    source_manifest["profile_dir"] = str(source_run / "profiles")
    source_manifest["profile_status_counts"] = {"ok": len(source_articles)}
    source_manifest["profile_style_counts"] = {"unknown:low": len(source_articles)}
    source_manifest["articles"] = source_articles
    _write_json(source_manifest_path, source_manifest)
    source_fingerprint = fingerprint_file(source_manifest_path, reject_symlink=True)
    assert source_fingerprint is not None
    quality_manifest["source_manifest_bytes"] = source_fingerprint.size
    quality_manifest["source_manifest_sha256"] = source_fingerprint.sha256
    quality_manifest["enrichment_snapshot_dir"] = str(
        initialize_enrichment_snapshot(quality_run)
    )

    processed_articles = [
        article for article in quality_manifest.get("articles") or [] if isinstance(article, dict)
    ]
    skipped_articles = [
        article for article in quality_manifest.get("skipped_articles") or [] if isinstance(article, dict)
    ]
    audit_articles: list[dict] = []
    for quality_article in [*processed_articles, *skipped_articles]:
        article_id = str(quality_article.get("article") or "")
        source_article = source_by_id.get(article_id)
        if source_article is None or not source_article.get("raw_stage_path"):
            continue
        production_raw = Path(source_article["raw_stage_path"])
        if not production_raw.is_file():
            continue
        quality_cached_raw = quality_run / "raw_cache" / f"{article_id}.{RAW_STAGE_NAME}"
        quality_cached_raw.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(production_raw, quality_cached_raw)
        quality_article["raw_cache_path"] = str(quality_cached_raw)
        if quality_article not in processed_articles:
            continue
        audit_dir = quality_run / "audit_tree" / article_id
        audited_polish = audit_dir / POLISH_STAGE_NAME
        if not audited_polish.is_file():
            continue
        audit_raw = audit_dir / RAW_STAGE_NAME
        shutil.copyfile(production_raw, audit_raw)
        quality_polish = quality_run / "polish" / f"{article_id}.{POLISH_STAGE_NAME}"
        quality_polish.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(audited_polish, quality_polish)
        quality_article["polish_path"] = str(quality_polish)
        raw_fingerprint = fingerprint_file(audit_raw, reject_symlink=True)
        polish_fingerprint = fingerprint_file(audited_polish, reject_symlink=True)
        assert raw_fingerprint is not None
        assert polish_fingerprint is not None
        audit_articles.append(
            {
                "article": article_id,
                "raw_stage_path": str(audit_raw),
                "polish_stage_path": str(audited_polish),
                "raw_stage_bytes": raw_fingerprint.size,
                "raw_stage_sha256": raw_fingerprint.sha256,
                "polish_stage_bytes": polish_fingerprint.size,
                "polish_stage_sha256": polish_fingerprint.sha256,
                "summary": {},
                "defects_found": [],
            }
        )

    _write_json(quality_manifest_path, quality_manifest)
    _write_json(
        quality_run / "audit_full_checks.json",
        {"audit_status": "complete", "articles": audit_articles},
    )
    _write_valid_gate_report(quality_run)
    return seal_quality_publication(quality_run)

def test_verify_stage_contract_passes_for_only_raw_and_polish(tmp_path: Path) -> None:
    _stage_pair(tmp_path / "converted" / "article_a")

    report = verify_stage_contract([tmp_path / "converted"])

    assert report["status"] == "pass"
    assert report["article_count"] == 1
    assert report["extra_html_count"] == 0


def test_verify_stage_contract_rejects_raw_without_manifest(tmp_path: Path) -> None:
    stage_dir = _stage_pair(tmp_path / "converted" / "article_a")
    (stage_dir / RAW_CONVERSION_MANIFEST_NAME).unlink()

    report = verify_stage_contract([tmp_path / "converted"])

    assert report["status"] == "fail"
    assert report["invalid_raw_conversion_count"] == 1
    assert report["articles"][0]["raw_conversion_reason"] == "manifest_missing"


def test_publish_latest_polish_rejects_tampered_raw_before_mutation(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    stage_dir = _stage_pair(converted / "article_a")
    target_polish = stage_dir / POLISH_STAGE_NAME
    old_polish = target_polish.read_text(encoding="utf-8")
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(target_polish),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {
            "source_run_dir": str(source_run),
            "articles": [{"article": article_id}],
        },
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>new audited polish</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"
    (stage_dir / RAW_STAGE_NAME).write_text(
        "<html><body>tampered raw</body></html>",
        encoding="utf-8",
    )

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
    )

    assert report["published_count"] == 0
    assert report["invalid_raw_conversion_count"] == 1
    assert report["stage_contract_status"] == "fail"
    assert report["records"][0]["status"] == "invalid_raw_conversion"
    assert target_polish.read_text(encoding="utf-8") == old_polish


def test_verify_stage_contract_rejects_duplicate_source_ownership(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    shared_source = tmp_path / "sources" / "shared.pdf"
    _stage_pair(converted / "first", source_pdf=shared_source)
    _stage_pair(converted / "second", source_pdf=shared_source)

    report = verify_stage_contract([converted])

    assert report["status"] == "fail"
    assert report["invalid_raw_conversion_count"] == 0
    assert "ownership is ambiguous" in report["raw_validation_error"]


def test_verify_stage_contract_flags_article_and_stage_extra_html(tmp_path: Path) -> None:
    article_dir = tmp_path / "converted" / "article_a"
    stage_dir = _stage_pair(article_dir)
    (article_dir / "article_a.html").write_text("<html>outer</html>", encoding="utf-8")
    (stage_dir / "02.en.polish.before-old.html").write_text("<html>old</html>", encoding="utf-8")

    report = verify_stage_contract([tmp_path / "converted"])

    assert report["status"] == "fail"
    assert report["extra_html_count"] == 2
    assert report["articles"][0]["extra_html_count"] == 2


def test_publish_latest_polish_copies_audited_stage_and_prunes_extras(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    article_dir = converted / "article_a"
    stage_dir = _stage_pair(article_dir)
    extra_outer = article_dir / "article_a.html"
    extra_stage = stage_dir / "02.en.polish.before-old.html"
    extra_outer.write_text("<html>outer</html>", encoding="utf-8")
    extra_stage.write_text("<html>old backup</html>", encoding="utf-8")

    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "collection_key_article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(stage_dir / POLISH_STAGE_NAME),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {
            "source_run_dir": str(source_run),
            "code_commit": "abc123",
            "working_tree_dirty": False,
            "articles": [{"article": article_id}],
        },
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>latest audited polish</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
        prune_extra_html=True,
    )

    assert report["published_count"] == 1
    assert report["removed_extra_html_count"] == 2
    assert report["stage_contract_status"] == "pass"
    assert (stage_dir / POLISH_STAGE_NAME).read_text(encoding="utf-8") == (
        "<html><body>latest audited polish</body></html>"
    )
    assert not extra_outer.exists()
    assert not extra_stage.exists()


def test_publish_latest_polish_ignores_log_only_stale_stage_dir_after_prune(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    article_dir = converted / "article_a"
    stage_dir = _stage_pair(article_dir)
    stale_stage_dir = article_dir / "_pdf_html_polish_stages"
    stale_stage_dir.mkdir()
    stale_raw = stale_stage_dir / RAW_STAGE_NAME
    stale_polish = stale_stage_dir / POLISH_STAGE_NAME
    stale_log = stale_stage_dir / "stage.log"
    stale_raw.write_text("<html>stale raw</html>", encoding="utf-8")
    stale_polish.write_text("<html>stale polish</html>", encoding="utf-8")
    stale_log.write_text("debug history\n", encoding="utf-8")

    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "collection_key_article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(stage_dir / POLISH_STAGE_NAME),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {
            "source_run_dir": str(source_run),
            "articles": [{"article": article_id}],
        },
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>latest audited polish</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
        prune_extra_html=True,
    )

    assert report["stage_contract_status"] == "pass"
    assert report["removed_extra_html_count"] == 2
    assert not stale_raw.exists()
    assert not stale_polish.exists()
    assert stale_log.exists()
    assert verify_stage_contract([converted])["status"] == "pass"


def test_publish_latest_polish_dry_run_does_not_mutate(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    article_dir = converted / "article_a"
    stage_dir = _stage_pair(article_dir)
    extra = article_dir / "article_a.html"
    extra.write_text("<html>outer</html>", encoding="utf-8")

    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(stage_dir / POLISH_STAGE_NAME),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {
            "source_run_dir": str(source_run),
            "articles": [{"article": article_id}],
        },
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>new</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=False,
        prune_extra_html=True,
    )

    assert report["mode"] == "dry_run"
    assert report["dry_run_count"] == 1
    assert report["extra_html_count"] == 1
    assert (stage_dir / POLISH_STAGE_NAME).read_text(encoding="utf-8") == (
        "<html><body>old polish</body></html>"
    )
    assert extra.exists()


def test_publish_latest_polish_reports_missing_source_stage_paths(tmp_path: Path) -> None:
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_without_paths"
    _write_json(source_run / "manifest.json", {"articles": [{"article_id": article_id}]})
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {
            "source_run_dir": str(source_run),
            "articles": [{"article": article_id}],
        },
    )

    report = publish_latest_polish_from_quality_run(quality_run, apply=True)

    assert report["published_count"] == 0
    assert report["missing_count"] == 1
    assert report["stage_contract_status"] == "fail"
    assert report["records"][0]["status"] == "missing_source_stage_paths"


def test_publish_latest_polish_failed_copy_preserves_previous_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    converted = tmp_path / "converted"
    article_dir = converted / "article_a"
    stage_dir = _stage_pair(article_dir)
    target = stage_dir / POLISH_STAGE_NAME
    extra = article_dir / "article_a.html"
    extra.write_text("<html>extra</html>", encoding="utf-8")
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(target),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {"source_run_dir": str(source_run), "articles": [{"article": article_id}]},
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>new</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"

    def fail_copy(_source: Path, temporary: Path) -> None:
        Path(temporary).write_text("partial", encoding="utf-8")
        raise OSError("simulated interrupted publish")

    monkeypatch.setattr(atomic_io_module.shutil, "copyfile", fail_copy)

    with pytest.raises(OSError, match="simulated interrupted publish"):
        publish_latest_polish_from_quality_run(
            quality_run,
            converted_roots=[converted],
            apply=True,
        )

    assert target.read_text(encoding="utf-8") == "<html><body>old polish</body></html>"
    assert extra.exists()
    assert list(stage_dir.glob("*.tmp")) == []


def test_publish_latest_polish_preflight_blocks_all_mutation(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    first_stage = _stage_pair(converted / "first")
    second_stage = _stage_pair(converted / "second")
    first_extra = converted / "first" / "first.html"
    first_extra.write_text("<html>extra</html>", encoding="utf-8")
    source_run = tmp_path / "quality" / "_converted_raw_source"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": "first",
                    "raw_stage_path": str(first_stage / RAW_STAGE_NAME),
                    "source_polish_path": str(first_stage / POLISH_STAGE_NAME),
                },
                {
                    "article_id": "second",
                    "raw_stage_path": str(second_stage / RAW_STAGE_NAME),
                    "source_polish_path": str(second_stage / POLISH_STAGE_NAME),
                },
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {
            "source_run_dir": str(source_run),
            "articles": [{"article": "first"}, {"article": "second"}],
        },
    )
    first_audited = quality_run / "audit_tree" / "first" / POLISH_STAGE_NAME
    first_audited.parent.mkdir(parents=True)
    first_audited.write_text("<html><body>new first</body></html>", encoding="utf-8")
    second_audited = quality_run / "audit_tree" / "second" / POLISH_STAGE_NAME
    second_audited.parent.mkdir(parents=True)
    second_audited.write_text("<html><body>new second</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"
    second_audited.unlink()

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
    )

    assert report["published_count"] == 0
    assert report["missing_count"] == 1
    assert report["stage_contract_status"] == "fail"
    assert {record["article"]: record["status"] for record in report["records"]} == {
        "first": "invalid_quality_publication",
        "second": "missing_audited_polish",
    }
    assert (first_stage / POLISH_STAGE_NAME).read_text(encoding="utf-8") == (
        "<html><body>old polish</body></html>"
    )
    assert first_extra.exists()


def test_publish_latest_polish_rejects_audit_tree_traversal(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    stage_dir = _stage_pair(converted / "article_a")
    target = stage_dir / POLISH_STAGE_NAME
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "../outside"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(target),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {"source_run_dir": str(source_run), "articles": [{"article": article_id}]},
    )
    outside = quality_run / "outside" / POLISH_STAGE_NAME
    outside.parent.mkdir(parents=True)
    outside.write_text("<html>outside</html>", encoding="utf-8")

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
    )

    assert report["published_count"] == 0
    assert report["outside_scope_count"] == 1
    assert report["records"][0]["status"] == "outside_quality_audit_tree"
    assert target.read_text(encoding="utf-8") == "<html><body>old polish</body></html>"


def test_publish_latest_polish_rejects_symlink_extra(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    article_dir = converted / "article_a"
    stage_dir = _stage_pair(article_dir)
    target = stage_dir / POLISH_STAGE_NAME
    outside = tmp_path / "outside.html"
    outside.write_text("<html>outside</html>", encoding="utf-8")
    extra = article_dir / "linked.html"
    try:
        extra.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is not permitted")
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(target),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {"source_run_dir": str(source_run), "articles": [{"article": article_id}]},
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>new</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
    )

    assert report["published_count"] == 0
    assert report["outside_scope_count"] == 1
    assert report["records"][0]["status"] == "unsafe_extra_html_path"
    assert outside.read_text(encoding="utf-8") == "<html>outside</html>"
    assert extra.is_symlink()


def test_publish_latest_polish_rejects_missing_publication_seal(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    stage_dir = _stage_pair(converted / "article_a")
    target = stage_dir / POLISH_STAGE_NAME
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(target),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {"source_run_dir": str(source_run), "articles": [{"article": article_id}]},
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>new</body></html>", encoding="utf-8")

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
    )

    assert report["published_count"] == 0
    assert report["quality_publication_valid"] is False
    assert report["records"][0]["status"] == "invalid_quality_publication"
    assert target.read_text(encoding="utf-8") == "<html><body>old polish</body></html>"


def test_publish_latest_polish_rejects_valid_html_tampered_after_seal(tmp_path: Path) -> None:
    converted = tmp_path / "converted"
    stage_dir = _stage_pair(converted / "article_a")
    target = stage_dir / POLISH_STAGE_NAME
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(stage_dir / RAW_STAGE_NAME),
                    "source_polish_path": str(target),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {"source_run_dir": str(source_run), "articles": [{"article": article_id}]},
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>sealed</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"
    audited.write_text("<html><body>tampered but valid</body></html>", encoding="utf-8")

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
    )

    assert report["published_count"] == 0
    assert report["quality_publication_valid"] is False
    assert report["records"][0]["status"] == "invalid_quality_publication"
    assert target.read_text(encoding="utf-8") == "<html><body>old polish</body></html>"


def test_publish_latest_polish_rechecks_raw_after_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    converted = tmp_path / "converted"
    stage_dir = _stage_pair(converted / "article_a")
    production_raw = stage_dir / RAW_STAGE_NAME
    target = stage_dir / POLISH_STAGE_NAME
    source_run = tmp_path / "quality" / "_converted_raw_source"
    article_id = "article_a"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": article_id,
                    "raw_stage_path": str(production_raw),
                    "source_polish_path": str(target),
                }
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {"source_run_dir": str(source_run), "articles": [{"article": article_id}]},
    )
    audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html><body>sealed</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"
    original_stage = stage_contract_module.stage_audited_polish

    def stage_then_change_raw(source: Path, destination: Path, sealed_record: dict) -> None:
        original_stage(source, destination, sealed_record)
        production_raw.write_text("<html><body>changed raw</body></html>", encoding="utf-8")

    monkeypatch.setattr(stage_contract_module, "stage_audited_polish", stage_then_change_raw)

    with pytest.raises(RuntimeError, match="Quality publication changed during staging"):
        publish_latest_polish_from_quality_run(
            quality_run,
            converted_roots=[converted],
            apply=True,
        )

    assert target.read_text(encoding="utf-8") == "<html><body>old polish</body></html>"


def test_publish_latest_polish_rolls_back_batch_when_second_target_copy_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    converted = tmp_path / "converted"
    first_stage = _stage_pair(converted / "first")
    second_stage = _stage_pair(converted / "second")
    first_target = first_stage / POLISH_STAGE_NAME
    second_target = second_stage / POLISH_STAGE_NAME
    first_before = first_target.read_bytes()
    second_before = second_target.read_bytes()
    first_extra = converted / "first" / "first.html"
    first_extra.write_text("<html><body>extra</body></html>", encoding="utf-8")
    source_run = tmp_path / "quality" / "_converted_raw_source"
    _write_json(
        source_run / "manifest.json",
        {
            "articles": [
                {
                    "article_id": "first",
                    "raw_stage_path": str(first_stage / RAW_STAGE_NAME),
                    "source_polish_path": str(first_target),
                },
                {
                    "article_id": "second",
                    "raw_stage_path": str(second_stage / RAW_STAGE_NAME),
                    "source_polish_path": str(second_target),
                },
            ]
        },
    )
    quality_run = tmp_path / "quality"
    _write_json(
        quality_run / "manifest.json",
        {
            "source_run_dir": str(source_run),
            "articles": [{"article": "first"}, {"article": "second"}],
        },
    )
    for article_id, body in (("first", "new first"), ("second", "new second")):
        audited = quality_run / "audit_tree" / article_id / POLISH_STAGE_NAME
        audited.parent.mkdir(parents=True)
        audited.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    assert _seal_quality_run(quality_run)["status"] == "completed"
    original_copy = stage_contract_module._copy_file_atomic
    failed = False

    def fail_second_target_once(source: Path, target: Path) -> None:
        nonlocal failed
        if (
            not failed
            and target.resolve(strict=False) == second_target.resolve(strict=False)
            and source.name.startswith("000002.")
        ):
            failed = True
            raise OSError("simulated second target failure")
        original_copy(source, target)

    monkeypatch.setattr(
        stage_contract_module,
        "_copy_file_atomic",
        fail_second_target_once,
    )

    with pytest.raises(OSError, match="simulated second target failure"):
        publish_latest_polish_from_quality_run(
            quality_run,
            converted_roots=[converted],
            apply=True,
            prune_extra_html=True,
        )

    assert failed
    assert first_target.read_bytes() == first_before
    assert second_target.read_bytes() == second_before
    assert first_extra.is_file()
    assert list(quality_run.glob(".quality_publish_*")) == []
