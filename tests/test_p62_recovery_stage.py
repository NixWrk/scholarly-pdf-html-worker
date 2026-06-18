from pathlib import Path
from typing import Any

from pdf_html_polish.quality_loop.p62_recovery_stage import (
    P62PatchTargetDependencies,
    apply_html_patch_to_targets,
    build_p62_image_recovery_report,
    patch_targets_for_record,
    recover_pdf_figure_asset_for_stage,
    resolve_p62_image_recovery_stage_config,
)


def _path_dependencies() -> P62PatchTargetDependencies:
    def existing_path_candidates(value: Any) -> list[Path]:
        return [value] if isinstance(value, Path) else []

    def path_is_inside(path: Path, root: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(root.resolve(strict=False))
            return True
        except ValueError:
            return False

    return P62PatchTargetDependencies(
        existing_path_candidates=existing_path_candidates,
        path_is_inside=path_is_inside,
        polish_stage="02.en.polish.html",
    )


def test_resolve_p62_image_recovery_stage_config_defaults() -> None:
    config = resolve_p62_image_recovery_stage_config({})

    assert config.max_items == 0
    assert config.execute_marker is True
    assert config.apply_patches is True
    assert config.render_zoom == 1.5
    assert config.marker_timeout == 300
    assert config.probe_source_visual_unavailable is True
    assert config.probe_marker_for_unavailable is True
    assert config.probe_marker_timeout == 300
    assert config.replace_page_render is True
    assert config.remove_false_match_recovery is True
    assert config.repair_duplicate_figure_images is True


def test_resolve_p62_image_recovery_stage_config_uses_gate_values_and_fallback_zoom() -> None:
    config = resolve_p62_image_recovery_stage_config(
        {
            "p62_image_recovery_max_articles": 7,
            "p62_image_recovery_execute_marker": False,
            "p62_image_recovery_apply_patches": False,
            "pdf_problem_evidence_render_zoom": 2.25,
            "p62_image_recovery_marker_timeout_seconds": 42,
            "p62_image_recovery_probe_source_visual_unavailable": False,
            "p62_image_recovery_probe_marker_for_unavailable": True,
            "p62_image_recovery_source_visual_probe_marker_timeout_seconds": 11,
            "p62_image_recovery_replace_page_render": False,
            "p62_image_recovery_remove_false_match_recovery": False,
            "p62_image_recovery_repair_duplicate_figure_images": False,
        }
    )

    assert config.max_items == 7
    assert config.execute_marker is False
    assert config.apply_patches is False
    assert config.render_zoom == 2.25
    assert config.marker_timeout == 42
    assert config.probe_source_visual_unavailable is False
    assert config.probe_marker_for_unavailable is True
    assert config.probe_marker_timeout == 11
    assert config.replace_page_render is False
    assert config.remove_false_match_recovery is False
    assert config.repair_duplicate_figure_images is False


def test_resolve_p62_image_recovery_stage_config_call_overrides_gate_values() -> None:
    config = resolve_p62_image_recovery_stage_config(
        {
            "p62_image_recovery_max_articles": 7,
            "p62_image_recovery_execute_marker": True,
            "p62_image_recovery_apply_patches": True,
        },
        max_items=3,
        execute_marker=False,
        apply_patches=False,
    )

    assert config.max_items == 3
    assert config.execute_marker is False
    assert config.apply_patches is False
    assert config.probe_marker_for_unavailable is False


def test_patch_targets_for_record_uses_record_manifest_and_run_fallbacks(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    record_path = run_dir / "record.html"
    manifest_path = run_dir / "manifest.html"
    fallback_path = run_dir / "polish" / "A1.02.en.polish.html"
    for path in (record_path, manifest_path, fallback_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html></html>", encoding="utf-8")

    targets = patch_targets_for_record(
        run_dir,
        {"article": "A1", "polish_stage_path": record_path},
        {"polish_path": manifest_path},
        allow_external_paths=False,
        dependencies=_path_dependencies(),
    )

    assert targets == [record_path, manifest_path, fallback_path]


def test_patch_targets_for_record_filters_external_paths_unless_allowed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    fallback_path = run_dir / "polish" / "A1.02.en.polish.html"
    external_path = tmp_path / "external.html"
    for path in (fallback_path, external_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html></html>", encoding="utf-8")

    without_external = patch_targets_for_record(
        run_dir,
        {"article": "A1", "polish_stage_path": external_path},
        {},
        allow_external_paths=False,
        dependencies=_path_dependencies(),
    )
    with_external = patch_targets_for_record(
        run_dir,
        {"article": "A1", "polish_stage_path": external_path},
        {},
        allow_external_paths=True,
        dependencies=_path_dependencies(),
    )

    assert without_external == [fallback_path]
    assert with_external == [external_path, fallback_path]


def test_patch_targets_for_record_deduplicates_equivalent_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    record_path = run_dir / "same.html"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text("<html></html>", encoding="utf-8")

    targets = patch_targets_for_record(
        run_dir,
        {"polish_stage_path": record_path},
        {"polish_path": record_path},
        allow_external_paths=False,
        dependencies=_path_dependencies(),
    )

    assert targets == [record_path]


def test_apply_html_patch_to_targets_writes_replacements(tmp_path: Path) -> None:
    target_path = tmp_path / "article.html"
    target_path.write_text("before", encoding="utf-8")

    result = apply_html_patch_to_targets(
        [target_path],
        lambda html: (html.replace("before", "after"), 1),
    )

    assert target_path.read_text(encoding="utf-8") == "after"
    assert result.replacement_count == 1
    assert result.patched_paths == (str(target_path),)
    assert result.errors == ()


def test_apply_html_patch_to_targets_preserves_existing_patch_state(tmp_path: Path) -> None:
    target_path = tmp_path / "article.html"
    target_path.write_text("before", encoding="utf-8")

    result = apply_html_patch_to_targets(
        [target_path],
        lambda html: (html.replace("before", "after"), 2),
        patched_paths=("seed.html",),
        replacement_count=3,
    )

    assert result.replacement_count == 5
    assert result.patched_paths == ("seed.html", str(target_path))


def test_apply_html_patch_to_targets_records_file_errors(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.html"

    result = apply_html_patch_to_targets(
        [missing_path],
        lambda html: (html, 1),
    )

    assert result.replacement_count == 0
    assert result.patched_paths == ()
    assert result.errors
    assert result.errors[0]["path"] == str(missing_path)


def test_recover_pdf_figure_asset_for_stage_prefers_detached_asset(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    asset_path = tmp_path / "detached.png"
    fallback_called = False

    def recover_detached(*args: Any, **kwargs: Any) -> dict[str, Any]:
        assert args == (pdf_path, 4, "Figure 2", tmp_path)
        assert kwargs == {"zoom": 1.75}
        return {
            "status": "recovered_detached",
            "path": str(asset_path),
            "source": "pdf_detached_plate_region_render",
            "page_number": 4,
            "selected_rect": [1, 2, 3, 4],
            "caption_found": True,
            "plate_index": 1,
            "plate_count": 2,
        }

    def recover_fallback(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal fallback_called
        fallback_called = True
        return {}

    result = recover_pdf_figure_asset_for_stage(
        pdf_path,
        4,
        "Figure 2",
        tmp_path,
        zoom=1.75,
        recover_detached_pdf_figure_plate_asset=recover_detached,
        recover_pdf_figure_asset=recover_fallback,
        data_url_from_image_file=lambda path: "data:image/png;base64,abc" if path == asset_path else "",
    )

    assert fallback_called is False
    assert result.data_url == "data:image/png;base64,abc"
    assert result.recovery_source == "pdf_detached_plate_region_render"
    assert result.recovery_detail == str(asset_path)
    assert result.item_updates["figure_asset_status"] == "recovered_detached"
    assert result.item_updates["figure_asset_selected_rect"] == [1, 2, 3, 4]
    assert result.item_updates["figure_asset_caption_found"] is True
    assert result.item_updates["figure_asset_plate_index"] == 1
    assert result.item_updates["figure_asset_plate_count"] == 2


def test_recover_pdf_figure_asset_for_stage_falls_back_to_region_asset(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    asset_path = tmp_path / "region.png"

    result = recover_pdf_figure_asset_for_stage(
        pdf_path,
        8,
        "Figure 4",
        tmp_path,
        zoom=2.0,
        recover_detached_pdf_figure_plate_asset=lambda *args, **kwargs: {
            "status": "detached_unavailable",
        },
        recover_pdf_figure_asset=lambda *args, **kwargs: {
            "status": "recovered_region",
            "path": str(asset_path),
            "source": "pdf_figure_region_render",
            "error": "",
            "page_number": 8,
        },
        data_url_from_image_file=lambda path: "data:image/png;base64,region" if path == asset_path else "",
    )

    assert result.data_url == "data:image/png;base64,region"
    assert result.recovery_source == "pdf_figure_region_render"
    assert result.recovery_detail == str(asset_path)
    assert result.item_updates["figure_asset_status"] == "recovered_region"
    assert result.item_updates["figure_asset_page_number"] == 8


def test_build_p62_image_recovery_report_summarizes_partial_recovery(tmp_path: Path) -> None:
    config = resolve_p62_image_recovery_stage_config(
        {"p62_image_recovery_execute_marker": False},
        apply_patches=True,
    )

    report = build_p62_image_recovery_report(
        generated_at="2026-01-02T03:04:05Z",
        run_dir=tmp_path / "run",
        out_path=tmp_path / "report.json",
        plan_path=tmp_path / "plan.json",
        recovery_root=tmp_path / "recovery",
        plan_candidate_count=2,
        selected_count=2,
        recovered_records=[
            {
                "status": "patched",
                "asset_status": "ready",
                "recovery_source": "marker_image",
                "patch_replacement_count": 2,
                "existing_page_render_upgrade": True,
                "duplicate_visual_repair_count": 1,
                "source_visual_probe_status": "not_run",
            },
            {
                "status": "unresolved",
                "asset_status": "not_ready",
                "recovery_source": "",
                "page_render_recovery_removed": True,
                "false_match_recovery_removed": True,
                "source_visual_probe_status": "failed",
            },
        ],
        patched_article_ids={"A1"},
        stage_config=config,
        allow_external_paths=True,
    )

    assert report["status"] == "partial"
    assert report["candidate_count"] == 2
    assert report["selected_count"] == 2
    assert report["asset_ready_count"] == 1
    assert report["patched_warning_count"] == 2
    assert report["patched_articles"] == ["A1"]
    assert report["page_render_upgrade_count"] == 1
    assert report["page_render_recovery_removed_count"] == 1
    assert report["false_match_recovery_removed_count"] == 1
    assert report["duplicate_visual_repair_count"] == 1
    assert report["execute_marker"] is False
    assert report["apply_patches"] is True
    assert report["allow_external_paths"] is True
    assert report["status_counts"] == {"patched": 1, "unresolved": 1}
    assert report["recovery_source_counts"] == {"marker_image": 1, "unresolved": 1}
    assert report["source_visual_probe_status_counts"] == {"failed": 1, "not_run": 1}


def test_build_p62_image_recovery_report_closes_complete_source_unavailable_evidence(
    tmp_path: Path,
) -> None:
    report = build_p62_image_recovery_report(
        generated_at="2026-01-02T03:04:05Z",
        run_dir=tmp_path / "run",
        out_path=tmp_path / "report.json",
        plan_path=tmp_path / "plan.json",
        recovery_root=tmp_path / "recovery",
        plan_candidate_count=1,
        selected_count=1,
        recovered_records=[
            {
                "status": "unresolved",
                "plan_status": "source_visual_unavailable",
                "asset_status": "not_ready",
                "source_visual_unavailable_reason": (
                    "all_label_matches_are_false_or_without_visual_objects"
                ),
                "source_visual_probe_status": "not_found",
                "source_visual_probe": {
                    "status": "not_found",
                    "label_pages": [7, 43],
                    "attempts": [{"status": "skipped_false_label_match"}],
                    "visual_inventory": {"status": "ready", "native_image_count": 0},
                    "pypdf_image_inventory": {"status": "ready", "image_count": 0},
                },
            },
        ],
        patched_article_ids=[],
        stage_config=resolve_p62_image_recovery_stage_config({}),
        allow_external_paths=False,
    )

    assert report["status"] == "ready"
    assert report["asset_ready_count"] == 0
    assert report["source_visual_unavailable_count"] == 1
    assert report["unresolved_count"] == 0
    assert report["status_counts"] == {"source_visual_unavailable": 1}
    assert report["recovery_source_counts"] == {"source_visual_unavailable": 1}
    assert report["articles"][0]["status"] == "source_visual_unavailable"


def test_build_p62_image_recovery_report_keeps_incomplete_source_unavailable_unresolved(
    tmp_path: Path,
) -> None:
    report = build_p62_image_recovery_report(
        generated_at="2026-01-02T03:04:05Z",
        run_dir=tmp_path / "run",
        out_path=tmp_path / "report.json",
        plan_path=tmp_path / "plan.json",
        recovery_root=tmp_path / "recovery",
        plan_candidate_count=1,
        selected_count=1,
        recovered_records=[
            {
                "status": "unresolved",
                "plan_status": "source_visual_unavailable",
                "asset_status": "not_ready",
                "source_visual_unavailable_reason": (
                    "all_label_matches_are_false_or_without_visual_objects"
                ),
                "source_visual_probe_status": "not_found",
                "source_visual_probe": {
                    "status": "not_found",
                    "label_pages": [7],
                    "attempts": [{"status": "skipped_false_label_match"}],
                    "visual_inventory": {"status": "ready", "native_image_count": 0},
                },
            },
        ],
        patched_article_ids=[],
        stage_config=resolve_p62_image_recovery_stage_config({}),
        allow_external_paths=False,
    )

    assert report["status"] == "unresolved"
    assert report["source_visual_unavailable_count"] == 0
    assert report["unresolved_count"] == 1
    assert report["status_counts"] == {"unresolved": 1}
    assert report["articles"][0]["status"] == "unresolved"


def test_build_p62_image_recovery_report_groups_duplicate_source_unavailable_records(
    tmp_path: Path,
) -> None:
    base_record = {
        "status": "source_visual_unavailable",
        "asset_status": "not_ready",
        "source_pdf_path": "paper.pdf",
        "figure_label": "2",
        "resolved_figure_label": "2",
        "source_visual_unavailable_reason": "all_label_matches_are_false_or_without_visual_objects",
        "source_visual_probe_status": "not_found",
        "source_visual_probe": {
            "status": "not_found",
            "label_pages": [12],
            "attempts": [{"status": "skipped_false_label_match"}],
            "visual_inventory": {"status": "ready", "native_image_count": 0},
            "pypdf_image_inventory": {"status": "ready", "image_count": 0},
        },
    }
    report = build_p62_image_recovery_report(
        generated_at="2026-01-02T03:04:05Z",
        run_dir=tmp_path / "run",
        out_path=tmp_path / "report.json",
        plan_path=tmp_path / "plan.json",
        recovery_root=tmp_path / "recovery",
        plan_candidate_count=2,
        selected_count=2,
        recovered_records=[
            {"article": "article_a", **base_record},
            {"article": "article_b", **base_record},
        ],
        patched_article_ids=[],
        stage_config=resolve_p62_image_recovery_stage_config({}),
        allow_external_paths=False,
    )

    assert report["source_visual_unavailable_count"] == 2
    assert report["source_visual_unavailable_group_count"] == 1
    assert report["source_visual_unavailable_groups"] == [
        {
            "source_pdf_path": "paper.pdf",
            "figure_label": "2",
            "source_visual_unavailable_reason": (
                "all_label_matches_are_false_or_without_visual_objects"
            ),
            "raw_record_count": 2,
            "article_count": 2,
            "affected_article_ids": ["article_a", "article_b"],
        }
    ]


def test_build_p62_image_recovery_report_marks_empty_plan_not_required(tmp_path: Path) -> None:
    report = build_p62_image_recovery_report(
        generated_at="2026-01-02T03:04:05Z",
        run_dir=tmp_path / "run",
        out_path=tmp_path / "report.json",
        plan_path=tmp_path / "plan.json",
        recovery_root=tmp_path / "recovery",
        plan_candidate_count=0,
        selected_count=0,
        recovered_records=[],
        patched_article_ids=[],
        stage_config=resolve_p62_image_recovery_stage_config({}),
        allow_external_paths=False,
    )

    assert report["status"] == "not_required"
    assert report["candidate_count"] == 0
    assert report["unresolved_count"] == 0
