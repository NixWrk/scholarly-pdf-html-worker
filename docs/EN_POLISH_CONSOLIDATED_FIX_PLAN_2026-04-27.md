# EN Polish Consolidated Fix Plan 2026-04-27

Purpose: turn the second manual review into one generalized repair plan for the
EN polish pipeline. This document is an implementation map, not an article-by-
article symptom log. The evidence log remains in
`docs/MANUAL_EN_POLISH_REVIEW_ROUND2_2026-04-27.md`.

## Inputs Reviewed

- Round 1 review: `docs/MANUAL_EN_POLISH_REVIEW_2026-04-26.md`
- Round 2 review: `docs/MANUAL_EN_POLISH_REVIEW_ROUND2_2026-04-27.md`
- Review copies: `manual_review_en_polish_2026-04-27/`
- Current polish code: `src/zoteropdf2md/single_file_html.py`
- Current audit sketch: `scripts/audit_en_polish.py`
- Current raw audit: `scripts/audit_en_raw.py`
- Current tests: `tests/test_single_file_html.py`,
  `tests/test_audit_en_polish.py`

## Operating Rules

- Do not hard-code article names, titles, or one-off text fragments as fixes.
- Every code repair needs either a transformation test, an audit test, or both.
- Prefer conservative normalization plus audit warnings over risky rewrites.
- Use the PDF text layer as optional evidence/fallback for suspicious regions,
  not as the only required path. The pipeline must still behave reasonably when
  the PDF is unavailable.
- When recovery is impossible or low-confidence, preserve visible content and
  emit an explicit warning instead of silently hiding the defect.

## Current Code Map

| Area | Current location | Relevant functions/checks |
|---|---|---|
| Main EN polish pipeline | `src/zoteropdf2md/single_file_html.py` | `polish_html_document` |
| Readability CSS / target UX | `single_file_html.py` | `_DEFAULT_READABILITY_STYLE`, `_inject_default_styles` |
| Figure anchors/linking | `single_file_html.py` | `_add_figure_anchors`, `_rewrite_existing_page_figure_links`, `_link_figure_refs`, `_insert_missing_figure_warnings` |
| Table anchors/linking | `single_file_html.py` | `_add_table_anchors`, `_rewrite_existing_page_table_links`, `_link_table_refs`, `_normalize_table_caption_style` |
| Citation/reference linking | `single_file_html.py` | `_add_reference_ids_and_citation_links`, `_convert_latex_sup_citations`, `_move_trailing_bracket_citations_out_of_inline_tex`, `_strip_reference_links_in_protected_blocks` |
| Units/math cleanup | `single_file_html.py` | `_normalize_scientific_units`, `_mark_unit_exponent_superscripts`, `_convert_math_tags_to_tex`, `_fix_latex_text_commands`, `_repair_common_math_ocr_substitutions` |
| Reading-order repair | `single_file_html.py` | `_repair_sentence_breaks_at_page_boundaries`, `_repair_sentence_breaks_around_figure_blocks`, `_repair_sentence_breaks_around_box_blocks`, `_reorder_table_block_away_from_formula_context` |
| Image inlining | `single_file_html.py` | `inline_images_from_html_file` |
| EN polish audit | `scripts/audit_en_polish.py` | existing P01-P19 checks for citations, units, figure/table UX, missing figures |
| Raw audit | `scripts/audit_en_raw.py` | raw image/caption/formula/reference diagnostics |

## Workstream 1: Review Packaging And Image Integrity

### Evidence

- The `manual_review_en_polish_2026-04-27` folder contains HTML copies but no
  `_page_*.jpeg` sidecar images.
- All reviewed HTML files still reference relative image paths. Therefore the
  manual review copies can show broken images even when the original stage
  folder has the image assets.

### Defect Classes

- `C-REVIEW-PACKAGE-IMAGE-ASSETS`
- `C-BROKEN-IMAGE-SRC-AUDIT`

