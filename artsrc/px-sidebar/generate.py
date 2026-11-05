#!/usr/bin/env python3
"""
Generates the in-game sidebar skin (mods/rapx/uibits/px-sidebar.png and px-sidebar-2x.png).

Coordinates are 1x UI pixels and must match the regions in mods/rapx/px-sidebar.yaml.
Panels are 9-sliced by OpenRA with *tiled* edges and centre, so anything outside the corners
must be uniform along the direction it tiles.

Icons are game-icons.net SVGs (CC BY 3.0, see icons/LICENSE.md) rasterised with rsvg-convert.

Run: python3 artsrc/px-sidebar/generate.py
"""

import io
import os
import subprocess
from PIL import Image, ImageDraw, ImageFilter

SS = 4
SHEET_W, SHEET_H = 512, 1024
HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, "icons")
OUT_DIR = os.path.join(HERE, "..", "..", "mods", "rapx", "uibits")

RED = (226, 38, 38)
RED_BRIGHT = (255, 106, 85)
GOLD = (255, 209, 102)
ICON = (207, 208, 214)
ICON_DIM = (84, 85, 94)
WHITE = (255, 255, 255)

sheet = Image.new("RGBA", (SHEET_W * SS, SHEET_H * SS), (0, 0, 0, 0))


def S(*v):
    return [int(round(x * SS)) for x in v]


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def chamfer(x, y, w, h, c, inset=0.0):
    """Rectangle with the top-left and bottom-right corners cut at 45 degrees (SS pixels)."""
    i = inset
    return [(x + c + i * 0.414, y + i), (x + w - i, y + i), (x + w - i, y + h - c - i * 0.414),
            (x + w - c - i * 0.414, y + h - i), (x + i, y + h - i), (x + i, y + c + i * 0.414)]


def paste_cell(layer, x, y, w, h):
    X, Y, W, H = S(x, y, w, h)
    sheet.alpha_composite(layer.crop((X, Y, X + W, Y + H)), (X, Y))


# --- Sidebar background: 64x64 at (0,0); slices L12 T8 R4 B8 -------------------------------
def sidebar_bg(x, y, w=64, h=64):
    X, Y, W, H = S(x, y, w, h)
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([X, Y, X + W - 1, Y + H - 1], fill=(17, 18, 22, 255))
    # brushed-metal: faint vertical hairlines on a 3px period (48px centre tiles seamlessly).
    # ImageDraw replaces pixels instead of blending, so translucent strokes go on their own layer.
    lines = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for xx in range(12 * SS, W, 3 * SS):
        ld.rectangle([X + xx, Y, X + xx + SS // 2, Y + H - 1], fill=(255, 255, 255, 5))
    layer.alpha_composite(lines)
    # dark rail on the far left, shading into the plate
    for xx in range(6 * SS):
        d.line([(X + xx, Y), (X + xx, Y + H - 1)], fill=lerp((5, 5, 6, 255), (29, 30, 35, 255), xx / (6 * SS)))
    # glowing accent line
    glow = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle([X + 6 * SS, Y, X + 8 * SS - 1, Y + H - 1], fill=(*RED, 255))
    layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2 * SS)))
    layer.alpha_composite(glow)
    # 1px bevel on the right edge
    d = ImageDraw.Draw(layer)
    d.rectangle([X + W - SS, Y, X + W - 1, Y + H - 1], fill=(40, 41, 48, 255))
    paste_cell(layer, x, y, w, h)


sidebar_bg(0, 0)


# --- Recessed well: 32x32 at (64,0); slices 6 6 20 20 6 6 -----------------------------------
def well(x, y, w=32, h=32):
    X, Y, W, H = S(x, y, w, h)
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([X, Y, X + W - 1, Y + H - 1], fill=(36, 37, 43, 255))           # border
    d.rectangle([X + SS, Y + SS, X + W - SS - 1, Y + H - 2 * SS - 1], fill=(9, 9, 11, 255))
    d.rectangle([X, Y + H - SS, X + W - 1, Y + H - 1], fill=(52, 53, 60, 255))  # bottom highlight
    # inner shadow under the top edge (uniform horizontally)
    shadow = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for yy in range(5 * SS):
        a = int(150 * (1 - yy / (5 * SS)) ** 2)
        sd.line([(X + SS, Y + SS + yy), (X + W - SS - 1, Y + SS + yy)], fill=(0, 0, 0, a))
    layer.alpha_composite(shadow)
    paste_cell(layer, x, y, w, h)


