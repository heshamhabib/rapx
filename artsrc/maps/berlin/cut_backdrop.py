#!/usr/bin/env python3
"""
Cuts the rendered Berlin backdrop (build_backdrop.py) into the chunks PxMapBackdrop loads, and makes the lobby preview.

  python3 artsrc/maps/berlin/cut_backdrop.py [--ppc 64] [--chunk 16] [--src build/backdrop-painted.png]

Output: mods/rapx/maps/berlin-1946/backdrop-<column>-<row>.png (chunk x chunk cells each) and map.png.
"""
import argparse
import glob
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "mods", "rapx", "maps", "berlin-1946"))

ap = argparse.ArgumentParser()
ap.add_argument("--ppc", type=int, default=64)
ap.add_argument("--chunk", type=int, default=16)
ap.add_argument("--src", default="build/backdrop.png", help="picture to cut, relative to this folder")
a = ap.parse_args()

Image.MAX_IMAGE_PIXELS = None
img = Image.open(os.path.join(HERE, a.src)).convert("RGB")
for old in glob.glob(os.path.join(MAP_DIR, "backdrop-*.png")):
    os.remove(old)
step = a.ppc * a.chunk
total = 0
for row in range((img.height + step - 1) // step):
    for col in range((img.width + step - 1) // step):
        box = (col * step, row * step, min(img.width, (col + 1) * step), min(img.height, (row + 1) * step))
        path = os.path.join(MAP_DIR, f"backdrop-{col}-{row}.png")
        img.crop(box).convert("RGBA").save(path, optimize=True)
        total += os.path.getsize(path)
preview = img.resize((img.width // 18, img.height // 18), Image.LANCZOS)
preview.save(os.path.join(MAP_DIR, "map.png"))
print(f"{img.width}x{img.height} -> chunks of {step}px, {total / 1e6:.1f} MB")
