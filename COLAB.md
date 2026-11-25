# Colab GPU Handoff

GPU-heavy stages (ACE-Step music, Wan 2.2 video) run manually in Google Colab
on a free Tesla T4. Everything else runs locally. This file is the exact
handoff procedure.

## Prerequisites

- Google account with Colab access (free tier: T4 GPU, ~14.5 GB VRAM).
- One of:
  - **Google Drive for desktop** installed — set `DRIVE_EXCHANGE_DIR` in `.env`
    to a folder inside your synced Drive, e.g.
    `DRIVE_EXCHANGE_DIR=/Users/<you>/Library/CloudStorage/GoogleDrive-<acct>/My Drive/heritage-exchange`
    (the pipeline creates it; Drive syncs automatically), or
  - **Manual upload** — the pipeline writes `./exchange/` locally and you
    upload it to `My Drive/heritage-exchange` yourself.
- Upload both notebooks (`notebooks/*.ipynb`) to Colab once: open
  [colab.research.google.com](https://colab.research.google.com) > File >
  Upload notebook. (They read everything else from the exchange folder.)

## The exchange folder

```
heritage-exchange/            # DRIVE_EXCHANGE_DIR points here
  jobs/music-<hash>/job.json  # music params from storyboard.json
  jobs/video-<hash>/job.json  # per-shot video params
  jobs/video-<hash>/inputs/   # Cloudflare keyframes for I2V conditioning
  pipeline_gpu/               # gpu_music.py, gpu_video.py (auto-synced)
  results/<job_id>/           # generated wav/mp4 files
  results/results.jsonl       # Colab run log → merged into runs.jsonl
```

## Procedure

1. **Local** — generate storyboard, keyframes, narration, package jobs:

   ```bash
   python -m pipeline.run --all
   ```

   This stops after packaging and prints the handoff checklist.

2. **Drive** — if `DRIVE_EXCHANGE_DIR` is unset, upload `./exchange/` to
   `My Drive/heritage-exchange` now. If set, wait for Drive to sync.

3. **Colab — music**: open `notebooks/music_ace_step.ipynb`, set runtime to
   **T4 GPU**, Runtime > Run all. Cell 5 is a ~5 s smoke test — if it fails,
   fix before continuing (record it in FAILURES.md). Cell 6 runs the real job.

4. **Colab — video**: same for `notebooks/video_wan22.ipynb`. Expect the first
   run to take a while (model download ~10 GB, then ~minutes per shot).

5. **Drive** — wait for `results/` to sync down (or download manually into
   `./exchange/results/`).

6. **Local** — collect + assemble:

   ```bash
   python -m pipeline.run --resume
   ```

   Copies `outputs/shots/*.mp4` and `outputs/music/music.wav`, merges the
   Colab log into `runs.jsonl`, builds `outputs/radio_cut/radio_cut.m4a` and
   `outputs/final/heritage_short.mp4`.

## Failure behaviour

- A shot that fails on GPU is reported in `results.jsonl` and covered at
  assemble time by an ffmpeg zoompan clip from its keyframe
  (`status: fallback` in `runs.jsonl`). The film still completes.
- If every video shot fails, the film is assembled entirely from keyframe
  fallback clips — degraded but reproducible.

## Troubleshooting

- **CUDA out of memory (video)**: lower `frames`/`steps`/resolution in the
  shot's `video` block of `storyboard.json`, repackage, rerun the job cell.
- **OOM in step 3 deps or model load**: Runtime > Restart, run cells again.
- **`acestep` import error**: uncomment the GitHub install line in cell 3.
- **Session timeout**: rerun cell 6 — `results/` persists on Drive, and
  `collect_results` skips already-imported jobs.

## Reproducibility limitations

- The two notebook runs are **manual** — Colab cannot be driven headlessly
  on the free tier without extra infrastructure. Everything before and after
  is one command.
- Colab's free T4 quota/session length varies; long jobs may need reruns.
- `acestep`/diffusers APIs may drift between releases — the notebooks pin
  nothing; record exact versions in EXPERIMENTS.md after a successful run.
- Given the same `storyboard.json` (seeds included), outputs are
  deterministic up to GPU nondeterminism.
