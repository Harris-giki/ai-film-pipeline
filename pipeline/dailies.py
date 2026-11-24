"""Step 13 — transcribe every take (word timestamps), table it, weight folders, snap to silence."""
from __future__ import annotations

import os
import subprocess
import re
from pathlib import Path

from .common import duration, has_audio, load_json, run, save_json, takes

_MODEL = None


def whisper(model_size: str = None):
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(model_size or os.environ.get("WHISPER_MODEL", "small.en"),
                              device="cpu", compute_type="int8")
    return _MODEL


def load_audio_16k(path: Path):
    """Decode with ffmpeg (avoids faster-whisper's PyAV dependency/version clashes)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def transcribe_file(path: Path, vad: bool = True) -> dict:
    """vad=True for raw takes; vad=False for mixes, where VAD drops speech under music."""
    segs, _ = whisper().transcribe(load_audio_16k(path), word_timestamps=True, vad_filter=vad, beam_size=5,
                                   condition_on_previous_text=False)
    words, lines = [], []
    for s in segs:
        if s.no_speech_prob > 0.6 or s.avg_logprob < -1.0:   # whisper hallucinations on scene noise
            continue
        ws = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.probability, 3)}
              for w in (s.words or [])]
        words += ws
        if ws:
            lines.append({"text": s.text.strip(), "s": ws[0]["s"], "e": ws[-1]["e"]})
    return {"words": words, "lines": lines}


def silences(path: Path, noise_db: float = -35, min_d: float = 0.12) -> list[list[float]]:
    p = run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"silencedetect=n={noise_db}dB:d={min_d}",
             "-f", "null", "-"], capture=True, check=False)
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", p.stderr)]
    if len(ends) < len(starts):
        ends.append(duration(path))
    merged = []
    for a, b in zip(starts, ends):
        if merged and a - merged[-1][1] < 0.05:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [[round(a, 3), round(b, 3)] for a, b in merged]


def snap(t: float, sil: list[list[float]], side: str) -> float:
    """Snap an in point back / out point forward to the nearest silence (never cut into a word)."""
    inside = [(a, b) for a, b in sil if a - 0.02 <= t <= b + 0.02]
    if inside:  # model word stamp fell inside a silence: trust the audio energy
        a, b = inside[0]
        return round(max(a, b - 0.15, 0.0), 3) if side == "in" else round(min(b, a + 0.15), 3)
    if side == "in":
        before = [(a, b) for a, b in sil if b <= t + 0.02]
        if before:
            a, b = max(before, key=lambda x: x[1])
            if t - b < 0.6:
                return round(max(a, b - 0.15, 0.0), 3)
        return round(max(t - 0.05, 0.0), 3)
    after = [(a, b) for a, b in sil if a >= t - 0.02]
    if after:
        a, b = min(after, key=lambda x: x[0])
        if a - t < 0.6:
            return round(min(b, a + 0.15), 3)
    return round(t + 0.05, 3)


def transcribe(proj: Path, refs: bool = False) -> int:
    out_path = proj / "09_edit" / ("refs_transcripts.json" if refs else "transcripts.json")
    data = load_json(out_path, {})
    files = sorted((proj / "01_refs").glob("*.*")) if refs else takes(proj)
    for f in files:
        key = f.stem
        if key in data and data[key].get("mtime") == f.stat().st_mtime:
            continue
        if not has_audio(f):
            data[key] = {"file": str(f), "mtime": f.stat().st_mtime, "words": [], "lines": [], "silences": [], "duration": duration(f)}
            continue
        print(f"transcribing {f.name} ...", flush=True)
        t = transcribe_file(f)
        t.update({"file": str(f), "mtime": f.stat().st_mtime, "silences": silences(f), "duration": duration(f)})
        data[key] = t
    # drop entries for clips that became rejects
    live = {f.stem for f in files}
    data = {k: v for k, v in data.items() if k in live}
    save_json(out_path, data)
    print(f"wrote {out_path} ({len(data)} clips)")
    return 0


def table(proj: Path, older_penalty: float = 0.2, primary: list[str] | None = None) -> int:
    tr = load_json(proj / "09_edit" / "transcripts.json")
    scenes = {s["id"]: s for s in load_json(proj / "03_scenes" / "scenes.json", [])}
    # folder weighting (generation batches): newest / primary batch first, older batches 15-25% lower.
    # Takes stored as 08_takes/<SCENE>/<file> are one batch; 08_takes/<batch>/<file> or
    # 08_takes/<SCENE>/<batch>/<file> make batches. Override with 09_edit/folder_weights.json.
    sids = set(scenes)
    batches = sorted({Path(v["file"]).parent for v in tr.values() if Path(v["file"]).parent.name not in sids},
                     key=lambda p: p.stat().st_mtime, reverse=True)
    weight = {fo: (1.0 if i == 0 or (primary and fo.name in primary) else 1.0 - older_penalty) for i, fo in enumerate(batches)}
    for name, w in load_json(proj / "09_edit" / "folder_weights.json", {}).items():
        for fo in list(weight) + [Path(v["file"]).parent for v in tr.values()]:
            if fo.name == name:
                weight[fo] = w
    rows = ["| Clip | Line | Speakers | Usable in | Usable out | Silent action ranges | Score |",
            "|------|------|----------|-----------|------------|----------------------|-------|"]
    for clip, v in sorted(tr.items()):
        sid = clip.split("_")[0]
        pair = "+".join(scenes.get(sid, {}).get("speaking", [])) or "-"
        w = weight.get(Path(v["file"]).parent, 1.0)
        sil = v.get("silences", [])
        long_sil = [f"{a:.2f}-{b:.2f}" for a, b in sil if b - a >= 1.0]
        if not v["lines"]:
            rows.append(f"| {clip} | (no dialogue) | {pair} | 0.00 | {v['duration']:.2f} | {', '.join(long_sil) or 'all'} | {w:.2f} |")
        for ln in v["lines"]:
            conf = sum(x["p"] for x in v["words"] if ln["s"] <= x["s"] <= ln["e"]) / max(1, len([x for x in v["words"] if ln["s"] <= x["s"] <= ln["e"]]))
            cut_off = ln["e"] > v["duration"] - 0.15
            score = w * conf * (0.5 if cut_off else 1.0)
            flag = " ⚠ line runs to clip end: extend the take, never trim a word" if cut_off else ""
            rows.append(f"| {clip} | {ln['text']}{flag} | {pair} | {snap(ln['s'], sil, 'in'):.2f} | "
                        f"{snap(ln['e'], sil, 'out'):.2f} | {', '.join(long_sil) or '-'} | {score:.2f} |")
    out = proj / "09_edit" / "dailies.md"
    out.write_text("# Dailies\n\nFolder weights: " +
                   (", ".join(f"{f.name}={w:.2f}" for f, w in weight.items()) or "single batch (all 1.00)") + "\n\n" + "\n".join(rows) +
                   "\n\n## Unused clips and why\n\n(dailies agent fills this in)\n")
    print(f"wrote {out}")
    return 0
