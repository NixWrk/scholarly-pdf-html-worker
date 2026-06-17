from pdf_html_polish.raw_html_polish.url_autolink import (
    autolink_plain_urls,
    autolink_text_urls,
)


def test_autolink_text_urls_links_urls_and_preserves_trailing_punctuation() -> None:
    linked = autolink_text_urls("See https://example.org/path.")

    assert (
        '<a href="https://example.org/path" target="_blank" rel="noopener noreferrer">'
        "https://example.org/path</a>."
    ) in linked


def test_autolink_text_urls_links_split_doi() -> None:
    linked = autolink_text_urls("Journal doi: 10.1002/ nau.22813.")

    assert (
        'doi:<a href="https://doi.org/10.1002/nau.22813" '
        'target="_blank" rel="noopener noreferrer">10.1002/nau.22813</a>.'
    ) in linked


def test_autolink_text_urls_strips_url_connector_from_link_body() -> None:
    linked = autolink_text_urls("Apps include www.wysa.com/and another app.")

    assert (
        '<a href="https://www.wysa.com/" target="_blank" rel="noopener noreferrer">'
        "www.wysa.com/</a>and"
    ) in linked


def test_autolink_plain_urls_skips_existing_links_and_code() -> None:
    html = (
        '<p>See https://example.org.</p>'
        '<a href="https://already.test">https://already.test</a>'
        "<code>www.code.test</code>"
    )

    linked = autolink_plain_urls(html)

    assert 'href="https://example.org"' in linked
    assert '<a href="https://already.test">https://already.test</a>' in linked
    assert "<code>www.code.test</code>" in linked
    assert linked.count('href="https://already.test"') == 1


def test_autolink_plain_urls_skips_escaped_anchor_snippets() -> None:
    html = (
        "<p>&lt;a href=&quot;https://example.org&quot;&gt;"
        "https://example.org&lt;/a&gt;</p>"
    )

    linked = autolink_plain_urls(html)

    assert linked == html
