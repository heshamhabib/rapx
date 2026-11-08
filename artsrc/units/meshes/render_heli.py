"""
Renders a helicopter from import_sketchfab.py (kind heli): "Body" + "Rotor<N>" roots, each rotor with its
hub on the origin.

  <out dir>/body/frame-NN.png   0-31 body without rotor blades, 32 facings (no ground shadow, like the jets)
  <out dir>/rotor/frame-NN.png  0-31 the blades over one blade period (each smeared over three positions);
                                no facings, the engine places it on the hub with WithIdleOverlay Offset.
                                Flying and landed rotors play the same frames at different Ticks
                                (sequences/hd-units.yaml: about one turn per 4 s flying, half that landed)

  Blender -b <unit>.blend -P artsrc/units/meshes/render_heli.py -- <out dir> <frame px> <samples> <blades> [rotor-only]

rotor-only skips the body (helicopters with weapon stations get it, and the weapon overlays, from render_loadout.py).
"""

import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import render_sprites  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, FRAME, SAMPLES, BLADES = argv[0], int(argv[1]), int(argv[2]), int(argv[3])
ROTOR_ONLY = len(argv) > 4 and argv[4] == "rotor-only"
os.environ["PX_NO_GROUND"] = "1"
render_sprites.setup(frame=FRAME, samples=SAMPLES)
body = bpy.data.objects["Body"]
rotors = [o for o in bpy.data.objects if o.name.startswith("Rotor") and not o.parent]


def show(root, visible):
    for o in [root, *root.children_recursive]:
        o.hide_render = not visible


for r in rotors:
    show(r, False)
for f in range(0 if ROTOR_ONLY else 32):
    render_sprites.face(body, f, 32)
    render_sprites.render_to(os.path.join(OUT, "body", f"frame-{f:02d}.png"))

# Rotor sheet from the first rotor (the Chinook's two rotors are the same)
show(body, False)
rotor = rotors[0]
show(rotor, True)
period = 2 * math.pi / BLADES
tmp = os.path.join(OUT, "rotor-steps")
steps = []
for i in range(32):
    rotor.rotation_euler = (0, 0, -period * i / 32)  # rotors turn clockwise seen from above
    path = os.path.join(tmp, f"step-{i:02d}.png")
    render_sprites.render_to(path)
    steps.append(path)


def load(path):
    img = bpy.data.images.load(path)
    px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    size = tuple(img.size)
    bpy.data.images.remove(img)
    return px, size


def save(px, size, path):
    img = bpy.data.images.new("out", size[0], size[1], alpha=True)
    img.pixels.foreach_set(px)
    img.filepath_raw = path
    img.file_format = "PNG"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save()
    bpy.data.images.remove(img)


frames = [load(p) for p in steps]
size = frames[0][1]
stack = np.stack([f[0].reshape(-1, 4) for f in frames])
# Visible blades turning (a blur disc reads as a dark circle once the engine draws the aircraft shadow):
# each frame smears three neighbouring blade positions for a little motion, premultiplied so edges stay clean
for i in range(32):
    near = stack[[(i - 1) % 32, i, (i + 1) % 32]]
    alpha = near[..., 3:4]
    colour = (near[..., :3] * alpha).sum(0) / np.maximum(alpha.sum(0), 1e-6)
    out = np.concatenate([colour, alpha.mean(0)], axis=1).ravel()
    save(out, size, os.path.join(OUT, "rotor", f"frame-{i:02d}.png"))
print("rendered", OUT)
