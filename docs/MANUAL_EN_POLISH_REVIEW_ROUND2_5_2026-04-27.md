# Manual EN Polish Review Round 2.5 2026-04-27

## Scope

Round 2.5 is a post-fix assessment of the current `01.en.raw.html -> 02.en.polish.html`
result against the Round 2 manual complaints. It is not a third complaint source.

Complaint documents counted for this pass:

1. `docs/MANUAL_EN_POLISH_REVIEW_2026-04-26.md`
2. `docs/MANUAL_EN_POLISH_REVIEW_ROUND2_2026-04-27.md`

Round 2 is the primary checklist for this assessment. Round 1 is background/baseline
when a Round 2 symptom depends on earlier observations.

## Current Inputs

- Current repolish report: `md_output/new/_quality_audit/repolish_en_from_raw_2026-04-27.json`
- Current audit with PDF diagnostics: `md_output/new/_quality_audit/en_polish_pair_audit_after_repolish_pdfdiag_2026-04-27.json`
- Post-fix repolish report: `md_output/new/_quality_audit/repolish_en_from_raw_after_universal_commit6_2026-04-27.json`
- Post-fix audit with PDF diagnostics: `md_output/new/_quality_audit/en_polish_pair_audit_after_universal_commit6_pdfdiag_2026-04-27.json`
- Latest all-article repolish after Kaiju iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_kaiju_iter_all_2026-04-27.json`
- Latest all-article audit after Kaiju iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_kaiju_iter_all_repolish_pdfdiag_2026-04-27.json`
- Latest all-article repolish after Li iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_li_iter_all_2026-04-27.json`
- Latest all-article audit after Li iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_li_iter_all_pdfdiag_2026-04-27.json`
- Latest Merken-only repolish after Merken iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_merken_iter2_2026-04-27.json`
- Latest Merken-only audit after Merken iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_merken_iter2_pdfdiag_2026-04-27.json`
- Latest all-article repolish after Merken iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_merken_iter_all_2026-04-27.json`
- Latest all-article audit after Merken iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_merken_iter_all_pdfdiag_2026-04-27.json`
- Latest Schelles-only repolish after Schelles iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_schelles_iter3_2026-04-27.json`
- Latest Schelles-only audit after Schelles iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_schelles_iter3_pdfdiag_2026-04-27.json`
- Latest all-article repolish after Schelles iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_schelles_iter_all_2026-04-27.json`
- Latest all-article audit after Schelles iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_schelles_iter_all_pdfdiag_2026-04-27.json`
- Latest Wang-only repolish after Wang iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_wang_iter_2026-04-27.json`
- Latest Wang-only audit after Wang iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_wang_iter3_pdfdiag_2026-04-27.json`
- Latest Teo-only repolish after Teo iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_teo_iter_2026-04-27.json`
- Latest Teo-only audit after Teo iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_teo_iter_pdfdiag_2026-04-27.json`
- Latest all-article repolish after Teo iteration: `md_output/new/_quality_audit/repolish_en_from_raw_after_teo_iter_all_2026-04-27.json`
- Latest all-article audit after Teo iteration: `md_output/new/_quality_audit/en_polish_pair_audit_after_teo_iter_all_pdfdiag_2026-04-27.json`
- Latest Merken-only repolish after round5 review: `md_output/new/_quality_audit/repolish_en_from_raw_after_merken_iter8_2026-04-27.json`
- Latest Merken-only audit after round5 review: `md_output/new/_quality_audit/en_polish_pair_audit_after_merken_iter8_pdfdiag_2026-04-27.json`
- Latest Schelles-only repolish after round5 review: `md_output/new/_quality_audit/repolish_en_from_raw_after_schelles_iter8b_2026-04-27.json`
- Latest Schelles-only audit after round5 review: `md_output/new/_quality_audit/en_polish_pair_audit_after_schelles_iter8b_pdfdiag_2026-04-27.json`
- Latest all-article repolish after round5 review: `md_output/new/_quality_audit/repolish_en_from_raw_after_iter8_all_2026-04-27.json`
- Latest all-article audit after round5 review: `md_output/new/_quality_audit/en_polish_pair_audit_after_iter8_all_pdfdiag_2026-04-27.json`
- Current review set: `manual_review_en_polish_inlined_2026-04-27_round3`
- Post-fix review set: `manual_review_en_polish_inlined_2026-04-27_round4`
- Latest iterative review set: `manual_review_en_polish_inlined_2026-04-27_round5`
- Latest round5-response review set: `manual_review_en_polish_inlined_2026-04-27_round6`
- Canonical checked files: the `polish_stage_path` entries from the current PDF-diagnostic audit.

Latest commits checked:

- `68fd93a Add optional PDF text diagnostics to EN polish audit`
- `b2ea067 Extend EN polish repair coverage`
- `1ab6205 Inline EN polish review images`
- `62c48b5 Protect EN polish page footnotes`
- `d3ad6f9 Guard model versions and normalize compact units`

## Pre-Fix Corpus Snapshot

The Round 2.5 input audit was materially cleaner than earlier runs:

- Articles: 7
- Raw image tags: 80
- Polish image tags: 80
- Missing local images: 0
- Polish reference links: 991
- Polish figure links: 268
- Polish table links: 24
- Source PDFs present: 7
- PDF text chars available: 657092
- Audit defects: only `P01` on Teo, warning for suspicious raw front-matter OCR.

Pre-fix caveat: the audit was too optimistic for several semantic defects. It
does not yet catch end-section interleaving, some sentence/float interruptions,
chemical suffix normalization, unlinked protected superscript ranges, or missing
spaces around scientific tokens.

## Post-Fix Recheck

After the universal EN-polish fix pass, the current automated signal is clean:

- Articles: 7.
- Raw image tags: 80.
- Polish image tags: 80.
- Missing local images: 0.
- Polish reference links: 1018.
- Polish figure links: 268.
- Polish table links: 24.
- Audit defects: none.
- Post-fix review bundle: `manual_review_en_polish_inlined_2026-04-27_round4`
  with 7 HTML files, 80 inlined images, and 0 missing images.

After the Li article-by-article iteration, the all-article audit is still clean:
80 raw images / 80 polish images, 1018 reference links, 268 figure links,
26 table links, 0 missing images, and no audit defects.

After the Merken article-by-article iteration, the Merken-only audit is clean:
8 raw images / 8 polish images, 117 reference links, 34 figure links,
2 table links, 0 missing images, and no Merken defects. The all-article audit
still has stable image/link totals but now reports one `P06` warning in Wang
Table II (`10 mm 2 mm` from adjacent table cells). This is tracked as a Wang
follow-up rather than a Merken regression.

