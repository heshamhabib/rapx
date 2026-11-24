#!/usr/bin/env python3
"""
Filmed effects (RedAlert Project X): turns Google Flow clips (artsrc/fx/video-prompts-v2.md) into sprite sheets.

  python3 artsrc/fx/make_video_fx.py [--preview] [--jobs N] [names...]   (names: rebuild only those clips/groups)

Each clip in CLIPS (artsrc/fx/video-src/<name>.mp4) is keyed off its chroma-green (or black) background, despilled,
resampled to its frame budget, cropped to everything it ever shows and shrunk to fit its size. Writes
mods/rapx/bits/hd/fx/video/<name>.png and mods/rapx/sequences/hd-video-fx.yaml (image pxvideofx). Clips play their whole
life on screen; nothing is faded out here or in the game.

Cut-off effects: Flow often lets smoke, dust rings or debris run past the frame edge. Every side where the effect's
solid mass meets the edge is EXTENDED instead of faded: the strip along that edge is mirrored outwards and dissolves
with distance, blurring, thinning and breaking up in drifting noise, so the smoke reads as carrying on past the old
edge and thinning into the air rather than stopping at a line.

Groups (fires and smoke: start, loop, end) share one crop, scale and origin, so the game can hand over from one part
to the next on the spot. A chain ("then") joins Frames-mode continuations into one clip (the nuke), the later parts at
their own, slower frame rate (the warhead's VideoSlowFrom / VideoSlowTick, printed here).
--preview writes artsrc/fx/preview/video-<name>.png on a grass colour.
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import binary_opening, gaussian_filter, zoom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "video-src")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "video")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-video-fx.yaml")
PREVIEW = os.path.join(HERE, "preview")

FPS_KEPT = 7           # frames kept per second of clip (the game dissolves each frame into the next, so it stays smooth)
FRAMES_MIN, FRAMES_MAX = 28, 48
TAIL_MAX = 3.0         # seconds of generated break-up at most, for clips whose smoke has not cleared by their end
LOOP_FRAMES = 48       # frames kept per loop (before the seam crossfade)
SIZE_SMALL = 320       # largest output side for 360p clips (texture memory: ~30 x 320 x 180 x 4 bytes per clip)
SIZE_BIG = 400         # largest output side for 720p clips
EDGE = 14              # px faded at frame borders the effect never reaches (scaled for bigger sources)
CROP_WARN = 0.04       # share of a frame edge the effect's solid mass may cover before that side is extended
END_WARN = 0.01        # share of the last frame an effect may still cover when the clip ends
SCREEN_PER_PX = 0.224  # screen pixels per source pixel of a 360p clip at Size 1 (warheads multiply by Size)
LOOP_BLEND = 0.25

# name -> options:
#   loop      repeats forever: the last LOOP_BLEND is crossfaded into the start; origin = foot of the flames/column
#   bg        "black" for clips filmed on black (electric arcs): alpha from brightness
#   start     seconds cut from the start, or "flash": cut everything before the first bright flash (a missile or
#             shell flying in that the game draws itself)
#   (start "blast": cut at the blast itself, for air hits that show the missile and the jet it hits flying in)
#   lead      source frames kept before the flash with start "flash" (default 1; 0 or less when the shell is still in view)
#   anchor    "flash" (default; first bright flash), "first", "base" (foot), "centre"
#   erase     [(x0, y0, x1, y1, half width)] in source pixels: grey smoke along these lines is removed (the trail of a
#             missile flying in that hangs on after the flash)
#   strict    harder despill for clips without bright yellow/orange (dust, earth, water)
#   frames    frames kept; size: largest output side; scale: in-game size multiplier
#   mirror    also define <name>-m, the same sheet flipped left to right (FlipX: no extra texture memory)
#   open_end  ends with the effect still showing on purpose (napalm hands over to the fire loop)
#   then      list of Frames-mode continuations joined after it (then_frames: frames kept from them)
#   fps       frames kept per second instead of FPS_KEPT: fires and smoke loops (played frame by frame, no blending)
#   group     name of the group's master clip (fires: start/loop/end share crop, scale and origin)
CLIPS = {
    # Ground explosions
    "cannon-1": {}, "cannon-2": {},
    "dirt-1": {"strict": True}, "dirt-2": {"strict": True},
    "artillery-1": {}, "artillery-2": {},
    # both film their own missile diving in (from a fixed side, ~1.3 s before the blast): the game draws its own
    "heavy-missile-1": {"start": "flash", "lead": 0},
    "heavy-missile-2": {"start": "flash", "lead": -3, "erase": [(700, 400, 1060, -40, 26)]},
    "bomb-1": {}, "bomb-2": {},
    "thermobaric": {},
    "cluster-1": {"anchor": "centre"},
    "gun-strafe-1": {"anchor": "first", "mirror": True},
    # Air explosions
    "airburst-1": {"start": "blast", "lead": -1}, "airburst-2": {"start": "blast", "lead": -3},
    "intercept-1": {"start": "blast", "lead": -1},
    "flak-1": {},
    "white-phosphorus-1": {},
    # Deaths
    "vehicle-1": {}, "vehicle-2": {},
    "building-1": {}, "building-2": {},
    "collapse-dust-1": {"anchor": "centre", "strict": True},
    "barrel-1": {},
    "ship-1": {},
    # Aircraft
    "jet-explode-1": {},
    "crash-1": {"mirror": True}, "crash-2": {"mirror": True},
    "heli-crash-1": {},
    # Water
    "splash-1": {"strict": True, "frames": 40}, "splash-2": {"strict": True, "frames": 40},
    "big-splash-1": {"strict": True, "frames": 54},
    "torpedo-1": {},
    # Weapons
    "launch-blast-1": {}, "launch-blast-2": {},
    "napalm-1": {"open_end": True},
    "tesla-hit-1": {"bg": "black"},
    "flame-burst-1": {"start": "flash"},
    "smoke-grenade-1": {"strict": True, "anchor": "centre"},
    # Nuclear: three Frames-mode parts, one event
    "nuke-1-1": {"then": ["nuke-2", "nuke-3"], "frames": 64, "then_frames": 48, "strict": True, "size": 470},
    # Fire and smoke: start / loop / end
    "fire-big-loop-1": {"loop": True, "group": "fire-big-loop-1", "size": 290, "fps": 14},
    "fire-big-start": {"group": "fire-big-loop-1", "size": 290, "fps": 14},
    "fire-big-end": {"group": "fire-big-loop-1", "size": 290, "fps": 14},
    "fire-small-loop-1": {"loop": True, "group": "fire-small-loop-1", "size": 200, "fps": 14},
    "fire-small-loop-2": {"loop": True, "group": "fire-small-loop-1", "size": 200, "fps": 14},
    "fire-small-start": {"group": "fire-small-loop-1", "size": 200, "fps": 14},
    "fire-small-end": {"group": "fire-small-loop-1", "size": 200, "fps": 14},
    "fire-wreck-loop-2": {"loop": True, "group": "fire-wreck-loop-2", "size": 210, "fps": 14},
    "fire-wreck-end": {"group": "fire-wreck-loop-2", "size": 210, "fps": 14},
    "smoke-column-loop-2": {"loop": True, "group": "smoke-column-loop-2", "size": 300, "fps": 14},
    "smoke-column-end": {"group": "smoke-column-loop-2", "size": 300, "fps": 14},
    "chimney-loop-1": {"loop": True, "size": 210, "fps": 14},
    "steam-loop-1": {"loop": True, "size": 210, "strict": True, "fps": 14},
    "gas-flare-loop-1": {"loop": True, "size": 200, "fps": 14},
    "tesla-crackle-loop-1": {"loop": True, "bg": "black", "size": 210, "anchor": "centre", "fps": 14},
}


# Sequences of image `explosion` for warheads that play stock effects (CreateEffect): alias -> clip
EXPLOSION_ALIASES = {"vsplash-1": "splash-1", "vsplash-2": "splash-2", "vbigsplash-1": "big-splash-1"}


# --- Reading and keying -------------------------------------------------------------------------------------------

def read_clip(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,r_frame_rate", "-of", "csv=p=0", path],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    num, den = probe[2].split("/")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32) / 255, float(num) / float(den)


def background(frames, black):
    """The bare screen, per pixel: Flow lights its green unevenly (bright middle, darker corners, soft shadows), so
    each pixel gets the median of the frames where it shows clean green; pixels never clean are filled from around."""
    if black:
        return np.zeros(frames.shape[1:], np.float32)
    idx = np.linspace(0, len(frames) - 1, min(32, len(frames))).round().astype(int)
    st = frames[idx]
    clean = (st[..., 1] - np.maximum(st[..., 0], st[..., 2])) > 0.30
    med = np.nanmedian(np.where(clean[..., None], st, np.nan), axis=0)
    valid = ~np.isnan(med[..., 0])
    med = np.nan_to_num(med)
    sigma = frames.shape[1] / 20
    weight = np.maximum(gaussian_filter(valid.astype(np.float32), sigma), 1e-4)
    fill = np.dstack([gaussian_filter(med[..., c] * valid, sigma) / weight for c in range(3)])
    plate = np.where(valid[..., None], med, fill)
    return np.dstack([gaussian_filter(plate[..., c], 2) for c in range(3)]).astype(np.float32)


def solid_mask(f, bg, black):
    if black:
        return f.max(axis=2) > 0.16
    kb = bg[..., 1] - np.maximum(bg[..., 0], bg[..., 2])
    return (f[..., 1] - np.maximum(f[..., 0], f[..., 2])) < kb * 0.35


def cropping(frames, bg, black):
    """How much of each frame edge the effect's solid mass covers at worst (thin debris and trails ignored)."""
    h = frames.shape[1]
    r = max(4, h // 60)
    worst = dict(top=0.0, bottom=0.0, left=0.0, right=0.0)
    for f in frames[::4]:
        s = binary_opening(solid_mask(f, bg, black), structure=np.ones((r, r)))
        for side, v in (("top", s[:r].mean()), ("bottom", s[-r:].mean()), ("left", s[:, :r].mean()),
                        ("right", s[:, -r:].mean())):
            worst[side] = max(worst[side], float(v))
    return {k: v for k, v in worst.items() if v > CROP_WARN}


def key_black(frame):
    """Light on black (arcs, sparks): alpha from brightness, colour unmultiplied."""
    a = np.clip((frame.max(axis=2) - 0.03) / 0.75, 0, 1) ** 0.85
    rgb = np.clip(frame / np.maximum(a, 0.02)[..., None], 0, 1)
    return np.dstack([rgb, a])


def key(frame, bg, strict=False):
    """Alpha from how green a pixel is relative to the screen, then unmix the screen colour out of it."""
    r, g, b = frame[..., 0], frame[..., 1], frame[..., 2]
    k = g - np.maximum(r, b)
    kb = np.maximum(bg[..., 1] - np.maximum(bg[..., 0], bg[..., 2]), 0.05)
    a = np.clip(1 - k / kb, 0, 1)
    a = np.clip((a - 0.06) / 0.88, 0, 1)
    a = gaussian_filter(a, 0.6)
    safe = np.maximum(a, 0.02)[..., None]
    rgb = np.clip((frame - (1 - safe) * bg) / safe, 0, 1)
    # Despill: fire, smoke, dust and water are never green; see-through glare keeps even less green
    limit = (rgb[..., 0] + rgb[..., 2]) / 2 if strict else np.maximum(rgb[..., 0], rgb[..., 2]) * (0.86 + 0.16 * a)
    thin = np.clip((0.6 - a) / 0.5, 0, 1)
    warm = rgb[..., 0] >= rgb[..., 2]
    limit = np.where(warm, np.minimum(limit, rgb[..., 0] * (1 - 0.3 * thin)), limit)
    spill = np.clip(rgb[..., 1] - limit, 0, 1)
    rgb[..., 1] = np.minimum(rgb[..., 1], limit)
    a = a * np.clip(1 - spill * 3, 0, 1)
    # Glare (brighter than the bare screen) is light: full brightness, never darkening what lies behind it
    glare = np.clip((frame.mean(axis=2) - bg.mean(axis=2) * 1.02) / 0.12, 0, 1) * np.clip((0.95 - a) / 0.3, 0, 1)
    if not strict:
        bright = rgb / np.maximum(rgb.max(axis=2, keepdims=True), 1e-3)
        rgb = rgb + (bright - rgb) * glare[..., None]
        rgb[..., 1] = np.minimum(rgb[..., 1], np.where(rgb[..., 0] >= rgb[..., 2], rgb[..., 0] * (1 - 0.3 * glare), 1))
    rgb[..., 1] = np.maximum(rgb[..., 1], np.minimum(rgb[..., 0], rgb[..., 2]) * 0.98)
    return np.dstack([rgb, a])


# --- Cut-off edges: extend instead of fade ---------------------------------------------------------------------------

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


def edge_ramp(h, w, edge, open_sides):
    """Fade towards the frame borders the effect never reaches (an extended side has none)."""
    ys, xs = np.arange(h, dtype=np.float32), np.arange(w, dtype=np.float32)
    t = np.ones((h, w), np.float32)
    for dist, side, axis in ((ys, "top", 0), (ys[::-1], "bottom", 0), (xs, "left", 1), (xs[::-1], "right", 1)):
        if side in open_sides:
            continue
        ramp = np.clip(dist / edge, 0, 1)
        t = np.minimum(t, ramp[:, None] if axis == 0 else ramp[None, :])
    return t * t * (3 - 2 * t)


class Extender:
    """Grows a frame past the sides where the effect was cut off. The strip along the edge is mirrored outwards, so
    the smoke carries on from the very pixels at the edge; with distance it blurs, thins and breaks up in a slowly
    drifting noise pattern (the same pattern every frame, so it moves with the smoke, not like static), and dissolves
    before the new edge."""

    def __init__(self, shape, sides, seed):
        self.h, self.w = shape
        self.pads = {}
        for side, cover in sides.items():
            dim = self.h if side in ("top", "bottom") else self.w
            self.pads[side] = int(dim * float(np.clip(0.14 + 0.55 * cover, 0.14, 0.42)))
        ph = self.h + self.pads.get("top", 0) + self.pads.get("bottom", 0)
        pw = self.w + self.pads.get("left", 0) + self.pads.get("right", 0)
        self.noise = noise(ph * 2, pw, seed, scales=(10, 26, 60))

    @property
    def offset(self):
        return self.pads.get("left", 0), self.pads.get("top", 0)

    def grow(self, f, side, pad, n):
        """Extend one side: rotate so the side is at the top, mirror the strip upwards, dissolve with distance."""
        rot = {"top": 0, "left": 3, "bottom": 2, "right": 1}[side]
        g = np.rot90(f, rot)
        nz = np.rot90(n, rot)[:pad, :g.shape[1]]
        strip = g[:pad][::-1].copy()                        # row pad-1 = the edge row, row 0 = farthest
        d = (pad - 1 - np.arange(pad, dtype=np.float32))[:, None] / pad   # 0 at the edge, 1 at the new border
        pm = strip[..., :3] * strip[..., 3:]
        a = strip[..., 3].copy()
        # Blur grows with distance: blend a sharp and a soft copy
        soft_pm = np.dstack([gaussian_filter(pm[..., c], pad * 0.12) for c in range(3)])
        soft_a = gaussian_filter(a, pad * 0.12)
        mix = np.clip(d * 1.3, 0, 1)[..., None]
        pm = pm * (1 - mix) + soft_pm * mix
        a = a * (1 - mix[..., 0]) + soft_a * mix[..., 0]
        # Thin out and break up: density falls with distance, holes open first where the noise is low
        breakup = np.clip((nz * 1.25 - d * 1.05 + 0.25) / 0.35, 0, 1)
        a = a * (1 - d) ** 1.4 * breakup
        rgb = pm / np.maximum(strip[..., 3:] * (1 - mix) + soft_a[..., None] * mix, 1e-4)
        ext = np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)]).astype(np.float32)
        g = np.concatenate([ext, g], axis=0)
        return np.rot90(g, -rot)

    def __call__(self, f, i):
        n = self.noise[i % self.noise.shape[0] // 2:][:self.noise.shape[0] // 2]   # drifts upwards over time
        out = f
        # Pad the noise to the growing frame as sides are added
        for side in ("top", "bottom", "left", "right"):
            if side in self.pads:
                nn = n
                if nn.shape[0] < out.shape[0] or nn.shape[1] < out.shape[1]:
                    nn = np.pad(nn, ((0, max(0, out.shape[0] - nn.shape[0])), (0, max(0, out.shape[1] - nn.shape[1]))),
                                mode="reflect")
                out = self.grow(out, side, self.pads[side], nn)
        return out


def dissipate(last, anchor_xy, count, wind=0.10, seed=7):
    """Frames of the smoke left in a clip's last frame breaking up: it drifts with the wind (more aloft), spreads and
    blurs, thins in soft patches and then tears apart in drifting noise until nothing is left. Not a fade: the smoke
    moves and breaks up like real smoke clearing."""
    from scipy.ndimage import map_coordinates
    h, w, _ = last.shape
    ax, ay = anchor_xy
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    height = np.clip((ay - yy) / max(ay, 1), 0, 1)
    big = noise(h * 2, w, seed, scales=(10, 26, 60))
    fine = noise(h * 2, w, seed + 1, scales=(4, 10))
    pm = last[..., :3] * last[..., 3:]
    a0 = last[..., 3]
    out = []
    for i in range(1, count + 1):
        t = i / count
        sx = xx - wind * w * t * (0.3 + 0.7 * height) - (xx - ax) * 0.25 * t * height
        sy = yy + 0.05 * h * t * (0.3 + height)
        coords = [sy, sx]
        pmi = np.dstack([map_coordinates(pm[..., c], coords, order=1, mode="constant") for c in range(3)])
        ai = map_coordinates(a0, coords, order=1, mode="constant")
        sigma = 0.6 + 4 * t
        pmi = np.dstack([gaussian_filter(pmi[..., c], sigma) for c in range(3)])
        ai = gaussian_filter(ai, sigma)
        off = int(t * h * 0.4)
        n = 0.75 * big[h - off:2 * h - off] + 0.25 * fine[h - off:2 * h - off]
        patch = np.clip(0.3 + 0.9 * n, 0, 1)
        tear = np.clip((n - (1.5 * t - 0.6)) / 0.35, 0, 1)
        rgb = pmi / np.maximum(ai, 1e-4)[..., None]
        ai = ai * (1 + (patch - 1) * min(1.0, 1.5 * t)) * tear * (1 - t) ** 1.1
        out.append(np.dstack([np.clip(rgb, 0, 1), np.clip(ai, 0, 1)]).astype(np.float32))
    return out


# --- Origins --------------------------------------------------------------------------------------------------------

def anchor(frames):
    """Centre of the first flash bright enough to stand out."""
    for f in frames[:12]:
        lum = f[..., :3].mean(axis=2) * f[..., 3]
        mask = lum > 0.85
        if mask.sum() > 20:
            ys, xs = np.nonzero(mask)
            return float(xs.mean()), float(ys.mean())
    return centre(frames)


def base(frames):
    """Foot of a fire or smoke column: the bottom of everything dense enough, centred on it."""
    dense = np.max([f[..., 3] for f in frames], axis=0) > 0.5
    ys, xs = np.nonzero(dense)
    bottom = ys.max()
    row = xs[ys > bottom - 0.1 * (bottom - ys.min())]
    return float(row.mean()), float(bottom)


def first(frames):
    for f in frames:
        ys, xs = np.nonzero(f[..., 3] > 0.3)
        if len(xs):
            return float(xs.mean()), float(ys.mean())
    return centre(frames)


def centre(frames):
    ys, xs = np.nonzero(np.max([f[..., 3] for f in frames], axis=0) > 0.3)
    return float(xs.mean()), float(ys.mean())


def flash_start(src, bg, lead=1):
    """First source frame with a bright flash (the blast itself), lead frames before it."""
    for i, f in enumerate(src):
        lum = f.mean(axis=2)
        if (lum > 0.88).sum() > f.shape[0] * f.shape[1] * 0.0015:
            return max(0, i - lead)
    return 0


def blast_start(src, lead=1):
    """Where the blast itself starts: the bright area passes 1% of the frame and stays there for 5 frames (a
    missile's motor glint or a glint on the jet it hits is smaller, or gone again at once). lead frames before it."""
    share = [(f.mean(axis=2) > 0.88).mean() for f in src]
    for i in range(len(share) - 5):
        if all(v > 0.01 for v in share[i:i + 5]):
            return max(0, i - lead)
    return 0


def erase_band(shape, lines):
    """0-1 weight of the pixels near any of the erase lines (soft edge), or None."""
    if not lines:
        return None
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    band = np.zeros((h, w), np.float32)
    for x0, y0, x1, y1, half in lines:
        dx, dy = x1 - x0, y1 - y0
        t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / float(dx * dx + dy * dy), 0, 1)
        d = np.hypot(xs - (x0 + t * dx), ys - (y0 + t * dy))
        band = np.maximum(band, np.clip((half * 1.5 - d) / (half * 0.5), 0, 1))
    return band


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


