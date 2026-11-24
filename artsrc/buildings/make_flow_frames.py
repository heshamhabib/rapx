#!/usr/bin/env python3
"""
Flow start/end frames for filmed building damage and collapse (artsrc/buildings/flow-building-prompts.md).

  python3 artsrc/buildings/make_flow_frames.py powr [weap ...]

Splits each building's two-up source render (artsrc/buildings/src/<id>.png: intact left, damaged right, on magenta)
into two 1920x1080 frames with the building at the same size and place in both, small enough to leave room around it
for debris and dust: <id>-intact.png and <id>-damaged.png in ~/Movies/explosion/buildings/. Flow's Frames mode uses
them as first and last frames, so the filmed states stay the same building.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import binary_opening, label

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT = os.path.expanduser("~/Movies/explosion/buildings")
W, H = 1920, 1080
HEIGHT = 0.52        # building height as a share of the frame
BASE = 0.74          # where its lowest point sits (share of the frame height from the top)
MAGENTA = (255, 0, 255)


def solid(img):
    """Pixels that are not the magenta background."""
    a = np.asarray(img).astype(int)
    return ~((a[..., 0] > 180) & (a[..., 2] > 180) & (a[..., 1] < 90))


def building_mask(img):
    """The building and the pieces next to it (its smoke), without slivers of the other render or stray specks."""
    m = binary_opening(solid(img), structure=np.ones((5, 5)))
    lab, n = label(m)
    if n == 0:
        return m
    sizes = np.bincount(lab.ravel())[1:]
    main = int(np.argmax(sizes)) + 1
    ys, xs = np.nonzero(lab == main)
    pad = img.width * 0.03
    x0, x1, y0, y1 = xs.min() - pad, xs.max() + pad, ys.min() - pad, ys.max() + pad
    keep = [main]
    for i in range(1, n + 1):
        if i == main or sizes[i - 1] < 40:
            continue
        ys, xs = np.nonzero(lab == i)
        if xs.min() >= x0 and xs.max() <= x1 and ys.min() >= y0 and ys.max() <= y1:
            keep.append(i)
    return np.isin(lab, keep)


def clean(img):
    """The render with its background set to exactly the frame's magenta."""
    a = np.asarray(img).copy()
    a[~(solid(img) & building_mask(img))] = MAGENTA
    return Image.fromarray(a)


def halves(img):
    """Left and right render, split at the widest background gap near the middle."""
    cols = solid(img).mean(axis=0)
    w = img.width
    mid = np.arange(int(w * 0.35), int(w * 0.65))
    gap = mid[np.argmin(cols[mid])]
    return img.crop((0, 0, gap, img.height)), img.crop((gap, 0, w, img.height))


def frames(bid):
    img = Image.open(os.path.join(SRC, f"{bid}.png")).convert("RGB")
    left, right = halves(img)
    # Equal-width magenta canvases: the shared box below may reach past the narrower half (a crop past the edge is black)
    width = max(left.width, right.width)
    padded = []
    for half in (left, right):
        canvas = Image.new("RGB", (width, half.height), MAGENTA)
        canvas.paste(half, (0, 0))
        padded.append(canvas)
    left, right = padded
    boxes = []
    for half in (left, right):
        ys, xs = np.nonzero(building_mask(half))
        boxes.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    # One box for both halves, so the building keeps its size and place between the frames
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    scale = H * HEIGHT / (y1 - y0)
    os.makedirs(OUT, exist_ok=True)
    for name, half in (("intact", left), ("damaged", right)):
        part = clean(half).crop((x0, y0, x1, y1))
        part = part.resize((round(part.width * scale), round(part.height * scale)), Image.LANCZOS)
        canvas = Image.new("RGB", (W, H), MAGENTA)
        canvas.paste(part, ((W - part.width) // 2, round(H * BASE) - part.height))
        path = os.path.join(OUT, f"{bid}-{name}.png")
        canvas.save(path)
        print(f"  {path}")


def main():
    for bid in sys.argv[1:] or ["powr"]:
        frames(bid)


if __name__ == "__main__":
    main()
