"""
Renders a vehicle from build_vehicles.py into its classic <id>.shp frame layout:

  jeep        0-31 body, 32-63 turret (no ground shadow; drawn over the body)
  apc, arty   0-31 body
  v2rl        0-31 body with rocket, 32-63 empty launcher (empty-idle, while reloading)

  Blender -b artsrc/units/vehicles/<id>.blend -P artsrc/units/vehicles/render_vehicle.py -- <id> <out dir> [frame px] [samples] [zoom]

Writes <out dir>/frame-NN.png. zoom > 1 renders a few key frames at higher resolution for checking.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import render_sprites  # noqa: E402

# Must match build_tanks.UNIT_PX (muzzle offsets); PX_UNIT_PX renders the same framing at more pixels
UNIT_PX = float(os.environ.get("PX_UNIT_PX", "3.5"))

argv = sys.argv[sys.argv.index("--") + 1:]
VID, OUT = argv[0], argv[1]
FRAME = int(argv[2]) if len(argv) > 2 else 160
SAMPLES = int(argv[3]) if len(argv) > 3 else 48
ZOOM = int(argv[4]) if len(argv) > 4 else 1
PREVIEW_FRAMES = {4, 12, 20, 28, 36, 44}

render_sprites.setup(frame=FRAME, samples=SAMPLES, zoom=ZOOM, unit_px=UNIT_PX)
objs = bpy.data.objects
body = objs["Body"]
ground = next(o for o in objs if o.is_shadow_catcher)


def tree(root):
    return [root, *root.children_recursive]


def render(index):
    if ZOOM > 1 and index not in PREVIEW_FRAMES:
        return
    render_sprites.render_to(os.path.join(OUT, f"frame-{index:02d}.png"))


def body_pass(start):
    for f in range(32):
        render_sprites.face(body, f, 32)
        render(start + f)


if VID == "jeep":
    turret = objs["Turret"]
    for o in tree(turret):
        o.hide_render = True
    body_pass(0)
    for o in tree(turret):
        o.hide_render = False
    for o in tree(body):
        o.visible_camera = False
        o.visible_shadow = False
    ground.hide_render = True
    for f in range(32):
        render_sprites.face(turret, f, 32)
        render(32 + f)
elif VID == "v2rl":
    body_pass(0)
    for o in tree(objs["Rocket"]):
        o.hide_render = True
    body_pass(32)
else:
    body_pass(0)
print("rendered", OUT)
