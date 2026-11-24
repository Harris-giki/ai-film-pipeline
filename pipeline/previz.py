"""Step 07 — one agent-ready Blender brief + shot.json per clip."""
from __future__ import annotations

from pathlib import Path

from .common import ROOT, load_json, save_json
from .scenes import load as load_scenes

BRIEF = """# PREVIZ BRIEF — {id}  ("{action}")

DO NOT MAKE A MOOD BOARD. Do not render check stills, plans or contact sheets and do not stop for
approval. Build the set, animate, and render the final clip straight away.

## WHAT THIS IS FOR
This grey previz is the motion and camera reference (@Video1) for Seedance 2.5 reference-to-video.
Seedance copies its camera path, framing, blocking, poses and timing almost frame for frame. The
prompt does not override it. Scene: {kind}. Location: {location} ({tod}). Camera idea: {camera}.

## WHAT WE LEARNED (numbered failures from earlier renders — append, never delete)
{learned}

## FILES
- Shot spec (edit this): {shot_json}
- Render script: {script}
- Output: {output}
- Location plate (light reference only, NOT rendered): {plate}

## WHAT TO RENDER
{frames} frames, {fps} fps, 1920x1080, one mp4. One continuous camera, never a cut.

## LOOK
Plain grey Workbench (flat/studio lighting). Distinct greys: sky, water, road, buildings, people
(each mannequin its own grey). No textures, no faces, no text.

## THE SET (metres, XYZ, Z up)
Describe every object in `set` with size + location. Line roads with repeating objects (poles, cones,
barriers) so speed reads. Never fly through foliage. Leave clean sky where a title goes and put 3-4
small fixed tracking dots there (`tracking_dots`).

## CHARACTERS
{characters}
Mannequins: neutral faces, no jaw animation, already in the acting pose at frame 1, each a different
build, hair shape and pose, no props, never closer than 2.5 m to camera, never cut by the frame edge.

## CAMERA (timed flight path)
Keyframes of position, look-at, lens 24-35 mm, bank <= 25 deg, >= 5 m clearance from geometry.

## TIMELINE (by second)
{timeline}

## FINAL CHECKS
1. Every mannequin visible and whole at frame 1 and stays >= 2.5 m from the lens.
2. No two mannequins share build + hair + pose.
3. One continuous move, no cuts, no jumps between keys.
4. Title sky (if any) is empty except tracking dots.
5. Output exists, is {frames} frames at {fps} fps, 1920x1080.
"""


def skeleton(scene: dict, chars: dict, out: Path) -> dict:
    builds = ["slim", "average", "heavy", "athletic"]
    hairs = ["long", "short", "ponytail", "cap", "bald"]
    poses = ["stand", "arms_crossed", "point", "walk", "lean"]
    mannequins = []
    for i, c in enumerate(scene.get("cast", [])):
        cd = chars.get(c, {})
        x = -1.2 + 2.4 * i
        mannequins.append({
            "name": c, "height": cd.get("height", 1.75),
            "build": cd.get("build_class", builds[i % len(builds)]),
            "hair": cd.get("hair_shape", hairs[i % len(hairs)]),
            "pose": poses[i % len(poses)],
            "keys": [{"t": 0, "pos": [x, 0, 0], "yaw": 180}, {"t": 10, "pos": [x, 0, 0], "yaw": 180}],
        })
    return {
        "id": scene["id"], "fps": 24, "duration": scene.get("duration", 10), "resolution": [1920, 1080],
        "output": str(out),
        "greys": {"sky": 0.78, "water": 0.42, "road": 0.30, "ground": 0.55, "building": 0.65, "prop": 0.2},
        "set": [
            {"name": "ground", "type": "plane", "size": [200, 200], "location": [0, 0, 0], "grey": "ground"},
        ],
        "mannequins": mannequins,
        "vehicles": [],
        "camera": {"keys": [
            {"t": 0, "pos": [0, -8, 1.6], "look_at": [0, 0, 1.4], "lens": 28, "bank": 0},
            {"t": 10, "pos": [0, -6, 1.7], "look_at": [0, 0, 1.4], "lens": 28, "bank": 0},
        ]},
        "tracking_dots": [],
        "learned": [],
    }


def write_brief(proj: Path, sid: str) -> int:
    scenes, chars, _ = load_scenes(proj)
    scene = next((s for s in scenes if s["id"] == sid), None)
    if not scene:
        print(f"no scene {sid}")
        return 1
    d = proj / "06_previz" / sid
    d.mkdir(parents=True, exist_ok=True)
    shot_json = d / "shot.json"
    out = d / "previz.mp4"
    shot = load_json(shot_json, {}) or skeleton(scene, chars, out)
    save_json(shot_json, shot)
    learned = shot.get("learned") or []
    chars_txt = "\n".join(
        f"- {m['name']}: height {m['height']} m, build {m['build']}, hair {m['hair']}, pose {m['pose']}, "
        f"start {m['keys'][0]['pos']}" for m in shot["mannequins"]) or "- none"
    timeline = "\n".join(f"- {s}s: " for s in range(0, int(shot["duration"]) + 1))
    (d / "brief.md").write_text(BRIEF.format(
        id=sid, action=scene.get("action", ""), kind=scene.get("kind"), location=scene.get("location"),
        tod=scene.get("tod"), camera=scene.get("camera", ""),
        learned="\n".join(f"{i}. {t}" for i, t in enumerate(learned, 1)) or "(none yet)",
        shot_json=shot_json, script=ROOT / "blender" / "previz.py", output=out,
        plate=proj / "05_plates" / f"{scene.get('location')}_{scene.get('tod')}.png",
        frames=int(shot["duration"] * shot["fps"]), fps=shot["fps"], characters=chars_txt,
        timeline=timeline))
    print(f"wrote {d/'brief.md'} and {shot_json}")
    return 0
