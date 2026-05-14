# Manual EN Polish Review Round 2 2026-04-27

Purpose: collect the second manual review of regenerated `02.en.polish.html`
files, verify each symptom against `01.en.raw.html` and `02.en.polish.html`,
then consolidate only generalized repair requirements.

Workflow reference: `docs/MANUAL_EN_POLISH_REVIEW_WORKFLOW_2026-04-26.md`

Consolidated fix plan: `docs/EN_POLISH_CONSOLIDATED_FIX_PLAN_2026-04-27.md`

Local review copies: `D:\Git_Code\ZoteroPDF_2_MD\manual_review_en_polish_2026-04-27`

## Status

| Article | User notes captured | Verified | Consolidated |
|---|---|---|---|
| Ahmed 2026 | yes | yes | yes |
| Kaiju 2017 | yes | yes | yes |
| Li 2026 | yes | yes | yes |
| Merken 2022 | yes | yes | yes |
| Schelles 2025 | yes | yes | yes |
| Wang 2017 | yes | yes | yes |
| Teo 2025 | yes | yes | yes |

## Cross-Article General Notes

### Manual Notes From User

- Figures do not display in the reviewed HTML files. This may be related to horizontal lines/wrappers, or to how review documents are assembled.
- Figure/table visual framing should be standardized as:
  `horizontal rule -> figure/table -> caption -> horizontal rule`.
  The current output has too many lines/rectangles in some places.
- Scientific symbols and units such as `μm` and `Ω` are not rendered consistently across articles:
  sometimes the number and unit are both inside a formula;
  sometimes only the number is a formula;
  sometimes only `μ`/`Ω` is a formula while the rest of the unit is plain text.
  The likely source is Marker mixing formula recognition and symbol recognition, but polish should standardize the output.
- Clicking links to figures/tables behaves inconsistently: sometimes the highlighted target is the image/table, sometimes the caption. Link target and highlighting should be repeatable across articles.

### Verification Notes

- The review folder `manual_review_en_polish_2026-04-27` currently contains only HTML copies and no `_page_*.jpeg` image assets. All seven review HTML files contain relative `<img src="_page_...">` references that are missing from the review folder. This explains broken images during manual review even when the source stage folder still contains the images.
- The image display issue therefore has at least one packaging cause: review copies are not self-contained. This should be fixed independently of any figure-wrapper styling fixes.
- Existing article-specific findings already show inconsistent figure/table targeting and float grouping: Ahmed full-page Figure 8, Li Figure 2, Wang Table III, and Teo Table 1.
- Existing article-specific findings also confirm the unit instability class across Merken and Schelles, with forms such as `\mu\text{m}`, `\mum`, `µm2`, `\muC`, `Ω`, `k \(\Omega\)`, and split symbol/unit text.

### Generalized Defect Classes

- `C-REVIEW-PACKAGE-IMAGE-ASSETS`: manual-review/export folders must include referenced image assets or rewrite image paths so copied HTML remains viewable.
- `C-BROKEN-IMAGE-SRC-AUDIT`: audit output should report `<img>` references whose files do not exist relative to the HTML file.
- `C-FIGURE-TABLE-VISUAL-FRAME-STANDARDIZATION`: figure and table blocks should have a single predictable visual frame: top rule, content, caption/title/note, bottom rule.
- `C-FLOAT-TARGET-WRAPPER-STANDARDIZATION`: figure/table links should target a stable wrapper for the whole figure/table unit, not randomly the image/table node or caption.
- `C-FLOAT-HIGHLIGHT-STANDARDIZATION`: target highlighting should consistently highlight the whole figure/table unit while scrolling the primary content into view.
- `C-SCIENTIFIC-UNIT-SEMANTIC-NORMALIZATION`: numbers, unit symbols, and unit names should be normalized into a stable semantic representation instead of being split unpredictably between math and text.

### Fix Requirements

- Make review copies self-contained:
  - copy all image assets referenced by each `02.en.polish.html` into the same review folder or article-specific subfolders;
  - alternatively rewrite `<img src>` to paths that remain valid from the review copy;
  - add an audit check that fails or warns when copied review HTML has missing images.
- Standardize figure/table rendering:
  - create one wrapper per figure/table unit;
  - render exactly one top separator and one bottom separator for the whole unit;
  - keep image/table content before caption/title notes when appropriate for reading;
  - avoid nested card-like borders, duplicated horizontal rules, and separate rectangles around both image and caption unless the original design demands it.
- Standardize figure/table link behavior:
  - all `fig-*` and `table-*` anchors should attach to the unit wrapper;
  - link clicks should scroll so the figure/table content is visible, not only the caption;
  - highlight should apply to the same wrapper for every article.
- Standardize scientific units:
  - normalize Marker fragments like `10 <math>\mu</math> m`, `10 \mu\text{m}`, `10 \mum`, `10 µ m`, `10 µm`, `10 µm<sup>2</sup>`, and `k \(\Omega\)`;
  - prefer readable semantic unit markup for simple measurements over math mode that splits symbols from units;
  - preserve true mathematical formulas and chemical/material notation via guarded context rules.

### Regression Coverage Needed

- Review-package test: copied review HTML with `<img src="_page_1_Figure_1.jpeg">` must include that image or a valid rewritten path.
- Audit test for missing `<img>` targets in any generated/review HTML.
- UI fixture for a figure and a table: expected one wrapper, one top rule, content, caption/title/note, one bottom rule.
- Link target fixture: clicking `#fig-1` and `#table-1` highlights the wrapper and scrolls content into view.
- Unit-normalization fixtures for `μm`, `μm²`, `Ω`, `kΩ`, `μC cm−2`, and mixed Marker math/text fragments.

### Open Constraints

- Figure/table visual framing must improve readability without hiding original content or making review harder.
- Unit normalization should prefer conservative semantic repair and audit warnings over risky changes when a token could be a variable, chemical formula, or true exponent.

