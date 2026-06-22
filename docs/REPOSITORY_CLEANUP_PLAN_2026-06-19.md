# Repository Cleanup Plan - 2026-06-19

This plan tracks the remaining cleanup needed to bring `pdf-html-polish` close
to a final maintainable shape after the main LLM-in-the-loop defect work.

The cleanup policy is deliberately conservative:

- keep every change small enough to review;
- preserve public CLI and compatibility aliases unless a test proves they are
  no longer needed;
- add or update focused tests for behavior touched by each cleanup;
- run targeted tests before the full project suite;
- commit each completed cleanup stage separately.

## Current Shape

- Production package: `src/pdf_html_polish/`
- Public CLI: `pdf-html-polish`
- Quality-loop orchestrator: `scripts/llm_quality_loop.py`
- Audit CLIs: `scripts/audit_en_polish.py`, `scripts/audit_en_raw.py`
- Major monoliths still present:
  - `src/pdf_html_polish/single_file_html.py`
  - `scripts/llm_quality_loop.py`
  - `scripts/audit_en_polish.py`
  - `tests/test_single_file_html.py`
  - `tests/test_llm_quality_loop.py`
  - `tests/test_audit_en_polish.py`

## Cleanup Stages

### 1. Stabilize Boundaries

- Document which commands and modules are public.
- Keep compatibility shims covered by tests while callers still depend on
  them.
- Avoid moving behavior across package boundaries without a test around the
  old entry point.

### 2. Thin `scripts/llm_quality_loop.py`

- Keep argparse, orchestration, config defaults, and dependency wiring in the
  script.
- Move or directly import domain behavior from `src/pdf_html_polish/quality_loop`.
- Remove pass-through wrappers when they add no repository-specific context.
- Keep wrappers that intentionally inject `ROOT`, stage names, output names, or
  test seams.

### 3. Thin Audit Scripts

- Convert `scripts/audit_en_polish.py` and `scripts/audit_en_raw.py` into CLI
  wrappers over package modules.
- Keep individual defect families in `quality_loop/audit_*`.
- Add focused tests in the matching `tests/test_audit_*.py` files.

### 4. Split `single_file_html.py` Gradually

- Do not rewrite the monolith in one pass.
- Extract one natural domain at a time:
  - references and bibliography repair;
  - internal/external link repair;
  - math and KaTeX helpers;
  - float/table/figure repair;
  - frontmatter and metadata cleanup;
  - image inlining and restoration.
- Preserve old private aliases until compatibility tests can be retired.
- After the polish pass on this module, run a polish/audit parity gate before
  any full PDF-to-polish batch.

### 5. Reshape Tests

- Split large test files by domain as code moves.
- Move shared fixtures/helpers into small test helper modules or
  `tests/conftest.py`.
- Keep regression tests close to the package module that owns the behavior.

### 6. Tooling And Repository Hygiene

- Add minimal formatting/lint tooling only after the active refactors settle.
- Start with safe import/unused-code checks before broader style rules.
- Review line-ending settings because Git warns about LF/CRLF conversion.

### 7. Final Documentation Pass

- Keep README focused on install, conversion, and operational boundaries.
- Keep quality-loop details in `docs/llm_quality_loop.md`.
- Separate active playbooks from historical investigation notes.
- Add a final release checklist: install, smoke conversion, targeted tests,
  full tests, quality-loop observe/gate.

### 8. Post-Refactor Verification Gate

- After meaningful `single_file_html.py` domain extractions, run focused tests
  plus the full suite.
- Before the full PDF-to-polish HTML pipeline, first run the existing
  polish/repolish path and audit reports to confirm there is no quality or
  behavior drift.
- For production-quality validation and behavior-neutral refactor acceptance,
  use the required repair-enabled `llm_quality_loop.py observe --converted-roots`
  gate described in `docs/REPOSITORY_WORKFLOW.md`. The 2026-06-22 reference
  shape is the full converted-root observe with tests, Zotero PDF map, P62
  recovery, polish auto-repair, post-repair audit, compare, and gate report.
- Only after that parity check passes, run the full PDF-to-polish HTML flow.

## Immediate Execution Queue

