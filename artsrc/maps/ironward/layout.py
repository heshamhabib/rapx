#!/usr/bin/env python3
"""
Ironward (IDEA-28 painted map): an 8-player walled prison-city on a moonlit winter night.

  python3 artsrc/maps/ironward/layout.py [--plan build/plan.png]

Output: mods/rapx/maps/ironward/{map.yaml, map.bin, map.png, water-flow.png}   the playable 8-player skirmish map
        artsrc/maps/ironward/build/{layout.json, ground_a.png, water.png}      the same design for build_backdrop.py

Scale: 7 m per cell, 128 x 128 cells = 896 x 896 m. North is up.

The map has 4-fold rotational symmetry: the NW quadrant is designed once and rotated, so every pair of start
positions gets the same ground. Each quadrant is painted as a different district:
  NW Foundry Row (steelworks)   NE Courthouse Hill (museum, bank)   SE Pier Nine (docks)   SW Grey Abbey (asylum)

  outer prison wall with watchtowers and four sealed gates
  canals: a ring round the central island + four arms to the wall, one bridge over each arm, four onto the island
  the island: rich ore and the Warden's Spire (IRSPIRE, capturable, pays its owner like an oil derrick, only more)
  8 start positions on a ring, a pair per quadrant (2v2v2v2 or free-for-all), each with a 28 x 28 build area
  corner yards behind each pair: gems and the district's landmark
  alleys between the gothic blocks: infantry shortcuts; tanks use the streets and the ring road

Gameplay layer: water -> Water, buildings / wall / landmarks -> Rock (impassable), streets and bridges -> Road,
alleys -> Rough (slow for vehicles), everything else -> Clear.
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
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "ironward")

CELL = 7.0
N = 128
C = N / 2
CLEAR, WATER, ROCK = 255, 1, 57          # SNOW templates: clear (16 variants), water, a 1x1 rock
ROAD, ROUGH = (228, 0), (47, 4)          # SNOW template tiles: road (vehicles +25%), rough (wheeled -50%)
DISTRICTS = ["foundry", "abbey", "pier", "courthouse"]   # rotation k of the NW quadrant: NW, SW, SE, NE

SPAWN_RADIUS = 50
LOT = 14                                 # half size of the cleared build area round each start (28 x 28 cells)
WALL = 2.5                               # wall thickness (cells)
RING = (13, 18)                          # canal ring round the island (inner, outer radius)
ARM = (61, 67)                           # canal arms, rows 61..66 (west arm; rotated for the others)
ARM_BRIDGES = [(36, 41)]                 # columns of the bridge over the west arm (one per arm: the bases reach the canal)
SPIRE_R = 4.5
YARD = (15, 15, 10)                      # corner yard centre x, y, radius (NW)
LANDMARK = (6, 6, 13, 13)                # district landmark in the yard (NW)
GEMS = (22, 22)
ISLAND_ORE = (C, C - 8.5)
RIVAL_ORE = (40, 52)                     # next to the arm bridges, between rival quadrants


def h32(*vals):
    return zlib.crc32(repr(vals).encode()) & 0xFFFFFFFF


def rot(p, k=1):
    """Rotate a point (cell coordinates, y down) k times the way np.rot90 rotates the grid."""
    x, y = p
    for _ in range(k):
        x, y = y, N - x
    return x, y


def rot_rect(r, k):
    (ax, ay), (bx, by) = rot((r[0], r[1]), k), rot((r[2], r[3]), k)
    return [min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", help="also write an annotated plan picture")
    a = ap.parse_args()

    ys, xs = np.mgrid[0:N, 0:N] + 0.5
    r = np.hypot(xs - C, ys - C)

    def sym(m):
        return m | np.rot90(m, 1) | np.rot90(m, 2) | np.rot90(m, 3)

    def rect(x0, y0, x1, y1):
        return (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)

    diag = (np.abs((xs - C) - (ys - C)) < 2.6) & (xs < C)       # the NW diagonal
    wall = sym(ys < WALL)
    towers = [(2.5, 2.5)] + [(x, 2) for x in (32, 96)]
    gate = (64, 1.5)

    ring = (r > RING[0]) & (r < RING[1])
    arm = sym(rect(WALL, ARM[0], 47, ARM[1]))
    arm_bridges = np.zeros((N, N), bool)
    for x0, x1 in ARM_BRIDGES:
        arm_bridges |= rect(x0, ARM[0] - 1, x1, ARM[1] + 1)
    bridges = sym(arm_bridges) | (ring & sym(diag))
    water = (ring | arm) & ~bridges

    ring_road = (r > 29) & (r < 33)
    avenues = sym((np.abs((xs - C) - (ys - C)) < 2.2) & (xs < C) & (r > RING[1]))
    streets = ring_road | avenues | sym(rect(WALL, 44, 60, 47) | rect(44, WALL, 47, 60)) | sym(rect(20, WALL, 23, 28))
    # Approach roads: each arm bridge continues as a street, full width, to the streets on both sides of the arm
    approaches = np.zeros((N, N), bool)
    for x0, x1 in ARM_BRIDGES:
        approaches |= rect(x0, 47, x1, ARM[0]) | rect(x0, ARM[1], x1, N - 47)
    streets |= sym(approaches)
    streets &= ~water

    spawns = []
    for k in range(8):
        t = math.radians(22.5 + 45 * k)
        spawns.append((round(C + SPAWN_RADIUS * math.cos(t)), round(C + SPAWN_RADIUS * math.sin(t))))
    lot = np.zeros((N, N), bool)
    for sx, sy in spawns:
        lot |= (np.abs(xs - sx) < LOT) & (np.abs(ys - sy) < LOT)

    yard = sym((np.hypot(xs - YARD[0], ys - YARD[1]) < YARD[2]) & ~wall)
    landmark = sym(rect(*LANDMARK))
    # The 4x4 capture point (cells 62-65) needs an open cell next to it: a passage on its south side
    spire = (r < SPIRE_R) & ~rect(C - 2, C + 2, C + 2, C + SPIRE_R + 1)
    island = r <= RING[0]

    # Resources
    def ellipse(cx, cy, rx, ry):
        return ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 <= 1

    ore = np.zeros((N, N), bool)
    gems = np.zeros((N, N), bool)
    for sx, sy in spawns:                                   # one field behind each base, toward the wall
        dx, dy = sx - C, sy - C
        d = math.hypot(dx, dy)
        ore |= ellipse(sx + dx / d * 11, sy + dy / d * 11, 4.5, 3.5)
    for k in range(4):
        gems |= ellipse(*rot(GEMS, k), 3.2, 3.2)
        ore |= ellipse(*rot(ISLAND_ORE, k), 2.6, 2.6)
        ore |= ellipse(*rot(RIVAL_ORE, k), 3.5, 2.5)
    ore &= ~water
    gems &= ~water

    # Gothic blocks: what is left, cut by alleys; the NW quadrant is split into house lots and rotated
    open_ground = water | streets | lot | yard | island | wall | bridges | ore | gems
    alleys = (np.abs(xs % 9 - 4.5) < 0.9) | (np.abs(ys % 11 - 5.5) < 0.9)
    houses_nw = ~open_ground & ~alleys & rect(0, 0, C, C) & ~landmark
    taken = np.zeros((N, N), bool)
    buildings = []
    for y in range(int(C)):
        for x in range(int(C)):
            if not houses_nw[y, x] or taken[y, x]:
                continue
            wmax, hmax = 3 + h32("w", x, y) % 4, 3 + h32("h", x, y) % 4
            w = 1
            while w < wmax and x + w < C and houses_nw[y, x + w] and not taken[y, x + w]:
                w += 1
            h = 1
            while h < hmax and y + h < C and np.all(houses_nw[y + h, x:x + w] & ~taken[y + h, x:x + w]):
                h += 1
            taken[y:y + h, x:x + w] = True
            seed = h32("b", x, y)
            buildings.append({"rect": [x, y, x + w, y + h], "floors": 3 + seed % 4, "style": seed % 7,
                              "lit": round((seed >> 8) % 100 / 100, 2)})
    houses = sym(taken)
    assert not np.any(taken & np.rot90(taken, 1)), "a house straddles a quadrant edge"
    all_buildings = []
    for k in range(4):
        for b in buildings:
            all_buildings.append(dict(b, rect=rot_rect(b["rect"], k), district=DISTRICTS[k]))

    grid = np.zeros((N, N), np.uint8)       # 0 clear, 1 water, 2 blocked
    grid[houses | wall | landmark | spire] = 2
    grid[water] = 1
    surface = np.zeros((N, N), np.uint8)    # 0 clear, 1 road, 2 rough (alleys)
    surface[(streets | bridges) & (grid == 0)] = 1
    surface[~open_ground & ~houses & (grid == 0)] = 2

    ground = np.full((N, N), "c", dtype="<U1")   # c snowy cobbles, a ploughed street, p plaza, y yard, q canal quay
    ground[streets | bridges] = "a"
    ground[island | lot] = "p"
    ground[yard] = "y"
    quay = ndimage.binary_dilation(ring | arm, iterations=1) & ~(ring | arm) & ~bridges
    ground[quay & (grid == 0)] = "q"

    res = np.zeros((N, N), np.uint8)
    res[ore] = 1
    res[gems] = 2

    os.makedirs(BUILD, exist_ok=True)
    check_paths(grid, spawns)
    write_map(grid, res, spawns, surface)
    write_water_flow(water, ring & ~bridges)
    write_ground_masks(ground, water)
    landmarks = {"spire": [C, C, SPIRE_R],
                 "yards": [[*rot(YARD[:2], k), YARD[2], DISTRICTS[k]] for k in range(4)],
                 "district_landmarks": [rot_rect(LANDMARK, k) + [DISTRICTS[k]] for k in range(4)],
                 "towers": [rot(t, k) for t in towers for k in range(4)],
                 "gates": [rot(gate, k) for k in range(4)]}
    bridge_list = []
    for k in range(4):
        for x0, x1 in ARM_BRIDGES:
            bridge_list.append({"rect": rot_rect([x0, ARM[0] - 1, x1, ARM[1] + 1], k), "kind": "arm"})
        ang = math.radians(225 + 90 * -k)
        bridge_list.append({"centre": [C + math.cos(ang) * (RING[0] + RING[1]) / 2, C + math.sin(ang) * (RING[0] + RING[1]) / 2],
                            "angle": ang, "length": RING[1] - RING[0] + 2, "width": 3.7, "kind": "island"})
    layout = {
        "cell_m": CELL, "cells": [N, N], "wall": WALL, "ring": RING, "arm": ARM,
        "grid": ["".join(".~#"[v] for v in row) for row in grid],
        "ground": ["".join(row) for row in ground],
        "resources": ["".join(" og"[v] for v in row) for row in res],
        "buildings": all_buildings, "bridges": bridge_list, "spawns": [list(s) for s in spawns],
        "landmarks": landmarks,
    }
    with open(os.path.join(BUILD, "layout.json"), "w") as f:
        json.dump(layout, f, separators=(",", ":"))
    print(f"{N}x{N} cells: blocked {int((grid == 2).sum())}, water {int((grid == 1).sum())}, ore {int(ore.sum())}, "
          f"gems {int(gems.sum())}, houses {len(all_buildings)}")
    if a.plan:
        write_plan(a.plan, grid, res, ground, spawns)


def check_paths(grid, spawns):
    """Every start must reach every other start and the Spire by land, and each arm bridge needs a 3-cell-wide way
    on and off (tanks queue badly through 1-cell alleys)."""
    passable = grid == 0
    labels, _ = ndimage.label(passable)
    region = labels[spawns[0][1], spawns[0][0]]
    for sx, sy in spawns:
        assert labels[sy, sx] == region, f"start {sx},{sy} is cut off"
    assert labels[int(C) - 6, int(C)] == region, "the Spire island is cut off"
    wide = ndimage.binary_erosion(passable, structure=np.ones((3, 3)))
    wlabels, _ = ndimage.label(ndimage.binary_dilation(wide, structure=np.ones((3, 3))) & passable)
    wregion = wlabels[spawns[0][1], spawns[0][0]]
    for sx, sy in spawns:
        assert wlabels[sy, sx] == wregion, f"start {sx},{sy} has no 3-wide way to the others"


def write_map(grid, res, spawns, surface):
    os.makedirs(MAP_DIR, exist_ok=True)
    W = H = N + 2                                         # one border cell on each side (Bounds: 1,1,N,N)
    tiles = bytearray()
    resources = bytearray()
    for i in range(W):
        for j in range(H):
            x, y = min(max(i - 1, 0), N - 1), min(max(j - 1, 0), N - 1)
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
    # The Warden's Spire: a 4x4 capture point at the centre
    actors.append(f"\tSpire: irspire\n\t\tOwner: Neutral\n\t\tLocation: {int(C) - 2 + 1},{int(C) - 2 + 1}\n")

    names = [f"Multi{k}" for k in range(8)]
    players = ["\tPlayerReference@Neutral:\n\t\tName: Neutral\n\t\tOwnsWorld: True\n\t\tNonCombatant: True\n"
               "\t\tFaction: allies\n",
               "\tPlayerReference@Creeps:\n\t\tName: Creeps\n\t\tNonCombatant: True\n\t\tFaction: allies\n"
               f"\t\tEnemies: {', '.join(names)}\n"]
    for n in names:
        players.append(f"\tPlayerReference@{n}:\n\t\tName: {n}\n\t\tPlayable: True\n\t\tFaction: Random\n"
                       f"\t\tEnemies: Creeps\n")
    yaml = ("MapFormat: 12\n\nRequiresMod: ra\n\nTitle: Ironward\n\nAuthor: RedAlert Project X\n\n"
            f"Tileset: SNOW\n\nMapSize: {W},{H}\n\nBounds: 1,1,{N},{N}\n\nVisibility: Lobby\n\n"
            "Categories: Conquest\n\nPlayers:\n" + "".join(players) + "\nActors:\n" + "".join(actors) +
            "\nRules:\n\tWorld:\n\t\tPxWeatherManager:\n\t\t\tAllowed: Snow, Blizzard\n\t\t\tClearChance: 0\n")
    with open(os.path.join(MAP_DIR, "map.yaml"), "w") as f:
        f.write(yaml)

    # Lobby preview from the layout (cut_backdrop.py replaces it with a backdrop thumbnail)
    if os.path.exists(os.path.join(MAP_DIR, "backdrop-0-0.png")):
        return
    S = 3
    colors = np.array([(205, 210, 220), (40, 70, 100), (80, 78, 92)], np.uint8)
    img = colors[grid]
    img[res == 1] = (200, 160, 60)
    img[res == 2] = (140, 90, 200)
    Image.fromarray(np.repeat(np.repeat(img, S, 0), S, 1)).save(os.path.join(MAP_DIR, "map.png"))


def write_water_flow(water, ring_cells, ppc=16, bank_cells=2.0):
    """PxBackdropWater flow map from the exact canal shape: R water, G flow angle (0.5 = west), B bank distance.
    The canals are near still: the water drifts slowly away from the island along the arms and round the ring."""
    up = np.repeat(np.repeat(water, 4, 0), 4, 1)
    cover = np.asarray(Image.fromarray((up * 255).astype(np.uint8)).resize((N * ppc, N * ppc), Image.BILINEAR), np.float32) / 255
    cover = ndimage.gaussian_filter(cover, 1.2)
    cover = np.clip((cover - 0.15) / 0.7, 0, 1)
    py, px = (np.mgrid[0:N * ppc, 0:N * ppc] + 0.5) / ppc
    dx, dy = px - C, py - C
    rr = np.hypot(dx, dy)
    # The ring is painted round: replace its stepped cells with the exact annulus (bridges still cut it)
    near_ring = (rr > RING[0] - 1.5) & (rr < RING[1] + 1.5)
    exact = np.clip(np.minimum(rr - RING[0] - 0.3, RING[1] - 0.3 - rr) * ppc / 2 + 0.5, 0, 1)
    ring_up = np.repeat(np.repeat(ring_cells, ppc, 0), ppc, 1)
    exact *= ndimage.gaussian_filter(ring_up.astype(np.float32), 1.2) > 0.5
    cover = np.where(near_ring & ~np.repeat(np.repeat(water & ~ring_cells, ppc, 0), ppc, 1), exact, cover)
    # Along the arms: outward; round the ring: clockwise
    ang_out = np.arctan2(dy, dx)
    ang_ring = ang_out + math.pi / 2
    t = np.clip((rr - 18) / 4, 0, 1)
    vx = np.cos(ang_ring) * (1 - t) + np.cos(ang_out) * t
    vy = np.sin(ang_ring) * (1 - t) + np.sin(ang_out) * t
    angle = np.arctan2(vy, vx) - math.pi
    angle = (angle + math.pi) % (2 * math.pi) - math.pi
    bank = ndimage.distance_transform_edt(cover > 0.5) / ppc
    size = 1 << (N * ppc - 1).bit_length()
    out = np.zeros((size, size, 4), np.uint8)
    out[..., 3] = 255
    out[:N * ppc, :N * ppc, 0] = np.round(cover * 255)
    out[:N * ppc, :N * ppc, 1] = np.round((angle / (2 * math.pi) + 0.5) * 255)
    out[:N * ppc, :N * ppc, 2] = np.round(np.clip(bank / bank_cells, 0, 1) * 255)
    Image.fromarray(out).save(os.path.join(MAP_DIR, "water-flow.png"), optimize=True)


def write_ground_masks(ground, water, ppm=2):
    """Ground masks for the Blender scene, `ppm` pixels per metre, soft edges.
    ground_a.png: R ploughed street, G plaza, B yard, A canal quay. water.png: the canals."""
    s = int(CELL * ppm)
    layers = []
    for keys in ("a", "p", "y", "q"):
        m = np.isin(ground, list(keys)).astype(np.uint8) * 255
        im = Image.fromarray(np.repeat(np.repeat(m, s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 1.2))
        layers.append(np.asarray(im))
    Image.fromarray(np.stack(layers, -1)).save(os.path.join(BUILD, "ground_a.png"))
    # The canal ring is round: draw it from its exact radii instead of the cell steps
    py, px = (np.mgrid[0:N * s, 0:N * s] + 0.5) / s
    rr = np.hypot(px - C, py - C)
    ring = np.clip(np.minimum(rr - RING[0], RING[1] - rr) * s / 2 + 0.5, 0, 1)
    cells = np.asarray(Image.fromarray(np.repeat(np.repeat((water * 255).astype(np.uint8), s, 0), s, 1))
                       .filter(ImageFilter.GaussianBlur(ppm * 0.6)), np.float32) / 255
    near_ring = (rr > RING[0] - 1.5) & (rr < RING[1] + 1.5)
    w = np.where(near_ring, np.minimum(ring, np.clip(cells * 3, 0, 1)), cells)
    Image.fromarray((w * 255).astype(np.uint8)).save(os.path.join(BUILD, "water.png"))


def write_plan(path, grid, res, ground, spawns, S=8):
    from PIL import ImageDraw
    img = np.zeros((N, N, 3), np.uint8)
    img[:] = (190, 196, 208)
    img[ground == "a"] = (120, 124, 136)
    img[(ground == "p") | (ground == "y")] = (160, 164, 176)
    img[grid == 2] = (70, 66, 80)
    img[grid == 1] = (30, 60, 90)
    img[res == 1] = (214, 170, 60)
    img[res == 2] = (160, 100, 220)
    im = Image.fromarray(np.repeat(np.repeat(img, S, 0), S, 1))
    d = ImageDraw.Draw(im)
    for i, (sx, sy) in enumerate(spawns):
        d.ellipse([sx * S - 18, sy * S - 18, sx * S + 18, sy * S + 18], fill=(230, 60, 60), outline=(0, 0, 0), width=2)
        d.text((sx * S, sy * S), str(i + 1), fill=(0, 0, 0), anchor="mm")
    im.save(path)


if __name__ == "__main__":
    main()
