"""
Renders the AI-generated ore truck (artsrc/units/meshes/harv.blend from import_glb.py) into the classic
harv.shp frame layout, like artsrc/units/harvester/render_harvester.py does for the procedural one:

  0-31    idle, 32 facings
  32-95   harvest, 8 facings x 8 frames (truck rocks, ore spills off the bucket lip)
  96-103  dock: dump bin tips up about its rear hinge (facing west)   [full truck only]
  104-110 dock-loop: ore pouring out of the tipped bin                 [full truck only]

Images: harv (full), harvhalf, harvempty, and the wrecks hhusk (full) / hhusk2 (empty).
The dump bin is cut out of the mesh (faces behind BIN_FRONT and above BIN_BOTTOM); ore piles are
added inside it.

  Blender -b artsrc/units/meshes/harv.blend -P artsrc/units/meshes/render_harv_mesh.py -- <out dir> [samples] [only]

PX_PREVIEW=1 renders only a few key frames (at 3x) for checking.
"""

import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "harvester"))
sys.path.insert(0, os.path.join(HERE, "..", "tank"))
import render_sprites  # noqa: E402
from build_harvester import make_ore, rock  # noqa: E402
from build_tank import box, link  # noqa: E402

FRAME = 224
UNIT_PX = 3.5
DOCK_TILT = 50.0
WEST = 8
BIN_FRONT = -0.4   # y: the bin is everything behind this...
BIN_BOTTOM = 3.4   # ...and above this height
BUCKET_LIP = Vector((0, 6.6, 0.4))

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
SAMPLES = int(argv[1]) if len(argv) > 1 else 48
ONLY = set(argv[2].split(",")) if len(argv) > 2 else None

objs = bpy.data.objects
body = objs["Body"]
src = next(o for o in body.children if o.type == "MESH")

# ---- Cut the dump bin out into its own object, hinged at its rear bottom edge
v = np.array([x.co[:] for x in src.data.vertices])
bm = bmesh.new()
bm.from_mesh(src.data)
pick = [f for f in bm.faces if f.calc_center_median().y < BIN_FRONT and f.calc_center_median().z > BIN_BOTTOM]
rear = min(f.calc_center_median().y for f in pick)
hinge = Vector((0, rear, BIN_BOTTOM))
bin_bm = bmesh.new()
uv_src = bm.loops.layers.uv.active
uv_dst = bin_bm.loops.layers.uv.new("UVMap")
vmap = {}
for f in pick:
    vs = [vmap.setdefault(x, bin_bm.verts.new(x.co - hinge)) for x in f.verts]
    nf = bin_bm.faces.new(vs)
    for l, nl in zip(f.loops, nf.loops):
        nl[uv_dst].uv = l[uv_src].uv
bmesh.ops.delete(bm, geom=pick, context="FACES")
bm.to_mesh(src.data)
bm.free()
bin_mesh = bpy.data.meshes.new("BinMesh")
bin_bm.to_mesh(bin_mesh)
bin_bm.free()
for m in src.data.materials:
    bin_mesh.materials.append(m)
for p in bin_mesh.polygons:
    p.use_smooth = True
hopper = link(bpy.data.objects.new("Hopper", None), body)
hopper.location = hinge
link(bpy.data.objects.new("Bin", bin_mesh), hopper)

# Bin interior: walls from the vertex extents, floor = lowest point well inside the footprint
inside = v[(v[:, 1] < BIN_FRONT - 0.8) & (v[:, 1] > rear + 0.8) & (v[:, 2] > BIN_BOTTOM)]
x_half = np.abs(inside[:, 0]).max() * 0.8
top = inside[:, 2].max()
core = inside[np.abs(inside[:, 0]) < x_half * 0.6]
floor = np.percentile(core[:, 2], 3)
y0, y1 = rear + 0.5, BIN_FRONT - 0.4
print(f"bin: rear {rear:.2f} floor {floor:.2f} top {top:.2f} half-width {x_half:.2f}")

# ---- Ore piles inside the bin (body space, parented to the hopper so they tip with it)
rng = random.Random(7)
ore = make_ore("Ore")


def ore_pile(name, level, dome):
    group = link(bpy.data.objects.new(name, None), hopper)
    bed = box(f"{name}Bed", (0, (y0 + y1) / 2, (floor + level) / 2), (2 * x_half, y1 - y0, level - floor), ore, group,
              bevel_w=0)
    bed.location -= hinge
    y, i = y0 + 0.2, 0
    while y < y1 - 0.1:
        x = -x_half + 0.25
        while x < x_half - 0.2:
            px, py = x + rng.uniform(-0.12, 0.12), y + rng.uniform(-0.12, 0.12)
            u, w = px / x_half, (py - (y0 + y1) / 2) / ((y1 - y0) / 2)
            h = level + dome * max(0.0, 1 - (u * u + w * w))
            r = rng.uniform(0.28, 0.42)
            rock(f"{name}Rock{i}", Vector((px, py, h - r * 0.3)) - hinge, r, ore, group, rng)
            i += 1
            x += 0.55
        y += 0.55
    return group


