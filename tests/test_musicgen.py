import pytest
from pipeline.run import music_job
from pipeline.gpu_music import blend_segments

def test_music_job_migrates_legacy_model():
    story = {"music": {"model": "ace-step-1.5", "prompt": "piano", "duration_seconds": 75}}
    job = music_job(story)
    assert job["music"]["model"] == "facebook/musicgen-small"
    assert job["music"]["seed"] == 42
    assert story["music"]["model"] == "ace-step-1.5"

def test_music_job_preserves_seed():
    assert music_job({"music": {"seed": 7}})["music"]["seed"] == 7

def test_crossfade_length_and_endpoints():
    np = pytest.importorskip("numpy")
    result = blend_segments([np.ones(10), np.zeros(10)], 4)
    assert len(result) == 16
    assert result[6] == 1
    assert result[9] == 0
    assert np.all(np.diff(result) <= 0)
