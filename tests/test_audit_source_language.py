import importlib.util
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "audit_source_language.py"

EN_PARAGRAPH = (
    "This article evaluates the method and reports the results of the study. "
    "The experiments were performed with a device and the measurements were "
    "compared with the reference system for validation. "
)
RU_PARAGRAPH = (
    "\u042d\u0442\u043e\u0442 \u0440\u0430\u0437\u0434\u0435\u043b "
    "\u043e\u043f\u0438\u0441\u044b\u0432\u0430\u0435\u0442 "
    "\u043a\u043b\u0438\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0435 "
    "\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u0438 "
    "\u0434\u043b\u044f \u043b\u0435\u0447\u0435\u043d\u0438\u044f "
    "\u0438 \u043d\u0430\u0431\u043b\u044e\u0434\u0435\u043d\u0438\u044f "
    "\u043f\u0430\u0446\u0438\u0435\u043d\u0442\u043e\u0432. "
)


def _make_temp_dir() -> Path:
    path = Path(".tmp_local2") / f"test_audit_source_language_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_source_language", AUDIT_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_source_language_audit_reports_non_english_raw_stage() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        root = tmp_path / "run"
        en_stage = root / "sample_en" / "_z2m_stages"
        ru_stage = root / "sample_ru" / "_z2m_stages"
        en_stage.mkdir(parents=True)
        ru_stage.mkdir(parents=True)
        (en_stage / "01.en.raw.html").write_text(
            "<html><body>" + EN_PARAGRAPH * 80 + "</body></html>",
            encoding="utf-8",
        )
        (ru_stage / "01.en.raw.html").write_text(
            "<html><body>" + EN_PARAGRAPH * 8 + RU_PARAGRAPH * 90 + "</body></html>",
            encoding="utf-8",
        )

        report = audit.build_report([root], target_language="en", min_confidence=0.75, skip_unknown=False)

        assert report["article_count"] == 2
        assert report["corpus_summary"]["language_skipped_total"] == 1
        assert report["language_skipped"][0]["article"] == "sample_ru"
        assert report["language_skipped"][0]["language"]["detected_language"] in {"ru", "mixed"}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_source_language_audit_cli_writes_json_and_csv() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        root = tmp_path / "run"
        stage = root / "sample_ru" / "_z2m_stages"
        stage.mkdir(parents=True)
        (stage / "01.en.raw.html").write_text(
            "<html><body>" + RU_PARAGRAPH * 80 + "</body></html>",
            encoding="utf-8",
        )
        out_path = tmp_path / "language.json"

        exit_code = audit.main(["--roots", str(root), "--out", str(out_path)])

        assert exit_code == 0
        csv_path = out_path.with_suffix(".csv")
        assert csv_path.is_file()
        report = json.loads(out_path.read_text(encoding="utf-8"))
        assert report["language_skipped"][0]["article"] == "sample_ru"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
