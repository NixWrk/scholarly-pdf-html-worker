# Meine English Raw/Polish Analysis Plan - 2026-04-29

## Purpose

This document defines the analysis protocol for the English subset of the
Meine full-library run:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop`

The goal is not to manually review every generated HTML equally. The goal is to
separate defects by origin and decide which fixes are universal enough for the
EN raw -> EN polish pipeline:

- PDF/Marker defects that EN polish should repair.
- PDF/Marker defects that EN polish cannot safely repair without additional PDF
  evidence.
- Defects that EN polish failed to repair.
- Defects introduced by EN polish itself.
- Automated-audit false positives.
- Stable clean cases that must remain clean after future changes.

The most important outputs are:

1. A prioritized list of universal fixes.
2. A list of regression fixtures before implementation.
3. A sharper audit signal: which checks correctly find real problems, and which
   checks need tuning.

## Source Artifacts

Language audit:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/_quality_audit/source_language_audit_2026-04-29.json`

Raw-stage audit:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/_quality_audit/en_raw_audit_2026-04-29.json`

Raw/polish pair audit:

`md_output/meine_full_library_en_polish_2026-04-28_single_loop/_quality_audit/en_polish_pair_audit_2026-04-29.json`

Per-article stage files:

- `.../<alias>/_z2m_stages/01.en.raw.html`
- `.../<alias>/_z2m_stages/02.en.polish.html`
- source PDF path from `source_language_audit_2026-04-29.json`

## Corpus Boundary

Only the English subset is in scope for EN-polish quality analysis.

Current language split:

| Language class | Count | Action |
| --- | ---: | --- |
| `en` | 82 | Analyze for EN raw/polish quality. |
| `ru` | 57 | Exclude from EN-polish analysis; language gate should quarantine. |
| `mixed` | 1 | Exclude from EN-polish analysis; inspect only as language-gate case. |
| `unknown` | 1 | Exclude from EN-polish analysis; inspect only as language-gate case. |

The `ru`, `mixed`, and `unknown` files are useful for validating the source
language gate, but they must not drive EN-polish repair logic.

## Current Automated Signal

For the 82 detected-English documents:

| Signal group | Count |
| --- | ---: |
| English articles with raw-audit findings | 58 / 82 |
| English articles with polish residual findings | 46 / 82 |
| Findings in both raw and polish audits | 32 |
| Raw findings only | 26 |
| Polish findings only | 14 |
| Clean in both audits | 10 |

This means polish improves the corpus but does not fully repair it. It also
means some checks appear only after polish, which is the highest-risk category
for regressions introduced by our code.

### English Raw Findings

| ID | Count | Meaning |
| --- | ---: | --- |
| `R11` | 43 | Broken hyphenated line joins in prose/table cells. |
| `R13` | 20 | Suspicious all-caps figure/table text inside headings. |
| `R08` | 12 | Glued roman/table footnote suffixes. |
| `R05` | 7 | Figure label/caption without nearby image. |
| `R12` | 6 | Formula/unit splits around micro units. |

### English Polish Residual Findings

| ID | Count | Meaning |
| --- | ---: | --- |
| `P01` | 24 | Suspicious raw front-matter marker OCR remains relevant after polish. |
| `P04` | 10 | Unlinked citation range/list remains in polish. |
| `P25` | 6 | Late body paragraph is marked as front matter. |
| `P14` | 6 | Figure link target is caption paragraph, not the whole figure block. |
| `P06` | 5 | Flattened or malformed unit/exponent/spacing pattern. |
| `P05` | 5 | Reference links appear in likely non-citation numeric context. |
| `P22` | 5 | Duplicate visible bibliography number. |
| `P13` | 4 | Figure caption has no nearby image. |
| `P03` | 3 | Author-line markers link to bibliography refs. |
| `P12` | 1 | Caption contains TeX/escaped-link residue. |
| `P30` | 1 | Likely float interruption inside body sentence. |

Image preservation is currently strong:

- raw images: 5061
- polish images: 5061
- missing local images: 0

Do not treat this as proof of figure quality. It only proves image assets were
not lost.

## Priority Order

Analyze articles in risk-first order, not alphabetical order.

### Tier 1 - Most Residual Polish Risk

Start with articles that have the highest number and variety of polish residual
classes:

| Alias | Residual classes | Source PDF |
| --- | --- | --- |
| `meine_0043_a848e1004f` | `P01`, `P05`, `P06`, `P12`, `P14`, `P22` | `Biological_Effects_of_Magnetic_and_Electromagnetic_Fields_1996.pdf` |
| `meine_0090_f9583a0fd3` | `P01`, `P05`, `P13`, `P22` | `Robinson - The Techniques and Material Aesthetics of the Daguerreotype.pdf` |
| `meine_0036_d04b54116e` | `P03`, `P05`, `P06`, `P13` | `Song ... - 2020 - Materials for flexible bioelectronic systems as chronic neural interfaces.pdf` |
| `meine_0066_6c8967bd60` | `P01`, `P06`, `P14` | `Stulik ... - 2013 - Collodion on Paper.pdf` |
| `meine_0140_7b0ca9bc57` | `P05`, `P22` | `Bhattacharjee ... - 2022 - Estimating Image Depth in the Comics Domain.pdf` |

These articles should expose whether the current residual classes are real,
false positives, or incomplete audit descriptions.

### Tier 2 - Polish-Only Findings

These are especially important because raw audit did not flag them, but pair
audit did. They are candidates for defects introduced by polish or defects that
raw audit cannot detect.

Initial English polish-only aliases:

- `meine_0004_a4cb70ccef`
- `meine_0027_4a8785387f`
- `meine_0039_75458d8a00`
- `meine_0065_4ae2d0d2b0`
- `meine_0069_7e5793c56a`
- `meine_0081_116f4112ad`
- `meine_0083_c766fd3388`
- `meine_0102_d3de54f14d`
- `meine_0107_ca7c762afc`
- `meine_0110_d7da0239e6`
- `meine_0119_b39521e56d`
- `meine_0121_bfa6ddf741`
- `meine_0129_09858ae6b9`
- `meine_0132_b3e2cea77b`

For every Tier 2 case, explicitly answer:

- Was raw actually clean, or did raw audit miss the precursor?
- Did polish add wrong classes, links, wrappers, or normalized text?
- Is the pair-audit finding a false positive caused by stricter polish checks?

### Tier 3 - Raw-Only Findings

These cases are success candidates: raw had a suspicious signal, but pair audit
does not report a remaining problem.

Use them as positive regression examples. Future fixes must not break them.

Initial English raw-only aliases:

- `meine_0001_3944c69948`
- `meine_0017_7ef4a4f872`
- `meine_0024_69ad5170a0`
- `meine_0029_ddf58debe6`
- `meine_0034_2a6279ac39`
- `meine_0041_515e781bb6`
- `meine_0042_05f20a6416`
- `meine_0045_567d338f68`
- `meine_0047_78d5e1f69c`
- `meine_0052_ef1533f1d7`
- `meine_0054_49ff51e940`
- `meine_0055_2603fc9fe5`
- `meine_0067_43913dc61b`
- `meine_0072_05920f8331`
- `meine_0089_be819c099a`
- `meine_0097_8b3b2a7071`
- `meine_0098_a0a5ce19d0`
- `meine_0099_f64b4f7670`
- `meine_0101_b335da079c`
- `meine_0105_94913746ed`
- `meine_0120_132c43321f`
- `meine_0128_d0a34eaf10`
- `meine_0133_b3bf023ca8`
- `meine_0134_edd06dc6d2`
- `meine_0138_686dec2e12`
- `meine_0139_765be5625a`

For every Tier 3 case, explicitly record what polish did correctly.

### Tier 4 - Clean Controls

Analyze a small sample of clean-both English articles. These are guardrails for
over-broad universal repairs.

For clean controls, do not do deep manual review unless visual inspection shows
something suspicious. The main question is:

- Would the proposed universal fixes alter this clean article?

## Per-Article Review Protocol

For each selected English article, inspect PDF, raw HTML, and polish HTML in
that order.

### 1. PDF Ground Truth

Use the PDF as the visual/content baseline:

- title, authors, affiliations, contribution markers;
- abstract and start of body;
- figure image/caption pairing;
- table title position and table body integrity;
- citations and bibliography numbering style;
- units, exponents, formula/prose boundaries;
- reading order around page breaks and floats;
- terminal sections: funding, supplementary material, references.

Record only facts needed to classify raw/polish behavior. Avoid full manual
copyediting.

### 2. Raw HTML

Inspect `01.en.raw.html`:

- Did Marker preserve the text order?
- Are figure images near their captions?
- Are table captions and cells structurally plausible?
- Are citations still recognizable?
- Are units/formulas recognizable, even if rough?
- Are footnotes, page furniture, or figure OCR text inside body prose?
- Are there raw-only defects that polish later repaired?

### 3. Polish HTML

Inspect `02.en.polish.html`:

- Did polish preserve every image asset and caption?
- Did polish improve reading order?
- Did polish link only real citations?
- Did polish avoid linking affiliation markers, units, exponents, dates, figure
  labels, and other non-citation numbers?
- Did polish normalize units without deleting spaces or exponents?
- Did polish wrap figures/tables as navigable units?
- Did polish add incorrect classes such as `z2m-front-matter` to body prose?

## Classification Statuses

Every symptom must receive exactly one primary status:

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

## Special Focus A - Problems Polish Did Not Solve

This category is the main backlog for EN polish repairs.

Use it when raw already contains the problem or its precursor and polish leaves
visible damage.

Questions to answer:

1. Is the raw defect structurally identifiable without PDF access?
2. Did polish try to repair it and fail, or never target it?
3. Can the repair be made using local HTML context only?
4. Would the repair be safe on the 7-article review corpus and clean Meine
   controls?
5. Does the fix need a warning rather than automatic mutation?

Likely not-solved classes:

### Front Matter OCR - `P01`

Current signal: 24 English articles.

Look for:

- damaged author affiliation markers;
- contribution/correspondence markers;
- author lines linked as bibliography refs;
- author markers left as ordinary text.

Possible universal direction:

- bounded front-matter region;
- stronger author/affiliation pattern recognition;
- no bibliography links before article body starts;
- conservative fallback to plain superscripts, not ref links.

### Citation Ranges and Lists - `P04`

Current signal: 10 English articles.

Look for:

- `[1-4]`, `[8-10]`, `[11, 12]`;
- tagged or split citation brackets;
- citation ranges inside table cells;
- citation lists near equations.

Possible universal direction:

- post-HTML citation parser that works across inline tags;
- stronger exclusion for math/table contexts;
- reference-count guard before creating links.

### Unit/Math Normalization - `P06`

Current signal: 5 English articles.

Look for:

- missing spaces: `CIC)of2.3mCm^-2`;
- flattened exponents: `cm - 2`;
- linked exponent numbers;
- micro-unit splits;
- prose absorbed into equations.

Possible universal direction:

- unit-token normalizer before citation linkification;
- protected unit exponents;
- local regex repair only for known unit grammar, not arbitrary math.

### Figure/Caption Integrity - `P13`, `P14`

Current signals: `P13=4`, `P14=6`.

Look for:

- caption without nearby image;
- image present but not wrapped with caption;
- link target scrolls to caption while image is above viewport;
- false missing-figure warnings.

Possible universal direction:

- figure-unit wrapper validation;
- broader but bounded image/caption proximity scan;
- target IDs on figure wrappers, not caption-only paragraphs.

### Bibliography Identity - `P22`

Current signal: 5 English articles.

Look for:

- duplicate visible reference numbers;
- bibliography continuation fragments;
- references split into multiple blocks;
- citations linking to wrong duplicate target.

Possible universal direction:

- visible-number identity pass;
- merge continuation blocks before assigning `ref-N`;
- audit hard-error for conflicting duplicate targets.

## Special Focus B - Problems Polish Created

This category has the highest priority for safety because it means our code can
damage otherwise acceptable raw output.

Use it when raw/PDF are acceptable but polish introduces visible damage.

Questions to answer:

1. Which polish pass likely created the defect?
2. Is the defect caused by over-broad regex/context?
3. Can the rule be narrowed by block type, section, tag ancestry, or local
   grammar?
4. Can this be prevented by a no-op guard?
5. Which clean controls need regression coverage?

Likely introduced-by-polish classes:

### Body Paragraph Marked as Front Matter - `P25`

Current signal: 6 English articles.

Risk:

- citation linking is suppressed in real body prose;
- body paragraphs may receive front-matter styling/semantics.

Likely cause:

- front-matter classifier extends too far beyond title/author/affiliation area.

Fix direction:

- hard boundary after abstract/introduction/body heading;
- maximum early-block window;
- require author/affiliation-like structure, not just numeric markers.

### False Citation Links - `P05`

Current signal: 5 English articles.

Risk:

- units, labels, dates, sample counts, figure/table values, or exponents link to
  bibliography references.

Likely cause:

- citation linker uses numeric shape without enough semantic context.

Fix direction:

- stronger non-citation context guards;
- unit/exponent/date/figure/table windows;
- require bracket/superscript/citation-like punctuation unless confidence is
  high.

### Author-Line Markers Linked as Refs - `P03`

Current signal: 3 English articles.

Risk:

- affiliation markers become bibliography links.

Likely cause:

- reference linkification runs before or outside front-matter protection.

Fix direction:

- classify front matter first;
- never create `#ref-*` links in protected author/affiliation blocks;
- convert author markers to plain superscripts.

