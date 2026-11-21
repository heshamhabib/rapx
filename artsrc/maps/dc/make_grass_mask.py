#!/usr/bin/env python3
"""
Grass mask for the animated lawns of Washington D.C. (PxBackdropGrass).

  python3 artsrc/maps/dc/make_grass_mask.py [--src build/backdrop-painted.png] [--preview out.png]

Finds the lawns in the backdrop by colour (green, not too dark: shadowed grass still sways, deep shade of trees
does not) and writes mods/rapx/maps/washington-dc/grass-mask.png: .r grass coverage, 16 pixels per cell from the
top-left cell of the map bounds, padded to a power of two. Run it after cut_backdrop.py whenever the backdrop
changes. Defaults to the repainted backdrop, else the Blender render.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "washington-dc")
BUILD = os.path.join(HERE, "build")
PPC = 16
Image.MAX_IMAGE_PIXELS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--preview")
    a = ap.parse_args()
    src = a.src or ("build/backdrop-painted.png" if os.path.exists(os.path.join(BUILD, "backdrop-painted.png")) else "build/backdrop.png")
    nx, ny = json.load(open(os.path.join(BUILD, "layout.json")))["cells"]
    work = PPC * 2
    img = Image.open(os.path.join(HERE, src)).convert("RGB").resize((nx * work, ny * work), Image.LANCZOS)
    hsv = np.asarray(img.convert("HSV")).astype(np.float32) / 255
    h, s, v = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    grass = (h > 38) & (h < 150) & (s > 0.20) & (v > 0.12)      # sunset: sunlit grass turns yellow-orange
    grass = ndimage.binary_opening(grass, iterations=2)
    grass = ndimage.binary_closing(grass, iterations=2)
    labels, k = ndimage.label(grass)
    if k:                                          # lawns, not single green pixels (signs, cars, copper roofs)
        sizes = ndimage.sum(grass, labels, range(1, k + 1))
        grass = np.isin(labels, np.flatnonzero(sizes > 4 * work * work) + 1)
    grass = ndimage.binary_erosion(grass, iterations=2)
    cover = np.asarray(Image.fromarray((grass * 255).astype(np.uint8)).resize((nx * PPC, ny * PPC), Image.BOX), np.float32) / 255
    cover = np.minimum(cover, ndimage.gaussian_filter(cover, 1.5) * 1.5).clip(0, 1)
    out = np.zeros((1 << (ny * PPC - 1).bit_length(), 1 << (nx * PPC - 1).bit_length(), 4), np.uint8)
    out[..., 3] = 255
    out[:ny * PPC, :nx * PPC, 0] = np.round(cover * 255)
    Image.fromarray(out).save(os.path.join(MAP_DIR, "grass-mask.png"), optimize=True)
    print(f"{src}: grass cells {cover.sum() / PPC / PPC:.0f} of {nx * ny}")
    if a.preview:
        base = np.asarray(img.resize((nx * PPC, ny * PPC))).astype(np.float32)
        tint = base * (1 - 0.5 * cover[..., None]) + np.array([255, 0, 255]) * 0.5 * cover[..., None]
        Image.fromarray(tint.astype(np.uint8)).save(a.preview)


if __name__ == "__main__":
    main()
