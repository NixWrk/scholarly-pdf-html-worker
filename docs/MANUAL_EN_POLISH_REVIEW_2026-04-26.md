# Manual EN Polish Review Findings 2026-04-26

Purpose: collect manual HTML/PDF comparison findings article by article, verify them against pipeline artifacts, and later consolidate them into generalized fix requirements.

Workflow reference: `docs/MANUAL_EN_POLISH_REVIEW_WORKFLOW_2026-04-26.md`

Local review copies: `D:\Git_Code\ZoteroPDF_2_MD\manual_review_en_polish_2026-04-26`

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

## Ahmed 2026

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-26/01_Ahmed_2026_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Ahmed и др. - 2026 - Robust minimally-invasive microfabricated stainless steel neura_3e6edbab/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Ahmed и др. - 2026 - Robust minimally-invasive microfabricated stainless steel neura_3e6edbab/_z2m_stages/02.en.polish.html`

### Manual Notes From User

- Author-affiliation numbers next to author names became reference links, although in the original article they are not bibliography citations.
- Some dimensions are damaged or not normalized, for example `as small as 25 m for 10- m`.
- Figure captions contain raw/verbose BioRender link markup, for example `<a href="https://BioRender.com/qms5tta">https://BioRender.com/qms5tta</a>).`
- Similar link-display defects appear inside caption/text fragments, for example `created in BioRender. Chamanzar, M. (2025) <a href="https://BioRender.com/nznmfl3">https://BioRender.com/nznmfl3</a>).`
- Figure 8 and its caption are in the wrong sequence.

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| AHM-01 | Article front matter, author line | Affiliation markers `1` and `2` after author names are converted into `#ref-1` / `#ref-2` links. | Author affiliation markers should remain plain affiliation/superscript markers and must not point to bibliography entries. | EN polish citation/linkification | verified |
| AHM-02 | Body text, electrode dimensions | Raw contains LaTeX-style units such as `25 \mu m`, `10- \mu m`, `1- \mu m`; polish can render them as plain `25 m` / `10- m`, losing the micro unit. | Micro-meter units should be normalized consistently, e.g. `25 um`, `10-um`, `1-um`, or an equivalent stable HTML representation. | Marker raw math/unit text plus EN polish normalization | verified |
| AHM-03 | Figure captions, BioRender credits | BioRender credit URLs are preserved as raw-looking anchor markup or overly literal external links inside captions. | BioRender credit should be readable and punctuation-stable; no visible raw HTML fragments or broken closing punctuation. | Marker raw escaped/inline anchor handling plus EN polish URL normalization | verified |
| AHM-04 | Figure caption fragments around BioRender credits | Caption text can be split around `created in BioRender`, author/year credit, and URL blocks, leaving link fragments that look like body text rather than caption content. | Caption credit fragments should remain part of the same figure caption block. | Marker block fragmentation plus EN polish caption assembly | verified |
| AHM-05 | Figure 8 area | Caption fragments and the `https://BioRender.com/8bfbsk2` heading appear before/around the image placeholder, so the figure-image-caption sequence is mixed. | The image and the complete Figure 8 caption should stay adjacent and ordered as a single figure block. | Marker ordering/extraction plus EN polish figure-block repair | verified |

### Root Cause Hypotheses

- The citation linker is applied too broadly and does not distinguish front-matter author affiliation superscripts from body/reference citations.
- Unit normalization does not reliably handle LaTeX micro-meter fragments before/after math conversion, especially when a hyphenated modifier is split as `10- \mu m`.
- BioRender credits arrive from Marker as inline/escaped HTML anchors and sometimes as isolated URL headings; polish currently linkifies or preserves them instead of normalizing caption-credit boilerplate.
- Figure block assembly does not merge caption continuations across URL headings and does not repair the common Marker pattern where an image placeholder appears after caption fragments.

### Generalized Defect Classes

- `C-AUTH-AFFILIATION-LINKIFY`: numeric author affiliations in article front matter must be excluded from bibliography-reference linkification.
- `C-MICRO-UNIT-NORMALIZATION`: LaTeX and split-text micro-meter units must be converted to stable readable text/HTML without losing the micro prefix.
- `C-FIGURE-CREDIT-URL-NORMALIZATION`: generated or extracted figure-credit URLs, especially BioRender credits, need caption-aware cleanup.
- `C-FIGURE-BLOCK-ORDER-ASSEMBLY`: fragmented figure captions, orphan URL headings, and nearby image placeholders must be assembled into coherent figure blocks.

### Fix Requirements

- Add front-matter awareness to reference linkification: before the abstract/main body, author lines and affiliation markers should not be converted to bibliography links; body citations and bibliography links must continue to work.
- Add robust unit normalization for `\mu m`, `\mu` plus separated `m`, and hyphenated modifiers such as `10- \mu m` / `1- \mu m`; the rule must be generic and not tied to this article text.
- Normalize caption credit anchors by unwrapping raw `<a href=...>` text, repairing punctuation, and treating BioRender-style credits as caption metadata/text instead of ordinary body links.
- Extend figure assembly to absorb caption continuation paragraphs and orphan URL headings around a figure, then place/keep the image placeholder and complete caption together.

### Regression Coverage Needed

- Unit tests for front-matter author affiliation markers beside names `Author 1, Author 2` plus normal body citations `[1]`/`(1)` in the same document.
- Unit tests for `25 \mu m`, `10- \mu m`, `1- \mu m`, and range-like forms such as `30 - 40 \mu m`.
- Unit tests for BioRender credit captions containing raw anchor markup and already-linkified anchors.
- Integration/regression fixture for the Figure 8 pattern: caption start, caption continuation, orphan URL heading, image placeholder, and remaining caption text.

## Kaiju 2017

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-26/02_Kaiju_2017_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Kaiju и др. - 2017 - High Spatiotemporal Resolution ECoG Recording of Somatosensory_2474f78c/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Kaiju и др. - 2017 - High Spatiotemporal Resolution ECoG Recording of Somatosensory_2474f78c/_z2m_stages/02.en.polish.html`

### Manual Notes From User

- Author-affiliation numbers next to author names became reference links, although in the original article they are not bibliography citations.
- Other non-reference numeric text also became links, for example affiliation prefixes in `1 Graduate School of Frontier Biosciences... 2 ...` and stimulation-condition text such as `(D2,4 mA)`.
- Figure 1 image is missing.
- Inline mathematical notation is displayed incorrectly, for example `is shown as iECoG(t) j . A coordinate of position j is shown as (x j , yj).`

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| KAI-01 | Article front matter, author line | Some affiliation markers after author names are converted into `#ref-*` links. | Author affiliation markers should remain plain affiliation/superscript markers and must not point to bibliography entries. | EN polish citation/linkification | verified |
| KAI-02 | Article front matter, affiliation paragraph | Affiliation labels `1`, `2`, `3`, `4` before institution names are converted into bibliography-reference links. | Institution affiliation labels should remain plain front-matter labels. | EN polish citation/linkification | verified |
| KAI-03 | Body/captions with scientific numeric text | Non-citation tokens such as `(D2, 4 mA)`, `D3, 4 mA`, and numeric parameter ranges can be linkified as references. | Numeric labels, stimulus conditions, units, table-like values, and model parameters should not become bibliography links unless they are in an explicit citation context. | EN polish citation/linkification | verified |
| KAI-04 | Figure 1 area | Raw and polish both have the Figure 1 caption, but no image block is adjacent to it; the first actual in-article image starts at Figure 2. | Figure 1 image should be preserved and assembled with its caption. | Marker raw image extraction plus EN polish figure-block assembly | verified |
| KAI-05 | Explanation text after COG equation | Subscripted variables are flattened as `iECoG(t) j`, `(x j , yj)`. | Inline variables should preserve subscript semantics, e.g. `iECoG(t)_j` and `(x_j, y_j)` or equivalent HTML/math. | Marker raw inline math extraction plus EN polish math normalization | verified |

