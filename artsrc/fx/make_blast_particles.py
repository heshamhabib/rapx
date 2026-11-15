#!/usr/bin/env python3
"""
HD blast particle sprites (RedAlert Project X, cinematic combat FX).

  python3 artsrc/fx/make_blast_particles.py [--preview]

Sprites for the particle explosions drawn by OpenRA.Mods.RAPX (PxExplosionWarhead, PxThrownBody), all at 3x density
(Scale 1/3), written to mods/rapx/bits/hd/fx/blast/px-*.png and mods/rapx/sequences/hd-blast-particles.yaml (merged
into the `pxfx` image, listed after hd-nuke-fx.yaml in mod.yaml):

  xfire    rolling fireball that cools from white-hot to red and turns into lit, sooty smoke (2 variants x 16 frames)
  xsmoke   volumetric smoke puffs, lit from the upper left, neutral grey so the game can tint them (12 variants)
  xdust    ground dust wave (an ellipse in the game's view) racing outwards and thinning (8 frames)
  xshock   thin shock ring on the ground (6 frames)
  xflash   detonation glare with streaks (additive)
  xlight   soft light the blast throws on the ground around it (additive)
  xdebris  dirt clods, rocks and metal shards (16 frames)
  xember   glowing ember streak (additive)
  shadow   soft drop shadow for thrown bodies and debris

--preview writes artsrc/fx/preview/blast-particles.png.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, PngImagePlugin
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_fire_fx as fire  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "blast")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-blast-particles.yaml")
PREVIEW = os.path.join(HERE, "preview", "blast-particles.png")
DENSITY = 3.0
SCALE = f"{1 / DENSITY:.4f}"

rng = np.random.default_rng(1915)


def grid(w, h):
    """Normalised coordinates: -1..1 across the sprite in both axes."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return (x - (w - 1) / 2) / (w / 2), (y - (h - 1) / 2) / (h / 2)


