from __future__ import annotations

import json
from pathlib import Path

from zoteropdf2md.citation_profile import (
    PdfLinkAnnotation,
    _author_year_reference_hint_count,
    _is_reference_citation_dest,
    _reference_entries_from_page_texts,
    infer_citation_style_from_text,
    load_zotero_overlay_citations,
    merge_citation_profile_with_zotero_overlays,
)
from zoteropdf2md.single_file_html import polish_html_document


def _refs(count: int) -> str:
    items = "".join(f"<li>{idx}. Reference {idx}.</li>" for idx in range(1, count + 1))
    return f"<h1>REFERENCES</h1><p block-type=\"ListGroup\"><ul>{items}</ul></p>"


def test_infer_citation_style_detects_parenthetical_numeric_pdf_text() -> None:
    text = (
        "Sentinel lymph node biopsy can provide accurate staging (1, 2). "
        "The method avoids ALND (1, 3, 4). "
        "Previous studies reported similar results (9, 10). "
        "Other authors found body mass index effects (3, 13-16). "
        "Comparable results were obtained previously (12). "
    )

    style, confidence, paren_count, bracket_count = infer_citation_style_from_text(
        text,
        ref_link_count=16,
    )

    assert style == "paren_numeric"
    assert confidence == "high"
    assert paren_count == 5
    assert bracket_count == 0


def test_infer_citation_style_detects_flattened_superscript_numeric_pdf_text() -> None:
    text = (
        "NIR imaging has high tissue penetration. 1,2,3,4 However, dyes are limited. "
        "The dyes have low intensity. 5,6,7 The signal can bleach. "
        "Tracking remains difficult. 8,9,10 Besides, crosstalk is common. "
        "The emission overlaps. 11,12,13 Therefore, new dyes are needed. "
        "FRET pair dyes. 14,15,16,17 FRET is non-radiative. "
    )

    style, confidence, paren_count, bracket_count = infer_citation_style_from_text(text)

    assert style == "superscript_numeric"
    assert confidence == "high"
    assert paren_count == 0
    assert bracket_count == 0


def test_infer_citation_style_detects_author_year_pdf_reference_links() -> None:
    text = (
        "Smith et al., 2020 introduced the baseline. "
        "Jones and Brown 2021 extended it. "
        "Gupta & Pruthi 2025 audited novelty. "
        "Lund and Naheem 2023 discussed authorship. "
        "Yeo-The & Tang 2023 reviewed attribution. "
        "Lehman and Stanley 2011 studied novelty search. "
    )

    style, confidence, paren_count, bracket_count = infer_citation_style_from_text(
        text,
        ref_link_count=6,
        author_year_hint_count=6,
    )

    assert style == "author_year"
    assert confidence == "high"
    assert paren_count == 0
    assert bracket_count == 0


def test_latex_cite_destinations_count_as_author_year_reference_evidence() -> None:
    annotations = [
        PdfLinkAnnotation(
            page=1,
            kind="reference" if _is_reference_citation_dest("cite.smith2020baseline") else "internal",
            dest="cite.smith2020baseline",
            target="cite.smith2020baseline",
            text="Smith et al. (2020)",
        ),
        PdfLinkAnnotation(
            page=1,
            kind="reference" if _is_reference_citation_dest("cite.jones2021extension") else "internal",
            dest="cite.jones2021extension",
            target="cite.jones2021extension",
            text="Jones and Brown (2021)",
        ),
    ]

    assert _is_reference_citation_dest("cite.smith2020baseline")
    assert not _is_reference_citation_dest("figure.1")
    assert _author_year_reference_hint_count(annotations) == 2


def test_reference_entries_from_page_texts_extracts_spotnitz_style_bracket_refs() -> None:
    entries = _reference_entries_from_page_texts(
        [
            (
                24,
                "References\n"
                "[157] C. Schug-Pass, D. A. Jacob et al., “Biomechanical properties,” Hernia, 2013.\n"
                "[158] R. H. Fortelny, A. H. Petter-Puchner, C. May et al., “The impact\n"
                "of atraumatic fibrin sealant vs. staple mesh fixation in TAPP\n"
                "hernia repair on chronic pain and quality of life,” Surgical Endoscopy, 2012.\n"
                "[159] M. Cambal, P. Zonca, and B. Hrbaty, “Comparison of self-\n"
                "gripping mesh,” Bratislavske Lekarske Listy, 2012.\n",
            )
        ]
    )

    assert [entry.number for entry in entries] == [157, 158, 159]
    assert entries[1].page == 24
    assert "Fortelny" in entries[1].text
    assert "atraumatic fibrin sealant" in entries[1].text


