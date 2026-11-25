"""Colab-side video generation with Wan 2.2 (TI2V-5B).

Copied into the Drive exchange folder (exchange/pipeline_gpu/) and imported
by notebooks/video_wan22.ipynb. Heavy deps (torch, diffusers) are imported
lazily so the module stays importable on the local Mac for testing.

T4 constraints (14.56 GB, no bf16): fp16 transformer, fp32 VAE,
enable_model_cpu_offload, VAE tiling, small frames/resolution per shot.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "Wan-AI/Wan2.2-TI2V-5B"
DEFAULT_NEGATIVE = (
    "low quality, distorted, warped, text, watermark, "
    "flicker, blurry, oversaturated"
)
DEFAULT_FPS = 24


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
        "stage": job.get("stage", "video"),
        "model": model,
        "parameters": parameters,
        "files": [],
    }


# -------------------------------
# Wan 2.2 pipeline
# -------------------------------

def _load_pipe(model_id):
    """Load Wan2.2-TI2V-5B configured for a 14.5 GB T4."""
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline

    # VAE stays fp32 — fp16 VAE decoding produces black/corrupted frames.
    vae = AutoencoderKLWan.from_pretrained(
        model_id, subfolder="vae", torch_dtype=torch.float32
    )
    pipe = WanPipeline.from_pretrained(
        model_id, vae=vae, torch_dtype=torch.float16
    )
    # Streams transformer/text-encoder blocks GPU<->CPU as needed;
    # without this the ~5B-param transformer alone approaches T4 limits.
    pipe.enable_model_cpu_offload()
    if hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    return pipe


def _generate_one(pipe, shot, inputs_dir, out_dir, fps):
    """Generate one shot clip. Returns filename or None if skipped."""
    import torch
    from diffusers.utils import export_to_video, load_image

    video = shot.get("video", {})
    keyframe = Path(inputs_dir) / f"{shot['id']}.png"
    image = load_image(str(keyframe)) if keyframe.is_file() else None

    generator = torch.Generator(device="cuda").manual_seed(
        int(video.get("seed", 42))
    )

    kwargs = {
        "prompt": shot["prompt"],
        "negative_prompt": shot.get("negative_prompt", DEFAULT_NEGATIVE),
        "height": int(video.get("height", 480)),
        "width": int(video.get("width", 480)),
        "num_frames": int(video.get("frames", 49)),
        "num_inference_steps": int(video.get("steps", 30)),
        "guidance_scale": float(video.get("guidance", 5.0)),
        "generator": generator,
    }
    if image is not None:
        # TI2V-5B accepts an optional first-frame conditioning image.
        kwargs["image"] = image

    out_path = Path(out_dir) / f"{shot['id']}.mp4"
    result = pipe(**kwargs)
    export_to_video(result.frames[0], str(out_path), fps=fps)
    torch.cuda.empty_cache()

    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RuntimeError(f"No video written for {shot['id']}")
    return out_path.name


def _generate_impl(job, out_dir, inputs_dir):
    """Generate all shots in the job. Returns list of produced files."""
    shots = job.get("shots", [])
    if not shots:
        raise RuntimeError("Job contains no shots")

    model_id = (
        shots[0].get("video", {}).get("model") or DEFAULT_MODEL
    )
    fps = int(job.get("fps", DEFAULT_FPS))
    pipe = _load_pipe(model_id)

    files, failures = [], []
    for shot in shots:
        try:
            files.append(_generate_one(pipe, shot, inputs_dir, out_dir, fps))
        except Exception as error:  # noqa: BLE001 - record per-shot, continue
            failures.append(f"{shot.get('id')}: {type(error).__name__}")

    if not files:
        raise RuntimeError(
            "All shots failed: " + "; ".join(failures or ["unknown"])
        )
    return files, failures


# -------------------------------
# Job entry points (notebook API)
# -------------------------------

def run_job(job_path, exchange_root):
    """Run a packaged video job; log to results/results.jsonl."""
    job_path = Path(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    results_root = Path(exchange_root) / "results"
    out_dir = results_root / job["job_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = job_path.parent / "inputs"

    model = (
        job.get("shots", [{}])[0].get("video", {}).get("model")
        or DEFAULT_MODEL
    )
    entry = _base_entry(job, model, {"shots": len(job.get("shots", []))})
    start = time.perf_counter()

    try:
        files, failures = _generate_impl(job, out_dir, inputs_dir)
        entry["files"] = files
        entry["status"] = "success"
        entry["error"] = "; ".join(failures) if failures else None
    except Exception as error:  # noqa: BLE001
        entry["status"] = "failed"
        entry["error"] = f"{type(error).__name__}: {error}"[:300]

    latency = time.perf_counter() - start
    entry["latency_seconds"] = round(latency, 3)
    entry["gpu_minutes"] = round(latency / 60, 3)
    entry["cost_usd"] = None

    _write_result(results_root, entry)
    return entry


def run_smoke(exchange_root):
    """Minimal clip to verify Wan 2.2 + CUDA work on this runtime."""
    smoke_job = {
        "job_id": f"smoke-video-{int(time.time())}",
        "stage": "video",
        "fps": DEFAULT_FPS,
        "shots": [
            {
                "id": "smoke",
                "prompt": "a tree swaying gently, soft light",
                "video": {
                    "model": DEFAULT_MODEL,
                    "width": 480,
                    "height": 480,
                    "frames": 17,
                    "steps": 6,
                    "guidance": 5.0,
                    "seed": 1,
                },
            }
        ],
    }
    results_root = Path(exchange_root) / "results"
    job_path = results_root / "_smoke_video_job.json"
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(smoke_job), encoding="utf-8")
    return run_job(job_path, exchange_root)
