# LLM Quality Loop

This repository keeps the LLM in the loop, not in charge of the loop. The
workflow is:

1. Regenerate EN polish from every cached raw HTML and citation profile.
2. Run focused regression tests for every new artifact fix, plus the configured
   test command.
3. Run the full EN polish audit.
4. Record all quality metrics and compare them with a previous run.
5. Evaluate gates for lower-is-better metrics.
6. Build a compact LLM analysis packet and prompt.
7. Let an engineer or coding agent make a small patch plus tests.
8. Repeat the full EN corpus loop before committing.

## Branch Workflow

Create a feature branch before experiments:

```powershell
git switch -c feature/llm-quality-loop
```

## Observe A Cached Run

Use a previous run directory that already contains `raw_cache/` and `profiles/`.
The command writes a new run directory with `polish/`, `audit_tree/`,
`audit_full_checks.json`, `quality_history_entry.json`, `quality_compare.json`,
`quality_gate_report.json`, `llm_analysis_pack.json`, and
`llm_analysis_prompt.md`.

This is the mandatory loop shape for code patches. By default `observe` now
uses `--polish-language auto`, `--target-language en`, and skips confidently
detected non-English documents from the EN corpus audit. The manifest records
`raw_count`, `article_count`, `skipped_count`, per-document language detection,
and the selected polish policy for every accepted document.

`observe` also runs the configured test command by default
(`required_test_command` in `configs/llm_quality_gates.json`, currently
`python -m pytest -q`) before audit/history/gates. Use `--skip-tests` only for
exploratory audit runs that do not include code changes.

```powershell
python scripts\llm_quality_loop.py observe `
  --source-run-dir .tmp_local2\source_exports_full_pdf_profile_rerun_d1100b3_2026-05-20 `
  --out-dir .tmp_local2\llm_runs\experiment_001 `
  --previous-entry .tmp_local2\source_exports_full_pdf_profile_rerun_d1100b3_2026-05-20\quality_history_entry.json `
  --run-id experiment_001 `
  --no-append-history
```

For language-specific repair experiments, keep the stage shape stable. Use
`--polish-language auto` for normal EN corpus work, or pass a policy explicitly
for targeted experiments. Russian page-reference repairs can still be tested
without switching English figure/table captions:

```powershell
python scripts\llm_quality_loop.py observe `
  --source-run-dir .tmp_local2\llm_runs\experiment_001 `
  --out-dir .tmp_local2\llm_runs\experiment_001_ru_policy `
  --polish-language ru `
  --no-append-history
```

Use `--include-non-target-language` only when intentionally reviewing a mixed
corpus. For the current branch, EN runs should stay on the default EN target.

## Observe Production Converted Stages

For Zotero production output under `data/html/converted/.../_z2m_stages`,
observe the existing raw/polish pairs directly. This mode does not repolish; it
audits the current production artifacts in place, keeps duplicate document
names separate with stable artifact ids, and writes `manual_review_queue.json`
for article-by-article review.

```powershell
python scripts\llm_quality_loop.py observe `
  --converted-roots D:\Elvis_projects\Zotero_automatization\data\html\converted `
  --out-dir .tmp_local2\llm_runs\converted_313_loop_adapter_2026-05-22 `
  --run-id converted_313_loop_adapter_2026-05-22 `
  --no-append-history `
  --max-articles 20
```

Use a previous entry only when it was produced by the same converted-stage mode;
older entries that were keyed by document name can collapse duplicate Zotero
attachments and create misleading deltas.

Converted-stage observation is useful for manual review queues, but it is not a
replacement for the mandatory cached raw EN repolish loop above because it does
not regenerate `02.en.polish.html`.

## Build Or Rebuild Only The LLM Pack

```powershell
python scripts\llm_quality_loop.py pack `
  --run-dir .tmp_local2\llm_runs\experiment_001 `
  --max-articles 15
```

The default pack ignores image-only defect ids from
`configs/llm_quality_gates.json`. This keeps the review focused on text,
citations, tables, structure, and OCR residue.

## Gate Only

```powershell
python scripts\llm_quality_loop.py gate `
  --run-dir .tmp_local2\llm_runs\experiment_001 `
  --fail-on-gate
```

The gate config is in `configs/llm_quality_gates.json`. It fails on new
regressions and positive deltas for critical lower-is-better metrics such as
broken internal links, mixed citation style, replacement characters, and
table-unit section id leaks.

## Optional External LLM Command

The loop can pass the generated prompt to an explicit command. Nothing is run
unless the command is provided after `--`.

```powershell
python scripts\llm_quality_loop.py run-llm `
  --prompt .tmp_local2\llm_runs\experiment_001\llm_analysis_prompt.md `
  --out .tmp_local2\llm_runs\experiment_001\llm_analysis.md `
  -- codex exec
```

The expected LLM output is a patch plan, not blind edits:

- critical findings by article;
- cross-article patterns;
- production file/function targets;
- regression tests to add;
- risks and gates to rerun.

## Patch Policy

Each fix should be small:

- one production repair layer;
- a focused regression test for the real artifact symptom;
- at least one non-regression edge case when the repair can touch links, tags,
  math, code/pre blocks, language policy, or nearby article classes;
- targeted repolish for affected articles;
- full cached raw EN corpus repolish before commit, with per-document auto
  policy and language stats in `manifest.json`;
- configured test command must pass in the loop, or the run must be clearly
  marked as exploratory with `--skip-tests`;
- gate must pass or the regression must be explicitly understood.
