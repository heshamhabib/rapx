#!/usr/bin/env python3
"""
Draws the HD rally point marker used by PxRallyPoint (image `pxrally`):

  flag.png  - animated waving banner on a steel pole with gold finial, hem, fringe and star emblem,
              plus its soft ground shadow (FRAMES frames, one wave cycle, loops seamlessly).
  base.png  - the ground emblem under the pole: bevelled steel bezel, gold rim, glowing inner ring.

The cloth and the inner ring are pure green so PlayerColorShift recolours them to the owner's colour;
gold and steel fall outside the shifted hue range and keep their colour.
Sprites are drawn at 4x density (Scale 0.25 in the sequences).

  python3 artsrc/rally/make_rally.py [--preview]
"""
import math
import os
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "rally")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-rally.yaml")

DENSITY = 4
SS = 3  # supersampling

FRAMES = 24
FRAME_TICK = 45

# Flag frame layout (sprite px at DENSITY).
FW, FH = 232, 262
POLE_X = 52
BASE_Y = 214            # pole foot = the rally point; PxRallyPoint FlagAnchor must match
POLE_TOP = 58
POLE_R = 3.4
CLOTH_TOP = 64
CLOTH_W = 112
CLOTH_H = 64

# Base emblem.
BW, BH = 148, 96
BASE_RX = 62            # outer radius in px; PxRallyPoint RingRadius = BASE_RX / DENSITY
BASE_RATIO = 0.58       # ground ellipse squash; PxRallyPoint RingRatio must match

GREEN = np.array([0.10, 0.92, 0.12])
GREEN_DARK = np.array([0.03, 0.42, 0.05])
GOLD = np.array([1.00, 0.78, 0.30])
GOLD_DARK = np.array([0.55, 0.34, 0.08])
STEEL = np.array([0.62, 0.66, 0.72])

LIGHT = np.array([-0.55, -0.60, 0.58])
LIGHT /= np.linalg.norm(LIGHT)

rng = np.random.default_rng(11)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def star_mask(px, py, cx, cy, r_out, r_in, points=5):
    """Antialiased-ish filled star (pixel coords, y down)."""
    dx, dy = px - cx, py - cy
    ang = np.arctan2(dx, -dy)
    r = np.hypot(dx, dy)
    seg = 2 * math.pi / points
    a = np.mod(ang + seg / 2, seg) - seg / 2
    # Distance of the star edge at angle a (straight edges between tips and notches).
    t = np.abs(a) / (seg / 2)
    tip = np.array([0.0, r_out])
    notch = np.array([r_in * math.sin(seg / 2), r_in * math.cos(seg / 2)])
    # Edge from tip (angle 0) to notch (angle seg/2): intersect ray with segment.
    ex, ey = notch - tip
    sa, ca = np.sin(np.abs(a)), np.cos(np.abs(a))
    denom = sa * ey - ca * ex
    s = (tip[1] * ex - tip[0] * ey) / np.where(np.abs(denom) < 1e-6, 1e-6, denom)
    del t
    return np.clip(np.abs(s) - r + 0.5, 0, 1)


