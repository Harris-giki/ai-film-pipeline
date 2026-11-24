"""Steps 22-23 — three-layer sound: stems, echo fix, mix, loudness."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .board import a_span, board_path, length
from .common import FPS, clip_path, ffmpeg, has_audio, load_json, run, save_json

XF = 4 / FPS          # 4-frame constant-power crossfade
TAIL_MAX = 0.5
SCENE_UNDER_DB = -12.0
DIP_DB = -4.6
DIP_LO, DIP_HI = 350, 4500
DIP_DOWN, DIP_UP = 0.8, 1.2
TARGET_LUFS, TARGET_TP = -14.0, -1.0
SPEECH_REF = -20.0       # dialogue reference level before mastering (LUFS)
MUSIC_UNDER_DB = -10.0   # music bed under dialogue, relative to speech
MUSIC_OPEN_DB = -2.0     # music between lines / montage, relative to speech


def montage_ranges(board: dict) -> list[tuple[float, float]]:
    return [(s["start"], s["end"]) for s in board.get("sections", []) if s.get("name", "").lower().startswith("montage")]


def in_ranges(t: float, rs) -> bool:
    return any(a <= t < b for a, b in rs)


def dialogue_lines(proj: Path, board: dict) -> list[tuple[float, float, dict]]:
    tr = load_json(proj / "09_edit" / "transcripts.json", {})
    mont = montage_ranges(board)
    out = []
    for it in board["items"]:
        if it.get("noa") or it.get("mute"):
            continue
        off = a_span(it)[0] - it["ain"]
        for ln in tr.get(it["clip"], {}).get("lines", []):
            if ln["e"] > it["ain"] + 0.05 and ln["s"] < it["aout"] - 0.05:
                s, e = max(ln["s"], it["ain"]) + off, min(ln["e"], it["aout"]) + off
                if in_ranges(s, mont) and it.get("tag") != "pink":
                    continue
                out.append((s, e, it))
    return sorted(out, key=lambda x: x[0])


def dialogue_segments(lines, gap: float = 1.5) -> list[tuple[float, float]]:
    """Whole dialogue segments (lines closer than `gap` merge) — music dips per segment, never per line."""
    segs = []
    for s, e, _ in lines:
        if segs and s - segs[-1][1] < gap:
            segs[-1][1] = max(segs[-1][1], e)
        else:
            segs.append([s, e])
    return [tuple(x) for x in segs]


def env_expr(ranges, down: float, up: float) -> str:
    """0..1 envelope: ramps up over `down` before each range, holds, ramps out over `up` after."""
    if not ranges:
        return "0"
    terms = [f"clip((t-{a - down:.3f})/{down},0,1)*clip(({b + up:.3f}-t)/{up},0,1)" for a, b in ranges]
    e = terms[0]
    for t in terms[1:]:
        e = f"max({e},{t})"
    return e


def _tail(clip: Path, aout: float) -> float:
    """Extend up to 0.5 s where a loud sound is cut off at the out point."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{max(aout - 0.05, 0):.3f}", "-t", "0.05", "-i", str(clip),
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    if len(x) == 0:
        return 0.0
    level = 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)
    return TAIL_MAX if level > -30 else 0.0