# --- Processing -----------------------------------------------------------------------------------------------------

def prepare(name, opts, sides=None):
    """Keyed, extended frames of one clip, before cropping. Returns (frames, meta)."""
    black = opts.get("bg") == "black"
    src, fps = read_clip(os.path.join(SRC, f"{name}.mp4"))
    parts = [len(src)]
    for more_name in opts.get("then", []):
        more, _ = read_clip(os.path.join(SRC, f"{more_name}.mp4"))
        src = np.concatenate([src, more[1:]])         # its first frame repeats the previous part's last one
        parts.append(len(more) - 1)
    bg = background(src, black)
    start = opts.get("start", 0)
    if start == "flash":
        cut0 = flash_start(src, bg, opts.get("lead", 1))
    elif start == "blast":
        cut0 = blast_start(src, opts.get("lead", 1))
    else:
        cut0 = int(round(start * fps))
    src = src[cut0:]
    parts[0] -= cut0
    if sides is None:
        sides = cropping(src, bg, black)
    n = len(src)
    loop = opts.get("loop", False)
    rate = opts.get("fps")
    auto = int(np.clip(round(parts[0] / fps * (rate or FPS_KEPT)), FRAMES_MIN, 120 if rate else FRAMES_MAX))
    if loop and rate:
        auto = int(round(auto * (1 - LOOP_BLEND)))
    frames = opts.get("frames", auto if (rate or not loop) else LOOP_FRAMES)
    count = int(frames / (1 - LOOP_BLEND)) if loop else frames
    if len(parts) > 1:
        rest = opts.get("then_frames", count)
        picks = np.concatenate([np.linspace(0, parts[0] - 1, count).round(),
                                np.linspace(parts[0], n - 1, rest).round()]).astype(int)
        slow = (count, int(round((n - parts[0]) / fps * 1000 / rest)))
        tick = int(round(parts[0] / fps * 1000 / count))
    else:
        picks = np.linspace(0, n - 1, count).round().astype(int)
        slow = None
        tick = int(round(n / fps * 1000 / count))
    short = min(src.shape[1:3])
    ramp = edge_ramp(*src.shape[1:3], EDGE * short / 360, sides)
    ext = Extender(src.shape[1:3], sides, seed=sum(map(ord, name))) if sides else None
    band = erase_band(src.shape[1:3], opts.get("erase", []))
    out = []
    for i, j in enumerate(picks):
        f = key_black(src[j]) if black else key(src[j], bg, opts.get("strict", False))
        f[..., 3] *= ramp
        if band is not None:
            grey = np.clip(1 - (f[..., :3].max(axis=2) - f[..., :3].min(axis=2)) / 0.15, 0, 1)
            f[..., 3] *= 1 - band * grey * (f[..., :3].max(axis=2) < 0.8)
        if ext:
            f = ext(f, i)
        out.append(f)
    if loop:
        out = loop_blend(out)
        tick = int(round(n / fps * 1000 / count))
    left = float((out[-1][..., 3] > 0.1).mean())
    warn = []
    if sides:
        warn.append("extended " + ", ".join(f"{k} {v:.0%}" for k, v in sides.items()))
    tail = 0
    ends_open = loop or opts.get("open_end") or (opts.get("group") and name.endswith("start"))
    if not ends_open and left > END_WARN:
        # Smoke still hanging when the clip stops: generate its break-up instead of cutting or fading it
        tail = int(round(min(TAIL_MAX, 1.2 + 6 * left) * 1000 / tick))
        warn.append(f"{left:.0%} still on screen at the end: {tail} frames of break-up added")
    return out, dict(name=name, fps=fps, short=short, tick=tick, slow=slow, sides=sides, warn=warn, tail=tail)


