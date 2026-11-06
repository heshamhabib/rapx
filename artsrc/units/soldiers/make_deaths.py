#!/usr/bin/env python3
"""
HD electrocuted and crushed deaths for every soldier, the dog's jump, and the paratrooper corpse
(RedAlert Project X, IDEA-30 phase 2). Built from each unit's own HD frames, so they match its look exactly.

  python3 artsrc/units/soldiers/make_deaths.py [--preview]

- die6 (ElectricityDeath): the soldier seizes up where he stands, jittering inside crawling electric arcs and
  white-blue flashes, then falls (his own HD death) charring black while the last arcs die out and smoke rises.
- die-crushed: his body lying on the ground (last frame of his HD fall) is flattened into it with a dust puff and a
  dark smear, then lies there and slowly fades.
- 3D soldiers: writes bits/hd/soldiers/<id>/die6.png + crushed.png (write_sequences.py adds them).
- Dog (AI sheets): bits/hd/infantry/dog/die6.png, crushed.png, jump.png (its run frames lifted along a leap arc).
- bits/hd/fx/corpse.png: the corpse of a paratrooper landing where he can't stand (explosion corpse).
- Writes mods/rapx/sequences/hd-infantry-deaths.yaml for the dog and the corpse.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, PngImagePlugin
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SOLDIERS = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "soldiers")
DOG = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "infantry", "dog")
FX = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-infantry-deaths.yaml")
PREVIEW = os.path.join(HERE, "preview")
ARC = np.array([0.55, 0.85, 1.0], np.float32)
CHAR = np.array([0.07, 0.06, 0.055], np.float32)


def frames(path):
    im = Image.open(path)
    fw, fh = (int(v) for v in im.info["FrameSize"].split(","))
    n = int(im.info["FrameAmount"])
    a = np.asarray(im.convert("RGBA"), dtype=np.float32) / 255
    cols = a.shape[1] // fw
    return [a[(i // cols) * fh:(i // cols + 1) * fh, (i % cols) * fw:(i % cols + 1) * fw].copy() for i in range(n)]


def save(path, fr, facings=1):
    fh, fw, _ = fr[0].shape
    cols = min(len(fr), max(1, 4096 // fw))
    rows = (len(fr) + cols - 1) // cols
    sheet = np.zeros((fh * rows, fw * cols, 4), np.float32)
    for i, f in enumerate(fr):
        r, c = divmod(i, cols)
        sheet[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw] = f
    sheet[..., :3] = np.where(sheet[..., 3:] > 0, sheet[..., :3], 0)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{fw},{fh}")
    info.add_text("FrameAmount", str(len(fr)))
    info.add_text("Facings", str(facings))
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(path, pnginfo=info, optimize=True)
    print("  wrote", os.path.relpath(path, ROOT), len(fr), "frames")


def shift(f, dx, dy):
    out = np.zeros_like(f)
    h, w, _ = f.shape
    ys, ye = max(0, dy), min(h, h + dy)
    xs, xe = max(0, dx), min(w, w + dx)
    out[ys:ye, xs:xe] = f[ys - dy:ye - dy, xs - dx:xe - dx]
    return out


def add_light(f, rgb, a):
    """Additive light on top of a straight-alpha frame (arcs, glows)."""
    out = f.copy()
    na = np.clip(out[..., 3] + a * (1 - out[..., 3]), 0, 1)
    out[..., :3] = (out[..., :3] * out[..., 3:4] + rgb * a[..., None]) / np.maximum(na, 1e-5)[..., None]
    out[..., 3] = na
    out[..., :3] = np.clip(out[..., :3], 0, 1)
    return out


def arcs(f, rng, count, strength, scale):
    """Jagged electric arcs crawling between random points of the body silhouette."""
    h, w, _ = f.shape
    body = body_mask(f)
    ys, xs = np.nonzero(body)
    if len(xs) < 2:
        return f
    size = max(ys.max() - ys.min(), xs.max() - xs.min())
    count = max(2, int(count * min(1.0, size / 60)))
    core = Image.new("L", (w * 2, h * 2), 0)
    d = ImageDraw.Draw(core)
    for _ in range(count):
        # a short crackling arc hugging the body: a random walk from one body point towards a near one
        i = rng.integers(0, len(xs))
        p = np.array([xs[i], ys[i]], float)
        heading = rng.uniform(0, 2 * np.pi)
        pts = [p]
        for _ in range(rng.integers(5, 10)):
            heading += rng.normal(0, 0.9)
            p = p + np.array([np.cos(heading), np.sin(heading)]) * size * rng.uniform(0.03, 0.07)
            pts.append(p)
            if rng.random() < 0.25:                      # a little fork
                q = p + np.array([np.cos(heading + 1.2), np.sin(heading + 1.2)]) * size * 0.06
                d.line([tuple(p * 2), tuple(q * 2)], fill=170, width=1)
        d.line([tuple(q * 2) for q in pts], fill=255, width=2)
    core = core.resize((w, h), Image.LANCZOS)
    c = np.asarray(core, np.float32) / 255
    glow = gaussian_filter(c, 2.2 * scale) * 2.2
    out = add_light(f, ARC, np.clip(glow * strength, 0, 1))
    return add_light(out, np.array([0.92, 0.97, 1.0], np.float32), np.clip(c * strength * 1.3, 0, 1))


def body_mask(f):
    """The soldier himself, not his soft ground shadow."""
    lum = f[..., :3].max(-1)
    return (f[..., 3] > 0.92) & (lum > 0.06)


def tint(f, rgb, k):
    out = f.copy()
    k = np.asarray(k, np.float32)
    if k.ndim == 2:
        k = k[..., None]
    out[..., :3] = out[..., :3] * (1 - k) + rgb * k
    return out


def smoke(f, rng, t, scale, amount):
    """A few soft grey wisps rising from the body."""
    h, w, _ = f.shape
    ys, xs = np.nonzero(body_mask(f))
    if not len(xs) or amount <= 0:
        return f
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.zeros((h, w), np.float32)
    for k in range(3):
        cx = xs.mean() + (k - 1) * 3 * scale + rng.normal(0, scale)
        cy = ys.min() - (1 + 0.8 * t + 2 * k) * scale
        r = (1.6 + 0.35 * t + 0.6 * k) * scale
        a += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)) * 0.22
    a = np.clip(a * amount, 0, 0.45)
    smoke_im = np.dstack([np.broadcast_to([0.42, 0.41, 0.4], (h, w, 3)), a])
    ta, ba = smoke_im[..., 3:4], f[..., 3:4]
    na = ta + ba * (1 - ta)
    rgb = (smoke_im[..., :3] * ta + f[..., :3] * ba * (1 - ta)) / np.maximum(na, 1e-5)
    return np.dstack([rgb, na[..., 0]]).astype(np.float32)


def electrocuted(stand, fall, seed, scale):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(7):                                   # seized up, jittering in the current
        f = shift(stand, int(rng.integers(-2, 3) * scale / 2), int(rng.integers(-1, 2) * scale / 2))
        flash = 0.55 if i % 2 == 0 else 0.15
        body = body_mask(f)
        f = tint(f, np.array([0.75, 0.92, 1.0]), flash * body)
        f = tint(f, CHAR, min(0.45, i * 0.06) * body)
        out.append(arcs(f, rng, 10 + 2 * (i % 3), 1.0, scale))
    for i, f in enumerate(fall):                          # falls, charred and smoking
        k = min(1.0, 0.45 + i * 0.09)
        f = tint(f, CHAR, k * 0.72 * body_mask(f))
        if i < 4:
            f = arcs(f, rng, 6 - i, 1 - i * 0.22, scale)
        out.append(smoke(f, rng, i, scale, min(1.0, i / 3)))
    for i in range(3):                                    # lies smoking
        out.append(smoke(out[-1 - i if i else -1], rng, len(fall) + i, scale, 1 - i * 0.3))
    return out


def crushed(lying, seed, scale, n=6):
    """Flatten the lying body into the ground, then let it fade."""
    rng = np.random.default_rng(seed)
    h, w, _ = lying.shape
    ys, xs = np.nonzero(lying[..., 3] > 0.3)
    base = ys.max() if len(ys) else h // 2
    out = []
    for i in range(n):
        k = 0.45 if i else 0.7
        rows = np.clip(base - (base - np.arange(h)) / k, 0, h - 1)
        sq = np.stack([np.stack([np.interp(rows, np.arange(h), lying[:, c, ch]) for c in range(w)], 1)
                       for ch in range(4)], -1).astype(np.float32)
        sq[..., :3] *= 0.55
        sq[..., :3] = sq[..., :3] * 0.7 + sq[..., :3].mean(-1, keepdims=True) * 0.3
        # dark smear under the body
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx = xs.mean() if len(xs) else w / 2
        sm = np.exp(-(((xx - cx) / (14 * scale)) ** 2 + ((yy - base + 2 * scale) / (4 * scale)) ** 2)) * 0.55
        smear = np.dstack([np.broadcast_to([0.2, 0.06, 0.04], (h, w, 3)), sm])
        ta, ba = sq[..., 3:4], smear[..., 3:4]
        na = ta + ba * (1 - ta)
        f = np.dstack([(sq[..., :3] * ta + smear[..., :3] * ba * (1 - ta)) / np.maximum(na, 1e-5), na[..., 0]])
        if i == 0:                                        # dust puff as the tracks go over
            dust = np.exp(-(((xx - cx) / (16 * scale)) ** 2 + ((yy - base + 5 * scale) / (7 * scale)) ** 2)) * 0.45
            f = np.dstack([(f[..., :3] * f[..., 3:4] * (1 - dust[..., None]) + np.array([0.55, 0.47, 0.36]) * dust[..., None])
                           / np.maximum(f[..., 3:4] + dust[..., None] * (1 - f[..., 3:4]), 1e-5),
                           f[..., 3] + dust * (1 - f[..., 3])])
        f[..., 3] *= 1.0 if i < 2 else 1 - (i - 1) / (n - 1) * 0.75
        out.append(f.astype(np.float32))
    return out


def best_facing(stand_frames, target):
    """The stand facing whose silhouette best matches the first frame of the death (same view)."""
    t = target[..., 3] > 0.5
    scores = [((f[..., 3] > 0.5) & t).sum() / max(1, ((f[..., 3] > 0.5) | t).sum()) for f in stand_frames]
    return int(np.argmax(scores))


def seq(name, path, length, facings=1, stride=None, tick=None, scale=0.2, extra=()):
    lines = [f"\t{name}:", f"\t\tFilename: {path}", "\t\tTilesetFilenames:"]
    lines += [f"\t\t\t{t}: {path}" for t in ("TEMPERAT", "SNOW", "DESERT", "INTERIOR")]
    lines += ["\t\tStart: 0", f"\t\tLength: {length}", f"\t\tFacings: {facings}"]
    if stride:
        lines.append(f"\t\tStride: {stride}")
    if facings > 1:
        lines.append("\t\tUseClassicFacings: False")
    if tick:
        lines.append(f"\t\tTick: {tick}")
    lines += ["\t\tOffset: 0,0", f"\t\tScale: {scale:.4f}"]
    return lines + [f"\t\t{e}" for e in extra]


def main():
    show = "--preview" in sys.argv
    previews = []
    for uid in sorted(os.listdir(SOLDIERS)):
        d = os.path.join(SOLDIERS, uid)
        if not (os.path.exists(os.path.join(d, "die1.png")) and os.path.exists(os.path.join(d, "idle.png"))):
            continue
        idle = frames(os.path.join(d, "idle.png"))
        per = len(idle) // 32
        stands = idle[::per]
        fall = frames(os.path.join(d, "die1.png"))
        lying = frames(os.path.join(d, "die2.png"))[-1] if os.path.exists(os.path.join(d, "die2.png")) else fall[-1]
        stand = stands[best_facing(stands, fall[0])]
        e = electrocuted(stand, fall, sum(map(ord, uid)), 3.0)
        c = crushed(lying, sum(map(ord, uid)) + 1, 3.0)
        save(os.path.join(d, "die6.png"), e)
        save(os.path.join(d, "crushed.png"), c)
        if uid == "e1":
            corpse = crushed(lying, 77, 3.0)[1:]
            save(os.path.join(FX, "corpse.png"), corpse)
            previews += [e[::2], c]

    # Dog (AI sheets, 8 facings)
    stands = frames(os.path.join(DOG, "stand.png"))
    fall = frames(os.path.join(DOG, "die1.png"))
    lying = frames(os.path.join(DOG, "die2.png"))[-1]
    e = electrocuted(stands[best_facing(stands, fall[0])], fall, 5, 3.0)
    c = crushed(lying, 6, 3.0)
    save(os.path.join(DOG, "die6.png"), e)
    save(os.path.join(DOG, "crushed.png"), c)
    run = frames(os.path.join(DOG, "run.png"))         # 8 facings x 6
    jump = []
    for fc in range(8):
        for i, lift in enumerate((12, 28, 28, 12)):      # sprite px (x 0.2 = world px): a leap ~6 px high
            f = shift(run[fc * 6 + i], 0, -lift)
            jump.append(f)
    save(os.path.join(DOG, "jump.png"), jump, 8)
    previews += [e[::2], c]

    y = ["# HD electrocuted / crushed deaths of the dog, its jump and idle2, and the paratrooper corpse.",
         "# GENERATED by artsrc/units/soldiers/make_deaths.py - edit that script, not this file.",
         "# (The 3D soldiers' die6 / die-crushed are written by write_sequences.py.)", "", "dog:"]
    y += seq("die6", "ra|bits/hd/infantry/dog/die6.png", len(e), tick=80,
             extra=["Frames: " + ", ".join(str(i) for i in range(len(e)))])
    y += seq("die-crushed", "ra|bits/hd/infantry/dog/crushed.png", len(c), tick=1600,
             extra=["ZOffset: -511", "Frames: " + ", ".join(str(i) for i in range(len(c)))])
    y += seq("jump", "ra|bits/hd/infantry/dog/jump.png", 4, 8, 4, tick=90)
    y += seq("idle2", "ra|bits/hd/infantry/dog/idle1.png", 8, tick=120)
    y += ["", "explosion:"]
    y += seq("corpse", "ra|bits/hd/fx/corpse.png", 5, tick=1600, scale=0.2, extra=["ZOffset: -512"])
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))

    if show:
        os.makedirs(PREVIEW, exist_ok=True)
        rows = []
        for fr in previews:
            strip = np.concatenate(fr, axis=1)
            bg = np.zeros(strip.shape[:2] + (3,), np.float32) + np.array([0.36, 0.42, 0.25])
            rows.append(strip[..., :3] * strip[..., 3:4] + bg * (1 - strip[..., 3:4]))
        width = max(r.shape[1] for r in rows)
        rows = [np.pad(r, ((0, 0), (0, width - r.shape[1]), (0, 0)), constant_values=0.3) for r in rows]
        Image.fromarray((np.concatenate(rows, 0) * 255).astype(np.uint8)).save(os.path.join(PREVIEW, "deaths.png"))


if __name__ == "__main__":
    main()
