"""Steps 07-08 — grey Workbench previz from a shot.json, rendered headless.

  blender -b -P blender/previz.py -- projects/<film>/06_previz/<ID>/shot.json [--force]

Refuses shots that break the previz rules (mannequin < 2.5 m from lens, identical mannequins,
mannequin cut by the frame edge at frame 1, bank > 25 deg, lens outside 24-35 mm, camera < 5 m
from set boxes) unless --force. Renders a PNG sequence and assembles one mp4 with ffmpeg, so it
works the same on Blender 4.x and 5.x. Run ONE Blender at a time.
"""
import json
import math
import os
import shutil
import subprocess
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    print("usage: blender -b -P previz.py -- shot.json [--force]")
    sys.exit(1)
SHOT_PATH = os.path.abspath(argv[0])
FORCE = "--force" in argv
shot = json.load(open(SHOT_PATH))
GREYS = {"sky": 0.78, "water": 0.42, "road": 0.30, "ground": 0.55, "building": 0.65, "prop": 0.2, **shot.get("greys", {})}
FPS = shot.get("fps", 24)
DUR = shot.get("duration", 10)
N = int(round(DUR * FPS))
RX, RY = shot.get("resolution", [1920, 1080])
OUT = os.path.abspath(shot.get("output") or os.path.join(os.path.dirname(SHOT_PATH), "previz.mp4"))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, N
scene.render.resolution_x, scene.render.resolution_y = RX, RY
scene.render.resolution_percentage = 100
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light = "STUDIO"
sh.color_type = "OBJECT"
sh.show_shadows = True
sh.show_cavity = False
world = bpy.data.worlds.new("sky")
world.color = (GREYS["sky"],) * 3
scene.world = world
scene.view_settings.view_transform = "Standard"

set_boxes = []


def grey(name_or_value):
    v = GREYS.get(name_or_value, name_or_value) if isinstance(name_or_value, str) else name_or_value
    return (v, v, v, 1.0)


def add_obj(o, g):
    if o["type"] == "plane":
        bpy.ops.mesh.primitive_plane_add(size=1, location=o["location"])
        ob = bpy.context.object
        ob.scale = (o["size"][0], o["size"][1], 1)
    elif o["type"] == "box":
        loc = list(o["location"])
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        ob = bpy.context.object
        ob.scale = o["size"]
        set_boxes.append((Vector(loc), Vector(o["size"]) / 2))
    elif o["type"] == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(radius=o["size"][0], depth=o["size"][1], location=o["location"])
        ob = bpy.context.object
    elif o["type"] == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=o["size"][0], location=o["location"])
        ob = bpy.context.object
    else:
        raise ValueError(f"unknown set type {o['type']}")
    ob.rotation_euler = Euler([math.radians(a) for a in o.get("rotation_deg", [0, 0, 0])])
    ob.color = grey(g)
    ob.name = o.get("name", o["type"])
    return ob


for o in shot.get("set", []):
    if o["type"] == "repeat":  # line roads with repeating objects so speed reads
        for i in range(o["count"]):
            sub = dict(o["object"])
            sub["location"] = [o["start"][k] + o["step"][k] * i for k in range(3)]
            add_obj(sub, o.get("grey", "prop"))
    else:
        add_obj(o, o.get("grey", "building"))

BUILD_W = {"slim": 0.85, "average": 1.0, "athletic": 1.1, "heavy": 1.3}


def mannequin(m, idx):
    h = m.get("height", 1.75)
    w = BUILD_W.get(m.get("build", "average"), 1.0)
    parts = []
    def prim(kind, loc, scale, rot=(0, 0, 0)):
        if kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=loc, segments=24, ring_count=12)
        elif kind == "cyl":
            bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, location=loc, vertices=16)
        else:
            bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        ob = bpy.context.object
        ob.scale = scale
        ob.rotation_euler = Euler([math.radians(r) for r in rot])
        parts.append(ob)
    head_r = h * 0.065
    leg_h = h * 0.47
    torso_h = h * 0.32
    sw = 0.2 * w
    # legs
    pose = m.get("pose", "stand")
    stride = 12 if pose == "walk" else 0
    for s in (-1, 1):
        prim("cyl", (s * sw * 0.45, 0, leg_h / 2), (0.07 * w, 0.07 * w, leg_h), (s * stride, 0, 0))
    # torso + hips
    prim("cyl", (0, 0, leg_h + torso_h / 2), (sw, 0.13 * w, torso_h))
    # neck + head
    prim("cyl", (0, 0, leg_h + torso_h + 0.04), (0.05, 0.05, 0.08))
    hz = leg_h + torso_h + 0.08 + head_r
    prim("sphere", (0, 0, hz), (head_r * 0.9, head_r, head_r * 1.12))
    # arms per pose (distinct silhouettes)
    arm_l = h * 0.33
    shoulder = leg_h + torso_h - 0.05
    arms = {"stand": (8, -8), "arms_crossed": (70, -70), "point": (85, -8), "walk": (-20, 20), "lean": (30, -5), "drive": (60, 60)}
    al, ar = arms.get(pose, (8, -8))
    for s, ang in ((-1, al), (1, ar)):
        prim("cyl", (s * (sw + 0.05), -math.sin(math.radians(ang)) * arm_l / 2, shoulder - math.cos(math.radians(ang)) * arm_l / 2),
             (0.045 * w, 0.045 * w, arm_l), (ang, 0, 0))
    # hair shape
    hair = m.get("hair", "short")
    if hair == "long":
        prim("sphere", (0, 0.04, hz - head_r * 0.6), (head_r * 1.0, head_r * 0.7, head_r * 1.8))
    elif hair == "ponytail":
        prim("sphere", (0, 0.11, hz + head_r * 0.2), (head_r * 0.35, head_r * 0.6, head_r * 0.35))
    elif hair == "cap":
        prim("cyl", (0, 0, hz + head_r * 0.7), (head_r * 1.02, head_r * 1.02, head_r * 0.5))
        prim("cube", (0, -head_r * 1.1, hz + head_r * 0.55), (head_r * 1.6, head_r * 1.2, 0.01))
    elif hair == "short":
        prim("sphere", (0, 0.01, hz + head_r * 0.25), (head_r * 0.98, head_r * 1.02, head_r * 0.9))
    # join into one object
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.object
    ob.name = m["name"]
    ob.color = grey(0.88 - 0.12 * (idx % 5))  # each mannequin its own grey
    for k in m["keys"]:
        f = 1 + k["t"] * FPS
        ob.location = k["pos"]
        ob.rotation_euler = (0, 0, math.radians(k.get("yaw", 0)))
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
    return ob


