"""
RedAlert Project X - procedural armoured minelayer (MNLY), modelled after
~/Downloads/Futuristic Armored Mine-Laying Vehicle.png.

Front cab with two windscreens, roof sensors, open mine bay at the rear and an inclined
mine conveyor rising over the back. The green skirt panels are the team colour
(pure green, hue ~0.33, so PlayerColorShift can recolour them in-game).

Single object hierarchy "Body" (no turret). Saves minelayer.blend.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/units/minelayer/build_minelayer.py
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tank"))
from build_tank import (box, cylinder, extrude_profile, link, make_paint, make_simple,  # noqa: E402
                        make_tracks, node_mat, reset_scene)

OUT_BLEND = os.path.join(HERE, "minelayer.blend")

# Olive-grey armour (linear RGB)
PAINT = (0.095, 0.092, 0.062)


def make_hazard(name):
    """Diagonal yellow/black warning stripes."""
    mat, nt, bsdf = node_mat(name)
    N, L = nt.nodes, nt.links
    tex = N.new("ShaderNodeTexCoord")
    wave = N.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.inputs["Scale"].default_value = 2.2
    L.new(tex.outputs["Object"], wave.inputs["Vector"])
    step = N.new("ShaderNodeMath")
    step.operation = "GREATER_THAN"
    step.inputs[1].default_value = 0.5
    L.new(wave.outputs["Fac"], step.inputs[0])
    col = N.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.inputs["A"].default_value = (0.015, 0.015, 0.012, 1)
    col.inputs["B"].default_value = (0.75, 0.5, 0.02, 1)
    L.new(step.outputs["Value"], col.inputs["Factor"])
    L.new(col.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def placed_box(name, center, size, mat, parent, rot_x=0.0, bevel_w=0.02):
    obj = box(name, (0, 0, 0), size, mat, parent, bevel_w=bevel_w)
    obj.location = center
    obj.rotation_euler = (rot_x, 0, 0)
    return obj


def rod(name, p0, p1, radius, mat, parent):
    """Cylinder between two points."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    obj = cylinder(name, (p0 + p1) / 2, radius, d.length, mat, parent, bevel_w=0, segments=12)
    obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return obj


