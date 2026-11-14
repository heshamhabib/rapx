"""
Renders a Mixamo-animated soldier (FBX "With Skin") into OpenRA sprite frames with the unit camera and lights
(artsrc/units/render_sprites.py): every facing (counter-clockwise from north) x the chosen animation frames.
The soldier is coloured from his concept views (soldier_paint.py) and carries a weapon prop placed every frame
from both hands (grip in the right hand, pointing through the left hand).

  blender -b -P artsrc/units/soldiers/render_soldier.py -- <id> <anim.fbx> <out dir> <facings> <frames|"auto:N"> [samples]

frames: comma-separated animation frames, or auto:N for N frames spread evenly over the clip.
Writes <out dir>/f<facing>-<n>.png.
"""

import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import render_sprites  # noqa: E402
import soldier_paint  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
UID, FBX, OUT, FACINGS, FRAMES = argv[0], argv[1], argv[2], int(argv[3]), argv[4]
SAMPLES = int(argv[5]) if len(argv) > 5 else 48

FRAME_PX = 192
# World pixels per metre: a standing soldier (1.8 m) projects to ~25 world px with the 50 degree camera
UNIT_PX = 19.0

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX)
arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
body = next(o for o in bpy.context.scene.objects if o.type == "MESH")

# Robots built from separate hard parts (IDEA-29): each loose part follows a single bone rigidly, the one that holds
# most of its transferred weight, so plates and limbs move like machinery instead of smearing across joints
RIGID = {"bdrd", "rgun"}


# Robots with other proportions: e1's skeleton (rest pose) refitted to them before binding. shoulder = the robot's
# shoulder joint (x, z, metres; the pivot its arms were lowered about in prep_sketchfab.py), arm = shoulder to finger
# tips. The animations rotate the bones, so they play the same on the refitted skeleton.
# hip = the hip joint (x, z): the leg chain is moved there and scaled to reach the ground.
FIT = {"bdrd": {"shoulder": (0.2, 1.40), "arm": 0.7},
       "rgun": {"shoulder": (0.33, 1.31), "arm": 0.61},
}
# Bodies weighted by distance to the refitted bones (one-piece meshes too unlike a human for the surface transfer)
PROXIMITY = set()


def fit_skeleton(fit):
    import numpy as np
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    inv = arm.matrix_world.inverted()
    w = arm.matrix_world
    sx, sz = fit["shoulder"]
    for side, sgn in (("Left", 1), ("Right", -1)):
        root = eb.get(f"mixamorig:{side}Arm")
        clav = eb.get(f"mixamorig:{side}Shoulder")
        if root is None:
            continue
        chain = [root] + list(root.children_recursive)
        old_root = w @ root.head
        tip = max(((w @ b.tail) - old_root).length for b in chain)
        k = fit["arm"] / max(tip, 1e-3)
        new_root = Vector((sgn * sx, old_root.y, sz))
        for b in chain:
            h, t = w @ b.head, w @ b.tail
            b.head = inv @ (new_root + (h - old_root) * k)
            b.tail = inv @ (new_root + (t - old_root) * k)
        if clav is not None:
            ch = w @ clav.head
            clav.head = inv @ Vector((ch.x, ch.y, sz + 0.06))
            clav.tail = inv @ new_root
    if "hip" in fit:
        hx, hz = fit["hip"]
        for side, sgn in (("Left", 1), ("Right", -1)):
            root = eb.get(f"mixamorig:{side}UpLeg")
            if root is None:
                continue
            chain = [root] + list(root.children_recursive)
            old_root = w @ root.head
            k = hz / max(old_root.z, 1e-3)
            new_root = Vector((sgn * hx, old_root.y, hz))
            for b in chain:
                h, t = w @ b.head, w @ b.tail
                b.head = inv @ (new_root + Vector(((h - old_root).x * k * 0.6, (h - old_root).y * k, (h - old_root).z * k)))
                b.tail = inv @ (new_root + Vector(((t - old_root).x * k * 0.6, (t - old_root).y * k, (t - old_root).z * k)))
    bpy.ops.object.mode_set(mode="OBJECT")
    print("skeleton fitted:", fit)


