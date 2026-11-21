"""
Ironward backdrop (IDEA-28): builds the walled prison-city on a moonlit winter night in Blender from build/layout.json
(layout.py) and renders the painted backdrop of the map.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/ironward/build_backdrop.py -- \
      [--ppc 64] [--samples 32] [--crop x0,y0,x1,y1 (cells)] [--out build/backdrop.png] [--no-render]

--ppc is pixels per map cell (64 = what the game draws; 8 is a quick preview). The map is 128 x 128 cells of 7 m.

Projection (same as Berlin and the HD units): the camera looks straight down and everything 3D is sheared so that
height leans up the screen (y += z * cot 50deg). The ground lines up with the map cells; the south walls show.
The moon comes from the top-left (north-west) like the sun in the rest of the game's art; street lamps, lit windows,
fire barrels and the watchtowers' searchlights add warm pools of light. Moonlit, not pitch black: units must read.

Noir skyline: stepped art-deco / gothic towers (glowing crowns, statues, water tanks), black steel elevated railway
viaducts on pillars, steel arch truss bridges over the canals, neon shop signs and lit rooftop billboards. Tall
things lean north in this projection, so a tower only goes where its lean falls on other houses, the wall or water,
never on open streets (tower_height).
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
from mathutils import Matrix, Vector

bpy.context.preferences.filepaths.save_version = 0      # no .blend1 backup copies (they filled the disk)

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
ARTSRC = os.path.normpath(os.path.join(HERE, "..", ".."))
TEX = os.path.join(ARTSRC, "textures")
SHEAR = 1 / math.tan(math.radians(50))
OBLIQUE = Matrix(((1, 0, 0, 0), (0, 1, SHEAR, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
FLOOR = 3.6                                     # metres per storey
LAMP_RGB = (1.0, 0.62, 0.30)                    # sodium street lamps
WINDOW_RGB = (1.0, 0.70, 0.38)

NEON = {"pink": (1.0, 0.12, 0.45), "cyan": (0.10, 0.85, 1.0), "red": (1.0, 0.08, 0.05), "green": (0.25, 1.0, 0.35),
        "amber": (1.0, 0.55, 0.08), "violet": (0.55, 0.20, 1.0)}
DISTRICT_NEON = {"foundry": ["amber", "red", "red", "cyan"], "courthouse": ["pink", "violet", "cyan", "amber"],
                 "pier": ["cyan", "green", "green", "pink"], "abbey": ["red", "violet", "green", "red"]}
WORDS = {"foundry": ["STEEL", "BAR", "DINER", "PAWN", "TOOLS", "BOXING", "LIQUOR", "GARAGE"],
         "courthouse": ["HOTEL", "THEATER", "CASINO", "JAZZ", "BANK", "CAFE", "DANCE", "RADIO"],
         "pier": ["FERRY", "MOTEL", "NOODLES", "FISH", "TAXI", "BAR", "CARGO", "OPEN"],
         "abbey": ["CHAPEL", "TAVERN", "PAWN", "HOTEL", "BAR", "CANDLES", "DINER", "OPEN"]}
TOWER_OPEN_MAX = 0.2         # share of open (walkable) cells a tower's lean may cover

# Per-district wall stone and roof colours (multiplied over the textures)
DISTRICT = {
    "foundry":    {"walls": [(0.55, 0.30, 0.24), (0.48, 0.28, 0.22), (0.42, 0.30, 0.26)], "roof": (0.22, 0.22, 0.24)},
    "courthouse": {"walls": [(0.78, 0.74, 0.66), (0.70, 0.68, 0.62), (0.74, 0.70, 0.60)], "roof": (0.20, 0.30, 0.28)},
    "pier":       {"walls": [(0.46, 0.40, 0.34), (0.38, 0.40, 0.42), (0.52, 0.44, 0.36)], "roof": (0.30, 0.30, 0.32)},
    "abbey":      {"walls": [(0.42, 0.42, 0.46), (0.36, 0.36, 0.40), (0.48, 0.46, 0.46)], "roof": (0.18, 0.18, 0.22)},
}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--ppc", type=int, default=64)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--crop", help="render only these cells: x0,y0,x1,y1")
    ap.add_argument("--out", default=os.path.join(BUILD, "backdrop.png"))
    ap.add_argument("--no-render", action="store_true")
    return ap.parse_args(argv)


# ---------------------------------------------------------------------------------------------- shader helpers

PAINTED = os.path.normpath(os.path.join(ARTSRC, "..", "assets", "maps", "ironward"))


def painted(name):
    """A painted ChatGPT texture (ironward-prompts.md) if it has been generated, else None."""
    for p in (os.path.join(PAINTED, "seamless", f"tex-{name}.png"), os.path.join(PAINTED, f"tex-{name}.png")):
        if os.path.exists(p):
            return p
    return None


PAINT_GAIN = (1.45, 1.30, 1.05)     # the textures already carry painted moonlight: warm them so the blue moon
#                                    does not tint them twice, and lift them out of the dark


def paint_tex(nt, coord, name, repeat_m, socket="Object", sat=0.8):
    """A painted texture tiled every repeat_m metres; a second copy, rotated and scaled, shows through a large noise
    mask to hide the repeat. `sat` scales the saturation, then PAINT_GAIN balances the colour."""
    path = painted(name)
    src = coord.outputs[socket] if hasattr(coord, "outputs") else coord
    m = nt.nodes.new("ShaderNodeMapping")
    m.inputs["Scale"].default_value = (1 / repeat_m,) * 3
    nt.links.new(src, m.inputs["Vector"])
    t1 = node_img(nt, path)
    nt.links.new(m.outputs["Vector"], t1.inputs["Vector"])
    m2 = nt.nodes.new("ShaderNodeMapping")
    m2.inputs["Scale"].default_value = (1 / (repeat_m * 1.37),) * 3
    m2.inputs["Rotation"].default_value = (0, 0, 0.65)
    m2.inputs["Location"].default_value = (0.31, 0.17, 0)
    nt.links.new(src, m2.inputs["Vector"])
    t2 = node_img(nt, path)
    nt.links.new(m2.outputs["Vector"], t2.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.6 / repeat_m
    nz.inputs["Detail"].default_value = 2.0
    nt.links.new(src, nz.inputs["Vector"])
    col = mix(nt, t1.outputs["Color"], t2.outputs["Color"], smooth(nt, nz.outputs["Fac"], 0.42, 0.58))
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = sat
    nt.links.new(col, hs.inputs["Color"])
    return mul(nt, hs.outputs["Color"], PAINT_GAIN)


def tex_or_paint(nt, coord, name, repeat_m, tint, paint, paint_repeat):
    """The painted texture `paint` (already coloured, so not tinted) when it exists, else the photo texture."""
    if painted(paint):
        return paint_tex(nt, coord, paint, paint_repeat)
    return tiled(nt, coord, name, repeat_m, tint)

def tex(name, kind="Color"):
    return sorted(glob.glob(os.path.join(TEX, name, f"*_{kind}.jpg")))[0]


def node_img(nt, path, non_color=False):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    return n


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
    if isinstance(fac, (int, float)):
        n.inputs["Factor"].default_value = fac
    else:
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


def tiled(nt, coord, name, repeat_m, tint=None, socket="Object"):
    m = nt.nodes.new("ShaderNodeMapping")
    m.inputs["Scale"].default_value = (1 / repeat_m, 1 / repeat_m, 1 / repeat_m)
    nt.links.new(coord.outputs[socket] if hasattr(coord, "outputs") else coord, m.inputs["Vector"])
    t = node_img(nt, tex(name))
    nt.links.new(m.outputs["Vector"], t.inputs["Vector"])
    out = t.outputs["Color"]
    return mul(nt, out, tint) if tint else out


def noise(nt, coord, scale, detail=4.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    nt.links.new(coord.outputs["Object"], n.inputs["Vector"])
    return n.outputs["Fac"]


def smooth(nt, v, lo, hi):
    r = nt.nodes.new("ShaderNodeMapRange")
    r.interpolation_type = "SMOOTHSTEP"
    r.inputs["From Min"].default_value = lo
    r.inputs["From Max"].default_value = hi
    nt.links.new(v, r.inputs["Value"])
    return r.outputs["Result"]


def edge(nt, maskv, nz, softness=0.35):
    """A mask with a ragged, painted-looking edge: (mask + noise) through a smooth step."""
    s = math_node(nt, "ADD", maskv, math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", nz, 0.5), softness * 2))
    return smooth(nt, s, 0.42, 0.58)


def attr(nt, name):
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = name
    return a


def new_mat(name):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    coord = nt.nodes.new("ShaderNodeTexCoord")
    return mat, nt, bsdf, coord


def snow_color(nt, coord):
    """Moonlit snow: near white with a faint blue, soft drifts."""
    if painted("snow"):
        return paint_tex(nt, coord, "snow", 12.0)
    s = tiled(nt, coord, "Snow006", 4.0, (0.92, 0.95, 1.0))
    return mul(nt, s, mix(nt, (0.86, 0.88, 0.92), (1.0, 1.0, 1.0), noise(nt, coord, 0.05, 3.0)))


# ---------------------------------------------------------------------------------------------- materials

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

    n_small = noise(nt, coord, 0.3)
    n_mid = noise(nt, coord, 0.07, 3.0)
    snow = snow_color(nt, coord)
    cobbles = tiled(nt, coord, "PavingStones131", 3.0, (0.55, 0.55, 0.6))
    slush = paint_tex(nt, coord, "slush", 26.0, sat=0.3) if painted("slush") else mul(nt, tiled(nt, coord, "Asphalt012", 12.0), (0.42, 0.44, 0.50))
    quay = tex_or_paint(nt, coord, "Concrete034", 3.0, (0.6, 0.6, 0.64), "quay", 8.0)

    # Open ground: snow with old cobbles showing through in trodden patches
    col = mix(nt, snow, cobbles, math_node(nt, "MULTIPLY", edge(nt, math_node(nt, "MULTIPLY", n_mid, 0.8), n_small, 0.2), 0.4))
    # Ploughed streets: wet slush with snow banked along the edges and tyre tracks of thin snow
    tracks = smooth(nt, noise(nt, coord, 0.25, 3.0), 0.55, 0.75)
    street = mix(nt, slush, mul(nt, snow, (0.8, 0.82, 0.88)), math_node(nt, "MULTIPLY", tracks, 0.15 if painted("slush") else 0.5))
    col = mix(nt, col, street, edge(nt, math_node(nt, "MULTIPLY", sep.outputs[0], 0.95), n_small, 0.08))
    # Plazas: swept cobbles with snow in the joints and drifts
    if painted("plaza"):
        plaza = mix(nt, paint_tex(nt, coord, "plaza", 14.0), snow, smooth(nt, noise(nt, coord, 0.05, 3.0), 0.55, 0.75))
    else:
        joints = smooth(nt, tiled(nt, coord, "PavingStones131", 3.0), 0.25, 0.5)
        plaza = mix(nt, snow, mul(nt, cobbles, (1.2, 1.2, 1.3)),
                    math_node(nt, "MULTIPLY", joints, smooth(nt, noise(nt, coord, 0.15, 3.0), 0.4, 0.6)))
    col = mix(nt, col, plaza, edge(nt, sep.outputs[1], n_small, 0.3))
    col = mix(nt, col, quay, edge(nt, ga.outputs["Alpha"], n_small, 0.05))

    # Canals: black water, a crust of ice and snow at the edges
    wv = wt.outputs["Color"]
    wcol = mix(nt, (0.010, 0.016, 0.026), (0.022, 0.034, 0.05), n_small)
    ice = mix(nt, (0.30, 0.38, 0.46), (0.55, 0.62, 0.70), n_small)
    shore = smooth(nt, wv, 0.5, 0.62)
    wcol = mix(nt, ice, wcol, edge(nt, shore, noise(nt, coord, 0.8, 2.0), 0.2))
    water = math_node(nt, "GREATER_THAN", wv, 0.5)
    col = mix(nt, col, wcol, water)
    nt.links.new(col, bsdf.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMix")
    nt.links.new(water, rough.inputs[0])
    rough.inputs[2].default_value = 0.75
    rough.inputs[3].default_value = 0.08
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    nt.links.new(n_small, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def painted_facade_material():
    """Walls from the painted facade textures (u = metres along the wall, v = metres up; one texture = 14.4 x 14.4 m,
    four storeys): limestone, brick or dark stone picked by the house colour ('bcol'). The windows are painted;
    'lit' and 'seed' add a soft warm glow on the lit ones."""
    mat, nt, bsdf, coord = new_mat("Facade")
    bcol = attr(nt, "bcol")
    uv = nt.nodes.new("ShaderNodeUVMap")
    m = nt.nodes.new("ShaderNodeMapping")
    m.inputs["Scale"].default_value = (1 / 14.4, 1 / 14.4, 1)
    nt.links.new(uv.outputs["UV"], m.inputs["Vector"])
    imgs = []
    for name in ("facade-stone", "facade-brick", "facade-limestone"):
        t = node_img(nt, painted(name) or painted("facade-stone"))
        nt.links.new(m.outputs["Vector"], t.inputs["Vector"])
        imgs.append(t.outputs["Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(bcol.outputs["Color"], sep.inputs[0])
    brick = math_node(nt, "GREATER_THAN", math_node(nt, "SUBTRACT", sep.outputs[0], sep.outputs[2]), 0.08)
    lime = math_node(nt, "GREATER_THAN", sep.outputs[0], 0.65)
    col = mix(nt, mix(nt, imgs[0], imgs[1], brick), imgs[2], lime)
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = 0.85
    nt.links.new(col, hs.inputs["Color"])
    nt.links.new(mul(nt, hs.outputs["Color"], PAINT_GAIN), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    # The painted window light glows: emission from the warm, bright parts of the texture
    hsv = nt.nodes.new("ShaderNodeSeparateColor")
    hsv.mode = "HSV"
    nt.links.new(col, hsv.inputs[0])
    warm = math_node(nt, "MULTIPLY", math_node(nt, "LESS_THAN", hsv.outputs[0], 0.16), smooth(nt, hsv.outputs[2], 0.55, 0.85))
    warm = math_node(nt, "MULTIPLY", warm, math_node(nt, "GREATER_THAN", hsv.outputs[1], 0.35))
    bsdf.inputs["Emission Color"].default_value = (*WINDOW_RGB, 1)
    nt.links.new(math_node(nt, "MULTIPLY", warm, 6.0), bsdf.inputs["Emission Strength"])
    return mat


def facade_material():
    """Gothic stone walls: colour from 'bcol', tall arched windows from the wall UVs (u = metres along, v = metres up);
    a share 'lit' of them glow warm. 'seed' varies the pattern per house."""
    if painted("facade-stone"):
        return painted_facade_material()
    mat, nt, bsdf, coord = new_mat("Facade")
    bcol = attr(nt, "bcol")
    lit = attr(nt, "lit")
    seed = attr(nt, "seed")
    stone = mul(nt, tiled(nt, coord, "Bricks076C", 2.2, None, "Object"), (1.5, 1.5, 1.55))
    stone = mul(nt, stone, bcol.outputs["Color"])
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]

    def band(x, period, lo, hi):
        f = math_node(nt, "FRACT", math_node(nt, "DIVIDE", x, period))
        return math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", f, lo), math_node(nt, "LESS_THAN", f, hi))

    win = math_node(nt, "MULTIPLY", band(u, 3.4, 0.36, 0.64), band(v, FLOOR, 0.22, 0.86))
    win = math_node(nt, "MULTIPLY", win, math_node(nt, "GREATER_THAN", v, 1.0))
    # Which windows are lit: white noise per window cell and house
    cell = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(math_node(nt, "FLOOR", math_node(nt, "DIVIDE", u, 3.4)), cell.inputs[0])
    nt.links.new(math_node(nt, "FLOOR", math_node(nt, "DIVIDE", v, FLOOR)), cell.inputs[1])
    nt.links.new(math_node(nt, "MULTIPLY", seed.outputs["Fac"], 97.0), cell.inputs[2])
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    nt.links.new(cell.outputs[0], wn.inputs["Vector"])
    on = math_node(nt, "LESS_THAN", wn.outputs["Value"], math_node(nt, "MULTIPLY", lit.outputs["Fac"], 0.55))
    glow = math_node(nt, "MULTIPLY", win, on)
    glass = (0.02, 0.025, 0.035)
    col = mix(nt, stone, glass, win)
    # Grime and frost: darker toward the ground, rime on the ledges
    grime = math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", 1.0, math_node(nt, "DIVIDE", v, 6.0), True), 0.4)
    col = mix(nt, col, (0.08, 0.08, 0.09), grime)
    ledge = math_node(nt, "MULTIPLY", band(v, FLOOR, 0.9, 1.0), math_node(nt, "SUBTRACT", 1.0, win))
    col = mix(nt, col, (0.8, 0.84, 0.9), math_node(nt, "MULTIPLY", ledge, 0.6))
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Emission Color"].default_value = (*WINDOW_RGB, 1)
    nt.links.new(math_node(nt, "MULTIPLY", glow, 9.0), bsdf.inputs["Emission Strength"])
    return mat


def roof_material():
    """Dark slate under snow; 'snow' (0..1) per face sets the cover (flat tops full, steep slopes patchy)."""
    mat, nt, bsdf, coord = new_mat("Roof")
    bcol = attr(nt, "bcol")
    sn = attr(nt, "snow")
    if painted("roof-snow"):
        slate = mul(nt, paint_tex(nt, coord, "roof-snow", 8.0), (0.75, 0.75, 0.8))
    else:
        slate = mul(nt, tiled(nt, coord, "RoofingTiles006", 3.0), bcol.outputs["Color"])
        slate = mul(nt, slate, (1.6, 1.6, 1.6))
    cover = edge(nt, math_node(nt, "MULTIPLY", sn.outputs["Fac"], 0.8), noise(nt, coord, 0.22, 4.0), 0.5)
    col = mix(nt, slate, mul(nt, snow_color(nt, coord), (0.85, 0.87, 0.92)), cover)
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    return mat


def plain(name, rgb, rough=0.85, metal=0.0, tex_name=None, repeat=3.0, emission=None, strength=0.0):
    mat, nt, bsdf, coord = new_mat(name)
    if tex_name:
        nt.links.new(tiled(nt, coord, tex_name, repeat, rgb), bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def snowy(name, rgb, tex_name="Concrete034", repeat=3.0):
    """A stone/metal material whose upward faces (face attribute 'snow') carry snow."""
    mat, nt, bsdf, coord = new_mat(name)
    base = paint_tex(nt, coord, "steel", 4.0) if (tex_name == "steel" and painted("steel")) else \
        tiled(nt, coord, "Concrete034" if tex_name == "steel" else tex_name, repeat, rgb)
    sn = attr(nt, "snow")
    cover = edge(nt, math_node(nt, "MULTIPLY", sn.outputs["Fac"], 0.9), noise(nt, coord, 0.6, 3.0), 0.3)
    nt.links.new(mix(nt, base, snow_color(nt, coord), cover), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


# ---------------------------------------------------------------------------------------------- geometry

class Mesh:
    """One bmesh with per-face colour / lit / seed / snow attributes and wall UVs."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.col = self.bm.faces.layers.float_color.new("bcol")
        self.lit = self.bm.faces.layers.float.new("lit")
        self.seed = self.bm.faces.layers.float.new("seed")
        self.snow = self.bm.faces.layers.float.new("snow")
        self.cur = {"lit": 0.0, "seed": 0.0}

    def face(self, pts, mat=0, color=(1, 1, 1), snow=None, uvs=None):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = mat
        f[self.col] = (*color, 1)
        f[self.lit] = self.cur["lit"]
        f[self.seed] = self.cur["seed"]
        if snow is None:
            f.normal_update()
            snow = 1.0 if f.normal.z > 0.9 else (0.75 if f.normal.z > 0.3 else 0.0)
        f[self.snow] = snow
        if uvs:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv
        else:
            for loop in f.loops:
                loop[self.uv].uv = (loop.vert.co.x, loop.vert.co.y)
        return f

    def wall(self, a, b, z0, z1, mat, color):
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        self.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], mat, color, 0.0,
                  [(0, z0), (ln, z0), (ln, z1), (0, z1)])

    def box(self, x0, y0, x1, y1, z0, z1, mat=0, color=(1, 1, 1), top=True, top_mat=None):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            self.wall(a, b, z0, z1, mat, color)
        if top:
            self.face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mat if top_mat is None else top_mat, color)

    def cylinder(self, cx, cy, r0, r1, z0, z1, mat=0, color=(1, 1, 1), seg=16, cap=True):
        ring = [(math.cos(2 * math.pi * i / seg), math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        for i in range(seg):
            (ax, ay), (bx, by) = ring[i], ring[(i + 1) % seg]
            u0, u1 = i / seg * 2 * math.pi * r0, (i + 1) / seg * 2 * math.pi * r0
            self.face([(cx + ax * r0, cy + ay * r0, z0), (cx + bx * r0, cy + by * r0, z0),
                       (cx + bx * r1, cy + by * r1, z1), (cx + ax * r1, cy + ay * r1, z1)], mat, color, None,
                      [(u0, z0), (u1, z0), (u1, z1), (u0, z1)])
        if cap:
            self.face([(cx + x * r1, cy + y * r1, z1) for x, y in ring], mat, color)

    def cone(self, cx, cy, r, z0, z1, mat=0, color=(1, 1, 1), seg=8):
        for i in range(seg):
            a, b = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            self.face([(cx + r * math.cos(a), cy + r * math.sin(a), z0), (cx + r * math.cos(b), cy + r * math.sin(b), z0),
                       (cx, cy, z1)], mat, color)

    def pyramid(self, x0, y0, x1, y1, z0, z1, mat=0, color=(1, 1, 1)):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            self.face([(a[0], a[1], z0), (b[0], b[1], z0), (cx, cy, z1)], mat, color)

    def gable_roof(self, x0, y0, x1, y1, z, rh, mat, color, wall_mat, wall_color):
        """Pitched roof along the long side, with gable ends in the wall material."""
        if x1 - x0 >= y1 - y0:
            ym = (y0 + y1) / 2
            self.face([(x0, y0, z), (x1, y0, z), (x1, ym, z + rh), (x0, ym, z + rh)], mat, color)
            self.face([(x1, y1, z), (x0, y1, z), (x0, ym, z + rh), (x1, ym, z + rh)], mat, color)
            self.face([(x0, y1, z), (x0, y0, z), (x0, ym, z + rh)], wall_mat, wall_color, 0.0, [(0, 0)] * 3)
            self.face([(x1, y0, z), (x1, y1, z), (x1, ym, z + rh)], wall_mat, wall_color, 0.0, [(0, 0)] * 3)
        else:
            xm = (x0 + x1) / 2
            self.face([(x1, y0, z), (x1, y1, z), (xm, y1, z + rh), (xm, y0, z + rh)], mat, color)
            self.face([(x0, y1, z), (x0, y0, z), (xm, y0, z + rh), (xm, y1, z + rh)], mat, color)
            self.face([(x0, y0, z), (x1, y0, z), (xm, y0, z + rh)], wall_mat, wall_color, 0.0, [(0, 0)] * 3)
            self.face([(x1, y1, z), (x0, y1, z), (xm, y1, z + rh)], wall_mat, wall_color, 0.0, [(0, 0)] * 3)

    def beam(self, p0, p1, t, mat=0, color=(1, 1, 1)):
        """A square beam of thickness t from p0 to p1 (any direction)."""
        a, b = Vector(p0), Vector(p1)
        dv = b - a
        if dv.length < 1e-4:
            return
        dv.normalize()
        ref = Vector((0, 0, 1)) if abs(dv.z) < 0.9 else Vector((1, 0, 0))
        u = dv.cross(ref).normalized() * t / 2
        v = dv.cross(u).normalized() * t / 2
        ring = [u + v, -u + v, -u - v, u - v]
        for i in range(4):
            c0, c1 = ring[i], ring[(i + 1) % 4]
            self.face([a + c0, b + c0, b + c1, a + c1], mat, color)

    def blob(self, x, y, z, r, flat, mat=0, color=(1, 1, 1), rng=None):
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=1, radius=r,
                                         matrix=Matrix.Translation((x, y, z)) @ Matrix.Diagonal((1, 1, flat, 1)))
        for vtx in res["verts"]:
            if rng:
                vtx.co += Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(-0.1, 0.1))) * r
        for f in {f for vtx in res["verts"] for f in vtx.link_faces}:
            f.material_index = mat
            f[self.col] = (*color, 1)
            f[self.snow] = 1.0
            for loop in f.loops:
                loop[self.uv].uv = (loop.vert.co.x, loop.vert.co.z)

    def finish(self, mats):
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


