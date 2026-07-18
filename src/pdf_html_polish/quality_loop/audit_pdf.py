"""PDF map and text extraction helpers for audit diagnostics."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Callable, Pattern, TypeGuard

from pdf_html_polish.artifact_integrity import fingerprint_file
from pdf_html_polish.html_stages import article_name_from_html_stage
from pdf_html_polish.quality_loop.audit_blocks import Block, Defect, diagnostic_text, normalize_ws
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect
from pdf_html_polish.quality_loop.cached_run_state import path_is_link_like


PDF_CITATION_DEST_RE = re.compile(r"^(?:cite|citation|bib)[.:]", re.IGNORECASE)
PDF_DIAG_SECTION_SEQUENCE = ("funding", "supplementary material", "references")
_MAX_PDF_CACHE_RECORD_BYTES = 16 * 1024 * 1024


def _pdf_map_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_pdf_map_article:{key}")
        payload[key] = value
    return payload


def _reject_pdf_map_constant(value: str) -> None:
    raise ValueError(f"nonfinite_pdf_map_value:{value}")


def _cache_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate_pdf_cache_key:{key}")
        payload[key] = value
    return payload


def _cache_value_sha256(value: Any) -> str | None:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PdfDiagnosticSourceError(RuntimeError):
    """Raised when PDF diagnostics cannot bind to one stable source file."""


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(str(Path(path).expanduser())))


def pdf_source_record(pdf_path: Path) -> dict[str, Any] | None:
    """Return exact content identity for one non-link PDF, or None when absent."""

    lexical = _lexical_absolute(pdf_path)
    if any(path_is_link_like(component) for component in (lexical, *lexical.parents)):
        raise PdfDiagnosticSourceError(f"source_pdf_link_like:{lexical}")
    canonical = lexical.resolve(strict=False)
    fingerprint = fingerprint_file(canonical, reject_symlink=True)
    if fingerprint is None:
        if canonical.exists() or path_is_link_like(canonical):
            raise PdfDiagnosticSourceError(f"source_pdf_invalid_or_unstable:{canonical}")
        return None
    return {
        "path": str(canonical),
        "bytes": fingerprint.size,
        "sha256": fingerprint.sha256,
    }


def _canonical_source_path(
    pdf_path: Path,
    source_record: dict[str, Any] | None,
) -> Path:
    return Path(source_record["path"]) if source_record is not None else _lexical_absolute(pdf_path).resolve(strict=False)


def _source_summary(pdf_path: Path, source_record: dict[str, Any] | None) -> dict[str, Any]:
    canonical = _lexical_absolute(pdf_path).resolve(strict=False)
    return {
        "source_pdf_path": str(canonical),
        "source_pdf_present": source_record is not None,
        "source_pdf_bytes": int(source_record["bytes"]) if source_record is not None else 0,
        "source_pdf_sha256": str(source_record["sha256"]) if source_record is not None else "",
    }


def _assert_source_unchanged(
    pdf_path: Path,
    source_before: dict[str, Any] | None,
    *,
    operation: str,
) -> None:
    source_after = pdf_source_record(pdf_path)
    if source_after != source_before:
        raise PdfDiagnosticSourceError(f"source_pdf_changed_during_{operation}:{pdf_path}")


def _summary_matches_source(
    summary: dict[str, Any],
    source_record: dict[str, Any],
) -> bool:
    return (
        summary.get("source_pdf_path") == source_record["path"]
        and summary.get("source_pdf_present") is True
        and type(summary.get("source_pdf_bytes")) is int
        and summary.get("source_pdf_bytes") == source_record["bytes"]
        and summary.get("source_pdf_sha256") == source_record["sha256"]
    )


_TEXT_CACHE_VALUE_KEYS = frozenset({"text", "summary"})
_TEXT_CACHE_SUMMARY_KEYS = frozenset(
    {
        "pdf_diagnostics_enabled",
        "source_pdf_path",
        "source_pdf_present",
        "source_pdf_bytes",
        "source_pdf_sha256",
        "source_pdf_origin",
        "pdf_text_status",
        "pdf_text_chars",
        "pdf_text_error",
        "pdf_text_cache_status",
    }
)
_LINK_CACHE_SUMMARY_KEYS = frozenset(
    {
        "pdf_link_text_status",
        "pdf_link_count",
        "pdf_citation_dest_links",
        "pdf_author_year_link_labels",
        "pdf_citation_link_samples",
        "pdf_link_text_error",
        "source_pdf_path",
        "source_pdf_present",
        "source_pdf_bytes",
        "source_pdf_sha256",
        "pdf_link_cache_status",
    }
)
_LINK_CACHE_SAMPLE_KEYS = frozenset({"page", "dest", "text"})


def _is_nonnegative_int(value: Any) -> TypeGuard[int]:
    return type(value) is int and value >= 0


def _is_optional_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _valid_cached_text_value(
    value: Any,
    source_record: dict[str, Any],
    *,
    source_origin: str,
) -> bool:
    if not isinstance(value, dict) or set(value) != _TEXT_CACHE_VALUE_KEYS:
        return False
    text = value.get("text")
    summary = value.get("summary")
    if (
        not isinstance(text, str)
        or not isinstance(summary, dict)
        or set(summary) != _TEXT_CACHE_SUMMARY_KEYS
        or not _summary_matches_source(summary, source_record)
    ):
        return False
    status = summary.get("pdf_text_status")
    return (
        summary.get("pdf_diagnostics_enabled") is True
        and summary.get("source_pdf_origin") == source_origin
        and isinstance(status, str)
        and bool(status)
        and type(summary.get("pdf_text_chars")) is int
        and summary.get("pdf_text_chars") == len(text)
        and _is_optional_string(summary.get("pdf_text_error"))
        and summary.get("pdf_text_cache_status") == "miss"
    )


def _valid_link_sample(sample: Any) -> bool:
    return (
        isinstance(sample, dict)
        and set(sample) == _LINK_CACHE_SAMPLE_KEYS
        and type(sample.get("page")) is int
        and sample["page"] > 0
        and isinstance(sample.get("dest"), str)
        and bool(sample["dest"])
        and isinstance(sample.get("text"), str)
    )


def _valid_cached_link_summary(
    summary: Any,
    source_record: dict[str, Any],
    *,
    sample_limit: int,
) -> bool:
    if (
        not isinstance(summary, dict)
        or set(summary) != _LINK_CACHE_SUMMARY_KEYS
        or not _summary_matches_source(summary, source_record)
    ):
        return False
    status = summary.get("pdf_link_text_status")
    link_count = summary.get("pdf_link_count")
    citation_count = summary.get("pdf_citation_dest_links")
    author_year_count = summary.get("pdf_author_year_link_labels")
    samples = summary.get("pdf_citation_link_samples")
    return (
        isinstance(status, str)
        and bool(status)
        and _is_nonnegative_int(link_count)
        and _is_nonnegative_int(citation_count)
        and citation_count <= link_count
        and _is_nonnegative_int(author_year_count)
        and author_year_count <= citation_count
        and isinstance(samples, list)
        and len(samples) <= min(citation_count, sample_limit)
        and all(_valid_link_sample(sample) for sample in samples)
        and _is_optional_string(summary.get("pdf_link_text_error"))
        and summary.get("pdf_link_cache_status") == "miss"
    )


def source_pdf_path(raw_path: Path, *, pdf_source_stage: str) -> Path:
    return raw_path.parent / pdf_source_stage


def article_name_from_stage(stage_path: Path) -> str:
    return article_name_from_html_stage(stage_path)


def first_path_value(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        for key in ("pdf_path", "source_pdf_path", "path"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    if isinstance(value, list):
        for item in value:
            candidate = first_path_value(item)
            if candidate:
                return candidate
    return None


def pdf_path_from_map_record(record: Any) -> Path | None:
    if isinstance(record, str) and record:
        return Path(record).expanduser()
    if not isinstance(record, dict):
        return None
    for key in ("pdf_path", "source_pdf_path", "path"):
        candidate = record.get(key)
        if isinstance(candidate, str) and candidate:
            return Path(candidate).expanduser()
    for key in ("exact_matches", "fuzzy_matches", "matches"):
        candidate = first_path_value(record.get(key))
        if candidate:
            return Path(candidate).expanduser()
    return None


def load_pdf_map(pdf_map_path: Path) -> dict[str, Path]:
    data = json.loads(
        pdf_map_path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=_pdf_map_object_without_duplicates,
        parse_constant=_reject_pdf_map_constant,
    )
    if isinstance(data, dict) and not any(key in data for key in ("items", "articles", "records")):
        return {
            str(article): path
            for article, value in data.items()
            if (path := pdf_path_from_map_record(value)) is not None
        }

    if isinstance(data, dict):
        records = data.get("items") or data.get("articles") or data.get("records") or []
    else:
        records = data

    pdf_map: dict[str, Path] = {}
    if not isinstance(records, list):
        return pdf_map
    seen_articles: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        article = record.get("article")
        if not isinstance(article, str) or not article:
            continue
        if article in seen_articles:
            raise ValueError(f"duplicate_pdf_map_article:{article}")
        seen_articles.add(article)
        pdf_path = pdf_path_from_map_record(record)
        if pdf_path is not None:
            pdf_map[article] = pdf_path
    return pdf_map


def extract_pdf_text(pdf_path: Path) -> tuple[str, str, str | None]:
    if not pdf_path.is_file():
        return "missing", "", None

    errors: list[str] = []
    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        try:
            return "pymupdf", "\n".join(page.get_text("text") for page in doc), None
        finally:
            doc.close()
    except ImportError as exc:
        errors.append(f"pymupdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pymupdf failed: {exc}")

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return "pypdf", "\n".join(page.extract_text() or "" for page in reader.pages), None
    except ImportError as exc:
        errors.append(f"pypdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pypdf failed: {exc}")

    return "unavailable", "", "; ".join(errors)


def pdf_citation_link_summary(
    pdf_path: Path,
    *,
    author_year_text_re: Pattern[str],
    sample_limit: int = 12,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "pdf_link_text_status": "disabled",
        "pdf_link_count": 0,
        "pdf_citation_dest_links": 0,
        "pdf_author_year_link_labels": 0,
        "pdf_citation_link_samples": [],
        "pdf_link_text_error": None,
    }
    if not pdf_path.is_file():
        summary["pdf_link_text_status"] = "missing"
        return summary
    try:
        import fitz
    except ImportError as exc:
        summary["pdf_link_text_status"] = "pymupdf_unavailable"
        summary["pdf_link_text_error"] = str(exc)
        return summary

    samples: list[dict[str, Any]] = []
    try:
        doc = fitz.open(str(pdf_path))
        try:
            for page_index, page in enumerate(doc):
                try:
                    links = page.get_links()
                except Exception:
                    continue
                summary["pdf_link_count"] += len(links)
                for link in links:
                    dest = str(link.get("nameddest") or "")
                    if not PDF_CITATION_DEST_RE.match(dest):
                        continue
                    summary["pdf_citation_dest_links"] += 1
                    text = ""
                    try:
                        rect = fitz.Rect(link["from"])
                        text = normalize_ws(page.get_textbox(rect) or "")
                    except Exception:
                        text = ""
                    if author_year_text_re.search(text):
                        summary["pdf_author_year_link_labels"] += 1
                    if len(samples) < sample_limit:
                        samples.append({"page": page_index + 1, "dest": dest, "text": text})
        finally:
            doc.close()
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        summary["pdf_link_text_status"] = "failed"
        summary["pdf_link_text_error"] = str(exc)
        return summary

    summary["pdf_link_text_status"] = "pymupdf"
    summary["pdf_citation_link_samples"] = samples
    return summary


def _load_pdf_link_summary_for_source(
    pdf_path: Path,
    *,
    source_before: dict[str, Any] | None,
    author_year_text_re: Pattern[str],
    sample_limit: int,
    pdf_citation_link_summary_func: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        summary = pdf_citation_link_summary_func(
            pdf_path,
            author_year_text_re=author_year_text_re,
            sample_limit=sample_limit,
        )
    finally:
        _assert_source_unchanged(pdf_path, source_before, operation="link_extraction")
    result = dict(summary)
    result.update(_source_summary(pdf_path, source_before))
    return result


def load_pdf_link_summary(
    pdf_path: Path,
    *,
    author_year_text_re: Pattern[str],
    sample_limit: int = 12,
    pdf_citation_link_summary_func: Callable[..., dict[str, Any]] = pdf_citation_link_summary,
) -> dict[str, Any]:
    """Analyze PDF links and attest the exact source bytes used."""

    source_before = pdf_source_record(pdf_path)
    pdf_path = _canonical_source_path(pdf_path, source_before)
    return _load_pdf_link_summary_for_source(
        pdf_path,
        source_before=source_before,
        author_year_text_re=author_year_text_re,
        sample_limit=sample_limit,
        pdf_citation_link_summary_func=pdf_citation_link_summary_func,
    )


def _load_pdf_diagnostic_text_for_source(
    pdf_path: Path,
    pdf_text_override: str | None,
    *,
    pdf_origin: str,
    source_before: dict[str, Any] | None,
    extract_pdf_text_func: Callable[[Path], tuple[str, str, str | None]] = extract_pdf_text,
) -> tuple[str, dict[str, Any]]:
    source_summary = _source_summary(pdf_path, source_before)
    try:
        if pdf_text_override is not None:
            return pdf_text_override, {
                "pdf_diagnostics_enabled": True,
                **source_summary,
                "source_pdf_origin": pdf_origin,
                "pdf_text_status": "override",
                "pdf_text_chars": len(pdf_text_override),
                "pdf_text_error": None,
            }

        status, text, error = extract_pdf_text_func(pdf_path)
        return text, {
            "pdf_diagnostics_enabled": True,
            **source_summary,
            "source_pdf_origin": pdf_origin,
            "pdf_text_status": status,
            "pdf_text_chars": len(text),
            "pdf_text_error": error,
        }
    finally:
        _assert_source_unchanged(pdf_path, source_before, operation="text_extraction")


def load_pdf_diagnostic_text(
    raw_path: Path,
    pdf_text_override: str | None,
    *,
    pdf_source_stage: str,
    pdf_path_override: Path | None = None,
    extract_pdf_text_func: Callable[[Path], tuple[str, str, str | None]] = extract_pdf_text,
) -> tuple[str, dict[str, Any]]:
    pdf_path = pdf_path_override or source_pdf_path(raw_path, pdf_source_stage=pdf_source_stage)
    pdf_origin = "map" if pdf_path_override is not None else "stage"
    source_before = pdf_source_record(pdf_path)
    pdf_path = _canonical_source_path(pdf_path, source_before)
    return _load_pdf_diagnostic_text_for_source(
        pdf_path,
        pdf_text_override,
        pdf_origin=pdf_origin,
        source_before=source_before,
        extract_pdf_text_func=extract_pdf_text_func,
    )


def phrase_positions(text: str, phrases: tuple[str, ...]) -> dict[str, int]:
    return {phrase: text.find(phrase) for phrase in phrases}


def section_order_pdf_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
    *,
    references_heading_re: Pattern[str],
    stage: str,
) -> list[Defect]:
    pdf_norm = diagnostic_text(pdf_text)
    polish_norm = diagnostic_text(polish_html)
    pdf_pos = phrase_positions(pdf_norm, PDF_DIAG_SECTION_SEQUENCE)
    polish_pos = phrase_positions(polish_norm, PDF_DIAG_SECTION_SEQUENCE)

    pdf_has_expected_order = (
        pdf_pos["funding"] != -1
        and pdf_pos["supplementary material"] != -1
        and pdf_pos["references"] != -1
        and pdf_pos["funding"] < pdf_pos["supplementary material"] < pdf_pos["references"]
    )
    polish_has_interleaved_refs = (
        polish_pos["funding"] != -1
        and polish_pos["supplementary material"] != -1
        and polish_pos["references"] != -1
        and polish_pos["funding"] < polish_pos["references"] < polish_pos["supplementary material"]
    )
    if not (pdf_has_expected_order and polish_has_interleaved_refs):
        return []

    ref_block = next((block for block in polish_blocks if references_heading_re.match(block.text)), None)
    return [
        make_defect(
            defect_id="P24",
            cc_class="CC-13/CC-14",
            check="PDF text layer suggests end-section order differs from polish",
            severity="warning",
            block=ref_block,
            snippet="PDF order: FUNDING -> SUPPLEMENTARY MATERIAL -> REFERENCES; polish order: FUNDING -> REFERENCES -> SUPPLEMENTARY MATERIAL",
            stage=stage,
            hypothesis="Marker or post-processing interleaved a two-column terminal section with the bibliography.",
            proposed_fix_layer="PDF-aware EN polish diagnostics and end-section ordering repair",
            regression_test="When PDF text has funding/supplementary material before references, audit warns if polish places references between them.",
            extra={"pdf_positions": pdf_pos, "polish_positions": polish_pos},
        )
    ]


def pdf_text_layer_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
    *,
    references_heading_re: Pattern[str],
    stage: str,
) -> list[Defect]:
    if not pdf_text.strip():
        return []
    return section_order_pdf_defects(
        pdf_text,
        polish_html,
        polish_blocks,
        references_heading_re=references_heading_re,
        stage=stage,
    )


class PdfDiagnosticsCache:
    """Small filesystem cache for expensive PDF audit diagnostics."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        pdf_source_stage: str,
        author_year_text_re: Pattern[str],
        extract_pdf_text_func: Callable[[Path], tuple[str, str, str | None]] = extract_pdf_text,
        pdf_citation_link_summary_func: Callable[..., dict[str, Any]] = pdf_citation_link_summary,
        author_year_cache_key: str = "AUTHOR_YEAR_TEXT_RE:v1",
    ) -> None:
        cache_dir = _lexical_absolute(cache_dir)
        if any(path_is_link_like(component) for component in (cache_dir, *cache_dir.parents)):
            raise PdfDiagnosticSourceError(f"pdf_cache_dir_link_like:{cache_dir}")
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir.resolve(strict=True)
        self.pdf_source_stage = pdf_source_stage
        self.extract_pdf_text_func = extract_pdf_text_func
        self.pdf_citation_link_summary_func = pdf_citation_link_summary_func
        self.author_year_text_re = author_year_text_re
        self.author_year_cache_key = author_year_cache_key
        self._lock = threading.Lock()

    def _key(self, pdf_path: Path, *, kind: str, extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
        source_record = pdf_source_record(pdf_path)
        if source_record is None:
            return None
        return {
            "version": 2,
            "kind": kind,
            "source_pdf": source_record,
            "extra": extra or {},
        }

    def _path_for_key(self, key: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _load(self, key: dict[str, Any]) -> Any | None:
        path = self._path_for_key(key)
        with self._lock:
            if path_is_link_like(path) or not path.is_file():
                return None
            try:
                if path.stat().st_size > _MAX_PDF_CACHE_RECORD_BYTES:
                    return None
                data = json.loads(
                    path.read_text(encoding="utf-8"),
                    object_pairs_hook=_cache_object_without_duplicates,
                    parse_constant=_reject_pdf_map_constant,
                )
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                return None
        if not isinstance(data, dict) or set(data) != {"key", "value", "value_sha256"}:
            return None
        value = data.get("value")
        value_sha256 = data.get("value_sha256")
        if (
            data.get("key") != key
            or not isinstance(value_sha256, str)
            or value_sha256 != _cache_value_sha256(value)
        ):
            return None
        return value

    def _store(self, key: dict[str, Any], value: Any) -> None:
        path = self._path_for_key(key)
        value_sha256 = _cache_value_sha256(value)
        if value_sha256 is None:
            return
        payload = {"key": key, "value": value, "value_sha256": value_sha256}
        text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        with self._lock:
            temporary: Path | None = None
            try:
                if path_is_link_like(path) or (path.exists() and not path.is_file()):
                    return
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    prefix=f".{path.name}.",
                    suffix=".tmp",
                    dir=self.cache_dir,
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    handle.write(text)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            except OSError:
                pass
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass

    def load_text(
        self,
        raw_path: Path,
        pdf_text_override: str | None,
        pdf_path_override: Path | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if pdf_text_override is not None:
            text, summary = load_pdf_diagnostic_text(
                raw_path,
                pdf_text_override,
                pdf_source_stage=self.pdf_source_stage,
                pdf_path_override=pdf_path_override,
                extract_pdf_text_func=self.extract_pdf_text_func,
            )
            summary["pdf_text_cache_status"] = "override"
            return text, summary
        pdf_path = pdf_path_override or source_pdf_path(raw_path, pdf_source_stage=self.pdf_source_stage)
        source_origin = "map" if pdf_path_override is not None else "stage"
        key = self._key(
            pdf_path,
            kind="text",
            extra={
                "extractor": "extract_pdf_text:v1",
                "source_pdf_origin": source_origin,
            },
        )
        if key is None:
            text, summary = load_pdf_diagnostic_text(
                raw_path,
                pdf_text_override,
                pdf_source_stage=self.pdf_source_stage,
                pdf_path_override=pdf_path_override,
                extract_pdf_text_func=self.extract_pdf_text_func,
            )
            summary["pdf_text_cache_status"] = "disabled"
            return text, summary
        cached = self._load(key)
        source_record = key["source_pdf"]
        pdf_path = _canonical_source_path(pdf_path, source_record)
        if _valid_cached_text_value(cached, source_record, source_origin=source_origin):
            assert isinstance(cached, dict)
            cached_text = cached["text"]
            cached_summary = cached["summary"]
            assert isinstance(cached_text, str)
            assert isinstance(cached_summary, dict)
            summary = dict(cached_summary)
            summary["pdf_text_cache_status"] = "hit"
            return cached_text, summary
        text, summary = _load_pdf_diagnostic_text_for_source(
            pdf_path,
            pdf_text_override,
            pdf_origin=source_origin,
            source_before=source_record,
            extract_pdf_text_func=self.extract_pdf_text_func,
        )
        if not _summary_matches_source(summary, source_record):
            raise PdfDiagnosticSourceError(f"source_pdf_changed_before_text_cache_store:{pdf_path}")
        summary = dict(summary)
        summary["pdf_text_cache_status"] = "miss"
        value = {"text": text, "summary": summary}
        if not _valid_cached_text_value(value, source_record, source_origin=source_origin):
            raise PdfDiagnosticSourceError(f"pdf_text_cache_value_invalid:{pdf_path}")
        self._store(key, value)
        return text, summary

    def link_summary(self, pdf_path: Path, *, sample_limit: int = 12) -> dict[str, Any]:
        if type(sample_limit) is not int or sample_limit < 0:
            raise ValueError("pdf_link_sample_limit_invalid")
        key = self._key(
            pdf_path,
            kind="links",
            extra={"sample_limit": sample_limit, "author_year_text_re": self.author_year_cache_key},
        )
        if key is None:
            pdf_path = _canonical_source_path(pdf_path, None)
            summary = _load_pdf_link_summary_for_source(
                pdf_path,
                source_before=None,
                author_year_text_re=self.author_year_text_re,
                sample_limit=sample_limit,
                pdf_citation_link_summary_func=self.pdf_citation_link_summary_func,
            )
            summary["pdf_link_cache_status"] = "disabled"
            return summary
        source_record = key["source_pdf"]
        pdf_path = _canonical_source_path(pdf_path, source_record)
        cached = self._load(key)
        if _valid_cached_link_summary(cached, source_record, sample_limit=sample_limit):
            assert isinstance(cached, dict)
            summary = dict(cached)
            summary["pdf_link_cache_status"] = "hit"
            return summary
        summary = _load_pdf_link_summary_for_source(
            pdf_path,
            source_before=source_record,
            author_year_text_re=self.author_year_text_re,
            sample_limit=sample_limit,
            pdf_citation_link_summary_func=self.pdf_citation_link_summary_func,
        )
        summary["pdf_link_cache_status"] = "miss"
        if not _valid_cached_link_summary(
            summary, source_record, sample_limit=sample_limit
        ):
            raise PdfDiagnosticSourceError(f"pdf_link_cache_value_invalid:{pdf_path}")
        self._store(key, summary)
        return summary
