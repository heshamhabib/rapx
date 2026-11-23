#!/usr/bin/env python3
"""
Video explosions (RedAlert Project X): turns AI-generated green-screen explosion clips into sprite sheets.

  python3 artsrc/fx/make_video_fx.py [--preview]

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
from scipy.ndimage import gaussian_filter, zoom

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
#   size     largest output frame side, for 720p clips that hold more detail
#   scale    in-game size multiplier for this clip
CLIPS = {
    "artillery-a": {},
    "artillery-b": {},
    "artillery-c": {"squash": 1.0, "size": 540},
    "cannon-a": {"squash": 1.0},
    "cannon-b": {"squash": 1.0},
    "dirt-a": {"squash": 1.0, "start": 2 / 24, "anchor": "first"},
    "bomb-a": {"squash": 1.0, "size": 540},
    "building-a": {"squash": 1.0, "size": 540, "start": 4 / 24},
    "vehicle-a": {"squash": 1.0},
    "flak-a": {"squash": 1.0},
    "fire-wreck-a": {"loop": True, "squash": 1.0, "size": 300},
    "fire-small-b": {"loop": True, "squash": 1.0, "size": 300},
    "fire-big-b": {"loop": True, "squash": 1.0, "size": 400, "shadow": 0.6},
    "smoke-column-a": {"loop": True, "squash": 1.0, "size": 440, "shadow": 0.3},
    "dust-a": {"squash": 1.0, "anchor": "centre", "shadow": 1.0, "strict": True},
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


def background(frames):
    """The screen colour: median of the clearly green pixels of the first frames."""
    px = frames[:4].reshape(-1, 3)
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
    limit = (rgb[..., 0] + rgb[..., 2]) / 2 if strict else np.maximum(rgb[..., 0], rgb[..., 2]) * 1.02
    spill = np.clip(rgb[..., 1] - limit, 0, 1)
    rgb[..., 1] = np.minimum(rgb[..., 1], limit)
    a = a * np.clip(1 - spill * 3, 0, 1)
    # Unmixing over-subtracts green on soft edges (the video's colour is stored at half resolution), which tints
    # them magenta: no pixel may be less green than both red and blue
    rgb[..., 1] = np.maximum(rgb[..., 1], np.minimum(rgb[..., 0], rgb[..., 2]) * 0.98)
    return np.dstack([rgb, a])


def edge_ramp(h, w, edge):
    y = np.minimum(np.arange(h), np.arange(h)[::-1])[:, None]
    x = np.minimum(np.arange(w), np.arange(w)[::-1])[None, :]
    d = np.minimum(np.broadcast_to(y, (h, w)), np.broadcast_to(x, (h, w))).astype(np.float32)
    t = np.clip(d / edge, 0, 1)
    return t * t * (3 - 2 * t)


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
    bg = background(src)
    src = src[int(round(opts.get("start", 0) * fps)):]
    n = len(src)
    short = min(src.shape[1:3])
    loop = opts.get("loop", False)
    count = int(FRAMES / (1 - LOOP_BLEND)) if loop else FRAMES
    picks = np.linspace(0, n - 1, count).round().astype(int)
    ramp = edge_ramp(*src.shape[1:3], EDGE * short / 360)
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
    scale = SCREEN_PER_PX * 360 / short * opts.get("scale", 1.0) / r

    tick = int(round(n / fps * 1000 / count))
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


def main():
    y = ["# Video explosions keyed from green-screen clips (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_video_fx.py - edit that script, not this file.", "", "pxvideofx:"]
    for name, opts in CLIPS.items():
        frames, anc, tick, scale = process(name, opts)
        save(name, frames, anc)
        if "--preview" in sys.argv:
            preview(name, frames)
        path = f"ra|bits/hd/fx/video/{name}.png"
        y += [f"\t{name}:", f"\t\tFilename: {path}", "\t\tStart: 0", f"\t\tLength: {len(frames)}",
              f"\t\tTick: {tick}", "\t\tOffset: 0,0", f"\t\tScale: {scale:.4f}", "\t\tZOffset: 512"]
    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print(f"wrote {SEQUENCES}")


if __name__ == "__main__":
    main()
