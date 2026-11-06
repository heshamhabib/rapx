"""
HD walls, mines and animated props rendered in Blender (RedAlert Project X, IDEA-30 phase 4).

  blender -b -P artsrc/env/props3d/render_props.py -- <job> <out dir> [samples]

Jobs (models: Sketchfab downloads in assets/inbox/phase34/, credited in mods/rapx/CREDITS):
  brik      concrete wall (procedural): the 16 neighbour joins x intact / scratched / damaged = wall-NN.png
  sbag      sandbag wall from the bags of "Sandbag Wall" (ahmagh2e): 16 joins
  fenc      wire fence from the "Modular Chain Link Fence Set" (FrodoUndead): 16 joins
  mines     minv = "Soviet AT Land Mine" (GameDevNick), minp = "Claymore Mine" (Tnkii)
  hosp      "Building of the polyclinic in russia" (narcozisne1) with a red cross on the roof
  windmill  "Dutch windmill" (lessers91): 8 frames of the sails turning
  v19       "Oil Pumpjack - Animated" (felhamard): 14 frames of one nodding cycle

Joins (WithWallSpriteBody): frame = sum of the neighbours, north 1, east 2, south 4, west 8. Every frame is a
post at the cell centre plus a half section towards each neighbour. Same camera and light as the HD units, 3x
density; the cell centre (ground) is the frame centre. make_props.py packs the frames.
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "units"))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "units", "tank"))
os.environ.setdefault("PX_LIGHT", "hd")
MODELS = os.path.join(ROOT, "assets", "inbox", "phase34")

argv = sys.argv[sys.argv.index("--") + 1:]
JOB, OUT = argv[0], argv[1]
SAMPLES = int(argv[2]) if len(argv) > 2 else 64
UNIT_PX = 4.0          # world pixels per Blender unit
CELL = 24 / UNIT_PX    # one map cell in Blender units

import build_tank as bt  # noqa: E402

bt.reset_scene()
import render_sprites  # noqa: E402

os.makedirs(OUT, exist_ok=True)


def import_model(name):
    """Imports a downloaded glTF under an empty; returns (root, meshes)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(MODELS, name, "scene.gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None:
            o.parent = root
    return root, [o for o in new if o.type == "MESH"]


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def bake(obj):
    """A standalone copy of one imported mesh with its world transform applied (for instancing)."""
    me = obj.data.copy()
    me.transform(obj.matrix_world)
    c = bpy.data.objects.new(obj.name + "_baked", me)
    return c


def setup(frame, catcher=1.0):
    scene = render_sprites.setup(frame=frame, samples=SAMPLES, unit_px=UNIT_PX)
    for o in scene.objects:
        if o.type == "MESH" and o.is_shadow_catcher:
            o.scale = (catcher, catcher, 1)
    return scene


def render(name):
    render_sprites.render_to(os.path.join(OUT, name + ".png"))


def clear(objs):
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)


ARMS = {1: Vector((0, 1, 0)), 2: Vector((1, 0, 0)), 4: Vector((0, -1, 0)), 8: Vector((-1, 0, 0))}


# --- Concrete wall ----------------------------------------------------------------------------------------------

