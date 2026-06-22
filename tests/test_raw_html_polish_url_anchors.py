from pdf_html_polish.raw_html_polish.url_anchors import (
    consume_compact_prefix,
    normalize_double_escaped_url_anchor_text,
    repair_prose_prefixed_url_anchor_tail,
    repair_split_scheme_url_anchor_fragments,
    repair_split_scheme_url_anchor_runs,
    repair_split_visible_url_anchors,
    repair_split_url_anchor_block_tail,
    repair_split_url_anchor_domain_tail,
    repair_spaced_protocol_url_anchors,
    unescape_html_entities_repeated,
)


def test_repair_spaced_protocol_url_anchors_repairs_href_and_label() -> None:
    html = (
        '<p>Available online: <a href="http: //www.brailleauthority.org/tg/web-manual/index.html">'
        "http: //www.brailleauthority.org/tg/web-manual/index.html</a></p>"
    )

    repaired = repair_spaced_protocol_url_anchors(html)

    assert 'href="http://www.brailleauthority.org/tg/web-manual/index.html"' in repaired
    assert ">http://www.brailleauthority.org/tg/web-manual/index.html</a>" in repaired
    assert "http: //" not in repaired


def test_repair_spaced_protocol_url_anchors_leaves_nested_label_text() -> None:
    html = '<a href="https: //example.org/path"><span>https: //example.org/path</span></a>'

    repaired = repair_spaced_protocol_url_anchors(html)

    assert 'href="https://example.org/path"' in repaired
    assert "<span>https: //example.org/path</span>" in repaired


def test_repair_spaced_protocol_url_anchors_fast_path_without_http() -> None:
    html = "<p>No URL here.</p>"

    assert repair_spaced_protocol_url_anchors(html) == html


def test_normalize_double_escaped_url_anchor_text_repairs_url_label() -> None:
    html = '<a href="https://example.org/?a=1&amp;b=2">https://example.org/?a=1&amp;amp;b=2</a>'

    assert normalize_double_escaped_url_anchor_text(html) == (
        '<a href="https://example.org/?a=1&amp;b=2">https://example.org/?a=1&amp;b=2</a>'
    )


def test_normalize_double_escaped_url_anchor_text_ignores_non_url_label() -> None:
    html = '<a href="https://example.org/?a=1&amp;b=2">Research &amp;amp; development</a>'

    assert normalize_double_escaped_url_anchor_text(html) == html


def test_consume_compact_prefix_ignores_whitespace() -> None:
    assert consume_compact_prefix(" 20 17.00020 rest", "2017.00020") == (" 20 17.00020", " rest")
    assert consume_compact_prefix(" 20x", "2017") is None


def test_repair_split_visible_url_anchors_repairs_ocr_tail() -> None:
    url = "http://journal.frontiersin.org/article/10.3389/fncir.2017.00020/full#supplementary-material"
    html = (
        '<p>Found <a href="http://journal.frontiersin.org/article/10.3389/fncir.2017.00020/full#supplementary-material">'
        "online at: http://journal.frontiersin.org/article/10.3389/fncir.</a> "
        "2017.00020/full#supplementary-material</p>"
    )

    repaired = repair_split_visible_url_anchors(html)

    assert f'Found online at: <a href="{url}">{url}</a></p>' in repaired
    assert "fncir.</a> 2017.00020" not in repaired


def test_repair_split_visible_url_anchors_leaves_unmatched_tail() -> None:
    html = '<a href="https://example.org/path">https://example.org/</a> different tail'

    assert repair_split_visible_url_anchors(html) == html


def test_repair_split_url_anchor_block_tail_repairs_paragraph_boundary() -> None:
    html = (
        '<p>Online at <a href="http://www.niepce-letters-and-">'
        "http://www.niepce-letters-and-</a></p>"
        "<p>documents.com/book/#/906/ (Date accessed, 18 March 2017)</p>"
    )

    repaired = repair_split_url_anchor_block_tail(html)

    expected_url = "http://www.niepce-letters-and-documents.com/book/#/906/"
    assert f'<a href="{expected_url}">{expected_url}</a> (Date accessed' in repaired
    assert "letters-and-</a></p>" not in repaired


def test_repair_split_url_anchor_block_tail_rejects_non_url_tail() -> None:
    html = '<a href="http://example-">http://example-</a> not-a-domain'

    assert repair_split_url_anchor_block_tail(html) == html


def test_unescape_html_entities_repeated_unwraps_nested_entities() -> None:
    assert unescape_html_entities_repeated("https://example.org/?a=1&amp;amp;b=2") == "https://example.org/?a=1&b=2"


def test_repair_split_url_anchor_domain_tail_repairs_dot_domain_tail() -> None:
    html = (
        '<p>Journal page <a href="http://www.dovepress">http://www.dovepress</a>. '
        "com/testimonials.php to read quotes.</p>"
    )

    repaired = repair_split_url_anchor_domain_tail(html)

    assert ">http://www.dovepress.com/testimonials.php</a> to read quotes." in repaired
    assert "www.dovepress</a>. com" not in repaired


def test_repair_split_url_anchor_domain_tail_rejects_non_url_visible_text() -> None:
    html = '<a href="https://example.org/path">example</a>. org/path'

    assert repair_split_url_anchor_domain_tail(html) == html


def test_repair_prose_prefixed_url_anchor_tail_moves_prose_prefix_outside_anchor() -> None:
    url = "https://example.org/path/supplemental"
    html = f'<p><a href="{url}">Available at: https://example.org/path/</a> supplemental.</p>'

    repaired = repair_prose_prefixed_url_anchor_tail(html)

    assert f'Available at: <a href="{url}">{url}</a>.' in repaired
    assert ">Available at: https://example.org/path/</a>" not in repaired


def test_repair_prose_prefixed_url_anchor_tail_rejects_mismatched_href() -> None:
    html = (
        '<p><a href="https://example.org/path/supplemental">'
        "Available at: https://different.example/path/</a> supplemental.</p>"
    )

    assert repair_prose_prefixed_url_anchor_tail(html) == html


def test_repair_split_scheme_url_anchor_fragments_merges_scheme_and_path_tail() -> None:
    url = "https://example.org/path/supplemental"
    html = f'<p>See https:// <a href="{url}">example.org/path</a> /supplemental</p>'

    repaired = repair_split_scheme_url_anchor_fragments(html)

    assert f'<a href="{url}">{url}</a>' in repaired
    assert 'https:// <a href="' not in repaired


def test_repair_split_scheme_url_anchor_runs_merges_same_href_anchor_chunks() -> None:
    url = "https://example.org/path/supplemental"
    html = (
        f'<p>See https:// <a href="{url}">example.org/path</a> '
        f'<a href="{url}">/supplemental</a></p>'
    )

    repaired = repair_split_scheme_url_anchor_runs(html)

    assert f'<p>See <a href="{url}">{url}</a></p>' == repaired


def test_repair_split_scheme_url_anchor_fragments_rejects_mismatched_next_href() -> None:
    url = "https://example.org/path/supplemental"
    html = (
        f'<p>See https:// <a href="{url}">example.org/path</a> '
        '<a href="https://different.example/path/supplemental">/supplemental</a></p>'
    )

    assert repair_split_scheme_url_anchor_fragments(html) == html
