# Meine EN Polish Fix And Test Plan 2026-04-30

Purpose: turn the first Meine manual review findings into a conservative
implementation and regression-test plan for the EN polish pipeline.

Scope of evidence:

- `docs/MEINE_EN_POLISH_MANUAL_REVIEW_2026-04-30.md`
- Reviewed articles: `001_meine_0001` through `005_meine_0012`
- Current polish code: `src/zoteropdf2md/single_file_html.py`
- Current audit code: `scripts/audit_en_polish.py`
- Current tests: `tests/test_single_file_html.py`,
  `tests/test_audit_en_polish.py`

This plan intentionally stops before implementation. It promotes only patterns
that are useful across articles and future PDFs.

## Operating Rules

- Do not hard-code article titles, authors, filenames, or exact complaint text.
- Prefer protected zones and explicit audit warnings over broad rewriting.
- Run citation linking only after the article-level citation/reference style is
  diagnosed.
- Preserve raw visible content when confidence is low; never silently delete a
  token that might be meaningful.
- Every code change needs at least one transformation test or one audit test.
- After each workstream, repolish the five reviewed Meine articles and inspect
  the changed snippets before moving to the next workstream.

## Current Code Map

| Area | Primary location | Existing hooks |
| --- | --- | --- |
| EN polish pipeline | `single_file_html.py` | `polish_html_document` |
| Reference/citation linking | `single_file_html.py` | `_add_reference_ids_and_citation_links`, `_link_sup_citations_in_safe_blocks`, `_link_bracket_citations`, `_rewrite_page_links_to_reference_targets` |
| Protected zones | `single_file_html.py` | `_mark_front_matter_paragraphs`, `_mark_affiliation_paragraphs`, `_mark_footnote_paragraphs_and_refs`, `_strip_reference_links_in_protected_blocks` |
| Units/math repair | `single_file_html.py` | `_normalize_scientific_units`, `_mark_unit_exponent_superscripts`, `_convert_math_tags_to_tex`, `_fix_false_sup_citations_in_decimals_and_figure_labels` |
| Float assembly | `single_file_html.py` | `_add_figure_anchors`, `_add_table_anchors`, `_wrap_float_units`, `_mark_consecutive_float_runs`, `_repair_sentence_breaks_around_figure_blocks`, `_repair_sentence_breaks_around_box_blocks` |
| Heading/section anchors | `single_file_html.py` | `_add_section_anchors`, `_link_section_refs` |
| Readability CSS | `single_file_html.py` | `_inject_default_styles` |
| Pair audit | `scripts/audit_en_polish.py` | `_citation_defects`, `_reference_identity_defects`, `_unit_math_defects`, `_figure_caption_ux_defects` |

## Priority Order

0. Pre-marker language detection and downstream language metadata handoff.
1. Citation/reference identity and protected zones.
2. Float-unit assembly and float-aware reading order.
3. Table readability and table-cell preservation.
4. Heading/equation anchors.
5. Audit expansion for the new failure modes.
6. Regeneration and manual spot-check of reviewed Meine articles.

The first two workstreams have the biggest blast radius and should be committed
separately.

## Workstream 0: Source-Language Gate

### Evidence

- `006_meine_0013_a6269b65e9` is a German article with an English abstract.
  The previous source-language audit misclassified it as English because it
  relied too much on Latin-script/English-abstract evidence.
- `015_meine_0030_7ddd815634` is a German book scan
  (`Die Photographie mit dem Kollodiumverfahren`, 1927) and is also classified
  as `detected_language=en`, `language_confidence=0.99` in the review index.
- Future runs may use different marker settings for different source languages,
  so language must be determined before the marker stage.

### Implementation

- Detect source language from PDF text before marker, sampling several pages and
  preferring the dominant body language over title-page/abstract-only evidence.
- Persist the decision next to the article artifacts, including:
  - `source_language`;
  - confidence and detector reason;
  - sampled page/window counts;
  - gate decision for the requested run language.
- Use `source_language` to select marker/profile settings for the source
  language before any raw HTML is generated.
- Treat mixed or unknown language as an explicit queue decision: skip, route to
  manual review, or run with a deliberately selected source-language profile.
- Keep post-marker HTML language audit as a diagnostic cross-check only; it
  should be able to flag disagreements, but not silently override the pre-marker
  source-language decision.

### Tests

- Add a single-loop regression where a German body with an English abstract is
  skipped for an English marker/polish run.
- Add a single-loop regression where a German historical book scan with Latin
  script and no English body text is skipped for an English marker/polish run.
- Add a metadata regression proving that the pre-marker `source_language` is
  written to the article/run manifest.
- Add an audit warning for pre-marker/post-marker language disagreement.

## Workstream 1: Article-Level Citation Strategy

### Evidence

- `001`: superscript citations became formula-like/math-like text and some
  superscripts were flattened into prose.
- `003`: front-matter author affiliation markers and unit exponents became
  bibliography links.
- `004`: bracket references `[1]`, `[11]` were not linked at all because no
  bracket-reference identity was established.
- `005`: bracket citations mostly improved, but `chi-square (chi2)` was linked
  as `#ref-2`.
- `016`: body citations use author-year style, but polish rewrites many
  different author-year citations to the same numeric target `#ref-11` because
  it retargets by reused page anchors instead of by author/year identity. Other
  author-year citations remain unresolved `#page-*` links.
- `017`: Frontiers-style article uses author-year bibliography references plus
  numbered web/source footnotes. Polish links body footnote markers `1`, `2`,
  and `3` to bibliography refs `ref-1`, `ref-2`, and `ref-3`.
- User request: choose the citation restoration strategy only after analyzing
  the PDF/article text and seeing which style dominates.

### Implementation

- Add an article-level citation-style detector before linkification.
- Inputs:
  - raw HTML body text;
  - reference-section text;
  - optional PDF text diagnostics when available.
- Output a small diagnosis object, for example:
  - `reference_list_style`: dotted numeric, bracket numeric, author-year, none;
  - `in_text_style`: bracket numeric, superscript numeric, author-year, mixed;
  - `numbered_note_style`: body footnote/source notes, bibliography citations,
    none;
  - `confidence`: high, medium, low;
  - counts for each observed style.
- Gate citation linking by the diagnosis:
  - bracket linker only when bracket citations and bracket/dotted numeric
    references are compatible;
  - superscript linker only when body prose has dominant superscript citations;
  - author-year retargeting only when surname/year evidence matches a reference
    entry with high confidence;
  - low confidence leaves ambiguous numeric tokens plain and emits an audit
    warning.
- Never map author-year page anchors to a numeric reference solely because the
  same `#page-*` target appears in the reference section. If author-year
  matching is unavailable or low-confidence, unwrap the page anchor and keep the
  visible citation text plain.
- In author-year articles, treat numeric superscripts as footnotes/source notes
  unless there is strong evidence of superscript numeric bibliography citation
  style.
- Keep the detector pure and testable; do not require PDF text for normal
  operation.

### Tests

Add to `tests/test_single_file_html.py`:

- `test_polish_html_document_detects_and_links_bracket_citation_style`
  - body has `[1]`, `[3-7]`;
  - references are `[1] Author...`, `[7] Author...`;
  - output has `id="ref-1"` and linked bracket citations.
- `test_polish_html_document_uses_superscript_strategy_only_in_body_prose`
  - body has citation superscripts;
  - title/author block has affiliation superscripts;
  - only body superscripts link.
- `test_polish_html_document_low_confidence_numeric_tokens_remain_plain`
  - no reliable references section;
  - numeric superscripts and bracket-like values remain unlinked.
- `test_polish_html_document_detects_author_year_citation_style`
  - body has `(Born et al., 1998; Martin et al., 1999)`;
  - reference list has matching author/year entries.
- `test_polish_html_document_does_not_map_author_year_citations_by_page_anchor`
  - two different author-year citations sharing one page target do not both
    link to the same numeric `#ref-*`.
