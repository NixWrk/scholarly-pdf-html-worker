# zotero-pdf-html-worker

A focused Zotero `PDF -> Marker HTML -> polished source HTML` worker. It owns the PDF-derived source HTML stage in `D:\Elvis_projects\Zotero_Automation`; Russian translation remains in the separate `zotero-html-translate-worker`.

This repository keeps the PDF-to-HTML polish path and its audit/quality-loop helpers. It intentionally does not include EN-to-RU translation or publisher web-HTML polish commands.

The public automation boundary is file-based: pass local PDF files and an output directory. Zotero collection lookup, queueing, WebDAV mirroring, and write-back belong to the main Zotero orchestrator.

The public command `pdf-html-polish` always runs the clean production pipeline:
PDF conversion followed by the repair-enabled quality loop, with final audited
HTML collected under the quality run's `final_html/` directory.

## Pipeline

Clean production pipeline:

1. Receive one or more local PDF paths.
2. Stage PDFs with short deterministic aliases for Marker.
3. Run `marker` batch conversion with `marker_single` fallback.
4. Build a PDF-derived citation profile from the original source PDF.
   - The profile uses PDF links/named destinations and optional
     Zotero/pdf.js overlay JSON.
   - Citation/internal-link recovery in EN polish is not derived from
     `01.en.raw.html` alone.
   - During converted-stage quality runs, raw HTML citation-style inference is
     also used as a fallback. High-confidence styles are accepted, and
     medium-confidence author-year evidence is accepted so author-year PDFs do
     not silently lose bibliography links.
5. Save HTML stages:
   - `01.en.raw.html`
   - `02.en.polish.html`
6. Run `llm_quality_loop.py observe --converted-roots` in repair-enabled mode.
   This reuses the converted raw stage, applies the accumulated deterministic
   repolish, PDF/P62 recovery, auto-repair, audit, and gate checks.
7. Publish the audited `02.en.polish.html` from the quality run back into the
   converted stage directory and enforce the two-HTML storage contract:
   `01.en.raw.html` plus the latest audited `02.en.polish.html`.
8. Collect the audited `02.en.polish.html` files from the quality run into
   `final_html/`.

For the full production order, including direct Zotero-storage PDF inputs,
post-conversion quality-loop repair, audit, and gate criteria, see
[`docs/REPOSITORY_WORKFLOW.md`](docs/REPOSITORY_WORKFLOW.md).

## Install

```powershell
pip install -e ".[math,pdf-text-detect]"
```

Runtime requirements outside this package:

- `marker` and `marker_single` available in `PATH`.
- Node.js plus a Zotero/pdf.js `generic-legacy` build for Zotero overlay
  citation recovery, unless you pass prebuilt `*.overlays.json` files.

The Docker image installs `marker-pdf==1.10.2`, which provides `marker` and
`marker_single`.

## Clean PDF To Audited Polished HTML

Use this command for a new document when the goal is the cleanest HTML this
repository can produce from its accumulated rules and repair stages:

```powershell
pdf-html-polish `
  --pdf "D:\work\paper.pdf" `
  --output-dir "D:\work\paper_pdf_html" `
  --quality-output-dir "D:\work\paper_pdf_html_quality" `
  --jobs 32
```

The primary conversion artifacts stay in `--output-dir`. The quality run writes
audit, repair, and gate reports under `--quality-output-dir`. The final audited
HTML files are collected here:

```text
D:\work\paper_pdf_html_quality\final_html\
```

The converted article directory is also normalized after the quality loop:
only the raw stage and the latest audited polish stage remain as HTML files.
The publication/verification report is written to:

```text
D:\work\paper_pdf_html_quality\converted_stage_publish_report.json
```

If a gate comparison against a compatible previous run is needed, add
`--previous-entry <quality_history_entry.json>`. For ordinary one-document
processing, the quality reports are still useful even without a previous entry.

## Conversion Stage

