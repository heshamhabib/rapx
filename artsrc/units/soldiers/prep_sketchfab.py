"""
Turns a rigged, textured Sketchfab soldier (glTF, CC BY 4.0) into a body for the 3D soldier pipeline:
the body meshes in their rest pose with their original textures (no view painting), 1.8 m tall, feet on the
ground, facing -Y, saved as upload/<id>.blend (object <id>, flagged keep_materials) - render_soldier.py then puts
it on e1's Mixamo rig like the AI bodies. The weapon (meshes driven by the given weapon bones) is saved separately
as upload/<id>-weapon.blend (object Weapon: grip at the origin, barrel along +Y, muzzle at its +Y end).

  blender -b -P artsrc/units/soldiers/prep_sketchfab.py -- <id> <scene.gltf> <weapon bone prefix,...> [grip 0-1] [--armbands]
  (unrigged models standing in an A-pose work too: every mesh is the body; pass "" for the weapon bones)
  Options for unrigged models (robots, IDEA-29):
    --yaw=<deg>          turn the model (counter-clockwise, before anything else) so it faces -Y
    --keep-near=<x>      a pack of several figures: keep the meshes whose centre is nearest x (model units)
    --decimate=<ratio>   reduce a very heavy mesh (e.g. 0.08) before saving
    --tpose=<sx>,<sz>[,<deg>]  T-pose arms: lower everything outside |x| > sx (metres of the 1.8 m body) about the
                         shoulder pivot (+-sx, sz) by deg (default 42) into the rig's A-pose, blended at the shoulder

grip: where the right hand holds the weapon, as a fraction of its length from the stock (default 0.3).
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:]
UID, GLTF, WEAPON_BONES = argv[0], argv[1], [b for b in argv[2].split(",") if b]
GRIP = float(argv[3]) if len(argv) > 3 and not argv[3].startswith("--") else 0.3
OPTS = {a.split("=")[0]: a.split("=", 1)[1] for a in sys.argv if a.startswith("--") and "=" in a}
HEIGHT = 1.8

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLTF)
scene = bpy.context.scene

# Bake every skinned mesh into its rest-pose geometry, drop helpers (stray spheres, loose bullets, empties)
arm = next((o for o in scene.objects if o.type == "ARMATURE"), None)
if arm is None:
    # Unrigged model (already standing in an A-pose): every mesh is the body
    for o in [o for o in scene.objects if o.type == "MESH"]:
        o.data = o.data.copy()
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
        if "--yaw" in OPTS:
            o.data.transform(Matrix.Rotation(math.radians(float(OPTS["--yaw"])), 4, "Z"))
    if "--keep-near" in OPTS:
        kx = float(OPTS["--keep-near"])
        cent = {o: sum((v.co for v in o.data.vertices), Vector()) / max(1, len(o.data.vertices))
                for o in scene.objects if o.type == "MESH"}
        xs = sorted({round(c.x, 1) for c in cent.values()})
        # the figure whose meshes cluster nearest kx: drop meshes farther than half the gap to the next figure
        gap = min((abs(c.x - kx) for c in cent.values()))
        for o, c in cent.items():
            if abs(c.x - kx) > gap + float(OPTS.get("--keep-r", "1.5")):
                bpy.data.objects.remove(o)
    for o in list(scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    arm_meshes = [o for o in scene.objects if o.type == "MESH"]
    for o in arm_meshes:
        o["_static"] = True
skinned = [o for o in scene.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
baked = []
if arm is None:
    baked = [(o, 0.0) for o in scene.objects if o.type == "MESH"]
    skinned = []
# Some rigs (Sketchfab exports of Unreal skeletons) lie on their back in the rest pose; the default pose stands them
# up through the root bones. That root rotation, applied to the rest-pose body, gives an upright A-pose.
if arm is not None:
    root = next((b for b in arm.pose.bones if b.parent and b.parent.parent is None), arm.pose.bones[0])
    arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    upright = (arm.matrix_world @ root.matrix) @ (arm.matrix_world @ root.bone.matrix_local).inverted()
    upright = upright.to_quaternion().to_matrix().to_4x4()  # rotation only
    print("root", root.name, "upright rotation", [round(a, 1) for a in [math.degrees(x) for x in upright.to_euler()]])
for o in skinned:
    groups = {g.index: g.name for g in o.vertex_groups}
    is_weapon = None
    # how much of the mesh the weapon bones drive
    weapon_w = 0.0
    total_w = 0.0
    for v in o.data.vertices:
        for g in v.groups:
            total_w += g.weight
            if any(groups[g.group].startswith(p) for p in WEAPON_BONES):
                weapon_w += g.weight
    share = weapon_w / max(total_w, 1e-6)
    # the body in its rest A-pose; the weapon in the model's default pose, where its bones give it its real size
    arm.data.pose_position = "POSE" if share >= 0.5 else "REST"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    me.transform(o.matrix_world)
    if share < 0.5:
        me.transform(upright)
    new = bpy.data.objects.new(o.name + "_baked", me)
    scene.collection.objects.link(new)
    baked.append((new, share))
for o in list(scene.objects):
    if o not in [b for b, _ in baked]:
        bpy.data.objects.remove(o)
for o, _ in baked:
    o.modifiers.clear()

body_parts = [o for o, w in baked if w < 0.5]
weapon_parts = [o for o, w in baked if w >= 0.5]
# Only the weapon itself (the biggest part): loose bits such as a bullet lying elsewhere are dropped
if weapon_parts:
    keep = max(weapon_parts, key=lambda o: len(o.data.polygons))
    for o in weapon_parts:
        if o is not keep:
            bpy.data.objects.remove(o)
    weapon_parts = [keep]
print("body parts", len(body_parts), "weapon parts", len(weapon_parts))


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    return o


body = join(body_parts, UID)
pts = np.array([v.co[:] for v in body.data.vertices])
lo, hi = pts.min(0), pts.max(0)
scale = HEIGHT / (hi[2] - lo[2])
shift = Matrix.Translation(-Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2])))
body.data.transform(Matrix.Scale(scale, 4) @ shift)
for p in body.data.polygons:
    p.use_smooth = True
body["keep_materials"] = True

if "--tpose" in OPTS:
    # Lower T-pose arms into the A-pose of e1's rig: rotate every vertex outside the shoulder line about the
    # shoulder pivot, the angle ramping in over a short band so the shoulder bends instead of tearing
    parts = [float(v) for v in OPTS["--tpose"].split(",")]
    sx, sz = parts[0], parts[1]
    deg = math.radians(parts[2] if len(parts) > 2 else 42)
    co = np.empty(len(body.data.vertices) * 3)
    body.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    ax = np.abs(co[:, 0])
    side = np.sign(co[:, 0])
    f = np.clip((ax - sx) / 0.1, 0, 1)
    f = f * f * (3 - 2 * f)
    ang = -deg * f * side                      # right arm (x > 0) turns clockwise in XZ, the left mirrored
    px = side * sx
    dx, dz = co[:, 0] - px, co[:, 2] - sz
    co[:, 0] = px + dx * np.cos(ang) - dz * np.sin(ang)
    co[:, 2] = sz + dx * np.sin(ang) + dz * np.cos(ang)
    body.data.vertices.foreach_set("co", co.ravel())
    body.data.update()
    # back to standing on the ground at 1.8 m
    co2 = co
    lo2, hi2 = co2.min(0), co2.max(0)
    body.data.transform(Matrix.Translation(Vector((0, 0, -lo2[2]))))
    print("arms lowered by %.0f degrees about (%.2f, %.2f)" % (math.degrees(deg), sx, sz))

if "--decimate" in OPTS:
    dec = body.modifiers.new("decimate", "DECIMATE")
    dec.ratio = float(OPTS["--decimate"])
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier="decimate")
    print("decimated to", len(body.data.polygons), "faces")

# Team colour: models have no pure-green areas, so add an armband round each upper arm (part of the body mesh,
# so it takes the arm's skin weights and moves with it). PlayerColorShift recolours the green in game.
if "--armbands" in sys.argv:
    import bmesh
    green = bpy.data.materials.new("TeamColour")
    green.use_nodes = True
    g = green.node_tree.nodes["Principled BSDF"]
    g.inputs["Base Color"].default_value = (0, 1, 0, 1)
    g.inputs["Roughness"].default_value = 0.6
    body.data.materials.append(green)
    mi = len(body.data.materials) - 1
    v = np.array([x.co[:] for x in body.data.vertices])
    bm = bmesh.new()
    bm.from_mesh(body.data)
    for side in (1, -1):
        # upper arm in the A-pose: the arm vertices between shoulder and elbow height, outside the torso
        z0, z1 = 1.22, 1.36
        sel = v[(np.sign(v[:, 0]) == side) & (np.abs(v[:, 0]) > 0.2) & (v[:, 2] > z0) & (v[:, 2] < z1)]
        if len(sel) < 10:
            continue
        c = sel.mean(0)
        r = np.percentile(np.linalg.norm((sel - c)[:, [1, 2]], axis=1), 80) * 1.12
        # the arm slopes down and out: band axis = the arm direction in that slice
        _, _, vt = np.linalg.svd(sel - c, full_matrices=False)
        axis = Vector(vt[0].tolist()).normalized()
        if axis.x * side < 0:
            axis = -axis
        ret = bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=r, radius2=r, depth=0.07)
        rot = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
        bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(c.tolist())) @ rot, verts=ret["verts"])
        for f in {f for vv in ret["verts"] for f in vv.link_faces}:
            f.material_index = mi
            f.smooth = True
    bm.to_mesh(body.data)
    bm.free()
    print("armbands added")

if weapon_parts:
    weapon = join(weapon_parts, "Weapon")
    weapon.data.transform(Matrix.Scale(scale, 4) @ shift)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(weapon.data)
    bm.verts.ensure_lookup_table()
    seen, islands = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        stack, isl = [v], []
        seen.add(v)
        while stack:
            u = stack.pop()
            isl.append(u)
            for e in u.link_edges:
                x = e.other_vert(u)
                if x not in seen:
                    seen.add(x)
                    stack.append(x)
        islands.append(isl)
    allpts = np.array([v.co[:] for v in bm.verts])
    centre = np.median(allpts, axis=0)
    spread = np.percentile(np.linalg.norm(allpts - centre, axis=1), 80)
    far = [v for isl in islands
           if np.linalg.norm(np.array([u.co[:] for u in isl]).mean(0) - centre) > 1.6 * spread for v in isl]
    bmesh.ops.delete(bm, geom=far, context="VERTS")
    bm.to_mesh(weapon.data)
    bm.free()
    print("weapon: dropped", len(far), "detached verts")
    w = np.array([v.co[:] for v in weapon.data.vertices])
    c = w.mean(0)
    # long axis by PCA; the barrel end is the thinner end
    _, _, vt = np.linalg.svd(w - c, full_matrices=False)
    axis = vt[0]
    t = (w - c) @ axis
    ends = (t > np.percentile(t, 90), t < np.percentile(t, 10))
    thick = [np.linalg.norm(w[e] - w[e].mean(0), axis=1).mean() for e in ends]
    if thick[0] > thick[1]:
        axis = -axis
        t = -t
    tmin, tmax = t.min(), t.max()
    grip = c + axis * (tmin + GRIP * (tmax - tmin))
    up = Vector((0, 0, 1))
    y = Vector(axis.tolist()).normalized()
    x = y.cross(up).normalized()
    z = x.cross(y).normalized()
    rot = Matrix((x, y, z)).to_4x4()  # rows = new axes: maps world -> weapon frame
    weapon.data.transform(rot @ Matrix.Translation(-Vector(grip.tolist())))
    weapon["muzzle"] = float((tmax - tmin) * (1 - GRIP))
    for p in weapon.data.polygons:
        p.use_smooth = True
    os.makedirs(os.path.join(HERE, "upload"), exist_ok=True)
    bpy.data.libraries.write(os.path.join(HERE, "upload", f"{UID}-weapon.blend"), {weapon}, fake_user=True)
    print("weapon: length %.2f m, muzzle %.2f m ahead of the grip" % ((tmax - tmin), weapon["muzzle"]))
    bpy.data.objects.remove(weapon)

os.makedirs(os.path.join(HERE, "upload"), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "upload", f"{UID}.blend"))
print("body", UID, len(body.data.polygons), "faces, height %.2f m" % HEIGHT)
