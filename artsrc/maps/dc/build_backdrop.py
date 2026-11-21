"""
Washington D.C. backdrop (IDEA-28): the National Mall and the city round it at golden sunset, built in Blender from
build/layout.json (layout.py) and rendered as the map's painted backdrop.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/dc/build_backdrop.py -- \\
      [--ppc 64] [--samples 32] [--crop x0,y0,x1,y1 (cells)] [--out build/backdrop.png] [--no-render]

Shares Monument City's scene code (which shares Ironward's): projection, materials, library placement. Replaced here:
the sunset light, the landmarks (White House, Capitol, Jefferson Memorial: Sketchfab models; Lincoln Memorial,
Washington Monument, the bridges: built here), the river's quay walls, lamps lit for the evening.

Every building gets the height the layout gave it (its lean stays inside its blocked city block, so no unit ever
drives over painted building), every landmark the height in layout.HEIGHTS.
"""
import math
import os
import random
import sys

_MONUMENT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "monument", "build_backdrop.py"))
_src = open(_MONUMENT).read()
exec(compile(_src[:_src.rindex("\nmain()")], _MONUMENT, "exec"))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402


LANDMARK_MODELS = {"capitol", "whitehouse", "jefferson"}
MODEL_SHARE = 0.92
SUN_RGB = (1.0, 0.70, 0.42)


def allowed_height(b, grid):
    return b["h"]


def build_city(L, m, rng):
    facade, roof = facade_material(), roof_material()
    trim = snowy("Trim", (0.72, 0.68, 0.62))
    metal = plain("Iron", (0.12, 0.12, 0.13), 0.5, 0.8)
    houses = Mesh("Houses")
    load_library()
    models = 0
    for i, b in enumerate(L["buildings"]):
        cx0, cy0, cx1, cy1 = b["rect"]
        x0, y1 = m(cx0, cy0)
        x1, y0 = m(cx1, cy1)
        x0, y0, x1, y1 = x0 + 0.3, y0 + 0.3, x1 - 0.3, y1 - 0.3
        r = random.Random(i)
        houses.cur = {"lit": b["lit"] * 0.25, "seed": r.random()}      # a few windows lit at sunset
        if b["h"] >= 10 and model_house(b, x0, y0, x1, y1, L["grid"], r, houses):
            models += 1
            continue
        color = WALLS[b["style"] % len(WALLS)]
        h = b["h"]
        houses.box(x0, y0, x1, y1, 0, h, 0, color, top=True, top_mat=1)
        houses.box(x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, h, h + 0.6, 2, (0.78, 0.74, 0.66), top=False)
        if h > 14 and r.random() < 0.3 and min(x1 - x0, y1 - y0) > 7:
            water_tank(houses, r.uniform(x0 + 3, x1 - 3), r.uniform(y0 + 3, y1 - 3), h, 3)
    houses.finish([facade, roof, trim, metal])
    print(f"{models} of {len(L['buildings'])} lots with 3D buildings")


def temple(mesh, x0, y0, x1, y1, h, cols_long, cols_short, mat_stone, mat_roof, attic=True):
    """A Greek temple: stepped podium, a colonnade all round, an attic and a flat roof (the Lincoln Memorial)."""
    for k in range(3):
        mesh.box(x0 + k * 1.2, y0 + k * 1.2, x1 - k * 1.2, y1 - k * 1.2, k * 1.2, (k + 1) * 1.2, mat_stone)
    z0 = 3.6
    ix0, iy0, ix1, iy1 = x0 + 4.5, y0 + 4.5, x1 - 4.5, y1 - 4.5
    mesh.box(ix0 + 3, iy0 + 3, ix1 - 3, iy1 - 3, z0, h - 3, mat_stone, top=False)           # the cella
    for k in range(cols_long):
        t = (k + 0.5) / cols_long
        for xx in (ix0 + 0.8, ix1 - 0.8):
            mesh.cylinder(xx, iy0 + t * (iy1 - iy0), 0.85, 0.75, z0, h - 3, mat_stone, seg=10)
    for k in range(cols_short):
        t = (k + 0.5) / cols_short
        for yy in (iy0 + 0.8, iy1 - 0.8):
            mesh.cylinder(ix0 + t * (ix1 - ix0), yy, 0.85, 0.75, z0, h - 3, mat_stone, seg=10)
    mesh.box(ix0 - 0.4, iy0 - 0.4, ix1 + 0.4, iy1 + 0.4, h - 3, h - 1.2, mat_stone, top=False)  # entablature
    if attic:
        mesh.box(ix0 + 1.5, iy0 + 1.5, ix1 - 1.5, iy1 - 1.5, h - 1.2, h, mat_stone, top=True, top_mat=mat_roof)


