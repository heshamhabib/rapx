"""
RedAlert Project X - procedural tanks (1TNK, 2TNK, 3TNK, 4TNK), modelled after assets/units/<id>.png.

One parameterised builder; each tank is a SPECS entry. Every .blend has two roots:
  Hull    tracks, hull and skirts, turned for the body facings
  Turret  turret and guns, built around its ring so it can turn on its own
The turret ring sits on the origin: the engine draws the turret sprite at the actor's centre.

  Blender -b -P artsrc/units/tanks/build_tanks.py -- <id>      -> artsrc/units/tanks/<id>.blend

Prints the muzzle positions in WDist for the Armament LocalOffset in rules/vehicles.yaml.
"""

import math
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tank"))
from build_tank import (box, cylinder, extrude_polygon, extrude_profile, link, make_paint, make_simple,  # noqa: E402
                        make_tracks, mesh_from_bmesh, reset_scene)

# World px per Blender unit used by render_tank.py; converts model units to WDist (1024 per 24px cell)
UNIT_PX = 3.5
WDIST_PER_UNIT = 1024 / 24 * UNIT_PX

ALLIED = dict(paint=(0.05, 0.06, 0.075), wear=(0.36, 0.37, 0.4))
SOVIET = dict(paint=(0.07, 0.064, 0.038), wear=(0.24, 0.1, 0.045))

SPECS = {
    # Allied light tank: low angular hull, small wedge turret, single long gun
    "1tnk": dict(faction=ALLIED, length=6.0, width=3.3, track_w=0.62, hull_h=1.22, wheels=5, double_tracks=False,
                 turret=dict(shape="angular", length=2.7, width=2.1, height=0.6, y=-0.35),
                 guns=dict(count=1, length=3.0, radius=0.07, spacing=0.0, fume=False, brake=False),
                 extras=("cupola", "rws", "antennas")),
    # Allied medium tank: bigger wedge turret with bustle, fume extractor on the gun
    "2tnk": dict(faction=ALLIED, length=6.9, width=3.6, track_w=0.7, hull_h=1.35, wheels=6, double_tracks=False,
                 turret=dict(shape="angular", length=3.3, width=2.7, height=0.72, y=-0.45),
                 guns=dict(count=1, length=4.0, radius=0.085, spacing=0.0, fume=True, brake=False),
                 extras=("cupola", "rws", "antennas", "sights")),
    # Soviet heavy tank: rounded turret, twin barrels with muzzle brakes
    "3tnk": dict(faction=SOVIET, length=7.3, width=3.8, track_w=0.75, hull_h=1.4, wheels=6, double_tracks=False,
                 turret=dict(shape="round", radius=1.45, height=0.85, y=-0.2),
                 guns=dict(count=2, length=3.6, radius=0.1, spacing=0.62, fume=False, brake=True),
                 extras=("cupola", "antennas")),
    # Soviet mammoth tank: double tracks each side, huge turret, twin guns and missile pods
    "4tnk": dict(faction=SOVIET, length=8.4, width=4.9, track_w=0.72, hull_h=1.55, wheels=6, double_tracks=True,
                 turret=dict(shape="round", radius=1.8, height=1.0, y=-0.35),
                 guns=dict(count=2, length=4.0, radius=0.12, spacing=0.72, fume=False, brake=True),
                 extras=("cupola", "antennas", "pods")),
}


def stadium(y0, y1, r, zc, steps=12):
    """Side profile (y, z) of a track run: two half circles joined by straight runs."""
    prof = []
    for i in range(steps):
        a = math.pi / 2 + i / (steps - 1) * math.pi
        prof.append((y0 + r * math.cos(a), zc + r * math.sin(a)))
    for i in range(steps):
        a = -math.pi / 2 + i / (steps - 1) * math.pi
        prof.append((y1 + r * math.cos(a), zc + r * math.sin(a)))
    return prof


def scaled(poly, s):
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in poly]


