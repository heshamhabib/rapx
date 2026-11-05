#!/usr/bin/env python3
"""
Writes mods/rapx/rules/carrier-decks.yaml: the flight decks of the IDEA-08 carriers (PxCarrierDeck), measured from
their HD art.

Frame 0 of each hull sprite (mods/rapx/bits/hd/units/<id>.png, facing north: bow up, island on the starboard =
right side) gives the deck (opaque pixels; the soft shadow is left out) and the island (team-colour pixels). The
deck's working areas are placed on a template in deck coordinates: t runs from the stern (-1) to the bow (+1), s
from the port edge (-1) to the starboard edge (+1).

  - catapult track: CatapultStart -> Launch (jets taxi to its start, then are shot along it)
  - landing strip:  Touchdown -> Rollout (jets catch the wires at Touchdown and roll out to Rollout)

Every slot gets a visible parking spot (no hidden slots). Spots are packed like a real deck: jets stand at 45 degrees
along the edges, noses on deck and tails hanging out over the water, wings overlapping a little, never on the island,
the landing strip or the catapult track. The parked size (ParkedScale) is the largest that fits all slots.

The engine draws sprite pixel p at actor + Scale * (p - size / 2), so a pixel is Scale * 1024 / 24 world units from
the ship's centre.

  python3 artsrc/units/carrier/make_carrier_decks.py            write the rules
  python3 artsrc/units/carrier/make_carrier_decks.py --preview  also draw before/after decks into artsrc/units/carrier/preview/
"""
import argparse
import math
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
UNITS = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "units")
OUT = os.path.join(ROOT, "mods", "rapx", "rules", "carrier-decks.yaml")
PREVIEW = os.path.join(HERE, "preview")
SCALE = 0.2333  # hull sprite scale (sequences/carriers.yaml)
COLUMNS = 8  # 32 facings in an 8 x 4 sheet
WU_PER_PX = SCALE * 1024 / 24

# Reference jet for packing and previews: the F-14 (widest carrier jet), drawn at JET_SCALE (sequences/jets.yaml).
JET_SPRITE = os.path.join(UNITS, "af-14-bobcat.png")
JET_SCALE = 0.3333
LANDED_SCALE = 0.6  # PxAltitudeScale.LandedScale of the jets
OVERLAP = 0.3  # how much neighbouring parked jets may overlap (wing over wing)
MAX_PARKED_SCALE = 0.85
OLD_PARKED_SCALE = 0.45  # before this layout (preview only)

# Deck templates (t, s).
ANGLED = {  # angled deck: Nimitz, Ford, Kuznetsov, ... (measured on the Nimitz)
    "CatapultStart": (0.30, 0.20),
    "Launch": (0.86, 0.20),
    "Touchdown": (-0.55, -0.09),
    "Rollout": (-0.05, -0.41),
    "Strip": ((-0.93, 0.15), (0.40, -0.69), 0.13),  # landing strip centre line and half width (of the deck width)
    "Track": 0.09,  # catapult track half width
}
STRAIGHT = {  # straight deck for short take-off / vertical landing ships: one run along the port side of the centre
    "CatapultStart": (-0.15, -0.12),
    "Launch": (0.88, -0.12),
    "Touchdown": (-0.60, -0.12),
    "Rollout": (-0.45, -0.12),
    "Strip": ((-0.95, -0.12), (0.97, -0.12), 0.15),
    "Track": 0.0,
}

# The Kiev is a cruiser forward: its deck starts amidships, on the port side.
OVERRIDES = {"CVSU": {"CatapultStart": (-0.35, -0.40), "Launch": (0.32, -0.45),
                      "Strip": ((-0.95, -0.40), (0.35, -0.45), 0.17)}}

# Actor -> (deck types, slots, template). Decks follow the real ships: catapults (CATOBAR), ski-jump (STOBAR) or
# short take-off / vertical landing only. Mistral (CVEG), Kaga (CVJP) and Bagheri (CVIR) have no deck yet: their
# nations have no jet that fits (helicopters and drones come later).
CARRIERS = {
    "CV1": ("Catapult, STOVL", 6, ANGLED),
    "CV2": ("Catapult, STOVL", 8, ANGLED),
    "CV3": ("Catapult, STOVL", 12, ANGLED),
    "CV4": ("Catapult, STOVL", 14, ANGLED),
    "CVGB": ("STOVL", 10, STRAIGHT),
    "CVFR": ("Catapult, STOVL", 8, ANGLED),
    "CVIT": ("STOVL", 6, STRAIGHT),
    "CVSU": ("STOVL", 6, STRAIGHT),
    "CVRU": ("SkiJump, STOVL", 10, ANGLED),
    "CVIN": ("SkiJump, STOVL", 8, ANGLED),
    "CVCN": ("Catapult, SkiJump, STOVL", 12, ANGLED),
    "CVTR": ("STOVL", 6, STRAIGHT),
}

