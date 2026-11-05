#!/usr/bin/env python3
"""
HD fire and smoke (RedAlert Project X): procedural, animated sprite sheets drawn at 3x density.

- Fire loops: flame tongues from a time-periodic turbulence field (so every loop is seamless) advected upwards,
  shaded through a black-body ramp (white-hot core, yellow, orange, deep red tips) with a soft glow halo and
  dark smoke rising off the tips.
- Bursts: napalm fireballs that roll outwards, cool from white to red and turn into drifting smoke.
- Smoke: lit, billowing smoke columns and puffs.

Writes mods/rapx/bits/hd/fx/fire/*.png and mods/rapx/sequences/hd-fire.yaml, which replaces the classic burning
tree overlays (burn-s/m/l), ground fires (fire 1-3, scorch_flames), crater smoke (smoke_m), smoke trails (smokey),
flame tower / flamethrower sprites (fb1, fb2, fb4), napalm explosions and signal smoke (smokland), and adds two
particle sprites to the pxfx image (fireball, billow) for the HD flamethrower (OpenRA.Mods.RAPX PxFlame).

  python3 artsrc/fx/make_fire_fx.py
"""
import os

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "fire")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-fire.yaml")
DENSITY = 3.0
SCALE = f"{1 / DENSITY:.4f}"

rng = np.random.default_rng(23)

# Black-body ramp: heat 0..1 -> colour (linear-ish sRGB)
RAMP = np.array([
    (0.00, (0.25, 0.02, 0.00)),
    (0.18, (0.62, 0.06, 0.01)),
    (0.38, (0.95, 0.28, 0.03)),
    (0.58, (1.00, 0.55, 0.10)),
    (0.78, (1.00, 0.82, 0.35)),
    (1.00, (1.00, 0.98, 0.88)),
], dtype=object)