def frustum(name, center, r0, r1, depth, mat, parent, segments=36):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r0, radius2=r1, depth=depth)
    obj = mesh_from_bmesh(name, bm, mat, parent, smooth=True)
    obj.location = center
    return obj


def build_hull(spec, mats, cy):
    """Hull centred at y = cy so the turret ring (spec turret y) lands on the origin."""
    paint, team, tracks, steel, dark, light = (mats[k] for k in ("paint", "team", "tracks", "steel", "dark", "light"))
    hull = link(bpy.data.objects.new("Hull", None))
    L, W, tw, hh = spec["length"], spec["width"], spec["track_w"], spec["hull_h"]
    hw = W / 2
    y0, y1 = cy - L / 2, cy + L / 2

    track_xs = [hw - tw / 2]
    if spec["double_tracks"]:
        track_xs.append(hw - tw * 1.5 - 0.1)
    inner = min(track_xs) - tw / 2
    for side in (-1, 1):
        for k, tx in enumerate(track_xs):
            x = side * tx
            extrude_profile(f"Track{side}_{k}", stadium(y0 + 0.55, y1 - 0.45, 0.47, 0.48), x - tw / 2, x + tw / 2,
                            tracks, hull, bevel_w=0.02)
        outer = side * (hw + 0.005)
        n = spec["wheels"]
        for i in range(n):
            y = y0 + 0.75 + i * (L - 1.4) / (n - 1)
            cylinder(f"Wheel{side}_{i}", (outer, y, 0.44), 0.34, 0.06, steel, hull, axis="X")
            cylinder(f"Hub{side}_{i}", (outer + side * 0.04, y, 0.44), 0.11, 0.05, dark, hull, axis="X")

        # Armoured side skirt with a team-colour band, split by dark straps
        box(f"Skirt{side}", (side * (hw + 0.04), cy - 0.1, 0.9), (0.08, L - 1.0, 0.56), paint, hull, bevel_w=0.02)
        band0, band1 = y0 + 0.7, y1 - 0.9
        box(f"SkirtTeam{side}", (side * (hw + 0.085), (band0 + band1) / 2, 0.86), (0.02, band1 - band0, 0.3), team, hull, bevel_w=0)
        k = 0
        y = band0 + 1.3
        while y < band1 - 0.4:
            box(f"Strap{side}_{k}", (side * (hw + 0.1), y, 0.88), (0.03, 0.12, 0.5), dark, hull, bevel_w=0)
            y += 1.3
            k += 1
        cylinder(f"Headlight{side}", (side * (hw - 0.45), y1 + 0.02, 1.12), 0.07, 0.06, light, hull, axis="Y")
        box(f"Hook{side}", (side * 0.75, y1 - 0.05, 0.62), (0.14, 0.2, 0.14), dark, hull)
        box(f"Exhaust{side}", (side * (hw - 0.8), y0 - 0.02, 1.05), (0.5, 0.1, 0.16), dark, hull)
        box(f"Stowage{side}", (side * (hw - 0.35), y0 + 1.3, hh + 0.12), (0.45, 1.2, 0.25), paint, hull)

    extrude_profile("LowerHull", [(y0 + 0.25, 0.42), (y1 - 0.45, 0.42), (y1, 0.95), (y0, 0.95)], -inner, inner, paint, hull)
    extrude_profile("UpperHull", [(y0 - 0.05, 0.95), (y1 - 0.1, 0.95), (y1 + 0.1, 1.08), (y1 - 1.5, hh), (y0 + 0.15, hh),
                                  (y0 - 0.05, hh - 0.2)], -(hw - 0.02), hw - 0.02, paint, hull, bevel_w=0.04)
    for i in range(7):
        box(f"Grille{i}", (0, y0 + 0.55 + i * 0.17, hh + 0.005), (W * 0.45, 0.07, 0.03), dark, hull, bevel_w=0)
    box("DriverHatch", (0.45, y1 - 1.75, hh + 0.02), (0.6, 0.45, 0.05), paint, hull)
    # Dark turret ring on the deck (the turret sprite is drawn over it)
    ring = spec["turret"].get("radius", min(spec["turret"].get("width", 2.0), spec["turret"].get("length", 2.0)) * 0.42)
    cylinder("TurretRing", (0, 0, hh + 0.02), ring * 0.9, 0.05, dark, hull, bevel_w=0)
    return hull


