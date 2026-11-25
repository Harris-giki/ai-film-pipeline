"""Credit estimate for a film before anything is generated (images, clips, music).

Defaults are what we measured in late 2026 and are only a guide: Seedance 2.5 1080p 10 s = 2,678 credits.
Shorter clips are assumed to scale linearly with duration (verify on the first short clip). Image cost is a
rough placeholder: measure one batch with get_balance and pass --image.
"""
from __future__ import annotations

from pathlib import Path

from .common import load_json


def estimate(proj: Path, clip10: float = 2678, image: float = 250, music: float = 300, takes: float = 1.0) -> int:
    scenes = load_json(proj / "03_scenes" / "scenes.json", [])
    chars = load_json(proj / "03_scenes" / "characters.json", {})
    vehicles = load_json(proj / "03_scenes" / "vehicles.json", {})
    imgs = {"lead sheets": 0, "vignette cards": 0, "plates": 0, "vehicles": len(vehicles)}
    for c in chars.values():
        outfits = list(c.get("outfits", {}))
        if c.get("role") == "vignette":
            imgs["vignette cards"] += len(outfits)
        else:
            imgs["lead sheets"] += 3 + 2 * max(0, len(outfits) - 1)
    imgs["plates"] = len({(s.get("location"), s.get("tod")) for s in scenes if s.get("location")})
    secs = [float(s.get("duration", 10)) for s in scenes]
    clip_cost = sum(clip10 * d / 10 for d in secs) * takes
    img_n = sum(imgs.values())
    total = clip_cost + img_n * image + music
    print(f"setups {len(scenes)}  |  clip seconds {sum(secs):.0f} ({sum(1 for d in secs if d >= 8)} long, "
          f"{sum(1 for d in secs if d < 8)} short)  |  takes per shot {takes}")
    print("images: " + ", ".join(f"{k} {v}" for k, v in imgs.items()) + f"  = {img_n}")
    print(f"estimate: clips {clip_cost:,.0f} + images {img_n * image:,.0f} + music {music:,.0f} = ~{total:,.0f} credits")
    print("assumptions: clip cost scales with duration; image cost is a placeholder until measured")
    return 0
