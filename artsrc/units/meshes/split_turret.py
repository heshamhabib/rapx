"""
Splits a single-mesh unit (from import_glb.py) into "Body" and a rotating "Turret" root.

Faces whose centre lies above z_cut and within an ellipse (rx, ry) around (cx, cy) - plus anything
beyond the ellipse's front edge above the cut, i.e. the gun barrel - become the turret. A dark
disc closes the hole left in the hull. The Turret root sits on the actor centre (0, 0) so the
renderer can turn it about its own pivot; the engine places it with Turreted Offset (printed).

  Blender -b <unit>.blend -P artsrc/units/meshes/split_turret.py -- <out.blend> cx cy rx ry z_cut [ring 0|1]

ring 0 skips the dark disc (spinners mounted on masts, where a disc would show).
"""

import math
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
CX, CY, RX, RY, ZCUT = (float(a) for a in argv[1:6])
RING = argv[6] != "0" if len(argv) > 6 else True
WDIST_PER_UNIT = 1024 / 24 * 3.5

body = bpy.data.objects["Body"]
src = next(o for o in body.children if o.type == "MESH")

bm = bmesh.new()
bm.from_mesh(src.data)
bm.faces.ensure_lookup_table()
pick = []
for f in bm.faces:
    c = f.calc_center_median()
    if c.z <= ZCUT:
        continue
    dx, dy = (c.x - CX) / RX, (c.y - CY) / RY
    in_ring = dx * dx + dy * dy <= 1.0
    barrel = c.y > CY and abs(c.x - CX) < RX * 0.6  # gun pointing forward past the turret
    if in_ring or barrel:
        pick.append(f)

turret_bm = bmesh.new()
vmap = {}
for f in pick:
    vs = []
    for v in f.verts:
        if v not in vmap:
            vmap[v] = turret_bm.verts.new(v.co - Vector((CX, CY, 0)))
        vs.append(vmap[v])
    nf = turret_bm.faces.new(vs)
    nf.material_index = f.material_index
uv_src = bm.loops.layers.uv.active
if uv_src:
    uv_dst = turret_bm.loops.layers.uv.new("UVMap")
    for f, nf in zip(pick, turret_bm.faces):
        for l, nl in zip(f.loops, nf.loops):
            nl[uv_dst].uv = l[uv_src].uv
bmesh.ops.delete(bm, geom=pick, context="FACES")
bm.to_mesh(src.data)
bm.free()

tmesh = bpy.data.meshes.new("TurretMesh")
turret_bm.to_mesh(tmesh)
turret_bm.free()
for m in src.data.materials:
    tmesh.materials.append(m)
turret = bpy.data.objects.new("Turret", None)
bpy.context.scene.collection.objects.link(turret)
tobj = bpy.data.objects.new("TurretShell", tmesh)
bpy.context.scene.collection.objects.link(tobj)
tobj.parent = turret
for p in tmesh.polygons:
    p.use_smooth = True

# Dark ring closing the hull under the turret
if RING:
    ring_mat = bpy.data.materials.new("Ring")
    ring_mat.use_nodes = True
    ring_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
    bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=0.04, location=(CX, CY, ZCUT))
    ring = bpy.context.object
    ring.scale = (RX * 0.95, RY * 0.95, 1)
    ring.data.materials.append(ring_mat)
    ring.parent = body

print(f"turret faces {len(pick)}; Turreted Offset: {round(CY * WDIST_PER_UNIT * 0.88)},{round(-CX * WDIST_PER_UNIT * 0.88)},0")
print(f"turret pivot height {ZCUT:.2f}")
turret["px_pivot"] = (CX, CY, 0.0)
body.name = "Hull"  # render with artsrc/units/tanks/render_tank.py (hull 0-31, turret 32-63)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
