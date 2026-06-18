# Quality Loop Follow-up Plan: Review Queue And P62 Tail

Baseline run:

- Run dir: `review_runs/full_rename_regression_20260618_07`
- Metric recheck: `quality_compare_metric_recheck.json`
- Current commit before this plan: `51657ac Harden polish quality loop repairs`
- Corpus: `raw=1009`, `articles=878`, `skipped=131`, `changed=602`
- Quality result after metric recheck: `score=447.0`, `defects=0`, `errors=0`, `warnings=0`
- Comparison with previous run: `score_delta=-404.5`, `defects_delta=-2.0`, `regressions=0`, `improvements=32`
- Gate state after metric recheck: fail only on `mandatory_review_pending=571`
- P62 image recovery: `selected=181`, `patched=171`, `unresolved=10`

## Problem Split

The remaining gate failure is not one problem.

1. Manual review queue pressure:
   - `manual_review_queue.json` has `878` pending items.
   - `571` are mandatory.
   - All mandatory items have `mandatory_review_reason=changed_without_quality_delta`.
   - Most mandatory items have no audit defect. Only `23` have any defect and `17` have non-ignored defects.
   - This means the queue is currently a conservative policy backlog, not a list of 571 known bugs.

2. P62 recovery tail:
   - The `10` unresolved records are two duplicate Lahav source records, each with figures `1..5`.
   - All have `plan_status=source_visual_unavailable`.
   - All have `source_visual_unavailable_reason=all_label_matches_are_false_or_without_visual_objects`.
   - False-match hints are `figure_caption_list` and `prose_parenthetical_reference`.
   - This is mostly an unmodeled terminal state, not a request to render arbitrary fallback pages.

## Track A: Make Manual Review Queue Risk-Based And Evidence-Based

Goal: reduce `mandatory_review_pending` without hiding risk. A changed article should stay mandatory only when the loop cannot produce enough deterministic evidence that the change is low risk.

### A1. Add Review Risk Classification

Extend `src/pdf_html_polish/quality_loop/review_workflow.py` queue items with:

- `review_risk_level`: `high`, `medium`, `low`, or `auto_verified`
- `review_risk_reasons`: stable list of reason codes
- `auto_review_eligible`: boolean
- `auto_review_evidence`: compact metrics and source reports used for the decision

Initial high-risk reasons:

- score, defect, error, or lower-is-better metric regression
- non-ignored audit defects
- broken internal links
- missing local images
- increased mixed citation style
- replacement-character growth not classified as PDF source noise
- article language boundary uncertainty
- P62 recovery unresolved without a terminal unavailable verdict

Initial low-risk or auto-verifiable reasons:

- article changed, but comparable metrics did not worsen
- no non-ignored defects
- no broken links
- no missing local images
- no mixed citation growth
- change is explained by a successful auto-repair or P62 recovery report

Tests:

- Add unit tests in `tests/test_quality_loop_review_workflow.py`.
- Cover high-risk changed articles remaining mandatory.
- Cover low-risk `changed_without_quality_delta` articles moving out of mandatory when evidence is complete.
- Cover existing `review_status` preservation across regenerated queues.

### A2. Add Deterministic Auto-Review Evidence

The queue should not auto-clear a changed article merely because score is unchanged. It should store why it is safe enough for automatic review.

Evidence sources to attach:

- `quality_compare*.json` article deltas
- `assessment*.json` link and citation-style metrics
- `audit_full_checks.json` non-ignored defect counts
- `manifest.json` changed flag and restored image counts
- `p62_image_recovery_report.json` patch status by article
- `polish_auto_repair_report.json` patch status and repair ids by article

Suggested decision:

- `auto_verified`: no non-ignored defects, no lower-is-better metric increase, and every known change is explained by successful repair/recovery reports.
- `low`: no quality regression, but change source is not fully explained.
- `medium`: ignored defects or image-only uncertainty remains.
- `high`: any non-ignored defect or regression signal remains.

Success metric:

- `mandatory_count` should represent high-risk items, not all changed unchanged-score items.
- `pending_mandatory_count` should be small enough for real review, and eventually `0` once high-risk items are reviewed or fixed.

### A3. Add Review State Tooling

Avoid manual JSON edits for the review queue.

Add a CLI subcommand or script that can update review status by article id:

- `review_status=reviewed`, `accepted_auto`, `needs_fix`, or `false_positive`
- `review_note`
- optional `observation_id` linking into the manual observation ledger

The queue already preserves `review_*` fields across regenerations. The missing piece is a safe command to update those fields reproducibly.

Tests:

- A reviewed item remains reviewed after `write_manual_review_queue`.
- Article id, raw path, and polish path all work as stable lookup keys.
- Gate pending count uses only mandatory items still marked `pending`.

