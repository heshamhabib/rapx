#!/usr/bin/env python3
"""
Big copies of the sidebar cameos for the Extras catalogue (PxCatalogueWidget's stage).

Renders every image's cameo again with generate.py's own functions at 4x the tile (960x640), so the
catalogue shows exactly the same picture as the sidebar, only sharper. Writes JPEGs (the art is opaque,
and PNGs this size would add ~150 MB) to mods/rapx/bits/hd/catalogue/<image>.jpg.
Touches nothing generate.py writes. Images whose cameo is an upscaled classic one are skipped
(the catalogue falls back to the small cameo).

Run: python3 artsrc/px-cameos/make_catalogue_art.py [image ...]
"""

import os
import sys

import generate as g

SCALE = 4
OUT = os.path.join(g.MOD, "bits", "hd", "catalogue")


def sidebar_images():
    """Every image with a sidebar cameo: the top-level keys of the generated hd-icons.yaml that have a px-icon."""
    images, image = [], None
    for line in open(os.path.join(g.MOD, "sequences", "hd-icons.yaml")):
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            image = line.strip().rstrip(":")
        elif line.strip() == "px-icon:" and image:
            images.append(image)
    return sorted(set(images))


def main():
    only = set(a.lower() for a in sys.argv[1:])
    os.makedirs(OUT, exist_ok=True)
    images = sidebar_images()

    # generate.py draws at the module-level tile size; render at SCALE x that
    g.W, g.H = 240 * SCALE, 160 * SCALE
    written = skipped = 0
    for image in images:
        if only and image not in only:
            continue
        if g.painted_source(image):
            img = g.painted_cameo(image)
        elif g.source_art(image) is not None:
            img = g.hd_cameo(image)
        else:
            skipped += 1
            continue
        img.convert("RGB").save(os.path.join(OUT, image + ".jpg"), quality=88, optimize=True)
        written += 1

    print(f"wrote {written} catalogue images to {os.path.relpath(OUT, g.ROOT)}, skipped {skipped} classic-only")


if __name__ == "__main__":
    main()
