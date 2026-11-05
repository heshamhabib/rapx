#!/usr/bin/env python3
"""
Draws the particle sprites used by the HD building effects (WithPxBuildingFx, WithPxDamageFx,
WithPxCollapse) and writes mods/rapx/sequences/hd-fx.yaml (image `pxfx`).

All sprites are white / neutral so the traits can tint them (smoke grey, steam white, sparks orange...).
Sprites are drawn at 3x density like the HD buildings (Scale 1/3 in the sequences).

  python3 artsrc/fx/make_fx.py
"""
import os

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-fx.yaml")
DENSITY = 3.0

rng = np.random.default_rng(7)


def grid(size):
    y, x = np.mgrid[0:size[1], 0:size[0]].astype(np.float32)
    return x - (size[0] - 1) / 2, y - (size[1] - 1) / 2


def noise(size, scale, octaves=4):
    """Smooth value noise in [0, 1]."""
    total = np.zeros((size[1], size[0]), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        n = gaussian_filter(rng.random((size[1], size[0])).astype(np.float32), scale / (2 ** o), mode="wrap")
        n = (n - n.min()) / (n.max() - n.min() + 1e-6)
        total += n * amp
        norm += amp
        amp *= 0.5
    return total / norm


def save(name, frames, sequence_opts):
    """frames: list of float RGBA arrays (premultiplied=False). Writes a horizontal sheet."""
    h, w, _ = frames[0].shape
    sheet = np.concatenate(frames, axis=1)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}.png"), pnginfo=info, optimize=True)
    return name, len(frames), sequence_opts


def puff(size=72):
    """Soft billowy smoke ball: white, shaded darker at the bottom, alpha from lumpy noise."""
    x, y = grid((size, size))
    r = np.sqrt(x ** 2 + y ** 2) / (size / 2)
    n = noise((size, size), 5)
    a = np.clip((1 - r - (n - 0.5) * 0.9) * 2.2, 0, 1) ** 1.5
    a = gaussian_filter(a, 1.2)
    shade = np.clip(0.95 - (y / size) * 0.5 + (n - 0.5) * 0.35, 0.45, 1)
    return np.dstack([shade, shade, shade, a * 0.9])


def glow(size=64, power=2.2):
    x, y = grid((size, size))
    r = np.sqrt(x ** 2 + y ** 2) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** power
    core = np.clip(1 - r * 4, 0, 1) ** 2
    v = np.clip(a + core, 0, 1)
    return np.dstack([v, v, v, v])


def flare(w=128, h=24):
    """Horizontal lens streak for beacons."""
    x, y = grid((w, h))
    v = np.exp(-(y / (h * 0.12)) ** 2) * np.clip(1 - np.abs(x) / (w / 2), 0, 1) ** 2
    v += np.exp(-(x ** 2 + y ** 2) / (h * 0.35) ** 2)
    v = np.clip(v, 0, 1)
    return np.dstack([v, v, v, v])


def spark(size=16):
    x, y = grid((size, size))
    r = np.sqrt(x ** 2 + y ** 2) / (size / 2)
    v = np.clip(1 - r, 0, 1) ** 3 + np.clip(1 - r * 2.5, 0, 1)
    v = np.clip(v, 0, 1)
    return np.dstack([v, v, v, v])


def flame_frames(w=48, h=72, n=10):
    """Flickering flame tongues (additive): white-yellow core, orange body, red tips."""
    frames = []
    base = noise((w, h * 3), 4, 3)
    x, y = grid((w, h))
    yy = (y + h / 2) / h                       # 0 top .. 1 bottom
    for i in range(n):
        off = int(i * h * 2 / n)
        nz = base[h * 2 - off:h * 3 - off] if off else base[h * 2:]
        width = (0.15 + 0.85 * yy ** 0.8) * (w / 2) * (0.75 + 0.5 * nz)
        body = np.clip(1 - np.abs(x + (nz - 0.5) * 10 * (1 - yy)) / width, 0, 1)
        body *= np.clip((yy - 0.05 - (nz - 0.5) * 0.5) * 2.5, 0, 1)
        body *= np.clip((1 - yy) * 8, 0, 1)    # soft base
        heat = np.clip(body * (0.4 + yy * 0.9), 0, 1)
        r = np.clip(heat * 2.0, 0, 1)
        g = np.clip(heat * 1.4 - 0.2, 0, 1)
        b = np.clip(heat * 1.6 - 0.9, 0, 1)
        a = np.clip(body * 1.5, 0, 1)
        frames.append(np.dstack([r * a, g * a, b * a, a]))
    return frames


