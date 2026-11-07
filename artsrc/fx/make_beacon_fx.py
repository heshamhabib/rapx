#!/usr/bin/env python3
"""
HD support-power beacons (RedAlert Project X, IDEA-30): the marker shown over a nuke, paradrop, parabomb or spy-plane
target and over player-placed beacons.

  python3 artsrc/fx/make_beacon_fx.py [--preview]

Writes mods/rapx/bits/hd/fx/beacon/*.png and mods/rapx/sequences/hd-beacon.yaml, which overrides the classic `beacon`
image (the engine's Beacon effect draws it):
  circles   lock-on: rings and brackets close in on the target and lock (played once, holds the last frame)
  pulse     looping reticle: turning tick ring, a pulse running outwards, glowing centre (BeaconSequence in the rules)
  arrow     glowing double chevron (the engine bobs it up and down)
  atomicon / pinficon / pbmbicon / camicon   posters in the HUD style: gunmetal glass panel, steel bevel, accent
            corner brackets, hazard band, glowing emblem (game-icons.net, CC BY 3.0, artsrc/px-sidebar/icons)
  clock     countdown overlay for the posters: the emblem disc darkens as a sweep and a gold arc runs round it
--preview writes artsrc/fx/preview/beacon-*.png.
"""
import io
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "fx", "beacon")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-beacon.yaml")
ICONS = os.path.join(ROOT, "artsrc", "px-sidebar", "icons")
FONT = os.path.join(ROOT, "mods", "rapx", "fonts")
PREVIEW = os.path.join(HERE, "preview")
D = 3            # sprite pixels per world pixel
SS = 4           # supersampling while drawing
SQUASH = 0.77    # ground plane foreshortening at the 50 degree camera

# HUD colours (artsrc/px-sidebar/generate.py)
RED = (226, 38, 38)
RED_BRIGHT = (255, 106, 85)
GOLD = (255, 209, 102)
STEEL = (120, 122, 132)

# poster -> (emblem svg, label, accent colour)
POSTERS = {
    "atomicon": ("radioactive", "NUCLEAR STRIKE", (255, 196, 40)),
    "pinficon": ("parachute", "AIRBORNE", (90, 200, 255)),
    "pbmbicon": ("falling-bomb", "AIR STRIKE", (255, 120, 50)),
    "camicon": ("eye", "RECON", (110, 235, 140)),
}
PW, PH = 62, 52   # poster size in world pixels


def font(size):
    for name in ("Oswald-SemiBold.ttf", "Oswald-Bold.ttf", "Roboto-Bold.ttf"):
        path = os.path.join(FONT, name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    files = [f for f in os.listdir(FONT) if f.lower().endswith((".ttf", ".otf"))]
    bold = [f for f in files if "bold" in f.lower()] or files
    return ImageFont.truetype(os.path.join(FONT, sorted(bold)[0]), size)


def glyph(name, size):
    """White icon mask (the SVGs are white on a black square)."""
    png = subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), os.path.join(ICONS, name + ".svg")],
                         check=True, capture_output=True).stdout
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    rgb = np.asarray(im).astype(np.float32) / 255
    mask = rgb[..., :3].mean(-1) * rgb[..., 3]
    return Image.fromarray((mask * 255).astype(np.uint8))


def solid(size, color, mask):
    layer = Image.new("RGBA", size, (*color, 255))
    layer.putalpha(mask)
    return layer


def glow(mask, color, radius, strength=1.0):
    m = mask.filter(ImageFilter.GaussianBlur(radius))
    m = m.point(lambda v: min(255, int(v * strength)))
    return solid(mask.size, color, m)


