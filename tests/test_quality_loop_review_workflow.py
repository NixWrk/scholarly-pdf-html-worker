from pathlib import Path

from pdf_html_polish.quality_loop.review_workflow import (
    write_article_review_stage,
    write_manual_review_queue,
)
from pdf_html_polish.quality_loop.run_utils import write_json


def test_review_queue_prioritizes_mandatory_changed_articles(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {"article": "a", "defects_found": [{"id": "P67", "severity": "warning"}]},
                {"article": "b", "defects_found": [{"id": "P20", "severity": "error"}]},
            ]
        },
    )
    write_json(run_dir / "quality_history_entry.json", {"articles": {"a": {"score": 1}, "b": {"score": 9}}})
    write_json(
        run_dir / "quality_compare.json",
        {"unchanged": [{"article": "a", "score_delta": 0}], "improvements": [{"article": "b", "score_delta": -1}]},
    )
    write_json(run_dir / "manifest.json", {"articles": [{"article_id": "a", "changed": True}, {"article_id": "b", "changed": True}]})

    queue = write_manual_review_queue(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": ["P20"]},
        comparison_by_article=lambda comparison: {
            item["article"]: {"bucket": bucket, **item}
            for bucket in ("unchanged", "improvements")
            for item in comparison.get(bucket, [])
        },
        manifest_article_by_id=lambda manifest: {
            item["article_id"]: item for item in manifest.get("articles", [])
        },
    )

    assert [item["article"] for item in queue] == ["a", "b"]
    assert queue[0]["mandatory_review"] is True
    assert queue[1]["non_ignored_defect_ids"] == {}


def test_review_queue_auto_verifies_changed_article_with_complete_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "audit_full_checks.json",
        {"articles": [{"article": "a", "defects_found": []}]},
    )
    write_json(run_dir / "quality_history_entry.json", {"articles": {"a": {"score": 0}}})
    write_json(
        run_dir / "quality_compare.json",
        {
            "unchanged": [
                {
                    "article": "a",
                    "score_delta": 0,
                    "defects_delta": 0,
                    "errors_delta": 0,
                    "warnings_delta": 0,
                    "metrics_delta": {"broken_internal_links": 0, "missing_local_images": 0},
                }
            ]
        },
    )
    write_json(
        run_dir / "manifest.json",
        {"articles": [{"article_id": "a", "changed": True, "restored_images": 2}]},
    )
    write_json(
        run_dir / "manual_review_queue.json",
        [
            {
                "article": "a",
                "review_status": "reviewed",
                "review_note": "human state survives",
                "review_risk_level": "high",
                "review_risk_reasons": ["stale_risk"],
            }
        ],
    )

    queue = write_manual_review_queue(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": []},
        comparison_by_article=lambda comparison: {
            item["article"]: {"bucket": "unchanged", **item}
            for item in comparison.get("unchanged", [])
        },
        manifest_article_by_id=lambda manifest: {
            item["article_id"]: item for item in manifest.get("articles", [])
        },
    )

    assert queue[0]["mandatory_review"] is False
    assert queue[0]["review_risk_level"] == "auto_verified"
    assert queue[0]["review_status"] == "reviewed"
    assert queue[0]["review_note"] == "human state survives"
    assert queue[0]["auto_review_eligible"] is True
    assert queue[0]["auto_review_evidence"]["change_sources"] == ["image_cache_restore"]


def test_review_queue_keeps_changed_article_with_non_ignored_defect_mandatory(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "audit_full_checks.json",
        {"articles": [{"article": "a", "defects_found": [{"id": "P71", "severity": "warning"}]}]},
    )
    write_json(run_dir / "quality_history_entry.json", {"articles": {"a": {"score": 0}}})
    write_json(
        run_dir / "quality_compare.json",
        {"unchanged": [{"article": "a", "score_delta": 0, "metrics_delta": {}}]},
    )
    write_json(run_dir / "manifest.json", {"articles": [{"article_id": "a", "changed": True}]})

    queue = write_manual_review_queue(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": []},
        comparison_by_article=lambda comparison: {
            item["article"]: {"bucket": "unchanged", **item}
            for item in comparison.get("unchanged", [])
        },
        manifest_article_by_id=lambda manifest: {
            item["article_id"]: item for item in manifest.get("articles", [])
        },
    )

    assert queue[0]["mandatory_review"] is True
    assert queue[0]["mandatory_review_reason"] == "changed_without_quality_delta"
    assert queue[0]["review_risk_level"] == "high"
    assert "non_ignored_quality_counted_audit_defects" in queue[0]["review_risk_reasons"]


