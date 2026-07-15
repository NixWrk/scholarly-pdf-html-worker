from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pdf_html_polish.stage_contract import (
    PUBLISH_REPORT_NAME,
    STAGE_CONTRACT_REPORT_NAME,
    publish_latest_polish_from_quality_run,
    report_to_json,
    verify_stage_contract,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify and publish the converted-stage HTML contract: each article "
            "keeps only 01.en.raw.html and the latest audited 02.en.polish.html."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="Verify converted roots without modifying files.")
    verify.add_argument("--root", action="append", type=Path, required=True, help="Converted root to verify.")
    verify.add_argument(
        "--out-report",
        type=Path,
        help=f"JSON report path. Defaults to ./{STAGE_CONTRACT_REPORT_NAME}.",
    )
    verify.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="Return exit code 1 when the two-HTML contract is not satisfied.",
    )

    publish = subparsers.add_parser(
        "publish",
        help="Publish audited quality-run polish back into converted stage directories.",
    )
    publish.add_argument("--quality-run-dir", type=Path, required=True)
    publish.add_argument(
        "--converted-root",
        action="append",
        type=Path,
        default=[],
        help="Optional converted root allow-list. Can be repeated.",
    )
    publish.add_argument(
        "--apply",
        action="store_true",
        help="Actually copy final polish and prune extra HTML. Without this the command is dry-run only.",
    )
    publish.add_argument(
        "--keep-extra-html",
        action="store_true",
        help="Do not prune extra HTML files while publishing.",
    )
    publish.add_argument(
        "--backup-dir",
        type=Path,
        help="Optional directory for backups of overwritten/removed HTML files.",
    )
    publish.add_argument(
        "--out-report",
        type=Path,
        help=f"JSON report path. Defaults to <quality-run-dir>/{PUBLISH_REPORT_NAME}.",
    )
    publish.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="Return exit code 1 if actual post-command stage verification still fails.",
    )
    return parser


def _print_verify_summary(report: dict[str, Any]) -> None:
    print(
        "Stage contract: "
        f"status={report['status']} "
        f"articles={report['article_count']} "
        f"failing={report['failing_article_count']} "
        f"extra_html={report['extra_html_count']} "
        f"missing_canonical={report['missing_canonical_count']}",
        flush=True,
    )


def _print_publish_summary(report: dict[str, Any]) -> None:
    print(
        "Published latest polish: "
        f"mode={report['mode']} "
        f"articles={report['article_count']} "
        f"published={report['published_count']} "
        f"dry_run={report['dry_run_count']} "
        f"missing={report['missing_count']} "
        f"extra_html={report['extra_html_count']} "
        f"removed_extra_html={report['removed_extra_html_count']} "
        f"stage_contract={report['stage_contract_status']}",
        flush=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        out_report = args.out_report or Path(STAGE_CONTRACT_REPORT_NAME)
        report = verify_stage_contract(args.root, out_report=out_report)
        _print_verify_summary(report)
        print(f"report={out_report}", flush=True)
        if args.fail_on_violations and report["status"] != "pass":
            return 1
        return 0

    if args.command == "publish":
        report = publish_latest_polish_from_quality_run(
            args.quality_run_dir,
            converted_roots=args.converted_root,
            apply=args.apply,
            prune_extra_html=not args.keep_extra_html,
            backup_dir=args.backup_dir,
            out_report=args.out_report,
        )
        _print_publish_summary(report)
        report_path = args.out_report or (args.quality_run_dir / PUBLISH_REPORT_NAME)
        print(f"report={report_path}", flush=True)
        if args.fail_on_violations and report["stage_contract_status"] != "pass":
            print(report_to_json(report), flush=True)
            return 1
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
