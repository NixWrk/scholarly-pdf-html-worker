from pathlib import Path

from pdf_html_polish.quality_loop.converted_runs import _converted_raw_citation_profile
from pdf_html_polish.single_file_html import polish_html_document


def test_other_language_polish_repairs_only_exact_language_neutral_residuals() -> None:
    html = (
        "<html><body>"
        "<p>Die deutschen Leitlinien wurden fuer Patienten aktualisiert.</p>"
        "<p>Die Behandlung ist effekt iv und sicher.</p>"
        "<p>Die Werte wurden retrospektiv und effektiv erfasst.</p>"
        "<p>The German guidelinesfor assessing BPH remain medicineresistant.</p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="other",
        polish_language="other",
    )

    assert "guidelines for assessing" in polished
    assert "Behandlung ist effektiv" in polished
    assert "retrospektiv und effektiv" in polished
    assert "medicineresistant" in polished


def test_english_polish_repairs_recovered_ocr_phrases() -> None:
    html = (
        "<html><body><p>Participants list all the    they identified. "
        "Continues variables are presented as mean and range. "
        "No perioperative differences were obeserved. "
        "Most published stuies used the preferrable threshold. "
        "These resultes include a single incision miduretrhal sling. "
        "Several characteriscs were measured. "
        "The telescope channel Dl50.4\u20130.78 mm was used. "
        "The back focus <i>F</i><sup>1</sup>8 of objective 3 was measured. "
        "The LED divergence is 2u560\u00b0."
        "</p></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        polish_language="en",
    )

    assert "list all that they identified" in polished
    assert "Continuous variables are presented" in polished
    assert "differences were observed" in polished
    assert "published studies used the preferable threshold" in polished
    assert "These results include a single incision midurethral sling" in polished
    assert "Several characteristics were measured" in polished
    assert "channel D1=0.4\u20130.78 mm" in polished
    assert "back focus F\u2081\u2032 of objective 3" in polished
    assert "2\u03c9=60\u00b0" in polished


def test_reference_polish_rejects_repeated_journal_page_footer_number() -> None:
    html = (
        "<html><body>"
        "<p>Prior studies [1, 2] describe the optical system.</p>"
        "<h4>References</h4>"
        "<ul>"
        "<li>1. Smith J. Optical systems. Journal of Optics. 2001.</li>"
        "<li>2. Jones A. Viewfinder design. Applied Optics. 2002.</li>"
        "</ul>"
        "<p>317 J. Opt. Technol. <b>72</b> (4), April 2005 Vovk et al. 317</p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        polish_language="en",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )

    assert 'id="ref-317"' not in polished
    assert 'href="#ref-317"' not in polished
    assert "317 J. Opt. Technol." in polished


def test_ru_polish_localizes_plural_and_supplementary_structural_labels() -> None:
    html = (
        "<html><body><main id='marker-doc'>"
        "<h1>Table OF \u0421\u043e\u0434\u0435\u0440\u0436\u0430\u043d\u0438\u0435</h1>"
        "<p class='z2m-table-caption'>TABLE S2. \u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u0442\u0435\u043a\u0441\u0442.</p>"
        "<p><a href='#fig-4a'>Figures 4A-C</a>, "
        "<a href='#fig-6b'>Figs. 6b</a>, "
        "<a href='#fig-a-2'>Fig. A.2</a>.</p>"
        "<figure id='fig-4a'></figure><figure id='fig-6b'></figure>"
        "<figure id='fig-a-2'></figure>"
        "</main></body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="ru",
        polish_language="ru",
    )

    assert "\u0421\u043e\u0434\u0435\u0440\u0436\u0430\u043d\u0438\u0435" in polished
    assert "\u0422\u0430\u0431\u043b\u0438\u0446\u0430 S2" in polished
    assert "\u0420\u0438\u0441\u0443\u043d\u043a\u0438 4A-C" in polished
    assert "\u0420\u0438\u0441\u0443\u043d\u043a\u0438 6b" in polished
    assert "\u0420\u0438\u0441\u0443\u043d\u043e\u043a A.2" in polished
    for forbidden in ("Table OF", "TABLE S2", "Figures 4A", "Figs. 6b", "Fig. A.2"):
        assert forbidden not in polished


def test_raw_profile_uses_numeric_superscripts_with_unnamed_numbered_tail() -> None:
    body = "".join(
        f"<p>Measurement ({index}) agrees with prior work.<sup>1\u20132</sup></p>"
        for index in range(1, 21)
    )
    references = "".join(
        f"<li>{index}. Reference author {index}. Journal 2020.</li>"
        for index in range(1, 12)
    )
    html = f"<html><body>{body}<ol>{references}</ol></body></html>"

    profile = _converted_raw_citation_profile(html, Path("vovk.html"))

    assert profile["style"] == "superscript_numeric"
    assert profile["confidence"] == "high"
    assert profile["numeric_superscript_hint_count"] == 20
    assert profile["numbered_reference_hint_count"] == 11


def test_raw_profile_accepts_bracket_style_with_unnamed_numbered_tail() -> None:
    author_year_noise = "".join(
        f"<p>Smith et al., {2000 + index} reported a separate observation.</p>"
        for index in range(45)
    )
    bracket_citations = "".join(
        f"<p>The method follows [{index}].</p>"
        for index in range(1, 19)
    )
    references = "".join(
        f"<li>{index}. Reference author {index}. Journal 2020.</li>"
        for index in range(1, 21)
    )
    html = (
        f"<html><body>{author_year_noise}{bracket_citations}"
        f"<ol>{references}</ol></body></html>"
    )

    profile = _converted_raw_citation_profile(html, Path("oelke.html"))

    assert profile["style"] == "bracket_numeric"
    assert profile["confidence"] == "medium"
    assert profile["bracket_numeric_count"] == 18
    assert profile["numbered_reference_hint_count"] == 20


def test_bracket_profile_does_not_link_decimal_comma_measurements() -> None:
    references = "".join(
        f"<li>{index}. Referenz {index}.</li>" for index in range(1, 10)
    )
    html = (
        "<html><body>"
        "<p>Der Serumwert lag bei <sup>1,9</sup> \u03bcg/l. "
        "Die Messung nutzte einen <sup>7,5</sup>-MHz-Ultraschallkopf. "
        "Die Methode wurde beschrieben [7].</p>"
        f"<h2>References</h2><ol>{references}</ol>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="other",
        polish_language="other",
        citation_profile={"style": "bracket_numeric", "confidence": "medium"},
    )

    assert "1,9 \u03bcg/l" in polished
    assert "7,5-MHz" in polished
    assert "<sup>1,9</sup>" not in polished
    assert "<sup>7,5</sup>" not in polished
    assert 'href="#ref-1"' not in polished
    assert 'href="#ref-9"' not in polished
    assert 'href="#ref-7" class="z2m-ref-link">[7]</a>' in polished
