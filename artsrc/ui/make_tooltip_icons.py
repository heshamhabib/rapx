#!/usr/bin/env python3
"""
HD glyphs for the production tooltip (PxWeaponLoadoutWidget, PxTooltipDescWidget).

  python3 artsrc/ui/make_tooltip_icons.py

Writes mods/rapx/bits/hd/ui/tooltip-icons.png: one 64x64 cell per glyph, in the order of NAMES (the widgets look
cells up by that index, so append new glyphs at the end). Glyphs are white with a soft dark rim baked in, so the
widget can tint them (multiply) and they still read on any plate. Drawn as vector shapes at 4x and downsampled.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "ui", "tooltip-icons.png")
CELL = 64
SS = 4
S = CELL * SS        # drawing canvas
COLS = 8

# Keep in sync with PxTooltipIcons.Names (OpenRA.Mods.RAPX/Widgets/PxTooltipIcons.cs)
NAMES = [
    "smallarms", "cannon", "artillery", "grenade", "missile", "bombs", "atomic", "beam",
    "tesla", "flame", "torpedo", "incendiary", "marker", "airdefence", "ciws", "support",
    "infantry", "light", "heavy", "building", "aircraft", "ship", "range", "damage",
    "reload", "strong", "weak", "rounds", "dps",
]


def P(*pts):
    """Points in a 0..100 design grid -> canvas pixels."""
    return [(x * S / 100, y * S / 100) for x, y in pts]


def R(x0, y0, x1, y1):
    return [x0 * S / 100, y0 * S / 100, x1 * S / 100, y1 * S / 100]


def W(w):
    return max(1, int(w * S / 100))


def rot(points, angle, cx=50, cy=50):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in points]


def shell(d, cx, cy, length, width, angle, fill=255):
    """A pointed round: body + ogive nose + base band."""
    h = width / 2
    body = [(cx - length / 2, cy - h), (cx + length * 0.15, cy - h), (cx + length / 2, cy), (cx + length * 0.15, cy + h),
            (cx - length / 2, cy + h)]
    d.polygon(P(*rot(body, angle, cx, cy)), fill=fill)
    band = [(cx - length / 2, cy - h - 1.5), (cx - length / 2 + 5, cy - h - 1.5), (cx - length / 2 + 5, cy + h + 1.5),
            (cx - length / 2, cy + h + 1.5)]
    d.polygon(P(*rot(band, angle, cx, cy)), fill=fill)


def g_smallarms(d):
    # Assault rifle in profile: stock, receiver, magazine, barrel
    d.polygon(P((8, 46), (30, 42), (34, 38), (74, 38), (74, 46), (40, 48), (36, 52), (14, 60), (8, 56)), fill=255)
    d.rectangle(R(74, 40, 94, 44), fill=255)
    d.polygon(P((46, 47), (56, 47), (60, 66), (52, 68)), fill=255)
    d.polygon(P((36, 48), (42, 48), (40, 60), (34, 60)), fill=255)
    d.rectangle(R(44, 32, 62, 36), fill=255)


def g_cannon(d):
    shell(d, 50, 50, 70, 22, -35)


def g_artillery(d):
    # A shell high on a dotted ballistic arc
    for i in range(7):
        t = i / 6
        x = 10 + 70 * t
        y = 82 - 120 * t * (1 - t) - 12 * t
        r = 2.4
        d.ellipse(R(x - r, y - r, x + r, y + r), fill=255)
    shell(d, 72, 40, 40, 14, 30)
    d.rectangle(R(6, 86, 94, 90), fill=255)


def g_grenade(d):
    d.ellipse(R(26, 34, 70, 86), fill=255)
    d.rectangle(R(40, 22, 56, 36), fill=255)
    d.polygon(P((56, 24), (80, 30), (78, 36), (56, 32)), fill=255)
    d.ellipse(R(62, 12, 76, 26), outline=255, width=W(3.5))
    for y in (50, 62, 74):
        d.line(P((28, y), (68, y)), fill=0, width=W(2.5))


def g_missile(d):
    body = [(12, 46), (68, 46), (88, 50), (68, 54), (12, 54)]
    fins = [(12, 46), (24, 46), (14, 34), (8, 34)], [(12, 54), (24, 54), (14, 66), (8, 66)]
    canards = [(54, 46), (60, 46), (56, 40)], [(54, 54), (60, 54), (56, 60)]
    for poly in [body, *fins, *canards]:
        d.polygon(P(*rot(poly, -30)), fill=255)
    for i, (x, y, r) in enumerate([(12, 76, 7), (22, 84, 5), (6, 88, 4)]):
        d.ellipse(R(x - r, y - r, x + r, y + r), fill=255)


def g_bombs(d):
    for cx, cy in ((34, 44), (66, 58)):
        d.ellipse(R(cx - 13, cy - 20, cx + 13, cy + 20), fill=255)
        d.polygon(P((cx - 11, cy - 16), (cx + 11, cy - 16), (cx + 14, cy - 32), (cx - 14, cy - 32)), fill=255)
        d.line(P((cx - 14, cy - 32), (cx + 14, cy - 32)), fill=255, width=W(3))
    for x in (34, 66):
        d.line(P((x - 6, 86), (x + 6, 86)), fill=255, width=W(3))


def g_atomic(d):
    d.ellipse(R(40, 40, 60, 60), fill=255)
    for a in (90, 210, 330):
        pts = [(50, 50)]
        for k in range(13):
            ang = math.radians(a - 30 + 60 * k / 12)
            pts.append((50 + 40 * math.cos(ang), 50 - 40 * math.sin(ang)))
        d.polygon(P(*pts), fill=255)
    d.ellipse(R(34, 34, 66, 66), outline=0, width=W(4))


def g_beam(d):
    d.polygon(P((6, 44), (30, 40), (30, 60), (6, 56)), fill=255)
    d.polygon(P((30, 46), (94, 48), (94, 52), (30, 54)), fill=255)
    for a in (0, 45, 90, 135):
        x, y = 86, 50
        dx, dy = 12 * math.cos(math.radians(a)), 12 * math.sin(math.radians(a))
        d.line(P((x - dx, y - dy), (x + dx, y + dy)), fill=255, width=W(3))


def g_tesla(d):
    d.polygon(P((60, 6), (24, 54), (46, 54), (34, 94), (78, 40), (54, 40), (70, 6)), fill=255)


def g_flame(d):
    d.polygon(P((50, 6), (64, 30), (78, 26), (82, 56), (72, 82), (50, 94), (28, 82), (18, 58), (24, 34), (36, 44), (40, 20)), fill=255)
    d.polygon(P((50, 50), (60, 64), (58, 80), (50, 86), (42, 80), (40, 66)), fill=0)


def g_torpedo(d):
    d.rounded_rectangle(R(10, 42, 82, 58), radius=W(8), fill=255)
    d.polygon(P((82, 44), (92, 50), (82, 56)), fill=255)
    d.polygon(P((10, 50), (2, 38), (8, 38), (18, 46)), fill=255)
    d.polygon(P((10, 50), (2, 62), (8, 62), (18, 54)), fill=255)
    for i, x in enumerate((26, 40, 56)):
        d.arc(R(x - 8, 62, x + 8, 78), 0, 180, fill=255, width=W(3))


def g_incendiary(d):
    d.ellipse(R(36, 6, 64, 34), fill=255)
    d.line(P((50, 34), (50, 46)), fill=255, width=W(3))
    d.polygon(P((50, 48), (62, 64), (70, 62), (72, 80), (60, 94), (40, 94), (28, 80), (30, 62), (38, 66)), fill=255)


def g_marker(d):
    # Smoke canister on its side with a billowing plume (Red Smoke)
    d.rounded_rectangle(R(10, 70, 46, 86), radius=W(4), fill=255)
    d.rectangle(R(22, 70, 30, 86), fill=0)
    for x, y, r in ((52, 70, 10), (62, 56, 13), (74, 40, 15), (58, 36, 11), (82, 22, 12), (68, 18, 9)):
        d.ellipse(R(x - r, y - r, x + r, y + r), fill=255)


def g_airdefence(d):
    d.ellipse(R(14, 14, 86, 86), outline=255, width=W(4))
    d.line(P((50, 4), (50, 26)), fill=255, width=W(4))
    d.line(P((50, 74), (50, 96)), fill=255, width=W(4))
    d.line(P((4, 50), (26, 50)), fill=255, width=W(4))
    d.line(P((74, 50), (96, 50)), fill=255, width=W(4))
    d.polygon(P((44, 66), (50, 30), (56, 66)), fill=255)


def g_ciws(d):
    d.pieslice(R(20, 46, 80, 106), 180, 360, fill=255)
    for i in range(3):
        y = 50 - i * 7
        d.polygon(P(*rot([(48, y - 2), (92, y - 2), (92, y + 2), (48, y + 2)], -25, 50, 62)), fill=255)
    d.ellipse(R(36, 18, 52, 34), outline=255, width=W(3))


def g_support(d):
    d.rectangle(R(40, 14, 60, 86), fill=255)
    d.rectangle(R(14, 40, 86, 60), fill=255)


def g_infantry(d):
    d.ellipse(R(40, 8, 60, 28), fill=255)
    d.polygon(P((36, 32), (64, 32), (70, 60), (60, 60), (60, 92), (52, 92), (50, 64), (48, 92), (40, 92), (40, 60), (30, 60)), fill=255)
    d.polygon(P((62, 36), (90, 26), (92, 30), (66, 44)), fill=255)


def g_light(d):
    d.polygon(P((6, 66), (12, 48), (30, 46), (40, 32), (70, 32), (78, 46), (94, 50), (94, 66)), fill=255)
    for x in (26, 74):
        d.ellipse(R(x - 11, 58, x + 11, 80), fill=255)
        d.ellipse(R(x - 5, 64, x + 5, 74), fill=0)
    d.polygon(P((44, 36), (56, 36), (56, 46), (42, 46)), fill=0)


def g_heavy(d):
    d.rounded_rectangle(R(6, 60, 94, 82), radius=W(10), fill=255)
    for x in (18, 34, 50, 66, 82):
        d.ellipse(R(x - 5, 66, x + 5, 76), fill=0)
    d.polygon(P((14, 60), (20, 48), (80, 48), (86, 60)), fill=255)
    d.rounded_rectangle(R(30, 32, 64, 50), radius=W(5), fill=255)
    d.rectangle(R(62, 37, 96, 42), fill=255)


def g_building(d):
    d.rectangle(R(10, 40, 46, 90), fill=255)
    d.rectangle(R(50, 18, 90, 90), fill=255)
    d.polygon(P((10, 40), (28, 26), (46, 40)), fill=255)
    for x in (58, 72):
        for y in (28, 44, 60):
            d.rectangle(R(x, y, x + 8, y + 9), fill=0)
    d.rectangle(R(22, 64, 34, 90), fill=0)


def g_aircraft(d):
    d.polygon(P((50, 4), (56, 20), (56, 40), (92, 60), (92, 68), (56, 58), (56, 80), (68, 90), (68, 96), (50, 90),
                (32, 96), (32, 90), (44, 80), (44, 58), (8, 68), (8, 60), (44, 40), (44, 20)), fill=255)


def g_ship(d):
    d.polygon(P((4, 60), (96, 60), (84, 80), (14, 80)), fill=255)
    d.rectangle(R(30, 44, 66, 60), fill=255)
    d.rectangle(R(42, 30, 54, 44), fill=255)
    d.rectangle(R(66, 52, 88, 56), fill=255)
    d.line(P((48, 14), (48, 30)), fill=255, width=W(3))
    for x in (8, 30, 52, 74):
        d.arc(R(x, 82, x + 22, 96), 200, 340, fill=255, width=W(3))


def g_range(d):
    d.ellipse(R(18, 18, 82, 82), outline=255, width=W(5))
    d.ellipse(R(40, 40, 60, 60), fill=255)
    for a in range(4):
        pts = rot([(50, 2), (50, 24)], a * 90)
        d.line(P(*pts), fill=255, width=W(6))


def g_damage(d):
    pts = []
    for k in range(16):
        r = 46 if k % 2 == 0 else 20
        a = math.radians(k * 22.5 - 90)
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    d.polygon(P(*pts), fill=255)


def g_reload(d):
    d.arc(R(14, 14, 86, 86), 40, 320, fill=255, width=W(11))
    d.polygon(P((70, 4), (94, 30), (62, 34)), fill=255)


def g_strong(d):
    d.polygon(P((50, 10), (92, 54), (72, 54), (50, 32), (28, 54), (8, 54)), fill=255)
    d.polygon(P((50, 46), (92, 90), (72, 90), (50, 68), (28, 90), (8, 90)), fill=255)


def g_weak(d):
    d.polygon(P((50, 54), (92, 10), (72, 10), (50, 32), (28, 10), (8, 10)), fill=255)
    d.polygon(P((50, 90), (92, 46), (72, 46), (50, 68), (28, 46), (8, 46)), fill=255)


def g_rounds(d):
    for x in (22, 46, 70):
        d.rounded_rectangle(R(x, 34, x + 16, 90), radius=W(2), fill=255)
        d.pieslice(R(x, 10, x + 16, 58), 180, 360, fill=255)
        d.rectangle(R(x, 78, x + 16, 82), fill=0)


def g_dps(d):
    d.polygon(P((10, 90), (10, 70), (36, 50), (52, 62), (82, 24), (92, 30), (54, 80), (38, 68), (20, 82)), fill=255)
    d.polygon(P((74, 14), (96, 14), (96, 36)), fill=255)


def render(fn):
    img = Image.new("L", (S, S), 0)
    fn(ImageDraw.Draw(img))
    glyph = img.resize((CELL, CELL), Image.LANCZOS)
    a = np.asarray(glyph).astype(np.float32) / 255

    # Soft dark rim so a tinted glyph reads on light and dark plates alike
    rim = np.asarray(glyph.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
    rim = np.clip(rim * 1.3, 0, 1) * 0.75
    alpha = np.clip(a + rim * (1 - a), 0, 1)

    # A gentle top-to-bottom sheen on the white
    ys = np.linspace(1.0, 0.82, CELL)[:, None]
    lum = np.where(alpha > 0, a * ys / np.maximum(alpha, 1e-6), 0)
    rgb = np.dstack([lum, lum, lum])
    return np.dstack([np.clip(rgb, 0, 1), alpha])


def main():
    rows = (len(NAMES) + COLS - 1) // COLS
    sheet = np.zeros((rows * CELL, COLS * CELL, 4), np.float32)
    for i, name in enumerate(NAMES):
        r, c = divmod(i, COLS)
        sheet[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] = render(globals()["g_" + name])
    Image.fromarray((sheet * 255).round().astype(np.uint8)).save(OUT, optimize=True)
    print("wrote", OUT, f"({len(NAMES)} glyphs)")


if __name__ == "__main__":
    main()
