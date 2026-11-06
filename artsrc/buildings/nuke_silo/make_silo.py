#!/usr/bin/env python3
"""
HD Missile Silo (MSLO) with its launch animation, and the nuclear missile in flight (RedAlert Project X).

  python3 artsrc/buildings/nuke_silo/make_silo.py [--skip-render] [--samples N] [--preview]

1. Renders the model with Blender (build_silo.py) into artsrc/buildings/nuke_silo/render/ (skip with --skip-render).
2. Adds the rocket exhaust to the launch frames: smoke billowing out of the shaft and rolling over the pad, a trail
   behind the climbing missile and the ignition glow on the building.
3. Writes mods/rapx/bits/hd/mslo*.png (idle, damaged, active, damaged-active, plus make and collapse from the shared
   building pipeline) and fx/blast/atomic-up/down.png, and mods/rapx/sequences/hd-silo.yaml (listed after
   hd-structures.yaml). The silo is not in build_all.py any more.

The NukePower (rules/structures.yaml) matches the animation: MissileDelay = LAUNCH_FRAME * TICK / 40 ms per tick,
SpawnOffset = the missile centre at that frame, FlightVelocity = its climbing speed. Rerun
artsrc/buildings/make_fx_rules.py and artsrc/px-cameos/generate.py after changing the art.
"""
import argparse
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "buildings"))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "fx"))
import build_all  # noqa: E402
import make_nuke_fx as nukefx  # noqa: E402

RENDER = os.path.join(HERE, "render")
HD = os.path.join(ROOT, "mods", "rapx", "bits", "hd")
FX = os.path.join(HD, "fx", "blast")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-silo.yaml")
PREVIEW = os.path.join(HERE, "preview")

# Must match build_silo.py
UNIT_PX, FRAME, DENSITY = 4.0, 480, 3.0
ACTIVE_FRAMES, LAUNCH_FRAME, TICK = 48, 32, 60
ROT = math.radians(10)
PIT = (-2.6, 0.2)
PAD_Z = 0.75
ELEV = math.radians(50)
K = UNIT_PX * DENSITY            # render pixels per Blender unit


def project(x, y, z):
    """Blender units (building space, before the 10 degree turn) -> render pixel."""
    xr = x * math.cos(ROT) - y * math.sin(ROT)
    yr = x * math.sin(ROT) + y * math.cos(ROT)
    return FRAME / 2 + xr * K, FRAME / 2 - (yr * math.sin(ELEV) + z * math.cos(ELEV)) * K


def load(path):
    im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255
    im[..., 3] = np.where(im[..., 3] < 0.03, 0, im[..., 3])         # shadow-catcher noise
    return im


def over(top, bottom):
    ta, ba = top[..., 3:4], bottom[..., 3:4]
    a = ta + ba * (1 - ta)
    rgb = (top[..., :3] * ta + bottom[..., :3] * ba * (1 - ta)) / np.maximum(a, 1e-5)
    return np.dstack([rgb, a])


