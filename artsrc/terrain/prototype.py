#!/usr/bin/env python3
"""
Offline prototype of the HD terrain shader (mods/rapx/shaders/terrainhd.frag).

Composes a small scene from real RA temperate tiles, then re-skins it the same way the
GPU shader does, so the look can be tuned quickly without launching the game.

  python3 artsrc/terrain/prototype.py <dir with temperat.pal + tile pngs> out.png
"""
import glob
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom

ART = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SRC = sys.argv[1]
OUT = sys.argv[2]
S = 4          # output pixels per world pixel (Retina at max zoom)
CELL = 24

# Must match the shader constants
PARAMS = dict(
    blur=1.1,              # texels; neighbourhood used for material classification
    grass_repeat=4.0,      # cells per texture repeat
    dirt_repeat=5.0,
    rock_repeat=4.0,
    sharpness=6.0,         # height-blend sharpening exponent
    shade_strength=0.7,    # how much the original large-scale shading is kept
)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def load_palette():
    pal = open(os.path.join(SRC, "temperat.pal"), "rb").read()
    p = np.array([[pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]] for i in range(256)], dtype=np.float32) * 4 / 255
    return p


def frames(name):
    return [np.array(Image.open(f)) for f in sorted(glob.glob(os.path.join(SRC, name + "-*.png")))]


def compose():
    """Index map of a 12x8 cell test scene: grass with a dirt path, rocks, cliffs and a shore."""
    w, h = 12, 8
    rng = np.random.default_rng(3)
    idx = np.zeros((h * CELL, w * CELL), dtype=np.uint8)
    clear = frames("clear1")
    for y in range(h):
        for x in range(w):
            idx[y * CELL:(y + 1) * CELL, x * CELL:(x + 1) * CELL] = clear[rng.integers(len(clear))]

    def place(name, cx, cy, tw, th):
        fr = frames(name)
        for i, f in enumerate(fr):
            tx, ty = cx + i % tw, cy + i // tw
            if f.max() == 0 or ty >= h or tx >= w:
                continue
            region = idx[ty * CELL:(ty + 1) * CELL, tx * CELL:(tx + 1) * CELL]
            mask = f != 0
            region[mask] = f[mask]

    place("sh01", 0, 3, 4, 5)
    place("d01", 4, 1, 2, 2)
    place("d02", 6, 2, 2, 2)
    place("d01", 8, 3, 2, 2)
    place("s01", 9, 0, 2, 2)
    place("s01", 5, 5, 2, 2)
    return idx


def load_tex(path, size=1024):
    im = Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32) / 255
    return a


def sample(tex, u, v):
    """Bilinear, wrapping texture lookup at normalized coords."""
    n = tex.shape[0]
    x = (u % 1.0) * n - 0.5
    y = (v % 1.0) * n - 0.5
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    x0 %= n
    y0 %= n
    x1 = (x0 + 1) % n
    y1 = (y0 + 1) % n
    return ((tex[y0, x0] * (1 - fx) + tex[y0, x1] * fx) * (1 - fy) +
            (tex[y1, x0] * (1 - fx) + tex[y1, x1] * fx) * fy)


def lum(c):
    return c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114


