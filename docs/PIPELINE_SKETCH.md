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

5. `zoteropdf2md.single_file_html.inline_images_from_html_file()`
   - inlines image assets
   - calls `polish_html_document()`
   - saves `02.en.polish.html` through `html_stages.save_html_stage()`

6. `experiments/lmstudio_instruct_translation/run_html_probe.py`
   - finds `02.en.polish.html`
   - calls `zoteropdf2md.gemma_html.translate_html_text_nodes()`
   - writes `03.ru.translate.html`

Some legacy extraction modules still exist in the source tree, but the public
automation boundary is file-based: PDF in, HTML out.
