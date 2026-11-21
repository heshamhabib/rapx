#!/usr/bin/env python3
"""
Makes the painted ChatGPT textures (assets/maps/monument/tex-*.png, monument-prompts.md) tile without visible seams.

  python3 artsrc/maps/monument/make_seamless.py

Output: assets/maps/monument/seamless/tex-*.png (build_backdrop.py prefers these). Ground and roof textures are made
seamless in both directions; facades too, since the towers repeat them upwards.

Method: the image is blended with a copy of itself shifted by half its size. The shifted copy has its seams in the
middle, where the original is kept; at the borders the shifted copy (continuous there) takes over. A noisy mask
hides the blend zone.
"""
import glob
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "assets", "maps", "monument"))
OUT = os.path.join(SRC, "seamless")
SIZE = 1024


def weight(n, rng):
    """1 in the middle, 0 at the ends, with a ragged transition."""
    t = np.abs(np.linspace(-1, 1, n))
    return np.clip((0.8 - t) / 0.35, 0, 1)


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(7)
    for path in sorted(glob.glob(os.path.join(SRC, "tex-*.png"))):
        name = os.path.basename(path)
        img = Image.open(path).convert("RGB")
        side = min(img.size)
        img = img.crop(((img.width - side) // 2, (img.height - side) // 2,
                        (img.width + side) // 2, (img.height + side) // 2)).resize((SIZE, SIZE), Image.LANCZOS)
        a = np.asarray(img).astype(np.float32)
        both = True                       # Ironward facades also repeat upwards (towers)
        shifted = np.roll(a, SIZE // 2, axis=1)
        wx = weight(SIZE, rng)[None, :]
        if both:
            shifted = np.roll(shifted, SIZE // 2, axis=0)
            w = np.minimum(wx, weight(SIZE, rng)[:, None])
        else:
            w = np.repeat(wx, SIZE, axis=0)
        # Ragged edge for the blend so it does not read as a soft square
        noise = np.asarray(Image.fromarray((rng.random((SIZE // 16, SIZE // 16)) * 255).astype(np.uint8))
                           .resize((SIZE, SIZE), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))) / 255.0
        w = np.clip((w - 0.5) * 2.5 + (noise - 0.5) * 0.8 + 0.5, 0, 1)[..., None]
        out = a * w + shifted * (1 - w)
        Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(os.path.join(OUT, name))
        print("seamless", name)


if __name__ == "__main__":
    main()