### Figure Target Regression - `P14`

Current signal: 6 English articles.

Risk:

- navigation jumps to caption, hiding image context.

Likely cause:

- ID assignment attaches to caption paragraph instead of wrapper.

Fix direction:

- move target IDs to wrapper when an image/caption unit exists;
- keep caption IDs only when there is no associated image and warning is shown.

## Article Worksheet Template

Use this template for every analyzed article.

```markdown
## <alias> - <short title>

Source PDF:
Raw stage:
Polish stage:
Language detection:

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

| Symptom | Raw status | Polish status | Classification | Evidence | Fix candidate |
| --- | --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... | ... |

### Polish Did Not Solve

- ...

### Polish Created

- ...

### Regression Coverage Needed

- ...

### Verdict

- `fixed_by_polish`:
- `not_fixed_by_polish`:
- `introduced_by_polish`:
- `audit_false_positive`:
- next action:
```

## Batch Summary Template

After every 5-10 articles, append a batch summary:

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

## Decision Rules For Universal Fixes

Promote a pattern to implementation only when all are true:

1. At least two articles show the same real pattern, or one article shows a
   severe deterministic regression introduced by polish.
2. The fix can be expressed with local HTML structure or reliable PDF
   diagnostics.
3. The fix has a no-op path for clean controls.
4. A focused regression fixture can be written before or with the code change.
5. The 7-article EN-polish review corpus remains stable.

