# LLM Quality Loop

This repository keeps the LLM in the loop, not in charge of the loop. The
workflow is:

1. Scan every cached raw HTML file and regenerate EN polish for every accepted
   EN document with its citation profile.
2. Run focused regression tests for every new artifact fix, then run the full
   configured project test suite.
3. Run the full EN polish audit.
4. Group every article-level manifestation into global pattern observations and
   append them to the cumulative pattern history.
5. Record every newly spotted manual manifestation in the append-only manual
   observation ledger before promoting it into an audit pattern, repair, or
   false-positive rule.
6. During problem analysis, render the implicated source PDF page or pages,
   extract the PDF text layer for those same pages, and compare both signals
   against `01.en.raw.html` and `02.en.polish.html` before classifying the root
   cause or choosing a repair. This is mandatory because the PDF text layer can
   be correct while the generated HTML is broken. Record both evidence paths in
   the analysis notes. If the stage-local PDF is missing for a converted-stage
   artifact, search the Zotero/source_exports PDF candidates recorded in the
   pack before declaring the source PDF unavailable.
7. If one `P*` defect id mixes different root causes or artifact mechanisms,
   split or refine the classification before, or together with, the repair.
   For example, body citation failures stay in `P04`, while table/float
   citation-like ranges and math/measurement ranges are tracked separately so
   their counts do not hide the real citation-parser backlog. Classification
   precision applies to text-pattern defects too: real roman-suffix word
   splits stay in `P45`, while affiliation labels, already-tagged superscript
   markers, linked suffix boundaries, and rendered math variables are tracked
   as telemetry-only `P45A`/`P45S`/`P45L`/`P45M`.
   splits that are audit telemetry rather than a new quality regression should
   stay in pattern history but set `extra.quality_counted=false`.
8. Record all quality metrics and compare them with a previous run.
9. Evaluate gates for lower-is-better metrics.
10. Build a compact LLM analysis packet and prompt.
11. Let an engineer or coding agent make a small patch plus tests.
12. Repeat the full EN corpus loop before committing.

## Branch Workflow

Create a feature branch before experiments:

```powershell
git switch -c feature/llm-quality-loop
```

## Observe A Cached Run

Use a previous run directory that already contains `raw_cache/` and `profiles/`.
The command writes a new run directory with `polish/`, `audit_tree/`,
`audit_full_checks.json`, `quality_history_entry.json`, `quality_compare.json`,
`quality_gate_report.json`, `pattern_observations.json`,
`source_pdf_map.json`, `pdf_problem_evidence_report.json`,
`llm_analysis_pack.json`, and `llm_analysis_prompt.md`.

This is the mandatory loop shape for code patches. By default `observe` now
uses `--polish-language auto`, `--target-language en`, and skips confidently
detected non-English documents from the EN corpus audit. It scans every cached
raw HTML file from the source run, repolishes every accepted EN document, and
records `raw_count`, `article_count`, `skipped_count`, per-document language
detection, and the selected polish policy for every accepted document.

`observe` also runs the full configured project test suite by default
(`required_test_command` in `configs/llm_quality_gates.json`, currently
`python -m pytest -q`) before audit/history/gates. Use `--skip-tests` only for
exploratory audit runs that do not include code changes.

When `require_pdf_text_layer_diagnostics` is enabled in the gate config,
`observe` writes `source_pdf_map.json` and runs the audit with
`--pdf-diagnostics`, so the audit can use the original PDF text layer even when
`00.source.pdf` is absent from the stage directory.

For the articles selected into the LLM problem pack, `observe` also writes
`pdf_problem_evidence_report.json` plus `pdf_problem_evidence/` artifacts. Each
available source PDF must produce a same-page text-layer excerpt and a rendered
page image before the problem classification is considered complete. Missing
source PDFs are allowed only when the report records the unavailable candidate
state.

After every audit, `observe` must write `pattern_observations.json` and append
the current all-article pattern summary to an accumulated JSONL history. The
default history is `pattern_observation_history.jsonl` next to the output run
directory; use `--pattern-history` only to choose another append-only history
file for the same loop. Pattern history is not optional: local manifestations
are reviewed as global pattern evidence first, then recurring groups become
problem candidates across one or more iterations.

Manual review has its own append-only ledger. If a reviewer notices a text,
link, table, citation, or artifact manifestation that is not already represented
by an audit defect, record the raw observation first and keep its article,
stage path, snippet, suspected pattern, status, and test coverage state. The
default ledger is `manual_observation_ledger.jsonl` next to the output run
directory; every `observe` run writes `manual_observation_summary.json` by
grouping that cumulative ledger. A single observation remains raw evidence
unless it is severe; repeated groups across articles or iterations become
problem candidates.

```powershell
python scripts\llm_quality_loop.py observe `
  --source-run-dir .tmp_local2\source_exports_full_pdf_profile_rerun_d1100b3_2026-05-20 `
  --out-dir .tmp_local2\llm_runs\experiment_001 `
  --previous-entry .tmp_local2\source_exports_full_pdf_profile_rerun_d1100b3_2026-05-20\quality_history_entry.json `
  --run-id experiment_001 `
  --no-append-history
