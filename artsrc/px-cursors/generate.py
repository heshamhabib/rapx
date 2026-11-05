#!/usr/bin/env python3
"""
Generates the RedAlert Project X mouse cursors (mods/rapx/uibits/px-cursors.png) and the
matching mods/rapx/cursors.yaml, styled after artsrc/px-cursors/reference.png:
red darts with a bevelled silver rim, neon red line icons, green guard / gold sell.

Every frame is drawn at SS x and downsampled for anti-aliasing. Coordinates below are in
1x cursor pixels inside an F x F frame. The PNG carries a FrameSize tEXt chunk so OpenRA's
PngSheet loader slices it into frames; cursors.yaml references them by Start/Length.

Run: python3 artsrc/px-cursors/generate.py
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from PIL.PngImagePlugin import PngInfo

F = 48          # design frame size in cursor units; all drawing coordinates below use these units
OUT = 64        # output frame size in pixels. The art is 2x density (metrics.yaml HighDensityCursors),
                # so a frame shows as OUT / 2 = 32 points on screen
SS = 4          # supersampling factor
N = F * SS
COLS = 16

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..", "..", "mods", "rapx")
FONT = "/System/Library/Fonts/Supplemental/Arial Black.ttf"

RED = (232, 36, 36)
RED_BRIGHT = (255, 96, 80)
RED_DARK = (120, 8, 10)
RED_CORE = (255, 200, 190)
GREEN = (60, 235, 80)
GREEN_CORE = (210, 255, 210)
CYAN = (60, 200, 255)
CYAN_CORE = (210, 245, 255)
GOLD_BRIGHT = (255, 226, 110)
GOLD_DARK = (190, 120, 20)
SILVER_LIGHT = (246, 246, 250)
SILVER_DARK = (92, 92, 100)
STEEL = (150, 150, 158)
OUTLINE = (22, 20, 22)


def P(v):
    return v * SS


def W(v):
    """Line width in SS px (PIL wants an int)."""
    return max(1, int(round(v * SS)))


# ---------------------------------------------------------------- primitives

def blank():
    return Image.new("RGBA", (N, N), (0, 0, 0, 0))


def mask(fn):
    m = Image.new("L", (N, N), 0)
    fn(ImageDraw.Draw(m))
    return m


def m_and(a, b):
    return Image.fromarray(np.minimum(np.array(a), np.array(b)))


def m_sub(a, b):
    return Image.fromarray(np.clip(np.array(a).astype(int) - np.array(b), 0, 255).astype(np.uint8))


def m_or(*ms):
    out = np.array(ms[0])
    for m in ms[1:]:
        out = np.maximum(out, np.array(m))
    return Image.fromarray(out)


def scale_alpha(m, a):
    return Image.fromarray(np.clip(np.array(m).astype(float) * a, 0, 255).astype(np.uint8))


def dilate(m, px):
    """Disk dilation by px (1x pixels)."""
    a = np.array(m)
    r = P(px)
    R = int(math.ceil(r))
    pad = np.pad(a, R)
    out = a.copy()
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            if dx * dx + dy * dy <= r * r:
                out = np.maximum(out, pad[R + dy:R + dy + N, R + dx:R + dx + N])
    return Image.fromarray(out)


def erode(m, px):
    return Image.fromarray(255 - np.array(dilate(Image.fromarray(255 - np.array(m)), px)))


def shift(m, dx, dy):
    return m.transform(m.size, Image.AFFINE, (1, 0, -P(dx), 0, 1, -P(dy)))


def solid(frame, m, color, alpha=1.0):
    layer = Image.new("RGBA", (N, N), color[:3] + (0,))
    layer.putalpha(scale_alpha(m, alpha))
    frame.alpha_composite(layer)


def gradient(frame, m, c1, c2, p1=None, p2=None):
    """Linear gradient c1 -> c2 from p1 to p2 (1x px); defaults to the mask's bbox diagonal."""
    if p1 is None:
        x0, y0, x1, y1 = m.getbbox()
        p1, p2 = (x0 / SS, y0 / SS), (x1 / SS, y1 / SS)
    ys, xs = np.mgrid[0:N, 0:N].astype(float) / SS
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t = ((xs - p1[0]) * dx + (ys - p1[1]) * dy) / max(dx * dx + dy * dy, 1e-6)
    t = np.clip(t, 0, 1)[..., None]
    rgb = np.array(c1, float) * (1 - t) + np.array(c2, float) * t
    layer = Image.fromarray(np.dstack([rgb, np.array(m)[..., None]]).astype(np.uint8))
    frame.alpha_composite(layer)


