#!/usr/bin/env python3
"""Builds the flag chrome collections.

- `flags` (mods/rapx/uibits/px-flags{,-2x,-3x}.png): 30x15 flags with a 1px border in the side colour.
  Column 0 keeps the stock RA slot order, column 1 holds the RAPX-only countries. Every country is drawn
  here; only the `allies` / `soviet` side emblems are still copied from glyphs*.png.
- `flags-large` (mods/rapx/uibits/px-flags-large{,-2x,-3x}.png): 64x32 flags for the lobby nation picker.
  Its regions are written to mods/rapx/px-flags-large.yaml.

Countries use their current national flags (Russia white/blue/red, Ukraine blue/yellow, England's
St George's Cross) rendered from the public domain SVGs in svg/ (see svg/SOURCE.md) with rsvg-convert.
Only the random "?" flags are drawn here.
"""
import io
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "mods", "rapx", "uibits")
MOD = os.path.join(ROOT, "..")
STOCK = ["england", "germany", "france", "spain", "turkey", "greece", "ukraine", "russia",
         "allies", "soviet", "RandomSoviet", "RandomAllies", "Random"]
ALLIED_BORDER = (89, 144, 255, 255)
SOVIET_BORDER = (191, 0, 0, 255)
SS = 24  # supersample: pixels per 1x flag pixel when drawing

def random_flag(fill):
    def draw(d, w, h):
        d.rectangle([0, 0, w, h], fill=fill)
        font = ImageFont.truetype(os.path.join(MOD, "fonts", "Rajdhani-Bold.ttf"), int(h * 1.05))
        box = d.textbbox((0, 0), "?", font=font)
        d.text(((w - (box[2] - box[0])) / 2 - box[0], (h - (box[3] - box[1])) / 2 - box[1]), "?", font=font, fill=(255, 255, 255))
    return draw

NEW = [("egypt", ALLIED_BORDER), ("cuba", SOVIET_BORDER), ("india", SOVIET_BORDER), ("pakistan", SOVIET_BORDER),
       ("china", SOVIET_BORDER), ("japan", ALLIED_BORDER), ("southkorea", ALLIED_BORDER), ("italy", ALLIED_BORDER),
       ("usa", ALLIED_BORDER), ("iran", SOVIET_BORDER)]

SVG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")
SVG = {"england": "gb-eng", "france": "fr", "germany": "de", "spain": "es", "turkey": "tr", "greece": "gr",
       "pakistan": "pk", "russia": "ru", "ukraine": "ua", "cuba": "cu", "india": "in", "egypt": "eg",
       "china": "cn", "japan": "jp", "southkorea": "kr", "italy": "it", "usa": "us", "iran": "ir"}
SIDE = {"england": ALLIED_BORDER, "france": ALLIED_BORDER, "germany": ALLIED_BORDER, "spain": ALLIED_BORDER,
        "turkey": SOVIET_BORDER, "greece": ALLIED_BORDER, "pakistan": SOVIET_BORDER, "russia": SOVIET_BORDER,
        "ukraine": SOVIET_BORDER, "cuba": SOVIET_BORDER, "india": SOVIET_BORDER, "egypt": ALLIED_BORDER,
        "china": SOVIET_BORDER, "japan": ALLIED_BORDER, "southkorea": ALLIED_BORDER, "italy": ALLIED_BORDER, "usa": ALLIED_BORDER, "iran": SOVIET_BORDER}
RANDOM = {"RandomSoviet": ((150, 18, 18), SOVIET_BORDER), "RandomAllies": ((28, 64, 150), ALLIED_BORDER),
          "Random": ((70, 71, 80), (120, 120, 128, 255))}
LARGE = ["england", "france", "germany", "spain", "turkey", "greece", "pakistan", "russia", "ukraine",
         "cuba", "india", "egypt", "china", "japan", "southkorea", "italy", "usa", "iran", "Random", "RandomAllies", "RandomSoviet"]

def svg_image(code, w, h):
    """Render a flag SVG to cover w x h (cropping the long side, keeping the centre)."""
    png = subprocess.run(["rsvg-convert", "-h", str(h * 2), os.path.join(SVG_DIR, code + ".svg")],
                         check=True, capture_output=True).stdout
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    scale = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * scale)), max(h, round(img.height * scale))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))

def flag_image(name, w, h):
    if name in SVG:
        return svg_image(SVG[name], w, h)
    if name in RANDOM:
        big = Image.new("RGBA", (w * 4, h * 4))
        random_flag(RANDOM[name][0])(ImageDraw.Draw(big), big.width, big.height)
        return big.resize((w, h), Image.LANCZOS)
    return None

def render(name, border, scale, w=30, h=15, b=1):
    out = Image.new("RGBA", (w * scale, h * scale), border)
    out.paste(flag_image(name, (w - 2 * b) * scale, (h - 2 * b) * scale), (b * scale, b * scale))
    return out

def main():
    for scale, suffix, size in [(1, "", (64, 256)), (2, "-2x", (128, 512)), (3, "-3x", (256, 1024))]:
        glyphs = Image.open(os.path.join(ROOT, f"glyphs{suffix}.png")).convert("RGBA")
        sheet = Image.new("RGBA", size)
        for i, name in enumerate(STOCK):
            if name in SVG or name in RANDOM:
                border = SIDE[name] if name in SVG else RANDOM[name][1]
                sheet.paste(render(name, border, scale), (0, 16 * i * scale))
            else:
                box = (226 * scale, (49 + 16 * i) * scale, 256 * scale, (64 + 16 * i) * scale)
                sheet.paste(glyphs.crop(box), (0, 16 * i * scale))
        for i, (name, border) in enumerate(NEW):
            sheet.paste(render(name, border, scale), (32 * scale, 16 * i * scale))
        sheet.save(os.path.join(ROOT, f"px-flags{suffix}.png"))

    # Large flags: 60x40 (3:2, the shape of most national flags) in one column, with a dark 1px frame
    for scale, suffix in [(1, ""), (2, "-2x"), (3, "-3x")]:
        sheet = Image.new("RGBA", (64 * scale, 1024 * scale))
        for i, name in enumerate(LARGE):
            sheet.paste(render(name, (12, 12, 15, 255), scale, 60, 40, 1), (0, 41 * i * scale))
        sheet.save(os.path.join(ROOT, f"px-flags-large{suffix}.png"))

    with open(os.path.join(MOD, "px-flags-large.yaml"), "w") as f:
        f.write("# GENERATED by artsrc/px-flags/generate.py - edit that script, not this file.\n")
        f.write("flags-large:\n\tImage: px-flags-large.png\n\tImage2x: px-flags-large-2x.png\n\tImage3x: px-flags-large-3x.png\n\tRegions:\n")
        for i, name in enumerate(LARGE):
            f.write(f"\t\t{name}: 0, {41 * i}, 60, 40\n")

    print("flags:\n\tImage: px-flags.png\n\tImage2x: px-flags-2x.png\n\tImage3x: px-flags-3x.png\n\tRegions:")
    for i, n in enumerate(STOCK):
        print(f"\t\t{n}: 0, {16 * i}, 30, 15")
    for i, (n, _) in enumerate(NEW):
        print(f"\t\t{n}: 32, {16 * i}, 30, 15")

if __name__ == "__main__":
    main()