def cloth_texture(u, v):
    """Colour, gold mask and alpha for cloth parameters u (0 at pole .. 1 fly end, fringe beyond) and v (0 top .. 1 bottom)."""
    px, py = u * CLOTH_W, v * CLOTH_H
    col = np.broadcast_to(GREEN, u.shape + (3,)).copy()

    # Subtle vertical gradient and woven texture.
    col *= (1.0 - 0.18 * v)[..., None]
    weave = 0.5 + 0.5 * np.sin(px * 2.2) * np.sin(py * 2.2)
    col *= (0.95 + 0.06 * weave)[..., None]

    gold = np.zeros(u.shape)
    edge = np.minimum.reduce([py, CLOTH_H - py, CLOTH_W - px])
    gold = np.maximum(gold, (edge < 3.2).astype(float))                     # outer hem
    gold = np.maximum(gold, ((edge > 6.0) & (edge < 7.4)).astype(float))    # pinstripe
    dark_band = (edge >= 3.2) & (edge <= 6.0)
    col[dark_band] = col[dark_band] * 0.55

    # Pole sleeve: darker doubled cloth along the pole.
    sleeve = px < 7
    col[sleeve] *= 0.72
    gold = np.where(px < 1.6, 1.0, gold)

    # Emblem: gold ring with a star.
    cx, cy = CLOTH_W * 0.46, CLOTH_H * 0.5
    r = np.hypot(px - cx, py - cy)
    ring = np.clip(1.0 - np.abs(r - 20.5) / 1.6, 0, 1)
    disc = r < 19
    col[disc] = col[disc] * 0.78
    star = star_mask(px, py, cx, cy, 16.5, 6.8)
    gold = np.maximum(gold, np.maximum(ring, star))

    alpha = np.ones(u.shape)
    fringe = u > 1.0
    strands = (np.mod(py, 3.0) < 1.9).astype(float)
    flen = (u - 1.0) * CLOTH_W
    alpha = np.where(fringe, strands * (flen < 7.0 + 1.5 * np.sin(py * 0.9)), alpha)
    gold = np.where(fringe, 1.0, gold)
    return col, gold, alpha