### Root Cause Hypotheses

- The same broad citation-linkification rule observed in Ahmed also affects Kaiju front matter, but Kaiju shows the broader failure mode: plain numeric labels are linkified even inside affiliations, stimulus-condition labels, captions, and parameter text.
- Citation detection appears to rely too much on numeric tokens matching bibliography IDs and not enough on citation context, such as brackets, parentheses intended as citations, reference runs, or nearby citation punctuation.
- Marker raw already lacks a real Figure 1 image block: it extracted Figure 1 visual content as OCR text in a heading-like block, then kept only the caption; polish cannot recover the missing image from the current raw artifact.
- Inline subscript math in prose is not recognized as math and is flattened into ordinary words/spaces; polish keeps the raw flattening instead of reconstructing obvious variable-index patterns around equations.

### Generalized Defect Classes

- `C-AUTH-AFFILIATION-LINKIFY`: numeric author affiliations in article front matter must be excluded from bibliography-reference linkification.
- `C-NONCITATION-NUMERIC-LINKIFY`: numeric tokens in affiliations, stimulus labels, units, ranges, table values, and captions must not be treated as references unless they occur in a validated citation context.
- `C-MISSING-FIGURE-IMAGE-FROM-RAW`: when Marker emits a figure caption and OCR-like visual text but no corresponding image, the pipeline must detect the missing figure asset instead of silently producing a caption-only figure.
- `C-INLINE-MATH-SUBSCRIPT-FLATTENING`: inline mathematical variables with subscripts/superscripts in prose must be preserved or reconstructed generically.

### Fix Requirements

- Reuse the front-matter exclusion needed for Ahmed, and extend it to institution affiliation paragraphs, not only author-name lines.
- Tighten citation linkification so a bare number or comma-separated numeric token is not enough to create a reference link; require citation-shaped context and reject known non-citation contexts such as `D2, 4 mA`, dimensions, scientific notation, table values, and affiliation labels.
- Add an audit/check for caption-only figures: if `Figure N` is present and surrounding blocks contain no associated image while neighboring figures do, report the missing image as a raw extraction defect.
- Investigate whether Figure 1 can be recovered from original PDF/page assets or Marker output; if not recoverable automatically, keep this as a raw-stage failure that must be surfaced clearly.
- Add normalization for obvious inline subscript patterns near equations, including `iECoG(t) j`, `x j`, `yj`, and similar variable/index forms, while avoiding broad rewrites of ordinary prose.

### Regression Coverage Needed

- Unit tests for front-matter author markers and institution affiliation labels in the same article header.
- Unit tests for non-citation numeric text: `(D2, 4 mA)`, `D3, 4 mA`, `10-10 to 10^2`, channel counts, and table-like numeric cells must remain unlinked.
- Regression fixture where Figure 1 has a caption but no image block, while Figure 2+ have image/caption pairs; the audit should flag Figure 1 as missing rather than passing silently.
- Unit tests for inline math prose reconstruction: `iECoG(t) j`, `(x j , yj)`, and equivalent single-letter index patterns after displayed equations.

## Li 2026

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-26/03_Li_2026_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Li и др. - 2026 - Scaling beyond the vagus nerve historical and contemporary progres_f7f4c983/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Li и др. - 2026 - Scaling beyond the vagus nerve historical and contemporary progres_f7f4c983/_z2m_stages/02.en.polish.html`

### Manual Notes From User

- Page-bottom/front-matter text is placed inside the running article text and is not visually separated, for example `© The Author(s) 2026. Open Access ...` and `* Correspondence: Ellis Meng ellis.meng@usc.edu`.
- Because bibliography entries are visually separated in the PDF but not in HTML, it becomes unclear which exact source a citation link points to.
- Text merging failed when a page break/interruption occurred inside a literature citation, for example `Copyright 2018 John Wiley & Sons. 2024 a, b). Each shank was inserted at 45°`.

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| LI-01 | Introduction, first pages | Raw inserts affiliations, the Creative Commons license block, correspondence, page footer, and Figure 1 between `Upadhye et` and the citation continuation. Polish then merges `* Correspondence: Ellis Meng...` with `al. 2022)...`, making metadata look like body text. | Front-matter/license/correspondence/page-footer material should be separated from body text, and the interrupted body sentence should be rejoined. | Marker raw page-artifact extraction plus EN polish continuation handling | verified |
| LI-02 | Running page headers/footers | Page footer lines such as `Li et al. Bioelectronic Medicine (2026) 12:6 Page 2 of 33` and similar reference-section page footers remain as ordinary paragraphs. | Repeating page headers/footers should be removed or marked as non-body metadata, not shown inline. | Marker raw page artifact classification plus EN polish cleanup | verified |
| LI-03 | References section | References are emitted as very large paragraph chunks containing many entries. Polish adds entry numbers, but the bibliography is still not structured as one visual item per source; body citation links often target `#page-*` anchors inside the reference area rather than clear reference-entry IDs. | Each reference should be an individually separated targetable item, with stable IDs and visual target affordance for clicked citations. | EN polish reference-list parsing, citation target mapping, and CSS/HTML structure | verified |
| LI-04 | Figure 12 / thin film intraneural interfaces section | Main text is split at `(Choi et al.`; Figure 12 image/caption and a page footer intervene; the continuation `2024 a, b). Each shank...` remains as a separate paragraph. This makes the text appear to follow the figure-caption copyright text. | Paragraph continuation should be rejoined across removable page artifacts and safely around figure/caption insertions when a citation or sentence is visibly incomplete. | Marker raw ordering plus EN polish cross-block continuation repair | verified |

### Root Cause Hypotheses

- Marker emits PDF page furniture and front-matter sidebars in reading order, so article metadata and page footers can land inside body paragraphs.
- Polish continuation merging works for adjacent text fragments but does not skip removable/relocatable artifacts such as page footers, license blocks, correspondence blocks, affiliations, or intervening figure blocks.
- Reference parsing is still page/paragraph based: long bibliography runs are not split into source-level HTML nodes, and citation links point to page anchors rather than entry anchors.
- The continuation detector does not recognize incomplete author-year citations such as `Upadhye et` or `(Choi et al.` as high-confidence merge boundaries.

### Generalized Defect Classes

- `C-PDF-PAGE-FURNITURE-IN-BODY`: page headers, page footers, copyright/license blocks, and publisher boilerplate must not remain as normal article paragraphs.
- `C-FRONTMATTER-METADATA-RELOCATION`: affiliations, correspondence, and license metadata need a dedicated front-matter/metadata region or visual treatment, not insertion into the body stream.
- `C-REFERENCE-LIST-STRUCTURING-AND-TARGETING`: bibliography entries must be split into individual visual/semantic items and linked by stable reference IDs.
- `C-INTERRUPTED-CITATION-CONTINUATION`: incomplete citations and sentences split by page breaks, figure blocks, or page furniture must be rejoined generically.

### Fix Requirements

- Add reusable page-furniture detection for patterns such as `Author et al. Journal (year) volume:article Page X of Y`, publisher license/copyright boilerplate, and correspondence labels.
- Remove routine page headers/footers from body output; relocate useful metadata such as correspondence, affiliations, and license text into a visually separated metadata/front-matter section.
- Extend paragraph continuation repair so it can bridge across removable page-furniture blocks and handle incomplete author-year citation fragments like `et al.` plus a following year.
- For figure interruptions, allow the body paragraph to be rejoined while keeping the figure image/caption as a separate figure block at the correct local position.
- Rebuild the references section as structured entries, ideally `ol/li` or one `<p id="ref-n">` per source, and map body citations to those entries rather than opaque `#page-*` anchors when possible.
- Add visible target affordance for clicked/linked bibliography entries, for example stable numbering, spacing, indentation, and `:target`/class styling.

