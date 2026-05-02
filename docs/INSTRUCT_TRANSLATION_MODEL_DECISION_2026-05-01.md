# Instruct translation model decision, 2026-05-01

## Decision

For the LM Studio instruct HTML translation path, keep **Gemma 4 26B A4B
Instruct Q6** as the project model:

```text
p6_google_gemma-4-26b-a4b@q6_k
```

Qwen3VL 30B Q6 remains a comparison/regression candidate, not the primary
model for quality work.

This decision applies to the LM Studio instruct translation experiments and
future integration work around that path. The older local HF translation path
has been retired from the maintained project code.

## Evidence

The 7-article comparison set was generated here:

```text
bench_lmstudio_instruct/compare7_gemma_vs_qwen_20260430/
```

Open:

```text
bench_lmstudio_instruct/compare7_gemma_vs_qwen_20260430/index.html
```

Each article folder contains:

```text
source.html
qwen.html
gemma.html
pair.html
```

`pair.html` shows Qwen on the left and Gemma on the right for manual quality
review.

After the current guards and deterministic repairs, both models reached the
basic hard-audit bar on the comparison set:

- hard errors: 0;
- visible CJK contamination: 0;
- prompt leaks: 0;
- visible sentinel leaks: 0;
- HTML structure mismatches: 0.

The model choice is therefore based on manual translation quality review, not
only on the automated audit counters. The accepted project direction is:
**Gemma output is the preferred translation quality baseline.**

## Operational command

Use Gemma for future full-set LM Studio instruct HTML probes:

```powershell
python experiments\lmstudio_instruct_translation\run_html_probe.py --input-dir manual_review_en_polish_inlined_2026-04-27_round6 --output-dir bench_lmstudio_instruct --run-name gemma4_26b_<name> --model p6_google_gemma-4-26b-a4b@q6_k --auto-load --context-length 32768 --identifier gemma4_26b_q6_ctx32768 --max-tokens 8192 --timeout-s 900 --load-timeout-s 1800 --quality-gate-max-segments 64 --cjk-gate-max-segments 64 --unload-after
```

Keep `--unload-after` on by default. The runner must not leave an unused model
resident in LM Studio after a probe finishes.

## Notes

- Qwen is still useful for catching contamination and robustness regressions,
  especially CJK insertion defects.
- Long Latin run counts remain a soft audit signal: inspect examples before
  treating them as translation defects, because protected references and
  technical names can be legitimate.
- New quality work should optimize for Gemma first, then re-run Qwen only as a
  cross-model regression check.