def glow(frame, m, color, radius=2.4, strength=1.0):
    b = m.filter(ImageFilter.GaussianBlur(P(radius)))
    solid(frame, b, color, strength)


def shadow(frame, m, dx=0.8, dy=1.2, alpha=0.7):
    solid(frame, shift(m, dx, dy).filter(ImageFilter.GaussianBlur(P(0.8))), (0, 0, 0), alpha)


def metal(frame, m, body, rim=1.4, glow_color=RED, glow_strength=0.9,
          rim_light=SILVER_LIGHT, rim_dark=SILVER_DARK):
    """Solid shape with a bevelled metal rim. body(frame, m) paints the inner fill."""
    outer = dilate(m, rim)
    edge = dilate(outer, 0.7)
    if glow_color:
        glow(frame, edge, glow_color, 2.4, glow_strength)
    shadow(frame, edge)
    solid(frame, edge, OUTLINE)
    gradient(frame, outer, rim_light, rim_dark)
    # inner shade line so the rim reads as a bevel, not a flat outline
    solid(frame, m_sub(dilate(m, 0.45), m), (40, 40, 46), 0.85)
    body(frame, m)


def red_body(frame, m):
    gradient(frame, m, RED_BRIGHT, RED_DARK)


def gold_body(frame, m):
    gradient(frame, m, GOLD_BRIGHT, GOLD_DARK)


def neon(frame, draw, width, color=RED, core=RED_CORE, filled=None, strength=1.2):
    """Glowing line art. draw(d, w) strokes with width w (SS px); filled(d) adds solid parts."""
    m = mask(lambda d: draw(d, W(width)))
    c = mask(lambda d: draw(d, W(width * 0.38)))
    if filled:
        f = mask(filled)
        m = m_or(m, f)
        c = m_or(c, erode(f, 1.0))
    solid(frame, dilate(m, 0.8), OUTLINE, 0.85)
    glow(frame, m, color, 2.6, strength)
    solid(frame, m, color)
    solid(frame, c, core, 0.85)


def desaturate(frame, dim=0.55):
    a = np.array(frame).astype(float)
    lum = (a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11) * dim
    a[..., 0] = lum * 1.05
    a[..., 1] = lum
    a[..., 2] = lum
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def rotated(fn, angle, cx=F / 2, cy=F / 2):
    """Draw a mask with fn, then rotate it (degrees, counter-clockwise) around (cx, cy)."""
    return mask(fn).rotate(angle, resample=Image.BICUBIC, center=(P(cx), P(cy)))


# ---------------------------------------------------------------- shapes

ARROW = [(0, 0), (0.22, 1.0), (0.40, 0.64), (0.86, 0.76)]


def arrow(frame, tip=(4, 4), h=27):
    pts = [(P(tip[0] + x * h), P(tip[1] + y * h)) for x, y in ARROW]
    m = mask(lambda d: d.polygon(pts, fill=255))
    lit = mask(lambda d: d.polygon([pts[0], pts[1], pts[2]], fill=255))

    def body(fr, mm):
        red_body(fr, mm)
        solid(fr, m_and(lit, mm), (255, 255, 255), 0.16)
        solid(fr, m_sub(mm, lit), (0, 0, 0), 0.22)

    metal(frame, m, body)


def ring(cx, cy, r):
    return lambda d, w: d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], outline=255, width=w)


def line(*pts):
    return lambda d, w: d.line([(P(x), P(y)) for x, y in pts], fill=255, width=w, joint="curve")