mans = [mannequin(m, i) for i, m in enumerate(shot.get("mannequins", []))]

for v in shot.get("vehicles", []):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob = bpy.context.object
    ob.name = v["name"]
    ob.scale = v.get("size", [4.5, 1.9, 1.4])
    ob.color = grey(v.get("grey", 0.35))
    for k in v["keys"]:
        ob.location = [k["pos"][0], k["pos"][1], k["pos"][2] + ob.scale[2] / 2]
        ob.rotation_euler = (0, 0, math.radians(k.get("yaw", 0)))
        ob.keyframe_insert("location", frame=1 + k["t"] * FPS)
        ob.keyframe_insert("rotation_euler", frame=1 + k["t"] * FPS)

for p in shot.get("tracking_dots", []):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=p[3] if len(p) > 3 else 0.4, location=p[:3])
    bpy.context.object.color = grey(0.1)

# camera: timed flight path with look-at and bank
cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.sensor_width = 36
errors = []
for k in shot["camera"]["keys"]:
    f = 1 + k["t"] * FPS
    pos, look = Vector(k["pos"]), Vector(k["look_at"])
    q = (look - pos).to_track_quat("-Z", "Y")
    bank = k.get("bank", 0)
    eul = q.to_euler()
    cam.location = pos
    cam.rotation_mode = "QUATERNION"
    from mathutils import Quaternion
    cam.rotation_quaternion = q @ Quaternion((0, 0, 1), math.radians(bank))
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_quaternion", frame=f)
    cam_data.lens = k.get("lens", 28)
    cam_data.keyframe_insert("lens", frame=f)
    if abs(bank) > 25:
        errors.append(f"camera key t={k['t']}: bank {bank} > 25 deg")
    if not 24 <= k.get("lens", 28) <= 35:
        errors.append(f"camera key t={k['t']}: lens {k.get('lens')} outside 24-35 mm")

# ---- rule checks across the shot
sig = [(m.get("build"), m.get("hair"), m.get("pose")) for m in shot.get("mannequins", [])]
if len(set(sig)) != len(sig):
    errors.append("two mannequins share build + hair + pose (the model will paint the same person twice)")
if len(sig) > 7:
    errors.append(f"{len(sig)} mannequins; cut the cast to seven or fewer")
close = {}   # name -> [first frame, last frame, min distance]
setclose = None


def note(store, key, f, d):
    cur = store.get(key)
    store[key] = [f, f, d] if cur is None else [cur[0], f, min(cur[2], d)]


for f in range(1, N + 1, 2):
    scene.frame_set(f)
    cp = cam.matrix_world.translation
    for ob in mans:
        d = (ob.matrix_world.translation - cp).length
        if d < 2.5:
            note(close, ob.name, f, d)
    if not shot.get("allow_close_set"):
        for c, half in set_boxes:
            closest = Vector([max(c[i] - half[i], min(cp[i], c[i] + half[i])) for i in range(3)])
            d = (closest - cp).length
            if d < 5:
                setclose = [f, f, d] if setclose is None else [setclose[0], f, min(setclose[2], d)]
for name, (a, b, d) in close.items():
    errors.append(f"{name} closer than 2.5 m to the lens around frames {a}-{b} (closest {d:.2f} m)")
if setclose:
    errors.append(f"camera within 5 m of set geometry around frames {setclose[0]}-{setclose[1]} (closest {setclose[2]:.2f} m)")
scene.frame_set(1)
for ob in mans:
    for corner in ob.bound_box:
        co = world_to_camera_view(scene, cam, ob.matrix_world @ Vector(corner))
        if co.z > 0 and not (0 <= co.x <= 1 and 0 <= co.y <= 1):
            errors.append(f"frame 1: {ob.name} is cut by the frame edge")
            break
errors = list(dict.fromkeys(errors))
if errors:
    print("\nPREVIZ RULE CHECK:")
    for e in errors:
        print("  ERROR", e)
    if not FORCE:
        print("Refusing to render. Fix shot.json (or --force).")
        sys.exit(2)

# ---- render PNG sequence then one mp4
blend = os.path.splitext(OUT)[0] + ".blend"
bpy.ops.wm.save_as_mainfile(filepath=blend)
tmp = os.path.splitext(OUT)[0] + "_frames"
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = os.path.join(tmp, "f_")
bpy.ops.render.render(animation=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-start_number", "1",
                "-i", os.path.join(tmp, "f_%04d.png"), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", OUT], check=True)
shutil.rmtree(tmp, ignore_errors=True)
print(f"PREVIZ OK -> {OUT} ({N} frames @ {FPS} fps, {RX}x{RY}); scene saved {blend}")