- `test_polish_html_document_unwraps_low_confidence_author_year_page_links`
  - unmatched author-year page anchors become plain visible citation text.
- `test_polish_html_document_distinguishes_frontiers_footnotes_from_references`
  - author-year references plus web/source footnotes do not link footnote `1`
    to `#ref-1`.

Add to `tests/test_audit_en_polish.py`:

- `test_analyze_pair_reports_reference_style_mismatch`
  - article has bracket citations and references but zero `#ref-*` links.
- `test_analyze_pair_reports_ambiguous_citation_style_low_confidence`
  - many numeric tokens, no clear references; audit warns instead of expecting
    links.
- `test_analyze_pair_reports_author_year_citations_linked_to_single_numeric_ref`
- `test_analyze_pair_reports_author_year_page_links_left_unresolved`
- `test_analyze_pair_reports_footnote_marker_linked_to_bibliography_ref`

## Workstream 2: Reference List Normalization And Deduplication

### Evidence

- `004`: bracket bibliography entries were not assigned `ref-*` targets.
- `005`: reference labels became visible duplicates such as `1. 1 .` because
  polish added `z2m-ref-num` but kept the original page-anchor label.
- Earlier review evidence also showed drift when Marker split reference entries
  across pages.
- `008`: Marker split reference `[13]` after `pages 1243-1250,` and put the
  continuation `Heidelberg, 2006. Springer.` in the next list group. Polish
  incorrectly synthesized this continuation as `ref-14`, shifting all semantic
  targets from `[14]` onward.
- `013`: Marker split reference `[7]` after `Pattern Analysis and Machine`.
  The continuation `Intelligence, IEEE Transactions on, 10, 1988, 439-451.`
  was synthesized as `ref-8`, shifting raw reference `[8]` and all later
  targets.
- `013`: body multi-citations now show visible-label/target mismatch caused by
  that drift: visible `,9` links to `#ref-10`, visible `,11` links to
  `#ref-12`, and visible `33` links to `#ref-34`.
- `018`: same-style bracket citations are mixed: many are linked, but
  page-anchor citations such as `[17,18]`, `[20-23]`, `[30]`, and `[33]` remain
  `#page-*` links.

### Implementation

- Normalize the references section before citation linking.
- Parse visible labels from:
  - `1. Author...`;
  - `[1] Author...`;
  - `<a href="#page-X">1</a> . Author...`;
  - `1. [1] Author...`.
- Assign `id="ref-N"` from the trusted visible number, not from list ordinal.
- When adding `<span class="z2m-ref-num">N.</span>`, consume/remove the original
  numeric label token or page-anchor label.
- Keep DOI/PMID/external links inside entries intact.
- Merge continuation-only list items only under strong guards:
  - no visible new reference number;
  - starts lowercase or with continuation punctuation;
  - or previous reference ends with continuation punctuation such as a comma and
    the next numbered item confirms that the current item is not a new entry;
  - or previous reference ends with an incomplete title/journal fragment and
    the current unlabeled item completes that bibliographic phrase;
  - previous item exists and same reference section is active.
- Never assign a `ref-N` ID from list ordinal alone when the raw/visible list
  item has no trusted numeric label. If a continuation cannot be merged safely,
  leave it un-id'd and emit an audit warning instead of shifting later targets.
- When rewriting citation/page anchors, target references by the visible
  citation label, not by inferred list ordinal or the shifted page-anchor map.
  A visible `9` may link only to `#ref-9`.
- Retarget page-anchor bracket citations using the same parser as plain bracket
  citations, including no-space lists, en-dash ranges, and trailing punctuation.
- If an article has high-confidence bracket citation style, avoid partial repair:
  same-style page-anchor bracket citations should either be retargeted or
  explicitly audited.

### Tests

Add to `tests/test_single_file_html.py`:

- `test_polish_html_document_consumes_page_anchor_reference_label`
  - input: `<li><b><a href="#page-1-0">1</a> .</b> Siegel...</li>`;
  - output: one visible `1.` and no `1. 1 .`.
- `test_polish_html_document_assigns_ids_to_bracket_reference_list`
  - input references `[1]`, `[11]`;
  - output has `ref-1`, `ref-11`.
- `test_polish_html_document_keeps_reference_external_links_during_label_dedup`
  - DOI and PMID anchors survive label normalization.
- `test_polish_html_document_merges_reference_continuation_without_id_drift`
  - continuation item does not become a new reference.
- `test_polish_html_document_does_not_synthesize_ref_id_for_unlabeled_reference_continuation`
  - `[13] ... pages 1243-1250,` followed by `Heidelberg, 2006. Springer.`
    remains one `ref-13`, and `[14] Jacob...` remains `ref-14`.
- `test_polish_html_document_merges_reference_continuation_after_incomplete_title`
  - `[7] ... Pattern Analysis and Machine` plus unlabeled `Intelligence...`
    remains `ref-7`, and raw `[8]` remains `ref-8`.
- `test_polish_html_document_links_page_anchor_citation_by_visible_label`
  - a multi-citation such as `[4,5,7,9,11,14,31,33]` links each visible label
    to the matching `#ref-N`.
- `test_polish_html_document_retargets_page_anchor_bracket_citation_list`
  - `<a href="#page-X">[17,18].</a>` links to `#ref-17` and `#ref-18`.
- `test_polish_html_document_retargets_page_anchor_bracket_citation_range`
  - `<a href="#page-X">[20-23]</a>` expands or links the range according to
    existing bracket-citation behavior.

Add to `tests/test_audit_en_polish.py`:

- `test_analyze_pair_reports_duplicate_dotted_reference_prefix`
  - `li#ref-1` text begins `1. 1 .`.
- `test_analyze_pair_reports_bracket_references_with_zero_ref_links`
  - bracket bibliography plus bracket body citations but no semantic links.
- `test_analyze_pair_reports_reference_id_drift_from_unlabeled_continuation`
  - a short continuation-only reference item receives `id="ref-N"` and the next
    visibly numbered raw reference is shifted.
- `test_analyze_pair_reports_ref_link_visible_label_mismatch`
  - linked citation text `9` pointing to `#ref-10` is reported.
- `test_analyze_pair_reports_bracket_citation_left_as_page_link`

## Workstream 3: Citation False-Positive Protected Zones

### Evidence

- `003`: author affiliation markers and unit exponents became ref links.
- `004`: `QMAX` was split as `QMA` plus a superscript/footnote `x`.
- `005`: `chi2` statistical notation became a ref link.
- `001`: word-final letters and superscript citations were conflated.
- `008`: plain decimal ratings `9.2`, `9.3`, `9.5`, and `8.2` were converted
  into linked superscript-like `#ref-*` pairs.
- `008`: section range text `Sections 3.3.5-3.3.8` was converted into
  reference links for `3,3` plus a dangling `.5-3.3.8`.
- `008`: page-locator citation `[14, p. 156]` remained unlinked; the desired
  behavior is to link only the reference label and preserve the locator text.
- `010`: raw page anchors split ordinary words (`ob` + `je` + `ct` + `s w`,
  `safe` + `ty c` + `oncerns`). Polish rewrote some of these page anchors to
  `#ref-*` because the same page IDs appear inside reference entries, producing
  false reference links inside words.
- `012`: the same Reichinger article reproduces the page-anchor defect and also
  shows a page-anchor fragment retargeted to `#ref-2` inside a plain prose word
  after `T`, breaking `The additive production methods`.
- `011`: a numbered method-list cross-reference, `steps 2 and 3`, was converted
  into a false `#ref-3` link even though it refers to procedure steps, not the
  bibliography.
- `013`: front-matter author markers remain page anchors glued into names:
  `Govern <a href="#page-0-0"> i1, </a>` and
  `Furfer <a href="#page-0-1"> i3, </a>`.
- `014`: clear superscript numeric citation style is detected for most
  citations, but flattened citation tokens such as `dysfunctional voiders.3`
  and `Agarwal et al3` remain unlinked.