After the Schelles article-by-article iteration, the Schelles-only audit is
clean: 8 raw images / 8 polish images, 123 reference links, 22 figure links,
7 table links, 0 missing images, and no Schelles defects. The all-article audit
keeps the same global totals and the same Wang-only `P06` warning.

After the Wang article-by-article iteration, the Wang-only audit is clean:
24 raw images / 24 polish images, 46 reference links, 28 figure links,
3 table links, 0 missing images, and no Wang defects. The previous Wang-only
`P06` was an audit false positive from flattening adjacent table cells
(`10 mm` + `2 mm`, `35 µm` + `35 µm`), not a visible polish defect.

After the Teo article-by-article iteration, the Teo-only audit is clean:
3 raw images / 3 polish images, 192 reference links, 5 figure links,
2 table links, 0 missing images, and no Teo defects.

The all-article PDF-diagnostic audit after the Wang/Teo iteration is clean:
7 pairs, 80 raw images / 80 polish images, 1018 reference links,
268 figure links, 26 table links, 0 missing images, and no defects.
The latest inlined review bundle is
`manual_review_en_polish_inlined_2026-04-27_round5` with 7 flat HTML files
and 80 inlined images.

After the round5-response iteration, the all-article PDF-diagnostic audit is
clean: 7 pairs, 80 raw images / 80 polish images, 1028 reference links,
268 figure links, 26 table links, 0 missing images, and no defects. The latest
inlined review bundle is `manual_review_en_polish_inlined_2026-04-27_round6`
with 7 flat HTML files and 80 inlined images.

Observed local wins:

- Ahmed Figure 8 BioRender caption fragments now merge into one caption flow.
- Ahmed bibliography no longer absorbs the standalone `Best Stainless...` entry.
- Kaiju terminal section order is restored before `REFERENCES`.
- Kaiju equation-defined index prose now renders as `iECoG(t)<sub>j</sub>`,
  `x<sub>j</sub>`, and `y<sub>j</sub>`.
- Li page footnote text is protected as `z2m-footnote`, and the Figure 2
  sentence interruption is repaired.
- Merken duplicate bracketed bibliography prefix and oxide suffix rendering are
  repaired.
- Schelles compact scientific/prose joins are normalized.
- Teo author and affiliation marker OCR is normalized in front matter; Teo
  citation ranges, `task. Sec.`, and `flagship models 6,000` are recovered into
  linked bibliography citations.

Residual risk:

- A clean audit is now a useful gate, but it is not a replacement for the next
  inlined visual review bundle.
- The repair layer is intentionally conservative. Future articles with novel
  journal front matter, unusual terminal sections, or heavily damaged captions
  should enter as audit warnings rather than silent rewrites.

## Latest Iterative Article Recheck

### 02 Kaiju 2017, after user review of `round4`

User-visible fixes applied:

- Missing Figure 1 now renders as one `z2m-float-unit z2m-figure-unit z2m-missing-figure-unit`.
  The image is still absent, but the warning and caption are visually separated
  by the same horizontal float borders as real figure units.
- The anesthesia dose sentence no longer pulls `and 0-2%, respectively` into
  MathJax. Only the unit fragments remain inline TeX; prose is plain text.
- Figure/reference/table link styling now sets an explicit `font-weight: 500`,
  so links inside `<b>` wrappers no longer look heavier than equivalent links.
- Base-10 scientific exponents such as `10^-10`, `10^2`, `C = 10^-1`, and
  `C = 10^0` are protected as `z2m-unit-exp` superscripts, not bibliography
  links.
- The chained page-boundary break at `trajectory separation and prediction
  accuracy...` is merged into one paragraph without merging the following
  `In this study...` paragraph.
- The supplementary-material URL keeps the original full URL as one visible
  clickable anchor: `http://journal.frontiersin.org/article/10.3389/fncir.2017.00020/full#supplementary-material`.

Generalization notes:

- Missing figures are now handled as explicit figure units rather than as
  article-specific exceptions.
- The page-boundary repair can merge chained continuation paragraphs, but still
  stops at sentence boundaries and ordinary new paragraphs.
- URL repair uses the existing `href` as authority and only rewrites visible
  text when the adjacent tail reconstructs the same URL.
- Audit now treats wrapped missing-figure units as handled, while still flagging
  silent caption-only figures.

Verification:

- `python -m pytest tests/test_single_file_html.py tests/test_audit_en_polish.py -q`: 174 passed.
- `python -m pytest tests -q --basetemp .tmp_local2\pytest_basetemp_kaiju_full_escalated`: 308 passed.
- Single Kaiju PDF-diagnostic audit: defects none.
- All-article PDF-diagnostic audit after Kaiju iteration: 7 pairs, 80 raw images,
  80 polish images, 1018 reference links, 268 figure links, 24 table links,
  defects none.

The article-by-article sections below preserve the original one-by-one Round 2.5
assessment unless they are explicitly marked with post-fix status. The
`Post-Fix Recheck` section above is the current automated state.

## Pre-Fix Cross-Article Delta

Improved:

- Image integrity and review packaging are now stable: all current article images are present.
- Figure/table wrapper counts and target styles are present across the corpus.
- Many reference links now target stable `#ref-*` anchors instead of embedded `#page-*` anchors.
- False reference links for some non-citation numbers are reduced, especially Teo `Grok 4` and Li footnote marker `1`.
- Several compact units now render with semantic exponent markup, for example `cm<sup>-2</sup>` and `um<sup>2</sup>`.
- Wang Table III sentence continuity is materially fixed.
- Teo Table 1 no longer interrupts the `relatively small... generalizability` sentence.

Still weak before the universal fix pass:

- Full-page captions and caption continuations are still fragile.
- End-of-article section order remains broken in Kaiju.
- Float-aware sentence repair is incomplete, especially Li Figure 2.
- Page footnote extraction is incomplete: markers are protected, but footnote text can still remain inline.
- Scientific word-boundary repair remains partial: examples include `forthe`, `Vwater`, `0.04for`, and `20nCfor`.
- Some citation forms are now protected from false linking but also left unlinked, especially Teo superscript ranges inside protected/front-matter paragraphs.
- Audit coverage must expand to catch the manual-review defects that now survive a clean JSON report.

## Article 1: Ahmed 2026

Round 2 complaints checked: `AHM2-01` through `AHM2-05`.

Current audit signal:

- Images: 10 raw / 10 polish.
- Figure IDs: 8.
- Reference links: 96.
- `href="#page-*"` links: 0 in the current stage.
- Audit defects: none.

What improved:

- Figure 8 now has a stable wrapper target: `id="fig-8"` with `z2m-float-unit z2m-figure-unit`.
- The reference 25 continuation is now merged into visible reference 25; visible reference 26 remains `Li, M. et al.`.
- Body reference links no longer point at `#page-*` anchors.
- The old ordinal drift symptom is reduced at the link-target layer because anchors are now assigned from visible bibliography numbering.

What did not improve enough:

- `AHM2-01` and `AHM2-02` remain open for the actual Figure 8 body caption. The visible body caption still splits the BioRender credit and URL into separate caption fragments, including a broken sequence like `created BioRender. Chamanzar. (2025)` followed by a separate URL heading and a continuation that starts with lowercase `comparison shows`.
- The same article contains a cleaner figure-list/table copy later, but that does not repair the visible Figure 8 caption flow.
- `AHM2-04` remains partially open. `Best Stainless Steel Wafer Polishing Services...` is appended to `li id="ref-57"`, `id="ref-58"` is absent, and the next visible entry is `59. Ong...`. The audit no longer reports link drift, but the bibliography semantics are still wrong.
- `AHM2-05` is not fully resolved while `ref-58` is missing as a real target. The previous wrong-target class changed shape rather than disappearing.

Next fix plan:

- Use the PDF text layer as a fallback for full-page figure captions, starting with Ahmed Figure 8.
- Keep complete image/title/caption/credit/panel text inside one figure unit; do not split a URL into a heading.
- Extend reference normalization to distinguish a true continuation from an unnumbered bibliography entry. A missing visible number such as 58 must be flagged, not silently absorbed into 57.
- Add audit checks for missing visible reference numbers and for `BioRender` captions split across heading/paragraph boundaries.

## Article 2: Kaiju 2017

Round 2 complaints checked: `KAI2-01` through `KAI2-03`.

Current audit signal:

- Images: 10 raw / 10 polish.
- Figure IDs: 9.
- Table IDs: 1.
- Reference links: 50.
- `href="#page-*"` links: 1, but the remaining example is a figure-page link around `Figures 3A,B`, not a bibliography citation.
- Audit defects: none.

What improved:

- `KAI2-01` is mostly improved for bibliography navigation. The old class of author-year links targeting embedded bibliography page anchors is no longer visible in the checked snippets.
- The remaining `#page-*` link is not the original reference-highlight problem. It points from `Figures 3A,B` to a page anchor, so it should be treated as a separate figure-link retargeting/UX issue.
- Wrapper and image integrity look stable.

What did not improve enough:

- `KAI2-02` remains open in prose. The display equation is correct (`iECoG(t)_j`, `x_j`, `y_j`), but the explanatory sentence still reads as `iECoG(t) j` and `(x j, yj)`.
- `KAI2-03` remains open. The end section still reads in broken order: `FUNDING ... by the Ministry of REFERENCES 1...`, then `SUPPLEMENTARY MATERIAL`, then later references continue.
- The current audit misses this because it does not reason over terminal section order; it can be fooled by an earlier body occurrence of `Supplementary Material`.

Next fix plan:

- Add a local equation-context repair for prose immediately following equations, restoring only credible indexed variables such as `iECoG(t)_j`, `x_j`, and `y_j`.
- Reorder terminal sections by heading spans and PDF text-layer order: complete `FUNDING`, complete `SUPPLEMENTARY MATERIAL`, then complete `REFERENCES`.
- Add an audit check that uses terminal heading positions, not first global string occurrence, to validate end-section order.

## Article 3: Li 2026

Round 2 complaints checked: `LI2-01` through `LI2-05`.
Additional article-by-article complaints checked in the Li iteration: six user
items reported after review of `03_Li`.

Latest Li iteration inputs:

- Repolish report: `md_output/new/_quality_audit/repolish_en_from_raw_after_li_iter_2026-04-27.json`
- Audit with PDF diagnostics: `md_output/new/_quality_audit/en_polish_pair_audit_after_li_iter_pdfdiag_2026-04-27.json`
- Review HTML refreshed in `manual_review_en_polish_inlined_2026-04-27_round4/03_Li.html`

Current audit signal after the Li iteration:

- Images: 17 raw / 17 polish.
- Figure IDs: 14.
- Table IDs: 7.
- Reference links: 397.
- Figure links: 66.
- Table links: 10.
- `href="#page-*"` links: 0.
- Audit defects: none.

What improved:

- The `Upadhye et / al. 2022` sentence split across front matter and Figure 1 is repaired. The prose now reads as `Upadhye et al. 2022). Therefore...`; the front matter and figure stay outside the restored paragraph.
- Table 6 and Table 7 captions now preserve source order: captions that are above tables in the article remain above tables in the wrapper.
- The broken `(Tables 6 and 7)` reference is fully retargeted: `6` links to `#table-6`, `7` links to `#table-7`, and the stale `#page-9-1` link is gone.
- Table 6 roman footnote markers are no longer glued into cell text. Examples now render as `sputtering<sup class="z2m-table-fn">i</sup>`, `Foil<sup class="z2m-table-fn">ii</sup>`, `Electrodeposition<sup class="z2m-table-fn">vii</sup>`, and `(EIROF)<sup class="z2m-table-fn">viii</sup>`.
- Table 7 soft line breaks inside data cells are removed where they are layout artifacts, so `electro<br/>chemical` becomes `electrochemical` and the cell text can use the full cell width. Bracket-citation line breaks are still preserved for citation-linking safety.
- The TiN paragraph split by page footnote blocks is repaired. The prose now reads `titanium target and nitrogen gas...`; footnote blocks 2-5 remain present after the restored paragraph.
- Previous Round 2 wins remain stable: the tensile-strength footnote marker is protected, reference links for checked author-year citations remain valid, and image integrity remains 17/17.

What did not improve enough:

- No listed Li iteration symptom remains visible in the refreshed `03_Li.html`.
- Residual watch item: some footnote callouts in the electrode-coatings paragraph are still text-adjacent (`impedance2`, `(CIC)4`, and `5 .`). They are not the page-footnote-block intrusion reported in this Li pass, but they are a good candidate for the next universal footnote-callout polish.

Next fix plan:

- Keep the Li fixtures as regression coverage for front-matter/figure sentence repair, footnote-block sentence repair, plural table links, table-caption source order, roman table footnote markers, and table-cell soft-break cleanup.
- Add a conservative follow-up pass for bare footnote callouts only when the nearby prose matches the extracted footnote keywords.
- Extend audit warnings for stale `#page-*` links inside plural table references and for table cells containing glued roman footnote suffixes.

## Article 4: Merken 2022

