"""Source-PDF discovery helpers for quality-loop diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import json
import os
import re
from pathlib import Path
from typing import Any

from pdf_html_polish.html_stages import article_dir_from_html_stage, is_html_stage_dir_name


PDF_TITLE_SEPARATOR_RE = re.compile("[^0-9A-Za-z\u0400-\u04FF]+")


def _load_json(path: Path, default: Any | None = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def manifest_article_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    articles: dict[str, dict[str, Any]] = {}
    for article in manifest.get("articles") or []:
        if not isinstance(article, dict):
            continue
        article_id = article.get("article_id") or article.get("article")
        if article_id:
            articles[str(article_id)] = article
    return articles


def manifest_article_for(manifest: dict[str, Any], article: str) -> dict[str, Any] | None:
    article = str(article or "")
    for item in manifest.get("articles") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("article_id") or "") == article or str(item.get("article") or "") == article:
            return item
    return None


def article_dir_from_stage(stage_path: Path) -> Path:
    return article_dir_from_html_stage(stage_path)


def configured_path_prefix_pairs(repo_root: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = [
        ("/pdf_html_polish_repo", str(repo_root)),
        ("/data/html", r"D:\Elvis_projects\Zotero_automatization\data\html"),
        ("/zotero_roots/pc_zotero", r"C:\PC\Zotero"),
        ("/zotero_roots/user_zotero", r"C:\Users\ELVIS_NIX\Zotero"),
    ]
    for env_name in ("HTML_DOCKER_MOUNT_PREFIX_MAP", "ZOTERO_PATH_PREFIX_MAP"):
        for item in os.environ.get(env_name, "").split(";"):
            if "=" not in item:
                continue
            left, right = (part.strip() for part in item.split("=", 1))
            if left and right:
                pairs.append((left, right))
                pairs.append((right, left))
    return pairs


def host_path_candidates(value: str, *, repo_root: Path) -> list[Path]:
    raw = value.strip()
    if not raw:
        return []
    candidates = [Path(raw).resolve(strict=False)]
    normalized = raw.replace("\\", "/")
    for source_prefix, target_prefix in configured_path_prefix_pairs(repo_root):
        source_norm = source_prefix.replace("\\", "/").rstrip("/")
        if normalized == source_norm or normalized.startswith(source_norm + "/"):
            suffix = normalized[len(source_norm) :].lstrip("/")
            candidates.append((Path(target_prefix) / Path(*suffix.split("/"))).resolve(strict=False))
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def path_text_variants(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    variants = [raw]
    try:
        repaired = raw.encode("cp1251").decode("utf-8")
    except UnicodeError:
        repaired = ""
    if repaired and repaired not in variants:
        variants.append(repaired)
    return variants


def existing_path_candidates(value: Any, *, repo_root: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    for variant in path_text_variants(value):
        for candidate in host_path_candidates(variant, repo_root=repo_root):
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.is_file():
                candidates.append(candidate)
    return candidates


def collect_pdf_path_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_lower = str(key).lower()
            appended = False
            if isinstance(nested, str) and (
                key_lower in {"source_pdf", "source_pdf_path", "pdf_path", "overlay_source_pdf", "source_path", "path"}
                or "pdf" in key_lower
            ):
                if nested.lower().split("?", 1)[0].endswith(".pdf"):
                    found.append(nested)
                    appended = True
            if not appended:
                found.extend(collect_pdf_path_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(collect_pdf_path_strings(nested))
    elif isinstance(value, str) and value.lower().split("?", 1)[0].endswith(".pdf"):
        found.append(value)
    return found


def source_export_dirs_from_stage_related_path(
    value: Any,
    *,
    raw_stage: str,
    polish_stage: str,
) -> list[Path]:
    if not value:
        return []
    path = Path(str(value)).resolve(strict=False)
    if path.name in {raw_stage, polish_stage} or is_html_stage_dir_name(path.parent.name):
        article_dir = article_dir_from_stage(path)
    else:
        article_dir = path
    parts = list(article_dir.parts)
    dirs: list[Path] = []
    for marker in ("source_exports", "converted", "final_exports"):
        if marker not in parts:
            continue
        idx = parts.index(marker)
        after = parts[idx + 1 :]
        if len(after) < 3:
            continue
        dirs.append(Path(*parts[:idx], "source_exports", *after[:3]).resolve(strict=False))
    return dirs


def pdf_candidates_from_source_export_dir(source_dir: Path, *, repo_root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not source_dir.is_dir():
        return candidates
    for json_path in sorted([source_dir / "manifest.json", *source_dir.glob("*_meta.json")], key=str):
        if not json_path.is_file():
            continue
        data = _load_json(json_path, default={})
        for pdf_value in collect_pdf_path_strings(data):
            for host_path in host_path_candidates(pdf_value, repo_root=repo_root):
                candidates.append(
                    {
                        "path": str(host_path),
                        "exists": host_path.is_file(),
                        "source": str(json_path),
                        "original_path": pdf_value,
                    }
                )
    return candidates


def zotero_root_paths(*, repo_root: Path) -> list[Path]:
    roots: list[Path] = []
    for source_prefix, target_prefix in configured_path_prefix_pairs(repo_root):
        if "zotero" not in source_prefix.lower() and "zotero" not in target_prefix.lower():
            continue
        root = Path(target_prefix).resolve(strict=False)
        if root not in roots:
            roots.append(root)
    return roots


def normalize_pdf_title_text(value: str) -> str:
    text = PDF_TITLE_SEPARATOR_RE.sub(" ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def _title_match_tokens(value: str) -> list[str]:
    return [token for token in normalize_pdf_title_text(value).split() if len(token) >= 4]


def article_title_fragments(article: str, manifest_article: dict[str, Any]) -> list[str]:
    fragments: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "")
        if not text:
            return
        stem = Path(text).stem if "." in Path(text).name else text
        stem = re.sub(r"^Zotero_[^_]+_[^_]+_[A-Z0-9]{6,10}(?:_\d+){1,3}_", "", stem)
        stem = re.sub(r"^[^-_]+(?:_[^_]+){0,4}_-_\d{4}[a-z]?_-_", "", stem)
        stem = stem.replace("_", " ")
        normalized = normalize_pdf_title_text(stem)
        if len(normalized) >= 32 and normalized not in fragments:
            fragments.append(normalized)

    add(article)
    for key in (
        "article",
        "article_id",
        "source_run_article",
        "raw_stage_path",
        "polish_stage_path",
        "source_polish_path",
        "polish_path",
        "restored_image_source",
    ):
        add(manifest_article.get(key))
    return fragments


@lru_cache(maxsize=8)
def _zotero_pdf_index(repo_root_text: str) -> tuple[str, ...]:
    repo_root = Path(repo_root_text)
    paths: list[str] = []
    seen: set[str] = set()
    for root in zotero_root_paths(repo_root=repo_root):
        if not root.is_dir():
            continue
        storage_roots = [root / "storage", *root.glob("*/storage")]
        for storage_root in storage_roots:
            if not storage_root.is_dir():
                continue
            try:
                iterator = storage_root.glob("*/*.pdf")
                for pdf_path in iterator:
                    resolved = str(pdf_path.resolve(strict=False))
                    if resolved not in seen and pdf_path.is_file():
                        seen.add(resolved)
                        paths.append(resolved)
            except OSError:
                continue
    return tuple(sorted(paths))


def title_fragment_matches_pdf(fragment: str, pdf_stem: str) -> tuple[bool, float]:
    fragment_norm = normalize_pdf_title_text(fragment)
    pdf_norm = normalize_pdf_title_text(pdf_stem)
    if len(fragment_norm) >= 32 and fragment_norm in pdf_norm:
        return True, 1.0
    tokens = _title_match_tokens(fragment_norm)
    if len(tokens) < 6:
        return False, 0.0
    pdf_tokens = _title_match_tokens(pdf_norm)
    if not pdf_tokens:
        return False, 0.0
    matched = 0
    search_start = 0
    for token in tokens:
        found_at = -1
        for index in range(search_start, len(pdf_tokens)):
            pdf_token = pdf_tokens[index]
            if pdf_token.startswith(token) or token.startswith(pdf_token):
                found_at = index
                break
        if found_at >= 0:
            matched += 1
            search_start = found_at + 1
    score = matched / max(1, len(tokens))
    return matched >= 6 and score >= 0.78, round(score, 4)


def pdf_candidates_from_zotero_title(article: str, manifest_article: dict[str, Any], *, repo_root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    fragments = article_title_fragments(article, manifest_article)
    if not fragments:
        return candidates
    for pdf_text in _zotero_pdf_index(str(repo_root.resolve(strict=False))):
        pdf_path = Path(pdf_text)
        for fragment in fragments:
            matched, score = title_fragment_matches_pdf(fragment, pdf_path.stem)
            if not matched:
                continue
            candidates.append(
                {
                    "path": str(pdf_path),
                    "exists": pdf_path.is_file(),
                    "source": "zotero_storage.title_match",
                    "original_path": fragment,
                    "match_score": score,
                }
            )
            break
    candidates.sort(key=lambda item: (-float(item.get("match_score") or 0.0), str(item.get("path"))))
    return candidates[:8]


def attachment_keys_from_article(article: str, manifest_article: dict[str, Any]) -> list[str]:
    keys: list[str] = []

    def add(value: str) -> None:
        if value and value not in keys:
            keys.append(value)

    def looks_like_attachment_key(value: str) -> bool:
        return (
            bool(re.fullmatch(r"[A-Z0-9]{6,10}", value))
            and any(ch.isalpha() for ch in value)
        )

    for token in re.split(r"[_\\/]+", article):
        if looks_like_attachment_key(token):
            add(token)
    for key in ("attachment_key", "zotero_attachment_key", "zotero_key"):
        value = manifest_article.get(key)
        if isinstance(value, str) and looks_like_attachment_key(value):
            add(value)
    for path_key in ("raw_stage_path", "polish_stage_path", "restored_image_source"):
        value = manifest_article.get(path_key)
        if not value:
            continue
        for part in Path(str(value)).parts:
            if looks_like_attachment_key(part):
                add(part)
    return keys


def pdf_candidates_from_zotero_storage(attachment_key: str, *, repo_root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not attachment_key:
        return candidates
    for root in zotero_root_paths(repo_root=repo_root):
        storage_dirs = [root / "storage" / attachment_key]
        if root.is_dir():
            storage_dirs.extend(root.glob(f"*/storage/{attachment_key}"))
        for storage_dir in storage_dirs:
            if not storage_dir.is_dir():
                continue
            for pdf_path in sorted(storage_dir.glob("*.pdf"), key=str):
                candidates.append(
                    {
                        "path": str(pdf_path.resolve(strict=False)),
                        "exists": pdf_path.is_file(),
                        "source": f"zotero_storage.{attachment_key}",
                        "original_path": str(storage_dir.resolve(strict=False)),
                    }
                )
    return candidates


def article_source_pdf_candidates(
    run_dir: Path,
    article: str,
    audit_summary: dict[str, Any],
    manifest_article: dict[str, Any],
    *,
    repo_root: Path,
    raw_stage: str,
    polish_stage: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    visited_runs: set[Path] = set()

    def add_pdf_value(value: Any, source: str) -> None:
        if not value:
            return
        for host_path in host_path_candidates(str(value), repo_root=repo_root):
            candidates.append(
                {
                    "path": str(host_path),
                    "exists": host_path.is_file(),
                    "source": source,
                    "original_path": str(value),
                }
            )

    def add_source_dirs_from_item(item: dict[str, Any]) -> None:
        for key in (
            "article_dir",
            "raw_stage_path",
            "source_polish_path",
            "polish_stage_path",
            "polish_path",
            "restored_image_source",
        ):
            for source_dir in source_export_dirs_from_stage_related_path(
                item.get(key),
                raw_stage=raw_stage,
                polish_stage=polish_stage,
            ):
                candidates.extend(pdf_candidates_from_source_export_dir(source_dir, repo_root=repo_root))

    add_pdf_value(audit_summary.get("source_pdf_path"), "audit_summary.source_pdf_path")
    add_source_dirs_from_item(manifest_article)
    for key in ("source_pdf", "source_pdf_path", "pdf_path", "overlay_source_pdf"):
        add_pdf_value(manifest_article.get(key), f"manifest.{key}")
    for attachment_key in attachment_keys_from_article(article, manifest_article):
        candidates.extend(pdf_candidates_from_zotero_storage(attachment_key, repo_root=repo_root))
    if not any(candidate.get("exists") for candidate in candidates):
        candidates.extend(pdf_candidates_from_zotero_title(article, manifest_article, repo_root=repo_root))

    def visit(source_run: Path) -> None:
        source_run = source_run.resolve(strict=False)
        if source_run in visited_runs:
            return
        visited_runs.add(source_run)
        manifest = _load_json(source_run / "manifest.json", default={})
        item = manifest_article_for(manifest, article) or {}
        if item:
            add_source_dirs_from_item(item)
            for key in ("source_pdf", "source_pdf_path", "pdf_path", "overlay_source_pdf"):
                add_pdf_value(item.get(key), f"{source_run.name}.manifest.{key}")
            for attachment_key in attachment_keys_from_article(article, item):
                candidates.extend(pdf_candidates_from_zotero_storage(attachment_key, repo_root=repo_root))
            if not any(candidate.get("exists") for candidate in candidates):
                candidates.extend(pdf_candidates_from_zotero_title(article, item, repo_root=repo_root))
        nested = manifest.get("source_run_dir")
        if nested:
            visit(Path(str(nested)))

    visit(run_dir)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = f"{candidate.get('path')}|{candidate.get('original_path')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    deduped.sort(key=lambda item: (not bool(item.get("exists")), str(item.get("path"))))
    return deduped[:12]


def write_source_pdf_map_for_run(
    run_dir: Path,
    manifest: dict[str, Any] | None = None,
    *,
    out_path: Path | None = None,
    repo_root: Path,
    raw_stage: str,
    polish_stage: str,
    output_name: str,
) -> dict[str, Any]:
    run_dir = run_dir.resolve(strict=False)
    manifest = manifest or _load_json(run_dir / "manifest.json", default={})
    out_path = out_path or (run_dir / output_name)
    records: list[dict[str, Any]] = []
    mapped: dict[str, dict[str, Any]] = {}
    for item in manifest.get("articles") or []:
        if not isinstance(item, dict):
            continue
        article = str(item.get("article_id") or item.get("article") or "")
        if not article:
            continue
        candidates = article_source_pdf_candidates(
            run_dir,
            article,
            {},
            item,
            repo_root=repo_root,
            raw_stage=raw_stage,
            polish_stage=polish_stage,
        )
        selected = next((candidate for candidate in candidates if candidate.get("exists")), None)
        record = {
            "article": article,
            "source_article": item.get("article"),
            "pdf_path": selected.get("path") if selected else "",
            "source": selected.get("source") if selected else "",
            "exists": bool(selected),
            "candidate_count": len(candidates),
            "candidates": candidates,
        }
        records.append(record)
        if selected:
            mapped[article] = record

    report = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "status": "ready" if mapped else "empty",
        "article_count": len(records),
        "mapped_count": len(mapped),
        "unmapped_count": len(records) - len(mapped),
        "records": records,
    }
    _write_json(out_path, report)
    return report
