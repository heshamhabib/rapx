#!/usr/bin/env python3
"""
Draws the HD money popup art used by PxCashPopups (the "+$75" that rises from oil rigs, refineries,
bounties, sold buildings...) and writes mods/rapx/sequences/hd-cash.yaml (image `pxcash`).

- Glyphs + - $ 0-9 in two styles: gold (income) and red (spending). Bold condensed type with a
  metallic vertical gradient, a bright bevel along the top edge, a dark outline and a soft warm glow.
  One PNG per glyph so the game can read each glyph's width from its sprite.
- A spinning gold coin (16 frames) with an embossed $ and a rim.
- A four-point sparkle star and a soft dark backing plate.

Everything is drawn at 3x density (Scale 1/3) like the other HD art.

  python3 artsrc/fx/make_cash.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from scipy.ndimage import binary_dilation, gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "cash")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-cash.yaml")
FONT = os.path.join(ROOT, "mods", "rapx", "fonts", "Rajdhani-Bold.ttf")
DENSITY = 3.0

# Must match PxCashPopupsInfo.GlyphPadding (sprite pixels of outline/glow around each glyph)
PAD = 12
SIZE = 66

GLYPHS = {"plus": "+", "minus": "-", "dollar": "$", **{str(d): str(d) for d in range(10)}}

STYLES = {
    # top highlight, upper body, lower body, bottom, outline, glow
    "gold": dict(stops=[(1.0, 0.98, 0.82), (1.0, 0.84, 0.36), (0.93, 0.6, 0.12), (0.62, 0.33, 0.05)],
                 outline=(0.18, 0.09, 0.01), glow=(1.0, 0.7, 0.2)),
    "red": dict(stops=[(1.0, 0.86, 0.8), (1.0, 0.42, 0.32), (0.86, 0.14, 0.1), (0.5, 0.04, 0.04)],
                outline=(0.16, 0.02, 0.02), glow=(1.0, 0.25, 0.15)),
}


def gradient(h, stops):
    """Vertical colour ramp through the given stops (top to bottom)."""
    t = np.linspace(0, 1, h)[:, None]
    pos = np.linspace(0, 1, len(stops))
    out = np.zeros((h, 3))
    for c in range(3):
        out[:, c] = np.interp(t[:, 0], pos, [s[c] for s in stops])
    return out[:, None, :]


def glyph(char, style):
    font = ImageFont.truetype(FONT, SIZE)
    l, t, r, b = font.getbbox("0")
    height = b - t                                        # cap height of digits: shared baseline/height
    l, _, r, _ = font.getbbox(char)
    w = (r - l) + 2 * PAD
    h = height + 2 * PAD
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((PAD - l, PAD - t), char, font=font, fill=255)
    m = np.asarray(mask, dtype=np.float32) / 255

    fill = gradient(h, style["stops"]) * np.ones((1, w, 1))
    # Bevel: light where the glyph's top edge is (mask minus mask shifted down), dark at the bottom edge
    up = np.zeros_like(m)
    up[2:] = m[:-2]
    bevel_top = np.clip(m - up, 0, 1)
    down = np.zeros_like(m)
    down[:-2] = m[2:]
    bevel_bottom = np.clip(m - down, 0, 1)
    fill = fill + bevel_top[..., None] * 0.45 - bevel_bottom[..., None] * 0.25
    # A thin specular line across the upper third
    y = np.arange(h)[:, None]
    shine = np.exp(-((y - (PAD + height * 0.3)) / 2.0) ** 2) * 0.25
    fill = np.clip(fill + shine[..., None], 0, 1)

    outline = binary_dilation(m > 0.5, iterations=3).astype(np.float32)
    outline = np.maximum(gaussian_filter(outline, 0.8), m)
    glow = gaussian_filter(outline, 4.0) * 0.55

    rgb = np.zeros((h, w, 3), np.float32)
    a = np.zeros((h, w), np.float32)
    # glow (behind), outline, fill
    rgb[:] = style["glow"]
    a = glow
    oa = outline
    rgb = rgb * (a * (1 - oa))[..., None] + np.array(style["outline"]) * oa[..., None]
    a = oa + a * (1 - oa)
    rgb = rgb * (1 - m[..., None]) + fill * m[..., None]
    a = np.maximum(a, m)
    rgb = np.where(a[..., None] > 1e-3, rgb / np.maximum(a, 1e-3)[..., None], 0)
    return np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)])


def coin_frames(size=72, n=16):
    """Spinning coin: the face narrows with cos(angle), showing its rim; the back shows a plain face."""
    font = ImageFont.truetype(FONT, int(size * 0.62))
    frames = []
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = (size - 1) / 2
    r = size * 0.4
    # Face artwork at full width: radial gold, inner ring, embossed $
    face = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(face)
    l, t, rr, b = font.getbbox("$")
    d.text((cx - (l + rr) / 2, cy - (t + b) / 2), "$", font=font, fill=255)
    dollar = np.asarray(face, dtype=np.float32) / 255
    for i in range(n):
        ang = i / n * np.pi * 2
        sx = max(abs(np.cos(ang)), 0.08)
        thick = (1 - sx) * size * 0.07 + 1
        front = np.cos(ang) >= 0
        # Rim: ellipse offset sideways by the thickness
        rim = (((xx - cx - thick) / (r * sx)) ** 2 + ((yy - cy) / r) ** 2) <= 1
        disc_d = ((xx - cx) / (r * sx)) ** 2 + ((yy - cy) / r) ** 2
        disc = disc_d <= 1
        u = (xx - cx) / sx + cx                                # unsquash to sample the face artwork
        ui = np.clip(np.round(u).astype(int), 0, size - 1)
        sym = dollar[yy.astype(int), ui] * disc * (1 if front else 0.0)
        ring = np.exp(-((np.sqrt(disc_d) - 0.8) / 0.05) ** 2) * disc

        shade = 1.05 - 0.45 * ((yy - cy) / r + 1) / 2 - 0.2 * np.sqrt(np.clip(disc_d, 0, 1))
        light = 0.75 + 0.25 * sx
        base = np.array([1.0, 0.78, 0.25])
        col = np.zeros((size, size, 3), np.float32)
        col[rim & ~disc] = np.array([0.55, 0.32, 0.05])
        col[disc] = (base * (shade * light)[..., None])[disc]
        col += (ring * 0.25)[..., None] * np.array([1, 0.9, 0.5])
        # Embossed $: lighter with a dark lower edge
        emb = np.zeros_like(sym)
        emb[1:] = sym[:-1]
        col += sym[..., None] * np.array([0.25, 0.2, 0.05]) - np.clip(emb - sym, 0, 1)[..., None] * 0.35
        # Specular glint sweeping over the face as it turns
        glint = np.exp(-(((xx - cx) / (r * sx) - np.sin(ang) * 0.6) / 0.18) ** 2) * disc * 0.35
        col += glint[..., None]
        a = (rim | disc).astype(np.float32)
        a = np.maximum(gaussian_filter(a, 0.6), disc.astype(np.float32) * 0)
        # dark outline
        outline = gaussian_filter(binary_dilation(a > 0.5, iterations=2).astype(np.float32), 0.7)
        col = col * a[..., None] + np.array([0.2, 0.1, 0.0]) * (outline * (1 - a))[..., None]
        alpha = np.maximum(a, outline)
        col = np.where(alpha[..., None] > 1e-3, col / np.maximum(alpha, 1e-3)[..., None], 0)
        frames.append(np.dstack([np.clip(col, 0, 1), alpha]))
    return frames


def sparkle(size=40):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) - (size - 1) / 2
    r = np.sqrt(x ** 2 + y ** 2) / (size / 2)
    star = np.exp(-np.abs(x) / 1.2) * np.clip(1 - np.abs(y) / (size / 2), 0, 1) ** 2
    star += np.exp(-np.abs(y) / 1.2) * np.clip(1 - np.abs(x) / (size / 2), 0, 1) ** 2
    star += np.clip(1 - r * 2.5, 0, 1) ** 2
    v = np.clip(star, 0, 1)
    return np.dstack([v, v, v, v])


def backing(w=240, h=80):
    """Soft dark plate (3:1) behind the popup so it reads on snow, ore or water."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = np.clip(np.abs(x - (w - 1) / 2) - (w - h) / 2, 0, None) / (h / 2)
    dy = np.abs(y - (h - 1) / 2) / (h / 2)
    a = np.clip(1 - np.sqrt(dx ** 2 + dy ** 2), 0, 1) ** 1.6 * 0.75
    z = np.zeros_like(a)
    return np.dstack([z + 0.03, z + 0.02, z, a])