### Implementation

- Add a small reusable review-collection helper, for example
  `scripts/collect_en_polish_review.py`.
- Prefer article-specific subfolders in the review bundle to avoid `_page_*`
  filename collisions between articles.
- For each `02.en.polish.html`, either:
  - copy every referenced local image beside the copied HTML, or
  - create a self-contained HTML copy by reusing `inline_images_from_html_file`.
- Add an audit check in `scripts/audit_en_polish.py` that reports local
  `<img src="...">` values whose target file is missing relative to the HTML.

### Tests

- A review packaging fixture with `02.en.polish.html` referencing
  `_page_1_Figure_1.jpeg` must produce a review copy where the image resolves.
- An audit fixture with a missing local image must produce a high-severity
  defect.
- Data URI images and remote URLs must not be reported as missing local files.

### Acceptance

- New manual review folders are viewable without broken local figures.
- Broken image assets are caught before manual review starts.

## Workstream 2: Figure/Table Unit Model, Visual Frame, And Navigation

### Evidence

- Current CSS applies borders to `p[id^="fig-"]`,
  `p.z2m-figure-caption`, `p[id^="table-"]`, and `figcaption`, which can create
  too many visual lines/rectangles.
- Figure/table targets are inconsistent: sometimes the image/table is the
  target, sometimes the caption is the target.
- User requirement: a predictable block:
  `horizontal rule -> figure/table -> caption/title/notes -> horizontal rule`.
- Ahmed Figure 8, Li Figure 2, Wang Table III, and Teo Table 1 show that
  figures/tables need a full unit model, not separate styling of loose nodes.

### Defect Classes

- `C-FIGURE-TABLE-VISUAL-FRAME-STANDARDIZATION`
- `C-FLOAT-TARGET-WRAPPER-STANDARDIZATION`
- `C-FLOAT-HIGHLIGHT-STANDARDIZATION`
- `C-FIGURE-FULL-PAGE-FLOAT-ASSEMBLY`
- `C-CAPTION-CREDIT-CONTINUATION`
- `C-TABLE-NOTE-ASSOCIATION`

### Implementation

- Introduce one wrapper per float unit:
  - `div.z2m-float-unit.z2m-figure-unit#fig-N`
  - `div.z2m-float-unit.z2m-table-unit#table-N`
- Move stable IDs from the image/caption/table node to the wrapper. Keep
  compatibility classes on inner nodes, but do not target them directly.
- Update `_add_figure_anchors`, `_add_table_anchors`,
  `_rewrite_existing_page_figure_links`, `_rewrite_existing_page_table_links`,
  `_link_figure_refs`, and `_link_table_refs` to target wrappers.
- Replace separate paragraph borders with wrapper CSS:
  - one top border;
  - content image/table;
  - caption/title/notes;
  - one bottom border;
  - `scroll-margin-top` and `:target` highlight on the wrapper.
- Assemble fragmented figure blocks before anchor assignment:
  - caption title/text before image;
  - BioRender URL/credit emitted as `h4`;
  - caption continuation after image;
  - delayed nearby image after a caption.
- For missing images, place the warning inside the figure wrapper so that the
  user sees a stable float unit and knows to inspect the PDF.

### Tests

- Figure fixture: image plus caption becomes one wrapper with one ID and one
  visual frame.
- Table fixture: caption/title, table, and notes become one wrapper with one
  target.
- Ahmed-like fixture:
  `caption -> credit URL heading -> caption continuation -> image -> caption`
  becomes one figure unit with the image before the final caption flow.
- Link fixture: references to `Fig. 8` and `Table III` target the wrapper, not a
  caption paragraph.
- Audit fixture: caption-targeted figures/tables are reported.

### Acceptance

- Clicking a figure/table link consistently scrolls to a visible whole unit.
- The highlighted target is the wrapper for every article.
- Float blocks use exactly one top and one bottom separator.