def proximity_weights(obj, falloff=4.0):
    """Every vertex weighted to its two nearest deform bones (rest pose) by inverse distance."""
    import numpy as np
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    groups = obj.vertex_groups
    bones = [bn for bn in arm.data.bones if bn.use_deform and bn.name in groups
             and not any(k in bn.name for k in ("Index", "Middle", "Ring", "Pinky", "Thumb"))]
    heads = np.array([(arm.matrix_world @ bn.head_local)[:] for bn in bones])
    tails = np.array([(arm.matrix_world @ bn.tail_local)[:] for bn in bones])
    seg = tails - heads
    L2 = np.maximum((seg ** 2).sum(1), 1e-9)
    d = np.empty((n, len(bones)), np.float32)
    for i in range(0, n, 20000):
        c = co[i:i + 20000]
        t = np.clip(((c[:, None, :] - heads[None]) * seg[None]).sum(2) / L2[None], 0, 1)
        d[i:i + 20000] = np.sqrt(((c[:, None, :] - (heads[None] + t[..., None] * seg[None])) ** 2).sum(2))
    order = np.argsort(d, 1)[:, :2]
    d2 = np.take_along_axis(d, order, 1)
    w = 1 / np.maximum(d2, 0.01) ** falloff
    w /= w.sum(1, keepdims=True)
    for g in groups:
        g.remove(list(range(n)))
    for k in range(2):
        for bi in range(len(bones)):
            idx = np.nonzero(order[:, k] == bi)[0]
            for v, wt in zip(idx.tolist(), w[idx, k].tolist()):
                groups[bones[bi].name].add([v], wt, "ADD")
    print("proximity weights on", len(bones), "bones")


def rigid_parts(obj):
    """Each loose part of obj follows the deform bone nearest to its centre (rest pose), weight 1."""
    import numpy as np
    me = obj.data
    n = len(me.vertices)
    ed = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    a, b = ed[0::2], ed[1::2]
    label = np.arange(n)
    while True:  # connected components by label propagation
        m = np.minimum(label[a], label[b])
        new_label = label.copy()
        np.minimum.at(new_label, a, m)
        np.minimum.at(new_label, b, m)
        new_label = new_label[new_label]
        if np.array_equal(new_label, label):
            break
        label = new_label
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    parts, inv = np.unique(label, return_inverse=True)
    cent = np.zeros((len(parts), 3))
    np.add.at(cent, inv, co)
    cent /= np.bincount(inv)[:, None]
    groups = obj.vertex_groups
    bones = [bn for bn in arm.data.bones if bn.use_deform and bn.name in groups]
    heads = np.array([(arm.matrix_world @ bn.head_local)[:] for bn in bones])
    tails = np.array([(arm.matrix_world @ bn.tail_local)[:] for bn in bones])
    seg = tails - heads
    L2 = np.maximum((seg ** 2).sum(1), 1e-9)
    t = np.clip(((cent[:, None, :] - heads[None]) * seg[None]).sum(2) / L2[None], 0, 1)
    near = heads[None] + t[..., None] * seg[None]
    best = np.sqrt(((cent[:, None, :] - near) ** 2).sum(2)).argmin(1)
    for g in groups:
        g.remove(list(range(n)))
    for bi in np.unique(best):
        idx = list(map(int, np.nonzero(best[inv] == bi)[0]))
        groups[bones[bi].name].add(idx, 1.0, "REPLACE")
    print("rigid parts:", len(parts), "on", len(np.unique(best)), "bones")


