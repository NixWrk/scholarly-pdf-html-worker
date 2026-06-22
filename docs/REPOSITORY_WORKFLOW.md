# Repository Workflow

This document is the canonical execution order for the current repository.
Older notes in `docs/` are useful context, but this file describes the workflow
that new production runs, quality checks, and cleanup patches should follow.

## Operating Boundary

`pdf-html-polish` is the canonical file-based PDF-to-audited-polished-HTML tool.
It runs the PDF conversion stage and then the repair-enabled quality loop over
the converted raw stages. The production input is a list of existing local PDF
files plus an output directory. Those PDF paths may point directly into Zotero
storage, for example:

```powershell
C:\PC\Zotero\Zotero_Elvis_Data\storage\ABC12345\paper.pdf
C:\Users\ELVIS_NIX\Zotero\storage\ABC12345\paper.pdf
```

The repository does not require a separate `source_exports` copy before
conversion. `source_exports`, filename maps, and converted-stage metadata are
fallbacks for diagnostics and historical runs, not the preferred production
entry point.

The public CLI is:

```powershell
pdf-html-polish --pdf <local-pdf> --output-dir <run-dir>
```

Repeat `--pdf` for batches. There is no public partial-conversion production
mode. For new document processing, the command always follows conversion with
the repair-enabled quality loop. Take the final audited HTML from the quality
run's `final_html/` directory.

Zotero collection lookup and Zotero write-back are not part of the public CLI in
this extraction. If a caller wants to process a Zotero library, it should resolve
the wanted Zotero storage PDF paths first and then pass those paths to `--pdf`.

## Classic Clean PDF-To-Polish Pipeline

Use this route for a new PDF when the goal is the maximum cleanup available from
the accumulated repository rules and repair stages.

```powershell
pdf-html-polish `
  --pdf "C:\PC\Zotero\Zotero_Elvis_Data\storage\ABC12345\paper.pdf" `
  --output-dir "review_runs\paper_YYYYMMDD_01" `
  --quality-output-dir "review_runs\paper_YYYYMMDD_01_quality" `
  --jobs 32
```

The command performs both major stages:

1. `run_pipeline(... export_mode=html)` creates production converted stages
   under `--output-dir`.
2. `llm_quality_loop.py observe --converted-roots <output-dir>` runs the
   repair-enabled repolish/audit/recovery loop under `--quality-output-dir`.
3. The clean pipeline publishes the audited quality-run `02.en.polish.html`
   back into the converted stage directory and verifies that the article
   directory keeps exactly two HTML files: `01.en.raw.html` and the latest
   audited `02.en.polish.html`.

The final HTML for downstream use is:

```text
<quality-output-dir>\final_html\<article-id>.html
```

The low-level `observe` command remains read-only with respect to the converted
tree. The public `pdf-html-polish` pipeline adds the explicit publication step
after `observe`, so the converted tree does not retain stale generated HTML
copies. The quality run is still the auditable final artifact set, and its
`audit_tree\<article-id>\02.en.polish.html` files are the source for both
`final_html/` and the published converted-stage polish.

Important reports for deciding whether the document is clean enough:

- `quality_gate_report.json`
- `audit_full_checks.json`
- `p62_image_recovery_report.json`
- `polish_auto_repair_report.json`
- `manual_review_queue.json`
- `article_review\index.html`
- `converted_stage_publish_report.json`

## Production Conversion Sequence

The public CLI performs this sequence internally. The first-stage converter is
an internal implementation detail; do not expose it as a Zotero worker
production mode.

1. Select source PDFs.

   Use existing local PDF paths. Direct Zotero storage paths are valid. Keep the
   selected path list stable if the run will be used as a quality baseline.

2. Start the clean PDF-to-polish pipeline.

   ```powershell
   pdf-html-polish `
     --pdf "C:\PC\Zotero\Zotero_Elvis_Data\storage\ABC12345\paper.pdf" `
     --pdf "C:\PC\Zotero\Zotero_Elvis_Data\storage\DEF67890\paper.pdf" `
     --output-dir "review_runs\pdf_to_polish_YYYYMMDD_01" `
     --quality-output-dir "review_runs\pdf_to_polish_YYYYMMDD_01_quality"
   ```

   Add `--zotero-overlay-dir <dir>` only when prebuilt Zotero/pdf.js
   `*.overlays.json` files are part of the run.

   On success, the converted article directory is normalized to the storage
   contract. There should be no extra `.html` files beside the raw/polish stage
   pair.

