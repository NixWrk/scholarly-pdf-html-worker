# Manual EN Polish Review Workflow 2026-04-26

Goal: turn manual HTML/PDF comparison notes into generalized, testable defect classes before implementing the next fixes.

## Working Rule

Do not fix isolated article symptoms immediately unless they are obviously blocking the review itself. First collect and verify notes across all reviewed articles, then group recurring defects and define precise fix requirements.

## Review Order

Use the same canonical order as the current EN raw/polish audit:

1. Ahmed 2026
2. Kaiju 2017
3. Li 2026
4. Merken 2022
5. Schelles 2025
6. Wang 2017
7. Teo 2025

## Per-Article Loop

For each article:

1. User sends manual notes from HTML/PDF comparison.
2. Codex checks the relevant artifacts:
   - `02.en.polish.html`
   - `01.en.raw.html`
   - original PDF/HTML when needed
   - current polish/raw extraction code when needed
3. Codex verifies each symptom and records:
   - where it appears;
   - what the expected output should be;
   - which layer likely introduced it;
   - whether it is article-specific or a general defect class;
   - what regression coverage is needed.
4. Codex appends findings to the review document.
5. Move to the next article only after the current article's notes are captured.

## Per-Article Section Template

Use this structure in the review document:

```markdown
## Article Name

### Manual Notes From User

- ...

### Verified Symptoms

| ID | Location | Symptom | Expected | Layer | Status |
|---|---|---|---|---|---|
| A01 | ... | ... | ... | raw/polish/... | open |

### Root Cause Hypotheses

- ...

### Generalized Defect Classes

- ...

### Fix Requirements

- ...

### Regression Coverage Needed

- ...
```

## Consolidation Pass

After all seven articles are captured, Codex performs a second pass over the review document:

1. Merge repeated symptoms into shared defect classes.
2. Separate pipeline bugs from unavoidable source PDF/layout limitations.
3. Assign each defect class to a layer:
   - Marker/raw extraction;
   - image extraction;
   - EN polish sentence repair;
   - caption/table anchors and links;
   - table/layout cleanup;
   - audit/test coverage.
4. Define final fix requirements for each class.
5. Define regression tests and pair-audit checks for each fix.
6. Prioritize implementation order by blast radius and confidence.

## Implementation Loop

Only after the consolidation pass:

1. Pick one defect class.
2. Add or update regression tests.
3. Implement a general fix, not an article-specific patch.
4. Regenerate affected `02.en.polish.html` files.
5. Re-run focused tests and pair-audit checks.
6. Update the manual review document with status and evidence.

## Initial Output Documents

- Workflow/protocol: `docs/MANUAL_EN_POLISH_REVIEW_WORKFLOW_2026-04-26.md`
- Findings log to create next: `docs/MANUAL_EN_POLISH_REVIEW_2026-04-26.md`
