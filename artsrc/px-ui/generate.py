#!/usr/bin/env python3
"""
Generates the RedAlert Project X UI skin (mods/rapx/uibits/px-ui.png and px-ui-2x.png).

Every element is drawn at 4x and downsampled for anti-aliasing. Coordinates below are in
1x UI pixels and must match the PanelRegion / Regions entries in mods/rapx/chrome/px-ui.yaml.

Panels are 9-sliced by OpenRA and the edges/center are *tiled*, so anything that is not a
corner must be uniform along its length (flat fills, straight borders, aligned scanlines).

Run: python3 artsrc/px-ui/generate.py
"""

import os
from PIL import Image, ImageDraw, ImageFilter

SS = 4  # supersampling factor
SHEET_W, SHEET_H = 512, 512
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "mods", "rapx", "uibits")

RED = (226, 38, 38)
RED_BRIGHT = (255, 92, 70)
RED_DIM = (110, 32, 34)
STEEL = (70, 70, 78)
STEEL_DIM = (44, 44, 50)

sheet = Image.new("RGBA", (SHEET_W * SS, SHEET_H * SS), (0, 0, 0, 0))


def chamfer_poly(x, y, w, h, cut_tl, cut_br, inset=0.0):
    """Rectangle with the top-left and bottom-right corners cut at 45 degrees (in SS pixels)."""
    i = inset
    return [
        (x + cut_tl + i * 0.414, y + i),
        (x + w - i, y + i),
        (x + w - i, y + h - cut_br - i * 0.414),
        (x + w - cut_br - i * 0.414, y + h - i),
        (x + i, y + h - i),
        (x + i, y + cut_tl + i * 0.414),
    ]


def panel(x, y, w, h, cut, fill, border, border_w=1.0, glow=None, glow_r=3.0, margin=0.0,
          scanlines=None, brackets=None, inner_line=None):
    """Draw a chamfered panel into the sheet. All arguments are in 1x pixels."""
    X, Y, W, H = (v * SS for v in (x, y, w, h))
    m, c, bw = margin * SS, cut * SS, border_w * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))

    if glow:
        g = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).line(chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c) + [chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c)[0]],
                               fill=glow, width=int(bw * 2), joint="curve")
        g = g.filter(ImageFilter.GaussianBlur(glow_r * SS))
        layer.alpha_composite(g)

    d = ImageDraw.Draw(layer)
    outer = chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c)
    d.polygon(outer, fill=border)
    inner = chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c, inset=bw)
    d.polygon(inner, fill=fill)

    if scanlines:
        period, color = scanlines
        mask = Image.new("L", sheet.size, 0)
        ImageDraw.Draw(mask).polygon(inner, fill=255)
        lines = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lines)
        for yy in range(Y, Y + H, period * SS):
            ld.rectangle([X, yy, X + W, yy + SS - 1], fill=color)
        layer.paste(Image.alpha_composite(layer, lines), (0, 0), mask)

    if inner_line:
        d.line(chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c, inset=bw + 2 * SS) +
               [chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c, inset=bw + 2 * SS)[0]],
               fill=inner_line, width=SS)

    if brackets:
        color, length, thick = brackets
        L, T = length * SS, thick * SS
        x0, y0, x1, y1 = X + m, Y + m, X + W - m, Y + H - m
        # top-right and bottom-left corners carry bright L-brackets
        d.rectangle([x1 - L, y0, x1, y0 + T], fill=color)
        d.rectangle([x1 - T, y0, x1, y0 + L], fill=color)
        d.rectangle([x0, y1 - T, x0 + L, y1], fill=color)
        d.rectangle([x0, y1 - L, x0 + T, y1], fill=color)
        # small accent ticks along the chamfers
        d.line([(x0 + c + 2 * SS, y0 + 2 * SS), (x0 + 2 * SS, y0 + c + 2 * SS)], fill=color, width=T)
        d.line([(x1 - c - 2 * SS, y1 - 2 * SS), (x1 - 2 * SS, y1 - c - 2 * SS)], fill=color, width=T)

    # clip to the element's own cell so glows never bleed into neighbouring regions
    sheet.alpha_composite(layer.crop((X, Y, X + W, Y + H)), (X, Y))


def rect(x, y, w, h, color):
    ImageDraw.Draw(sheet).rectangle([x * SS, y * SS, (x + w) * SS - 1, (y + h) * SS - 1], fill=color)


