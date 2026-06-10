from zoteropdf2md.quality_loop.p62_context import (
    clean_context_fragment,
    recovery_snippets,
    warning_context_from_html,
)


def test_clean_context_fragment_removes_missing_warning_boilerplate_and_images() -> None:
    fragment = (
        "<p>Figure 2 image was not extracted into this HTML. "
        "Please check the original PDF for the missing visual content.</p>"
        "<p><img src='data:image/png;base64,AAAA'> Real caption text.</p>"
    )

    assert clean_context_fragment(fragment) == "[image] Real caption text."


def test_warning_context_from_html_selects_matching_label_and_warning_index() -> None:
    html = (
        "<div><p>Figure 1 image was not extracted into this HTML.</p>"
        "<p>Wrong nearby context.</p></div>"
        "<div class='z2m-missing'><p>Figure 2 image was not extracted into this HTML.</p>"
        "<p>Expected nearby context.</p></div>"
    )
    defect = {"extra": {"figure_label": "2", "warning_index": 1}}

    context, source = warning_context_from_html(html, defect, radius=800)

    assert source == "warning_text_regex"
    assert "Expected nearby context" in context
    assert "Wrong nearby context" not in context


def test_recovery_snippets_falls_back_to_defect_snippet_when_warning_missing() -> None:
    defect = {
        "snippet": "Figure 4 missing visual near the methods section",
        "extra": {"figure_label": "4"},
    }

    snippets, context, source = recovery_snippets("", defect, context_chars=1200)

    assert context == ""
    assert source == "html_unavailable"
    assert snippets == ["Figure 4 missing visual near the methods section"]
