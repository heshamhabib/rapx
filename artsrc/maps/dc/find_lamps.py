#!/usr/bin/env python3
"""
Finds the street lamps painted into the Washington D.C. backdrop and writes them as animated lights.

  python3 artsrc/maps/dc/find_lamps.py [--src build/backdrop-painted.png] [--preview out.png]

The repaint moves lamps a little, so the lights must come from the painted picture, not from the Blender scene: a lamp
head is a small, very bright, warm (orange-yellow) blob. Lit windows are warm too but they sit inside building cells
(blocked in the layout) and come in rows; lamps stand on road, pavement or lawn cells. Bridge lamps count as lamps.
Output: build/lights.txt and mods/rapx/maps/washington-dc/lights.txt (PxBackdropLights format, kind `lamp`).
"""
import argparse
import json
import os
import shutil

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
BUILD = os.path.join(HERE, "build")
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "washington-dc")
PPC = 64
Image.MAX_IMAGE_PIXELS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="build/backdrop-painted.png")
    ap.add_argument("--preview")
    a = ap.parse_args()
    L = json.load(open(os.path.join(BUILD, "layout.json")))
    nx, ny = L["cells"]
    grid = L["grid"]
    img = Image.open(os.path.join(HERE, a.src)).convert("RGB")
    # A painted lamp head: a white-hot core (nearly colourless, brightest pixels) wrapped in a saturated orange
    # halo. Lane markings and kerbs are white too, but long and without the halo; sunlit paving is bright but
    # pale; lit windows are inside buildings (blocked cells).
    hsv = np.asarray(img.convert("HSV")).astype(np.float32) / 255
    h, sat, v = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    core = (v > 0.95) & (sat < 0.25)                        # white-hot, not a sunlit orange highlight
    orange = ((h > 12) & (h < 50) & (sat > 0.45) & (v > 0.55)).astype(np.float32)
    halo = ndimage.uniform_filter(orange, 25)
    labels, n = ndimage.label(core)
    out = []
    for i, sl in enumerate(ndimage.find_objects(labels), 1):
        if sl is None:
            continue
        hgt, wid = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = int((labels[sl] == i).sum())
        if area < 4 or area > 220 or max(hgt, wid) > 24 or max(hgt, wid) > 2.5 * max(1, min(hgt, wid)):
            continue
        cy, cx = (sl[0].start + sl[0].stop) / 2, (sl[1].start + sl[1].stop) / 2
        if halo[int(cy), int(cx)] < 0.22:                      # a quarter of the 25 px box round it glows orange
            continue
        x, y = cx / PPC, cy / PPC
        foot = grid[min(ny - 1, int(y + 0.6))][min(nx - 1, int(x))]
        if foot in "#~":
            continue
        out.append((x, y))
    # Merge heads closer than 0.6 cells (double lanterns)
    merged = []
    for x, y in out:
        if all((x - mx) ** 2 + (y - my) ** 2 > 0.64 for mx, my in merged):   # double lanterns = one lamp
            merged.append((x, y))
    lines = ["# Washington D.C. street lamps found in the painted backdrop (find_lamps.py): kind x y r g b size"]
    lines += [f"lamp {x:.3f} {y:.3f} 1.000 0.620 0.300 1.00" for x, y in merged]
    for path in (os.path.join(BUILD, "lights.txt"), os.path.join(MAP_DIR, "lights.txt")):
        open(path, "w").write("\n".join(lines) + "\n")
    print(f"{len(merged)} lamps")
    if a.preview:
        from PIL import ImageDraw
        pv = img.resize((nx * 16, ny * 16))
        d = ImageDraw.Draw(pv)
        for x, y in merged:
            d.ellipse([x * 16 - 6, y * 16 - 6, x * 16 + 6, y * 16 + 6], outline=(0, 255, 255), width=2)
        pv.save(a.preview)


if __name__ == "__main__":
    main()