def save(path, frames):
    h, w, _ = frames[0].shape
    info = PngImagePlugin.PngInfo()
    if len(frames) > 1:
        info.add_text("FrameSize", f"{w},{h}")
        info.add_text("FrameAmount", str(len(frames)))
    sheet = np.concatenate(frames, axis=1)
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(path, pnginfo=info, optimize=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    yaml = [
        "# HD money popup art (RedAlert Project X).",
        "# GENERATED by artsrc/fx/make_cash.py - edit that script, not this file.",
        "",
        "pxcash:",
        "\tDefaults:",
        f"\t\tScale: {1 / DENSITY:.4f}",
    ]
    for style_name, style in STYLES.items():
        for name, char in GLYPHS.items():
            file = f"{style_name}-{name}.png"
            save(os.path.join(OUT, file), [glyph(char, style)])
            yaml += [f"\t{style_name}-{name}:", f"\t\tFilename: ra|bits/hd/cash/{file}"]

    coins = coin_frames()
    save(os.path.join(OUT, "coin.png"), coins)
    save(os.path.join(OUT, "sparkle.png"), [sparkle()])
    save(os.path.join(OUT, "backing.png"), [backing()])
    yaml += ["\tcoin:", "\t\tFilename: ra|bits/hd/cash/coin.png", f"\t\tLength: {len(coins)}"]
    yaml += ["\tbacking:", "\t\tFilename: ra|bits/hd/cash/backing.png"]
    yaml += ["\tsparkle:", "\t\tFilename: ra|bits/hd/cash/sparkle.png", "\t\tBlendMode: Additive"]

    with open(SEQUENCES, "w") as f:
        f.write("\n".join(yaml) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))


if __name__ == "__main__":
    main()
