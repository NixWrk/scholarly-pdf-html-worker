import base64
from pathlib import Path
import pytest


from pdf_html_polish.quality_loop.cached_images import (
    apply_data_image_cache,
    copy_review_html_with_inline_images,
    local_image_candidates_from_dirs,
    cached_data_image_cache,
    ordered_data_image_cache,
)
from pdf_html_polish.quality_loop.run_utils import write_json

def _jpeg_data_url(label: str) -> str:
    blob = b"\xff\xd8" + label.encode("ascii") + b"\xff\xd9"
    return f"data:image/jpeg;base64,{base64.b64encode(blob).decode('ascii')}"


FIG1_DATA_URL = _jpeg_data_url("figure-one")
FIG2_DATA_URL = _jpeg_data_url("figure-two")
RECOVERED_DATA_URL = _jpeg_data_url("recovered")


def test_ordered_data_image_cache_uses_source_hints_first() -> None:
    raw_html = '<p><img src="fig1.png"/></p><p><img src="fig2.png"/></p>'
    previous_html = (
        f'<p><img data-z2m-src="fig1.png" src="{FIG1_DATA_URL}"/></p>'
        f'<p><img data-z2m-src="fig2.png" src="{FIG2_DATA_URL}"/></p>'
    )

    cache = ordered_data_image_cache(raw_html, previous_html)
    html, count = apply_data_image_cache(raw_html, cache)

    assert cache["fig2.png"] == FIG2_DATA_URL
    assert count == 2
    assert f'data-z2m-src="fig1.png" src="{FIG1_DATA_URL}"' in html
    assert f'data-z2m-src="fig2.png" src="{FIG2_DATA_URL}"' in html


def test_ordered_data_image_cache_uses_matching_figure_unit_when_recovery_adds_images() -> None:
    raw_html = (
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="_page_10_Figure_2.jpeg"/></p>'
        "</div>"
    )
    previous_html = (
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        f'<p class="z2m-figure-target"><img src="{FIG1_DATA_URL}"/></p>'
        "</div>"
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        f'<img src="{RECOVERED_DATA_URL}"/>'
        "</p>"
        "</div>"
    )

    cache = ordered_data_image_cache(raw_html, previous_html)
    html, count = apply_data_image_cache(raw_html, cache)

    assert cache == {"_page_10_Figure_2.jpeg": FIG1_DATA_URL}
    assert count == 1
    assert f'data-z2m-src="_page_10_Figure_2.jpeg" src="{FIG1_DATA_URL}"' in html


def test_cached_data_image_cache_follows_source_run_chain(tmp_path: Path) -> None:
    source = tmp_path / "source"
    ancestor = tmp_path / "ancestor"
    previous_polish = ancestor / "polish" / "doc.02.en.polish.html"
    previous_polish.parent.mkdir(parents=True)
    previous_polish.write_text(f'<img data-z2m-src="fig1.png" src="{FIG1_DATA_URL}"/>', encoding="utf-8")
    write_json(source / "manifest.json", {"source_run_dir": str(ancestor), "articles": [{"article": "doc"}]})
    write_json(ancestor / "manifest.json", {"articles": [{"article": "doc"}]})

    cache, source_path = cached_data_image_cache(source, "doc", '<img src="fig1.png"/>')

    assert cache == {"fig1.png": FIG1_DATA_URL}
    assert source_path == str(previous_polish)


def test_cached_data_image_cache_reads_audit_tree_review_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    previous_polish = source / "audit_tree" / "doc" / "02.en.polish.html"
    previous_polish.parent.mkdir(parents=True)
    previous_polish.write_text(
        f'<img data-z2m-src="fig1.png" src="{FIG1_DATA_URL}"/>',
        encoding="utf-8",
    )
    write_json(source / "manifest.json", {"articles": [{"article": "doc"}]})

    cache, source_path = cached_data_image_cache(source, "doc", '<img src="fig1.png"/>')

    assert cache == {"fig1.png": FIG1_DATA_URL}
    assert source_path == str(previous_polish)


def test_ordered_data_image_cache_does_not_guess_global_image_order() -> None:
    raw_html = '<img src="first.jpg"><img src="second.jpg">'
    previous_html = f'<img src="{FIG2_DATA_URL}"><img src="{FIG1_DATA_URL}">'

    assert ordered_data_image_cache(raw_html, previous_html) == {}



def test_ordered_data_image_cache_recovers_one_unambiguous_legacy_image() -> None:
    raw_html = '<img src="only.jpg">'
    previous_html = f'<img src="{FIG1_DATA_URL}">'

    assert ordered_data_image_cache(raw_html, previous_html) == {
        "only.jpg": FIG1_DATA_URL,
    }

def test_image_cache_rejects_broken_hinted_data_url() -> None:
    raw_html = '<img src="fig1.png">'
    previous_html = '<img data-z2m-src="fig1.png" src="data:image/png;base64,AAAA">'

    cache = ordered_data_image_cache(raw_html, previous_html)
    restored, count = apply_data_image_cache(raw_html, {"fig1.png": "data:image/png;base64,AAAA"})
    remote, remote_count = apply_data_image_cache(
        raw_html,
        {"fig1.png": "https://example.org/not-a-cached-data-image.png"},
    )

    assert cache == {}
    assert restored == raw_html
    assert count == 0

    assert remote == raw_html
    assert remote_count == 0

def test_local_image_candidates_reject_parent_and_absolute_escape(tmp_path: Path) -> None:
    article_dir = tmp_path / "article"
    article_dir.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"\xff\xd8outside\xff\xd9")

    assert local_image_candidates_from_dirs("../outside.jpg", [article_dir]) == []
    assert local_image_candidates_from_dirs(str(outside), [article_dir]) == []


def test_review_copy_refuses_broken_single_file_publication(tmp_path: Path) -> None:
    source_dir = tmp_path / "article"
    source_dir.mkdir()
    source = source_dir / "02.en.polish.html"
    source.write_text('<html><body><img src="missing.jpg"></body></html>', encoding="utf-8")
    target = tmp_path / "review" / "02.en.polish.html"

    with pytest.raises(ValueError, match="unsupported=1"):
        copy_review_html_with_inline_images(source, target)

    assert not target.exists()
