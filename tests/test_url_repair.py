from zoteropdf2md.url_repair import repair_broken_visible_url_text, split_url_and_trailing_punct


def test_split_url_and_trailing_punct_keeps_balanced_delimiters() -> None:
    assert split_url_and_trailing_punct("https://example.org/a(b).") == ("https://example.org/a(b)", ".")
    assert split_url_and_trailing_punct("https://example.org/a(b)).") == ("https://example.org/a(b)", ").")
    assert split_url_and_trailing_punct("https://example.org/a[1]].") == ("https://example.org/a[1]", "].")


def test_repair_broken_visible_url_text_joins_known_ocr_splits() -> None:
    assert repair_broken_visible_url_text("hps://dl.acm.org/doi/10.1145/3155286") == (
        "https://dl.acm.org/doi/10.1145/3155286"
    )
    assert repair_broken_visible_url_text("https:// www.who. int/ blindness /causes/trends/en/") == (
        "https://www.who.int/blindness/causes/trends/en/"
    )
    assert repair_broken_visible_url_text("doi: 10.1002/ nau.22813") == "doi: 10.1002/nau.22813"
