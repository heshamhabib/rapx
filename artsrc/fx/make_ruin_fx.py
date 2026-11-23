#!/usr/bin/env python3
"""
HD ruins of destroyed buildings (RedAlert Project X).

  python3 artsrc/fx/make_ruin_fx.py [--preview]

Keys the magenta out of assets/fx/ruins/ruin-*.png (from artsrc/fx/generate_ruins.py) and packs them as the frames of
`pxfx` ruin (bits/hd/fx/ruin.png), the rubble and scorched ground WithPxCollapse leaves where a building stood. The
debris sheet (assets/fx/ruins/debris.png, 4 x 2 pieces) becomes `pxfx` rubble (bits/hd/fx/rubble.png), the chunks a
collapsing building throws. Writes mods/rapx/sequences/hd-ruin-fx.yaml. --preview writes artsrc/fx/preview/ruin.png.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter, label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "assets", "fx", "ruins")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-ruin-fx.yaml")
PREVIEW = os.path.join(HERE, "preview")

RUIN_WIDTH = 560     # px per ruin frame (drawn at footprint size by WithPxCollapse, about 3x density)
RUBBLE_SIZE = 64     # px per rubble frame; drawn at the 20 px chunk size
CHUNK_SIZE = 20


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255


def key(img):
    """Alpha from how magenta a pixel is (soot fading into the background keys to soft black), then unmix."""
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    k = np.minimum(r, b) - g
    bgmask = k > 0.5
    bg = np.median(img[bgmask], axis=0) if bgmask.any() else np.array([1, 0, 1], np.float32)
    kb = min(bg[0], bg[2]) - bg[1]
    a = np.clip(1 - k / kb, 0, 1)
    a = np.clip((a - 0.04) / 0.9, 0, 1)
    a = gaussian_filter(a, 0.7)
    safe = np.maximum(a, 0.02)[..., None]
    rgb = np.clip((img - (1 - safe) * bg) / safe, 0, 1)
    # Despill: red and blue may not both rise above green (nothing in the rubble is magenta)
    spill = np.clip(np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1], 0, 1)
    rgb[..., 0] -= spill
    rgb[..., 2] -= spill
    # The AI paints a pinkish halo into the soft soot rim: across the see-through rim, fade the colour to grey soot
    grey = rgb.mean(axis=2, keepdims=True) * np.array([1.0, 0.97, 0.93])
    t = np.clip((a - 0.2) / 0.8, 0, 1)[..., None]
    rgb = grey + (rgb - grey) * t ** 3
    # The faintest edge pixels unmix to bright specks: they can only be thin soot
    faint = np.clip(1 - a / 0.3, 0, 1)[..., None]
    rgb = rgb + (np.array([0.2, 0.19, 0.18]) - rgb) * faint
    return np.dstack([np.clip(rgb, 0, 1), a])


def crop(rgba, threshold=0.03, pad=4):
    ys, xs = np.nonzero(rgba[..., 3] > threshold)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, rgba.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, rgba.shape[1])
    return rgba[y0:y1, x0:x1]


def resize(rgba, w, h):
    """Premultiplied resize, so dark fringes don't bleed from transparent pixels."""
    pm = np.dstack([rgba[..., :3] * rgba[..., 3:], rgba[..., 3:]])
    im = Image.fromarray((pm * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    out = np.asarray(im).astype(np.float32) / 255
    a = out[..., 3:]
    return np.dstack([out[..., :3] / np.maximum(a, 1e-4), a])


def edge_fade(rgba, width=0.06):
    """Fade the last few percent towards the frame border, so a ruin never ends in a hard line."""
    h, w = rgba.shape[:2]
    y = np.minimum(np.arange(h), np.arange(h)[::-1])[:, None] / (h * width)
    x = np.minimum(np.arange(w), np.arange(w)[::-1])[None, :] / (w * width)
    rgba[..., 3] *= np.clip(np.minimum(y, x), 0, 1)
    return rgba


def save(name, frames):
    h, w, _ = frames[0].shape
    sheet = np.concatenate(frames, axis=1)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}.png"),
                                                                       pnginfo=info, optimize=True)
    print(f"  {name}: {len(frames)} frames {w}x{h}")


