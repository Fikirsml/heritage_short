
import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from jsonschema import validate


# -------------------------------
# Project configuration
# -------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = ROOT_DIR / "outputs"
CACHE_DIR = ROOT_DIR / ".cache"
LOG_FILE = ROOT_DIR / "runs.jsonl"
STORYBOARD_FILE = ROOT_DIR / "storyboard.json"
SCHEMA_FILE = ROOT_DIR / "schema" / "storyboard.schema.json"

load_dotenv(ROOT_DIR / ".env")


# -------------------------------
# Environment variables
# -------------------------------

def get_env(name):
    """Retrieve a required environment variable."""
    value = os.getenv(name)

    if not value:
        raise ValueError(
            f"Missing environment variable: {name}"
        )

    return value


# -------------------------------
# JSON utilities
# -------------------------------

def load_json(path):
    """Read a JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data, path):
    """Save data to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data, file, indent=2, ensure_ascii=False
        )


# -------------------------------
# Storyboard validation
# -------------------------------

def load_storyboard():
    """Load and validate the storyboard."""
    storyboard = load_json(STORYBOARD_FILE)
    schema = load_json(SCHEMA_FILE)

    validate(instance=storyboard, schema=schema)

    return storyboard


# -------------------------------
# Caching
# -------------------------------

def generate_hash(data):
    """Generate a deterministic hash of stage inputs."""
    serialized = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def hash_file(path):
    """Hash a reference image, audio or other file."""
    return hashlib.sha256(
        Path(path).read_bytes()
    ).hexdigest()


def get_cache_path(stage, inputs, extension):
    """Return the cache path for specific stage inputs."""
    cache_key = generate_hash(inputs)

    directory = CACHE_DIR / stage
    directory.mkdir(parents=True, exist_ok=True)

    extension = extension.lstrip(".")

    return directory / f"{cache_key}.{extension}"


def is_cached(path):
    """Check whether a non-empty cached output exists."""
    path = Path(path)

    return path.is_file() and path.stat().st_size > 0


# -------------------------------
# Model call logging
# -------------------------------

def log_run(
    stage,
    model,
    parameters,
    latency,
    seed=None,
    cost=None,
    status="success",
    shot_id=None,
    error=None,
    gpu_minutes=None
):
    """Append one model call to runs.jsonl."""

    entry = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "stage": stage,
        "shot_id": shot_id,
        "model": model,
        "parameters": parameters,
        "seed": seed,
        "latency_seconds": round(latency, 3),
        "cost_usd": cost,
        "gpu_minutes": gpu_minutes,
        "status": status,
        "error": error
    }

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(
            json.dumps(entry, ensure_ascii=False) + "\n"
        )


# -------------------------------
# Retry mechanism
# -------------------------------

def retry(exceptions, max_attempts=3, delay=2):
    """Retry transient failures with exponential backoff."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions:
                    if attempt == max_attempts:
                        raise

                    wait_time = delay * (2 ** (attempt - 1))

                    print(
                        f"Attempt {attempt} failed. "
                        f"Retrying in {wait_time}s..."
                    )

                    time.sleep(wait_time)

        return wrapper

    return decorator


# -------------------------------
# Directory initialization
# -------------------------------

def setup_directories():
    """Create directories required by the pipeline."""

    directories = [
        OUTPUT_DIR / "references",
        OUTPUT_DIR / "keyframes",
        OUTPUT_DIR / "shots",
        OUTPUT_DIR / "narration",
        OUTPUT_DIR / "music",
        OUTPUT_DIR / "final",
        CACHE_DIR
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    LOG_FILE.touch(exist_ok=True)


if __name__ == "__main__":
    setup_directories()
    print("Project directories initialized successfully.")