def combine(*fns):
    def draw(d, w):
        for f in fns:
            f(d, w)
    return draw


def dot(cx, cy, r):
    return lambda d: d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], fill=255)


def cannot(frame, cx=F / 2, cy=F / 2, r=13, width=3.2):
    k = r * 0.68
    neon(frame, combine(ring(cx, cy, r), line((cx - k, cy - k), (cx + k, cy + k))), width)


def crosshair(frame, cx=F / 2, cy=F / 2, r=11, gap=0.0, color=RED, core=RED_CORE, strength=1.2):
    o, i = r + 6 - gap, r - 5 + gap
    draw = combine(ring(cx, cy, r),
                   line((cx, cy - o), (cx, cy - i)), line((cx, cy + i), (cx, cy + o)),
                   line((cx - o, cy), (cx - i, cy)), line((cx + i, cy), (cx + o, cy)))
    neon(frame, draw, 2.2, color, core, filled=dot(cx, cy, 1.6), strength=strength)


def precision(frame, cx=F / 2, cy=F / 2):
    """Silver crosshair with a red centre (reference: PRECISION ATTACK)."""
    def bars(d):
        for a, b in (((0, -17), (0, -5)), ((0, 5), (0, 17)), ((-17, 0), (-5, 0)), ((5, 0), (17, 0))):
            d.line([(P(cx + a[0]), P(cy + a[1])), (P(cx + b[0]), P(cy + b[1]))], fill=255, width=W(2.2))
        d.arc([P(cx - 9), P(cy - 9), P(cx + 9), P(cy + 9)], 200, 250, fill=255, width=W(1.6))
        d.arc([P(cx - 9), P(cy - 9), P(cx + 9), P(cy + 9)], 20, 70, fill=255, width=W(1.6))
    m = mask(bars)
    metal(frame, m, lambda fr, mm: gradient(fr, mm, SILVER_LIGHT, STEEL), rim=0.5, glow_strength=0.5)
    neon(frame, lambda d, w: None, 1, filled=dot(cx, cy, 2.6))


def arrowhead_pts(cx, cy, size, angle):
    """Arrowhead pointing along angle (degrees, 0 = up, clockwise), tip at distance size from centre."""
    base = [(0, -size), (size * 0.8, size * 0.35), (0, 0), (-size * 0.8, size * 0.35)]
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    return [(P(cx + x * ca - y * sa), P(cy + x * sa + y * ca)) for x, y in base]


def arrowheads(frame, cx, cy, dist, size, angles, dim=False):
    pts_all = []
    for ang in angles:
        a = math.radians(ang)
        hx, hy = cx + math.sin(a) * dist, cy - math.cos(a) * dist
        pts_all.append(arrowhead_pts(hx, hy, size, ang))
    m = mask(lambda d: [d.polygon(p, fill=255) for p in pts_all])
    metal(frame, m, red_body, rim=1.2, glow_color=None if dim else RED)


def move(frame, push=0.0):
    cx = cy = F / 2
    d0 = 10 + push

    def cross(d):
        for a, b in (((0, -d0), (0, d0)), ((-d0, 0), (d0, 0))):
            d.line([(P(cx + a[0]), P(cy + a[1])), (P(cx + b[0]), P(cy + b[1]))], fill=255, width=W(2))
    metal(frame, mask(cross), lambda fr, mm: gradient(fr, mm, SILVER_LIGHT, STEEL), rim=0.6, glow_color=None)
    arrowheads(frame, cx, cy, d0 + 1, 6.5, (0, 90, 180, 270))
    metal(frame, dilate(mask(dot(cx, cy, 2.4)), 0), red_body, rim=1.0)


def guard(frame, cx=F / 2, cy=F / 2, r=14, color=GREEN, core=GREEN_CORE):
    box = [P(cx - r), P(cy - r), P(cx + r), P(cy + r)]

    def draw(d, w):
        for s in (200, 290, 20, 110):
            d.arc(box, s, s + 50, fill=255, width=w)
        for sx in (-1, 1):
            d.line([(P(cx - sx * 6), P(cy - 3.5)), (P(cx - sx * 2.5), P(cy)), (P(cx - sx * 6), P(cy + 3.5))],
                   fill=255, width=max(1, w - W(0.6)), joint="curve")
    neon(frame, draw, 2.8, color, core)


