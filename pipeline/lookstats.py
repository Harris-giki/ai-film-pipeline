"""Measure a film's look (brightness, black/white point, contrast, saturation, detail) and match it to a target.

Targets come from the style pack (`target_metrics`) or from any reference film (`--ref`). This turned
"it looks worse than the reference" into numbers: SUNSHINE measured luma 0.41 / black 0.078 / sat 0.39
against the reference's 0.31 / 0.033 / 0.51, i.e. too bright, milky blacks, under-saturated.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from .common import load_json, save_json


def measure(path: Path, fps: float = 1.0) -> dict:
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf",
                          f"fps={fps},scale=480:270,format=rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 270, 480, 3).astype(np.float32) / 255
    mx, mn = a.max(3), a.min(3)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    Y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    lap = np.abs(Y[:, 1:-1, 1:-1] * 4 - Y[:, :-2, 1:-1] - Y[:, 2:, 1:-1] - Y[:, 1:-1, :-2] - Y[:, 1:-1, 2:]).mean()
    return {"luma": round(float(Y.mean()), 3), "black_point": round(float(np.percentile(Y, 2, axis=(1, 2)).mean()), 3),
            "white_point": round(float(np.percentile(Y, 98, axis=(1, 2)).mean()), 3),
            "contrast_std": round(float(Y.std(axis=(1, 2)).mean()), 3), "saturation": round(float(sat.mean()), 3),
            "detail": round(float(lap) * 100, 2)}


def _stats(a) -> dict:
    import numpy as np
    mx, mn = a.max(3), a.min(3)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    Y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    return {"luma": float(Y.mean()), "black_point": float(np.percentile(Y, 2, axis=(1, 2)).mean()),
            "white_point": float(np.percentile(Y, 98, axis=(1, 2)).mean()),
            "contrast_std": float(Y.std(axis=(1, 2)).mean()), "saturation": float(sat.mean())}


WEIGHTS = {"luma": 3.0, "black_point": 4.0, "saturation": 3.0, "white_point": 1.0, "contrast_std": 1.0}


def fit(cut: Path, grade: dict, tgt: dict, work: Path, frames: int = 16, rounds: int = 3) -> tuple[dict, dict]:
    """Closed-loop grade fit: run the REAL grade chain on sampled frames of the ungraded cut and search
    contrast / saturation / gamma / black point until the measured look matches the target."""
    import copy

    import numpy as np

    from .common import duration, ffmpeg
    from .finish import grade_chain
    work.mkdir(parents=True, exist_ok=True)
    sample = work / "lookfit_sample.mov"
    d = duration(cut)
    ffmpeg("-i", cut, "-vf", f"fps={frames / d:.5f},scale=960:540", "-frames:v", frames, "-c:v", "prores_ks", "-profile:v", "3", "-an", sample)

    def evaluate(g: dict) -> tuple[float, dict]:
        g2 = copy.deepcopy(g)
        g2["halation"]["sigma"] = max(1, g2["halation"]["sigma"] * 0.5)   # sample is half resolution
        graph = ";".join(grade_chain(g2, "0:v", "o")) + ";[o]scale=480:270,format=rgb24[f]"
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(sample), "-filter_complex", graph, "-map", "[f]",
                              "-f", "rawvideo", "-"], capture_output=True).stdout
        a = np.frombuffer(raw, np.uint8).reshape(-1, 270, 480, 3).astype(np.float32) / 255
        st = _stats(a)
        err = sum(w * ((st[k] - tgt[k]) / max(tgt[k], 0.05)) ** 2 for k, w in WEIGHTS.items() if k in tgt)
        return err, st

    g = copy.deepcopy(grade)
    g.setdefault("eq", {}).setdefault("gamma", 1.0)
    g.setdefault("black_point", 0.0)
    knobs = {("eq", "contrast"): (0.85, 1.25), ("eq", "saturation"): (0.6, 1.7), ("eq", "gamma"): (0.65, 1.4), ("black_point",): (0.0, 0.08)}
    best, best_st = evaluate(g)
    for r in range(rounds):
        for key, (lo, hi) in knobs.items():
            cur = g[key[0]][key[1]] if len(key) == 2 else g[key[0]]
            span = (hi - lo) / (4 * (r + 1))
            for cand in np.linspace(max(lo, cur - span), min(hi, cur + span), 7):
                trial = copy.deepcopy(g)
                if len(key) == 2:
                    trial[key[0]][key[1]] = round(float(cand), 3)
                else:
                    trial[key[0]] = round(float(cand), 3)
                e, st = evaluate(trial)
                if e < best:
                    best, best_st, g = e, st, trial
        print(f"  round {r + 1}: error {best:.4f}  luma {best_st['luma']:.3f} black {best_st['black_point']:.3f} "
              f"sat {best_st['saturation']:.3f}")
    return g, {k: round(v, 3) for k, v in best_st.items()}


def cmd(proj: Path, video: str | None, ref: str | None, apply: bool) -> int:
    """Measure the graded master against the target; with --apply, fit the grade on the ungraded cut."""
    from .finish import grade_cfg
    from .style import load as load_style
    st = load_style(proj)
    tgt = {k: v for k, v in (measure(Path(ref)) if ref else st["target_metrics"]).items() if k != "detail"}
    masters = sorted((proj / "12_master").glob("*_final.mp4"))
    vid = Path(video) if video else (masters[-1] if masters else None)
    if vid is not None and vid.exists():
        cur = measure(vid)
        print(f"{'metric':14s}{'this film':>11s}{'target':>10s}   ({vid.name})")
        for k in ("luma", "black_point", "white_point", "contrast_std", "saturation"):
            flag = "" if abs(cur[k] - tgt[k]) <= 0.15 * max(abs(tgt[k]), 0.05) else "  <- off"
            print(f"{k:14s}{cur[k]:>11}{round(tgt[k], 3):>10}{flag}")
    if not apply:
        print("run with --apply to fit the grade to the target")
        return 0
    cuts = sorted((proj / "09_edit" / "cuts").glob("cut_v*.mov"))
    if not cuts:
        print("no cut to fit on (fp render-cut first)")
        return 1
    print(f"fitting grade on {cuts[-1].name} -> target {({k: round(v, 3) for k, v in tgt.items()})}")
    g, pred = fit(cuts[-1], grade_cfg(proj), tgt, proj / "10_finish")
    save_json(proj / "10_finish" / "grade.json", g)
    print(f"applied: contrast {g['eq']['contrast']}, saturation {g['eq']['saturation']}, gamma {g['eq']['gamma']}, "
          f"black_point {g['black_point']}; predicted {pred}. Now `fp master` and re-measure.")
    return 0
