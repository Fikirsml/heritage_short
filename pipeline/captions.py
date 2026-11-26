"""Local word-weighted captions; approximate timing, not forced alignment."""
import re
import wave
from pipeline.utils import INPUT_DIR, OUTPUT_DIR

def stamp(seconds):
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def generate():
    folder = OUTPUT_DIR / "narration"
    with wave.open(str(folder / "narration.wav"), "rb") as wav:
        duration = wav.getnframes() / wav.getframerate()
    text = (INPUT_DIR / "narration.txt").read_text().strip()
    words = text.split()
    if not words:
        raise ValueError("Empty narration")
    chunks = []
    current = []
    for word in words:
        current.append(word)
        if len(current) >= 9 or (len(current) >= 4 and re.search(r'[.!?]$', word)):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    weights = [sum(len(w)+2 for w in c) for c in chunks]
    total = sum(weights)
    start = 0
    blocks = []
    for i, (chunk, weight) in enumerate(zip(chunks, weights), 1):
        end = start + duration * weight / total
        blocks.append(f"{i}\n{stamp(start)} --> {stamp(end)}\n{' '.join(chunk)}")
        start = end
    blocks.append(f"{len(blocks)+1}\n{stamp(duration)} --> {stamp(min(90,duration+2))}\nAI-assisted visuals, voice and music")
    path = folder / "subtitles.srt"
    path.write_text("\n\n".join(blocks)+"\n", encoding="utf-8")
    print("[captions] approximate timing; review against narration")
    return path
