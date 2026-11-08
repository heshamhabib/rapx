#!/usr/bin/env python3
"""
Falling strategic bombs for the bomber strikes (rules/fatman.yaml, rules/tu95.yaml): a Sketchfab model rendered
nose-down, slowly turning about its long axis while it falls, packed into mods/rapx/bits/hd/fx/<name>-bomb.png
(sequence `falling` in sequences/fatman.yaml).

  python3 artsrc/fx/make_bomb_fx.py [fatman|rds37 ...]   (from the repo root; runs Blender itself; default: all)

  fatman  "Atomic Bomb - FATMAN" by CaptainTux (CC-BY-4.0), USA Fatman Strike
  rds37   the RDS-37 under "Tu-95M with RDS-37" by Jeyhun1985 (CC-BY-4.0), Russia's thermonuclear strike

Bombs are drawn larger than real size (a 3.25 m Fatman would be 8 world px) so they read while they fall, like the
nuke's falling missile (atomic.down Scale 1.8).
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
GLB = os.path.join(ROOT, "artsrc", "units", "meshes", "glb", "sketchfab")
# name -> (glTF, parts kept (None = all), on-screen length in world px). Every model's nose points to -Y.
BOMBS = {
    "fatman": (os.path.join(GLB, "inbox4", "fatman", "scene.gltf"), None, 22),
    "rds37": (os.path.join(GLB, "inbox5", "tu95", "scene.gltf"), ["Object_7", "Object_2", "Object_3", "Object_8"], 28),
}
FRAMES = 16
FRAME_PX = 120  # sprite px (3 per world px): a 40 px world frame
TILT = 18  # degrees off vertical, nose down and a little ahead


def paths(name):
    return (os.path.join(HERE, "preview", f"{name}-bomb"),
            os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", f"{name}-bomb.png"))


def render(name):
    import bpy
    from mathutils import Vector

    sys.path.insert(0, os.path.join(ROOT, "artsrc", "units"))
    os.environ["PX_LIGHT"] = "hd"
    os.environ["PX_NO_GROUND"] = "1"
    import render_sprites

    bpy.ops.wm.read_factory_settings(use_empty=True)
    src, keep, world_px = BOMBS[name]
    render_dir = paths(name)[0]
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    for o in [o for o in bpy.data.objects if o.type == "MESH" and keep and o.name not in keep]:
        bpy.data.objects.remove(o)
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
    unit_px = world_px / length
    render_sprites.setup(frame=FRAME_PX, samples=96, unit_px=unit_px)
    for i in range(FRAMES):
        spin = math.radians(i * 360 / FRAMES)
        # spin about the long axis (Y) first, then +90 about X turns the nose (-Y) to -Z (down); the tilt
        # leaves the nose leaning a little towards the viewer
        body.rotation_euler = (math.radians(90 - TILT), spin, 0)
        render_sprites.render_to(os.path.join(render_dir, f"frame-{i:02d}.png"))


try:
    import bpy  # noqa: F401  (inside Blender: render the bomb named after "--")
except ImportError:  # plain Python: run Blender for each bomb, then pack
    for bomb in sys.argv[1:] or list(BOMBS):
        render_dir, out = paths(bomb)
        subprocess.run(["rm", "-rf", render_dir])
        subprocess.run(["nice", "-n", "15", os.environ.get("BLENDER", "blender"), "-b", "-t", "4", "-P",
                        os.path.abspath(__file__), "--", bomb], cwd=ROOT, check=True, capture_output=True)
        subprocess.run([sys.executable, os.path.join(ROOT, "artsrc", "units", "pack_sprites.py"), render_dir, out],
                       check=True)
else:
    render(sys.argv[sys.argv.index("--") + 1])