LIGHTS = []


ANIM = []      # animated lights for the game (PxBackdropLights): (anim, x, y_sheared, rgb, size, aim)


def light(x, y, z, rgb, watts, radius=0.3, kind="POINT", aim=None, spot_deg=30.0, anim="lamp", size=1.0):
    """A light at (x, y, z) in metres, sheared like the meshes. Created in bulk by make_lights(). `anim` names how the
    game animates it on top of the backdrop (lamp, neon, fire, blink, search, steady); None = baked only. Searchlights
    are not baked at all: the game sweeps them."""
    if kind != "SPOT":
        LIGHTS.append((x, y + z * SHEAR, z, rgb, watts, radius, kind, aim, spot_deg))
    if anim:
        ANIM.append((anim, x, y + z * SHEAR, rgb, size, aim))


def marker(anim, x, y, z, rgb, size=1.0):
    """An animated light for the game only (no Blender light), e.g. the red beacons on masts."""
    ANIM.append((anim, x, y + z * SHEAR, rgb, size, None))


def write_anim_lights(L):
    """build/lights.txt: one line per animated light, in map cells of the playable area (x right, y down, the picture's
    position, i.e. after the height lean): kind x y r g b size [aim_x aim_y]."""
    C, N = L["cell_m"], L["cells"][1]
    lines = []
    for anim, x, ys, rgb, size, aim in ANIM:
        line = f"{anim} {x / C:.3f} {N - ys / C:.3f} {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} {size:.2f}"
        if aim:
            line += f" {aim[0] / C:.3f} {N - aim[1] / C:.3f}"
        lines.append(line)
    with open(os.path.join(BUILD, "lights.txt"), "w") as f:
        f.write("# Ironward animated lights (build_backdrop.py): kind x y r g b size [aim_x aim_y]\n" + "\n".join(lines) + "\n")
    print(f"{len(lines)} animated lights")


