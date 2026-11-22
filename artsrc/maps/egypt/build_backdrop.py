"""
Egypt: Cairo and Giza backdrop (IDEA-28): the Nile between Giza and Cairo at golden sunset, built in Blender from
build/layout.json (layout.py) and rendered as the map's painted backdrop.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/egypt/build_backdrop.py -- \\
      [--ppc 64] [--samples 32] [--crop x0,y0,x1,y1 (cells)] [--out build/backdrop.png] [--no-render]

Shares Washington D.C.'s scene code (sunset light, lamps, bridges, cars; which shares Monument City's and Ironward's)
and replaces: the ground (desert sand, fields, palm grove), the landmarks (pyramids built here as exact shapes; the
Sphinx, the Karnak-style temple, the temple ruins and the palms from Sketchfab; the Cairo Tower and the Grand
Egyptian Museum built here), palms in the grove and on the island, feluccas on the Nile.
"""
import math
import os
import random

_DC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dc", "build_backdrop.py"))
_src = open(_DC).read()
exec(compile(_src[:_src.rindex("\nmain()")], _DC, "exec"))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

LANDMARK_MODELS = {"sphinx", "temples", "ruins", "ruins2", "palms", "palmpack", "felucca"}
SAND = (0.93, 0.76, 0.52)


def ground_material():
    """Monument City's ground (asphalt, paving, lawns, quays, water) with the desert sand of the Giza plateau."""
    mat, nt, bsdf, coord = new_mat("Ground")
    ga = node_img(nt, os.path.join(BUILD, "ground_a.png"), non_color=True)
    ga.image.alpha_mode = "CHANNEL_PACKED"
    ga.interpolation = "Cubic"
    nt.links.new(coord.outputs["UV"], ga.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(ga.outputs["Color"], sep.inputs[0])
    wt = node_img(nt, os.path.join(BUILD, "water.png"), non_color=True)
    sd = node_img(nt, os.path.join(BUILD, "sand.png"), non_color=True)
    for n in (wt, sd):
        n.interpolation = "Cubic"
        nt.links.new(coord.outputs["UV"], n.inputs["Vector"])
    n_small = noise(nt, coord, 0.3)
    paving = tiled(nt, coord, "PavingStones070", 2.5, (0.92, 0.84, 0.72))
    asphalt = mul(nt, tiled(nt, coord, "Asphalt012", 8.0), (0.50, 0.48, 0.46))
    plaza = tiled(nt, coord, "PavingStones131", 3.0, (1.05, 0.92, 0.74))
    lawn = lawn_color(nt, coord)
    quay = tiled(nt, coord, "Concrete034", 3.0, (0.9, 0.84, 0.74))
    sand = mul(nt, tiled(nt, coord, "Ground054", 9.0, SAND), mix(nt, (0.86, 0.82, 0.78), (1.1, 1.05, 0.98), noise(nt, coord, 0.03, 3.0)))
    # Wind ripples in the sand
    ripples = smooth(nt, noise(nt, coord, 0.9, 1.0), 0.4, 0.6)
    sand = mix(nt, sand, mul(nt, sand, (0.9, 0.86, 0.82)), math_node(nt, "MULTIPLY", ripples, 0.4))
    col = paving
    col = mix(nt, col, sand, edge(nt, sd.outputs["Color"], noise(nt, coord, 0.2, 3.0), 0.35))
    col = mix(nt, col, asphalt, edge(nt, sep.outputs[0], n_small, 0.04))
    col = mix(nt, col, plaza, edge(nt, sep.outputs[1], n_small, 0.04))
    col = mix(nt, col, lawn, edge(nt, sep.outputs[2], n_small, 0.25))
    col = mix(nt, col, quay, edge(nt, ga.outputs["Alpha"], n_small, 0.04))
    wv = wt.outputs["Color"]
    wcol = mix(nt, (0.05, 0.16, 0.18), (0.08, 0.24, 0.26), n_small)
    water = math_node(nt, "GREATER_THAN", wv, 0.5)
    col = mix(nt, col, wcol, water)
    nt.links.new(col, bsdf.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMix")
    nt.links.new(water, rough.inputs[0])
    rough.inputs[2].default_value = 0.9
    rough.inputs[3].default_value = 0.06
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    return mat


def pyramid(mesh, x0, y0, x1, y1, h, mat, courses=26):
    """A stepped pyramid: horizontal courses (the casing is long gone), so its faces catch the low sun in bands."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hw = (x1 - x0) / 2
    for k in range(courses):
        z0, z1 = h * k / courses, h * (k + 1) / courses
        r = hw * (1 - k / courses)
        mesh.box(cx - r, cy - r, cx + r, cy + r, z0, z1, mat, top=True)
    mesh.pyramid(cx - hw / courses, cy - hw / courses, cx + hw / courses, cy + hw / courses, h, h + h / courses, mat)


def build_landmarks(L, m, rng):
    stone = plain("Limestone", (0.88, 0.74, 0.54), 0.9, tex_name="Concrete034", repeat=3.0)
    glass = plain("Museum glass", (0.55, 0.60, 0.62), 0.25, 0.2)
    alabaster = plain("Alabaster", (0.92, 0.86, 0.76), 0.6, tex_name="Concrete034", repeat=6.0)
    concrete = plain("Tower concrete", (0.78, 0.72, 0.64), 0.8, tex_name="Concrete034", repeat=4.0)
    copper = plain("Tower crown", (0.40, 0.55, 0.42), 0.5, 0.4)
    lm = Mesh("Landmarks")       # 0 limestone, 1 glass, 2 alabaster, 3 concrete, 4 copper
    lm.cur = {"lit": 0.0, "seed": 0.0}
    H = L["heights"]

    def ground(key):
        x0c, y0c, x1c, y1c = L["landmarks"][key]
        ax0, ay1 = m(x0c, y0c)
        ax1, ay0 = m(x1c, y1c)
        return ax0, ay0, ax1, ay1

    def lib(model, n=0):
        names = [nm for nm, (_, i) in LIB.items() if i["model"] == model]
        return names[n % len(names)] if names else None

    def fit(key, name, rotz=0.0, margin=0.96):
        if not name:
            return
        ax0, ay0, ax1, ay1 = ground(key)
        i = LIB[name][1]
        w, d = (i["d"], i["w"]) if rotz % 180 else (i["w"], i["d"])
        s = min((ax1 - ax0) * margin / w, (ay1 - ay0) * margin / d)
        place_center(name, (s, s, min(s, H[key] / i["h"])), (ax0 + ax1) / 2, (ay0 + ay1) / 2, rotz=rotz)

    for key in ("khufu", "khafre", "menkaure"):
        ax0, ay0, ax1, ay1 = ground(key)
        side = min(ax1 - ax0, ay1 - ay0)
        cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
        pyramid(lm, cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2, H[key], 0)
    fit("sphinx", lib("sphinx"))
    fit("karnak", lib("temples", 2), rotz=90)
    fit("ruins", lib("ruins2"))

    # Grand Egyptian Museum: a long low wedge whose roof rises towards the north, a translucent alabaster facade on
    # the forecourt (south) side, and a glass entrance with a giant pyramid-shaped canopy
    ax0, ay0, ax1, ay1 = ground("gem")
    hgt = H["gem"]
    lm.box(ax0, ay0 + 2, ax1, ay1, 0, hgt * 0.4, 2, top=False)
    lm.face([(ax0, ay0 + 2, hgt * 0.4), (ax1, ay0 + 2, hgt * 0.4), (ax1, ay1, hgt), (ax0, ay1, hgt)], 1, (1, 1, 1), 1.0)
    lm.face([(ax0, ay1, hgt * 0.4), (ax0, ay0 + 2, hgt * 0.4), (ax0, ay1, hgt)], 2, (1, 1, 1), 0.0)
    lm.face([(ax1, ay0 + 2, hgt * 0.4), (ax1, ay1, hgt * 0.4), (ax1, ay1, hgt)], 2, (1, 1, 1), 0.0)
    lm.box(ax0, ay1 - 0.5, ax1, ay1, hgt * 0.4, hgt, 2, top=False)
    for k in range(9):                                           # the facade's triangular panels
        x = ax0 + (k + 0.5) * (ax1 - ax0) / 9
        lm.face([(x - 6, ay0 + 1.9, 0.5), (x + 6, ay0 + 1.9, 0.5), (x, ay0 + 1.9, hgt * 0.38)], 1, (1, 1, 1), 0.0)
    cxm = (ax0 + ax1) / 2
    lm.pyramid(cxm - 5, ay0 - 3, cxm + 5, ay0 + 5, 0, 8, 1)

    # Cairo Tower: a lattice-clad concrete shaft widening at the top into a lotus-shaped crown with a viewing deck
    ax0, ay0, ax1, ay1 = ground("cairotower")
    cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
    hgt = H["cairotower"]
    lm.cylinder(cx, cy, 6.0, 6.0, 0, 1.5, 3, seg=24)
    lm.cylinder(cx, cy, 3.6, 3.0, 1.5, hgt * 0.82, 3, seg=16, cap=False)
    for k in range(12):                                          # the lattice: crossing diagonal ribs
        a0 = 2 * math.pi * k / 12
        for j in range(10):
            z0, z1 = 1.5 + j * (hgt * 0.82 - 1.5) / 10, 1.5 + (j + 1) * (hgt * 0.82 - 1.5) / 10
            r0, r1 = 3.65 - 0.6 * j / 10, 3.65 - 0.6 * (j + 1) / 10
            a1 = a0 + (0.26 if j % 2 == 0 else -0.26)
            lm.beam((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0), (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1), z1), 0.25, 3)
            a0 = a1
    for k in range(10):                                          # lotus petals opening at the top
        a = 2 * math.pi * k / 10
        p0 = Vector((cx + 3.0 * math.cos(a), cy + 3.0 * math.sin(a), hgt * 0.82))
        p1 = Vector((cx + 5.2 * math.cos(a), cy + 5.2 * math.sin(a), hgt * 0.95))
        lm.beam(p0, p1, 1.4, 4)
    lm.cylinder(cx, cy, 4.6, 4.6, hgt * 0.9, hgt * 0.96, 3, seg=20)
    lm.cylinder(cx, cy, 0.4, 0.1, hgt * 0.96, hgt, 3, seg=6)

    # Avenue of sphinxes from the Nile to the temple: small sphinxes on both sides
    sph = lib("sphinx")
    if sph:
        x0c, y0c, x1c, y1c = L["avenue"]
        i = LIB[sph][1]
        s = 5.0 / i["w"]
        n = int((x1c - x0c) * 7 / 6)
        for k in range(n):
            x, _ = m(x0c + (k + 0.5) * (x1c - x0c) / n, 0)
            for yc in (y0c - 0.3, y1c + 0.3):
                _, y = m(0, yc)
                place_center(sph, (s, s, s), x, y)
    # Sacred lake: a stone rim
    x0c, y0c, x1c, y1c = L["lake"]
    ax0, ay1 = m(x0c, y0c)
    ax1, ay0 = m(x1c, y1c)
    for (a, b) in (((ax0, ay0), (ax1, ay0)), ((ax1, ay0), (ax1, ay1)), ((ax1, ay1), (ax0, ay1)), ((ax0, ay1), (ax0, ay0))):
        lm.wall(a, b, -1.0, 0.8, 0, (1, 1, 1))
    lm.finish([stone, glass, alabaster, concrete, copper])


def build_palms(L, m, rng):
    """Date palms: dense in the palm grove along the west bank (blocked cells), a few on Gezira island and round the
    temple's forecourt edges; feluccas with white sails on the Nile."""
    palms = [n for n, (_, i) in LIB.items() if i["model"] in ("palms", "palmpack") and i["h"] > 4]
    if not palms:
        return
    C, (NX, NY) = L["cell_m"], L["cells"]
    ground, grid = L["ground"], L["grid"]
    n = 0
    for y in range(NY):
        for x in range(NX):
            g = ground[y][x]
            if g == "v" and rng.random() < 0.85:
                k = 2
            elif g == "y" and grid[y][x] == "." and L["island"] and \
                    ((x - L["island"][0]) / L["island"][2]) ** 2 + ((y - L["island"][1]) / L["island"][3]) ** 2 < 0.8 and rng.random() < 0.15:
                k = 1
            else:
                continue
            for _ in range(k):
                px, py = m(x + rng.random(), y + rng.random())
                name = rng.choice(palms)
                i = LIB[name][1]
                s = rng.uniform(9, 13) / i["h"]
                place_center(name, (s, s, s), px, py, rotz=rng.uniform(0, 360))
                n += 1
    boat = next((nm for nm, (_, i) in LIB.items() if i["model"] == "felucca"), None)
    if boat:
        i = LIB[boat][1]
        s = 14.0 / max(i["w"], i["d"])
        for (cx, cy, rot) in ((64, 58, 10), (66, 76, -8), (67, 20, 5), (63, 66, 180)):
            px, py = m(cx, cy)
            place_center(boat, (s, s, s), px, py, rotz=rot)
    print(f"{n} palms")


def main():
    global BUILD_L
    a = args()
    t0 = time.time()
    with open(os.path.join(BUILD, "layout.json")) as f:
        L = json.load(f)
    BUILD_L = L
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(1922)
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
    build_palms(L, m, rng)
    make_lights()
    setup(L, a)
    t1 = time.time()
    print(f"SCENE BUILT in {t1 - t0:.1f}s")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "egypt.blend"))
    if not a.no_render:
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y} "
              f"in {time.time() - t1:.1f}s -> {a.out}")


main()
