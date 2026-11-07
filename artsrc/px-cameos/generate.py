#!/usr/bin/env python3
"""
Generates the large production-tile cameos used by the RAPX sidebar.

For every `icon` sequence in mods/rapx/sequences/*.yaml this writes a 240x160 PNG
(2x of the 120x80 tile) to mods/rapx/bits/hd/icons/ and a matching `px-icon`
sequence to mods/rapx/sequences/hd-icons.yaml (GENERATED - edit this script, not that file).

- Structures with HD art in mods/rapx/bits/hd/<image>.png are re-rendered from it: the
  PlayerColorShift green is recoloured to the UI red and the building is lit on a dark backdrop.
- Jets use their render in assets/jets/ (mapping in artsrc/jets/make_jets.py).
- Units with concept art in assets/units/<image>.png (a render on a plain white background,
  named after the sequence image, e.g. 2tnk.png) are cut out of it and staged the same way.
- Painted Red Alert 2-style cameos in assets/cameos/<image>.png (from artsrc/prompts/cameo-prompts.md) are used for
  images without HD art (cover-cropped to 3:2 and scaled to the tile). Buildings with HD art always use their render,
  so all building tiles keep one style.
- Everything else uses the classic cameo, exported with OpenRA.Utility, with the baked-in name
  text cropped off (the tile draws its own label) and upscaled.

The stock-size `icon` sequence (64x48, drawn by the observer and support-power widgets, which ignore sequence Scale)
is also replaced by a downscaled copy of the HD cameo in mods/rapx/bits/hd/icons/small/, for every image with HD or
painted art. Images that only have the classic cameo keep their classic `icon`.

Run (needs the RA content installed and the engine built): python3 artsrc/px-cameos/generate.py
"""

import colorsys
import glob
import os
import re
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MOD = os.path.join(ROOT, "mods", "rapx")
HD = os.path.join(MOD, "bits", "hd")
CONCEPTS = os.path.join(ROOT, "assets", "units")
PAINTED = os.path.join(ROOT, "assets", "cameos")
OUT = os.path.join(HD, "icons")
SMALL = os.path.join(OUT, "small")
# National jets (artsrc/jets/make_jets.py): image jet.<id> -> render assets/jets/<file>.png
sys.path.insert(0, os.path.join(ROOT, "artsrc", "jets"))
from make_jets import JETS  # noqa: E402
JET_ART = {"jet." + j[0]: j[1] for j in JETS}
ENGINE = os.path.join(ROOT, "engine")
W, H = 240, 160
TILESETS = ("TEMPERAT", "SNOW", "DESERT", "INTERIOR")


def parse_icon_sequences():
    """Yield (image, sequence, filename) for every icon sequence. The yaml is tab-indented."""
    found = []
    for path in sorted(glob.glob(os.path.join(MOD, "sequences", "*.yaml"))):
        if os.path.basename(path).startswith("hd-"):
            continue
        image = seq = None
        for line in open(path):
            line = line.rstrip("\n").split("#")[0].rstrip()
            if not line:
                continue
            depth = len(line) - len(line.lstrip("\t"))
            key, _, value = line.strip().partition(":")
            if depth == 0:
                image, seq = key, None
            elif depth == 1:
                seq = key
            elif depth == 2 and seq == "icon" and key == "Filename" and not image.startswith("^"):
                found.append((image, seq, value.strip()))
    return found


def recolor(im, hue=(0.25, 0.45), min_s=0.35):
    """Team green -> the UI red. Renders of downloaded models (min_s low, the game's 0.22-0.45 hue range) keep their
    lit and shaded team areas in paler greens, which the stricter defaults for concept art would leave green."""
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if hue[0] < h < hue[1] and s > min_s:
                nr, ng, nb = colorsys.hsv_to_rgb(0.0, min(1, s * 0.95), v * 0.92)
                px[x, y] = (int(nr * 255), int(ng * 255), int(nb * 255), a)
    return im