def test_review_queue_does_not_make_non_quality_telemetry_mandatory(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "a",
                    "defects_found": [
                        {
                            "id": "P71",
                            "severity": "warning",
                            "extra": {"quality_counted": False},
                        }
                    ],
                }
            ]
        },
    )
    write_json(run_dir / "quality_history_entry.json", {"articles": {"a": {"score": 0}}})
    write_json(
        run_dir / "quality_compare.json",
        {"unchanged": [{"article": "a", "score_delta": 0, "metrics_delta": {}}]},
    )
    write_json(run_dir / "manifest.json", {"articles": [{"article_id": "a", "changed": True}]})

    queue = write_manual_review_queue(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": []},
        comparison_by_article=lambda comparison: {
            item["article"]: {"bucket": "unchanged", **item}
            for item in comparison.get("unchanged", [])
        },
        manifest_article_by_id=lambda manifest: {
            item["article_id"]: item for item in manifest.get("articles", [])
        },
    )

    assert queue[0]["mandatory_review"] is False
    assert queue[0]["review_risk_level"] == "medium"
    assert queue[0]["non_ignored_defect_count"] == 1
    assert queue[0]["non_ignored_quality_counted_defect_count"] == 0
    assert "observed_non_quality_or_telemetry_defects" in queue[0]["review_risk_reasons"]


def test_review_queue_keeps_incomplete_p62_unavailable_record_mandatory(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "audit_full_checks.json",
        {"articles": [{"article": "a", "defects_found": []}]},
    )
    write_json(run_dir / "quality_history_entry.json", {"articles": {"a": {"score": 0}}})
    write_json(
        run_dir / "quality_compare.json",
        {"unchanged": [{"article": "a", "score_delta": 0, "metrics_delta": {}}]},
    )
    write_json(run_dir / "manifest.json", {"articles": [{"article_id": "a", "changed": True}]})
    write_json(
        run_dir / "p62_image_recovery_report.json",
        {
            "articles": [
                {
                    "article": "a",
                    "status": "unresolved",
                    "plan_status": "source_visual_unavailable",
                    "source_visual_unavailable_reason": (
                        "all_label_matches_are_false_or_without_visual_objects"
                    ),
                    "source_visual_probe_status": "not_found",
                    "source_visual_probe": {
                        "status": "not_found",
                        "label_pages": [1],
                        "visual_inventory": {"status": "ready"},
                    },
                }
            ]
        },
    )

    queue = write_manual_review_queue(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": []},
        comparison_by_article=lambda comparison: {
            item["article"]: {"bucket": "unchanged", **item}
            for item in comparison.get("unchanged", [])
        },
        manifest_article_by_id=lambda manifest: {
            item["article_id"]: item for item in manifest.get("articles", [])
        },
    )

    assert queue[0]["mandatory_review"] is True
    assert queue[0]["review_risk_level"] == "high"
    assert "p62_unresolved_without_terminal_status" in queue[0]["review_risk_reasons"]


def test_review_queue_accepts_audit_terminal_p62_source_visual_unavailable(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": "a",
                    "defects_found": [
                        {
                            "id": "P62",
                            "severity": "warning",
                            "extra": {
                                "figure_label": "7",
                                "p62_subtype": "source_visual_unavailable",
                                "quality_counted": False,
                                "warning_origin": "source_visual_unavailable",
                            },
                        }
                    ],
                }
            ]
        },
    )
    write_json(run_dir / "quality_history_entry.json", {"articles": {"a": {"score": 0}}})
    write_json(
        run_dir / "quality_compare.json",
        {"unchanged": [{"article": "a", "score_delta": 0, "metrics_delta": {}}]},
    )
    write_json(run_dir / "manifest.json", {"articles": [{"article_id": "a", "changed": True}]})
    write_json(
        run_dir / "p62_image_recovery_report.json",
        {
            "articles": [
                {
                    "article": "a",
                    "status": "unresolved",
                    "figure_label": "7",
                    "source_visual_probe_status": "not_found",
                }
            ]
        },
    )

    queue = write_manual_review_queue(
        run_dir,
        gate_config={"ignored_defect_ids_for_analysis": ["P62"]},
        comparison_by_article=lambda comparison: {
            item["article"]: {"bucket": "unchanged", **item}
            for item in comparison.get("unchanged", [])
        },
        manifest_article_by_id=lambda manifest: {
            item["article_id"]: item for item in manifest.get("articles", [])
        },
    )

    assert queue[0]["mandatory_review"] is False
    assert queue[0]["auto_review_evidence"]["p62"]["source_visual_unavailable_count"] == 1
    assert queue[0]["auto_review_evidence"]["p62"]["actionable_unresolved_count"] == 0
    assert "p62_unresolved_without_terminal_status" not in queue[0]["review_risk_reasons"]


def test_article_review_stage_uses_copy_callback_and_writes_index(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    source = run_dir / "polish" / "a.02.en.polish.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html><body>Review me</body></html>", encoding="utf-8")

    def copy_review_html(source_path: Path, target_path: Path) -> dict[str, object]:
        target_path.parent.mkdir(parents=True)
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        return {"review_html": str(target_path), "inlined_image_count": 0, "missing_image_count": 0}

    report = write_article_review_stage(
        run_dir,
        [{"article": "a", "mandatory_review": True, "review_status": "pending", "polish_stage_path": str(source)}],
        repo_root=tmp_path,
        polish_stage="02.en.polish.html",
        copy_review_html_with_inline_images=copy_review_html,
    )

    assert report["status"] == "ready"
    assert report["pending_mandatory_count"] == 1
    assert Path(report["articles"][0]["review_html"]).is_file()
    assert Path(report["index_html"]).read_text(encoding="utf-8").count("open") == 1
