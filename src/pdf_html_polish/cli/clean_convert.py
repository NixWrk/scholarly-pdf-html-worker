from __future__ import annotations

import argparse
from collections.abc import Sequence

from pdf_html_polish.clean_pipeline import (
    CleanPipelineOptions,
    run_clean_pipeline,
)
from pdf_html_polish.export_modes import ExportMode
from pdf_html_polish.marker_runner import MarkerRunner
from pdf_html_polish.pipeline import run_raw_html_pipeline
from pdf_html_polish.pipeline_options import PipelineOptions
from pdf_html_polish.stage_contract import PUBLISH_REPORT_NAME


def _log(message: str) -> None:
    print(message, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert PDF files to audited, repair-enabled polished EN HTML. "
            "This is the recommended clean production pipeline."
        )
    )
    parser.add_argument(
        "--pdf",
        action="append",
        required=True,
        help="PDF file to convert. Can be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Primary conversion output directory.",
    )
    parser.add_argument(
        "--quality-output-dir",
        help=(
            "Quality-loop output directory. Defaults to '<output-dir>_quality'. "
            "The final audited HTML is collected under its final_html/ folder."
        ),
    )
    parser.add_argument("--run-id", help="Quality-loop run id. Defaults to the quality output directory name.")
    parser.add_argument("--final-html-dir", help="Optional directory for collected final audited HTML files.")
    parser.add_argument("--previous-entry", help="Optional compatible quality_history_entry.json for comparison.")
    parser.add_argument("--gate-config", help="Optional quality gate config path.")
    parser.add_argument("--jobs", type=int, help="Default article-level worker count for quality stages.")
    parser.add_argument("--repolish-jobs", type=int, help="Worker count for quality-loop repolish.")
    parser.add_argument("--audit-jobs", type=int, help="Worker count for quality-loop audit.")
    parser.add_argument("--p62-marker-recovery-jobs", type=int)
    parser.add_argument("--p62-recovery-jobs", type=int)
    parser.add_argument("--polish-auto-repair-jobs", type=int)
    parser.add_argument(
        "--append-history",
        action="store_true",
        help="Append the run to the shared quality history. By default only per-run history artifacts are written.",
    )
    parser.add_argument(
        "--skip-quality-tests",
        action="store_true",
        help="Skip the quality-loop test command. Use only when intentionally optimizing for per-document runtime.",
    )
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Return failure when quality_gate_report.json status is fail.",
    )
    parser.add_argument(
        "--diagnostic-allow-gate-failure",
        dest="fail_on_gate",
        action="store_false",
        help="Allow diagnostic output even when the document quality gate fails.",
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help=(
            "Internal chunk-fallback mode: run Marker and save 01.en.raw.html only; "
            "skip citation profile, polish, quality observe, and final HTML collection."
        ),
    )
    parser.add_argument(
        "--repolish-existing",
        action="store_true",
        help=(
            "Reuse existing 01.en.raw.html stages under --output-dir, rerun polish and "
            "quality observe, and skip PDF conversion."
        ),
    )

    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--no-cuda", action="store_true")
    parser.add_argument("--cuda-device-index", type=int, default=0)
    parser.add_argument("--model-cache-dir")
    parser.add_argument("--max-base-len", type=int, default=120)
    parser.add_argument("--disable-batch-multiprocessing", action="store_true")
    parser.add_argument(
        "--postprocess-jobs",
        type=int,
        default=1,
        help="Worker count for post-Marker HTML polish/inlining. Default: 1.",
    )
    parser.add_argument(
        "--zotero-overlay-dir",
        help="Optional directory with Zotero/pdf.js *.overlays.json files.",
    )
    parser.add_argument(
        "--require-zotero-overlay",
        dest="require_zotero_overlay",
        action="store_true",
        default=True,
        help="Require Zotero/pdf.js overlay evidence; enabled by default for production PDF -> HTML.",
    )
    parser.add_argument(
        "--allow-missing-zotero-overlay",
        dest="require_zotero_overlay",
        action="store_false",
        help="Allow conversion to continue without Zotero/pdf.js overlay evidence.",
    )
    parser.add_argument("--marker-cmd", default="marker")
    parser.add_argument("--marker-single-cmd", default="marker_single")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.raw_only and args.repolish_existing:
        parser.error("--raw-only and --repolish-existing are mutually exclusive")
    runner = MarkerRunner(
        marker_cmd=args.marker_cmd,
        marker_single_cmd=args.marker_single_cmd,
    )
    conversion_options = PipelineOptions(
        source_pdf_paths=args.pdf,
        output_dir=args.output_dir,
        skip_existing=not args.no_skip_existing,
        use_cuda=not args.no_cuda,
        cuda_device_index=args.cuda_device_index,
        model_cache_dir=args.model_cache_dir,
        max_base_len=args.max_base_len,
        disable_batch_multiprocessing=args.disable_batch_multiprocessing,
        postprocess_max_workers=max(1, args.postprocess_jobs),
        zotero_overlay_dir=args.zotero_overlay_dir,
        require_zotero_overlay=args.require_zotero_overlay,
        export_mode=ExportMode.HTML.value,
    )
    try:
        if args.raw_only:
            raw_summary = run_raw_html_pipeline(conversion_options, runner, _log, lambda: False)
        else:
            clean_options = CleanPipelineOptions(
                conversion_options=conversion_options,
                quality_output_dir=args.quality_output_dir,
                run_id=args.run_id,
                jobs=args.jobs,
                repolish_jobs=args.repolish_jobs,
                audit_jobs=args.audit_jobs,
                p62_marker_recovery_jobs=args.p62_marker_recovery_jobs,
                p62_recovery_jobs=args.p62_recovery_jobs,
                polish_auto_repair_jobs=args.polish_auto_repair_jobs,
                previous_entry=args.previous_entry,
                gate_config=args.gate_config,
                final_html_dir=args.final_html_dir,
                no_append_history=not args.append_history,
                skip_quality_tests=args.skip_quality_tests,
                fail_on_gate=args.fail_on_gate,
                reuse_existing_conversion=args.repolish_existing,
            )
            summary = run_clean_pipeline(clean_options, runner, _log, lambda: False)
    finally:
        runner.cleanup_spawned_processes(_log)

    print("", flush=True)
    if args.raw_only:
        print(f"conversion_output_dir={raw_summary.output_dir}", flush=True)
        print("raw_only=true", flush=True)
        print(f"converted={raw_summary.converted_total}", flush=True)
        print(f"failed={raw_summary.failed_total}", flush=True)
        return 1 if raw_summary.failed_total else 0

    print(f"conversion_output_dir={summary.conversion_summary.output_dir}", flush=True)
    print(f"quality_output_dir={summary.quality_output_dir}", flush=True)
    print(f"run_id={summary.run_id}", flush=True)
    print(f"converted={summary.conversion_summary.converted_total}", flush=True)
    print(f"failed={summary.conversion_summary.failed_total}", flush=True)
    print(f"observe_exit_code={summary.observe_exit_code}", flush=True)
    if summary.converted_stage_publish_report is not None:
        publish_report = summary.converted_stage_publish_report
        print(
            "converted_stage_publish="
            f"published:{publish_report.get('published_count')} "
            f"removed_extra_html:{publish_report.get('removed_extra_html_count')} "
            f"contract:{publish_report.get('stage_contract_status')}",
            flush=True,
        )
        print(
            f"converted_stage_publish_report={summary.quality_output_dir / PUBLISH_REPORT_NAME}",
            flush=True,
        )
    print(f"final_html_dir={summary.final_html.final_html_dir}", flush=True)
    print(f"final_html_count={len(summary.final_html.artifacts)}", flush=True)
    print(f"final_html_manifest={summary.final_html.manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
