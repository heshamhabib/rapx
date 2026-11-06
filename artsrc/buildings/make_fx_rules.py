#!/usr/bin/env python3
"""
Writes mods/rapx/rules/hd-building-fx.yaml: the live effects of the HD buildings.

Every HD building gets
  WithPxCollapse   sinks into the ground with dust and debris when destroyed, leaves a burning scorch mark
  WithPxDamageFx   smoke when damaged, black smoke + fire when heavily damaged (spots picked from the sprite)
and the buildings listed in FX get their own effects (WithPxBuildingFx@n): chimney smoke/steam,
pulsing reactors, blinking and rotating lights, electric arcs, welding sparks while producing.

FX positions are pixels in the HD sprite (mods/rapx/bits/hd/<id>.png, open it in any image editor);
this script converts them to screen offsets using the sprite's sequence Offset.
Re-run after rebuilding the buildings (build_all.py).

National styles (sequences/hd-structures-styles.yaml) get the same collapse/damage FX and their own live effects,
found automatically in the styled sprite (style_fx): glowing lamps/cores pulse, the highest spires blink,
chimneys steam, factories throw welding sparks while producing. The default effects are switched off for those
nations with a GrantConditionOnFaction condition. Check the spots with --preview (writes artsrc/buildings/preview/).

  python3 artsrc/buildings/make_fx_rules.py
"""
import os
import re
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion, binary_opening, label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
HD = os.path.join(ROOT, "mods", "rapx", "bits", "hd")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-structures.yaml")
STRUCTURES = os.path.join(ROOT, "mods", "rapx", "rules", "structures.yaml")
STYLE_SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-structures-styles.yaml")
OUT = os.path.join(ROOT, "mods", "rapx", "rules", "hd-building-fx.yaml")
PREVIEW = os.path.join(HERE, "preview")
DENSITY = 3.0

# Colours
STEAM = "E8ECEEB0"
SMOKE = "8A8580C0"
SOOT = "3C3834D0"
DUST = "B4A58AA0"
ORANGE = "FF9A3A"
AMBER = "FFB040"
RED = "FF3020"
GREEN = "60FF80"
BLUE = "70B0FF"
WHITE = "FFFFFF"


def steam(x, y, size=1.0, **kw):
    return {**dict(Type="Steam", Offset=(x, y), Color=STEAM, Size=size, Rate=5, Life=60, Radius=(3, 1.5)), **kw}


def smoke(x, y, size=1.0, color=SMOKE, **kw):
    return {**dict(Type="Smoke", Offset=(x, y), Color=color, Size=size, Rate=6, Life=90, Radius=(2, 1)), **kw}


def pulse(x, y, color, size=1.0, period=60, lo=0.25, hi=0.8, **kw):
    return dict(Type="Pulse", Offset=(x, y), Color=color, Size=size, Period=period, MinAlpha=lo, MaxAlpha=hi, **kw)


def blink(x, y, color=RED, size=0.6, period=50, **kw):
    return dict(Type="Blink", Offset=(x, y), Color=color, Size=size, Period=period, **kw)


def beacon(x, y, color=AMBER, size=0.8, period=36, **kw):
    return dict(Type="Beacon", Offset=(x, y), Color=color, Size=size, Period=period, Radius=(2, 0), **kw)


def arcs(x, y, rx, ry, color=BLUE, size=0.7, rate=8, **kw):
    return dict(Type="Arcs", Offset=(x, y), Radius=(rx, ry), Color=color, Size=size, Rate=rate, **kw)


def sparks(x, y, rx, ry, rate=6, producing=True, **kw):
    fx = dict(Type="Sparks", Offset=(x, y), Radius=(rx, ry), Color="FFC070", Size=0.7, Rate=rate, **kw)
    if producing:
        fx["OnlyWhileProducing"] = "true"
    return fx


def chase(points, color, period=40, **kw):
    """Lights flashing one after another."""
    step = period // len(points)
    return [blink(x, y, color, period=period, Phase=i * step, **kw) for i, (x, y) in enumerate(points)]


