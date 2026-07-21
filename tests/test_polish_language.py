from pathlib import Path

import pytest

from pdf_html_polish.polish_language import (
    resolve_document_polish_language,
    resolve_polish_language_policy,
)
from pdf_html_polish.single_file_html import (
    _normalize_ru_reference_lexemes,
    polish_and_inline_html_file,
    polish_html_document,
)


DE_PARAGRAPH = (
    "Die deutschen Leitlinien zur Diagnostik wurden von Experten erstellt und "
    "fuer Patienten mit Symptomen aktualisiert. Die Untersuchung, die Empfehlungen "
    "und die Beurteilung der Evidenz sollen in der klinischen Praxis helfen. "
)
ZH_PARAGRAPH = (
    "\u672c\u7814\u7a76\u63cf\u8ff0\u795e\u7ecf\u63a5\u53e3\u7684\u8bbe\u8ba1\u548c"
    "\u4e34\u5e8a\u8bc4\u4f30\u65b9\u6cd5\u3002\u7814\u7a76\u6bd4\u8f83\u60a3\u8005"
    "\u6d4b\u91cf\u7ed3\u679c\u548c\u5b9e\u9a8c\u6761\u4ef6\uff0c\u5e76\u8be6\u7ec6"
    "\u8bf4\u660e\u65b9\u6cd5\u3001\u7ed3\u679c\u548c\u8ba8\u8bba\u3002"
)


@pytest.mark.parametrize(
    ("paragraph", "expected_language"),
    [
        (DE_PARAGRAPH, "de"),
        (ZH_PARAGRAPH, "zh"),
    ],
)
def test_auto_policy_routes_known_non_target_languages_to_other(
    paragraph: str,
    expected_language: str,
) -> None:
    decision = resolve_document_polish_language(
        f"<html><body><p>{paragraph * 80}</p></body></html>",
        polish_language="auto",
    )

    assert decision.detection.detected_language == expected_language
    assert decision.detection.confidence >= 0.75
    assert decision.selected_polish_language == "other"


def test_explicit_non_target_language_resolves_to_other_policy() -> None:
    assert resolve_polish_language_policy("de").code == "other"
    assert resolve_polish_language_policy("zh").code == "other"


def test_other_policy_preserves_native_captions_and_skips_english_ocr_rules() -> None:
    html = (
        "<html><body>"
        '<p class="z2m-table-caption">Tabelle 1. ERGEBNISSE.</p>'
        '<p class="z2m-figure-caption">Abbildung 2. VERSUCH.</p>'
        "<p>Lost-looking tokens frst, fne, and medicineresistant stay native.</p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="other",
        polish_language="other",
    )

    assert "Tabelle 1. ERGEBNISSE." in polished
    assert "Abbildung 2. VERSUCH." in polished
    assert "frst, fne, and medicineresistant" in polished


