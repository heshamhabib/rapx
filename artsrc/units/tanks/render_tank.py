"""
Renders a tank from build_tanks.py into the classic <id>.shp frame layout:
  0-31   hull, 32 facings (turret left out entirely: hidden but solid it would black out the hull under it)
  32-63  turret, 32 facings (no ground shadow; the engine draws it over the hull)

  Blender -b artsrc/units/tanks/<id>.blend -P artsrc/units/tanks/render_tank.py -- <out dir> [frame px] [samples] [zoom]

Writes <out dir>/frame-NN.png. zoom > 1 renders a few key frames at higher resolution for checking.
Spinning overlays (radar dishes, coils) use the same layout: set PX_SPIN_FRAMES for a loop shorter
than 32 frames (the part then turns a full circle in that many frames).
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import render_sprites  # noqa: E402

# Must match build_tanks.UNIT_PX (muzzle offsets); PX_UNIT_PX renders the same framing at more pixels
# (meshes/make.sh: 2x sheets drawn at half the sequence Scale)
UNIT_PX = float(os.environ.get("PX_UNIT_PX", "3.5"))

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
FRAME = int(argv[1]) if len(argv) > 1 else 160
SAMPLES = int(argv[2]) if len(argv) > 2 else 48
ZOOM = int(argv[3]) if len(argv) > 3 else 1
PREVIEW_FRAMES = {4, 12, 20, 28, 36, 44}

render_sprites.setup(frame=FRAME, samples=SAMPLES, zoom=ZOOM, unit_px=UNIT_PX)
hull, turret = bpy.data.objects["Hull"], bpy.data.objects["Turret"]
ground = next(o for o in bpy.data.objects if o.is_shadow_catcher)


def camera_visible(root, visible):
    for o in [root, *root.children_recursive]:
        o.visible_camera = visible


def render(index):
    if ZOOM > 1 and index not in PREVIEW_FRAMES:
        return
    render_sprites.render_to(os.path.join(OUT, f"frame-{index:02d}.png"))


# Hull pass: no turret at all
for o in [turret, *turret.children_recursive]:
    o.hide_render = True
for f in range(32):
    render_sprites.face(hull, f, 32)
    render_sprites.face(turret, f, 32)
    render(f)

# Turret pass: only the turret, no ground shadow
for o in [turret, *turret.children_recursive]:
    o.hide_render = False
camera_visible(hull, False)
for o in [hull, *hull.children_recursive]:
    o.visible_shadow = False
ground.hide_render = True
spin = int(os.environ.get("PX_SPIN_FRAMES", "32"))
for f in range(spin):
    render_sprites.face(turret, f, spin)
    render(32 + f)
print("rendered", OUT)
