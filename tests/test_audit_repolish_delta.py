from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_repolish_delta.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_repolish_delta", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _defect(defect_id: str, *, quality_counted: bool = True) -> dict[str, object]:
    return {
        "id": defect_id,
        "severity": "error",
        "status": "open",
        "extra": {"quality_counted": quality_counted},
    }


def test_load_json_report_accepts_utf8_bom(tmp_path: Path) -> None:
    audit = _load_module()
    report = tmp_path / "report.json"
    report.write_bytes(b'\xef\xbb\xbf{"articles": [{"attachment_key": "CONTROL"}]}')

    assert audit.load_json_report(report)["articles"][0]["attachment_key"] == "CONTROL"


def test_article_patterns_filter_before_fresh_baseline() -> None:
    audit = _load_module()
    article = {"article": "Learning to See Again", "raw_stage_path": "paper/raw.html"}

    assert audit.article_matches_patterns(article, [])
    assert audit.article_matches_patterns(article, ["learning to see"])
    assert audit.article_matches_patterns(article, ["paper/raw"])
    assert not audit.article_matches_patterns(article, ["horton"])


def test_quality_defects_honors_explicit_non_quality_override() -> None:
    audit = _load_module()
    p71_without_explicit_flag = _defect("P71")
    p71_without_explicit_flag["extra"] = {}
    article = {
        "defects_found": [
            _defect("P20"),
            _defect("P71", quality_counted=False),
            p71_without_explicit_flag,
        ]
    }

    assert [defect["id"] for defect in audit.quality_defects(article)] == ["P20", "P71"]


def test_console_safe_escapes_characters_missing_from_console_encoding() -> None:
    audit = _load_module()

    rendered = audit.console_safe("paper á Б", encoding="cp1251")

    assert rendered == r"paper \xe1 Б"


def test_evaluate_article_reports_fixed_current_repolish(tmp_path: Path) -> None:
    audit = _load_module()
    raw = tmp_path / "01.en.raw.html"
    old = tmp_path / "02.en.polish.html"
    raw.write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    old.write_text("<html><body><p>Old</p></body></html>", encoding="utf-8")
    article = {
        "article": "paper",
        "raw_stage_path": str(raw),
        "polish_stage_path": str(old),
        "defects_found": [_defect("P99")],
    }

    analyzed_paths: list[Path] = []

    def analyze_pair(_raw: Path, polish: Path) -> dict[str, object]:
        analyzed_paths.append(polish)
        if polish == old:
            return {"defects_found": [_defect("P99")]}
        return {"defects_found": []}

    result = audit.evaluate_article(
        article,
        repolish=lambda _path: "<html><body><p>Repolished</p></body></html>",
        analyze_pair=analyze_pair,
        temp_root=tmp_path,
    )

    assert result["classification"] == "fixed"
    assert result["recommended_action"] == "repolish"
    assert result["before_defect_counts"] == {"P99": 1}
    assert result["after_defect_counts"] == {}
    assert result["after_defects"] == []
    assert result["output_bytes"] > 0
    assert analyzed_paths[0] == old


def test_evaluate_article_ignores_stale_snapshot_defects(tmp_path: Path) -> None:
    audit = _load_module()
    raw = tmp_path / "01.en.raw.html"
    old = tmp_path / "02.en.polish.html"
    raw.write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    old.write_text("<html><body><p>Old</p></body></html>", encoding="utf-8")
    article = {
        "article": "paper",
        "raw_stage_path": str(raw),
        "polish_stage_path": str(old),
        "defects_found": [_defect("P99")],
    }

    def analyze_pair(_raw: Path, polish: Path) -> dict[str, object]:
        defect_id = "P66" if polish == old else "P20"
        return {"defects_found": [_defect(defect_id)]}

    result = audit.evaluate_article(
        article,
        repolish=lambda _path: "<html><body><p>Repolished</p></body></html>",
        analyze_pair=analyze_pair,
        temp_root=tmp_path,
    )

    assert result["before_defect_counts"] == {"P66": 1}
    assert result["after_defect_counts"] == {"P20": 1}
    assert result["classification"] == "regressed"