def finish(members, master, size, scale_mult=1.0):
    """Crop a group to everything any member ever shows, scale it, origin from the master. All share one box."""
    alive = None
    for frames, _ in members.values():
        m = np.max([f[..., 3] for f in frames], axis=0) > 0.02
        alive = m if alive is None else (alive | m)
    ys, xs = np.nonzero(alive)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    r = min(1.0, size / (x1 - x0), size / (y1 - y0))
    mframes, mopts = members[master][0], CLIPS[master]
    loop = mopts.get("loop", False)
    mode = mopts.get("anchor", "base" if loop else "flash")
    ax, ay = {"flash": anchor, "first": first, "base": base, "centre": centre}[mode](mframes)
    ax, ay = (ax - x0) * r, (ay - y0) * r
    results = {}
    for name, (frames, meta) in members.items():
        out = [np.clip(zoom(f[y0:y1, x0:x1], (r, r, 1), order=1), 0, 1) for f in frames]
        if meta["tail"]:
            dense = np.nonzero(np.max([f[..., 3] for f in out], axis=0) > 0.3)[0]
            out += dissipate(out[-1], (ax, max(dense.max() if len(dense) else ay, ay)), meta["tail"],
                             seed=sum(map(ord, name)))
        scale = SCREEN_PER_PX * 360 / meta["short"] * CLIPS[name].get("scale", 1.0) * scale_mult / r
        results[name] = (out, (ax, ay), meta["tick"], scale, meta)
    return results


