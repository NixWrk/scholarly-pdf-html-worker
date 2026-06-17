# EN Raw Debug Test Plan

This plan fixes the staged-debugging rule for `01.en.raw.html` artifacts.
The EN raw stage is the boundary between Marker/PDF extraction and our own
HTML polish code.

## Scope

Canonical EN raw corpus:

| Label | Glob | Current raw bytes | img | fig labels | table labels | page headers |
|---|---|---:|---:|---:|---:|---:|
| Ahmed 2026 | `md_output/new/electrodes_W7TECQDX/Ahmed*/_z2m_stages/01.en.raw.html` | 162661 | 10 | 21 | 0 | 0 |
| Kaiju 2017 | `md_output/new/electrodes_W7TECQDX/Kaiju*/_z2m_stages/01.en.raw.html` | 75275 | 10 | 21 | 3 | 0 |
| Li 2026 | `md_output/new/electrodes_W7TECQDX/Li*/_z2m_stages/01.en.raw.html` | 298525 | 17 | 15 | 7 | 32 |
| Merken 2022 | `md_output/new/electrodes_W7TECQDX/Merken*/_z2m_stages/01.en.raw.html` | 108806 | 8 | 12 | 3 | 0 |
| Schelles 2025 | `md_output/new/electrodes_W7TECQDX/Schelles*/_z2m_stages/01.en.raw.html` | 87764 | 8 | 20 | 9 | 0 |
| Wang 2017 | `md_output/new/headless_intracranial/Wang*/_z2m_stages/01.en.raw.html` | 67259 | 24 | 46 | 8 | 0 |
| Teo 2025 | `md_output/new/headless_llm_medicine/Teo*/_z2m_stages/01.en.raw.html` | 109067 | 3 | 6 | 3 | 0 |

Auxiliary snapshots:

1. `md_output/new/control_ahmed_kaiju_20260424_211715`
2. `md_output/new/control_kaiju_fast_20260425_111733`

These are useful for A/B comparison, but they are not the canonical corpus.
Ignore `md_output/_test_tmp` for article-quality audits.

## Fixed Rule

Every article-quality investigation starts at `01.en.raw.html`.

1. If the defect exists in EN raw, classify it as Marker/PDF extraction or
   source-structure damage.
2. If EN raw is clean and `02.en.polish.html` is broken, debug EN polish.
3. Do not patch EN polish to hide an EN raw defect unless the patch is an
   explicit fallback policy with a recorded tradeoff.

## EN Raw Test Matrix

Run every check on all canonical EN raw files.

| Test ID | Check | Failure meaning | Next action |
|---|---|---|---|
| R01 | File exists, is non-empty, UTF-8 readable | Stage artifact missing/corrupt | Re-run full PDF to EN raw |
| R02 | HTML has `<html`, `<body`, balanced major closing tags | Marker emitted malformed HTML | Re-run Marker or add raw-stage failure |
| R03 | Count `<img>` tags and sidecar image files | Images missing from raw extraction | Inspect PDF page and Marker output |
| R04 | Detect figure labels: `FIGURE N`, `Fig. N`, `Figure N` | Caption extraction baseline | Compare with image proximity |
| R05 | Figure label has nearby image before/after within a small block window | Caption-without-image defect | Classify as Marker figure loss |
| R06 | Detect OCR-only figure panels in headings | Marker converted figure panel into text | Flag as raw extraction defect |
| R07 | Detect page headers/footers like `Page X of Y` | Header cleanup needed in EN polish | Add/adjust EN polish rule |
| R08 | Detect glued roman/table footnote suffixes: `Foilii`, `etchingv` | Raw OCR/table artifact | Add EN polish normalization only after corpus check |
| R09 | Detect DOI corruption and duplicated DOI fragments | Raw text extraction damage | If raw only, classify Marker/source; if polish only, fix polish |
| R10 | Detect bibliography start and post-reference sections | References boundary baseline | Prevent over-freezing post-reference text |
| R11 | Detect broken hyphenated line joins in prose/table cells | OCR layout artifact | Decide EN polish text-normalization rule |
| R12 | Detect formula/unit splits such as `20Вµm`, `20 Вµ m`, `m` separated from `Вµ` | Raw OCR/formula artifact | Add EN polish or formula protection test |
| R13 | Detect suspicious all-caps figure/table text inside headings | Figure/table panel OCR leakage | Classify as raw extraction defect |
| R14 | Detect raw pipeline sentinels: `Z2M`, `<z2m` | Should never exist in EN raw | Fail immediately |
| R15 | Detect existing anchors/links and escaped anchors | Raw link baseline | Ensure polish is idempotent |
| R16 | Compare raw text length, image count, figure label count with previous run | Regression guard | Investigate before EN polish |

## Required Per-Article Report

Create or update one audit report per debug run with this shape:

```text
Article:
Stage path:
Run/log:

EN raw summary:
- bytes:
- images:
- figure labels:
- table labels:
- page headers:
- raw sentinels:

Defects found:
- ID:
- snippet:
- first broken stage:
- hypothesis:
- same-pattern hits across corpus:
- proposed fix layer:
- regression test:
- status:
```

## Iteration Order

Use this order for each defect class:

1. Pick one visible defect from one article.
2. Find the first broken stage.
3. Grep the same pattern across all seven canonical EN raw files.
4. Record whether it is isolated or systemic.
5. Write the smallest detector or unit test for the systemic pattern.
6. Implement only the layer-specific fix.
7. Re-run the detector on all seven EN raw files.
8. If EN polish output is affected, continue upward stage by stage.

## Initial EN Raw Hypotheses To Test

1. Kaiju Figure 1 missing image: caption exists but the figure panel was OCRed
   into heading text.
2. Li page headers: raw contains 32 `Page X of Y` headers; EN polish should
   remove them without damaging body text.
3. Li roman suffix glue: raw may contain table/footnote suffixes glued to words;
   EN polish should normalize only systematic cases.
4. Table text fragmentation: raw table cells may contain broken line joins that
   later harm EN polish.
5. Formula/unit fragmentation: raw OCR may split `Вµm`, dimensions, and labels
   before EN polish.
6. Figure/table label baseline: raw has no `fig-*` ids yet, so any later link/id
   defects belong to EN polish, not Marker.

## Suggested Detector Command

Use a read-only detector first; do not run conversion or polish for EN raw triage.

```powershell
$Root = "D:\Git_Code\ZoteroPDF_2_MD"
Set-Location $Root

python scripts\audit_en_raw.py `
  --roots md_output\new\electrodes_W7TECQDX `
          md_output\new\headless_intracranial `
          md_output\new\headless_llm_medicine `
  --out md_output\new\_quality_audit\en_raw_audit.json
```

If `scripts/audit_en_raw.py` does not exist yet, create it before the next
manual article audit. The script should be read-only and should not call Marker,
Zotero, or WebDAV.

