"""
Renders a non-humanoid unit (walkers, drones, the attack dog: the "Other (own approach)" group) from a downloaded,
animated Sketchfab model with the soldiers' camera and lights, into the soldier frame layout (<out>/f<facing>-<n>.png,
packed by pack_soldier.py, sequences by write_sequences.py). The model plays its own clips (skeleton or shape-key
animation); moves it lacks are made procedurally:
  walk     legs of a static model swung in a gait (Strider: parts given by name groups in CFG["legs"])
  lunge    the whole body darts forward and back (the dog's bite)
  fall     the body tips over onto its side and sinks (deaths)
  recoil   a sharp kick back and recovery (firing)

  blender -b -P artsrc/units/soldiers/render_creature.py -- <id> <sequence> <out dir> <facings> <frames> [samples]
frames: auto:N (N frames over the clip, looping), span:N (first to last), or comma-separated frame numbers.
Env: PX_CAMEO=<png> renders the sidebar cameo view instead (one frame, low three-quarter camera).
"""

import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import render_sprites  # noqa: E402

SF = os.path.join(HERE, "sketchfab")

# Per unit: src (glTF under sketchfab/), yaw (degrees, turns the nose to +Y = north), height or length (metres in
# game: the body is scaled to it), frame (px), clips: sequence -> (action name prefix or None, procedural mode or
# None), team: ("hue", lo, hi) turns that paint hue into team green, ("top", z0) a band of the top from z0
# (fraction of the height) up.
CFG = {
    "enfw": {"src": "other.enfw__medium_mech_striker", "yaw": 180, "height": 3.1, "frame": 320,
             "clips": {"idle": ("a4IdlePose", None), "aim": ("a4IdlePose", None), "run": ("a5WalkCycle", None),
                       "shoot": ("a4IdlePose", "recoil"), "die1": ("b2DeathFallDown1", None),
                       "die2": ("b2DeathFallDown2", None)},
             "team": ("hue", 0.52, 0.72)},
    "sdrn": {"src": "other.sdrn__steampunk_spider", "yaw": 180, "length": 1.5, "frame": 192,
             "clips": {"idle": ("Armature|spider_walk_slow", None), "aim": ("Armature|spider_walk_slow", None),
                       "run": ("Armature|spider_walk_fast_1", None), "shoot": ("Armature|spider_attack_1", None),
                       "die1": ("Armature|spider_dead", None), "die2": ("Armature|spider_dead", None)},
             "team": ("top", 0.9), "inplace": True},
    "dog": {"src": "other.dog__doberman_walk_cycle", "yaw": 180, "length": 1.15, "frame": 192,
            "clips": {"idle": (None, None), "aim": (None, None), "run": ("", None), "shoot": (None, "lunge"),
                      "die1": (None, "fall"), "die2": (None, "fall")},
            "team": None, "inplace": True},
    "strd": {"src": "other.strd__quadruped_mech_walker", "yaw": 180, "length": 4.2, "frame": 384,
             "clips": {"idle": (None, None), "aim": (None, None), "run": (None, "walk"), "shoot": (None, "recoil"),
                       "die1": (None, "fall"), "die2": (None, "fall")},
             "team": ("hue", 0.52, 0.72), "legs": "quadrants"},
}

argv = sys.argv[sys.argv.index("--") + 1:]
UID, SEQ, OUT, FACINGS, FRAMES = argv[0], argv[1], argv[2], int(argv[3]), argv[4]
SAMPLES = int(argv[5]) if len(argv) > 5 else 40
C = CFG[UID]
UNIT_PX = 19.0  # world px per metre, as render_soldier.py

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(SF, C["src"], "scene.gltf"))
scene = bpy.context.scene
bpy.context.view_layer.update()

# Root empty: everything top-level hangs under it, so facing turns the whole unit
root = bpy.data.objects.new("UnitRoot", None)
scene.collection.objects.link(root)
tops = [o for o in scene.objects if o.parent is None and o is not root]
for o in tops:
    o.parent = root
