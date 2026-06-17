from pathlib import Path

from pdf_html_polish.quality_loop.resolver_decisions import write_resolver_decisions
from pdf_html_polish.quality_loop.run_utils import write_json


def test_resolver_decisions_split_telemetry_repair_and_quality_defects(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "article_a",
                    "summary": {
                        "source_pdf_present": True,
                        "source_pdf_path": "paper.pdf",
                        "pdf_text_status": "pymupdf",
                    },
                    "defects_found": [
                        {"id": "P04T", "severity": "warning", "extra": {"quality_counted": False}},
                        {
                            "id": "P62",
                            "severity": "warning",
                            "extra": {"quality_counted": False, "warning_origin": "caption-only-target"},
                        },
                        {"id": "P04N", "severity": "warning", "extra": {"quality_counted": False}},
                        {
                            "id": "P71",
                            "severity": "warning",
                            "extra": {"quality_counted": False, "source_pdf_text_layer_evidence": True},
                        },
                        {"id": "P67", "severity": "error", "check": "quality counted text defect"},
                    ],
                }
            ],
        },
    )
    write_json(run_dir / "quality_history_entry.json", {"run_id": "run_a"})
    write_json(run_dir / "manifest.json", {"source_kind": "test"})

    report = write_resolver_decisions(run_dir)

    assert report["decision_counts"]["accepted_telemetry"] == 2
    assert report["decision_counts"]["needs_pdf_recovery"] == 1
    assert report["decision_counts"]["needs_pdf_reference_recovery"] == 1
    assert report["decision_counts"]["needs_repair"] == 1
    assert report["accepted_telemetry_counts"] == {"P04T": 1, "P71": 1}
    assert report["repair_candidate_counts"] == {"P04N": 1, "P62": 1}