def main():
    pal = load_palette()
    idx = compose()
    orig = pal[idx]                                     # (H, W, 3) at world resolution
    H, W = idx.shape

    # Classification works on a blurred neighbourhood so speckles inside grass average out
    smooth = np.stack([gaussian_filter(orig[..., c], PARAMS["blur"]) for c in range(3)], -1)
    up = lambda a: zoom(a, (S, S) + (1,) * (a.ndim - 2), order=1)
    C = up(smooth)
    v = C.max(-1)
    green = (C[..., 1] - (C[..., 0] + C[..., 2]) / 2) / (v + 0.02)
    blue = (C[..., 2] - (C[..., 0] + C[..., 1]) / 2) / (v + 0.02)

    water = smoothstep(0.10, 0.22, blue) * smoothstep(0.30, 0.42, v)
    rock = smoothstep(0.33, 0.45, v) * (1 - water)
    grass = smoothstep(0.03, 0.14, green) * (1 - water) * (1 - rock)
    dirt = np.clip(1 - water - rock - grass, 0, 1)

    # World-space detail textures
    yy, xx = np.mgrid[0:H * S, 0:W * S].astype(np.float32) / S  # world pixels
    tg = load_tex(glob.glob(os.path.join(ART, "textures", "Grass004", "*_Color.jpg"))[0])
    td = load_tex(os.path.join(ART, "textures", "dirt_aerial_02", "dirt_aerial_02_diff_2k.jpg"))
    tr = load_tex(os.path.join(ART, "textures", "aerial_rocks_02", "aerial_rocks_02_diff_2k.jpg"))
    cg = sample(tg, xx / (CELL * PARAMS["grass_repeat"]), yy / (CELL * PARAMS["grass_repeat"]))
    # second, rotated + scaled grass sample breaks up visible tiling
    cg2 = sample(tg, (xx * 0.6 + yy * 0.8) / (CELL * PARAMS["grass_repeat"] * 2.7), (-xx * 0.8 + yy * 0.6) / (CELL * PARAMS["grass_repeat"] * 2.7))
    macro = smoothstep(0.2, 0.8, lum(sample(td, xx / (CELL * 23), yy / (CELL * 19))) * 2.2)[..., None]
    cg = cg * (0.8 + 0.2 * macro) * 0.5 + cg2 * 0.5
    cd = sample(td, xx / (CELL * PARAMS["dirt_repeat"]), yy / (CELL * PARAMS["dirt_repeat"]))
    cr = sample(tr, xx / (CELL * PARAMS["rock_repeat"]), yy / (CELL * PARAMS["rock_repeat"]))

    # Natural colour grade for the grass: darker, less saturated, slightly warm
    g_l = lum(cg)[..., None]
    cg = (g_l + (cg - g_l) * 0.72) * np.array([0.80, 0.74, 0.62])

    # Rocks and dirt keep the original sprite's form (lit faces / shadows) and take only
    # surface detail from the photo texture ("detail overlay")
    sharp = up(np.stack([gaussian_filter(orig[..., c], 0.55) for c in range(3)], -1))
    def overlay(tex, base, gain):
        return base * (lum(tex) / (lum(tex).mean() + 1e-4))[..., None] * gain
    cr = overlay(cr, sharp, 1.15) * 0.75 + cr * np.array([0.55, 0.52, 0.48]) * 0.25
    cd = overlay(cd, C, 1.2) * 0.45 + cd * 0.55 * 0.8

    # Height blend: each material's own luminance decides who wins at the boundaries
    k = PARAMS["sharpness"]
    wg = (grass * (lum(cg) + 0.6)) ** k
    wd = (dirt * (lum(cd) + 0.6)) ** k
    wr = (rock * (lum(cr) + 0.6)) ** k
    total = wg + wd + wr + 1e-6
    wg, wd, wr = (w / total for w in (wg, wd, wr))

    # Grass keeps the original large-scale light/shadow (darker patches, cliff shadows)
    ratio = np.clip(lum(C) / 0.205, 0.45, 1.35)
    cg = cg * (1 + PARAMS["shade_strength"] * (ratio - 1))[..., None]
    hd = cg * wg[..., None] + cd * wd[..., None] + cr * wr[..., None]

    # Water keeps its original (animated in game) colour, smoothed
    wsm = up(np.stack([gaussian_filter(orig[..., c], 0.9) for c in range(3)], -1))
    out = hd * (1 - water[..., None]) + wsm * water[..., None]

    before = np.repeat(np.repeat(orig, S, 0), S, 1)
    img = np.concatenate([before, np.ones((H * S, 8, 3)), np.clip(out, 0, 1)], 1)
    Image.fromarray((img * 255).astype(np.uint8)).save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
