"""
Renders the sidebar cameo view of a unit .blend: the model turned to show its front-left side, seen from a low
three-quarter angle (like the concept art the other cameos are cut from), tightly framed on a transparent
background. artsrc/px-cameos/generate.py stages it on the tile backdrop.

  Blender -b <unit>.blend -P artsrc/units/meshes/render_cameo.py -- <out.png> [elevation degrees] [facing 0-31]
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("PX_LIGHT", "hd")
os.environ["PX_NO_GROUND"] = "1"  # the tile draws its own soft shadow
import render_sprites  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
ELEV = math.radians(float(argv[1]) if len(argv) > 1 else 28)
FACING = int(argv[2]) if len(argv) > 2 else 12
W, H = 960, 640

render_sprites.setup(frame=W, samples=128, zoom=1, unit_px=3.5)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = W, H

# Assemble the unit at the facing: hull/body turned, turrets placed on their ring and turned with it
angle = math.radians(FACING * 360 / 32)
main = next(o for o in bpy.data.objects if o.name in ("Hull", "Body"))
render_sprites.face(main, FACING, 32)
for o in bpy.data.objects:
    pivot = o.get("px_pivot") or o.get("px_hub")
    if pivot is None or o.parent:
        continue
    x, y, z = pivot
    o.location = (x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle), z)
    o.rotation_euler = (0, 0, angle)
bpy.context.view_layer.update()

# Low three-quarter camera, framed on the model's projected bounds
cam = scene.camera
cam.location = Vector((0, -50 * math.cos(ELEV), 50 * math.sin(ELEV)))
cam.rotation_euler = (math.radians(90) - ELEV, 0, 0)
bpy.context.view_layer.update()
right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
pts = []
dg = bpy.context.evaluated_depsgraph_get()
for o in bpy.data.objects:
    if o.type != "MESH" or not o.visible_get() or o.hide_render or o.name.lower().startswith(("shadow", "ground")):
        continue
    me = o.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(o.matrix_world)
    pts.append(co @ m[:3, :3].T + m[:3, 3])
pts = np.concatenate(pts)
u, v = pts @ np.array(right), pts @ np.array(up)
cu, cv = (u.min() + u.max()) / 2, (v.min() + v.max()) / 2
span = max((u.max() - u.min()), (v.max() - v.min()) * W / H) * 1.06
cam.data.ortho_scale = span
cam.location = cam.location + right * cu + up * cv - (Vector(cam.location) @ right) * right - (Vector(cam.location) @ up) * up
render_sprites.render_to(OUT)
print("cameo", OUT)
