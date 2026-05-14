# HTML Stage Audit: md_output/new (2026-04-24)

## Scope

This audit covers the interrupted debug run stored in:

- `md_output/new`
- `logs/translate_new_only_20260424_150709.log`
- machine metrics: `md_output/new/_quality_audit/audit_metrics_20260424.json`

Stage model:

1. `01.en.raw.html`: raw Marker HTML snapshot.
2. `02.en.polish.html`: English polish + image inlining.
3. `03.ru.translate.html`: Gemma output before final RU polish.
4. `04.ru.polish.html`: RU polish + final image inlining.

The translation-only run was manually stopped. It did not fail internally:

- log ends with `forrtl: error (200): program aborting due to window-CLOSE event`;
- no `FAILED:` entries are present;
- only Ahmed and Kaiju reached final RU stages;
- Li was interrupted during translation;
- Merken, Schelles, Wang, Teo currently have only EN stages.

## Progress Snapshot

| Article | EN raw | EN polish | RU translate | RU polish | Status |
|---|---:|---:|---:|---:|---|
| Ahmed | yes | yes | yes | yes | complete, quality issues remain |
| Kaiju | yes | yes | yes | yes | complete, severe quality issues remain |
| Li | yes | yes | no | no | interrupted during RU translation |
| Merken | yes | yes | no | no | EN-only so far |
| Schelles | yes | yes | no | no | EN-only so far |
| Wang | yes | yes | no | no | EN-only so far |
| Teo | yes | yes | no | no | EN-only so far |

## Checks That Passed

| Check | Result | Meaning |
|---|---|---|
| Image data URI hashes vs sidecar files | 0 mismatches in all available final EN/RU files | Current image inlining does not corrupt bytes. If an image looks wrong in browser, it is likely CSS/browser/color-space/rendering, not base64 payload mismatch. |
| Nested anchors | 0 in all current stages | Recent idempotence fixes are holding. |
| Sentinel leaks | 0 in all current completed RU stages | No `@@Z2M_` or `<z2m...>` leaks in Ahmed/Kaiju final RU. |
| False `Unit N` links | 0 detected | The earlier `(Unit 1)` class of false citation link is not reproduced here. |
| RU-created link count | unchanged from EN to RU for Ahmed/Kaiju | RU processing is not creating new links; it preserves EN anchors and normalizes labels. |
| Li page headers | raw EN has 32 page headers, EN polish has 0 | EN cleanup removed `Li et al. Bioelectronic Medicine ... Page X of 33`. |
| Li glued roman suffixes | raw EN has `Foilii`, `Laser ablationiv`, `Plasma (dry) etchingv`; EN polish has 0 known hits | Current EN polish fixes this class before translation. |
| Kaiju DOI corruption | not reproduced | `Front. Neural Circuits 11:20. doi: 10.3389/fncir.2017.00020` stays structurally intact. |
| RU `Figure/Table` English labels after RU polish | 0 generic `Figure N` / `Table N` hits in Ahmed/Kaiju final RU | The deterministic RU label normalizer works for common English labels. |

## Log Findings

| Article | Unique LLM calls | Completed calls | Segments | Warnings |
|---|---:|---:|---:|---|
| Ahmed | 823 | 823 | 377 | identity residuals: 10, wide paragraph recovery: 14, quality gate unresolved: 10 |
| Kaiju | 263 | 263 | 246 | identity residuals: 3, wide paragraph recovery: 5, quality gate unresolved: 3 |
| Li | 855 | 854 | unknown | interrupted before `03.ru.translate.html` was written |

Root causes from the log:

1. Translation is too expensive per article because recovery/quality passes trigger many extra model calls.
2. The run has no segment-level resume: after stopping Li at call 855, Li must be restarted from the article level.
3. Quality gates detect some English residuals but do not fail the article and cannot always repair them.
4. The log contains the tokenizer warning about `fix_mistral_regex`; current code now passes `fix_mistral_regex=True`, so the next run must confirm that this warning disappears.

## Defect Register