# Another soldier on e1's rig: when the clip is not this soldier's own (no Mixamo upload of his), his body
# from upload/<id>.blend replaces the clip's mesh and takes its skin weights from the nearest surface
# (all soldiers share the A-pose, 1.8 m height and orientation of prep_mixamo.py).
if body.name != UID and os.path.exists(os.path.join(HERE, "upload", f"{UID}.blend")):
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    with bpy.data.libraries.load(os.path.join(HERE, "upload", f"{UID}.blend")) as (src, dst):
        dst.objects = [UID]
    new = dst.objects[0]
    bpy.context.scene.collection.objects.link(new)
    new.matrix_world = Matrix.Identity(4)
    # the clip's mesh lives under the armature's transform; bring it to the same world space as the new body
    donor = body
    donor_world = donor.matrix_world.copy()
    for g in donor.vertex_groups:
        new.vertex_groups.new(name=g.name)
    dt = new.modifiers.new("weights", "DATA_TRANSFER")
    dt.object = donor
    dt.use_object_transform = True
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    bpy.context.view_layer.objects.active = new
    bpy.ops.object.modifier_apply(modifier="weights")
    if UID in FIT:
        fit_skeleton(FIT[UID])
    if UID in RIGID:
        rigid_parts(new)
    elif UID in PROXIMITY:
        proximity_weights(new)
    new.parent = arm
    new.matrix_parent_inverse = arm.matrix_world.inverted()
    mod = new.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    bpy.data.objects.remove(donor)
    body = new
    arm.data.pose_position = "POSE"
    print("body", UID, "on the clip's rig:", len(body.vertex_groups), "groups")

# Colours from the concept views, on the rest pose (textured bodies from prep_sketchfab.py keep their own)
TEXTURED = bool(body.get("keep_materials"))
if not TEXTURED:
    body.data.materials.clear()
    body.data.materials.append(soldier_paint.vertex_color_material())
    # Always repaint: colours that went through Mixamo's FBX come back in the wrong colour space
    for a in list(body.data.color_attributes):
        body.data.color_attributes.remove(a)
    bpy.context.scene.frame_set(int(arm.animation_data.action.frame_range[0]))
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    soldier_paint.paint(body, UID)
    arm.data.pose_position = "POSE"

# Root: turns the whole soldier; the model faces -Y, OpenRA facing 0 is north (+Y)
root = bpy.data.objects.new("Root", None)
bpy.context.scene.collection.objects.link(root)
arm.parent = root
arm.matrix_parent_inverse = Matrix.Rotation(math.pi, 4, "Z")


def make_rifle():
    """A simple dark assault rifle along +Y (grip at the origin), sized for a 1.8 m soldier."""
    mat = bpy.data.materials.new("Gun")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
    bsdf.inputs["Roughness"].default_value = 0.75  # matte: a shiny gun reflects the sky as white blobs
    bsdf.inputs["Metallic"].default_value = 0.1
    parts = [  # (size x, y, z), (centre x, y, z)
        ((0.05, 0.36, 0.07), (0, 0.10, 0.03)),    # receiver + handguard
        ((0.025, 0.30, 0.025), (0, 0.42, 0.04)),  # barrel
        ((0.04, 0.22, 0.09), (0, -0.20, 0.0)),    # stock
        ((0.035, 0.05, 0.14), (0, 0.06, -0.07)),  # magazine
        ((0.03, 0.04, 0.09), (0, -0.03, -0.05)),  # pistol grip
        ((0.035, 0.10, 0.04), (0, 0.08, 0.09)),   # optic
    ]
    objs = []
    for size, centre in parts:
        bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
        o = bpy.context.object
        o.scale = size
        o.data.materials.append(mat)
        objs.append(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    gun = bpy.context.object
    gun.name = "Rifle"
    return gun


def make_launcher():
    """A shoulder-fired rocket launcher along +Y (grip at the origin): olive tube, warhead, sight."""
    olive = bpy.data.materials.new("Tube")
    olive.use_nodes = True
    b = olive.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.09, 0.1, 0.05, 1)
    b.inputs["Roughness"].default_value = 0.7
    dark = bpy.data.materials.new("Gun")
    dark.use_nodes = True
    d = dark.node_tree.nodes["Principled BSDF"]
    d.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
    d.inputs["Roughness"].default_value = 0.75
    objs = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.055, depth=1.05, location=(0, 0.15, 0.1),
                                        rotation=(math.radians(90), 0, 0))
    objs.append((bpy.context.object, olive))
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.075, radius2=0.02, depth=0.2, location=(0, 0.77, 0.1),
                                    rotation=(math.radians(-90), 0, 0))
    objs.append((bpy.context.object, dark))
    for size, centre in (((0.035, 0.05, 0.12), (0, 0.0, 0.0)), ((0.035, 0.05, 0.1), (0, 0.3, 0.02)),
                         ((0.03, 0.12, 0.05), (-0.07, 0.05, 0.14))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
        bpy.context.object.scale = size
        objs.append((bpy.context.object, dark))
    for o, m in objs:
        o.data.materials.append(m)
    bpy.ops.object.select_all(action="DESELECT")
    for o, _ in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0][0]
    # Bake every part's own rotation first, or the joined launcher keeps the tube's 90 degree tilt
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.join()
    tube = bpy.context.object
    tube.name = "Launcher"
    return tube


