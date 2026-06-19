from pdf_html_polish.html_links import (
    attr_value,
    href_attr_literal,
    replace_href_attr_literal,
    unwrap_nested_fig_links,
    unwrap_nested_same_href_internal_links,
)


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


def test_unwrap_nested_fig_links_keeps_inner_figure_link() -> None:
    html = (
        '<a class="z2m-fig-link" href="#fig-1">'
        '<a class="z2m-fig-link" href="#fig-1">Fig. 1</a>'
        "</a>"
    )

    assert unwrap_nested_fig_links(html) == '<a class="z2m-fig-link" href="#fig-1">Fig. 1</a>'


def test_unwrap_nested_same_href_internal_links_keeps_inner_link_and_trailing_punct() -> None:
    html = '<a href="#fig-1" class="outer"><a class="inner" href="#fig-1">Fig. 1</a>).</a>'

    assert unwrap_nested_same_href_internal_links(html) == (
        '<a class="inner" href="#fig-1">Fig. 1</a>).'
    )


def test_unwrap_nested_same_href_internal_links_keeps_different_targets() -> None:
    html = '<a href="#fig-1"><a href="#fig-2">Fig. 2</a></a>'

    assert unwrap_nested_same_href_internal_links(html) == html
