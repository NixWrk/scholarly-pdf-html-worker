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
            "P04",
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
        assert "P04" in defect_ids
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
            "P62",
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
        expected = {"P67", "P71", "P83", "P87", "P91", "P92"}
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
        expected = {"P66", "P67", "P71", "P81", "P82", "P83", "P84", "P90", "P92"}
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
        expected = {"P36", "P67", "P71", "P72", "P75", "P83", "P90", "P91", "P92"}
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


def test_broken_url_audit_does_not_flag_url_followed_by_reference_year() -> None:
    audit = _load_audit_module()

    assert audit.BROKEN_URL_TEXT_RE.search("See https://example.org/path/ (2018).") is None
    assert audit.BROKEN_URL_TEXT_RE.search("IEEE Xplore https://ieeexplore.ieee.org/ 1 March 2021") is None
    assert audit.BROKEN_URL_TEXT_RE.search("See https://example.org/path/ next-fragment.") is not None
