from __future__ import annotations

from pathlib import Path

import pytest

from pdf_html_polish import atomic_io
from pdf_html_polish.models import AttachmentRecord, ResolvedAttachment, StagedFile
from pdf_html_polish.staging import (
    FILENAME_MAP_NAME,
    _make_short_base_name,
    stage_resolved_pdfs,
    write_filename_map,
)


def _resolved(source_pdf: Path) -> ResolvedAttachment:
    return ResolvedAttachment(
        attachment=AttachmentRecord(
            item_id=1,
            attachment_key="direct_pdf_0001",
            parent_item_id=None,
            link_mode=None,
            path=str(source_pdf),
            content_type="application/pdf",
        ),
        source_pdf_path=source_pdf,
    )


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


def _seed_existing_article(output_dir: Path, *, source_pdf: Path, alias_base: str) -> None:
    article_dir = output_dir / alias_base
    article_dir.mkdir(parents=True)
    (article_dir / f"{alias_base}.html").write_text("<html></html>", encoding="utf-8")
    _write_filename_map(output_dir, source_pdf=source_pdf, alias_base=alias_base)


def test_stage_resolved_pdfs_avoids_existing_alias_owned_by_other_source(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    stem = "Same long Zotero title with distinct PDFs and a shared visible filename"
    source_a = tmp_path / "storage_a" / f"{stem}.pdf"
    source_b = tmp_path / "storage_b" / f"{stem}.pdf"
    source_a.parent.mkdir()
    source_b.parent.mkdir()
    source_a.write_bytes(b"%PDF-1.4\nsource-a\n")
    source_b.write_bytes(b"%PDF-1.4\nsource-b\n")
    alias_base = _make_short_base_name(stem, 48)
    _seed_existing_article(output_dir, source_pdf=source_a, alias_base=alias_base)

    result = stage_resolved_pdfs(
        [_resolved(source_b)],
        output_dir,
        requested_max_base_len=48,
        temp_root=tmp_path / "runtime",
    )

    staged = result.staged_files[0]
    assert staged.alias_base_name != alias_base
    assert staged.alias_base_name.endswith("_2")
    assert staged.alias_pdf_path.is_file()


def test_stage_resolved_pdfs_keeps_existing_alias_owned_by_same_source(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    stem = "Same long Zotero title with an already mapped source PDF"
    source_pdf = tmp_path / "storage_a" / f"{stem}.pdf"
    source_pdf.parent.mkdir()
    source_pdf.write_bytes(b"%PDF-1.4\nsource-a\n")
    alias_base = _make_short_base_name(stem, 48)
    _seed_existing_article(output_dir, source_pdf=source_pdf, alias_base=alias_base)

    result = stage_resolved_pdfs(
        [_resolved(source_pdf)],
        output_dir,
        requested_max_base_len=48,
        temp_root=tmp_path / "runtime",
    )

    assert result.staged_files[0].alias_base_name == alias_base


def test_write_filename_map_preserves_previous_map_when_publication_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    map_path = output_dir / FILENAME_MAP_NAME
    previous = "source_pdf_path,alias_pdf_path\nprevious.pdf,previous_alias.pdf\n"
    map_path.write_text(previous, encoding="utf-8")
    staged = StagedFile(
        source_pdf_path=tmp_path / "new.pdf",
        alias_pdf_path=tmp_path / "new_alias.pdf",
        alias_base_name="new_alias",
        source_base_len=3,
        alias_base_len=9,
        was_shortened=True,
        materialization="copy",
    )

    def fail_replace(_temporary: Path, _target: Path) -> None:
        raise OSError("simulated map publication failure")

    monkeypatch.setattr(atomic_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated map publication failure"):
        write_filename_map(output_dir, [staged])

    assert map_path.read_text(encoding="utf-8") == previous
    assert not list(output_dir.glob(f".{FILENAME_MAP_NAME}.*.tmp"))
