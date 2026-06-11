from __future__ import annotations

from zoteropdf2md.translation.html_marking import (
    mark_author_line_notranslate,
    mark_references_block_notranslate,
)


def test_mark_author_line_notranslate_marks_author_paragraph_after_heading() -> None:
    html = "<h1>Title</h1><p>Alice Smith, Bob Jones, and Carol White</p><h2>Abstract</h2>"

    result = mark_author_line_notranslate(html)

    assert result == (
        '<h1>Title</h1><p translate="no">Alice Smith, Bob Jones, and Carol White</p>'
        "<h2>Abstract</h2>"
    )


def test_mark_author_line_notranslate_skips_metadata_paragraphs() -> None:
    html = "<h1>Title</h1><p>Received: 1 January 2025</p><h2>Abstract</h2>"

    assert mark_author_line_notranslate(html) == html


def test_mark_references_block_notranslate_wraps_to_next_heading() -> None:
    html = (
        "<h2>References</h2><ol><li>One</li><li>Two</li></ol>"
        "<h2>Appendix</h2><p>Body</p>"
    )

    result = mark_references_block_notranslate(html)

    assert result == (
        '<div class="z2m-references-block" translate="no">'
        "<h2>References</h2><ol><li>One</li><li>Two</li></ol>"
        "</div><h2>Appendix</h2><p>Body</p>"
    )


def test_mark_references_block_notranslate_uses_list_boundary_without_next_heading() -> None:
    html = "<h2>References</h2><ol><li>One</li></ol><p>Post-reference note</p>"

    result = mark_references_block_notranslate(html)

    assert result == (
        '<div class="z2m-references-block" translate="no">'
        "<h2>References</h2><ol><li>One</li></ol>"
        "</div><p>Post-reference note</p>"
    )
