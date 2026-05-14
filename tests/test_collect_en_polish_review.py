import importlib.util
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
COLLECT_SCRIPT = ROOT / "scripts" / "collect_en_polish_review.py"


def _make_temp_dir() -> Path:
    path = Path(".tmp_local2") / f"test_collect_en_polish_review_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_collect_module():
    spec = importlib.util.spec_from_file_location("collect_en_polish_review", COLLECT_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collect_review_set_inlines_stage_html_article_images() -> None:
    collect = _load_collect_module()
    tmp_path = _make_temp_dir()
    try:
        article_dir = tmp_path / "Article Sample"
        stage_dir = article_dir / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        image_path = article_dir / "_page_1_Figure_1.jpeg"
        image_path.write_bytes(b"\xff\xd8\xfffake")
        (stage_dir / "02.en.polish.html").write_text(
            '<html><body><p><img src="_page_1_Figure_1.jpeg"></p></body></html>',
            encoding="utf-8",
        )
        out_dir = tmp_path / "review"

        report = collect.collect_review_set([tmp_path], out_dir)

        assert report["article_count"] == 1
        assert report["inlined_image_count"] == 1
        assert report["missing_image_count"] == 0
        article_report = report["articles"][0]
        review_html = Path(article_report["review_html"])
        assert review_html.is_file()
        review_text = review_html.read_text(encoding="utf-8")
        assert 'src="data:image/jpeg;base64,' in review_text
        assert 'data-z2m-src="_page_1_Figure_1.jpeg"' in review_text
        assert not (review_html.parent / "_page_1_Figure_1.jpeg").exists()
        saved_report = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        assert saved_report["articles"][0]["inlined_images"] == ["_page_1_Figure_1.jpeg"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_collect_review_set_reports_missing_images() -> None:
    collect = _load_collect_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article Sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "02.en.polish.html").write_text(
            '<html><body><p><img src="_page_1_Figure_1.jpeg"></p></body></html>',
            encoding="utf-8",
        )

        report = collect.collect_review_set([tmp_path], tmp_path / "review")

        assert report["missing_image_count"] == 1
        assert report["articles"][0]["missing_images"][0]["src"] == "_page_1_Figure_1.jpeg"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