Round 2 complaints checked: `MER2-01` through `MER2-04`.
Additional article-by-article complaints checked in the Merken iteration: five
user items reported after review of `04_Merken`.

Current audit signal:

- Images: 8 raw / 8 polish.
- Figure IDs: 5.
- Table IDs: 1.
- Reference links: 117.
- `href="#page-*"` links: 2, both observed as section references (`2.5` and `2.3`), not bibliography targets.
- Audit defects: none.

What improved:

- `MER2-01` is improved in Table 1. The Neuropixels row now reads as a recognizable `70 um x 20 um (1 shaft)` form in current rendering, with the multiplication and unit fragments no longer obviously broken.
- Some dimension/unit markup now uses dedicated exponent handling rather than raw TeX fragments.
- Bibliography link counts are stable and the current audit reports no reference-link identity defects.

What did not improve enough:

- `MER2-02` remains open. Material formulas still render as `HfO <i>x</i>`, `AlO <i>x</i>`, and mixed `IrO <i>x</i>` / `IrO <i><sup>x</sup></i>` rather than normalized subscript oxide notation.
- `MER2-03` is only partially improved. Body/caption area text still shows inconsistent plain-text forms such as `900 um 2`, `2000 um 2`, and related spaced exponent artifacts after HTML flattening.
- `MER2-04` remains open. The bibliography still shows duplicate visible numbering such as `1. [1] Hubel...` because `z2m-ref-num` is added while the raw bracketed source number remains.

Next fix plan:

- Normalize credible oxide formulas (`HfOx`, `AlOx`, `IrOx`) to a single subscript representation in material contexts.
- Normalize area units consistently across table, caption, and body contexts; keep semantic exponent markup but avoid plain-text `um 2` artifacts where possible.
- Strip or reuse bracketed source numbers like `[1]` before adding visible `z2m-ref-num`.
- Add audit checks for `z2m-ref-num` followed by bracketed duplicate numbering and for oxide formulas using italic/superscript `x`.

### Merken Iteration Pre-Fix Characterization

Latest checked files:

- `md_output/new/electrodes_W7TECQDX/Merken и др. - 2022 - Thin flexible arrays for long-term multi-electrode recordings_d0ccb2cf/_z2m_stages/01.en.raw.html`
- `md_output/new/electrodes_W7TECQDX/Merken и др. - 2022 - Thin flexible arrays for long-term multi-electrode recordings_d0ccb2cf/_z2m_stages/02.en.polish.html`
- `manual_review_en_polish_inlined_2026-04-27_round4/04_Merken.html`

Current automated signal after the Li all-article repolish remains clean for Merken:
8 raw images / 8 polish images, 5 figure IDs, 1 table ID, 117 reference links,
34 figure links, and no audit defects.

Observed symptoms from the new Merken review:

- `MER-ITER4-01`: formula/unit representation is inconsistent between table,
  caption, and prose. Older oxide defects are improved in body prose
  (`HfO<sub>x</sub>`, `AlO<sub>x</sub>`, `IrO<sub>x</sub>` are present), but
  table and dimension contexts still mix MathJax-style `\(...\)` with plain
  HTML/unit markup. Fix target is consistency, not changing scientific text.
- `MER-ITER4-02`: micro-unit spacing is still broken where Marker/model emitted
  italicized micro alone: `130 <i> µ </i> m` should become a normal `130 µm`
  or the same canonical unit representation used elsewhere. This is a unit-token
  normalization issue, not a prose rewrite.
- `MER-ITER4-03`: the electrode-size paragraph contains prose-bearing math
  delimiters and escaped TeX residue around ordinary dimensions:
  `\((900 µm<sup>2</sup>; 58/92 \ ch)`, `;\) 12/92 ch)`,
  `\(100 µm × 40 µm\)`, and `\(4000 µm<sup>2</sup>\)`. The same data is clean
  enough in Figure 3 caption, so the body paragraph should be normalized to the
  caption-style plain HTML form.
- `MER-ITER4-04`: a page/citation boundary still splits one sentence:
  `...surface degradation </p><p><a href="#ref-60">[60]</a>. The combination...`.
  The citation belongs to the preceding sentence and should not start a new
  body paragraph.
- `MER-ITER4-05`: compact dimension ranges inside inline math still lose
  readable spacing in display/flattened review form, e.g. the user-visible
  `(30x30μmto200x40μm)` symptom corresponds in current HTML to
  `\((30 × 30 µm  to  200 × 40 µm)\)`. The universal target is to unwrap
  simple dimension prose from inline TeX and normalize spacing around `×` and
  `to`.

Common pattern candidates before code changes:

- `P-MATH-PROSE-UNIT`: inline TeX delimiters around ordinary prose dimensions
  and channel counts. Scope candidate: only unwrap when the content contains
  no real math operators beyond `×`, unit tokens, ranges, punctuation, and
  `ch`; do not unwrap equations, variables, or statistical expressions.
- `P-MICRO-UNIT-TOKEN`: `µ`/`μ`/mojibake micro split from `m` by tags or spaces,
  especially `<i>µ</i> m` and `µ m`. Scope candidate: repair only known SI
  prefixes before `m`, `m2`, or unit exponent markup.
- `P-CITATION-CONTINUATION`: a paragraph ending without terminal citation,
  followed by a paragraph containing only a citation anchor plus sentence
  punctuation and then normal prose. Scope candidate: merge citation prefix
  back into the previous paragraph while leaving subsequent prose as a separate
  paragraph if it starts a new sentence.
- `P-DIMENSION-SPACING`: compact or over-spaced dimension ranges such as
  `30 × 30 µm  to  200 × 40 µm`; normalize to a readable plain-text/HTML form
  without converting valid formulas elsewhere.

Planned universal checks before implementation:

- Search all current EN polish stages for inline TeX blocks containing `µm`,
  `×`, `to`, or `ch` to confirm the rule is not Merken-only.
- Search all current EN polish stages for tag-split micro units and citation-only
  continuation paragraphs.
- Add regression fixtures before changing the polish code.

Pattern scan over the current 7 EN polish stages:

- `P-MATH-PROSE-UNIT` is cross-article, not Merken-only: inline TeX
  dimension/channel-like snippets were found in Ahmed (1), Kaiju (1), Merken
  (13), Schelles (6), and Wang (16). This supports a conservative general pass,
  but the rule must distinguish ordinary dimension prose from true equations.
- `P-MICRO-UNIT-TOKEN` with tag-split micro meter is currently concentrated in
  Merken (10 occurrences). A looser spaced-micro-meter scan also finds one
  Ahmed occurrence, so the repair is still general SI-token cleanup.
