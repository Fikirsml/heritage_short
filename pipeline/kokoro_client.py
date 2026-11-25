"""Local Kokoro-82M narration provider (offline fallback to Gemini TTS).

Runs entirely on CPU — no GPU, no API key, no per-call cost. The first
call downloads ~330 MB of weights (hexgrad/Kokoro-82M) into the Hugging
Face cache.

Install: pip install "kokoro>=0.9.2" "misaki[en]>=0.9.4"
         brew install espeak-ng   # English G2P shells out to espeak-ng
Imports are lazy so this module stays importable without the deps.
"""

import os
import shutil
import struct
import time
from pathlib import Path

from pipeline.utils import (
    OUTPUT_DIR,
    get_cache_path,
    is_cached,
    log_run,
    write_pcm_wav,
)

MODEL = "kokoro-82m"
REPO_ID = "hexgrad/Kokoro-82M"
SAMPLE_RATE = 24000
LANG_CODE = "a"  # American English
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
# Homebrew prefixes checked when espeak-ng is not on PATH
_ESPEAK_PATHS = ("/usr/local/bin/espeak-ng", "/opt/homebrew/bin/espeak-ng")

_pipeline = None


def _ensure_espeak():
    """Make espeak-ng reachable for phonemizer: system binary or pip loader."""
    # PATH plus standard Homebrew prefixes (brew may be installed after login)
    candidates = [shutil.which("espeak-ng")]
    candidates += [p for p in _ESPEAK_PATHS if Path(p).is_file()]
    binary = next((c for c in candidates if c), None)
    if binary:
        os.environ.setdefault("PHONEMIZER_ESPEAK_EXECUTABLE", binary)
        bindir = str(Path(binary).parent)
        if bindir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")
        return
    try:
        import espeakng_loader
    except ImportError:
        raise RuntimeError(
            "espeak-ng not found - Kokoro needs it for English G2P. "
            "Install: pip install espeakng-loader (or: brew install espeak-ng)"
        )
    lib = Path(espeakng_loader.get_library_path())
    if not lib.is_file():
        raise RuntimeError(f"espeakng-loader library missing: {lib}")
    os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", str(lib))
    if hasattr(espeakng_loader, "get_data_path"):
        data = espeakng_loader.get_data_path()
        if data and Path(data).is_dir():
            os.environ.setdefault("ESPEAK_DATA_PATH", str(data))


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _ensure_espeak()
        from kokoro import KPipeline  # lazy: pulls in torch
        _pipeline = KPipeline(lang_code=LANG_CODE, repo_id=REPO_ID)
    return _pipeline


def _chunk_audio(result):
    """Extract the audio tensor/list from a KPipeline result."""
    audio = getattr(result, "audio", None)
    if audio is None and isinstance(result, (tuple, list)) and len(result) >= 3:
        audio = result[2]  # older releases yield (graphemes, phonemes, audio)
    if audio is None:
        raise RuntimeError("Kokoro chunk has no audio payload")
    return audio


def _to_pcm16(audio):
    """Float samples in [-1, 1] (torch tensor or sequence) -> PCM16 bytes."""
    samples = audio.tolist() if hasattr(audio, "tolist") else list(audio)
    ints = [int(max(-1.0, min(1.0, float(s))) * 32767) for s in samples]
    return struct.pack(f"<{len(ints)}h", *ints)


def synthesize_speech(script, voice=None, speed=None):
    """Synthesize with Kokoro. Returns (pcm_bytes, sample_rate)."""
    voice = voice or os.getenv("KOKORO_VOICE") or DEFAULT_VOICE
    speed = float(speed or os.getenv("KOKORO_SPEED") or DEFAULT_SPEED)

    chunks = [
        _to_pcm16(_chunk_audio(result))
        for result in _get_pipeline()(script, voice=voice, speed=speed)
    ]
    if not any(chunks):
        raise RuntimeError("Kokoro returned no audio")
    return b"".join(chunks), SAMPLE_RATE


def generate_narration(script, voice=None, speed=None, out_path=None):
    """Write the narration wav; identical params are served from cache."""
    voice = voice or os.getenv("KOKORO_VOICE") or DEFAULT_VOICE
    speed = float(speed or os.getenv("KOKORO_SPEED") or DEFAULT_SPEED)
    out_path = (
        Path(out_path)
        if out_path
        else OUTPUT_DIR / "narration" / "narration.wav"
    )
    params = {
        "provider": "kokoro",
        "voice": voice,
        "speed": speed,
        "chars": len(script),
    }
    cache_path = get_cache_path(
        "narration",
        {"provider": "kokoro", "model": MODEL, "script": script,
         "voice": voice, "speed": speed},
        "wav",
    )

    if is_cached(cache_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cache_path, out_path)
        log_run(
            stage="narration",
            model=MODEL,
            parameters={**params, "cached": True},
            latency=0.0,
            cost=0.0,
        )
        return out_path

    start = time.perf_counter()
    try:
        pcm, rate = synthesize_speech(script, voice=voice, speed=speed)
        write_pcm_wav(cache_path, pcm, rate)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cache_path, out_path)
    except Exception as error:
        log_run(
            stage="narration",
            model=MODEL,
            parameters=params,
            latency=time.perf_counter() - start,
            cost=0.0,
            status="failed",
            error=type(error).__name__,
        )
        raise

    log_run(
        stage="narration",
        model=MODEL,
        parameters=params,
        latency=time.perf_counter() - start,
        cost=0.0,
    )
    return out_path
    return out_path
