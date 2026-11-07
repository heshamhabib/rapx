#!/usr/bin/env python3
"""
Our own versions of the last small sprites that came from bits/ (copied from OpenRA's RA mod, edits of the original
art), IDEA-31: cargo / resource pips, the SPY tag, power-off and repair icons, veteran chevrons and rank insignia,
GPS dots, the heal and level-up crate effects, the capture-the-flag flag, the steel crate on water and the map
editor's camera / spawn / waypoint markers. Same frame order as the originals.

Symbols from game-icons.net (artsrc/sprites/icons/source, CC BY 3.0, credited in mods/rapx/CREDITS). GPS dots are
palette-indexed and drawn only in the player colour range (indices 80-95), so they keep showing the owner's colour.
Writes mods/rapx/bits/hd/ui/<name>.png; everything else is RGBA at 3x for `Scale: 0.3333`.

  python3 artsrc/sprites/make_markers.py
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import make_icons as icons
import make_ui_sprites as ui

S = ui.S
GOLD = (236, 196, 92)
SCRATE = os.path.join(ui.ROOT, "mods", "rapx", "bits", "hd", "env", "scrate.png")


def canvas(w, h):
    return Image.new("RGBA", (w * S, h * S))


def outlined_symbol(name, size, fill, outline=(14, 14, 12), width=3, rotate=0):
    s = icons.symbol(name, size, rotate)
    a = s.split()[3]
    ring = a.filter(ImageFilter.MaxFilter(width * 2 + 1))
    out = Image.new("RGBA", s.size)
    out.paste(Image.new("RGBA", s.size, outline + (255,)), (0, 0), ring)
    out.paste(Image.new("RGBA", s.size, fill + (255,)), (0, 0), a)
    return out


def centred(img, sym, dy=0):
    img.alpha_composite(sym, ((img.width - sym.width) // 2, (img.height - sym.height) // 2 + dy))
    return img


def pips2():
    """Cargo / resource pips, 4x4: empty, green, yellow, grey, red, blue."""
    frames = []
    for col in ((46, 50, 46), (40, 205, 60), (240, 190, 30), (170, 175, 180), (215, 40, 35), (60, 130, 240)):
        img = canvas(4, 4)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, img.width - 1, img.height - 1], fill=(8, 10, 8, 255))
        d.rectangle([2, 2, img.width - 3, img.height - 3], fill=col + (255,))
        d.line([2, 2, img.width - 3, 2], fill=tuple(min(255, c + 70) for c in col) + (255,), width=2)
        frames.append(img)
    ui.save_sheet("pips2", frames)


def tag_spy():
    ui.save_sheet("tag-spy", [ui.outlined_text(canvas(16, 8), "SPY", 24)])


def pulsing(name, symbol, w, h, colour, n=5):
    """A symbol whose glow pulses over n frames (power-off bolt, repair spanner)."""
    frames = []
    size = int(min(w, h) * S * 0.9)
    for i in range(n):
        k = 0.5 + 0.5 * math.sin(i / n * 2 * math.pi)
        img = canvas(w, h)
        sym = outlined_symbol(symbol, size, tuple(min(255, int(c * (0.8 + 0.3 * k))) for c in colour))
        layer = Image.new("RGBA", img.size)
        layer.alpha_composite(icons.glow(icons.symbol(symbol, size), colour, 3, 0.4 + 0.5 * k),
                              ((img.width - size) // 2, (img.height - size) // 2))
        img.alpha_composite(layer)
        frames.append(centred(img, sym))
    ui.save_sheet(name, frames)


def chevrons(name, w, h, colour, scale):
    """1, 2, 3 chevrons and a star (veteran levels / rank insignia)."""
    frames = []
    for level in (1, 2, 3, 4):
        img = canvas(w, h)
        d = ImageDraw.Draw(img)
        cx, cy = img.width / 2, img.height / 2
        u = scale * S
        if level < 4:
            for k in range(level):
                y = cy + (level - 1) * u * 0.55 - k * u * 1.1
                pts = [(cx - u * 1.6, y + u * 0.5), (cx, y - u * 0.9), (cx + u * 1.6, y + u * 0.5),
                       (cx + u * 1.6, y + u * 1.4), (cx, y), (cx - u * 1.6, y + u * 1.4)]
                d.polygon(pts, fill=colour + (255,), outline=(14, 12, 8, 255), width=1)
        else:
            r1, r2 = u * 1.9, u * 0.8
            pts = [(cx + (r1 if j % 2 == 0 else r2) * math.sin(j * math.pi / 5),
                    cy - (r1 if j % 2 == 0 else r2) * math.cos(j * math.pi / 5)) for j in range(10)]
            d.polygon(pts, fill=colour + (255,), outline=(14, 12, 8, 255), width=1)
        frames.append(img)
    ui.save_sheet(name, frames)


# GPS dot frames (sequences/misc.yaml gpsdot): Infantry, Vehicle, Ship, Helicopter, Plane, Harvester, Structure,
# Oil, Hospital, Biohazard, Communications, Forward
GPS_SYMBOLS = [None, "tank", "anchor", "helicopter", "jet-fighter", "truck", "house", "drop", "hospital-cross",
               "biohazard", "radio-tower", "flying-flag"]


def gpsdot():
    """Palette-indexed: fill in the light end of the player colour ramp, outline in its dark end."""
    W, H = 19 * S, 16 * S
    frames = []
    for sym in GPS_SYMBOLS:
        if sym is None:
            a = Image.new("L", (W, H))
            ImageDraw.Draw(a).ellipse([W / 2 - 9, H / 2 - 9, W / 2 + 9, H / 2 + 9], fill=255)
        else:
            s = icons.symbol(sym, H - 6)
            a = Image.new("L", (W, H))
            a.paste(s.split()[3], ((W - s.width) // 2, 3))
        fill = np.asarray(a) > 110
        ring = np.asarray(a.filter(ImageFilter.MaxFilter(7))) > 110
        idx = np.where(fill, 81, np.where(ring, 93, 0)).astype(np.uint8)
        frames.append(Image.frombytes("P", (W, H), idx.tobytes()))
    pal = [0] * 768
    for i in range(16):  # only previews use these colours; in game the player palette remaps 80-95
        v = 240 - i * 14
        pal[(80 + i) * 3:(80 + i) * 3 + 3] = [v, v, v]
    ui.save_sheet("gpsdot", frames, mode="P", palette=pal)


def ctflag():
    """Capture-the-flag flag waving on its pole, 10 frames on the original 25x40 canvas (Length 9 is used)."""
    frames = []
    W, H = 25 * S, 40 * S
    for i in range(10):
        img = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(img)
        px = 18
        d.rectangle([px - 3, 10, px + 2, H - 6], fill=(70, 64, 58, 255))
        d.rectangle([px - 1, 10, px, H - 6], fill=(150, 140, 128, 255))
        cloth = []
        for j in range(21):
            x = px + 3 + j * 2.6
            y = 14 + 5 * math.sin(j * 0.32 - i * 0.63) * j / 20
            cloth.append((x, y))
        bottom = [(x, y + 26) for x, y in reversed(cloth)]
        d.polygon(cloth + bottom, fill=(232, 222, 196, 255), outline=(60, 54, 44, 255))
        for j in range(0, 20, 4):
            x, y = cloth[j]
            d.line([(x, y + 2), (x, y + 24)], fill=(205, 192, 162, 255), width=2)
        d.ellipse([px - 9, H - 12, px + 9, H - 2], fill=(0, 0, 0, 90))
        frames.append(img)
    ui.save_sheet("ctflag", frames)


def editor_marker(name, draw):
    """Map editor markers: a translucent green tile with a dark symbol."""
    img = canvas(24, 24)
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, img.width - 3, img.height - 3], fill=(70, 200, 90, 170), outline=(20, 70, 30, 255), width=3)
    draw(img, d)
    ui.save_sheet(name, [img])


def heal_effect():
    """Heal crate: a green medical cross grows, glows and bursts into a ring (35 frames like the original)."""
    ui.save_sheet("crate-heal", icons.crate_effect("hospital-cross", (80, 230, 110), 35))


def levelup():
    """+1 RANK rising and fading, 5 frames on 32x32."""
    frames = []
    font = ImageFont.truetype(ui.FONT, 26)
    for i in range(5):
        img = canvas(32, 32)
        layer = Image.new("RGBA", img.size)
        ld = ImageDraw.Draw(layer)
        y = img.height / 2 + 8 - i * 6
        box = ld.textbbox((0, 0), "+1 RANK", font=font)
        x = (img.width - (box[2] - box[0])) / 2
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                ld.text((x + dx, y + dy), "+1 RANK", font=font, fill=(16, 12, 6, 255))
        ld.text((x, y), "+1 RANK", font=font, fill=GOLD + (255,))
        a = np.asarray(layer).copy()
        a[..., 3] = (a[..., 3] * (1 - i / 6)).astype(np.uint8)
        img.alpha_composite(Image.fromarray(a))
        frames.append(img)
    ui.save_sheet("levelup", frames)


def scrate_water():
    """Steel crate on water: the HD steel crate bobbing in ripples (the water frames of the scrate image)."""
    crate = Image.open(SCRATE).convert("RGBA")
    info = crate.info.get("Frame[0]")
    if info:
        x, y, w, h = map(int, info.split(";")[0].split(","))
        crate = crate.crop((x, y, x + w, y + h))
    frames = []
    for i in range(4):
        img = canvas(24, 24)
        d = ImageDraw.Draw(img)
        cx, cy = img.width / 2, img.height / 2 + 6
        for k in range(3):
            r = 18 + ((i * 5 + k * 6) % 17)
            d.ellipse([cx - r, cy - r * 0.55, cx + r, cy + r * 0.55], outline=(200, 225, 255, int(170 * (1 - (r - 18) / 17))),
                      width=2)
        bob = int(2 * math.sin(i * math.pi / 2))
        img.alpha_composite(crate, (int(cx - crate.width / 2), int(cy - crate.height * 0.8 + bob)))
        frames.append(img)
    ui.save_sheet("scrate-water", frames)


def main():
    pips2()
    tag_spy()
    pulsing("poweroff", "power-lightning", 24, 24, (255, 220, 70))
    pulsing("allyrepair", "spanner", 28, 25, GOLD)
    chevrons("iconchevrons", 15, 20, GOLD, 2.6)
    chevrons("rank", 12, 12, (255, 170, 40), 1.9)
    gpsdot()
    ctflag()
    editor_marker("camera", lambda img, d: centred(img, outlined_symbol("video-camera", 48, (20, 40, 24), (20, 40, 24), 0)))
    editor_marker("mpspawn", lambda img, d: _spawn_text(img))
    editor_marker("waypoint", lambda img, d: d.line([(14, 22), (36, 22), (56, 52)], fill=(20, 40, 24, 255), width=5)
                  or d.polygon([(56, 52), (46, 50), (55, 41)], fill=(20, 40, 24, 255)))
    heal_effect()
    levelup()
    scrate_water()


def _spawn_text(img):
    top = ui.outlined_text(Image.new("RGBA", (img.width, img.height // 2)), "PLAYER", 20)
    bottom = ui.outlined_text(Image.new("RGBA", (img.width, img.height // 2)), "SPAWN", 20)
    img.alpha_composite(top, (0, 6))
    img.alpha_composite(bottom, (0, img.height // 2 - 6))


if __name__ == "__main__":
    main()
