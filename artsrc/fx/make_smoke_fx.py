#!/usr/bin/env python3
"""
Red Smoke "Danger Close" (IDEA-46): HD sprites for the coloured smoke marker.

  python3 artsrc/fx/make_smoke_fx.py

Writes mods/rapx/bits/hd/fx/smoke/*.png and mods/rapx/sequences/hd-smoke-fx.yaml:

  pxfx csmoke    12 soft, billowing "cauliflower" smoke puffs, lit from the top left, white (the trait tints them:
                 deep red at the nozzle, pale coral as the cloud thins out — the look of artsrc/fx/reference/red-smoke.jpg)
  pxsmoke can    the smoke canister lying on the ground, 8-frame loop of the nozzle sputtering
  pxsmoke spin   16 frames of the canister tumbling through the air (the thrown grenade, Bullet projectile)
  pxsmoke trail  6 frames of a small red puff left behind by the flying canister (Bullet trail)
  pxsmoke stain  4 variants of the red dye stain the smoke leaves on the ground (flat)
  pxsmoke reticle  aim ring the owner sees where the drifting cloud will draw the fire (white, tinted by the trait)
  icon redsmoke  support power icon, cropped from the reference photo

Canisters are real 3D: points on a cylinder are lit (Lambert + metal highlight) and splatted into a z-buffer at 4x
supersampling, seen from the same tilted camera as the HD units (north-south squashed to ~0.78).
"""
import math
import os

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "smoke")
UI = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "ui")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-smoke-fx.yaml")
REFERENCE = os.path.join(HERE, "reference", "red-smoke.jpg")
SQUASH = 0.78                     # tilted HD camera: ground north-south / east-west
SS = 4                            # canister supersampling

rng = np.random.default_rng(46)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


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


