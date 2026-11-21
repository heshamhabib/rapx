#!/usr/bin/env python3
"""
Repaint pass for the Washington D.C. backdrop (IDEA-28): ChatGPT repaints the Blender render piece by piece in the chosen
style , and the pieces are blended back into one picture.

  python3 artsrc/maps/dc/repaint.py cut        # build/backdrop.png -> build/tiles/*.png + artsrc/prompts/dc-repaint-prompts.md
  python3 artsrc/prompts/generate_images.py --prompts dc-repaint-prompts.md --category maps --stop-on-limit
  python3 artsrc/maps/dc/repaint.py check      # drift score per piece (did ChatGPT move buildings?)
  python3 artsrc/maps/dc/repaint.py review     # build/review/*.png: render | repaint with the blocked cells in red
  python3 artsrc/maps/dc/repaint.py assemble   # assets/maps/dc/paint/*.png -> build/backdrop-painted.png
  python3 artsrc/maps/dc/cut_backdrop.py --src build/backdrop-painted.png

Same method as the Berlin repaint: pieces of 24 x 16 cells overlapping by 4, cross-faded; pieces that drift (score
below --min) are left out so the render shows there until they are regenerated.

Start areas: ChatGPT reads a big empty square as a gap to fill and paints trees, lamp posts, statues or even whole
streets of houses into it. Players build there, so the 8 build areas always come from the Blender render (style-A
plaza texture), colour-matched to the repaint round them and feathered over 1.5 cells; the drift score ignores
them too.
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
PAINT = os.path.join(ROOT, "assets", "maps", "dc", "paint")
PROMPTS = os.path.join(ROOT, "artsrc", "prompts", "dc-repaint-prompts.md")
PPC = 64
TW, TH = 24, 16          # piece size in cells
OVERLAP = 4
Image.MAX_IMAGE_PIXELS = None

# The prompt is put together per piece: it only names what is really in that piece. Naming every landmark in every
# prompt ("where the attached image has them") made ChatGPT invent small Capitols, Pentagons and canals in ordinary
# city blocks.
STYLE = ("A highly detailed, realistic pre-rendered 2D map for a real-time strategy game: part of central Washington "
         "D.C. at golden sunset, rich and cinematic like a high-end modern RTS map, every window, cornice, roof, tree, "
         "car and lamp readable, true real-world proportions. Warm golden-orange low sunlight, long soft shadows, "
         "glowing warm street lamps just switched on, a hint of violet in the shadows.")
KEEP = ("The attached image is a 3D blockout: use it for WHERE things are, not for how they look. Keep every "
        "footprint exactly: where each building, street, lawn, path and shore stands, its outline and size, the "
        "camera and the light direction. Open ground in the attached image (streets, sidewalks, plazas, lawns, "
        "woods) must stay open ground: never add a building, wall or roof there, and never leave out a building that "
        "is there. Draw only what the attached image shows: never add a building or landmark that is not in it.")
CITY = ("Inside each building footprint, redraw the building as real Washington D.C. architecture: neoclassical "
        "limestone and granite federal buildings with columns and cornices, red-brick rowhouses and offices with "
        "flat roofs, a few modern glass office blocks; height limits keep them low and wide.")
LANDMARKS = {
    "whitehouse": "the White House: a white neoclassical mansion with its south portico of columns, on a green lawn",
    "capitol": "the US Capitol in white marble with its great dome and two long wings",
    "lincoln": "the Lincoln Memorial: a white marble Greek temple ringed by Doric columns on a stepped base",
    "monument": "the Washington Monument: a tall white marble obelisk on a round grassy knoll ringed by flagpoles",
    "jefferson": "the Jefferson Memorial: a round white marble temple with a shallow dome and a columned portico",
}
NO_LANDMARK = ("There is no famous landmark in this piece: only ordinary city buildings, lawns and trees. Never draw a "
               "domed capitol, an obelisk, a marble temple or a famous white mansion here.")
GROUND = ("On the ground: wide dark asphalt avenues with white lane markings and crosswalks, parked cars and taxis "
          "where the attached image has them, light paving, street lamps, lush green lawns with gravel paths.")
WATER = "Water is calm and reflects the golden sky, exactly where the attached image shows water, with stone banks."
NO_WATER = "There is no water in this piece: never paint a river, canal, pool or pond."
TAIL = ("Camera: straight down from above; tall things lean up the picture so the south walls are visible, as in "
        "the attached image. No people, no soldiers, no tanks, no logos, no labels, no UI, no frame, no border, no "
        "watermark. Landscape image, aspect ratio 3:2.")


def piece_prompt(L, x, y):
    """The prompt for the piece at cell x, y: names only the landmarks it holds and water only where it has some."""
    found = []
    for key, r in L["landmarks"].items():
        box = r
        ox = min(box[2], x + TW) - max(box[0], x)
        oy = min(box[3], y + TH) - max(box[1], y)
        if ox > 1.5 and oy > 1.5:
            found.append(key)
    # Water within 3 cells counts too: the picture is sheared, so the harbour shows a little north of its cells
    water = any("~" in row[max(0, x - 3):x + TW + 3] for row in L["grid"][max(0, y - 3):y + TH + 3])
    parts = [STYLE, KEEP, CITY]
    if found:
        parts.append("This piece shows " + "; and ".join(LANDMARKS[k] for k in found) + ", exactly where the "
                     "attached image has it; no other landmark.")
    else:
        parts.append(NO_LANDMARK)
    parts += [GROUND, WATER if water else NO_WATER, TAIL]
    return " ".join(parts)


# In front of the prompt for pieces that are mostly a start area: without it ChatGPT fills the open ground
BASE = ("Most of this piece is a large empty green lawn where players will build their base: keep it completely open, "
        "flat and calm, only grass in the golden light. No buildings, no trees, no paths, no objects on the lawn.")


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
    lines = ["# RedAlert Project X - Washington D.C. repaint pieces (ChatGPT, IDEA-28)", "",
             "Generated by `artsrc/maps/dc/repaint.py cut`. Do not edit by hand.", "", "## Map style frames", ""]
    import json
    with open(os.path.join(BUILD, "layout.json")) as f:
        L = json.load(f)
    ground = L["ground"]
    for n, (x, y) in enumerate(pieces(wc, hc), 1):
        name = f"tile-{x:03d}-{y:03d}"
        cells = "".join(row[x:x + TW] for row in ground[y:y + TH])
        prompt = piece_prompt(L, x, y)
        if cells.count("y") > 0.5 * len(cells):                 # mostly a build area (lawn), not a landmark plaza
            prompt = BASE + " " + prompt
        img.crop((x * PPC, y * PPC, (x + TW) * PPC, (y + TH) * PPC)).save(os.path.join(TILES, name + ".png"))
        lines += [f"### {n}. Piece at cell {x},{y}", f"Save as: `dc/paint/{name}.png`",
                  f"Reference: `artsrc/maps/dc/build/tiles/{name}.png`", "", "```", prompt, "```", ""]
    with open(PROMPTS, "w") as f:
        f.write("\n".join(lines))
    print(f"{len(pieces(wc, hc))} pieces -> {TILES}, prompts -> {PROMPTS}")


LOT = 10                 # half size of a build area (layout.py)


def lot_mask(scale=1):
    """Build areas of the 8 starts, in map cells (or `scale` pixels per cell): 1 inside, 0 outside."""
    import json
    with open(os.path.join(BUILD, "layout.json")) as f:
        L = json.load(f)
    m = np.zeros((L["cells"][1] * scale, L["cells"][0] * scale), np.float32)
    for sx, sy in L["spawns"]:
        m[max(0, (sy - LOT) * scale):(sy + LOT) * scale, max(0, (sx - LOT) * scale):(sx + LOT) * scale] = 1
    return m


def layout_signal(img):
    """Light and shadow at the scale of houses and streets (band-pass of a small grey copy), normalised."""
    g = img.convert("L").resize((144, 96), Image.LANCZOS)
    a = (np.asarray(g.filter(ImageFilter.GaussianBlur(2))).astype(np.float32)
         - np.asarray(g.filter(ImageFilter.GaussianBlur(12))).astype(np.float32))
    return (a - a.mean()) / (a.std() + 1e-6)


_LOTS = None


def score(name):
    """Correlation of the layout in the render and in the repainted piece outside the build areas (those come from
    the render anyway): about 0.75 for a faithful repaint, below 0 for an unrelated or shifted picture. A piece that
    is nearly all build area scores 1."""
    global _LOTS
    if _LOTS is None:
        _LOTS = lot_mask()
    x, y = (int(v) for v in name[5:-4].split("-"))
    keep = 1 - _LOTS[y:y + TH, x:x + TW]
    if keep.mean() < 0.15:
        return 1.0
    keep = np.asarray(Image.fromarray((keep * 255).astype(np.uint8)).resize((144, 96), Image.BILINEAR), np.float32) / 255
    src = Image.open(os.path.join(TILES, name))
    out = Image.open(os.path.join(PAINT, name)).convert("RGB").resize(src.size, Image.LANCZOS)
    a, b = layout_signal(src), layout_signal(out)
    return float((a * b * keep).sum() / keep.sum())


def invented_water(name):
    """Share of the piece that ChatGPT painted as water (blue, saturated) on cells that are land in the layout."""
    import json
    with open(os.path.join(BUILD, "layout.json")) as f:
        grid = json.load(f)["grid"]
    x, y = (int(v) for v in name[5:-4].split("-"))
    out = Image.open(os.path.join(PAINT, name)).convert("HSV").resize((TW * 8, TH * 8))
    hsv = np.asarray(out).astype(np.float32) / 255
    blue = (hsv[..., 0] * 360 > 170) & (hsv[..., 0] * 360 < 230) & (hsv[..., 1] > 0.35) & (hsv[..., 2] > 0.25)
    land = np.repeat(np.repeat(np.array([[c != "~" for c in row[x:x + TW]] for row in grid[y:y + TH]]), 8, 0), 8, 1)
    # Lean: high things are drawn up to ~2 cells north of their cells; ignore a 2-cell margin round real water
    from scipy import ndimage
    near = ndimage.binary_dilation(~land, iterations=16)
    return float((blue & land & ~near).mean())


def check(minimum):
    rows = []
    for path in sorted(glob.glob(os.path.join(PAINT, "tile-*.png"))):
        name = os.path.basename(path)
        s = score(name)
        w = invented_water(name)
        if w > 0.01:
            print(f"{name}  invented water {w * 100:.1f} % -> redo")
            s = min(s, -1.0)
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
    out = acc / wsum
    # Build areas from the render, colour-matched to the repaint in a band just inside their edge, feathered
    lots = lot_mask()
    feather = np.asarray(Image.fromarray((lots * 255).astype(np.uint8)).resize(base.size, Image.NEAREST), np.float32) / 255
    from scipy import ndimage
    inner = ndimage.distance_transform_edt(feather > 0.5) / PPC            # cells from the lot edge, inside
    band = (inner > 0.5) & (inner < 3.0)
    render = np.asarray(base).astype(np.float32)
    gain = out[band].mean(0) / np.maximum(render[band].mean(0), 1)
    w_lot = np.clip((inner - 0.25) / 1.5, 0, 1)[..., None]
    out = out * (1 - w_lot) + (render * gain) * w_lot
    print(f"build areas from the render, colour gain {np.round(gain, 3)}")
    out = out.clip(0, 255).astype(np.uint8)
    Image.fromarray(out).save(os.path.join(BUILD, "backdrop-painted.png"))
    print("->", os.path.join(BUILD, "backdrop-painted.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["cut", "check", "review", "assemble"])
    ap.add_argument("--min", type=float, default=0.5, help="lowest layout correlation that counts as no drift")
    a = ap.parse_args()
    {"cut": cut, "check": lambda: check(a.min), "review": review, "assemble": lambda: assemble(a.min)}[a.step]()
