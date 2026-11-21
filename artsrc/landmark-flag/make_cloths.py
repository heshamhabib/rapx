#!/usr/bin/env python3
"""Nation flag images for the landmark flag (render_flag.py): build/cloths/<faction>.png, 600 x 400.

Countries come from the public domain SVGs in artsrc/px-flags/svg (rsvg-convert); the two side factions (allies =
Union, soviet = Vanguard) get a plain banner with a star."""
import os
import subprocess

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(HERE, "..", "px-flags", "svg")
OUT = os.path.join(HERE, "build", "cloths")
SVG = {"england": "gb-eng", "france": "fr", "germany": "de", "turkey": "tr", "pakistan": "pk", "russia": "ru",
       "ukraine": "ua", "cuba": "cu", "india": "in", "egypt": "eg", "china": "cn", "japan": "jp", "southkorea": "kr",
       "italy": "it", "usa": "us", "iran": "ir"}
SIDES = {"allies": ((28, 64, 150), (255, 255, 255)), "soviet": ((170, 20, 20), (255, 205, 60))}
W, H = 600, 400


def star(d, cx, cy, r, fill):
    import math
    pts = []
    for k in range(10):
        rr = r if k % 2 == 0 else r * 0.42
        a = -math.pi / 2 + k * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


os.makedirs(OUT, exist_ok=True)
for name, code in SVG.items():
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), "--keep-aspect-ratio", "-o", path + ".tmp.png",
                    os.path.join(SVG_DIR, code + ".svg")], check=True)
    im = Image.open(path + ".tmp.png").convert("RGB").resize((W, H), Image.LANCZOS)
    im.save(path)
    os.remove(path + ".tmp.png")
for name, (bg, fg) in SIDES.items():
    im = Image.new("RGB", (W, H), bg)
    star(ImageDraw.Draw(im), W / 2, H / 2, H * 0.32, fg)
    im.save(os.path.join(OUT, name + ".png"))
print(len(os.listdir(OUT)), "cloths")
