#!/usr/bin/env python3
"""Contact sheet of the prepared Ironward buildings (prep_buildings.py renders the shots): build/buildings-sheet.png."""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
shots = json.load(open(os.path.join(BUILD, "models", "shots.json")))
info = json.load(open(os.path.join(BUILD, "buildings.json")))
cols = 8
rows = (len(shots) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 256, rows * 284), (20, 20, 24))
d = ImageDraw.Draw(sheet)
for n, (name, path) in enumerate(shots):
    x, y = (n % cols) * 256, (n // cols) * 284
    sheet.paste(Image.open(path).convert("RGB"), (x, y))
    i = info[name]
    d.text((x + 4, y + 262), f"{name}  {i['w']:.0f}x{i['d']:.0f}x{i['h']:.0f}m  {i['tris'] // 1000}k", fill=(255, 255, 255))
sheet.save(os.path.join(BUILD, "buildings-sheet.png"))
print(len(shots), "buildings ->", os.path.join(BUILD, "buildings-sheet.png"))
