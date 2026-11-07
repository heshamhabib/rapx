"""
Ironward city buildings: imports the Sketchfab models (tools/download_sketchfab.py --ironward, plus the Longworth
Building from assets/inbox) and turns them into a library of single buildings for build_backdrop.py.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/ironward/prep_buildings.py

Output: build/buildings.blend (one mesh object per building, origin at the middle of its footprint on the ground,
front facing south = -Y), build/buildings.json (size and source of each) and build/buildings-sheet.png (every
building seen through the game's camera, to check scale and facing).

Sets that hold several buildings in one file are split: loose parts are grouped by overlapping footprints, flat
ground plates are dropped first so they do not glue a whole set into one block, and small leftovers (lamps,
benches, rubbish) are dropped. Per-model fixes (scale, which side is the front) are in MODELS.
"""
import glob
import json
import math
import os
import shutil
import sys
import zipfile

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
BUILD = os.path.join(HERE, "build")
SRC = os.path.join(ROOT, "assets", "inbox", "ironward-buildings")
TMP = os.path.join(BUILD, "models")

# key: (zip pattern, scale fix, extra rotation in degrees about Z so the front faces -Y)
MODELS = {
    "longworth": (os.path.join(ROOT, "assets", "inbox", "longworth_building_low_poly_game_ready.zip"), 1.0, 0),
}
for z in sorted(glob.glob(os.path.join(SRC, "*.zip"))):
    MODELS[os.path.basename(z).split("__")[0]] = (z, 1.0, 0)
# Fixes found on the contact sheet (filled in after the first run)
FIX = json.load(open(os.path.join(HERE, "buildings-fix.json"))) if os.path.exists(os.path.join(HERE, "buildings-fix.json")) else {}

MIN_FOOT = 5.0       # metres: smaller groups are props
MIN_HEIGHT = 4.0


def import_model(key, path):
    out = os.path.join(TMP, key)
    if not os.path.isdir(out):
        os.makedirs(out)
        with zipfile.ZipFile(path) as z:
            z.extractall(out)
    gltf = (glob.glob(os.path.join(out, "**", "*.gltf"), recursive=True) + glob.glob(os.path.join(out, "**", "*.glb"), recursive=True))[0]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=gltf)
    return [o for o in bpy.data.objects if o not in before]


def merged_mesh(objs, name):
    """All mesh objects of an import baked into one bmesh in world space (materials kept)."""
    bm = bmesh.new()
    mats = []
    for o in objs:
        if o.type != "MESH":
            continue
        me = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        offset = len(mats)
        mats += [s.material for s in o.material_slots]
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        for f in tmp.faces:
            f.material_index += offset
        m = bpy.data.meshes.new("tmp")
        tmp.to_mesh(m)
        tmp.free()
        bm.from_mesh(m)
        bpy.data.meshes.remove(m)
        o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    return bm, mats


def split_buildings(bm):
    """Groups of faces that make up separate buildings: [(faces)]."""
    bm.faces.ensure_lookup_table()
    # Loose parts
    seen, parts = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, part = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            part.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        parts.append(part)

    def box(part):
        vs = [v.co for f in part for v in f.verts]
        return (min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs),
                max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs))
    boxes = [box(p) for p in parts]
    # Drop ground plates: flat and wide
    keep = [i for i, b in enumerate(boxes) if not (b[5] - b[2] < 0.6 and (b[3] - b[0]) * (b[4] - b[1]) > 40)]
    # Union parts whose boxes touch or nearly touch (walls are often separate thin planes)
    parent = {i: i for i in keep}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a in keep:
        for b in keep:
            if a < b:
                A, B = boxes[a], boxes[b]
                g = 0.15
                if A[0] < B[3] + g and B[0] < A[3] + g and A[1] < B[4] + g and B[1] < A[4] + g and A[2] < B[5] + g and B[2] < A[5] + g:
                    parent[find(a)] = find(b)
    groups = {}
    for i in keep:
        groups.setdefault(find(i), []).append(i)
    out = []
    for idx in groups.values():
        b = [min(boxes[i][k] for i in idx) for k in range(3)] + [max(boxes[i][k] for i in idx) for k in range(3, 6)]
        if b[3] - b[0] < MIN_FOOT or b[4] - b[1] < MIN_FOOT or b[5] - b[2] < MIN_HEIGHT:
            continue
        out.append(([f for i in idx for f in parts[i]], b))
    return out


