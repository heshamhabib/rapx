#!/usr/bin/env python3
"""Export the classic RA map-environment art (objects, bridges, debris, smudges) to PNG references.

Reads docs/environment-assets.csv (run make_inventory.py first) and writes
artsrc/env-inventory/classic/<TILESET>/<name>.png (4x nearest-neighbour upscale, transparent background)
plus contact sheets artsrc/env-inventory/classic/sheet-<group>.png for a quick look.
Objects: frame 0 (intact) and, when the sprite has one, <name>-damaged.png.
Tile templates are reassembled from their cells.

  python3 artsrc/env-inventory/export_classic.py
"""
import csv
import glob
import os
import subprocess
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ENGINE = os.path.join(ROOT, "engine")
OUT = os.path.join(HERE, "classic")
CSV = os.path.join(ROOT, "docs", "environment-assets.csv")
PAL = {"TEMPERAT": "temperat.pal", "SNOW": "snow.pal", "DESERT": "desert.pal", "INTERIOR": "interior.pal"}
EXT = {"tem": "TEMPERAT", "sno": "SNOW", "des": "DESERT", "int": "INTERIOR"}
SCALE = 4
TILE_CATEGORIES = {"Bridge", "Debris"}


def utility(*args):
    env = dict(os.environ)
    dotnet = os.path.expanduser("~/.dotnet")
    env["PATH"] = dotnet + os.pathsep + env.get("PATH", "")
    env.setdefault("DOTNET_ROOT", dotnet)
    return subprocess.run([os.path.join(ROOT, "utility.sh"), *args], cwd=ENGINE, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def frames(filename, palette):
    """Returns the exported frames of a sprite/tile file as RGBA images (index 0 transparent)."""
    if not utility("--png", filename, palette):
        return []
    stem = os.path.splitext(filename)[0]
    paths = sorted(glob.glob(os.path.join(ENGINE, stem + "-[0-9][0-9][0-9][0-9].png")))
    out = []
    for p in paths:
        im = Image.open(p)
        rgba = im.convert("RGBA")
        if im.mode == "P":
            rgba.putalpha(Image.frombytes("L", im.size, bytes(0 if b == 0 else 255 for b in im.tobytes())))
        out.append(rgba)
        os.remove(p)
    return out


def up(im):
    return im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)


def save(im, tileset, name):
    d = os.path.join(OUT, tileset)
    os.makedirs(d, exist_ok=True)
    up(im).save(os.path.join(d, name + ".png"))


def assemble(cells, w, h):
    im = Image.new("RGBA", (w * 24, h * 24), (0, 0, 0, 0))
    for i, c in enumerate(cells[: w * h]):
        im.alpha_composite(c.crop((0, 0, 24, 24)), ((i % w) * 24, (i // w) * 24))
    return im


def contact_sheet(entries, path, cols=8):
    """entries: [(label, png path)]"""
    if not entries:
        return
    ims = [(lbl, Image.open(p)) for lbl, p in entries]
    cw = max(i.width for _, i in ims) + 16
    ch = max(i.height for _, i in ims) + 40
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGBA", (cw * min(cols, len(ims)), ch * rows), (40, 40, 44, 255))
    d = ImageDraw.Draw(sheet)
    for n, (lbl, im) in enumerate(ims):
        x, y = (n % cols) * cw, (n // cols) * ch
        sheet.alpha_composite(im, (x + 8, y + 8))
        d.text((x + 8, y + ch - 26), lbl, fill=(255, 255, 255, 255))
    sheet.save(path)


def main():
    rows = list(csv.DictReader(open(CSV)))
    jobs = []  # (file, tileset, kind, name, size, category)
    for r in rows:
        if r["kind"] == "object":
            if r["id/actor"].endswith(".Husk"):
                continue  # the burnt frames are exported with the live tree
            for f in r["source_files"].split(", "):
                ext = f.rsplit(".", 1)[-1]
                ts = EXT.get(ext, "TEMPERAT")
                jobs.append((f, ts, "object", r["id/actor"].lower(), r["size_cells"], r["category"]))
        elif r["category"] in TILE_CATEGORIES:
            f = r["source_files"]
            jobs.append((f, r["tileset"], "tile", os.path.splitext(f)[0], r["size_cells"], r["category"]))
    for n in range(1, 7):
        for ext, ts in EXT.items():
            if ts != "INTERIOR":
                jobs += [(f"sc{n}.{ext}", ts, "smudge", f"sc{n}", "1x1", "Smudge"),
                         (f"cr{n}.{ext}", ts, "smudge", f"cr{n}", "1x1", "Smudge")]

    files = sorted({j[0] for j in jobs})
    pals = sorted(set(PAL.values()))
    utility("--extract", *files, *pals)
    groups = {}
    done = set()
    try:
        for f, ts, kind, name, size, cat in jobs:
            if (f, ts) in done:
                continue
            done.add((f, ts))
            fr = frames(f, PAL[ts])
            if not fr:
                print("skip", f)
                continue
            if kind == "tile":
                w, h = (int(v) for v in size.split("x"))
                im = assemble(fr, w, h)
            else:
                im = fr[0]
            save(im, ts, name)
            groups.setdefault(f"{cat}-{ts}", []).append((name, os.path.join(OUT, ts, name + ".png")))
            if kind == "object" and len(fr) > 1:
                # trees: last frame = burnt; buildings: frame 1 = damaged
                dmg = fr[-1] if cat == "Tree" else fr[1]
                save(dmg, ts, name + ("-burnt" if cat == "Tree" else "-damaged"))
    finally:
        for f in files + pals:
            p = os.path.join(ENGINE, f)
            if os.path.exists(p):
                os.remove(p)
    for g, entries in groups.items():
        contact_sheet(entries, os.path.join(OUT, f"sheet-{g.replace(' ', '_')}.png"))
    print(f"exported {len(done)} files to {OUT}")


if __name__ == "__main__":
    main()
