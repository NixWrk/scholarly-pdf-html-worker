from pathlib import Path

from pdf_html_polish.quality_loop.source_pdf import (
    attachment_keys_from_article,
    article_source_pdf_candidates,
    collect_pdf_path_strings,
    existing_path_candidates,
    normalize_pdf_title_text,
    path_text_variants,
)


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


def test_source_pdf_title_normalization_keeps_cyrillic_words() -> None:
    assert (
        normalize_pdf_title_text(
            "\u0418\u0432\u0430\u043d\u043e\u0432 - 2024 - "
            "\u041a\u0430\u0447\u0435\u0441\u0442\u0432\u043e "
            "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f PDF"
        )
        == (
            "\u0438\u0432\u0430\u043d\u043e\u0432 2024 "
            "\u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e "
            "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f pdf"
        )
    )
    assert normalize_pdf_title_text("\u041a\u0438\u0457\u0432 PDF") == "\u043a\u0438\u0457\u0432 pdf"


def test_collect_pdf_path_strings_does_not_duplicate_keyed_pdf_values() -> None:
    data = {
        "source_pdf": "D:/papers/source.pdf",
        "nested": [{"overlay_source_pdf": "D:/papers/overlay.pdf?download=1"}],
    }

    assert collect_pdf_path_strings(data) == [
        "D:/papers/source.pdf",
        "D:/papers/overlay.pdf?download=1",
    ]


def test_attachment_keys_skip_numeric_article_identifiers() -> None:
    assert attachment_keys_from_article(
        "Zotero_Elvis_D_KEY12345_571527_Article",
        {"zotero_attachment_key": "ABC12345"},
    ) == ["KEY12345", "ABC12345"]


def test_existing_path_candidates_keeps_path_repair_in_source_pdf_module(tmp_path: Path) -> None:
    pdf_path = tmp_path / "\u041a\u0438\u0457\u0432.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    mojibake = str(pdf_path).encode("utf-8").decode("cp1251")

    assert path_text_variants(mojibake)[-1] == str(pdf_path)
    assert existing_path_candidates(mojibake, repo_root=tmp_path) == [
        pdf_path.resolve(strict=False)
    ]


def test_source_pdf_candidates_fall_back_to_zotero_cyrillic_title_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    zotero_root = tmp_path / "Zotero_Elvis_Data"
    storage_dir = zotero_root / "storage" / "RUSPDF42"
    storage_dir.mkdir(parents=True)
    pdf_path = (
        storage_dir
        / (
            "\u0418\u0432\u0430\u043d\u043e\u0432 - 2024 - "
            "\u041a\u0430\u0447\u0435\u0441\u0442\u0432\u043e "
            "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f "
            "\u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0445 "
            "\u0434\u0430\u043d\u043d\u044b\u0445 PDF.pdf"
        )
    )
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("ZOTERO_PATH_PREFIX_MAP", f"/zotero_roots/test_zotero={zotero_root}")

    candidates = article_source_pdf_candidates(
        tmp_path / "run",
        (
            "Zotero_Elvis_D_C37DAWJT_2754214_17806620590000_"
            "\u041a\u0430\u0447\u0435\u0441\u0442\u0432\u043e_"
            "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f_"
            "\u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0445_"
            "\u0434\u0430\u043d\u043d\u044b\u0445_PDF"
        ),
        {},
        {},
        repo_root=tmp_path,
        raw_stage="01.en.raw.html",
        polish_stage="02.en.polish.html",
    )

    assert candidates[0]["path"] == str(pdf_path.resolve(strict=False))
    assert candidates[0]["source"] == "zotero_storage.title_match"
    assert candidates[0]["exists"] is True
