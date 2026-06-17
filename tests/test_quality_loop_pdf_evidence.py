from pathlib import Path

from pdf_html_polish.quality_loop.pdf_evidence import (
    attach_pdf_evidence_to_pack,
    problem_snippets_for_evidence,
    write_pdf_problem_evidence_stage,
)


def test_problem_snippets_include_defects_and_comparison() -> None:
    snippets = problem_snippets_for_evidence(
        {
            "defects": [{"snippet": " Broken   DOI boundary "}],
            "comparison": {"article": "article_a", "score_delta": 2},
        }
    )

    assert snippets == ["Broken DOI boundary", "comparison regression score_delta=2"]


def test_pdf_evidence_stage_blocks_when_source_pdf_required(tmp_path: Path) -> None:
    report = write_pdf_problem_evidence_stage(
        tmp_path / "run",
        {"articles": [{"article": "article_a", "source_pdf_candidates": []}]},
        gate_config={"pdf_problem_evidence_allow_missing_source_pdf": False},
        pdf_text_pages=lambda *_args, **_kwargs: ("not_called", [], None),
        render_pdf_evidence_page=lambda *_args, **_kwargs: {"status": "not_called"},
    )

    assert report["status"] == "incomplete"
    assert report["blocking_issue_count"] == 1
    assert report["source_pdf_unavailable_count"] == 1
    assert (tmp_path / "run" / "pdf_problem_evidence_report.json").is_file()


def test_attach_pdf_evidence_to_pack_adds_stage_summary() -> None:
    pack = {"articles": [{"article": "article_a"}, {"article": "article_b"}]}
    report = {
        "status": "ready",
        "report_path": "report.json",
        "evidence_dir": "pdf_problem_evidence",
        "selected_count": 1,
        "ready_count": 1,
        "source_pdf_unavailable_count": 0,
        "blocking_issue_count": 0,
        "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
        "articles": [{"article": "article_a", "evidence_page": 2}],
    }

    updated = attach_pdf_evidence_to_pack(pack, report)

    assert updated["articles"][0]["pdf_problem_evidence"]["evidence_page"] == 2
    assert updated["articles"][1]["pdf_problem_evidence"] == {}
    assert updated["pdf_problem_evidence_stage"]["ready_count"] == 1
