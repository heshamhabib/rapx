#!/usr/bin/env python3
"""
Egypt: Cairo and Giza (IDEA-28 painted map): the Nile between Giza and Cairo at golden sunset, 4 players.
An imaginary compression of the real places (they are ~15 km apart): the Giza plateau with its three pyramids and
the Sphinx, the Grand Egyptian Museum beside it, the Nile with Gezira island and the Cairo Tower, downtown Cairo on
the east bank, and a Karnak-style temple with an avenue of sphinxes and a sacred lake.

  python3 artsrc/maps/egypt/layout.py [--plan build/plan.png]

Output: mods/rapx/maps/egypt-cairo-giza/{map.yaml, map.bin, map.png, water-flow.png}   the playable map
        artsrc/maps/egypt/build/{layout.json, ground_a.png, water.png, sand.png}      the design for build_backdrop.py

Scale: 7 m per cell, 128 x 96 cells. North is up; the Nile flows north through the middle.

  bases: Giza (NW), Saqqara desert (SW), Downtown Cairo (NE), Old Cairo (SE)
  capturable (pay money, nation flag, build round): the Great Pyramid (pays double), the Sphinx, the Cairo Tower,
  the Grand Egyptian Museum, the Karnak temple; the other two pyramids and the temple ruins are scenery
  three bridges over the Nile; the middle one crosses Gezira island past the Cairo Tower

Same rules as Washington D.C.: wide roads, solid city blocks with lean-limited building heights, landmarks block
their lean rows, every base and landmark reachable 3 tanks wide, clean build areas and ground in front of landmarks.
"""
import argparse
import json
import math
import os
import struct
import zlib

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "egypt-cairo-giza")

CELL = 7.0
NX, NY = 128, 96
CLEAR, WATER, ROCK = 255, 1, 57
ROAD, ROUGH = (228, 0), (47, 4)
LOT = 10
SHEAR = 1 / math.tan(math.radians(50))
MAX_H = 40.0

RIVER = [(68, -3), (66, 24), (62, 48), (64, 72), (70, 100)]    # the Nile's centre line (it flows north)
RIVER_W = 10
ISLAND = (63, 40, 4.5, 7.5)                 # Gezira island (ellipse)
BRIDGES = [[(45, 9), (85, 9)], [(45, 40), (85, 40)], [(45, 86), (88, 86)]]
SACRED_LAKE = (90, 79, 97, 84)
SPAWNS = {"giza": (14, 12), "saqqara": (12, 84), "downtown": (114, 12), "oldcairo": (114, 84)}
# Scaled heights (metres; real ones would lean 15+ cells): pyramids keep their 0.64 height / base ratio
HEIGHTS = {"khufu": 60.0, "sphinx": 14.0, "cairotower": 55.0, "gem": 16.0, "karnak": 18.0,
           "khafre": 50.0, "menkaure": 30.0, "ruins": 10.0}
# name: (actor or None for scenery, footprint x0, y0, x1, y1, capture x0, y0, x1, y1 or None, open side)
LANDMARKS = {
    "khufu": ("egpyramid", (22, 54, 36, 68), (28, 64, 32, 68), (0, 1)),
    "sphinx": ("egsphinx", (42, 52, 50, 56), (46, 52, 50, 56), (1, 0)),
    "cairotower": ("egcairotower", (62, 33, 65, 36), (61, 32, 65, 36), (0, 1)),
    "gem": ("egmuseum", (22, 30, 42, 38), (30, 34, 34, 38), (0, 1)),
    "karnak": ("egkarnak", (88, 62, 104, 72), (88, 66, 92, 70), (-1, 0)),
    "khafre": (None, (39, 64, 50, 75), None, None),
    "menkaure": (None, (42, 79, 49, 86), None, None),
    "ruins": (None, (80, 34, 88, 40), None, None),
}
TREE_TYPES = []