def noise(h, w, scale, octaves=4):
    total = np.zeros((h, w), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        n = gaussian_filter(rng.random((h, w)).astype(np.float32), max(scale / (2 ** o), 0.6))
        n = (n - n.min()) / (n.max() - n.min() + 1e-6)
        total += n * amp
        norm += amp
        amp *= 0.5
    return total / norm


# ------------------------------------------------------------------------------------------------------- smoke puffs

def make_puff(size=160):
    """A cauliflower cluster of soft lobes. Density -> height field -> normals -> light from the top left with a
    little self-shadowing, so the multiplied tint reads as rolling, sunlit coloured smoke."""
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    c = size / 2
    dens = np.zeros((size, size), np.float32)
    lobes = rng.integers(16, 24)
    for i in range(lobes):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.04, 0.27) * size if i else 0
        cx = c + math.cos(a) * r
        cy = c + math.sin(a) * r * 0.85 + (0.04 * size if i else 0)
        rad = rng.uniform(0.08, 0.15) * size * (1.6 if i == 0 else 1)
        dens += np.exp(-(((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * (rad * 0.62) ** 2)))

    # Billows on the surface and a ragged rim
    dens *= 0.72 + 0.5 * noise(size, size, size * 0.06)
    dens = gaussian_filter(dens, 1.2)
    dens /= dens.max()
    edge = smoothstep(0.08, 0.42, dens)
    rim = np.hypot(xs - c, ys - c) / (size / 2)
    edge *= 1 - smoothstep(0.78, 0.98, rim)

    height = gaussian_filter(dens, 1.4) * size * 0.45
    gy, gx = np.gradient(height)
    n = np.dstack([-gx, -gy, np.ones_like(gx) * 2.2])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    light = np.array([-0.55, -0.62, 0.56])
    light /= np.linalg.norm(light)
    lambert = np.clip((n * light).sum(axis=2), 0, 1)

    # Self-shadow: the lower right of the cluster sits in its own shade
    shade = 1 - 0.35 * smoothstep(-0.2, 0.9, ((xs - c) * 0.6 + (ys - c)) / (size / 2)) * smoothstep(0.2, 0.8, dens)
    lum = (0.5 + 0.62 * lambert) * shade
    lum *= 0.9 + 0.12 * noise(size, size, size * 0.02, 2)
    lum = np.clip(lum, 0, 1)

    alpha = edge * (0.75 + 0.25 * smoothstep(0.2, 0.7, dens))
    img = np.dstack([lum, lum * 0.985, lum * 0.97, alpha])
    return img


# ------------------------------------------------------------------------------------------------------- canisters

def rot(axis, a):
    c, s = math.cos(a), math.sin(a)
    x, y, z = axis
    return np.array([
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ])


def canister_points(length=1.0, radius=0.2, n_side=180, n_len=120, n_cap=40):
    """Surface samples of a smoke grenade along +X: (positions, normals, material id, axial coordinate).
    Materials: 0 olive-drab body, 1 red label band, 2 silver top cap, 3 dark nozzle end, 4 glowing vent."""
    pts, nrm, mat, axial = [], [], [], []
    ts = np.linspace(0, 2 * math.pi, n_side, endpoint=False)
    us = np.linspace(-length / 2, length / 2, n_len)
    T, U = np.meshgrid(ts, us)
    T, U = T.ravel(), U.ravel()
    side = np.stack([U, radius * np.cos(T), radius * np.sin(T)], 1)
    sn = np.stack([np.zeros_like(T), np.cos(T), np.sin(T)], 1)
    k = (U + length / 2) / length
    m = np.where(k < 0.16, 2, np.where((k > 0.42) & (k < 0.7), 1, 0))
    pts.append(side), nrm.append(sn), mat.append(m), axial.append(k)

    rs = np.linspace(0, radius, n_cap)
    for end, sign in ((length / 2, 1), (-length / 2, -1)):
        R, TT = np.meshgrid(rs, ts)
        R, TT = R.ravel(), TT.ravel()
        cap = np.stack([np.full_like(R, end), R * np.cos(TT), R * np.sin(TT)], 1)
        cn = np.tile([sign, 0, 0], (len(R), 1)).astype(float)
        if sign > 0:
            cm = np.where(R < radius * 0.42, 4, 3)
        else:
            cm = np.full(len(R), 2)
        pts.append(cap), nrm.append(cn), mat.append(cm), axial.append(np.full(len(R), 1.0 if sign > 0 else 0.0))

    return np.concatenate(pts), np.concatenate(nrm), np.concatenate(mat), np.concatenate(axial)


BASE = {
    0: np.array([0.36, 0.38, 0.27]),     # olive drab
    1: np.array([0.78, 0.1, 0.08]),      # red band: marks it as a smoke grenade
    2: np.array([0.72, 0.73, 0.76]),     # aluminium cap with the spoon
    3: np.array([0.14, 0.12, 0.11]),     # scorched nozzle end
    4: np.array([1.0, 0.55, 0.18]),      # burning composition in the vent
}


def render_canister(w, h, orient, scale, vent_glow=1.0, centre=(0.5, 0.62)):
    """orient: 3x3 matrix applied to the canister (axis along +X). World axes: x right, y towards the viewer
    (south), z up. Screen: sx = x, sy = SQUASH * y - z * 0.63 (the HD camera)."""
    p, n, m, k = canister_points()
    p = p @ orient.T
    n = n @ orient.T
    W, H = w * SS, h * SS
    sx = (p[:, 0] * scale + centre[0] * w) * SS
    sy = ((SQUASH * p[:, 1] - 0.63 * p[:, 2]) * scale + centre[1] * h) * SS
    depth = p[:, 1] * SQUASH + p[:, 2] * 0.63            # bigger = nearer the camera

    view = np.array([0.0, 0.78, 0.63])
    view /= np.linalg.norm(view)
    facing = (n * view).sum(1) > -0.05
    light = np.array([-0.5, -0.35, 0.8])
    light /= np.linalg.norm(light)
    lam = np.clip((n * light).sum(1), 0, 1)
    half = light + view
    half /= np.linalg.norm(half)
    spec = np.clip((n * half).sum(1), 0, 1) ** 28

    col = np.zeros((len(p), 3))
    for mid, base in BASE.items():
        sel = m == mid
        metal = 0.9 if mid == 2 else (0.35 if mid in (0, 1) else 0.1)
        col[sel] = base * (0.28 + 0.85 * lam[sel, None]) + metal * spec[sel, None]
    vent = m == 4
    col[vent] = BASE[4] * (0.6 + 0.8 * vent_glow)

    buf = np.zeros((H, W, 3), np.float32)
    zb = np.full((H, W), -1e9, np.float32)
    ix = np.round(sx).astype(int)
    iy = np.round(sy).astype(int)
    ok = facing & (ix >= 0) & (ix < W - 1) & (iy >= 0) & (iy < H - 1)
    order = np.argsort(depth[ok])
    ix, iy, d, c = ix[ok][order], iy[ok][order], depth[ok][order], col[ok][order]
    # Splat 2x2 so the dense samples close up without holes; later (nearer) samples win
    for dx in (0, 1):
        for dy in (0, 1):
            zb_view = zb[iy + dy, ix + dx]
            win = d >= zb_view
            zb[iy[win] + dy, ix[win] + dx] = d[win]
            buf[iy[win] + dy, ix[win] + dx] = c[win]

    cov = (zb > -1e8).astype(np.float32)
    rgb = buf.reshape(h, SS, w, SS, 3).mean(axis=(1, 3))
    a = cov.reshape(h, SS, w, SS).mean(axis=(1, 3))
    rgb = np.where(a[..., None] > 0, rgb / np.maximum(a[..., None], 1e-6), 0)
    return np.dstack([np.clip(rgb, 0, 1), a]), sx.mean() / SS, sy.mean() / SS


def drop_shadow(img, dx=2, dy=3, blur=1.6, strength=0.55):
    a = img[..., 3]
    sh = gaussian_filter(np.roll(np.roll(a, dy, 0), dx, 1), blur) * strength
    out = img.copy()
    out_a = a + sh * (1 - a)
    out[..., :3] = np.where(out_a[..., None] > 0, img[..., :3] * a[..., None] / np.maximum(out_a[..., None], 1e-6), 0)
    out[..., 3] = out_a
    return out


def make_can_frames(frames=8, w=72, h=48):
    """Lying on its side, nozzle towards the lower right like the reference photo; the vent sputters."""
    orient = rot((0, 0, 1), math.radians(28)) @ rot((1, 0, 0), math.radians(20))
    out = []
    for i in range(frames):
        glow = 0.65 + 0.35 * math.sin(i / frames * 2 * math.pi) * math.sin(i / frames * 6 * math.pi + 1)
        img, _, _ = render_canister(w, h, orient, 30, vent_glow=glow, centre=(0.46, 0.55))
        out.append(drop_shadow(img))
    return out


def make_spin_frames(frames=16, size=56):
    out = []
    for i in range(frames):
        a = i / frames * 2 * math.pi
        orient = rot((0, 1, 0), a) @ rot((0, 0, 1), math.radians(35)) @ rot((1, 0, 0), a * 0.5)
        img, _, _ = render_canister(size, size, orient, 26, vent_glow=1.0, centre=(0.5, 0.5))
        out.append(img)
    return out


# ------------------------------------------------------------------------------------------------------- trail, stain

def make_trail_frames(frames=6, size=48):
    """A small red puff that swells and thins (Bullet trails cannot be tinted, so the colour is baked)."""
    base = make_puff(size)
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    out = []
    for i in range(frames):
        t = i / (frames - 1)
        s = 0.55 + 0.6 * t
        c = (size - 1) / 2
        coords = [c + (ys - c) / s, c + (xs - c) / s]
        img = np.dstack([map_coordinates(base[..., ch], coords, order=1, mode="constant") for ch in range(4)])
        lum = img[..., 0]
        rgb = np.dstack([0.95 * lum + 0.08, 0.32 * lum + 0.12 * t, 0.27 * lum + 0.12 * t])
        out.append(np.dstack([np.clip(rgb, 0, 1), img[..., 3] * (1 - t) ** 1.2 * 0.85]))
    return out


def make_stain(w=224, h=160):
    """Powdery dye soaked into the ground: a dense blotch in the middle, splashes and fine grains around it,
    the deep red of the photo's tarmac stain. Flat: drawn with alpha on the terrain."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    r = np.hypot((xs - cx) / (w / 2), (ys - cy) / (h / 2))
    n = noise(h, w, 18)
    body = 1 - smoothstep(0.25, 0.75, r + (n - 0.5) * 0.55)

    splash = np.zeros((h, w), np.float32)
    for _ in range(rng.integers(5, 9)):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.45, 0.8)
        sx, sy = cx + math.cos(a) * d * w / 2, cy + math.sin(a) * d * h / 2
        rad = rng.uniform(5, 13)
        splash = np.maximum(splash, 1 - smoothstep(rad * 0.5, rad, np.hypot(xs - sx, ys - sy * 1.0)))
    grain = (rng.random((h, w)) > 0.82).astype(np.float32) * (1 - smoothstep(0.4, 1.0, r))
    alpha = np.clip(body * (0.55 + 0.35 * noise(h, w, 6)) + splash * 0.6 + grain * 0.35, 0, 1)
    alpha = gaussian_filter(alpha, 0.7) * 0.9
    v = noise(h, w, 4)
    rgb = np.dstack([0.55 + 0.25 * v, 0.07 + 0.06 * v, 0.07 + 0.05 * v])
    return np.dstack([rgb, alpha])


def make_reticle(w=160, h=124):
    """Four bracket arcs and a dotted inner ring, foreshortened onto the ground (white; tinted and pulsed in code)."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    u = (xs - cx) / (w / 2 - 3)
    v = (ys - cy) / (h / 2 - 3)
    r = np.hypot(u, v)
    ang = np.arctan2(v, u)
    arcs = (1 - smoothstep(0.035, 0.07, np.abs(r - 0.92))) * (np.cos(ang * 4) < -0.25)
    dots = (1 - smoothstep(0.03, 0.055, np.abs(r - 0.55))) * (np.cos(ang * 24) > 0.2)
    centre = 1 - smoothstep(0.05, 0.09, r)
    a = np.clip(arcs + dots * 0.7 + centre, 0, 1)
    glow = gaussian_filter(a, 2.5) * 0.6
    a = np.clip(a + glow, 0, 1)
    return np.dstack([np.ones_like(a), np.ones_like(a), np.ones_like(a), a])


def make_icon():
    """The support power icon: the user's red smoke photo, cropped to the 4:3 icon around the canister and plume."""
    im = Image.open(REFERENCE).convert("RGB")
    w, h = im.size
    th = int(min(h, w * 3 / 4))
    tw = int(th * 4 / 3)
    left = max(0, min(w - tw, int(w * 0.62 - tw / 2)))
    top = max(0, min(h - th, int(h * 0.55 - th / 2)))
    im = im.crop((left, top, left + tw, top + th)).resize((256, 192), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255
    # A little punch and a vignette, like the other HD icons
    a = np.clip((a - 0.5) * 1.12 + 0.52, 0, 1)
    ys, xs = np.mgrid[0:192, 0:256].astype(np.float32)
    vig = 1 - 0.35 * smoothstep(0.55, 1.15, np.hypot((xs - 128) / 128, (ys - 96) / 96))
    a *= vig[..., None]
    Image.fromarray((a * 255).round().astype(np.uint8)).save(os.path.join(UI, "icon-redsmoke.png"), optimize=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    save_sheet(os.path.join(OUT, "csmoke.png"), [make_puff() for _ in range(12)])
    save_sheet(os.path.join(OUT, "can.png"), make_can_frames())
    save_sheet(os.path.join(OUT, "spin.png"), make_spin_frames())
    save_sheet(os.path.join(OUT, "trail.png"), make_trail_frames())
    save_sheet(os.path.join(OUT, "stain.png"), [make_stain() for _ in range(4)])
    save_sheet(os.path.join(OUT, "reticle.png"), [make_reticle()])
    if os.path.exists(REFERENCE):
        make_icon()

    with open(SEQUENCES, "w") as f:
        f.write("""# Red Smoke "Danger Close" (IDEA-46): coloured smoke puffs, the canister, its flight, dye stain and aim ring.
# GENERATED by artsrc/fx/make_smoke_fx.py - edit that script, not this file.

pxfx:
	csmoke:
		Filename: ra|bits/hd/fx/smoke/csmoke.png
		Length: 12
		Scale: 0.3333

pxsmoke:
	Defaults:
		Scale: 0.3333
	can:
		Filename: ra|bits/hd/fx/smoke/can.png
		Length: 8
		Tick: 60
	spin:
		Filename: ra|bits/hd/fx/smoke/spin.png
		Length: 16
		Tick: 40
	trail:
		Filename: ra|bits/hd/fx/smoke/trail.png
		Length: 6
		Tick: 80
		ZOffset: 1023
	stain:
		Filename: ra|bits/hd/fx/smoke/stain.png
		Length: 4
	reticle:
		Filename: ra|bits/hd/fx/smoke/reticle.png
		Length: 1
		BlendMode: Additive

icon:
	redsmoke:
		Filename: ra|bits/hd/ui/icon-redsmoke.png
		Scale: 0.25
""")
    print("wrote", OUT, "and", SEQUENCES)


if __name__ == "__main__":
    main()