# --- Dialog: 64x64 at (0,0), 16px corners -------------------------------------------------
panel(0, 0, 64, 64, cut=10, margin=3, fill=(12, 10, 12, 236), border=(*RED, 255), border_w=1.5,
      glow=(*RED, 150), glow_r=2.0, scanlines=(4, (255, 255, 255, 7)),
      brackets=((*RED_BRIGHT, 255), 13, 2), inner_line=(*RED_DIM, 120))

# --- Buttons: 32x32, 8px corners, row y=64 -------------------------------------------------
buttons = [
    # fill, border, glow
    ((26, 20, 22, 235), (*RED_DIM, 255), None),                  # button
    ((48, 18, 20, 240), (*RED, 255), (*RED, 140)),               # hover
    ((120, 20, 22, 245), (*RED_BRIGHT, 255), (*RED, 160)),       # pressed
    ((22, 22, 24, 170), (*STEEL_DIM, 255), None),                # disabled
    ((168, 24, 28, 245), (*RED_BRIGHT, 255), (*RED, 120)),       # highlighted (primary)
    ((205, 34, 34, 250), (255, 140, 110, 255), (*RED_BRIGHT, 190)),  # highlighted-hover
    ((120, 18, 20, 250), (*RED_BRIGHT, 255), (*RED, 160)),       # highlighted-pressed
    ((60, 30, 32, 170), (*STEEL_DIM, 255), None),                # highlighted-disabled
]
for i, (fill, border, glow) in enumerate(buttons):
    panel(i * 32, 64, 32, 32, cut=5, margin=1.5, fill=fill, border=border, border_w=1, glow=glow, glow_r=1.5)

# --- Text fields / checkboxes: 32x32, 8px corners, row y=96 ---------------------------------
fields = [
    ((6, 5, 7, 225), (*STEEL, 255), None),          # field
    ((10, 6, 8, 230), (*RED_DIM, 255), None),       # hover
    ((14, 6, 8, 235), (*RED, 255), (*RED, 130)),    # focused / pressed
    ((10, 10, 12, 150), (*STEEL_DIM, 255), None),   # disabled
]
for i, (fill, border, glow) in enumerate(fields):
    panel(i * 32, 96, 32, 32, cut=0, margin=1.5, fill=fill, border=border, border_w=1, glow=glow, glow_r=1.5)

# --- Section header: 64x13 at (0,128); 8px fixed ends, tiled middle ---------------------------
rect(0, 128, 64, 12, (200, 30, 30, 46))
rect(0, 140, 64, 1, (*RED, 230))
rect(0, 128, 3, 12, (*RED_BRIGHT, 255))      # left accent block (in the fixed left end)
rect(61, 128, 3, 12, (*RED_BRIGHT, 255))     # right accent block

# --- Dropdown separators: 1x19 at row y=150 ---------------------------------------------------
for i, color in enumerate([(*RED_DIM, 255), (*RED, 255), (*RED_BRIGHT, 255), (*STEEL_DIM, 255)]):
    rect(i * 2, 150, 1, 19, color)

# --- Title underline: 320x6 at (0,176), glowing line that fades out at both ends ------------
line = Image.new("RGBA", (320 * SS, 6 * SS), (0, 0, 0, 0))
ld = ImageDraw.Draw(line)
ld.rectangle([0, 2 * SS, 320 * SS, 3 * SS], fill=(*RED_BRIGHT, 255))
line = Image.alpha_composite(line.filter(ImageFilter.GaussianBlur(1.5 * SS)), line)
fade = Image.new("L", line.size, 0)
for xx in range(line.width):
    t = 1 - abs(xx / line.width * 2 - 1)
    ImageDraw.Draw(fade).line([(xx, 0), (xx, line.height)], fill=int(255 * min(1, t * 2.2)))
line.putalpha(Image.composite(line.getchannel("A"), Image.new("L", line.size, 0), fade))
sheet.alpha_composite(line, (0, 176 * SS))