- `014`: page anchors contain ordinary page-break prose such as
  `that formulas that use the total`, and polish leaves them as visible
  `#page-*` links.
- `017`: comma-decimal/statistical values are linked as references, for example
  effect size `1,5` becomes `#ref-1` plus `#ref-5`, and allocation ratio `3,1`
  becomes `#ref-3` plus `#ref-1`.

### Implementation

- Extend protected zones before citation linkification:
  - front matter, authors, affiliations, contribution notes;
  - units and unit exponents;
  - math/statistical notation near Greek letters or statistical symbols;
  - table cells containing all-caps feature variables;
  - table footnote markers only when they match a real footnote pattern.
- Add specific guards:
  - no `#ref-*` link inside `chi2`, `R2`, `r2`, `p2`, `x2` statistical/math
    tokens unless bracket/superscript strategy is high-confidence and context is
    prose citation punctuation;
  - no table-footnote split of all-caps variables like `QMAX`;
  - no citation link inside already marked `z2m-unit-exp`.
- Do not link numeric tokens when they are part of decimal values, ratings,
  comma decimals, statistical values, section numbers, chapter/appendix ranges,
  dotted numeric outlines, numbered method steps, or procedure-list
  cross-references.
- Support bracket citations with page locators by linking only the numeric
  reference label, for example `[14, p. 156]` -> linked `14` plus plain
  `, p. 156`.
- Rewrite page anchors to reference targets only when the visible page-anchor
  text and its immediate neighbors form a real citation token. Page anchors that
  contain word fragments must be unwrapped and merged back into normal prose.
- Normalize or unwrap front-matter page anchors that are glued to author names
  or affiliation markers before citation/page retargeting runs.
- When article-level superscript citation confidence is high, restore flattened
  citation tokens such as `et al3` and sentence-final `.3` only if:
  - the target `ref-N` exists;
  - the token is not part of a decimal, section number, figure/table number,
    procedure step, or unit;
  - local punctuation matches a citation context.
- Unwrap page anchors whose visible text is ordinary prose continuation rather
  than a citation, figure/table ref, URL, or page marker.

### Tests

Add to `tests/test_single_file_html.py`:

- `test_polish_html_document_does_not_link_chi_square_exponent`
  - `(chi <sup>2</sup>)` remains statistical notation.
- `test_polish_html_document_does_not_link_r_squared_or_statistical_exponents`
  - `R<sup>2</sup>` and `r<sup>2</sup>` remain plain.
- `test_polish_html_document_preserves_all_caps_table_variables`
  - `QMAX`, `AUC`, `CMG`, `PVR` remain plain table text.
- `test_polish_html_document_does_not_link_author_affiliations`
  - author superscripts in a front-matter paragraph stay unlinked.
- `test_polish_html_document_does_not_link_unit_exponents`
  - `mL s<sup>-1</sup>` and Marker-damaged variants remain unlinked.
- `test_polish_html_document_does_not_link_decimal_ratings_as_references`
  - `average rating was 9.2`, `average 8.2` remain plain decimals.
- `test_polish_html_document_does_not_link_comma_decimal_statistics_as_references`
  - `effect size was 1,5` and `ratio 3,1` remain plain numeric values.
- `test_polish_html_document_does_not_link_section_number_ranges_as_references`
  - `Sections 3.3.5-3.3.8` remains plain or becomes section links, never
    `#ref-3`.
- `test_polish_html_document_does_not_link_step_numbers_as_references`
  - `steps 2 and 3` inside a numbered procedure remains plain text.
- `test_polish_html_document_links_bracket_citation_with_page_locator`
  - `[14, p. 156]` links `14` to `#ref-14` and keeps `p. 156` visible.
- `test_polish_html_document_does_not_retarget_word_fragment_page_links_to_references`
  - `ob<a href="#page-7-0">je</a><a href="#page-7-1">ct</a><a href="#page-7-2">s w</a>ould`
    becomes plain `objects would`, not `#ref-*`.
- `test_polish_html_document_unwraps_front_matter_author_page_anchor_glue`
  - `Govern<a href="#page-0-0"> i1, </a>` is normalized without a page link.
- `test_polish_html_document_links_flattened_superscript_citation_after_et_al`
  - `Agarwal et al3` links `3` to `#ref-3` under superscript-style confidence.
- `test_polish_html_document_links_flattened_sentence_final_superscript_citation`
  - `dysfunctional voiders.3` links `3` to `#ref-3` without touching decimals.
- `test_polish_html_document_unwraps_prose_page_break_links`
  - `<a href="#page-11-0">that formulas that use the total</a>` becomes plain
    prose.

Add to `tests/test_audit_en_polish.py`:

- `test_analyze_pair_reports_ref_link_inside_statistical_superscript`
- `test_analyze_pair_reports_all_caps_variable_split_as_table_footnote`
- `test_analyze_pair_reports_decimal_rating_linked_as_reference`
- `test_analyze_pair_reports_comma_decimal_value_linked_as_reference`
- `test_analyze_pair_reports_section_range_linked_as_reference`
- `test_analyze_pair_reports_step_number_linked_as_reference`
- `test_analyze_pair_reports_ref_link_inside_word_fragment`
- `test_analyze_pair_reports_remaining_page_link_inside_word_fragment`
- `test_analyze_pair_reports_front_matter_page_anchor_glue`
- `test_analyze_pair_reports_flattened_superscript_citation_left_unlinked`
- `test_analyze_pair_reports_prose_page_break_link_left_visible`

## Workstream 4: Float Units, Figure Grids, Boxes, And Reading Order

### Evidence

- `001`: boxes need the same top/bottom framing as floats; Box 1 reference was
  not linked.
- `004`: side-by-side figure grids were extracted as
  `image, image, caption, caption`; polish wrapped only one figure and left the
  other caption-only/orphan-image.
- `005`: top-of-page Figure 1 interrupted a sentence continuation; polish
  created a figure wrapper but left the reading-order split and page-span figure
  reference.
- `008`: an ACM permission/copyright block, conference line, TeX macro artifact,
  and DOI line appeared between two halves of one body sentence. Polish marked
  the permission block as front matter but still merged `DOI: http://...` with
  the continuation sentence, producing broken body prose.
- `009`: thesis-style figure/table numbers use chapter-local identifiers such
  as `Figure 2.1`, `Figure 3.20`, `Table 4.2`. Polish collapses them to
  `fig-2`, `fig-3`, `table-4`, causing duplicate IDs and wrong links.
- `009`: entries in `LIST OF FIGURES` and `LISTS OF TABLE` are treated like
  body figure/table references and sometimes like caption evidence, producing
  misleading links and audit warnings.
- `014`: table/caption pairing drifts around sequential tables. The visible
  `TABLE 4` caption remains a standalone `p id="table-4"`, the following
  actual table is wrapped as `div id="table-5"`, and the visible `TABLE 5`
  caption is appended after that table while the next actual table is left
  unwrapped.
- `014`: `TABLE 2` receives an ID on the caption paragraph, but the following
  table is not wrapped into the same float unit.
- `014`: some table references link only the visible number (`4`, `5`, `7.`)
  rather than the complete `Table N` phrase.
- `016`: figure assembly groups unrelated captions into one wrapper:
  `fig-4` becomes an alias inside the `fig-1` wrapper, and `fig-5` becomes an
  alias inside the `fig-2` wrapper.
- `016`: page-anchor cross-references `(Table 1)`, `(Fig. 1)`, and `(Fig. 2)`
  remain `#page-*` links even though semantic targets exist.
- `016`: `(Figs. 3 and 5)` is split incorrectly: `(Figs. 3` remains a page link
  and `5` becomes a false bibliography link to `#ref-5`.
- `017`: only `fig-1` and `fig-2` targets exist even though the article refers
  to `Figure 3`, `Figure 3D`, `Figure 4A`, `Figure 4B`, and `Figure 4`.
