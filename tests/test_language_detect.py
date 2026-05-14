from pathlib import Path

from zoteropdf2md.language_detect import (
    detect_language_from_html,
    detect_language_from_pdf,
    language_gate_decision,
    _sample_pdf_page_indexes,
    visible_text_from_html,
)


EN_PARAGRAPH = (
    "This study evaluates the design of neural interfaces and describes the "
    "methods, results, and discussion for the experiments. The device was "
    "tested with several measurements, and the results show stable behavior "
    "with low impedance and consistent recording quality. "
)

RU_PARAGRAPH = (
    "\u041a\u043b\u0438\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0435 "
    "\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u0438 "
    "\u0434\u043b\u044f \u043f\u0430\u0446\u0438\u0435\u043d\u0442\u043e\u0432 "
    "\u043e\u043f\u0438\u0441\u044b\u0432\u0430\u044e\u0442 "
    "\u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0443, "
    "\u043b\u0435\u0447\u0435\u043d\u0438\u0435 \u0438 "
    "\u043d\u0430\u0431\u043b\u044e\u0434\u0435\u043d\u0438\u0435. "
    "\u0412 \u044d\u0442\u043e\u043c \u0440\u0430\u0437\u0434\u0435\u043b\u0435 "
    "\u0442\u0430\u043a\u0436\u0435 \u043f\u0440\u0438\u0432\u0435\u0434\u0435\u043d\u044b "
    "\u043f\u043e\u043a\u0430\u0437\u0430\u043d\u0438\u044f \u0438 "
    "\u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u044f "
    "\u0434\u043b\u044f \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0438\u044f. "
)

DE_PARAGRAPH = (
    "Die deutschen Leitlinien zur Diagnostik des benignen Prostatasyndroms "
    "wurden von Experten erstellt und f\u00fcr Patienten mit Symptomen des "
    "unteren Harntraktes aktualisiert. Die Untersuchung, die Empfehlungen "
    "und die Beurteilung der Evidenz sollen in der klinischen Praxis helfen. "
)


def test_detects_english_body_despite_cyrillic_comment_metadata() -> None:
    html = "<html><body><!-- source_pdf=\u0438 \u0434\u0440. -->" + EN_PARAGRAPH * 80 + "</body></html>"

    detection = detect_language_from_html(html)
    decision = language_gate_decision(detection, target_language="en")

    assert detection.detected_language == "en"
    assert detection.sampled_windows > 1
    assert not decision.should_skip


def test_document_wide_detection_does_not_trust_english_first_page() -> None:
    html = "<html><body>" + EN_PARAGRAPH * 18 + RU_PARAGRAPH * 90 + "</body></html>"

    detection = detect_language_from_html(html)
    decision = language_gate_decision(detection, target_language="en")

    assert detection.detected_language in {"ru", "mixed"}
    assert detection.sampled_windows > 1
    assert decision.should_skip


def test_russian_body_with_english_references_is_gated_before_translation() -> None:
    html = (
        "<html><body>"
        + RU_PARAGRAPH * 70
        + "<h2>References</h2>"
        + EN_PARAGRAPH * 120
        + "</body></html>"
    )

    detection = detect_language_from_html(html)
    decision = language_gate_decision(detection, target_language="en")

    assert detection.detected_language == "ru"
    assert decision.should_skip


def test_german_body_with_english_abstract_is_gated_before_english_run() -> None:
    html = "<html><body>" + EN_PARAGRAPH * 8 + DE_PARAGRAPH * 80 + "</body></html>"

    detection = detect_language_from_html(html)
    decision = language_gate_decision(detection, target_language="en")

    assert detection.detected_language == "de"
    assert detection.sampled_windows > 1
    assert decision.should_skip


def test_visible_text_uses_document_text_before_references() -> None:
    html = "<p>" + RU_PARAGRAPH * 4 + "</p><h2>References</h2><p>" + EN_PARAGRAPH * 20 + "</p>"

    text = visible_text_from_html(html)

    assert "References" not in text
    assert "This study evaluates" not in text


def test_unknown_language_is_allowed_by_default_but_can_be_skipped() -> None:
    detection = detect_language_from_html("<html><body><p>LC 10 mA 20 Hz.</p></body></html>")

    assert detection.detected_language == "unknown"
    assert not language_gate_decision(detection, target_language="en").should_skip
    assert language_gate_decision(detection, target_language="en", skip_unknown=True).should_skip


def test_pdf_page_sampling_uses_start_middle_and_end_pages() -> None:
    pages = _sample_pdf_page_indexes(100, max_pages=9)

    assert pages[:3] == [0, 1, 2]
    assert pages[-3:] == [97, 98, 99]
    assert any(35 <= page <= 65 for page in pages)


def test_missing_pdf_detection_returns_unknown_without_crashing() -> None:
    detection, extraction = detect_language_from_pdf(Path(".tmp_local2/missing-language-test.pdf"))

    assert extraction.status == "missing"
    assert len(extraction.text) == 0
    assert detection.detected_language == "unknown"


def test_auto_target_language_detects_without_skipping() -> None:
    detection = detect_language_from_html("<html><body>" + RU_PARAGRAPH * 80 + "</body></html>")

    decision = language_gate_decision(detection, target_language="auto")

    assert detection.detected_language == "ru"
    assert not decision.should_skip
    assert decision.reason == "no_target_language"
