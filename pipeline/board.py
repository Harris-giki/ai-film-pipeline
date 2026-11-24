"""Steps 14-17 — the edit board JSON: init, diff, gap fill, order board, render exactly what is there.

Board item (step 17):
  id     stable item id (the editor keeps it)       clip  take stem, e.g. "N01_t2"
  t      timeline start of the picture (s)         inp/out  picture in/out in the source (s)
  ain/aout  sound in/out in the source (s); sync-locked: sound sits at t + (ain - inp)
  vt/at  video / audio layer (1 = bottom)          mute  item sound muted
  nov    sound only (no video)                     noa   picture only (no audio)
  note   free text                                 tag   colour tag; "pink" keeps its dialogue
"""
from __future__ import annotations

import copy
import html
import json
import shutil
import time
from pathlib import Path

from .common import FPS, H, W, clip_path, duration, ffmpeg, has_audio, load_json, save_json, tc

GAP_FILL_FRAMES = 3


def board_path(proj: Path) -> Path:
    return proj / "09_edit" / "board.json"


def baseline_path(proj: Path) -> Path:
    return proj / "09_edit" / "board_baseline.json"


def new_item(i: int, clip: str, t: float, inp: float, out: float, **kw) -> dict:
    it = {"id": f"i{i:03d}", "clip": clip, "t": round(t, 3), "inp": round(inp, 3), "out": round(out, 3),
          "ain": round(inp, 3), "aout": round(out, 3), "vt": 1, "at": 1, "mute": False, "nov": False,
          "noa": False, "note": "", "tag": ""}
    it.update(kw)
    return it


def v_span(it):
    return (it["t"], it["t"] + it["out"] - it["inp"])


def a_span(it):
    s = it["t"] + (it["ain"] - it["inp"])
    return (s, s + it["aout"] - it["ain"])


def length(board: dict) -> float:
    ends = [v_span(i)[1] for i in board["items"] if not i.get("nov")] + \
           [a_span(i)[1] for i in board["items"] if not i.get("noa")]
    return max(ends, default=0.0)


# ---------------------------------------------------------------- init (step 14)
def init(proj: Path) -> int:
    sel = load_json(proj / "09_edit" / "selects.json")
    plan = load_json(proj / "09_edit" / "plan.json", {})
    beats = load_json(proj / "09_edit" / "beats.json", {}).get("beats", [])
    offset = plan.get("song_offset", 0.0)
    grid = [b - offset for b in beats if b - offset >= 0]
    items, t = [], 0.0
    for n, s in enumerate(sel, 1):
        inp, out = float(s["in"]), float(s["out"])
        if s.get("use") == "montage" and grid:
            # beat-locked montage hit: 0.25-0.5 s, ending on the next beat after t
            nxt = next((b for b in grid if b > t + 0.25), t + 0.4)
            out = inp + max(0.25, min(0.5, nxt - t))
        items.append(new_item(n, s["clip"], t, inp, out, note=s.get("why", ""),
                              noa=s.get("use") in ("cutaway", "montage") and not s.get("keep_audio", False)))
        t += out - inp
    board = {"fps": FPS, "version": 1, "items": items,
             "music": {"file": load_json(proj / "09_edit" / "beats.json", {}).get("song"),
                       "offset": offset, "end": plan.get("end_word_time")},
             "sections": plan.get("sections", [])}
    save_json(board_path(proj), board)
    print(f"board with {len(items)} items, {t:.2f}s -> {board_path(proj)}")
    return 0


# ---------------------------------------------------------------- diff + gap fill (step 17)
def diff(old: dict, new: dict) -> dict:
    o = {i["id"]: i for i in old.get("items", [])}
    n = {i["id"]: i for i in new.get("items", [])}
    added = [n[k] for k in n if k not in o]
    removed = [o[k] for k in o if k not in n]
    retimed, changed = [], []
    timing = ("t", "inp", "out", "ain", "aout", "vt", "at")
    for k in n.keys() & o.keys():
        dt = {f: (o[k].get(f), n[k].get(f)) for f in timing if abs((o[k].get(f) or 0) - (n[k].get(f) or 0)) > 1e-3}
        if dt:
            retimed.append({"id": k, "clip": n[k]["clip"], "changes": dt})
        other = {f: (o[k].get(f), n[k].get(f)) for f in ("mute", "nov", "noa", "note", "tag", "clip") if o[k].get(f) != n[k].get(f)}
        if other:
            changed.append({"id": k, "clip": n[k]["clip"], "changes": other})
    return {"added": added, "removed": removed, "retimed": retimed, "changed": changed}


