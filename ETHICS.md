# Ethics & Compliance

## Consent

- The story is the author's own personal experience.
- TODO: before publishing, record consent for any other identifiable people
  mentioned in the narration or shown in imagery.
- No third-party voices or likenesses may be generated without documented consent.

## AI disclosure

- The final piece must disclose that narration/visuals are AI-generated.
- TODO: decide disclosure format (description text vs. on-screen note).

## Licensing

- Music and SFX must be licensed or provider-generated; verify terms permit the
  intended sharing audience. TODO: select sources and record them here.
- Generated images/clips: confirm provider terms allow publication. TODO.

## Privacy

- Avoid publishing sensitive personal details (addresses, full names of others,
  exact locations). TODO: review the final script before release.

## Credentials & data handling

- API keys live only in `.env` (gitignored). Never commit credentials.
- `outputs/kept/` is tracked in git — do not place private or licensed
  material there unless it is intended for assessment/review.

## MusicGen migration (2026-11-26)

Default music worker: `facebook/musicgen-small`, FP16 on Colab T4. See [FAILURES.md](FAILURES.md) F011–F016 for measured results and provider decision. The new notebook pins Transformers 4.57.6 and SciPy 1.16.3; run smoke first, then explicitly select the packaged job ID. Worker generates up to 25-second segments, blends with one-second crossfades, trims to target length and caches by generation settings. Model weights are CC BY-NC 4.0; assignment substitution acceptance and full-length integration are pending. Measured standalone generation: 9.863 s for 5.06 s audio, 1.215 GiB peak allocated GPU memory, $0 API cost; not a full-track benchmark.