def make_lights():
    data = {}
    for i, (x, y, z, rgb, watts, radius, kind, aim, spot_deg) in enumerate(LIGHTS):
        key = (kind, rgb, round(watts), radius, spot_deg)
        if key not in data:
            d = bpy.data.lights.new(f"L{len(data)}", kind)
            d.color = rgb
            d.energy = watts
            d.shadow_soft_size = radius
            if hasattr(d, "use_shadow"):
                d.use_shadow = kind != "POINT"
            if kind == "SPOT":
                d.spot_size = math.radians(spot_deg)
                d.spot_blend = 0.6
            data[key] = d
        ob = bpy.data.objects.new(f"Light{i}", data[key])
        ob.location = (x, y, z)
        if aim:
            ax, ay, az = aim
            direction = Vector((ax - x, ay + az * SHEAR - y, az - z))
            ob.rotation_euler = (-direction).to_track_quat("Z", "Y").to_euler()
        bpy.context.collection.objects.link(ob)
    print(f"{len(LIGHTS)} lights")
    write_anim_lights(BUILD_L)


# ---------------------------------------------------------------------------------------------- the city

def neon_materials():
    mats = [plain("Sign frame", (0.03, 0.03, 0.035), 0.5, 0.6)]
    for name, rgb in NEON.items():
        mats.append(plain(f"Neon {name}", rgb, 0.4, emission=rgb, strength=22.0))
    mats.append(plain("Billboard", (0.9, 0.9, 0.85), 0.5, emission=(1.0, 0.95, 0.85), strength=2.5))
    mats.append(plain("Ink", (0.02, 0.02, 0.02), 0.6))
    mats.append(plain("Statue", (0.32, 0.42, 0.38), 0.6, 0.3))
    return mats


NEON_INDEX = {name: i + 1 for i, name in enumerate(NEON)}
BILLBOARD, INK, STATUE = len(NEON) + 1, len(NEON) + 2, len(NEON) + 3
TEXT_CACHE = {}
TEXTS = []


def text(word, mat_index, cx, yface, zc, height, max_w):
    """Queues a word written on a south-facing surface (centre cx, zc; in front of the wall at y = yface)."""
    TEXTS.append((word, mat_index, cx, yface, zc, height, max_w))


def make_texts(mats):
    for word, mi, cx, yface, zc, height, max_w in TEXTS:
        if word not in TEXT_CACHE:
            cu = bpy.data.curves.new("txt", "FONT")
            cu.body = word
            cu.size = 1.0
            cu.extrude = 0.04
            cu.align_x = "CENTER"
            cu.align_y = "CENTER"
            ob = bpy.data.objects.new("txt", cu)
            bpy.context.collection.objects.link(ob)
            bpy.context.view_layer.update()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            bpy.data.objects.remove(ob)
            xs = [v.co.x for v in me.vertices] or [0, 1]
            ys = [v.co.y for v in me.vertices] or [0, 1]
            TEXT_CACHE[word] = (me, max(xs) - min(xs), max(ys) - min(ys))
        me, tw, th = TEXT_CACHE[word]
        s = min(height / max(th, 0.01), max_w / max(tw, 0.01))
        mx = Matrix.Translation((cx, yface, zc)) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Scale(s, 4)
        me2 = me.copy()
        me2.transform(OBLIQUE @ mx)
        me2.materials.clear()
        me2.materials.append(mats[mi])
        bpy.context.collection.objects.link(bpy.data.objects.new(f"Text {word}", me2))
    print(f"{len(TEXTS)} signs with text")


def tower_height(b, grid, r):
    """Height (m) of a tower on this lot, or 0: only lots of 3x3+ cells, and only where the northward lean covers
    at most TOWER_OPEN_MAX open cells."""
    x0, y0, x1, y1 = (int(round(v)) for v in b["rect"])
    if (x1 - x0) * (y1 - y0) < 9 or min(x1 - x0, y1 - y0) < 3 or r.random() > 0.6:
        return 0
    for h in (78, 64, 52, 42, 34):
        lean = math.ceil(h * SHEAR / 7.0)
        cells = [grid[y][x] for x in range(x0, x1) for y in range(max(0, y0 - lean), y0)]
        if not cells or sum(c == "." for c in cells) / len(cells) <= TOWER_OPEN_MAX:
            return h
    return 0


def statue(mesh, x, y, z, s, mat):
    """A robed figure with a raised arm on a little plinth."""
    mesh.box(x - 0.8 * s, y - 0.8 * s, x + 0.8 * s, y + 0.8 * s, z, z + 0.8 * s, mat)
    mesh.cylinder(x, y, 0.75 * s, 0.35 * s, z + 0.8 * s, z + 3.4 * s, mat, seg=8)
    mesh.blob(x, y, z + 3.8 * s, 0.38 * s, 1.1, mat)
    mesh.beam((x + 0.3 * s, y, z + 3.1 * s), (x + 0.9 * s, y - 0.2 * s, z + 4.6 * s), 0.25 * s, mat)
    mesh.beam((x - 0.3 * s, y, z + 3.1 * s), (x - 0.7 * s, y - 0.3 * s, z + 2.2 * s), 0.25 * s, mat)


def water_tank(mesh, x, y, z, iron):
    for dx, dy in ((-1.6, -1.6), (1.6, -1.6), (-1.6, 1.6), (1.6, 1.6)):
        mesh.beam((x + dx, y + dy, z), (x + dx * 0.8, y + dy * 0.8, z + 4), 0.25, iron)
    mesh.cylinder(x, y, 2.2, 2.2, z + 4, z + 7.5, iron, (0.35, 0.25, 0.18), seg=12, cap=False)
    mesh.cone(x, y, 2.4, z + 7.5, z + 9, 2, seg=12)