def build_group(names):
    """Process one clip or one group of clips; returns {name: (frames, anchor, tick, scale, meta)}."""
    master = CLIPS[names[0]].get("group", names[0])
    first_opts = CLIPS[master]
    black = first_opts.get("bg") == "black"
    # A group shares the extended sides: the union of every member's cut-off edges
    sides = {}
    if len(names) > 1:
        for name in names:
            src, _ = read_clip(os.path.join(SRC, f"{name}.mp4"))
            for k, v in cropping(src, background(src, black), black).items():
                sides[k] = max(sides.get(k, 0), v)
    members = {}
    for name in names:
        members[name] = prepare(name, CLIPS[name], sides if len(names) > 1 else None)
    size = first_opts.get("size")
    if size is None:
        size = SIZE_SMALL if members[master][1]["short"] <= 360 else SIZE_BIG
    return finish(members, master, size)


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


def preview(name, frames, step=None):
    os.makedirs(PREVIEW, exist_ok=True)
    step = step or max(1, len(frames) // 10)
    pick = frames[::step]
    h, w, _ = pick[0].shape
    bg = np.zeros((h, w * len(pick), 3), np.float32) + np.array([0.36, 0.42, 0.25])
    for i, fr in enumerate(pick):
        a = fr[..., 3:4]
        bg[:, i * w:(i + 1) * w] = fr[..., :3] * a + bg[:, i * w:(i + 1) * w] * (1 - a)
    Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8)).save(os.path.join(PREVIEW, f"video-{name}.png"))


