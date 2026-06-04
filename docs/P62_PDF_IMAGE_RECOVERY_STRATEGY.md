# P62 PDF Image Recovery Strategy

This note records the follow-up investigation for P62 missing-figure recovery.
The main goal is not merely to silence a warning, but to recover the exact
visual that appears at the corresponding location in the source PDF.

## Current 12-Case Finding

The problematic retry subset was initially described as pages where marker did
not return an image. A stricter full-PDF search showed a different root cause:
some records had the wrong PDF page selected before marker was invoked.

Correct-page verdicts for the manually reviewed subset:

| Retry index | Target | Originally selected | Correct verdict | Reason |
|---:|---|---:|---|---|
| 13 | Figure 5 | 7 | page 8 | Page 7 contains Figure 4; the target caption/visual is on page 8. |
| 18 | Figure 1 | 1 | page 2 | Page 1 is the article header; the behavioral-task visual is on page 2. |
| 21 | Figure 1 | 8 | source visual unavailable | Lahav source has manuscript placeholders / caption lists, not the embedded figure visual. |
| 22 | Figure 2 | 43 | source visual unavailable | Lahav source has a caption list / placeholder, not the embedded figure visual. |
| 23 | Figure 3 | 13 | source visual unavailable | Lahav source references the figure in prose/caption list only. |
| 24 | Figure 4 | 13 | source visual unavailable | Lahav source references the figure in prose/caption list only. |
| 25 | Figure 5 | 14 | source visual unavailable | Lahav source has `Insert Figure` placeholders, not embedded visuals. |
| 33 | Figure 2 | 4 | page 14 | Page 4 is contents; IEC Figure 2 / Na test cycle is on page 14. |
| 37 | Figure 3-1 | 9 | page 53 | The full label is `Figure 3-1`; using only `Figure 3` hits list-of-figures noise. |
| 38 | Figure 1 | 12 | page 3 | Page 12 is reference/text match; Kuang FIG. 1 is on page 3. |
| 39 | Figure 2 | 12 | page 4 | Page 12 is reference/text match; Kuang FIG. 2 is on page 4. |
| 40 | Figure 3 | 12 | page 6 | Page 12 is reference/text match; Kuang FIG. 3 is on page 6. |

Artifacts:

- `.tmp_local2/llm_runs/converted_all3_loop104b_p62_marker_observe_2026-06-03/p62_false_match_correct_page_candidates.md`
- `.tmp_local2/llm_runs/converted_all3_loop104b_p62_marker_observe_2026-06-03/p62_false_match_correct_page_review/index.html`
- `.tmp_local2/llm_runs/converted_all3_loop104b_p62_marker_observe_2026-06-03/p62_pdf_tool_extraction_report.md`

## Automated Page Search Rules

Future P62 recovery must not select a page from `Figure N` text alone. Use a
ranked resolver before marker/image extraction:

1. Extract the target caption from the HTML figure unit.
2. Preserve the full figure label from the caption, including hierarchical
   labels such as `3-1`, `3.1`, letter suffixes, or appendix-style labels.
3. Search the full PDF text layer, not only the first N pages.
4. Score candidate pages with:
   - exact full-label match;
   - caption-token overlap;
   - caption-like occurrence near the label;
   - presence of visual objects on the page (`image_xrefs`, image blocks,
     drawings, or nontrivial vector/text layout near the caption).
5. Penalize or reject:
   - table of contents / contents pages;
   - figure-caption lists / list-of-figures pages;
   - manuscript placeholders such as `Insert figure 1 about here`;
   - prose-only parenthetical mentions such as `(Figure 3)`;
   - bibliography/reference/backmatter text-only matches;
   - pages with no visual objects when another caption-compatible visual page
     exists.
6. If all matches are placeholders/caption lists/prose-only, classify the record
   as `source_visual_unavailable` instead of sending it to marker.
7. Emit evidence for every selected page: selected page number, selected rank,
   top alternatives, false-match hints, visual object counts, and rendered
   contact sheet.