def ruins():
    files = sorted(glob.glob(os.path.join(SRC, "ruin-*.png")))
    cut = [crop(key(load(f))) for f in files]
    height = max(int(round(c.shape[0] * RUIN_WIDTH / c.shape[1])) for c in cut)
    frames = []
    for c in cut:
        h = int(round(c.shape[0] * RUIN_WIDTH / c.shape[1]))
        fr = np.zeros((height, RUIN_WIDTH, 4), np.float32)
        top = (height - h) // 2
        fr[top:top + h] = resize(c, RUIN_WIDTH, h)
        frames.append(edge_fade(fr))
    return frames


def rubble():
    path = os.path.join(SRC, "debris.png")
    if not os.path.exists(path):
        return []
    rgba = key(load(path))
    # Solid pieces with no soft rim: cut tighter, so no light outline is left around them
    rgba[..., 3] = np.clip((rgba[..., 3] - 0.4) / 0.6, 0, 1)
    # Pieces = connected solid regions, biggest eight, ordered left to right, top to bottom
    lab, n = label(rgba[..., 3] > 0.5)
    sizes = np.bincount(lab.ravel())[1:]
    keep = np.argsort(sizes)[::-1][:8] + 1
    pieces = []
    for i in keep:
        ys, xs = np.nonzero(lab == i)
        pieces.append((ys.mean() // (rgba.shape[0] / 2), xs.mean(), ys.min(), ys.max(), xs.min(), xs.max()))
    pieces.sort()
    frames = []
    for _, _, y0, y1, x0, x1 in pieces:
        p = rgba[max(y0 - 6, 0):y1 + 7, max(x0 - 6, 0):x1 + 7]
        s = (RUBBLE_SIZE - 4) / max(p.shape[:2])
        h, w = max(1, int(p.shape[0] * s)), max(1, int(p.shape[1] * s))
        fr = np.zeros((RUBBLE_SIZE, RUBBLE_SIZE, 4), np.float32)
        y, x = (RUBBLE_SIZE - h) // 2, (RUBBLE_SIZE - w) // 2
        fr[y:y + h, x:x + w] = resize(p, w, h)
        frames.append(fr)
    return frames


def preview(frames, pieces):
    os.makedirs(PREVIEW, exist_ok=True)
    h, w, _ = frames[0].shape
    canvas = np.zeros((h + RUBBLE_SIZE, w * len(frames), 3), np.float32) + np.array([0.86, 0.88, 0.92])
    canvas[:, : w * len(frames) // 2] = np.array([0.36, 0.42, 0.25])
    for i, fr in enumerate(frames):
        a = fr[..., 3:]
        canvas[:h, i * w:(i + 1) * w] = fr[..., :3] * a + canvas[:h, i * w:(i + 1) * w] * (1 - a)
    for i, fr in enumerate(pieces):
        a = fr[..., 3:]
        sl = canvas[h:, i * RUBBLE_SIZE:(i + 1) * RUBBLE_SIZE]
        sl[:] = fr[..., :3] * a + sl * (1 - a)
    Image.fromarray((np.clip(canvas, 0, 1) * 255).astype(np.uint8)).save(os.path.join(PREVIEW, "ruin.png"))


def main():
    frames = ruins()
    save("ruin", frames)
    pieces = rubble()
    y = ["# HD ruins and rubble of destroyed buildings (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_ruin_fx.py - edit that script, not this file.", "", "pxfx:",
         "\truin:", "\t\tFilename: ra|bits/hd/fx/ruin.png", f"\t\tLength: {len(frames)}"]
    if pieces:
        save("rubble", pieces)
        y += ["\trubble:", "\t\tFilename: ra|bits/hd/fx/rubble.png", f"\t\tLength: {len(pieces)}",
              f"\t\tScale: {CHUNK_SIZE / RUBBLE_SIZE:.4f}"]
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    if "--preview" in sys.argv:
        preview(frames, pieces)
    print(f"wrote {SEQUENCES}")


if __name__ == "__main__":
    main()
