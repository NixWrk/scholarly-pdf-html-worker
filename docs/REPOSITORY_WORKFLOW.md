# Repository Workflow

This document is the canonical execution order for the current repository.
Older notes in `docs/` are useful context, but this file describes the workflow
that new production runs, quality checks, and cleanup patches should follow.

## Operating Boundary

`pdf-html-polish` is a file-based PDF-to-polished-HTML tool. The production
input is a list of existing local PDF files plus an output directory. Those PDF
paths may point directly into Zotero storage, for example:

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
pdf-html-polish --pdf <local-pdf> --output-dir <run-dir> --export-mode html
```

Repeat `--pdf` for batches. Zotero collection lookup and Zotero write-back are
not part of the public CLI in this extraction. If a caller wants to process a
Zotero library, it should resolve the wanted Zotero storage PDF paths first and
then pass those paths to `--pdf`.

## Production Conversion Sequence

Run this sequence when generating polished EN HTML from source PDFs.

1. Select source PDFs.

   Use existing local PDF paths. Direct Zotero storage paths are valid. Keep the
   selected path list stable if the run will be used as a quality baseline.

2. Start the PDF conversion pipeline.

   ```powershell
   pdf-html-polish `
     --pdf "C:\PC\Zotero\Zotero_Elvis_Data\storage\ABC12345\paper.pdf" `
     --pdf "C:\PC\Zotero\Zotero_Elvis_Data\storage\DEF67890\paper.pdf" `
     --output-dir "review_runs\pdf_to_polish_YYYYMMDD_01" `
     --export-mode html
   ```

   Add `--zotero-overlay-dir <dir>` only when prebuilt Zotero/pdf.js
   `*.overlays.json` files are part of the run.

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

After a production PDF-to-polish run, run the quality loop against the converted
root. This is the normal post-conversion check and repair path.

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
- `pdf-html-polish --export-mode html` completed with `failed=0`.
- The output root contains `_source_filename_map.csv` and article directories
  with `_pdf_html_polish_stages/01.en.raw.html` and
  `_pdf_html_polish_stages/02.en.polish.html`.
- The repair-enabled `llm_quality_loop.py observe --converted-roots ...` run
  completed.
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
