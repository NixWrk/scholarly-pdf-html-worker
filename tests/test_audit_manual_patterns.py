import re

from zoteropdf2md.quality_loop.audit_blocks import Block
from zoteropdf2md.quality_loop.audit_manual_patterns import (
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
