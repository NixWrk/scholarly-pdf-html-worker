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
