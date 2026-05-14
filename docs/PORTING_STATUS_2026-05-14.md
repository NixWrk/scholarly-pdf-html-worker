# Porting Status - 2026-05-14

Source repository: `D:\Git_Code\ZoteroPDF_2_MD`.
Target repository: `D:\Git_Code\pdf-html-translator`.

## What Was Ported

- EN polish methodology and review documentation from the ZoteroPDF_2_MD workstream.
- EN polish audit/repolish/review helper scripts under `scripts/`.
- Focused EN polish and audit regression tests under `tests/`.
- Curated local review corpus under `review_runs/imported_from_zoteropdf2md_2026-05-14/`.

## Included Review Corpus

- 7-article control corpus from `md_output/new`:
  - `electrodes_W7TECQDX`
  - `headless_intracranial`
  - `headless_llm_medicine`
  - corresponding `_quality_audit` reports
- Meine `001-025` stage corpus from `md_output/meine_full_library_en_polish_2026-04-28_single_loop`.
- Meine `_quality_audit` reports, including the orphan figure target recovery run.
- Manual review snapshots:
  - `manual_review_en_polish_inlined_2026-04-27_round3`
  - `manual_review_meine_en_polish_inlined_2026-04-30_001_025_subset`
  - `manual_review_meine_en_polish_inlined_2026-04-30_after_fixes_001_005`
  - `manual_review_meine_en_polish_inlined_2026-05-02_018_025_final`

## Current Known State

The code-level EN polish behavior was already present in this repository before this port: `src/zoteropdf2md/single_file_html.py` matched the source repository byte-for-byte at port time.

The historical commit hash `006716b Recover orphan EN figure targets` is not present in this repository history; its code arrived through the initial extraction history instead. This port adds the missing working evidence: docs, scripts, tests, and review corpora.

## Development Method To Continue Here

1. Record each complaint in a review ledger before changing code.
2. Compare `01.en.raw.html` with `02.en.polish.html` and classify the defect as `raw_only`, `not_fixed_by_polish`, `introduced_by_polish`, `audit_false_positive`, or `ocr_policy`.
3. Promote only local, repeatable patterns to universal EN polish fixes.
4. Add or extend focused regression tests before/with the fix.
5. Re-run the 7-article control corpus and the active Meine batch.
6. Keep uncertain missing figure/table targets for PDF/raw-region diagnostics instead of broad HTML guessing.

## Useful Commands

Run focused tests:

```powershell
python -m pytest -q tests\test_single_file_html.py tests\test_audit_en_polish.py tests\test_repolish_en_from_raw.py tests\test_collect_en_polish_review.py
```

Repolish the imported 7-article control corpus:

```powershell
python scripts\repolish_en_from_raw.py --roots review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\electrodes_W7TECQDX review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\headless_intracranial review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\headless_llm_medicine --table-caption-language en --out-report review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\_quality_audit\repolish_control_7_current.json
```

Audit the imported 7-article control corpus:

```powershell
python scripts\audit_en_polish.py --roots review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\electrodes_W7TECQDX review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\headless_intracranial review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\headless_llm_medicine --pdf-diagnostics --out review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\_quality_audit\audit_control_7_current.json
```

## Port Verification - 2026-05-14

Focused transferred test suite:

```powershell
python -m pytest -q tests\test_single_file_html.py tests\test_audit_en_polish.py tests\test_repolish_en_from_raw.py tests\test_collect_en_polish_review.py tests\test_audit_en_raw.py tests\test_audit_source_language.py tests\test_language_detect.py
```

Result: `272 passed`.

Imported control-7 audit command completed successfully and wrote:

`review_runs\imported_from_zoteropdf2md_2026-05-14\md_output\new\_quality_audit\audit_control_7_port_check_2026-05-14.json`

Audit totals: `raw_img=80`, `polish_img=80`, `page_links=1`, `bad_chars=0`, `missing_img=0`.

## Full HTML Import - 2026-05-14

After the initial curated import, the review corpus was expanded to include all HTML needed for unfinished manual review:

- every `manual_review*` directory from the source repository;
- an HTML-only mirror of every `md_output/**/*.html` file under `review_runs/imported_from_zoteropdf2md_2026-05-14/html_mirror/md_output`.

Manifest:

`review_runs/imported_from_zoteropdf2md_2026-05-14/HTML_CORPUS_MANIFEST_2026-05-14.md`

Use the `manual_review*` folders for visual inspection and `html_mirror/md_output` when raw/polish stage paths are needed for comparison.