1. Treat the full source-PDF pipeline run
   `review_runs/full_pdf_to_polish_from_source_map_chunked_20260620_01` plus
   audit `review_runs/full_pdf_to_polish_from_source_map_chunked_audit_20260620_02`
   as the current production baseline. Treat
   `review_runs/full_pdf_to_polish_repair_observe_20260622_01` as the current
   required observe-gate example for quality-neutral refactor validation.
2. Triage full-PDF-only audit clusters before broad refactors: source-PDF
   mapping is incomplete for converted-root audits, 51 items remain in the
   re-OCR queue, and the full run still has accepted/queued repair candidates
   despite passing the gate.
3. Remove or explicitly retire the stale `_MOJIBAKE_REPLACEMENTS` compatibility
   tuple left in `single_file_html.py` after the pre-cleanup extraction.
4. Start the frontmatter/footnote cluster in small slices, using
   `raw_html_polish/frontmatter_footnotes.py` as the package owner.
5. Preserve old private aliases in `single_file_html.py` while tests still
   import them.
6. After the `single_file_html.py` polish pass, run polish/audit parity before
   the full PDF-to-polish HTML pipeline.
7. Run the full PDF-to-polish HTML flow only after the parity gate passes.

## Progress

- Documented the cleanup plan in this file.
- Removed no-context pass-through helpers from `scripts/llm_quality_loop.py`
  while keeping compatibility names covered by tests.
- Tightened source-PDF discovery by removing duplicate keyed PDF paths and
  ignoring numeric article ids as Zotero attachment-key candidates.
- Moved existing path-candidate repair logic from the script into
  `quality_loop/source_pdf.py`.
- Added `.gitattributes` so future cleanup does not accumulate accidental
  line-ending churn.
- Current `llm_quality_loop.py` boundary: remaining wrappers should generally
  stay unless they are moved with their injected defaults (`ROOT`, stage names,
  output names, or dependency callbacks) into package-level orchestration
  helpers.
- Started audit-script thinning by moving image asset diagnostics from
  `scripts/audit_en_polish.py` into `quality_loop/audit_images.py` with direct
  unit tests.
- Moved source-PDF float-gap confirmation from `scripts/audit_en_polish.py`
  into `quality_loop/audit_float_gap.py` with direct unit tests.
- Moved P20/P96 image defect builders from `scripts/audit_en_polish.py` into
  `quality_loop/audit_images.py` with direct unit tests.
- Moved P98 citation-style consistency diagnostics from
  `scripts/audit_en_polish.py` into `quality_loop/audit_citation_style.py`
  with direct unit tests.
- Moved manual recent text-pattern callbacks from `scripts/audit_en_polish.py`
  into `quality_loop/audit_manual_patterns.py` with direct unit tests.
- Moved `MeineRecentLinkDeps` citation/reference callbacks from
  `scripts/audit_en_polish.py` into `quality_loop/audit_citation_style.py`
  with direct unit tests.
- Moved figure-caption classifiers from `scripts/audit_en_polish.py` into
  `quality_loop/audit_figure_caption_ux.py` with direct unit tests.
- Moved manual blind-spot context classifiers from `scripts/audit_en_polish.py`
  into `quality_loop/audit_figure_caption_ux.py` and
  `quality_loop/audit_manual_patterns.py` with direct unit tests.
- Removed duplicate P04 citation-range helper logic from
  `scripts/audit_en_polish.py`; the CLI now relies on
  `quality_loop/audit_p04.py` for those classifiers.
- Moved the P05 reference false-positive classifier from
  `scripts/audit_en_polish.py` into `quality_loop/audit_citation_style.py`
  with direct unit tests.
- Moved default `MeineRecentLinkDeps` reference/body-context callbacks from
  `scripts/audit_en_polish.py` into `quality_loop/audit_manual_recent.py`
  with direct unit tests.
- Moved supplementary figure classification from `scripts/audit_en_polish.py`
  into `quality_loop/audit_figure_caption_ux.py` with direct unit tests.
- Moved P04 reference-target number collection from `scripts/audit_en_polish.py`
  into `quality_loop/audit_p04.py` with direct unit tests.
