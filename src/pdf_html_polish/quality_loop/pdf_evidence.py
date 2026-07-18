"""PDF page-render and text-layer evidence stage for quality-loop packs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from pdf_html_polish.artifact_integrity import FileFingerprint, fingerprint_file

from pdf_html_polish.atomic_io import write_text_atomic

from .enrichment_snapshot import snapshot_enrichment_file
from .observations import compact_observation_text
from .p62_matching import best_pdf_text_page
from .run_utils import json_object, now, reset_run_owned_directory, slug, write_json

PDF_PROBLEM_EVIDENCE_REPORT_SCHEMA_VERSION = 1
PDF_PROBLEM_EVIDENCE_PROVENANCE_SCHEMA_VERSION = 1
PDF_PROBLEM_EVIDENCE_INPUTS_SCHEMA_VERSION = 1
PDF_PROBLEM_EVIDENCE_INPUTS_NAME = "pdf_problem_evidence_inputs.json"

PDF_PROBLEM_EVIDENCE_REPORT_FIELDS = frozenset(
    {
        "generated_at",
        "run_dir",
        "report_path",
        "schema_version",
        "evidence_dir",
        "status",
        "required_checks",
        "allow_missing_source_pdf",
        "selected_count",
        "ready_count",
        "source_pdf_unavailable_count",
        "blocking_issue_count",
        "articles",
        "provenance",
    }
)
PDF_PROBLEM_EVIDENCE_ARTICLE_FIELDS = frozenset(
    {
        "article",
        "source_article",
        "status",
        "source_pdf_available",
        "source_pdf_path",
        "source_pdf_origin_path",
        "source_pdf_source",
        "source_pdf_candidate_count",
        "required_checks",
        "problem_snippet_count",
        "problem_snippets",
        "evidence_page",
        "text_layer_status",
        "text_layer_chars",
        "text_layer_page_count",
        "text_layer_page_limit",
        "text_layer_truncated_to_limit",
        "text_layer_error",
        "text_layer_excerpt_path",
        "page_render_status",
        "page_render_path",
        "page_render_error",
        "match_score",
    }
)
PDF_PROBLEM_EVIDENCE_UNAVAILABLE_ARTICLE_FIELDS = (
    PDF_PROBLEM_EVIDENCE_ARTICLE_FIELDS | {"unavailable_reason"}
)
PDF_PROBLEM_EVIDENCE_CANDIDATE_REQUIRED_FIELDS = frozenset(
    {"path", "exists", "source"}
)
PDF_PROBLEM_EVIDENCE_CANDIDATE_ALLOWED_FIELDS = (
    PDF_PROBLEM_EVIDENCE_CANDIDATE_REQUIRED_FIELDS | {"original_path"}
)


def _evidence_file_record(
    path: Path,
    *,
    kind: str,
    article: str = "",
    fingerprint: FileFingerprint | None = None,
) -> dict[str, Any]:
    resolved = path.resolve(strict=False)
    current = fingerprint or fingerprint_file(resolved, reject_symlink=True)
    if current is None:
        raise ValueError(f"pdf_evidence_artifact_unstable:{kind}:{resolved}")
    return {
        "kind": kind,
        "article": article,
        "path": str(resolved),
        "bytes": current.size,
        "sha256": current.sha256,
    }


PdfTextPages = Callable[..., tuple[str, list[str], str | None]]
RenderPdfPage = Callable[..., dict[str, Any]]


def problem_snippets_for_evidence(article: dict[str, Any]) -> list[str]:
    snippets: list[str] = []
    for defect in article.get("defects") or []:
        if isinstance(defect, dict) and defect.get("snippet"):
            snippets.append(compact_observation_text(defect.get("snippet"), max_len=800))
    comparison = json_object(article.get("comparison"))
    if comparison.get("article") and comparison.get("score_delta"):
        snippets.append(f"comparison regression score_delta={comparison.get('score_delta')}")
    return [snippet for snippet in snippets if snippet]


def attach_pdf_evidence_to_pack(pack: dict[str, Any], evidence_report: dict[str, Any]) -> dict[str, Any]:
    evidence_by_article = {
        str(item.get("article")): item
        for item in evidence_report.get("articles") or []
        if isinstance(item, dict) and item.get("article")
    }
    for article in pack.get("articles") or []:
        if isinstance(article, dict):
            article["pdf_problem_evidence"] = evidence_by_article.get(str(article.get("article")), {})
    pack["pdf_problem_evidence_stage"] = {
        "status": evidence_report.get("status"),
        "report_path": evidence_report.get("report_path"),
        "evidence_dir": evidence_report.get("evidence_dir"),
        "selected_count": evidence_report.get("selected_count", 0),
        "ready_count": evidence_report.get("ready_count", 0),
        "source_pdf_unavailable_count": evidence_report.get("source_pdf_unavailable_count", 0),
        "blocking_issue_count": evidence_report.get("blocking_issue_count", 0),
        "required_checks": evidence_report.get("required_checks", []),
    }
    return pack


def write_pdf_problem_evidence_stage(
    run_dir: Path,
    pack: dict[str, Any],
    *,
    gate_config: dict[str, Any],
    out_path: Path | None = None,
    output_name: str = "pdf_problem_evidence_report.json",
    pdf_text_pages: PdfTextPages,
    render_pdf_evidence_page: RenderPdfPage,
) -> dict[str, Any]:
    """Create PDF render/text-layer evidence requirements for selected problem articles."""

    run_dir = run_dir.resolve(strict=False)
    out_path = out_path or (run_dir / output_name)
    evidence_dir = run_dir / "pdf_problem_evidence"
    max_articles = int(gate_config.get("pdf_problem_evidence_max_articles") or 0)
    selected_articles = list(pack.get("articles") or [])
    if max_articles > 0:
        selected_articles = selected_articles[:max_articles]
    zoom = float(gate_config.get("pdf_problem_evidence_render_zoom") or 1.5)
    max_pdf_pages = int(gate_config.get("pdf_problem_evidence_max_pdf_pages") or 80)
    allow_missing_source_pdf = bool(gate_config.get("pdf_problem_evidence_allow_missing_source_pdf", True))

    selection_articles: list[dict[str, Any]] = []
    for index, article in enumerate(selected_articles, start=1):
        article_id = str(article.get("article") or f"article_{index}")
        candidates = [
            dict(candidate)
            for candidate in article.get("source_pdf_candidates") or []
            if isinstance(candidate, dict)
        ]
        selected_pdf = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("exists")
                and isinstance(candidate.get("path"), str)
                and Path(str(candidate["path"])).expanduser().is_file()
            ),
            None,
        )
        selection_articles.append(
            {
                "article": article_id,
                "source_article": article.get("source_article"),
                "source_pdf_candidates": candidates,
                "selected_source_pdf": selected_pdf,
                "problem_snippets": problem_snippets_for_evidence(article),
            }
        )
    selection_path = run_dir / PDF_PROBLEM_EVIDENCE_INPUTS_NAME
    selection_payload = {
        "schema_version": PDF_PROBLEM_EVIDENCE_INPUTS_SCHEMA_VERSION,
        "max_articles": max_articles,
        "render_zoom": zoom,
        "max_pdf_pages": max_pdf_pages,
        "allow_missing_source_pdf": allow_missing_source_pdf,
        "articles": selection_articles,
    }
    write_json(selection_path, selection_payload)
    selection_record = _evidence_file_record(
        selection_path,
        kind="evidence_inputs",
    )

    evidence_dir = reset_run_owned_directory(run_dir, "pdf_problem_evidence")
    evidence_articles: list[dict[str, Any]] = []
    artifact_records: list[dict[str, Any]] = []
    ready_count = 0
    unavailable_count = 0
    blocking_issue_count = 0

    for index, article in enumerate(selection_articles, start=1):
        article_id = str(article["article"])
        candidates = list(article["source_pdf_candidates"])
        selected_pdf = article.get("selected_source_pdf")
        snippets = list(article["problem_snippets"])
        article_dir = evidence_dir / f"{index:03d}_{slug(article_id, max_len=72)}"
        record: dict[str, Any] = {
            "article": article_id,
            "source_article": article.get("source_article"),
            "status": "source_pdf_unavailable",
            "source_pdf_available": bool(selected_pdf),
            "source_pdf_path": selected_pdf.get("path") if selected_pdf else "",
            "source_pdf_origin_path": selected_pdf.get("path") if selected_pdf else "",
            "source_pdf_source": selected_pdf.get("source") if selected_pdf else "",
            "source_pdf_candidate_count": len(candidates),
            "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
            "problem_snippet_count": len(snippets),
            "problem_snippets": snippets[:8],
            "evidence_page": 0,
            "text_layer_status": "not_run",
            "text_layer_chars": 0,
            "text_layer_page_count": 0,
            "text_layer_page_limit": max_pdf_pages,
            "text_layer_truncated_to_limit": False,
            "text_layer_error": "",
            "text_layer_excerpt_path": "",
            "page_render_status": "not_run",
            "page_render_path": "",
            "page_render_error": "",
            "match_score": 0.0,
        }
        if not selected_pdf:
            unavailable_count += 1
            record["unavailable_reason"] = "No existing source PDF candidate was found."
            if not allow_missing_source_pdf:
                blocking_issue_count += 1
            evidence_articles.append(record)
            continue

        source_pdf_path = Path(str(selected_pdf.get("path") or "")).expanduser()
        pdf_path = snapshot_enrichment_file(
            run_dir,
            article_id,
            "pdf_problem_evidence",
            source_pdf_path,
        )
        record["source_pdf_path"] = str(pdf_path)
        artifact_records.append(
            _evidence_file_record(
                pdf_path,
                kind="source_pdf",
                article=article_id,
            )
        )
        text_status, pages, text_error = pdf_text_pages(pdf_path, max_pages=max_pdf_pages)
        page_number, match_score = best_pdf_text_page(snippets, pages)
        if page_number <= 0 and pages:
            page_number = 1
        text_excerpt_path = ""
        selected_page_text = pages[page_number - 1] if page_number > 0 and pages else ""
        if selected_page_text.strip():
            text_excerpt_path = str(article_dir / f"page_{page_number:04d}.txt")
            Path(text_excerpt_path).parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(Path(text_excerpt_path), selected_page_text, errors="replace")
            artifact_records.append(
                _evidence_file_record(
                    Path(text_excerpt_path),
                    kind="text_excerpt",
                    article=article_id,
                )
            )
        render = (
            render_pdf_evidence_page(
                pdf_path,
                page_number or 1,
                article_dir / f"page_{(page_number or 1):04d}.png",
                zoom=zoom,
            )
            if page_number > 0 or pages
            else {"status": "no_page_to_render", "path": "", "error": "No page text was extracted."}
        )
        if render.get("status") == "rendered":
            render_value = render.get("path")
            render_path = Path(str(render_value or "")).expanduser()
            expected_render_path = article_dir / f"page_{(page_number or 1):04d}.png"
            if (
                not render_value
                or render_path.resolve(strict=False) != expected_render_path.resolve(strict=False)
            ):
                render = {
                    "status": "invalid_render_path",
                    "path": str(render_path) if render_value else "",
                    "error": "Renderer did not publish the expected run-owned page artifact.",
                }
            else:
                artifact_records.append(
                    _evidence_file_record(
                        render_path,
                        kind="page_render",
                        article=article_id,
                    )
                )

        text_chars = sum(len(page_text.strip()) for page_text in pages)
        record.update(
            {
                "status": "ready",
                "evidence_page": page_number,
                "text_layer_status": text_status,
                "text_layer_chars": text_chars,
                "text_layer_page_count": len(pages),
                "text_layer_page_limit": max_pdf_pages,
                "text_layer_truncated_to_limit": len(pages) >= max_pdf_pages,
                "text_layer_error": text_error or "",
                "text_layer_excerpt_path": text_excerpt_path,
                "page_render_status": render.get("status"),
                "page_render_path": render.get("path"),
                "page_render_error": render.get("error") or "",
                "match_score": round(float(match_score), 4),
            }
        )
        if text_chars <= 0 or render.get("status") != "rendered":
            record["status"] = "incomplete"
            blocking_issue_count += 1
        else:
            ready_count += 1
        evidence_articles.append(record)

    if not selection_articles:
        status = "not_required"
    elif blocking_issue_count:
        status = "incomplete"
    else:
        status = "ready"
    report = {
        "generated_at": now(),
        "run_dir": str(run_dir),
        "report_path": str(out_path),
        "schema_version": PDF_PROBLEM_EVIDENCE_REPORT_SCHEMA_VERSION,
        "evidence_dir": str(evidence_dir),
        "status": status,
        "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
        "allow_missing_source_pdf": allow_missing_source_pdf,
        "selected_count": len(selection_articles),
        "ready_count": ready_count,
        "source_pdf_unavailable_count": unavailable_count,
        "blocking_issue_count": blocking_issue_count,
        "articles": evidence_articles,
        "provenance": {
            "schema_version": PDF_PROBLEM_EVIDENCE_PROVENANCE_SCHEMA_VERSION,
            "inputs": selection_record,
            "artifacts": artifact_records,
        },
    }
    write_json(out_path, report)
    return report