## PDF Tool Matrix For Future Tests

These tools should be tested as marker alternatives or supplements. They are not
all equivalent: some extract native PDF image streams, some render pages/crops,
and some perform higher-level document layout parsing.

| Tool | Role to test | Expected value | Limitations / notes |
|---|---|---|---|
| Poppler `pdfimages` | Native raster image extraction | Fast extraction of embedded image streams; useful comparison against PyMuPDF/pypdf. | Does not reconstruct vector/text/composite figures. Not currently in local PATH. |
| Poppler `pdftohtml` | HTML/XML layout and image export | May expose image positions and page layout independent of marker. | Needs installation; output quality varies by PDF. |
| MuPDF `mutool extract` | Native object extraction | Extracts image/font objects from PDF; good native-stream baseline. | Does not reconstruct figures assembled from vectors/text. Not currently in local PATH. |
| MuPDF `mutool convert` | Render pages/crops/SVG | Useful deterministic renderer and SVG/vector comparison. | Needs installation; crop selection still requires our geometry. |
| `pdf2htmlEX` | Layout-preserving HTML conversion | Can reveal figure regions and page layout close to visual PDF. | Installation can be difficult; project availability varies by platform. |
| PyMuPDF (`fitz`) | Primary local geometry and extraction engine | Installed and tested. Provides text, drawings, image xrefs, image bboxes/rects, native extraction, and rendering. | Native extraction returned small components for the tested 12-case subset, not complete figures. Still best for geometry and crop rendering. |
| PyMuPDF4LLM | High-level Markdown/layout extraction | Candidate for image/table segmentation and caption association. | Not installed locally; must be evaluated separately. |
| `pdfminer.six` | Text/layout diagnostics | Installed. Useful as an independent text-layer resolver. | Not a strong image extraction engine. |
| Apache PDFBox `ExtractImages` | Java native image extraction | Good independent native-stream baseline. | Native images only; geometry association must be added. |
| Apache Tika | Text/metadata/content extraction | Broad fallback parser for difficult PDFs. | Not a precise figure-image extraction tool by itself. |
| `pypdf` | Native image extraction | Installed and tested. Simple `page.images` extraction. | No strong bbox geometry; matched PyMuPDF in extracting only small components for tested cases. |
| PDFium / `pypdfium2` / `pdfium-render` | High-quality rendering | `pypdfium2` is installed. Good renderer candidate for deterministic crop fallback. | Rendering engine, not native figure extraction. |
| `pdfcpu` | CLI PDF extraction/inspection | Candidate native-stream extractor and object inspector. | Needs installation and test matrix coverage. |
| Docling / Docling Parse / Docling Serve | Higher-level document layout parser | Installed locally. Candidate for figure/table segmentation and caption association. | Potentially heavier runtime; needs controlled per-page tests. |
| MinerU | Scientific PDF parsing / layout | Candidate for figure/table extraction on papers. | Needs installation and controlled benchmark; may be heavy. |

## Extraction Test Result

For the corrected 12-case subset, available local native extractors were tested:
PyMuPDF (`doc.extract_image`) and pypdf (`page.images`).

Result:

- Native extraction found image streams on only 3 corrected records: #18, #33,
  and #37.
- The extracted streams were not the complete target figures. They were small
  components such as glyphs, bars, masks, or tiny page elements.
- Correct pages #13 and #38-#40 have no native raster figure image to extract;
  their visuals are vector/text/layout objects and must be recovered by
  deterministic region rendering.
- Records #21-#25 appear to have no embedded source visual in the PDF.

Therefore the recovery pipeline should be:

1. full-caption page resolver;
2. marker-first on the resolved page;
3. native image extraction only when a single image object can be safely linked
   to the target caption by bbox/proximity;
4. deterministic PDF region render for vector, table, or composite figures;
5. `source_visual_unavailable` when the source PDF contains only placeholders,
   figure lists, or prose references.