well(64, 0)


# --- Command bar plate: 32x32 at (96,0); slices 8 8 16 16 8 8 -------------------------------
def command_plate(x, y, w=32, h=32, cut=6):
    X, Y, W, H = S(x, y, w, h)
    c = cut * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    outer = chamfer(X, Y, W, H, c)
    ImageDraw.Draw(layer).polygon(outer, fill=(56, 58, 66, 255))
    inner = chamfer(X, Y, W, H, c, inset=SS)
    mask = Image.new("L", sheet.size, 0)
    ImageDraw.Draw(mask).polygon(inner, fill=255)
    plate = Image.new("RGBA", sheet.size, (17, 18, 22, 255))
    deco = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    # hairlines on a 4px period so the 16px centre and 8px corners tile seamlessly
    for xx in range(0, W, 4 * SS):
        dd.rectangle([X + xx, Y, X + xx + SS // 2, Y + H - 1], fill=(255, 255, 255, 5))
    glow = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle([X, Y + 3 * SS, X + W, Y + 5 * SS - 1], fill=(*RED, 255))
    deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(1.5 * SS)))
    deco.alpha_composite(glow)
    plate.alpha_composite(deco)
    layer.paste(plate, (0, 0), mask)
    paste_cell(layer, x, y, w, h)


command_plate(96, 0)


# --- Bottom selection panel plate: 32x32 at (128,0); slices L4 T10 R4 B4 ---------------------
def bottom_plate(x, y, w=32, h=32):
    X, Y, W, H = S(x, y, w, h)
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle([X, Y, X + W - 1, Y + H - 1], fill=(17, 18, 22, 255))
    deco = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    for xx in range(0, W, 4 * SS):
        dd.rectangle([X + xx, Y, X + xx + SS // 2, Y + H - 1], fill=(255, 255, 255, 5))
    glow = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle([X, Y, X + W, Y + 2 * SS - 1], fill=(*RED, 255))
    deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2 * SS)))
    deco.alpha_composite(glow)
    layer.alpha_composite(deco)
    paste_cell(layer, x, y, w, h)


bottom_plate(128, 0)


# --- Keys: 40x40 cells on row y=64; slices L10 T16 R10 B16, centre 20x8 ---------------------
def key(x, y, top, bottom, border, glow=None, highlight=28, w=40, h=40, cut=6, margin=2):
    X, Y, W, H = S(x, y, w, h)
    m, c = margin * SS, cut * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    outer = chamfer(X + m, Y + m, W - 2 * m, H - 2 * m, c)
    if glow:
        g = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).line(outer + [outer[0]], fill=glow, width=2 * SS, joint="curve")
        layer.alpha_composite(g.filter(ImageFilter.GaussianBlur(1.5 * SS)))
    else:
        # drop shadow below the key
        sh = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).polygon(chamfer(X + m, Y + m + 2 * SS, W - 2 * m, H - 2 * m, c), fill=(3, 3, 4, 255))
        layer.alpha_composite(sh)

    d = ImageDraw.Draw(layer)
    d.polygon(outer, fill=border)
    inner = chamfer(X + m, Y + m, W - 2 * m, H - 2 * m, c, inset=SS)
    mask = Image.new("L", sheet.size, 0)
    ImageDraw.Draw(mask).polygon(inner, fill=255)
    fill = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    # vertical gradient lives in the fixed top/bottom slices; the tiled centre is flat
    mid = lerp(top, bottom, 0.5)
    t0, t1 = Y + 16 * SS, Y + H - 16 * SS
    for yy in range(Y, Y + H):
        if yy < t0:
            col = lerp(top, mid, (yy - Y) / (t0 - Y))
        elif yy >= t1:
            col = lerp(mid, bottom, (yy - t1) / (Y + H - t1))
        else:
            col = mid
        fd.line([(X, yy), (X + W, yy)], fill=col)
    bevel = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(bevel).rectangle([X, Y + m + SS, X + W, Y + m + 2 * SS - 1], fill=(255, 255, 255, highlight))
    fill.alpha_composite(bevel)  # top bevel
    layer.paste(Image.alpha_composite(layer, fill), (0, 0), mask)
    paste_cell(layer, x, y, w, h)


