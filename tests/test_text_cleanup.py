from pdf_html_polish.text_cleanup import drop_repeated_phrases


def test_drop_repeated_phrases_collapses_three_or_more_phrase_runs() -> None:
    text = "alpha beta gamma alpha beta gamma alpha beta gamma remains."

    assert drop_repeated_phrases(text) == "alpha beta gamma remains."


def test_drop_repeated_phrases_keeps_two_phrase_mentions() -> None:
    text = "alpha beta gamma alpha beta gamma remains."

    assert drop_repeated_phrases(text) == text