def build_turret(spec, mats, hh):
    paint, team, steel, dark, glass = (mats[k] for k in ("paint", "team", "steel", "dark", "glass"))
    t, g, extras = spec["turret"], spec["guns"], spec["extras"]
    turret = link(bpy.data.objects.new("Turret", None))
    turret.location = (0, 0, hh)

    if t["shape"] == "angular":
        tl, twd, th = t["length"], t["width"], t["height"]
        shell = [(-0.42 * twd, 0.55 * tl), (0.42 * twd, 0.55 * tl), (0.5 * twd, 0.18 * tl), (0.5 * twd, -0.35 * tl),
                 (0.4 * twd, -0.45 * tl), (-0.4 * twd, -0.45 * tl), (-0.5 * twd, -0.35 * tl), (-0.5 * twd, 0.18 * tl)]
        taper = 0.88
        extrude_polygon("TurretShell", shell, 0.0, th, paint, turret, top_scale=taper, bevel_w=0.05)
        # Team band following the sloped sides at mid height
        z0, z1 = th * 0.38, th * 0.68
        s0, s1 = 1 - (1 - taper) * z0 / th + 0.018, 1 - (1 - taper) * z1 / th + 0.018
        extrude_polygon("TurretTeam", scaled(shell, s0), z0, z1, team, turret, top_scale=s1 / s0, bevel_w=0)
        extrude_polygon("Bustle", [(-0.38 * twd, -0.45 * tl), (0.38 * twd, -0.45 * tl), (0.33 * twd, -0.66 * tl),
                                   (-0.33 * twd, -0.66 * tl)], 0.1, th * 0.8, paint, turret, bevel_w=0.03)
        front, top, half_w = 0.55 * tl, th, 0.5 * twd
    else:
        r, th = t["radius"], t["height"]
        frustum("TurretBase", (0, 0, th * 0.3), r, r * 0.97, th * 0.6, paint, turret)
        frustum("TurretDome", (0, -0.05, th * 0.8), r * 0.97, r * 0.72, th * 0.4, paint, turret)
        frustum("TurretTeam", (0, 0, th * 0.34), r + 0.03, r + 0.02, th * 0.26, team, turret)
        box("TurretBustle", (0, -r * 0.95, th * 0.45), (r * 1.1, r * 0.5, th * 0.7), paint, turret, bevel_w=0.05)
        front, top, half_w = r * 0.9, th, r

    # Mantlet and guns
    gz = top * 0.5
    span = g["spacing"] * (g["count"] - 1)
    box("Mantlet", (0, front + 0.12, gz), (span + 0.75, 0.45, top * 0.62), paint, turret, bevel_w=0.04)
    tips = []
    for k in range(g["count"]):
        gx = -span / 2 + k * g["spacing"]
        y_start = front + 0.3
        y_tip = y_start + g["length"]
        cylinder(f"Barrel{k}", (gx, (y_start + y_tip) / 2, gz), g["radius"], g["length"], steel, turret, axis="Y", bevel_w=0)
        cylinder(f"Sleeve{k}", (gx, y_start + 0.45, gz), g["radius"] * 1.6, 0.9, paint, turret, axis="Y")
        if g["fume"]:
            cylinder(f"Fume{k}", (gx, y_start + g["length"] * 0.6, gz), g["radius"] * 1.65, 0.5, paint, turret, axis="Y")
        if g["brake"]:
            cylinder(f"Brake{k}", (gx, y_tip - 0.18, gz), g["radius"] * 1.7, 0.36, dark, turret, axis="Y")
        else:
            cylinder(f"Muzzle{k}", (gx, y_tip - 0.1, gz), g["radius"] * 1.3, 0.2, dark, turret, axis="Y")
        tips.append((gx, y_tip, hh + gz))

    if "cupola" in extras:
        cylinder("Cupola", (half_w * 0.45, -0.3, top + 0.12), 0.32, 0.24, paint, turret)
        cylinder("CupolaHatch", (half_w * 0.45, -0.3, top + 0.26), 0.27, 0.05, paint, turret)
    if "rws" in extras:
        box("RWS", (-half_w * 0.4, 0.2, top + 0.17), (0.3, 0.38, 0.22), dark, turret)
        cylinder("RWSGun", (-half_w * 0.4, 0.7, top + 0.19), 0.03, 0.75, steel, turret, axis="Y", bevel_w=0)
    if "sights" in extras:
        box("Sight", (half_w * 0.55, front * 0.55, top + 0.14), (0.4, 0.45, 0.28), paint, turret)
        box("SightGlass", (half_w * 0.55, front * 0.55 + 0.23, top + 0.15), (0.3, 0.03, 0.15), glass, turret, bevel_w=0)
    if "antennas" in extras:
        for side in (-1, 1):
            cylinder(f"Antenna{side}", (side * half_w * 0.6, -half_w * 0.9, top + 0.9), 0.022, 1.8, dark, turret,
                     bevel_w=0, segments=8)
    if "pods" in extras:
        # Missile pods on both turret sides, 2x2 tubes each with red warheads
        warhead = make_simple("Warhead", (0.5, 0.05, 0.03), roughness=0.4)
        for side in (-1, 1):
            px = side * (half_w + 0.35)
            box(f"Pod{side}", (px, 0.0, top * 0.62), (0.62, 1.2, 0.62), paint, turret, bevel_w=0.04)
            for i in (-1, 1):
                for j in (-1, 1):
                    cylinder(f"Tube{side}{i}{j}", (px + i * 0.15, 0.61, top * 0.62 + j * 0.15), 0.1, 0.04, dark, turret,
                             axis="Y", bevel_w=0)
                    cylinder(f"Warhead{side}{i}{j}", (px + i * 0.15, 0.6, top * 0.62 + j * 0.15), 0.07, 0.04, warhead,
                             turret, axis="Y", bevel_w=0)
    return turret, tips