### D1. Kaiju: Figure 1 image is missing from the structured article body

Status: open.

First broken stage: `01.en.raw.html`.

Evidence:

- In Kaiju raw HTML, the only images before the article title are `_page_0_Picture_1.jpeg` and `_page_0_Picture_2.jpeg`.
- Their dimensions are small: `382x91` and `85x89`, consistent with page/logo fragments rather than the full Figure 1 panel.
- The Figure 1 visual content appears as OCR text in a heading:
  `A 96ch flexible surface electrode array Fabricated electrode Thickness = 20Вµm ...`
- The next real figure image in the document sequence is `_page_3_Figure_10.jpeg`, followed by `FIGURE 2`.

Probable cause:

Marker did not emit the full Figure 1 image as an image node. It OCR-extracted text from the figure into an `h1`, then emitted the caption as text. EN polish cannot reconstruct a missing image if Marker never produced one.

Fix direction:

1. Add a structural detector for caption-without-nearby-image around `FIGURE N |`.
2. Add a Marker artifact check that flags when `fig-1` exists but no preceding/nearby image with matching page/figure order exists.
3. If possible, keep a fallback crop/image extraction artifact from Marker/PDF pages for figures that become OCR-only headings.

### D2. Kaiju: Figure 1 caption label becomes `Р РђР”РРћР“Р РђРњ 1`

Status: open.

First broken stage: `03.ru.translate.html`.

Evidence:

- Source: `FIGURE 1 | Electrode fabrication and experimental paradigm...`
- RU translate and final RU: `Р РђР”РРћР“Р РђРњ 1 | РР·РіРѕС‚РѕРІР»РµРЅРёРµ СЌР»РµРєС‚СЂРѕРґРѕРІ...`
- The paragraph has `id="fig-1"`, so the correct label is deterministic even if the model mistranslates it.

Probable cause:

The model translated the caption label itself. RU polish normalizes common forms like `Figure`, `Fig.`, `Р¤РёРіСѓСЂР°`, and broken `Р РёСЃСѓРЅ...`, but it does not know that `Р РђР”РРћР“Р РђРњ` is a hallucinated figure label.

Fix direction:

Do not trust the model for caption labels. For any paragraph with `id="fig-N"`, rewrite the visible caption prefix deterministically to `Р РёСЃСѓРЅРѕРє N.` after translation, regardless of the model's first token.

### D3. Kaiju: abbreviation paragraph hallucinated a business glossary

Status: critical, open.

First broken stage: `03.ru.translate.html`.

Evidence:

Source:

```text
Abbreviations: SEP, Sensory evoked potential; ECoG, Electrocorticogram; MEMS, ...
```

RU output starts with unrelated content:

```text
**Abbreviations:** * CEO - РіРµРЅРµСЂР°Р»СЊРЅС‹Р№ РґРёСЂРµРєС‚РѕСЂ * COO - РѕРїРµСЂР°С†РёРѕРЅРЅС‹Р№ РґРёСЂРµРєС‚РѕСЂ * CFO ...
```

Only after the hallucinated business glossary does it return to some source abbreviations.

Probable cause:

The model treated `Abbreviations:` as an instruction/header to generate a generic glossary. Current guards protect some uppercase acronyms, but they do not validate that the output did not introduce many new acronym definitions absent from the source. Mixed-case scientific terms such as `ECoG` and `ВµECoG` are also not covered by the simple `[A-Z]{2,5}` abbreviation mask.

Fix direction:

1. Treat `Abbreviations:` paragraphs as a special structured block.
2. Preserve the abbreviation keys exactly: `SEP`, `ECoG`, `MEMS`, `COG`, `BMI`, `Ch`, `D1`... must remain present, and unrelated keys like `CEO`, `COO`, `CFO` must fail validation.
3. Extend abbreviation masking to mixed-case and prefixed forms: `ECoG`, `iECoG`, `ВµECoG`, `PtIr`, `IrOx`, `RuOx`, `TiN`, etc.
4. Add a hallucinated-acronym guard: if output introduces several uppercase/mixed-case abbreviations not present in source, retry locally or keep a deterministic structured translation.