- `P-CITATION-CONTINUATION` is currently visible once in Merken, but it is a
  generic PDF page-boundary pattern: previous paragraph ends before a citation,
  the next paragraph starts with only `[N].` and then continues prose.
- `P-DIMENSION-SPACING` is a subset of `P-MATH-PROSE-UNIT`; it should be handled
  by the same narrow unwrapping/spacing pass.
- The split-oxide scan still reports candidates in Li and Merken, but checked
  Merken body prose already renders the named oxide formulas with `<sub>x</sub>`.
  This pass should stay scoped to known oxide formulas and avoid changing author
  names or bibliography tokens.

### Merken Iteration Post-Fix Recheck

Reports and review output:

- Merken-only repolish: `md_output/new/_quality_audit/repolish_en_from_raw_after_merken_iter2_2026-04-27.json`
- Merken-only audit: `md_output/new/_quality_audit/en_polish_pair_audit_after_merken_iter2_pdfdiag_2026-04-27.json`
- All-article repolish: `md_output/new/_quality_audit/repolish_en_from_raw_after_merken_iter_all_2026-04-27.json`
- All-article audit: `md_output/new/_quality_audit/en_polish_pair_audit_after_merken_iter_all_pdfdiag_2026-04-27.json`
- Updated review bundle: `manual_review_en_polish_inlined_2026-04-27_round4/04_Merken.html`

Implemented universal fix layers:

- `P-MATH-PROSE-UNIT`: unwrap only simple dimension/table prose from inline
  TeX when visible text contains units/ranges/channel counts and does not contain
  real equation markers such as `_` or `=`.
- `P-MICRO-UNIT-TOKEN`: normalize tag-split or space-split micro-meter units,
  for example `<i>µ</i> m` and `µ m`.
- `P-DIMENSION-SPACING`: normalize readable spacing around `×`, `to`,
  semicolons, parentheses, `\mathrm{mm}`, and simple `\pm` symbols in dimension
  contexts.
- `P-CITATION-CONTINUATION`: move a leading linked citation such as `[60].`
  back to the previous paragraph when it closes the preceding sentence, while
  leaving the following prose in its own paragraph.

What improved in Merken:

- `MER-ITER4-01` resolved for the checked cases. Table/caption/body dimension
  snippets no longer mix MathJax wrappers with plain unit text for simple sizes:
  examples such as `18.5 mm × 23 mm`, `(4 × 9 shafts)`, `± 1 mm × 2 mm`,
  and `23 × 18.5 mm` now render as symbols/plain HTML.
- `MER-ITER4-02` resolved. The insertion sentence now reads
  `at least 130 µm` without an italic micro token separated from `m`.
- `MER-ITER4-03` resolved. The electrode-size paragraph now renders as normal
  prose with unit exponent markup:
  `30 μm × 30 μm (900 µm<sup class="z2m-unit-exp">2</sup>; 58/92 ch)`,
  `50 µm × 40 µm (2000 µm<sup class="z2m-unit-exp">2</sup>; 12/92 ch)`,
  `100 µm × 40 µm (4000 µm<sup class="z2m-unit-exp">2</sup>; 11/92 ch)`,
  and `200 µm × 40 µm (8000 µm<sup class="z2m-unit-exp">2</sup>; 11/92 ch)`.
- `MER-ITER4-04` resolved. The `[60]` citation is now attached to
  `surface degradation [60].`, and `The combination...` starts the next
  paragraph normally.
- `MER-ITER4-05` resolved. The range now reads
  `(30 × 30 µm to 200 × 40 µm),` without compacted `30x30µmto...` display.

Regression coverage added:

- Split/tagged micro-meter token normalization.
- Merken-style electrode-size prose accidentally wrapped in inline TeX.
- Table-cell dimension TeX with `mm`, `\times`, `\pm`, `\mathrm{mm}`, and
  parenthesized shaft counts.
- Page-split leading linked citation continuation.
- Guard fixture proving a real equation such as `\(x_i = y_i + 1\)` remains
  inline math.

Residual risk:

- The Merken local audit has no defects. The only remaining `\(...\)` snippets
  found in Merken are the MathJax configuration script and a true statistical
  expression, `\(p = 1.80 × 10^{-3}\)`.
- The all-article audit now reports one `P06` warning in Wang Table II, where
  adjacent table columns flatten as `10 mm 2 mm`. This should be handled during
  the Wang pass or by making `P06` table-aware; it is not a Merken symptom.

### Merken follow-up after user review of `round5`

Manual complaint checked:

- `MER-ITER8-01`: Table 1 still contains formula delimiters around a simple
  size value: `Up to \[18 × 21  mm\]`.

Pre-fix characterization:

- This is the same ordinary-dimension class as the previous Merken pass, but it
  arrives from Marker as display TeX `\[...\]` inside a table cell rather than
  inline TeX `\(...\)`.
- The content has no equation markers; it is a plain table dimension with
  `\times` and `\text{ mm}`.

Common-pattern fix requirements:

- Reuse the existing conservative dimension-prose detector for display TeX.
- Normalize `\text{mm}` / `\text{ mm}` the same way as `\mathrm{mm}`.
- Keep real display equations untouched.

Universal fix applied:

- Extend dimension-prose normalization from inline TeX `\(...\)` to display
  TeX `\[...\]` when the content is a simple unit/dimension phrase.
- Normalize `\text{ mm}` inside such dimension snippets.

What improved in Merken:

- `MER-ITER8-01` resolved. The checked Table 1 cell now reads
  `Up to 18 × 21 mm (up to 256 shafts)` with no MathJax delimiters.
- Merken-only PDF-diagnostic audit remains clean after the fix.

Regression coverage added:

- Table-cell display TeX with `18 \times 21 \text{ mm}` unwraps to plain
  dimension text.
- Existing guard coverage still keeps true equations in MathJax.

## Article 5: Schelles 2025

Round 2 complaints checked: `SCH2-01` through `SCH2-05`.

Current audit signal:

- Images: 8 raw / 8 polish.
- Figure IDs: 4.
- Table IDs: 2.
- Reference links: 122.
- `href="#page-*"` links: 0.
- Audit defects: none.

What improved:

- `SCH2-01` is improved at the HTML level: `100 uC cm<sup>-2</sup>` now uses semantic exponent markup instead of a raw math-only unit.
- Several area/charge-density instances also use `z2m-unit-exp` markup, for example `mC cm<sup>-2</sup>` and `um<sup>2</sup>`.
- Link/anchor health is better than earlier runs: no `#page-*` links were found in the current stage.

What did not improve enough:

- `SCH2-02` remains partial. The HTML has exponent markup, but surrounding text still contains spacing defects such as `made forthe electrodes` and some plain text flattens as `67.5 um 2`.
- `SCH2-03` and `SCH2-04` remain open around the CIC sentence. One occurrence still keeps prose inside math-like text: `\((CIC) of 2.3 mC cm^{-2}\)`, and the sentence-ending period before `Additionally` is still missing at the HTML boundary.
- `SCH2-05` remains open. Examples still present: `Vwater`, `0.04for`, `forintracorticalstimulation`, `20nCfor`, and dense fragments like `chosenasthiswasregardedasthenominal`.

Next fix plan:

- Add a word-boundary repair pass for high-confidence scientific/prose joins, with a denylist for valid compact notation.
- Convert prose-bearing math unit snippets such as `(CIC) of 2.3 mC cm^{-2}` back to normal text plus unit markup.
- Restore terminal punctuation when a formula/unit phrase ends a sentence before a new paragraph.
- Add audit checks for common joined-token patterns around units: `for[a-z]`, `Vwater`, `nCfor`, `Awas`, and `0.04for`.

### Schelles Iteration Pre-Fix Characterization

Latest checked files:

- `md_output/new/electrodes_W7TECQDX/Schelles и др. - 2025 - Optimization of sputtered iridium oxide microelectrodes for_3221a765/_z2m_stages/01.en.raw.html`
- `md_output/new/electrodes_W7TECQDX/Schelles и др. - 2025 - Optimization of sputtered iridium oxide microelectrodes for_3221a765/_z2m_stages/02.en.polish.html`
- `manual_review_en_polish_inlined_2026-04-27_round4/05_Schelles.html`

Current automated signal after the Merken all-article repolish:
8 raw images / 8 polish images, 123 reference links, 22 figure links,
2 table links, 0 missing images, and no Schelles audit defects.

Observed symptoms from the new Schelles review:

- `SCH-ITER5-01`: a prose-bearing CIC phrase is still inside inline TeX:
  `\((CIC) of 2.3 mC cm^{-2}\)`. In rendered/flattened review this loses
  readable spacing as `CIC)of2.3mCm^-2`. This should be normalized to plain
  text plus unit exponent markup, not left for MathJax.
- `SCH-ITER5-02`: ohm unit prefixes are split from the unit symbol and sometimes
  from punctuation: examples include `4.8 k Ω`, `100.3 k Ω ,`,
  `1 M Ω .`, and `3 k Ω ,`. The target is SI-symbol spacing such as `4.8 kΩ`,
  `100.3 kΩ,`, and `1 MΩ.`.

Common pattern candidates before code changes:

- `P-CIC-PROSE-MATH`: inline TeX used around an explanatory unit phrase rather
  than an equation. Scope candidate: only unwrap `CIC of <number> mC cm^-2`
  and keep true statistical/math expressions in TeX.
- `P-OHM-PREFIX-SPACING`: `k`/`M`/similar SI prefixes separated from `Ω`.
  Scope candidate: join only known SI prefixes directly before `Ω`/`Ω`,
  then remove whitespace before punctuation after unit symbols.
- `P-UNIT-EXP-PUNCT-SPACING`: spaces between a unit and its exponent `<sup>`,
  and spaces between unit exponent markup and punctuation, for example
  `mC cm <sup>-2</sup> ,`. Scope candidate: run after exponent marking.

Pattern scan over the current 7 EN polish stages:

- `P-CIC-PROSE-MATH` is currently Schelles-local: 2 current matches, both in
  Schelles.
- `P-OHM-PREFIX-SPACING` is cross-article: Ahmed has 1 match and Schelles has
  13 matches.
- `P-OHM-PUNCT-SPACING` is currently Schelles-local with 7 matches.

### Schelles Iteration Post-Fix Recheck

Reports and review output:

- Schelles-only repolish: `md_output/new/_quality_audit/repolish_en_from_raw_after_schelles_iter3_2026-04-27.json`
- Schelles-only audit: `md_output/new/_quality_audit/en_polish_pair_audit_after_schelles_iter3_pdfdiag_2026-04-27.json`
- All-article repolish: `md_output/new/_quality_audit/repolish_en_from_raw_after_schelles_iter_all_2026-04-27.json`
- All-article audit: `md_output/new/_quality_audit/en_polish_pair_audit_after_schelles_iter_all_pdfdiag_2026-04-27.json`
- Updated review bundle: `manual_review_en_polish_inlined_2026-04-27_round4/05_Schelles.html`

Implemented universal fix layers:

- `P-CIC-PROSE-MATH`: unwrap simple CIC charge-density phrases from inline
  TeX into plain text plus `z2m-unit-exp` markup.
- `P-CIC-ASSIGN-UNIT`: unwrap simple parenthetical CIC assignments such as
  `(CIC = 1.9 mC cm^-2)` when they only contain a value and unit.
- `P-OHM-PREFIX-SPACING`: normalize SI-prefix ohm units from `k Ω` / `M Ω`
  to `kΩ` / `MΩ`.
- `P-UNIT-EXP-PUNCT-SPACING`: remove spaces before unit exponent `<sup>` and
  before punctuation after unit symbols/exponent markup.
- `P-VALUE-MICRO-CURRENT`: normalize value-plus-inline-TeX microamp units,
  for example `300 \(\mu A\)` to `300 μA`.

What improved in Schelles:

- `SCH-ITER5-01` resolved. The user-visible CIC sentence now reads:
  `charge injection capacity (CIC) of 2.3 mC cm<sup class="z2m-unit-exp">-2</sup>.`
  The following `Additionally...` paragraph keeps its sentence boundary.
- Related CIC parentheticals now render as text:
  `(CIC = 1.9 mC cm<sup class="z2m-unit-exp">-2</sup>)` and
  `(CIC = 0.7 mC cm<sup class="z2m-unit-exp">-2</sup>),`.
- `SCH-ITER5-02` resolved for checked output. Examples now render as
  `4.8 kΩ`, `100.3 kΩ, 11.3 kΩ, 24.6 kΩ and 41.7 kΩ,`, and `1 MΩ.`
- Post-fix Schelles scans report 0 matches for split `k Ω`, 0 matches for
  `Ω` followed by spaced punctuation, 0 matches for CIC inline-TeX, and
  0 matches for `z2m-unit-exp` followed by spaced punctuation.

Regression coverage added:

- Inline-TeX CIC prose phrase with restored terminal punctuation.
- Parenthetical CIC assignment with charge-density unit.
- `k Ω` / `M Ω` prefix spacing and punctuation cleanup.
- Unit exponent punctuation cleanup after `mC cm<sup>-2</sup>` and
  `µm<sup>2</sup>`.