def fill_gaps(board: dict, max_frames: int = GAP_FILL_FRAMES) -> list[str]:
    """Fill picture gaps of <= max_frames by extending the item that ends at the gap."""
    log = []
    vis = sorted([i for i in board["items"] if not i.get("nov")], key=lambda i: v_span(i)[0])
    for k in range(1, len(vis)):
        b = vis[k]
        a = max(vis[:k], key=lambda x: v_span(x)[1])  # item whose picture ends last before b
        gap = v_span(b)[0] - v_span(a)[1]
        if 1e-3 < gap <= max_frames / FPS + 1e-6:
            sync = abs(a["aout"] - a["out"]) < 1e-3
            a["out"] = round(a["out"] + gap, 3)
            if sync:
                a["aout"] = a["out"]
            log.append(f"filled {round(gap * FPS)}-frame gap after {a['id']} ({a['clip']})")
    return log


def report(d: dict) -> str:
    lines = [f"ADDED ({len(d['added'])}):"] + [f"  + {i['id']} {i['clip']} at {tc(i['t'])}" for i in d["added"]]
    lines += [f"REMOVED ({len(d['removed'])}):"] + [f"  - {i['id']} {i['clip']}" for i in d["removed"]]
    lines += [f"RETIMED ({len(d['retimed'])}):"]
    for r in d["retimed"]:
        lines.append(f"  ~ {r['id']} {r['clip']}: " + ", ".join(f"{k} {a}->{b}" for k, (a, b) in r["changes"].items()))
    lines += [f"OTHER CHANGES ({len(d['changed'])}):"]
    for r in d["changed"]:
        lines.append(f"  * {r['id']} {r['clip']}: " + ", ".join(f"{k} {a!r}->{b!r}" for k, (a, b) in r["changes"].items()))
    return "\n".join(lines)


def latest_request(proj: Path) -> Path | None:
    reqs = sorted((proj / "09_edit" / "requests").glob("request_*.json"))
    return reqs[-1] if reqs else None


def diff_cmd(proj: Path) -> int:
    req = latest_request(proj)
    new = load_json(req)["board"] if req else load_json(board_path(proj))
    old = load_json(baseline_path(proj), {"items": []})
    if req:
        msg = load_json(req).get("message", "")
        print(f"REQUEST {req.name}" + (f"\nHUMAN NOTE: {msg}" if msg else ""))
    d = diff(old, new)
    print(report(d))
    for line in fill_gaps(new):
        print("GAPFILL", line)
    save_json(board_path(proj), new)
    print(f"new length {length(new):.2f}s; board.json updated. Render only after sign-off: pipeline render-cut")
    return 0


# ---------------------------------------------------------------- order board (step 15)
def item_line(proj: Path, it: dict) -> str:
    tr = load_json(proj / "09_edit" / "transcripts.json", {}).get(it["clip"], {})
    words = [w["w"] for w in tr.get("words", []) if it["ain"] - 0.05 <= w["s"] <= it["aout"]]
    return " ".join(words)


