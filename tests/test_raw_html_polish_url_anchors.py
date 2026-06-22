from pdf_html_polish.raw_html_polish.url_anchors import repair_spaced_protocol_url_anchors


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
