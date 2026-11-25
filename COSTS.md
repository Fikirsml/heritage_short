# Costs

Per-run and cumulative spend tracking. No spend recorded yet.

## Provider rates

<!-- TODO: fill in current pricing before the first paid API call -->

| Provider   | Operation     | Unit     | Price                                                 | Source / date checked |
| ---------- | ------------- | -------- | ----------------------------------------------------- | --------------------- |
| Kokoro-82M | TTS narration | per call | $0 (local CPU; model: hexgrad/Kokoro-82M, Apache-2.0) | 2026-11-25            |
| TBD        | TBD           | TBD      | TBD                                                   | TBD                   |

## Spend log

| Date | Run ID | Provider | Operation | Units | Cost (USD) |
| ---- | ------ | -------- | --------- | ----- | ---------- |
| —    | —      | —        | —         | —     | —          |

## Budget

- **Cap**: TBD
- **Notes**: TBD

## MusicGen migration (2026-11-26)

Default music worker: `facebook/musicgen-small`, FP16 on Colab T4. See [FAILURES.md](FAILURES.md) F011–F016 for measured results and provider decision. The new notebook pins Transformers 4.57.6 and SciPy 1.16.3; run smoke first, then explicitly select the packaged job ID. Worker generates up to 25-second segments, blends with one-second crossfades, trims to target length and caches by generation settings. Model weights are CC BY-NC 4.0; assignment substitution acceptance and full-length integration are pending. Measured standalone generation: 9.863 s for 5.06 s audio, 1.215 GiB peak allocated GPU memory, $0 API cost; not a full-track benchmark.