- Moved the full citation defect family (`P04*`, `P05`, `P28`, `P32`) from
  `scripts/audit_en_polish.py` into `quality_loop/audit_citations.py` with
  direct unit tests.
- Moved pair-level polish audit orchestration from `scripts/audit_en_polish.py`
  into `quality_loop/audit_polish_pair.py` with direct unit tests; the script
  now only supplies dependency wiring for `analyze_pair`.
- Moved polish audit report/progress orchestration from
  `scripts/audit_en_polish.py` into `quality_loop/audit_polish_report.py`
  with direct unit tests; the script now only supplies report-level wiring.
- Moved targeted polish audit report merging from `scripts/audit_en_polish.py`
  into `quality_loop/audit_polish_report.py` with direct unit tests.
- Moved polish audit summary output from `scripts/audit_en_polish.py` into
  `quality_loop/audit_polish_report.py` with direct unit tests.
- Collapsed `MeineRecentLinkDeps` wiring in `scripts/audit_en_polish.py` behind
  `quality_loop/audit_manual_recent.py` defaults; link-pattern regexes and
  caption-aware warning wrappers now live in the package with direct unit tests.
- Collapsed `MeineRecentTextDeps` wiring in `scripts/audit_en_polish.py` behind
  `quality_loop/audit_manual_recent.py` defaults; text/OCR regexes and callback
  dependencies now live in the package with direct unit tests.
- Started `scripts/audit_en_raw.py` thinning by moving raw block parsing,
  snippet helpers, generic first-match defects, and UTF-8 read diagnostics into
  `quality_loop/audit_raw_blocks.py` with direct unit tests.
- Moved EN raw image reference/sidecar summary and `R03` missing-image
  diagnostics from `scripts/audit_en_raw.py` into
  `quality_loop/audit_raw_images.py` with direct unit tests.
- Moved EN raw structural checks (`R02`, `R05`, `R06`, `R13`) and small
  anchor/reference/mojibake summaries from `scripts/audit_en_raw.py` into
  `quality_loop/audit_raw_checks.py` with direct unit tests.
- Moved EN raw per-file analysis orchestration and raw pattern checks
  (`R07`, `R08`, `R09`, `R11`, `R12`, `R14`) from `scripts/audit_en_raw.py`
  into `quality_loop/audit_raw_analysis.py` with direct unit tests.
- Moved EN raw stage discovery, corpus aggregation, report assembly, and console
  summary output from `scripts/audit_en_raw.py` into
  `quality_loop/audit_raw_report.py` with direct unit tests; the script is now
  primarily CLI argument handling and JSON writing.
- Completed a control pass over both audit CLIs after raw extraction:
  `scripts/audit_en_raw.py` is primarily CLI/JSON wiring, while
  `scripts/audit_en_polish.py` intentionally keeps compatibility aliases still
  exercised by tests.
- Recorded the post-`single_file_html.py` verification gate: run polish/audit
  parity first, then the full PDF-to-polish HTML pipeline.
- Started `single_file_html.py` decomposition by moving stale inline-image data
  URL refresh helpers into `html_images.py`; the monolith now preserves those
  private names as compatibility aliases with focused tests on the package
  owner and the alias surface.
- Moved reusable inline-image text inlining/cache orchestration into
  `html_images.py`; `single_file_html.py` now keeps file-level polish wrappers
  and compatibility aliases while direct image behavior is tested in
  `tests/test_html_images.py`.
- Moved nested figure/same-href internal link unwrapping into `html_links.py`
  with direct link tests and compatibility aliases retained in
  `single_file_html.py`.
- Moved repeated-phrase cleanup into `text_cleanup.py`; `pipeline.py` now uses
  that package helper directly, while `single_file_html.py` keeps a
  compatibility alias covered by tests.
- Moved inline `<sup>/<sub>` escaped/spaced tag cleanup into
  `raw_html_polish/html_fragments.py` with direct fragment tests and
  compatibility aliases retained in `single_file_html.py`.
- Moved low-risk pre-cleanup helpers (`_fix_common_mojibake`,
  `_cleanup_marker_escape_artifacts`, `_strip_protocol_sentinel_leaks`) and
  generic skip-stack wiring into `raw_html_polish/pre_cleanup.py` with direct
  tests; citation-specific skip-stack logic intentionally remains in
  `single_file_html.py`.
