"""
Renders one assembled view of a unit .blend (turret on its ring, rotors on their hubs) for checking a model
before the full sprite render, with the lighting of PX_LIGHT (default hd).

  Blender -b <unit>.blend -P artsrc/units/meshes/preview_unit.py -- <out.png> [facing 0-31] [turret facing] [zoom] [air]

air = 1 renders like the aircraft (no ground shadow, the jets' unit size).
"""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("PX_LIGHT", "hd")
import render_sprites  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
FACING = int(argv[1]) if len(argv) > 1 else 4
TURRET = int(argv[2]) if len(argv) > 2 else FACING
ZOOM = int(argv[3]) if len(argv) > 3 else 3
AIR = len(argv) > 4 and argv[4] == "1"
if AIR:
    os.environ["PX_NO_GROUND"] = "1"

render_sprites.setup(frame=224 if AIR else 192, samples=96, zoom=ZOOM, unit_px=9.1 / 2 if AIR else 3.5)
angle = math.radians(FACING * 360 / 32)
main = next(o for o in bpy.data.objects if o.name in ("Hull", "Body"))
render_sprites.face(main, FACING, 32)
for o in bpy.data.objects:
    pivot = o.get("px_pivot") or o.get("px_hub")
    if pivot is None or o.parent:
        continue
    x, y, z = pivot
    o.location = (x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle), z)
    o.rotation_euler = (0, 0, math.radians((TURRET if o.name == "Turret" else FACING) * 360 / 32))
render_sprites.render_to(OUT)
