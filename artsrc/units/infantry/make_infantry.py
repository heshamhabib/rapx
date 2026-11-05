#!/usr/bin/env python3
"""
Turns the AI infantry animation sheets (assets/units/<id>/<anim>-<dir>.png, magenta background, see
artsrc/prompts/infantry-anim-prompts.md) into HD game sprites.

Per sheet: cut the grid into frames, key out the magenta, scale the soldier to a common size, align
every frame on a shared ground line (so the animation does not jitter), add a soft ground shadow.
Directions: S, SW, W, NW, N are drawn; SE, E, NE are mirrored. OpenRA's 8 facings run counter-clockwise
from north: N, NW, W, SW, S, SE, E, NE.

Writes mods/rapx/bits/hd/infantry/<id>/<sequence>.png (PngSheet) and mods/rapx/sequences/hd-infantry.yaml
(GENERATED - edit this script, not that file).

  python3 artsrc/units/infantry/make_infantry.py            # every unit in UNITS
  python3 artsrc/units/infantry/make_infantry.py e1 [e2 ...] # only these (the yaml still lists all of UNITS)
"""

import os
import re
import sys

import numpy as np
from PIL import Image, ImageFilter
from PIL.PngImagePlugin import PngInfo
from scipy.ndimage import binary_opening, label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MOD = os.path.join(ROOT, "mods", "rapx")
PROMPTS = os.path.join(ROOT, "artsrc", "prompts", "infantry-anim-prompts.md")

BASE_FRAME = 192     # sprite pixels per frame (3x density: 64 world px) for soldier-sized units
BASE_HEIGHT = 72     # standing soldier height in sprite pixels (24 world px, classic size + 25 %)
BASE_FEET = 22       # ground line below the frame centre, sprite pixels
FRAME, STAND_HEIGHT, FEET = BASE_FRAME, BASE_HEIGHT, BASE_FEET  # set per unit by build()
PRONE_MAX_H = 43     # lying soldiers are squashed to at most this tall: the AI draws the N-facing
                     # prone poses so foreshortened that they read as standing at sprite size
FACING_DIRS = ["n", "nw", "w", "sw", "s", "se", "e", "ne"]
MIRROR = {"se": "sw", "e": "w", "ne": "nw"}

# sequence -> (sheet, frames or None for all, kind, reversed); kind decides how the sheet is scaled
#   upright: soldier height ~ STAND_HEIGHT; prone: sized like the lying pose of the poses sheet;
#   first: scaled by the first frame (upright), the rest follow (falls, dives)
FACED = {
    "stand": ("poses", [0], "upright", False),
    "stand2": ("poses", [1], "upright", False),
    "prone-stand": ("poses", [2], "pose-prone", False),
    "prone-stand2": ("poses", [2], "pose-prone", False),
    "run": ("run", None, "upright", False),
    "shoot": ("shoot", None, "upright", False),
    "liedown": ("dive", None, "first", False),
    "standup": ("dive", None, "first", True),
    "prone-run": ("crawl", None, "prone", False),
    "prone-shoot": ("prone-shoot", None, "prone", False),
    "heal": ("heal", None, "upright", False),      # Medic
    "repair": ("repair", None, "upright", False),  # Mechanic
}
SINGLE = {  # facing-less sequences; sheet name(s) in order of preference
    "idle1": (["idle1"], None, "upright"),
    "idle2": (["idle2"], None, "upright"),
    "die1": (["die1"], None, "first"),
    "die2": (["die2"], None, "first"),
    # Only die1/die2 are drawn for most soldiers (2026-10-27 trim); older sets also have die3/die4
    "die3": (["die3", "die1"], None, "first"),
    "die4": (["die4", "die2"], None, "first"),
    "die5": (["die4", "die2"], None, "first"),
    "parachute": (["parachute"], [0], "upright"),  # Rifle Infantry only
}

# Every unit with HD animation sheets; the generated yaml always lists all of them
UNITS = ["e1", "e2", "e3", "e4", "e6", "e7", "medi", "mech", "shok", "spy", "dog",  # thf removed from the game
         "enfw", "cybt", "bdrd", "rgun", "strd", "irgd", "taut", "sdrn"]
