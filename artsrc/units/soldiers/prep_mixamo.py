"""
Turns a raw Hunyuan3D soldier shape (artsrc/units/meshes/shape/<id>.glb) into a Mixamo upload:
upright, facing -Y (Mixamo's front), feet on the ground, 1.8 m tall, decimated, coloured from the concept views,
exported as artsrc/units/soldiers/upload/<id>.fbx. Also renders preview/<id>.png (front, side, back).

  blender -b -P artsrc/units/soldiers/prep_mixamo.py -- <id> [yaw_deg]
"""

import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import soldier_paint  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
argv = sys.argv[sys.argv.index("--") + 1:]
UID = argv[0]
if os.path.exists(os.path.join(HERE, "upload", f"{UID}.keep")):
    print("prepared", UID, "kept (hand-picked body, upload/%s.keep)" % UID)
    sys.exit(0)
YAW = float(argv[1]) if len(argv) > 1 else 0.0
HEIGHT = 1.8
FACES = 40000

bpy.ops.wm.read_factory_settings(use_empty=True)
# The body shape: shape/<id>.glb, or the empty-handed one (shape/<id>-unarmed-front.glb) when it exists
SHAPE = os.path.join(ROOT, "artsrc", "units", "meshes", "shape", f"{UID}-unarmed-front.glb")
if not os.path.exists(SHAPE):
    SHAPE = os.path.join(ROOT, "artsrc", "units", "meshes", "shape", f"{UID}.glb")
bpy.ops.import_scene.gltf(filepath=SHAPE)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for o in meshes:
    o.data.transform(o.matrix_world)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
for o in list(bpy.context.scene.objects):
    if o.type != "MESH":
        bpy.data.objects.remove(o)

# One object
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
body = bpy.context.view_layer.objects.active
body.name = UID
body.data.transform(Matrix.Rotation(math.radians(YAW), 4, "Z"))

# Feet on the ground, centred, 1.8 m tall
pts = [v.co for v in body.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
scale = HEIGHT / (hi.z - lo.z)
body.data.transform(Matrix.Scale(scale, 4) @ Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))))

# Weapons fused to the body are cut away (the game carries a separate weapon prop in the hand, so it moves
# with the hands). Per soldier: boxes (xmin, xmax, zmin, zmax) and the depth in front of which geometry goes.
CUTS = {
    "e1": [((-0.30, 0.30, 0.72, 1.36), -0.155)],
}
if UID in CUTS:
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(body.data)
    doomed = [v for v in bm.verts for (x0, x1, z0, z1), ymax in CUTS[UID]
              if x0 <= v.co.x <= x1 and z0 <= v.co.z <= z1 and v.co.y < ymax]
    bmesh.ops.delete(bm, geom=list(set(doomed)), context="VERTS")
    # Drop loose leftovers of the weapon (any island much smaller than the body)
    bm.verts.ensure_lookup_table()
    seen, islands = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        stack, isl = [v], []
        seen.add(v)
        while stack:
            u = stack.pop()
            isl.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        islands.append(isl)
    biggest = max(len(i) for i in islands)
    bmesh.ops.delete(bm, geom=[v for i in islands if len(i) < biggest * 0.02 for v in i], context="VERTS")
    # Close the hole the weapon leaves in the chest
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(body.data)
    bm.free()
    print("cut weapon:", len(set(doomed)), "verts")

# Lighter mesh for Mixamo's rigger
dec = body.modifiers.new("dec", "DECIMATE")
dec.ratio = min(1.0, FACES / max(1, len(body.data.polygons)))
bpy.ops.object.modifier_apply(modifier="dec")
for p in body.data.polygons:
    p.use_smooth = True

soldier_paint.paint(body, UID)
body.data.materials.clear()
body.data.materials.append(soldier_paint.vertex_color_material())

os.makedirs(os.path.join(HERE, "upload"), exist_ok=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(HERE, "upload", f"{UID}.fbx"), use_selection=False,
                         apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", colors_type="SRGB")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "upload", f"{UID}.blend"))

# Preview: front, left side, back
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys() else "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 1200, 700
scene.render.film_transparent = False
world = bpy.data.worlds.new("w")
world.color = (0.8, 0.8, 0.8)
scene.world = world
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3
sun.rotation_euler = (math.radians(45), 0, math.radians(-30))
scene.collection.objects.link(sun)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = 6.4
scene.collection.objects.link(cam)
scene.camera = cam
copies = []
for i, yaw in enumerate([0, 90, 180]):
    c = body.copy()
    c.data = body.data
    c.matrix_world = Matrix.Translation((-2.1 + i * 2.1, 0, 0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    scene.collection.objects.link(c)
    copies.append(c)
body.hide_render = True
cam.location = (0, -10, 0.9)
cam.rotation_euler = (math.radians(90), 0, 0)
scene.render.filepath = os.path.join(HERE, "upload", f"{UID}-preview.png")
bpy.ops.render.render(write_still=True)
print("prepared", UID, len(body.data.polygons), "faces")
