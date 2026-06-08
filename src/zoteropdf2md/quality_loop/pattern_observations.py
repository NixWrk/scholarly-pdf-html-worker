"""Pattern-observation history for quality-loop audits."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .observations import add_count, append_jsonl, problem_state, read_jsonl
from .run_utils import load_json, now, slug, write_json


DEFAULT_PATTERN_HISTORY_NAME = "pattern_observation_history.jsonl"


def pattern_key_for_defect(defect: dict[str, Any], defect_patterns: dict[str, Any]) -> str:
    defect_id = str(defect.get("id") or "unknown")
    pattern = defect_patterns.get(defect_id) if isinstance(defect_patterns.get(defect_id), dict) else {}
    known_pattern = str(pattern.get("pattern") or "").strip()
    if known_pattern:
        return known_pattern
    check = str(defect.get("check") or "unclassified").strip()
    return f"{defect_id}:{slug(check, max_len=48)}"


def empty_pattern_record(pattern_key: str, defect_patterns: dict[str, Any]) -> dict[str, Any]:
    matching = [
        pattern
        for pattern in defect_patterns.values()
        if isinstance(pattern, dict) and pattern.get("pattern") == pattern_key
    ]
    known = matching[0] if matching else {}
    return {
        "pattern_key": pattern_key,
        "criticality": known.get("criticality"),
        "fix_layer": known.get("fix_layer"),
        "occurrence_count": 0,
        "article_count": 0,
        "articles": [],
        "defect_ids": {},
        "checks": {},
        "severity_counts": {},
        "sample_observations": [],
    }


def aggregate_pattern_history(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for record in records:
        run_id = str(record.get("run_id") or "")
        generated_at = str(record.get("generated_at") or "")
        for pattern in record.get("patterns") or []:
            if not isinstance(pattern, dict):
                continue
            pattern_key = str(pattern.get("pattern_key") or "")
            if not pattern_key:
                continue
            target = aggregated.setdefault(
                pattern_key,
                {
                    "pattern_key": pattern_key,
                    "criticality": pattern.get("criticality"),
                    "fix_layer": pattern.get("fix_layer"),
                    "run_ids": [],
                    "run_count": 0,
                    "occurrence_count": 0,
                    "article_observation_count": 0,
                    "defect_ids": {},
                    "checks": {},
                    "severity_counts": {},
                    "sample_observations": [],
                    "first_seen_at": generated_at,
                    "last_seen_at": generated_at,
                },
            )
            if run_id and run_id not in target["run_ids"]:
                target["run_ids"].append(run_id)
            target["run_count"] = len(target["run_ids"])
            target["occurrence_count"] += int(pattern.get("occurrence_count") or 0)
            target["article_observation_count"] += int(pattern.get("article_count") or 0)
            for key, value in dict(pattern.get("defect_ids") or {}).items():
                add_count(target["defect_ids"], str(key), int(value or 0))
            for key, value in dict(pattern.get("checks") or {}).items():
                add_count(target["checks"], str(key), int(value or 0))
            for key, value in dict(pattern.get("severity_counts") or {}).items():
                add_count(target["severity_counts"], str(key), int(value or 0))
            for sample in pattern.get("sample_observations") or []:
                if len(target["sample_observations"]) >= 8:
                    break
                if isinstance(sample, dict):
                    target["sample_observations"].append(sample)
            if generated_at:
                if not target.get("first_seen_at") or generated_at < target["first_seen_at"]:
                    target["first_seen_at"] = generated_at
                if not target.get("last_seen_at") or generated_at > target["last_seen_at"]:
                    target["last_seen_at"] = generated_at

    for pattern in aggregated.values():
        pattern["defect_ids"] = dict(sorted(pattern["defect_ids"].items()))
        pattern["checks"] = dict(sorted(pattern["checks"].items()))
        pattern["severity_counts"] = dict(sorted(pattern["severity_counts"].items()))
        pattern["run_ids"] = sorted(pattern["run_ids"])
        pattern["problem_state"] = problem_state(
            int(pattern.get("run_count") or 0),
            int(pattern.get("article_observation_count") or 0),
            int(pattern.get("occurrence_count") or 0),
        )

    return sorted(
        aggregated.values(),
        key=lambda item: (
            item.get("problem_state") != "problem_candidate",
            -int(item.get("article_observation_count") or 0),
            -int(item.get("occurrence_count") or 0),
            str(item.get("pattern_key") or ""),
        ),
    )


def write_pattern_observations(
    run_dir: Path,
    *,
    defect_patterns_path: Path | None = None,
    defect_patterns: dict[str, Any] | None = None,
    history_path: Path | None = None,
    default_history_name: str = DEFAULT_PATTERN_HISTORY_NAME,
) -> dict[str, Any]:
    """Summarize current corpus manifestations and append them to pattern history."""

    run_dir = run_dir.resolve(strict=False)
    history_path = (history_path or (run_dir.parent / default_history_name)).resolve(strict=False)
    if defect_patterns is None:
        defect_patterns = load_json(defect_patterns_path, default={}) if defect_patterns_path is not None else {}
    audit = load_json(run_dir / "audit_full_checks.json", default={"articles": []})
    manifest = load_json(run_dir / "manifest.json", default={})
    entry = load_json(run_dir / "quality_history_entry.json", default={})
    run_id = str(entry.get("run_id") or run_dir.name)

    current_by_pattern: dict[str, dict[str, Any]] = {}
    audit_articles = [article for article in audit.get("articles") or [] if isinstance(article, dict)]
    for article in audit_articles:
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        source_article = str(article.get("source_article") or article_id)
        artifact_hint = article.get("artifact_hint")
        raw_stage_path = article.get("raw_stage_path")
        polish_stage_path = article.get("polish_stage_path")
        for defect in article.get("defects_found") or []:
            if not isinstance(defect, dict):
                continue
            pattern_key = pattern_key_for_defect(defect, defect_patterns)
            record = current_by_pattern.setdefault(
                pattern_key,
                {
                    **empty_pattern_record(pattern_key, defect_patterns),
                    "_article_set": set(),
                },
            )
            record["occurrence_count"] += 1
            record["_article_set"].add(article_id)
            add_count(record["defect_ids"], str(defect.get("id") or "unknown"))
            add_count(record["checks"], str(defect.get("check") or "unknown"))
            add_count(record["severity_counts"], str(defect.get("severity") or "info"))
            if len(record["sample_observations"]) < 8:
                record["sample_observations"].append(
                    {
                        "article": article_id,
                        "source_article": source_article,
                        "artifact_hint": artifact_hint,
                        "defect_id": defect.get("id"),
                        "severity": defect.get("severity"),
                        "check": defect.get("check"),
                        "snippet": defect.get("snippet"),
                        "raw_stage_path": raw_stage_path,
                        "polish_stage_path": polish_stage_path,
                    }
                )

    patterns: list[dict[str, Any]] = []
    for record in current_by_pattern.values():
        articles = sorted(record.pop("_article_set"))
        record["articles"] = articles
        record["article_count"] = len(articles)
        record["defect_ids"] = dict(sorted(record["defect_ids"].items()))
        record["checks"] = dict(sorted(record["checks"].items()))
        record["severity_counts"] = dict(sorted(record["severity_counts"].items()))
        record["problem_state"] = problem_state(1, len(articles), int(record["occurrence_count"] or 0))
        patterns.append(record)

    patterns.sort(
        key=lambda item: (
            item.get("problem_state") != "problem_candidate",
            -int(item.get("article_count") or 0),
            -int(item.get("occurrence_count") or 0),
            str(item.get("pattern_key") or ""),
        )
    )

    history_record = {
        "generated_at": now(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "source_kind": manifest.get("source_kind"),
        "code_commit": manifest.get("code_commit"),
        "working_tree_dirty": manifest.get("working_tree_dirty"),
        "article_count_reviewed": len(audit_articles),
        "pattern_count": len(patterns),
        "patterns": patterns,
    }
    previous_history = read_jsonl(history_path)
    append_jsonl(history_path, history_record)
    cumulative_patterns = aggregate_pattern_history([*previous_history, history_record])
    problem_candidates = [
        pattern for pattern in cumulative_patterns if pattern.get("problem_state") == "problem_candidate"
    ]
    summary = {
        **history_record,
        "history_path": str(history_path),
        "all_articles_reviewed_for_patterns": True,
        "cumulative_patterns": cumulative_patterns,
        "problem_candidates": problem_candidates,
    }
    write_json(run_dir / "pattern_observations.json", summary)
    return summary