def make_sniper_rifle():
    """A long bolt-action sniper rifle along +Y (grip at the origin): barrel, big scope, stock, bipod."""
    mat = bpy.data.materials.new("Gun")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.035, 0.035, 0.03, 1)
    bsdf.inputs["Roughness"].default_value = 0.75
    bsdf.inputs["Metallic"].default_value = 0.1
    objs = []
    for size, centre in (((0.05, 0.42, 0.07), (0, 0.12, 0.03)),    # receiver + forend
                         ((0.022, 0.5, 0.022), (0, 0.58, 0.05)),   # long barrel
                         ((0.045, 0.3, 0.1), (0, -0.24, 0.0)),     # stock
                         ((0.03, 0.04, 0.09), (0, -0.03, -0.05)),  # grip
                         ((0.012, 0.012, 0.12), (-0.03, 0.5, -0.04)), ((0.012, 0.012, 0.12), (0.03, 0.5, -0.04))):  # bipod
        bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
        bpy.context.object.scale = size
        objs.append(bpy.context.object)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.028, depth=0.32, location=(0, 0.1, 0.11),
                                        rotation=(math.radians(90), 0, 0))  # scope
    objs.append(bpy.context.object)
    for o in objs:
        o.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.join()
    gun = bpy.context.object
    gun.name = "SniperRifle"
    return gun


def _parts(name, parts, materials):
    """Joins boxes / cylinders into one prop along +Y (grip at the origin).
    parts: (kind, size or (radius, depth), centre, rotation_deg_x, material index)."""
    objs = []
    for kind, size, centre, rot, mi in parts:
        if kind == "box":
            bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
            bpy.context.object.scale = size
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=size[0], depth=size[1], location=centre,
                                                rotation=(math.radians(rot), 0, 0))
        bpy.context.object.data.materials.append(materials[mi])
        objs.append(bpy.context.object)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.join()
    bpy.context.object.name = name
    return bpy.context.object


