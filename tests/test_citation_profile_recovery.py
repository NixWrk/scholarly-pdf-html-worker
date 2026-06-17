from pdf_html_polish.citation_profile_recovery import (
    citation_profile_has_zotero_reference_evidence,
    citation_profile_is_author_year,
    citation_profile_reference_entries_by_number,
    contiguous_profile_reference_recovery_numbers,
    pdf_recovered_reference_section_from_profile,
)


def test_citation_profile_reference_entries_accept_dict_items() -> None:
    profile = {
        "reference_entries": [
            {"number": "1", "text": "Smith J. Example."},
            {"number": 2, "text": "Jones A. Example."},
            {"number": "bad", "text": "ignored"},
            {"number": 3, "text": ""},
        ]
    }

    assert citation_profile_reference_entries_by_number(profile) == {
        1: "Smith J. Example.",
        2: "Jones A. Example.",
    }


def test_contiguous_profile_reference_recovery_requires_prefix_complete_entries() -> None:
    profile = {"reference_entries_recovery_numbers": [1, 2, 3]}

    assert contiguous_profile_reference_recovery_numbers(profile, {1: "one", 2: "two", 3: "three"}) == [1, 2, 3]
    assert contiguous_profile_reference_recovery_numbers(profile, {1: "one", 3: "three"}) == []


def test_pdf_recovered_reference_section_escapes_entries() -> None:
    section, max_number = pdf_recovered_reference_section_from_profile(
        {
            "reference_entries_recovery_numbers": [1],
            "reference_entries": [{"number": 1, "text": "Smith < Jones & Co."}],
        }
    )

    assert max_number == 1
    assert 'id="ref-1"' in section
    assert "Smith &lt; Jones &amp; Co." in section


def test_citation_profile_style_and_zotero_evidence_helpers() -> None:
    profile = {
        "style": "author_year",
        "confidence": "medium",
        "zotero_citation_count": "2",
    }

    assert citation_profile_is_author_year(profile) is True
    assert citation_profile_has_zotero_reference_evidence(profile) is True