FX = {
    "powr": [steam(70, 24), steam(108, 40)],
    "apwr": [
        steam(85, 30, 1.3), steam(167, 46, 1.3),
        pulse(80, 92, ORANGE, 1.1, period=56), pulse(113, 100, ORANGE, 1.1, period=62), pulse(147, 108, ORANGE, 1.1, period=50),
    ],
    "stek": [
        pulse(85, 36, ORANGE, 1.4, period=40, lo=0.4, hi=0.9), pulse(168, 48, ORANGE, 1.4, period=46, lo=0.4, hi=0.9),
        smoke(85, 32, 1.1, SOOT), smoke(168, 44, 1.1, SOOT),
        arcs(57, 47, 6, 5), arcs(191, 69, 6, 5),
        *chase([(52, 135), (75, 163), (124, 173), (157, 153)], AMBER, period=80, size=0.5),
    ],
    "proc": [smoke(60, 40, 0.8), smoke(100, 62, 0.6, DUST, Life=45), beacon(108, 8, AMBER, 0.6)],
    "dome": [
        dict(Type="Orbit", Offset=(80, 52), Radius=(27, 9), Color=GREEN, Size=0.8, Period=90, MinAlpha=0.05, MaxAlpha=0.9),
        blink(38, 10, RED, period=45), blink(126, 44, RED, period=55),
    ],
    "fact": [
        beacon(63, 20, AMBER), blink(216, 30, RED, period=40),
        sparks(150, 110, 25, 10), sparks(90, 162, 18, 5, rate=9),
    ],
    "weap": [
        smoke(65, 15, 0.9, OnlyWhileProducing="true"), smoke(188, 34, 0.9, OnlyWhileProducing="true"),
        sparks(85, 140, 25, 8), blink(32, 112, AMBER, period=60), blink(133, 128, AMBER, period=60, Phase=30),
    ],
    "tsla": [pulse(57, 6, BLUE, 1.3, period=30, lo=0.3, hi=0.9), arcs(57, 9, 17, 6, rate=4)],
    "gap": [pulse(40, 22, BLUE, 1.7, period=70, lo=0.3, hi=0.85), arcs(40, 22, 9, 9, rate=12, size=0.5)],
    "pdox": [pulse(78, 46, BLUE, 2.6, period=90, lo=0.15, hi=0.6), arcs(78, 46, 18, 18, rate=9, size=0.6), blink(80, 10, WHITE)],
    "iron": [pulse(100, 30, RED, 1.7, period=60, lo=0.3, hi=0.9), blink(115, 98, AMBER, period=70)],
    "atek": [pulse(75, 60, BLUE, 1.6, period=90, lo=0.1, hi=0.5), blink(104, 18, RED, period=50), *chase([(10, 88), (115, 110)], AMBER, period=60)],
    "hpad": [beacon(113, 20, RED, 0.7), *chase([(48, 40), (165, 40), (175, 92), (40, 90)], GREEN, period=60, size=0.45)],
    "fix": [*chase([(73, 22), (200, 50), (155, 135), (30, 95)], GREEN, period=48, size=0.6), sparks(110, 112, 20, 8, rate=20, producing=False)],
    "syrd": [blink(65, 20, RED, period=45), beacon(150, 25, AMBER, 0.7), sparks(95, 75, 15, 5)],
    "spen": [blink(40, 35, RED, period=50), blink(205, 55, RED, period=50, Phase=25), sparks(115, 100, 18, 5)],
    "barr": [beacon(32, 20, RED, 0.6), blink(95, 96, AMBER, period=70)],
    "tent": [blink(66, 10, RED, period=50), blink(118, 12, RED, period=50, Phase=25)],
    "mslo": [*chase([(93, 241), (256, 219), (76, 171)], RED, period=40)],   # corner lamps of the 3D silo
    "silo": [steam(40, 12, 0.5, Rate=12)],
    "oilr": [
        dict(Type="Flame", Offset=(13, 34), Color="FFFFFF", Size=0.9, Rate=1.5, Life=90, Radius=(2, 1)),
        blink(113, 4, RED, period=50), steam(150, 62, 0.6, Rate=9), sparks(128, 150, 14, 5, rate=30, producing=False),
    ],
}


