"""Turns the blue paint of the Allied prism art into team-colour green (in place), so PlayerColorShift
(hues 0.22-0.45, rules/palettes.yaml) repaints it in the owner's colour. The cyan crystals and glow strips
are lighter and greener-blue, so they stay as they are.

  python3 artsrc/space/team_paint.py <png> [<png> ...]

Used by artsrc/units/meshes/make.sh (ptnk) and on artsrc/buildings/src/ptwr.png (before build_all.py).
"""
import sys

import numpy as np
from matplotlib.colors import hsv_to_rgb, rgb_to_hsv
from PIL import Image, PngImagePlugin

PAINT_HUES = (0.555, 0.72)  # blue paint; the crystal / glow cyan sits below 0.555
MIN_SAT = 0.18
MAX_VALUE = 0.78            # brighter blue-white is crystal or glow
GREEN = 0.333
SAT_BOOST = 1.7

for path in sys.argv[1:]:
    src = Image.open(path)
    a = np.asarray(src.convert("RGBA")).astype(np.float32) / 255
    hsv = rgb_to_hsv(a[..., :3])
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    paint = (h >= PAINT_HUES[0]) & (h <= PAINT_HUES[1]) & (s >= MIN_SAT) & (v <= MAX_VALUE) & (a[..., 3] > 0)
    hsv[..., 0] = np.where(paint, GREEN, h)
    hsv[..., 1] = np.where(paint, np.minimum(1, s * SAT_BOOST), s)
    a[..., :3] = hsv_to_rgb(hsv)
    # Keep the PNG text chunks: sprite sheets carry FrameSize/FrameAmount, buildings their PxOffset
    meta = PngImagePlugin.PngInfo()
    for k, val in getattr(src, "text", {}).items():
        meta.add_text(k, val)
    Image.fromarray((a * 255).round().astype(np.uint8)).save(path, pnginfo=meta)
    print(f"{path}: {paint.sum()} paint pixels -> team green")
