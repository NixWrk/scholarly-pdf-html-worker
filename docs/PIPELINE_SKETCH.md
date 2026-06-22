# Pipeline Sketch

Current production path in this extraction:

1. `pdf-html-polish --pdf ...`
   - receives exact local PDF paths from the caller
   - runs the conversion stage
   - runs the repair-enabled converted-root quality loop
   - publishes the audited polish back into the converted stage tree
   - verifies the converted stage tree keeps exactly two HTML files per article:
     `01.en.raw.html` and the latest audited `02.en.polish.html`
   - collects final audited HTML under `<quality-output-dir>/final_html`

Internal conversion stage:

1. `pdf_html_polish.pipeline.run_pipeline(... export_mode="html")`
   - receives exact local PDF paths from the caller
   - does not inspect Zotero metadata, collections, WebDAV, or Web API state

2. `pdf_html_polish.pipeline.discover_source_pdfs()`
   - validates that each source is an existing PDF
   - builds in-memory source records for staging

3. `pdf_html_polish.staging.stage_resolved_pdfs()`
   - creates short aliases
   - hardlinks/copies PDFs into a runtime staging directory

4. `pdf_html_polish.marker_runner.MarkerRunner`
   - `run_batch()` calls `marker`
   - `run_single()` calls `marker_single` fallback

5. `pdf_html_polish.citation_profile.build_citation_profile_from_pdf()`
   - reads the original source PDF, not the raw HTML stage
   - extracts PDF links/named destinations for citation, figure, and table
     recovery
   - merges matching Zotero/pdf.js `*.overlays.json` data when supplied through
     `--zotero-overlay-dir`

6. `pdf_html_polish.single_file_html.polish_and_inline_html_file()`
   - inlines image assets
   - calls `polish_html_document(citation_profile=...)`
   - saves `02.en.polish.html` through `html_stages.save_html_stage()`

7. `scripts/llm_quality_loop.py observe --converted-roots ...`
   - copies converted `01.en.raw.html` into an internal quality-loop cache
   - applies deterministic repolish, repair, audit, and gate stages
   - writes audited `02.en.polish.html` under the quality run's `audit_tree/`

8. `pdf_html_polish.stage_contract.publish_latest_polish_from_quality_run()`
   - copies the audited quality-run `02.en.polish.html` back over the matching
     converted-stage `02.en.polish.html`
   - never modifies `01.en.raw.html`
   - removes stale generated `.html` copies from the converted article
     directory
   - writes `converted_stage_publish_report.json`

The former EN-to-RU translation runner and publisher web-HTML polish commands
are intentionally outside this repository. The public automation boundary is
file-based: PDF in, audited polished EN HTML out.

`01.en.raw.html` is not enough to reproduce production citation/internal-link
behavior. Use `scripts/pdf_profile_lab.py` plus `_source_filename_map.csv` for
link-sensitive repolish checks. `scripts/repolish_en_from_raw.py` deliberately
does not build or pass PDF citation profiles and should only be used for
raw-HTML-only polish checks.

For a new PDF, do not stop at the internal conversion stage when the goal is the
cleanest result. The accumulated repair knowledge is applied by the clean
wrapper's quality loop. The downstream artifact should be the collected
`final_html/*.html` file, while the converted stage tree is retained only as the
raw source plus the latest audited polish snapshot.