### Regression Coverage Needed

- Fixture where body text is split by affiliations, license/copyright, correspondence, page footer, and figure blocks; expected output keeps metadata separate and restores the body paragraph.
- Fixture for `(Choi et al.` followed by figure/caption/footer and `2024 a, b). Each shank...`; expected output rejoins the citation and sentence.
- Tests for stripping or relocating repeated page footer strings in body and references.
- Tests that long reference paragraphs are split into individual numbered entries with stable IDs and readable visual separation.
- Tests that author-year body citation links resolve to a distinct reference entry or a visibly highlighted target.

## Merken 2022

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-26/04_Merken_2022_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Merken и др. - 2022 - Thin flexible arrays for long-term multi-electrode recordings_d0ccb2cf/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Merken и др. - 2022 - Thin flexible arrays for long-term multi-electrode recordings_d0ccb2cf/_z2m_stages/02.en.polish.html`

### Manual Notes From User

- Author-affiliation numbers next to author names became reference links, although in the original article they are not bibliography citations.
- Some real bibliography citations did not remain links, apparently because current citation parsing does not handle hyphens, en dashes, and comma-separated ranges, for example `different functions of the brain [1-4].`, `the microwire arrays [11, 12]`, `Atlas [34, 35, 40–43]`.
- Unit powers/exponents became links or were flattened, for example `the 20 by 100 m2` and `(10 mg kg h − 1 IV)`.
- Formula-like content in table cells is displayed incorrectly, for example `Up to (up to 256 shafts)` and `(1 shaft)`.
- Non-citation numeric text became links, for example `phosphate buffered saline with a pH of 7,4`, `Macaca mulatta, female monkey 1: 7.5 kg...`, `Sedated electrophysiological recordings in monkey 1`, and `(week 8 to week 52)`.
- Degree signs are displayed incorrectly, for example `(1.5 ◦ × 1.5 ◦)`.
- Not all formulas are rendered correctly; some remain visible as raw text rather than formulas.

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| MER-01 | Article front matter, author line | Raw has affiliation superscripts such as `1,5,6`; polish converts them into `#ref-1`, `#ref-5`, `#ref-6` bibliography links. | Author affiliation markers should remain plain affiliation/superscript markers and must not point to bibliography entries. | EN polish citation/linkification | verified |
| MER-02 | Body citations and table citation labels | Real citations with ranges/lists remain unlinked as plain text: `[1-4]`, `[6, 7]`, `[8–10]`, `[11, 12]`, `[28–33]`, `[34, 35, 40–43]`, `[22-24]`. | Citation parser should link citation ranges and comma-separated lists, including hyphen and en-dash ranges. | EN polish citation parsing/linkification | verified |
| MER-03 | Abstract, body units, figure captions | Unit exponents and powers are flattened or treated as references, e.g. `20 by 100 \(\mu\) m 2`, `cd m − 2`, `10 mg kg h − 1`, and `900 \(\mu\) m 2`; some `1`, `2`, `52` tokens become ref links. | Unit exponents should be preserved as superscript/math and never interpreted as bibliography references. | Marker raw math/unit extraction plus EN polish citation/maths handling | verified |
| MER-04 | Table 1 | Table cells keep raw TeX-like fragments or malformed display math, e.g. `\(70 \mum \times 20 \mum\) (1 shaft)`, `Up to \[18 \times 21 mm\] (up to 256 shafts)`, and citation labels in rows stay unlinked. | Table math and citation text should be normalized cell-by-cell without changing ordinary parenthetical text. | EN polish table math/citation normalization | verified |
| MER-05 | Body text and figure captions | Non-citation numeric context is linked to references: pH `7,4` links to refs 7/4, monkey labels `monkey 1/2`, `week 52`, `month 1`, and figure-caption labels become `#ref-*`. | Scientific values, animal labels, week/month labels, pH values, and figure-caption numbering should not become bibliography links. | EN polish citation/linkification | verified |
| MER-06 | Visual-angle and temperature units | Degree symbols are emitted as spaced `◦`, for example `360 ◦`; user also observed visual-angle expressions like `1.5 ◦ × 1.5 ◦`. | Degree symbols should be normalized as `°` with correct spacing, e.g. `360°` or `1.5° × 1.5°`. | Marker raw symbol extraction plus EN polish unit normalization | verified |
| MER-07 | Body formulas and figure captions | Formula fragments remain visible as raw TeX/math text in prose, e.g. `\(\mu\)`, `\(\times\)`, `\mum^2`, `\(p = 1.80 \times 10^{-3}\)`, instead of rendering/normalizing consistently. | Inline math should render as math or be converted to stable readable HTML/text consistently across prose, captions, and tables. | EN polish math rendering/normalization | verified |

### Root Cause Hypotheses

- The same front-matter affiliation-linkification defect seen in Ahmed and Kaiju remains present for multi-affiliation superscripts.
- Citation parsing currently handles some single bracket citations but misses bracketed lists/ranges when they contain hyphens, en dashes, comma-separated groups, or mixed range/list forms.
- The false-positive citation rule is too permissive for bare numbers and superscripts, so unit exponents, animal labels, pH values, week/month labels, and caption labels are misclassified as bibliography references.
- Table normalization applies generic text/math cleanup to entire cells but does not parse table-cell math, citation labels, and parenthetical descriptors independently.
- Degree and micro/math symbol cleanup is inconsistent across body, captions, and tables; some raw TeX delimiters survive into final HTML.

### Generalized Defect Classes

- `C-AUTH-AFFILIATION-LINKIFY`: numeric author affiliations in article front matter must be excluded from bibliography-reference linkification.
- `C-CITATION-RANGE-LIST-LINKIFY`: real citations containing hyphen ranges, en-dash ranges, comma-separated lists, and mixed list/range forms must be linked.
- `C-NONCITATION-NUMERIC-LINKIFY`: numeric tokens in units, pH values, animal labels, week/month labels, captions, and table values must not be treated as references.
- `C-UNIT-EXPONENT-MATH-NORMALIZATION`: powers and unit exponents such as `m^2`, `kg^-1`, `h^-1`, and `cd m^-2` must remain math/unit notation, not links or plain trailing numbers.
- `C-TABLE-MATH-CELL-NORMALIZATION`: table-cell formulas and dimensions must be normalized per cell without damaging ordinary descriptors like `(1 shaft)` or `(up to 256 shafts)`.
- `C-DEGREE-SYMBOL-NORMALIZATION`: degree symbols and visual-angle expressions need stable `°` rendering and spacing.
- `C-INLINE-MATH-RENDERING`: raw TeX fragments that survive Marker extraction must be rendered or converted consistently.

### Fix Requirements

- Reuse the front-matter exclusion required for Ahmed/Kaiju and ensure it handles comma-separated multi-affiliations such as `1,5,6`.
- Extend citation parsing to recognize `[1-4]`, `[8–10]`, `[11, 12]`, `[34, 35, 40–43]`, and mixed hyphen/en-dash forms; link each referenced ID or the whole citation span in a stable way.
- Add citation false-positive guards for nearby unit tokens, decimal/comma numeric values, `pH`, `monkey`, `week`, `month`, figure captions, and math/superscript contexts.
- Normalize unit exponents before citation linking, preserving `µm²`, `m²`, `kg^-1`, `h^-1`, and similar forms as math/unit text.
- Apply table-specific normalization that keeps each `<td>`/`<th>` independent, handles dimensions and citations inside cells, and does not collapse/destructure parenthetical descriptors.
- Normalize `◦` and similar OCR degree symbols to `°`, with no stray spaces before the symbol and sensible spaces around multiplication signs.
- Decide a single output policy for inline math in final HTML: either render TeX via math support or convert simple scientific expressions to readable Unicode/HTML; apply the same policy to body, captions, and tables.