def obelisk(mesh, cx, cy, h, base, mat):
    """The Washington Monument: a tapering marble shaft with a pyramidion."""
    top = base * 0.66
    shaft = h * 0.9
    for (ax, ay), (bx, by) in zip([(-1, -1), (1, -1), (1, 1), (-1, 1)], [(1, -1), (1, 1), (-1, 1), (-1, -1)]):
        mesh.face([(cx + ax * base, cy + ay * base, 0), (cx + bx * base, cy + by * base, 0),
                   (cx + bx * top, cy + by * top, shaft), (cx + ax * top, cy + ay * top, shaft)], mat, (1, 1, 1), 0.0,
                  [(0, 0), (2 * base, 0), (2 * base, shaft), (0, shaft)])
    mesh.pyramid(cx - top, cy - top, cx + top, cy + top, shaft, h, mat)


def build_landmarks(L, m, rng):
    marble = plain("Marble", (0.90, 0.88, 0.84), 0.6, tex_name="Concrete034", repeat=6.0)
    roofm = plain("Lead roof", (0.42, 0.44, 0.46), 0.7, tex_name="Concrete034", repeat=6.0)
    lawn = plain("Landmark lawn", (0.32, 0.46, 0.20), 0.9, tex_name="Grass004", repeat=5.0)
    flagpole = plain("Flagpole", (0.85, 0.85, 0.85), 0.3, 0.9)
    paving = plain("Paving", (0.78, 0.74, 0.66), 0.8, tex_name="PavingStones131", repeat=3.0)
    lm = Mesh("Landmarks")       # 0 marble, 1 roof, 2 lawn, 3 flagpole, 4 paving
    lm.cur = {"lit": 0.0, "seed": 0.0}
    H = L["heights"]

    def ground(key):
        x0c, y0c, x1c, y1c = L["landmarks"][key]
        ax0, ay1 = m(x0c, y0c)
        ax1, ay0 = m(x1c, y1c)
        return ax0, ay0, ax1, ay1

    def lib(model):
        return next((n for n, (_, i) in LIB.items() if i["model"] == model), None)

    def fit(key, model, rotz=0.0, margin=0.94):
        ax0, ay0, ax1, ay1 = ground(key)
        name = lib(model)
        if not name:
            return
        i = LIB[name][1]
        w, d = (i["d"], i["w"]) if rotz % 180 else (i["w"], i["d"])
        s = min((ax1 - ax0) * margin / w, (ay1 - ay0) * margin / d)
        sz = min(s, H[key] / i["h"])
        place_center(name, (s, s, sz), (ax0 + ax1) / 2, (ay0 + ay1) / 2, rotz=rotz)

    # Lincoln Memorial: the temple, long side north-south, facing east over the Reflecting Pool
    ax0, ay0, ax1, ay1 = ground("lincoln")
    temple(lm, ax0 + 2, ay0 + 4, ax1 - 2, ay1 - 2, H["lincoln"], 9, 6, 0, 1)
    # Washington Monument on its round grassy knoll, ringed by flags
    ax0, ay0, ax1, ay1 = ground("monument")
    cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
    lm.cylinder(cx, cy, 13, 13, 0, 0.6, 4, seg=48)
    obelisk(lm, cx, cy, H["monument"], 4.6, 0)
    for k in range(24):
        a = 2 * math.pi * k / 24
        lm.cylinder(cx + 11 * math.cos(a), cy + 11 * math.sin(a), 0.08, 0.06, 0.6, 9, 3, seg=5, cap=False)
    fit("capitol", "capitol")
    fit("whitehouse", "whitehouse")
    fit("jefferson", "jefferson")
    lm.finish([marble, roofm, lawn, flagpole, paving])


