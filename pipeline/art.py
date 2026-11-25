"""Steps 05-06: character sheet, location plate and vehicle prompts, written in the film's style.

Every prompt = the style's LOOK block (verbatim) + one shot-specific line + a body that describes the
subject in the style's own medium (a real person, a plasticine puppet, a pixel sprite, a paper puppet...).
"""
from __future__ import annotations

from pathlib import Path

from .common import load_json
from .look import with_look
from .style import load as load_style


def _desc(c: dict) -> str:
    return ", ".join(x for x in (c.get("age", ""), f"{c['build']} build" if c.get("build") else "",
                                 c.get("hair", ""), c.get("face", "")) if x)


def portrait_prompt(st: dict, name: str, c: dict, outfit: str, garments: str) -> str:
    return with_look(st["look"],
        f"Keep the reference light even and true to colour for {name}'s portrait.",
        f"Single 4:5 portrait of {st['character_medium']}, named {name}: {_desc(c)}. "
        f"Wearing ({outfit}): {garments}. Head and shoulders, facing camera, neutral expression. "
        f"{st['sheet_backdrop']} No text, no logos, no watermark.")


def sheet2_prompt(st: dict, name: str, outfit: str, garments: str = "", variant: bool = False) -> str:
    head = (f"Edit of the six-tile face sheet in @Image1: keep the exact same character {name}, same face, hair, expressions, "
            f"layout and lighting; change only the clothing to outfit '{outfit}': {garments}. " if variant else
            f"Six-tile face sheet of the character in @Image1 ({name}, outfit '{outfit}'). ")
    return with_look(st["look"],
        f"Keep the reference light even across all six tiles of {name}'s face sheet.",
        head + "3 columns x 2 rows, 16:9, same scale and lighting in every tile: row 1 neutral front, three-quarter, "
        "profile; row 2 smirk, shout, grin. Head and shoulders only, nothing below the collarbone. "
        f"{st['sheet_backdrop']} Identical face and design in all tiles. No text, no labels, no logos.")


def sheet1_prompt(st: dict, name: str, c: dict, outfit: str, garments: str, variant: bool = False) -> str:
    head = (f"Edit of the full-body turnaround in @Image2: keep the exact same character {name}, same face as @Image1, "
            "same four views, scale, pose and lighting; change only the clothing. " if variant else
            f"Full-body turnaround sheet of the character in @Image1 and @Image2 ({name}). ")
    return with_look(st["look"],
        f"Keep the reference light even from head to feet for {name}'s turnaround.",
        head + "16:9, four views side by side at the same scale: front, three-quarter, profile, back. Head to feet fully "
        f"visible in every view, height {c.get('height', 1.75)} m in proportion. Outfit '{outfit}', garment by garment: "
        f"{garments}. {st['sheet_backdrop']} Same identity as the face sheet. No text, no labels, no logos.")


def card_prompt(st: dict, name: str, c: dict, outfit: str, garments: str) -> str:
    """One-image reference for a vignette character who appears in a single setup (a third of the cost of
    portrait + face sheet + turnaround, and enough for consistency within one shot)."""
    return with_look(st["look"],
        f"Keep the reference light even and true to colour for {name}'s character card.",
        f"Character card, 16:9, of {st['character_medium']}, named {name}: {_desc(c)}. Left half: one full-body front view, "
        f"head to feet, height {c.get('height', 1.75)} m in proportion. Right half: two head-and-shoulders close-ups of the same "
        f"face, neutral front and three-quarter. Wearing ({outfit}): {garments}. {st['sheet_backdrop']} "
        "Identical identity in all three views. No text, no labels, no logos.")


def plate_prompt(st: dict, loc: str, l: dict, tod: str) -> str:
    return with_look(st["look"],
        f"Keep the {tod} light of {l.get('desc', loc)} as the plate's grade; brightness and palette come from here.",
        f"Empty-set location plate, {st['plate_medium']}: {l.get('desc', loc)}, {tod}. 16:9. Camera height "
        f"{l.get('camera_height_m', 1.6)} m, {l.get('plate_angle', 'wide establishing angle from a different side than any planned shot')}. "
        "No characters, no vehicles unless listed, no readable text, no signs with words, no logos.")


def vehicle_prompt(st: dict, name: str, desc: str) -> str:
    return with_look(st["look"],
        "Keep the reference light even across all four views.",
        f"Four-view sheet of {st['vehicle_medium']}, an original vehicle '{name}': {desc}. Front, rear, left side, right "
        f"side at the same scale, 16:9. {st['sheet_backdrop']} No badges, no logos, no plates, no text.")


def write_sheet_prompts(proj: Path) -> int:
    st = load_style(proj)
    chars = load_json(proj / "03_scenes" / "characters.json")
    n = 0
    for name, c in chars.items():
        outfits = c.get("outfits", {})
        base = c.get("base_outfit") or next(iter(outfits), None)
        for outfit, garments in outfits.items():
            d = proj / "04_sheets" / name / outfit
            d.mkdir(parents=True, exist_ok=True)
            if c.get("role") == "vignette":
                (d / "prompt_card.txt").write_text(card_prompt(st, name, c, outfit, garments) + "\n\nREFS: none (text to image)\n")
            elif outfit == base:
                (d / "prompt_1_portrait_4x5.txt").write_text(portrait_prompt(st, name, c, outfit, garments))
                (d / "prompt_2_sheet2_face.txt").write_text(sheet2_prompt(st, name, outfit) +
                    "\n\nREFS: @Image1 = portrait_4x5.png (NOT the turnaround)\n")
                (d / "prompt_3_sheet1_full.txt").write_text(sheet1_prompt(st, name, c, outfit, garments) +
                    "\n\nREFS: @Image1 = portrait_4x5.png, @Image2 = sheet2_face.png\n")
            else:
                (d / "prompt_variant_sheet2_face.txt").write_text(sheet2_prompt(st, name, outfit, garments, variant=True) +
                    f"\n\nREFS: @Image1 = ../{base}/sheet2_face.png\n")
                (d / "prompt_variant_sheet1_full.txt").write_text(sheet1_prompt(st, name, c, outfit, garments, variant=True) +
                    f"\n\nREFS: @Image1 = ../{base}/sheet2_face.png, @Image2 = ../{base}/sheet1_full.png\n")
            n += 1
    for vname, desc in load_json(proj / "03_scenes" / "vehicles.json", {}).items():
        d = proj / "04_sheets" / f"VEH_{vname}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "prompt_fourview.txt").write_text(vehicle_prompt(st, vname, desc))
        n += 1
    print(f"[{st['id']}] wrote prompts for {n} character/outfit/vehicle sets under 04_sheets/")
    return 0


def write_plate_prompts(proj: Path) -> int:
    st = load_style(proj)
    locs = load_json(proj / "03_scenes" / "locations.json")
    d = proj / "05_plates"
    d.mkdir(parents=True, exist_ok=True)
    n = 0
    for loc, l in locs.items():
        for tod in l.get("tods", ["day"]):
            (d / f"{loc}_{tod}.prompt.txt").write_text(plate_prompt(st, loc, l, tod))
            n += 1
    print(f"[{st['id']}] wrote {n} plate prompts under 05_plates/")
    return 0
