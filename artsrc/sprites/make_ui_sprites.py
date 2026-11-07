#!/usr/bin/env python3
"""
Draws our own versions of the small interface and effect sprites that still came from the original game (IDEA-31):
pips (ammo pips, control group digits, PRIMARY / READY / HOLD tags, medic cross), the build / target overlay, the
map editor's shroud edges, the observer support power clock, the move-order flash, the paradrop direction arrows,
the water crate and the concrete bibs under the forward command post and technology center.

Same frame order as the sprites they replace, so the sequences in misc.yaml / structures.yaml only change their
Filename (and Scale). Drawn at 3x and shown with `Scale: 0.3333`, except the shroud (1x, palette-indexed so the
editor's shroud and fog palettes still apply). Text uses Rajdhani Bold (SIL OFL, mods/rapx/fonts).

Writes mods/rapx/bits/hd/ui/<name>.png (frames in the PNG `Frame[i]` metadata).

  python3 artsrc/sprites/make_ui_sprites.py
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "ui")
FONT = os.path.join(ROOT, "mods", "rapx", "fonts", "Rajdhani-Bold.ttf")
WCRATE = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "env", "wcrate.png")
S = 3  # drawing scale
rng = np.random.default_rng(31)


def save_sheet(name, frames, mode="RGBA", palette=None):
    """Frames side by side; each frame's region goes into `Frame[i]` (offset 0,0 = centred like the originals)."""
    w = sum(f.width for f in frames)
    h = max(f.height for f in frames)
    sheet = Image.new(mode, (w, h))
    if palette:
        sheet.putpalette(palette)
    info = PngImagePlugin.PngInfo()
    x = 0
    for i, f in enumerate(frames):
        sheet.paste(f, (x, 0))
        info.add_text(f"Frame[{i}]", f"{x},0,{f.width},{f.height};0,0")
        x += f.width
    os.makedirs(OUT, exist_ok=True)
    if mode == "P":
        sheet.save(os.path.join(OUT, name + ".png"), pnginfo=info, transparency=0)
    else:
        sheet.save(os.path.join(OUT, name + ".png"), pnginfo=info)
    print(f"{name}.png  {len(frames)} frames")


def canvas(w, h):
    return Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))


def outlined_text(img, text, size, fill=(240, 240, 232, 255)):
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, size)
    box = d.textbbox((0, 0), text, font=font)
    x = (img.width - (box[2] - box[0])) / 2 - box[0]
    y = (img.height - (box[3] - box[1])) / 2 - box[1]
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            if dx or dy:
                d.text((x + dx, y + dy + 1), text, font=font, fill=(10, 12, 10, 235))
    d.text((x, y), text, font=font, fill=fill)
    return img


def pip(color):
    """A small bevelled lamp, centred on the 34x8 canvas of the original pips."""
    img = canvas(34, 8)
    d = ImageDraw.Draw(img)
    cx, cy, r = img.width // 2, img.height // 2, 6
    d.rectangle([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1], fill=(8, 10, 8, 255))
    d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
    light = tuple(min(255, int(c * 1.35 + 40)) for c in color)
    dark = tuple(int(c * 0.55) for c in color)
    d.line([cx - r, cy - r, cx + r, cy - r], fill=light + (255,), width=2)
    d.line([cx - r, cy - r, cx - r, cy + r], fill=light + (255,), width=2)
    d.line([cx - r, cy + r, cx + r, cy + r], fill=dark + (255,), width=2)
    d.line([cx + r, cy - r, cx + r, cy + r], fill=dark + (255,), width=2)
    return img


