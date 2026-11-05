#!/usr/bin/env python3
"""
Turns a Gemini building render (solid magenta background) into game-ready RGBA sprites.

- Keys out the magenta background; the darker magenta cast shadow becomes a soft black shadow.
- Removes magenta spill from the building's edges.
- Scales the building so its width matches its footprint (cells * 24 world px) at DENSITY
  sprite pixels per world pixel, and reports the sequence Offset that centres it on the footprint.
- Wide images (intact building on the left, damaged on the right) are split automatically:
  the damaged half is aligned to the intact one and both get the same size, scale and offset.
  Outputs <dst> and <dst>-damaged.png.

  python3 artsrc/buildings/process_building.py in.jpeg out.png --cells 2 [--density 3]
"""
import argparse
import os

import numpy as np
from PIL import Image
from scipy.ndimage import binary_opening, gaussian_filter, label

CELL = 24


def key(img, shadow_opacity):
    """Returns (rgba, building_alpha) for an image on a magenta background."""
    border = np.concatenate([img[:8].reshape(-1, 3), img[-8:].reshape(-1, 3), img[:, :8].reshape(-1, 3), img[:, -8:].reshape(-1, 3)])
    bg = np.median(border, axis=0)

    # Background and its cast shadow are magenta at different brightness; the building is
    # neutral grey (or team green). Judge by chroma ("how magenta"), not by brightness.
    mx = img.max(-1)
    magenta = (np.minimum(img[..., 0], img[..., 2]) - img[..., 1]) / (mx + 1e-3)
    bg_magenta = (min(bg[0], bg[2]) - bg[1]) / bg.max()
    alpha = 1 - np.clip((magenta / bg_magenta - 0.30) / (0.80 - 0.30), 0, 1)
    s = np.clip(np.maximum(img[..., 0], img[..., 2]) / max(bg[0], bg[2]), 0, 1.2)

    # Drop tiny specks; keep the main object (building, its smoke etc.)
    solid = binary_opening(alpha > 0.5, iterations=2)
    labels, n = label(solid)
    if n > 1:
        sizes = np.bincount(labels.ravel())
        sizes[0] = 0
        keep = sizes > sizes.max() * 0.02
        alpha = np.where(keep[labels] | (alpha < 0.5), alpha, 0)

    # Un-mix the edges: colour = (pixel - (1 - a) * s * bg) / a, then remove remaining magenta spill
    a3 = np.maximum(alpha, 1e-3)[..., None]
    fg = np.clip((img - (1 - alpha)[..., None] * s[..., None] * bg) / a3, 0, 1)
    spill = np.clip(np.minimum(fg[..., 0], fg[..., 2]) - fg[..., 1], 0, None)
    fg[..., 0] -= spill
    fg[..., 2] -= spill

    # Shadow: background pixels darker than the backdrop become translucent black
    # (ignoring the slight brightness noise / vignetting of AI-rendered backdrops)
    shadow = np.clip((1 - s - 0.05) / 0.50, 0, 1) * shadow_opacity * (1 - alpha)

    # No usable cast shadow in the render: synthesize a soft one falling to the bottom-right (sun top-left)
    if shadow.sum() < 0.05 * alpha.sum():
        h, w = alpha.shape
        size = np.sqrt(alpha.sum())
        dx, dy = int(size * 0.10), int(size * 0.06)
        cast = np.zeros_like(alpha)
        cast[dy:, dx:] = alpha[:h - dy, :w - dx]
        cast = gaussian_filter(np.maximum(cast, alpha), size * 0.02)
        shadow = np.clip(cast, 0, 1) * shadow_opacity * 0.85 * (1 - alpha)
    out_a = alpha + shadow

    # Near-invisible pixels become fully transparent: the game's darkening / highlight overlays
    # (e.g. low power) would otherwise reveal them as a box around the sprite
    out_a = np.where(out_a < 0.05, 0, out_a)
    out_rgb = fg * (alpha / np.maximum(out_a, 1e-3))[..., None]
    return np.dstack([out_rgb, out_a]), alpha


