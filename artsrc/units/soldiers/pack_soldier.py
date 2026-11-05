#!/usr/bin/env python3
"""
Packs rendered soldier frames (render_soldier.py: <dir>/f<facing>-<n>.png) into an OpenRA PngSheet:
facing-major (all frames of facing 0, then facing 1, ...), counter-clockwise from north, like UseClassicFacings: False.

  python3 artsrc/units/soldiers/pack_soldier.py <render dir> <out.png> [frames]

frames: comma-separated frame numbers to take (default all), e.g. "0" for a still pose.
"""
import glob
import os
import re
import sys

import numpy as np
from PIL import Image, ImageFilter
from PIL.PngImagePlugin import PngInfo

src, out = sys.argv[1], sys.argv[2]
pick = [int(f) for f in sys.argv[3].split(",")] if len(sys.argv) > 3 else None

files = {}
for p in glob.glob(os.path.join(src, "f*-*.png")):
    m = re.match(r"f(\d+)-(\d+)\.png", os.path.basename(p))
    files[(int(m.group(1)), int(m.group(2)))] = p
facings = max(f for f, _ in files) + 1
frames = pick or sorted({n for _, n in files})

ALPHA_FLOOR = 6  # shadow-catcher noise, see artsrc/units/pack_sprites.py


def clean(img):
    a = np.asarray(img.convert("RGBA")).copy()
    alpha = a[..., 3].astype(np.float32)
    a[..., 3] = np.clip((alpha - ALPHA_FLOOR) * 255 / (255 - ALPHA_FLOOR), 0, 255).astype(np.uint8)
    out = Image.fromarray(a)
    # Light sharpening so folds and gear survive the 1/3 scale-down in game (colour only, alpha untouched)
    rgb = out.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=70, threshold=2))
    out = Image.merge("RGBA", (*rgb.split(), out.getchannel("A")))
    return out


tiles = [clean(Image.open(files[(f, n)])) for f in range(facings) for n in frames]
w, h = tiles[0].size
cols = 16
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * w, (i // cols) * h))
meta = PngInfo()
meta.add_text("FrameSize", f"{w},{h}")
meta.add_text("FrameAmount", str(len(tiles)))
meta.add_text("Facings", str(facings))
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
sheet.save(out, pnginfo=meta, optimize=True)
print(f"packed {facings} facings x {len(frames)} frames ({w}x{h}) into {out}")
