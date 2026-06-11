from __future__ import annotations

from zoteropdf2md.translation.abbreviations import (
    repair_abbreviation_definition_segment,
    replace_abbreviation_paragraphs_ru,
    source_abbreviation_entries,
)


def test_source_abbreviation_entries_uses_known_ru_expansions() -> None:
    entries = source_abbreviation_entries(
        "Abbreviations: ECoG, electrocorticogram; SEP, somatosensory evoked potential."
    )

    assert entries == [
        ("ECoG", "электрокортикограмма"),
        ("SEP", "сенсорный вызванный потенциал"),
    ]


def test_replace_abbreviation_paragraphs_ru_marks_rebuilt_text_notranslate() -> None:
    html = (
        "<p><b>Abbreviations:</b> ECoG, electrocorticogram; "
        "SEP, somatosensory evoked potential.</p>"
    )

    result = replace_abbreviation_paragraphs_ru(html)

    assert result == (
        '<p><span translate="no">Сокращения: ECoG, электрокортикограмма; '
        "SEP, сенсорный вызванный потенциал.</span></p>"
    )


def test_repair_abbreviation_definition_segment_replaces_hallucinated_business_glossary() -> None:
    source = "Abbreviations: ECoG, electrocorticogram; SEP, somatosensory evoked potential."
    translated = "  Сокращения: CEO, директор; CRM, система.  "

    result = repair_abbreviation_definition_segment(source, translated)

    assert result == (
        "  Сокращения: ECoG, электрокортикограмма; "
        "SEP, сенсорный вызванный потенциал.  "
    )
