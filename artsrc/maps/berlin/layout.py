#!/usr/bin/env python3
"""
Berlin 1946 (IDEA-28 pilot): a hand-designed, simplified post-war Berlin, laid out like a Commandos map: a few clear set
pieces instead of the exact street plan.

  python3 artsrc/maps/berlin/layout.py

Output: mods/rapx/maps/berlin-1946/{map.yaml, map.bin, map.png}   the playable 4-player skirmish map
        artsrc/maps/berlin/build/layout.json                       the same design for the Blender scene (build_scene.py)

Scale: 7 m per cell (true scale: a tank is about a cell). 128 x 80 cells = 896 x 560 m. North is up.

  Platz der Republik (NW base) | Reichstag | the Spree with two bridges (top) | ruined Mitte blocks (NE base)
  ---------------- main avenue: Victory Column - Brandenburg Gate - Pariser Platz - Soviet tower ----------------
  Tiergarten, cut down for firewood (SW base) | Ebertstrasse | ruined blocks (SE base)

Gameplay layer: water -> Water, standing buildings / landmarks -> Rock (impassable), everything else -> Clear.
The tiles are only a stand-in; the painted backdrop (PxMapBackdrop) is drawn over them.
"""
import json
import math
import os
import struct
import zlib

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "berlin-1946")

CELL = 7.0
NX, NY = 128, 80
CLEAR, WATER, ROCK = 255, 1, 57          # TEMPERAT templates: clear (16 variants), water, a 1x1 rock

# ------------------------------------------------------------------------------------------------- the design (cells)

SPREE = [(33, -3), (40, 6), (52, 12), (68, 14), (86, 13), (104, 9), (131, 5)]   # centre line
SPREE_WIDTH = 7
BRIDGES = [(85, 3), (101, 3)]             # x, width (north-south road bridges)

AVENUE = (44, 48)                         # main east-west avenue, rows 44..47
EBERT = (50, 53)                          # north-south street, columns 50..52
STREETS_NS = [(66, 68), (84, 86), (100, 102)]
STREETS_EW = [(27, 29), (62, 64)]

REICHSTAG = (36, 26, 20, 14)              # centre x, y, width, height
GATE = (56.5, 46)                         # centre; runs north-south across the avenue
VICTORY_COLUMN = (12, 46)
SOVIET_TOWER = (110, 46)
PARISER_PLATZ = (54, 36, 67, 57)          # open square east of the gate (x0, y0, x1, y1)

PLATZ = (2, 14, 28, 40)                   # Platz der Republik: open lawn
TIERGARTEN = (0, 49, 49, 80)              # cut-down park

SPAWNS = [(14, 27, 1, 1), (14, 67, 1, -1), (115, 31, -1, 1), (115, 69, -1, -1)]
BASE_LOT = (10, 8)                        # half size of the rubble lot cleared around eastern start positions
BASE_ORE = [(14, 15), (14, 39), (29, 67), (14, 55), (100, 31), (115, 19), (100, 69), (115, 57)]   # 2 per start
CONTESTED = [(34, 62, "ore"), (76, 72, "ore"), (24, 6, "gems"), (96, 3, "gems")]


def h32(*vals):
    return zlib.crc32(repr(vals).encode()) & 0xFFFFFFFF


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0.0, 1.0)
    return np.hypot(px - ax - t * dx, py - ay - t * dy)


