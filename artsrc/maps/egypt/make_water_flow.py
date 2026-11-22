#!/usr/bin/env python3
"""
Trims the animated-water mask of Egypt (Cairo and Giza) (PxBackdropWater) to the water the backdrop really shows.

  python3 artsrc/maps/egypt/make_water_flow.py [--src build/backdrop.png] [--preview out.png]

layout.py writes mods/rapx/maps/egypt-cairo-giza/water-flow.png from the water cells (the Potomac, the Reflecting Pool,
the Tidal Basin). Bridges and leaning buildings cross the water in the picture; the water shader would make them
wobble, so the mask (R channel) keeps only pixels that look like the painted water, slightly shrunk. Run it after
cut_backdrop.py whenever the backdrop changes.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "egypt-cairo-giza")
BUILD = os.path.join(HERE, "build")
PPC = 16
Image.MAX_IMAGE_PIXELS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="build/backdrop.png")
    ap.add_argument("--preview")
    a = ap.parse_args()
    nx, ny = json.load(open(os.path.join(BUILD, "layout.json")))["cells"]
    flow = np.asarray(Image.open(os.path.join(MAP_DIR, "water-flow.png")).convert("RGBA")).copy()
    cover = flow[:ny * PPC, :nx * PPC, 0].astype(np.float32) / 255
    img = Image.open(os.path.join(HERE, a.src)).convert("RGB").resize((nx * PPC, ny * PPC), Image.LANCZOS)
    hsv = np.asarray(img.convert("HSV")).astype(np.float32) / 255
    h, s = hsv[..., 0] * 360, hsv[..., 1]
    # Keep the layout's water except what is painted bright over it (bridge decks, balustrades, boats, banks: light
    # stone and pavement); the golden reflections are bright but saturated and orange, so they stay water
    v = hsv[..., 2]
    solid = (v > 0.55) & (s < 0.35)
    solid = ndimage.binary_dilation(solid, iterations=2)
    keep = ndimage.gaussian_filter((~solid).astype(np.float32), 1.0)
    # Landmarks lean north over the water (the Cairo Tower over the Nile): never ripple anything drawn there
    L = json.load(open(os.path.join(BUILD, "layout.json")))
    lm = np.zeros_like(keep, dtype=bool)
    py, px = (np.mgrid[0:ny * PPC, 0:nx * PPC] + 0.5) / PPC
    for key, (x0, y0, x1, y1) in L["landmarks"].items():
        lean = L["heights"].get(key, 0) / np.tan(np.radians(50)) / L["cell_m"]
        lm |= (px >= x0 - 0.5) & (px < x1 + 0.5) & (py >= y0 - lean - 0.8) & (py < y1 + 0.3)
    keep = keep * np.clip(1.0 - ndimage.gaussian_filter(lm.astype(np.float32), 3.0) * 2.0, 0, 1)
    out = cover * keep
    flow[:ny * PPC, :nx * PPC, 0] = np.round(out * 255)
    Image.fromarray(flow).save(os.path.join(MAP_DIR, "water-flow.png"), optimize=True)
    print(f"water cells {cover.sum() / PPC / PPC:.0f} -> {out.sum() / PPC / PPC:.0f}")
    if a.preview:
        base = np.asarray(img).astype(np.float32)
        tint = base * (1 - 0.5 * out[..., None]) + np.array([255, 0, 0]) * 0.5 * out[..., None]
        Image.fromarray(tint.astype(np.uint8)).save(a.preview)


if __name__ == "__main__":
    main()
