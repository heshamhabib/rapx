"""
RedAlert Project X - procedural support vehicles, modelled after assets/units/<id>.png.

  jeep  Ranger: armoured 4x4 with a roof gun turret (separate "Turret" root)
  apc   APC: tracked armoured box with a fixed machine-gun cupola
  arty  Artillery: tracked hull with a big rear turret and long gun (fixed, the hull turns to fire)
  v2rl  V2 launcher: 4-axle truck carrying a V2 rocket ("Rocket" group, hidden while reloading)

Every .blend has a "Body" root centred on the actor position (and "Turret" for the jeep).

  Blender -b -P artsrc/units/vehicles/build_vehicles.py -- <id>      -> artsrc/units/vehicles/<id>.blend

Prints the muzzle positions (model WDist; scale by ~0.88 forward / ~0.64 up for Armament LocalOffset).
"""

import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tank"))
sys.path.insert(0, os.path.join(HERE, "..", "tanks"))
sys.path.insert(0, os.path.join(HERE, "..", "minelayer"))
from build_minelayer import make_hazard, placed_box  # noqa: E402
from build_tank import (box, cylinder, extrude_profile, link, make_paint, make_simple, make_tracks,  # noqa: E402
                        reset_scene)
from build_tanks import ALLIED, SOVIET, WDIST_PER_UNIT, build_hull, build_turret, frustum  # noqa: E402


def materials(faction):
    return dict(
        paint=make_paint("Paint", faction["paint"], wear_color=faction["wear"]),
        team=make_simple("TeamColor", (0.02, 0.85, 0.02), roughness=0.45),
        tracks=make_tracks("Tracks"),
        rubber=make_tracks("Tyres"),
        steel=make_simple("Steel", (0.18, 0.18, 0.19), metallic=1.0, roughness=0.38),
        dark=make_simple("DarkMetal", (0.03, 0.03, 0.032), metallic=0.6, roughness=0.5),
        glass=make_simple("Glass", (0.01, 0.02, 0.03), metallic=0.5, roughness=0.15),
        light=make_simple("Headlight", (0.9, 0.9, 0.8), roughness=0.2, emission=(1.0, 0.95, 0.8)),
        amber=make_simple("Amber", (0.9, 0.45, 0.05), roughness=0.3, emission=(1.0, 0.5, 0.05)),
    )


def tyre(name, x, y, r, w, m, parent):
    cylinder(f"{name}Tyre", (x, y, r), r, w, m["rubber"], parent, axis="X", segments=32)
    cylinder(f"{name}Rim", (x + math.copysign(0.02, x), y, r), r * 0.55, w, m["steel"], parent, axis="X")
    cylinder(f"{name}Hub", (x + math.copysign(w / 2 + 0.02, x), y, r), r * 0.2, 0.05, m["dark"], parent, axis="X")


def centre(body, shift):
    """Moves everything under Body by -shift in y so the vehicle turns about its middle."""
    for child in body.children:
        child.location.y -= shift


def muzzles(tips):
    return ", ".join(f"{round(y * WDIST_PER_UNIT)},{round(-x * WDIST_PER_UNIT)},{round(z * WDIST_PER_UNIT)}"
                     for x, y, z in tips)