def test_load_zotero_overlay_citations_reads_probe_summary() -> None:
    overlay_path = Path(".tmp_local2/test_zotero_overlay_probe_summary.overlays.json")
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        overlay_path.write_text(
            json.dumps(
                {
                    "summary": {
                        "citations": [
                            {
                                "pageIndex": 0,
                                "text": "3-5",
                                "context": "pretreatment UDS.3-5Recently",
                                "references": [{"index": 3}, {"index": 4}, {"index": 5}],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        citations = load_zotero_overlay_citations(overlay_path)
        merged = merge_citation_profile_with_zotero_overlays(
            {"style": "unknown", "confidence": "low"},
            overlay_path,
        )
    finally:
        overlay_path.unlink(missing_ok=True)

    assert len(citations) == 1
    assert citations[0].text == "3-5"
    assert citations[0].refs == [3, 4, 5]
    assert merged["zotero_citation_count"] == 1
    assert merged["zotero_citations"][0]["context"] == "pretreatment UDS.3-5Recently"


def test_parenthetical_numeric_profile_retargers_page_anchor_citations_without_sup_false_positive() -> None:
    html = (
        "<html><body>"
        "<p>Sentinel lymph node biopsy provides accurate staging "
        '<a href="#page-6-0">(1,</a> <a href="#page-6-0">2)</a>. '
        "ALND "
        '<a href="#page-6-0">(1,</a> 3 , <a href="#page-6-0">4)</a> '
        "can be avoided. Successful axillary SLNB "
        '( 3 , 13 - <a href="#page-6-0">16)</a>. '
        "The mean number was \\(5.22 \\pm <sup>2,38</sup>, p = 0.075\\)."
        "</p>"
        f"{_refs(40)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "paren_numeric", "confidence": "high"},
    )

    assert 'href="#ref-1"' in polished
    assert 'href="#ref-2"' in polished
    assert 'href="#ref-3"' in polished
    assert 'href="#ref-4"' in polished
    assert 'href="#ref-13"' in polished
    assert 'href="#ref-16"' in polished
    assert 'href="#ref-38"' not in polished
    assert "<sup>2,38</sup>" in polished
    assert "staging (" in polished
    assert ") can be avoided" in polished


def test_parenthetical_numeric_profile_links_plain_text_citations_but_not_percentages_or_years() -> None:
    html = (
        "<html><body>"
        "<p>Ignored either (8). The total was 35 (19.2%) patients, "
        "the trial was published (2022), and accuracy improved (21-26). "
        "Deep regions may be missed (5, 34).</p>"
        f"{_refs(40)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "paren_numeric", "confidence": "high"},
    )

    assert 'href="#ref-8"' in polished
    assert 'href="#ref-21"' in polished
    assert 'href="#ref-26"' in polished
    assert 'href="#ref-5"' in polished
    assert 'href="#ref-34"' in polished
    assert "(19.2%)" in polished
    assert "(2022)" in polished


def test_parenthetical_numeric_profile_keeps_low_number_citation_near_data_word() -> None:
    html = (
        "<html><body>"
        "<p>Exploration should be carried out only after opening the axillary fascia; "
        "blind exploration in the fat tissue must be strictly avoided (5).</p>"
        "<p>This study has limitations. First, there was no long-term follow-up, "
        "and so data on postoperative recurrence were not available.</p>"
        "<p>Smith 2020, Jones 2019, Brown 2018, White 2017, and Black 2016 "
        "make this look like an author-year document.</p>"
        f"{_refs(40)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "paren_numeric", "confidence": "high"},
    )

    assert 'strictly avoided (<a href="#ref-5" class="z2m-ref-link">5</a>).' in polished


def test_parenthetical_numeric_profile_uses_annotation_budget_when_available() -> None:
    html = (
        "<html><body>"
        "<p>First cited statement (8). A second plain parenthetical number (8).</p>"
        f"{_refs(10)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "paren_numeric",
            "confidence": "high",
            "ref_dest_prefix": "B",
            "annotations": [
                {"page": 2, "kind": "reference", "dest": "B8", "target": "8", "text": "(8)."}
            ],
        },
    )

    assert polished.count('href="#ref-8"') == 1
    assert 'number (8).' in polished


def test_pdf_annotation_profile_links_author_year_label_without_linking_bare_years() -> None:
    html = (
        "<html><body>"
        "<p>Prior work (Smith et al., 2020) found the same pattern. "
        "The study period ran from 2019 to 2020.</p>"
        f"{_refs(10)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "author_year",
            "confidence": "high",
            "ref_dest_prefix": "B",
            "annotations": [
                {
                    "page": 2,
                    "kind": "reference",
                    "dest": "B7",
                    "target": "7",
                    "text": "Smith et al., 2020",
                }
            ],
        },
    )

    assert '(<a href="#ref-7" class="z2m-ref-link">Smith et al., 2020</a>)' in polished
    assert "from 2019 to 2020" in polished


def test_pdf_annotation_profile_retargets_author_year_page_anchor_once_per_annotation() -> None:
    html = (
        "<html><body>"
        '<p><a href="#page-2-0">Smith et al., 2020</a> reported this. '
        "Smith et al., 2020 was mentioned again as plain prose.</p>"
        f"{_refs(10)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "author_year",
            "confidence": "high",
            "ref_dest_prefix": "B",
            "annotations": [
                {
                    "page": 2,
                    "kind": "reference",
                    "dest": "B7",
                    "target": "7",
                    "text": "Smith et al., 2020",
                }
            ],
        },
    )

    assert '<a href="#ref-7" class="z2m-ref-link">Smith et al., 2020</a> reported this' in polished
    assert polished.count('href="#ref-7"') == 1
    assert "mentioned again as plain prose" in polished


def test_author_year_profile_locks_out_numeric_citation_recovery() -> None:
    html = (
        "<html><body>"
        "<p>Prior work (Smith et al., 2020) found the same pattern. "
        "This local footnote-like marker<sup>2</sup> and stale link "
        '<sup><a href="#ref-3" class="z2m-ref-link">3</a></sup> are not bibliography citations. '
        'A page artifact <a href="#ref-4" class="z2m-ref-link">(4)</a> should stay text.</p>'
        f"{_refs(10)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "author_year",
            "confidence": "high",
            "annotations": [
                {
                    "page": 2,
                    "kind": "reference",
                    "target": "7",
                    "text": "Smith et al., 2020",
                }
            ],
        },
    )
    body = polished[: polished.index("REFERENCES")]

    assert 'href="#ref-7" class="z2m-ref-link">Smith et al., 2020</a>' in body
    assert 'href="#ref-2"' not in body
    assert 'href="#ref-3"' not in body
    assert 'href="#ref-4"' not in body
    assert "marker<sup>2</sup>" in body
    assert "stale link <sup>3</sup>" in body
    assert "page artifact (4) should stay text" in body


def test_superscript_numeric_profile_wraps_annotation_backed_ref_runs_only() -> None:
    html = (
        "<html><body>"
        '<p>Blood vasculatures <a href="#ref-1" class="z2m-ref-link">1,</a> '
        '<a href="#ref-2" class="z2m-ref-link">2</a> and fluorescent agents '
        '<a href="#ref-4" class="z2m-ref-link">.4,</a> '
        '<a href="#ref-5" class="z2m-ref-link">5</a>. '
        "A figure caption mentions phantom 1 and 2.</p>"
        f"{_refs(10)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "superscript_numeric",
            "confidence": "high",
            "annotations": [
                {"page": 2, "kind": "reference", "target": "1", "text": "res1,2"},
                {"page": 2, "kind": "reference", "target": "2", "text": "res1,2"},
                {"page": 2, "kind": "reference", "target": "4", "text": "agents.4,5"},
                {"page": 2, "kind": "reference", "target": "5", "text": "agents.4,5"},
            ],
        },
    )

    assert '<sup><a href="#ref-1" class="z2m-ref-link">1</a>,<a href="#ref-2" class="z2m-ref-link">2</a></sup>' in polished
    assert '<sup><a href="#ref-4" class="z2m-ref-link">4</a>,<a href="#ref-5" class="z2m-ref-link">5</a></sup>' in polished
    assert "</sup> and fluorescent" in polished
    assert "phantom 1 and 2" in polished


def test_superscript_numeric_profile_links_annotation_backed_tex_sup_range() -> None:
    html = (
        "<html><body>"
        r"<p>Nuclear imaging: \(1^{12-14}\). Real binary range \(2^{16}\).</p>"
        f"{_refs(20)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "superscript_numeric",
            "confidence": "high",
            "annotations": [
                {"page": 5, "kind": "reference", "target": "12", "text": "12-14"},
                {"page": 5, "kind": "reference", "target": "14", "text": "12-14"},
            ],
        },
    )

    assert '<sup><a href="#ref-12" class="z2m-ref-link">12</a>-<a href="#ref-14" class="z2m-ref-link">14</a></sup>' in polished
    assert r"\(2^{16}\)" in polished