def h32(*vals):
    return zlib.crc32(repr(vals).encode()) & 0xFFFFFFFF


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0.0, 1.0)
    return np.hypot(px - ax - t * dx, py - ay - t * dy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan")
    a = ap.parse_args()
    ys, xs = np.mgrid[0:NY, 0:NX] + 0.5

    def rect(x0, y0, x1, y1):
        return (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)

    def band(pts, w):
        return np.min([seg_dist(xs, ys, *p, *q) for p, q in zip(pts, pts[1:])], axis=0) < w / 2

    def ell(cx, cy, rx, ry):
        return ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 <= 1

    river_d = np.min([seg_dist(xs, ys, *p, *q) for p, q in zip(RIVER, RIVER[1:])], axis=0)
    island = ell(*ISLAND)
    river = ((river_d < RIVER_W / 2) | ell(ISLAND[0], ISLAND[1], ISLAND[2] + 5, ISLAND[3] + 2)) & ~island
    bridge_band = np.zeros((NY, NX), bool)
    for b in BRIDGES:
        bridge_band |= band(b, 5.5)
    bridges = bridge_band & river
    lake = rect(*SACRED_LAKE)
    water = (river | lake) & ~bridges
    lab, _ = ndimage.label(~river)
    west = (lab == lab[48, 2]) | ((xs < 62) & ~river & ~island)
    desert = west & (ys > 44)

    # Roads: west bank (Giza) and east bank (Cairo) grids, the Corniche along the Nile, the desert road
    # No roads on the Giza plateau: the pyramids and the Sphinx stand in open sand (the desert is passable anyway)
    roads = (rect(4, 24, 56, 29) | rect(48, 0, 53, 46)
             | rect(76, 0, 81, NY) | rect(81, 24, NX, 29) | rect(81, 50, NX, 55) | rect(98, 0, 102, 50)
             | rect(81, 74, 104, 78) | rect(98, 55, 102, 62) | rect(104, 50, 108, 62))
    streets = (roads | bridge_band) & ~water
    lot = np.zeros((NY, NX), bool)
    for sx, sy in SPAWNS.values():
        lot |= rect(sx - LOT, sy - LOT, sx + LOT, sy + LOT)
    fields = west & ~desert & band([(57, 0), (55, 44)], 6)          # green fields along the west bank
    avenue_sphinx = rect(70, 67, 88, 69)                             # the avenue of sphinxes to the Nile
    gem_plaza = (rect(18, 37, 46, 45)                                # the museum's forecourt (towards the pyramids)
                 | rect(81, 61, 88, 74))                             # the temple's forecourt at the avenue's end
    footprints = np.zeros((NY, NX), bool)
    for name, (_, fp, _, _) in LANDMARKS.items():
        footprints |= rect(*fp)
        lean = math.ceil(HEIGHTS[name] * SHEAR / CELL)
        if name in ("khufu", "khafre", "menkaure"):                  # a pyramid's apex leans: a narrow column
            cx = (fp[0] + fp[2]) / 2
            footprints |= rect(cx - 2, fp[1] - lean, cx + 2, fp[1])
        elif name == "cairotower":
            footprints |= rect(fp[0], fp[1] - lean, fp[2], fp[1])
        else:
            footprints |= rect(fp[0], fp[1] - lean, fp[2], fp[1])
    sphinx_statues = np.zeros((NY, NX), bool)                        # the avenue: statues on both sides (scenery)

    ore = np.zeros((NY, NX), bool)
    for name, (sx, sy) in SPAWNS.items():
        ox = sx + (LOT + 4) * (1 if sx < NX / 2 else -1)
        ore |= ell(ox, sy, 2.5, 5.0)
    gems = ell(20, 46, 3.0, 1.8) | ell(92, 44, 3.0, 1.8)
    ore &= ~water & ~streets & ~lot & ~footprints
    gems &= ~water & ~footprints

    open_ground = water | streets | lot | fields | footprints | ore | gems | desert | bridges | island | avenue_sphinx | gem_plaza
    blocks = ~open_ground
    blocks = ndimage.binary_opening(blocks, structure=np.ones((3, 3)))
    buildings = pack_buildings(blocks)
    grid = np.zeros((NY, NX), np.uint8)
    # The green strip along the west bank is a palm grove: blocked, so the painted palms never stand where units drive
    grove = fields & ~streets & ~bridge_band & ~lot
    grid[blocks | footprints | grove] = 2
    grid[water] = 1
    surface = np.zeros((NY, NX), np.uint8)
    surface[streets & (grid == 0)] = 1

    ground = np.full((NY, NX), "c", dtype="<U1")   # c paving, a asphalt, p plaza, y fields, q quay, d desert sand
    ground[desert] = "d"
    ground[fields | island | lot & ~desert] = "y"
    ground[grove] = "v"
    ground[lot & desert] = "d"
    ground[streets] = "a"
    ground[avenue_sphinx | gem_plaza] = "p"
    quay = ndimage.binary_dilation(water, iterations=1) & ~water & ~bridges
    ground[quay & (grid == 0) & ~desert] = "q"
    for name, (_, fp, cap, _) in LANDMARKS.items():
        ring = rect(fp[0] - 1, fp[1] - 1, fp[2] + 1, fp[3] + 1) & (grid == 0) & ~streets
        ground[ring & (ground != "d")] = "p"

    res = np.zeros((NY, NX), np.uint8)
    res[ore] = 1
    res[gems] = 2
    trees = []

    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(MAP_DIR, exist_ok=True)
    spawns = list(SPAWNS.values())
    check(grid, res, spawns, rect)
    actors = [(name, act, ((cap[0] + cap[2]) // 2, (cap[1] + cap[3]) // 2)) for name, (act, _, cap, _) in LANDMARKS.items() if act]
    write_map(grid, res, spawns, surface, actors, trees)
    write_water_flow(water, river_d, lake)
    write_ground_masks(ground, water)
    layout = {
        "cell_m": CELL, "cells": [NX, NY], "river": RIVER, "river_w": RIVER_W, "island": ISLAND,
        "grid": ["".join(".~#"[v] for v in row) for row in grid],
        "ground": ["".join(row) for row in ground],
        "resources": ["".join(" og"[v] for v in row) for row in res],
        "buildings": buildings, "spawns": [list(s) for s in spawns], "lot": LOT, "trees": trees,
        "landmarks": {k: list(v[1]) for k, v in LANDMARKS.items()},
        "captures": {k: list(v[2]) for k, v in LANDMARKS.items() if v[2]},
        "bridges": BRIDGES, "lake": SACRED_LAKE, "avenue": [70, 67, 88, 69], "heights": HEIGHTS,
    }
    with open(os.path.join(BUILD, "layout.json"), "w") as f:
        json.dump(layout, f, separators=(",", ":"))
    print(f"{NX}x{NY} cells: blocked {int((grid == 2).sum())}, water {int((grid == 1).sum())}, ore {int(ore.sum())}, "
          f"gems {int(gems.sum())}, houses {len(buildings)}")
    if a.plan:
        write_plan(a.plan, grid, res, ground, spawns, trees)


def pack_buildings(blocks):
    """Buildings for the Blender scene inside the blocked city blocks. Each block is cut into lots of 3-6 cells;
    a lot's height is limited by the block rows north of it, so its lean (h * SHEAR / CELL rows) stays in the block.
    The first rows of a block are only lean: lots there are low (a wall of 1-2 storey shops along the street)."""
    out = []
    used = np.zeros_like(blocks)
    for y in range(NY):
        for x in range(NX):
            if not blocks[y, x] or used[y, x]:
                continue
            wmax, hmax = 3 + h32("w", x, y) % 4, 3 + h32("h", x, y) % 3
            w = 1
            while w < wmax and x + w < NX and blocks[y, x + w] and not used[y, x + w]:
                w += 1
            h = 1
            while h < hmax and y + h < NY and np.all(blocks[y + h, x:x + w] & ~used[y + h, x:x + w]):
                h += 1
            used[y:y + h, x:x + w] = True
            # Rows of block north of this lot, over its whole width
            k = 0
            while y - k - 1 >= 0 and np.all(blocks[y - k - 1, x:x + w]):
                k += 1
            room = k * CELL / SHEAR                           # the tallest building whose lean fits
            seed = h32("b", x, y)
            want = 12 + seed % 1000 / 1000 * (MAX_H - 12)
            height = round(max(4.0, min(room, want)), 1)       # 4 m leans half a cell: a shopfront awning
            district = "cairo" if x > NX / 2 else "giza"
            out.append({"rect": [x, y, x + w, y + h], "h": height, "floors": max(1, int(height / 3.6)),
                        "style": seed % 7, "lit": round((seed >> 8) % 100 / 100, 2), "district": district})
    return out


def check(blocked, res, spawns, rect):
    """Every base reaches every base and every landmark 3 cells wide; the build areas and 6 rows of ground in front
    of each landmark's capture point take buildings; every base has the same amount of ore beside it."""
    passable = blocked == 0
    wide = ndimage.binary_erosion(passable, structure=np.ones((3, 3)))
    wl, _ = ndimage.label(ndimage.binary_dilation(wide, structure=np.ones((3, 3))) & passable)
    region = wl[spawns[0][1], spawns[0][0]]
    for sx, sy in spawns:
        assert wl[sy, sx] == region, f"base {sx},{sy}: no 3-wide way to the others"
        area = (slice(sy - LOT, sy + LOT), slice(sx - LOT, sx + LOT))
        assert not blocked[area].any() and not res[area].any(), f"base {sx},{sy}: blocked cells or resources in it"
    for name, (act, fp, cap, side) in LANDMARKS.items():
        if not cap:
            continue
        dx, dy = side
        x0, y0, x1, y1 = cap
        if dx:
            front = (slice(y0 - 1, y1 + 1), slice(x1, x1 + 6) if dx > 0 else slice(x0 - 6, x0))
        else:
            front = (slice(y1, y1 + 6) if dy > 0 else slice(y0 - 6, y0), slice(x0 - 1, x1 + 1))
        assert not blocked[front].any() and not res[front].any(), f"{name}: the ground in front of it does not take buildings"
        assert wl[front].max() == region, f"{name}: cannot be reached"


def write_map(grid, res, spawns, surface, landmarks, trees):
    os.makedirs(MAP_DIR, exist_ok=True)
    W, H = NX + 2, NY + 2
    tiles = bytearray()
    resources = bytearray()
    for i in range(W):
        for j in range(H):
            x, y = min(max(i - 1, 0), NX - 1), min(max(j - 1, 0), NY - 1)
            g = grid[y, x]
            rv = res[y, x] if (x, y) == (i - 1, j - 1) else 0
            if g == 1:
                tiles += struct.pack("<HB", WATER, 0)
            elif g == 2:
                tiles += struct.pack("<HB", ROCK, 0)
            elif surface[y, x] == 1 and not rv:
                tiles += struct.pack("<HB", *ROAD)
            elif surface[y, x] == 2 and not rv:
                tiles += struct.pack("<HB", *ROUGH)
            else:
                tiles += struct.pack("<HB", CLEAR, h32("clear", i, j) % 16)
            resources += struct.pack("<BB", rv, 12 if rv == 1 else (3 if rv == 2 else 0))
    header = struct.pack("<BHHIII", 2, W, H, 17, 0, 17 + len(tiles))
    with open(os.path.join(MAP_DIR, "map.bin"), "wb") as f:
        f.write(header + tiles + resources)

    actors = []
    for x, y in spawns:
        actors.append(f"\tActor{len(actors)}: mpspawn\n\t\tOwner: Neutral\n\t\tLocation: {x + 1},{y + 1}\n")
    for name, actor, (lx, ly) in landmarks:
        actors.append(f"\t{name.capitalize()}: {actor}\n\t\tOwner: Neutral\n\t\tLocation: {lx - 2 + 1},{ly - 2 + 1}\n")
    for x, y in trees:
        t = TREE_TYPES[h32("tt", x, y) % len(TREE_TYPES)]
        actors.append(f"\tActor{len(actors)}: {t}\n\t\tOwner: Neutral\n\t\tLocation: {x + 1},{y}\n")
    names = [f"Multi{k}" for k in range(4)]
    players = ["\tPlayerReference@Neutral:\n\t\tName: Neutral\n\t\tOwnsWorld: True\n\t\tNonCombatant: True\n\t\tFaction: allies\n",
               "\tPlayerReference@Creeps:\n\t\tName: Creeps\n\t\tNonCombatant: True\n\t\tFaction: allies\n"
               f"\t\tEnemies: {', '.join(names)}\n"]
    for n in names:
        players.append(f"\tPlayerReference@{n}:\n\t\tName: {n}\n\t\tPlayable: True\n\t\tFaction: Random\n\t\tEnemies: Creeps\n")
    yaml = ("MapFormat: 12\n\nRequiresMod: ra\n\nTitle: Egypt: Cairo and Giza\n\nAuthor: RedAlert Project X\n\n"
            f"Tileset: TEMPERAT\n\nMapSize: {W},{H}\n\nBounds: 1,1,{NX},{NY}\n\nVisibility: Lobby\n\n"
            "Categories: World Cities\n\nPlayers:\n" + "".join(players) + "\nActors:\n" + "".join(actors) +
            "\nRules:\n\tWorld:\n\t\tPxWeatherManager:\n\t\t\tFixed: Clear\n")
    with open(os.path.join(MAP_DIR, "map.yaml"), "w") as f:
        f.write(yaml)
    if os.path.exists(os.path.join(MAP_DIR, "backdrop-0-0.png")):
        return
    colors = np.array([(170, 180, 150), (50, 100, 140), (120, 104, 96)], np.uint8)
    img = colors[grid]
    Image.fromarray(np.repeat(np.repeat(img, 3, 0), 3, 1)).save(os.path.join(MAP_DIR, "map.png"))


def write_water_flow(water, river_d, still, ppc=16, bank_cells=2.0):
    """PxBackdropWater flow map: R water, G flow angle (0.5 = west), B bank distance. The Nile flows north (towards
    the top of the map, against the RIVER line's order); the temple's sacred lake barely moves."""
    up = np.repeat(np.repeat(water, 4, 0), 4, 1)
    cover = np.asarray(Image.fromarray((up * 255).astype(np.uint8)).resize((NX * ppc, NY * ppc), Image.BILINEAR), np.float32) / 255
    cover = np.clip((ndimage.gaussian_filter(cover, 1.2) - 0.15) / 0.7, 0, 1)
    py, px = (np.mgrid[0:NY * ppc, 0:NX * ppc] + 0.5) / ppc
    best = np.full(px.shape, np.inf)
    tx = np.zeros(px.shape)
    ty = np.zeros(px.shape)
    for (ax, ay), (bx, by) in zip(RIVER, RIVER[1:]):
        d = seg_dist(px, py, ax, ay, bx, by)
        sel = d < best
        best[sel] = d[sel]
        n = math.hypot(bx - ax, by - ay)
        tx[sel], ty[sel] = (ax - bx) / n, (ay - by) / n            # the Nile flows north: against the line
    tx, ty = ndimage.gaussian_filter(tx, ppc * 3), ndimage.gaussian_filter(ty, ppc * 3)
    angle = np.arctan2(ty, tx) - math.pi
    angle = (angle + math.pi) % (2 * math.pi) - math.pi
    bank = ndimage.distance_transform_edt(cover > 0.5) / ppc
    still_up = np.repeat(np.repeat(still, ppc, 0), ppc, 1)
    bank = np.where(still_up, np.minimum(bank, 0.3), bank)        # pools: "near the bank" everywhere = slow, calm
    W2 = 1 << (NX * ppc - 1).bit_length()
    H2 = 1 << (NY * ppc - 1).bit_length()
    out = np.zeros((H2, W2, 4), np.uint8)
    out[..., 3] = 255
    out[:NY * ppc, :NX * ppc, 0] = np.round(cover * 255)
    out[:NY * ppc, :NX * ppc, 1] = np.round((angle / (2 * math.pi) + 0.5) * 255)
    out[:NY * ppc, :NX * ppc, 2] = np.round(np.clip(bank / bank_cells, 0, 1) * 255)
    Image.fromarray(out).save(os.path.join(MAP_DIR, "water-flow.png"), optimize=True)


def write_ground_masks(ground, water, ppm=2):
    """ground_a.png: R asphalt, G plaza, B fields / lawn, A quay; water.png: water; sand.png: the desert.
    `ppm` pixels per metre, soft edges."""
    s = int(CELL * ppm)
    layers = []
    for keys in ("a", "p", "yv", "q"):
        m = np.isin(ground, list(keys)).astype(np.uint8) * 255
        layers.append(np.asarray(Image.fromarray(np.repeat(np.repeat(m, s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 1.2))))
    Image.fromarray(np.stack(layers, -1)).save(os.path.join(BUILD, "ground_a.png"))
    w = Image.fromarray(np.repeat(np.repeat((water * 255).astype(np.uint8), s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 2.5))
    Image.fromarray(np.where(np.asarray(w) > 127, 255, 0).astype(np.uint8)).filter(ImageFilter.GaussianBlur(ppm * 0.6)).save(os.path.join(BUILD, "water.png"))
    m = (ground == "d").astype(np.uint8) * 255
    Image.fromarray(np.repeat(np.repeat(m, s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 2)).save(os.path.join(BUILD, "sand.png"))


def write_plan(path, grid, res, ground, spawns, trees, S=8):
    from PIL import ImageDraw
    img = np.zeros((NY, NX, 3), np.uint8)
    img[:] = (190, 192, 180)
    img[ground == "a"] = (110, 112, 120)
    img[ground == "y"] = (120, 170, 100)
    img[ground == "d"] = (220, 190, 130)
    img[ground == "p"] = (220, 210, 190)
    img[grid == 2] = (90, 80, 80)
    img[grid == 1] = (40, 80, 120)
    img[res == 1] = (214, 170, 60)
    img[res == 2] = (160, 100, 220)
    for x, y in trees:
        img[y, x] = (30, 80, 30)
    im = Image.fromarray(np.repeat(np.repeat(img, S, 0), S, 1))
    d = ImageDraw.Draw(im)
    for i, (sx, sy) in enumerate(spawns):
        d.ellipse([sx * S - 16, sy * S - 16, sx * S + 16, sy * S + 16], fill=(230, 60, 60), outline=(0, 0, 0), width=2)
        d.text((sx * S, sy * S), str(i + 1), fill=(0, 0, 0), anchor="mm")
    for name, (_, _, cap, _) in LANDMARKS.items():
        if not cap:
            continue
        d.rectangle([cap[0] * S, cap[1] * S, cap[2] * S, cap[3] * S], outline=(255, 0, 255), width=3)
    im.save(path)


if __name__ == "__main__":
    main()
