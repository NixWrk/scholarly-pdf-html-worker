# Meine EN Polish Manual Review 2026-04-30

## Scope

This document is the working log for manual review of the detected-English
subset of the Meine full-library EN polish run.

The review target is:

`manual_review_meine_en_polish_inlined_2026-04-30`

The source pipeline output is:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop`

Only documents classified as `en` by the source-language audit are in scope for
EN polish defect analysis. Non-English, mixed, and unknown-language files are
language-gate cases, not EN-polish repair evidence.

## Source Artifacts

Review bundle:

`manual_review_meine_en_polish_inlined_2026-04-30`

Review index:

`manual_review_meine_en_polish_inlined_2026-04-30/index.json`

Manual notes scaffold:

`manual_review_meine_en_polish_inlined_2026-04-30/review_notes.md`

Language audit:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/_quality_audit/source_language_audit_2026-04-29.json`

Raw-stage audit:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/_quality_audit/en_raw_audit_2026-04-29.json`

Raw/polish pair audit:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/_quality_audit/en_polish_pair_audit_2026-04-29.json`

Per-article stages:

- `.../<alias>/_z2m_stages/01.en.raw.html`
- `.../<alias>/_z2m_stages/02.en.polish.html`
- source PDF path from the language audit / review index

## Current Review Set

The flat review bundle contains 82 HTML files:

- `001_meine_0001_3944c69948.html`
- ...
- one file per detected-English article

Each review item is mapped back to the source PDF, raw HTML, and polish HTML in
`index.json` and `index.csv`.

## Working Rule

Do not fix isolated article symptoms immediately unless the defect blocks manual
review or is a severe deterministic regression introduced by polish.

For normal cases:

1. Capture the user report for one article.
2. Verify against PDF, raw HTML, and polish HTML.
3. Classify the symptom.
4. Record required regression coverage.
5. Move to the next article.
6. Consolidate recurring symptoms into universal repair candidates after a
   small batch.

Production fixes must be structural and general. Do not use article names,
titles, author names, or one-off text snippets as production conditions.

## Per-Article Loop

For each article:

1. User sends manual notes from HTML/PDF comparison.
2. Codex resolves the review file through `index.json`.
3. Codex checks:
   - review HTML;
   - `02.en.polish.html`;
   - `01.en.raw.html`;
   - source PDF when needed;
   - current polish/raw extraction code when needed.
4. Codex records:
   - where the symptom appears;
   - what the expected output should be;
   - whether raw already had the defect or polish introduced it;
   - which layer likely owns the fix;
   - whether the issue is article-specific or a general defect class;
   - what regression coverage is needed.
5. Codex appends the finding to this document.
6. Move to the next article only after the current article's notes are captured.

## Classification Statuses

Every symptom receives exactly one primary status:

| Status | Meaning |
| --- | --- |
| `fixed_by_polish` | Raw was defective; polish repaired it completely. |
| `partially_fixed_by_polish` | Polish improved the raw defect but visible residue remains. |
| `not_fixed_by_polish` | Raw was defective and polish left the defect essentially intact. |
| `introduced_by_polish` | Raw was acceptable, but polish created a new defect. |
| `revealed_by_polish_audit` | Raw audit did not detect the precursor, but PDF/raw inspection shows the root existed before polish. |
| `raw_marker_only` | Raw is defective, but fixing it safely needs Marker/PDF-aware extraction rather than EN polish heuristics. |
| `audit_false_positive` | Automated audit warning is not a visible defect after manual/PDF check. |
| `needs_pdf_diagnostics` | PDF evidence is required before a universal repair can be trusted. |

## Review Priorities

Highest priority:

1. Problems introduced by polish.
2. Problems polish did not solve.
3. Problems polish only partially solved.
4. Audit false positives or blind spots.
5. Raw-marker-only defects that need PDF-aware extraction.

Recurring problem families to watch:

- front matter and author/affiliation markers;
- citation ranges and citation lists;
- false citation links in units, exponents, dates, labels, and table values;
- bibliography identity and duplicate visible reference numbers;
- figure/table wrapper integrity;
- figure/table runs with no body text between them;
- caption/table title placement;
- page-break reading order damage;
- unit/math spacing and exponent normalization;
- prose accidentally absorbed into formulas;
- body paragraphs incorrectly marked as front matter.

## Article Worksheet Template

Use this template for every reviewed article.

```markdown
## <review file> - <alias>

Source PDF:
Raw stage:
Polish stage:
Language detection:

### Manual Notes From User

- ...

### Automated Signals

Raw audit:
Polish pair audit:

### PDF Ground Truth Notes

- ...

### Raw HTML Notes

- ...

### Polish HTML Notes

- ...

### Defect Classification

| ID | Location | Symptom | Expected | Raw status | Polish status | Classification | Fix candidate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M001 | ... | ... | ... | ... | ... | ... | ... |

### Polish Did Not Solve

- ...

### Polish Created

- ...

### Regression Coverage Needed

- ...

### Verdict

- `fixed_by_polish`:
- `partially_fixed_by_polish`:
- `not_fixed_by_polish`:
- `introduced_by_polish`:
- `audit_false_positive`:
- `raw_marker_only`:
- next action:
```

## Batch Summary Template

After every 5-10 reviewed articles, append a batch summary.

```markdown
## Batch Summary <N>

Articles reviewed:

### Confirmed Not Solved By Polish

| Pattern | Articles | Proposed universal fix | Risk |
| --- | --- | --- | --- |

### Confirmed Introduced By Polish

| Pattern | Articles | Suspected pass | Guard/fix |
| --- | --- | --- | --- |

### Audit False Positives

| Check | Articles | How to tune |
| --- | --- | --- |

### Regression Fixtures To Add

- ...

### Implementation Candidates

1. ...
2. ...
3. ...
```

## Rules For Promoting A Fix

Promote a pattern to implementation only when all are true:

1. At least two articles show the same real pattern, or one article shows a
   severe deterministic regression introduced by polish.
2. The fix can be expressed with local HTML structure or reliable PDF
   diagnostics.
3. The fix has a no-op path for clean controls.
4. A focused regression fixture can be written before or with the code change.
5. The original seven-article EN-polish review corpus remains stable.

Do not promote a pattern when:

- the evidence requires visual judgment unavailable to the pipeline;
- the rule depends on one journal/layout only;
- the fix would rewrite arbitrary prose without strong structural guards;
- the audit check is likely a false positive and needs tuning first.

## Implementation Loop

After a defect class is promoted:

1. Add or update focused regression tests.
2. Implement a general fix.
3. Regenerate affected EN polish files.
4. Run focused tests.
5. Run pair-audit checks.
6. Spot-check clean controls and the original seven-article corpus.
7. Update this document with status and evidence.

## Active Findings

New article findings will be appended below.

## Global Requests From User

### G001 - Box Floats Need Visual Framing

User request:

- Boxes should also be visually separated by horizontal lines above and below.

Current interpretation:

- Treat `BOX N` blocks as float units, not ordinary headings/prose.
- A box unit should be framed similarly to figure/table float runs.
- Box references such as `(Box 1)` should have a stable target when the box is
  present.

General fix candidate:

- Add a box-unit assembler before continuation repair.
- Detect `BOX N` / `Box N` headings plus title and body paragraphs.
- Assign wrapper IDs like `box-1`.
- Link textual references such as `(Box 1)` to the wrapper.
- Add CSS/top-bottom framing for `z2m-box-unit`, or include boxes in the shared
  float-run framing model where appropriate.

Regression coverage needed:

- A Nature-style `BOX 1` heading followed by a title and two-column body must be
  wrapped as one unit.
- A body reference `(Box 1)` must link to `#box-1`.
- The first box paragraph must not be merged into neighboring body prose.
- Box framing must not change normal section headings.

### G002 - Citation Strategy Must Be Chosen Per Article From PDF Evidence

User request:

- Literature-link restoration can use several strategies, but the strategy must
  be selected after analyzing the PDF text and counting which citation shape is
  dominant: numeric superscripts, square-bracket citations, or another style.

Current interpretation:

- Citation linkification should not be a single global heuristic.
- Before restoring citations, the pipeline should inspect the article as a
  whole, including PDF text and the reference section, and set a per-article
  `citation_style` diagnosis.
- The citation strategy must be consistent with the reference-list identity
  found in the same article.
- Non-citation superscripts, units, equations, affiliations, table footnotes,
  statistical notation, and author markers must be protected before citation
  linkification.

General fix candidate:

- Add a citation-style detector that scans the PDF text beyond the first page
  and records counts for:
  - square-bracket numeric citations, such as `[1]`, `[3-7]`, `[10, 12]`;
  - superscript numeric citations near prose punctuation;
  - author-year references;
  - numbered reference-list entries;
  - equation labels and unit/math superscripts that should be excluded.
- Use the dominant compatible pair of in-text citation style plus reference-list
  style to select the linker.
- When mixed styles exist, link only high-confidence cases and leave the rest
  plain with an audit warning.
- Write citation-style evidence into the article diagnostics so false positives
  can be reviewed.

Regression coverage needed:

- A bracket-citation article with `[1]` and `[3-7]` should use bracket linking
  and must not link `χ2`, units, or author affiliations.
- A superscript-citation article should link only superscripts in body prose and
  must not link front-matter affiliations or math exponents.
- An article with no reliable reference-list identity should not force
  reference links from ambiguous numeric tokens.
- The audit should flag a mismatch between detected reference-list style and
  generated in-text links.

### G003 - HTML Width Should Respect The Widest Table

User request:

- Render the HTML using a document width based on the widest table.

Current interpretation:

- The readable HTML container should not force very wide tables into a fixed
  narrow content width.
- Very wide tables should either expand the document's usable width or be placed
  in a table wrapper with predictable horizontal scrolling.
- The choice should preserve readable prose width where possible, but must not
  let table cells overflow or make the table unusable.

General fix candidate:

- During polish, compute table complexity signals such as maximum column count,
  long unbreakable cell tokens, and estimated intrinsic table width.
- Emit a CSS custom property or class for wide-table documents/individual table
  units.
- For the document view, allow the main container to expand up to the widest
  table within viewport constraints.
- For extreme tables, wrap the table in a `z2m-table-scroll` container with
  stable overflow behavior.

Regression coverage needed:

- A 16-20 column table should remain fully inspectable without leaking outside
  the document container.
- Normal narrow tables should keep the standard prose width.
- Wide-table handling must not change semantic table content or reference/table
  anchors.

## 001_meine_0001_3944c69948.html - meine_0001_3944c69948

Source PDF:

`C:\PC\Zotero\Zotero_NIX_Data\storage\25HA92IT\Lüscher и др. - 2025 - Roadmap for direct and indirect translation of optogenetics into discoveries and therapies for human.pdf`

Raw stage:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/meine_0001_3944c69948/_z2m_stages/01.en.raw.html`

Polish stage:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/meine_0001_3944c69948/_z2m_stages/02.en.polish.html`

Review HTML:

`manual_review_meine_en_polish_inlined_2026-04-30/001_meine_0001_3944c69948.html`

Language detection:

- `en`, confidence `0.99`.

### Manual Notes From User

- General: boxes should be separated by horizontal lines above and below.
- The paragraph split around `(with >10,000 papers already reporting on
  discoveries made with optogenetics)` is broken.
- Text citations became formula/exponent text: `memory \(^4\)`,
  `decision-making \(^5\)`, `heart-to-brain communication \(^6\)`.
- Figure captions for Figure 1, Figure 2, and similar figures have broken text
  flow; PDF comparison recommended.
- Superscript citations in body text became ordinary inline text and sometimes
  absorbed the final letter of the preceding word: `functio n13 ,14`,
  `consideration s20, 23`, `brains 14, 17 - 19`.
- The `(Box 1)` reference is not linked.

### Automated Signals

Raw audit:

- `R08`: glued roman/table footnote suffixes, count `4`.
- `R11`: broken hyphenated line joins, count `7`.

Polish pair audit:

- No defects reported.

Audit verdict:

- The current pair audit missed visible defects in citation superscripts, box
  assembly/linking, caption-continuation assembly, and a severe box/body
  continuation merge.

### PDF Ground Truth Notes

- Page 1 shows the `>10,000 papers...` text as a continuation of the preceding
  paragraph, not as a new paragraph.
- Page 1 shows `memory4`, `decision-making5`, `heart-to-brain communication6`,
  and `approach7` as citation superscripts.
- Page 2 shows `(Box 1)` as a textual box reference in the body.
- Page 2 shows `function13,14`, `brains14,17-19`, and `considerations20,23` as
  normal words followed by citation superscripts.
- Page 2 shows Figure 1 caption text as a figure caption split across columns;
  the caption continuation is not ordinary body prose.
- Page 3 shows a visually framed `BOX 1` block with title `Indirect
  translation: examples inspired by optogenetic circuit analysis`.
- Page 5 shows Figure 2 caption text split across the figure caption area; the
  continuation beginning `surface) in retinal ganglion cells...` belongs to the
  caption, not body prose.

### Raw HTML Notes

- Raw already splits the `>10,000 papers...` continuation into a separate
  paragraph.
- Raw preserves some early superscript citations as plain caret text:
  `memory ^4`, `decision-making ^5`, `heart-to-brain communication ^6`,
  `approach ^7`.
- Raw contains `functio n13 ,14`, `consideration s20, 23`, and
  `brains 14, 17 - 19`, so the word/citation boundary is already damaged before
  polish.
- Raw has a visible `BOX 1` heading and the box title as separate blocks, but no
  stable `box-1` target.
- Raw keeps the first Box 1 body paragraph separate from the surrounding body
  text.
- Raw has Figure 1 and Figure 2 captions split across multiple adjacent
  paragraphs; it does not provide a complete figure wrapper.

### Polish HTML Notes

- Polish leaves the `>10,000 papers...` text as a separate paragraph.
- Polish converts raw caret citations into TeX-like inline math text:
  `\(^4\)`, `\(^5\)`, `\(^6\)`, `\(^7\)` instead of bibliography links.
- Polish leaves `functio n13 ,14`, `consideration s20, 23`, and
  `brains 14, 17 - 19` as visible damaged text rather than repairing the word
  boundary and citation links.
- Polish creates `fig-1` and `fig-2` wrappers, but the caption continuation
  paragraphs remain outside the wrappers.
- Polish has no `#box-1` target and no link from `(Box 1)` to a box wrapper.
- Polish introduces a severe box/body merge: the first Box 1 body paragraph is
  merged into the preceding body paragraph after `For these`, while `BOX 1` and
  the box title remain after that merged paragraph.

### Defect Classification

| ID | Location | Symptom | Expected | Raw status | Polish status | Classification | Fix candidate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M001-001 | Opening body, page 1 | `>10,000 papers...` starts a separate paragraph | Join with preceding paragraph after `(with` | Split in raw | Still split | `not_fixed_by_polish` | Continuation repair should handle paragraph starts beginning with comparative/math punctuation when previous paragraph ends with an open parenthetical. |
| M001-002 | Opening body, page 1 | `memory \(^4\)`, `decision-making \(^5\)`, `heart-to-brain communication \(^6\)` | Citation superscripts linked to refs 4, 5, 6 | Raw caret citations are recognizable but unlinked | Converted to TeX-like math text | `introduced_by_polish` | Citation tokenizer should protect `^N` citation forms before math normalization and link them when reference targets exist. |
| M001-003 | Figure 1 and Figure 2 | Caption continuation paragraphs remain outside `fig-1`/`fig-2` wrappers | Each figure wrapper owns image plus full caption continuation | Raw caption fragments are split | Wrapper added but incomplete | `partially_fixed_by_polish` | Float assembler should absorb local caption continuations until a body boundary/heading is reached. |
| M001-004 | Body text near Figure 1 / page 2 | `functio n13 ,14`, `consideration s20, 23`, `brains 14, 17 - 19` | Whole word plus linked citation superscripts/ranges | Word/citation boundary damaged in raw | Still damaged and unlinked | `not_fixed_by_polish` | Add cautious word-final-letter plus citation-number repair for lowercase-letter gap before valid citation ranges/lists. |
| M001-005 | `(Box 1)` references | Box references are plain text | Link `(Box 1)` to a stable `#box-1` wrapper | Box heading exists but no target | Still no target/link | `not_fixed_by_polish` | Add box-unit wrapper/ID model and box-reference linker. |
| M001-006 | Box 1 block, page 3 | First Box 1 body paragraph is merged into preceding body paragraph | Box content remains inside framed Box 1 unit | Raw keeps box paragraph separate | Polish merges it into body prose | `introduced_by_polish` | Assemble/protect box units before continuation repair; forbid paragraph continuation across `BOX N` boundaries. |
| M001-007 | Box 1 visual rendering | Box is not framed with top/bottom horizontal lines | Box has visual separation comparable to PDF and figure/table float runs | Raw has plain headings | Polish has plain headings/no wrapper | `not_fixed_by_polish` | Shared float framing should include `z2m-box-unit`. |

### Polish Did Not Solve

- It did not repair the paragraph continuation after `(with`.
- It did not repair raw word/citation splits such as `functio n13 ,14`.
- It did not assemble complete figure caption continuations.
- It did not create a Box 1 target or link `(Box 1)`.
- It did not frame the box as a float-like unit.

### Polish Created

- It converted raw caret citation superscripts into TeX-like formula text.
- It merged the first Box 1 paragraph into ordinary body prose, crossing the
  `BOX 1` boundary.

### Regression Coverage Needed

- Citation fixture: `memory ^4, decision-making ^5 and heart-to-brain
  communication ^6` should become linked citation superscripts, not `\(^4\)`.
- Continuation fixture: paragraph ending `(with` followed by a paragraph
  beginning `>10,000...` should be joined.
- Figure fixture: a caption split into several adjacent paragraphs should be
  owned by one `z2m-figure-unit`.
- Box fixture: `BOX 1` + title + body paragraphs should become one
  `z2m-box-unit#box-1`.
- Box boundary fixture: continuation repair must not merge body text across a
  `BOX N` heading or move the first box paragraph into body prose.
- Link fixture: `(Box 1)` should link to `#box-1`.
- Audit fixture: pair audit should flag unlinked `\(^N\)` citation remnants,
  missing box targets for existing `BOX N`, and box/body continuation merges.

### Verdict

- `fixed_by_polish`: none from the user-reported symptoms.
- `partially_fixed_by_polish`: figure wrappers exist, but caption assembly is
  incomplete.
- `not_fixed_by_polish`: opening paragraph continuation, word/citation splits,
  Box 1 link/target/framing.
- `introduced_by_polish`: caret citations converted to TeX-like math; first Box
  1 paragraph merged into body prose.
- `audit_false_positive`: none.
- `raw_marker_only`: none confirmed yet; all current symptoms appear repairable
  or at least warnable from HTML structure plus optional PDF diagnostics.
- next action: continue collecting article-level evidence. Promote box-unit
  assembly and caret-citation protection if the same patterns recur, or promote
  sooner if Box 1 merge is treated as a severe deterministic polish regression.

## 002_meine_0003_b9eaf6e854.html - meine_0003_b9eaf6e854

Source PDF:

`C:\PC\Zotero\Zotero_NIX_Data\storage\2TLCQAPQ\Mukhiddinov и Kim - 2021 - A Systematic Literature Review on the Automatic Creation of Tactile Graphics for the Blind and Visua.pdf`

Raw stage:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/meine_0003_b9eaf6e854/_z2m_stages/01.en.raw.html`

Polish stage:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/meine_0003_b9eaf6e854/_z2m_stages/02.en.polish.html`

Review HTML:

`manual_review_meine_en_polish_inlined_2026-04-30/002_meine_0003_b9eaf6e854.html`

Language detection:

- `en`, confidence `0.99`.

### Manual Notes From User

- Repeated page top/bottom insertions leak into text:
  `Processes 2021, 9, 1726` and
  `Processes 2021, 9, 1726. https://doi.org/10.3390/pr9101726`.