keys = [
    # top, bottom, border, glow
    ((46, 48, 56, 255), (25, 26, 31, 255), (56, 58, 66, 255), None),                   # normal
    ((54, 46, 52, 255), (30, 24, 28, 255), (*RED, 255), (*RED, 150)),                  # hover
    ((18, 18, 22, 255), (30, 31, 36, 255), (*RED_BRIGHT, 255), (*RED, 120)),           # pressed
    ((24, 25, 29, 255), (18, 18, 22, 255), (36, 37, 43, 255), None),                   # disabled
    ((240, 58, 50, 255), (154, 21, 21, 255), (*RED_BRIGHT, 255), (*RED, 170)),         # highlighted
    ((255, 84, 70, 255), (176, 30, 28, 255), (255, 160, 140, 255), (*RED_BRIGHT, 200)),  # highlighted-hover
    ((150, 20, 20, 255), (196, 36, 32, 255), (*RED_BRIGHT, 255), (*RED, 150)),         # highlighted-pressed
    ((70, 30, 32, 255), (44, 22, 24, 255), (60, 40, 42, 255), None),                   # highlighted-disabled
]
for i, (top, bottom, border, glow) in enumerate(keys):
    key(i * 40, 64, top, bottom, border, glow, highlight=60 if i in (4, 5) else 26)


# --- Icons ------------------------------------------------------------------------------------
def raster(name, size):
    png = subprocess.run(["rsvg-convert", "-w", str(size * SS), "-h", str(size * SS),
                          os.path.join(ICONS, name + ".svg")], check=True, capture_output=True).stdout
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    # game-icons SVGs draw a black square behind a white glyph: keep only the glyph
    return img.convert("L")


def icon(name, x, y, size, color, shadow=True):
    mask = raster(name, size)
    X, Y = S(x, y)
    glyph = Image.new("RGBA", mask.size, (*color[:3], 255))
    glyph.putalpha(mask)
    if shadow:
        sh = Image.new("RGBA", mask.size, (0, 0, 0, 255))
        sh.putalpha(mask.point(lambda a: a * 0.8))
        sheet.alpha_composite(sh, (X, Y + SS))
    sheet.alpha_composite(glyph, (X, Y))


# order icons, 24x24 on a 32px pitch at row y=112: base / active / disabled
ORDER = ["repair:auto-repair", "sell:receive-money", "power:power-lightning", "beacon:flag-objective", "options:cog"]
for i, entry in enumerate(ORDER):
    svg = entry.split(":")[1]
    for j, color in enumerate((ICON, WHITE, ICON_DIM)):
        icon(svg, (i * 3 + j) * 32, 112, 24, color)

# home (camera to construction yard) button icon, same 24x24 states; the y=112 row is full so it lives at y=960
for j, color in enumerate((ICON, WHITE, ICON_DIM)):
    icon("house", j * 32, 960, 24, color)

# production tab icons, 28x28 on a 32px pitch: base + disabled at row y=144, alert at row y=176
PRODUCTION = ["building:factory", "defense:military-fort", "infantry:brodie-helmet", "vehicle:battle-tank",
              "aircraft:jet-fighter", "ship:battleship"]
for i, entry in enumerate(PRODUCTION):
    svg = entry.split(":")[1]
    icon(svg, i * 64, 144, 28, ICON)
    icon(svg, i * 64 + 32, 144, 28, ICON_DIM, shadow=False)
    icon(svg, i * 32, 176, 28, GOLD)


# command bar icons, 24x24 on a 32px pitch: base at row y=256, disabled at y=288, highlighted at y=320
COMMANDS = ["attack-move:crosshair-arrow", "force-move:move", "force-attack:crosshair", "guard:checked-shield",
            "deploy:expand", "scatter:split-arrows", "stop:stop-sign", "queue-orders:path-distance",
            "attack-anything:crossed-swords", "defend:shield", "return-fire:return-arrow", "hold-fire:halt"]
for i, entry in enumerate(COMMANDS):
    svg = entry.split(":")[1]
    icon(svg, i * 32, 256, 24, ICON)
    icon(svg, i * 32, 288, 24, ICON_DIM, shadow=False)
    icon(svg, i * 32, 320, 24, WHITE)


