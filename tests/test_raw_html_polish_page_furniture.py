from pdf_html_polish.raw_html_polish.page_furniture import (
    drop_page_header_footer_paragraphs,
    drop_pmc_page_chrome,
    drop_publisher_chrome_pages,
    drop_repeated_page_furniture,
    looks_running_header_line,
    strip_leading_pdf_line_number_from_body,
    strip_internal_raw_html_title,
    strip_pdf_running_header_prefix_from_body,
)


def test_drop_page_header_footer_paragraphs_removes_journal_page_line() -> None:
    html = "<p>This role may be</p><p>Processes 2021, 9, 1726 5 of 31</p><p>performed later.</p>"

    repaired = drop_page_header_footer_paragraphs(html)

    assert "Processes 2021" not in repaired
    assert "<p>This role may be</p><p>performed later.</p>" == repaired


def test_drop_repeated_page_furniture_removes_repeated_running_header_and_prefix() -> None:
    html = (
        "<p>Journal of Materials Chemistry B Accepted Manuscript</p>"
        "<p>Journal of Materials Chemistry B Accepted Manuscript Body starts here.</p>"
        "<p>Journal of Materials Chemistry B Accepted Manuscript</p>"
    )

    repaired = drop_repeated_page_furniture(html)

    assert repaired == "<p>Body starts here.</p>"


def test_drop_publisher_chrome_pages_removes_repository_cover_with_leading_image() -> None:
    html = (
        '<p><img src="flore-cover.png"/></p>'
        "<h1>FLORE Repository istituzionale dell'Università degli Studi di Firenze</h1>"
        "<p>La data sopra indicata si riferisce al Repository FloRe (Article begins on next page)</p>"
        "<p>Article body starts.</p>"
    )

    repaired = drop_publisher_chrome_pages(html)

    assert "flore-cover" not in repaired
    assert "FLORE Repository" not in repaired
    assert repaired == "<p>Article body starts.</p>"


def test_drop_pmc_page_chrome_removes_balanced_sidebar_dialog_and_disclaimer() -> None:
    html = (
        "<main><h1>Article</h1><p>Body.</p></main>"
        '<div class="pmc-sidenav desktop:grid-col-4"><section><h2>ACTIONS</h2>'
        '<div><ul class="usa-list--actions"><li>PDF<ul><li>nested</li></ul></li></ul></div>'
        "</section></div>"
        '<div class="overlay" role="dialog" aria-label="Citation Dialog" hidden>'
        '<div class="dialog citation-dialog"><h2>Cite</h2></div></div>'
        '<div class="pmc-layout__disclaimer" role="complementary">NLM disclaimer</div>'
        "<footer>Kept footer.</footer>"
    )

    repaired = drop_pmc_page_chrome(html)

    assert repaired == "<main><h1>Article</h1><p>Body.</p></main><footer>Kept footer.</footer>"
    assert drop_pmc_page_chrome(repaired) == repaired


def test_drop_pmc_page_chrome_keeps_article_actions_section_without_pmc_signature() -> None:
    html = "<article><h2>Actions</h2><ul><li>Clinical action.</li></ul></article>"

    assert drop_pmc_page_chrome(html) == html


def test_strip_internal_raw_html_title_preserves_body_text_and_is_idempotent() -> None:
    html = "<html><head><title>Gothe atlas raw HTML</title></head><body><p>raw HTML</p></body></html>"

    repaired = strip_internal_raw_html_title(html)

    assert repaired == "<html><head><title>Gothe atlas</title></head><body><p>raw HTML</p></body></html>"
    assert strip_internal_raw_html_title(repaired) == repaired
    assert strip_internal_raw_html_title("<title>Raw HTML</title>") == "<title>Raw HTML</title>"


def test_running_header_helpers_strip_known_prefixes() -> None:
    assert looks_running_header_line("ChemComm Accepted Manuscript")

    body, changed = strip_pdf_running_header_prefix_from_body(
        '<span id="page-3"></span>ChemComm Accepted Manuscript Body text.'
    )

    assert changed
    assert body == '<span id="page-3"></span>Body text.'


def test_strip_leading_pdf_line_number_from_body_accepts_known_unit_tails() -> None:
    body, changed = strip_leading_pdf_line_number_from_body('<span id="page-3"></span>20 nm fluorescence signal')

    assert changed
    assert body == '<span id="page-3"></span>nm fluorescence signal'


def test_strip_leading_pdf_line_number_from_body_rejects_non_grid_number() -> None:
    assert strip_leading_pdf_line_number_from_body("21 nm fluorescence signal") == (
        "21 nm fluorescence signal",
        False,
    )