def main():
    ys, xs = np.mgrid[0:NY, 0:NX] + 0.5
    grid = np.zeros((NY, NX), np.uint8)          # 0 clear, 1 water, 2 blocked
    ground = np.full((NY, NX), "p", dtype="<U1")  # p paving/rubble, a asphalt, g grass, s stumps, q quay

    def rect(r):
        return (xs >= r[0]) & (xs < r[2]) & (ys >= r[1]) & (ys < r[3])

    # Streets
    street = np.zeros((NY, NX), bool)
    street |= (ys >= AVENUE[0]) & (ys < AVENUE[1])
    street |= (xs >= EBERT[0]) & (xs < EBERT[1]) & (ys > 12)
    for a, b in STREETS_NS:
        street |= (xs >= a) & (xs < b) & (ys > 10)
    for a, b in STREETS_EW:
        street |= (ys >= a) & (ys < b) & (xs > EBERT[0])
    ground[street] = "a"
    ground[rect(PLATZ)] = "g"
    ground[rect(TIERGARTEN) & ~street] = "s"

    # The Spree, its quays and bridges
    river_d = np.min([seg_dist(xs, ys, ax, ay, bx, by) for (ax, ay), (bx, by) in zip(SPREE, SPREE[1:])], axis=0)
    water = river_d <= SPREE_WIDTH / 2
    ground[(river_d <= SPREE_WIDTH / 2 + 1.2) & ~water] = "q"
    grid[water] = 1
    for bx, bw in BRIDGES:
        grid[(xs >= bx - bw / 2) & (xs < bx + bw / 2) & water] = 0
        ground[(xs >= bx - bw / 2) & (xs < bx + bw / 2) & (river_d <= SPREE_WIDTH / 2 + 2)] = "a"

    # City blocks between the streets east of Ebertstrasse
    xcuts = [EBERT[1]] + [v for s in STREETS_NS for v in s] + [NX + 2]
    ycuts = [-2] + [v for s in STREETS_EW for v in s] + list(AVENUE) + [NY + 2]
    blocks = [[xcuts[i] + 1, ycuts[j] + 1, xcuts[i + 1] - 1, ycuts[j + 1] - 1]
              for i in range(0, len(xcuts), 2) for j in range(0, len(ycuts), 2)]
    blocks.append([4, -2, 30, 6])                    # ruins along the river bank, north-west

    lots = [PARISER_PLATZ]
    for bx, by, sx, sy in SPAWNS:
        if bx > 64:
            lots.append((bx - BASE_LOT[0], by - BASE_LOT[1], bx + BASE_LOT[0], by + BASE_LOT[1]))

    buildings = []
    for i, (x0, y0, x1, y1) in enumerate(blocks):
        x0, y0, x1, y1 = max(x0, -2), max(y0, -2), min(x1, NX + 2), min(y1, NY + 2)
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        # A perimeter block: a row of houses 3 cells deep on each side, courtyard inside
        depth = 3
        sides = [(x0, y0, x1, y0 + depth), (x0, y1 - depth, x1, y1),
                 (x0, y0 + depth, x0 + depth, y1 - depth), (x1 - depth, y0 + depth, x1, y1 - depth)]
        ground[rect((x0 + depth, y0 + depth, x1 - depth, y1 - depth))] = "d"     # courtyard
        for k, (a, b, c, d) in enumerate(sides):
            horizontal = c - a >= d - b
            length = (c - a) if horizontal else (d - b)
            pos, j = 0.0, 0
            while pos < length - 0.5:
                w = min(length - pos, 4 + h32("w", i, k, j) % 5)
                r = (a + pos, b, a + pos + w, d) if horizontal else (a, b + pos, c, b + pos + w)
                pos += w
                j += 1
                cxr, cyr = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
                if any(l[0] <= cxr < l[2] and l[1] <= cyr < l[3] for l in lots) or np.any(water & rect(r)):
                    continue
                roll = h32("state", i, k, j) % 100
                state = "rubble" if roll < 18 else ("shell" if roll < 50 else "standing")
                buildings.append({"rect": [round(v, 2) for v in r], "state": state,
                                  "floors": 4 + h32("f", i, k, j) % 2, "facade": h32("fac", i, k, j) % 6})

    ground[rect(PARISER_PLATZ) & (ground != "a")] = "p"

    # Landmarks
    rx, ry, rw, rh = REICHSTAG
    grid[rect((rx - rw / 2, ry - rh / 2, rx + rw / 2, ry + rh / 2))] = 2
    gx, gy = GATE
    for k in range(6):                                   # 6 column rows, 5 passages
        cy = gy - 4.7 + k * 1.88
        grid[rect((gx - 0.8, cy - 0.3, gx + 0.8, cy + 0.3))] = 2
    for side in (-1, 1):                                 # guard houses
        grid[rect((gx - 1, gy + side * 6 - 1, gx + 1, gy + side * 6 + 1))] = 2
    vx, vy = VICTORY_COLUMN
    grid[rect((vx - 1.5, vy - 1.5, vx + 1.5, vy + 1.5))] = 2
    tx, ty = SOVIET_TOWER
    grid[rect((tx - 2.5, ty - 2.5, tx + 2.5, ty + 2.5))] = 2

    # Resources: two fields per start position, plus contested ones; houses under ore become rubble
    fields = []
    for cx, cy in BASE_ORE:
        fields.append((cx, cy, "ore", 4.5, 3.4))
    for cx, cy, kind in CONTESTED:
        fields.append((cx, cy, kind, 4.0, 3.0) if kind == "ore" else (cx, cy, kind, 2.4, 1.7))
    res = np.zeros((NY, NX), np.uint8)
    for cx, cy, kind, rxf, ryf in fields:
        ph = h32("ore", cx, cy) % 628 / 100
        a = np.arctan2(ys - cy, xs - cx)
        wob = 1 + 0.08 * np.sin(2 * a + ph) + 0.06 * np.sin(5 * a + 2 * ph)
        inside = (((xs - cx) / rxf) ** 2 + ((ys - cy) / ryf) ** 2 <= wob * wob) & (grid != 1)
        res[inside] = 1 if kind == "ore" else 2
    for b in buildings:
        if b["state"] != "rubble" and np.any(res[rect(b["rect"])]):
            b["state"] = "rubble"
    for b in buildings:
        if b["state"] != "rubble":
            grid[rect(b["rect"]) & (grid == 0) & (res == 0)] = 2

    # Surviving trees (actors): a few in Tiergarten and Platz der Republik, a row along the avenue
    trees = []
    for y in range(1, NY - 1):
        for x in range(1, NX - 1):
            if grid[y, x] or res[y, x] or any(math.hypot(x - sx, y - sy) < 12 for sx, sy, _, _ in SPAWNS):
                continue
            g = ground[y, x]
            p = {"s": 7, "g": 2}.get(g, 0)
            if g == "a" and y in (AVENUE[0], AVENUE[1] - 1) and x < EBERT[0] - 2 and x % 3 == 0 \
                    and math.hypot(x - VICTORY_COLUMN[0], y - VICTORY_COLUMN[1]) > 6:
                p = 70
            if p and h32("tree", x, y) % 100 < p:
                trees.append((x, y))

    write_map(grid, res, trees)
    write_ground_masks(ground)
    layout = {
        "cell_m": CELL, "cells": [NX, NY],
        "grid": ["".join(".~#"[v] for v in row) for row in grid],
        "ground": ["".join(row) for row in ground],
        "resources": ["".join(" og"[v] for v in row) for row in res],
        "spree": SPREE, "spree_width": SPREE_WIDTH, "bridges": BRIDGES,
        "buildings": buildings,
        "spawns": [[x, y] for x, y, _, _ in SPAWNS],
        "trees": trees,
        "landmarks": {"reichstag": list(REICHSTAG), "brandenburg_gate": list(GATE),
                      "victory_column": list(VICTORY_COLUMN), "soviet_tower": list(SOVIET_TOWER)},
    }
    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "layout.json"), "w") as f:
        json.dump(layout, f, separators=(",", ":"))
    counts = {s: sum(1 for b in buildings if b["state"] == s) for s in ("standing", "shell", "rubble")}
    print(f"{NX}x{NY} cells: blocked {int((grid == 2).sum())}, water {int((grid == 1).sum())}, "
          f"ore {int((res == 1).sum())}, gems {int((res == 2).sum())}, trees {len(trees)}, houses {counts}")


