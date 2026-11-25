"""Steps 09-10 — Seedance 2.5 reference-to-video prompts: skeleton, build, lint."""
from __future__ import annotations

import re
from pathlib import Path

from .common import load_json, save_json
from .style import load as load_style
from .scenes import load as load_scenes

# LIGHTING was added after studying a top-tier reference trailer: every shot there has its own motivated
# light (neon, practicals, golden hour, fluorescent), while one blanket LOOK made all of SUNSHINE look alike.
SECTIONS = ["FORMAT", "REFERENCE ROLES", "THE LOCATION AND WHO IS WHERE", "THE PEOPLE", "FRAMING",
            "EYE LINE", "MOUTH", "TIMELINE", "CAMERA", "LIGHTING", "PACE", "PERFORMANCE", "CONTINUITY", "AUDIO",
            "LOOK", "CONSTRAINTS"]
PREVIZ_SECTIONS = ["FORMAT", "REFERENCE ROLES", "WHAT THE PREVIZ SHOWS", "THE PEOPLE", "MOUTH",
                   "PERFORMANCE", "LIGHTING", "AUDIO", "LOOK", "CONSTRAINTS"]

NO_CUTS = [
    "One continuous shot from the first frame to the last frame.",
    "No cuts, no edits, no scene changes, no transitions.",
    "The camera never jumps to a new angle; it moves only as described.",
]
AUDIO_DEFAULT = ("Rich natural scene sound for this location and action. No music. No risers, no whooshes, "
                 "no hits, no stingers. No breaths, no gasps, no laughs, no sighs, no human non-speech sounds.")


def references(proj: Path, scene: dict) -> list[dict]:
    """Upload order (step 11): Video1 previz, Image01+ plates, then face sheet + full sheet per person."""
    refs = []
    pv = proj / "06_previz" / scene["id"] / "previz.mp4"
    if scene.get("previz") and pv.exists():
        refs.append({"tag": "@Video1", "file": str(pv), "role": "camera path, framing, positions, poses and timing"})
    n = 1
    plates = [scene.get("location") + "_" + scene.get("tod")] + scene.get("extra_plates", [])
    for p in plates:
        refs.append({"tag": f"@Image{n}", "file": str(proj / "05_plates" / f"{p}.png"), "role": f"location and light ({p})"})
        n += 1
    for c in scene.get("cast", []):
        o = scene.get("outfit", {}).get(c, "")
        base = proj / "04_sheets" / c / o
        refs.append({"tag": f"@Image{n}", "file": str(base / "sheet2_face.png"), "role": f"{c} face and identity", "who": c})
        refs.append({"tag": f"@Image{n+1}", "file": str(base / "sheet1_full.png"), "role": f"{c} full body and outfit", "who": c})
        n += 2
    for v in scene.get("vehicles", []):
        refs.append({"tag": f"@Image{n}", "file": str(proj / "04_sheets" / f"VEH_{v}" / "fourview.png"), "role": f"vehicle {v}"})
        n += 1
    return refs


def skeleton(proj: Path, scene: dict) -> dict:
    refs = references(proj, scene)
    has_previz = any(r["tag"] == "@Video1" for r in refs)
    secs = PREVIZ_SECTIONS if has_previz else SECTIONS
    s = {k: "" for k in secs}
    st = load_style(proj)
    s["FORMAT"] = f"{scene.get('duration', 10)} seconds, 16:9, 24 fps. Style: {st['label']}. {st['motion']}"
    by_who: dict[str, list[str]] = {}
    for r in refs:
        if "who" in r:
            by_who.setdefault(r["who"], []).append(r["tag"])
    roles = [f"{r['tag']} is {r['role']}." for r in refs if "who" not in r]
    roles += [f"{' and '.join(t)} control {w}." for w, t in by_who.items()]
    if has_previz:
        roles.append("The grey figures in @Video1 are layout only; every person is fully dressed in the listed outfit.")
    s["REFERENCE ROLES"] = " ".join(roles)
    s["AUDIO"] = AUDIO_DEFAULT
    s["LOOK"] = st["look"]
    s["CONSTRAINTS"] = " ".join(NO_CUTS) + " Each action happens once. " + st["constraints"]
    if "LIGHTING" in s:
        s["LIGHTING"] = scene.get("lighting", "")
    if "CAMERA" in s and scene.get("camera"):
        s["CAMERA"] = scene["camera"]
    if "FRAMING" in s and scene.get("lens"):
        s["FRAMING"] = scene["lens"]
    if "TIMELINE" in s:
        s["TIMELINE"] = " ".join(f"{t} s:" for t in range(0, int(scene.get("duration", 10)) + 1, 2))
    if scene.get("lines"):
        s["MOUTH"] = " ".join(f"{l['who']} says: \"{l['text']}\"" for l in scene["lines"]) + \
            " Only the speaker's lips move."
    else:
        s["MOUTH"] = "Nobody speaks. Mouths stay closed."
    return {"id": scene["id"], "previz": has_previz, "references": refs, "sections": s, "last_frame": ""}


