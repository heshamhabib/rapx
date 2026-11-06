#!/usr/bin/env python3
"""
HD walls, mines, hospital, windmill, oil pumpjack, lighthouse and the last classic building / prop animations
(RedAlert Project X, IDEA-30 phase 4).

  python3 artsrc/env/props3d/make_props.py [--skip-render] [--samples N]

1. Renders render_props.py jobs with Blender (Sketchfab models, credited in mods/rapx/CREDITS) into render/<job>/.
2. Packs them into mods/rapx/bits/hd/props/ and writes mods/rapx/sequences/hd-props.yaml (after hd-env.yaml):
   brik / sbag / fenc (16 neighbour joins; brik also scratched and damaged), minv / minp, hosp (idle, damaged,
   rubble, build-up), windmill (turning sails), v19 (nodding pumpjack) and v19.husk (charred, HD fire).
3. From the existing HD art: the lighthouse (assets/env/civilian/lhus.png fitted by make_env.py) with a sweeping
   beam; build-up (`make`) and rubble (`dead`) of the Bio Lab, Tech Center, Forward Command and Oil Derrick
   (shared building pipeline); burnt trees falling over (`tXX.husk dead`); fallen power poles; the village
   building's `active` frames; the MAD Tank's thump (`qtnk piston`).
Also writes one frame per new prop to mods/rapx/bits/hd/<image>.png for the sidebar cameos (px-cameos/generate.py).
"""
import argparse
import glob
import math
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "buildings"))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "env"))
import build_all  # noqa: E402

RENDER = os.path.join(HERE, "render")
HD = os.path.join(ROOT, "mods", "rapx", "bits", "hd")
OUT = os.path.join(HD, "props")
ENV = os.path.join(HD, "env")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-props.yaml")
ENV_SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-env.yaml")
TILESETS = ("TEMPERAT", "SNOW", "DESERT", "INTERIOR")
DENSITY = 3.0
JOBS = ["brik", "sbag", "fenc", "mines", "hosp", "windmill", "v19"]


def load(path):
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255
    a[..., 3] = np.where(a[..., 3] < 0.03, 0, a[..., 3])
    return a


