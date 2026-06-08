from pathlib import Path

from zoteropdf2md.quality_loop.review_workflow import (
    write_article_review_stage,
    write_manual_review_queue,
)
from zoteropdf2md.quality_loop.run_utils import write_json


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
