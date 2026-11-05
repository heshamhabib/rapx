#!/usr/bin/env python3
"""
Generates artsrc/prompts/jet-prompts.md: one ChatGPT image prompt per aircraft in the IDEA-12 jet roster
(docs/DESIGN-IDEAS.md) plus the other aircraft from the design ideas. Edit the tables below and re-run.

Each prompt asks for a 3D model reference image (like the unit prompts in gemini-prompts.md): one jet on a
white background, seen from the front-left and above, with the real aircraft's shape but a made-up name,
no real markings, the nation's paint scheme and green team-colour areas.

The shared wording (view, lighting, background, team colour) is most of every prompt, so each aircraft's
recognition features come first and are stated as must-haves: with only the real aircraft's name to go on,
the image generator draws a generic jet and similar aircraft come out looking the same. Keep the shape notes
in the tables concrete (nose, intakes, wings, tail, engines). The roster starts at tier 2: piston fighters
and first-generation (tier 0-1) jets were dropped. The images then go through an
image-to-3D tool (.glb) and the Blender pipeline renders every facing.

  python3 artsrc/prompts/make_jet_prompts.py
  python3 artsrc/prompts/generate_images.py --prompts jet-prompts.md --category jets

Sections in the output:
  ## Jets            one base model per real aircraft (the 3D models to make)
  ## Jet variants    the same aircraft flown by another nation, or a close version of it (optional)
  ## Other aircraft  non-jet aircraft from the ideas (tiltrotor, airship, drone)
"""
import os
import re

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jet-prompts.md")

# What each role carries / looks like.
ROLE = {
    "air": ("air-superiority fighter", "air-to-air missiles on the wing pylons and wingtips"),
    "int": ("interceptor", "large long-range air-to-air missiles under the wings and fuselage"),
    "multi": ("multirole fighter", "a mixed load of air-to-air missiles and precision bombs under the wings"),
    "attack": ("ground-attack aircraft", "rocket pods and bombs under the wings"),
    "strike": ("strike aircraft", "heavy bombs and air-to-ground missiles under the wings and fuselage"),
    "stealth": ("stealth fighter", "no external weapons (weapons are carried in internal bays), smooth radar-absorbent skin"),
    "bomber": ("bomber", "no external weapons, bomb bay doors closed"),
    "carrier": ("carrier-based naval jet", "a naval load of missiles and bombs, an arrestor hook under the tail, folding wings shown spread"),
    "vtol": ("vertical take-off jump jet", "rotating vectored-thrust exhaust nozzles on the fuselage sides, light weapons under the wings"),
    "recon": ("high-altitude reconnaissance jet", "no weapons, sensor bays only"),
    "ucav": ("unmanned combat drone", "no cockpit and no canopy, smooth stealthy body, weapons in internal bays"),
    "light": ("light attack jet", "small rocket pods and light bombs under the wings"),
    "transport": ("giant cargo transport aircraft", "no weapons"),
}

# Paint scheme per nation. Green camouflage is never used (green = team colour).
NATION = {
    "soviet": "Soviet air force light grey with blue-grey upper surfaces",
    "allied": "NATO two-tone low-visibility grey",
    "usa": "US air force two-tone low-visibility grey",
    "france": "French air force blue-grey and dark grey",
    "germany": "German air force two-tone grey-blue",
    "england": "Royal Air Force medium sea grey and dark sea grey",
    "italy": "Italian air force light grey",
    "turkey": "Turkish air force two-tone grey",
    "pakistan": "Pakistan air force two-tone grey",
    "japan": "Japanese two-tone sea blue",
    "southkorea": "Korean air force dark two-tone grey",
    "russia": "Russian blue-grey splinter camouflage",
    "ukraine": "Ukrainian digital pixel camouflage in greys",
    "cuba": "Cuban sand and brown camouflage",
    "india": "Indian air force grey with blue-grey upper surfaces",
    "egypt": "Egyptian desert camouflage in sand, tan and brown",
    "china": "Chinese air force dark grey-blue",
    "iran": "Iranian desert camouflage in sand, tan and brown",
}
STEALTH_PAINT = "dark charcoal-grey radar-absorbent finish"
# Aircraft whose real finish is part of their look; the shape notes rely on these.
PAINT_OVERRIDE = {
    "AF-117 Nightjar": "all-black faceted radar-absorbent finish",
    "SR-7 Blackwing": "all-black heat-resistant titanium finish",
    "Tv-160 Swanwing": "glossy anti-flash white finish",
}

