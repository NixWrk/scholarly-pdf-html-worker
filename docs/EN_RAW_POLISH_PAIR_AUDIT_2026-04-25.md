# EN Raw / EN Polish Pair Audit 2026-04-25

Scope: seven canonical pairs from `docs/EN_RAW_DEBUG_TEST_PLAN.md`.
Each pair was checked as `01.en.raw.html` -> regenerated `02.en.polish.html`.

## Pair Matrix

| Article | img raw->polish | captions raw->polish | captions without nearby image | page headers | OCR panel heading | polish fig ids | polish fig links | polish table ids | polish table links | fig/table `#page-*` refs |
|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|
| Ahmed 2026 | 10->10 | 8->8 | []->[] | 0->0 | []->[] | 8 | 64 | 0 | 0 | 0 |
| Kaiju 2017 | 10->10 | 9->9 | [1]->[1] | 0->0 | [31]->[] | 9 | 48 | 1 | 2 | 0 |
| Li 2026 | 17->17 | 14->14 | []->[] | 32->0 | []->[] | 14 | 52 | 7 | 9 | 0 |
| Merken 2022 | 8->8 | 5->5 | []->[] | 0->0 | []->[] | 5 | 34 | 1 | 2 | 0 |
| Schelles 2025 | 8->8 | 4->4 | []->[] | 0->0 | []->[] | 4 | 16 | 2 | 7 | 0 |
| Wang 2017 | 24->24 | 18->18 | []->[] | 0->0 | []->[] | 18 | 26 | 4 | 3 | 0 |
| Teo 2025 | 3->3 | 1->2 | []->[] | 0->0 | []->[] | 2 | 3 | 1 | 2 | 0 |

Notes:

- Caption counts now exclude known non-caption forms such as `Fig. N (See legend on next page.)`, `Fig. N was ...`, and subfigure body references like `Figure 2(B) shows ...`.
- `captions without nearby image` uses a wider block window because panel labels and short continuation paragraphs can sit between a caption and its image.
- `fig/table #page-* refs` counts page anchors that still appear to be figure/table references after polish. It is now 0 across the corpus.

## Marker / EN Raw Problems

1. Kaiju 2017, Figure 1:
   - Raw has an OCR-only figure panel heading immediately before the caption:
     `A 96ch flexible surface electrode array Fabricated electrode Thickness = 20um ...`
   - Raw has the `FIGURE 1 | ...` caption, but no nearby image for Figure 1.
   - The sidecar set has 10 images, but this figure panel is represented as text, not as an extracted image.
   - First broken stage: `01.en.raw.html`.

2. Li 2026 page headers:
   - Raw contains 32 `Li et al. Bioelectronic Medicine (2026) 12:6 Page X of 33` headers.
   - EN polish removes them: 32 -> 0.

3. Teo 2025 Figure 2 caption shape:
   - Raw has a LaTeX-like caption wrapper:
     `\label{lem:fig.2} \textbf{Fig. 2} \ | \ \textbf{...}`
   - EN polish normalizes it into visible caption text and now gives it `id="fig-2"`.

4. Raw extraction fragmentation:
   - Table/citation text still contains layout fragments such as `Parylene Ci`, `LCPsii`, `SMPsiii`, and split compounds in Li.
   - Merken/Schelles/Ahmed contain many real hyphenated compounds (`micro- and nanofabrication`, `inter- and intraoperative`) that should not be blindly joined.
   - EN polish now handles the audited glued roman suffix forms with table-aware guards.

## EN Polish Fixes Applied

1. Caption/body merge guard:
   - Sentence repair no longer starts from figure/table caption nodes.
   - Li/Kaiju merge signatures are now absent:
     `Electrode fabrication and experimental paradigm. (0.12`, `cross-sectional diagram. vary in diameter`, `multichannel cuff electrode. adequate insulation`, `stimulation and recording. The recording sites`, `blood pressure and heart rate. Ren`.

2. Figure caption anchors:
   - Wrapped labels such as `<b> Fig. 2 </b> ...` and `<strong>Fig. 2</strong> | ...` now receive `fig-*` ids.
   - False positives are filtered for body references such as `Figure 2(B) shows ...`, `Fig. 14 was ...`, and legend stubs.
   - Unique and total figure id counts now match in every regenerated polish file.

3. Existing page-anchor retargeting:
   - Figure/table references already wrapped as `href="#page-*"` are retargeted to `#fig-*` / `#table-*`.
   - The rewrite handles split punctuation forms such as `2)`, `1(`, and subfigure references.

4. Table anchors and links:
   - Table captions in paragraphs and headings now get `table-*` ids.
   - Plain and existing page-wrapped table references are linked to semantic table anchors.

5. Table-cell roman suffixes:
   - Short table cells now split glued roman footnote markers, for example `Parylene Ci` -> `Parylene C i`, `LCPsii` -> `LCPs ii`, and `SMPsiii` -> `SMPs iii`.
   - The existing prose-level rule also closes `Foilii`, `Laser ablationiv`, and `Plasma (dry) etchingv`.

## Closed vs Not Closed

Closed:

- Li raw page headers: closed by EN polish.
- Kaiju OCR panel heading text: removed by EN polish.
- Teo raw LaTeX-like Figure 2 caption: readable and anchored.
- Image count is stable across all pairs; no polish image loss detected.
- Caption/body merges introduced by polish: closed.
- Li/Teo wrapped figure caption anchors: closed.
- Existing figure/table `#page-*` references: closed for semantic refs.
- Table anchors/reference links: implemented for paragraph and heading captions.
- Duplicate `fig-*` ids from legend stubs/body sentences: closed.
- Audited glued roman suffix fragments in prose/table cells: closed.

Not closed:

- Kaiju Figure 1 image is still absent because the image was not extracted into raw; polish cannot reconstruct it from text.
- Kaiju Figure 1 caption still has no nearby image, even after OCR heading removal.

## Next Fix Order

1. Investigate Marker/raw image extraction for Kaiju Figure 1.
2. Promote the pair audit into a repeatable regression command so future polish changes can rerun this matrix automatically.