# Robots (IDEA-29) never take cover: no prone / dive sequences
ROBOTS = {"enfw", "cybt", "bdrd", "rgun", "strd", "irgd", "taut", "sdrn"}
# Height relative to a soldier (frame size and ground line grow with it)
SIZE = {"dog": 0.6, "enfw": 2.0, "strd": 1.8, "bdrd": 1.2, "rgun": 1.15, "irgd": 1.2, "taut": 1.2,
        "cybt": 1.1, "sdrn": 0.5}
# Size in game (Balanced RTS: a soldier about half a tank's height): sprite Scale = 1/3 (3x density) x this
GAME_SCALE = {"enfw": 0.7, "strd": 0.7}
DEFAULT_GAME_SCALE = 0.6
# Sheets a unit draws under another name (base name before "-<dir>")
SHEET_ALIAS = {"dog": {"poses": "stand", "shoot": "attack"},
               "sdrn": {"die2": "shoot-sw"}}  # killed by explosions: the detonation sheet
# Units whose rules use other sequence names (WithInfantryBody DefaultAttackSequence / AttackSequences /
# IdleSequences); a list writes the same sprite under several names
RENAME = {"e2": {"shoot": "throw", "prone-shoot": "prone-throw"},
          "e7": {"shoot": ["shoot-left", "shoot-right"], "prone-shoot": ["prone-shoot-left", "prone-shoot-right"]},
          "medi": {"idle1": "idle"}, "mech": {"idle1": "idle"}, "thf": {"idle1": "idle"},
          "dog": {"shoot": "eat", "run": ["run", "walk"]}}
# Keys of the classic sequence that don't fit the HD sheet and must be removed (Tanya's hand-picked frames)
CLEAR = {"e7": {"shoot-left": ["Combine"], "shoot-right": ["Combine"],
                "prone-shoot-left": ["Frames"], "prone-shoot-right": ["Frames"]}}
for _uid in ROBOTS:  # robots have only two drawn deaths; crushed / electrocuted reuse the collapse
    RENAME[_uid] = {"die1": ["die1", "die-crushed", "die6"]}


def grids():
    """Sheet name (e.g. 'e1/run-sw') -> (cols, rows), from the prompt file."""
    text = open(PROMPTS).read()
    found = {}
    for name, cols, rows in re.findall(r"Save as: `([^`]+)\.png`\s*\nReference:[^\n]*\nGrid: (\d+)x(\d+)", text):
        found[name] = (int(cols), int(rows))
    return found


def key_magenta(rgb):
    """Alpha from 'how magenta' a pixel is; removes magenta spill from the edges."""
    a = rgb.astype(np.float32) / 255
    mag = np.minimum(a[..., 0], a[..., 2]) - a[..., 1]
    alpha = 1 - np.clip((mag - 0.25) / 0.35, 0, 1)
    spill = np.clip(np.minimum(a[..., 0], a[..., 2]) - a[..., 1], 0, None) * (alpha < 1)
    a[..., 0] -= spill * 0.8
    a[..., 2] -= spill * 0.8
    return np.dstack([np.clip(a, 0, 1), alpha])


