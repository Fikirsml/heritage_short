import wave
import pytest
from pipeline.smoke_test import write_pcm_wav, safe_error


def test_wav(tmp_path):
    path = tmp_path / "test.wav"
    write_pcm_wav(path, b"\x00\x00" * 240)
    with wave.open(str(path), "rb") as audio:
        assert audio.getnframes() == 240
        assert audio.getframerate() == 24000
        assert audio.getnchannels() == 1


def test_empty_audio(tmp_path):
    with pytest.raises(ValueError):
        write_pcm_wav(tmp_path / "test.wav", b"")


def test_error_redaction():
    assert "secret-token" not in safe_error(RuntimeError("secret-token"))