Do not promote a pattern when:

- the evidence requires visual judgment that is unavailable to the pipeline;
- the rule depends on one journal/layout only;
- the fix would rewrite arbitrary prose without strong structural guards;
- the audit check is likely a false positive and needs tuning first.

## Recommended First Iteration

Start with Tier 1:

1. `meine_0043_a848e1004f`
2. `meine_0090_f9583a0fd3`
3. `meine_0036_d04b54116e`
4. `meine_0066_6c8967bd60`
5. `meine_0140_7b0ca9bc57`

For each article, produce the worksheet above. After the fifth article, create
the first batch summary and decide whether the top implementation target is:

- front-matter boundary/classifier repair;
- citation false-positive/range repair;
- unit/math normalization repair;
- figure-wrapper/target repair;
- bibliography identity repair.

The first implementation pass should focus on defects that polish either failed
to solve or introduced. Raw-only defects that polish already fixes should be
kept as regression controls, not immediate repair targets.

## Current Processing Stage Snapshot - 2026-05-02

Active stage:
`PDF/Marker -> 01.en.raw.html -> 02.en.polish.html`.

Scope:

- normal EN polish only;
- no RU translation;
- no write-back into Zotero;
- no OCR-specific policy changes;
- no broad visual guessing without a reliable local HTML/PDF signal.