def noise(w, h, scale, octaves=3):
    total = np.zeros((h, w), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        n = gaussian_filter(rng.random((h, w)).astype(np.float32), max(0.6, scale / (2 ** o)), mode="wrap")
        n = (n - n.min()) / (n.max() - n.min() + 1e-6)
        total += n * amp
        norm += amp
        amp *= 0.5
    return total / norm


def smoothstep(a, b, x):
    return fire.smoothstep(a, b, x)


def rgba(v, a, warm=(1.0, 1.0, 1.0)):
    v = np.asarray(v, np.float32)
    if v.ndim == 2:
        v = np.dstack([v * warm[0], v * warm[1], v * warm[2]])
    return np.dstack([np.clip(v, 0, 1), np.clip(a, 0, 1)])


# --- Fire ---------------------------------------------------------------------------------------------------------

def xfire(size=144, frames=16, variants=2):
    """Rolling fireball: a lumpy, turbulent ball with dark soot folds between bright lobes. It swells, cools from
    white-hot to deep red and turns into a lit, sooty smoke cloud (one evolution per variant, not a loop)."""
    ss = 2
    S = size * ss
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    xn = (x - (S - 1) / 2) / (S / 2)
    out = []
    for _ in range(variants):
        n1 = fire.periodic_noise((frames, S, S), (frames / 4, S / 7, S / 7))
        n2 = fire.periodic_noise((frames, S, S), (frames / 3, S / 16, S / 16), 2)
        n3 = fire.periodic_noise((frames, S, S), (frames / 3, S / 36, S / 36), 2)
        n4 = fire.periodic_noise((frames, S, S), (frames / 2.5, S / 11, S / 11), 2)
        lobes = [(rng.uniform(-0.42, 0.42), rng.uniform(-0.42, 0.42), rng.uniform(0.32, 0.58))
                 for _ in range(rng.integers(5, 9))]
        for i in range(frames):
            t = i / (frames - 1)
            grow = 1 - (1 - min(1, t * 1.6)) ** 3
            r_max = 0.95 * (0.3 + 0.7 * grow)
            yn = (y - (0.55 - 0.12 * t) * (S - 1)) / (S / 2)
            # lumpy body: lobes that drift outwards as the ball swells, a round core, noise on every rim
            dens = np.zeros((S, S), np.float32)
            for lx, ly, lr in lobes:
                rr = lr * r_max * (0.9 + 0.3 * n1[i])
                d2 = ((xn - lx * r_max * 1.1) ** 2 + ((yn - ly * r_max * 1.1) * 1.15) ** 2) / np.maximum(rr, 1e-3) ** 2
                dens = np.maximum(dens, np.clip(1 - d2, 0, 1))
            core = np.clip(1 - (xn ** 2 + (yn * 1.2) ** 2) / r_max ** 2, 0, 1)
            dens = np.maximum(dens, core * 0.9)
            dens = np.clip(dens * (0.8 + 0.45 * n1[i]) - 0.08, 0, 1)
            heat0 = max(0.0, 1 - t * 1.25) ** 0.8
            folds = smoothstep(0.25, 0.6, n4[i])                       # dark soot between the bright lobes
            detail = (0.35 + 0.95 * n2[i]) * (0.65 + 0.7 * n3[i])
            heat = np.clip(dens ** 0.55 * heat0 * detail * (0.45 + 0.75 * folds) * 1.7, 0, 1)
            heat = np.maximum(heat, core ** 2 * heat0 * 1.1 * (0.7 + 0.5 * n3[i]))   # white-hot centre
            fire_a = smoothstep(0.05, 0.3, heat) * smoothstep(0.0, 0.08, dens)
            fire_rgb = fire.ramp(np.clip(heat ** 1.15, 0, 1))
            smoke_a = np.clip(smoothstep(0.0, 0.25, dens) * 0.92 * smoothstep(0.06, 0.45, t)
                              * (1 - smoothstep(0.78, 1.0, t)) * (0.5 + 0.6 * n1[i]) * (0.8 + 0.4 * n3[i]), 0, 0.95)
            smoke_v = 0.08 + 0.16 * n1[i] + 0.14 * np.clip(-xn - yn, 0, 1) + 0.06 * n3[i] + 0.1 * folds * heat0
            out.append(fire.downsample(fire.compose(fire_rgb, fire_a, smoke_v, smoke_a, glow=0.5 * heat0), ss))
    return out


# --- Smoke --------------------------------------------------------------------------------------------------------

def xsmoke(size=128, variants=12):
    """Volumetric puffs: a cauliflower of small lobes over a bigger mass, lit from the upper left with a soft shadow
    side, a little rim light and fine turbulence. Neutral grey, so the game tints it (soot, dust, steam)."""
    frames = []
    x, y = grid(size, size)
    light_dir = np.array([-0.6, -0.6, 0.52], np.float32)
    light_dir /= np.linalg.norm(light_dir)
    for _ in range(variants):
        dens = np.zeros((size, size), np.float32)
        for _ in range(rng.integers(2, 4)):
            cx, cy = rng.uniform(-0.18, 0.18, 2)
            r = rng.uniform(0.42, 0.55)
            dens = np.maximum(dens, np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / r ** 2 * 1.5))
        for _ in range(rng.integers(10, 17)):
            a, d = rng.uniform(0, 2 * np.pi), rng.uniform(0.22, 0.5)
            cx, cy = np.cos(a) * d, np.sin(a) * d * 0.95
            r = rng.uniform(0.16, 0.3)
            dens = np.maximum(dens, np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / r ** 2 * 1.5) * rng.uniform(0.8, 1.0))
        fine = noise(size, size, size / 12, 3)
        coarse = noise(size, size, size / 4, 2)
        dens = dens * (0.78 + 0.35 * coarse) * (0.88 + 0.24 * fine)
        a = np.clip((dens - 0.16) * 2.6, 0, 1) ** 1.3
        a = gaussian_filter(a, 0.6) * (0.78 + 0.28 * fine)
        soft = gaussian_filter(dens, size * 0.018)
        gy, gx = np.gradient(soft)
        nz = np.full_like(soft, 0.11)
        norm = np.sqrt(gx ** 2 + gy ** 2 + nz ** 2) + 1e-6
        lit = (-gx * light_dir[0] - gy * light_dir[1] + nz * light_dir[2]) / norm
        v = 0.3 + 0.7 * np.clip(lit * 1.05 + 0.3, 0, 1)
        v *= 1 - 0.3 * np.clip(soft * 1.4, 0, 1)         # self-shadowing in the thick middle
        rim = np.clip(1 - a, 0, 1) * np.clip(a * 4, 0, 1) * 0.25
        v = np.clip(v * (0.9 + 0.2 * fine) + rim, 0.08, 1)
        frames.append(rgba(v, a * 0.96))
    return frames


# --- Ground waves -------------------------------------------------------------------------------------------------

