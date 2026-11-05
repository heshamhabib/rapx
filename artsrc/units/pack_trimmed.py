#!/usr/bin/env python3
"""
Packs rendered frames into one OpenRA PngSheet with every frame trimmed to its visible pixels: per-frame regions and
offsets in the PNG metadata (Frame[i]: x,y,w,h;offsetX,offsetY, read by the engine's PngSheetLoader). For overlays
that are mostly empty (a missile on a jet frame), the sheet costs only the drawn pixels.

  python3 artsrc/units/pack_trimmed.py <out.png> <frame dir> [<frame dir> ...]

Frames are taken in order: all frame-NN.png of the first dir, then the second, ... (a sequence's Start = index * 32).
An empty frame keeps a 1x1 transparent region so the frame numbering stays intact.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

ALPHA_FLOOR = 6  # the shadow catcher's faint noise, as pack_sprites.py
out, dirs = sys.argv[1], sys.argv[2:]
frames = []
for d in dirs:
    files = sorted(glob.glob(os.path.join(d, "frame-*.png")))
    if not files:
        sys.exit(f"no frames in {d}")
    frames += files

pieces = []
for p in frames:
    a = np.asarray(Image.open(p).convert("RGBA")).copy()
    alpha = a[..., 3].astype(np.float32)
    a[..., 3] = np.clip((alpha - ALPHA_FLOOR) * 255 / (255 - ALPHA_FLOOR), 0, 255).astype(np.uint8)
    h, w = a.shape[:2]
    ys, xs = np.nonzero(a[..., 3])
    if len(xs) == 0:
        pieces.append((np.zeros((1, 1, 4), np.uint8), (0.0, 0.0)))
        continue
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    # Offset: the trimmed region's centre relative to the full frame's centre (pixels, y down)
    pieces.append((a[y0:y1, x0:x1], ((x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2)))

# Shelf packing, rows of up to 2048 px
width = max(2048, max(p[0].shape[1] for p in pieces))
x = y = row = 0
spots = []
for img, _ in pieces:
    ph, pw = img.shape[:2]
    if x + pw > width:
        x, y, row = 0, y + row + 1, 0
    spots.append((x, y))
    x += pw + 1
    row = max(row, ph)
sheet = Image.new("RGBA", (width, y + row + 1), (0, 0, 0, 0))
meta = PngInfo()
for i, ((img, off), (px, py)) in enumerate(zip(pieces, spots)):
    sheet.paste(Image.fromarray(img), (px, py))
    meta.add_text(f"Frame[{i}]", f"{px},{py},{img.shape[1]},{img.shape[0]};{off[0]:.1f},{off[1]:.1f}")
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
sheet.save(out, pnginfo=meta, optimize=True)
print(f"packed {len(pieces)} trimmed frames into {out} ({sheet.size[0]}x{sheet.size[1]})")
