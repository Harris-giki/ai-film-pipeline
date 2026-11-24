"""Steps 05-06 — character sheet and location plate prompts (LOOK + one shot line)."""
from __future__ import annotations

from pathlib import Path

from .common import load_json
from .look import with_look

BACKDROP = "Seamless dark grey studio backdrop, even soft key light, neutral relaxed pose."


def portrait_prompt(name: str, c: dict, outfit: str, garments: str) -> str:
    return with_look(
        f"Keep the neutral studio light even and true to skin tone for {name}'s reference portrait.",
        f"Single 4:5 portrait of one original character named {name}: {c.get('age', 'adult')}, "
        f"{c.get('build', '')} build, {c.get('hair', '')}, {c.get('face', '')}. "
        f"Wearing ({outfit}): {garments}. Head and shoulders, facing camera, neutral expression. "
        f"{BACKDROP} No text, no logos, no watermark.")


def sheet2_prompt(name: str, outfit: str) -> str:
    return with_look(
        f"Keep the neutral studio light even across all six tiles of {name}'s face sheet.",
        f"Six-tile headshot sheet of the person in @Image1 ({name}, outfit '{outfit}'), 3 columns x 2 rows, "
        "16:9, same scale and lighting in every tile: row 1 neutral front, three-quarter, profile; "
        "row 2 smirk, shout, grin. Head and shoulders only, nothing below the collarbone. "
        f"{BACKDROP} Identical face, hair and clothing in all tiles. No text, no labels, no logos.")


def sheet1_prompt(name: str, c: dict, outfit: str, garments: str) -> str:
    return with_look(
        f"Keep the neutral studio light even from head to shoe soles for {name}'s turnaround.",
        f"Full-body turnaround sheet of the person in @Image1 and @Image2 ({name}), 16:9, four views "
        "side by side at the same scale: front, three-quarter, profile, back. Head to shoe soles fully "
        f"visible in every view, height {c.get('height', 1.75)} m. Outfit '{outfit}', garment by garment: "
        f"{garments}. {BACKDROP} Same identity as the face sheet. No text, no labels, no logos.")


def variant_note(name: str, outfit: str) -> str:
    return (f"OUTFIT VARIANT for {name} -> '{outfit}': edit from BOTH existing sheets of the base outfit "
            "(pass them as references) and change only the clothing. If the variant adds headwear, "
            "also regenerate a matching face sheet.")


def plate_prompt(loc: str, l: dict, tod: str) -> str:
    return with_look(
        f"Keep the {tod} light of {l.get('desc', loc)} as the plate's grade; brightness and palette come from here.",
        f"Empty-set location plate: {l.get('desc', loc)}, {tod}. 16:9, 4K. Camera height "
        f"{l.get('camera_height_m', 1.6)} m, {l.get('plate_angle', 'wide establishing angle from a different side than any planned shot')}. "
        "No people, no vehicles unless listed, no readable text, no signs with words, no logos.")


def vehicle_prompt(name: str, desc: str) -> str:
    return with_look(
        "Keep neutral studio light even across all four views.",
        f"Four-view vehicle sheet of an original vehicle '{name}': {desc}. Front, rear, left side, right "
        "side at the same scale, 16:9. Seamless dark grey backdrop. No badges, no logos, no plates, no text.")


def write_sheet_prompts(proj: Path) -> int:
    chars = load_json(proj / "03_scenes" / "characters.json")
    n = 0
    for name, c in chars.items():
        outfits = c.get("outfits", {})
        base = c.get("base_outfit") or next(iter(outfits), None)
        for outfit, garments in outfits.items():
            d = proj / "04_sheets" / name / outfit
            d.mkdir(parents=True, exist_ok=True)
            if outfit == base:
                (d / "prompt_1_portrait_4x5.txt").write_text(portrait_prompt(name, c, outfit, garments))
                (d / "prompt_2_sheet2_face.txt").write_text(sheet2_prompt(name, outfit) +
                                                            "\n\nREFS: @Image1 = portrait_4x5.png (NOT the turnaround)\n")
                (d / "prompt_3_sheet1_full.txt").write_text(sheet1_prompt(name, c, outfit, garments) +
                                                            "\n\nREFS: @Image1 = portrait_4x5.png, @Image2 = sheet2_face.png\n")
            else:
                (d / "prompt_variant.txt").write_text(
                    variant_note(name, outfit) + "\n\n" + sheet1_prompt(name, c, outfit, garments) +
                    f"\n\nREFS: @Image1 = ../{base}/sheet2_face.png, @Image2 = ../{base}/sheet1_full.png\n")
            n += 1
    for vname, desc in load_json(proj / "03_scenes" / "vehicles.json", {}).items():
        d = proj / "04_sheets" / f"VEH_{vname}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "prompt_fourview.txt").write_text(vehicle_prompt(vname, desc))
        n += 1
    print(f"wrote prompts for {n} character/outfit/vehicle sets under 04_sheets/")
    return 0


def write_plate_prompts(proj: Path) -> int:
    locs = load_json(proj / "03_scenes" / "locations.json")
    d = proj / "05_plates"
    d.mkdir(parents=True, exist_ok=True)
    n = 0
    for loc, l in locs.items():
        for tod in l.get("tods", ["day"]):
            (d / f"{loc}_{tod}.prompt.txt").write_text(plate_prompt(loc, l, tod))
            n += 1
    print(f"wrote {n} plate prompts under 05_plates/")
    return 0