- These insertions break page-continuation text:
  `this role may be ... Processes 2021 , 9 , 1726 5 of 31 performed by friends,
  parents, or teachers`.
- URL is broken: `https://arxi v.org/`.
- A non-citation number became a bibliography link:
  `the United States had the most papers, with 52.`

### Automated Signals

Raw audit:

- `R11`: broken hyphenated line joins, count `3`.

Polish pair audit:

- `P01`: suspicious raw front-matter marker OCR in the license/copyright block.

Audit verdict:

- The user-reported page-furniture leak, broken page-continuation merge,
  broken URL link, and false citation link were not reported by the current
  pair audit.

### PDF Ground Truth Notes

- The PDF visually shows `Processes 2021, 9, 1726` as a repeated page header,
  with page numbers such as `5 of 31` on the opposite side of the header line.
  These are page furniture, not article prose.
- The body sentence crosses the page boundary: page 4 ends with
  `this role may be`, and page 5 begins with `performed by friends, parents, or
  teachers...`. The page header between them must be ignored for body text.
- Page 7 Table 1 displays the arXiv URL as one intact URL:
  `https://arxiv.org/`.
- Page 9 body prose says `the United States had the most papers, with 52.`;
  `52` is a plain count and not a reference citation.

### Raw HTML Notes

- Raw contains 31 `Processes 2021...` hits, mostly as standalone paragraphs such
  as `Processes 2021 , 9 , 1726 5 of 31`.
- Raw keeps the page-break body text separated:
  one paragraph ends `this role may be`, the repeated header appears as its own
  paragraph, and the next body paragraph begins `performed by friends...`.
- Raw preserves the arXiv table URL as plain intact text:
  `<td>https://arxiv.org/</td>`.
- Raw leaves `52` in `with 52.` as plain text, not a citation link.

### Polish HTML Notes

- Polish still contains 31 `Processes 2021...` hits.
- Several repeated header/footer strings are now merged into body paragraphs,
  for example:
  `Processes 2021 , 9 , 1726 5 of 31 performed by friends...`.
- The page-continuation body sentence is not repaired:
  `this role may be` remains separated from `performed by friends...`.
- Polish breaks the arXiv URL in Table 1:
  `<a href="https://arxi">https://arxi</a> v.org/`.
- Polish incorrectly links the plain count `52` to `#ref-52` in
  `the United States had the most papers, with 52.`

### Defect Classification

| ID | Location | Symptom | Expected | Raw status | Polish status | Classification | Fix candidate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M002-001 | Whole article page boundaries | Repeated `Processes 2021 , 9 , 1726 N of 31` appears in body HTML | Repeated page headers/footers removed or quarantined as page furniture | Present in raw as standalone page-furniture paragraphs | Still present | `not_fixed_by_polish` | Add repeated page-furniture detector for journal/year/volume/article/page-count patterns. |
| M002-002 | Page 4/5 continuation | `this role may be` is separated from `performed by friends...` by page furniture | Join body continuation while dropping header/page number | Raw split by standalone page header | Polish keeps split and merges header into next paragraph | `partially_fixed_by_polish` / `introduced_by_polish` | Continuation repair should skip page furniture and never merge page furniture into body. |
| M002-003 | Table 1 arXiv URL | `https://arxi v.org/` with link only to `https://arxi` | Link full `https://arxiv.org/` | Raw URL intact as plain text | Polish breaks and partially links it | `introduced_by_polish` | URL linker should normalize safe intra-URL spaces before linkification and validate full URL token boundaries. |
| M002-004 | Review Results prose, page 9 | Plain count `52` links to `#ref-52` | Keep `52` as plain text | Raw plain count | Polish links it as citation | `introduced_by_polish` | Citation linker needs stronger guard against bare numeric counts in prose, especially after `with`/`,` and before period. |

### Polish Did Not Solve

- It did not remove repeated page headers/page numbers.
- It did not repair the page-break continuation around `this role may be` /
  `performed by friends...`.

### Polish Created

- It merged repeated page furniture into ordinary body paragraphs.
- It broke the intact raw arXiv URL and linked only the partial prefix.
- It created a false citation link from the plain count `52`.

### Regression Coverage Needed

- Page-furniture fixture:
  `Processes 2021 , 9 , 1726 5 of 31` repeated across pages should be removed
  or quarantined before body continuation repair.
- Page-continuation fixture:
  `this role may be` + page header + `performed by friends...` should become a
  continuous body sentence without the header text.
- URL fixture:
  `https://arxiv.org/` in a table cell must remain a single full external link.
- Broken-URL repair fixture:
  `https://arxi v.org/` should either be repaired to `https://arxiv.org/` or
  left unlinked with an audit warning, never linked as `https://arxi`.
- False-citation fixture:
  `with 52.` must not link to `#ref-52`.
- Audit fixture:
  pair audit should flag repeated page furniture in polish, partial URL links
  that stop before a URL-like suffix, and likely false bare-number ref links.

### Verdict

- `fixed_by_polish`: none from the user-reported symptoms.
- `partially_fixed_by_polish`: page continuation is partially processed but
  remains visibly broken.
- `not_fixed_by_polish`: repeated page furniture remains in the output.
- `introduced_by_polish`: page furniture merged into body, arXiv URL broken,
  plain count `52` linked as a citation.
- `audit_false_positive`: none.
- `raw_marker_only`: page furniture originates in raw extraction, but the
  repeated pattern appears repairable from HTML-only corpus context.
- next action: continue collecting article-level evidence. Promote repeated
  page-furniture removal and false-bare-number citation guards if they recur;
  URL partial-link protection is already a strong candidate because it is a
  deterministic polish regression from intact raw text.

## 003_meine_0004_a4cb70ccef.html - meine_0004_a4cb70ccef

Source PDF:

`C:\PC\Zotero\Zotero_NIX_Data\storage\2W82D3CT\Wheeler и др. - 2012 - The Shape of the Urine Stream — From Biophysics to Diagnostics.pdf`

Raw stage:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/meine_0004_a4cb70ccef/_z2m_stages/01.en.raw.html`

Polish stage:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/meine_0004_a4cb70ccef/_z2m_stages/02.en.polish.html`

Review HTML:

`manual_review_meine_en_polish_inlined_2026-04-30/003_meine_0004_a4cb70ccef.html`

Language detection:

- `en`, confidence `0.99`.

### Manual Notes From User

- A non-reference marker became a link:
  `Andrew P. S. Wheeler1*,`.
- Missing links where links should exist:
  `Equation 8.`
- A unit/formula exponent was recognized as a reference link:
  `flow rates of 5 to 50 mL:s{ 1 .`

### Automated Signals

Raw audit:

- No raw defects reported.

Polish pair audit:

- `P01`: suspicious raw front-matter marker OCR in the copyright/license block.

Audit verdict:

- The current pair audit missed the actual user-reported defects: affiliation
  markers linked as references, missing equation-reference links, and false
  reference links in unit exponents.

### PDF Ground Truth Notes

- Page 1 shows author affiliation markers in the title line:
  `Andrew P. S. Wheeler1*`, `Samir Morad2`, `Noor Buchholz3`,
  `Martin M. Knight2`. These are affiliations/corresponding-author markers, not
  bibliography references.
- Page 3 shows prose references to numbered equations:
  `the wavelength is given by Equation 8`, followed by equation `(8)`, and then
  `Equation 8 follows from Equation 7... as in Equation 9`.
- Page 6 shows unit exponents in flow-rate notation, including
  `5 to 50 mL.s^-1` visually in the methods section. The extracted PDF text
  represents the same shape as `mL:s{1`.

### Raw HTML Notes

- Raw author line contains escaped author superscript markup inside an `h1`:
  `Andrew P. S. Wheeler&lt;sup&gt;1*&lt;/sup&gt;, ...`.
- Raw has no bibliography links in the author line.
- Raw contains equation references as plain text:
  `Equation 8`, `Equation 7`, `Equation 9`.
- Raw contains equation display blocks with TeX tags, for example
  `L = V/f \tag{8}` and `L = Q/Af \tag{9}`.
- Raw has no equation IDs or equation-reference links.
- Raw represents several unit exponents as `mL:s{ <sup>1</sup>` or
  `mLs{ <sup>1</sup> mm{ <sup>1</sup>`, but these superscripts are plain text
  and are not linked to bibliography references.

### Polish HTML Notes

- Polish unescapes the author superscripts and then links the affiliation
  numbers to bibliography references:
  `1 -> #ref-1`, `2 -> #ref-2`, `3 -> #ref-3`.
- Polish creates equation rows such as
  `<div class="z2m-equation-row"> ... <span class="z2m-eq-num">(8)</span>`,
  but does not assign an equation ID and does not link textual references such
  as `Equation 8`.
- Polish links unit exponent `1` in `mL:s{ 1` and related unit expressions to
  `#ref-1`.

### Defect Classification

| ID | Location | Symptom | Expected | Raw status | Polish status | Classification | Fix candidate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M003-001 | Author/title line, page 1 | Affiliation markers in `Andrew P. S. Wheeler1*` become bibliography links | Keep author affiliation markers as plain superscripts/front-matter markers | Raw has escaped affiliation superscripts and no ref links | Polish links them to refs 1/2/3 | `introduced_by_polish` | Front-matter classifier/protected zone must run before citation linkification; no `#ref-*` links inside title/author/affiliation blocks. |
| M003-002 | Equation references, page 3 | `Equation 8`, `Equation 7`, `Equation 9` are plain text | Link equation references to corresponding equation rows | Raw has equation refs and `\tag{8}`/`\tag{9}` but no IDs | Polish creates equation rows but no IDs/links | `not_fixed_by_polish` | Equation-row assembler should assign stable IDs such as `eq-8`; equation-reference linker should target them. |
| M003-003 | Unit/exponent text in Results and Materials | `mL:s{ <sup>1</sup>` exponent `1` links to `#ref-1` | Unit exponent remains protected/plain, ideally normalized to `mL s^-1` | Raw unit exponent is malformed but unlinked | Polish links exponent as a citation | `introduced_by_polish` | Citation linker needs unit/exponent protected zones before reference linking. |
| M003-004 | Unit normalization | `mL:s{ 1`, `mLs{ 1 mm{ 1`, `w10mL:s{ 1` remain visibly malformed | Normalize or at least preserve readable scientific unit grammar without false links | Raw malformed | Polish still malformed | `not_fixed_by_polish` | Scientific text normalizer should repair known `s{1`/`mm{1` exponent forms with tight unit grammar guards. |

### Polish Did Not Solve

- It did not create stable equation targets or links for `Equation 8`,
  `Equation 7`, and `Equation 9`.
- It did not normalize malformed flow-rate unit exponents.

### Polish Created

- It linked front-matter affiliation markers to bibliography references.
- It linked scientific unit exponents to bibliography reference `1`.

### Regression Coverage Needed

- Front-matter fixture:
  `Author Name<sup>1*</sup>, Other Author<sup>2</sup>` in a title/author block
  must not produce `#ref-1` or `#ref-2` links.
- Equation fixture:
  `Equation 8` plus a display block with `\tag{8}` should produce a stable
  equation target and an internal equation link.
- Unit-exponent fixture:
  `mL:s{ <sup>1</sup>` and `mLs{ <sup>1</sup> mm{ <sup>1</sup>` must not link
  exponent `1` to `#ref-1`.
- Unit-normalization fixture:
  Known unit forms such as `mL:s{1`, `mL/s`, and `mL s^-1` should remain
  readable and citation-safe.
- Audit fixture:
  pair audit should flag `#ref-*` links in author/front-matter blocks and
  `#ref-1` links immediately following unit/exponent punctuation.

### Verdict

- `fixed_by_polish`: none from the user-reported symptoms.
- `partially_fixed_by_polish`: equation rows were created, but equation linking
  is missing.
- `not_fixed_by_polish`: equation references and malformed unit grammar.
- `introduced_by_polish`: author affiliation markers linked as refs; unit
  exponents linked as refs.
- `audit_false_positive`: the reported `P01` does not cover the visible user
  symptoms.
- `raw_marker_only`: none confirmed; the current issues are protectable or
  repairable from HTML structure.
- next action: continue collecting article-level evidence. The front-matter
  protected-zone and unit-exponent citation guards now recur across articles and
  are becoming strong universal repair candidates.

### Implementation Status - 2026-04-30

Implemented and verified for `meine_0004_a4cb70ccef`:

- M003-001 fixed: author-heading affiliation superscripts are marked as
  front-matter and are not linked to `#ref-*`.
- M003-002 fixed: equation rows have stable `eq-N` IDs and textual references
  such as `Equation 8` link to them.
- M003-003 fixed: `mL:s{ <sup>1</sup>` and already-linked variants normalize
  to `mL s<sup class="z2m-unit-exp">-1</sup>` before citation linking.
- M003-004 partly fixed: observed `mL:s{1`, `20{25 mL:s{1`, and `w10mL:s{1`
  cases now render as readable, citation-safe `mL s^-1` forms.
- Additional audit-driven fix: Figure 4's two adjacent image blocks and its
  single caption are wrapped inside one `z2m-figure-unit`.

Regression coverage added in `tests/test_single_file_html.py`:

- author affiliation superscripts in `h1` front matter;
- `mL:s{1` / linked unit-exponent repair, including compact `w10mL`;
- multi-image single-caption figure wrapping.

Verification:

- `python -m pytest tests\test_single_file_html.py tests\test_audit_en_polish.py -q`
  -> `221 passed`.
- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0004_a4cb70ccef --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_003_after_003_fixes_2026-04-30.json`
  -> `articles=1 changed=1 inlined_images=10 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0004_a4cb70ccef --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_003_after_003_fixes_2026-04-30.json`
  -> `defects=0`, `page_links=0`, `missing_img=0`.

## 004_meine_0011_33cd7b163e.html - meine_0011_33cd7b163e

Source PDF:
`C:\PC\Zotero\Zotero_NIX_Data\storage\54LFWS3H\Baas - A machine learning approach to the automatic classification of female uroflowmetry measurements.pdf`

Review HTML:
`manual_review_meine_en_polish_inlined_2026-04-30\004_meine_0011_33cd7b163e.html`

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0011_33cd7b163e\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0011_33cd7b163e\_z2m_stages\02.en.polish.html`

### Manual Notes From User

1. Lost bibliography links:
   `annealing [11].` and `point must lie [1]`.
2. `QMAx` is recognized as a Roman/superscript marker even though it is not one.
3. The heading link/highlight does not cover the complete heading:
   `Appendix B More information about the machine learning classifiers and their construction`.
4. Figure/image order is broken. Figures 15 and 16 appear first as images and
   then as captions. The same pattern occurs for Figures 18 and 19.

### Automated Signals

- Raw audit:
  - `R11`: broken hyphenated/continuation joins, count 10.
- Polish pair audit:
  - `P04`: unlinked citation range/list remains in polish.
  - `P14`: figure link target caption paragraph not whole figure block.
- Pair-audit counters:
  - `polish_ref_links: 0`
  - `polish_fig_links: 32`
  - `polish_table_links: 11`
  - `polish_fig_ids: 19`
  - `polish_table_ids: 4`

Audit verdict:

- `P04` is directionally related to the lost `[N]` citations, but it does not
  state the larger failure: this article has bracketed references and bracketed
  in-text citations, while polish creates zero bibliography reference IDs.
- `P14` is directionally related to figure target quality, but it does not catch
  the more severe image/caption pairing failure for side-by-side figures.
- The audit did not flag the `QMAX -> QMA<sup>x</sup>` table-variable mutation.
- The audit did not flag the incomplete Appendix B heading target.

### PDF Ground Truth Notes

- PDF page 24 has the full Appendix B heading as one visual heading:
  `Appendix B  More information about the machine learning classifiers and their construction`.
- PDF page 27 shows Figure 15 on the left and Figure 16 on the right, with each
  caption placed directly below its corresponding image.
- PDF page 29 shows Figure 17 above and Figures 18/19 below, with Figure 18 and
  Figure 19 captions placed under their corresponding images.
- PDF text contains bracket citations such as `simulated annealing [11].` and
  `optimal point must lie [1].`.
- PDF text contains `QMAX` as a feature name/variable in Table 1, not as `QMA`
  plus a superscript or footnote `x`.

Screenshot evidence:

- `_review_screenshots\meine_0011_33cd7b163e\page_24.png`
- `_review_screenshots\meine_0011_33cd7b163e\page_27.png`
- `_review_screenshots\meine_0011_33cd7b163e\page_28.png`
- `_review_screenshots\meine_0011_33cd7b163e\page_29.png`

### Raw HTML Notes

- Raw contains `simulated annealing [11].` and `point must lie [1].` as plain
  text with no links.
- Raw contains the references section as a heading plus plain/ListGroup
  paragraphs beginning with `[1]`, `[2]`, and so on. There are no normalized
  `ref-*` IDs.
- Raw Table 1 preserves the feature name as `QMAX`.
- Raw Appendix B is a plain heading without a stable section target.
- Raw Figure 15/16 extraction order is already fragmented:
  image for Figure 15, image for Figure 16, caption for Figure 15, caption for
  Figure 16.
- Raw Figure 18/19 extraction order has the same grid pattern:
  image for Figure 18, image for Figure 19, caption for Figure 18, caption for
  Figure 19.

### Polish HTML Notes

- Polish still has `simulated annealing [11].` and `point must lie [1].` as
  plain text; no bibliography links are created.
- Polish still has no `ref-*` IDs in the references section; the pair audit
  reports `polish_ref_links: 0`.
- Polish mutates `QMAX` in Table 1 into `QMA<sup class="z2m-table-fn">x</sup>`.
- Polish renders Appendix B as an `h1` containing an internal page span:
  `<h1> <span id="page-23-0"> </span> Appendix B More information ... </h1>`.
  There is no stable ID on the heading wrapper itself.
- Polish partially assembles Figure 15, but leaves Figure 16 as a caption-only
  target next to an orphan image.
- Polish partially assembles Figure 18, but leaves Figure 19 as a caption-only
  target next to an orphan image.

### Defect Classification

| ID | Location | Symptom | Expected | Raw status | Polish status | Classification | Fix candidate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M004-001 | Body citations and references | `[11]` and `[1]` remain plain text in `annealing [11].` and `point must lie [1].` | Bracket citations link to corresponding bracketed references | Raw has bracket citations and bracketed reference list, but no normalized ref IDs | Polish still creates no reference IDs or citation links | `not_fixed_by_polish` | Bracket-reference identity parser for `[N]` bibliography entries and a citation linker for in-text `[N]` tokens. |
| M004-002 | Table 1 feature variable | `QMAX` becomes `QMA<sup>x</sup>` / visually `QMA x` | Preserve `QMAX` as an all-caps feature variable | Raw preserves `QMAX` | Polish treats final `x` as a table footnote/superscript marker | `introduced_by_polish` | Table-footnote and Roman/suffix detector needs a guard for all-caps variables and domain abbreviations. |
| M004-003 | Appendix B heading | Heading target/highlight does not cover the complete heading | Whole heading should have a stable section ID and link target | Raw heading has no stable section ID | Polish only provides an internal page span inside the `h1`; no wrapper ID | `not_fixed_by_polish` | Heading normalizer should assign IDs to full heading elements even when page spans are embedded. |
| M004-004 | Figures 15/16 | Images appear before both captions; polish pairs only one figure and leaves one image/caption orphaned | Each figure image and caption should form one `z2m-figure-unit` in correct order | Raw order is image-image-caption-caption | Polish partially assembles Figure 15 and leaves Figure 16 caption-only/orphan-image | `partially_fixed_by_polish` | Float assembler should detect same-page image grids followed by matching caption runs and pair by order. |
| M004-005 | Figures 18/19 | Same image-image-caption-caption failure for Figure 18 and Figure 19 | Each figure image and caption should form one `z2m-figure-unit` in correct order | Raw order is image-image-caption-caption | Polish partially assembles Figure 18 and leaves Figure 19 caption-only/orphan-image | `partially_fixed_by_polish` | Same float-grid pairing rule as M004-004; audit should flag caption-only figure IDs adjacent to orphan images. |