def read_offsets(path=SEQUENCES):
    """Image name -> Offset of its main sprite (the turret layer for turreted defences)."""
    found, current, seq = {}, None, None
    if not os.path.exists(path):
        return found
    with open(path) as f:
        for line in f:
            if re.match(r"^[a-z0-9.]+:$", line):
                current = line.strip()[:-1]
                found[current] = {}
            elif re.match(r"^\t[a-z-]+:$", line):
                seq = line.strip()[:-1]
            elif current and line.strip().startswith("Offset:"):
                found[current].setdefault(seq, tuple(int(v) for v in line.split(":")[1].split(",")))
    return {bid: seqs.get("turret", seqs.get("idle")) for bid, seqs in found.items() if seqs.get("idle")}


def actor_blocks():
    """Actor name -> list of its lines in structures.yaml."""
    blocks, current = {}, None
    with open(STRUCTURES) as f:
        for line in f:
            if re.match(r"^[A-Za-z0-9^]+:", line):
                current = line.split(":")[0]
                blocks[current] = []
            elif current:
                blocks[current].append(line.rstrip("\n"))
    return blocks


def damage_points(bid, offset, count, path=None):
    """Spots spread over the building body (not its shadow or front apron) where fires can start."""
    im = np.asarray(Image.open(path or os.path.join(HD, f"{bid}.png")).convert("RGBA"), dtype=np.float32) / 255
    h, w, _ = im.shape
    lum = im[..., :3].mean(-1)
    body = binary_erosion((im[..., 3] > 0.95) & (lum > 0.08), iterations=4)
    ys, xs = np.nonzero(body)
    if len(xs) == 0:
        return []
    y0, y1 = ys.min(), ys.max()
    keep = (ys < y0 + (y1 - y0) * 0.75) & (ys > y0 + (y1 - y0) * 0.1)
    xs, ys = xs[keep], ys[keep]

    # Farthest-point sampling from the centre of the body
    rng = np.random.default_rng(sum(map(ord, bid)))
    cx, cy = xs.mean(), ys.mean()
    first = np.argmin((xs - cx) ** 2 + (ys - cy) ** 2 + rng.random(len(xs)) * 50)
    chosen = [first]
    dist = (xs - xs[first]) ** 2 + (ys - ys[first]) ** 2
    for _ in range(count - 1):
        nxt = int(np.argmax(dist))
        chosen.append(nxt)
        dist = np.minimum(dist, (xs - xs[nxt]) ** 2 + (ys - ys[nxt]) ** 2)
    return [screen(xs[i], ys[i], w, h, offset) for i in chosen]


def peaks(body, count, min_gap):
    """The highest points of the silhouette (spires, chimneys, masts), at least min_gap px apart: (x, y)."""
    h, w = body.shape
    top = np.where(body.any(0), np.argmax(body, axis=0), h)
    order = np.argsort(top, kind="stable")
    found = []
    for x in order:
        if top[x] >= h or len(found) >= count:
            break
        if all(abs(x - fx) >= min_gap for fx, _ in found):
            found.append((int(x), int(top[x])))
    return found