- `017`: polish emits a useful missing-figure warning for `Figure 1`, but audit
  does not treat this as a review issue because no local image path is missing.
- `018`: a figure run interrupts a sentence around `see Fig. 19) permanently`
  before the continuation `displayed at the Museo di San Marco...`.
- Global user request: adjacent figure/table/box units with no body text between
  them should have one separator above the run and one below.

### Implementation

- Treat boxes as float units:
  - `div.z2m-float-unit.z2m-box-unit#box-N`;
  - link `(Box N)` to the wrapper;
  - include boxes in float-run framing.
- Add a figure-grid assembler before final float wrapping:
  - detect runs of adjacent image nodes followed by caption runs on the same
    page/nearby block window;
  - pair images and captions by order;
  - produce complete wrappers for each figure;
  - do not create caption-only figure IDs when an orphan image is adjacent.
- Support composite float numbers:
  - preserve the full visible identifier for chapter-style labels such as
    `Figure 2.1`, `Figure 3.20`, `Table 4.2`;
  - generate targets such as `fig-2-1`, `fig-3-20`, `table-4-2`;
  - reject duplicate IDs during target assignment and fall back to a unique,
    visible-number-derived slug instead of reusing `fig-2`.
- Treat table-of-contents/list-of-figures/list-of-tables regions as index zones:
  - do not create figure/table targets from index entries;
  - link index entries only when a full matching target exists;
  - never let index entries drive caption-without-image warnings.
- Improve float-aware continuation repair:
  - if left paragraph ends in an incomplete phrase or conjunction and the first
    non-float block after the float starts lowercase, merge the text fragments;
  - keep the float as a separate unit after a stable insertion point.
- Treat page/copyright/DOI boilerplate blocks as explicit non-body interruptions:
  - classify common publisher permission notices, conference header/footer lines,
    DOI-only lines, and long TeX macro leaks separately from front matter;
  - do not concatenate boilerplate text into the body continuation;
  - when both sides of the boilerplate are body fragments, repair the body
    sentence around the boilerplate while keeping the boilerplate isolated.
- Retarget page-span figure links after wrapper IDs exist:
  - `(Fig 1)` split as `<a href="#page-X">(Fig</a> 1)` becomes one link to
    `#fig-1`.
- Pair table captions with the correct adjacent table by trusted visible table
  number, not by wrapper ordinal. Caption-before-table and caption-after-table
  cases should both create a single wrapper whose ID matches the visible table
  number.
- Link table references as complete phrases when the visible phrase exists:
  `Table 4`, `TABLE 4`, and `table 4` should point to `#table-4`, not only the
  digit.
- Do not add a later figure number as an alias inside an earlier wrapper unless
  the image/caption evidence proves a single compound figure. Ambiguous
  multi-caption/single-image cases should stay explicit and warn rather than
  create misleading aliases.
- Retarget figure/table list references such as `(Figs. 3 and 5)` by the visible
  figure/table label, and never pass the list item numbers to bibliography
  citation linking.
- Support subfigure/lettered references such as `Figure 4A`, `Figure 4B`, and
  `Figure 3D`. If a matching figure target cannot be created, emit an audit
  warning instead of silently leaving bold/plain text.
- Audit intentionally emitted missing-figure warning blocks as review findings,
  even when there is no broken local image path.

### Tests

Add to `tests/test_single_file_html.py`:

- `test_polish_html_document_wraps_box_unit_and_links_box_reference`
  - `BOX 1` plus body and `(Box 1)` link to `#box-1`.
- `test_polish_html_document_marks_box_figure_table_run_as_single_visual_run`
  - adjacent box/figure/table units receive run start/end classes.
- `test_polish_html_document_pairs_two_images_followed_by_two_captions`
  - input `img15, img16, Figure 15 caption, Figure 16 caption`;
  - output has `fig-15` and `fig-16`, both with one image and one caption.
- `test_polish_html_document_uses_composite_figure_ids_for_chapter_numbering`
  - `Figure 2.1` and `Figure 2.10` become `fig-2-1` and `fig-2-10`.
- `test_polish_html_document_uses_composite_table_ids_for_chapter_numbering`
  - `Table 4.1` and `Table 4.2` become distinct `table-4-1` and `table-4-2`.
- `test_polish_html_document_does_not_make_duplicate_float_ids`
  - repeated chapter-style figure labels never reuse `id="fig-2"`.
- `test_polish_html_document_does_not_create_targets_from_list_of_figures`
  - list/index rows may link to existing full targets but do not create them.
- `test_polish_html_document_repairs_top_of_page_figure_sentence_split`
  - `validated for` + figure + `the assessment...` becomes one paragraph plus a
    separate figure unit.
- `test_polish_html_document_repairs_sentence_split_around_figure_run`
  - `see Fig. 19) permanently` + figure run + `displayed at...` is repaired
    while figures stay as separate units.
- `test_polish_html_document_repairs_body_sentence_around_acm_permission_boilerplate`
  - `while` + permission/DOI boilerplate + `the plasticity...` becomes a clean
    body sentence and isolated boilerplate.
- `test_polish_html_document_retargets_split_page_figure_link_to_wrapper`
  - `(Fig 1)` page-anchor fragment becomes `href="#fig-1"`.
- `test_polish_html_document_pairs_table_caption_before_table_by_visible_number`
  - `TABLE 2` caption plus following table becomes one `#table-2` wrapper.
- `test_polish_html_document_pairs_table_caption_after_previous_table_without_id_drift`
  - `TABLE 4` attaches to its own adjacent table and does not make the next
    wrapper `#table-5`.
- `test_polish_html_document_links_full_table_reference_phrase`
  - `Table 4` links as one phrase, not only `4`.
- `test_polish_html_document_does_not_alias_unrelated_figure_captions`
  - `Fig. 1` and `Fig. 4` captions after one image do not silently create
    `fig-4` as an alias inside `fig-1`.
- `test_polish_html_document_retargets_page_table_reference_to_wrapper`
  - `(Table 1)` page-anchor text links to `#table-1`.
- `test_polish_html_document_links_figure_list_reference_to_figures`
  - `(Figs. 3 and 5)` links both numbers to `#fig-3` and `#fig-5`, never
    `#ref-5`.
- `test_polish_html_document_handles_lettered_subfigure_references`
  - `Figure 4A` and `Figure 3D` link to the best available figure target or
    remain plain with an audit warning.

Add to `tests/test_audit_en_polish.py`:

- `test_analyze_pair_reports_caption_only_figure_adjacent_to_orphan_image`
- `test_analyze_pair_reports_float_interruption_with_lowercase_continuation`
- `test_analyze_pair_reports_page_span_figure_ref_when_figure_wrapper_exists`
- `test_analyze_pair_reports_duplicate_semantic_ids`
- `test_analyze_pair_reports_collapsed_composite_figure_number`
- `test_analyze_pair_ignores_list_of_figures_caption_without_image`
- `test_analyze_pair_reports_table_caption_target_drift`
- `test_analyze_pair_reports_standalone_table_caption_with_unwrapped_adjacent_table`
- `test_analyze_pair_reports_partial_table_reference_link`
- `test_analyze_pair_reports_unrelated_figure_alias_inside_wrapper`
- `test_analyze_pair_reports_figure_list_number_linked_as_reference`
- `test_analyze_pair_reports_visible_figure_reference_without_target`
- `test_analyze_pair_reports_missing_figure_warning_block`

## Workstream 5: Tables, Wide Layout, Soft Breaks, And Statistical Markers

### Evidence

- `003`: table text still had roman numeral/footnote leakage and narrow
  line-break artifacts.
- `004`: table variable `QMAX` was mutated.
- `005`: Table 3 has 19 columns and overflows the fixed readable container.
- `005`: p-value significance stars were damaged to replacement characters, but
  the table note states `*: statistically significant`.
- `008`: the roman-footnote/suffix repair is too broad outside table-footnote
  contexts and split normal names/words: `Gustav` -> `Gusta v`, `Bulatov` ->
  `Bulato v`, `Vinnikov` -> `Vinniko v`.
