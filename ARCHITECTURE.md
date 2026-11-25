# Architecture

> Status: Phase 1 scaffolding. The modules below are planned, not implemented.

## Overview

Single-machine, linear pipeline. Each stage reads inputs from disk, calls one
provider, writes artifacts under `outputs/`, and appends one record to
`runs.jsonl`. No framework — plain Python modules only.

## Data flow

```
story text -> shot list -> generated assets (stills/clips)
           -> narration audio -> radio cut -> final cut
```

## Modules (planned)

- **`schema/`** — dataclasses + JSON schemas for `Story`, `Shot`, `AssetRef`, `RunRecord`.
- **`pipeline/`** — one module per stage. Tentative split: `story.py`, `shots.py`,
  `assets.py`, `narration.py`, `assemble.py`, plus `run.py` (orchestrator and
  `runs.jsonl` writer). Exact split TBD.
- **`tests/`** — pytest unit tests for schemas and stage I/O; provider calls mocked.

## Providers (planned)

- **Gemini** — story/script text generation; possibly images.
- **Cloudflare Workers AI** — TTS narration and/or image models; R2 optional storage.
- Final provider selection TBD — record comparisons in EXPERIMENTS.md.

## Run log

`runs.jsonl` — append-only, one JSON object per run. Planned fields: run id,
timestamp, stage, config reference, artifact paths, status, cost estimate.
Schema TBD in Phase 2.

## Outputs

- `outputs/narration/` — narration audio + scripts (generated, gitignored)
- `outputs/radio_cut/` — audio-first cut (generated, gitignored)
- `outputs/kept/` — hand-picked artifacts retained for assessment (tracked in git)