def stems(proj: Path) -> int:
    board = load_json(board_path(proj))
    out = proj / "11_sound"
    out.mkdir(parents=True, exist_ok=True)
    total = length(board)
    lines = dialogue_lines(proj, board)
    mont = montage_ranges(board)
    items = [i for i in board["items"] if not i.get("noa") and not i.get("mute") and has_audio(clip_path(proj, i["clip"]))]
    if not items:
        print("no clip audio on the board")
        return 1
    args, sc, dl = [], [], []
    for k, it in enumerate(items):
        clip = clip_path(proj, it["clip"])
        args += ["-i", clip]
        start = max(a_span(it)[0], 0)
        tail = _tail(clip, it["aout"])
        d = it["aout"] - it["ain"] + tail
        base = (f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim={it['ain']:.4f}:{it['ain'] + d:.4f},"
                f"asetpts=PTS-STARTPTS,afade=t=in:d={XF:.4f}:curve=qsin,"
                f"afade=t=out:st={max(d - (tail or XF), 0):.4f}:d={(tail or XF):.4f}:curve=qsin,"
                f"adelay={int(start * 1000)}:all=1,asplit[s{k}][d{k}]")
        sc.append(base)
        # dialogue stem: this item's line ranges only (energy gate by time)
        mine = [(s, e) for s, e, i in lines if i is it]
        gate = "+".join(f"between(t,{s - 0.08:.3f},{e + 0.12:.3f})" for s, e in mine) or "0"
        sc.append(f"[d{k}]volume='if({gate},1,0)':eval=frame[dd{k}]")
        dl.append(k)
    n = len(items)
    # adelay shifts timestamps; never atrim before amix. Mix over silent full-length beds instead.
    args += ["-f", "lavfi", "-t", f"{total:.4f}", "-i", "anullsrc=r=48000:cl=stereo",
             "-f", "lavfi", "-t", f"{total:.4f}", "-i", "anullsrc=r=48000:cl=stereo"]
    bed_s, bed_d = n, n + 1
    seg = dialogue_segments(lines)
    speech = env_expr(seg, 0.1, 0.1)
    # scene stem: full in montage, ~12 dB under speech elsewhere (only while speech plays)
    mont_e = "+".join(f"between(t,{a},{b})" for a, b in mont) or "0"
    g = 10 ** (SCENE_UNDER_DB / 20)
    sc.append(f"[{bed_s}:a]" + "".join(f"[s{k}]" for k in range(n)) + f"amix=inputs={n + 1}:normalize=0:duration=first,"
              f"volume='if({mont_e},1,1-(1-{g:.4f})*({speech}))':eval=frame[scene]")
    sc.append(f"[{bed_d}:a]" + "".join(f"[dd{k}]" for k in dl) + f"amix=inputs={len(dl) + 1}:normalize=0:duration=first[dia]")
    script = out / "stems.filter"
    script.write_text(";\n".join(sc))
    ffmpeg(*args, "-filter_complex_script", script, "-map", "[scene]", "-c:a", "pcm_s24le", out / "scene.wav",
           "-map", "[dia]", "-c:a", "pcm_s24le", out / "dialogue.wav")
    # music stem
    music = board.get("music") or {}
    beats = load_json(proj / "09_edit" / "beats.json", {})
    plan = load_json(proj / "09_edit" / "plan.json", {})
    if music.get("file"):
        title_at = plan.get("title_at", 0.0)
        first = beats.get("first_lyric", 0.0)
        song_start = first - title_at          # seconds into the song at timeline 0
        end = plan.get("end_word_time") or total
        pre = max(-song_start, 0)
        ffmpeg("-ss", f"{max(song_start, 0):.3f}", "-i", music["file"],
               "-f", "lavfi", "-t", f"{total:.4f}", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex",
               f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{max(end - pre, 0.01):.3f},"
               f"afade=t=out:st={max(end - pre - 0.01, 0):.3f}:d=0.01,adelay={int(pre * 1000)}:all=1[m];"
               "[1:a][m]amix=inputs=2:normalize=0:duration=first[o]",   # hard stop on the end word
               "-map", "[o]", "-c:a", "pcm_s24le", out / "music.wav")
    save_json(out / "segments.json", {"dialogue_lines": [[s, e, i["id"]] for s, e, i in lines],
                                      "dialogue_segments": seg, "montage": mont})
    print(f"stems -> {out}/scene.wav, dialogue.wav" + (", music.wav" if music.get("file") else " (no music on board)"))
    print(f"{len(lines)} dialogue lines in {len(seg)} segments; montage ranges {mont}")
    return 0


