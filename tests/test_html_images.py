import base64

from zoteropdf2md.html_images import (
    data_image_src_looks_renderable,
    decode_data_image_payload,
    html_node_has_broken_data_image,
    html_node_has_renderable_image,
    html_node_image_srcs,
)


def _data_url(mime: str, blob: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"


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