def test_file_polish_accepts_explicit_ru_policy(tmp_path: Path) -> None:
    source = tmp_path / "translated.ru.html"
    source.write_text(
        "<html><body><main id='marker-doc'>"
        "<h2>References</h2>"
        "<p>English source text deliberately defeats automatic RU detection.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )

    result = polish_and_inline_html_file(source, polish_language="ru")

    assert (
        "\u0421\u043f\u0438\u0441\u043e\u043a \u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b"
        in result.html
    )
    assert "<h2>References</h2>" not in result.html


def test_ru_policy_localizes_standalone_english_structural_headings() -> None:
    html = (
        "<html><body>"
        "<p>\u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u043d\u0430\u0443\u0447\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u0435\u0442 \u044f\u0437\u044b\u043a \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430.</p>"
        "<h1>288 <b>Figures</b></h1>"
        "<h2>Tables</h2>"
        "<h3>References</h3>"
        "<h4>Sections</h4>"
        "<h5>Appendices</h5>"
        "<h6>Equations</h6>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="ru",
        polish_language="ru",
    )

    for english_label in (
        "Figures",
        "Tables",
        "References",
        "Sections",
        "Appendices",
        "Equations",
    ):
        assert english_label not in polished
    assert "288 <b>\u0420\u0438\u0441\u0443\u043d\u043a\u0438</b>" in polished
    assert "\u0422\u0430\u0431\u043b\u0438\u0446\u044b" in polished
    assert (
        "\u0421\u043f\u0438\u0441\u043e\u043a \u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b"
        in polished
    )


def test_ru_policy_localizes_late_english_figure_caption_label() -> None:
    html = (
        "<html><body>"
        "<p>\u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u043d\u0430\u0443\u0447\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u0435\u0442 \u044f\u0437\u044b\u043a \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430.</p>"
        "<div id='fig-22' class='z2m-float-unit z2m-figure-unit'>"
        "<p class='z2m-figure-caption'>Figure 22. For animated models, "
        "the caption remains available for translation review.</p>"
        "</div>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="ru",
        polish_language="ru",
    )

    assert "Figure 22" not in polished
    assert "\u0420\u0438\u0441\u0443\u043d\u043e\u043a 22" in polished
    assert "For animated models" in polished


def test_ru_reference_normalizer_allows_captions_inside_reference_wrapper() -> None:
    html = (
        "<div class='z2m-references-block' translate='no'>"
        "<p>Reference title mentioning Figure 9 remains bibliographic.</p>"
        "<p class='z2m-figure-caption'>Figure 22. For animated models.</p>"
        "<p class='z2m-table-caption'>Table 3. Measurements.</p>"
        "</div>"
    )

    normalized = _normalize_ru_reference_lexemes(html)

    assert "Reference title mentioning Figure 9" in normalized
    assert "Figure 22" not in normalized
    assert "Table 3" not in normalized
    assert "\u0420\u0438\u0441\u0443\u043d\u043e\u043a 22" in normalized
    assert "\u0422\u0430\u0431\u043b\u0438\u0446\u0430 3" in normalized


def test_english_only_ru_normalizer_preserves_existing_ru_abbreviation() -> None:
    html = "<p>\u0421\u043c. \u0440\u0438\u0441. 2.9, then Figure 3 for comparison.</p>"

    normalized = _normalize_ru_reference_lexemes(
        html,
        english_labels_only=True,
    )

    assert "\u0440\u0438\u0441. 2.9" in normalized
    assert "Figure 3" not in normalized
    assert "\u0420\u0438\u0441\u0443\u043d\u043e\u043a 3" in normalized


def test_ru_normalizer_localizes_caption_label_split_by_inline_markup() -> None:
    html = (
        "<p class='z2m-figure-caption'><b>Fig.</b> 3. Caption.</p>"
        "<p class='z2m-figure-caption'>Fig. <a href='#fig-5'>5</a>. Caption.</p>"
    )

    normalized = _normalize_ru_reference_lexemes(html, english_labels_only=True)

    assert "<b>\u0420\u0438\u0441\u0443\u043d\u043e\u043a</b> 3" in normalized
    assert (
        "\u0420\u0438\u0441\u0443\u043d\u043e\u043a <a href='#fig-5'>5</a>"
        in normalized
    )


def test_ru_normalizer_localizes_letter_number_table_keys() -> None:
    html = (
        "<p class='z2m-table-caption'>Table D1. Caption.</p>"
        "<p>See <a href='#table-a1'>Table A1</a>.</p>"
    )

    normalized = _normalize_ru_reference_lexemes(html, english_labels_only=True)

    assert "\u0422\u0430\u0431\u043b\u0438\u0446\u0430 D1" in normalized
    assert (
        "<a href='#table-a1'>\u0422\u0430\u0431\u043b\u0438\u0446\u0430 A1</a>"
        in normalized
    )


def test_ru_normalizer_localizes_caption_collection_heading() -> None:
    html = "<h2>Figure captions</h2><p>\u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u0442\u0435\u043a\u0441\u0442.</p>"

    normalized = _normalize_ru_reference_lexemes(html, english_labels_only=True)

    assert "<h2>\u041f\u043e\u0434\u043f\u0438\u0441\u0438 \u043a \u0440\u0438\u0441\u0443\u043d\u043a\u0430\u043c</h2>" in normalized
    assert "Figure captions" not in normalized
