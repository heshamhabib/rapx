"""
Renders a jet with weapon stations (IDEA-34, artsrc/jets/loadout_table.py) from import_sketchfab.py:

  <out dir>/frame-NN.png             0-31 the jet without its weapons (32 facings)
  <out dir>/store-<tag>/frame-NN.png each weapon alone, 32 facings, same framing; the airframe is a holdout (an
                                     invisible mask), so a missile under a wing is cut where the wing covers it

  Blender -b <unit>.blend -P artsrc/units/meshes/render_loadout.py -- <out dir> <frame px> <samples>
"""

import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import render_sprites  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, FRAME, SAMPLES = argv[0], int(argv[1]), int(argv[2])
render_sprites.setup(frame=FRAME, samples=SAMPLES)
body = bpy.data.objects["Body"]
stores = sorted((o for o in body.children_recursive if "px_store" in o), key=lambda o: o.name)
airframe = [o for o in body.children_recursive if o.type == "MESH" and o not in stores]


def turn_all(prefix):
    for f in range(32):
        render_sprites.face(body, f, 32)
        render_sprites.render_to(os.path.join(OUT, prefix, f"frame-{f:02d}.png"))


for s in stores:
    s.hide_render = True
turn_all("")
for o in airframe:
    o.is_holdout = True
for s in stores:
    for t in stores:
        t.hide_render = t is not s
    turn_all(f"store-{s['px_store']}")
print("rendered", OUT, "stores:", " ".join(s["px_store"] for s in stores))
