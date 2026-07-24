import re

from pdf_html_polish.quality_loop.audit_blocks import Block
from pdf_html_polish.quality_loop.audit_manual_patterns import (
    bibliography_numbering_residue_is_clean_reference_boundary,
    ends_like_sentence_fragment,
    find_split_dot_email_match,
    joined_word_match_is_non_prose,
    joined_word_match_is_url_slug,
    looks_like_affiliation_label_roman_boundary,
    page_link_semantic_kind,
    replacement_chars_are_pdf_source_noise,
    starts_like_sentence_continuation,
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


def test_joined_word_match_is_non_prose_accepts_ground_truth_call_only() -> None:
    call_text = "The evaluator calls GroundTruth () before comparison."
    prose_text = "The groundtruth label is still joined in prose."
    call_match = re.search("GroundTruth", call_text)
    prose_match = re.search("groundtruth", prose_text)
    assert call_match is not None
    assert prose_match is not None

    assert joined_word_match_is_non_prose(call_text, call_match)
    assert not joined_word_match_is_non_prose(prose_text, prose_match)


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


def test_sentence_fragment_helpers_detect_float_interruption_shape() -> None:
    assert ends_like_sentence_fragment("The response stayed stable and")
    assert not ends_like_sentence_fragment("The response stayed stable.")
    assert starts_like_sentence_continuation("continued after the figure")
    assert not starts_like_sentence_continuation("Continued after the figure")


def test_page_link_semantic_kind_classifies_cross_refs_and_citations() -> None:
    link_re = re.compile(r"<a\b[^>]*href=\"#page-\d+\"[^>]*>(?P<body>.*?)</a>")
    semantic_html = 'See Figure <a href="#page-4">2</a> for details.'
    citation_html = 'Prior work <a href="#page-8">[12]</a> was cited.'
    glue_html = 'Prior work <a href="#page-9">a 12</a> was cited.'
    semantic_match = link_re.search(semantic_html)
    citation_match = link_re.search(citation_html)
    glue_match = link_re.search(glue_html)
    assert semantic_match is not None
    assert citation_match is not None
    assert glue_match is not None

    assert page_link_semantic_kind(semantic_html, semantic_match) == "semantic-cross-reference"
    assert page_link_semantic_kind(citation_html, citation_match) == "citation"
    assert page_link_semantic_kind(glue_html, glue_match) == "citation-ocr-glue"
