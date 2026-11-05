#!/usr/bin/env python3
"""
Turns the AI-made map environment art in assets/env/ into HD sprites for the classic map objects.

Inputs (written by artsrc/prompts/generate_images.py, see env-prompts.md / env-sheets.md):
  assets/env/trees/<id>-<terrain>.png   living tree (left half) + burnt tree (right half) on magenta
  assets/env/props/<id>[-<terrain>].png single object on magenta (rocks, ice, boxes, poles, crates, mine...)
  assets/env/civilian/<id>[-<terrain>].png  building intact (left) + damaged (right), or a single field / haystack
  assets/env/tech/<id>.png              tech building intact (left) + damaged (right)
  assets/env/smudges/<scorch|crater>-<terrain>.png  six decals in a 3 x 2 grid -> sc1..sc6 / cr1..cr6
  assets/env/walls/<id>.png             wall pieces -> the 16 connection frames (artsrc/env/make_walls.py)
  assets/env/tiles/<tileset>/<template>.png  bridge / ford / debris tiles -> mods/rapx/bits/hd/tiles (make_tiles.py)

For every image it
  - keys out the magenta background (its darker magenta cast shadow becomes a soft black shadow),
  - splits two-version images and aligns the second (burnt) half onto the first,
  - scales the object to the size of the classic sprite (artsrc/env-inventory/classic/<TILESET>/<id>.png,
    exported at 4x by export_classic.py) and places its base where the classic object's base is,
and writes mods/rapx/bits/hd/env/<id>[-<terrain>][-burnt].png.

Sequences can't mix scales per tileset, so a tileset whose HD render hasn't arrived yet gets the classic
sprite upscaled to the same density (<id>-<terrain>-classic.png); it is replaced automatically once the
render lands. Then it regenerates
  mods/rapx/sequences/hd-env.yaml  overrides the classic sequences (merged on top of decorations.yaml / misc.yaml)
  mods/rapx/rules/hd-env.yaml      HD actors drawn with the `player` palette switch to `terrain`, so the
                                   team colour shift (PlayerColorShift) doesn't repaint their greens

Incremental: an image is only reprocessed when its source is newer than the output (--force redoes all).
Rerun whenever new renders land in assets/env/.

  python3 artsrc/env/make_env.py [--force] [--only t01,rock1] [--preview]
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, PngImagePlugin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "buildings"))
from process_building import align, key, resize, shift  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_tiles import process_tiles  # noqa: E402
from make_walls import process_walls  # noqa: E402

ASSETS = os.path.join(ROOT, "assets", "env")
CLASSIC = os.path.join(ROOT, "artsrc", "env-inventory", "classic")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "env")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-env.yaml")
RULES = os.path.join(ROOT, "mods", "rapx", "rules", "hd-env.yaml")
PREVIEW = os.path.join(HERE, "preview")
CLASSIC_SEQUENCES = [os.path.join(ROOT, "mods", "rapx", "sequences", f) for f in ("decorations.yaml", "misc.yaml", "structures.yaml")]
RULE_FILES = glob.glob(os.path.join(ROOT, "mods", "rapx", "rules", "*.yaml"))

DENSITY = 3.0          # sprite pixels per world pixel (same as the HD buildings/units)
CLASSIC_SCALE = 4      # export_classic.py upscale factor
SHADOW_OPACITY = 0.55
TERRAINS = {"temperate": "TEMPERAT", "snow": "SNOW", "desert": "DESERT", "interior": "INTERIOR"}
TILESETS = ["TEMPERAT", "SNOW", "DESERT", "INTERIOR"]
FALLBACK_ORDER = ["TEMPERAT", "SNOW", "DESERT", "INTERIOR"]

# Classic sprite to fit to, when it isn't named like the render
CLASSIC_NAME = {"scrate": "crate", "wcrate": "moneycrate"}
# Renders that are not used: ctflag is an animated, team-coloured flag; the windmill (turning sails), lighthouse
# (sweeping beam) and pumpjack v19 (nodding) keep their classic animations until they get animated HD versions
# (IDEA-22 phase 4)
SKIP = {"ctflag", "windmill", "lhus", "v19"}
# Size tweaks on top of the classic fit (1.0 = same visual size as the classic sprite)
EXTRA_SCALE = {}

TREE = re.compile(r"^tc?\d\d$")
# Flat civilian objects (fields, haystacks, igloos): one image, no damaged version
FIELDS = {"v12", "v13", "v14", "v15", "v16", "v17", "v18", "rice"}
# Civilian and tech buildings (filled by collect()): intact + damaged halves -> idle / damaged-idle
BUILDINGS = set()


def sequence_map(image_id):
    """{sequence image: {sequence: frame}} - frame 0 = render (left half), 1 = second half (burnt)."""
    if TREE.match(image_id):
        return {image_id: {"idle": 0}, f"{image_id}.husk": {"idle": 1}}
    if image_id.startswith("utilpol"):
        return {image_id: {"idle": 0, "damaged-idle": 0}}
    if image_id in ("wcrate", "scrate"):
        return {image_id: {"idle": 0, "land": 0}}
    if image_id in FIELDS:
        return {image_id: {"idle": 0, "damaged-idle": 0}}
    if image_id in BUILDINGS:
        return {image_id: {"idle": 0, "damaged-idle": 1}}
    return {image_id: {"idle": 0}}


def parse_name(path):
    """assets/env/trees/t01-snow.png -> ('t01', 'SNOW' or None)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r"^(.+?)-(temperate|snow|desert|interior)$", stem)
    return (m.group(1), TERRAINS[m.group(2)]) if m else (stem, None)