def test_flattened_superscript_numeric_document_links_groups_without_line_numbers_or_exponents() -> None:
    html = (
        "<html><body>"
        "<p>High tissue penetration. 1,2,3,4 However, dyes remain challenging. "
        "Limitations remain. 5,6,7 The signal can bleach. "
        "Physiology tracking is hard. 8,9,10 Besides, crosstalk is common. "
        "Signals overlap. 11,12,13 Therefore, new dyes are needed. "
        "FRET pair 30 dyes. 14,15,16,17 FRET is non-radiative. "
        "Nanoprobes help bioimaging. 18,19 For example, Tan et al. continued. "
        "The ratio of three dyes.<sup>20,21</sup> Law et al. continued. "
        "The nanomicelles were incubated with tumor HepG2 cell 20 and monitored. "
        "Signals were compared with the QDs 30 and MB dye. "
        "The overlap was 1.39 × 10<sup>-17</sup> M<sup>-1</sup> nm<sup>4</sup>.</p>"
        f"{_refs(30)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
    )

    assert 'penetration.<sup><a href="#ref-1" class="z2m-ref-link">1</a>,<a href="#ref-2" class="z2m-ref-link">2</a>,<a href="#ref-3" class="z2m-ref-link">3</a>,<a href="#ref-4" class="z2m-ref-link">4</a></sup> However' in polished
    assert 'dyes.<sup><a href="#ref-14" class="z2m-ref-link">14</a>,<a href="#ref-15" class="z2m-ref-link">15</a>,<a href="#ref-16" class="z2m-ref-link">16</a>,<a href="#ref-17" class="z2m-ref-link">17</a></sup> FRET' in polished
    assert 'three dyes.<sup><a href="#ref-20" class="z2m-ref-link">20</a>,<a href="#ref-21" class="z2m-ref-link">21</a></sup>' in polished
    assert "cell 20 and" in polished
    assert "QDs 30 and" in polished
    assert '10<sup class="z2m-unit-exp">-17</sup>' in polished
    assert 'nm<sup class="z2m-unit-exp">4</sup>' in polished