def align(reference, moving, max_shift=80):
    """Integer (dy, dx) that best overlays the `moving` mask onto `reference` (FFT cross-correlation)."""
    f = np.fft.rfft2(reference) * np.conj(np.fft.rfft2(moving))
    corr = np.fft.irfft2(f, reference.shape)
    corr = np.roll(np.roll(corr, max_shift, 0), max_shift, 1)[:2 * max_shift + 1, :2 * max_shift + 1]
    dy, dx = np.unravel_index(np.argmax(corr), corr.shape)
    return dy - max_shift, dx - max_shift


def shift(a, dy, dx):
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def resize(crop, scale):
    """Premultiplied Lanczos resize (avoids dark fringes) -> uint8 RGBA."""
    pm = np.dstack([crop[..., :3] * crop[..., 3:], crop[..., 3]])
    size = (max(1, round(crop.shape[1] * scale)), max(1, round(crop.shape[0] * scale)))
    chans = [np.asarray(Image.fromarray((pm[..., c] * 255).astype(np.uint8)).resize(size, Image.LANCZOS), dtype=np.float32) / 255 for c in range(4)]
    pm = np.dstack(chans)
    a = pm[..., 3:]
    rgb = np.where(a > 1e-3, pm[..., :3] / np.maximum(a, 1e-3), 0)
    return (np.clip(np.dstack([rgb, a]), 0, 1) * 255).astype(np.uint8), size


def process(src, dst, cells, density=3.0, shadow_opacity=0.6, extra_scale=1.0, log=print):
    """Process one render; returns (paths, size, offset). Wide images yield <dst> and <dst>-damaged."""
    img = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255
    h, w, _ = img.shape

    # Wide images hold the intact building (left) and the damaged one (right)
    halves = [img[:, :w // 2], img[:, w // 2:w // 2 * 2]] if w > 1.6 * h else [img]
    keyed = [key(half, shadow_opacity) for half in halves]

    if len(keyed) == 2:
        dy, dx = align(keyed[0][1], keyed[1][1])
        keyed[1] = (shift(keyed[1][0], dy, dx), shift(keyed[1][1], dy, dx))
        log(f"aligned damaged half by {dx},{dy} px")

    # The intact building's bounds (without the shadow) determine scale and centre;
    # the crop covers everything visible in either version so both sprites line up exactly
    ys, xs = np.nonzero(keyed[0][1] > 0.5)
    bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    visible = np.any([rgba[..., 3] > 0.02 for rgba, _ in keyed], axis=0)
    ys2, xs2 = np.nonzero(visible)
    cx0, cx1 = min(xs2.min(), bx0), max(xs2.max() + 1, bx1)
    cy0, cy1 = min(ys2.min(), by0), max(ys2.max() + 1, by1)

    scale = cells * CELL * density * extra_scale / (bx1 - bx0)
    stem, ext = os.path.splitext(dst)
    paths = [dst, f"{stem}-damaged{ext}"][:len(keyed)]
    for (rgba, _), path in zip(keyed, paths):
        final, size = resize(rgba[cy0:cy1, cx0:cx1], scale)
        Image.fromarray(final).save(path, optimize=True)

    # Offset (sprite pixels) that moves the building's centre onto the image centre
    ox = round(size[0] / 2 - ((bx0 + bx1) / 2 - cx0) * scale)
    oy = round(size[1] / 2 - ((by0 + by1) / 2 - cy0) * scale)
    for path in paths:
        log(f"{path}: {size[0]}x{size[1]} px, scale {scale:.3f}, sequence Offset: {ox},{oy}")
    return paths, size, (ox, oy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--cells", type=int, required=True, help="building width in cells (excluding the bib row)")
    ap.add_argument("--density", type=float, default=3.0, help="sprite pixels per world pixel")
    ap.add_argument("--shadow", type=float, default=0.6, help="maximum shadow opacity")
    ap.add_argument("--scale", type=float, default=1.0, help="extra size multiplier relative to the footprint")
    args = ap.parse_args()
    process(args.src, args.dst, args.cells, args.density, args.shadow, args.scale)


if __name__ == "__main__":
    main()