### Regression Coverage Needed

- Tests for multi-affiliation author superscripts `1,5,6` before the abstract.
- Tests for citation forms `[1-4]`, `[6, 7]`, `[8–10]`, `[22-24]`, `[34, 35, 40–43]`, and text containing multiple citations in one sentence.
- Tests that `pH 7,4`, `monkey 1`, `monkey 2`, `week 52`, `month 1`, `10 mg kg h − 1`, and `cd m − 2` are not bibliography links.
- Tests for unit exponent normalization: `20 by 100 \mu m<sup>2</sup>`, `900 \mu m 2`, `kg h − 1`, `m − 2`.
- Table fixture based on Table 1 with dimensions, citation labels, `(1 shaft)`, and `(up to 256 shafts)`.
- Tests for `360 ◦`, `1.5 ◦ × 1.5 ◦`, and visual-angle/temperature degree contexts.
- Tests for raw TeX fragments in body, figure captions, and table cells.

## Schelles 2025

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-26/05_Schelles_2025_en_polish.html`
- Stage raw: `md_output/new/electrodes_W7TECQDX/Schelles и др. - 2025 - Optimization of sputtered iridium oxide microelectrodes for_3221a765/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/electrodes_W7TECQDX/Schelles и др. - 2025 - Optimization of sputtered iridium oxide microelectrodes for_3221a765/_z2m_stages/02.en.polish.html`

### Manual Notes From User

- Author-affiliation numbers next to author names and in the affiliation block became bibliography links, although they are not references in the original article.
- Unit powers/exponents became links or were flattened, for example `2.3 mC cm-2` and `3200 um2`.
- Some real bibliography citations did not remain links, especially ranges and comma-separated lists such as `[1-4]`, `[6-8]`, and `[9, 17, 18, 20]`.
- Inline formulas and adjacent citations are damaged, for example citation `[13]` after a charge-density formula and `[17]` being swallowed into an iridium hydroxide equation.
- Some formulas remain as text rather than rendered/normalized math, for example `Ir(OH)_2 <-> IrOH + H^+ + e^-[17]`.
- Table values and captions do not normalize formula/unit notation, for example `2000 um2` and `3.1 mCcm-2 (CIC)`.
- Original PDF internal links scroll to a centered/highlighted target; the generated HTML lacks this visible target affordance.
- Unit/dimension formatting is inconsistent, for example `350 A`, `0.3V`, `0.7Vand`, and `100 uAand`.
- A figure cross-reference link is lost for `(figures 4(A), (B))`.

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| SCH-01 | Article front matter, author line and affiliations | Raw keeps author affiliation markers as superscripts (`1,2,6,*` etc.), but polish converts the numeric markers into `#ref-*` bibliography links. The affiliation block is marked as affiliations, but labels `1` to `5` are still linked to references. | Front-matter author and institution affiliation markers should remain affiliation markers, never bibliography links. | EN polish citation/linkification and front-matter handling | verified |
| SCH-02 | Article front matter | Polish merges e-mail and keywords into the author/front-matter paragraph, making metadata read like part of the author line. | E-mail, keywords, affiliations, contribution notes, and correspondence should be visually/semantically separated from author names and body text. | EN polish front-matter assembly | verified |
| SCH-03 | Abstract and body units | Unit exponents are flattened and/or linkified: `2.3 mC cm - 2`, `3200 um 2`, `0.35 mC cm - 2`, with `2` or `-2` sometimes converted to reference links. | Unit exponents such as `cm^-2` and `um^2` should remain unit/math notation and must be protected from citation linkification. | Marker raw math/unit extraction plus EN polish citation/maths ordering | verified |
| SCH-04 | Body citations | Real citation ranges/lists remain plain text: `[1-4]`, `[6-8]`, `[10-12]`, `[9-11]`, `[9, 17, 18, 20]`, `[9, 51, 52]`, `[41, 53]`. | Citation parser should link citation ranges and comma-separated lists, including hyphen/en-dash ranges and mixed list/range forms. | EN polish citation parsing/linkification | verified |
| SCH-05 | Inline formulas and adjacent citations | Formula/citation boundaries are unstable. One equation keeps the citation inside math text: `Ir(OH)_2 ... e^- [17]`; charge-density formula text near `[13]` is visually awkward and can separate the citation from the formula context. | Citations adjacent to formulas should stay outside the math span and remain linked; math rendering must not swallow citation brackets. | Marker raw math extraction plus EN polish math/citation boundary handling | verified |
| SCH-06 | Tables | Table cells keep unnormalized unit/math text such as `2000 um2`, `3.1 mCcm-2 (CIC)`, `90-95 mCcm-2`, and header fragments like `mC/cm \(^2\)`. | Table cells and headers should normalize units/math per cell, preserving exponents and spacing without damaging descriptors. | EN polish table math/cell normalization | verified |
| SCH-07 | Internal link navigation | Reference IDs exist, but clicked internal links do not provide the original-like visible target highlight/rectangle or equivalent focus cue. | Internal citation/figure/reference targets should scroll with a stable offset and show a temporary or `:target` visual highlight. | EN polish HTML/CSS target affordance | verified |
| SCH-08 | Figure captions and body units | Unit spacing and micro-unit rendering are inconsistent: `350 \(\mu\) A` can render/read as `350 A`, and raw/polish contain run-together forms such as `0.3V`, `0.7Vand`, `100 uAand`, `250 uA, respectively`. | Numeric values, units, and following words should be standardized generically: preserve micro prefixes and insert missing spaces around unit tokens and words. | Marker raw OCR spacing plus EN polish unit normalization | verified |
| SCH-09 | Figure cross-references | Single panel references such as `figure 4(D)` can be linked, but plural/multi-panel references such as `figures 4(A), (B)` remain plain text. | Figure cross-reference parser should link multi-panel and plural forms to the relevant figure target. | EN polish cross-reference linkification | verified |

### Root Cause Hypotheses

- The same broad citation-linkification rule seen in Ahmed/Kaiju/Merken is active here: numeric front-matter markers and unit exponents are eligible for `#ref-*` links before context has excluded them.
- Citation parsing is too narrow for real citations: it handles some single bracketed numbers but misses ranges, en-dash/hyphen forms, comma-separated lists, and mixed list/range citations.
- Math/unit normalization and citation linkification are ordered or scoped incorrectly. The linker sees unit exponents as reference numbers, while math normalization can include adjacent citation brackets inside the formula span.
- Table normalization does not apply the same math/unit cleanup as body text, and it does not repair missing spaces in compact scientific-unit strings such as `mCcm-2`.
- Internal-link targets are structurally present but have no CSS/HTML affordance comparable to the original PDF target rectangle.
- Figure cross-reference parsing is tuned for simple singular forms and does not cover plural multi-panel references like `figures 4(A), (B)`.

### Generalized Defect Classes

