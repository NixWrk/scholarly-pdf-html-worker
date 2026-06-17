# pdf-html-polish

A focused `PDF -> Marker HTML -> polished EN HTML` pipeline extracted from an
older Zotero-oriented workflow and now kept as a standalone PDF HTML polish
tool.

This repository keeps the PDF-to-HTML polish path and its audit/quality-loop
helpers. It intentionally does not include the former EN-to-RU translation
runner or publisher web-HTML polish commands.

The public automation boundary is file-based: pass local PDF files and an
output directory; any Zotero collection lookup, queueing, WebDAV mirroring, or
write-back belongs to the caller.

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

## Convert PDF Files To Polished EN HTML

```powershell
pdf-html-polish `
  --pdf "D:\work\paper.pdf" `
  --output-dir "D:\work\pdf-html-output" `
  --zotero-overlay-dir "D:\work\zotero-overlays" `
  --export-mode html
```

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
  --output-dir "D:\work\pdf-html-output" `
  --export-mode html
```

The installed public converter is `pdf-html-polish`.

## Container Notes

The included Dockerfile installs Marker, Node.js, the local overlay probe, and
the optional math/PDF-text dependencies used by the HTML polish path. For Zotero
overlay citation recovery, mount or provide a Zotero/pdf.js `generic-legacy`
build and set `PDF_HTML_POLISH_ZOTERO_PDFJS_DIR`, or pass prebuilt overlays with
`--zotero-overlay-dir`.

## Source Layout

- `src/pdf_html_polish/` - extracted PDF conversion, EN HTML polish,
  quality-loop, Zotero/WebDAV adapter, and audit modules.
- `src/pdf_html_polish/cli/` - small CLI wrapper for the PDF polish
  pipeline.
- `scripts/` - audit, repolish, and regression helpers for PDF-derived EN HTML.
- `docs/` - decision/playbook documents kept with the extraction.
