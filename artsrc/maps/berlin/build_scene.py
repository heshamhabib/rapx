"""
Builds the Berlin painted-map pilot scene in Blender (IDEA-28) and renders a preview.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/berlin/build_scene.py -- \
      [--width 2560] [--engine eevee|cycles] [--samples 32] [--out build/preview.png] [--crop x0,y0,x1,y1]

Reads berlin_osm.json (extract_osm.py) and build/mask_*.png + build/trees.json (prepare_layers.py).
Writes build/berlin.blend and the render.

Projection: the game's ground is square, and heights lean "up" the screen. The scene is built with that oblique
projection baked in: every vertex at height z is moved north by z * SHEAR, and the camera looks straight down. The
ground then lines up with the map cells, and the south faces of buildings show, like the game's sprites.
Light comes from the top-left (north-west), like the rest of the game's art.
"""
import argparse
import glob
import json
import math
import os
import random
import sys
import time

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
TEX = os.path.normpath(os.path.join(HERE, "..", "..", "textures"))
ELEVATION = 50.0                                  # camera angle of the game's art (render_sprites.py)
SHEAR = 1 / math.tan(math.radians(ELEVATION))     # north shift per metre of height
HEIGHT_SCALE = 1.0                                # building heights (1 = real)

WALLS = [(0.86, 0.80, 0.70), (0.80, 0.76, 0.68), (0.74, 0.72, 0.68), (0.84, 0.74, 0.58), (0.78, 0.68, 0.62),
         (0.70, 0.70, 0.72), (0.88, 0.85, 0.78), (0.66, 0.60, 0.54)]
ROOFS = [(0.30, 0.30, 0.32), (0.38, 0.37, 0.36), (0.25, 0.26, 0.28), (0.45, 0.43, 0.40), (0.55, 0.30, 0.22),
         (0.50, 0.28, 0.20)]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=2560)
    ap.add_argument("--engine", default="eevee")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--out", default=os.path.join(BUILD, "preview.png"))
    ap.add_argument("--crop", help="render only this part, in metres: x0,y0,x1,y1")
    return ap.parse_args(argv)


def sheared(x, y, z):
    return Vector((x, y + z * SHEAR, z))


# ---------------------------------------------------------------------------------------------- materials

def tex_path(name, kind="Color"):
    hits = sorted(glob.glob(os.path.join(TEX, name, f"*_{kind}.jpg")))
    return hits[0] if hits else None


def image_node(nt, path, non_color=False):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    return n


def tiled_texture(nt, coord, name, repeat_m, kind="Color"):
    """Texture `name` tiled every `repeat_m` metres in object space."""
    path = tex_path(name, kind)
    m = nt.nodes.new("ShaderNodeMapping")
    m.inputs["Scale"].default_value = (1 / repeat_m, 1 / repeat_m, 1)
    nt.links.new(coord.outputs["Object"], m.inputs["Vector"])
    t = image_node(nt, path, non_color=(kind != "Color"))
    nt.links.new(m.outputs["Vector"], t.inputs["Vector"])
    return t


def mix(nt, a, b, fac):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    nt.links.new(fac, n.inputs["Factor"])
    nt.links.new(a, n.inputs[6])
    nt.links.new(b, n.inputs[7])
    return n.outputs[2]


def mixf(nt, a, b, fac):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "FLOAT"
    nt.links.new(fac, n.inputs["Factor"])
    if isinstance(a, (int, float)):
        n.inputs[2].default_value = a
    else:
        nt.links.new(a, n.inputs[2])
    if isinstance(b, (int, float)):
        n.inputs[3].default_value = b
    else:
        nt.links.new(b, n.inputs[3])
    return n.outputs[0]


def tint(nt, color_out, rgb, strength=1.0):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = "MULTIPLY"
    n.inputs["Factor"].default_value = strength
    nt.links.new(color_out, n.inputs[6])
    n.inputs[7].default_value = (*rgb, 1)
    return n.outputs[2]