def backdrop():
    k = W / 240  # 1 for the sidebar tile; make_catalogue_art.py renders larger
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(38 - 20 * t), int(40 - 21 * t), int(47 - 24 * t), 255))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, W, round(20 * k)):
        gd.line([(x, 0), (x, H)], fill=(255, 255, 255, 10), width=round(k))
    for y in range(0, H, round(20 * k)):
        gd.line([(0, y), (W, y)], fill=(255, 255, 255, 10), width=round(k))
    bg.alpha_composite(grid)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([30 * k, 14 * k, 210 * k, 150 * k], fill=(226, 38, 38, 46))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(26 * k)))
    return bg


def cut_out_white(im):
    """Makes the white backdrop of a concept render transparent (only white connected to the border)."""
    import numpy as np
    from scipy.ndimage import binary_dilation, label
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    lo = a.min(-1)
    bright = lo > 232
    labels, _ = label(bright)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    bg = np.isin(labels, border[border > 0])
    # Soft 1-2px edge: near-white pixels touching the backdrop fade out with their brightness
    edge = binary_dilation(bg, iterations=2) & ~bg
    alpha = np.where(bg, 0.0, 1.0)
    alpha[edge] = np.clip((255 - lo[edge]) / 60, 0, 1)
    rgba = np.dstack([a, alpha * 255]).astype(np.uint8)
    return Image.fromarray(rgba).copy()


def painted_source(image):
    # Buildings with HD art use their own render, so every building tile shares one style (dark backdrop, lit model)
    if os.path.exists(os.path.join(HD, image + ".png")):
        return None
    path = os.path.join(PAINTED, image + ".png")
    return path if os.path.exists(path) else None


def painted_cameo(image):
    """Cover-crops a painted cameo to the tile's 3:2 aspect and scales it to W x H."""
    im = Image.open(painted_source(image)).convert("RGBA")
    scale = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left, top = (im.width - W) // 2, (im.height - H) // 2
    img = im.crop((left, top, left + W, top + H)).filter(ImageFilter.UnsharpMask(radius=1.5, percent=50, threshold=2))
    return img


# Units rendered from downloaded models (not their concept art): a cameo view of the model itself, rendered on a
# transparent background by artsrc/units/meshes/render_cameo.py (same low three-quarter angle as the concepts)
RENDERS = os.path.join(ROOT, "assets", "units", "renders")


def source_art(image):
    render = os.path.join(RENDERS, image + ".png")
    if os.path.exists(render):
        im = Image.open(render).convert("RGBA")
        return im.crop(im.getbbox())
    concept = os.path.join(CONCEPTS, image + ".png")
    if image in JET_ART:
        concept = os.path.join(ROOT, "assets", "jets", JET_ART[image] + ".png")
    if os.path.exists(concept):
        return cut_out_white(Image.open(concept))
    hd = os.path.join(HD, image + ".png")
    return Image.open(hd).convert("RGBA") if os.path.exists(hd) else None


