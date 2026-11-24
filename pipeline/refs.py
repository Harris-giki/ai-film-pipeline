"""Step 02 — tile reference trailers and measure their pacing."""
from __future__ import annotations

import re
import statistics
from pathlib import Path

from .common import duration, ffmpeg, run, save_json

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def detect_cuts(path: Path, threshold: float = 0.30) -> list[float]:
    """Scene-change timestamps via ffmpeg's select filter."""
    p = run(["ffmpeg", "-hide_banner", "-i", path, "-filter:v",
             f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], capture=True, check=False)
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", p.stderr)]


def tile(path: Path, out_dir: Path, cols: int = 8, rows: int = 6) -> list[Path]:
    """ffmpeg fps=1,tile — one sheet per cols*rows seconds."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / f"{path.stem}_tile_%02d.jpg"
    ffmpeg("-i", path, "-vf", f"fps=1,scale=320:-1,tile={cols}x{rows}", "-q:v", "3", pattern)
    return sorted(out_dir.glob(f"{path.stem}_tile_*.jpg"))


def frame_grid(path: Path, out: Path, step: float = 0.5, cols: int = 5) -> Path:
    """Frame grid at a fixed step (step 10: watch the previz at 0.5 s)."""
    dur = duration(path)
    n = max(1, int(dur / step))
    cols = min(cols, n)
    rows = (n + cols - 1) // cols
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-i", path, "-vf",
           f"fps={1/step},scale=384:-1,drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:"
           f"fontcolor=yellow:box=1:boxcolor=black@0.6,tile={cols}x{rows}",
           "-frames:v", "1", "-q:v", "3", out)
    return out


def study(proj: Path) -> dict:
    refs = [p for p in sorted((proj / "01_refs").iterdir()) if p.suffix.lower() in VIDEO_EXT]
    if not refs:
        print("No reference videos in 01_refs/. Drop trailers there first.")
        return {}
    out_dir = proj / "02_research"
    report = {}
    for r in refs:
        dur = duration(r)
        cuts = detect_cuts(r)
        bounds = [0.0] + cuts + [dur]
        shots = [round(b - a, 2) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
        hist = {"<1s": 0, "1-2s": 0, "2-3s": 0, "3-5s": 0, ">5s": 0}
        for s in shots:
            k = "<1s" if s < 1 else "1-2s" if s < 2 else "2-3s" if s < 3 else "3-5s" if s < 5 else ">5s"
            hist[k] += 1
        per10 = [sum(1 for c in cuts if i <= c < i + 10) for i in range(0, int(dur) + 1, 10)]
        tiles = tile(r, out_dir / "tiles")
        report[r.name] = {
            "duration": round(dur, 2), "shots": len(shots),
            "mean_shot": round(statistics.mean(shots), 2) if shots else None,
            "median_shot": round(statistics.median(shots), 2) if shots else None,
            "histogram": hist, "cuts_per_10s": per10, "cut_times": [round(c, 2) for c in cuts],
            "tiles": [str(t.relative_to(proj)) for t in tiles],
        }
        print(f"{r.name}: {dur:.1f}s, {len(shots)} shots, median {report[r.name]['median_shot']}s, "
              f"{len(tiles)} tile sheets")
    save_json(out_dir / "refs_stats.json", report)
    print(f"wrote {out_dir/'refs_stats.json'}  — now read the tiles and write pacing.md + scene_design.md")
    return report
