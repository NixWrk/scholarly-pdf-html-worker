from pdf_html_polish.abbreviations import RU_ABBREV_TO_LATIN
from pdf_html_polish.raw_html_polish.presentation import (
    collapse_repeated_author_breaks,
    cleanup_empty_html_blocks,
    fix_heading_inline_abbreviation_breaks,
    inject_default_styles,
    inject_utf8_charset,
    restore_abbreviations,
    wrap_body_in_container,
)


def test_presentation_injects_utf8_style_and_container() -> None:
    html = "<html><head></head><body><p>Text</p></body></html>"
    style = '<style data-z2m-style="readable">body { color: black; }</style>'

    polished = inject_utf8_charset(html)
    polished = inject_default_styles(polished, readability_style=style)
    polished = wrap_body_in_container(polished)

    assert '<meta charset="utf-8">' in polished
    assert style in polished
    assert '<main id="marker-doc">' in polished


def test_presentation_replaces_existing_readable_style() -> None:
    html = (
        "<html><head>"
        '<style data-z2m-style="readable">old</style>'
        "</head><body></body></html>"
    )
    style = '<style data-z2m-style="readable">new</style>'

    polished = inject_default_styles(html, readability_style=style)

    assert style in polished
    assert "old" not in polished


def test_presentation_cleans_empty_blocks_and_heading_breaks() -> None:
    html = "<h1>Новая схема. <i>LC</i> датчик</h1><p> </p><br><br><br><br>"

    polished = cleanup_empty_html_blocks(fix_heading_inline_abbreviation_breaks(html))

    assert "<i>LC</i>-датчика" in polished
    assert "<p>" not in polished
    assert polished.count("<br>") == 2


def test_presentation_collapses_break_runs_only_in_author_containers() -> None:
    html = (
        '<article class="ltx_document ltx_authors_1line">'
        "<p>Body<br><br>Second paragraph.</p>"
        '<div class="ltx_authors">A<br>\n&nbsp;<br><span>B</span><br/>C'
        '<script>const sample = "<br><br>";</script></div>'
        "<!-- <div class=\"authors\">X<br><br>Y</div> -->"
        "</article>"
    )

    collapsed = collapse_repeated_author_breaks(html)

    assert "<p>Body<br><br>Second paragraph.</p>" in collapsed
    assert '<div class="ltx_authors">A<br>\n&nbsp;<span>B</span><br/>C' in collapsed
    assert '<script>const sample = "<br><br>";</script>' in collapsed
    assert "<!-- <div class=\"authors\">X<br><br>Y</div> -->" in collapsed
    assert collapse_repeated_author_breaks(collapsed) == collapsed


def test_restore_abbreviations_skips_tags_and_attrs() -> None:
    pattern, replacement = next(iter(RU_ABBREV_TO_LATIN.items()))
    token = pattern.replace(r"\b", "")
    html = f'<p data-name="{token}">Текст {token}</p>'

    restored = restore_abbreviations(html)

    assert f'data-name="{token}"' in restored
    assert f"Текст {replacement}" in restored
