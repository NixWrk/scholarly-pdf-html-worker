import base64

import pytest

import pdf_html_polish.html_images as html_images_module

from pdf_html_polish.html_images import (
    data_image_src_looks_renderable,
    decode_data_image_payload,
    html_node_has_broken_data_image,
    html_node_has_renderable_image,
    html_node_image_srcs,
    inspect_inline_image_integrity,
    inline_images_from_html_text,
    refresh_inlined_data_urls_by_cache,
    refresh_inlined_data_urls_by_hint,
    resolve_local_image_candidate,
)
from pdf_html_polish.single_file_html import polish_and_inline_html_file


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
    assert not data_image_src_looks_renderable("data:image/png,not-base64")
    assert data_image_src_looks_renderable("https://example.org/image.png")
    assert not data_image_src_looks_renderable("data:image/png,not-a-png")
    assert data_image_src_looks_renderable("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>")
    assert data_image_src_looks_renderable("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'/>")
    assert data_image_src_looks_renderable(_data_url("image/svg+xml", b"<svg></svg>"))
    assert not data_image_src_looks_renderable(_data_url("image/svg+xml", b"not-svg"))


def test_data_image_src_renderability_accepts_ascii_whitespace_after_end_marker() -> None:
    adobe_jpeg = b"\xff\xd8\xff\xee\x00\x0eAdobe\x00payload\xff\xd9\n"

    assert data_image_src_looks_renderable(_data_url("image/jpeg", adobe_jpeg))
    assert html_node_has_renderable_image(f'<img src="{_data_url("image/jpeg", adobe_jpeg)}">')
    assert not html_node_has_broken_data_image(f'<img src="{_data_url("image/jpeg", adobe_jpeg)}">')


def test_inline_image_integrity_counts_only_live_unresolved_images() -> None:
    valid_png = _data_url("image/png", _valid_png_blob())
    broken_png = "data:image/png;base64,AAAA"
    html = (
        f'<img src="{valid_png}">'
        '<img data-z2m-inline-skip="legacy" src="https://example.org/image.png">'
        '<img data-z2m-inline-skip="missing_sidecar" src="figures/missing.png">'
        "<img alt=\"missing src\">"
        f'<img src="{broken_png}">'
        '<script>const sample = \'<img src="script.png">\';</script>'
        '<!-- <img src="comment.png"> -->'
    )

    integrity = inspect_inline_image_integrity(html)

    assert integrity.image_count == 5
    assert integrity.missing_src_count == 1
    assert integrity.unsupported_src_count == 1
    assert integrity.broken_data_url_count == 1
    assert integrity.inline_skip_count == 1
    assert not integrity.publishable


def test_inline_image_integrity_accepts_renderable_inline_and_remote_images() -> None:
    valid_png = _data_url("image/png", _valid_png_blob())
    integrity = inspect_inline_image_integrity(
        f'<img data-z2m-inline-skip="legacy" src="{valid_png}">'
        '<img data-z2m-inline-skip="legacy" src="https://example.org/image.png">'
    )

    assert integrity.image_count == 2
    assert integrity.inline_skip_count == 0
    assert integrity.publishable


def test_resolve_local_image_candidate_rejects_encoded_parent_escape(tmp_path) -> None:
    base_dir = tmp_path / "article"
    base_dir.mkdir()
    inside = base_dir / "inside.png"
    outside = tmp_path / "outside.png"
    inside.write_bytes(_valid_png_blob())
    outside.write_bytes(_valid_png_blob())

    assert resolve_local_image_candidate(base_dir, "inside.png?cache=1") == inside
    assert resolve_local_image_candidate(base_dir, "../outside.png") is None
    assert resolve_local_image_candidate(base_dir, "%2e%2e/outside.png") is None


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


def test_refresh_image_cache_clears_stale_skip_on_valid_payload() -> None:
    cached_data_url = _data_url("image/png", _valid_png_blob())
    html = (
        '<img data-z2m-image-key="img-1" data-z2m-inline-skip="old-budget" '
        f'src="{cached_data_url}">'
    )

    refreshed, count = refresh_inlined_data_urls_by_cache(
        html,
        image_cache={"img-1": cached_data_url},
    )

    assert count == 0
    assert "data-z2m-inline-skip" not in refreshed
    assert f'src="{cached_data_url}"' in refreshed