meshes = [o for o in scene.objects if o.type == "MESH"]


def world_points():
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        m = np.array(ev.matrix_world)
        pts.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
        ev.to_mesh_clear()
    return np.concatenate(pts)


# Size and ground: measured in the rest / first frame, applied through an inner scale empty
inner = bpy.data.objects.new("UnitScale", None)
scene.collection.objects.link(inner)
inner.parent = root
for o in tops:
    o.parent = inner
inner.rotation_euler = (0, 0, math.radians(C.get("yaw", 0)))
bpy.context.view_layer.update()
pts = world_points()
lo, hi = pts.min(0), pts.max(0)
if "height" in C:
    k = C["height"] / max(hi[2] - lo[2], 1e-6)
else:
    k = C["length"] / max(hi[1] - lo[1], hi[0] - lo[0], 1e-6)
inner.scale = (k, k, k)
bpy.context.view_layer.update()
pts = world_points()
lo, hi = pts.min(0), pts.max(0)
inner.location = (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])
bpy.context.view_layer.update()
HEIGHT = hi[2] - lo[2]

# Team colour in the materials
team = C.get("team")
if team:
    for m in {s.material for o in meshes for s in o.material_slots if s.material}:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        base = bsdf.inputs["Base Color"]
        if base.is_linked:
            src = base.links[0].from_socket
        else:
            rgb = nt.nodes.new("ShaderNodeRGB")
            rgb.outputs[0].default_value = base.default_value
            src = rgb.outputs[0]
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.mode = "HSV"
        nt.links.new(src, sep.inputs[0])
        h, s, v = sep.outputs
        if team[0] == "hue":
            gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = team[1]
            lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = team[2]
            sat = nt.nodes.new("ShaderNodeMath"); sat.operation = "GREATER_THAN"; sat.inputs[1].default_value = 0.2
            nt.links.new(h, gt.inputs[0]); nt.links.new(h, lt.inputs[0]); nt.links.new(s, sat.inputs[0])
            m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
            nt.links.new(gt.outputs[0], m1.inputs[0]); nt.links.new(lt.outputs[0], m1.inputs[1])
            mask = nt.nodes.new("ShaderNodeMath"); mask.operation = "MULTIPLY"
            nt.links.new(m1.outputs[0], mask.inputs[0]); nt.links.new(sat.outputs[0], mask.inputs[1])
            fac = mask.outputs[0]
        else:
            # band of the body from z0 up, in object space of the scaled unit (world z at rest)
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(geo.outputs["Position"], xyz.inputs[0])
            gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"
            gt.inputs[1].default_value = HEIGHT * team[1]
            nt.links.new(xyz.outputs["Z"], gt.inputs[0])
            fac = gt.outputs[0]
        comb = nt.nodes.new("ShaderNodeCombineColor"); comb.mode = "HSV"
        comb.inputs[0].default_value = 1 / 3
        comb.inputs[1].default_value = 0.85
        vv = nt.nodes.new("ShaderNodeMath"); vv.operation = "MULTIPLY_ADD"
        vv.inputs[1].default_value = 0.8; vv.inputs[2].default_value = 0.15
        nt.links.new(v, vv.inputs[0]); nt.links.new(vv.outputs[0], comb.inputs[2])
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        sk = {x.identifier: x for x in mix.inputs}
        nt.links.new(fac, sk["Factor_Float"]); nt.links.new(src, sk["A_Color"]); nt.links.new(comb.outputs[0], sk["B_Color"])
        nt.links.new(next(o for o in mix.outputs if o.identifier == "Result_Color"), base)

