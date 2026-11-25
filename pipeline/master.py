"""Step 24 — master in ONE pass from the cut intermediate: grade, titles, grain, subtitles, final mix."""
from __future__ import annotations

import shutil
from pathlib import Path

from .board import board_path, length
from .common import H, ROOT, W, ffmpeg, load_json
from .finish import grade_cfg, grade_chain, grain_chain, style_post_chain, title_overlays, titles_chain
from .style import load as load_style


def master(proj: Path, cut: Path | None = None, burn_subs: bool = True) -> Path:
    cuts = sorted((proj / "09_edit" / "cuts").glob("cut_v*.mov"))
    cut = cut or (cuts[-1] if cuts else None)
    if not cut:
        raise SystemExit("no cut intermediate; run render-cut first")
    mixf = proj / "11_sound" / "mix.wav"
    total = length(load_json(board_path(proj)))
    cfg = grade_cfg(proj)
    overlays = title_overlays(proj)
    inputs = ["-i", cut]
    audio_map = "0:a?"
    if mixf.exists():
        inputs += ["-i", mixf]
        audio_map = "1:a"
    post = load_style(proj)["post"]
    palette_idx = None
    if post.get("palette"):   # pixel styles: build a limited palette from the cut first (pass 1)
        pal = proj / "12_master" / "palette.png"
        pal.parent.mkdir(parents=True, exist_ok=True)
        pw, ph = post.get("pixelate") or [W, H]
        ffmpeg("-i", cut, "-vf", f"fps=2,scale={pw}:{ph}:flags=area,palettegen=max_colors={post['palette']}:stats_mode=full", pal)
        palette_idx = len(inputs) // 2
        inputs += ["-i", pal]
    first_ov = len(inputs) // 2
    for o in overlays:
        inputs += ["-i", o["file"]]
    g = grade_chain(cfg, "0:v", "graded")                       # 1. grade
    g += style_post_chain(post, "graded", "styled", total, palette_idx)   # 1b. style post (stepping, pixels, paper)
    g += titles_chain(overlays, first_ov, "styled", "titled")   # 2. titles: after grade, before grain
    g += grain_chain(cfg, "titled", "grained", total)           # 3. grain last (of the picture look)
    ass = proj / "10_finish" / "subs" / "subs.ass"
    tail = "[grained]"
    if burn_subs and ass.exists():                              # 4. subtitles
        g.append(f"[grained]ass={ass}[subbed]")
        tail = "[subbed]"
    g.append(f"{tail}format=yuv420p,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[vout]")
    script = proj / "12_master" / "master.filter"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(";\n".join(g))
    out = proj / "12_master" / f"{proj.name}_final.mp4"
    ffmpeg(*inputs, "-filter_complex_script", script, "-map", "[vout]", "-map", audio_map,
           "-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-crf", "14",
           "-maxrate", "50M", "-bufsize", "100M", "-r", "24",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{total:.3f}", out,
           quiet=False)
    print(f"mastered {out}")
    return out


def package(proj: Path) -> int:
    d = proj / "12_master" / "package"
    d.mkdir(parents=True, exist_ok=True)
    keep = {
        "stems": [proj / "11_sound" / n for n in ("dialogue.wav", "scene.wav", "music.wav", "mix.wav")],
        "subs": list((proj / "10_finish" / "subs").glob("subs.*")),
        "alpha": list((proj / "10_finish" / "subs").glob("*.mov")) + list((proj / "10_finish" / "titles").rglob("*.mov")),
        "board": [proj / "09_edit" / "board.json"] + list((proj / "09_edit" / "cuts").glob("board_v*.json")),
        "scripts": [ROOT / "pipeline", ROOT / "blender", proj / "12_master" / "master.filter", proj / "11_sound" / "mix.filter"],
    }
    for sub, files in keep.items():
        (d / sub).mkdir(exist_ok=True)
        for f in files:
            if not f.exists():
                continue
            if f.is_dir():
                shutil.copytree(f, d / sub / f.name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(f, d / sub / f.name)
    print(f"packaged stems, SRT, alpha tracks, board JSON and build scripts in {d}")
    return 0