- Value-plus-inline-TeX microamp unit normalization.

Residual risk:

- Schelles local audit has no defects after the iteration.
- The all-article audit still reports the pre-existing Wang Table II `P06`
  warning (`10 mm 2 mm` from adjacent table cells). This is not introduced by
  the Schelles unit-spacing pass and remains a Wang/table-aware audit follow-up.

### Schelles follow-up after user review of `round5`

Manual complaint checked:

- `SCH-ITER8-01`: citation links were lost in
  `visual cortex [ 10, 12 , 17 ].`; only the last number was linked, and it
  could point at the wrong reference anchor.

Pre-fix characterization:

- The raw source had page-anchor links inside the bracketed citation list.
  During reference retargeting, a page anchor could become an incorrect
  `#ref-*` target before bracket-citation linkification ran.
- The cross-tag bracket-citation parser then skipped the whole bracket when it
  saw an existing `<a>`, leaving plain `10, 12` and a wrong/partial linked `17`.

Common-pattern fix requirements:

- If a bracketed citation list visually parses as numeric citations, rebuild
  links from the visible numbers even when old anchors are already present.
- Normalize simple comma spacing inside the rebuilt citation list.
- Keep the protection rules for non-citation contexts and out-of-range numbers.

Universal fix applied:

- Cross-tag bracket citation recovery now treats existing anchors inside a
  valid numeric citation list as stale markup and reconstructs links by visible
  number.

What improved in Schelles:

- `SCH-ITER8-01` resolved. The checked phrase now reads:
  `visual cortex [<a href="#ref-10">10</a>, <a href="#ref-12">12</a>, <a href="#ref-17">17</a>].`
- Schelles-only PDF-diagnostic audit remains clean after the fix.

Regression coverage added:

- A bracket citation list containing an existing wrong anchor, for example
  `[10, 12, <a href="#ref-16">17</a>]`, is rebuilt as links to refs 10, 12,
  and 17.

## Article 6: Wang 2017

Round 2 complaints checked: `WAN2-01` and `WAN2-02`.

Current audit signal:

- Images: 24 raw / 24 polish.
- Figure IDs: 18.
- Table IDs: 4.
- Reference links: 46.
- `href="#page-*"` links: 0.
- Audit defects: none.

What improved:

- `WAN2-01` looks resolved. The current body paragraph now reads as one sentence: `given the antennas' and sensor's sizes. A small antenna...`; Table III no longer splits the phrase between `sensor's` and `sizes`.
- `WAN2-02` looks resolved in the checked output. The old table-note fragment `fbrain...` was not found as ordinary body text in the current stage.
- No remaining page-anchor links were found.

What did not improve enough:

- No Round 2 Wang complaint remained visible in the checked snippets.
- Residual risk is mostly regression risk: the repair should be covered by fixtures because similar table interruptions still occur in Li/Teo-style contexts.

Next fix plan:

- Lock the current behavior with a Wang-like regression fixture: a table must not split `given the antennas' and sensor's sizes`.
- Add a table-note fixture proving that table notes stay inside or adjacent to the table unit.

### Wang follow-up after user review of `round4`

Manual complaint checked:

- `WAN-ITER6-01`: `Digital Object Identifier 10.1109/TBCAS.2017.2731370`
  remained plain text instead of a clickable DOI link.

Common pattern:

- Some publishers write bare DOI values after an explicit label such as
  `Digital Object Identifier`, without the `doi:` prefix. The existing DOI
  autolinker only handled the `doi:` form, so IEEE-style front-matter DOI lines
  were missed.

Universal fix applied:

- Add context-aware bare DOI autolinking for `Digital Object Identifier` / `DOI`
  labels while preserving the visible DOI text exactly.
- Keep the generated target canonical: `https://doi.org/<doi>`.
- Expand the audit unit checker to inspect table cells separately even when a
  table is wrapped in a float `<div>`, so adjacent table values no longer create
  false `P06` unit warnings.

What improved in Wang:

- `WAN-ITER6-01` resolved. The checked line now renders as:
  `Digital Object Identifier <a href="https://doi.org/10.1109/TBCAS.2017.2731370">10.1109/TBCAS.2017.2731370</a>`.
- Wang-only PDF-diagnostic audit is clean after the fix.
- The earlier Wang `P06` warning on Table II is resolved as an audit correction;
  the table contents themselves were already correctly separated in the HTML.

Regression coverage added:

- Plain web/DOI autolinking now includes the IEEE bare DOI label form.
- Audit coverage now proves that adjacent table cells such as `10 mm` and
  `2 mm` do not become a false flattened-unit defect, including inside a
  `z2m-table-unit` wrapper.

Residual risk:

- The DOI matcher intentionally stays label-gated for bare DOI strings. This
  avoids turning arbitrary numeric substrings into links, but means unlabeled
  bare DOI prose should still be reviewed before broadening the matcher.

## Article 7: Teo 2025

Round 2 complaints checked: `TEO2-01` through `TEO2-06`.

Current audit signal:

- Images: 3 raw / 3 polish.
- Figure IDs: 2.
- Table IDs: 1.
- Reference links: 192.
- `href="#page-*"` links: 0.
- Audit defects after the universal fix pass: none.

What improved:

- `TEO2-01` looks resolved. `Grok 4` is now plain model-version text inside `Claude 4 and Grok 4`, while the following biomedical-setting citation links to `#ref-6`.
- `TEO2-04` looks improved. The checked Foresight paragraph now reads as `However, researchers are applying... Foresight is...` in one paragraph, not split after `However,`.
- `TEO2-06` is improved for the main interruption. Table 1 now appears after the surrounding evaluation/validation text rather than between `relatively small` and `generalizability`.
- `TEO2-02` is now repaired. `task. Sec.` is recovered as `task<sup>58</sup>`, and `flagship models 6,000` is recovered as `flagship models<sup>59,60</sup>`.
- `TEO2-03` and `TEO2-05` are now repaired through the late citation/linkification and front-matter bounding passes: numeric superscript ranges in body paragraphs are linked instead of protected.
- The raw front-matter marker damage is repaired in polish: author markers such as `10 13`, `10 14`, and `1.2.5` become plain affiliation superscripts, and affiliation starts such as `3 Nuffield`, `10 Academic`, `13Department`, and `14Department` become affiliation labels.

What did not improve enough:

- No Teo Round 2 symptom remains visible in the automated audit.
- Residual risk is now visual/manual: front matter should be spot-checked in the next inlined review bundle because OCR marker recovery is necessarily conservative.

Next fix plan:

- Keep the Teo fixtures as regression coverage for future Nature-style front matter.
- Add future audit warnings for front-matter marker repairs that cannot be matched back to the same author names in polish.
- Rebuild the inlined review bundle after the current code commits land.

### Teo follow-up after user review of `round4`

Manual complaints checked:

- `TEO-ITER7-01`: Box 1 and Figure 1 still interrupt the sentence ending
  `enabling the production of ... highly detailed, realistic images`.
- `TEO-ITER7-02`: a page/paragraph split remains after dangling `However,`;
  the continuation `Foresight's development...` starts a new paragraph.

Pre-fix characterization:

- `TEO-ITER7-01` is a chained float problem. The raw order has one body
  paragraph split by Box 1, then the repaired left paragraph still ends with
  `enabling the production of`, and Figure 1 plus its caption remain between
  that phrase and the continuation `highly detailed, realistic images`.
- `TEO-ITER7-02` is a discourse-marker continuation problem. The standard
  page-boundary repair handles lowercase or grammatical continuation tokens,
  but `However, Foresight's...` starts with a capitalized proper noun and is
  therefore left split.

Common-pattern fix requirements:

- Extend the box/floating-block sentence repair so that, after merging a body
  paragraph across a Box block, it can also consume a following figure/image
  gap and a lowercase continuation paragraph before leaving the Box/Figure
  units in place.
- Treat figure-caption paragraphs as non-prose gap blocks when they sit between
  two halves of one sentence.
- Allow conservative dangling discourse markers such as `However,` to merge
  with the next paragraph even when the next paragraph begins with a capitalized
  proper noun.

Regression coverage needed:

- A Box 1 glossary followed by Figure 1 must not split
  `enabling the production of highly detailed, realistic images`.
- `However,` followed by `Foresight's development...` must merge into one
  paragraph, while ordinary completed sentences must remain separate.

Universal fix applied:

- Box sentence repair can now merge a following figure/image gap and lowercase
  continuation when the paragraph recovered from a Box block still ends
  mid-sentence.
- Figure-caption paragraphs are recognized as non-prose gap blocks in the same
  way as image-only paragraphs and figure/table elements.
- Dangling discourse markers such as `However,` are treated as continuation
  cues even when the next paragraph begins with a capitalized proper noun.

What improved in Teo:

- `TEO-ITER7-01` resolved. The checked body sentence now reads:
  `enabling the production of highly detailed, realistic images<sup>23</sup>.`
  Box 1 and Figure 1 follow after the complete prose sentence instead of
  sitting between `production of` and `highly detailed`.
- `TEO-ITER7-02` resolved. The checked paragraph now reads:
  `However, Foresight's development has been halted...` in one paragraph.
- Teo-only PDF-diagnostic audit is clean after the fix.

Regression coverage added:

- A Teo-like Box 1 glossary + Figure 1 sequence preserves the full body
  sentence and still keeps the Box and figure wrapper.
- A Teo-like dangling `However,` page-boundary split merges with the next
  paragraph.

Residual risk:

- The chained Box/Figure merge is still conservative: it only consumes a tail
  after a recognized non-prose image/figure gap and a continuation-shaped next
  paragraph.

## Cross-Article Float-Run Follow-Up After `round5`

Manual complaint checked:

- `C-FLOAT-RUN-FRAME`: if figures and tables go one after another without body
  text between them, captions do not count as separating text; the run should
  be visually framed by two horizontal rules total: one above the first float
  and one below the last float.

Pre-fix characterization:

- Consecutive `z2m-float-unit` wrappers occur across the corpus, including
  Kaiju, Li, Merken, Wang, and smaller runs in Ahmed/Schelles/Teo.
- Before this pass, each wrapper drew its own top and bottom border. A run of
  adjacent floats therefore rendered with internal horizontal rules rather than
  one clean outer frame.

Universal fix applied:

- Add a post-wrapper pass that detects adjacent figure/table wrappers separated
  only by ignorable whitespace/page anchors.
- Mark each run with `z2m-float-run-start`, `z2m-float-run-mid`, and
  `z2m-float-run-end`.
- CSS keeps only the first top rule and the last bottom rule for a run, removing
  internal top/bottom borders while preserving ordinary single-float framing.

Regression coverage added:

- A consecutive figure + table fixture is wrapped as one visual run, with
  start/end classes and the expected CSS rules.

Verification:

- All-article PDF-diagnostic audit after the pass is clean.
- Full pytest after the pass: `323 passed`.

## Round 2.5 Closeout

Final checked output:

- Review bundle: `manual_review_en_polish_inlined_2026-04-27_round6`
  with flat files `01_Ahmed.html` through `07_Teo.html`.
- Final all-article repolish:
  `md_output/new/_quality_audit/repolish_en_from_raw_after_iter8_all_2026-04-27.json`.
- Final all-article audit:
  `md_output/new/_quality_audit/en_polish_pair_audit_after_iter8_all_pdfdiag_2026-04-27.json`.

Final automated signal:

- Articles: 7.
- Images: 80 raw / 80 polish, 0 missing.
- Reference links: 1028.
- Figure links: 268.
- Table links: 26.
- Audit defects: none.
- Full regression suite: `323 passed`.

Final spot checks for the latest manual comments:

- Merken Table 1 no longer contains `Up to \[...\]`; the checked cell reads
  `Up to 18 × 21 mm`.
- Schelles `visual cortex [10, 12, 17]` has links to refs 10, 12, and 17.
- Consecutive figure/table runs are marked with `z2m-float-run-*` classes in
  the output corpus, so CSS renders one outer top/bottom frame for each run.

Residual 2.5 risk:

- The audit is now clean and catches more of the previously manual symptoms,
  but it still cannot prove semantic perfection for every caption, table
  reading order, or publisher-specific OCR pattern. The round6 bundle remains
  the manual-review artifact for visual confirmation.

## Updated Priority Plan

1. Preserve the universal repair mechanisms as the commit stack:
   - audit blind-spot coverage;
   - bibliography identity and citation recovery;
   - float wrappers and reading-order repair;
   - terminal section/footnote repair;
   - scientific text normalization;
   - front-matter marker OCR repair.
2. Rebuild and archive a fresh inlined review bundle from the clean post-fix
   output.
3. Preserve wins with regression fixtures:
   - Teo `Grok 4` model-version guard.
   - Li footnote marker not linked as bibliography ref 1.
   - Wang Table III no longer splitting `sensor's sizes`.
   - Unit exponent rendering for `uC cm^-2`, `mC cm^-2`, and `um^2`.
   - Teo author/affiliation marker OCR repair without bibliography links.
   - Ahmed BioRender caption URL merge.
   - Kaiju terminal section ordering.
