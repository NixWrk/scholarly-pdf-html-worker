from __future__ import annotations

import argparse
import atexit
import datetime as dt
import html as html_lib
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

from .lmstudio_client import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_MODEL,
    LMStudioConfig,
    LMStudioInstructTranslator,
    load_lms_model,
    resolve_base_url,
    unload_lms_model,
)
import zoteropdf2md.gemma_html as gemma_html
from zoteropdf2md.gemma_html import (
    _is_recovery_context_active,
    _mark_author_line_notranslate,
    translate_html_text_nodes,
)
from zoteropdf2md.html_stages import (
    HTML_STAGE_DIR_NAME,
    POLISH_STAGE_NAME,
    TRANSLATE_STAGE_NAME,
    article_dir_from_html_stage,
)


STAGE_INPUT_NAME = POLISH_STAGE_NAME
TRANSLATE_OUTPUT_NAME = TRANSLATE_STAGE_NAME

HIDDEN_TEXT_TAGS = {"script", "style", "svg", "math"}
SENTINEL_PATTERN = re.compile(r"@@Z2M|<z2m|zz2m", re.IGNORECASE)
CJK_PATTERN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
PROMPT_LEAK_PATTERN = re.compile(
    r"translate the following|output only the translation|rules:|"
    r"preserve every marker|here is|translation:|"
    r"вот перевод|правила:|сохраняйте кажд",
    re.IGNORECASE,
)
LONG_LATIN_RUN_PATTERN = re.compile(
    r"\b(?:[A-Za-z][A-Za-z'-]{2,}[\s,;:()/-]+){5,}[A-Za-z][A-Za-z'-]{2,}\b"
)


