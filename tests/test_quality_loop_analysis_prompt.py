from pdf_html_polish.quality_loop.analysis_prompt import render_llm_prompt


def test_analysis_prompt_includes_required_evidence_and_loop_guards() -> None:
    prompt = render_llm_prompt(
        {
            "run_id": "run_a",
            "ignored_defect_ids": [],
            "articles": [],
            "pdf_problem_evidence_stage": {"status": "ready", "blocking_issue_count": 0},
            "p62_marker_recovery_plan": {"status": "ready", "ready_count": 1},
            "p62_image_recovery_stage": {
                "candidate_count": 1,
                "source_visual_unavailable_count": 1,
                "source_visual_unavailable_group_count": 1,
            },
        }
    )

    assert "Every production artifact fix must include a focused regression test" in prompt
    assert "PDF page render and text-layer evidence" in prompt
    assert "full cached raw EN repolish comparison" in prompt
    assert "pdf_problem_evidence_status" in prompt
    assert "p62_marker_recovery_status" in prompt
    assert "source_visual_unavailable_count" in prompt
    assert "source_visual_unavailable_group_count" in prompt
