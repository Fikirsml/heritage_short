"""Colab-side MusicGen generation; legacy ACE-Step retained for experiments.

This module is copied into the Drive exchange folder (exchange/pipeline_gpu/)
and imported by notebooks/music_ace_step.ipynb. Heavy dependencies (torch,
acestep) are imported lazily inside functions so the module stays importable
on the local Mac for testing.

NOTE: the ACE-Step API differs between releases. If the smoke test in the
notebook fails with a TypeError, adjust the kwargs in _init_pipeline() /
_generate_impl() for the installed version and record it in FAILURES.md.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


# -------------------------------
# Result logging (mirrors log_run)
# -------------------------------

def _write_result(results_root, entry):
    results_root = Path(results_root)
    results_root.mkdir(parents=True, exist_ok=True)
    with open(results_root / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _base_entry(job, model, parameters):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job.get("job_id"),
        "stage": job.get("stage", "music"),
        "model": model,
        "parameters": parameters,
        "files": [],
    }


# -------------------------------
# ACE-Step pipeline
# -------------------------------

def _init_pipeline():
    """Initialize ACE-Step on a T4: fp16 weights + CPU offload."""
    try:
        from acestep.pipeline_ace_step import ACEStepPipeline
    except ImportError:
        # Some releases expose it at package root.
        from acestep import ACEStepPipeline

    kwargs = {
        "checkpoint_dir": os.environ.get(
            "ACESTEP_CHECKPOINT_DIR", "/content/acestep-checkpoints"
        ),
        # T4 (Turing) has no bf16 units — fp16 is the right precision.
        "bf16": False,
        "torch_compile": False,
        # Keep VRAM pressure low on the 14.5 GB card.
        "cpu_offload": True,
    }
    try:
        return ACEStepPipeline(**kwargs)
    except TypeError:
        # Older releases take checkpoint_dir positionally.
        return ACEStepPipeline(kwargs["checkpoint_dir"])


def _generate_legacy(job, out_dir):
    """Generate the music track. Returns list of produced filenames."""
    import torch

    music = job.get("music", {})
    prompt = music.get("prompt", "instrumental")
    duration = float(music.get("duration_seconds", 60))
    seed = music.get("seed")

    if seed is not None:
        torch.manual_seed(int(seed))

    pipe = _init_pipeline()
    out_path = Path(out_dir) / "music.wav"

    pipe(
        prompt=prompt,
        lyrics=music.get("lyrics", ""),
        audio_duration=duration,
        infer_step=int(music.get("steps", 60)),
        guidance_scale=float(music.get("guidance", 15.0)),
        save_path=str(out_path),
        format="wav",
    )

    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RuntimeError("ACE-Step produced no output file")
    return [out_path.name]



MODEL_ID = "facebook/musicgen-small"
_CACHE_VERSION = 1

def blend_segments(segments, overlap):
    import numpy as np
    result = segments[0]
    for segment in segments[1:]:
        n = min(overlap, len(result), len(segment))
        if n:
            fade = np.linspace(0, 1, n, dtype=np.float32)
            result = np.concatenate((result[:-n], result[-n:] * (1-fade) + segment[:n] * fade, segment[n:]))
        else:
            result = np.concatenate((result, segment))
    return result

def _generate_impl(job, out_dir):
    import hashlib
    import shutil
    import math
    import numpy as np
    import torch
    from scipy.io import wavfile
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    music = job["music"]
    duration = float(music["duration_seconds"])
    if not math.isfinite(duration) or not 0 < duration <= 180:
        raise ValueError("Music duration must be between 0 and 180 seconds")
    settings = dict(model=MODEL_ID, prompt=music["prompt"], duration=duration,
                    seed=int(music.get("seed", 42)), segment_seconds=25,
                    overlap_seconds=1, guidance=3.0, precision="float16",
                    version=_CACHE_VERSION)
    key = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    out = Path(out_dir) / "music.wav"
    cache = Path(out_dir).parent.parent / "cache" / "music" / (key + ".wav")
    if cache.is_file() and cache.stat().st_size > 44:
        shutil.copy2(cache, out)
        job["_cache_hit"] = True
        return [out.name]
    if not torch.cuda.is_available():
        raise RuntimeError("MusicGen worker requires CUDA")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = MusicgenForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch.float16).to("cuda").eval()
    rate = model.config.audio_encoder.sampling_rate
    inputs = processor(text=[settings["prompt"]], padding=True, return_tensors="pt").to("cuda")
    segments = []
    total = 0
    target = round(duration * rate)
    overlap = rate
    torch.cuda.reset_peak_memory_stats()
    while total < target:
        seconds = min(25, (target-total+(overlap if segments else 0))/rate + 0.2)
        torch.manual_seed(settings["seed"] + len(segments))
        with torch.inference_mode():
            values = model.generate(**inputs, do_sample=True, guidance_scale=3.0,
                                    max_new_tokens=max(16, math.ceil(seconds*50)+4))
        audio = values[0, 0].float().cpu().numpy()
        if len(audio) <= (overlap if segments else 0):
            raise RuntimeError("Generated segment too short")
        total += len(audio) - (overlap if segments else 0)
        segments.append(audio)
    audio = blend_segments(segments, overlap)[:target]
    wavfile.write(str(out), rate, np.clip(audio, -1, 1).astype(np.float32))
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    shutil.copy2(out, tmp)
    tmp.replace(cache)
    job["_peak_gpu_memory_gib"] = round(torch.cuda.max_memory_allocated()/1024**3, 3)
    job["_cache_hit"] = False
    return [out.name]


# -------------------------------
# Job entry points (notebook API)
# -------------------------------

def run_job(job_path, exchange_root):
    """Run a packaged job and log the result to results/results.jsonl."""
    job_path = Path(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    results_root = Path(exchange_root) / "results"
    out_dir = results_root / job["job_id"]
    out_dir.mkdir(parents=True, exist_ok=True)

    model = MODEL_ID
    entry = _base_entry(job, model, job.get("music", {}))
    start = time.perf_counter()

    try:
        entry["files"] = _generate_impl(job, out_dir)
        entry["status"] = "success"
        entry["error"] = None
    except Exception as error:  # noqa: BLE001 - log and report, don't hide
        entry["status"] = "failed"
        entry["error"] = f"{type(error).__name__}: {error}"[:300]

    latency = time.perf_counter() - start
    entry["latency_seconds"] = round(latency, 3)
    entry["gpu_minutes"] = round(latency / 60, 3)
    entry["cost_usd"] = 0.0
    entry["cache_hit"] = job.get("_cache_hit", False)
    entry["peak_gpu_memory_gib"] = job.get("_peak_gpu_memory_gib")

    _write_result(results_root, entry)
    return entry


def run_smoke(exchange_root):
    """Tiny generation to verify MusicGen + CUDA work on this runtime."""
    smoke_job = {
        "job_id": f"smoke-music-{int(time.time())}",
        "stage": "music",
        "music": {
            "prompt": "soft piano note sequence",
            "duration_seconds": 5,
            "model": MODEL_ID,
            "seed": 42,
        },
    }
    results_root = Path(exchange_root) / "results"
    job_path = results_root / "_smoke_job.json"
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(smoke_job), encoding="utf-8")
    return run_job(job_path, exchange_root)