def exhaust(frames):
    """Rocket exhaust over the launch frames: a billowing cloud pushed out of the shaft across the pad, a trail
    following the missile up, and a hot glow lighting the building around the shaft."""
    rng = np.random.default_rng(1961)
    n = 95
    ang = rng.uniform(0, 2 * np.pi, n)
    puffs = dict(ang=ang, speed=rng.uniform(0.7, 1.7, n), t0=rng.uniform(23, 33, n), rise=rng.uniform(0.02, 0.07, n),
                 size=rng.uniform(0.55, 0.95, n), light=rng.uniform(0.85, 1.1, n))
    m = 46
    trail = dict(s=rng.uniform(0, 1, m), dx=rng.normal(0, 0.25, m), size=rng.uniform(0.5, 0.85, m),
                 light=rng.uniform(0.9, 1.1, m))
    sx, sy = project(*PIT, PAD_Z + 0.4)
    yy, xx = np.mgrid[0:FRAME, 0:FRAME].astype(np.float32)
    out = []
    for f, frame in enumerate(frames):
        c = nukefx.Canvas(FRAME, FRAME)
        items = []
        for i in range(n):
            t = f - puffs["t0"][i]
            if t < 0:
                continue
            d = puffs["speed"][i] * (1 - 0.8 ** t) / 0.2               # pushed out, slowed by drag
            x, y = PIT[0] + math.cos(puffs["ang"][i]) * d, PIT[1] + math.sin(puffs["ang"][i]) * d * 0.9
            z = PAD_Z + 0.3 + puffs["rise"][i] * t * (1 + 0.3 * t)
            heat = max(0.0, 0.9 - t * 0.18)
            life = min(1.0, t / 1.5) * max(0.0, 1 - max(0, f - 34) / 12)
            r = puffs["size"][i] * (1 + 0.1 * t) * K
            px, py = project(x, y, z)
            items.append((y + z, px, py, r, (1.0, 0.98, 0.95), heat * 0.55, 0.7 * life, 5000 + i, 1.45 * puffs["light"][i]))
        if 26 <= f:
            top = PAD_Z + 0.45 * 0.9 * min(f, LAUNCH_FRAME + 1 - 26) ** 2        # base of the climbing missile
            for i in range(m):
                z = PAD_Z + trail["s"][i] * top
                age = (1 - trail["s"][i]) * 3 + max(0, f - LAUNCH_FRAME)
                fade = max(0.0, 1 - max(0, f - LAUNCH_FRAME) / 14)
                px, py = project(PIT[0] + trail["dx"][i] + 0.05 * age, PIT[1], z)
                r = trail["size"][i] * (1 + 0.12 * age) * K
                items.append((PIT[1] + z, px, py, r, (1.0, 0.98, 0.95), max(0.0, 0.6 - age * 0.25), 0.75 * fade,
                              7000 + i, 1.45 * trail["light"][i]))
        for it in sorted(items, key=lambda it: it[0]):
            c.billow(*it[1:])
        img = frame.copy()
        # ignition glow on the building around the shaft
        g = max(0.0, 1 - abs(f - 27) / 8) if f >= 23 else 0
        if g > 0:
            glow = np.exp(-((xx - sx) ** 2 + ((yy - sy) * 1.3) ** 2) / (2 * (14 * K * 0.45) ** 2)) * g
            img[..., :3] = np.clip(img[..., :3] + np.array([1.0, 0.55, 0.18]) * glow[..., None] * 0.4 * img[..., 3:4], 0, 1)
        out.append(over(c.image(), img).astype(np.float32))
    return out