def ground_material(W, H):
    mat = bpy.data.materials.new("Ground")
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    coord = nt.nodes.new("ShaderNodeTexCoord")

    # Masks come packed 4 per RGBA image (prepare_layers.py): Metal allows only 16 textures per material
    packed = {}
    for img, layers in (("a", ("green", "forest", "paved", "minor")), ("b", ("rail", "road", "embankment", "water"))):
        t = image_node(nt, os.path.join(BUILD, f"masks_{img}.png"), non_color=True)
        t.image.alpha_mode = "CHANNEL_PACKED"
        t.interpolation = "Cubic"
        nt.links.new(coord.outputs["UV"], t.inputs["Vector"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], sep.inputs[0])
        for k, layer in enumerate(layers[:3]):
            packed[layer] = sep.outputs[k]
        packed[layers[3]] = t.outputs["Alpha"]

    def mask(name):
        return packed[name]

    paving = tint(nt, tiled_texture(nt, coord, "PavingStones070", 3.0).outputs[0], (0.82, 0.80, 0.76))
    grass = tint(nt, tiled_texture(nt, coord, "Grass004", 5.0).outputs[0], (0.85, 0.95, 0.75))
    forest = tint(nt, tiled_texture(nt, coord, "Grass005", 6.0).outputs[0], (0.45, 0.55, 0.38))
    gravel = tint(nt, tiled_texture(nt, coord, "Ground054", 4.0).outputs[0], (0.85, 0.82, 0.76))
    asphalt = tint(nt, tiled_texture(nt, coord, "Asphalt012", 8.0).outputs[0], (0.75, 0.75, 0.78))
    concrete = tiled_texture(nt, coord, "Concrete034", 4.0).outputs[0]
    ballast = tint(nt, tiled_texture(nt, coord, "Ground054", 2.5).outputs[0], (0.55, 0.50, 0.46))

    col = paving
    col = mix(nt, col, grass, mask("green"))
    col = mix(nt, col, forest, mask("forest"))
    col = mix(nt, col, paving, mask("paved"))
    col = mix(nt, col, gravel, mask("minor"))
    col = mix(nt, col, ballast, mask("rail"))
    col = mix(nt, col, asphalt, mask("road"))
    col = mix(nt, col, concrete, mask("embankment"))

    # Water: deep blue-green, glossy, with a slow noise ripple
    water_m = mask("water")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.08
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    water_col = nt.nodes.new("ShaderNodeMix")
    water_col.data_type = "RGBA"
    nt.links.new(noise.outputs["Fac"], water_col.inputs["Factor"])
    water_col.inputs[6].default_value = (0.05, 0.13, 0.16, 1)
    water_col.inputs[7].default_value = (0.09, 0.20, 0.23, 1)
    col = mix(nt, col, water_col.outputs[2], water_m)
    nt.links.new(col, bsdf.inputs["Base Color"])
    nt.links.new(mixf(nt, 0.85, 0.08, water_m), bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def building_materials():
    walls = bpy.data.materials.new("Walls")
    nt = walls.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    coord = nt.nodes.new("ShaderNodeTexCoord")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "bcol"
    plaster = tiled_texture(nt, coord, "Plaster001", 3.0).outputs[0]
    base = nt.nodes.new("ShaderNodeMix")
    base.data_type = "RGBA"
    base.blend_type = "MULTIPLY"
    base.inputs["Factor"].default_value = 1.0
    nt.links.new(plaster, base.inputs[6])
    nt.links.new(attr.outputs["Color"], base.inputs[7])
    # Windows from the wall UVs (u = metres along the wall, v = height): a grid of dark glass panes above 3 m
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])

    def band(src, period, lo, hi):
        d = nt.nodes.new("ShaderNodeMath")
        d.operation = "DIVIDE"
        d.inputs[1].default_value = period
        nt.links.new(src, d.inputs[0])
        f = nt.nodes.new("ShaderNodeMath")
        f.operation = "FRACT"
        nt.links.new(d.outputs[0], f.inputs[0])
        a = nt.nodes.new("ShaderNodeMath")
        a.operation = "GREATER_THAN"
        a.inputs[1].default_value = lo
        nt.links.new(f.outputs[0], a.inputs[0])
        b = nt.nodes.new("ShaderNodeMath")
        b.operation = "LESS_THAN"
        b.inputs[1].default_value = hi
        nt.links.new(f.outputs[0], b.inputs[0])
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = "MULTIPLY"
        nt.links.new(a.outputs[0], m.inputs[0])
        nt.links.new(b.outputs[0], m.inputs[1])
        return m.outputs[0]

    wu = band(sep.outputs["X"], 3.6, 0.28, 0.72)
    wv = band(sep.outputs["Y"], 3.4, 0.30, 0.78)
    above = nt.nodes.new("ShaderNodeMath")
    above.operation = "GREATER_THAN"
    above.inputs[1].default_value = 3.0
    nt.links.new(sep.outputs["Y"], above.inputs[0])
    w1 = nt.nodes.new("ShaderNodeMath")
    w1.operation = "MULTIPLY"
    nt.links.new(wu, w1.inputs[0])
    nt.links.new(wv, w1.inputs[1])
    win = nt.nodes.new("ShaderNodeMath")
    win.operation = "MULTIPLY"
    nt.links.new(w1.outputs[0], win.inputs[0])
    nt.links.new(above.outputs[0], win.inputs[1])
    glass = nt.nodes.new("ShaderNodeMix")
    glass.data_type = "RGBA"
    nt.links.new(win.outputs[0], glass.inputs["Factor"])
    nt.links.new(base.outputs[2], glass.inputs[6])
    glass.inputs[7].default_value = (0.08, 0.10, 0.12, 1)
    nt.links.new(glass.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(mixf(nt, 0.8, 0.15, win.outputs[0]), bsdf.inputs["Roughness"])

    roof = bpy.data.materials.new("Roofs")
    nt = roof.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    coord = nt.nodes.new("ShaderNodeTexCoord")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "bcol"
    conc = tiled_texture(nt, coord, "Concrete034", 5.0).outputs[0]
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    m.blend_type = "MULTIPLY"
    m.inputs["Factor"].default_value = 1.0
    nt.links.new(conc, m.inputs[6])
    nt.links.new(attr.outputs["Color"], m.inputs[7])
    nt.links.new(m.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    return walls, roof


def simple_material(name, rgb, rough=0.7, metal=0.0, emission=None, transmission=0.0):
    mat = bpy.data.materials.new(name)
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = 2.0
    return mat


# ---------------------------------------------------------------------------------------------- geometry

def ring_area(pts):
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


def clean_ring(pts):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 0.05:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) <= 0.05:
        out.pop()
    return out


def add_prism(bm, uv, col, outer, holes, h, color_wall, color_roof, wall_mat=0, roof_mat=1):
    """Extruded footprint with sheared walls (UV u = metres along the wall, v = height) and a filled roof."""
    rings = []
    o = clean_ring(outer)
    if len(o) < 3:
        return
    if ring_area(o) < 0:
        o.reverse()
    rings.append(o)
    for hole in holes:
        hh = clean_ring(hole)
        if len(hh) >= 3:
            if ring_area(hh) > 0:
                hh.reverse()
            rings.append(hh)
    top_edges = []
    for ring in rings:
        n = len(ring)
        bot = [bm.verts.new(sheared(x, y, 0)) for x, y in ring]
        top = [bm.verts.new(sheared(x, y, h)) for x, y in ring]
        dist = 0.0
        for i in range(n):
            j = (i + 1) % n
            seg = math.dist(ring[i], ring[j])
            try:
                f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
            except ValueError:
                dist += seg
                continue
            f.material_index = wall_mat
            f[col] = color_wall
            for loop, (u, v) in zip(f.loops, ((dist, 0), (dist + seg, 0), (dist + seg, h), (dist, h))):
                loop[uv].uv = (u, v)
            dist += seg
        for i in range(n):
            try:
                top_edges.append(bm.edges.new((top[i], top[(i + 1) % n])))
            except ValueError:
                pass
    res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=top_edges)
    for f in res["geom"]:
        if isinstance(f, bmesh.types.BMFace):
            if f.normal.z < 0:
                f.normal_flip()
            f.material_index = roof_mat
            f[col] = color_roof


