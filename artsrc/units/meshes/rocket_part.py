"""
After split_turret.py has cut the V2 rocket out (cx = cy = 0, so it stays in place), turns the
result into the layout render_vehicle.py expects for v2rl: a "Body" root with a "Rocket" child.

  Blender -b v2rl.blend -P artsrc/units/meshes/rocket_part.py
"""

import bpy

hull, rocket = bpy.data.objects["Hull"], bpy.data.objects["Turret"]
hull.name, rocket.name = "Body", "Rocket"
rocket.parent = hull
bpy.ops.wm.save_mainfile()
print("rocket part ready")
