#!/usr/bin/env python3
"""
Cuts a generated env sheet (see env-sheets.md) back into its parts: one image per grid cell, in reading order.

The cut lines are the clean magenta gaps nearest to where the grid puts them, so a sheet whose objects are a
little off-centre still cuts cleanly. A sheet is rejected (SliceError) when a gap is not clean (something
crosses between cells), a cell is empty, a two-up cell is missing one of its copies, or a terrain tile is not
a filled rectangle of the expected shape; generate_images.py then asks for the sheet again.

  python3 slice_sheet.py SHEET.png 2x2 obj [OUT_DIR]     # try it by hand; writes cell-N.png
"""
import os
import sys

import numpy as np
from PIL import Image

GAP_CLEAN = 0.985    # a gap row/column must be this much background
GAP_MIN = 0.96       # ... or at least this, when no fully clean line exists near the expected cut
SEARCH = 0.22        # look for the gap within this fraction of a cell around the expected cut
MIN_CONTENT = 0.01   # a cell must have this much non-background
TILE_FILL = 0.85     # a tile's bounding box must be this full
TILE_ASPECT = 0.25   # and within this relative error of the expected w:h


class SliceError(Exception):
    pass


def background(rgb):
    """Magenta and magenta in shadow (the objects cast their shadows onto the background)."""
    r, g, b = (rgb[..., i].astype(np.int32) for i in range(3))
    lo = np.minimum(r, b)
    return (lo > 50) & (g * 100 < lo * 45) & (np.abs(r - b) * 100 < np.maximum(r, b) * 35)


def find_cut(profile, expected, cell):
    """Index of the cleanest gap line near `expected` in a 1-D background-fraction profile."""
    lo, hi = max(0, int(expected - SEARCH * cell)), min(len(profile), int(expected + SEARCH * cell) + 1)
    window = profile[lo:hi]
    clean = np.flatnonzero(window >= GAP_CLEAN)
    if clean.size:
        # split the clean lines into runs and cut through the middle of the run closest to the expected line
        runs = np.split(clean, np.flatnonzero(np.diff(clean) > 1) + 1)
        mids = [lo + (run[0] + run[-1]) // 2 for run in runs]
        return min(mids, key=lambda m: abs(m - expected))
    best = int(np.argmax(window))
    if window[best] < GAP_MIN:
        raise SliceError("no clean gap near %d (best line is %.0f%% background)" % (expected, 100 * window[best]))
    return lo + best


def cuts(mask, n, axis):
    """n-1 cut positions splitting `mask` into n bands along axis (0 = rows, 1 = columns)."""
    profile = mask.mean(axis=1 - axis)
    size = mask.shape[axis]
    return [0] + [find_cut(profile, i * size / n, size / n) for i in range(1, n)] + [size]


def check_cell(mask, kind, label):
    if mask.size == 0 or (~mask).mean() < MIN_CONTENT:
        raise SliceError("%s is empty" % label)
    if kind in ("tree2", "bld2"):  # both copies present: content in each half
        half = mask.shape[1] // 2
        for side, m in (("left", mask[:, :half]), ("right", mask[:, half:])):
            if (~m).mean() < MIN_CONTENT / 2:
                raise SliceError("%s: %s copy missing" % (label, side))


def crop_tile(img, mask, aspect, label):
    """Crops a tile cell to its painted rectangle and checks the shape."""
    rows = np.flatnonzero((~mask).mean(axis=1) > 0.5)
    cols = np.flatnonzero((~mask).mean(axis=0) > 0.5)
    if not rows.size or not cols.size:
        raise SliceError("%s: no tile found" % label)
    y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    fill = (~mask[y0:y1, x0:x1]).mean()
    if fill < TILE_FILL:
        raise SliceError("%s: tile is not a filled rectangle (%.0f%% filled)" % (label, 100 * fill))
    want, got = aspect[0] / aspect[1], (x1 - x0) / (y1 - y0)
    if abs(got / want - 1) > TILE_ASPECT:
        raise SliceError("%s: tile shape %.2f, expected %.2f" % (label, got, want))
    return img.crop((x0, y0, x1, y1))


def slice_sheet(path, rows, cols, kind, aspect=(1, 1)):
    """Returns the cell images in reading order, or raises SliceError."""
    img = Image.open(path).convert("RGB")
    mask = background(np.asarray(img))
    out = []
    ys = cuts(mask, rows, 0)
    for r, (y0, y1) in enumerate(zip(ys[:-1], ys[1:])):
        band = mask[y0:y1]
        xs = cuts(band, cols, 1)
        for c, (x0, x1) in enumerate(zip(xs[:-1], xs[1:])):
            label = "cell %d" % (r * cols + c + 1)
            m = band[:, x0:x1]
            check_cell(m, kind, label)
            cell = img.crop((x0, y0, x1, y1))
            out.append(crop_tile(cell, m, aspect, label) if kind == "tile" else cell)
    return out


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    rows, cols = (int(v) for v in sys.argv[2].split("x"))
    out = sys.argv[4] if len(sys.argv) > 4 else "."
    try:
        cells = slice_sheet(sys.argv[1], rows, cols, sys.argv[3])
    except SliceError as e:
        sys.exit("rejected: %s" % e)
    os.makedirs(out, exist_ok=True)
    for n, im in enumerate(cells, 1):
        im.save(os.path.join(out, "cell-%d.png" % n))
        print("cell-%d.png %dx%d" % (n, im.width, im.height))


if __name__ == "__main__":
    main()