def classic_sequences():
    """{image: {sequence: [filenames...]}} of the classic sequences we override (to know which tilesets have art)."""
    result = {}
    for path in CLASSIC_SEQUENCES:
        image = seq = None
        for line in open(path, encoding="utf-8"):
            if re.match(r"^[^\s#][^:]*:\s*$", line):
                image, seq = line.strip()[:-1], None
                result.setdefault(image, {})
            elif image and re.match(r"^\t[^\t#][^:]*:\s*$", line):
                seq = line.strip()[:-1]
            elif image and seq and re.match(r"^\t\t\t?(Filename|[A-Z]+):", line.lstrip("\n")):
                value = line.split(":", 1)[1].strip()
                if value:
                    result[image].setdefault(seq, []).append(value)
    return result


def tileset_specific(image_id, classic):
    """False when the classic art is one .shp shared by every tileset."""
    files = [f for seqs in classic.get(image_id, {}).values() for f in seqs]
    return not files or not all(f.lower().endswith(".shp") for f in files)


def classic_path(image_id, tileset, frame):
    name = CLASSIC_NAME.get(image_id, image_id)
    suffix = ["", "-burnt" if TREE.match(image_id) else "-damaged"][frame]
    order = ([tileset] if tileset else []) + FALLBACK_ORDER
    for ts in order:
        p = os.path.join(CLASSIC, ts, f"{name}{suffix}.png")
        if os.path.exists(p):
            return p, ts
    return None, None


def classic_rgba(path):
    """Classic export -> float RGBA; the shadow (bright green in the export) becomes translucent black."""
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255
    green = (a[..., 1] > 0.9) & (a[..., 0] < 0.2) & (a[..., 2] < 0.2) & (a[..., 3] > 0)
    a[green] = (0, 0, 0, 0.5)
    return a, (a[..., 3] > 0.5) & ~green


def bbox(mask):
    ys, xs = np.nonzero(mask)
    return xs.min(), xs.max() + 1, ys.min(), ys.max() + 1


def save_png(arr, path, offset):
    """Pads the sprite so `offset` is baked in (sequences share one Offset across tilesets) and saves it."""
    ox, oy = offset
    h, w = arr.shape[:2]
    padded = np.zeros((h + 2 * abs(oy), w + 2 * abs(ox), 4), np.uint8)
    padded[2 * max(oy, 0):2 * max(oy, 0) + h, 2 * max(ox, 0):2 * max(ox, 0) + w] = arr
    arr, offset = padded, (0, 0)
    info = PngImagePlugin.PngInfo()
    info.add_text("rapx-offset", json.dumps(offset))
    Image.fromarray(arr).save(path, optimize=True, pnginfo=info)


def load_offset(path):
    return tuple(json.loads(Image.open(path).text["rapx-offset"]))


