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
