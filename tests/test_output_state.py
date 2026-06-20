from __future__ import annotations

from pathlib import Path

from pdf_html_polish.output_state import detect_existing_results, normalize_source_path
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
    (article_dir / f"{alias_base}.html").write_text("<html></html>", encoding="utf-8")
    _write_filename_map(output_dir, source_pdf=source_a, alias_base=alias_base)

    existing = detect_existing_results(output_dir, [source_a, source_b], artifact_extension=".html")

    assert normalize_source_path(source_a) in existing
    assert normalize_source_path(source_b) not in existing