def chunk_frames(size=20, n=8):
    """Small debris chunks (rubble, metal) with light top-left shading."""
    frames = []
    for i in range(n):
        x, y = grid((size, size))
        ang = np.arctan2(y, x)
        k = rng.integers(5, 8)
        radii = rng.uniform(0.45, 0.95, k)
        idx = ((ang + np.pi) / (2 * np.pi) * k).astype(int) % k
        nxt = (idx + 1) % k
        f = ((ang + np.pi) / (2 * np.pi) * k) % 1
        rad = (radii[idx] * (1 - f) + radii[nxt] * f) * size / 2
        a = np.clip(rad - np.sqrt(x ** 2 + y ** 2), 0, 1)
        light = np.clip(0.55 - (x + y) / size * 0.6, 0.15, 1)
        tone = rng.uniform(0.35, 0.65)
        warm = rng.uniform(0.9, 1.05)
        frames.append(np.dstack([light * tone * warm, light * tone, light * tone / warm, a]))
    return frames


def scorch(w=240, h=130):
    """Burn mark left on the ground after a building collapses."""
    x, y = grid((w, h))
    r = np.sqrt((x / (w / 2)) ** 2 + (y / (h / 2)) ** 2)
    n = noise((w, h), 6)
    a = np.clip((1 - r - (n - 0.5) * 0.7) * 2.5, 0, 1) * 0.85
    v = 0.06 + n * 0.08
    return np.dstack([v * 1.1, v, v * 0.9, a])


def shockwave(size=128, n=6):
    """Expanding dust ring lying on the ground (an ellipse in the game's view)."""
    frames = []
    x, y = grid((size, size // 2))
    r = np.sqrt(x ** 2 + (y * 2) ** 2) / (size / 2)
    for i in range(n):
        t = (i + 1) / n
        ring = np.exp(-((r - t * 0.9) / (0.08 + 0.1 * t)) ** 2) * (1 - t * 0.7)
        frames.append(np.dstack([np.ones_like(r), np.ones_like(r) * 0.95, np.ones_like(r) * 0.9, ring]))
    return frames


def main():
    os.makedirs(OUT, exist_ok=True)
    sequences = [
        save("puff", [puff() for _ in range(6)], {}),
        save("glow", [glow()], {"BlendMode": "Additive"}),
        save("flare", [flare()], {"BlendMode": "Additive"}),
        save("spark", [spark()], {"BlendMode": "Additive"}),
        save("flame", flame_frames(), {"BlendMode": "Additive"}),
        save("chunk", chunk_frames(), {}),
        save("scorch", [scorch()], {}),
        save("ring", shockwave(), {}),
    ]

    yaml = [
        "# Particle sprites for the HD building effects (RedAlert Project X).",
        "# GENERATED by artsrc/fx/make_fx.py - edit that script, not this file.",
        "",
        "pxfx:",
        "\tDefaults:",
        f"\t\tScale: {1 / DENSITY:.4f}",
    ]
    for name, length, opts in sequences:
        yaml += [f"\t{name}:", f"\t\tFilename: ra|bits/hd/fx/{name}.png", f"\t\tLength: {length}"]
        yaml += [f"\t\t{k}: {v}" for k, v in opts.items()]
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(yaml) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))


if __name__ == "__main__":
    main()