### D4. Kaiju: English residuals remain in RU body

Status: open.

First broken stage: `03.ru.translate.html`; persists in `04.ru.polish.html`.

Evidence:

Title:

```text
Р’С‹СЃРѕРєРѕРµ РїСЂРѕСЃС‚СЂР°РЅСЃС‚РІРµРЅРЅРѕ-РІСЂРµРјРµРЅРЅРѕРµ СЂР°Р·СЂРµС€РµРЅРёРµ ECoG Recording of Somatosensory РџРѕС‚РµРЅС†РёР°Р»С‹...
```

Methods paragraph:

```text
Рљ СЃРѕР¶Р°Р»РµРЅРёСЋ, the detailed anesthesia records were lost. The approximate dosage of each drug was ...
```

Log:

- `en_residual_segments=3`
- `en_residual_quality_gate_attempted=3`
- `en_residual_quality_gate_recovered=0`
- `en_residual_quality_gate_unresolved=3`

Probable cause:

The quality gate sees residual English but treats it as warning-only. It does not fail the article, and its retry strategy cannot recover these segments. Formula-heavy paragraphs and technical acronyms make the residual detector conservative.

Fix direction:

1. Make unresolved body residuals a hard failure for debug runs.
2. Save a per-segment residual report with source and translated text.
3. For residual body paragraphs, retry with a stronger prompt and smaller unit of text.
4. Exclude formulas/references, but not ordinary prose that contains English sentences.

### D5. Kaiju: `ECoG` / `ВµECoG` term policy is inconsistent

Status: open.

First broken stage: `03.ru.translate.html`.

Evidence:

- `Electrocorticogram (ECoG)` becomes `Р­Р»РµРєС‚СЂРѕРєРѕСЂС‚РёРєР°Р»СЊРЅС‹Р№ СЂРµРіРёСЃС‚СЂ (Р­РљР )`.
- `РљР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР°: ВµECoG` keeps `ВµECoG`, while body uses `Р­РљР ` / `Р­РљРѕР“`.
- The title keeps `ECoG Recording` in English.

Probable cause:

There is no deterministic domain glossary for mixed-case neuroscience abbreviations. The generic acronym rule mostly protects all-uppercase tokens, but `ECoG` is mixed case and therefore remains model-dependent.

Fix direction:

Add a glossary/mask layer for scientific mixed-case abbreviations and material names. At minimum:

- preserve `ECoG`, `ВµECoG`, `iECoG`, `SEP`, `ERP`, `BMI`, `MEMS`;
- optionally translate expansions, but keep abbreviation tokens exact.

### D6. Ahmed: escaped BioRender link becomes a real malformed anchor and eats caption text

Status: critical, open.

First broken stage: `03.ru.translate.html`.

Evidence:

EN source in `02.en.polish.html` contains escaped anchor text inside the caption:

```html
&lt;a href="https://BioRender.com/qms5tta"&gt;https://BioRender.com/qms5tta&lt;/a&gt;
```

RU output turns it into a real `<a>` tag and the rest of the caption becomes part of the link:

```html
<a href="https://BioRender.com/qms5tta">https://BioRender.com/qms5tta&amp;ltР¤РѕС‚РѕРіСЂР°С„РёСЏ РїРѕР»РЅРѕСЃС‚СЊСЋ Р¶РµСЃС‚РєРѕР№...
...
</a>
```

Final RU still contains English tail fragments:

```text
in NHP. Inset shows a \(\bf c\) Photograph of a steeltrode with flexible tether cable...
```

Probable cause:

The translator receives escaped HTML-like text as normal text. The model unescapes or rewrites `&lt;a ...&gt;` into actual HTML. Because translation operates on tag-split HTML parts, escaped tags are not protected by the normal tag preservation path.

Fix direction:

