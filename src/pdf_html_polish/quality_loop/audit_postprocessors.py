"""Deterministic semantic transforms applied after the audit subprocess."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, NoReturn


class AuditPostprocessorError(ValueError):
    """Raised when a postprocessor input cannot produce an authoritative result."""


def _fail(reason: str) -> NoReturn:
    raise AuditPostprocessorError(reason)


def _canonical_stage_pair(record: dict[str, Any], *, label: str) -> tuple[str, str]:
    values: list[str] = []
    for field in ("raw_stage_path", "polish_stage_path"):
        value = record.get(field)
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            _fail(f"{label}_{field}_invalid")
        canonical = str(Path(value).resolve(strict=False))
        if value != canonical:
            _fail(f"{label}_{field}_not_canonical")
        values.append(canonical)
    return values[0], values[1]


def normalize_converted_audit_article_ids_payload(
    audit: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Return the exact converted-id normalization of an audit payload."""

    if not isinstance(audit, dict):
        _fail("audit_not_object")
    if not isinstance(manifest, dict) or manifest.get("source_kind") != "converted_stage_roots":
        _fail("manifest_source_kind_invalid")
    manifest_articles = manifest.get("articles")
    audit_articles = audit.get("articles")
    if not isinstance(manifest_articles, list):
        _fail("manifest_articles_invalid")
    if not isinstance(audit_articles, list):
        _fail("audit_articles_invalid")

    by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    manifest_ids: set[str] = set()
    for index, article in enumerate(manifest_articles):
        if not isinstance(article, dict):
            _fail(f"manifest_article_invalid:{index}")
        article_id = article.get("article_id")
        if (
            not isinstance(article_id, str)
            or not article_id
            or article_id in manifest_ids
        ):
            _fail(f"manifest_article_id_invalid:{index}")
        artifact_hint = article.get("artifact_hint")
        if artifact_hint is not None and not isinstance(artifact_hint, str):
            _fail(f"manifest_artifact_hint_invalid:{article_id}")
        pair = _canonical_stage_pair(article, label=f"manifest_article:{article_id}")
        if pair in by_pair:
            _fail(f"manifest_stage_pair_duplicate:{article_id}")
        manifest_ids.add(article_id)
        by_pair[pair] = article

    normalized = deepcopy(audit)
    normalized_articles = normalized.get("articles")
    assert isinstance(normalized_articles, list)
    unmatched: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, article in enumerate(normalized_articles):
        if not isinstance(article, dict):
            _fail(f"audit_article_invalid:{index}")
        article_id = article.get("article")
        if not isinstance(article_id, str) or not article_id:
            _fail(f"audit_article_id_invalid:{index}")
        pair = _canonical_stage_pair(article, label=f"audit_article:{article_id}")
        if pair in seen_pairs:
            _fail(f"audit_stage_pair_duplicate:{article_id}")
        seen_pairs.add(pair)
        manifest_article = by_pair.get(pair)
        if manifest_article is None:
            unmatched.append(
                {
                    "raw_stage_path": pair[0],
                    "polish_stage_path": pair[1],
                }
            )
            continue
        source_article = article.get("source_article")
        if source_article is not None and not isinstance(source_article, str):
            _fail(f"audit_source_article_invalid:{article_id}")
        article["source_article"] = source_article or article_id
        article["article"] = manifest_article["article_id"]
        article["artifact_hint"] = manifest_article.get("artifact_hint")

    normalized["article_count"] = len(normalized_articles)
    normalized.pop("converted_id_normalization_unmatched", None)
    if unmatched:
        normalized["converted_id_normalization_unmatched"] = unmatched
    return normalized
