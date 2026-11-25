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
