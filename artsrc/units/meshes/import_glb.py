"""
Imports an image-to-3D model (.glb) as a unit "Body" ready for render_sprites.py:
ground at z=0, centred on the origin, front along +Y, scaled to a given length in Blender units.

  Blender -b -P artsrc/units/meshes/import_glb.py -- <in.glb> <out.blend> <length> [yaw_deg] [saturation] [value]

yaw_deg turns the model about the vertical axis after import so its front points along +Y.
saturation (default 1.3) warms the AI texture back towards the concept art; it is applied with a
Hue/Saturation node after each base-colour texture, so team-colour green stays green.
"""

import math
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT, LENGTH = argv[0], argv[1], float(argv[2])
YAW = float(argv[3]) if len(argv) > 3 else 0.0
SATURATION = float(argv[4]) if len(argv) > 4 else 1.3
VALUE = float(argv[5]) if len(argv) > 5 else 1.08

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

# Bake every transform into the meshes, then apply the yaw
for o in meshes:
    o.data.transform(o.matrix_world)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
    o.data.transform(Matrix.Rotation(math.radians(YAW), 4, "Z"))
for o in list(bpy.context.scene.objects):
    if o.type != "MESH":
        bpy.data.objects.remove(o)

pts = [v.co for o in meshes for v in o.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
size = hi - lo
scale = LENGTH / size.y
centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
for o in meshes:
    o.data.transform(Matrix.Scale(scale, 4) @ Matrix.Translation(-centre))
    for p in o.data.polygons:
        p.use_smooth = True

# Colour pass on the AI texture
for mat in {s.material for o in meshes for s in o.material_slots if s.material}:
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf or not bsdf.inputs["Base Color"].links:
        continue
    link = bsdf.inputs["Base Color"].links[0]
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = SATURATION
    hsv.inputs["Value"].default_value = VALUE
    nt.links.new(link.from_socket, hsv.inputs["Color"])
    nt.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])

body = bpy.data.objects.new("Body", None)
bpy.context.scene.collection.objects.link(body)
for o in meshes:
    o.parent = body
print("size (x, y, z) after scaling:", tuple(round(c * scale, 2) for c in size))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
