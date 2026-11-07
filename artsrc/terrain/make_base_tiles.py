#!/usr/bin/env python3
"""
Repaints every terrain template of the TEMPERAT, SNOW and DESERT tilesets as our own base tiles (IDEA-31), so the
game no longer needs the original tile files.

The base tiles are what the HD terrain shader (shaders/terrain_detail.frag) reads: it classifies each pixel as
grass / dirt / rock / water from its colour and paints the HD photo textures over it, lit by the base tile's light
and shade. So only the *layout* of each template matters, not its pixel art. For every template this script:

1. labels each pixel of the original tile with its class, using the same rules as the shader (temperate: the
   green / bright / blue rules, snow and desert: the nearest reference colour from rules/palettes.yaml), plus a
   coarse light band (dark / mid / light) within the class;
2. keeps water as one flat band; smooths the label map (3x3 majority, twice) so the original pixel detail is gone and only the shapes remain;
3. paints each label with one flat colour - the average colour of that label over the whole tileset, so the shader
   classifies it exactly as before - plus our own fine noise.

The originals are read from the installed game once (OpenRA.Utility --extract / --png) into a cache in
assets/terrain-classic/ (git-ignored). Writes mods/rapx/bits/terrain-base/<tileset>/<image>.png with one 24x24
frame per tile index (PNG `Frame[i]`), and points the tileset's `Images:` at them with --apply.

  python3 artsrc/terrain/make_base_tiles.py [TILESET ...] [--apply]
"""
import glob
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter, uniform_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MOD = os.path.join(ROOT, "mods", "rapx")
CACHE = os.path.join(ROOT, "assets", "terrain-classic")
OUT = os.path.join(MOD, "bits", "terrain-base")
TILESETS = {"TEMPERAT": ("temperat.yaml", "temperat.pal"), "SNOW": ("snow.yaml", "snow.pal"),
            "DESERT": ("desert.yaml", "desert.pal")}
CLASSES = ["grass", "dirt", "rock", "water", "void"]
BANDS = 3


def utility(*args, cwd):
    env = dict(os.environ, MOD_SEARCH_PATHS=f"{ROOT}/mods,{ROOT}/engine/mods", ENGINE_DIR=f"{ROOT}/engine",
               PATH=os.path.expanduser("~/.dotnet") + ":" + os.environ["PATH"],
               DOTNET_ROOT=os.path.expanduser("~/.dotnet"))
    return subprocess.run(["dotnet", f"{ROOT}/engine/bin/OpenRA.Utility.dll", "rapx", *args], cwd=cwd, env=env,
                          capture_output=True, text=True)


