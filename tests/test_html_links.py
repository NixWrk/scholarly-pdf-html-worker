from pdf_html_polish.html_links import attr_value, href_attr_literal, replace_href_attr_literal


def test_href_attr_literal_preserves_escaped_href_text() -> None:
    attrs = ' class="link" href="https://example.org/a&amp;b" data-id="1"'

    assert href_attr_literal(attrs) == "https://example.org/a&amp;b"
    assert attr_value(attrs, "href") == "https://example.org/a&b"


def test_href_attr_literal_allows_double_quotes_inside_single_quoted_href() -> None:
    attrs = ' class="link" href=\'"https://example.org/path"\''

    assert href_attr_literal(attrs) == '"https://example.org/path"'


def test_replace_href_attr_literal_escapes_new_href() -> None:
    attrs = "class='link' href='old' title=\"same\""

    replaced = replace_href_attr_literal(attrs, 'https://example.org/a?x=1&y="q"<tag>')

    assert replaced == (
        "class='link' "
        'href="https://example.org/a?x=1&amp;y=&quot;q&quot;&lt;tag&gt;" '
        'title="same"'
    )


def test_replace_href_attr_literal_leaves_attrs_without_href_unchanged() -> None:
    attrs = 'class="link" title="same"'

    assert replace_href_attr_literal(attrs, "https://example.org") == attrs
