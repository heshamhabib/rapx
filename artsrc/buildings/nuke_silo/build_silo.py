"""
RedAlert Project X - the nuclear missile of the Missile Silo (MSLO), built and rendered from code.

  blender -b -P artsrc/buildings/nuke_silo/build_silo.py -- <out dir> [samples]

The silo building itself is ChatGPT art (artsrc/buildings/src/mslo.png, an empty launch bay); make_silo.py stands
this missile in that bay and animates the launch, so the missile on the pad is exactly the one that falls on the
target. Writes <out dir>/missile-stand.png (base on the frame centre, no flame), missile-fire-N.png (the same with
the exhaust flame) and missile-up-N.png / missile-down-N.png (centred, for the NukePower flight). Same orthographic
50 degree camera, light and 3x density as the HD units (artsrc/units/render_sprites.py).

Model units: 1 Blender unit = UNIT_PX world pixels.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "units"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "units", "tank"))
os.environ.setdefault("PX_LIGHT", "hd")

UNIT_PX = 4.0           # world pixels per Blender unit
FRAME = 216             # render pixels (72 world px: the whole missile with its flame)
MISSILE_LEN = 9.0

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(HERE, "render")
SAMPLES = int(argv[1]) if len(argv) > 1 else 64

import build_tank as bt  # noqa: E402

bt.reset_scene()
import render_sprites  # noqa: E402

# --- Materials --------------------------------------------------------------------------------------------------

def emissive(name, colour, strength):
    mat, nt, bsdf = bt.node_mat(name)
    bsdf.inputs["Base Color"].default_value = (*colour, 1)
    bsdf.inputs["Emission Color"].default_value = (*colour, 1)
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


STEEL_DARK = bt.make_simple("SteelDark", (0.06, 0.065, 0.07), metallic=0.6, roughness=0.5)
WHITE = bt.make_paint("MissileWhite", (0.82, 0.83, 0.84), roughness=0.38, wear_color=(0.6, 0.6, 0.6))
NOSE = bt.make_paint("MissileNose", (0.55, 0.045, 0.035), roughness=0.35)
GREY = bt.make_paint("MissileGrey", (0.36, 0.37, 0.39), roughness=0.45)
BAND = bt.make_simple("MissileBand", (0.62, 0.06, 0.05), roughness=0.45)
ORANGE = emissive("FinTip", (1.0, 0.32, 0.05), 1.5)
FLAME = emissive("Flame", (1.0, 0.62, 0.22), 30.0)


def roundel_material():
    """Yellow radiation roundel (trefoil) for the missile's red band: drawn procedurally in the shader."""
    mat, nt, bsdf = bt.node_mat("Roundel")
    N, L = nt.nodes, nt.links
    tex = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(tex.outputs["Object"], sep.inputs[0])
    # polar coordinates on the disc (object space, disc in the XZ plane, radius 1)
    r = N.new("ShaderNodeVectorMath")
    r.operation = "LENGTH"
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(sep.outputs["X"], comb.inputs["X"])
    L.new(sep.outputs["Y"], comb.inputs["Y"])
    L.new(comb.outputs[0], r.inputs[0])
    ang = N.new("ShaderNodeMath")
    ang.operation = "ARCTAN2"
    L.new(sep.outputs["Y"], ang.inputs[0])
    L.new(sep.outputs["X"], ang.inputs[1])
    # three 60 degree blades: sin(3a) > 0.5 -> inside a blade (offset so one points down)
    a3 = N.new("ShaderNodeMath")
    a3.operation = "MULTIPLY"
    a3.inputs[1].default_value = 3.0
    L.new(ang.outputs[0], a3.inputs[0])
    ph = N.new("ShaderNodeMath")
    ph.operation = "ADD"
    ph.inputs[1].default_value = math.pi / 2
    L.new(a3.outputs[0], ph.inputs[0])
    s = N.new("ShaderNodeMath")
    s.operation = "SINE"
    L.new(ph.outputs[0], s.inputs[0])
    blade = N.new("ShaderNodeMath")
    blade.operation = "GREATER_THAN"
    blade.inputs[1].default_value = 0.5
    L.new(s.outputs[0], blade.inputs[0])
    ring_in = N.new("ShaderNodeMath")
    ring_in.operation = "GREATER_THAN"
    ring_in.inputs[1].default_value = 0.28
    L.new(r.outputs["Value"], ring_in.inputs[0])
    ring_out = N.new("ShaderNodeMath")
    ring_out.operation = "LESS_THAN"
    ring_out.inputs[1].default_value = 0.72
    L.new(r.outputs["Value"], ring_out.inputs[0])
    band = N.new("ShaderNodeMath")
    band.operation = "MULTIPLY"
    L.new(ring_in.outputs[0], band.inputs[0])
    L.new(ring_out.outputs[0], band.inputs[1])
    blades = N.new("ShaderNodeMath")
    blades.operation = "MULTIPLY"
    L.new(band.outputs[0], blades.inputs[0])
    L.new(blade.outputs[0], blades.inputs[1])
    hub = N.new("ShaderNodeMath")
    hub.operation = "LESS_THAN"
    hub.inputs[1].default_value = 0.18
    L.new(r.outputs["Value"], hub.inputs[0])
    edge = N.new("ShaderNodeMath")
    edge.operation = "GREATER_THAN"
    edge.inputs[1].default_value = 0.88
    L.new(r.outputs["Value"], edge.inputs[0])
    black = N.new("ShaderNodeMath")
    black.operation = "MAXIMUM"
    L.new(blades.outputs[0], black.inputs[0])
    L.new(hub.outputs[0], black.inputs[1])
    black2 = N.new("ShaderNodeMath")
    black2.operation = "MAXIMUM"
    L.new(black.outputs[0], black2.inputs[0])
    L.new(edge.outputs[0], black2.inputs[1])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (1.0, 0.72, 0.02, 1)
    mix.inputs["B"].default_value = (0.02, 0.02, 0.02, 1)
    L.new(black2.outputs[0], mix.inputs["Factor"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.4
    return mat


ROUNDEL = roundel_material()

# --- Helpers ----------------------------------------------------------------------------------------------------

def lathe(name, profile, mat, parent=None, segments=40):
    """Body of revolution around Z from (radius, z) points."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = [bm.verts.new((r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), z))
                for i in range(segments)]
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if profile[0][0] > 0:
        bm.faces.new(list(reversed(rings[0])))
    if profile[-1][0] > 0:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bt.mesh_from_bmesh(name, bm, mat, parent, smooth=True)


def empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bt.link(e, parent)
    e.location = loc
    return e


def fin_mesh(name, angle, mat, parent):
    """Swept trapezoid fin standing out from the body at `angle` (radians around Z)."""
    r0, span, root, tip, sweep, thick = 0.62, 0.55, 1.9, 0.9, 0.7, 0.09
    pts = [(r0, 0.0), (r0, root), (r0 + span, sweep + tip), (r0 + span, sweep)]
    bm = bmesh.new()
    vs = []
    for side in (-thick, thick):
        vs.append([bm.verts.new((x, side, z)) for x, z in pts])
    a, b = vs
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = bt.mesh_from_bmesh(name, bm, mat, parent)
    o.rotation_euler = (0, 0, angle)
    return o


def build_missile(parent):
    """Soviet nuclear missile like the RA2 silo's (reference/): white body, red ogive nose, red bands (the upper one
    with the radiation roundel), four short red fins that fit the silo's launch bay, dark nozzle. Base at z=0,
    length MISSILE_LEN."""
    m = empty("Missile", parent)
    R = 0.62
    lathe("Nozzle", [(0.0, -0.15), (0.42, -0.15), (0.5, 0.25), (0.56, 0.3)], STEEL_DARK, m)
    lathe("Body", [(0.56, 0.3), (R, 0.45), (R, 7.0)], WHITE, m)
    nose = [(R, 7.0)] + [(R * math.cos(t * math.pi / 2) ** 0.75, 7.0 + 2.0 * math.sin(t * math.pi / 2))
                        for t in [i / 16 for i in range(1, 17)]]
    lathe("Nose", nose, NOSE, m)
    for z in (2.6, 4.6):
        lathe(f"Ring{z}", [(R + 0.02, z), (R + 0.02, z + 0.14)], GREY, m)
    lathe("BandLow", [(R + 0.015, 0.45), (R + 0.015, 1.15)], BAND, m)
    lathe("BandNose", [(R + 0.015, 6.55), (R + 0.015, 6.8)], BAND, m)
    lathe("Band", [(R + 0.015, 5.55), (R + 0.015, 5.95)], BAND, m)
    # roundel on the band, facing the camera (-Y)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=40)
    disc = bt.mesh_from_bmesh("Roundel", bm, ROUNDEL, m)
    disc.rotation_euler = (math.radians(90), 0, 0)
    disc.scale = (0.4, 0.4, 0.4)
    disc.location = (0, -R - 0.03, 5.75)
    for i, ang in enumerate((math.radians(45 + 90 * k) for k in range(4))):
        fin = fin_mesh(f"Fin{i}", ang, BAND, m)
        tipb = bmesh.new()
        bmesh.ops.create_cube(tipb, size=1.0)
        tip = bt.mesh_from_bmesh(f"FinTip{i}", tipb, ORANGE, fin)
        tip.scale = (0.12, 0.2, 0.22)
        tip.location = (0.62 + 0.5, 0, 0.82)
    # small dark hatches
    for z in (3.3, 3.9):
        bt.box(f"Hatch{z}", (-0.18, -R + 0.01, z), (0.14, 0.04, 0.22), STEEL_DARK, m, bevel_w=0)
        bt.box(f"Hatch{z}b", (0.18, -R + 0.01, z), (0.14, 0.04, 0.22), STEEL_DARK, m, bevel_w=0)
    return m


def build_flame(parent):
    """Exhaust plume: a bright emissive cone pointing down from the nozzle (scaled per frame)."""
    f = lathe("Flame", [(0.0, -4.5), (0.35, -3.2), (0.5, -1.6), (0.46, -0.6), (0.38, -0.15)], FLAME, parent, 24)
    return f


# --- Scene, light, camera -----------------------------------------------------------------------------------------

missile = build_missile(None)
flame = build_flame(missile)
scene = render_sprites.setup(frame=FRAME, samples=SAMPLES, unit_px=UNIT_PX)
for o in scene.objects:
    if o.type == "MESH" and o.is_shadow_catcher:
        o.hide_render = True        # no shadow: the missile stands in the painted silo / flies over the map
os.makedirs(OUT, exist_ok=True)

# Standing on its base (the frame centre), as on the launch pad: without and with the exhaust flame
flame.hide_render = True
render_sprites.render_to(os.path.join(OUT, "missile-stand.png"))
flame.hide_render = False
for i, k in enumerate((0.75, 1.0, 0.85, 1.12)):
    flame.scale = (0.9 + 0.3 * k, 0.9 + 0.3 * k, k)
    render_sprites.render_to(os.path.join(OUT, f"missile-fire-{i}.png"))

# In flight, centred, for the NukePower (nose up while climbing, nose down diving)
import random  # noqa: E402
rnd = random.Random(7)
for direction in ("up", "down"):
    for i in range(4):
        if direction == "up":
            missile.rotation_euler = (0, 0, 0)
            missile.location = (0, 0, -MISSILE_LEN / 2 + 0.4)
            k = rnd.uniform(0.8, 1.15)
            flame.hide_render = False
            flame.scale = (0.9 + 0.3 * k, 0.9 + 0.3 * k, k)
        else:
            missile.rotation_euler = (0, math.radians(180), 0)   # about Y: the roundel still faces the camera
            missile.location = (0, 0, MISSILE_LEN / 2 - 0.4)
            flame.hide_render = True
        render_sprites.render_to(os.path.join(OUT, f"missile-{direction}-{i}.png"))

print("rendered the missile to", OUT)
