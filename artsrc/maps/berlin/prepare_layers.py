#!/usr/bin/env python3
"""
Ground masks and tree positions for the Berlin painted-map pilot (IDEA-28), from berlin_osm.json.

  python3 artsrc/maps/berlin/prepare_layers.py

Output (artsrc/maps/berlin/build/):
  mask_<layer>.png   1 px per metre, white = layer present, anti-aliased (drawn at 2x and reduced)
                     layers: water, embankment, green, forest, paved, road, minor (paths), rail, building
  masks_a.png / masks_b.png   the same masks packed 4 per RGBA image (a: green forest paved minor, b: rail road
                     embankment water), so the Blender ground material stays under Metal's 16-texture limit
  trees.json         [[x, y, scale, kind], ...] in metres (kind 0 = park/forest tree, 1 = street tree)
"""
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
SS = 2  # supersampling


def load():
    with open(os.path.join(HERE, "berlin_osm.json")) as f:
        return json.load(f)


def canvas(w, h):
    im = Image.new("L", (w * SS, h * SS), 0)
    return im, ImageDraw.Draw(im)


def px(pt, h):
    return (pt[0] * SS, (h - pt[1]) * SS)


def fill_polys(draw, polys, h, value=255):
    for p in polys:
        if len(p["outer"]) >= 3:
            draw.polygon([px(q, h) for q in p["outer"]], fill=value)
    for p in polys:
        for hole in p.get("holes", []):
            if len(hole) >= 3:
                draw.polygon([px(q, h) for q in hole], fill=0)


def lines(draw, items, h, width_of):
    for it in items:
        pts = [px(q, h) for q in it["pts"]]
        if len(pts) < 2:
            continue
        w = max(1, int(width_of(it) * SS))
        draw.line(pts, fill=255, width=w, joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[-1]):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


def save(im, name):
    small = im.resize((im.width // SS, im.height // SS), Image.LANCZOS)
    small.save(os.path.join(BUILD, f"mask_{name}.png"), optimize=True)
    return np.asarray(small).astype(np.float32) / 255


def main():
    d = load()
    W, H = (int(math.ceil(v)) for v in d["size_m"])
    os.makedirs(BUILD, exist_ok=True)
    masks = {}

    im, dr = canvas(W, H)
    fill_polys(dr, d["water"], H)
    lines(dr, d["waterways"], H, lambda it: 6)
    masks["water"] = save(im, "water")
    # Stone embankment: a 4 m band along every shore (Berlin's Spree and canals are walled)
    emb = im.filter(ImageFilter.MaxFilter(9 * SS - (9 * SS + 1) % 2))
    emb = Image.fromarray(np.clip(np.asarray(emb, np.int16) - np.asarray(im, np.int16), 0, 255).astype(np.uint8))
    masks["embankment"] = save(emb, "embankment")

    for name in ("green", "forest", "paved"):
        im, dr = canvas(W, H)
        fill_polys(dr, d[name], H)
        masks[name] = save(im, name)

    major = [r for r in d["roads"] if r["w"] >= 7 and not r["tunnel"]]
    minor = [r for r in d["roads"] if r["w"] < 7 and not r["tunnel"]]
    im, dr = canvas(W, H)
    lines(dr, major, H, lambda it: it["w"])
    masks["road"] = save(im, "road")
    im, dr = canvas(W, H)
    lines(dr, minor, H, lambda it: it["w"])
    masks["minor"] = save(im, "minor")
    im, dr = canvas(W, H)
    lines(dr, d["rails"], H, lambda it: 7 if it["kind"] in ("rail", "light_rail") else 4)
    masks["rail"] = save(im, "rail")
    im, dr = canvas(W, H)
    fill_polys(dr, d["buildings"], H)
    masks["building"] = save(im, "building")

    for name, layers in (("a", ("green", "forest", "paved", "minor")), ("b", ("rail", "road", "embankment", "water"))):
        rgba = np.stack([(masks[k] * 255 + 0.5).astype(np.uint8) for k in layers], axis=-1)
        Image.fromarray(rgba).save(os.path.join(BUILD, f"masks_{name}.png"))

    # Trees: dense in forest, scattered in parks, rows along streets; never on water, roads, rails or buildings
    rng = random.Random(28)
    blocked = np.maximum.reduce([masks["water"], masks["road"], masks["rail"], masks["building"], masks["embankment"]])

    def free(x, y):
        ix, iy = int(x), int(H - 1 - y)
        return 0 <= ix < W and 0 <= iy < H and blocked[iy, ix] < 0.3

    trees = []
    forest, green = masks["forest"], masks["green"]
    for (mask, spacing, scale) in ((forest, 7.5, (0.9, 1.4)), (green, 16, (0.8, 1.3))):
        for gy in np.arange(0, H, spacing):
            for gx in np.arange(0, W, spacing):
                x = gx + rng.uniform(-spacing / 2, spacing / 2)
                y = gy + rng.uniform(-spacing / 2, spacing / 2)
                ix, iy = int(x), int(H - 1 - y)
                if 0 <= ix < W and 0 <= iy < H and mask[iy, ix] > 0.5 and free(x, y):
                    trees.append([round(x, 1), round(y, 1), round(rng.uniform(*scale), 2), 0])
    for r in d["roads"]:
        if r["kind"] not in ("primary", "secondary", "tertiary", "residential") or r["tunnel"] or r["bridge"]:
            continue
        pts = r["pts"]
        off = r["w"] / 2 + 3.5
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = math.hypot(x1 - x0, y1 - y0)
            if seg < 1:
                continue
            nx, ny = -(y1 - y0) / seg, (x1 - x0) / seg
            t = rng.uniform(0, 14)
            while t < seg:
                bx, by = x0 + (x1 - x0) * t / seg, y0 + (y1 - y0) * t / seg
                for side in (-1, 1):
                    x, y = bx + nx * off * side, by + ny * off * side
                    if free(x, y) and rng.random() < 0.85:
                        trees.append([round(x, 1), round(y, 1), round(rng.uniform(0.6, 0.9), 2), 1])
                t += 14
    with open(os.path.join(BUILD, "trees.json"), "w") as f:
        json.dump(trees, f, separators=(",", ":"))
    print(f"masks {W}x{H} px; trees {len(trees)} "
          f"({sum(1 for t in trees if t[3] == 0)} park/forest, {sum(1 for t in trees if t[3] == 1)} street)")


if __name__ == "__main__":
    main()
