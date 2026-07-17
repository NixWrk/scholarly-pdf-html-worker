#!/usr/bin/env python
"""Run targeted article invariants between refactoring cycles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.atomic_io import write_text_atomic  # noqa: E402
from pdf_html_polish.quality_loop.article_check import build_refactor_article_check  # noqa: E402


def _rerun_selected_audit(
    run_dir: Path,
    selected_articles: list[str],
    *,
    enable_pdf_diagnostics: bool,
) -> dict[str, object]:
    from scripts.audit_en_polish import _load_pdf_map, build_report  # noqa: PLC0415

    roots: list[Path] = []
    missing_roots: list[str] = []
    for article_id in selected_articles:
        article_dir = run_dir / "audit_tree" / article_id
        if article_dir.exists():
            roots.append(article_dir)
        else:
            missing_roots.append(article_id)
    pdf_map = None
    pdf_map_path = run_dir / "source_pdf_map.json"
    if enable_pdf_diagnostics and pdf_map_path.is_file():
        pdf_map = _load_pdf_map(pdf_map_path)
    audit = build_report(roots, enable_pdf_diagnostics=enable_pdf_diagnostics, pdf_map=pdf_map)
    audit["_missing_selected_roots"] = missing_roots
    return audit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--article", action="append", default=[])
    parser.add_argument("--defect-id", action="append", default=[])
    parser.add_argument("--from-pack", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--rerun-audit",
        action="store_true",
        help="Re-run current audit code on selected audit_tree articles and enforce quality invariants.",
    )
    parser.add_argument("--rerun-audit-out", type=Path)
    parser.add_argument(
        "--no-rerun-pdf-diagnostics",
        dest="rerun_pdf_diagnostics",
        action="store_false",
        help="Disable PDF diagnostics for --rerun-audit.",
    )
    parser.add_argument("--allow-gate-failure", action="append", default=None)
    parser.add_argument("--allow-any-gate-failure", action="store_true")
    parser.add_argument("--no-require-quality-zero", dest="require_quality_zero", action="store_false")
    parser.add_argument("--no-require-hard-links-zero", dest="require_hard_links_zero", action="store_false")
    parser.set_defaults(require_quality_zero=True, require_hard_links_zero=True, rerun_pdf_diagnostics=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    allowed_gate_failures = None
    if args.allow_any_gate_failure:
        allowed_gate_failures = {"*"}
    elif args.allow_gate_failure is not None:
        allowed_gate_failures = set(args.allow_gate_failure)
    report = build_refactor_article_check(
        args.run_dir,
        explicit_articles=args.article,
        defect_ids=args.defect_id,
        from_pack=args.from_pack,
        limit=args.limit,
        require_quality_zero=args.require_quality_zero,
        require_hard_links_zero=args.require_hard_links_zero,
        allowed_gate_failures=allowed_gate_failures,
    )
    if args.rerun_audit:
        audit = _rerun_selected_audit(
            args.run_dir.resolve(strict=False),
            list(report.get("selected_articles") or []),
            enable_pdf_diagnostics=args.rerun_pdf_diagnostics,
        )
        rerun_summary = {
            "audit_status": audit.get("audit_status"),
            "article_count": audit.get("article_count"),
            "missing_selected_roots": audit.get("_missing_selected_roots", []),
            "quality_defect_counts": (audit.get("corpus_summary") or {}).get("defect_counts", {}),
            "observed_defect_counts": (audit.get("corpus_summary") or {}).get("observed_defect_counts", {}),
            "non_quality_defect_counts": (audit.get("corpus_summary") or {}).get("non_quality_defect_counts", {}),
        }
        if args.rerun_audit_out is not None:
            args.rerun_audit_out.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(
                args.rerun_audit_out,
                json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            )
            rerun_summary["path"] = str(args.rerun_audit_out)
        report["rerun_audit"] = rerun_summary
        if rerun_summary["missing_selected_roots"]:
            report["failures"].append(
                {
                    "kind": "rerun_audit_missing_selected_roots",
                    "articles": rerun_summary["missing_selected_roots"],
                }
            )
        if args.require_quality_zero and rerun_summary["quality_defect_counts"]:
            report["failures"].append(
                {
                    "kind": "rerun_audit_quality_defect_counts",
                    "counts": rerun_summary["quality_defect_counts"],
                }
            )
        report["status"] = "fail" if report["failures"] else "pass"
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(args.out, payload)
    print(
        "Refactor article check: "
        f"status={report['status']} selected={report['selected_article_count']} "
        f"quality={report['quality_totals']} gate={report['gate_status']}"
    )
    if report.get("rerun_audit"):
        rerun = report["rerun_audit"]
        print(
            "Refactor rerun audit: "
            f"articles={rerun['article_count']} quality={rerun['quality_defect_counts']} "
            f"observed={rerun['observed_defect_counts']}"
        )
    if report["failures"]:
        print(json.dumps(report["failures"], ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