def jeep():
    m = materials(ALLIED)
    body = link(bpy.data.objects.new("Body", None))
    for side in (-1, 1):
        for i, y in enumerate((1.55, -1.55)):
            tyre(f"W{side}{i}", side * 1.18, y, 0.56, 0.46, m, body)
        box(f"Flare{side}F", (side * 1.25, 1.55, 1.18), (0.3, 1.3, 0.12), m["paint"], body)
        box(f"Flare{side}R", (side * 1.25, -1.55, 1.18), (0.3, 1.3, 0.12), m["paint"], body)
        box(f"Headlight{side}", (side * 0.8, 2.47, 1.3), (0.3, 0.04, 0.14), m["light"], body, bevel_w=0)
        box(f"SideWindow{side}", (side * 1.16, -0.55, 2.05), (0.03, 1.8, 0.45), m["glass"], body, bevel_w=0)
        box(f"Mirror{side}", (side * 1.3, 0.95, 1.95), (0.08, 0.1, 0.3), m["dark"], body)
        cylinder(f"Antenna{side}", (side * 0.95, -2.1, 3.3), 0.02, 1.7, m["dark"], body, bevel_w=0, segments=8)
    box("Chassis", (0, 0, 0.75), (2.2, 4.6, 0.4), m["dark"], body)
    extrude_profile("Lower", [(-2.45, 0.75), (2.3, 0.75), (2.5, 1.1), (2.4, 1.45), (1.2, 1.62), (-2.45, 1.62)],
                    -1.25, 1.25, m["paint"], body, bevel_w=0.05)
    extrude_profile("Cabin", [(-2.35, 1.6), (1.15, 1.6), (0.6, 2.45), (-2.35, 2.45)], -1.15, 1.15, m["paint"], body,
                    bevel_w=0.05)
    ang = math.atan2(1.15 - 0.6, 2.45 - 1.6)
    placed_box("Windscreen", (0, 0.9, 2.03), (1.9, 0.04, 0.6), m["glass"], body, rot_x=ang, bevel_w=0)
    box("BullBar", (0, 2.6, 1.05), (2.0, 0.12, 0.5), m["dark"], body)
    box("Grille", (0, 2.49, 1.28), (0.9, 0.04, 0.25), m["dark"], body, bevel_w=0)
    # Team stripe down the middle of the hood and roof
    box("HoodTeam", (0, 1.85, 1.57), (0.55, 1.1, 0.04), m["team"], body, bevel_w=0)
    box("RoofTeam", (0, -0.95, 2.47), (0.55, 2.7, 0.04), m["team"], body, bevel_w=0)
    cylinder("Spare", (0, -2.55, 1.45), 0.42, 0.25, m["rubber"], body, axis="Y")

    # Roof gun turret, its ring on the actor centre
    shift = -0.55
    turret = link(bpy.data.objects.new("Turret", None))
    turret.location = (0, 0, 2.45)
    cylinder("TurretRing", (0, 0, 0.06), 0.4, 0.12, m["dark"], turret)
    box("GunHousing", (0, 0.05, 0.32), (0.42, 0.6, 0.34), m["paint"], turret, bevel_w=0.03)
    box("Shield", (0, 0.42, 0.36), (0.7, 0.05, 0.4), m["paint"], turret)
    box("Ammo", (0.3, -0.1, 0.3), (0.18, 0.3, 0.2), m["dark"], turret)
    cylinder("MG", (0, 0.95, 0.38), 0.035, 1.1, m["steel"], turret, axis="Y", bevel_w=0)
    centre(body, shift)
    return [(0, 1.5, 2.45 + 0.38)]


def apc():
    m = materials(SOVIET)
    spec = dict(length=6.2, width=3.2, track_w=0.6, hull_h=1.3, wheels=5, double_tracks=False,
                turret=dict(radius=0.4, y=0.0))
    hull = build_hull(spec, m, 0.0)
    hull.name = "Body"
    # Tall armoured box on top with a team band along its sides, rear door and an MG cupola
    extrude_profile("Superstructure", [(-3.05, 1.28), (1.55, 1.28), (0.85, 2.2), (-3.05, 2.2)], -1.45, 1.45,
                    m["paint"], hull, bevel_w=0.05)
    for side in (-1, 1):
        box(f"BoxTeam{side}", (side * 1.465, -1.0, 1.85), (0.03, 3.6, 0.28), m["team"], hull, bevel_w=0)
        box(f"Vision{side}", (side * 1.465, 0.35, 2.02), (0.03, 0.5, 0.1), m["glass"], hull, bevel_w=0)
    box("RearDoor", (0, -3.07, 1.7), (1.4, 0.04, 0.8), m["dark"], hull, bevel_w=0)
    box("Hatch", (-0.6, -1.6, 2.23), (0.8, 0.9, 0.05), m["paint"], hull)
    cylinder("Cupola", (0.2, -0.2, 2.32), 0.42, 0.24, m["paint"], hull)
    box("MGMount", (0.2, 0.15, 2.5), (0.25, 0.45, 0.2), m["dark"], hull)
    cylinder("MG", (0.2, 0.95, 2.52), 0.035, 1.2, m["steel"], hull, axis="Y", bevel_w=0)
    return [(0.2, 1.55, 2.52)]


def arty():
    m = materials(ALLIED)
    spec = dict(length=6.6, width=3.4, track_w=0.62, hull_h=1.25, wheels=6, double_tracks=False,
                turret=dict(shape="angular", length=3.0, width=2.6, height=1.0, y=0.0),
                guns=dict(count=1, length=4.4, radius=0.1, spacing=0.0, fume=True, brake=True),
                extras=("cupola", "antennas"))
    hull = build_hull(spec, m, 0.0)
    hull.name = "Body"
    bpy.data.objects["TurretRing"].hide_render = True
    turret, tips = build_turret(spec, m, spec["hull_h"])
    # The gun house sits towards the rear and turns with the hull
    turret_y = -0.95
    turret.parent = hull
    turret.location = (0, turret_y, spec["hull_h"])
    for side in (-1, 1):
        box(f"HouseTeam{side}", (side * 1.33, turret_y - 0.2, spec["hull_h"] + 0.55), (0.03, 2.2, 0.22), m["team"],
            hull, bevel_w=0)
        box(f"Spade{side}", (side * 1.2, -3.35, 0.75), (0.5, 0.15, 0.6), m["dark"], hull)
    return [(x, y + turret_y, z) for x, y, z in tips]