def ramp(heat):
    xs = [p[0] for p in RAMP]
    out = np.zeros(heat.shape + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(heat, xs, [p[1][c] for p in RAMP])
    return out


def periodic_noise(shape, sigmas, octaves=3):
    """Smooth noise in [0, 1], periodic along every axis (gaussian filter with wrap)."""
    total = np.zeros(shape, np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        s = [max(0.6, v / (2 ** o)) for v in sigmas]
        n = gaussian_filter(rng.random(shape).astype(np.float32), s, mode="wrap")
        n = (n - n.min()) / (n.max() - n.min() + 1e-6)
        total += n * amp
        norm += amp
        amp *= 0.5
    return total / norm


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def compose(fire_rgb, fire_a, smoke_v, smoke_a, glow=0.35):
    """Fire over smoke, plus a soft orange glow halo around the hot parts."""
    lum = fire_a * np.clip(fire_rgb.mean(-1), 0, 1)
    halo = gaussian_filter(lum, max(1.5, fire_a.shape[1] * 0.04)) * glow
    halo_rgb = np.array([1.0, 0.5, 0.12], np.float32)
    # smoke layer
    a = smoke_a
    rgb = np.dstack([smoke_v * 1.02, smoke_v, smoke_v * 0.97])
    # halo over smoke
    ha = np.clip(halo, 0, 1)
    rgb = rgb * (1 - ha[..., None]) * (a[..., None] / np.maximum(a + ha * (1 - a), 1e-4)[..., None]) + \
        halo_rgb * (ha / np.maximum(a + ha * (1 - a), 1e-4))[..., None]
    a = a + ha * (1 - a)
    # fire over everything
    fa = np.clip(fire_a, 0, 1)
    out_a = fa + a * (1 - fa)
    out_rgb = (fire_rgb * fa[..., None] + rgb * (a * (1 - fa))[..., None]) / np.maximum(out_a, 1e-4)[..., None]
    return np.dstack([np.clip(out_rgb, 0, 1), np.clip(out_a, 0, 1)])


def fire_loop(w, h, period, width=0.42, height=0.8, sway=0.10, smoke=0.5, base=0.12, tongues=3, embers=6):
    """A seamless loop of `period` frames: several flame tongues rising from a base line at `base` (fraction of h
    from the bottom), `height` = flame height as a fraction of h, dark smoke curling off the tips, glowing embers."""
    ss = 2  # supersample
    W, H = w * ss, h * ss
    n1 = periodic_noise((period, H, W), (period / 5, H / 9, W / 7))
    n2 = periodic_noise((period, H, W), (period / 4, H / 7, W / 5), 2)
    n3 = periodic_noise((period, H, W), (period / 3, H / 26, W / 18), 2)
    ns = periodic_noise((period, H, W), (period / 3, H / 9, W / 6))
    nd = periodic_noise((period, H, W), (period / 3, H / 30, W / 24), 2)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    yn = (H - 1 - y) / (H - 1) - base           # 0 at the flame base, up positive
    xn = (x - (W - 1) / 2) / (W / 2)            # -1..1
    # tongue layout: centres, relative heights and phase offsets
    k = max(1, tongues)
    centres = np.linspace(-0.55, 0.55, k) * width if k > 1 else np.array([0.0])
    heights = rng.uniform(0.65, 1.0, k)
    heights[k // 2] = 1.0
    phases = rng.uniform(0, 1, k)
    # embers: (x0, phase, speed, size)
    em = [(rng.uniform(-width, width), rng.uniform(0, 1), rng.integers(1, 3), rng.uniform(0.6, 1.2)) for _ in range(embers)]
    frames = []
    for t in range(period):
        shift = int(round(t * H / period))      # one full noise period per loop: seamless
        a1 = np.roll(n1[t], -shift, axis=0)
        a2 = np.roll(n2[t], -shift, axis=0)
        a3 = np.roll(n3[t], -2 * shift % H, axis=0)
        sm = np.roll(ns[t], -(shift // 2), axis=0)
        dd = np.roll(nd[t], -2 * shift % H, axis=0)
        heat = np.zeros_like(xn)
        for c, hk, ph in zip(centres, heights, phases):
            flick = 0.85 + 0.15 * np.sin(2 * np.pi * (t / period + ph))
            hh = height * hk * flick
            yy = np.clip(yn / hh, 0, 1.6)
            xd = xn - c + (a2 - 0.5) * sway * 4.5 * np.clip(yy, 0, 1) ** 1.3
            wid = width / k ** 0.35 * (1 - np.clip(yy, 0, 1)) ** 0.6 * (0.7 + 0.6 * a1) + 1e-3
            body = np.clip(1 - np.abs(xd) / wid, 0, 1) ** 0.9
            top = smoothstep(1.05, 0.45, yy + (a1 - 0.5) * 0.6 + (a3 - 0.5) * 0.45)
            heat = np.maximum(heat, body * top * (1.05 - 0.55 * np.clip(yy, 0, 1)))
        bottom = smoothstep(-0.05, 0.06, yn)
        heat = heat * bottom * (0.55 + 0.6 * a1) * (0.8 + 0.4 * dd)
        heat = np.clip(heat * 1.25 - (a3 - 0.5) * 0.3, 0, 1)
        fire_a = smoothstep(0.07, 0.3, heat)
        fire_rgb = ramp(np.clip(heat ** 1.25 * 1.1, 0, 1))
        # embers: bright specks rising and drifting, each loops with the animation
        for ex, eph, espd, esz in em:
            u = (t / period * espd + eph) % 1
            ey = base + u * min(1.0 - base, height * 1.6)
            ex2 = ex + 0.08 * np.sin(2 * np.pi * (u * 2 + eph))
            px, py = (ex2 + 1) * W / 2, (1 - ey) * (H - 1)
            r2 = ((x - px) ** 2 + (y - py) ** 2) / (esz * ss * 1.6) ** 2
            spot = np.exp(-r2) * (1 - u) ** 0.8
            fire_rgb = fire_rgb * (1 - spot[..., None]) + np.array([1.0, 0.75, 0.3]) * spot[..., None]
            fire_a = np.maximum(fire_a, spot * 0.95)
        # smoke curling off the tips, thickening, drifting and thinning towards the top of the sprite
        yy = yn / height
        sy = yy - 0.6
        sw = (width * 0.8 + np.clip(sy, 0, 2) * 0.45) * (0.65 + 0.7 * sm)
        sbody = np.clip(1 - np.abs(xn + (sm - 0.5) * 0.6 * np.clip(sy, 0, 2) - 0.12 * np.clip(sy, 0, 2)) / sw, 0, 1)
        sden = sbody ** 0.8 * smoothstep(0.0, 0.3, sy) * smoothstep(1.0 - base, 0.55, yn) \
            * (0.3 + 0.9 * sm) * (0.75 + 0.5 * dd) * smoke
        smoke_a = np.clip(sden * 1.6, 0, 0.88)
        smoke_v = 0.12 + 0.2 * sm + 0.14 * np.clip(-xn, 0, 1) + 0.06 * dd   # lit from the upper left
        f = compose(fire_rgb, fire_a, smoke_v, smoke_a)
        frames.append(downsample(f, ss))
    return frames


def downsample(rgba, ss):
    if ss == 1:
        return rgba
    h, w = rgba.shape[0] // ss, rgba.shape[1] // ss
    premul = np.dstack([rgba[..., :3] * rgba[..., 3:4], rgba[..., 3:4]])
    premul = premul[:h * ss, :w * ss].reshape(h, ss, w, ss, 4).mean(axis=(1, 3))
    a = premul[..., 3:4]
    return np.dstack([premul[..., :3] / np.maximum(a, 1e-4), a])


def burst(w, h, n, size=0.9, rise=0.25, smoke_end=0.95, seed_shift=0):
    """A napalm burst: a turbulent fireball rolls out with flame tongues on its rim, cools white -> red, and
    turns into a dark, lit smoke cloud that rises and fades."""
    ss = 2
    W, H = w * ss, h * ss
    n1 = periodic_noise((n, H, W), (n / 4, H / 9, W / 9))
    n2 = periodic_noise((n, H, W), (n / 3, H / 24, W / 24), 2)
    n3 = periodic_noise((n, H, W), (n / 3, H / 48, W / 48), 2)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    xn0 = (x - (W - 1) / 2) / (W / 2)
    frames = []
    for i in range(n):
        t = i / (n - 1)
        grow = 1 - (1 - min(1, t * 1.7)) ** 3
        r_max = size * (0.3 + 0.7 * grow)
        cy = 0.64 - rise * t
        yn = (y - cy * (H - 1)) / (H / 2)
        xn = xn0
        r = np.sqrt(xn ** 2 + (yn * (1.3 - 0.4 * t)) ** 2)
        ang = np.arctan2(yn, xn)
        rim = 0.12 * np.sin(ang * 7 + n1[i] * 6) * (n2[i] - 0.3)
        edge = r_max * (0.7 + 0.55 * n1[i] + rim)
        dens = np.clip(1 - r / np.maximum(edge, 1e-3), 0, 1)
        heat0 = max(0.0, 1 - t * 1.3) ** 0.85
        detail = (0.6 + 0.55 * n2[i]) * (0.8 + 0.4 * n3[i])
        heat = np.clip(dens ** 0.65 * heat0 * detail * 1.5, 0, 1)
        fire_a = smoothstep(0.05, 0.28, heat)
        fire_rgb = ramp(np.clip(heat ** 1.2, 0, 1))
        smoke_a = np.clip(smoothstep(0.0, 0.3, dens) * smoke_end * smoothstep(0.08, 0.5, t)
                          * (1 - smoothstep(0.72, 1.0, t)) * (0.55 + 0.6 * n1[i]) * (0.8 + 0.4 * n3[i]), 0, 0.92)
        smoke_v = 0.1 + 0.18 * n1[i] + 0.12 * np.clip(-xn - yn, 0, 1) + 0.05 * n3[i]
        frames.append(downsample(compose(fire_rgb, fire_a, smoke_v, smoke_a, glow=0.55 * heat0), ss))
    return frames


def fireball_loop(size, period):
    """Round, rolling ball of flame for the flamethrower particles (seamless loop)."""
    ss = 2
    S = size * ss
    n1 = periodic_noise((period, S, S), (period / 4, S / 6, S / 6))
    n2 = periodic_noise((period, S, S), (period / 3, S / 14, S / 14), 2)
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    xn, yn = (x - (S - 1) / 2) / (S / 2), (y - (S - 1) / 2) / (S / 2)
    r = np.sqrt(xn ** 2 + yn ** 2)
    frames = []
    for t in range(period):
        edge = 0.62 + 0.38 * n1[t]
        dens = np.clip(1 - r / edge, 0, 1)
        heat = np.clip(dens ** 0.6 * (0.7 + 0.6 * n2[t]) * 1.35, 0, 1)
        a = smoothstep(0.04, 0.3, heat)
        frames.append(downsample(np.dstack([ramp(heat), a]), ss))
    return frames


def billow(size, k):
    """Detailed smoke puffs (neutral grey, lit from the upper left) for particles: k variants."""
    frames = []
    for _ in range(k):
        n = periodic_noise((size, size), (size / 6, size / 6))
        d = periodic_noise((size, size), (size / 14, size / 14), 2)
        y, x = np.mgrid[0:size, 0:size].astype(np.float32)
        xn, yn = (x - (size - 1) / 2) / (size / 2), (y - (size - 1) / 2) / (size / 2)
        r = np.sqrt(xn ** 2 + yn ** 2)
        a = np.clip((1 - r / (0.65 + 0.35 * n)) * 2.0, 0, 1) ** 1.3 * (0.7 + 0.3 * d)
        light = np.clip(0.78 - (xn + yn) * 0.22 + (d - 0.5) * 0.3, 0.35, 1)
        frames.append(np.dstack([light, light * 0.99, light * 0.97, gaussian_filter(a, 0.8) * 0.92]))
    return frames


def smoke_column(w, h, rise_frames, loop, dark=0.18):
    """Crater smoke: grows for rise_frames, then loops seamlessly for `loop` frames."""
    ss = 2
    W, H = w * ss, h * ss
    n1 = periodic_noise((loop, H, W), (loop / 4, H / 8, W / 6))
    n2 = periodic_noise((loop, H, W), (loop / 3, H / 18, W / 14), 2)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    yn = (H - 1 - y) / (H - 1)
    xn = (x - (W - 1) / 2) / (W / 2)

    def frame(t, amount):
        k = t % loop
        shift = int(round(k * H / loop))
        a1 = np.roll(n1[k], -shift, axis=0)
        a2 = np.roll(n2[k], -shift, axis=0)
        wid = (0.22 + yn * 0.85) * (0.75 + 0.5 * a1)
        xd = xn + (a1 - 0.5) * 0.7 * yn
        body = np.clip(1 - np.abs(xd) / wid, 0, 1) ** 0.8
        reach = 0.12 + 0.88 * amount
        top = smoothstep(reach, reach - 0.35, yn + (a1 - 0.5) * 0.25)
        dens = body * top * (0.45 + 0.75 * a1) * smoothstep(0.0, 0.08, yn) * (1 - yn * 0.55)
        a = np.clip(dens * 2.1 * (0.8 + 0.4 * a2), 0, 0.9)
        v = dark + 0.25 * a2 + 0.14 * np.clip(-xd, 0, 1) + 0.1 * yn
        rgb = np.dstack([v * 1.02, v, v * 0.96])
        return downsample(np.dstack([np.clip(rgb, 0, 1), a]), ss)

    intro = [frame(i, (i + 1) / rise_frames) for i in range(rise_frames)]
    body = [frame(rise_frames + i, 1) for i in range(loop)]
    return intro, body


def puff_trail(size, n, warm=False):
    """Smoke trail puff (smokey / fb2 / fb4): appears, expands and fades. warm: starts as fire."""
    ss = 2
    S = size * ss
    n1 = periodic_noise((n, S, S), (n / 3, S / 6, S / 6))
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    xn, yn = (x - (S - 1) / 2) / (S / 2), (y - (S - 1) / 2) / (S / 2)
    r = np.sqrt(xn ** 2 + yn ** 2)
    frames = []
    for i in range(n):
        t = i / (n - 1)
        rad = 0.35 + 0.6 * t
        dens = np.clip(1 - r / (rad * (0.7 + 0.5 * n1[i])), 0, 1)
        sa = np.clip(dens * 1.6, 0, 1) ** 1.2 * (1 - t) ** 1.3 * 0.85
        sv = 0.45 + 0.3 * n1[i] - 0.2 * yn * 0.5 + 0.1 * np.clip(-xn - yn, 0, 1)
        if warm:
            heat = np.clip(dens ** 0.6 * max(0, 1 - t * 2.2) * 1.4, 0, 1)
            fa = smoothstep(0.05, 0.3, heat)
            f = compose(ramp(heat), fa, sv * 0.6, sa * smoothstep(0.15, 0.45, t), glow=0.4 * max(0, 1 - t * 2))
        else:
            f = np.dstack([np.clip(np.dstack([sv, sv, sv * 0.98]), 0, 1), sa])
        frames.append(downsample(f, ss))
    return frames


def save(name, frames):
    h, w, _ = frames[0].shape
    sheet = np.concatenate(frames, axis=1)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}.png"),
                                                                       pnginfo=info, optimize=True)
    print(f"  {name}: {len(frames)} frames {w}x{h}")
    return f"ra|bits/hd/fx/fire/{name}.png", len(frames)


def seq(name, filename, start=0, length=None, extra=()):
    lines = [f"\t{name}:", f"\t\tFilename: {filename}", f"\t\tStart: {start}"]
    if length is not None:
        lines.append(f"\t\tLength: {length}")
    lines.append(f"\t\tScale: {SCALE}")
    lines += [f"\t\t{e}" for e in extra]
    return lines


def main():
    os.makedirs(OUT, exist_ok=True)
    y = ["# HD fire and smoke (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_fire_fx.py - edit that script, not this file.",
         "# Replaces the classic fire / smoke sprites with procedural, animated 3x-density sheets.", ""]

    # --- Burning trees: intro (flames catch), seamless loop, end (die down) -------------------------------
    for size, (w, h, intro, loop) in {"s": (66, 96, 12, 46), "m": (90, 126, 16, 44), "l": (114, 156, 16, 44)}.items():
        frames = fire_loop(w, h, loop, width=0.5, height=0.62, smoke=0.55, base=0.18, tongues=3 if size != "s" else 2)
        def squash(f, k):
            """Flames at k of their height, anchored at the base row."""
            hh = f.shape[0]
            base_row = int(hh * (1 - 0.18))
            rows = np.clip(base_row - (base_row - np.arange(hh)) / max(k, 0.05), 0, hh - 1)
            out = np.stack([np.stack([np.interp(rows, np.arange(hh), f[:, c, ch]) for c in range(f.shape[1])], 1)
                            for ch in range(4)], -1)
            out[..., 3] *= min(1, k * 2)
            return out.astype(np.float32)
        grow = [squash(frames[i % loop], (i + 1) / intro) for i in range(intro)]
        end = [squash(frames[(intro + i) % loop], 1 - (i + 1) / 7) for i in range(6)]
        fn, _ = save(f"burn-{size}", grow + frames + end)
        y += [f"burn-{size}:"]
        y += seq("idle", fn, 0, intro, ["ZOffset: 512", "Offset: 0,-8"])
        y += seq("loop", fn, intro, loop, ["ZOffset: 512", "Offset: 0,-8"])
        y += seq("end", fn, intro + loop, 6, ["ZOffset: 512", "Offset: 0,-8"])
        y.append("")

    # --- Ground fires (fire 1-3, scorch_flames) -------------------------------------------------------------
    sizes = {"1": (78, 108, 1.0), "2": (60, 84, 0.85), "3": (45, 66, 0.7), "4": (36, 54, 0.6)}
    fire_files = {}
    for k, (w, h, sc) in sizes.items():
        fn, n = save(f"fire{k}", fire_loop(w, h, 24, width=0.55, height=0.66, smoke=0.4, base=0.14, tongues=3))
        fire_files[k] = (fn, n)
    y.append("fire:")
    for k, (fn, n) in fire_files.items():
        y += seq(k, fn, 0, n, ["Offset: 0,-10", "ZOffset: 1023", "Tick: 50"])
    y.append("")
    # Scorch fires (SmudgeLayer smoke): burn for two loops, die down, end as a wisp of smoke (classic layout)
    y.append("scorch_flames:")
    for name, k, (w, h, sc) in (("large_flame", "1", sizes["1"]), ("medium_flame", "2", sizes["2"]),
                                ("small_flame", "3", sizes["3"])):
        loop = fire_loop(w, h, 24, width=0.55, height=0.66, smoke=0.4, base=0.14, tongues=3)
        die = []
        for i in range(12):
            f = loop[i % 24].copy()
            kk = 1 - (i + 1) / 13
            hh = f.shape[0]
            base_row = int(hh * (1 - 0.14))
            rows = np.clip(base_row - (base_row - np.arange(hh)) / max(kk, 0.05), 0, hh - 1)
            f = np.stack([np.stack([np.interp(rows, np.arange(hh), f[:, c, ch]) for c in range(f.shape[1])], 1)
                          for ch in range(4)], -1).astype(np.float32)
            f[..., 3] *= min(1, kk * 2.5)
            die.append(f)
        intro, _ = smoke_column(w, h, 16, 8)
        wisp = [f.copy() for f in intro[::-1]]
        for i, f in enumerate(wisp):
            f[..., 3] *= 0.8 * (1 - i / len(wisp))
        fn, n = save(f"scorch-{name}", loop + loop + die + wisp)
        y += seq(name, fn, 0, n, ["Offset: 0,-10", "Tick: 50"])
        y.append("\t\t-Combine:")
    y.append("")

    # --- Crater smoke: rise, loop, then sink back (classic smoke_m layout: idle / loop / end) -----------
    intro, body = smoke_column(72, 144, 26, 42)
    fn, _ = save("smoke_m", intro + body)
    y.append("smoke_m:")
    y += seq("idle", fn, 0, len(intro) + len(body), ["Offset: 2,-22", "ZOffset: 512"])
    y += seq("loop", fn, len(intro), len(body), ["Offset: 2,-22", "ZOffset: 512"])
    y += [f"\tend:", f"\t\tFilename: {fn}", "\t\tFrames: " + ", ".join(str(i) for i in range(len(intro) - 1, -1, -1)),
          "\t\tOffset: 2,-22", "\t\tZOffset: 512", f"\t\tScale: {SCALE}"]
    y.append("")

    # --- Smoke trail (aircraft, damaged units, missiles) ----------------------------------------------------
    fn, n = save("smokey", puff_trail(42, 14))
    y.append("smokey:")
    y += seq("idle", fn, 0, n, ["ZOffset: 1023"])
    y.append("")

    # --- Flame tower / flamethrower classic sprites (fireball body + burning trail) -----------------------
    fn, n = save("fb1", fireball_loop(36, 12))
    y.append("fb1:")
    y += seq("idle", fn, 0, n, ["ZOffset: 1023", "BlendMode: Additive"])
    y.append("")
    for name in ("fb2", "fb4"):
        fn, n = save(name, puff_trail(40, 12, warm=True))
        y.append(f"{name}:")
        y += seq("idle", fn, 0, n, ["ZOffset: 1023"])
        y.append("")

    # --- Napalm explosions --------------------------------------------------------------------------------
    small = save("napalm-small", burst(84, 84, 18, size=0.8, rise=0.2))
    med = save("napalm", burst(150, 132, 22, size=0.85, rise=0.25))
    large = save("napalm-large", burst(216, 186, 26, size=0.9, rise=0.28))
    y.append("explosion:")
    for name, (fn, n), extra in (("small_napalm", small, []), ("offset_napalm", small, ["Offset: 0,-12"]),
                                 ("napalm", med, []), ("building_napalm", med, ["Offset: 0,-12"]),
                                 ("large_napalm", large, [])):
        y += seq(name, fn, 0, n, ["ZOffset: 511"] + extra)
    y.append("")

    # --- Signal smoke (smokland): a tall column that builds up, then loops ---------------------------------
    intro, body = smoke_column(84, 216, 72, 20, dark=0.32)
    fn, _ = save("smokland", intro + body)
    y.append("smokland:")
    y += seq("open", fn, 0, len(intro), ["Tick: 120", "ZOffset: 1023", "Offset: 0,-30"])
    y += seq("idle", fn, len(intro), len(body), ["Tick: 120", "ZOffset: 1023", "Offset: 0,-30"])
    y.append("")

    # --- Particle sprites for the HD flamethrower (pxfx image) ---------------------------------------------
    fb, nfb = save("fireball", fireball_loop(56, 16))
    bl, nbl = save("billow", billow(80, 8))
    y.append("pxfx:")
    y += seq("fireball", fb, 0, nfb, ["BlendMode: Additive"])
    y += seq("billow", bl, 0, nbl)
    y.append("")

    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y))
    print("wrote", os.path.relpath(SEQUENCES, ROOT))


if __name__ == "__main__":
    main()