def test_refresh_article_audit_replaces_stale_diagnostics(tmp_path: Path) -> None:
    audit = _load_module()
    raw = tmp_path / "01.en.raw.html"
    old = tmp_path / "02.en.polish.html"
    article = {
        "article": "paper",
        "raw_stage_path": str(raw),
        "polish_stage_path": str(old),
        "defects_found": [_defect("P99")],
    }

    refreshed = audit.refresh_article_audit(
        article,
        analyze_pair=lambda _raw, _polish: {
            "article": "current-paper",
            "defects_found": [_defect("P66")],
        },
    )

    assert refreshed["article"] == "current-paper"
    assert [defect["id"] for defect in refreshed["defects_found"]] == ["P66"]


def test_build_fresh_baseline_uses_parallel_strict_report(tmp_path: Path) -> None:
    audit = _load_module()
    raw = tmp_path / "01.en.raw.html"
    polish = tmp_path / "02.en.polish.html"
    baseline = tmp_path / "baseline.json"
    raw.write_text("raw", encoding="utf-8")
    polish.write_text("polish", encoding="utf-8")
    article = {
        "raw_stage_path": str(raw),
        "polish_stage_path": str(polish),
    }
    calls: list[dict[str, object]] = []

    def build_report(roots: list[Path], **kwargs: object) -> dict[str, object]:
        calls.append({"roots": roots, **kwargs})
        return {"articles": [{**article, "defects_found": [_defect("P66")]}]}

    refreshed = audit.build_fresh_baseline(
        SimpleNamespace(build_report=build_report),
        [article],
        output=baseline,
        jobs=4,
    )

    assert [defect["id"] for defect in refreshed[0]["defects_found"]] == ["P66"]
    assert calls == [
        {
            "roots": [polish],
            "enable_pdf_diagnostics": False,
            "progress_out": baseline,
            "progress_write_every": 25,
            "jobs": 4,
        }
    ]


def test_classify_delta_rejects_new_defect_despite_lower_total() -> None:
    audit = _load_module()

    classification = audit.classify_delta(
        audit.Counter({"P20": 2, "P99": 1}),
        audit.Counter({"P66": 1}),
    )

    assert classification == "regressed"


def test_evaluate_article_keeps_persistent_defect_for_code_fix(tmp_path: Path) -> None:
    audit = _load_module()
    raw = tmp_path / "01.en.raw.html"
    old = tmp_path / "02.en.polish.html"
    raw.write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    old.write_text("<html><body><p>Old</p></body></html>", encoding="utf-8")
    article = {
        "article": "paper",
        "raw_stage_path": str(raw),
        "polish_stage_path": str(old),
        "defects_found": [_defect("P20")],
    }

    result = audit.evaluate_article(
        article,
        repolish=lambda _path: "<html><body><p>Still broken</p></body></html>",
        analyze_pair=lambda _raw, _polish: {"defects_found": [_defect("P20")]},
        temp_root=tmp_path,
    )

    assert result["classification"] == "unchanged"
    assert result["recommended_action"] == "code_fix_or_reconvert"
    assert [defect["id"] for defect in result["after_defects"]] == ["P20"]


