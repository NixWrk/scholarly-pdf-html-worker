# Polish Float And Math Regression Observations

Date: 2026-05-15
Branch observed: `fix/pdf-derived-citation-profile`
Repository: `D:\Git_Code\pdf-html-translator`

## Context

This note records the current diagnosis of two related regressions in the EN polish stage:

1. Worse reconstruction of prose split by figures, tables, boxes, page furniture, and footnotes.
2. Worse or inconsistent rendering of formulas, inline math, display equations, and unit expressions.

The investigation compared the split-out repository against the earlier `ZoteroPDF_2_MD` version and inspected the main polish pipeline in `src/zoteropdf2md/single_file_html.py`.

## Main Finding

The current EN polish stage does not have one stable document model for reading order, floats, formulas, units, and citations. Instead, it uses a long sequence of regex-oriented repair passes. Many of these passes were added to fix real local defects from the seven-article and Meine review sets, but their interaction is now fragile.

The visible result is that some cases improve locally, while future articles or noisier Marker output expose regressions:

- body text split by a figure/table may remain split;
- body text can be merged only in simple `p -> gap -> p` shapes;
- formula-like unit snippets may be converted to plain text;
- true formulas may remain raw TeX if MathJax does not render;
- citation superscripts and unit exponents can compete for the same `<sup>` tokens;
- display equations are repaired only when they match a limited set of expected shapes.

## Prose Split Around Figures And Tables

Relevant code areas:

- `_add_figure_anchors`
- `_add_table_anchors`
- `_wrap_box_units`
- `_wrap_float_units`
- `_repair_sentence_breaks_around_figure_blocks`
- `_repair_sentence_breaks_around_float_units`
- `_is_sentence_continuation`

The current repair works best when the structure is simple:

```text
left prose paragraph -> already-recognized float/gap -> right prose paragraph
```

It is much weaker when the gap contains several heterogeneous blocks:

- image without a stable figure target;
- caption split away from image;
- table caption separated from table;
- footnote or table note;
- page header/footer residue;
- box heading/body;
- front matter fragments;
- list items or heading-like blocks;
- OCR/Marker artifacts.

Specific mechanical limits observed:

- `_repair_sentence_breaks_around_float_units` depends too much on successful float wrapping into `div.z2m-float-unit`.
- If a figure/table is not semantically wrapped, the later continuation repair often cannot treat it as a movable non-prose gap.
- The late repair scans only a limited number of gap nodes.
- It refuses some candidate right paragraphs when the right paragraph already has an `id`.
- `_is_sentence_continuation` is intentionally conservative and mostly catches lowercase continuations; hyphenated page splits and uppercase continuations are under-covered.
- Recent wrapper logic became safer and more conservative, which reduces false grouping but also reduces the number of blocks that become repairable float gaps.

The earlier and split-out versions behaved the same on several spot-checked raw samples, so this is not just one new typo in the split-out repository. The larger Meine corpus is exposing shapes that the existing repair model never covered well.

## Formula And Math Rendering

Relevant code areas:

- `_unwrap_spurious_math_captions`
- `_fix_subscript_equation_spill`
- `_convert_math_tags_to_tex`
- `_fix_equation_display`
- `_normalize_scientific_units`
- `_mark_unit_exponent_superscripts`
- `_convert_latex_sup_citations`
- `_recover_citations_leaked_into_tex_units`
- `_repair_ref_links_absorbed_decimal_or_unit_text`
- `_fix_false_sup_citations_in_decimals_and_figure_labels`
- `_inject_mathjax`

Current behavior is mixed by design:

- true math is usually kept as TeX and rendered by MathJax;
- simple unit/dimension expressions are often converted to plain HTML text plus `<sup class="z2m-unit-exp">`;
- some prose-bearing math snippets are unwrapped into normal text;
- citation-like math superscripts may be promoted to bibliography superscripts.

That policy solved real defects from Merken, Schelles, Kaiju, and related reviews, but it is fragile because formulas, units, citations, and superscripts are not classified first. They are repaired opportunistically as the pipeline progresses.

Main risks:

- If MathJax is unavailable or slow, valid TeX remains visibly raw in the final HTML.
- Unit expressions and real formulas are distinguished by heuristics rather than a durable role model.
- Citation linking and unit exponent normalization both operate on `<sup>` and `^{...}` patterns.
- Display equation repair mainly recognizes `block-type="Equation"`, `\[...\]`, and trailing equation numbers like `(1)`.
- Prose swallowed into math is only extracted for known patterns; unknown article-specific formula/prose mixtures can remain broken.
- String-level tests can pass while actual browser rendering still looks wrong.

## Test Check Performed

Focused tests were run for the current code:

```text
python -m pytest -q tests\test_single_file_html.py -k "sentence_split or float"
20 passed, 245 deselected

python -m pytest -q tests\test_single_file_html.py -k "math or equation or unit or cic or ohm or exponent or formula"
42 passed, 223 deselected
```

The passing tests show that current handcrafted fixtures still work. They do not prove that the full corpus renders correctly, because the tests mostly assert HTML substrings and do not verify browser-rendered MathJax output or full-document reading order.

## Root Cause Summary

