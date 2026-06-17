from pathlib import Path

from pdf_html_polish.quality_loop.source_pdf import article_source_pdf_candidates


def test_source_pdf_candidates_fall_back_to_zotero_title_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    zotero_root = tmp_path / "Zotero_Elvis_Data"
    storage_dir = zotero_root / "storage" / "LQQBDBNU"
    storage_dir.mkdir(parents=True)
    pdf_path = (
        storage_dir
        / "Example - 2024 - Custom Zotero Fallback Mobility Paper With Unique Nebula Marker.pdf"
    )
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("ZOTERO_PATH_PREFIX_MAP", f"/zotero_roots/test_zotero={zotero_root}")

    candidates = article_source_pdf_candidates(
        tmp_path / "run",
        "Zotero_Elvis_D_C37DAWJT_2754214_17806620590000_"
        "Custom_Zotero_Fallback_Mobility_Paper_With_Unique_Nebula_Marker",
        {},
        {},
        repo_root=tmp_path,
        raw_stage="01.en.raw.html",
        polish_stage="02.en.polish.html",
    )

    assert candidates[0]["path"] == str(pdf_path.resolve(strict=False))
    assert candidates[0]["source"] == "zotero_storage.title_match"
    assert candidates[0]["exists"] is True