```

Record a newly spotted manifestation while reviewing `manual_review_queue.json`:

```powershell
python scripts\llm_quality_loop.py record-observation `
  --ledger .tmp_local2\llm_runs\manual_observation_ledger.jsonl `
  --run-dir .tmp_local2\llm_runs\experiment_001 `
  --article article_a `
  --stage-path .tmp_local2\llm_runs\experiment_001\audit_tree\article_a\02.en.polish.html `
  --snippet "Objec tive split remains in body text" `
  --suspected-pattern "inline OCR word split in ordinary text"
```

When that observation is confirmed and covered, append a status update with the
same `--observation-id` or update the existing review note in the queue. The
summary counts the latest record for each observation id, while the JSONL file
keeps the full trail. The important invariant is that the loop can reconstruct
what was seen, where it was seen, and whether audit/repair/guard tests now cover
it.

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

When the production converted tree itself is the corpus for the next loop,
convert it into an internal cached-run source and repolish that cache. This
uses every `01.en.raw.html` under the supplied converted roots, keeps the
original stage paths for image restoration and review, skips confidently
non-EN documents by default, and does not write back to `data/html/converted`.
Because converted stages do not carry the original PDF citation profiles, the
cache records a per-document citation-style inference from the raw HTML text.
Only high-confidence inferred styles are used as the effective polish profile;
medium-confidence inferences stay as diagnostics and keep the effective profile
at `unknown/low`:

```powershell
python scripts\llm_quality_loop.py observe `
  --converted-roots D:\Elvis_projects\Zotero_automatization\data\html\converted\Zotero_Elvis_Data_cfd7a6f4 D:\Elvis_projects\Zotero_automatization\data\html\converted\Zotero_Heart_n_Lung_Data_745ee21a D:\Elvis_projects\Zotero_automatization\data\html\converted\Zotero_NIX_Data_ba8b3354 `
  --repolish-converted-raw `
  --out-dir .tmp_local2\llm_runs\converted_all3_repolish_001 `
  --run-id converted_all3_repolish_001
```

Converted article ids are derived from the library, attachment key,
size/mtime directory, and document folder rather than from discovery order.
If the production corpus gains or loses files between loop iterations, the
quality comparison reports `new_articles` and `removed_articles` separately and
uses `comparable_totals_delta` for the lower-is-better gate. New documents are
still audited and queued for review, but they are not counted as regressions of
the code patch that was just made.

## Build Or Rebuild Only The LLM Pack

```powershell
python scripts\llm_quality_loop.py pack `
  --run-dir .tmp_local2\llm_runs\experiment_001 `
  --max-articles 15
```

The default pack ignores image-only defect ids from
`configs/llm_quality_gates.json`. This keeps the review focused on text,
citations, tables, structure, and OCR residue.

The generated prompt treats PDF page render and PDF text-layer evidence as
mandatory during problem analysis. For every article-local symptom selected for
repair, render the source PDF page that contains the snippet, figure, table,
footnote, or nearby page anchor; extract the text layer for that same page; and
compare both with raw and polished HTML before deciding whether the defect is a
parser bug, OCR/layout artifact, audit false positive, or missing source asset.
If `source_pdf_present=false` in the pack, inspect `source_pdf_candidates` from
Zotero/source_exports first and record the unavailable PDF as an analysis
limitation only when no candidate can be rendered.

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
- cross-article and cross-iteration accumulated patterns;
- production file/function targets;
- regression tests to add;
- risks and gates to rerun.

## Patch Policy

Each fix should be small:

- one production repair layer;
- a focused regression test for the real artifact symptom;
- at least one non-regression edge case when the repair can touch links, tags,
  math, code/pre blocks, language policy, or nearby article classes;
- all article-level manifestations grouped into `pattern_observations.json` and
  appended to the cumulative pattern history before deciding what problem to
  solve;
- PDF page render evidence checked during problem analysis for each repaired
  article-local symptom, or an explicit note that the source PDF was
  unavailable;
- newly spotted manual manifestations appended to
  `manual_observation_ledger.jsonl`, then grouped in
  `manual_observation_summary.json`, before deciding whether they are recurring
  problems;
- confirmed manual observations must get audit, repair, false-positive, or
  guard test coverage and an updated status/test status in the ledger trail;
- `P*` classification refined whenever a current pattern summary shows that a
  single defect id is hiding distinct mechanisms, such as plain text OCR
  spacing, inline-tag splits, and table-footnote word splits;
- targeted repolish for affected articles;
- full cached raw EN corpus repolish before commit: all cached raw files scanned
  and every accepted EN article repolished, with per-document auto policy and
  language stats in `manifest.json`;
- full configured project test suite must pass in the loop, or the run must be
  clearly marked as exploratory with `--skip-tests`;
- long-running repolish, test, and audit steps must emit progress and persist
  stdout/stderr command logs in the run directory; a silent long corpus run is
  not a valid loop artifact because failures and slow articles cannot be
  localized after the fact;
- gate must pass or the regression must be explicitly understood.