The polish stage needs a stronger intermediate representation. The current pipeline repeatedly rewrites raw HTML with regexes, but the decisions depend on roles that are not made explicit early enough:

- body prose;
- figure unit;
- table unit;
- box unit;
- caption;
- table note;
- footnote;
- page furniture;
- true display math;
- true inline math;
- simple unit expression;
- citation superscript;
- unit exponent;
- prose accidentally swallowed by math.

Without these roles, each repair pass has to rediscover context locally, and passes can undo or constrain one another.

## Recommended Direction

1. Build a block-role stream before late polish repairs.

   Classify document nodes into prose, float, caption, note, page furniture, math, unit, citation, and protected/reference areas. Use this role stream for reading-order repairs instead of scanning only local regex patterns.

2. Decouple prose-continuation repair from successful float wrapping.

   Even when a figure/table is not fully wrapped, visually non-prose blocks should be treated as crossable gaps if they are classified safely.

3. Replace the simple `p -> gap -> p` continuation model with a role-aware continuation pass.

   It should support controlled crossing of multiple non-prose blocks and handle hyphenated page splits such as `ex- ... cluded`.

4. Introduce explicit math policy classes.

   Suggested classes:

   - `true_math`: keep as MathJax TeX or MathML;
   - `display_equation`: preserve display layout and equation number;
   - `unit_expression`: convert to stable HTML text plus `z2m-unit-exp`;
   - `table_dimension`: normalize as text/HTML inside cells;
   - `citation_sup`: link only after citation-profile validation;
   - `prose_in_math`: unwrap only when high-confidence.

5. Make citation profile detection feed the math/unit decision.

   If the current branch is adding PDF-derived citation-profile logic, that profile should decide whether numeric superscripts are likely references before unit exponents are touched. This is important for future articles with different citation styles.

6. Add browser-rendered checks for MathJax.

   Unit tests should keep substring checks, but regression review also needs a rendered HTML check that detects raw TeX leakage and broken display equations.

7. Promote real corpus snippets to fixtures.

   Add fixtures from the Meine and seven-article cases:

   - sentence split by figure/table/box;
   - hyphenated page split through non-prose blocks;
   - figure caption/body interleaving;
   - CIC prose-bearing math;
   - Merken dimension prose math;
   - table-cell dimensions;
   - base-10 exponents that are not references;
   - citation superscripts that are not unit exponents;
   - unit exponents that are not citations.

## Practical Next Step

For the current branch, the safest next implementation step is not to add more broad regexes. First add a small role/classification layer and tests around it, then route both citation-profile decisions and math/unit repair through that layer. This should make local fixes useful for future articles instead of only correcting the current corpus.

## Implemented Float-Prose Repairs - 2026-05-20

The production polish path now has a safer global repair for prose interrupted by
one or more float blocks. The motivating real case was the Franco 2018 uroflow
article, where tables interrupted sentences in the English HTML before
translation:

- `... has greater variability` + tables 1-2 + `with higher error rates ...`
- `... (Supplemental Table S3). We` + tables 3-5 + `can see that ...`

Implemented behavior in `src/zoteropdf2md/single_file_html.py`:

- `_repair_sentence_breaks_around_float_units()` now runs iteratively, so it can
  bridge more than one adjacent float/table/figure run instead of only one
  simple `p -> float -> p` shape.
- Duplicate nested float wrappers with the same `id` are collapsed. This matters
  when source HTML is already partly polished and `_wrap_float_units()` sees an
  existing `div.z2m-float-unit`.
- Standalone punctuation paragraphs such as `<p> . </p>` are treated as
  non-prose gaps when they sit between float units.
- The continuation guard supports Cyrillic text and short multi-word left
  fragments such as `We can clearly` when the right paragraph is a plausible
  lowercase continuation.
- False `z2m-front-matter` markings no longer prevent a valid prose
  continuation repair.

The repair is still deliberately conservative. It does not blindly merge every
paragraph surrounding a table or figure, because false merges can corrupt
reading order. Examples that must remain guarded:

```text
The baseline characteristics are shown in Table 1
[Table 1]
the secondary analysis was performed only in adults.
```

If the source lost a period after `Table 1`, this may still be two independent
sentences rather than one interrupted sentence.

```text
We can
[Table 2]
Table 2 shows the final values.
```

Here `We can` may be an OCR residue or incomplete fragment, while the right side
is a table caption/prose start, not necessarily its continuation.

Therefore the current rule only crosses blocks that are already recognized as
non-prose gaps, and it still requires the right side to look like a sentence
continuation. This keeps the fix aggressive for clear float-split cases while
avoiding broad paragraph reordering.

Regression coverage added in `tests/test_single_file_html.py`:

- multiple adjacent floats inside one interrupted sentence;
- Russian text split by several tables;
- English text split after a false `z2m-front-matter` mark;
- pre-wrapped table runs that would otherwise become nested wrappers;
- punctuation-only paragraphs between table runs;
- short multi-word left fragments such as `We can clearly`.

Validation after the change:

```text
python -m pytest -q tests/test_single_file_html.py
301 passed, 1 warning

python -m pytest -q
399 passed, 6 warnings
```