- `009`: the same broad suffix repair split `APPENDIX` in a table-of-contents
  row into `APPEND` plus a table footnote `ix`.
- `012`: the table repair splits an ordinary table word:
  `multi-view input` becomes `mult<sup class="z2m-table-fn">i</sup>-view input`.
- `013`: the same roman/name splitting appears in a reference author name:
  `Belyaev, A.` becomes `Belyae v, A.`.
- `014`: mixed-case table variables are split as false table footnotes:
  raw `Qmax` becomes `Qma<sup class="z2m-table-fn">x</sup>` about 170 times.
- `015`: after a German book scan is mistakenly processed through the English
  path, ordinary German table words are split as footnotes, including
  `Kali-Salpeter`, `Kupfervitriol`, `Mastix`, and `Borax`.
- `016`: another author surname is split: `Yakovlev (1967)` becomes
  `Yakovle v (1967)`.
- `017`: `Nedelev` is split in front matter and references as `Nedele v`.
- User request: render HTML width according to the widest table.

### Implementation

- Add table complexity analysis during polish:
  - maximum cells in a row;
  - long unbreakable tokens;
  - estimated intrinsic width.
- Add CSS classes:
  - normal tables keep current readable width;
  - wide-table documents expand `#marker-doc` up to a larger max width;
  - extreme tables are wrapped in `div.z2m-table-scroll`.
- Ensure table wrappers preserve anchors and captions.
- Repair table-cell soft breaks only where they are clear line-break artifacts:
  - join `electro chemical` to `electrochemical` if source split occurs inside
    a known word or hyphenated line-break pattern;
  - do not rewrite arbitrary prose.
- Restore statistical significance markers under strict guards:
  - replacement character appears immediately after a p-value;
  - same table or adjacent table note contains `*: statistically significant`;
  - output becomes `*`.
- Restrict roman numeral/footnote suffix splitting to trusted table or footnote
  contexts. Do not split ordinary words, hyphenated words, names, or
  reference-author surnames ending in roman letters such as `v`, `i`, or `x`.
- Protect mixed-case scientific/domain variables such as `Qmax`, `Qavg`,
  `Qave`, `PVR`, and similar compact tokens from table-footnote splitting.
- Keep roman/footnote suffix guards language-neutral: ordinary words in any
  Latin-script language must not be split only because they end in `i`, `v`,
  `x`, `vi`, or `ix`.

### Tests

Add to `tests/test_single_file_html.py`:

- `test_polish_html_document_marks_wide_table_document_width`
  - 19-column table emits wide-table class/style hook.
- `test_polish_html_document_wraps_extreme_table_in_scroll_container`
  - very wide table is inspectable and remains inside the document.
- `test_polish_html_document_preserves_table_anchor_inside_scroll_wrapper`
  - `#table-3` still targets the float/table wrapper.
- `test_polish_html_document_restores_p_value_significance_star`
  - `<0.01�` plus `*: statistically significant` becomes `<0.01*`.
- `test_polish_html_document_does_not_restore_unrelated_replacement_chars`
  - unrelated replacement characters are left for audit.
- `test_polish_html_document_does_not_split_names_ending_in_roman_letters`
  - `Gustav`, `Bulatov`, and `Vinnikov` remain intact.
- `test_polish_html_document_does_not_split_hyphenated_words_as_table_footnotes`
  - `multi-view input` remains intact inside a table cell.
- `test_polish_html_document_does_not_split_mixed_case_table_variables`
  - `Qmax`, `Qavg`, and `Qave` remain intact inside table cells.
- `test_polish_html_document_does_not_split_non_english_words_as_table_footnotes`
  - `Kali-Salpeter`, `Kupfervitriol`, `Mastix`, and `Borax` remain intact.
- `test_polish_html_document_still_splits_table_roman_footnote_suffixes`
  - table-specific cases such as `Foilii` or `sputteringi` still repair.

Add to `tests/test_audit_en_polish.py`:

- `test_analyze_pair_reports_wide_table_without_layout_hook`
- `test_analyze_pair_reports_p_value_replacement_marker_with_star_note`
- `test_analyze_pair_reports_roman_suffix_split_inside_normal_name`
- `test_analyze_pair_reports_roman_suffix_split_inside_reference_author_name`
- `test_analyze_pair_reports_mixed_case_variable_split_as_table_footnote`
- `test_analyze_pair_reports_non_english_word_split_as_table_footnote`

## Workstream 6: Heading And Equation Anchors

### Evidence

- `003`: textual references such as `Equation 8` are not linked even when
  equation rows exist.
- `004`: Appendix B heading contains an embedded page span but no stable ID on
  the whole heading wrapper.
- `013`: equation tags such as `\tag{2.1}` and `\tag{2.4}` are present, but no
  `eq-*` IDs are created. Textual refs such as `Eqn. 2.1)` and `Eqn. 2.4)`
  remain `#page-*` links.

### Implementation

- Assign stable heading IDs to whole heading elements even when a page span is
  embedded inside the heading.
- Preserve page-span anchors as internal markers but never use them as the main
  section target when a heading wrapper can be targeted.
- Assign equation IDs from `\tag{N}` / equation numbers.
- Assign dotted/decimal equation IDs from labels such as `2.1`, `2.4`, and
  `A.3`, using canonical targets such as `eq-2-1`.
- Link textual references such as `Equation 8`, `Eq. (8)`, `Eqn. 2.1`, and
  `(2.1)` under conservative context guards.

### Tests

Add to `tests/test_single_file_html.py`:

- `test_polish_html_document_assigns_heading_id_with_embedded_page_span`
  - whole `h1` gets a stable `section-*` ID.
- `test_polish_html_document_links_equation_text_refs_to_equation_rows`
  - `Equation 8` links to `#eq-8`.
- `test_polish_html_document_assigns_decimal_equation_ids`
  - `\tag{2.1}` creates `id="eq-2-1"`.
- `test_polish_html_document_links_eqn_decimal_refs`
  - `Eqn. 2.1)` links to `#eq-2-1` while preserving visible punctuation.
- `test_polish_html_document_preserves_page_span_inside_heading`
  - page marker remains but is not the main target.

Add to `tests/test_audit_en_polish.py`:

- `test_analyze_pair_reports_heading_page_span_target_without_heading_id`
- `test_analyze_pair_reports_equation_reference_without_equation_target`
- `test_analyze_pair_reports_decimal_equation_ref_left_as_page_link`

## Workstream 7: URL And DOI Link Integrity

### Evidence

- `001` and `006` from the broader review set had DOI text that should be
  clickable.
- `002` had a split URL such as `https://arxi v.org/`.
- `005` references contain DOI links where line/page breaks can split URL text.
- `008` has an anchor whose `href` is a valid ACM DOI URL but whose visible text
  is OCR-damaged as `hps://...`.
- `014`: reference `9` improves from two split URL anchors to one visible URL,
  but an acknowledgments DOI remains plain and split as `doi: 10.1002/
  nau.22813`. The current audit warning points at the repaired URL rather than
  this remaining DOI defect.
- `018`: the supplementary DOI is repaired to one visible anchor in polish, but
  audit still reports it as split, so P36 also needs false-positive reduction.

### Implementation

- Keep DOI detection independent from bibliography citation linking.
- Repair URL tokens split by whitespace inside known URL domains when adjacent
  tokens form a valid URL-like string.
- Repair DOI tokens split by whitespace after a DOI prefix, including
  `doi: 10.1002/ nau.22813`, and make them clickable.
- When an external URL anchor has a valid URL in `href` and the visible text is a
  near-miss OCR form of the same URL, repair the visible text from the `href`.
- Do not convert plain numbers near prose counts into references.

### Tests

Add to `tests/test_single_file_html.py`:

- `test_polish_html_document_links_plain_doi_text_without_rewriting_label`
- `test_polish_html_document_repairs_split_plain_doi_after_prefix`
- `test_polish_html_document_repairs_split_url_token`
- `test_polish_html_document_repairs_visible_url_text_from_href_near_miss`
- `test_polish_html_document_does_not_link_plain_count_as_reference`

Add to `tests/test_audit_en_polish.py`:

- `test_analyze_pair_reports_split_url_anchor`
- `test_analyze_pair_reports_plain_doi_without_link`
- `test_analyze_pair_reports_split_plain_doi_without_link`
- `test_analyze_pair_reports_visible_url_text_disagrees_with_href`
- `test_analyze_pair_does_not_report_repaired_single_url_anchor_as_split`

## Workstream 8: Audit Expansion

### Evidence

Manual review found several defects that current audit did not catch:

- article-level citation style mismatch;
- author-year citations wrongly mapped to a single numeric reference;
- numeric footnote markers in author-year articles linked to bibliography refs;
- duplicate reference labels;
- false ref links in statistical notation;
- all-caps variable split into a table footnote;
- figure/page-span reference not retargeted to wrapper;
- page/ref links inside ordinary word fragments;
- caption-only figure with adjacent orphan image;
- wide table without layout handling;
- p-value replacement marker with star note;
- heading with embedded page span but no heading wrapper ID.
- reference-id drift caused by an unlabeled continuation item;
- bracket citations left as page links after partial same-style repair;
- false reference links in decimal ratings and dotted section ranges;
- false reference links in comma-decimal/statistical values;
- false reference links in numbered method/procedure step references;
- citation visible labels pointing to different `#ref-*` numbers;
- duplicate/collapsed IDs from composite figure/table numbering;
- table caption/target drift and standalone captions adjacent to unwrapped
  tables;
- partial table-reference links that link only the number instead of `Table N`;
- unrelated figure aliases inside a wrapper;
- figure list/range numbers linked as bibliography references;
- visible figure/subfigure refs with no matching semantic target;
- emitted missing-figure warning blocks not counted by audit;
- list-of-figures/table-of-contents entries mistaken for real captions;
- decimal equation references left as page anchors while matching equation tags
  exist;
- front-matter page-anchor glue in author/affiliation markers;
- mixed-case scientific variables split as table footnotes;
- ordinary non-English Latin-script words split as table footnotes;
- flattened superscript-style citations left unlinked;
- ordinary page-break prose left as visible `#page-*` links;
- split plain DOI text left unlinked;
- publisher boilerplate or DOI text concatenated into body prose;
- long TeX macro leaks such as repeated `\@ifnextchar` fragments;
- roman-suffix repair splitting ordinary names/words.

### Implementation

Add or tune audit checks in `scripts/audit_en_polish.py`:

- `P-CIT-STYLE`: bracket citations/references present but no semantic links.
- `P-AUTHORYEAR-NUMERIC-MISLINK`: author-year citations are linked to numeric
  `#ref-*` targets without author/year identity evidence, especially when many
  different citations point to one reference.
- `P-AUTHORYEAR-PAGE-LINK`: author-year citation text remains a visible
  `#page-*` link after polish.
- `P-FOOTNOTE-FALSE-REF`: numeric footnote/source-note marker links to a
  bibliography `#ref-*` in an author-year article.
- `P-REF-DUP-DOTTED`: visible duplicate labels such as `1. 1 .`.
- `P-STAT-FALSE-REF`: `#ref-*` inside `chi2`, `R2`, or Greek/stat notation.
- `P-TABLE-VAR-SPLIT`: all-caps variable followed by `z2m-table-fn`.
- `P-FIG-PAGE-LINK`: page-span figure reference remains while `#fig-N` exists.
- `P-WORD-FRAG-LINK`: `#page-*` or `#ref-*` link text is embedded inside an
  ordinary word fragment.
- `P-FIG-ORPHAN-GRID`: caption-only figure target adjacent to orphan image.
- `P-WIDE-TABLE`: wide table without layout hook or scroll wrapper.
- `P-PVALUE-REPL`: replacement char after p-value and local star note exists.
- `P-HEADING-PAGE-TARGET`: page span inside heading but no heading wrapper ID.
- `P-REF-ID-DRIFT`: `ref-N` assigned to a short continuation-only item and
  later visible raw labels are shifted.
- `P-BRACKET-PAGE-CIT`: bracket citation text remains linked to `#page-*` in a
  high-confidence bracket-citation article.
- `P-DUP-ID`: repeated semantic IDs such as multiple `id="fig-2"` wrappers.
- `P-COMPOSITE-FLOAT-COLLAPSE`: visible `Figure 2.10` / `Table 4.2` is linked
  to a chapter-only target such as `#fig-2` / `#table-4`.
- `P-TABLE-CAPTION-TARGET-DRIFT`: visible table caption number and wrapper ID
  disagree, or a caption is attached to the wrong adjacent table.
- `P-TABLE-CAPTION-UNWRAPPED`: standalone table caption is adjacent to an
  unwrapped table.
- `P-TABLE-PARTIAL-LINK`: only the number inside `Table N` is linked.
- `P-FIG-ALIAS-MISPAIR`: a wrapper contains aliases/captions for unrelated
  visible figure numbers.
- `P-FIG-LIST-FALSE-REF`: a figure list/range reference such as
  `(Figs. 3 and 5)` contains `#ref-*`.
- `P-FIG-REF-NO-TARGET`: visible `Figure N`, `Figure 4A`, or `Figure 3D`
  appears but no compatible `fig-*` target exists.
- `P-MISSING-FIG-WARNING`: polish emitted a missing-figure warning block.
- `P-INDEX-CAPTION-FP`: list-of-figures/list-of-tables rows are reported as
  caption-without-image defects.
- `P-DECIMAL-FALSE-REF`: linked `#ref-*` pairs render a decimal rating/value.
- `P-COMMA-DECIMAL-FALSE-REF`: linked `#ref-*` pairs render comma-decimal or
  statistical values such as `1,5` or `3,1`.
- `P-SECTION-RANGE-FALSE-REF`: dotted section/chapter range contains `#ref-*`.
- `P-STEP-FALSE-REF`: method/procedure step references such as `steps 2 and 3`
  contain `#ref-*`.
- `P-REF-LABEL-MISMATCH`: linked citation text contains number `N` but the href
  points to a different `#ref-M`.
- `P-EQ-PAGE-LINK`: an equation reference remains linked to `#page-*` while a
  matching equation tag/target exists or can be inferred.
- `P-FRONT-MATTER-PAGE-GLUE`: front matter contains page anchors glued to
  author names or affiliation markers.
- `P-MIXEDCASE-VAR-SPLIT`: compact variables such as `Qmax` are split by
  `z2m-table-fn`.
- `P-NONEN-WORD-FN-SPLIT`: ordinary non-English Latin-script words are split by
  `z2m-table-fn`.
- `P-FLAT-CIT-UNLINKED`: flattened superscript citation tokens such as
  `et al3` or sentence-final `.3` remain unlinked when `ref-3` exists and the
  article style is superscript numeric.
- `P-PROSE-PAGE-LINK`: visible `#page-*` links contain ordinary prose
  continuation text.
- `P-DOI-SPLIT-PLAIN`: DOI text is split by whitespace and remains unlinked.
- `P-BOILERPLATE-MERGED`: DOI/copyright/page boilerplate text is concatenated
  into a body paragraph.
- `P-TEX-MACRO-LEAK`: long TeX macro/control-sequence artifacts remain visible.
- `P-ROMAN-SPLIT-WORD`: normal names, hyphenated words, or prose words are
  split before roman letters.

### Tests

Add focused fixtures to `tests/test_audit_en_polish.py` for every new audit
check. Each fixture should be small HTML strings written to temporary raw/polish
files and passed through `analyze_pair`.

## Commit Plan

### Commit 1: Citation style and reference identity

Includes:

- Workstream 1 detector.
- Workstream 2 reference normalization.
- Core citation/reference tests.