The first-stage converter is now an internal implementation detail of the clean
pipeline, not a public production mode. The clean CLI still accepts conversion
options such as `--zotero-overlay-dir`, `--no-cuda`, `--model-cache-dir`, and
Marker command overrides, but it always follows conversion with repair-enabled
quality processing.

Output HTML stages are saved under each article folder in
`_pdf_html_polish_stages`. Audit and repolish helpers also recognize the legacy
`_z2m_stages` name when reading older runs.
`--zotero-overlay-dir` is optional; when present, matching Zotero/pdf.js
`*.overlays.json` files are used for citation-link recovery before automatic
overlay generation is attempted.

Important: `02.en.polish.html` is not a pure function of `01.en.raw.html` for
link quality. The production path also passes a citation profile built from the
source PDF, optionally enriched with Zotero/pdf.js overlays. Raw-only repolish
helpers can be useful for text, float, math, or layout checks, but they are not
valid for citation/internal-link regression checks.

The EN polish audit also guards this boundary: if an author-year article has
`ref-*` bibliography targets but no body links to them, the quality loop reports
`P99` as an error instead of publishing a silently unlinked result.
The P55 audit/auto-repair path preserves author-year links when the anchor label
matches the target bibliography entry by surname and year.

Production converted-stage storage has a strict HTML contract. For each article
directory, the only retained HTML files are:

- `01.en.raw.html`
- `02.en.polish.html`

The public clean pipeline writes the audited latest polish back into
`02.en.polish.html` and prunes stale generated HTML copies. To audit an existing
converted tree without changing it:

```powershell
pdf-html-polish-stage-contract verify `
  --root "D:\Elvis_projects\Zotero_Automation\Zotero_automatization\data\html\converted" `
  --out-report "C:\tmp\converted_stage_contract.json"
```

To publish a completed quality run back into a converted tree, first run without
`--apply` and inspect the report, then repeat with `--apply`:

```powershell
pdf-html-polish-stage-contract publish `
  --quality-run-dir "D:\work\paper_pdf_html_quality" `
  --converted-root "D:\work\paper_pdf_html" `
  --out-report "C:\tmp\paper_publish_dry_run.json"
```

For link-sensitive repolish experiments, use `scripts/pdf_profile_lab.py` with a
`_source_filename_map.csv` beside the raw stages. The CSV must include
`alias_pdf_path` and `source_pdf_path` columns so the lab can rebuild the same
PDF-derived citation profiles used by production. Pass `--zotero-overlay-dir`
when the run should reuse prebuilt Zotero/pdf.js `*.overlays.json` files.

Multiple PDFs can be passed by repeating `--pdf`:

```powershell
pdf-html-polish `
  --pdf "D:\work\paper-1.pdf" `
  --pdf "D:\work\paper-2.pdf" `
  --output-dir "D:\work\pdf-html-output"
```

The installed public converter is `pdf-html-polish`; `pdf-html-polish-clean` is
kept as a compatibility alias for the same clean pipeline. The Zotero
orchestration image name is `zotero-pdf-html-worker:local`.

## Container Notes

The included Dockerfile installs Marker, Node.js, the local overlay probe, and
the optional math/PDF-text dependencies used by the HTML polish path. For Zotero
overlay citation recovery, the image builds a pinned Zotero/pdf.js
`generic-legacy` tree at `/opt/zotero-pdfjs` and sets
`PDF_HTML_POLISH_ZOTERO_PDFJS_DIR`. For local experiments, you can still mount
or provide another build with that variable, or pass prebuilt overlays with
`--zotero-overlay-dir`.

## Source Layout

- `src/pdf_html_polish/` - extracted PDF conversion, EN HTML polish,
  quality-loop, Zotero/WebDAV adapter, and audit modules.
- `src/pdf_html_polish/cli/` - small CLI wrapper for the PDF polish
  pipeline.
- `scripts/` - audit, repolish, and regression helpers for PDF-derived EN HTML.
- `docs/` - decision/playbook documents kept with the extraction.
