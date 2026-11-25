"""Assemble the final film with ffmpeg.

Concatenates per-shot clips, then mixes narration and music on top.
Fallback: any shot without a generated .mp4 gets a Ken Burns zoompan
clip built from its keyframe, so a failed or slow GPU video stage still
produces a complete video.
"""

import shutil
import subprocess
from pathlib import Path

from pipeline.utils import OUTPUT_DIR, log_run

FPS = 24
SIZE = (480, 480)


def _require_ffmpeg():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError) as exc:
        raise RuntimeError("FFmpeg unavailable; install imageio-ffmpeg from requirements.txt") from exc


def _run(cmd):
    if cmd[0] == "ffmpeg":
        cmd = [_require_ffmpeg(), *cmd[1:]]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed ({' '.join(cmd[:3])}...): {proc.stderr[-400:]}"
        )
    return proc


def _write_concat_file(clips, path):
    path = Path(path)
    path.write_text(
        "".join(f"file '{clip}'\n" for clip in clips), encoding="utf-8"
    )
    return path


def build_fallback_clip(keyframe, out_path, duration, size=SIZE, fps=FPS):
    """Ken Burns pan/zoom clip from a still image (GPU-video fallback)."""
    _require_ffmpeg()
    width, height = size
    frames = max(1, round(duration * fps))
    vf = (
        f"scale={width * 4}:{height * 4}:force_original_aspect_ratio=increase,crop={width * 4}:{height * 4},"
        "zoompan=z='min(1.0+0.0008*on,1.2)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={width}x{height}:fps={fps},setsar=1,format=yuv420p"
    )
    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(keyframe),
        "-vf", vf, "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return Path(out_path)


def normalize_clip(src, dest, duration, size=SIZE, fps=FPS):
    """Re-encode a generated clip to exact duration/size/fps.

    Shorter clips are padded by cloning the last frame; longer ones are cut.
    """
    _require_ffmpeg()
    width, height = size
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},"
        "tpad=stop=-1:stop_mode=clone,format=yuv420p"
    )
    _run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", vf, "-t", str(duration),
        "-c:v", "libx264", "-an",
        str(dest),
    ])
    return Path(dest)


def assemble(storyboard, out_path=None, size=SIZE, fps=FPS, shots_dir=None):
    """Build the final mp4. Returns (final_path, fallback_shot_ids)."""
    _require_ffmpeg()
    final = Path(out_path) if out_path else OUTPUT_DIR / "final" / "heritage_short.mp4"
    work = final.parent / "_work" / final.stem
    work.mkdir(parents=True, exist_ok=True)

    clips, fallbacks = [], []
    for shot in storyboard["shots"]:
        shot_id = shot["id"]
        duration = float(shot["duration_seconds"])
        dest = work / f"{shot_id}.mp4"
        generated = (Path(shots_dir) if shots_dir is not None else OUTPUT_DIR / "shots") / f"{shot_id}.mp4"

        if generated.is_file() and generated.stat().st_size > 0:
            normalize_clip(generated, dest, duration, size, fps)
        else:
            keyframe = OUTPUT_DIR / "keyframes" / f"{shot_id}.png"
            if not keyframe.is_file():
                raise FileNotFoundError(
                    f"{shot_id}: no video clip and no keyframe at {keyframe}"
                )
            build_fallback_clip(keyframe, dest, duration, size, fps)
            fallbacks.append(shot_id)
            log_run(
                stage="assemble",
                model="ffmpeg-zoompan",
                parameters={"reason": "missing video clip", "duration": duration},
                latency=0,
                status="fallback",
                shot_id=shot_id,
            )
        clips.append(dest)

    concat = _write_concat_file(clips, work / "concat.txt")
    video = work / "video_only.mp4"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video),
    ])

    narration = OUTPUT_DIR / "narration" / "narration.wav"
    music = OUTPUT_DIR / "music" / "music.wav"

    cmd = ["ffmpeg", "-y", "-i", str(video)]
    filter_complex, audio_map = None, None
    if narration.is_file() and music.is_file():
        cmd += ["-i", str(narration), "-i", str(music)]
        filter_complex = (
            "[1:a][2:a]amix=inputs=2:duration=longest"
            ":weights='1 0.3'[a]"
        )
        audio_map = "[a]"
    elif narration.is_file():
        cmd += ["-i", str(narration)]
        audio_map = "1:a"
    elif music.is_file():
        cmd += ["-i", str(music)]
        audio_map = "1:a"

    cmd += ["-map", "0:v"]
    if filter_complex:
        cmd += ["-filter_complex", filter_complex]
    if audio_map:
        cmd += ["-map", audio_map, "-c:a", "aac"]
    cmd += ["-c:v", "copy", "-shortest", str(final)]

    _run(cmd)
    return final, fallbacks


def build_radio_cut(narration=None, music=None, out_path=None):
    """Audio-first cut: narration over ducked music -> outputs/radio_cut/."""
    _require_ffmpeg()
    narration = Path(narration) if narration else OUTPUT_DIR / "narration" / "narration.wav"
    music = Path(music) if music else OUTPUT_DIR / "music" / "music.wav"
    out_path = Path(out_path) if out_path else OUTPUT_DIR / "radio_cut" / "radio_cut.m4a"

    if not narration.is_file():
        raise FileNotFoundError(f"narration wav missing: {narration}")

    if music.is_file():
        _run([
            "ffmpeg", "-y",
            "-i", str(narration), "-i", str(music),
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=longest:weights='1 0.35'[a]",
            "-map", "[a]", "-c:a", "aac", "-shortest",
            str(out_path),
        ])
    else:
        _run([
            "ffmpeg", "-y", "-i", str(narration),
            "-c:a", "aac", str(out_path),
        ])
    return out_path