def build():
    reset_scene()

    paint = make_paint("Paint", PAINT)
    team = make_simple("TeamColor", (0.02, 0.85, 0.02), roughness=0.45)
    team["px_team"] = True
    tracks = make_tracks("Tracks")
    steel = make_simple("Steel", (0.17, 0.17, 0.16), metallic=1.0, roughness=0.4)
    dark = make_simple("DarkMetal", (0.03, 0.03, 0.03), metallic=0.6, roughness=0.5)
    glass = make_simple("Glass", (0.01, 0.02, 0.03), metallic=0.5, roughness=0.15)
    lens = make_simple("Lens", (0.05, 0.2, 0.6), roughness=0.1, emission=(0.1, 0.4, 1.0))
    light = make_simple("Headlight", (0.9, 0.9, 0.8), roughness=0.2, emission=(1.0, 0.95, 0.8))
    hazard = make_hazard("Hazard")
    mine = make_simple("Mine", (0.13, 0.12, 0.08), metallic=0.5, roughness=0.45)
    mine_cap = make_simple("MineCap", (0.4, 0.04, 0.03), roughness=0.4)

    body = bpy.data.objects.new("Body", None)
    link(body)

    # ---- Hull: lower tub between the tracks, upper deck over the tracks
    extrude_profile("LowerHull", [(-3.4, 0.42), (3.2, 0.42), (3.6, 0.95), (-3.5, 0.95)], -1.15, 1.15, paint, body)
    extrude_profile("UpperHull", [(-3.65, 0.95), (3.55, 0.95), (3.75, 1.12), (3.65, 1.5), (-3.65, 1.5)],
                    -1.82, 1.82, paint, body, bevel_w=0.04)

    # ---- Running gear and team-colour skirts
    for side in (-1, 1):
        x = side * 1.47
        prof = []
        for i in range(24):
            a = math.pi / 2 + i / 23 * math.pi
            prof.append((-3.0 + 0.47 * math.cos(a), 0.48 + 0.47 * math.sin(a)))
        for i in range(24):
            a = -math.pi / 2 + i / 23 * math.pi
            prof.append((3.1 + 0.47 * math.cos(a), 0.48 + 0.47 * math.sin(a)))
        extrude_profile(f"Track{side}", prof, x - 0.36, x + 0.36, tracks, body, bevel_w=0.02)
        for i in range(7):
            y = -2.6 + i * 0.87
            cylinder(f"Wheel{side}_{i}", (x + side * 0.37, y, 0.42), 0.36, 0.06, steel, body, axis="X")
            cylinder(f"Hub{side}_{i}", (x + side * 0.41, y, 0.42), 0.12, 0.05, dark, body, axis="X")

        # Skirt: armour frame with green panels separated by black straps
        box(f"Skirt{side}", (side * 1.86, -0.05, 1.07), (0.08, 6.9, 0.74), paint, body, bevel_w=0.02)
        for i in range(4):
            y0 = -3.3 + i * 1.62
            box(f"Team{side}_{i}", (side * 1.91, y0 + 0.75, 1.07), (0.03, 1.42, 0.6), team, body, bevel_w=0)
            box(f"Strap{side}_{i}", (side * 1.92, y0 + 1.54, 1.07), (0.04, 0.14, 0.76), dark, body, bevel_w=0)

    # ---- Front: bumper, winch, tow hooks, lights
    box("Bumper", (0, 3.72, 0.95), (3.3, 0.22, 0.4), paint, body)
    cylinder("Winch", (0, 3.85, 0.78), 0.2, 1.1, steel, body, axis="X")
    for side in (-1, 1):
        box(f"Hook{side}", (side * 0.95, 3.88, 0.72), (0.14, 0.2, 0.16), dark, body)
        box(f"Light{side}", (side * 1.45, 3.7, 1.32), (0.4, 0.1, 0.14), light, body, bevel_w=0)

    # ---- Armoured cab with sloped windscreen
    slope0, slope1 = (3.55, 1.95), (2.7, 2.9)
    extrude_profile("Cab", [(0.4, 1.5), (3.62, 1.5), (3.62, 1.95), (slope0[0], slope0[1]), (slope1[0], slope1[1]),
                            (0.4, 2.9)], -1.65, 1.65, paint, body, bevel_w=0.05)
    ang = math.atan2(slope0[0] - slope1[0], slope1[1] - slope0[1])  # slope tilt from vertical
    mid = ((slope0[0] + slope1[0]) / 2, (slope0[1] + slope1[1]) / 2)
    n = (math.cos(ang), math.sin(ang))  # outward normal in (y, z)
    for side in (-1, 1):
        placed_box(f"Window{side}", (side * 0.78, mid[0] + n[0] * 0.03, mid[1] + n[1] * 0.03),
                   (1.15, 0.04, 0.8), glass, body, rot_x=ang, bevel_w=0)
        box(f"Mirror{side}", (side * 1.85, 2.9, 2.3), (0.08, 0.12, 0.35), dark, body)
    box("CabSide", (0, 1.3, 2.25), (3.45, 0.9, 1.1), paint, body, bevel_w=0.04)
    # Team stripe across the cab roof, behind the windscreen (visible from every facing)
    box("RoofTeam", (0, 2.45, 2.915), (3.0, 0.4, 0.03), team, body, bevel_w=0)

    # Roof kit: sensor pod with blue lens, hatches, antennas
    box("Sensor", (-0.75, 1.8, 3.15), (1.0, 0.8, 0.5), paint, body, bevel_w=0.04)
    box("SensorLens", (-1.1, 2.21, 3.15), (0.22, 0.03, 0.22), lens, body, bevel_w=0)
    cylinder("Hatch1", (0.7, 1.7, 2.95), 0.4, 0.12, paint, body)
    cylinder("Hatch2", (0.6, 0.75, 2.95), 0.36, 0.12, paint, body)
    cylinder("Antenna1", (-1.3, 1.2, 4.0), 0.025, 2.2, dark, body, bevel_w=0, segments=8)
    cylinder("Antenna2", (0.3, 0.4, 4.1), 0.025, 2.4, dark, body, bevel_w=0, segments=8)

    # ---- Mid section: engine/equipment block
    box("Equipment", (0, 0.0, 2.0), (3.4, 0.9, 1.0), paint, body, bevel_w=0.04)
    for i in range(5):
        box(f"Grille{i}", (1.71, -0.3 + i * 0.15, 2.0), (0.03, 0.08, 0.7), dark, body, bevel_w=0)

    # ---- Mine bay at the rear: low walls with rows of mines
    for side in (-1, 1):
        box(f"BayWall{side}", (side * 1.6, -2.0, 1.95), (0.14, 3.2, 0.9), paint, body)
        box(f"BayWallTeam{side}", (side * 1.6, -2.0, 2.41), (0.16, 3.0, 0.03), team, body, bevel_w=0)
    box("BayRear", (0, -3.55, 1.85), (3.3, 0.14, 0.7), paint, body)
    for i in range(3):
        for j in (-1, 1):
            cx, cy = j * 1.0, -1.2 - i * 0.85
            if abs(cx - 0.2) < 0.9:
                continue  # conveyor sits in the middle
            cylinder(f"BayMine{i}{j}", (cx, cy, 1.62), 0.3, 0.2, mine, body)
            cylinder(f"BayMineCap{i}{j}", (cx, cy, 1.74), 0.08, 0.05, mine_cap, body, bevel_w=0)
    box("RearBox", (-1.1, -3.0, 2.35), (0.8, 0.8, 0.8), paint, body, bevel_w=0.04)

    # ---- Inclined mine conveyor rising over the back
    r0, r1 = Vector((0.2, -0.5, 1.75)), Vector((0.2, -3.75, 4.6))
    d = r1 - r0
    length = d.length
    tilt = math.atan2(d.z, -d.y)
    rx = -tilt  # box Y axis -> along the ramp (front-down to back-up)
    centre = (r0 + r1) / 2
    normal = Vector((0, math.sin(tilt), math.cos(tilt)))
    placed_box("RampBed", centre, (1.3, length, 0.12), dark, body, rot_x=rx, bevel_w=0)
    for side in (-1, 1):
        placed_box(f"Rail{side}", centre + Vector((side * 0.75, 0, 0.1)), (0.2, length, 0.38), hazard, body, rot_x=rx)
        rod(f"Ram{side}", (0.2 + side * 0.95, -2.2, 1.6), centre + Vector((side * 0.95, -0.4, -0.2)), 0.09, steel, body)
    for k in range(4):
        t = 0.25 + k * 0.2
        p = r0 + d * t + normal * 0.16
        disc = cylinder(f"RampMine{k}", (0, 0, 0), 0.38, 0.2, mine, body)
        disc.location = p
        disc.rotation_euler = (rx, 0, 0)
        cap = cylinder(f"RampMineCap{k}", (0, 0, 0), 0.1, 0.06, mine_cap, body, bevel_w=0)
        cap.location = p + normal * 0.12
        cap.rotation_euler = (rx, 0, 0)
    box("RampHead", (0.2, -3.85, 4.65), (1.9, 0.45, 0.45), paint, body, bevel_w=0.04)
    box("RampHeadTeam", (0.2, -3.85, 4.885), (1.7, 0.35, 0.03), team, body, bevel_w=0)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print("saved", OUT_BLEND)


if __name__ == "__main__":
    build()
