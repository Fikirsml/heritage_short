"""Cloudflare Workers AI client: keyframe image generation.

Uses the REST API directly (no SDK) with sha256-based caching so
repeated runs of the same prompt+params cost nothing.
"""

import base64
import os
import time
from pathlib import Path

import requests

from pipeline.utils import (
    get_cache_path,
    get_env,
    is_cached,
    log_run,
)

DEFAULT_MODEL = "@cf/black-forest-labs/flux-1-schnell"


def generate_image(prompt, model=None, out_path=None, width=None, height=None):
    """Generate a PNG keyframe via Workers AI. Returns the file path."""
    model = model or os.getenv("CF_IMAGE_MODEL") or DEFAULT_MODEL

    cache = get_cache_path(
        "keyframes",
        {"prompt": prompt, "model": model, "w": width, "h": height},
        ".png",
    )
    if out_path is None and is_cached(cache):
        return cache

    account_id = get_env("CLOUDFLARE_ACCOUNT_ID")
    api_token = get_env("CLOUDFLARE_API_TOKEN")
    url = (
        "https://api.cloudflare.com/client/v4/"
        f"accounts/{account_id}/ai/run/{model}"
    )
    payload = {"prompt": prompt}
    if width:
        payload["width"] = width
    if height:
        payload["height"] = height

    start = time.perf_counter()
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_token}"},
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        result = response.json()

        if not result.get("success"):
            raise RuntimeError(
                f"Cloudflare generation failed: {result.get('errors')}"
            )
        image_b64 = result.get("result", {}).get("image")
        if not image_b64:
            raise RuntimeError("No generated image returned")

        target = Path(out_path) if out_path else cache
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(image_b64))
    except Exception as error:
        log_run(
            stage="keyframes",
            model=model,
            parameters=payload,
            latency=time.perf_counter() - start,
            status="failed",
            error=type(error).__name__,
        )
        raise

    log_run(
        stage="keyframes",
        model=model,
        parameters=payload,
        latency=time.perf_counter() - start,
    )
    return target
