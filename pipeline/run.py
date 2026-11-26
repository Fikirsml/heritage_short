"""One-command orchestrator for the semi-automated pipeline.

Stages:
    story       generate storyboard.json via Gemini (reuses existing unless --force)
    keyframes   Cloudflare keyframe image per shot -> outputs/keyframes/
    narration   Gemini TTS -> outputs/narration/narration.wav
    package     write Colab jobs (music + video) into the Drive exchange dir
    collect     copy Colab results back into outputs/ and merge runs log
    assemble    ffmpeg build -> outputs/final/ + outputs/radio_cut/
    all         local stages, then print the Colab handoff checklist

GPU stages (music, video) run manually in Colab — see COLAB.md.
`--resume` is a shortcut for collect + assemble after Drive sync.
"""

import argparse
import copy
import sys
import os
import re
import wave

from pipeline import exchange, utils
from pipeline.utils import OUTPUT_DIR, STORYBOARD_FILE


def stage_story(force=False):
    if STORYBOARD_FILE.is_file() and not force:
        storyboard = utils.load_storyboard()
        from pipeline.storyboard import load_creative_inputs
        narration, _, _ = load_creative_inputs()
        if storyboard["narration"]["script"] != narration:
            raise ValueError("Narration changed; regenerate storyboard with --stage story --force")
        print(
            f"[story] reusing {STORYBOARD_FILE.name} "
            f"({len(storyboard['shots'])} shots). "
            "Use --force to regenerate."
        )
        return storyboard
    from pipeline import storyboard as storyboard_stage
    result = storyboard_stage.generate_storyboard()
    print(f"[story] wrote {STORYBOARD_FILE.name} ({len(result['shots'])} shots)")
    return result


STYLE = "Cinematic realism, recurring anonymous student in neutral charcoal clothing, faces hidden, restrained cool-to-warm palette, centered composition, no readable generated text."

def visual_prompt(shot):
    return re.split(r"\bMotion:\s*", shot["prompt"], maxsplit=1, flags=re.I)[0].strip()

def stage_keyframes(storyboard):
    from pipeline.cloudflare_client import generate_image

    made = []
    for shot in storyboard["shots"]:
        out = OUTPUT_DIR / "keyframes" / f"{shot['id']}.png"
        if out.is_file() and out.stat().st_size > 0:
            print(f"[keyframes] {shot['id']}: cached")
        else:
            generate_image(visual_prompt(shot) + " " + STYLE, out_path=out)
            print(f"[keyframes] {shot['id']}: generated")
        made.append(out)
    return made


def stage_narration(storyboard):
    from pipeline import tts

    narration = storyboard["narration"]
    path = tts.generate_narration(
        narration["script"],
        voice=(os.getenv("KOKORO_VOICE") or "af_heart") if (os.getenv("TTS_PROVIDER") or "kokoro").strip().lower() == "kokoro" else narration.get("voice"),
        model=narration.get("model"),
    )
    with wave.open(str(path), "rb") as audio:
        seconds = audio.getnframes() / audio.getframerate()
    print(f"[narration] wrote {path} ({seconds:.2f}s)")
    if seconds > 88:
        print("[timing] Narration exceeds 88s; review pacing or shorten before final assembly.")
    else:
        target = max(60, round(seconds + 2, 2))
        total = sum(s["duration_seconds"] for s in storyboard["shots"])
        durations = [round(s["duration_seconds"] * target / total, 2) for s in storyboard["shots"]]
        durations[-1] = round(target - sum(durations[:-1]), 2)
        for shot, duration in zip(storyboard["shots"], durations):
            shot["duration_seconds"] = duration
        storyboard["target_duration_seconds"] = target
        storyboard["music"]["duration_seconds"] = target
        utils.save_json(storyboard, STORYBOARD_FILE)
        print(f"[timing] provisional proportional timeline: {target:.2f}s; review spoken cue alignment.")
    return path


def quality_profile(quality):
    return utils.load_json(utils.INPUT_DIR / 'config' / 'quality_profiles.json')[quality]


def video_job(storyboard, quality):
    profile = quality_profile(quality)
    shots = copy.deepcopy(storyboard['shots'])
    for shot in shots:
        shot.setdefault('video', {}).update({k: profile[k] for k in ('width', 'height', 'steps', 'frames', 'guidance')})
        motion = shot.get("motion_prompt") or (re.split(r"\bMotion:\s*", shot["prompt"], maxsplit=1, flags=re.I)[1] if re.search(r"\bMotion:\s*", shot["prompt"], flags=re.I) else "")
        shot["prompt"] = visual_prompt(shot) + " " + STYLE + (" Motion: " + motion if motion else "")
    return {'fps': 24, 'shots': shots, 'quality': quality}


def music_job(storyboard):
    music = dict(storyboard["music"])
    music.update(model="facebook/musicgen-small", seed=music.get("seed", 42))
    return {"music": music, "worker_version": 1}


def stage_package(storyboard, quality='draft'):
    keyframes = [
        OUTPUT_DIR / "keyframes" / f"{shot['id']}.png"
        for shot in storyboard["shots"]
    ]
    existing = [p for p in keyframes if p.is_file()]

    music_dir = exchange.package_job(
        "music", music_job(storyboard)
    )
    video_dir = exchange.package_job(
        "video",
        video_job(storyboard, quality),
        input_files=existing,
    )

    print(f"[package] music job -> {music_dir}")
    print(f"[package] video job -> {video_dir} "
          f"({len(existing)}/{len(keyframes)} keyframes)")
    print_handoff()
    return music_dir, video_dir