def test_zotero_overlay_profile_links_confirmed_flattened_superscript_citations_only() -> None:
    html = (
        "<html><body>"
        "<p>The x2 test and \u03c72 independence test were used before the clinical text. "
        "There are no clear methods to prove the symptoms. 2 Published studies continued. "
        "Treatment was not correlated with pretreatment UDS.3-5 Recently, interest increased. "
        "C-reactive protein.6-10 Genetic association was investigated. "
        "Haylen et al.12 created the Liverpool nomograms. "
        "volume voided plus residual). 14,15 Digesu et al. found another pattern. "
        "No clear parameter. 19 The report continued. "
        "The last marker was PVR). 24 In our study it mattered.</p>"
        f"{_refs(24)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "unknown",
            "confidence": "low",
            "zotero_citations": [
                {"page": 2, "text": "2", "refs": [2], "context": "parity and x2test was used"},
                {"page": 3, "text": "2", "refs": [2], "context": "\u03c72independence test showed"},
                {
                    "page": 1,
                    "text": "2",
                    "refs": [2],
                    "context": "methods to prove the symptoms.2Published studies",
                },
                {
                    "page": 1,
                    "text": "3-5",
                    "refs": [3, 4, 5],
                    "context": "pretreatment UDS.3-5Recently, interest",
                },
                {
                    "page": 1,
                    "text": "6-10",
                    "refs": [6, 7, 8, 9, 10],
                    "context": "C-reactive protein.6-10Genetic association",
                },
                {
                    "page": 4,
                    "text": "12",
                    "refs": [12],
                    "context": "Haylen et al.12created the Liverpool",
                },
                {
                    "page": 4,
                    "text": "14,15",
                    "refs": [14, 15],
                    "context": "voided plus residual).14,15Digesu et al",
                },
                {
                    "page": 4,
                    "text": "19",
                    "refs": [19],
                    "context": "No clear parameter.19The report continued",
                },
                {
                    "page": 4,
                    "text": "24",
                    "refs": [24],
                    "context": "last marker was PVR).24In our study",
                },
            ],
        },
    )

    assert "x<sup>2</sup> test" in polished
    assert "\u03c7<sup>2</sup> independence test" in polished
    assert 'x<sup><a href="#ref-2"' not in polished
    assert '\u03c7<sup><a href="#ref-2"' not in polished
    assert 'symptoms.<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> Published' in polished
    assert 'UDS.<sup><a href="#ref-3" class="z2m-ref-link">3</a>-<a href="#ref-5" class="z2m-ref-link">5</a></sup> Recently' in polished
    assert 'protein.<sup><a href="#ref-6" class="z2m-ref-link">6</a>-<a href="#ref-10" class="z2m-ref-link">10</a></sup> Genetic' in polished
    assert 'al.<sup><a href="#ref-12" class="z2m-ref-link">12</a></sup> created' in polished
    assert 'residual).<sup><a href="#ref-14" class="z2m-ref-link">14</a>,<a href="#ref-15" class="z2m-ref-link">15</a></sup> Digesu' in polished
    assert 'parameter.<sup><a href="#ref-19" class="z2m-ref-link">19</a></sup> The' in polished
    assert 'PVR).<sup><a href="#ref-24" class="z2m-ref-link">24</a></sup> In' in polished