def concrete_wall(state):
    """state 0 intact, 1 scratched, 2 damaged (broken tops, chunks knocked out)."""
    con = bt.make_paint("WallConcrete", (0.2, 0.195, 0.185), roughness=0.9, wear_color=(0.17, 0.165, 0.16))
    dark = bt.make_paint("WallJoint", (0.2, 0.19, 0.18), roughness=0.9)
    rnd = random.Random(5)
    T, H = 2.1, 3.3      # thickness, height (8.4 x 13 world px)

    def post():
        objs = [bt.box("Post", (0, 0, (H + 0.5) / 2), (2.7, 2.7, H + 0.5), con, bevel_w=0.08),
                bt.box("PostCap", (0, 0, H + 0.55), (3.0, 3.0, 0.2), dark, bevel_w=0.04)]
        return objs

    def arm(d):
        objs = []
        n = 2                                      # two blocks per half cell
        for k in range(n):
            a = 1.2 + (CELL / 2 - 1.2) * (k + 0.5) / n
            ln = (CELL / 2 - 1.2) / n - 0.08
            h = H
            if state == 2 and rnd.random() < 0.7:
                h = H * rnd.uniform(0.45, 0.8)
            c = d * a
            size = (ln, T, h) if d.x else (T, ln, h)
            objs.append(bt.box("Block", (c.x, c.y, h / 2), size, con, bevel_w=0.07))
            if state == 2 and h < H:
                for _ in range(2):
                    r = bt.box("Rubble", (c.x + rnd.uniform(-1, 1), c.y + rnd.uniform(-1, 1) - 1.4, 0.2),
                               (0.5, 0.4, 0.35), con, bevel_w=0.05)
                    r.rotation_euler = (0, 0, rnd.uniform(0, 3))
                    objs.append(r)
        return objs

    return post, arm


# --- Sandbags ---------------------------------------------------------------------------------------------------

def sandbags():
    _, meshes = import_model("sandbag-wall")
    src = max(meshes, key=lambda o: len(o.data.vertices))
    bag = bake(src)
    clear(meshes)
    bpy.context.scene.collection.objects.link(bag)
    mn, mx = bounds([bag])
    size = mx - mn
    centre = (mn + mx) / 2
    bag.data.transform(Matrix.Translation(-centre))
    # bag: 1.7 x 0.95 x 0.75 units (7 x 4 x 3 px)
    s = Vector((1.7 / size.x, 0.95 / size.y, 0.75 / size.z))
    bag.data.transform(Matrix.Diagonal((*s, 1)))
    bag.hide_render = True
    rnd = random.Random(9)

    def place(x, y, z, yaw):
        o = bpy.data.objects.new("Bag", bag.data)
        bpy.context.scene.collection.objects.link(o)
        o.location = (x, y, z)
        o.rotation_euler = (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), yaw + rnd.uniform(-0.12, 0.12))
        return o

    def post():
        objs = []
        for row in range(3):
            for k in range(3):
                a = k * 2 * math.pi / 3 + row * 0.9
                objs.append(place(math.cos(a) * 0.6, math.sin(a) * 0.6, 0.37 + row * 0.66, a + math.pi / 2))
        return objs

    def arm(d):
        objs = []
        yaw = 0 if d.x else math.pi / 2
        for row in range(3):
            off = 0.75 if row % 2 else 0.0
            for k in range(2):
                a = 0.9 + off + k * 1.45
                if a > CELL / 2 + 0.3:
                    continue
                c = d * a
                objs.append(place(c.x, c.y, 0.37 + row * 0.66, yaw))
        return objs

    return post, arm


# --- Wire fence -------------------------------------------------------------------------------------------------

