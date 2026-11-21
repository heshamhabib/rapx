"""
Landmark flag (captured landmarks of the painted maps): a steel flagpole with a waving national flag, a player-colour
pennant at the top and a player-colour band round the plinth.

  python3 artsrc/landmark-flag/make_cloths.py                        # nation flag images (from artsrc/px-flags/svg)
  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/landmark-flag/render_flag.py
  python3 artsrc/landmark-flag/pack.py                               # -> mods/rapx/bits/hd/landmark-flag/*.png + sequences

The cloth is the draped "Mexican Flag" model (SusiePhilpott, CC-BY-4.0, assets/inbox/flag/mexican_flag.zip) with its
texture replaced by each nation's flag and a travelling wave added (FRAMES frames, one loop). Rendered with the game's
oblique projection (height leans up the picture, y += z * cot 50deg), sun from the north-west, at 8x the game's pixel
density (192 px per cell) and drawn at Scale 0.25: a monumental flag twice real size (16 m cloth, 28 m pole), still sharp at 2x zoom. The pole's foot is at the
exact centre of every frame.

Two passes per frame: the full picture, and a mask of the player-colour parts (pure green; PlayerColorShift recolours
them in game). pack.py splits them so the national colours are never recoloured (many flags contain green).
"""
import glob
import math
import os
import zipfile

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
BUILD = os.path.join(HERE, "build")
CLOTHS = os.path.join(BUILD, "cloths")
FRAMES_DIR = os.path.join(BUILD, "frames")
MODEL = os.path.join(ROOT, "assets", "inbox", "flag", "mexican_flag.zip")

