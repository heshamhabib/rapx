#!/usr/bin/env python3
"""
Packs rendered facing frames (frame-NN.png from render_sprites.py) into one OpenRA PngSheet:
a grid of COLS frames per row, with FrameSize / FrameAmount metadata for the engine.

  python3 artsrc/units/pack_sprites.py <render dir> <out.png> [cols]
"""
import glob
import os
import sys

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

src, out = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 8

# The shadow catcher leaves faint noise (alpha 1-6) over the whole frame, which shows in-game
# as a light square around the unit. Remove it and rescale the rest of the alpha range.
ALPHA_FLOOR = 6


def clean(img):
    a = np.asarray(img.convert("RGBA")).copy()
    alpha = a[..., 3].astype(np.float32)
    a[..., 3] = np.clip((alpha - ALPHA_FLOOR) * 255 / (255 - ALPHA_FLOOR), 0, 255).astype(np.uint8)
    return Image.fromarray(a)


frames = [clean(Image.open(p)) for p in sorted(glob.glob(os.path.join(src, "frame-*.png")))]
if not frames:
    sys.exit(f"no frames in {src}")
w, h = frames[0].size
rows = (len(frames) + cols - 1) // cols
sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
for i, f in enumerate(frames):
    sheet.paste(f, ((i % cols) * w, (i // cols) * h))

meta = PngInfo()
meta.add_text("FrameSize", f"{w},{h}")
meta.add_text("FrameAmount", str(len(frames)))
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
sheet.save(out, pnginfo=meta, optimize=True)
print(f"packed {len(frames)} frames ({w}x{h}) into {out}")