3. `discover_source_pdfs` validates direct PDF paths.

   Missing paths and non-PDF files are skipped and counted as unresolved. Direct
   PDF mode does not inspect Zotero collections or metadata.

4. `detect_existing_results` applies skip-existing logic.

   Existing output is detected through `_source_filename_map.csv` and output
   artifact folders, so duplicate visible filenames do not collide with earlier
   runs.

5. `stage_resolved_pdfs` creates Marker-safe aliases.

   PDFs are hardlinked or copied into a runtime staging directory with short
   deterministic aliases. The output root receives `_source_filename_map.csv`
   with `source_pdf_path` and `alias_pdf_path`; this map is part of the
   production contract because later audits use it to recover source PDFs.

6. `MarkerRunner.run_batch` runs Marker.

   The pipeline calls `marker` for the staged batch. If expected artifacts are
   missing or unchanged afterward, it calls `marker_single` for the remaining
   files.

7. Raw HTML is snapshotted.

   For HTML export mode, each article folder gets
   `_pdf_html_polish_stages/01.en.raw.html` plus stage logs. The legacy
   `_z2m_stages` name is still recognized by audit/repolish helpers, but new
   output should use `_pdf_html_polish_stages`.

8. OCR quality is checked.

   `assess_ocr_quality_from_html` may enqueue weak OCR candidates into the
   run's re-OCR queue. This is an operational follow-up; it does not replace the
   normal polish/audit path for successfully converted documents.

9. The PDF-derived citation profile is built from the original source PDF.

   `build_citation_profile_from_pdf` reads the source PDF, not just
   `01.en.raw.html`. It uses PDF links and named destinations, and it merges a
   matching Zotero/pdf.js overlay when one is available.

10. Polish and image inlining produce final EN HTML.

   `polish_and_inline_html_file` calls
   `polish_html_document(citation_profile=...)`, inlines image assets, writes
   the HTML artifact, and snapshots
   `_pdf_html_polish_stages/02.en.polish.html`.

11. Run history is updated.

   Successfully converted source PDFs are appended to the local history. The
   CLI prints the output directory, resolved PDF count, converted count, OCR
   queue counts, and failed count.

## Mandatory Quality Loop After Production Conversion

The public `pdf-html-polish` command runs the quality loop automatically. If a
developer manually creates a converted root while debugging an internal boundary,
they must run the same quality loop against that converted root before using the
HTML downstream.

```powershell
python scripts\llm_quality_loop.py observe `
  --converted-roots "review_runs\pdf_to_polish_YYYYMMDD_01" `
  --out-dir "review_runs\pdf_to_polish_YYYYMMDD_01_quality" `
  --run-id "pdf_to_polish_YYYYMMDD_01_quality" `
  --previous-entry "<previous-compatible-quality_history_entry.json>" `
  --jobs 32
```

`--converted-roots` defaults to the full repair-enabled path:

1. `prepare_converted_raw_cache` copies every production `01.en.raw.html` into
   an internal `_converted_raw_source/raw_cache`.
   The generated citation-profile fallback accepts high-confidence inferred
   styles and medium-confidence author-year evidence; that keeps converted PDF
   articles with author-year prose from falling back to `unknown:low` and losing
   bibliography link recovery.

2. If `_source_filename_map.csv` or `full_source_filename_map.csv` is found
   above the converted roots, `source_pdf_path` is copied into the converted
   manifest so diagnostics can use the original Zotero/source PDF directly.

3. `repolish_cached_run` regenerates `02.en.polish.html` into the observe
   run's own `polish/` and `audit_tree/` directories without writing back to the
   production conversion output.

4. The configured test command runs before audit. The default gate config uses
   `python -m pytest -q`.

5. `write_source_pdf_map_for_run` writes `source_pdf_map.json` for PDF text
   diagnostics. Source PDF resolution checks, in order, include:
   manifest `source_pdf_path` fields, stage-related source-export metadata,
   Zotero storage by attachment key, and Zotero title matching. The configured
   Zotero roots are `C:\PC\Zotero` and `C:\Users\ELVIS_NIX\Zotero`, with
   optional prefix maps from `HTML_DOCKER_MOUNT_PREFIX_MAP` and
   `ZOTERO_PATH_PREFIX_MAP`.

6. `audit_en_polish.py` runs with PDF diagnostics and the resolved PDF map when
   available.
   Citation-style audit treats an author-year article with bibliography
   `ref-*` targets but zero body `#ref-*` links as `P99` error, so missing
   author-year bibliography links cannot pass the final quality gate silently.
   P55 audit and auto-repair keep valid author-year `#ref-*` links when the
   anchor label matches the bibliography target by surname and year.