### A4. Keep Sampling Separate From Gate

For low-risk changed articles, build a sampled review bundle for human confidence, but do not make the whole low-risk set mandatory.

Sampling should be deterministic:

- top N by score
- top N by changed link/image count
- stable hash sample by article id
- at least one article from each repair source group

Success metric:

- Gate can pass when high-risk mandatory items are cleared.
- Low-risk sample remains visible in `article_review_report.json` as non-blocking evidence.

## Track B: Close The P62 Tail As A Terminal Source-Unavailable State

Goal: make the 10 remaining P62 records explicit and auditable. Do not replace them with arbitrary PDF page renders.

### B1. Promote Proven Source-Unavailable Records Out Of `unresolved`

Current P62 unresolved records already contain enough evidence:

- `plan_status=source_visual_unavailable`
- `source_visual_probe_status=not_found`
- label pages checked
- false-match hints recorded
- native image inventory found no source visual
- marker probe did not find a usable source visual

Change report semantics:

- Use `status=source_visual_unavailable` instead of `status=unresolved` for records with complete unavailable evidence.
- Add `source_visual_unavailable_count`.
- Keep `unresolved_count` only for records that still need code or manual investigation.

Tests:

- Add `build_p62_image_recovery_report` coverage for terminal unavailable records.
- Assert terminal unavailable records are not counted as unresolved.
- Assert incomplete unavailable evidence still stays unresolved.

### B2. Mark HTML/Audit State Without Hiding The Limitation

When the source PDF has no embedded target visual, the HTML should not pretend the image was recovered. It should also not keep looking like an actionable missing-figure repair.

Preferred behavior:

- Keep a visible missing/source-unavailable marker in the figure unit.
- Add stable machine-readable metadata, for example `data-z2m-recovery-source="source_visual_unavailable"`.
- Teach the P62 audit to treat this as a terminal source limitation, not a repairable missing image.
- Keep the finding available in reports as informational telemetry.

Tests:

- A figure with source-unavailable metadata does not become a repairable P62 warning.
- The marker remains visible enough for manual inspection.
- The quality history does not count it as a regression.

### B3. Deduplicate Repeated Source Records

The current 10 records are two article ids pointing at the same Lahav source PDF and the same figure labels `1..5`.

Add grouping in reports:

- group key: source PDF path plus resolved figure label plus unavailable reason
- affected article ids: list
- counted terminal issue count: grouped and raw counts both recorded

Success metric:

- The report explains `10 raw records / 5 grouped unavailable figures`.
- Future duplicate Zotero attachments do not make the tail look larger than it is.

### B4. Keep Real Recovery Paths Strict

For records that are not terminal source-unavailable:

- keep full-label page resolver mandatory
- reject table of contents, caption lists, placeholders, and prose-only references
- prefer marker or PDF figure-region render when visual evidence exists
- use page render fallback only when caption and visual evidence support the page

Tests:

- Placeholder/caption-list pages are rejected.
- Figure-region render is preferred over full-page fallback.
- Duplicate visual repair accepts region-render sources.

## Execution Order

1. B1 first: it is small, high-confidence, and should reduce P62 `unresolved_count` without changing article content.
2. B2 next if B1 still leaves actionable P62 warnings in audit output.
3. A1 and A2 together: risk classification needs evidence fields to be useful.
4. A3 after the queue shape is stable.
5. A4 last: sampling is useful only after mandatory semantics are correct.
6. Full run and metric recheck after each code-bearing batch.

## Verification Commands

Focused tests:

```powershell
python -m pytest tests\test_quality_loop_review_workflow.py tests\test_p62_recovery_stage.py tests\test_audit_p62.py
```

Full tests:

```powershell
python -m pytest
```

Full loop shape:

```powershell
python scripts\llm_quality_loop.py observe `
  --source-run-dir review_runs\full_control_repolish_post_target_repairs_20260611_02 `
  --out-dir review_runs\<new_run_id> `
  --run-id <new_run_id> `
  --previous-entry review_runs\full_control_repolish_post_target_repairs_20260611_02\quality_history_entry.json `
  --no-append-history
```

Required final checks:

- `regressions=0`
- `defects=0`
- `errors=0`
- `warnings=0`
- `mixed_citation_style_delta<=0`
- `p62_image_recovery_report.unresolved_count=0` or only records without complete unavailable evidence remain
- `quality_gate_report.failures` does not include `mandatory_review_pending`

## Guardrails

- Do not solve this by raising `max_pending_mandatory_reviews`.
- Do not auto-mark changed articles as reviewed without stored evidence.
- Do not render arbitrary PDF pages for P62 source-unavailable records.
- Do not remove visible source-unavailable information from HTML just to silence P62.
- Every code change gets a focused test before the full corpus run.
