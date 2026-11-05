#!/usr/bin/env python3
"""
Writes mods/rapx/rules/airfield-slots.yaml: the parking slots of the IDEA-06 airfields, measured from their HD art.

Each pad in the sprite (mods/rapx/bits/hd/<id>.png) is a team-colour (green) outline. Its centre becomes a
Reservable SlotOffset (relative to the building centre, in world units), so planes park exactly on the painted pads.
The engine draws sprite pixel p at  actor + Scale * (p - size / 2 + Offset)  (SpriteRenderer), Scale = 1 / DENSITY
for airfields (build_all.py NOT_GROWN). Every slot must lie in its own footprint cell: the engine finds the building
under a landed plane by its cell, and a parked plane blocks landing in its cell.

  python3 artsrc/buildings/make_airfield_slots.py            write the rules
  python3 artsrc/buildings/make_airfield_slots.py --preview  also draw the slots into artsrc/buildings/preview/
"""
import argparse
import os
import re

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, binary_fill_holes, label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
HD = os.path.join(ROOT, "mods", "rapx", "bits", "hd")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-structures.yaml")
OUT = os.path.join(ROOT, "mods", "rapx", "rules", "airfield-slots.yaml")
PREVIEW = os.path.join(HERE, "preview")
DENSITY = 3.0
CELL = 24  # world pixels per cell
WDIST = 1024  # world units per cell

# image id -> (actors using it, footprint (w, h), pad grid in the art (columns, rows))
AIRFIELDS = {
    "afld": (["AFLD"], (6, 5), (2, 2)),
    "abas": (["ABAS"], (8, 7), (3, 2)),
    "afbs": (["AFBS"], (12, 9), (4, 2)),
    "sacm": (["SACM"], (20, 15), (5, 2)),
}
# Parked planes face the viewer (south): the pads are wider than deep and a MiG facing south is 33 x 24 px.
FACING = 512


def sequence_offset(image):
    with open(SEQUENCES) as f:
        text = f.read()
    block = re.search(rf"^{image}:\n(.*?)(?=^\S|\Z)", text, re.M | re.S).group(1)
    x, y = re.search(r"Offset: (-?\d+),(-?\d+)", block).groups()
    return int(x), int(y)


