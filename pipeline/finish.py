"""Steps 18, 20, 21 — grade chain, tracked titles, subtitles."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .board import a_span, board_path, length
from .common import FPS, H, W, clip_path, ffmpeg, load_json, save_json, tc

# ------------------------------------------------------------------ step 18: grade
# Grade defaults now come from the film's style pack (styles/*.json). The old single default (35% halation,
# heavy grain, contrast < 1) lifted the blacks and washed SUNSHINE out; the realistic pack is retuned toward
# a measured top-tier reference (deep blacks, ~0.5 saturation).
def grade_cfg(proj: Path) -> dict:
    from .style import load as load_style
    base = load_style(proj)["grade"]
    p = proj / "10_finish" / "grade.json"
    if not p.exists():
        save_json(p, base)
    return {**base, **load_json(p)}


def grade_chain(cfg: dict, src: str, dst: str) -> list[str]:
    """Filtergraph lines: [src] -> graded (before titles/grain) -> [dst]. Zero-strength stages are skipped."""
    g, out = [], src
    g.append(f"[{out}]format=gbrp16le[g_in]"); out = "g_in"
    if cfg.get("lut"):
        g.append(f"[{out}]split[l0][l1]")
        g.append(f"[l1]lut3d=file='{cfg['lut']}':interp=tetrahedral[l2]")
        g.append(f"[l0][l2]blend=all_mode=normal:all_opacity={cfg['lut_mix']}[g_lut]"); out = "g_lut"
    h = cfg["halation"]
    if h.get("screen", 0) > 0:
        r, gg, b = h["warm"]
        g.append(f"[{out}]split[h0][h1]")
        g.append(f"[h1]curves=all='0/0 {h['knee']}/0 1/1',gblur=sigma={h['sigma']},"
                 f"colorchannelmixer=rr={r}:gg={gg}:bb={b}[h2]")
        g.append(f"[h0][h2]blend=all_mode=screen:all_opacity={h['screen']}[g_hal]"); out = "g_hal"
    e = cfg["eq"]
    g.append(f"[{out}]eq=contrast={e['contrast']}:saturation={e['saturation']}:gamma={e.get('gamma', 1.0)}[g_eq]"); out = "g_eq"
    if cfg.get("black_point"):  # crush lifted blacks: map input black_point -> 0
        bp = cfg["black_point"]
        g.append(f"[{out}]curves=all='0/0 {bp}/0 1/1'[g_bp]"); out = "g_bp"
    bl = cfg["bloom"]
    if bl.get("body_ranges") and bl.get("screen", 0) > 0:
        en = "+".join(f"between(t,{a},{z})" for a, z in bl["body_ranges"])
        g.append(f"[{out}]split[b0][b1]")
        g.append(f"[b1]gblur=sigma={bl['sigma']}[b2]")
        g.append(f"[b0][b2]blend=all_mode=screen:all_opacity={bl['screen']}:enable='{en}'[g_bl]"); out = "g_bl"
    g.append(f"[{out}]null[{dst}]")
    return g


def grain_chain(cfg: dict, src: str, dst: str, dur: float) -> list[str]:
    gr = cfg["grain"]
    if not gr.get("luma") or not gr.get("opacity"):
        return [f"[{src}]null[{dst}]"]
    return [
        f"color=c=0x808080:s={gr['w']}x{gr['h']}:r={FPS}:d={dur:.3f},format=yuv444p,"
        f"noise=c0s={gr['luma']}:c0f=t+u,scale={W}:{H}:flags=bicubic,format=gbrp16le[grain]",
        f"[{src}][grain]blend=all_mode=grainmerge:all_opacity={gr['opacity']}:shortest=1[{dst}]",
    ]


def style_post_chain(post: dict, src: str, dst: str, dur: float, palette_input: int | None = None) -> list[str]:
    """Style-defining post: stop-motion frame stepping, pixelation, limited palette, paper texture."""
    g, cur = [], src
    if post.get("frame_step"):   # hold each pose for 24/frame_step frames (12 = "on twos")
        g.append(f"[{cur}]fps={post['frame_step']},fps={FPS}[ps_step]"); cur = "ps_step"
    if post.get("pixelate"):
        pw, ph = post["pixelate"]
        g.append(f"[{cur}]scale={pw}:{ph}:flags=area,scale={W}:{H}:flags=neighbor[ps_px]"); cur = "ps_px"
    if post.get("palette") and palette_input is not None:
        g.append(f"[{cur}]format=rgb24[ps_rgb]")
        g.append(f"[ps_rgb][{palette_input}:v]paletteuse=dither=bayer:bayer_scale=3[ps_pal]"); cur = "ps_pal"
    if post.get("texture") == "paper":
        g.append(f"color=c=0xf4eee0:s={W}x{H}:r={FPS}:d={dur:.3f},noise=alls=18:allf=0,gblur=sigma=1.1,format=gbrp16le[ps_tex]")
        g.append(f"[{cur}]format=gbrp16le[ps_in]")
        g.append(f"[ps_in][ps_tex]blend=all_mode=multiply:all_opacity=0.22:shortest=1[ps_paper]"); cur = "ps_paper"
    g.append(f"[{cur}]format=gbrp16le[{dst}]")
    return g


def grade_preview(proj: Path, clip: str, at: float = 2.0) -> int:
    cfg = grade_cfg(proj)
    src = clip_path(proj, clip)
    out = proj / "10_finish" / f"grade_preview_{clip}.png"
    graph = ";".join([f"[0:v]scale={W}:{H},split[s_a][s_b]"] + grade_chain(cfg, "s_a", "gr") +
                     grain_chain(cfg, "gr", "gg", 0.5) +
                     ["[s_b]format=gbrp16le[orig]", "[orig][gg]hstack,scale=1920:-1,format=rgb24[o]"])
    ffmpeg("-ss", f"{at}", "-i", src, "-frames:v", "1", "-filter_complex", graph, "-map", "[o]", out)
    print(f"wrote {out} (left: original, right: graded + grain)")
    return 0


# ------------------------------------------------------------------ step 20: tracked titles
def title_overlays(proj: Path) -> list[dict]:
    """Each overlay is tied to ONE source clip: overlay frame 0 = clip frame 0.
    If the cut trims the clip head by N frames, the overlay is trimmed by the same N."""
    board = load_json(board_path(proj))
    out = []
    for t in load_json(proj / "10_finish" / "titles.json", []):
        uses = [i for i in board["items"] if i["clip"] == t["clip"] and not i.get("nov")]
        if t.get("item"):
            uses = [i for i in uses if i["id"] == t["item"]]
        if not uses:
            print(f"WARN title {t['overlay']}: clip {t['clip']} not on the board")
            continue
        it = uses[0]
        n = round(it["inp"] * FPS)
        out.append({"file": str((proj / t["overlay"]) if not Path(t["overlay"]).is_absolute() else t["overlay"]),
                    "trim_frames": n, "start": it["t"], "end": it["t"] + it["out"] - it["inp"]})
    return out


def titles_chain(overlays: list[dict], first_input: int, src: str, dst: str) -> list[str]:
    g, cur = [], src
    for k, o in enumerate(overlays):
        idx = first_input + k
        g.append(f"[{idx}:v]trim=start_frame={o['trim_frames']},setpts=PTS-STARTPTS+{o['start']:.4f}/TB,"
                 f"format=gbrap16le[t{k}]")
        nxt = f"ti{k}"
        g.append(f"[{cur}][t{k}]overlay=eof_action=pass:enable='between(t,{o['start']:.4f},{o['end']:.4f})',format=gbrp16le[{nxt}]")
        cur = nxt
    g.append(f"[{cur}]null[{dst}]")
    return g


# ------------------------------------------------------------------ step 21: subtitles
MAX_CHARS = 42
HOLD = 0.25
FONT = "Helvetica Neue"
FONT_SIZE = 49
CENTRE_Y = 0.88


def _split_line(words: list[dict]) -> list[list[dict]]:
    """Split at natural pauses / punctuation so each line is <= 42 chars."""
    out, cur = [], []
    for w in words:
        cand = " ".join(x["w"] for x in cur + [w])
        if cur and len(cand) > MAX_CHARS:
            # back off to the last punctuation or biggest pause inside cur
            cut = len(cur)
            for j in range(len(cur) - 1, 0, -1):
                if re.search(r"[,.;:!?]$", cur[j - 1]["w"]) or cur[j]["s"] - cur[j - 1]["e"] > 0.25:
                    cut = j
                    break
            out.append(cur[:cut])
            cur = cur[cut:]
        cur.append(w)
        if re.search(r"[.!?]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [c for c in out if c]


def _onset(clip: Path, t0: float, search: float = 0.2) -> float:
    """Voice energy onset near a word start (time from the voice, not model word stamps)."""
    import numpy as np
    sr = 16000
    a = max(t0 - search, 0)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{2 * search:.3f}", "-i", str(clip),
                          "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    if len(x) < 400:
        return t0
    hop = 160
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))[::hop]
    thr = max(rms.max() * 0.25, 1e-4)
    idx = int(np.argmax(rms > thr))
    return a + idx * hop / sr


def build_subs(proj: Path) -> list[dict]:
    board = load_json(board_path(proj))
    tr = load_json(proj / "09_edit" / "transcripts.json", {})
    subs = []
    for it in board["items"]:
        if it.get("noa") or it.get("mute"):
            continue
        words = [w for w in tr.get(it["clip"], {}).get("words", []) if w["e"] > it["ain"] + 0.05 and w["s"] < it["aout"] - 0.05]
        if not words:
            continue
        clip = clip_path(proj, it["clip"])
        off = a_span(it)[0] - it["ain"]
        for grp in _split_line(words):
            on = _onset(clip, grp[0]["s"])
            if abs(on - grp[0]["s"]) > 0.15:   # cross-check against word times
                on = grp[0]["s"]
            start = on + off - 1 / FPS          # on one frame early
            end = grp[-1]["e"] + off + HOLD     # hold 0.25 s
            text = " ".join(w["w"] for w in grp).strip()
            text = text[:1].upper() + text[1:]
            subs.append({"start": max(start, 0), "end": end, "text": text, "item": it["id"]})
    subs.sort(key=lambda s: s["start"])
    for a, b in zip(subs, subs[1:]):           # never into the next line
        a["end"] = min(a["end"], b["start"] - 1 / FPS)
    return subs


def _srt_t(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _ass_t(s: float) -> str:
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def write_subs(proj: Path) -> int:
    d = proj / "10_finish" / "subs"
    d.mkdir(parents=True, exist_ok=True)
    subs = build_subs(proj)
    (d / "subs.srt").write_text("".join(f"{n}\n{_srt_t(s['start'])} --> {_srt_t(s['end'])}\n{s['text']}\n\n"
                                        for n, s in enumerate(subs, 1)))
    margin_v = int(round(H * (1 - CENTRE_Y) - FONT_SIZE / 2))
    ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           f"Style: Sub,{FONT} Medium,{FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,40,40,{margin_v},1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    ass += [f"Dialogue: 0,{_ass_t(s['start'])},{_ass_t(s['end'])},Sub,,0,0,0,,{s['text']}" for s in subs]
    (d / "subs.ass").write_text("\n".join(ass) + "\n")
    board = load_json(board_path(proj))
    total = length(board)
    # alpha track (ProRes 4444)
    ffmpeg("-f", "lavfi", "-i", f"color=c=black@0.0:s={W}x{H}:r={FPS}:d={total:.3f},format=yuva444p10le",
           "-vf", f"ass={d/'subs.ass'}:alpha=1", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
           d / "subs_alpha.mov")
    # luminance behind each line + burned preview from the latest cut
    cuts = sorted((proj / "09_edit" / "cuts").glob("cut_v*.mov"))
    flags = []
    if cuts:
        from PIL import Image
        import io
        for s in subs:
            mid = (s["start"] + s["end"]) / 2
            png = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{mid:.3f}", "-i", str(cuts[-1]), "-frames:v", "1",
                                  "-vf", f"crop={int(W*0.6)}:{FONT_SIZE*2}:{int(W*0.2)}:{int(H*CENTRE_Y-FONT_SIZE)},format=gray",
                                  "-f", "image2", "-c:v", "png", "-"], capture_output=True).stdout
            if png:
                lum = sum(Image.open(io.BytesIO(png)).getdata()) / (int(W * 0.6) * FONT_SIZE * 2) / 255
                s["luma"] = round(lum, 3)
                if lum > 0.62:
                    flags.append(s)
        ffmpeg("-i", cuts[-1], "-vf", f"scale=1280:720,ass={d/'subs.ass'}:original_size={W}x{H}",
               "-c:v", "libx264", "-crf", "23", "-c:a", "aac", d / "burned_preview.mp4")
    save_json(d / "subs.json", subs)
    print(f"{len(subs)} subtitle lines -> subs.srt, subs.ass, subs_alpha.mov" + (", burned_preview.mp4" if cuts else ""))
    for f in flags:
        print(f"FLAG bright background (luma {f['luma']}) at {tc(f['start'])}: \"{f['text']}\" — human decision")
    return 0