Verification:

- `python -m pytest tests/test_single_file_html.py -q`
- `python -m pytest tests/test_audit_en_polish.py -q`
- repolish `001-005`, inspect reference/citation snippets.

### Commit 2: Protected zones for math, units, front matter, table variables

Includes:

- Workstream 3 guards.
- False-positive tests for author affiliations, units, `chi2`, `R2`, and
  `QMAX`.

Verification:

- targeted `pytest -k "citation or reference or unit or table_variable or chi"`
- repolish `003-005`, inspect affected snippets.

### Commit 3: Float units, boxes, figure grids, reading order

Includes:

- Workstream 4 box wrapper/linking.
- Figure-grid pairing.
- Float-aware continuation repair and page-figure retargeting.

Verification:

- targeted `pytest -k "figure or float or box"`
- repolish `001`, `004`, `005`, inspect Box 1, Figure 15/16, Figure 18/19,
  Figure 1 continuation.

### Commit 4: Wide tables and table marker cleanup

Includes:

- Workstream 5 layout hooks.
- p-value star repair.
- table soft-break and all-caps regression tests.

Verification:

- targeted `pytest -k "table or wide or p_value"`
- browser/manual check of `005` Table 3.

### Commit 5: Heading/equation anchors and URL/DOI integrity

Includes:

- Workstream 6 heading/equation anchors.
- Workstream 7 URL/DOI repairs.

Verification:

- targeted `pytest -k "heading or equation or doi or url"`
- inspect `003` equations, `004` Appendix B, `002` split URL once included.

### Commit 6: Audit expansion

Includes:

- Workstream 8 checks.
- Audit fixtures.

Verification:

- `python -m pytest tests/test_audit_en_polish.py -q`
- run pair audit over the five reviewed Meine articles and confirm new checks
  catch pre-fix failures, then clear after repolish.

## Five-Article Acceptance Matrix

| Article | Must improve | Must not regress |
| --- | --- | --- |
| `001` | Box framing/linking; citation superscript recovery; figure caption continuity | Do not link box headings as references; do not merge box text into body |
| `002` | Page furniture removal; split URL repair; false count link prevention | Do not remove real article title/content; do not break valid references |
| `003` | Author affiliations and unit exponents stay unlinked; equation refs link | Do not lose existing equation displays or bibliography links |
| `004` | Bracket refs link; `QMAX` preserved; Appendix B whole-heading target; figure grids pair correctly | Do not over-pair unrelated images/captions; do not superscript all-caps variables |
| `005` | Figure 1 no longer splits prose; `chi2` unlinked; Table 3 readable; p-value stars restored; refs deduped | Do not remove DOI/PMID links; do not flatten wide-table content |

## Final Verification After Implementation

1. Run focused unit tests for the touched workstream.
2. Run full polish/audit tests:
   `python -m pytest tests/test_single_file_html.py tests/test_audit_en_polish.py -q`
3. Repolish the five reviewed Meine articles from raw.
4. Rebuild the manual review bundle for these articles.
5. Run pair audit on the repolished set.
6. Compare against `docs/MEINE_EN_POLISH_MANUAL_REVIEW_2026-04-30.md`:
   - every `introduced_by_polish` item must be gone or downgraded to an audit
     warning;
   - every `not_fixed_by_polish` item must be fixed or explicitly marked as
     raw-only/not safely recoverable;
   - every new audit check must detect at least one pre-fix fixture.

## 018-025 Iteration - 2026-05-02

### Implemented Universal Fixes

- Unicode front-matter author detection now counts capitalized name pairs and
  glued affiliation markers with diacritics. This prevents affiliation markers
  in author lines such as Krhut/Gärtner/Sýkora/Zvarová from becoming
  bibliography links while preserving body numeric citations.
- Split page-linked bracket citations are recovered even when Marker puts
  brackets inside separate page anchors, for example
  `<a href="#page">[3</a>, <a href="#page">5]</a>`.
- Existing page links to figure subpanels are retargeted to semantic figure
  anchors when the base figure exists: `Fig. 1a-c`, `Fig. 2d,e`, `Fig. 2g-i`.
- Page links on unresolved `Fig.`/`Table` references are unwrapped when no
  semantic target exists. This removes misleading `#page-*` links without
  inventing fake figure/table targets.
- Linked unit exponents are repaired for additional physical units:
  `N m2`, `nm d^-1`, `cm^-3`, and related negative exponent forms no longer
  point to `#ref-1/#ref-2/#ref-3`.
- Table-footnote roman repair now joins `Matr<sup>ix</sup>` back to `Matrix`.
- Audit `P59` now treats an article with five or more superscript numeric
  reference links as numeric-citation-dominant, avoiding a false author-year
  footnote warning on numeric-style articles.

### Regression Tests Added

- `test_polish_html_document_does_not_link_unicode_author_affiliation_markers`
- `test_polish_html_document_repairs_split_page_linked_bracket_list`
- `test_polish_html_document_repairs_already_linked_unit_exponent`
  extended for `N m2`, `nm d^-1`, and `cm^-3`.
- `test_polish_html_document_retargets_existing_page_figure_link`
  extended for subpanel lists/ranges.
- `test_polish_html_document_unwraps_unresolved_semantic_page_links`
- `test_polish_html_document_repairs_table_word_splits_without_losing_roman_text`
  extended for `Matrix`.
- `test_analyze_pair_does_not_report_p59_for_numeric_citation_dominant_article`

### Verification Snapshot

- Targeted polish tests:
  `python -m pytest -q tests\test_single_file_html.py -k "already_linked_unit_exponent or unresolved_semantic_page_links or retargets_existing_page_figure_link or split_page_linked_bracket or table_word_splits or unicode_author_affiliation"`
  -> `7 passed`.
- Targeted audit tests:
  `python -m pytest -q tests\test_audit_en_polish.py -k "p59 or recent_meine_manual_blind_spots"`
  -> `2 passed`.
- Re-polish report:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_018_025_after_fixes_2026-05-02.json`
  -> `articles=8 changed=2 inlined_images=182 missing_images=0`.
- Pair audit report:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_018_025_after_fixes_2026-05-02.json`
  -> `page_links=0`, `raw_img=182`, `polish_img=182`,
  `ref_links=409`, `fig_links=215`, `table_links=47`,
  `bad_chars=0`, `missing_img=0`.

### Residual Patterns

- Float-aware reading order still needs a safer general rule. It remains visible
  in `018`, `023`, and `024` as `P30/P40`.
- Missing semantic figure targets remain raw/PDF-diagnostics work in `022` and
  `024`, and OCR/book-policy work in `023`.
- Variable typography still needs a broader but conservative rule for forms
  such as `D eff`.
- Audit precision still needs tuning for valid high-number medical citations
  reported by `P60`.

## 018-025 Manual Follow-up - 2026-05-02

### Additional Universal Fixes Implemented

- Common mojibake replacement now handles double-encoded punctuation, micro,
  omega, degree, multiplication, and copyright artifacts in a stable
  longest-first pass.
- Float-aware sentence repair now:
  - avoids classifying long body prose as front matter just because it contains
    many capitalized place/person-like names;
  - treats image-only paragraphs as float gaps when they sit next to wrapped
    figure/table/box units;
  - merges the continuation paragraph back into prose while leaving the float
    run intact after the repaired sentence.
- Known word-glue repairs run again after page/float merges, fixing merge-made
  age artifacts such as `6year-old`; `7 year-old` also normalizes to
  `7-year-old`.
- Effective variables render as subscripted forms for both plain `D eff` and
  tagged `<i>D</i> eff`.
- Plain unit exponents normalize in scientific prose:
  `10-13 cm-2 s -1` -> `10^-13 cm^-2 s^-1` markup.
- Formula fragments such as `ZrAl x O y` normalize to subscripted chemical
  formula markup, and `P45` ignores already-subscripted formulas.
- Reference-list cleanup strips duplicate bare leading numbers after generated
  `z2m-ref-num` spans.

