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