def v2rl():
    m = materials(SOVIET)
    hazard = make_hazard("Hazard")
    rust = make_paint("Rust", (0.16, 0.06, 0.03), wear_color=(0.3, 0.2, 0.12))
    body = link(bpy.data.objects.new("Body", None))
    axles = (2.55, 1.2, -1.6, -2.95)
    for side in (-1, 1):
        for i, y in enumerate(axles):
            tyre(f"W{side}{i}", side * 1.22, y, 0.56, 0.44, m, body)
        box(f"CabWindow{side}", (side * 1.26, 3.0, 2.15), (0.03, 0.8, 0.45), m["glass"], body, bevel_w=0)
        box(f"CabTeam{side}", (side * 1.265, 2.45, 1.7), (0.03, 0.35, 1.1), m["team"], body, bevel_w=0)
        box(f"Headlight{side}", (side * 0.85, 3.97, 1.4), (0.3, 0.04, 0.14), m["light"], body, bevel_w=0)
        box(f"Marker{side}", (side * 1.15, 3.95, 2.62), (0.12, 0.05, 0.08), m["amber"], body, bevel_w=0)
        box(f"BedRail{side}", (side * 1.2, -1.1, 1.42), (0.12, 4.9, 0.2), m["paint"], body)
        rod_y = -0.2
        box(f"Cradle{side}", (side * 0.4, rod_y, 2.0), (0.15, 0.25, 1.1), m["dark"], body)
        box(f"Cradle2{side}", (side * 0.4, -2.6, 2.0), (0.15, 0.25, 1.1), m["dark"], body)
    box("Chassis", (0, -0.1, 0.85), (2.2, 7.6, 0.4), m["dark"], body)
    extrude_profile("Cab", [(1.85, 1.05), (3.95, 1.05), (3.95, 1.9), (3.65, 2.6), (1.85, 2.6)], -1.25, 1.25,
                    m["paint"], body, bevel_w=0.05)
    placed_box("Windscreen", (0, 3.82, 2.27), (2.0, 0.04, 0.6), m["glass"], body, rot_x=math.atan2(0.3, 0.7),
               bevel_w=0)
    box("Grille", (0, 3.97, 1.45), (1.1, 0.04, 0.5), m["dark"], body, bevel_w=0)
    box("Bed", (0, -1.05, 1.18), (2.45, 5.6, 0.25), m["paint"], body)
    box("BedStripe", (0, -3.86, 1.1), (2.4, 0.05, 0.3), hazard, body, bevel_w=0)
    box("Launcher", (0, -1.3, 1.55), (0.7, 4.6, 0.25), m["dark"], body)

    # The rocket, lying on its cradle with the nose over the cab; fins are team-coloured
    rocket = link(bpy.data.objects.new("Rocket", None), body)
    rocket.location = (0, -0.8, 2.95)
    cylinder("RocketBody", (0, 0, 0), 0.48, 4.6, rust, rocket, axis="Y")
    for k, y in enumerate((-1.4, 0.6)):
        cylinder(f"RocketBand{k}", (0, y, 0), 0.5, 0.18, m["paint"], rocket, axis="Y")
    nose = frustum("RocketNose", (0, 2.95, 0), 0.48, 0.04, 1.3, rust, rocket)
    nose.rotation_euler = (-math.pi / 2, 0, 0)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        fin = box(f"Fin{k}", (0, 0, 0), (0.06, 0.8, 0.55), m["team"], rocket, bevel_w=0.01)
        fin.location = (math.cos(a) * 0.68, -2.1, math.sin(a) * 0.68)
        fin.rotation_euler = (0, -a + math.pi / 2, 0)
    centre(body, 0.2)
    return []


BUILDERS = dict(jeep=jeep, apc=apc, arty=arty, v2rl=v2rl)


def build(vid):
    reset_scene()
    tips = BUILDERS[vid]()
    out = os.path.join(HERE, f"{vid}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f"saved {out}")
    if tips:
        print(f"muzzle LocalOffset {vid}: {muzzles(tips)}")


if __name__ == "__main__":
    build(sys.argv[sys.argv.index("--") + 1])