def fence():
    _, meshes = import_model("chainlink-fence")
    posts = [o for o in meshes if len(o.data.vertices) == 235]
    panels = [o for o in meshes if len(o.data.vertices) == 422]
    post_src, panel_src = bake(posts[0]), bake(panels[0])
    clear(meshes)
    for o in (post_src, panel_src):
        bpy.context.scene.collection.objects.link(o)
        mn, mx = bounds([o])
        o.data.transform(Matrix.Translation(Vector((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z))))
        o.hide_render = True
    for m in panel_src.data.materials:            # chain link: denser and darker, or it vanishes at game size
        if not m or not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        alpha = bsdf.inputs["Alpha"]
        if alpha.is_linked:
            src = alpha.links[0].from_socket
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            mul.use_clamp = True
            mul.inputs[1].default_value = 5.0
            nt.links.new(src, mul.inputs[0])
            nt.links.new(mul.outputs[0], alpha)
        col = bsdf.inputs["Base Color"]
        if col.is_linked:
            src = col.links[0].from_socket
            dk = nt.nodes.new("ShaderNodeMix")
            dk.data_type = "RGBA"
            dk.blend_type = "MULTIPLY"
            dk.inputs["Factor"].default_value = 1.0
            dk.inputs["B"].default_value = (0.55, 0.55, 0.55, 1)
            nt.links.new(src, dk.inputs["A"])
            nt.links.new(dk.outputs["Result"], col)
    mn, mx = bounds([panel_src])
    k = 3.2 / (mx.z - mn.z)                 # 12.8 px tall
    plen = (mx.y - mn.y) * k

    def post():
        o = bpy.data.objects.new("FencePost", post_src.data)
        bpy.context.scene.collection.objects.link(o)
        o.scale = (k * 1.8, k * 1.8, k * 1.05)       # thicker posts read better at game size
        return [o]

    def arm(d):
        o = bpy.data.objects.new("FencePanel", panel_src.data)
        bpy.context.scene.collection.objects.link(o)
        o.scale = (k, (CELL / 2) / plen * k, k)
        o.location = d * (CELL / 4)
        o.rotation_euler = (0, 0, 0 if d.y else math.pi / 2)
        return [o]

    return post, arm


def walls(builder, states, frame=168):
    setup(frame)
    for state in range(states):
        post, arm = builder(state) if builder is concrete_wall else builder()
        for mask in range(16):
            objs = post()
            for bit, d in ARMS.items():
                if mask & bit:
                    objs += arm(d)
            render(f"wall-{state * 16 + mask:02d}")
            clear(objs)
        if builder is not concrete_wall:
            break


# --- Single models ----------------------------------------------------------------------------------------------

def fit(name, size_px, axis="max", yaw=0.0, lift=0.0):
    """Imports a model, scales its largest (or "z") extent to size_px world pixels, centres it on the origin with its
    base on the ground."""
    root, meshes = import_model(name)
    mn, mx = bounds(meshes)
    ext = (mx - mn)
    span = ext.z if axis == "z" else max(ext.x, ext.y)
    s = size_px / UNIT_PX / span
    root.scale = (s, s, s)
    root.location = (-(mn.x + mx.x) / 2 * s, -(mn.y + mx.y) / 2 * s, -mn.z * s + lift)
    pivot = bpy.data.objects.new(name + "_yaw", None)
    bpy.context.scene.collection.objects.link(pivot)
    root.parent = pivot
    pivot.rotation_euler = (0, 0, math.radians(yaw))
    return pivot, root, meshes, s


def mines():
    setup(96)
    pivot, root, meshes, s = fit("at-mine", 7.5, lift=-0.35)      # half buried
    render("minv")
    clear(meshes + [root, pivot])
    pivot, root, meshes, s = fit("claymore", 5.5, yaw=-15)
    render("minp")