def soot(im, seed=3):
    """Battle damage on the building pixels: soot patches and scorch streaks."""
    rng = np.random.default_rng(seed)
    h, w, _ = im.shape
    n = gaussian_filter(rng.random((h, w)).astype(np.float32), 6)
    n = (n - n.min()) / (n.max() - n.min())
    fine = gaussian_filter(rng.random((h, w)).astype(np.float32), 1.2)
    fine = (fine - fine.min()) / (fine.max() - fine.min())
    dark = np.clip((n - 0.45) * 2.5, 0, 1) * (0.55 + 0.45 * fine)
    body = (im[..., 3] > 0.9).astype(np.float32)
    out = im.copy()
    out[..., :3] *= (1 - 0.72 * dark * body)[..., None]
    out[..., :3] *= 0.86
    return out


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
    lines += [f"\t\t\t{t}: {path}" for t in ("TEMPERAT", "SNOW", "DESERT", "INTERIOR")]
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

    idle = load(os.path.join(RENDER, "idle.png"))
    active = [load(os.path.join(RENDER, f"active-{f:02d}.png")) for f in range(ACTIVE_FRAMES)]
    damaged = soot(idle)
    damaged_active = [soot(f) for f in active]
    active, damaged_active = exhaust(active), exhaust(damaged_active)

    box = bbox([idle] + active)
    x0, y0, x1, y1 = box
    offset = (round(x0 + (x1 - x0) / 2 - FRAME / 2), round(y0 + (y1 - y0) / 2 - FRAME / 2))
    os.makedirs(HD, exist_ok=True)
    sheet([idle], os.path.join(HD, "mslo.png"), box, offset)
    sheet([damaged], os.path.join(HD, "mslo-damaged.png"), box, offset)
    sheet(active, os.path.join(HD, "mslo-active.png"), box)
    sheet(damaged_active, os.path.join(HD, "mslo-damaged-active.png"), box)
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

    scale = 1 / DENSITY
    y = ["# HD Missile Silo with its launch animation, and the nuclear missile in flight (RedAlert Project X).",
         "# GENERATED by artsrc/buildings/nuke_silo/make_silo.py - edit that script, not this file.",
         "# Pure green (#00FF00) areas are recoloured to the owner's colour by PlayerColorShift.", "", "mslo:"]
    y += seq("idle", "mslo", 1, offset, scale)
    y += seq("damaged-idle", "mslo-damaged", 1, offset, scale)
    y += seq("make", "mslo-make", build_all.MAKE_FRAMES, offset, scale, 45)
    y += seq("active", "mslo-active", ACTIVE_FRAMES, offset, scale, TICK)
    y += seq("damaged-active", "mslo-damaged-active", ACTIVE_FRAMES, offset, scale, TICK)
    y += seq("collapse", "mslo-collapse", build_all.COLLAPSE_FRAMES, offset, scale)
    y += ["", "atomic:"]
    y += seq("up", "fx/blast/atomic-up", 4, (0, 0), scale, extra=["ZOffset: 1023"])
    y += seq("down", "fx/blast/atomic-down", 4, (0, 0), scale, extra=["ZOffset: 1023"])
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))

    # Hand-off to the NukePower missile: its centre at LAUNCH_FRAME, in world units relative to the building centre
    base = PAD_Z + 0.45 * 0.9 * (LAUNCH_FRAME - 26) ** 2
    cz = (base + 4.5) * UNIT_PX * math.cos(ELEV)                        # screen pixels above the pad
    xr = PIT[0] * math.cos(ROT) - PIT[1] * math.sin(ROT)
    yr = (PIT[0] * math.sin(ROT) + PIT[1] * math.cos(ROT)) * math.sin(ELEV)
    speed = 0.9 * (LAUNCH_FRAME - 26) * UNIT_PX * math.cos(ELEV) / (TICK / 40)   # screen px per game tick
    wd = 1024 / 24
    print(f"NukePower: MissileDelay: {round(LAUNCH_FRAME * TICK / 40)}  SpawnOffset: {round(xr * UNIT_PX * wd)},"
          f"{round(yr * UNIT_PX * wd)},{round(cz * wd)}  FlightVelocity: {round(speed * wd)}")
    lamps = [project(x, yv, z) for x, yv, z in ((-7.5 + 0.6, -4.5 + 0.6, PAD_Z + 0.4), (7.5 - 0.6, -4.5 + 0.6, PAD_Z + 0.4),
                                               (-7.5 + 0.6, 4.5 - 0.6, PAD_Z + 0.4))]
    print("lamp pixels in mslo.png:", [(round(px - x0), round(py - y0)) for px, py in lamps])
    if args.preview:
        os.makedirs(PREVIEW, exist_ok=True)
        pick = [idle, damaged] + active[::4]
        w = x1 - x0
        bg = np.zeros((y1 - y0, w * len(pick), 3), np.float32) + np.array([0.36, 0.42, 0.25])
        for i, f in enumerate(pick):
            c = f[y0:y1, x0:x1]
            bg[:, i * w:(i + 1) * w] = c[..., :3] * c[..., 3:4] + bg[:, i * w:(i + 1) * w] * (1 - c[..., 3:4])
        Image.fromarray((bg * 255).astype(np.uint8)).save(os.path.join(PREVIEW, "silo.png"))


if __name__ == "__main__":
    main()