def process_render(src, image_id, tileset, outs, log):
    """Keys, fits and saves one render. outs = output path per frame (1 or 2)."""
    img = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255
    h, w, _ = img.shape
    halves = [img[:, :w // 2], img[:, w // 2:w // 2 * 2]] if w > 1.6 * h else [img]
    keyed = [key(half, SHADOW_OPACITY) for half in halves]
    if len(keyed) == 2:
        dy, dx = align(keyed[0][1], keyed[1][1])
        keyed[1] = (shift(keyed[1][0], dy, dx), shift(keyed[1][1], dy, dx))

    ref, ref_ts = classic_path(image_id, tileset, 0)
    if not ref:
        log(f"  {image_id}: no classic sprite to fit to, skipped")
        return False
    _, cmask = classic_rgba(ref)
    fh, fw = cmask.shape
    k = DENSITY / CLASSIC_SCALE
    c0, c1, r0, r1 = bbox(cmask)
    # Classic object: size and base centre relative to the frame centre, in HD sprite pixels
    cw, ch = (c1 - c0) * k, (r1 - r0) * k
    base_rel = (((c0 + c1) / 2 - fw / 2) * k, (r1 - fh / 2) * k)

    bx0, bx1, by0, by1 = bbox(keyed[0][1] > 0.5)
    # Match the visual area (AI renders don't keep the classic aspect exactly)
    scale = np.sqrt(cw * ch / ((bx1 - bx0) * (by1 - by0))) * EXTRA_SCALE.get(image_id, 1.0)

    visible = np.any([rgba[..., 3] > 0.02 for rgba, _ in keyed], axis=0)
    x0, x1, y0, y1 = bbox(visible)
    x0, x1, y0, y1 = min(x0, bx0), max(x1, bx1), min(y0, by0), max(y1, by1)
    for (rgba, _), out in zip(keyed, outs):
        final, size = resize(rgba[y0:y1, x0:x1], scale)
        # Offset that puts the object's base centre where the classic one is (sprite is drawn centred)
        hd_base = (((bx0 + bx1) / 2 - x0) * scale - size[0] / 2, (by1 - y0) * scale - size[1] / 2)
        offset = (round(base_rel[0] - hd_base[0]), round(base_rel[1] - hd_base[1]))
        save_png(final, out, offset)
    log(f"  {os.path.relpath(src, ROOT)} -> {size[0]}x{size[1]}, scale {scale:.3f}, offset {offset}, fit to {ref_ts}")
    return True


def process_classic(image_id, tileset, frame, out):
    """Classic sprite upscaled to DENSITY (stand-in until the HD render for this tileset arrives)."""
    path, _ = classic_path(image_id, tileset, frame)
    if not path:
        return False
    rgba, _ = classic_rgba(path)
    final, _ = resize(rgba, DENSITY / CLASSIC_SCALE)
    save_png(final, out, (0, 0))
    return True


def stale(src, out, force):
    return force or not os.path.exists(out) or os.path.getmtime(src) > os.path.getmtime(out)


def collect():
    """{image_id: {tileset or None: render path}}"""
    renders = {}
    for group in ("trees", "props", "civilian", "tech"):
        if group in ("civilian", "tech"):
            BUILDINGS.update(parse_name(p)[0] for p in glob.glob(os.path.join(ASSETS, group, "*.png")))
        for path in sorted(glob.glob(os.path.join(ASSETS, group, "*.png"))):
            image_id, ts = parse_name(path)
            if image_id not in SKIP:
                renders.setdefault(image_id, {})[ts] = path
    return renders


def classic_tilesets(image_id):
    name = CLASSIC_NAME.get(image_id, image_id)
    return [ts for ts in TILESETS if os.path.exists(os.path.join(CLASSIC, ts, f"{name}.png"))]


def actors_with_image(image_id):
    """Rule actors drawn with this image: <ID>: blocks plus any actor with `Image: <id>`."""
    actors = []
    for path in RULE_FILES:
        if os.path.basename(path).startswith("hd-"):
            continue
        actor, palette = None, {}
        for line in open(path, encoding="utf-8"):
            m = re.match(r"^([^\s#^][^:]*):\s*$", line)
            if m:
                actor = m.group(1)
                if actor.lower() == image_id:
                    actors.append((actor, path))
            elif actor and re.match(r"^\t\tImage:\s*" + re.escape(image_id) + r"\s*$", line, re.I):
                actors.append((actor, path))
    return actors


SMUDGES = {"scorch": ("scorches", "sc"), "crater": ("craters", "cr")}


def process_smudges(force, log):
    """Cuts each 3 x 2 decal sheet into its six smudges, sized like the classic ones. Returns sequence yaml lines."""
    files = {}  # (image, sequence) -> {tileset: output}
    for path in sorted(glob.glob(os.path.join(ASSETS, "smudges", "*.png"))):
        kind, ts = parse_name(path)
        if kind not in SMUDGES or not ts:
            continue
        image, prefix = SMUDGES[kind]
        tag = "temperate" if ts == "TEMPERAT" else ts.lower()
        outs = [os.path.join(OUT, f"{prefix}{n}-{tag}.png") for n in range(1, 7)]
        if force or any(stale(path, o, False) for o in outs):
            img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255
            h, w, _ = img.shape
            for n, out in enumerate(outs):
                r, c = divmod(n, 3)
                cell = img[h * r // 2:h * (r + 1) // 2, w * c // 3:w * (c + 1) // 3]
                rgba, mask = key(cell, SHADOW_OPACITY)
                if not np.any(rgba[..., 3] > 0.05):
                    log(f"  {os.path.relpath(path, ROOT)} cell {n + 1} is empty, skipped")
                    continue
                x0, x1, y0, y1 = bbox(rgba[..., 3] > 0.05)
                ref, _ = classic_path(f"{prefix}{n + 1}", ts, 0)
                _, cmask = classic_rgba(ref)
                c0, c1, r0, r1 = bbox(cmask)
                k = DENSITY / CLASSIC_SCALE
                scale = np.sqrt((c1 - c0) * k * (r1 - r0) * k / ((x1 - x0) * (y1 - y0)))
                final, _ = resize(rgba[y0:y1, x0:x1], scale)
                save_png(final, out, (0, 0))
            log(f"  {os.path.relpath(path, ROOT)} -> {prefix}1..6 ({tag})")
        for n, out in enumerate(outs):
            if os.path.exists(out):
                files.setdefault((image, f"{prefix}{n + 1}"), {})[ts] = out

    lines, images = [], {}
    for (image, seq), by_ts in sorted(files.items()):
        images.setdefault(image, []).append((seq, by_ts))
    for image, seqs in images.items():
        lines.append(f"{image}:")
        for seq, by_ts in seqs:
            default = by_ts.get("TEMPERAT") or next(iter(by_ts.values()))
            lines += [f"\t{seq}:", f"\t\tFilename: ra|bits/hd/env/{os.path.basename(default)}", "\t\tTilesetFilenames:"]
            lines += [f"\t\t\t{t}: ra|bits/hd/env/{os.path.basename(by_ts[t])}" for t in TILESETS if t in by_ts]
            lines += ["\t\tStart: 0", "\t\tLength: 1", f"\t\tScale: {1 / DENSITY:.4f}", "\t\tOffset: 0,0"]
        lines.append("")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="reprocess everything")
    ap.add_argument("--only", help="comma separated image ids")
    ap.add_argument("--preview", action="store_true", help="write artsrc/env/preview/*.png (classic vs HD)")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    only = set(args.only.split(",")) if args.only else None
    classic = classic_sequences()
    renders = collect()
    entries = {}  # image_id -> {tileset or '*': [frame paths]}
    for image_id, by_ts in sorted(renders.items()):
        frames = max(sequence_map(image_id)[i].get(s, 0) for i in sequence_map(image_id) for s in sequence_map(image_id)[i]) + 1
        specific = tileset_specific(image_id, classic)
        files = {}
        if not specific:
            src = by_ts.get(None) or next(iter(by_ts.values()))
            outs = [os.path.join(OUT, f"{image_id}{['', '-burnt'][f]}.png") for f in range(frames)]
            if (only is None or image_id in only) and stale(src, outs[0], args.force):
                if not process_render(src, image_id, None, outs, print):
                    continue
            if os.path.exists(outs[0]):
                files["*"] = outs
        else:
            for ts in sorted(set(classic_tilesets(image_id)) | {t for t in by_ts if t}):
                tag = ts.lower() if ts != "TEMPERAT" else "temperate"
                src = by_ts.get(ts) or (by_ts.get(None) if ts == (classic_path(image_id, None, 0)[1]) else None)
                if src:
                    outs = [os.path.join(OUT, f"{image_id}-{tag}{['', '-burnt'][f]}.png") for f in range(frames)]
                    if (only is None or image_id in only) and stale(src, outs[0], args.force):
                        process_render(src, image_id, ts, outs, print)
                else:
                    outs = [os.path.join(OUT, f"{image_id}-{tag}-classic{['', '-burnt'][f]}.png") for f in range(frames)]
                    if not os.path.exists(outs[0]) or args.force:
                        for f, out in enumerate(outs):
                            process_classic(image_id, ts, f, out)
                        print(f"  {image_id} {ts}: no HD render yet, classic upscaled")
                if all(os.path.exists(o) for o in outs):
                    files[ts] = outs
                # An HD render arrived: drop the stand-in
                stand_in = [os.path.join(OUT, f"{image_id}-{tag}-classic{['', '-burnt'][f]}.png") for f in range(frames)]
                if src:
                    for p in stand_in:
                        if os.path.exists(p):
                            os.remove(p)
        if files:
            entries[image_id] = files

    write_sequences(entries, process_smudges(args.force, print) + process_walls(args.force, print))
    write_rules(entries)
    process_tiles(args.force, print)
    if args.preview:
        write_preview(entries)


def write_sequences(entries, extra=()):
    lines = ["# HD map environment sprites (RedAlert Project X).",
             "# GENERATED by artsrc/env/make_env.py from assets/env/ - edit that script, not this file.",
             "# Merged on top of the classic sequences in decorations.yaml / misc.yaml.", ""]
    for image_id, files in entries.items():
        for image, seqs in sequence_map(image_id).items():
            lines.append(f"{image}:")
            for seq, frame in seqs.items():
                default_ts = "*" if "*" in files else next(t for t in FALLBACK_ORDER if t in files)
                default = files[default_ts][frame]
                lines.append(f"\t{seq}:")
                lines.append(f"\t\tFilename: ra|bits/hd/env/{os.path.basename(default)}")
                if default_ts != "*":
                    lines.append("\t\tTilesetFilenames:")
                    for ts in TILESETS:
                        if ts in files:
                            lines.append(f"\t\t\t{ts}: ra|bits/hd/env/{os.path.basename(files[ts][frame])}")
                lines += ["\t\tStart: 0", "\t\tLength: 1", f"\t\tScale: {1 / DENSITY:.4f}"]
                lines.append("\t\tOffset: 0,0")
            lines.append("")
    lines += list(extra)
    with open(SEQUENCES, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {os.path.relpath(SEQUENCES, ROOT)} ({len(entries)} images)")


def write_rules(entries):
    lines = ["# HD map environment actors (RedAlert Project X).",
             "# GENERATED by artsrc/env/make_env.py - edit that script, not this file.",
             "# True-colour sprites with the `player` palette get their greens shifted to the owner's colour",
             "# (PlayerColorShift); every HD map object is drawn with the terrain palette instead (true-colour sprites",
             "# ignore the palette otherwise).", ""]
    seen = set()
    for image_id in entries:
        for actor, path in actors_with_image(image_id):
            if actor not in seen:
                seen.add(actor)
                lines += [f"{actor}:", "\tRenderSprites:", "\t\tPalette: terrain", ""]
    with open(RULES, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {os.path.relpath(RULES, ROOT)} ({len(seen)} actors: {', '.join(sorted(seen))})")


def write_preview(entries):
    """Classic (left) vs HD (right) per tileset on a flat ground colour, at 2x world scale."""
    os.makedirs(PREVIEW, exist_ok=True)
    ground = {"TEMPERAT": (86, 104, 60), "SNOW": (214, 220, 228), "DESERT": (196, 160, 112), "INTERIOR": (70, 70, 74), "*": (86, 104, 60)}
    cells = []
    for image_id, files in entries.items():
        for ts, paths in files.items():
            for frame, path in enumerate(paths):
                cp, _ = classic_path(image_id, None if ts == "*" else ts, frame)
                cells.append((f"{image_id} {ts}{' burnt' if frame else ''}", cp, path, ground[ts]))
    cell_w, cell_h, z = 360, 260, 2
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, -(-len(cells) // cols) * cell_h), (30, 30, 30))
    draw = ImageDraw.Draw(sheet)
    for i, (label, cp, hp, col) in enumerate(cells):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        tile = Image.new("RGBA", (cell_w - 4, cell_h - 4), col + (255,))
        for j, (p, off) in enumerate([(cp, (0, 0)), (hp, load_offset(hp))]):
            if not p:
                continue
            im = Image.open(p).convert("RGBA")
            s = z / (CLASSIC_SCALE if j == 0 else DENSITY)
            im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
            cx, cy = (j * 2 + 1) * tile.width // 4, tile.height // 2 + 20
            ox, oy = (off[0] * z / DENSITY, off[1] * z / DENSITY)
            tile.alpha_composite(im, (int(cx - im.width / 2 + ox), int(cy - im.height / 2 + oy)))
            ImageDraw.Draw(tile).ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=(255, 0, 0, 255))
        sheet.paste(tile.convert("RGB"), (x + 2, y + 2))
        draw.text((x + 6, y + 6), label, fill=(255, 255, 255))
    out = os.path.join(PREVIEW, "env-preview.png")
    sheet.save(out)
    print(f"wrote {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