def test_refresh_image_cache_restores_valid_but_changed_payload() -> None:
    cached_data_url = _data_url("image/png", _valid_png_blob())
    changed_data_url = _data_url("image/jpeg", b"\xff\xd8other\xff\xd9")
    html = (
        '<img data-z2m-image-key="img-1" data-z2m-src="original.png" '
        f'src="{changed_data_url}">'
    )

    refreshed, count = refresh_inlined_data_urls_by_cache(
        html,
        image_cache={"img-1": cached_data_url},
    )

    assert count == 1
    assert changed_data_url not in refreshed
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


def test_inline_images_from_html_text_inlines_large_sidecar_by_default(tmp_path) -> None:
    image_path = tmp_path / "large.jpg"
    image_path.write_bytes(b"\xff\xd8" + (b"x" * (2 * 1024 * 1024 + 1)) + b"\xff\xd9")
    html = '<html><body><img alt="Large" src="large.jpg"></body></html>'

    result, image_cache = inline_images_from_html_text(html, tmp_path)

    assert result.inlined_images == 1
    assert len(image_cache) == 1
    assert "data:image/jpeg;base64" in result.html
    assert 'data-z2m-src="large.jpg"' in result.html
    assert "data-z2m-inline-skip" not in result.html
    assert ' src="data:image/jpeg;base64,' in result.html


def test_inline_images_from_html_text_skips_sidecar_over_image_limit(tmp_path) -> None:
    image_path = tmp_path / "large.png"
    image_path.write_bytes(_valid_png_blob())
    html = '<html><body><img alt="Large" src="large.png"></body></html>'

    result, image_cache = inline_images_from_html_text(
        html,
        tmp_path,
        max_image_bytes=16,
        max_total_bytes=10_000,
    )

    assert result.inlined_images == 0
    assert image_cache == {}
    assert "data:image/png;base64" not in result.html
    assert 'src="large.png"' in result.html
    assert 'data-z2m-inline-skip="image_too_large"' in result.html


