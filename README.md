# Heritage Short

A reproducible pipeline that generates a 60–90 second AI-assisted short film about a
personal college journey and the role of faith in God through challenges.

- **Challenge**: 10 Academy — Week 0, AI Content Generation
- **Narration language**: English
- **Audience**: family and friends
- **Status**: Phase 1 — foundation and smoke tests implemented; live verification pending.

## Repository layout

```
pipeline/          # pipeline stage modules (planned)
schema/            # data contracts: Story, Shot, AssetRef, RunRecord (planned)
tests/             # pytest unit tests
outputs/
  narration/       # generated narration audio + scripts (gitignored)
  radio_cut/       # generated audio-first cut (gitignored)
  kept/            # hand-picked artifacts retained for assessment (tracked)
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

Configure model names in .env and Kaggle credentials locally.

```bash
python -m pipeline.smoke_test
python -m pipeline.smoke_test --provider gemini-tts
python -m pytest -v
ffmpeg -version
ffprobe -version
```

Smoke tests make real requests and may incur charges. Unknown costs are logged as null; reconcile actual charges in COSTS.md. Successful TTS writes outputs/narration/test.wav. Listen to it to verify quality. Kaggle connectivity does not verify GPU availability. Model defaults may need updating for your account. Keep non-sensitive assessment artifacts in outputs/kept/. Live tests have not been verified.

## Documentation

- **DESIGN.md** — creative brief and story design
- **ARCHITECTURE.md** — module layout and data flow
- **EXPERIMENTS.md** — provider/model experiment log
- **FAILURES.md** — things that broke and how they were fixed
- **COSTS.md** — per-run and cumulative spend
- **ETHICS.md** — consent, AI disclosure, licensing, privacy
