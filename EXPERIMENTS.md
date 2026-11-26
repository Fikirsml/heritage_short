# Experiments Log

Append-only record of provider, model, and prompt experiments. Newest entries at the bottom.

## Entry format

- **ID**: E### 
- **Date**: YYYY-MM-DD
- **Goal / hypothesis**: what you expected to learn
- **Config**: provider, model, prompt reference, key parameters
- **Result**: what actually happened (link artifacts in `outputs/` if kept)
- **Decision**: what changed because of it

## Entries

### E001 — Portable FFmpeg installation

- **Date**: 2026-11-25
- **Goal / hypothesis**: Avoid local dependency compilation while retaining FFmpeg assembly on Intel macOS Monterey.
- **Config**: Homebrew versus imageio-ffmpeg==0.8.1 in Python 3.12.7.
- **Result**: Homebrew attempts left no installed FFmpeg. Bundled FFmpeg 9.0.2-tessus launched successfully and encoded a playable two-second 640x360 H.264 test video. No measured timing comparison was recorded.
- **Decision**: Prefer system FFmpeg when present; otherwise use the bundled executable. No standalone ffprobe is supplied by this workaround.


## MusicGen migration (2026-11-26)

Default music worker: `facebook/musicgen-small`, FP16 on Colab T4. See [FAILURES.md](FAILURES.md) F011–F016 for measured results and provider decision. The new notebook pins Transformers 4.57.6 and SciPy 1.16.3; run smoke first, then explicitly select the packaged job ID. Worker generates up to 25-second segments, blends with one-second crossfades, trims to target length and caches by generation settings. Model weights are CC BY-NC 4.0; assignment substitution acceptance and full-length integration are pending. Measured standalone generation: 9.863 s for 5.06 s audio, 1.215 GiB peak allocated GPU memory, $0 API cost; not a full-track benchmark.

### Integrated MusicGen cache verification — 2026-11-26 EAT

User confirmed first integrated smoke run succeeded with cache_hit=false, and second run succeeded with cache_hit=true. Second result: UTC 2026-11-25T22:35:11.152295+00:00, job smoke-music-1795646111, model facebook/musicgen-small, prompt soft piano note sequence, duration requested 5 s, seed 42, music.wav, status success, error null, latency 0.027 s, gpu_minutes 0.0 (rounded), cost_usd 0.0, peak_gpu_memory_gib null (not measured on cache hit). Earlier standalone generation took 9.863 s; illustrative comparison is about 365x faster, not a controlled same-job speedup because first integrated latency was not supplied and prompts differ. Integrated short generation, playback and cache reuse verified by user; full-length generation remains pending.

### Wan 2.2 quantized smoke experiment (2026-11-26)

User-reported successful standalone text-to-video on Tesla T4 using Wan-AI/Wan2.2-TI2V-5B-Diffusers, NF4 transformer/text encoder, FP16 compute, FP32 VAE, 480x480, 17 frames, six steps, 24 fps, seed 42. Loading 148.4 s; peak allocated GPU memory 13.92 GiB. Nominal headroom 0.64 GiB against previously measured 14.56 GiB capacity; not a measurement of free VRAM. Generation latency unavailable. Recommend 480 generation with export upscaling, pending longer-clip and image-conditioning verification. Evidence saved by user to Drive experiments/wan_smoke. No production worker validation yet.

### Wan image conditioning follow-up

User reports successful standalone image-to-video generation using WanImageToVideoPipeline.from_pipe(pipe, expand_timesteps=True), sharing the quantized components, 480x480, 17 frames, six steps, guidance 3, seed 42. F018 standalone compatibility resolved. Integrated worker and cache remain unverified; no I2V latency or memory measurement supplied. Final/ultra 20 steps are proposed production settings, not benchmarked.

### Technical foundation verification (2026-11-26)

User confirms Windsurf IDE with SWE free-agent and local `python -m pytest -q`: 38 passed in 12.64s following Wan integration commit 00eb130. Offline regression suite passed; integrated GPU production and video cache verification remain pending. Coding agent setup is user-reported.


## Planned hybrid motion experiment
Compare the previously reviewed all-FFmpeg rough cut (2.8/5 user rating; later revision reported worse) with a hybrid cut using five Wan shots, four intentional stills and one procedural graphic. At identical per-shot settings this reduces planned video inference calls from ten to five; GPU minutes, memory, quality and final audience feedback remain unmeasured. Record actual settings, successful clips, retries and latency after production.


## Hybrid implementation
Final jobs select five motion shots. Final profile 480x480, 33 frames, 12 steps, retry at 17 frames on CUDA OOM. Existing persistent cache retained. Assembly adds intentional stills, procedural one-degree rays, interpolated motion and sidechain ducking with loudnorm. Captions use approximate word-weighted timing, not speech alignment; review required. All new production changes remain untested on the user's Mac and GPU. No measured savings claimed.


## Full-length MusicGen production — 2026-11-26
User-reported worker result: music-0292a71a10559697, facebook/musicgen-small, requested duration 89.33 s, seed 42, success, music.wav, cache miss, latency 153.971 s, reported GPU minutes 2.566 (worker wall time / 60), peak allocated GPU memory 1.598 GiB, reported API cost USD 0.00. Public checkpoint download 2.36 GB. Missing HF_TOKEN and deprecated torch_dtype warnings were nonfatal. Audio duration and creative quality have not been independently verified. Runtime allocation and total infrastructure cost were not measured.


## Wan production partial success — 2026-11-26
User-reported job video-8c1d0793623cfbe4: 2/5 clips generated (shot_01_graduation, shot_08_dawn_horizon); shots 02, 06, 09 failed with CUDA OOM requesting 128 MiB. T4 capacity 14.56 GiB, process usage 14.46–14.49 GiB, free 71.81–103.81 MiB, reserved unallocated 713.75–737.75 MiB. Worker reported success despite partial completion. Wall time 1118.845 s, reported GPU minutes 18.647, cost unknown. Allocator fragmentation may contribute but is not established as root cause. Preserve successful clips; prioritize final assembly with fallback for missing clips. Clip playback and actual frame counts not independently verified.