# selection panel stat icons, 18x18 on a 32px pitch at row y=352
STATS = [("breastplate", ICON), ("stopwatch", ICON), ("power-lightning", GOLD), ("speedometer", ICON),
         ("two-coins", GOLD)]
for i, (svg, color) in enumerate(STATS):
    icon(svg, i * 32, 352, 18, color)

# building action icons, 28x28 on a 32px pitch at row y=384: base / highlighted / disabled
BUILDING_ACTIONS = ["repair:auto-repair", "sell:receive-money", "power:power-lightning", "rally:star-flag"]
for i, entry in enumerate(BUILDING_ACTIONS):
    svg = entry.split(":")[1]
    for j, color in enumerate((ICON, WHITE, ICON_DIM)):
        icon(svg, (i * 3 + j) * 32, 384, 28, color, shadow=j != 2)


# faction emblems, 44x44 badges at row y=208
def emblem(x, y, svg, top, bottom, glyph_color, size=44):
    X, Y, W = *S(x, y), size * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    mask = Image.new("L", sheet.size, 0)
    ImageDraw.Draw(mask).polygon(chamfer(X, Y, W, W, 8 * SS), fill=255)
    grad = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for yy in range(W):
        gd.line([(X, Y + yy), (X + W, Y + yy)], fill=lerp(top, bottom, yy / W))
    shine = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(shine).rectangle([X, Y, X + W, Y + SS - 1], fill=(255, 255, 255, 80))
    grad.alpha_composite(shine)
    layer.paste(grad, (0, 0), mask)
    sheet.alpha_composite(layer.crop((X, Y, X + W, Y + W)), (X, Y))
    icon(svg, x + 7, y + 7, size - 14, glyph_color)


emblem(0, 208, "hammer-sickle", (240, 58, 50, 255), (142, 18, 18, 255), GOLD)
emblem(48, 208, "eagle-emblem", (70, 130, 240, 255), (22, 52, 130, 255), WHITE)

# small glyphs
icon("two-coins", 96, 210, 28, GOLD)
icon("power-lightning", 128, 208, 18, (126, 224, 138))
icon("power-lightning", 148, 208, 18, (255, 92, 70))
icon("radar-sweep", 168, 208, 14, (143, 232, 156), shadow=False)
icon("padlock", 184, 208, 22, (232, 230, 227))

# --- Lobby: panels from y=448, auto-placed icons from y=560; regions go to mods/rapx/px-lobby.yaml
LOBBY_YAML = ["# Lobby skin regions. GENERATED by artsrc/px-sidebar/generate.py - edit that script, not this file.", ""]


def lobby_panel(name, x, y, w, h, cut, fill, border, slices, glow=None, dashed=False, top_line=False):
    X, Y, W, H = S(x, y, w, h)
    c = cut * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    outer = chamfer(X + SS, Y + SS, W - 2 * SS, H - 2 * SS, c)
    if glow:
        g = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).line(outer + [outer[0]], fill=glow, width=2 * SS, joint="curve")
        layer.alpha_composite(g.filter(ImageFilter.GaussianBlur(1.2 * SS)))
    d = ImageDraw.Draw(layer)
    if dashed:
        inner = chamfer(X + SS, Y + SS, W - 2 * SS, H - 2 * SS, c, inset=SS)
        d.polygon(inner, fill=fill)
        # 4 on / 4 off dashes so tiled 16px edges stay seamless
        dash = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(dash)
        dd.line(outer + [outer[0]], fill=border, width=SS)
        mask = Image.new("L", sheet.size, 0)
        md = ImageDraw.Draw(mask)
        for k in range(0, max(W, H), 8 * SS):
            md.rectangle([X + k, Y, X + k + 4 * SS - 1, Y + H], fill=255)
            md.rectangle([X, Y + k, X + W, Y + k + 4 * SS - 1], fill=255)
        layer.paste(dash, (0, 0), Image.composite(mask, Image.new("L", sheet.size, 0), dash.getchannel("A")))
    else:
        d.polygon(outer, fill=border)
        d.polygon(chamfer(X + SS, Y + SS, W - 2 * SS, H - 2 * SS, c, inset=SS), fill=fill)
    if top_line:
        line = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(line).rectangle([X + c, Y + SS, X + W, Y + 3 * SS], fill=(*RED, 255))
        m = Image.new("L", sheet.size, 0)
        ImageDraw.Draw(m).polygon(outer, fill=255)
        glowl = line.filter(ImageFilter.GaussianBlur(2.5 * SS))
        glowl.alpha_composite(line)
        layer.paste(Image.alpha_composite(layer, glowl), (0, 0), m)
    paste_cell(layer, x, y, w, h)
    l, t, r, b = slices
    LOBBY_YAML.append(f"{name}:\n\tInherits: ^PXSidebar\n\tPanelRegion: {x}, {y}, {l}, {t}, {w - l - r}, {h - t - b}, {r}, {b}\n")


