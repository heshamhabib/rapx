#!/usr/bin/env python3
"""
Lobby art for the TITAN column and the "Choose your titan" picker (OpenRA.Mods.RAPX/Widgets/PxTitanWidgets.cs).

Input: the hero renders from render_titan.py (`Blender -b -P artsrc/units/meshes/render_titan.py -- <titan> x art`):
artsrc/px-ui/titans/<titan>-{banner,portrait}.png, transparent. Each titan is staged on a dark backdrop with a glow in
its colour (Godzilla's breath pink, Kong's ember amber), drifting embers and a vignette; "none" and "random" get
drawn emblems in the same frame.

Output: mods/rapx/uibits/px-titans{,-2x,-3x}.png and mods/rapx/px-titans.yaml (image collection "px-titans"):
  portrait-<id>  72x48   row button and small picker cards (ids: godzilla, kong, none, random = the lobby ids)
  banner-<id>    296x120 the big picker cards (titans only)

  python3 artsrc/px-ui/make_titan_art.py
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MOD = os.path.join(ROOT, "mods", "rapx")
SRC = os.path.join(HERE, "titans")
FONT = os.path.join(MOD, "fonts", "Rajdhani-Bold.ttf")

# lobby id -> (render name, glow colour, brighten)
TITANS = {"godzilla": ("godz", (255, 60, 200), 1.0), "kong": ("kong", (255, 150, 50), 1.25)}
PORTRAIT = (72, 48)
BANNER = (296, 120)
SHEET = (512, 256)
SCALES = (1, 2, 3)


def backdrop(size, glow, centre=(0.62, 0.55), seed=1):
    """Dark gradient, a soft glow in the titan's colour behind it, faint haze bands and embers, vignette."""
    w, h = size
    img = Image.new("RGBA", size, (11, 12, 16, 255))
    px = img.load()
    cx, cy = centre[0] * w, centre[1] * h
    r = max(w, h) * 0.62
    for y in range(h):
        for x in range(w):
            d = math.hypot((x - cx) / r, (y - cy) / (r * 0.8))
            g = max(0.0, 1.0 - d) ** 1.8
            base = 14 + 10 * (1 - y / h)
            px[x, y] = (int(base + glow[0] * 0.55 * g), int(base + glow[1] * 0.55 * g), int(base + 4 + glow[2] * 0.55 * g), 255)
    rnd = random.Random(seed)
    haze = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(haze)
    for _ in range(6):
        y = rnd.uniform(0.3, 0.95) * h
        d.ellipse([rnd.uniform(-0.3, 0.5) * w, y - h * 0.06, rnd.uniform(0.6, 1.3) * w, y + h * 0.06],
                  fill=(*glow, 18))
    img.alpha_composite(haze.filter(ImageFilter.GaussianBlur(h * 0.05)))
    embers = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(embers)
    for _ in range(int(w * h / 3200 * (300 / w) ** 2 * (w / 300) ** 2)):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h) ** 1.0
        s = rnd.uniform(0.25, 0.8) * w / 300
        a = int(rnd.uniform(40, 170) * (0.35 + 0.65 * y / h))
        d.ellipse([x - s, y - s, x + s, y + s], fill=(255, min(255, glow[1] + 120), min(255, glow[2] + 80), a))
    img.alpha_composite(embers.filter(ImageFilter.GaussianBlur(w / 900)))
    return img


def vignette(img, strength=0.55):
    w, h = img.size
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) * 0.18))
    dark = Image.new("RGBA", img.size, (4, 4, 6, int(255 * strength)))
    out = img.copy()
    out.alpha_composite(Image.composite(Image.new("RGBA", img.size, (0, 0, 0, 0)), dark, mask))
    return out


def stage(figure, size, glow, brighten, anchor="right", fill=0.98, seed=1):
    """The figure on its backdrop: a coloured rim of light around its silhouette, a contact shadow, bottom fade."""
    w, h = size
    fig = figure.crop(figure.getbbox())
    if brighten != 1.0:
        rgb = ImageEnhance.Brightness(fig.convert("RGB")).enhance(brighten)
        rgb = ImageEnhance.Contrast(rgb).enhance(1.08)
        fig = Image.merge("RGBA", (*rgb.split(), fig.getchannel("A")))
    scale = min(h * fill / fig.height, w * (0.62 if anchor == "right" else 0.92) / fig.width)
    fig = fig.resize((max(1, int(fig.width * scale)), max(1, int(fig.height * scale))), Image.LANCZOS)
    x = w - fig.width - int(w * 0.03) if anchor == "right" else (w - fig.width) // 2
    y = h - fig.height
    img = backdrop(size, glow, centre=((x + fig.width * 0.5) / w, 0.5), seed=seed)
    # rim glow: the silhouette blurred in the titan's colour behind the figure
    sil = Image.new("RGBA", size, (0, 0, 0, 0))
    tint = Image.new("RGBA", fig.size, (*glow, 255))
    sil.paste(tint, (x, y), fig.getchannel("A"))
    img.alpha_composite(sil.filter(ImageFilter.GaussianBlur(max(2, h * 0.035))))
    img.alpha_composite(fig, (x, y))
    # fade the bottom into the card so text sits on dark
    fade = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(fade)
    for i in range(int(h * 0.45)):
        a = int(200 * (i / (h * 0.45)) ** 1.6)
        d.line([(0, h - int(h * 0.45) + i), (w, h - int(h * 0.45) + i)], fill=(8, 8, 11, a))
    img.alpha_composite(fade)
    return vignette(img, 0.45)


