"""
RedAlert Project X - procedural main battle tank.

Builds a modern MBT from code with PBR materials and saves it to tank.blend.
Hull and turret are separate objects ("Hull", "Turret") so the renderer can
output them as separate OpenRA sequences (body + rotating turret).

Run headless:
  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/units/tank/build_tank.py
"""

import math
import os

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_BLEND = os.path.join(HERE, "tank.blend")

# Paint colour (linear RGB). The team-colour band is kept separate (see make_team_paint).
PAINT = (0.105, 0.115, 0.075)


# --------------------------------------------------------------------------------------------
# Scene helpers
# --------------------------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def link(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent:
        obj.parent = parent
    return obj


def mesh_from_bmesh(name, bm, mat=None, parent=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = link(bpy.data.objects.new(name, me), parent)
    if mat:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return obj


def bevel(obj, width=0.03, segments=2, angle=40):
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = True
    return obj


def extrude_profile(name, profile_yz, x0, x1, mat, parent=None, bevel_w=0.03):
    """Extrude a closed YZ profile along X from x0 to x1."""
    bm = bmesh.new()
    left = [bm.verts.new((x0, y, z)) for y, z in profile_yz]
    right = [bm.verts.new((x1, y, z)) for y, z in profile_yz]
    n = len(profile_yz)
    bm.faces.new(list(reversed(left)))
    bm.faces.new(right)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((left[i], left[j], right[j], right[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = mesh_from_bmesh(name, bm, mat, parent)
    return bevel(obj, bevel_w) if bevel_w else obj


def extrude_polygon(name, poly_xy, z0, z1, mat, parent=None, top_scale=1.0, bevel_w=0.03, offset=(0, 0)):
    """Extrude a closed XY polygon from z0 to z1, optionally shrinking the top (sloped sides)."""
    bm = bmesh.new()
    cx = sum(p[0] for p in poly_xy) / len(poly_xy)
    cy = sum(p[1] for p in poly_xy) / len(poly_xy)
    bot = [bm.verts.new((x + offset[0], y + offset[1], z0)) for x, y in poly_xy]
    top = [bm.verts.new((cx + (x - cx) * top_scale + offset[0], cy + (y - cy) * top_scale + offset[1], z1)) for x, y in poly_xy]
    n = len(poly_xy)
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = mesh_from_bmesh(name, bm, mat, parent)
    return bevel(obj, bevel_w) if bevel_w else obj


def box(name, center, size, mat, parent=None, bevel_w=0.02):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + center[0], v.co.y * size[1] + center[1], v.co.z * size[2] + center[2]))
    obj = mesh_from_bmesh(name, bm, mat, parent)
    return bevel(obj, bevel_w, angle=60) if bevel_w else obj


def cylinder(name, center, radius, depth, mat, parent=None, axis="Z", segments=32, bevel_w=0.01, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=depth)
    obj = mesh_from_bmesh(name, bm, mat, parent, smooth=True)
    if axis == "X":
        obj.rotation_euler = (0, math.radians(90), 0)
    elif axis == "Y":
        obj.rotation_euler = (math.radians(90), 0, 0)
    if rot:
        obj.rotation_euler = rot
    obj.location = center
    if bevel_w:
        bevel(obj, bevel_w, segments=2, angle=50)
    return obj


# --------------------------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------------------------

def node_mat(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, nt, bsdf


def make_paint(name, color, roughness=0.55, wear_color=(0.32, 0.31, 0.29)):
    """Military paint with edge wear (bevel-normal trick), cavity grime (AO) and mottling (noise)."""
    mat, nt, bsdf = node_mat(name)
    N, L = nt.nodes, nt.links

    tex = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 8.0
    L.new(tex.outputs["Object"], noise.inputs["Vector"])

    # Mottled base colour
    mottle = N.new("ShaderNodeMix")
    mottle.data_type = "RGBA"
    mottle.inputs["A"].default_value = (*color, 1)
    mottle.inputs["B"].default_value = (color[0] * 0.7, color[1] * 0.72, color[2] * 0.65, 1)
    ramp = N.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.4
    ramp.inputs["From Max"].default_value = 0.7
    L.new(noise.outputs["Fac"], ramp.inputs["Value"])
    L.new(ramp.outputs["Result"], mottle.inputs["Factor"])

    # Cavity grime from ambient occlusion
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.35
    grime = N.new("ShaderNodeMix")
    grime.data_type = "RGBA"
    L.new(mottle.outputs["Result"], grime.inputs["B"])
    grime.inputs["A"].default_value = (0.02, 0.018, 0.012, 1)
    aoramp = N.new("ShaderNodeMapRange")
    aoramp.inputs["From Min"].default_value = 0.35
    aoramp.inputs["From Max"].default_value = 0.95
    L.new(ao.outputs["AO"], aoramp.inputs["Value"])
    L.new(aoramp.outputs["Result"], grime.inputs["Factor"])

    # Edge wear: compare rounded (bevel) normal with true normal
    bev = N.new("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = 0.04
    geo = N.new("ShaderNodeNewGeometry")
    dot = N.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L.new(bev.outputs["Normal"], dot.inputs[0])
    L.new(geo.outputs["Normal"], dot.inputs[1])
    edge = N.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value = 0.985
    edge.inputs["From Max"].default_value = 0.90
    L.new(dot.outputs["Value"], edge.inputs["Value"])
    edge_noise = N.new("ShaderNodeMath")
    edge_noise.operation = "MULTIPLY"
    L.new(edge.outputs["Result"], edge_noise.inputs[0])
    L.new(noise.outputs["Fac"], edge_noise.inputs[1])
    wear_mask = N.new("ShaderNodeMath")
    wear_mask.operation = "GREATER_THAN"
    wear_mask.inputs[1].default_value = 0.28
    L.new(edge_noise.outputs["Value"], wear_mask.inputs[0])

    wear = N.new("ShaderNodeMix")
    wear.data_type = "RGBA"
    L.new(grime.outputs["Result"], wear.inputs["A"])
    wear.inputs["B"].default_value = (*wear_color, 1)
    L.new(wear_mask.outputs["Value"], wear.inputs["Factor"])
    L.new(wear.outputs["Result"], bsdf.inputs["Base Color"])

    metal = N.new("ShaderNodeMath")
    metal.operation = "MULTIPLY"
    metal.inputs[1].default_value = 0.9
    L.new(wear_mask.outputs["Value"], metal.inputs[0])
    L.new(metal.outputs["Value"], bsdf.inputs["Metallic"])

    rough = N.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = roughness - 0.12
    rough.inputs["To Max"].default_value = roughness + 0.12
    L.new(noise.outputs["Fac"], rough.inputs["Value"])
    L.new(rough.outputs["Result"], bsdf.inputs["Roughness"])

    # Subtle surface breakup in the normals
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    fine = N.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 40.0
    L.new(tex.outputs["Object"], fine.inputs["Vector"])
    L.new(fine.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_simple(name, color, metallic=0.0, roughness=0.6, emission=None):
    mat, nt, bsdf = node_mat(name)
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = 4.0
    return mat


def make_tracks(name):
    """Dark steel track links: a wave texture along the track direction gives the tread pattern."""
    mat, nt, bsdf = node_mat(name)
    N, L = nt.nodes, nt.links
    tex = N.new("ShaderNodeTexCoord")
    wave = N.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 6.0
    wave.wave_profile = "SAW"
    L.new(tex.outputs["Object"], wave.inputs["Vector"])
    col = N.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.inputs["A"].default_value = (0.012, 0.012, 0.012, 1)
    col.inputs["B"].default_value = (0.09, 0.085, 0.08, 1)
    L.new(wave.outputs["Fac"], col.inputs["Factor"])
    L.new(col.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.7
    bsdf.inputs["Roughness"].default_value = 0.65
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    L.new(wave.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# --------------------------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------------------------

def build():
    reset_scene()

    paint = make_paint("Paint", PAINT)
    team = make_simple("TeamColor", (0.8, 0.05, 0.05), roughness=0.45)  # tagged for the team mask pass
    team["px_team"] = True
    tracks = make_tracks("Tracks")
    rubber = make_simple("Rubber", (0.015, 0.015, 0.015), roughness=0.8)
    steel = make_simple("Steel", (0.18, 0.18, 0.19), metallic=1.0, roughness=0.38)
    dark = make_simple("DarkMetal", (0.03, 0.03, 0.032), metallic=0.6, roughness=0.5)
    glass = make_simple("Optics", (0.02, 0.05, 0.06), metallic=0.2, roughness=0.05)
    light = make_simple("Headlight", (0.9, 0.9, 0.8), roughness=0.2, emission=(1.0, 0.9, 0.7))

    hull = bpy.data.objects.new("Hull", None)
    link(hull)

    # ---- Lower hull (between the tracks) and upper hull (full width over the tracks)
    extrude_profile("LowerHull", [(-3.3, 0.42), (3.0, 0.42), (3.45, 0.95), (-3.45, 0.95)], -1.15, 1.15, paint, hull)
    extrude_profile("UpperHull",
                    [(-3.55, 0.95), (3.45, 0.95), (3.65, 1.08), (2.1, 1.48), (-3.45, 1.48), (-3.6, 1.32)],
                    -1.82, 1.82, paint, hull, bevel_w=0.04)

    # ---- Running gear
    for side in (-1, 1):
        x = side * 1.47
        track_prof = []
        for i in range(24):  # stadium shape: two semicircles joined
            a = math.pi / 2 + i / 23 * math.pi
            track_prof.append((-2.95 + 0.47 * math.cos(a), 0.48 + 0.47 * math.sin(a)))
        for i in range(24):
            a = -math.pi / 2 + i / 23 * math.pi
            track_prof.append((3.05 + 0.47 * math.cos(a), 0.48 + 0.47 * math.sin(a)))
        extrude_profile(f"Track{side}", track_prof, x - 0.36, x + 0.36, tracks, hull, bevel_w=0.02)

        for i in range(7):
            y = -2.55 + i * 0.87
            cylinder(f"Wheel{side}_{i}", (x + side * 0.37, y, 0.42), 0.36, 0.06, steel, hull, axis="X")
            cylinder(f"Hub{side}_{i}", (x + side * 0.41, y, 0.42), 0.12, 0.05, dark, hull, axis="X")

        # Armoured side skirts with segment seams
        for i in range(6):
            y0 = -3.0 + i * 1.08
            box(f"Skirt{side}_{i}", (side * 1.86, y0 + 0.52, 0.86), (0.07, 1.04, 0.5), paint, hull, bevel_w=0.015)

        # Mudguard / fender at the front
        box(f"Fender{side}", (side * 1.47, 3.35, 1.0), (0.78, 0.5, 0.05), paint, hull)
        cylinder(f"HeadLight{side}", (side * 1.25, 3.62, 1.13), 0.07, 0.06, light, hull, axis="Y")
        box(f"Hook{side}", (side * 0.7, 3.5, 0.62), (0.12, 0.18, 0.14), dark, hull)

    # ---- Engine deck: grilles, exhausts, storage
    for i in range(9):
        box(f"Grille{i}", (0, -1.75 - i * 0.18, 1.5), (2.2, 0.07, 0.03), dark, hull, bevel_w=0)
    for side in (-1, 1):
        box(f"Exhaust{side}", (side * 1.2, -3.52, 1.2), (0.5, 0.12, 0.18), dark, hull)
        box(f"Box{side}", (side * 1.55, -2.6, 1.6), (0.45, 1.3, 0.25), paint, hull)
    box("DriverHatch", (0.55, 2.35, 1.5), (0.55, 0.45, 0.05), paint, hull)
    for i in range(3):
        box(f"Periscope{i}", (0.35 + i * 0.2, 2.62, 1.52), (0.12, 0.05, 0.06), glass, hull, bevel_w=0)

    # Team-colour stripe across the front of the upper hull
    box("TeamStripe", (0, 2.6, 1.47), (3.4, 0.18, 0.025), team, hull, bevel_w=0)

    # ---- Turret (pivot at its ring centre so the renderer can rotate it)
    turret = bpy.data.objects.new("Turret", None)
    link(turret)
    turret.location = (0, -0.25, 1.48)
    tz0, tz1 = 0.0, 0.8
    shell = [(-0.95, 2.05), (0.95, 2.05), (1.6, 0.85), (1.6, -1.55), (1.2, -2.05), (-1.2, -2.05), (-1.6, -1.55), (-1.6, 0.85)]
    extrude_polygon("TurretShell", shell, tz0, tz1, paint, turret, top_scale=0.9, bevel_w=0.05)
    box("TurretRing", (0, 0, 0.02), (2.4, 2.4, 0.06), dark, turret, bevel_w=0)

    # Bustle rack at the rear
    extrude_polygon("Bustle", [(-1.25, -2.05), (1.25, -2.05), (1.1, -2.7), (-1.1, -2.7)], 0.15, 0.62, paint, turret, bevel_w=0.03)

    # Gun: mantlet, barrel with fume extractor and muzzle
    box("Mantlet", (0, 2.15, 0.42), (0.9, 0.35, 0.55), paint, turret, bevel_w=0.04)
    cylinder("Barrel", (0, 4.4, 0.42), 0.085, 4.4, steel, turret, axis="Y", bevel_w=0)
    cylinder("Sleeve", (0, 3.1, 0.42), 0.13, 1.4, paint, turret, axis="Y")
    cylinder("Fume", (0, 4.7, 0.42), 0.14, 0.55, paint, turret, axis="Y")
    cylinder("Muzzle", (0, 6.55, 0.42), 0.11, 0.25, dark, turret, axis="Y")

    # Commander's cupola, sight, remote weapon station
    cylinder("Cupola", (0.75, -0.6, 0.92), 0.36, 0.25, paint, turret)
    cylinder("CupolaHatch", (0.75, -0.6, 1.06), 0.3, 0.05, paint, turret)
    box("GunnerSight", (-0.8, 1.2, 0.95), (0.42, 0.5, 0.32), paint, turret)
    box("SightGlass", (-0.8, 1.46, 0.98), (0.32, 0.03, 0.18), glass, turret, bevel_w=0)
    box("RWS", (0.75, 0.2, 1.0), (0.32, 0.4, 0.22), dark, turret)
    cylinder("RWSGun", (0.75, 0.75, 1.02), 0.03, 0.8, steel, turret, axis="Y", bevel_w=0)

    # Smoke dischargers (angled tubes), antennas, side stowage
    for side in (-1, 1):
        for i in range(4):
            cylinder(f"Smoke{side}_{i}", (side * (1.2 + i * 0.09), 0.9 - i * 0.12, 0.88), 0.055, 0.28, dark, turret,
                     rot=(math.radians(-55), 0, math.radians(side * 30)), bevel_w=0)
        box(f"Stowage{side}", (side * 1.68, -0.6, 0.38), (0.15, 1.6, 0.45), paint, turret)
        cylinder(f"Antenna{side}", (side * 1.05, -1.85, 1.6), 0.012, 1.8, dark, turret, bevel_w=0, segments=8)

    box("TurretTeamStripe", (0, -1.0, 0.8), (2.6, 0.22, 0.02), team, turret, bevel_w=0)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print("saved", OUT_BLEND)


if __name__ == "__main__":
    build()
