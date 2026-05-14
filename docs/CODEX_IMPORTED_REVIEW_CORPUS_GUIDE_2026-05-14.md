# Codex Imported Review Corpus Guide - 2026-05-14

This repository continues the PDF -> EN raw HTML -> EN polish HTML work that was developed in `D:\Git_Code\ZoteroPDF_2_MD`.

## What Was Imported

The imported material is the working evidence base for continuing EN polish fixes without losing the previous review history:

- manual review notes and consolidated fix plans;
- audit scripts and regression tests used during the EN polish iterations;
- JSON outputs from repolish/audit runs;
- all available review HTML and `md_output` HTML, including articles that have not yet been fully processed.

## Tracked Documentation

Primary review and planning documents are in:

`D:\Git_Code\pdf-html-translator\docs`

Most important files:

- `MANUAL_EN_POLISH_REVIEW_2026-04-26.md` - first manual review of the original 7 control articles.
- `MANUAL_EN_POLISH_REVIEW_ROUND2_2026-04-27.md` - second manual review round.
- `MANUAL_EN_POLISH_REVIEW_ROUND2_5_2026-04-27.md` - comparison of round 2 complaints against later output.
- `EN_POLISH_CONSOLIDATED_FIX_PLAN_2026-04-27.md` - consolidated fix plan by workstream.
- `EN_POLISH_UNIVERSAL_REPAIR_PLAN_2026-04-27.md` - plan for universal/local-safe repairs.
- `MEINE_EN_POLISH_MANUAL_REVIEW_2026-04-30.md` - manual findings for Meine articles.
- `MEINE_ENGLISH_RAW_POLISH_ANALYSIS_PLAN_2026-04-29.md` - analysis plan for English articles.
- `MEINE_EN_POLISH_FIX_AND_TEST_PLAN_2026-04-30.md` - fix/test plan for Meine issues.
- `MEINE_EN_POLISH_ITERATIVE_INSTRUCTIONS_2026-05-02.md` - working method for article-by-article iteration.
- `Доработки после отпуска.md` - deferred follow-up items, including OCR-specific polish policy.
- `PORTING_STATUS_2026-05-14.md` - what was moved into this split repository and how it was verified.

## Local Review Corpus

Large local review artifacts are under:

`D:\Git_Code\pdf-html-translator\review_runs\imported_from_zoteropdf2md_2026-05-14`

This folder is ignored by git through `review_runs/` because it is large and machine-local.

Important subfolders:

- `manual_review*` - self-contained or inlined HTML sets intended for visual manual inspection.
- `html_mirror\md_output` - mirror of HTML outputs from the old repository, preserving the original `md_output` layout.
- `md_output\new\_quality_audit` - curated quality-audit JSON outputs from the main EN polish iterations.
- `HTML_CORPUS_MANIFEST_2026-05-14.md` - count/size manifest for imported HTML folders.

## How Codex Should Use This

When continuing EN polish work, start from the docs above, then inspect the matching HTML in `review_runs` and the JSON audits in `_quality_audit`.

Use the 7 original control articles for regression checks, then validate against the Meine subsets/articles that triggered the current issue. Prefer universal repairs that fix a pattern across articles while preserving already-passing control cases.

Do not commit `review_runs/`. Commit only code, scripts, tests, and compact documentation.