NATION_LABEL = {
    "soviet": "Soviet side", "allied": "Allied side", "usa": "USA",
    "france": "France", "germany": "Germany", "england": "England", "italy": "Italy", "turkey": "Turkey",
    "pakistan": "Pakistan", "japan": "Japan", "southkorea": "South Korea", "russia": "Russia",
    "ukraine": "Ukraine", "cuba": "Cuba", "india": "India", "egypt": "Egypt", "china": "China", "iran": "Iran",
}

# (game name, real inspiration, nation, tier, role, silhouette notes)
# tier: 0-5 or "X". One aircraft per silhouette type: at sprite size (~50px) only the outline survives,
# so near-twins (Su-27/Su-35, Rafale/Typhoon, ...) are left out. Each nation flies these in its own paint;
# add an aircraft only if its silhouette is new. The full earlier roster is in jet_roster_full.py.
# Notes start with what makes the outline unique.
JETS = [
    # --- Fighters and interceptors ---
    ("MiK-21 Fishbone", "MiG-21", "soviet", 2, "air", "small tailed delta wing with a separate swept tailplane, slim tube-shaped body, round nose intake with a shock cone, single tall swept fin"),
    ("AF-104 Starflash", "F-104 Starfighter", "allied", 2, "int", "very long needle-nosed body with tiny thin straight wings set far back, a T-tail on top of the fin, half-cone intakes on the sides"),
    ("AF-4 Spectre II", "F-4 Phantom II", "allied", 2, "int", "heavy two-seat twin-engine jet whose outer wing panels bend sharply upwards and whose tailplanes droop sharply downwards, big side intakes"),
    ("MiK-23 Flintlock", "MiG-23", "soviet", 3, "multi", "variable-sweep wings shown half swept, a long pointed body, box side intakes, one tall fin and a large folding ventral fin under the tail"),
    ("MiK-25 Foxbane", "MiG-25", "soviet", 3, "int", "huge long box-shaped intakes along a slab-sided body, thin trapezoid wings, two tall outward-canted tail fins, two very large engine nozzles"),
    ("AF-14 Bobcat", "F-14 Tomcat", "allied", 3, "int", "two-seat carrier jet with variable-sweep wings shown spread wide, engines far apart in separate nacelles with a flat 'pancake' between them, twin tails"),
    ("Sk-27 Flankard", "Sukhoi Su-27", "soviet", 3, "air", "very large twin-engine fighter, engines widely spaced under a flat lifting body, twin tails outboard of the engines, long tail sting between the nozzles, big curved wing-root extensions"),
    ("AF-16 Fighting Kestrel", "F-16 Fighting Falcon", "allied", 3, "multi", "compact single-engine fighter with a gaping chin intake under the cockpit, frameless bubble canopy, cropped-delta wings blended into the body, one fin"),
    ("Mirago 2000", "Dassault Mirage 2000", "france", 3, "multi", "pure tailless delta wing with no tailplane and no canards, one tall fin, semicircular side intakes, slim single-engine body"),
    ("Rafal F4", "Dassault Rafale", "france", 4, "multi", "delta wing with clearly visible canard foreplanes just behind the cockpit, two engines side by side, intakes low on the fuselage sides"),
    ("Saeqa", "HESA Saeqeh (Iran)", "iran", 3, "air", "small F-5-style light fighter with a sharply pointed nose, short trapezoid wings, side intakes and TWO outward-canted tail fins instead of one"),
    # --- Ground attack ---
    ("AA-10 Thunderhog", "A-10 Thunderbolt II", "allied", 3, "attack", "long straight unswept wings, two big round engine pods mounted on top of the rear fuselage, twin tail fins at the ends of the tailplane, a huge cannon in the nose"),
    ("Sk-25 Rook", "Sukhoi Su-25", "soviet", 3, "attack", "armoured jet with straight shoulder wings slightly swept, two engines in long nacelles alongside the fuselage, one tall fin, many weapon pylons"),
    # --- Stealth ---
    ("AF-117 Nightjar", "F-117 Nighthawk", "allied", 3, "stealth", "faceted angular body made of flat triangular panels, sharply swept arrow wings, a V-tail of two flat fins, all-black finish"),
    ("AF-22 Raptorex", "F-22 Raptor", "allied", 5, "stealth", "diamond-shaped wings and diamond tailplanes, twin outward-canted fins, angled side intakes, flat rectangular engine nozzles"),
    ("AYF-23 Black Recluse", "Northrop YF-23", "allied", "X", "stealth", "diamond wings with no tailplane, two large slanted all-moving V-tail fins, engine exhausts in troughs on top of the rear body"),
    ("Sk-47 Berkov", "Sukhoi Su-47 Berkut", "soviet", "X", "stealth", "wings swept FORWARD (wing tips ahead of the wing roots), canard foreplanes, twin tails, long tail sting"),
    ("JX-20 Jade Dragon", "Chengdu J-20", "china", 5, "stealth", "very long slender stealth body with canard foreplanes behind the cockpit, a delta wing far back, twin canted fins and small ventral fins"),
    ("Qahir-X", "IAIO Qaher-313 concept (Iran)", "iran", "X", "stealth", "small angular single-seat stealth jet with a very large bubble canopy, wing tips bent sharply DOWNWARDS, twin canted fins, intakes above the wing roots"),
    # --- VTOL ---
    ("Harrow", "Harrier", "england", 3, "vtol", "short fat body with big round side intakes, shoulder wings that droop downwards, small outrigger wheels at the wing tips, four swivelling exhaust nozzles on the body sides"),
    ("Yk-141 Freestyler", "Yakovlev Yak-141", "soviet", "X", "vtol", "supersonic VTOL jet whose two tail fins sit on twin tail booms either side of a swivelling rear nozzle, box intakes, lift-jet doors behind the cockpit"),
    # --- Bombers and recon ---
    ("AB-2 Wraith", "B-2 Spirit", "allied", 5, "bomber", "huge tailless flying wing shaped like a boomerang with a saw-tooth trailing edge, no fuselage and no fins at all"),
    ("AB-52 Stratoforce", "B-52 Stratofortress", "usa", 2, "bomber", "huge long-bodied bomber with long drooping swept wings carrying eight engines in four double pods, one very tall tail fin"),
    ("Tv-160 Swanwing", "Tupolev Tu-160", "russia", 3, "bomber", "huge slender white bomber with variable-sweep wings shown half swept, a blended body and four engines in two pods under the wing roots"),
    ("Volcan", "Avro Vulcan", "england", 2, "bomber", "huge thick triangular delta-wing bomber with no tailplane, one large fin, engines buried in the wing roots with slot intakes"),
    ("SR-7 Blackwing", "SR-71 Blackbird", "usa", 3, "recon", "long flat black body with sharp chines along its sides, thin delta wings, two huge engine nacelles with pointed inlet spikes, two inward-canted fins on the nacelles"),
    # --- Naval ---
    ("Sea Vixa", "de Havilland Sea Vixen", "england", 2, "carrier", "twin-boom carrier fighter: two long tail booms joined at the back by a high tailplane, a pod-like body with the cockpit offset to one side"),
    # --- Drones ---
    ("AX-47 Stingray", "Northrop Grumman X-47B", "allied", "X", "ucav", "short wide tailless cranked-kite flying wing with a dorsal intake behind the nose, a carrier arrestor hook, no cockpit"),
    ("Grom-K", "Kronshtadt Grom", "russia", "X", "ucav", "small jet combat drone with a slim body, an intake on top behind the nose, short swept wings and a V-tail, no cockpit"),
    # --- Light attack and transport ---
    ("L-39U Albatross", "Aero L-39 Albatros", "ukraine", 2, "light", "small two-seat jet trainer with straight wings and fuel tanks on the wing tips, intakes on the sides behind the cockpit, armed for light attack"),
    ("An-225 Dreamer", "Antonov An-225 Mriya", "ukraine", 4, "transport", "the largest aircraft ever: six engines under high wings, a very long body, twin tail fins at the ends of the tailplane"),
]