## Workstream 3: Reference/Citation Identity And Link Preservation

### Evidence

- Ahmed reference IDs drift because raw bibliography list items are split by
  page breaks and anchors are assigned by list ordinal instead of visible
  bibliography number.
- Merken has duplicate visible reference prefixes such as `1. [1]`.
- Kaiju/Li author-year links often point to `#page-*` anchors inside reference
  list items, so navigation reaches the right area but only highlights the
  number or page marker.
- Li loses many author-year links.
- Teo has citation ranges turned into math, lost ranges such as `134-139`, and
  false positive links around model version numbers such as `Grok 4`.
- Front matter, affiliations, footnotes, dimensions, and model versions still
  need stronger citation-linkification protection.

### Defect Classes

- `C-REFERENCE-LIST-NORMALIZATION-BEFORE-LINKING`
- `C-REFERENCE-CONTINUATION-MERGE`
- `C-REFERENCE-TARGET-AUDIT`
- `C-BRACKETED-REFERENCE-PREFIX-DEDUP`
- `C-PAGE-ANCHOR-TO-REFERENCE-RETARGETING`
- `C-AUTHOR-YEAR-CITATION-RETARGETING`
- `C-REFERENCE-LINK-PRESERVATION`
- `C-FOOTNOTE-MARKER-PROTECTION`
- `C-MODEL-VERSION-NUMBER-PROTECTION`
- `C-MATH-SUPERSCRIPT-CITATION-LINKING`
- `C-CITATION-RANGE-LINKIFICATION`
- `C-SUPERSCRIPT-CITATION-OCR-RECOVERY`

### Implementation

- Add a bibliography normalization pass before `_add_reference_ids_and_citation_links`:
  - detect the reference section;
  - parse visible leading reference numbers independently from `<li>` ordinal;
  - merge continuation-only items into the previous reference;
  - remove duplicate prefixes such as `1. [1]`;
  - assign `id="ref-N"` from the trusted visible number when available.
- Build a page-anchor-to-reference map:
  - if `#page-*` lives inside `<li id="ref-N">`, rewrite incoming citation links
    from `#page-*` to `#ref-N`;
  - apply this to author-year citations as well as numeric citations.
- Ensure the `id` and target highlight are on the whole `<li>`, not on a number
  span or embedded page marker.
- Strengthen protected zones before numeric linkification:
  - front matter and affiliations;
  - author contribution/correspondence notes;
  - page footnotes;
  - table cells with dimensions/animal metadata/week ranges;
  - model version expressions such as `Claude 4`, `Grok 4`;
  - known unit exponents.
- Convert citation-like math superscripts back to citations only when the
  content is a valid citation range/list and the surrounding context is prose.
- Preserve true math and unit exponents by checking unit and equation context.

### Tests

- Ahmed-like split reference fixture:
  reference `25` continuation starts on the next item, then real `26`; IDs do
  not drift.
- Duplicate prefix fixture: `1. [1] Hubel...` normalizes to one visible number
  and one `ref-1` target.
- Page-anchor retarget fixture: author-year link to `#page-29-11` inside
  `li#ref-42` rewrites to `#ref-42`.
- Footnote fixture: `low tensile strength<sup>1</sup>` remains a footnote marker
  when a page footnote is present, not a bibliography reference.
- Model-version fixture: `Claude 4 and Grok 4` is not linkified.
- Teo-like fixture: `^{71-73}` and `134-139` become clickable citation ranges
  when references exist.

### Acceptance

- No visible `ref-N` anchor contains a different leading reference number.
- Author-year and numeric citations target full bibliography entries.
- False positives in front matter, footnotes, units, and model names are
  protected.

## Workstream 4: Scientific Units, Inline Math, And Formula Boundaries

### Evidence

- Merken and Schelles show unstable unit rendering: sometimes number and unit
  are both math, sometimes only the symbol is math, sometimes unit exponents
  become citation links.
