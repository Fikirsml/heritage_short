# Creative inputs

- `narration.txt`: paste approved spoken narration only (no title or directions). Required for story generation.
- `story_brief.md`: audience, story context and visual direction.
- `prompts/storyboard.md`: editable instructions for Gemini; generated shot and music prompts live in storyboard.json.

These files are tracked in a public repository. Do not include secrets or unapproved personal details. Regenerate with `python -m pipeline.run --stage story --force` after editing. Generated storyboard remains at repository root. Existing downstream assets may need regeneration when prompts change.

## Quality profiles and video cache

Edit inputs/config/quality_profiles.json to tune generation. Default draft uses 480 square, 15 steps, 17 frames; final uses 720 square, 30 steps, 49 frames; ultra reuses final generation settings and exports at 1080 (upscaled). Native 720 generation on T4 is not yet verified.

Run `python -m pipeline.run --stage package --quality draft`, execute the matching video job in Colab, then `python -m pipeline.run --resume --quality draft`. Repeat with final or ultra when approved. Select the job path printed by package; do not run an older job by mistake.

Per-shot SHA-256 cache persists at exchange/cache/video, keyed by model, prompt, negative prompt, video settings, fps and keyframe bytes. Preserve this folder across Colab sessions. Cache hits skip model loading when all shots are cached. Job IDs include input file hashes; video results are isolated by profile and job ID. Exports are outputs/final/<quality>/horizontal.mp4 and vertical.mp4. Both generated footage and still-image fallback are center-cropped to fill each frame. Missing video clips use keyframe fallback. Music and narration remain shared. Existing media may need regeneration after creative edits; GPU inference and full regression testing remain pending.