def emblem(size, kind):
    """None: an empty titan slot (a struck-through ring). Random: a question mark lit pink and amber."""
    w, h = size
    img = backdrop(size, (120, 122, 135) if kind == "none" else (220, 110, 140), centre=(0.5, 0.5), seed=7)
    d = ImageDraw.Draw(img)
    cx, cy, r = w / 2, h / 2, h * 0.3
    if kind == "none":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(150, 152, 162, 255), width=max(2, int(h * 0.05)))
        d.line([(cx - r * 0.7, cy + r * 0.7), (cx + r * 0.7, cy - r * 0.7)], fill=(150, 152, 162, 255), width=max(2, int(h * 0.05)))
    else:
        font = ImageFont.truetype(FONT, int(h * 0.82))
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((cx, cy), "?", font=font, anchor="mm", fill=(255, 90, 190, 255))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(h * 0.08)))
        d.text((cx, cy), "?", font=font, anchor="mm", fill=(255, 214, 160, 255))
    return vignette(img, 0.5)


def frame(img):
    """A thin light edge on top and a dark keyline, like the nation flags' cards."""
    d = ImageDraw.Draw(img)
    w, h = img.size
    k = max(1, round(w / PORTRAIT[0] if w <= PORTRAIT[0] * 3 else w / BANNER[0]))
    d.rectangle([0, 0, w - 1, h - 1], outline=(0, 0, 0, 255), width=k)
    d.line([(k, k), (w - 1 - k, k)], fill=(255, 255, 255, 60), width=k)
    return img


def main():
    pieces = {}  # name -> (scale -> image)
    for scale in SCALES:
        pw, ph = PORTRAIT[0] * scale, PORTRAIT[1] * scale
        bw, bh = BANNER[0] * scale, BANNER[1] * scale
        for tid, (render, glow, brighten) in TITANS.items():
            portrait = Image.open(os.path.join(SRC, f"{render}-portrait.png")).convert("RGBA")
            banner = Image.open(os.path.join(SRC, f"{render}-banner.png")).convert("RGBA")
            pieces.setdefault(f"portrait-{tid}", {})[scale] = frame(stage(portrait, (pw, ph), glow, brighten, "center", 1.0, seed=3))
            pieces.setdefault(f"banner-{tid}", {})[scale] = frame(stage(banner, (bw, bh), glow, brighten, "right", 0.97, seed=5))
        for kind in ("none", "random"):
            pieces.setdefault(f"portrait-{kind}", {})[scale] = frame(emblem((pw, ph), kind))

    # Column header icon: Godzilla's silhouette in the header grey, like the other px-lobby-icons
    sil = Image.open(os.path.join(SRC, "godz-banner.png")).convert("RGBA")
    sil = sil.crop(sil.getbbox())
    for scale in SCALES:
        size = 16 * scale
        a = sil.getchannel("A")
        k = min(size / a.width, size / a.height)
        a = a.resize((max(1, int(a.width * k)), max(1, int(a.height * k))), Image.LANCZOS)
        icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        icon.paste(Image.new("RGBA", a.size, (157, 158, 166, 255)), ((size - a.width) // 2, (size - a.height) // 2), a)
        pieces.setdefault("col-titan", {})[scale] = icon

    # Layout (1x units): portraits stacked on the left, banners on the right
    regions, x, y = {}, 0, 0
    for name in ("portrait-godzilla", "portrait-kong", "portrait-none", "portrait-random"):
        regions[name] = (0, y, *PORTRAIT)
        y += PORTRAIT[1] + 2
    regions["col-titan"] = (0, y, 16, 16)
    y = 0
    for name in ("banner-godzilla", "banner-kong"):
        regions[name] = (PORTRAIT[0] + 4, y, *BANNER)
        y += BANNER[1] + 2

    for scale in SCALES:
        sheet = Image.new("RGBA", (SHEET[0] * scale, SHEET[1] * scale), (0, 0, 0, 0))
        for name, (rx, ry, rw, rh) in regions.items():
            sheet.paste(pieces[name][scale], (rx * scale, ry * scale))
        suffix = "" if scale == 1 else f"-{scale}x"
        sheet.save(os.path.join(MOD, "uibits", f"px-titans{suffix}.png"))

    lines = ["# GENERATED by artsrc/px-ui/make_titan_art.py - edit that script, not this file.", "px-titans:",
             "\tImage: px-titans.png", "\tImage2x: px-titans-2x.png", "\tImage3x: px-titans-3x.png", "\tRegions:"]
    lines += [f"\t\t{name}: {rx}, {ry}, {rw}, {rh}" for name, (rx, ry, rw, rh) in regions.items()]
    open(os.path.join(MOD, "px-titans.yaml"), "w").write("\n".join(lines) + "\n")
    print("wrote", len(regions), "titan art regions")


if __name__ == "__main__":
    main()