def frames_of(path):
    im = Image.open(path)
    fw, fh = (int(v) for v in im.info["FrameSize"].split(","))
    n = int(im.info["FrameAmount"])
    a = np.asarray(im.convert("RGBA"), dtype=np.float32) / 255
    cols = a.shape[1] // fw
    return [a[(i // cols) * fh:(i // cols + 1) * fh, (i % cols) * fw:(i % cols + 1) * fw].copy() for i in range(n)]


def soot(im, strength=1.0, seed=3):
    rng = np.random.default_rng(seed)
    h, w, _ = im.shape
    n = gaussian_filter(rng.random((h, w)).astype(np.float32), max(2.0, w / 60))
    n = (n - n.min()) / (n.max() - n.min() + 1e-6)
    dark = np.clip((n - 0.45) * 2.5, 0, 1) * strength
    body = (im[..., 3] > 0.9).astype(np.float32)
    out = im.copy()
    out[..., :3] *= (1 - 0.7 * dark * body)[..., None] * (1 - 0.12 * strength)
    return out


def symmetric_box(frames, pad=3):
    """Crop box centred on the frame centre (the anchor), as tight as all frames allow."""
    a = np.zeros(frames[0].shape[:2], bool)
    for f in frames:
        a |= f[..., 3] > 0.02
    ys, xs = np.nonzero(a)
    h, w = a.shape
    hw = min(w // 2, int(max(w / 2 - xs.min(), xs.max() + 1 - w / 2)) + pad)
    hh = min(h // 2, int(max(h / 2 - ys.min(), ys.max() + 1 - h / 2)) + pad)
    return (w // 2 - hw, h // 2 - hh, w // 2 + hw, h // 2 + hh)


def save(path, frames, box=None):
    if box is None:
        box = symmetric_box(frames)
    x0, y0, x1, y1 = box
    crop = [f[y0:y1, x0:x1] for f in frames]
    fh, fw, _ = crop[0].shape
    cols = max(1, min(len(crop), 4096 // fw))
    rows = (len(crop) + cols - 1) // cols
    sheet = np.zeros((fh * rows, fw * cols, 4), np.float32)
    for i, f in enumerate(crop):
        r, c = divmod(i, cols)
        sheet[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw] = f
    sheet[..., :3] = np.where(sheet[..., 3:] > 0, sheet[..., :3], 0)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{fw},{fh}")
    info.add_text("FrameAmount", str(len(crop)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(path, pnginfo=info, optimize=True)
    print("  wrote", os.path.relpath(path, ROOT), f"{len(crop)} x {fw}x{fh}")
    return crop


def cameo(image, frame):
    """One frame for the sidebar cameo generator (it looks for bits/hd/<image>.png)."""
    Image.fromarray((np.clip(frame, 0, 1) * 255).astype(np.uint8)).save(os.path.join(HD, image + ".png"))


def seq(name, path, length, start=0, tick=None, files=None, extra=()):
    lines = [f"\t{name}:", f"\t\tFilename: {path}", "\t\tTilesetFilenames:"]
    lines += [f"\t\t\t{t}: {(files or {}).get(t, path)}" for t in TILESETS]
    lines += [f"\t\tStart: {start}", f"\t\tLength: {length}", "\t\tFacings: 1", "\t\tOffset: 0,0", f"\t\tScale: {1 / DENSITY:.4f}"]
    if tick:
        lines.append(f"\t\tTick: {tick}")
    return lines + [f"\t\t{e}" for e in extra]


def props_dir(name):
    return f"ra|bits/hd/props/{name}.png"


# --- 2D helpers ---------------------------------------------------------------------------------------------------

def rotate_about(f, cx, cy, ang, out_shape):
    """Rotates frame f (RGBA float) by ang radians about (cx, cy) into a canvas of out_shape, same anchor centre."""
    H, W = out_shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ox, oy = (W - f.shape[1]) / 2, (H - f.shape[0]) / 2
    c, s = math.cos(ang), math.sin(ang)
    dx, dy = xx - (cx + ox), yy - (cy + oy)
    sx = c * dx + s * dy + cx
    sy = -s * dx + c * dy + cy
    pre = np.dstack([f[..., :3] * f[..., 3:4], f[..., 3:4]])
    res = np.stack([map_coordinates(pre[..., ch], [sy, sx], order=1, mode="constant") for ch in range(4)], -1)
    a = res[..., 3:4]
    return np.dstack([res[..., :3] / np.maximum(a, 1e-5), a]).astype(np.float32)


def base_point(f):
    ys, xs = np.nonzero(f[..., 3] > 0.6)
    if not len(ys):
        return f.shape[1] / 2, f.shape[0] / 2
    bottom = ys.max()
    near = xs[ys > bottom - 6]
    return float(near.mean()), float(bottom)


def falling(f, n=8, final=1.45, dust=True):
    """A tree or pole toppling over about its base (to the right), with a dust puff where it lands."""
    h, w, _ = f.shape
    size = int(max(h, w) * 2.2)
    cx, cy = base_point(f)
    out = []
    for i in range(n):
        t = (i + 1) / n
        ang = final * t ** 1.8
        fr = rotate_about(f, cx, cy, -ang, (size, size))
        if dust and t > 0.6:
            yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
            gx = (size - w) / 2 + cx + h * 0.45
            gy = (size - h) / 2 + cy
            k = (t - 0.6) / 0.4
            d = np.exp(-(((xx - gx) / (h * 0.35)) ** 2 + ((yy - gy + 6) / (h * 0.12)) ** 2)) * 0.5 * (1 - 0.4 * k)
            dust_im = np.dstack([np.broadcast_to([0.45, 0.4, 0.33], (size, size, 3)), d])
            a = fr[..., 3:4] + dust_im[..., 3:4] * (1 - fr[..., 3:4])
            fr = np.dstack([(fr[..., :3] * fr[..., 3:4] + dust_im[..., :3] * dust_im[..., 3:4] * (1 - fr[..., 3:4]))
                            / np.maximum(a, 1e-5), a[..., 0]])
        out.append(fr.astype(np.float32))
    return out


def env_variants(image_id, seq_name="idle"):
    """The HD env files of a sequence per tileset, read from hd-env.yaml: {tileset: file path}."""
    s = open(ENV_SEQUENCES).read()
    i = s.find(f"\n{image_id}:\n")
    if i < 0:
        return {}
    m = re.search(r"\n(?=[^\t\n])", s[i + 2:])
    blk = s[i:i + 2 + m.start()] if m else s[i:]
    j = blk.find(f"\t{seq_name}:\n")
    if j < 0:
        return {}
    k = re.search(r"\n\t[a-z-]+:\n", blk[j + 2:])
    sb = blk[j:j + 2 + k.start()] if k else blk[j:]
    files = {}
    base = re.search(r"Filename: ra\|(\S+)", sb)
    for t in TILESETS:
        m2 = re.search(rf"\t{t}: ra\|(\S+)", sb)
        files[t] = (m2 or base).group(1) if (m2 or base) else None
    return files


def beam_frames(base, n=16):
    """Lighthouse: a light beam sweeping round from the lamp, brightest when it swings towards the camera."""
    h, w, _ = base.shape
    a = base[..., 3] > 0.6
    ys, xs = np.nonzero(a)
    top = ys.min()
    lamp = (float(xs[ys < top + 6].mean()), float(top + max(4, (ys.max() - top) * 0.07)))
    size = max(h, w) + 160
    ox, oy = (size - w) // 2, (size - h) // 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    lx, ly = lamp[0] + ox, lamp[1] + oy
    out = []
    for i in range(n):
        th = 2 * math.pi * i / n
        canvas = np.zeros((size, size, 4), np.float32)
        canvas[oy:oy + h, ox:ox + w] = base
        add = np.zeros((size, size), np.float32)
        for k, sign in enumerate((1, -1)):                       # two opposite lenses
            dx, dy = math.cos(th) * sign, math.sin(th) * sign * 0.45
            ln = math.hypot(dx, dy)
            ux, uy = dx / ln, dy / ln
            along = (xx - lx) * ux + (yy - ly) * uy
            across = -(xx - lx) * uy + (yy - ly) * ux
            length = 70 * ln
            cone = np.clip(1 - along / length, 0, 1) * (along > 0) * np.exp(-(across / (2 + along * 0.18)) ** 2)
            towards = 0.5 + 0.5 * math.sin(th) * sign                 # pointing at the camera: brighter
            add += cone * (0.25 + 0.5 * towards)
        add += np.exp(-((xx - lx) ** 2 + (yy - ly) ** 2) / 18) * 1.2
        add = gaussian_filter(add, 1.0)
        light = np.array([1.0, 0.95, 0.75], np.float32)
        al = np.clip(add, 0, 1)
        na = al + canvas[..., 3] * (1 - al)
        canvas[..., :3] = (light * al[..., None] + canvas[..., :3] * canvas[..., 3:4] * (1 - al[..., None])) / np.maximum(na, 1e-5)[..., None]
        canvas[..., 3] = na
        out.append(canvas)
    return out


# --- main -----------------------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()
    if not args.skip_render:
        for job in JOBS:
            subprocess.run(["nice", "-n", "10", "blender", "-b", "-P", os.path.join(HERE, "render_props.py"), "--", job,
                            os.path.join(RENDER, job), str(args.samples)], check=True, stdout=subprocess.DEVNULL)
            print("rendered", job)

    y = ["# HD walls, mines, hospital, windmill, pumpjack, lighthouse and the last classic building animations.",
         "# GENERATED by artsrc/env/props3d/make_props.py - edit that script, not this file.",
         "# Sketchfab models credited in mods/rapx/CREDITS.", ""]

    # Walls: 16 joins each; the concrete wall also scratched and damaged
    for wid in ("brik", "sbag", "fenc"):
        files = sorted(glob.glob(os.path.join(RENDER, wid, "wall-*.png")))
        fr = [load(f) for f in files]
        if wid == "brik":
            fr = fr[:16] + [soot(f, 0.6, 1) for f in fr[16:32]] + [soot(f, 1.2, 2) for f in fr[32:48]]
        crop = save(os.path.join(OUT, f"{wid}.png"), fr)
        cameo(wid, crop[10])                       # east-west section
        y += [f"{wid}:"] + seq("idle", props_dir(wid), 16)
        if wid == "brik":
            y += seq("scratched-idle", props_dir(wid), 16, 16) + seq("damaged-idle", props_dir(wid), 16, 32)
        y.append("")

    # Mines, half buried, drawn under units
    for mid in ("minv", "minp"):
        crop = save(os.path.join(OUT, f"{mid}.png"), [load(os.path.join(RENDER, "mines", f"{mid}.png"))])
        cameo(mid, crop[0])
        y += [f"{mid}:"] + seq("idle", props_dir(mid), 1, extra=["ZOffset: -512"]) + [""]

    # Hospital: idle, damaged, build-up, rubble and collapse from the shared building pipeline
    h = load(os.path.join(RENDER, "hosp", "hosp.png"))
    box = symmetric_box([h])
    crop = save(os.path.join(OUT, "hosp.png"), [h], box)
    save(os.path.join(OUT, "hosp-damaged.png"), [soot(h)], box)
    cameo("hosp", crop[0])
    build_all.make_animation(os.path.join(OUT, "hosp.png"), os.path.join(OUT, "hosp-make.png"))
    build_all.collapse_animation(os.path.join(OUT, "hosp-damaged.png"), os.path.join(OUT, "hosp-collapse.png"))
    col = frames_of(os.path.join(OUT, "hosp-collapse.png"))
    rubble = col[int(len(col) * 0.6)]                 # the ruin half sunk (the last frame has gone under)
    save(os.path.join(OUT, "hosp-dead.png"), [rubble], (0, 0, rubble.shape[1], rubble.shape[0]))
    y += ["hosp:"] + seq("idle", props_dir("hosp"), 1) + seq("damaged-idle", props_dir("hosp-damaged"), 1)
    y += seq("make", props_dir("hosp-make"), build_all.MAKE_FRAMES, tick=45)
    y += seq("dead", props_dir("hosp-dead"), 1, tick=800) + [""]

    # Windmill: sails turning; damaged = sooty
    wm = [load(os.path.join(RENDER, "windmill", f"windmill-{i}.png")) for i in range(8)]
    box = symmetric_box(wm)
    crop = save(os.path.join(OUT, "windmill.png"), wm, box)
    save(os.path.join(OUT, "windmill-damaged.png"), [soot(f) for f in wm], box)
    cameo("windmill", crop[0])
    y += ["windmill:"] + seq("idle", props_dir("windmill"), 8, tick=80) + seq("damaged-idle", props_dir("windmill-damaged"), 8, tick=80) + [""]

    # Oil pumpjack: one nodding cycle; the wreck is the pump charred, with the HD fire on it
    pj = [load(os.path.join(RENDER, "v19", f"v19-{i}.png")) for i in range(14)]
    box = symmetric_box(pj)
    crop = save(os.path.join(OUT, "v19.png"), pj, box)
    husk = soot(pj[0], 1.6)
    husk[..., :3] *= 0.45
    save(os.path.join(OUT, "v19-husk.png"), [husk], box)
    cameo("v19", crop[0])
    y += ["v19:"] + seq("idle", props_dir("v19"), 14, tick=90) + [""]
    fire = "ra|bits/hd/fx/fire/fire2.png"
    y += ["v19.husk:"] + seq("idle", props_dir("v19-husk"), 1)
    y += seq("fire-start", fire, 8, tick=50, extra=["ZOffset: 1"])
    y += seq("fire-loop", fire, 24, tick=50, extra=["ZOffset: 1"]) + [""]

    # Lighthouse: the AI render fitted like the other env props, with a sweeping beam
    import make_env  # noqa: E402
    src = os.path.join(ROOT, "assets", "env", "civilian", "lhus.png")
    tmp = os.path.join(RENDER, "lhus")
    os.makedirs(tmp, exist_ok=True)
    outs = [os.path.join(tmp, "lhus.png"), os.path.join(tmp, "lhus-burnt.png")]
    if make_env.process_render(src, "lhus", "TEMPERAT", outs, print):
        base = load(outs[0])
        burnt = load(outs[1]) if os.path.exists(outs[1]) else soot(base)
        lit = beam_frames(base)
        box = symmetric_box(lit)
        crop = save(os.path.join(OUT, "lhus.png"), lit, box)
        save(os.path.join(OUT, "lhus-damaged.png"), [beam_frames(burnt, 8)[i] for i in range(8)], box)
        cameo("lhus", crop[0])
        y += ["lhus:"] + seq("idle", props_dir("lhus"), 16, tick=120) + seq("damaged-idle", props_dir("lhus-damaged"), 8, tick=180) + [""]

    # Build-up and rubble of the tech buildings, per tileset variant of their HD env art
    for bid, want in (("bio", ("make", "dead")), ("miss", ("make", "dead")), ("fcom", ("make",)), ("oilb", ("make",))):
        idle, burnt = env_variants(bid), env_variants(bid, "damaged-idle")
        made, dead = {}, {}
        for t in TILESETS:
            f = idle.get(t)
            if not f or f in made:
                continue
            path = os.path.join(ROOT, "mods", "rapx", f)
            stem = os.path.splitext(os.path.basename(f))[0]
            if "make" in want:
                build_all.make_animation(path, os.path.join(OUT, f"{stem}-make.png"))
                made[f] = props_dir(f"{stem}-make")
            if "dead" in want:
                bf = burnt.get(t) or f
                build_all.collapse_animation(os.path.join(ROOT, "mods", "rapx", bf), os.path.join(OUT, f"{stem}-collapse.png"))
                col = frames_of(os.path.join(OUT, f"{stem}-collapse.png"))
                r = col[int(len(col) * 0.6)]
                save(os.path.join(OUT, f"{stem}-dead.png"), [r], (0, 0, r.shape[1], r.shape[0]))
                os.remove(os.path.join(OUT, f"{stem}-collapse.png"))
                dead[f] = props_dir(f"{stem}-dead")
        y.append(f"{bid}:")
        if made:
            files = {t: made[idle[t]] for t in TILESETS if idle.get(t) in made}
            y += seq("make", next(iter(made.values())), build_all.MAKE_FRAMES, tick=45, files=files)
        if dead:
            files = {t: dead[idle[t]] for t in TILESETS if idle.get(t) in dead}
            y += seq("dead", next(iter(dead.values())), 1, tick=800, files=files)
        y.append("")

    # Burnt trees topple over; power poles fall
    for husk in sorted({os.path.basename(p).split("-")[0] for p in glob.glob(os.path.join(ENV, "t*-burnt.png"))}):
        variants = env_variants(f"{husk}.husk")
        if not variants:
            continue
        made = {}
        for t in TILESETS:
            f = variants.get(t)
            if not f or f in made:
                continue
            stem = os.path.splitext(os.path.basename(f))[0]
            fr = falling(load(os.path.join(ROOT, "mods", "rapx", f)))
            save(os.path.join(OUT, f"{stem}-fall.png"), fr)
            made[f] = props_dir(f"{stem}-fall")
        files = {t: made[variants[t]] for t in TILESETS if variants.get(t) in made}
        y += [f"{husk}.husk:"] + seq("dead", next(iter(made.values())), 8, tick=80, files=files) + [""]
    for pole in ("utilpol1", "utilpol2"):
        f = load(os.path.join(ENV, f"{pole}.png"))
        fallen = falling(f, n=8, dust=False)[-1]
        save(os.path.join(OUT, f"{pole}-dead.png"), [fallen])
        y += [f"{pole}:"] + seq("dead", props_dir(f"{pole}-dead"), 1) + [""]

    # MAD Tank thump (MadTank ThumpSequence "piston", played as the body animation while it charges): the HD tank
    # slams down and bounces, 4 frames in 8 facings (it stands still while thumping), with dust at the tracks
    src = frames_of(os.path.join(HD, "units", "qtnk.png"))[::4]
    thump = []
    for f in src:
        fh, fw, _ = f.shape
        yy, xx = np.mgrid[0:fh, 0:fw].astype(np.float32)
        ys, xs = np.nonzero(f[..., 3] > 0.6)
        for i, dy in enumerate((-10, -4, 3, 0)):
            g = np.zeros_like(f)
            if dy < 0:
                g[:fh + dy] = f[-dy:]
            elif dy > 0:
                g[dy:] = f[:fh - dy]
            else:
                g = f.copy()
            if i == 2 and len(ys):                   # dust where the hull hits the ground
                d = np.exp(-(((xx - xs.mean()) / (fw * 0.3)) ** 2 + ((yy - ys.max()) / (fh * 0.05)) ** 2)) * 0.45
                a = g[..., 3] + d * (1 - g[..., 3])
                g[..., :3] = (g[..., :3] * g[..., 3:4] + np.array([0.5, 0.44, 0.35]) * (d * (1 - g[..., 3]))[..., None]) / np.maximum(a, 1e-5)[..., None]
                g[..., 3] = a
            thump.append(g)
    save(os.path.join(HD, "units", "qtnk-thump.png"), thump)
    y += ["qtnk:", "\tpiston:", "\t\tFilename: ra|bits/hd/units/qtnk-thump.png", "\t\tStart: 0", "\t\tLength: 4",
          "\t\tFacings: 8", "\t\tUseClassicFacings: False", "\t\tTick: 60", "\t\tScale: 0.2333", ""]

    # Village building v04: its active frames are the HD building
    idle, burnt = env_variants("v04"), env_variants("v04", "damaged-idle")
    if idle:
        y += ["v04:"] + seq("active", "ra|" + idle["TEMPERAT"], 1, files={t: "ra|" + idle[t] for t in TILESETS})
        y += seq("damaged-active", "ra|" + burnt["TEMPERAT"], 1, files={t: "ra|" + burnt[t] for t in TILESETS}) + [""]

    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))


if __name__ == "__main__":
    main()