def hospital():
    setup(300, catcher=3)
    root, meshes = import_model("polyclinic")
    scan = meshes[0]
    # the scan includes the ground round the building: drop every face near its lowest level
    me = scan.data
    bm = bmesh.new()
    bm.from_mesh(me)
    wz = [(scan.matrix_world @ v.co).z for v in bm.verts]
    floor = min(wz) + 0.55
    dead = [f for f in bm.faces if max((scan.matrix_world @ v.co).z for v in f.verts) < floor]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(me)
    bm.free()
    me.update()
    bpy.context.view_layer.update()
    ws = [scan.matrix_world @ v.co for v in me.vertices]
    mn = Vector((min(p.x for p in ws), min(p.y for p in ws), min(p.z for p in ws)))
    mx = Vector((max(p.x for p in ws), max(p.y for p in ws), max(p.z for p in ws)))
    s = 15.5 / max(mx.x - mn.x, mx.y - mn.y)            # 62 px long: a 2x2 building grown like the HD ones
    root.scale = (s, s, s)
    root.location = (-(mn.x + mx.x) / 2 * s, -(mn.y + mx.y) / 2 * s, -floor * s)
    pivot = bpy.data.objects.new("HospPivot", None)
    bpy.context.scene.collection.objects.link(pivot)
    root.parent = pivot
    pivot.rotation_euler = (0, 0, math.radians(8))
    # red cross on a white roof panel so it reads as a hospital from above
    top = (mx.z - floor) * s
    white = bt.make_simple("CrossWhite", (0.92, 0.92, 0.9), roughness=0.5)
    red = bt.make_simple("CrossRed", (0.75, 0.03, 0.03), roughness=0.45)
    c = min(mx.x - mn.x, mx.y - mn.y) * s * 0.32
    bt.box("RoofPanel", (0, 0, top + 0.05), (c, c, 0.1), white, pivot, bevel_w=0)
    bt.box("CrossA", (0, 0, top + 0.12), (c * 0.72, c * 0.22, 0.06), red, pivot, bevel_w=0)
    bt.box("CrossB", (0, 0, top + 0.12), (c * 0.22, c * 0.72, 0.06), red, pivot, bevel_w=0)
    render("hosp")


def windmill():
    setup(240, catcher=2)
    root, meshes = import_model("dutch-windmill")
    mn, mx = bounds(meshes)
    s = 11.0 / (mx.z - mn.z)                             # 44 px tall
    sails = max(meshes, key=lambda o: (bounds([o])[1].z - bounds([o])[0].z))
    smn, smx = bounds([sails])
    hub = (smn + smx) / 2
    hub.x = smx.x
    # sails turn about a horizontal axis along +X through their hub
    pivot_sails = bpy.data.objects.new("SailHub", None)
    bpy.context.scene.collection.objects.link(pivot_sails)
    pivot_sails.parent = root
    pivot_sails.location = hub
    bpy.context.view_layer.update()
    world = sails.matrix_world.copy()
    sails.parent = pivot_sails
    sails.matrix_world = world
    root.scale = (s, s, s)
    root.location = (-(mn.x + mx.x) / 2 * s, -(mn.y + mx.y) / 2 * s, -mn.z * s)
    yaw = bpy.data.objects.new("MillYaw", None)
    bpy.context.scene.collection.objects.link(yaw)
    root.parent = yaw
    yaw.rotation_euler = (0, 0, math.radians(-70))      # sails towards the camera, a little from the side
    for i in range(8):
        pivot_sails.rotation_euler = (math.radians(i * 90 / 8), 0, 0)
        render(f"windmill-{i}")


def pumpjack():
    setup(240, catcher=2)
    pivot, root, meshes, s = fit("pumpjack", 34, yaw=-60)
    rust = bt.make_paint("PumpRust", (0.12, 0.05, 0.025), roughness=0.75, wear_color=(0.2, 0.17, 0.14))
    iron = bt.make_paint("PumpIron", (0.12, 0.12, 0.12), roughness=0.6)
    for o in meshes:
        textured = any(m and m.use_nodes and any(n.type == "TEX_IMAGE" and n.image and n.image.has_data
                                                  for n in m.node_tree.nodes) for m in o.data.materials)
        if not textured:
            o.data.materials.clear()
            o.data.materials.append(iron if "Cylinder" in o.name else rust)
    scene = bpy.context.scene
    acts = [a for a in bpy.data.actions]
    start, end = (1, 250)
    if acts:
        start, end = (int(v) for v in acts[0].frame_range)
    for i in range(14):
        scene.frame_set(start + round(i * (end - start) / 14))
        render(f"v19-{i}")


JOBS = {"brik": lambda: walls(concrete_wall, 3), "sbag": lambda: walls(sandbags, 1),
        "fenc": lambda: walls(fence, 1), "mines": mines, "hosp": hospital, "windmill": windmill, "v19": pumpjack}
JOBS[JOB]()
print("rendered", JOB, "to", OUT)
