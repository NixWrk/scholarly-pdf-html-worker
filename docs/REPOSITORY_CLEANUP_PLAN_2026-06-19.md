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

## Immediate Execution Queue

1. Continue thinning `scripts/audit_en_polish.py` by defect family.
2. Keep extracted audit helpers in focused `quality_loop/audit_*` modules with
   direct tests.
3. Revisit `scripts/audit_en_raw.py` once the polish audit boundaries are
   calmer.
4. Only then start extracting small domains from `single_file_html.py`.

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