def build_details(L, m, rng):
    """Bridges (granite arches with balustrades), river quay walls, the Reflecting Pool's rim, street lamps lit
    for the evening, parked cars and taxis."""
    C = L["cell_m"]
    NX, NY = L["cells"]
    grid, ground = L["grid"], L["ground"]
    granite = plain("Granite", (0.70, 0.66, 0.60), 0.85, tex_name="Concrete034", repeat=3.0)
    asphalt = plain("Bridge road", (0.25, 0.25, 0.27), 0.7, tex_name="Asphalt012", repeat=6.0)
    iron = plain("Lamp iron", (0.08, 0.09, 0.08), 0.5, 0.7)
    bulb = plain("Lamp glow", (1, 0.8, 0.5), 0.3, emission=LAMP_RGB, strength=12.0)
    cars = [plain(f"Car {k}", c, 0.3, 0.5) for k, c in enumerate(CAR_COLORS)]
    d = Mesh("Details")      # 0 granite, 1 asphalt, 2 iron, 3 bulb, 4.. cars
    d.cur = {"lit": 0.0, "seed": 0.0}
    for (ax, ay), (bx, by) in L["bridges"]:
        p0, p1 = Vector(m(ax, ay)), Vector(m(bx, by))
        u = (p1 - p0).normalized()
        n = Vector((-u.y, u.x))
        hw = 2.6 * C / 2 + 1.5
        a, b = p0, p1
        corners = [a - n * hw, b - n * hw, b + n * hw, a + n * hw]
        d.face([(c.x, c.y, 1.2) for c in corners], 1, (1, 1, 1), 1.0)
        for side in (-1, 1):
            e0, e1 = a + n * side * hw, b + n * side * hw
            d.wall((e0.x, e0.y), (e1.x, e1.y), -2.0, 2.4, 0, (1, 1, 1))                     # face and balustrade
            ln = (p1 - p0).length
            for k in range(int(ln / 9)):                                                        # piers between arches
                c = a + u * (k + 0.5) * ln / int(ln / 9) + n * side * (hw + 0.4)
                d.box(c.x - 1.2, c.y - 1.2, c.x + 1.2, c.y + 1.2, -2.0, 2.8, 0)
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            for side in (-1, 1):
                c = a + (b - a) * t + n * side * (hw - 0.4)
                d.cylinder(c.x, c.y, 0.14, 0.1, 1.2, 6, 2, seg=6, cap=False)
                d.blob(c.x, c.y, 6.2, 0.4, 1.0, 3)
                light(c.x, c.y, 6, LAMP_RGB, 1500, 0.2, anim="lamp", size=0.9)
    # (The banks are painted by the ground material's quay band; cell-stepped walls looked jagged on the curves)
    # Street lamps, lit for the evening (PxBackdropLights animates them in game)
    for y in range(1, NY - 1):
        for x in range(1, NX - 1):
            if ground[y][x] != "a" or grid[y][x] != "." or (x * 7 + y * 13) % 6:
                continue
            if not any(grid[y + dy][x + dx] == "#" or ground[y + dy][x + dx] in "yp" for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            px, py = m(x + 0.5, y + 0.5)
            d.cylinder(px, py, 0.14, 0.1, 0, 6, 2, seg=6, cap=False)
            d.box(px - 0.05, py - 0.05, px + 0.9, py + 0.05, 5.8, 6.0, 2)
            d.blob(px + 0.9, py, 5.7, 0.35, 0.8, 3)
            light(px + 0.9, py, 5.6, LAMP_RGB, 2200, 0.2, anim="lamp", size=1.0)
    for _ in range(220):
        x, y = rng.randrange(NX), rng.randrange(NY)
        if ground[y][x] != "a" or grid[y][x] != ".":
            continue
        cx, cy = m(x + rng.random(), y + rng.random())
        horiz = 0 < x < NX - 1 and ground[y][x + 1] == "a" and ground[y][x - 1] == "a"
        a = (0 if horiz else math.pi / 2) + rng.uniform(-0.05, 0.05)
        ln, wd = rng.uniform(4.2, 5.0), 1.9
        ca, sa = math.cos(a), math.sin(a)
        cs = [(cx + ca * u - sa * v, cy + sa * u + ca * v) for u, v in ((-ln / 2, -wd / 2), (ln / 2, -wd / 2), (ln / 2, wd / 2), (-ln / 2, wd / 2))]
        mat = 4 + rng.randrange(len(CAR_COLORS))
        for z0, z1, s in ((0.3, 1.0, 1.0), (1.0, 1.5, 0.6)):
            pts = [(cx + (qx - cx) * s, cy + (qy - cy) * s) for qx, qy in cs]
            for i in range(4):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % 4]
                d.face([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], mat, (1, 1, 1), 0.0)
            d.face([(qx, qy, z1) for qx, qy in pts], mat, (1, 1, 1), 1.0)
    d.finish([granite, asphalt, iron, bulb] + cars)


def setup(L, a):
    """Golden sunset: a low warm sun from the west-north-west (the game's light still comes from the top-left), long
    shadows to the east-south-east, a cool violet sky fill so shadows are not black."""
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
    bg.inputs[0].default_value = (0.66, 0.58, 0.62, 1)
    bg.inputs["Strength"].default_value = 1.05
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 6.5
    sun.data.angle = math.radians(1.2)
    sun.data.color = SUN_RGB
    travel = Vector((0.9, -0.42, -math.tan(math.radians(28)))).normalized()
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
    global BUILD_L
    a = args()
    t0 = time.time()
    with open(os.path.join(BUILD, "layout.json")) as f:
        L = json.load(f)
    BUILD_L = L
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(1791)
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
    make_lights()
    setup(L, a)
    t1 = time.time()
    print(f"SCENE BUILT in {t1 - t0:.1f}s")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "dc.blend"))
    if not a.no_render:
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y} "
              f"in {time.time() - t1:.1f}s -> {a.out}")


main()
