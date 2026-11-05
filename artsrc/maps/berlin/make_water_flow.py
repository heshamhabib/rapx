#!/usr/bin/env python3
"""
Flow map for the animated Spree on the painted Berlin backdrop (PxBackdropWater).

  python3 artsrc/maps/berlin/make_water_flow.py [--preview out.png]

Reads the shipped backdrop chunks (mods/rapx/maps/berlin-1946/backdrop-<col>-<row>.png), finds the painted river by
its teal colour near the layout's Spree line (the oblique render shifts it off the cell grid, so the layout curve
alone does not fit), and writes mods/rapx/maps/berlin-1946/water-flow.png at PPC pixels per cell (padded to a
power of two):
  R  water coverage (anti-aliased; bridges, boats and overhanging buildings are excluded by colour)
  G  flow direction angle, 0.5 = due west (the Spree flows west), 0..1 = -pi..pi around it
  B  distance from the nearest bank, 1 = BANK_CELLS cells or more (the current is slower and foamier at the banks)
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "berlin-1946")
SRC_PPC = 64            # backdrop pixels per cell
PPC = 16                # flow map pixels per cell
CORRIDOR = 7.5          # cells around the layout's Spree line that may hold river water
BANK_CELLS = 2.5


def load_backdrop():
    cols = (layout.NX + 15) // 16
    rows = (layout.NY + 15) // 16
    full = Image.new("RGB", (cols * 1024, rows * 1024))
    for c in range(cols):
        for r in range(rows):
            full.paste(Image.open(os.path.join(MAP_DIR, f"backdrop-{c}-{r}.png")).convert("RGB"), (c * 1024, r * 1024))
    return full.crop((0, 0, layout.NX * SRC_PPC, layout.NY * SRC_PPC))


def spree_frame(px, py):
    """Distance to the layout's Spree line and the downstream (westward) unit tangent of its nearest segment."""
    best = np.full(px.shape, np.inf)
    tx = np.zeros(px.shape)
    ty = np.zeros(px.shape)
    for (ax, ay), (bx, by) in zip(layout.SPREE, layout.SPREE[1:]):
        d = layout.seg_dist(px, py, ax, ay, bx, by)
        sel = d < best
        best[sel] = d[sel]
        n = math.hypot(bx - ax, by - ay)
        tx[sel], ty[sel] = (ax - bx) / n, (ay - by) / n      # SPREE runs west -> east; the water flows east -> west
    return best, tx, ty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    args = ap.parse_args()

    # Classify at 2x the output resolution, then reduce for anti-aliased edges
    work = PPC * 2
    img = load_backdrop().resize((layout.NX * work, layout.NY * work), Image.LANCZOS)
    hsv = np.asarray(img.convert("HSV")).astype(np.float32) / 255.0
    h, s, v = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    teal = (h > 150) & (h < 215) & (s > 0.10) & (v > 0.07) & (v < 0.70)
    # Water in the quay walls' shadow turns olive-dark; warm ruins stay below hue 60
    teal |= (h > 95) & (h < 215) & (s > 0.08) & (v > 0.05) & (v < 0.30)

    py, px = (np.mgrid[0:layout.NY * work, 0:layout.NX * work] + 0.5) / work
    # The oblique render moved the river about 2.5 cells north of the layout line
    dist, _, _ = spree_frame(px, py + 2.5)
    teal &= dist < CORRIDOR

    # Clean up speckles, fill reflections/shadow detail inside the water, keep the river body only
    teal = ndimage.binary_opening(teal, iterations=2)
    teal = ndimage.binary_closing(teal, iterations=4)
    # Bridge in the notches that dark reflections bite out of the edge, but never onto the bright quay stone
    quay = (v > 0.32) & (h < 70)
    teal |= ndimage.binary_closing(teal, structure=np.ones((3, 3)), iterations=12) & ~ndimage.binary_dilation(quay, iterations=2)
    teal = ndimage.binary_fill_holes(teal)
    labels, n = ndimage.label(teal)
    if n:
        sizes = ndimage.sum(teal, labels, range(1, n + 1))
        keep = np.flatnonzero(sizes > 0.05 * sizes.max()) + 1
        teal = np.isin(labels, keep)

    # Pull the edge in a little so quay walls are never smeared into the water
    teal = ndimage.binary_erosion(teal, iterations=2)
    cover = np.asarray(Image.fromarray((teal * 255).astype(np.uint8)).resize((layout.NX * PPC, layout.NY * PPC), Image.BOX),
        np.float32) / 255.0
    # A soft rim so the moving surface melts into the painted water instead of ending on a hard line
    cover = np.minimum(cover, ndimage.gaussian_filter(cover, 1.5) * 1.6).clip(0, 1)

    bank = ndimage.distance_transform_edt(teal) / work
    bank = np.asarray(Image.fromarray(bank.astype(np.float32)).resize((layout.NX * PPC, layout.NY * PPC), Image.BILINEAR))

    py, px = (np.mgrid[0:layout.NY * PPC, 0:layout.NX * PPC] + 0.5) / PPC
    _, tx, ty = spree_frame(px, py + 2.5)
    # Blend the per-segment tangents smoothly around the bends
    tx = ndimage.gaussian_filter(tx, PPC * 3)
    ty = ndimage.gaussian_filter(ty, PPC * 3)
    angle = np.arctan2(ty, tx) - math.pi              # 0 = due west
    angle = (angle + math.pi) % (2 * math.pi) - math.pi

    size = 1 << max(layout.NX * PPC - 1, layout.NY * PPC - 1).bit_length()
    out = np.zeros((size, size, 4), np.uint8)
    out[..., 3] = 255
    out[:layout.NY * PPC, :layout.NX * PPC, 0] = np.round(cover * 255)
    out[:layout.NY * PPC, :layout.NX * PPC, 1] = np.round((angle / (2 * math.pi) + 0.5) * 255)
    out[:layout.NY * PPC, :layout.NX * PPC, 2] = np.round(np.clip(bank / BANK_CELLS, 0, 1) * 255)
    path = os.path.join(MAP_DIR, "water-flow.png")
    Image.fromarray(out).save(path, optimize=True)
    print(f"{path}: {size}x{size}, water cells {cover.sum() / PPC / PPC:.0f}")

    if args.preview:
        base = img.resize((layout.NX * PPC, layout.NY * PPC)).convert("RGB")
        tint = np.asarray(base, np.float32)
        tint[..., 0] = tint[..., 0] * (1 - cover) + 255 * cover * 0.8 + tint[..., 0] * cover * 0.2
        Image.fromarray(tint.astype(np.uint8)).save(args.preview)


if __name__ == "__main__":
    main()