7. P62 marker recovery planning runs when configured.

8. P62 image recovery runs when configured. It may call Marker on source PDFs,
   render source PDF pages, patch missing figure warnings, and refresh
   assessment data.

9. `polish_auto_repair` runs when configured. It patches supported recurring
   issues such as OCR residues, numeric reference labels, broken internal links,
   spaced multipanel references, flattened unit exponents, and duplicate figure
   visual cases.

10. If repair stages patched articles, audit is rerun. Targeted audit is used
    when every patched article can be isolated; otherwise the full audit is
    rerun.

11. Quality history is recorded and compared with the previous compatible run.
    Compare only runs with compatible article ids and source kind. Do not treat
    a `cached_raw_repolish` run and a different `converted_stage_roots` corpus
    as an apples-to-apples regression comparison.

12. The loop writes manual review queues, article review bundles, accumulated
    pattern observations, manual observation summaries, resolver decisions,
    `llm_analysis_pack.json`, `llm_analysis_prompt.md`, and the gate report.

Use `--audit-converted-existing` only for a readonly inspection of existing
`02.en.polish.html` files. That mode deliberately does not repolish and does
not run repair stages, so it is not the canonical final quality check.

After a manual `observe` run finishes and is accepted, publish the audited
polish back into the converted tree before handing that tree to downstream
automation. Run the publish command first as a dry-run, then repeat with
`--apply` only after the report points at the intended converted root:

```powershell
pdf-html-polish-stage-contract publish `
  --quality-run-dir "review_runs\pdf_to_polish_YYYYMMDD_01_quality" `
  --converted-root "review_runs\pdf_to_polish_YYYYMMDD_01" `
  --out-report "C:\tmp\publish_latest_dry_run.json"
```

The publication step never modifies `01.en.raw.html`. It replaces the matching
source `02.en.polish.html` with the audited quality-run polish, prunes stale
generated HTML copies, and writes `converted_stage_publish_report.json`.

Use this verification command to prove an existing converted tree already
satisfies the two-HTML storage contract:

```powershell
pdf-html-polish-stage-contract verify `
  --root "D:\Elvis_projects\Zotero_Automation\Zotero_automatization\data\html\converted" `
  --out-report "C:\tmp\converted_stage_contract.json" `
  --fail-on-violations
```

## Required Observe Acceptance Gate

For production-quality validation and for meaningful behavior refactors, the
required gate is a full repair-enabled observe run over the converted corpus.
Do not replace it with a readonly audit, a raw-only repolish, or a partial
article sample when declaring repository quality unchanged.

The required command shape is:

```powershell
python scripts\llm_quality_loop.py observe `
  --converted-roots "<production-conversion-root>" `
  --out-dir "review_runs\<descriptive_observe_run_id>" `
  --run-id "<descriptive_observe_run_id>" `
  --previous-entry "<previous-compatible-quality_history_entry.json>" `
  --jobs <parallel-worker-count>