def glow_spots(im, body, count):
    """Bright, saturated blobs (lamps, reactor cores, energy orbs, windows): (x, y, hex colour, size).
    Team-colour green is excluded (it is recoloured in game)."""
    rgb, a = im[..., :3], im[..., 3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-3)
    team = (rgb[..., 1] > 0.6) & (rgb[..., 0] < 0.55) & (rgb[..., 2] < 0.55)
    # A lamp's core is close to white and brighter than any sunlit wall (sandstone, plaster)
    lum = rgb.mean(-1)
    hot = (a > 0.9) & body & (lum > 0.8) & (mx > 0.93) & (sat > 0.12) & ~team
    hot = binary_opening(hot, iterations=1)
    labels, n = label(hot)
    blobs = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(labels == i)
        if len(xs) < 6 or len(xs) > 600:
            continue
        col = rgb[ys, xs].mean(0)
        col = col / col.max()
        blobs.append((len(xs) * mx[ys, xs].mean(), int(xs.mean()), int(ys.mean()), col, len(xs)))
    blobs.sort(key=lambda b: -b[0])
    spots = []
    for _, x, y, col, area in blobs:
        if any((x - sx) ** 2 + (y - sy) ** 2 < 20 ** 2 for sx, sy, _, _ in spots):
            continue
        hexcol = "".join(f"{int(c * 255):02X}" for c in col)
        spots.append((x, y, hexcol, round(min(2.2, 0.5 + np.sqrt(area) / 12), 1)))
        if len(spots) >= count:
            break
    return spots


