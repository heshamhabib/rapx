"""
The Sk-27 Flankard's source model (Sketchfab Su-27P; imported with yaw 180, its nose points to -y) is posed for maintenance: the radome is swung up and the
canopy is open, and both sit in the team-colour box (green in the renders). This closes them in sk-27-flankard.blend:
the radome is turned so its axis points forward and its base ring meets the front of the hull; the canopy and its
glass are turned down about their rear hinge until they lie level on the fuselage. The team-colour mask is moved
from the cockpit to the tail fins (the import box assumed the nose points the other way).

  blender -b artsrc/units/meshes/sk-27-flankard.blend -P artsrc/units/meshes/fix_su27_pose.py [-- --save]
"""
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

SAVE = "--save" in sys.argv


def obj(prefix):
    return next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(prefix))


def world_verts(o):
    m = o.matrix_world
    return np.array([tuple(m @ v.co) for v in o.data.vertices])


def apply(o, transform):
    """Apply a world-space 4x4 transform to the object's vertices (keeping the object transform)."""
    m = o.matrix_world
    inv = m.inverted()
    t = inv @ transform @ m
    for v in o.data.vertices:
        v.co = t @ v.co
    o.data.update()


def rotation_between(a, b):
    a, b = Vector(a).normalized(), Vector(b).normalized()
    return a.rotation_difference(b).to_matrix().to_4x4()


hull = obj("hull_")
nose = obj("nose_Material")
canopy = obj("canopy_")
glass = obj("glass_")

# Which way the nose points along y (+1 after the import's yaw 180, -1 in the raw model)
hv = world_verts(hull)
nv = world_verts(nose)
f = 1.0 if nv[:, 1].mean() > hv[:, 1].mean() else -1.0

# Front opening of the hull: its foremost vertices
ext = hv[:, 1] * f
front = hv[ext > ext.max() - 0.08]
H = front.mean(axis=0)

# Radome: a cone; its base is the wider end. Turn its axis forward (a slight droop) and put the base on the hull
c = nv.mean(axis=0)
_, _, vt = np.linalg.svd(nv - c)
proj = (nv - c) @ vt[0]
lo, hi = nv[proj < proj.min() + 0.08], nv[proj > proj.max() - 0.08]
spread = lambda p: np.linalg.norm(p - p.mean(axis=0), axis=1).mean()
base, tipside = (lo, hi) if spread(lo) > spread(hi) else (hi, lo)
B, T = base.mean(axis=0), tipside.mean(axis=0)
print("nose points", "+y" if f > 0 else "-y", "radome base", B.round(2), "tip", T.round(2), "hull front", H.round(2))
rot = rotation_between(T - B, (0, f, -0.04))
apply(nose, Matrix.Translation(Vector(H)) @ rot @ Matrix.Translation(-Vector(B)))

# Canopy: hinged at its rear bottom; of the two ways to turn it level, keep the one that lies lowest
cv = np.vstack([world_verts(canopy), world_verts(glass)])
rear_ext = -cv[:, 1] * f
rear = cv[rear_ext > rear_ext.max() - 0.1]
P = rear[rear[:, 2].argmin()]
cc = cv.mean(axis=0)
_, _, vt = np.linalg.svd(cv - cc)
long_axis = vt[0] if abs(vt[0][1]) > abs(vt[1][1]) else vt[1]
angle = abs(np.arctan2(abs(long_axis[2]), abs(long_axis[1])))
best = None
for sign in (1, -1):
	m = Matrix.Translation(Vector(P)) @ Matrix.Rotation(sign * angle, 4, "X") @ Matrix.Translation(-Vector(P))
	top = max((m @ Vector(v))[2] for v in cv)
	if best is None or top < best[0]:
		best = (top, m)
print("canopy hinge", P.round(2), "tilt deg", np.degrees(angle).round(1))
for o in (canopy, glass):
	apply(o, best[1])

# Team colour on the tail fins only: the top 45% of the rearmost 30% (never the radome or canopy)
meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data.attributes.get("px_team")]
allv = np.vstack([world_verts(o) for o in meshes])
lo_b, hi_b = allv.min(axis=0), allv.max(axis=0)
z0 = lo_b[2] + 0.55 * (hi_b[2] - lo_b[2])
tail_cut = (hi_b[1] - 0.3 * (hi_b[1] - lo_b[1])) if f < 0 else (lo_b[1] + 0.3 * (hi_b[1] - lo_b[1]))
for o in meshes:
	v = world_verts(o)
	in_tail = (v[:, 1] >= tail_cut) if f < 0 else (v[:, 1] <= tail_cut)
	inside = (in_tail & (v[:, 2] >= z0)).astype(float)
	if o in (nose, canopy, glass):
		inside[:] = 0
	o.data.attributes["px_team"].data.foreach_set("value", inside.tolist())
	o.data.update()

for o in (nose, canopy, glass):
	v = world_verts(o)
	print("now", o.name, v.min(axis=0).round(2), v.max(axis=0).round(2))

if SAVE:
	bpy.ops.wm.save_mainfile()
	print("saved", bpy.data.filepath)