### Regression Tests Added Or Extended

- `test_inline_images_adds_readability_and_repairs_common_text_artifacts`
- `test_polish_html_document_strips_bare_duplicate_ref_prefix`
- `test_polish_html_document_repairs_sentence_split_by_float_run_after_long_body_paragraph`
- `test_polish_html_document_repairs_sentence_split_by_image_then_table_float`
- `test_polish_html_document_repairs_common_scientific_word_glue`
- `test_polish_html_document_normalizes_plain_negative_unit_exponents`
- `test_polish_html_document_normalizes_latex_dimension_times_and_oxide_subscripts`
- `test_analyze_pair_does_not_report_p45_for_formula_subscripts`

### Verification Snapshot

- `python -m pytest -q tests\test_single_file_html.py` -> `230 passed`.
- `python -m pytest -q tests\test_audit_en_polish.py` -> `19 passed`.
- Final repolish:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_018_025_after_manual_review_final_2026-05-02.json`
  -> `articles=8 changed=1 inlined_images=182 missing_images=0`.
- Final pair audit:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_018_025_after_manual_review_final_2026-05-02.json`
  -> `page_links=0`, `raw_img=182`, `polish_img=182`, `bad_chars=0`,
  `missing_img=0`.

### Updated Residual Patterns

- `018`, `020`, and `025` are clean in the final pair audit.
- `024` no longer has the `All authors independently screened all the ...
  retrieved articles` table interruption; remaining issue is weak/missing
  figure target discovery.
- `019` remaining normal-article issues: likely audit false positive near a
  valid citation in WVTR prose, and raw/figure-assembly issue for `Figure 2f`
  without nearby image.
- `021` remaining `P60` appears to be audit precision around a valid citation
  `83`.
- `022` and `024` need figure-target recovery from raw/PDF diagnostics.
- `023` remains OCR/book-like and belongs to the future OCR-specific polish
  sketch/policy rather than normal EN article tuning.

## 001-025 Orphan Figure Target Recovery - 2026-05-02

### Universal Fix Implemented

- Added conservative recovery of semantic `fig-*` targets for Marker orphan
  figure images when the explicit caption label is missing but nearby prose
  still contains a visible `Fig./Figure N` reference.
- The rule is intentionally bounded:
  - candidate images must look like Marker figure extractions
    (`_page_*_Figure_*.jpeg/png/webp/gif` or `FigureN.*`);
  - table-adjacent images are excluded;
  - unlabeled panel legends can bind to the missing predecessor before the next
    known numbered figure;
  - ordered orphan image runs can bind to nearby following figure references;
  - a single orphan image can bind to one unambiguous preceding figure
    reference, with preceding references taking priority over later prose.
- This repaired the safe target-recovery cases seen in `017`, `022`, and
  `024` without changing the 7-article control set.

### Regression Tests Added

- `test_polish_html_document_recovers_unlabeled_panel_figure_target`
- `test_polish_html_document_recovers_ordered_orphan_figure_targets`
- `test_polish_html_document_recovers_next_unassigned_orphan_figure_ref`
- `test_polish_html_document_recovers_orphan_figure_after_nearby_ref`
- `test_polish_html_document_does_not_recover_after_ambiguous_previous_refs`
- `test_polish_html_document_does_not_recover_table_adjacent_image_as_figure`

### Verification Snapshot

- `python -m pytest -q tests\test_single_file_html.py` -> `236 passed`.
- `python -m pytest -q tests\test_audit_en_polish.py` -> `19 passed`.
- 7-article control repolish:
  `md_output\new\_quality_audit\repolish_after_orphan_figure_recovery_2026-05-02.json`
  -> `articles=7 changed=0 inlined_images=80 missing_images=0`.
- 7-article control audit:
  `md_output\new\_quality_audit\en_polish_pair_audit_after_orphan_figure_recovery_pdfdiag_2026-05-02.json`
  -> `raw_img=80`, `polish_img=80`, `page_links=1`, `bad_chars=0`,
  `missing_img=0`; no new image loss.
- Meine `001-025` repolish:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\repolish_meine_001_025_after_orphan_figure_recovery_2026-05-02.json`
  -> `articles=25 changed=2 inlined_images=425 missing_images=0`.
- Meine `001-025` audit:
  `md_output\meine_full_library_en_polish_2026-04-28_single_loop\_quality_audit\en_polish_pair_audit_meine_001_025_after_orphan_figure_recovery_2026-05-02.json`
  -> `raw_img=425`, `polish_img=425`, `fig_links=523`, `bad_chars=0`,
  `missing_img=0`.

### Updated Residual Patterns

- `022` no longer has the missing `Fig. 1A` semantic target.
- `024` now recovers safe targets for `Fig. 1` and `Fig. 2`; the remaining
  `Fig. 3` target should wait for PDF/raw-region diagnostics because the
  nearest later extracted objects are separated by table material and are not
  safe to auto-assign.
- `017` now recovers `Figure 4A/Figure 4`; the remaining `Figure 3` target is
  not assigned because the nearby extraction is a `Picture` artifact rather
  than a Marker `Figure` image.

## Full 001-082 Repass PDF-Map And Roman Repairs - 2026-05-15

### Universal Fixes Implemented

- Pair audit can now load a Zotero-derived PDF map with `--pdf-map`, so
  PDF-aware diagnostics are no longer limited to articles that have a local
  `00.source.pdf` beside the HTML stages.
- The audit blind-spot list now includes split e-mail local parts (`P64`), and
  `P45` ignores valid bibliography volume strings such as `v. 13`.
- EN polish repairs the repeated roman-suffix false splits found during the
  full manual pass:
  `NHP s41`, `Abdusalomo v et al.`, `V. Bulato v. Scientific...`,
  `Hale vi suggests/proposed`, and `simono v@...`.

### Regression Tests Added Or Extended

- `test_build_report_uses_external_pdf_map_for_pdf_diagnostics`
- `test_load_pdf_map_accepts_zotero_candidate_records`
- `test_polish_html_document_repairs_acronym_plural_page_link_citation`
- `test_polish_html_document_rejoins_surname_v_before_et_al_and_reference_sentence`
- `test_polish_html_document_rejoins_vi_surname_before_reporting_verb`
- `test_polish_html_document_rejoins_roman_split_email_local_part`
- `test_audit_recent_manual_blind_spots_are_covered` now covers `P64`.
- `test_analyze_pair_ignores_known_false_positive_patterns` now covers
  `American Journal of Photography v. 13`.

### Verification Snapshot

- Targeted tests:
  `python -m pytest -q tests\test_single_file_html.py tests\test_audit_en_polish.py`
  -> `287 passed`.
- Full test suite:
  `python -m pytest -q` -> `304 passed` with the existing `.pytest_cache`
  access-denied warning on this machine.
- Final full-repass repolish:
  `.tmp_local2\analysis\repolish_meine_001_082_after_roman_email_halevi2_fixes_2026-05-15.json`
  -> `article_count=82`, final pass `changed_count=1`,
  `inlined_image_count=1726`, `missing_image_count=0`.
- Final PDF-aware full-repass pair audit:
  `.tmp_local2\analysis\pair_audit_meine_001_082_final_pdfmap_2026-05-15.json`
  -> `article_count=82`, clean `51`, residual `31`,
  `source_pdf_present=81`, `polish_missing_local_images=0`.

### Updated Residual Patterns

- Fixed by code in this pass:
  `meine_0001_3944c69948`, `meine_0003_b9eaf6e854`,
  `meine_0015_be8f26bb9b`, `meine_0090_f9583a0fd3`, and
  `meine_0134_edd06dc6d2`.
- Remaining work should focus on figure wrapper/target completeness
  (`P39/P61/P62`), table/list extraction (`P13/P50`), numeric
  citation-vs-line-number ambiguity (`P04/P05/P59/P60`), and the PDF
  end-section order diagnostic (`P24`).
