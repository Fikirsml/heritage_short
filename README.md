# Heritage Short

A reproducible pipeline that generates a 60–90 second AI-assisted short film about a
personal college journey and the role of faith in God through challenges.

- **Challenge**: 10 Academy — Week 0, AI Content Generation
- **Narration language**: English
- **Audience**: family and friends
- **Status**: Phase 2 — semi-automated pipeline implemented. Local stages work via APIs; GPU stages (music, video) run manually on Colab (see COLAB.md). Live end-to-end run pending.

## Repository layout

```
pipeline/          # stage modules + Colab-side GPU workers
  run.py           # orchestrator: python -m pipeline.run --stage <name>
  storyboard.py    # Gemini: storyboard.json generation (reads inputs/story_brief.md)
  tts.py           # narration provider dispatch (TTS_PROVIDER env)
  kokoro_client.py # local Kokoro-82M TTS (offline, free)
  gemini_client.py # Gemini TTS narration (optional provider)
  cloudflare_client.py # Workers AI keyframe images
  exchange.py      # Drive job packaging + result collection
  gpu_music.py     # ACE-Step 1.5 worker (runs on Colab)
  gpu_video.py     # Wan 2.2 TI2V-5B worker (runs on Colab)
  assemble.py      # ffmpeg concat/mix + keyframe fallback
  smoke_test.py    # live provider connectivity checks
schema/            # storyboard.json JSON Schema
storyboard.json    # single source of truth for all stages
inputs/story_brief.md     # YOUR story details — input to the story stage (fill in TODOs)
notebooks/         # Colab notebooks (GPU handoff — see COLAB.md)
tests/             # pytest unit tests (no live calls)
outputs/
  keyframes/ shots/ music/ narration/ radio_cut/ final/  # generated (gitignored)
  kept/            # hand-picked artifacts retained for assessment (tracked)
exchange/          # local fallback for the Drive exchange dir (gitignored)
runs.jsonl         # append-only log, one JSON object per model call
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real keys — .env is gitignored
```

## Running

Requires keys in `.env`. Assembly prefers system FFmpeg if available, otherwise
uses the executable supplied by `imageio-ffmpeg==0.8.1` (installed from
requirements.txt). Homebrew is optional. See FAILURES.md F009 and EXPERIMENTS.md E001.

Verify the resolved executable:

```bash
python -c 'from pipeline.assemble import _require_ffmpeg; print(_require_ffmpeg())'
python -c 'from pipeline.assemble import _run; print(_run(["ffmpeg", "-version"]).stdout.splitlines()[0])'
```

The bundled executable does not provide a standalone ffprobe command.

Narration defaults to **local Kokoro-82M** (`TTS_PROVIDER=kokoro` — free,
offline, CPU; first run downloads ~330 MB of weights). Deps are pip-only:
`pip install "kokoro>=0.9.2" "misaki[en]>=0.9.4" espeakng-loader`
(espeakng-loader bundles the espeak-ng binary; a system `brew install
espeak-ng` also works — see FAILURES.md F009 for ffmpeg status).
Set `TTS_PROVIDER=gemini` to use Gemini TTS instead.

Input order: fill in `inputs/narration.txt` (approved spoken script), `inputs/story_brief.md` and `inputs/prompts/storyboard.md` →
`--stage story --force` generates a real `storyboard.json` → hand-edit it if
needed → the remaining stages consume it. All three creative inputs must be nonempty. Narration is preserved verbatim (outer whitespace trimmed). See inputs/README.md.

```bash
python -m pipeline.run --stage all       # story → keyframes → narration → package Colab jobs
python -m pipeline.run --resume    # after Colab + Drive sync: collect → assemble
python -m pipeline.run --stage story --force   # regenerate storyboard.json
```

GPU stages are a **manual handoff** — upload the exchange folder to Drive and
run the two notebooks in Colab (full procedure: **COLAB.md**). The final film
lands in `outputs/final/heritage_short.mp4`; audio-only preview in
`outputs/radio_cut/`.

```bash
python -m pytest -v                # unit tests (offline)
python -m pipeline.smoke_test      # live provider checks (may incur charges)
python -m pipeline.smoke_test --provider kokoro   # local TTS check (free)
```

**Reproducibility limitation**: the two Colab notebook runs are manual —
everything else is one command. Given the same `storyboard.json` seeds, output
is deterministic up to GPU nondeterminism. Failed video shots fall back to
ffmpeg zoompan clips so the film always assembles.

## Documentation

- **DESIGN.md** — creative brief and story design
- **ARCHITECTURE.md** — module layout and data flow
- **EXPERIMENTS.md** — provider/model experiment log
- **FAILURES.md** — things that broke and how they were fixed
- **COSTS.md** — per-run and cumulative spend
- **ETHICS.md** — consent, AI disclosure, licensing, privacy

- **DESIGN.md** — creative brief and story design
- **ARCHITECTURE.md** — module layout and data flow
- **EXPERIMENTS.md** — provider/model experiment log
- **FAILURES.md** — things that broke and how they were fixed
- **COSTS.md** — per-run and cumulative spend
- **ETHICS.md** — consent, AI disclosure, licensing, privacy
- **COSTS.md** — per-run and cumulative spend
- **ETHICS.md** — consent, AI disclosure, licensing, privacy

## Quality profiles and video cache

Edit inputs/config/quality_profiles.json to tune generation. Default draft uses 480 square, 15 steps, 17 frames; final uses 720 square, 30 steps, 49 frames; ultra reuses final generation settings and exports at 1080 (upscaled). Native 720 generation on T4 is not yet verified.

Run `python -m pipeline.run --stage package --quality draft`, execute the matching video job in Colab, then `python -m pipeline.run --resume --quality draft`. Repeat with final or ultra when approved. Select the job path printed by package; do not run an older job by mistake.

Per-shot SHA-256 cache persists at exchange/cache/video, keyed by model, prompt, negative prompt, video settings, fps and keyframe bytes. Preserve this folder across Colab sessions. Cache hits skip model loading when all shots are cached. Job IDs include input file hashes; video results are isolated by profile and job ID. Exports are outputs/final/<quality>/horizontal.mp4 and vertical.mp4. Both generated footage and still-image fallback are center-cropped to fill each frame. Missing video clips use keyframe fallback. Music and narration remain shared. Existing media may need regeneration after creative edits; GPU inference and full regression testing remain pending.

### Required assignment exports

Both aspect ratios are mandatory (PDF: What You Will Build, Phase 3, Assignment 2). Draft exports 864x486 and 486x864 (near 480p, exact ratios); final 1280x720 and 720x1280; ultra 1920x1080 and 1080x1920. Submit vertical.mp4 as main and horizontal.mp4 as attachment. Subtitle and end-card implementation remain pending.

## MusicGen migration (2026-11-26)

Default music worker: `facebook/musicgen-small`, FP16 on Colab T4. See [FAILURES.md](FAILURES.md) F011–F016 for measured results and provider decision. The new notebook pins Transformers 4.57.6 and SciPy 1.16.3; run smoke first, then explicitly select the packaged job ID. Worker generates up to 25-second segments, blends with one-second crossfades, trims to target length and caches by generation settings. Model weights are CC BY-NC 4.0; assignment substitution acceptance and full-length integration are pending. Measured standalone generation: 9.863 s for 5.06 s audio, 1.215 GiB peak allocated GPU memory, $0 API cost; not a full-track benchmark.