def down(im):
    return im.resize((im.width // SS, im.height // SS), Image.LANCZOS)


def chamfer(w, h, c, inset=0):
    i = inset
    return [(i + c, i), (w - 1 - i - c, i), (w - 1 - i, i + c), (w - 1 - i, h - 1 - i - c),
            (w - 1 - i - c, h - 1 - i), (i + c, h - 1 - i), (i, h - 1 - i - c), (i, i + c)]


def poster(name):
    svg, label, accent = POSTERS[name]
    pad = 6 * D * SS                                   # room for the outer glow
    w, h = PW * D * SS + 2 * pad, PH * D * SS + 2 * pad
    pw, ph = PW * D * SS, PH * D * SS
    c = 7 * D * SS
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def at(points):
        return [(x + pad, y + pad) for x, y in points]

    # outer accent glow
    shape = Image.new("L", (w, h), 0)
    ImageDraw.Draw(shape).polygon(at(chamfer(pw, ph, c)), fill=255)
    im.alpha_composite(glow(shape, accent, 5 * D * SS, 0.55))

    # gunmetal glass panel with a vertical gradient
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = np.linspace(0, 1, ph)[:, None]
    top, bottom = np.array([40, 41, 48]), np.array([11, 11, 14])
    col = (top * (1 - grad) + bottom * grad).astype(np.uint8)
    body = Image.fromarray(np.repeat(col[:, None, :], pw, 1).reshape(ph, pw, 3)).convert("RGBA")
    body.putalpha(240)
    panel.paste(body, (pad, pad))
    inner = Image.new("L", (w, h), 0)
    ImageDraw.Draw(inner).polygon(at(chamfer(pw, ph, c)), fill=255)
    panel.putalpha(Image.fromarray(np.minimum(np.asarray(panel.getchannel("A")), np.asarray(inner))))
    im.alpha_composite(panel)

    # header: accent bar with the label, hazard band at the bottom
    hh = int(ph * 0.2)
    head = Image.new("L", (w, h), 0)
    ImageDraw.Draw(head).polygon(at([(c, 0), (pw - 1 - c, 0), (pw - 1, c), (pw - 1, hh), (0, hh), (0, c)]), fill=255)
    hl = Image.new("RGBA", (w, h), (*[int(v * 0.32) for v in accent], 255))
    hl.putalpha(head.point(lambda v: v * 0.9))
    im.alpha_composite(hl)
    band_y = ph - int(ph * 0.1)
    stripes = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(stripes)
    step = 6 * D * SS
    for x in range(-ph, pw + ph, step):
        sd.polygon(at([(x, band_y), (x + step // 2, band_y), (x + step // 2 - (ph - band_y), ph), (x - (ph - band_y), ph)]),
                   fill=255)
    clip = Image.new("L", (w, h), 0)
    ImageDraw.Draw(clip).polygon(at(chamfer(pw, ph, c, 2 * SS)), fill=255)
    band = Image.new("L", (w, h), 0)
    ImageDraw.Draw(band).rectangle([pad, pad + band_y, pad + pw, pad + ph], fill=255)
    stripe_mask = Image.fromarray((np.asarray(stripes, np.float32) * np.asarray(clip) * np.asarray(band) / 255 / 255 * 0.85)
                                  .astype(np.uint8))
    im.alpha_composite(solid((w, h), accent, stripe_mask))

    f = font(int(hh * 0.62))
    d = ImageDraw.Draw(im)
    tw = d.textlength(label, font=f)
    tmask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(tmask).text((pad + (pw - tw) / 2, pad + hh * 0.18), label, font=f, fill=255)
    im.alpha_composite(glow(tmask, accent, 2 * SS, 1.2))
    im.alpha_composite(solid((w, h), (255, 246, 230), tmask))

    # emblem disc: dark well, accent ring, glowing icon
    cx, cy = pad + pw / 2, pad + hh + (band_y - hh) / 2
    r = (band_y - hh) * 0.42
    disc = Image.new("L", (w, h), 0)
    ImageDraw.Draw(disc).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    well = np.clip(1 - rr, 0, 1)
    tint = np.array(accent, np.float32)
    rgb = (np.array([8, 8, 10], np.float32) * (1 - well[..., None] ** 2) + tint * 0.28 * well[..., None] ** 2)
    well_im = Image.fromarray(np.dstack([rgb, np.asarray(disc, np.float32)]).astype(np.uint8))
    im.alpha_composite(well_im)
    ring = Image.new("L", (w, h), 0)
    ImageDraw.Draw(ring).ellipse([cx - r, cy - r, cx + r, cy + r], outline=255, width=int(1.2 * D * SS))
    im.alpha_composite(glow(ring, accent, 2 * SS, 1.5))
    im.alpha_composite(solid((w, h), tuple(min(255, int(v * 1.1) + 30) for v in accent), ring))
    size = int(r * 1.45)
    g = glyph(svg, size)
    gm = Image.new("L", (w, h), 0)
    gm.paste(g, (int(cx - size / 2), int(cy - size / 2)))
    im.alpha_composite(glow(gm, accent, 4 * SS, 1.6))
    im.alpha_composite(solid((w, h), tuple(min(255, v + 90) for v in accent), gm))
    hot = gm.filter(ImageFilter.MinFilter(3)).point(lambda v: v * 0.55)
    im.alpha_composite(solid((w, h), (255, 255, 245), hot))

    # steel bevel and accent corner brackets
    d = ImageDraw.Draw(im)
    d.polygon(at(chamfer(pw, ph, c)), outline=(*STEEL, 255), width=int(1.0 * D * SS))
    d.polygon(at(chamfer(pw, ph, c, int(1.3 * D * SS))), outline=(20, 20, 24, 255), width=int(0.5 * D * SS))
    br = Image.new("L", (w, h), 0)
    bd = ImageDraw.Draw(br)
    L, t = 9 * D * SS, int(1.3 * D * SS)
    for (x0, y0, sx, sy) in ((0, 0, 1, 1), (pw - 1, 0, -1, 1), (0, ph - 1, 1, -1), (pw - 1, ph - 1, -1, -1)):
        bd.line([at([(x0 + sx * c, y0)])[0], at([(x0 + sx * (c + L), y0)])[0]], fill=255, width=t)
        bd.line([at([(x0, y0 + sy * c)])[0], at([(x0, y0 + sy * (c + L * 0.7))])[0]], fill=255, width=t)
        bd.line([at([(x0 + sx * c, y0)])[0], at([(x0, y0 + sy * c)])[0]], fill=255, width=t)
    im.alpha_composite(glow(br, accent, 2 * SS, 1.4))
    im.alpha_composite(solid((w, h), tuple(min(255, v + 60) for v in accent), br))

    # scanlines and a glass sheen across the top
    sc = np.zeros((h, w), np.float32)
    sc[::3 * SS, :] = 1
    sc = np.asarray(inner, np.float32) / 255 * sc * 0.07
    im.alpha_composite(Image.fromarray(np.dstack([np.full((h, w, 3), 255, np.float32), sc * 255]).astype(np.uint8)))
    sheen = np.clip(1 - (yy - pad) / (ph * 0.55) - (xx - pad) / (pw * 3), 0, 1) ** 2 * 0.12
    sheen *= np.asarray(inner, np.float32) / 255
    im.alpha_composite(Image.fromarray(np.dstack([np.full((h, w, 3), 255, np.float32), sheen * 255]).astype(np.uint8)))
    return down(im), (cx, cy, r, pad, w, h)


def clock(geom, frames=48):
    """Countdown overlay matching the poster's emblem disc."""
    cx, cy, r, pad, w, h = geom
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = (np.degrees(np.arctan2(xx - cx, -(yy - cy))) + 360) % 360      # clockwise from 12 o'clock
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    out = []
    for i in range(frames):
        # full a little before the end: the engine only shows the last frame at the very moment of impact
        p = min(1.0, i / ((frames - 1) * 0.92))
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        # time still to run: darkened sweep over the disc
        dark = ((ang >= p * 360) & (rr < r * 0.98)).astype(np.float32) * 0.5
        im.alpha_composite(Image.fromarray(np.dstack([np.zeros((h, w, 3)), dark * 255]).astype(np.uint8)))
        # elapsed: gold arc round the disc with a bright head
        arc = Image.new("L", (w, h), 0)
        R = r + 2.2 * D * SS
        if p > 0:
            ImageDraw.Draw(arc).arc([cx - R, cy - R, cx + R, cy + R], -90, -90 + p * 360, fill=255, width=int(1.4 * D * SS))
            hx, hy = cx + R * np.sin(np.radians(p * 360)), cy - R * np.cos(np.radians(p * 360))
            ImageDraw.Draw(arc).ellipse([hx - 2 * D * SS, hy - 2 * D * SS, hx + 2 * D * SS, hy + 2 * D * SS], fill=255)
        im.alpha_composite(glow(arc, GOLD, 3 * SS, 1.6))
        im.alpha_composite(solid((w, h), (255, 238, 190), arc))
        out.append(down(im))
    return out


def arrow():
    w, h = 22 * D * SS, 30 * D * SS
    pad = 4 * D * SS
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    shape = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(shape)
    for k, y0 in enumerate((0, 0.42)):
        top = pad + h * y0
        th = h * 0.5
        d.polygon([(pad, top), (pad + w / 2, top + th * 0.62), (pad + w, top), (pad + w, top + th * 0.38),
                   (pad + w / 2, top + th), (pad, top + th * 0.38)], fill=255 if k else 200)
    im.alpha_composite(glow(shape, RED, 3 * D * SS, 1.3))
    # metallic body: bright top edge fading into the accent
    yy = np.linspace(0, 1, im.height)[:, None, None]
    body = np.array(RED_BRIGHT, np.float32) * (1 - yy) * 0.3 + np.array([255, 236, 210], np.float32) * (1 - yy) * 0.7 + \
        np.array(RED, np.float32) * yy
    body = np.broadcast_to(body, (im.height, im.width, 3))
    im.alpha_composite(Image.fromarray(np.dstack([body, np.asarray(shape, np.float32)]).astype(np.uint8)))
    edge = shape.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    im.alpha_composite(solid(im.size, (255, 250, 240), edge.point(lambda v: v * 0.6)))
    return down(im)


def reticle(radius, rot, brackets, pulse, alpha, w):
    """Top-down reticle (radius in world px) drawn into a w x w world-px canvas, then squashed for the camera."""
    S = w * D * SS
    c = S / 2
    R = radius * D * SS
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    lw = int(1.7 * D * SS)
    # outer tick ring
    for k in range(36):
        a = np.radians(rot + k * 10)
        long = k % 9 == 0
        r0, r1 = R * (0.86 if long else 0.92), R
        d.line([(c + r0 * np.sin(a), c - r0 * np.cos(a)), (c + r1 * np.sin(a), c - r1 * np.cos(a))],
               fill=int(255 * alpha), width=lw if long else max(1, lw // 2))
    # dashed inner ring, counter-rotating
    for k in range(12):
        a0 = -rot * 1.6 + k * 30
        d.arc([c - R * 0.66, c - R * 0.66, c + R * 0.66, c + R * 0.66], a0, a0 + 18, fill=int(200 * alpha), width=lw)
    # corner brackets
    b = R * brackets
    L = R * 0.28
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        x, y = c + sx * b * 0.72, c + sy * b * 0.72
        d.line([(x, y), (x - sx * L, y)], fill=int(255 * alpha), width=lw)
        d.line([(x, y), (x, y - sy * L)], fill=int(255 * alpha), width=lw)
    # centre: cross and dot
    d.ellipse([c - R * 0.06, c - R * 0.06, c + R * 0.06, c + R * 0.06], fill=int(255 * alpha))
    for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([(c + sx * R * 0.14, c + sy * R * 0.14), (c + sx * R * 0.32, c + sy * R * 0.32)], fill=int(230 * alpha), width=lw)
    if pulse is not None:
        pr = R * pulse
        d.ellipse([c - pr, c - pr, c + pr, c + pr], outline=int(255 * alpha * (1 - pulse) ** 1.2), width=lw * 2)
    im = im.resize((S, int(S * SQUASH)), Image.LANCZOS)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(glow(im, RED, 3 * SS, 1.3))
    out.alpha_composite(solid(im.size, (255, 120, 95), im))
    core = im.point(lambda v: v * 0.45)
    out.alpha_composite(solid(im.size, (255, 236, 200), core))
    return down(out)


def save(name, frames):
    w, h = frames[0].size
    cols = min(len(frames), max(1, 4096 // w))
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        sheet.paste(fr, ((i % cols) * w, (i // cols) * h))
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(len(frames)))
    sheet.save(os.path.join(OUT, name + ".png"), pnginfo=info, optimize=True)
    print(f"  {name}: {len(frames)} frames {w}x{h}")


def seq(name, file, length, offset="0,0", extra=()):
    path = f"ra|bits/hd/fx/beacon/{file}.png"
    lines = [f"\t{name}:", f"\t\tFilename: {path}", "\t\tTilesetFilenames:"]
    lines += [f"\t\t\t{t}: {path}" for t in ("TEMPERAT", "SNOW", "DESERT", "INTERIOR")]
    lines += ["\t\tStart: 0", f"\t\tLength: {length}", f"\t\tOffset: {offset}", f"\t\tScale: {1 / D:.4f}"]
    return lines + [f"\t\t{e}" for e in extra]


def preview(name, frames):
    os.makedirs(PREVIEW, exist_ok=True)
    w, h = frames[0].size
    bg = Image.new("RGBA", (w * len(frames), h), (78, 96, 52, 255))
    for i, fr in enumerate(frames):
        bg.alpha_composite(fr, (i * w, 0))
    bg.save(os.path.join(PREVIEW, f"beacon-{name}.png"))


def main():
    show = "--preview" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    y = ["# HD support-power beacons (RedAlert Project X).",
         "# GENERATED by artsrc/fx/make_beacon_fx.py - edit that script, not this file.", "", "beacon:"]

    W = 84
    lock = [reticle(30 * (1 + 0.9 * (1 - t) ** 2), 90 * (1 - t) ** 2, 1 + 0.8 * (1 - t) ** 2, None, 0.35 + 0.65 * t, W)
            for t in np.linspace(0, 1, 14)]
    save("circles", lock)
    y += seq("circles", "circles", len(lock), extra=["ZOffset: 2047", "BlendMode: Additive"])
    loop = [reticle(30, i * 10 / 24 * 3, 1.0, i / 24, 0.85 + 0.15 * np.sin(i / 24 * 2 * np.pi), W) for i in range(24)]
    save("pulse", loop)
    y += seq("pulse", "pulse", len(loop), extra=["ZOffset: 2047", "BlendMode: Additive"])
    a = arrow()
    save("arrow", [a])
    y += seq("arrow", "arrow", 1, f"0,{-(a.height / D) / 2 + 2:.0f}")
    geom = None
    for name in POSTERS:
        im, geom = poster(name)
        save(name, [im])
        y += seq(name, name, 1, f"0,{-(PH / 2 + 22)}")
        if show:
            preview(name, [im])
    clk = clock(geom)
    save("clock", clk)
    y += seq("clock", "clock", len(clk), f"0,{-(PH / 2 + 22)}")
    if show:
        preview("circles", lock + loop[::3])
        preview("arrow", [a])
        preview("clock", clk[::6])

    with open(SEQUENCES, "w") as f:
        f.write("\n".join(y) + "\n")
    print("wrote", os.path.relpath(SEQUENCES, ROOT))


if __name__ == "__main__":
    main()
