#!/usr/bin/env python3
"""Build the animated light layers for the main menu (drawn by PxMenuFxWidget).

Each spot below cuts the bright, hot parts of mods/rapx/uibits/menu-background.png out of a soft
ellipse, adds a little bloom, and saves it as an additive layer (black = no light). The widget
fades each layer in and out with its own effect, so fires flicker independently of each other.

Writes mods/rapx/uibits/menu-fx/*.png and menu-fx/menu-fx.yaml. Spots below are in menu-background.png
pixels; the manifest shifts them to menu-background-full.png (see make_menu_bg.py).
Re-run after replacing menu-background.png, and move the spots if the art changes.
"""
import os

import numpy as np
from PIL import Image, ImageFilter

from make_menu_bg import offset_for

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UIBITS = os.path.join(ROOT, "mods", "rapx", "uibits")
OUT = os.path.join(UIBITS, "menu-fx")

LAYER_SCALE = 0.5   # glow layers are soft, so half resolution is plenty
BLOOM = 10          # bloom blur radius in layer pixels

# name: (cx, cy, rx, ry, mask, effect, speed, min, max)
#   mask   fire = orange/red highlights, red = saturated reds, bright = any bright saturated colour,
#          shine = bright metal highlights (kept sharp: full resolution, no bloom)
#   effect Flicker = jittery fire noise, Pulse = slow sine breathing, Twinkle = sharp occasional peaks,
#          Shine = a band of light sweeping left to right, speed sweeps per second
SPOTS = {
    "fire-tanks": (230, 845, 190, 120, "fire", "Flicker", 1.0, 0.3, 1.5),
    "fire-tank-small": (470, 1010, 160, 130, "fire", "Flicker", 1.2, 0.3, 1.5),
    "fire-left-edge": (50, 820, 110, 160, "fire", "Flicker", 0.9, 0.2, 1.2),
    "lava-left": (230, 1235, 260, 100, "fire", "Flicker", 0.6, 0.2, 1.0),
    "lava-globe": (900, 1250, 380, 120, "fire", "Flicker", 0.7, 0.3, 1.3),
    "lava-centre": (1380, 1200, 300, 140, "fire", "Flicker", 0.8, 0.3, 1.3),
    "fire-tower": (1720, 930, 180, 130, "fire", "Flicker", 1.1, 0.3, 1.6),
    "lava-right": (1720, 1170, 220, 90, "fire", "Flicker", 0.7, 0.2, 1.0),
    "fire-crater": (2400, 1050, 190, 90, "fire", "Flicker", 1.0, 0.4, 2.0),
    "fire-far-right": (2960, 930, 200, 120, "fire", "Flicker", 0.9, 0.3, 1.8),
    "afterburner": (1530, 355, 170, 70, "fire", "Flicker", 2.6, 0.4, 1.6),
    "logo": (960, 660, 780, 360, "red", "Pulse", 0.25, 0.0, 0.45),
    "logo-shine": (960, 660, 660, 320, "shine", "Shine", 0.15, 0.0, 1.8),
    "hud-ring-left": (660, 310, 115, 115, "bright", "Pulse", 0.55, 0.0, 0.6),
    "hud-ring-right": (1270, 280, 125, 125, "bright", "Pulse", 0.45, 0.0, 0.6),
    "hud-arc": (1590, 720, 120, 420, "bright", "Pulse", 0.35, 0.05, 0.45),
    "flare-left": (270, 585, 200, 40, "bright", "Twinkle", 0.5, 0.1, 1.0),
    "flare-right": (1690, 585, 230, 40, "bright", "Twinkle", 0.4, 0.1, 1.0),
}

# Blinking red warning lights: (x, y, size, period seconds, phase)
BEACONS = {
    "tower-left": (1781, 578, 26, 1.6, 0.0),
    "tower-right": (2956, 578, 26, 1.6, 0.8),
    "tower-tanks": (421, 818, 18, 2.1, 0.3),
    "heli-tail": (102, 246, 16, 1.2, 0.5),
    "heli-belly": (346, 377, 18, 1.2, 0.0),
}

# Where embers rise from: x, y, width, height
EMBER_SOURCES = [
    (0, 780, 650, 380),
    (650, 1150, 1000, 194),
    (1600, 880, 400, 300),
    (2200, 1000, 400, 150),
    (2750, 860, 418, 200),
]

# Where distant explosions flash: x, y, width, height
FLASH_AREA = (1750, 650, 1380, 380)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def mask_for(kind, rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    sat = np.max(rgb, axis=-1) - np.min(rgb, axis=-1)
    if kind == "fire":
        return smoothstep(0.22, 0.7, r) * smoothstep(0.1, 0.35, r - b) * smoothstep(0.0, 0.2, g + 0.08)
    if kind == "red":
        return smoothstep(0.45, 0.9, r) * smoothstep(0.3, 0.6, r - g)
    if kind == "shine":
        return smoothstep(0.5, 0.85, lum)
    return smoothstep(0.3, 0.7, lum + 0.3 * sat) * smoothstep(0.2, 0.5, sat)


def ellipse_falloff(w, h, rx, ry):
    y, x = np.mgrid[0:h, 0:w]
    d = np.sqrt(((x + 0.5 - w / 2) / rx) ** 2 + ((y + 0.5 - h / 2) / ry) ** 2)
    return 1 - smoothstep(0.55, 1.0, d)


def save_rgb(arr, path):
    Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).convert("RGBA").save(path)


