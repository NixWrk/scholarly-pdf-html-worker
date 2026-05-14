# EN Polish Commit Plan 2026-04-27

Purpose: incremental commit roadmap for bringing EN autopolish close to ideal
on the current seven articles while making the behavior reusable for future
papers.

## Current Implementation Status

The current working tree implements the planned repair stack as one continuous
pass, with regression coverage.

Verification:

- `python -m pytest tests/test_single_file_html.py tests/test_audit_en_polish.py -q`
  -> 169 passed, 1 cache-permission warning.
- `python scripts\repolish_en_from_raw.py --roots md_output\new\electrodes_W7TECQDX md_output\new\headless_intracranial md_output\new\headless_llm_medicine --table-caption-language en --out-report md_output\new\_quality_audit\repolish_en_from_raw_after_universal_commit6_2026-04-27.json`
  -> 7 articles, 1 changed, 80 inlined images, 0 missing images.
- `python scripts\audit_en_polish.py --roots md_output\new\electrodes_W7TECQDX md_output\new\headless_intracranial md_output\new\headless_llm_medicine --pdf-diagnostics --out md_output\new\_quality_audit\en_polish_pair_audit_after_universal_commit6_pdfdiag_2026-04-27.json`
  -> 7 pairs, 1021 reference links, 268 figure links, 24 table links,
  defects: none.
- `python scripts\collect_en_polish_review.py --roots md_output\new\electrodes_W7TECQDX md_output\new\headless_intracranial md_output\new\headless_llm_medicine --out manual_review_en_polish_inlined_2026-04-27_round4`
  -> 7 review files, 80 inlined images, 0 missing images.

Recommended commit slicing from the current diff:

1. Audit expansion and report docs.
2. Reference/citation/front-matter protection repairs.
3. Float wrappers, caption merge, and reading-order repairs.
4. Terminal section, footnote, and scientific notation repairs.
5. OCR recovery and final regression tests/repolish reports.

## Commit 1: Audit Contract And Low-Risk Guards

Goal: make known Round 2.5 blind spots visible and apply safe structural guards.

Scope:

- Add audit checks for late `z2m-front-matter` body paragraphs, citation-like
  math superscripts, unlinked numeric superscript ranges, missing visible
  bibliography numbers/gaps, duplicate bracketed bibliography prefixes,
  conjunction-before-float reading-order risks, and joined scientific/prose
  tokens.
- Tighten low-risk transforms: do not merge an unnumbered bibliography item into
  the previous reference unless it has continuation evidence; bound front-matter
  detection to the article-start region; convert `\(^{...}\)` citations after
  math conversion as well as before; treat standalone page-anchor spans as
  transparent between prose and floats.

Expected local wins:

- Ahmed `Best Stainless...` gets its own `ref-58` instead of being absorbed into
  `ref-57`.
- Teo later body paragraphs are no longer protected as front matter.
- Teo `\(^{71-73}\)` and `<sup>134-139</sup>` can enter normal citation linking.
- Li Figure 2-style splits have a better chance of being repaired despite
  intervening page anchors.

## Commit 2: Citation Identity And Recovery

Goal: stabilize all citation targets before expanding more syntax.

Scope:

- Complete bibliography identity model: visible number map, gap warnings, and
  true continuation vs unnumbered-entry classification.
- Retarget `#page-*` links inside bibliography entries to whole `#ref-*`
  entries.
- Link superscript ranges/lists after protection and math conversion.
- Preserve model/version, footnote, unit, and front-matter guards.

Expected local wins:

- Ahmed reference 58 and later numeric citations stabilize.
- Li author-year links stay stable.
- Teo citation ranges become clickable without relinking `Grok 4`.

## Commit 3: Float Unit And Reading Order

Goal: make figures/tables atomic, targetable units and prevent them from
splitting sentences.

Scope:

- Strengthen figure/table wrapper assembly.
- Associate caption continuations, URLs, and table notes with the wrapper.
- Repair continuation around wrappers and legacy image/caption blocks.
- Preserve Wang Table III as a regression fixture.

Expected local wins:

- Ahmed Figure 8 visible caption becomes one caption flow.
- Li Figure 2 no longer interrupts the nerve-fiber sentence.
- Teo Table 1 remains separate from body validation prose.

## Commit 4: Terminal Sections And Footnotes

Goal: repair article-end ordering and page notes without touching ordinary body
content.

Scope:

- Reorder terminal sections only inside the end-of-document region.
- Keep `FUNDING`, `SUPPLEMENTARY MATERIAL`, and `REFERENCES` semantically
  separated.
- Extract page footnote blocks into dedicated callouts.

Expected local wins:

- Kaiju end sections are restored.
- Li footnote text leaves body flow.

## Commit 5: Scientific Text Normalizer

Goal: normalize compact scientific notation with context guards.

Scope:

- Expand unit and word-boundary normalization.
- Split prose-bearing math snippets.
- Normalize oxide formula suffixes only in material contexts.
- Repair local equation-defined variables in nearby explanatory prose.

Expected local wins:

- Schelles `Vwater`, `0.04for`, `20nCfor`, and CIC punctuation improve or warn.
- Merken oxide formulas normalize.
- Kaiju `iECoG(t) j`, `(x j, yj)` prose is repaired.

## Commit 6: PDF Evidence Adapter

Goal: use local PDF text as optional evidence for ambiguous cases.

Scope:

- Add local PDF-text comparison helpers for captions, references, terminal
  sections, and suspicious OCR citation damage.
- Keep PDF unavailable as a supported path.

Expected local wins:

- Ahmed Figure 8 caption repair becomes higher confidence.
- Teo `task. Sec.` / `6,000` can be flagged or repaired with evidence.
- Kaiju terminal order can be confirmed.

## Commit 7: Full Repolish And Review Bundle

Goal: regenerate, audit, and manually verify.

Scope:

- Run repolish on all seven current articles.
- Run expanded audit with PDF diagnostics.
- Generate a new inlined/self-contained review bundle.
- Update the Round 2.5 follow-up notes with resolved/open status.
