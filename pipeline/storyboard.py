"""Story stage: generate storyboard.json via Gemini, validate it, save it.

The generated file is meant to be hand-edited afterwards — every
downstream stage re-validates it against schema/storyboard.schema.json.
"""

import json
import os
import re
import time

from google import genai
from google.genai import types

from pipeline.utils import (
    SCHEMA_FILE,
    STORYBOARD_FILE,
    get_env,
    load_json,
    log_run,
    save_json,
)

DEFAULT_TEXT_MODEL = "gemini-2.5-flash"

PROMPT_TEMPLATE = """Write a storyboard for a {duration}-second AI-generated short film.

Story: the author's real college journey — arriving hopeful, hitting academic
and personal challenges, and getting through them with faith in God.
Audience: family and friends. Narration is first-person, plain spoken English,
about 150-220 words so it reads in roughly {duration} seconds. Warm, honest,
hopeful tone — no melodrama.

Reply with ONLY a JSON object in exactly this shape:
{{
  "title": "short film title",
  "target_duration_seconds": {duration},
  "narration": {{"script": "full first-person narration text"}},
  "music": {{"prompt": "instrumental music description matching the mood", "duration_seconds": {duration}}},
  "shots": [
    {{"id": "shot_01", "prompt": "visual description for image/video generation", "duration_seconds": 12}},
    ...
  ]
}}

Rules:
- exactly {shot_count} shots, ids shot_01..shot_{shot_count:02d}
- shot durations must sum to about {duration} seconds
- each shot prompt is a single concrete visual scene (no text overlays, no real people's faces)
- progression: hopeful arrival -> struggle -> turning point with faith -> resolution/gratitude
"""


def _LAarat eload_json(SCHEMA_FILE)

        # Fill defaults the generator may omit, then validate the result.
        storyboard.setdefault(
            "target_duration_seconds", duration_seconds
        )
        storyboard.setdefault("music", {})
        storyboard["music"].setdefault("model", "ace-step-1.5")
        storyboard["narration"].setdefault("voice", "Kore")
        default_video = {
            "model": "Wan-AI/Wan2.2-TI2V-5B",
            "width": 480,
            "height": 480,
            "frames": 49,
            "steps": 30,
            "guidance": 5.0,
        }
        for index, shot in enumerate(storyboard["shots"]):
            shot.setdefault("id", f"shot_{index + 1:02d}")
            video = {**default_video, **shot.get("video", {})}
            video.setdefault("seed", 1000 + index)
            shot["video"] = video

        from jsonschema import validate
        validate(instance=storyboard, schema=schema)
        save_json(storyboard, STORYBOARD_FILE)
    except Exception as error:
        log_run(
            stage="story",
            model=model,
            parameters={"duration": duration_seconds, "shots": shot_count,
                        "brief": brief_source or "default"},
            latency=time.perf_counter() - start,
            status="failed",
            error=type(error).__name__,
        )
        raise

    log_run(
        stage="story",
        model=model,
        parameters={"duration": duration_seconds, "shots": shot_count,
                    "brief": brief_source or "default"},
        latency=time.perf_counter() - start,
    )
    return storyboard