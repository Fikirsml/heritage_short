import pytest

from pipeline import assemble


class _Proc:
    returncode = 0
    stderr = ""


def _fake_ffmpeg(monkeypatch, calls):
    monkeypatch.setattr(assemble.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    def run(cmd, **kwargs):
        calls.append(cmd)
        return _Proc()

    monkeypatch.setattr(assemble.subprocess, "run", run)


def test_concat_file(tmp_path):
    clips = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    path = assemble._write_concat_file(clips, tmp_path / "concat.txt")
    assert path.read_text().splitlines() == [
        f"file '{clips[0]}'",
        f"file '{clips[1]}'",
    ]


def test_fallback_clip_invokes_zoompan(monkeypatch, tmp_path):
    calls = []
    _fake_ffmpeg(monkeypatch, calls)
    keyframe = tmp_path / "k.png"
    keyframe.write_bytes(b"img")

    assemble.build_fallback_clip(keyframe, tmp_path / "c.mp4", 5)

    cmd = " ".join(calls[0])
    assert "zoompan" in cmd
    assert calls[0][calls[0].index("-t") + 1] == "5"


def test_normalize_clip_pads_to_duration(monkeypatch, tmp_path):
    calls = []
    _fake_ffmpeg(monkeypatch, calls)
    src = tmp_path / "in.mp4"
    src.write_bytes(b"vid")

    assemble.normalize_clip(src, tmp_path / "out.mp4", 7)

    cmd = " ".join(calls[0])
    assert "tpad=stop=-1:stop_mode=clone" in cmd
    assert calls[0][calls[0].index("-t") + 1] == "7"


def test_assemble_missing_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(assemble, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(assemble.shutil, "which", lambda name: "x")
    storyboard = {"shots": [
        {"id": "shot_01", "prompt": "x", "duration_seconds": 4}
    ]}
    with pytest.raises(FileNotFoundError):
        assemble.assemble(storyboard)


def test_radio_cut_requires_narration(monkeypatch, tmp_path):
    monkeypatch.setattr(assemble.shutil, "which", lambda name: "x")
    with pytest.raises(FileNotFoundError):
        assemble.build_radio_cut(narration=tmp_path / "missing.wav")


def test_require_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(assemble.shutil, "which", lambda name: None)
    import imageio_ffmpeg
    def missing():
        raise RuntimeError("missing")
    monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", missing)
    with pytest.raises(RuntimeError, match="(?i)ffmpeg"):
        assemble._require_ffmpeg()


def test_require_ffmpeg_bundled(monkeypatch):
    import imageio_ffmpeg
    monkeypatch.setattr(assemble.shutil, "which", lambda name: None)
    monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/bundled/ffmpeg")
    assert assemble._require_ffmpeg() == "/bundled/ffmpeg"
