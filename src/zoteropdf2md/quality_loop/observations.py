"""Manual and pattern-observation helpers for quality-loop runs."""

from __future__ import annotations

from html import unescape
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .run_utils import load_json, now, slug, write_json


DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME = "manual_observation_ledger.jsonl"
TAG_RE = re.compile(r"<[^>]+>")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def add_count(target: dict[str, int], key: str, amount: int = 1) -> None:
    target[key] = int(target.get(key, 0) or 0) + amount


def problem_state(run_count: int, article_observation_count: int, occurrence_count: int) -> str:
    if run_count >= 2 or article_observation_count >= 2 or occurrence_count >= 3:
        return "problem_candidate"
    return "pattern_observation"


def manual_observation_ledger_path(
    run_dir: Path,
    ledger_path: Path | None = None,
    *,
    default_name: str = DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME,
) -> Path:
    return (ledger_path or (run_dir.parent / default_name)).resolve(strict=False)


def normalize_observation_text(value: Any, *, max_len: int = 180) -> str:
    text = TAG_RE.sub(" ", str(value or ""))
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\d+", "#", text)
    return text[:max_len]


def compact_observation_text(value: Any, *, max_len: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def manual_observation_signature(observation: dict[str, Any]) -> str:
    suspected_pattern = normalize_observation_text(observation.get("suspected_pattern"), max_len=96)
    if suspected_pattern:
        return f"pattern:{slug(suspected_pattern, max_len=96)}"
    for key in ("visible_text", "snippet", "html_fragment", "notes"):
        normalized = normalize_observation_text(observation.get(key))
        if normalized:
            return f"text:{slug(normalized, max_len=120)}"
    return "text:unknown"


def record_manual_observation(ledger_path: Path, observation: dict[str, Any]) -> dict[str, Any]:
    """Append one manually spotted manifestation to the cumulative ledger."""

    article = str(observation.get("article") or "").strip()
    snippet = str(observation.get("snippet") or "").strip()
    if not article:
        raise ValueError("Manual observation requires an article.")
    if not snippet:
        raise ValueError("Manual observation requires a snippet.")

    created_at = str(observation.get("created_at") or now())
    stage_path = observation.get("stage_path")
    defect_id = observation.get("defect_id_if_any") or observation.get("defect_id")
    record = {
        "created_at": created_at,
        "run_id": str(observation.get("run_id") or "").strip(),
        "article": article,
        "stage_path": str(stage_path) if stage_path else "",
        "defect_id_if_any": str(defect_id or "").strip(),
        "snippet": snippet,
        "html_fragment": str(observation.get("html_fragment") or "").strip(),
        "visible_text": str(observation.get("visible_text") or "").strip(),
        "suspected_pattern": str(observation.get("suspected_pattern") or "").strip(),
        "status": str(observation.get("status") or "untriaged").strip() or "untriaged",
        "test_status": str(observation.get("test_status") or "none").strip() or "none",
        "notes": str(observation.get("notes") or "").strip(),
        "source": str(observation.get("source") or "manual_review").strip() or "manual_review",
    }
    record["normalized_signature"] = str(
        observation.get("normalized_signature") or manual_observation_signature(record)
    )
    digest_source = json.dumps(
        {
            "created_at": record["created_at"],
            "article": record["article"],
            "snippet": record["snippet"],
            "stage_path": record["stage_path"],
            "suspected_pattern": record["suspected_pattern"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    record["observation_id"] = str(
        observation.get("observation_id")
        or f"manual-{slug(created_at, max_len=20)}-{hashlib.sha1(digest_source.encode('utf-8')).hexdigest()[:10]}"
    )
    append_jsonl(ledger_path.resolve(strict=False), record)
    return record


def write_manual_observation_summary(
    run_dir: Path,
    *,
    ledger_path: Path | None = None,
    default_ledger_name: str = DEFAULT_MANUAL_OBSERVATION_LEDGER_NAME,
) -> dict[str, Any]:
    """Group raw manual observations before promoting them into problems."""

    run_dir = run_dir.resolve(strict=False)
    ledger_path = manual_observation_ledger_path(run_dir, ledger_path, default_name=default_ledger_name)
    raw_records = read_jsonl(ledger_path)
    records_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_record in enumerate(raw_records):
        record = dict(raw_record)
        observation_id = str(record.get("observation_id") or f"legacy-{index}")
        record["observation_id"] = observation_id
        created_at = str(record.get("created_at") or "")
        previous = records_by_id.get(observation_id)
        if previous is None:
            record["_first_seen_at"] = created_at
            records_by_id[observation_id] = record
            continue
        first_seen = str(previous.get("_first_seen_at") or previous.get("created_at") or "")
        previous_created = str(previous.get("created_at") or "")
        if created_at >= previous_created:
            record["_first_seen_at"] = first_seen
            records_by_id[observation_id] = record
    records = sorted(
        records_by_id.values(),
        key=lambda record: (str(record.get("_first_seen_at") or ""), str(record.get("observation_id") or "")),
    )
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        signature = str(record.get("normalized_signature") or manual_observation_signature(record))
        first_seen_at = str(record.get("_first_seen_at") or record.get("created_at") or "")
        group = grouped.setdefault(
            signature,
            {
                "normalized_signature": signature,
                "occurrence_count": 0,
                "article_count": 0,
                "run_count": 0,
                "articles": [],
                "run_ids": [],
                "defect_ids": {},
                "statuses": {},
                "test_statuses": {},
                "suspected_patterns": {},
                "sources": {},
                "sample_observations": [],
                "first_seen_at": first_seen_at,
                "last_seen_at": str(record.get("created_at") or ""),
                "_articles": set(),
                "_run_ids": set(),
            },
        )
        group["occurrence_count"] += 1
        article = str(record.get("article") or "")
        run_id = str(record.get("run_id") or "")
        if article:
            group["_articles"].add(article)
        if run_id:
            group["_run_ids"].add(run_id)
        add_count(group["defect_ids"], str(record.get("defect_id_if_any") or "none"))
        add_count(group["statuses"], str(record.get("status") or "untriaged"))
        add_count(group["test_statuses"], str(record.get("test_status") or "none"))
        add_count(group["suspected_patterns"], str(record.get("suspected_pattern") or "unspecified"))
        add_count(group["sources"], str(record.get("source") or "manual_review"))

        created_at = str(record.get("created_at") or "")
        if first_seen_at:
            if not group.get("first_seen_at") or first_seen_at < group["first_seen_at"]:
                group["first_seen_at"] = first_seen_at
        if created_at:
            if not group.get("last_seen_at") or created_at > group["last_seen_at"]:
                group["last_seen_at"] = created_at
        if len(group["sample_observations"]) < 8:
            group["sample_observations"].append(
                {
                    "observation_id": record.get("observation_id"),
                    "article": article,
                    "run_id": run_id,
                    "stage_path": record.get("stage_path"),
                    "defect_id_if_any": record.get("defect_id_if_any"),
                    "snippet": compact_observation_text(record.get("snippet")),
                    "status": record.get("status") or "untriaged",
                    "test_status": record.get("test_status") or "none",
                    "notes": compact_observation_text(record.get("notes"), max_len=240),
                }
            )

    groups: list[dict[str, Any]] = []
    for group in grouped.values():
        articles = sorted(group.pop("_articles"))
        run_ids = sorted(group.pop("_run_ids"))
        group["articles"] = articles
        group["run_ids"] = run_ids
        group["article_count"] = len(articles)
        group["run_count"] = len(run_ids)
        for key in ("defect_ids", "statuses", "test_statuses", "suspected_patterns", "sources"):
            group[key] = dict(sorted(group[key].items()))
        group["problem_state"] = problem_state(
            int(group.get("run_count") or 0),
            int(group.get("article_count") or 0),
            int(group.get("occurrence_count") or 0),
        )
        groups.append(group)

    groups.sort(
        key=lambda item: (
            item.get("problem_state") != "problem_candidate",
            -int(item.get("article_count") or 0),
            -int(item.get("occurrence_count") or 0),
            str(item.get("normalized_signature") or ""),
        )
    )
    problem_candidates = [group for group in groups if group.get("problem_state") == "problem_candidate"]
    requires_triage = [group for group in groups if int(dict(group.get("statuses") or {}).get("untriaged", 0) or 0)]
    summary = {
        "generated_at": now(),
        "run_id": load_json(run_dir / "quality_history_entry.json", default={}).get("run_id") or run_dir.name,
        "run_dir": str(run_dir),
        "ledger_path": str(ledger_path),
        "ledger_entry_count": len(raw_records),
        "observation_count": len(records),
        "group_count": len(groups),
        "groups": groups,
        "problem_candidates": problem_candidates,
        "requires_triage": requires_triage,
    }
    write_json(run_dir / "manual_observation_summary.json", summary)
    return summary