- Examples include `70\mum x 20 \mum`, `4000\mum^2`, `67.5 x 47.5\mum^2`,
  `100\muC cm^-2`, `mCcm^-2`, missing spaces after `(CIC)`, and lost sentence
  periods after formula repair.
- Kaiju has a local variable-index error where `j` should be subscript only in
  a specific equation-defined context.
- Merken has chemical/material notation such as `AlOx` where `x` may need a
  subscript, but a global `x` rule would break dimensions and prose.

### Defect Classes

- `C-SCIENTIFIC-UNIT-SEMANTIC-NORMALIZATION`
- `C-UNIT-DIMENSION-NORMALIZATION`
- `C-AREA-UNIT-EXPONENT-NORMALIZATION`
- `C-TABLE-CELL-MATH-NORMALIZATION`
- `C-UNIT-TEXTSTYLE-IN-MATH`
- `C-PROSE-BEARING-MATH-SPLIT`
- `C-SCIENTIFIC-WORD-BOUNDARY-REPAIR`
- `C-FORMULA-TERMINAL-PUNCTUATION-RESTORE`
- `C-CHEMICAL-FORMULA-SUBSCRIPT-GUARD`
- `C-POST-EQUATION-VARIABLE-INDEX-RESTORATION`

### Implementation

- Define a single simple-measurement policy:
  - simple measurements should be readable text/HTML, not fragmented MathJax;
  - keep unit exponents as `<sup class="z2m-unit-exp">...</sup>`;
  - never link unit exponents as citations;
  - preserve full display equations as MathJax.
- Extend `_normalize_scientific_units` and `_mark_unit_exponent_superscripts` to
  normalize:
  - `\mum`, `\mu m`, `um`, mojibake micro variants;
  - `m2`, `um2`, `cm-2`, `cm^-2`;
  - compact forms such as `mCcm^-2`;
  - `x`/multiplication in dimensions to a stable `x` or multiplication symbol;
  - missing spaces around units and following words.
- Add a prose-bearing math splitter:
  - if a math span contains ordinary prose glued to a measurement, split the
    prose out and normalize only the measurement.
- Add punctuation restoration after formula normalization:
  - if the original sentence had terminal punctuation after a formula, preserve
    it after repair.
- Add guarded chemical formula handling:
  - support material tokens like `AlOx`, `HfOx`, `IrOx` only in chemistry/material
    contexts;
  - do not convert `x` in dimensions or ordinary text.
- Add context-aware variable-index repair:
  - inspect nearby display equations for variable forms such as `iECoG(t)_j`,
    `x_j`, `y_j`;
  - repair only matching nearby prose forms;
  - never globally rewrite standalone `j`.

### Tests

- Unit fixtures for inline prose, table cells, and captions.
- Citation-vs-unit exponent fixture: `cm^-2` and `um^2` must not create
  `z2m-ref-link`.
- Prose-glue fixture: `(CIC)of2.3mCm^-2` becomes readable with spaces.
- Terminal punctuation fixture: a sentence ending with a measurement keeps the
  period.
- Chemical guard fixture: `AlOx` in a material sentence receives the expected
  subscript, but `70 um x 20 um` remains a dimension.
- Kaiju-like fixture: only equation-defined `j` indices are restored.

### Acceptance

- Simple measurements are visually consistent across articles.
- Unit exponents are never mistaken for bibliography links.
- True formulas remain formulas, and prose does not disappear into math spans.

## Workstream 5: Reading Order, Float Interruptions, Footnotes, And End Sections

### Evidence

- Li Figure 2 interrupts a body sentence: `and` ... figure/caption ... `vary`.
- Wang Table III interrupts a sentence around antenna/sensor sizes.
- Teo Table 1 interrupts `relatively small...`, and table notes are interleaved
  with body text.
- Kaiju final page interleaves `FUNDING`, `REFERENCES`, and `SUPPLEMENTARY
  MATERIAL` because of two-column layout ordering.