def pips():
    text = lambda t: outlined_text(canvas(34, 8), t, 25)
    cross = canvas(34, 8)
    d = ImageDraw.Draw(cross)
    cx, cy = cross.width // 2, cross.height // 2
    for w, col in ((9, (10, 10, 10, 255)), (5, (225, 30, 30, 255))):
        d.rectangle([cx - w, cy - 3 - w // 3, cx + w, cy + 3 + w // 3], fill=col)
        d.rectangle([cx - 3 - w // 3, cy - w, cx + 3 + w // 3, cy + w], fill=col)
    frames = [
        pip((46, 50, 46)),          # 0 empty
        pip((40, 205, 60)),         # 1 green
        text("PRIMARY"),            # 2
        text("READY"),              # 3
        text("HOLD"),               # 4
        pip((240, 170, 30)),        # 5 yellow
        pip((180, 200, 220)),       # 6 grey / blue
        pip((215, 40, 35)),         # 7 red
    ]
    frames += [text(str(i)) for i in range(10)]   # 8-17 control group digits
    frames += [text("FAKE"), text("F"), cross, text("PRI")]  # 18-21
    save_sheet("pips", frames)


def overlay():
    """Build / target placement cell: translucent diagonal stripes (white, yellow, red) and a corner frame."""
    frames = []
    for col in ((235, 235, 235), (245, 215, 40), (220, 40, 30)):
        img = canvas(24, 24)
        d = ImageDraw.Draw(img)
        for k in range(-img.height, img.width, 18):
            d.line([(k, img.height), (k + img.height, 0)], fill=col + (175,), width=6)
        frames.append(img)
    img = canvas(24, 24)
    d = ImageDraw.Draw(img)
    n, w = 18, 4
    for x0, y0, sx, sy in ((0, 0, 1, 1), (img.width - 1, 0, -1, 1), (0, img.height - 1, 1, -1),
                           (img.width - 1, img.height - 1, -1, -1)):
        d.line([(x0, y0), (x0 + sx * n, y0)], fill=(240, 240, 240, 230), width=w)
        d.line([(x0, y0), (x0, y0 + sy * n)], fill=(240, 240, 240, 230), width=w)
    frames.append(img)
    save_sheet("overlay", frames)


# Shroud palette (ShroudPalette): 0 clear, 4 black, 5 / 6 / 7 lighter shades (fog palette makes them translucent)
SHROUD_INDEX = [255, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240, 20, 40, 56, 65, 97, 130,
                148, 194, 24, 33, 66, 132, 28, 41, 67, 134, 1, 2, 4, 8, 3, 6, 12, 9, 7, 14, 13, 11, 5, 10]


def shroud():
    """46 edge frames in the order of ShroudRenderer `Index` (world.yaml). Bits: 1 TL, 2 TR, 4 BR, 8 BL corners,
    16 top, 32 right, 64 bottom, 128 left side. Darkness falls off from each shrouded side / corner with a soft,
    slightly wavy edge."""
    n = 24
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    frames = []
    for idx in SHROUD_INDEX:
        dark = np.zeros((n, n))
        wob = 1.4 * np.sin(xx * 0.55 + idx) + 1.2 * np.sin(yy * 0.6 + idx * 0.7)
        sides = {16: n - yy, 32: xx, 64: yy, 128: n - xx}       # distance into the cell from that side
        for bit, dist in sides.items():
            if idx & bit:
                dark = np.maximum(dark, np.clip(1 - (n - dist + wob) / 13.0, 0, 1))
        corners = {1: (0, 0), 2: (n, 0), 4: (n, n), 8: (0, n)}
        for bit, (cx, cy) in corners.items():
            if idx & bit:
                r = np.hypot(xx - cx, yy - cy) + wob
                dark = np.maximum(dark, np.clip(1 - r / 15.0, 0, 1))
        if idx == 255:
            dark[:] = 1
        level = np.select([dark > 0.8, dark > 0.55, dark > 0.32, dark > 0.12], [4, 5, 6, 7], 0).astype(np.uint8)
        frames.append(Image.frombytes("P", (n, n), level.tobytes()))
    pal = [0, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 40, 40, 40, 90, 90, 90, 160, 160, 160]
    save_sheet("shroud", frames, mode="P", palette=pal + [0] * (768 - len(pal)))


def clock():
    """Observer support power clock: 55 frames of a dark shutter sweeping open clockwise over a 64x48 icon."""
    frames = []
    for i in range(55):
        img = canvas(64, 48)
        d = ImageDraw.Draw(img)
        left = 1 - i / 54
        if left > 0:
            big = int(max(img.size) * 1.5)
            box = [img.width / 2 - big, img.height / 2 - big, img.width / 2 + big, img.height / 2 + big]
            d.pieslice(box, -90 + 360 * (1 - left), 270, fill=(0, 0, 0, 150))
        frames.append(img)
    save_sheet("clock", frames)


def moveflsh():
    """Move-order flash: a cyan hologram ring expanding and fading (5 frames), the same on every tileset."""
    frames = []
    for i in range(5):
        img = canvas(24, 24)
        d = ImageDraw.Draw(img)
        r = 6 + i * 7.5
        a = int(255 * (1 - i / 5.5))
        cx, cy = img.width / 2, img.height / 2
        for k, (dr, w, al) in enumerate(((0, 6, a), (3, 2, a // 3))):
            d.ellipse([cx - r - dr, cy - (r - dr) * 0.7 - dr * 0.3, cx + r + dr, cy + (r - dr) * 0.7 + dr * 0.3],
                      outline=(80, 230, 255, al), width=w)
        if i == 4:
            d.ellipse([cx - 4, cy - 3, cx + 4, cy + 3], fill=(80, 230, 255, 150))
        frames.append(img.filter(ImageFilter.GaussianBlur(0.6)))
    save_sheet("moveflsh", frames)


def arrows():
    """Paradrop direction arrows: frames 1-8 = up, up-right, right, down-right, down, down-left, left, up-left
    (frame 0 is unused but kept so Start values stay the same)."""
    base = canvas(30, 24)
    d = ImageDraw.Draw(base)
    cx, cy = base.width / 2, base.height / 2
    pts = [(0, -27), (21, -3), (8, -3), (8, 24), (-8, 24), (-8, -3), (-21, -3)]
    shadow = [(cx + x + 3, cy + y + 3) for x, y in pts]
    d.polygon(shadow, fill=(0, 0, 0, 120))
    d.polygon([(cx + x, cy + y) for x, y in pts], fill=(8, 10, 8, 255))
    inner = [(x * 0.8, y * 0.8 + 1) for x, y in pts]
    d.polygon([(cx + x, cy + y) for x, y in inner], fill=(245, 240, 225, 255))
    frames = [canvas(30, 24)]
    for k in range(8):
        frames.append(base.rotate(-45 * k, resample=Image.BICUBIC))
    save_sheet("paradirection", frames)


def wcrate_water():
    """Crate floating on water: our HD crate (hd/env/wcrate.png, first frame) bobbing in a ripple ring."""
    crate = Image.open(WCRATE).convert("RGBA")  # single 36x37 frame, same 3x density
    frames = []
    for i in range(4):
        img = canvas(24, 24)
        d = ImageDraw.Draw(img)
        cx, cy = img.width / 2, img.height / 2 + 6
        for k in range(3):
            r = 18 + ((i * 5 + k * 6) % 17)
            a = int(170 * (1 - (r - 18) / 17))
            d.ellipse([cx - r, cy - r * 0.55, cx + r, cy + r * 0.55], outline=(200, 225, 255, a), width=2)
        bob = int(2 * math.sin(i * math.pi / 2))
        img.alpha_composite(crate, (int(cx - crate.width / 2), int(cy - crate.height * 0.8 + bob)))
        frames.append(img)
    save_sheet("wcrate-water", frames)


def bib(cols, rows, terrain):
    """Concrete foundation under a building, one 24x24 frame per cell (row-major), like the classic bib tiles."""
    base = {"temperate": (128, 126, 118), "snow": (176, 180, 186), "desert": (170, 150, 118)}[terrain]
    W, H = cols * 24 * S, rows * 24 * S
    slab = np.zeros((H, W, 4), np.float32)
    noise = rng.normal(0, 7, (H, W))
    k = np.ones(5) / 5
    noise = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, noise)
    noise = np.apply_along_axis(lambda c: np.convolve(c, k, "same"), 0, noise)
    for c in range(3):
        slab[..., c] = base[c] + noise
    slab[..., 3] = 255
    img = Image.fromarray(np.clip(slab, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # expansion joints between the slabs, a darker border and worn corners
    for x in range(24 * S, W, 24 * S):
        d.line([(x, 0), (x, H)], fill=tuple(int(v * 0.72) for v in base) + (255,), width=2)
    for y in range(24 * S, H, 24 * S):
        d.line([(0, y), (W, y)], fill=tuple(int(v * 0.72) for v in base) + (255,), width=2)
    d.rectangle([0, 0, W - 1, H - 1], outline=tuple(int(v * 0.6) for v in base) + (255,), width=5)
    a = np.array(img)
    yy, xx = np.mgrid[0:H, 0:W]
    edge = np.minimum.reduce([xx, yy, W - 1 - xx, H - 1 - yy]).astype(np.float32)
    rough = edge + rng.normal(0, 2.2, edge.shape)
    a[..., 3] = np.where(rough < 2.5, 0, 255).astype(np.uint8)
    img = Image.fromarray(a)
    frames = [img.crop((c * 24 * S, r * 24 * S, (c + 1) * 24 * S, (r + 1) * 24 * S))
              for r in range(rows) for c in range(cols)]
    return frames


def bibs():
    for name, (cols, rows) in (("bib2", (3, 2)), ("bib3", (2, 2))):
        for terrain in ("temperate", "snow", "desert"):
            save_sheet(f"{name}-{terrain}", bib(cols, rows, terrain))


def main():
    pips()
    overlay()
    shroud()
    clock()
    moveflsh()
    arrows()
    wcrate_water()
    bibs()


if __name__ == "__main__":
    main()
