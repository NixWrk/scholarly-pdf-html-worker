import json
from pathlib import Path

import pytest

import pdf_html_polish.html_stages as html_stages_module
from pdf_html_polish.html_stages import (
    HTML_STAGE_DIR_NAME,
    LEGACY_HTML_STAGE_DIR_NAME,
    POLISH_STAGE_NAME,
    RAW_CONVERSION_MANIFEST_NAME,
    RAW_STAGE_NAME,
    RawConversionValidator,
    article_dir_from_html_stage,
    article_name_from_html_stage,
    is_html_stage_path,
    require_current_raw_conversions,
    write_raw_conversion_manifest,
)


VALID_RAW_HTML = "<html><body><p>Raw article.</p></body></html>"


def test_html_stage_constants_and_article_helpers() -> None:
    stage_path = Path("root") / "Article Name" / HTML_STAGE_DIR_NAME / RAW_STAGE_NAME
    flat_path = Path("root") / "Article Name" / POLISH_STAGE_NAME

    assert RAW_STAGE_NAME == "01.en.raw.html"
    assert POLISH_STAGE_NAME == "02.en.polish.html"
    assert HTML_STAGE_DIR_NAME == "_pdf_html_polish_stages"
    assert is_html_stage_path(stage_path)
    assert is_html_stage_path(Path("root") / "Article Name" / LEGACY_HTML_STAGE_DIR_NAME / RAW_STAGE_NAME)
    assert not is_html_stage_path(flat_path)
    assert article_dir_from_html_stage(stage_path) == Path("root") / "Article Name"
    assert article_name_from_html_stage(stage_path) == "Article Name"
    assert article_dir_from_html_stage(flat_path) == Path("root") / "Article Name"


def _raw_fixture(
    tmp_path: Path,
    article: str,
    *,
    source_pdf: Path | None = None,
) -> tuple[Path, Path, Path]:
    stage_dir = tmp_path / "converted" / article / HTML_STAGE_DIR_NAME
    stage_dir.mkdir(parents=True)
    source_path = source_pdf or tmp_path / "sources" / f"{article}.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    if not source_path.exists():
        source_path.write_bytes(b"%PDF-1.4\nsource\n")
    raw_path = stage_dir / RAW_STAGE_NAME
    raw_path.write_text(VALID_RAW_HTML, encoding="utf-8")
    return stage_dir, source_path, raw_path


def test_raw_conversion_manifest_v2_validates_current_stage(tmp_path: Path) -> None:
    stage_dir, source_pdf, raw_path = _raw_fixture(tmp_path, "article")

    manifest_path = write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = RawConversionValidator([source_pdf]).validate(raw_path)

    assert manifest_path == stage_dir / RAW_CONVERSION_MANIFEST_NAME
    assert payload["schema_version"] == 2
    assert payload["article_name"] == "article"
    assert payload["source_pdf_path"] == str(source_pdf.resolve())
    assert payload["raw_html_name"] == RAW_STAGE_NAME
    assert validation.valid
    assert validation.source_pdf_path == source_pdf.resolve()
    assert require_current_raw_conversions(
        [raw_path],
        source_pdf_paths=[source_pdf],
    ) == [validation]


def test_raw_conversion_validator_rejects_missing_and_tampered_stage(tmp_path: Path) -> None:
    stage_dir, source_pdf, raw_path = _raw_fixture(tmp_path, "article")
    manifest_path = write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )
    manifest_path.unlink()

    missing = RawConversionValidator().validate(raw_path)
    assert not missing.valid
    assert missing.reason == "manifest_missing"

    write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )
    raw_path.write_text("<html><body><p>Tampered.</p></body></html>", encoding="utf-8")
    tampered = RawConversionValidator().validate(raw_path)
    assert not tampered.valid
    assert tampered.reason == "raw_fingerprint_mismatch"


def test_raw_conversion_validator_rejects_changed_source_and_malformed_raw(tmp_path: Path) -> None:
    stage_dir, source_pdf, raw_path = _raw_fixture(tmp_path, "article")
    write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )
    source_pdf.write_bytes(b"%PDF-1.4\nchanged source\n")
    changed_source = RawConversionValidator().validate(raw_path)
    assert not changed_source.valid
    assert changed_source.reason == "source_fingerprint_mismatch"

    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )
    raw_path.write_text("<html><body>truncated", encoding="utf-8")
    malformed = RawConversionValidator().validate(raw_path)
    assert not malformed.valid
    assert malformed.reason == "raw_html_malformed"


