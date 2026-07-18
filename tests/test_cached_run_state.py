from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from pdf_html_polish.quality_loop import cached_run_state
from pdf_html_polish.quality_loop.cached_run_state import (
    CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
    CachedRunSourceError,
    stage_cached_repolish_source_snapshot,
    revalidate_cached_repolish_source_unchanged,
    validate_cached_repolish_source,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _fingerprint(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def _write_source(
    root: Path, article_ids: tuple[str, ...] = ("doc",)
) -> dict[str, object]:
    root = root.resolve(strict=False)
    raw_dir = root / "raw_cache"
    profile_dir = root / "profiles"
    raw_dir.mkdir(parents=True)
    profile_dir.mkdir(parents=True)
    articles: list[dict[str, object]] = []
    for index, article_id in enumerate(article_ids, start=1):
        raw_path = raw_dir / f"{article_id}.01.en.raw.html"
        profile_path = profile_dir / f"{article_id}.citation_profile.json"
        raw_path.write_text(
            f"<html><body><p>Stable source {article_id}.</p></body></html>",
            encoding="utf-8",
        )
        _write_json(
            profile_path,
            {"status": "ok", "style": "unknown", "confidence": "low"},
        )
        raw_bytes, raw_sha256 = _fingerprint(raw_path)
        profile_bytes, profile_sha256 = _fingerprint(profile_path)
        articles.append(
            {
                "index": index,
                "article_id": article_id,
                "article": article_id,
                "raw_cache_path": str(raw_path),
                "profile_path": str(profile_path),
                "raw_cache_bytes": raw_bytes,
                "raw_cache_sha256": raw_sha256,
                "profile_bytes": profile_bytes,
                "profile_sha256": profile_sha256,
                "profile_status": "ok",
                "citation_style": "unknown",
                "citation_confidence": "low",
            }
        )
    manifest: dict[str, object] = {
        "source_snapshot_schema_version": CACHED_REPOLISH_SOURCE_SCHEMA_VERSION,
        "source_kind": "converted_raw_cache",
        "out_dir": str(root),
        "raw_count": len(articles),
        "article_count": len(articles),
        "raw_cache_dir": str(raw_dir),
        "profile_dir": str(profile_dir),
        "profile_status_counts": {"ok": len(articles)},
        "profile_style_counts": {"unknown:low": len(articles)},
        "articles": articles,
    }
    _write_json(root / "manifest.json", manifest)
    return manifest


def test_validate_cached_repolish_source_accepts_exact_committed_tree(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write_source(source, ("alpha", "beta"))

    validation = validate_cached_repolish_source(source)

    assert validation.run_dir == source.resolve()
    assert [article.article_id for article in validation.articles] == ["alpha", "beta"]
    assert validation.manifest["raw_count"] == 2
    assert len(validation.manifest_fingerprint.sha256) == 64


@pytest.mark.parametrize(
    ("manifest_change", "error"),
    [
        ({"source_kind": "cached_raw_repolish"}, "source_kind_not_converted_raw_cache"),
        (
            {"source_snapshot_schema_version": 999},
            "source_snapshot_schema_version_invalid",
        ),
        (
            {"source_snapshot_schema_version": True},
            "source_snapshot_schema_version_invalid",
        ),
        ({"raw_count": 2}, "raw_count_mismatch"),
        ({"article_count": 2}, "article_count_mismatch"),
    ],
)
def test_validate_cached_repolish_source_rejects_invalid_manifest_contract(
    tmp_path: Path,
    manifest_change: dict[str, object],
    error: str,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    manifest.update(manifest_change)
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match=error):
        validate_cached_repolish_source(source)


def test_validate_cached_repolish_source_requires_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "raw_cache").mkdir(parents=True)
    (source / "profiles").mkdir()

    with pytest.raises(
        CachedRunSourceError, match="manifest_missing_empty_symlink_or_unstable"
    ):
        validate_cached_repolish_source(source)


@pytest.mark.parametrize(
    ("directory", "name", "error"),
    [
        ("raw_cache", "extra.01.en.raw.html", "raw_file_set_mismatch"),
        ("profiles", "extra.citation_profile.json", "profile_file_set_mismatch"),
    ],
)
def test_validate_cached_repolish_source_rejects_extra_files(
    tmp_path: Path,
    directory: str,
    name: str,
    error: str,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    (source / directory / name).write_text("extra", encoding="utf-8")

    with pytest.raises(CachedRunSourceError, match=error):
        validate_cached_repolish_source(source)


@pytest.mark.parametrize(
    ("relative_path", "error"),
    [
        (Path("raw_cache/doc.01.en.raw.html"), "raw_file_set_mismatch"),
        (Path("profiles/doc.citation_profile.json"), "profile_file_set_mismatch"),
    ],
)
def test_validate_cached_repolish_source_rejects_missing_files(
    tmp_path: Path,
    relative_path: Path,
    error: str,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    (source / relative_path).unlink()

    with pytest.raises(CachedRunSourceError, match=error):
        validate_cached_repolish_source(source)


@pytest.mark.parametrize(
    ("relative_path", "replacement", "error"),
    [
        (
            Path("raw_cache/doc.01.en.raw.html"),
            b"<html><body><p>Tampered raw.</p></body></html>",
            "raw_fingerprint_mismatch:doc",
        ),
        (
            Path("profiles/doc.citation_profile.json"),
            b'{"status":"tampered"}\n',
            "profile_fingerprint_mismatch:doc",
        ),
    ],
)
def test_validate_cached_repolish_source_rejects_tampered_artifacts(
    tmp_path: Path,
    relative_path: Path,
    replacement: bytes,
    error: str,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    (source / relative_path).write_bytes(replacement)

    with pytest.raises(CachedRunSourceError, match=error):
        validate_cached_repolish_source(source)


@pytest.mark.parametrize(
    ("relative_path", "replacement", "error"),
    [
        (Path("raw_cache/doc.01.en.raw.html"), b"\xff\xfe", "raw_invalid_utf8:doc"),
        (Path("raw_cache/doc.01.en.raw.html"), b"plain text", "raw_html_malformed:doc"),
        (
            Path("profiles/doc.citation_profile.json"),
            b"{broken",
            "profile_json_unreadable:doc",
        ),
    ],
)
def test_validate_cached_repolish_source_rejects_malformed_committed_artifacts(
    tmp_path: Path,
    relative_path: Path,
    replacement: bytes,
    error: str,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    path = source / relative_path
    path.write_bytes(replacement)
    size, sha256 = _fingerprint(path)
    article = manifest["articles"][0]
    assert isinstance(article, dict)
    if relative_path.parts[0] == "raw_cache":
        article["raw_cache_bytes"] = size
        article["raw_cache_sha256"] = sha256
    else:
        article["profile_bytes"] = size
        article["profile_sha256"] = sha256
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match=error):
        validate_cached_repolish_source(source)


def test_validate_cached_repolish_source_rejects_duplicate_article_id(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    article = manifest["articles"][0]
    assert isinstance(article, dict)
    manifest["articles"] = [article, dict(article, index=2)]
    manifest["raw_count"] = 2
    manifest["article_count"] = 2
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match="duplicate_article_id:doc"):
        validate_cached_repolish_source(source)


def test_validate_cached_repolish_source_rejects_manifest_path_escape(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    article = manifest["articles"][0]
    assert isinstance(article, dict)
    article["raw_cache_path"] = str((tmp_path / "outside.01.en.raw.html").resolve())
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match="raw_cache_path_mismatch:doc"):
        validate_cached_repolish_source(source)


def test_validate_cached_repolish_source_rejects_duplicate_manifest_key(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    manifest_path = source / "manifest.json"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        manifest_text.replace(
            '"source_kind": "converted_raw_cache",',
            '"source_kind": "converted_raw_cache",\n  "source_kind": "converted_raw_cache",',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CachedRunSourceError, match="manifest_json_unreadable"):
        validate_cached_repolish_source(source)


def test_validate_cached_repolish_source_rejects_duplicate_profile_key(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    profile_path = source / "profiles" / "doc.citation_profile.json"
    profile_text = profile_path.read_text(encoding="utf-8")
    profile_path.write_text(
        profile_text.replace(
            '"status": "ok",',
            '"status": "ok",\n  "status": "ok",',
            1,
        ),
        encoding="utf-8",
    )
    profile_bytes, profile_sha256 = _fingerprint(profile_path)
    article = manifest["articles"][0]
    assert isinstance(article, dict)
    article["profile_bytes"] = profile_bytes
    article["profile_sha256"] = profile_sha256
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match="profile_json_unreadable:doc"):
        validate_cached_repolish_source(source)


def test_validate_cached_repolish_source_requires_string_profile_contract(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    profile_path = source / "profiles" / "doc.citation_profile.json"
    _write_json(profile_path, {"style": "unknown", "confidence": "low"})
    profile_bytes, profile_sha256 = _fingerprint(profile_path)
    article = manifest["articles"][0]
    assert isinstance(article, dict)
    article["profile_bytes"] = profile_bytes
    article["profile_sha256"] = profile_sha256
    article["profile_status"] = "unknown"
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match="profile_status_invalid:doc"):
        validate_cached_repolish_source(source)


@pytest.mark.skipif(
    os.name != "nt", reason="case-insensitive path alias is Windows-specific"
)
def test_validate_cached_repolish_source_rejects_case_aliased_artifact_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write_source(source, ("Doc", "doc"))

    with pytest.raises(CachedRunSourceError, match="duplicate_artifact_path:doc"):
        validate_cached_repolish_source(source)


def test_stage_cached_repolish_source_snapshot_rejects_target_inside_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write_source(source)

    with pytest.raises(CachedRunSourceError, match="snapshot_path_inside_source"):
        stage_cached_repolish_source_snapshot(
            source,
            tmp_path / "staging",
            source / "nested_snapshot",
        )


@pytest.mark.parametrize("nested_path", ["staging", "published"])
def test_stage_cached_repolish_source_snapshot_rejects_overlapping_paths(
    tmp_path: Path,
    nested_path: str,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    outer = tmp_path / "snapshot-outer"
    inner = outer / "snapshot-inner"
    if nested_path == "published":
        staging = outer
        published = inner
    else:
        staging = inner
        published = outer

    with pytest.raises(CachedRunSourceError, match="snapshot_paths_overlap"):
        stage_cached_repolish_source_snapshot(
            source,
            staging,
            published,
        )

    assert not outer.exists()


def test_stage_cached_repolish_source_snapshot_rejects_source_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    raw_path = source / "raw_cache" / "doc.01.en.raw.html"
    real_read = cached_run_state.read_bytes_with_fingerprint
    raw_reads = 0

    def read_then_mutate(path: Path, *, reject_symlink: bool):
        nonlocal raw_reads
        if Path(path) == raw_path:
            raw_reads += 1
            if raw_reads == 2:
                raw_path.write_text(
                    "<html><body><p>Changed during snapshot.</p></body></html>",
                    encoding="utf-8",
                )
        return real_read(path, reject_symlink=reject_symlink)

    monkeypatch.setattr(
        cached_run_state, "read_bytes_with_fingerprint", read_then_mutate
    )
    staging = tmp_path / "staging"

    with pytest.raises(CachedRunSourceError, match="raw_changed_during_snapshot:doc"):
        stage_cached_repolish_source_snapshot(
            source,
            staging,
            tmp_path / "quality" / "_repolish_source_snapshot",
        )

    assert not staging.exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink support unavailable")
def test_validate_cached_repolish_source_rejects_symlinked_artifact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    raw_path = source / "raw_cache" / "doc.01.en.raw.html"
    outside = tmp_path / "outside.html"
    outside.write_bytes(raw_path.read_bytes())
    raw_path.unlink()
    try:
        raw_path.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(CachedRunSourceError, match="raw_file_set_mismatch|raw_invalid"):
        validate_cached_repolish_source(source)


def test_stage_cached_repolish_source_snapshot_rewrites_and_seals_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    original = _write_source(source, ("alpha", "beta"))
    staging = tmp_path / "staging"
    published = tmp_path / "quality" / "_repolish_source_snapshot"

    snapshot_manifest = stage_cached_repolish_source_snapshot(
        source,
        staging,
        published,
    )

    assert not published.exists()
    assert snapshot_manifest["out_dir"] == str(published.resolve(strict=False))
    assert snapshot_manifest["source_snapshot_origin"]["run_dir"] == str(
        source.resolve()
    )
    assert len(snapshot_manifest["source_snapshot_origin"]["manifest_sha256"]) == 64
    for article in snapshot_manifest["articles"]:
        assert (
            Path(article["raw_cache_path"]).parent
            == published.resolve(strict=False) / "raw_cache"
        )
        assert (
            Path(article["profile_path"]).parent
            == published.resolve(strict=False) / "profiles"
        )

    published.parent.mkdir(parents=True)
    staging.replace(published)
    validation = validate_cached_repolish_source(published)

    assert [article.article_id for article in validation.articles] == ["alpha", "beta"]
    assert (
        validation.manifest["source_snapshot_origin"]["manifest_sha256"]
        == hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()
    )
    assert (
        original["articles"][0]["raw_cache_path"]
        != validation.manifest["articles"][0]["raw_cache_path"]
    )


def test_stage_cached_repolish_source_snapshot_leaves_no_partial_stage_on_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    (source / "raw_cache" / "doc.01.en.raw.html").write_text(
        "tampered", encoding="utf-8"
    )
    staging = tmp_path / "staging"

    with pytest.raises(CachedRunSourceError, match="raw_fingerprint_mismatch:doc"):
        stage_cached_repolish_source_snapshot(
            source,
            staging,
            tmp_path / "quality" / "_repolish_source_snapshot",
        )

    assert not staging.exists()


@pytest.mark.parametrize(
    ("artifact", "error"),
    [
        ("manifest", "manifest_json_unreadable"),
        ("profile", "profile_json_unreadable:doc"),
    ],
)
def test_validate_cached_repolish_source_rejects_nonfinite_json_constants(
    tmp_path: Path,
    artifact: str,
    error: str,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    if artifact == "manifest":
        path = source / "manifest.json"
    else:
        path = source / "profiles" / "doc.citation_profile.json"
    path.write_text(
        path.read_text(encoding="utf-8").replace("{", '{"nonfinite": NaN,', 1),
        encoding="utf-8",
    )
    if artifact == "profile":
        profile_bytes, profile_sha256 = _fingerprint(path)
        article = manifest["articles"][0]
        assert isinstance(article, dict)
        article["profile_bytes"] = profile_bytes
        article["profile_sha256"] = profile_sha256
        _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match=error):
        validate_cached_repolish_source(source)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink support unavailable")
@pytest.mark.parametrize(
    ("link_kind", "error"),
    [
        ("staging", "snapshot_staging_already_exists"),
        ("published", "snapshot_target_already_exists"),
    ],
)
def test_stage_cached_repolish_source_snapshot_rejects_dangling_directory_symlink(
    tmp_path: Path,
    link_kind: str,
    error: str,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    dangling_target = tmp_path / f"{link_kind}-target"
    link = tmp_path / f"{link_kind}-link"
    try:
        link.symlink_to(dangling_target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    staging = link if link_kind == "staging" else tmp_path / "staging"
    published = link if link_kind == "published" else tmp_path / "quality" / "snapshot"

    with pytest.raises(CachedRunSourceError, match=error):
        stage_cached_repolish_source_snapshot(source, staging, published)

    assert not dangling_target.exists()
    if link_kind == "published":
        assert not staging.exists()


def test_revalidate_cached_repolish_source_rejects_consistent_manifest_rewrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    expected = validate_cached_repolish_source(source)
    raw_path = source / "raw_cache" / "doc.01.en.raw.html"
    raw_path.write_text(
        "<html><body><p>Consistently replaced source.</p></body></html>",
        encoding="utf-8",
    )
    raw_bytes, raw_sha256 = _fingerprint(raw_path)
    article = manifest["articles"][0]
    assert isinstance(article, dict)
    article["raw_cache_bytes"] = raw_bytes
    article["raw_cache_sha256"] = raw_sha256
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(
        CachedRunSourceError, match="manifest_changed_during_processing"
    ):
        revalidate_cached_repolish_source_unchanged(expected)


@pytest.mark.parametrize("extra_kind", ["file", "directory"])
def test_validate_cached_repolish_source_rejects_extra_top_level_entry(
    tmp_path: Path,
    extra_kind: str,
) -> None:
    source = tmp_path / "source"
    _write_source(source)
    extra = source / ("stale-report.json" if extra_kind == "file" else "polish")
    if extra_kind == "file":
        extra.write_text('{"stale": true}\n', encoding="utf-8")
    else:
        extra.mkdir()

    with pytest.raises(CachedRunSourceError, match="source_top_level_set_mismatch"):
        validate_cached_repolish_source(source)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("index", True, "article_index_invalid:doc"),
        ("profile_status_counts", {"ok": True}, "profile_status_counts_invalid"),
        ("profile_style_counts", {"unknown:low": True}, "profile_style_counts_invalid"),
    ],
)
def test_validate_cached_repolish_source_rejects_boolean_integer_aliases(
    tmp_path: Path,
    field: str,
    value: object,
    error: str,
) -> None:
    source = tmp_path / "source"
    manifest = _write_source(source)
    if field == "index":
        article = manifest["articles"][0]
        assert isinstance(article, dict)
        article[field] = value
    else:
        manifest[field] = value
    _write_json(source / "manifest.json", manifest)

    with pytest.raises(CachedRunSourceError, match=error):
        validate_cached_repolish_source(source)
