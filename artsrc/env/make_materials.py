#!/usr/bin/env python3
"""
Makes the AI ground materials (assets/env/materials/<terrain>-<material>.png) game-ready for the HD
terrain pass (TerrainDetailTextures in rules/palettes.yaml):

  - flattens large-scale lighting (vignettes / gradients would show as a grid when the texture repeats),
  - makes the texture seamless: the image is blended with a half-offset copy of itself near its edges,
    so every edge pixel comes from the middle of the source, which has no seam,
  - resizes to 1024x1024 (OpenRA textures must be a power of two),

and writes mods/rapx/bits/terrain/<terrain>-<material>.png. Incremental; --force redoes all.
--preview writes artsrc/env/preview/materials.png (each texture tiled 2x2, seams in the middle).

  python3 artsrc/env/make_materials.py [--force] [--preview]
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "assets", "env", "materials")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "terrain")
PREVIEW = os.path.join(HERE, "preview")
SIZE = 1024
# Materials whose detail is too harsh at RTS zoom: (fine blur px, contrast kept 0-1). The snow road (packed snow,
# slush and gravel) only needs a little, so road templates don't stand out as patches against the snow.
CALM = {"snow-road.png": (0.6, 0.75)}


def flatten(a, sigma):
    """Divides out lighting variation larger than `sigma` px (keeps the mean colour)."""
    low = np.dstack([gaussian_filter(a[..., c], sigma, mode="wrap") for c in range(3)])
    return np.clip(a * (a.mean((0, 1)) / np.maximum(low, 1e-3)), 0, 1)


def seamless(a):
    h, w, _ = a.shape
    shifted = np.roll(np.roll(a, h // 2, 0), w // 2, 1)
    # Weight of the shifted copy: 1 at the edges, 0 in the middle; smooth so the blend has no visible band
    y = np.abs(np.linspace(-1, 1, h))[:, None]
    x = np.abs(np.linspace(-1, 1, w))[None, :]
    edge = np.clip((np.maximum(x, y) - 0.55) / 0.40, 0, 1)
    wgt = (edge * edge * (3 - 2 * edge))[..., None]
    out = a * (1 - wgt) + shifted * wgt
    # Blending two images averages away contrast; restore the local contrast in the blended band
    mean = np.dstack([gaussian_filter(out[..., c], 6, mode="wrap") for c in range(3)])
    boost = 1 + 0.45 * (2 * wgt * (1 - wgt)) * 2
    return np.clip(mean + (out - mean) * boost, 0, 1)


def process(src, dst):
    a = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255
    a = flatten(a, a.shape[0] / 6)
    a = seamless(a)
    if os.path.basename(src) in CALM:
        blur, keep = CALM[os.path.basename(src)]
        mean = np.dstack([gaussian_filter(a[..., c], 24, mode="wrap") for c in range(3)])
        fine = np.dstack([gaussian_filter(a[..., c], blur, mode="wrap") for c in range(3)])
        a = np.clip(mean + (fine - mean) * keep, 0, 1)
    im = Image.fromarray((a * 255 + 0.5).astype(np.uint8)).resize((SIZE, SIZE), Image.LANCZOS)
    im.save(dst, optimize=True)


def seam_ratio(path):
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    inner = np.abs(np.diff(a, axis=1)).mean()
    return (np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0] - a[-1]).mean()) / 2 / inner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    outs = []
    for src in sorted(glob.glob(os.path.join(SRC, "*.png"))):
        dst = os.path.join(OUT, os.path.basename(src))
        if args.force or not os.path.exists(dst) or os.path.basename(src) in CALM or os.path.getmtime(src) > os.path.getmtime(dst):
            process(src, dst)
            print(f"  {os.path.basename(src)}: seam {seam_ratio(src):.2f} -> {seam_ratio(dst):.2f}")
        outs.append(dst)
    print(f"{len(outs)} materials in {os.path.relpath(OUT, ROOT)}")

    if args.preview:
        os.makedirs(PREVIEW, exist_ok=True)
        t = 256
        cols = 6
        sheet = Image.new("RGB", (cols * 2 * t, -(-len(outs) // cols) * 2 * t))
        draw = ImageDraw.Draw(sheet)
        for i, p in enumerate(outs):
            im = Image.open(p).resize((t, t), Image.LANCZOS)
            x, y = (i % cols) * 2 * t, (i // cols) * 2 * t
            for dx in (0, t):
                for dy in (0, t):
                    sheet.paste(im, (x + dx, y + dy))
            draw.text((x + 6, y + 6), os.path.basename(p), fill=(255, 255, 0))
        sheet.save(os.path.join(PREVIEW, "materials.png"))
        print("wrote artsrc/env/preview/materials.png")


if __name__ == "__main__":
    main()
