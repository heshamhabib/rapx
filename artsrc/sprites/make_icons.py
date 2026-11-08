#!/usr/bin/env python3
"""
Draws the support power icons, the crate pickup effects and the GPS satellite launch (IDEA-31) from game-icons.net
symbols (artsrc/sprites/icons/source/*.svg, CC BY 3.0 by Lorc and Delapouite, credited in mods/rapx/CREDITS).

- Support power icons: the symbol in the power's colour, glowing on a dark steel panel with a faint grid (the
  PxSupportPowers launch panels scale them to fit). 64x48 like the originals, drawn at 4x.
- Crate effects: the symbol grows out of the crate with a glow, then bursts into a fading ring.
- GPS launch (`sputnik`): the rocket symbol upright with a flickering exhaust flame.

Needs rsvg-convert (`brew install librsvg`). Writes mods/rapx/bits/hd/ui/<name>.png.

  python3 artsrc/sprites/make_icons.py
"""
import io
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_ui_sprites as ui

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "icons", "source")

# sequence name -> (symbol, colour)
POWERS = {
    "abomb": ("mushroom-cloud", (255, 120, 40)),
    "invuln": ("energy-shield", (235, 50, 45)),
    "chrono": ("teleport", (90, 170, 255)),
    "spyplane": ("jet-fighter", (170, 200, 220)),
    "paratroopers": ("parachute", (120, 220, 90)),
    "gps": ("satellite", (60, 230, 230)),
    "parabombs": ("bombing-run", (255, 170, 40)),
    "sonar": ("radar-sweep", (70, 240, 140)),
    "fatman": ("falling-bomb", (255, 205, 60)),  # USA Fatman bomber strike (rules/fatman.yaml)
    "rds37": ("radioactive", (255, 70, 50)),  # Russia's thermonuclear strike (rules/fatman.yaml SBMB)
}
# crate effect sequence -> (symbol, colour, frames)
CRATES = {
    "reveal-map": ("world", (90, 200, 255), 10),
    "hide-map": ("invisible", (190, 120, 255), 19),
    "invuln": ("edged-shield", (255, 210, 60), 15),
}


def symbol(name, size, rotate=0):
    """White symbol on transparent, `size` pixels square (game-icons draw on a black 512 square; drop it)."""
    svg = open(os.path.join(SRC, name + ".svg")).read().replace('<path d="M0 0h512v512H0z"/>', "")
    png = subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size)], input=svg.encode(),
                         capture_output=True, check=True).stdout
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    return img.rotate(rotate, resample=Image.BICUBIC) if rotate else img


def tint(img, color, alpha=1.0):
    a = np.array(img).astype(np.float32)
    out = np.zeros_like(a)
    out[..., :3] = color
    out[..., 3] = a[..., 3] * alpha
    return Image.fromarray(out.astype(np.uint8))


def glow(img, color, radius, strength=1.0):
    g = tint(img, color, strength).filter(ImageFilter.GaussianBlur(radius))
    out = Image.new("RGBA", img.size)
    out.alpha_composite(g)
    out.alpha_composite(g)
    return out


def power_icon(sym, color):
    W, H = 256, 192
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img)
    # dark steel panel: vertical gradient, faint grid, inner bevel
    for y in range(H):
        v = int(30 - 14 * y / H)
        d.line([(0, y), (W, y)], fill=(v, v + 3, v + 2, 255))
    for x in range(0, W, 16):
        d.line([(x, 0), (x, H)], fill=(color[0] // 6, color[1] // 6, color[2] // 6, 255))
    for y in range(0, H, 16):
        d.line([(0, y), (W, y)], fill=(color[0] // 6, color[1] // 6, color[2] // 6, 255))
    vign = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vign).ellipse([-W * 0.2, -H * 0.3, W * 1.2, H * 1.3], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(40))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 200))
    dark.putalpha(Image.eval(vign, lambda v: 200 - v * 200 // 255))
    img.alpha_composite(dark)
    s = symbol(sym, 150)
    pos = ((W - 150) // 2, (H - 150) // 2)
    layer = Image.new("RGBA", (W, H))
    layer.alpha_composite(glow(s, color, 10), pos)
    img.alpha_composite(layer)
    lit = tint(s, tuple(min(255, int(c * 0.55 + 120)) for c in color))
    img.alpha_composite(lit, pos)
    d.rectangle([0, 0, W - 1, H - 1], outline=(110, 115, 110, 255), width=3)
    d.rectangle([3, 3, W - 4, H - 4], outline=(10, 12, 10, 255), width=2)
    return img


def crate_effect(sym, color, n):
    """Symbol rises and grows over the first 60% of the frames, then bursts into an expanding, fading ring."""
    size = 24 * ui.S
    frames = []
    for i in range(n):
        t = i / (n - 1)
        img = Image.new("RGBA", (size, size))
        grow = min(1.0, t / 0.6)
        scale = 0.25 + 0.75 * (1 - (1 - grow) ** 2)
        fade = 1.0 if t < 0.6 else max(0.0, 1 - (t - 0.6) / 0.4)
        sz = max(4, int(size * 0.8 * scale))
        s = symbol(sym, sz)
        pos = ((size - sz) // 2, (size - sz) // 2 - int(6 * grow))
        layer = Image.new("RGBA", (size, size))
        layer.alpha_composite(glow(s, color, 3, fade), pos)
        layer.alpha_composite(tint(s, tuple(min(255, c + 70) for c in color), fade), pos)
        img.alpha_composite(layer)
        if t >= 0.6:
            r = size * (0.3 + 0.55 * (t - 0.6) / 0.4)
            ring = Image.new("RGBA", (size, size))
            ImageDraw.Draw(ring).ellipse([size / 2 - r, size / 2 - r * 0.8, size / 2 + r, size / 2 + r * 0.8],
                                         outline=color + (int(220 * fade),), width=3)
            img.alpha_composite(ring.filter(ImageFilter.GaussianBlur(0.8)))
        frames.append(img)
    return frames


def sputnik():
    """GPS satellite launch: upright rocket with a flickering flame, 4 frames on the original 24x72 canvas."""
    W, H = 24 * ui.S, 72 * ui.S
    rocket = symbol("rocket", 90, rotate=-45)
    rocket = rocket.crop(rocket.getbbox())
    rocket = tint(rocket, (235, 238, 240))
    rng = np.random.default_rng(5)
    frames = []
    for i in range(4):
        img = Image.new("RGBA", (W, H))
        top = 12
        img.alpha_composite(rocket, ((W - rocket.width) // 2, top))
        fl = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(fl)
        y0 = top + rocket.height - 6
        ln = 70 + rng.integers(-12, 14)
        for w, col in ((16, (255, 120, 30, 200)), (10, (255, 220, 120, 230)), (5, (255, 255, 240, 255))):
            d.polygon([(W / 2 - w, y0), (W / 2 + w, y0), (W / 2 + rng.uniform(-3, 3), y0 + ln * w / 16)], fill=col)
        img.alpha_composite(fl.filter(ImageFilter.GaussianBlur(2)))
        frames.append(img)
    return frames


def main():
    for name, (sym, color) in POWERS.items():
        ui.save_sheet(f"icon-{name}", [power_icon(sym, color)])
    for name, (sym, color, n) in CRATES.items():
        ui.save_sheet(f"crate-{name}", crate_effect(sym, color, n))
    ui.save_sheet("sputnik", sputnik())


if __name__ == "__main__":
    main()
