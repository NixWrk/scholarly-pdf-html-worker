from pathlib import Path

from scripts.record_en_polish_quality_history import build_entry, compare_entries


def test_quality_history_records_all_numeric_audit_and_assessment_metrics() -> None:
    assessment = {
        "articles": [
            {
                "article": "article_a",
                "profile_style": "bracket_numeric",
                "profile_confidence": "medium",
                "profile_status": "ok",
                "href_counts": {
                    "broken_internal_links": 1,
                    "internal_page_anchor_links": 2,
                    "ref_links": 5,
                    "table_links": 1,
                },
                "table_units_with_section_ids": 2,
                "sup_ref_links": 0,
                "bracket_ref_links": 4,
                "mixed_citation_style": False,
                "missing_warning_count": 3,
            }
        ]
    }
    audit = {
        "corpus_summary": {"defect_counts": {"P01": 1, "P02": 1}},
        "articles": [
            {
                "article": "article_a",
                "summary": {
                    "raw_blocks": 10,
                    "polish_blocks": 8,
                    "raw_img_tags": 1,
                    "polish_img_tags": 2,
                    "polish_ref_links": 7,
                    "polish_fig_links": 3,
                    "polish_table_links": 1,
                    "polish_page_links": 2,
                    "polish_fig_ids": 3,
                    "polish_table_ids": 1,
                    "polish_has_target_style": True,
                    "polish_replacement_chars": 2,
                    "polish_missing_local_images": 1,
                    "source_pdf_present": False,
                    "pdf_text_chars": 123,
                    "pdf_text_status": "ok",
                    "source_pdf_origin": "map",
                },
                "defects_found": [
                    {"id": "P01", "severity": "error"},
                    {"id": "P02", "severity": "warning"},
                ],
            }
        ],
    }

    entry = build_entry(
        run_dir=Path("run"),
        run_id="run_a",
        assessment=assessment,
        audit=audit,
    )

    record = entry["articles"]["article_a"]
    metrics = record["metrics"]

    assert metrics["raw_blocks"] == 10
    assert metrics["polish_blocks"] == 8
    assert metrics["block_delta"] == -2
    assert metrics["image_delta"] == 1
    assert metrics["polish_replacement_chars"] == 2
    assert metrics["polish_missing_local_images"] == 1
    assert metrics["pdf_text_chars"] == 123
    assert metrics["polish_has_target_style"] == 1
    assert metrics["broken_internal_links"] == 1
    assert metrics["bracket_ref_links"] == 4
    assert metrics["missing_warning_count"] == 3
    assert record["labels"]["profile_style"] == "bracket_numeric"
    assert record["labels"]["pdf_text_status"] == "ok"
    assert entry["totals"]["raw_blocks"] == 10
    assert entry["totals"]["polish_replacement_chars"] == 2


def test_quality_history_compares_deltas_for_every_metric() -> None:
    previous = {
        "run_id": "old",
        "totals": {"score": 10, "polish_replacement_chars": 1},
        "articles": {
            "article_a": {
                "score": 10,
                "defects": 1,
                "errors": 1,
                "warnings": 0,
                "metrics": {
                    "raw_blocks": 10,
                    "polish_blocks": 9,
                    "polish_replacement_chars": 1,
                    "broken_internal_links": 2,
                },
            }
        },
    }
    current = {
        "run_id": "new",
        "totals": {"score": 7, "polish_replacement_chars": 3},
        "articles": {
            "article_a": {
                "score": 7,
                "defects": 1,
                "errors": 0,
                "warnings": 1,
                "metrics": {
                    "raw_blocks": 10,
                    "polish_blocks": 8,
                    "polish_replacement_chars": 3,
                    "broken_internal_links": 0,
                },
            }
        },
    }

    comparison = compare_entries(previous, current)
    delta = comparison["improvements"][0]

    assert comparison["totals_delta"]["score"] == -3
    assert comparison["totals_delta"]["polish_replacement_chars"] == 2
    assert delta["metrics_delta"]["polish_blocks"] == -1
    assert delta["metrics_delta"]["polish_replacement_chars"] == 2
    assert delta["polish_replacement_chars_delta"] == 2
    assert delta["broken_internal_links_delta"] == -2