## Ahmed 2026

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-27/01_Ahmed_2026_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Ahmed и др. - 2026 - Robust minimally-invasive microfabricated stainless steel neura_3e6edbab/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Ahmed и др. - 2026 - Robust minimally-invasive microfabricated stainless steel neura_3e6edbab/_z2m_stages/02.en.polish.html`
- Local source PDF copy: `md_output/new/electrodes_W7TECQDX/Ahmed и др. - 2026 - Robust minimally-invasive microfabricated stainless steel neura_3e6edbab/_z2m_stages/00.source.pdf`
- Extracted Figure 8 image: `md_output/new/electrodes_W7TECQDX/Ahmed и др. - 2026 - Robust minimally-invasive microfabricated stainless steel neura_3e6edbab/_page_36_Figure_5.jpeg`
- Source PDF named in the stage log: `Ahmed и др. - 2026 - Robust minimally-invasive microfabricated stainless steel neural interfaces for high resolution reco.pdf`

### Manual Notes From User

- Text/caption continuation is still broken around the BioRender credit, for example `around the insertion site (created BioRender. Chamanzar. (2025) https://BioRender.com/8bfbsk2).comparison shows normalized cel`.
- Figure 8 and its caption are still out of sequence. The source page is complex: the figure and caption occupy a whole page, and Marker probably misread the layout.
- Figure/reference target highlighting works well, but reference navigation is shifted: clicking reference 58 shows reference 56.
- Reference numbering is mixed around `56,57,60,59,60,61`.
- The shift may be caused by treating non-reference continuation text as a reference, for example:
  `25. Niinomi, M. Recent metallic materials for biomedical applications. Metall. Mater. Trans. A`
  / `26. (2007) doi:10.1007/s11661-002-0109-2.`
  / `26. Li, M. et al. Study of biocompatibility...`.

### Verification Notes

- The source PDF is now copied beside `01.en.raw.html` as `00.source.pdf`. The extracted Figure 8 sidecar image is present and was inspected; the image itself is intact and contains the full multi-panel Figure 8.
- PDF page 37 shows Figure 8 as a complex full-page layout: the caption title and first caption column are on the left, the multi-panel image is on the right, and the caption continues under the image across the page width. This explains why Marker emitted caption fragments before and after the image.
- The PDF text layer for page 37 contains cleaner Figure 8 caption text than Marker raw, including `created in BioRender. Chamanzar, M. (2025) https://BioRender.com/8bfbsk2). c shows...`; Marker raw loses `in`, changes punctuation around `Chamanzar, M.`, turns the URL into an `h4`, and drops/relocates the `c` panel lead.
- The Figure 8 ordering defect first appears in `01.en.raw.html`: Marker emits the caption title, caption text, isolated URL heading, more caption text, then the image, then more caption continuation text.
- `02.en.polish.html` preserves that ordering while adding `id="fig-8"` to the image placeholder, so current polish improved targetability but did not assemble the whole figure block.
- The reference shift first appears in `01.en.raw.html`: the bibliography has 87 list items, while the visible source numbering ends at 84. Several references are split into extra list items or continuation fragments.
- `02.en.polish.html` assigns `id="ref-N"` by list-item ordinal, so extra raw list items make anchors drift away from the visible bibliography numbers.
- PDF pages 49-50 show reference 25 split by a page break: the page 50 top line starts with `(2007) doi:...` and has no new reference number. Marker incorrectly turns this continuation into a separate list item.
- PDF pages 50-51 show the same class for reference 38: the URL continuation starts on the next page without a reference number.
- PDF page 52 confirms the original bibliography numbering around `56-64` is correct, including `58. Best Stainless Steel Wafer Polishing Services...`; the HTML `ref-58` drift is caused by earlier split items, not by the PDF source numbering.
- PDF pages 53-54 show the same continuation pattern for reference 77: `Open source silicon microprobes for` continues on page 54 as `high throughput neural recording...`.

### Verified Symptoms

| ID | Location | Symptom | Expected | First broken stage | Status |
|---|---|---|---|---|---|
| AHM2-01 | Figure 8 caption, BioRender credit | The URL is isolated as an `h4`, and the following caption continuation starts with lowercase `comparison`, creating punctuation/spacing like `). comparison` or user-observed `).comparison`; PDF page 37 text layer has the cleaner `created in BioRender... ). c shows...`. | BioRender credit and following caption continuation should remain in one caption flow with stable punctuation and spacing. | `01.en.raw.html`; repairable in EN polish, optionally aided by PDF text-layer fallback | verified |
| AHM2-02 | Figure 8 block | The image `_page_36_Figure_5.jpeg` is placed after the caption title and the first part of the caption, then another caption continuation follows the image. PDF page 37 confirms this is one full-page figure/caption layout. | Figure image, complete caption title, credit, and all panel descriptions should be assembled into one figure block with predictable image/caption order. | `01.en.raw.html`; repairable in EN polish by figure-block assembly | verified |
| AHM2-03 | Bibliography references 25-30 | Raw splits reference 25 into `25. ... Metall. Mater. Trans. A` plus a separate continuation `(2007) doi:...`; the next real item still starts as `26. Li, M. ...`. | Continuation-only list items must be merged into the previous real bibliography item before assigning reference IDs. | `01.en.raw.html`; repairable in EN polish reference normalization | verified |
| AHM2-04 | Bibliography references 56-61 | Raw contains extra non-numbered or misnumbered list items such as `Best Stainless Steel Wafer Polishing Services...`, producing visible order `56, 57, 60, 59, 60, 61`. | Reference IDs and visible numbers should follow the actual bibliography numbers, and malformed continuation/non-numbered items should not shift later anchors. | `01.en.raw.html`; repairable in EN polish reference normalization/audit | verified |
| AHM2-05 | Body citation link to reference 58 | In polish, a body citation shown as `58` links to `#ref-58`, but `#ref-58` contains visible reference 56 because anchors use raw list ordinal rather than visible bibliography number. | Body citation `58` should target the bibliography entry whose visible source number is 58, not the 58th raw list item. | `02.en.polish.html` anchor assignment after raw split refs | verified |

### Root Cause Hypotheses

- Figure 8 is a Marker layout-ordering defect: a full-page float/caption is emitted as ordinary sequential blocks, with URL credit text misclassified as a heading.
- For Figure 8, Marker appears to prefer the page-zone order over the cleaner PDF text layer. The text layer itself is good enough to prove several raw caption defects are not inherent to the PDF.
- EN polish currently recognizes the Figure 8 target image, but does not protect and reorder a complete figure unit made of image plus fragmented caption continuations.
- Reference IDs are assigned too early from raw list-item ordinals. The code does not first normalize bibliography entries by visible reference numbers, continuation-only fragments, duplicate numbers, missing numbers, and URL-only splits.
- Because anchors are ordinal-based, one early split reference can shift every later citation target.

### Generalized Defect Classes

- `C-FIGURE-FULL-PAGE-FLOAT-ASSEMBLY`: full-page or multi-panel figures may arrive as caption fragments plus delayed image nodes; polish should group them into one figure block instead of relying on raw block order.
- `C-CAPTION-CREDIT-CONTINUATION`: URL/credit fragments inside captions, especially BioRender-style credits emitted as headings, should be reclassified as caption text and merged with adjacent caption continuations.
- `C-REFERENCE-LIST-NORMALIZATION-BEFORE-LINKING`: bibliography list items must be normalized before `ref-*` IDs are assigned. Visible source numbers, not raw list ordinal, should define reference identity when available.
- `C-REFERENCE-CONTINUATION-MERGE`: list items without a credible new-reference start, or with only year/DOI/URL continuation content, should be merged into the previous bibliography item.
- `C-REFERENCE-TARGET-AUDIT`: after linking, the pipeline should warn or fail debug checks when `id="ref-N"` contains a visible leading number different from `N`, duplicate visible numbers, gaps, or non-numbered entries inside numbered references.
- `C-PDF-TEXT-LAYER-FALLBACK-FOR-CAPTIONS-AND-REFS`: when a local source PDF is available, use its text layer as an audit/fallback signal for captions and bibliography entries that Marker splits or corrupts.

### Fix Requirements

- Add a pre-link bibliography normalization pass in EN polish:
  - detect the bibliography region;
  - parse visible leading numbers independently from raw `<li>` ordinal;
  - merge continuation-only items into the previous real entry;
  - preserve or repair the visible numbering without creating duplicate `ref-*` targets;
  - assign `id="ref-N"` by visible reference number whenever it is trustworthy.
- Add reference audit checks to `scripts/audit_en_polish.py` for anchor/visible-number mismatches, duplicate visible bibliography numbers, missing visible numbers, and ordinal drift.
- Extend figure-block assembly to handle the pattern `caption title -> caption text -> URL heading -> caption text -> image -> caption text`, then produce a stable figure unit for link targets and visual review.
- Add regression fixtures based on Ahmed Figure 8 and the split references near 25, 38/reader URL, 58/Best Stainless Steel Wafer, and 77/high-throughput continuation.
- For debug runs with `00.source.pdf`, compare suspicious caption/reference fragments against the PDF text layer before classifying the defect as unrecoverable Marker damage.

### Open Constraints

- Direct PDF visual verification can now be repeated from the local `00.source.pdf` copy if needed. The available extracted Figure 8 image already confirms the image itself is not lost.

## Kaiju 2017

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-27/02_Kaiju_2017_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Kaiju и др. - 2017 - High Spatiotemporal Resolution ECoG Recording of Somatosensory_2474f78c/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Kaiju и др. - 2017 - High Spatiotemporal Resolution ECoG Recording of Somatosensory_2474f78c/_z2m_stages/02.en.polish.html`
- Local source PDF copy: `md_output/new/electrodes_W7TECQDX/Kaiju и др. - 2017 - High Spatiotemporal Resolution ECoG Recording of Somatosensory_2474f78c/_z2m_stages/00.source.pdf`

### Manual Notes From User

- Reference navigation jumps to the correct bibliography record, but only the number in the list is highlighted rather than the whole entry.
- The inline notation is still wrong: `is shown as iECoG(t) j . A coordinate of position j is shown as (x j , yj).` The `j` should be a subscript only in this mathematical context; a generic "make every j subscript" rule would be wrong.
- On the bibliography page, the reading order is broken. PDF order is `FUNDING` text, then `SUPPLEMENTARY MATERIAL`, then `REFERENCES`, but HTML inserts `REFERENCES` after `by the Ministry of`, continues funding later, and then resumes references after supplementary material.

### Verification Notes

- PDF page 5 contains the cleaner mathematical context: the display equation uses `iECoG(t)_j`, `x_j`, and `y_j`; the following prose visually/textually refers to `iECoG(t)j` and `(xj, yj)` as indexed variables.
- `01.en.raw.html` is already wrong around this prose: Marker emits `iECoG(t)<sup>j</sup>`, splits the sentence across paragraphs, emits `x<sup>j</sup>`, and leaves `yj` flattened. `02.en.polish.html` merges the paragraphs but preserves the wrong superscript/flattened variable forms.
- The wrong `j` is therefore a raw-stage math extraction error, but the correct repair is context-aware: the immediately preceding equation defines the variable-index forms that should be restored in the following explanatory sentence.
- PDF page 12 has a two-column end-of-article layout. The left column contains the start of `FUNDING` and then `REFERENCES`; the right column contains the continuation of `FUNDING`, `SUPPLEMENTARY MATERIAL`, and more references. The PDF text layer reports the intended order correctly.
- `01.en.raw.html` follows a layout-zone order instead: `FUNDING` start, `REFERENCES` heading and first 12 entries, funding continuation, `SUPPLEMENTARY MATERIAL`, then reference 13 onward. Polish preserves this broken order.
- Some body author-year citations still link to Marker page anchors such as `#page-11-22` instead of `#ref-13`. Those page anchors are embedded inside the target bibliography `<li>` immediately after `<span class="z2m-ref-num">13.</span>`, so browser `:target` highlights the tiny span/number area instead of the whole bibliography entry.

### Verified Symptoms

| ID | Location | Symptom | Expected | First broken stage | Status |
|---|---|---|---|---|---|
| KAI2-01 | Body citation links to references | Links such as author-year citations target `#page-*` anchors embedded inside bibliography list items, so the correct entry is reached but only the number/near-number span is highlighted. | Citation links should target the containing `li id="ref-N"` or otherwise highlight the whole bibliography entry consistently. | `02.en.polish.html` link retargeting/UX | verified |
| KAI2-02 | Data Analysis, COG equation explanation | Marker raw turns indexed variables into superscript/flat text: `iECoG(t)<sup>j</sup>`, `x<sup>j</sup>`, `yj`; polish renders/copies this as `iECoG(t) j`, `(x j, yj)`. | Only the variables defined by the neighboring equation should be restored as indexed variables, e.g. `iECoG(t)_j`, `x_j`, `y_j` or equivalent HTML/math. | `01.en.raw.html`; repairable in EN polish using nearby equation context/PDF text layer | verified |
| KAI2-03 | PDF page 12, end sections and references | `REFERENCES` is inserted into the middle of the funding paragraph, then funding and supplementary material continue before reference 13 onward. | End-of-article sections should remain in semantic order: complete `FUNDING`, complete `SUPPLEMENTARY MATERIAL`, then full `REFERENCES`. | `01.en.raw.html`; repairable in EN polish with two-column section/order repair or PDF text-layer fallback | verified |

### Root Cause Hypotheses

- Marker preserves page-link anchors from the PDF/reference mapping, while EN polish adds `ref-N` IDs but does not retarget author-year citation links that still point to page anchors inside bibliography entries.
- Marker misclassifies index glyphs in prose after a display formula: it turns subscript-like `j` after `iECoG(t)` and `x` into superscripts and misses the compact `y_j` form. The nearby display equation contains enough evidence to repair this without a broad `j` rule.
- Marker's page-layout reading order for the final two-column page overrides the PDF text layer's semantic order. The left-column `REFERENCES` heading is emitted before the right-column continuation of `FUNDING` and `SUPPLEMENTARY MATERIAL`.

### Generalized Defect Classes

- `C-PAGE-ANCHOR-TO-REFERENCE-RETARGETING`: when a `#page-*` anchor lives inside `li id="ref-N"`, incoming citation links to that page anchor should be retargeted to `#ref-N` or should trigger whole-entry highlighting.
- `C-POST-EQUATION-VARIABLE-INDEX-RESTORATION`: prose immediately following a display equation can contain flattened or wrong-superscript variable indices; restore only variable forms explicitly present in the neighboring formula or PDF text layer.
- `C-TWO-COLUMN-END-SECTION-ORDER-REPAIR`: final sections such as funding, supplementary material, acknowledgements, conflict statements, and references may be interleaved by two-column page reading order and must be reassembled by section semantics before reference parsing/linking.

### Fix Requirements

- During reference-link reconstruction, build a map from every `#page-*` anchor inside a bibliography `<li id="ref-N">` to `#ref-N`, then rewrite body citations to the stable reference target.
- Ensure target CSS/HTML highlights the whole reference item, not an embedded page marker or numeric span.
- Add a context-aware inline math repair pass for post-equation prose:
  - inspect the previous display formula for indexed variable forms such as `iECoG(t)_j`, `x_j`, and `y_j`;
  - repair only matching broken prose forms in the nearby explanatory paragraph;
  - do not globally rewrite standalone `j`.
- Add an end-section ordering repair before bibliography normalization:
  - detect `REFERENCES` inserted between an incomplete section paragraph and its continuation;
  - move non-reference continuation paragraphs back under their owning heading;
  - keep `SUPPLEMENTARY MATERIAL` before `REFERENCES` when the PDF/text-layer order proves that sequence.
- Add PDF text-layer audit support for suspicious two-column final pages: if raw order differs from the text-layer order around terminal headings, flag and optionally repair.

### Regression Coverage Needed

- Link-target test where body text links to `#page-11-22`, the page anchor lives inside `<li id="ref-13">`, and polish rewrites/highlights `#ref-13`.
- Inline math fixture with a display equation containing `iECoG(t)_j`, `x_j`, `y_j`, followed by prose with `iECoG(t)<sup>j</sup>`, `x<sup>j</sup>`, and `yj`; expected output restores only those local variables.
- Two-column end-section fixture: `FUNDING` incomplete paragraph, premature `REFERENCES`, reference list start, funding continuation, `SUPPLEMENTARY MATERIAL`, reference continuation. Expected output completes funding/supplementary sections before references.

## Li 2026

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-27/03_Li_2026_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Li и др. - 2026 - Scaling beyond the vagus nerve historical and contemporary progres_f7f4c983/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Li и др. - 2026 - Scaling beyond the vagus nerve historical and contemporary progres_f7f4c983/_z2m_stages/02.en.polish.html`
- Local source PDF copy: `md_output/new/electrodes_W7TECQDX/Li и др. - 2026 - Scaling beyond the vagus nerve historical and contemporary progres_f7f4c983/_z2m_stages/00.source.pdf`

### Manual Notes From User

- Text continuation is broken when interrupted by Figure 2: `Fibers may be myelinated or unmyelinated and` is separated from `vary in diameter` by the figure image/caption.
- Reference navigation reaches the correct bibliography entry, but only the number/near-number area is highlighted rather than the whole entry.
- A non-reference footnote marker became a reference link, while some real author-year citation links were lost, e.g. `low tensile strength 1 . ... (Lienemann et al. 2023 ; Paggi et al. 2024).`
- A bottom footnote is placed in the middle of body text and is not visually separated: `1 Tensile strength of a material is determined...`.
- Many author-year citation links are lost, including examples around `memory effect (Cho et al. 2021; González-González et al. 2018).` and `(Gablech and Głowacki 2023)`.

### Verification Notes

- PDF page 2 ends with the body sentence `Fibers may be myelinated or unmyelinated and`; PDF page 3 starts with Figure 2 and its caption, then the body continuation `vary in diameter...`. This is a legitimate figure interruption in the PDF layout.
- `01.en.raw.html` emits page header text, image, Figure 2 caption, and then the body continuation between the two halves of that sentence. `02.en.polish.html` removes the page header and styles the caption but still leaves the figure/caption between `and` and `vary`.
- The PDF visual layout confirms that Figure 2 is a left-column float and the sentence continuation appears below it. HTML needs to preserve reading continuity while keeping the figure block visually nearby.
- PDF page 7 shows footnote marker `1` after `low tensile strength` and the actual footnote at the page bottom, visually separated by a rule. `01.en.raw.html` preserves this as `<sup>1</sup>` plus a separate paragraph beginning with `<sup>1</sup> Tensile strength...`.
- `02.en.polish.html` turns the footnote marker into `<a href="#ref-1" class="z2m-ref-link">1</a>`, although it is a footnote, not bibliography citation. The footnote text is relocated/hidden by surrounding table/text flow and is not rendered as a footnote/callout.
- Marker raw includes many author-year citations as PDF page anchors around the year, for example `Lienemann et al. <a href="#page-29-11">2023</a>` and `Paggi et al. <a href="#page-30-1">2024</a>`. The corresponding bibliography entries contain matching `span id="page-29-11"` / `span id="page-30-1"` inside `<li>` records.
- In polish, the bibliography receives stable `ref-*` IDs, but author-year links are not consistently retargeted from `#page-*` to `#ref-*`. Some remain as page-anchor links, some are lost and become plain text.
- The `memory effect` paragraph on PDF page 8 has multiple linked author-year citations. In polish, `Cho et al. 2021`, `González-González et al. 2018`, and `Gablech and Głowacki 2023` appear as plain text despite matching bibliography entries with page anchors.

### Verified Symptoms

| ID | Location | Symptom | Expected | First broken stage | Status |
|---|---|---|---|---|---|
| LI2-01 | Peripheral nerve anatomy / Figure 2 | A body sentence is interrupted by Figure 2 image/caption: `Fibers may be myelinated or unmyelinated and` then figure/caption, then `vary in diameter...`. | The figure block may remain nearby, but body sentence continuity should be restored or the interruption should be visually and semantically clear. | `01.en.raw.html`; repairable in EN polish with float-aware continuation repair | verified |
| LI2-02 | Author-year reference navigation | Clicks can land on `#page-*` anchors embedded inside bibliography entries, so highlight/focus covers only the page marker/near-number span rather than the whole reference entry. | Author-year citation links should target the containing `li id="ref-N"` or otherwise highlight the full bibliography entry. | `02.en.polish.html` reference retargeting/UX | verified |
| LI2-03 | Footnote marker after `low tensile strength` | Footnote marker `1` is converted into `#ref-1`, creating a false bibliography link. | Page footnote markers should remain footnote markers and link only to a footnote/callout, not to bibliography entry 1. | `02.en.polish.html` citation linkification | verified |
| LI2-04 | Footnote text on page 7 | The footnote text `1 Tensile strength...` is treated as ordinary body/page text and is not visually separated as a footnote. | Page-bottom footnotes should be extracted or displayed as dedicated footnote/callout blocks associated with their markers. | `01.en.raw.html`; repairable in EN polish with footnote detection/relocation | verified |
| LI2-05 | Author-year citation links | Real author-year citation links are inconsistently preserved. Examples such as `Lienemann et al. 2023`, `Paggi et al. 2024`, `Cho et al. 2021`, `González-González et al. 2018`, and `Gablech and Głowacki 2023` are plain text in polish even when raw had page anchors or bibliography entries. | Author-year citations should be mapped to stable bibliography targets using existing PDF page anchors and/or parsed bibliography metadata. | Marker raw provides weak page anchors; EN polish lacks author-year mapping/retargeting | verified |

### Root Cause Hypotheses

- Marker emits legitimate PDF float interruptions as linear HTML order, so the figure block splits the body sentence instead of being grouped as a float with a rejoined prose flow.
- The current continuation repair removes some page furniture but does not treat figure/caption/table/footnote blocks as movable interruptions when both sides form one incomplete sentence.
- Citation linkification is too numeric: it treats `<sup>1</sup>` footnotes as bibliography references.
- Author-year citations are not reconstructed semantically. Marker emits many as `#page-*` links to bibliography-local anchors; polish assigns `ref-*` IDs but does not build an author-year/page-anchor-to-reference mapping before preserving or rewriting links.
- Link/highlight UX is inherited from small embedded page anchors inside bibliography entries rather than the whole reference `<li>`.

### Generalized Defect Classes

- `C-FLOAT-AWARE-BODY-CONTINUATION`: figures, tables, and captions can interrupt incomplete body sentences; polish should repair the reading flow while keeping the visual float block nearby and targetable.
- `C-FOOTNOTE-MARKER-PROTECTION`: superscript footnote markers must be distinguished from numeric bibliography citations before reference linkification.
- `C-FOOTNOTE-BLOCK-EXTRACTION`: page-bottom footnotes should be detected from their marker, small/page-bottom context, and separator/page layout, then rendered separately from body prose.
- `C-AUTHOR-YEAR-CITATION-RETARGETING`: author-year citations should be mapped to bibliography entries using raw `#page-*` anchors inside reference list items, parsed author/year keys, and optional PDF text-layer evidence.
- `C-REFERENCE-LINK-PRESERVATION`: existing citation links should not silently become plain text unless the target is invalid and an audit warning is emitted.

### Fix Requirements

- Extend continuation repair to handle `body fragment -> float block -> body continuation` patterns when the left fragment ends with conjunctions or incomplete syntax and the right fragment begins with a lower-case continuation.
- Keep figure/table blocks visually separated and targetable, but do not allow them to break copy/read order of the surrounding sentence.
- Before numeric citation linking, identify local footnote markers and footnote text blocks:
  - superscript marker in body with a matching page-bottom footnote block;
  - footnote block beginning with the same marker and short explanatory prose;
  - local page/section proximity when available.
- Render extracted footnotes as dedicated `z2m-footnote` blocks and link marker to footnote, not to `ref-*`.
- Build an author-year citation map:
  - collect page anchors inside bibliography `<li id="ref-N">`;
  - retarget body links pointing to those anchors to `#ref-N`;
  - parse bibliography entries into author/year keys for citations whose raw page anchors were dropped or absent;
  - support diacritics and multi-author forms such as `González-González et al. 2018` and `Gablech and Głowacki 2023`;
  - preserve links and emit audit warnings for ambiguous/unresolved author-year citations.
- Apply the same whole-entry target/highlight behavior as in Kaiju: links into reference-local page anchors should focus/highlight the containing `<li>`.

### Regression Coverage Needed

- Fixture for Figure 2-style interruption: body paragraph ending `and`, figure image/caption block, then body paragraph starting `vary`; expected output restores body continuity or marks the figure as a non-breaking float.
- Fixture for footnote marker `strength<sup>1</sup>` plus page-bottom `<sup>1</sup> Tensile strength...`; expected no `#ref-1`, visible footnote/callout output.
- Fixture where raw author-year citations use `#page-*` links and bibliography entries contain corresponding `span id="page-*"` inside `li id="ref-N"`; expected links retarget to `#ref-N`.
- Fixture for author-year citation recovery with diacritics and multi-author names: `Cho et al. 2021`, `González-González et al. 2018`, `Gablech and Głowacki 2023`.
- Audit test that flags a drop in body citation links between raw and polish when the target bibliography entry still exists.

## Merken 2022

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-27/04_Merken_2022_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Merken и др. - 2022 - Thin flexible arrays for long-term multi-electrode recordings_d0ccb2cf/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Merken и др. - 2022 - Thin flexible arrays for long-term multi-electrode recordings_d0ccb2cf/_z2m_stages/02.en.polish.html`
- Local source PDF copy: `md_output/new/electrodes_W7TECQDX/Merken и др. - 2022 - Thin flexible arrays for long-term multi-electrode recordings_d0ccb2cf/_z2m_stages/00.source.pdf`

### Manual Notes From User

- Table formula/unit rendering is wrong, for example `70\mum x 20 \mum (1 shaft)`.
- A chemical/material index became a superscript: `AlOx 20 nm`. This must be handled carefully so real exponents are not broken.
- Inline/caption unit formulas are still malformed, for example `100\mum x 40\mum (4000\mum^2`.
- Bibliography numbers are duplicated, for example `1. [1] Hubel D and Wiesel T...`.

### Verification Notes

- PDF page 4 Table 1 shows the Neuropixels cell as `70 µm × 20 µm (1 shaft)`. `01.en.raw.html` represents it as a `<math>` block with `70 \mu\text{m} \times 20 \mu\text{m}`. `02.en.polish.html` can render related table/body units as compact malformed TeX-like fragments such as `\mum`, so the unit normalization is not stable across tables/body/captions.
- PDF page 5 visually confirms material formulas use subscript `x`: `HfOₓ`, `AlOₓ`, `IrOₓ`. Marker raw is inconsistent: some occurrences are `AlO<i>x</i>`/`IrO<i>x</i>`, while later occurrences become `AlO<i><sup>x</sup></i>` and `HfO<i><sup>x</sup></i>`. Polish preserves this inconsistency instead of normalizing material formulas.
- PDF page 8 Figure 3 caption and figure labels contain electrode areas such as `900 µm²`, `2000 µm²`, `4000 µm²`, `8000 µm²`. Raw often emits these as `\mu` plus escaped `&lt;sup&gt;2&lt;/sup&gt;` or math fragments; polish sometimes preserves a `z2m-unit-exp` `<sup>2</sup>`, but text extraction/visual output still reads as spaced `µ m 2` in plain-text contexts and some inline math remains as `\mum^2`.
- The inline body section around Figure 3 contains a second form of the same unit class: raw has math fragments like `100 \,\mu\text{m} \times 40 \,\mu\text{m}` and `4000 \,\mu\text{m}^2`; polish produces mixed LaTeX fragments such as `\(100 \,\mum \times 40 \,\mum\)` and `\(4000 \,\mum^2\)`.
- PDF page 13 starts the bibliography with bracketed source numbers `[1]`, `[2]`, `[3]`, etc. Raw list items preserve those bracket numbers but have no stable `ref-*` IDs. Polish adds `<span class="z2m-ref-num">1.</span>` before entries while leaving the original `[1]` for some records, causing visible duplicates like `1. [1]`.

### Verified Symptoms

| ID | Location | Symptom | Expected | First broken stage | Status |
|---|---|---|---|---|---|
| MER2-01 | Table 1, Neuropixels row | Unit/math cell `70 µm × 20 µm (1 shaft)` is represented through fragile math fragments and can render as malformed `\mum`/plain `x` style. | Table dimensions should normalize to a readable, consistent unit form such as `70 µm × 20 µm (1 shaft)` without breaking table layout. | `01.en.raw.html` emits MathML/TeX fragments; `02.en.polish.html` lacks robust normalization | verified |
| MER2-02 | Section 2.2 material formulas | `HfOₓ`, `AlOₓ`, and `IrOₓ` are inconsistently emitted as italic `x` or superscript `x`, although the PDF shows subscript material notation. | Chemical/material formula suffix `x` should be normalized as a subscript only in credible oxide/material formula contexts. | `01.en.raw.html` | verified |
| MER2-03 | Figure 3 caption and body electrode-size text | Area units and dimensions mix escaped superscripts, inline math, spaced `µ m 2`, and `\mum^2` fragments. | Unit dimensions and areas should be normalized consistently across body, caption, and table contexts: `µm`, `×`, and `µm²`/equivalent semantic markup. | `01.en.raw.html`; polish currently only partially repairs | verified |
| MER2-04 | Bibliography first entries | Polish shows duplicate visible numbering such as `1. [1] Hubel...` when raw entries already start with bracketed source numbers. | Reference normalization should use one visible numbering scheme and strip or reuse bracketed source numbers before adding `z2m-ref-num`. | `02.en.polish.html` | verified |

### Root Cause Hypotheses

- Unit markup is fragmented by Marker into several equivalent representations: MathML `<math>`, TeX text, escaped HTML superscripts, isolated italic `µ`, and plain text. EN polish has repairs for some forms, but no single unit-normalization pass that runs consistently for tables, captions, and body prose.
- Material formulas are being treated like generic styled text/math. Marker sometimes encodes the oxide suffix as `<i>x</i>` and sometimes as `<i><sup>x</sup></i>`; the polish pass does not infer the intended chemical/material subscript from local context.
- Bibliography numbering is normalized after list IDs are created, but the existing leading bracketed numbers are not removed in entries where a page-anchor span or other inline tag appears before `[N]`.

### Generalized Defect Classes

- `C-UNIT-DIMENSION-NORMALIZATION`: normalize dimensions such as `70 µm × 20 µm`, `100 µm × 40 µm`, and `20 by 100 µm²` from MathML, TeX, escaped HTML, and plain text forms.
- `C-AREA-UNIT-EXPONENT-NORMALIZATION`: detect unit exponents for `µm²`, `mm²`, `cm²`, `m²`, etc. without confusing them with reference numbers or chemical suffixes.
- `C-TABLE-CELL-MATH-NORMALIZATION`: apply the same unit/math normalization inside `<td>` cells without flattening table structure or losing non-math labels such as `(1 shaft)`.
- `C-CHEMICAL-FORMULA-SUBSCRIPT-GUARD`: normalize `AlOₓ`, `HfOₓ`, `IrOₓ`, and similar material/oxide tokens as subscripted formulas only when local context supports chemical/material notation.
- `C-BRACKETED-REFERENCE-PREFIX-DEDUP`: before adding visible bibliography numbers, strip or reuse leading `[N]` prefixes even when page-anchor spans or inline tags precede them.

### Fix Requirements

- Add a unified unit-normalization pass before final HTML serialization:
  - accept `\mu\text{m}`, `\mu m`, `\mum`, italic `µ` plus `m`, escaped `&lt;sup&gt;2&lt;/sup&gt;`, and existing `<sup class="z2m-unit-exp">2</sup>`;
  - preserve dimensions with `×` and area exponents as semantic text/markup;
  - run on body paragraphs, captions, and table cells.
- Add a guarded material-formula repair:
  - target only tokens like `AlO x`, `HfO x`, `IrO x` when adjacent to oxide/material wording or known material contexts;
  - convert italic/superscript `x` to subscript-style formula markup;
  - do not apply this rule to numeric exponents, variables, coordinates, or generic single-letter math.
- Improve bibliography normalization:
  - for each reference `<li>`, ignore leading spans/anchors while checking for `[N]`;
  - if the `li` already begins with `[N]`, either strip `[N]` after assigning `ref-N` or use it as the sole visible number;
  - add an audit check for `^\d+\.\s*\[\d+\]` and for mismatch between visible bracket number and `id="ref-N"`.
- Add regression fixtures covering:
  - table cell `70 \mu\text{m} \times 20 \mu\text{m} (1 shaft)`;
  - caption areas `900/2000/4000/8000 µm²`;
  - mixed inline math `100 \,\mu\text{m} \times 40 \,\mu\text{m}` plus `4000 \,\mu\text{m}^2`;
  - material formulas `HfO<i>x</i>` and `AlO<i><sup>x</sup></i>`;
  - bibliography items beginning with `[1]` after a page-anchor span.

### Open Constraints

- This must not become a blanket rule that turns every trailing `x` into a subscript. The safe rule is context-driven: material formula tokens only, with tests proving that real exponents and variables remain unchanged.

## Schelles 2025

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-27/05_Schelles_2025_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Schelles и др. - 2025 - Optimization of sputtered iridium oxide microelectrodes for_3221a765/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Schelles и др. - 2025 - Optimization of sputtered iridium oxide microelectrodes for_3221a765/_z2m_stages/02.en.polish.html`
- Local source PDF copy: `md_output/new/electrodes_W7TECQDX/Schelles и др. - 2025 - Optimization of sputtered iridium oxide microelectrodes for_3221a765/_z2m_stages/00.source.pdf`

### Manual Notes From User

- Inline formulas still have rendering defects, for example `67.5 x 47.5\mum^2` and `Platinum electrodes, that are widely used in cochlear implants, already show electrode corrosion and tissue response at 100\muC cm^-2`.
- Spaces are sometimes lost around/inside formulas, for example `corresponding to a charge injection capacity (CIC)of2.3mCm^-2`.
- Sentence-final punctuation is sometimes lost after formulas, using the same example: `corresponding to a charge injection capacity (CIC)of2.3mCm^-2`.

### Verification Notes

- PDF page 2 has the intended prose and unit spacing: `Platinum electrodes... response at 100 μC cm−2 [13].` Raw represents this as `<math>100 \,\mu\text{C} \,\text{cm}^{-2}</math>`, while polish serializes it as `\(100 \,\muC \,cm^{-2}\)`. The polish form is less robust because `\muC` and `cm` are treated as math variables instead of text-style units.
- PDF page 4 contains `47.5 by 67.5 μm2 were made for the electrodes`; PDF page 7/Figure 2 contains `67.5 × 47.5 μm2`. Raw has several forms: plain `47.5 by 67.5 μm2were made forthe electrodes`, math `47.5 \times 67.5 \,\mu\text{m}^2`, and isolated exponent fragments. Polish improves some superscripts but still emits `\(67.5 \times 47.5 \,\mum^2\)` in the Figure 2 caption.
- PDF page 8 has the sentence `This occurred at a current of 350 μA, corresponding to a charge injection capacity (CIC) of 2.3 mC cm−2. Additionally...`. Raw already loses the final period: the paragraph ends immediately after `<math>(CIC) of 2.3 mC cm^{-2}</math>`, and the next paragraph begins `Additionally...`.
- Polish preserves that lost period and wraps the prose-bearing math as `\((CIC) of 2.3 mC cm^{-2}\)`. In rendered MathJax-style output, spaces inside math can collapse or look wrong, producing the user-observed visual class `CIC)of2.3mC...`.
- Some missing spaces are not formula-specific: Marker raw also emits OCR/text-layer spacing defects such as `lowertemperature`, `improvesthe`, `process(reactive`, `Vwater`, and `forthe`. These need a generic word-boundary repair/audit, but formula boundaries are the highest-risk subset because they affect scientific meaning.

### Verified Symptoms

| ID | Location | Symptom | Expected | First broken stage | Status |
|---|---|---|---|---|---|
| SCH2-01 | Introduction, platinum electrode charge density | Unit formula is serialized as `\(100 \,\muC \,cm^{-2}\)`, which can render as cramped math variables rather than readable `100 μC cm−2`. | Charge-density units should render as stable units with preserved spacing and exponent: `100 μC cm−2` or equivalent semantic markup. | `02.en.polish.html` worsens raw's more explicit `\mu\text{C}`/`\text{cm}` form | verified |
| SCH2-02 | Figure 2 caption and electrode-area text | Area dimensions appear as mixed forms such as `67.5 \times 47.5 \,\mum^2`, plain `μm2`, and escaped/superscript fragments. | Dimension and area units should normalize consistently: `67.5 × 47.5 μm²`, `47.5 by 67.5 μm²`, preserving intended multiplier words/symbols. | `01.en.raw.html`; polish only partially repairs | verified |
| SCH2-03 | Section 3.2 CIC sentence | Formula/prose boundary can render with lost spaces, e.g. `(CIC)of2.3mC...`, because prose `(CIC) of 2.3 mC cm^{-2}` is wrapped as math. | Only true formula/unit tokens should be math/semantic unit markup; prose and abbreviations should keep normal text spacing. | `01.en.raw.html` creates a prose-bearing math block; `02.en.polish.html` preserves it | verified |
| SCH2-04 | Section 3.2 after final formula | Source PDF has `2.3 mC cm−2. Additionally...`; raw and polish lose the period before `Additionally`. | If an inline formula ends a sentence, terminal punctuation from PDF/raw context must be preserved or restored before the next sentence/paragraph. | `01.en.raw.html`; repairable in polish with punctuation audit/fallback | verified |
| SCH2-05 | Body text adjacent to units/formulas | Non-formula spacing defects remain around scientific tokens, e.g. `μm2were`, `forthe`, `Vwater`, and `0.04for`. | Word-boundary repair should flag or fix high-confidence missing spaces without changing valid compact scientific notation. | `01.en.raw.html`; partially repairable in polish | verified |

### Root Cause Hypotheses

- Marker emits scientific units in too many shapes: text-layer `μm2`, MathML, TeX, escaped `<sup>`, and prose embedded inside `<math>`. The polish pass has several local repairs, but it does not first classify unit tokens and then normalize them consistently.
- The EN polish serializer converts some precise TeX forms to less precise MathJax-style snippets, for example `\mu\text{C}` becoming `\muC`; that risks both visual spacing defects and semantic ambiguity.
- Punctuation after final inline math is vulnerable because Marker can put the math at paragraph end and start the next sentence in a new paragraph, dropping the terminal punctuation that is visible in the PDF text layer.
- Generic OCR/text-layer spacing defects need a conservative boundary detector; formula-adjacent defects need stronger handling because TeX/MathJax ignores ordinary spaces inside math mode.

### Generalized Defect Classes

- `C-UNIT-TEXTSTYLE-IN-MATH`: when units remain in math notation, unit letters must be text-style/roman and spaced (`\mathrm{}` or HTML unit markup), not concatenated math variables like `\muC`.
- `C-PROSE-BEARING-MATH-SPLIT`: math blocks that contain prose abbreviations or surrounding words, e.g. `(CIC) of 2.3 mC cm^{-2}`, should be split into text plus unit markup.
- `C-FORMULA-TERMINAL-PUNCTUATION-RESTORE`: when a paragraph ends with inline math and the next paragraph starts with a new sentence, preserve or restore missing terminal punctuation using PDF text-layer evidence when available.
- `C-SCIENTIFIC-WORD-BOUNDARY-REPAIR`: detect high-confidence missing spaces around units, parentheses, and prose words without breaking valid compact tokens such as chemical formulas or variable names.

### Fix Requirements

- Extend the unit-normalization pass from Merken to cover charge/current units:
  - `μC`, `mC`, `nC`, `μA`, `kΩ`, `mV`, `V`, `s`;
  - compound units such as `mC cm−2`, `μC cm−2`, `mV s−1`;
  - TeX forms `\mu\text{C}`, `\muC`, `\text{cm}^{-2}`, `cm^{-2}`, `\mum^2`, and plain `μm2`.
- Add a pass that splits prose-bearing math:
  - keep `(CIC)` and words like `of` in normal text;
  - normalize only `2.3 mC cm−2` as a unit expression;
  - ensure rendered text has real spaces outside math/inline unit spans.
- Add punctuation repair/audit:
  - if an inline math/formula block is the last content in a paragraph and the following paragraph begins with an uppercase sentence starter, check for missing `.`, `;`, `:` or comma context;
  - when `00.source.pdf` is available, compare the local PDF text layer before inserting punctuation;
  - flag unresolved cases in `audit_en_polish`.
- Add conservative word-boundary repairs for high-confidence OCR spacing:
  - unit-to-word patterns like `μm2were`;
  - common prose merges such as `forintracorticalstimulation`, `Vwater`, `current(0.7V`;
  - avoid broad dictionary splitting that could corrupt scientific names, formulas, identifiers, or URLs.

### Regression Coverage Needed

- Fixture for `100 \,\mu\text{C} \,\text{cm}^{-2}` expected as stable `100 μC cm−2`/semantic unit markup, not `\muC`.
- Fixture for `67.5 \times 47.5 \,\mu\text{m}^2` and `67.5 \times 47.5 \,\mum^2` expected as `67.5 × 47.5 μm²`.
- Fixture for `<math>(CIC) of 2.3 mC cm^{-2}</math>` expected to split prose from unit markup and preserve spaces.
- Fixture for paragraph-ending formula followed by `Additionally` where the PDF/source text has `cm−2. Additionally`; expected output restores the period.
- Audit fixture for high-confidence missing spaces such as `μm2were`, `Vwater`, `0.04for`, while leaving valid chemical/material tokens untouched.

### Open Constraints

- Space repair must be conservative. It should prefer audit warnings over risky automatic edits when the boundary could be a formula, chemical notation, identifier, DOI/URL, or author/page abbreviation.

## Wang 2017

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-27/06_Wang_2017_en_polish.html`
- Stage raw: `md_output/new/headless_intracranial/Wang и др. - 2017 - A Novel Intracranial Pressure Readout Circuit for Passive Wirel_7c2701f3/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/headless_intracranial/Wang и др. - 2017 - A Novel Intracranial Pressure Readout Circuit for Passive Wirel_7c2701f3/_z2m_stages/02.en.polish.html`
- Local source PDF copy: `md_output/new/headless_intracranial/Wang и др. - 2017 - A Novel Intracranial Pressure Readout Circuit for Passive Wirel_7c2701f3/_z2m_stages/00.source.pdf`

### Manual Notes From User

- Text flow around Table III is broken:
  `given the antennas' and sensor's`
  / `TABLE III Antenna Parameters`
  / `is the function which describes localized tissue permittivity and conductivity of the human head sizes. A small antenna features...`

### Verification Notes

- PDF page 7 visually shows a two-column layout with Figure 16 and section V/A text in the left column, while Table III is a right-column float. The body sentence starts at the bottom of the left column: `Fig. 16 shows the k factor ... given the antennas' and sensor's`, then continues below the table in the right column with `sizes. A small antenna features...`.
- The correct body reading is therefore: `Fig. 16 shows the k factor for two antenna with distance varying based on (4)∼(8), given the antennas' and sensor's sizes. A small antenna features...`
- Table III also has a table note under the table: `fbrain is the function which describes localized tissue permittivity and conductivity of the human head.` That note must remain associated with Table III and must not be merged into the body sentence before `sizes.`
- `01.en.raw.html` already emits the interruption: paragraph ending `given the antennas' and sensor's`, then `<h4>TABLE III Antenna Parameters</h4>`, `<table>...`, then a paragraph with the table note followed by body continuation `sizes. A small antenna...`.
- `02.en.polish.html` preserves the same order while adding `id="table-iii"` and table links. It improves targetability but does not repair the reading flow or separate the table note from body continuation.
- The PDF text layer itself returns the same layout-order interleaving, so a PDF-text fallback alone is insufficient. The repair needs structural/layout-aware detection: table float plus incomplete surrounding sentence plus table note.

### Verified Symptoms

| ID | Location | Symptom | Expected | First broken stage | Status |
|---|---|---|---|---|---|
| WAN2-01 | Section V.A / Table III | Table III is inserted between `given the antennas' and sensor's` and `sizes.`, splitting a body sentence across a table float. | The body sentence should be rejoined as `given the antennas' and sensor's sizes.` while Table III remains a separate targetable table block. | `01.en.raw.html`; repairable in EN polish with table-aware continuation repair | verified |
| WAN2-02 | Table III note | Table note `fbrain is the function... human head.` is emitted as ordinary paragraph text immediately before the body continuation `sizes.` | Table notes/footnotes should stay visually and semantically inside or adjacent to the table block, not merge with surrounding prose. | `01.en.raw.html`; polish preserves | verified |

### Root Cause Hypotheses

- This is a two-column float ordering defect. Marker and the PDF text layer follow page layout order rather than logical reading order, so a right-column table and its note interrupt a sentence whose first half is in the left column and whose continuation is below the table.
- EN polish currently treats tables as fixed inline blocks and does not run the same incomplete-sentence continuation logic across table/figure floats.
- Table notes are not grouped into table units strongly enough; they can become ordinary paragraphs that interfere with body-continuation decisions.

### Generalized Defect Classes

- `C-TABLE-FLOAT-BODY-CONTINUATION`: tables can interrupt incomplete body sentences in multi-column PDFs; polish should rejoin the body text while keeping the table as a separate float.
- `C-TABLE-NOTE-ASSOCIATION`: table notes/footnotes immediately below a table should be grouped with that table and excluded from body-continuation text.
- `C-TWO-COLUMN-FLOAT-ORDERING`: when PDF/text order is column-layout order, use syntax and structural cues to distinguish logical prose order from float/table placement.

### Fix Requirements

- Extend `C-FLOAT-AWARE-BODY-CONTINUATION` to tables:
  - detect `body fragment -> table title/table/table note -> body continuation`;
  - consider the left fragment incomplete when it ends with possessives, conjunctions, prepositions, determiners, or other non-terminal syntax such as `sensor's`;
  - consider the right fragment a continuation when it starts with a lower-case word or sentence tail such as `sizes.`;
  - rejoin the body sentence without swallowing the table block.
- Group table captions/titles and notes:
  - `TABLE III Antenna Parameters` + `<table>` + `fbrain is...` should form one table unit;
  - links to `Table III` should target the table unit;
  - table notes should be styled/marked separately from body paragraphs.
- Add an audit warning for body paragraphs ending with suspicious incomplete fragments immediately before a table/figure and the following body paragraph beginning with a sentence tail.
- Do not rely solely on PDF text layer ordering for this class, because the local PDF text layer repeats the layout-order interleaving.

### Regression Coverage Needed

- Fixture for `Fig. 16 ... given the antennas' and sensor's` + `TABLE III` + table note + `sizes. A small antenna...`; expected body sentence is rejoined and table note remains inside the table unit.
- Audit fixture for a table inserted after a possessive/incomplete phrase and before a lower-case continuation.
- Negative fixture where a table legitimately appears between complete sentences; expected no reordering.

### Open Constraints

- Table movement must preserve visual reviewability: the table can remain near the original location, but the text reading order must not leave a sentence split across the table block.

## Teo 2025

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-27/07_Teo_2025_en_polish.html`
- Stage raw: `md_output/new/headless_llm_medicine/Teo и др. - 2025 - Generative artificial intelligence in medicine/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/headless_llm_medicine/Teo и др. - 2025 - Generative artificial intelligence in medicine/_z2m_stages/02.en.polish.html`
- Local source PDF copy: `md_output/new/headless_llm_medicine/Teo и др. - 2025 - Generative artificial intelligence in medicine/_z2m_stages/00.source.pdf`

### Manual Notes From User

- A model version became a citation link although it is not a reference: `Claude 4 and Grok 4)`.
- PDF has `highly specific medical task58.`, but HTML has `specific medical task. Sec.`.
- In and around `Clinical applications of generative artificial intelligence`, references became formulas and stopped being clickable.
- Page-break text merging is broken around: `However, Foresight's development has been halted owing to concerns regarding unauthorized data use—highlighting...`.
- Links are lost in `Description Evaluation)) 134–139.`, likely because of the dash/range.
- Table-related text merging is broken. The expected body flow is `Many previous trials of AI-based interventions were relatively small (often single-center)...`, then Table 1 and its note. HTML instead inserts the table note into the sentence after `relatively`, and leaves `small...` after the table.

### Verification Notes

- PDF page 5 and raw both contain model names such as `Claude 4 and Grok 4` as plain model-version text. In `02.en.polish.html`, the first occurrence becomes `Grok <sup><a href="#ref-4">4</a></sup>`, while the second occurrence `Grok 4 are trending...` remains plain. The false link is introduced by EN polish numeric citation linking near a closing parenthesis.
- PDF page 5 has `... highly specific medical task58. Smaller models...`. `01.en.raw.html` already emits `... highly specific medical task. Sec.` and also corrupts the following citation range `59,60` into `6,000` in `flagship models 6,000`. Polish preserves these recognition defects. This is not a real section marker.
- In `Clinical applications of generative artificial intelligence`, PDF page 5 has superscript citation ranges such as `71–73`, `12`, and `74`. Raw encodes them as inline math blocks like `<math display="inline">^{71-73}</math>`. Polish serializes them as literal MathJax snippets `\(^{71-73}\)`, so they are not clickable citation links.
- PDF pages 5-6 show a page break after `However,`; page 6 starts `Foresight's development...`. Raw and polish preserve this as two paragraphs: one ending `However,` and the next beginning `Foresight's development...`. The sentence is logically continuous and should be rejoined.
- PDF page 7 has `CIDEr (Consensus-based Image Description Evaluation))134–139.`. Raw contains escaped superscript `&lt;sup&gt;134–139&lt;/sup&gt;`; polish converts it to `<sup>134–139</sup>` but does not link it. Neighboring simple citations such as `133`, `140`, and `141` are linked, so the unlinked range is a range/dash parsing gap.
- PDF page 7 ends the body sentence with `Many previous trials of AI-based interventions were relatively`; PDF page 8 begins with Table 1, then the table note, then the body continuation `small (often single-center)...`. Raw emits `body fragment -> table -> table note -> body continuation`. Polish worsens the table-note association by moving the note text into the body fragment before the table title, producing `were relatively This list includes...`.

### Verified Symptoms

| ID | Location | Symptom | Expected | First broken stage | Status |
|---|---|---|---|---|---|
| TEO2-01 | Intro/model examples | `Grok 4` is mislinked as `Grok <sup><a href="#ref-4">4</a></sup>` even though it is a model version, not citation 4. | Numeric citation linking must protect known version/model-number contexts such as `GPT-5`, `Gemini 2.5 Pro`, `Claude 4`, `Grok 4`, `Llama 2`. | `02.en.polish.html` | verified |
| TEO2-02 | Model distillation section | Citation `58` after `task` is misrecognized as `Sec.`, and nearby `59,60` becomes `6,000`. | Superscript citation OCR errors should be recovered or at least flagged when the PDF/text context and bibliography support a citation number/range. | `01.en.raw.html`; polish preserves | verified |
| TEO2-03 | Clinical applications section | Citations are emitted as math snippets such as `\(^{71-73}\)`, `\(^{12}\)`, and `\(^{74}\)`, so they are not clickable. | Superscript-like inline math containing only citation numbers/ranges should be converted to citation links, not rendered as formulas. | `01.en.raw.html`; repairable in polish | verified |
| TEO2-04 | Foresight paragraph across pages | Paragraph split leaves `However,` at the end of one paragraph and `Foresight's development...` as a new paragraph. | Page-break continuation should rejoin discourse markers and their following clause into one paragraph/sentence. | `01.en.raw.html`; repairable in polish | verified |
| TEO2-05 | Evaluation metrics paragraph | Citation range `134–139` remains plain `<sup>134–139</sup>` and is not linked. | Superscript citation ranges with en dash/hyphen should link to valid bibliography targets, at minimum range endpoints and preferably the whole range. | `02.en.polish.html` range linkification gap | verified |
| TEO2-06 | Clinical evaluation / Table 1 | Table 1 interrupts `were relatively small...`; table note is inserted before the table and into body prose. | Body sentence should read `were relatively small... generalizability152.`; Table 1 and its note should remain a separate table unit. | `01.en.raw.html` split; `02.en.polish.html` worsens note placement | verified |

### Root Cause Hypotheses

- Numeric citation detection is too permissive around superscripts and closing punctuation, so model-version numbers can be linked when they happen to resemble citations.
- Marker can OCR superscript citations into ordinary words or numbers (`58` -> `Sec.`, `59,60` -> `6,000`), and current polish has no citation-recovery/audit pass comparing expected citation density against PDF text/bibliography.
- Citations represented as inline math are treated as real formulas. This preserves visual-ish superscripts but bypasses citation linking and click targets.
- Page and table float order from the PDF linearization is preserved too literally: discourse-marker continuation and multi-page table continuation are not repaired.
- Table notes are not strongly associated with their table before continuation repair, so they can be moved into body prose.

### Generalized Defect Classes

- `C-MODEL-VERSION-NUMBER-PROTECTION`: protect product/model version numbers from numeric citation linkification.
- `C-SUPERSCRIPT-CITATION-OCR-RECOVERY`: detect citation-looking OCR corruptions such as `Sec.` or `6,000` where PDF text/bibliography context indicates superscript citations.
- `C-MATH-SUPERSCRIPT-CITATION-LINKING`: convert inline math containing only citation superscripts/ranges into citation links.
- `C-CITATION-RANGE-LINKIFICATION`: link plain superscript ranges with hyphen/en dash/em dash separators.
- `C-DISCOURSE-MARKER-PAGE-CONTINUATION`: rejoin page-break paragraphs where the first fragment ends with `However,`, `Therefore,`, `Moreover,` or similar markers.
- `C-MULTIPAGE-TABLE-FLOAT-BODY-CONTINUATION`: repair body text split across a table that starts on the next page and has its continuation below the table.
- `C-TABLE-NOTE-ORDER-PRESERVATION`: table notes must remain attached to the table and must not be inserted into surrounding body sentences.

### Fix Requirements

- Add numeric citation guards before linkification:
  - do not link numbers in known model/version patterns (`GPT-5`, `Gemini 2.5`, `Claude 4`, `Grok 4`, `Llama 2`, `Stable Diffusion 3`, `DALL-E 3`, `Evo 2`, etc.);
  - require citation-like context, such as superscript markup, bracketed numeric citation, or proximity to previous/next citation tokens, before converting a bare number.
- Add citation-recovery/audit for OCR anomalies:
  - flag text like `task. Sec.` when the PDF text layer has `task58.` and reference 58 exists;
  - flag comma-number corruptions such as `models 6,000` where the PDF has `models59,60`;
  - prefer audit warnings when recovery confidence is low.
- Convert citation-like math to links:
  - recognize `^{12}`, `^{71-73}`, `^{153-156}` inside `<math>` or `\(...\)` as citations, not formulas;
  - support comma-separated and ranged groups;
  - preserve real mathematical exponents by requiring surrounding prose/citation context and valid bibliography numbers.
- Improve range linkification:
  - handle `<sup>134–139</sup>`, `<sup>142-147</sup>`, and mixed en dash/hyphen separators;
  - link each valid reference in the range or provide a stable range target behavior consistent with the rest of the project.
- Extend continuation repair:
  - rejoin `However,`/similar discourse-marker paragraph endings with the following paragraph when there is no structural boundary;
  - handle `body fragment -> multi-page table -> table note -> body continuation`;
  - group `Table 1 title + table + note` before deciding body continuation.

### Regression Coverage Needed

- Fixture where `Grok 4)` appears near real citations; expected no `#ref-4` link on the version number.
- Fixture for `task. Sec.` with PDF/source evidence of `task58.`; expected recovery to citation 58 or an audit warning.
- Fixture for `models 6,000` with source evidence of `models59,60`; expected recovery/audit.
- Fixture for `<math>^{71-73}</math>` and `\(^{153-156}\)`; expected citation links, not formulas.
- Fixture for `<sup>134–139</sup>`; expected range links.
- Fixture for `However,` at page end followed by body continuation; expected one paragraph.
- Fixture for `Many previous trials... relatively` + Table 1 + table note + `small (often single-center)...`; expected body sentence rejoined and table note attached to table.

### Open Constraints

- Citation-like math conversion must not corrupt real mathematical exponents. Require valid bibliography numbers and prose/citation context before converting.
- Model-version protection should be extensible by pattern, not a hard-coded Teo-only list.
