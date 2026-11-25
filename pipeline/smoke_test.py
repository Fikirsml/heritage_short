
import time
import argparse
import os
import wave
import re
from google.genai import types
import requests

from google import genai

from pipeline.utils import (
    get_env,
    log_run,
    setup_directories
)


# -----------------------------------
# Shared smoke test runner
# -----------------------------------

def safe_error(error):
    status = getattr(error, "code", None)
    response = getattr(error, "response", None)
    if response is not None:
        status = getattr(response, "status_code", status)
    hints = {400: "invalid request", 401: "authentication failed",
             403: "permission denied", 404: "resource unavailable",
             429: "quota or rate limit", 503: "provider unavailable"}
    if isinstance(status, int):
        return f"{type(error).__name__}: HTTP {status} ({hints.get(status, 'request failed')})"
    if isinstance(error, requests.Timeout):
        return "Timeout: provider did not respond"
    return f"{type(error).__name__}: inspect local configuration or response"


def run_test(provider, model, test_function, parameters):
    """Execute a provider test and record its result."""

    start = time.perf_counter()

    try:
        test_function()

    except Exception as error:
        latency = time.perf_counter() - start

        log_run(
            stage="smoke_test",
            model=model,
            parameters=parameters,
            latency=latency,
            status="failed",
            error=safe_error(error)
        )

        print(
            f"[FAIL] {provider}: "
            f"{safe_error(error)} ({latency:.2f}s)"
        )

        return False

    latency = time.perf_counter() - start

    log_run(
        stage="smoke_test",
        model=model,
        parameters=parameters,
        latency=latency,
        status="success"
    )

    print(f"[PASS] {provider}: {latency:.2f}s")

    return True


# -----------------------------------
# Gemini API
# -----------------------------------

def test_gemini(model):
    """Verify Gemini text generation."""

    client = genai.Client(
        api_key=get_env("GEMINI_API_KEY")
    )

    response = client.models.generate_content(
        model=model,
        contents="Reply with the word OK."
    )

    if not response.text:
        raise RuntimeError("Empty Gemini response")


# -----------------------------------
# Cloudflare Workers AI
# -----------------------------------

def test_cloudflare(model):
    """Verify Cloudflare image generation."""

    account_id = get_env("CLOUDFLARE_ACCOUNT_ID")
    api_token = get_env("CLOUDFLARE_API_TOKEN")

    url = (
        "https://api.cloudflare.com/client/v4/"
        f"accounts/{account_id}/ai/run/{model}"
    )

    headers = {
        "Authorization": f"Bearer {api_token}"
    }

    payload = {
        "prompt": "A simple green tree on a white background."
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("success"):
        raise RuntimeError("Cloudflare generation failed")

    if not result.get("result", {}).get("image"):
        raise RuntimeError("No generated image returned")


# -----------------------------------
# Kaggle API
# -----------------------------------

def test_kaggle():
    """Verify Kaggle authentication and API access."""

    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()

    api.dataset_list(
        search="iris",
        page=1
    )


def write_pcm_wav(path, data, sample_rate=24000):
    if not data or len(data) % 2 or sample_rate <= 0:
        raise ValueError("Invalid PCM audio")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with wave.open(str(temporary), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(data)
    temporary.replace(path)


def test_gemini_tts(model, voice):
    from pipeline.utils import OUTPUT_DIR
    path = OUTPUT_DIR / "narration" / "test.wav"
    path.unlink(missing_ok=True)
    client = genai.Client(api_key=get_env("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=model,
        contents="Say clearly: This is a narration test.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            )
        )
    )
    for candidate in response.candidates or []:
        for part in (candidate.content.parts or []) if candidate.content else []:
            inline = part.inline_data
            if inline and inline.data and (inline.mime_type or "").lower().startswith("audio/l16"):
                match = re.search(r"rate=(\d+)", inline.mime_type)
                write_pcm_wav(path, inline.data, int(match.group(1)) if match else 24000)
                return
    raise RuntimeError("No supported PCM audio returned")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["gemini", "gemini-tts", "cloudflare", "kaggle"])
    args = parser.parse_args()
    setup_directories()
    text_model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    tts_model = os.getenv("GEMINI_TTS_MODEL") or "gemini-2.5-flash-preview-tts"
    voice = os.getenv("GEMINI_TTS_VOICE") or "Kore"
    image_model = "@cf/black-forest-labs/flux-1-schnell"
    checks = {
        "gemini": (text_model, lambda: test_gemini(text_model), {"provider": "Google", "prompt": "Reply with the word OK."}),
        "gemini-tts": (tts_model, lambda: test_gemini_tts(tts_model, voice), {"provider": "Google", "voice": voice, "prompt": "Say clearly: This is a narration test."}),
        "cloudflare": (image_model, lambda: test_cloudflare(image_model), {"provider": "Cloudflare", "prompt": "A simple green tree on a white background."}),
        "kaggle": (None, test_kaggle, {"provider": "Kaggle", "test": "api_connectivity"})
    }
    results = {}
    for name, (model, function, parameters) in checks.items():
        if args.provider is None or args.provider == name:
            results[name] = run_test(name, model, function, parameters)
    print(f"{sum(results.values())}/{len(results)} tests passed. Results recorded in runs.jsonl")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