ore_full = ore_pile("OreFull", top - 0.25, 0.7)
ore_half = ore_pile("OreHalf", floor + (top - floor) * 0.5, 0.25)

spray = link(bpy.data.objects.new("Spray", None), body)
spray_rocks = [rock(f"Spray{i}", (0, 0, 0), rng.uniform(0.18, 0.3), ore, spray, rng) for i in range(10)]
stream = link(bpy.data.objects.new("Stream", None), body)
stream_rocks = [rock(f"Stream{i}", (0, 0, 0), rng.uniform(0.22, 0.36), ore, stream, rng) for i in range(16)]


def show(group, visible):
    for o in [group, *group.children_recursive]:
        o.hide_render = not visible


def pose(tilt=0.0, spray_phase=None, stream_phase=None, stream_count=0, rock_deg=0.0):
    hopper.rotation_euler = (math.radians(tilt), 0, 0)
    src.rotation_euler = (math.radians(rock_deg), 0, 0)  # the truck pitches a little as it digs

    show(spray, spray_phase is not None)
    if spray_phase is not None:
        for i, r in enumerate(spray_rocks):
            p = (spray_phase + i / len(spray_rocks)) % 1.0
            x = -2.0 + 4.0 * ((i * 0.37) % 1.0)
            r.location = (x, BUCKET_LIP.y + 0.6 * p, BUCKET_LIP.z + 2.4 * p - 2.6 * p * p + 0.3)

    show(stream, stream_phase is not None)
    if stream_phase is not None:
        lip = hopper.matrix_basis @ Vector((0, -0.3, (top - BIN_BOTTOM) * 0.5))
        for i, r in enumerate(stream_rocks):
            r.hide_render = i >= stream_count
            p = (stream_phase + i / len(stream_rocks)) % 1.0
            x = -1.6 + 3.2 * ((i * 0.61) % 1.0)
            r.location = (x, lip.y - 0.3 - 1.2 * p, lip.z * (1 - p * p))


PREVIEW = {4, 12, 20, 28, 58, 103, 106} if os.environ.get("PX_PREVIEW") else None


def render(image, index):
    if PREVIEW is not None and index not in PREVIEW:
        return
    render_sprites.render_to(os.path.join(OUT, image, f"frame-{index:03d}.png"))


def render_truck(image, load, dock):
    show(ore_full, load == "full")
    show(ore_half, load == "half")
    pose()
    for f in range(32):
        render_sprites.face(body, f, 32)
        render(image, f)
    for f in range(8):
        render_sprites.face(body, f, 8)
        for t in range(8):
            pose(spray_phase=t / 8, rock_deg=1.2 * math.sin(t * math.pi / 4))
            render(image, 32 + f * 8 + t)
    if dock:
        render_sprites.face(body, WEST, 32)
        for t in range(8):
            ease = 0.5 - 0.5 * math.cos(math.pi * t / 7)
            pose(tilt=DOCK_TILT * ease, stream_phase=0.0 if t == 7 else None, stream_count=5)
            render(image, 96 + t)
        for t in range(7):
            pose(tilt=DOCK_TILT, stream_phase=t / 7, stream_count=len(stream_rocks))
            render(image, 104 + t)


def char_everything():
    """Burnt-out wrecks: darken every texture strongly (ore keeps its colour)."""
    for mat in bpy.data.materials:
        if not mat.use_nodes or mat.name.startswith("Ore"):
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        burn = nt.nodes.new("ShaderNodeMix")
        burn.data_type = "RGBA"
        burn.inputs["Factor"].default_value = 0.82
        burn.inputs["B"].default_value = (0.025, 0.022, 0.02, 1)
        if bsdf.inputs["Base Color"].links:
            nt.links.new(bsdf.inputs["Base Color"].links[0].from_socket, burn.inputs["A"])
        else:
            burn.inputs["A"].default_value = bsdf.inputs["Base Color"].default_value
        nt.links.new(burn.outputs["Result"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.9


def wanted(image):
    return ONLY is None or image in ONLY


render_sprites.setup(frame=FRAME, samples=SAMPLES, unit_px=UNIT_PX, zoom=3 if PREVIEW else 1)
for image, load, dock in (("harv", "full", True), ("harvhalf", "half", False), ("harvempty", "empty", False)):
    if wanted(image):
        render_truck(image, load, dock)
        print("rendered", image)

if wanted("hhusk") or wanted("hhusk2"):
    char_everything()
    for image, load in (("hhusk", "full"), ("hhusk2", "empty")):
        if wanted(image):
            show(ore_full, load == "full")
            show(ore_half, False)
            pose(tilt=4.0)
            for f in range(32):
                render_sprites.face(body, f, 32)
                render(image, f)
            print("rendered", image)
