#!/usr/bin/env python3
"""
Washington D.C. (IDEA-28 painted map): the National Mall and the city round it at golden sunset, 4 players.
Simplified from the real map (user reference: a satellite map of central D.C.).

  python3 artsrc/maps/dc/layout.py [--plan build/plan.png]

Output: mods/rapx/maps/washington-dc/{map.yaml, map.bin, map.png, water-flow.png}   the playable map
        artsrc/maps/dc/build/{layout.json, ground_a.png, water.png}                 the design for build_backdrop.py

Scale: 7 m per cell, 128 x 96 cells (896 x 672 m; the real Mall is squeezed to fit). North is up.

  the Mall runs west-east through the middle: Lincoln Memorial - Reflecting Pool - Washington Monument - lawns - Capitol
  the White House north of the Monument with its park and the Ellipse; Pennsylvania Avenue to the Capitol
  the Tidal Basin south of the Monument, the Jefferson Memorial on its south shore
  the Potomac along the west and south-west, the Memorial Bridge and the 14th Street bridge to Virginia
  bases: Foggy Bottom (NW), Downtown (NE), The Wharf (SE), Arlington across the river (SW)
  capturable landmarks (pay money, nation flag on capture, can be built round): Lincoln, White House, Capitol,
  Jefferson; the Washington Monument in the middle pays the most

Real geography is not symmetric, so the balance is checked instead: same ore per base, every base reaches every
other base and every landmark 3 cells wide, the build areas and the ground in front of each landmark take buildings.

Gameplay layer: water -> Water; city blocks, landmarks -> Rock; avenues, streets and bridges -> Road; the rest Clear.
Trees in the Virginia woods and along the Mall are tree actors.

Nothing painted may stand where units drive: in this projection a building of height h is drawn leaning
h * cot(50deg) north of its ground footprint. So every city block between the roads is blocked as a whole, and each
building stands far enough south in its block that its lean stays inside the block (buildings deep in a block can be
tall, the ones at its north edge are low). Landmarks block their lean rows too (LEAN).
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
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "washington-dc")

CELL = 7.0
NX, NY = 128, 96
CLEAR, WATER, ROCK = 255, 1, 57          # TEMPERAT templates
ROAD, ROUGH = (228, 0), (47, 4)
LOT = 10                                  # half size of a build area (20 x 20 cells)

RIVER = [(8, -3), (10, 30), (22, 56), (40, 78), (58, 100)]    # Potomac centre line (flows south-east)
RIVER_W = 11
POOL = (43, 49, 58, 52)                   # Reflecting Pool
BRIDGE1 = [(6, 66), (28, 60.5)]           # Memorial Bridge: Arlington -> Independence Ave
BRIDGE2 = [(26, 88), (54, 81)]            # 14th Street bridge: Arlington -> Maine Ave
BASIN = (60, 70, 10, 6.5)                 # Tidal Basin ellipse
MALL = (24, 44, 112, 58)
SHEAR = 1 / math.tan(math.radians(50))
MAX_H = 52.0                              # tallest city building, metres
# Landmark heights in metres (build_backdrop.py scales the models to them) and the rows their lean covers
HEIGHTS = {"lincoln": 18.0, "monument": 45.0, "capitol": 22.0, "whitehouse": 16.0, "jefferson": 24.0}
ELLIPSE = (64, 31, 8, 6)
WH_PARK = (56, 12, 72, 37)
SPAWNS = {"foggybottom": (26, 12), "downtown": (112, 14), "wharf": (112, 84), "arlington": (12, 84)}
# name: (actor, footprint x0, y0, x1, y1, capture x0, y0, x1, y1, open side (dx, dy))
LANDMARKS = {
    "lincoln": ("dclincoln", (32, 46, 40, 55), (34, 51, 38, 55), (0, 1)),       # faces the pool: capture from the south
    "monument": ("dcmonument", (62, 49, 66, 53), (62, 49, 66, 53), (0, 1)),
    "capitol": ("dccapitol", (109, 46, 123, 56), (109, 49, 113, 53), (-1, 0)),
    "whitehouse": ("dcwhitehouse", (59, 14, 69, 21), (62, 17, 66, 21), (0, 1)),
    "jefferson": ("dcjefferson", (59, 79, 66, 86), (60, 82, 64, 86), (0, 1)),
}
TREE_TYPES = ["t01", "t02", "t03", "t05", "t06", "t07", "t12", "t13"]


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
    river = river_d < RIVER_W / 2
    # Virginia: the land west / south-west of the river
    lab, _ = ndimage.label(~river)
    virginia = lab == lab[90, 2]
    bridges = (band(BRIDGE1, 5.5) | band(BRIDGE2, 5.5)) & river
    pool = rect(*POOL)
    basin = ell(*BASIN)
    water = (river | pool | basin) & ~bridges

    # Wide roads: named avenues 5 cells, the street grid 4 cells (diagonals wider so 3 tanks fit side by side)
    avenues = (rect(18, 39, NX, 44) | rect(20, 58, NX, 63) | rect(70, 0, 75, NY) | rect(44, 0, 48, 39)
               | rect(86, 0, 90, 39) | rect(86, 63, 90, NY) | rect(98, 24, 102, 39) | rect(36, 23, 70, 27)
               | band([(75, 27), (108, 41)], 5.5) | band([BRIDGE2[1], (66, 80), (102, 80)], 5.5) | rect(75, 2, NX, 6)
               | rect(33, 0, 37, 39) | rect(57, 0, 59, 12) | rect(102, 63, 106, NY) | rect(75, 70, NX, 74)
               | band([BRIDGE1[1], (34, 60.5)], 5.5) | rect(34, 63, 38, NY) | rect(38, 88, 56, 92))
    virginia_roads = band([(12, 74), BRIDGE1[0]], 5.5) | band([(12, 74), BRIDGE2[0]], 5.5)
    # The bridges' approaches on both banks are road too (bridges above is only the deck over the water)
    streets = ((avenues & ~virginia) | (virginia_roads & virginia) | band(BRIDGE1, 5.5) | band(BRIDGE2, 5.5)) & ~water
    lot = np.zeros((NY, NX), bool)
    for sx, sy in SPAWNS.values():
        lot |= rect(sx - LOT, sy - LOT, sx + LOT, sy + LOT)
    mall = rect(*MALL) & ~virginia
    parks = (ell(*ELLIPSE) | rect(*WH_PARK) | ell(62, 89, 10, 6) | ell(64, 51, 7, 7)) & ~virginia
    footprints = np.zeros((NY, NX), bool)
    for name, (_, fp, _, _) in LANDMARKS.items():
        footprints |= rect(*fp)
        lean = math.ceil(HEIGHTS[name] * SHEAR / CELL)
        if name == "monument":                            # the obelisk: a narrow column of lean
            footprints |= rect(fp[0] + 1, fp[1] - lean, fp[2] - 1, fp[1])
        else:
            footprints |= rect(fp[0], fp[1] - lean, fp[2], fp[1])

    # Resources: an equal field next to each base (outside it), two contested gem fields
    ore = np.zeros((NY, NX), bool)
    for name, (sx, sy) in SPAWNS.items():
        ox = sx + (LOT + 4) * (1 if sx < NX / 2 else -1)
        ore |= ell(ox, sy, 2.5, 5.0)
    gems = ell(90, 51, 3.0, 1.8) | ell(44, 30, 3.0, 1.8)
    ore &= ~water & ~streets & ~lot
    gems &= ~water

    open_ground = water | streets | lot | mall | parks | footprints | ore | gems | virginia | bridges
    # City blocks: everything else, solid; small scraps (< 3 cells across) become sidewalk
    blocks = ~open_ground
    blocks = ndimage.binary_opening(blocks, structure=np.ones((3, 3)))
    taken = blocks.copy()
    buildings = pack_buildings(blocks)
    grid = np.zeros((NY, NX), np.uint8)
    grid[taken | footprints] = 2
    grid[water] = 1
    # Capture points must not be blocked cells for the actor (they are its own footprint), and the landmark
    # footprint stays blocked round them
    surface = np.zeros((NY, NX), np.uint8)
    surface[streets & (grid == 0)] = 1

    ground = np.full((NY, NX), "c", dtype="<U1")   # c sidewalk, a asphalt, p plaza, y lawn, q quay, w woods
    ground[virginia & ~water] = "w"
    ground[mall | parks | lot] = "y"
    ground[streets] = "a"
    quay = ndimage.binary_dilation(water, iterations=1) & ~water & ~bridges
    ground[quay & (grid == 0)] = "q"
    for name, (_, fp, cap, _) in LANDMARKS.items():
        ground[rect(fp[0] - 1, fp[1] - 1, fp[2] + 1, fp[3] + 1) & (grid == 0) & ~streets] = "p"

    res = np.zeros((NY, NX), np.uint8)
    res[ore] = 1
    res[gems] = 2

    # Trees: Virginia woods (not on roads, the base, or the shore) and two rows along the Mall
    trees = []
    shore = ndimage.binary_dilation(water, iterations=2)
    keep_clear = lot | streets | shore | ore | ndimage.binary_dilation(footprints, iterations=2)
    for name, (_, fp, cap, (dx, dy)) in LANDMARKS.items():                # the ground in front of each landmark
        keep_clear |= rect(cap[0] - 7, cap[1] - 7, cap[2] + 7, cap[3] + 7)
    for y in range(1, NY - 1):
        for x in range(1, NX - 1):
            if grid[y, x] or keep_clear[y, x] or res[y, x]:
                continue
            p = 0
            if virginia[y, x]:
                p = 30
            elif mall[y, x] and y in (45, 56) and x % 3 == 0 and not (60 < x < 68):
                p = 90
            if p and h32("tree", x, y) % 100 < p:
                trees.append((x, y))
    tree_cells = np.zeros((NY, NX), bool)
    for x, y in trees:
        tree_cells[y, x] = True

    os.makedirs(BUILD, exist_ok=True)
    spawns = list(SPAWNS.values())
    check(grid | tree_cells * 2, res, spawns, rect)
    actors = [(name, act, ((cap[0] + cap[2]) // 2, (cap[1] + cap[3]) // 2)) for name, (act, _, cap, _) in LANDMARKS.items()]
    # The capture point cells are part of the landmark footprint (blocked for movement anyway); the actor occupies them
    write_map(grid, res, spawns, surface, actors, trees)
    write_water_flow(water, river_d, pool | basin)
    write_ground_masks(ground, water)
    layout = {
        "cell_m": CELL, "cells": [NX, NY], "river": RIVER, "river_w": RIVER_W,
        "grid": ["".join(".~#"[v] for v in row) for row in grid],
        "ground": ["".join(row) for row in ground],
        "resources": ["".join(" og"[v] for v in row) for row in res],
        "buildings": buildings, "spawns": [list(s) for s in spawns], "lot": LOT, "trees": trees,
        "landmarks": {k: list(v[1]) for k, v in LANDMARKS.items()},
        "captures": {k: list(v[2]) for k, v in LANDMARKS.items()},
        "pool": POOL, "basin": BASIN, "bridges": [BRIDGE1, BRIDGE2], "heights": HEIGHTS,
    }
    with open(os.path.join(BUILD, "layout.json"), "w") as f:
        json.dump(layout, f, separators=(",", ":"))
    print(f"{NX}x{NY} cells: blocked {int((grid == 2).sum())}, water {int((grid == 1).sum())}, ore {int(ore.sum())}, "
          f"gems {int(gems.sum())}, houses {len(buildings)}, trees {len(trees)}")
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
            district = "federal" if 40 < x < 100 and 24 < y < 70 else "downtown" if y < 40 else "southwest"
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
    for name, (_, fp, cap, (dx, dy)) in LANDMARKS.items():
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
    yaml = ("MapFormat: 12\n\nRequiresMod: ra\n\nTitle: Washington D.C.\n\nAuthor: RedAlert Project X\n\n"
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
    """PxBackdropWater flow map: R water, G flow angle (0.5 = west), B bank distance. The Potomac flows south-east
    along its line; the Reflecting Pool and the Tidal Basin barely move."""
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
        tx[sel], ty[sel] = (bx - ax) / n, (by - ay) / n
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
    """ground_a.png: R asphalt, G plaza, B lawn, A quay; water.png: water. `ppm` pixels per metre, soft edges.
    woods.png: the Virginia woods ground."""
    s = int(CELL * ppm)
    layers = []
    for keys in ("a", "p", "yw", "q"):                  # the Virginia woods' floor is grass too (trees are actors)
        m = np.isin(ground, list(keys)).astype(np.uint8) * 255
        layers.append(np.asarray(Image.fromarray(np.repeat(np.repeat(m, s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 1.2))))
    Image.fromarray(np.stack(layers, -1)).save(os.path.join(BUILD, "ground_a.png"))
    w = Image.fromarray(np.repeat(np.repeat((water * 255).astype(np.uint8), s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 2.5))
    Image.fromarray(np.where(np.asarray(w) > 127, 255, 0).astype(np.uint8)).filter(ImageFilter.GaussianBlur(ppm * 0.6)).save(os.path.join(BUILD, "water.png"))
    m = (ground == "w").astype(np.uint8) * 255
    Image.fromarray(np.repeat(np.repeat(m, s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 2)).save(os.path.join(BUILD, "woods.png"))


def write_plan(path, grid, res, ground, spawns, trees, S=8):
    from PIL import ImageDraw
    img = np.zeros((NY, NX, 3), np.uint8)
    img[:] = (190, 192, 180)
    img[ground == "a"] = (110, 112, 120)
    img[ground == "y"] = (120, 170, 100)
    img[ground == "w"] = (90, 130, 80)
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
        d.rectangle([cap[0] * S, cap[1] * S, cap[2] * S, cap[3] * S], outline=(255, 0, 255), width=3)
    im.save(path)


if __name__ == "__main__":
    main()