def render(p: dict) -> str:
    out = []
    for k, v in p["sections"].items():
        out.append(f"{k}: {v.strip()}")
    if p.get("last_frame"):
        out.append(f"LAST FRAME: {p['last_frame'].strip()}")
    return "\n\n".join(out) + "\n"


def lint(p: dict, text: str, chars: list[str], st: dict | None = None) -> list[str]:
    st = st or load_style(None)
    errs = []
    order = PREVIZ_SECTIONS if p["previz"] else SECTIONS
    if list(p["sections"].keys()) != order:
        errs.append(f"section order must be: {', '.join(order)}")
    for k, v in p["sections"].items():
        if not v.strip() or re.search(r"\b\d+ s:\s*(\d+ s:|$)", v):
            errs.append(f"section {k} is empty or has unfilled timeline seconds")
    if re.search("[\u2013\u2014]", text):
        errs.append("contains en/em dashes")
    for line in NO_CUTS:
        if line not in text:
            errs.append(f"missing no-cuts line: {line}")
    if st["look"] not in text:
        errs.append(f"{st['id']} LOOK block missing or paraphrased")
    if st["constraints"] not in text:
        errs.append(f"{st['id']} style constraints missing from CONSTRAINTS")
    if "LIGHTING" in p["sections"] and len(p["sections"]["LIGHTING"].split()) < 6:
        errs.append("LIGHTING must name the motivated light sources, direction and colour for this shot")
    tags = {r["tag"] for r in p["references"]}
    used = set(re.findall(r"@(?:Image\d+|Video\d+)", text))
    for t in used - tags:
        errs.append(f"{t} used but not in reference list")
    for t in tags:
        if t not in p["sections"].get("REFERENCE ROLES", ""):
            errs.append(f"{t} not bound in REFERENCE ROLES")
    if not p.get("last_frame"):
        errs.append("no described LAST FRAME")
    for r in p["references"]:
        if not Path(r["file"]).exists():
            errs.append(f"reference file missing: {r['file']}")
    for c in chars:
        if c not in text:
            errs.append(f"character {c} never named (one name per character, used consistently)")
    if p["previz"] and re.search(r"\b(raises?|lifts?|turns?|holds?)\b.*\b(arm|hand|head)\b", p["sections"].get("PERFORMANCE", ""), re.I):
        errs.append("WARN: previz owns poses; do not fix a pose with wording")
    return errs


def cmd(proj: Path, sid: str, build: bool, lint_only: bool) -> int:
    scenes, _, _ = load_scenes(proj)
    scene = next((s for s in scenes if s["id"] == sid), None)
    if not scene:
        print(f"no scene {sid}")
        return 1
    d = proj / "07_upload" / sid
    pj = d / "prompt.json"
    if not pj.exists():
        save_json(pj, skeleton(proj, scene))
        print(f"wrote skeleton {pj}; fill the sections, then run with --build")
        return 0
    p = load_json(pj)
    text = render(p)
    errs = lint(p, text, scene.get("cast", []), load_style(proj))
    hard = [e for e in errs if not e.startswith("WARN")]
    for e in errs:
        print(("WARN " if e.startswith("WARN") else "LINT ") + e.removeprefix("WARN: "))
    if build and not hard:
        (d / "prompt.txt").write_text(text)
        print(f"wrote {d/'prompt.txt'}\n" + "=" * 60 + "\n" + text + "=" * 60)
    print("RESULT:", "FAIL" if hard else "PASS")
    return 1 if hard else 0