# --- Main menu side panel: 128x128 at (0,256), 40px corners --------------------------------
def menu_panel(x, y, size=128, cut=22, margin=3):
    X, Y, S, m, c = x * SS, y * SS, size * SS, margin * SS, cut * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    outline = chamfer_poly(X + m, Y + m, S - 2 * m, S - 2 * m, c, c)

    g = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).line(outline + [outline[0]], fill=(*RED, 170), width=3 * SS, joint="curve")
    layer.alpha_composite(g.filter(ImageFilter.GaussianBlur(2 * SS)))

    d = ImageDraw.Draw(layer)
    d.polygon(outline, fill=(*RED, 255))
    inner = chamfer_poly(X + m, Y + m, S - 2 * m, S - 2 * m, c, c, inset=1.5 * SS)
    d.polygon(inner, fill=(7, 6, 8, 222))

    # Everything inside the frame is clipped to the inner shape
    mask = Image.new("L", sheet.size, 0)
    ImageDraw.Draw(mask).polygon(inner, fill=255)
    deco = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)

    # Header band: red wash fading down over the fixed top edge (uniform horizontally so it tiles)
    for yy in range(36 * SS):
        a = int(70 * (1 - yy / (36 * SS)) ** 1.6)
        dd.line([(X, Y + m + yy), (X + S, Y + m + yy)], fill=(200, 26, 28, a))

    # Scanlines, aligned to the 4px period so the tiled centre stays seamless
    for yy in range(Y, Y + S, 4 * SS):
        dd.rectangle([X, yy, X + S, yy + SS - 1], fill=(255, 255, 255, 6))

    # Glowing vertical accent rail down the left edge
    rail = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    ImageDraw.Draw(rail).rectangle([X + 9 * SS, Y, X + 11 * SS - 1, Y + S], fill=(*RED_BRIGHT, 255))
    deco.alpha_composite(rail.filter(ImageFilter.GaussianBlur(2.5 * SS)))
    deco.alpha_composite(rail)
    dd.rectangle([X + 14 * SS, Y, X + 15 * SS - 1, Y + S], fill=(*RED_DIM, 160))

    # Thin inner line along the right edge
    dd.rectangle([X + S - m - 6 * SS, Y, X + S - m - 5 * SS - 1, Y + S], fill=(*RED_DIM, 140))

    layer.paste(Image.alpha_composite(layer, deco), (0, 0), mask)

    # Bright L-brackets on the square corners, accent ticks along the chamfers
    L, T = 18 * SS, 2 * SS
    x0, y0, x1, y1 = X + m, Y + m, X + S - m, Y + S - m
    d = ImageDraw.Draw(layer)
    d.rectangle([x1 - L, y0, x1, y0 + T], fill=(*RED_BRIGHT, 255))
    d.rectangle([x1 - T, y0, x1, y0 + L], fill=(*RED_BRIGHT, 255))
    d.rectangle([x0, y1 - T, x0 + L, y1], fill=(*RED_BRIGHT, 255))
    d.rectangle([x0, y1 - L, x0 + T, y1], fill=(*RED_BRIGHT, 255))
    d.line([(x0 + c + 3 * SS, y0 + 3 * SS), (x0 + 3 * SS, y0 + c + 3 * SS)], fill=(*RED_BRIGHT, 255), width=T)
    d.line([(x1 - c - 3 * SS, y1 - 3 * SS), (x1 - 3 * SS, y1 - c - 3 * SS)], fill=(*RED_BRIGHT, 255), width=T)

    sheet.alpha_composite(layer.crop((X, Y, X + S, Y + S)), (X, Y))


menu_panel(0, 256)