def build_tower(houses, neon, x0, y0, x1, y1, H, color, rc, r, district):
    """A stepped art-deco / gothic tower: three setbacks, corner piers, and a crown: gothic spire, glowing art-deco
    bands, or statues and a water tank. Mesh materials: 0 facade, 1 roof, 2 trim, 3 iron."""
    houses.cur["lit"] = 0.3 + r.random() * 0.3
    w, d = x1 - x0, y1 - y0
    tiers = [(0.0, 0.55), (0.12, 0.80), (0.24, 0.92)]
    z = 0.0
    for inset, top in tiers:
        ix, iy = w * inset / 2, d * inset / 2
        zt = H * top
        houses.box(x0 + ix, y0 + iy, x1 - ix, y1 - iy, z, zt, 0, color, top=True, top_mat=2)
        for px, py in ((x0 + ix, y0 + iy), (x1 - ix, y0 + iy), (x0 + ix, y1 - iy), (x1 - ix, y1 - iy)):
            houses.box(px - 0.6, py - 0.6, px + 0.6, py + 0.6, z, zt + 2.0, 2, (0.5, 0.5, 0.55))
            houses.pyramid(px - 0.7, py - 0.7, px + 0.7, py + 0.7, zt + 2.0, zt + 3.5, 2, (0.5, 0.5, 0.55))
        z = zt
    ix, iy = w * 0.24 / 2, d * 0.24 / 2
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tx0, ty0, tx1, ty1 = x0 + ix, y0 + iy, x1 - ix, y1 - iy
    kind = r.choice(("spire", "deco", "statues"))
    col = r.choice(DISTRICT_NEON[district])
    if kind == "spire":
        houses.pyramid(tx0, ty0, tx1, ty1, z, z + min(w, d) * 1.1, 1, rc)
        top = z + min(w, d) * 1.1
        houses.cylinder(cx, cy, 0.12, 0.04, top, top + 6, 3, seg=4)
        neon.blob(cx, cy, top + 6, 0.35, 1.0, NEON_INDEX["red"])
        marker("blink", cx, cy, top + 6, (1.0, 0.1, 0.05), 0.6)
    elif kind == "deco":
        # Glowing stepped crown: neon bands round each step, a mast with a red light
        zz = z
        for k in range(3):
            sx, sy = (tx1 - tx0) * (0.85 - k * 0.2) / 2, (ty1 - ty0) * (0.85 - k * 0.2) / 2
            houses.box(cx - sx, cy - sy, cx + sx, cy + sy, zz, zz + 3.5, 0, color, top=True, top_mat=2)
            neon.box(cx - sx - 0.1, cy - sy - 0.1, cx + sx + 0.1, cy + sy + 0.1, zz + 3.2, zz + 3.6, NEON_INDEX[col], top=False)
            zz += 3.5
        houses.cylinder(cx, cy, 0.25, 0.08, zz, zz + 12, 3, seg=6)
        neon.blob(cx, cy, zz + 12, 0.4, 1.0, NEON_INDEX["red"])
        marker("blink", cx, cy, zz + 12, (1.0, 0.1, 0.05), 0.6)
        light(cx, cy - 4, zz, NEON[col], 6000, 1.0, anim="neon", size=1.6)
    else:
        houses.face([(tx0, ty0, z), (tx1, ty0, z), (tx1, ty1, z), (tx0, ty1, z)], 2, (0.5, 0.5, 0.55), 1.0)
        for px in (tx0 + 1.2, tx1 - 1.2):
            statue(neon, px, ty0 + 1.2, z, 1.5, STATUE)
        water_tank(houses, cx + (tx1 - tx0) * 0.15, cy + (ty1 - ty0) * 0.15, z, 3)
    # A vertical neon name down the south face of the lower block
    if r.random() < 0.6 and w > 8:
        word = r.choice(WORDS[district])
        zc = H * 0.3
        neon.box(cx - 1.2, y0 - 0.5, cx + 1.2, y0, zc - 0.5 * len(word) * 1.4, zc + 0.5 * len(word) * 1.4 + 0.6, 0, top=False)
        for k, ch in enumerate(word):
            text(ch, NEON_INDEX[col], cx, y0 - 0.55, zc + (len(word) / 2 - k - 0.5) * 1.4 + 0.3, 1.1, 1.6)
        light(cx, y0 - 3, zc, NEON[col], 2500, 1.0, anim="neon", size=1.3)


def shop_signs(neon, b, ground, x0, y0, x1, y1, h, rise, r):
    """Neon shop sign over the street door, and sometimes a lit billboard on the roof, both facing south."""
    cx0, cy0, cx1, cy1 = (int(round(v)) for v in b["rect"])
    N = len(ground)
    south = [ground[cy1][x] for x in range(cx0, cx1)] if cy1 < N else []
    faces_street = south and sum(g in "apy" for g in south) / len(south) > 0.5
    w = x1 - x0
    col = r.choice(DISTRICT_NEON[b["district"]])
    if faces_street and r.random() < 0.4 and w > 5:
        sw = min(w - 1.5, r.uniform(4.0, 7.5))
        sx = r.uniform(x0 + 0.5, x1 - 0.5 - sw)
        neon.box(sx, y0 - 0.35, sx + sw, y0, 3.4, 4.9, 0, top=False)
        text(r.choice(WORDS[b["district"]]), NEON_INDEX[col], sx + sw / 2, y0 - 0.4, 4.15, 1.0, sw - 0.6)
        light(sx + sw / 2, y0 - 2.5, 4.0, NEON[col], 1200, 0.6, anim="neon", size=1.0)
    if faces_street and r.random() < 0.12 and w > 9:
        bw = min(w - 2, 10.0)
        bx = (x0 + x1) / 2 - bw / 2
        zb = h + 0.6 + rise * 0.6
        by = y0 + (y1 - y0) * 0.3
        for px in (bx + 1, bx + bw - 1):
            neon.beam((px, by + 0.2, h), (px, by + 0.2, zb + 4.2), 0.3, 0)
        neon.box(bx, by - 0.3, bx + bw, by, zb, zb + 4.2, BILLBOARD, top=False)
        text(r.choice(WORDS[b["district"]]), INK, bx + bw / 2, by - 0.35, zb + 2.1, 2.2, bw - 1.0)
        light(bx + bw / 2, by - 3, zb + 2, (1.0, 0.95, 0.85), 3000, 1.0, anim="steady", size=1.2)


# ---------------------------------------------------------------------------------------------- Sketchfab buildings

MODEL_SHARE = 0.85      # share of house lots that get a real 3D building (prep_buildings.py library) instead of a box
# Models each district favours (weight x3); everything else can appear anywhere
PREFER = {"courthouse": {"longworth", "midrise", "nyc", "block", "apartment", "artdeco"},
          "foundry": {"factory", "brick", "row"}, "pier": {"brick", "row", "factory"}, "abbey": {"clocktower"}}
LANDMARK_MODELS = {"cathedral"}          # placed by build_landmarks only
LIB = {}


def load_library():
    """The prepared buildings (build/buildings.blend): {name: (mesh, info)}; their materials get snow on faces that
    pointed up before the shear (face attribute 'upz')."""
    path = os.path.join(BUILD, "buildings.blend")
    if LIB or not os.path.exists(path):
        return LIB
    info = json.load(open(os.path.join(BUILD, "buildings.json")))
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.meshes = [n for n in src.meshes if n in info]
    for me in dst.meshes:
        LIB[me.name] = (me, info[me.name])
    done = set()
    for me, _ in LIB.values():
        for mat in me.materials:
            if mat and mat.name not in done:
                add_snow(mat)
                done.add(mat.name)
    print(f"{len(LIB)} library buildings")
    return LIB


def add_snow(mat):
    """Mixes snow into an imported material where the face pointed up (roofs, ledges, cornices)."""
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return
    sock = bsdf.inputs["Base Color"]
    if sock.links:
        base = sock.links[0].from_socket
    else:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = sock.default_value
        base = rgb.outputs[0]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    up = attr(nt, "upz")
    cover = edge(nt, smooth(nt, up.outputs["Fac"], 0.45, 0.8), noise(nt, coord, 0.4, 3.0), 0.3)
    # Night: the photo textures are daylight; darken and cool them a little so they sit in the moonlit scene
    night = mul(nt, base, (0.95, 0.97, 1.05))
    nt.links.new(mix(nt, night, mul(nt, snow_color(nt, coord), (0.9, 0.92, 0.97)), cover), sock)
    # Lit windows: dark, grey-blue texture pixels (glass) on walls, a random third of them per 1.6 m patch, glow warm
    hsv = nt.nodes.new("ShaderNodeSeparateColor")
    hsv.mode = "HSV"
    nt.links.new(base, hsv.inputs[0])
    glass = math_node(nt, "MULTIPLY", math_node(nt, "LESS_THAN", hsv.outputs[2], 0.22), math_node(nt, "LESS_THAN", hsv.outputs[1], 0.35))
    patch = nt.nodes.new("ShaderNodeTexVoronoi")
    patch.inputs["Scale"].default_value = 0.6
    nt.links.new(coord.outputs["Object"], patch.inputs["Vector"])
    lit = math_node(nt, "GREATER_THAN", sep_r(nt, patch.outputs["Color"]), 0.74)
    wall = math_node(nt, "LESS_THAN", up.outputs["Fac"], 0.3)
    glow = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", glass, lit), wall)
    bsdf.inputs["Emission Color"].default_value = (*WINDOW_RGB, 1)
    nt.links.new(math_node(nt, "MULTIPLY", glow, 2.5), bsdf.inputs["Emission Strength"])
    mat.use_backface_culling = False


def sep_r(nt, color):
    s = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(color, s.inputs[0])
    return s.outputs[0]


def allowed_height(b, grid):
    """Tallest building (m) whose northward lean on this lot covers at most a quarter open cells; 18 m at least
    (a four-storey house, as the box houses were)."""
    x0, y0, x1, y1 = (int(round(v)) for v in b["rect"])
    for h in (60, 48, 40, 32, 26, 22):
        lean = math.ceil(h * SHEAR / 7.0)
        cells = [grid[y][x] for x in range(x0, x1) for y in range(max(0, y0 - lean), y0)]
        if not cells or sum(c == "." for c in cells) / len(cells) <= 0.25:
            return h
    return 18.0


def pick_model(w, d, max_h, district, r, exclude=()):
    """(name, (sx, sy, sz)) of a library building stretched to cover a w x d lot (m) exactly, or None. Blocked cells
    must look blocked, so the model fills the whole lot: each side may stretch 0.65-1.5x and the two sides may
    differ by 35 % at most; the height follows the smaller of the two and is squashed (to 0.7) under max_h."""
    best = []
    for name, (_, i) in LIB.items():
        if i["model"] in LANDMARK_MODELS or name in exclude:
            continue
        sx, sy = w / i["w"], d / i["d"]
        if not (0.65 <= sx <= 1.5 and 0.65 <= sy <= 1.5) or max(sx, sy) / min(sx, sy) > 1.35:
            continue
        s = min(sx, sy)
        zs = min(1.0, max_h / (i["h"] * s))
        if zs < 0.7:
            continue
        distort = max(sx, sy) / min(sx, sy)
        weight = (1 / distort) * (3.0 if i["model"] in PREFER.get(district, ()) else 1.0) * (0.3 if i["model"] == "brownstone" else 1.0)
        best.append((weight, name, (sx, sy, s * zs)))
    if not best:
        return None
    best.sort(reverse=True)
    top = best[:6]
    pick = r.choices(top, weights=[b[0] for b in top])[0]
    return pick[1], pick[2]


