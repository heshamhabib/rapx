#!/usr/bin/env python3
"""
Builds the HD wall sprites (chain-link CYCL, barbed wire BARB, wooden fence WOOD) from the AI wall renders.

Input: assets/env/walls/<id>.png - three pieces left to right on magenta: (1) a standalone post, (2) an east-west
section that spans exactly one map tile between its two post centres, (3) a north-south section running away
from the camera (back post at the top, front post at the bottom).

The game picks one of 16 frames per wall cell from its neighbours (WithWallSpriteBody: north 1, east 2, south 4,
west 8). Every frame is composed from half-sections cut at the middle of each section, back to front:
north half, west/east halves, the post, south half. Frames 16-31 are the damaged versions (torn, darker fence).
Output: mods/rapx/bits/hd/env/<id>-wall.png (PngSheet, 32 frames) + sequence lines for hd-env.yaml.

  python3 artsrc/env/make_walls.py [--force] [--preview]      (make_env.py runs it too)
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image, PngImagePlugin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "buildings"))
from process_building import key  # noqa: E402

ASSETS = os.path.join(ROOT, "assets", "env", "walls")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "env")
PREVIEW = os.path.join(HERE, "preview")
DENSITY = 3.0
TILE = int(24 * DENSITY)            # one map cell in HD sprite pixels
W, H = 120, 220                     # frame size; the cell centre is the frame centre
BASE = (W // 2, H // 2 + 18)        # post base: 6 world pixels below the cell centre, like the classic walls
SHADOW_OPACITY = 0.55


def runs(flags):
    """[(start, end)] of consecutive True values."""
    out, start = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i))
            start = None
    return out


def to_image(rgba):
    return Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8))


def scaled(rgba, sx, sy):
    """Premultiplied Lanczos resize with separate x / y scale."""
    h, w = rgba.shape[:2]
    size = (max(1, round(w * sx)), max(1, round(h * sy)))
    pm = np.dstack([rgba[..., :3] * rgba[..., 3:], rgba[..., 3]])
    chans = [np.asarray(Image.fromarray((pm[..., c] * 255).astype(np.uint8)).resize(size, Image.LANCZOS), np.float32) / 255
             for c in range(4)]
    pm = np.dstack(chans)
    a = pm[..., 3:]
    return np.dstack([np.where(a > 1e-3, pm[..., :3] / np.maximum(a, 1e-3), 0), a])


def pieces(path):
    """Keys the render and measures the east-west section. Returns the parts as float RGBA arrays plus anchors.
    The AI's north-south piece is drawn almost end-on (two overlapping posts), so the north-south fence is built
    from the east-west rails instead: the rail band between the posts, turned to run away from the camera."""
    img = np.asarray(Image.open(path).convert("RGB"), np.float32) / 255
    h, w, _ = img.shape
    ew, ew_mask = key(img[:, w // 3:2 * w // 3], SHADOW_OPACITY)
    solid = ew_mask > 0.5
    rows = np.nonzero(solid.any(1))[0]
    reach, bottom = rows.min(), rows.max()

    # Posts: columns that are solid over most of the object's height (rails, wire and mesh are sparse)
    cover = solid[reach:bottom + 1].mean(0)
    post_runs = [r for r in runs(cover > 0.7) if r[1] - r[0] > 3]
    if len(post_runs) < 2:
        raise ValueError(f"{path}: could not find both posts of the east-west section")
    (l0, l1), (r0, r1) = post_runs[0], post_runs[-1]
    cl, cr = (l0 + l1) / 2, (r0 + r1) / 2
    base = max(np.nonzero(solid[:, l0:l1].any(1))[0].max(), np.nonzero(solid[:, r0:r1].any(1))[0].max())
    scale = TILE / (cr - cl)

    pad = max(2, int((l1 - l0) * 0.15))
    post = ew[:, max(0, l0 - pad):l1 + pad]
    post_anchor = (cl - max(0, l0 - pad), base)
    mid = int(round((cl + cr) / 2))
    east = ew[:, int(cl):mid]              # from the post centre to the middle of the span
    west = ew[:, mid:int(round(cr)) + 1]   # from the middle of the span to the post centre

    # Rail band between the posts (fence only), turned 90 degrees so its length runs north-south
    f0, f1 = l1 + pad, r0 - pad
    band_rows = np.nonzero(solid[:, f0:f1].any(1))[0]
    rail_top, rail_bottom = band_rows.min(), band_rows.max()
    rails = ew[rail_top:rail_bottom + 1, f0:f1]
    strip = np.rot90(rails, 1).copy()      # (length, band height)
    return dict(scale=scale, post=(post, post_anchor), east=(east, (0, base)), west=(west, (west.shape[1], base)),
                strip=strip, rail_top=base - rail_top, rail_bottom=base - rail_bottom)


def place_strip(canvas, strip, width, top, bottom):
    """Draws the north-south rail strip as a narrow vertical band from `top` to `bottom` (canvas rows)."""
    sx = width / strip.shape[1]
    sy = (bottom - top) / strip.shape[0]
    img = to_image(scaled(strip, sx, sy))
    x = int(round(BASE[0] - img.width / 2))
    y = int(round(top))
    img = img.crop((max(0, -x), max(0, -y), img.width, img.height))
    canvas.alpha_composite(img, (max(0, x), max(0, y)))


def place(canvas, part, anchor, sx, sy, at):
    """Composites a part so its anchor (in part pixels) lands on `at` (canvas pixels)."""
    img = to_image(scaled(part, sx, sy))
    x = int(round(at[0] - anchor[0] * sx))
    y = int(round(at[1] - anchor[1] * sy))
    # alpha_composite needs a non-negative destination: crop whatever sticks out at the top / left
    img = img.crop((max(0, -x), max(0, -y), img.width, img.height))
    canvas.alpha_composite(img, (max(0, x), max(0, y)))


def damage(rgba, seed):
    """Torn, sooty fence: holes from blotchy noise and darker colours."""
    rng = np.random.default_rng(seed)
    h, w = rgba.shape[:2]
    noise = np.asarray(Image.fromarray((rng.random((max(2, h // 12), max(2, w // 12))) * 255).astype(np.uint8))
                       .resize((w, h), Image.BICUBIC), np.float32) / 255
    out = rgba.copy()
    out[..., 3] *= np.clip((noise - 0.38) * 5, 0, 1)
    out[..., :3] *= 0.72
    return out


def compose(p, bits, damaged):
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    s = p["scale"]
    parts = {k: p[k] for k in ("east", "west")}
    strip = p["strip"]
    if damaged:
        parts = {k: (damage(v[0], hash(k) & 0xffff), v[1]) for k, v in parts.items()}
        strip = damage(strip, 77)
    # Rails seen running away from the camera: a narrow band at rail height, half a tile long each way
    width = max(6, min(18, strip.shape[1] * s * 0.35))
    top_here, bottom_here = BASE[1] - p["rail_top"] * s, BASE[1] - p["rail_bottom"] * s
    half = TILE / 2
    # Back to front
    if bits & 1:
        place_strip(canvas, strip, width, top_here - half, bottom_here)
    if bits & 8:
        place(canvas, *parts["west"], s, s, BASE)
    if bits & 2:
        place(canvas, *parts["east"], s, s, BASE)
    post, anchor = p["post"]
    place(canvas, post * np.array([0.8, 0.8, 0.8, 1.0]) if damaged else post, anchor, s, s, BASE)
    if bits & 4:
        place_strip(canvas, strip, width, top_here, bottom_here + half)
    return canvas


def process_walls(force=False, log=print, preview=False):
    """Builds every wall sheet whose render is newer than it. Returns sequence lines for hd-env.yaml."""
    lines = []
    for path in sorted(glob.glob(os.path.join(ASSETS, "*.png"))):
        wall = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(OUT, f"{wall}-wall.png")
        if force or not os.path.exists(out) or os.path.getmtime(path) > os.path.getmtime(out):
            try:
                p = pieces(path)
            except ValueError as e:
                log(f"  {e}, skipped")
                continue
            frames = [compose(p, bits, damaged) for damaged in (False, True) for bits in range(16)]
            sheet = Image.new("RGBA", (W * 8, H * 4), (0, 0, 0, 0))
            for i, f in enumerate(frames):
                sheet.paste(f, ((i % 8) * W, (i // 8) * H))
            meta = PngImagePlugin.PngInfo()
            meta.add_text("FrameSize", f"{W},{H}")
            meta.add_text("FrameAmount", str(len(frames)))
            os.makedirs(OUT, exist_ok=True)
            sheet.save(out, pnginfo=meta, optimize=True)
            log(f"  {os.path.relpath(path, ROOT)} -> {os.path.relpath(out, ROOT)} (scale {p['scale']:.3f})")
            if preview:
                write_preview(wall, frames)
        if os.path.exists(out):
            lines += [f"{wall}:",
                      "\tidle:", f"\t\tFilename: ra|bits/hd/env/{wall}-wall.png", "\t\tStart: 0", "\t\tLength: 16",
                      f"\t\tScale: {1 / DENSITY:.4f}", "\t\tOffset: 0,0",
                      "\tdamaged-idle:", f"\t\tFilename: ra|bits/hd/env/{wall}-wall.png", "\t\tStart: 16", "\t\tLength: 16",
                      f"\t\tScale: {1 / DENSITY:.4f}", "\t\tOffset: 0,0", ""]
    return lines


def write_preview(wall, frames):
    """A small walled yard (corners, T-joints, a cross, a gap) on grass, the way the game puts frames together."""
    layout = ["#####.##",
              "#...#..#",
              "#...####",
              "#...#..#",
              "#####..#"]
    rows, cols = len(layout), len(layout[0])
    img = Image.new("RGBA", (cols * TILE + W, rows * TILE + H), (86, 104, 60, 255))
    for damaged in (False,):
        for y in range(rows):
            for x in range(cols):
                if layout[y][x] != "#":
                    continue

                def at(dx, dy):
                    yy, xx = y + dy, x + dx
                    return 0 <= yy < rows and 0 <= xx < cols and layout[yy][xx] == "#"
                bits = (1 if at(0, -1) else 0) | (2 if at(1, 0) else 0) | (4 if at(0, 1) else 0) | (8 if at(-1, 0) else 0)
                cx, cy = x * TILE + TILE // 2 + W // 2, y * TILE + TILE // 2 + H // 2
                img.alpha_composite(frames[bits + (16 if damaged else 0)], (cx - W // 2, cy - H // 2))
    os.makedirs(PREVIEW, exist_ok=True)
    img.save(os.path.join(PREVIEW, f"wall-{wall}.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--preview", action="store_true", help="write artsrc/env/preview/wall-<id>.png")
    args = ap.parse_args()
    process_walls(args.force, print, args.preview)
