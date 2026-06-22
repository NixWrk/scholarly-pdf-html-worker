from pdf_html_polish.raw_html_polish.url_text_repair import (
    repair_broken_plain_url_text,
    repair_broken_url_anchor_labels,
    split_trailing_prose_url,
)


def test_repair_broken_plain_url_text_repairs_visible_text_outside_links() -> None:
    html = "<p>See https:// www.who. int/ blindness /causes/trends/en/ today.</p>"

    repaired = repair_broken_plain_url_text(html)

    assert "https://www.who.int/blindness/causes/trends/en/" in repaired
    assert "https:// www.who. int" not in repaired


def test_repair_broken_plain_url_text_skips_anchor_text() -> None:
    html = '<p><a href="https://www.who.int/">https:// www.who. int/</a></p>'

    assert repair_broken_plain_url_text(html) == html


def test_repair_broken_url_anchor_labels_repairs_visible_label() -> None:
    href = "https://www.who.int/blindness/causes/trends/en/"
    html = f'<p><a href="{href}">https:// www.who. int/ blindness /causes/trends/en/</a></p>'

    repaired = repair_broken_url_anchor_labels(html)

    assert repaired == f'<p><a href="{href}">{href}</a></p>'


def test_repair_broken_url_anchor_labels_keeps_sentence_period_outside_anchor() -> None:
    href = "http://www.3dphotoworks.com"
    html = f'<p>DPhotoWorks website is at <a href="{href}"> http://www.3dphotoworks.com. </a></p>'

    repaired = repair_broken_url_anchor_labels(html)

    assert repaired == f'<p>DPhotoWorks website is at <a href="{href}">{href}</a>.</p>'


def test_repair_broken_url_anchor_labels_collapses_duplicate_visible_label() -> None:
    href = "https://example.org/path"
    html = f'<p><a href="{href}">{href}{href}</a></p>'

    repaired = repair_broken_url_anchor_labels(html)

    assert repaired == f'<p><a href="{href}">{href}</a></p>'


def test_split_trailing_prose_url_detects_url_with_sentence_tail() -> None:
    assert split_trailing_prose_url("https://example.org/path) applies to all groups") == (
        "https://example.org/path",
        ") applies to all groups",
    )
    assert split_trailing_prose_url("https://example/path) applies to all groups") is None
