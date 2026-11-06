#!/usr/bin/env python3
"""
HD explosions, muzzle flashes, shells and gem sparkles (RedAlert Project X, IDEA-30 phase 1).

  python3 artsrc/fx/make_blast_fx.py [--preview]

Procedural particle simulations drawn for the game's 50 degree camera, like make_water_fx.py. Writes
mods/rapx/bits/hd/fx/blast/*.png and mods/rapx/sequences/hd-blast-fx.yaml (listed after hd-water-fx.yaml in
mod.yaml), which replaces the last classic combat sprites:

  explosion  piff, piffs, water_piff, water_piffs (bullet hits), small/med/large_explosion, artillery_explosion,
             self_destruct, building, flak_explosion_ground, small/med_explosion_air (the nuke: make_nuke_fx.py)
  <unit>     muzzle / garrison-muzzle: cannon, autocannon and machine-gun flashes in 32 facings, SAM launch in 16
  120mm, 50cal, bomb (grenade, depth charge), bomblet
  twinkle    gem sparkles (additive)

Explosion sheets put the impact point at the sprite origin through the PNG Offset, as the water splashes do.
Directional sprites are drawn once looking east on the ground plane, then turned to every facing (counter-clockwise
from north, like the unit renders) and squashed for the camera. --preview writes artsrc/fx/preview/blast-*.png.
"""
import os
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_fire_fx as fire  # noqa: E402
import make_water_fx as water  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "blast")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-blast-fx.yaml")
PREVIEW = os.path.join(HERE, "preview")
DENSITY = 4.0          # sprite pixels per world pixel (explosions, shells, sparkles)
MUZZLE_DENSITY = 3.0   # muzzle flashes (32 facings, so a little lower)
SQUASH = 0.77          # ground plane foreshortening at the 50 degree camera
FILE = "ra|bits/hd/fx/blast/{}.png"

DUST = np.array([0.50, 0.42, 0.31], np.float32)
SMOKE_LIGHT = np.array([0.66, 0.63, 0.59], np.float32)
SMOKE_DARK = np.array([0.07, 0.065, 0.06], np.float32)

_kernels = {}


def kernel(sigma):
    key = max(0.5, round(sigma * 4) / 4)
    k = _kernels.get(key)
    if k is None:
        r = int(np.ceil(key * 2.6)) + 1
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
        k = _kernels[key] = np.exp(-(xx ** 2 + yy ** 2) / (2 * key ** 2))
    return k


