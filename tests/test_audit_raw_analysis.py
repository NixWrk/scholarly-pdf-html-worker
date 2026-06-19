from pdf_html_polish.quality_loop.audit_raw_analysis import analyze_raw_file


def test_analyze_raw_file_reports_summary_and_defects(tmp_path) -> None:
    article_dir = tmp_path / "Raw sample"
    stage_dir = article_dir / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    html_path = stage_dir / "01.en.raw.html"
    html_path.write_text(
        "\n".join(
            [
                "<html><body>",
                "<p>Figure 1. Caption without image.</p>",
                "<p>Page 2 of 4 with Foilii and 20 \u0412\u00b5 m.</p>",
                "<p>@@Z2M_A_1</p>",
                "</body></html>",
            ]
        ),
        encoding="utf-8",
    )

    result = analyze_raw_file(html_path)

    summary = result["en_raw_summary"]
    assert result["article"] == "Raw sample"
    assert summary["figure_labels"] == 1
    assert summary["page_headers"] == 1
    assert summary["raw_sentinels"] == 1
    assert summary["formula_unit_fragments"] == 1
    assert summary["mojibake_micro_tokens"] == 1

    defect_ids = {defect["id"] for defect in result["defects_found"]}
    assert {"R05", "R07", "R08", "R12", "R14"}.issubset(defect_ids)
