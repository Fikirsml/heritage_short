"""Gemini API client: narration TTS for the pipeline.

Provider calls live here so stages in run.py and the smoke tests share
one implementation. All functions are safe to import without credentials;
errors only surface when a call is made.
"""

import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types

from pipeline.utils import (
    OUTPUT_DIR,
    get_env,
    log_run,
    write_pcm_wav,
)

DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Kore"


def _client():
    return genai.Client(api_key=get_env("GEMINI_API_KEY"))


def synthesize_speech(text, model, voice):
    """Call Gemini TTS. Returns (pcm_bytes, sample_rate)."""
    response = _client().models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice
                    )
                )
            ),
        ),
    )

    for candidate in response.candidates or []:
        parts = (candidate.content.parts or []) if candidate.content else []
        for part in parts:
            inline = part.inline_data
            if (
                inline
                and inline.data
                and (inline.mime_type or "").lower().startswith("audio/l16")
            ):
                match = re.search(r"rate=(\d+)", inline.mime_type)
                rate = int(match.group(1)) if match else 24000
                return inline.data, rate

    raise RuntimeError("No supported PCM audio returned")


def generate_narration(script, voice=None, model=None, out_path=None):
    """Synthesize the full narration script to a wav file."""
    model = model or os.getenv("GEMINI_TTS_MODEL") or DEFAULT_TTS_MODEL
    voice = voice or os.getenv("GEMINI_TTS_VOICE") or DEFAULT_VOICE
    out_path = (
        Path(out_path)
        if out_path
        else OUTPUT_DIR / "narration" / "narration.wav"
    )

    start = time.perf_counter()
    try:
        pcm, rate = synthesize_speech(script, model, voice)
        write_pcm_wav(out_path, pcm, rate)
    except Exception as error:
        log_run(
            stage="narration",
            model=model,
            parameters={"voice": voice, "chars": len(script)},
            latency=time.perf_counter() - start,
            status="failed",
            error=type(error).__name__,
        )
        raise

    log_run(
        stage="narration",
        model=model,
        parameters={"voice": voice, "chars": len(script)},
        latency=time.perf_counter() - start,
    )
    return out_path
