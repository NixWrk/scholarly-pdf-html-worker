import importlib.util
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repolish_en_from_raw.py"


def _make_temp_dir() -> Path:
    path = Path(".tmp_local2") / f"test_repolish_en_from_raw_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_module():
    spec = importlib.util.spec_from_file_location("repolish_en_from_raw", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repolish_file_writes_polish_stage_and_inlines_article_images() -> None:
    repolish = _load_module()
    tmp_path = _make_temp_dir()
    try:
        article_dir = tmp_path / "Article sample"
        stage_dir = article_dir / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (article_dir / "fig1.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        raw_path = stage_dir / "01.en.raw.html"
        raw_path.write_text(
            '<html><body><p>See Fig. 1.</p><p><img src="fig1.png"></p><p>Figure 1. Caption.</p></body></html>',
            encoding="utf-8",
        )

        result = repolish.repolish_file(raw_path)

        polish_path = stage_dir / "02.en.polish.html"
        assert result.changed is True
        assert result.inlined_images == ["fig1.png"]
        assert result.missing_images == []
        polished = polish_path.read_text(encoding="utf-8")
        assert "data:image/png;base64," in polished
        assert 'data-z2m-src="fig1.png"' in polished
        assert '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">' in polished
        assert 'href="#fig-1"' in polished
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_repolish_file_restores_images_from_source_run_cache() -> None:
    repolish = _load_module()
    tmp_path = _make_temp_dir()
    try:
        article_dir = tmp_path / "Article sample"
        stage_dir = article_dir / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        raw_path.write_text(
            '<html><body><p><img src="fig1.png"></p></body></html>',
            encoding="utf-8",
        )

        source_polish = tmp_path / "source_run" / "polish" / "Article sample.02.en.polish.html"
        source_polish.parent.mkdir(parents=True)
        source_polish.write_text(
            '<html><body><p><img data-z2m-src="fig1.png" src="data:image/png;base64,AAAA"></p></body></html>',
            encoding="utf-8",
        )

        result = repolish.repolish_file(raw_path, image_cache_source_run=tmp_path / "source_run")

        polished = (stage_dir / "02.en.polish.html").read_text(encoding="utf-8")
        assert result.restored_images == 1
        assert result.image_cache_source == str(source_polish.resolve(strict=False))
        assert result.inlined_images == []
        assert result.missing_images == []
        assert 'data-z2m-src="fig1.png"' in polished
        assert 'src="data:image/png;base64,AAAA"' in polished
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_repolish_cli_reports_restored_images_from_source_run_cache() -> None:
    repolish = _load_module()
    tmp_path = _make_temp_dir()
    try:
        article_dir = tmp_path / "Article sample"
        stage_dir = article_dir / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text(
            '<html><body><p><img src="fig1.png"></p></body></html>',
            encoding="utf-8",
        )
        source_polish = tmp_path / "source_run" / "polish" / "Article sample.02.en.polish.html"
        source_polish.parent.mkdir(parents=True)
        source_polish.write_text(
            '<html><body><p><img data-z2m-src="fig1.png" src="data:image/png;base64,AAAA"></p></body></html>',
            encoding="utf-8",
        )
        report_path = tmp_path / "report.json"

        exit_code = repolish.main(
            [
                "--roots",
                str(tmp_path),
                "--out-report",
                str(report_path),
                "--image-cache-source-run",
                str(tmp_path / "source_run"),
                "--fail-on-missing-images",
            ]
        )

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert exit_code == 0
        assert report["restored_image_count"] == 1
        assert report["missing_image_count"] == 0
        assert report["articles"][0]["restored_images"] == 1
        assert report["articles"][0]["image_cache_source"] == str(source_polish.resolve(strict=False))
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_repolish_cli_writes_json_report() -> None:
    repolish = _load_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text("<html><body><p>Plain.</p></body></html>", encoding="utf-8")
        report_path = tmp_path / "report.json"

        exit_code = repolish.main(["--roots", str(tmp_path), "--out-report", str(report_path)])

        assert exit_code == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["article_count"] == 1
        assert report["changed_count"] == 1
        assert (stage_dir / "02.en.polish.html").is_file()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_repolish_cli_can_select_ru_polish_policy_with_en_captions() -> None:
    repolish = _load_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text(
            "<html><body>"
            '<span id="page-33-0"></span>'
            '<p>Параллакс возникает <a href="#page-33-0">см. с. 34</a>.</p>'
            "</body></html>",
            encoding="utf-8",
        )
        report_path = tmp_path / "report.json"

        exit_code = repolish.main(
            [
                "--roots",
                str(tmp_path),
                "--out-report",
                str(report_path),
                "--table-caption-language",
                "en",
                "--polish-language",
                "ru",
            ]
        )

        assert exit_code == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["table_caption_language"] == "en"
        assert report["polish_language"] == "ru"
        polished = (stage_dir / "02.en.polish.html").read_text(encoding="utf-8")
        assert 'href="#page-33-0"' not in polished
        assert "см. с. 34" in polished
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_repolish_cli_auto_policy_selects_ru_per_document() -> None:
    repolish = _load_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        ru_body = "РџР°СЂР°Р»Р»Р°РєСЃ РІРѕР·РЅРёРєР°РµС‚ РІ СЌС‚РѕРј СЂР°Р·РґРµР»Рµ. " * 90
        (stage_dir / "01.en.raw.html").write_text(
            "<html><body>"
            '<span id="page-33-0"></span>'
            f"<p>{ru_body}</p>"
            '<p>РџР°СЂР°Р»Р»Р°РєСЃ <a href="#page-33-0">СЃРј. СЃ. 34</a>.</p>'
            "</body></html>",
            encoding="utf-8",
        )
        mojibake_ru_body = (
            "\u0420\u045f\u0420\xb0\u0421\u0402\u0420\xb0\u0420\xbb\u0420\xbb\u0420\xb0"
            "\u0420\u0454\u0421\u0403 \u0420\u0406\u0420\u0455\u0420\xb7\u0420\u0405"
            "\u0420\u0451\u0420\u0454\u0420\xb0\u0420\xb5\u0421\u201a \u0420\u0406 "
            "\u0421\u040c\u0421\u201a\u0420\u0455\u0420\u0458 \u0421\u0402\u0420\xb0"
            "\u0420\xb7\u0420\u0491\u0420\xb5\u0420\xbb\u0420\xb5. "
        ) * 90
        (stage_dir / "01.en.raw.html").write_text(
            "<html><body>"
            '<span id="page-33-0"></span>'
            f"<p>{mojibake_ru_body}</p>"
            '<p>\u0441\u043c. \u0441. 34</p>'
            '<p>\u0420\u045f\u0420\xb0\u0421\u0402\u0420\xb0\u0420\xbb\u0420\xbb'
            '\u0420\xb0\u0420\u0454\u0421\u0403 <a href="#page-33-0">'
            '\u0421\u0403\u0420\u0458. \u0421\u0403. 34</a>.</p>'
            "</body></html>",
            encoding="utf-8",
        )
        report_path = tmp_path / "report.json"

        exit_code = repolish.main(
            [
                "--roots",
                str(tmp_path),
                "--out-report",
                str(report_path),
                "--table-caption-language",
                "en",
                "--polish-language",
                "auto",
            ]
        )

        assert exit_code == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["polish_language"] == "auto"
        assert report["polish_language_counts"] == {"ru": 1}
        assert report["articles"][0]["polish_language"] == "ru"
        assert report["articles"][0]["detected_language"] == "ru"
        polished = (stage_dir / "02.en.polish.html").read_text(encoding="utf-8")
        assert "СЃРј. СЃ. 34" in polished
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_repolish_cli_can_skip_non_english_documents_for_en_corpus() -> None:
    repolish = _load_module()
    tmp_path = _make_temp_dir()
    try:
        en_stage = tmp_path / "English article" / "_z2m_stages"
        ru_stage = tmp_path / "Russian article" / "_z2m_stages"
        en_stage.mkdir(parents=True)
        ru_stage.mkdir(parents=True)
        en_text = (
            "This study evaluates the design of neural interfaces and describes the methods, "
            "results, and discussion for the experiments. "
        ) * 80
        ru_text = (
            "\u041a\u043b\u0438\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0435 "
            "\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u0438 "
            "\u043e\u043f\u0438\u0441\u044b\u0432\u0430\u044e\u0442 "
            "\u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0443 "
            "\u0438 \u043b\u0435\u0447\u0435\u043d\u0438\u0435. "
        ) * 80
        (en_stage / "01.en.raw.html").write_text(f"<html><body><p>{en_text}</p></body></html>", encoding="utf-8")
        (ru_stage / "01.en.raw.html").write_text(f"<html><body><p>{ru_text}</p></body></html>", encoding="utf-8")
        report_path = tmp_path / "report.json"

        exit_code = repolish.main(
            [
                "--roots",
                str(tmp_path),
                "--out-report",
                str(report_path),
                "--polish-language",
                "auto",
                "--target-language",
                "en",
                "--skip-non-target-language",
            ]
        )

        assert exit_code == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["raw_count"] == 2
        assert report["article_count"] == 1
        assert report["skipped_count"] == 1
        assert report["polish_language_counts"] == {"en": 1}
        assert (en_stage / "02.en.polish.html").is_file()
        assert not (ru_stage / "02.en.polish.html").exists()
        skipped = [article for article in report["articles"] if article["skipped"]]
        assert skipped[0]["detected_language"] == "ru"
        assert skipped[0]["skip_reason"] == "detected_ru_not_en"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
