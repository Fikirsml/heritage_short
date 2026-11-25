# Creative inputs

- `narration.txt`: paste approved spoken narration only (no title or directions). Required for story generation.
- `story_brief.md`: audience, story context and visual direction.
- `prompts/storyboard.md`: editable instructions for Gemini; generated shot and music prompts live in storyboard.json.

These files are tracked in a public repository. Do not include secrets or unapproved personal details. Regenerate with `python -m pipeline.run --stage story --force` after editing. Generated storyboard remains at repository root. Existing downstream assets may need regeneration when prompts change.