def echo(proj: Path, dialogue: Path | None = None, scene: Path | None = None, apply: bool = False) -> int:
    """Cross-correlate the dialogue stem against clip audio per line. Constant lag = doubled voice."""
    import numpy as np
    from scipy.signal import correlate
    d = proj / "11_sound"
    dialogue = dialogue or d / "dialogue.wav"
    scene = scene or d / "scene.wav"
    segs = load_json(d / "segments.json")["dialogue_lines"]
    sr = 16000

    def load(p, a, dur):
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", str(p),
                              "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.float32)

    lags = []
    for s, e, iid in segs:
        x, y = load(dialogue, s, e - s), load(scene, s, e - s)
        if len(x) < sr * 0.3 or len(y) < sr * 0.3:
            continue
        n = min(len(x), len(y))
        c = correlate(y[:n] - y[:n].mean(), x[:n] - x[:n].mean(), mode="full", method="fft")
        mid = n - 1
        win = int(0.1 * sr)
        k = int(np.argmax(np.abs(c[mid - win:mid + win]))) - win
        peak = np.abs(c[mid - win:mid + win]).max() / (np.linalg.norm(x[:n]) * np.linalg.norm(y[:n]) + 1e-9)
        lags.append((iid, s, k / sr * 1000, float(peak)))
        print(f"{iid} @ {s:6.2f}s  lag {k / sr * 1000:+6.1f} ms  corr {peak:.2f}")
    strong = [l for l in lags if l[3] > 0.3 and abs(l[2]) > 2]
    if not strong:
        print("no doubled voice detected (no strong non-zero lag)")
        return 0
    med = float(np.median([l[2] for l in strong]))
    spread = float(np.std([l[2] for l in strong]))
    print(f"median lag {med:+.1f} ms (spread {spread:.1f} ms) on {len(strong)} lines -> "
          + ("CONSTANT lag: two copies of each voice" if spread < 3 else "lag not constant: check per line"))
    if apply and spread < 3:
        fixed = d / "dialogue_aligned.wav"
        if med > 0:
            ffmpeg("-i", dialogue, "-af", f"adelay={med:.1f}:all=1", "-c:a", "pcm_s24le", fixed)
        else:
            ffmpeg("-i", dialogue, "-af", f"atrim=start={-med / 1000:.4f},asetpts=PTS-STARTPTS", "-c:a", "pcm_s24le", fixed)
        print(f"wrote {fixed}; mix will use it")
    return 0


def _loudnorm_measure(path: Path) -> dict:
    p = run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA=11:print_format=json",
             "-f", "null", "-"], capture=True, check=False)
    return json.loads(re.findall(r"\{[^{}]+\}", p.stderr)[-1])


