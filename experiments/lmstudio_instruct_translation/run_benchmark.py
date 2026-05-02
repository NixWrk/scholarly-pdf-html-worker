from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from lmstudio_client import unload_lms_model


SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Candidate:
    key: str
    model: str
    identifier: str


CANDIDATES: dict[str, Candidate] = {
    "qwen3vl30b": Candidate(
        key="qwen3vl30b",
        model="p6_qwen_qwen3-vl-30b@q6_k",
        identifier="qwen3vl30b_q6_ctx32768_bench",
    ),
    "gemma4_26b": Candidate(
        key="gemma4_26b",
        model="p6_google_gemma-4-26b-a4b@q6_k",
        identifier="gemma4_26b_q6_ctx32768_bench",
    ),
    "gemma4_31b": Candidate(
        key="gemma4_31b",
        model="p6_google_gemma-4-31b@q8_0",
        identifier="gemma4_31b_q8_ctx32768_bench",
    ),
}


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def run_command(args: list[str]) -> int:
    print("\n> " + " ".join(args), flush=True)
    return subprocess.run(args, cwd=SCRIPT_DIR.parents[1], check=False).returncode


def unload_candidate(candidate: Candidate) -> None:
    try:
        unloaded = unload_lms_model(candidate.identifier, timeout_s=120, missing_ok=True)
    except Exception as exc:
        print(f"[WARN] failed to unload {candidate.identifier}: {exc}", flush=True)
        return
    if unloaded:
        print(f"unloaded: {candidate.identifier}", flush=True)


def candidate_list(raw: str) -> list[Candidate]:
    result: list[Candidate] = []
    for item in [part.strip() for part in raw.split(",") if part.strip()]:
        try:
            result.append(CANDIDATES[item])
        except KeyError as exc:
            choices = ", ".join(sorted(CANDIDATES))
            raise SystemExit(f"Unknown candidate '{item}'. Choices: {choices}") from exc
    if not result:
        raise SystemExit("No benchmark candidates selected.")
    return result


def run(args: argparse.Namespace) -> int:
    candidates = candidate_list(args.models)
    suffix = args.run_suffix or timestamp()
    failures = 0

    for candidate in candidates:
        try:
            if not args.skip_synthetic:
                cmd = [
                    sys.executable,
                    str(SCRIPT_DIR / "run_synthetic.py"),
                    "--model",
                    candidate.model,
                    "--context-length",
                    str(args.context_length),
                    "--identifier",
                    candidate.identifier,
                    "--max-tokens",
                    str(args.synthetic_max_tokens),
                    "--timeout-s",
                    str(args.timeout_s),
                    "--load-timeout-s",
                    str(args.load_timeout_s),
                ]
                if args.auto_load:
                    cmd.append("--auto-load")
                code = run_command(cmd)
                if code != 0:
                    failures += 1
                    if args.stop_on_error:
                        return code

            if args.skip_html:
                continue

            run_name = f"{args.run_prefix}_{candidate.key}_{suffix}"
            cmd = [
                sys.executable,
                str(SCRIPT_DIR / "run_html_probe.py"),
                "--input-dir",
                args.input_dir,
                "--output-dir",
                args.output_dir,
                "--run-name",
                run_name,
                "--model",
                candidate.model,
                "--context-length",
                str(args.context_length),
                "--identifier",
                candidate.identifier,
                "--max-tokens",
                str(args.max_tokens),
                "--timeout-s",
                str(args.timeout_s),
                "--load-timeout-s",
                str(args.load_timeout_s),
                "--article-regex",
                args.article_regex,
                "--quality-gate-max-segments",
                str(args.quality_gate_max_segments),
                "--cjk-gate-max-segments",
                str(args.cjk_gate_max_segments),
            ]
            if args.auto_load:
                cmd.append("--auto-load")
            code = run_command(cmd)
            if code != 0:
                failures += 1
                if args.stop_on_error:
                    return code
        finally:
            if args.auto_load and args.unload_after_candidate:
                unload_candidate(candidate)

    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the LM Studio instruct translation benchmark for selected candidates."
    )
    parser.add_argument("--models", default="qwen3vl30b,gemma4_26b")
    parser.add_argument("--input-dir", default="manual_review_en_polish_inlined_2026-04-27_round6")
    parser.add_argument("--output-dir", default="bench_lmstudio_instruct")
    parser.add_argument("--run-prefix", default="bench")
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--article-regex", default="06_Wang")
    parser.add_argument("--context-length", type=int, default=32768)
    parser.add_argument("--auto-load", action="store_true", default=True)
    parser.add_argument("--no-auto-load", action="store_false", dest="auto_load")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--synthetic-max-tokens", type=int, default=2048)
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--load-timeout-s", type=int, default=1800)
    parser.add_argument("--quality-gate-max-segments", type=int, default=8)
    parser.add_argument("--cjk-gate-max-segments", type=int, default=8)
    parser.add_argument("--skip-synthetic", action="store_true")
    parser.add_argument("--skip-html", action="store_true")
    parser.add_argument("--keep-loaded", action="store_false", dest="unload_after_candidate")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.set_defaults(unload_after_candidate=True)
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