def xdust(w=256, h=154, n=8):
    """Dust wave racing out along the ground: a thick ragged ring with a haze trailing inside it."""
    frames = []
    x, y = grid(w, h)
    r = np.sqrt(x ** 2 + y ** 2)
    ang = np.arctan2(y, x)
    rag = noise(w, h, w / 10, 2)
    fine = noise(w, h, w / 28, 2)
    for i in range(n):
        t = (i + 0.5) / n
        radius = 0.18 + 0.78 * (1 - (1 - t) ** 1.6)
        width = 0.1 + 0.12 * t
        rr = r * (1 + 0.16 * (rag - 0.5) + 0.05 * np.sin(ang * 9 + i))
        band = np.exp(-((rr - radius) / width) ** 2)
        haze = smoothstep(radius + 0.05, radius * 0.25, rr) * 0.4 * (1 - t) ** 0.7
        a = np.clip((band * 1.15 + haze) * (1 - t) ** 0.85 * (0.7 + 0.45 * fine), 0, 1)
        a *= smoothstep(1.0, 0.92, r)
        v = 0.78 - 0.16 * (x + y) / 2 + 0.18 * (fine - 0.5)
        frames.append(rgba(np.clip(v, 0.3, 1), a))
    return frames


def xshock(w=192, h=116, n=6):
    """The shock front: a thin bright ring with a faint halo just outside it."""
    frames = []
    x, y = grid(w, h)
    r = np.sqrt(x ** 2 + y ** 2)
    for i in range(n):
        t = (i + 0.5) / n
        radius = 0.25 + 0.68 * (1 - (1 - t) ** 1.8)
        width = 0.03 + 0.02 * t
        ring = np.exp(-((r - radius) / width) ** 2)
        halo = 0.3 * np.exp(-((r - radius - 0.04) / (width * 3.5)) ** 2)
        a = np.clip((ring + halo) * (1 - t) ** 0.6, 0, 1) * smoothstep(1.0, 0.95, r)
        frames.append(rgba(np.ones_like(a), a))
    return frames


# --- Light --------------------------------------------------------------------------------------------------------

def xflash(size=192):
    """Detonation glare: a white core, a warm halo and a handful of anisotropic streaks (additive)."""
    x, y = grid(size, size)
    r = np.sqrt(x ** 2 + y ** 2)
    core = np.exp(-(r / 0.11) ** 2)
    halo = 0.42 * np.exp(-(r / 0.42) ** 2) + 0.12 * np.exp(-(r / 0.8) ** 2)
    streaks = np.zeros_like(r)
    for a0, ln in zip(rng.uniform(0, np.pi, 6), rng.uniform(0.45, 0.95, 6)):
        along = x * np.cos(a0) + y * np.sin(a0)
        perp = -x * np.sin(a0) + y * np.cos(a0)
        streaks += np.exp(-(perp / 0.012) ** 2) * np.exp(-(along / ln) ** 2) * 0.8
    v = np.clip(core * 1.3 + halo + streaks, 0, 1)
    warm = np.array([1.0, 0.86, 0.62], np.float32)
    rgb = warm[None, None, :] * (1 - core[..., None]) + core[..., None]
    return np.dstack([np.clip(rgb, 0, 1), v])


def xlight(w=256, h=154):
    """The light a blast throws on the ground: a soft warm ellipse (additive)."""
    x, y = grid(w, h)
    r = np.clip(np.sqrt(x ** 2 + y ** 2), 0, 1)
    a = (1 - r) ** 2.2 * 0.95
    return rgba(np.ones_like(a), a, (1.0, 0.9, 0.72))


def xember(w=40, h=10):
    """A glowing ember drawn as a short symmetric streak (the game turns it along its flight)."""
    x, y = grid(w, h)
    a = np.exp(-(y * 1.9) ** 2) * np.exp(-(x * 1.4) ** 2)
    a = np.clip(a * 1.2 + np.exp(-((x * 4) ** 2 + (y * 2) ** 2)) * 0.6, 0, 1)
    return rgba(np.ones_like(a), a, (1.0, 0.95, 0.85))


def shadow(w=96, h=58):
    x, y = grid(w, h)
    r = np.sqrt(x ** 2 + y ** 2)
    a = smoothstep(1.0, 0.25, r) * 0.92
    return rgba(np.ones_like(a), a)


# --- Debris -------------------------------------------------------------------------------------------------------

def polygon_mask(size, pts, ss=4):
    im = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(im).polygon([((px + 1) / 2 * size * ss, (py + 1) / 2 * size * ss) for px, py in pts], fill=255)
    m = np.asarray(im, np.float32) / 255
    return m.reshape(size, ss, size, ss).mean(axis=(1, 3))