def write_ground_masks(ground, ppm=2):
    """Ground masks for the Blender scene, `ppm` pixels per metre, soft edges.
    ground_a.png: R asphalt, G grass, B dirt (stumps, courtyards), A quay stone. water.png: the Spree (exact curve)."""
    from PIL import ImageFilter
    s = int(CELL * ppm)
    layers = []
    for keys in ("a", "g", "sd", "q"):
        m = np.isin(ground, list(keys)).astype(np.uint8) * 255
        im = Image.fromarray(np.repeat(np.repeat(m, s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 1.2))
        layers.append(np.asarray(im))
    py, px = (np.mgrid[0:NY * s, 0:NX * s] + 0.5) / s
    d = np.min([seg_dist(px, py, ax, ay, bx, by) for (ax, ay), (bx, by) in zip(SPREE, SPREE[1:])], axis=0)
    # The quay band follows the river's curve (the cell grid would give it steps)
    layers[3] = (np.clip((SPREE_WIDTH / 2 + 1.0 - d) * s / 2, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(np.stack(layers, -1)).save(os.path.join(BUILD, "ground_a.png"))
    w = np.clip((SPREE_WIDTH / 2 - d) * s / 2 + 0.5, 0, 1)
    Image.fromarray((w * 255).astype(np.uint8)).save(os.path.join(BUILD, "water.png"))


def write_map(grid, res, trees):
    os.makedirs(MAP_DIR, exist_ok=True)
    W, H = NX + 2, NY + 2                                 # one border cell on each side (Bounds: 1,1,NX,NY)
    tiles = bytearray()
    resources = bytearray()
    for i in range(W):
        for j in range(H):
            x, y = min(max(i - 1, 0), NX - 1), min(max(j - 1, 0), NY - 1)
            g = grid[y, x]
            r = res[y, x] if (x, y) == (i - 1, j - 1) else 0
            if g == 1:
                tiles += struct.pack("<HB", WATER, 0)
            elif g == 2:
                tiles += struct.pack("<HB", ROCK, 0)
            else:
                tiles += struct.pack("<HB", CLEAR, h32("clear", i, j) % 16)
            resources += struct.pack("<BB", r, 12 if r == 1 else (3 if r == 2 else 0))
    header = struct.pack("<BHHIII", 2, W, H, 17, 0, 17 + len(tiles))
    with open(os.path.join(MAP_DIR, "map.bin"), "wb") as f:
        f.write(header + tiles + resources)

    tree_types = ["t01", "t02", "t03", "t05", "t06", "t07", "t12", "t13"]
    actors = []
    for x, y, _, _ in SPAWNS:
        actors.append(f"\tActor{len(actors)}: mpspawn\n\t\tOwner: Neutral\n\t\tLocation: {x + 1},{y + 1}\n")
    for x, y in trees:
        # These trees stand on the bottom-left cell of their 2x2 box
        t = tree_types[h32("tt", x, y) % len(tree_types)]
        actors.append(f"\tActor{len(actors)}: {t}\n\t\tOwner: Neutral\n\t\tLocation: {x + 1},{y}\n")

    players = ["\tPlayerReference@Neutral:\n\t\tName: Neutral\n\t\tOwnsWorld: True\n\t\tNonCombatant: True\n"
               "\t\tFaction: allies\n",
               "\tPlayerReference@Creeps:\n\t\tName: Creeps\n\t\tNonCombatant: True\n\t\tFaction: allies\n"
               "\t\tEnemies: Multi0, Multi1, Multi2, Multi3\n"]
    for k in range(4):
        players.append(f"\tPlayerReference@Multi{k}:\n\t\tName: Multi{k}\n\t\tPlayable: True\n\t\tFaction: Random\n"
                       f"\t\tEnemies: Creeps\n")
    yaml = ("MapFormat: 12\n\nRequiresMod: ra\n\nTitle: Berlin 1946\n\nAuthor: RedAlert Project X\n\n"
            f"Tileset: TEMPERAT\n\nMapSize: {W},{H}\n\nBounds: 1,1,{NX},{NY}\n\nVisibility: Lobby\n\n"
            "Categories: World Cities\n\nPlayers:\n" + "".join(players) + "\nActors:\n" + "".join(actors))
    with open(os.path.join(MAP_DIR, "map.yaml"), "w") as f:
        f.write(yaml)

    # Lobby preview from the layout (replaced by a backdrop thumbnail once one is rendered)
    S = 4
    colors = np.array([(150, 140, 120), (50, 90, 130), (90, 80, 72)], np.uint8)
    img = colors[grid]
    img[res == 1] = (200, 160, 60)
    img[res == 2] = (140, 90, 200)
    Image.fromarray(np.repeat(np.repeat(img, S, 0), S, 1)).save(os.path.join(MAP_DIR, "map.png"))


if __name__ == "__main__":
    main()
