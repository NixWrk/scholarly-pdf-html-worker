from pathlib import Path
from typing import Any

from zoteropdf2md.quality_loop.p62_recovery_stage import (
    P62PatchTargetDependencies,
    apply_html_patch_to_targets,
    patch_targets_for_record,
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
