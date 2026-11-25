import json
import pytest
from pipeline import utils


def test_hash():
    assert utils.generate_hash({"a": 1, "b": 2}) == utils.generate_hash({"b": 2, "a": 1})
    assert utils.generate_hash({"a": 1}) != utils.generate_hash({"a": 2})


def test_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path)
    path = utils.get_cache_path("test", {"a": 1}, ".wav")
    assert not utils.is_cached(path)
    path.touch()
    assert not utils.is_cached(path)
    path.write_bytes(b"audio")
    assert utils.is_cached(path)


def test_log(tmp_path, monkeypatch):
    path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(utils, "LOG_FILE", path)
    utils.log_run("test", "model", {}, 0.1234)
    utils.log_run("test", "model", {}, 1, status="failed")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["latency_seconds"] == 0.123
    assert records[0]["cost_usd"] is None
    assert records[1]["status"] == "failed"


def test_retry(monkeypatch):
    delays = []
    monkeypatch.setattr(utils.time, "sleep", delays.append)
    attempts = []
    @utils.retry(ValueError, max_attempts=3)
    def work():
        attempts.append(1)
        if len(attempts) < 3:
            raise ValueError("temporary")
        return "ok"
    assert work() == "ok"
    assert delays == [2, 4]


def test_missing_env(monkeypatch):
    monkeypatch.delenv("HERITAGE_TEST_MISSING", raising=False)
    with pytest.raises(ValueError, match="HERITAGE_TEST_MISSING"):
        utils.get_env("HERITAGE_TEST_MISSING")
