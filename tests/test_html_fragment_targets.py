from __future__ import annotations

from pathlib import Path

from pdf_html_polish.html_fragment_targets import (
    repair_duplicate_fragment_targets,
    unwrap_broken_local_fragment_links,
)
from pdf_html_polish.single_file_html import polish_and_inline_html_file


def test_duplicate_fragment_targets_retarget_links_to_their_own_chunks() -> None:
    html = (
        '<section data-zotero-worker-chunk="1" data-pages="1-10">'
        '<figure id="fig-1">first</figure>'
        '<a href="#fig-1" aria-describedby="fig-1">first link</a>'
        '</section>'
        '<section data-zotero-worker-chunk="2" data-pages="11-20">'
        '<a href="#fig-1" aria-describedby="fig-1">second link</a>'
        '<figure id="fig-1">second</figure>'
        '</section>'
    )

    repaired = repair_duplicate_fragment_targets(html)

    assert repaired.duplicate_target_count == 1
    assert repaired.renamed_target_count == 1
    assert repaired.rewritten_reference_count == 2
    assert repaired.html.count('id="fig-1"') == 1
    assert 'id="fig-1--z2m-p11-20"' in repaired.html
    assert repaired.html.count('href="#fig-1"') == 1
    assert 'href="#fig-1--z2m-p11-20"' in repaired.html
    assert 'aria-describedby="fig-1--z2m-p11-20"' in repaired.html


def test_duplicate_fragment_targets_choose_nearest_target_within_one_chunk() -> None:
    html = (
        '<section data-zotero-worker-chunk="1" data-pages="1-10">'
        '<div id="note"><a href="#note">first</a></div>'
        '<p>separator</p>'
        '<div id="note"><a href="#note">second</a></div>'
        '</section>'
    )

    repaired = repair_duplicate_fragment_targets(html)

    assert repaired.html.count('id="note"') == 1
    assert 'id="note--z2m-p1-10"' in repaired.html
    assert repaired.html.count('href="#note"') == 1
    assert repaired.html.count('href="#note--z2m-p1-10"') == 1


def test_duplicate_fragment_targets_rewrite_idrefs_and_css_urls() -> None:
    html = (
        '<section data-zotero-worker-chunk="1" data-pages="1-10">'
        '<div id="panel">first</div></section>'
        '<section data-zotero-worker-chunk="2" data-pages="11-20">'
        '<label for="panel" aria-controls="panel unique" '
        'style="clip-path:url(#panel)">second</label>'
        '<div id="panel">second</div><div id="unique">unique</div>'
        '</section>'
    )

    repaired = repair_duplicate_fragment_targets(html)

    assert 'id="panel--z2m-p11-20"' in repaired.html
    assert 'for="panel--z2m-p11-20"' in repaired.html
    assert 'aria-controls="panel--z2m-p11-20 unique"' in repaired.html
    assert 'url(#panel--z2m-p11-20)' in repaired.html


def test_duplicate_fragment_target_repair_leaves_unique_html_unchanged() -> None:
    html = (
        '<script>const sample = \'<p id="fake">x</p>\';</script>'
        '<p id="real"><a href="#real">real</a></p>'
    )

    repaired = repair_duplicate_fragment_targets(html)

    assert repaired.html == html
    assert repaired.duplicate_target_count == 0
    assert repaired.renamed_target_count == 0
    assert repaired.rewritten_reference_count == 0


def test_broken_local_fragment_links_are_unwrapped_after_targets_settle() -> None:
    html = (
        '<p id="valid">target</p>'
        '<p><a href="#valid"><strong>valid</strong></a> '
        '<a class="z2m-ref-link" href="#missing%2Dref"><em>missing</em></a> '
        '<a href="#page--1-0">page text</a></p>'
    )

    repaired = unwrap_broken_local_fragment_links(html)

    assert repaired.unwrapped_link_count == 2
    assert '<a href="#valid"><strong>valid</strong></a>' in repaired.html
    assert '<em>missing</em>' in repaired.html
    assert 'href="#missing%2Dref"' not in repaired.html
    assert 'href="#page--1-0"' not in repaired.html
    assert "page text" in repaired.html


def test_broken_local_fragment_links_use_named_anchor_targets() -> None:
    html = '<a name="legacy"></a><p><a href="#legacy">valid</a></p>'

    repaired = unwrap_broken_local_fragment_links(html)

    assert repaired.html == html
    assert repaired.unwrapped_link_count == 0


def test_fragment_repairs_ignore_raw_text_and_html_comments() -> None:
    html = (
        '<!-- <p id="valid"><a href="#missing">comment link</a></p> -->'
        '<script>const template = \'<p id="valid">'
        '<a href="#missing">script link</a></p>\';</script>'
        '<style>.sample { clip-path: url(#missing); }</style>'
        '<p id="valid">real target</p>'
        '<a href="#missing"><em>real missing link</em></a>'
    )

    duplicate_repair = repair_duplicate_fragment_targets(html)
    link_repair = unwrap_broken_local_fragment_links(html)

    assert duplicate_repair.html == html
    assert duplicate_repair.duplicate_target_count == 0
    assert '<a href="#missing">comment link</a>' in link_repair.html
    assert '<a href="#missing">script link</a>' in link_repair.html
    assert "url(#missing)" in link_repair.html
    assert '<a href="#missing"><em>real missing link</em></a>' not in link_repair.html
    assert "<em>real missing link</em>" in link_repair.html
    assert link_repair.unwrapped_link_count == 1


def test_post_polish_pipeline_repairs_duplicate_chunk_ids(tmp_path: Path) -> None:
    html_path = tmp_path / "chunked.html"
    html_path.write_text(
        '<html data-zotero-worker-chunked="true"><body>'
        '<section data-zotero-worker-chunk="1" data-pages="1-10">'
        '<p id="shared-target">first</p><a href="#shared-target">first link</a>'
        '</section>'
        '<section data-zotero-worker-chunk="2" data-pages="11-20">'
        '<p id="shared-target">second</p><a href="#shared-target">second link</a>'
        '<a href="#page--1-0">unresolved Marker link</a>'
        '</section></body></html>',
        encoding="utf-8",
    )

    result = polish_and_inline_html_file(html_path)

    assert result.html.count('id="shared-target"') == 1
    assert 'id="shared-target--z2m-p11-20"' in result.html
    assert result.html.count('href="#shared-target"') == 1
    assert 'href="#shared-target--z2m-p11-20"' in result.html
    assert 'href="#page--1-0"' not in result.html