# --- Main menu buttons: 96x40 cells at row y=384; 24px side / 12px top+bottom slices ----------
def menu_button(x, y, fill, border, rail, stripes, glow=None, w=96, h=40, cut=8, margin=2.0):
    small = w < 64
    X, Y, W, H, m, c = x * SS, y * SS, w * SS, h * SS, margin * SS, cut * SS
    layer = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    outline = chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c)
    if glow:
        g = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).line(outline + [outline[0]], fill=glow, width=2 * SS, joint="curve")
        layer.alpha_composite(g.filter(ImageFilter.GaussianBlur(1.5 * SS)))

    d = ImageDraw.Draw(layer)
    d.polygon(outline, fill=border)
    inner = chamfer_poly(X + m, Y + m, W - 2 * m, H - 2 * m, c, c, inset=SS)
    d.polygon(inner, fill=fill)

    mask = Image.new("L", sheet.size, 0)
    ImageDraw.Draw(mask).polygon(inner, fill=255)
    deco = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    for yy in range(Y, Y + H, 2 * SS):
        dd.rectangle([X, yy, X + W, yy + SS // 2], fill=(255, 255, 255, 5))
    rx, rw = (3, 2) if small else (6, 3)
    dd.rectangle([X + rx * SS, Y, X + (rx + rw) * SS - 1, Y + H], fill=rail)
    layer.paste(Image.alpha_composite(layer, deco), (0, 0), mask)

    # Three hazard stripes tucked into the bottom-right corner slice
    d = ImageDraw.Draw(layer)
    n, step, ln = (2, 3, 3) if small else (3, 4, 5)
    bx, by = X + W - m - c - (1 if small else 2) * SS, Y + H - m - (1.5 if small else 2) * SS
    for i in range(n):
        ox = bx - i * step * SS
        d.line([(ox, by), (ox + ln * SS, by - ln * SS)], fill=stripes, width=int(1.5 * SS if not small else SS))

    sheet.alpha_composite(layer.crop((X, Y, X + W, Y + H)), (X, Y))


menu_buttons = [
    # fill, border, rail, stripes, glow
    ((14, 11, 13, 228), (96, 30, 32, 255), (170, 30, 32, 255), (120, 34, 34, 255), None),          # normal
    ((76, 14, 17, 240), (*RED_BRIGHT, 255), (255, 150, 120, 255), (*RED_BRIGHT, 255), (*RED, 170)),  # hover
    ((140, 20, 22, 248), (255, 140, 110, 255), (255, 230, 220, 255), (255, 200, 180, 255), (*RED_BRIGHT, 190)),  # pressed
    ((12, 12, 14, 150), (*STEEL_DIM, 255), (*STEEL, 255), (*STEEL_DIM, 255), None),               # disabled
]
for i, (fill, border, rail, stripes, glow) in enumerate(menu_buttons):
    menu_button(i * 96, 384, fill, border, rail, stripes, glow)

# --- Compact buttons for every other menu: 48x28 cells at row y=432; 10px side / 9px top+bottom
compact = [
    # fill, border, rail, stripes, glow
    ((18, 13, 15, 230), (110, 34, 36, 255), (170, 30, 32, 255), (120, 34, 34, 255), None),          # button
    ((76, 14, 17, 240), (*RED_BRIGHT, 255), (255, 150, 120, 255), (*RED_BRIGHT, 255), (*RED, 160)),  # hover
    ((140, 20, 22, 248), (255, 140, 110, 255), (255, 230, 220, 255), (255, 200, 180, 255), (*RED_BRIGHT, 180)),  # pressed
    ((14, 14, 16, 160), (*STEEL_DIM, 255), (*STEEL, 255), (*STEEL_DIM, 255), None),               # disabled
    ((120, 20, 24, 245), (*RED_BRIGHT, 255), (255, 200, 180, 255), (255, 170, 150, 255), (*RED, 130)),  # highlighted
    ((170, 28, 30, 250), (255, 150, 120, 255), (255, 235, 225, 255), (255, 210, 190, 255), (*RED_BRIGHT, 180)),  # highlighted-hover
    ((96, 16, 18, 250), (*RED_BRIGHT, 255), (255, 230, 220, 255), (255, 200, 180, 255), (*RED, 160)),  # highlighted-pressed
    ((48, 24, 26, 170), (*STEEL_DIM, 255), (*STEEL, 255), (*STEEL_DIM, 255), None),               # highlighted-disabled
]
for i, (fill, border, rail, stripes, glow) in enumerate(compact):
    menu_button(i * 48, 432, fill, border, rail, stripes, glow, w=48, h=28, cut=5, margin=1.5)

# --- Section header strip: 64x24 at (0,464); 8px sides, 4px top/bottom, uniform middle ------
rect(0, 464, 64, 24, (200, 30, 30, 44))
rect(0, 487, 64, 1, (*RED, 220))
rect(0, 464, 3, 24, (*RED_BRIGHT, 255))

# --- Write 1x and 2x sheets -------------------------------------------------------------------
for scale, name in ((1, "px-ui.png"), (2, "px-ui-2x.png")):
    out = sheet.resize((SHEET_W * scale, SHEET_H * scale), Image.LANCZOS)
    out.save(os.path.join(OUT_DIR, name))
    print("wrote", name, out.size)