def job(names):
    results = build_group(names)
    lines = []
    for name in names:
        frames, anc, tick, scale, meta = results[name]
        save(name, frames, anc)
        if "--preview" in sys.argv:
            preview(name, frames)
        h, w = frames[0].shape[:2]
        msg = f"  {name}: {len(frames)} x {w}x{h}, tick {tick} ms, scale {scale:.3f}"
        if meta["slow"]:
            msg += f", continuation from frame {meta['slow'][0]} at {meta['slow'][1]} ms (VideoSlowFrom/VideoSlowTick)"
        if meta["warn"]:
            msg += "  [" + "; ".join(meta["warn"]) + "]"
        lines.append(msg)
    return names, lines, {n: (len(results[n][0]), results[n][2], results[n][3]) for n in names}


def groups():
    order, seen = [], {}
    for name, opts in CLIPS.items():
        g = opts.get("group")
        if g:
            if g not in seen:
                seen[g] = []
                order.append(seen[g])
            seen[g].append(name)
        else:
            order.append([name])
    # The master first in each group
    return [sorted(g, key=lambda n: n != CLIPS[n].get("group", n)) for g in order]


def sequence_info():
    """name -> (length, tick, scale) of the clips already in the sequences file."""
    info = {}
    if not os.path.exists(SEQUENCES):
        return info
    lines = open(SEQUENCES).read().split("\n")
    for i, l in enumerate(lines):
        if l.startswith("\t") and not l.startswith("\t\t") and l.endswith(":"):
            block = {x.strip().split(": ")[0]: x.strip().split(": ")[1] for x in lines[i + 1:i + 9] if ": " in x}
            if "Length" in block:
                info[l.strip()[:-1]] = (int(block["Length"]), int(block["Tick"]), float(block["Scale"]))
    return info


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()]
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 3
    todo = [g for g in groups() if not only or any(n in only for n in g)]
    known = sequence_info()
    with Pool(jobs) as pool:
        for names, lines, info in pool.imap_unordered(job, todo):
            for l in lines:
                print(l, flush=True)
            known.update(info)
    y = ["# Filmed effects keyed from Google Flow clips (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_video_fx.py - edit that script, not this file.", "", "pxvideofx:"]
    for name, opts in CLIPS.items():
        if name not in known:
            continue
        length, tick, scale = known[name]
        variants = [(name, False)] + ([(name + "-m", True)] if opts.get("mirror") else [])
        for seq, flip in variants:
            y += [f"\t{seq}:", f"\t\tFilename: ra|bits/hd/fx/video/{name}.png", "\t\tStart: 0", f"\t\tLength: {length}",
                  f"\t\tTick: {tick}", "\t\tOffset: 0,0", f"\t\tScale: {scale:.4f}", "\t\tZOffset: 512"]
            if flip:
                y.append("\t\tFlipX: true")
    # Water splashes are played by the stock CreateEffect warheads (image explosion), so they get names there too
    y += ["", "explosion:"]
    for alias, name in EXPLOSION_ALIASES.items():
        if name in known:
            length, tick, scale = known[name]
            y += [f"\t{alias}:", f"\t\tFilename: ra|bits/hd/fx/video/{name}.png", "\t\tStart: 0", f"\t\tLength: {length}",
                  f"\t\tTick: {tick}", "\t\tOffset: 0,0", f"\t\tScale: {scale * 0.7:.4f}", "\t\tZOffset: 0"]
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print(f"wrote {SEQUENCES}")


if __name__ == "__main__":
    main()
