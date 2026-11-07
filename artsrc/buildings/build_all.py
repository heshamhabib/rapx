#!/usr/bin/env python3
"""
Builds every HD building from artsrc/buildings/src/ and writes mods/rapx/sequences/hd-structures.yaml.

For each building it produces (in mods/rapx/bits/hd/):
  <id>.png          intact building
  <id>-damaged.png  damaged building (from the right half of a two-version render)
  <id>-make.png     construction (and, reversed, selling): hologram scan, welding seam, finishing flash
  <id>-collapse.png destruction: the building sinks below its base outline and chars

Add a building by dropping its render into src/ and adding a row to BUILDINGS.

National styles (IDEA-01): a render at assets/styles/<nation>/<id>.png (same layout: intact left, damaged right)
becomes image <id>.<nation> in mods/rapx/bits/hd/styles/<nation>/ + sequences/hd-structures-styles.yaml
(it inherits every other sequence of <id>), and rules/hd-faction-styles.yaml points the building's FactionImages
at it, so that nation builds its own version. Nations/buildings without a render keep the default art.
Styles are rebuilt only when their render is newer than the output.

  python3 artsrc/buildings/build_all.py                 everything
  python3 artsrc/buildings/build_all.py --styles-only   only the national styles (fast, incremental)
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image, PngImagePlugin
from scipy.ndimage import binary_dilation, binary_erosion, gaussian_filter, sobel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from process_building import process  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd")
SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-structures.yaml")
STYLES_SRC = os.path.join(ROOT, "assets", "styles")
STYLES_OUT = os.path.join(OUT, "styles")
STYLE_SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-structures-styles.yaml")
STYLE_RULES = os.path.join(ROOT, "mods", "rapx", "rules", "hd-faction-styles.yaml")
RULES = os.path.join(ROOT, "mods", "rapx", "rules")

DENSITY = 3.0
# Buildings are drawn larger than their footprint so they read right next to the 1.4x HD vehicles and
# HD infantry (user's call, 2026-10-27): the art grows about a point near the bottom of the footprint,
# so buildings mostly get taller; footprints, pads and gameplay are unchanged.
BUILDING_SCALE = 1.25
TILESETS = ["TEMPERAT", "SNOW", "DESERT", "INTERIOR"]
MAKE_FRAMES = 22
MAKE_TICK = 45
COLLAPSE_FRAMES = 16

# Team colour: PlayerColorShift MinHue/MaxHue in rules/palettes.yaml (hues in linear RGB). Green further than
# TEAM_PAINT_REACH px from bright team paint is foliage and moves into NATURAL_HUES (see protect_natural_greens).
TEAM_HUE_MIN = 0.22
TEAM_HUE_MAX = 0.45
TEAM_PAINT_MIN_VALUE = 0.25
TEAM_PAINT_REACH = 3
NATURAL_HUES = (0.17, 0.215)

# id: (source render, building width in cells, extra size multiplier)
BUILDINGS = {
    "fact": ("fact.png", 3, 1.0),
    "powr": ("powr.png", 2, 1.0),
    "apwr": ("apwr.png", 3, 1.0),
    "proc": ("proc.png", 3, 1.0),
    "silo": ("silo.png", 1, 1.0),
    "weap": ("weap.png", 3, 1.0),
    "fix": ("fix.png", 3, 1.0),
    "dome": ("dome.png", 2, 1.0),
    "hpad": ("hpad.png", 2, 1.0),
    "afld": ("afld.png", 6, 1.0),
    "abas": ("abas.png", 8, 1.0),
    "afbs": ("afbs.png", 10, 1.0),
    "sacm": ("sacm.png", 12, 1.0),
    "tent": ("tent.png", 2, 1.0),
    "barr": ("barr.png", 2, 1.0),
    "kenn": ("kenn.png", 1, 1.0),
    "syrd": ("syrd.png", 3, 1.0),
    "spen": ("spen.png", 3, 1.0),
    "atek": ("atek.png", 2, 1.0),
    "stek": ("stek.png", 3, 1.0),
    "pdox": ("pdox.png", 2, 1.0),
    "iron": ("iron.png", 2, 1.0),
    "gap": ("gap.png", 1, 1.0),
    "pbox": ("pbox.png", 1, 1.0),
    "hbox": ("hbox.png", 1, 1.0),
    # "mslo": 3D model with a launch animation, artsrc/buildings/nuke_silo/make_silo.py (sequences/hd-silo.yaml)
    "gun": ("gun.png", 1, 1.0),
    "agun": ("agun.png", 1, 1.0),
    "ftur": ("ftur.png", 1, 1.0),
    "tsla": ("tsla.png", 1, 1.0),
    "sam": ("sam.png", 2, 1.0),
    "oilr": ("oilr.png", 3, 1.0),
    "ptwr": ("ptwr.png", 1, 1.15),  # Prism Tower (Allied beam defence)
    "mi6": ("mi6.png", 2, 1.0),  # MI6 Headquarters (England only, unlocks the Spy)
}

# Buildings with no classic art: the sequences they get (the classic ones are read from structures.yaml)
AIRFIELD_SEQUENCES = ["idle", "damaged-idle", "active", "damaged-active", "make"]
NEW_BUILDINGS = {"oilr": ["idle", "damaged-idle", "make"], "ptwr": ["idle", "damaged-idle", "make"],
                 "mi6": ["idle", "damaged-idle", "make"],
                 "abas": AIRFIELD_SEQUENCES, "afbs": AIRFIELD_SEQUENCES, "sacm": AIRFIELD_SEQUENCES}

# Airfields (IDEA-06) are drawn exactly on their footprint, not grown by BUILDING_SCALE: their parking pads are
# the slots planes land on (Reservable SlotOffsets, written by make_airfield_slots.py) and must stay inside it.
NOT_GROWN = {"afld", "abas", "afbs", "sacm"}

# Turreted defences: the render shows the whole defence with its gun, so it is drawn as the
# (non-rotating, Facings 1) turret layer and the separate base layer is blanked.
# TODO: rotating guns need 32 facings, e.g. via an image-to-3D model.
TURRETED = {"gun", "agun", "sam"}

# Which existing sequences of a building get which HD image. Sequences a building
# does not have are skipped; overlay sequences are blanked so classic art is not drawn on top.
INTACT = ["idle", "place", "build", "active", "stages"]
DAMAGED = ["damaged-idle", "damaged-build", "damaged-active", "damaged-stages"]
BLANK = ["build-top", "damaged-build-top", "idle-top", "damaged-idle-top"]


def existing_sequences():
    """Sequence names per building from the classic sequences file."""
    result, current = {}, None
    with open(os.path.join(ROOT, "mods", "rapx", "sequences", "structures.yaml")) as f:
        for line in f:
            line = line.split("#", 1)[0].rstrip()
            if line and not line[0].isspace() and line.strip().endswith(":"):
                current = line.strip()[:-1]
                result[current] = []
            elif current and line.startswith("\t") and not line.startswith("\t\t") and line.strip().endswith(":"):
                result[current].append(line.strip()[:-1])
    return result


def building_mask(alpha):
    """Building body vs its cast shadow: the keyed shadow is never more than ~60% opaque.
    Anti-aliased edge pixels next to the body count as body too."""
    solid = alpha > 0.62
    return (binary_dilation(solid, iterations=2) & (alpha > 0)) | solid


def make_animation(intact_path, out_path, frames=MAKE_FRAMES):
    """Construction (played backwards when selling):
    a holographic wireframe scans in from the ground, the building is welded up row by row behind a hot seam
    throwing sparks, the hologram fades and the finished building flashes once."""
    im = np.asarray(Image.open(intact_path).convert("RGBA"), dtype=np.float32) / 255
    h, w, _ = im.shape
    rgb, a = im[..., :3], im[..., 3]
    lum = rgb.mean(-1)

    body = building_mask(a)
    body_soft = gaussian_filter(body.astype(np.float32), 0.7)
    ys = np.nonzero(body.any(1))[0]
    top, bottom = ys.min(), ys.max()

    # Wireframe: silhouette plus strong interior edges, in hologram cyan
    gx, gy = sobel(gaussian_filter(lum, 0.8), 1), sobel(gaussian_filter(lum, 0.8), 0)
    edges = np.clip(np.hypot(gx, gy) * 2.2, 0, 1) * body_soft
    outline = np.clip(body_soft - gaussian_filter(binary_erosion(body, iterations=2).astype(np.float32), 0.7), 0, 1)
    wire = np.clip(np.maximum(edges ** 1.5, outline * 1.2), 0, 1)
    scan = (np.arange(h) % 5 < 2)[:, None].astype(np.float32)
    holo_rgb = np.array([0.45, 0.9, 1.0])

    rows = np.arange(h, dtype=np.float32)[:, None]
    rng = np.random.default_rng(1)
    sheet = np.zeros((h, w * frames, 4), dtype=np.float32)
    for i in range(frames):
        t = i / (frames - 1)
        holo_in = np.clip(t / 0.3, 0, 1)                    # wireframe scan-in
        build = np.clip((t - 0.2) / 0.65, 0, 1)             # welding progress
        holo_out = 1 - np.clip((t - 0.8) / 0.15, 0, 1)      # hologram fades at the end
        flash = np.exp(-((t - 0.92) / 0.05) ** 2)           # finishing flash

        # Hologram: drawn upwards from the ground
        holo_edge = bottom - (bottom - top + 12) * holo_in
        holo_mask = np.clip((rows - holo_edge) / 4, 0, 1)
        holo_a = (wire * 0.75 + body_soft * (0.12 + 0.1 * scan)) * holo_mask * holo_out
        flicker = 0.85 + 0.15 * np.sin(i * 2.3)
        holo_a *= flicker

        # Real building below the welding seam
        edge = bottom + 2 - (bottom - top + 6) * build
        solid = np.clip((rows - edge) / 2 + 0.5, 0, 1)
        if build >= 1:
            solid = np.ones_like(solid)
        seam = np.exp(-((rows - edge) / 2.2) ** 2) * (0 < build < 1) * body_soft

        frame = np.zeros((h, w, 4), np.float32)
        shadow_a = np.where(body, 0, a) * build
        bld_a = np.where(body, a, 0) * solid
        col = rgb * (1 + 0.8 * flash)
        out_a = np.clip(bld_a + shadow_a * (1 - bld_a), 0, 1)
        frame[..., :3] = col * (bld_a / np.maximum(out_a, 1e-3))[..., None]
        frame[..., 3] = out_a

        # Hologram over (where the building isn't solid yet)
        ha = holo_a * (1 - bld_a)
        frame[..., :3] = frame[..., :3] * (1 - ha[..., None]) + holo_rgb * ha[..., None]
        frame[..., 3] = np.clip(frame[..., 3] + ha * (1 - frame[..., 3]), 0, 1)

        # Hot welding seam and sparks just above it
        hot = np.array([1.0, 0.8, 0.45])
        sa = np.clip(seam * 1.2, 0, 1)
        frame[..., :3] = frame[..., :3] * (1 - sa[..., None]) + hot * sa[..., None]
        frame[..., 3] = np.maximum(frame[..., 3], sa)
        if 0 < build < 1:
            cand = np.argwhere(body & (np.abs(rows - edge + 4) < 6))
            if len(cand):
                for y, x in cand[rng.choice(len(cand), min(len(cand), 6 + w // 25), replace=False)]:
                    y2, x2 = max(0, y - rng.integers(1, 6)), x + rng.integers(-2, 3)
                    for yy, xx in ((y, x), (y2, x2)):
                        if 0 <= xx < w:
                            frame[yy, xx, :3] = [1, 0.95, 0.75]
                            frame[yy, xx, 3] = 1

        sheet[:, i * w:(i + 1) * w] = frame

    # Straight-alpha RGB for transparent pixels doesn't matter; keep it clean
    sheet[..., :3] = np.where(sheet[..., 3:] > 0, sheet[..., :3], 0)
    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(frames))
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(out_path, pnginfo=info, optimize=True)


def collapse_animation(src_path, out_path, frames=COLLAPSE_FRAMES):
    """Destruction: the (damaged) building sinks into the ground below its own base outline, crumbling at the
    ground line and charring as it goes; its shadow fades. Dust, debris and fire are added by WithPxCollapse."""
    im = np.asarray(Image.open(src_path).convert("RGBA"), dtype=np.float32) / 255
    h, w, _ = im.shape
    rgb, a = im[..., :3], im[..., 3]
    body = building_mask(a)
    body_a = np.where(body, a, 0)
    shadow_a = np.where(body, 0, a)
    ys = np.nonzero(body.any(1))[0]
    top, bottom = ys.min(), ys.max()

    # Ground line: the lowest body pixel of each column (the building's base outline), smoothed
    cols = np.where(body.any(0), h - 1 - np.argmax(body[::-1], axis=0), -1).astype(np.float32)
    ground = np.maximum.reduce([np.roll(cols, k) for k in range(-3, 4)])
    rows = np.arange(h, dtype=np.float32)[:, None]
    rng = np.random.default_rng(3)
    jag = gaussian_filter(rng.random(w).astype(np.float32), 1.5) * 10 - 5
    sheet = np.zeros((h, w * frames, 4), dtype=np.float32)
    for i in range(frames):
        t = i / (frames - 1)
        d = int(round((bottom - top) * 0.9 * t ** 1.5))
        moved = np.zeros_like(im)
        moved[d:] = np.dstack([rgb, body_a])[:h - d] if d else np.dstack([rgb, body_a])

        # Hide what has sunk below the base outline; the edge crumbles
        line = ground[None, :] + jag[None, :] * min(1, t * 4)
        keep = np.clip((line - rows) / 2, 0, 1)
        moved[..., 3] *= keep

        # Char and dust near the ground line
        near = np.clip(1 - (line - rows) / 25, 0, 1) * min(1, t * 3)
        moved[..., :3] *= (1 - 0.5 * t) * (1 - 0.35 * near[..., None])
        moved[..., :3] += np.array([0.32, 0.27, 0.2]) * (0.4 * near[..., None])

        sa = shadow_a * (1 - t) ** 2
        out_a = np.clip(moved[..., 3] + sa * (1 - moved[..., 3]), 0, 1)
        frame = np.zeros((h, w, 4), np.float32)
        frame[..., :3] = moved[..., :3] * (moved[..., 3] / np.maximum(out_a, 1e-3))[..., None]
        frame[..., 3] = out_a
        sheet[:, i * w:(i + 1) * w] = frame

    info = PngImagePlugin.PngInfo()
    info.add_text("FrameSize", f"{w},{h}")
    info.add_text("FrameAmount", str(frames))
    Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8)).save(out_path, pnginfo=info, optimize=True)


def _seq_block(name, filename, offset, length=None, tick=None, scale=BUILDING_SCALE):
    # Classic art uses per-tileset files (e.g. DESERT: tentmake.des); point every tileset at the HD file
    lines = [f"\t{name}:", f"\t\tFilename: ra|bits/hd/{filename}", "\t\tTilesetFilenames:"]
    lines += [f"\t\t\t{tileset}: ra|bits/hd/{filename}" for tileset in TILESETS]
    lines += ["\t\tStart: 0"]
    if length:
        lines.append(f"\t\tLength: {length}")
    if tick:
        lines.append(f"\t\tTick: {tick}")
    lines += [f"\t\tScale: {scale / DENSITY:.4f}", f"\t\tOffset: {offset[0]},{offset[1]}"]
    return lines


def grown(offset, cells, scale=BUILDING_SCALE):
    """Offset after scaling the art by BUILDING_SCALE about an anchor near the bottom of the footprint.
    The engine scales a sprite about its own centre, so the centre moves to anchor + scale * (offset - anchor)."""
    ay = 8 * cells  # world px below the footprint centre (between the centre and the bottom edge)
    return (round(scale * offset[0]), round(ay + scale * (offset[1] - ay)))


def sequences_for(bid, names, offset, prefix, damaged_file, has_damaged=True):
    """Sequence blocks for one building image; files are relative to bits/hd (prefix = subfolder)."""
    scale = 1.0 if bid in NOT_GROWN else BUILDING_SCALE
    offset = grown(offset, BUILDINGS[bid][1], scale)
    f = lambda name: prefix + name
    yaml = []
    seq_block = lambda *a, **k: _seq_block(*a, scale=scale, **k)
    for name in names:
        if bid in TURRETED and name in ("turret", "recoil"):
            yaml += seq_block(name, f(f"{bid}.png"), offset, 1) + ["\t\tFacings: 1", "\t\tUseClassicFacings: false"]
        elif bid in TURRETED and name in ("damaged-turret", "damaged-recoil"):
            yaml += seq_block(name, f(damaged_file), offset, 1) + ["\t\tFacings: 1", "\t\tUseClassicFacings: false"]
        elif bid in TURRETED and name == "idle":
            yaml += seq_block(name, "blank.png", (0, 0), 1)
        elif name in INTACT:
            yaml += seq_block(name, f(f"{bid}.png"), offset, 1)
        elif name in DAMAGED:
            yaml += seq_block(name, f(damaged_file), offset, 1)
        elif name in BLANK:
            yaml += seq_block(name, "blank.png", (0, 0), 1)
        elif name == "make":
            yaml += seq_block(name, f(f"{bid}-make.png"), offset, MAKE_FRAMES, MAKE_TICK)
    # Played by WithPxCollapse when the building is destroyed
    yaml += seq_block("collapse", f(f"{bid}-collapse.png"), offset, COLLAPSE_FRAMES)
    return yaml


def protect_natural_greens(path):
    """PlayerColorShift (rules/palettes.yaml) recolours linear hues TEAM_HUE_MIN..TEAM_HUE_MAX, which also catches
    leaves and grass (palms on the Cuban buildings turned the player's colour). Bright saturated green is team paint;
    any in-range green further than TEAM_PAINT_REACH px from it is foliage and gets a yellow-green hue just below
    the range, so it keeps its look in every team colour. Returns the number of pixels changed."""
    im = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64) / 255
    srgb, alpha = im[..., :3], im[..., 3:]
    lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    hi, lo = lin.max(-1), lin.min(-1)
    chroma = hi - lo
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    sat = chroma / np.maximum(hi, 1e-9)
    hue = np.where(hi == g, (b - r) / np.maximum(chroma, 1e-9) + 2, 0) / 6
    shifted = (hi == g) & (chroma > 1e-4) & (hue > TEAM_HUE_MIN) & (hue <= TEAM_HUE_MAX) & (alpha[..., 0] > 0)
    paint = shifted & (hue > 0.29) & (hue < 0.40) & (sat > 0.6) & (hi > TEAM_PAINT_MIN_VALUE)
    natural = shifted & ~binary_dilation(paint, iterations=TEAM_PAINT_REACH)
    if not natural.any():
        return 0
    # Same chroma and value, hue squeezed into NATURAL_HUES: green stays the max channel; below 1/3 blue is the
    # min, so hue = ((b - r) / chroma + 2) / 6 gives r = b + chroma * (2 - 6 * hue)
    lo_h, hi_h = NATURAL_HUES
    new_hue = lo_h + (hue - TEAM_HUE_MIN) / (TEAM_HUE_MAX - TEAM_HUE_MIN) * (hi_h - lo_h)
    new = lin.copy()
    new[..., 0] = np.where(natural, lo + chroma * (2 - 6 * new_hue), r)
    new[..., 1] = np.where(natural, hi, g)
    new[..., 2] = np.where(natural, lo, b)
    out = np.where(new <= 0.0031308, new * 12.92, 1.055 * np.maximum(new, 0) ** (1 / 2.4) - 0.055)
    info = PngImagePlugin.PngInfo()
    for k, v in Image.open(path).text.items():
        info.add_text(k, v)
    Image.fromarray((np.clip(np.concatenate([out, alpha], -1), 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        path, pnginfo=info, optimize=True)
    return int(natural.sum())


def build(bid, src_path, out_dir, cells, extra):
    """Process one render into <out_dir>/<bid>{,-damaged,-make,-collapse}.png; returns (offset, damaged file name)."""
    paths, size, offset = process(src_path, os.path.join(out_dir, f"{bid}.png"), cells, DENSITY, extra_scale=extra,
                                  log=lambda m: print("  " + m))
    for p in paths:
        moved = protect_natural_greens(p)
        if moved:
            print(f"  {os.path.basename(p)}: {moved} foliage pixels moved out of the team-colour hues")
    damaged_file = f"{bid}-damaged.png" if len(paths) > 1 else f"{bid}.png"
    make_animation(paths[0], os.path.join(out_dir, f"{bid}-make.png"))
    collapse_animation(paths[-1], os.path.join(out_dir, f"{bid}-collapse.png"))
    print(f"{bid}: done ({'with' if len(paths) > 1 else 'no'} damaged version)")
    return offset, damaged_file


def sprite_offset(path):
    """Sequence Offset of an already built sprite, stored in its PNG text chunk."""
    text = Image.open(path).text.get("PxOffset")
    return tuple(int(v) for v in text.split(",")) if text else None


def save_offset(path, offset):
    im = Image.open(path)
    im.load()
    info = PngImagePlugin.PngInfo()
    info.add_text("PxOffset", f"{offset[0]},{offset[1]}")
    im.save(path, pnginfo=info, optimize=True)


def factions():
    """Faction internal names from world.yaml (lower case), so a typo in a styles folder name is caught."""
    with open(os.path.join(RULES, "world.yaml")) as f:
        return {m.lower() for m in re.findall(r"^\t\tInternalName:\s*(\S+)", f.read(), re.M)}


def image_users():
    """Actor names whose RenderSprites image is <id> per id."""
    users = {}
    for name in ("structures.yaml",):
        with open(os.path.join(RULES, name)) as f:
            text = f.read()
        for block in re.split(r"\n(?=[A-Za-z0-9^])", text):
            actor = block.split(":", 1)[0].strip()
            if not re.fullmatch(r"[A-Z0-9]+", actor):
                continue
            m = re.search(r"^\t\tImage:\s*(\S+)", block, re.M)
            users.setdefault((m.group(1) if m else actor).lower(), []).append(actor)
    return users


def build_styles(classic):
    known = factions()
    styles = {}  # nation -> {bid: (offset, damaged file)}
    for nation in sorted(os.listdir(STYLES_SRC)) if os.path.isdir(STYLES_SRC) else []:
        folder = os.path.join(STYLES_SRC, nation)
        if not os.path.isdir(folder):
            continue
        if nation not in known:
            print(f"skip styles/{nation}: no faction with that InternalName")
            continue
        out_dir = os.path.join(STYLES_OUT, nation)
        os.makedirs(out_dir, exist_ok=True)
        for src in sorted(os.listdir(folder)):
            bid = os.path.splitext(src)[0].lower()
            if not src.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            if bid not in BUILDINGS:
                print(f"skip styles/{nation}/{src}: unknown building id")
                continue
            src_path, out = os.path.join(folder, src), os.path.join(out_dir, f"{bid}.png")
            if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src_path) and sprite_offset(out):
                offset = sprite_offset(out)
                damaged = f"{bid}-damaged.png" if os.path.exists(os.path.join(out_dir, f"{bid}-damaged.png")) else f"{bid}.png"
            else:
                print(f"[{nation}]", end=" ")
                _, cells, extra = BUILDINGS[bid]
                offset, damaged = build(bid, src_path, out_dir, cells, extra)
                save_offset(out, offset)
            styles.setdefault(nation, {})[bid] = (offset, damaged)

    seq = [
        "# National building styles (RedAlert Project X, IDEA-01).",
        "# GENERATED by artsrc/buildings/build_all.py from assets/styles/<nation>/<id>.png - edit that script, not this file.",
        "# Each <id>.<nation> image inherits the default <id> image and replaces its HD art.",
        "",
    ]
    for nation, blds in styles.items():
        for bid, (offset, damaged) in sorted(blds.items()):
            names = classic.get(bid, []) + NEW_BUILDINGS.get(bid, [])
            seq += [f"{bid}.{nation}:", f"\tInherits: {bid}"]
            seq += sequences_for(bid, names, offset, f"styles/{nation}/", damaged)
            seq.append("")
    with open(STYLE_SEQUENCES, "w") as f:
        f.write("\n".join(seq))
    print("wrote", os.path.relpath(STYLE_SEQUENCES, ROOT))

    users = image_users()
    rules = [
        "# National building styles (RedAlert Project X, IDEA-01): which nation uses which building image.",
        "# GENERATED by artsrc/buildings/build_all.py - edit that script, not this file.",
        "# A nation missing from a list builds the default art.",
        "",
    ]
    for bid in BUILDINGS:
        nations = [n for n in styles if bid in styles[n]]
        if not nations:
            continue
        for actor in users.get(bid, [bid.upper()]):
            rules += [f"{actor}:", "\tRenderSprites:", "\t\tFactionImages:"]
            rules += [f"\t\t\t{n}: {bid}.{n}" for n in nations]
            rules.append("")
    with open(STYLE_RULES, "w") as f:
        f.write("\n".join(rules))
    print("wrote", os.path.relpath(STYLE_RULES, ROOT))
    for nation, blds in styles.items():
        print(f"  {nation}: {' '.join(sorted(blds))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles-only", action="store_true", help="only (re)build the national styles")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    blank = os.path.join(OUT, "blank.png")
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(blank)

    classic = existing_sequences()
    if not args.styles_only:
        yaml = [
            "# High resolution building art (RedAlert Project X).",
            "# GENERATED by artsrc/buildings/build_all.py - edit that script, not this file.",
            "# Pure green (#00FF00) areas are recoloured to the owner's colour by PlayerColorShift.",
            "",
        ]
        for bid, (src, cells, extra) in BUILDINGS.items():
            src_path = os.path.join(SRC, src)
            if not os.path.exists(src_path):
                print(f"skip {bid}: {src} not found")
                continue
            out = os.path.join(OUT, f"{bid}.png")
            if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src_path) and sprite_offset(out):
                # Unchanged source: reuse the built art
                offset = sprite_offset(out)
                damaged_file = f"{bid}-damaged.png" if os.path.exists(os.path.join(OUT, f"{bid}-damaged.png")) else f"{bid}.png"
            else:
                offset, damaged_file = build(bid, src_path, OUT, cells, extra)
                save_offset(out, offset)
            names = classic.get(bid, []) + NEW_BUILDINGS.get(bid, [])
            yaml.append(f"{bid}:")
            yaml += sequences_for(bid, names, offset, "", damaged_file)
            yaml.append("")

        with open(SEQUENCES, "w") as f:
            f.write("\n".join(yaml))
        print("wrote", os.path.relpath(SEQUENCES, ROOT))

    build_styles(classic)


if __name__ == "__main__":
    main()
