import json
import sys
import types
import wave

import pytest

from pipeline import kokoro_client, tts, utils


@pytest.fixture(autouse=True)
def reset_pipeline(monkeypatch, tmp_path):
    """Isolate the module-level pipeline cache and redirects per test."""
    kokoro_client._pipeline = None
    monkeypatch.setenv("KOKORO_VOICE", "af_heart")
    monkeypatch.setenv("KOKORO_SPEED", "1.0")
    monkeypatch.setattr(
        kokoro_client.shutil, "which", lambda name: "/usr/bin/espeak-ng"
    )
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(utils, "LOG_FILE", tmp_path / "runs.jsonl")
    yield
    kokoro_client._pipeline = None


def _fake_kokoro(monkeypatch, chunks=((0.0, 0.5, -0.5, 2.0), (0.25,))):
    """Install a fake `kokoro` module; returns its call log."""
    calls = []

    class _Result:
        def __init__(self, audio):
            self.audio = audio

    class KPipeline:
        def __init__(self, lang_code="a", repo_id=None):
            calls.append(("init", lang_code, repo_id))

        def __call__(self, text, voice=None, speed=1.0):
            calls.append(("call", text, voice, speed))
            for chunk in chunks:
                yield _Result(list(chunk))

    module = types.ModuleType("kokoro")
    module.KPipeline = KPipeline
    monkeypatch.setitem(sys.modules, "kokoro", module)
    return calls


def _log_entries():
    if not utils.LOG_FILE.is_file():
        return []
    return [
        json.loads(line)
        for line in utils.LOG_FILE.read_text().splitlines()
    ]


def test_synthesize_concatenates_chunks(monkeypatch):
    calls = _fake_kokoro(monkeypatch)
    pcm, rate = kokoro_client.synthesize_speech("Hello world.")

    assert rate == 24000
    assert len(pcm) == 2 * 5  # 4 + 1 samples, 16-bit
    # +2.0 input is clipped to full scale
    assert pcm[6:8] == (32767).to_bytes(2, "little", signed=True)
    assert calls == [
        ("init", "a", "hexgrad/Kokoro-82M"),
        ("call", "Hello world.", "af_heart", 1.0),
    ]


def test_synthesize_empty_audio_fails(monkeypatch):
    _fake_kokoro(monkeypatch, chunks=())
    with pytest.raises(RuntimeError, match="no audio"):
        kokoro_client.synthesize_speech("Hello")


def test_missing_espeak_fails(monkeypatch):
    _fake_kokoro(monkeypatch)
    monkeypatch.setattr(kokoro_client.shutil, "which", lambda name: None)
    monkeypatch.setattr(kokoro_client, "_ESPEAK_PATHS", ())
    monkeypatch.setitem(sys.modules, "espeakng_loader", None)
    with pytest.raises(RuntimeError, match="espeak-ng"):
        kokoro_client.synthesize_speech("Hello")


def test_generate_narration_writes_wav_and_logs(monkeypatch, tmp_path):
    _fake_kokoro(monkeypatch)
    out = tmp_path / "narration.wav"

    result = kokoro_client.generate_narration("A test script.", out_path=out)

    assert result == out
    with wave.open(str(out), "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 5

    entry = _log_entries()[-1]
    assert entry["model"] == "kokoro-82m"
    assert entry["stage"] == "narration"
    assert entry["status"] == "success"
    assert entry["cost_usd"] == 0.0
    assert entry["parameters"]["voice"] == "af_heart"


def test_generate_narration_uses_cache(monkeypatch, tmp_path):
    calls = _fake_kokoro(monkeypatch)
    out = tmp_path / "narration.wav"

    kokoro_client.generate_narration("Same script.", out_path=out)
    kokoro_client.generate_narration("Same script.", out_path=out)

    assert len([c for c in calls if c[0] == "call"]) == 1
    entries = _log_entries()
    assert entries[-1]["parameters"]["cached"] is True


def test_generate_narration_logs_failure(monkeypatch, tmp_path):
    _fake_kokoro(monkeypatch)
    monkeypatch.setitem(sys.modules, "espeakng_loader", None)
    monkeypatch.setattr(kokoro_client.shutil, "which", lambda name: None)
    monkeypatch.setattr(kokoro_client, "_ESPEAK_PATHS", ())
    with pytest.raises(RuntimeError):
        kokoro_client.generate_narration("x", out_path=tmp_path / "n.wav")

    entry = _log_entries()[-1]
    assert entry["status"] == "failed"
    assert entry["model"] == "kokoro-82m"


def test_tts_dispatch_kokoro_maps_gemini_voice(monkeypatch, tmp_path):
    calls = _fake_kokoro(monkeypatch)
    monkeypatch.setenv("TTS_PROVIDER", "kokoro")
    monkeypatch.setenv("KOKORO_VOICE", "af_bella")

    tts.generate_narration("Script.", voice="Kore", out_path=tmp_path / "n.wav")

    # Gemini-style voice "Kore" is dropped -> env/default Kokoro voice used
    assert calls[-1] == ("call", "Script.", "af_bella", 1.0)


def test_tts_dispatch_kokoro_accepts_kokoro_voice(monkeypatch, tmp_path):
    calls = _fake_kokoro(monkeypatch)
    monkeypatch.setenv("TTS_PROVIDER", "kokoro")

    tts.generate_narration(
        "Script.", voice="bm_george", out_path=tmp_path / "n.wav"
    )
    assert calls[-1] == ("call", "Script.", "bm_george", 1.0)


def test_tts_dispatch_unknown_provider(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "wat")
    with pytest.raises(ValueError, match="TTS_PROVIDER"):
        tts.generate_narration("x")
