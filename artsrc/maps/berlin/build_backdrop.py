"""
Berlin 1946 backdrop (IDEA-28): builds the post-war scene in Blender from build/layout.json (layout.py) and renders the
painted backdrop of the map.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/berlin/build_backdrop.py -- \
      [--ppc 64] [--samples 32] [--crop x0,y0,x1,y1 (cells)] [--out build/backdrop.png]

--ppc is pixels per map cell (64 = what the game draws; 18 is a quick preview). The map is 128 x 80 cells of 7 m.

Projection (same as the HD units and buildings): the camera looks straight down and everything 3D is sheared so that
height leans up the screen (y += z * cot 50deg). The ground lines up with the map cells; the south walls show.
The sun comes from the top-left (north-west). Trees are not painted: they are actors in the map (they can burn).
"""
import argparse
import json
import math
import os
import random
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
ARTSRC = os.path.normpath(os.path.join(HERE, "..", ".."))
TEX = os.path.join(ARTSRC, "textures")
SHEAR = 1 / math.tan(math.radians(50))
OBLIQUE = Matrix(((1, 0, 0, 0), (0, 1, SHEAR, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
FLOOR = 3.6                                     # metres per storey

PLASTER = [(0.62, 0.55, 0.43), (0.55, 0.52, 0.46), (0.60, 0.49, 0.38), (0.49, 0.48, 0.45), (0.64, 0.58, 0.47),
           (0.52, 0.43, 0.36)]
ROOF = [(0.26, 0.27, 0.29), (0.32, 0.31, 0.30), (0.40, 0.25, 0.19), (0.34, 0.22, 0.17), (0.23, 0.23, 0.24),
        (0.30, 0.29, 0.27)]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--ppc", type=int, default=64)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--crop", help="render only these cells: x0,y0,x1,y1")
    ap.add_argument("--out", default=os.path.join(BUILD, "backdrop.png"))
    ap.add_argument("--no-render", action="store_true")
    return ap.parse_args(argv)


# ---------------------------------------------------------------------------------------------- materials

PAINTED = os.path.normpath(os.path.join(ARTSRC, "..", "assets", "maps", "berlin"))


def painted(name):
    """A hand-painted ChatGPT texture (berlin-prompts.md) if it has been generated, else None."""
    if not name:
        return None
    for p in (os.path.join(PAINTED, "seamless", f"tex-{name}.png"), os.path.join(PAINTED, f"tex-{name}.png")):
        if os.path.exists(p):
            return p
    return None


def tex(name, kind="Color"):
    import glob
    hits = sorted(glob.glob(os.path.join(TEX, name, f"*_{kind}.jpg")))
    return hits[0]


def node_img(nt, path, non_color=False):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    return n


def tiled(nt, coord, name, repeat_m, tint=None, paint=None, paint_repeat=None):
    """Photo texture `name` tiled every `repeat_m` metres, or the painted texture `paint` (already coloured, so
    not tinted) every `paint_repeat` metres when it exists."""
    path = painted(paint)
    if path:
        repeat_m, tint = paint_repeat or repeat_m, None
    m = nt.nodes.new("ShaderNodeMapping")
    m.inputs["Scale"].default_value = (1 / repeat_m, 1 / repeat_m, 1 / repeat_m)
    nt.links.new(coord.outputs["Object"], m.inputs["Vector"])
    t = node_img(nt, path or tex(name))
    nt.links.new(m.outputs["Vector"], t.inputs["Vector"])
    out = t.outputs["Color"]
    if path:
        # Hide the repeat: a second copy, rotated and at another scale, shows through a large-scale noise mask
        m2 = nt.nodes.new("ShaderNodeMapping")
        m2.inputs["Scale"].default_value = (1 / (repeat_m * 1.37),) * 3
        m2.inputs["Rotation"].default_value = (0, 0, 0.65)
        m2.inputs["Location"].default_value = (0.31, 0.17, 0)
        nt.links.new(coord.outputs["Object"], m2.inputs["Vector"])
        t2 = node_img(nt, path)
        nt.links.new(m2.outputs["Vector"], t2.inputs["Vector"])
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 0.6 / repeat_m
        nz.inputs["Detail"].default_value = 2.0
        nt.links.new(coord.outputs["Object"], nz.inputs["Vector"])
        r = nt.nodes.new("ShaderNodeMapRange")
        r.inputs["From Min"].default_value = 0.42
        r.inputs["From Max"].default_value = 0.58
        nt.links.new(nz.outputs["Fac"], r.inputs["Value"])
        out = mix(nt, out, t2.outputs["Color"], r.outputs["Result"])
    if tint:
        out = mul(nt, out, tint)
    return out


def mul(nt, a, rgb):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = "MULTIPLY"
    n.inputs["Factor"].default_value = 1.0
    nt.links.new(a, n.inputs[6])
    if isinstance(rgb, tuple):
        n.inputs[7].default_value = (*rgb, 1)
    else:
        nt.links.new(rgb, n.inputs[7])
    return n.outputs[2]


def mix(nt, a, b, fac):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    nt.links.new(fac, n.inputs["Factor"])
    for sock, v in ((n.inputs[6], a), (n.inputs[7], b)):
        if isinstance(v, tuple):
            sock.default_value = (*v, 1)
        else:
            nt.links.new(v, sock)
    return n.outputs[2]


def math_node(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for sock, v in zip(n.inputs, (a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            sock.default_value = v
        else:
            nt.links.new(v, sock)
    return n.outputs[0]


def noise(nt, coord, scale, detail=4.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    nt.links.new(coord.outputs["Object"], n.inputs["Vector"])
    return n.outputs["Fac"]


def edge(nt, maskv, nz, softness=0.35):
    """A mask with a ragged, painted-looking edge: (mask + noise) through a smooth step."""
    s = math_node(nt, "ADD", maskv, math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", nz, 0.5), softness * 2))
    r = nt.nodes.new("ShaderNodeMapRange")
    r.interpolation_type = "SMOOTHSTEP"
    r.inputs["From Min"].default_value = 0.42
    r.inputs["From Max"].default_value = 0.58
    nt.links.new(s, r.inputs["Value"])
    return r.outputs["Result"]


def new_mat(name):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    coord = nt.nodes.new("ShaderNodeTexCoord")
    return mat, nt, bsdf, coord


def ground_material():
    mat, nt, bsdf, coord = new_mat("Ground")
    ga = node_img(nt, os.path.join(BUILD, "ground_a.png"), non_color=True)
    ga.image.alpha_mode = "CHANNEL_PACKED"
    ga.interpolation = "Cubic"
    nt.links.new(coord.outputs["UV"], ga.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(ga.outputs["Color"], sep.inputs[0])
    wt = node_img(nt, os.path.join(BUILD, "water.png"), non_color=True)
    wt.interpolation = "Cubic"
    nt.links.new(coord.outputs["UV"], wt.inputs["Vector"])

    n_small = noise(nt, coord, 0.25)
    n_big = noise(nt, coord, 0.02, 2.0)
    paving = tiled(nt, coord, "PavingStones070", 3.2, (0.72, 0.68, 0.62), "cobbles", 16.0)
    # Streets: cobbles (most of Berlin's streets in 1946), a little darker than the squares. The painted asphalt
    # read as water to ChatGPT's repaint on the wide avenues.
    asphalt = mul(nt, tiled(nt, coord, "Asphalt012", 9.0, (0.62, 0.60, 0.60), "cobbles", 11.0), (0.8, 0.78, 0.76))
    grass = tiled(nt, coord, "Grass004", 6.0, (0.78, 0.80, 0.58), "lawn", 24.0)
    dirt = tiled(nt, coord, "Ground054", 5.0, (0.78, 0.70, 0.60), "mud", 26.0)
    quay = tiled(nt, coord, "Concrete034", 3.0, (0.80, 0.78, 0.74), "quay", 9.0)

    col = paving
    col = mix(nt, col, asphalt, edge(nt, sep.outputs[0], n_small, 0.12))
    col = mix(nt, col, grass, edge(nt, sep.outputs[1], n_small, 0.45))
    # Dirt (cut-down park, courtyards): muddy earth with patches of worn grass
    n_mid = noise(nt, coord, 0.06, 3.0)
    mud = mix(nt, mul(nt, dirt, (0.62, 0.55, 0.45)), mul(nt, grass, (0.75, 0.72, 0.6)),
              edge(nt, math_node(nt, "MULTIPLY", n_mid, 1.0), n_small, 0.25))
    col = mix(nt, col, mud, edge(nt, sep.outputs[2], n_small, 0.45))
    # Dust patches everywhere: the city is a ruin
    dust = edge(nt, math_node(nt, "MULTIPLY", n_big, 0.95), n_small, 0.3)
    col = mix(nt, col, mul(nt, dirt, (0.9, 0.85, 0.8)), math_node(nt, "MULTIPLY", dust, 0.3))
    col = mix(nt, col, quay, edge(nt, ga.outputs["Alpha"], n_small, 0.05))

    # The Spree: murky green-grey, darker near the quay walls
    wcol = mix(nt, (0.06, 0.10, 0.10), (0.12, 0.17, 0.16), n_small)
    shore = math_node(nt, "POWER", wt.outputs["Color"], 0.35)
    wcol = mix(nt, (0.03, 0.05, 0.05), wcol, shore)
    water = math_node(nt, "GREATER_THAN", wt.outputs["Color"], 0.5)
    col = mix(nt, col, wcol, water)
    # Large-scale colour variation, warm
    col = mul(nt, col, mix(nt, (0.86, 0.84, 0.82), (1.04, 1.0, 0.94), n_big))
    nt.links.new(col, bsdf.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMix")
    nt.links.new(water, rough.inputs[0])
    rough.inputs[2].default_value = 0.9
    rough.inputs[3].default_value = 0.12
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(n_small, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def painted_facade_material():
    """Walls from the painted facade textures (u = metres along the wall, v = metres up; one texture = 19 x 19 m):
    ochre or grey picked by the house colour ('bcol'), the burnt-out facade where 'burn' is high."""
    mat, nt, bsdf, coord = new_mat("Facade")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "bcol"
    burn = nt.nodes.new("ShaderNodeAttribute")
    burn.attribute_name = "burn"
    uv = nt.nodes.new("ShaderNodeUVMap")
    m = nt.nodes.new("ShaderNodeMapping")
    m.inputs["Scale"].default_value = (1 / 19.0, 1 / 19.0, 1)
    nt.links.new(uv.outputs["UV"], m.inputs["Vector"])
    imgs = []
    for name in ("facade-ochre", "facade-grey", "facade-burnt"):
        t = node_img(nt, painted(name) or painted("facade-ochre"))
        nt.links.new(m.outputs["Vector"], t.inputs["Vector"])
        imgs.append(t.outputs["Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attr.outputs["Color"], sep.inputs[0])
    greyish = math_node(nt, "LESS_THAN", math_node(nt, "SUBTRACT", sep.outputs[0], sep.outputs[2]), 0.1)
    col = mix(nt, imgs[0], imgs[1], greyish)
    col = mix(nt, col, imgs[2], math_node(nt, "GREATER_THAN", burn.outputs["Fac"], 0.7))
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def facade_material():
    """Walls: plaster (colour from the 'bcol' attribute), a grid of windows from the wall UVs (u = metres along the
    wall, v = metres up), ground-floor shop band, cornice. 'burn' (0..1) blackens the windows and adds soot above them.
    The painted facades replace all of this once they have been generated."""
    if painted("facade-ochre"):
        return painted_facade_material()
    mat, nt, bsdf, coord = new_mat("Facade")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "bcol"
    burn = nt.nodes.new("ShaderNodeAttribute")
    burn.attribute_name = "burn"
    plaster = mul(nt, tiled(nt, coord, "Plaster001", 2.5), attr.outputs["Color"])
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]

    def band(x, period, lo, hi):
        f = math_node(nt, "FRACT", math_node(nt, "DIVIDE", x, period))
        return math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", f, lo), math_node(nt, "LESS_THAN", f, hi))

    win = math_node(nt, "MULTIPLY", band(u, 3.8, 0.34, 0.66), band(v, FLOOR, 0.25, 0.78))
    upper = math_node(nt, "GREATER_THAN", v, 4.2)
    win = math_node(nt, "MULTIPLY", win, upper)
    shop = math_node(nt, "MULTIPLY", math_node(nt, "LESS_THAN", v, 3.4), band(u, 5.0, 0.12, 0.88))
    soot_v = math_node(nt, "MULTIPLY", band(u, 3.4, 0.2, 0.8), band(v, FLOOR, 0.78, 1.0))
    soot = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", soot_v, upper), burn.outputs["Fac"])
    col = mix(nt, plaster, mul(nt, plaster, (0.35, 0.33, 0.3)), soot)
    glass = mix(nt, (0.10, 0.11, 0.12), (0.015, 0.012, 0.01), burn.outputs["Fac"])
    col = mix(nt, col, glass, math_node(nt, "MAXIMUM", win, shop))
    # General grime towards the ground
    grime = math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", 1.0, math_node(nt, "DIVIDE", v, 8.0), True), 0.35)
    col = mix(nt, col, (0.2, 0.18, 0.16), math_node(nt, "MAXIMUM", grime, 0.0))
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def roof_material():
    mat, nt, bsdf, coord = new_mat("Roof")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "bcol"
    if painted("roof-slate"):
        # Slate or red tiles, picked by the roof colour
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(attr.outputs["Color"], sep.inputs[0])
        red = math_node(nt, "GREATER_THAN", math_node(nt, "SUBTRACT", sep.outputs[0], sep.outputs[2]), 0.08)
        col = mix(nt, tiled(nt, coord, "RoofingTiles006", 8.0, None, "roof-slate", 8.0),
                  tiled(nt, coord, "RoofingTiles006", 8.0, None, "roof-tile", 8.0), red)
    else:
        col = mul(nt, tiled(nt, coord, "RoofingTiles006", 3.0), attr.outputs["Color"])
        col = mul(nt, col, (1.3, 1.3, 1.3))
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    return mat


def plain(name, rgb, rough=0.85, metal=0.0, tex_name=None, repeat=3.0, paint=None, paint_repeat=None, shade=None):
    mat, nt, bsdf, coord = new_mat(name)
    if tex_name:
        col = tiled(nt, coord, tex_name, repeat, rgb, paint, paint_repeat)
        nt.links.new(mul(nt, col, shade) if shade else col, bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return mat


# ---------------------------------------------------------------------------------------------- geometry helpers

class Mesh:
    """One bmesh with per-face colour/burn attributes and wall UVs."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.col = self.bm.faces.layers.float_color.new("bcol")
        self.burn = self.bm.faces.layers.float.new("burn")

    def face(self, pts, mat=0, color=(1, 1, 1), burn=0.0, uvs=None):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = mat
        f[self.col] = (*color, 1)
        f[self.burn] = burn
        if uvs:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv
        else:
            for loop in f.loops:
                loop[self.uv].uv = (loop.vert.co.x, loop.vert.co.y)
        return f

    def box(self, x0, y0, x1, y1, z0, z1, mat=0, color=(1, 1, 1), burn=0.0, top=True, bottom=False):
        h = z1 - z0
        quads = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
        for (ax, ay), (bx, by) in quads:
            ln = math.hypot(bx - ax, by - ay)
            self.face([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], mat, color, burn,
                      [(0, z0), (ln, z0), (ln, z0 + h), (0, z0 + h)])
        if top:
            self.face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mat, color, burn)
        if bottom:
            self.face([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], mat, color, burn)

    def cylinder(self, cx, cy, r0, r1, z0, z1, mat=0, color=(1, 1, 1), seg=16, cap=True):
        ring = [(math.cos(2 * math.pi * i / seg), math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        for i in range(seg):
            (ax, ay), (bx, by) = ring[i], ring[(i + 1) % seg]
            u0, u1 = i / seg * 2 * math.pi * r0, (i + 1) / seg * 2 * math.pi * r0
            self.face([(cx + ax * r0, cy + ay * r0, z0), (cx + bx * r0, cy + by * r0, z0),
                       (cx + bx * r1, cy + by * r1, z1), (cx + ax * r1, cy + ay * r1, z1)], mat, color, 0,
                      [(u0, z0), (u1, z0), (u1, z1), (u0, z1)])
        if cap:
            self.face([(cx + x * r1, cy + y * r1, z1) for x, y in ring], mat, color)

    def blob(self, x, y, z, r, flat, mat=0, color=(1, 1, 1), rng=None):
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=1, radius=r,
                                         matrix=Matrix.Translation((x, y, z)) @ Matrix.Diagonal((1, 1, flat, 1)))
        for v in res["verts"]:
            if rng:
                v.co += Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(-0.1, 0.1))) * r
        faces = {f for v in res["verts"] for f in v.link_faces}
        for f in faces:
            f.material_index = mat
            f[self.col] = (*color, 1)
            for loop in f.loops:
                loop[self.uv].uv = (loop.vert.co.x, loop.vert.co.z)

    def finish(self, mats, parent):
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        # Bake the oblique projection into the vertices (a sheared object matrix confuses EEVEE's culling)
        me.transform(OBLIQUE)
        me.update()
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.collection.objects.link(ob)
        return ob


# ---------------------------------------------------------------------------------------------- the city

def build_city(L, parent, rng):
    C = L["cell_m"]
    NY = L["cells"][1]

    def m(cx, cy):
        return cx * C, (NY - cy) * C

    facade, roof = bpy.data.materials.get("Facade") or facade_material(), roof_material()
    rubble_m = plain("Rubble", (0.62, 0.55, 0.48), tex_name="Ground054", repeat=2.0, paint="rubble", paint_repeat=6.0)
    brick_m = plain("Brick", (0.55, 0.38, 0.30), tex_name="Plaster001", repeat=1.5)
    houses = Mesh("Houses")          # materials: 0 facade, 1 roof, 2 rubble, 3 brick
    for i, b in enumerate(L["buildings"]):
        cx0, cy0, cx1, cy1 = b["rect"]
        x0, y1 = m(cx0, cy0)
        x1, y0 = m(cx1, cy1)
        color = PLASTER[b["facade"]]
        r = random.Random(i)
        h = b["floors"] * FLOOR + 1.2
        if b["state"] == "standing":
            houses.box(x0, y0, x1, y1, 0, h, 0, color, burn=r.choice((0.0, 0.0, 0.4)), top=False)
            # Pitched roof along the long side, with a cornice line
            rc = ROOF[r.randrange(len(ROOF))]
            w, d = x1 - x0, y1 - y0
            rh = min(w, d) * 0.38
            if w >= d:
                ym = (y0 + y1) / 2
                houses.face([(x0, y0, h), (x1, y0, h), (x1, ym, h + rh), (x0, ym, h + rh)], 1, rc)
                houses.face([(x1, y1, h), (x0, y1, h), (x0, ym, h + rh), (x1, ym, h + rh)], 1, rc)
                houses.face([(x0, y1, h), (x0, y0, h), (x0, ym, h + rh)], 0, color)
                houses.face([(x1, y0, h), (x1, y1, h), (x1, ym, h + rh)], 0, color)
            else:
                xm = (x0 + x1) / 2
                houses.face([(x1, y0, h), (x1, y1, h), (xm, y1, h + rh), (xm, y0, h + rh)], 1, rc)
                houses.face([(x0, y1, h), (x0, y0, h), (xm, y0, h + rh), (xm, y1, h + rh)], 1, rc)
                houses.face([(x0, y0, h), (x1, y0, h), (xm, y0, h + rh)], 0, color)
                houses.face([(x1, y1, h), (x0, y1, h), (xm, y1, h + rh)], 0, color)
            # Chimneys
            for _ in range(r.randint(1, 3)):
                cx, cy = r.uniform(x0 + 1.5, x1 - 1.5), r.uniform(y0 + 1.5, y1 - 1.5)
                houses.box(cx - 0.5, cy - 0.5, cx + 0.5, cy + 0.5, h, h + rh + 1.2, 3, (0.5, 0.36, 0.3))
        elif b["state"] == "shell":
            # Burnt-out shell: outer walls only, broken tops, rubble inside
            t = 0.7
            for (ax, ay, bx, by) in ((x0, y0, x1, y0 + t), (x0, y1 - t, x1, y1), (x0, y0, x0 + t, y1), (x1 - t, y0, x1, y1)):
                horizontal = bx - ax > by - ay
                length = (bx - ax) if horizontal else (by - ay)
                n = max(1, int(length / 3.4))
                for k in range(n):
                    hh = h * r.choice((1.0, 1.0, 0.9, 0.75, 0.6, 0.45, 0.3))
                    if horizontal:
                        houses.box(ax + k * length / n, ay, ax + (k + 1) * length / n, by, 0, hh, 0, color, 1.0)
                    else:
                        houses.box(ax, ay + k * length / n, bx, ay + (k + 1) * length / n, 0, hh, 0, color, 1.0)
            for _ in range(int((x1 - x0) * (y1 - y0) / 25) + 2):
                houses.blob(r.uniform(x0 + 1, x1 - 1), r.uniform(y0 + 1, y1 - 1), 0, r.uniform(1.2, 2.6),
                            r.uniform(0.35, 0.6), 2, (0.8, 0.78, 0.74), r)
        else:
            # Collapsed: heaps of rubble and a few wall stumps
            for _ in range(int((x1 - x0) * (y1 - y0) / 12) + 3):
                houses.blob(r.uniform(x0, x1), r.uniform(y0, y1), 0, r.uniform(1.4, 3.4), r.uniform(0.3, 0.55), 2,
                            (0.9, 0.86, 0.8), r)
            for _ in range(r.randint(0, 2)):
                sx, sy = r.uniform(x0, x1 - 3), r.uniform(y0, y1 - 0.7)
                houses.box(sx, sy, sx + r.uniform(2, 5), sy + 0.7, 0, r.uniform(2, 7), 0, color, 1.0)
            for _ in range(int((x1 - x0) * (y1 - y0) / 18)):
                bx_, by_ = r.uniform(x0, x1), r.uniform(y0, y1)
                houses.box(bx_, by_, bx_ + 0.6, by_ + 0.3, 0, 0.25, 3, (0.6, 0.4, 0.32))
    houses.finish([facade, roof, rubble_m, brick_m], parent)
    return m


def build_landmarks(L, parent, m, rng):
    stone = plain("Sandstone", (0.74, 0.66, 0.52), tex_name="Plaster001", repeat=2.0, paint="quay", paint_repeat=6.0)
    dark_stone = plain("Burnt stone", (0.46, 0.42, 0.36), tex_name="Plaster001", repeat=2.0, paint="pavement", paint_repeat=8.0)
    bronze = plain("Bronze", (0.22, 0.30, 0.25), 0.45, 0.6)
    gold = plain("Gold", (0.92, 0.70, 0.30), 0.3, 1.0)
    steel = plain("Steel", (0.30, 0.30, 0.31), 0.5, 0.8)
    concrete = plain("Concrete", (0.50, 0.48, 0.45), tex_name="Concrete034", repeat=4.0, paint="quay", paint_repeat=8.0,
                     shade=(0.7, 0.68, 0.65))
    courtyard = plain("Courtyard", (0.3, 0.28, 0.26), tex_name="Ground054", repeat=3.0, paint="courtyard", paint_repeat=8.0,
                      shade=(0.55, 0.52, 0.5))
    slate = plain("Slate", (0.3, 0.31, 0.33), tex_name="RoofingTiles006", repeat=4.0, paint="roof-slate", paint_repeat=8.0)
    rubble = plain("Rubble2", (0.62, 0.55, 0.48), tex_name="Ground054", repeat=2.0, paint="rubble", paint_repeat=6.0)
    lm = Mesh("Landmarks")   # 0 stone, 1 burnt stone, 2 bronze, 3 gold, 4 steel, 5 concrete, 6 rubble, 7 facade,
    #                          8 courtyard, 9 slate
    C = L["cell_m"]

    # Reichstag: 140 x 98 m, burnt, corner towers, west portico, the bare steel frame of its dome
    cx, cy, w, h = L["landmarks"]["reichstag"]
    rx, ry = m(cx, cy)
    W, D = w * C / 2, h * C / 2
    sand = (0.62, 0.56, 0.45)
    lm.box(rx - W, ry - D, rx + W, ry + D, 0, 24, 7, sand, burn=1.0, top=False)
    # Roof: sloped slate wings around four dark inner courtyards (so it reads as a roof, not a square)
    wing = 14
    lm.box(rx - W + 1, ry - D + 1, rx + W - 1, ry - D + wing, 24, 29, 9)
    lm.box(rx - W + 1, ry + D - wing, rx + W - 1, ry + D - 1, 24, 29, 9)
    lm.box(rx - W + 1, ry - D + wing, rx - W + wing, ry + D - wing, 24, 29, 9)
    lm.box(rx + W - wing, ry - D + wing, rx + W - 1, ry + D - wing, 24, 29, 9)
    lm.box(rx - 12, ry - D + wing, rx + 12, ry + D - wing, 24, 29, 9)            # central hall under the dome
    for cx_ in (rx - W + wing, rx + 12):                                          # courtyards: dark, low
        for cy_ in (ry - D + wing, ry):
            lm.box(cx_ + 1, cy_ + 1, cx_ + (W - wing - 12) - 1, cy_ + (D - wing) - 1, 0, 2, 8)
    for _ in range(12):
        lm.blob(rng.uniform(rx - W + 4, rx + W - 4), rng.uniform(ry - D + 4, ry + D - 4), 29, rng.uniform(1.5, 3.0), 0.4, 6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            tx, ty = rx + sx * (W - 9), ry + sy * (D - 9)
            lm.box(tx - 9, ty - 9, tx + 9, ty + 9, 0, 33, 7, sand, burn=1.0)
            lm.box(tx - 7, ty - 7, tx + 7, ty + 7, 33, 36, 1)
    for k in range(6):                                                  # west portico columns
        lm.cylinder(rx - W - 4, ry - 13 + k * 5.2, 1.1, 1.0, 2, 22, 0, seg=10)
    lm.box(rx - W - 7, ry - 16, rx - W, ry + 16, 0, 2, 0)
    lm.box(rx - W - 6, ry - 16, rx - W, ry + 16, 22, 26, 0)
    lm.face([(rx - W - 6, ry - 16, 26), (rx - W - 6, ry + 16, 26), (rx - W - 6, ry, 32)], 0)   # pediment
    # Dome frame: ribs and rings
    dz, dr = 27, 18
    for k in range(16):
        a = 2 * math.pi * k / 16
        prev = None
        for j in range(9):
            t = j / 8 * math.pi / 2
            p = (rx + math.cos(a) * dr * math.cos(t), ry + math.sin(a) * dr * math.cos(t), dz + dr * 0.9 * math.sin(t))
            if prev:
                lm.cylinder((p[0] + prev[0]) / 2, (p[1] + prev[1]) / 2, 0.35, 0.35, min(p[2], prev[2]), max(p[2], prev[2]) + 0.6, 4, seg=4, cap=False)
            prev = p
    for j in (1, 3, 5):
        t = j / 8 * math.pi / 2
        rr, zz = dr * math.cos(t), dz + dr * 0.9 * math.sin(t)
        lm.cylinder(rx, ry, rr, rr, zz, zz + 0.5, 4, seg=32, cap=False)
    lm.cylinder(rx, ry, dr + 1, dr + 1, 24, 28, 1, seg=32)

    # Brandenburg Gate: runs north-south, 6 rows of Doric columns, attic, quadriga
    gx, gy = m(*L["landmarks"]["brandenburg_gate"])
    lm.box(gx - 6, gy - 32, gx + 6, gy + 32, 0, 1.2, 0)
    for k in range(6):
        cy_ = gy + (-4.7 + k * 1.88) * C
        for sx in (-1, 1):
            lm.cylinder(gx + sx * 4, cy_, 0.9, 0.8, 1.2, 14, 0, seg=12)
    lm.box(gx - 6, gy - 33, gx + 6, gy + 33, 14, 17.5, 0)
    lm.box(gx - 4.5, gy - 20, gx + 4.5, gy + 20, 17.5, 21, 0)
    lm.box(gx - 2, gy - 4, gx + 2, gy + 4, 21, 22.5, 0)
    for k in range(4):                                                   # the four horses, battered
        lm.blob(gx - 0.5, gy - 3 + k * 2, 24, 1.2, 1.4, 2)
    lm.box(gx + 0.5, gy - 0.8, gx + 1.5, gy + 0.8, 22.5, 27, 2)
    for side in (-1, 1):                                                 # guard houses
        lm.box(gx - 7, gy + side * 42 - 7, gx + 7, gy + side * 42 + 7, 0, 9, 0)
        lm.box(gx - 7.5, gy + side * 42 - 7.5, gx + 7.5, gy + side * 42 + 7.5, 9, 10.5, 0)

    # Victory Column on its round terrace
    vx, vy = m(*L["landmarks"]["victory_column"])
    lm.cylinder(vx, vy, 16, 16, 0, 1.0, 0, seg=40)
    lm.box(vx - 9, vy - 9, vx + 9, vy + 9, 1, 8, 0)
    lm.cylinder(vx, vy, 6.5, 6.5, 8, 16, 0, seg=24)
    for k in range(16):
        a = 2 * math.pi * k / 16
        lm.cylinder(vx + 6.8 * math.cos(a), vy + 6.8 * math.sin(a), 0.4, 0.4, 8, 16, 0, seg=6)
    lm.cylinder(vx, vy, 7.2, 7.2, 16, 17, 0, seg=24)
    for j in range(4):                                                   # column drums with gilded bands
        z0 = 17 + j * 10
        lm.cylinder(vx, vy, 3.2 - j * 0.2, 3.0 - j * 0.2, z0, z0 + 9, 1 if j % 2 else 0, seg=20)
        lm.cylinder(vx, vy, 3.3 - j * 0.2, 3.3 - j * 0.2, z0 + 9, z0 + 10, 3, seg=20)
    lm.cylinder(vx, vy, 2.6, 2.6, 57, 59, 0, seg=16)
    lm.cylinder(vx, vy, 1.0, 0.5, 59, 66, 3, seg=10)
    lm.blob(vx, vy + 1.5, 64, 1.8, 0.3, 3)                               # Victoria's wings

    # Soviet tower under construction: concrete shaft, scaffold rings, a crane
    tx, ty = m(*L["landmarks"]["soviet_tower"])
    lm.cylinder(tx, ty, 14, 14, 0, 6, 5, seg=24)
    lm.cylinder(tx, ty, 8, 5.5, 6, 88, 5, seg=24)
    for j in range(12):
        z = 50 + j * 4
        lm.cylinder(tx, ty, 7.5, 7.5, z, z + 0.3, 4, seg=24, cap=False)
    for k in range(8):
        a = 2 * math.pi * k / 8
        lm.cylinder(tx + 7.4 * math.cos(a), ty + 7.4 * math.sin(a), 0.25, 0.25, 50, 98, 4, seg=4, cap=False)
    lm.box(tx + 9, ty - 1, tx + 11, ty + 1, 0, 110, 4)
    lm.box(tx - 25, ty - 0.8, tx + 32, ty + 0.8, 108, 110, 4)
    lm.box(tx + 26, ty - 2, tx + 32, ty + 2, 104, 108, 4)
    lm.cylinder(tx - 18, ty, 0.1, 0.1, 80, 108, 4, seg=3, cap=False)
    for _ in range(14):
        a = rng.uniform(0, 2 * math.pi)
        lm.blob(tx + math.cos(a) * rng.uniform(16, 26), ty + math.sin(a) * rng.uniform(16, 26), 0, rng.uniform(1.5, 3),
                0.4, 6)
    lm.finish([stone, dark_stone, bronze, gold, steel, concrete, rubble, bpy.data.materials.get("Facade"), courtyard, slate],
              parent)


def build_details(L, parent, m, rng):
    """Bridges, quay walls, wrecked cars, craters, tree stumps in Tiergarten, tank traps."""
    C = L["cell_m"]
    NX, NY = L["cells"]
    grid = L["grid"]
    ground = L["ground"]
    stone = plain("Bridge stone", (0.62, 0.58, 0.52), tex_name="Concrete034", repeat=3.0)
    asphalt = plain("Bridge road", (0.35, 0.34, 0.33), tex_name="Asphalt012", repeat=6.0, paint="cobbles", paint_repeat=9.0)
    wreck = plain("Wreck", (0.16, 0.14, 0.12), 0.7, 0.4)
    wood = plain("Stump", (0.36, 0.26, 0.18), 0.9)
    crater = plain("Crater", (0.42, 0.36, 0.30), 0.95, tex_name="Ground054", repeat=2.0, paint="courtyard", paint_repeat=5.0,
                   shade=(0.45, 0.42, 0.40))
    rim = plain("Crater rim", (0.40, 0.34, 0.27), 0.95, tex_name="Ground054", repeat=2.0, paint="rubble", paint_repeat=6.0)
    d = Mesh("Details")      # 0 stone, 1 asphalt, 2 wreck, 3 wood, 4 crater, 5 crater rim
    water_rows = {}
    for y in range(NY):
        for x in range(NX):
            if grid[y][x] == "~":
                water_rows.setdefault(x, []).append(y)
    # Bridges: deck, parapets, piers
    for bx, bw in L["bridges"]:
        cols = [y for x in range(int(bx - bw / 2) - 1, int(bx + bw / 2) + 1) for y in water_rows.get(x, [])]
        if not cols:
            continue
        y0c, y1c = min(cols) - 1.5, max(cols) + 2.5
        x0, ytop = m(bx - bw / 2, y0c)
        x1, ybot = m(bx + bw / 2, y1c)
        d.box(x0, ybot, x1, ytop, 0.6, 1.4, 1)
        d.box(x0 - 0.8, ybot, x0, ytop, 0.6, 2.6, 0)
        d.box(x1, ybot, x1 + 0.8, ytop, 0.6, 2.6, 0)
        d.box(x0 - 0.8, ybot, x1 + 0.8, ytop, -2.5, 0.6, 0, top=False)
    # Quay walls along the smooth river banks: a stone wall dropping into the water, and a low parapet on top
    half = L["spree_width"] / 2 * C
    bridges_m = [((bx - bw / 2 - 0.5) * C, (bx + bw / 2 + 0.5) * C) for bx, bw in L["bridges"]]
    pts = [m(x, y) for x, y in L["spree"]]
    for (ax, ay), (bx_, by_) in zip(pts, pts[1:]):
        ln = math.hypot(bx_ - ax, by_ - ay)
        n = max(1, int(ln / 2.0))
        nx_, ny_ = -(by_ - ay) / ln, (bx_ - ax) / ln
        for side in (-1, 1):
            for k in range(n):
                p0 = (ax + (bx_ - ax) * k / n + nx_ * half * side, ay + (by_ - ay) * k / n + ny_ * half * side)
                p1 = (ax + (bx_ - ax) * (k + 1) / n + nx_ * half * side, ay + (by_ - ay) * (k + 1) / n + ny_ * half * side)
                if any(lo <= (p0[0] + p1[0]) / 2 <= hi for lo, hi in bridges_m):
                    continue
                o = (nx_ * side * 0.6, ny_ * side * 0.6)              # outward, away from the water
                q0, q1 = (p0[0] + o[0], p0[1] + o[1]), (p1[0] + o[0], p1[1] + o[1])
                d.face([(p0[0], p0[1], -2.5), (p1[0], p1[1], -2.5), (p1[0], p1[1], 0.9), (p0[0], p0[1], 0.9)], 0)
                d.face([(p1[0], p1[1], -2.5), (p0[0], p0[1], -2.5), (p0[0], p0[1], 0.9), (p1[0], p1[1], 0.9)], 0)
                d.face([(p0[0], p0[1], 0.9), (p1[0], p1[1], 0.9), (q1[0], q1[1], 0.9), (q0[0], q0[1], 0.9)], 0)
    # Wrecked vehicles on the streets, craters everywhere outside the river
    for k in range(40):
        x, y = rng.randrange(NX), rng.randrange(NY)
        if ground[y][x] != "a" or grid[y][x] != ".":
            continue
        cx, cy = m(x + rng.random(), y + rng.random())
        a = rng.choice((0, math.pi / 2)) + rng.uniform(-0.4, 0.4)
        ln, wd = rng.uniform(4.2, 5.5), 1.9
        ca, sa = math.cos(a), math.sin(a)
        corners = [(cx + ca * u - sa * v, cy + sa * u + ca * v) for u, v in ((-ln / 2, -wd / 2), (ln / 2, -wd / 2), (ln / 2, wd / 2), (-ln / 2, wd / 2))]
        for z0, z1, s in ((0.3, 1.0, 1.0), (1.0, 1.6, 0.6)):
            pts = [(cx + (px - cx) * s, cy + (py - cy) * s) for px, py in corners]
            for i in range(4):
                (ax, ay), (bx_, by_) = pts[i], pts[(i + 1) % 4]
                d.face([(ax, ay, z0), (bx_, by_, z0), (bx_, by_, z1), (ax, ay, z1)], 2)
            d.face([(px, py, z1) for px, py in pts], 2)
    for k in range(220):
        x, y = rng.uniform(0, NX), rng.uniform(0, NY)
        if grid[int(y)][int(x)] == "~":
            continue
        cx, cy = m(x, y)
        r = rng.uniform(1.5, 4.5)
        ring = [(math.cos(2 * math.pi * i / 14), math.sin(2 * math.pi * i / 14)) for i in range(14)]
        d.face([(cx + u * r, cy + v * r, 0.04) for u, v in ring], 4)
        for i in range(14):                                               # thrown-up rim
            (ua, va), (ub, vb) = ring[i], ring[(i + 1) % 14]
            d.face([(cx + ua * r, cy + va * r, 0.03), (cx + ub * r, cy + vb * r, 0.03),
                    (cx + ub * r * 1.35, cy + vb * r * 1.35, 0.0), (cx + ua * r * 1.35, cy + va * r * 1.35, 0.0)], 5)
    # Tree stumps where Tiergarten was cut down
    for y in range(NY):
        for x in range(NX):
            if ground[y][x] != "s" or grid[y][x] != ".":
                continue
            for _ in range(rng.randint(0, 3)):
                cx, cy = m(x + rng.random(), y + rng.random())
                d.cylinder(cx, cy, rng.uniform(0.25, 0.45), rng.uniform(0.2, 0.4), 0, rng.uniform(0.3, 0.8), 3, seg=6)
    # Tank traps across the avenue east of the gate
    gx, gy = L["landmarks"]["brandenburg_gate"]
    for k in range(10):
        cx, cy = m(gx + 13 + (k % 2) * 0.6, gy - 1.8 + k * 0.42)
        for a in (0, math.pi / 3, 2 * math.pi / 3):
            d.box(cx - 0.9 * math.cos(a) - 0.1, cy - 0.9 * math.sin(a) - 0.1, cx + 0.9 * math.cos(a) + 0.1,
                  cy + 0.9 * math.sin(a) + 0.1, 0, 1.2, 2)
    d.finish([stone, asphalt, wreck, wood, crater, rim], parent)


# ---------------------------------------------------------------------------------------------- scene

def setup(L, a):
    sc = bpy.context.scene
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = e
            break
        except TypeError:
            continue
    ee = sc.eevee
    ee.taa_render_samples = a.samples
    for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2),
                      ("shadow_step_count", 8), ("use_gtao", True), ("gtao_distance", 4.0)):
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
    world = bpy.data.worlds.new("Sky")
    sc.world = world
    bg = world.node_tree.nodes.get("Background")
    hdr = os.path.join(ARTSRC, "hdri", "sky_2k.hdr")
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdr)
    world.node_tree.links.new(env.outputs[0], bg.inputs[0])
    bg.inputs["Strength"].default_value = 0.45
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.6
    sun.data.angle = math.radians(1.5)
    sun.data.color = (1.0, 0.91, 0.78)
    travel = Vector((0.7, -0.62, -math.tan(math.radians(40)))).normalized()
    sun.rotation_euler = (-travel).to_track_quat("Z", "Y").to_euler()
    bpy.context.collection.objects.link(sun)

    C = L["cell_m"]
    NX, NY = L["cells"]
    x0, y0, x1, y1 = (0, 0, NX, NY) if not a.crop else (float(v) for v in a.crop.split(","))
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.type = "ORTHO"
    w, h = (x1 - x0) * C, (y1 - y0) * C
    cam.data.ortho_scale = max(w, h)
    cam.location = ((x0 + x1) / 2 * C, (NY - (y0 + y1) / 2) * C, 600)
    cam.data.clip_end = 2000
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x = int(round((x1 - x0) * a.ppc))
    sc.render.resolution_y = int(round((y1 - y0) * a.ppc))
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.filepath = a.out


def main():
    a = args()
    t0 = time.time()
    with open(os.path.join(BUILD, "layout.json")) as f:
        L = json.load(f)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(1946)
    C = L["cell_m"]
    NX, NY = L["cells"]
    W, H = NX * C, NY * C

    # Ground (flat, not sheared)
    me = bpy.data.meshes.new("Ground")
    pad = 40
    me.from_pydata([(-pad, -pad, 0), (W + pad, -pad, 0), (W + pad, H + pad, 0), (-pad, H + pad, 0)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for loop, v in zip(uvl.data, me.vertices):
        loop.uv = (v.co.x / W, v.co.y / H)
    me.materials.append(ground_material())
    bpy.context.collection.objects.link(bpy.data.objects.new("Ground", me))

    # Everything 3D is sheared (Mesh.finish): height leans up the screen like the game's art
    oblique = None
    m = build_city(L, oblique, rng)
    build_landmarks(L, oblique, m, rng)
    build_details(L, oblique, m, rng)
    setup(L, a)
    t1 = time.time()
    print(f"SCENE BUILT in {t1 - t0:.1f}s")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "berlin1946.blend"))
    if not a.no_render:
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y} "
              f"in {time.time() - t1:.1f}s -> {a.out}")


main()