def wrench(frame, inlay=RED, cx=F / 2, cy=F / 2, scale=1.0):
    s = scale

    def shape(d):
        hx = cx - 9 * s
        d.ellipse([P(hx - 7 * s), P(cy - 7 * s), P(hx + 7 * s), P(cy + 7 * s)], fill=255)
        d.rounded_rectangle([P(hx), P(cy - 3.4 * s), P(cx + 15 * s), P(cy + 3.4 * s)], radius=P(3.4 * s), fill=255)
        # jaw opening
        d.rectangle([P(hx - 9 * s), P(cy - 2.6 * s), P(hx - 1 * s), P(cy + 2.6 * s)], fill=0)
    m = rotated(shape, -45)
    slot = rotated(lambda d: d.rounded_rectangle(
        [P(cx - 4 * s), P(cy - 1.4 * s), P(cx + 12.5 * s), P(cy + 1.4 * s)], radius=P(1.4 * s), fill=255), -45)

    def body(fr, mm):
        gradient(fr, mm, SILVER_LIGHT, SILVER_DARK)
        solid(fr, dilate(slot, 0.4), (30, 30, 34))
        gradient(fr, slot, tuple(min(255, c + 60) for c in inlay), tuple(c // 2 for c in inlay))
    metal(frame, m, body, rim=0.6, glow_color=inlay, glow_strength=0.6,
          rim_light=(70, 70, 76), rim_dark=(30, 30, 34))


def dollar(frame, cx=F / 2, cy=F / 2, size=34):
    font = ImageFont.truetype(FONT, P(size))
    m = mask(lambda d: d.text((P(cx), P(cy)), "$", font=font, fill=255, anchor="mm"))
    metal(frame, m, gold_body, rim=1.0, glow_color=(255, 190, 40), glow_strength=0.8,
          rim_light=(120, 80, 10), rim_dark=(60, 36, 4))


def radiation(frame, cx=F / 2, cy=F / 2, r=14):
    def blades(d):
        for s in (-120, 0, 120):
            d.pieslice([P(cx - r * 0.78), P(cy - r * 0.78), P(cx + r * 0.78), P(cy + r * 0.78)],
                       s - 90 - 30, s - 90 + 30, fill=255)
        d.ellipse([P(cx - 3.6), P(cy - 3.6), P(cx + 3.6), P(cy + 3.6)], fill=0)
        d.ellipse([P(cx - 2), P(cy - 2), P(cx + 2), P(cy + 2)], fill=255)
    neon(frame, ring(cx, cy, r), 2.6, filled=blades)


def gear(frame, cx=F / 2, cy=F / 2, r=12):
    def shape(d):
        d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], fill=255)
        for k in range(8):
            a = math.radians(k * 45)
            pts = []
            for ox, oy in ((-2.6, r - 1), (2.6, r - 1), (2.0, r + 3.6), (-2.0, r + 3.6)):
                pts.append((P(cx + ox * math.cos(a) - oy * math.sin(a)), P(cy + ox * math.sin(a) + oy * math.cos(a))))
            d.polygon(pts, fill=255)
        d.ellipse([P(cx - r * 0.55), P(cy - r * 0.55), P(cx + r * 0.55), P(cy + r * 0.55)], fill=0)
    metal(frame, mask(shape), lambda fr, mm: gradient(fr, mm, SILVER_LIGHT, SILVER_DARK), rim=0.5,
          rim_light=(70, 70, 76), rim_dark=(30, 30, 34), glow_strength=0.5)
    neon(frame, ring(cx, cy, r * 0.55 + 0.6), 1.8)


