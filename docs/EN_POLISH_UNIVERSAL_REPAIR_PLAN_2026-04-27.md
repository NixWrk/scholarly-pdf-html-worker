# EN Polish Universal Repair Plan 2026-04-27

Purpose: reduce the Round 2.5 article-specific residual defects to a small set
of general repair mechanisms. The goal is to help the current seven articles
locally while avoiding brittle article-specific fixes, and to make the same
mechanisms useful for future papers.

Primary input:

- `docs/MANUAL_EN_POLISH_REVIEW_ROUND2_5_2026-04-27.md`

Related plans and evidence:

- `docs/EN_POLISH_CONSOLIDATED_FIX_PLAN_2026-04-27.md`
- `docs/MANUAL_EN_POLISH_REVIEW_ROUND2_2026-04-27.md`
- `md_output/new/_quality_audit/en_polish_pair_audit_after_repolish_pdfdiag_2026-04-27.json`
- `md_output/new/_quality_audit/en_polish_pair_audit_after_universal_commit6_pdfdiag_2026-04-27.json`

## Implementation Result

The universal repair pass has been implemented in the current working tree and
verified on the seven-article corpus.

Current automated result:

- 7 EN raw/polish pairs audited.
- 80 raw images and 80 polish images.
- 0 missing local images.
- 1021 reference links.
- 268 figure links.
- 24 table links.
- 0 audit defects.

The implementation keeps the same design direction as this plan: conservative
local repairs, protected front matter/footnotes, idempotent bibliography and
float handling, and audit checks for every defect class that was converted into
a repair.

## Design Rules

Every fix should follow these rules:

- No article names, titles, author names, or one-off snippets as production
  conditions.
- Prefer structural predicates over text patches: DOM role, heading class,
  reference-list shape, page-anchor location, figure/table number, paragraph
  continuation state, and neighboring block roles.
- Use confidence tiers:
  - `repair`: high-confidence structural evidence.
  - `warn`: plausible defect but ambiguous repair.
  - `preserve`: low-confidence case; keep content visible.
- Every transform must be idempotent. Running polish twice should not add more
  wrappers, links, or numbering.
- Each repair needs a narrow fixture plus one cross-article regression check.
- Optional PDF text can increase confidence, but HTML-only behavior must remain
  deterministic and safe.
- Audits should detect every class that the repair attempts to fix. A clean
  audit must mean more than "no exceptions".

## Universal Problem Families

| Family | Current local symptoms | Universal solution |
|---|---|---|
| Block role ambiguity | Ahmed split captions, Li footnote text in body, Teo body paragraphs marked front matter | Lightweight block role classifier before destructive rewrites |
| Float fragmentation | Ahmed Figure 8, Li Figure 2, Wang Table III, Teo Table 1 | Float unit assembler plus float-aware continuation repair |
| Reference identity drift | Ahmed missing `ref-58`, Merken `1. [1]` | Bibliography identity model based on visible numbers and continuation rules |
| Citation ambiguity | Teo `Grok 4`, Teo `^{71-73}`, Li footnote `1`, author-year links | Citation tokenizer with protected zones and recovery passes |
| Section order damage | Kaiju `FUNDING/REFERENCES/SUPPLEMENTARY` interleaving | End-section ordering repair using heading spans and terminal region constraints |
| Scientific text damage | Merken oxide suffixes, Schelles units and glued words, Kaiju indexed variables | Scientific text normalizer with context guards |
| Audit blind spots | Clean JSON despite visible defects | Audit expansion that mirrors the repair families |

## Proposed Pass Order

1. Parse and classify DOM blocks.
2. Assemble float units and normalize target wrappers.
3. Repair end-section order in terminal article regions.
4. Normalize bibliography identity.
5. Build protected zones and citation candidates.
6. Link citations and retarget page anchors.
7. Repair float-aware sentence continuations and footnotes.
8. Normalize scientific text, units, formulas, and guarded local variables.
9. Run audit checks that correspond to each pass.

This order is important: references and citations should not be finalized before
front matter, footnotes, floats, and terminal sections are classified.

## Mechanism 1: Block Role Classifier

Need: many defects happen because the pipeline treats all paragraphs as equal.

Create a lightweight role classifier over DOM blocks:

- `front_matter`
- `body`
- `figure_unit`
- `table_unit`
- `figure_caption`
- `table_caption`
- `table_note`
- `page_footnote`
- `bibliography_heading`
- `bibliography_item`
- `terminal_section_heading`
- `terminal_section_body`
- `display_math`
- `suspicious_raw_ocr`

Local wins:

- Teo later body paragraphs stop being protected as front matter.
- Li page footnote text can be separated from body text.
- Ahmed caption fragments can be grouped before citation/reference passes.
- Kaiju terminal sections can be isolated from references.