# Animation: pick the action, frame range
anim_target = None
clip, mode = C["clips"].get(SEQ, (None, None))
first = last = scene.frame_current
if clip is not None:
    acts = [a for a in bpy.data.actions if a.name.startswith(clip)] if clip else list(bpy.data.actions)
    if acts:
        act = sorted(acts, key=lambda a: len(a.name))[0]
        for o in scene.objects:
            ad = o.animation_data
            if o.type == "ARMATURE" or (ad and ad.action):
                o.animation_data_create()
                o.animation_data.action = act
                for tr in list(o.animation_data.nla_tracks):
                    o.animation_data.nla_tracks.remove(tr)
            if o.type == "MESH" and o.data.shape_keys and o.data.shape_keys.animation_data:
                anim_target = o.data.shape_keys
        first, last = int(act.frame_range[0]), int(act.frame_range[1])
        print("clip", act.name, first, last)
else:
    # still pose: the first frame of whatever is loaded, no motion
    for o in scene.objects:
        if o.animation_data:
            o.animation_data.action = None if o.type == "ARMATURE" and SEQ not in ("idle", "aim") else o.animation_data.action

if FRAMES.startswith("auto:"):
    n = int(FRAMES[5:])
    frames = [first + round(i * (last - first) / n) for i in range(n)]
elif FRAMES.startswith("span:"):
    n = int(FRAMES[5:])
    frames = [first + round(i * (last - first) / max(1, n - 1)) for i in range(n)]
else:
    frames = [int(f) for f in FRAMES.split(",")]
NF = len(frames)

os.environ["PX_LIGHT"] = "punchy"
if os.environ.get("PX_CAMEO"):
    os.environ["PX_NO_GROUND"] = "1"
scene = render_sprites.setup(C["frame"], SAMPLES, 1, UNIT_PX)
scene.render.threads_mode = "FIXED"
scene.render.threads = int(os.environ.get("PX_THREADS", "4"))
THROTTLE = float(os.environ.get("PX_THROTTLE", "1.0"))
try:
    os.nice(10)
except OSError:
    pass


def procedural(i):
    """Offset / rotation of the inner body for procedural moves, step i of NF."""
    t = i / max(1, NF - 1)
    loc, rot = Vector((0, 0, 0)), (0.0, 0.0, 0.0)
    if mode == "lunge":
        d = math.sin(t * math.pi)
        loc = Vector((0, 0.35 * d * HEIGHT, 0.08 * d * HEIGHT))
        rot = (math.radians(-12 * d), 0, 0)
    elif mode == "fall":
        e = min(1, t * 1.4) ** 2
        rot = (0, math.radians(88 * e), 0)
        loc = Vector((0.25 * HEIGHT * e, 0, -0.05 * HEIGHT * e))
    elif mode == "recoil":
        d = math.exp(-((t * NF) % 3) * 1.3) if i % 3 == 0 or True else 0
        d = [1.0, 0.45, 0.15][i % 3]
        loc = Vector((0, -0.04 * HEIGHT * d, 0))
        rot = (math.radians(3 * d), 0, 0)
    elif mode == "walk":
        b = math.sin(t * 2 * math.pi)
        loc = Vector((0, 0, 0.02 * HEIGHT * abs(b)))
        rot = (0, math.radians(1.5 * b), 0)
    return loc, rot


base_loc = inner.location.copy()
base_rot = inner.rotation_euler.copy()