Latest implementation checkpoint:
`006716b Recover orphan EN figure targets`.

### What This Stage Now Handles

- Marker figure images that are extracted as orphan
  `_page_*_Figure_*.jpeg/png/webp/gif` blocks.
- Missing `fig-*` targets when visible prose still contains a nearby
  `Fig./Figure N` reference.
- Three safe recovery patterns:
  - orphan figure image plus unlabeled panel legend before the next known
    numbered figure;
  - ordered orphan figure-image run before nearby references;
  - one orphan figure image after one unambiguous preceding reference.
- Guardrails:
  - table-adjacent images are not promoted to figures;
  - ambiguous previous references are ignored;
  - `Picture` artifacts are not treated as figure targets by this pass;
  - remaining uncertain figure targets stay in audit as `P61`.

### Fixed Problem Classes

| Problem class | Examples | Status |
| --- | --- | --- |
| Missing target for unlabeled panel figure | `022` / `Fig. 1A` | fixed in EN polish |
| Missing targets for ordered orphan figure images | `024` / `Fig. 1`, `Fig. 2` | fixed where safe |
| Figure introduced before visual region | `017` / `Figure 4A`, `Figure 4` | fixed where one nearby number is unambiguous |
| Image loss during repolish | 7-article control and `001-025` | no loss observed |

### Remaining Problem Classes

| Problem class | Examples | Required next layer |
| --- | --- | --- |
| Missing figure target without safe Marker `Figure` image | `017` / `Figure 3` | PDF/raw-region diagnostics |
| Missing target after table-separated extracted regions | `024` / `Fig. 3` | PDF/raw-region diagnostics |
| OCR/book-like layout noise | `023` and other OCR/scanned-like sources | OCR-specific polish sketch/policy |
| Audit precision around valid high-number citations | recurring `P60` cases | audit tuning, not broad polish rewrite |

### Verification Artifacts

- 7-article control repolish:
  `md_output\new\_quality_audit\repolish_after_orphan_figure_recovery_2026-05-02.json`
- 7-article control audit:
  `md_output\new\_quality_audit\en_polish_pair_audit_after_orphan_figure_recovery_pdfdiag_2026-05-02.json`
- Meine `001-025` repolish:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_001_025_after_orphan_figure_recovery_2026-05-02.json`
- Meine `001-025` audit:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_001_025_after_orphan_figure_recovery_2026-05-02.json`

### Next Iteration Rule

If the next complaint is a missing figure/table target, first classify it by
evidence:

1. Local HTML evidence is strong: implement or extend EN polish with a focused
   regression test.
2. HTML evidence is weak but PDF layout can decide: add PDF/raw diagnostics and
   feed structured hints to EN polish.
3. Source is OCR/scanned/book-like: route to the future OCR-specific polish
   policy instead of broadening normal EN polish.
