
import time
import requests

from google import genai
from kaggle.api.kaggle_api_extended import KaggleApi

from pipeline.utils import (
    get_env,
    log_run,
    setup_directories
)


# -----------------------------------
# Shared smoke test runner
# -----------------------------------

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
            error=type(error).__name__
        )

        print(
            f"[FAIL] {provider}: "
            f"{type(error).__name__} ({latency:.2f}s)"
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

    api = KaggleApi()
    api.authenticate()

    api.dataset_list(
        search="iris",
        page=1
    )


# -----------------------------------
# Main entry point
# -----------------------------------

def main():

    setup_directories()

    print("=" * 45)
    print("HERITAGE SHORT - PROVIDER SMOKE TEST")
    print("=" * 45)

    gemini_model = get_env("GEMINI_MODEL")
    cloudflare_model = "@cf/black-forest-labs/flux-1-schnell"

    results = {}

    results["Gemini"] = run_test(
        provider="Gemini",
        model=gemini_model,
        test_function=lambda: test_gemini(gemini_model),
        parameters={
            "provider": "Google",
            "test": "text_generation",
            "prompt": "Reply with the word OK."
        }
    )

    results["Cloudflare"] = run_test(
        provider="Cloudflare",
        model=cloudflare_model,
        test_function=lambda: test_cloudflare(cloudflare_model),
        parameters={
            "provider": "Cloudflare",
            "test": "image_generation",
            "prompt": "A simple green tree on a white background."
        }
    )

    results["Kaggle"] = run_test(
        provider="Kaggle",
        model=None,
        test_function=test_kaggle,
        parameters={
            "provider": "Kaggle",
            "test": "api_connectivity"
        }
    )

    print("\n" + "=" * 45)
    print("SMOKE TEST SUMMARY")
    print("=" * 45)

    for provider, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{provider}: {status}")

    passed_count = sum(results.values())

    print(
        f"\n{passed_count}/{len(results)} tests passed."
    )

    print("Results recorded in runs.jsonl")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
