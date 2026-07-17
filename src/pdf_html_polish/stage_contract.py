from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .html_stages import HTML_STAGE_DIR_NAMES, POLISH_STAGE_NAME, RAW_STAGE_NAME
from .quality_loop.run_utils import git_dirty, git_short_head, load_json, now, write_json


RAW_STAGE = RAW_STAGE_NAME
POLISH_STAGE = POLISH_STAGE_NAME
PUBLISH_REPORT_NAME = "converted_stage_publish_report.json"
STAGE_CONTRACT_REPORT_NAME = "stage_contract_report.json"


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _iter_direct_children(path: Path) -> Iterable[Path]:
    try:
        yield from path.iterdir()
    except OSError:
        return


def _iter_html_files(root: Path) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda _error: None):
        base = Path(dirpath)
        for filename in filenames:
            if filename.lower().endswith(".html"):
                yield base / filename


def _stage_dir_has_html(stage_dir: Path) -> bool:
    return any(_iter_html_files(stage_dir))


def find_stage_dirs(roots: Iterable[Path]) -> list[Path]:
    """Return stage directories recognized under converted roots.

    Both the current ``_pdf_html_polish_stages`` and legacy ``_z2m_stages``
    names are supported because the live Zotero converted tree contains older
    runs.
    """

    found: set[Path] = set()
    for raw_root in roots:
        root = _resolve(raw_root)
        if root.is_file():
            if root.parent.name in HTML_STAGE_DIR_NAMES and _stage_dir_has_html(root.parent):
                found.add(root.parent)
            continue
        if not root.exists():
            continue
        if root.name in HTML_STAGE_DIR_NAMES and _stage_dir_has_html(root):
            found.add(root)
            continue
        for dirpath, dirnames, _filenames in os.walk(root, onerror=lambda _error: None):
            for dirname in list(dirnames):
                stage_dir = (Path(dirpath) / dirname).resolve(strict=False)
                if dirname in HTML_STAGE_DIR_NAMES and _stage_dir_has_html(stage_dir):
                    found.add(stage_dir)
    return sorted(found, key=str)


def _article_dir_record(article_dir: Path, stage_dirs: list[Path]) -> dict[str, Any]:
    preferred = sorted(
        stage_dirs,
        key=lambda path: (0 if path.name == "_pdf_html_polish_stages" else 1, str(path)),
    )[0]
    allowed = {
        (preferred / RAW_STAGE).resolve(strict=False),
        (preferred / POLISH_STAGE).resolve(strict=False),
    }
    html_files = sorted(
        (path.resolve(strict=False) for path in _iter_html_files(article_dir)),
        key=str,
    )
    extras = [path for path in html_files if path not in allowed]
    missing = [path for path in sorted(allowed, key=str) if not path.is_file()]
    issues: list[dict[str, Any]] = []
    if len(stage_dirs) > 1:
        issues.append(
            {
                "kind": "multiple_stage_dirs",
                "stage_dirs": [str(path) for path in sorted(stage_dirs, key=str)],
            }
        )
    if missing:
        issues.append({"kind": "missing_canonical_html", "paths": [str(path) for path in missing]})
    if extras:
        issues.append({"kind": "extra_html", "paths": [str(path) for path in extras]})

    return {
        "article_dir": str(article_dir),
        "stage_dir": str(preferred),
        "html_count": len(html_files),
        "expected_html_count": 2,
        "raw_stage_path": str(preferred / RAW_STAGE),
        "polish_stage_path": str(preferred / POLISH_STAGE),
        "extra_html_count": len(extras),
        "extra_html_paths": [str(path) for path in extras],
        "missing_canonical_count": len(missing),
        "missing_canonical_paths": [str(path) for path in missing],
        "status": "pass" if not issues else "fail",
        "issues": issues,
    }


def verify_stage_contract(
    roots: Iterable[Path],
    *,
    out_report: Path | None = None,
) -> dict[str, Any]:
    """Verify that every discovered article stores exactly raw + latest polish HTML."""

    roots = [_resolve(root) for root in roots]
    stage_dirs = find_stage_dirs(roots)
    grouped: dict[Path, list[Path]] = {}
    for stage_dir in stage_dirs:
        grouped.setdefault(stage_dir.parent.resolve(strict=False), []).append(stage_dir)

    articles = [
        _article_dir_record(article_dir, sorted(article_stage_dirs, key=str))
        for article_dir, article_stage_dirs in sorted(grouped.items(), key=lambda item: str(item[0]))
    ]
    failing_articles = [article for article in articles if article["status"] != "pass"]
    report = {
        "generated_at": now(),
        "schema_version": 1,
        "source_roots": [str(root) for root in roots],
        "code_commit": git_short_head(),
        "working_tree_dirty": git_dirty(),
        "stage_dir_count": len(stage_dirs),
        "article_count": len(articles),
        "passing_article_count": len(articles) - len(failing_articles),
        "failing_article_count": len(failing_articles),
        "extra_html_count": sum(int(article["extra_html_count"]) for article in articles),
        "missing_canonical_count": sum(int(article["missing_canonical_count"]) for article in articles),
        "status": "pass" if not failing_articles else "fail",
        "articles": articles,
    }
    if out_report is not None:
        write_json(_resolve(out_report), report)
    return report


