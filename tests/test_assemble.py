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


def test_fallback_clip_preserves_centered_image(monkeypatch, tmp_path):
    calls = []
    _fake_ffmpeg(monkeypatch, calls)
    keyframe = tmp_path / "k.png"
    keyframe.write_bytes(b"img")

    assemble.build_fallback_clip(keyframe, tmp_path / "c.mp4", 5)

    cmd = " ".join(calls[0])
    assert "overlay=(W-w)/2:(H-h)/2" in cmd and "gblur" in cmd
    assert "zoompan" not in cmd and "eval=frame" not in cmd
    assert calls[0][calls[0].index("-frames:v") + 1] == "120"


def test_normalize_clip_pads_to_duration(monkeypatch, tmp_path):
    calls = []
    _fake_ffmpeg(monkeypatch, calls)
    src = tmp_path / "in.mp4"
    src.write_bytes(b"vid")

    assemble.normalize_clip(src, tmp_path / "out.mp4", 7)

    cmd = " ".join(calls[-1])
    assert "minterpolate" in cmd
    assert "tpad=stop=-1:stop_mode=clone" in cmd
    assert calls[-1][calls[-1].index("-t") + 1] == "7"


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


@pytest.mark.parametrize("size", [(1280, 720), (720, 1280)])
def test_editorial_titles(size):
    ass = assemble.title_ass(size, 89.33)
    assert "ONE DEGREE" in ass
    assert "AI-GENERATED CONTENT" in ass
    assert "0:01:27.33,0:01:29.33,Closing" in ass
    assert f"PlayResX: {size[0]}" in ass
    assert r"\fad(250,250)" in ass


def test_editorial_keyframe_precedence(monkeypatch, tmp_path):
    monkeypatch.setattr(assemble, "OUTPUT_DIR", tmp_path)
    original = tmp_path / "keyframes" / "shot_03.png"
    revised = tmp_path / "keyframes_polished" / "shot_03.png"
    assert assemble.editorial_keyframe("shot_03") == original
    revised.parent.mkdir()
    revised.write_bytes(b"image")
    assert assemble.editorial_keyframe("shot_03") == revised