def lobby_alias(name, target):
    LOBBY_YAML.append(f"{name}:\n\tInherits: {target}\n")


ROW = (8, 8, 8, 8)
lobby_panel("px-lobby-frame", 0, 448, 96, 96, 14, (12, 12, 15, 244), (*RED, 255), (32, 32, 32, 32), top_line=True)
lobby_panel("px-row", 96, 448, 32, 32, 6, (20, 21, 25, 255), (40, 41, 47, 255), ROW)
lobby_panel("px-row-hover", 128, 448, 32, 32, 6, (26, 27, 32, 255), (120, 52, 54, 255), ROW)
lobby_panel("px-row-empty", 160, 448, 32, 32, 6, (12, 12, 15, 210), (62, 63, 72, 255), ROW)
lobby_panel("px-card", 192, 448, 32, 32, 6, (20, 21, 25, 255), (42, 43, 49, 255), ROW)
lobby_panel("px-card-hover", 224, 448, 32, 32, 6, (29, 30, 36, 255), (*RED_BRIGHT, 255), ROW)
lobby_panel("px-card-highlighted", 256, 448, 32, 32, 6, (58, 20, 22, 255), (*RED_BRIGHT, 255), ROW, glow=(*RED, 150))
lobby_alias("px-row-pressed", "px-row-hover")
lobby_alias("px-row-disabled", "px-row")
lobby_alias("px-row-highlighted", "px-row-hover")
lobby_alias("px-card-pressed", "px-card-highlighted")
lobby_alias("px-card-highlighted-hover", "px-card-highlighted")
lobby_alias("px-card-highlighted-pressed", "px-card-highlighted")
lobby_alias("px-card-disabled", "px-card")

GREY = (157, 158, 166)
LOBBY_ICONS = [
    # collection, name, svg, size, colour
    ("px-lobby-icons", "title", "crossed-swords", 28, GOLD),
    ("px-lobby-icons", "tab-players", "three-friends", 20, WHITE),
    ("px-lobby-icons", "tab-options", "settings-knobs", 20, WHITE),
    ("px-lobby-icons", "tab-music", "musical-notes", 20, WHITE),
    ("px-lobby-icons", "col-commander", "person", 16, RED_BRIGHT),
    ("px-lobby-icons", "col-color", "palette", 16, RED_BRIGHT),
    ("px-lobby-icons", "col-nation", "star-flag", 16, RED_BRIGHT),
    ("px-lobby-icons", "col-team", "shield", 16, RED_BRIGHT),
    ("px-lobby-icons", "col-handicap", "speedometer", 16, RED_BRIGHT),
    ("px-lobby-icons", "col-spawn", "position-marker", 16, RED_BRIGHT),
    ("px-lobby-icons", "col-status", "checked-shield", 16, RED_BRIGHT),
    ("px-lobby-icons", "chip-players", "three-friends", 16, GREY),
    ("px-lobby-icons", "chip-speed", "speedometer", 16, GREY),
    ("px-lobby-icons", "chip-cash", "two-coins", 16, GREY),
    ("px-lobby-icons", "map", "treasure-map", 20, WHITE),
    ("px-lobby-icons", "play", "play-button", 22, WHITE),
    ("px-lobby-icons", "back", "return-arrow", 18, WHITE),
    ("px-lobby-icons", "join", "door", 16, WHITE),
    ("px-lobby-icons", "ai", "vintage-robot", 16, WHITE),
    ("px-lobby-icons", "spectate", "eye", 16, WHITE),
    ("px-lobby-icons", "reset", "auto-repair", 18, WHITE),
    ("px-lobby-icons", "admin", "cog", 18, WHITE),
    ("px-lobby-icons", "avatar-human", "person", 24, ICON),
    ("px-lobby-icons", "avatar-bot", "vintage-robot", 24, ICON),
    ("px-lobby-icons", "sum-cash", "two-coins", 16, RED_BRIGHT),
    ("px-lobby-icons", "sum-units", "battle-tank", 16, RED_BRIGHT),
    ("px-lobby-icons", "sum-speed", "speedometer", 16, RED_BRIGHT),
    ("px-lobby-icons", "sum-time", "stopwatch", 16, RED_BRIGHT),
    ("px-lobby-icons", "sum-treaty", "hourglass", 16, RED_BRIGHT),
    ("px-lobby-icons", "section-battlefield", "eye", 16, RED_BRIGHT),
    ("px-lobby-icons", "section-rules", "checked-shield", 16, RED_BRIGHT),
    ("px-lobby-icons", "section-setup", "settings-knobs", 16, RED_BRIGHT),
    ("px-lobby-icons", "section-dev", "alien-bug", 16, GREY),
    ("px-lobby-icons", "tick", "check-mark", 16, WHITE),
    ("px-lobby-icons", "tick-ready", "check-mark", 14, (143, 255, 159)),
    ("px-lobby-icons", "waiting", "hourglass", 14, (185, 186, 194)),
    ("px-lobby-icons", "taken", "cancel", 20, (225, 225, 230)),
]
OPTION_ICONS = [("explored", "treasure-map"), ("fog", "fog"), ("separateteamspawns", "split-arrows"),
                ("buildradius", "stone-wall"), ("shortgame", "stopwatch"), ("crates", "wooden-crate"),
                ("allybuild", "castle"), ("factundeploy", "truck"), ("reusable-engineers", "monkey-wrench"),
                ("bounty", "two-coins"), ("cheats", "alien-bug"), ("startingcash", "two-coins"),
                ("startingunits", "battle-tank"), ("techlevel", "processor"), ("gamespeed", "speedometer"),
                ("timelimit", "stopwatch"), ("peacetreaty", "hourglass"), ("default", "settings-knobs")]
