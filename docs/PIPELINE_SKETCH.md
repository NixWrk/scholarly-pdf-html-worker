# Pipeline Sketch

Current production path in this extraction:

1. `zoteropdf2md.pipeline.discover_collection_pdfs()`
   - opens Zotero data
   - queries collection attachments
   - resolves local PDF paths

2. `zoteropdf2md.staging.stage_resolved_pdfs()`
   - creates short aliases
   - hardlinks/copies PDFs into a runtime staging directory

3. `zoteropdf2md.marker_runner.MarkerRunner`
   - `run_batch()` calls `marker`
   - `run_single()` calls `marker_single` fallback

4. `zoteropdf2md.single_file_html.inline_images_from_html_file()`
   - inlines image assets
   - calls `polish_html_document()`
   - saves `02.en.polish.html` through `html_stages.save_html_stage()`

5. `experiments/lmstudio_instruct_translation/run_html_probe.py`
   - finds `02.en.polish.html`
   - calls `zoteropdf2md.gemma_html.translate_html_text_nodes()`
   - writes `03.ru.translate.html`
