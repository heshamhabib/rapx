"""
RedAlert Project X - HD Missile Silo (MSLO) and its nuclear missile, built and rendered from code.

  blender -b -P artsrc/buildings/nuke_silo/build_silo.py -- <out dir> [samples] [only]

only = idle | active | missile (default: all). Writes <out dir>/idle.png, active-NN.png (the launch: beacons flash,
service arms swing away, blast doors slide open, the missile rises on its elevator, ignites and lifts off, doors
close) and missile-up-N.png / missile-down-N.png (the missile in flight for the NukePower). Same orthographic 50 degree
camera, light and 3x density as the HD units (artsrc/units/render_sprites.py). make_silo.py turns them into sheets.

Model units: 1 Blender unit = UNIT_PX world pixels. The building's ground centre is the origin (the frame centre).
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
FRAME = 480             # render pixels (160 world pixels: room for the missile lifting off)
ACTIVE_FRAMES = 48
LAUNCH_FRAME = 32       # last frame that shows the missile; the game's missile takes over after it
PIT = Vector((-2.6, 0.2, 0))   # silo shaft centre (Blender units)
MISSILE_LEN = 9.0
PAD_Z = 0.75            # platform top

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(HERE, "render")
SAMPLES = int(argv[1]) if len(argv) > 1 else 64
ONLY = argv[2] if len(argv) > 2 else "all"

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


def stripes(name, a, b, scale=2.2, axis="X"):
    """Hazard chevrons: diagonal bands of two colours."""
    mat, nt, bsdf = bt.node_mat(name)
    N, L = nt.nodes, nt.links
    tex = N.new("ShaderNodeTexCoord")
    wave = N.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = scale
    L.new(tex.outputs["Object"], wave.inputs["Vector"])
    step = N.new("ShaderNodeMath")
    step.operation = "GREATER_THAN"
    step.inputs[1].default_value = 0.5
    L.new(wave.outputs["Fac"], step.inputs[0])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*a, 1)
    mix.inputs["B"].default_value = (*b, 1)
    L.new(step.outputs["Value"], mix.inputs["Factor"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def concrete(name, colour):
    mat = bt.make_paint(name, colour, roughness=0.85, wear_color=(0.42, 0.4, 0.37))
    return mat


CONCRETE = concrete("Concrete", (0.38, 0.34, 0.27))
CONCRETE_DARK = concrete("ConcreteDark", (0.22, 0.2, 0.17))
STEEL = bt.make_paint("Steel", (0.22, 0.23, 0.25), roughness=0.45)
STEEL_DARK = bt.make_simple("SteelDark", (0.06, 0.065, 0.07), metallic=0.6, roughness=0.5)
DOOR = bt.make_paint("Door", (0.17, 0.18, 0.19), roughness=0.5)
RED_PAINT = bt.make_paint("RedPaint", (0.42, 0.04, 0.03), roughness=0.5)
HAZARD = stripes("Hazard", (0.85, 0.62, 0.05), (0.03, 0.03, 0.03), 1.6)
TEAM = bt.make_simple("Team", (0.0, 1.0, 0.0), roughness=0.5)       # PlayerColorShift recolours pure green
WINDOW = emissive("Window", (0.35, 0.85, 1.0), 3.0)
PIT_LIGHT = emissive("PitLight", (1.0, 0.18, 0.08), 6.0)
BEACON = emissive("Beacon", (1.0, 0.12, 0.05), 0.0)                  # animated: blinks during the launch
WHITE = bt.make_paint("MissileWhite", (0.82, 0.83, 0.84), roughness=0.38, wear_color=(0.6, 0.6, 0.6))
NOSE = bt.make_simple("MissileNose", (0.025, 0.025, 0.028), metallic=0.2, roughness=0.3)
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
    r0, span, root, tip, sweep, thick = 0.62, 1.05, 2.1, 1.1, 0.8, 0.09
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
    """Nuclear missile like the reference: white body, black ogive nose, red band with the radiation roundel,
    grey rings, four swept grey fins with orange tips, dark nozzle. Base at z=0, length MISSILE_LEN."""
    m = empty("Missile", parent)
    R = 0.62
    lathe("Nozzle", [(0.0, -0.15), (0.42, -0.15), (0.5, 0.25), (0.56, 0.3)], STEEL_DARK, m)
    lathe("Body", [(0.56, 0.3), (R, 0.45), (R, 7.0)], WHITE, m)
    nose = [(R, 7.0)] + [(R * math.cos(t * math.pi / 2) ** 0.75, 7.0 + 2.0 * math.sin(t * math.pi / 2))
                        for t in [i / 16 for i in range(1, 17)]]
    lathe("Nose", nose, NOSE, m)
    for z in (2.6, 4.6):
        lathe(f"Ring{z}", [(R + 0.02, z), (R + 0.02, z + 0.14)], GREY, m)
    lathe("Band", [(R + 0.015, 5.55), (R + 0.015, 5.95)], BAND, m)
    # roundel on the band, facing the camera (-Y)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=40)
    disc = bt.mesh_from_bmesh("Roundel", bm, ROUNDEL, m)
    disc.rotation_euler = (math.radians(90), 0, 0)
    disc.scale = (0.4, 0.4, 0.4)
    disc.location = (0, -R - 0.03, 5.75)
    for i, ang in enumerate((math.radians(45 + 90 * k) for k in range(4))):
        fin = fin_mesh(f"Fin{i}", ang, GREY, m)
        tipb = bmesh.new()
        bmesh.ops.create_cube(tipb, size=1.0)
        tip = bt.mesh_from_bmesh(f"FinTip{i}", tipb, ORANGE, fin)
        tip.scale = (0.12, 0.2, 0.22)
        tip.location = (0.62 + 1.0, 0, 0.92)
    # small dark hatches
    for z in (3.3, 3.9):
        bt.box(f"Hatch{z}", (-0.18, -R + 0.01, z), (0.14, 0.04, 0.22), STEEL_DARK, m, bevel_w=0)
        bt.box(f"Hatch{z}b", (0.18, -R + 0.01, z), (0.14, 0.04, 0.22), STEEL_DARK, m, bevel_w=0)
    return m


def build_flame(parent):
    """Exhaust plume: a bright emissive cone pointing down from the nozzle (scaled per frame)."""
    f = lathe("Flame", [(0.0, -4.5), (0.35, -3.2), (0.5, -1.6), (0.46, -0.6), (0.38, -0.15)], FLAME, parent, 24)
    return f


# --- The silo -----------------------------------------------------------------------------------------------------

root = empty("Silo")
root.rotation_euler = (0, 0, math.radians(10))      # seen from the front-left corner like the other HD buildings
W, D = 15.0, 9.0                                    # platform, Blender units (60 x 36 world px)
hole = 4.2                                          # shaft opening

# Platform with a square opening over the shaft, built as four slabs around it
px, py = PIT.x, PIT.y
slabs = [((-W / 2, px - hole / 2), (-D / 2, D / 2)), ((px + hole / 2, W / 2), (-D / 2, D / 2)),
         ((px - hole / 2, px + hole / 2), (-D / 2, py - hole / 2)), ((px - hole / 2, px + hole / 2), (py + hole / 2, D / 2))]
for i, ((x0, x1), (y0, y1)) in enumerate(slabs):
    bt.box(f"Slab{i}", ((x0 + x1) / 2, (y0 + y1) / 2, PAD_Z / 2), (x1 - x0, y1 - y0, PAD_Z), CONCRETE, root, bevel_w=0.08)
# stepped plinth all round and a hazard border
bt.box("Plinth", (0, 0, 0.12), (W + 0.8, D + 0.8, 0.24), CONCRETE_DARK, root, bevel_w=0.06)
for i, (cx, cy, sx, sy) in enumerate(((px, py - hole / 2 - 0.25, hole + 1.0, 0.5), (px, py + hole / 2 + 0.25, hole + 1.0, 0.5),
                                       (px - hole / 2 - 0.25, py, 0.5, hole), (px + hole / 2 + 0.25, py, 0.5, hole))):
    bt.box(f"HazardRim{i}", (cx, cy, PAD_Z + 0.02), (sx, sy, 0.06), HAZARD, root, bevel_w=0)
# fortified wall round the back and sides (sloped outside, like the other HD bunkers)
for i, (x0, x1, y0, y1) in enumerate(((-W / 2 - 0.4, W / 2 + 0.4, D / 2 - 0.2, D / 2 + 0.5),
                                       (-W / 2 - 0.4, -W / 2 + 0.3, -D / 2 + 1.2, D / 2 + 0.5),
                                       (W / 2 - 0.3, W / 2 + 0.4, -D / 2 + 1.2, D / 2 + 0.5))):
    bt.extrude_polygon(f"Wall{i}", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 0, 1.7, CONCRETE_DARK, root,
                       top_scale=0.93, bevel_w=0.08)
    bt.box(f"WallCap{i}", ((x0 + x1) / 2, (y0 + y1) / 2, 1.75), (x1 - x0 - 0.2, y1 - y0 - 0.1, 0.12), RED_PAINT, root,
           bevel_w=0.02)
# raised concrete collar round the blast doors
collar = 0.75
for i, (cx, cy, sx, sy) in enumerate(((px, py - hole / 2 - collar / 2 - 0.5, hole + 2 * collar + 1.0, collar),
                                       (px, py + hole / 2 + collar / 2 + 0.5, hole + 2 * collar + 1.0, collar),
                                       (px - hole / 2 - collar / 2 - 0.5, py, collar, hole + 1.0),
                                       (px + hole / 2 + collar / 2 + 0.5, py, collar, hole + 1.0))):
    bt.extrude_polygon(f"Collar{i}", [(cx - sx / 2, cy - sy / 2), (cx + sx / 2, cy - sy / 2), (cx + sx / 2, cy + sy / 2),
                                      (cx - sx / 2, cy + sy / 2)], PAD_Z, PAD_Z + 0.55, CONCRETE, root, top_scale=0.9,
                       bevel_w=0.06)
# floodlight masts and supply barrels
for i, (x, y) in enumerate(((-W / 2 + 1.0, -D / 2 + 1.3), (W / 2 - 1.1, -D / 2 + 1.4))):
    bt.cylinder(f"Mast{i}", (x, y, PAD_Z + 1.4), 0.07, 2.8, STEEL, root, segments=8, bevel_w=0)
    bt.box(f"Flood{i}", (x, y, PAD_Z + 2.85), (0.55, 0.3, 0.3), STEEL_DARK, root, bevel_w=0.02)
    bt.box(f"FloodLens{i}", (x, y - 0.16, PAD_Z + 2.85), (0.45, 0.03, 0.2), WINDOW, root, bevel_w=0)
for i, (x, y) in enumerate(((0.6, -3.4), (0.95, -3.55), (0.75, -3.0), (-6.4, 2.9), (-6.0, 3.2))):
    bt.cylinder(f"Barrel{i}", (x, y, PAD_Z + 0.32), 0.2, 0.62, RED_PAINT if i % 2 else STEEL, root, segments=14,
                bevel_w=0.02)

# door rails
for y in (py - hole / 2 - 0.62, py + hole / 2 + 0.62):
    bt.box(f"Rail{y}", (px, y, PAD_Z + 0.08), (hole * 2.6, 0.18, 0.16), STEEL, root, bevel_w=0.03)

# Shaft: dark walls, red light strips, the elevator floor sits deep down
shaft = empty("Shaft", root, (px, py, 0))
for i, (cx, cy, sx, sy) in enumerate(((0, -hole / 2, hole, 0.2), (0, hole / 2, hole, 0.2), (-hole / 2, 0, 0.2, hole), (hole / 2, 0, 0.2, hole))):
    bt.box(f"ShaftWall{i}", (cx, cy, -5.0), (sx, sy, 11.5), STEEL_DARK, shaft, bevel_w=0)
for k in range(3):
    for i, (cx, cy, sx, sy) in enumerate(((0, hole / 2 - 0.12, hole * 0.8, 0.05), (-hole / 2 + 0.12, 0, 0.05, hole * 0.8),
                                           (hole / 2 - 0.12, 0, 0.05, hole * 0.8))):
        bt.box(f"PitLight{k}{i}", (cx, cy, -0.6 - 2.2 * k), (sx, sy, 0.12), PIT_LIGHT, shaft, bevel_w=0)

# Elevator with the missile on it
elevator = empty("Elevator", shaft)
bt.box("ElevatorDeck", (0, 0, -0.1), (hole * 0.92, hole * 0.92, 0.2), STEEL, elevator, bevel_w=0.04)
missile = build_missile(elevator)
flame = build_flame(missile)

# Blast doors (two halves sliding left / right on the rails)
doors = []
for side in (-1, 1):
    d = empty(f"DoorPivot{side}", root, (px + side * hole / 4, py, PAD_Z + 0.25))
    bt.box(f"Door{side}", (0, 0, 0), (hole / 2, hole + 0.9, 0.5), DOOR, d, bevel_w=0.06)
    bt.box(f"DoorStripe{side}", (side * 0.35, 0, 0.27), (0.5, hole + 0.7, 0.04), HAZARD, d, bevel_w=0)
    bt.box(f"DoorTeam{side}", (-side * 0.55, 0, 0.27), (0.22, hole + 0.5, 0.04), TEAM, d, bevel_w=0)
    for k in range(3):
        bt.box(f"DoorRib{side}{k}", (0, -hole / 2 + 0.6 + k * (hole - 1.2) / 2, 0.28), (hole / 2 - 0.2, 0.14, 0.08), STEEL, d,
               bevel_w=0.02)
    doors.append((d, side))

# Gantry tower behind-left of the shaft, with two service arms that swing away
tower = empty("Tower", root, (px - hole / 2 - 1.4, py + hole / 2 + 0.6, PAD_Z))
TH = 10.5
for i, (dx, dy) in enumerate(((-0.55, -0.55), (0.55, -0.55), (-0.55, 0.55), (0.55, 0.55))):
    bt.box(f"Post{i}", (dx, dy, TH / 2), (0.16, 0.16, TH), RED_PAINT, tower, bevel_w=0.02)
for k in range(7):
    z = 0.6 + k * 1.5
    for i, (cx, cy, sx, sy) in enumerate(((0, -0.55, 1.1, 0.08), (0, 0.55, 1.1, 0.08), (-0.55, 0, 0.08, 1.1), (0.55, 0, 0.08, 1.1))):
        bt.box(f"Brace{k}{i}", (cx, cy, z), (sx, sy, 0.08), STEEL, tower, bevel_w=0)
    for i, sgn in enumerate((-1, 1)):
        brace = bt.box(f"X{k}{i}", (0, 0, 0), (0.06, 0.06, 1.75), STEEL, tower, bevel_w=0)
        brace.location = (0, -0.55, z + 0.75)      # boxes pivot at their mesh origin: build centred, then place
        brace.rotation_euler = (0, sgn * math.radians(37), 0)
bt.box("TowerTop", (0, 0, TH + 0.1), (1.5, 1.5, 0.2), STEEL, tower, bevel_w=0.03)
beacon_top = bt.cylinder("TowerBeacon", (0, 0, TH + 0.4), 0.22, 0.4, BEACON, tower, segments=16, bevel_w=0)
arms = []
for k, z in enumerate((4.6, 8.2)):
    arm = empty(f"ArmPivot{k}", tower, (0.55, -0.2, z))
    bt.box(f"Arm{k}", (1.0, 0, 0), (2.0, 0.35, 0.3), RED_PAINT, arm, bevel_w=0.03)
    bt.box(f"ArmClamp{k}", (2.05, 0, 0), (0.3, 0.7, 0.45), STEEL, arm, bevel_w=0.03)
    arms.append(arm)

# Control bunker on the right with lit windows, a radar dish and an antenna
bunker = empty("Bunker", root, (3.6, 0.6, PAD_Z))
bt.extrude_polygon("BunkerBody", [(-2.6, -2.6), (2.6, -2.6), (2.6, 2.6), (-2.6, 2.6)], 0, 2.4, CONCRETE, bunker,
                   top_scale=0.86, bevel_w=0.08)
bt.extrude_polygon("BunkerArmour", [(-2.8, -2.8), (2.8, -2.8), (2.8, -2.3), (-2.8, -2.3)], 0, 1.0, CONCRETE_DARK, bunker,
                   top_scale=0.95, bevel_w=0.06)
bt.box("BunkerTrim", (0, -2.56, 2.15), (4.6, 0.08, 0.16), RED_PAINT, bunker, bevel_w=0)
bt.box("BunkerRoof", (0, 0, 2.5), (4.4, 4.4, 0.22), STEEL, bunker, bevel_w=0.04)
bt.box("BunkerTeam", (0, 0, 2.64), (3.4, 1.0, 0.06), TEAM, bunker, bevel_w=0)
bt.box("Windows", (0, -2.48, 1.55), (3.6, 0.08, 0.38), WINDOW, bunker, bevel_w=0)
bt.box("WindowsSide", (-2.48, 0, 1.55), (0.08, 3.6, 0.38), WINDOW, bunker, bevel_w=0)
bt.box("BunkerDoor", (1.4, -2.55, 0.6), (0.9, 0.12, 1.2), STEEL_DARK, bunker, bevel_w=0.02)
dish = empty("Dish", bunker, (1.1, 1.1, 2.62))
bt.cylinder("DishMast", (0, 0, 0.4), 0.1, 0.8, STEEL, dish, segments=12, bevel_w=0)
dish_bowl = lathe("DishBowl", [(0.0, 0.0), (0.45, 0.05), (0.8, 0.22), (0.95, 0.4)], STEEL, dish, 28)
dish_bowl.location = (0, 0, 0.8)
dish_bowl.rotation_euler = (math.radians(-55), 0, math.radians(30))
bt.cylinder("Antenna", (-1.4, 1.2, 4.1), 0.05, 3.0, STEEL, bunker, segments=8, bevel_w=0)
bt.cylinder("AntennaTip", (-1.4, 1.2, 5.65), 0.09, 0.12, BEACON, bunker, segments=8, bevel_w=0)
for i in range(3):
    bt.cylinder(f"Vent{i}", (-1.2 + i * 0.7, -1.0, 2.75), 0.18, 0.3, STEEL_DARK, bunker, segments=14, bevel_w=0)

# Fuel tanks behind the bunker
for i, y in enumerate((3.35, 2.35)):
    bt.cylinder(f"Tank{i}", (5.2, y, 1.25), 0.45, 3.4, WHITE, root, axis="X", segments=24, bevel_w=0.03)
    for x in (4.0, 6.4):
        bt.box(f"TankSaddle{i}{x}", (x, y, 0.95), (0.25, 0.9, 0.4), STEEL, root, bevel_w=0.02)
# pipes from the tanks to the shaft
bt.cylinder("Pipe", (1.2, 3.1, PAD_Z + 0.25), 0.12, 7.0, STEEL, root, axis="X", segments=12, bevel_w=0)

# Corner warning lights on the platform
corner_lights = []
for i, (x, y) in enumerate(((-W / 2 + 0.6, -D / 2 + 0.6), (W / 2 - 0.6, -D / 2 + 0.6), (-W / 2 + 0.6, D / 2 - 0.6))):
    bt.cylinder(f"LampBase{i}", (x, y, PAD_Z + 0.12), 0.22, 0.24, STEEL_DARK, root, segments=12, bevel_w=0)
    corner_lights.append(bt.cylinder(f"Lamp{i}", (x, y, PAD_Z + 0.36), 0.16, 0.26, BEACON, root, segments=12, bevel_w=0))

# --- Scene, light, camera -----------------------------------------------------------------------------------------

scene = render_sprites.setup(frame=FRAME, samples=SAMPLES, unit_px=UNIT_PX)
for o in scene.objects:
    if o.type == "MESH" and o.is_shadow_catcher:
        o.scale = (5, 5, 1)          # the tall missile throws a long shadow
        catcher = o


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def set_state(doors_open, missile_z, arms_out, beacon, flame_k):
    for d, side in doors:
        d.location.x = px + side * (hole / 4 + doors_open * hole * 0.62)
    # the elevator stops at the pad; at lift-off only the missile goes on climbing
    elevator.location.z = min(missile_z, PAD_Z)
    missile.location.z = missile_z - elevator.location.z
    for o in [missile] + list(missile.children_recursive):
        o.visible_shadow = missile.location.z < 0.5      # no long shadow from the missile in the air
    for k, arm in enumerate(arms):
        arm.rotation_euler = (0, 0, math.radians(-95 * arms_out * (1 if k == 0 else 0.9)))
    BEACON.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = beacon
    flame.hide_render = flame_k <= 0.01
    flame.scale = (0.8 + 0.4 * flame_k, 0.8 + 0.4 * flame_k, max(0.05, flame_k))


def launch_state(f):
    """Pose of frame f of the launch (ACTIVE_FRAMES frames)."""
    blink = 18.0 if (f // 2) % 2 == 0 and f < 40 else 1.5
    arms_out = smooth(0, 6, f)
    open_ = smooth(2, 13, f) * (1 - smooth(38, 46, f))
    hidden = -MISSILE_LEN - 1.2
    if f < 10:
        z = hidden
    elif f < 22:
        z = hidden + (PAD_Z - hidden) * smooth(10, 22, f)
    elif f < 26:
        z = PAD_Z
    else:
        t = f - 26
        z = PAD_Z + 0.5 * 0.9 * t * t                 # lift-off, accelerating
    flame_k = 0 if f < 23 else min(1.0, 0.35 + (f - 23) * 0.22)
    return dict(doors_open=open_, missile_z=z, arms_out=arms_out, beacon=blink, flame_k=flame_k), f <= LAUNCH_FRAME


os.makedirs(OUT, exist_ok=True)
if ONLY in ("all", "idle"):
    set_state(0, -MISSILE_LEN - 1.2, 0, 2.0, 0)
    render_sprites.render_to(os.path.join(OUT, "idle.png"))

if ONLY in ("all", "active"):
    for f in range(ACTIVE_FRAMES):
        state, visible = launch_state(f)
        set_state(**state)
        missile.hide_render = not visible
        for o in missile.children_recursive:
            o.hide_render = not visible or (o is flame and state["flame_k"] <= 0.01)
        render_sprites.render_to(os.path.join(OUT, f"active-{f:02d}.png"))
    missile.hide_render = False
    for o in missile.children_recursive:
        o.hide_render = False

if ONLY in ("all", "missile"):
    # The missile alone, centred, for the NukePower flight sprites (nose up while climbing, nose down diving)
    keep = set([missile, flame] + list(missile.children_recursive))
    for o in scene.objects:
        if o.type in ("MESH", "CURVE") and o not in keep:
            o.hide_render = True
    elevator.parent = None
    elevator.location = (0, 0, 0)
    missile.parent = None
    BEACON.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0
    scene.render.resolution_x = scene.render.resolution_y = 216
    scene.camera.data.ortho_scale = 216 / (UNIT_PX * render_sprites.DENSITY)
    import random
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

print("rendered", ONLY, "to", OUT)
