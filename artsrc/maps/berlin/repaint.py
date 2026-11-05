#!/usr/bin/env python3
"""
Repaint pass for the Berlin 1946 backdrop (IDEA-28 step 6): ChatGPT repaints the Blender render piece by piece in
the chosen style (style C), and the pieces are blended back into one picture.

  python3 artsrc/maps/berlin/repaint.py cut        # build/backdrop.png -> build/tiles/*.png + artsrc/prompts/berlin-repaint-prompts.md
  python3 artsrc/prompts/generate_images.py --prompts berlin-repaint-prompts.md --category maps --stop-on-limit
  python3 artsrc/maps/berlin/repaint.py check      # drift score per piece (did ChatGPT move buildings?)
  python3 artsrc/maps/berlin/repaint.py review     # build/review/*.png: render | repaint with the blocked cells in red
                                                   # (look for buildings on open ground; delete the piece to redo it)
  python3 artsrc/maps/berlin/repaint.py assemble   # assets/maps/berlin/paint/*.png -> build/backdrop-painted.png
  python3 artsrc/maps/berlin/cut_backdrop.py --src build/backdrop-painted.png

Pieces are 24 x 16 cells (1536 x 1024 px at 64 px per cell, the size ChatGPT paints) and overlap by 4 cells; the
overlaps are cross-faded. Pieces that drift (score below --min) are left out of the blend, so the render shows
there until they are regenerated (delete the piece and run the generator again).
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
BUILD = os.path.join(HERE, "build")
TILES = os.path.join(BUILD, "tiles")
PAINT = os.path.join(ROOT, "assets", "maps", "berlin", "paint")
PROMPTS = os.path.join(ROOT, "artsrc", "prompts", "berlin-repaint-prompts.md")
PPC = 64
TW, TH = 24, 16          # piece size in cells
OVERLAP = 4
Image.MAX_IMAGE_PIXELS = None

PROMPT = ("A highly detailed hand-painted 2D game map in the pre-rendered style of classic tactics games from around "
          "2000: sharp, clean, richly textured, like a detailed painted diorama, every brick, cobblestone, roof tile, "
          "window frame and piece of rubble readable. Scene: part of central Berlin in 1946, a year after the war. "
          "The attached image is only a rough 3D blockout: use it for WHERE things are, not for how they look. Keep "
          "every footprint exactly: where each building, wall, street, square, bridge and river bank stands, its "
          "outline and size, the camera and the light direction. Open ground in the attached image (streets, "
          "squares, courtyards, parks, rubble lots) must stay open ground: never add a building, wall or roof "
          "there, and never leave out a building that is there. Inside each footprint, redraw the building as rich "
          "real architecture: Berlin apartment houses from 1900 with ornate plaster facades, cornices, balconies, "
          "window surrounds, shop fronts, varied slate and red tile roofs with dormers, chimneys, skylights and "
          "broken roof sections, burnt-out shells with empty window holes, soot and fallen floors inside, collapsed "
          "houses as rubble heaps with broken walls and timber beams; landmarks with their real detail: the Brandenburg Gate "
          "is an open sandstone colonnade, NOT a building: six rows of Doric columns with open passages between "
          "them, a flat attic on top and the bronze chariot with four horses; the Reichstag is a burnt stone palace "
          "with corner towers and the bare steel ribs of its dome; the Victory Column is a tall column with a "
          "golden statue; the tower under construction is a concrete shaft with scaffolding and a crane. On the ground: "
          "cobblestones, bomb craters with scorched rims, wrecked cars, tank traps, street lamps, puddles, weeds, "
          "debris, a muddy cut-down park with tree stumps, the river Spree with stone quay walls. Light: clear "
          "afternoon sun from the top-left, crisp shadows to the bottom-right, natural colours. Camera: straight "
          "down from above; tall things lean up the picture so the south walls are visible, as in the attached "
          "image. The only water is the river Spree where the attached image shows blue-green water: never paint "
          "water, canals or ponds anywhere else (dark ground is a muddy road). No trees (the game adds them), no people, no soldiers, no tanks, no text, no labels, no UI, no "
          "frame, no border, no watermark. Landscape image, aspect ratio 3:2.")


# Added in front of the prompt for pieces that are mostly park (Tiergarten, Platz der Republik): without it ChatGPT
# fills the open ground with small ruins
PARK = ("Most of this piece is a big city park whose trees were cut down for firewood: keep it open and calm, muddy "
        "earth and worn yellow-green grass with tree stumps, wood chips, footpaths, tyre tracks, puddles and a few "
        "bomb craters. No buildings, no ruins, no walls and no rubble heaps in the park.")


def pieces(w_cells, h_cells):
    def starts(total, size):
        step = size - OVERLAP
        s = list(range(0, max(1, total - size) + 1, step))
        if s[-1] + size < total:
            s.append(total - size)
        return s
    return [(x, y) for y in starts(h_cells, TH) for x in starts(w_cells, TW)]


def cut():
    img = Image.open(os.path.join(BUILD, "backdrop.png")).convert("RGB")
    wc, hc = img.width // PPC, img.height // PPC
    os.makedirs(TILES, exist_ok=True)
    for old in glob.glob(os.path.join(TILES, "*.png")):
        os.remove(old)
    lines = ["# RedAlert Project X - Berlin 1946 repaint pieces (ChatGPT, IDEA-28 step 6)", "",
             "Generated by `artsrc/maps/berlin/repaint.py cut`. Do not edit by hand.", "", "## Map style frames", ""]
    import json
    with open(os.path.join(BUILD, "layout.json")) as f:
        ground = json.load(f)["ground"]
    for n, (x, y) in enumerate(pieces(wc, hc), 1):
        name = f"tile-{x:03d}-{y:03d}"
        cells = "".join(row[x:x + TW] for row in ground[y:y + TH])
        prompt = PROMPT
        if (cells.count("s") + cells.count("g")) > 0.4 * len(cells):
            prompt = PARK + " " + PROMPT
        img.crop((x * PPC, y * PPC, (x + TW) * PPC, (y + TH) * PPC)).save(os.path.join(TILES, name + ".png"))
        lines += [f"### {n}. Piece at cell {x},{y}", f"Save as: `berlin/paint/{name}.png`",
                  f"Reference: `artsrc/maps/berlin/build/tiles/{name}.png`", "", "```", prompt, "```", ""]
    with open(PROMPTS, "w") as f:
        f.write("\n".join(lines))
    print(f"{len(pieces(wc, hc))} pieces -> {TILES}, prompts -> {PROMPTS}")


def layout_signal(img):
    """Light and shadow at the scale of houses and streets (band-pass of a small grey copy), normalised."""
    g = img.convert("L").resize((144, 96), Image.LANCZOS)
    a = (np.asarray(g.filter(ImageFilter.GaussianBlur(2))).astype(np.float32)
         - np.asarray(g.filter(ImageFilter.GaussianBlur(12))).astype(np.float32))
    return (a - a.mean()) / (a.std() + 1e-6)


def score(name):
    """Correlation of the layout in the render and in the repainted piece: about 0.75 for a faithful repaint of the
    style frames, below 0 for an unrelated or shifted picture."""
    src = Image.open(os.path.join(TILES, name))
    out = Image.open(os.path.join(PAINT, name)).convert("RGB").resize(src.size, Image.LANCZOS)
    return float((layout_signal(src) * layout_signal(out)).mean())


def check(minimum):
    rows = []
    for path in sorted(glob.glob(os.path.join(PAINT, "tile-*.png"))):
        name = os.path.basename(path)
        s = score(name)
        rows.append((s, name))
        print(f"{name}  {s:.2f}  {'DRIFT' if s < minimum else 'ok'}")
    print(f"{len(rows)} pieces, {sum(1 for s, _ in rows if s < minimum)} below {minimum}")
    return {n for s, n in rows if s >= minimum}


def review():
    """Side-by-side of each piece: the render, and the repaint with the gameplay's blocked cells outlined in red, so
    a painted building on open ground (units would drive through it) is easy to spot."""
    import json
    from PIL import ImageDraw
    with open(os.path.join(BUILD, "layout.json")) as f:
        grid = json.load(f)["grid"]
    out_dir = os.path.join(BUILD, "review")
    os.makedirs(out_dir, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(PAINT, "tile-*.png"))):
        name = os.path.basename(path)
        x0, y0 = (int(v) for v in name[5:-4].split("-"))
        w, h = 1024, 683
        src = Image.open(os.path.join(TILES, name)).convert("RGB").resize((w, h))
        out = Image.open(path).convert("RGB").resize((w, h))
        d = ImageDraw.Draw(out)
        sx, sy = w / TW, h / TH
        for cy in range(TH):
            for cx in range(TW):
                if grid[y0 + cy][x0 + cx] == "#":
                    d.rectangle((cx * sx, cy * sy, (cx + 1) * sx, (cy + 1) * sy), outline=(255, 0, 0))
        sheet = Image.new("RGB", (2 * w, h))
        sheet.paste(src, (0, 0))
        sheet.paste(out, (w, 0))
        sheet.save(os.path.join(out_dir, name))
    print("->", out_dir)


def assemble(minimum):
    base = Image.open(os.path.join(BUILD, "backdrop.png")).convert("RGB")
    acc = np.asarray(base).astype(np.float32) * 1e-3
    wsum = np.full(acc.shape[:2] + (1,), 1e-3, np.float32)
    good = check(minimum)
    pw, ph = TW * PPC, TH * PPC
    ramp = OVERLAP * PPC
    wx = np.minimum(1, np.minimum(np.arange(pw) + 1, pw - np.arange(pw)) / ramp)
    wy = np.minimum(1, np.minimum(np.arange(ph) + 1, ph - np.arange(ph)) / ramp)
    w = (wy[:, None] * wx[None, :])[..., None].astype(np.float32)
    for name in sorted(good):
        x, y = (int(v) for v in name[5:-4].split("-"))
        piece = np.asarray(Image.open(os.path.join(PAINT, name)).convert("RGB").resize((pw, ph), Image.LANCZOS))
        ys, xs = slice(y * PPC, y * PPC + ph), slice(x * PPC, x * PPC + pw)
        acc[ys, xs] += piece.astype(np.float32) * w
        wsum[ys, xs] += w
    out = (acc / wsum).clip(0, 255).astype(np.uint8)
    Image.fromarray(out).save(os.path.join(BUILD, "backdrop-painted.png"))
    print("->", os.path.join(BUILD, "backdrop-painted.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["cut", "check", "review", "assemble"])
    ap.add_argument("--min", type=float, default=0.5, help="lowest layout correlation that counts as no drift")
    a = ap.parse_args()
    {"cut": cut, "check": lambda: check(a.min), "review": review, "assemble": lambda: assemble(a.min)}[a.step]()
