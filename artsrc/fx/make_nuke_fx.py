#!/usr/bin/env python3
"""
HD nuclear mushroom cloud (RedAlert Project X, IDEA-30).

  python3 artsrc/fx/make_nuke_fx.py [--preview]   (about 10 s of cloud: FRAMES x TICK)

Writes mods/rapx/bits/hd/fx/blast/nuke.png and mods/rapx/sequences/hd-nuke-fx.yaml (listed after hd-blast-fx.yaml),
replacing `explosion nuke`. The cloud is built from a few hundred "billows": lumpy spheres lit by a sun from the top
left, with fine bump noise, rim occlusion and their own glow while hot. They are drawn back to front for the 50 degree
camera, which gives the cauliflower look of a real mushroom cloud: a blinding fireball climbs on a stem of dust and
fire, rolls into a golden cap with a glowing underside, while a base surge of dust spreads over the ground; it all cools
to brown and drifts apart. The flash, shock ring and radiation glow are drawn by the PxRadiation warhead
(OpenRA.Mods.RAPX/Warheads/PxRadiationWarhead.cs). --preview writes artsrc/fx/preview/nuke.png.
"""
import os
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_fire_fx as fire  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "blast")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-nuke-fx.yaml")
PREVIEW = os.path.join(HERE, "preview")
D = 1.7                  # sprite pixels per world pixel (a soft cloud: lower than the units to save memory)
SQUASH = 0.77
FRAMES = 100
TICK = 100               # ms per frame: 10 seconds (user: let the cloud hang longer before it vanishes)
# Story time t (shape, colour) against display time u: the fireball and the climb keep their pace (u 0-0.3), the
# glowing cap then hangs and cools slowly (u 0.3-0.75) and only then turns brown, drifts and fades (u 0.75-1).
STORY = ((0.0, 0.0), (0.3, 0.5), (0.75, 0.78), (1.0, 1.0))
FADE = (0.75, 1.0)
W, H = 250, 270          # canvas in world pixels
GROUND = 62              # ground point above the bottom edge, world pixels
SUN = np.array([-0.5, -0.62, 0.6])
SUN /= np.linalg.norm(SUN)

rng = np.random.default_rng(1945)
T = 256
BUMP = gaussian_filter(rng.random((T, T)).astype(np.float32), 2.2, mode="wrap")
BUMP = (BUMP - BUMP.min()) / (BUMP.max() - BUMP.min()) - 0.5
BUMP2 = gaussian_filter(rng.random((T, T)).astype(np.float32), 0.9, mode="wrap")
BUMP2 = (BUMP2 - BUMP2.min()) / (BUMP2.max() - BUMP2.min()) - 0.5


