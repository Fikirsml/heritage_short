"""Narration TTS provider dispatch.

TTS_PROVIDER selects the backend:
  kokoro  local Kokoro-82M on CPU (default — free, offline, no API key)
  gemini  Google Gemini TTS (paid API; gemini-2.5-flash-preview-tts)
"""

import os


def generate_narration(script, voice=None, model=None, out_path=None):
    provider = (os.getenv("TTS_PROVIDER") or "kokoro").strip().lower()

    if provider == "gemini":
        from pipeline import gemini_client
        return gemini_client.generate_narration(
            script, voice=voice, model=model, out_path=out_path
        )

    if provider == "kokoro":
        from pipeline import kokoro_client
        # Gemini voice names (e.g. "Kore") aren't Kokoro voices — Kokoro
        # ids always contain '_' (af_heart, bm_george, ...). Fall back to
        # the Kokoro default instead of failing on an unknown voice.
        if voice and "_" not in voice:
            voice = None
        return kokoro_client.generate_narration(
            script, voice=voice, out_path=out_path
        )

    raise ValueError(
        f"Unknown TTS_PROVIDER={provider!r} (expected 'kokoro' or 'gemini')"
    )
