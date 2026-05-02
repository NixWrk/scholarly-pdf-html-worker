# pdf-html-translator

A focused extraction of the Zotero PDF -> Marker HTML -> polished EN HTML -> Gemma LM Studio RU HTML pipeline from `ZoteroPDF_2_MD`.

The extraction intentionally excludes the Tkinter GUI and large benchmark/manual-review outputs. It keeps the pipeline modules, Gemma HTML translation engine, LM Studio runners, and a small CLI/container scaffold.

## Pipeline

1. Read local Zotero data from `zotero.sqlite` and `storage`.
2. Resolve PDF attachments in a collection.
3. Stage PDFs with short deterministic aliases for Marker.
4. Run `marker` batch conversion with `marker_single` fallback.
5. Save HTML stages:
   - `01.en.raw.html`
   - `02.en.polish.html`
6. Translate `02.en.polish.html` to Russian through LM Studio/Gemma:
   - `03.ru.translate.html`

## Install

```powershell
pip install -e .
```

Runtime requirements outside this package:

- `marker` and `marker_single` available in `PATH`.
- LM Studio local server and `lms` CLI for auto-load/unload translation runs.

## Convert Zotero PDFs To EN HTML

```powershell
pdf-html-convert-zotero `
  --zotero-data-dir "C:\Users\YOU\Zotero" `
  --collection-key "COLLECTION_KEY" `
  --output-dir "D:\work\pdf-html-output" `
  --include-subcollections
```

Output HTML stages are saved under each article folder in `_z2m_stages`.

## Translate EN HTML To RU HTML

```powershell
pdf-html-translate `
  --input-dir "D:\work\pdf-html-output" `
  --output-dir "D:\work\pdf-html-runs" `
  --run-name "gemma4_26b_run" `
  --model "p6_google_gemma-4-26b-a4b@q6_k" `
  --auto-load `
  --context-length 32768 `
  --identifier "gemma4_26b_q6_ctx32768" `
  --max-tokens 8192 `
  --timeout-s 900 `
  --load-timeout-s 1800 `
  --unload-after
```

The translated file for each article is `03.ru.translate.html`.

## Container Notes

The included Dockerfile is a scaffold. It installs this project but leaves Marker/model runtime choices explicit, because GPU/CUDA and Marker installation tend to be host-specific.

For LM Studio from a container, use a reachable host URL such as `http://host.docker.internal:<port>/v1` instead of container-local `127.0.0.1`.

## Source Layout

- `src/zoteropdf2md/` - extracted pipeline and translation modules.
- `src/pdf_html_translator/cli/` - small CLI wrappers for the extracted pipeline.
- `experiments/lmstudio_instruct_translation/` - maintained Gemma/LM Studio translation runner.
- `docs/` - decision/playbook documents kept with the extraction.
