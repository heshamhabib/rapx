"""
Quality preview of tank.blend on a grass ground plane, from the RTS camera angle.
  Blender -b artsrc/units/tank/tank.blend -P artsrc/units/tank/preview.py -- out.png [facing_deg] [elevation_deg]
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.normpath(os.path.join(HERE, "..", ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(HERE, "preview.png")
FACING = float(argv[1]) if len(argv) > 1 else 35.0
ELEV = float(argv[2]) if len(argv) > 2 else 50.0

scene = bpy.context.scene

# --- Cycles on the Apple GPU
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.device = "GPU"
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.resolution_x = scene.render.resolution_y = 1024
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"

# --- Sky + sun
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
env = wn.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(os.path.join(ART, "hdri", "sky_2k.hdr"))
world.node_tree.links.new(env.outputs["Color"], wn["Background"].inputs["Color"])
wn["Background"].inputs["Strength"].default_value = 0.7

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 4.5
sun.data.angle = math.radians(1.5)
sun.rotation_euler = (math.radians(40), 0, math.radians(-35))  # light from upper-left, shadows fall down-right
scene.collection.objects.link(sun)

# --- Ground plane with grass
bpy.ops.mesh.primitive_plane_add(size=40)
ground = bpy.context.object
gm = bpy.data.materials.new("Ground")
gm.use_nodes = True
gnt = gm.node_tree
bsdf = gnt.nodes["Principled BSDF"]
import glob
tex_dir = os.path.join(ART, "textures", "Grass004")
img = gnt.nodes.new("ShaderNodeTexImage")
img.image = bpy.data.images.load(glob.glob(os.path.join(tex_dir, "*_Color.jpg"))[0])
mapping = gnt.nodes.new("ShaderNodeMapping")
mapping.inputs["Scale"].default_value = (6, 6, 6)
tc = gnt.nodes.new("ShaderNodeTexCoord")
gnt.links.new(tc.outputs["UV"], mapping.inputs["Vector"])
gnt.links.new(mapping.outputs["Vector"], img.inputs["Vector"])
gnt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.9
ground.data.materials.append(gm)

# --- Face the tank and turret
hull = bpy.data.objects["Hull"]
turret = bpy.data.objects["Turret"]
hull.rotation_euler = (0, 0, math.radians(FACING))
turret.parent = hull
turret.location = (0, -0.25, 1.48)
turret.rotation_euler = (0, 0, math.radians(-20))

# --- Orthographic RTS camera
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = 11
e = math.radians(ELEV)
dist = 40
cam.location = Vector((0, -dist * math.cos(e), dist * math.sin(e) + 0.8))
cam.rotation_euler = (math.radians(90) - e, 0, 0)
scene.collection.objects.link(cam)
scene.camera = cam

scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("wrote", OUT)