# (game name, base game name, real inspiration, nation, tier, role, how it differs)
# Empty on purpose: variants were only repaints, and the game recolours models per nation and player.
VARIANTS = []


# (game name, save-as name, kind, description, nation)
OTHER = [
    ("Kestrel Tiltrotor", "kestrel-tiltrotor", "tiltrotor aircraft",
     "A V-22 Osprey-style tiltrotor transport with two huge rotors on wingtip engine nacelles tilted up for hovering, a rear loading ramp and a twin tail.", "usa"),
    ("Zeppelin", "zeppelin", "armoured airship",
     "A huge armoured Soviet bombing airship: a long rigid cigar-shaped envelope with armour plates, an armoured gondola with bomb bays underneath and four propeller engines.", "soviet"),
    ("Swarm Drone", "swarm-drone", "small combat drone",
     "A small loitering combat drone for a drone swarm: delta wing, rear pusher propeller, a sensor ball under the nose and a small warhead.", "turkey"),
]

PROMPT = (
    "3D model reference image of a single {kind} for a real-time strategy game: {lead}. "
    "Key recognition features, which must be clearly visible: {features}. "
    "The silhouette must be unmistakably the real {real}, not a generic {kind}: match its shape, proportions, "
    "wing planform, tail, intakes and engines closely, "
    "but it carries no real markings: no national insignia, no roundels, no stars, no flags, no serial numbers, no squadron badges, no text. "
    "Loadout: {load}. In flight configuration: landing gear retracted, canopy closed. "
    "View: three-quarter view from the front-left and above (about 40 degrees), so the top of the wings is clearly visible, "
    "the whole aircraft visible and centred, nose pointing to the upper left, orthographic, no perspective distortion. "
    "Paint: {paint}, realistic panel lines and light weathering; no green camouflage. "
    "Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. "
    "Neutral even studio lighting, no dramatic shadows. "
    "Paint the team-colour areas ({team}) in flat pure bright green (#00FF00); use no other green anywhere on the aircraft. "
    "Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image."
)