```

The acceptance checklist is:

- The observe run completes without process errors.
- The configured test command exits with code `0`.
- The final audit used for `quality_history_entry.json` exits with code `0`.
- `source_pdf_map.json` is `ready`; for Zotero-backed production corpora, every
  article is either mapped to an existing Zotero/source PDF or explicitly
  recorded as unavailable.
- Repair stages run according to the gate config. When P62 image recovery or
  `polish_auto_repair` patches articles, the final quality history must come
  from the post-repair rerun audit.
- `quality_compare.json` compares against a compatible previous entry. A
  successful quality-neutral refactor has `regression_count=0`; remaining gate
  failures must be explicit mandatory-review backlog, not hidden regressions.
- `quality_gate_report.json` is the authoritative gate result. A failing gate
  may be accepted only as documented follow-up when the compare report shows no
  regressions and the remaining mandatory items are enumerated.
- If the converted tree will be reused downstream, the audited polish has been
  published back with `pdf-html-polish-stage-contract publish --apply`, and
  `converted_stage_publish_report.json` records
  `stage_contract_status=pass`.

The 2026-06-22 reference run
`review_runs\full_pdf_to_polish_repair_observe_20260622_01` is the current
example of this required gate shape: it repolished the converted full
PDF-to-polish corpus, ran the test suite, used Zotero source-PDF mapping,
executed P62 recovery and polish auto-repair, reran targeted audit after
patches, and compared against
`review_runs\full_pdf_to_polish_from_source_map_chunked_audit_20260620_02\quality_history_entry.json`.

## Quality Loop For Existing Cached Runs

Use this mode when the input is already a cached run with `raw_cache/` and
`profiles/`:

```powershell
python scripts\llm_quality_loop.py observe `
  --source-run-dir "<run-with-raw_cache-and-profiles>" `
  --out-dir "review_runs\cached_repolish_YYYYMMDD_01" `
  --run-id "cached_repolish_YYYYMMDD_01" `
  --previous-entry "<previous-compatible-quality_history_entry.json>" `
  --jobs 32
```

This path is also repair-enabled. It repolishes every accepted EN document,
runs tests, audits, runs configured repair stages, reruns audit after patches,
records history, and evaluates the gate.

## Standalone Diagnostic Modes

These commands are useful, but they are not replacements for the canonical
production conversion plus repair-enabled observe run.

- `scripts/audit_en_polish.py --roots ...`

  Direct audit of raw/polish stage pairs. Use it for focused diagnostics or
  targeted checks. For PDF-grounded checks, pass `--pdf-diagnostics` and
  `--pdf-map`.

- `scripts/repolish_en_from_raw.py --roots ...`

  Raw-HTML-only repolish. It does not rebuild PDF-derived citation profiles and
  should not be used to judge citation/internal-link production parity.

- `scripts/pdf_profile_lab.py`

  Link-sensitive repolish lab. Use it when `_source_filename_map.csv` is
  available and the experiment needs to rebuild citation profiles from source
  PDFs.

- `scripts/refactor_article_check.py`

  Small refactor sanity helper for rerunning article-level checks. It is not a
  corpus gate.

## Patch And Cleanup Workflow

For repository cleanup or behavior patches, use this order.

1. Read the local owner modules and tests before editing.

2. Make the smallest scoped change that preserves the production sequence above.

3. Add focused regression tests for changed behavior. Documentation-only
   changes do not need pytest, but they should pass `git diff --check`.

4. Run targeted tests for the touched area.

5. Run the full test suite before behavior commits:

   ```powershell
   python -m pytest -q
   ```

6. For behavior affecting `single_file_html.py`, audit logic, repair stages, or
   source-PDF resolution, run a repair-enabled observe pass before declaring the
   patch quality-neutral.

7. For larger polish refactors, first run polish/audit parity on an existing
   corpus. Only after that passes should a full PDF-to-polish production batch
   be rerun.

8. Commit each completed stage separately with the tests or checks that justify
   it.

## Completion Criteria For A Final Production Run

A run is production-ready when all of the following are true:

- The input PDF list is stable and points to existing local PDFs, including
  direct Zotero storage paths when appropriate.
- `pdf-html-polish` completed, or the equivalent internal manual sequence
  conversion stage plus repair-enabled `llm_quality_loop.py observe
  --converted-roots ...` completed.
- The primary conversion stage completed with `failed=0`.
- The output root contains `_source_filename_map.csv` and article directories
  with `_pdf_html_polish_stages/01.en.raw.html` and
  `_pdf_html_polish_stages/02.en.polish.html`.
- The converted article directories satisfy the two-HTML storage contract:
  exactly `01.en.raw.html` plus the latest audited `02.en.polish.html`; no
  stale generated `.html` copies remain.
- The repair-enabled quality run completed and collected final audited HTML in
  `<quality-output-dir>\final_html\`.
- `converted_stage_publish_report.json` exists and has
  `stage_contract_status=pass`.
- `source_pdf_map.json` maps source PDFs for the corpus or records explicit
  unavailable candidates.
- P62 recovery and polish auto-repair reports were produced when enabled by the
  gate config.
- The final audit after repairs is the audit used for quality history and gate
  evaluation.
- The gate passes against a compatible previous entry, or the report explicitly
  records that no previous entry was available.
- Remaining manual review items are either resolved, accepted as telemetry, or
  documented as follow-up work.