def crystals(frame, cx, cy, s=1.0):
    shards = [
        [(0, -11), (3.5, -4), (2, 6), (-2, 6), (-3.5, -4)],
        [(-7, -5), (-3.2, 0), (-2.6, 6), (-7.5, 6), (-9.5, 0)],
        [(7, -6), (9.8, 0), (8, 6), (3, 6), (3.6, -1)],
    ]
    polys = [[(P(cx + x * s), P(cy + y * s)) for x, y in sh] for sh in shards]
    m = mask(lambda d: [d.polygon(p, fill=255) for p in polys])
    lit = mask(lambda d: [d.polygon([p[0], p[1], p[2]], fill=255) for p in polys])

    def body(fr, mm):
        red_body(fr, mm)
        solid(fr, m_and(lit, mm), (255, 255, 255), 0.2)
    metal(frame, m, body, rim=0.7, rim_light=(255, 150, 140), rim_dark=(90, 10, 10))


def block_arrow(frame, cx, cy, down=True, s=1.0):
    pts = [(-2.6, -8), (2.6, -8), (2.6, 0), (7, 0), (0, 8), (-7, 0), (-2.6, 0)]
    sign = 1 if down else -1
    poly = [(P(cx + x * s), P(cy + sign * y * s)) for x, y in pts]
    metal(frame, mask(lambda d: d.polygon(poly, fill=255)), red_body, rim=0.9)