def test_inline_images_from_html_text_downscales_oversized_sidecar_before_skip(tmp_path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "large.bmp"
    Image.new("RGB", (2200, 2200), (110, 80, 40)).save(image_path, format="BMP")
    original_size = image_path.stat().st_size
    html = '<html><body><img alt="Large" src="large.bmp"></body></html>'

    result, image_cache = inline_images_from_html_text(
        html,
        tmp_path,
        max_image_bytes=1_000_000,
        max_total_bytes=1_000_000,
    )

    assert result.inlined_images == 1
    assert "data-z2m-inline-skip" not in result.html
    assert 'data-z2m-src="large.bmp"' in result.html
    assert 'src="data:image/jpeg;base64,' in result.html
    decoded = decode_data_image_payload(next(iter(image_cache.values())))
    assert decoded is not None
    assert len(decoded[1]) <= 1_000_000
    assert len(decoded[1]) < original_size


def test_inline_images_from_html_text_downscales_above_default_style_threshold(tmp_path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "atlas.bmp"
    Image.new("RGB", (300, 300), (90, 120, 150)).save(image_path, format="BMP")
    html = '<html><body><img alt="Atlas" src="atlas.bmp"></body></html>'

    result, image_cache = inline_images_from_html_text(
        html,
        tmp_path,
        downscale_bytes=8_000,
        hard_max_image_bytes=1_000_000,
    )

    assert result.inlined_images == 1
    assert 'src="data:image/jpeg;base64,' in result.html
    decoded = decode_data_image_payload(next(iter(image_cache.values())))
    assert decoded is not None
    assert len(decoded[1]) < image_path.stat().st_size


def test_polish_and_inline_preserves_downscaled_payload(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "atlas.bmp"
    Image.new("RGB", (300, 300), (90, 120, 150)).save(image_path, format="BMP")
    original_size = image_path.stat().st_size
    html_path = tmp_path / "article.html"
    html_path.write_text(
        '<html><body><img alt="Atlas" src="atlas.bmp"></body></html>',
        encoding="utf-8",
    )
    monkeypatch.setenv("PDF_HTML_INLINE_IMAGE_MAX_BYTES", "0")
    monkeypatch.setenv("PDF_HTML_INLINE_IMAGE_TOTAL_MAX_BYTES", "0")
    monkeypatch.setenv("PDF_HTML_INLINE_IMAGE_DOWNSCALE_BYTES", "8000")
    monkeypatch.setenv("PDF_HTML_INLINE_IMAGE_HARD_MAX_BYTES", "1000000")

    result = polish_and_inline_html_file(html_path)

    sources = html_node_image_srcs(result.html)
    assert len(sources) == 1
    assert sources[0].startswith("data:image/jpeg;base64,")
    decoded = decode_data_image_payload(sources[0])
    assert decoded is not None
    assert len(decoded[1]) < original_size
    assert 'data-z2m-src="atlas.bmp"' in result.html
    assert "data-z2m-inline-skip" not in result.html


def test_inline_images_from_html_text_hard_skips_when_recompression_fails(tmp_path) -> None:
    image_path = tmp_path / "broken.jpg"
    image_path.write_bytes(b"\xff\xd8\xff" + (b"x" * 100) + b"\xff\xd9")
    html = '<html><body><img alt="Broken" src="broken.jpg"></body></html>'

    result, image_cache = inline_images_from_html_text(
        html,
        tmp_path,
        downscale_bytes=32,
        hard_max_image_bytes=64,
    )

    assert result.inlined_images == 0
    assert image_cache == {}
    assert 'src="broken.jpg"' in result.html
    assert 'data-z2m-inline-skip="image_hard_limit_exceeded"' in result.html


def test_inline_images_from_html_text_keeps_soft_limit_fallback(tmp_path) -> None:
    image_path = tmp_path / "unusual.jpg"
    image_path.write_bytes(b"\xff\xd8\xff" + (b"x" * 40) + b"\xff\xd9")
    html = '<html><body><img alt="Unusual" src="unusual.jpg"></body></html>'

    result, _ = inline_images_from_html_text(
        html,
        tmp_path,
        downscale_bytes=16,
        hard_max_image_bytes=128,
    )

    assert result.inlined_images == 1
    assert 'src="data:image/jpeg;base64,' in result.html
    assert "data-z2m-inline-skip" not in result.html


def test_inline_images_from_html_text_rejects_parent_path_escape(tmp_path) -> None:
    article_dir = tmp_path / "article"
    article_dir.mkdir()
    outside_image = tmp_path / "outside.png"
    outside_image.write_bytes(_valid_png_blob())
    html = '<html><body><img alt="Outside" src="../outside.png"></body></html>'

    result, image_cache = inline_images_from_html_text(html, article_dir)

    assert result.inlined_images == 0
    assert image_cache == {}
    assert 'src="../outside.png"' in result.html


def test_inline_images_from_html_text_rejects_symlink_escape(tmp_path) -> None:
    article_dir = tmp_path / "article"
    article_dir.mkdir()
    outside_image = tmp_path / "outside.png"
    outside_image.write_bytes(_valid_png_blob())
    link = article_dir / "linked.png"
    try:
        link.symlink_to(outside_image)
    except OSError:
        pytest.skip("symlinks are unavailable")

    result, image_cache = inline_images_from_html_text(
        '<html><body><img alt="Outside" src="linked.png"></body></html>',
        article_dir,
    )

    assert result.inlined_images == 0
    assert image_cache == {}
    assert 'src="linked.png"' in result.html


def test_inline_images_from_html_text_skips_after_document_budget(tmp_path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(_valid_png_blob())
    second.write_bytes(_valid_png_blob())
    first_size = len(first.read_bytes())
    html = '<html><body><img src="first.png"><img src="second.png"></body></html>'

    result, image_cache = inline_images_from_html_text(
        html,
        tmp_path,
        max_image_bytes=10_000,
        max_total_bytes=first_size + 1,
    )

    assert result.inlined_images == 1
    assert len(image_cache) == 1
    assert result.html.count("data:image/png;base64") == 1
    assert 'src="second.png"' in result.html
    assert 'data-z2m-inline-skip="document_inline_budget_exceeded"' in result.html


def test_inline_images_preserves_valid_data_urls_without_sidecar_hint(tmp_path) -> None:
    first_blob = b"\xff\xd8first\xff\xd9"
    second_blob = b"\xff\xd8second\xff\xd9"
    (tmp_path / "a.jpg").write_bytes(first_blob)
    (tmp_path / "b.jpg").write_bytes(second_blob)
    first_url = _data_url("image/jpeg", first_blob)
    second_url = _data_url("image/jpeg", second_blob)
    html = f'<img src="{second_url}"><img src="{first_url}">'

    result, _ = inline_images_from_html_text(html, tmp_path)

    assert html_node_image_srcs(result.html) == [second_url, first_url]
    assert "data-z2m-src" not in result.html


def test_refresh_inlined_data_urls_by_hint_rejects_parent_escape(tmp_path) -> None:
    article_dir = tmp_path / "article"
    article_dir.mkdir()
    outside_image = tmp_path / "outside.png"
    outside_image.write_bytes(_valid_png_blob())
    broken_data_url = "data:image/png;base64,AAAA"
    html = f'<img data-z2m-src="../outside.png" src="{broken_data_url}">'

    refreshed, count = refresh_inlined_data_urls_by_hint(html, base_dir=article_dir)

    assert count == 0
    assert broken_data_url in refreshed


def test_inline_images_clears_stale_skip_metadata_after_success(tmp_path) -> None:
    image_path = tmp_path / "plot.png"
    image_path.write_bytes(_valid_png_blob())
    html = (
        '<img data-z2m-inline-skip="image_too_large" '
        'data-z2m-inline-size="100" data-z2m-inline-limit="10" src="plot.png">'
    )

    result, _ = inline_images_from_html_text(html, tmp_path)

    assert 'src="data:image/png;base64,' in result.html
    assert "data-z2m-inline-skip" not in result.html
    assert "data-z2m-inline-size" not in result.html
    assert "data-z2m-inline-limit" not in result.html


def test_inline_image_integrity_ignores_inert_html() -> None:
    valid_data_url = _data_url("image/png", _valid_png_blob())
    html = (
        '<!-- <img src="missing.png"> -->'
        '<script>const sample = `<img src="missing.png">`;</script>'
        '<style>.sample::after { content: "<img src=missing.png>"; }</style>'
        f'<img src="{valid_data_url}">'
    )

    integrity = inspect_inline_image_integrity(html)

    assert integrity.image_count == 1
    assert integrity.publishable


def test_inline_image_integrity_reports_publication_failures() -> None:
    html = (
        "<img>"
        '<img data-z2m-inline-skip="budget" src="relative.png">'
        '<img src="data:image/png;base64,AAAA">'
        '<img src="https://example.org/image.png">'
    )

    integrity = inspect_inline_image_integrity(html)

    assert integrity.image_count == 4
    assert integrity.missing_src_count == 1
    assert integrity.unsupported_src_count == 1
    assert integrity.broken_data_url_count == 1
    assert integrity.inline_skip_count == 1
    assert not integrity.publishable


def test_polish_and_inline_rejects_unpublished_local_image(tmp_path) -> None:
    html_path = tmp_path / "article.html"
    html_path.write_text(
        '<html><body><img alt="Missing" src="missing.png"></body></html>',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unsupported_src=1"):
        polish_and_inline_html_file(html_path)


def test_large_data_image_validation_decodes_only_small_edges(monkeypatch) -> None:
    blob = b"\xff\xd8" + (b"x" * (1024 * 1024)) + b"\xff\xd9"
    data_url = _data_url("image/jpeg", blob)
    real_decode = base64.b64decode
    decoded_input_sizes: list[int] = []

    def guarded_decode(value, *args, **kwargs):
        decoded_input_sizes.append(len(value))
        return real_decode(value, *args, **kwargs)

    monkeypatch.setattr(html_images_module.base64, "b64decode", guarded_decode)

    assert data_image_src_looks_renderable(data_url)
    assert decoded_input_sizes
    assert max(decoded_input_sizes) <= 44


def test_large_data_image_validation_rejects_invalid_middle_character() -> None:
    blob = b"\xff\xd8" + (b"x" * 4096) + b"\xff\xd9"
    data_url = _data_url("image/jpeg", blob)
    comma = data_url.index(",")
    middle = comma + 1 + (len(data_url) - comma - 1) // 2
    corrupted = f"{data_url[:middle]}!{data_url[middle + 1:]}"

    assert not data_image_src_looks_renderable(corrupted)