def _quality_source_manifest(quality_run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    quality_manifest = load_json(quality_run_dir / "manifest.json")
    source_run_dir_value = quality_manifest.get("source_run_dir")
    if not source_run_dir_value:
        raise ValueError(
            "Quality manifest has no source_run_dir. Run observe in converted-raw repolish mode first."
        )
    source_run_dir = _resolve(Path(str(source_run_dir_value)))
    source_manifest = load_json(source_run_dir / "manifest.json")
    return quality_manifest, source_manifest


def _source_article_by_id(source_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for article in source_manifest.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article_id") or article.get("article") or "")
        if article_id:
            if article_id in by_id:
                raise ValueError(
                    f"Source manifest contains duplicate article id: {article_id!r}."
                )
            by_id[article_id] = article
    return by_id


def _quality_article_ids(quality_manifest: dict[str, Any]) -> list[str]:
    article_ids: list[str] = []
    for article in quality_manifest.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or article.get("article_id") or "")
        if article_id:
            if article_id in article_ids:
                raise ValueError(
                    f"Quality manifest contains duplicate article id: {article_id!r}."
                )
            article_ids.append(article_id)
    return article_ids


def _backup_path_for(backup_dir: Path, path: Path) -> Path:
    drive = path.drive.replace(":", "")
    parts = [part for part in path.parts if part not in (path.anchor, path.drive, "\\")]
    return backup_dir / drive / Path(*parts)


def _copy_file_atomic(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _backup_file(path: Path, backup_dir: Path) -> Path | None:
    if not path.is_file():
        return None
    target = _backup_path_for(backup_dir, path)
    _copy_file_atomic(path, target)
    return target


def _manifest_path_value(article: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = article.get(key)
        if value:
            return str(value)
    return ""


def _stage_extra_html_paths(stage_dir: Path) -> list[Path]:
    article_dir = stage_dir.parent
    allowed = {
        (stage_dir / RAW_STAGE).absolute(),
        (stage_dir / POLISH_STAGE).absolute(),
    }
    return sorted(
        (
            path.absolute()
            for path in _iter_html_files(article_dir)
            if path.absolute() not in allowed
        ),
        key=str,
    )


def publish_latest_polish_from_quality_run(
    quality_run_dir: Path,
    *,
    converted_roots: Iterable[Path] = (),
    apply: bool = False,
    prune_extra_html: bool = True,
    backup_dir: Path | None = None,
    out_report: Path | None = None,
) -> dict[str, Any]:
    """Publish final audited polish HTML back into the source converted stages.

    The source ``01.en.raw.html`` is never modified.  The final
    ``audit_tree/<article>/02.en.polish.html`` produced by the quality loop is
    copied over the matching source ``02.en.polish.html``.  Extra HTML files
    under the same article directory are reported and, with ``apply=True`` and
    ``prune_extra_html=True``, removed.
    """

    quality_run_dir = _resolve(quality_run_dir)
    quality_audit_root = _resolve(quality_run_dir / "audit_tree")
    converted_roots = [_resolve(root) for root in converted_roots]
    resolved_backup_dir = _resolve(backup_dir) if backup_dir is not None else None
    quality_manifest, source_manifest = _quality_source_manifest(quality_run_dir)
    source_by_id = _source_article_by_id(source_manifest)

    article_ids = _quality_article_ids(quality_manifest)
    records: list[dict[str, Any]] = []
    copied = 0
    skipped = 0
    removed = 0
    missing = 0
    out_of_scope = 0
    pending: list[tuple[dict[str, Any], Path, Path, list[Path]]] = []

    for article_id in article_ids:
        source_article = source_by_id.get(article_id)
        audited_polish = _resolve(quality_audit_root / article_id / POLISH_STAGE)
        if source_article is None:
            missing += 1
            records.append(
                {
                    "article": article_id,
                    "status": "missing_source_manifest_article",
                    "audited_polish_path": str(audited_polish),
                }
            )
            continue

        raw_path_value = _manifest_path_value(source_article, "raw_stage_path")
        target_polish_value = _manifest_path_value(source_article, "source_polish_path", "polish_stage_path")
        if not raw_path_value or not target_polish_value:
            missing += 1
            records.append(
                {
                    "article": article_id,
                    "status": "missing_source_stage_paths",
                    "raw_stage_path": raw_path_value,
                    "target_polish_path": target_polish_value,
                    "audited_polish_path": str(audited_polish),
                }
            )
            continue

        raw_path = _resolve(Path(raw_path_value))
        target_polish = _resolve(Path(target_polish_value))
        stage_dir = raw_path.parent
        if converted_roots and not any(_is_relative_to(raw_path, root) for root in converted_roots):
            out_of_scope += 1
            records.append(
                {
                    "article": article_id,
                    "status": "outside_converted_roots",
                    "raw_stage_path": str(raw_path),
                    "target_polish_path": str(target_polish),
                }
            )
            continue

        extra_html = _stage_extra_html_paths(stage_dir) if stage_dir.exists() else []
        record: dict[str, Any] = {
            "article": article_id,
            "raw_stage_path": str(raw_path),
            "target_polish_path": str(target_polish),
            "audited_polish_path": str(audited_polish),
            "extra_html_count": len(extra_html),
            "extra_html_paths": [str(path) for path in extra_html],
            "copied": False,
            "removed_extra_html_count": 0,
            "backup_paths": [],
        }

        if not _is_relative_to(audited_polish, quality_audit_root):
            out_of_scope += 1
            record["status"] = "outside_quality_audit_tree"
            records.append(record)
            continue
        if not raw_path.is_file():
            missing += 1
            record["status"] = "missing_raw_stage"
            records.append(record)
            continue
        article_root = stage_dir.parent.resolve(strict=False)
        unsafe_extra_html = [
            path
            for path in extra_html
            if path.is_symlink()
            or not _is_relative_to(path.resolve(strict=False), article_root)
        ]
        if unsafe_extra_html:
            out_of_scope += 1
            record["status"] = "unsafe_extra_html_path"
            record["unsafe_extra_html_paths"] = [str(path) for path in unsafe_extra_html]
            records.append(record)
            continue
        if not audited_polish.is_file():
            missing += 1
            record["status"] = "missing_audited_polish"
            records.append(record)
            continue
        if target_polish.parent != stage_dir:
            missing += 1
            record["status"] = "target_not_beside_raw"
            records.append(record)
            continue

        pending.append((record, audited_polish, target_polish, extra_html))
        records.append(record)

    preflight_complete = missing == 0 and out_of_scope == 0
    if apply and preflight_complete:
        for record, audited_polish, target_polish, extra_html in pending:
            if resolved_backup_dir is not None:
                backup_path = _backup_file(target_polish, resolved_backup_dir)
                if backup_path is not None:
                    record["backup_paths"].append(str(backup_path))
            _copy_file_atomic(audited_polish, target_polish)
            copied += 1
            record["copied"] = True
            if prune_extra_html:
                for extra_path in extra_html:
                    if resolved_backup_dir is not None:
                        backup_path = _backup_file(extra_path, resolved_backup_dir)
                        if backup_path is not None:
                            record["backup_paths"].append(str(backup_path))
                    try:
                        extra_path.unlink()
                    except FileNotFoundError:
                        pass
                    else:
                        removed += 1
                        record["removed_extra_html_count"] += 1
            record["status"] = "published"
    elif apply:
        for record, _audited_polish, _target_polish, _extra_html in pending:
            record["status"] = "blocked_by_preflight"
    else:
        skipped = len(pending)
        for record, _audited_polish, _target_polish, _extra_html in pending:
            record["status"] = "dry_run"

    affected_roots = [
        Path(record["raw_stage_path"]).parent.parent
        for record in records
        if record.get("raw_stage_path") and record.get("status") != "outside_converted_roots"
    ]
    contract_report = verify_stage_contract(affected_roots) if affected_roots else {
        "status": "pass",
        "article_count": 0,
        "failing_article_count": 0,
    }
    contract_verification_status = contract_report.get("status")
    stage_contract_status = "pass" if preflight_complete and contract_verification_status == "pass" else "fail"
    report = {
        "generated_at": now(),
        "schema_version": 1,
        "mode": "apply" if apply else "dry_run",
        "quality_run_dir": str(quality_run_dir),
        "quality_code_commit": quality_manifest.get("code_commit"),
        "quality_working_tree_dirty": quality_manifest.get("working_tree_dirty"),
        "current_code_commit": git_short_head(),
        "current_working_tree_dirty": git_dirty(),
        "converted_roots": [str(root) for root in converted_roots],
        "prune_extra_html": prune_extra_html,
        "backup_dir": str(resolved_backup_dir) if resolved_backup_dir is not None else "",
        "article_count": len(article_ids),
        "published_count": copied,
        "dry_run_count": skipped,
        "missing_count": missing,
        "outside_scope_count": out_of_scope,
        "extra_html_count": sum(int(record.get("extra_html_count") or 0) for record in records),
        "removed_extra_html_count": removed,
        "stage_contract_status": stage_contract_status,
        "stage_contract_verification_status": contract_verification_status,
        "stage_contract_failing_article_count": contract_report.get("failing_article_count"),
        "records": records,
    }
    if out_report is not None:
        write_json(_resolve(out_report), report)
    else:
        write_json(quality_run_dir / PUBLISH_REPORT_NAME, report)
    return report


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
