from pathlib import Path

from zoteropdf2md.quality_loop.cached_images import (
    apply_data_image_cache,
    cached_data_image_cache,
    ordered_data_image_cache,
)
from zoteropdf2md.quality_loop.run_utils import write_json


def test_ordered_data_image_cache_uses_source_hints_first() -> None:
    raw_html = '<p><img src="fig1.png"/></p><p><img src="fig2.png"/></p>'
    previous_html = (
        '<p><img data-z2m-src="fig1.png" src="data:image/png;base64,AAAA"/></p>'
        '<p><img data-z2m-src="fig2.png" src="data:image/png;base64,BBBB"/></p>'
    )

    cache = ordered_data_image_cache(raw_html, previous_html)
    html, count = apply_data_image_cache(raw_html, cache)

    assert cache["fig2.png"] == "data:image/png;base64,BBBB"
    assert count == 2
    assert 'data-z2m-src="fig1.png" src="data:image/png;base64,AAAA"' in html
    assert 'data-z2m-src="fig2.png" src="data:image/png;base64,BBBB"' in html


def test_ordered_data_image_cache_uses_matching_figure_unit_when_recovery_adds_images() -> None:
    raw_html = (
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="_page_10_Figure_2.jpeg"/></p>'
        "</div>"
    )
    previous_html = (
        '<div id="fig-6" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="data:image/jpeg;base64,FIG6"/></p>'
        "</div>"
        '<div id="fig-7" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img src="data:image/jpeg;base64,RECOVERED7"/>'
        "</p>"
        "</div>"
    )

    cache = ordered_data_image_cache(raw_html, previous_html)
    html, count = apply_data_image_cache(raw_html, cache)

    assert cache == {"_page_10_Figure_2.jpeg": "data:image/jpeg;base64,FIG6"}
    assert count == 1
    assert 'data-z2m-src="_page_10_Figure_2.jpeg" src="data:image/jpeg;base64,FIG6"' in html


def test_cached_data_image_cache_follows_source_run_chain(tmp_path: Path) -> None:
    source = tmp_path / "source"
    ancestor = tmp_path / "ancestor"
    previous_polish = ancestor / "polish" / "doc.02.en.polish.html"
    previous_polish.parent.mkdir(parents=True)
    previous_polish.write_text('<img src="data:image/png;base64,AAAA"/>', encoding="utf-8")
    write_json(source / "manifest.json", {"source_run_dir": str(ancestor), "articles": [{"article": "doc"}]})
    write_json(ancestor / "manifest.json", {"articles": [{"article": "doc"}]})

    cache, source_path = cached_data_image_cache(source, "doc", '<img src="fig1.png"/>')

    assert cache == {"fig1.png": "data:image/png;base64,AAAA"}
    assert source_path == str(previous_polish)


def test_cached_data_image_cache_reads_audit_tree_review_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    previous_polish = source / "audit_tree" / "doc" / "02.en.polish.html"
    previous_polish.parent.mkdir(parents=True)
    previous_polish.write_text(
        '<img data-z2m-src="fig1.png" src="data:image/png;base64,AAAA"/>',
        encoding="utf-8",
    )
    write_json(source / "manifest.json", {"articles": [{"article": "doc"}]})

    cache, source_path = cached_data_image_cache(source, "doc", '<img src="fig1.png"/>')

    assert cache == {"fig1.png": "data:image/png;base64,AAAA"}
    assert source_path == str(previous_polish)