1. Mask escaped HTML entities that represent tags before model calls.
2. Mask URLs and escaped anchor snippets as atomic non-translatable placeholders.
3. After translation, validate that no new real HTML tags appeared inside a text segment unless they existed as real tags in the source segment.
4. For figure captions, use paragraph-wide recovery when escaped tags or long subfigure sequences are present.

### D7. Ahmed: units and formula-adjacent text are damaged

Status: open.

First broken stage: mixed; source has fragile math/text unit splits, RU translation amplifies them.

Evidence:

Final RU Figure 1 caption includes:

```text
РїРѕРїРµСЂРµС‡РЅС‹Рј СЃРµС‡РµРЅРёРµРј 140 РјРј \(\mu\) Рј С… 280 \(\mu\) Рј
```

The intended value is micrometers, not `РјРј \(\mu\) Рј`.

Probable cause:

The source contains unit fragments split across math and text, such as `\(\mu\) m` and `\(\mu\) РґРёР°РјРµС‚СЂ m`. Formula masking protects `\mu`, while the adjacent `m` remains ordinary translatable text. The model then translates or duplicates the surrounding unit words.

Fix direction:

1. Normalize micro-units before translation: `\(\mu\) m`, `\mu m`, `Вµ m` -> atomic `Вµm` or protected `@@Z2M_UNIT...@@`.
2. Protect dimension expressions such as `140 Вµm x 280 Вµm`, `15 Вµm diameter`, `50 Вµm apart` as unit-aware spans.
3. Restore localized unit text deterministically after translation.

### D8. Ahmed and Kaiju: metadata and author-name policy is inconsistent

Status: open.

First broken stage: `03.ru.translate.html`.

Evidence:

Ahmed:

```text
Р¦РёС‚Р°С‚Р° СЌС‚РѕР№ СЃС‚Р°С‚СЊРё: Ahmed, Z., Kimukin, I., Jain, V.
Рё РґСЂ. Рё РґСЂ. ...
Р—Р°Р±РёСЂ РђС…РјРµРґ, РР±СЂР°РіРёРј РљРёРјСѓРєРёРЅ, Р’РёС€Р°Р» Р”Р¶Р°Р№ ...
```

Kaiju:

```text
Taro Kaiju 1, 2, РљСЌР№РёС‚Рё Р”РѕР№ 1, 2, Masashi Yokota ...
```

Probable cause:

Author/citation metadata is translated as normal prose. The prompt says not to modify proper names, but the model does so inconsistently. Also, citation text can be split into adjacent text nodes, producing repeated `Рё РґСЂ.`.

Fix direction:

Choose a deterministic policy:

1. safest: mark author lists and citation lines as `translate="no"`;
2. or structured transliteration: transliterate all author names consistently in a dedicated metadata pass.

The current mixed policy is not stable enough.

### D9. Ahmed and Kaiju: terminology and grammar quality remains low even after structural polish

Status: open, model/prompt/glossary class.

Evidence:

Ahmed:

- `РґР»СЏ РІС‹СЃРѕРєРѕСЂР°Р·СЂРµС€Р°СЋС‰РµРіРѕ Р·Р°РїРёСЃРё`
- `СЌР»РµРєС‚СЂРѕРґСѓ`
- `РЅРµР№СЂРѕРЅРЅРѕР№ РїСЂРѕР±С‹`
- `СЃС‚Р°Р»СЊРЅС‹Рµ РґР°С‚С‡РёРєРё`
- `СЃС‚РµСЂР¶РµРЅСЊ`, `С€С‚Р°РЅРіР°`, `Р·РѕРЅРґ`, `СЌР»РµРєС‚СЂРѕРґР°` used inconsistently for the same probe/shank concept.

Kaiju:

- `СЃРµРЅСЃРѕСЂРЅР°СЏ РґРµРєРѕР№Рґ`
- `Р°Р»РёР°СЃРёРЅРіРѕРІР°РЅРёРµ`
- `РїРѕСЃС‚С†РµРЅС‚СЂР°Р»СЊРЅС‹Р№ РіРёР·Сѓ`
- `РїСЂРѕР±РёС‚С‹С… РєР°РЅР°Р»РѕРІ`
- `РЁС‚СЂР°Р± РїРѕРєР°Р·С‹РІР°СЋС‚`