def _mat(name, rgb, rough=0.75, emit=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 6
    return m


def make_flamer():
    """Flamethrower: a thick tube with a nozzle and a pilot-light housing, olive and dark metal."""
    dark, olive = _mat("Gun", (0.035, 0.035, 0.04)), _mat("Olive", (0.1, 0.11, 0.06))
    return _parts("Flamer", [
        ("cyl", (0.04, 0.55), (0, 0.18, 0.02), 90, 1),          # body
        ("cyl", (0.022, 0.25), (0, 0.55, 0.03), 90, 0),         # nozzle
        ("box", (0.04, 0.06, 0.1), (0, -0.02, -0.06), 0, 0),    # grip
        ("box", (0.035, 0.06, 0.09), (0, 0.32, -0.06), 0, 0),   # front grip
        ("cyl", (0.03, 0.12), (0, 0.5, -0.04), 90, 0),          # pilot light
    ], [dark, olive])


def make_pistol():
    """A pistol in the right hand (Tanya)."""
    dark = _mat("Gun", (0.03, 0.03, 0.035))
    return _parts("Pistol", [
        ("box", (0.035, 0.2, 0.05), (0, 0.08, 0.04), 0, 0),     # slide
        ("box", (0.032, 0.05, 0.11), (0, -0.01, -0.03), 0, 0),  # grip
    ], [dark])


def make_tesla_gun():
    """Shock Trooper's Tesla gun: a heavy barrel with copper coils and a glowing blue tip."""
    dark, copper = _mat("Gun", (0.04, 0.04, 0.05)), _mat("Copper", (0.45, 0.2, 0.08), 0.4)
    glow = _mat("Glow", (0.3, 0.6, 1.0), 0.3, emit=(0.4, 0.75, 1.0))
    return _parts("TeslaGun", [
        ("box", (0.06, 0.4, 0.09), (0, 0.1, 0.02), 0, 0),       # body
        ("cyl", (0.045, 0.06), (0, 0.24, 0.03), 90, 1),         # coils
        ("cyl", (0.045, 0.06), (0, 0.34, 0.03), 90, 1),
        ("cyl", (0.03, 0.12), (0, 0.44, 0.03), 90, 0),          # emitter
        ("cyl", (0.038, 0.04), (0, 0.52, 0.03), 90, 2),         # glowing tip
        ("box", (0.04, 0.05, 0.1), (0, -0.04, -0.06), 0, 0),    # grip
    ], [dark, copper, glow])


# Weapon prop per soldier (rifle by default) and where its muzzle flash sits (prop space)
# None: empty hands (Grenadier throws; Engineer, Medic, Mechanic and Spy carry no gun)
PROPS = {"e3": make_launcher, "snip": make_sniper_rifle, "e2": None, "e4": make_flamer, "e7": make_pistol,
         "shok": make_tesla_gun, "e6": None, "medi": None, "mech": None, "spy": None,
         # Humanoid robots (IDEA-29): Cyborg Trooper heavy auto-pistol, Railgun Robot's long railgun, Tesla Automaton
         # throws lightning from its claws; the Battle Droid and Iron Guard carry the rifle
         "cybt": make_pistol, "rgun": make_sniper_rifle, "taut": None}
MUZZLE = {"e3": (0, 0.9, 0.1), "snip": (0, 0.85, 0.05), "e4": (0, 0.7, 0.03), "e7": (0, 0.2, 0.04),
          "shok": (0, 0.56, 0.03), "cybt": (0, 0.2, 0.04), "rgun": (0, 0.85, 0.05)}
def load_weapon():
    """The model's own weapon (prep_sketchfab.py: upload/<id>-weapon.blend, grip at the origin, barrel along +Y)."""
    with bpy.data.libraries.load(os.path.join(HERE, "upload", f"{UID}-weapon.blend")) as (src, dst):
        dst.objects = ["Weapon"]
    w = dst.objects[0]
    bpy.context.scene.collection.objects.link(w)
    MUZZLE[UID] = (0, float(w.get("muzzle", 0.7)), 0.03)
    return w


if os.path.exists(os.path.join(HERE, "upload", f"{UID}-weapon.blend")):
    PROPS[UID] = load_weapon
_prop = PROPS.get(UID, make_rifle)
gun = _prop() if _prop else None


def place_gun():
    """Grip in the right hand, barrel through the left hand, top facing up."""
    if gun is None:
        return
    bones = arm.pose.bones
    rh = arm.matrix_world @ bones["mixamorig:RightHand"].head
    lh = arm.matrix_world @ bones["mixamorig:LeftHand"].head
    fwd = lh - rh
    if fwd.length < 0.05:
        fwd = arm.matrix_world.to_3x3() @ Vector((0, -1, 0))
    fwd.normalize()
    up = Vector((0, 0, 1))
    side = fwd.cross(up)
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(fwd).normalized()
    rot = Matrix((side, fwd, up)).transposed().to_4x4()
    gun.matrix_world = Matrix.Translation(rh + up * -0.02) @ rot


# The vehicles' punchy light: little sky, a hard sun and a cool rim light, so the figure's edges and folds read
os.environ["PX_LIGHT"] = "punchy"
if os.environ.get("PX_CAMEO"):
    os.environ["PX_NO_GROUND"] = "1"  # the sidebar tile draws its own soft shadow
scene = render_sprites.setup(FRAME_PX, SAMPLES, 1, UNIT_PX)
# Thermal throttle (laptop): fewer CPU threads, low priority and a cooling pause after every frame.
#   PX_THROTTLE=seconds of pause per frame (default 1.0; 0 = full speed), PX_THREADS=CPU threads (default 4)
THROTTLE = float(os.environ.get("PX_THROTTLE", "1.0"))
scene.render.threads_mode = "FIXED"
scene.render.threads = int(os.environ.get("PX_THREADS", "4"))
try:
    os.nice(10)
except OSError:
    pass
# punchy also makes textured paint shiny and metallic (for vehicles); the uniform stays cloth
for m in body.data.materials:
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Metallic"].default_value = 0.0
        b.inputs["Roughness"].default_value = 0.6
        # Textured bodies: the same punch as the painted ones (more saturation and contrast, a little brighter),
        # so model textures don't render dull under the game lights
        if TEXTURED and b.inputs["Base Color"].is_linked:
            nt = m.node_tree
            src = b.inputs["Base Color"].links[0].from_socket
            hsv = nt.nodes.new("ShaderNodeHueSaturation")
            hsv.inputs["Saturation"].default_value = 1.45
            hsv.inputs["Value"].default_value = 1.25
            bc = nt.nodes.new("ShaderNodeBrightContrast")
            bc.inputs["Contrast"].default_value = 0.18
            nt.links.new(src, hsv.inputs["Color"])
            nt.links.new(hsv.outputs["Color"], bc.inputs["Color"])
            nt.links.new(bc.outputs["Color"], b.inputs["Base Color"])
action = arm.animation_data.action
first, last = int(action.frame_range[0]), int(action.frame_range[1])
if FRAMES.startswith("auto:"):  # N frames of a loop (the last frame equals the first, so it is left out)
    n = int(FRAMES[5:])
    frames = [first + round(i * (last - first) / n) for i in range(n)]
elif FRAMES.startswith("span:"):  # N frames from the first to the last frame inclusive (one-shot moves)
    n = int(FRAMES[5:])
    frames = [first + round(i * (last - first) / max(1, n - 1)) for i in range(n)]
else:
    frames = [int(f) for f in FRAMES.split(",")]

# Options (environment):
#   PX_INPLACE=1    cancel the hips' horizontal travel (animations downloaded without "In Place", deaths)
#   PX_SHOTS=0,1,.. per output frame: 1 = a shot (recoil kick through the shoulders + muzzle flash)
INPLACE = os.environ.get("PX_INPLACE") == "1"
SHOTS = [int(x) for x in os.environ.get("PX_SHOTS", "").split(",") if x]
hips = arm.pose.bones["mixamorig:Hips"]
scene.frame_set(first)
bpy.context.view_layer.update()
hips_start = hips.head.copy()  # armature space

flash_mat = bpy.data.materials.new("Flash")
flash_mat.use_nodes = True
fnt = flash_mat.node_tree
fnt.nodes.clear()
emit = fnt.nodes.new("ShaderNodeEmission")
emit.inputs["Color"].default_value = (1.0, 0.55, 0.12, 1)
emit.inputs["Strength"].default_value = 14
fout = fnt.nodes.new("ShaderNodeOutputMaterial")
fnt.links.new(emit.outputs["Emission"], fout.inputs["Surface"])
bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.05, location=(0, 0, 0))
bpy.context.object.scale = (1, 1, 2.2)  # stretched along the barrel
flash = bpy.context.object
flash.data.materials.append(flash_mat)
flash.visible_shadow = False
flash.hide_render = True


