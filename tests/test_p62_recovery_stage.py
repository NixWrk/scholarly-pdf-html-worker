from zoteropdf2md.quality_loop.p62_recovery_stage import resolve_p62_image_recovery_stage_config


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