### Polish Did Not Solve

- It did not recognize bracketed reference-list entries as reference targets.
- It did not link bracketed in-text citations to references.
- It did not create a stable whole-heading target for Appendix B.
- It did not fully repair side-by-side figure grids where multiple images are
  followed by multiple captions.

### Polish Created

- It mutated the all-caps variable `QMAX` into a table-footnote/superscript
  shape.
- It created caption-only figure targets next to orphan images for Figure 16 and
  Figure 19, making the visual order worse than a simple unwrapped raw sequence.

### Regression Coverage Needed

- Bracket-reference fixture:
  a references section with `[1] ...` and `[11] ...` plus body citations
  `[1]` and `[11]` must create `ref-1`, `ref-11`, and corresponding in-text
  links.
- All-caps variable fixture:
  table text such as `QMAX`, `CMG`, `PVR`, and `AUC` must remain plain text and
  must not be split into a base token plus a superscript/footnote suffix.
- Heading-anchor fixture:
  an `h1` or `h2` containing an embedded page-span anchor must still receive a
  stable heading ID on the wrapper, and links should target/highlight the whole
  heading.
- Float-grid fixture:
  `img, img, caption Figure 15, caption Figure 16` should become two complete
  figure units, with no orphan images and no caption-only figure targets.
- Audit fixture:
  pair audit should flag articles with bracketed references plus bracketed body
  citations but `polish_ref_links: 0`.
- Audit fixture:
  pair audit should flag caption-only `fig-*` targets adjacent to orphan images.
- Audit fixture:
  table-footnote audit should flag single-letter superscripts created from
  all-caps variables.

### Verdict

- `fixed_by_polish`: none from the user-reported symptoms.
- `partially_fixed_by_polish`: Figure 15 and Figure 18 were partially wrapped,
  but their neighboring figures remained orphaned and caption-only.
- `not_fixed_by_polish`: bracket citation/reference identity; Appendix B whole
  heading target.
- `introduced_by_polish`: `QMAX` table-variable mutation; caption-only figure
  targets next to orphan images.
- `audit_true_positive_incomplete`: `P04` and `P14` point in the right general
  direction but do not describe the full failures.
- `raw_marker_only`: figure-grid extraction order originates in raw, but the
  polish stage has enough local evidence to assemble the image/caption pairs.
- next action: continue collecting article-level evidence before implementing.
  Bracket-reference identity, all-caps table-variable protection, whole-heading
  anchors, and same-page figure-grid pairing are now universal repair candidates.

### Implementation Status - 2026-04-30

Implemented and verified for `meine_0011_33cd7b163e`:

- M004-001 fixed: references headings with numeric/Roman prefixes such as
  `VIII. References` are now recognized as bibliography starts, bracketed
  reference-list entries receive `ref-*` IDs, and body citations like
  `annealing [11].` and `point must lie [1].` link to `#ref-11` and `#ref-1`.
- M004-002 verified fixed by the current table-footnote guards: Table 1 now
  preserves all-caps feature variable `QMAX` as plain text.
- M004-003 verified fixed by the current heading-anchor pass: the full Appendix
  B heading wrapper now has `id="section-appendix-b"` even with an embedded page
  span.
- M004-004 and M004-005 verified fixed by the current float-grid assembler:
  Figures 15/16 and 18/19 are emitted as complete `z2m-figure-unit` wrappers
  with their corresponding image and caption, not as orphan image/caption pairs.
- Audit-driven split URL repair added: adjacent URL anchors with the same
  quoted `href` are merged into one clean external link. This fixed the
  remaining P36 symptom in reference 21:
  `https://commons.wikimedia.org/wiki/File:Threshold_roc.stack_overflow_answers.svg`.

Universal coverage added:

- `test_polish_html_document_links_bracket_refs_after_numbered_references_heading`
  covers Roman/numeric-prefixed references headings plus body `[N]` citations,
  including page-linked bracket citations rewritten to reference links without
  losing surrounding whitespace.
- `test_polish_html_document_repairs_url_spaces_inside_path_continuations`
  covers plain split URLs with spaces after path separators and underscores.
- `test_polish_html_document_merges_split_quoted_url_anchors` covers multiple
  adjacent anchors that point to the same URL while the `href` value is wrapped
  in stray quotes.

Verification:

- `python -m pytest tests\test_single_file_html.py tests\test_audit_en_polish.py -q`
  -> `224 passed`.
- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0011_33cd7b163e --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_004_after_split_url_fixes_2026-04-30.json`
  -> `articles=1 changed=1 inlined_images=18 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0011_33cd7b163e --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_004_after_split_url_fixes_2026-04-30.json`
  -> `defects=0`, `ref_links=51`, `fig_links=35`, `table_links=11`,
  `page_links=0`, `missing_img=0`.

## 005_meine_0012_68ff614900.html - meine_0012_68ff614900

Source PDF:
`C:\PC\Zotero\Zotero_NIX_Data\storage\5LG4ZQZV\Takeshima и др. - 2022 - The association between the parameters of uroflowmetry and lower urinary tract symptoms in prostate.pdf`

Review HTML:
`manual_review_meine_en_polish_inlined_2026-04-30\005_meine_0012_68ff614900.html`

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0012_68ff614900\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0012_68ff614900\_z2m_stages\02.en.polish.html`

Language detection:

- `en`, confidence `0.99`.

### Manual Notes From User

General requests:

1. Citation restoration should choose a strategy after analyzing the PDF and
   identifying the dominant citation shape.
2. HTML width should be rendered according to the widest table.

Article-specific notes:

1. Figure 1 interrupts body text.
2. The exponent in `(χ2)` becomes a bibliography link.
3. Table 3 extends beyond the display bounds.
4. In Table 3, `<0.01*` becomes `<0.01`.
5. Reference-list numbers are duplicated because the original reference numbers
   already contain backlinks.

### Automated Signals

- Raw audit:
  - `R11`: broken hyphenated/continuation joins, count 7.
- Polish pair audit:
  - `P01`: suspicious raw front-matter marker OCR.
- Pair-audit counters:
  - `polish_ref_links: 45`
  - `polish_fig_links: 1`
  - `polish_table_links: 0`
  - `polish_fig_ids: 4`
  - `polish_table_ids: 4`
  - `polish_missing_local_images: 0`

Audit verdict:

- The audit did not catch the Figure 1 reading-order interruption.
- The audit did not flag the false `χ2 -> #ref-2` link.
- The audit did not flag the Table 3 width/layout failure.
- The audit did not flag the damaged statistical-significance marker.
- The audit did not flag duplicated reference-list labels such as `1. 1 .`.
- `P01` does not cover the user-visible symptoms in this article.

### PDF Ground Truth Notes

- PDF page 2 ends the `Patient population` paragraph with a continuation
  fragment: `a questionnaire validated for`.
- PDF page 3 begins visually with Figure 1, then continues the same paragraph
  with `the assessment of LUTS [10]`.
- For readable HTML, the paragraph should remain logically continuous; the
  top-of-page figure should not split the sentence.
- PDF page 3 shows Pearson's chi-square test as statistical notation `(χ2)`,
  not as a literature citation.
- PDF page 6 shows Table 3 as a very wide table with 19 visible columns.
- PDF page 6 visually shows significant p-values as `<0.01*`, `0.014*`,
  `0.025*`, and similar forms. The table note says `*: statistically
  significant`.
- PDF page 11 shows reference labels as ordinary numbered list labels:
  `1.`, `2.`, `3.`, and so on.

Screenshot evidence:

- `_review_screenshots\meine_0012_68ff614900\page_2.png`
- `_review_screenshots\meine_0012_68ff614900\page_3.png`
- `_review_screenshots\meine_0012_68ff614900\page_6.png`
- `_review_screenshots\meine_0012_68ff614900\page_11.png`

### Raw HTML Notes

- Raw splits the `Patient population` paragraph around Figure 1:
  - before the figure: `... a questionnaire validated for`;
  - after the figure: `the assessment of LUTS [10], before and after RARP.`
- Raw places the Figure 1 image and caption between those two paragraph
  fragments.
- Raw preserves the chi-square expression as plain statistical notation:
  `χ <sup>2</sup>`, with no bibliography link.
- Raw Table 3 is already a very wide table; the widest row has 19 cells.
- Raw Table 3 already has damaged significance markers such as `<0.01�`,
  `0.014�`, `0.025�`, and `0.040�` instead of visual `*`.
- Raw references have original reference labels as page-anchor links, for
  example `<a href="#page-1-0">1</a> .`, but no `ref-*` IDs.
- Raw in-text citation links are mostly page/backlink anchors, not semantic
  reference links.

### Polish HTML Notes

- Polish keeps Figure 1 between the split paragraph fragments; the paragraph
  after the figure still begins with lowercase `the assessment of LUTS`.
- Polish wraps Figure 1 as `id="fig-1"`, but the body reference still targets a
  page span fragment, not the figure unit:
  `<a href="#page-2-0">(Fig</a> 1)`.
- Polish changes `χ <sup>2</sup>` to
  `χ <sup><a class="z2m-ref-link" href="#ref-2">2</a></sup>`.
- Polish CSS fixes `#marker-doc` at `max-width: 980px` while Table 3 has 19
  columns, so the rendered table can overflow or become unusably cramped.
- Polish preserves the damaged significance markers as `�` and does not restore
  the visual `*`.
- Polish assigns `id="ref-N"` and adds `<span class="z2m-ref-num">N.</span>`,
  but it also keeps the original linked label `N .`, producing visible duplicate
  labels such as `1. 1 .`, `2. 2 .`, and `3. 3 .`.

### Defect Classification

| ID | Location | Symptom | Expected | Raw status | Polish status | Classification | Fix candidate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M005-001 | Figure 1 / Patient population | Figure 1 splits a paragraph between `validated for` and `the assessment of LUTS` | Merge the continuation into one readable paragraph and keep the figure as a separate float before or after the full paragraph | Raw inserts image/caption between the two text fragments | Polish preserves the split | `not_fixed_by_polish` | Float-aware continuation repair across top-of-page figures; if pre-float text ends with an incomplete phrase and post-float text starts lowercase, merge text before placing the float. |
| M005-002 | Statistical analyses | `(χ2)` exponent `2` links to `#ref-2` | Keep `χ2`/`χ²` as protected statistical notation | Raw has plain `χ <sup>2</sup>` | Polish links the superscript `2` as a reference | `introduced_by_polish` | Citation linker must protect math/statistical notation, especially Greek-letter expressions in parentheses. |
| M005-003 | Table 3 layout | Table 3 extends beyond readable display bounds | The HTML container or table wrapper should adapt to the widest table | Raw has a 19-column table but no readable CSS constraint | Polish adds a fixed-width readable container (`max-width: 980px`) without wide-table handling | `introduced_by_polish` | Wide-table detector should expand document width or wrap extreme tables in a controlled horizontal-scroll container. |
| M005-004 | Table 3 p-values | Visual `<0.01*` becomes `<0.01�` / effectively loses the significance star | Preserve or restore the `*` significance marker | Raw already has `�` instead of `*` | Polish leaves the damaged marker unchanged | `raw_marker_only` + `not_fixed_by_polish` | Statistical-table marker repair: if table cells have `�` next to p-values and the note says `*: statistically significant`, normalize those markers back to `*`. |
| M005-005 | References list | Reference labels appear as `1. 1 .`, `2. 2 .`, etc. | Each reference should have exactly one visible numeric label | Raw has original label numbers as page-anchor links but no `ref-*` IDs | Polish adds new `z2m-ref-num` spans without consuming/removing the original label anchors | `introduced_by_polish` | Reference-list normalizer should consume existing numeric label tokens when assigning `ref-*` IDs and remove page-backlinks from label positions. |
| M005-006 | Body reference to Figure 1 | `(Fig 1)` still links only the `(Fig` fragment to a page span | Link the whole `Fig 1` reference to `#fig-1` | Raw has page-span link around `(Fig` only | Polish creates `#fig-1` but does not retarget the body link | `not_fixed_by_polish` | Figure-reference linker should rewrite page-span figure references to figure-unit targets after figure IDs are assigned. |

### Polish Did Not Solve

- It did not repair the paragraph split around the top-of-page Figure 1 float.
- It did not retarget `(Fig 1)` to the generated `#fig-1` wrapper.
- It did not restore damaged `*` significance markers in Table 3.

### Polish Created

- It linked the statistical exponent in `(χ2)` to bibliography reference `2`.
- It made Table 3 visibly problematic by applying a fixed readable container
  without wide-table handling.
- It duplicated reference-list labels by adding `z2m-ref-num` while preserving
  the original linked numeric labels.

### Regression Coverage Needed

- Float-continuation fixture:
  paragraph fragment ending in `validated for`, then a figure block, then a
  lowercase continuation `the assessment ...` should become one paragraph plus a
  separate figure float.
- Figure-reference fixture:
  `(Fig 1)` split as `<a href="#page-N">(Fig</a> 1)` must become a whole-token
  link to `#fig-1`.
- Statistical-notation fixture:
  `(χ <sup>2</sup>)`, `χ2`, `R2`, and similar math/statistical expressions must
  not produce `#ref-*` links.
- Wide-table fixture:
  a table with 19 columns must remain inspectable and must not overflow the
  document container.
- Significance-marker fixture:
  p-values like `<0.01�` plus a table note `*: statistically significant` should
  normalize to `<0.01*`; unrelated replacement characters should remain audited,
  not blindly rewritten.
- Reference-list fixture:
  a raw reference item with an existing linked label `<a href="#page-X">1</a>.`
  should become one `id="ref-1"` item with a single visible `1.` label.
- Audit fixture:
  pair audit should flag duplicate reference labels, `#ref-*` links inside
  statistical superscripts, figure references that still target page spans, and
  wide tables without wide-table CSS/layout handling.

### Verdict

- `fixed_by_polish`: body bibliography citations are improved in several places
  compared with raw page/backlink anchors.
- `partially_fixed_by_polish`: Figure 1 receives a figure wrapper, but the
  reading order and body link remain wrong.
- `not_fixed_by_polish`: Figure 1 paragraph continuation; Figure 1 body link;
  damaged p-value significance markers.
- `introduced_by_polish`: `χ2` false reference link; Table 3 display/layout
  regression; duplicated reference-list labels.
- `audit_false_negative`: all user-reported symptoms are currently missed by
  the pair audit.
- `raw_marker_only`: significance-star extraction is damaged before polish, but
  can likely be repaired from local table-note evidence.
- next action: continue collecting article-level evidence. This article adds
  strong support for citation-style detection, math/stat protected zones,
  wide-table rendering, reference-label consumption, and float-aware
  continuation repair.

### Implementation Status - 2026-04-30

Implemented and verified for `meine_0012_68ff614900`:

- M005-001 fixed: prose continuations can now be repaired after figure/table
  wrappers have already been built. The Figure 1 interruption no longer splits
  `a questionnaire validated for the assessment of LUTS`.
- M005-002 verified fixed by the current math/stat protected citation logic:
  the chi-square notation does not create a `#ref-2` link.
- M005-003 verified fixed by the current wide-table layout pass:
  wide tables receive `z2m-wide-table`, and the document receives
  `z2m-has-wide-table`.
- M005-004 fixed: table significance replacement markers are restored from both
  actual U+FFFD and mojibake `пїЅ`; local threshold markers such as
  `vs. пїЅ -150mL` and `vs. пїЅ +10mL/s` are normalized to `&ge;` / `&le;`.
- M005-005 verified fixed by current reference-list normalization: reference
  list labels no longer render as duplicate `1. 1.` / `2. 2.` labels.
- M005-006 fixed: split page-linked table references such as
  `<a href="#page-3-0">(Table</a> 1` now retarget to `#table-1`.
- Audit-driven citation repair added: partial page-linked bracket citations such
  as `[<a ...>29</a><a ...>–34]</a>` and `<a ...>[30</a>]` are converted to
  semantic `#ref-*` citation links instead of being mapped to the first
  reference on the PDF page.
- Audit-driven supplementary-link repair added: supplementary refs such as
  `(S1-S3 Tables)` are unlinked when no semantic table target exists, removing
  residual `#page-*` links.
- Table-note detection was expanded for common article table tails:
  significance notes, median/value notes, abbreviation lines, table DOI lines,
  and OR/CI/perioperative-change definitions. This prevents table notes from
  swallowing body prose and lets body continuations rejoin across table/figure
  float blocks.

Universal coverage added:

- `test_polish_html_document_repairs_partial_page_linked_bracket_citations`
  covers partial page-linked bracket citations and citation ranges.
- `test_polish_html_document_repairs_sentence_split_by_wrapped_float_unit`
  covers body prose split by an already wrapped Figure 1-style float.
- `test_polish_html_document_merges_body_tail_across_table_notes_and_figure`
  covers body continuation across a table, table notes, DOI line, and a figure.
- `test_polish_html_document_unlinks_supplementary_page_refs_without_targets`
  covers supplementary table refs with no semantic target.
- `test_polish_html_document_retargets_split_page_table_refs`
  covers split page-linked `(Table 1)` references.
- `test_polish_html_document_restores_mojibake_significance_and_threshold_markers`
  covers mojibake p-value stars and local threshold comparator repair.

Verification:

- `python -m pytest tests\test_single_file_html.py tests\test_audit_en_polish.py -q`
  -> `230 passed`.
- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0012_68ff614900 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_005_after_005_fixes_round3_2026-04-30.json`
  -> `articles=1 changed=1 inlined_images=7 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0012_68ff614900 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_005_after_005_fixes_round3_2026-04-30.json`
  -> `defects=0`, `ref_links=43`, `fig_links=7`, `table_links=7`,
  `page_links=0`, `bad_chars=0`, `missing_img=0`.

### Batch Regression - 001-005 - 2026-04-30

After the 005 fixes, the current code was replayed across the manually reviewed
Meine articles `001` through `005`.

Verification:

- `python scripts\repolish_en_from_raw.py --roots ...001 ...002 ...003 ...004 ...005 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_001_005_after_005_fixes_2026-04-30.json`
  -> `articles=5 changed=2 inlined_images=56 missing_images=0`.
- `python scripts\audit_en_polish.py --roots ...001 ...002 ...003 ...004 ...005 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_001_005_after_005_fixes_2026-04-30.json`
  -> `defects=none`, `raw_img=56`, `polish_img=56`, `ref_links=777`,
  `fig_links=90`, `table_links=28`, `page_links=0`, `bad_chars=0`,
  `missing_img=0`.

## 006_meine_0013_a6269b65e9.html - meine_0013_a6269b65e9

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0013_a6269b65e9\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0013_a6269b65e9\_z2m_stages\02.en.polish.html`

### Baseline Findings

- The article is not an English article. The main body is German
  (`Deutsche Leitlinien...`, `Literatur`), with an English abstract later in the
  document.
- The EN pair audit reported `P04` because German bracket citations remained
  unlinked and `polish_ref_links=0`.
- This is not a good EN-polish target. Fixing it by broadening English citation
  recovery to German `Literatur` would hide the real problem: a non-English PDF
  entered the English pipeline.

### Implementation Status - 2026-04-30

Implemented language-gate protection:

- `language_detect.py` now recognizes German (`de`) as a non-target Latin-script
  language using German stopwords and Latin-1 word/character sampling.
- For `meine_0013_a6269b65e9`, detection changed from false `en` to
  `de`, confidence `0.98`, reason `latin_majority_german_stopwords`.
- For an English run (`target_language=en`), the gate now returns
  `should_skip=True`, reason `detected_de_not_en`.

Regression coverage added:

- `test_german_body_with_english_abstract_is_gated_before_english_run` verifies
  that a German body with an English abstract is skipped for an English run.

Verification:

- `python -m pytest tests\test_language_detect.py tests\test_zotero_library_single_loop_language_gate.py tests\test_single_file_html.py tests\test_audit_en_polish.py -q`
  -> `241 passed`.
- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0013_a6269b65e9 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_006_baseline_2026-04-30.json`
  -> `articles=1 changed=1 inlined_images=0 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0013_a6269b65e9 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_006_baseline_2026-04-30.json`
  -> baseline EN-polish audit `P04=1`, now classified as `language_filter_miss`
  rather than an EN-polish repair target.

Follow-up requirement added to the fix plan:

- The pre-marker detected `source_language` must be persisted and passed to the
  later translation stage together with the separate user/configured
  `target_language`.
- Translation must not re-detect source language from polished HTML, because
  abstracts, references, and OCR noise can disagree with the dominant body
  language.

## 007_meine_0014_10ec76f1a8.html - meine_0014_10ec76f1a8

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0014_10ec76f1a8\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0014_10ec76f1a8\_z2m_stages\02.en.polish.html`

### Baseline Findings

- This is a short English handout (`Tactile Graphics`), not a normal scholarly
  article with references, figures, tables, or numbered citations.
- Raw contains six local images. Polish inlines all six images and keeps the two
  external resource URLs clickable.
- Raw splits a body sentence around a layout image:
  `When tactile graphics are introduced ... it` / image /
  `is important to recognize...`.
- Current polish repairs that text continuity and leaves the image as a separate
  block after the repaired paragraph. For this handout layout, that looks like a
  useful float-aware reading-order repair rather than a new defect.
- No citation/reference/table/figure-link requirements apply to this item.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0014_10ec76f1a8 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_007_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=6 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0014_10ec76f1a8 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_007_current_2026-05-01.json`
  -> `defects=none`, `raw_img=6`, `polish_img=6`, `page_links=0`,
  `bad_chars=0`, `missing_img=0`.

### Follow-Up

- No EN-polish code change needed from this article.
- Future audit can optionally tag short non-scholarly handouts separately so
  clean zero-reference items are not confused with failed reference detection.

## 008_meine_0015_be8f26bb9b.html - meine_0015_be8f26bb9b

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0015_be8f26bb9b\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0015_be8f26bb9b\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all nine local images.
- Figure 1 is assembled into a float wrapper and body references such as
  `Fig. 1b` are retargeted to `#fig-1`.
- Bracket references are mostly recognized and linked in the body.
- The DOI line is made clickable where it survives as visible text.

### Defects Not Fixed From Raw

- The source contains ACM/page boilerplate in the middle of the introduction:
  permission text, conference line, a DOI-only line, and a huge TeX macro leak
  containing repeated `\@ifnextchar`.
- Raw splits one body sentence around that boilerplate:
  `... keep the connection to the two-dimensional original, while` /
  boilerplate / `the plasticity of the added height...`.
- Polish does not cleanly repair this interruption. Worse, it concatenates the
  DOI line with the continuation body sentence:
  `DOI: http://dx.doi.org/10.1145/2982142.2982176 the plasticity...`.
- Raw has a visible URL typo in an ACM anchor:
  visible `hps://dl.acm.org/doi/10.1145/2982142.2982176`, while the `href` is
  valid `https://...`. Polish leaves the visible typo.
- Raw has hyphen/space damage such as `touchinteraction`, `realworld`,
  `off-theshelf`, and `state-ofthe-art`; polish does not repair these.
- Raw contains the reference-list split `[13] ... pages 1243-1250,` followed by
  continuation-only `Heidelberg, 2006. Springer.`.

### Defects Introduced By Polish

- The continuation-only reference item `Heidelberg, 2006. Springer.` becomes a
  synthetic `ref-14`. The real raw `[14] R. J. K. Jacob...` becomes `ref-15`.
  This shifts semantic targets for references `14+`.
- Plain decimal ratings are converted into false reference links:
  `9.2`, `9.3`, `9.5`, and `8.2` become linked `#ref-*` pairs.
- Section range text `Sections 3.3.5-3.3.8` is corrupted into reference links
  for `3,3` plus a dangling `.5-3.3.8`.
- The page-locator citation `[14, p. 156]` remains unlinked. After the reference
  drift above, linking it naively would also target the wrong entry.
- The roman-footnote/suffix repair is too broad outside table contexts and
  splits normal names/words:
  `Gustav` -> `Gusta v`, `Bulatov` -> `Bulato v`, `Vinnikov` -> `Vinniko v`.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0015_be8f26bb9b --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_008_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=9 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0015_be8f26bb9b --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_008_current_2026-05-01.json`
  -> `P04=1`, `P25=1`, `ref_links=0` in the summary is misleading because
  body citation links exist but shifted reference IDs and false decimal/section
  links are not yet detected by the audit.

### Fix Requirements

- Merge continuation-only reference items without assigning synthetic IDs from
  list ordinal; preserve visible labels as the only trusted `ref-N` source.
- Add citation guards for decimal values, dotted section numbers/ranges, and
  page-locator citations.
- Classify publisher/page boilerplate separately from front matter and keep it
  out of body continuation repair.
- Detect and report TeX macro leaks.
- Restrict roman suffix repair to true table/footnote contexts.
- Repair visible URL text from valid `href` when the visible URL is a near-miss.

## 009_meine_0016_21f99425d5.html - meine_0016_21f99425d5

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0016_21f99425d5\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0016_21f99425d5\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all 44 local images.
- Many body figure references are detected and linked.
- Some table references are detected and linked.
- Turkish characters in the front matter are decoded correctly in current
  polish (`Barış ÖZYURTLU`, `İlkay SALIHOĞLU`), even though PowerShell default
  output can display the raw file as mojibake.

### Defects Not Fixed From Raw

- This is a thesis/book-style document with chapter-local numbering:
  `Figure 2.1`, `Figure 2.10`, `Figure 3.20`, `Table 4.2`, etc.
- Raw contains a long table of contents, list of tables, and list of figures.
  These index regions are structurally different from body captions and should
  not drive float-target creation.

### Defects Introduced By Polish

- Composite figure numbers are collapsed to chapter-only IDs:
  `Figure 2.1`, `Figure 2.2`, ..., `Figure 2.11` all target/reuse `fig-2`;
  `Figure 3.1`, ..., `Figure 3.27` target/reuse `fig-3`.
- The polished HTML contains duplicate semantic IDs:
  `fig-2` appears 11 times, `fig-3` appears 27 times, `fig-4` appears 2 times,
  and `table-4` appears 2 times.
- Links in `LIST OF FIGURES` and body prose therefore point to the wrong or
  first matching target instead of the specific full figure number.
- The audit `P13` warning is partly an audit false positive: list-of-figures
  rows are being interpreted as caption-without-image evidence.
- The audit `P39` warning points to a real wrapper problem near figures
  `2.10` and `2.11`: one adjacent figure image/caption remains outside a
  complete wrapper, while sharing the same collapsed `fig-2` target.
- The roman suffix/table-footnote repair again overfires:
  `APPENDIX 1`, `APPENDIX 3`, and `APPENDIX 4` in the contents table become
  `APPEND<sup class="z2m-table-fn">ix</sup>`.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0016_21f99425d5 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_009_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=44 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0016_21f99425d5 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_009_current_2026-05-01.json`
  -> `P13=1`, `P39=1`, `fig_links=105`, `table_links=4`,
  `polish_fig_ids=40`, `polish_table_ids=3`.

### Fix Requirements

- Support composite figure/table identifiers and generate unique IDs such as
  `fig-2-1`, `fig-2-10`, `fig-3-20`, `table-4-2`.
- Add duplicate semantic ID audit coverage.
- Treat table of contents, list of figures, and list of tables as index zones:
  they may link to existing full targets, but they must not create targets or
  trigger caption-without-image defects.
- Restrict roman suffix repair so all-caps words such as `APPENDIX` remain
  intact.

## 010_meine_0017_7ef4a4f872.html - meine_0017_7ef4a4f872

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0017_7ef4a4f872\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0017_7ef4a4f872\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines both local images.
- References are assigned stable IDs and most bracket citations link correctly.
- Figure and table references are mostly linked.
- Author affiliation superscripts are preserved as footnote-style markers, not
  bibliography links.

### Defects Not Fixed From Raw

- Raw contains page anchors embedded inside ordinary words, for example
  `ob` + `je` + `ct` + `s w` + `ould` and `safe` + `ty c` + `oncerns`.
- Raw contains repeated external URL annotations over normal acknowledgement
  words near `Design for All-Foundation Barcelona`; polish preserves these
  suspicious links.

### Defects Introduced Or Amplified By Polish

- Some page-fragment anchors inside words are rewritten to bibliography links
  because the same `#page-*` IDs also appear inside reference entries:
  `s w` becomes a `#ref-10` link inside `objects would`, and `ty c` becomes a
  `#ref-8` link inside `safety concerns`.
- Several page links remain inside word fragments, so the visible text is still
  broken even when it is not retargeted.
- The audit warning `P36` reports a split URL/DOI near the reference list, but
  it misses the more important word-fragment page/ref-link defect.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0017_7ef4a4f872 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_010_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=2 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0017_7ef4a4f872 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_010_current_2026-05-01.json`
  -> `P36=1`, `ref_links=34`, `fig_links=6`, `table_links=2`,
  `page_links=15`, `bad_chars=0`.

### Fix Requirements

- Page anchors should be retargeted to references only when the visible text is
  citation-like. Word-fragment page anchors must be unwrapped and merged into
  prose.
- Add audit coverage for `#page-*` and `#ref-*` links embedded inside ordinary
  word fragments.
- Review repeated external URL anchors over plain words as likely PDF annotation
  overlay artifacts.

## 011_meine_0020_1d46c89d76.html - meine_0020_1d46c89d76

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0020_1d46c89d76\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0020_1d46c89d76\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all eight local images.
- Figure wrappers and figure links are mostly clean: references such as
  `Figure 1` point to semantic figure wrappers, and the final figure sequence is
  not collapsed into duplicate IDs.
- Bibliography items are assigned stable `ref-*` IDs, and ordinary bracket
  citations are linked.
- The general audit reports no current defects for this pair.

### Defects Not Fixed From Raw

- IOP publisher/front-matter material remains visible at the beginning:
  `PAPER - OPEN ACCESS`, `To cite this article`, `Related content`, and
  related-content snippets. This is probably front matter rather than body
  corruption, but it should remain classified so it cannot be merged into body
  prose later.
- Raw has a footnote/publisher line with spacing damage:
  `theCreative Commons Attribution 3.0 licence`. Polish preserves that damaged
  token.

### Defects Introduced By Polish

- A method-list cross-reference is falsely converted into a bibliography link:
  raw `steps 2 and 3` becomes `steps 2 and <sup><a href="#ref-3">3</a></sup>`.
  In context this refers to procedure steps inside the same five-step method
  list, not to reference `[3]`.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0020_1d46c89d76 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_011_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=8 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0020_1d46c89d76 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_011_current_2026-05-01.json`
  -> `defects=none`, `raw_img=8`, `polish_img=8`, `ref_links=22`,
  `fig_links=7`, `page_links=0`, `bad_chars=0`.

### Fix Requirements

- Citation linking must treat numbered procedure steps and method-list
  cross-references as protected prose, not bibliography citations.
- Audit should report `#ref-*` links inside step references such as
  `steps 2 and 3`.
- Publisher/front-matter blocks should keep their classification so future
  reading-order repair does not merge them into surrounding body paragraphs.

## 012_meine_0024_69ad5170a0.html - meine_0024_69ad5170a0

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0024_69ad5170a0\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0024_69ad5170a0\_z2m_stages\02.en.polish.html`

### What Improved

- This is a duplicate/source variant of the same Reichinger 2012 article
  reviewed as `010`, and it reproduces the same broad polish behavior.
- Polish inlines both local images.
- Bracket citations, figure references, and table references are mostly linked.
- Author affiliation superscripts remain footnote-style markers rather than
  bibliography links.

### Defects Not Fixed From Raw

- Raw contains many page anchors embedded inside ordinary words and sentence
  continuations, including `object should`, `safety concerns`, `include`,
  `expressiveness`, `alternatives`, `according to`, `straightforward`, and
  `Generally`.
- Polish leaves many of these page anchors in place, so the text still contains
  visible word breaks such as `incl` / page link / `ude`,
  `Gener` / page link / `digital`, and `straightfo` / page link / `ard`.
- The acknowledgement still contains repeated external `tactileview.com` links
  over normal words near `Design for All-Foundation Barcelona`; these look like
  PDF annotation overlay artifacts and should not be trusted as content links.

### Defects Introduced Or Amplified By Polish

- Some word-fragment page anchors are retargeted to bibliography references.
  The fragment between `safe` and `oncerns` becomes a `#ref-8` link, breaking
  `safety concerns`.
- Another prose fragment is retargeted to `#ref-2`, producing broken text near
  `T ... dditive production methods`.
- Table footnote/roman-suffix repair overfires inside a normal table word:
  raw `multi-view input` becomes
  `mult<sup class="z2m-table-fn">i</sup>-view input`.
- The audit `P36` warning points to a reference-list URL adjacency, but it does
  not report the higher-impact page/ref word-fragment defects or the false table
  footnote split.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0024_69ad5170a0 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_012_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=2 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0024_69ad5170a0 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_012_current_2026-05-01.json`
  -> `P36=1`, `raw_img=2`, `polish_img=2`, `ref_links=34`,
  `fig_links=6`, `table_links=2`, `page_links=15`, `bad_chars=0`.

### Fix Requirements

- Same as `010`: page anchors inside word fragments must be unwrapped and merged
  into prose, not retargeted to references.
- Citation retargeting should require citation-shaped visible text and should
  reject empty, whitespace-only, or word-fragment anchors.
- Roman/table-footnote splitting must not split normal words or hyphenated
  terms such as `multi-view`.
- Audit should prioritize word-fragment page/ref links and table-word suffix
  splits over the current broad URL adjacency warning.

## 013_meine_0027_4a8785387f.html - meine_0027_4a8785387f

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0027_4a8785387f\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0027_4a8785387f\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all seventeen local images.
- Figure IDs are unique in the current output: `fig-1` through `fig-15` each
  appear once.
- Many body figure references are linked to semantic figure wrappers.
- Bibliography items and bracket citations are mostly linkified.
- A raw split DOI in the reference list is visually repaired in polish:
  `http://dx.doi.org/10.1007/ BF00056771` becomes a single URL-like anchor.

### Defects Not Fixed From Raw

- Raw splits reference `[7]` across list items: the first item ends at
  `Pattern Analysis and Machine`, and the next unnumbered item continues with
  `Intelligence, IEEE Transactions on, 10, 1988, 439-451.`.
- Raw contains front-matter page anchors glued into author markers:
  `Govern` + page-anchor `i1,` and `Furfer` + page-anchor `i3,`.
- Raw has equation tags such as `\tag{2.1}` and textual references such as
  `Eqn. 2.1)`, but no stable equation IDs are created by the current polish.

### Defects Introduced Or Amplified By Polish

- The unnumbered continuation after reference `[7]` is synthesized as
  `id="ref-8"`. The real raw `[8] Governi...` then becomes `ref-9`, shifting
  all later semantic reference targets.
- Body multi-citations compensate for the drift by linking visible labels to
  different target numbers, for example visible `,9` points to `#ref-10`,
  visible `,11` points to `#ref-12`, visible `,31` points to `#ref-32`, and
  visible `33` points to `#ref-34`.
- Equation references remain page anchors instead of equation links:
  `Eqn. 2.1)` and `Eqn. 2.4)` still target `#page-*`.
- Front-matter author markers remain page anchors/glued text instead of
  normalized affiliation markers: `Govern <a href="#page-0-0"> i1, </a>` and
  `Furfer <a href="#page-0-1"> i3, </a>`.
- Roman/name splitting appears in the reference list: `Belyaev, A.` becomes
  `Belyae v, A.`.
- The audit reports `P33`, `P34`, and `P36`, but it does not directly name the
  highest-impact defects: reference label/target mismatch, decimal equation
  refs left as page anchors, and front-matter page-anchor glue.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0027_4a8785387f --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_013_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=17 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0027_4a8785387f --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_013_current_2026-05-01.json`
  -> `P33=1`, `P34=1`, `P36=1`, `raw_img=17`, `polish_img=17`,
  `ref_links=66`, `fig_links=49`, `page_links=4`, `bad_chars=0`.

### Fix Requirements

- Reference normalization must merge continuation-only entries after incomplete
  titles or journal names and must never create a new `ref-*` ID from list
  ordinal alone.
- Citation retargeting must use the visible citation label as the semantic
  target number. A visible `9` should not link to `#ref-10` just because the
  reference list drifted.
- Equation IDs must support dotted labels such as `2.1`, `2.4`, and `2.7`, and
  text refs such as `Eqn. 2.1)` should link to those IDs instead of `#page-*`.
- Front-matter page anchors that glue author names to affiliation markers must
  be normalized or unwrapped before reference/page retargeting.
- Roman-suffix repair must not split ordinary names such as `Belyaev`.

## 014_meine_0029_ddf58debe6.html - meine_0029_ddf58debe6

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0029_ddf58debe6\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0029_ddf58debe6\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines both local images.
- The document is marked as a wide-table document, and the first very wide
  table receives `class="z2m-wide-table"`.
- Bibliography entries are assigned `ref-*` IDs without the continuation drift
  seen in `008` and `013`.
- Most superscript-style citations that are still represented as `<sup>` are
  linked correctly, for example `publication 2`, `Griffiths et al. 6`, and
  `Yang et al. 7`.
- The split two-anchor URL in reference `9` is visually repaired into one
  external URL anchor.

### Defects Not Fixed From Raw

- Raw already contains page anchors across normal prose at page breaks, for
  example `Additionally, elevated residuals due to turbulent flow or` and
  `that formulas that use the total`. Polish preserves them as `#page-*` links
  instead of unwrapping them back into prose.
- Raw has flattened superscript citations such as `dysfunctional voiders.3` and
  `Agarwal et al3`. Polish does not restore these as semantic links even though
  the article has a clear superscript numeric citation style and `ref-3` exists.
- A DOI in the acknowledgments remains split and plain:
  `doi: 10.1002/ nau.22813`.

### Defects Introduced Or Amplified By Polish

- The roman/table-footnote repair massively overfires in table variables:
  raw has `Qmax`, while polish contains about 170 instances of
  `Qma<sup class="z2m-table-fn">x</sup>`.
- Table/caption pairing drifts around tables `4` and `5`: the visible `TABLE 4`
  caption stays as a standalone `p id="table-4"`, the following actual table is
  wrapped as `div id="table-5"`, and the visible `TABLE 5` caption is appended
  after that table. The next actual table is left unwrapped.
- `TABLE 2` is also not wrapped as a float unit: the caption gets
  `id="table-2"`, while the following table remains separate.
- Some table references become partial links (`4`, `5`, `7.`) instead of the
  whole visible `Table N` phrase.