def cut(path, cols, rows):
    """Frames of a sheet: (rgba float array cropped to the cell, bbox in cell coords) per cell."""
    rgb = np.asarray(Image.open(path).convert("RGB"))
    H, W = rgb.shape[:2]
    rgba = key_magenta(rgb)
    out = []
    for r in range(rows):
        for c in range(cols):
            cell = rgba[r * H // rows:(r + 1) * H // rows, c * W // cols:(c + 1) * W // cols].copy()
            solid = binary_opening(cell[..., 3] > 0.5, iterations=1)
            labels, n = label(solid)
            if n:
                sizes = np.bincount(labels.ravel())
                sizes[0] = 0
                main = int(np.argmax(sizes))
                my, mx = np.nonzero(labels == main)
                pad_x, pad_y = (mx.max() - mx.min()) * 0.2, (my.max() - my.min()) * 0.2
                keep = np.zeros(n + 1, bool)
                for k in range(1, n + 1):
                    if sizes[k] < sizes[main] * 0.002:
                        continue  # specks
                    ky, kx = np.nonzero(labels == k)
                    cy, cx = ky.mean(), kx.mean()
                    # The soldier plus what is next to him (muzzle flash, casings); parts of the
                    # neighbouring frame that cross the cell border are dropped
                    keep[k] = (mx.min() - pad_x <= cx <= mx.max() + pad_x) and (my.min() - pad_y <= cy <= my.max() + pad_y)
                cell[..., 3] *= keep[labels] | (cell[..., 3] < 0.5)
            ys, xs = np.nonzero(cell[..., 3] > 0.1)
            bbox = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if len(xs) else (0, 0, 1, 1)
            out.append((cell, bbox))
    return out


def place(frames, scale, prone):
    """Puts the frames into FRAME x FRAME sprites with one shared anchor, plus a soft shadow."""
    xs = [(b[0] + b[2]) / 2 for _, b in frames]
    ax = float(np.median(xs))
    if prone:
        ay = float(np.median([(b[1] + b[3]) / 2 for _, b in frames]))
        tx, ty = FRAME / 2, FRAME / 2 + FEET * 0.5
    else:
        ay = float(np.median([b[3] for _, b in frames]))
        tx, ty = FRAME / 2, FRAME / 2 + FEET
    sy = 1.0
    if prone:
        sy = min(1.0, PRONE_MAX_H / (height_of(frames) * scale))
    sprites = []
    for cell, _ in frames:
        img = Image.fromarray((cell * 255).astype(np.uint8))
        w, h = img.size
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale * sy))), Image.LANCZOS)
        ox, oy = round(tx - ax * scale), round(ty - ay * scale * sy)
        fig = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
        fig.paste(img, (ox, oy), img)
        # Shadow: the figure's own outline squashed onto the ground, shifted down-right, blurred
        mask = fig.split()[3]
        ground = round(ty)
        sh = mask.resize((FRAME, max(1, FRAME // 4)), Image.BILINEAR)
        shadow_mask = Image.new("L", (FRAME, FRAME), 0)
        shadow_mask.paste(sh, (6, ground - sh.height + 4))
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(3)).point(lambda v: int(v * 0.35))
        out = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
        out.paste((0, 0, 0, 255), (0, 0), shadow_mask)
        out.alpha_composite(fig)
        sprites.append(out)
    return sprites


def save_sheet(frames, path):
    cols = min(8, len(frames))
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (FRAME * cols, FRAME * rows), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, ((i % cols) * FRAME, (i // cols) * FRAME))
    meta = PngInfo()
    meta.add_text("FrameSize", f"{FRAME},{FRAME}")
    meta.add_text("FrameAmount", str(len(frames)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path, pnginfo=meta, optimize=True)


def height_of(frames):
    return float(np.median([b[3] - b[1] for _, b in frames]))


def length_of(frames):
    return float(np.median([max(b[2] - b[0], b[3] - b[1]) for _, b in frames]))


def build(uid, grid):
    global FRAME, STAND_HEIGHT, FEET
    size = SIZE.get(uid, 1.0)
    STAND_HEIGHT = round(BASE_HEIGHT * size)
    FRAME = BASE_FRAME if size <= 1.25 else 64 * round(BASE_FRAME * size * 1.1 / 64)
    FEET = round(BASE_FEET * max(1.0, size))
    src = os.path.join(ROOT, "assets", "units", uid)
    alias = SHEET_ALIAS.get(uid, {})

    def sheet(name):
        base, _, d = name.rpartition("-") if name.rsplit("-", 1)[-1] in FACING_DIRS else (name, "", "")
        name = alias.get(base, base) + ("-" + d if d else "")
        path = os.path.join(src, f"{name}.png")
        if not os.path.exists(path):
            return None
        key = f"{uid}/{name}"
        # Sheets dropped from the prompt file in the 2026-10-27 trim keep their old grids
        size = grid.get(key) or {"die3": (4, 2), "die4": (4, 2), "corpse": (2, 2)}.get(name) or (2, 2)
        return cut(path, *size)

    # Prone size per direction, relative to the standing height (from the poses sheet)
    prone_ratio = {}
    for d in FACING_DIRS[:5]:
        poses = sheet(f"poses-{d}")
        if poses and len(poses) > 2:
            prone_ratio[d] = length_of([poses[2]]) / (poses[0][1][3] - poses[0][1][1])

    def scaled(frames, kind, d):
        if kind == "upright":
            return STAND_HEIGHT / height_of(frames)
        if kind == "first":
            return STAND_HEIGHT / (frames[0][1][3] - frames[0][1][1])
        ratio = prone_ratio.get(d, 1.0)
        return STAND_HEIGHT * ratio / length_of(frames)

    out_dir = os.path.join(MOD, "bits", "hd", "infantry", uid)
    seqs = {}
    for seq, (name, pick, kind, backwards) in FACED.items():
        if uid in ROBOTS and (seq.startswith("prone") or seq in ("liedown", "standup")):
            continue
        per_facing = []
        for d in FACING_DIRS:
            frames = sheet(f"{name}-{MIRROR.get(d, d)}")
            if frames is None or (pick and max(pick) >= len(frames)):
                break
            if kind == "pose-prone":
                scale = STAND_HEIGHT / (frames[0][1][3] - frames[0][1][1])
                chosen, prone = [frames[i] for i in pick], True
            else:
                chosen = [frames[i] for i in pick] if pick else frames
                scale = scaled(frames, kind, MIRROR.get(d, d))
                prone = kind == "prone"
            sprites = place(chosen, scale, prone)
            if d in MIRROR:
                sprites = [s.transpose(Image.FLIP_LEFT_RIGHT) for s in sprites]
            if backwards:
                sprites = sprites[::-1]
            per_facing.append(sprites)
        if len(per_facing) != 8:
            if per_facing:
                print(f"{uid}: skip {seq} (missing {name} sheets)")
            continue
        length = len(per_facing[0])
        save_sheet([f for facing in per_facing for f in facing], os.path.join(out_dir, f"{seq}.png"))
        seqs[seq] = (length, 8)

    for seq, (names, pick, kind) in SINGLE.items():
        frames = next((f for f in (sheet(n) for n in names) if f is not None), None)
        if frames is None:
            continue
        chosen = [frames[i] for i in pick] if pick else frames
        sprites = place(chosen, scaled(frames, kind, "s"), False)
        save_sheet(sprites, os.path.join(out_dir, f"{seq}.png"))
        seqs[seq] = (len(sprites), 1)
    print(f"{uid}: {len(seqs)} sequences")
    return seqs


def main():
    grid = grids()
    lines = ["# HD infantry (RedAlert Project X), overriding the classic sequences.",
             "# GENERATED by artsrc/units/infantry/make_infantry.py - edit that script, not this file.",
             "# Frames come from the AI animation sheets in assets/units/<id>/; facings run N, NW, W, SW, S, SE, E, NE.",
             ""]
    only = set(sys.argv[1:]) or set(UNITS)
    for uid in UNITS:
        if uid in only:
            build(uid, grid)
        lines.append(uid + ":")
        out_dir = os.path.join(MOD, "bits", "hd", "infantry", uid)
        for fn in sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []:
            seq = fn[:-4]
            info = Image.open(os.path.join(out_dir, fn)).info
            frames = int(info["FrameAmount"])
            facings = 1 if seq in SINGLE else 8
            length = frames // facings
            names = RENAME.get(uid, {}).get(seq, seq)
            for name in [names] if isinstance(names, str) else names:
                lines += [f"\t{name}:", f"\t\tFilename: ra|bits/hd/infantry/{uid}/{seq}.png", "\t\tStart: 0",
                          f"\t\tLength: {length}", f"\t\tStride: {length}", f"\t\tFacings: {facings}",
                          f"\t\tScale: {GAME_SCALE.get(uid, DEFAULT_GAME_SCALE) / 3:.4f}"] + [f"\t\t-{k}:" for k in CLEAR.get(uid, {}).get(name, [])]
        lines.append("")
    with open(os.path.join(MOD, "sequences", "hd-infantry.yaml"), "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
