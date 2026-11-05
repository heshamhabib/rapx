"""
Ordnance survey for IDEA-34 (real jet loadouts): pictures of the weapons hanging on a jet's model (found from shape by
storefind.py), each store tinted and listed, for writing the loadout table (loadout_table.py).

  Blender -b artsrc/units/meshes/<sprite>.blend -P artsrc/jets/loadouts.py -- <unit id> <out dir>

Writes <out dir>/<unit>.json (stores: centre, size, guessed family) and <out dir>/<unit>.png (top view).
"""

import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storefind  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
UNIT, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)

for o in bpy.data.objects:  # turrets / rotors back on their hubs
    p = o.get("px_pivot") or o.get("px_hub")
    if p is not None and not o.parent:
        o.location = p
bpy.context.view_layer.update()
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
stores, size = storefind.find(meshes)
stores.sort(key=lambda s: (-abs(s["centre"][0]), s["centre"][1]))

colours = [(1, 0.15, 0.1), (0.1, 0.5, 1), (1, 0.85, 0.1), (0.2, 0.9, 0.3), (0.9, 0.3, 0.9), (0.1, 0.9, 0.9),
           (1, 0.55, 0.1), (0.6, 0.4, 1), (1, 1, 1), (0.5, 1, 0.6)]
for k, st in enumerate(stores):
    mat = bpy.data.materials.new(f"store{k}")
    mat.use_nodes = True
    em = mat.node_tree.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*colours[k % len(colours)], 1)
    em.inputs["Strength"].default_value = 2.0
    mat.node_tree.links.new(em.outputs[0], mat.node_tree.nodes["Material Output"].inputs["Surface"])
    for name, faces in st["faces"]:
        o = bpy.data.objects[name]
        o.data.materials.append(mat)
        slot = len(o.data.materials) - 1
        for fi in faces:
            o.data.polygons[fi].material_index = slot
    st["colour"] = colours[k % len(colours)]

lo, hi = size["lo"], size["hi"]
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
    e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = True
for o in list(bpy.data.objects):
    if o.type in ("CAMERA", "LIGHT") or getattr(o, "is_shadow_catcher", False):
        bpy.data.objects.remove(o)
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[1].default_value = 1.2
sun = bpy.data.objects.new("s", bpy.data.lights.new("s", "SUN"))
sun.data.energy = 3
scene.collection.objects.link(sun)
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = max(size["length"], size["span"]) * 1.1
cam.location = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2] + 20)
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.filepath = os.path.join(OUT, f"{UNIT}.png")
bpy.ops.render.render(write_still=True)

json.dump({"unit": UNIT, **size, "stores": [{k: v for k, v in s.items() if k != "faces"} for s in stores]},
          open(os.path.join(OUT, f"{UNIT}.json"), "w"), indent=1)
print(f"{UNIT}: {len(stores)} stores ->", ", ".join(s["family"] for s in stores))
