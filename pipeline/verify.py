"""Steps 15 + 24 — verify a render by machine and say what was not checked."""
from __future__ import annotations

import difflib
import re
import shutil
from pathlib import Path

from .board import board_path, length
from .common import FPS, H, W, duration, ffmpeg, has_audio, load_json, probe, run, save_json


def loudness(path: Path) -> dict:
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-filter_complex", "ebur128=peak=true",
             "-f", "null", "-"], capture=True, check=False)
    tail = p.stderr[p.stderr.rfind("Summary:"):]
    I = re.search(r"I:\s+(-?[0-9.]+) LUFS", tail)
    TP = re.search(r"Peak:\s+(-?[0-9.]+|-inf) dBFS", tail)
    return {"I": float(I.group(1)) if I else None, "TP": float(TP.group(1)) if TP and TP.group(1) != "-inf" else None}


def frame_count(path: Path) -> int:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
               "stream=nb_read_packets", "-of", "csv=p=0", path], capture=True).stdout.strip()
    return int(out.split(",")[0]) if out else 0


def planned_lines(proj: Path) -> list[str]:
    board = load_json(board_path(proj))
    tr = load_json(proj / "09_edit" / "transcripts.json", {})
    out = []
    for it in sorted(board["items"], key=lambda i: i["t"]):
        if it.get("noa") or it.get("mute"):
            continue
        ws = [w["w"] for w in tr.get(it["clip"], {}).get("words", []) if w["e"] > it["ain"] + 0.05 and w["s"] < it["aout"] - 0.05]
        if ws:
            out.append(" ".join(ws))
    return out


def norm(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()


def verify(proj: Path, path: Path, final: bool = False) -> int:
    rep = {"file": str(path)}
    info = probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    rep["video"] = {"codec": v["codec_name"], "w": v["width"], "h": v["height"], "fps": v["r_frame_rate"],
                    "frames": frame_count(path), "duration": round(duration(path), 3)}
    try:
        expected = round(length(load_json(board_path(proj))) * FPS)
        rep["video"]["expected_frames"] = expected
    except SystemExit:
        expected = None
    if has_audio(path):
        rep["loudness"] = loudness(path)
        # transcript of the mix vs the planned lines
        from .dailies import transcribe_file
        heard = transcribe_file(path, vad=False)
        plan = " ".join(planned_lines(proj))
        a, b = norm(plan), norm(" ".join(w["w"] for w in heard["words"]))
        sm = difflib.SequenceMatcher(a=a, b=b)
        missing = [" ".join(a[i1:i2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op in ("delete", "replace")]
        extra = [" ".join(b[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op in ("insert", "replace")]
        rep["transcript"] = {"match_ratio": round(sm.ratio(), 3), "missing_from_mix": missing, "unexpected_in_mix": extra}
    # frame sheet: intro / body / outro
    dur = duration(path)
    sheet = path.with_name(path.stem + "_frames.jpg")
    n = 12
    ffmpeg("-i", path, "-vf", f"fps={n / max(dur, 0.1):.5f},scale=480:-1,tile=4x3", "-frames:v", "1", "-q:v", "3", sheet)
    rep["frame_sheet"] = str(sheet)
    problems = []
    if expected and abs(rep["video"]["frames"] - expected) > 1:
        problems.append(f"frame count {rep['video']['frames']} != expected {expected}")
    if final:
        if (v["width"], v["height"]) != (W, H):
            problems.append("not 1920x1080")
        if v["r_frame_rate"] != f"{FPS}/1":
            problems.append(f"fps {v['r_frame_rate']} != 24")
        L = rep.get("loudness", {})
        if L.get("I") is not None and abs(L["I"] + 14) > 0.5:
            problems.append(f"integrated {L['I']} LUFS (target -14)")
        if L.get("TP") is not None and L["TP"] > -1.0:
            problems.append(f"true peak {L['TP']} dBTP > -1")
    if final:
        from .lookstats import measure
        from .style import load as load_style
        tgt = load_style(proj)["target_metrics"]
        lk = measure(path)
        rep["look"] = {"measured": lk, "target": tgt}
        if lk["black_point"] > tgt["black_point"] + 0.03:
            problems.append(f"milky blacks: black point {lk['black_point']} vs target {tgt['black_point']} (fp lookmatch --apply)")
        if lk["saturation"] < tgt["saturation"] * 0.75:
            problems.append(f"washed-out colour: saturation {lk['saturation']} vs target {tgt['saturation']} (fp lookmatch --apply)")
    rep["problems"] = problems
    rep["not_checked"] = ["Nobody watched the full picture in real time; only the 12-frame sheet was sampled.",
                          "No human listened; speech was checked by ASR only, music/FX balance not judged."]
    save_json(path.with_name(path.stem + "_verify.json"), rep)
    print(f"VIDEO   {rep['video']}")
    if "loudness" in rep:
        print(f"LOUD    {rep['loudness']['I']} LUFS, TP {rep['loudness']['TP']} dBTP")
        t = rep["transcript"]
        print(f"SPEECH  match {t['match_ratio']}; missing: {t['missing_from_mix'][:8]}; unexpected: {t['unexpected_in_mix'][:8]}")
    print(f"FRAMES  {sheet}")
    if "look" in rep:
        m, t = rep["look"]["measured"], rep["look"]["target"]
        print("LOOK    " + ", ".join(f"{k} {m[k]} (target {t[k]})" for k in t if k in m))
    for p in problems:
        print(f"PROBLEM {p}")
    for nc in rep["not_checked"]:
        print(f"NOT CHECKED {nc}")
    return 1 if problems else 0