Probable cause:

The pipeline has structural context windows, but it lacks a domain glossary and document-level terminology memory. The model translates many short text nodes and captions independently enough that term choices drift.

Fix direction:

1. Add a domain glossary for electrodes/neuroengineering terms.
2. Add document-level term memory extracted from title/abstract/keywords.
3. Run a deterministic post-edit for high-confidence terminology only.
4. Keep grammar/style improvement as a separate quality pass; do not mix it with link/image cleanup.

### D10. Li: EN defects are mostly fixed, but RU cannot be assessed yet

Status: partial.

First broken stage for old symptoms: `01.en.raw.html`; fixed by `02.en.polish.html`.

Evidence:

Raw EN:

- 32 page headers like `Li et al. Bioelectronic Medicine (2026) 12:6 Page X of 33`;
- known glued roman suffixes: `Foilii`, `Laser ablationiv`, `Plasma (dry) etchingv`.

EN polish:

- page headers: 0;
- known glued roman suffixes: 0.

Translation status:

- Li was interrupted at LLM call 855;
- no `03.ru.translate.html`;
- no `04.ru.polish.html`.

Probable cause:

The EN cleanup is working for these classes. The remaining blocker is translation runtime and lack of segment-level resume.

Fix direction:

1. Add per-article skip/resume for completed RU.
2. Add segment-level checkpoints for long articles.
3. Add a fast debug mode that can translate a selected article or selected paragraph range.

### D11. Translation runtime is too high for iterative QA

Status: open.

Evidence:

- Ahmed: 377 final segments, 823 unique model calls, about 2h34m.
- Kaiju: 246 final segments, 263 model calls, about 59m.
- Li: 855 calls before interruption and no saved RU result.

Probable cause:

The current translation path combines windowed batching with multiple recovery layers and final quality gates. This improves safety but makes long articles expensive. Because partial segment outputs are not checkpointed, a stop discards hours of work for the current article.

Fix direction:

1. Implement segment-level checkpoint/resume.
2. Save per-segment source/target diagnostics for failed residuals.
3. Add configurable hard failure on unresolved residuals for debug runs.
4. Add selected-article and selected-stage translation commands.

## Root Cause Map

| Layer | Confirmed issues |
|---|---|
| Marker extraction | Kaiju Figure 1 missing as image; figure visual OCR text became heading. |
| EN polish | Mostly effective in this run; fixed Li headers and roman suffixes; no image hash corruption. |
| Gemma segmentation/reassembly | English residuals survive; no segment checkpointing; escaped HTML-like text can become real tags. |
| Gemma model behavior | Abbreviation hallucination, bad title translation, terminology drift, grammar/case issues. |
| RU polish | Common `Figure/Table` normalization works, but hallucinated caption labels like `Р РђР”РРћР“Р РђРњ 1` are not corrected. |
| Observability | Warnings exist but do not fail debug runs; no per-problem segment report yet. |

## Immediate Fix Priority

1. Add hard validation for new HTML tags inside translated text segments.
2. Add deterministic caption-prefix rewrite using `id="fig-N"` and table ids/context.
3. Add abbreviation block validator and mixed-case abbreviation masking.
4. Add unresolved-English residual hard fail in debug mode.
5. Add segment-level checkpoint/resume before running Li again.
6. Add unit-span normalization/protection for `Вµm`, `\mu m`, and dimension expressions.
7. Add metadata author/citation protection policy.
8. Add Marker-stage warning for caption without nearby figure image.

## Recommended Next Verification

Do not rerun the full PDF -> EN stage yet. The EN snapshots are enough to fix most current issues.

Recommended order:

1. Implement the deterministic validators/postprocessors above.
2. Re-polish existing `02.en.polish.html` and completed RU files where possible.
3. Run a translation-only resume for one article, preferably Kaiju, because it has multiple severe but compact defects.
4. Only after Kaiju is clean, continue Li with checkpoint/resume enabled.


