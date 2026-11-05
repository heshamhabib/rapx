#!/usr/bin/env python3
"""
HD water effects (RedAlert Project X).

  python3 artsrc/fx/make_water_fx.py

Writes mods/rapx/sequences/hd-water-fx.yaml with:
  explosion: small_splash / med_splash / large_splash
      Animated HD water splashes replacing the classic h2o_exp1-3 frames, so every weapon that hits water gets them:
      a flash, a column of spray thrown up and falling back, a crown of droplets, lingering mist and a foam ring
      spreading on the surface. Simulated as particles and drawn for the game's 50 degree camera.
  pxfx: foam
      Flat foam patches (white, lying on the water) for the torpedo wake (PxTorpedo) and water launches (PxRocket).
"""
import os

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-water-fx.yaml")
DENSITY = 4.0          # sprite pixels per world pixel
SQUASH = 0.77          # ground plane foreshortening at the 50 degree camera (sin 50)
FRAMES = 24
COLUMNS = 6            # frames per row in the sheets

WATER_LIGHT = np.array([1.0, 1.0, 1.0])
WATER_SHADOW = np.array([0.62, 0.74, 0.82])

# name -> size factor (1 = shell / torpedo hit)
SPLASHES = {"large_splash": 1.0, "med_splash": 0.72, "small_splash": 0.45}


def grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return x, y


