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

### Integrated MusicGen cache verification — 2026-11-26 EAT

User confirmed first integrated smoke run succeeded with cache_hit=false, and second run succeeded with cache_hit=true. Second result: UTC 2026-11-25T22:35:11.152295+00:00, job smoke-music-1795646111, model facebook/musicgen-small, prompt soft piano note sequence, duration requested 5 s, seed 42, music.wav, status success, error null, latency 0.027 s, gpu_minutes 0.0 (rounded), cost_usd 0.0, peak_gpu_memory_gib null (not measured on cache hit). Earlier standalone generation took 9.863 s; illustrative comparison is about 365x faster, not a controlled same-job speedup because first integrated latency was not supplied and prompts differ. Integrated short generation, playback and cache reuse verified by user; full-length generation remains pending.
