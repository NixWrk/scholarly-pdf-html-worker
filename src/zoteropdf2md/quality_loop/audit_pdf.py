"""PDF map and text extraction helpers for audit diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Any, Callable, Pattern

from zoteropdf2md.html_stages import article_name_from_html_stage
from zoteropdf2md.quality_loop.audit_blocks import normalize_ws


PDF_CITATION_DEST_RE = re.compile(r"^(?:cite|citation|bib)[.:]", re.IGNORECASE)


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
    data = json.loads(pdf_map_path.read_text(encoding="utf-8-sig"))
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
    for record in records:
        if not isinstance(record, dict):
            continue
        article = record.get("article")
        if not isinstance(article, str) or not article:
            continue
        pdf_path = pdf_path_from_map_record(record)
        if pdf_path is not None:
            pdf_map[article] = pdf_path
    return pdf_map


def extract_pdf_text(pdf_path: Path) -> tuple[str, str, str | None]:
    if not pdf_path.is_file():
        return "missing", "", None

    errors: list[str] = []
    try:
        import fitz  # type: ignore[import-not-found]

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
        from pypdf import PdfReader  # type: ignore[import-not-found]

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
        import fitz  # type: ignore[import-not-found]
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
    if pdf_text_override is not None:
        return pdf_text_override, {
            "pdf_diagnostics_enabled": True,
            "source_pdf_path": str(pdf_path),
            "source_pdf_present": pdf_path.is_file(),
            "source_pdf_origin": pdf_origin,
            "pdf_text_status": "override",
            "pdf_text_chars": len(pdf_text_override),
            "pdf_text_error": None,
        }

    status, text, error = extract_pdf_text_func(pdf_path)
    return text, {
        "pdf_diagnostics_enabled": True,
        "source_pdf_path": str(pdf_path),
        "source_pdf_present": pdf_path.is_file(),
        "source_pdf_origin": pdf_origin,
        "pdf_text_status": status,
        "pdf_text_chars": len(text),
        "pdf_text_error": error,
    }


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
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_source_stage = pdf_source_stage
        self.extract_pdf_text_func = extract_pdf_text_func
        self.pdf_citation_link_summary_func = pdf_citation_link_summary_func
        self.author_year_text_re = author_year_text_re
        self.author_year_cache_key = author_year_cache_key
        self._lock = threading.Lock()

    def _key(self, pdf_path: Path, *, kind: str, extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not pdf_path.is_file():
            return None
        stat = pdf_path.stat()
        return {
            "version": 1,
            "kind": kind,
            "path": str(pdf_path.resolve(strict=False)),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "extra": extra or {},
        }

    def _path_for_key(self, key: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _load(self, key: dict[str, Any]) -> Any | None:
        path = self._path_for_key(key)
        with self._lock:
            if not path.is_file():
                return None
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        if data.get("key") != key:
            return None
        return data.get("value")

    def _store(self, key: dict[str, Any], value: Any) -> None:
        path = self._path_for_key(key)
        payload = {"key": key, "value": value}
        tmp_path = path.with_name(f"{path.name}.{threading.get_ident()}.tmp")
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        with self._lock:
            try:
                tmp_path.write_text(text, encoding="utf-8")
                tmp_path.replace(path)
            except OSError:
                try:
                    tmp_path.unlink()
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
        key = self._key(pdf_path, kind="text", extra={"extractor": "extract_pdf_text:v1"})
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
        if isinstance(cached, dict):
            summary = dict(cached.get("summary") or {})
            summary["pdf_text_cache_status"] = "hit"
            return str(cached.get("text") or ""), summary
        text, summary = load_pdf_diagnostic_text(
            raw_path,
            pdf_text_override,
            pdf_source_stage=self.pdf_source_stage,
            pdf_path_override=pdf_path_override,
            extract_pdf_text_func=self.extract_pdf_text_func,
        )
        summary = dict(summary)
        summary["pdf_text_cache_status"] = "miss"
        self._store(key, {"text": text, "summary": summary})
        return text, summary

    def link_summary(self, pdf_path: Path, *, sample_limit: int = 12) -> dict[str, Any]:
        key = self._key(
            pdf_path,
            kind="links",
            extra={"sample_limit": sample_limit, "author_year_text_re": self.author_year_cache_key},
        )
        if key is None:
            summary = self.pdf_citation_link_summary_func(
                pdf_path,
                author_year_text_re=self.author_year_text_re,
                sample_limit=sample_limit,
            )
            summary["pdf_link_cache_status"] = "disabled"
            return summary
        cached = self._load(key)
        if isinstance(cached, dict):
            summary = dict(cached)
            summary["pdf_link_cache_status"] = "hit"
            return summary
        summary = self.pdf_citation_link_summary_func(
            pdf_path,
            author_year_text_re=self.author_year_text_re,
            sample_limit=sample_limit,
        )
        summary = dict(summary)
        summary["pdf_link_cache_status"] = "miss"
        self._store(key, summary)
        return summary
