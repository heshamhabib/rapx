"""
Monument City backdrop (IDEA-28): builds the imaginary American city on a sunny summer day in Blender from
build/layout.json (layout.py) and renders the painted backdrop of the map.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/monument/build_backdrop.py -- \\
      [--ppc 64] [--samples 32] [--crop x0,y0,x1,y1 (cells)] [--out build/backdrop.png] [--no-render]

Shares Ironward's scene code (artsrc/maps/ironward/build_backdrop.py is loaded first: projection, mesh helpers,
library placement) and replaces what differs: summer materials, sun and sky, the city fill, the landmarks and the
street details. The landmarks are Sketchfab models (prep_buildings.py library) except the Pentagon, built here.
Tall things lean north in this projection, so each landmark stays inside its blocked footprint (or leans over water).
"""
import math
import os
import random
import sys

_IRONWARD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ironward", "build_backdrop.py"))
_src = open(_IRONWARD).read()
exec(compile(_src[:_src.rindex("\nmain()")], _IRONWARD, "exec"))    # HERE/BUILD follow this file's __file__

import bpy  # noqa: E402
from mathutils import Matrix  # noqa: E402

PAINTED = os.path.normpath(os.path.join(ARTSRC, "..", "assets", "maps", "monument"))
MODEL_SHARE = 0.95
PREFER = {}
LANDMARK_MODELS = {"capitol", "liberty", "rushmore", "willis", "flatiron"}
WALLS = [(0.62, 0.30, 0.22), (0.55, 0.36, 0.28), (0.80, 0.74, 0.62), (0.72, 0.70, 0.66), (0.50, 0.42, 0.36), (0.86, 0.82, 0.72)]
CAR_COLORS = [(0.95, 0.72, 0.05)] * 4 + [(0.05, 0.05, 0.06), (0.8, 0.8, 0.82), (0.55, 0.05, 0.05), (0.1, 0.2, 0.45)]


# ---------------------------------------------------------------------------------------------- summer materials

def snow_color(nt, coord):
    return tiled(nt, coord, "Concrete034", 3.0, (0.8, 0.79, 0.76))


def snowy(name, rgb, tex_name="Concrete034", repeat=3.0):
    return plain(name, rgb, 0.8, tex_name="Concrete034" if tex_name in ("steel", "Snow006") else tex_name, repeat=repeat)


def roof_material():
    """Flat tar-and-gravel city roofs."""
    mat, nt, bsdf, coord = new_mat("Roof")
    col = tiled(nt, coord, "Concrete034", 4.0, (0.42, 0.41, 0.40))
    col = mul(nt, col, mix(nt, (0.75, 0.74, 0.72), (1.1, 1.08, 1.04), noise(nt, coord, 0.08, 3.0)))
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    return mat


def add_snow(mat):
    """(Summer) imported building materials are kept as they are; both sides drawn."""
    mat.use_backface_culling = False


PAINT_GAIN = (1.0, 1.0, 1.0)     # (Ironward warms its night textures; daylight textures stay as painted)


