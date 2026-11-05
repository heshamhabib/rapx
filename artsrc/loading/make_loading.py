#!/usr/bin/env python3
"""Convert the loading-screen art in assets/loading into game-ready PNGs.

Every image in assets/loading (jpeg/png) becomes mods/rapx/uibits/loading/loading-NN.png,
scaled to 1920px wide. FullscreenImageLoadScreen picks one at random for each map load
(starting a skirmish, leaving one). Rerun after adding or removing art, then update the
LoadingImages list in mods/rapx/mod.yaml (the script prints it).
"""
import glob
import os

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "assets", "loading")
DST = os.path.join(ROOT, "mods", "rapx", "uibits", "loading")
WIDTH = 1920

os.makedirs(DST, exist_ok=True)
for old in glob.glob(os.path.join(DST, "loading-*.png")):
    os.remove(old)

sources = sorted(f for f in glob.glob(os.path.join(SRC, "*")) if f.lower().endswith((".jpg", ".jpeg", ".png")))
names = []
for i, path in enumerate(sources, 1):
    img = Image.open(path).convert("RGB")
    h = round(img.height * WIDTH / img.width)
    img = img.resize((WIDTH, h), Image.LANCZOS)
    name = "loading-%02d.png" % i
    img.save(os.path.join(DST, name), optimize=True)
    names.append("ra|uibits/loading/" + name)
    print("%s <- %s" % (name, os.path.basename(path)))

print("\nLoadingImages: " + ", ".join(names))