def place_model(name, scale, cx, front_y, filler):
    """A copy of a library building scaled by (sx, sy, sz), its front on the lot's south edge (y = front_y), sheared
    like the rest. A plain snowy core block goes inside: many game models are only a facade and a roof."""
    me0, i = LIB[name]
    sx, sy, sz = scale
    w, d, h = i["w"] * sx, i["d"] * sy, i["h"] * sz
    cy = front_y + d / 2
    me = me0.copy()
    me.transform(OBLIQUE @ Matrix.Translation((cx, cy, 0)) @ Matrix.Diagonal((sx, sy, sz, 1)))
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    filler.box(cx - w / 2 + 0.6, front_y + 0.8, cx + w / 2 - 0.6, front_y + d - 0.6, 0, h * 0.9, 2, (0.30, 0.30, 0.33))
    return w, d, h


def model_house(b, x0, y0, x1, y1, grid, r, filler):
    """Fills a house lot with 1-3 library buildings side by side along its long side; False if none fits."""
    if not LIB or r.random() > MODEL_SHARE:
        return False
    w, d = x1 - x0, y1 - y0
    max_h = allowed_height(b, grid)
    for k in (1, 2, 3):
        if w / k < 6:
            break
        picks = []
        for j in range(k):
            p = pick_model(w / k, d, max_h, b["district"], r, exclude={q[0] for q in picks})
            if not p:
                break
            picks.append(p)
        if len(picks) == k:
            for j, (name, scale) in enumerate(picks):
                place_model(name, scale, x0 + (j + 0.5) * w / k, y0, filler)
            return True
    return False


def build_city(L, m, rng):
    C = L["cell_m"]
    facade, roof = facade_material(), roof_material()
    trim = snowy("Trim", (0.45, 0.45, 0.5))
    metal = plain("Iron", (0.10, 0.10, 0.11), 0.5, 0.8)
    houses = Mesh("Houses")         # 0 facade, 1 roof, 2 trim (snowy stone), 3 iron
    neon = Mesh("Neon")             # 0 sign frame, 1.. neon colours, BILLBOARD, INK, STATUE
    nmats = neon_materials()
    towers = models = 0
    load_library()
    for i, b in enumerate(L["buildings"]):
        cx0, cy0, cx1, cy1 = b["rect"]
        x0, y1 = m(cx0, cy0)
        x1, y0 = m(cx1, cy1)
        x0, y0, x1, y1 = x0 + 0.4, y0 + 0.4, x1 - 0.4, y1 - 0.4      # a gap between houses
        r = random.Random(i)
        dist = DISTRICT[b["district"]]
        color = dist["walls"][b["style"] % len(dist["walls"])]
        rc = dist["roof"]
        houses.cur = {"lit": b["lit"], "seed": r.random()}
        floors = 2 + b["floors"] % 3
        h = floors * FLOOR + 1.0
        w, d = x1 - x0, y1 - y0
        style = b["style"]
        H = tower_height(b, L["grid"], r)
        if H:
            build_tower(houses, neon, x0, y0, x1, y1, H, color, rc, r, b["district"])
            towers += 1
            continue
        if model_house(b, x0, y0, x1, y1, L["grid"], r, houses):
            models += 1
            shop_signs(neon, b, L["ground"], x0, y0, x1, y1, h, 3.0, r)
            continue
        houses.box(x0, y0, x1, y1, 0, h, 0, color, top=False)
        houses.box(x0 - 0.2, y0 - 0.2, x1 + 0.2, y1 + 0.2, h, h + 0.6, 2, (0.5, 0.5, 0.55), top=False)   # cornice
        if b["district"] == "foundry" and style < 3:
            # Sawtooth factory roof and a tall brick chimney
            n = max(1, int(w / 6))
            for k in range(n):
                sx0, sx1 = x0 + k * w / n, x0 + (k + 1) * w / n
                houses.face([(sx0, y0, h), (sx1, y0, h), (sx1, y1, h), (sx0, y1, h)], 1, rc, 1.0)
                houses.face([(sx0, y0, h), (sx0, y1, h), (sx0 + (sx1 - sx0) * 0.3, y1, h + 3), (sx0 + (sx1 - sx0) * 0.3, y0, h + 3)],
                            0, color, 0.0, [(0, 0), (d, 0), (d, 3), (0, 3)])
                houses.face([(sx0 + (sx1 - sx0) * 0.3, y0, h + 3), (sx0 + (sx1 - sx0) * 0.3, y1, h + 3), (sx1, y1, h), (sx1, y0, h)],
                            1, rc, 0.7)
            if style == 0:
                cx, cy = r.uniform(x0 + 2, x1 - 2), r.uniform(y0 + 2, y1 - 2)
                houses.cylinder(cx, cy, 1.4, 1.0, h, h + 22, 0, color, seg=10, cap=False)
                houses.cylinder(cx, cy, 1.25, 1.25, h + 22, h + 23, 2, (0.3, 0.3, 0.32), seg=10)
        elif b["district"] == "pier" and style < 3:
            # Warehouse: low-pitched corrugated roof
            houses.gable_roof(x0, y0, x1, y1, h + 0.6, min(w, d) * 0.18, 1, (0.30, 0.32, 0.34), 0, color)
        elif b["district"] == "courthouse" and style < 2:
            # Mansard roof with a balustrade
            inset = min(w, d) * 0.22
            houses.face([(x0, y0, h + 0.6), (x1, y0, h + 0.6), (x1 - inset, y0 + inset, h + 4), (x0 + inset, y0 + inset, h + 4)], 1, rc)
            houses.face([(x1, y0, h + 0.6), (x1, y1, h + 0.6), (x1 - inset, y1 - inset, h + 4), (x1 - inset, y0 + inset, h + 4)], 1, rc)
            houses.face([(x1, y1, h + 0.6), (x0, y1, h + 0.6), (x0 + inset, y1 - inset, h + 4), (x1 - inset, y1 - inset, h + 4)], 1, rc)
            houses.face([(x0, y1, h + 0.6), (x0, y0, h + 0.6), (x0 + inset, y0 + inset, h + 4), (x0 + inset, y1 - inset, h + 4)], 1, rc)
            houses.face([(x0 + inset, y0 + inset, h + 4), (x1 - inset, y0 + inset, h + 4), (x1 - inset, y1 - inset, h + 4),
                         (x0 + inset, y1 - inset, h + 4)], 1, rc, 1.0)
        else:
            # Gothic: a steep pitched roof, gables, pinnacles on the corners, dormers
            rh = min(w, d) * 0.62
            houses.gable_roof(x0, y0, x1, y1, h + 0.6, rh, 1, rc, 0, color)
            if style in (3, 5, 6) or b["district"] == "abbey":
                for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                    houses.box(px - 0.5, py - 0.5, px + 0.5, py + 0.5, h, h + 3.2, 2, (0.5, 0.5, 0.55))
                    houses.pyramid(px - 0.6, py - 0.6, px + 0.6, py + 0.6, h + 3.2, h + 5.5, 2, (0.5, 0.5, 0.55))
            if style == 4 and w > 9:
                # A little bell turret on the ridge
                tx, ty = (x0 + x1) / 2, (y0 + y1) / 2
                houses.box(tx - 1.3, ty - 1.3, tx + 1.3, ty + 1.3, h + rh * 0.7, h + rh + 3, 0, color, top=False)
                houses.pyramid(tx - 1.6, ty - 1.6, tx + 1.6, ty + 1.6, h + rh + 3, h + rh + 9, 1, rc)
        for _ in range(r.randint(1, 2)):                                   # chimneys
            cx, cy = r.uniform(x0 + 1.2, x1 - 1.2), r.uniform(y0 + 1.2, y1 - 1.2)
            houses.box(cx - 0.5, cy - 0.5, cx + 0.5, cy + 0.5, h, h + min(w, d) * 0.5 + 1.5, 2, (0.42, 0.36, 0.34))
        # Fire escapes on some south walls (the side the camera sees)
        if style in (1, 2) and w > 7:
            fx = r.uniform(x0 + 1, x1 - 4)
            for f in range(1, floors):
                houses.box(fx, y0 - 1.0, fx + 3, y0, f * FLOOR, f * FLOOR + 0.12, 3, (0.1, 0.1, 0.1))
        if b["district"] == "foundry" and style < 3:
            rise = 3.0
        elif b["district"] == "pier" and style < 3:
            rise = min(w, d) * 0.18
        elif b["district"] == "courthouse" and style < 2:
            rise = 3.4
        else:
            rise = min(w, d) * 0.62
        shop_signs(neon, b, L["ground"], x0, y0, x1, y1, h, rise, r)
        if rise < 4 and r.random() < 0.15:
            water_tank(houses, r.uniform(x0 + 3, x1 - 3), r.uniform(y0 + 3, y1 - 3), h + 0.6 + rise, 3)
    houses.finish([facade, roof, trim, metal])
    neon.finish(nmats)
    make_texts(nmats)
    print(f"{towers} towers, {models} lots with 3D buildings")


def build_wall(L, m):
    """The prison wall round the map: 12 m of concrete with a walkway, watchtowers with searchlights, sealed gates."""
    C = L["cell_m"]
    N = L["cells"][0]
    S = N * C
    t = L["wall"] * C
    concrete = snowy("Wall concrete", (0.52, 0.52, 0.56), "Concrete034", 4.0)
    rust = plain("Gate steel", (0.24, 0.13, 0.09), 0.6, 0.5)
    glass = plain("Tower glass", (0.05, 0.05, 0.05), 0.2, 0.0, emission=(1.0, 0.85, 0.6), strength=3.0)
    wire = plain("Wire", (0.08, 0.08, 0.08), 0.5, 0.8)
    w = Mesh("Wall")      # 0 concrete, 1 gate steel, 2 tower glass, 3 wire
    H = 12.0
    for x0, y0, x1, y1 in ((0, S - t, S, S), (0, 0, S, t), (0, 0, t, S), (S - t, 0, S, S)):
        w.box(x0, y0, x1, y1, 0, H, 0, (1, 1, 1), top=False)
        w.face([(x0, y0, H), (x1, y0, H), (x1, y1, H), (x0, y1, H)], 0, (1, 1, 1), 1.0)
    # Razor wire coils on the inner edge
    for k in range(0, int(S), 3):
        for (x, y) in ((k, S - t - 0.4), (k, t + 0.4), (t + 0.4, k), (S - t - 0.4, k)):
            w.cylinder(x, y, 0.35, 0.35, H - 0.5, H + 0.3, 3, seg=5, cap=False)
    # Watchtowers: concrete shaft, glazed cabin, conical roof, a searchlight raking the city
    for tx, ty in L["landmarks"]["towers"]:
        x, y = m(tx, ty)
        w.box(x - 4, y - 4, x + 4, y + 4, 0, 20, 0)
        w.box(x - 5, y - 5, x + 5, y + 5, 20, 21, 0)
        w.box(x - 4.4, y - 4.4, x + 4.4, y + 4.4, 21, 24.5, 2, top=False)
        w.pyramid(x - 5.5, y - 5.5, x + 5.5, y + 5.5, 24.5, 28.5, 0)
        cx, cy = m(64, 64)
        dx, dy = cx - x, cy - y
        dd = math.hypot(dx, dy)
        reach = 38 + (int(tx * 7 + ty * 3) % 20)
        side = 18 if int(tx + ty) % 2 else -18
        light(x + dx / dd * 5, y + dy / dd * 5, 26, (0.85, 0.92, 1.0), 1.2e6, 0.2, "SPOT",
              (x + dx / dd * reach + dy / dd * side, y + dy / dd * reach - dx / dd * side, 0), 14, anim="search", size=2.4)
    # Sealed gates: steel doors welded shut, concrete blocks in front
    for gx, gy in L["landmarks"]["gates"]:
        x, y = m(gx, gy)
        horizontal = abs(gy - 1.5) < 2 or abs(gy - (N - 1.5)) < 2
        if horizontal:
            w.box(x - 26, y - t, x + 26, y + t, 0, 16, 0)
            w.box(x - 14, y - t - 0.3, x + 14, y + t + 0.3, 0, 10, 1)
        else:
            w.box(x - t, y - 26, x + t, y + 26, 0, 16, 0)
            w.box(x - t - 0.3, y - 14, x + t + 0.3, y + 14, 0, 10, 1)
        light(x, y, 14, LAMP_RGB, 6000, 0.4)
    w.finish([concrete, rust, glass, wire])


