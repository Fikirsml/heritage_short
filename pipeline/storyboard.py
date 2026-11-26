"""Generate a validated storyboard from approved creative inputs."""
import json
import os
import re
import time

from google import genai
from google.genai import types
from jsonschema import validate
from pipeline.utils import (
    INPUT_DIR, SCHEMA_FILE, STORYBOARD_FILE, get_env, load_json, log_run, save_json
)

DEFAULT_TEXT_MODEL = "gemini-3.5-flash"

def load_creative_inputs():
    paths = [INPUT_DIR / "narration.txt", INPUT_DIR / "story_brief.md",
             INPUT_DIR / "prompts" / "storyboard.md"]
    values = [path.read_text(encoding="utf-8").strip() for path in paths]
    if not all(values):
        raise ValueError("Fill in narration.txt, story_brief.md and prompts/storyboard.md in inputs/")
    return tuple(values)

def generate_storyboard(duration_seconds=75, shot_count=10):
    narration, brief, instructions = load_creative_inputs()
    schema = load_json(SCHEMA_FILE)
    model = os.getenv("GEMINI_MODEL", DEFAULT_TEXT_MODEL)
    prompt = (
        f"{instructions}\nTarget duration: {duration_seconds} seconds. "
        f"Exactly {shot_count} shots. Shot durations must sum to target.\n"
        "Separate still prompt and motion_prompt. Keep faces hidden and clothing consistent. Avoid readable generated text.\n"
        f"Brief:\n{brief}\nApproved narration:\n{narration}\n"
        f"Return only JSON matching this schema:\n{json.dumps(schema)}"
    )
    start = time.perf_counter()
    params = {"duration": duration_seconds, "shots": shot_count, "brief": "inputs/story_brief.md"}
    try:
        client = genai.Client(api_key=get_env("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        storyboard = json.loads(response.text)
        storyboard["target_duration_seconds"] = duration_seconds
        storyboard.setdefault("narration", {})["script"] = narration
        storyboard["narration"].setdefault("voice", "af_heart")
        storyboard["music"].setdefault("model", "facebook/musicgen-small")
        storyboard["music"]["duration_seconds"] = duration_seconds
        for index, shot in enumerate(storyboard["shots"]):
            raw_id = shot.get("id", f"shot_{index+1:02d}")
            if isinstance(raw_id, str):
                shot["id"] = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_id).strip("_") or f"shot_{index+1:02d}"
            video = {"model": "Wan-AI/Wan2.2-TI2V-5B-Diffusers", "width": 480,
                     "height": 480, "frames": 17, "steps": 6, "guidance": 3.0,
                     **shot.get("video", {})}
            video.setdefault("seed", 1000 + index)
            shot["video"] = video
        validate(instance=storyboard, schema=schema)
        shots = storyboard["shots"]
        if len(shots) != shot_count or len({s["id"] for s in shots}) != shot_count:
            raise ValueError("Unexpected shot count or duplicate shot IDs")
        if abs(sum(s["duration_seconds"] for s in shots) - duration_seconds) > 0.5:
            raise ValueError("Shot durations do not match target duration")
        save_json(storyboard, STORYBOARD_FILE)
    except Exception as error:
        log_run(stage="story", model=model, parameters=params,
                latency=time.perf_counter()-start, status="failed", error=type(error).__name__)
        raise
    log_run(stage="story", model=model, parameters=params, latency=time.perf_counter()-start)
    return storyboard
