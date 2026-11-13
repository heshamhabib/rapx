#!/usr/bin/env python3
"""
National jet roster (IDEA-12, first pass): one buildable aircraft per image in assets/jets/, each available
only to the nations that really fly (or flew, or have ordered) that aircraft.

Writes (GENERATED - edit this script, not the outputs):
- mods/rapx/rules/jets.yaml       actors + per-jet ProvidesPrerequisite on AFLD / HPAD (Factions = operators)
- mods/rapx/sequences/jets.yaml   images inheriting the stock mig / yak / tran sprites + a stock-size `icon`
- mods/rapx/fluent/jets.ftl       names and descriptions

Then run artsrc/px-cameos/generate.py: it cuts the sidebar cameos out of assets/jets/<file>.png.

Until the jets have their own 3D sprites they fly with the stock MiG / Yak / Chinook sprite and stats of that
base (scaled by role below). Operators come from docs/research/national-air-forces.md; deals reported but
unconfirmed in 2026 are counted as confirmed (user's call, 2026-10-26).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MOD = os.path.join(ROOT, "mods", "rapx")

UNION = ["allies", "usa", "england", "france", "germany", "japan", "southkorea", "italy", "egypt"]
VANGUARD = ["soviet", "russia", "ukraine", "cuba", "india", "china", "turkey", "pakistan", "iran"]

# Role -> (base actor, cost, HP, speed, description). Base actor: mig (Maverick strike), yak (machine guns), tran (transport)
# Jets in game, Balanced RTS proportions (a fighter about 2x a medium tank): 2.6x the 1/3 of their 3x-density
# renders. The sprites get blurry above 1/3; make.sh re-renders jets 2.6x bigger, then this drops back to 1/3.
JET_SCALE = 0.3333  # renders are 2.6x bigger (make.sh), so 1/3 gives the 2.6x size
JET_BOUNDS = "\tSelectable:\n\t\tBounds: 3000, 2800, 0, 0\n\t\tDecorationBounds: 3328, 3104, 0, 220"
# Big jets shrink smoothly as they descend (PxAltitudeScale: 60 % when parked) so they fit the airfield pads.
# It must come before the shadow, so the inherited WithShadow is replaced by one listed after it.
JET_LANDING = ("\tPxAltitudeScale:\n\t\tLandedScale: 0.6\n\t-WithShadow:\n"
               "\tWithShadow@SCALED:\n\t\tOffset: 43, 128, 0\n\t\tZOffset: -129")
ROLES = {
    "piston": ("yak", 700, 5000, 160, "Piston-engined fighter from the 1940s.\n  Cheap and quick to build\n  Strong vs Infantry and Light armor"),
    "light": ("yak", 900, 6000, 180, "Light attack jet.\n  Strong vs Infantry, Light armor and drones\n  Weak vs Fighters and Anti-Air"),
    "fighter": ("mig", 1600, 8000, 223, "Jet fighter.\n  Strong vs Buildings and Vehicles\n  Weak vs Anti-Air"),
    "interceptor": ("mig", 1800, 7000, 260, "Fast interceptor.\n  Strong vs Buildings and Vehicles\n  Weak vs Anti-Air"),
    "multirole": ("mig", 2000, 9000, 223, "Multirole fighter.\n  Strong vs Buildings and Vehicles\n  Weak vs Anti-Air"),
    "attack": ("mig", 1800, 14000, 170, "Armoured ground-attack jet.\n  Strong vs Tanks and Vehicles\n  Weak vs Fighters"),
    "stealth": ("mig", 3000, 9000, 240, "Stealth fighter.\n  Strong vs Buildings and Vehicles\n  Weak vs Anti-Air"),
    "vtol": ("mig", 1700, 8000, 190, "VTOL jump jet.\n  Strong vs Vehicles\n  Weak vs Anti-Air"),
    "carrier": ("mig", 1700, 8500, 210, "Naval strike fighter.\n  Strong vs Ships and Vehicles\n  Weak vs Anti-Air"),
    "bomber": ("mig", 4000, 25000, 150, "Heavy bomber.\n  Strong vs Buildings\n  Weak vs Fighters and Anti-Air"),
    "recon": ("mig", 2500, 7000, 340, "High-speed reconnaissance jet.\n  Very hard to catch\n  Weak vs Anti-Air"),
    "drone": ("yak", 1200, 4000, 210, "Unmanned combat drone.\n  Cheap, low health\n  Strong vs Infantry and Light armor"),
    "transport": ("tran", 1500, 20000, 120, "Transport aircraft.\n  Carries infantry\n  Unarmed"),
    "airship": ("mig", 5000, 40000, 70, "Armoured bombing airship.\n  Huge bomb load, very slow\n  Weak vs Anti-Air"),
}

# Tier -> extra prerequisites. "X" = prototype / experimental: one per player.
TIERS = {
    0: ["~techlevel.medium"],
    2: ["~techlevel.medium"],
    3: ["~techlevel.medium"],
    4: ["techcenter", "~techlevel.high"],
    5: ["techcenter", "~techlevel.high"],
    "X": ["techcenter", "~techlevel.high"],
}

# (id, asset file, game name, real aircraft, tier, role, operators)
JETS = [
    # --- USA and the Union shared roster ---
    ("f104", "af-104-starflash", "AF-104 Starflash", "F-104 Starfighter", 2, "interceptor",
     ["allies", "usa", "germany", "italy", "japan", "turkey", "pakistan"]),
    ("f4", "af-4-spectre-ii", "AF-4 Spectre II", "F-4 Phantom II", 2, "interceptor",
     ["allies", "usa", "england", "germany", "japan", "southkorea", "egypt", "turkey", "iran"]),
    ("f14", "af-14-bobcat", "AF-14 Bobcat", "F-14 Tomcat", 3, "interceptor", ["allies", "usa", "iran"]),
    ("f16", "af-16-fighting-kestrel", "AF-16 Fighting Kestrel", "F-16 Fighting Falcon", 3, "multirole",
     ["allies", "usa", "italy", "southkorea", "egypt", "turkey", "pakistan", "ukraine"]),
    ("a10", "aa-10-thunderhog", "AA-10 Thunderhog", "A-10 Thunderbolt II", 3, "attack", ["allies", "usa"]),
    ("f117", "af-117-nightjar", "AF-117 Nightjar", "F-117 Nighthawk", 3, "stealth", ["allies", "usa"]),
    ("sr71", "sr-7-blackwing", "SR-7 Blackwing", "SR-71 Blackbird", 3, "recon", ["usa"]),
    ("b52", "ab-52-stratoforce", "AB-52 Stratoforce", "B-52 Stratofortress", 2, "bomber", ["usa"]),
    ("f22", "af-22-raptorex", "AF-22 Raptorex", "F-22 Raptor", 5, "stealth", ["allies", "usa"]),
    ("b2", "ab-2-wraith", "AB-2 Wraith", "B-2 Spirit", 5, "bomber", ["allies", "usa"]),
    ("ho229", "hg-229-nachtfluegel", "HG-229 Nachtflügel", "Horten Ho 229", 5, "bomber", ["germany"]),
    ("yf23", "ayf-23-black-recluse", "AYF-23 Black Recluse", "Northrop YF-23", "X", "stealth", ["allies", "usa"]),
    ("x47", "ax-47-stingray", "AX-47 Stingray", "X-47B", "X", "drone", ["usa"]),
    ("v22", "kestrel-tiltrotor", "Kestrel Tiltrotor", "V-22 Osprey", 4, "transport", ["usa", "japan"]),
    # --- Japan ---
    ("f2", "af-2-zero-viper", "AF-2 Zero Viper", "Mitsubishi F-2", 4, "carrier", ["japan"]),
    # --- Europe ---
    ("harrier", "harrow", "Harrow", "Harrier / AV-8B", 3, "vtol", ["allies", "usa", "england", "italy", "india"]),
    ("m2000", "mirago-2000", "Mirago 2000", "Mirage 2000", 3, "multirole",
     ["allies", "france", "egypt", "india", "ukraine"]),
    ("rafale", "rafal-f4", "Rafal F4", "Dassault Rafale", 4, "multirole", ["france", "egypt", "india", "ukraine"]),
    ("typhoon", "typhon", "Typhon", "Eurofighter Typhoon", 4, "multirole", ["england", "germany", "italy", "turkey"]),
    ("vulcan", "volcan", "Volcan", "Avro Vulcan", 2, "bomber", ["england"]),
    ("he177", "he-177-greif", "He-177 Greif", "Heinkel He 177 Greif", 0, "bomber", ["germany"]),
    ("seavixen", "sea-vixa", "Sea Vixa", "de Havilland Sea Vixen", 2, "carrier", ["england"]),
    # --- Vanguard shared roster and Russia ---
    ("mig3", "mik-3-strela", "MiK-3 Strela", "MiG-3", 0, "piston", ["soviet", "russia"]),
    ("la11", "lav-11-fang", "LaV-11 Fang", "Lavochkin La-11", 0, "piston", ["soviet", "russia", "china"]),
    ("mig21", "mik-21-fishbone", "MiK-21 Fishbone", "MiG-21", 2, "fighter",
     ["soviet", "russia", "ukraine", "cuba", "india", "china", "pakistan", "iran", "egypt"]),
    ("mig23", "mik-23-flintlock", "MiK-23 Flintlock", "MiG-23", 3, "multirole",
     ["soviet", "russia", "ukraine", "cuba", "india", "egypt"]),
    ("mig25", "mik-25-foxbane", "MiK-25 Foxbane", "MiG-25", 3, "interceptor", ["soviet", "russia", "ukraine", "india"]),
    ("su25", "sk-25-rook", "Sk-25 Rook", "Sukhoi Su-25", 3, "attack", ["soviet", "russia", "ukraine", "iran"]),
    ("su27", "sk-27-flankard", "Sk-27 Flankard", "Sukhoi Su-27", 3, "fighter", ["soviet", "russia", "ukraine", "china"]),
    ("su30", "sk-30-flankard-m", "Sk-30 Flankard-M", "Sukhoi Su-30SM / MKI", 4, "multirole",
     ["soviet", "russia", "india", "china"]),
    ("su35", "sk-35-flankard-e", "Sk-35 Flankard-E", "Sukhoi Su-35", 4, "multirole",
     ["soviet", "russia", "china", "egypt", "iran"]),
    ("tu160", "tv-160-swanwing", "Tv-160 Swanwing", "Tupolev Tu-160", 3, "bomber", ["russia"]),
    ("su47", "sk-47-berkov", "Sk-47 Berkov", "Sukhoi Su-47 Berkut", "X", "stealth", ["soviet", "russia"]),
    ("yak141", "yk-141-freestyler", "Yk-141 Freestyler", "Yakovlev Yak-141", "X", "vtol", ["soviet", "russia"]),
    ("grom", "grom-k", "Grom-K", "Kronshtadt Grom", "X", "drone", ["russia"]),
    ("zeppelin", "zeppelin", "Zeppelin", "armoured airship", "X", "airship", VANGUARD),
    # --- Ukraine ---
    ("l39", "l-39u-albatross", "L-39U Albatross", "Aero L-39 Albatros", 2, "light", ["ukraine", "cuba", "egypt"]),
    ("an225", "an-225-dreamer", "An-225 Dreamer", "Antonov An-225 Mriya", 4, "transport", ["ukraine"]),
    # --- China, Turkey, Iran ---
    ("j20", "jx-20-jade-dragon", "JX-20 Jade Dragon", "Chengdu J-20", 5, "stealth", ["china"]),
    ("swarm", "swarm-drone", "Swarm Drone", "Kargu-style loitering drone", 3, "drone", ["turkey"]),
    ("saeqeh", "saeqa", "Saeqa", "HESA Saeqeh", 3, "fighter", ["iran"]),
    ("qaher", "qahir-x", "Qahir-X", "IAIO Qaher-313", "X", "stealth", ["iran"]),
]

NATION_NAMES = {
    "allies": "Union", "usa": "USA", "england": "England", "france": "France", "germany": "Germany",
    "japan": "Japan", "southkorea": "South Korea", "italy": "Italy", "egypt": "Egypt", "soviet": "Vanguard",
    "russia": "Russia", "ukraine": "Ukraine", "cuba": "Cuba", "india": "India", "china": "China",
    "turkey": "Turkey", "pakistan": "Pakistan", "iran": "Iran",
}

HEADER = "# GENERATED by artsrc/jets/make_jets.py - edit that script, not this file.\n"


def actor(jid):
    return "jet." + jid


def prereq(jid):
    return "jetwing." + jid


def main():
    files = set(os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "assets", "jets")))
    missing = [j[1] for j in JETS if j[1] not in files]
    assert not missing, f"no image in assets/jets for {missing}"
    for j in JETS:
        unknown = set(j[6]) - set(UNION + VANGUARD)
        assert not unknown, f"{j[0]}: unknown nations {unknown}"

    rules = [HEADER + "# National jet roster (IDEA-12): which nation may build which aircraft.\n"]

    # Each jet is unlocked by a prerequisite that the airfield (or helipad) gives only to its operators
    for building, bases in (("AFLD", ("mig", "yak")), ("HPAD", ("tran",))):
        rules.append(building + ":")
        for jid, _, _, _, _, role, nations in JETS:
            if ROLES[role][0] in bases:
                rules += [f"\tProvidesPrerequisite@{prereq(jid)}:", f"\t\tFactions: {', '.join(nations)}",
                          f"\t\tPrerequisite: {prereq(jid)}"]
        rules.append("")

    for order, (jid, _, _, _, tier, role, nations) in enumerate(JETS):
        base, cost, hp, speed, _ = ROLES[role]
        producer = "~hpad" if base == "tran" else "~afld"
        prereqs = [producer, "~" + prereq(jid)] + TIERS[tier]
        rules += [
            actor(jid).upper() + ":",
            f"\tInherits: {base.upper()}",
            "\tBuildable:",
            f"\t\tPrerequisites: {', '.join(prereqs)}",
            f"\t\tBuildPaletteOrder: {200 + order * 2}",
            f"\t\tDescription: actor-jet-{jid}.description",
        ]
        if tier == "X":
            rules.append("\t\tBuildLimit: 1")
        rules += [
            "\tValued:", f"\t\tCost: {cost}",
            "\tTooltip:", f"\t\tName: actor-jet-{jid}.name",
            "\tHealth:", f"\t\tHP: {hp}",
            "\tAircraft:", f"\t\tSpeed: {speed}",
            "\tPxNationalUnit:", f"\t\tFactions: {', '.join(nations)}",
            *( [JET_BOUNDS] if base != "tran" else [] ),  # transports keep their non-selectable Interactable
            JET_LANDING,
            "",
        ]

    seqs = [HEADER + "# Jets fly with the stock sprite of their base until they get their own HD sprites\n"
            "# (artsrc/units/meshes/make.sh <file> -> bits/hd/units/<file>.png, 32 facings, no ground shadow).\n"]
    for jid, file, *_ , role, _n in JETS:
        seqs += [actor(jid) + ":", f"\tInherits: {ROLES[role][0]}"]
        if os.path.exists(os.path.join(MOD, "bits", "hd", "units", f"{file}.png")):
            body = [f"\t\tFilename: ra|bits/hd/units/{file}.png", "\t\tStart: 0", "\t\tLength: 1", "\t\tFacings: 32",
                    "\t\tUseClassicFacings: False", f"\t\tScale: {JET_SCALE:.4f}"]
            seqs += ["\tidle:"] + body
            if ROLES[role][0] == "tran":
                # Chinook-based transports: no helicopter rotors on a plane, and the unload "door" frames
                # show the plane itself
                for rotor in ("rotor", "rotor2", "slow-rotor", "slow-rotor2"):
                    seqs += [f"\t{rotor}:", "\t\tFilename: ra|bits/hd/blank.png", "\t\tStart: 0", "\t\tLength: 1"]
                for anim in ("open", "unload"):
                    seqs += [f"\t{anim}:"] + body
        # The base's HD icon has TilesetFilenames, which beat Filename: drop them so this file shows.
        seqs += ["\ticon:", f"\t\tFilename: ra|bits/hd/jets/{file}.png", "\t\t-TilesetFilenames:", ""]

    ftl = [HEADER.replace("#", "##")]
    for jid, file, name, real, tier, role, nations in JETS:
        desc = ROLES[role][4].split("\n")
        flown = ", ".join(NATION_NAMES[n] for n in nations)
        era = "Prototype, one per player" if tier == "X" else f"Generation tier {tier}"
        ftl += [f"actor-jet-{jid} =", f"    .name = {name}", "    .description =",
                f"    {desc[0]}"] + [f"    {line}" for line in desc[1:]] + [
                f"      {era}", f"      Flown by: {flown}", ""]

    os.makedirs(os.path.join(MOD, "bits", "hd", "jets"), exist_ok=True)
    for path, lines in (("rules/jets.yaml", rules), ("sequences/jets.yaml", seqs), ("fluent/jets.ftl", ftl)):
        with open(os.path.join(MOD, path), "w") as out:
            out.write("\n".join(lines))
    print(f"wrote {len(JETS)} jets")


if __name__ == "__main__":
    main()