def noise(rng, w, h, scale, octaves=4):
    """Smooth value noise in [0, 1]."""
    total = np.zeros((h, w), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        n = gaussian_filter(rng.random((h, w)).astype(np.float32), max(0.6, scale / (2 ** o)), mode="wrap")
        n = (n - n.min()) / (n.max() - n.min() + 1e-6)
        total += n * amp
        norm += amp
        amp *= 0.5
    return total / norm


class Canvas:
    """Accumulates soft splats: density and density-weighted light."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.dens = np.zeros((h, w), np.float32)
        self.light = np.zeros((h, w), np.float32)
        self.kernels = {}

    def kernel(self, sigma):
        key = round(sigma * 4) / 4
        k = self.kernels.get(key)
        if k is None:
            r = int(np.ceil(key * 2.5)) + 1
            yy, xx = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
            k = np.exp(-(xx ** 2 + yy ** 2) / (2 * max(key, 0.5) ** 2))
            self.kernels[key] = k
        return k

    def splat(self, x, y, sigma, weight, light):
        k = self.kernel(sigma)
        r = k.shape[0] // 2
        xi, yi = int(round(x)), int(round(y))
        x0, y0, x1, y1 = xi - r, yi - r, xi + r + 1, yi + r + 1
        if x1 <= 0 or y1 <= 0 or x0 >= self.w or y0 >= self.h:
            return
        kx0, ky0 = max(0, -x0), max(0, -y0)
        kx1, ky1 = k.shape[1] - max(0, x1 - self.w), k.shape[0] - max(0, y1 - self.h)
        sub = k[ky0:ky1, kx0:kx1] * weight
        self.dens[max(0, y0):min(self.h, y1), max(0, x0):min(self.w, x1)] += sub
        self.light[max(0, y0):min(self.h, y1), max(0, x0):min(self.w, x1)] += sub * light


def splash_frames(k, seed):
    """Returns (frames, offset): RGBA float frames and the sprite offset putting the impact point at the origin."""
    rng = np.random.default_rng(seed)
    d = DENSITY
    w, h = int(84 * k * d) // 2 * 2, int(96 * k * d) // 2 * 2
    bx, by = w / 2, h - 24 * k * d          # impact point on the canvas
    g = 0.9 * k                              # gravity, world px / frame^2

    def drops(n, r0max, vz, vout, size, t0max, weight):
        a = rng.uniform(0, 2 * np.pi, n)
        r0 = rng.uniform(0, 1, n) ** 0.7 * r0max
        return dict(
            x=np.cos(a) * r0, y=np.sin(a) * r0,
            vx=np.cos(a) * rng.uniform(*vout, n), vy=np.sin(a) * rng.uniform(*vout, n),
            vz=rng.uniform(*vz, n) * (1 - 0.45 * r0 / max(r0max, 1e-3)),
            t0=rng.uniform(0, t0max, n) ** 1.5 / max(t0max, 1e-3) ** 0.5,
            size=rng.uniform(*size, n), weight=weight * rng.uniform(0.6, 1.2, n),
            light=rng.uniform(-0.15, 0.15, n))

    vmax = np.sqrt(2 * g * 58 * k)
    column = drops(700, 4.5 * k, (0.45 * vmax, vmax), (0.05 * k, 0.5 * k), (0.4 * k ** 0.5, 1.2 * k ** 0.5), 3, 0.5)
    # Fast thin jets: the fastest drops fan out widest, so the column flares into tendrils at the top
    column["vx"] *= 0.5 + 1.6 * (column["vz"] / vmax) ** 3
    column["vy"] *= 0.5 + 1.6 * (column["vz"] / vmax) ** 3
    crown = drops(320, 6 * k, (0.2 * vmax, 0.42 * vmax), (0.8 * k, 2.0 * k), (0.4 * k ** 0.5, 0.9 * k ** 0.5), 1.5, 0.5)
    # Spray: fine bright droplets thrown out of the whole splash
    spray = drops(260, 5 * k, (0.3 * vmax, 0.95 * vmax), (0.6 * k, 2.6 * k), (0.25 * k ** 0.5, 0.45 * k ** 0.5), 2, 1.1)
    spray["light"] += 0.25

    # Mist: big soft puffs that hang in the air where the column was and drift up as it collapses
    mist_n = 40
    mist = dict(x=rng.normal(0, 4 * k, mist_n), y=rng.normal(0, 2 * k, mist_n), z=rng.uniform(4, 40, mist_n) * k,
                t0=rng.uniform(3, 9, mist_n), size=rng.uniform(4, 8, mist_n) * k, light=rng.uniform(0, 0.2, mist_n))

    xx, yy = grid(w, h)
    foam_tex = noise(rng, w, h, 3 * d * k ** 0.5)
    lace = np.clip((noise(rng, w, h, 1.2 * d * k ** 0.5, 3) - 0.38) * 3, 0, 1)
    ring_r = np.sqrt((xx - bx) ** 2 + ((yy - by) / SQUASH) ** 2) / d       # world px from the impact

    frames = []
    for f in range(FRAMES):
        c = Canvas(w, h)
        u = f / (FRAMES - 1)

        for p, spread in ((column, 0.035), (crown, 0.05), (spray, 0.0)):
            t = f - p["t0"]
            alive = t >= 0
            z = p["vz"] * t - 0.5 * g * t ** 2
            x = p["x"] + p["vx"] * t
            y = p["y"] + p["vy"] * t
            alive &= z > -0.5
            for i in np.nonzero(alive)[0]:
                falling = p["vz"][i] - g * t[i] < 0
                sigma = p["size"][i] * (1 + spread * t[i]) * d
                light = np.clip(0.72 - 0.25 * x[i] / (8 * k) + 0.2 * z[i] / (50 * k) + p["light"][i], 0.25, 1)
                c.splat(bx + x[i] * d, by + (y[i] * SQUASH - z[i]) * d, sigma, p["weight"][i] * (0.7 if falling else 1), light)

        t = f - mist["t0"]
        for i in np.nonzero(t >= 0)[0]:
            life = np.clip(t[i] / 6, 0, 1) * np.clip(1 - u, 0, 1) ** 1.5
            z = mist["z"][i] + 0.4 * k * t[i]
            c.splat(bx + (mist["x"][i] + 0.25 * k * t[i]) * d, by + (mist["y"][i] * SQUASH - z) * d,
                    mist["size"][i] * (1 + 0.06 * t[i]) * d, 0.09 * life, 0.8 + mist["light"][i])

        # Impact flash: a white dome bursting out of the surface
        if f < 4:
            c.splat(bx, by - 3 * k * d, (4 + 2 * f) * k * d, [1.6, 1.1, 0.6, 0.25][f], 1.0)

        alpha = 1 - np.exp(-c.dens * 1.6)
        light = np.clip(c.light / np.maximum(c.dens, 1e-4), 0, 1)
        rgb = WATER_SHADOW[None, None] + (WATER_LIGHT - WATER_SHADOW)[None, None] * light[..., None]

        # Foam ring and churned foam on the surface, under the spray
        radius = k * (5 + 25 * (1 - np.exp(-f / 7)))
        width = k * (2 + 4 * u)
        ring = np.exp(-((ring_r - radius) / width) ** 2)
        inner = np.clip(1 - ring_r / (radius * 0.85), 0, 1) ** 0.7 * 0.55
        foam = np.clip((ring * 1.1 + inner) * (0.25 + 0.75 * lace) * (0.6 + 0.7 * foam_tex) - 0.12, 0, 1) * (1 - u) ** 1.3
        foam = gaussian_filter(foam, 0.6)
        foam_rgb = np.array([0.88, 0.94, 0.97])

        a = alpha + foam * (1 - alpha)
        out = (rgb * alpha[..., None] + foam_rgb[None, None] * (foam * (1 - alpha))[..., None]) / np.maximum(a, 1e-4)[..., None]
        fade = np.clip((FRAMES - 1 - f) / 4, 0, 1)
        frames.append(np.dstack([out, np.clip(a * fade, 0, 1)]).astype(np.float32))

    return frames, (0, -(by - h / 2))


def foam_patches(n=8, w=96, h=64):
    rng = np.random.default_rng(23)
    frames = []
    xx, yy = grid(w, h)
    for _ in range(n):
        cx, cy = (w - 1) / 2, (h - 1) / 2
        r = np.sqrt(((xx - cx) / (w / 2)) ** 2 + ((yy - cy) / (h / 2)) ** 2)
        tex = noise(rng, w, h, 4)
        lace = noise(rng, w, h, 1.6, 2)
        a = np.clip((1 - r - (tex - 0.5) * 0.8) * 2.2, 0, 1) * np.clip((lace - 0.32) * 3, 0, 1)
        a = gaussian_filter(a, 0.7) * 0.9
        v = 0.9 + 0.1 * tex
        frames.append(np.dstack([v * 0.97, v, v, a]))
    return frames


def save(name, frames, offset=None, columns=None):
    h, w, _ = frames[0].shape
    columns = columns or len(frames)
    rows = (len(frames) + columns - 1) // columns
    sheet = np.zeros((h * rows, w * columns, 4), np.float32)
    for i, fr in enumerate(frames):
        r, c = divmod(i, columns)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = fr
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    if offset:
        info.add_text("Offset", f"{offset[0]:.0f},{offset[1]:.0f}")
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}.png"), pnginfo=info, optimize=True)
    print("wrote", name, f"{w}x{h} x{len(frames)}")


def main():
    os.makedirs(OUT, exist_ok=True)
    scale = 1 / DENSITY
    yaml = [
        "# HD water splashes and foam (RedAlert Project X).",
        "# GENERATED by artsrc/fx/make_water_fx.py - edit that script, not this file.",
        "",
        "explosion:",
    ]
    for i, (name, k) in enumerate(SPLASHES.items()):
        frames, offset = splash_frames(k, 100 + i)
        file = name.replace("_splash", "") + "-splash"
        save(file, frames, offset, COLUMNS)
        yaml += [f"\t{name}:", f"\t\tFilename: ra|bits/hd/fx/{file}.png", f"\t\tLength: {FRAMES}",
                 f"\t\tScale: {scale:.4f}", "\t\tZOffset: 0"]

    save("foam", foam_patches())
    yaml += ["", "pxfx:", "\tfoam:", "\t\tFilename: ra|bits/hd/fx/foam.png", "\t\tLength: 8", f"\t\tScale: {scale:.4f}"]

    with open(SEQUENCES, "w") as f:
        f.write("\n".join(yaml) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))


if __name__ == "__main__":
    main()
