import importlib.util
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "audit_en_polish.py"


def _make_temp_dir() -> Path:
    path = Path(".tmp_local2") / f"test_audit_en_polish_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_en_polish", AUDIT_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fast_line_lookup_matches_count_based_lookup() -> None:
    audit = _load_audit_module()
    text = "first line\nsecond line\n\nfourth line"
    starts = audit._line_starts(text)

    for offset in range(len(text) + 1):
        assert audit._line_at_from_starts(starts, offset) == audit._line_at(text, offset)


def test_analyze_pair_reports_manual_review_defect_shapes() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "\n".join(
                    [
                        "<html><body>",
                        "<p>Zhen Ling Teo © 1,2,15, Robert Morris 10 13, Daniel Ting 1.2.5</p>",
                        "<p>Xavier Quill 10 13, Nora Vale 1.2.5</p>",
                        "<p block-type=\"Equation\"><math>Z_1|_{\\frac{\\omega}{2m}=1}</math> (3)</p>",
                        "</body></html>",
                    ]
            ),
            encoding="utf-8",
        )
        polish_path.write_text(
            "\n".join(
                [
                    "<html><head><style>.z2m-ref-link{}</style></head><body>",
                    "<p>Alice Example <sup><a href=\"#ref-1\" class=\"z2m-ref-link\">1</a>,"
                    "<a href=\"#ref-2\" class=\"z2m-ref-link\">2</a></sup>, "
                    "Bob Example <sup><a href=\"#ref-3\" class=\"z2m-ref-link\">3</a></sup></p>",
                    "<p class=\"z2m-affiliations\"><a href=\"#ref-1\" class=\"z2m-ref-link\">1</a> Department.</p>",
                    "<p>Different functions [1-4] and current 2.3 mC cm - 2 were observed.</p>",
                    "<table><tr><td>Atlas [34,<br/>35, 40–43]</td></tr></table>",
                    '<p>The probe moved at 0.01 mm s <i>−</i> <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> '
                    'and subtended 1.5 <i>◦ ×</i> 1.5 <i>◦</i>.</p>',
                    "<p>Formula boundary \\(IrOH + H^+ + e^- [17]\\) is broken.</p>",
                    "<p block-type=\"Equation\">\\[Z_1|_{\\frac{\\omega}{2m}=1}\\] (3)</p>",
                    "<p block-type=\"Equation\">\\(Z_1 = 1\\) (1) To make (1) more clear, we define terms.</p>",
                    "<p block-type=\"Equation\">Fig. 4 shows \\(Z_1\\) is a function of frequency.</p>",
                    "<p block-type=\"Equation\">\\[Ly_s(i)=y(i)\\]</p>",
                    "<p id=\"table-iv\">TABLE IV. Comparison.</p>",
                    "<table><tr><td>Range</td></tr></table>",
                    "<div class=\"z2m-equation-row\">(9)</div>",
                    "<p id=\"fig-2\">Fig. 2 Caption \\label{fig:sample} to evaluate for aspects.</p>",
                    "<p>See <a href=\"#fig-2\" class=\"z2m-fig-link\">Fig. 2</a>.</p>",
                    "<p>Intermediate prose separates the next figure warning.</p>",
                    "<p>Another ordinary paragraph.</p>",
                    "<p>One more ordinary paragraph.</p>",
                    "<p class=\"z2m-missing-figure-warning\">Figure 8 image was not extracted into this HTML.</p>",
                    "<p id=\"fig-8\">Figure 8. Delayed image caption.</p>",
                    "<p>caption continuation.</p>",
                    "<p><img src=\"fig8.png\"/></p>",
                    "<p>The lack of distortion (figures 4(A), (B)) suggests stable shape.</p>",
                    "<p>Copyright 2018 John Wiley &amp; Sons.</p><p>2024 a, b). Each shank was inserted.</p>",
                    "<p>reinforcement learning, which relies on human input (required) image-modeling task in which the model was exposed.</p>",
                    "<h4>References</h4><p id=\"ref-1\">One.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {
            "P01",
            "P02",
            "P03",
            "P04R",
            "P06",
            "P07",
            "P08",
            "P09",
            "P10",
            "P11",
            "P12",
            "P13",
            "P14",
            "P15",
            "P16",
            "P17",
            "P18",
            "P19",
        }
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_rendered_katex_unit_text_for_p06() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Air flow was \\(0.36 m s^{-1}\\).</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><head><style>.z2m-ref-link{}</style></head><body>",
                    '<p>Air flow was <span class="z2m-math z2m-math-inline" role="math" '
                    'data-z2m-tex="\\(0.36 m s^{-1}\\)">'
                    '<span class="katex"><span class="katex-html" aria-hidden="true">'
                    "<span>0.36</span><span>m</span><span>s</span><span>−</span><span>1</span>"
                    "</span></span></span> at the top of the incubator.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P06" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p03_for_early_body_bracket_citations() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>The experimental setup included the Rotational-Translational Chair "
                    '(RT-Chair; <a href="#ref-10" class="z2m-ref-link">[10]</a>) and the '
                    "3D Tune-In Toolkit tool (3DTI Toolkit; "
                    '<a href="#ref-11" class="z2m-ref-link">[11]</a>).</p>',
                    "<h4>References</h4>",
                    "<ol>",
                    *[f"<li>Reference {idx}.</li>" for idx in range(1, 12)],
                    "</ol>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P03" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p03_for_early_zebrafish_body_citations() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>We first examined whether larval zebrafish maintain their pitch during "
                    'spontaneous swim bouts <sup><a href="#ref-42" class="z2m-ref-link">42</a></sup>. '
                    "To measure behavior we used the Scalable Apparatus to Measure Posture and "
                    'Locomotion (SAMPL) <sup><a href="#ref-43" class="z2m-ref-link">43</a></sup>.</p>',
                    "<h4>References</h4>",
                    "<ol>",
                    *[f"<li>Reference {idx}.</li>" for idx in range(1, 44)],
                    "</ol>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P03" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_accepts_wrapped_missing_figure_unit() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><head><style>:target{outline:1px solid blue}[id^=\"fig-\"]{scroll-margin-top:42vh}</style></head><body>",
                    '<p>See <a href="#fig-1" class="z2m-fig-link">Figure 1</a>.</p>',
                    '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">',
                    '<p class="z2m-missing-figure-warning z2m-figure-target">Figure 1 image was not extracted into this HTML.</p>',
                    '<p class="z2m-figure-caption">Figure 1. Caption survived, but the image did not.</p>',
                    "</div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P13" not in defect_ids
        assert "P14" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_accepts_table_surrogate_figure_unit_for_p13_p14() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "table surrogate figure sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><head><style>:target{outline:1px solid blue}[id^=\"fig-\"]{scroll-margin-top:42vh}</style></head><body>",
                    '<p>See <a href="#fig-2" class="z2m-fig-link">Figure 2</a>.</p>',
                    '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">',
                    '<table class="z2m-figure-target">',
                    "<tbody><tr><th></th><th colspan=\"2\">State of the world</th></tr>",
                    "<tr><td>Judge response</td><td>Hit</td><td>False alarm</td></tr></tbody>",
                    "</table>",
                    '<p class="z2m-figure-caption">Figure 2. Modified imitation game and signal detection matrices.</p>',
                    "</div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P13" not in defect_ids
        assert "P14" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_marks_caption_only_missing_warning_as_not_quality_counted() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "caption only missing figure sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><head><style>:target{outline:1px solid blue}[id^=\"fig-\"]{scroll-margin-top:42vh}</style></head><body>"
            '<p>See <a href="#fig-5" class="z2m-fig-link">Figure 5</a>.</p>'
            '<div id="fig-5" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
            '<p data-z2m-origin="caption-only-target" class="z2m-missing-figure-warning z2m-figure-target">'
            "Figure 5 image was not extracted into this HTML.</p>"
            '<p class="z2m-figure-caption">Figure 5. Caption survived, but the image did not.</p>'
            "</div>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p62 = [defect for defect in result["defects_found"] if defect["id"] == "P62"]
        assert len(p62) == 1
        assert p62[0]["extra"]["quality_counted"] is False
        assert p62[0]["extra"]["warning_origin"] == "caption-only-target"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_marks_handled_missing_figure_unit_as_not_quality_counted() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "handled missing figure unit sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><head><style>:target{outline:1px solid blue}[id^=\"fig-\"]{scroll-margin-top:42vh}</style></head><body>"
            '<p>See <a href="#fig-2" class="z2m-fig-link">Figure 2</a>.</p>'
            '<div id="fig-2" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
            '<p class="z2m-missing-figure-warning z2m-figure-target" role="note">'
            "Figure 2 image was not extracted into this HTML.</p>"
            '<p class="z2m-figure-caption">Figure 2. Caption survived, but the image did not.</p>'
            "</div>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p62 = [defect for defect in result["defects_found"] if defect["id"] == "P62"]
        assert len(p62) == 1
        assert p62[0]["extra"]["quality_counted"] is False
        assert p62[0]["extra"]["warning_origin"] == "missing-figure-unit"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_marks_adjacent_caption_missing_warning_as_not_quality_counted() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "adjacent missing caption sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>The taxonomy is shown in Figure 1.</p>'
            '<p class="z2m-missing-figure-warning" role="note">'
            "Figure 1 image was not extracted into this HTML.</p>"
            "<h4><b>Figure 1. NCC MERP harm score.</b></h4>"
            "<p>Category A has the capacity to cause error.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p62 = [defect for defect in result["defects_found"] if defect["id"] == "P62"]
        assert len(p62) == 1
        assert p62[0]["extra"]["quality_counted"] is False
        assert p62[0]["extra"]["warning_origin"] == "caption-only-caption"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_add_corpus_hit_counts_ignores_non_quality_defects() -> None:
    audit = _load_audit_module()
    articles = [
        {
            "defects_found": [
                {"id": "P61", "extra": {"quality_counted": False}},
                {"id": "P62", "extra": {"quality_counted": False}},
                {"id": "P67", "extra": {}},
            ]
        },
        {"defects_found": [{"id": "P61", "extra": {"quality_counted": False}}]},
    ]

    counts = audit._add_corpus_hit_counts(articles)

    assert counts == {"P67": 1}
    assert articles[0]["defects_found"][0]["same_pattern_hits_across_corpus"] == 0
    assert articles[0]["defects_found"][0]["same_pattern_observed_hits_across_corpus"] == 2


def test_analyze_pair_does_not_report_p14_for_duplicate_figure_ids() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "duplicate figure id sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><head><style>:target{outline:1px solid blue}[id^=\"fig-\"]{scroll-margin-top:42vh}</style></head><body>"
            '<p>See <a href="#fig-1" class="z2m-fig-link">Figure 1</a>.</p>'
            '<div id="fig-1" class="z2m-float-unit z2m-figure-unit">'
            '<p class="z2m-figure-target"><img src="fig1-a.jpg"/></p>'
            '<p class="z2m-figure-caption">Figure 1. Extracted image.</p>'
            "</div>"
            '<p id="fig-1">Figure 1. Duplicate caption-only target from another embedded document.</p>'
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P13" not in defect_ids
        assert "P14" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_body_figure_references_for_p13() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "figure prose references sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>Figure 1 provides a visual comparison of generated samples across datasets.</p>"
            "<p>Fig. 3 depicts the first prototype we fabricated.</p>"
            "<p>Fig. 2 , represents the cleaner closed in the manner to hold the covering.</p>"
            "<p>FIG. 1 depicts an exploded perspective view of the system.</p>"
            "<p>Figure 2f summarizes literature results at a specific condition.</p>"
            "<p>Figure 4a ,b represents a recent progress in this direction.</p>"
            "<p>Figure 1 A snapshot of the output 6 Figure 2 : Uroflow Dashboard preview7 Figure 3 Different symptoms.</p>"
            "<p>Figure 6</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P13" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_plain_caption_without_image_for_p13() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "plain caption only sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Figure 5. Caption survived, but no image is nearby.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P13" in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_list_of_figures_table_for_p13() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "list of figures sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<table><tbody><tr><th>Figure 98.</th>"
            "<th>Oversized daguerreotype caption in the list of figures.</th>"
            "<th>348</th></tr></tbody></table>"
            '<div id="fig-98" class="z2m-float-unit z2m-figure-unit">'
            '<p class="z2m-figure-target"><img src="data:image/png;base64,AA=="/></p>'
            "<p>Figure 98. Oversized daguerreotype caption.</p></div>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P13" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_counts_each_missing_figure_warning() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><head><style>p.z2m-missing-figure-warning { color: red; }</style></head><body>",
                    '<p class="z2m-missing-figure-warning">Figure 2 image was not extracted into this HTML.</p>',
                    '<div class="z2m-missing-figure-warning">Figure 4 image was not extracted into this HTML.</div>',
                    '<div class="z2m-missing-figure-unit">',
                    '<p class="z2m-missing-figure-warning">Figure 8 image was not extracted into this HTML.</p>',
                    "</div>",
                    '<p>Figure 6 image was not extracted into this HTML, but this is plain prose.</p>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p62 = [defect for defect in result["defects_found"] if defect["id"] == "P62"]
        assert len(p62) == 3
        assert [defect["extra"]["warning_index"] for defect in p62] == [1, 2, 3]
        assert "Figure 2 image was not extracted" in p62[0]["snippet"]
        assert "Figure 4 image was not extracted" in p62[1]["snippet"]
        assert "Figure 8 image was not extracted" in p62[2]["snippet"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_overlapping_block_parser_keeps_nested_missing_figure_context() -> None:
    audit = _load_audit_module()
    html = "\n".join(
        [
            "<html><body>",
            '<div class="z2m-float-unit">',
            '<p><img src="data:image/png;base64,abc"/></p>',
            '<p class="z2m-missing-figure-warning">Figure 9 image was not extracted into this HTML.</p>',
            '<p class="z2m-figure-caption">Figure 9. Caption belongs to the image above.</p>',
            "</div>",
            "</body></html>",
        ]
    )

    blocks = audit._parse_overlapping_blocks(html)
    warning = next(block for block in blocks if "z2m-missing-figure-warning" in block.classes)
    classification = audit._classify_missing_figure_warning(warning, blocks)

    assert any(block.tag == "div" and block.has_img for block in blocks)
    assert classification["defect_id"] == "P62A"
    assert classification["extra"]["p62_subtype"] == "same_label_image_near_warning"


def test_overlapping_block_parser_treats_figure_table_target_as_visual_context() -> None:
    audit = _load_audit_module()
    html = "\n".join(
        [
            "<html><body>",
            '<div id="fig-9" class="z2m-float-unit z2m-figure-unit">',
            '<table class="z2m-figure-target"><tbody><tr><td>Recommended route</td></tr></tbody></table>',
            '<p class="z2m-missing-figure-warning">Figure 9 image was not extracted into this HTML.</p>',
            '<p class="z2m-figure-caption">Figure 9. Route recommendation matrix.</p>',
            "</div>",
            "</body></html>",
        ]
    )

    blocks = audit._parse_overlapping_blocks(html)
    warning = next(block for block in blocks if "z2m-missing-figure-warning" in block.classes)
    classification = audit._classify_missing_figure_warning(warning, blocks)

    assert any(block.tag == "div" and block.has_figure_visual and not block.has_img for block in blocks)
    assert classification["defect_id"] == "P62A"
    assert classification["extra"]["p62_subtype"] == "same_label_image_near_warning"


def test_analyze_pair_splits_missing_figure_warning_contexts() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        data_img = "data:image/png;base64,abc"
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    f'<p><img src="{data_img}"/></p>',
                    '<p class="z2m-missing-figure-warning">Figure 1 image was not extracted into this HTML.</p>',
                    '<p class="z2m-figure-caption">Figure 1. Caption belongs to the image above.</p>',
                    f'<p><img src="{data_img}"/></p>',
                    '<p class="z2m-missing-figure-warning">Figure 2 image was not extracted into this HTML.</p>',
                    '<p class="z2m-figure-caption">Figure 3. Different caption nearby.</p>',
                    "<p>Filler A.</p>",
                    "<p>Filler B.</p>",
                    "<p>Filler C.</p>",
                    "<p>Filler D.</p>",
                    "<p>Filler E.</p>",
                    "<p>Filler F.</p>",
                    "<p>Filler G.</p>",
                    "<p>Filler H.</p>",
                    '<p class="z2m-missing-figure-warning">Figure 4 image was not extracted into this HTML.</p>',
                    '<p class="z2m-figure-caption">Figure 4. Caption survived, but no image is nearby.</p>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p62a = [defect for defect in result["defects_found"] if defect["id"] == "P62A"]
        p62b = [defect for defect in result["defects_found"] if defect["id"] == "P62B"]
        p62 = [defect for defect in result["defects_found"] if defect["id"] == "P62"]
        assert len(p62a) == 1
        assert len(p62b) == 1
        assert len(p62) == 1
        assert p62a[0]["extra"]["p62_subtype"] == "same_label_image_near_warning"
        assert p62a[0]["extra"]["figure_label"] == "1"
        assert p62b[0]["extra"]["p62_subtype"] == "nearby_image_ambiguous_label"
        assert p62[0]["extra"]["p62_subtype"] == "no_nearby_image"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_classify_missing_warning_across_body_prose_as_p62b() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<div id="fig-1" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">',
                    '<p class="z2m-missing-figure-warning z2m-figure-target">Figure 1 image was not extracted into this HTML.</p>',
                    '<p class="z2m-figure-caption">Figure 1. Missing overview image.</p>',
                    "</div>",
                    "<p>Ordinary prose separates the missing figure from the next visual.</p>",
                    '<div id="fig-2" class="z2m-float-unit z2m-figure-unit">',
                    '<p class="z2m-figure-target"><img src="data:image/png;base64,abc"/></p>',
                    '<p class="z2m-figure-caption">Figure 2. Next figure image.</p>',
                    "</div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p62 = [defect for defect in result["defects_found"] if defect["id"] == "P62"]
        assert any(defect["extra"]["figure_label"] == "1" for defect in p62)
        assert "P62B" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_classify_missing_warning_across_previous_figure_unit_as_p62a() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">',
                    '<p class="z2m-figure-target"><img src="data:image/png;base64,abc"/></p>',
                    '<p class="z2m-figure-caption">Figure 5. Extracted previous figure.</p>',
                    "</div>",
                    '<div id="fig-6" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">',
                    '<p class="z2m-missing-figure-warning z2m-figure-target">Figure 6 image was not extracted into this HTML.</p>',
                    '<p class="z2m-figure-caption">Figure 6. Caption survived, but no image is nearby.</p>',
                    "</div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        p62 = [defect for defect in result["defects_found"] if defect["id"] == "P62"]
        assert "P62A" not in defect_ids
        assert "P62B" not in defect_ids
        assert any(defect["extra"]["figure_label"] == "6" for defect in p62)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_nearby_image_offsets_ignore_different_labeled_figure_unit() -> None:
    audit = _load_audit_module()
    blocks = audit._parse_blocks(
        "<html><body>"
        '<div id="fig-8" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="data:image/png;base64,abc"/></p>'
        '<p class="z2m-figure-caption">Figure 8. Previous extracted image.</p>'
        "</div>"
        '<p id="fig-10">Figure 10. Caption survived, but its image is absent.</p>'
        "</body></html>"
    )

    target = next(block for block in blocks if block.id == "fig-10")

    assert audit._nearby_image_offsets(blocks, target.index, label="10") == []
    assert audit._nearby_image_offsets(blocks, target.index, label=None) == [-1]


def test_analyze_pair_allows_single_image_multiple_caption_alias_for_p57() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "compound figure alias sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<div id="fig-12" class="z2m-float-unit z2m-figure-unit">'
            '<span id="fig-13" class="z2m-float-alias"></span>'
            '<p class="z2m-figure-target"><img src="data:image/png;base64,abc"/></p>'
            '<p class="z2m-figure-caption"><b>Fig. 12.</b> F1 confidence curve.</p>'
            '<p class="z2m-figure-caption"><b>Fig. 13.</b> Precision recall curve.</p>'
            "</div>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P57" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_closes_raw_frontmatter_ocr_when_polish_repairs_markers() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body><p>Zhen Ling Teo \u0412\u00a9 1,2,15, "
            "Nigam H. Shah 10 13, Daniel Shu Wei Ting 1.2.5</p></body></html>",
            encoding="utf-8",
        )
        polish_path.write_text(
            "<html><body><p class=\"z2m-front-matter\">"
            "Zhen Ling Teo<sup>1,2,15</sup>, Nigam H. Shah<sup>10,13</sup> "
            "&amp; Daniel Shu Wei Ting<sup>1,2,5</sup></p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_copyright_notice_as_frontmatter_ocr() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body><p>Copyright: \u00a9 2022 by the authors. "
            "This article is an open access article distributed under the Creative Commons license.</p></body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_all_rights_reserved_notice_as_frontmatter_ocr() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body><p>\u00a9 2013 J. Paul Getty Trust. "
            "All rights reserved.</p></body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_publisher_print_key_as_frontmatter_ocr() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body><p>Printed in the United States of America 10 9 8 7 6 5 4 3</p></body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_dates_addresses_and_toc_as_frontmatter_ocr() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body>"
            "<p>27 June 2019 (27.06.2019)</p>"
            "<p>Submitted: 14.03.2020</p>"
            "<p>Available Online Date: 08.05.2020</p>"
            "<p>Wilhelmina Children's Hospital/University Medical Center Utrecht, "
            "Department of Neonatology, Room KE 04.123.1, Lundlaan 6, "
            "3584 EA Utrecht, The Netherlands</p>"
            "<p>Abstract iii List of Figures and Tables vi Acknowledgements xiii "
            "Chapter 1: Introduction 1.1 Overview 1 1.2 The Process 8 "
            "1.3 Material Culture 21 1.4 Engaging Literature 30</p>"
            "<p>Chapter 5: Sensitizing Accelerators 5.1 Overview 183 "
            "5.2 Introduction 186 5.3 The District 191 5.4 Chloride of Iodine 208 "
            "Chapte r 6: Optics and Exposure 6.1 Overview 240 6.2 Camera Systems 245</p>"
            "</body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_doi_metadata_as_frontmatter_ocr() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body>"
            "<p>To link to this article: https://doi.org/10.1080/17483107.2023.2228827</p>"
            "<p>DOI: 10.1111/j.1747-4949.2011.00654.x</p>"
            "<p>*Correspondence: bfoster@bcm.edu https://doi.org/10.1016/j.cub.2019.08.004</p>"
            "<p>Vision Res . 2015 June ; 111(0 0): 182-196. doi:10.1016/j.visres.2014.10.023.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_publication_toc_and_contact_metadata_as_frontmatter_ocr() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body>"
            "<p>Citation: de Ruyter van Steveninck, J., van Wezel, R., &amp; van Gerven, M. "
            "(2022). End-to-end optimization of prosthetic vision. Journal of Vision, 22(2):20, "
            "1-14, https://doi.org/10.1167/jov.22.2.20.</p>"
            "<p>Please cite this article as: Rowan, D., The detection of virtual objects using echoes by humans, "
            "Hearing Research (2017), doi: 10.1016/j.heares.2017.01.001</p>"
            "<p>Received: 2016.02.26 Accepted: 2016.05.15 Published: 2016.05.27</p>"
            "<p>16.2.1 Gaze Tracking and Image Stabilization</p>"
            "<p>Chapter 1 Introduction1 1.1 Instrumentation and Modelling2 1.1.1 Application of FIM4 "
            "1.2 Aims and Objectives6 Chapter 2 Literature Review8 2.1 Bioimpedance8 "
            "2.1.1 Biological tissue in electric field8 2.1.3 Frequency response of bioimpedance9</p>"
            "<p>Ujejskiego 75, 85-168 Bydgoszcz, Poland Tel: 0048 52 3655 553; e-mail: psoban@wp.pl</p>"
            "</body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_pdf_verified_frontmatter_toc_and_highlight_markers_as_p01() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body>"
            "<p>Yu-Han Wang , Chen Li , Wen-Ching Chen , Poyin Huang 1 2 2 2, 3, 4, 5, 6, 7</p>"
            "<p>Received: 13.12.2018 Accepted: 28.02.2019</p>"
            "<p>Page 1. Introduction 4 2. Keywords 4 3. Accomplishments 4 4. Impact 7 "
            "5. Changes/Problems 7 6. Products 8 7. Participants 8 8. Requirements 9 9. Appendices 9</p>"
            "<p>Patient Cause of blindness Age at onset of blindness Time since onset of blindness "
            "Progression of blindness Braille reading (years) Experience (years)</p>"
            "<p>Prior to microelectrode array placement, T16 underwent a multi-modal MRI session "
            "approximately 45 minutes in duration to guide surgical array placement, based on the "
            "Human Connectome Project parcellation 22.</p>"
            "<p>reality for the blind and weak-sighted people&quot; (project No. 01.2.2-LMT-K-718-01-0060)</p>"
            "<p>1. We present eFlesh, a magnetic tactile sensor. 2. We characterize the response of eFlesh.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_keeps_author_affiliation_marker_frontmatter_ocr() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text(
            "<html><body><p>Xavier Quill 10 13, Nora Vale 1.2.5</p></body></html>",
            encoding="utf-8",
        )
        polish_path.write_text("<html><body><p>Clean body.</p></body></html>", encoding="utf-8")

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P01" in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p12_for_tex_inside_clean_table_body() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<div id="table-1" class="z2m-float-unit z2m-table-unit">'
            '<p class="z2m-table-caption">Table 1. Key structural and electrical parameters.</p>'
            '<table><tr><td data-z2m-tex="\\\\alpha">\\textbf{not caption}</td></tr></table>'
            "</div>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P12" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_marks_source_pdf_replacement_noise_as_non_quality_counted() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>SVRI (&gt;2400 dynes\ufffdsec\ufffdcm-5\ufffdm"
            '<sup class="z2m-unit-exp">2</sup>).</p></body></html>',
            encoding="utf-8",
        )

        result = audit.analyze_pair(
            raw_path,
            polish_path,
            pdf_text_override="SVRI (>2400 dynes\x01sec\x01cm-5\x01m2).",
        )

        p35 = [defect for defect in result["defects_found"] if defect["id"] == "P35"]
        assert p35
        assert p35[0]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_marks_known_ocr_token_present_in_pdf_layer_as_non_quality_counted() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Wherev 2 denotes v T v in the source scan.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(
            raw_path,
            polish_path,
            pdf_text_override="Wherev 2 denotes v T v in the source scan.",
        )

        p71 = [defect for defect in result["defects_found"] if defect["id"] == "P71"]
        assert p71
        assert p71[0]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_keeps_known_ocr_token_quality_counted_when_pdf_layer_is_clean() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Wherev 2 denotes v T v in the generated HTML.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(
            raw_path,
            polish_path,
            pdf_text_override="Where v2 denotes v T v in the source layer.",
        )

        p71 = [defect for defect in result["defects_found"] if defect["id"] == "P71"]
        assert p71
        assert p71[0]["extra"].get("quality_counted") is not False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_numeric_vectors_as_citation_ranges() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The unnormalized likelihood assignment vector would be [6, 0, 0, 10]. "
            "Dividing by 16 gives [0.375, 0, 0, 0.625].</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P04" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_software_version_sup_lists_as_citation_ranges() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>The model was implemented in PyTorch version <sup>1,3,1</sup>, "
            "using CUDA driver version <sup>10,2</sup>.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P04" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_splits_table_sup_ranges_from_body_p04() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<table><tr><th>Antonio Lozano <sup>1,2</sup>, Xing Chen <sup>1,3</sup></th></tr></table>"
            "<h4>References</h4><ol><li>Ref one.</li><li>Ref two.</li><li>Ref three.</li></ol>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P04" not in defects_by_id
        assert defects_by_id["P04T"]["severity"] == "warning"
        assert defects_by_id["P04T"]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_affiliation_markers_in_frontmatter_table_for_p04t() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><table><tr><td>"
            "1 Large-scale mapping of artificial perceptions "
            "Antonio Lozano 1,2, Xing Chen 1,3, Mike La Grouw 1, "
            "Eduardo Fernandez 2,4 and Pieter Roelfsema 1,6,7,8. "
            "1 Department of Vision and Cognition, Netherlands Institute for Neuroscience. "
            "2 Division of Neurobiology, University of Denmark. "
            "3 These authors contributed equally."
            "</td></tr></table></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P04T" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_search_statement_year_range_for_p04t() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><table><tr><td>"
            "Set Number Concept Search Statement 5. PCL Devices #1 AND "
            "('adhesion barrier'/exp OR 'mesh':ti,ab) AND [2011-2021]"
            "</td></tr></table></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P04T" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_splits_math_ranges_from_body_p04() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The produced center point heatmap is P in [0, 1] "
            "for each class score.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P04" not in defects_by_id
        assert "P04M" not in defects_by_id
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_splits_interval_arrays_from_body_p04() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Converted to intervals: [4,9,12,14,56,59]</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P04" not in defects_by_id
        assert "P04M" not in defects_by_id
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_unlinked_sup_citation_range_in_math_context_as_p04m() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>The measured values were consistent with the magnetic-force model"
            "<sup>28-31</sup>.</p>"
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 32))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P04" not in defects_by_id
        assert defects_by_id["P04M"]["severity"] == "warning"
        assert defects_by_id["P04M"]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_coordinate_points_as_p04m() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The map size is [1000 x 1000], with starting and ending "
            "points of [480, 500] and [900, 450], respectively.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P04" not in defect_ids
        assert "P04M" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_prefers_body_p04_over_table_or_math_p04_splits() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<table><tr><td>Author <sup>1,2</sup></td></tr></table>"
            "<p>Prior studies [1, 2] support the method.</p>"
            '<h4>References</h4><ol><li id="ref-1">Ref one.</li><li id="ref-2">Ref two.</li></ol>'
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P04" in defect_ids
        assert "P04T" not in defect_ids
        assert "P04M" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_classifies_p04_without_reference_targets() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Prior studies [1, 2] support the method.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P04" not in defects_by_id
        assert defects_by_id["P04N"]["severity"] == "warning"
        assert defects_by_id["P04N"]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_classifies_p04_with_missing_reference_targets() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>Settings were presented in [6, 7].</p>"
            '<h4>References</h4><ol><li id="ref-5">Merged ref.</li><li id="ref-8">Later ref.</li></ol>'
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P04" not in defects_by_id
        assert defects_by_id["P04R"]["severity"] == "warning"
        assert defects_by_id["P04R"]["extra"]["missing_targets"] == [6, 7]
        assert defects_by_id["P04R"]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_cli_writes_pair_audit_report() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        root = tmp_path / "root"
        stage_dir = root / "Clean sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        (stage_dir / "01.en.raw.html").write_text(
            "<html><body><p><img src=\"fig.png\"></p><p>Figure 1. Caption.</p></body></html>",
            encoding="utf-8",
        )
        (stage_dir / "02.en.polish.html").write_text(
            "<html><body><p><img src=\"data:image/png;base64,AAAA\"></p><p id=\"fig-1\">Figure 1. Caption.</p></body></html>",
            encoding="utf-8",
        )
        out_path = tmp_path / "pair_audit.json"

        exit_code = audit.main(["--roots", str(root), "--out", str(out_path), "--fail-on-error"])

        assert exit_code == 0
        report = json.loads(out_path.read_text(encoding="utf-8"))
        assert report["article_count"] == 1
        assert report["articles"][0]["summary"]["polish_fig_ids"] == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_missing_local_image_assets() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Figure 1. Caption.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            '<html><body><p><img src="_page_1_Figure_1.jpeg"></p></body></html>',
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P20" in defect_ids
        assert result["summary"]["polish_missing_local_images"] == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_flatten_adjacent_table_unit_cells_into_p06() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<table><tr><th>Parameter</th><th>Test sensor</th><th>Final sensor</th></tr>",
                    "<tr><td>Outer radius</td><td>10 mm</td><td>2 mm</td></tr>",
                    "<tr><td>Trace thickness</td><td>35 µm</td><td>35 µm</td></tr></table>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P06" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_flatten_wrapped_table_unit_cells_into_p06() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<div id="table-ii" class="z2m-float-unit z2m-table-unit"><table>',
                    "<tr><th>Parameter</th><th>Test sensor</th><th>Final sensor</th></tr>",
                    "<tr><td>Outer radius</td><td>10 mm</td><td>2 mm</td></tr>",
                    "<tr><td>Plate thickness</td><td>1.57 mm</td><td>1.57 mm</td></tr>",
                    "</table></div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P06" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p06_ignores_large_unit_followed_by_citation_or_uppercase_m2_label() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>The pitch was 50 \u03bcm 151 in a citation context.</p>"
            "<p>The M2 occlusion and 350M 2 model label remain prose.</p>"
            "<p>The BMI unit kg/m2 and irradiance unit W/m2 remain acceptable plain-text denominators.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P06" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p06_reports_plain_area_unit_exponent() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The indoor maze covered 8 x 4 m 2.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P06" in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_bracket_citation_after_unit() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Charge density stayed at 100 \u03bcC cm<sup class="z2m-unit-exp">-2</sup> '
            '[<a href="#ref-13" class="z2m-ref-link">13</a>].</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 14))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_whole_bracket_ref_anchor_after_unit() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Charge density stayed at 100 \u03bcC cm<sup class="z2m-unit-exp">-2</sup> '
            '<a href="#ref-13" class="z2m-ref-link">[13]</a>.</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 14))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_sentence_final_sup_citation_before_ph() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>OAB should be investigated.'
            '<sup><a href="#ref-10" class="z2m-ref-link">10</a></sup> '
            "The most recent study shows a strong correlation between urine pH and symptoms."
            '<sup><a href="#ref-11" class="z2m-ref-link">11</a></sup></p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 12))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_sentence_final_sup_citation_group() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>The range of phosphene sizes."
            '<sup><a href="#ref-40" class="z2m-ref-link">40</a>,'
            '<a href="#ref-41" class="z2m-ref-link">41</a></sup> '
            "Furthermore, stimulus current can alter phosphene size.</p>"
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 42))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_long_bracket_citation_before_phosphene() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>Prior work used uniform maps "
            '[<a href="#ref-13" class="z2m-ref-link">13</a>, '
            '<a href="#ref-18" class="z2m-ref-link">18</a>, '
            '<a href="#ref-21" class="z2m-ref-link">21</a>, '
            '<a href="#ref-22" class="z2m-ref-link">22</a>, '
            '<a href="#ref-23" class="z2m-ref-link">23</a>, '
            '<a href="#ref-24" class="z2m-ref-link">24</a>, '
            '<a href="#ref-25" class="z2m-ref-link">25</a>, '
            '<a href="#ref-26" class="z2m-ref-link">26</a>, '
            '<a href="#ref-27" class="z2m-ref-link">27</a>, '
            '<a href="#ref-29" class="z2m-ref-link">29</a>, '
            '<a href="#ref-34" class="z2m-ref-link">34</a>-'
            '<a href="#ref-36" class="z2m-ref-link">36</a>]. '
            "The number of phosphenes was then matched.</p>"
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 37))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_month_word_citation() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Recognition improved over the course of a month <a href="#ref-29" class="z2m-ref-link">29</a>.</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 30))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P05" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_author_degree_byline() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>ALPHA ONE, F.R.C.S.(SN), <a href="#ref-1" class="z2m-ref-link">1</a> '
            'BETA TWO, M.D., <a href="#ref-4" class="z2m-ref-link">4</a> '
            'GAMMA THREE, PH.D., <a href="#ref-1" class="z2m-ref-link">1</a>, '
            '<a href="#ref-3" class="z2m-ref-link">3</a> DELTA FOUR, B.Sc., '
            '<a href="#ref-1" class="z2m-ref-link">1</a> EPSILON FIVE, F.R.C.S.(SN), '
            '<a href="#ref-2" class="z2m-ref-link">2</a></p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 5))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P05" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_animal_human_study_citations() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Sensitivity was reported in animal<sup><a href="#ref-17" class="z2m-ref-link">17</a></sup> '
            'and human studies of retinal<sup><a href="#ref-18" class="z2m-ref-link">18</a>,'
            '<a href="#ref-19" class="z2m-ref-link">19</a></sup> and cortical'
            '<sup><a href="#ref-43" class="z2m-ref-link">43</a></sup> stimulation.</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 44))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P05" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_measurement_parenthetical_citation() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Specificity (68%-90%<a href="#ref-28" class="z2m-ref-link">28</a>) was measured '
            'with rates (&lt;10 mL/s, &lt;15 mL/s, &lt;19 mL/s'
            '<a href="#ref-28" class="z2m-ref-link">28</a>).</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 29))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P05" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_d2_type_receptor_citation() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Overexpression of D2-type dopamine receptors disrupts timing'
            '<sup><a href="#ref-192" class="z2m-ref-link">192</a></sup>.</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 193))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P05" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_et_al_citation_near_ph() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Patients with PH were evaluated. Tonelli et al<sup>'
            '<a href="#ref-10" class="z2m-ref-link">10</a></sup> compared methods.</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 11))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_parenthetical_tail_citation_after_units() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>The probe area was 15 × 60 µm<sup class="z2m-unit-exp">2</sup> '
            '<a href="#ref-25" class="z2m-ref-link">)25</a>. '
            "Critical challenges remained.</p>"
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 26))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p05_for_clean_citation_after_unit_parenthetical() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>Similar macroporous networks can be formed into probes with advantages '
            '(<a href="#fig-2" class="z2m-fig-link">Fig. 2c</a>, bottom) '
            '<a href="#ref-50" class="z2m-ref-link">50</a>. '
            "The stiffness is much lower than silicon probes (~10-9 Nm2, "
            'cross-sectional area of 15 x 60 Вµm<sup class="z2m-unit-exp">2</sup>)'
            '<a href="#ref-25" class="z2m-ref-link">25</a>.</p>'
            "<h4>References</h4><ol>"
            + "".join(f'<li id="ref-{idx}">Reference {idx}.</li>' for idx in range(1, 51))
            + "</ol></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_resolves_stage_images_from_article_folder() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        article_dir = tmp_path / "Article sample"
        stage_dir = article_dir / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        (article_dir / "_page_1_Figure_1.jpeg").write_bytes(b"\xff\xd8\xfffake")
        raw_path.write_text("<html><body><p>Figure 1. Caption.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            '<html><body><p><img src="_page_1_Figure_1.jpeg"></p></body></html>',
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P20" not in defect_ids
        assert result["summary"]["polish_missing_local_images"] == 0
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_duplicate_visual_across_distinct_figures() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<div id="fig-5" class="z2m-figure-unit">',
                    f'<p class="z2m-figure-target"><img src="{data_url}"></p>',
                    '<p class="z2m-figure-caption">Figure 5. Correct caption.</p>',
                    "</div>",
                    '<div id="fig-6" class="z2m-figure-unit">',
                    f'<p class="z2m-figure-target"><img src="{data_url}"></p>',
                    '<p class="z2m-figure-caption">Figure 6. Different caption.</p>',
                    "</div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P96" in defects_by_id
        assert defects_by_id["P96"]["extra"]["figure_ids"] == ["fig-5", "fig-6"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_reference_identity_mismatch_and_duplicates() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<ul><li id="ref-58"><span class="z2m-ref-num">56.</span> Drifted ref.</li>',
                    '<li id="ref-59"><span class="z2m-ref-num">56.</span> Duplicate visible ref.</li></ul>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P21" in defect_ids
        assert "P22" in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_reference_target_missing_visible_number() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<ol><li id="ref-1"><span class="z2m-ref-num">1.</span> Smith J. Example.</li>',
                    '<li id="ref-2">Jones J. Unnumbered visible entry.</li></ol>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P97" in defects_by_id
        assert defects_by_id["P97"]["extra"]["missing_visible_ref_ids"] == [2]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_accepts_bracketed_visible_reference_number() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<ol><li id="ref-1">[1] Smith J. Example.</li>',
                    '<li id="ref-2">[2] Jones J. Bracket-numbered entry.</li></ol>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P97" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_numeric_ref_link_in_author_year_article() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Smith et al. (2020), Jones and Brown (2021), Gupta &amp; Pruthi (2025), "
                    "Lund and Naheem (2023), Yeo-The &amp; Tang (2023), and Lehman and Stanley (2011) "
                    'define the author-year style, but this marker <sup><a href="#ref-12" '
                    'class="z2m-ref-link">12</a></sup> should not be a bibliography link.</p>',
                    "<h4>References</h4><ol>",
                    *[
                        f'<li id="ref-{idx}"><span class="z2m-ref-num">{idx}.</span> Reference {idx}.</li>'
                        for idx in range(1, 13)
                    ],
                    "</ol></body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert "P98" in defects_by_id
        assert defects_by_id["P98"]["extra"]["ref_target"] == "12"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_citation_style_audit_ignores_reference_years_for_pdf_cite_numeric_article() -> None:
    audit = _load_audit_module()
    html = "\n".join(
        [
            "<html><body>",
            '<p>Numeric citation style keeps this link <sup><a href="#ref-3" '
            'class="z2m-ref-link">3</a></sup> and this one <sup><a href="#ref-4" '
            'class="z2m-ref-link">4</a></sup>.</p>',
            "<h4>References</h4><ol>",
            *[
                f'<li id="ref-{idx}"><span class="z2m-ref-num">{idx}.</span> '
                f"Smith J. Example numeric reference. {2010 + idx}.</li>"
                for idx in range(1, 8)
            ],
            "</ol></body></html>",
        ]
    )
    pdf_text = (
        "References. Smith et al. (2020). Jones and Brown (2021). "
        "Gupta & Pruthi (2022). Lund and Naheem (2023). "
        "Yeo-The and Tang (2024). Lehman and Stanley (2025)."
    )

    defects = audit._citation_style_consistency_defects(
        html,
        audit._parse_blocks(html),
        pdf_text=pdf_text,
        pdf_link_summary={
            "pdf_citation_dest_links": 20,
            "pdf_author_year_link_labels": 0,
        },
    )

    assert [defect.id for defect in defects] == []


def test_analyze_pair_does_not_report_p22_for_numeric_value_rows() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    "<p>1.90 1.97 1.68 1.13 0.79</p>",
                    '<p id="ref-1"><span class="z2m-ref-num">1.</span> Smith J. Example reference.</p>',
                    '<p id="ref-2"><span class="z2m-ref-num">2.</span> Jones J. Another reference.</p>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P22" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p22_for_post_reference_numbered_outline() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<p id="ref-1"><span class="z2m-ref-num">1.</span> Smith J. Example reference. 2020.</p>',
                    '<p id="ref-2"><span class="z2m-ref-num">2.</span> Jones J. Another reference. 2021.</p>',
                    "<h2>Generated outline</h2>",
                    "<p>1. Forward process: gradually adds Gaussian noise.</p>",
                    "<p>2. Reverse process: removes this noise.</p>",
                    "<h3>2.1 Multi-scale approaches</h3>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P22" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p22_for_local_abstract_references() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h2>8 | Uroflow Stop Test and Potency Recovery</h2>",
                    *[f"<p>Abstract prose line {idx}.</p>" for idx in range(1, 25)],
                    "<h4>References</h4>",
                    '<p id="ref-1">1. Alenizi AM, Bienz M, Rajih E, et al. Uroflow Stop Test after prostatectomy.</p>',
                    "<h2>9 | Another conference abstract</h2>",
                    "<h4>References</h4>",
                    '<p id="ref-1">1. AtД±lgan AE, Eren EГ‡. Mojibake local abstract reference.</p>',
                    "<h2>10 | Title-first abstract bibliography</h2>",
                    "<h4>References</h4>",
                    '<p id="ref-1">1. Quality of Life in Patients with Bladder Cancer Undergoing Ileal Conduit. '
                    "In Vivo. doi: 10.21873/invivo.11216 . PMID: 29275311.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P22" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_residual_unit_only_tex_fragments() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Charge density remained \\(\\mu\\) C cm<sup>-2</sup>.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P23" in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_tex_optional_numeric_argument_for_p07() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            '<html><body><p>The threshold equals <span class="z2m-math" role="math" '
            'data-z2m-tex="\\(\\sqrt[3]{V_n}\\)">3 V_n</span> in this model.</p></body></html>',
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P07" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_pdf_text_layer_end_section_order_hint() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h3>FUNDING</h3>",
                    "<p>This work was partially supported by the ministry.</p>",
                    "<h3>REFERENCES</h3>",
                    '<p id="ref-1"><span class="z2m-ref-num">1.</span> Example reference.</p>',
                    "<h3>SUPPLEMENTARY MATERIAL</h3>",
                    "<p>The Supplementary Material can be found online.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )
        pdf_text = (
            "FUNDING This work was partially supported by the ministry. "
            "SUPPLEMENTARY MATERIAL The Supplementary Material can be found online. "
            "REFERENCES 1. Example reference."
        )

        result = audit.analyze_pair(
            raw_path,
            polish_path,
            enable_pdf_diagnostics=True,
            pdf_text_override=pdf_text,
        )

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P24" in defect_ids
        assert result["summary"]["pdf_text_status"] == "override"
        assert result["summary"]["pdf_text_chars"] == len(pdf_text)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_uses_external_pdf_map_for_pdf_diagnostics() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    original_extract = audit._extract_pdf_text
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        external_pdf = tmp_path / "zotero" / "external.pdf"
        external_pdf.parent.mkdir(parents=True)
        external_pdf.write_bytes(b"%PDF-1.4\n")
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h3>FUNDING</h3>",
                    "<p>Support statement.</p>",
                    "<h3>REFERENCES</h3>",
                    '<p id="ref-1"><span class="z2m-ref-num">1.</span> Example reference.</p>',
                    "<h3>SUPPLEMENTARY MATERIAL</h3>",
                    "<p>The Supplementary Material can be found online.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )
        map_path = tmp_path / "pdf_map.json"
        map_path.write_text(
            json.dumps([{"article": "Article sample", "pdf_path": str(external_pdf)}]),
            encoding="utf-8",
        )
        pdf_text = "FUNDING Support statement. SUPPLEMENTARY MATERIAL online. REFERENCES 1. Example reference."

        def fake_extract(pdf_path: Path):
            assert pdf_path == external_pdf
            return "fake", pdf_text, None

        audit._extract_pdf_text = fake_extract

        result = audit.build_report(
            [tmp_path],
            enable_pdf_diagnostics=True,
            pdf_map=audit._load_pdf_map(map_path),
        )

        article = result["articles"][0]
        defect_ids = {defect["id"] for defect in article["defects_found"]}
        assert "P24" in defect_ids
        assert article["summary"]["source_pdf_path"] == str(external_pdf)
        assert article["summary"]["source_pdf_origin"] == "map"
        assert article["summary"]["source_pdf_present"] is True
        assert article["summary"]["pdf_text_status"] == "fake"
    finally:
        audit._extract_pdf_text = original_extract
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_refreshes_progress_json_while_auditing() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    original_analyze_pair = audit.analyze_pair
    try:
        root = tmp_path / "root"
        for article_name in ("Article one", "Article two"):
            stage_dir = root / article_name / "_z2m_stages"
            stage_dir.mkdir(parents=True)
            (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
            (stage_dir / "02.en.polish.html").write_text(
                "<html><body><p>Polished.</p></body></html>",
                encoding="utf-8",
            )

        progress_path = tmp_path / "audit.json"
        observed_progress: list[tuple[str, int, int]] = []

        def wrapped_analyze_pair(*args, **kwargs):
            if progress_path.exists():
                data = json.loads(progress_path.read_text(encoding="utf-8"))
                observed_progress.append(
                    (
                        data["audit_status"],
                        data["processed_pair_count"],
                        data["total_pair_count"],
                    )
                )
            return original_analyze_pair(*args, **kwargs)

        audit.analyze_pair = wrapped_analyze_pair

        report = audit.build_report([root], progress_out=progress_path, progress_write_every=1)
        saved = json.loads(progress_path.read_text(encoding="utf-8"))

        assert observed_progress == [("running", 1, 2)]
        assert report["audit_status"] == "complete"
        assert saved["audit_status"] == "complete"
        assert saved["processed_pair_count"] == 2
        assert saved["total_pair_count"] == 2
    finally:
        audit.analyze_pair = original_analyze_pair
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_parallel_jobs_match_serial_report() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        root = tmp_path / "root"
        for article_name, polish_html in (
            ("Article one", "<html><body><p>Polished.</p></body></html>"),
            ("Article two", "<html><body><p>Replacement \ufffd char.</p></body></html>"),
            ("Article three", "<html><body><p id=\"ref-1\">Reference.</p></body></html>"),
        ):
            stage_dir = root / article_name / "_z2m_stages"
            stage_dir.mkdir(parents=True)
            (stage_dir / "01.en.raw.html").write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
            (stage_dir / "02.en.polish.html").write_text(polish_html, encoding="utf-8")

        serial = audit.build_report([root], jobs=1)
        parallel = audit.build_report([root], jobs=2)

        serial["generated_at"] = ""
        parallel["generated_at"] = ""
        assert parallel["articles"] == serial["articles"]
        assert parallel["corpus_summary"] == serial["corpus_summary"]
        assert parallel == serial
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_load_pdf_map_accepts_zotero_candidate_records() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        map_path = tmp_path / "candidates.json"
        map_path.write_text(
            json.dumps(
                [
                    {
                        "article": "meine_0001_3944c69948",
                        "exact_matches": [],
                        "fuzzy_matches": [
                            {
                                "score": 10,
                                "path": str(tmp_path / "storage" / "paper.pdf"),
                            }
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )

        pdf_map = audit._load_pdf_map(map_path)

        assert pdf_map["meine_0001_3944c69948"] == tmp_path / "storage" / "paper.pdf"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_round25_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    *[f"<p>Body paragraph {i}.</p>" for i in range(45)],
                    '<p class="z2m-front-matter">Intrinsic metrics include BLEU, ROUGE, METEOR, CIDEr, '
                    "and Levenshtein distance for evaluation<sup>134-139</sup>.</p>",
                    "<p>Evaluation metrics remain unlinked<sup>134-139</sup>.</p>",
                    r"<p>Clinical applications remain limited \(^{71-73}\).</p>",
                    "<p>The paragraph ends with and</p>",
                    '<div id="fig-2" class="z2m-float-unit z2m-figure-unit"><p><img src="data:image/png;base64,AAAA"></p>'
                    "<p>Figure 2. Caption.</p></div>",
                    "<p>vary in diameter after the figure.</p>",
                    '<p class="z2m-figure-caption">Figure 8. Caption (created BioRender. Chamanzar. (2025)</p>',
                    '<h4 class="z2m-figure-caption">https://BioRender.com/8bfbsk2).</h4>',
                    '<p class="z2m-figure-caption">comparison shows normalized cell density.</p>',
                    "<p>Models optimize performance in a highly specific medical task. Sec.</p>",
                    "<p>A model is fine-tuned on outputs generated by flagship models 6,000.</p>",
                    "<p>The level reached Vwater and p = 0.04for the comparison; it was 20nCfor stimulation.</p>",
                    "<h4>References</h4>",
                    '<ul><li id="ref-1"><span class="z2m-ref-num">1.</span> [1] Duplicate prefix.</li>',
                    '<li id="ref-3"><span class="z2m-ref-num">3.</span> Gap after ref one.</li></ul>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert {"P25", "P26", "P27", "P28", "P30", "P31", "P32"}.issubset(defect_ids)
        assert "P06" in defect_ids
        assert "P04R" in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_counts_nested_bibliography_refs_before_reporting_id_gap() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<p block-type="Text" id="ref-1">1. First reference.</p>',
                    '<p block-type="ListGroup"><ul>',
                    '<li block-type="ListItem" id="ref-2"><span class="z2m-ref-num">2.</span> Second reference.</li>',
                    '<li block-type="ListItem" id="ref-3"><span class="z2m-ref-num">33.</span> Third reference.</li>',
                    "</ul></p>",
                    '<p block-type="Text" id="ref-4">4. Fourth reference.</p>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P26" not in defect_ids
        assert "P21" not in defect_ids
        assert "P22" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_embedded_numbered_references_inside_bibliography_item() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<ul><li id="ref-95"><span class="z2m-ref-num">95.</span> '
                    "Trautmann, E. M. et al. Neural dynamics. Neuron 103, 292-308 (2019). "
                    "96. Chen, X. et al. Customized implants. Journal of Neuroscience Methods 286, 38-55 (2017).</li>",
                    '<li id="ref-96"><span class="z2m-ref-num">96.</span> Highlights item.</li></ul>',
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p26 = [defect for defect in result["defects_found"] if defect["id"] == "P26"]
        assert p26
        assert p26[0]["check"] == "Bibliography item contains embedded numbered references"
        assert p26[0]["extra"]["embedded_number"] == 96
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_volume_number_as_embedded_reference() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    "<p>Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, "
                    "David Warde-Farley, Sherjil Ozair, Aaron Courville, and Yoshua Bengio. "
                    "Generative adversarial nets. In Z. Ghahramani, M. Welling, C. Cortes, "
                    "N. Lawrence, and K.Q. Weinberger (eds.), Advances in Neural Information "
                    "Processing Systems, volume 27. Curran Associates, Inc., 2014. "
                    "URL https://example.org/paper.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P26" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_next_abstract_section_as_embedded_reference() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    "<p>1. Alenizi AM, Bienz M, Rajih E, et al. "
                    "Uroflow Stop Test and Potency Recovery. Urology. 2015;86(4):766-771.</p>",
                    "<p>Results: Patients recruited in the study were 100. "
                    "Results according to PVR stratification are reported in Table 1. "
                    "There were no significant differences among the groups. "
                    "2. Martorana G., Sollini M.L., Fede Spicchiale C. "
                    "Neurogenic overactive bladder and voiding dysfunction in multiple sclerosis patients.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p26 = [
            defect
            for defect in result["defects_found"]
            if defect["id"] == "P26"
            and defect["check"] == "Bibliography item contains embedded numbered references"
        ]
        assert not p26
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_create_reference_gap_from_nested_refs_alone() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<p block-type="Text" id="ref-1">1. First reference.</p>',
                    '<p block-type="ListGroup"><ul>',
                    '<li block-type="ListItem" id="ref-3"><span class="z2m-ref-num">3.</span> Third reference.</li>',
                    "</ul></p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P26" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_joined_word_patterns_inside_url_slugs() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>Reference URL https://www.wsj.com/articles/a-hardwareupdate-for-the-human-brain-1496660400.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P67" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_flag_algorithm_voicecommands_as_joined_word() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>Algorithm input includes VoiceCommands, AIType, and a command stream.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P67" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_joined_word_patterns_in_prose_after_url_slug() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>URL https://www.wsj.com/articles/a-hardwareupdate-for-the-human-brain-1496660400.</p>"
            "<p>The withlower urinary tract phrase remains in prose.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p67 = [defect for defect in result["defects_found"] if defect["id"] == "P67"]
        assert p67
        assert p67[0]["extra"]["match"] == "withlower"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_meine_manual_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p>Patients (Box <a href="#page-2-0">1)</a>) and van der Kamp '
                    '<a href="#page-4-0">[1]</a>.</p>',
                    '<div id="box-1" class="z2m-float-unit z2m-box-unit"><h2>BOX 1</h2></div>',
                    "<h1>Indirect translation: examples inspired by optogenetic circuit analysis</h1>",
                    '<p>Human brain functio<a href="#ref-13" class="z2m-ref-link">n13 ,14</a> remains relevant.</p>',
                    '<p>Haptic graphs <a href="#ref-24" class="z2m-ref-link">[<a href="#ref-24" '
                    'class="z2m-ref-link">24</a></a>,<a href="#ref-25" class="z2m-ref-link">25</a>] '
                    "remain malformed.</p>",
                    "<p>License: https:// creativecommons.org/licenses/by/ 4.0/ and doi.org/ 10.1000/example.</p>",
                    "<p><sup>\ufffd</sup> : statistically significant</p>",
                    '<div id="fig-4" class="z2m-float-unit z2m-figure-unit">'
                    '<p><img src="data:image/png;base64,AAAA"></p></div>',
                    '<p><img src="data:image/png;base64,BBBB"></p>',
                    '<p class="z2m-figure-caption"><a href="#fig-4" class="z2m-fig-link">4.</a> '
                    "Post-RARP urinary continence recovery.</p>",
                    "<p>A decrease in PVR of over 50 mL led to decreased daytime</p>",
                    '<div id="table-2" class="z2m-float-unit z2m-table-unit"><p class="z2m-table-caption">'
                    "Table 2. Comparison.</p><table><tr><td>Value</td></tr></table></div>",
                    "<p>frequency, slow stream, and bladder pain.</p>",
                    "<p>https://doi.org/10.1371/journal.pone.0275069.t003 frequency, slow stream, and bladder pain.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert {"P33", "P34", "P35", "P36", "P37", "P38", "P39", "P40", "P41"}.issubset(defect_ids)
        assert result["summary"]["polish_page_links"] == 2
        assert result["summary"]["polish_replacement_chars"] == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_uses_pdf_text_layer_to_ignore_source_float_sentence_splits() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>There is only one location of the greatest derivative, negative or</p>",
                    '<div id="table-1" class="z2m-float-unit z2m-table-unit"><table><tr><td>Value</td></tr></table></div>',
                    "<p>positive, depending on the directions of the currents in the coil sections.</p>",
                    "<p>No tumors developed in either</p>",
                    '<div id="fig-7" class="z2m-float-unit z2m-figure-unit">'
                    '<p class="z2m-figure-caption">Figure 7. Tumors in a dish.</p></div>',
                    "<p>sham- or field-exposed animals.</p>",
                    "<p>This feature makes these coils negative or</p>",
                    '<div id="table-c67" class="z2m-float-unit z2m-table-unit">'
                    '<p class="z2m-table-caption">Table 1. Coil comparison.</p>'
                    "<table><tr><td>Value</td></tr></table></div>",
                    "<p>positive, depending on the directions of the currents in the coil sections.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )
        pdf_text = (
            "There is only one location of the greatest derivative, negative or "
            "Table 1. The maximum E and derivative at the nerve location for various coils "
            "positive, depending on the directions of the currents in the coil sections. "
            "N0 turnors devcloped in e1ther Figure 7. Tumors in a dish "
            "sham- or field-exposed animals. This ieafure makes these coils negative or "
            "Table 1. Noisy text layer material positive depending on current direction."
        )

        result = audit.analyze_pair(raw_path, polish_path, pdf_text_override=pdf_text)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P30" not in defect_ids
        assert "P40" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p39_across_intervening_prose() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<div id="fig-4-13" class="z2m-float-unit z2m-figure-unit">',
                    '<p class="z2m-figure-target"><img src="fig413-a.png"/></p>',
                    '<p class="z2m-figure-caption"><a href="#fig-4-13" class="z2m-fig-link">Рис. 4.13</a> '
                    "<b>Высококонтрастный сюжет</b></p>",
                    "</div>",
                    '<p><img src="fig413-b.png"/></p>',
                    '<p>На рис. 4.13 показан сюжет с широким диапазоном тонов.</p>',
                    '<p class="z2m-figure-caption"><a href="#fig-4-14" class="z2m-fig-link">Рис. 4.14</a> '
                    "<b>Следующий рисунок</b></p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P39" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_recent_meine_manual_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i} (20{i:02d}).</li>'
            for i in range(1, 12)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p class="z2m-front-matter">Lapo Governi <a href="#page-0-0">i1,</a> Rocco Furferi.</p>',
                    '<p>Shifted citation <a href="#ref-10" class="z2m-ref-link">,9</a> remains wrong.</p>',
                    '<p>See Eqn. <a href="#page-2-1">2.1)</a> for the minimization result.</p>',
                    "<p>Yakovle v (1967) and Nedele v (2019) are surname splits.</p>",
                    '<p>Qma<sup class="z2m-table-fn">x</sup> and Mast<sup class="z2m-table-fn">ix</sup> are split.</p>',
                    '<p id="table-4">TABLE 4. Formula summary.</p>',
                    '<div id="table-5" class="z2m-float-unit z2m-table-unit"><table><tr><td>Value</td></tr></table></div>',
                    '<p id="table-2">TABLE 2. Unwrapped body.</p><table><tr><td>Loose</td></tr></table>',
                    '<p>See Table <a href="#table-4" class="z2m-table-link">4</a> and Table 5.</p>',
                    "<p>Agarwal et al3 reported dysfunctional voiders.3 in this cohort.</p>",
                    '<p>We found <a href="#page-9-0">that formulas that use the total</a> bladder volume were useful.</p>',
                    "<p>doi: 10.1002/ nau.22813</p>",
                    "<p>AUSFUEHRLICHES HANDBUCH DER PHOTOGRAPHIE KOLLODIUMVERFAHREN DRITTE "
                    "AUFLAGE DRESDEN WISS PHOTOGR INSTITUT TECHNICHE SHULE WISSEN UND DER DIE DAS MIT.</p>",
                    '<p>Author-year mix <a href="#ref-11" class="z2m-ref-link">Bandettini, 1999</a> is wrong, '
                    "while Smith, 2020, Jones, 2019, Brown, 2018, and White, 2017 remain text.</p>",
                    '<p>Another citation <a href="#page-3-0">(Adam et al., 2001)</a> remains a page link.</p>',
                    '<div id="fig-1" class="z2m-float-unit z2m-figure-unit"><p><img src="data:image/png;base64,AAAA"></p>'
                    '<p id="fig-4">Figure 4. Wrong alias caption.</p></div>',
                    '<p>The comparison in (Figs. 3 and <a href="#ref-5" class="z2m-ref-link">5</a>) is malformed.</p>',
                    '<p>Source marker <sup><a href="#ref-1" class="z2m-ref-link">1</a></sup> should be a footnote.</p>',
                    '<p>The effect size was <a href="#ref-1" class="z2m-ref-link">1</a>,'
                    '<a href="#ref-5" class="z2m-ref-link">5</a> and allocation ratio was '
                    '<a href="#ref-3" class="z2m-ref-link">3</a>,<a href="#ref-1" class="z2m-ref-link">1</a>.</p>',
                    "<p>The absent semantic target is Figure 9A in the text.</p>",
                    '<p class="z2m-missing-figure-warning">Figure 1 image was not extracted into this HTML.</p>',
                    '<p><img src="data:image/png;base64,AAAA"/></p>',
                    "<p>Figure 2. Nearby different image caption.</p>",
                    '<p><a href="#page-1-0">[17,18].</a> remained a page citation.</p>',
                    "<p>Contact e-mail: simono v@neuro.nnov.ru remains split.</p>",
                    "<p>Here, we review relevant considerationsincluding the selection of methods.</p>",
                    "<p>Common OCR words include efect, eficacy, oficer and coeficient.</p>",
                    "<p>Currently available tools are neabling moderate illumination.</p>",
                    "<p>Another corrupted label is Me-mail: author@example.com and \u25a1Se-mail: author@example.com.</p>",
                    "<p>The method is timeconsuming and displaycan be useful; patients,were included; "
                    "prostatectomy\u0394VV appears.</p>",
                    "<p>For these " + ("intervening observations " * 12) + "</p>",
                    '<div class="z2m-float-unit z2m-figure-unit"><p>Figure 7. Inserted caption text.</p></div>',
                    "<p>reasons, a transdiagnostic repair is needed.</p>",
                    "<p>Runaway slow, slow, slow, slow, slow, slow, slow, slow appears in the paragraph.</p>",
                    "<p>Reference journal Neurosci. Biobeha v. Rev. remains split.</p>",
                    "<p>Known OCR forms include iournal.pone, Segmentaion, urflowmetry, urtheral, "
                    "systometry, inital, simpification, validtation, seperable, Wherev 2, Dmax=Dminw1:5, "
                    "pv0:05, 0:5mLs{, health male volunteer, will to help, effici\u00a8ency, "
                    "and 0.999 0995.</p>",
                    "<p>Positive value = increased symptoms, negative value = decreased symptoms studies "
                    "to evaluate pre- and post-operative LUTS.</p>",
                    "<p>Mukhriddin Mukhiddinov 100 and Soon-Young Kim retained author-marker glue.</p>",
                    "<h4>References</h4>",
                    "<ul>",
                    *refs,
                    "</ul>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {
            "P42",
            "P43",
            "P44",
            "P45",
            "P46",
            "P47",
            "P48",
            "P49",
            "P50",
            "P51",
            "P52",
            "P53",
            "P54",
            "P55",
            "P56",
            "P57",
            "P58",
            "P59",
            "P60",
            "P61",
            "P62B",
            "P63",
            "P64",
            "P65",
            "P66",
            "P67",
            "P68",
            "P69",
            "P70",
            "P71",
            "P72",
            "P73",
        }
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_pdf_verified_numeric_threshold_range_for_p73() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Between 0 and 100, the minimum perceptual threshold is 12. "
                    "Between 100 and 200, the minimum perceptual threshold is 24. "
                    "Between 200 and 255, the minimum perceptual threshold is 36.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P73" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p68_for_repaired_systemic_circulation_tail() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Delivery cannot completely prevent vector entry into the systemic circulation "
                    "(with some serotypes more likely to leak than others 124). "
                    "AAV DNA could also be detected in the systemic circulation.</p>",
                    '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">',
                    '<p class="z2m-figure-caption">Fig. 5 | Human immune responses. '
                    "Clinical experience has not revealed destruction of transduced target cells "
                    "behind the BBB.</p>",
                    "</div>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P68" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_006_010_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Leitthema Deutsche Leitlinien Diagnostik Prostatasyndroms "
                    "Zusammenfassung Urologe Klinik der die das mit und.</p>",
                    "<p>Latest updates: hps://dl.acm.org/doi/10.1145/2982142.2982176</p>",
                    "<p>" + ("\\@ifnextchar{\\@model{\\o}}" * 8) + "</p>",
                    "<p>DOI: http://dx.doi.org/10.1145/2982142.2982176 the plasticity "
                    "of the added height makes it easier to recognize by touch.</p>",
                    "<p>CamIO extended the concept to touchinteraction and realworld "
                    "testing with off-theshelf cameras and numbergestures.</p>",
                    "<p>Known OCR splits include APPEND ix, INTEL i LIGENT, qualitat iv, "
                    "Uroflowmetery, bootloding, Examing, Parametres, and Rewiev.</p>",
                    "<p>Names include Moritz Neum\u00a8uller and Bezi\u00b4er surfaces.</p>",
                    "<div>Table 3.1: curve features and thresholds. 3.8. Data Acquisition "
                    "records were stored. 3.9. Criteria for Use of Data removed invalid cases.</div>",
                    "<p>While touching the original ob je ct s w ould be best, safe ty c oncerns "
                    "can remain; we also incl ude expressi ve ness issues.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P53", "P67", "P71", "P74", "P75", "P76", "P77", "P78"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p77_when_table_closed_before_sections() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<div class="z2m-float-unit z2m-table-unit">',
                    "<p><b>Table 3.1:</b> curve features and thresholds.</p>",
                    "</div>",
                    "<h3>3.8. Data Acquisition</h3>",
                    "<p>Records were stored.</p>",
                    "<h3>3.9. Criteria for Use of Data</h3>",
                    "<p>Invalid cases were removed.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P77" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_011_015_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>1 Content from this work may be used under the terms of "
                    "theCreative Commons Attribution 3.0 licence.</p>",
                    "<div>Figure 6. Digital models: c) relief; d)2.5D model; "
                    "e) tactile bas-relief.</div>",
                    "<p>1Department of Industrial Engineering, University of Florence, "
                    "lapo.governi@unfi.it 2Department of Architecture, "
                    "luca.puggelli@unifi.it 5Department of Design.</p>",
                    "<p>The initial premicturtion volume and Qavg and Omax were calculated.</p>",
                    "<p>FRANCO ET AL. | 1915</p>",
                    "<div>TABLE 1. Female descriptive statistics. nales 5 ted Q a rates "
                    "vg avg ndexe s Ca ed Qm rates ax Qn Flow i \u0131ax ndexes "
                    "an \u00b1sp. P Values 0.06 0.00 4 .565</div>",
                    "<p>F = force, V = Vol ofmoved; see B Nusssenblatt for a copied name.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P67", "P71", "P79", "P80", "P81", "P82"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_016_020_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Despite the intensive investigation of</p>",
                    "<p>The purpose of this study is inserted before the continuation.</p>",
                    "<p>adults and older children with these techniques, little is known.</p>",
                    "<p>Our preliminary findings indicate that by using this novel sys- tem, "
                    "fMRI studies can continue.</p>",
                    "<p>Reference residue includes temprature and childrean.</p>",
                    "<p>& lt;sup>2 Living Paintings. & lt;sup>3 World Health Organization.</p>",
                    "<p>Before leaving the background section The use of non tactile methods "
                    "that communicate visual images in a non visual form are mentioned.</p>",
                    "<h2>ETHICS STATEMENT</h2>",
                    "<p>The studies were approved by Simon Jones, Department of Computer Science,</p>",
                    "<h2>REFERENCES</h2>",
                    "<p>Faul et al. Beha v. Res. Methods. Visual Perceptionof Progress. "
                    "Image Descriptionsfor Blind Users on a Social Network Service,\"in "
                    "Proceedings. This is an openaccess article.</p>",
                    "<p>University of Bath, United Kingdom. Participation was voluntary.</p>",
                    "<h2>AUTHOR CONTRIBUTIONS</h2>",
                    "<p>A cognitive iter, threedimensional reproductions, basrelief, and "
                    "realworld images remained.</p>",
                    "<p>I mplantable systems have ulimate goals and a Three-dimensioanl image "
                    "with fexible feld-efect transistors.</p>",
                    "<p>Additional opportunities include programmed pharmacological delivery and mul-</p>",
                    "<div>Fig. 4 | High-resolution/scalable neural electronic systems.</div>",
                    "<p>Review Article Nature Materials timodal sensing was resumed after the figure.</p>",
                    "<p>Email: jan. krhut@fno.cz. The UFrecorded value, SUFestimated parameters, "
                    "SUFdetermined flow pattern, and documents that that intensity phrase remained.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P66", "P67", "P70", "P71", "P83", "P84", "P85", "P86"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p66_ignores_rst_abbreviations_but_flags_mojibake_first() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>RST-001 and the RST group are valid abbreviations.</p>"
            "<p>The hemisphere stimulated \u00aerst was randomized.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p66 = [defect for defect in result["defects_found"] if defect["id"] == "P66"]
        assert [defect["extra"]["match"] for defect in p66] == ["\u00aerst"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_021_025_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>MRI is now recommended as the standard of care for term infants</p>",
                    "<p>Department of Radiology, Hills Road, Cambridge.</p>",
                    "<p>with hypoxic ischaemic encephalopathy and seizures.</p>",
                    "<p>Objects labelled NOT MRsafe and an MRcompatible incubator were noted.</p>",
                    "<p>References contain lung-tohead ratio, feed-andsleep technique, "
                    "readyreckoners, and injuryassociated cerebral findings.</p>",
                    "<p>Sedation and aesthesia protocols. J Magr Reson Imaging. "
                    "A 4 telsa MRI scanner was listed.</p>",
                    "<p>Available at www. osh a.europa.eu for occupational safety notes.</p>",
                    "<h2>EARLY DETECTION OF NEUROGENIC BLADDER DYSFUNCTION CAUSED BY PROTRUDED LUMBAH I - i</h2>",
                    "<p>The (!I G :. nosis was based on abnormal contraction. "
                    "A table had v&me, TVRP, pleak flow, timulus, and mesc.</p>",
                    "<p>Later OCR included foriTi 110 and stimulus.d/T./Sz, "
                    "elTicacy, and Unit: kcounl/mg prolan.</p>",
                    "<p>A meta-analysis residue kept Mata-Analysis, correla ition, "
                    "Retinal Nerve Fiber Laver, and an Amercian ophthalmological society thesis.</p>",
                    "<p>The reflex contracted the bulbocarnosus muscle.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P67", "P71", "P83", "P87", "P88"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p83_ignores_repaired_contiguous_phrases() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Despite the intensive investigation of adults and older children with these techniques, "
                    "little is known about children.</p>",
                    "<p>The collage of black icons on white background is printed on swell paper to form a "
                    "tactile rendering of the photograph.</p>",
                    "<p>MRI is now recommended as the standard of care for term infants with hypoxic "
                    "ischaemic encephalopathy.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P83" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p83_reports_license_tail_moved_into_competing_interest() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Competing interest: See page 14 of the Creative Commons "
                    "Attribution License, which permits unrestricted use.</p>",
                    "<p>Funding: See page 15 today deliver the high data rate.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P83" in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_026_030_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Contact: iskandar@ neurosurgery.wisc.edu.</p>",
                    "<p>The sensor, with qualify factor Q, had minimal step length form ADF4351 "
                    "and coupling factor deceases as the distance 1/R3.</p>",
                    "<p>Fa Wang received a degree from Fudan Univerisity and worked on MEME sensors.</p>",
                    "<p>P. Heppner, \u00b4 and D. Budgett. C\u00b8 . Varel, Syd \u00a8 anheimo, "
                    "and a wireless \u00a8 intraocular device were listed.</p>",
                    "<p>Conclusion says reliability remains insufficiently</p>",
                    "<p>Strengths and limitations text is inserted here.</p>",
                    "<p>researched. Low-to-moderate levels of evidence follow.</p>",
                    "<p>Transperineal ultrasound uroflowmetry with a radio frequency reflection measurement to evaluate BOO was</p>",
                    "<table>Large summary table interrupts this sentence.</table>",
                    "<p>compared with pressure flow studies, and demonstrated a high ROC-AUC.</p>",
                    "<p>See http://dx.doi.org/10.1136/ bmjopen-2021-056234 and http://journals . sagepub.com/doi.</p>",
                    "<p>Online supple mental table 1A-C is cited.</p>",
                    "<p>References include 20. 20 van Tulder and 33. 32 De Nunzio.</p>",
                    "<p>It isl part of this old scan. Purpose was to demonstrale the enor\u00b7 mous range. "
                    "The brochure says Llnhof Master Te&lt;:hnlka and Unhol Kafdan Mastel TL.</p>",
                    "<div>1 2 3 4 5 6 7 8 9 10 avg. sum 1. Did tl ne IAG he elp to bet ter "
                    "unde rstand th e paintir ng?</div>",
                    "<p>The allin-one prototype used singlefinger gestures for locationspecific content. "
                    "Computeraided design is referenced. Bulato v. remained split.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P67", "P71", "P76", "P78", "P82", "P83", "P87", "P88", "P89", "P90"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_031_035_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Functional Magnetic Resonance Imaging (fMR i) remained split in the contents.</p>",
                    "<table><tr><td>Additional projects: 3 1 mm female human brain cortex.</td></tr></table>",
                    "<p>You may also like Become a Multilingual by Means of Artwork in Information Technology "
                    "and a low-cost ChArUco-based 3D scanner for cultural heritage.</p>",
                    "<p>Francesco Buonamici, Luca Puggelli, Yary Volpe1.</p>",
                    "<p>The paintings were selected for the (B) 1. Flocked, raised-line outline drawings "
                    "included in the audio-tactile package. Four paintings were famous enough P to bc "
                    "familiar to visitors. E clarity of their design was duplicated.</p>",
                    "<p>Project partners included Mu&es de la Ville de Paris and Association Valentin Haiiy. "
                    "The Cruc$xion caption also had thev in body prose.</p>",
                    "<p>For example, parameter a' is Eq. (1) is a design parameter. The pupil was D_{eve} "
                    "and D'_{\\rm eve}. The grid had b5223 magnification, Dl5660620 nm, 2u560 degrees, "
                    "Dl50.4-0.78 m m, 9 m m, and focus F 1 8.</p>",
                    "<p>Mehmet Zeynel Keskin and Yusuf Ozlem Ilbey 1 1 2 3 1 1.</p>",
                    "<p>The MBVurgency, Qmaxnormal, and residualnormal values remained joined. "
                    "A possible indicator ofdepression was cited inIndian rural population and asmeasured "
                    "by IPSS. The symptomscore and withlower fragments, tractfunction, benignprostatic "
                    "hypertrophy, urineflow rates, AcceptableBladder Capacity, suggestiveof abnormal "
                    "uroflow pattern, distentionon voiding, healthyyoung men, and Theeffect of bladder "
                    "sensation remained.</p>",
                    "<p>Reference residue: flow flow flow flow and Liverposl nomograms with comparision.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P67", "P71", "P87", "P91", "P92"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_old_scan_ocr_gibberish_ignores_normal_rising_and_always() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Total compute has been rising exponentially for decades, "
            "and results are always checked against benchmarks.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P87" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_036_040_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>The selected machine was Object Eden260V for the rapid-prototyping sample.</p>",
                    "<p>Figure 17a Nineteenthcentury CC-mounted print. The mattecollodion paper had "
                    "darkbrown tonality and 20th- and 21 st-century substrates.</p>",
                    "<table>Collodion Prints S Process Surface Coating Paper Fibers Ag Au Other "
                    "Inorganics Surface/Tonality Wothlytype 8 x x Sr.I.</table>",
                    "<p>Symptoms may not be specifi c, and testing identifi es diffi culty with fl ow. "
                    "Urofl owmetry is defi ned by fl uid rate, profi le, fi lling, refl ux, and "
                    "signifi cant confi dence limits.</p>",
                    "<p>There is obvious urinary leakage with</p>",
                    "<p>From Blaivas JG, Olsson CA: Stress incontinence source text.</p>",
                    "<p>minimal increases in intravesical pressure.</p>",
                    "<p>Caption residue had electromyograhic tracing, an involunatary contraction, "
                    "clincal grading, and symphisis pubis.</p>",
                    "<p>Jin et al. Combined Imaging in Breast Cancer split a paragraph. "
                    "Alrabadi et al. 3 stayed as a page header.</p>",
                    "<p>& lt;sup>a Body mass index. & lt;sup>d Sentinel lymph node biopsy.</p>",
                    "<p>The nearinfrared tracer used a selfcontrolled protocol with 99Tcmcolloids and "
                    "nonneoadjuvant chemotherapy. American Society of Clinical Ncology and Florescence "
                    "Technique remained in references. Values included 5.22 \\pm 2, 38.</p>",
                    "<p>Lujain Al Omari1 was listed as an author. The TQma x column, Voiding positing, "
                    "and significate statistical differences remained visible.</p>",
                    "<p>References included Medical management 3. of benign prostatic hyperplasia, "
                    "findings and 17. postvoiding residual urine, and post-void residual 20. urine volume.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P66", "P67", "P71", "P81", "P82", "P84", "P90", "P92"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_041_045_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>An Over 5 Ho 6 Chapter One _ aries 8 noving Adhesive Tape "
                    "Restorin g a Camera Stand24 Pac kard Ideal Shutter.</p>",
                    "<p>Cleaning the Autographic Kodak Camera 1915-192640 Kodak No. 3 l A "
                    "Folding Brownie48 Chapter S ix Index HIMPY.</p>",
                    "<p>Contact: jakub.i.krukowski@gmail. com and see www.yumpu . com/en/document.</p>",
                    "<p>High intraand interobserver reproducibility used a lightbeam method. "
                    "The Videobased device was handassembled, and OpticalTouch remained joined.</p>",
                    "<p>A Comprehensive Review 4. Emphasizing Anatomy stayed in references. "
                    "Urethral Stricture Recurrence 21. After Anterior Urethroplasty also stayed. "
                    "Challenges and Opportunities, Jeddah 28. Khorsheed was shifted.</p>",
                    "<p>During LUTS workup, malignancy or traumatic lesions. A present-address block "
                    "John G. Webster john.webster@wisc.edu major and essential step was inserted.</p>",
                    "<p>Many visual computing algorithms turn permission metadata and ACM copyright "
                    "into the middle of the paragraph out to be equally well suited for tactile media.</p>",
                    "<p>5:2 xx A. Reichinger et al. page header survived in body text.</p>",
                    "<p>Known OCR residues included Schfer, Standarisation, subcomitee, standarization, "
                    "aformentioned, Cvalli, Routeledge, PdetQma x, BOO i, IPP Grade iii, "
                    "simulates the The validation, to be The topological sort, and DirectX- R.</p>",
                    "<p>Detached accents remained as BRICENO~ , H. M. and HOLLERER ~ , T.</p>",
                    "<p>S.V. Krishna Reddy pa and Ahammad Basha Shaik pb a Department of Urology.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P67", "P71", "P76", "P81", "P82", "P83", "P86", "P88", "P90", "P92"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_bibliography_numbers_at_clean_li_boundaries() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    "<ul>",
                    '<li id="ref-27"><span class="z2m-ref-num">27.</span> Bokhari, A. '
                    "Paper presented at the The Saudi Economy Conference: Challenges and Opportunities, Jeddah</li>",
                    '<li id="ref-28"><span class="z2m-ref-num">28.</span> Khorsheed, M. S. '
                    "Fostering university-industry collaboration.</li>",
                    '<li id="ref-281"><span class="z2m-ref-num">281.</span> Zhang, H. '
                    "Traveling theta waves in the human hippocampus.</li>",
                    '<li id="ref-282"><span class="z2m-ref-num">282.</span> Buzsaki, G. '
                    "Brain rhythms have come of age.</li>",
                    "</ul>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P90" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_046_050_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p>Over the years, numerous papers by Alice Brown and Michael Green investigated '
                    'museum technologies [<a href="#ref-80" class="z2m-ref-link">80</a>] and '
                    'gallery visitor practice [<a href="#ref-103" class="z2m-ref-link">103</a>].</p>',
                    "<p>See http://pediatrics.aappublications.org/content/113/2/e150.full.h tml "
                    "for the split URL ending.</p>",
                    "<p>The old city was airpolluted, the diet was vitamin-Ddeficient, and the "
                    "watersoluble asprepared CDs were described as ecofriendly.</p>",
                    "<p>Database table tokens included MDP i and ISTOR; another method used "
                    "14 C-beled vitamin D and a Shepadex column.</p>",
                    "<p>The urodynamics paper cited Pogoreli\u00b4c and Huski\u00b4c with detached accents. "
                    "However, t o the best of our knowledge this should be one word.</p>",
                    "<p>Resonance-Compatible Incubator With a Built-in Coil Ultrafast Magnetic "
                    "Resonance Imaging of the Neonate in a Magnetic appeared as a running header.</p>",
                    "<p>Journal of Materials Chemistry B Accepted Manuscrip was followed by RSC line "
                    "numbers: residues with 20 the sizes below 10 nm and been 25 reported.</p>",
                    "<p>surrounding environment needs to be controlled care- From the Section of "
                    "Academic Radiology metadata fully, because they cannot maintain homeostasis.</p>",
                    "<p>enclusive app output was followed by table damage near Cavalier i et al.</p>",
                    "<p>References had Proceedings of the 2023 ACM 31. International Conference and "
                    "25 5 H. Li as shifted numbering.</p>",
                    "<p>Mingyue Xue, ab Mengbing Zou, Jingjin Zhao, Zhihua Zhan Ab and Shulin Zhao "
                    "Zhao A green approach was developed.</p>",
                    "<p>Ote this: DO: 10.1039/c0xx00000x ARTI CLE TYPE attempeted to detecte MB afrer "
                    "5 minutes with speices responsed selectively.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P67", "P71", "P76", "P78", "P81", "P82", "P83", "P90", "P92", "P93"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
        assert "P03" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_051_055_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>The front matter ended with http://dx.doi.org/10.1016/j.gmod.2013.10.001 "
                    "lines as a basis for further work.</p>",
                    "<p>Broken links included https://www.iceaaonline.com/wp "
                    "content/uploads/2015/06/report.pdf and "
                    "https://babel.hathitrust.org/cgi/pt? id=mdp.39015006370568.</p>",
                    "<p>The basreliefs method had frontto-back traversal, signalto-noise measures, "
                    "farred spectra, timedependent acquisition, first-inhumans studies, and a "
                    "backilluminated detector.</p>",
                    "<p>A patent described anatomicallycompatible, convectionenhanced, "
                    "neurologicallyrelated, valvegated, and mindenhancing parts.</p>",
                    "<p>The book title was Learning R ates andChallenges, with a SoftBankbacked "
                    "company in the note.</p>",
                    "<p>OCR residues included Abstrac t, List of F igures, Acknow rledgements, "
                    "Chapte r, Append i ces, Apper ndi x, Bibliogra phy, [p, pj]of, left)999, "
                    "fotograf ii, London1843, co verage, approximatley, chronologicall y, "
                    "Archtecture, Woodsawer, Vacla v, Date o of mailing, Autho Authorized, "
                    "patent family anne x, hiah camera, In some [880] embodiments, Marvland, "
                    "and OceanofPDF.com.</p>",
                    "<p>Although qualified, in the absence of aSignificant, p &lt; 0.05. standards, "
                    "it remains impractical.</p>",
                    "<p>The application discloses magnetic resonance imaging (MRI) [071] This "
                    "compatible cranial implant device.</p>",
                    "<p>The bibliography line was 16. 16Novadaq Technologies Inc.</p>",
                    "<p>Articles you may be interested in Magnetic resonance-guided near-infrared "
                    "tomography of the breast.</p>",
                    "<p>Eva M. Sevick-Murac aa) Department of Molecular Imaging.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P67", "P71", "P72", "P75", "P90", "P91", "P92"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_056_060_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p>Reference text showed <a href="http://www.annualreviews.org">'
                    "http:// www.annualreviews.org</a> and www.operativeneuro surgery-online.com.</p>",
                    "<p>Common ligature losses included specifc identifed fow fxed artifcial "
                    "refect ofline aferents artiicial scientiic certiication deining "
                    "eectiveness ailiations irst inluence itness worklow.</p>",
                    "<p>Joined words included singleneuron crossfrequency inhibitionbased "
                    "phaselocked Alessentially medicineresistant customdesigned hardwareupdate "
                    "Competinginterests Additionalinformation andrequests andpermissions "
                    "ofrealistic ofmedical ofclinical ofperspective offactual of13.</p>",
                    "<p>Old scan OCR left Avoiraupois, appro ximately, weigh ght, bH scale, "
                    "F 011 07, .oog-inch, Avo i irdupois, Chroming and Auditor Spring Inc., "
                    "ERTAINTY, pathologica, essenetial, USMLE:pPotential, GAL such as, "
                    "Constitutional Al, Al techniques, euromodulation devices, crania l implant, "
                    "and Bultimore.</p>",
                    "<p>The comment preserved B rain-computer as spaced OCR residue.</p>",
                    "<p>Nature page chrome said Check for updates in the body.</p>",
                    "<p>Hydrometer g 4 &#205; &#247; column tokens scattered across the table "
                    "until the Hydrometer only note.</p>",
                    "<p>They organize sequential neuronal events as well as The temporal "
                    "characteristics of brain oscillations were inserted here.</p>",
                    "<p>The references read neuroimaging 76. Mondok and RNS System in Epilepsy "
                    "Study GroupMorrell MJ.</p>",
                    "<p>Zhen Ling Teo &copy; 1,2,15 and Robert J. T. Morris &copy; 11 were in "
                    "the author line.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P66", "P67", "P71", "P78", "P81", "P82", "P83", "P88", "P90", "P92"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_061_065_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Front matter used https://doi.org/10.1145/3623509.3633377 or "
                    "alternative text. Current methods continued the abstract.</p>",
                    "<p>Footnotes merged with body: using-artificial-intelligence-to-help-blind-people-see-facebook "
                    "A novel system and ClearVision project: www.clearvisionproject.org In summary.</p>",
                    "<p>Repository chrome: FLORE Repository istituzionale dell'Universita degli Studi di Firenze "
                    "with metadata, policy text, and Article begins on next page.</p>",
                    "<p>Reference URL merge: http://bit.ly/art-brera 6www.ada.gov/lodblind.htm.</p>",
                    "<p>Lost ligatures included frst fne fgurative defned profcient beneft "
                    "difculty difculties staf eforts confrm confrming clarifed infuenced "
                    "fndings feld.</p>",
                    "<p>Joined terms included KeunWhangbo easy-tolearn Shapefrom-shading "
                    "Attributebased thistask higherthan disabilitiessometimesface artworksis "
                    "hierarchicalsegmentation webbased needsto includesinformation "
                    "participantssuggested overallwork guidelinesfor issimilarto easierto "
                    "spatialcognitive wassupported blindaccessible Key-wordaware.</p>",
                    "<p>OCR tokens included Stoimeno v., list all the they identified, "
                    "OPRATING PRICIPLE, discription, milivolt, upto, coma separated, "
                    "purposed work, millitres, ghraph, Authers, et nl., Electronic(Cambridge, "
                    "If inal, Hands of!, best suites, and Computer Based Method ?.</p>",
                    "<p>Detached accents stayed in Pakenait &#729; e&#729;, fac&#184;ade, "
                    "Spath &#168;, The challenge would &#180; be, and SEQUIN &#180; , C.</p>",
                    "<p>The name Bel humeur was split by OCR spacing.</p>",
                    "<p>References shifted: Suggestive contours for conveying shape. 5. ACM "
                    "Transactions, and TouchPen details incorrectly continued as 13. Cham.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P66", "P67", "P71", "P75", "P76", "P78", "P83", "P90", "P91"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p66_ignores_defne_reference_name() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h4>References</h4>",
                    '<ol><li id="ref-142"><span class="z2m-ref-num">142.</span> '
                    "Defne Circi, Ghazal Khalighinejad, and Anlan Chen. "
                    "How well do large language models understand tables?</li></ol>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P66" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_066_070_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>ChemComm Accepted Manuscript. Published on 03 August 2015. "
                    "Downloaded by Emory University on 04/08/2015 04:19:33.</p>",
                    "<p>The article had excellent 10 contrast, minimal 15 autofluorescence, "
                    "20 photobleaching thresholds, 25 development of nanoprobes, 30 dyes, "
                    "35 resulting fluorescence, 45 developed as a nanoprobe, 60 illustrated "
                    "in Figure 1, 75 fabricated samples, 85 nanomicelles, and 100 As shown "
                    "in Figure 4A.</p>",
                    "<p>OCR tokens included Stocks shift, CTABassistant, nanomicells, a plent "
                    "of serum, ODs/MB nanomicelles, toxity, uroflometer, 31.6 8 C, 35.9 8 C, "
                    "368C, 378C, 425 cmH2O, and 460 bpm.</p>",
                    "<p>Lost ligatures included magnetic eld, eld strength, ve patients, rst "
                    "few days, suf cient, insuf cient, bene ts, ndings, and Of ce.</p>",
                    "<p>Spaced OCR residues included Groenenda al@wkz.azu.nl, Wilhel mina, "
                    "RUTHERFO RD, environ ment, Inter national, disconti nuation, and Ita ly.</p>",
                    "<p>Footnotes interrupted prose: small animals imaging In summary, by doping "
                    "the QDs/MB pair. Urinary flow can also be recorded by voiding on a disk "
                    "13 Cardus, D.: Studies on the dynamics of the bladder. which rotates at "
                    "a constant speed.</p>",
                    "<p>More reference/body mixing: who measured the maximum flow by 18 Holm, "
                    "H. H.: A uroflowmeter and a method for combined pressure and flow measurement "
                    "recording the volume of air displaced by urine.</p>",
                    "<p>Four of these principles were tested for accuracy * UF2 Physico-Medical "
                    "Systems Corporation, Montreal constant flow response was measured.</p>",
                    "<p>References shifted as 7. 50 7 P. Greenspan, 11. 55 10 X. He, "
                    "1468. 1469. 20 L. Wang, 1470. 75 21 X. Chen, and 1476. We. Liu.</p>",
                    "<p>92 Y. Volpe et al. and 106 Y. Volpe et al. remained as page headers.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P66", "P67", "P71", "P78", "P81", "P83", "P90", "P93"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_071_075_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Reference URL path split: https://www.museodelprado.es/touching- the-prado "
                    "in the bibliography.</p>",
                    "<p>Lost ligatures stayed as urine ow rates and white ght in the old scan.</p>",
                    "<p>Joined residues included FromFebruary, Qmaxurgency, image processingbased, "
                    "extrusionsurgically, inflammationat, of theonly, NeururolUrodyn2021, "
                    "such asportraits, and iodineattacks.</p>",
                    "<p>OCR tokens included Deptartment, fascade, basrelif, Mulitmodal, agumentation, "
                    "Archelological, Museum of Moden Art, Deparment, Polywoks, PRAVALENCE, "
                    "pvalue &lt; 0.05, IPelvic, hispareunia, main: 12, characteriscs, obeserved, "
                    "stuies, miduretrhal, incotinence, resultes, intrauethral, oncontinence, "
                    "Urologiy, OUALITY, QLO C30, istopaholohical, Continues variables, "
                    "postvoding, Thirtyeight, electronical, oraotten, PATRATS, STLAR, throughour, "
                    "This ing with Fig. 1, elipse, couse-quence, Dipping Robs, daguerrectype, "
                    "sclution, iedide, Cutring, proccss, Negavives, precipated, and cunce.</p>",
                    "<p>Spaced OCR residues included Leporin i, enj oy, sepa ration, at tached, "
                    "free fr om ye elk, and eve ly.</p>",
                    "<p>Affiliation glue remained as InstituteDepartment of Urology.</p>",
                    "<p>15206777, 2021, S3, Downloaded from "
                    "https://onlinelibrary.wiley.com/doi/10.1002/nau.24751 by Egyptian National "
                    "Sti. Network (Enstinet). RETURN CIRCULATION DEPARTMENT.</p>",
                    "<p>Questionnaire table OCR: MS MPTO SY columns and responses collapsed before "
                    "W TO GET IT HO. Hyposulp Water phite of of soc la also remained.</p>",
                    "<p>Patients with a history of lower urinary system surgery, neurological problems, "
                    "lower urinary tract tumor, and active urinary infections were ex- Main Points: "
                    "Uroflowmetry is an essential test for evaluating patients with LUTS. cluded, "
                    "and a total of 83 patients were included.</p>",
                    "<p>www.forgottenbooks.com THIS PAGE IS LOCKED TO FREE MEMBERS. Purchase full "
                    "membership to immediately unlock this page. Over 2,000 years of human knowledge.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P66", "P67", "P71", "P78", "P79", "P81", "P82", "P83", "P91"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_splits_intra_word_spacing_by_html_mechanism() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>COMMENT <b>B</b> rain-computer remained in body text.</p>",
                    '<table><tr><td>Leporin<sup class="z2m-table-fn">i</sup> et al.</td></tr></table>',
                    "<p>A plain OCR residue in a different mechanism stayed as Ita ly.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
        assert {"P78", "P94", "P95"}.issubset(defects_by_id)
        assert defects_by_id["P78"]["extra"]["match"] == "Ita ly"
        assert defects_by_id["P94"]["extra"]["match"] == "B rain-computer"
        assert defects_by_id["P95"]["extra"]["match"] == "Leporin i"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_076_080_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p>Code is available at <a href="https://tinyurl.com/ys7psv5u">'
                    "https://tinyurl.com/ ys7psv5u</a>.</p>",
                    "<p>Lost ligatures stayed as Urofowmetry, bladder flling, fuid, "
                    "fuorescent display, specifcity, signifcant, modifcation, and cutof.</p>",
                    "<p>Joined residues included pushpull, twoobject, held inWM, itemspecific, "
                    "controlrelated, lowdimensional, topdown, contextdependent, finergrained, "
                    "cuetrials, trialaverage, match-tosample, spatiovectors, Qcould, Qto, "
                    "IPPgrades, metaanalysis, and BPHassociated.</p>",
                    "<p>A reference retained Curr. Opin. Beha v. Sci. 38, 20-28.</p>",
                    "<p>OCR tokens included passive senor, Urdynamic tests, urinary track, "
                    "International continent society, non-invasivly, home urofowmetry, Refrence, "
                    "FERENCE VALUES, Qrnax, TQrnax, TlOO, Q2sea, classifified, Neurocsi, "
                    "Hip-pocampus, IPSS 0 = 10 symptoms, DWT values -2 mm, and grade 1¼0.</p>",
                    "<p>T a bl e 2 1 con t' old scan nue d. HE?LTHY SUBJECT 11 ME?SUREMENT 32 SER.</p>",
                    "<p>Spatial computing predicts that control-related spiking and LFP activity "
                    "is spatially distributed. The green (sample 1) and light blue rectangles mark "
                    "when the samples were shown.</p>",
                    "<p>Old scan residues included Uroflowrnetry, uroflowrneter, RotCDTleter, "
                    "PsyahoZogiaaZ, Gra1Jimetry, OVerfLow, prinaip Ze, ResiduaZ, bZood, "
                    "MuZtiphasicity, estabZishment, variabZes, abiZities, measzu'ing, fww-cion, "
                    "contin,Ious, A!Jstract, vuiation, measwe, and Druck/Fiow.</p>",
                    "<p>University of Groningen repository cover. IMPORTANT NOTE: consult the "
                    "publisher version. Downloaded from the University of Groningen/UMCG research "
                    "database.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P36", "P66", "P67", "P70", "P71", "P82", "P87", "P91"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_fulltext_batch_081_082_blind_spots() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>II. BEHAVIORALAND NEUROLOGICAL RELATIONS OF MAP USE WITH EMPHASIS "
                    "ON TACTILE MAP. III. TYPES OFTACTILE MAPS and EVERYDAYACTIVITIES. "
                    "The choice of rougher texture.Tactile cartography follows.</p>",
                    "<p>Manuscript received on April 17, 2021. Revised Manuscript received "
                    "on April 15, 2021. Manuscript published on April 30, 2021.</p>",
                    "<p>* Correspondence Author participants were asked to complete a test "
                    "that included different types of graphics.</p>",
                    "<p>OCR residues include beacause, \u03a4he touch map, \u0399mproving, "
                    "threfore, eBDetheque, an notate, form eBDtheque, and compliment of "
                    "the text-area mask.</p>",
                    "<p>Deblina Bhattacharjee, Martin Everaert, Mathieu Salzmann, "
                    "Sabine Susstrunk \u00a8 School of Computer and Communication Sciences.</p>",
                    "<p>The comics article still has featurebased GAN, upprojection method, "
                    "groundtruth images, shiftinvariant loss, imagedepth pairs, "
                    "intraobject depth values, state-oftheart I2I method, domaininvariant "
                    "content space, textdetection module, speechballoon areas, textbased "
                    "artifacts, contentaware resizing, leftright consistency, "
                    "Semisupervised learning, imageto-image translation, and realdomain "
                    "images.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        expected = {"P67", "P71", "P76", "P81", "P83"}
        assert expected.issubset(defect_ids), sorted(expected - defect_ids)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_flag_title_case_tooteko_as_ocr_token() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The Tooteko project provides tactile 3D models for museum "
            "visitors.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P71" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_flag_irit_elipse_lab_as_ocr_token() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The IRIT-ELIPSE group evaluated tactile models.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P71" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_country_period_before_email_for_p86() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Instrumentation and Control, Pune, Maharashtra, India. "
            "aratipravin03@gmail.com</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P86" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_sentence_period_before_email_for_p86() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Correspondence should be addressed. jamesbarresemd@gmail.com. "
            "Please contact the corresponding author. cfeng@nyu.edu.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P86" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_true_split_dot_emails_for_p86() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>Email: jan. krhut@fno.cz. "
            "Reach margaret.tarampi@psych .utah.edu.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p86 = [defect for defect in result["defects_found"] if defect["id"] == "P86"]
        assert p86
        assert p86[0]["extra"]["match"] in {"jan. krhut@fno.cz", "margaret.tarampi@psych .utah.edu"}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_hyper_parameter_phase_and_spaced_year_false_positives() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i}.</li>'
            for i in range(1, 35)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p>The default hyper-parameters of [<a href="#ref-20" class="z2m-ref-link">20</a>] '
                    "were used. During the training phase, the loss was stable.</p>",
                    "<p>American Journal of Photography v. 13, no. 151, is a volume label.</p>",
                    "<p>Table 2 1. measured quantity author(s) year of publ. Kondo et al . 1 978 + Drake.</p>",
                    "<h4>References</h4>",
                    "<ul>",
                    *refs,
                    "</ul>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
        assert "P45" not in defect_ids
        assert "P50" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_flattened_citation_shapes_inside_table_captions() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i}.</li>'
            for i in range(1, 18)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<div id="table-1" class="z2m-float-unit z2m-table-unit">',
                    '<p class="z2m-table-caption">TABLE 1. Ding et al. 15 / Palmom et al. 16.</p>',
                    "</div>",
                    "<p>Ordinary body text has no flattened citation.</p>",
                    "<h4>References</h4><ul>",
                    *refs,
                    "</ul></body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P50" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_flattened_citation_shapes_inside_table_like_text() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i}.</li>'
            for i in range(1, 45)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Real-time Object detection Algorithm category Region "
                    "Guo et al40 Li et al36 Li et al39 Time efficiency ROC curve "
                    "Precision recall F-measure Algorithm score.</p>",
                    "<h4>References</h4><ul>",
                    *refs,
                    "</ul></body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P50" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_flattened_citation_shapes_inside_math_contexts() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i}.</li>'
            for i in range(1, 18)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>The current spread equation uses I = 1 + K * (rad - rad_e)2 I_input "
                    "where surface.14 is a rendered OCR artifact, not a citation.</p>",
                    "<h4>References</h4><ul>",
                    *refs,
                    "</ul></body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P50" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_classifies_joined_infig_as_joined_word_not_p50() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i}.</li>'
            for i in range(1, 4)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<p>Theexperiment tookplaceinasquare area and was reproduced inFig.1.</p>",
                    "<h4>References</h4><ul>",
                    *refs,
                    "</ul></body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P50" not in defect_ids
        assert "P67" in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_flattened_shapes_inside_split_doi_url() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i}.</li>'
            for i in range(1, 12)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p>Reference DOI <a href="https://doi.org/10.1146/annure">'
                    "https://doi.org/10.1146/annure</a> v.bioeng.10.061807.160529.</p>",
                    "<h4>References</h4><ul>",
                    *refs,
                    "</ul></body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P50" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_hyphenated_d_labels_before_citations() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [
            f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Author {i}.</li>'
            for i in range(1, 35)
        ]
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    '<p>Nanobodies Ty1 <a href="#ref-33" class="z2m-ref-link">33</a>, '
                    'H11-D4 <a href="#ref-34" class="z2m-ref-link">34</a>, and '
                    'Nb21 <a href="#ref-35" class="z2m-ref-link">35</a> were modified.</p>',
                    "<h4>References</h4><ul>",
                    *refs,
                    "</ul></body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P05" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_numbered_section_heading_after_references_block() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    "<h1>References</h1>",
                    "<ul>",
                    '<li id="ref-1"><span class="z2m-ref-num">1.</span> First reference.</li>',
                    '<li id="ref-2"><span class="z2m-ref-num">2.</span> Second reference.</li>',
                    "</ul>",
                    '<p>- Section <a href="#section-1" class="z2m-section-link">1</a>: Text-detection Module</p>',
                    '<h3 id="section-1">1. Text-detection Module</h3>',
                    "<p>Supplementary body text continues here.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P22" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p59_for_numeric_citation_dominant_article() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "numeric sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Ref {i}.</li>' for i in range(1, 8)]
        body = "".join(
            f'<p>Method text mentions Smith, 20{i:02d}, but numeric evidence'
            f'<sup><a href="#ref-{i}" class="z2m-ref-link">{i}</a></sup> remains valid.</p>'
            for i in range(1, 7)
        )
        polish_path.write_text(
            f"<html><body>{body}<h4>References</h4><ul>{''.join(refs)}</ul></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P59" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p59_for_sparse_sup_numeric_article() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "sparse numeric sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Ref {i}.</li>' for i in range(1, 22)]
        sup_body = (
            '<p>Smith, 2000 and Jones, 2001 make the document look author-year. '
            'Brown, 2002 and White, 2003 add more author-year evidence. '
            'Vagus nerve stimulation<sup><a href="#ref-2" class="z2m-ref-link">2</a></sup> '
            'and responsive neurostimulation (RNS)<sup><a href="#ref-3" class="z2m-ref-link">3</a>,'
            '<a href="#ref-4" class="z2m-ref-link">4</a></sup> are discussed. '
            'The pivotal trial<sup><a href="#ref-5" class="z2m-ref-link">5</a></sup> is cited too.</p>'
        )
        plain_links = "".join(
            f'<p>Additional numeric citation evidence <a href="#ref-{i}" class="z2m-ref-link">{i}</a>.</p>'
            for i in range(6, 17)
        )
        polish_path.write_text(
            f"<html><body>{sup_body}{plain_links}<h4>References</h4><ul>{''.join(refs)}</ul></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P59" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p60_for_bracketed_citation_lists() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "numeric citation list" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Ref {i}.</li>' for i in range(1, 40)]
        polish_path.write_text(
            "<html><body>"
            '<p>"Small sample size" is frequently cited as a limitation '
            '[<a href="#ref-21" class="z2m-ref-link">21</a>, '
            '<a href="#ref-33" class="z2m-ref-link">33</a>, '
            '<a href="#ref-37" class="z2m-ref-link">37</a>].</p>'
            '<p>A sample size estimate was justified by prior work '
            '[<a href="#ref-22" class="z2m-ref-link">22</a>].</p>'
            '<p>Effect sizes and attrition rates were similar to those observed in the pilot study.'
            '<sup><a href="#ref-21" class="z2m-ref-link">21</a></sup></p>'
            '<p>Our sample size is comparable to previous studies testing the same tasks '
            '<a href="#ref-31" class="z2m-ref-link">31</a>,'
            '<a href="#ref-32" class="z2m-ref-link">32</a>.</p>'
            '<p>Adapted from van Tulder et al, '
            '<a href="#ref-20" class="z2m-ref-link">20</a> in line with criteria.</p>'
            '<p>The adult males group was discussed in '
            '[<a href="#ref-11" class="z2m-ref-link">11</a>-'
            '<a href="#ref-15" class="z2m-ref-link">15</a>].</p>'
            f"<h4>References</h4><ul>{''.join(refs)}</ul></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P60" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_p60_for_sample_size_value_links() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "sample size value link" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = [f'<li id="ref-{i}"><span class="z2m-ref-num">{i}.</span> Ref {i}.</li>' for i in range(1, 40)]
        polish_path.write_text(
            "<html><body>"
            '<p>The final sample size of the early-blind group was '
            '<sup><a href="#ref-11" class="z2m-ref-link">11</a></sup>.</p>'
            '<p>Sample size was <sup><a href="#ref-32" class="z2m-ref-link">32</a></sup> to 63.</p>'
            f"<h4>References</h4><ul>{''.join(refs)}</ul></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defects = [defect for defect in result["defects_found"] if defect["id"] == "P60"]
        assert defects
        assert defects[0]["extra"]["num"] in {"11", "32"}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p60_for_plain_group_near_citation() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "plain group citation" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        refs = ['<li id="ref-25"><span class="z2m-ref-num">25.</span> Ref.</li>']
        polish_path.write_text(
            "<html><body>"
            '<p>The Kodicek group and a group of buildings were mentioned before '
            '<sup><a href="#ref-25" class="z2m-ref-link">25</a></sup>.</p>'
            f"<h4>References</h4><ul>{''.join(refs)}</ul></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P60" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p45_for_formula_subscripts() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "formula sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>A stable phase of ZrAl<sub>x</sub>O<sub>y</sub> forms at the interface.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P45" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p45_for_x_ray_or_version_abbreviation() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "roman false positive sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>While x-ray-based approaches remain useful, they are not widespread.</p>"
            "<p>Statistical Package for the Social Sciences v.22 was used.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P45" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_does_not_report_p45_for_formula_like_roman_tokens() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "roman formula sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>Where x j belongs to dataset X, Node x i represents a camera pose.</p>"
            "<p>Coordinates i, Mean i, Type i, and Numbered x are table variables.</p>"
            "<p>Assuming v is velocity, Reference v is an electrode, and Mimics v.22 was used.</p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P45" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_splits_tagged_p45_contexts_from_real_roman_suffix_splits() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    cases = [
        (
            "sup-marker",
            "<html><body><p>Joao Paulo Teixeira<sup>i</sup>, Daniele Mandrioli.</p></body></html>",
            "P45S",
        ),
        (
            "linked-suffix",
            "<html><body><p>Korol and Pisan "
            '<a href="#ref-67" class="z2m-ref-link">i</a> '
            '<a href="#ref-67" class="z2m-ref-link">2015)</a>.</p></body></html>',
            "P45L",
        ),
        (
            "math-variable",
            "<html><body><p>Function "
            '<span class="z2m-math z2m-math-inline" data-z2m-tex="\\(v(\\cdot)\\)">v</span> '
            "computes the vector.</p></body></html>",
            "P45M",
        ),
        (
            "affiliation-label",
            "<html><body><p>a University of Copenhagen, Copenhagen, Denmark "
            "b University of Debrecen, Hungary c Institute of Occupational Medicine, Germany "
            "d National Institute, France e Public Health Center, Italy f Research Unit, Spain "
            "g Maritime Medicine, Hamburg, Germany h Aarhus University, Copenhagen, Denmark "
            "i National Institute of Health, Porto, Portugal ARTICLE INFO Keywords: Insecticides.</p></body></html>",
            "P45A",
        ),
        (
            "affiliation-label-country-institution",
            "<html><body><p>h Aarhus University, Department of Public Health, Aarhus, "
            "National Research Centre for the Working Environment, Copenhagen, Denmark "
            "i National Institute of Health, Environmental Health Department, Porto, Portugal "
            "ARTICLE INFO Keywords: Cohort study.</p></body></html>",
            "P45A",
        ),
        (
            "affiliation-label-state-country-institution",
            "<html><body><p>h School of Medicine and Psychology, ANU College of Health and Medicine, "
            "Canberra, NSW Australia i Clinical Psychology, McGill University, Montreal, QC Canada "
            "j Monash Alfred Psychiatry Research Center ARTICLE INFO Keywords: Brain stimulation.</p></body></html>",
            "P45A",
        ),
        (
            "frontmatter-list-affiliation-label",
            '<html><body><p block-type="ListGroup" class="z2m-front-matter"><ul>'
            "<li><sup>h</sup> Aarhus University, Copenhagen, Denmark</li>"
            "<li><sup>i</sup> National Institute of Health, Porto, Portugal</li>"
            "</ul></p></body></html>",
            "P45A",
        ),
    ]
    try:
        stage_dir = tmp_path / "Article sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")

        for name, polish_html, expected_id in cases:
            polish_path.write_text(polish_html, encoding="utf-8")
            result = audit.analyze_pair(raw_path, polish_path)

            defects_by_id = {defect["id"]: defect for defect in result["defects_found"]}
            assert "P45" not in defects_by_id, name
            assert defects_by_id[expected_id]["severity"] == "warning"
            assert defects_by_id[expected_id]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_post_reference_doi_metadata_for_duplicate_numbers() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "doi metadata sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<h4>References</h4>"
            '<ul><li id="ref-10"><span class="z2m-ref-num">10.</span> Real reference.</li></ul>'
            '<p><a href="https://doi.org/10.4028/www.scientific.net/AMM.510">'
            "10.4028/www.scientific.net/AMM.510</a></p>"
            '<p><a href="https://doi.org/10.4028/www.scientific.net/AMM.510.163">'
            "10.4028/www.scientific.net/AMM.510.163</a></p>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P22" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_reports_doi_body_merge_only_within_one_block() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "doi boundary sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")

        polish_path.write_text(
            "<html><body>"
            "<p>DOI: https://doi.org/10.1145/2982142.2982176 "
            "the plasticity of the system remains visible in later trials.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        result = audit.analyze_pair(raw_path, polish_path)
        assert "P75" in {defect["id"] for defect in result["defects_found"]}

        polish_path.write_text(
            "<html><body>"
            "<p>DOI: https://doi.org/10.1145/2982142.2982176</p>"
            "<p>the plasticity of the system remains visible in later trials.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        result = audit.analyze_pair(raw_path, polish_path)
        assert "P75" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p61_accepts_supplementary_figure_target() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "supplementary figure sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>See <a href="#fig-supplementary-11" class="z2m-fig-link">Supplementary Figure 11</a> '
            'and <a href="#fig-1" class="z2m-fig-link">Figure 1</a>.</p>'
            '<p id="fig-supplementary-11">Supplementary Figure 11. Effect of the sensing condition.</p>'
            '<p id="fig-1">Figure 1. Main overview.</p>'
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P61" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p61_is_not_quality_counted() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "missing figure reference sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The setup is shown in Figure 7.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        p61 = [defect for defect in result["defects_found"] if defect["id"] == "P61"]
        assert len(p61) == 1
        assert p61[0]["extra"]["quality_counted"] is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p61_uses_compound_figure_reference_keys() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "compound figure ref sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            "<p>The relation is shown in Figure 2-1 and Fig. 3.5.</p>"
            "<p>The Cole model in Figure 2.1a remains visible, and the robustness is tested in Figure 5. "
            "100 random examples are generated.</p>"
            '<div id="fig-2-1" class="z2m-float-unit z2m-figure-unit">'
            '<p class="z2m-figure-target"><img src="fig21.jpg"/></p>'
            '<p class="z2m-figure-caption">Figure 2-1. Conductivity summary.</p>'
            "</div>"
            '<div id="fig-3-5" class="z2m-float-unit z2m-figure-unit">'
            '<p class="z2m-figure-target"><img src="fig35.jpg"/></p>'
            '<p class="z2m-figure-caption">Figure 3.5. Flow-rate signal.</p>'
            "</div>"
            '<div id="fig-5" class="z2m-float-unit z2m-figure-unit">'
            '<p class="z2m-figure-target"><img src="fig5.jpg"/></p>'
            '<p class="z2m-figure-caption">Figure 5. Robustness test.</p>'
            "</div>"
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P61" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_accepts_split_prefix_supplementary_figure_link() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "split supplementary figure sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>The calibration is shown in Supplementary '
            '<a href="#fig-supplementary-2" class="z2m-fig-link">Figure 2</a>.</p>'
            '<p id="fig-supplementary-2">Supplementary Figure 2. Calibration summary.</p>'
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P61" not in defect_ids
        assert "P13" not in defect_ids
        assert "P14" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_p61_ignores_external_supplementary_figure_ref() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "missing supplementary figure sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body><p>The delayed response appears in Supplementary Figure 11.</p></body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        assert "P61" not in {defect["id"] for defect in result["defects_found"]}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_analyze_pair_ignores_supplementary_caption_only_target_for_p13_p14() -> None:
    audit = _load_audit_module()
    tmp_path = _make_temp_dir()
    try:
        stage_dir = tmp_path / "supplementary caption target sample" / "_z2m_stages"
        stage_dir.mkdir(parents=True)
        raw_path = stage_dir / "01.en.raw.html"
        polish_path = stage_dir / "02.en.polish.html"
        raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
        polish_path.write_text(
            "<html><body>"
            '<p>See <a href="#fig-supplementary-s2" class="z2m-fig-link">Supplementary Figure S2</a>.</p>'
            '<p id="fig-supplementary-s2">Supplementary Figure S2 Prompt for generating queries.</p>'
            "</body></html>",
            encoding="utf-8",
        )

        result = audit.analyze_pair(raw_path, polish_path)

        defect_ids = {defect["id"] for defect in result["defects_found"]}
        assert "P13" not in defect_ids
        assert "P14" not in defect_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_broken_url_audit_does_not_flag_url_followed_by_reference_year() -> None:
    audit = _load_audit_module()

    assert audit.BROKEN_URL_TEXT_RE.search("See https://example.org/path/ (2018).") is None
    assert audit.BROKEN_URL_TEXT_RE.search("IEEE Xplore https://ieeexplore.ieee.org/ 1 March 2021") is None
    assert (
        audit.BROKEN_URL_TEXT_RE.search(
            "Resources http://www.easytactilegraphics.com/product/intact-sketchpad/ "
            "http://www.sensationalbooks.com/products.html"
        )
        is None
    )
    assert (
        audit.MALFORMED_URL_ANCHOR_BODY_RE.search(
            '<a href="http://www.easytactilegraphics.com/product/intact-sketchpad/">'
            "http://www.easytactilegraphics.com/product/intact-sketchpad/</a> "
            '<a href="http://www.sensationalbooks.com/products.html">'
            "http://www.sensationalbooks.com/products.html</a>"
        )
        is None
    )
    assert audit.BROKEN_URL_TEXT_RE.search("See https://example.org/path/ next-fragment.") is not None
