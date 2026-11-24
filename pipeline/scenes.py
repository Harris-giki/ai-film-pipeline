"""Step 03 — scene list validation, numbered table and one-picture board."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .common import load_json, save_json

ID_RE = re.compile(r"^[A-Z]{1,3}\d{1,3}$")
KINDS = {"dialogue", "emote", "gameplay"}


def load(proj: Path):
    d = proj / "03_scenes"
    return (load_json(d / "scenes.json"), load_json(d / "characters.json", {}),
            load_json(d / "locations.json", {}))


def validate(scenes: list[dict], chars: dict, locs: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    ids = [s.get("id", "") for s in scenes]
    for i, dup in Counter(ids).items():
        if dup > 1:
            errors.append(f"duplicate id {i}")
    last_outfit: dict[str, str] = {}
    prev_pair = None
    for n, s in enumerate(scenes):
        sid = s.get("id", f"#{n}")
        if not ID_RE.match(sid):
            errors.append(f"{sid}: id must be stable short code like N01, V11, B5")
        if s.get("kind") not in KINDS:
            errors.append(f"{sid}: kind must be one of {sorted(KINDS)}")
        cast = s.get("cast", [])
        speaking = s.get("speaking", [])
        if len(speaking) > 2:
            errors.append(f"{sid}: max two speaking characters (has {len(speaking)})")
        if not set(speaking) <= set(cast):
            errors.append(f"{sid}: speaking characters must be in cast")
        lines = s.get("lines", [])
        if len(lines) not in (0, 1, 2):
            errors.append(f"{sid}: two short lines or none (has {len(lines)})")
        for ln in lines:
            if len(ln.get("text", "").split()) > 14:
                warns.append(f"{sid}: line by {ln.get('who')} is long; keep lines short")
            if ln.get("who") not in speaking:
                errors.append(f"{sid}: line speaker {ln.get('who')} not in speaking")
        if s.get("kind") == "dialogue" and not lines:
            warns.append(f"{sid}: dialogue scene with no lines")
        if s.get("kind") != "dialogue" and lines:
            warns.append(f"{sid}: {s.get('kind')} scene has lines")
        action = s.get("action", "")
        if not action or re.search(r"\b(then|and then|after that)\b", action, re.I):
            errors.append(f"{sid}: one single action (no 'then' sequences)")
        if s.get("duration", 10) != 10:
            warns.append(f"{sid}: method uses 10 s clips")
        if s.get("aspect", "16:9") != "16:9":
            errors.append(f"{sid}: aspect must be 16:9")
        loc = s.get("location")
        if locs and loc not in locs:
            errors.append(f"{sid}: unknown location {loc}")
        elif locs and s.get("tod") not in locs[loc].get("tods", [s.get("tod")]):
            errors.append(f"{sid}: no {s.get('tod')} plate planned for {loc}")
        # outfit / accessory change for every character vs previous appearance
        outfits = s.get("outfit", {})
        changed = False
        for c in cast:
            if chars and c not in chars:
                errors.append(f"{sid}: unknown character {c}")
                continue
            o = outfits.get(c)
            if o is None:
                errors.append(f"{sid}: no outfit listed for {c}")
                continue
            if chars and o not in chars[c].get("outfits", {}):
                errors.append(f"{sid}: outfit '{o}' not defined for {c}")
            if last_outfit.get(c) != o:
                changed = True
            last_outfit[c] = o
        if cast and not changed and not s.get("accessory_change"):
            errors.append(f"{sid}: needs an outfit or accessory change (set accessory_change)")
        pair = frozenset(cast) if len(cast) >= 2 else None
        if pair and pair == prev_pair:
            errors.append(f"{sid}: neighbouring scenes reuse the same character pair {sorted(pair)}")
        prev_pair = pair
    kinds = Counter(s.get("kind") for s in scenes)
    for k in KINDS:
        if scenes and kinds.get(k, 0) == 0:
            warns.append(f"no '{k}' scenes; method mixes all three kinds")
    return errors, warns


def table_md(scenes: list[dict]) -> str:
    rows = ["| # | ID | Kind | Cast (speaking*) | Location | Action | Lines | Camera |",
            "|---|----|------|------------------|----------|--------|-------|--------|"]
    for n, s in enumerate(scenes, 1):
        cast = ", ".join(c + ("*" if c in s.get("speaking", []) else "") for c in s.get("cast", []))
        lines = " / ".join(f"{l['who']}: \"{l['text']}\"" for l in s.get("lines", [])) or "none"
        rows.append(f"| {n} | {s['id']} | {s.get('kind')} | {cast} | {s.get('location')} ({s.get('tod')}) "
                    f"| {s.get('action')} | {lines} | {s.get('camera', '')} |")
    return "\n".join(rows) + "\n"


def board_png(proj: Path, scenes: list[dict], out: Path) -> None:
    """One picture of the whole set: a card per scene, using the plate thumbnail if one exists."""
    from PIL import Image, ImageDraw, ImageFont
    cols = 6
    cw, chh = 320, 230
    rows = (len(scenes) + cols - 1) // cols or 1
    img = Image.new("RGB", (cols * cw, rows * chh), (24, 24, 26))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15)
        big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except OSError:
        font = big = ImageFont.load_default()
    colours = {"dialogue": (230, 90, 140), "emote": (90, 170, 230), "gameplay": (120, 200, 120)}
    for n, s in enumerate(scenes):
        x, y = (n % cols) * cw, (n // cols) * chh
        plate = proj / "05_plates" / f"{s.get('location')}_{s.get('tod')}.png"
        if plate.exists():
            th = Image.open(plate).convert("RGB")
            th.thumbnail((cw - 10, 150))
            img.paste(th, (x + 5, y + 5))
        else:
            d.rectangle([x + 5, y + 5, x + cw - 5, y + 155], fill=(50, 50, 55))
        d.rectangle([x + 5, y + 5, x + 60, y + 32], fill=colours.get(s.get("kind"), (128, 128, 128)))
        d.text((x + 10, y + 7), f"{n + 1}", fill="white", font=big)
        d.text((x + 70, y + 10), s["id"], fill="white", font=big)
        d.text((x + 8, y + 160), ", ".join(s.get("cast", [])) or "(no cast)", fill="white", font=font)
        d.text((x + 8, y + 180), (s.get("action", ""))[:40], fill=(200, 200, 200), font=font)
        d.text((x + 8, y + 200), f"{s.get('location')} / {s.get('tod')}", fill=(160, 160, 160), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def cmd(proj: Path) -> int:
    scenes, chars, locs = load(proj)
    errors, warns = validate(scenes, chars, locs)
    for w in warns:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    d = proj / "03_scenes"
    (d / "scenes.md").write_text(table_md(scenes))
    board_png(proj, scenes, d / "scenes_board.png")
    print(f"{len(scenes)} scenes; wrote {d/'scenes.md'} and {d/'scenes_board.png'}")
    print("RESULT:", "FAIL" if errors else "PASS")
    return 1 if errors else 0