class _VisibleTextParser(HTMLParser):
    def __init__(self, *, skip_no_translate: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_no_translate = skip_no_translate
        self.parts: list[str] = []
        self._stack: list[tuple[str, bool, bool]] = []

    def _current_hidden(self) -> bool:
        return bool(self._stack and self._stack[-1][1])

    def _current_no_translate(self) -> bool:
        return bool(self._stack and self._stack[-1][2])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_map = {name.lower(): value for name, value in attrs}
        hidden = self._current_hidden() or tag_l in HIDDEN_TEXT_TAGS
        no_translate = self._current_no_translate() or (
            self.skip_no_translate
            and (attr_map.get("translate") or "").strip().lower() == "no"
        )
        self._stack.append((tag_l, hidden, no_translate))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return None

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag_l:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if not self._current_hidden() and not self._current_no_translate():
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_name(value: str, *, max_len: int = 120) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    value = re.sub(r"\s+", "_", value).strip(" ._")
    if not value:
        value = "article"
    return value[:max_len].rstrip(" ._") or "article"


def article_label(source_path: Path) -> str:
    if source_path.name == STAGE_INPUT_NAME and source_path.parent.name == HTML_STAGE_DIR_NAME:
        return article_dir_from_html_stage(source_path).name
    if source_path.name == STAGE_INPUT_NAME:
        return source_path.parent.name
    return source_path.stem


def visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return html_lib.unescape(parser.text())


def quality_visible_text(html: str) -> str:
    parser = _VisibleTextParser(skip_no_translate=True)
    parser.feed(html)
    return html_lib.unescape(parser.text())


def structural_counts(html: str) -> dict[str, int]:
    patterns = {
        "img": r"<img\b",
        "figure": r"<figure\b",
        "table": r"<table\b",
        "a": r"<a\b",
        "href": r"\bhref\s*=",
        "id": r"\bid\s*=",
        "sup": r"<sup\b",
        "sub": r"<sub\b",
        "math": r"<math\b",
    }
    return {
        name: len(re.findall(pattern, html, flags=re.IGNORECASE))
        for name, pattern in patterns.items()
    }


def audit_translation(source_html: str, translated_html: str) -> dict[str, Any]:
    source_visible = visible_text(source_html)
    translated_visible = visible_text(translated_html)
    translated_quality_visible = quality_visible_text(translated_html)
    source_counts = structural_counts(source_html)
    translated_counts = structural_counts(translated_html)
    structure_mismatches = {
        key: {"source": source_counts[key], "translated": translated_counts[key]}
        for key in sorted(source_counts)
        if source_counts[key] != translated_counts[key]
    }
    source_len = len(source_visible)
    translated_len = len(translated_visible)
    length_ratio = translated_len / source_len if source_len else 0.0
    long_latin_runs = LONG_LATIN_RUN_PATTERN.findall(translated_quality_visible)
    hard_errors: list[str] = []
    warnings: list[str] = []
    prompt_leaks = len(PROMPT_LEAK_PATTERN.findall(translated_quality_visible))
    visible_sentinels = len(SENTINEL_PATTERN.findall(translated_quality_visible))
    raw_sentinels = len(SENTINEL_PATTERN.findall(translated_html))
    cyrillic_chars = len(re.findall(r"[\u0400-\u04FF]", translated_quality_visible))
    cjk_matches = list(CJK_PATTERN.finditer(translated_quality_visible))
    cjk_examples: list[str] = []
    for match in cjk_matches[:10]:
        start = max(0, match.start() - 80)
        end = min(len(translated_quality_visible), match.end() + 80)
        snippet = translated_quality_visible[start:end].strip()
        if snippet not in cjk_examples:
            cjk_examples.append(snippet)
    if prompt_leaks:
        hard_errors.append("prompt_leak")
    if visible_sentinels:
        hard_errors.append("visible_sentinel_leak")
    if cjk_matches:
        hard_errors.append("cjk_contamination")
    if translated_len and cyrillic_chars == 0:
        hard_errors.append("no_cyrillic_text")
    if structure_mismatches:
        warnings.append("html_structure_count_mismatch")
    if source_len and not (0.35 <= length_ratio <= 2.8):
        warnings.append("visible_length_ratio_outlier")
    return {
        "source_visible_chars": source_len,
        "translated_visible_chars": translated_len,
        "visible_length_ratio": round(length_ratio, 4),
        "translated_cyrillic_chars": cyrillic_chars,
        "cjk_contamination_count": len(cjk_matches),
        "cjk_contamination_examples": cjk_examples,
        "prompt_leak_count": prompt_leaks,
        "visible_sentinel_leak_count": visible_sentinels,
        "raw_sentinel_like_count": raw_sentinels,
        "long_latin_run_count": len(long_latin_runs),
        "long_latin_run_examples": long_latin_runs[:10],
        "structure_counts_source": source_counts,
        "structure_counts_translated": translated_counts,
        "structure_mismatches": structure_mismatches,
        "hard_errors": hard_errors,
        "warnings": warnings,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def find_source_files(input_dir: Path, output_dir: Path) -> list[Path]:
    if input_dir.is_file():
        return [input_dir]
    sources = sorted(input_dir.rglob(STAGE_INPUT_NAME), key=lambda p: str(p).lower())
    return [path for path in sources if output_dir not in path.parents]


def summarize_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    finish_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    elapsed_total = 0.0
    prompt_leak_like = 0
    for call in calls:
        finish = str(call.get("finish_reason") or "unknown")
        call_type = str(call.get("call_type") or "unknown")
        finish_counts[finish] = finish_counts.get(finish, 0) + 1
        type_counts[call_type] = type_counts.get(call_type, 0) + 1
        elapsed_total += float(call.get("elapsed_s") or 0.0)
        prompt_leak_like += int(bool(call.get("prompt_leak_like")))
    return {
        "call_count": len(calls),
        "call_type_counts": type_counts,
        "finish_reason_counts": finish_counts,
        "call_elapsed_s_total": round(elapsed_total, 2),
        "prompt_leak_like_call_count": prompt_leak_like,
    }


def translate_one(
    source_path: Path,
    article_dir: Path,
    args: argparse.Namespace,
    *,
    base_url: str,
    api_model: str,
) -> dict[str, Any]:
    article_dir.mkdir(parents=True, exist_ok=True)
    source_copy = article_dir / STAGE_INPUT_NAME
    translated_path = article_dir / TRANSLATE_OUTPUT_NAME
    calls_path = article_dir / "calls.jsonl"
    report_path = article_dir / "translation_report.json"

    source_raw = source_path.read_text(encoding="utf-8", errors="replace")
    shutil.copy2(source_path, source_copy)
    source_html = _mark_author_line_notranslate(source_raw)

    translator = LMStudioInstructTranslator(
        LMStudioConfig(
            base_url=base_url,
            model=api_model,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            timeout_s=args.timeout_s,
        )
    )
    warnings: list[str] = []
    batch_fallbacks: list[str] = []
    active_segment_no: int | None = None
    active_segment_total: int | None = None

    def translate_text(text: str) -> str:
        marker_count = len(re.findall(r"<z2m-i\d+/>", text, flags=re.IGNORECASE))
        if _is_recovery_context_active():
            call_type = "recovery"
        elif marker_count >= 2:
            call_type = "marker_batch"
        else:
            call_type = "segment"
        result = translator.translate(text, call_type=call_type)
        if translator.calls:
            translator.calls[-1]["segment_no"] = active_segment_no
            translator.calls[-1]["segment_total"] = active_segment_total
            translator.calls[-1]["marker_count"] = marker_count
        return result

    def on_segment_start(segment_no: int, total: int) -> None:
        nonlocal active_segment_no, active_segment_total
        active_segment_no = segment_no
        active_segment_total = total
        print(f"segment {segment_no}/{max(1, total)}: {article_label(source_path)}", flush=True)

    def on_progress(done: int, total: int) -> None:
        if total and (done == total or done % max(1, total // 10) == 0):
            print(f"progress {done}/{total}: {article_label(source_path)}", flush=True)

    def on_batch_fallback(reason: str) -> None:
        batch_fallbacks.append(reason)
        print(f"batch fallback: {reason}", flush=True)

    def on_warning(message: str) -> None:
        warnings.append(message)

    started = perf_counter()
    try:
        translated_html, translated_segments = translate_html_text_nodes(
            source_html,
            translate_text=translate_text,
            max_chunk_chars=args.max_chunk_chars,
            target_language_code="ru",
            context_window_segments=args.context_window_segments,
            context_overlap_segments=args.context_overlap_segments,
            context_max_window_chars=args.context_max_window_chars,
            enable_marker_batching=not args.disable_marker_batching,
            enable_en_residual_quality_gate=not args.disable_quality_gate,
            en_residual_quality_gate_max_segments=args.quality_gate_max_segments,
            enable_cjk_quality_gate=not args.disable_cjk_gate,
            cjk_quality_gate_max_segments=args.cjk_gate_max_segments,
            on_segment_start=on_segment_start,
            on_progress=on_progress,
            on_batch_fallback=on_batch_fallback,
            on_warning=on_warning,
        )
    except Exception:
        write_jsonl(calls_path, translator.calls)
        raise
    elapsed = perf_counter() - started

    translated_path.write_text(translated_html, encoding="utf-8")
    write_jsonl(calls_path, translator.calls)
    audit = audit_translation(source_html, translated_html)
    report = {
        "status": "completed",
        "source_html_path": str(source_path),
        "translated_html_path": str(translated_path),
        "model": args.model,
        "api_model": api_model,
        "base_url": base_url,
        "context_length": args.context_length if args.auto_load else None,
        "abbrev_mask_enabled": not args.disable_abbrev_mask,
        "elapsed_s": round(elapsed, 2),
        "translated_segments": translated_segments,
        "warnings_from_translate_html": warnings,
        "batch_fallbacks": batch_fallbacks,
        "call_summary": summarize_calls(translator.calls),
        "audit": audit,
    }
    write_json(report_path, report)
    print(
        "done "
        f"{article_label(source_path)} elapsed={elapsed:.1f}s "
        f"calls={len(translator.calls)} prompt_leaks={audit['prompt_leak_count']} "
        f"sentinels={audit['visible_sentinel_leak_count']}",
        flush=True,
    )
    return report


def run(args: argparse.Namespace) -> int:
    if args.disable_abbrev_mask:
        gemma_html._apply_abbrev_mask = lambda text: (text, {})

    base_url = resolve_base_url(
        args.base_url,
        start_server=args.start_server,
        timeout_s=args.timeout_s,
    )
    api_model = args.model
    if args.auto_load:
        api_model = load_lms_model(
            args.model,
            context_length=args.context_length,
            gpu=args.gpu,
            parallel=args.parallel,
            ttl=args.ttl,
            identifier=args.identifier,
            timeout_s=args.load_timeout_s,
        )
        print(
            f"loaded: model_key={args.model} api_model={api_model} "
            f"context_length={args.context_length}",
            flush=True,
        )
        if args.unload_after:
            atexit.register(unload_lms_model, api_model, timeout_s=120, missing_ok=True)

    input_dir = Path(args.input_dir).resolve(strict=False)
    output_root = Path(args.output_dir).resolve(strict=False) / args.run_name
    sources = find_source_files(input_dir, output_root)
    if args.article_regex:
        pattern = re.compile(args.article_regex, re.IGNORECASE)
        sources = [path for path in sources if pattern.search(str(path)) or pattern.search(article_label(path))]
    if args.article_limit:
        sources = sources[: args.article_limit]
    if not sources:
        raise SystemExit(f"No {STAGE_INPUT_NAME} files found in {input_dir}")

    output_root.mkdir(parents=True, exist_ok=True)
    print(f"output: {output_root}", flush=True)
    print(f"model : {args.model}", flush=True)
    print(f"api   : {api_model}", flush=True)
    print(f"url   : {base_url}", flush=True)
    if args.disable_abbrev_mask:
        print("abbrev_mask: disabled", flush=True)

    reports = []
    started = perf_counter()
    for idx, source_path in enumerate(sources, start=1):
        label = safe_name(article_label(source_path))
        article_dir = output_root / f"{idx:02d}_{label}"
        print(f"=== {idx}/{len(sources)} {label} ===", flush=True)
        try:
            reports.append(
                translate_one(
                    source_path,
                    article_dir,
                    args,
                    base_url=base_url,
                    api_model=api_model,
                )
            )
        except Exception as exc:
            report = {
                "status": "error",
                "source_html_path": str(source_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            write_json(article_dir / "translation_report.json", report)
            reports.append(report)
            if args.stop_on_error:
                raise

    summary = {
        "run_name": args.run_name,
        "model": args.model,
        "api_model": api_model,
        "base_url": base_url,
        "context_length": args.context_length if args.auto_load else None,
        "abbrev_mask_enabled": not args.disable_abbrev_mask,
        "started_at": timestamp(),
        "elapsed_s": round(perf_counter() - started, 2),
        "article_count": len(reports),
        "completed_count": sum(1 for item in reports if item.get("status") == "completed"),
        "error_count": sum(1 for item in reports if item.get("status") == "error"),
        "hard_error_article_count": sum(
            1
            for item in reports
            if item.get("status") == "completed" and item.get("audit", {}).get("hard_errors")
        ),
        "articles": reports,
    }
    write_json(output_root / "summary.json", summary)
    return 0 if summary["error_count"] == 0 and summary["hard_error_article_count"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate polished EN HTML stages through LM Studio instruct models."
    )
    parser.add_argument("--input-dir", default="manual_review_en_polish_inlined_2026-04-27_round6")
    parser.add_argument("--output-dir", default="bench_lmstudio_instruct")
    parser.add_argument("--run-name", default="lmstudio_instruct_probe")
    parser.add_argument("--article-regex", default="")
    parser.add_argument("--article-limit", type=int, default=0)
    parser.add_argument("--base-url", default="auto")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--context-window-segments", type=int, default=4)
    parser.add_argument("--context-overlap-segments", type=int, default=1)
    parser.add_argument("--context-max-window-chars", type=int, default=20000)
    parser.add_argument("--max-chunk-chars", type=int, default=1800)
    parser.add_argument("--quality-gate-max-segments", type=int, default=8)
    parser.add_argument("--disable-quality-gate", action="store_true")
    parser.add_argument("--cjk-gate-max-segments", type=int, default=8)
    parser.add_argument("--disable-cjk-gate", action="store_true")
    parser.add_argument("--disable-marker-batching", action="store_true")
    parser.add_argument("--disable-abbrev-mask", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--auto-load", action="store_true")
    parser.add_argument("--context-length", type=int, default=DEFAULT_CONTEXT_LENGTH)
    parser.add_argument("--gpu", default="max")
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--ttl", type=int, default=3600)
    parser.add_argument("--identifier", default="")
    parser.add_argument("--load-timeout-s", type=int, default=1800)
    parser.add_argument("--unload-after", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(list(argv) if argv is not None else None))
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        print("")
        print("Check that LM Studio local server is running and that --base-url points to it.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