Guardrails:

- Classifier should output roles and confidence, not immediately rewrite.
- When roles conflict, preserve source order and emit an audit warning.
- Front matter should be bounded by early-page position and known article-start
  patterns, not by generic superscript density alone.

Future-proofing:

- The same classifier gives future articles a shared vocabulary for all later
  passes.
- New journal layouts can add role hints without rewriting citation or unit
  logic.

Regression fixtures:

- Teo-like body paragraph after a table/figure with numeric superscripts must
  remain `body`, not `front_matter`.
- Li-like page-bottom footnote must classify as `page_footnote`.
- A normal author-affiliation block near article start must remain protected.

## Mechanism 2: Float Unit Assembler

Need: figures and tables arrive as separate images, captions, heading fragments,
notes, and sometimes body continuations.

Build one canonical unit:

- `div.z2m-float-unit.z2m-figure-unit#fig-N`
- `div.z2m-float-unit.z2m-table-unit#table-N`

Each unit owns:

- target ID and target highlight;
- image/table content;
- caption/title;
- caption continuations;
- credits and URLs;
- table notes and footnotes;
- missing-image warning if needed.

Local wins:

- Ahmed Figure 8 BioRender URL/continuation becomes one figure caption flow.
- Teo Table 1 note stays with the table.
- Wang Table III behavior is preserved as a regression.
- Li Figure 2 becomes a movable unit for sentence-continuation repair.

Guardrails:

- Assemble only within a local window around a figure/table number or page
  anchor.
- Do not absorb ordinary body paragraphs unless they match caption/note
  continuation signals.
- Preserve all visible text even when confidence is low.
- If an image is delayed or missing, keep the wrapper and add a warning instead
  of dropping the block.

Future-proofing:

- Any future figure/table link can target the same wrapper model.
- The reading-order pass can move whole float units without losing captions or
  notes.

Regression fixtures:

- Ahmed-like `caption -> URL heading -> continuation -> image -> continuation`.
- Teo-like `table note -> table -> body continuation`.
- Existing Wang Table III sentence must remain fixed.

## Mechanism 3: Float-Aware Reading Order Repair

Need: floats should be nearby, but not split the sentence that a human reads.

General rule:

- If a paragraph before a float ends in an incomplete syntactic state and the
  paragraph after the float continues it, move or join the text around the
  float while keeping the float nearby and targetable.

High-confidence incomplete states:

- trailing conjunctions: `and`, `or`, `but`;
- trailing possessive/noun phrase fragments;
- discourse marker alone: `However,`, `Additionally,`, `Therefore,`;
- no terminal punctuation and lowercase continuation after the float;
- PDF text confirms the joined sequence.

Local wins:

- Li Figure 2 no longer splits `Fibers may be... and vary...`.
- Teo Table 1 remains after the completed validation paragraph.
- Wang Table III stays fixed.
- Ahmed full-page figure ordering becomes easier once Figure 8 is one unit.

Guardrails:

- Never move a float across a section heading unless PDF text confirms it.
- Never join across bibliography, footnote, or terminal-section boundaries.
- If the post-float paragraph starts a new sentence with strong punctuation or
  heading-like capitalization, do not join.

Future-proofing:

- This catches future page-break and two-column float interruptions without
  article-specific text.

Regression fixtures:

- Li-like conjunction before figure.
- Wang-like possessive phrase before table.
- Teo-like discourse paragraph before table.
- Negative fixture: a complete sentence before a figure must not be joined.

## Mechanism 4: End-Section Ordering Repair

Need: terminal sections in two-column layouts can interleave with references.

General rule:

- In the terminal article region, classify headings and collect their bodies
  before assigning reference IDs.
- Valid terminal order is usually:
  `ACKNOWLEDGEMENTS/FUNDING/AUTHOR CONTRIBUTIONS/DATA AVAILABILITY`,
  `SUPPLEMENTARY MATERIAL`, then `REFERENCES`.

Local wins:

- Kaiju `FUNDING ... REFERENCES ... SUPPLEMENTARY MATERIAL` can be restored.
- Reference normalization starts from a clean reference section.

Guardrails:

- Apply only near the end of the document after methods/results/body sections.
- Require recognized terminal headings and at least one bibliography item.
- Preserve unknown terminal sections in original relative order and warn.

Future-proofing:

- Future Frontiers/Nature/IEEE terminal layouts get one ordering mechanism.

Regression fixtures:

- Kaiju-like terminal page with references inserted into funding.
- Negative fixture: an earlier body mention of "Supplementary Material" must not
  be treated as the terminal heading.

## Mechanism 5: Bibliography Identity Model

Need: citation correctness depends on stable reference identities, not list
ordinal position.

Build reference identity from:

- visible leading number;
- existing `li` boundaries;
- embedded page anchors;
- DOI/URL/title-like continuation signals;
- gap and duplicate detection.

Local wins:

- Ahmed missing `ref-58` is flagged or repaired instead of silently merging into
  `ref-57`.
- Merken `1. [1]` duplicate prefix is removed or normalized.
- Author-year links can retarget the whole bibliography entry.

Guardrails:

- If visible numbers skip, do not renumber blindly. Preserve and warn unless a
  high-confidence continuation explains the gap.
- Continuation merge requires no leading reference number and continuation-like
  content, or PDF text support.
- A true unnumbered web reference must become its own warning/entry, not
  corrupt the previous numbered entry.

Future-proofing:

- Future split bibliographies, page breaks, and journal-specific bracketed refs
  use the same identity model.

Regression fixtures:

- Ahmed-like continuation after reference 25.
- Ahmed-like missing/unnumbered item between 57 and 59.
- Merken-like `1. [1] Hubel...`.
- Author-year page anchor inside a bibliography item retargets to `#ref-N`.

## Mechanism 6: Citation Tokenizer, Protection, And Recovery

Need: numbers may be citations, model versions, footnote markers, units,
affiliations, table values, or OCR-damaged superscripts.

Separate the work into three stages:

1. Protected zones:
   - front matter and affiliations;
   - page footnotes;
   - unit exponents;
   - dimensions and table metadata;
   - model/version names;
   - true formulas.
2. Citation candidates:
   - numeric superscripts;
   - bracketed numeric citations;
   - author-year citations;
   - citation-like math superscripts;
   - ranges and lists.
3. Recovery:
   - valid ranges link to existing references;
   - `#page-*` anchors inside bibliography entries retarget to `#ref-N`;
   - suspicious OCR forms are warned or repaired only with strong evidence.

Local wins:

- Teo `Grok 4` stays unlinked.
- Teo `^{71-73}`, `^{12}`, `^{74}`, and `134-139` become linkable when not in a
  protected zone.
- Li footnote marker `1` stays a footnote marker.
- Li author-year links remain stable.

Guardrails:

- Valid model/version patterns are protected before numeric linkification.
- Unit exponents never become citations.
- Front-matter protection must be bounded; it cannot suppress real body
  citations later in the document.
- OCR recovery should warn when reference support is weak.

Future-proofing:

- New model names and citation styles can be handled by expanding protection
  and candidate patterns independently.

Regression fixtures:

- `Claude 4 and Grok 4` no links.
- `^{71-73}` in prose links as a citation range.
- `cm^-2` and `um^2` do not link.
- Footnote marker with matching footnote block does not link to `ref-1`.
- Body paragraph after a table still links `134-139`.

## Mechanism 7: Footnote Model

Need: page footnotes are neither bibliography citations nor ordinary body text.

General rule:

- Detect matching page-footnote markers and page-bottom note blocks.
- Render notes as dedicated callouts or a footnote block.
- Protect markers and note bodies from bibliography linkification.

Local wins:

- Li low-tensile-strength marker remains correct.
- Li footnote text moves out of body flow.

Guardrails:

- Extract only when marker and note body are close by page/order evidence.
- Do not extract numbered list items, section headings, or bibliography entries.
- If the note body cannot be confidently associated, leave it visible and warn.

Future-proofing:

- Future page-bottom notes and publisher footnotes share the same model.

Regression fixtures:

- Li-like marker plus note text.
- Negative fixture: reference list item `1.` is not a page footnote.

## Mechanism 8: Scientific Text Normalizer

Need: scientific notation should be readable, but global regexes can break
legitimate formulas.

Subpasses:

- Unit normalization:
  - `uC`, `mC`, `um`, `cm`, `kOhm`, `Ohm`;
  - exponents as `<sup class="z2m-unit-exp">`;
  - compact dimensions and areas.
- Prose-bearing math splitter:
  - split prose such as `(CIC) of` out of math spans;
  - keep only true formula/unit tokens in math.
- Word-boundary repair:
  - high-confidence joins around units and common prose words;
  - audit low-confidence dense joins.
- Chemical formula guard:
  - material-context `HfOx`, `AlOx`, `IrOx` to subscript `x`;
  - no global `x` conversion.
- Equation-context variable repair:
  - derive local indexed variables from nearby display equations;
  - repair immediate explanatory prose only.

Local wins:

- Schelles units improve without turning exponents into references.
- Schelles `Vwater`, `0.04for`, `20nCfor` become flagged/fixed where safe.
- Merken oxide formulas normalize without affecting dimensions.
- Kaiju prose variables match the equation.

Guardrails:

- No global variable rewrites.
- No chemical subscript rewrite without material/oxide context.
- If a dense joined token might be a real technical token, warn instead of
  splitting.
- Preserve display equations unless the issue is clearly a citation-like
  superscript.