def hd_cameo(image):
    rendered = os.path.exists(os.path.join(RENDERS, image + ".png"))
    b = recolor(source_art(image), (0.22, 0.45), 0.1) if rendered else recolor(source_art(image))
    b = b.crop(b.getbbox())
    scale = min((W * 0.84) / b.width, (H * 0.84) / b.height)
    b = b.resize((int(b.width * scale), int(b.height * scale)), Image.LANCZOS)
    img = backdrop()
    k = W / 240
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cx, by = W // 2, H - round(10 * k)
    ImageDraw.Draw(sh).ellipse([cx - b.width * 0.45, by - 16 * k, cx + b.width * 0.45, by + 4 * k], fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 * k)))
    img.alpha_composite(b, (cx - b.width // 2, by - b.height))
    return img


def utility(*args):
    env = dict(os.environ)
    dotnet = os.path.expanduser("~/.dotnet")
    env["PATH"] = dotnet + os.pathsep + env.get("PATH", "")
    env.setdefault("DOTNET_ROOT", dotnet)
    subprocess.run([os.path.join(ROOT, "utility.sh"), *args], cwd=ENGINE, env=env, check=True,
                   stdout=subprocess.DEVNULL)


def classic_cameos(filenames):
    """Export classic cameos to RGBA images, keyed by filename. Temporary files live in engine/."""
    utility("--extract", "temperat.pal", *filenames)
    result = {}
    try:
        for f in filenames:
            utility("--png", f, "temperat.pal")
            png = os.path.join(ENGINE, f[:-4] + "-0000.png")
            result[f] = Image.open(png).convert("RGBA")
            os.remove(png)
    finally:
        for f in list(filenames) + ["temperat.pal"]:
            if os.path.exists(os.path.join(ENGINE, f)):
                os.remove(os.path.join(ENGINE, f))
    return result


def upscale(cameo):
    # rows 38+ hold the baked-in name; crop to the tile's 3:2 aspect and upscale
    art = cameo.crop((3, 0, 60, 38))
    art = art.resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    vignette = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vignette).ellipse([-60, -50, W + 60, H + 50], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(30))
    dark = Image.new("RGBA", (W, H), (8, 8, 10, 255))
    return Image.composite(art, Image.blend(dark, art, 0.55), vignette)


def sequence(seq, path, scale):
    lines = [f"\t{seq}:", f"\t\tFilename: {path}", "\t\tTilesetFilenames:"]
    lines += [f"\t\t\t{t}: {path}" for t in TILESETS]
    return lines + ["\t\tStart: 0", "\t\tLength: 1", "\t\tFacings: 1", "\t\tOffset: 0,0", f"\t\tScale: {scale}"]


def main():
    os.makedirs(SMALL, exist_ok=True)
    entries = parse_icon_sequences()
    has_painted = {image for image, _, _ in entries if painted_source(image)}
    has_art = {image for image, _, _ in entries if image in has_painted or source_art(image) is not None}
    classic = sorted({f for image, _, f in entries if image not in has_art and not f.endswith(".png")})
    cameos = classic_cameos(classic)

    lines = ["# Large production-tile cameos (RedAlert Project X).",
             "# GENERATED by artsrc/px-cameos/generate.py - edit that script, not this file.", ""]
    by_image = {}
    for image, seq, f in entries:
        by_image.setdefault(image, []).append((seq, f))

    for image in sorted(by_image):
        lines.append(image + ":")
        for seq, f in by_image[image]:
            name = os.path.basename(f.split("|")[-1])[:-4] + ".png"
            if image in has_painted:
                img = painted_cameo(image)
                if f.startswith("ra|") and f.endswith(".png"):
                    img.resize((64, 48), Image.LANCZOS).save(os.path.join(MOD, f[3:]))
            elif image in has_art:
                img = hd_cameo(image)
                if f.startswith("ra|") and f.endswith(".png"):
                    # New buildings have no classic cameo: their stock-size `icon` is made from the HD one too
                    img.resize((64, 48), Image.LANCZOS).save(os.path.join(MOD, f[3:]))
            else:
                img = upscale(cameos[f])
            img.convert("RGBA").save(os.path.join(OUT, name))
            path = "ra|bits/hd/icons/" + name
            lines += sequence(f"px-{seq}", path, 0.5)
            if image in has_art and not f.endswith(".png"):
                img.convert("RGBA").resize((64, 48), Image.LANCZOS).save(os.path.join(SMALL, name))
                lines += sequence(seq, "ra|bits/hd/icons/small/" + name, 1)
        lines.append("")

    with open(os.path.join(MOD, "sequences", "hd-icons.yaml"), "w") as out:
        out.write("\n".join(lines))
    print(f"wrote {len(entries)} cameos ({len(entries) - len(classic)} from HD art)")


if __name__ == "__main__":
    main()
