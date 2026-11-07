#!/usr/bin/env python3
"""
Our own "mini bibs" (IDEA-31): the ragged gravel patches drawn by WithBuildingBib under the small defences and
support buildings (SAM, AA gun, gap generator, service depot, flame tower, turret, hospital, Iron Curtain, silo /
kennel, pillbox, Chronosphere, Tesla coil). The classic mb*.tem files came from OpenRA's RA mod (edits of the
original art).

Only each patch's outline is taken from the classic frame (so it sits under the building as before); the outline is
smoothed at 3x and filled with our own gravel texture, one colourway per tileset. Writes
mods/rapx/bits/hd/ui/mb<name>-<tileset>.png (one 72x72 frame per cell, shown with Scale 0.3333).

  python3 artsrc/sprites/make_minibibs.py
"""
import glob
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "terrain"))
import make_base_tiles as mbt  # noqa: E402  (utility() export helper)
import make_ui_sprites as ui  # noqa: E402

NAMES = ["SAM", "AGUN", "GAP", "FIX", "FTUR", "GUN", "HOSP", "IRON", "SILO", "PBOX", "PDOX", "TSLA"]
# tileset -> (gravel base colour, speckle colours)
LOOK = {
    "temperate": ((112, 104, 92), [(80, 74, 66), (146, 138, 124), (60, 56, 50)]),
    "snow": ((168, 170, 176), [(128, 128, 134), (226, 228, 234), (100, 100, 108)]),
    "desert": ((168, 140, 104), [(132, 108, 78), (204, 178, 138), (104, 84, 60)]),
}
CACHE = os.path.join(ROOT, "assets", "terrain-classic", "minibibs")


def outlines(name):
    """Alpha masks (24x24 bool) of the classic mb<name>.tem frames, exported once into the cache."""
    os.makedirs(CACHE, exist_ok=True)
    stem = f"mb{name}"
    if not glob.glob(os.path.join(CACHE, stem + "-*.png")):
        if not os.path.exists(os.path.join(CACHE, "temperat.pal")):
            mbt.utility("--extract", "temperat.pal", cwd=CACHE)
        mbt.utility("--extract", stem + ".tem", cwd=CACHE)
        mbt.utility("--png", stem + ".tem", "temperat.pal", cwd=CACHE)
        os.remove(os.path.join(CACHE, stem + ".tem"))
    files = sorted(glob.glob(os.path.join(CACHE, stem + "-*.png")), key=lambda p: int(p.rsplit("-", 1)[1][:-4]))
    return [np.asarray(Image.open(f).convert("RGBA"))[..., 3] > 0 for f in files]


def gravel(mask, terrain, rng):
    base, specks = LOOK[terrain]
    S = ui.S
    soft = gaussian_filter(zoom(mask.astype(np.float32), S, order=1), 2.2)
    edge_noise = gaussian_filter(rng.normal(0, 1, soft.shape), 1.5) * 0.12
    alpha = np.clip((soft + edge_noise - 0.42) / 0.12, 0, 1)
    h, w = soft.shape
    rgb = np.ones((h, w, 3)) * np.array(base, np.float32)
    rgb *= (1 + gaussian_filter(rng.normal(0, 1, (h, w)), 2.0)[..., None] * 0.35)
    for col in specks:
        dots = gaussian_filter((rng.random((h, w)) < 0.06).astype(np.float32), 0.7) > 0.12
        rgb[dots] = rgb[dots] * 0.4 + np.array(col) * 0.6
    rgb *= (0.82 + 0.18 * alpha)[..., None]  # slightly darker towards the ragged rim
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8))


def main():
    for name in NAMES:
        masks = outlines(name)
        for terrain in LOOK:
            rng = np.random.default_rng(abs(hash((name, terrain))) % 2 ** 32)
            ui.save_sheet(f"mb{name.lower()}-{terrain}", [gravel(m, terrain, rng) for m in masks])


if __name__ == "__main__":
    main()