def build(tank_id):
    spec = SPECS[tank_id]
    reset_scene()
    f = spec["faction"]
    mats = dict(
        paint=make_paint("Paint", f["paint"], wear_color=f["wear"]),
        team=make_simple("TeamColor", (0.02, 0.85, 0.02), roughness=0.45),
        tracks=make_tracks("Tracks"),
        steel=make_simple("Steel", (0.18, 0.18, 0.19), metallic=1.0, roughness=0.38),
        dark=make_simple("DarkMetal", (0.03, 0.03, 0.032), metallic=0.6, roughness=0.5),
        glass=make_simple("Optics", (0.02, 0.05, 0.06), metallic=0.2, roughness=0.05),
        light=make_simple("Headlight", (0.9, 0.9, 0.8), roughness=0.2, emission=(1.0, 0.9, 0.7)),
    )
    build_hull(spec, mats, -spec["turret"]["y"])
    _, tips = build_turret(spec, mats, spec["hull_h"])

    out = os.path.join(HERE, f"{tank_id}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    offsets = ", ".join(f"{round(y * WDIST_PER_UNIT)},{round(-x * WDIST_PER_UNIT)},{round(z * WDIST_PER_UNIT)}"
                        for x, y, z in tips)
    print(f"saved {out}")
    print(f"muzzle LocalOffset {tank_id}: {offsets}")


if __name__ == "__main__":
    build(sys.argv[sys.argv.index("--") + 1])
