#!/usr/bin/env python3
"""
Trims the animated-water mask of Ironward (PxBackdropWater) to the water the painted backdrop really shows.

  python3 artsrc/maps/ironward/make_water_flow.py [--src build/backdrop-painted.png] [--preview out.png]

layout.py writes mods/rapx/maps/ironward/water-flow.png from the exact canal cells. High things lean north over the
canals in the picture, and the water shader would make them wobble, so this removes from the mask (R channel):
  - the elevated railway ring (14 m up: drawn 1.7 cells north of its ground line) where it crosses the arms,
  - the arches of the arm bridges (up to 11 m: up to 1.6 cells north of the deck),
  - anything bright or warm in the painted picture (lamps, lit windows, snow on leaning roofs), slightly grown.
Run it after cut_backdrop.py whenever the backdrop or the layout changes.
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "ironward")
BUILD = os.path.join(HERE, "build")
PPC = 16                                  # flow map pixels per cell
SHEAR = 1 / math.tan(math.radians(50))
Image.MAX_IMAGE_PIXELS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="build/backdrop-painted.png")
    ap.add_argument("--preview")
    a = ap.parse_args()
    L = json.load(open(os.path.join(BUILD, "layout.json")))
    n, cell = L["cells"][0], L["cell_m"]
    flow = np.asarray(Image.open(os.path.join(MAP_DIR, "water-flow.png")).convert("RGBA")).copy()
    cover = flow[:n * PPC, :n * PPC, 0].astype(np.float32) / 255
    py, px = (np.mgrid[0:n * PPC, 0:n * PPC] + 0.5) / PPC
    keep = np.ones_like(cover)

    # Railway ring: radius 31 cells round the centre, drawn 14 m * shear north; deck and trusses about 1 cell wide
    lift = 14 * SHEAR / cell
    rr = np.hypot(px - n / 2, py - (n / 2 - lift))
    keep[np.abs(rr - 31) < 1.1] = 0
    # Bridge arches lean north of the arm bridges
    for b in L["bridges"]:
        if b["kind"] != "arm":
            continue
        x0, y0, x1, y1 = b["rect"]
        keep[(px >= x0 - 0.5) & (px < x1 + 0.5) & (py >= y0 - 1.8) & (py < y1)] = 0
    # Bright or warm painted detail over the water
    img = Image.open(os.path.join(HERE, a.src)).convert("RGB").resize((n * PPC, n * PPC), Image.LANCZOS)
    hsv = np.asarray(img.convert("HSV")).astype(np.float32) / 255
    bright = (hsv[..., 2] > 0.32) | ((hsv[..., 0] < 0.17) & (hsv[..., 1] > 0.35) & (hsv[..., 2] > 0.2))
    keep[ndimage.binary_dilation(bright, iterations=2)] = 0
    keep = ndimage.gaussian_filter(keep, 1.0)
    out = cover * np.clip(keep * 1.4 - 0.2, 0, 1)
    flow[:n * PPC, :n * PPC, 0] = np.round(out * 255)
    Image.fromarray(flow).save(os.path.join(MAP_DIR, "water-flow.png"), optimize=True)
    print(f"water cells {cover.sum() / PPC / PPC:.0f} -> {out.sum() / PPC / PPC:.0f}")
    if a.preview:
        base = np.asarray(img).astype(np.float32)
        tint = base * (1 - 0.45 * out[..., None]) + np.array([255, 0, 0]) * 0.45 * out[..., None]
        Image.fromarray(tint.astype(np.uint8)).save(a.preview)


if __name__ == "__main__":
    main()
