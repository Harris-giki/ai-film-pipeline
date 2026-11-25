"""Visual style packs: one choice at the start drives every stage of the film.

A pack (styles/<id>.json) defines the LOOK block, how characters/sets/vehicles are described, video motion
language (e.g. stop-motion on twos), negative constraints, a camera-language and lighting menu, post
effects (frame stepping, pixelation, palette, paper texture), grade defaults, target look metrics, pacing
targets and the critic's style checklist.

Selecting a style copies the pack into <film>/00_brief/style.json, so a film keeps its style even if the
pack in the plugin is improved later. Films without a style default to realistic-cinematic.
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import ROOT, die, load_json, save_json

STYLES = ROOT / "styles"
DEFAULT = "realistic-cinematic"


def packs() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(STYLES.glob("*.json")) if not p.stem.startswith("_")}


def film_style_path(proj: Path) -> Path:
    return proj / "00_brief" / "style.json"


def load(proj: Path | None) -> dict:
    if proj is not None and film_style_path(proj).exists():
        return load_json(film_style_path(proj))
    return packs()[DEFAULT]


def film_cfg(proj: Path) -> dict:
    return load_json(proj / "00_brief" / "film.json", {"duration_s": 60})


def set_style(proj: Path, sid: str, duration: float | None = None, custom: Path | None = None) -> int:
    if custom:
        pack = json.loads(Path(custom).read_text())
        missing = [k for k in packs()[DEFAULT] if k not in pack]
        if missing:
            die(f"custom style is missing keys: {missing} (start from styles/_template.json)")
    else:
        all_packs = packs()
        if sid not in all_packs:
            die(f"unknown style '{sid}'. Available: {', '.join(all_packs)} (or --custom <file.json>)")
        pack = all_packs[sid]
    save_json(film_style_path(proj), pack)
    cfg = film_cfg(proj)
    cfg["style"] = pack["id"]
    if duration:
        cfg["duration_s"] = duration
    save_json(proj / "00_brief" / "film.json", cfg)
    pace = pack["pacing"]
    setups = round(cfg["duration_s"] / 60 * pace["setups_per_minute"])
    print(f"style: {pack['label']}  ->  {film_style_path(proj)}")
    print(f"targets for {cfg['duration_s']:.0f} s: ~{setups} distinct setups, median shot {pace['median_shot_s']} s, "
          f"montage hits {pace['montage_hit_s'][0]}-{pace['montage_hit_s'][1]} s, dialogue in ~{int(pace['dialogue_shot_share']*100)}% of shots, "
          f"title by {pace['title_by_s']} s")
    return 0


def list_cmd() -> int:
    for sid, p in packs().items():
        print(f"{sid:22s} {p['label']}\n{'':22s} {p['summary']}")
    print("\ncustom: copy styles/_template.json, fill it in, then `fp style <film> --custom my_style.json`")
    return 0


def look(proj: Path | None) -> str:
    return load(proj)["look"]
