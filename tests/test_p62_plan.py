from pathlib import Path

from zoteropdf2md.quality_loop.p62_plan import (
    P62MarkerRecoveryPlanDependencies,
    write_marker_recovery_plan,
)
from zoteropdf2md.quality_loop.run_utils import write_json


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


def _deps(
    *,
    selected_pdf: dict | None = None,
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
            None,
            "missing",
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
