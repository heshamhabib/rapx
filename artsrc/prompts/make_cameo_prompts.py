#!/usr/bin/env python3
"""
Generates artsrc/prompts/cameo-prompts.md: one ChatGPT image prompt per sidebar cameo, in the style of the
Red Alert 2 build icons (a dramatic painted-looking 3D render of the unit in a battlefield scene, see
artsrc/px-cameos/reference-ra2-cameos.png). Edit the tables below and re-run.

  python3 artsrc/prompts/make_cameo_prompts.py
  python3 artsrc/prompts/generate_images.py --prompts cameo-prompts.md --category cameos
  python3 artsrc/px-cameos/generate.py        # turns assets/cameos/*.png into the 240x160 sidebar tiles

The Save-as name is the sequence image name (e.g. 2tnk), so px-cameos/generate.py finds it.
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cameo-prompts.md")

SIDE = {
    "allied": "Allied look: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, "
              "clean edges, glass sensor domes; small steel-blue accent stripes",
    "soviet": "Soviet look: heavy brutalist 2026 Soviet industrial, thick riveted steel, dark olive-grey with rust-red panels, "
              "massive bolts and exposed pipes; small deep-red accent stripes",
    "neutral": "Military look: modern 2026 military engineering, dark steel, concrete and olive-grey paint, hazard stripes; "
               "small deep-red accent stripes",
}

# Scene behind the subject, by kind. Kept simple and softly blurred so the subject reads at 120x80 pixels.
SCENE = {
    "building": "standing inside a fortified military base at golden hour, other base buildings and floodlights softly blurred behind it",
    "defense": "guarding the edge of a military base, sandbags and barbed wire in the foreground, a smoky battlefield softly blurred behind it",
    "vehicle": "driving through a dusty battlefield, kicking up dust, burning wrecks and smoke softly blurred behind it",
    "infantry": "advancing across a ruined city street, rubble and smoke softly blurred behind",
    "aircraft": "flying low over a battlefield, clouds and smoke columns softly blurred behind it, motion streaks",
    "ship": "cutting through rough sea with a big bow wave, spray and a stormy sky softly blurred behind it",
    "power": "a dramatic scene from above the battlefield",
}

# (save-as image name, display name, side, kind, subject description)
ITEMS = [
    # --- Buildings ---
    ("fact", "Construction Yard", "neutral", "building", "a large fortified Construction Yard assembly plant with a tall crane arm and vehicle bay doors"),
    ("powr", "Power Plant", "neutral", "building", "a compact Power Plant with two steaming cooling stacks, transformers and thick power cables"),
    ("apwr", "Advanced Power Plant", "neutral", "building", "a big Advanced Power Plant with three glowing reactor cores visible through vents and cooling towers"),
    ("proc", "Ore Refinery", "neutral", "building", "an Ore Refinery with a truck unloading dock, conveyors, crushers and storage silos, an ore truck unloading glowing ore"),
    ("silo", "Ore Silo", "neutral", "building", "a squat armoured Ore Silo tank with gauges and a hatch, glowing ore visible inside a window"),
    ("weap", "War Factory", "neutral", "building", "a massive War Factory with a huge open vehicle bay door, a new tank rolling out"),
    ("fix", "Service Depot", "neutral", "building", "a Service Depot repair platform with robotic repair arms working on a tank"),
    ("dome", "Radar Dome", "neutral", "building", "a Radar Dome with a large white radome and antenna masts"),
    ("hpad", "Helipad", "allied", "building", "an Allied Helipad with a landing pad, lights and a helicopter landing on it"),
    ("afld", "Airfield", "soviet", "building", "a Soviet Airfield with a hangar, control tower and a jet on the runway"),
    ("tent", "Allied Barracks", "allied", "building", "an Allied Barracks: a modern fortified troop building with a flag and soldiers marching out"),
    ("barr", "Soviet Barracks", "soviet", "building", "a Soviet Barracks: a heavy concrete troop bunker with red banners and soldiers marching out"),
    ("kenn", "Kennel", "soviet", "building", "a Soviet Kennel for attack dogs: a small fenced concrete building with a guard dog"),
    ("syrd", "Naval Yard", "allied", "building", "an Allied Naval Yard on water with gantry cranes and a warship being built"),
    ("spen", "Sub Pen", "soviet", "building", "a Soviet Sub Pen on water: a concrete submarine bunker with a submarine surfacing"),
    ("atek", "Allied Tech Center", "allied", "building", "an Allied Tech Center: a high-tech laboratory with glass domes, antennas and a satellite dish"),
    ("stek", "Soviet Tech Center", "soviet", "building", "a Soviet Tech Center: a heavy research complex with glowing reactor vents and a tall antenna"),
    ("pdox", "Chronosphere", "allied", "building", "the Allied Chronosphere: a giant glowing blue sphere held by emitter arms, crackling with time energy"),
    ("iron", "Iron Curtain", "soviet", "building", "the Soviet Iron Curtain: a huge emitter dish glowing deep red over a fortified base"),
    ("mslo", "Missile Silo", "neutral", "building", "a Missile Silo with its blast doors open and a nuclear missile rising, steam pouring out"),
    ("gap", "Gap Generator", "allied", "building", "an Allied Gap Generator: a tall tower projecting a dark shroud field around it"),
    ("oilr", "Oil Rig", "neutral", "building", "an offshore Oil Rig on the sea with a burning gas flare and pumping machinery"),
    ("hosp", "Hospital", "neutral", "building", "a field Hospital building with a red cross on the roof and ambulances outside"),
    # --- Defences ---
    ("pbox", "Pillbox", "allied", "defense", "a concrete Pillbox bunker with a machine gun firing from its slit"),
    ("hbox", "Camo Pillbox", "allied", "defense", "a camouflaged Pillbox bunker hidden under netting and foliage, a gun firing"),
    ("gun", "Turret", "allied", "defense", "an Allied cannon Turret firing, muzzle flash"),
    ("ftur", "Flame Tower", "soviet", "defense", "a Soviet Flame Tower spraying a jet of fire"),
    ("tsla", "Tesla Coil", "soviet", "defense", "a Soviet Tesla Coil tower crackling with a huge bolt of blue-white electricity"),
    ("agun", "AA Gun", "allied", "defense", "an Allied twin-barrel anti-aircraft gun firing tracers into the sky"),
    ("sam", "SAM Site", "soviet", "defense", "a Soviet SAM Site launching a surface-to-air missile with a smoke trail"),
    ("sbag", "Sandbags", "neutral", "defense", "a curved wall of stacked sandbags with a soldier behind it"),
    ("fenc", "Wire Fence", "soviet", "defense", "a Soviet barbed-wire fence with concrete posts and warning signs"),
    ("brik", "Concrete Wall", "neutral", "defense", "a thick reinforced concrete wall section with hazard stripes"),
    # --- Vehicles ---
    ("1tnk", "Light Tank", "allied", "vehicle", "a fast Allied Light Tank with a small turret"),
    ("2tnk", "Medium Tank", "allied", "vehicle", "an Allied Medium Tank, main battle tank firing its cannon"),
    ("3tnk", "Heavy Tank", "soviet", "vehicle", "a Soviet Heavy Tank with a twin-barrel turret"),
    ("4tnk", "Mammoth Tank", "soviet", "vehicle", "a huge Soviet Mammoth Tank with twin cannons and missile pods, firing"),
    ("v2rl", "V2 Rocket Launcher", "soviet", "vehicle", "a Soviet V2 Rocket Launcher truck raising a large missile to fire"),
    ("arty", "Artillery", "allied", "vehicle", "an Allied self-propelled Artillery gun firing a shell, big muzzle blast"),
    ("harv", "Ore Truck", "neutral", "vehicle", "an armoured Ore Truck harvesting glowing ore crystals"),
    ("mcv", "MCV", "neutral", "vehicle", "a huge Mobile Construction Vehicle with a folded crane on its back"),
    ("jeep", "Ranger", "allied", "vehicle", "a fast Allied Ranger jeep with a mounted machine gun"),
    ("apc", "APC", "allied", "vehicle", "an Allied armoured personnel carrier with its rear ramp open and troops jumping out"),
    ("mnly", "Minelayer", "neutral", "vehicle", "a tracked Minelayer vehicle dropping mines behind it"),
    ("truk", "Supply Truck", "neutral", "vehicle", "an armoured Supply Truck loaded with crates"),
    ("mgg", "Mobile Gap Generator", "allied", "vehicle", "an Allied Mobile Gap Generator truck with a tall emitter projecting a dark shroud field"),
    ("mrj", "Mobile Radar Jammer", "allied", "vehicle", "an Allied Mobile Radar Jammer truck with a large jamming dish and visible interference waves"),
    ("ttnk", "Tesla Tank", "soviet", "vehicle", "a Soviet Tesla Tank firing a crackling bolt of electricity from its coil turret"),
    ("ftrk", "Mobile Flak", "soviet", "vehicle", "a Soviet Mobile Flak truck firing anti-aircraft bursts into the sky"),
    ("dtrk", "Demolition Truck", "soviet", "vehicle", "a Soviet Demolition Truck loaded with a huge glowing warhead, radiation warning signs"),
    ("ctnk", "Chrono Tank", "allied", "vehicle", "an Allied Chrono Tank shimmering blue as it teleports, missile pods on its sides"),
    ("qtnk", "M.A.D. Tank", "soviet", "vehicle", "a Soviet M.A.D. Tank with a huge seismic piston sending shockwaves into the ground"),
    ("stnk", "Phase Transport", "allied", "vehicle", "an Allied Phase Transport fading into stealth, half transparent"),
    # --- Infantry ---
    ("e1", "Rifle Infantry", "neutral", "infantry", "a rifle infantry soldier firing an assault rifle"),
    ("e2", "Grenadier", "soviet", "infantry", "a Soviet Grenadier throwing a grenade"),
    ("e3", "Rocket Soldier", "neutral", "infantry", "a Rocket Soldier firing a shoulder-launched rocket"),
    ("e4", "Flamethrower", "soviet", "infantry", "a Soviet Flamethrower trooper spraying fire"),
    ("e6", "Engineer", "neutral", "infantry", "a combat Engineer in a hard hat with a toolkit and wrench"),
    ("e7", "Tanya", "allied", "infantry", "an elite Allied female commando with twin pistols and explosive charges, confident pose"),
    ("spy", "Spy", "allied", "infantry", "an Allied Spy in a long coat and hat, disguise and silenced pistol"),
    ("thf", "Thief", "allied", "infantry", "a sneaky Allied Thief in dark clothes carrying a bag of stolen money"),
    ("medi", "Medic", "allied", "infantry", "an Allied field Medic with a medical kit tending to a soldier"),
    ("mech", "Mechanic", "allied", "infantry", "an Allied field Mechanic with a big wrench repairing a vehicle"),
    ("shok", "Shock Trooper", "soviet", "infantry", "a Soviet Shock Trooper in armour firing an electric Tesla gun"),
    ("dog", "Attack Dog", "soviet", "infantry", "a fierce Soviet attack dog leaping forward, snarling"),
    # --- Aircraft ---
    ("mig", "MiK-29 Fulcra", "soviet", "aircraft", "a Soviet MiG-29-style twin-tail jet fighter firing missiles"),
    ("yak", "Yk-9 Stormer", "soviet", "aircraft", "a Soviet Yak-9-style propeller fighter-bomber strafing"),
    ("heli", "Longbow", "allied", "aircraft", "an Allied Apache Longbow-style attack helicopter firing missiles"),
    ("hind", "Hind", "soviet", "aircraft", "a Soviet Mi-24 Hind-style gunship helicopter firing rockets"),
    ("tran", "Chinook", "allied", "aircraft", "an Allied Chinook-style twin-rotor transport helicopter"),
    ("mh60", "Black Hawk", "allied", "aircraft", "an Allied Black Hawk-style utility helicopter with door gunners"),
    # --- Ships ---
    ("ss", "Submarine", "soviet", "ship", "a Soviet attack submarine surfacing, torpedo launching"),
    ("msub", "Missile Submarine", "soviet", "ship", "a Soviet missile submarine launching a cruise missile from the sea"),
    ("dd", "Destroyer", "allied", "ship", "an Allied Destroyer warship firing its deck gun"),
    ("ca", "Cruiser", "allied", "ship", "an Allied heavy Cruiser firing a broadside from its big guns"),
    ("lst", "Transport", "neutral", "ship", "a landing craft Transport with its bow ramp down at a beach"),
    ("pt", "Gunboat", "allied", "ship", "a fast Allied Gunboat speeding with a mounted gun"),
]

# Support powers (saved as power-<name>.png; their sidebar widget still uses the stock icons until wired up)
POWERS = [
    ("power-abomb", "Atom Bomb", "neutral", "a nuclear missile streaking down onto a target, a mushroom cloud starting to rise"),
    ("power-chrono", "Chronoshift", "allied", "tanks vanishing in a flash of blue time energy and reappearing elsewhere"),
    ("power-gps", "GPS Satellite", "allied", "an Allied satellite in orbit above the Earth, scanning beams sweeping the ground"),
    ("power-invuln", "Iron Curtain", "soviet", "a Soviet tank glowing deep red, wrapped in an invulnerability field, shells bouncing off"),
    ("power-parabombs", "Parabombs", "soviet", "a Soviet bomber dropping bombs on parachutes over a target"),
    ("power-paratroopers", "Paratroopers", "soviet", "Soviet paratroopers jumping from a transport plane, parachutes opening"),
    ("power-sonar", "Sonar Pulse", "allied", "a sonar pulse ring spreading through the dark sea, revealing a hidden submarine"),
    ("power-spyplane", "Spy Plane", "soviet", "a high-altitude Soviet spy plane flying over the battlefield taking photos"),
]

PROMPT = (
    "Sidebar build-icon artwork for a real-time strategy game, in the style of the classic Command & Conquer: Red Alert 2 "
    "build icons: a dramatic, cinematic, highly detailed photorealistic 3D render. Subject: {subject}, {scene}. "
    "Camera: low three-quarter front view, slightly below eye level so the subject looks powerful; the subject fills about "
    "70 percent of the frame, centred and slightly low, with the whole subject visible and a strong clear silhouette. "
    "{side}. Lighting: warm golden-hour sun from the left with a bright rim light separating the subject from the background, "
    "shallow depth of field so the background is soft and the subject is sharp, rich contrast, saturated but realistic colours, "
    "dust and atmosphere. It must read clearly as a tiny 120 x 80 pixel icon: simple bold shapes, no clutter around the subject. "
    "No text, no letters, no numbers, no logos, no emblems, no flags, no insignia, no watermark, no frame, no border, no UI. "
    "Landscape image, aspect ratio 3:2."
)

POWER_PROMPT = (
    "Sidebar special-power icon artwork for a real-time strategy game, in the style of the classic Command & Conquer: Red Alert 2 "
    "icons: a dramatic, cinematic, highly detailed photorealistic 3D render. Scene: {subject}. {side}. Bold, simple composition "
    "with one clear focal point, strong light and colour contrast, readable as a tiny 120 x 80 pixel icon. "
    "No text, no letters, no numbers, no logos, no emblems, no flags, no insignia, no watermark, no frame, no border, no UI. "
    "Landscape image, aspect ratio 3:2."
)


def main():
    lines = [
        "# RedAlert Project X - sidebar cameo prompts (ChatGPT)",
        "",
        "Generated by `make_cameo_prompts.py`. Do not edit by hand: edit the script and re-run it.",
        "",
        "Red Alert 2-style build icons for every building, defence, unit and support power in the sidebar.",
        "",
        "**How to use**",
        "",
        "1. Automatic: `python3 artsrc/prompts/generate_images.py --prompts cameo-prompts.md --category cameos` saves",
        "   `assets/cameos/<name>.png`. Once one image looks right, add `--ref ../../assets/cameos/<that>.png` so every other",
        "   cameo matches its style. Do not attach the RA2 reference picture itself (it contains logos and a watermark).",
        "2. Manual: one ChatGPT chat per cameo; save each image under its **Save as** name in `assets/cameos/`.",
        "3. Then run `python3 artsrc/px-cameos/generate.py`: painted cameos in `assets/cameos/` take priority over the",
        "   rendered ones and are cropped to the 3:2 tile (240 x 160) automatically.",
        "4. Reject an image if it has text, logos or a frame, if the subject is cut off or tiny, or if the background is busier",
        "   than the subject. Regenerate.",
        "",
        "New units and buildings from the design ideas get a row in `make_cameo_prompts.py` when they are added to the game.",
        "",
    ]
    n = 0
    sections = [("Buildings", "building"), ("Defenses", "defense"), ("Vehicles", "vehicle"),
                ("Infantry", "infantry"), ("Aircraft", "aircraft"), ("Ships", "ship")]
    # One "## Cameos" section (what generate_images.py reads), with readable sub-headings as bold lines.
    lines += ["## Cameos", ""]
    for title, kind in sections:
        lines += ["**%s**" % title, ""]
        for name, label, side, k, subject in ITEMS:
            if k != kind:
                continue
            n += 1
            prompt = PROMPT.format(subject=subject, scene=SCENE[kind], side=SIDE[side])
            lines += ["### %d. %s" % (n, label), "Save as: `%s.png`" % name, "", "```", prompt, "```", ""]
    lines += ["## Support powers", ""]
    for name, label, side, subject in POWERS:
        n += 1
        prompt = POWER_PROMPT.format(subject=subject, side=SIDE[side])
        lines += ["### %d. %s" % (n, label), "Save as: `%s.png`" % name, "", "```", prompt, "```", ""]

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wrote %s: %d cameos, %d support powers" % (OUT, len(ITEMS), len(POWERS)))


if __name__ == "__main__":
    main()