- The audit reports only `P36`, and that warning points at the repaired INSEAD
  URL rather than the remaining split DOI or the table/citation defects.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0029_ddf58debe6 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_014_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=2 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0029_ddf58debe6 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_014_current_2026-05-01.json`
  -> `P36=1`, `raw_img=2`, `polish_img=2`, `ref_links=19`,
  `fig_links=0`, `table_links=13`, `page_links=2`, `bad_chars=0`.

### Fix Requirements

- Roman/table-footnote repair must protect mixed-case scientific variables such
  as `Qmax`, `Qavg`, and similar domain terms, not only all-caps variables.
- Table wrapping must use the visible table number from the caption as the
  trusted ID and must pair captions with the correct adjacent table even when a
  page span or a caption-after-table pattern is present.
- Superscript citation strategy should restore flattened citation tokens such
  as `et al3` and sentence-final `.3` under strict article-level confidence
  guards.
- Page anchors that hold ordinary page-break prose should be unwrapped and
  merged, not left as visible navigation links.
- DOI repair must handle `doi: 10.1002/ nau.22813` and make it clickable
  without changing the visible DOI content beyond removing the spurious space.
- Audit needs direct checks for table-caption/target drift, mixed-case variable
  footnote splits, flattened unlinked citations, and split plain DOI text.

## 015_meine_0030_7ddd815634.html - meine_0030_7ddd815634

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0030_7ddd815634\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0030_7ddd815634\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all eighty-six local images without missing-image warnings.
- The run does not create bibliography, figure, table, or page links in this
  book-like document, so there is no citation-link drift in the current output.

### Language Gate Finding

- This is a German source book, `Die Photographie mit dem Kollodiumverfahren`
  by J. M. Eder, 1927.
- The review index still classifies it as `detected_language=en` with
  `language_confidence=0.99`.
- This is therefore not an EN-polish article-quality case first; it is a
  pre-marker language-gate failure. It should not be sent through the English
  marker/polish/translation path.

### Defects Not Fixed From Raw

- German OCR mojibake remains throughout the text, for example
  `AUSFГњHRLICHES`, `fГјhren`, `gГ¤nzlich`, and `Photographie`.
- The current audit reports `P06` on German degree/unit text such as
  `77В° C`; this is a symptom of running English-oriented checks against a
  German OCR document.

### Defects Introduced Or Amplified By Polish

- The same roman/table-footnote repair is unsafe in non-English table text:
  ordinary words such as `Kali-Salpeter`, `Kupfervitriol`, `Mastix`, and
  `Borax` are split with `z2m-table-fn` superscripts.
- Inlining images expands the polished HTML substantially, from roughly
  1.1 MB raw HTML to roughly 15.2 MB polished HTML. This is expected for
  self-contained review HTML, but it matters for reviewing old book scans with
  many embedded pages.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0030_7ddd815634 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_015_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=86 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0030_7ddd815634 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_015_current_2026-05-01.json`
  -> `P06=1`, `raw_img=86`, `polish_img=86`, `ref_links=0`,
  `fig_links=0`, `table_links=0`, `page_links=0`, `bad_chars=0`.

### Fix Requirements

- Pre-marker source-language detection must reject this document for an English
  run before marker is invoked.
- Run metadata must preserve `source_language=de` so later translation receives
  the correct source language instead of guessing from polished HTML.
- If a future German polish profile processes this document, roman/table
  footnote splitting must be language-neutral and must not split ordinary words
  ending in `i`, `v`, `x`, `vi`, or `ix`.

## 016_meine_0031_45c7a0c4d9.html - meine_0031_45c7a0c4d9

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0031_45c7a0c4d9\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0031_45c7a0c4d9\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all six local images.
- The reference list receives stable `ref-1` through `ref-36` IDs.
- Some figure wrappers and figure links exist, and `Table 1` is wrapped as a
  semantic table unit.
- No replacement characters or missing local images are reported.

### Defects Not Fixed From Raw

- Raw contains figure-order/caption-order damage: an image for `Fig. 1` is
  followed by both `Fig. 1` and `Fig. 4` captions; another image for `Fig. 2`
  is followed by both `Fig. 2` and `Fig. 5` captions.
- Raw has semantic cross-references as page anchors, for example `(Table 1)`,
  `(Fig. 1)`, `(Fig. 2)`, and `(Figs. 3 and 5)`.
- Raw splits many author-year citations into page anchors, including
  `(Born et al., 1998; Martin et al., 1999)`, `(Adam et al., 2001)`, and
  `(Dehaene-Lambertz et al., 2002)`.

### Defects Introduced Or Amplified By Polish

- Article-level citation strategy is wrong for this document. The body uses
  author-year citations, but polish rewrites many different author-year
  page-anchor citations to the same numeric target `#ref-11`.
- Other author-year citations remain as `#page-*` links, so the output mixes
  false semantic bibliography links with unresolved page links.
- Figure wrappers are mispaired: `fig-4` is added as an alias inside the
  `fig-1` wrapper, and `fig-5` is added as an alias inside the `fig-2` wrapper.
  These aliases make figure navigation ambiguous when the visible captions
  refer to different figures.
- Cross-reference `(Figs. 3 and 5)` is corrupted: `(Figs. 3` remains a page
  link and `5` becomes a false bibliography link to `#ref-5` instead of a
  figure link to `#fig-5`.
- `(Table 1)`, `(Fig. 1)`, and `(Fig. 2)` remain page links even though
  `table-1`, `fig-1`, and `fig-2` targets exist.
- Roman/name splitting appears again: `Yakovlev (1967)` becomes
  `Yakovle v (1967)`.
- The audit catches only part of this as `P33` and `P14`; it does not directly
  report author-year citations mapped to the wrong numeric reference, figure
  list refs turned into bibliography links, or unrelated figure aliases inside
  one wrapper.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0031_45c7a0c4d9 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_016_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=6 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0031_45c7a0c4d9 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_016_current_2026-05-01.json`
  -> `P01=1`, `P14=1`, `P33=1`, `raw_img=6`, `polish_img=6`,
  `ref_links=28`, `fig_links=9`, `page_links=16`, `polish_fig_ids=7`,
  `polish_table_ids=1`, `bad_chars=0`.

### Fix Requirements

- Article-level citation detection must recognize author-year in-text style and
  must not retarget author-year page anchors to numeric references via page
  target reuse.
- If author-year matching is implemented, it should match by surname/year
  against the reference list. If confidence is low, unwrap to plain citation
  text rather than creating a wrong `#ref-*` link.
- Figure list/range references such as `(Figs. 3 and 5)` must link to figure
  targets, not bibliography targets.
- Page-anchor figure/table refs should be retargeted after wrappers exist:
  `(Table 1)` -> `#table-1`, `(Fig. 1)` -> `#fig-1`, `(Fig. 2)` -> `#fig-2`.
- Figure assembly must not hide unrelated visible figure numbers as aliases
  inside another figure wrapper unless the image is genuinely shared by the
  same compound figure.
- Roman-suffix repair must not split author surnames such as `Yakovlev`.

## 017_meine_0034_2a6279ac39.html - meine_0034_2a6279ac39

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0034_2a6279ac39\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0034_2a6279ac39\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all five local images.
- DOI text in the article citation is linked.
- Footnote paragraphs for web resources are more recognizable than in raw, and
  external URLs such as `about.fb.com`, `livingpaintings.org`, and
  `github.com/facebookresearch/detectron` are clickable.
- Equation rows receive stable IDs (`eq-1`, `eq-2`, `eq-3`).
- The general audit currently reports no defects.

### Defects Not Fixed From Raw

- Figure 1 image is not extracted. Polish correctly emits a visible missing
  figure warning, but the figure remains absent from the review HTML.
- Figure 3 and Figure 4 content is not fully wrapped as semantic figure units:
  only `fig-1` and `fig-2` targets exist even though the text references
  `Figure 3`, `Figure 3D`, `Figure 4A`, `Figure 4B`, and `Figure 4`.
- The raw web-footnote `2` is malformed as escaped markup before polish:
  `&lt;sup&gt;2&lt;/sup&gt;Living Paintings...`.

### Defects Introduced Or Amplified By Polish

- The citation strategy is mixed up for a Frontiers-style article. The main
  bibliography is author-year, while superscript `1`, `2`, and `3` in the body
  are web/source footnotes. Polish links these footnote markers to bibliography
  IDs `ref-1`, `ref-2`, and `ref-3`.
- Statistical/comma-number values are falsely linked as references:
  effect size `1,5` becomes links to `ref-1` and `ref-5`; allocation ratio
  `3,1` becomes links to `ref-3` and `ref-1`; sample-size group `2` becomes
  `ref-2`.
- Author-year linking is inconsistent: `Lederman` is linked to `ref-27`, while
  many other author-year citations remain plain text.
- Roman/name splitting appears again in front matter and references:
  `Nedelev` becomes `Nedele v`.
- The audit misses these issues because it does not yet check footnote markers
  linked to bibliography refs, comma-decimal/statistical values linked as refs,
  or unresolved visible figure references with no matching `fig-*` target.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0034_2a6279ac39 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_017_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=5 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0034_2a6279ac39 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_017_current_2026-05-01.json`
  -> `defects=none`, `raw_img=5`, `polish_img=5`, `ref_links=9`,
  `fig_links=6`, `table_links=1`, `page_links=1`, `polish_fig_ids=2`,
  `polish_table_ids=1`, `bad_chars=0`.

### Fix Requirements

- Article-level citation strategy must distinguish author-year bibliography
  references from numbered web/source footnotes in Frontiers-style articles.
- Numeric footnote markers should link to footnote blocks or remain footnote
  markers, not bibliography references.
- Citation guards must treat comma-decimal/statistical values such as `1,5` and
  `3,1` like decimal values, not reference lists.
- Figure audit should report visible `Figure N` / `Figure 4A` / `Figure 3D`
  references when no matching semantic figure target exists.
- Roman-suffix repair must not split surnames such as `Nedelev`.

## 018_meine_0035_520bdb5064.html - meine_0035_520bdb5064

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0035_520bdb5064\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0035_520bdb5064\_z2m_stages\02.en.polish.html`

### What Improved

- Polish inlines all twenty-six local images.
- Twenty-two figure IDs are created, and many figure references are linked.
- The bracket reference list is mostly normalized into `ref-*` targets.
- The supplementary-material DOI is visually repaired from two split raw URL
  anchors into one external URL anchor.

### Defects Not Fixed From Raw

- Several bracket citations remain as page links instead of semantic reference
  links: `[1].`, `[2].`, `[3].`, `[4]:`, `[17,18].`, `[20-23].`, `[30].`, and
  `[33].`.
- The problematic citations include no-space lists and en-dash ranges, which
  should be ordinary bracket-citation grammar.
- A float sequence interrupts a sentence: `including "The Annunciation" ... (see
  Fig. 19) permanently` is split by the image/captions for figures 16-18 before
  the continuation `displayed at the Museo di San Marco...`.

### Defects Introduced Or Amplified By Polish

- Some nearby bracket citations are linked, but the page-anchor citations above
  remain unresolved, so one article mixes good semantic `#ref-*` links with
  stale `#page-*` citation links.
- The audit `P36` warns on the supplementary DOI even though the current polish
  output visually repairs it to a single anchor; this looks like an audit false
  positive after URL repair.
- Figure/reference linking is otherwise strong enough here that the remaining
  defects are narrow and good regression fixtures.

### Audit Result - 2026-05-01

- `python scripts\repolish_en_from_raw.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0035_520bdb5064 --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_018_current_2026-05-01.json`
  -> `articles=1 changed=1 inlined_images=26 missing_images=0`.
- `python scripts\audit_en_polish.py --roots md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0035_520bdb5064 --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_018_current_2026-05-01.json`
  -> `P04=1`, `P33=1`, `P36=1`, `P40=1`, `raw_img=26`,
  `polish_img=26`, `ref_links=53`, `fig_links=26`, `table_links=1`,
  `page_links=8`, `polish_fig_ids=22`, `polish_table_ids=1`,
  `bad_chars=0`.

### Fix Requirements

- Bracket citation parser must retarget page-anchor citations with no-space
  lists and ranges: `[17,18]`, `[20-23]`, and trailing-punctuation variants.
- Citation repair should avoid mixed states where some bracket citations link to
  `#ref-*` while same-style citations in the same article remain `#page-*`.
- Float-aware reading-order repair should rejoin sentence fragments around
  figure runs while keeping figures as separate units.
- Audit should distinguish genuinely split URL/DOI text from already repaired
  single-anchor URLs to avoid false positives.

### Follow-up Result - 2026-05-02

- Re-polish over `018-025` with the current fixes removes the stale bracket
  page-citation state in this article: `page_links=0`, `P04/P33/P36` no longer
  appear.
- Current remaining audit finding is only `P40`: the figure run around
  `"The Annunciation" ... (see Fig. 19) permanently ... displayed at the Museo
  di San Marco` still needs a float-aware reading-order solution.

## 019_meine_0036_d04b54116e.html - meine_0036_d04b54116e

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0036_d04b54116e\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0036_d04b54116e\_z2m_stages\02.en.polish.html`

### What Improved

- Figure subpanel page anchors such as `Fig. 1a-c`, `Fig. 1d-f`, and similar
  references are now retargeted to semantic figure anchors.
- The false bibliography link inside the physical unit `N m2` is repaired to a
  unit exponent.
- Many linked negative unit exponents in rate/density units, including
  `nm d^-1` and `cm^-3`, are converted away from `#ref-*` links.
- The remaining unresolved `Table 2` page anchor is unwrapped rather than left
  as a misleading `#page-*` semantic reference.
- `page_links` dropped from `8` to `0`, figure links rose from `54` to `61`,
  and reference links dropped from `196` to `179` because unit false positives
  were removed.

### Defects Not Fixed From Raw

- `Figure 2f summarizes...` still appears as a caption-like paragraph without a
  nearby image. This looks like source extraction / figure assembly, not a safe
  citation-only polish fix.
- Some micro-unit text is still mojibake-like (`Ојm`) in the audit snippet,
  which keeps `P05/P06` alive around the Neuralink paragraph.
- The variable phrase `D eff` remains split as plain text. It should probably
  become a compact variable form such as `D_eff` or `D<sub>eff</sub>`, but that
  needs a broader variable-normalization rule.

### Defects Introduced Or Amplified By Polish

- No remaining `#page-*` semantic links after the 2026-05-02 pass.
- Remaining linked-reference concerns are mostly audit warnings around numeric
  citation/unit proximity and variable typography, not obvious wrong targets.

### Audit Result - 2026-05-02

- `python scripts\repolish_en_from_raw.py --roots ...018-025... --out-report md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_018_025_after_fixes_2026-05-02.json`
  -> `articles=8 changed=2 inlined_images=182 missing_images=0`.
- `python scripts\audit_en_polish.py --roots ...018-025... --out md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_018_025_after_fixes_2026-05-02.json`
  -> for this article: `P05=1`, `P06=1`, `P13=1`, `P45=1`,
  `raw_img=6`, `polish_img=6`, `ref_links=179`, `fig_links=61`,
  `table_links=5`, `page_links=0`, `bad_chars=0`.

### Fix Requirements

- Add a variable typography rule for common effective-property variables:
  `D eff`, `E eff`, and similar cases should not look like ordinary prose.
- Continue normalizing mojibake micro signs before unit/exponent audit.
- Treat caption-like `Figure 2f` paragraphs with no nearby image as a
  figure-assembly/PDF-diagnostics task, not as a citation-linking task.

## 020_meine_0039_75458d8a00.html - meine_0039_75458d8a00

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0039_75458d8a00\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0039_75458d8a00\_z2m_stages\02.en.polish.html`

### What Improved

- Unicode author names with mixed affiliation markers are now recognized as
  front matter: `Jan Krhut,1,2`, `Marcel Gärtner`, `Radek Sýkora`,
  `Libor Luňáček`, `Katarína Zvarová5`, `Peter Zvara2,6`.
- Author affiliation markers are no longer linked to bibliography references.
- Body numeric citations remain linked.

### Defects Not Fixed From Raw

- The article has some raw reference-list duplication (`1. 1 Gravas...`,
  `2. 2 Kranse...`) that is not yet normalized in this pass.

### Defects Introduced Or Amplified By Polish

- None detected by the current pair audit after the 2026-05-02 fix.

### Audit Result - 2026-05-02

- Current pair audit for this article reports `defects=0`, `page_links=0`,
  `ref_links=7`, `fig_links=8`, `table_links=1`, `bad_chars=0`.

### Fix Requirements

- Reference-list duplicate visible numbers should be normalized in a later
  bibliography-cleanup pass, but this article is now clean for the reviewed
  polish issues.

## 021_meine_0041_515e781bb6.html - meine_0041_515e781bb6

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0041_515e781bb6\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0041_515e781bb6\_z2m_stages\02.en.polish.html`

### What Improved

- Split page-linked bracket citation lists like `[3, 5]` are recovered as
  `#ref-3` and `#ref-5`.
- The table header word `Matrix` is no longer split as
  `Matr<sup class="z2m-table-fn">ix</sup>`.
- Existing `Table 2` page link is retargeted to `#table-2`.

### Defects Not Fixed From Raw

- The current audit still reports `P60` around a numeric/statistical-looking
  context, but manual inspection suggests the visible `83` in the neonatal coil
  discussion is a real citation. Treat this as audit precision work unless a
  manual review proves otherwise.

### Defects Introduced Or Amplified By Polish

- None confirmed after the 2026-05-02 pass.

### Audit Result - 2026-05-02

- Current pair audit for this article reports `P60=1`, `page_links=0`,
  `ref_links=122`, `fig_links=9`, `table_links=4`, `bad_chars=0`.

### Fix Requirements

- Tighten `P60` so valid high-number citations in medical/imaging prose are not
  reported as statistical false positives.

## 022_meine_0042_05f20a6416.html - meine_0042_05f20a6416

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0042_05f20a6416\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0042_05f20a6416\_z2m_stages\02.en.polish.html`

### What Improved

- Images remain preserved (`4 -> 4`), and existing figure references for
  extracted targets are linked.
- No page-link residue remains.

### Defects Not Fixed From Raw

- Visible `Fig. 1A` has no matching semantic `fig-1` target. Raw appears to
  contain images for the document but not a recoverable `FIGURE 1` caption.

### Defects Introduced Or Amplified By Polish

- None confirmed. The missing `Fig. 1A` target is a raw extraction / figure
  caption discovery problem.

### Audit Result - 2026-05-02

- Current pair audit for this article reports `P61=1`, `page_links=0`,
  `ref_links=5`, `fig_links=3`, `table_links=1`, `bad_chars=0`.

### Fix Requirements

- Future PDF diagnostics should try to associate orphaned image regions with
  visible figure references when the caption label is missing from raw HTML.

## 023_meine_0043_a848e1004f.html - meine_0043_a848e1004f

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0043_a848e1004f\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0043_a848e1004f\_z2m_stages\02.en.polish.html`

### What Improved

- All 109 extracted images are preserved in polish.
- Page links are not present after the current pass.

### Defects Not Fixed From Raw

- This item behaves like an older book/scan/OCR-heavy source, not like the
  normal article set. Raw audit reports `54` defects.
- Remaining issues include OCR front matter, duplicate visible bibliography
  numbers, malformed units, TeX/caption residue, float interruptions, and a
  missing extracted figure warning.

### Defects Introduced Or Amplified By Polish

- Some float-order warnings remain in polish, but the source is noisy enough
  that this should be handled under an OCR/book policy rather than by broad
  normal-article polish rules.

### Audit Result - 2026-05-02

- Current pair audit for this article reports `P01`, `P05`, `P06`, `P12`,
  `P14`, `P22`, `P30`, `P40`, `P62`; `page_links=0`, `ref_links=4`,
  `fig_links=108`, `table_links=34`, `bad_chars=0`.

### Fix Requirements

- Do not tune normal EN polish too aggressively against this source.
- Route OCR/book-like documents to the future OCR-specific polish policy noted
  in the post-vacation plan.

## 024_meine_0045_567d338f68.html - meine_0045_567d338f68

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0045_567d338f68\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0045_567d338f68\_z2m_stages\02.en.polish.html`

### What Improved

- Existing `Table 1` and `Table 2` references are linked to table targets.
- The stale `Fig. 2` page anchor is now unwrapped because no semantic
  `fig-2` target exists. This removes misleading `#page-*` semantic links.
- `page_links` dropped from `1` to `0`.

### Defects Not Fixed From Raw

- No figure targets are created (`polish_fig_ids=0`) even though visible
  `Fig. 1`, `Fig. 2`, and `Fig. 3` references exist.
- Remaining `P30/P40` warnings indicate reading-order interruptions around the
  literature search/method prose.

### Defects Introduced Or Amplified By Polish

- None confirmed after stale page anchors are unwrapped. The main issue is
  missing figure target discovery from raw.