def test_superscript_numeric_profile_links_comma_before_range_citation() -> None:
    html = (
        "<html><body>"
        "<p>It has been reported for colloidal quantum dots, 37-39 and the emission is quenched.</p>"
        f"{_refs(41)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert (
        'quantum dots,<sup><a href="#ref-37" class="z2m-ref-link">37</a>-'
        '<a href="#ref-39" class="z2m-ref-link">39</a></sup> and'
    ) in polished


def test_superscript_numeric_profile_recovers_author_adjacent_flattened_citations() -> None:
    html = (
        "<html><body>"
        "<p>Martiniello et al. 18 report broad tablet adoption. "
        "Wang et al24 compared saliency models. "
        "Program management.21 improved after follow-up. "
        "FRET pair 30 dyes stayed a measurement phrase. "
        "Figure 2 shows the apparatus.</p>"
        f"{_refs(30)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert 'et al.<sup><a href="#ref-18" class="z2m-ref-link">18</a></sup> report' in polished
    assert 'et al<sup><a href="#ref-24" class="z2m-ref-link">24</a></sup> compared' in polished
    assert 'management.<sup><a href="#ref-21" class="z2m-ref-link">21</a></sup> improved' in polished
    assert "FRET pair 30 dyes" in polished
    assert "Figure 2 shows" in polished
    assert 'href="#ref-30"' not in polished
    assert 'href="#ref-2"' not in polished


def test_superscript_numeric_profile_retargets_space_separated_ref_run_links() -> None:
    html = (
        "<html><body>"
        '<p>Reference tests were reported <a href="#ref-9" class="z2m-ref-link">'
        "22-25 28 29 34 35 37-39 41 44 47 50 51 55-57"
        "</a>. Criterion validity was "
        '<a href="#ref-32" class="z2m-ref-link">44 51 55 56</a>.</p>'
        f"{_refs(60)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert 'href="#ref-9" class="z2m-ref-link">22-25' not in polished
    assert (
        '<sup><a href="#ref-22" class="z2m-ref-link">22</a>-'
        '<a href="#ref-25" class="z2m-ref-link">25</a> '
        '<a href="#ref-28" class="z2m-ref-link">28</a>'
    ) in polished
    assert (
        'Criterion validity was <sup><a href="#ref-44" class="z2m-ref-link">44</a> '
        '<a href="#ref-51" class="z2m-ref-link">51</a> '
        '<a href="#ref-55" class="z2m-ref-link">55</a> '
        '<a href="#ref-56" class="z2m-ref-link">56</a></sup>.'
    ) in polished


def test_superscript_numeric_profile_moves_closing_paren_out_of_ref_link() -> None:
    html = (
        "<html><body>"
        '<p>The value was r=0.29 <a href="#ref-56" class="z2m-ref-link">56)</a> '
        'and specificity was 92% <a href="#ref-51" class="z2m-ref-link">51)</a>.</p>'
        f"{_refs(60)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert 'r=0.29 <sup><a href="#ref-56" class="z2m-ref-link">56</a></sup>)' in polished
    assert '92% <sup><a href="#ref-51" class="z2m-ref-link">51</a></sup>)' in polished
    assert '>56)</a>' not in polished
    assert '>51)</a>' not in polished


def test_superscript_numeric_profile_does_not_link_comma_measurement_series() -> None:
    html = (
        "<html><body>"
        '<p class="z2m-figure-caption">Fig. 8. Fluorescence response '
        "from top: 0, 0.2, 0.8, 1, 2, 4, 6, 8 and 10 uM.</p>"
        f"{_refs(10)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={"style": "superscript_numeric", "confidence": "high"},
    )

    assert "0.8, 1, 2, 4, 6, 8 and 10 uM" in polished
    assert 'href="#ref-1"' not in polished


def test_zotero_overlay_profile_does_not_link_chemical_formula_numbers() -> None:
    html = (
        "<html><body>"
        "<p>The H2O signal, CO2 signal, TiO2 layer, and sp2 carbon were compared. "
        "There are no clear methods to prove the symptoms. 2 Published studies continued.</p>"
        f"{_refs(2)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "unknown",
            "confidence": "low",
            "zotero_citations": [
                {"page": 1, "text": "2", "refs": [2], "context": "The H2O signal"},
                {"page": 1, "text": "2", "refs": [2], "context": "CO2 signal"},
                {"page": 1, "text": "2", "refs": [2], "context": "TiO2 layer"},
                {"page": 1, "text": "2", "refs": [2], "context": "sp2 carbon were compared"},
                {
                    "page": 1,
                    "text": "2",
                    "refs": [2],
                    "context": "methods to prove the symptoms.2Published studies",
                },
            ],
        },
    )

    assert "H2O signal" in polished
    assert "CO2 signal" in polished
    assert "TiO2 layer" in polished
    assert "sp2 carbon" in polished
    assert 'H<sup><a href="#ref-2"' not in polished
    assert 'CO<sup><a href="#ref-2"' not in polished
    assert 'TiO<sup><a href="#ref-2"' not in polished
    assert 'sp<sup><a href="#ref-2"' not in polished
    assert 'symptoms.<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> Published' in polished


def test_zotero_overlay_profile_handles_rsc_notes_and_references_front_matter() -> None:
    html = (
        "<html><body>"
        "<p>The particles were below 10 nm. 1,2 Owing to robust inertness, CDs are "
        "useful in bioimaging, 3,4 photocatalysis. 5,6 and light-emitting devices.</p>"
        "<h4>Notes and references</h4>"
        '<p block-type="ListGroup" class="has-continuation z2m-affiliations"><ul>'
        "<li><sup>a</sup> Key Laboratory for Chemistry, Guangxi Normal University, China. "
        "Fax: (+86) 773-5832294; Tel: (+86)</li>"
        "<li>10 773-5845973; E-mail: jzhao12@example.org</li>"
        "<li><sup>b</sup> Guilin Normal College, Guilin, 541001, China.</li>"
        "<li>† Electronic Supplementary Information (ESI) available: figures and tables.</li>"
        "<li>Y. Fang, S. Guo, D. Li, ACS Nano, 2012, 6, 400-409.</li>"
        "<li>S. N. Baker and G. A. Baker, Angew. Chem. Int. Ed., 2010, 49, 6726-6726.</li>"
        "<li>L. Cao, X. Wang and Y. P. Sun, J. Am. Chem. Soc., 2007, 129, 11318-11319.</li>"
        "<li>S. Yang, L. Cao and Y. P. Sun, J. Am. Chem. Soc., 2009, 131, 11308-11309.</li>"
        "<li>H. Li, X. He and S. T. Lee, Angew. Chem. Int. Ed., 2010, 49, 4430-4434.</li>"
        "<li>L. Cao, S. Sahu and Y. P. Sun, J. Am. Chem. Soc., 2011, 133, 4754-4757.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "unknown",
            "confidence": "low",
            "zotero_citations": [
                {"text": "1,2", "refs": [1, 2], "context": "were below 10 nm.1,2Owing to robust"},
                {"text": "3,4", "refs": [3, 4], "context": "useful in bioimaging,3,4photocatalysis"},
                {"text": "5,6", "refs": [5, 6], "context": "photocatalysis.5,6and light-emitting"},
            ],
        },
    )

    assert '<li><sup>a</sup> Key Laboratory' in polished
    assert 'id="ref-1"><span class="z2m-ref-num">1.</span> Y. Fang' in polished
    assert 'id="ref-1"><sup>a</sup>' not in polished
    assert 'below 10 nm.<sup><a href="#ref-1" class="z2m-ref-link">1</a>,<a href="#ref-2" class="z2m-ref-link">2</a></sup> Owing' in polished
    assert 'bioimaging,<sup><a href="#ref-3" class="z2m-ref-link">3</a>,<a href="#ref-4" class="z2m-ref-link">4</a></sup> photocatalysis' in polished
    assert 'photocatalysis.<sup><a href="#ref-5" class="z2m-ref-link">5</a>,<a href="#ref-6" class="z2m-ref-link">6</a></sup> and' in polished


def test_rsc_nested_reference_items_keep_true_numbers_and_link_series_superscripts() -> None:
    ref_prefix = "".join(f"<li>{idx}. Reference {idx}.</li>" for idx in range(1, 5))
    ref_middle = (
        "<li>25 5 H. Li, X. He and S. T. Lee, Angew. Chem. Int. Ed., 2010, 49, 4430-4434.</li>"
        + "".join(f"<li>{idx} A. Author, Journal, 2012, {idx}, 1-2.</li>" for idx in range(6, 21))
    )
    html = (
        "<html><body>"
        "<p>Carbonizing organics routes<sup>15-18</sup> and green sources such as "
        "soybeans,<sup>21</sup> orange juice,<sup>22</sup> gas soot,<sup>23</sup> grass,"
        "<sup>24</sup> watermelon peel,<sup>25</sup> pomelo peel,<sup>26</sup> ginger"
        "<sup>27</sup> and honey.<sup>28</sup> Electron transfer was reported"
        "<sup>37-39</sup> and confirmed.<sup>40</sup> Final work.<sup>41</sup></p>"
        "<h4>Notes and references</h4>"
        "<p block-type='ListGroup'><ul>"
        f"{ref_prefix}{ref_middle}"
        "<li>60 21 C. Zhu, J. Zhai and S. Dong, Chem. Commun., 2012, 48, 9367-9369."
        "<ul><li class='list-indent-1'>22 S. Sahu, B. Behera and S. Mohapatra, Chem. Commun., 2012, 48, 8835-8837.</li></ul>"
        "<ul><li class='list-indent-1'>23 L. Tian, D. Ghosh and S. Chen, Chem. Mater., 2009, 21, 2803-2809.</li></ul>"
        "</li>"
        "<li>65 24 S. Liu, J. Tian and X. Sun, Adv. Mater., 2012, 24, 2037-2041.</li>"
        "<li>25 J. Zhou, Z. Sheng and C. Li, Mater. Lett., 2012, 66, 222-224.</li>"
        "</ul></p>"
        "<p block-type='ListGroup'><ul>"
        "<li>26 W. Lu, X. Qin and X. Sun, Anal. Chem., 2012, 84, 5351-5357.</li>"
        "<li>27 C. L. Li, C. M. Ou and H. T. Chang, J. Mater. Chem. B, 2014, 2, 4564-4571.</li>"
        "<li>75 28 X. M. Yang, Y. Zhuo and Y. Dou, Biosens. Bioelectron., 2014, 60, 292-298."
        "<ul><li class='list-indent-1'>29 I. A. W. Tan, A. L. Ahmad and B. Hameed, Desalination, 2008, 225, 13-28.</li></ul>"
        "<ul><li class='list-indent-1'>30 M. Auta and B. Hameed, Chem. Eng. J., 2014, 237, 352-361.</li></ul>"
        "</li>"
        "<li>80 31 A. M. Vargas, A. L. Cazetta and V. Almeida, Chem. Eng. J., 2011, 168, 722-730."
        "<ul><li class='list-indent-1'>M. H. Wheeler and J. S. H. Wade, Am. J. Surg., 1982, 143, 713-716.</li></ul>"
        "<ul><li class='list-indent-1'>J. Sprung, D. L. Bourke and P. Thomas, J. Clin. Monit., 1994, 10, 267-269.</li></ul>"
        "</li>"
        "<li>R. Liu, D. Wu, S. Liu, K. Koynov and Q. Li, Angew. Chem., 2009, 121, 4668-4671.</li>"
        "<li>35 Y. P. Sun, B. Zhou and S. Xie, J. Am. Chem. Soc., 2006, 128, 7756-7757.</li>"
        "<li>36 J. Peng, W. Gao and P. M. Ajayan, Nano Lett., 2012, 12, 844-849.</li>"
        "<li>95 37 J. Huang, Z. Huang and T. Lian, J. Am. Chem. Soc., 2010, 132, 4858-4864."
        "<ul><li class='list-indent-1'>A. Rakovich, D. Savateeva and A. Eychmuller, Nanoscale Res. Lett., 2010, 5, 753-760.</li></ul>"
        "</li>"
        "<li>O. V. Ovchinnikov, M. S. Smirnov, T. S. Shatskikh, V. Y. 100 39 Khokhlov, B. Shapiro and S. Ambrozevich, J. Nanopart. Res., 2014, 16, 2286-2304."
        "<ul><li class='list-indent-1'>P. V. Kamat, N. M. Dimitrijevic and R. Fessenden, J. Phys. Chem., 1987, 91, 396-401.</li></ul>"
        "</li>"
        "<li>105 41 Y. Yan, M. Zhang and L. Mao, Chem. Mater., 2005, 17, 3457-3463.</li>"
        "</ul></p>"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "superscript_numeric",
            "confidence": "high",
            "zotero_citations": [
                {"text": "21", "refs": [21], "context": "sources such as soybeans,21orange juice"}
            ],
        },
    )
    ref_section = polished[polished.index("Notes and references") :]

    assert 'id="ref-5"><span class="z2m-ref-num">5.</span> H. Li' in ref_section
    assert 'id="ref-22"><span class="z2m-ref-num">22.</span> S. Sahu' in ref_section
    assert 'id="ref-23"><span class="z2m-ref-num">23.</span> L. Tian' in ref_section
    assert 'id="ref-29"><span class="z2m-ref-num">29.</span> I. A. W. Tan' in ref_section
    assert 'id="ref-32"><span class="z2m-ref-num">32.</span> M. H. Wheeler' in ref_section
    assert 'id="ref-40"><span class="z2m-ref-num">40.</span> P. V. Kamat' in ref_section
    assert 'id="ref-41"><span class="z2m-ref-num">41.</span> Y. Yan' in ref_section
    assert "25 5 H. Li" not in ref_section
    assert "60 21 C. Zhu" not in ref_section
    assert "100 39 Khokhlov" not in ref_section
    assert "V. Y. Khokhlov" in ref_section
    assert 'routes<sup><a href="#ref-15" class="z2m-ref-link">15</a>-<a href="#ref-18" class="z2m-ref-link">18</a></sup> and' in polished
    for ref_id in (21, 22, 23, 24, 25, 26, 27, 28, 37, 39, 40, 41):
        assert f'href="#ref-{ref_id}"' in polished[: polished.index("Notes and references")]