for oid, svg in OPTION_ICONS:
    LOBBY_ICONS.append(("px-option-icons", oid, svg, 18, RED_BRIGHT))
    LOBBY_ICONS.append(("px-option-icons", oid + "-off", svg, 18, ICON_DIM))

# Sidebar category chips (IDEA-05, PxCategoryBarWidget): white when selected/hovered, dim otherwise
CATEGORY_ICONS = [("command", "star-flag"), ("power", "power-lightning"), ("resources", "crystal-cluster"),
                  ("army", "crossed-swords"), ("marine", "trident"), ("navy", "anchor"), ("airforce", "jet-fighter"),
                  ("space", "satellite"), ("rnd", "erlenmeyer"), ("unmanned", "delivery-drone"),
                  ("strategic", "mushroom-cloud"), ("walls", "stone-wall"), ("ground", "cannon"), ("air", "radar-sweep"),
                  ("coast", "life-buoy"), ("other", "settings-knobs")]
for cid, svg in CATEGORY_ICONS:
    LOBBY_ICONS.append(("px-category-icons", cid, svg, 18, WHITE))
    LOBBY_ICONS.append(("px-category-icons", cid + "-off", svg, 18, ICON_DIM))

regions = {}
cx, cy, row_h = 0, 560, 0
for coll, name, svg, size, color in LOBBY_ICONS:
    if cx + size > SHEET_W:
        cx, cy, row_h = 0, cy + row_h + 4, 0
    icon(svg, cx, cy, size, color, shadow=size >= 18)
    regions.setdefault(coll, []).append(f"\t\t{name}: {cx}, {cy}, {size}, {size}")
    cx += size + 6
    row_h = max(row_h, size + 2)

# host crown, drawn by hand
crown_y = cy + row_h + 4
crown = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
ImageDraw.Draw(crown).polygon([(SS * v[0], SS * (crown_y + v[1])) for v in
                               ((1, 11), (2, 2), (5, 7), (8, 1), (11, 7), (14, 2), (15, 11))], fill=(*GOLD, 255))
sheet.alpha_composite(crown)
regions["px-lobby-icons"].append(f"\t\tcrown: 0, {crown_y}, 16, 12")