def render_flag(t):
    W, H = FW * SS, FH * SS
    rgb = np.zeros((H, W, 3))
    alpha = np.zeros((H, W))
    zbuf = np.full((H, W), -1e9)
    shadow = np.zeros((H, W))

    nu, nv = CLOTH_W * SS * 2, CLOTH_H * SS * 2
    uu, vv = np.meshgrid(np.linspace(0, 1.07, int(nu * 1.07)), np.linspace(0, 1, nv))

    ph = 2 * math.pi * (1.35 * uu - t) + 0.9 * vv * uu
    amp = (2.0 + 13.0 * uu) * np.power(uu, 0.6)
    z = amp * np.sin(ph) + 2.2 * uu * np.sin(2 * math.pi * (2.7 * uu - 2 * t) + 1.7 * vv)
    # The fly end loses length as the cloth folds.
    x = POLE_X + POLE_R + uu * CLOTH_W * (0.93 + 0.04 * np.cos(2 * math.pi * t)) - 3.0 * uu * (1 - np.cos(ph)) * 0.5
    y = CLOTH_TOP + vv * CLOTH_H + 0.32 * z + 7.0 * uu ** 2 * (0.6 + vv * 0.4)

    du = uu[0, 1] - uu[0, 0]
    dv = vv[1, 0] - vv[0, 0]
    dzdu = np.gradient(z, du, axis=1) / CLOTH_W
    dzdv = np.gradient(z, dv, axis=0) / CLOTH_H
    n = np.stack([-dzdu, -dzdv, np.ones_like(z)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lam = np.clip((n * LIGHT).sum(-1), 0, 1)
    view = np.array([0, 0, 1.0])
    half = (LIGHT + view) / np.linalg.norm(LIGHT + view)
    spec = np.clip((n * half).sum(-1), 0, 1)

    col, gold, a = cloth_texture(uu, vv)
    shade = 0.32 + 0.88 * lam
    # Ambient occlusion in folds facing away.
    shade *= 0.85 + 0.15 * np.clip(1 - np.abs(dzdu) * 0.6, 0, 1)
    gcol = GOLD_DARK + (GOLD - GOLD_DARK) * np.clip(lam, 0, 1)[..., None]
    base = col * (1 - gold[..., None]) + gcol * gold[..., None]
    sheen = (0.18 * spec ** 14 * (1 - gold) + 0.75 * spec ** 30 * gold)[..., None]
    c = base * shade[..., None] + sheen

    ix = np.clip((x * SS).astype(int), 0, W - 1)
    iy = np.clip((y * SS).astype(int), 0, H - 1)
    order = np.argsort(z, axis=None)
    fx, fy = ix.ravel()[order], iy.ravel()[order]
    fa = a.ravel()[order]
    keep = fa > 0.5
    rgb[fy[keep], fx[keep]] = c.reshape(-1, 3)[order][keep]
    alpha[fy[keep], fx[keep]] = 1
    zbuf[fy[keep], fx[keep]] = z.ravel()[order][keep]

    # Ground shadow of the cloth (light from upper left -> shadow falls lower right).
    hgt = BASE_Y - y
    sx = np.clip(((x + 0.30 * hgt) * SS).astype(int), 0, W - 1)
    sy = np.clip(((BASE_Y + 0.11 * hgt) * SS).astype(int), 0, H - 1)
    shadow[sy[a > 0.5], sx[a > 0.5]] = 1

    # Pole: steel cylinder with gold collars.
    py_, px_ = np.mgrid[0:H, 0:W] / SS
    tpole = (px_ - POLE_X) / POLE_R
    on_pole = (np.abs(tpole) <= 1) & (py_ >= POLE_TOP) & (py_ <= BASE_Y)
    nx = tpole
    nz = np.sqrt(np.clip(1 - nx ** 2, 0, 1))
    plam = np.clip(nx * LIGHT[0] + nz * LIGHT[2], 0, 1)
    pspec = np.clip(nx * half[0] + nz * half[2], 0, 1) ** 40
    collar = np.zeros_like(py_, bool)
    for cy0, ch in ((POLE_TOP, 4), (CLOTH_TOP + 2, 3), (CLOTH_TOP + CLOTH_H - 3, 3), (BASE_Y - 14, 5)):
        collar |= (py_ >= cy0) & (py_ < cy0 + ch)
    pole_col = np.where(collar[..., None], GOLD_DARK + (GOLD - GOLD_DARK) * plam[..., None],
                        STEEL * (0.25 + 0.85 * plam)[..., None])
    pole_col = pole_col + (pspec * 0.9)[..., None]
    pole_z = np.where(collar, 9, 6)
    widen = collar & (np.abs((px_ - POLE_X) / (POLE_R + 1.2)) <= 1)
    on_pole = on_pole | (widen & (py_ >= POLE_TOP) & (py_ <= BASE_Y))
    front = on_pole & (pole_z > zbuf)
    rgb[front] = pole_col[front]
    alpha[front] = 1

    # Finial: gold sphere + spear tip.
    fcy = POLE_TOP - 6
    r = np.hypot(px_ - POLE_X, py_ - fcy)
    sph = r <= 6.0
    snx, sny = (px_ - POLE_X) / 6.0, (py_ - fcy) / 6.0
    snz = np.sqrt(np.clip(1 - snx ** 2 - sny ** 2, 0, 1))
    slam = np.clip(snx * LIGHT[0] + sny * LIGHT[1] + snz * LIGHT[2], 0, 1)
    sspec = np.clip(snx * half[0] + sny * half[1] + snz * half[2], 0, 1) ** 30
    scol = GOLD_DARK + (GOLD - GOLD_DARK) * slam[..., None] + sspec[..., None]
    rgb[sph] = scol[sph]
    alpha[sph] = 1
    tip_top = fcy - 22
    tip_h = (fcy - 4) - tip_top
    tt = (py_ - tip_top) / tip_h
    half_w = 3.6 * np.sin(np.clip(tt, 0, 1) * math.pi * 0.85)
    tip = (tt >= 0) & (tt <= 1) & (np.abs(px_ - POLE_X) <= half_w) & ~sph
    side = np.where(px_ < POLE_X, 1.0, 0.55)
    tcol = GOLD_DARK + (GOLD - GOLD_DARK) * side[..., None]
    tcol = tcol + (0.6 * np.exp(-((px_ - POLE_X + 0.8) ** 2) / 0.8))[..., None]
    rgb[tip] = tcol[tip]
    alpha[tip] = 1

    # Pole shadow.
    for yy in np.arange(tip_top, BASE_Y, 1.0 / SS):
        hgt = BASE_Y - yy
        sx0 = int((POLE_X + 0.30 * hgt) * SS)
        sy0 = int((BASE_Y + 0.11 * hgt) * SS)
        if 0 <= sy0 < H:
            shadow[sy0, max(0, sx0 - int(POLE_R * SS)):min(W, sx0 + int(POLE_R * SS))] = 1

    shadow = gaussian_filter(shadow, 1.6 * SS) * 0.42
    shadow = np.clip(shadow * 2.2, 0, 0.42)

    # Composite shadow under the flag.
    out_a = alpha + shadow * (1 - alpha)
    out_rgb = rgb * alpha[..., None] / np.maximum(out_a, 1e-6)[..., None]

    img = np.dstack([np.clip(out_rgb, 0, 1), out_a])
    img = img.reshape(FH, SS, FW, SS, 4)
    # Downsample with premultiplied alpha.
    prem = img[..., :3] * img[..., 3:4]
    prem = prem.mean(axis=(1, 3))
    a_ = img[..., 3].mean(axis=(1, 3))
    rgb_ = prem / np.maximum(a_, 1e-6)[..., None]
    return np.dstack([rgb_, a_])


def render_base():
    W, H = BW * SS, BH * SS
    py_, px_ = np.mgrid[0:H, 0:W] / SS
    cx, cy = BW / 2, BH / 2
    # Undo the ground squash: work in a top-down disc.
    dx = (px_ - cx) / BASE_RX
    dy = (py_ - cy) / (BASE_RX * BASE_RATIO)
    r = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)

    rgb = np.zeros((H, W, 3))
    a = np.zeros((H, W))

    # Height profile -> normals for bevels.
    def bump(r0, r1, h):
        return h * smoothstep(r0, r0 + 0.04, r) * (1 - smoothstep(r1 - 0.04, r1, r))

    height = bump(0.80, 1.00, 1.0) + bump(0.0, 0.52, 0.35)
    gy, gx = np.gradient(height)
    n = np.dstack([-gx * 40, -gy * 40, np.ones_like(r)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lam = np.clip((n * LIGHT).sum(-1), 0, 1)

    # Outer steel bezel with gold rim.
    bezel = (r > 0.80) & (r <= 1.0)
    rgb[bezel] = (STEEL * 0.55 * (0.4 + 1.0 * lam)[..., None])[bezel]
    rim = (r > 0.955) & (r <= 1.0)
    rgb[rim] = (GOLD_DARK + (GOLD - GOLD_DARK) * lam[..., None])[rim]
    inner_rim = (r > 0.80) & (r <= 0.83)
    rgb[inner_rim] = (GOLD_DARK + (GOLD - GOLD_DARK) * (0.4 + 0.6 * lam)[..., None])[inner_rim]
    # Rivets around the bezel.
    for k in range(12):
        t = k * math.pi / 6 + math.pi / 12
        rx, ry = cx + math.cos(t) * BASE_RX * 0.89, cy + math.sin(t) * BASE_RX * 0.89 * BASE_RATIO
        d = np.hypot(px_ - rx, (py_ - ry) / BASE_RATIO)
        riv = d < 2.4
        rl = np.clip(1 - np.hypot((px_ - rx + 0.8), (py_ - ry + 0.5)) / 2.4, 0, 1)
        rgb[riv] = (GOLD_DARK + (GOLD - GOLD_DARK) * rl[..., None])[riv]

    # Glowing team-colour ring with notches.
    glow_ring = (r > 0.52) & (r <= 0.80)
    notch = np.abs(np.mod(ang + math.pi / 8, math.pi / 4) - math.pi / 8) < 0.07
    band = np.clip(1 - np.abs(r - 0.66) / 0.10, 0, 1)
    gcol = GREEN_DARK * 0.6 + GREEN * (0.25 + 0.95 * band ** 1.5)[..., None]
    gcol = np.where(notch[..., None], GREEN_DARK * 0.35, gcol)
    rgb[glow_ring] = gcol[glow_ring]

    # Centre plate: dark steel with a faint radial engraving.
    centre = r <= 0.52
    eng = 0.5 + 0.5 * np.cos(ang * 16)
    plate = STEEL * (0.22 + 0.5 * lam)[..., None] * (0.9 + 0.1 * eng)[..., None]
    plate = plate + GREEN_DARK * 0.25 * (1 - r / 0.52)[..., None]
    rgb[centre] = plate[centre]
    cring = np.abs(r - 0.50) < 0.02
    rgb[cring] = (GOLD_DARK + (GOLD - GOLD_DARK) * lam[..., None])[cring]

    a[r <= 1.0] = 1
    # Soft contact shadow just outside the rim.
    halo = np.clip(1 - (r - 1.0) / 0.14, 0, 1) * (r > 1.0) * 0.45
    out_a = a + halo * (1 - a)
    out_rgb = rgb * a[..., None] / np.maximum(out_a, 1e-6)[..., None]

    img = np.dstack([np.clip(out_rgb, 0, 1), out_a]).reshape(BH, SS, BW, SS, 4)
    prem = (img[..., :3] * img[..., 3:4]).mean(axis=(1, 3))
    a_ = img[..., 3].mean(axis=(1, 3))
    return np.dstack([prem / np.maximum(a_, 1e-6)[..., None], a_])


def save(name, frames):
    h, w, _ = frames[0].shape
    sheet = np.concatenate(frames, axis=1)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    path = os.path.join(OUT, f"{name}.png")
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(path, pnginfo=info, optimize=True)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    flags = [render_flag(i / FRAMES) for i in range(FRAMES)]
    save("flag", flags)
    base = render_base()
    save("base", [base])

    with open(SEQUENCES, "w") as f:
        f.write("# HD rally point marker (RedAlert Project X), drawn by PxRallyPoint.\n")
        f.write("# GENERATED by artsrc/rally/make_rally.py - edit that script, not this file.\n\n")
        f.write("pxrally:\n")
        f.write("\tDefaults:\n")
        f.write(f"\t\tScale: {1 / DENSITY:g}\n")
        f.write("\tflag:\n")
        f.write("\t\tFilename: ra|bits/hd/rally/flag.png\n")
        f.write(f"\t\tLength: {FRAMES}\n")
        f.write(f"\t\tTick: {FRAME_TICK}\n")
        f.write("\tbase:\n")
        f.write("\t\tFilename: ra|bits/hd/rally/base.png\n")
        f.write("\t\tLength: 1\n")

    print(f"FlagAnchor: {POLE_X},{BASE_Y}  RingRadius: {BASE_RX / DENSITY:g}  RingRatio: {BASE_RATIO}")

    if "--preview" in sys.argv:
        # Team-colour (red) preview on snow, flag over base, 4 frames.
        bg = np.ones((FH + 60, FW * 4, 3)) * np.array([0.88, 0.86, 0.90])
        for i, fi in enumerate((0, 6, 12, 18)):
            ox = i * FW
            b = base.copy()
            by, bx = BASE_Y - BH // 2 + 20, POLE_X - BW // 2 + ox
            for img, (oy, ox2) in ((b, (by, bx)), (flags[fi], (20, ox))):
                h, w, _ = img.shape
                y0, x0 = max(0, oy), max(0, ox2)
                sub = img[y0 - oy:min(h, bg.shape[0] - oy), x0 - ox2:min(w, bg.shape[1] - ox2)]
                c = sub[..., :3].copy()
                hsv_green = (c[..., 1] > c[..., 0] * 1.3) & (c[..., 1] > c[..., 2] * 1.3)
                c[hsv_green] = c[hsv_green][:, [1, 0, 2]] * np.array([1.0, 0.25, 0.25])
                al = sub[..., 3:4]
                region = bg[y0:y0 + sub.shape[0], x0:x0 + sub.shape[1]]
                region[:] = region * (1 - al) + c * al
        Image.fromarray((bg * 255).astype(np.uint8)).save(os.path.join(HERE, "preview.png"))


if __name__ == "__main__":
    main()