- `C-AUTH-AFFILIATION-LINKIFY`: numeric author affiliations in article front matter must be excluded from bibliography-reference linkification.
- `C-FRONTMATTER-METADATA-RELOCATION`: e-mail, keywords, affiliations, contribution notes, and correspondence metadata need dedicated front-matter structure/visual treatment.
- `C-CITATION-RANGE-LIST-LINKIFY`: real citations containing hyphen ranges, en-dash ranges, comma-separated lists, and mixed list/range forms must be linked.
- `C-NONCITATION-NUMERIC-LINKIFY`: numeric tokens in units, affiliation labels, table values, captions, and scientific values must not be treated as references unless citation context is validated.
- `C-UNIT-EXPONENT-MATH-NORMALIZATION`: powers and unit exponents such as `um^2`, `cm^-2`, `mC cm^-2`, and compact `mCcm-2` must remain math/unit notation, not links or plain trailing numbers.
- `C-MATH-CITATION-BOUNDARY`: citations adjacent to formulas must remain outside the math span and should be linked without corrupting the formula.
- `C-TABLE-MATH-CELL-NORMALIZATION`: table-cell formulas, dimensions, unit exponents, and citation labels must be normalized per cell/header.
- `C-INTERNAL-LINK-TARGET-HIGHLIGHTING`: internal reference/figure/table targets need visible `:target`/focus styling and stable scroll positioning.
- `C-UNIT-SPACING-STANDARDIZATION`: OCR/run-together scientific text must be repaired generically around values, units, and words, e.g. `0.7Vand` -> `0.7 V and`.
- `C-FIGURE-PANEL-CROSSREF-LINKIFY`: figure cross-references must handle plural and multi-panel forms such as `figures 4(A), (B)`.

### Fix Requirements

- Reuse and harden the front-matter exclusion needed for Ahmed/Kaiju/Merken so author superscripts, institution labels, equal-contribution notes, and correspondence markers are never bibliography links.
- Keep front-matter metadata as separate blocks: author line, affiliations, e-mail, keywords, equal-contribution notes, and correspondence should not collapse into one paragraph.
- Normalize/protect unit exponents before citation linkification. The citation linker must not run inside math/unit spans or on superscript-like exponent tokens.
- Extend citation parsing to recognize `[1-4]`, `[1-4], ... [6-8]`, `[9, 17, 18, 20]`, `[9, 51, 52]`, `[41, 53]`, and equivalent hyphen/en-dash variants.
- Add math/citation boundary cleanup so a trailing citation like `[17]` after `e^-` is outside the formula span and can become a normal reference link.
- Apply unit/math cleanup inside table cells and headers, including compact forms like `mCcm-2`, `um2`, and `mC/cm \(^2\)`.
- Add CSS/HTML target affordance for clicked references, figures, and tables, for example `scroll-margin-top` plus a visible `:target` outline/highlight.
- Add generic spacing repair for numeric values and units/words: `0.3V`, `0.7Vand`, `100 uAand`, and micro-current forms should normalize without article-specific strings.
- Extend figure cross-reference linkification to plural/multi-panel forms while keeping the visible text intact.

### Regression Coverage Needed

- Tests for Schelles-style front matter with author superscripts `1,2,6,*`, affiliation labels, equal-contribution note, e-mail, and keywords.
- Tests for citation forms `[1-4]`, `[6-8]`, `[10-12]`, `[9-11]`, `[9, 17, 18, 20]`, `[9, 51, 52]`, and `[41, 53]`.
- Tests that `2.3 mC cm-2`, `3200 um2`, `0.35 mC cm^-2`, and `mCcm-2` are normalized as units and never linked to references.
- Tests for math/citation boundaries: `Ir(OH)_2 ... e^-[17]`, `e^- [17]`, and a rendered formula immediately followed by `[13]`.
- Table fixture with `2000 um2`, `3.1 mCcm-2 (CIC)`, `90-95 mCcm-2`, and `mC/cm \(^2\)` in independent cells/headers.
- HTML/CSS check that following a `#ref-*` or figure target produces visible target styling and stable scroll positioning.
- Tests for unit spacing repairs: `0.3V`, `0.7Vand`, `100 uAand`, `250 uA, respectively`, and `350 \mu A`.
- Tests for figure cross-references: `figure 4(D)`, `figures 4(A), (B)`, and `figures 2(C), (E), 3(A)`.