def xdebris(size=32, n=16):
    frames = []
    x, y = grid(size, size)
    for i in range(n):
        shard = i % 5 == 2 or i % 5 == 4
        k = rng.integers(3, 6) if shard else rng.integers(6, 10)
        angs = np.sort(rng.uniform(0, 2 * np.pi, k))
        if shard:
            rad = rng.uniform(0.2, 0.75, k) * np.where(np.cos(angs) > 0, 1.0, 0.55)
        else:
            rad = rng.uniform(0.38, 0.62, k)
        pts = list(zip(np.cos(angs) * rad, np.sin(angs) * rad))
        m = polygon_mask(size, pts)
        if not shard:
            m = np.clip(gaussian_filter(m, 1.2) * 1.5 - 0.2, 0, 1)
        soft = gaussian_filter(m, 2.0)
        gy, gx = np.gradient(soft)
        lit = np.clip(0.5 - (gx + gy) * 9.0, 0, 1)
        grain = noise(size, size, size / 6, 2)
        if shard:
            base = np.array([0.3, 0.3, 0.31], np.float32) * (0.55 + 0.9 * lit)[..., None]
            edge = np.clip(m - gaussian_filter(m, 1.0), 0, 1) * 2.5
            base = base + edge[..., None] * np.array([0.75, 0.72, 0.65]) * lit[..., None]
        else:
            tone = rng.uniform(0.75, 1.1)
            base = np.array([0.52, 0.44, 0.35], np.float32) * tone * (0.45 + 0.8 * lit)[..., None]
            base *= (0.8 + 0.4 * grain)[..., None]
        frames.append(np.dstack([np.clip(base, 0, 1), m]))
    return frames


# --- Output -------------------------------------------------------------------------------------------------------

def save(name, frames):
    h, w, _ = frames[0].shape
    sheet = np.concatenate(frames, axis=1)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    path = os.path.join(OUT, f"px-{name}.png")
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(path, pnginfo=info, optimize=True)
    print(f"  {name}: {len(frames)} frames {w}x{h}")
    return len(frames)


def main():
    os.makedirs(OUT, exist_ok=True)
    preview = "--preview" in sys.argv
    sheets = [
        ("xfire", xfire(), []),
        ("xsmoke", xsmoke(), []),
        ("xdust", xdust(), []),
        ("xshock", xshock(), []),
        ("xflash", [xflash()], ["BlendMode: Additive"]),
        ("xlight", [xlight()], ["BlendMode: Additive"]),
        ("xdebris", xdebris(), []),
        ("xember", [xember()], ["BlendMode: Additive"]),
        ("shadow", [shadow()], []),
    ]
    yaml = ["# HD blast particle sprites (RedAlert Project X): fireballs, smoke, dust and shock waves, debris, embers.",
            "# GENERATED by artsrc/fx/make_blast_particles.py - edit that script, not this file.",
            "", "pxfx:"]
    for name, frames, extra in sheets:
        n = save(name, frames)
        yaml += [f"\t{name}:", f"\t\tFilename: ra|bits/hd/fx/blast/px-{name}.png", "\t\tStart: 0", f"\t\tLength: {n}",
                 f"\t\tScale: {SCALE}"]
        yaml += [f"\t\t{e}" for e in extra]
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(yaml) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))

    if preview:
        rows = []
        for name, frames, extra in sheets:
            h, w, _ = frames[0].shape
            cols = min(len(frames), 16)
            row = Image.new("RGBA", (w * cols, h), (88, 118, 86, 255))
            for i, fr in enumerate(frames[:cols]):
                im = Image.fromarray((np.clip(fr, 0, 1) * 255).astype(np.uint8))
                if "BlendMode: Additive" in extra:
                    base = row.crop((i * w, 0, (i + 1) * w, h)).convert("RGB")
                    add = np.asarray(base, np.float32) / 255 + fr[..., :3] * fr[..., 3:4]
                    im = Image.fromarray((np.clip(add, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
                    row.paste(im, (i * w, 0))
                else:
                    row.alpha_composite(im, (i * w, 0))
            rows.append(row)
        width = max(r.size[0] for r in rows)
        out = Image.new("RGBA", (width, sum(r.size[1] for r in rows)), (88, 118, 86, 255))
        yy = 0
        for r in rows:
            out.paste(r, (0, yy))
            yy += r.size[1]
        os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
        out.save(PREVIEW)
        print("preview", os.path.relpath(PREVIEW, ROOT))


if __name__ == "__main__":
    main()
