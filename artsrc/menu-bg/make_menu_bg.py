#!/usr/bin/env python3
"""Extend mods/rapx/uibits/menu-background.png (ultra-wide) to a 16:10 main-menu background.

The original art is kept pixel for pixel in the middle. Above it goes stormy sky built from the
empty clouds on the right of the art; below it a mirrored, blurred and darkened reflection of the
ground, which reads as glowing lava. Writes mods/rapx/uibits/menu-background-full.png and prints
the vertical offset of the original inside it (make_menu_fx.py uses the same offset).

Re-run after replacing menu-background.png, then re-run make_menu_fx.py.
"""
import os

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UIBITS = os.path.join(ROOT, "mods", "rapx", "uibits")

ASPECT = 1.6                        # 16:10, the common Mac screen shape
CLOUDS = (1950, 0, 2600, 560)       # empty sky in the art, free of buildings and lights
REFLECTION_BLUR = (5, 14, 30)       # blur levels from the seam outward
REFLECTION_DARKEN = 0.6
SKY_DARKEN = 0.45


def arr(im):
    return np.asarray(im).astype(np.float32)


def offset_for(size):
    w, h = size
    return (round(w / ASPECT) - h) // 2


def sky(src, w, pad):
    # Clouds squashed vertically (more distant), mirror-tiled across the width. A second tiling,
    # shifted half a tile and flipped upside down, is blended in so the repeat is hard to spot.
    cl = src.crop(CLOUDS).resize((CLOUDS[2] - CLOUDS[0], pad))

    def tiled(tile, start):
        row = Image.new("RGB", (w, pad))
        x, flip = start, False
        while x < w:
            row.paste(tile.transpose(Image.FLIP_LEFT_RIGHT) if flip else tile, (x, 0))
            x += tile.width
            flip = not flip
        return arr(row)

    a = tiled(cl, 0)
    b = tiled(cl.transpose(Image.FLIP_TOP_BOTTOM), -cl.width // 2)
    blend = 0.5 + 0.5 * np.sin(np.arange(w) / w * np.pi * 5)[None, :, None]
    clouds = a * blend + b * (1 - blend)
    clouds = arr(Image.fromarray(np.clip(clouds, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)))

    # Near the seam, fade into the art's own top edge stretched upward so the colours carry on
    edge = arr(src.crop((0, 0, w, 12)).resize((w, pad)).filter(ImageFilter.GaussianBlur(25)))
    y = np.linspace(0, 1, pad)[:, None, None]
    mix = np.clip((y - 0.45) / 0.55, 0, 1) ** 1.5
    out = (clouds * (1 - mix) + edge * mix) * (1 - SKY_DARKEN + SKY_DARKEN * y)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def reflection(src, w, h, pad):
    strip = src.crop((0, h - pad, w, h)).transpose(Image.FLIP_TOP_BOTTOM)
    levels = [arr(strip)] + [arr(strip.filter(ImageFilter.GaussianBlur(r))) for r in REFLECTION_BLUR]
    out = np.zeros_like(levels[0])
    steps = len(levels) - 1
    for y in range(pad):
        d = y / (pad - 1)
        t = min(d * steps, steps - 0.001)
        i = int(t)
        f = t - i
        out[y] = (levels[i][y] * (1 - f) + levels[i + 1][y] * f) * (1 - REFLECTION_DARKEN * d ** 1.2)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def main():
    src = Image.open(os.path.join(UIBITS, "menu-background.png")).convert("RGB")
    w, h = src.size
    pad = offset_for(src.size)
    full_h = h + 2 * pad

    out = Image.new("RGB", (w, full_h))
    out.paste(sky(src, w, pad), (0, 0))
    out.paste(src, (0, pad))
    out.paste(reflection(src, w, h, pad), (0, pad + h))

    # Soften the sky seam (the reflection seam is continuous by construction)
    a = arr(out)
    soft = arr(out.filter(ImageFilter.GaussianBlur(6)))
    weight = np.exp(-((np.arange(full_h) - pad) / 18.0) ** 2)[:, None, None]
    out = Image.fromarray(np.clip(a * (1 - weight) + soft * weight, 0, 255).astype(np.uint8))

    out.save(os.path.join(UIBITS, "menu-background-full.png"))
    print("wrote menu-background-full.png (%dx%d), art offset %d" % (w, full_h, pad))


if __name__ == "__main__":
    main()
