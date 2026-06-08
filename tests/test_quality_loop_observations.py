from pathlib import Path

from zoteropdf2md.quality_loop.observations import (
    compact_observation_text,
    manual_observation_signature,
    read_jsonl,
    record_manual_observation,
    write_manual_observation_summary,
)
from zoteropdf2md.quality_loop.run_utils import write_json


def test_manual_observation_summary_accumulates_problem_candidates(tmp_path: Path) -> None:
    ledger_path = tmp_path / "manual_observation_ledger.jsonl"
    first = record_manual_observation(
        ledger_path,
        {
            "created_at": "2026-05-25T00:00:00+00:00",
            "run_id": "run1",
            "article": "article_a",
            "snippet": "The article shows Objec tive split in a heading.",
            "suspected_pattern": "inline OCR word split in ordinary text",
        },
    )
    second = record_manual_observation(
        ledger_path,
        {
            "created_at": "2026-05-25T01:00:00+00:00",
            "run_id": "run2",
            "article": "article_b",
            "snippet": "The body contains meth ods after an inline span.",
            "suspected_pattern": "inline OCR word split in ordinary text",
        },
    )
    run_dir = tmp_path / "run2"
    write_json(run_dir / "quality_history_entry.json", {"run_id": "run2"})

    summary = write_manual_observation_summary(run_dir, ledger_path=ledger_path)

    assert first["normalized_signature"] == second["normalized_signature"]
    assert len(read_jsonl(ledger_path)) == 2
    assert summary["observation_count"] == 2
    candidate = summary["problem_candidates"][0]
    assert candidate["article_count"] == 2
    assert candidate["run_count"] == 2
    assert [sample["article"] for sample in candidate["sample_observations"]] == ["article_a", "article_b"]


def test_manual_observation_signature_and_compaction() -> None:
    assert manual_observation_signature({"snippet": "<span>Figure 12</span> has residue 34"}) == (
        "text:figure_has_residue"
    )
    assert compact_observation_text("a " * 400, max_len=12) == "a a a a a..."
