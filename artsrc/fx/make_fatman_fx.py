#!/usr/bin/env python3
"""
The falling Fatman bomb (USA bomber strike, rules/fatman.yaml): renders the Sketchfab model "Atomic Bomb - FATMAN"
(CaptainTux, CC-BY-4.0, artsrc/units/meshes/glb/sketchfab/inbox4/fatman) nose-down, slowly turning about its long
axis while it falls, and packs the frames into mods/rapx/bits/hd/fx/fatman-bomb.png (image `fatman`, sequence
`falling` in sequences/fatman.yaml).

  python3 artsrc/fx/make_fatman_fx.py            (from the repo root; runs Blender itself)

The bomb is drawn larger than real size (3.25 m = 8 world px) so it reads while it falls, like the nuke's falling
missile (atomic.down Scale 1.8).
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "artsrc", "units", "meshes", "glb", "sketchfab", "inbox4", "fatman", "scene.gltf")
RENDER = os.path.join(HERE, "preview", "fatman-bomb")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "fatman-bomb.png")
FRAMES = 16
FRAME_PX = 120  # sprite px (3 per world px): a 40 px world frame
BOMB_WORLD_PX = 22  # bomb length on screen before the camera's foreshortening
TILT = 18  # degrees off vertical, nose down and a little ahead


def render():
    import bpy
    from mathutils import Vector

    sys.path.insert(0, os.path.join(ROOT, "artsrc", "units"))
    os.environ["PX_LIGHT"] = "hd"
    os.environ["PX_NO_GROUND"] = "1"
    import render_sprites

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    centre, length = (lo + hi) / 2, hi.y - lo.y  # the model's nose points to -Y, tail fins to +Y

    body = bpy.data.objects.new("Body", None)
    bpy.context.scene.collection.objects.link(body)
    for o in meshes:
        world = o.matrix_world.copy()
        o.parent = body
        o.matrix_world = world
    for o in meshes:
        o.location -= centre  # parented with an identity body: local = world

    body.rotation_mode = "YXZ"  # assigning an Euler copies its angles, not its order
    unit_px = BOMB_WORLD_PX / length
    render_sprites.setup(frame=FRAME_PX, samples=96, unit_px=unit_px)
    for i in range(FRAMES):
        spin = math.radians(i * 360 / FRAMES)
        # spin about the long axis (Y) first, then +90 about X turns the nose (-Y) to -Z (down); the tilt
        # leaves the nose leaning a little towards the viewer
        body.rotation_euler = (math.radians(90 - TILT), spin, 0)
        render_sprites.render_to(os.path.join(RENDER, f"frame-{i:02d}.png"))


try:
    import bpy  # noqa: F401  (inside Blender: render)
except ImportError:  # plain Python: run Blender on this file, then pack
    subprocess.run(["rm", "-rf", RENDER])
    subprocess.run(["nice", "-n", "15", os.environ.get("BLENDER", "blender"), "-b", "-t", "4", "-P",
                    os.path.abspath(__file__)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "artsrc", "units", "pack_sprites.py"), RENDER, OUT],
                   check=True)
else:
    render()