## Wang 2017

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-26/06_Wang_2017_en_polish.html`
- Stage raw: `md_output/new/headless_intracranial/Wang и др. - 2017 - A Novel Intracranial Pressure Readout Circuit for Passive Wirel_7c2701f3/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/headless_intracranial/Wang и др. - 2017 - A Novel Intracranial Pressure Readout Circuit for Passive Wirel_7c2701f3/_z2m_stages/02.en.polish.html`

### Manual Notes From User

- Formula rendering and text order are broken in the methodology section around equations (1), (2), Fig. 4, Fig. 5, and equation (3). In the original, the sequence is: text introducing equation (1), equation (1), definition text, equation (2), `Fig. 4 shows...`, `As shown in Fig. 5...`, `At resonant frequency`, equation (3), then the following explanation. In HTML, formula blocks and prose are merged/reordered.
- Table/float handling is wrong around equation (9): the equation body appears first, then the table, and only after the table does the equation number `(9)` appear.

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| WAN-01 | Methodology, equation (1) | Raw has equation (1) and the following definition sentence as separate blocks, but polish merges them into one `block-type="Equation"` paragraph: equation `(1)` followed immediately by `To make (1) more clear...`. | A display equation and its following prose must remain separate blocks; equation text should not absorb the next explanatory paragraph. | EN polish equation/prose block assembly | verified |
| WAN-02 | Methodology, equation (2), Fig. 4/Fig. 5 text | Raw/original order is equation (2), then `Fig. 4 shows...`, then `As shown in Fig. 5...`. Polish merges the Fig. 5 paragraph into the equation (2) block and leaves `Fig. 4 shows...` after it, reversing the prose order. | Equation blocks and neighboring prose must preserve source/original order, especially when an equation-like prose block sits between two text paragraphs. | EN polish equation/prose ordering | verified |
| WAN-03 | Methodology, `Fig. 4 shows...` function paragraph | Raw marks the mixed prose/function paragraph as `block-type="Equation"` because it contains display math. Polish then treats it as an equation block even though it starts with prose. | Mixed prose plus formula paragraphs should be classified/handled as text-with-math unless they are pure display equations. | Marker raw block typing plus EN polish mixed math handling | verified |
| WAN-04 | Methodology, equation (3) | Raw/polish equation (3) contains `Z_1|_{\frac{\omega}{2m}=1}` while the original expression is the resonant condition `omega / omega_0 = 1`. | Mathematical OCR/extraction must preserve variable names and denominators in displayed equations. | Marker raw math recognition/extraction | verified |
| WAN-05 | Equation (9) near Signal Processing/Table IV | Polish emits the moving-average equation body, then `We chose N = 5`, then Table IV title/table, and only after the table a standalone `(9)` row. | Equation body and equation number must be an atomic unit; no paragraph, table, figure, or float may be inserted between them. | EN polish equation-number assembly and float relocation | verified |
| WAN-06 | Table IV / Signal Processing continuation | Raw places floating Table IV before the paragraph continuation `and the signal were located...`; polish relocates the table, but it lands inside the equation (9) group instead of at a safe boundary. | Floating tables should be moved only to safe block boundaries and must not split paragraphs, equations, captions, or equation-number groups. | Marker raw float order plus EN polish float/table placement | verified |
| WAN-07 | Math rendering/copyability in figure captions and equations | Source contains MathJax TeX for inline formulas such as `L_m`, `I_1`, `I_2`, and display equations, but the user-observed rendered/copied HTML loses visible formula text in places. | Final HTML math should render visibly and remain inspectable/copyable with a stable fallback, not become blank or inaccessible in review/copy workflows. | EN polish math rendering/fallback policy | verified |

### Root Cause Hypotheses

- Equation assembly is too eager to merge adjacent blocks when a display equation is followed by text, so prose after equations (1) and (2) becomes part of the equation block.
- The block classifier treats any paragraph containing display math as an equation block, even when it starts with prose (`Fig. 4 shows...`). This makes later ordering/merge logic handle mixed prose as a movable equation.
- Floating table relocation is performed after equation body/number splitting, so a table can be inserted between an equation and its number.
- The equation-number detector does not treat `(9)` as bound to the immediately preceding display equation once intervening blocks have been moved.
- Marker raw math extraction already contains at least one formula-content error (`omega/2m` instead of `omega/omega_0`), which polish cannot safely infer without a math-quality audit.
- Math rendering relies on MathJax/SVG output and lacks a robust review/copy fallback for rendered formulas.

### Generalized Defect Classes

- `C-EQUATION-PROSE-BLOCK-SEPARATION`: display equations must not absorb following explanatory prose.
- `C-EQUATION-PROSE-ORDER-PRESERVATION`: equation/prose cleanup must preserve the order of adjacent equation, mixed-math, and text blocks.
- `C-MIXED-PROSE-MATH-BLOCK-TYPING`: paragraphs that combine prose with formulas should not be treated as pure equation blocks.
- `C-DISPLAY-MATH-OCR-INTEGRITY`: displayed equations need quality checks for corrupted symbols, denominators, subscripts, and variables.
- `C-EQUATION-NUMBER-ATOMICITY`: equation body and equation number must stay together as a single structural unit.
- `C-FLOAT-TABLE-SAFE-RELOCATION`: floating tables must be relocated only at safe boundaries and must not split paragraphs/equations.
- `C-MATH-RENDERING-FALLBACK`: final HTML math should have a stable visible/copyable fallback in addition to visual rendering.

### Fix Requirements

- Before merging or relocating blocks, detect display-equation units as `{leading prose? + math body + equation number}` and keep the equation body/number atomic.
- Do not merge a following `block-type="Text"` paragraph into a previous equation merely because the previous block has an equation number; preserve block boundaries after numbered equations.
- Reclassify mixed prose/math paragraphs such as `Fig. 4 shows ... f(...) = ...` as text-with-math or a mixed block, not as a pure equation block eligible for equation-only movement.
- Preserve source order for neighboring equation/text blocks unless a float-relocation rule has a higher-confidence safe target.
- Run table/figure float relocation only after protected groups are formed, and reject insertion points inside protected equation groups or incomplete paragraphs.
- Add an equation-number binding pass that pulls orphan numbers like `(9)` back to the nearest compatible equation body before any table/figure placement.
- Add math quality/audit checks for suspicious OCR substitutions in equations, including `omega_0` becoming `2m`, missing subscripts, and impossible denominator tokens.
- Ensure MathJax-rendered formulas retain review/copy fallback text, for example accessible TeX/MathML annotations or nonblank fallback spans.

### Regression Coverage Needed

- Fixture for equations (1)-(3): equation (1), explanatory text, equation (2), mixed `Fig. 4 shows...` function paragraph, Fig. 5 prose, equation (3), and following explanation must remain in order.
- Test that equation (1) and `To make (1) more clear...` remain separate blocks.
- Test that equation (2) does not absorb `As shown in Fig. 5...`, and that `Fig. 4 shows...` remains before the Fig. 5 paragraph.
- Test mixed prose/math paragraph classification for `Fig. 4 shows Z1 is a function of ... f(...) = ...`.
- Fixture where a floating table is near an equation: no table/title/paragraph may appear between the equation body and number `(9)`.
- Test orphan equation-number repair for a standalone `(9)` after an intervening table.
- Math extraction audit fixture for `omega / omega_0 = 1` to catch corrupt output like `omega / 2m = 1`.
- Browser/HTML check that inline and display math have nonblank rendered output and a copyable/inspectable fallback.

## Teo 2025

Artifacts:

- Review copy: `manual_review_en_polish_2026-04-26/07_Teo_2025_en_polish.html`
- Stage raw: `md_output/new/headless_llm_medicine/Teo и др. - 2025 - Generative artificial intelligence in medicine/_z2m_stages/01.en.raw.html`
- Stage polish: `md_output/new/headless_llm_medicine/Teo и др. - 2025 - Generative artificial intelligence in medicine/_z2m_stages/02.en.polish.html`

### Manual Notes From User

- Author-affiliation numbers next to author names became bibliography links, although in the original article they point to author/affiliation footnotes at the bottom of the first page. The problem is partial/inconsistent: not every author marker is linked, and some markers are already corrupted in the raw text.
- A small line-break restoration defect remains in a figure caption: `on human input (required) \\ to evaluate for aspects such as accuracy,`.

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| TEO-01 | Article front matter, author line | Raw already corrupts the author line: corresponding-author/footnote icons appear as `©`, some affiliation markers are plain text, some remain `<sup>`, and some author/marker text is mis-OCRed, e.g. `Prasanth Mooya`, `Nigam H. Shah 10 13`, `Curtis P. Langlotz 10 14`, `Daniel Shu Wei Ting 1.2.5`. | Author names, corresponding-author markers, equal-contribution markers, and affiliation footnote markers should be preserved distinctly and not OCR-folded into author names. | Marker raw front-matter OCR/structure extraction | verified |
| TEO-02 | Article front matter, author line | Polish converts the surviving superscript affiliation markers beside authors into bibliography links (`#ref-1`, `#ref-2`, `#ref-4`, etc.), while raw-corrupted plain markers remain unlinked. | Author-affiliation/footnote markers should remain front-matter markers and must not point to bibliography entries. | EN polish citation/linkification | verified |
| TEO-03 | Article front matter, affiliation footnote block | Polish identifies the affiliation paragraph as `z2m-affiliations`, but some affiliation labels inside it (`1`, `2`, `8`, `9`, `11`, `12`, `15`) are still linked to bibliography refs. | Institution affiliation labels in front matter should remain affiliation labels, even when the block has already been classified as affiliations. | EN polish citation/linkification and front-matter handling | verified |
| TEO-04 | First-page reading order around affiliations | Raw inserts the long affiliation footnote block between body paragraphs about foundation models. Polish relocates it closer to front matter but still carries raw OCR/label defects. | First-page affiliations and footnotes should be extracted into a dedicated front-matter region without interrupting body continuity and without losing marker semantics. | Marker raw page-footnote ordering plus EN polish relocation | verified |
| TEO-05 | Figure 2 caption | Raw extracts the Fig. 2 caption as a single inline math block ending with a literal LaTeX linebreak `\\`, followed by the caption continuation in a separate text block. Polish rejoins the continuation but leaves the literal `\\` visible: `human input (required) \\ to evaluate...`. | Caption continuations split by line/page breaks should be merged while removing LaTeX linebreak escapes and preserving normal spacing. | Marker raw caption/math extraction plus EN polish caption continuation cleanup | verified |

### Root Cause Hypotheses

- The same front-matter affiliation-linkification defect seen in Ahmed/Kaiju/Merken/Schelles remains, but Teo adds a raw-stage complication: some author markers are not represented as clean superscripts, so polish can only partly recognize/link them.
- Nature-style author metadata uses multiple marker types: affiliation numbers, equal-contribution notes, corresponding-author symbols, and footnote affiliations. The current extraction does not preserve these as separate semantic marker types.
- Citation linkification still runs inside blocks already classified as affiliations, which shows that `z2m-affiliations` is not being used as a hard exclusion zone.
- Marker treats the Fig. 2 caption as LaTeX/math because it contains TeX-like `\label`, `\textbf`, and `\\`; polish unwraps some caption formatting but does not remove the literal LaTeX linebreak escape after continuation merge.

### Generalized Defect Classes

- `C-AUTH-AFFILIATION-LINKIFY`: numeric author affiliations in article front matter must be excluded from bibliography-reference linkification.
- `C-FRONTMATTER-MARKER-OCR-INTEGRITY`: author affiliation numbers, corresponding-author symbols, equal-contribution notes, and footnote markers must be preserved as distinct marker types.
- `C-FRONTMATTER-METADATA-RELOCATION`: affiliations and first-page footnote metadata need a dedicated front-matter/metadata region and must not interrupt body paragraphs.
- `C-AFFILIATION-BLOCK-LINKIFY-EXCLUSION`: once a block is classified as affiliations/front matter, citation linkification must not convert its labels into bibliography links.
- `C-CAPTION-LATEX-LINEBREAK-CLEANUP`: literal TeX linebreak escapes such as `\\` must be removed when caption continuations are merged.
- `C-CAPTION-MATH-MISCLASSIFICATION`: figure captions containing TeX-like formatting commands should be treated as captions/text, not as math expressions.

