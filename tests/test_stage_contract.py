from __future__ import annotations

import json
from pathlib import Path

import pytest

import pdf_html_polish.atomic_io as atomic_io_module
from pdf_html_polish.html_stages import (
    POLISH_STAGE_NAME,
    RAW_CONVERSION_MANIFEST_NAME,
    RAW_STAGE_NAME,
    write_raw_conversion_manifest,
)
from pdf_html_polish.stage_contract import (
    publish_latest_polish_from_quality_run,
    verify_stage_contract,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    (stage_dir / RAW_STAGE_NAME).write_text(
        "<html><body>tampered raw</body></html>",
        encoding="utf-8",
    )

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
    audited.write_text("<html>new</html>", encoding="utf-8")

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
    audited.write_text("<html>new</html>", encoding="utf-8")

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
    audited = quality_run / "audit_tree" / "first" / POLISH_STAGE_NAME
    audited.parent.mkdir(parents=True)
    audited.write_text("<html>new first</html>", encoding="utf-8")

    report = publish_latest_polish_from_quality_run(
        quality_run,
        converted_roots=[converted],
        apply=True,
    )

    assert report["published_count"] == 0
    assert report["missing_count"] == 1
    assert report["stage_contract_status"] == "fail"
    assert report["records"][0]["status"] == "blocked_by_preflight"
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
    audited.write_text("<html>new</html>", encoding="utf-8")

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