- Li page footnote text is placed in the body and not visually separated.
- Ahmed references and full-page Figure 8 prove that page breaks and float
  layout are a recurring source of semantic ordering defects.

### Defect Classes

- `C-FLOAT-AWARE-BODY-CONTINUATION`
- `C-TABLE-FLOAT-BODY-CONTINUATION`
- `C-MULTIPAGE-TABLE-FLOAT-BODY-CONTINUATION`
- `C-TWO-COLUMN-FLOAT-ORDERING`
- `C-TWO-COLUMN-END-SECTION-ORDER-REPAIR`
- `C-DISCOURSE-MARKER-PAGE-CONTINUATION`
- `C-TABLE-NOTE-ORDER-PRESERVATION`
- `C-FOOTNOTE-BLOCK-EXTRACTION`

### Implementation

- Extend sentence-continuation repair to understand float wrappers:
  - detect incomplete left paragraph + float/table/figure + lowercase or
    syntactically dependent right continuation;
  - repair reading order while keeping the float visually nearby.
- For figures and tables, assemble the complete float unit first, then decide
  whether the float should remain between paragraphs or move after the completed
  sentence.
- Add table-note association:
  - keep explanatory notes and metric descriptions with the table wrapper;
  - do not let notes become the continuation of body prose.
- Add end-section ordering repair before reference normalization:
  - if `REFERENCES` appears between an incomplete `FUNDING`/`ACKNOWLEDGEMENTS`/
    `SUPPLEMENTARY MATERIAL` paragraph and its continuation, move the
    continuation back under its owning heading before the reference list.
- Add footnote extraction:
  - detect page-bottom footnote blocks with matching superscript markers;
  - render them as separated notes/callouts;
  - protect footnote markers from bibliography linkification.

### Tests

- Li-like figure interruption fixture: body sentence is readable before/after
  Figure 2.
- Wang-like table interruption fixture: table does not split the sentence
  around `sizes`.
- Teo-like table fixture: `relatively small...` remains body text before the
  table, table notes stay inside the table unit.
- Kaiju-like end-section fixture: full `FUNDING`, then `SUPPLEMENTARY MATERIAL`,
  then `REFERENCES`.
- Footnote fixture: page note is separated and marker is not a ref link.

### Acceptance

- Floats do not split ordinary sentences in the final reading order.
- Terminal sections are not interleaved with references.
- Footnotes are visually separated and semantically protected.

## Workstream 6: PDF Text-Layer Fallback And Diagnostics

### Evidence

- For Ahmed Figure 8 and references, the local `00.source.pdf` text layer was
  cleaner than Marker raw in several suspicious areas.
- For Kaiju final sections, the PDF text layer preserves the semantic order
  better than Marker HTML.
- PDF text is still not guaranteed to be available or perfect, so it should
  guide high-confidence repair and diagnostics rather than replace HTML logic.

### Implementation

- Add optional PDF-aware diagnostics for debug/audit runs when `00.source.pdf`
  is present beside `01.en.raw.html`.
- Use PDF text layer as a fallback signal for:
  - fragmented captions and BioRender credits;
  - bibliography continuation items across page breaks;
  - end-of-article section order;
  - suspicious OCR substitutions near citations.
- Keep repairs confidence-scored:
  - high-confidence: same page/neighboring block, matching figure/ref number,
    clear continuation marker;
  - low-confidence: emit audit warning and preserve visible HTML.

### Tests

- Unit tests should cover fallback decision logic with synthetic text-layer
  strings, not require heavyweight PDF extraction in the normal test suite.
- Integration/debug tests may run on the seven local PDFs when available.

### Acceptance

- PDF fallback improves suspicious cases when available.
- The pipeline remains deterministic and useful without local PDFs.

## Workstream 7: Audit Expansion

### Add Checks