class Canvas:
    """Premultiplied RGBA; billows are composited 'over' in depth order."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)

    def billow(self, sx, sy, r, albedo, heat, alpha, seed, light=1.0):
        R = r * 1.3
        x0, x1 = int(max(0, sx - R)), int(min(self.w, sx + R + 1))
        y0, y1 = int(max(0, sy - R)), int(min(self.h, sy + R + 1))
        if x0 >= x1 or y0 >= y1 or alpha <= 0.01:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        u, v = (xx - sx) / r, (yy - sy) / r
        th = np.arctan2(v, u)
        prng = np.random.default_rng(seed)
        lump = 1 + sum(prng.uniform(0.03, 0.06) * np.sin(k * th + prng.uniform(0, 6.3)) for k in (3, 4, 6))
        rr = np.sqrt(u ** 2 + v ** 2) / lump
        inside = np.clip((1 - rr) * r * 0.3, 0, 1)
        if not inside.any():
            return
        nz = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
        nx, ny = u / lump, v / lump
        ox, oy = prng.integers(0, T, 2)
        scale = max(1, int(round(r / 14)))
        bump = BUMP[((yy // scale + oy) % T).astype(int), ((xx // scale + ox) % T).astype(int)]
        bump2 = BUMP2[((yy + oy) % T).astype(int), ((xx + ox) % T).astype(int)]
        diffuse = np.clip(SUN[0] * nx + SUN[1] * ny + SUN[2] * nz + 0.55 * bump + 0.25 * bump2, 0, 1)
        shade = (0.26 + 0.74 * diffuse) * (0.62 + 0.38 * nz) * light
        col = np.array(albedo, np.float32)[None, None] * shade[..., None]
        if heat > 0.02:
            # hot gas glows from inside: strongest where the billow faces the camera, in its creases too
            glow = heat * (0.45 + 0.55 * nz) * (0.85 + 0.6 * bump)
            col = col * (1 - min(1.0, heat) * 0.6) + fire.ramp(np.clip(glow, 0, 1)) * np.clip(glow * 1.3, 0, 1.2)[..., None]
        fray = np.clip(1 - (rr - 0.55) * 1.6 * (0.7 - bump2 - 0.6 * bump), 0, 1)     # frayed, gassy rim
        a = inside * alpha * fray
        sl = (slice(y0, y1), slice(x0, x1))
        self.rgb[sl] = col * a[..., None] + self.rgb[sl] * (1 - a[..., None])
        self.a[sl] = a + self.a[sl] * (1 - a)

    def image(self):
        a = self.a[..., None]
        return np.dstack([np.clip(self.rgb / np.maximum(a, 1e-5), 0, 1), np.clip(self.a, 0, 1)])


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def frames():
    w, h = int(W * D), int(H * D)
    ox, oy = w / 2, h - GROUND * D

    def px(x, y, z):
        return ox + x * D, oy + (y * SQUASH - z) * D

    # Cap billows: big ones give the shape, small ones crowd its surface (the cauliflower)
    def directions(n):
        v = rng.normal(size=(n, 3))
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    big = dict(dir=directions(150), size=rng.uniform(0.24, 0.34, 150), heat=rng.uniform(0.85, 1.1, 150),
               roll=rng.uniform(0, 2 * np.pi, 150), light=rng.uniform(0.85, 1.1, 150))
    small = dict(dir=directions(380), size=rng.uniform(0.1, 0.17, 380), heat=rng.uniform(0.8, 1.1, 380),
                 roll=rng.uniform(0, 2 * np.pi, 380), light=rng.uniform(0.85, 1.1, 380))
    ns = 120
    stem = dict(s=rng.uniform(0, 1, ns), a=rng.uniform(0, 2 * np.pi, ns), r=np.sqrt(rng.uniform(0, 1, ns)),
                size=rng.uniform(0.75, 1.15, ns), light=rng.uniform(0.85, 1.1, ns))
    nb = 420
    surge = dict(a=rng.uniform(0, 2 * np.pi, nb), r=rng.uniform(0.15, 1.0, nb) ** 0.7, z=rng.uniform(0, 1, nb),
                 size=rng.uniform(5, 9, nb), light=rng.uniform(0.8, 1.1, nb), delay=rng.uniform(0, 0.08, nb))
    out = []
    for f in range(FRAMES):
        u = f / (FRAMES - 1)
        t = float(np.interp(u, *zip(*STORY)))
        hc = 18 + 112 * (1 - np.exp(-3.4 * t))         # cap centre height
        rc = 16 + 46 * (1 - np.exp(-3.2 * t))           # cap radius: wide and flat like a mushroom cap
        cool = np.exp(-t / 0.75)                         # stays golden for most of the show
        fade = 1 - smooth(*FADE, u)
        items = []                                       # (depth, sx, sy, r, albedo, heat, alpha, seed, light)

        def add(x, y, z, r, albedo, heat, alpha, seed, light=1.0):
            sx, sy = px(x, y, z)
            items.append((0.64 * y + 0.77 * z, sx, sy, r * D, albedo, heat, alpha, seed, light))

        for group, layer in ((big, 0), (small, 1)):
            n = len(group["size"])
            for i in range(n):
                dx, dy, dz = group["dir"][i]
                # the underside curls into a rolling torus; the top is a flattened dome
                if dz < -0.1:
                    b = group["roll"][i] + 2.2 * t
                    ring = rc * (0.8 + 0.24 * np.cos(b))
                    hor = np.hypot(dx, dy) + 1e-6
                    x, y = dx / hor * ring, dy / hor * ring
                    z = hc - rc * 0.16 + rc * 0.2 * np.sin(b)
                    under = 1.0
                else:
                    s = 1.0 if layer else 0.8
                    x, y, z = dx * rc * s, dy * rc * s, hc + dz * rc * 0.46 * s
                    under = max(0.0, -dz)
                r = group["size"][i] * rc * (1.15 if layer == 0 else 1.0)
                # the core and the underside stay hot longest (the bright golden glow under the cap)
                # golden underside and core, cooler crust on top and at the rim
                crust = max(0.0, dz) * (0.12 + 0.3 * t)
                heat = group["heat"][i] * cool ** (0.55 if under > 0.5 else 1.0) * (1.3 if under > 0.5 else 1.0 - crust)
                heat = min(1.0, heat + 0.5 * np.exp(-t / 0.06))
                k = t ** 1.5
                albedo = np.array([0.95, 0.66, 0.3]) * (1 - k) + np.array([0.55, 0.42, 0.32]) * k
                add(x, y, z, r, albedo, heat, 0.96 * fade, 1000 * layer + i, group["light"][i] * (0.9 + 0.2 * dz))

        top = hc - rc * 0.35
        for i in range(ns):
            s = (stem["s"][i] + 0.45 * t) % 1.0
            z = s * top
            width = (8 + 7 * s ** 2 + 12 * (1 - s) ** 4) * min(1.0, 0.3 + t * 3)
            x, y = np.cos(stem["a"][i]) * width * stem["r"][i], np.sin(stem["a"][i]) * width * stem["r"][i] * 0.8
            heat = cool ** 0.5 * (0.75 + 0.25 * (1 - s)) * (1.1 - 0.5 * stem["r"][i])
            albedo = np.array([0.72, 0.5, 0.27])
            add(x, y, z, width * 0.75 * stem["size"][i], albedo, heat, 0.95 * fade * min(1.0, t * 12), 2000 + i,
                stem["light"][i])

        for i in range(nb):
            tt = max(0.0, t - surge["delay"][i])
            rs = (10 + 95 * (1 - np.exp(-3.0 * tt))) * surge["r"][i]
            a = surge["a"][i] + 0.15 * tt
            x, y = np.cos(a) * rs, np.sin(a) * rs
            z = 1 + surge["z"][i] * (3 + 5 * tt) + (1 - surge["r"][i]) * 5 * min(1.0, tt * 4)   # low mound at the foot
            heat = 0.8 * cool ** 1.2 * (1 - surge["r"][i] * 0.7)
            albedo = np.array([0.66, 0.5, 0.33])
            r = surge["size"][i] * (0.6 + 0.6 * tt)
            add(x, y, z, r, albedo, heat, 0.7 * fade * min(1.0, tt * 14), 3000 + i, surge["light"][i])

        c = Canvas(w, h)
        # dust haze lying on the ground under the surge
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        rs = 10 + 95 * (1 - np.exp(-3.0 * t))
        gx, gy = (xx - ox) / D, (yy - oy) / (D * SQUASH)
        haze = np.exp(-((np.hypot(gx, gy) / rs) ** 2) * 2.2) * 0.75 * fade * min(1.0, t * 10)
        c.rgb += np.array([0.5, 0.39, 0.28])[None, None] * haze[..., None]
        c.a += haze
        for it in sorted(items, key=lambda it: it[0]):
            c.billow(*it[1:])
        img = c.image()
        # soft focus: a little of the blurred cloud over itself, so it reads as gas and not as balls
        pre = np.dstack([img[..., :3] * img[..., 3:4], img[..., 3:4]])
        blur = np.stack([gaussian_filter(pre[..., ch], 2.2 * D) for ch in range(4)], -1)
        pre = pre * 0.72 + blur * 0.28
        img = np.dstack([pre[..., :3] / np.maximum(pre[..., 3:4], 1e-5), pre[..., 3]])

        # glow halo around the hot cloud, and the first frames' fireball flash
        lum = img[..., 3] * np.clip(img[..., :3].mean(-1) - 0.45, 0, 1)
        halo = np.clip(gaussian_filter(lum, 9 * D) * 2.2 * cool, 0, 0.75)
        hal = np.dstack([np.broadcast_to([1.0, 0.72, 0.3], halo.shape + (3,)), halo])
        img = over(img, hal)
        if f < 4:
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            fx, fy = px(0, 0, hc)
            g = np.exp(-((xx - fx) ** 2 + (yy - fy) ** 2) / (2 * ((28 - 5 * f) * D) ** 2)) * [1.0, 0.85, 0.6, 0.35][f]
            img = over(np.dstack([np.broadcast_to([1.0, 0.98, 0.9], g.shape + (3,)), np.clip(g * 1.3, 0, 1)]), img)
        out.append(img.astype(np.float32))
        print(f"  frame {f + 1}/{FRAMES}", end="\r")
    print()
    return out, (ox, oy)


def over(top, bottom):
    ta, ba = top[..., 3:4], bottom[..., 3:4]
    a = ta + ba * (1 - ta)
    rgb = (top[..., :3] * ta + bottom[..., :3] * ba * (1 - ta)) / np.maximum(a, 1e-5)
    return np.dstack([rgb, a])


def main():
    fr, (ax, ay) = frames()
    h, w, _ = fr[0].shape
    cols = max(1, 4096 // w)
    rows = (len(fr) + cols - 1) // cols
    sheet = np.zeros((h * rows, w * cols, 4), np.float32)
    for i, f in enumerate(fr):
        r, c = divmod(i, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = f
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(fr)))
    info.add_text("Offset", f"{w / 2 - ax:.0f},{h / 2 - ay:.0f}")
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "nuke.png"), pnginfo=info,
                                                                       optimize=True)
    print(f"  nuke: {len(fr)} frames {w}x{h}")
    path = "ra|bits/hd/fx/blast/nuke.png"
    y = ["# HD nuclear mushroom cloud (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_nuke_fx.py - edit that script, not this file.", "", "explosion:", "\tnuke:",
         f"\t\tFilename: {path}", "\t\tTilesetFilenames:"]
    y += [f"\t\t\t{t}: {path}" for t in ("TEMPERAT", "SNOW", "DESERT", "INTERIOR")]
    y += ["\t\tStart: 0", f"\t\tLength: {len(fr)}", "\t\tOffset: 0,0", f"\t\tScale: {1 / D:.4f}", "\t\tZOffset: 2047",
          f"\t\tTick: {TICK}"]
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    if "--preview" in sys.argv:
        os.makedirs(PREVIEW, exist_ok=True)
        pick = fr[::5]
        bg = np.zeros((h, w * len(pick), 3), np.float32) + np.array([0.36, 0.42, 0.25])
        for i, f in enumerate(pick):
            a = f[..., 3:4]
            bg[:, i * w:(i + 1) * w] = f[..., :3] * a + bg[:, i * w:(i + 1) * w] * (1 - a)
        Image.fromarray((bg * 255).astype(np.uint8)).save(os.path.join(PREVIEW, "nuke.png"))


if __name__ == "__main__":
    main()
