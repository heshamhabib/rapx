#!/usr/bin/env python3
"""
Video explosions (RedAlert Project X): turns AI-generated green-screen explosion clips into sprite sheets.

  python3 artsrc/fx/make_video_fx.py [--preview] [names...]   (names: rebuild only those clips)

Each clip in CLIPS (artsrc/fx/video-src/<name>.mp4, made with Google Flow on a flat chroma-green background, locked
camera, one centred blast) is keyed, despilled, faded at the frame edges (debris trails that leave the frame would
otherwise end in a hard line), resampled to FRAMES frames, cropped, squashed for the
50 degree camera and shrunk to fit MAXDIM. Writes mods/rapx/bits/hd/fx/video/<name>.png and mods/rapx/sequences/hd-video-fx.yaml (image
pxvideofx). The detonation point (the first bright flash) is the sprite origin. Clips marked loop (fires) repeat
seamlessly instead, with the foot of the flames as origin. PxExplosion warheads play explosions through their Video /
AirVideo lists; WithPxWreckFx, WithPxDamageFx and WithPxCollapse play the fires, smoke and dust. --preview writes artsrc/fx/preview/video-<name>.png on a grass colour.
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import binary_opening, gaussian_filter, map_coordinates, zoom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "video-src")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "video")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-video-fx.yaml")
PREVIEW = os.path.join(HERE, "preview")

FRAMES = 56          # frames kept per clip
MAXDIM = 440         # largest output frame side (px); keeps each clip near 25 MB of texture memory
SQUASH = 0.85        # vertical squash for straight-down shots; the game camera is at 50 degrees
EDGE = 40            # source pixels faded out along the frame border (scaled up for bigger sources)
FADE_TAIL = 0.0      # last part of an explosion faded out in the sheet (0: the warhead lingers and fades the last frame)
SCREEN_PER_PX = 0.224  # screen pixels per source pixel of a 360p clip at Size 1 (the warhead multiplies by Size)

# name -> options:
#   loop     a fire or smoke column that repeats forever: no tail fade, the last LOOP_BLEND of the clip is crossfaded
#            into its start, and the origin is the foot of the flames instead of the first flash
#   squash   vertical squash (SQUASH suits straight-down shots; high-angle and side-on shots need none: 1.0)
#   start    seconds cut from the start (a shell flying in, a pad shown before the blast)
#   anchor   "flash" (default: first bright flash), "first" (middle of the first visible frame), "base" (foot),
#            "centre" (middle of everything ever visible)
#   shadow   drop the shadow the clip casts on the green: the fraction of the frame, from the bottom, where darker
#            green counts as background (1.0 = everywhere). Thin black smoke looks just like shadow, so keep it to
#            the ground band under smoke columns.
#   strict   harder despill for clips without bright yellow/orange (dust, earth)
#   frames   frames kept (default FRAMES; long clips need more to stay smooth)
#   mirror   also write <name>-m, flipped left to right (directional clips such as a crash skid)
#   edge     wider fade at the frame border, for clips whose dust or smoke runs off the frame (multiple of EDGE)
#   edges    {"top": k, ...}: widen the border fade on those sides only (thin smoke brushing one edge)
#   ring     fade a dust ring that runs off the bottom along an oval in its own perspective
#   tail     seconds of break-up synthesised from the last frame, for clips that end before the smoke clears
#            (tail_frames: how many; the warhead plays them via VideoSlowFrom/VideoSlowTick, printed here)
#   cropped_ok  silence the cropping warning (only for clips checked by eye: debris specks, not cut-off mass)
#   then     (with then_frames: frames kept from it) a continuation clip (made in Flow's Frames mode from this clip's last frame) appended to it, so the
#            effect plays out and clears by itself instead of the game fading out a frozen last frame
#   size     largest output frame side, for 720p clips that hold more detail
#   scale    in-game size multiplier for this clip
CLIPS = {
    "artillery-a": {"edges": {"left": 2.0, "right": 2.5}},
    "artillery-b": {},
    "artillery-c": {"squash": 1.0, "size": 540, "edges": {"top": 3.0}, "ring": True},
    "cannon-a": {"squash": 1.0},
    "cannon-b": {"squash": 1.0},
    "dirt-a": {"squash": 1.0, "start": 2 / 24, "anchor": "first"},
    "bomb-a": {"squash": 1.0, "size": 540, "edges": {"top": 2.0}, "ring": True},
    "building-a": {"squash": 1.0, "size": 540, "start": 4 / 24, "ring": True},
    "vehicle-a": {"squash": 1.0},
    "flak-a": {"squash": 1.0},
    "fire-wreck-a": {"loop": True, "squash": 1.0, "size": 300, "edges": {"top": 2.0}},
    "fire-small-b": {"loop": True, "squash": 1.0, "size": 300},
    "fire-big-b": {"loop": True, "squash": 1.0, "size": 400, "shadow": 0.6, "edges": {"top": 3.0}},
    "smoke-column-a": {"loop": True, "squash": 1.0, "size": 440, "shadow": 0.3},
    "dust-a": {"squash": 1.0, "anchor": "centre", "shadow": 1.0, "strict": True},
    "nuke-a": {"squash": 1.0, "size": 560, "frames": 80, "strict": True, "edges": {"top": 0.5}, "ring": True,
               "tail": 5, "tail_frames": 30, "cropped_ok": True},
    "napalm-a": {"squash": 1.0, "edges": {"top": 3.0}},
    "launch-blast-a": {"squash": 1.0, "ring": True},
    "crash-a": {"squash": 1.0, "size": 540, "start": 7 / 24, "anchor": "first", "mirror": True,
                "edges": {"right": 2.0}},
}
LOOP_BLEND = 0.25


def read_clip(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,r_frame_rate", "-of", "csv=p=0", path],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    num, den = probe[2].split("/")
    fps = float(num) / float(den)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32) / 255, fps


CROP_WARN = 0.04     # a clip whose solid mass covers more than this share of a frame edge was filmed cropped


def cropping(frames, bg):
    """How much of each frame edge the effect's solid mass covers at worst (thin debris and trails ignored): the
    effect ran out of the filmed frame there, and the missing part cannot be recovered. Fix it in the clip."""
    h = frames.shape[1]
    r = max(4, h // 60)
    kb = bg[1] - max(bg[0], bg[2])
    worst = dict(top=0.0, bottom=0.0, left=0.0, right=0.0)
    for f in frames[::6]:
        k = f[..., 1] - np.maximum(f[..., 0], f[..., 2])
        s = binary_opening(k < kb * 0.35, structure=np.ones((r, r)))
        for side, v in (("top", s[:r].mean()), ("bottom", s[-r:].mean()), ("left", s[:, :r].mean()),
                        ("right", s[:, -r:].mean())):
            worst[side] = max(worst[side], float(v))
    return {k: v for k, v in worst.items() if v > CROP_WARN}


def background(frames):
    """The screen colour: median of the clearly green pixels of frames across the clip (a flash can wash out the
    first ones)."""
    n = len(frames)
    px = frames[[0, n // 4, n // 2, 3 * n // 4, n - 1]].reshape(-1, 3)
    green = px[(px[:, 1] - np.maximum(px[:, 0], px[:, 2])) > 0.35]
    return np.median(green, axis=0)


def key(frame, bg, shadow=0.0, strict=False):
    """Alpha from how green a pixel is relative to the screen, then unmix the screen colour out of it."""
    r, g, b = frame[..., 0], frame[..., 1], frame[..., 2]
    k = g - np.maximum(r, b)
    kb = bg[1] - max(bg[0], bg[2])
    a = np.clip(1 - k / kb, 0, 1)
    if shadow > 0:
        # A shadow darkens the screen without changing its hue: judge the band by how green, not how bright
        hue = np.clip(1 - (k / np.maximum(g, 1e-3)) / (kb / bg[1]), 0, 1)
        band = np.arange(frame.shape[0])[:, None] >= frame.shape[0] * (1 - shadow)
        a = np.where(band, np.minimum(a, hue), a)
    a = np.clip((a - 0.06) / 0.88, 0, 1)
    a = gaussian_filter(a, 0.6)
    safe = np.maximum(a, 0.02)[..., None]
    rgb = np.clip((frame - (1 - safe) * bg) / safe, 0, 1)
    # Despill: no keyed pixel may be greener than its red/blue allow (fire and smoke are never green). Pixels that
    # needed a lot of it are glare lighting up the screen rather than matter in front of it: thin them out.
    # strict (dust, earth): green may not exceed the mean of red and blue either.
    # See-through glare (a flash's halo) unmixes yellow-green: the thinner it is, the less green it may keep.
    limit = (rgb[..., 0] + rgb[..., 2]) / 2 if strict else np.maximum(rgb[..., 0], rgb[..., 2]) * (0.86 + 0.16 * a)
    # Warm glare: a thin halo around a flash is orange light, so towards zero opacity green falls to 70% of red
    thin = np.clip((0.6 - a) / 0.5, 0, 1)
    warm = rgb[..., 0] >= rgb[..., 2]
    limit = np.where(warm, np.minimum(limit, rgb[..., 0] * (1 - 0.3 * thin)), limit)
    spill = np.clip(rgb[..., 1] - limit, 0, 1)
    rgb[..., 1] = np.minimum(rgb[..., 1], limit)
    a = a * np.clip(1 - spill * 3, 0, 1)
    # Glare: where the picture is brighter than the bare screen, a flash's light is falling on it. That is light, not
    # matter, and must never darken what lies behind it: give it full brightness (keeping its hue) where it is thin
    glare = np.clip((frame.mean(axis=2) - bg.mean() * 1.02) / 0.12, 0, 1) * np.clip((0.95 - a) / 0.3, 0, 1)
    if not strict:
        bright = rgb / np.maximum(rgb.max(axis=2, keepdims=True), 1e-3)
        rgb = rgb + (bright - rgb) * glare[..., None]
        rgb[..., 1] = np.minimum(rgb[..., 1], np.where(rgb[..., 0] >= rgb[..., 2], rgb[..., 0] * (1 - 0.3 * glare), 1))
    # Unmixing over-subtracts green on soft edges (the video's colour is stored at half resolution), which tints
    # them magenta: no pixel may be less green than both red and blue
    rgb[..., 1] = np.maximum(rgb[..., 1], np.minimum(rgb[..., 0], rgb[..., 2]) * 0.98)
    return np.dstack([rgb, a])


def edge_ramp(h, w, edge, sides=None):
    """Fade towards the frame border; sides = {"top": k, ...} widens the fade on those sides only (k x edge)."""
    sides = sides or {}
    ys, xs = np.arange(h, dtype=np.float32), np.arange(w, dtype=np.float32)
    t = np.ones((h, w), np.float32)
    for dist, side, axis in ((ys, "top", 0), (ys[::-1], "bottom", 0), (xs, "left", 1), (xs[::-1], "right", 1)):
        ramp = np.clip(dist / (edge * sides.get(side, 1.0)), 0, 1)
        t = np.minimum(t, ramp[:, None] if axis == 0 else ramp[None, :])
    return t * t * (3 - 2 * t)


def noise(h, w, seed, scales=(6, 18, 48)):
    """Smooth fractal noise in 0..1 (bigger features weigh more)."""
    rng = np.random.default_rng(seed)
    n = np.zeros((h, w), np.float32)
    total = 0.0
    for i, sc in enumerate(scales):
        layer = gaussian_filter(rng.random((h, w)).astype(np.float32), sc)
        layer = (layer - layer.mean()) / (layer.std() + 1e-6)
        n += layer * (i + 1)
        total += i + 1
    n /= total
    return np.clip(0.5 + n * 0.5, 0, 1)


def dissipate(last, anchor_xy, count, wind=0.12, seed=7):
    """Frames of a smoke cloud breaking up, made from its last filmed frame: holes open in a drifting noise pattern
    and grow, the smoke spreads and blurs, the top drifts with the wind and rises more than the base, glow dies out
    and the smoke turns lighter as it thins. For clips that end before the smoke has cleared."""
    h, w, _ = last.shape
    ax, ay = anchor_xy
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    height = np.clip((ay - yy) / max(ay, 1), 0, 1)                  # 0 at the foot, 1 at the top of the frame
    big = noise(h * 2, w, seed, scales=(14, 34, 80))                  # taller than the frame: it scrolls upwards
    fine = noise(h * 2, w, seed + 1, scales=(5, 12))
    pm = last[..., :3] * last[..., 3:]
    a0 = last[..., 3]
    out = []
    for i in range(1, count + 1):
        t = i / count
        # Where each pixel's smoke came from: wind shear (more aloft), rise (more aloft), spread from the centre
        sx = xx - wind * w * t * (0.3 + 0.7 * height) - (xx - ax) * 0.35 * t * height / (1 + 0.35 * t * height)
        sy = yy + 0.06 * h * t * height
        coords = [sy, sx]
        pmi = np.dstack([map_coordinates(pm[..., c], coords, order=1, mode="constant") for c in range(3)])
        ai = map_coordinates(a0, coords, order=1, mode="constant")
        sigma = 0.8 + 6 * t
        pmi = np.dstack([gaussian_filter(pmi[..., c], sigma) for c in range(3)])
        ai = gaussian_filter(ai, sigma)
        # Break-up: first the smoke thins unevenly in broad soft patches, then (second half) the thinnest patches tear
        # away; overall density falls slowly the whole time
        off = int(t * h * 0.5)
        n = 0.75 * big[h - off:2 * h - off] + 0.25 * fine[h - off:2 * h - off]
        patch = np.clip(0.3 + 0.9 * n, 0, 1)
        tear = np.clip((n - (1.6 * t - 0.8)) / 0.4, 0, 1)
        rgb = pmi / np.maximum(ai, 1e-4)[..., None]
        ai = ai * (1 + (patch - 1) * min(1.0, 1.5 * t)) * tear * (1 - t) ** 1.2
        lum = rgb.mean(axis=2, keepdims=True)
        grey = np.clip(lum * 1.05, 0, 1) * np.array([1.0, 0.98, 0.95])
        rgb = rgb + (grey - rgb) * min(1.0, t * 3)                     # the glow dies out
        rgb = rgb + (0.62 - rgb) * 0.45 * t                           # thinning smoke turns lighter
        out.append(np.dstack([np.clip(rgb, 0, 1), np.clip(ai, 0, 1)]).astype(np.float32))
    return out


def anchor(frames):
    """Centre of the first flash bright enough to stand out."""
    for f in frames[:12]:
        lum = f[..., :3].mean(axis=2) * f[..., 3]
        mask = lum > 0.85
        if mask.sum() > 20:
            ys, xs = np.nonzero(mask)
            return float(xs.mean()), float(ys.mean())
    h, w = frames[0].shape[:2]
    return w / 2, h / 2


def loop_blend(frames):
    """Crossfade the end of the clip into its start (premultiplied), so the last frame leads into the first."""
    n = len(frames)
    blend = max(2, int(n * LOOP_BLEND))
    out = []
    for i in range(n - blend):
        f = frames[i]
        if i < blend:
            t = i / blend
            g = frames[n - blend + i]
            pa = f[..., :3] * f[..., 3:] * t + g[..., :3] * g[..., 3:] * (1 - t)
            a = f[..., 3:] * t + g[..., 3:] * (1 - t)
            f = np.dstack([pa / np.maximum(a, 1e-4), a])
        out.append(f)
    return out


def base(frames):
    """Foot of a fire or smoke column: the bottom of everything dense enough, centred on it."""
    dense = np.max([f[..., 3] for f in frames], axis=0) > 0.5
    ys, xs = np.nonzero(dense)
    bottom = ys.max()
    row = xs[ys > bottom - 0.1 * (bottom - ys.min())]
    return float(row.mean()), float(bottom)


def first(frames):
    """Middle of whatever is visible in the first frame."""
    ys, xs = np.nonzero(frames[0][..., 3] > 0.3)
    if len(xs) == 0:
        h, w = frames[0].shape[:2]
        return w / 2, h / 2
    return float(xs.mean()), float(ys.mean())


def centre(frames):
    """Middle of everything that is ever visible."""
    ys, xs = np.nonzero(np.max([f[..., 3] for f in frames], axis=0) > 0.3)
    return float(xs.mean()), float(ys.mean())


def process(name, opts):
    src, fps = read_clip(os.path.join(SRC, f"{name}.mp4"))
    then = opts.get("then")
    split = 0
    if then and os.path.exists(os.path.join(SRC, f"{then}.mp4")):
        more, _ = read_clip(os.path.join(SRC, f"{then}.mp4"))
        if more.shape[1:3] != src.shape[1:3]:
            more = np.stack([np.asarray(Image.fromarray((f * 255).astype(np.uint8)).resize(
                (src.shape[2], src.shape[1]), Image.LANCZOS)).astype(np.float32) / 255 for f in more])
        # Its first frame repeats our last one
        split = len(src)
        src = np.concatenate([src, more[1:]])
    bg = background(src)
    src = src[int(round(opts.get("start", 0) * fps)):]
    cut = cropping(src, bg)
    if cut and not opts.get("cropped_ok"):
        print(f"  WARNING {name}: filmed cropped, the effect runs out of the frame at "
              + ", ".join(f"{k} {v:.0%}" for k, v in cut.items()) + " - regenerate it with the camera further back")
    n = len(src)
    short = min(src.shape[1:3])
    loop = opts.get("loop", False)
    frames = opts.get("frames", FRAMES)
    count = int(frames / (1 - LOOP_BLEND)) if loop else frames
    picks = np.linspace(0, n - 1, count).round().astype(int)
    slow = None
    if split:
        # The continuation is slow smoke: it gets its own, lower frame rate (the warhead's VideoSlowFrom/-Tick)
        rest = opts.get("then_frames", count // 2)
        picks = np.concatenate([np.linspace(0, split - 1, count).round(),
                                np.linspace(split, n - 1, rest).round()]).astype(int)
        slow = (count, int(round((n - split) / fps * 1000 / rest)))
        n, count = split, count + rest
    ramp = edge_ramp(*src.shape[1:3], EDGE * short / 360 * opts.get("edge", 1.0), opts.get("edges"))
    out = []
    for i, j in enumerate(picks):
        f = key(src[j], bg, opts.get("shadow", 0.0), opts.get("strict", False))
        f[..., 3] *= ramp
        if not loop and FADE_TAIL > 0:
            tail = np.clip((1 - i / (count - 1)) / FADE_TAIL, 0, 1)
            f[..., 3] *= tail * tail * (3 - 2 * tail)
        out.append(f)

    if loop:
        out = loop_blend(out)
    mode = opts.get("anchor", "base" if loop else "flash")
    ax, ay = {"flash": anchor, "first": first, "base": base, "centre": centre}[mode](out)
    if opts.get("ring"):
        # Dust ring running off the bottom: fade its front along an oval that follows the ring's perspective, not
        # along a straight line at the frame edge
        h, w = out[0].shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        rx, ry = min(ax, w - ax), h - ay
        d = np.sqrt(((xx - ax) / rx) ** 2 + ((yy - ay) / ry) ** 2)
        t = np.clip((d - 0.8) / 0.2, 0, 1)
        oval = np.where(yy > ay, 1 - t * t * (3 - 2 * t), 1).astype(np.float32)
        for f in out:
            f[..., 3] *= oval

    # Crop to everything that is ever visible
    alive = np.max([f[..., 3] for f in out], axis=0) > 0.02
    ys, xs = np.nonzero(alive)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    out = [f[y0:y1, x0:x1] for f in out]
    ax, ay = ax - x0, ay - y0

    squash = opts.get("squash", SQUASH)
    size = opts.get("size", MAXDIM)
    r = min(1.0, size / (x1 - x0), size / ((y1 - y0) * squash))
    sy, sx = r * squash, r
    out = [np.clip(zoom(f, (sy, sx, 1), order=1), 0, 1) for f in out]
    ax, ay = ax * sx, ay * sy
    tail = opts.get("tail")
    if tail:
        # The clip ends before its smoke has cleared: break the last frame up over `tail` seconds
        rest = opts.get("tail_frames", 30)
        base_y = max(np.nonzero(np.max([f[..., 3] for f in out], axis=0) > 0.3)[0].max(), ay)
        slow = (len(out), int(round(tail * 1000 / rest)))
        out += dissipate(out[-1], (ax, base_y), rest)
    scale = SCREEN_PER_PX * 360 / short * opts.get("scale", 1.0) / r

    tick = int(round(n / fps * 1000 / (slow[0] if slow else count)))
    if tail:
        tick = int(round(n / fps * 1000 / count))
    if slow:
        print(f"  {name}: continuation from frame {slow[0]} at {slow[1]} ms per frame "
              f"(set VideoSlowFrom: {slow[0]} and VideoSlowTick: {slow[1]} on the warhead)")
    print(f"  {name}: {n} src frames @ {fps:.0f} fps, bg {np.round(bg * 255).astype(int)}, "
          f"{len(out)} x {out[0].shape[1]}x{out[0].shape[0]}, tick {tick} ms, scale {scale:.3f}, anchor {ax:.0f},{ay:.0f}")
    return out, (ax, ay), tick, scale


def save(name, frames, anc):
    os.makedirs(OUT, exist_ok=True)
    h, w, _ = frames[0].shape
    columns = max(1, 4096 // w)
    rows = (len(frames) + columns - 1) // columns
    sheet = np.zeros((h * rows, w * columns, 4), np.float32)
    for i, fr in enumerate(frames):
        r, c = divmod(i, columns)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = fr
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    info.add_text("Offset", f"{w / 2 - anc[0]:.0f},{h / 2 - anc[1]:.0f}")
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{name}.png"),
                                                                       pnginfo=info, optimize=True)


def preview(name, frames, step=4):
    os.makedirs(PREVIEW, exist_ok=True)
    pick = frames[::step]
    h, w, _ = pick[0].shape
    bg = np.zeros((h, w * len(pick), 3), np.float32) + np.array([0.36, 0.42, 0.25])
    for i, fr in enumerate(pick):
        a = fr[..., 3:4]
        bg[:, i * w:(i + 1) * w] = fr[..., :3] * a + bg[:, i * w:(i + 1) * w] * (1 - a)
    Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8)).save(os.path.join(PREVIEW, f"video-{name}.png"))


def sequence_info(name):
    """Tick and Scale of an already built clip, from the current sequences file (to rebuild only some clips)."""
    if not os.path.exists(SEQUENCES):
        return None, None
    lines = open(SEQUENCES).read().split("\n")
    try:
        i = lines.index(f"\t{name}:")
    except ValueError:
        return None, None
    block = {l.strip().split(": ")[0]: l.strip().split(": ")[1] for l in lines[i + 1:i + 8] if ": " in l}
    return int(block["Tick"]), float(block["Scale"])


def sheet_length(name):
    return int(Image.open(os.path.join(OUT, f"{name}.png")).text["FrameAmount"])


def main():
    y = ["# Video explosions keyed from green-screen clips (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_video_fx.py - edit that script, not this file.", "", "pxvideofx:"]
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    for name, opts in CLIPS.items():
        frames, anc, tick, scale = None, None, None, None
        variants = [(name, False)] + ([(name + "-m", True)] if opts.get("mirror") else [])
        for out, flip in variants:
            if not only or name in only:
                if frames is None:
                    frames, anc, tick, scale = process(name, opts)
                w = frames[0].shape[1]
                save(out, [f[:, ::-1] for f in frames] if flip else frames, (w - anc[0], anc[1]) if flip else anc)
                if "--preview" in sys.argv and not flip:
                    preview(name, frames)
            else:
                tick, scale = sequence_info(name)
                if tick is None:
                    continue
            length = len(frames) if frames is not None else sheet_length(out)
            path = f"ra|bits/hd/fx/video/{out}.png"
            y += [f"\t{out}:", f"\t\tFilename: {path}", "\t\tStart: 0", f"\t\tLength: {length}",
                  f"\t\tTick: {tick}", "\t\tOffset: 0,0", f"\t\tScale: {scale:.4f}", "\t\tZOffset: 512"]
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print(f"wrote {SEQUENCES}")


if __name__ == "__main__":
    main()
