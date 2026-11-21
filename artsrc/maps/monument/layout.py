#!/usr/bin/env python3
"""
Monument City (IDEA-28 painted map): a small 4-player imaginary American city on a sunny summer day.

  python3 artsrc/maps/monument/layout.py [--plan build/plan.png]

Output: mods/rapx/maps/monument-city/{map.yaml, map.bin, map.png, water-flow.png}   the playable 4-player map
        artsrc/maps/monument/build/{layout.json, ground_a.png, water.png}       the same design for build_backdrop.py

Scale: 7 m per cell, 96 x 96 cells = 672 x 672 m. North is up. 4-fold rotational symmetry (the NW quadrant is designed
once and rotated): every base gets the same ground; each quarter has different landmark art.

  a base in each corner (24 x 24 cells, nothing in it but grass), its ore field across the avenue
  a landmark plaza in the middle of each edge, between two bases, each landmark capturable and paying like an oil
  derrick only more (MCCAPITOL north, MCTOWER east, MCPENTAGON south, MCRUSHMORE west), gems in front of each
  the harbour in the middle with Liberty Island (Statue of Liberty), a promenade ring road round it
  a Manhattan avenue grid with two diagonal Broadways that cut wedge blocks (Flatiron); city blocks cut by alleys

Gameplay layer: water -> Water, buildings / landmarks / island -> Rock, avenues -> Road, alleys -> Rough, rest Clear.
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
MAP_DIR = os.path.join(ROOT, "mods", "rapx", "maps", "monument-city")

CELL = 7.0
N = 96
C = N / 2
CLEAR, WATER, ROCK = 255, 1, 57          # TEMPERAT templates: clear (16 variants), water, a 1x1 rock
ROAD, ROUGH = (228, 0), (47, 4)          # TEMPERAT template tiles: road (vehicles +25%), rough (wheeled -50%)
# Quarter k (rotation of the NW quadrant) -> which landmark is at the edge midpoint it holds
QUARTERS = ["capitol", "rushmore", "pentagon", "tower"]     # N, W, S, E
ACTORS = {"capitol": "mccapitol", "rushmore": "mcrushmore", "pentagon": "mcpentagon", "tower": "mctower"}

RING = (4.2, 13.0)                       # harbour: island radius, harbour outer radius
PROMENADE = (13.0, 16.0)
LOT = 12                                 # half size of a build area (24 x 24 cells)
SPAWN = (15, 15)                         # NW start; rotated for the others
PLAZA = (38, 1, 58, 22)                  # north landmark plaza (straddles the quadrant edge; symmetric about x = 48)
LANDMARK = (42, 3, 54, 14)               # its blocked footprint
# Gems beside the landmark on its far side: buildings cannot stand on resources, so the plaza in front of the
# landmark (where an owner builds round it) stays free of them
GEMS = [(40, 6), (56, 6)]
CAPTURE = (46, LANDMARK[3] - 4, 50, LANDMARK[3])   # the capture point's 4x4 cells, on the landmark's inner edge
BASE_ORE = (34.5, 13)                    # the NW base's ore field: the block east of it, across the avenue (never
#                                          inside a build area: buildings cannot stand on ore)


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

    water = (r >= RING[0]) & (r < RING[1])
    island = r < RING[0]
    promenade = (r >= PROMENADE[0]) & (r < PROMENADE[1])
    # Avenues are 3 cells wide (check_paths wants tank columns to get through)
    avenues = sym(rect(0, 27, 48, 30) | rect(27, 0, 30, 48) | rect(0, 40, 36, 43) | rect(40, 24, 43, 36) | rect(18, 28, 21, 48))
    broadway = sym((np.abs((xs - C) - (ys - C)) < 2.3) & (r > PROMENADE[1]) & (r < 34) & (xs < C))
    streets = (avenues | broadway | promenade) & ~water & ~island

    spawns = [tuple(int(v) for v in rot(SPAWN, k)) for k in range(4)]
    lot = np.zeros((N, N), bool)
    for sx, sy in spawns:
        lot |= (np.abs(xs - sx) < LOT) & (np.abs(ys - sy) < LOT)
    plaza = sym(rect(*PLAZA))
    landmark = sym(rect(*LANDMARK))

    def ellipse(cx, cy, rx, ry):
        return ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 <= 1

    ore = np.zeros((N, N), bool)
    gems = np.zeros((N, N), bool)
    for k, (sx, sy) in enumerate(spawns):                 # one field next to each base, across the avenue
        ox, oy = rot(BASE_ORE, k)
        ore |= ellipse(ox, oy, 2.4, 5.0) if k % 2 == 0 else ellipse(ox, oy, 5.0, 2.4)
        for g in GEMS:                                    # two small fields in the plaza's back corners
            gems |= ellipse(*rot(g, k), 1.6, 2.6) if k % 2 == 0 else ellipse(*rot(g, k), 2.6, 1.6)

    open_ground = water | island | streets | lot | plaza | ore | gems
    alleys = (np.abs(xs % 7 - 3.5) < 0.6) | (np.abs(ys % 7 - 3.5) < 0.6)
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
            all_buildings.append(dict(b, rect=rot_rect(b["rect"], k), district=QUARTERS[k]))

    grid = np.zeros((N, N), np.uint8)       # 0 clear, 1 water, 2 blocked
    grid[houses | landmark | island] = 2
    grid[water] = 1
    surface = np.zeros((N, N), np.uint8)    # 0 clear, 1 road, 2 rough (alleys)
    surface[streets & (grid == 0)] = 1
    surface[~open_ground & ~houses & (grid == 0)] = 2

    ground = np.full((N, N), "c", dtype="<U1")   # c sidewalk / alley, a asphalt, p plaza, y lawn, q quay
    ground[streets] = "a"
    ground[plaza] = "p"
    ground[lot] = "y"
    quay = ndimage.binary_dilation(water, iterations=1) & ~water & ~island
    ground[quay & (grid == 0)] = "q"

    res = np.zeros((N, N), np.uint8)
    res[ore] = 1
    res[gems] = 2

    os.makedirs(BUILD, exist_ok=True)
    check_paths(grid, spawns)
    # The plaza in front of each landmark and beside it must take buildings too (owners build round it)
    for k in range(4):
        fx0, fy0, fx1, fy1 = (int(v) for v in rot_rect((PLAZA[0], LANDMARK[3], PLAZA[2], PLAZA[3]), k))
        area = (slice(fy0, fy1), slice(fx0, fx1))
        assert not grid[area].any() and not res[area].any(), f"{QUARTERS[k]}: blocked cells or resources in front of it"
    for sx, sy in spawns:                                  # the whole build area must take buildings
        area = (slice(sy - LOT, sy + LOT), slice(sx - LOT, sx + LOT))
        assert not grid[area].any() and not res[area].any(), f"start {sx},{sy}: blocked cells or resources in the build area"
    lm_actors = []
    for k, q in enumerate(QUARTERS):
        # The 4x4 capture point sits at the landmark's edge facing the map centre: an engineer has to reach a cell
        # next to it (in the middle of the blocked landmark it could never be captured)
        x0, y0, x1, y1 = rot_rect(CAPTURE, k)
        lm_actors.append((q.capitalize(), ACTORS[q], (int(x0) + 2, int(y0) + 2)))
    write_map(grid, res, spawns, surface, lm_actors)
    write_water_flow(water, water)
    write_ground_masks(ground, water)
    landmarks = {q: rot_rect(LANDMARK, k) for k, q in enumerate(QUARTERS)}
    landmarks["plazas"] = {q: rot_rect(PLAZA, k) for k, q in enumerate(QUARTERS)}
    landmarks["liberty"] = [C, C, RING[0]]
    layout = {
        "cell_m": CELL, "cells": [N, N], "ring": RING,
        "grid": ["".join(".~#"[v] for v in row) for row in grid],
        "ground": ["".join(row) for row in ground],
        "resources": ["".join(" og"[v] for v in row) for row in res],
        "buildings": all_buildings, "bridges": [], "spawns": [list(s) for s in spawns],
        "landmarks": landmarks, "lot": LOT,
    }
    with open(os.path.join(BUILD, "layout.json"), "w") as f:
        json.dump(layout, f, separators=(",", ":"))
    print(f"{N}x{N} cells: blocked {int((grid == 2).sum())}, water {int((grid == 1).sum())}, ore {int(ore.sum())}, "
          f"gems {int(gems.sum())}, houses {len(all_buildings)}")
    if a.plan:
        write_plan(a.plan, grid, res, ground, spawns)


def check_paths(grid, spawns):
    """Every start must reach every other start and every landmark plaza by land, 3 cells wide (tanks queue badly
    through 1-cell alleys)."""
    passable = grid == 0
    labels, _ = ndimage.label(passable)
    region = labels[spawns[0][1], spawns[0][0]]
    for sx, sy in spawns:
        assert labels[sy, sx] == region, f"start {sx},{sy} is cut off"
    wide = ndimage.binary_erosion(passable, structure=np.ones((3, 3)))
    wlabels, _ = ndimage.label(ndimage.binary_dilation(wide, structure=np.ones((3, 3))) & passable)
    wregion = wlabels[spawns[0][1], spawns[0][0]]
    for sx, sy in spawns:
        assert wlabels[sy, sx] == wregion, f"start {sx},{sy} has no 3-wide way to the others"


def write_map(grid, res, spawns, surface, landmarks):
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
    # The four landmarks: 4x4 capture points centred on (lx, ly)
    for name, actor, (lx, ly) in landmarks:
        actors.append(f"\t{name}: {actor}\n\t\tOwner: Neutral\n\t\tLocation: {lx - 2 + 1},{ly - 2 + 1}\n")

    names = [f"Multi{k}" for k in range(4)]
    players = ["\tPlayerReference@Neutral:\n\t\tName: Neutral\n\t\tOwnsWorld: True\n\t\tNonCombatant: True\n"
               "\t\tFaction: allies\n",
               "\tPlayerReference@Creeps:\n\t\tName: Creeps\n\t\tNonCombatant: True\n\t\tFaction: allies\n"
               f"\t\tEnemies: {', '.join(names)}\n"]
    for n in names:
        players.append(f"\tPlayerReference@{n}:\n\t\tName: {n}\n\t\tPlayable: True\n\t\tFaction: Random\n"
                       f"\t\tEnemies: Creeps\n")
    yaml = ("MapFormat: 12\n\nRequiresMod: ra\n\nTitle: Monument City\n\nAuthor: RedAlert Project X\n\n"
            f"Tileset: TEMPERAT\n\nMapSize: {W},{H}\n\nBounds: 1,1,{N},{N}\n\nVisibility: Lobby\n\n"
            "Categories: Conquest\n\nPlayers:\n" + "".join(players) + "\nActors:\n" + "".join(actors) +
            "\nRules:\n\tWorld:\n\t\tPxWeatherManager:\n\t\t\tFixed: Clear\n")
    with open(os.path.join(MAP_DIR, "map.yaml"), "w") as f:
        f.write(yaml)

    # Lobby preview from the layout (cut_backdrop.py replaces it with a backdrop thumbnail)
    if os.path.exists(os.path.join(MAP_DIR, "backdrop-0-0.png")):
        return
    S = 3
    colors = np.array([(170, 180, 150), (50, 100, 140), (120, 104, 96)], np.uint8)
    img = colors[grid]
    img[res == 1] = (200, 160, 60)
    img[res == 2] = (140, 90, 200)
    Image.fromarray(np.repeat(np.repeat(img, S, 0), S, 1)).save(os.path.join(MAP_DIR, "map.png"))


def write_water_flow(water, ring_cells, ppc=16, bank_cells=2.0):
    """PxBackdropWater flow map from the exact canal shape: R water, G flow angle (0.5 = west), B bank distance.
    The harbour water turns slowly round Liberty Island."""
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
    ground_a.png: R asphalt street, G plaza / sidewalk, B lawn, A harbour quay. water.png: the harbour."""
    s = int(CELL * ppm)
    layers = []
    for keys in ("a", "p", "y", "q"):
        m = np.isin(ground, list(keys)).astype(np.uint8) * 255
        im = Image.fromarray(np.repeat(np.repeat(m, s, 0), s, 1)).filter(ImageFilter.GaussianBlur(ppm * 1.2))
        layers.append(np.asarray(im))
    Image.fromarray(np.stack(layers, -1)).save(os.path.join(BUILD, "ground_a.png"))
    # The harbour is round: draw it from its exact radii instead of the cell steps
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
