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
    # Move the intact foreground inside a safe margin; animate the backdrop
    # independently for a subtle layered-motion effect.
    index = Path(keyframe).stem.split("_")[1] if "_" in Path(keyframe).stem else ""
    styles = {
        "01": (0.88, 0.98, 0, 0), "02": (0.98, 0.88, 0, 0),
        "03": (0.91, 0.91, 0.035, 0), "04": (0.96, 0.96, 0, 0),
        "05": (0.88, 0.98, 0, 0), "06": (0.90, 0.94, 0, -0.025),
        "07": (0.88, 0.98, 0, 0), "08": (0.90, 0.94, 0, -0.025),
        "09": (0.98, 0.88, 0, 0), "10": (0.94, 0.97, 0, 0),
    }
    start, end, dx, dy = styles.get(index, (0.90, 0.98, 0, 0))
    progress = f"min(t/{max(duration, 0.04)},1)"
    ease = f"(0.5-0.5*cos(PI*{progress}))"
    factor = f"({start}+({end-start})*{ease})"
    short = min(width, height)
    grade = "eq=brightness=-0.035:saturation=0.88," if index in ("02", "04") else ("eq=saturation=1.08:brightness=0.015," if index in ("08", "09", "10") else "")
    vf = (
        f"[0:v]split[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=24,eq=brightness=-0.12[back];"
        f"[fg]scale={short}:{short}:force_original_aspect_ratio=decrease,"
        f"scale=w='trunc(iw*{factor}/2)*2':h='trunc(ih*{factor}/2)*2':eval=frame,"
        f"{grade}setsar=1[front];"
        f"[back][front]overlay=x='(W-w)/2+{dx}*W*(2*{ease}-1)':"
        f"y='(H-h)/2+{dy}*H*(2*{ease}-1)':eval=frame,"
        f"setsar=1,format=yuv420p"
    )
    if index == "10":
        vf += f",fade=t=out:st={max(0,duration-0.8)}:d=0.8"
    _run([
        "ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(keyframe),
        "-filter_complex_threads", "1", "-filter_complex", vf, "-frames:v", str(frames),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return Path(out_path)


def build_still_clip(keyframe, dest, duration, size, fps):
    w,h = size
    vf = (f"[0:v]split[b][f];[b]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=24,eq=brightness=-0.15[bg];"
          f"[f]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p")
    _run(["ffmpeg","-y","-loop","1","-framerate",str(fps),"-i",str(keyframe),"-filter_complex_threads","1","-filter_complex",vf,"-t",str(duration),"-c:v","libx264",str(dest)])


def build_degree_clip(dest, duration, size, fps):
    import math
    w,h = size
    # Two rays separated by exactly one degree; reveal along their length.
    x,y = int(w*.12), int(h*.5)
    length = int(w*.76)
    slope = math.tan(math.radians(1))
    vf = (f"geq=r='if(between(X,{x},{x}+{length}*min(T/{duration}*2,1))*lt(abs(Y-{y}),2),230,if(between(X,{x},{x}+{length}*min(T/{duration}*2,1))*lt(abs(Y-{y}+(X-{x})*{slope}),2),255,15))':"
          f"g='if(lt(abs(Y-{y}),2)*between(X,{x},{x}+{length}*min(T/{duration}*2,1)),230,if(lt(abs(Y-{y}+(X-{x})*{slope}),2)*between(X,{x},{x}+{length}*min(T/{duration}*2,1)),180,20))':"
          f"b='if(lt(abs(Y-{y}),2)*between(X,{x},{x}+{length}*min(T/{duration}*2,1)),230,30)',format=yuv420p")
    _run(["ffmpeg","-y","-f","lavfi","-i",f"color=c=black:s={w}x{h}:r={fps}","-vf",vf,"-t",str(duration),"-c:v","libx264",str(dest)])


def normalize_clip(src, dest, duration, size=SIZE, fps=FPS):
    """Re-encode a generated clip to exact duration/size/fps.

    Shorter clips are padded by cloning the last frame; longer ones are cut.
    """
    _require_ffmpeg()
    width, height = size
    import re
    probe = subprocess.run([_require_ffmpeg(), "-i", str(src)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
    source_duration = sum(float(v)*m for v,m in zip(match.groups(),(3600,60,1))) if match else duration
    stretch = max(1, duration / max(source_duration, 0.04))
    vf = (
        f"setpts={stretch}*PTS,minterpolate=fps={fps}:mi_mode=mci,"
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

        index = shot_id.split("_")[1] if "_" in shot_id else ""
        hybrid = shots_dir is not None and Path(shots_dir).parent.name == "final"
        if hybrid and index == "05":
            build_degree_clip(dest, duration, size, fps)
            log_run(stage="assemble", model="procedural-degree", parameters={"duration": duration}, latency=0, status="success", shot_id=shot_id)
        elif hybrid and index in {"03","04","07","10"}:
            build_still_clip(OUTPUT_DIR / "keyframes" / f"{shot_id}.png", dest, duration, size, fps)
            log_run(stage="assemble", model="intentional-still", parameters={"duration": duration}, latency=0, status="success", shot_id=shot_id)
        elif generated.is_file() and generated.stat().st_size > 0:
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
                model="ffmpeg-fit-blur",
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
            "[1:a]asplit=2[voice][control];[2:a]volume=0.30[bed];[bed][control]sidechaincompress=threshold=0.025:ratio=6:attack=20:release=400[duck];[voice][duck]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]"
        )
        audio_map = "[a]"
    elif narration.is_file():
        cmd += ["-i", str(narration)]
        audio_map = "1:a"
    elif music.is_file():
        cmd += ["-i", str(music)]
        audio_map = "1:a"

    cmd += ["-map", "0:v", "-t", str(sum(float(s["duration_seconds"]) for s in storyboard["shots"]))]
    if filter_complex:
        cmd += ["-filter_complex", filter_complex]
    if audio_map:
        cmd += ["-map", audio_map, "-c:a", "aac"]
    # Optional locally authored text overlays, including timed subtitles/end card.
    subtitles = OUTPUT_DIR / "narration" / "subtitles.srt"
    if subtitles.is_file():
        # Fixed relative path avoids escaping arbitrary user directory names.
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            local_srt = Path(temp) / "captions.srt"
            shutil.copyfile(subtitles, local_srt)
            escaped = str(local_srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            cmd += ["-vf", f"subtitles='{escaped}'", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
            _run(cmd + [str(final)])
        return final, fallbacks
    cmd += ["-c:v", "copy", str(final)]

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