def lawn_color(nt, coord):
    """The lawns: three painted HD grass textures (monument-prompts.md, make_seamless.py) blended in large natural
    patches: lush meadow and short park lawn, with drier straw-coloured patches, each tiled at its own scale and
    turned so no repeat shows. Falls back to the photo texture when they have not been generated."""
    if not painted("grass-lush"):
        return mul(nt, tiled(nt, coord, "Grass004", 5.0), mix(nt, (0.78, 0.92, 0.62), (0.95, 1.0, 0.7), noise(nt, coord, 0.05, 3.0)))
    lush = paint_tex(nt, coord, "grass-lush", 30.0, sat=1.0)
    lawn = paint_tex(nt, coord, "grass-lawn", 24.0, sat=1.0)
    dry = paint_tex(nt, coord, "grass-dry", 34.0, sat=1.0)
    col = mix(nt, lawn, lush, smooth(nt, noise(nt, coord, 0.018, 3.0), 0.4, 0.62))
    col = mix(nt, col, dry, math_node(nt, "MULTIPLY", smooth(nt, noise(nt, coord, 0.011, 4.0), 0.55, 0.72), 0.85))
    # Light and dark mottling at the scale of a few metres, like uneven ground and thicker clumps
    col = mul(nt, col, (0.84, 0.88, 0.74))                          # a deeper, less lime green
    return mul(nt, col, mix(nt, (0.82, 0.85, 0.82), (1.08, 1.06, 1.0), noise(nt, coord, 0.12, 3.0)))


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
    side = tiled(nt, coord, "PavingStones070", 2.5, (0.88, 0.86, 0.82))
    asphalt = mul(nt, tiled(nt, coord, "Asphalt012", 8.0), (0.52, 0.52, 0.54))
    plaza = tiled(nt, coord, "PavingStones131", 3.0, (1.05, 1.0, 0.9))
    lawn = lawn_color(nt, coord)
    quay = tiled(nt, coord, "Concrete034", 3.0, (0.86, 0.85, 0.82))
    col = side
    col = mix(nt, col, asphalt, edge(nt, sep.outputs[0], n_small, 0.04))
    col = mix(nt, col, plaza, edge(nt, sep.outputs[1], n_small, 0.04))
    col = mix(nt, col, lawn, edge(nt, sep.outputs[2], n_small, 0.25))
    col = mix(nt, col, quay, edge(nt, ga.outputs["Alpha"], n_small, 0.04))
    wv = wt.outputs["Color"]
    wcol = mix(nt, (0.03, 0.13, 0.19), (0.06, 0.22, 0.28), n_small)
    wcol = mix(nt, (0.02, 0.08, 0.11), wcol, smooth(nt, wv, 0.5, 0.75))
    water = math_node(nt, "GREATER_THAN", wv, 0.5)
    col = mix(nt, col, wcol, water)
    nt.links.new(col, bsdf.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMix")
    nt.links.new(water, rough.inputs[0])
    rough.inputs[2].default_value = 0.85
    rough.inputs[3].default_value = 0.06
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    return mat


# ---------------------------------------------------------------------------------------------- city

def place_center(name, scale, cx, cy, z=0.0, rotz=0.0):
    """A library building centred on (cx, cy) metres at height z, scaled (sx, sy, sz), turned rotz degrees, sheared."""
    me0, i = LIB[name]
    me = me0.copy()
    me.transform(OBLIQUE @ Matrix.Translation((cx, cy, z)) @ Matrix.Rotation(math.radians(rotz), 4, "Z")
                 @ Matrix.Diagonal((*scale, 1)))
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return i


def build_city(L, m, rng):
    facade, roof = facade_material(), roof_material()
    trim = snowy("Trim", (0.7, 0.68, 0.64))
    metal = plain("Iron", (0.12, 0.12, 0.13), 0.5, 0.8)
    houses = Mesh("Houses")          # 0 facade, 1 roof, 2 trim, 3 iron
    load_library()
    models = 0
    for i, b in enumerate(L["buildings"]):
        cx0, cy0, cx1, cy1 = b["rect"]
        x0, y1 = m(cx0, cy0)
        x1, y0 = m(cx1, cy1)
        x0, y0, x1, y1 = x0 + 0.4, y0 + 0.4, x1 - 0.4, y1 - 0.4
        r = random.Random(i)
        houses.cur = {"lit": 0.0, "seed": r.random()}
        if model_house(b, x0, y0, x1, y1, L["grid"], r, houses):
            models += 1
            continue
        # Fallback: a brick or limestone block with a flat roof, a cornice and sometimes a water tank
        color = WALLS[b["style"] % len(WALLS)]
        h = min(allowed_height(b, L["grid"]), (3 + b["floors"] % 5) * FLOOR + 1.0)
        houses.box(x0, y0, x1, y1, 0, h, 0, color, top=True, top_mat=1)
        houses.box(x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, h, h + 0.7, 2, (0.75, 0.73, 0.68), top=False)
        if r.random() < 0.3 and min(x1 - x0, y1 - y0) > 7:
            water_tank(houses, r.uniform(x0 + 3, x1 - 3), r.uniform(y0 + 3, y1 - 3), h, 3)
    houses.finish([facade, roof, trim, metal])
    print(f"{models} of {len(L['buildings'])} lots with 3D buildings")


def pent(cx, cy, rad, rot=90.0):
    return [(cx + rad * math.cos(math.radians(rot + 72 * k)), cy + rad * math.sin(math.radians(rot + 72 * k))) for k in range(5)]


def pentagon(mesh, cx, cy, R):
    """Five concentric rings with light wells, ten radial corridors and a lawn courtyard. Materials: 0 limestone,
    1 roof, 2 courtyard lawn."""
    rings = [(1.0, 0.87), (0.80, 0.69), (0.62, 0.52), (0.46, 0.37)]
    for ro, ri in rings:
        h = 22.0 if ro > 0.5 else 20.0
        o, n = pent(cx, cy, R * ro), pent(cx, cy, R * ri)
        for k in range(5):
            a, b = o[k], o[(k + 1) % 5]
            mesh.wall(a, b, 0, h, 0, (1, 1, 1))
            c, d = n[(k + 1) % 5], n[k]
            mesh.wall(c, d, 0, h, 0, (1, 1, 1))
            mesh.face([(*a, h), (*b, h), (*n[(k + 1) % 5], h), (*n[k], h)], 1, (1, 1, 1), 1.0)
    # Corridors across the light wells: at each corner and each side's middle
    for k in range(5):
        for t in (0.0, 0.5):
            ang = math.radians(90 + 72 * (k + t))
            r0, r1 = R * 0.37, R * 0.87
            if t == 0.5:
                r0, r1 = r0 * math.cos(math.radians(36)), r1 * math.cos(math.radians(36))
            ux, uy = math.cos(ang), math.sin(ang)
            nx, ny = -uy * 4.5, ux * 4.5
            p = [(cx + ux * r0 - nx, cy + uy * r0 - ny), (cx + ux * r1 - nx, cy + uy * r1 - ny),
                 (cx + ux * r1 + nx, cy + uy * r1 + ny), (cx + ux * r0 + nx, cy + uy * r0 + ny)]
            for q in range(4):
                mesh.wall(p[q], p[(q + 1) % 4], 0, 18, 0, (1, 1, 1))
            mesh.face([(*q, 18) for q in p], 1, (1, 1, 1), 1.0)
    inner = pent(cx, cy, R * 0.37)
    mesh.face([(*q, 0.05) for q in inner], 2, (1, 1, 1), 1.0)
    mesh.cylinder(cx, cy, 3.0, 3.0, 0, 4, 1, seg=8)                       # the courtyard's little pavilion


def build_landmarks(L, m, rng):
    C = L["cell_m"]
    stone = plain("Limestone", (0.80, 0.78, 0.72), 0.85, tex_name="Concrete034", repeat=4.0)
    roofm = plain("Pentagon roof", (0.36, 0.38, 0.40), 0.8, tex_name="Concrete034", repeat=6.0)
    lawn = plain("Courtyard lawn", (0.30, 0.48, 0.20), 0.9, tex_name="Grass004", repeat=5.0)
    granite = plain("Granite", (0.74, 0.64, 0.56), 0.85, tex_name="Concrete034", repeat=6.0)
    glass = plain("Podium glass", (0.12, 0.16, 0.20), 0.2, 0.3)
    pine = plain("Pine", (0.06, 0.16, 0.07), 0.9)
    lm = Mesh("Landmarks")       # 0 limestone, 1 roof, 2 lawn, 3 granite, 4 glass, 5 pine
    lm.cur = {"lit": 0.0, "seed": 0.0}

    def rect_m(key):
        x0c, y0c, x1c, y1c = L["landmarks"][key]
        ax0, ay1 = m(x0c, y0c)
        ax1, ay0 = m(x1c, y1c)
        return ax0, ay0, ax1, ay1

    def lib(model):
        return next((n for n, (_, i) in LIB.items() if i["model"] == model), None)

    # US Capitol (north): fills the width of its plot, centred
    ax0, ay0, ax1, ay1 = rect_m("capitol")
    name = lib("capitol")
    if name:
        i = LIB[name][1]
        s = (ax1 - ax0) * 0.98 / i["w"]
        place_center(name, (s, s, s), (ax0 + ax1) / 2, (ay0 + ay1) / 2)
        lm.face([(ax0, ay0, 0.05), (ax1, ay0, 0.05), (ax1, ay1, 0.05), (ax0, ay1, 0.05)], 2, (1, 1, 1), 1.0)   # its lawn

    # Willis Tower (east): a podium filling the plot, the tower at its south edge, short enough not to lean out
    ax0, ay0, ax1, ay1 = rect_m("tower")
    lm.box(ax0 + 1, ay0 + 1, ax1 - 1, ay1 - 1, 0, 7, 0, top=True, top_mat=1)
    lm.box(ax0 + 1.3, ay0 + 0.7, ax1 - 1.3, ay0 + 1.3, 1, 5, 4)                 # glass lobby front
    name = lib("willis")
    if name:
        i = LIB[name][1]
        base = min(ax1 - ax0, ay1 - ay0) * 0.38
        hmax = ((ay1 - ay0) - base - 2) / SHEAR
        s = base / max(i["w"], i["d"])
        place_center(name, (s, s, min(s, hmax / i["h"])), (ax0 + ax1) / 2, ay0 + 2 + base / 2)

    # The Pentagon (south): built here
    ax0, ay0, ax1, ay1 = rect_m("pentagon")
    w, d = ax1 - ax0, ay1 - ay0
    R = min(w / 1.902, d / 1.809) * 0.98
    pentagon(lm, (ax0 + ax1) / 2, ay0 + d / 2 - R * (1 - math.cos(math.radians(36))) / 2, R)

    # Mount Rushmore (west): the carved relief at the south of the plot, faces to the camera, squashed so its top
    # stays inside the plot; a granite mountain behind and round it, pines at its foot
    ax0, ay0, ax1, ay1 = rect_m("rushmore")
    name = lib("rushmore")
    for _ in range(46):
        bx, by = rng.uniform(ax0 + 6, ax1 - 6), rng.uniform(ay0 + (ay1 - ay0) * 0.45, ay1 - 6)
        lm.blob(bx, by, 0, rng.uniform(9, 16), rng.uniform(0.7, 1.2), 3, (1, 1, 1), rng)
    for _ in range(26):
        bx = rng.uniform(ax0 + 2, ax1 - 2)
        by = rng.choice((rng.uniform(ay0 + 1, ay0 + 6), rng.uniform(ay0 + 1, ay1 - 2)))
        if ay0 + 8 < by and ax0 + 8 < bx < ax1 - 8:
            continue
        hgt = rng.uniform(6, 11)
        lm.cone(bx, by, hgt * 0.3, 0, hgt, 5, seg=7)
    if name:
        i = LIB[name][1]
        s = (ax1 - ax0) * 0.92 / i["w"]
        d = i["d"] * s
        sz = min(s, ((ay1 - ay0) - d - 3) / SHEAR / i["h"])
        place_center(name, (s, s, sz), (ax0 + ax1) / 2, ay0 + 3 + d / 2)

    # Statue of Liberty on its star-shaped fort, on the island in the harbour
    cx, cy = m(L["landmarks"]["liberty"][0], L["landmarks"]["liberty"][1])
    rad = L["landmarks"]["liberty"][2] * C
    star = []
    for k in range(22):
        rr = rad * (0.92 if k % 2 == 0 else 0.62)
        a = math.radians(90 + k * 360 / 22)
        star.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    for k in range(22):
        lm.wall(star[k], star[(k + 1) % 22], 0, 4.0, 3, (1, 1, 1))
    lm.face([(*q, 4.0) for q in star], 2, (1, 1, 1), 1.0)
    lm.box(cx - 7, cy - 7, cx + 7, cy + 7, 4, 20, 3, top=True, top_mat=3)
    lm.box(cx - 8, cy - 8, cx + 8, cy + 8, 4, 7, 3, top=True, top_mat=3)
    name = lib("liberty")
    if name:
        i = LIB[name][1]
        s = 38.0 / i["h"]
        place_center(name, (s, s, s), cx, cy, z=20.0)
    lm.finish([stone, roofm, lawn, granite, glass, pine])


def build_details(L, m, rng):
    """Street lamps, parked cars and yellow taxis, harbour quay walls, a few boats."""
    C = L["cell_m"]
    N = L["cells"][0]
    grid, ground = L["grid"], L["ground"]
    stone = plain("Quay stone", (0.70, 0.68, 0.64), 0.85, tex_name="Concrete034", repeat=3.0)
    iron = plain("Lamp iron", (0.08, 0.09, 0.08), 0.5, 0.7)
    cars = [plain(f"Car {k}", c, 0.3, 0.5) for k, c in enumerate(CAR_COLORS)]
    hull = plain("Hull", (0.92, 0.92, 0.90), 0.4)
    d = Mesh("Details")      # 0 stone, 1 iron, 2 hull, 3.. car colours
    for y in range(1, N - 1):
        for x in range(1, N - 1):
            if ground[y][x] != "a" or grid[y][x] != "." or (x * 7 + y * 13) % 5:
                continue
            if not any(grid[y + dy][x + dx] == "#" for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            px, py = m(x + 0.5, y + 0.5)
            d.cylinder(px, py, 0.14, 0.1, 0, 6, 1, seg=6, cap=False)
            d.box(px - 0.05, py - 0.05, px + 0.9, py + 0.05, 5.8, 6.0, 1)
    for _ in range(160):
        x, y = rng.randrange(N), rng.randrange(N)
        if ground[y][x] != "a" or grid[y][x] != ".":
            continue
        cx, cy = m(x + rng.random(), y + rng.random())
        # Cars run along the street: look at which way the asphalt continues
        horiz = (x + 1 < N and ground[y][x + 1] == "a") and (x > 0 and ground[y][x - 1] == "a")
        a = (0 if horiz else math.pi / 2) + rng.uniform(-0.05, 0.05)
        ln, wd = rng.uniform(4.2, 5.0), 1.9
        ca, sa = math.cos(a), math.sin(a)
        corners = [(cx + ca * u - sa * v, cy + sa * u + ca * v) for u, v in ((-ln / 2, -wd / 2), (ln / 2, -wd / 2), (ln / 2, wd / 2), (-ln / 2, wd / 2))]
        mat = 3 + rng.randrange(len(CAR_COLORS))
        for z0, z1, s in ((0.3, 1.0, 1.0), (1.0, 1.5, 0.6)):
            pts = [(cx + (qx - cx) * s, cy + (qy - cy) * s) for qx, qy in corners]
            for i in range(4):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % 4]
                d.face([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], mat, (1, 1, 1), 0.0)
            d.face([(qx, qy, z1) for qx, qy in pts], mat, (1, 1, 1), 1.0)
    # Harbour quay walls: round, at the island and the outer shore
    R0, R1 = L["ring"]
    cx, cy = m(N / 2, N / 2)
    seg = 120
    for rad, out in ((R0 * C, -1), (R1 * C, 1)):
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            p0 = (cx + math.cos(a0) * rad, cy + math.sin(a0) * rad)
            p1 = (cx + math.cos(a1) * rad, cy + math.sin(a1) * rad)
            q0 = (cx + math.cos(a0) * (rad + out * 0.7), cy + math.sin(a0) * (rad + out * 0.7))
            q1 = (cx + math.cos(a1) * (rad + out * 0.7), cy + math.sin(a1) * (rad + out * 0.7))
            d.face([(p0[0], p0[1], -1.5), (p1[0], p1[1], -1.5), (p1[0], p1[1], 0.9), (p0[0], p0[1], 0.9)], 0, (1, 1, 1), 0.0)
            d.face([(p1[0], p1[1], -1.5), (p0[0], p0[1], -1.5), (p0[0], p0[1], 0.9), (p1[0], p1[1], 0.9)], 0, (1, 1, 1), 0.0)
            d.face([(p0[0], p0[1], 0.9), (p1[0], p1[1], 0.9), (q1[0], q1[1], 0.9), (q0[0], q0[1], 0.9)], 0, (1, 1, 1), 1.0)
    # A few boats on the harbour (south half, where nothing tall leans over them)
    for k in range(4):
        a = math.radians(200 + k * 40)
        rr = (R0 + R1) / 2 * C
        bx, by = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        ta = a + math.pi / 2
        ux, uy = math.cos(ta), math.sin(ta)
        pts = [(bx + ux * 6, by + uy * 6), (bx + ux * 2 - uy * 1.8, by + uy * 2 + ux * 1.8), (bx - ux * 5 - uy * 1.8, by - uy * 5 + ux * 1.8),
               (bx - ux * 5 + uy * 1.8, by - uy * 5 - ux * 1.8), (bx + ux * 2 + uy * 1.8, by + uy * 2 - ux * 1.8)]
        for i in range(5):
            d.wall(pts[i], pts[(i + 1) % 5], 0, 1.4, 2, (1, 1, 1))
        d.face([(*q, 1.4) for q in pts], 2, (1, 1, 1), 1.0)
        d.box(bx - 1.5, by - 1.2, bx + 1.5, by + 1.2, 1.4, 3.2, 2)
    d.finish([stone, iron, hull] + cars)


def build_vegetation(L, m, rng):
    """Scatters the Sketchfab grass clumps, flowers and shrubs (prep_vegetation.py) over the build areas: dense grass
    tufts everywhere, flowers in small drifts, shrubs along the lawn edges. Each plant mesh is sheared once in four
    turns; the copies share it and only move and scale (a uniform scale keeps the shear right)."""
    path = os.path.join(BUILD, "vegetation.blend")
    if not os.path.exists(path):
        return
    info = json.load(open(os.path.join(BUILD, "vegetation.json")))
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.meshes = [n for n in src.meshes if n in info]
    variants = {"grass": [], "flower": [], "shrub": []}
    for me in dst.meshes:
        for k in range(4):
            v = me.copy()
            v.transform(OBLIQUE @ Matrix.Rotation(k * math.pi / 2 + 0.4, 4, "Z"))
            variants[info[me.name]["kind"]].append(v)
    C = L["cell_m"]
    lot = L["lot"]
    col = bpy.data.collections.new("Vegetation")
    bpy.context.scene.collection.children.link(col)
    count = {"grass": 0, "flower": 0, "shrub": 0}

    def put(kind, x, y, s):
        ob = bpy.data.objects.new(kind, rng.choice(variants[kind]))
        ob.location = (x, y, 0)
        ob.scale = (s, s, s)
        col.objects.link(ob)
        count[kind] += 1

    for sx, sy in L["spawns"]:
        x0, y1 = m(sx - lot, sy - lot)
        x1, y0 = m(sx + lot, sy + lot)
        # Flower drifts: a few centres, flowers thinning out round them
        drifts = [(rng.uniform(x0 + 8, x1 - 8), rng.uniform(y0 + 8, y1 - 8), rng.uniform(5, 11)) for _ in range(9)]
        area = (x1 - x0) * (y1 - y0)
        for _ in range(int(area / 3.2)):                      # a tuft every ~3 m2
            x, y = rng.uniform(x0 + 0.5, x1 - 0.5), rng.uniform(y0 + 0.5, y1 - 0.5)
            put("grass", x, y, rng.uniform(0.75, 1.3))
        for cx, cy, rad in drifts:
            for _ in range(int(rad * rad * 0.5)):
                a, r = rng.uniform(0, 2 * math.pi), rad * math.sqrt(rng.random())
                x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
                if x0 < x < x1 and y0 < y < y1:
                    put("flower", x, y, rng.uniform(0.7, 1.2))
        # Shrubs and taller grass along the edges of the lawn (inside it by a metre)
        for side in range(4):
            length = (x1 - x0) if side < 2 else (y1 - y0)
            t = rng.uniform(0, 6)
            while t < length:
                if side == 0:
                    x, y = x0 + t, y0 + 1.2
                elif side == 1:
                    x, y = x0 + t, y1 - 1.2
                elif side == 2:
                    x, y = x0 + 1.2, y0 + t
                else:
                    x, y = x1 - 1.2, y0 + t
                if rng.random() < 0.55:
                    put("shrub", x, y, rng.uniform(0.6, 1.0))
                for _ in range(3):
                    put("grass", x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5), rng.uniform(1.2, 1.6))
                t += rng.uniform(3, 7)
    print(f"vegetation: {count}")


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
                    ("shadow_step_count", 8), ("use_gtao", True), ("gtao_distance", 4.0)):
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
    world = bpy.data.worlds.new("Sky")
    sc.world = world
    bg = world.node_tree.nodes.get("Background")
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(os.path.join(ARTSRC, "hdri", "sky_2k.hdr"))
    world.node_tree.links.new(env.outputs[0], bg.inputs[0])
    bg.inputs["Strength"].default_value = 0.5
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.8
    sun.data.angle = math.radians(1.5)
    sun.data.color = (1.0, 0.95, 0.86)
    travel = Vector((0.7, -0.62, -math.tan(math.radians(42)))).normalized()
    sun.rotation_euler = (-travel).to_track_quat("Z", "Y").to_euler()
    bpy.context.collection.objects.link(sun)
    C = L["cell_m"]
    NX, NY = L["cells"]
    x0, y0, x1, y1 = (0, 0, NX, NY) if not a.crop else (float(v) for v in a.crop.split(","))
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max((x1 - x0) * C, (y1 - y0) * C)
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
    rng = random.Random(1776)
    C = L["cell_m"]
    NX, NY = L["cells"]
    W, H = NX * C, NY * C

    def m(cx, cy):
        return cx * C, (NY - cy) * C

    me = bpy.data.meshes.new("Ground")
    pad = 40
    me.from_pydata([(-pad, -pad, 0), (W + pad, -pad, 0), (W + pad, H + pad, 0), (-pad, H + pad, 0)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for loop, v in zip(uvl.data, me.vertices):
        loop.uv = (v.co.x / W, v.co.y / H)
    me.materials.append(ground_material())
    bpy.context.collection.objects.link(bpy.data.objects.new("Ground", me))
    build_city(L, m, rng)
    build_landmarks(L, m, rng)
    build_details(L, m, rng)
    setup(L, a)
    t1 = time.time()
    print(f"SCENE BUILT in {t1 - t0:.1f}s")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "monument.blend"))
    if not a.no_render:
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y} "
              f"in {time.time() - t1:.1f}s -> {a.out}")


main()