def stone_material():
    """Dark gothic stone for untextured models (the cathedral)."""
    mat = bpy.data.materials.get("Gothic stone")
    if mat:
        return mat
    mat = bpy.data.materials.new("Gothic stone")
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.20, 0.20, 0.23, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def main():
    os.makedirs(TMP, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lib = bpy.data.collections.new("Buildings")
    bpy.context.scene.collection.children.link(lib)
    info = {}
    for key, (path, scale, rot) in MODELS.items():
        fix = FIX.get(key, {})
        scale = fix.get("scale", scale)
        rot = fix.get("rot", rot)
        objs = import_model(key, path)
        bm, mats = merged_mesh(objs, key)
        for o in objs:
            bpy.data.objects.remove(o, do_unlink=True)
        bm.transform(Matrix.Rotation(math.radians(rot), 4, "Z") @ Matrix.Scale(scale, 4))
        groups = split_buildings(bm)
        skip = set(fix.get("skip", []))
        n = 0
        for k, (faces, b) in enumerate(sorted(groups, key=lambda g: (g[1][0], g[1][1]))):
            name = f"{key}-{k}"
            if name in skip:
                continue
            # Copy the group's faces into their own mesh, origin at the footprint centre on the ground
            sub = bmesh.new()
            vmap = {}
            layer_uv = bm.loops.layers.uv.active
            sub_uv = sub.loops.layers.uv.new("UVMap") if layer_uv else None
            for f in faces:
                vs = []
                for v in f.verts:
                    if v not in vmap:
                        vmap[v] = sub.verts.new(v.co)
                    vs.append(vmap[v])
                try:
                    nf = sub.faces.new(vs)
                except ValueError:
                    continue
                nf.material_index = f.material_index
                nf.smooth = f.smooth
                if layer_uv:
                    for l_src, l_dst in zip(f.loops, nf.loops):
                        l_dst[sub_uv].uv = l_src[layer_uv].uv
            cx, cy, z0 = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2]
            sub.transform(Matrix.Translation((-cx, -cy, -z0)))
            # How much each face points up, before the game's shear (for snow on roofs and ledges)
            up = sub.faces.layers.float.new("upz")
            for f in sub.faces:
                f.normal_update()
                f[up] = max(0.0, f.normal.z)
            me = bpy.data.meshes.new(name)
            sub.to_mesh(me)
            sub.free()
            if fix.get("material") == "stone":
                mats = [stone_material()]
                for poly in me.polygons:
                    poly.material_index = 0
            for m in mats:
                if m:
                    # Game models often hide back faces; the oblique camera sees round them, so draw both sides
                    m.use_backface_culling = False
                    if hasattr(m, "use_backface_culling_shadow"):
                        m.use_backface_culling_shadow = False
                me.materials.append(m)
            ob = bpy.data.objects.new(name, me)
            lib.objects.link(ob)
            info[name] = {"model": key, "w": round(b[3] - b[0], 2), "d": round(b[4] - b[1], 2), "h": round(b[5] - b[2], 2),
                          "tris": sum(len(f.verts) - 2 for f in faces)}
            n += 1
        bm.free()
        print(f"{key}: {n} buildings")
    for o in lib.objects:
        o.hide_render = False
    with open(os.path.join(BUILD, "buildings.json"), "w") as f:
        json.dump(info, f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "buildings.blend"))
    contact_sheet(lib, info)


def contact_sheet(lib, info):
    """Every building through the game's camera (straight down, height leaning north), one render each; the sheet is
    put together outside Blender (its Python has no PIL): build/models/shots.json -> buildings-sheet.png."""
    shear = 1 / math.tan(math.radians(50))
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 8
    sc.render.resolution_x = sc.render.resolution_y = 256
    sc.render.film_transparent = False
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.55, 0.6, 1)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(40), math.radians(20), math.radians(-40))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    sc.collection.objects.link(cam)
    sc.camera = cam
    shots = []
    for o in lib.objects:
        o.hide_render = True
    for o in lib.objects:
        i = info[o.name]
        sheared = bpy.data.objects.new("s", o.data.copy())
        sheared.data.transform(Matrix(((1, 0, 0, 0), (0, 1, shear, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
        sc.collection.objects.link(sheared)
        size = max(i["w"], i["d"] + i["h"] * shear) * 1.1
        cam.data.ortho_scale = size
        cam.location = (0, i["h"] * shear / 2, 500)
        path = os.path.join(TMP, f"shot-{o.name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(sheared, do_unlink=True)
        shots.append((o.name, path))
    with open(os.path.join(TMP, "shots.json"), "w") as f:
        json.dump(shots, f)
    print(f"sheet: {len(shots)} buildings")


main()
