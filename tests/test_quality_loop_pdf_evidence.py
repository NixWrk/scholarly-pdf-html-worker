from pathlib import Path

import pytest

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


def test_pdf_evidence_rerun_removes_stale_run_owned_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    pack = {
        "articles": [
            {
                "article": "paper",
                "source_pdf_candidates": [
                    {"exists": True, "path": str(source_pdf), "source": "test"}
                ],
                "defects": [{"snippet": "target text"}],
            }
        ]
    }

    def render(_pdf: Path, _page: int, target: Path, *, zoom: float) -> dict:
        assert zoom == 1.5
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png")
        return {"status": "rendered", "path": str(target), "error": ""}

    kwargs = {
        "gate_config": {},
        "pdf_text_pages": lambda *_args, **_kwargs: ("ok", ["target text"], None),
        "render_pdf_evidence_page": render,
    }
    first = write_pdf_problem_evidence_stage(run_dir, pack, **kwargs)
    assert first["status"] == "ready"
    stale = run_dir / "pdf_problem_evidence" / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    second = write_pdf_problem_evidence_stage(run_dir, pack, **kwargs)

    assert second["status"] == "ready"
    assert not stale.exists()
    assert {
        path.name
        for path in (run_dir / "pdf_problem_evidence").rglob("*")
        if path.is_file()
    } == {"page_0001.txt", "page_0001.png"}


def test_pdf_evidence_refuses_to_replace_regular_file_output_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    output = run_dir / "pdf_problem_evidence"
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="run_owned_directory_not_directory"):
        write_pdf_problem_evidence_stage(
            run_dir,
            {"articles": []},
            gate_config={},
            pdf_text_pages=lambda *_args, **_kwargs: ("not_called", [], None),
            render_pdf_evidence_page=lambda *_args, **_kwargs: {"status": "not_called"},
        )

    assert output.read_text(encoding="utf-8") == "keep"


def test_pdf_evidence_refuses_linked_output_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    output = run_dir / "pdf_problem_evidence"
    try:
        output.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ValueError, match="run_owned_directory_link_like"):
        write_pdf_problem_evidence_stage(
            run_dir,
            {"articles": []},
            gate_config={},
            pdf_text_pages=lambda *_args, **_kwargs: ("not_called", [], None),
            render_pdf_evidence_page=lambda *_args, **_kwargs: {"status": "not_called"},
        )

    assert sentinel.read_text(encoding="utf-8") == "keep"
