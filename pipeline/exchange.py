"""Google Drive exchange: package jobs for Colab, collect results back.

Layout (under DRIVE_EXCHANGE_DIR, or ./exchange as a local fallback):

    exchange_root/
      jobs/<stage>-<hash>/job.json     # generation parameters
      jobs/<stage>-<hash>/inputs/*     # copied input assets (keyframes)
      pipeline_gpu/gpu_music.py        # Colab-side modules, auto-synced
      pipeline_gpu/gpu_video.py
      results/<job_id>/*               # files produced on Colab
      results/results.jsonl            # Colab run log (merged into runs.jsonl)
"""

import json
import os
import shutil
from pathlib import Path

from pipeline import utils

GPU_MODULES = ("gpu_music.py", "gpu_video.py")
LOCAL_EXCHANGE = utils.ROOT_DIR / "exchange"


def exchange_root():
    """Drive-synced exchange folder, or local ./exchange fallback."""
    raw = os.getenv("DRIVE_EXCHANGE_DIR")
    return Path(raw).expanduser() if raw else LOCAL_EXCHANGE


def _sync_gpu_modules(root):
    """Copy the Colab-side modules so notebooks import current code."""
    gpu_dir = root / "pipeline_gpu"
    gpu_dir.mkdir(parents=True, exist_ok=True)
    for name in GPU_MODULES:
        shutil.copy2(utils.ROOT_DIR / "pipeline" / name, gpu_dir / name)


def package_job(stage, job, input_files=None):
    """Write job.json + inputs into the exchange dir. Returns job dir."""
    input_files = list(input_files or [])
    hashes = {Path(p).name: utils.hash_file(p) for p in input_files}
    job_id = f"{stage}-{utils.generate_hash({'job': job, 'inputs': hashes})[:16]}"
    root = exchange_root()
    job_dir = root / "jobs" / job_id
    (job_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(parents=True, exist_ok=True)

    for src in input_files or []:
        src = Path(src)
        shutil.copy2(src, job_dir / "inputs" / src.name)

    utils.save_json(
        {"job_id": job_id, "stage": stage, **job},
        job_dir / "job.json",
    )
    _sync_gpu_modules(root)
    return job_dir


def list_results(stage=None):
    """Job ids present under results/ (filtered by stage prefix)."""
    results_dir = exchange_root() / "results"
    if not results_dir.is_dir():
        return []
    ids = [d.name for d in results_dir.iterdir() if d.is_dir()]
    if stage:
        ids = [i for i in ids if i.startswith(f"{stage}-") or i.startswith(f"smoke-{stage}")]
    return sorted(ids)


def collect_results(dest_dir, stage=None, job_id_filter=None):
    """Copy successful result files into dest_dir and merge the Colab
    results.jsonl into runs.jsonl. Idempotent: already-imported job ids
    are tracked in .cache/collected_jobs.json. Returns copied paths."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    results_dir = exchange_root() / "results"
    log_path = results_dir / "results.jsonl"
    marker = utils.CACHE_DIR / "collected_jobs.json"
    seen = set(utils.load_json(marker)) if marker.is_file() else set()

    record_marker = utils.CACHE_DIR / "collected_records.json"
    records = set(utils.load_json(record_marker)) if record_marker.is_file() else set()
    copied, new_entries = [], []
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            job_id = entry.get("job_id")
            if job_id_filter and job_id != job_id_filter:
                continue
            if job_id in seen or (stage and entry.get("stage") != stage):
                continue
            record = utils.generate_hash(entry)
            if record in records:
                continue
            if entry.get("status") == "success":
                for name in entry.get("files", []):
                    src = results_dir / job_id / name
                    if src.is_file():
                        target = dest_dir / name
                        shutil.copy2(src, target)
                        copied.append(target)
            new_entries.append(entry)
            records.add(record)
            if job_id and entry.get("status") == "success" and not entry.get("error"):
                seen.add(job_id)

    if new_entries:
        with open(utils.LOG_FILE, "a", encoding="utf-8") as f:
            for entry in new_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        utils.save_json(sorted(seen), marker)
        utils.save_json(sorted(records), record_marker)

    return copied