def test_evaluate_article_can_keep_candidate_without_touching_current_artifact(
    tmp_path: Path,
) -> None:
    audit = _load_module()
    raw = tmp_path / "01.en.raw.html"
    old = tmp_path / "02.en.polish.html"
    raw.write_text("<html><body><p>Raw</p></body></html>", encoding="utf-8")
    old.write_text("<html><body><p>Current</p></body></html>", encoding="utf-8")
    keep = tmp_path / "kept"
    article = {
        "article": "paper",
        "raw_stage_path": str(raw),
        "polish_stage_path": str(old),
        "defects_found": [_defect("P100")],
    }

    result = audit.evaluate_article(
        article,
        repolish=lambda _path: "<html><body><p>Candidate</p></body></html>",
        analyze_pair=lambda _raw, polish: {
            "defects_found": [_defect("P100")] if polish == old else []
        },
        temp_root=tmp_path,
        keep_output_dir=keep,
    )

    candidate = Path(result["candidate_output_path"])
    assert (
        candidate.read_text(encoding="utf-8")
        == "<html><body><p>Candidate</p></body></html>"
    )
    assert old.read_text(encoding="utf-8") == "<html><body><p>Current</p></body></html>"


def test_stage_raw_with_sidecars_finds_images_above_stage_directory(
    tmp_path: Path,
) -> None:
    audit = _load_module()
    article_dir = tmp_path / "article"
    stage_dir = article_dir / "_pdf_html_polish_stages"
    stage_dir.mkdir(parents=True)
    raw = stage_dir / "01.en.raw.html"
    raw.write_text(
        '<html><body><img src="_page_1_Figure_2.jpeg"></body></html>', encoding="utf-8"
    )
    sidecar = article_dir / "_page_1_Figure_2.jpeg"
    sidecar.write_bytes(b"\xff\xd8\xff\xe0image")

    staged = audit.stage_raw_with_sidecars(raw, tmp_path / "staged")

    assert staged.is_file()
    assert (staged.parent / sidecar.name).read_bytes() == sidecar.read_bytes()


def test_stage_raw_with_sidecars_recovers_unique_attempt_image(
    tmp_path: Path,
) -> None:
    audit = _load_module()
    signature_dir = tmp_path / "signature"
    article_dir = signature_dir / "article"
    stage_dir = article_dir / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw = stage_dir / "01.en.raw.html"
    image_name = "_page_4_Figure_1.jpeg"
    raw.write_text(f'<img src="{image_name}">', encoding="utf-8")
    attempt_image = signature_dir / "_attempts" / "attempt-a" / "chunk" / image_name
    attempt_image.parent.mkdir(parents=True)
    attempt_image.write_bytes(b"unique-attempt-image")

    staged = audit.stage_raw_with_sidecars(raw, tmp_path / "staged")

    assert (staged.parent / image_name).read_bytes() == b"unique-attempt-image"


def test_stage_raw_with_sidecars_rejects_conflicting_attempt_images(
    tmp_path: Path,
) -> None:
    audit = _load_module()
    article_dir = tmp_path / "article"
    stage_dir = article_dir / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    raw = stage_dir / "01.en.raw.html"
    image_name = "_page_4_Figure_1.jpeg"
    raw.write_text(f'<img src="{image_name}">', encoding="utf-8")
    for attempt, content in (("attempt-a", b"first"), ("attempt-b", b"second")):
        image = article_dir / "_attempts" / attempt / image_name
        image.parent.mkdir(parents=True)
        image.write_bytes(content)

    staged = audit.stage_raw_with_sidecars(raw, tmp_path / "staged")

    assert not (staged.parent / image_name).exists()


def test_inferred_citation_profile_preserves_medium_author_year_evidence(
    tmp_path: Path,
) -> None:
    audit = _load_module()
    raw = tmp_path / "01.en.raw.html"
    raw.write_text(
        "<html><body><p>Smith et al. (2020), Jones and Brown (2021), "
        "Gupta and Pruthi (2022), Lund and Naheem (2023), "
        "Yeo-The and Tang (2024), Lehman and Stanley (2011), "
        "Taylor and Green (2019), and White et al. (2018) are cited.</p>"
        "<h4>References</h4><p>Smith, J. (2020). Example.</p></body></html>",
        encoding="utf-8",
    )

    profile = audit.inferred_citation_profile(raw)

    assert profile["style"] == "author_year"
    assert profile["confidence"] in {"medium", "high"}
