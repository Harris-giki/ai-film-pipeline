"""Step 14 — beat-track the song and transcribe lyrics for landmarks."""
from __future__ import annotations

from pathlib import Path

from .common import save_json


def beats(proj: Path, song: Path, lyrics: bool = True) -> int:
    import librosa
    import numpy as np
    y, sr = librosa.load(str(song), sr=22050, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    bt = librosa.frames_to_time(frames, sr=sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    # crude downbeat estimate: the beat phase (0..3) with the strongest mean onset
    strengths = onset_env[frames] if len(frames) else np.array([])
    phase = int(np.argmax([strengths[i::4].mean() if len(strengths[i::4]) else 0 for i in range(4)])) if len(strengths) else 0
    downbeats = bt[phase::4]
    # energy curve for spotting the drop (largest rise in RMS over 2 s)
    rms = librosa.feature.rms(y=y)[0]
    rt = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    win = int(2 * sr / 512)
    rise = np.array([rms[i:i + win].mean() - rms[max(0, i - win):i].mean() if i > win else 0 for i in range(len(rms))])
    drop = float(rt[int(np.argmax(rise))]) if len(rise) else None
    data = {"song": str(song), "duration": float(len(y) / sr), "tempo": float(np.atleast_1d(tempo)[0]),
            "beats": [round(float(t), 3) for t in bt], "downbeats": [round(float(t), 3) for t in downbeats],
            "drop_guess": round(drop, 3) if drop else None, "lyrics": []}
    if lyrics:
        from .dailies import transcribe_file
        t = transcribe_file(song)
        data["lyrics"] = t["words"]
        data["lyric_lines"] = t["lines"]
        if t["words"]:
            data["first_lyric"] = t["words"][0]["s"]
    out = proj / "09_edit" / "beats.json"
    save_json(out, data)
    print(f"tempo {data['tempo']:.1f} BPM, {len(bt)} beats, drop ~{data['drop_guess']}s, "
          f"first lyric {data.get('first_lyric')}s -> {out}")
    print("Next: choose song offset so first lyric lands on the title card, and the end word to hard-stop on;"
          " write them into 09_edit/plan.json {'song_offset':..,'end_word_time':..,'title_at':..,'sections':[...]}")
    return 0