### Audit Result - 2026-05-02

- Current pair audit for this article reports `P30=1`, `P40=1`, `P61=1`,
  `page_links=0`, `ref_links=29`, `fig_links=0`, `table_links=2`,
  `bad_chars=0`.

### Fix Requirements

- Add figure-target recovery for articles where raw has figure images/captions
  but labels are too weak for the current wrapper.
- Float-aware reading-order repair should handle method paragraphs interrupted
  by extracted floats without moving unrelated content.

## 025_meine_0046_17de6ce7f1.html - meine_0046_17de6ce7f1

Raw stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0046_17de6ce7f1\_z2m_stages\01.en.raw.html`

Polish stage:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\meine_0046_17de6ce7f1\_z2m_stages\02.en.polish.html`

### What Improved

- Current pair audit reports no polish defects.
- No image loss, no bad characters, no page links, and no reference-link
  false positives are detected.

### Defects Not Fixed From Raw

- Raw audit still has one `R13`-class warning, but it does not currently surface
  as a polish defect.

### Defects Introduced Or Amplified By Polish

- None detected.

### Audit Result - 2026-05-02

- Current pair audit for this article reports `defects=0`, `page_links=0`,
  `ref_links=0`, `fig_links=0`, `table_links=0`, `bad_chars=0`.

### Fix Requirements

- Keep as a negative-control article for future changes: broad citation,
  figure, and unit repairs should continue to leave it quiet.

## Manual Follow-up 018-025 - 2026-05-02

Review set:
`manual_review_meine_en_polish_inlined_2026-05-02_018_025_final`

Repolish report:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_018_025_after_manual_review_final_2026-05-02.json`

Pair audit:
`md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_018_025_after_manual_review_final_2026-05-02.json`

### Implemented Universal Repairs

- Mojibake normalization now handles common double-encoded UTF-8/Windows
  artifacts before unit and citation repair.
- Page/float sentence repair now accepts long body paragraphs that were falsely
  classified as front matter, and it can merge prose across a run containing
  wrapped floats plus image-only paragraphs.
- Known word-glue cleanup is also applied after float/page-boundary merges, so
  merge-created age forms such as `6year-old` become `6-year-old`.
- Effective-variable typography handles both plain `D eff` and tagged
  `<i>D</i> eff`, rendering them as subscripted `D_eff`.
- Plain negative unit exponents such as `cm-2 s -1`, plus `10-13` before those
  units, are normalized to unit exponent markup.
- Chemical formula fragments such as `ZrAl x O y` are normalized to subscript
  formula markup, and the audit no longer treats already-subscripted formulas
  as roman-suffix word splits.
- Duplicate bare reference-list numbers after generated `z2m-ref-num` spans
  are stripped.

### Article-by-Article Result

- `018_meine_0035_520bdb5064`: fixed the float-run interruption around
  `"The Annunciation" ... permanently displayed...`; current pair audit is
  clean for this article.
- `019_meine_0036_d04b54116e`: fixed mojibake units/dashes, split unit
  exponents, `D_eff` typography, and `ZrAl_xO_y` formula typography. Remaining
  audit findings are `P05` around a likely valid superscript citation near the
  WVTR formula and `P13` for `Figure 2f` without a nearby extracted image.
- `020_meine_0039_75458d8a00`: duplicate visible reference numbers are fixed;
  current pair audit is clean.
- `021_meine_0041_515e781bb6`: fixed `6year-old` and `7 year-old`; remaining
  `P60` appears to be audit precision around a real citation `83`.
- `022_meine_0042_05f20a6416`: no polish-created page links remain. Remaining
  `Fig. 1A` issue is missing figure-target recovery from raw/PDF extraction.
- `023_meine_0043_a848e1004f`: some float and unit noise improved, but this is
  still an OCR/book-like source. Keep it under the future OCR policy rather than
  tuning normal article polish against it.
- `024_meine_0045_567d338f68`: fixed the table/image interruption in `All
  authors independently screened all the retrieved articles...`; remaining issue
  is missing semantic figure targets for visible `Fig. 1`/`Fig. 2`/`Fig. 3`.
- `025_meine_0046_17de6ce7f1`: remains clean and should stay a negative-control
  article for broad polish rules.

### Final Audit Snapshot

- Totals: `raw_img=182`, `polish_img=182`, `page_links=0`, `bad_chars=0`,
  `missing_img=0`.
- Clean in current audit: `018`, `020`, `025`.
- Remaining normal-article work: figure-target recovery for weak/missing figure
  captions; audit precision for valid superscript citations near formulas.
- OCR/book-like remaining work: `023` should be handled by the future OCR
  polish sketch/policy, not by broad normal EN polish rules.

## Post-Follow-up Stage: Orphan Figure Targets - 2026-05-02

Commit:
`006716b Recover orphan EN figure targets`

Processing stage:
`PDF/Marker -> 01.en.raw.html -> 02.en.polish.html`. This stage is still normal
EN polish for born-digital/text-layer sources. It does not change Marker output,
does not run RU translation, and does not write back to Zotero.

Verification reports:

- 7-article control repolish:
  `md_output\new\_quality_audit\repolish_after_orphan_figure_recovery_2026-05-02.json`
- 7-article control audit:
  `md_output\new\_quality_audit\en_polish_pair_audit_after_orphan_figure_recovery_pdfdiag_2026-05-02.json`
- Meine `001-025` repolish:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_001_025_after_orphan_figure_recovery_2026-05-02.json`
- Meine `001-025` pair audit:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_001_025_after_orphan_figure_recovery_2026-05-02.json`

### Problems Fixed At This Stage

- `017_meine_0034_2a6279ac39`: `Figure 4A/Figure 4` now links to a recovered
  semantic target on the nearby Marker figure image.
- `022_meine_0042_05f20a6416`: the missing `Fig. 1A` target is now recovered
  from the orphan `_page_*_Figure_*.jpeg` image and the unlabeled panel legend.
- `024_meine_0045_567d338f68`: safe targets are now recovered for `Fig. 1` and
  `Fig. 2` from the ordered orphan figure-image run.
- The 7-article control set stayed stable: `raw_img=80`, `polish_img=80`,
  `missing_img=0`, `bad_chars=0`.
- Meine `001-025` stayed image-safe: `raw_img=425`, `polish_img=425`,
  `missing_img=0`, `bad_chars=0`.

### Remaining Problems After This Stage

- `017_meine_0034_2a6279ac39`: `Figure 3` still has no safe semantic target.
  The nearby extracted object is a `Picture` artifact rather than a Marker
  `Figure` image, so assigning it in EN polish would be guesswork.
- `024_meine_0045_567d338f68`: `Fig. 3` still has no safe semantic target. The
  next candidate regions are separated by table material and need PDF/raw-region
  diagnostics before assignment.
- `023_meine_0043_a848e1004f` remains OCR/book-like and should stay out of
  normal article-polish tuning.

### Next Processing Stage

The next target is not broader HTML guessing. It should be a PDF/raw-region
diagnostic stage that can decide whether an extracted image region corresponds
to a visible figure reference when the HTML lacks a reliable local caption or
nearby Marker `Figure` image. The resulting decisions can then feed EN polish as
structured hints instead of one-off article heuristics.

## Continuation Analysis - 2026-05-14

### 024_meine_0045_567d338f68 - orphan figure target verification

Automatic checks:

- Current pair audit reports `P61=1` for a visible figure reference without a
  compatible semantic target.
- Current raw audit reports only `R11=1`, so the automated raw audit does not
  describe the figure-target mismatch.

Raw HTML observations:

- `01.en.raw.html` contains visible prose references to `Fig. 1`, `Fig. 2`,
  `Fig. 3`, and `Figs. 4, 5`.
- Raw contains extracted figure images in article order:
  `_page_1_Figure_14.jpeg`, `_page_2_Figure_11.jpeg`,
  `_page_3_Figure_2.jpeg`, `_page_4_Figure_2.jpeg`,
  `_page_4_Figure_10.jpeg`.
- The figure labels are embedded inside the raster images, not exposed as
  adjacent caption text for EN polish to parse.

Polish/current-code observations:

- Current `polish_html_document()` reproduces semantic wrappers only for
  `fig-1`, `fig-2`, and `fig-4`.
- `fig-1` is assigned to `_page_2_Figure_11.jpeg`, whose visible raster label
  is `Fig. 2`.
- `fig-2` is assigned to `_page_3_Figure_2.jpeg`, whose visible raster label is
  `Fig. 3`.
- `fig-4` is assigned to `_page_4_Figure_2.jpeg`, whose visible raster label is
  `Fig. 4`.
- The actual `Fig. 1` raster image (`_page_1_Figure_14.jpeg`) and actual
  `Fig. 5` raster image (`_page_4_Figure_10.jpeg`) remain unwrapped.

Classification:

- First broken layer: Marker/raw extraction, because figure labels are trapped
  inside raster images and are not available as HTML caption text.
- Polish status: current orphan-target recovery introduces/amplifies a semantic
  navigation defect by assigning wrong `fig-*` IDs when it guesses from nearby
  references without reliable local label evidence.
- Primary status: `introduced_by_polish` for wrong semantic targets;
  `needs_pdf_diagnostics` for reliable recovery of all figure targets.

Next action:

- Do not broaden HTML guessing.
- Add a focused regression around this pattern before changing code: multiple
  orphan figure images with raster-only labels and several nearby figure
  references must not receive shifted semantic IDs.
- The conservative production behavior should either leave ambiguous orphan
  images unassigned with an audit warning, or consume structured PDF/raw-region
  hints before assigning `fig-*` targets.

Follow-up implementation:

- Added a focused regression:
  `test_polish_html_document_does_not_shift_orphan_targets_when_refs_outnumber_images`.
- Narrowed ordered orphan-image recovery so it only pairs a run of orphan figure
  images with following missing figure references when the counts match exactly.
- After the guard, current code no longer assigns shifted `fig-1`/`fig-2`
  targets in this article. It keeps only the high-confidence `fig-4` assignment
  to `_page_4_Figure_2.jpeg`, whose raster label is `Fig. 4`.
- `Fig. 1`, `Fig. 2`, `Fig. 3`, and `Fig. 5` remain unresolved and should be
  handled by the future PDF/raw-region diagnostic stage rather than by broader
  HTML guessing.

Verification:

- `python -m pytest -q tests\test_single_file_html.py tests\test_audit_en_polish.py`
  -> `256 passed`.
- `python -m pytest -q tests\test_repolish_en_from_raw.py tests\test_collect_en_polish_review.py tests\test_audit_en_raw.py tests\test_audit_source_language.py tests\test_language_detect.py`
  -> `17 passed`.

### 027_meine_0048_a97baaa72b - table note split verification

Automatic checks:

- Imported-stage raw audit is clean for this article.
- Imported-stage pair audit reports 7 findings, but a current-code preview already
  fixes some stale imported-output issues such as the front-matter DOI split and
  several visible citation/target mismatches.
- The remaining high-confidence current-code structural issue is the table 2 note
  and surrounding paragraph ordering.

Raw HTML observations:

- `01.en.raw.html` has the body sentence split as `...4 scores for measurement`
  before table 2 and `error. In none of the studies...` after the table/figure
  region.
- The table 2 note is complete in raw:
  `*In order to meet a level of evidence, all three criteria have to be met
  (consistency, methodological quality and sample size). Adapted from...`.
- Raw also contains noisy page-linked superscript citations in numeric contexts
  such as `r=0.2 255`, `%28`, and `mL/ s28`; these need separate citation/OCR
  classification and are not the same defect as the table-note split.

PDF observations:

- PDF page 3 confirms that `sample size). Adapted from...` belongs to the table
  note, not to the preceding `measurement error` paragraph.
- PDF page 4 confirms the transrectal-ultrasound numeric strings are values with
  superscript citations, for example `r=0.22` with citation `55`.
- PDF page 9 confirms `%28` and `mL/s28` are valid citation superscripts near
  percent/unit text, so the `P05` signal is at least partly audit precision.

Current-code polish observations:

- `_split_table_note_body_continuations()` splits the table note before
  `size). Adapted...` because of its broad `size/sizes` continuation candidate.
- `_repair_sentence_breaks_around_float_units()` then correctly rejoins
  `measurement` with `error...`, but it also carries the wrongly split note tail
  into that paragraph.

Classification:

- First broken layer: `02.en.polish.html`.
- Root cause: table-note continuation splitting treats `sample size)` inside a
  parenthetical table note as if it were prose continuing the previous body
  paragraph.
- Universal pattern: `size/sizes` table-note split candidates must not fire when
  the candidate is inside an unclosed parenthetical note phrase.

Fix requirements:

- Add a regression where a table note contains
  `(consistency, methodological quality and sample size).`
- Keep the existing positive case where a formula table note is followed by a
  genuine body continuation beginning with `sizes.`
- After code change, repolish and audit this article before moving to the next
  defect family.

Follow-up after current-code repolish:

- The table-note split is fixed in a current-code preview and the current
  repolish/audit no longer reports `P40` or the stale DOI split.
- Remaining `0048` citation/OCR issues include over-absorbed numeric citation
  links: PDF page 4 has `r=0.22` plus citation `55`, while HTML has
  `r=0.2 <a>255</a>`. The same shape appears for `r=0.05` plus citation `55`
  and `r=0.21` plus citation `39`.
- PDF page 9 also confirms `mL/s28` is a valid unit followed by citation `28`,
  while HTML has `mL/ <a>s28)</a>`.
- Classification: first broken layer is raw/OCR for the split text shape, but
  EN polish can safely compensate when a ref link absorbs exactly one decimal
  digit or the `s` in `mL/s` and the remaining suffix is a valid reference
  number.
- Required regression: repair these narrow absorbed-link shapes without
  unlinking legitimate citations near percent or unit text.

Verification after fixes:

- Current repolish/audit for `026-035` removes the `0048` table-note `P40`, DOI
  `P52`, absorbed-letter `P37`, and mismatched-label `P42` findings.
- Remaining `0048` findings are lower-confidence or broader workstreams:
  `P05`/`P60` audit precision around valid superscript citations near units and
  table-note text, `P50` flattened citation inside a table cell, and `P33`
  unresolved table page anchors because this article has no semantic table
  targets yet.

### 031_meine_0057_e9e50c744a - Arkhipov roman-suffix split

Automatic checks:

- Current pair audit reports `P45=1` for `Anton Arkhipo v provided...`.

Raw/polish observations:

- `01.en.raw.html` already contains the correct text:
  `Philip Shiu and Anton Arkhipov provided guidance...`.
- Current `02.en.polish.html` changes that to:
  `Philip Shiu and Anton Arkhipo v provided guidance...`.

Classification:

- First broken layer: `02.en.polish.html`.
- Root cause: the roman-suffix normalization pass splits a surname ending in
  `v`; the later false-split repair did not rejoin it when the next word is
  lowercase prose (`provided`).
- Universal pattern: a capitalized surname split before `v/i/x` after a
  capitalized given name should be rejoined even when the following prose word
  is lowercase.

Fix requirements:

- Add a regression for `Anton Arkhipo v provided`.
- Preserve audit/code guards for normal phrases like `While x-ray-based`.

### 030_meine_0055_2603fc9fe5 - section-link and missing-figure triage

Automatic checks:

- Current pair audit reports `P33=1` for `Section 2)` still pointing to a PDF
  page anchor and `P62=1` for a missing extracted Figure 6 image.

Raw/polish observations:

- Raw contains `Section <a href="#page-4-0">2)</a>` and no section IDs.
- Current polish creates semantic section targets including `id="section-2"`,
  but the split section reference remains a page link because the page-linked
  section-reference parser only accepted a trailing period, not `)`.
- Raw has the Figure 6 caption text, but the image itself was not extracted.
  Current polish correctly creates a `z2m-missing-figure-unit` for `fig-6` and
  links visible `Figure 6` references to it.

Classification:

- `Section 2)` first broken layer: `02.en.polish.html`, because the target
  exists but the split page link was not retargeted.
- Figure 6 first broken layer: Marker/raw extraction, because the visual content
  is absent before polish. The current missing-figure warning is the correct
  conservative behavior.

Fix requirements:

- Extend split section-reference retargeting to allow a trailing `)`.
- Do not try to synthesize the missing Figure 6 image in EN polish.

### 034_meine_0060_3b1d6c9c17 - roman-suffix split and reference-list triage

Automatic checks:

- Current pair audit reports `P01=1` and `P04=1`.

Raw/polish observations:

- Raw contains the author surname `Petrangovskii`; current polish splits it as
  `Petrangovsk ii` in the front matter.
- Raw contains a valid superscript citation range `<sup>1-7</sup>` in the body.
  Current polish leaves it as plain `1-7`.
- The bibliography-like material is embedded in a `ListGroup` without a normal
  `References` heading and begins immediately after a conclusion item. Current
  EN polish therefore does not assign `ref-*` IDs for this article.

Classification:

- `Petrangovskii` first broken layer: `02.en.polish.html`, caused by roman-suffix
  splitting of a surname ending in `ii`.
- `1-7` citation range first broken layer: raw/reference-structure extraction.
  The range cannot be safely linked until the trailing bibliography list is
  recognized as references rather than ordinary list content.

Fix requirements:

- Add a regression for `V. V. Petrangovsk ii` after initials and rejoin it.
- Do not add a one-off reference-list inference for this article; defer the
  no-heading bibliography/list-group case to a separate reference-structure
  workstream.

Verification after fixes:

- Current polish no longer contains `Petrangovsk ii`; it preserves
  `V. V. Petrangovskii`.
- `P04` remains because the trailing bibliography-like list is not recognized
  as a reference section in raw/polish.
- `P01` remains a raw/front-matter audit warning and should be handled together
  with the broader front-matter/reference-structure diagnostics.

### 026-035 current-code audit snapshot

Verification reports:

- Repolish:
  `.tmp_local2\analysis\repolish_meine_026_035_after_petrangovskii_p_end_repair_2026-05-14.json`
- Pair audit:
  `.tmp_local2\analysis\pair_audit_meine_026_035_after_petrangovskii_p_end_repair_2026-05-14.json`

Current totals:

- `raw_img=186`, `polish_img=186`, `missing_img=0`, `bad_chars=0`.
- `ref_links=376`, `fig_links=99`, `table_links=29`, `page_links=48`.
- Remaining audit checks:
  `P01=1`, `P04=1`, `P05=1`, `P33=2`, `P50=1`, `P60=1`, `P61=1`, `P62=1`.

Clean articles in this current-code audit:

- `026_meine_0047_78d5e1f69c`
- `028_meine_0052_ef1533f1d7`
- `029_meine_0054_49ff51e940`
- `032_meine_0058_940c8b16de`
- `033_meine_0059_5c38c8b6f6`
- `035_meine_0062_c320053119`

Problems fixed or removed from current audit in this stage:

- `027_meine_0048_a97baaa72b`: fixed table-note splitting around
  `sample size). Adapted...`; fixed over-absorbed decimal/unit citation links
  such as `r=0.2 <a>255</a>` and `mL/ <a>s28)</a>`.
- `030_meine_0055_2603fc9fe5`: fixed split section links with trailing `)`,
  including `Section 2)`.
- `031_meine_0057_e9e50c744a`: fixed `Anton Arkhipo v provided`; audit no
  longer flags normal `x-ray` text as `P45`.
- `034_meine_0060_3b1d6c9c17`: fixed `Petrangovsk ii`.
- `035_meine_0062_c320053119`: current `P45` around `Sciences v.22` was an
  audit false positive and is no longer reported.

Remaining workstreams:

- `027_meine_0048_a97baaa72b`: `P05` and `P60` are audit precision around valid
  superscript citations near unit/table-note text; `P50` is flattened citations
  inside a table cell; `P33` remains because no semantic table targets are
  created for table captions embedded inside table grids.
- `030_meine_0055_2603fc9fe5`: `P33` remains for `Section 3.5.1`, whose heading
  is embedded in an italic paragraph rather than exposed as a section target.
  `P62` remains a Marker/raw missing-image issue for Figure 6.
- `031_meine_0057_e9e50c744a`: `P61` remains for a textual `Figure 2` reference
  that explicitly cites an external/copyright-constrained image, not an extracted
  figure target.
- `034_meine_0060_3b1d6c9c17`: `P04` remains because citation ranges cannot be
  linked until the no-heading bibliography list is recognized; `P01` remains as
  raw/front-matter diagnostic noise.

Regression:

- `python -m pytest tests\test_single_file_html.py tests\test_audit_en_polish.py -q`
  -> `262 passed`.
- `python -m pytest -q`
  -> `279 passed`.
- Both runs still emit the existing `.pytest_cache` access-denied warning on
  this machine.

### 036_meine_0065_4ae2d0d2b0 - DOI split and duplicate-number audit precision

Automatic checks:

- Current pair audit reports `P52=1` for a DOI split after slash and `P22=1`
  for duplicate visible bibliography number `10`.
- Current raw audit is clean for this article.

Raw/polish observations:

- `01.en.raw.html` contains the compact DOI
  `10.4028/www.scientific.net/AMM.510.163` in front matter and publisher
  metadata.
- Current `02.en.polish.html` rewrites the visible text as
  `10.4028/ www.scientific.net/AMM.510.163` because the URL autolinker wraps the
  internal `www.scientific.net/...` fragment before DOI linking can consume the
  full DOI.
- The `P22` duplicate visible number comes from post-reference DOI-only metadata
  lines beginning with `10.4028...`, not from a duplicated bibliography item.

Classification:

- DOI split first broken layer: `02.en.polish.html`.
- Duplicate-number report first broken layer: audit precision. The relevant
  post-reference blocks are DOI metadata, not reference-list entries.

Fix requirements:

- In URL/DOI autolinking, protect DOI anchors before generic URL linking so DOI
  labels containing `www.` are not split.
- Support bare DOI tokens such as `[10.4028/www.scientific.net/AMM.510.163]`
  without swallowing the surrounding bracket.
- Teach the reference-identity audit to ignore post-reference DOI-only metadata
  blocks when checking duplicate visible bibliography numbers.

### 037_meine_0066_6c8967bd60 - figure caption/image pairing

Automatic checks:

- Current pair audit exposed a `P57` alias/wrapper issue around late figure
  captions and images.

Raw/polish observations:

- Raw contains figure captions and neighboring images, but the polish stage
  could assign the caption alias to the wrong image or close a float before all
  of the image/caption material belonging to the figure.
- Manual raw/polish inspection showed this was not an HTML-output-only issue:
  the pairing logic in EN polish needed stricter adjacency and target checks.

Fix and verification:

- Tightened figure caption/image pairing and alias wrapper handling in
  `single_file_html.py`, including guards for images that can safely receive a
  figure id and captions immediately followed by images.
- Added regression coverage for the repaired pairing path.

## Continuation Analysis 046-075 - 2026-05-14

Batch:

- Reviewed Meine EN-gated positions `046-075`, roots
  `meine_0077_689400c133` through `meine_0128_d0a34eaf10`.
- Source PDFs were absent for manually inspected `meine_0089_be819c099a`,
  `meine_0104_4533bbb6f0`, and `meine_0110_d7da0239e6`, so classification used
  raw HTML plus polished HTML.

Initial automatic reports:

- Language audit:
  `.tmp_local2\analysis\language_audit_meine_046_075_current_2026-05-14.json`
  -> `en=30`, `skipped=0`, `unknown=0`.
- Raw audit:
  `.tmp_local2\analysis\raw_audit_meine_046_075_current_2026-05-14.json`
  -> `raw_sentinels=0`, `page_headers=0`, defects
  `R05=3`, `R08=5`, `R11=16`, `R12=3`, `R13=7`.
- Initial pair audit:
  `.tmp_local2\analysis\pair_audit_meine_046_075_current_2026-05-14.json`
  -> `raw_img=604`, `polish_img=604`, `missing_img=0`, `bad_chars=0`,
  `page_links=73`; remaining checks included
  `P01=4`, `P03=1`, `P04=2`, `P05=2`, `P13=2`, `P14=1`, `P22=2`, `P33=7`,
  `P34=1`, `P36=1`, `P39=4`, `P40=1`, `P42=1`, `P45=1`, `P50=1`, `P59=4`,
  `P60=5`, `P61=4`, `P62=1`.

Manual findings and fixes:

- `meine_0104_4533bbb6f0`: raw/polish showed page anchors in image/subpanel
  references such as `image 5e` and `8j`. EN polish now retargets image/panel
  subfigure page links to the parent figure when that figure target exists.
- `meine_0089_be819c099a`: raw/polish showed an unheaded bibliography after
  `ACKNOWLEDGMENTS`, with reference numbers glued to author initials (`1E. M.`).
  EN polish now detects this unheaded reference list and normalizes glued
  visible reference numbers.
- `meine_0089_be819c099a`: raw/polish also showed `Eq. (3)` pointing to a page
  anchor while the equation body was a standalone text paragraph ending `(3)`.
  EN polish now promotes short text equations with trailing equation numbers to
  `z2m-equation-row` targets and retargets integer/decimal page-linked equation
  references.
- `meine_0089_be819c099a`: the table range `Tables I-III` had the second roman
  token left as a page link. EN polish now retargets table range tails with roman
  labels when the semantic table target exists.
- `meine_0110_d7da0239e6`: raw/polish showed URL footnotes (`3`-`7`) treated as
  ordinary text, which caused nested URL/ref anchors and page-linked OCR footnote
  markers (`onlin e4`, `blin d6`). EN polish now detects URL footnote paragraphs
  with leading page spans/outer anchors, protects them from bibliography
  linkification, rewrites page-linked OCR footnote markers to
  `z2m-footnote-ref`, and detaches long prose tails that had been merged into a
  leading URL footnote paragraph.
- Audit precision was tightened for front-matter metadata/date/address/TOC
  blocks and bracketed numeric citation lists so `P01`/`P60` no longer report
  known false positives from this batch.

Final automatic reports:

- Repolish:
  `.tmp_local2\analysis\repolish_meine_046_075_after_footnote_tail_split_2026-05-14.json`
  -> `articles=30`, `changed=1` on the final tail-split pass, `inlined_images=604`,
  `missing_images=0`.
- Pair audit:
  `.tmp_local2\analysis\pair_audit_meine_046_075_after_footnote_tail_split_2026-05-14.json`
  -> `raw_img=604`, `polish_img=604`, `missing_img=0`, `bad_chars=0`,
  `ref_links=1937`, `fig_links=789`, `table_links=129`, `page_links=18`.
- Remaining checks after this pass:
  `P03=1`, `P04=2`, `P05=2`, `P13=2`, `P14=1`, `P22=2`, `P39=4`, `P40=1`,
  `P42=1`, `P45=1`, `P50=1`, `P59=5`, `P61=4`, `P62=1`.
- Checks removed from this batch by code/audit changes:
  `P01`, `P33`, `P34`, `P36`, and `P60`.
- `meine_0110_d7da0239e6` is now clean in the final pair audit.

Remaining workstreams:

- `P39`: multi-image/multi-caption float wrapping remains in
  `meine_0088`, `meine_0091`, `meine_0114`, and `meine_0127`.
- `P59/P61`: mixed numeric citation false positives vs real non-citation links
  need article-level triage before a broad citation-rule change.
- `P62`: `meine_0122_7dc83f89b2` still has a missing extracted image warning;
  classify against source PDF when available.

Regression:

- `python -m pytest tests\test_single_file_html.py tests\test_audit_en_polish.py -q`
  -> `275 passed`.
- `python -m pytest -q`
  -> `292 passed`.
- Both runs still emit the existing `.pytest_cache` access-denied warning on
  this machine.

## Continuation Analysis 076-082 - 2026-05-14

Batch:

- The current Meine EN-gated review index contains `82` articles total, so after
  position `075` only positions `076-082` remained for this pass, not a full
  30-article block.
- Reviewed roots:
  `meine_0129_09858ae6b9`, `meine_0132_b3e2cea77b`,
  `meine_0133_b3bf023ca8`, `meine_0134_edd06dc6d2`,
  `meine_0138_686dec2e12`, `meine_0139_765be5625a`,
  `meine_0140_7b0ca9bc57`.
- Local `00.source.pdf` files were absent beside these stages, so manual
  classification used raw HTML plus polished HTML.

Initial automatic reports:

- Repolish:
  `.tmp_local2\analysis\repolish_meine_076_082_current_2026-05-14.json`
  -> `articles=7`, `changed=7`, `inlined_images=195`, `missing_images=0`.
- Language audit:
  `.tmp_local2\analysis\language_audit_meine_076_082_current_2026-05-14.json`
  -> `en=7`, `skipped=0`, `unknown=0`.
- Raw audit:
  `.tmp_local2\analysis\raw_audit_meine_076_082_current_2026-05-14.json`
  -> `raw_sentinels=0`, `page_headers=0`, defects
  `R05=1`, `R08=1`, `R11=3`, `R13=2`.
- Initial pair audit:
  `.tmp_local2\analysis\pair_audit_meine_076_082_current_2026-05-14.json`
  -> `raw_img=195`, `polish_img=195`, `missing_img=0`, `bad_chars=106`,
  `page_links=16`; checks `P05=1`, `P22=1`, `P33=2`, `P34=1`, `P35=1`,
  `P37=1`, `P39=1`, `P45=1`, `P50=1`, `P62=1`.

Manual findings and fixes:

- `meine_0129_09858ae6b9`: raw/polish showed OCR page-anchor citation glue:
  `W <a>M11</a><a>,19</a>`, `i <a>n20.</a>`, and `(dPCA <a>)20</a>`.
  EN polish now joins the split word/abbreviation and retargets the citation
  numbers to `#ref-*` inside superscripts.