def plus(frame, cx, cy, minus=False, color=RED):
    def shape(d):
        d.rectangle([P(cx - 7), P(cy - 2.2), P(cx + 7), P(cy + 2.2)], fill=255)
        if not minus:
            d.rectangle([P(cx - 2.2), P(cy - 7), P(cx + 2.2), P(cy + 7)], fill=255)
    bright = tuple(min(255, c + 70) for c in color)
    dark = tuple(c // 2 for c in color)
    metal(frame, mask(shape), lambda fr, mm: gradient(fr, mm, bright, dark), rim=0.8, glow_color=color)


def flag(frame, cx, cy):
    def draw(d, w):
        d.ellipse([P(cx - 8), P(cy + 4), P(cx + 8), P(cy + 10)], outline=255, width=w)
        d.line([(P(cx), P(cy + 7)), (P(cx), P(cy - 9))], fill=255, width=w)
    neon(frame, draw, 1.8, filled=lambda d: d.polygon(
        [(P(cx), P(cy - 9)), (P(cx + 9), P(cy - 6)), (P(cx), P(cy - 2.5))], fill=255))


def eye(frame, cx, cy, color=RED, core=RED_CORE):
    def draw(d, w):
        # almond: upper lid is an arc of a circle centred below, lower lid one centred above
        R, o = 13, 8.5
        d.arc([P(cx - R), P(cy + o - R), P(cx + R), P(cy + o + R)], 222, 318, fill=255, width=w)
        d.arc([P(cx - R), P(cy - o - R), P(cx + R), P(cy - o + R)], 42, 138, fill=255, width=w)
    neon(frame, draw, 1.8, color, core, filled=dot(cx, cy, 3.4))


def star(frame, cx, cy, r=10):
    pts = []
    for k in range(16):
        a = math.radians(k * 22.5)
        rr = r if k % 4 == 0 else (r * 0.55 if k % 2 == 0 else r * 0.3)
        pts.append((P(cx + math.sin(a) * rr), P(cy - math.cos(a) * rr)))
    m = m_sub(mask(lambda d: d.polygon(pts, fill=255)), mask(dot(cx, cy, 2.6)))
    metal(frame, m, red_body, rim=0.7)
    neon(frame, lambda d, w: None, 1, filled=dot(cx, cy, 1.6))


def power(frame, cx, cy, r=7.5):
    def draw(d, w):
        d.arc([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], -60, 240, fill=255, width=w)
        d.line([(P(cx), P(cy - r - 1.5)), (P(cx), P(cy - 1))], fill=255, width=w)
    neon(frame, draw, 2.2)


def landing(frame, cx=F / 2, cy=F / 2, color=GREEN, core=GREEN_CORE, pulse=0.0):
    def draw(d, w):
        for rx, ry in ((15 + pulse, 6 + pulse * 0.4), (8 + pulse * 0.6, 3.2 + pulse * 0.25)):
            d.ellipse([P(cx - rx), P(cy + 8 - ry), P(cx + rx), P(cy + 8 + ry)], outline=255, width=w)
    neon(frame, draw, 1.8, color, core, filled=lambda d: d.polygon(
        [(P(cx - 7), P(cy - 14)), (P(cx), P(cy - 10)), (P(cx + 7), P(cy - 14)), (P(cx), P(cy + 4))], fill=255))


# ---------------------------------------------------------------- cursor set

BADGE = (33, 33)   # centre of the bottom-right badge on arrow cursors
TIP = (4, 4)       # arrow tip = hotspot of arrow cursors
CENTRE = (F // 2, F // 2)


def with_arrow(badge, h=24):
    def fn():
        fr = blank()
        arrow(fr, TIP, h)
        badge(fr)
        return fr
    return fn


def single(draw):
    def fn():
        fr = blank()
        draw(fr)
        return fr
    return fn


def blocked(draw):
    """Greyed-out icon with a small red 'cannot' badge."""
    def fn():
        fr = desaturate(draw())
        cannot(fr, 35, 35, 7, 2.2)
        return fr
    return fn


def scroll_frame(angle, dim):
    def fn():
        fr = blank()
        a = math.radians(angle)
        cx, cy = F / 2 - math.sin(a) * 2, F / 2 + math.cos(a) * 2
        arrowheads(fr, cx, cy, 6, 13, (angle,), dim)
        return desaturate(fr, 0.7) if dim else fr
    return fn


def scroll_hotspot(angle):
    a = math.radians(angle)
    return (round(F / 2 + math.sin(a) * 14), round(F / 2 - math.cos(a) * 14))


# Each entry: frames (list of zero-arg painters), hotspot pixel in frame, cursor names.
CURSORS = []


def add(names, painters, hotspot):
    CURSORS.append((names, painters, hotspot))


add(["default", "default-minimap", "joystick-all"], [single(lambda f: arrow(f, TIP, 27))], TIP)
add(["select"], [with_arrow(lambda f, p=p: neon(f, ring(BADGE[0], BADGE[1], 6 + p), 2.2, strength=1.0 + p * 0.4))
                 for p in (0, 0.6, 1.2, 0.6)], TIP)
add(["move", "move-minimap", "move-rough"], [single(lambda f, p=p: move(f, p)) for p in (0, 0.7, 1.4, 0.7)], CENTRE)
add(["move-blocked", "move-blocked-minimap", "generic-blocked", "generic-blocked-minimap",
     "enter-blocked", "enter-blocked-minimap", "attackmove-blocked", "attackmove-blocked-minimap",
     "assaultmove-blocked", "assaultmove-blocked-minimap", "powerdown-blocked"],
    [single(cannot)], CENTRE)
add(["attack", "attack-minimap"], [single(lambda f, g=g: crosshair(f, gap=g, strength=1.0 + g * 0.3))
                                    for g in (0, 0.8, 1.6, 0.8)], CENTRE)
add(["attackoutsiderange", "attackoutsiderange-minimap", "c4", "c4-minimap"], [single(precision)], CENTRE)
add(["harvest", "harvest-minimap"], [with_arrow(lambda f: crystals(f, BADGE[0], BADGE[1] + 1, 1.05))], TIP)
add(["enter", "enter-minimap"], [with_arrow(lambda f: block_arrow(f, BADGE[0], BADGE[1], True))], TIP)
add(["guard", "guard-minimap"], [single(guard)], CENTRE)
add(["capture", "capture-minimap"], [with_arrow(lambda f: flag(f, BADGE[0], BADGE[1] - 1))], TIP)
add(["heal", "heal-minimap"], [with_arrow(lambda f: plus(f, BADGE[0], BADGE[1], color=(40, 200, 70)))], TIP)
add(["ability", "ability-minimap"], [with_arrow(lambda f: star(f, BADGE[0], BADGE[1]))], TIP)
add(["deploy"], [single(gear)], CENTRE)
add(["deploy-blocked"], [blocked(single(gear))], CENTRE)
add(["repair"], [single(wrench)], CENTRE)
add(["repair-blocked"], [blocked(single(wrench))], CENTRE)
add(["goldwrench"], [single(lambda f: wrench(f, inlay=(255, 190, 40)))], CENTRE)
add(["goldwrench-blocked"], [blocked(single(lambda f: wrench(f, inlay=(255, 190, 40))))], CENTRE)
add(["sell", "sell2"], [single(dollar)], CENTRE)
add(["sell-blocked"], [blocked(single(dollar))], CENTRE)
add(["nuke"], [single(lambda f, r=r: radiation(f, r=r)) for r in (14, 14.6, 15.2, 14.6)], CENTRE)
add(["chrono-select"], [with_arrow(lambda f: eye(f, BADGE[0], BADGE[1] + 1, CYAN, CYAN_CORE))], TIP)
add(["chrono-target"], [single(lambda f, p=p: landing(f, color=CYAN, core=CYAN_CORE, pulse=p)) for p in (0, 1, 2, 1)],
    (F // 2, F // 2 + 8))
add(["powerdown"], [with_arrow(lambda f: power(f, BADGE[0], BADGE[1]))], TIP)
add(["attackmove", "attackmove-minimap"], [with_arrow(lambda f: crosshair(f, BADGE[0], BADGE[1], 6, strength=1.0))], TIP)
add(["assaultmove", "assaultmove-minimap"],
    [with_arrow(lambda f: crosshair(f, BADGE[0], BADGE[1], 6, color=(255, 150, 30), core=(255, 230, 190)))], TIP)

SCROLL = [("t", 0), ("tr", 45), ("r", 90), ("br", 135), ("b", 180), ("bl", 225), ("l", 270), ("tl", 315)]
for name, ang in SCROLL:
    add(["scroll-" + name], [scroll_frame(ang, False)], scroll_hotspot(ang))
    add(["scroll-%s-blocked" % name, "joystick-%s-blocked" % name], [scroll_frame(ang, True)], scroll_hotspot(ang))


# ---------------------------------------------------------------- output

def finish(frame):
    return frame.convert("RGBa").resize((OUT, OUT), Image.LANCZOS).convert("RGBA")


def main():
    frames = []
    yaml = ["# Generated by artsrc/px-cursors/generate.py - do not edit by hand.", "Cursors:", "\tpx-cursors.png:"]
    for names, painters, (hx, hy) in CURSORS:
        start = len(frames)
        frames.extend(finish(p()) for p in painters)
        for name in names:
            yaml.append("\t\t%s:" % name)
            yaml.append("\t\t\tStart: %d" % start)
            if len(painters) > 1:
                yaml.append("\t\t\tLength: %d" % len(painters))
            # OpenRA hotspots are relative to the frame centre, in output pixels
            ox, oy = round((hx - F / 2) * OUT / F), round((hy - F / 2) * OUT / F)
            if ox:
                yaml.append("\t\t\tX: %d" % ox)
            if oy:
                yaml.append("\t\t\tY: %d" % oy)

    rows = (len(frames) + COLS - 1) // COLS
    sheet = Image.new("RGBA", (COLS * OUT, rows * OUT), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        sheet.paste(fr, (i % COLS * OUT, i // COLS * OUT))

    info = PngInfo()
    info.add_text("FrameSize", "%d,%d" % (OUT, OUT))
    info.add_text("FrameAmount", str(len(frames)))
    sheet.save(os.path.join(MOD, "uibits", "px-cursors.png"), pnginfo=info)
    with open(os.path.join(MOD, "cursors.yaml"), "w") as f:
        f.write("\n".join(yaml) + "\n")

    # Preview on a terrain-ish background, 2x, for eyeballing.
    pv = Image.new("RGBA", sheet.size, (70, 78, 52, 255))
    pv.alpha_composite(sheet)
    pv.save(os.path.join(HERE, "preview.png"))
    print("%d frames, %d cursors" % (len(frames), sum(len(c[0]) for c in CURSORS)))


if __name__ == "__main__":
    main()
