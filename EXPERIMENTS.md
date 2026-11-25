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