def stage_collect(storyboard=None, quality='draft'):
    copied = []
    if storyboard is not None:
        music_dir = exchange.package_job("music", music_job(storyboard))
        copied += exchange.collect_results(OUTPUT_DIR / "music", stage="music", job_id_filter=music_dir.name)
    if storyboard is not None:
        keyframes = [OUTPUT_DIR / "keyframes" / f"{s['id']}.png" for s in storyboard["shots"]]
        job_dir = exchange.package_job("video", video_job(storyboard, quality), [p for p in keyframes if p.is_file()])
        copied += exchange.collect_results(OUTPUT_DIR / "shots" / quality / job_dir.name, stage="video", job_id_filter=job_dir.name)
    if copied:
        for path in copied:
            print(f"[collect] {path}")
    else:
        print("[collect] nothing new in the exchange results folder")
    return copied


def export_sizes(quality):
    """Exact 16:9 and 9:16, with even dimensions for H.264."""
    short = quality_profile(quality)["export_height"]
    if short == 480:
        short = 486  # nearest even multiple of 9
    if short % 18:
        raise ValueError("Export short edge must be a multiple of 18")
    long = short * 16 // 9
    return {"horizontal": (long, short), "vertical": (short, long)}


def apply_edit_timing(storyboard):
    """Apply optional local shot-start anchors without modifying the storyboard."""
    path = utils.INPUT_DIR / "timing.json"
    if not path.is_file():
        return storyboard
    result = copy.deepcopy(storyboard)
    shots = result["shots"]
    anchors = utils.load_json(path)
    ids = [s["id"] for s in shots]
    if set(anchors) - set(ids):
        raise ValueError("Unknown shot in timing.json")
    total = sum(float(s["duration_seconds"]) for s in shots)
    points = {0: 0.0, len(shots): total}
    for key, value in anchors.items():
        points[ids.index(key)] = float(value)
    ordered = sorted(points.items())
    if ordered[0][1] != 0 or any(not (0 <= a < b <= total) for (_, a), (_, b) in zip(ordered, ordered[1:])):
        raise ValueError("Shot timing anchors must increase within film duration")
    for (i, start), (j, end) in zip(ordered, ordered[1:]):
        weight = sum(float(s["duration_seconds"]) for s in shots[i:j])
        elapsed = 0.0
        for k in range(i, j):
            duration = round((end-start)*float(shots[k]["duration_seconds"])/weight, 2) if k < j-1 else round(end-start-elapsed, 2)
            shots[k]["duration_seconds"] = duration
            elapsed += duration
    return result


def stage_assemble(storyboard, quality='draft'):
    from pipeline import assemble

    radio = assemble.build_radio_cut()
    print(f"[assemble] radio cut -> {radio}")

    keyframes = [OUTPUT_DIR / "keyframes" / f"{s['id']}.png" for s in storyboard["shots"]]
    job_dir = exchange.package_job("video", video_job(storyboard, quality), [p for p in keyframes if p.is_file()])
    storyboard = apply_edit_timing(storyboard)
    dest = OUTPUT_DIR / "final" / quality
    dest.mkdir(parents=True, exist_ok=True)
    for label, size in export_sizes(quality).items():
        final, fallbacks = assemble.assemble(storyboard, out_path=dest / f"{label}.mp4", size=size, shots_dir=OUTPUT_DIR / "shots" / quality / job_dir.name)
        print(f"[assemble] {label} {size[0]}x{size[1]} -> {final}")
        if fallbacks:
            print(f"[assemble] ffmpeg fallback used for: {', '.join(fallbacks)}")
    return final


def print_handoff():
    root = exchange.exchange_root()
    print(
        "\n================ GPU HANDOFF (Colab) ================\n"
        f"Exchange dir: {root}\n"
        "If it is not a Drive-synced folder, upload it to Google Drive\n"
        "as 'heritage-exchange' at My Drive root, then:\n"
        "  1. notebooks/musicgen.ipynb -> Runtime > Run all\n"
        "  2. notebooks/video_wan22.ipynb    -> Runtime > Run all\n"
        "  3. Let Drive sync results/ back locally\n"
        "Then:  python -m pipeline.run --resume\n"
        "(Details in COLAB.md)\n"
        "=====================================================\n"
    )


STAGES = [
    "story", "keyframes", "narration",
    "package", "collect", "assemble", "all",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, default="all")
    parser.add_argument(
        "--force", action="store_true",
        help="regenerate storyboard.json even if it exists",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="shortcut for collect + assemble after a Colab run",
    )
    parser.add_argument("--quality", choices=["draft", "final", "ultra"], default="draft")
    args = parser.parse_args(argv)

    utils.setup_directories()

    try:
        if args.resume or args.stage == "collect":
            storyboard = utils.load_storyboard()
            stage_collect(storyboard, args.quality)
            if args.resume:
                stage_assemble(storyboard, args.quality)
            return 0

        if args.stage == "assemble":
            stage_assemble(utils.load_storyboard(), args.quality)
            return 0

        if args.stage == "package":
            stage_package(utils.load_storyboard(), args.quality)
            return 0

        storyboard = stage_story(force=args.force)
        if args.stage == "story":
            return 0
        if args.stage == "narration":
            stage_narration(storyboard)
            return 0
        stage_keyframes(storyboard)
        if args.stage == "keyframes":
            return 0
        stage_narration(storyboard)
        if args.stage == "narration":
            return 0

        stage_package(storyboard, args.quality)

        if stage_collect(storyboard, args.quality):
            print("[all] results already present - assembling now")
            stage_assemble(storyboard, args.quality)
        # else: handoff instructions were printed by stage_package
        return 0
    except Exception as error:  # noqa: BLE001 - CLI surface: report, don't trace
        print(f"ERROR [{type(error).__name__}]: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