### Fix Requirements

- Reuse the front-matter exclusion rules from previous articles, and extend them to Nature-style footnote markers with multi-affiliation lists such as `1,2,15`, corresponding-author/equal-contribution symbols, and author-specific notes.
- Preserve or reconstruct front-matter marker semantics before citation linkification: affiliation labels, contribution markers, and corresponding-author symbols should not be passed through the bibliography-linkifier.
- Treat `z2m-affiliations` and equivalent metadata blocks as citation-linkification exclusion zones.
- Add raw/front-matter audits for suspicious author-line OCR patterns: stray `©`, marker runs like `10 13`, decimal-like affiliation lists such as `1.2.5`, and missing superscripts after author names.
- Relocate first-page affiliation footnote blocks to a dedicated metadata region while preserving body paragraph continuity.
- In captions, unwrap common TeX formatting commands (`\label`, `\textbf`) as caption markup/text and remove linebreak escapes `\\` during continuation merge.
- Ensure caption continuation repair produces a single readable caption with normal spacing around the join point, not an escaped TeX residue.

### Regression Coverage Needed

- Front-matter fixture for a Nature-style author line with `1,2,15`, `3,15`, `11,12`, corresponding-author symbols, equal-contribution markers, and a matching affiliation footnote block.
- Tests that author and affiliation-block labels remain unlinked even when matching bibliography IDs exist.
- Tests for partially degraded raw author markers: `© 1,2,15`, `10 13`, `10 14`, and `1.2.5` should trigger audit/repair behavior rather than bibliography links.
- Fixture where an affiliation footnote block appears between body paragraphs; expected output relocates it without interrupting body text.
- Caption fixture with `\label`, `\textbf`, `\\`, and continuation text in the next block; expected output has no visible backslash linebreak and preserves caption text.

## Global User Questions And UX Wishes

Status: captured before consolidation.

### User Notes

- Figure links should open the figure itself near the center of the viewport. Current behavior often targets the caption, so the caption becomes the first visible line and the image is above/out of view.
- Internal links should behave consistently across articles. Reference links, figure links, table links, and section links currently can scroll/focus/highlight differently.
- Figure+caption blocks and table+caption blocks could be visually separated by two horizontal rules or an equivalent stable frame, so they are easier to distinguish from running text.
- When the pipeline can infer that a figure should exist but Marker did not emit it, the HTML should show a clear warning/apology and tell the user to check the original PDF.
- Question: why is the PDF text layer not always used? Why does some content go through OCR, producing small defects such as `.` becoming `,`?
- Question: why are some internal/citation links lost? Are they not transferred from the PDF, and is it inherently difficult to preserve them?

### Preliminary Technical Answers

- Current Marker invocation does not force text-layer-only extraction. `MarkerRunner` calls `marker`/`marker_single` with `--drop_repeated_text`, `--drop_repeated_table_text`, and for `marker_single` sets `--PdfProvider_pdftext_workers 1`; it does not pass `--disable_ocr`, `--force_ocr`, or custom OCR/text-layer thresholds.
- Marker can use OCR when it decides the PDF provider/text layer is incomplete or unreliable. Its CLI exposes `--disable_ocr`, `--layout_coverage_threshold`, `--min_document_ocr_threshold`, `--PdfProvider_force_ocr`, `--PdfProvider_strip_existing_ocr`, and related thresholds. This means extraction mode is data-dependent unless we set an explicit policy.
- Even when a PDF has a text layer, that layer may be visually correct but structurally poor: wrong reading order, split glyphs, missing spaces, embedded-font encoding, equations drawn as vectors, figure text as raster, tables not represented as text, or hidden OCR text that does not match the rendered page. Marker may therefore OCR some pages/regions to recover layout or math/table content.
- Small OCR defects such as punctuation substitutions cannot be fully prevented after OCR has been chosen, but they can be reduced by preflight checks, conservative OCR thresholds, optional text-layer-only mode for suitable PDFs, and post-OCR audits/normalizers for high-confidence patterns.
- PDF internal links are not enough by themselves for our final HTML. Some links are preserved as PDF annotations, some are page/coordinate destinations, and many article citations are plain text rather than actual PDF hyperlinks. Our HTML currently rebuilds many links from text patterns after Marker, so losses happen when citation/cross-reference parsing misses a pattern or when Marker changes the surrounding text.
- It is not impossible, but it is a multi-source problem: combine PDF annotations where available, parsed bibliography/figure/table anchors, and deterministic text-pattern reconstruction. The current bugs are mostly in reconstruction/linkification scope, not in a fundamental impossibility.
- Missing figures are already partially detectable at audit level: `scripts/audit_en_raw.py` has checks like `R05` for a figure caption without a nearby image and `R06/R13` for figure content OCR leaking into headings. The next product step is to surface those findings in generated HTML, not only in audit reports.

### Global Requirements For Consolidation

- `G-UX-FIGURE-TARGET-CENTERING`: figure links should target a wrapper around the whole figure block, not only caption text; CSS/JS should scroll the block so the image+caption is centered or at least fully visible with a consistent offset.
- `G-UX-INTERNAL-LINK-STANDARDIZATION`: all internal links should use the same behavior model: stable target IDs, `scroll-margin`, visible `:target`/focus highlight, and consistent styling for references, figures, tables, equations, and sections.
- `G-UX-FIGURE-TABLE-VISUAL-SEPARATION`: figure+caption and table+caption groups should be rendered as distinct blocks with horizontal separators or an equivalent light boundary, without nesting unrelated content inside them.
- `G-OBS-MISSING-FIGURE-WARNING`: if a figure caption/cross-reference strongly indicates a missing figure image, final HTML should insert a visible warning block near the caption and point the user to the original PDF.
- `G-PDF-TEXT-LAYER-PREFLIGHT`: before Marker conversion, run a PDF text-layer quality check and record whether the document/page is text-layer-good, OCR-needed, mixed, or suspicious.
- `G-MARKER-OCR-POLICY`: expose/configure Marker OCR policy explicitly, including a conservative/default policy and a diagnostic text-layer-only pass for PDFs with good text layers.
- `G-RAW-QUALITY-AUDIT-SURFACING`: raw extraction warnings should be carried into stage logs and optionally into final HTML when the output is known to be incomplete or potentially misleading.
- `G-LINK-RECONSTRUCTION-MULTISOURCE`: link reconstruction should use both PDF annotations/destinations when available and deterministic text parsing for citations, figure refs, table refs, equations, and sections.

## Consolidation Pass

Status: complete; implementation planning and fixes pending.

### Cross-Article Defect Classes