def mix(proj: Path, clarity: bool = False) -> int:
    board = load_json(board_path(proj))
    d = proj / "11_sound"
    segs = load_json(d / "segments.json")
    total = length(board)
    mont = [tuple(x) for x in segs["montage"]]
    dseg = [tuple(x) for x in segs["dialogue_segments"]]
    dia = d / "dialogue_aligned.wav" if (d / "dialogue_aligned.wav").exists() else d / "dialogue.wav"
    inputs = ["-i", dia, "-i", d / "scene.wav"]
    g = []
    mont_e = "+".join(f"between(t,{a},{b})" for a, b in mont) or "0"
    clar = ",equalizer=f=280:t=q:w=1:g=-2,equalizer=f=3600:t=q:w=1:g=2.5,highshelf=f=9000:g=1.5,deesser" if clarity else ""
    # Gain staging: AI clips and generated songs arrive at wildly different levels, so balance the
    # stems against each other BEFORE any loudness mastering. Speech is the reference.
    from .verify import loudness
    dia_I = loudness(dia)["I"]
    stage = (SPEECH_REF - dia_I) if dia_I is not None and dia_I > -70 else 0.0
    print(f"gain staging: dialogue {dia_I} LUFS -> {SPEECH_REF} (gain {stage:+.1f} dB, applied to dialogue + scene)")
    g.append(f"[0:a]volume={stage:.2f}dB,volume='if({mont_e},{10 ** (2 / 20):.4f},1)':eval=frame{clar}[dia]")
    g.append(f"[1:a]volume={stage:.2f}dB[scene]")
    buses = ["[dia]", "[scene]"]
    k = 2
    if (d / "music.wav").exists():
        inputs += ["-i", d / "music.wav"]
        env = env_expr(dseg, DIP_DOWN, DIP_UP)
        mus_I = loudness(d / "music.wav")["I"] or SPEECH_REF
        g_out = SPEECH_REF + MUSIC_OPEN_DB - mus_I     # music carries the trailer between lines
        g_dlg = SPEECH_REF + MUSIC_UNDER_DB - mus_I    # whole-segment bed under dialogue
        print(f"gain staging: music {mus_I} LUFS -> {g_out:+.1f} dB open, {g_dlg:+.1f} dB under dialogue")
        bed = f"if({mont_e},{g_out:.2f},{g_out:.2f}+({g_dlg - g_out:.2f})*({env}))"
        # bed level per whole dialogue segment (0.8 s down, 1.2 s up), then dip only the 350-4500 Hz band
        g.append(f"[{k}:a]volume='pow(10,({bed})/20)':eval=frame,asplit=3[m0][m1][m2]")
        g.append(f"[m0]highpass=f={DIP_LO},lowpass=f={DIP_HI},"
                 f"volume='if({mont_e},1,pow(10,{DIP_DB}*({env})/20))':eval=frame[mband]")
        g.append(f"[m1]lowpass=f={DIP_LO}[mlo]")
        g.append(f"[m2]highpass=f={DIP_HI}[mhi]")
        g.append("[mband][mlo][mhi]amix=inputs=3:normalize=0[music]")
        buses.append("[music]")
        k += 1
    fx = load_json(d / "fx.json", [])
    if fx:
        speech = env_expr(dseg, 0.05, 0.05)
        parts = []
        for j, f in enumerate(fx):
            inputs += ["-i", f["file"]]
            gain = f.get("gain_db", 0) - 3
            g.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain}dB,adelay={int(f['t'] * 1000)}:all=1[fx{j}]")
            parts.append(f"[fx{j}]")
            k += 1
        # 12% dark room reverb on the FX group; cut any tail that would wash over a line
        g.append("".join(parts) + f"amix=inputs={len(parts)}:normalize=0,asplit[fxd][fxw]")
        g.append("[fxw]aecho=0.8:0.7:40|73|121:0.5|0.35|0.2,lowpass=f=3500,volume=0.12[fxr]")
        g.append(f"[fxd][fxr]amix=inputs=2:normalize=0,volume='1-({speech})':eval=frame[fx]")
        buses.append("[fx]")
    g.append("".join(buses) + f"amix=inputs={len(buses)}:normalize=0,atrim=0:{total:.4f}[pre]")
    script = d / "mix.filter"
    script.write_text(";\n".join(g))
    pre = d / "mix_pre.wav"
    ffmpeg(*inputs, "-filter_complex_script", script, "-map", "[pre]", "-c:a", "pcm_s24le", "-ar", "48000", pre)
    from .verify import loudness
    final = d / "mix.wav"
    # Peak-limit first (4x oversampled so inter-sample peaks are caught), then a linear gain to the
    # loudness target, then a final 4x oversampled limiter as a true-peak safety net. Iterate the gain
    # a couple of times because the limiter itself moves integrated loudness slightly.
    ceiling = 10 ** ((TARGET_TP - 0.6) / 20)
    lim = (f"aresample=192000,alimiter=limit={ceiling:.4f}:attack=1:release=60:level=false:asc=1,"
           "aresample=48000")
    gain = 0.0
    for _ in range(3):
        ffmpeg("-i", pre, "-af", f"volume={gain:.2f}dB,{lim}", "-c:a", "pcm_s24le", final)
        L = loudness(final)
        if L["I"] is None or abs(L["I"] - TARGET_LUFS) <= 0.2:
            break
        gain += TARGET_LUFS - L["I"]
    print(f"mix -> {final}: {L['I']} LUFS integrated, true peak {L['TP']} dBTP (target {TARGET_LUFS} / <= {TARGET_TP})")
    return 0
