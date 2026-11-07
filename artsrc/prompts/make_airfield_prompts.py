#!/usr/bin/env python3
"""
Generates artsrc/prompts/airfield-prompts.md: ChatGPT image prompts for the slot airfields and helipads of IDEA-06
(docs/DESIGN-IDEAS.md): the redesigned Airfield (4 slots), Air Base (10), Air Force Base (20), Strategic Air
Command (40), and the Helipad (1), Heliport (4) and Air Cavalry Base (10). Plus a sidebar cameo for each.

The building prompts use the same render rules as gemini-prompts.md (camera, footprint, intact + damaged side by
side, magenta background, green team colour), so the results go through artsrc/buildings/build_all.py like the
other buildings. What is added: the parking pads are drawn EMPTY (planes are separate actors that park on them),
flat, evenly spaced in a fixed grid and not covered by roofs, so the SlotOffsets in the rules can be measured
from the picture. Both sides build these, so they use the shared military style; national looks come later (IDEA-01).

  python3 artsrc/prompts/make_airfield_prompts.py
  python3 artsrc/prompts/generate_images.py --prompts airfield-prompts.md --category buildings
  python3 artsrc/prompts/generate_images.py --prompts airfield-prompts.md --category cameos
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_prompts import BUILDING, STYLE, TEAM  # noqa: E402
from make_cameo_prompts import PROMPT as CAMEO, SCENE, SIDE  # noqa: E402

OUT = os.path.join(HERE, "airfield-prompts.md")

# Real scale (IDEA-06 decision 2026-10-27): 1 map cell = about 10 m (the 17.5 m MiG covers 1.75 cells), so every pad,
# shelter, hangar, tower and runway WIDTH is true size. Only runway length is cut to the base width; OpenRA planes
# don't need a runway. A jet pad is 2 x 2 cells (20 m square), enough for a parked fighter in any direction.
SCALE = (
    " Real-world scale: one map tile is 10 metres, and a fighter jet is about 17 metres long, so every part of the base "
    "has true real-life size relative to the tiles; only the runway is shorter than a real one."
)

# Added to every airfield description: the pads must work as parking slots in game.
PADS = (
    " The parking pads are the most important part: exactly {slots} {pad}, {layout}. Every pad is flat at ground level, "
    "the same size{size}, evenly spaced on a regular grid, with a clear painted outline, and completely EMPTY: no aircraft, "
    "no vehicles, no people and no objects on any pad. Nothing (roof, tower, crane, wire) hangs over a pad, so each pad "
    "is fully visible from above."
)
JET_PAD = ", each a square 2 x 2 tiles (20 x 20 metres)"

# One image per version for bases too big to draw well in half a 2:1 image. The damaged prompt is run with the
# intact image attached (--ref) and the two are joined side by side before build_all.py.
SINGLE = (
    "Game asset for a top-down real-time strategy game: a single building, {state}. "
    "{desc} "
    "View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, "
    "the front of the building faces the bottom of the image, no perspective distortion, the whole building visible and centred. "
    "The building's base covers a {w} x {h} square-tile footprint (width {w}, depth {h}). "
    "{style}. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. "
    "Lighting: sun from the top-left; the building casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. "
    "{team} "
    "Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, "
    "no labels, no logo, no watermark, no border. Landscape image, aspect ratio 3:2."
)
DAMAGED_STATE = (
    "heavily battle-damaged. The attached image shows this exact building intact: keep exactly the same layout, size, "
    "camera angle and position, and only add the damage: blackened scorch marks, cracked and broken armour panels, "
    "bent and broken parts{extra}, exposed rebar and twisted metal, debris, small fires and thin dark smoke; still "
    "standing and clearly the same building, not destroyed; its surviving team-colour areas stay green"
)

# id, name, footprint (w, h), slots, pad kind, pad layout, team-colour areas, description, extra damage, cameo subject,
# split (intact and damaged as two images)
AIRFIELDS = [
    ("afld", "Airfield", (6, 5), 4, "jet parking pads",
     "in a 2 x 2 grid filling the left two thirds of the base",
     "the pad outlines and the tower roof",
     "An Airfield (redesigned, Red Alert 2 style): a concrete air apron. Along the right side: a small control tower "
     "(2 x 2 tiles) and a fuel bowser bay. Along the front edge: a 1-tile-wide taxiway. Floodlight poles at the corners.",
     ", the control tower cab shattered, cracks across the apron",
     "a compact military Airfield apron with four parking pads next to a small control tower, one jet fighter parked on a pad",
     False),
    ("abas", "Air Base", (8, 7), 6, "jet parking pads",
     "in two rows of 3 pads, on the left three quarters of the apron",
     "the pad outlines, the hangar roof stripe and the tower roof",
     "An Air Base: a concrete air apron. Along the whole back edge: a maintenance hangar (8 tiles wide, 2 tiles deep) "
     "with its big doors closed, where four more jets are kept inside. On the right side: a control tower (2 x 2 tiles) "
     "and fuel tanks. Along the front edge: a 1-tile-wide taxiway. Floodlight poles.",
     ", the hangar roof caved in, the control tower cab shattered",
     "a military Air Base with jets parked on two rows of pads in front of a large closed hangar and a control tower",
     False),
    # Compact redesign (2026-11-07, like sacm: only the pads and a tower; was 12x9 with a runway, 6 shelters and a
    # fuel depot, art kept in artsrc/buildings/src/old/afbs-v1-12x9.png).
    ("afbs", "Air Force Base", (10, 6), 8, "jet parking pads",
     "in two straight rows of 4 pads each, filling the left four fifths of the base",
     "the pad outlines and the tower roof",
     "A compact Air Force Base: a plain concrete air apron with nothing on it but the parking pads and, along the "
     "right edge, one control tower with a glass cab and a small rotating radar on top (2 x 2 tiles at its base). No "
     "runways, no hangars, no shelters, no fuel tanks and no other buildings. A thin armoured kerb with small edge "
     "lights runs around the apron.",
     ", the radar torn off the tower, the cab windows shattered, cracks and craters across the apron",
     "a compact military Air Force Base: two rows of jet fighters parked on pads next to a control tower",
     True),
    # Compact redesign (2026-11-07, user: only the pads and a tower, smallest possible; was 20x15 with runways and
    # hangars, art kept in artsrc/buildings/src/old/sacm-v1-20x15.png).
    ("sacm", "Strategic Air Command", (12, 6), 10, "jet parking pads",
     "in two straight rows of 5 pads each, filling the left five sixths of the base",
     "the pad outlines and the tower roof",
     "A compact Strategic Air Command: a plain concrete air apron with nothing on it but the parking pads and, along "
     "the right edge, one tall command tower with a radar dish on top (2 x 2 tiles at its base). No runways, no "
     "hangars, no shelters, no fuel tanks and no other buildings. A thin armoured kerb with small edge lights runs "
     "around the apron.",
     ", the radar dish torn off the tower, the tower windows shattered, cracks and craters across the apron",
     "a compact military Strategic Air Command: two rows of jet fighters parked on pads next to a tall command tower with a radar dish",
     True),
    ("hpad", "Helipad", (2, 2), 1, "helicopter landing pad", "filling most of the footprint, with a large H marking in the middle",
     "the landing circle markings",
     "A Helipad: a raised armoured square helicopter landing platform with edge lights, a small control booth at one back "
     "corner and a fuel hose reel.",
     ", the landing pad cracked and lights smashed",
     "an armoured military Helipad with a large H marking and edge lights, a helicopter landing on it",
     False),
    ("hprt", "Heliport", (4, 3), 4, "round helicopter landing pads, each with an H marking",
     "in a 2 x 2 grid around a small central control tower",
     "the landing circle markings and the tower roof",
     "A Heliport: a concrete platform with a small control tower in the middle, a windsock mast, edge lights and a "
     "fuel truck bay at one corner.",
     ", the control tower cab shattered, pads cracked and lights smashed",
     "a military Heliport with four round H landing pads around a small control tower, helicopters parked on two pads",
     False),
    ("acav", "Air Cavalry Base", (6, 5), 10, "round helicopter landing pads, each with an H marking",
     "in two straight rows of 5 pads each, filling the front two thirds of the base",
     "the landing circle markings and the hangar roof stripe",
     "An Air Cavalry Base: a large concrete helicopter base with a wide maintenance hangar along the back edge "
     "(its big doors open), a control tower, a rotor-blade rack, fuel tanks and an ammunition bunker.",
     ", the hangar roof caved in, a fuel tank burning, pads cracked",
     "a large military Air Cavalry Base with rows of attack helicopters parked on round H pads in front of a big maintenance hangar",
     False),
]

# Slots kept inside hangars / shelters (not drawn as pads): IDEA-06 section 3.
HIDDEN = {"afld": 0, "abas": 4, "afbs": 0, "sacm": 0}


def main():
    out = [
        "# RedAlert Project X - airfield prompts (ChatGPT)",
        "",
        "GENERATED by `artsrc/prompts/make_airfield_prompts.py` - edit that script, not this file.",
        "Design: IDEA-06 *Airfields with parking slots* in `docs/DESIGN-IDEAS.md`.",
        "",
        "**How to use**",
        "",
        "- Unattended: `python3 artsrc/prompts/generate_images.py --prompts airfield-prompts.md --category buildings`",
        "  (then `--category cameos`). Images go to `assets/buildings/` and `assets/cameos/`.",
        "- By hand: one new ChatGPT chat per prompt. Attach the approved Construction Yard (`artsrc/buildings/src/fact-chatgpt.png`)",
        "  and start with: *\"Match the style, camera angle, lighting and level of detail of the attached image, but draw the",
        "  building described below.\"* Save each image under its **Save as** name.",
        "- Reject a building image if: a pad has an aircraft or object on it, the pad count or grid is wrong, a roof or tower",
        "  covers part of a pad, the two copies differ in size or angle, or the background is not flat magenta.",
        "  The pad count matters less on the 20 and 40 slot bases (the game draws its own slot markings on top), but the",
        "  pads must be in clean, even rows.",
        "- The slot markings themselves (empty pad, \"reserved\" pad) are small overlay sprites drawn by code, not by ChatGPT.",
        "- Real scale (1 tile = 10 m): a jet pad is 2 x 2 tiles. Bigger bases keep the rest of their slots inside hangars",
        "  and shelters (planes taxi in and are hidden), so only some slots are drawn as pads.",
        "- Air Force Base and Strategic Air Command are drawn as two images each: run `afbs` first, then",
        "  `--only afbs-damaged --ref ../../assets/buildings/afbs.png` (same for sacm), and join them side by side (intact left) before",
        "  `build_all.py`.",
        "",
        "New ids: `abas` Air Base, `afbs` Air Force Base, `sacm` Strategic Air Command, `hprt` Heliport, `acav` Air Cavalry",
        "Base. `afld` and `hpad` replace the current art (the Airfield grows from 3x2 to 6x5).",
        "",
        "## Buildings",
        "",
        "Wide 2:1 images, intact (left) + damaged (right). Footprints are in map cells (width x depth).",
        "",
    ]
    n = 0
    for bid, name, (w, h), slots, pad, layout, areas, desc, extra, _, split in AIRFIELDS:
        jet = bid in HIDDEN
        full = desc + PADS.format(slots=slots, pad=pad, layout=layout, size=JET_PAD if jet else "") + (SCALE if jet else "")
        team = TEAM.format(areas=areas)
        total = slots + HIDDEN.get(bid, 0)
        title = "%s (%dx%d, %d slot%s%s)" % (name, w, h, total, "" if total == 1 else "s",
                                            ": %d pads + %d inside" % (slots, HIDDEN[bid]) if HIDDEN.get(bid) else "")
        if split:
            for suffix, state in (("", "intact and new"), ("-damaged", DAMAGED_STATE.format(extra=extra))):
                n += 1
                prompt = SINGLE.format(state=state, desc=full, w=w, h=h, style=STYLE["neutral"], team=team)
                out += ["### %d. %s%s" % (n, title, ", damaged" if suffix else ", intact"),
                        "Save as: `%s%s.png`" % (bid, suffix), "", "```", prompt, "```", ""]
            continue
        n += 1
        prompt = BUILDING.format(desc=full, w=w, h=h, style=STYLE["neutral"], team=team, extra=extra)
        out += ["### %d. %s" % (n, title), "Save as: `%s.png`" % bid, "", "```", prompt, "```", ""]

    out += ["## Cameos", "", "Sidebar build icons, same style as `cameo-prompts.md`. Here the pads show parked aircraft.", ""]
    for bid, name, *_, subject, _split in AIRFIELDS:
        n += 1
        prompt = CAMEO.format(subject=subject, scene=SCENE["building"], side=SIDE["neutral"])
        out += ["### %d. %s" % (n, name), "Save as: `%s.png`" % bid, "", "```", prompt, "```", ""]

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("wrote %s: %d prompts" % (OUT, n))


if __name__ == "__main__":
    main()
