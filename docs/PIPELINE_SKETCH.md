# Pipeline Sketch

Current production path in this extraction:

1. `pdf-html-convert --pdf ...`
   - receives exact local PDF paths from the caller
   - does not inspect Zotero metadata, collections, WebDAV, or Web API state

2. `zoteropdf2md.pipeline.discover_source_pdfs()`
   - validates that each source is an existing PDF
   - builds in-memory source records for staging

3. `zoteropdf2md.staging.stage_resolved_pdfs()`
   - creates short aliases
   - hardlinks/copies PDFs into a runtime staging directory

4. `zoteropdf2md.marker_runner.MarkerRunner`
   - `run_batch()` calls `marker`
   - `run_single()` calls `marker_single` fallback

5. `zoteropdf2md.citation_profile.build_citation_profile_from_pdf()`
   - reads the original source PDF, not the raw HTML stage
   - extracts PDF links/named destinations for citation, figure, and table
     recovery
   - merges matching Zotero/pdf.js `*.overlays.json` data when supplied through
     `--zotero-overlay-dir`

6. `zoteropdf2md.single_file_html.polish_and_inline_html_file()`
   - inlines image assets
   - calls `polish_html_document(citation_profile=...)`
   - saves `02.en.polish.html` through `html_stages.save_html_stage()`

The former EN-to-RU translation runner and publisher web-HTML polish commands
are intentionally outside this repository. The public automation boundary is
file-based: PDF in, polished EN HTML out.

`01.en.raw.html` is not enough to reproduce production citation/internal-link
behavior. Use `scripts/pdf_profile_lab.py` plus `_source_filename_map.csv` for
link-sensitive repolish checks. `scripts/repolish_en_from_raw.py` deliberately
does not build or pass PDF citation profiles and should only be used for
raw-HTML-only polish checks.