- Documented the full repair-enabled converted-root observe as the mandatory
  acceptance gate for production-quality validation and behavior-neutral
  refactors.
- Continued the `single_file_html.py` frontmatter decomposition by moving
  author byline/marker classifier helpers into
  `raw_html_polish/frontmatter_footnotes.py`; compatibility aliases remain in
  `single_file_html.py` and direct owner tests cover the moved logic.
- Moved frontmatter page-anchor marker repair into
  `raw_html_polish/frontmatter_footnotes.py` behind an explicit word-join
  dependency callback; `single_file_html.py` keeps the old private wrapper.
- Moved the frontmatter affiliation-label body detector into
  `raw_html_polish/frontmatter_footnotes.py` with a compatibility alias in
  `single_file_html.py`.
- Moved footnote detector helpers (`leading_footnote_number`,
  `footnote_keywords`, and the callback-backed `looks_footnote_block`) into
  `raw_html_polish/frontmatter_footnotes.py`; `single_file_html.py` keeps the
  old private names where callers still use them.
- Moved footnote paragraph/reference marking into
  `raw_html_polish/frontmatter_footnotes.py` with explicit callbacks for
  float-caption guards and citation safety checks.
- Moved page-linked footnote reference repair into
  `raw_html_polish/frontmatter_footnotes.py`; `single_file_html.py` now imports
  the old private name directly from the package owner.
- Moved URL-leading footnote prose-tail splitting into
  `raw_html_polish/frontmatter_footnotes.py`.
- Moved frontmatter marker OCR orchestration into
  `raw_html_polish/frontmatter_footnotes.py` with an explicit word-join
  dependency for page-anchor marker repair.
- Moved frontmatter paragraph marking into
  `raw_html_polish/frontmatter_footnotes.py` with an explicit
  `looks_front_matter_block` callback; `single_file_html.py` keeps the old
  private wrapper.
- Moved frontmatter block classification into
  `raw_html_polish/frontmatter_footnotes.py` with an explicit
  `looks_affiliation_block` callback; `single_file_html.py` keeps the old
  private wrapper.
- Split the confirmed frontmatter artifact repair family inside
  `single_file_html.py` into small private helpers for e-mail fixes, Turkish
  byline markers, Xue byline/abstract splitting, Sevick marker normalization,
  and Zhu affiliation-tail splitting; this keeps behavior local while preparing
  the family for a later owner-module move.
- Moved the confirmed frontmatter artifact repair family into
  `raw_html_polish/frontmatter_footnotes.py`; `single_file_html.py` keeps the
  old private names as compatibility aliases.
- Moved affiliation block detection/marking into
  `raw_html_polish/frontmatter_footnotes.py`; `single_file_html.py` keeps the
  old private names as aliases so sentence/float repair callers do not change.
- Started the URL/anchor cleanup by moving spaced-protocol URL anchor repair
  double-escaped URL anchor label normalization, and split-visible URL anchor
  repair, plus paragraph-boundary, domain-tail, prose-prefixed, split-scheme,
  DOI split, adjacent same-href URL, adjacent mailto, and noisy `http://www`
  anchor repairs, into `raw_html_polish/url_anchors.py`; `single_file_html.py`
  keeps the old private pattern/function names as aliases.
- Ran a full cached-raw no-repair parity check on
  `review_runs/refactor_parity_cleanup_20260619_02` from the latest 1009-raw
  source run. The run repolished 878 EN articles, skipped 131 non-target
  documents, reported 657 changed polish outputs, and passed the full test
  suite (`1348 passed, 5 warnings`). The audit/gate failed against the repaired
  baseline (`score_delta=1194.75`, `defects_delta=51`,
  `broken_internal_links_delta=177`, `mandatory_pending=67`), but the main
  counted defects matched the previous pre-auto-repair state (`P98=42`,
  `P04=1`, `P59=3`, `P13=1`). Treat this as evidence that production
  PDF-to-polish should wait for a standard repair-enabled parity pass, not as a
  direct refactor regression verdict.
