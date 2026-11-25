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
import sys

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


def stage_keyframes(storyboard):
    from pipeline.cloudflare_client import generate_image

    made = []
    for shot in storyboard["shots"]:
        out = OUTPUT_DIR / "keyframes" / f"{shot['id']}.png"
        if out.is_file() and out.stat().st_size > 0:
            print(f"[keyframes] {shot['id']}: cached")
        else:
            generate_image(shot["prompt"], out_path=out)
            print(f"[keyframes] {shot['id']}: generated")
        made.append(out)
    return made


def stage_narration(storyboard):
    from pipeline import tts

    narration = storyboard["narration"]
    path = tts.generate_narration(
        narration["script"],
        voice=narration.get("voice"),
        model=narration.get("model"),
    )
    print(f"[narration] wrote {path}")
    return path


def stage_package(storyboard):
    keyframes = [
        OUTPUT_DIR / "keyframes" / f"{shot['id']}.png"
        for shot in storyboard["shots"]
    ]
    existing = [p for p in keyframes if p.is_file()]

    music_dir = exchange.package_job(
        "music", {"music": storyboard["music"]}
    )
    video_dir = exchange.package_job(
        "video",
        {"fps": 24, "shots": storyboard["shots"]},
        input_files=existing,
    )

    print(f"[package] music job -> {music_dir}")
    print(f"[package] video job -> {video_dir} "
          f"({len(existing)}/{len(keyframes)} keyframes)")
    print_handoff()
    return music_dir, video_dir


def stage_collect(storyboard=None):
    copied = []
    copied += exchange.collect_results(OUTPUT_DIR / "music", stage="music")
    copied += exchange.collect_results(OUTPUT_DIR / "shots", stage="video")
    if copied:
        for path in copied:
            print(f"[collect] {path}")
    else:
        print("[collect] nothing new in the exchange results folder")
    return copied


def stage_assemble(storyboard):
    from pipeline import assemble

    radio = assemble.build_radio_cut()
    print(f"[assemble] radio cut -> {radio}")

    final, fallbacks = assemble.assemble(storyboard)
    print(f"[assemble] final video -> {final}")
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
        "  1. notebooks/music_ace_step.ipynb -> Runtime > Run all\n"
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
    args = parser.parse_args(argv)

    utils.setup_directories()

    try:
        if args.resume or args.stage == "collect":
            storyboard = utils.load_storyboard()
            stage_collect(storyboard)
            if args.resume:
                stage_assemble(storyboard)
            return 0

        if args.stage == "assemble":
            stage_assemble(utils.load_storyboard())
            return 0

        if args.stage == "package":
            stage_package(utils.load_storyboard())
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

        stage_package(storyboard)

        if stage_collect(storyboard):
            print("[all] results already present - assembling now")
            stage_assemble(storyboard)
        # else: handoff instructions were printed by stage_package
        return 0
    except Exception as error:  # noqa: BLE001 - CLI surface: report, don't trace
        print(f"ERROR [{type(error).__name__}]: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
