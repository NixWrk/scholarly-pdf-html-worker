from pdf_html_polish.quality_loop.p62_context import recovery_snippets


def test_recovery_snippets_use_surrounding_context_for_warning_only_sequence_gap() -> None:
    html = (
        "<html><body>"
        "<p>The directional control pattern is shown in Figure 3 and depends on bearing angle.</p>"
        '<div id="fig-3" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        '<p data-z2m-origin="sequence-gap-missing-target" '
        'class="z2m-missing-figure-warning z2m-figure-target" role="note">'
        "Figure 3 image was not extracted into this HTML. "
        "Please check the original PDF for the missing visual content."
        "</p>"
        "</div>"
        "<p>The rotational control is shown later.</p>"
        "</body></html>"
    )

    snippets, context, source = recovery_snippets(
        html,
        {
            "snippet": "Figure 3 image was not extracted into this HTML.",
            "extra": {"figure_label": "3", "warning_index": 1},
        },
        context_chars=1000,
    )

    assert source == "warning_text_regex"
    assert "directional control pattern" in context
    assert "Figure 3 image was not extracted" not in context
    assert "Fig. 3" in snippets
