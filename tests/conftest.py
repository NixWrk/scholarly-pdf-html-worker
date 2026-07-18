import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.artifact_integrity import fingerprint_file  # noqa: E402
from pdf_html_polish.quality_loop.audit_command_provenance import (  # noqa: E402
    build_audit_code_manifest,
    build_audit_command_report,
)


def write_attested_audit_command(
    run_dir: Path,
    *,
    enable_pdf_diagnostics: bool = False,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Complete a test audit fixture and bind it to a realistic command report."""

    run_dir = Path(run_dir).resolve(strict=False)
    audit_path = run_dir / "audit_full_checks.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    articles = audit.get("articles")
    if not isinstance(articles, list):
        articles = []
        audit["articles"] = articles
    audit_roots = [Path(root).resolve(strict=False) for root in (roots or [])]
    if not audit_roots:
        declared_roots = audit.get("roots")
        if isinstance(declared_roots, list) and declared_roots:
            audit_roots = [Path(str(root)).resolve(strict=False) for root in declared_roots]
        else:
            audit_roots = [(run_dir / "audit_tree").resolve(strict=False)]
    for root in audit_roots:
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
    for article in articles:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("article") or "article")
        raw_value = article.get("raw_stage_path")
        polish_value = article.get("polish_stage_path")
        if not raw_value or not polish_value:
            stage_root = audit_roots[0] if audit_roots[0].is_dir() else audit_roots[0].parent
            stage_dir = stage_root / article_id / "_z2m_stages"
            stage_dir.mkdir(parents=True, exist_ok=True)
            raw_path = stage_dir / "01.en.raw.html"
            polish_path = stage_dir / "02.en.polish.html"
            if not raw_path.exists():
                raw_path.write_text("<html><body><p>Raw.</p></body></html>", encoding="utf-8")
            if not polish_path.exists():
                polish_path.write_text("<html><body><p>Polish.</p></body></html>", encoding="utf-8")
            article["raw_stage_path"] = str(raw_path.resolve(strict=False))
            article["polish_stage_path"] = str(polish_path.resolve(strict=False))
        raw_fingerprint = fingerprint_file(Path(str(article["raw_stage_path"])), reject_symlink=True)
        polish_fingerprint = fingerprint_file(Path(str(article["polish_stage_path"])), reject_symlink=True)
        assert raw_fingerprint is not None and polish_fingerprint is not None
        article["raw_stage_bytes"] = raw_fingerprint.size
        article["raw_stage_sha256"] = raw_fingerprint.sha256
        article["polish_stage_bytes"] = polish_fingerprint.size
        article["polish_stage_sha256"] = polish_fingerprint.sha256
        summary = article.setdefault("summary", {})
        if isinstance(summary, dict):
            summary.setdefault("pdf_diagnostics_enabled", enable_pdf_diagnostics)
            summary.setdefault("source_pdf_present", False)
            summary.setdefault("pdf_text_chars", 0)
        article.setdefault("defects_found", [])
    audit.setdefault("generated_at", "2026-01-01T00:00:00+00:00")
    audit.setdefault("stage", "01.en.raw.html -> 02.en.polish.html")
    audit["roots"] = [str(root) for root in audit_roots]
    audit["audit_status"] = "complete"
    audit["processed_pair_count"] = len(articles)
    audit["total_pair_count"] = len(articles)
    audit["article_count"] = len(articles)
    corpus_summary = audit.setdefault("corpus_summary", {})
    if not isinstance(corpus_summary, dict):
        corpus_summary = {}
        audit["corpus_summary"] = corpus_summary
    corpus_summary.setdefault("defect_counts", {})
    corpus_summary.setdefault("observed_defect_counts", {})
    corpus_summary.setdefault("non_quality_defect_counts", {})
    totals = corpus_summary.setdefault("totals", {})
    if isinstance(totals, dict):
        totals.setdefault("source_pdf_present", 0)
        totals.setdefault("pdf_text_chars", 0)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (run_dir / "audit_stdout.log").write_text("", encoding="utf-8")
    (run_dir / "audit_stderr.log").write_text("", encoding="utf-8")
    report = build_audit_command_report(
        run_dir,
        repo_root=ROOT,
        roots=audit_roots,
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_input=None,
        pdf_diagnostics_cache_dir=None,
        jobs=1,
        merge_previous_report_input=None,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        returncode=0,
        code_manifest=build_audit_code_manifest(ROOT),
    )
    (run_dir / "audit_command_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
