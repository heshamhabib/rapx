"""
RedAlert Project X - procedural ore truck (HARV), modelled after assets/units/harv.png.

Six-wheeled mining truck: armoured cab with a team-colour roof, a loader bucket on lift arms at
the front, and a tipping ore hopper with a team-colour band along each side.

Object groups the renderer animates (render_harvester.py):
  Body           root, turned for each facing
  Boom / Bucket  loader lift arms and bucket, dig and curl while harvesting
  Hopper         tips up around its rear hinge while unloading
  OreFull/OreHalf  ore piles inside the hopper (none = empty truck)
  Spray          ore chunks spilling off the bucket lip while harvesting
  Stream         ore falling out of the tipped hopper
  objects with px_ram / px_ram_tip  hydraulic rams, stretched each frame between those two empties

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/units/harvester/build_harvester.py
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tank"))
sys.path.insert(0, os.path.join(HERE, "..", "minelayer"))
from build_tank import (box, cylinder, extrude_profile, link, make_paint, make_simple,  # noqa: E402
                        make_tracks, mesh_from_bmesh, node_mat, reset_scene)
from build_minelayer import make_hazard, placed_box, rod  # noqa: E402

OUT_BLEND = os.path.join(HERE, "harvester.blend")

PAINT = (0.1, 0.09, 0.058)

# The hopper hinges at its rear bottom edge; its parts are modelled in world coordinates
# and converted with hp() into the hinge's local space.
HINGE = Vector((0, -4.0, 1.65))
# Loader boom pivot (body space) and the bucket hinge at the end of the lift arms (boom space)
BOOM_PIVOT = Vector((0, 2.2, 1.9))
CENTRE_SHIFT = 0.95
BUCKET_HINGE = Vector((0, 2.6, -0.95))


def hp(x, y, z):
    return (x - HINGE.x, y - HINGE.y, z - HINGE.z)


def make_ore(name):
    """Dark rock shot through with gold ore."""
    mat, nt, bsdf = node_mat(name)
    N, L = nt.nodes, nt.links
    tex = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.0
    noise.inputs["Detail"].default_value = 4.0
    L.new(tex.outputs["Object"], noise.inputs["Vector"])
    ramp = N.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.45
    ramp.inputs["From Max"].default_value = 0.6
    L.new(noise.outputs["Fac"], ramp.inputs["Value"])
    col = N.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.inputs["A"].default_value = (0.035, 0.03, 0.025, 1)
    col.inputs["B"].default_value = (0.75, 0.48, 0.06, 1)
    L.new(ramp.outputs["Result"], col.inputs["Factor"])
    L.new(col.outputs["Result"], bsdf.inputs["Base Color"])
    L.new(ramp.outputs["Result"], bsdf.inputs["Metallic"])
    bsdf.inputs["Roughness"].default_value = 0.5
    return mat


def rock(name, center, radius, mat, parent, rng):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius)
    for v in bm.verts:
        v.co *= rng.uniform(0.75, 1.15)
    obj = mesh_from_bmesh(name, bm, mat, parent)
    obj.location = center
    obj.rotation_euler = (rng.uniform(0, 6.3), rng.uniform(0, 6.3), rng.uniform(0, 6.3))
    obj.scale = (1, 1, rng.uniform(0.6, 0.9))
    return obj


def ore_pile(name, parent, ore, top, dome, rng):
    """Ore filling the hopper up to `top` (world z) with a heap of `dome` above it in the middle."""
    group = link(bpy.data.objects.new(name, None), parent)
    # Solid bed so no gaps show between the surface rocks
    floor = 2.1
    box(f"{name}Bed", hp(0, -1.95, (floor + top - 0.15) / 2), (2.9, 3.7, top - 0.15 - floor), ore, group, bevel_w=0)
    i = 0
    y = -3.65
    while y < -0.1:
        x = -1.25
        while x < 1.3:
            px, py = x + rng.uniform(-0.1, 0.1), y + rng.uniform(-0.1, 0.1)
            # Heap: highest over the middle of the bed, dropping to `top` at the walls
            u, v = px / 1.45, (py + 1.95) / 1.95
            h = top + dome * max(0.0, 1 - (u * u + v * v))
            r = rng.uniform(0.2, 0.3)
            rock(f"{name}Rock{i}", hp(px, py, h - r * 0.3), r, ore, group, rng)
            i += 1
            x += 0.4
        y += 0.4
    return group


def build():
    reset_scene()
    rng = random.Random(7)

    paint = make_paint("Paint", PAINT)
    team = make_simple("TeamColor", (0.02, 0.85, 0.02), roughness=0.45)
    team["px_team"] = True
    rubber = make_tracks("Tyres")
    steel = make_simple("Steel", (0.2, 0.2, 0.19), metallic=1.0, roughness=0.35)
    dark = make_simple("DarkMetal", (0.03, 0.03, 0.03), metallic=0.6, roughness=0.5)
    glass = make_simple("Glass", (0.01, 0.02, 0.03), metallic=0.5, roughness=0.15)
    light = make_simple("Headlight", (0.9, 0.9, 0.8), roughness=0.2, emission=(1.0, 0.95, 0.8))
    amber = make_simple("Amber", (0.9, 0.45, 0.05), roughness=0.3, emission=(1.0, 0.5, 0.05))
    brass = make_simple("Brass", (0.45, 0.32, 0.1), metallic=1.0, roughness=0.35)
    hazard = make_hazard("Hazard")
    ore = make_ore("Ore")

    body = link(bpy.data.objects.new("Body", None))

    # ---- Chassis and running gear: three axles of big off-road tyres
    box("Chassis", (0, -0.6, 1.25), (2.3, 7.6, 0.5), paint, body)
    for side in (-1, 1):
        for i, y in enumerate((0.9, -1.95, -3.8)):
            cylinder(f"Tyre{side}_{i}", (side * 1.5, y, 0.85), 0.85, 0.72, rubber, body, axis="X", segments=40)
            cylinder(f"Rim{side}_{i}", (side * 1.53, y, 0.85), 0.47, 0.72, steel, body, axis="X")
            cylinder(f"Hub{side}_{i}", (side * 1.88, y, 0.85), 0.18, 0.06, dark, body, axis="X")
        box(f"Fender{side}", (side * 1.5, 0.9, 1.8), (0.85, 2.0, 0.1), paint, body)
        box(f"FuelTank{side}", (side * 1.3, -0.45, 1.25), (0.4, 1.3, 0.6), paint, body)

    # ---- Cab with a team-colour roof
    extrude_profile("Cab", [(1.3, 1.5), (3.35, 1.5), (3.35, 2.25), (3.1, 2.95), (1.3, 2.95)],
                    -1.35, 1.35, paint, body, bevel_w=0.05)
    ang = math.atan2(3.35 - 3.1, 2.95 - 2.25)
    for side in (-1, 1):
        placed_box(f"Windscreen{side}", (side * 0.62, 3.25, 2.62), (1.0, 0.04, 0.55), glass, body, rot_x=ang, bevel_w=0)
        box(f"SideWindow{side}", (side * 1.36, 2.55, 2.55), (0.03, 0.8, 0.45), glass, body, bevel_w=0)
        box(f"Headlight{side}", (side * 0.95, 3.37, 1.95), (0.35, 0.04, 0.16), light, body, bevel_w=0)
        box(f"RoofLight{side}", (side * 1.05, 3.05, 3.02), (0.2, 0.08, 0.1), light, body, bevel_w=0)
        box(f"Marker{side}", (side * 1.37, 1.6, 1.9), (0.04, 0.12, 0.12), amber, body, bevel_w=0)
        box(f"Mirror{side}", (side * 1.55, 3.0, 2.5), (0.08, 0.1, 0.4), dark, body)
    box("Grille", (0, 3.37, 1.75), (1.0, 0.04, 0.35), dark, body, bevel_w=0)
    box("RoofTeam", (0, 2.15, 2.97), (2.55, 1.6, 0.04), team, body, bevel_w=0)
    cylinder("RoofDome", (-0.3, 1.7, 3.05), 0.32, 0.18, paint, body)
    cylinder("Antenna1", (-0.8, 1.6, 3.9), 0.025, 1.9, dark, body, bevel_w=0, segments=8)
    cylinder("Antenna2", (0.1, 1.45, 3.7), 0.025, 1.5, dark, body, bevel_w=0, segments=8)

    # ---- Engine bay between cab and hopper: block, exhaust stacks, filters
    box("Engine", (0, 0.85, 2.15), (2.4, 0.8, 1.3), paint, body)
    for side in (-1, 1):
        cylinder(f"Exhaust{side}", (side * 0.55, 0.85, 3.15), 0.15, 1.0, steel, body)
        cylinder(f"ExhaustCap{side}", (side * 0.55, 0.85, 3.67), 0.17, 0.08, dark, body)
        cylinder(f"Filter{side}", (side * 1.05, 0.75, 2.95), 0.22, 0.6, paint, body)
        box(f"EngineGrille{side}", (side * 1.21, 0.85, 2.15), (0.03, 0.55, 0.7), dark, body, bevel_w=0)
        box(f"Rail{side}", (side * 1.25, 0.4, 2.95), (0.04, 0.6, 0.04), brass, body, bevel_w=0)

    # ---- Loader at the front: lift arms on a boom pivot, curling bucket with teeth and hazard-striped sides
    box("FrontFrame", (0, 3.55, 1.25), (2.2, 0.5, 0.7), paint, body)
    for side in (-1, 1):
        box(f"BoomMount{side}", (side * 1.5, 2.2, 1.9), (0.3, 0.5, 0.6), dark, body)
    boom = link(bpy.data.objects.new("Boom", None), body)
    boom.location = BOOM_PIVOT
    for side in (-1, 1):
        rod(f"LiftArm{side}", (side * 1.5, 0, 0), (side * 1.5, BUCKET_HINGE.y, BUCKET_HINGE.z), 0.2, paint, boom)
    rod("CrossTube", (-1.5, 1.4, -0.5), (1.5, 1.4, -0.5), 0.14, paint, boom)

    bucket = link(bpy.data.objects.new("Bucket", None), boom)
    bucket.location = BUCKET_HINGE
    worn = make_paint("BucketSteel", (0.055, 0.05, 0.042), roughness=0.5)
    floor_z = -0.95
    box("BucketBack", (0, 0.0, floor_z + 0.6), (3.6, 0.14, 1.25), worn, bucket)
    placed_box("BucketFloor", (0, 0.7, floor_z + 0.08), (3.6, 1.45, 0.13), worn, bucket, rot_x=math.radians(-4))
    box("BucketTop", (0, 0.12, floor_z + 1.2), (3.7, 0.4, 0.12), worn, bucket)
    for side in (-1, 1):
        extrude_profile(f"BucketSide{side}", [(0.0, floor_z), (1.45, floor_z), (0.35, floor_z + 1.25), (0.0, floor_z + 1.25)],
                        side * 1.8 - 0.07, side * 1.8 + 0.07, worn, bucket, bevel_w=0.02)
        box(f"BucketStripe{side}", (side * 1.88, 0.45, floor_z + 0.55), (0.02, 0.5, 0.7), hazard, bucket, bevel_w=0)
    for k in range(7):
        x = -1.5 + k * 0.5
        placed_box(f"BucketTooth{k}", (x, 1.55, floor_z + 0.07), (0.22, 0.4, 0.12), steel, bucket, rot_x=math.radians(-6))

    # ---- Tipping hopper (parts in hinge space)
    hopper = link(bpy.data.objects.new("Hopper", None), body)
    hopper.location = HINGE
    box("HopperFloor", hp(0, -1.95, 1.87), (3.3, 3.9, 0.45), paint, hopper)
    side_profile = [hp(0, -3.9, 1.65)[1:], hp(0, 0.0, 1.65)[1:], hp(0, 0.5, 3.35)[1:], hp(0, -4.4, 3.35)[1:]]
    for side in (-1, 1):
        x0, x1 = (1.5, 1.65) if side > 0 else (-1.65, -1.5)
        extrude_profile(f"HopperSide{side}", side_profile, x0, x1, paint, hopper, bevel_w=0.03)
        box(f"HopperLip{side}", hp(side * 1.6, -1.95, 3.4), (0.22, 4.9, 0.1), paint, hopper)
        # One long team-colour band along the top of each side, ribs below it
        box(f"HopperTeam{side}", hp(side * 1.665, -1.95, 2.95), (0.03, 4.1, 0.42), team, hopper, bevel_w=0)
        for k, y in enumerate((-3.85, -2.9, -1.95, -1.0, 0.05)):
            box(f"Rib{side}_{k}", hp(side * 1.68, y, 2.2), (0.07, 0.14, 1.05), dark, hopper, bevel_w=0)
    front = [hp(0, 0.0, 1.65)[1:], hp(0, 0.15, 1.65)[1:], hp(0, 0.65, 3.35)[1:], hp(0, 0.5, 3.35)[1:]]
    rear = [hp(0, -3.9, 1.65)[1:], hp(0, -4.05, 1.65)[1:], hp(0, -4.55, 3.35)[1:], hp(0, -4.4, 3.35)[1:]]
    extrude_profile("HopperFront", front, -1.65, 1.65, paint, hopper, bevel_w=0.03)
    extrude_profile("HopperRear", rear, -1.65, 1.65, paint, hopper, bevel_w=0.03)
    box("HopperPivot", hp(0, -4.0, 1.6), (2.6, 0.3, 0.3), dark, hopper)

    ore_pile("OreFull", hopper, ore, 3.25, 0.55, rng)
    ore_pile("OreHalf", hopper, ore, 2.55, 0.15, rng)

    # ---- Hydraulic rams between chassis and hopper front (stretched per frame by the renderer)
    for side in (-1, 1):
        base = link(bpy.data.objects.new(f"RamBase{side}", None), body)
        base.location = (side * 1.0, 0.45, 1.45)
        tip = link(bpy.data.objects.new(f"RamTip{side}", None), hopper)
        tip.location = hp(side * 1.0, -0.2, 2.05)
        ram = cylinder(f"Ram{side}", (0, 0, 0), 0.11, 1.0, brass, body, bevel_w=0, segments=12)
        ram["px_ram"], ram["px_ram_tip"] = base.name, tip.name
        # Lift cylinders from the front frame to the lift arms
        lbase = link(bpy.data.objects.new(f"LiftBase{side}", None), body)
        lbase.location = (side * 0.85, 3.6, 1.0)
        ltip = link(bpy.data.objects.new(f"LiftTip{side}", None), boom)
        ltip.location = (side * 1.3, 1.6, -0.45)
        lift = cylinder(f"LiftRam{side}", (0, 0, 0), 0.13, 1.0, steel, body, bevel_w=0, segments=12)
        lift["px_ram"], lift["px_ram_tip"] = lbase.name, ltip.name

    # ---- Animated debris (hidden unless the renderer shows it)
    spray = link(bpy.data.objects.new("Spray", None), body)
    for i in range(9):
        rock(f"Spray{i}", (0, 0, 0), rng.uniform(0.12, 0.2), ore, spray, rng)
    stream = link(bpy.data.objects.new("Stream", None), body)
    for i in range(14):
        rock(f"Stream{i}", (0, 0, 0), rng.uniform(0.16, 0.26), ore, stream, rng)

    # Centre the truck (bucket teeth to hopper rear) on the actor position so it turns about its middle
    for child in body.children:
        child.location.y -= CENTRE_SHIFT

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print("saved", OUT_BLEND)


if __name__ == "__main__":
    build()