def build_landmarks(L, m, rng):
    stone = snowy("Landmark stone", (0.62, 0.60, 0.58), "Bricks076C", 2.5)
    dark = snowy("Dark stone", (0.36, 0.35, 0.38), "Bricks076C", 2.5)
    brick = snowy("Brick", (0.50, 0.28, 0.22), "Bricks076C", 2.0)
    slate = roof_material()
    iron = plain("Iron2", (0.10, 0.10, 0.11), 0.5, 0.8)
    clock = plain("Clock face", (0.9, 0.85, 0.7), 0.4, emission=(1.0, 0.86, 0.55), strength=6.0)
    rose = plain("Rose window", (0.3, 0.1, 0.1), 0.4, emission=(1.0, 0.45, 0.25), strength=4.0)
    furnace = plain("Furnace glow", (0.5, 0.2, 0.05), 0.5, emission=(1.0, 0.42, 0.12), strength=12.0)
    lm = Mesh("Landmarks")   # 0 stone, 1 dark stone, 2 brick, 3 roof, 4 iron, 5 clock, 6 rose window, 7 furnace
    sx, sy, sr = L["landmarks"]["spire"]
    x, y = m(sx, sy)
    # The Warden's Spire: a gothic clock tower on a stepped plinth, glowing clock faces, a needle spire
    lm.cur = {"lit": 0.0, "seed": 0.0}
    lm.box(x - 15, y - 15, x + 15, y + 15, 0, 1.2, 0)
    lm.box(x - 11, y - 11, x + 11, y + 11, 1.2, 9, 1, (1, 1, 1), top_mat=0)
    for px, py in ((-1, -1), (1, -1), (-1, 1), (1, 1)):                       # corner buttresses
        lm.box(x + px * 11 - 2, y + py * 11 - 2, x + px * 11 + 2, y + py * 11 + 2, 0, 16, 1)
        lm.pyramid(x + px * 11 - 2.3, y + py * 11 - 2.3, x + px * 11 + 2.3, y + py * 11 + 2.3, 16, 21, 0)
    lm.box(x - 7, y - 7, x + 7, y + 7, 9, 34, 1, top=False)
    lm.box(x - 7.6, y - 7.6, x + 7.6, y + 7.6, 34, 35, 0, top=False)
    lm.box(x - 7, y - 7, x + 7, y + 7, 35, 42, 1, top=False)
    for a, b in (((x - 4, y - 7.05), (x + 4, y - 7.05)), ((x + 7.05, y - 4), (x + 7.05, y + 4)),
                 ((x + 4, y + 7.05), (x - 4, y + 7.05)), ((x - 7.05, y + 4), (x - 7.05, y - 4))):
        lm.wall(a, b, 35.5, 41.5, 5, (1, 1, 1))                                 # clock faces
    for px, py in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        lm.box(x + px * 6.5 - 0.8, y + py * 6.5 - 0.8, x + px * 6.5 + 0.8, y + py * 6.5 + 0.8, 42, 46, 0)
        lm.pyramid(x + px * 6.5 - 1, y + py * 6.5 - 1, x + px * 6.5 + 1, y + py * 6.5 + 1, 46, 50, 0)
    lm.pyramid(x - 7, y - 7, x + 7, y + 7, 42, 70, 3, (0.2, 0.22, 0.26))
    lm.cylinder(x, y, 0.15, 0.05, 70, 76, 4, seg=4)
    light(x, y - 9, 38, (1.0, 0.85, 0.55), 40000, 2.0, anim="steady", size=1.8)
    for k in range(4):                                                      # lamps round the plinth
        a = math.pi / 4 + k * math.pi / 2
        light(x + math.cos(a) * 17, y + math.sin(a) * 17, 4, LAMP_RGB, 3000, 0.3)

    for x0c, y0c, x1c, y1c, dist in L["landmarks"]["district_landmarks"]:
        ax0, ay1 = m(x0c, y0c)
        ax1, ay0 = m(x1c, y1c)
        cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
        w = ax1 - ax0
        if dist == "foundry":
            # Blast furnace with a glowing tap, two tall stacks, a gas holder
            lm.box(ax0, ay0, ax0 + w * 0.55, ay1, 0, 14, 2, (1, 1, 1))
            lm.cylinder(cx + 8, cy - 6, 6, 4.5, 0, 26, 4, seg=16)
            lm.cylinder(cx + 8, cy - 6, 4.6, 4.6, 26, 27, 7, seg=16)
            for k in range(2):
                lm.cylinder(ax0 + 6 + k * 9, ay1 - 6, 2.0, 1.4, 14, 50, 2, seg=12, cap=False)
                lm.cylinder(ax0 + 6 + k * 9, ay1 - 6, 1.5, 1.5, 50, 51, 4, seg=12)
            lm.cylinder(cx + 10, cy + 12, 9, 9, 0, 16, 4, seg=24)
            light(cx + 8, cy - 14, 6, (1.0, 0.45, 0.15), 60000, 2.0, anim="fire", size=2.5)
        elif dist == "abbey":
            # The gothic cathedral (library model) when there is one, else the asylum chapel; a graveyard round it
            lm.cur = {"lit": 0.25, "seed": 0.3}
            cath = next((n for n, (_, i) in LIB.items() if i["model"] == "cathedral"), None)
            if cath:
                i = LIB[cath][1]
                s = min(w / i["w"], (ay1 - ay0) / i["d"])
                place_model(cath, (s, s, s), cx, ay0, lm)
            else:
                lm.box(ax0 + 4, cy - 7, ax1 - 4, cy + 7, 0, 14, 1, top=False)
                lm.gable_roof(ax0 + 4, cy - 7, ax1 - 4, cy + 7, 14, 10, 3, (0.18, 0.18, 0.22), 1, (1, 1, 1))
                lm.box(ax0 + 4, cy - 4, ax0 + 12, cy + 4, 0, 30, 1, top=False)
                lm.pyramid(ax0 + 3.5, cy - 4.5, ax0 + 12.5, cy + 4.5, 30, 46, 3, (0.18, 0.18, 0.22))
                lm.cylinder(cx + 6, cy - 7.05, 3.2, 3.2, 6, 6.1, 6, seg=16)
                lm.face([(cx + 6 + 3 * math.cos(2 * math.pi * k / 16), cy - 7.1, 8 + 3 * math.sin(2 * math.pi * k / 16))
                         for k in range(16)], 6, (1, 1, 1), 0.0)
            yx, yy = L["landmarks"]["yards"][[d[3] for d in L["landmarks"]["yards"]].index("abbey")][:2]
            gx, gy = m(yx, yy)
            for _ in range(70):
                a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(14, 55)
                px, py = gx + math.cos(a) * rr, gy + math.sin(a) * rr
                if ax0 - 2 < px < ax1 + 2 and ay0 - 2 < py < ay1 + 2:
                    continue
                lm.box(px - 0.5, py - 0.15, px + 0.5, py + 0.15, 0, rng.uniform(0.9, 1.6), 1)
            light(cx + 6, cy - 12, 6, (1.0, 0.5, 0.3), 20000, 2.0, anim="steady", size=1.5)
        elif dist == "pier":
            # Ferry terminal shed, a gantry crane, stacks of crates
            lm.box(ax0, ay0, ax1, ay0 + w * 0.45, 0, 9, 2, (0.5, 0.55, 0.6))
            lm.gable_roof(ax0, ay0, ax1, ay0 + w * 0.45, 9, 3, 3, (0.30, 0.32, 0.34), 2, (0.5, 0.55, 0.6))
            for px in (ax0 + 4, ax1 - 4):
                for py in (ay1 - 4, ay1 - 18):
                    lm.box(px - 0.6, py - 0.6, px + 0.6, py + 0.6, 0, 26, 4, (0.8, 0.5, 0.1))
            lm.box(ax0 + 3, ay1 - 19, ax1 - 3, ay1 - 3, 26, 28, 4, (0.8, 0.5, 0.1), top=True)
            for _ in range(14):
                px, py = rng.uniform(ax0 + 2, ax1 - 8), rng.uniform(ay1 - 16, ay1 - 6)
                lm.box(px, py, px + 6, py + 2.4, 0, 2.6 * rng.randint(1, 2), 4,
                       rng.choice(((0.5, 0.15, 0.1), (0.15, 0.25, 0.4), (0.4, 0.4, 0.15))))
            light(cx, cy, 20, (0.8, 0.9, 1.0), 25000, 1.0)
        else:
            # Courthouse: portico of columns, pediment, a green copper dome
            lm.cur = {"lit": 0.5, "seed": 0.7}
            lm.box(ax0 + 3, ay0 + 3, ax1 - 3, ay1 - 3, 0, 16, 0, top=False)
            lm.face([(ax0 + 3, ay0 + 3, 16), (ax1 - 3, ay0 + 3, 16), (ax1 - 3, ay1 - 3, 16), (ax0 + 3, ay1 - 3, 16)], 0)
            for k in range(8):
                lm.cylinder(ax0 + 6 + k * (w - 12) / 7, ay0 + 1, 0.8, 0.7, 1, 15, 0, seg=10)
            lm.box(ax0 + 3, ay0 - 0.5, ax1 - 3, ay0 + 3, 15, 17, 0)
            lm.face([(ax0 + 3, ay0 - 0.5, 17), (ax1 - 3, ay0 - 0.5, 17), (cx, ay0 - 0.5, 22)], 0, (1, 1, 1), 0.0)
            lm.cylinder(cx, cy + 3, 9, 9, 16, 22, 0, seg=24)
            for j in range(6):
                t0, t1 = j / 6 * math.pi / 2, (j + 1) / 6 * math.pi / 2
                lm.cylinder(cx, cy + 3, 9 * math.cos(t0), 9 * math.cos(t1), 22 + 9 * math.sin(t0), 22 + 9 * math.sin(t1), 3,
                            (0.25, 0.45, 0.40), seg=24, cap=(j == 5))
            for k in range(2):
                light(ax0 + 8 + k * (w - 16), ay0 - 4, 5, LAMP_RGB, 4000, 0.3)
    lm.finish([stone, dark, brick, slate, iron, clock, rose, furnace])


