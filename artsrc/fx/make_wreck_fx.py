#!/usr/bin/env python3
"""
One style for every destroyed vehicle (WithPxWreckFx on ^Husk).

  python3 artsrc/fx/make_wreck_fx.py

1. HD effect sprites, added to the `pxfx` image in mods/rapx/sequences/hd-wreck-fx.yaml:
     wfire   32-frame seamless loop of a burning fire (tongues licking upwards), additive
     wsmoke  8 lit volumetric smoke puffs (white, tinted by the trait)
2. Charred wreck sheets mods/rapx/bits/hd/units/<unit>-wreck.png made from the live HD sprites, so every wreck is
   the same model as the vehicle it was: hull burnt to soot-black metal with heat-tinted and ash-grey patches.
   The baked ground shadow is kept as it is (the old husks blackened the shadow into a disc).
   Rerun after re-rendering a vehicle.
"""
import os

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FX = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx")
UNITS = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "units")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-wreck-fx.yaml")
DENSITY = 4.0                     # sprite pixels per world pixel

# source sheet -> (wreck sheet, frames to keep: None = all)
WRECKS = {
    "1tnk": None, "2tnk": None, "mtnk": None, "3tnk": None, "4tnk": None, "mgg": None,
    "mcv": None, "xr85": None, "spdr": None, "harv": 32, "harvempty": 32,
}

rng = np.random.default_rng(11)


