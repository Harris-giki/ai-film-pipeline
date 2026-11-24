"""Step 19 — render one title word as a poured metallic mesh (transparent PNG).

  blender -b -P blender/title.py -- --text WORD --font path/to/font.otf --out projects/<film>/10_finish/titles/WORD

Settings follow the method: text curve bevel 0.055 / offset -0.0715, join, voxel remesh 0.011,
Smooth 0.9 x 9, Subsurf 1; Principled BSDF #ff78c0 metallic 1.0 roughness 0.03; colour-ramp world
(peach sky, violet floor, strength 1.8), no HDRI; four area lights; 85 mm; Cycles 2400x1200,
160 samples, transparent film, view transform Standard. One Blender at a time (parallel runs fail silently).
"""
import argparse
import math
import sys

import bpy

ap = argparse.ArgumentParser()
ap.add_argument("--text", required=True)
ap.add_argument("--font", default=None)
ap.add_argument("--out", required=True)
ap.add_argument("--tracking", type=float, default=0.125)
ap.add_argument("--samples", type=int, default=160)
ap.add_argument("--colour", default="ff78c0")
ap.add_argument("--offset", type=float, default=-0.0715)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

font = bpy.data.fonts.load(a.font) if a.font else None


def build(offset):
    curve = bpy.data.curves.new("title", "FONT")
    curve.body = a.text
    if font:
        curve.font = font
    curve.align_x, curve.align_y = "CENTER", "CENTER"
    curve.space_character = 1 + a.tracking
    curve.space_word = 0.55            # word gap pulled in 45 percent
    curve.extrude = 0.08
    curve.bevel_depth = 0.055
    curve.offset = offset
    o = bpy.data.objects.new("title", curve)
    sc.collection.objects.link(o)
    o.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.view_layer.update()
    ref_h = o.dimensions.z if o.dimensions.z else o.dimensions.y   # curve height before conversion
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.object
    bpy.context.view_layer.update()
    return o, ref_h


ob, _ = build(a.offset)
# A negative offset on a stock font's acute corners (M, V, W, A...) throws spikes out of the glyph.
# The method's own font has round joins and never does this. A shrinking offset must make the word
# smaller than offset 0; if it comes out taller, those are spikes: rebuild with offset 0.
if a.offset < 0:
    probe, _ = build(0.0)
    h_neg, h_zero = ob.dimensions.y, probe.dimensions.y   # local text space: y = height
    bpy.data.objects.remove(probe)
    if h_neg > h_zero + 0.01:
        print(f"WARN offset {a.offset} spiked the mesh ({h_neg:.3f} > {h_zero:.3f} at offset 0); using offset 0")
        bpy.data.objects.remove(ob)
        ob, _ = build(0.0)
bpy.context.view_layer.objects.active = ob
rm = ob.modifiers.new("remesh", "REMESH"); rm.mode = "VOXEL"; rm.voxel_size = 0.011
sm = ob.modifiers.new("smooth", "SMOOTH"); sm.factor = 0.9; sm.iterations = 9
ss = ob.modifiers.new("subsurf", "SUBSURF"); ss.levels = 1; ss.render_levels = 1
bpy.ops.object.shade_smooth()

mat = bpy.data.materials.new("chrome")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
r, g, b = (int(a.colour[i:i + 2], 16) / 255 for i in (0, 2, 4))
bsdf.inputs["Base Color"].default_value = (r ** 2.2, g ** 2.2, b ** 2.2, 1)
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Roughness"].default_value = 0.03
ob.data.materials.append(mat)

# colour-ramp world: peach sky -> violet floor, strength 1.8 (no HDRI)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
tex = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
mr = nt.nodes.new("ShaderNodeMapRange"); ramp = nt.nodes.new("ShaderNodeValToRGB")
bg = nt.nodes.new("ShaderNodeBackground"); out = nt.nodes.new("ShaderNodeOutputWorld")
mr.inputs["From Min"].default_value = -1; mr.inputs["From Max"].default_value = 1
ramp.color_ramp.elements[0].color = (0.32, 0.12, 0.55, 1)    # violet floor
ramp.color_ramp.elements[1].color = (1.0, 0.62, 0.45, 1)     # peach sky
bg.inputs["Strength"].default_value = 1.8
nt.links.new(tex.outputs["Normal"], sep.inputs[0])   # view direction: up = sky, down = floor
nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

for i, (x, z, e) in enumerate([(-4, 3, 600), (4, 3, 600), (0, -3, 300), (0, 5, 400)]):
    ld = bpy.data.lights.new(f"area{i}", "AREA"); ld.energy = e; ld.size = 3
    lo = bpy.data.objects.new(f"area{i}", ld); sc.collection.objects.link(lo)
    lo.location = (x, -6, z)
    lo.rotation_euler = (math.radians(90) - math.atan2(z, 6), 0, math.atan2(x, 6) * -1)

cd = bpy.data.cameras.new("cam"); cd.lens = 85
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
dims = ob.dimensions
dist = max(dims.x, dims.z * 2) * 85 / 36 * 1.15 + 1
cam.location = (0, -dist, 0); cam.rotation_euler = (math.radians(90), 0, 0)

sc.render.engine = "CYCLES"
sc.cycles.samples = a.samples
sc.render.resolution_x, sc.render.resolution_y = 2400, 1200
sc.render.film_transparent = True
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.render.filepath = a.out + ".png"
bpy.ops.render.render(write_still=True)
print(f"TITLE OK -> {a.out}.png  (add glints/bloom in Pillow; build the tracked ProRes 4444 overlay from it)")