def test_notes_and_references_heading_requires_zotero_overlay_evidence() -> None:
    html = (
        "<html><body>"
        "<p>A local note mentions 1,2 but no overlay confirmed bibliography.</p>"
        "<h4>Notes and references</h4>"
        "<ul><li>Not necessarily a bibliography.</li><li>Another note.</li></ul>"
        "</body></html>"
    )

    polished = polish_html_document(html, table_caption_language="en")

    assert 'id="ref-1"' not in polished
    assert 'href="#ref-1"' not in polished


def test_superscript_numeric_profile_links_annotation_backed_plain_number_by_context() -> None:
    html = (
        "<html><body>"
        "<p>A control value 15 The device ignored this. "
        "Applications include gastrointestinal surgery following i.v. administration of ICG. "
        "15 The NOVADAQ system was used.</p>"
        f"{_refs(20)}"
        "</body></html>"
    )

    polished = polish_html_document(
        html,
        table_caption_language="en",
        citation_profile={
            "style": "superscript_numeric",
            "confidence": "high",
            "annotations": [
                {"page": 5, "kind": "reference", "target": "15", "text": "intestin G.15 Th"},
            ],
        },
    )

    assert "control value 15 The device" in polished
    assert 'ICG.<sup><a href="#ref-15" class="z2m-ref-link">15</a></sup> The NOVADAQ' in polished
    assert polished.count('href="#ref-15"') == 1