def build_buildings(data, walls, roofs):
    rng = random.Random(7)
    lm = data["landmarks"]
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    col = bm.faces.layers.float_color.new("bcol")
    count = 0
    for b in data["buildings"]:
        pts = b["outer"]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        if any(math.hypot(cx - l["x"], cy - l["y"]) < l["clear_radius"] for l in lm.values()):
            continue
        area = abs(ring_area(pts))
        if area < 12 or b.get("kind") in ("roof", "carport", "construction"):
            continue
        h = b["h"] or (8.0 if area < 120 else 18.0 + rng.uniform(-3, 5))
        h = max(3.0, min(h, 120.0)) * HEIGHT_SCALE
        wall = (*rng.choice(WALLS), 1.0)
        roof = (*rng.choice(ROOFS), 1.0)
        add_prism(bm, uv, col, pts, b["holes"], h, wall, roof)
        count += 1
    me = bpy.data.meshes.new("Buildings")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(walls)
    me.materials.append(roofs)
    ob = bpy.data.objects.new("Buildings", me)
    bpy.context.collection.objects.link(ob)
    return count


# ---------------------------------------------------------------------------------------------- landmarks

def box(bm, x0, y0, x1, y1, z0, z1, mat):
    v = [bm.verts.new(sheared(x, y, z)) for z in (z0, z1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for f in faces:
        bm.faces.new([v[i] for i in f]).material_index = mat


def cylinder(bm, cx, cy, r0, r1, z0, z1, mat, seg=20):
    bot = [bm.verts.new(sheared(cx + r0 * math.cos(a), cy + r0 * math.sin(a), z0))
           for a in (2 * math.pi * i / seg for i in range(seg))]
    top = [bm.verts.new(sheared(cx + r1 * math.cos(a), cy + r1 * math.sin(a), z1))
           for a in (2 * math.pi * i / seg for i in range(seg))]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((bot[i], bot[j], top[j], top[i])).material_index = mat
    bm.faces.new(list(reversed(bot))).material_index = mat
    bm.faces.new(top).material_index = mat


def sphere(bm, cx, cy, cz, r, mat, seg=24, rings=12, z_cut=None):
    verts = []
    for i in range(rings + 1):
        phi = math.pi * i / rings
        z = cz + r * math.cos(phi)
        if z_cut is not None:
            z = max(z, z_cut)
        rr = r * math.sin(phi)
        verts.append([bm.verts.new(sheared(cx + rr * math.cos(2 * math.pi * k / seg),
                                           cy + rr * math.sin(2 * math.pi * k / seg), z)) for k in range(seg)])
    for i in range(rings):
        for k in range(seg):
            a, b = verts[i][k], verts[i][(k + 1) % seg]
            c, d = verts[i + 1][(k + 1) % seg], verts[i + 1][k]
            try:
                bm.faces.new((a, d, c, b)).material_index = mat
            except ValueError:
                pass


def build_landmarks(data):
    """Simplified models at real size: Brandenburg Gate, Reichstag, TV Tower, Victory Column."""
    mats = [simple_material("Sandstone", (0.78, 0.70, 0.56), 0.8),          # 0
            simple_material("Stone grey", (0.62, 0.60, 0.56), 0.8),         # 1
            simple_material("Bronze green", (0.20, 0.32, 0.26), 0.45, 0.6), # 2
            simple_material("Gold", (0.95, 0.72, 0.30), 0.25, 1.0),         # 3
            simple_material("Concrete", (0.80, 0.80, 0.80), 0.7),           # 4
            simple_material("Steel ball", (0.70, 0.72, 0.75), 0.25, 0.9),   # 5
            simple_material("Glass dome", (0.75, 0.85, 0.90), 0.05, 0.3, transmission=0.6),  # 6
            simple_material("Antenna red", (0.75, 0.12, 0.10), 0.6)]       # 7
    bm = bmesh.new()
    lm = data["landmarks"]

    # Brandenburg Gate: spans north-south, 65.5 m x 11 m, 6 columns per side, attic and quadriga
    gx, gy = lm["brandenburg_gate"]["x"], lm["brandenburg_gate"]["y"]
    box(bm, gx - 6, gy - 33, gx + 6, gy + 33, 0, 1.5, 0)
    for side in (-1, 1):
        for k in range(6):
            cy = gy - 27.5 + k * 11
            cylinder(bm, gx + side * 4.5, cy, 0.95, 0.85, 1.5, 15, 0, seg=12)
    box(bm, gx - 6, gy - 33, gx + 6, gy + 33, 15, 18, 0)        # entablature
    box(bm, gx - 5, gy - 18, gx + 5, gy + 18, 18, 21, 0)        # attic
    box(bm, gx - 3, gy - 3.5, gx + 3, gy + 3.5, 21, 26.5, 2)     # quadriga
    for side in (-1, 1):                                         # guard houses
        box(bm, gx - 7, gy + side * 42 - 6, gx + 7, gy + side * 42 + 6, 0, 10, 0)

    # Reichstag: 137 x 97 m, 34 m high, corner towers, glass dome
    rx, ry = lm["reichstag"]["x"], lm["reichstag"]["y"]
    box(bm, rx - 48, ry - 68, rx + 48, ry + 68, 0, 30, 1)
    for sx in (-1, 1):                                           # corner towers, 16 x 16 m, set into the corners
        for sy in (-1, 1):
            cx, cy = rx + sx * 42, ry + sy * 62
            box(bm, cx - 8, cy - 8, cx + 8, cy + 8, 0, 38, 1)
    box(bm, rx - 52, ry - 12, rx - 46, ry + 12, 0, 22, 1)       # west portico
    sphere(bm, rx, ry, 30, 20, 6, z_cut=30)

    # TV Tower: shaft, ball, antenna (368 m)
    tx, ty = lm["tv_tower"]["x"], lm["tv_tower"]["y"]
    cylinder(bm, tx, ty, 30, 30, 0, 9, 4, seg=10)               # base pavilion
    cylinder(bm, tx, ty, 16, 8, 0, 200, 4, seg=24)
    sphere(bm, tx, ty, 212, 16, 5)
    cylinder(bm, tx, ty, 3.5, 1.2, 226, 300, 4, seg=12)
    cylinder(bm, tx, ty, 1.2, 0.5, 300, 368, 7, seg=8)

    # Victory Column: round terrace, pedestal, column, golden Victoria
    vx, vy = lm["victory_column"]["x"], lm["victory_column"]["y"]
    cylinder(bm, vx, vy, 22, 22, 0, 2, 1, seg=32)
    box(bm, vx - 10, vy - 10, vx + 10, vy + 10, 2, 9, 1)
    cylinder(bm, vx, vy, 7, 7, 9, 18, 1, seg=24)                # colonnade hall
    cylinder(bm, vx, vy, 3.4, 2.8, 18, 58, 1, seg=20)
    cylinder(bm, vx, vy, 1.6, 0.6, 58, 67, 3, seg=10)           # Victoria

    me = bpy.data.meshes.new("Landmarks")
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new("Landmarks", me)
    bpy.context.collection.objects.link(ob)


# ---------------------------------------------------------------------------------------------- trees

def tree_prototype(name, height, crown, seed):
    rng = random.Random(seed)
    bm = bmesh.new()
    cylinder(bm, 0, 0, 0.35 * crown / 4, 0.25 * crown / 4, 0, height * 0.45, 0, seg=6)
    # Crown: a lumpy sphere (a few overlapping blobs)
    for k in range(4):
        ox, oy = rng.uniform(-0.25, 0.25) * crown, rng.uniform(-0.25, 0.25) * crown
        oz = height * 0.62 + rng.uniform(-0.1, 0.12) * height
        r = crown * rng.uniform(0.45, 0.6)
        sphere(bm, ox, oy, oz, r, 1, seg=10, rings=6)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    trunk = simple_material(name + " trunk", (0.25, 0.18, 0.12), 0.9)
    leaves = bpy.data.materials.new(name + " leaves")
    nt = leaves.node_tree
    b = nt.nodes.get("Principled BSDF")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.12, 0.24, 0.07, 1)
    ramp.color_ramp.elements[1].color = (0.30, 0.42, 0.14, 1)
    nt.links.new(info.outputs["Random"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    me.materials.append(trunk)
    me.materials.append(leaves)
    ob = bpy.data.objects.new(name, me)
    return ob


def build_trees(trees):
    protos = [tree_prototype("TreeA", 18, 9, 1), tree_prototype("TreeB", 14, 7, 2), tree_prototype("TreeC", 11, 6, 3)]
    coll = bpy.data.collections.new("TreeProtos")
    bpy.context.scene.collection.children.link(coll)
    for p in protos:
        coll.objects.link(p)
    coll.hide_render = True
    coll.hide_viewport = True
    rng = random.Random(11)
    groups = [[], [], []]
    for x, y, s, kind in trees:
        groups[2 if kind == 1 else rng.randrange(2)].append((x, y, s))
    for proto, pts in zip(protos, groups):
        if not pts:
            continue
        me = bpy.data.meshes.new(proto.name + "Points")
        me.vertices.add(len(pts))
        me.vertices.foreach_set("co", [c for x, y, _ in pts for c in (x, y, 0.0)])
        a = me.attributes.new("tree_scale", "FLOAT", "POINT")
        a.data.foreach_set("value", [s for _, _, s in pts])
        ob = bpy.data.objects.new(proto.name + "Instances", me)
        bpy.context.collection.objects.link(ob)
        mod = ob.modifiers.new("Instances", "NODES")
        ng = bpy.data.node_groups.new(proto.name + "GN", "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        nin = ng.nodes.new("NodeGroupInput")
        nout = ng.nodes.new("NodeGroupOutput")
        inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
        objn = ng.nodes.new("GeometryNodeObjectInfo")
        objn.inputs["Object"].default_value = proto
        objn.inputs["As Instance"].default_value = True
        sc = ng.nodes.new("GeometryNodeInputNamedAttribute")
        sc.data_type = "FLOAT"
        sc.inputs["Name"].default_value = "tree_scale"
        ng.links.new(nin.outputs[0], inst.inputs["Points"])
        ng.links.new(objn.outputs["Geometry"], inst.inputs["Instance"])
        ng.links.new(sc.outputs["Attribute"], inst.inputs["Scale"])
        ng.links.new(inst.outputs["Instances"], nout.inputs[0])
        mod.node_group = ng


# ---------------------------------------------------------------------------------------------- scene

def setup_scene(W, H, a):
    sc = bpy.context.scene
    engines = {"eevee": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"), "cycles": ("CYCLES",)}[a.engine]
    for e in engines:
        try:
            sc.render.engine = e
            break
        except TypeError:
            continue
    if a.engine == "cycles":
        sc.cycles.samples = a.samples
        sc.cycles.use_denoising = True
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "METAL"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = True
            sc.cycles.device = "GPU"
        except Exception as ex:  # noqa: BLE001
            print("GPU setup failed, using CPU:", ex)
    else:
        ee = sc.eevee
        ee.taa_render_samples = a.samples
        for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2),
                          ("use_gtao", True), ("gtao_distance", 6.0)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except Exception:  # noqa: BLE001
                    pass
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass

    # Sky light + sun from the north-west (top-left of the screen)
    world = bpy.data.worlds.new("Sky")
    sc.world = world
    bg = world.node_tree.nodes.get("Background")
    hdr = os.path.normpath(os.path.join(HERE, "..", "..", "hdri", "sky_2k.hdr"))
    if os.path.exists(hdr):
        env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdr)
        world.node_tree.links.new(env.outputs[0], bg.inputs[0])
    bg.inputs["Strength"].default_value = 0.55
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.2
    sun.data.angle = math.radians(2.5)
    sun.data.color = (1.0, 0.96, 0.9)
    travel = Vector((0.75, -0.6, -math.tan(math.radians(42)))).normalized()   # light travels to the SE, downwards
    sun.rotation_euler = (-travel).to_track_quat("Z", "Y").to_euler()
    bpy.context.collection.objects.link(sun)

    # Orthographic camera straight down over the map (or a crop of it)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.type = "ORTHO"
    x0, y0, x1, y1 = (0, 0, W, H) if not a.crop else (float(v) for v in a.crop.split(","))
    w, h = x1 - x0, y1 - y0
    cam.data.ortho_scale = max(w, h)
    cam.location = ((x0 + x1) / 2, (y0 + y1) / 2, 1500)
    cam.data.clip_end = 5000
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x = a.width
    sc.render.resolution_y = int(round(a.width * h / w))
    sc.render.resolution_percentage = 100
    sc.render.filepath = a.out


def main():
    a = args()
    t0 = time.time()
    with open(os.path.join(HERE, "berlin_osm.json")) as f:
        data = json.load(f)
    with open(os.path.join(BUILD, "trees.json")) as f:
        trees = json.load(f)
    W, H = data["size_m"]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new("Ground")
    me.from_pydata([(0, 0, 0), (W, 0, 0), (W, H, 0), (0, H, 0)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for loop, uvv in zip(uvl.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = uvv
    me.materials.append(ground_material(W, H))
    bpy.context.collection.objects.link(bpy.data.objects.new("Ground", me))

    walls, roofs = building_materials()
    n = build_buildings(data, walls, roofs)
    build_landmarks(data)
    build_trees(trees)
    setup_scene(W, H, a)
    t1 = time.time()
    print(f"SCENE BUILT in {t1 - t0:.1f}s: {n} buildings, {len(trees)} trees, 4 landmarks")
    os.makedirs(BUILD, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "berlin.blend"))
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y} "
          f"({a.engine}) in {time.time() - t1:.1f}s -> {a.out}")


main()