Future-proofing:

- Future scientific papers get reusable units/math cleanup while preserving
  domain-specific notation.

Regression fixtures:

- Schelles charge density and CIC sentences.
- Merken oxide formulas and dimensions in the same fixture.
- Kaiju display equation plus explanatory prose.
- Negative fixture: legitimate variable `x` in a dimension or equation remains.

## Mechanism 9: PDF Evidence Adapter

Need: PDF text is often cleaner around captions, terminal sections, and OCR
citations, but cannot be mandatory.

Use PDF text only as evidence:

- confirm caption continuations and panel order;
- confirm terminal section order;
- confirm bibliography continuation vs new entry;
- detect suspicious OCR substitutions near citations;
- restore punctuation when PDF text has clear sentence boundary.

Local wins:

- Ahmed Figure 8 caption can be rebuilt with higher confidence.
- Kaiju terminal order can be confirmed.
- Teo `task. Sec.` and `6,000` can be flagged or repaired with evidence.
- Schelles missing period before `Additionally` can be restored.

Guardrails:

- PDF fallback must be optional and deterministic.
- If PDF text conflicts with DOM or is low quality, emit a diagnostic only.
- Keep repair windows local by page/figure/reference number.

Future-proofing:

- Future PDFs gain diagnostics automatically when `00.source.pdf` is present.

Regression fixtures:

- Synthetic PDF-text strings for decision logic.
- No mandatory PDF extraction in ordinary unit tests.

## Mechanism 10: Audit As Contract

Need: Round 2.5 showed that a clean audit can still hide visible defects.

Add audit classes matching the mechanisms:

- role classifier anomalies:
  - body paragraph marked front matter after the article start;
  - footnote-looking block in body flow.
- float defects:
  - figure/table ID not on wrapper;
  - caption URL split into heading;
  - paragraph ending in conjunction before a float.
- terminal order defects:
  - `REFERENCES` inside funding/supplementary text;
  - terminal headings out of expected order.
- bibliography defects:
  - `ref-N` visible number mismatch;
  - missing visible reference number;
  - duplicate `z2m-ref-num` plus bracketed number;
  - unnumbered item absorbed into previous entry.
- citation defects:
  - unlinked `<sup>` numeric range when references exist;
  - citation-like math superscript;
  - `#page-*` citation into bibliography;
  - model/version number linked as citation.
- scientific text defects:
  - joined unit/prose patterns;
  - prose-bearing math;
  - oxide suffix as italic/superscript `x`;
  - unit exponent linked as citation.

Guardrails:

- Audits should distinguish `error`, `warning`, and `info`.
- Warnings are acceptable for ambiguous future layouts; silent failures are not.
- Every production repair should have an audit that fails before the repair on a
  small fixture.

## Implementation Sequence

1. Audit-first scaffold
   - Add fixture audits for the Round 2.5 blind spots.
   - This prevents green reports from hiding known defects.

2. Block roles and front-matter bounds
   - Fix Teo over-protection before citation recovery, because otherwise valid
     body citations stay suppressed.

3. Float unit assembler
   - Stabilize wrappers, captions, notes, and targets before reading-order
     movement.

4. Bibliography identity model
   - Fix reference targets before expanding citation linkification.

5. Citation tokenizer/protection/recovery
   - Recover Teo ranges and preserve already-fixed `Grok 4` / Li footnote wins.

6. Reading-order and footnote model
   - Use stable roles and float units to repair Li, Kaiju, and table/figure
     continuations.

7. Scientific text normalizer
   - Apply guarded unit, chemical, prose-math, and variable repairs.

8. PDF evidence adapter
   - Add confidence boosts and diagnostics for cases HTML cannot decide alone.

9. Full repolish and review
   - Regenerate all seven current articles.
   - Run the expanded audit.
   - Produce a new self-contained review set.
   - Verify the Round 2.5 checklist again.

## Acceptance Criteria

- No production condition depends on the current article names or exact titles.
- Current local wins are preserved:
  - Teo `Grok 4` is not a citation.
  - Li footnote marker is not `ref-1`.
  - Wang Table III no longer splits `sensor's sizes`.
  - Current image integrity remains 80/80 with no missing local images.
- Open local defects are either repaired or explicitly audited:
  - Ahmed Figure 8 caption and missing reference 58.
  - Kaiju terminal section order and indexed-variable prose.
  - Li Figure 2 sentence and page footnote text.
  - Merken oxide formulas and duplicate bracketed reference prefix.
  - Schelles joined scientific/prose tokens and CIC punctuation.
  - Teo citation ranges/math superscripts/front-matter over-protection.
- Future articles with the same structural patterns receive the same behavior
  without adding article-specific branches.
- Ambiguous future cases remain visible as warnings rather than silent rewrites.