# Point-defence gun mounts (PxPointDefense) at the corners of the hull (t, s): sponsons fore and aft on both sides,
# like the Phalanx / Kashtan mounts of real carriers. Small ships get two.
MOUNTS = [(0.80, 0.95), (0.80, -0.95), (-0.88, 0.95), (-0.88, -0.95)]
SMALL_MOUNTS = [(0.80, 0.95), (-0.88, -0.95)]
SMALL = {"CV1", "CVTR", "CVIT", "CVEG", "CVIR"}

# Carriers without a flight deck yet (no jet of their nation fits): only their gun mounts are written. They place
# them with the engine's BodyOrientation.LocalToWorld, which foreshortens by sin(40 degrees).
DEFENCE_ONLY = ["CVEG", "CVJP", "CVIR"]
ENGINE_FORESHORTENING = math.sin(math.radians(40))

# Facing of parked jets relative to the ship (WAngle, counter-clockwise): 45 degrees in from the edge, nose forward.
STARBOARD_FACING = 128  # parked on the starboard edge: nose to port-forward
PORT_FACING = 896  # parked on the port edge: nose to starboard-forward


def load_jet():
    sheet = Image.open(JET_SPRITE).convert("RGBA")
    size = sheet.width // COLUMNS
    frames = [sheet.crop(((i % COLUMNS) * size, (i // COLUMNS) * size, (i % COLUMNS + 1) * size, (i // COLUMNS + 1) * size))
              for i in range(32)]
    alpha = np.array(frames[0].getchannel("A")) > 200
    ys, xs = np.nonzero(alpha)
    # Size in hull-sprite pixels at flying size.
    k = JET_SCALE / SCALE
    return frames, (ys.max() - ys.min()) * k, (xs.max() - xs.min()) * k


def deck(actor):
    sheet = Image.open(os.path.join(UNITS, actor.lower() + ".png")).convert("RGBA")
    size = sheet.width // COLUMNS
    frame = sheet.crop((0, 0, size, size))
    rgba = np.array(frame).astype(int)
    alpha = rgba[..., 3]
    hull = alpha >= 250
    # Rows with at least a few opaque pixels: ignores stray antenna/mast pixels beyond the bow and stern.
    rows = [y for y in range(size) if hull[y].sum() >= 8]
    bow, stern = min(rows), max(rows)
    cols = np.nonzero(hull[bow:stern + 1].sum(axis=0) >= (stern - bow) // 4)[0]
    port, starboard = cols.min(), cols.max()
    r, g, b = rgba[..., 0], rgba[..., 1], rgba[..., 2]
    island = (alpha > 100) & (g > r + 30) & (g > b + 30)
    island = binary_dilation(island, iterations=7)
    return frame, size, hull, island, (bow, stern, port, starboard)


def to_px(ts, outline):
    bow, stern, port, starboard = outline
    t, s = ts
    return np.array([port + (starboard - port) * (s + 1) / 2, stern + (bow - stern) * (t + 1) / 2])


def foreshortening(actor):
    """How much the renders shorten the north-south axis: hull length bow-up (frames 0, 16) / side-on (frames 8, 24).

    The hulls are rendered with a tilted camera, so in the bow-up frame the ship looks shorter than side-on.
    """
    sheet = Image.open(os.path.join(UNITS, actor.lower() + ".png")).convert("RGBA")
    size = sheet.width // COLUMNS

    def extent(i):
        a = np.array(sheet.crop(((i % COLUMNS) * size, (i // COLUMNS) * size, (i % COLUMNS + 1) * size, (i // COLUMNS + 1) * size)).getchannel("A")) >= 250
        rows = np.nonzero(a.sum(axis=1) >= 8)[0]
        cols = np.nonzero(a.sum(axis=0) >= 8)[0]
        return cols.max() - cols.min(), rows.max() - rows.min()

    return (extent(0)[1] + extent(16)[1]) / (extent(8)[0] + extent(24)[0])


def to_local(p, size, squash):
    """Sprite pixel (bow-up frame) -> true (forward, right) ship coordinates in world units from the ship's centre.

    In the bow-up frame the ship's length is foreshortened by squash; PxCarrierDeck applies it again for whatever
    heading the ship has (Foreshortening), so undo it here.
    """
    return round((size / 2 - p[1]) * WU_PER_PX / squash), round((p[0] - size / 2) * WU_PER_PX)


def segment_mask(shape, a, b, half_width):
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
    p = np.stack([xs, ys], axis=-1).astype(float)
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(1e-6, float(ab @ ab)), 0, 1)
    d = np.linalg.norm(p - (a + t[..., None] * ab), axis=-1)
    return d <= half_width


def nose_dir(facing):
    """Unit vector (x right, y down) of a jet with this facing in the north-up frame (counter-clockwise)."""
    a = facing / 1024 * 2 * math.pi
    return np.array([-math.sin(a), -math.cos(a)])


def pack(hull, keepout, outline, jet_len, jet_span, slots, parked_scale):
    """Greedy packing of slots jets at parked_scale; returns [(x, y, facing)] (may be fewer than slots)."""
    bow, stern, port, starboard = outline
    k = LANDED_SCALE * parked_scale
    length, span = jet_len * k, jet_span * k
    spacing = max(length, span) * (1 - OVERLAP)
    centre_x = (port + starboard) / 2
    usable = hull & ~keepout
    # Tails may hang out over the water (not over the island or the working areas).
    overhang = binary_dilation(hull, iterations=max(1, int(length * 0.3))) & ~keepout
    edge = binary_dilation(hull, iterations=max(1, int(length * 0.12))) & ~keepout
    h, w = hull.shape

    def ok(mask, p):
        x, y = int(round(p[0])), int(round(p[1]))
        return 0 <= x < w and 0 <= y < h and mask[y, x]

    candidates = []
    for y in range(bow, stern + 1, 2):
        for x in range(port - int(length * 0.3), starboard + int(length * 0.3) + 1, 2):
            c = np.array([x, y], float)
            facing = STARBOARD_FACING if x >= centre_x else PORT_FACING
            n = nose_dir(facing)
            side = np.array([-n[1], n[0]])
            nose, mid, tail = c + n * length * 0.42, c + n * length * 0.18, c - n * length * 0.4
            # Nose, cockpit, centre and the front of the tail on deck; only the tail end and wing tips hang over the water.
            on_deck = all(ok(usable, q) for q in (nose, mid, c, c - n * length * 0.12))
            over = all(ok(overhang, q) for q in (tail, c + side * span * 0.42, c - side * span * 0.42,
                                                  c - n * length * 0.2 + side * span * 0.3, c - n * length * 0.2 - side * span * 0.3))
            if on_deck and over:
                # Edge spots first (like a real deck), then from the bow aft.
                candidates.append((-abs(x - centre_x), y, c, facing))

    candidates.sort(key=lambda e: (round(e[0] / 4), e[1]))
    spots = []
    for _, _, c, facing in candidates:
        if all(np.linalg.norm(c - np.array(s[:2])) >= spacing for s in spots):
            spots.append((c[0], c[1], facing))
            if len(spots) == slots:
                break

    return spots


def best_layout(hull, keepout, outline, jet_len, jet_span, slots):
    lo, hi, best = 0.25, MAX_PARKED_SCALE, None
    for _ in range(14):
        mid = (lo + hi) / 2
        spots = pack(hull, keepout, outline, jet_len, jet_span, slots, mid)
        if len(spots) >= slots:
            lo, best = mid, (mid, spots)
        else:
            hi = mid

    return best or (lo, pack(hull, keepout, outline, jet_len, jet_span, slots, lo))


def draw_jets(img, frames, spots, parked_scale):
    k = JET_SCALE / SCALE * LANDED_SCALE * parked_scale
    for x, y, facing in sorted(spots, key=lambda s: s[1]):
        fr = frames[int(round(facing / 32)) % 32]
        fr = fr.resize((max(1, int(fr.width * k)), max(1, int(fr.height * k))), Image.LANCZOS)
        img.alpha_composite(fr, (int(x - fr.width / 2), int(y - fr.height / 2)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    frames, jet_len, jet_span = load_jet()
    lines = [
        "# Flight decks of the carriers (RedAlert Project X, IDEA-08 2c A1).",
        "# GENERATED by artsrc/units/carrier/make_carrier_decks.py from the HD art - edit that script, not this file.",
        "",
    ]
    if args.preview:
        os.makedirs(PREVIEW, exist_ok=True)
        sheets = []

    for actor, (types, slots, template) in CARRIERS.items():
        tpl = dict(template, **OVERRIDES.get(actor, {}))
        frame, size, hull, island, outline = deck(actor)
        bow, stern, port, starboard = outline
        width = starboard - port

        points = {name: to_px(tpl[name], outline) for name in ("CatapultStart", "Launch", "Touchdown", "Rollout")}
        (sa, sb, shw) = tpl["Strip"]
        strip = segment_mask(hull.shape, to_px(sa, outline), to_px(sb, outline), shw * width)
        track = segment_mask(hull.shape, points["CatapultStart"], points["Launch"] + (points["Launch"] - points["CatapultStart"]) * 0.2,
                             max(tpl["Track"] * width, 1)) if tpl["Track"] > 0 else np.zeros_like(hull)
        # Jets wait at the catapult start before the shot: keep a jet-sized space clear there.
        start = segment_mask(hull.shape, points["CatapultStart"], points["CatapultStart"], 0.3 * width)
        keepout = island | strip | track | start

        parked_scale, spots = best_layout(hull, keepout, outline, jet_len, jet_span, slots)
        if len(spots) < slots:
            print(f"{actor}: only {len(spots)} of {slots} slots fit")

        squash = foreshortening(actor)
        local = {name: to_local(p, size, squash) for name, p in points.items()}
        lines += [
            f"{actor}:",
            "\tPxCarrierDeck:",
            f"\t\tSlots: {slots}",
            f"\t\tForeshortening: {round(squash * 1000)}",
            f"\t\tDeckTypes: {types}",
            f"\t\tCatapultStart: {local['CatapultStart'][0]},{local['CatapultStart'][1]},0",
            f"\t\tLaunchOffset: {local['Launch'][0]},{local['Launch'][1]},0",
            f"\t\tRecoveryOffset: {local['Touchdown'][0]},{local['Touchdown'][1]},0",
            f"\t\tRolloutOffset: {local['Rollout'][0]},{local['Rollout'][1]},0",
            "\t\tParkOffsets: " + ", ".join("{},{},0".format(*to_local((x, y), size, squash)) for x, y, _ in spots),
            "\t\tParkFacings: " + ", ".join(str(f) for _, _, f in spots),
            f"\t\tParkedScale: {parked_scale:.3f}",
            "\t\tLaunchSound: ra|audio/aircraft/jet-pass1.wav",
            "\t\tLandSound: ra|audio/aircraft/jet-pass3.wav",
            "",
        ]
        mounts = [to_local(to_px(m, outline), size, squash) for m in (SMALL_MOUNTS if actor in SMALL else MOUNTS)]
        lines[-1:-1] = [
            "\tPxPointDefense:",
            "\t\tMounts: " + ", ".join(f"{f},{r},0" for f, r in mounts),
        ]
        print(f"{actor}: {len(spots)}/{slots} spots, parked scale {parked_scale:.2f} (was {OLD_PARKED_SCALE})")

        if args.preview:
            crop = (max(0, port - 60), max(0, bow - 20), min(size, starboard + 60), min(size, stern + 20))
            before = frame.copy()
            old = [(*to_px((t, s), outline), f) for (t, s), f in
                   zip([(0.53, 0.62), (0.33, 0.62), (0.13, 0.62), (-0.56, 0.62), (-0.76, 0.62), (-0.91, 0.62)], [128] * 6)]
            draw_jets(before, frames, old[:slots], OLD_PARKED_SCALE)

            after = frame.copy()
            overlay = Image.new("RGBA", after.size, (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            for mask, color in [(strip, (0, 255, 120, 40)), (track, (255, 140, 0, 50))]:
                ys, xs = np.nonzero(mask & hull)
                for x, y in zip(xs[::3], ys[::3]):
                    od.point((x, y), fill=color)
            after.alpha_composite(overlay)
            draw_jets(after, frames, spots, parked_scale)
            d = ImageDraw.Draw(after)
            for name, color in [("CatapultStart", (255, 140, 0, 255)), ("Launch", (255, 60, 0, 255)),
                                ("Touchdown", (0, 255, 120, 255)), ("Rollout", (0, 160, 255, 255))]:
                x, y = points[name]
                d.ellipse((x - 4, y - 4, x + 4, y + 4), outline=color, width=2)

            pair = Image.new("RGBA", ((crop[2] - crop[0]) * 2 + 10, crop[3] - crop[1]), (24, 48, 72, 255))
            pair.alpha_composite(before.crop(crop), (0, 0))
            pair.alpha_composite(after.crop(crop), (crop[2] - crop[0] + 10, 0))
            pair.save(os.path.join(PREVIEW, actor.lower() + ".png"))
            sheets.append(pair)

    for actor in DEFENCE_ONLY:
        frame, size, hull, island, outline = deck(actor)
        mounts = [to_local(to_px(m, outline), size, ENGINE_FORESHORTENING) for m in (SMALL_MOUNTS if actor in SMALL else MOUNTS)]
        lines += [
            f"{actor}:",
            "\tPxPointDefense:",
            "\t\tMounts: " + ", ".join(f"{f},{r},0" for f, r in mounts),
            "",
        ]

    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print("wrote", os.path.relpath(OUT, ROOT))

    if args.preview:
        w = sum(s.width for s in sheets) + 20 * len(sheets)
        h = max(s.height for s in sheets)
        sheet = Image.new("RGBA", (w, h), (24, 48, 72, 255))
        x = 0
        for s in sheets:
            sheet.alpha_composite(s, (x, 0))
            x += s.width + 20
        sheet.save(os.path.join(PREVIEW, "all.png"))


if __name__ == "__main__":
    main()