| Class ID | Articles | Symptom Pattern | Root Layer | Fix Requirement | Priority | Status |
|---|---|---|---|---|---|---|
| CC-01 Front-Matter Marker Protection | Ahmed, Kaiju, Merken, Schelles, Teo, Li | Author affiliations, institution labels, contribution/correspondence markers, e-mail, keywords, and license/copyright blocks are mixed with body text or converted to bibliography links. | Marker raw front-matter extraction plus EN polish citation linkification | Detect front-matter/affiliation regions early, preserve marker semantics, relocate metadata to a dedicated area, and make those regions citation-linkification exclusion zones. | P0 | open |
| CC-02 Citation Grammar And False-Positive Control | Kaiju, Merken, Schelles, Teo, Li | Real citation ranges/lists are not linked, while non-citation numbers in affiliations, units, pH, animal labels, weeks/months, captions, and tables become links. | EN polish citation parsing/linkification | Replace broad numeric linking with a context-aware citation grammar: support ranges/lists and reject math/unit/front-matter/table/scientific-value contexts. | P0 | open |
| CC-03 Reference Entry Structuring And Targets | Li, Schelles, global UX | Bibliography entries are not always visually separated/targetable; clicked references lack consistent highlight or target affordance. | EN polish reference parsing and HTML/CSS | Split references into individual entries with stable IDs, map body citations to those IDs, and apply standardized target highlight/scroll behavior. | P1 | open |
| CC-04 Unit, Exponent, Degree, And Spacing Normalization | Ahmed, Merken, Schelles, Wang | Micro-units are lost, exponents become plain numbers or links, degree symbols are malformed, and values run into units/words. | Marker raw math/unit extraction plus EN polish normalization | Normalize units before citation linking; preserve micro prefixes, exponents, degree symbols, and spacing across body, captions, and tables. | P0 | open |
| CC-05 Math Rendering And Math/Citation Boundaries | Kaiju, Merken, Schelles, Wang, Teo | Inline math is flattened or raw TeX remains visible; citations can be swallowed into formulas; rendered math can be hard to inspect/copy. | Marker raw math extraction plus EN polish math rendering | Establish one math policy for simple scientific notation vs MathJax; keep citations outside math spans; add visible/copyable fallback. | P0 | open |
| CC-06 Equation Block Ordering And Number Atomicity | Wang, Merken, Schelles | Equation blocks absorb following prose, mixed prose/math is treated as pure equation, equation numbers are separated from bodies, and table relocation can split formula groups. | EN polish equation/table block assembly | Protect equation units as `{prose lead? + formula + number}` before relocation; preserve neighboring block order and keep equation numbers attached. | P0 | open |
| CC-07 Table Cell Math And Float Safety | Merken, Schelles, Wang | Table cells/headers keep malformed math/units, table citations are inconsistent, and floating tables can land inside paragraph/equation continuations. | Marker raw table extraction plus EN polish table normalization | Normalize each cell/header independently and relocate tables only at safe boundaries outside protected paragraphs/equations/captions. | P1 | open |
| CC-08 Figure/Caption Assembly And Missing Figure Disclosure | Ahmed, Kaiju, Schelles, Teo, global UX | Figure captions are fragmented, image/caption order is wrong, some figure images are missing, and caption-only figures pass silently. | Marker raw figure extraction plus EN polish figure assembly/audit | Assemble image+caption+credit as one block; detect caption-without-image and insert a visible warning when the raw image is missing. | P0 | open |
| CC-09 Cross-Reference Link Reconstruction | Schelles, Wang, Teo, global UX | Figure/table refs, multi-panel refs, and some existing PDF links are lost or inconsistently reconstructed. | EN polish link reconstruction; optional PDF annotation layer | Use deterministic text parsing plus PDF annotations/destinations where available; support plural and multi-panel forms such as `figures 4(A), (B)`. | P1 | open |
| CC-10 Internal Link UX Standardization | Schelles, global UX | Different internal links scroll/focus/highlight differently; figure links target captions instead of the whole figure. | EN polish HTML/CSS/optional JS | Target figure/table/reference wrappers, use consistent `scroll-margin`, `:target`/focus highlight, and center/fully reveal figure blocks on navigation. | P1 | open |
| CC-11 Page Furniture And Continuation Repair | Li, Teo, Wang | Page headers/footers, license/correspondence blocks, affiliations, figures, and tables interrupt body sentences or citations. | Marker raw reading order plus EN polish continuation repair | Remove/relocate page furniture and reconnect incomplete sentences/citations across removable or floated blocks. | P0 | open |
| CC-12 Caption TeX/URL Cleanup | Ahmed, Teo | BioRender URLs and TeX-like caption markup/linebreaks remain visible or break caption continuity. | Marker raw caption extraction plus EN polish cleanup | Treat captions as captions even when wrapped in math/escaped HTML; unwrap safe TeX/HTML markup, normalize credit URLs, and remove `\\` linebreak residues. | P1 | open |
| CC-13 PDF Text-Layer/OCR Policy And Raw Audit Surfacing | Kaiju, Wang, Teo, global questions | Marker sometimes OCRs despite a text layer, causing small OCR defects; raw-only missing images/math corruption are not surfaced to users. | Preflight, Marker invocation, raw audit/reporting | Add PDF text-layer preflight, explicit OCR policy, raw quality audits, and user-facing warnings for defects that polish cannot safely fix. | P1 | open |

### Final Implementation Requirements

- All fixes must be structural and pattern-based, not hard-coded to a single article title or exact sentence.
- The pipeline must preserve a clear boundary between three layers: raw Marker extraction defects, deterministic EN polish repair, and final HTML UX.
- Citation linking must become opt-in by validated context, not by bare number availability. Front matter, affiliations, units, math, captions, and table-value contexts are protected zones.
- Math/unit normalization must run before citation linkification so exponents and scientific values cannot become references.
- Figure/table/equation grouping must be performed before moving floats or repairing paragraph continuations.
- Final HTML should prefer explicit disclosure over silent failure: if the raw artifact lacks a figure image or has suspicious raw extraction damage, show a warning near the affected object and keep the stage/audit trail.
- Internal navigation must use a single contract for references, figures, tables, equations, and sections: stable IDs, predictable scroll offset, visible target highlight, and readable link styling.
- The implementation must keep all seven reviewed article pairs as regression fixtures or snippet fixtures.

### Recommended Fix Order

1. P0 link safety: front-matter/affiliation exclusion, validated citation grammar, false-positive guards, and reference-entry targets.
2. P0 protected structure: equation-number atomicity, figure/table/equation grouping, and safe continuation repair.
3. P0 scientific notation: unit/exponent/micro/degree normalization plus math/citation boundary cleanup.
4. P0 missing-content disclosure: caption-without-image detection surfaced in final HTML.
5. P1 visual/UX pass: internal-link target behavior, centered figure navigation, target highlights, and figure/table separators.
6. P1 raw-stage observability: PDF text-layer preflight, explicit Marker OCR policy, and raw audit integration.

### Regression Plan

- Pair auto-check sketch: `python scripts/audit_en_polish.py --roots md_output/new --out md_output/new/_quality_audit/en_polish_pair_audit.json`.
- Unit tests in `tests/test_single_file_html.py` for front-matter author markers, affiliation blocks, citation ranges/lists, false-positive numeric contexts, unit exponents, degree symbols, TeX caption linebreak cleanup, equation-number atomicity, table relocation safety, and multi-panel figure refs.
- Script tests in `tests/test_audit_en_polish.py` for automated warning/error detection mapped to `CC-*`: front-matter linkification, citation ranges, unit flattening, math/citation boundaries, equation/prose merge, orphan equation numbers, caption TeX residue, missing figures, caption-targeted figure links, and target UX.
- Raw-audit tests in `tests/test_audit_en_raw.py` for caption-without-image, figure OCR leakage into headings, malformed math snippets, page furniture, and suspicious front-matter marker OCR.
- Golden snippet fixtures from all seven articles: `01_Ahmed`, `02_Kaiju`, `03_Li`, `04_Merken`, `05_Schelles`, `06_Wang`, and `07_Teo`.
- End-to-end polish rerun for all seven `01.en.raw.html` inputs, producing fresh `02.en.polish.html` outputs for comparison against the manual findings.
- HTML behavior checks for target navigation: clicked `#fig-*` reveals image+caption, clicked `#ref-*` highlights the reference entry, and table/equation links follow the same visual contract.
- Acceptance gate: every verified symptom is either fixed in polish output or replaced by an explicit user-facing warning when the raw artifact lacks recoverable source content.