def test_manifest_writer_rejects_malformed_raw_without_publication(tmp_path: Path) -> None:
    stage_dir, source_pdf, raw_path = _raw_fixture(tmp_path, "article")
    raw_path.write_text("<html><body>truncated", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed"):
        write_raw_conversion_manifest(
            stage_dir,
            source_pdf=source_pdf,
            raw_stage_path=raw_path,
        )

    assert not (stage_dir / RAW_CONVERSION_MANIFEST_NAME).exists()


def test_interrupted_manifest_publication_invalidates_previous_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_dir, source_pdf, raw_path = _raw_fixture(tmp_path, "article")
    manifest_path = write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )
    raw_path.write_text("<html><body><p>Replacement.</p></body></html>", encoding="utf-8")

    def fail_atomic_write(_path: Path, _payload: object) -> None:
        raise OSError("simulated interrupted publication")

    monkeypatch.setattr(html_stages_module, "write_json_atomic", fail_atomic_write)
    with pytest.raises(OSError, match="interrupted publication"):
        write_raw_conversion_manifest(
            stage_dir,
            source_pdf=source_pdf,
            raw_stage_path=raw_path,
        )

    assert not manifest_path.exists()


def test_legacy_manifest_requires_unique_explicit_source_scope(tmp_path: Path) -> None:
    stage_dir, source_pdf, raw_path = _raw_fixture(tmp_path, "article")
    manifest_path = write_raw_conversion_manifest(
        stage_dir,
        source_pdf=source_pdf,
        raw_stage_path=raw_path,
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    payload.pop("article_name")
    payload.pop("source_pdf_path")
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    unscoped = RawConversionValidator().validate(raw_path)
    scoped = RawConversionValidator([source_pdf]).validate(raw_path)
    duplicate_source = tmp_path / "duplicate" / source_pdf.name
    duplicate_source.parent.mkdir()
    duplicate_source.write_bytes(source_pdf.read_bytes())
    ambiguous = RawConversionValidator([source_pdf, duplicate_source]).validate(raw_path)

    assert unscoped.reason == "legacy_manifest_requires_source_scope"
    assert scoped.valid
    assert ambiguous.reason == "legacy_source_ambiguous"


def test_require_current_raw_conversions_rejects_mixed_tree(tmp_path: Path) -> None:
    first_dir, first_source, first_raw = _raw_fixture(tmp_path, "first")
    second_dir, second_source, second_raw = _raw_fixture(tmp_path, "second")
    write_raw_conversion_manifest(first_dir, source_pdf=first_source, raw_stage_path=first_raw)
    write_raw_conversion_manifest(second_dir, source_pdf=second_source, raw_stage_path=second_raw)
    second_raw.write_text("<html><body><p>Tampered.</p></body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid=1 total=2"):
        require_current_raw_conversions([first_raw, second_raw])


def test_require_current_raw_conversions_rejects_duplicate_source_ownership(tmp_path: Path) -> None:
    shared_source = tmp_path / "sources" / "shared.pdf"
    first_dir, _source, first_raw = _raw_fixture(
        tmp_path,
        "first",
        source_pdf=shared_source,
    )
    second_dir, _source, second_raw = _raw_fixture(
        tmp_path,
        "second",
        source_pdf=shared_source,
    )
    write_raw_conversion_manifest(first_dir, source_pdf=shared_source, raw_stage_path=first_raw)
    write_raw_conversion_manifest(second_dir, source_pdf=shared_source, raw_stage_path=second_raw)

    with pytest.raises(RuntimeError, match="ownership is ambiguous"):
        require_current_raw_conversions([first_raw, second_raw])


def test_require_current_raw_conversions_rejects_missing_requested_source(tmp_path: Path) -> None:
    stage_dir, source_pdf, raw_path = _raw_fixture(tmp_path, "first")
    missing_source = tmp_path / "sources" / "second.pdf"
    missing_source.write_bytes(b"%PDF-1.4\nsecond\n")
    write_raw_conversion_manifest(stage_dir, source_pdf=source_pdf, raw_stage_path=raw_path)

    with pytest.raises(RuntimeError, match="have no current raw conversion"):
        require_current_raw_conversions(
            [raw_path],
            source_pdf_paths=[source_pdf, missing_source],
        )
