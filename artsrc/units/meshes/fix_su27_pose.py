"""
The Sk-27 Flankard's source model (Sketchfab Su-27P) is posed for maintenance: the radome is swung up and the
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

# Front opening of the hull: its foremost vertices (smallest y)
hv = world_verts(hull)
front = hv[hv[:, 1] < hv[:, 1].min() + 0.08]
H = front.mean(axis=0)

# Radome: a cone. Its tip is the vertex furthest from the hull front; its base ring is the widest end
nv = world_verts(nose)
c = nv.mean(axis=0)
_, _, vt = np.linalg.svd(nv - c)
axis = vt[0]
proj = (nv - c) @ axis
tip_end = 1 if abs(proj.max()) > abs(proj.min()) else -1
# The base is the end whose cross-section is wider
lo, hi = nv[proj < proj.min() + 0.08], nv[proj > proj.max() - 0.08]
spread = lambda p: np.linalg.norm(p - p.mean(axis=0), axis=1).mean()
base, tipside = (lo, hi) if spread(lo) > spread(hi) else (hi, lo)
B = base.mean(axis=0)
T = tipside.mean(axis=0)
print("radome base", B.round(2), "tip", T.round(2), "hull front", H.round(2))
rot = rotation_between(T - B, (0, -1, -0.04))
move = Matrix.Translation(Vector(H)) @ rot @ Matrix.Translation(-Vector(B))
apply(nose, move)

# Canopy: hinged at its rear bottom; turn it down about the x axis until its long axis is level
cv = np.vstack([world_verts(canopy), world_verts(glass)])
rear = cv[cv[:, 1] > cv[:, 1].max() - 0.1]
P = rear[rear[:, 2].argmin()]
cc = cv.mean(axis=0)
_, _, vt = np.linalg.svd(cv - cc)
long_axis = vt[0] if abs(vt[0][1]) > abs(vt[1][1]) else vt[1]
angle = np.arctan2(long_axis[2], abs(long_axis[1])) * (1 if long_axis[1] < 0 else -1)
print("canopy hinge", P.round(2), "tilt deg", np.degrees(angle).round(1))
hinge = Matrix.Translation(Vector(P)) @ Matrix.Rotation(angle, 4, "X") @ Matrix.Translation(-Vector(P))
for o in (canopy, glass):
	apply(o, hinge)

# The team-colour mask (px_team, import_sketchfab.py) used JET_BOX "rear 30%, top 45%" as fractions of the bounds
# from low y, but this model's nose points to -y, so the box sat on the cockpit and the raised radome/canopy. Redo it
# on the real tail: the top 45% of the rearmost 30% (high y).
meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data.attributes.get("px_team")]
allv = np.vstack([world_verts(o) for o in meshes])
lo, hi = allv.min(axis=0), allv.max(axis=0)
y0 = hi[1] - 0.3 * (hi[1] - lo[1])
z0 = lo[2] + 0.55 * (hi[2] - lo[2])
for o in meshes:
	v = world_verts(o)
	inside = ((v[:, 1] >= y0) & (v[:, 2] >= z0)).astype(float)
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
