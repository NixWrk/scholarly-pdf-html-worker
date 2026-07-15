from pathlib import Path

import pytest

from pdf_html_polish.quality_loop.run_utils import (
    article_dir_from_stage,
    article_name_from_stage,
    artifact_hint,
    converted_article_id,
    json_object,
    load_json,
    norm_path,
    profile_value,
    slug,
    write_json,
)


def test_slug_normalizes_and_falls_back_to_article() -> None:
    assert slug(" ACME / Trial: 1 ", max_len=20) == "ACME_Trial_1"
    assert slug("... /// ...") == "article"
    assert slug("x" * 90) == "x" * 80


def test_json_helpers_round_trip_and_missing_default(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "data.json"

    write_json(path, {"title": "Zażółć", "items": [1, 2]})

    assert load_json(path) == {"title": "Zażółć", "items": [1, 2]}
    assert load_json(tmp_path / "missing.json", default={"ok": True}) == {"ok": True}
    with pytest.raises(FileNotFoundError):
        load_json(tmp_path / "missing.json")

    assert json_object({"ok": True}) == {"ok": True}
    assert json_object(None) == {}
    assert json_object(["not", "an", "object"]) == {}


def test_stage_path_helpers_handle_z2m_stage_layout(tmp_path: Path) -> None:
    article_dir = tmp_path / "library" / "ATTACH123" / "v1" / "article-title"
    stage_path = article_dir / "_z2m_stages" / "01.en.raw.html"

    assert article_dir_from_stage(stage_path) == article_dir
    assert article_name_from_stage(stage_path) == "article-title"
    assert artifact_hint(stage_path, depth=3) == str(Path("article-title") / "_z2m_stages" / "01.en.raw.html")


def test_converted_article_id_includes_library_attachment_and_version(tmp_path: Path) -> None:
    raw_path = (
        tmp_path
        / "Very Long Library Name"
        / "ATTACH-1234567890"
        / "2026 Version With Extra Words"
        / "Article: With Punctuation!"
        / "_z2m_stages"
        / "01.en.raw.html"
    )

    assert converted_article_id(raw_path) == (
        "Very_Long_Libr_ATTACH-123_2026_Version_With_Extr_Article_With_Punctuation"
    )


def test_converted_article_id_disambiguates_long_article_names_with_shared_prefix(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "review_runs" / "full_pdf_to_polish" / "root"
    first = (
        parent
        / "Oswalt et al. - 2021 - Multi-electrode stimulation evokes consist_3a3f09be"
        / "_pdf_html_polish_stages"
        / "01.en.raw.html"
    )
    second = (
        parent
        / "Oswalt et al. - 2021 - Multi-electrode stimulation evokes consist_3a3f09_2"
        / "_pdf_html_polish_stages"
        / "01.en.raw.html"
    )

    first_id = converted_article_id(first)
    second_id = converted_article_id(second)

    assert first_id != second_id
    assert "_Oswalt_et_al" in first_id
    assert "_Oswalt_et_al" in second_id
    assert len(first_id.rsplit("_", 1)[-1]) == 8
    assert len(second_id.rsplit("_", 1)[-1]) == 8


def test_profile_and_norm_path_helpers(tmp_path: Path) -> None:
    assert profile_value({"status": "ready"}, "status") == "ready"
    assert profile_value({"status": ""}, "status", default="unknown") == "unknown"
    assert profile_value({}, "status", default="unknown") == "unknown"
    assert norm_path("") == ""
    assert norm_path(tmp_path / "not-created") == str((tmp_path / "not-created").resolve(strict=False))
