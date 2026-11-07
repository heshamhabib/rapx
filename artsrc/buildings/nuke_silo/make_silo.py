#!/usr/bin/env python3
"""
HD Missile Silo (MSLO) with its launch animation, and the nuclear missile in flight (RedAlert Project X).

  python3 artsrc/buildings/nuke_silo/make_silo.py [--skip-render] [--samples N] [--preview]

The building is ChatGPT art: artsrc/buildings/src/mslo.png (prompt: artsrc/prompts/silo-prompts.md; intact left,
damaged right, an EMPTY launch bay with a cradle). The missile is the 3D model of build_silo.py, the same one that
flies to the target, so the silo shows exactly the missile that falls on the enemy.

1. Renders the missile with Blender (build_silo.py) into render/ (skip with --skip-render).
2. Keys the building like every other HD building (process_building.py) and stands the missile in its cradle.
3. Animates the launch over the building: alarm lights, ignition, smoke pouring out of the bay, lift-off with a
   trail, then a fresh missile rises out of the shaft back into the cradle (the idle picture shows it).
4. Writes mods/rapx/bits/hd/mslo*.png (idle, damaged, active, damaged-active, make, collapse), fx/blast/atomic-up/down.png
   and mods/rapx/sequences/hd-silo.yaml (listed after hd-structures.yaml).

The NukePower (rules/structures.yaml) must match the animation; the values are printed at the end:
MissileDelay = LAUNCH_FRAME * TICK / 40 ms per tick, SpawnOffset = the missile centre at that frame, FlightVelocity =
its climbing speed; BeaconRemoveAdvance = -MissileDelay keeps the beacon until the impact. Rerun artsrc/buildings/make_fx_rules.py and artsrc/px-cameos/generate.py after changing the art.
"""
import argparse
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, PngImagePlugin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "buildings"))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "fx"))
import build_all  # noqa: E402
import make_nuke_fx as nukefx  # noqa: E402
from process_building import process  # noqa: E402

SRC = os.path.join(ROOT, "artsrc", "buildings", "src", "mslo.png")
RENDER = os.path.join(HERE, "render")
HD = os.path.join(ROOT, "mods", "rapx", "bits", "hd")
FX = os.path.join(HD, "fx", "blast")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-silo.yaml")
PREVIEW = os.path.join(HERE, "preview")

CELLS = 2                        # footprint 2x2
DENSITY = build_all.DENSITY
GROW = build_all.BUILDING_SCALE  # the building art is drawn 1.25x; the missile must keep its flight size
G = DENSITY / GROW               # sheet pixels per screen pixel

# Measured on the source render (left half, pixels): centre of the cradle ring the missile stands in, and the
# front cradle arms that are nearer the camera than the missile
RING = (445, 542)
FRONT = [(385, 488, 419, 562), (470, 488, 504, 562)]
LAMPS = [(292, 96), (598, 96), (392, 268), (498, 268), (445, 256)]   # alarm lights: tower tops and bay lamps

# Missile renders (build_silo.py): base on the frame centre, 3x density
M_FRAME, M_DENSITY, UNIT_PX, MISSILE_LEN = 216, 3.0, 4.0, 9.0
ELEV = math.radians(50)
M_CENTRE = (MISSILE_LEN / 2 - 0.4) * UNIT_PX * math.cos(ELEV)   # screen px from the base to the flight sprite centre
M_LENGTH = MISSILE_LEN * UNIT_PX * math.cos(ELEV)

DOWN_SCALE = 1.8                 # the falling missile is drawn bigger than the one leaving the silo (user's call)
ACTIVE_FRAMES, TICK = 48, 60
IGNITE, LIFTOFF, LAUNCH_FRAME = 7, 10, 22   # LAUNCH_FRAME: last frame with the missile; the game's missile follows
ACCEL = 0.85                                # screen px / frame^2 while climbing
RELOAD = (33, 47)                           # the next missile rises out of the shaft into the cradle
PAD_TOP, PAD_SIDE, PAD_BOTTOM = 190, 40, 24  # room round the building for the climbing missile and the smoke


