import base64

from pdf_html_polish.html_images import (
    data_image_src_looks_renderable,
    decode_data_image_payload,
    html_node_has_broken_data_image,
    html_node_has_renderable_image,
    html_node_image_srcs,
    inline_images_from_html_text,
    refresh_inlined_data_urls_by_cache,
    refresh_inlined_data_urls_by_hint,
)


def _data_url(mime: str, blob: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"


def _valid_png_blob() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )


def test_decode_data_image_payload_handles_full_data_urls_and_raw_base64() -> None:
    jpeg = b"\xff\xd8\xffjpeg-bytes\xff\xd9"
    data_url = _data_url("image/jpeg", jpeg)

    assert decode_data_image_payload(data_url) == ("image/jpeg", jpeg)
    assert decode_data_image_payload(base64.b64encode(jpeg).decode("ascii")) == ("image/jpeg", jpeg)


def test_data_image_src_renderability_detects_truncated_known_images() -> None:
    valid_gif = _data_url("image/gif", b"GIF89a123;")
    truncated_png = "data:image/png;base64,iVBORw0KGgo="

    assert data_image_src_looks_renderable(valid_gif)
    assert not data_image_src_looks_renderable(truncated_png)
    assert data_image_src_looks_renderable("https://example.org/image.png")


def test_html_node_image_helpers_extract_and_classify_sources() -> None:
    valid_jpeg = _data_url("image/jpeg", b"\xff\xd8ok\xff\xd9")
    broken_jpeg = _data_url("image/jpeg", b"\xff\xd8missing-end-marker")
    node = f'<p><img src="{valid_jpeg}"><img alt="bad" src=\'{broken_jpeg}\'></p>'

    assert html_node_image_srcs(node) == [valid_jpeg, broken_jpeg]
    assert html_node_has_renderable_image(node)
    assert html_node_has_broken_data_image(node)


def test_refresh_inlined_data_urls_by_hint_restores_sidecar_payload(tmp_path) -> None:
    image_path = tmp_path / "img.png"
    image_path.write_bytes(_valid_png_blob())
    broken_data_url = "data:image/png;base64,AAAA"
    html = f'<p><img data-z2m-src="img.png" src="{broken_data_url}"></p>'

    refreshed, count = refresh_inlined_data_urls_by_hint(html, base_dir=tmp_path)

    assert count == 1
    assert broken_data_url not in refreshed
    assert f'src="{_data_url("image/png", image_path.read_bytes())}"' in refreshed


def test_refresh_inlined_data_urls_by_cache_restores_broken_payload() -> None:
    cached_data_url = _data_url("image/png", _valid_png_blob())
    broken_data_url = "data:image/png;base64,AAAA"
    html = f'<p><img data-z2m-image-key="img-1" src="{broken_data_url}"></p>'

    refreshed, count = refresh_inlined_data_urls_by_cache(
        html,
        image_cache={"img-1": cached_data_url},
    )

    assert count == 1
    assert broken_data_url not in refreshed
    assert f'src="{cached_data_url}"' in refreshed


def test_inline_images_from_html_text_inlines_sidecar_and_records_cache(tmp_path) -> None:
    image_path = tmp_path / "plot.png"
    image_path.write_bytes(_valid_png_blob())
    html = '<html><body><img alt="Plot" src="plot.png"></body></html>'

    result, image_cache = inline_images_from_html_text(html, tmp_path)

    expected_data_url = _data_url("image/png", image_path.read_bytes())
    assert result.inlined_images == 1
    assert f'src="{expected_data_url}"' in result.html
    assert 'data-z2m-src="plot.png"' in result.html
    assert 'data-z2m-image-key="' in result.html
    assert list(image_cache.values()) == [expected_data_url]
