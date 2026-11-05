#!/usr/bin/env python3
"""
Turns the AI terrain-tile renders (bridges, fords, debris) into HD tile art the game draws over the classic tiles.

Input:  assets/env/tiles/<tileset dir>/<template image>.png   (one render per tile template, see env-sheets.md)
        artsrc/env-inventory/classic/<TILESET>/<template image>.png  (classic template at 4x: which cells exist)
Output: mods/rapx/bits/hd/tiles/<tileset dir>/<template image>.png - the render resized to the template's cell grid
        at 3x density (72 px per cell); cells the template doesn't have are cut away and the template's outer edges
        fade out over a few pixels so it blends into the HD terrain around it. Debris tiles keep only their features
        (rocks, rubble, wrecks): their plain ground is made transparent so the shader's ground shows through.

The PxHDTiles world trait (OpenRA.Mods.RAPX/Traits/World/PxHDTiles.cs) cuts these into cells and draws them over
every map cell that uses the template. Incremental; --force redoes all.

  python3 artsrc/env/make_tiles.py [--force]       (make_env.py runs it too)
"""
import argparse
import csv
import glob
import os

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, distance_transform_edt, gaussian_filter, label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ASSETS = os.path.join(ROOT, "assets", "env", "tiles")
CLASSIC = os.path.join(ROOT, "artsrc", "env-inventory", "classic")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "tiles")
CELL = 72            # HD pixels per map cell (24 world pixels at density 3)
CLASSIC_CELL = 96    # classic export: 24 pixels at 4x
FEATHER = 5          # HD pixels over which the template's outer edge fades out
DEBRIS_FEATHER = 14  # debris sits in open ground: a wider fade hides its edge
INVENTORY = os.path.join(ROOT, "docs", "environment-assets.csv")


def debris_templates():
    """{(TILESET, image stem)} of the Debris tiles (rocks, rubble on open ground)."""
    out = set()
    for r in csv.DictReader(open(INVENTORY)):
        if r["kind"] == "tile" and r["category"] == "Debris":
            out.add((r["tileset"], r["source_files"].rsplit(".", 1)[0]))
    return out


def feature_alpha(img):
    """Debris tiles: opaque only on the features (rocks, rubble, wrecks, plants and their shadows); the plain ground
    around them becomes transparent so the HD terrain shader's own ground shows through without a colour edge.
    Features = whatever contrasts with its local ground, in blobs big enough not to be gravel; the threshold adapts to
    how busy the tile is."""
    a = np.asarray(img, np.float32) / 255
    s = CELL / 72
    ground = np.median(a.reshape(-1, 3), 0)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    local = gaussian_filter(lum, 12 * s)
    d = gaussian_filter(np.abs(lum - local) + 0.6 * np.sqrt(((a - ground) ** 2).sum(2)), 2.5 * s)
    core = d > max(0.14, np.percentile(d, 72))
    lab, _ = label(core)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    keep = np.isin(lab, np.nonzero(sizes >= 150 * s * s * (img.width * img.height) / (216 * 216))[0])
    keep = binary_dilation(keep, iterations=max(1, round(4 * s)))
    return np.clip(gaussian_filter(keep.astype(np.float32), 2.5 * s) * 1.4, 0, 1)


TILESETS = {"temperat": "TEMPERAT", "snow": "SNOW", "desert": "DESERT", "interior": "INTERIOR"}


def remastered_bridges():
    """{(tileset dir, image stem)} of the bridge templates make_terrain_tiles.py builds (it cuts the bridge out of
    these renders itself), so this script must leave them alone."""
    import make_terrain_tiles as mtt
    out = set()
    for ts, info in mtt.TILESETS.items():
        out |= {(ts, mtt.stem(t)) for t in mtt.parse_templates(os.path.join(mtt.MOD, "tilesets", info["yaml"]), ts)
                if t.get("bridge_cells") or t.get("ramp")}
    return out


def process_tiles(force=False, log=print):
    done = 0
    debris = debris_templates()
    bridges = remastered_bridges()
    for path in sorted(glob.glob(os.path.join(ASSETS, "*", "*.png"))):
        tsdir = os.path.basename(os.path.dirname(path))
        stem = os.path.splitext(os.path.basename(path))[0]
        if (tsdir, stem) in bridges:
            continue
        out = os.path.join(OUT, tsdir, stem + ".png")
        if not force and os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(path):
            continue
        classic = os.path.join(CLASSIC, TILESETS.get(tsdir, tsdir.upper()), stem + ".png")
        if not os.path.exists(classic):
            log(f"  {os.path.relpath(path, ROOT)}: no classic template {os.path.relpath(classic, ROOT)}, skipped")
            continue

        ref = np.asarray(Image.open(classic).convert("RGBA"))
        cw, ch = ref.shape[1] // CLASSIC_CELL, ref.shape[0] // CLASSIC_CELL
        present = np.array([[ref[y * CLASSIC_CELL:(y + 1) * CLASSIC_CELL, x * CLASSIC_CELL:(x + 1) * CLASSIC_CELL, 3].any()
                             for x in range(cw)] for y in range(ch)])

        img = Image.open(path).convert("RGB").resize((cw * CELL, ch * CELL), Image.LANCZOS)
        is_debris = (TILESETS.get(tsdir, tsdir.upper()), stem) in debris
        mask = np.kron(present, np.ones((CELL, CELL), bool))
        # Fade towards missing cells and the template border (pad so the border counts as outside)
        padded = np.pad(mask, 1, constant_values=False)
        alpha = np.clip(distance_transform_edt(padded)[1:-1, 1:-1] / (DEBRIS_FEATHER if is_debris else FEATHER), 0, 1)
        if is_debris:
            alpha = alpha * feature_alpha(img)
        rgba = np.dstack([np.asarray(img), (alpha * 255).astype(np.uint8)])

        os.makedirs(os.path.dirname(out), exist_ok=True)
        Image.fromarray(rgba).save(out, optimize=True)
        done += 1
    log(f"  AI tiles: {done} updated")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    process_tiles(ap.parse_args().force)