# Lobby option checkboxes (PxOptionSwitchWidget): 24x24 chamfered boxes centred in 32x32 cells so the glow fits
def checkbox(x, y, checked, border, fill_top, fill_bottom, tick=WHITE, glow=None, size=24):
    X, Y = S(x + 4, y + 4)
    W, c = size * SS, 5 * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    outer = chamfer(X, Y, W, W, c)
    if glow:
        g = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).polygon(outer, fill=glow)
        layer.alpha_composite(g.filter(ImageFilter.GaussianBlur(2 * SS)))
    d = ImageDraw.Draw(layer)
    d.polygon(outer, fill=border)
    mask = Image.new("L", sheet.size, 0)
    ImageDraw.Draw(mask).polygon(chamfer(X, Y, W, W, c, inset=1.5 * SS), fill=255)
    grad = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for yy in range(W):
        gd.line([(X, Y + yy), (X + W, Y + yy)], fill=lerp(fill_top, fill_bottom, yy / W))
    # recessed when empty (dark top edge), raised when checked (light top edge)
    gd.rectangle([X, Y + int(1.5 * SS), X + W, Y + int(2.5 * SS)], fill=(255, 255, 255, 70) if checked else (0, 0, 0, 120))
    layer.paste(grad, (0, 0), mask)
    if checked:
        pts = [(X + 6 * SS, Y + 12.5 * SS), (X + 10.5 * SS, Y + 17 * SS), (X + 18.5 * SS, Y + 7.5 * SS)]
        sh = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).line([(px, py + SS) for px, py in pts], fill=(60, 0, 0, 170), width=int(3.2 * SS), joint="curve")
        layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(0.6 * SS)))
        ImageDraw.Draw(layer).line(pts, fill=(*tick[:3], 255), width=int(3.2 * SS), joint="curve")
        for px, py in (pts[0], pts[2]):
            r = 1.6 * SS
            ImageDraw.Draw(layer).ellipse([px - r, py - r, px + r, py + r], fill=(*tick[:3], 255))
    paste_cell(layer, x, y, 32, 32)


check_y = crown_y + 16
CHECKBOXES = [
    ("off", False, (70, 71, 80, 255), (10, 10, 13, 255), (24, 25, 30, 255), WHITE, None),
    ("off-hover", False, (*RED_BRIGHT, 255), (12, 12, 15, 255), (30, 26, 30, 255), WHITE, (*RED, 90)),
    ("on", True, (*RED_BRIGHT, 255), (240, 70, 60, 255), (168, 22, 22, 255), WHITE, (*RED, 140)),
    ("on-hover", True, (255, 160, 140, 255), (255, 92, 78, 255), (190, 30, 28, 255), WHITE, (*RED, 200)),
    ("off-disabled", False, (44, 45, 52, 255), (14, 14, 17, 255), (18, 18, 22, 255), WHITE, None),
    ("on-disabled", True, (110, 50, 50, 255), (96, 36, 36, 255), (70, 26, 26, 255), (170, 150, 150), None),
]
regions["px-checkbox"] = []
for i, (name, checked, border, top, bottom, tick, glow) in enumerate(CHECKBOXES):
    checkbox(i * 32, check_y, checked, border, top, bottom, tick, glow)
    regions["px-checkbox"].append(f"\t\t{name}: {i * 32}, {check_y}, 32, 32")

for coll, lines in regions.items():
    LOBBY_YAML.append(f"{coll}:\n\tInherits: ^PXSidebar\n\tRegions:\n" + "\n".join(lines) + "\n")

with open(os.path.join(HERE, "..", "..", "mods", "rapx", "px-lobby.yaml"), "w") as f:
    f.write("\n".join(LOBBY_YAML))


# --- Write 1x and 2x sheets -------------------------------------------------------------------
for scale, name in ((1, "px-sidebar.png"), (2, "px-sidebar-2x.png")):
    out = sheet.resize((SHEET_W * scale, SHEET_H * scale), Image.LANCZOS)
    # resampling bleeds the empty sheet into cell edges: the plate and well must stay fully opaque
    for x, y, w, h in ((0, 0, 64, 64), (64, 0, 32, 32), (128, 0, 32, 32)):
        alpha = out.getchannel("A")
        alpha.paste(255, (x * scale, y * scale, (x + w) * scale, (y + h) * scale))
        out.putalpha(alpha)
    out.save(os.path.join(OUT_DIR, name))
    print("wrote", name, out.size)