def make_sprites(out):
    # Soft round dot for embers, beacons and flashes (additive, white; tinted at draw time)
    n = 64
    d = ellipse_falloff(n, n, n / 2, n / 2)
    y, x = np.mgrid[0:n, 0:n]
    r = np.sqrt((x + 0.5 - n / 2) ** 2 + (y + 0.5 - n / 2) ** 2) / (n / 2)
    dot = np.clip(np.exp(-r * r * 6) * 1.2, 0, 1) * d
    save_rgb(np.dstack([dot] * 3), os.path.join(out, "dot.png"))


def build(src_path, out, image_dir, spots, beacons, ember_sources, flash_area, oy=0):
    """Write the light layers, dot sprite and manifest (<out>/<name of out>.yaml) for one piece of art.

    Positions are in src_path pixels; oy shifts them down when the art is shown padded (see make_menu_bg.py).
    image_dir is the mod path the manifest points the game at (e.g. ra|uibits/menu-fx).
    """
    os.makedirs(out, exist_ok=True)
    src = Image.open(src_path).convert("RGB")
    sw, sh = src.size
    full = np.asarray(src).astype(np.float32) / 255
    small = src.resize((round(sw * LAYER_SCALE), round(sh * LAYER_SCALE)), Image.LANCZOS)
    small = np.asarray(small).astype(np.float32) / 255

    lines = ["ImageSize: %d,%d" % (sw, sh + 2 * oy), "Layers:"]
    for name, (cx, cy, rx, ry, kind, effect, speed, lo, hi) in spots.items():
        sharp = kind == "shine"
        scale, rgb = (1.0, full) if sharp else (LAYER_SCALE, small)
        x0, y0 = max(0, cx - rx), max(0, cy - ry)
        x1, y1 = min(sw, cx + rx), min(sh, cy + ry)
        lx0, ly0 = int(x0 * scale), int(y0 * scale)
        lx1, ly1 = int(np.ceil(x1 * scale)), int(np.ceil(y1 * scale))
        crop = rgb[ly0:ly1, lx0:lx1]
        h, w = crop.shape[:2]

        # Falloff is centred on the spot, not the (possibly edge-clipped) crop
        yy, xx = np.mgrid[0:h, 0:w]
        dx = ((xx + lx0 + 0.5) / scale - cx) / rx
        dy = ((yy + ly0 + 0.5) / scale - cy) / ry
        falloff = 1 - smoothstep(0.5, 1.0, np.sqrt(dx * dx + dy * dy))

        light = crop * mask_for(kind, crop)[..., None]
        bloom = Image.fromarray((np.clip(light, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(BLOOM))
        if not sharp:
            light = light + 0.9 * np.asarray(bloom).astype(np.float32) / 255
        save_rgb(light * falloff[..., None], os.path.join(out, name + ".png"))

        lines += [
            "\t%s:" % name,
            "\t\tImage: %s/%s.png" % (image_dir, name),
            "\t\tRect: %d,%d,%d,%d" % (lx0 / scale, ly0 / scale + oy, w / scale, h / scale),
            "\t\tEffect: %s" % effect,
            "\t\tSpeed: %s" % speed,
            "\t\tMin: %s" % lo,
            "\t\tMax: %s" % hi,
        ]

    lines.append("Beacons:")
    for name, (x, y, size, period, phase) in beacons.items():
        lines += ["\t%s:" % name, "\t\tPosition: %d,%d" % (x, y + oy), "\t\tSize: %d" % size,
                  "\t\tPeriod: %s" % period, "\t\tPhase: %s" % phase]

    lines.append("EmberSources:")
    lines += ["\tsource-%d: %d,%d,%d,%d" % (i, x, y + oy, w, h) for i, (x, y, w, h) in enumerate(ember_sources)]
    fx, fy, fw, fh = flash_area
    lines.append("FlashArea: %d,%d,%d,%d" % (fx, fy + oy, fw, fh))

    with open(os.path.join(out, os.path.basename(out) + ".yaml"), "w") as f:
        f.write("\n".join(lines) + "\n")

    make_sprites(out)
    print("wrote %d layers to %s" % (len(spots), out))


def main():
    src_path = os.path.join(UIBITS, "menu-background.png")
    oy = offset_for(Image.open(src_path).size)
    build(src_path, OUT, "ra|uibits/menu-fx", SPOTS, BEACONS, EMBER_SOURCES, FLASH_AREA, oy)


if __name__ == "__main__":
    main()
