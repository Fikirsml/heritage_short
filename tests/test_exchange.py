import json

from pipeline import exchange, utils


def _write_result_line(root, entry):
    results = root / "results"
    results.mkdir(parents=True, exist_ok=True)
    with open(results / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def test_exchange_root_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.delenv("DRIVE_EXCHANGE_DIR", raising=False)
    assert exchange.exchange_root() == exchange.LOCAL_EXCHANGE


def test_exchange_root_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DRIVE_EXCHANGE_DIR", str(tmp_path / "drive" / "ex"))
    assert exchange.exchange_root() == tmp_path / "drive" / "ex"


def test_package_job(tmp_path, monkeypatch):
    monkeypatch.setenv("DRIVE_EXCHANGE_DIR", str(tmp_path / "ex"))
    src = tmp_path / "shot_01.png"
    src.write_bytes(b"png-bytes")

    job_dir = exchange.package_job(
        "video", {"shots": [{"id": "shot_01"}]}, [src]
    )

    job = json.loads((job_dir / "job.json").read_text())
    assert job["job_id"].startswith("video-")
    assert job["stage"] == "video"
    assert (job_dir / "inputs" / "shot_01.png").read_bytes() == b"png-bytes"

    gpu_dir = tmp_path / "ex" / "pipeline_gpu"
    assert (gpu_dir / "gpu_music.py").is_file()
    assert (gpu_dir / "gpu_video.py").is_file()


def test_collect_results_copies_and_merges(tmp_path, monkeypatch):
    monkeypatch.setenv("DRIVE_EXCHANGE_DIR", str(tmp_path / "ex"))
    log = tmp_path / "runs.jsonl"
    monkeypatch.setattr(utils, "LOG_FILE", log)
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path / "cache")

    job_dir = tmp_path / "ex" / "results" / "music-abc12345"
    job_dir.mkdir(parents=True)
    (job_dir / "music.wav").write_bytes(b"audio")
    _write_result_line(tmp_path / "ex", {
        "job_id": "music-abc12345",
        "stage": "music",
        "status": "success",
        "files": ["music.wav"],
        "model": "ace-step-1.5",
        "latency_seconds": 5.0,
    })

    dest = tmp_path / "out"
    copied = exchange.collect_results(dest)

    assert [p.name for p in copied] == ["music.wav"]
    merged = [json.loads(l) for l in log.read_text().splitlines()]
    assert merged[0]["job_id"] == "music-abc12345"


def test_collect_results_idempotent_and_skips_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("DRIVE_EXCHANGE_DIR", str(tmp_path / "ex"))
    log = tmp_path / "runs.jsonl"
    monkeypatch.setattr(utils, "LOG_FILE", log)
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path / "cache")

    _write_result_line(tmp_path / "ex", {
        "job_id": "video-failed1",
        "stage": "video",
        "status": "failed",
        "files": [],
        "error": "CUDA out of memory",
    })

    dest = tmp_path / "out"
    copied = exchange.collect_results(dest)
    assert copied == []  # failed job: nothing to copy
    # failure still recorded in runs.jsonl
    merged = [json.loads(l) for l in log.read_text().splitlines()]
    assert merged[0]["status"] == "failed"

    # second collect: nothing re-imported
    assert exchange.collect_results(dest) == []
    assert len(log.read_text().splitlines()) == 1