def build_details(L, m, rng):
    """Bridges, street lamps, fire barrels, snow banks, snowed-in cars, quay walls."""
    C = L["cell_m"]
    N = L["cells"][0]
    grid, ground = L["grid"], L["ground"]
    stone = snowy("Bridge stone", (0.48, 0.48, 0.52), "Concrete034", 3.0)
    road = plain("Bridge road", (0.28, 0.29, 0.32), 0.6, tex_name="Asphalt012", repeat=6.0)
    iron = plain("Lamp iron", (0.06, 0.06, 0.07), 0.5, 0.7)
    bulb = plain("Lamp glow", (1, 0.8, 0.5), 0.3, emission=LAMP_RGB, strength=30.0)
    fire = plain("Fire", (1, 0.5, 0.1), 0.5, emission=(1.0, 0.45, 0.1), strength=25.0)
    snowm = snowy("Snow bank", (0.8, 0.82, 0.86), "Snow006", 3.0)
    car = snowy("Car", (0.18, 0.12, 0.10), "Concrete034", 2.0)
    d = Mesh("Details")      # 0 stone, 1 road, 2 iron, 3 bulb, 4 fire, 5 snow, 6 car
    # Bridges over the arms: deck, parapets, lamp posts at both ends
    for b in L["bridges"]:
        if b["kind"] == "arm":
            cx0, cy0, cx1, cy1 = b["rect"]
            x0, y1 = m(cx0, cy0)
            x1, y0 = m(cx1, cy1)
            along_x = (x1 - x0) > (y1 - y0) * 1.0 and (cy1 - cy0) < (cx1 - cx0)
            d.box(x0, y0, x1, y1, 0.4, 1.0, 1, top=True)
            if along_x:
                d.box(x0, y0 - 0.7, x1, y0, 0.4, 2.0, 0)
                d.box(x0, y1, x1, y1 + 0.7, 0.4, 2.0, 0)
            else:
                d.box(x0 - 0.7, y0, x0, y1, 0.4, 2.0, 0)
                d.box(x1, y0, x1 + 0.7, y1, 0.4, 2.0, 0)
            # Steel arch truss over each side: arch ribs, hangers down to the deck, wind bracing on top
            span = (x0, x1) if along_x else (y0, y1)
            sides = (y0 - 0.35, y1 + 0.35) if along_x else (x0 - 0.35, x1 + 0.35)
            n = 12

            def pt(t, side, z):
                s = span[0] + (span[1] - span[0]) * t
                return (s, side, z) if along_x else (side, s, z)
            for side in sides:
                for k in range(n):
                    t0, t1 = k / n, (k + 1) / n
                    z0, z1 = 1.0 + 10 * math.sin(math.pi * t0), 1.0 + 10 * math.sin(math.pi * t1)
                    d.beam(pt(t0, side, z0), pt(t1, side, z1), 0.7, 2)
                    if 0 < k:
                        d.beam(pt(t0, side, z0), pt(t0, side, 1.0), 0.18, 2)
                        d.beam(pt(t0, side, z0), pt(t1, side, 1.0), 0.12, 2)
            for k in range(3, n - 2):
                tk = k / n
                zk = 1.0 + 10 * math.sin(math.pi * tk)
                d.beam(pt(tk, sides[0], zk), pt(tk, sides[1], zk), 0.3, 2)
            apex = pt(0.5, sum(sides) / 2, 11.3)
            d.blob(*apex, 0.3, 1.0, 3)
            light(*apex, (1.0, 0.1, 0.05), 400, 0.2, anim="blink", size=0.6)
            for px, py in ((x0, y0), (x1, y1)):
                d.cylinder(px, py, 0.15, 0.12, 2, 7, 2, seg=6, cap=False)
                d.blob(px, py, 7.2, 0.45, 1.0, 3)
                light(px, py, 7, LAMP_RGB, 5000, 0.2)
        else:
            cx, cy = m(*b["centre"])
            a = -b["angle"]                              # cell y runs down, metres y runs up
            ln, wd = b["length"] * C / 2, b["width"] * C / 2
            ca, sa = math.cos(a), math.sin(a)

            def p(u, v, z):
                return (cx + ca * u - sa * v, cy + sa * u + ca * v, z)
            for z0, z1, v0, v1, mat in ((0.4, 1.0, -wd, wd, 1), (0.4, 2.0, -wd - 0.7, -wd, 0), (0.4, 2.0, wd, wd + 0.7, 0)):
                d.face([p(-ln, v0, z1), p(ln, v0, z1), p(ln, v1, z1), p(-ln, v1, z1)], mat)
                d.face([p(-ln, v0, z0), p(ln, v0, z0), p(ln, v0, z1), p(-ln, v0, z1)], mat, (1, 1, 1), 0.0)
                d.face([p(ln, v1, z0), p(-ln, v1, z0), p(-ln, v1, z1), p(ln, v1, z1)], mat, (1, 1, 1), 0.0)
            for u in (-ln, ln):
                for v in (-wd - 0.35, wd + 0.35):
                    q = p(u, v, 0)
                    d.cylinder(q[0], q[1], 0.15, 0.12, 2, 6, 2, seg=6, cap=False)
                    d.blob(q[0], q[1], 6.2, 0.4, 1.0, 3)
                    light(q[0], q[1], 6, LAMP_RGB, 3500, 0.2)
    # Street lamps: along the streets, on cells next to buildings, every few cells
    for y in range(1, N - 1):
        for x in range(1, N - 1):
            if ground[y][x] != "a" or grid[y][x] != ".":
                continue
            if (x * 7 + y * 13) % 5:
                continue
            near_house = any(grid[y + dy][x + dx] == "#" for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if not near_house:
                continue
            px, py = m(x + 0.5, y + 0.5)
            d.cylinder(px, py, 0.14, 0.1, 0, 6, 2, seg=6, cap=False)
            d.box(px - 0.05, py - 0.05, px + 0.9, py + 0.05, 5.8, 6.0, 2)
            d.blob(px + 0.9, py, 5.7, 0.35, 0.8, 3)
            light(px + 0.9, py, 5.6, LAMP_RGB, 4500, 0.2)
    # Fire barrels in the corner yards, base lots and alleys, with people's junk round them
    barrels = 0
    for _ in range(4000):
        x, y = rng.randrange(N), rng.randrange(N)
        if grid[y][x] != "." or ground[y][x] not in "yc" or barrels >= 90:
            continue
        if not any(grid[y + dy][x + dx] == "#" for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= x + dx < N and 0 <= y + dy < N):
            continue
        px, py = m(x + rng.random(), y + rng.random())
        d.cylinder(px, py, 0.4, 0.4, 0, 1.0, 2, seg=8, cap=False)
        d.blob(px, py, 1.05, 0.38, 0.5, 4)
        light(px, py, 1.6, (1.0, 0.45, 0.12), 900, 0.3, anim="fire", size=0.9)
        barrels += 1
    # Snow banks along the ploughed streets, snowed-in cars
    for y in range(N):
        for x in range(N):
            if ground[y][x] != "a" or grid[y][x] != ".":
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= x + dx < N and 0 <= y + dy < N and ground[y + dy][x + dx] not in "aq" and grid[y + dy][x + dx] == ".":
                    if rng.random() < 0.5:
                        px, py = m(x + 0.5 + dx * 0.45, y + 0.5 + dy * 0.45)
                        d.blob(px, py, 0, rng.uniform(1.0, 1.8), 0.35, 5, (1, 1, 1), rng)
    for _ in range(70):
        x, y = rng.randrange(N), rng.randrange(N)
        if ground[y][x] != "a" or grid[y][x] != ".":
            continue
        cx, cy = m(x + rng.random(), y + rng.random())
        a = rng.choice((0, math.pi / 2)) + rng.uniform(-0.3, 0.3)
        ln, wd = rng.uniform(4.0, 5.2), 1.8
        ca, sa = math.cos(a), math.sin(a)
        corners = [(cx + ca * u - sa * v, cy + sa * u + ca * v) for u, v in ((-ln / 2, -wd / 2), (ln / 2, -wd / 2), (ln / 2, wd / 2), (-ln / 2, wd / 2))]
        for z0, z1, s in ((0.3, 1.0, 1.0), (1.0, 1.6, 0.6)):
            pts = [(cx + (qx - cx) * s, cy + (qy - cy) * s) for qx, qy in corners]
            for i in range(4):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % 4]
                d.face([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], 6, (1, 1, 1), 0.0)
            d.face([(qx, qy, z1) for qx, qy in pts], 6, (1, 1, 1), 1.0)
    # Quay walls round the canal ring: two round stone walls, open where the bridges cross
    R0, R1 = L["ring"]
    cx, cy = m(N / 2, N / 2)
    seg = 160
    for rad, out in ((R0 * C, -1), (R1 * C, 1)):
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            am = (a0 + a1) / 2
            if min(abs((math.degrees(am) - 45) % 90 - 45), 90) < (3.0 if out < 0 else 2.4) * 180 / math.pi / (rad / C):
                continue                                                # a bridge crosses here (on the diagonals)
            p0 = (cx + math.cos(a0) * rad, cy + math.sin(a0) * rad)
            p1 = (cx + math.cos(a1) * rad, cy + math.sin(a1) * rad)
            q0 = (cx + math.cos(a0) * (rad + out * 0.7), cy + math.sin(a0) * (rad + out * 0.7))
            q1 = (cx + math.cos(a1) * (rad + out * 0.7), cy + math.sin(a1) * (rad + out * 0.7))
            d.face([(p0[0], p0[1], -1.5), (p1[0], p1[1], -1.5), (p1[0], p1[1], 0.9), (p0[0], p0[1], 0.9)], 0, (1, 1, 1), 0.0)
            d.face([(p1[0], p1[1], -1.5), (p0[0], p0[1], -1.5), (p0[0], p0[1], 0.9), (p1[0], p1[1], 0.9)], 0, (1, 1, 1), 0.0)
            d.face([(p0[0], p0[1], 0.9), (p1[0], p1[1], 0.9), (q1[0], q1[1], 0.9), (q0[0], q0[1], 0.9)], 0, (1, 1, 1), 1.0)
    # Quay walls along the straight arms: the cells next to water get a low stone parapet on the water side
    for y in range(N):
        for x in range(N):
            if grid[y][x] != "~" or math.hypot(x + 0.5 - N / 2, y + 0.5 - N / 2) < R1 + 1.5:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx_, ny_ = x + dx, y + dy
                if 0 <= nx_ < N and 0 <= ny_ < N and ground[ny_][nx_] == "q":
                    ax, ay = m(x + 0.5 + dx * 0.5 - abs(dy) * 0.5, y + 0.5 + dy * 0.5 - abs(dx) * 0.5)
                    bx, by = m(x + 0.5 + dx * 0.5 + abs(dy) * 0.5, y + 0.5 + dy * 0.5 + abs(dx) * 0.5)
                    d.box(min(ax, bx) - 0.3, min(ay, by) - 0.3, max(ax, bx) + 0.3, max(ay, by) + 0.3, -1.5, 0.9, 0)
    d.finish([stone, road, iron, bulb, fire, snowm, car])