FRAMES = int(os.environ.get("FLAG_FRAMES", 12))
PPM = 192 / 7.0                      # pixels per metre (192 px per 7 m cell)
W, H = 512, 704                      # canvas; the pole's foot is at its centre
SHEAR = 1 / math.tan(math.radians(50))
OBLIQUE = Matrix(((1, 0, 0, 0), (0, 1, SHEAR, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
POLE_H = 14.0
CLOTH_W = 8.0
CLOTH_TOP = 12.6
GREEN = (0.0, 1.0, 0.0)


def mat(name, rgb, rough=0.5, metal=0.0, image=None):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if image:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = image
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    m.use_backface_culling = False
    return m


def mask_mat(name, white):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1, 1, 1, 1) if white else (0, 0, 0, 1)
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def obj_from_bm(name, bm, material):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def cylinder(r0, r1, z0, z1, seg=16, x=0.0, y=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r0, radius2=r1, depth=z1 - z0,
                          matrix=Matrix.Translation((x, y, (z0 + z1) / 2)))
    return bm


def load_cloth():
    """The draped cloth: hoist (pole side) at x = 0, flying towards +x, top edge at CLOTH_TOP, facing the camera (-y).
    Returns the object and the rest positions of its vertices."""
    out = os.path.join(BUILD, "model")
    if not os.path.isdir(out):
        with zipfile.ZipFile(MODEL) as z:
            z.extractall(out)
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=glob.glob(os.path.join(out, "**", "*.gltf"), recursive=True)[0])
    new = [o for o in bpy.context.scene.objects if o not in before]
    obs = [o for o in new if o.type == "MESH"]
    bpy.context.view_layer.update()
    me = obs[0].data.copy()
    me.transform(obs[0].matrix_world)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    # After import (glTF is y-up -> Blender z-up) the cloth spans x (width) and z (height), thin in y
    w = max(xs) - min(xs)
    s = CLOTH_W / w
    me.transform(Matrix.Translation((0, 0, CLOTH_TOP)) @ Matrix.Scale(s, 4)
                 @ Matrix.Translation((-min(xs), -(max(ys) + min(ys)) / 2, -max(zs))))
    ob = bpy.data.objects.new("Cloth", me)
    bpy.context.collection.objects.link(ob)
    rest = [v.co.copy() for v in me.vertices]
    return ob, rest


def cloth_texture(me, flag_path):
    """A texture for the cloth's UV layout with the nation's flag in both UV islands (front and back), each oriented
    so the hoist side of the flag is at the pole."""
    from array import array
    img = bpy.data.images.load(flag_path, check_existing=True)
    fw, fh = img.size
    fpx = list(img.pixels)
    size = 1024
    out = [0.0] * (size * size * 4)
    uv = me.uv_layers.active.data
    islands = {0: [], 1: []}
    for poly in me.polygons:
        for li in poly.loop_indices:
            u, v = uv[li].uv
            x = me.vertices[me.loops[li].vertex_index].co.x
            islands[0 if v >= 0.5 else 1].append((u, v, x))
    for pts in islands.values():
        if not pts:
            continue
        u0, u1 = min(p[0] for p in pts), max(p[0] for p in pts)
        v0, v1 = min(p[1] for p in pts), max(p[1] for p in pts)
        mu = sum(p[0] for p in pts) / len(pts)
        mx = sum(p[2] for p in pts) / len(pts)
        cov = sum((p[0] - mu) * (p[2] - mx) for p in pts)
        flip = cov < 0                                   # u decreases away from the pole
        x0, x1 = int(u0 * size), int(math.ceil(u1 * size))
        y0, y1 = int(v0 * size), int(math.ceil(v1 * size))
        for y in range(max(0, y0 - 2), min(size, y1 + 2)):
            ty = min(fh - 1, max(0, int((y - y0) / max(1, y1 - y0) * fh)))
            for x in range(max(0, x0 - 2), min(size, x1 + 2)):
                tx = (x - x0) / max(1, x1 - x0)
                if flip:
                    tx = 1 - tx
                tx = min(fw - 1, max(0, int(tx * fw)))
                i = (y * size + x) * 4
                j = (ty * fw + tx) * 4
                out[i:i + 4] = fpx[j:j + 3] + [1.0]
    tex = bpy.data.images.new("ClothTex", size, size)
    tex.pixels[:] = out
    return tex


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 24
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"

    world = bpy.data.worlds.new("w")
    sc.world = world
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.62, 0.72, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.0
    travel = Vector((0.7, -0.62, -math.tan(math.radians(42)))).normalized()
    sun.rotation_euler = (-travel).to_track_quat("Z", "Y").to_euler()
    sc.collection.objects.link(sun)

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = H / PPM
    cam.location = (0, 0, 300)
    cam.data.clip_end = 1000
    sc.collection.objects.link(cam)
    sc.camera = cam

    steel = mat("Steel", (0.62, 0.63, 0.66), 0.3, 1.0)
    gold = mat("Gold", (0.95, 0.72, 0.3), 0.25, 1.0)
    stone = mat("Stone", (0.78, 0.76, 0.72), 0.85)
    team = mat("Team", GREEN, 0.5)
    parts = []
    for bm, m in ((cylinder(0.11, 0.08, 0, POLE_H), steel), (cylinder(0.25, 0.25, POLE_H, POLE_H + 0.5), gold),
                  (cylinder(0.9, 0.9, 0, 0.6, seg=8), stone), (cylinder(0.92, 0.92, 0.6, 0.95, seg=8), team),
                  (cylinder(0.7, 0.7, 0.95, 1.3, seg=8), stone)):
        parts.append(obj_from_bm("part", bm, m))
    # Player-colour pennant: a long triangle above the flag, between the cloth and the finial
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((0, 0, CLOTH_TOP + 0.25), (0, 0, CLOTH_TOP + 1.2), (3.2, 0, CLOTH_TOP + 0.7))]
    bm.faces.new(vs)
    pennant = obj_from_bm("Pennant", bm, team)
    parts.append(pennant)
    cloth, rest = load_cloth()
    for ob in parts:
        ob.data.transform(OBLIQUE)
    cloth_mesh = cloth.data

    mask_on, mask_off = mask_mat("MaskOn", True), mask_mat("MaskOff", False)
    nations = sorted(os.path.splitext(f)[0] for f in os.listdir(CLOTHS) if f.endswith(".png"))
    for fi in range(FRAMES):
        # Travelling wave, zero at the pole: bends the cloth towards and away from the camera, a little up and down
        ph = 2 * math.pi * fi / FRAMES
        for v, p in zip(cloth_mesh.vertices, rest):
            d = max(0.0, p.x) / CLOTH_W
            wave = math.sin(2 * math.pi * d * 1.2 - ph)
            co = Vector((p.x - 0.25 * d * d, p.y + 0.55 * d * wave, p.z + 0.12 * d * math.sin(2 * math.pi * d * 1.2 - ph + 1.3)))
            v.co = OBLIQUE @ co
        cloth_mesh.update()
        # Team-colour mask: emission white on team parts, black (still occluding) on the rest
        saved = {ob.name: list(ob.data.materials) for ob in parts + [cloth]}
        for ob in parts + [cloth]:
            for i, m in enumerate(ob.data.materials):
                ob.data.materials[i] = mask_on if m == team else mask_off
        sc.render.filepath = os.path.join(FRAMES_DIR, f"mask-{fi:02d}.png")
        bpy.ops.render.render(write_still=True)
        for ob in parts + [cloth]:
            for i, m in enumerate(saved[ob.name]):
                ob.data.materials[i] = m
        for n in nations:
            if fi == 0 or not cloth_mesh.materials:
                pass
            key = f"Cloth-{n}"
            m = bpy.data.materials.get(key)
            if not m:
                m = mat(key, (1, 1, 1), 0.8, image=cloth_texture(cloth_mesh, os.path.join(CLOTHS, n + ".png")))
            if cloth_mesh.materials:
                cloth_mesh.materials[0] = m
            else:
                cloth_mesh.materials.append(m)
            sc.render.filepath = os.path.join(FRAMES_DIR, f"{n}-{fi:02d}.png")
            bpy.ops.render.render(write_still=True)
        print(f"frame {fi + 1}/{FRAMES}")


main()