def slug(name):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower().replace("é", "e").replace("í", "i"))).strip("-")


def paint(nation, tier, role):
    if role in ("stealth", "ucav") or (role == "bomber" and tier in (5, "X")):
        return STEALTH_PAINT
    return NATION[nation]


def team(role):
    if role in ("ucav", "bomber") or role == "stealth":
        return "a band across the top of the fuselage and the wingtips"
    if role == "transport":
        return "the tail fins and a band around the fuselage"
    return "the tail fin and the wingtips"


def article(word):
    return "An" if word[0].lower() in "aeiou" else "A"


def loadout(role, tier, extra):
    """Weapons by role; tier 2 fighters get the early-missile era load."""
    if tier == 2 and role == "air":
        return "cannons and a pair of early heat-seeking missiles"
    return ROLE[role][1]


def kind_of(role, extra):
    return ROLE[role][0]


def tier_label(t):
    return "X (prototype / future)" if t == "X" else str(t)


def main():
    lines = [
        "# RedAlert Project X - jet roster image prompts (ChatGPT)",
        "",
        "Generated by `make_jet_prompts.py` from the IDEA-12 jet roster in `docs/DESIGN-IDEAS.md`. Do not edit by hand: edit the",
        "script and re-run it.",
        "",
        "**How to use**",
        "",
        "1. Automatic: `python3 artsrc/prompts/generate_images.py --prompts jet-prompts.md --category jets` runs every prompt",
        "   through ChatGPT and saves `assets/jets/<name>.png`. Add `--only af-22-raptorex,mik-21-fishbone` for a few.",
        "   There is one aircraft per silhouette type; each nation flies them in its own paint and team colour.",
        "2. Manual: start a new ChatGPT chat per aircraft (in the same chat it tends to edit the previous image), paste the",
        "   prompt, and save the image under its **Save as** name. `browser_helper.py` copies each prompt and files the downloads.",
        "   For a consistent look, attach the first approved jet image and add: *\"Match the style, camera angle, lighting and",
        "   level of detail of the attached image, but draw the aircraft described below.\"*",
        "3. Reject an image if it looks like a generic jet instead of the real aircraft (check the key recognition features),",
        "   real insignia or text, a non-white background,",
        "   landing gear down, or green outside the team-colour areas. Regenerate.",
        "4. Then, as with the other units: image-to-3D tool (Tripo AI, Meshy or Hunyuan3D) -> `<name>.glb` -> Blender pipeline",
        "   renders the 32 facings, shadow and sidebar icon. Variants can reuse their base model with a new paint texture.",
        "",
        "The real aircraft name is only a shape reference for the image generator; the game shows the made-up name.",
        "",
    ]
    n = 0
    shapes = {j[0]: j[5] for j in JETS}
    lines += ["## Jets", ""]
    for name, real, nation, tier, role, extra in JETS:
        n += 1
        kind = kind_of(role, extra)
        lead = "\"%s\" (%s, tier %s), based on the real %s" % (name, NATION_LABEL[nation], tier_label(tier), real)
        prompt = PROMPT.format(kind=kind, lead=lead, features=extra, real=real,
                               load=loadout(role, tier, extra), paint=PAINT_OVERRIDE.get(name, paint(nation, tier, role)),
                               team=team(role))
        lines += ["### %d. %s" % (n, name),
                  "Real inspiration: %s · %s · tier %s · %s" % (real, NATION_LABEL[nation], tier_label(tier), ROLE[role][0]),
                  "Save as: `%s.png  ->  %s.glb`" % (slug(name), slug(name)), "", "```", prompt, "```", ""]

    if VARIANTS:
        lines += ["## Jet variants", "",
                  "Optional: the same aircraft as a base model, in another nation's paint or a close version. If you skip these,",
                  "the game reuses the base model with team colour.", ""]
    for name, base, real, nation, tier, role, diff in VARIANTS:
        assert base in shapes, base
        n += 1
        kind = ROLE[role][0]
        lead = "\"%s\" (%s, tier %s), the %s of the real %s" % (name, NATION_LABEL[nation], tier_label(tier), diff, real)
        prompt = PROMPT.format(kind=kind, lead=lead, features="%s; %s" % (shapes[base], diff), real=real,
                               load=loadout(role, tier, ""), paint=paint(nation, tier, role), team=team(role))
        lines += ["### %d. %s" % (n, name),
                  "Variant of: %s · real: %s · %s · tier %s" % (base, real, NATION_LABEL[nation], tier_label(tier)),
                  "Save as: `%s.png  ->  %s.glb`" % (slug(name), slug(name)), "", "```", prompt, "```", ""]

    lines += ["## Other aircraft", ""]
    for name, save, kind, desc, nation in OTHER:
        n += 1
        prompt = (
            "3D model reference image of a single %s for a real-time strategy game. %s "
            "No real markings: no insignia, no flags, no text. "
            "View: three-quarter view from the front-left and above (about 40 degrees), the whole aircraft visible and centred, "
            "orthographic, no perspective distortion. Paint: %s, light weathering. "
            "Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. "
            "Neutral even studio lighting, no dramatic shadows. "
            "Paint the team-colour areas (the tail and a band around the body) in flat pure bright green (#00FF00); use no other green anywhere. "
            "Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image."
        ) % (kind, desc, NATION[nation])
        lines += ["### %d. %s" % (n, name), "Save as: `%s.png  ->  %s.glb`" % (save, save), "", "```", prompt, "```", ""]

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wrote %s: %d jets, %d variants, %d other (%d prompts)" % (OUT, len(JETS), len(VARIANTS), len(OTHER), n))


if __name__ == "__main__":
    main()