def build_viaducts(L, m, rng):
    """Elevated railway: a steel viaduct on pillars round the ring road (radius 31 cells, clear of every base lot),
    crossing the four canal arms on truss spans, and four spurs along the diagonal avenues out to a station in each
    corner yard. Two trains with lit windows. Decoration only: the cells below stay what the layout says."""
    C = L["cell_m"]
    N = L["cells"][0]
    grid = L["grid"]
    iron = snowy("Viaduct iron", (0.10, 0.10, 0.11), "steel", 2.0)
    deck_m = snowy("Viaduct deck", (0.20, 0.18, 0.17), "Asphalt012", 4.0)
    car_m = plain("Train", (0.16, 0.20, 0.22), 0.5, 0.4)
    win_m = plain("Train windows", (1, 0.8, 0.5), 0.4, emission=(1.0, 0.75, 0.4), strength=10.0)
    v = Mesh("Viaducts")     # 0 iron, 1 deck, 2 train, 3 train windows
    Z = 14.0
    HW = 3.0                 # half width of the deck
    cx, cy = m(N / 2, N / 2)

    def cell(p):
        x, y = p[0] / C, N - p[1] / C
        return grid[min(N - 1, max(0, int(y)))][min(N - 1, max(0, int(x)))]

    def frame(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(dx, dy)
        return dx / ln, dy / ln, -dy / ln, dx / ln, ln

    def segment(p, q, k):
        ux, uy, nx, ny, ln = frame(p, q)
        a = [(p[0] + nx * s * HW, p[1] + ny * s * HW) for s in (-1, 1)]
        b = [(q[0] + nx * s * HW, q[1] + ny * s * HW) for s in (-1, 1)]
        v.face([(*a[0], Z), (*b[0], Z), (*b[1], Z), (*a[1], Z)], 1)
        v.face([(*a[0], Z - 1.2), (*b[0], Z - 1.2), (*b[0], Z), (*a[0], Z)], 0, (1, 1, 1), 0.0)
        v.face([(*b[1], Z - 1.2), (*a[1], Z - 1.2), (*a[1], Z), (*b[1], Z)], 0, (1, 1, 1), 0.0)
        for s in (0, 1):
            v.beam((*a[s], Z + 2.4), (*b[s], Z + 2.4), 0.35, 0)
            v.beam((*a[s], Z), (*a[s], Z + 2.4), 0.22, 0)
            v.beam((*a[s], Z if k % 2 else Z + 2.4), (*b[s], Z + 2.4 if k % 2 else Z), 0.16, 0)

    def pillar(p, q, k):
        if cell(p) == "~":
            return
        ux, uy, nx, ny, ln = frame(p, q)
        for s in (-2.4, 2.4):
            v.beam((p[0] + nx * s, p[1] + ny * s, 0), (p[0] + nx * s, p[1] + ny * s, Z - 1.2), 0.7, 0)
        v.beam((p[0] - nx * 2.6, p[1] - ny * 2.6, Z - 2.2), (p[0] + nx * 2.6, p[1] + ny * 2.6, Z - 2.2), 0.5, 0)
        v.beam((p[0] - nx * 2.4, p[1] - ny * 2.4, 3.0), (p[0] + nx * 2.4, p[1] + ny * 2.4, Z - 2.4), 0.2, 0)
        if k % 2 == 0:
            light(p[0], p[1], Z - 1.8, LAMP_RGB, 1800, 0.3)

    def train(pts, start, cars=4):
        """Cars along the polyline pts, from segment `start`."""
        for c in range(cars):
            p, q = pts[start + c], pts[start + c + 1]
            ux, uy, nx, ny, ln = frame(p, q)
            mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            hl, hw = min(ln / 2 - 0.5, 6.0), 1.5
            corners = [(mid[0] + ux * a + nx * b, mid[1] + uy * a + ny * b) for a, b in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]
            for i in range(4):
                (ax, ay), (bx, by) = corners[i], corners[(i + 1) % 4]
                v.face([(ax, ay, Z + 0.3), (bx, by, Z + 0.3), (bx, by, Z + 3.4), (ax, ay, Z + 3.4)], 2, (1, 1, 1), 0.0)
                # A strip of lit windows on each long side
                if i in (0, 2):
                    o = (nx * (-0.06 if i == 0 else 0.06), ny * (-0.06 if i == 0 else 0.06))
                    a2 = (ax + (bx - ax) * 0.08 + o[0], ay + (by - ay) * 0.08 + o[1])
                    b2 = (ax + (bx - ax) * 0.92 + o[0], ay + (by - ay) * 0.92 + o[1])
                    v.face([(*a2, Z + 1.6), (*b2, Z + 1.6), (*b2, Z + 2.5), (*a2, Z + 2.5)], 3, (1, 1, 1), 0.0)
            v.face([(x, y, Z + 3.4) for x, y in corners], 2, (1, 1, 1), 1.0)
        p = pts[start + cars // 2]
        light(p[0], p[1], Z + 2.0, (1.0, 0.75, 0.4), 2500, 1.0, anim=None)

    # The ring, with a pillar every other segment (about 14 m)
    R = 31 * C
    n = 96
    ring = [(cx + R * math.cos(2 * math.pi * i / n), cy + R * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]
    for i in range(n):
        segment(ring[i], ring[i + 1], i)
        if i % 2 == 0:
            pillar(ring[i], ring[i + 1], i // 2)
    train(ring, 5)
    train(ring, 55)
    # Diagonal spurs to the corner-yard stations: platform, canopy, buffer stop
    for k in range(4):
        a = math.radians(45 + 90 * k)
        r0, r1 = 31 * C, 56 * C
        steps = 13
        spur = [(cx + math.cos(a) * (r0 + (r1 - r0) * j / steps), cy + math.sin(a) * (r0 + (r1 - r0) * j / steps)) for j in range(steps + 1)]
        for j in range(steps):
            segment(spur[j], spur[j + 1], j)
            if j % 2 == 1:
                pillar(spur[j], spur[j + 1], j)
        ux, uy, nx, ny, ln = frame(spur[-4], spur[-1])
        e = spur[-1]
        for s in (-1, 1):                                                    # platforms either side
            p0 = (spur[-4][0] + nx * s * (HW + 2.5), spur[-4][1] + ny * s * (HW + 2.5))
            p1 = (e[0] + nx * s * (HW + 2.5), e[1] + ny * s * (HW + 2.5))
            v.beam((*p0, Z - 0.3), (*p1, Z - 0.3), 4.0, 1)
        for j in range(4):                                                   # canopy columns and roof
            c = spur[-4 + j] if j < 3 else e
            for s in (-1, 1):
                v.beam((c[0] + nx * s * (HW + 4), c[1] + ny * s * (HW + 4), Z), (c[0] + nx * s * (HW + 4), c[1] + ny * s * (HW + 4), Z + 5.5), 0.3, 0)
        v.beam((spur[-4][0], spur[-4][1], Z + 6.0), (e[0], e[1], Z + 6.0), 2 * (HW + 4.5), 1)
        v.beam((e[0] - nx * HW, e[1] - ny * HW, Z + 0.8), (e[0] + nx * HW, e[1] + ny * HW, Z + 0.8), 0.8, 0)
        light((spur[-3][0] + e[0]) / 2, (spur[-3][1] + e[1]) / 2, Z + 4.5, (1.0, 0.8, 0.5), 6000, 1.0)
    v.finish([iron, deck_m, car_m, win_m])


# ---------------------------------------------------------------------------------------------- scene

def setup(L, a):
    sc = bpy.context.scene
    for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = e
            break
        except TypeError:
            continue
    ee = sc.eevee
    ee.taa_render_samples = a.samples
    for at, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2),
                    ("shadow_step_count", 8), ("use_gtao", True), ("gtao_distance", 4.0), ("light_threshold", 0.02)):
        if hasattr(ee, at):
            try:
                setattr(ee, at, val)
            except Exception:  # noqa: BLE001
                pass
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0
    world = bpy.data.worlds.new("Night")
    sc.world = world
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.09, 0.10, 0.14, 1) if painted("snow") else (0.07, 0.09, 0.16, 1)
    bg.inputs["Strength"].default_value = 1.5
    moon = bpy.data.objects.new("Moon", bpy.data.lights.new("Moon", "SUN"))
    moon.data.energy = 1.5
    moon.data.angle = math.radians(1.0)
    moon.data.color = (0.80, 0.86, 1.0) if painted("snow") else (0.62, 0.74, 1.0)
    travel = Vector((0.7, -0.62, -math.tan(math.radians(40)))).normalized()
    moon.rotation_euler = (-travel).to_track_quat("Z", "Y").to_euler()
    bpy.context.collection.objects.link(moon)

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
    global BUILD_L
    with open(os.path.join(BUILD, "layout.json")) as f:
        L = json.load(f)
    BUILD_L = L
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(1989)
    C = L["cell_m"]
    NX, NY = L["cells"]
    W, H = NX * C, NY * C

    def m(cx, cy):
        return cx * C, (NY - cy) * C

    # Ground (flat, not sheared)
    me = bpy.data.meshes.new("Ground")
    pad = 40
    me.from_pydata([(-pad, -pad, 0), (W + pad, -pad, 0), (W + pad, H + pad, 0), (-pad, H + pad, 0)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for loop, v in zip(uvl.data, me.vertices):
        loop.uv = (v.co.x / W, v.co.y / H)
    me.materials.append(ground_material())
    bpy.context.collection.objects.link(bpy.data.objects.new("Ground", me))

    build_city(L, m, rng)
    build_wall(L, m)
    build_landmarks(L, m, rng)
    build_details(L, m, rng)
    build_viaducts(L, m, rng)
    make_lights()
    setup(L, a)
    t1 = time.time()
    print(f"SCENE BUILT in {t1 - t0:.1f}s")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "ironward.blend"))
    if not a.no_render:
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y} "
              f"in {time.time() - t1:.1f}s -> {a.out}")


main()
