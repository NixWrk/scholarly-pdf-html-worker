# pdf-html-translator

A focused `PDF -> Marker HTML -> polished source HTML -> optional Gemma LM
Studio RU HTML` pipeline extracted from `ZoteroPDF_2_MD`.

The extraction intentionally excludes the Tkinter GUI and large benchmark/manual-review outputs. It keeps the pipeline modules, Gemma HTML translation engine, LM Studio runners, and a small CLI/container scaffold.

This repository is intentionally Zotero-agnostic at the automation boundary:
pass it PDF files and output directories; any Zotero lookup, queueing,
write-back, WebDAV, or Web API work belongs to the caller.

## Pipeline

1. Receive one or more local PDF paths.
2. Stage PDFs with short deterministic aliases for Marker.
3. Run `marker` batch conversion with `marker_single` fallback.
4. Build a PDF-derived citation profile from the original source PDF.
   - The profile uses PDF links/named destinations and optional
     Zotero/pdf.js overlay JSON.
   - Citation/internal-link recovery in EN polish is not derived from
     `01.en.raw.html` alone.
5. Save HTML stages:
   - `01.en.raw.html`
   - `02.en.polish.html`
6. Detect source language from the polished HTML/text.
7. Translate English `02.en.polish.html` to Russian through LM Studio/Gemma:
   - `03.ru.translate.html`

Source language detection currently recognizes `en`, `ru`, `de`, `fr`, `es`,
`it`, `pt`, `nl`, `pl`, `ja`, `zh`, plus `mixed` and `unknown`. The automation
caller uses this as a language gate: English is translated to Russian;
non-English, mixed, and unknown documents are not sent to the English-to-Russian
translation runner.

## Install

```powershell
pip install -e ".[math,pdf-text-detect]"
```

Runtime requirements outside this package:

- `marker` and `marker_single` available in `PATH`.
- Node.js plus a Zotero/pdf.js `generic-legacy` build for Zotero overlay
  citation recovery, unless you pass prebuilt `*.overlays.json` files.
- LM Studio local server and `lms` CLI for auto-load/unload translation runs.

The Docker image installs `marker-pdf==1.10.2`, which provides `marker` and
`marker_single`. It does not install the Windows LM Studio `lms` CLI; container
translation should normally connect to a running LM Studio server through
`--base-url http://host.docker.internal:1234/v1`. Use `--auto-load` only in an
image/environment where `lms` is available.

## Convert PDF Files To EN HTML

```powershell
pdf-html-convert `
  --pdf "D:\work\paper.pdf" `
  --output-dir "D:\work\pdf-html-output" `
  --zotero-overlay-dir "D:\work\zotero-overlays" `
  --export-mode html
```

Output HTML stages are saved under each article folder in `_z2m_stages`.
`--zotero-overlay-dir` is optional; when present, matching Zotero/pdf.js
`*.overlays.json` files are used for citation-link recovery before automatic
overlay generation is attempted.

Important: `02.en.polish.html` is not a pure function of `01.en.raw.html` for
link quality. The production path also passes a citation profile built from the
source PDF, optionally enriched with Zotero/pdf.js overlays. Raw-only repolish
helpers can be useful for text, float, math, or layout checks, but they are not
valid for citation/internal-link regression checks.

For link-sensitive repolish experiments, use `scripts/pdf_profile_lab.py` with a
`_source_filename_map.csv` beside the raw stages. The CSV must include
`alias_pdf_path` and `source_pdf_path` columns so the lab can rebuild the same
PDF-derived citation profiles used by production. Pass `--zotero-overlay-dir`
when the run should reuse prebuilt Zotero/pdf.js `*.overlays.json` files.

Multiple PDFs can be passed by repeating `--pdf`:

```powershell
pdf-html-convert `
  --pdf "D:\work\paper-1.pdf" `
  --pdf "D:\work\paper-2.pdf" `
  --output-dir "D:\work\pdf-html-output" `
  --export-mode html
```

The installed public converter is `pdf-html-convert`. Zotero lookup and write-back
are intentionally outside this repository.

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

The included Dockerfile installs Marker, Node.js, the local overlay probe, and
the optional math/PDF-text dependencies used by the HTML polish path. For Zotero
overlay citation recovery, mount or provide a Zotero/pdf.js `generic-legacy`
build and set `Z2M_ZOTERO_PDFJS_DIR`, or pass prebuilt overlays with
`--zotero-overlay-dir`.

For LM Studio from a container, use a reachable host URL such as `http://host.docker.internal:<port>/v1` instead of container-local `127.0.0.1`.

## Source Layout

- `src/zoteropdf2md/` - extracted conversion, polish, web-polish, quality-loop, and translation modules.
- `src/pdf_html_translator/cli/` - small CLI wrappers for the extracted pipeline.
- `src/zoteropdf2md/translation/` - packaged Gemma/LM Studio translation runner used by `pdf-html-translate`.
- `experiments/lmstudio_instruct_translation/` - compatibility and benchmark wrappers around the packaged translation runner.
- `docs/` - decision/playbook documents kept with the extraction.
