"""
The V2RL's own rocket as a flying sprite: the "Rocket" part of meshes/v2rl.blend rendered alone, centred, from 32
directions, in three attitudes (climb / level / dive), at the same pixel density and light as the launcher, so the
rocket that flies is the one that was on the rail (weapons/missiles.yaml SCUD, sequences pxmissile v2*).

  PX_LIGHT=punchy PX_NO_GROUND=1 Blender -b artsrc/units/meshes/v2rl.blend -P artsrc/units/vehicles/render_v2_rocket.py -- <out dir> [name] [one]
  python3 artsrc/units/pack_sprites.py <out dir>/<attitude> mods/rapx/bits/hd/fx/missile-<attitude>.png
(make_v2_rocket.sh does both.) name (default v2) names the attitudes <name>, <name>-climb, <name>-dive; "one" keeps a
single missile when the Rocket part holds a pair side by side (the Zolfaghar: the loose pieces on the +x side); "first"
keeps the first rocket when every rocket is its own part (the Thunderhead MLRS).

Rendered at the launcher's density (its 448px frames: unit_px 3.5 at zoom 2 = 21 px per unit), so the same sprite
Scale (0.2333) draws it at the same size. Measured on that render, the rocket's centre sits 42 px up and ~4 px behind
the launcher's origin = SCUD LocalOffset -45,0,420 (1 render px = 0.2333 game px = 9.96 world units); its length
(196 px) is ~1950 world units, so PxRocket Length (exhaust behind the centre) is half that.
"""

import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import render_sprites  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
NAME = ARGS[1] if len(ARGS) > 1 else "v2"
ONE = len(ARGS) > 2 and ARGS[2] == "one"
FIRST = len(ARGS) > 2 and ARGS[2] == "first"
FRAME = 256
ATTITUDES = {NAME: 0, f"{NAME}-climb": 35, f"{NAME}-dive": -35}

objs = bpy.data.objects
rocket = objs["Rocket"]
parts = [o for o in rocket.children_recursive if o.type == "MESH"]
if FIRST:
    parts = sorted(parts, key=lambda o: o.name)[:1]
others = [o for o in objs if o.type == "MESH" and o not in parts]
if ONE:
    # Keep the pieces of the rocket part that lie on the +x side of its centre line (one missile of the pair)
    import bmesh
    for o in parts:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        mw = o.matrix_world
        cx = sum((mw @ v.co).x for v in bm.verts) / max(1, len(bm.verts))
        drop = [f for f in bm.faces if (mw @ f.calc_center_median()).x < cx]
        bmesh.ops.delete(bm, geom=drop, context="FACES")
        bm.to_mesh(o.data)
        bm.free()

# Where the rocket sits: centre of its bounding box, in model units (+Y forward, +Z up)
pts = [o.matrix_world @ v.co for o in parts for v in o.data.vertices]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre = (lo + hi) / 2
render_sprites.setup(frame=FRAME, samples=48, unit_px=7.0)
print(f"rocket centre (units) {tuple(round(c, 3) for c in centre)}, length {round(hi.y - lo.y, 3)}")

for o in others:
    o.hide_render = True

# yaw root -> pitch root -> rocket meshes moved so the rocket's centre is at the origin
yaw = objs.new("Yaw", None)
pitch = objs.new("Pitch", None)
bpy.context.scene.collection.objects.link(yaw)
bpy.context.scene.collection.objects.link(pitch)
pitch.parent = yaw
for o in parts:
    world = o.matrix_world.copy()
    o.parent = pitch
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_world = Matrix.Translation(-centre) @ world

for name, angle in ATTITUDES.items():
    pitch.rotation_euler = (math.radians(angle), 0, 0)
    for f in range(32):
        render_sprites.face(yaw, f, 32)
        render_sprites.render_to(os.path.join(OUT, name, f"frame-{f:02d}.png"))
print("rendered v2 rocket")