- Ran the repair-enabled full cached-raw parity check in
  `review_runs/refactor_parity_cleanup_repair_enabled_20260619_01` against
  `review_runs/full_p62_parallel_p61_p71_20260619_01`. The run repolished 878
  EN articles from 1009 cached raws, skipped 131 non-target documents, and
  changed 657 polish outputs.
- The default P62 image-recovery parallelism (`p62_image_recovery_jobs=16`)
  exhausted memory on the full corpus. Resuming P62 with `--jobs 2` completed
  the recovery stage (`candidate_count=184`, `asset_ready_count=160`,
  `patched_warning_count=370`, `unresolved_count=12`), so the default gate
  config now uses `p62_image_recovery_jobs=2` for reliability.
- Polish auto-repair patched 62 articles in the repair-enabled parity pass
  (`P04=98`, `P59=20`, `P98=176`, `broken_internal_links=300`). A refreshed
  full PDF-aware polish audit covered all 878 articles with no counted defects;
  only non-quality telemetry remained (`P62`, `P04M`, `P61`, `P45*`, `P71`,
  `P35`).
- Final repair-enabled parity result: `quality_history` score `445.0`,
  defects/errors/warnings `0/0/0`, `quality_compare` regressions `0`,
  improvements `2`, article review `not_required`, and quality gate `pass`.
  Follow-up audit fixes added during this pass covered all-letter Zotero
  attachment keys, P05 clean citation false positives near truncated
  `phoneme` text, P33 supplemental-media page anchors, and review classification
  for `source_pdf_unavailable` P62 records.
- Ran the full chunked source-PDF-to-polish HTML pipeline in
  `review_runs/full_pdf_to_polish_from_source_map_chunked_20260620_01` from the
  repair-enabled source PDF map. The run covered 744 unique existing source PDF
  paths, completed with `failed_count=0`, and produced 744
  `_pdf_html_polish_stages/02.en.polish.html` files after backfilling two
  duplicate-stem PDFs.
- The full run exposed and fixed two production accounting bugs:
  renderable inline `data:image` payloads are now shielded during polish so
  regex phases do not scan base64 (`bfed005`), and duplicate Zotero PDFs with
  the same visible filename no longer false-skip or collide on alias ownership
  (`1aaa806`). Converted-root article ids now keep a short hash when truncated,
  so long names that differ only near the end stay distinct in quality history
  (`c1f2447`).
- Verification after those fixes: `python -m pytest` passed with
  `1361 passed, 5 warnings`. The production output map now has 744 rows, 744
  unique source paths, and 744 unique aliases. The only process left after the
  run was the unrelated n8n launcher.
- Full converted-root audit
  `review_runs/full_pdf_to_polish_from_source_map_chunked_audit_20260620_02`
  covered 744 articles at commit `c1f2447` with a clean working tree and passed
  the quality gate (`failures=[]`). Quality history totals were
  `score=2435.75`, `defects=305`, `errors=122`, `warnings=182`,
  `missing_local_images=0`, and `polish_missing_local_images=0`.
- Remaining full-PDF follow-up signals are operational, not blockers for the
  current gate: `_reocr_pending.json` contains 51 entries; converted-root
  `source_pdf_map.json` mapped only 119 of 744 articles because the audit run
  cannot yet recover every original source PDF from converted stage paths; and
  resolver decisions still include queued repair/recovery groups
  (`needs_repair=305`, `needs_pdf_recovery=124`, `needs_semantic_recovery=8`).
- Operational notes from the full run: one historical chunk retry remains in
  `chunked_pipeline_status.json` (`batches=745`) because a Windows cp1251
  console encode error interrupted a retry before the UTF-8 resume; final
  status is still `paths_total=744`, `completed_count=744`, `failed_count=0`.
  Production logging should keep using safe stdout handling for Windows
  Unicode-heavy titles.
- Parallelized the P62 marker recovery plan pre-stage by `p62_marker_recovery_jobs`
  and wired `observe --jobs` as a fallback for P62 marker planning, P62 image
  recovery, and polish auto-repair when neither stage-specific CLI flags nor
  gate config values are provided. The default gate config now uses
  `p62_marker_recovery_jobs=8`, while `polish_auto_repair_jobs=32` remains the
  auto-repair default.