def kick(strength):
    """Recoil: shoulders and head snap back a little."""
    from mathutils import Quaternion
    for name, angle in (("mixamorig:Spine2", -0.07), ("mixamorig:RightShoulder", -0.10), ("mixamorig:Neck", -0.05)):
        pb = arm.pose.bones.get(name)
        if pb:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = pb.rotation_quaternion @ Quaternion((1, 0, 0), angle * strength)


# Sidebar cameo (PX_CAMEO=<out.png>): the first frame only, the soldier turned to show his front-left side, seen
# from a low three-quarter camera (PX_CAMEO_ELEV degrees, default 18) and framed tightly at 960x640, like the
# vehicles' artsrc/units/meshes/render_cameo.py. artsrc/px-cameos/generate.py stages it on the tile.
if os.environ.get("PX_CAMEO"):
    import numpy as np
    W, H = 960, 640
    elev = math.radians(float(os.environ.get("PX_CAMEO_ELEV", "18")))
    scene.render.resolution_x, scene.render.resolution_y = W, H
    scene.frame_set(frames[0])
    root.location = (0, 0, 0)
    # PX_CAMEO_FACING (of 32, 16 = straight at the camera): 15 shows the front like the infantry concept art
    render_sprites.face(root, int(os.environ.get("PX_CAMEO_FACING", "12")), 32)
    if os.environ.get("PX_CAMEO_REST"):
        # standing straight with relaxed arms (the body's A-pose), like the infantry concept art
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    place_gun()
    if os.environ.get("PX_CAMEO_REST") and gun is not None:
        # relaxed hands can't aim: the weapon hangs from the right hand, barrel down and slightly forward
        rh = arm.matrix_world @ arm.pose.bones["mixamorig:RightHand"].head
        gun.matrix_world = Matrix.Translation(rh) @ root.matrix_world.to_3x3().to_4x4() @ Matrix.Rotation(math.radians(-100), 4, "X")
        bpy.context.view_layer.update()
    cam = scene.camera
    cam.location = Vector((0, -50 * math.cos(elev), 50 * math.sin(elev)))
    cam.rotation_euler = (math.radians(90) - elev, 0, 0)
    bpy.context.view_layer.update()
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
    upv = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in scene.objects:
        if o.type != "MESH" or o.hide_render or o is flash:
            continue
        me = o.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        pts.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
        o.evaluated_get(dg).to_mesh_clear()
    pts = np.concatenate(pts)
    u, v = pts @ np.array(right), pts @ np.array(upv)
    cam.data.ortho_scale = max(u.max() - u.min(), (v.max() - v.min()) * W / H) * 1.08
    loc = Vector(cam.location)
    cam.location = loc + right * ((u.min() + u.max()) / 2 - loc.dot(right)) + upv * ((v.min() + v.max()) / 2 - loc.dot(upv))
    render_sprites.render_to(os.environ["PX_CAMEO"])
    print("cameo", os.environ["PX_CAMEO"])
    sys.exit(0)

