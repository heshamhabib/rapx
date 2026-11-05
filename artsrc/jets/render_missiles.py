"""
Fired weapons as HD sprites (IDEA-34): every procedural weapon kind (ordnance.py) rendered alone from 32 directions with
the HD light, at the jets' scale, for the PxRocket projectile (weapons/jet-ordnance.yaml Image: pxmissile).

  Blender -b -P artsrc/jets/render_missiles.py -- <kind> <out dir> [size multiplier]
then python3 artsrc/units/pack_sprites.py <out dir> mods/rapx/bits/hd/fx/missile-<kind>.png
(make_missiles.sh does all kinds).
"""

import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "units"))
os.environ["PX_LIGHT"] = "hd"
os.environ["PX_NO_GROUND"] = "1"

argv = sys.argv[sys.argv.index("--") + 1:]
KIND, OUT = argv[0], argv[1]
# Optional size multiplier (default 1 = the jets' scale)
SIZE = float(argv[2]) if len(argv) > 2 else 1.0
bpy.ops.wm.read_factory_settings(use_empty=True)
import ordnance  # noqa: E402
import render_sprites  # noqa: E402

# Jets: ~0.46 Blender units per metre at their in-game size (F-16: 15 m = 7 units)
obj = ordnance.build(KIND, 7.0 / 15.06 * SIZE)
root = bpy.data.objects.new("Root", None)
bpy.context.scene.collection.objects.link(root)
obj.parent = root
# centred: the projectile places it in flight
# The frame grows for long rockets (rendered length ~ 3.15 px per unit_px per Blender unit, measured on aim9)
frame = max(96, 16 * math.ceil(obj["px_length"] * 9.1 * 3.15 * 1.15 / 16))
render_sprites.setup(frame=frame, samples=64, unit_px=9.1)
for f in range(32):
    render_sprites.face(root, f, 32)
    render_sprites.render_to(os.path.join(OUT, f"frame-{f:02d}.png"))
print("rendered", KIND)