def periodic_noise(h, w, scale, octaves=4):
    """Smooth value noise in [0, 1] that tiles in both directions."""
    total = np.zeros((h, w), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        n = gaussian_filter(rng.random((h, w)).astype(np.float32), max(scale / (2 ** o), 0.6), mode="wrap")
        n = (n - n.min()) / (n.max() - n.min() + 1e-6)
        total += n * amp
        norm += amp
        amp *= 0.5
    return total / norm


def save_sheet(path, frames):
    h, w, _ = frames[0].shape
    cols = min(len(frames), max(1, 2048 // w))
    rows = (len(frames) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 4), np.float32)
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = f
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    Image.fromarray((np.clip(sheet, 0, 1) * 255).round().astype(np.uint8)).save(path, pnginfo=info, optimize=True)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------------------------------------ fire

def make_fire(frames=32, w=112, h=176):
    """Seamless loop: two periodic noise fields scroll upwards by whole tiles over the loop; a tongue-shaped mask,
    sideways licking and a black-body colour ramp turn them into flames."""
    tile = h * 2
    n1 = periodic_noise(tile, w, 9)
    n2 = periodic_noise(tile, w, 4)
    warp = periodic_noise(tile, w, 14)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xs - (w - 1) / 2) / (w / 2)               # -1..1 across
    v = 1 - ys / (h - 1)                           # 0 at the base, 1 at the top
    out = []
    for f in range(frames):
        t = f / frames
        # Layer offsets move a whole number of tiles per loop, so frame `frames` == frame 0
        o1 = (ys + t * tile * 2) % tile
        o2 = (ys + t * tile * 3) % tile
        ow = (ys + t * tile * 1) % tile
        lick = (map_coordinates(warp, [ow, xs], order=1, mode="wrap") - 0.5) * 0.9 * v
        a = map_coordinates(n1, [o1, (xs + lick * w * 0.4) % w], order=1, mode="wrap")
        b = map_coordinates(n2, [o2, (xs + lick * w * 0.6) % w], order=1, mode="wrap")
        turb = a * 0.65 + b * 0.35
        # Narrow tongue with a soft, rounded base (no hard edge where it meets the hull)
        width = 0.5 * (1 - v) ** 0.9 + 0.06
        body = smoothstep(0, 0.75, 1 - np.abs(u + lick * 0.5) / width) * smoothstep(0.0, 0.2, v)
        # Turbulence breaks the cone into separate tongues higher up
        heat = body * (0.25 + 1.15 * turb) - v * 0.7 - (1 - b) * 0.45 * v
        heat = np.clip(heat * 1.15, 0, 1)
        # Black-body-ish ramp: deep red -> orange -> yellow, white only in the hottest core
        r = smoothstep(0.02, 0.3, heat)
        g = smoothstep(0.2, 0.8, heat) * 0.85
        bl = smoothstep(0.82, 1.0, heat) * 0.55
        alpha = smoothstep(0.02, 0.4, heat)
        # Straight alpha (normal blending) so the fire reads the same over bright and dark ground; the separate
        # additive glow in WithPxWreckFx adds the light. Cooler edges are a little transparent smoky red.
        out.append(np.stack([np.maximum(r, 0.35), g * (0.55 + 0.45 * r), bl, alpha], -1))
    return out


# ----------------------------------------------------------------------------------------------------------- smoke

def make_smoke(count=8, size=144):
    """Billowy puffs lit from the north-west: lumpy outline, inner noise, shading from the density gradient."""
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = (size - 1) / 2
    ang = np.arctan2(ys - cy, xs - cx)
    rad = np.hypot(xs - cx, ys - cy) / (size / 2)
    out = []
    for i in range(count):
        lumps = sum(rng.uniform(0.03, 0.06) * np.cos(k * ang + rng.uniform(0, 6.3)) for k in (2, 3, 4))
        detail = periodic_noise(size, size, 12) * 0.6 + periodic_noise(size, size, 4) * 0.4
        # Cauliflower outline: the noise itself bites into a soft round falloff
        falloff = 1 - (rad / (0.82 + lumps)) ** 2
        density = smoothstep(0.0, 1.0, falloff * 0.95 + (detail - 0.5) * 0.85) * smoothstep(0, 0.2, falloff)
        # Shade a height field (overall dome + billows) lit from the north-west
        height = gaussian_filter(density, 4) * 0.7 + gaussian_filter(detail, 2) * 0.5
        gy, gx = np.gradient(height)
        lit = 0.68 + (gx * 0.6 + gy * 0.8) * 26
        lit = np.clip(lit, 0.3, 1.1) * (0.9 + 0.1 * detail)
        shade = np.clip(lit, 0, 1)
        alpha = density ** 1.4
        out.append(np.stack([shade, shade, shade * 0.98, alpha], -1))
    return out


# ---------------------------------------------------------------------------------------------------------- wrecks

def char_sheet(name, keep):
    src = Image.open(os.path.join(UNITS, f"{name}.png"))
    fw, fh = (int(v) for v in src.info["FrameSize"].split(","))
    count = int(src.info["FrameAmount"])
    a = np.asarray(src.convert("RGBA")).astype(np.float32) / 255
    cols = a.shape[1] // fw
    keep = keep or count
    frames = []
    for i in range(keep):
        r, c = divmod(i, cols)
        frames.append(a[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw].copy())

    out = []
    for f in frames:
        rgb, al = f[..., :3], f[..., 3]
        # Body vs baked shadow: the shadow is semi-transparent and near black
        body = smoothstep(0.55, 0.8, al)
        lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
        soot = periodic_noise(fh, fw, 5)
        heat = periodic_noise(fh, fw, 14)
        ash = periodic_noise(fh, fw, 2.5)
        # Charcoal metal that keeps the model's light and shade
        base = 0.05 + lum * 0.42 + (lum - 0.45) * 0.12
        charred = np.stack([base * 1.02, base * 0.96, base * 0.9], -1)
        # Heat-tinted steel (brown / rust / blued) in broad patches
        tint = smoothstep(0.55, 0.8, heat)[..., None]
        charred = charred * (1 - 0.55 * tint) + tint * 0.55 * np.stack([base * 1.9, base * 1.05, base * 0.62], -1)
        # Soot blotches and grey ash flecks
        charred *= (1 - 0.45 * smoothstep(0.5, 0.75, soot))[..., None]
        flecks = smoothstep(0.78, 0.92, ash) * smoothstep(0.35, 0.9, lum)
        charred = charred * (1 - flecks[..., None]) + flecks[..., None] * np.array([0.42, 0.41, 0.4], np.float32)
        rgb2 = rgb * (1 - body[..., None]) + np.clip(charred, 0, 1) * body[..., None]
        out.append(np.concatenate([rgb2, al[..., None]], -1))

    path = os.path.join(UNITS, f"{name}-wreck.png")
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{fw},{fh}")
    info.add_text("FrameAmount", str(len(out)))
    rows = (len(out) + cols - 1) // cols
    sheet = np.zeros((rows * fh, cols * fw, 4), np.float32)
    for i, f in enumerate(out):
        r, c = divmod(i, cols)
        sheet[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw] = f
    Image.fromarray((np.clip(sheet, 0, 1) * 255).round().astype(np.uint8)).save(path, pnginfo=info, optimize=True)
    print(f"{path}: {len(out)} frames")


def main():
    os.makedirs(FX, exist_ok=True)
    fire = make_fire()
    save_sheet(os.path.join(FX, "wfire.png"), fire)
    smoke = make_smoke()
    save_sheet(os.path.join(FX, "wsmoke.png"), smoke)

    scale = 1 / DENSITY
    with open(SEQUENCES, "w") as f:
        f.write("# HD wreck fire and smoke (RedAlert Project X), merged into the `pxfx` image of hd-fx.yaml.\n")
        f.write("# GENERATED by artsrc/fx/make_wreck_fx.py - edit that script, not this file.\n\n")
        f.write("pxfx:\n")
        f.write(f"\twfire:\n\t\tFilename: ra|bits/hd/fx/wfire.png\n\t\tLength: {len(fire)}\n"
                f"\t\tScale: {scale:.4f}\n")
        f.write(f"\twsmoke:\n\t\tFilename: ra|bits/hd/fx/wsmoke.png\n\t\tLength: {len(smoke)}\n\t\tScale: {scale:.4f}\n")
    print(f"{SEQUENCES}: wfire {len(fire)}, wsmoke {len(smoke)}")

    for name, keep in WRECKS.items():
        char_sheet(name, keep)


if __name__ == "__main__":
    main()
