from __future__ import annotations

import argparse
from collections.abc import Sequence

from pdf_html_polish.export_modes import ExportMode
from pdf_html_polish.marker_runner import MarkerRunner
from pdf_html_polish.pipeline import PipelineOptions, run_pipeline


def _log(message: str) -> None:
    print(message, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert one or more PDF files to polished EN HTML."
    )
    parser.add_argument(
        "--pdf",
        action="append",
        required=True,
        help="PDF file to convert. Can be repeated.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--no-cuda", action="store_true")
    parser.add_argument("--cuda-device-index", type=int, default=0)
    parser.add_argument("--model-cache-dir", default=None)
    parser.add_argument("--max-base-len", type=int, default=120)
    parser.add_argument("--disable-batch-multiprocessing", action="store_true")
    parser.add_argument(
        "--zotero-overlay-dir",
        default=None,
        help=(
            "Optional directory with Zotero/pdf.js *.overlays.json files. "
            "When provided, citation profiles use these overlays before "
            "falling back to automatic overlay generation."
        ),
    )
    parser.add_argument(
        "--export-mode",
        default=ExportMode.HTML.value,
        choices=[ExportMode.HTML.value, ExportMode.CLASSIC.value, ExportMode.LLM.value],
        help="Output mode. Zotero write-back is intentionally not supported here.",
    )
    parser.add_argument("--marker-cmd", default="marker")
    parser.add_argument("--marker-single-cmd", default="marker_single")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runner = MarkerRunner(
        marker_cmd=args.marker_cmd,
        marker_single_cmd=args.marker_single_cmd,
    )
    options = PipelineOptions(
        source_pdf_paths=args.pdf,
        output_dir=args.output_dir,
        skip_existing=not args.no_skip_existing,
        use_cuda=not args.no_cuda,
        cuda_device_index=args.cuda_device_index,
        model_cache_dir=args.model_cache_dir,
        max_base_len=args.max_base_len,
        disable_batch_multiprocessing=args.disable_batch_multiprocessing,
        zotero_overlay_dir=args.zotero_overlay_dir,
        export_mode=args.export_mode,
    )
    try:
        summary = run_pipeline(options, runner, _log, lambda: False)
    finally:
        runner.cleanup_spawned_processes(_log)

    print("", flush=True)
    print(f"output_dir={summary.output_dir}", flush=True)
    print(f"resolved_pdfs={summary.pdfs_resolved}", flush=True)
    print(f"converted={summary.converted_total}", flush=True)
    print(f"ocr_quality_failed={summary.ocr_quality_failed_total}", flush=True)
    print(f"reocr_queued={summary.reocr_queued_total}", flush=True)
    print(f"reocr_pending={summary.reocr_pending_total}", flush=True)
    print(f"failed={summary.failed_total}", flush=True)
    return 0 if summary.failed_total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
