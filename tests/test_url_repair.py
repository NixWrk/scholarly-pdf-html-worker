from pdf_html_polish.url_repair import (
    compact_visible_url_fragment,
    repair_broken_visible_url_text,
    split_url_fragment_text_prose_tail,
    split_url_and_trailing_punct,
    starts_like_visible_url_fragment,
    strip_wrapping_url_quotes,
    url_fragment_compare_key,
    url_fragment_keys_match_allowing_lost_hyphens,
)


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


def test_url_fragment_helpers_normalize_visible_fragments() -> None:
    assert compact_visible_url_fragment("https://example.org/a &amp; b") == "https://example.org/a&b"
    assert url_fragment_compare_key("(https://Example.org/path/)") == "example.org/path"
    assert url_fragment_keys_match_allowing_lost_hyphens("example.org/a-b", "example.org/ab")


def test_split_url_fragment_text_prose_tail_keeps_access_dates_out_of_url() -> None:
    fragment, consumed = split_url_fragment_text_prose_tail("path/to/page (accessed March 2024)")

    assert fragment == "path/to/page"
    assert consumed == len("path/to/page")


def test_visible_url_fragment_detection_and_quote_stripping() -> None:
    assert starts_like_visible_url_fragment(" doi.org/10.1000/example")
    assert starts_like_visible_url_fragment(" 10.1000/example")
    assert not starts_like_visible_url_fragment("available online")
    assert strip_wrapping_url_quotes(' "https://example.org" ') == "https://example.org"
