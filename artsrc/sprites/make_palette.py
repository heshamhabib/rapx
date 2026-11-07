#!/usr/bin/env python3
"""
Writes mods/rapx/bits/rapx.pal, our own 256-colour palette (IDEA-31). It replaces temperat.pal / snow.pal /
desert.pal from the original game for every PaletteFromFile in rules/palettes.yaml.

Nothing the game draws takes its colours from a palette file any more: all sprites and terrain tiles are RGBA, the
editor shroud uses ShroudPalette and the GPS dots use only the player colour range 80-95, which PlayerColorPalette
remaps. So the palette only has to exist and keep 80-95 as a light-to-dark ramp; the rest is a plain colour wheel.
Classic VGA format: 256 x (r, g, b), 6 bits per channel.

  python3 artsrc/sprites/make_palette.py
"""
import colorsys
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mods", "rapx", "bits", "rapx.pal")

cols = []
for i in range(256):
    if i == 0:
        c = (0, 0, 0)
    elif i < 16 or i >= 240:
        v = (i if i < 16 else i - 224) / 31
        c = (v, v, v)
    elif 80 <= i < 96:
        v = 1 - (i - 80) / 17          # player colour ramp: light to dark
        c = (v, v, v)
    else:
        h = ((i - 16) % 32) / 32
        v = 0.35 + 0.6 * ((i - 16) // 32) / 7
        c = colorsys.hsv_to_rgb(h, 0.6, min(v, 1))
    cols.append(tuple(min(63, round(x * 63)) for x in c))
with open(OUT, "wb") as f:
    f.write(bytes(v for c in cols for v in c))
print(OUT, os.path.getsize(OUT), "bytes")