def style_fx(bid, path):
    """Live effects for a national building, found in its sprite (pixel positions, same format as FX)."""
    im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255
    h, w, _ = im.shape
    body = binary_erosion(im[..., 3] > 0.95, iterations=1)
    ys, xs = np.nonzero(body)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    tops = peaks(body, 3, max(12, w // 6))
    fx = []

    # Glowing lamps and cores breathe; each one on its own rhythm
    for i, (x, y, col, size) in enumerate(glow_spots(im, body, 4)):
        fx.append(pulse(x, y, col, size, period=50 + 13 * i, lo=0.2, hi=0.75, Phase=9 * i))

    if bid in ("powr", "apwr"):
        fx += [steam(x, y + 2, 1.2 if bid == "apwr" else 1.0) for x, y in tops[:2]]
    elif bid == "proc":
        fx += [smoke(tops[0][0], tops[0][1] + 2, 0.8), beacon(tops[-1][0], tops[-1][1], AMBER, 0.6)]
    elif bid == "fact":
        fx += [beacon(tops[0][0], tops[0][1], AMBER), sparks(cx, cy, w // 9, h // 20),
               sparks(cx - w // 8, y1 - h // 6, w // 12, 5, rate=9)]
    elif bid == "weap":
        fx += [smoke(x, y + 2, 0.9, OnlyWhileProducing="true") for x, y in tops[:2]]
        fx += [sparks(cx - w // 10, y1 - h // 5, w // 10, 8)]
    elif bid == "dome":
        x, y = tops[0]
        fx.append(dict(Type="Orbit", Offset=(x, y + h // 8), Radius=(w // 6, w // 18), Color=GREEN, Size=0.8, Period=90,
                       MinAlpha=0.05, MaxAlpha=0.9))
    elif bid in ("tsla", "gap", "pdox"):
        x, y = tops[0]
        fx.append(arcs(x, y + 6, w // 8, w // 14, rate=6))

    # Warning lights on the highest spires (skipping the one that already has a beacon)
    lit = {(f["Offset"]) for f in fx if f["Type"] == "Beacon"}
    for i, (x, y) in enumerate(t for t in tops if t not in lit):
        fx.append(blink(x, y, RED, period=45 + 10 * i, Phase=12 * i))
    return fx


def save_preview(name, path, fx):
    from PIL import ImageDraw
    os.makedirs(PREVIEW, exist_ok=True)
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (90, 110, 80, 255))
    bg.alpha_composite(im)
    d = ImageDraw.Draw(bg)
    marks = {"Pulse": "yellow", "Blink": "red", "Beacon": "orange", "Steam": "white", "Smoke": "gray",
             "Sparks": "cyan", "Orbit": "lime", "Arcs": "blue"}
    for f in fx:
        x, y = f["Offset"]
        r = 5
        d.ellipse((x - r, y - r, x + r, y + r), outline=marks.get(f["Type"], "white"), width=2)
    bg.save(os.path.join(PREVIEW, f"fx-{name}.png"))


def screen(px, py, w, h, offset):
    """HD sprite pixel -> screen pixels relative to the actor centre."""
    return (round((px - w / 2 + offset[0]) / DENSITY, 1), round((py - h / 2 + offset[1]) / DENSITY, 1))


def fmt(v):
    if isinstance(v, tuple):
        return ",".join(fmt(c) for c in v)
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def fx_lines(fx_list, w, h, offset, condition, start=0):
    lines = []
    for i, fx in enumerate(fx_list, start):
        fx = dict(fx)
        fx["Offset"] = screen(*fx["Offset"], w, h, offset)
        if "Radius" in fx:
            fx["Radius"] = tuple(round(r / DENSITY, 1) for r in fx["Radius"])
        lines.append(f"\tWithPxBuildingFx@{i}:")
        lines.append(f"\t\tRequiresCondition: {condition}")
        lines += [f"\t\t{k}: {fmt(v)}" for k, v in fx.items()]
    return lines


def main():
    preview = "--preview" in sys.argv
    offsets = read_offsets()
    offsets.update(read_offsets(os.path.join(ROOT, "mods", "rapx", "sequences", "hd-silo.yaml")))
    styles = {}  # bid -> {nation: offset}
    for name, offset in read_offsets(STYLE_SEQUENCES).items():
        bid, nation = name.split(".", 1)
        styles.setdefault(bid, {})[nation] = offset

    blocks = actor_blocks()
    lines = [
        "# Live effects of the HD buildings (RedAlert Project X).",
        "# GENERATED by artsrc/buildings/make_fx_rules.py - edit that script, not this file.",
        "",
    ]
    for bid, offset in offsets.items():
        actor = bid.upper()
        if actor not in blocks:
            continue

        block = "\n".join(blocks[actor])
        powered = re.search(r"Inherits.*Disable", block) is not None
        condition = "!build-incomplete && !disabled" if powered else "!build-incomplete"
        im = Image.open(os.path.join(HD, f"{bid}.png"))
        w, h = im.size
        cells = max(1, round(w / (24 * DENSITY)))
        nations = styles.get(bid, {})
        default = f"{condition} && !pxstyled" if nations else condition

        lines.append(f"{actor}:")
        if "WithDeathAnimation" in block:
            # Classic low-res death sprites don't fit the HD art; the collapse replaces them
            lines.append("\t-WithDeathAnimation:")
        lines.append("\tWithPxCollapse:")
        if re.search(r"TerrainTypes:\s*Water", block):
            lines.append("\t\tOnWater: true")
        count = {1: 2, 2: 3}.get(cells, 4)
        points = damage_points(bid, offset, count)
        lines += ["\tWithPxDamageFx:", "\t\tPoints: " + ", ".join(f"{round(x)},{round(y)}" for x, y in points),
                  f"\t\tSize: {0.8 + 0.2 * cells:g}"]
        if nations:
            lines.append("\t\tRequiresCondition: !pxstyled")
        lines += fx_lines(FX.get(bid, []), w, h, offset, default)

        # National styles: their own damage spots and effects, the default ones are switched off
        if nations:
            lines += ["\tGrantConditionOnFaction@pxstyled:", "\t\tFactions: " + ", ".join(nations),
                      "\t\tCondition: pxstyled"]
            n = len(FX.get(bid, []))
            for nation, soffset in nations.items():
                path = os.path.join(HD, "styles", nation, f"{bid}.png")
                sw, sh = Image.open(path).size
                cond = f"pxstyle-{nation}"
                lines += [f"\tGrantConditionOnFaction@{cond}:", f"\t\tFactions: {nation}", f"\t\tCondition: {cond}"]
                points = damage_points(bid, soffset, count, path)
                lines += [f"\tWithPxDamageFx@{nation}:", f"\t\tRequiresCondition: {cond}",
                          "\t\tPoints: " + ", ".join(f"{round(x)},{round(y)}" for x, y in points),
                          f"\t\tSize: {0.8 + 0.2 * cells:g}"]
                fx = style_fx(bid, path)
                lines += fx_lines(fx, sw, sh, soffset, f"{condition} && {cond}", n)
                n += len(fx)
                if preview:
                    save_preview(f"{bid}.{nation}", path, fx)
        lines.append("")

    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
