# LM Studio instruct translation experiments

This folder keeps benchmark and compatibility wrappers for the packaged
LM Studio HTML translation runner.

The maintained production path is `pdf-html-translate`, backed by
`zoteropdf2md.translation`.  The scripts here delegate to that package code
where they need the production runner/client.

## What it tests

- OpenAI-compatible LM Studio endpoint: `http://127.0.0.1:1234/v1`.
- Old marker protocol: `<z2m-i1/>...<z2m-i2/>...`.
- C2-like HTML window settings: `window=4`, `overlap=1`, `max_chars=20000`.
- Same `translate_html_text_nodes()` HTML segmentation/recovery machinery.

This answers one question:

```text
Was old C2 unstable because marker batching is bad by itself,
or because the previous HF translation path was not a general instruct model?
```

## Current project decision

As of 2026-05-01, the project keeps **Gemma 4 26B A4B Instruct Q6** as the
primary LM Studio instruct translation model:

```text
p6_google_gemma-4-26b-a4b@q6_k
```

Qwen3VL 30B Q6 remains a comparison/regression model, especially for checking
CJK contamination behavior, but it is not the preferred quality baseline.

Decision record:

```text
docs/INSTRUCT_TRANSLATION_MODEL_DECISION_2026-05-01.md
```

The accepted 7-article comparison output is:

```text
bench_lmstudio_instruct/compare7_gemma_vs_qwen_20260430/index.html
```

## Before running

Start LM Studio local server:

```text
LM Studio -> Developer -> Local Server -> Start Server
```

Load exactly one model, or pass the exact model id reported by `/v1/models`.
By default the scripts discover the active port with:

```powershell
lms server status
```

You can still pass an endpoint explicitly. A typical endpoint looks like:

```text
http://127.0.0.1:1234/v1
```

If LM Studio shows another port, pass it explicitly:

```powershell
--base-url http://127.0.0.1:<port>/v1
```

List model ids:

```powershell
python experiments\lmstudio_instruct_translation\run_synthetic.py --list-models
```

If you get `ConnectionRefusedError` / `WinError 10061`, the local server is not
listening at the selected URL. Start the LM Studio local server or fix
`--base-url`.

Use only models that are explicitly instruct/chat-tuned for the main probe.
Base models are useful only as a negative control, because this experiment tests
whether a true instruct model can follow the old `Rules:` + marker protocol.

From the current local list, the primary candidate is:

- `p6_google_gemma-4-26b-a4b@q6_k` (`Gemma 4 26B A4B Instruct Q6`).

Secondary comparison candidates:

- `p6_qwen_qwen3-vl-30b@q6_k` / the exact `Qwen3 VL ... Instruct` id reported
  by LM Studio;
- `p6_google_gemma-4-31b@q8_0` if you explicitly want to test the heavier
  Gemma variant.

Do not use `qwen/qwen3.5-35b-a3b` as the main instruct baseline: it is not
marked as an instruct model in the local list. It can be tested separately only
as a base-model control.

## Synthetic sanity check

Run this before full HTML probes:

```powershell
python experiments\lmstudio_instruct_translation\run_synthetic.py --model "p6_qwen_qwen3-vl-30b@q6_k" --auto-load --context-length 32768
```

Gemma example:

```powershell
python experiments\lmstudio_instruct_translation\run_synthetic.py --model "p6_google_gemma-4-26b-a4b@q6_k" --auto-load --context-length 32768
```

Use the exact ids from `--list-models` if these differ on your machine.

Output:

```text
experiments/lmstudio_instruct_translation/out/synthetic_<model>.json
```

The sanity probe checks:

- marker preservation;
- DOI/URL/formula preservation;
- placeholder preservation;
- acronym preservation;
- presence of Cyrillic output.

## Li/Wang HTML probe

Qwen instruct:

```powershell
python experiments\lmstudio_instruct_translation\run_html_probe.py --input-dir manual_review_en_polish_inlined_2026-04-27_round6 --run-name qwen3vl_instruct_c2_li_wang --model "p6_qwen_qwen3-vl-30b@q6_k" --auto-load --context-length 32768 --article-regex "03_Li|06_Wang"
```

Gemma:

```powershell
python experiments\lmstudio_instruct_translation\run_html_probe.py --input-dir manual_review_en_polish_inlined_2026-04-27_round6 --run-name gemma4_instruct_c2_li_wang --model "p6_google_gemma-4-26b-a4b@q6_k" --auto-load --context-length 32768 --article-regex "03_Li|06_Wang"
```

## Two-model benchmark

Run the current Qwen and Gemma instruct candidates with the same synthetic and
HTML settings when you need a regression comparison:

```powershell
python experiments\lmstudio_instruct_translation\run_benchmark.py --models qwen3vl30b,gemma4_26b --article-regex "06_Wang" --run-prefix bench_c2 --auto-load --context-length 32768
```

The benchmark unloads each candidate after its synthetic + HTML block finishes,
so Qwen is not left resident while Gemma loads. Pass `--keep-loaded` only when
you intentionally want the final model to stay in LM Studio.

The benchmark keeps CJK contamination as a hard quality signal. For Russian
output, any visible CJK character such as `\u8026` is treated as a defect and
the HTML translator retries the affected segment through the CJK quality gate.

Output:

```text
bench_lmstudio_instruct/<run-name>/
  summary.json
  01_<article>/
    02.en.polish.html
    03.ru.translate.html
    calls.jsonl
    translation_report.json
```

## Useful knobs

```powershell
--max-tokens 8192
--context-window-segments 4
--context-overlap-segments 1
--context-max-window-chars 20000
--quality-gate-max-segments 8
--cjk-gate-max-segments 8
--disable-quality-gate
--disable-cjk-gate
--disable-marker-batching
--auto-load
--context-length 32768
--gpu max
--ttl 3600
--unload-after
```

For an apples-to-apples old C2 probe, keep marker batching enabled.

## Compare against previous runs

Primary comparison points:

- `prompt_leak_count`;
- `visible_sentinel_leak_count`;
- `raw_sentinel_like_count`;
- `cjk_contamination_count`;
- `long_latin_run_count`;
- `structure_mismatches`;
- `call_summary.call_count`;
- elapsed time;
- manual check of Wang title/abstract.

Gemma remains the project baseline while the probe shows no prompt leaks, no
marker leaks, no CJK contamination, and stable HTML structure.
