from pdf_html_polish.raw_html_polish.doi_anchors import (
    repair_doi_anchor_swallowed_prose_tails,
    repair_miswrapped_doi_anchor_labels,
    split_doi_metadata_body_paragraphs,
)


def test_repair_miswrapped_doi_anchor_labels_moves_tail_into_anchor() -> None:
    href = "https://doi.org/10.1234/example.5678"
    html = f'<p>Source <a href="{href}">Published doi: 10.1234/</a>example.5678.</p>'

    repaired = repair_miswrapped_doi_anchor_labels(html)

    assert repaired == f'<p>Source Published doi: <a href="{href}">10.1234/example.5678</a>.</p>'


def test_repair_doi_anchor_swallowed_prose_tails_splits_href_tail() -> None:
    url = "https://doi.org/10.1234/example"
    html = (
        f'<p>DOI: <a href="{url} Introduction">{url} Introduction</a> '
        "This paragraph continues with enough words to be body prose.</p>"
    )

    repaired = repair_doi_anchor_swallowed_prose_tails(html)

    assert repaired == (
        f'<p>DOI: <a href="{url}">{url}</a></p>\n'
        "<p>Introduction This paragraph continues with enough words to be body prose.</p>"
    )


def test_repair_doi_anchor_swallowed_prose_tails_rejects_short_tail() -> None:
    url = "https://doi.org/10.1234/example"
    html = f'<p>DOI: <a href="{url} Intro">{url} Intro</a> short.</p>'

    assert repair_doi_anchor_swallowed_prose_tails(html) == html


def test_split_doi_metadata_body_paragraphs_splits_body_after_doi() -> None:
    href = "https://doi.org/10.1234/example"
    tail = "The study reports enough body prose to satisfy the paragraph split guard."
    html = f'<p>DOI: <a href="{href}">{href}</a> {tail}</p>'

    repaired = split_doi_metadata_body_paragraphs(html)

    assert repaired == f'<p>DOI: <a href="{href}">{href}</a></p>\n<p>{tail}</p>'


def test_split_doi_metadata_body_paragraphs_keeps_reference_paragraphs() -> None:
    href = "https://doi.org/10.1234/example"
    html = f'<p id="ref-1">DOI: <a href="{href}">{href}</a> The reference text should stay intact.</p>'

    assert split_doi_metadata_body_paragraphs(html) == html


def test_split_doi_metadata_body_paragraphs_keeps_front_matter_non_plos_doi() -> None:
    href = "https://doi.org/10.1234/example"
    html = f'<p class="z2m-front-matter">DOI: <a href="{href}">{href}</a> The body-like text remains metadata.</p>'

    assert split_doi_metadata_body_paragraphs(html) == html
