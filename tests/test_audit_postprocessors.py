from __future__ import annotations

import copy
from pathlib import Path

import pytest

from pdf_html_polish.quality_loop.audit_postprocessors import (
    AuditPostprocessorError,
    normalize_converted_audit_article_ids_payload,
)


def _article(tmp_path: Path, name: str, article: str = "Doc") -> dict[str, object]:
    stage_dir = tmp_path / name / "_z2m_stages"
    return {
        "article": article,
        "raw_stage_path": str((stage_dir / "01.en.raw.html").resolve(strict=False)),
        "polish_stage_path": str((stage_dir / "02.en.polish.html").resolve(strict=False)),
        "summary": {"polish_blocks": 1},
    }


def _manifest_article(
    audit_article: dict[str, object],
    article_id: str,
) -> dict[str, object]:
    return {
        "article_id": article_id,
        "raw_stage_path": audit_article["raw_stage_path"],
        "polish_stage_path": audit_article["polish_stage_path"],
        "artifact_hint": f"converted/{article_id}",
    }


def test_normalize_converted_ids_is_exact_and_does_not_mutate_inputs(
    tmp_path: Path,
) -> None:
    first = _article(tmp_path, "first")
    second = _article(tmp_path, "second")
    audit = {"articles": [first, second], "article_count": 2, "marker": "kept"}
    manifest = {
        "source_kind": "converted_stage_roots",
        "articles": [
            _manifest_article(first, "first_id"),
            _manifest_article(second, "second_id"),
        ],
    }
    original_audit = copy.deepcopy(audit)
    original_manifest = copy.deepcopy(manifest)

    normalized = normalize_converted_audit_article_ids_payload(audit, manifest)

    assert audit == original_audit
    assert manifest == original_manifest
    assert [item["article"] for item in normalized["articles"]] == [
        "first_id",
        "second_id",
    ]
    assert [item["source_article"] for item in normalized["articles"]] == [
        "Doc",
        "Doc",
    ]
    assert [item["artifact_hint"] for item in normalized["articles"]] == [
        "converted/first_id",
        "converted/second_id",
    ]
    assert normalized["marker"] == "kept"
    assert "converted_id_normalization_unmatched" not in normalized


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("wrong-kind", "manifest_source_kind_invalid"),
        ("duplicate-id", "manifest_article_id_invalid:1"),
        ("duplicate-manifest-pair", "manifest_stage_pair_duplicate:second_id"),
        ("relative-manifest-path", "manifest_article:first_id_raw_stage_path_invalid"),
        ("invalid-hint", "manifest_artifact_hint_invalid:first_id"),
        ("duplicate-audit-pair", "audit_stage_pair_duplicate:Doc"),
        ("invalid-source-article", "audit_source_article_invalid:Doc"),
    ],
)
def test_normalize_converted_ids_rejects_ambiguous_inputs(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    first = _article(tmp_path, "first")
    second = _article(tmp_path, "second")
    audit = {"articles": [first, second]}
    manifest = {
        "source_kind": "converted_stage_roots",
        "articles": [
            _manifest_article(first, "first_id"),
            _manifest_article(second, "second_id"),
        ],
    }
    if mutation == "wrong-kind":
        manifest["source_kind"] = "other"
    elif mutation == "duplicate-id":
        manifest["articles"][1]["article_id"] = "first_id"
    elif mutation == "duplicate-manifest-pair":
        manifest["articles"][1]["raw_stage_path"] = manifest["articles"][0][
            "raw_stage_path"
        ]
        manifest["articles"][1]["polish_stage_path"] = manifest["articles"][0][
            "polish_stage_path"
        ]
    elif mutation == "relative-manifest-path":
        manifest["articles"][0]["raw_stage_path"] = "relative.html"
    elif mutation == "invalid-hint":
        manifest["articles"][0]["artifact_hint"] = 7
    elif mutation == "duplicate-audit-pair":
        audit["articles"][1]["raw_stage_path"] = audit["articles"][0][
            "raw_stage_path"
        ]
        audit["articles"][1]["polish_stage_path"] = audit["articles"][0][
            "polish_stage_path"
        ]
    else:
        audit["articles"][0]["source_article"] = 7

    with pytest.raises(AuditPostprocessorError, match=reason):
        normalize_converted_audit_article_ids_payload(audit, manifest)


def test_normalize_converted_ids_records_unmatched_pairs(tmp_path: Path) -> None:
    first = _article(tmp_path, "first")
    audit = {
        "articles": [first],
        "converted_id_normalization_unmatched": [{"stale": True}],
    }
    manifest = {"source_kind": "converted_stage_roots", "articles": []}

    normalized = normalize_converted_audit_article_ids_payload(audit, manifest)

    assert normalized["article_count"] == 1
    assert normalized["converted_id_normalization_unmatched"] == [
        {
            "raw_stage_path": first["raw_stage_path"],
            "polish_stage_path": first["polish_stage_path"],
        }
    ]
