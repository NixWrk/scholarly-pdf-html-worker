from pathlib import Path

from pdf_html_polish.quality_loop.pattern_observations import write_pattern_observations
from pdf_html_polish.quality_loop.run_utils import write_json


def _write_run(run_dir: Path, *, run_id: str, article: str, snippet: str) -> None:
    write_json(run_dir / "manifest.json", {"source_kind": "cached_raw_repolish", "code_commit": run_id})
    write_json(run_dir / "quality_history_entry.json", {"run_id": run_id})
    write_json(
        run_dir / "audit_full_checks.json",
        {
            "articles": [
                {
                    "article": article,
                    "raw_stage_path": f"{article}.raw.html",
                    "polish_stage_path": f"{article}.polish.html",
                    "defects_found": [
                        {
                            "id": "P67",
                            "severity": "warning",
                            "check": "Text residue",
                            "snippet": snippet,
                        }
                    ],
                }
            ]
        },
    )


def test_pattern_observations_accumulate_across_runs(tmp_path: Path) -> None:
    history_path = tmp_path / "pattern_history.jsonl"
    defect_patterns = {
        "P67": {
            "pattern": "text-cleanup",
            "criticality": "medium",
            "fix_layer": "EN polish text cleanup",
        }
    }
    first_run = tmp_path / "run1"
    second_run = tmp_path / "run2"
    _write_run(first_run, run_id="run1", article="article_a", snippet="bad spacing")
    _write_run(second_run, run_id="run2", article="article_b", snippet="bad join")

    first_summary = write_pattern_observations(
        first_run,
        defect_patterns=defect_patterns,
        history_path=history_path,
    )
    second_summary = write_pattern_observations(
        second_run,
        defect_patterns=defect_patterns,
        history_path=history_path,
    )

    assert first_summary["patterns"][0]["pattern_key"] == "text-cleanup"
    assert history_path.read_text(encoding="utf-8").count("\n") == 2
    candidate = second_summary["problem_candidates"][0]
    assert candidate["pattern_key"] == "text-cleanup"
    assert candidate["run_ids"] == ["run1", "run2"]
    assert candidate["article_observation_count"] == 2
