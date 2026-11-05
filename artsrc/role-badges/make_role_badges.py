#!/usr/bin/env python3
"""
Bakes the role badge icons (PxRoleBadge) from game-icons.net SVGs (CC BY 3.0, see icons/LICENSE.md):
white glyph with top-lit shading, a dark outline and a soft drop shadow, tinted per role where it helps.
The team-colour glow behind them is drawn live in game.

Writes mods/rapx/bits/hd/rolebadges.png (PngSheet, one frame per role) and sequences/role-badges.yaml.

  python3 artsrc/role-badges/make_role_badges.py
"""
import io
import os
import re
import subprocess

import numpy as np
from PIL import Image, ImageFilter
from PIL.PngImagePlugin import PngInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ICONS = os.path.join(HERE, "icons")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "rolebadges.png")
SEQ = os.path.join(ROOT, "mods", "rapx", "sequences", "role-badges.yaml")

FRAME = 128          # px per badge (shown at ~24 px: crisp on HiDPI and when zoomed)
GLYPH = 96           # glyph size inside the frame

# Thin icons get bolder strokes so they read at ~24 px
BOLD = {"sniper": 5}
# role (PxRole, lower case) -> (icon file, tint (top, bottom) RGB)
WHITE = ((255, 255, 255), (196, 204, 214))
ROLES = {
    "rifle": ("skoll_ak47", WHITE),
    "rocket": ("lorc_rocket", ((255, 255, 255), (255, 176, 92))),
    "grenade": ("lorc_grenade", WHITE),
    "flame": ("delapouite_flamethrower", ((255, 226, 140), (255, 120, 40))),
    "sniper": ("delapouite_crosshair", ((255, 255, 255), (255, 120, 110))),
    "pistol": ("john-colburn_pistol-gun", WHITE),
    "medic": ("sbed_health-normal", ((255, 110, 100), (205, 30, 30))),
    "mechanic": ("lorc_spanner", WHITE),
    "engineer": ("lorc_gear-hammer", ((255, 236, 160), (226, 176, 60))),
    "tesla": ("lorc_tesla-coil", ((200, 236, 255), (70, 160, 255))),
    "spy": ("delapouite_spy", WHITE),
    "dog": ("lorc_paw", WHITE),
    "machinegun": ("skoll_machine-gun", WHITE),
    "robot": ("delapouite_robot-helmet", ((220, 240, 255), (130, 170, 200))),
}


def glyph(name):
    """Alpha mask of the icon (the black background square of game-icons.net removed)."""
    svg = open(os.path.join(ICONS, name + ".svg")).read()
    svg = re.sub(r'<path d="M0 0h512v512H0z"[^>]*/>', "", svg)
    svg = svg.replace('fill="#000"', 'fill="none"')
    png = subprocess.run(["rsvg-convert", "-w", str(GLYPH * 2), "-h", str(GLYPH * 2)], input=svg.encode(),
                         capture_output=True, check=True).stdout
    im = Image.open(io.BytesIO(png)).convert("RGBA").resize((GLYPH, GLYPH), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    # glyph = bright pixels (the icon is white); transparent/black = background
    lum = a[..., :3].mean(-1) / 255
    return np.clip(a[..., 3] / 255 * lum, 0, 1)


def badge(mask, tint):
    pad = (FRAME - GLYPH) // 2
    m = np.zeros((FRAME, FRAME), np.float32)
    m[pad:pad + GLYPH, pad:pad + GLYPH] = mask
    mi = Image.fromarray((m * 255).astype(np.uint8))

    out = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
    # soft drop shadow
    sh = mi.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(5))
    shadow = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 255), (3, 5), sh.point(lambda v: int(v * 0.7)))
    out.alpha_composite(shadow)
    # dark outline
    ol = mi.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(0.8))
    outline = Image.new("RGBA", (FRAME, FRAME), (12, 13, 16, 0))
    outline.putalpha(ol.point(lambda v: int(min(255, v * 1.15))))
    out.alpha_composite(outline)
    # top-lit gradient fill
    top, bottom = np.array(tint[0], np.float32), np.array(tint[1], np.float32)
    t = np.linspace(0, 1, FRAME)[:, None, None]
    grad = (top * (1 - t) + bottom * t).repeat(FRAME, axis=1)
    fill = np.dstack([grad, m[..., None] * 255]).astype(np.uint8)
    out.alpha_composite(Image.fromarray(fill))
    # thin inner highlight on the upper edges
    inner = mi.filter(ImageFilter.MinFilter(3))
    edge = np.clip(np.asarray(mi, np.float32) - np.asarray(inner, np.float32), 0, 255)
    up = np.roll(edge, 1, axis=0) * (np.arange(FRAME)[:, None] < FRAME * 0.6)
    hl = np.zeros((FRAME, FRAME, 4), np.uint8)
    hl[..., :3] = 255
    hl[..., 3] = (up * 0.55).astype(np.uint8)
    out.alpha_composite(Image.fromarray(hl))
    return out


def main():
    frames = []
    for role, (icon, tint) in ROLES.items():
        mask = glyph(icon)
        if role in BOLD:
            mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(BOLD[role])),
                              np.float32) / 255
        frames.append(badge(mask, tint))
    sheet = Image.new("RGBA", (FRAME * len(frames), FRAME), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * FRAME, 0))
    meta = PngInfo()
    meta.add_text("FrameSize", f"{FRAME},{FRAME}")
    meta.add_text("FrameAmount", str(len(frames)))
    sheet.save(OUT, pnginfo=meta, optimize=True)
    lines = ["# Role badge icons (PxRoleBadge). GENERATED by artsrc/role-badges/make_role_badges.py.", "", "pxroles:"]
    for i, role in enumerate(ROLES):
        lines += [f"\t{role}:", "\t\tFilename: ra|bits/hd/rolebadges.png", f"\t\tStart: {i}"]
    open(SEQ, "w").write("\n".join(lines) + "\n")
    print(f"wrote {len(frames)} badges to {OUT}")


if __name__ == "__main__":
    main()
