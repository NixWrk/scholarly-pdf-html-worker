from pdf_html_polish.raw_html_polish.page_furniture import (
    drop_page_header_footer_paragraphs,
    drop_publisher_chrome_pages,
    drop_repeated_page_furniture,
    looks_running_header_line,
    strip_leading_pdf_line_number_from_body,
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