def load(path):
    im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255
    im[..., 3] = np.where(im[..., 3] < 0.03, 0, im[..., 3])
    return im


def over(top, bottom):
    ta, ba = top[..., 3:4], bottom[..., 3:4]
    a = ta + ba * (1 - ta)
    rgb = (top[..., :3] * ta + bottom[..., :3] * ba * (1 - ta)) / np.maximum(a, 1e-5)
    return np.dstack([rgb, a])


def resized(im, f):
    """Premultiplied Lanczos resize of a float RGBA image."""
    pm = np.dstack([im[..., :3] * im[..., 3:], im[..., 3]])
    size = (max(1, round(im.shape[1] * f)), max(1, round(im.shape[0] * f)))
    ch = [np.asarray(Image.fromarray(pm[..., c].astype(np.float32)).resize(size, Image.LANCZOS)) for c in range(4)]
    pm = np.clip(np.dstack(ch), 0, 1)
    a = pm[..., 3:]
    return np.dstack([np.where(a > 1e-3, pm[..., :3] / np.maximum(a, 1e-3), 0), a]).astype(np.float32)


def paste(canvas, im, x, y):
    """`im` over `canvas` with its top-left corner at (x, y) (rounded), clipped to the canvas."""
    x, y = round(x), round(y)
    h, w = im.shape[:2]
    H, W = canvas.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return canvas
    layer = np.zeros_like(canvas)
    layer[y0:y1, x0:x1] = im[y0 - y:y1 - y, x0 - x:x1 - x]
    return over(layer, canvas)


class Silo:
    def __init__(self, building, transform):
        h, w = building.shape[:2]
        self.W, self.H = w + 2 * PAD_SIDE, h + PAD_TOP + PAD_BOTTOM
        self.building = np.zeros((self.H, self.W, 4), np.float32)
        self.building[PAD_TOP:PAD_TOP + h, PAD_SIDE:PAD_SIDE + w] = building
        cx, cy = transform["crop"]
        s = transform["scale"]
        self.at = lambda x, y: (PAD_SIDE + (x - cx) * s, PAD_TOP + (y - cy) * s)   # source px -> sheet px
        self.ring = self.at(*RING)
        self.front = np.zeros((self.H, self.W), bool)
        for x0, y0, x1, y1 in FRONT:
            (a, b), (c, d) = self.at(x0, y0), self.at(x1, y1)
            self.front[int(b):int(math.ceil(d)), int(a):int(math.ceil(c))] = True
        f = G / M_DENSITY
        self.stand = resized(load(os.path.join(RENDER, "missile-stand.png")), f)
        self.fire = [resized(load(os.path.join(RENDER, f"missile-fire-{i}.png")), f) for i in range(4)]
        self.anchor = M_FRAME / 2 * f        # the missile's base inside its (resized) render

    def with_missile(self, img, rise, fire=None):
        """The missile standing `rise` screen px above its cradle (negative: still down the shaft)."""
        m = self.stand if fire is None else self.fire[fire]
        layer = paste(np.zeros_like(img), m, self.ring[0] - self.anchor, self.ring[1] - self.anchor - rise * G)
        layer[int(round(self.ring[1])):] = 0                 # below the cradle ring: inside the shaft
        out = over(layer, img)
        out[self.front] = over(img[self.front][None], out[self.front][None])[0]   # the front arms stay in front
        return out


def rise_at(f):
    t = f - LIFTOFF
    return 0.5 * ACCEL * t * t if t > 0 else 0.0


