# Architecture

Semi-automated pipeline: local orchestration on the Mac, GPU-heavy stages
(music, video) executed manually in Google Colab on a T4, with a Google Drive
folder as the asset-exchange layer. `storyboard.json` is the single source of
truth — every stage reads it and re-validates it against
`schema/storyboard.schema.json`.

## Data flow

```
Gemini ──► storyboard.json ──► Cloudflare keyframes ─┐
             │                                      │ (Drive exchange)
             ├─► TTS narration.wav ────────────────►▼
             │     (TTS_PROVIDER: kokoro local | gemini API)
             │                            Colab: gpu_video.py  → shots/*.mp4
             └─► music job ──────────────────► gpu_music.py  → music.wav
                                                        │
ffmpeg assemble ◄─ collect (results + log merge) ◄───────┘
      │─► outputs/final/heritage_short.mp4
      └─► outputs/radio_cut/radio_cut.m4a
```

## Modules

- **`pipeline/run.py`** — orchestrator (`--stage`, `--all`, `--resume`).
  Prints the Colab handoff checklist after `package`.
- **`pipeline/storyboard.py`** — Gemini → `storyboard.json`, schema-validated.
- **`pipeline/tts.py`** — narration provider dispatch on `TTS_PROVIDER`
  (`kokoro` default, `gemini` optional). Gemini voice names are mapped to the
  Kokoro default when the local provider is selected.
- **`pipeline/kokoro_client.py`** — local Kokoro-82M TTS →
  `outputs/narration/narration.wav`. CPU-only, ~330 MB HF weights on first
  call, uses `espeakng-loader` (pip) or system espeak-ng for English G2P.
  Results cached by script+voice+speed hash; `cost_usd: 0.0`.
- **`pipeline/gemini_client.py`** — Gemini TTS (optional provider).
- **`pipeline/cloudflare_client.py`** — Workers AI flux-1-schnell →
  `outputs/keyframes/<shot_id>.png`, sha256-cached in `.cache/`.
- **`pipeline/exchange.py`** — `package_job()` writes `job.json` + inputs and
  syncs `gpu_*.py` into the exchange dir; `collect_results()` copies Colab
  results into `outputs/` and merges `results.jsonl` into `runs.jsonl`
  (idempotent via `.cache/collected_jobs.json`).
- **`pipeline/gpu_music.py` / `gpu_video.py`** — Colab workers for ACE-Step 1.5
  and Wan 2.2 TI2V-5B. Heavy deps are lazily imported so they stay importable
  locally; not called from local stages.
- **`pipeline/assemble.py`** — ffmpeg concat to uniform 480x480/24fps clips
  (`tpad` pads short clips), narration+music mix (`amix`, music at ~30%).
  Missing shot videos fall back to zoompan clips from keyframes.
- **`pipeline/utils.py`** — env, JSON, storyboard validation, hashing/caching,
  `runs.jsonl` logging, retry, `write_pcm_wav`, directory setup.
- **`pipeline/smoke_test.py`** — live provider connectivity checks.
- **`notebooks/`** — thin Colab wrappers: mount Drive → install deps → smoke
  test → `run_job(job.json)`.
- **`tests/`** — offline unit tests (providers/ffmpeg mocked).

## Run log

`runs.jsonl` — append-only, one object per model call or notable event:
`timestamp`, `job_id`, `stage`, `shot_id`, `model`, `parameters`, `seed`,
`latency_seconds`, `cost_usd` (0.0 for local Kokoro; cache hits log
`parameters.cached: true`), `gpu_minutes`, `status` (success/failed/fallback),
`error`, `files` (Colab entries). Colab entries are written to
`results.jsonl` on Drive and merged on `collect`.

## T4 GPU constraints (14.56 GB)

- Wan 2.2: TI2V-5B, fp16 transformer + fp32 VAE (avoids black frames),
  `enable_model_cpu_offload`, VAE tiling, 480x480, 49 frames (~2 s), ~30 steps.
- ACE-Step: fp16 (`bf16=False` — T4 has no bf16 units), `cpu_offload=True`.
- Any shot failing on GPU → ffmpeg keyframe fallback at assemble; the film
  always completes.

## Outputs

- `outputs/keyframes|shots|music|narration|radio_cut|final/` — generated, gitignored
- `outputs/kept/` — hand-picked artifacts retained for assessment (tracked)
- `exchange/` — local fallback for the Drive exchange dir (gitignored)