for i, f in enumerate(frames):
    shot = SHOTS[i] if i < len(SHOTS) else 0
    for facing in range(FACINGS):
        scene.frame_set(f)
        root.location = (0, 0, 0)
        render_sprites.face(root, facing, FACINGS)
        if FACINGS == 1 and os.environ.get("PX_DEG"):  # one fixed direction (deaths play facing-less)
            root.rotation_euler = (0, 0, math.radians(float(os.environ["PX_DEG"])))
        if shot:
            kick(1.0)
        bpy.context.view_layer.update()
        if INPLACE:
            now = arm.matrix_world @ hips.head
            start_w = arm.matrix_world @ hips_start
            root.location = (start_w.x - now.x, start_w.y - now.y, 0)
            bpy.context.view_layer.update()
        place_gun()
        if shot and gun is not None:
            flash.hide_render = False
            m = gun.matrix_world
            muzzle = MUZZLE.get(UID, (0, 0.68, 0.04))
            flash.matrix_world = m @ Matrix.Translation(muzzle) @ Matrix.Rotation(-1.5708, 4, "X")
        else:
            flash.hide_render = True
        render_sprites.render_to(os.path.join(OUT, f"f{facing:02d}-{i:02d}.png"))
        if THROTTLE > 0:
            time.sleep(THROTTLE)
print("rendered", len(frames), "frames x", FACINGS, "facings")
