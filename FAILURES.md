# Failures Log

Append-only record of things that broke, misbehaved, or produced bad output — and what fixed them (or didn't).

## Entry format

- **ID**: F###
- **Date**: YYYY-MM-DD
- **Stage**: which pipeline stage
- **Symptom**: what you observed
- **Root cause**: what actually caused it
- **Fix**: what resolved it (or current workaround)
- **Status**: open / resolved / wontfix

## Entries

### F001 — Google's text test couldn't find the model

- **Date**: 2026-11-25
- **Stage**: smoke test (Gemini)
- **Symptom**: The check that asks Google to reply "OK" failed with "HTTP 404" — meaning the service was reached, but the thing we asked for doesn't exist.
- **Root cause**: The model name we sent (`gemini-2.5-flash`) isn't available to this account/API key — likely a wrong or outdated model name in `.env`.
- **Fix**: Not fixed yet. Check the exact model name in the Google AI Studio console and update `GEMINI_MODEL` in `.env`.
- **Status**: open

### F002 — Google's voice test rejected our request

- **Date**: 2026-11-25
- **Stage**: smoke test (Gemini TTS)
- **Symptom**: The check that asks Google to speak a test sentence failed with "HTTP 400" — meaning Google's servers understood we were knocking, but said the request was badly formed.
- **Root cause**: Unknown yet — most likely the voice model name isn't right for this account, or the request settings don't match what that model expects.
- **Fix**: Not fixed yet. Confirm the TTS model name and whether this account has access to it.
- **Status**: open

### F003 — Cloudflare test never started: missing login details

- **Date**: 2026-11-25
- **Stage**: smoke test (Cloudflare)
- **Symptom**: The image-generation check failed instantly (0.00s) before even contacting Cloudflare.
- **Root cause**: The project couldn't find Cloudflare's account ID and API token — those boxes in `.env` are still empty.
- **Fix**: Not fixed yet. Fill in `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in `.env` (values come from the Cloudflare dashboard).
- **Status**: open

### F004 — Kaggle tool isn't installed

- **Date**: 2026-11-25
- **Stage**: smoke test (Kaggle)
- **Symptom**: The Kaggle check failed instantly with "module not found" — the computer was asked to use a tool it doesn't have.
- **Root cause**: The `kaggle` package was added to `requirements.txt`, but it hasn't been installed into the project's environment yet.
- **Fix**: Run `source .venv/bin/activate && pip install -r requirements.txt`. A Kaggle credentials file (`~/.kaggle/kaggle.json`) will also be needed for this check to pass.
- **Status**: open

### F005 — Upload to GitHub failed

- **Date**: 2026-11-25
- **Stage**: repo setup
- **Symptom**: `git push` failed with "does not appear to be a git repository."
- **Root cause**: Two things at once — the project was trying to reach GitHub over SSH (which wasn't set up on this machine), and the typed address may not have matched the real repo name.
- **Fix**: Switched the remote address to the HTTPS form and logged in. `git pull` and pushes work now.
- **Status**: resolved

### F006 — Test runner mixed up the two kinds of tests

- **Date**: 2026-11-25
- **Stage**: test setup
- **Symptom**: Running `pytest` reported errors like "fixture 'model' not found" and tried to run the live provider checks as if they were offline unit tests.
- **Root cause**: The provider checks in `pipeline/smoke_test.py` are named `test_*`, so pytest automatically collected them — even though they make real paid API calls and need credentials.
- **Fix**: A `pytest.ini` file was added telling pytest to only look inside the `tests/` folder. All 8 unit tests now pass; live checks are run separately via `python -m pipeline.smoke_test`.
- **Status**: resolved

## F007 — Kaggle GPU unavailable

- Date: 2026-11-25
- Problem: Kaggle GPU unavailable.
- Alternative tested: Google Colab.
- GPU detected: NVIDIA Tesla T4.
- Available VRAM: 14.56 GB.
- CUDA availability: True.
- Resolution: Switch GPU execution to Google Colab.
- Remaining risk: Model memory requirements and session limits.
- Status: GPU access resolved; model execution pending.

### F008 — Gemini TTS unavailable; narration moved to a local model

- **Date**: 2026-11-25
- **Stage**: smoke test (Gemini TTS) / narration
- **Symptom**: Gemini text and Cloudflare images pass, but every TTS attempt fails — the voice model `gemini-2.5-flash-preview-tts` isn't reachable for this account (latest error: `RuntimeError` after the earlier HTTP 400/404s).
- **Root cause**: The preview TTS model name isn't available to this API key (renamed or gated).
- **Fix**: Added a free local fallback — Kokoro-82M runs on this Mac's CPU with no API key. `TTS_PROVIDER=kokoro` is now the default; `TTS_PROVIDER=gemini` keeps the old path. Install: `pip install "kokoro>=0.9.2" "misaki[en]>=0.9.4" espeakng-loader` (espeakng-loader bundles the espeak binary; no brew needed — this Mac has no Homebrew).
- **Status**: resolved via fallback; Gemini TTS remains open if preview access is granted later.

### F009 — No ffmpeg on this Mac

- **Date**: 2026-11-25
- **Stage**: assemble / environment setup
- **Symptom**: `ffmpeg`/`ffprobe` are not on PATH. (Earlier, `brew` itself was missing; Homebrew was installed on 2026-11-25 and `brew install espeak-ng` now works — binary at `/usr/local/bin/espeak-ng`.)
- **Root cause**: ffmpeg was never installed; `brew install ffmpeg` was never run.
- **Fix**: `brew install ffmpeg`. Until then the assemble/radio_cut stages can't run locally; narration (Kokoro) and all provider stages work without it.
- **Status**: open — blocked on `brew install ffmpeg`

#### F009 follow-up — 2026-11-25

- **Observed failure**: Multiple Homebrew FFmpeg installation attempts did not complete on Intel macOS 12.6.1. No FFmpeg Cellar or opt directory, no running brew process, and no ffmpeg/ffprobe command. Dependency logs exist; cache 333 MB and available disk 13 GiB.
- **Root cause**: Exact installation failure remains unknown; earlier entry is superseded by these observations.
- **Alternative**: FFmpeg via pip-installed imageio-ffmpeg==0.8.1, rather than Homebrew.
- **Verification**: Bundled FFmpeg 9.0.2-tessus returned exit code 0; a two-second H.264 black-screen MP4 was encoded and played successfully on the user's Mac.
- **Status**: Installation blocker resolved via fallback. Pipeline regression tests pending; standalone ffprobe remains unavailable.

### F010 — Regression tests after portable FFmpeg and cache changes

- Date: 2026-11-25
- Evidence: 32 passed, 2 failed in 10.07 seconds at e1b7334.
- Causes: old FFmpeg test mocked only system lookup; failed GPU job records were imported repeatedly after retry support was introduced.
- Fix: mock both executable sources and test bundled fallback; deduplicate result records separately from completed job IDs so failed jobs can be retried.
- Status: patch committed; local regression verification pending.

#### F010 verification — 2026-11-25

- Local commit 9804cee: `python -m pytest -q` returned 35 passed in 2.46s.
- Status: resolved for offline regression suite. Live GPU and full assembly verification remain pending.

### F011–F016 — ACE-Step blocked music generation; migration to MusicGen

- Date: 2026-11-26
- Stage: Colab music smoke test.
- F011: PyPI install of acestep returned no matching distribution.
- F012: attempted installation rejected Python 3.13.16 (requires >=3.11,<3.13); switched to Colab 2026.01 / Python 3.12.12.
- F013: dependency warnings involving fsspec/gcsfs and jedi.
- F014: installed legacy ace_step 0.2.0 loaded ACE-Step/ACE-Step-v1-3.5B, not requested 1.5. Diffusion completed but decoding failed with GET was unable to find an engine to execute this computation.
- F015: legacy constructor used dtype, while worker passed bf16 through kwargs; precision mismatch suspected, not proven as crash cause.
- F016: repeated runtime restarts even during debugging; no confirmed OOM or definitive crash cause. No usable audio verified.
- Decision: stop spending limited GPU sessions and deadline time on legacy integration; use facebook/musicgen-small through Transformers 4.57.6 and SciPy 1.16.3, in a clean Colab T4 runtime. Imports and inference passed without the previous installation/runtime blockers in this test.
- Measured: FP16, seed 42, guidance 3, 256 tokens, 9.863 s generation, 5.06 s audio, 32 kHz, 647738 bytes, peak allocated GPU memory 1.215 GiB (about 8.3% of 14.56 GiB capacity; not total runtime memory), zero API cost. No comparable successful ACE-Step peak-memory measurement exists. No crash in successful MusicGen test.
- Creative evaluation (user): audio 4/5, emotional alignment 3/5, prompt adherence 4/5, narration suitability 4/5; mean 3.75/5. No free-text observations supplied.
- Tradeoffs: MusicGen weights CC BY-NC 4.0; noncommercial use only under weight license. Assignment names ACE-Step 1.5; substitution disclosed, acceptance not confirmed. Longer scores require segmented generation and crossfades; continuity not yet tested.
- Status: short standalone generation blocker resolved via substitution; integrated worker, cache and full-length soundtrack verification pending. Legacy ACE-Step 1.5 itself was not successfully tested.

#### MusicGen integration verification — 2026-11-26

- User-reported local regression run after commit 3b17c91: `python -m pytest -q` — 38 passed in 15.88s, no failures or skips.
- Offline integration tests passed, including model migration, seed preservation and crossfade behavior.
- Integrated Colab inference, cache reuse and full-length soundtrack remain pending.

### Integrated MusicGen cache verification — 2026-11-26 EAT

User confirmed first integrated smoke run succeeded with cache_hit=false, and second run succeeded with cache_hit=true. Second result: UTC 2026-11-25T22:35:11.152295+00:00, job smoke-music-1795646111, model facebook/musicgen-small, prompt soft piano note sequence, duration requested 5 s, seed 42, music.wav, status success, error null, latency 0.027 s, gpu_minutes 0.0 (rounded), cost_usd 0.0, peak_gpu_memory_gib null (not measured on cache hit). Earlier standalone generation took 9.863 s; illustrative comparison is about 365x faster, not a controlled same-job speedup because first integrated latency was not supplied and prompts differ. Integrated short generation, playback and cache reuse verified by user; full-length generation remains pending.

### F017 — Wan checkpoint format incompatible with Diffusers

- Date: 2026-11-26
- Symptom: smoke failed with OSError; direct traceback showed HTTP 404 for vae/config.json in Wan-AI/Wan2.2-TI2V-5B.
- Environment: Python 3.13.16, torch 2.14.1+cu130, diffusers 0.42.1, transformers 5.22.1, CUDA available, available RAM 10.76 GiB, free disk 112.48 GiB.
- Cause: original checkpoint repository lacks the requested Diffusers component configuration.
- Fix: use Wan-AI/Wan2.2-TI2V-5B-Diffusers; user verified downloads of vae/config.json and model_index.json. Preserve detailed per-shot exception messages.
- Status: missing configuration blocker resolved; weight loading, pipeline compatibility, memory feasibility and inference pending.

### F018–F021 — Wan compatibility and loading experiments

- F018 (open): WanPipeline call signature has no image argument; WanImageToVideoPipeline exists but checkpoint compatibility remains untested.
- F019 (partially resolved): NF4 transformer and text encoder, FP16 compute, FP32 VAE, CUDA and VAE tiling enabled successful 480x480 text-to-video on T4. Peak allocated 13.92 GiB of previously measured 14.56 GiB. Higher resolution and longer clips unverified.
- F020 (resolved): bitsandbytes 0.50.2 installed and standalone NF4 passed, but Diffusers availability false until session restart; after restart availability true and minimum version check passed.
- F021 (workaround verified): offline snapshot completeness check reported nine missing files including documentation/assets. Normal online from_pretrained loading succeeded; no claim that full snapshot is complete.
- User-reported smoke success: 17 frames, 24 fps, six steps, seed 42, loading 148.4 seconds. Video saved to Drive experiment folder. Generation latency not captured in supplied metrics. Worker integration and image conditioning pending.

### Wan image conditioning follow-up

User reports successful standalone image-to-video generation using WanImageToVideoPipeline.from_pipe(pipe, expand_timesteps=True), sharing the quantized components, 480x480, 17 frames, six steps, guidance 3, seed 42. F018 standalone compatibility resolved. Integrated worker and cache remain unverified; no I2V latency or memory measurement supplied. Final/ultra 20 steps are proposed production settings, not benchmarked.

### F022 — Gemini shot ID formatting

User-reported schema ValidationError: generated shot ID contained whitespace. Normalize string IDs to filename-safe characters before validation; retain schema and duplicate-ID checks. Failed response was not saved by the existing pipeline; regeneration required. Fix committed, live verification pending.


## GPU availability and fallback quality
Kaggle GPU remained unavailable and the original Colab account exhausted its quota. The user reported signing into another Google account; authorized runtime availability has not been verified. Do not treat account switching as a quota workaround. All ten FFmpeg fallback shots rendered in both aspect ratios, but the user rated the initial rough cut 2.8/5 and reported the revised effects looked worse and still resembled a slideshow. Mitigation selected: hybrid motion with five prioritized Wan shots, four stills and one procedural graphic. Production verification pending.


## Hybrid regression test follow-up
User reported 34 passed, 4 failed in 12.57s after pulling 9285fe5. Two assembly assertions expected obsolete zoompan or the first subprocess call rather than the new duration probe followed by interpolation. Two Kokoro tests inherited the approved am_michael environment voice instead of isolating af_heart. Updated assertions and test environment; rerun pending. No production narration changes. Mocked tests do not verify actual FFmpeg filter execution.

Verification: user reported 38 passed in 3.16s at 745ce18; both production jobs packaged successfully. Offline regression resolved; actual GPU inference and FFmpeg production filters remain unverified.
