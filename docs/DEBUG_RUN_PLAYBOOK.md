# Debug Run Playbook

This document is the mandatory debugging rule for HTML, EN polish, RU
translation, and RU polish changes.

## Rule 0: One Defect, One Hypothesis

Do not batch unrelated symptoms into one fix.

For every observed defect:

1. Record the exact article, stage, file path, and snippet.
2. State one root-cause hypothesis before editing code.
3. Check the same pattern across the whole control corpus.
4. Fix the shared mechanism, not the single visible snippet.
5. Add or update a regression test for the mechanism.
6. Re-run the relevant control scope and compare against the previous run.
7. Commit only if the target defect improves and no tracked metric regresses.

## Control Corpus

Use the current debug corpus until it is intentionally replaced:

1. Ahmed 2026, electrodes collection.
2. Kaiju 2017, electrodes collection.
3. Li 2026, electrodes collection.
4. Merken 2022, electrodes collection.
5. Schelles 2025, electrodes collection.
6. Wang 2017, headless/intracranial control.
7. Teo 2025, headless/LLM medicine control.

If a change is article-specific by design, explicitly say so in the commit
message or audit note. Otherwise, assume the change must be validated across
the control corpus.

## Stage Artifacts

Every debug run must keep these artifacts while the pipeline is being tuned:

1. `01.en.raw.html`: raw Marker HTML.
2. `02.en.polish.html`: EN polish output.
3. `03.ru.translate.html`: Gemma output before final RU polish.
4. `04.ru.polish.html`: final RU polish output.
5. A stage log for each article or batch.
6. A machine-readable comparison report when possible.

The stage where the defect first appears determines where to debug:

| First broken stage | Debug target |
|---|---|
| `01.en.raw.html` | Marker/PDF extraction or source PDF structure |
| `02.en.polish.html` | EN polish / `single_file_html.py` |
| `03.ru.translate.html` | Gemma segmentation, prompts, masks, recovery |
| `04.ru.polish.html` | RU polish, label normalization, link cleanup |

For EN raw triage, use the article-level matrix in
[`EN_RAW_DEBUG_TEST_PLAN.md`](EN_RAW_DEBUG_TEST_PLAN.md).

For EN polish citation or internal-link defects, preserve the extra production
inputs. `02.en.polish.html` uses a citation profile built from the source PDF
and, when available, Zotero/pdf.js overlay JSON. A raw-only repolish can hide or
create link regressions and must not be used as the validation run for
reference, figure, table, or page-link quality.

## Run Ladder

Use the smallest run that can falsify the hypothesis, then widen.

1. Static inspection: grep snippets, inspect HTML around the defect, inspect
   the matching log lines.
2. Unit/regression test: reproduce the mechanism without the model when
   possible.
3. Postprocess-only run: use existing stage artifacts when only polish/link/
   cleanup code changed. For link-sensitive EN polish checks, use
   `scripts/pdf_profile_lab.py` with `_source_filename_map.csv` and optional
   `--zotero-overlay-dir`; use `scripts/repolish_en_from_raw.py` only for
   raw-HTML-only text/float/math checks.
4. Translation-only run on one article: use fixed `02.en.polish.html` input
   when only Gemma logic changed.
5. Translation-only run on the control corpus: required before calling a
   Gemma fix stable.
6. Full PDF to EN raw run: required when Marker extraction, source selection,
   staging, or EN polish behavior may have changed.
7. Full PDF to final RU run: required before declaring the pipeline release
   quality.

## Required Metrics

Each comparison should record at least:

1. Total runtime and runtime per article.
2. Gemma call count, recovery call count, average call time.
3. `en_residual_segments`.
4. `sentinel_leak_segments`.
5. Count of raw `@@Z2M`, `<z2m`, and bare `Z2M_A/T/F` leaks.
6. Count of stray protected-abbreviation tails such as `SNR@`, `ECoG@`,
   `BMI@`.
7. RU-created anchor count compared with EN polish.
8. Broken or hallucinated figure/table labels.
9. Image data-URI hash mismatches against sidecar images.
10. New untranslated post-reference sections.

## Regression Gate

A change can be committed only when:

1. The target defect is fixed or reduced in the control run.
2. No previously passing tracked metric regresses.
3. The speed budget is not materially worse unless explicitly accepted.
4. The relevant tests pass.
5. The audit note records remaining residual risks.

Target speed for normal RU translation remains about 20-40 minutes per article.
If a quality change increases runtime, compare total article time, not only
single-call latency: fewer retries may still be a net win.