def detect_pads(path):
    """Centres (sprite px) of the green pad outlines. The outlines are thin and broken after scaling, so they are
    thickened until they close; roofs and other solid green parts are dropped (an outline covers little of its box).
    Returns the detection with the most pads of a common size, and the typical pad size."""
    im = np.asarray(Image.open(path).convert("RGBA")).astype(int)
    r, g, b, a = im[..., 0], im[..., 1], im[..., 2], im[..., 3]
    green = (g > 120) & (g > r + 40) & (g > b + 40) & (a > 128)
    best = ([], (0, 0))
    for iterations in range(3, 8):
        lab, n = label(binary_fill_holes(binary_dilation(green, iterations=iterations)))
        found = []
        for i in range(1, n + 1):
            ys, xs = np.nonzero(lab == i)
            w, h = np.ptp(xs) + 1, np.ptp(ys) + 1
            ring = green[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean()
            if w > 30 and h > 20 and ring < 0.2 and 1.05 < w / h < 1.8:
                found.append((xs.mean(), ys.mean(), w, h))
        if found:
            median = np.median([f[2] * f[3] for f in found])
            found = [f for f in found if 0.7 * median < f[2] * f[3] < 1.4 * median]
            # Pads have neighbours; a lone match (a window, a sign on the tower) does not
            reach = 1.6 * np.median([f[2] for f in found])
            found = [f for f in found if any(0 < np.hypot(f[0] - o[0], f[1] - o[1]) < reach for o in found)]
        if len(found) > len(best[0]):
            best = ([(f[0], f[1]) for f in found], (np.median([f[2] for f in found]), np.median([f[3] for f in found])))
    return best


def fit_grid(points, cols, rows):
    """The pads sit on a regular (slightly skewed) grid: centre(i, j) = O + i * U + j * V. Finds U (along a row)
    and V (to the next row) from the detected pads, fits the grid to them and returns all cols x rows centres,
    back row first, left to right."""
    pts = np.array(points, dtype=float)
    diffs = [q - p for p in pts for q in pts if (q - p)[0] > 20 and abs((q - p)[1]) < 0.3 * (q - p)[0]]
    # Neighbour steps along a row; average them (a pad's detected box can be a little off-centre)
    shortest = min(np.hypot(*d) for d in diffs)
    u = np.mean([d for d in diffs if np.hypot(*d) < 1.4 * shortest], axis=0)
    candidates = []
    for p in pts:
        for q in pts:
            d = q - p
            if d[1] <= 20:
                continue
            k = round(np.dot(d, u) / np.dot(u, u))
            # Pads of the same row reduce to (almost) nothing: only real row steps count
            if np.hypot(*(d - k * u)) > 0.4 * np.hypot(*u):
                candidates.append(d - k * u)
    v = min(candidates, key=lambda d: np.hypot(*d))
    # Integer grid index of every pad relative to the first, then least squares for O, U, V
    basis = np.array([u, v]).T
    idx = np.rint(np.linalg.solve(basis, (pts - pts[0]).T).T).astype(int)
    idx -= idx.min(axis=0)
    if idx[:, 0].max() >= cols or idx[:, 1].max() >= rows:
        raise SystemExit(f"pads do not fit a {cols} x {rows} grid: {idx.tolist()}")
    a = np.column_stack([np.ones(len(pts)), idx[:, 0], idx[:, 1]])
    coef, *_ = np.linalg.lstsq(a, pts, rcond=None)
    return [tuple(coef[0] + i * coef[1] + j * coef[2]) for j in range(rows) for i in range(cols)], len(pts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    lines = [
        "# Parking slots of the airfields (RedAlert Project X, IDEA-06).",
        "# GENERATED by artsrc/buildings/make_airfield_slots.py from the HD art - edit that script, not this file.",
        "",
    ]
    ok = True
    for image, (actors, (fw, fh), (cols, rows)) in AIRFIELDS.items():
        path = os.path.join(HD, f"{image}.png")
        size = Image.open(path).size
        ox, oy = sequence_offset(image)
        detected, (pw, ph) = detect_pads(path)
        pads, found = fit_grid(detected, cols, rows)
        offsets, cells = [], set()
        for px, py in pads:
            # world pixels from the building centre, then world units
            wx = (px - size[0] / 2 + ox) / DENSITY
            wy = (py - size[1] / 2 + oy) / DENSITY
            vx, vy = round(wx * WDIST / CELL), round(wy * WDIST / CELL)
            cell = (int(np.floor((vx + fw * WDIST / 2) / WDIST)), int(np.floor((vy + fh * WDIST / 2) / WDIST)))
            if not (0 <= cell[0] < fw and 0 <= cell[1] < fh):
                print(f"  {image}: slot at {vx},{vy} is outside the {fw}x{fh} footprint (cell {cell})")
                ok = False
            if cell in cells:
                print(f"  {image}: two slots share cell {cell}")
                ok = False
            cells.add(cell)
            offsets.append((vx, vy))
        print(f"{image}: {len(pads)} slots ({found} pads detected, the rest from the grid), "
              f"pad {pw / DENSITY:.0f} x {ph / DENSITY:.0f} px in game")
        for actor in actors:
            lines += [f"{actor}:", "\tReservable:",
                      "\t\tSlotOffsets: " + ", ".join(f"{x},{y},0" for x, y in offsets),
                      "\t\tSlotFacings: " + ", ".join(str(FACING) for _ in offsets), ""]
        if args.preview:
            os.makedirs(PREVIEW, exist_ok=True)
            im = Image.open(path).convert("RGBA")
            d = ImageDraw.Draw(im)
            for i, (px, py) in enumerate(pads):
                d.rectangle((px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2), outline=(255, 0, 0, 255), width=2)
                d.text((px - 4, py - 6), str(i + 1), fill=(255, 255, 0, 255))
            im.save(os.path.join(PREVIEW, f"{image}-slots.png"))

    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print("wrote", os.path.relpath(OUT, ROOT))
    if not ok:
        raise SystemExit("slot check failed (see above)")


if __name__ == "__main__":
    main()