- `meine_0138_686dec2e12`: raw/polish showed a split bracket citation
  `[26-29]` leaving an extra closing `</a>`. EN polish now removes double-closed
  reference anchors after citation reconstruction.
- `meine_0138_686dec2e12`: page anchors around decimal semantic references such
  as `Fig. 6.1` and `Tables 6.1 and 6.2` were stale PDF navigation, not valid
  semantic targets. EN polish now unwraps decimal figure/table page links when
  no matching `fig-6-1` or `table-6-1` style target exists.
- `meine_0140_7b0ca9bc57`: raw/polish showed the OCR surname split
  `Kuznietso v`. Added a conservative known-word repair to restore
  `Kuznietsov`.
- Audit precision was tightened:
  `P05` no longer treats a truncated `phase` window as `pH`;
  `P22` ignores numbered `section-*` headings after a references block; and
  `P50` ignores OCR-spaced years such as `et al . 1 978`.

Final automatic reports:

- Repolish:
  `.tmp_local2\analysis\repolish_meine_076_082_after_decimal_table_tail_fix_2026-05-14.json`
  -> `articles=7`, final pass `changed=1`, `inlined_images=195`,
  `missing_images=0`.
- Language audit:
  `.tmp_local2\analysis\language_audit_meine_076_082_final_2026-05-14.json`
  -> `en=7`, `skipped=0`, `unknown=0`.
- Raw audit:
  `.tmp_local2\analysis\raw_audit_meine_076_082_final_2026-05-14.json`
  -> unchanged raw defects `R05=1`, `R08=1`, `R11=3`, `R13=2`.
- Pair audit:
  `.tmp_local2\analysis\pair_audit_meine_076_082_after_decimal_table_tail_fix_2026-05-14.json`
  -> `raw_img=195`, `polish_img=195`, `missing_img=0`, `ref_links=537`,
  `fig_links=162`, `table_links=66`, `page_links=0`, `bad_chars=106`.
- Remaining checks after this pass:
  `P35=1`, `P39=1`, `P62=1`.
- Checks removed from this batch by code/audit changes:
  `P05`, `P22`, `P33`, `P34`, `P37`, `P45`, and `P50`.
- `meine_0129_09858ae6b9`, `meine_0132_b3e2cea77b`,
  `meine_0134_edd06dc6d2`, `meine_0139_765be5625a`, and
  `meine_0140_7b0ca9bc57` are now clean in the final pair audit.

Remaining workstreams:

- `meine_0133_b3bf023ca8`: old book OCR quality remains poor, with visible
  replacement characters (`P35`) and decimal figure-series wrapping around
  `Fig. 8.x` (`P39`). This should be handled as a larger raw/OCR plus decimal
  figure-target workstream, not a manual HTML edit.
- `meine_0138_686dec2e12`: `P62` remains because the polished HTML explicitly
  reports a missing extracted `Figure 6` image. Classify against source PDF when
  available.

Regression:

- Targeted citation/page-link/audit regressions passed during the pass.
- `python -m pytest -q` -> `298 passed`.
- The run still emits the existing `.pytest_cache` access-denied warning on
  this machine.

## Full 001-082 Repass With Zotero PDFs - 2026-05-15

Scope and method:

- Repeated the pass over all `82` imported Meine articles from
  `review_runs\imported_from_zoteropdf2md_2026-05-14`.
- Followed the repository methodology: automatic repolish, language audit, raw
  audit, pair audit, then manual raw-vs-polish inspection for every article.
- Used Zotero Meine PDF candidates for PDF-aware diagnostics where available.
  The final PDF map covered `81/82` articles; only
  `meine_0133_b3bf023ca8` still has no mapped source PDF.
- No generated HTML was hand-edited. Fixes were made in polish/audit code and
  verified by regenerating `_z2m_stages\02.en.polish.html`.

Automatic reports:

- Article list:
  `.tmp_local2\analysis\meine_001_082_articles_full_repass_2026-05-15.txt`.
- Manual dossiers:
  `.tmp_local2\analysis\meine_001_082_full_repass_dossiers_2026-05-15.md`.
- Zotero PDF map:
  `.tmp_local2\analysis\meine_001_082_zotero_pdf_map_best_2026-05-15.json`.
- Final repolish:
  `.tmp_local2\analysis\repolish_meine_001_082_after_roman_email_halevi2_fixes_2026-05-15.json`
  -> `article_count=82`, final pass `changed_count=1`,
  `inlined_image_count=1726`, `missing_image_count=0`.
- Language audit:
  `.tmp_local2\analysis\language_audit_meine_001_082_full_repass_current_2026-05-15.json`
  -> `en=80`, `de=2`, `unknown=0`; the German articles are
  `meine_0013_a6269b65e9` and `meine_0030_7ddd815634`.
- Raw audit:
  `.tmp_local2\analysis\raw_audit_meine_001_082_full_repass_current_2026-05-15.json`
  -> `bytes=12163282`, `img_tags=1726`, `figure_labels=2293`,
  `table_labels=625`, `page_headers=0`, `raw_sentinels=0`; article-level
  raw defect counts `R05=7`, `R08=12`, `R11=43`, `R12=6`, `R13=20`.
- Final PDF-aware pair audit:
  `.tmp_local2\analysis\pair_audit_meine_001_082_final_pdfmap_2026-05-15.json`
  -> `article_count=82`, clean articles `51`, residual articles `31`,
  `raw_img_tags=1726`, `polish_img_tags=1726`, `polish_ref_links=5428`,
  `polish_fig_links=1733`, `polish_table_links=336`,
  `polish_page_links=108`, `polish_replacement_chars=106`,
  `polish_missing_local_images=0`, `source_pdf_present=81`,
  `pdf_text_chars=7091634`.
- Final residual pair checks:
  `P01=1`, `P03=1`, `P04=3`, `P05=8`, `P06=1`, `P12=1`, `P13=4`,
  `P14=4`, `P22=3`, `P24=1`, `P33=3`, `P35=1`, `P39=8`, `P40=1`,
  `P42=1`, `P49=1`, `P50=3`, `P53=1`, `P54=1`, `P57=1`, `P59=6`,
  `P60=1`, `P61=7`, `P62=5`.

Code and audit changes from this full pass:

- `scripts/audit_en_polish.py` now accepts `--pdf-map` and can attach
  PDF diagnostics from the Zotero candidate map instead of requiring a local
  `00.source.pdf` beside every stage.
- Added `P64` to the recent-manual-defect blind-spot list for split e-mail
  local parts.
- Tightened `P45` so bibliography strings like journal volume `v. 13` do not
  count as broken roman-suffix words.
- `src/zoteropdf2md/single_file_html.py` now repairs the specific repeated
  roman-suffix cases found manually:
  `NHP s41` -> `NHPs<sup>41</sup>`,
  `Abdusalomo v et al.` -> `Abdusalomov et al.`,
  `V. Bulato v. Scientific...` -> `V. Bulatov. Scientific...`,
  `Hale vi suggests/proposed` -> `Halevi suggests/proposed`, and
  `simono v@...` -> `simonov@...`.

Manual article ledger:

| # | article | verdict | note |
|---|---|---|---|
| 001 | `meine_0001_3944c69948` | fixed | `NHP s41` now repairs to `NHPs<sup>41</sup>`. |
| 002 | `meine_0003_b9eaf6e854` | fixed | `Abdusalomo v et al.` now repairs to `Abdusalomov et al.`. |
| 003 | `meine_0004_a4cb70ccef` | clean | No manual polish regression found. |
| 004 | `meine_0011_33cd7b163e` | residual | `P49/P57`: table link plus figure wrapper/target issue. |
| 005 | `meine_0012_68ff614900` | clean | No manual polish regression found. |
| 006 | `meine_0013_a6269b65e9` | language gate | German source; do not use as EN polish evidence. |
| 007 | `meine_0014_10ec76f1a8` | clean | No manual polish regression found. |
| 008 | `meine_0015_be8f26bb9b` | fixed | `V. Bulato v.` now repairs to `V. Bulatov.`. |
| 009 | `meine_0016_21f99425d5` | residual | `P13/P39/P59`: thesis list/table/figure extraction. |
| 010 | `meine_0017_7ef4a4f872` | clean | No manual polish regression found. |
| 011 | `meine_0020_1d46c89d76` | clean | No manual polish regression found. |
| 012 | `meine_0024_69ad5170a0` | clean | No manual polish regression found. |
| 013 | `meine_0027_4a8785387f` | clean | Front-matter roman/affiliation repair still holds. |
| 014 | `meine_0029_ddf58debe6` | clean | No manual polish regression found. |
| 015 | `meine_0030_7ddd815634` | language gate | German/OCR book; residuals are not EN-polish evidence. |
| 016 | `meine_0031_45c7a0c4d9` | residual | `P14`: figure target/caption mismatch. |
| 017 | `meine_0034_2a6279ac39` | residual | `P61/P62`: missing figure/target warning. |
| 018 | `meine_0035_520bdb5064` | clean | No manual polish regression found. |
| 019 | `meine_0036_d04b54116e` | residual | `P05/P13`: figure/citation context remains ambiguous. |
| 020 | `meine_0039_75458d8a00` | clean | No manual polish regression found. |
| 021 | `meine_0041_515e781bb6` | clean | No manual polish regression found. |
| 022 | `meine_0042_05f20a6416` | clean | Older OCR quality, but polish does not worsen it. |
| 023 | `meine_0043_a848e1004f` | residual | `P05/P12/P14/P22/P62`: raw/Marker/book extraction. |
| 024 | `meine_0045_567d338f68` | residual | `P61`: figure target recovery still incomplete. |
| 025 | `meine_0046_17de6ce7f1` | clean | No manual polish regression found. |
| 026 | `meine_0047_78d5e1f69c` | clean | Watch front-matter/body paragraph classification. |
| 027 | `meine_0048_a97baaa72b` | residual | `P05/P33/P50/P60`: page/citation/table context. |
| 028 | `meine_0052_ef1533f1d7` | clean | No manual polish regression found. |
| 029 | `meine_0054_49ff51e940` | clean | OCR imperfect, but polish does not worsen it. |
| 030 | `meine_0055_2603fc9fe5` | residual | `P33/P62`: missing figure/page-link context. |
| 031 | `meine_0057_e9e50c744a` | residual | `P59/P61`: likely dLight false positive plus figure target. |
| 032 | `meine_0058_940c8b16de` | clean | No manual polish regression found. |
| 033 | `meine_0059_5c38c8b6f6` | clean | No manual polish regression found. |
| 034 | `meine_0060_3b1d6c9c17` | residual | `P04`: plain numeric citations remain unlinked. |
| 035 | `meine_0062_c320053119` | clean | No manual polish regression found. |
| 036 | `meine_0065_4ae2d0d2b0` | clean | No manual polish regression found. |
| 037 | `meine_0066_6c8967bd60` | residual | `P14/P39`: figure wrapper/target context. |
| 038 | `meine_0067_43913dc61b` | residual | `P39/P50`: figure/table extraction context. |
| 039 | `meine_0068_76f918fd36` | residual | `P24/P33`: PDF end-section order plus page links. |
| 040 | `meine_0069_7e5793c56a` | clean | No manual polish regression found. |
| 041 | `meine_0071_64e1cd9668` | residual/audit | `P01`: book print-line boilerplate, likely audit precision. |
| 042 | `meine_0072_05920f8331` | clean | No manual polish regression found. |
| 043 | `meine_0073_ff16051f77` | clean | No manual polish regression found. |
| 044 | `meine_0074_de2d3d07e4` | clean | No manual polish regression found. |
| 045 | `meine_0076_d26777905f` | clean | No manual polish regression found. |
| 046 | `meine_0077_689400c133` | residual | `P03/P04`: citation/list density in raw context. |
| 047 | `meine_0081_116f4112ad` | clean | No manual polish regression found. |
| 048 | `meine_0082_ea4293c5ba` | residual/audit | `P05`: old numeric phrase context, likely false positive. |
| 049 | `meine_0083_c766fd3388` | clean | No manual polish regression found. |
| 050 | `meine_0086_6ed92a65fa` | residual | `P04`: RSC accepted-manuscript line-number/citation context. |
| 051 | `meine_0088_9ee61053c9` | residual | `P39`: external figure caption/wrapper context. |
| 052 | `meine_0089_be819c099a` | residual | `P59`: numeric citations in prose remain ambiguous. |
| 053 | `meine_0090_f9583a0fd3` | partial fixed | `Halevi` repaired; residual thesis/table/list `P05/P22/P13/P40/P50`. |
| 054 | `meine_0091_38079470c9` | residual | `P39/P61`: patent figure image/run context. |
| 055 | `meine_0096_44b5fb52f5` | clean | No manual polish regression found. |
| 056 | `meine_0097_8b3b2a7071` | clean | No manual polish regression found. |
| 057 | `meine_0098_a0a5ce19d0` | clean | No manual polish regression found. |
| 058 | `meine_0099_f64b4f7670` | residual | `P05/P42`: citation identity/number context. |
| 059 | `meine_0101_b335da079c` | clean | No manual polish regression found. |
| 060 | `meine_0102_d3de54f14d` | clean | No manual polish regression found. |
| 061 | `meine_0104_4533bbb6f0` | clean | No manual polish regression found. |
| 062 | `meine_0105_94913746ed` | clean | No manual polish regression found. |
| 063 | `meine_0107_ca7c762afc` | clean | No manual polish regression found. |
| 064 | `meine_0109_9d362effa4` | clean | No manual polish regression found. |
| 065 | `meine_0110_d7da0239e6` | clean | No manual polish regression found. |
| 066 | `meine_0114_596913ccaf` | residual | `P13/P39/P59`: thesis/list/figure extraction. |
| 067 | `meine_0117_a82555f407` | residual | `P05/P61`: RSC line numbers plus figure target. |
| 068 | `meine_0119_b39521e56d` | clean | No manual polish regression found. |
| 069 | `meine_0120_132c43321f` | clean | No manual polish regression found. |
| 070 | `meine_0121_bfa6ddf741` | residual | `P14/P59/P61`: citation/figure target context. |
| 071 | `meine_0122_7dc83f89b2` | residual | `P22/P59/P62`: abstracts collection plus missing Figure 1. |
| 072 | `meine_0123_7efa824c9f` | clean | No manual polish regression found. |
| 073 | `meine_0126_88b178ad3d` | clean | No manual polish regression found. |
| 074 | `meine_0127_8197240fe4` | residual | `P39/P61`: book scan, locked-page boilerplate, figure target. |
| 075 | `meine_0128_d0a34eaf10` | clean | No manual polish regression found. |
| 076 | `meine_0129_09858ae6b9` | clean | Prior citation/page-link fixes still hold. |
| 077 | `meine_0132_b3e2cea77b` | clean | No manual polish regression found. |
| 078 | `meine_0133_b3bf023ca8` | residual | `P35/P39`: old OCR/book, no mapped source PDF. |
| 079 | `meine_0134_edd06dc6d2` | fixed | Split e-mail `simono v@...` now repairs to `simonov@...`. |
| 080 | `meine_0138_686dec2e12` | residual | `P62`: missing extracted Figure 6 warning remains. |
| 081 | `meine_0139_765be5625a` | clean | No manual polish regression found. |
| 082 | `meine_0140_7b0ca9bc57` | clean | Prior surname/citation fixes still hold. |

Remaining workstreams after the full repass:

- Figure wrapper and semantic target completeness: `P39/P61/P62`, especially
  theses, patents, books, and abstract collections.
- Table/list extraction: `P13/P50`, mostly raw Marker structure rather than
  polish-only text repair.
- Numeric citation versus line-number ambiguity: `P04/P05/P59/P60`.
- PDF section-order diagnostic: `P24` on `meine_0068_76f918fd36`.
- Raw OCR/language-gate cleanup: `P35` and the two German articles should stay
  out of normal EN-polish tuning unless a separate OCR/language workflow is
  started.

Regression:

- `python -m pytest -q tests\test_single_file_html.py tests\test_audit_en_polish.py`
  -> `287 passed`.
- `python -m pytest -q` -> `304 passed`.
- The run still emits the existing `.pytest_cache` access-denied warning on
  this machine.

## Five-at-a-time full-text blind-spot pass, batch 001-005 - 2026-05-15

Method: read the complete polished text for each article, compare against the
current audit output, and add scanner rules only for high-confidence defect
families seen manually. Generated HTML was not edited.

Articles:

| # | article | previous audit | manual blind spots added to scan |
|---|---|---|---|
| 001 | `meine_0001_3944c69948` | clean | `considerationsincluding`, lost-ff words, corrupted `Me-mail`/boxed e-mail labels, body sentences interrupted by Box/Figures, runaway repeated `slow`/deactivation text, reference `Biobeha v. Rev.`, OCR `neabling`. |
| 002 | `meine_0003_b9eaf6e854` | clean | `timeconsuming`, `Refreshabletactile`, `displaycan`, reference-title `Segmentaion`, author-marker glue like `100 and`. |
| 003 | `meine_0004_a4cb70ccef` | clean | `inital`, `simpification`, `patients,were`, `iournal.pone`, malformed p-values / flow-rate notation, `health male volunteer`. |
| 004 | `meine_0011_33cd7b163e` | `P49/P57` | Added missed OCR/spacing families: `systometry`, `urflowmetry`, `staffmember(s)`, `validtation`, `seperable`, `Wherev 2`, `pngpng`. Existing `P49/P57` still apply. |
| 005 | `meine_0012_68ff614900` | clean | `timeconsuming`, `da Vinci1Si`, `urtheral`, `nervesparing`, `prostatectomyDeltaVV`, `0.999 0995`, and table-note/body merge after `Positive value = ... decreased symptoms`. |

New audit checks:

- `P65`: runaway repeated word/fragment.
- `P66`: common lost-ligature OCR words.
- `P67`: known joined words and missing separators.
- `P68`: body sentence interrupted by float material.
- `P69`: corrupted e-mail label marker.
- `P70`: reference abbreviation split before roman-like `v`.
- `P71`: known OCR token/phrase residue.
- `P72`: table note merged into following body prose.
- `P73`: author-line affiliation/ORCID marker glued as `100`.

Report:

- `.tmp_local2/analysis/pair_audit_meine_001_005_fulltext_blindspots_2026-05-15.json`
- Real batch result after scanner expansion: `P65=1`, `P66=1`,
  `P67=5`, `P68=1`, `P69=1`, `P70=1`, `P71=5`, `P72=1`,
  `P73=1`, plus existing `P49=1`, `P57=1`.

## Five-at-a-time full-text blind-spot pass, batch 006-010 - 2026-05-15

Method: same as batch 001-005. The complete polished block text was reviewed
for `meine_0013` through `meine_0017`; the scanner was then expanded for
defect families that were visible manually but absent from the initial report.

Articles:

| # | article | previous audit | manual blind spots added to scan |
|---|---|---|---|
| 006 | `meine_0013_a6269b65e9` | clean | German article reached the EN-polish pass; lowercase roman-suffix splits such as `effekt iv`, `retrospekt iv`, `qualitat iv`. |
| 007 | `meine_0014_10ec76f1a8` | clean | No high-confidence conversion defect beyond simple/flat source text. |
| 008 | `meine_0015_be8f26bb9b` | clean | ACM web/PDF front matter residue, visible malformed URL label `hps://...`, runaway `\@ifnextchar` TeX macro, DOI merged into first body sentence, joined words such as `touchinteraction`, `realworld`, `off-theshelf`, and detached accent names such as `Bezi'er`. |
| 009 | `meine_0016_21f99425d5` | `P13/P39/P59` | Existing figure/list/citation warnings still apply. Added `twodimensional`, thesis OCR tokens (`Examing`, `Parametres`, `Uroflowmetery`, `APPEND ix`, `INTEL i LIGENT`) and a table/list block that swallows `3.8 Data Acquisition` / `3.9 Criteria for Use of Data`. |
| 010 | `meine_0017_7ef4a4f872` | clean | Detached accent in `Neumuller`; many intra-word spacing residues such as `ob je ct s w ould`, `safe ty c oncerns`, `incl ude`, `expressi ve ness`, `straightfo rw ard`. |

Scanner changes:

- `P36` now also catches malformed visible URL labels inside otherwise valid
  URL anchors, e.g. `hps://dl.acm.org/...`.
- `P53` German-source hints now include the Springer guideline pattern
  (`Leitthema`, `Deutsche Leitlinien`, `Zusammenfassung`, `Urologe`, etc.).
- `P67` joined-word coverage now includes the tactile-relief/uroflow batch
  terms (`touchinteraction`, `realworld`, `off-theshelf`,
  `state-ofthe-art`, `numbergestures`, `voicecommands`, `twodimensional`).
- `P71` OCR-token coverage now includes thesis/list residues such as
  `APPEND ix`, `INTEL i LIGENT`, `Uroflowmetery`, `Examing`,
  `Parametres`, `Rewiev`, and `qualitat iv`.
- `P74`: runaway LaTeX macro expansion.
- `P75`: DOI metadata merged into following body prose.
- `P76`: detached accent mark inside a word/name.
- `P77`: table/list block absorbs following section prose.
- `P78`: known intra-word spacing residues.

Report:

- `.tmp_local2/analysis/pair_audit_meine_006_010_fulltext_blindspots_2026-05-15.json`
- Real batch result after scanner expansion: `P36=1`, `P53=1`,
  `P67=2`, `P71=2`, `P74=1`, `P75=1`, `P76=2`, `P77=1`,
  `P78=1`, plus existing `P13=1`, `P39=1`, `P59=1`.

## Five-at-a-time full-text blind-spot pass, batch 011-015 - 2026-05-15

Method: same as previous five-at-a-time passes. The complete polished block
text was reviewed for `meine_0020`, `meine_0024`, `meine_0027`,
`meine_0029`, and `meine_0030`; generated HTML was not edited. Scanner
changes were added only for high-confidence defects visible manually but absent
from the initial audit.

Articles:

| # | article | previous audit | manual blind spots added to scan |
|---|---|---|---|
| 011 | `meine_0020_1d46c89d76` | clean | Joined Creative Commons phrase `theCreative`; figure-panel separator residue such as `d)2.5D`. |
| 012 | `meine_0024_69ad5170a0` | `P76/P78` | No new scanner family beyond existing detached-accent and intra-word spacing checks. |
| 013 | `meine_0027_4a8785387f` | clean | Front-matter affiliation markers glued to labels (`1Department`, `5Department`) and suspicious institutional e-mail typo `@unfi.it`. |
| 014 | `meine_0029_ddf58debe6` | clean | Uroflow OCR residues (`premicturtion`, `Qavg and Omax`, `Vol ofmoved`, `Nusssenblatt`), body page headers such as `FRANCO ET AL. | 1915`, and severely scrambled table text such as `nales 5 ted Q a rates`. |
| 015 | `meine_0030_7ddd815634` | `P05/P06/P53/P54` | German book/OCR material is already correctly gated by non-English and roman-split checks; no German-specific generated-HTML edit or narrow polish fix was added. |

Scanner changes:

- `P67` joined-word/separator coverage now includes `theCreative` and
  figure-panel residue such as `d)2.5D`.
- `P71` OCR-token coverage now includes uroflow/table residues such as
  `premicturtion`, `Qavg and Omax`, `Vol ofmoved`, and `Nusssenblatt`.
- `P79`: front-matter affiliation number glued to `Department`.
- `P80`: suspicious institution-specific e-mail domain typo, currently
  `@unfi.it`.
- `P81`: PDF page header/footer left as body prose.
- `P82`: table block with heavily OCR-scrambled column headers/data.

Report:

- `.tmp_local2/analysis/pair_audit_meine_011_015_fulltext_blindspots_2026-05-15.json`
- Real batch result after scanner expansion: `P67=1`, `P71=1`,
  `P76=1`, `P78=1`, `P79=1`, `P80=1`, `P81=1`, `P82=1`,
  plus existing `P05=1`, `P06=1`, `P53=1`, `P54=1`.

## Five-at-a-time full-text blind-spot pass, batch 016-020 - 2026-05-15

Method: same five-at-a-time full-text pass. The complete polished text was
reviewed for `meine_0031`, `meine_0034`, `meine_0035`, `meine_0036`, and
`meine_0039`; generated HTML was not edited. Console mojibake was checked
against UTF-8 snippets before adding rules.

Articles:

| # | article | previous audit | manual blind spots added to scan |
|---|---|---|---|
| 016 | `meine_0031_45c7a0c4d9` | `P14/P76` | Sentence/section interruption around `Despite the intensive investigation of ... adults and older children`; line-break/OCR residues such as `sys- tem`, `temprature`, `childrean`. |
| 017 | `meine_0034_2a6279ac39` | `P61/P62/P67` | Escaped footnote superscripts (`& lt;sup>2`, `& lt;sup>3`), figure/footnote interruption of `printed on swell paper to ... form a tactile rendering`, reference/backmatter interleave, `Beha v. Res. Methods`, and joined reference/copyright residues (`Perceptionof`, `Descriptionsfor`, `openaccess`). |
| 018 | `meine_0035_520bdb5064` | `P67` | `cognitive iter`, `threedimensional`, `basrelief`, and sentence interruption around `in the (hypothetic)` followed by figure blocks before `3D space`. |
| 019 | `meine_0036_d04b54116e` | `P05/P13/P66` | Lost-ligature/OCR family expanded for Nature references (`fexible`, `fbers`, `flm`, `biofuid`, `difusion`, `coefcient`, `galss`, etc.); `I mplantable`, `ulimate`, `Three-dimensioanl`; interruption `mul- ... timodal` with page header material. |
| 020 | `meine_0039_75458d8a00` | clean | Split e-mail local-part `jan. krhut@fno.cz`, joined uroflow terms (`UFrecorded`, `SUFestimated`, `SUFdetermined`), and duplicated phrase `documents that that intensity`. |

Scanner changes:

- `P66` now covers lost `ff`/`fi`/`fl` ligature residue, not only `ff`.
- `P67` joined-word coverage now includes `Perceptionof`,
  `Descriptionsfor`, `openaccess`, `basrelief`, `threedimensional`,
  `UFrecorded`, `SUFestimated`, and `SUFdetermined`.
- `P70` reference roman-split coverage now includes `Beha v. Res. Methods`.
- `P71` OCR-token coverage now includes `sys- tem`, `temprature`,
  `childrean`, `cognitive iter`, `I mplantable`, `ulimate`,
  `Three-dimensioanl`, and `documents that that intensity`.
- `P83`: body phrase interrupted by figure, footnote, or journal metadata.
- `P84`: escaped footnote superscript markup remains visible.
- `P85`: References interleaved with back-matter sections.
- `P86`: e-mail local-part split after a dot.

Report:

- `.tmp_local2/analysis/pair_audit_meine_016_020_fulltext_blindspots_2026-05-15.json`
- Real batch result after scanner expansion: `P67=3`, `P70=1`,
  `P71=4`, `P83=4`, `P84=1`, `P85=1`, `P86=1`, plus existing
  `P05=1`, `P13=1`, `P14=1`, `P61=1`, `P62=1`, `P66=1`, `P76=1`.

## Five-at-a-time full-text blind-spot pass, batch 021-025 - 2026-05-15

Method: same five-at-a-time full-text pass. The complete polished text was
reviewed for `meine_0041`, `meine_0042`, `meine_0043`, `meine_0045`, and
`meine_0046`; generated HTML was not edited. `meine_0043` is a long
book/OCR import, so the new rule treats it as an OCR-quality/routing problem
rather than a normal article-polish repair.

Articles:

| # | article | previous audit | manual blind spots added to scan |
|---|---|---|---|
| 021 | `meine_0041_515e781bb6` | clean | Body sentence interrupted by affiliation metadata (`MRI is now recommended...` / `with hypoxic ischaemic encephalopathy`), joined MR/reference terms (`MRsafe`, `MRcompatible`, `lung-tohead`, `feed-andsleep`, `readyreckoners`, `injuryassociated`), OCR residues (`aesthesia`, `Magr Reson`, `telsa`), and split domain `www. osh a.europa.eu`. |
| 022 | `meine_0042_05f20a6416` | clean | Old-scan OCR gate for title/abstract/table/reference gibberish such as `LUMBAH I - i`, `The (!I G :. nosis`, `v&me`, `TVRP`, `pleak flow`, `timulus`, `Vesicaf`, `snine`, and `Bvadley`. |
| 023 | `meine_0043_a848e1004f` | `P05/P12/P14/P22/P62` | Confirmed as long book/OCR import; added OCR-quality gate for residual tokens such as `suiprising`, `foriTi`, `stimulus.d/T./Sz`, `elTicacy`, `kcounl/mg prolan`, and `linearmotor S~pole aller`. |
| 024 | `meine_0045_567d338f68` | `P61/P84` | Added OCR-token coverage for meta-analysis/table/back-matter residues including `Mata-Analysis`, `correla ition`, `Retinal Nerve Fiber Laver`, and `Amercian ophthalmological society`. |
| 025 | `meine_0046_17de6ce7f1` | clean | Added one visible OCR residue, `bulbocarnosus`, while keeping the rest of the article as a low-noise control. |

Scanner changes:

- `P67` joined-word coverage now includes MR-safety and reference compounds
  from neonatal MRI material.
- `P71` OCR-token coverage now includes the focused residues found in
  `0041`, `0045`, and `0046`.
- `P83` now catches the neonatal MRI body sentence interrupted by affiliation
  metadata.
- `P87`: old-scan OCR gibberish / OCR-quality gate.
- `P88`: URL domain split by OCR whitespace.

Report:

- `.tmp_local2/analysis/pair_audit_meine_021_025_fulltext_blindspots_2026-05-15.json`
- Real batch result after scanner expansion: `P67=1`, `P71=3`,
  `P83=1`, `P87=2`, `P88=1`, plus existing `P05=1`, `P12=1`,
  `P14=1`, `P22=1`, `P61=1`, `P62=1`, `P84=1`.
