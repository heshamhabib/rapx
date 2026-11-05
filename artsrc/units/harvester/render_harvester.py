"""
Renders every ore truck sprite from harvester.blend, in the classic harv.shp frame layout so the
stock sequence definitions (idle / harvest / dock / dock-loop) keep their Start values:

  0-31    idle, 32 facings
  32-95   harvest, 8 facings x 8 frames (bucket digs and curls, ore spills off the lip)
  96-103  dock: hopper tips up (facing west, the refinery's DockAngle)       [full truck only]
  104-110 dock-loop: ore pouring out of the tipped hopper                     [full truck only]

Images: harv (full), harvhalf, harvempty, and the wrecks hhusk (full) / hhusk2 (empty).

  Blender -b artsrc/units/harvester/harvester.blend -P artsrc/units/harvester/render_harvester.py -- <out dir> [samples] [only]

Writes <out dir>/<image>/frame-NNN.png. `only` limits it to a comma-separated list of images.
With PX_PREVIEW=1 only a few key frames are rendered, at 3x resolution, for checking the model.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import render_sprites  # noqa: E402

FRAME = 192
UNIT_PX = 3.5  # ~39 world px long, like the classic truck
DOCK_TILT = 52.0
WEST = 8  # facing frame (of 32) pointing west

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
SAMPLES = int(argv[1]) if len(argv) > 1 else 48
ONLY = set(argv[2].split(",")) if len(argv) > 2 else None
PREVIEW = bool(os.environ.get("PX_PREVIEW"))
PREVIEW_FRAMES = {4, 12, 20, 28, 32 + 3 * 8 + 2, 103, 106}

obj = bpy.data.objects
body, boom, bucket, hopper = obj["Body"], obj["Boom"], obj["Bucket"], obj["Hopper"]
spray, stream = obj["Spray"], obj["Stream"]
spray_rocks = sorted(spray.children, key=lambda o: o.name)
stream_rocks = sorted(stream.children, key=lambda o: o.name)
rams = [o for o in obj if "px_ram" in o]


def show(group, visible):
    group.hide_render = not visible
    for child in group.children_recursive:
        child.hide_render = not visible


def to_body(o, local=None):
    """Position in Body space of `local` (default: the origin) in o's own space."""
    p = Vector(local) if local is not None else Vector()
    while o is not body:
        p = o.matrix_basis @ p
        o = o.parent
    return p


def pose(tilt=0.0, lift=0.0, curl=0.0, spray_phase=None, stream_phase=None, stream_count=0, bob=0.0):
    hopper.rotation_euler = (math.radians(tilt), 0, 0)
    boom.rotation_euler = (math.radians(lift), 0, 0)
    bucket.rotation_euler = (math.radians(curl), 0, 0)
    body.location = (0, 0, bob)

    # Rams run from their chassis mount to their mount on the moving part
    for ram in rams:
        a = to_body(obj[ram["px_ram"]])
        b = to_body(obj[ram["px_ram_tip"]])
        d = b - a
        ram.location = (a + b) / 2
        ram.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        ram.scale = (1, 1, d.length)

    # Ore spilling off the bucket lip down to the ground, each chunk on its own phase (seamless loop)
    show(spray, spray_phase is not None)
    if spray_phase is not None:
        lip = to_body(bucket, (0, 1.5, 0.1))
        for i, r in enumerate(spray_rocks):
            p = (spray_phase + i / len(spray_rocks)) % 1.0
            x = -1.5 + 3.0 * ((i * 0.37) % 1.0)
            r.location = Vector((x, lip.y + 0.35 * p, lip.z * (1 - p * p))) - spray.location

    # Ore pouring off the rear lip of the tipped hopper down to the ground
    show(stream, stream_phase is not None)
    if stream_phase is not None:
        lip = to_body(hopper, (0, -0.45, 1.6))
        for i, r in enumerate(stream_rocks):
            r.hide_render = i >= stream_count
            p = (stream_phase + i / len(stream_rocks)) % 1.0
            x = -0.9 + 1.8 * ((i * 0.61) % 1.0)
            r.location = Vector((x, lip.y - 0.25 - 0.9 * p, lip.z - lip.z * p * p)) - stream.location


def render(image, index):
    if PREVIEW and index not in PREVIEW_FRAMES:
        return
    render_sprites.render_to(os.path.join(OUT, image, f"frame-{index:03d}.png"))


def render_truck(image, ore, dock):
    show(obj["OreFull"], ore == "full")
    show(obj["OreHalf"], ore == "half")

    pose()
    for f in range(32):
        render_sprites.face(body, f, 32)
        render(image, f)

    for f in range(8):
        render_sprites.face(body, f, 8)
        for t in range(8):
            # Dig cycle: the bucket lifts and curls back, then lowers again; ore spills while it is raised
            c = 0.5 - 0.5 * math.cos(2 * math.pi * t / 8)
            pose(lift=10.0 * c, curl=28.0 * c, spray_phase=t / 8, bob=0.02 * math.sin(t * math.pi / 2))
            render(image, 32 + f * 8 + t)

    if dock:
        render_sprites.face(body, WEST, 32)
        for t in range(8):
            ease = 0.5 - 0.5 * math.cos(math.pi * t / 7)
            pose(tilt=DOCK_TILT * ease, stream_phase=0.0 if t == 7 else None, stream_count=4)
            render(image, 96 + t)
        for t in range(7):
            pose(tilt=DOCK_TILT, stream_phase=t / 7, stream_count=len(stream_rocks))
            render(image, 104 + t)


def char_everything():
    """Burnt-out look for the wrecks: every surface becomes scorched metal (ore stays dull)."""
    charred = bpy.data.materials.new("Charred")
    charred.use_nodes = True
    bsdf = charred.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.03, 0.028, 0.025, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    for o in obj:
        # Skip the ore and the renderer's shadow-catcher ground plane
        if o.type == "MESH" and not o.is_shadow_catcher and "Rock" not in o.name and "Bed" not in o.name:
            o.data.materials.clear()
            o.data.materials.append(charred)
            for m in list(o.modifiers):
                if m.type == "BEVEL":
                    m.harden_normals = False


def render_husk(image, ore):
    show(obj["OreFull"], ore == "full")
    show(obj["OreHalf"], False)
    pose(tilt=4.0)  # sagging hopper
    for f in range(32):
        render_sprites.face(body, f, 32)
        render(image, f)


def wanted(image):
    return ONLY is None or image in ONLY


render_sprites.setup(frame=FRAME, samples=SAMPLES, unit_px=UNIT_PX, zoom=3 if PREVIEW else 1)
for image, ore, dock in (("harv", "full", True), ("harvhalf", "half", False), ("harvempty", "empty", False)):
    if wanted(image):
        render_truck(image, ore, dock)
        print("rendered", image)

if wanted("hhusk") or wanted("hhusk2"):
    char_everything()
    for image, ore in (("hhusk", "full"), ("hhusk2", "empty")):
        if wanted(image):
            render_husk(image, ore)
            print("rendered", image)
