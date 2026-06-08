"""PDF page-render and text-layer evidence stage for quality-loop packs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .observations import compact_observation_text
from .p62_matching import best_pdf_text_page
from .run_utils import now, slug, write_json


PdfTextPages = Callable[..., tuple[str, list[str], str | None]]
RenderPdfPage = Callable[..., dict[str, Any]]


def problem_snippets_for_evidence(article: dict[str, Any]) -> list[str]:
    snippets: list[str] = []
    for defect in article.get("defects") or []:
        if isinstance(defect, dict) and defect.get("snippet"):
            snippets.append(compact_observation_text(defect.get("snippet"), max_len=800))
    comparison = article.get("comparison") if isinstance(article.get("comparison"), dict) else {}
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

    evidence_articles: list[dict[str, Any]] = []
    ready_count = 0
    unavailable_count = 0
    blocking_issue_count = 0

    for index, article in enumerate(selected_articles, start=1):
        article_id = str(article.get("article") or f"article_{index}")
        candidates = list(article.get("source_pdf_candidates") or [])
        selected_pdf = next((candidate for candidate in candidates if candidate.get("exists")), None)
        snippets = problem_snippets_for_evidence(article)
        article_dir = evidence_dir / f"{index:03d}_{slug(article_id, max_len=72)}"
        record: dict[str, Any] = {
            "article": article_id,
            "source_article": article.get("source_article"),
            "status": "source_pdf_unavailable",
            "source_pdf_available": bool(selected_pdf),
            "source_pdf_path": selected_pdf.get("path") if selected_pdf else "",
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

        pdf_path = Path(str(selected_pdf.get("path") or "")).expanduser()
        text_status, pages, text_error = pdf_text_pages(pdf_path, max_pages=max_pdf_pages)
        page_number, match_score = best_pdf_text_page(snippets, pages)
        if page_number <= 0 and pages:
            page_number = 1
        text_excerpt_path = ""
        if page_number > 0 and pages:
            text_excerpt_path = str(article_dir / f"page_{page_number:04d}.txt")
            Path(text_excerpt_path).parent.mkdir(parents=True, exist_ok=True)
            Path(text_excerpt_path).write_text(pages[page_number - 1], encoding="utf-8", errors="replace")
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

        text_chars = sum(len(page_text) for page_text in pages)
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

    if not selected_articles:
        status = "not_required"
    elif blocking_issue_count:
        status = "incomplete"
    else:
        status = "ready"
    report = {
        "generated_at": now(),
        "run_dir": str(run_dir),
        "report_path": str(out_path),
        "evidence_dir": str(evidence_dir),
        "status": status,
        "required_checks": ["source_pdf_page_render", "source_pdf_text_layer"],
        "allow_missing_source_pdf": allow_missing_source_pdf,
        "selected_count": len(selected_articles),
        "ready_count": ready_count,
        "source_pdf_unavailable_count": unavailable_count,
        "blocking_issue_count": blocking_issue_count,
        "articles": evidence_articles,
    }
    write_json(out_path, report)
    return report
