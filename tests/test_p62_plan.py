import json
from pathlib import Path

from zoteropdf2md.quality_loop.p62_plan import (
    P62MarkerRecoveryPlanDependencies,
    write_marker_recovery_plan,
)
from zoteropdf2md.quality_loop.run_utils import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_p62_audit(run_dir: Path) -> None:
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "Article One",
                    "defects_found": [
                        {
                            "id": "P62",
                            "snippet": "Missing Figure 2 warning",
                            "extra": {"figure_label": "2", "warning_index": 1},
                        }
                    ],
                }
            ]
        },
    )
    write_json(run_dir / "manifest.json", {"articles": []})


def _write_p62a_audit(run_dir: Path) -> None:
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "Article One",
                    "defects_found": [
                        {
                            "id": "P62A",
                            "snippet": "Stale missing Figure 3 warning",
                            "extra": {
                                "figure_label": "3",
                                "warning_index": 1,
                                "p62_subtype": "same_label_image_near_warning",
                            },
                        }
                    ],
                }
            ]
        },
    )
    write_json(run_dir / "manifest.json", {"articles": []})


def _write_p61_audit(run_dir: Path) -> None:
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "Article With P61",
                    "defects_found": [
                        {
                            "id": "P61",
                            "snippet": "The robot became trapped in Figure 11b.",
                            "extra": {
                                "figure": "11",
                                "figure_key": "11",
                                "visible_label": "Figure 11b",
                            },
                        }
                    ],
                }
            ]
        },
    )
    write_json(run_dir / "manifest.json", {"articles": []})


def _deps(
    *,
    selected_pdf: dict | None = None,
    polish_path: Path | None = None,
    pages: list[str] | None = None,
    resolver: dict | None = None,
) -> P62MarkerRecoveryPlanDependencies:
    return P62MarkerRecoveryPlanDependencies(
        index_polish_stage_files=lambda run_dir: [],
        selected_pdf_candidate=lambda run_dir, article_id, article, manifest_article: (
            selected_pdf,
            [selected_pdf] if selected_pdf else [],
        ),
        find_polish_stage_path_for_article=lambda run_dir, article_id, article, manifest_article, polish_index: (
            polish_path,
            "test" if polish_path is not None else "missing",
        ),
        recovery_snippets=lambda html, defect, *, context_chars: (["Figure 2 context"], "Figure 2 context", "defect"),
        full_figure_label_from_context=lambda context, fallback_label: f"Figure {fallback_label}",
        pdf_text_pages=lambda pdf_path, *, max_pages: ("ok", pages or [], None),
        resolve_pdf_page_for_figure=lambda snippets, pdf_pages, figure_label, *, pdf_path: resolver or {},
        validate_marker_output=lambda marker_output_dir, figure_label: {"status": "not_run"},
    )


def test_write_marker_recovery_plan_reports_unavailable_source_pdf(tmp_path: Path) -> None:
    _write_p62_audit(tmp_path)

    report = write_marker_recovery_plan(
        tmp_path,
        gate_config={},
        dependencies=_deps(),
    )

    assert report["status"] == "partial"
    assert report["status_counts"] == {"source_pdf_unavailable": 1}
    assert report["articles"][0]["figure_label"] == "2"


def test_write_marker_recovery_plan_includes_p62a_missing_warning(tmp_path: Path) -> None:
    _write_p62a_audit(tmp_path)

    report = write_marker_recovery_plan(
        tmp_path,
        gate_config={},
        dependencies=_deps(),
    )

    assert report["candidate_count"] == 1
    assert report["articles"][0]["figure_label"] == "3"
    assert report["articles"][0]["warning_origin"] == "same_label_image_near_warning"


def test_write_marker_recovery_plan_ignores_p61_by_default(tmp_path: Path) -> None:
    _write_p61_audit(tmp_path)

    report = write_marker_recovery_plan(
        tmp_path,
        gate_config={},
        dependencies=_deps(),
    )

    assert report["status"] == "not_required"
    assert report["candidate_count"] == 0


def test_default_gate_config_includes_p61_marker_recovery() -> None:
    config = json.loads((REPO_ROOT / "configs" / "llm_quality_gates.json").read_text(encoding="utf-8"))

    assert config["p62_marker_recovery_include_p61"] is True


def test_write_marker_recovery_plan_can_include_p61_source_backed_item(tmp_path: Path) -> None:
    _write_p61_audit(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    report = write_marker_recovery_plan(
        tmp_path,
        gate_config={"p62_marker_recovery_include_p61": True},
        dependencies=_deps(
            selected_pdf={"path": str(pdf_path), "source": "test", "exists": True},
            pages=["Figure 11b caption and visual evidence"],
            resolver={
                "page_number": 1,
                "match_score": 0.9,
                "label_pages": [1],
                "candidates": [{"page_number": 1, "score": 0.9}],
            },
        ),
    )

    record = report["articles"][0]
    assert report["status"] == "ready"
    assert report["candidate_count"] == 1
    assert record["defect_id"] == "P61"
    assert record["figure_label"] == "11b"
    assert record["target_figure_key"] == "11"
    assert record["marker_page_range"] == "0"


def test_write_marker_recovery_plan_expands_all_p61_refs_in_polish_html(tmp_path: Path) -> None:
    _write_p61_audit(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    polish_path = tmp_path / "02.en.polish.html"
    polish_path.write_text(
        "<html><body>"
        "<p>The first local result is shown in Figure 2.</p>"
        "<p>The same local result is discussed again in FIGURE 2.</p>"
        "<p>The second local result is shown in Figure 3.</p>"
        "</body></html>",
        encoding="utf-8",
    )

    report = write_marker_recovery_plan(
        tmp_path,
        gate_config={"p62_marker_recovery_include_p61": True},
        dependencies=_deps(
            selected_pdf={"path": str(pdf_path), "source": "test", "exists": True},
            polish_path=polish_path,
            pages=["Figure 2 caption and visual evidence. Figure 3 caption and visual evidence."],
            resolver={
                "page_number": 1,
                "match_score": 0.9,
                "label_pages": [1],
                "candidates": [{"page_number": 1, "score": 0.9}],
            },
        ),
    )

    assert report["candidate_count"] == 2
    assert [record["visible_label"] for record in report["articles"]] == ["Figure 2", "Figure 3"]
    assert [record["target_figure_key"] for record in report["articles"]] == ["2", "3"]


def test_write_marker_recovery_plan_builds_ready_single_page_record(tmp_path: Path) -> None:
    _write_p62_audit(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    report = write_marker_recovery_plan(
        tmp_path,
        gate_config={},
        dependencies=_deps(
            selected_pdf={"path": str(pdf_path), "source": "test", "exists": True},
            pages=["Figure 2 caption and visual evidence"],
            resolver={
                "page_number": 1,
                "match_score": 0.9,
                "label_pages": [1],
                "candidates": [{"page_number": 1, "score": 0.9}],
            },
        ),
    )

    record = report["articles"][0]
    assert report["status"] == "ready"
    assert record["status"] == "ready"
    assert record["marker_page_range"] == "0"
    assert record["marker_command"]
    assert Path(record["source_pdf_page_excerpt_path"]).read_text(encoding="utf-8") == "Figure 2 caption and visual evidence"