class Layer:
    """Soft splats: accumulated density and a density-weighted value (heat for fire, light for smoke)."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.dens = np.zeros((h, w), np.float32)
        self.val = np.zeros((h, w), np.float32)

    def splat(self, x, y, sigma, weight, value):
        if weight <= 0:
            return
        k = kernel(sigma)
        r = k.shape[0] // 2
        xi, yi = int(round(x)), int(round(y))
        x0, y0, x1, y1 = xi - r, yi - r, xi + r + 1, yi + r + 1
        if x1 <= 0 or y1 <= 0 or x0 >= self.w or y0 >= self.h:
            return
        kx0, ky0 = max(0, -x0), max(0, -y0)
        kx1, ky1 = k.shape[1] - max(0, x1 - self.w), k.shape[0] - max(0, y1 - self.h)
        sub = k[ky0:ky1, kx0:kx1] * weight
        sl = (slice(max(0, y0), min(self.h, y1)), slice(max(0, x0), min(self.w, x1)))
        self.dens[sl] += sub
        self.val[sl] += sub * value

    def mean(self):
        return np.clip(self.val / np.maximum(self.dens, 1e-5), 0, 1)


def over(top, bottom):
    """Straight-alpha 'over' of two RGBA float images."""
    ta, ba = top[..., 3:4], bottom[..., 3:4]
    a = ta + ba * (1 - ta)
    rgb = (top[..., :3] * ta + bottom[..., :3] * ba * (1 - ta)) / np.maximum(a, 1e-5)
    return np.dstack([rgb, a])


def layer_rgba(layer, dark, light, gain, tex=None):
    """Billowy smoke: opacity broken up by the texture, lit from the top left by the slope of its own density."""
    dens = layer.dens * gain * (1 if tex is None else tex)
    a = 1 - np.exp(-dens)
    soft = gaussian_filter(dens, max(1.0, layer.w * 0.012))
    gy, gx = np.gradient(soft)
    rel = -(gx + gy) / (soft + 0.15 * soft.max() + 1e-5) * layer.w * 0.03
    v = np.clip(0.25 + 0.5 * layer.mean() + 0.45 * np.tanh(rel), 0, 1)
    if tex is not None:
        v = np.clip(v * (0.8 + 0.25 * tex), 0, 1)
    return np.dstack([dark + (light - dark) * v[..., None], a])


def compose(fire_l, smoke_l, dust_l, glow=0.4, fire_tex=None, smoke_tex=None, smoke_dark=SMOKE_DARK,
            smoke_light=SMOKE_LIGHT):
    """Dust under smoke under fire, with an orange glow halo around the hot parts."""
    out = layer_rgba(dust_l, DUST * 0.25, DUST * 1.25, 1.5, smoke_tex)
    out = over(layer_rgba(smoke_l, smoke_dark, smoke_light, 1.4, smoke_tex), out)
    tex = 1 if fire_tex is None else fire_tex
    # turbulent fire: the texture breaks up both the heat (bright cores, dark red veins) and the edges
    heat = np.clip(fire_l.mean() * (0.45 + 0.6 * tex) + 0.25 * fire.smoothstep(0.6, 2.5, fire_l.dens), 0, 1)
    fa = 1 - np.exp(-fire_l.dens * 1.6 * tex ** 1.5)
    fa *= fire.smoothstep(0.08, 0.32, heat)
    if glow > 0:
        lum = gaussian_filter(fa * heat, max(1.5, fire_l.w * 0.035)) * glow
        out = over(np.dstack([np.broadcast_to([1.0, 0.5, 0.13], lum.shape + (3,)), np.clip(lum, 0, 0.8)]), out)
    return over(np.dstack([fire.ramp(np.clip(heat ** 0.9, 0, 1)), fa]), out)


def texture(rng, w, h, scale, octaves=3):
    return 0.45 + 1.1 * water.noise(rng, w, h, scale, octaves)


def scroll(tex, dy):
    return np.roll(tex, -int(round(dy)), axis=0)


# --- Explosions ---------------------------------------------------------------------------------------------------

def blast(R, frames, seed, air=False, fire_amt=1.0, smoke=1.0, dark=0.0, dust=1.0, debris=16, sparks=20, column=0.0,
          flash=1.0, size=None, d=DENSITY):
    """One explosion. R = fireball radius in world px. Returns (frames, anchor): anchor = impact pixel."""
    rng = np.random.default_rng(seed)
    W, H = size or (R * 5.4, R * (5.0 if air else 6.2) + column * R * 2.5)
    w, h = int(W * d) // 2 * 2, int(H * d) // 2 * 2
    ox, oy = w / 2, (h / 2 if air else h - 1.2 * R * d)
    g = 0.11 * R                              # gravity, world px / frame^2

    def px(x, y, z):
        return ox + x * d, oy + (y * SQUASH - z) * d

    # Fireball puffs thrown out of the blast, slowed by drag, rising as they cool into smoke
    n = int((45 + 22 * R) * fire_amt)
    # The fireball bursts out in a few uneven lobes, so it is never a clean sphere
    lobes = rng.integers(4, 8)
    la = rng.uniform(0, 2 * np.pi, lobes)
    lu = rng.uniform(-0.8 if air else 0.15, 1, lobes)
    lobe_dir = np.stack([np.sqrt(1 - lu ** 2) * np.cos(la), np.sqrt(1 - lu ** 2) * np.sin(la), lu], 1)
    lobe_speed, lobe_delay = rng.uniform(0.6, 1.35, lobes), rng.uniform(0, 1.8, lobes)
    lobe_heat = rng.uniform(0.85, 1.25, lobes)
    which = rng.integers(0, lobes, n)
    a = rng.uniform(0, 2 * np.pi, n)
    u = rng.uniform(-1 if air else 0.1, 1, n)
    s = np.sqrt(1 - u ** 2)
    dirs = np.stack([s * np.cos(a), s * np.sin(a), u], 1) * 0.5 + lobe_dir[which] * 0.8
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    speed = R * rng.uniform(0.2, 0.45, n) * lobe_speed[which]
    puffs = dict(dx=dirs[:, 0], dy=dirs[:, 1], dz=dirs[:, 2] * (1.0 if air else 1.25), speed=speed,
                 t0=rng.uniform(0, 1.0, n) + lobe_delay[which], heat=rng.uniform(0.8, 1.05, n),
                 tau=frames * rng.uniform(0.08, 0.2, n) * lobe_heat[which],
                 size=R * rng.uniform(0.11, 0.24, n), light=rng.uniform(-0.15, 0.15, n))
    drag = 0.6
    # Lingering smoke rising from the blast
    m = int((14 + 7 * R) * smoke)
    lsmoke = dict(x=rng.normal(0, 0.3 * R, m), y=rng.normal(0, 0.3 * R, m), z=rng.uniform(0.3, 1.0, m) * R,
                  t0=rng.uniform(2, max(3, frames * 0.35), m), rise=rng.uniform(0.08, 0.18, m) * R,
                  size=rng.uniform(0.15, 0.3, m) * R, light=rng.uniform(-0.1, 0.15, m))
    # Debris clods and sparks on ballistic paths
    def ballistic(k, vh, vz, life):
        a = rng.uniform(0, 2 * np.pi, k)
        return dict(vx=np.cos(a) * rng.uniform(*vh, k), vy=np.sin(a) * rng.uniform(*vh, k),
                    vz=rng.uniform(*vz, k), t0=rng.uniform(0, 1.5, k), life=rng.uniform(*life, k))
    clods = ballistic(debris, (0.15 * R, 0.55 * R), (0.3 * R, 0.9 * R), (frames * 0.4, frames * 0.8))
    if air:
        clods["vz"] -= 0.55 * R
    spark = ballistic(sparks, (0.5 * R, 1.3 * R), (-0.6 * R if air else 0.1 * R, 1.1 * R), (3, 8))
    # Dirt thrown up in a column (artillery)
    c = int(column * 50)
    jet = ballistic(c, (0.02 * R, 0.18 * R), (0.7 * R, 1.25 * R), (frames * 0.7, frames))
    jet["size"] = rng.uniform(0.12, 0.22, c) * R

    tex_f = texture(rng, w, h, 0.07 * R * d, 4)
    tex_s = texture(rng, w, h, 0.14 * R * d, 4)
    out = []
    for f in range(frames):
        fl, sl, dl = Layer(w, h), Layer(w, h), Layer(w, h)
        life_end = np.clip((frames - 1 - f) / max(3, frames * 0.3), 0, 1)

        t = f - puffs["t0"]
        for i in np.nonzero(t >= 0)[0]:
            ti = t[i]
            dist = puffs["speed"][i] * (1 - drag ** ti) / (1 - drag)
            x, y = puffs["dx"][i] * dist, puffs["dy"][i] * dist
            heat = puffs["heat"][i] * np.exp(-ti / puffs["tau"][i])
            # hot gas rises, faster once it has cooled into smoke
            z = puffs["dz"][i] * dist + (0 if air else 0.3 * R) + 0.04 * R * ti + 0.012 * R * ti ** 2 * (1 - heat)
            if not air:
                z = max(z, 0.15 * R)
            sigma = puffs["size"][i] * (0.55 + 0.9 * (1 - np.exp(-ti / 2.5)) + 0.04 * ti) * d
            X, Y = px(x, y, z)
            fl.splat(X, Y, sigma, 0.6 * fire.smoothstep(0.1, 0.45, heat), heat)
            sw = smoke * 0.5 * (1 - fire.smoothstep(0.15, 0.55, heat)) * life_end
            sl.splat(X, Y, sigma * 1.15, sw, np.clip(0.3 - 0.3 * x / R + 0.25 * z / R + puffs["light"][i] - dark, 0, 1))

        t = f - lsmoke["t0"]
        for i in np.nonzero(t >= 0)[0]:
            ti = t[i]
            z = lsmoke["z"][i] + lsmoke["rise"][i] * ti
            X, Y = px(lsmoke["x"][i] + 0.04 * R * ti, lsmoke["y"][i], z)
            sw = smoke * 0.32 * np.clip(ti / 3, 0, 1) * life_end
            sl.splat(X, Y, lsmoke["size"][i] * (1 + 0.09 * ti) * d, sw,
                     np.clip(0.45 + 0.25 * z / (2 * R) + lsmoke["light"][i] - dark, 0, 1))

        if not air and dust > 0:
            k = int(18 + 4 * R)
            r = R * (0.5 + 1.5 * (1 - np.exp(-f / 4)))
            for j in range(k):
                ang = 2 * np.pi * (j + 0.37 * np.sin(j * 7.1)) / k
                X, Y = px(np.cos(ang) * r, np.sin(ang) * r, 0.18 * R + 0.04 * R * f)
                dl.splat(X, Y, R * 0.28 * (1 + 0.07 * f) * d, 0.22 * dust * (1 - f / frames) ** 1.3,
                         0.55 + 0.3 * np.sin(ang + 2.4))

        for p, kind in ((clods, "clod"), (spark, "spark"), (jet, "jet")):
            t = f - p["t0"]
            for i in np.nonzero((t >= 0) & (t < p["life"]))[0]:
                ti = t[i]
                z = p["vz"][i] * ti - 0.5 * g * ti ** 2 + (0 if air else 0.2 * R)
                if not air and z < 0:
                    continue
                x, y = p["vx"][i] * ti, p["vy"][i] * ti
                X, Y = px(x, y, z)
                if kind == "spark":
                    fade = 1 - ti / p["life"][i]
                    for step in range(3):   # a short streak along the path
                        bt = max(0.0, ti - 0.25 * step)
                        bz = p["vz"][i] * bt - 0.5 * g * bt ** 2 + (0 if air else 0.2 * R)
                        bx, by = px(p["vx"][i] * bt, p["vy"][i] * bt, bz)
                        fl.splat(bx, by, 0.35 * d, 1.4 * fade * (1 - 0.3 * step), 1.0)
                elif kind == "clod":
                    dl.splat(X, Y, max(0.4, 0.04 * R) * d, 2.5, 0.02)
                else:
                    dl.splat(X, Y, p["size"][i] * (1 + 0.05 * ti) * d, 0.3 * life_end, 0.5 + 0.2 * np.sin(i))

        if f < 3 and flash > 0:
            X, Y = px(0, 0, 0 if air else 0.35 * R)
            fl.splat(X, Y, R * [0.95, 0.7, 0.45][f] * flash * d, [3.0, 1.6, 0.6][f], 1.0)

        frame = compose(fl, sl, dl, glow=0.5 * max(0.0, 1 - f / (frames * 0.5)),
                        fire_tex=scroll(tex_f, f * 0.1 * R * d), smoke_tex=scroll(tex_s, f * 0.07 * R * d),
                        smoke_dark=SMOKE_DARK * (1 - 0.5 * dark), smoke_light=SMOKE_LIGHT * (1 - 0.45 * dark))
        frame[..., 3] *= np.clip((frames - 1 - f) / 2.5, 0, 1)
        out.append(frame.astype(np.float32))
    return out, (ox, oy)


def scatter(base, anchor, hits, frames, seed, spread):
    """Several copies of one effect at random spots and delays (piffs: a burst of bullets)."""
    rng = np.random.default_rng(seed)
    h, w, _ = base[0].shape
    pad = int(spread)
    W, H = w + 2 * pad, h + 2 * pad
    shots = [(rng.uniform(-spread, spread), rng.uniform(-spread, spread) * SQUASH, d) for d in
             sorted(rng.choice(np.arange(0, frames - len(base) + 1), hits, replace=False))]
    shots[0] = (0.0, 0.0, 0)
    out = []
    for f in range(frames):
        canvas = np.zeros((H, W, 4), np.float32)
        for dx, dy, delay in sorted(shots, key=lambda s: s[1]):
            i = f - delay
            if 0 <= i < len(base):
                x0, y0 = pad + int(round(dx)), pad + int(round(dy))
                region = canvas[y0:y0 + h, x0:x0 + w]
                canvas[y0:y0 + h, x0:x0 + w] = over(base[i], region)
        out.append(canvas)
    return out, (anchor[0] + pad, anchor[1] + pad)


def water_hit(k, frames, seed):
    water.FRAMES = frames
    fr, off = water.splash_frames(k, seed)
    h, w, _ = fr[0].shape
    return fr, (w / 2, h / 2 - off[1])


def nuke(seed, frames=44, d=2.5):
    """Mushroom cloud: blinding flash, a rolling fireball that climbs on a stem of dust, and a base surge."""
    rng = np.random.default_rng(seed)
    W, H = 150, 178
    w, h = int(W * d) // 2 * 2, int(H * d) // 2 * 2
    ox, oy = w / 2, h - 26 * d

    def px(x, y, z):
        return ox + x * d, oy + (y * SQUASH - z) * d

    n = 520
    cap = dict(a=rng.uniform(0, 2 * np.pi, n), b=rng.uniform(0, 2 * np.pi, n), r=rng.uniform(0.3, 1.0, n),
               size=rng.uniform(3, 6, n), heat=rng.uniform(0.85, 1.05, n), tau=rng.uniform(9, 15, n),
               light=rng.uniform(-0.12, 0.12, n))
    q = 260
    dome = dict(a=rng.uniform(0, 2 * np.pi, q), r=np.sqrt(rng.uniform(0, 1, q)), size=rng.uniform(3.5, 6.5, q),
                heat=rng.uniform(0.85, 1.05, q), tau=rng.uniform(8, 13, q), light=rng.uniform(-0.12, 0.12, q))
    m = 140
    stem = dict(s=rng.uniform(0, 1, m), a=rng.uniform(0, 2 * np.pi, m), r=rng.uniform(0, 1, m),
                size=rng.uniform(3.5, 6, m), light=rng.uniform(-0.1, 0.1, m))
    k = 220
    surge = dict(a=rng.uniform(0, 2 * np.pi, k), r=rng.uniform(0.6, 1.1, k) ** 0.5, z=rng.uniform(1, 9, k),
                 size=rng.uniform(3, 6, k), light=rng.uniform(-0.1, 0.15, k))
    tex_f = texture(rng, w, h, 2.5 * d, 4)
    tex_s = texture(rng, w, h, 4.5 * d, 4)
    out = []
    for f in range(frames):
        fl, sl, dl = Layer(w, h), Layer(w, h), Layer(w, h)
        life = np.clip((frames - 1 - f) / 12, 0, 1)
        hc = 10 + 78 * (1 - np.exp(-f / 15))           # cap height
        major = 7 + 30 * (1 - np.exp(-f / 11))          # torus radius: the cap spreads wide
        minor = 5 + 8 * (1 - np.exp(-f / 11))
        for i in range(n):
            b = cap["b"][i] + 0.16 * f                   # the cap rolls: up the outside, in over the top
            rr = minor * cap["r"][i]
            ring = major + rr * np.cos(b)
            x, y = ring * np.cos(cap["a"][i]), ring * np.sin(cap["a"][i])
            z = hc + rr * np.sin(b) * 0.55
            heat = cap["heat"][i] * np.exp(-f / cap["tau"][i]) * (0.75 + 0.25 * np.cos(b))
            sigma = cap["size"][i] * (0.6 + 0.6 * (1 - np.exp(-f / 6))) * d
            X, Y = px(x, y, z)
            fl.splat(X, Y, sigma, 0.5 * fire.smoothstep(0.12, 0.5, heat), heat)
            sl.splat(X, Y, sigma * 1.1, 0.45 * (1 - fire.smoothstep(0.2, 0.6, heat)) * life,
                     np.clip(0.3 + 0.45 * np.sin(b) - 0.2 * x / major + cap["light"][i], 0, 1))
        for i in range(q):                                 # the domed top of the cap, over the torus
            rr = dome["r"][i] * (major + 0.3 * minor)
            x, y = rr * np.cos(dome["a"][i]), rr * np.sin(dome["a"][i])
            z = hc + minor * (0.35 + 0.7 * (1 - dome["r"][i] ** 2))
            heat = dome["heat"][i] * np.exp(-f / dome["tau"][i])
            sigma = dome["size"][i] * (0.6 + 0.6 * (1 - np.exp(-f / 6))) * d
            X, Y = px(x, y, z)
            fl.splat(X, Y, sigma, 0.45 * fire.smoothstep(0.12, 0.5, heat), heat)
            sl.splat(X, Y, sigma * 1.1, 0.4 * (1 - fire.smoothstep(0.2, 0.6, heat)) * life,
                     np.clip(0.55 + 0.2 * (1 - dome["r"][i]) - 0.25 * x / major - 0.15 * y / major
                             + dome["light"][i], 0, 1))
        if f >= 3:
            for i in range(m):
                s = (stem["s"][i] + 0.025 * f) % 1.0
                z = s * hc * 0.92
                rad = (4 + 10 * s ** 3) * stem["r"][i] * min(1, f / 10)
                x, y = rad * np.cos(stem["a"][i]), rad * np.sin(stem["a"][i])
                X, Y = px(x, y, z)
                heat = 0.75 * np.exp(-f / 9) * (1 - s)
                fl.splat(X, Y, stem["size"][i] * d, 0.4 * fire.smoothstep(0.1, 0.4, heat), heat)
                dl.splat(X, Y, stem["size"][i] * d, 0.35 * min(1, (f - 3) / 4) * life,
                         np.clip(0.5 - 0.2 * x / 6 + stem["light"][i], 0, 1))
        rs = 8 + 58 * (1 - np.exp(-f / 9))
        for i in range(k):
            ang = surge["a"][i] + 0.004 * f
            x, y = np.cos(ang) * rs * surge["r"][i], np.sin(ang) * rs * surge["r"][i]
            X, Y = px(x, y, surge["z"][i] + 0.15 * f)
            dl.splat(X, Y, surge["size"][i] * (1 + 0.03 * f) * d, 0.11 * min(1, f / 3) * life,
                     np.clip(0.55 + 0.3 * np.sin(ang + 2.2) + surge["light"][i], 0, 1))
        if f < 6:
            X, Y = px(0, 0, 12)
            fl.splat(X, Y, [24, 20, 16, 12, 9, 7][f] * d, [4, 3, 2, 1.2, 0.7, 0.4][f], 1.0)
        frame = compose(fl, sl, dl, glow=0.65 * np.exp(-f / 14), fire_tex=scroll(tex_f, f * 0.6 * d),
                        smoke_tex=scroll(tex_s, f * 0.4 * d), smoke_dark=np.array([0.16, 0.13, 0.11]),
                        smoke_light=np.array([0.78, 0.72, 0.64]))
        out.append(frame.astype(np.float32))
    return out, (ox, oy)


# --- Directional sprites ------------------------------------------------------------------------------------------

def turn(frames, facings, squash=SQUASH):
    """East-facing ground-plane images -> one block of frames per facing (CCW from north), camera-squashed."""
    s = frames[0].shape[0]
    c = (s - 1) / 2
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    gx, gy = xx - c, (yy - c) / squash
    out = []
    for i in range(facings):
        al = 2 * np.pi * i / facings
        fx, fy = -np.sin(al), -np.cos(al)
        u = gx * fx + gy * fy                      # along the facing
        v = -gx * fy + gy * fx                     # across it
        coords = [c + v, c + u]
        for fr in frames:
            pre = np.dstack([fr[..., :3] * fr[..., 3:4], fr[..., 3:4]])
            res = np.stack([map_coordinates(pre[..., ch], coords, order=1, mode="constant") for ch in range(4)], -1)
            a = res[..., 3:4]
            out.append(np.dstack([res[..., :3] / np.maximum(a, 1e-5), a]).astype(np.float32))
    return out


def line_field(xx, yy, ang, length, width, taper=1.0):
    """A soft spike from the origin along ang (radians), fading towards its tip."""
    ux, uy = np.cos(ang), np.sin(ang)
    along = xx * ux + yy * uy
    across = -xx * uy + yy * ux
    t = np.clip(along / max(length, 1e-3), 0, 1)
    w = width * (1 - taper * t * 0.85)
    inside = (along > -width) & (along < length)
    return np.exp(-(across / np.maximum(w, 1e-3)) ** 2) * (1 - t) ** 1.2 * inside


def muzzle_cannon(frames, big, seed, d=MUZZLE_DENSITY):
    """Tank / ship gun: a forward tongue of flame with side jets out of the muzzle brake, then a smoke ring."""
    rng = np.random.default_rng(seed)
    k = 1.0 if big else 0.6
    S = int(44 * k * d) // 2 * 2 + 2
    c = (S - 1) / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    xx, yy = (xx - c) / d, (yy - c) / d
    tex = texture(rng, S, S, 1.6 * d)
    n = int(60 * k)
    puff = dict(a=rng.normal(0, 0.45, n), v=rng.uniform(1.2, 3.4, n) * k, size=rng.uniform(1.6, 3.0, n) * k,
                light=rng.uniform(-0.15, 0.15, n))
    out = []
    for f in range(frames):
        fl, sl, dl = Layer(S, S), Layer(S, S), Layer(S, S)
        u = f / max(1, frames - 1)
        # smoke cloud pushed forward, slowing and spreading
        for i in range(n):
            dist = puff["v"][i] * (1 - 0.62 ** (f + 1)) / 0.38
            x, y = np.cos(puff["a"][i]) * dist + 1.5 * k, np.sin(puff["a"][i]) * dist
            sl.splat(c + x * d, c + y * d, puff["size"][i] * (1 + 0.25 * f) * d,
                     0.5 * min(1, f / 1.5) * (1 - u) ** 1.5, np.clip(0.6 + puff["light"][i] - 0.05 * y, 0, 1))
        frame = compose(fl, sl, dl, glow=0, smoke_tex=scroll(tex, f * 0.5 * d))
        if f < 3:
            i_f = [1.0, 0.6, 0.25][f]
            core = line_field(xx, yy, 0, 14 * k * i_f + 3, 2.6 * k, 0.9) * 1.6
            core += line_field(xx, yy, 0.0, 22 * k * i_f, 1.1 * k, 0.5) * 0.7
            for side in (np.pi / 2, -np.pi / 2):
                core += line_field(xx - 1.2 * k, yy, side, 6 * k * i_f, 1.3 * k, 0.7)
            core += np.exp(-((xx - 1 * k) ** 2 + yy ** 2) / (2 * (2.2 * k * (0.6 + i_f)) ** 2)) * 1.3
            core *= 0.7 + 0.6 * tex
            heat = np.clip(core * 0.9, 0, 1)
            a = np.clip(1 - np.exp(-core * 2.2), 0, 1) * i_f ** 0.5
            flame = np.dstack([fire.ramp(heat ** 0.8), a])
            frame = over(flame, frame)
        out.append(frame.astype(np.float32))
    return out


def muzzle_mg(seed, d=MUZZLE_DENSITY):
    """Machine gun: a flickering star of flame (long forward spike, short side spikes), a wisp of smoke."""
    rng = np.random.default_rng(seed)
    S = int(26 * d) // 2 * 2 + 2
    c = (S - 1) / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    xx, yy = (xx - c) / d, (yy - c) / d
    out = []
    for f, i_f in enumerate([1.0, 0.45, 0.9, 0.35, 0.75, 0.2]):
        core = line_field(xx, yy, rng.normal(0, 0.05), 9 * i_f + 2, 1.3, 0.9) * 1.4
        for ang in (0.9, -0.9, 2.2, -2.2):
            core += line_field(xx, yy, ang + rng.normal(0, 0.12), (2.5 + 2 * rng.random()) * i_f, 0.7, 0.8) * 0.9
        core += np.exp(-(xx ** 2 + yy ** 2) / (2 * (1.3 * (0.5 + i_f)) ** 2)) * 1.3
        heat = np.clip(core, 0, 1)
        a = np.clip(1 - np.exp(-core * 2.5), 0, 1)
        flame = np.dstack([fire.ramp(heat ** 0.7), a])
        smoke = np.exp(-((xx - 4 - f * 0.8) ** 2 + (yy * 1.3) ** 2) / (2 * (1.5 + 0.5 * f) ** 2)) * 0.25 * min(1, f / 2)
        base = np.dstack([np.broadcast_to(SMOKE_LIGHT, smoke.shape + (3,)), smoke])
        out.append(over(flame, base).astype(np.float32))
    return out


def sam_launch(frames, seed, d=2.5):
    """SAM launch: a flash at the tube and a backblast of exhaust smoke and dust blowing out behind the launcher."""
    rng = np.random.default_rng(seed)
    S = int(64 * d) // 2 * 2 + 2
    c = (S - 1) / 2
    n = 160
    a = np.pi + rng.normal(0, 0.55, n)
    puff = dict(a=a, v=rng.uniform(1.5, 5.0, n), t0=rng.uniform(0, 2.5, n), size=rng.uniform(2.0, 3.6, n),
                light=rng.uniform(-0.1, 0.2, n), heat=rng.uniform(0.7, 1.0, n), dust=rng.random(n) < 0.35)
    tex = texture(rng, S, S, 2.5 * d)
    out = []
    for f in range(frames):
        fl, sl, dl = Layer(S, S), Layer(S, S), Layer(S, S)
        life = np.clip((frames - 1 - f) / 6, 0, 1)
        t = f - puff["t0"]
        for i in np.nonzero(t >= 0)[0]:
            ti = t[i]
            dist = puff["v"][i] * (1 - 0.7 ** ti) / 0.3
            x, y = np.cos(puff["a"][i]) * dist, np.sin(puff["a"][i]) * dist
            sigma = puff["size"][i] * (0.6 + 0.12 * ti) * d
            heat = puff["heat"][i] * np.exp(-ti / 1.6)
            fl.splat(c + x * d, c + y * d, sigma * 0.8, 0.5 * fire.smoothstep(0.15, 0.5, heat), heat)
            target = dl if puff["dust"][i] else sl
            target.splat(c + x * d, c + y * d, sigma, 0.35 * min(1, ti / 1.5) * life,
                         np.clip(0.6 + puff["light"][i] - 0.04 * y, 0, 1))
        if f < 3:
            fl.splat(c, c, [6, 4.5, 3][f] * d, [2.5, 1.4, 0.6][f], 1.0)
            fl.splat(c + 4 * d, c, [3, 2, 1][f] * d, [1.5, 0.8, 0.3][f], 1.0)
        out.append(compose(fl, sl, dl, glow=0.4 * np.exp(-f / 3), fire_tex=tex, smoke_tex=scroll(tex, f * d)))
    return out


# --- Projectiles --------------------------------------------------------------------------------------------------

def shell(kind, d=DENSITY):
    """East-facing tank shell (hot slug with a heat trail) or 50-cal tracer, on the ground plane."""
    S = int(28 * d) // 2 * 2 + 2
    c = (S - 1) / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    xx, yy = (xx - c) / d, (yy - c) / d
    if kind == "120mm":
        core = np.exp(-((xx / 2.2) ** 2 + (yy / 0.9) ** 2) * 1.5)
        trail = line_field(-xx, yy, 0, 11, 0.9, 0.6) * (xx < 0.5)
        glow = np.exp(-((xx / 4) ** 2 + (yy / 2.2) ** 2))
        heat = np.clip(core * 1.1 + trail * 0.55, 0, 1)
        a = np.clip(core * 1.4 + trail * 0.6 + glow * 0.35, 0, 1)
    else:
        core = line_field(-xx + 2, yy, 0, 9, 0.45, 0.4)
        glow = line_field(-xx + 2.5, yy, 0, 11, 1.4, 0.3)
        heat = np.clip(core * 1.2 + glow * 0.4, 0, 1)
        a = np.clip(core * 1.5 + glow * 0.45, 0, 1)
    return [np.dstack([fire.ramp(np.clip(0.35 + 0.65 * heat, 0, 1)), a]).astype(np.float32)]


def tumbler(frames, length, width, body, band, d=DENSITY, ss=3):
    """A small tumbling bomb (grenade, bomblet): shaded capsule turning end over end, lit from the top left."""
    S = int(max(length, width) * 1.6 * d) // 2 * 2 + 2
    c = (S * ss - 1) / 2
    yy, xx = np.mgrid[0:S * ss, 0:S * ss].astype(np.float32)
    xx, yy = (xx - c) / (d * ss), (yy - c) / (d * ss)
    out = []
    for f in range(frames):
        ang = np.pi * f / frames
        foreshort = 0.55 + 0.45 * abs(np.cos(2 * ang))       # the long axis tilts towards and away from the camera
        ux, uy = np.cos(ang), np.sin(ang)
        along = (xx * ux + yy * uy) / (length / 2 * foreshort)
        across = (-xx * uy + yy * ux) / (width / 2)
        r = np.sqrt(along ** 2 + across ** 2)
        inside = np.clip((1 - r) * 6, 0, 1)
        nz = np.sqrt(np.clip(1 - np.minimum(r, 1) ** 2, 0, 1))
        light = np.clip(0.25 + 0.75 * (nz * 0.6 + (-xx - yy) / max(length, width) * 0.8), 0.08, 1.2)
        rgb = np.array(body)[None, None] * light[..., None]
        stripe = np.exp(-((along - 0.25) / 0.12) ** 2)[..., None]
        rgb = rgb * (1 - stripe) + np.array(band)[None, None] * light[..., None] * stripe
        spec = np.clip((nz - 0.6) * 2.5, 0, 1) * np.clip((-xx - yy) / max(length, width) * 2, 0, 1)
        rgb = rgb + spec[..., None] * 0.6
        out.append(fire.downsample(np.dstack([np.clip(rgb, 0, 1), inside]), ss).astype(np.float32))
    return out


def nuke_missile(up, d=DENSITY, ss=2):
    """The nuclear missile climbing out of the silo (flame below) or diving onto the target (glowing nose)."""
    W, H = 22, 56
    w, h = int(W * d * ss), int(H * d * ss)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x = (xx - (w - 1) / 2) / (d * ss)
    y = (yy - (h - 1) / 2) / (d * ss)
    if not up:
        y = -y
    out = []
    rng = np.random.default_rng(7 if up else 8)
    for f in range(4):
        r = 2.4
        body_len = 13
        top, bottom = -15, -15 + body_len * 2
        nose = np.clip((y - top) / 5, 0, 1)                    # cone over the top 5 px
        radius = r * np.sqrt(nose)
        inside = (np.abs(x) < radius) & (y > top) & (y < bottom)
        fin = (y > bottom - 5) & (y < bottom) & (np.abs(x) < r + 2.6 * (y - (bottom - 5)) / 5) & (np.abs(x) > r - 0.3)
        shade = np.sqrt(np.clip(1 - (x / np.maximum(radius, 1e-3)) ** 2, 0, 1))
        light = np.clip(0.3 + 0.7 * shade * (0.8 - 0.35 * x / r), 0.1, 1)
        base = np.where(((y - top) % 9 < 1.6)[..., None], np.array([0.15, 0.15, 0.14]), np.array([0.86, 0.86, 0.82]))
        base = np.where((np.abs(y - (top + 9)) < 2.2)[..., None], np.array([0.85, 0.66, 0.1]), base)
        rgb = base * light[..., None]
        rgb = np.where(fin[..., None], np.array([0.25, 0.25, 0.24]) * (0.6 + 0.4 * (x > 0))[..., None], rgb)
        a = (inside | fin).astype(np.float32)
        img = np.dstack([rgb, a])
        if up:
            flick = 0.85 + 0.3 * rng.random()
            fy = (y - bottom) / (14 * flick)
            flame = np.exp(-(x / (1.7 * (1 + 0.6 * np.clip(fy, 0, 1)))) ** 2) * np.clip(1 - fy, 0, 1) * (fy > -0.05)
            heat = np.clip(flame * 1.3, 0, 1)
            img = over(img, np.dstack([fire.ramp(heat), np.clip(flame * 1.5, 0, 1)]))
        else:
            hot = np.exp(-((y - top - 2) / 3) ** 2) * inside
            img[..., :3] = img[..., :3] * (1 - 0.7 * hot[..., None]) + fire.ramp(np.clip(0.4 + 0.5 * hot, 0, 1)) * 0.7 * hot[..., None]
            glow = np.exp(-(x ** 2 + (y - top) ** 2) / 18) * 0.5 * (0.8 + 0.4 * rng.random())
            img = over(img, np.dstack([fire.ramp(np.full_like(glow, 0.6)), glow]))
        out.append(fire.downsample(img, ss).astype(np.float32))
    return out


def twinkle(frames, size, rot, seed, d=DENSITY):
    """Gem sparkle: a four-point star with a soft core, growing and fading."""
    rng = np.random.default_rng(seed)
    S = int(16 * d) // 2 * 2 + 2
    c = (S - 1) / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    xx, yy = (xx - c) / d, (yy - c) / d
    tint = np.array([1.0, 0.97, 0.92]) * (0.9 + 0.1 * rng.random(3))
    out = []
    for f in range(frames):
        k = np.sin(np.pi * (f + 0.5) / frames) ** 1.5
        star = np.zeros_like(xx)
        for i in range(4):
            ang = rot + i * np.pi / 2
            star += line_field(xx, yy, ang, size * k * (1.0 if i % 2 == 0 else 0.75), 0.45, 0.8)
        for i in range(4):
            star += line_field(xx, yy, rot + np.pi / 4 + i * np.pi / 2, size * k * 0.35, 0.35, 0.8) * 0.6
        star += np.exp(-(xx ** 2 + yy ** 2) / (2 * (0.9 * k + 0.2) ** 2)) * 1.4 * k
        a = np.clip(star, 0, 1)
        out.append(np.dstack([np.broadcast_to(tint, a.shape + (3,)), a]).astype(np.float32))
    return out


# --- Output -------------------------------------------------------------------------------------------------------

def save(name, frames, anchor=None, columns=None):
    h, w, _ = frames[0].shape
    columns = columns or min(len(frames), max(1, 4096 // w))
    rows = (len(frames) + columns - 1) // columns
    sheet = np.zeros((h * rows, w * columns, 4), np.float32)
    for i, fr in enumerate(frames):
        r, c = divmod(i, columns)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = fr
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    if anchor is not None:
        info.add_text("Offset", f"{w / 2 - anchor[0]:.0f},{h / 2 - anchor[1]:.0f}")
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}.png"),
                                                                       pnginfo=info, optimize=True)
    print(f"  {name}: {len(frames)} frames {w}x{h}")
    return frames


def seq(name, file, length, scale, facings=None, stride=None, extra=()):
    path = FILE.format(file)
    lines = [f"\t{name}:", f"\t\tFilename: {path}", "\t\tTilesetFilenames:"]
    lines += [f"\t\t\t{t}: {path}" for t in ("TEMPERAT", "SNOW", "DESERT", "INTERIOR")]
    lines += ["\t\tStart: 0", f"\t\tLength: {length}"]
    if facings:
        lines += [f"\t\tFacings: {facings}", "\t\tUseClassicFacings: False", f"\t\tStride: {stride or length}"]
    lines += ["\t\tOffset: 0,0", f"\t\tScale: {scale:.4f}"]
    return lines + [f"\t\t{e}" for e in extra]


def preview(name, frames, step=1):
    os.makedirs(PREVIEW, exist_ok=True)
    pick = frames[::step]
    h, w, _ = pick[0].shape
    bg = np.zeros((h, w * len(pick), 3), np.float32) + np.array([0.36, 0.42, 0.25])
    for i, fr in enumerate(pick):
        a = fr[..., 3:4]
        bg[:, i * w:(i + 1) * w] = fr[..., :3] * a + bg[:, i * w:(i + 1) * w] * (1 - a)
    Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8)).save(os.path.join(PREVIEW, f"blast-{name}.png"))


# Ground explosions: name -> (fireball radius, frames, options)
GROUND = {
    "small_explosion": (5.5, 18, dict(debris=10, sparks=16)),
    "med_explosion": (8.0, 22, dict(debris=18, sparks=24)),
    "large_explosion": (11.0, 24, dict(debris=24, sparks=30, smoke=1.2)),
    "artillery_explosion": (11.0, 26, dict(debris=30, sparks=20, column=1.0, smoke=1.1)),
    "building": (16.0, 28, dict(debris=34, sparks=36, smoke=1.4, dust=1.3)),
    "flak_explosion_ground": (5.0, 14, dict(debris=8, sparks=14, dark=0.6, dust=0.6)),
}
AIR = {
    "small_explosion_air": (5.0, 14, dict(debris=6, sparks=16, dark=0.75)),
    "med_explosion_air": (7.5, 18, dict(debris=10, sparks=22, dark=0.55)),
}
# Muzzle users: image -> (sequence, sheet, length)
MUZZLES = {
    "2tnk": ("muzzle", "cannon", 8), "3tnk": ("muzzle", "cannon", 8), "4tnk": ("muzzle", "cannon", 8),
    "arty": ("muzzle", "cannon", 8), "ctnk": ("muzzle", "cannon", 8), "ca": ("muzzle", "cannon", 8),
    "pt": ("muzzle", "cannon", 8), "gun": ("muzzle", "cannon", 8),
    "1tnk": ("muzzle", "autocannon", 5), "ftrk": ("muzzle", "autocannon", 5), "agun": ("muzzle", "autocannon", 5),
    "jeep": ("muzzle", "mg", 6), "apc": ("muzzle", "mg", 6), "pbox": ("muzzle", "mg", 6),
    "hbox": ("muzzle", "mg", 6), "yak": ("muzzle", "mg", 6), "hind": ("muzzle", "mg", 6), "mh60": ("muzzle", "mg", 6),
    "e1": ("garrison-muzzle", "mg", 6), "e7": ("garrison-muzzle", "mg", 3),
    "sam": ("muzzle", "sam", 18),
}
MUZZLE_SHEETS = {"cannon": (32, 8), "autocannon": (32, 5), "mg": (32, 6), "sam": (16, 18)}


def main():
    show = "--preview" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    y = ["# HD explosions, muzzle flashes, shells and gem sparkles (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_blast_fx.py - edit that script, not this file.", "", "explosion:"]
    s4 = 1 / DENSITY

    print("explosions")
    for i, (name, (R, n, opts)) in enumerate(GROUND.items()):
        frames, anchor = blast(R, n, 300 + i, **opts)
        save(name, frames, anchor)
        y += seq(name, name, n, s4, extra=["ZOffset: 2047"])
        if name == "artillery_explosion":
            y += seq("self_destruct", name, n, s4, extra=["ZOffset: 2047"])
        if show:
            preview(name, frames, 2)
    for i, (name, (R, n, opts)) in enumerate(AIR.items()):
        frames, anchor = blast(R, n, 400 + i, air=True, dust=0, **opts)
        save(name, frames, anchor)
        y += seq(name, name, n, s4, extra=["ZOffset: 511"])
        if show:
            preview(name, frames, 2)

    piff, anchor = blast(2.2, 9, 500, fire_amt=0.25, smoke=0.0, dust=0.55, debris=7, sparks=9, flash=0.8)
    save("piff", piff, anchor)
    y += seq("piff", "piff", 9, s4, extra=["ZOffset: 2047"])
    piffs, anchor2 = scatter(piff, anchor, 4, 15, 501, 5 * DENSITY)
    save("piffs", piffs, anchor2)
    y += seq("piffs", "piffs", 15, s4, extra=["ZOffset: 2047"])
    wp, anchor = water_hit(0.2, 12, 502)
    save("water_piff", wp, anchor)
    y += seq("water_piff", "water_piff", 12, s4, extra=["ZOffset: 0"])
    wps, anchor2 = scatter(wp, anchor, 3, 18, 503, 5 * DENSITY)
    save("water_piffs", wps, anchor2)
    y += seq("water_piffs", "water_piffs", 18, s4, extra=["ZOffset: 0"])
    if show:
        preview("piffs", piffs, 1)
        preview("water_piffs", wps, 2)

    # the nuke mushroom cloud is drawn by make_nuke_fx.py (hd-nuke-fx.yaml)
    y.append("")

    print("muzzle flashes")
    sheets = {
        "cannon": muzzle_cannon(8, True, 700), "autocannon": muzzle_cannon(5, False, 701),
        "mg": muzzle_mg(702), "sam": sam_launch(18, 703),
    }
    for name, frames in sheets.items():
        facings, _ = MUZZLE_SHEETS[name]
        save("muzzle-" + name, turn(frames, facings))
        if show:
            preview("muzzle-" + name, turn(frames, 8)[:len(frames)] + turn(frames, 8)[2 * len(frames):3 * len(frames)])
    for image, (sequence, sheet, length) in MUZZLES.items():
        facings, per = MUZZLE_SHEETS[sheet]
        d = 2.5 if sheet == "sam" else MUZZLE_DENSITY
        extra = ["-Combine:"] if image == "e1" else []     # e1's classic garrison flash combines two sprites
        y += [f"{image}:"] + seq(sequence, "muzzle-" + sheet, length, 1 / d, facings, per, extra) + [""]

    print("projectiles")
    for name in ("120mm", "50cal"):
        save(name, turn(shell(name), 32))
        y += [f"{name}:"] + seq("idle", name, 1, s4, 32, 1, ["ZOffset: 1023"]) + [""]
    bomb = save("bomb", tumbler(8, 3.6, 2.4, (0.24, 0.27, 0.16), (0.55, 0.5, 0.3)))
    y += ["bomb:"] + seq("idle", "bomb", 8, s4, extra=["ZOffset: 1023"]) + [""]
    bomblet = save("bomblet", tumbler(7, 3.4, 1.7, (0.3, 0.3, 0.3), (0.85, 0.45, 0.1)))
    y += ["bomblet:"] + seq("idle", "bomblet", 7, s4, extra=["ZOffset: 1023"]) + [""]
    # the nuke missile in flight (atomic up / down) is rendered with the silo: artsrc/buildings/nuke_silo
    if show:
        preview("projectiles", [np.pad(f, ((0, 0), (0, 0), (0, 0))) for f in turn(shell("120mm"), 8)])
        preview("tracer", turn(shell("50cal"), 8))
        preview("bomb", bomb + bomblet[:0])
        preview("bomblet", bomblet)

    print("sparkles")
    y.append("twinkle:")
    for i, (n, size, rot) in enumerate(((6, 5.5, 0.0), (5, 4.5, 0.4), (5, 3.8, -0.3))):
        fr = save(f"twinkle{i + 1}", twinkle(n, size, rot, 800 + i))
        y += seq(f"twinkle{i + 1}", f"twinkle{i + 1}", n, s4, extra=["BlendMode: Additive"])
        if show:
            preview(f"twinkle{i + 1}", fr)

    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))


if __name__ == "__main__":
    main()