# Procedural gait for a static walker: every mesh well outside the body belongs to the leg of its quadrant; a leg
# swings about its hip (vertical axis) and lifts its foot while swinging, diagonal pairs in step
LEGS = []
if C.get("legs") == "quadrants" and mode == "walk":
    bpy.context.view_layer.update()
    rinv = root.matrix_world.inverted()
    body_w = 0.0
    cents = {}
    for o in meshes:
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        c = sum(bb, Vector()) / 8
        cents[o] = (rinv @ c)
    xs = np.array([abs(c.x) for c in cents.values()])
    body_w = np.percentile(xs, 30) + 0.15 * HEIGHT
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts = [o for o, c in cents.items() if abs(c.x) > body_w and np.sign(c.x) == sx and np.sign(c.y) == sy]
            if not parts:
                continue
            pc = [cents[o] for o in parts]
            near = min(pc, key=lambda c: abs(c.x))
            hip = Vector((sx * body_w * 0.8, near.y, max(c.z for c in pc)))
            foot = min(pc, key=lambda c: c.z)
            out = Vector((foot.x - hip.x, foot.y - hip.y, 0)).normalized()
            LEGS.append({"parts": parts, "rest": {o: rinv @ o.matrix_world for o in parts}, "hip": hip,
                         "lift_axis": out.cross(Vector((0, 0, 1))), "phase": 0.0 if sx * sy > 0 else 0.5})
    print("legs", [len(l["parts"]) for l in LEGS])


def pose_legs(t):
    for leg in LEGS:
        p = 2 * math.pi * (t + leg["phase"])
        swing = math.radians(14) * math.sin(p)
        lift = math.radians(9) * max(0.0, math.cos(p))
        hip = leg["hip"]
        m = Matrix.Translation(hip) @ Matrix.Rotation(swing, 4, "Z") @ Matrix.Rotation(lift, 4, leg["lift_axis"]) \
            @ Matrix.Translation(-hip)
        for o in leg["parts"]:
            o.matrix_world = root.matrix_world @ m @ leg["rest"][o]


def pose(i, f):
    scene.frame_set(f)
    loc, rot = procedural(i)
    inner.location = base_loc + loc
    if C.get("inplace") and mode is None:
        # clips that walk forward (root motion baked into the mesh): keep the body centred on the cell
        inner.rotation_euler = base_rot
        bpy.context.view_layer.update()
        p = world_points() @ np.array(root.matrix_world.inverted())[:3, :3].T
        inner.location = inner.location - Vector(((p[:, 0].min() + p[:, 0].max()) / 2, (p[:, 1].min() + p[:, 1].max()) / 2, 0))
    inner.rotation_euler = (base_rot[0] + rot[0], base_rot[1] + rot[1], base_rot[2] + rot[2])
    if LEGS:
        bpy.context.view_layer.update()
        pose_legs(i / NF)


if os.environ.get("PX_CAMEO"):
    W, H = 960, 640
    elev = math.radians(float(os.environ.get("PX_CAMEO_ELEV", "22")))
    scene.render.resolution_x, scene.render.resolution_y = W, H
    pose(0, frames[0])
    render_sprites.face(root, 12, 32)
    cam = scene.camera
    cam.location = Vector((0, -50 * math.cos(elev), 50 * math.sin(elev)))
    cam.rotation_euler = (math.radians(90) - elev, 0, 0)
    bpy.context.view_layer.update()
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
    upv = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    p = world_points()
    u, v = p @ np.array(right), p @ np.array(upv)
    cam.data.ortho_scale = max(u.max() - u.min(), (v.max() - v.min()) * W / H) * 1.08
    loc = Vector(cam.location)
    cam.location = loc + right * ((u.min() + u.max()) / 2 - loc.dot(right)) + upv * ((v.min() + v.max()) / 2 - loc.dot(upv))
    render_sprites.render_to(os.environ["PX_CAMEO"])
    print("cameo", os.environ["PX_CAMEO"])
    sys.exit(0)

for i, f in enumerate(frames):
    for facing in range(FACINGS):
        render_sprites.face(root, facing, FACINGS)
        if FACINGS == 1 and os.environ.get("PX_DEG"):
            root.rotation_euler = (0, 0, math.radians(float(os.environ["PX_DEG"])))
        bpy.context.view_layer.update()
        pose(i, f)
        bpy.context.view_layer.update()
        render_sprites.render_to(os.path.join(OUT, f"f{facing:02d}-{i:02d}.png"))
        if THROTTLE > 0:
            time.sleep(THROTTLE)
print("rendered", NF, "frames x", FACINGS, "facings")
