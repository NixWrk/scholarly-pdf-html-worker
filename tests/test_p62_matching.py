from zoteropdf2md.quality_loop.p62_matching import (
    best_pdf_text_page,
    caption_head_present_near_label,
    caption_head_tokens,
    false_page_match_hint,
    figure_label_present_in_text_strict,
    full_figure_label_from_context,
    label_looks_caption_like,
)


def test_full_figure_label_from_context_expands_hierarchical_label() -> None:
    context = "The recovered caption reads Figure 3-1. Navigation setup and trial layout."

    assert full_figure_label_from_context(context, "3") == "3-1"


def test_strict_figure_label_match_does_not_match_hierarchical_prefix() -> None:
    assert figure_label_present_in_text_strict("Figure 3-1 shows the apparatus.", "3") is False
    assert figure_label_present_in_text_strict("Figure 3 shows the apparatus.", "3") is True


def test_false_page_match_hint_classifies_common_non_visual_pages() -> None:
    assert false_page_match_hint("Contents ..... Figure 2 ..... 14", "2") == "toc_or_contents"
    assert false_page_match_hint("Please insert Figure 4 near this placeholder.", "4") == "manuscript_placeholder"
    assert false_page_match_hint("References\nPrior work discusses Figure 5 in passing.", "5") == "backmatter_or_reference_text"


def test_caption_head_matching_keeps_true_caption_despite_parenthetical_reference() -> None:
    snippets = ["Figure 8. Fluorescence response after stimulation in the virtual task."]
    page_text = (
        "Earlier work mentioned (Figure 8) in prose. "
        "Figure 8. Fluorescence response after stimulation in the virtual navigation task."
    )

    assert caption_head_tokens(snippets, "8")[:3] == ["fluorescence", "response", "after"]
    assert caption_head_present_near_label(page_text, "8", snippets) is True
    assert label_looks_caption_like(page_text, "8") is False


def test_best_pdf_text_page_scores_snippet_overlap() -> None:
    page, score = best_pdf_text_page(
        ["Figure 6. Cortical electrode activation map and phosphene shapes."],
        [
            "Generic methods and participant recruitment.",
            "Figure 6. Cortical electrode activation map and phosphene shapes.",
        ],
    )

    assert page == 2
    assert score > 0.5