- Missing local image files for polish/review HTML.
- Figure/table wrapper conformance:
  - target ID must be on wrapper;
  - no target ID on caption-only paragraph unless it is a deliberate warning
    wrapper;
  - one wrapper per figure/table number.
- Reference identity:
  - `ref-N` visible number mismatch;
  - duplicate visible reference numbers;
  - gaps caused by continuation items;
  - incoming links to `#page-*` anchors inside bibliography entries.
- Citation preservation:
  - author-year citations that still point to page anchors;
  - citation-looking math superscripts;
  - unlinked citation ranges/lists when references exist.
- Unit normalization:
  - split unit/math fragments;
  - unit exponents linked as refs;
  - glued unit/prose boundaries.
- Reading-order risks:
  - incomplete paragraph before figure/table plus lowercase continuation after;
  - references heading inside funding/supplementary text;
  - table notes detached from nearby table.

### Acceptance

- The audit reports the old round-2 symptom classes before fixes.
- After fixes and regeneration, the audit has no high-severity defects for the
  seven reviewed articles.

## Article Coverage Matrix

| Article | Main remaining symptom classes | Covered by workstreams |
|---|---|---|
| Ahmed | full-page Figure 8 assembly, BioRender caption continuation, reference ID drift from split entries | 2, 3, 6, 7 |
| Kaiju | reference target/highlight, equation-defined `j` indices, two-column end-section order | 2, 3, 4, 5, 6, 7 |
| Li | figure-interrupted sentence, footnote marker/block, lost author-year links, reference highlight | 2, 3, 5, 7 |
| Merken | table/caption units, chemical subscripts, inline dimensions, duplicate reference prefixes | 3, 4, 7 |
| Schelles | unit spacing, compact measurements, terminal punctuation after formulas | 4, 7 |
| Wang | table interrupting sentence, table title/note association | 2, 5, 7 |
| Teo | false numeric links, OCR citation damage, citations as math, page/table continuation, table notes | 3, 4, 5, 6, 7 |
| All | broken review images, float visual frame, consistent figure/table link behavior, unit consistency | 1, 2, 4, 7 |

## Implementation Order

1. Baseline and fixtures
   - Add or update tests that reproduce the generalized classes above.
   - Run current tests to prove the fixtures fail for the right reasons.

2. Review packaging and missing-image audit
   - This is the fastest user-visible fix and removes ambiguity from manual
     review.

3. Float wrappers, visual frame, and navigation targets
   - Unify figure/table behavior before deeper reading-order repairs, because
     later passes should operate on stable float units.

4. Bibliography normalization and citation retargeting
   - Fix reference identity before adding more citation forms; otherwise links
     can become confidently wrong.

5. Unit/math normalization
   - Normalize simple measurements, protect unit exponents, split prose-bearing
     math, and add guarded variable/chemical repairs.

6. Reading-order and footnote repair
   - Use the stable float wrappers and normalized reference section to repair
     sentence splits, table notes, end sections, and footnotes.

7. Optional PDF fallback diagnostics
   - Add high-confidence PDF text-layer support where HTML alone cannot decide.

8. Regenerate and compare
   - Regenerate all seven `02.en.polish.html` files.
   - Run `scripts/audit_en_polish.py --roots md_output/new`.
   - Build a new self-contained review folder.
   - Manually verify the old symptom list against the regenerated output.

## Final Acceptance Criteria

- All seven reviewed articles regenerate without the round-2 high-severity
  symptoms.
- Review HTML copies display figures without missing sidecar assets.
- Figure/table links always target and highlight a whole wrapper.
- Bibliography IDs match visible bibliography numbers.
- Numeric, author-year, bracketed, and superscript citation links remain
  clickable where references exist.
- Front matter, footnotes, model versions, dimensions, and unit exponents are
  not mislinked as references.
- Simple scientific measurements render consistently in body text, captions,
  and tables.
- Floats do not split sentence reading order.
- Remaining low-confidence defects are visible audit warnings, not silent
  failures.