def launch(silo, building):
    """The ACTIVE_FRAMES launch frames over `building` (intact or damaged, already on the sheet canvas)."""
    rng = np.random.default_rng(1961)
    n = 42
    puffs = dict(ang=rng.uniform(0.1 * np.pi, 0.9 * np.pi, n), speed=rng.uniform(1.6, 3.4, n),
                 t0=rng.uniform(IGNITE + 1, LIFTOFF + 8, n), rise=rng.uniform(0.04, 0.14, n),
                 size=rng.uniform(2.2, 3.6, n), light=rng.uniform(0.85, 1.1, n))
    m = 40
    trail = dict(s=rng.uniform(0, 1, m), dx=rng.normal(0, 0.5, m), size=rng.uniform(1.6, 2.6, m),
                 light=rng.uniform(0.9, 1.1, m))
    rx, ry = silo.ring
    yy, xx = np.mgrid[0:silo.H, 0:silo.W].astype(np.float32)
    lamps = [silo.at(*p) for p in LAMPS]
    frames = []
    for f in range(ACTIVE_FRAMES):
        img = building.copy()
        body = img[..., 3:4]
        # alarm: red lights flashing on the towers and in the bay until the missile is gone
        if f <= LAUNCH_FRAME + 4 and (f // 2) % 2 == 0:
            glow = sum(np.exp(-((xx - lx) ** 2 + (yy - ly) ** 2) / (2 * (2.2 * G) ** 2)) for lx, ly in lamps)
            img[..., :3] = np.clip(img[..., :3] + np.array([1.0, 0.12, 0.05]) * glow[..., None] * 0.9 * body, 0, 1)
        # ignition glow lighting the bay
        g = 0.0
        if f >= IGNITE:
            g = min(1.0, (f - IGNITE + 1) / 3) * max(0.0, 1 - max(0, f - LIFTOFF - 4) / 9)
        if g > 0:
            glow = np.exp(-((xx - rx) ** 2 + ((yy - ry) * 1.2) ** 2) / (2 * (9 * G) ** 2)) * g
            img[..., :3] = np.clip(img[..., :3] + np.array([1.0, 0.6, 0.2]) * glow[..., None] * 0.55 * body, 0, 1)
        # the missile
        if f <= LAUNCH_FRAME:
            img = silo.with_missile(img, rise_at(f), None if f < IGNITE else f % 4)
        elif RELOAD[0] <= f:
            t = (f - RELOAD[0]) / (RELOAD[1] - RELOAD[0])
            img = silo.with_missile(img, -(M_LENGTH + 3) * (1 - t * t * (3 - 2 * t)))
        # exhaust smoke: pouring out of the bay and the flame trench, and a trail behind the climbing missile
        c = nukefx.Canvas(silo.W, silo.H)
        items = []
        for i in range(n):
            t = f - puffs["t0"][i]
            if t < 0:
                continue
            d = puffs["speed"][i] * (1 - 0.8 ** t) / 0.2 * G
            x = rx + math.cos(puffs["ang"][i]) * d * 1.6
            y = ry + math.sin(puffs["ang"][i]) * d * 0.7 - puffs["rise"][i] * t * (1 + 0.15 * t) * G
            heat = max(0.0, 0.9 - t * 0.2)
            life = min(1.0, t / 1.5) * max(0.0, 1 - max(0, f - 22) / 12)
            r = puffs["size"][i] * (1 + 0.05 * t) * G
            items.append((y, x, y, r, (1.0, 0.98, 0.95), heat * 0.55, 0.75 * life, 5000 + i, 1.4 * puffs["light"][i]))
        if f > LIFTOFF:
            top = rise_at(min(f, LAUNCH_FRAME + 1))
            fade = max(0.0, 1 - max(0, f - LAUNCH_FRAME) / 10)
            for i in range(m):
                z = trail["s"][i] * top
                age = (1 - trail["s"][i]) * 3 + max(0, f - LAUNCH_FRAME)
                x = rx + (trail["dx"][i] + 0.25 * age) * G
                y = ry - z * G
                r = trail["size"][i] * (1 + 0.07 * age) * G
                items.append((y - 999, x, y, r, (1.0, 0.98, 0.95), max(0.0, 0.6 - age * 0.25), 0.7 * fade, 7000 + i,
                              1.4 * trail["light"][i]))
        for it in sorted(items, key=lambda it: it[0]):
            c.billow(*it[1:])
        frames.append(over(c.image(), img).astype(np.float32))
    return frames


def sheet(frames, path, box, anchor=None):
    x0, y0, x1, y1 = box
    crop = [f[y0:y1, x0:x1] for f in frames]
    h, w, _ = crop[0].shape
    cols = max(1, min(len(crop), 4096 // w))
    rows = (len(crop) + cols - 1) // cols
    s = np.zeros((h * rows, w * cols, 4), np.float32)
    for i, f in enumerate(crop):
        r, c = divmod(i, cols)
        s[r * h:(r + 1) * h, c * w:(c + 1) * w] = f
    s[..., :3] = np.where(s[..., 3:] > 0, s[..., :3], 0)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(crop)))
    if anchor is not None:
        info.add_text("PxOffset", f"{anchor[0]},{anchor[1]}")
    Image.fromarray((np.clip(s, 0, 1) * 255).astype(np.uint8)).save(path, pnginfo=info, optimize=True)
    print("  wrote", os.path.relpath(path, ROOT), f"{len(crop)} x {w}x{h}")


def bbox(frames, pad=4):
    a = np.zeros(frames[0].shape[:2], bool)
    for f in frames:
        a |= f[..., 3] > 0.02
    ys, xs = np.nonzero(a)
    return (max(0, xs.min() - pad), max(0, ys.min() - pad), min(a.shape[1], xs.max() + pad + 1),
            min(a.shape[0], ys.max() + pad + 1))


def seq(name, file, length, offset, scale, tick=None, extra=()):
    path = f"ra|bits/hd/{file}.png"
    lines = [f"\t{name}:", f"\t\tFilename: {path}", "\t\tTilesetFilenames:"]
    lines += [f"\t\t\t{t}: {path}" for t in build_all.TILESETS]
    lines += ["\t\tStart: 0", f"\t\tLength: {length}"]
    if tick:
        lines.append(f"\t\tTick: {tick}")
    lines += [f"\t\tScale: {scale:.4f}", f"\t\tOffset: {offset[0]},{offset[1]}"]
    return lines + [f"\t\t{e}" for e in extra]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    if not args.skip_render:
        subprocess.run(["nice", "-n", "10", "blender", "-b", "-P", os.path.join(HERE, "build_silo.py"), "--", RENDER,
                        str(args.samples)], check=True, stdout=subprocess.DEVNULL)

    os.makedirs(HD, exist_ok=True)
    transform = {}
    paths, _, offset = process(SRC, os.path.join(HD, "mslo.png"), CELLS, DENSITY, log=lambda m: print("  " + m),
                               transform=transform)
    for p in paths:
        build_all.protect_natural_greens(p)
    intact, damaged = load(paths[0]), load(paths[1])
    silo = Silo(intact, transform)
    bld = silo.building
    silo_d = Silo(damaged, transform)
    idle = silo.with_missile(bld, 0)
    idle_d = silo.with_missile(silo_d.building, 0)
    active = launch(silo, bld)
    active_d = launch(silo, silo_d.building)

    # The building sequences get a tight crop; only the launch needs the sky above for the climbing missile.
    # Sequence Offset of a crop: the building's centre (process() offset, measured on the building sprite) on it.
    bh, bw = intact.shape[:2]
    bcx, bcy = PAD_SIDE + bw / 2 - offset[0], PAD_TOP + bh / 2 - offset[1]
    off = lambda b: (round((b[2] - b[0]) / 2 - (bcx - b[0])), round((b[3] - b[1]) / 2 - (bcy - b[1])))
    box_idle = bbox([idle, idle_d])
    box = bbox(active + active_d)
    x0, y0, x1, y1 = box
    sheet([idle], os.path.join(HD, "mslo.png"), box_idle, off(box_idle))
    sheet([idle_d], os.path.join(HD, "mslo-damaged.png"), box_idle, off(box_idle))
    sheet(active, os.path.join(HD, "mslo-active.png"), box, off(box))
    sheet(active_d, os.path.join(HD, "mslo-damaged-active.png"), box, off(box))
    build_all.make_animation(os.path.join(HD, "mslo.png"), os.path.join(HD, "mslo-make.png"))
    build_all.collapse_animation(os.path.join(HD, "mslo-damaged.png"), os.path.join(HD, "mslo-collapse.png"))
    print("  wrote make + collapse")

    # Missile in flight: centred frames (the projectile draws the frame centre at its position)
    for direction in ("up", "down"):
        fr = [load(os.path.join(RENDER, f"missile-{direction}-{i}.png")) for i in range(4)]
        bx0, by0, bx1, by1 = bbox(fr)
        c = fr[0].shape[0] / 2
        hw, hh = max(c - bx0, bx1 - c), max(c - by0, by1 - c)
        sheet(fr, os.path.join(FX, f"atomic-{direction}.png"), (int(c - hw), int(c - hh), int(c + hw), int(c + hh)))

    # build_all.grown() moves a building sprite so the art grows about a point near the bottom of the footprint; it
    # expects the offset of the bare building sprite, so take that shift once and add it to both crops
    g = build_all.grown(offset, CELLS)
    grow = lambda b: (off(b)[0] + g[0] - offset[0], off(b)[1] + g[1] - offset[1])
    grown_idle, grown = grow(box_idle), grow(box)
    scale = GROW / DENSITY
    y = ["# HD Missile Silo with its launch animation, and the nuclear missile in flight (RedAlert Project X).",
         "# GENERATED by artsrc/buildings/nuke_silo/make_silo.py - edit that script, not this file.",
         "# Pure green (#00FF00) areas are recoloured to the owner's colour by PlayerColorShift.", "", "mslo:"]
    y += seq("idle", "mslo", 1, grown_idle, scale)
    y += seq("damaged-idle", "mslo-damaged", 1, grown_idle, scale)
    y += seq("make", "mslo-make", build_all.MAKE_FRAMES, grown_idle, scale, build_all.MAKE_TICK)
    y += seq("active", "mslo-active", ACTIVE_FRAMES, grown, scale, TICK)
    y += seq("damaged-active", "mslo-damaged-active", ACTIVE_FRAMES, grown, scale, TICK)
    y += seq("collapse", "mslo-collapse", build_all.COLLAPSE_FRAMES, grown_idle, scale)
    y += ["", "atomic:"]
    y += seq("up", "fx/blast/atomic-up", 4, (0, 0), 1 / M_DENSITY, extra=["ZOffset: 1023"])
    y += seq("down", "fx/blast/atomic-down", 4, (0, 0), DOWN_SCALE / M_DENSITY, extra=["ZOffset: 1023"])
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))

    # Hand-off to the NukePower missile: its centre at LAUNCH_FRAME, relative to the actor centre. A sheet pixel p is
    # drawn at (p - frame centre + Offset) * Scale screen px; screen px -> world units: 1024 / 24.
    wd = 1024 / 24
    sx = ((silo.ring[0] - x0) - (x1 - x0) / 2 + grown[0]) * scale
    sy = ((silo.ring[1] - y0) - (y1 - y0) / 2 + grown[1]) * scale
    h = rise_at(LAUNCH_FRAME) + M_CENTRE
    speed = ACCEL * (LAUNCH_FRAME - LIFTOFF) / (TICK / 40)            # screen px per game tick
    print(f"NukePower: MissileDelay: {round(LAUNCH_FRAME * TICK / 40)}  SpawnOffset: {round(sx * wd)},{round(sy * wd)},"
          f"{round(h * wd)}  FlightVelocity: {round(speed * wd)}")
    print("lamp pixels in mslo.png:", [(round(silo.at(*p)[0] - box_idle[0]), round(silo.at(*p)[1] - box_idle[1]))
                                       for p in LAMPS[:2]])
    if args.preview:
        os.makedirs(PREVIEW, exist_ok=True)
        pick = [idle, idle_d] + active[::3]
        w = x1 - x0
        bg = np.zeros((y1 - y0, w * len(pick), 3), np.float32) + np.array([0.36, 0.42, 0.25])
        for i, f in enumerate(pick):
            c = f[y0:y1, x0:x1]
            bg[:, i * w:(i + 1) * w] = c[..., :3] * c[..., 3:4] + bg[:, i * w:(i + 1) * w] * (1 - c[..., 3:4])
        Image.fromarray((bg * 255).astype(np.uint8)).save(os.path.join(PREVIEW, "silo.png"))


if __name__ == "__main__":
    main()
