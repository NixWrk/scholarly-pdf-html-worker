from __future__ import annotations

from pathlib import Path

import pytest

from pdf_html_polish.output_state import detect_existing_results, normalize_source_path
from pdf_html_polish.result_state import (
    RESULT_MANIFEST_NAME,
    completed_result_is_current,
    invalidate_completed_result,
    publish_completed_result,
)
from pdf_html_polish.staging import FILENAME_MAP_NAME, _make_short_base_name


def _write_filename_map(output_dir: Path, *, source_pdf: Path, alias_base: str) -> None:
    (output_dir / FILENAME_MAP_NAME).write_text(
        "\n".join(
            [
                "source_pdf_path,alias_pdf_path,source_base_len,alias_base_len,was_shortened,materialization",
                f"{source_pdf},{output_dir / '_stage' / f'{alias_base}.pdf'},120,{len(alias_base)},yes,copy",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_detect_existing_results_does_not_reuse_hash_alias_owned_by_other_source(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    source_a_dir = tmp_path / "storage_a"
    source_b_dir = tmp_path / "storage_b"
    source_a_dir.mkdir()
    source_b_dir.mkdir()
    stem = "Same long Zotero title with distinct PDFs and a shared visible filename"
    source_a = source_a_dir / f"{stem}.pdf"
    source_b = source_b_dir / f"{stem}.pdf"
    source_a.write_bytes(b"%PDF-1.4\nsource-a\n")
    source_b.write_bytes(b"%PDF-1.4\nsource-b\n")
    alias_base = _make_short_base_name(stem, 48)
    article_dir = output_dir / alias_base
    article_dir.mkdir()
    artifact_path = article_dir / f"{alias_base}.html"
    artifact_path.write_text(
        "<html><body>source a</body></html>",
        encoding="utf-8",
    )
    _write_filename_map(output_dir, source_pdf=source_a, alias_base=alias_base)
    publish_completed_result(
        source_pdf_path=source_a,
        artifact_path=artifact_path,
        result_kind="polished_html",
    )

    existing = detect_existing_results(output_dir, [source_a, source_b], artifact_extension=".html")

    assert normalize_source_path(source_a) in existing
    assert normalize_source_path(source_b) not in existing


def test_detect_existing_results_rejects_artifact_without_completion_manifest(
    tmp_path: Path,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    output_dir = tmp_path / "out"
    article_dir = output_dir / "paper"
    article_dir.mkdir(parents=True)
    artifact_path = article_dir / "paper.html"
    artifact_path.write_text(
        "<html><body>uncommitted</body></html>",
        encoding="utf-8",
    )

    existing = detect_existing_results(
        output_dir,
        [source_pdf],
        artifact_extension=".html",
    )

    assert existing == set()
    assert not (article_dir / RESULT_MANIFEST_NAME).exists()


def test_completed_result_rejects_source_pdf_change(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\noriginal\n")
    article_dir = tmp_path / "out" / "paper"
    article_dir.mkdir(parents=True)
    artifact_path = article_dir / "paper.html"
    artifact_path.write_text("<html><body>complete</body></html>", encoding="utf-8")
    publish_completed_result(
        source_pdf_path=source_pdf,
        artifact_path=artifact_path,
        result_kind="polished_html",
    )

    source_pdf.write_bytes(b"%PDF-1.4\nchanged source\n")

    assert not completed_result_is_current(source_pdf, artifact_path)
    assert detect_existing_results(
        article_dir.parent,
        [source_pdf],
        artifact_extension=".html",
    ) == set()


def test_completed_result_rejects_artifact_change(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    article_dir = tmp_path / "out" / "paper"
    article_dir.mkdir(parents=True)
    artifact_path = article_dir / "paper.html"
    artifact_path.write_text("<html><body>complete</body></html>", encoding="utf-8")
    publish_completed_result(
        source_pdf_path=source_pdf,
        artifact_path=artifact_path,
        result_kind="polished_html",
    )

    artifact_path.write_text("<html><body>truncated", encoding="utf-8")

    assert not completed_result_is_current(source_pdf, artifact_path)
    assert detect_existing_results(
        article_dir.parent,
        [source_pdf],
        artifact_extension=".html",
    ) == set()


def test_publish_completed_result_rejects_malformed_html(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    article_dir = tmp_path / "out" / "paper"
    article_dir.mkdir(parents=True)
    artifact_path = article_dir / "paper.html"
    artifact_path.write_text(
        "<html><body>crossed close tags</html></body>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="empty, malformed, or unstable"):
        publish_completed_result(
            source_pdf_path=source_pdf,
            artifact_path=artifact_path,
            result_kind="polished_html",
        )

    assert not (article_dir / RESULT_MANIFEST_NAME).exists()


def test_invalidate_completed_result_keeps_artifact_but_disables_skip(
    tmp_path: Path,
) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nsource\n")
    article_dir = tmp_path / "out" / "paper"
    article_dir.mkdir(parents=True)
    artifact_path = article_dir / "paper.html"
    artifact_path.write_text("<html><body>complete</body></html>", encoding="utf-8")
    manifest_path = publish_completed_result(
        source_pdf_path=source_pdf,
        artifact_path=artifact_path,
        result_kind="polished_html",
    )
    assert completed_result_is_current(source_pdf, artifact_path)

    invalidate_completed_result(artifact_path)

    assert artifact_path.is_file()
    assert not manifest_path.exists()
    assert detect_existing_results(
        article_dir.parent,
        [source_pdf],
        artifact_extension=".html",
    ) == set()
