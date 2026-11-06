"""
HD parachutes (RedAlert Project X, IDEA-30 phase 2): the paradrop canopy and the parabomb, rendered from the Sketchfab
model "Army Parachute" by amaraklov (CC-BY-4.0, credited in mods/rapx/CREDITS).

  blender -b -P artsrc/units/parachute/render_parachute.py -- <out dir> [samples]

Writes <out dir>/parach-open-N.png (5: the canopy deploys from a streamer), parach-idle-N.png (11: it sways and
breathes on the way down), parabomb-open-N.png (8) and parabomb-idle-N.png (5: a small canopy carrying a Mk 82).
Same camera and light as the HD units. make_parachute.py packs them.

Paratroopers: the frame centre is where WithParachute draws the canopy (Offset 0,0,384 above the soldier), and the
suspension lines meet just above it, at the soldier's shoulders. Parabomb: the frame centre is the bomb.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "units"))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "jets"))
os.environ["PX_LIGHT"] = "hd"
os.environ["PX_NO_GROUND"] = "1"

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(HERE, "render")
SAMPLES = int(argv[1]) if len(argv) > 1 else 64
MODEL = os.path.join(ROOT, "assets", "inbox", "parachute", "army-parachute", "scene.gltf")

CANOPY_PX = 30.0          # canopy width in world pixels
WIDTH_BU = 1.35           # model canopy width (bounds -0.67 .. 0.67)
UNIT_PX = CANOPY_PX / WIDTH_BU
FRAME = 288               # render pixels (96 world pixels)

bpy.ops.wm.read_factory_settings(use_empty=True)
import render_sprites  # noqa: E402

bpy.ops.import_scene.gltf(filepath=MODEL)
chute = bpy.data.objects.new("Chute", None)
bpy.context.scene.collection.objects.link(chute)
for o in list(bpy.context.scene.objects):
    if o.type == "MESH":
        o.parent = chute
# model z runs -1 (lines meet) .. 1 (canopy top): put the meeting point at the pivot, so the canopy inflates and
# sways around the load; MEET = where the lines meet, ~2 world px above the frame centre
for o in chute.children:
    o.location.z += 1.0
MEET = 2.0 / (UNIT_PX * math.cos(math.radians(render_sprites.ELEVATION)))

scene = render_sprites.setup(frame=FRAME, samples=SAMPLES, unit_px=UNIT_PX)


def pose(open_k, sway, breathe, size=1.0, meet=None):
    """open_k 0 = a tight streamer, 1 = fully inflated; the lines meet at height `meet`."""
    w = (0.18 + 0.82 * open_k ** 0.7) * size * breathe
    h = (1.55 - 0.55 * open_k) * size
    chute.scale = (w, w, h)
    chute.location = (0, 0, MEET if meet is None else meet)
    chute.rotation_euler = (math.radians(sway[0]), math.radians(sway[1]), 0)


os.makedirs(OUT, exist_ok=True)

# Paratrooper canopy
for i in range(5):
    k = (i + 1) / 5
    pose(1 - (1 - k) ** 2, (0, 0), 1.0 + 0.08 * math.sin(k * math.pi))
    render_sprites.render_to(os.path.join(OUT, f"parach-open-{i}.png"))
for i in range(11):
    a = 2 * math.pi * i / 11
    pose(1, (5 * math.sin(a), 4 * math.cos(a)), 1.0 + 0.03 * math.sin(2 * a))
    render_sprites.render_to(os.path.join(OUT, f"parach-idle-{i}.png"))

# Parabomb: a half-size canopy carrying a Mk 82, the bomb at the frame centre
import ordnance  # noqa: E402
bomb = ordnance.build("mk82", 0.19 * 22 / UNIT_PX)      # ~9 world px long
bomb.rotation_euler = (math.radians(-90), 0, 0)          # built along +Y: nose down
bomb.location = (0, 0, 0)
SMALL = 0.5
bomb_len = 2.2 * 0.19 * 22 / UNIT_PX
for i in range(8):
    k = (i + 1) / 8
    pose(1 - (1 - k) ** 2, (0, 0), 1.0, SMALL, bomb_len / 2)
    render_sprites.render_to(os.path.join(OUT, f"parabomb-open-{i}.png"))
for i in range(5):
    a = 2 * math.pi * i / 5
    pose(1, (6 * math.sin(a), 5 * math.cos(a)), 1.0 + 0.03 * math.sin(2 * a), SMALL, bomb_len / 2)
    bomb.rotation_euler = (math.radians(-90 + 5 * math.sin(a)), math.radians(4 * math.cos(a)), 0)
    render_sprites.render_to(os.path.join(OUT, f"parabomb-idle-{i}.png"))
print("rendered parachutes to", OUT)