def orderboard(proj: Path) -> int:
    from PIL import Image, ImageDraw, ImageFont
    board = load_json(board_path(proj))
    out_dir = proj / "09_edit" / "orderboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    items = sorted([i for i in board["items"] if not i.get("nov")], key=lambda i: (v_span(i)[0], -i["vt"]))
    rows, thumbs = [], []
    for n, it in enumerate(items, 1):
        th = out_dir / f"{n:03d}_{it['id']}.jpg"
        src = clip_path(proj, it["clip"])
        ffmpeg("-ss", f"{(it['inp'] + it['out']) / 2:.3f}", "-i", src, "-frames:v", "1", "-vf", "scale=320:-1", "-q:v", "4", th)
        line = item_line(proj, it)
        thumbs.append((n, th, it, line))
        rows.append(f"<tr><td>{n}</td><td><img src='orderboard/{th.name}'></td><td>{tc(it['t'])}</td>"
                    f"<td>{html.escape(it['clip'])}<br><small>{it['inp']:.2f}-{it['out']:.2f}</small></td>"
                    f"<td>{html.escape(line) or '<i>picture only</i>'}</td><td>{html.escape(it.get('note',''))}</td></tr>")
    (proj / "09_edit" / "orderboard.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Order board</title><style>body{font:14px Helvetica;background:#111;color:#eee}"
        "td{padding:6px;border-bottom:1px solid #333;vertical-align:top}img{width:200px}</style>"
        f"<h1>Order board — {proj.name} ({length(board):.1f}s)</h1><table>{''.join(rows)}</table>")
    # contact PNG for showing in chat
    cols, cw, ch = 6, 320, 240
    sheet = Image.new("RGB", (cols * cw, ((len(thumbs) + cols - 1) // cols or 1) * ch), (17, 17, 17))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except OSError:
        f = ImageFont.load_default()
    for k, (n, th, it, line) in enumerate(thumbs):
        x, y = (k % cols) * cw, (k // cols) * ch
        sheet.paste(Image.open(th), (x, y))
        d.text((x + 4, y + 184), f"{n}  {tc(it['t'])}  {it['clip']}", fill="white", font=f)
        d.text((x + 4, y + 204), (line or "(picture only)")[:44], fill=(200, 200, 200), font=f)
    sheet.save(proj / "09_edit" / "orderboard.png")
    print(f"wrote {proj/'09_edit'/'orderboard.html'} and orderboard.png ({len(thumbs)} items)")
    return 0


# ---------------------------------------------------------------- render exactly what is there (step 17)
def timeline_segments(proj: Path, board: dict) -> list[dict]:
    """Per-frame: topmost video layer wins; real gaps stay black. Returns merged segments."""
    total = int(round(length(board) * FPS))
    vis = [i for i in board["items"] if not i.get("nov")]
    frames = []
    for f in range(total):
        t = (f + 0.5) / FPS
        cover = [i for i in vis if v_span(i)[0] <= t < v_span(i)[1]]
        if cover:
            top = max(cover, key=lambda i: (i["vt"], board["items"].index(i)))
            frames.append((top["id"], top["clip"], top["inp"] + (t - top["t"])))
        else:
            frames.append((None, None, None))
    segs = []
    for f, (iid, clip, src) in enumerate(frames):
        if segs and segs[-1]["id"] == iid:
            segs[-1]["frames"] += 1
        else:
            segs.append({"id": iid, "clip": clip, "src": (src - 0.5 / FPS) if src is not None else None, "frames": 1})
    return segs


def render(proj: Path, out: Path | None = None) -> Path:
    board = load_json(board_path(proj))
    cuts = proj / "09_edit" / "cuts"
    cuts.mkdir(parents=True, exist_ok=True)
    ver = len(list(cuts.glob("cut_v*.mov"))) + 1
    out = out or cuts / f"cut_v{ver:02d}.mov"
    tmp = cuts / f".tmp_v{ver:02d}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},setsar=1,format=yuv422p10le"
    parts = []
    for k, s in enumerate(timeline_segments(proj, board)):
        p = tmp / f"{k:04d}.mov"
        n = s["frames"]
        if s["clip"] is None:
            ffmpeg("-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}", "-frames:v", n,
                   "-vf", "format=yuv422p10le", "-c:v", "prores_ks", "-profile:v", "3", p)
        else:
            ffmpeg("-ss", f"{max(s['src'], 0):.4f}", "-i", clip_path(proj, s["clip"]), "-frames:v", n, "-an",
                   "-vf", vf, "-c:v", "prores_ks", "-profile:v", "3", p)
        parts.append(p)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    video = tmp / "video.mov"
    ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video)
    audio = render_audio(proj, board, tmp / "audio.wav")
    args = ["-i", video] + (["-i", audio] if audio else []) + ["-c:v", "copy"]
    args += (["-c:a", "pcm_s24le", "-shortest"] if audio else []) + [out]
    ffmpeg(*args)
    shutil.rmtree(tmp, ignore_errors=True)
    save_json(baseline_path(proj), board)  # the sent/rendered board becomes the new baseline
    snap = cuts / f"board_v{ver:02d}.json"
    save_json(snap, board)
    print(f"rendered {out} ({length(board):.2f}s); baseline updated; board snapshot {snap.name}")
    return out


def render_audio(proj: Path, board: dict, out: Path) -> Path | None:
    """Clip sound only (music + dialogue stems come later in pipeline/mix.py). 2-frame de-click fades."""
    items = [i for i in board["items"] if not i.get("noa") and not i.get("mute")
             and has_audio(clip_path(proj, i["clip"]))]
    muted_layers = set(board.get("muted_audio_layers", []))
    items = [i for i in items if i["at"] not in muted_layers]
    total = length(board)
    if not items:
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{total:.3f}", "-c:a", "pcm_s24le", out)
        return out
    args, chains = [], []
    fade = 2 / FPS
    for k, it in enumerate(items):
        args += ["-i", clip_path(proj, it["clip"])]
        start = max(a_span(it)[0], 0)
        d = it["aout"] - it["ain"]
        chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim={it['ain']:.4f}:{it['aout']:.4f},"
                      f"asetpts=PTS-STARTPTS,afade=t=in:d={fade:.4f},afade=t=out:st={max(d - fade, 0):.4f}:d={fade:.4f},"
                      f"adelay={int(start * 1000)}:all=1[a{k}]")
    args += ["-f", "lavfi", "-t", f"{total:.4f}", "-i", "anullsrc=r=48000:cl=stereo"]
    mix = f"[{len(items)}:a]" + "".join(f"[a{k}]" for k in range(len(items))) + \
        f"amix=inputs={len(items) + 1}:normalize=0:duration=first:dropout_transition=0[out]"
    ffmpeg(*args, "-filter_complex", ";".join(chains + [mix]), "-map", "[out]", "-c:a", "pcm_s24le", out)
    return out