def templates(tileset):
    """[(image file, [tile indices used])] in file order."""
    # The classic file names: from the tileset as committed before the switch (2026-11-07) when --apply already
    # pointed it at our PNGs
    path = os.path.join(MOD, "tilesets", TILESETS[tileset][0])
    text = open(path).read()
    if "terrain-base/" in text:
        text = subprocess.run(["git", "show", f"5549ce9:mods/rapx/tilesets/{TILESETS[tileset][0]}"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout
    out = {}
    for block in re.split(r"\n\tTemplate@", text)[1:]:
        img = re.search(r"\n\t\tImages: (\S+)", block).group(1)
        tiles = [int(t) for t in re.findall(r"\n\t\t\t(\d+):", block)]
        out.setdefault(img, set()).update(tiles)
    return out


def export(tileset, images):
    """Original frames as RGBA arrays: {image: [frame arrays]}; cached in assets/terrain-classic/<tileset>/."""
    d = os.path.join(CACHE, tileset)
    os.makedirs(d, exist_ok=True)
    pal = TILESETS[tileset][1]
    if not os.path.exists(os.path.join(d, pal)):
        utility("--extract", pal, cwd=d)
    todo = [i for i in images if not glob.glob(os.path.join(d, os.path.splitext(i)[0] + "-*.png"))
            and not os.path.basename(i).startswith("ra|")]
    for i in range(0, len(todo), 40):
        utility("--extract", *todo[i:i + 40], cwd=d)
    for img in todo:
        utility("--png", img, pal, cwd=d)
        if os.path.exists(os.path.join(d, img)):
            os.remove(os.path.join(d, img))
    frames = {}
    for img in images:
        stem = os.path.splitext(img)[0]
        files = sorted(glob.glob(os.path.join(d, stem + "-*.png")), key=lambda p: int(p.rsplit("-", 1)[1][:-4]))
        if files:
            frames[img] = [np.asarray(Image.open(f).convert("RGBA"), np.float32) / 255 for f in files]
    return frames


def reference_colours(tileset):
    """Snow / desert: [(rgb, class index)] from the TerrainDetailTextures block in rules/palettes.yaml."""
    text = open(os.path.join(MOD, "rules", "palettes.yaml")).read()
    block = re.search(r"Tilesets: " + tileset + r"\n(.*?)(?=\n\t\w|\Z)", text, re.S)
    refs = []
    for key, cls in (("GroundColors", 0), ("DirtColors", 1), ("RockColors", 2), ("WaterColors", 3)):
        m = re.search(key + r": ([0-9A-Fa-f, ]+)", block.group(1)) if block else None
        for h in (m.group(1).split(",") if m else []):
            h = h.strip()
            refs.append((np.array([int(h[k:k + 2], 16) for k in (0, 2, 4)], np.float32) / 255, cls))
    return refs


def classify(rgb, tileset, refs):
    """Class index per pixel (0 grass, 1 dirt, 2 rock, 3 water) with the shader's rules, on unblurred pixels."""
    v = rgb.max(-1)
    if not refs:
        green = (rgb[..., 1] - (rgb[..., 0] + rgb[..., 2]) * 0.5) / (v + 0.02)
        blue = (rgb[..., 2] - (rgb[..., 0] + rgb[..., 1]) * 0.5) / (v + 0.02)
        water = (blue > 0.16) & (v > 0.36)
        rock = (v > 0.39) & ~water
        grass = (green > 0.085) & ~water & ~rock
        dirt = ~water & ~rock & ~grass & (v > 0.205)
        cls = np.where(water, 3, np.where(rock, 2, np.where(dirt, 1, 0)))
    else:
        dist = np.stack([((rgb - c) ** 2).sum(-1) for c, _ in refs], -1)
        cls = np.array([k for _, k in refs])[dist.argmin(-1)]
    return cls


def lum(rgb):
    return rgb @ np.array([0.299, 0.587, 0.114], np.float32)


def majority(labels, n, passes=2):
    """3x3 majority filter over integer labels 0..n-1 (n = number of labels)."""
    for _ in range(passes):
        onehot = np.stack([(labels == k).astype(np.float32) for k in range(n)], -1)
        votes = uniform_filter(onehot, size=(3, 3, 1), mode="nearest")
        labels = votes.argmax(-1)
    return labels


def build(tileset, apply):
    refs = reference_colours(tileset) if tileset != "TEMPERAT" else []
    imgs = templates(tileset)
    frames = export(tileset, imgs)
    missing = [i for i in imgs if i not in frames]
    print(f"{tileset}: {len(imgs)} images, {len(frames)} exported" + (f", MISSING {missing}" if missing else ""))

    # Pass 1: labels (class, light band) for every original pixel; band thresholds per class from the whole tileset
    raw = {}
    for img, fr in frames.items():
        raw[img] = []
        for a in fr:
            rgb, alpha = a[..., :3], a[..., 3]
            cls = classify(rgb, tileset, refs)
            cls = np.where((alpha < 0.5) | (rgb.max(-1) < 0.02), 4, cls)
            raw[img].append((cls, lum(rgb), rgb))
    edges = {}
    for k in range(4):
        vals = np.concatenate([l[c == k] for fr in raw.values() for c, l, _ in fr])
        edges[k] = np.percentile(vals, [100 / BANDS * b for b in range(1, BANDS)]) if len(vals) else []
    nlab = 4 * BANDS + 1
    sums = np.zeros((nlab, 3))
    counts = np.zeros(nlab)
    labelled = {}
    for img, fr in raw.items():
        labelled[img] = []
        for cls, l, rgb in fr:
            band = np.zeros_like(cls)
            for k in range(3):
                m = cls == k
                band[m] = np.searchsorted(edges[k], l[m])
            # Water is one flat band: the shader shows the base tile's light and dark on the HD water, and banded
            # water repeats as a blotchy pattern in every cell
            band[cls == 3] = BANDS // 2
            lab = np.where(cls == 4, nlab - 1, cls * BANDS + band)
            lab = majority(lab, nlab)
            labelled[img].append(lab)
            for k in range(nlab):
                m = lab == k
                sums[k] += rgb[m].sum(0)
                counts[k] += m.sum()
    colour = sums / np.maximum(counts, 1)[:, None]

    # Pass 2: paint
    out_dir = os.path.join(OUT, tileset.lower())
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(abs(hash(tileset)) % 2 ** 32)
    for img, labs in labelled.items():
        tiles = []
        for lab in labs:
            n = gaussian_filter(rng.normal(0, 1, lab.shape), 0.8)
            nw = gaussian_filter(rng.normal(0, 1, lab.shape), 2.5, mode="wrap")
            water = (lab >= 3 * BANDS) & (lab < 4 * BANDS)
            gain = 1 + np.where(water, 0.025 * nw / max(nw.std(), 1e-6), 0.045 * n / max(n.std(), 1e-6))
            rgb = np.clip(colour[lab] * gain[..., None], 0, 1)
            alpha = np.where(lab == nlab - 1, 0, 1)
            tiles.append(np.dstack([rgb, alpha]))
        save(os.path.join(out_dir, os.path.splitext(img)[0] + ".png"), tiles)
    if apply:
        point_tileset(tileset)


def save(path, tiles):
    info = PngImagePlugin.PngInfo()
    sheet = np.zeros((24, 24 * len(tiles), 4), np.uint8)
    for i, t in enumerate(tiles):
        sheet[:, i * 24:(i + 1) * 24] = (t * 255 + 0.5).astype(np.uint8)
        info.add_text(f"Frame[{i}]", f"{i * 24},0,24,24;0,0")
    Image.fromarray(sheet).save(path, pnginfo=info, optimize=True)


def point_tileset(tileset):
    """Images: <classic file> -> ra|bits/terrain-base/<tileset>/<stem>.png for every image we wrote."""
    path = os.path.join(MOD, "tilesets", TILESETS[tileset][0])
    text = open(path).read()
    d = os.path.join(OUT, tileset.lower())

    def repl(m):
        stem = os.path.splitext(m.group(1))[0]
        if os.path.exists(os.path.join(d, stem + ".png")):
            return f"\n\t\tImages: ra|bits/terrain-base/{tileset.lower()}/{stem}.png"
        return m.group(0)
    text = re.sub(r"\n\t\tImages: (?!ra\|)(\S+)", repl, text)
    open(path, "w").write(text)


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(TILESETS)
    for t in names:
        build(t, "--apply" in sys.argv)


if __name__ == "__main__":
    main()
