import re

from pdf_html_polish.quality_loop.audit_blocks import Block
from pdf_html_polish.quality_loop.audit_manual_patterns import (
    bibliography_numbering_residue_is_clean_reference_boundary,
    find_split_dot_email_match,
    joined_word_match_is_url_slug,
    looks_like_affiliation_label_roman_boundary,
    replacement_chars_are_pdf_source_noise,
)


def _block(text: str, *, classes: str = "") -> Block:
    attrs = {"class": classes} if classes else {}
    return Block(index=0, tag="p", attrs=attrs, raw=f"<p>{text}</p>", text=text, line=1)


def _roman_match(text: str) -> re.Match[str]:
    match = re.search(r"(?P<prefix>[A-Z][A-Za-z]+)\s+(?P<suffix>v|i|x|vi|ix)\b", text)
    assert match is not None
    return match


def test_replacement_chars_are_pdf_source_noise_for_known_pdf_control_char() -> None:
    assert replacement_chars_are_pdf_source_noise(
        "pressure dynes\ufffdsec\ufffdcm-5 was preserved",
        "pressure dynes\x01sec\x01cm-5 was preserved",
    )


def test_replacement_chars_are_pdf_source_noise_keeps_ordinary_damage_counted() -> None:
    assert not replacement_chars_are_pdf_source_noise("ordinary\ufffdtext", "ordinary text")


def test_affiliation_roman_boundary_accepts_country_before_institution() -> None:
    block = _block("ARTICLE INFO Denmark i National Institute of Public Health", classes="z2m-front-matter")

    assert looks_like_affiliation_label_roman_boundary(block, _roman_match(block.text))


def test_affiliation_roman_boundary_requires_frontmatter_or_context() -> None:
    block = _block("Denmark i National Institute of Public Health")

    assert not looks_like_affiliation_label_roman_boundary(block, _roman_match(block.text))


def test_affiliation_roman_boundary_rejects_non_i_suffix() -> None:
    block = _block("ARTICLE INFO Denmark v National Institute of Public Health", classes="z2m-front-matter")

    assert not looks_like_affiliation_label_roman_boundary(block, _roman_match(block.text))


def test_joined_word_match_is_url_slug_only_inside_url_left_context() -> None:
    url_text = "Reference URL https://www.wsj.com/articles/a-hardwareupdate-for-the-human-brain."
    prose_text = "The hardwareupdate phrase remains in prose."

    url_match = re.search("hardwareupdate", url_text)
    prose_match = re.search("hardwareupdate", prose_text)
    assert url_match is not None
    assert prose_match is not None

    assert joined_word_match_is_url_slug(url_text, url_match)
    assert not joined_word_match_is_url_slug(prose_text, prose_match)


def test_find_split_dot_email_match_ignores_sentence_boundary_before_email() -> None:
    text = "Correspondence should be addressed. jamesbarresemd@gmail.com."

    assert find_split_dot_email_match(text) is None


def test_find_split_dot_email_match_reports_true_split_dot_email() -> None:
    match = find_split_dot_email_match("Email: jan. krhut@fno.cz.")

    assert match is not None
    assert match.group(0) == "jan. krhut@fno.cz"


def test_bibliography_numbering_residue_accepts_existing_reference_boundary() -> None:
    html = '<ol><li id="ref-2"><span class="z2m-ref-num">2.</span> Smith J. Example.</li></ol>'

    assert bibliography_numbering_residue_is_clean_reference_boundary(html, "2. Smith")
    assert not bibliography_numbering_residue_is_clean_reference_boundary(html, "2. Jones")
